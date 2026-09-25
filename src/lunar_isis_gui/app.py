from __future__ import annotations

import os
import queue
import subprocess
import threading
import tkinter as tk
import xml.etree.ElementTree as ElementTree
from pathlib import Path
from tkinter import filedialog, messagebox, ttk


ROOT = Path(__file__).resolve().parents[2]
DERIVED_ROOT = ROOT / "data" / "derived" / "isis"


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def label_values(label_path: Path, name: str) -> list[str]:
    root = ElementTree.parse(label_path).getroot()
    return [
        element.text.strip()
        for element in root.iter()
        if local_name(element.tag) == name and element.text
    ]


def find_sibling_payload(label_path: Path) -> Path:
    names = label_values(label_path, "file_name")
    for name in names:
        candidate = label_path.parent / name
        if candidate.is_file():
            return candidate
        lower_name = name.lower()
        for sibling in label_path.parent.iterdir():
            if sibling.is_file() and sibling.name.lower() == lower_name:
                return sibling
    for candidate in label_path.parent.iterdir():
        if candidate.is_file() and candidate.suffix.lower() in {".img", ".imq"}:
            return candidate
    raise FileNotFoundError(f"No image payload found beside {label_path}")


def classify(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".cub", ".tif", ".tiff"}:
        return "ISIS product"
    if suffix == ".xml":
        try:
            title = " ".join(label_values(path, "title")).lower()
            names = " ".join(label_values(path, "name")).lower()
        except (OSError, ElementTree.ParseError):
            title = ""
            names = ""
        if "ohrc" in title or "orbiter high resolution camera" in names or "_ohr_" in path.name.lower():
            return "OHRC"
        return "NAC"
    if suffix in {".img", ".imq"}:
        return "NAC"
    return "Unknown"


def find_tool(name: str) -> Path | None:
    candidates = []
    for variable in ("ISISROOT", "CONDA_PREFIX"):
        value = os.environ.get(variable)
        if value:
            candidates.append(Path(value) / "bin" / name)
    candidates.append(Path.home() / "miniforge3" / "envs" / "isis" / "bin" / name)
    candidates.append(Path.home() / "mambaforge" / "envs" / "isis" / "bin" / name)
    for candidate in candidates:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate
    path_value = os.environ.get("PATH", "")
    for directory in path_value.split(os.pathsep):
        candidate = Path(directory) / name
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate
    return None


class IsisLauncher(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Lunar ISIS Workbench")
        self.geometry("940x650")
        self.minsize(780, 520)
        self.configure(background="#11191c")
        self.selected_path = tk.StringVar()
        self.detected_type = tk.StringVar(value="Select a source file")
        self.status = tk.StringVar(value="Ready")
        self.output_path = tk.StringVar(value="Output will be created under data/derived/isis")
        self.process_queue: queue.Queue[tuple[str, str]] = queue.Queue()
        self.worker: threading.Thread | None = None
        self.last_output: Path | None = None
        self.build_style()
        self.build_ui()
        self.after(100, self.consume_process_output)

    def build_style(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("App.TFrame", background="#11191c")
        style.configure("Panel.TFrame", background="#1a2529")
        style.configure("Title.TLabel", background="#11191c", foreground="#eef3f2", font=("DejaVu Sans", 22, "bold"))
        style.configure("Subtle.TLabel", background="#11191c", foreground="#9aa9ac", font=("DejaVu Sans", 10))
        style.configure("Panel.TLabel", background="#1a2529", foreground="#dce5e3", font=("DejaVu Sans", 10))
        style.configure("PanelHead.TLabel", background="#1a2529", foreground="#d7f36b", font=("DejaVu Sans", 10, "bold"))
        style.configure("Accent.TButton", background="#d7f36b", foreground="#11191c", padding=(14, 9), font=("DejaVu Sans", 10, "bold"))
        style.map("Accent.TButton", background=[("active", "#e6ff8c"), ("disabled", "#52605a")])
        style.configure("Secondary.TButton", background="#2a393d", foreground="#eef3f2", padding=(12, 8))
        style.map("Secondary.TButton", background=[("active", "#35484d")])
        style.configure("Type.TLabel", background="#33474a", foreground="#d7f36b", padding=(8, 4), font=("DejaVu Sans", 9, "bold"))

    def build_ui(self) -> None:
        outer = ttk.Frame(self, style="App.TFrame", padding=28)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="Lunar ISIS Workbench", style="Title.TLabel").pack(anchor="w")
        ttk.Label(outer, text="Import OHRC and NAC products, then open them in qview.", style="Subtle.TLabel").pack(anchor="w", pady=(5, 24))

        source_panel = ttk.Frame(outer, style="Panel.TFrame", padding=18)
        source_panel.pack(fill="x")
        ttk.Label(source_panel, text="SOURCE PRODUCT", style="PanelHead.TLabel").pack(anchor="w")
        path_row = ttk.Frame(source_panel, style="Panel.TFrame")
        path_row.pack(fill="x", pady=(12, 10))
        path_entry = ttk.Entry(path_row, textvariable=self.selected_path, state="readonly")
        path_entry.pack(side="left", fill="x", expand=True, ipady=7)
        ttk.Button(path_row, text="Browse files", command=self.choose_source, style="Secondary.TButton").pack(side="left", padx=(10, 0))
        info_row = ttk.Frame(source_panel, style="Panel.TFrame")
        info_row.pack(fill="x")
        self.type_badge = ttk.Label(info_row, textvariable=self.detected_type, style="Type.TLabel")
        self.type_badge.pack(side="left")
        ttk.Label(info_row, text="  XML labels are read beside their payload; NAC uses its attached PDS3 image label.", style="Panel.TLabel").pack(side="left")

        actions = ttk.Frame(outer, style="App.TFrame")
        actions.pack(fill="x", pady=18)
        self.import_button = ttk.Button(actions, text="Import with ISIS", command=self.import_source, style="Accent.TButton", state="disabled")
        self.import_button.pack(side="left")
        self.open_button = ttk.Button(actions, text="Open selected product", command=self.open_selected, style="Secondary.TButton")
        self.open_button.pack(side="left", padx=10)
        ttk.Button(actions, text="Clear", command=self.clear_selection, style="Secondary.TButton").pack(side="left")
        ttk.Label(actions, textvariable=self.status, style="Subtle.TLabel").pack(side="right")

        output_panel = ttk.Frame(outer, style="Panel.TFrame", padding=18)
        output_panel.pack(fill="x", pady=(0, 18))
        ttk.Label(output_panel, text="ISIS OUTPUT", style="PanelHead.TLabel").pack(anchor="w")
        ttk.Label(output_panel, textvariable=self.output_path, style="Panel.TLabel", wraplength=850).pack(anchor="w", pady=(10, 0))

        log_panel = ttk.Frame(outer, style="Panel.TFrame", padding=18)
        log_panel.pack(fill="both", expand=True)
        ttk.Label(log_panel, text="COMMAND LOG", style="PanelHead.TLabel").pack(anchor="w")
        log_frame = ttk.Frame(log_panel, style="Panel.TFrame")
        log_frame.pack(fill="both", expand=True, pady=(10, 0))
        self.log = tk.Text(log_frame, height=12, background="#0b1012", foreground="#c5d1ce", insertbackground="#d7f36b", relief="flat", padx=12, pady=10, wrap="word")
        scrollbar = ttk.Scrollbar(log_frame, orient="vertical", command=self.log.yview)
        self.log.configure(yscrollcommand=scrollbar.set)
        self.log.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def choose_source(self) -> None:
        path = filedialog.askopenfilename(
            title="Choose OHRC, NAC, ISIS cube, or GeoTIFF",
            initialdir=str(ROOT / "data"),
            filetypes=[
                ("Lunar products", "*.xml *.IMG *.img *.cub *.tif *.tiff"),
                ("All files", "*"),
            ],
        )
        if not path:
            return
        selected = Path(path).resolve()
        self.selected_path.set(str(selected))
        product_type = classify(selected)
        self.detected_type.set(product_type)
        self.import_button.configure(state="normal" if product_type in {"OHRC", "NAC"} else "disabled")
        self.output_path.set("Existing ISIS product selected" if product_type == "ISIS product" else "Output will be created under data/derived/isis")
        self.status.set("Source selected")
        self.write_log(f"Selected: {selected}\nDetected type: {product_type}\n")

    def clear_selection(self) -> None:
        self.selected_path.set("")
        self.detected_type.set("Select a source file")
        self.output_path.set("Output will be created under data/derived/isis")
        self.import_button.configure(state="disabled")
        self.status.set("Ready")

    def write_log(self, text: str) -> None:
        self.log.insert("end", text)
        self.log.see("end")

    def output_for(self, source: Path, product_type: str) -> Path:
        folder = DERIVED_ROOT / ("ohrc" if product_type == "OHRC" else "nac")
        folder.mkdir(parents=True, exist_ok=True)
        return folder / f"{source.stem}.cub"

    def build_import_command(self, source: Path) -> tuple[list[str], Path, str]:
        product_type = classify(source)
        if product_type == "OHRC":
            output = self.output_for(source, product_type)
            return ["isisimport", f"from={source}", f"to={output}"], output, product_type
        if product_type == "NAC":
            payload = find_sibling_payload(source) if source.suffix.lower() == ".xml" else source
            output = self.output_for(payload, product_type)
            return ["pds2isis", f"from={payload}", f"to={output}"], output, product_type
        raise ValueError("Select an OHRC XML label, NAC IMG file, or an existing ISIS product.")

    def import_source(self) -> None:
        if self.worker and self.worker.is_alive():
            return
        source = Path(self.selected_path.get())
        try:
            command, output, product_type = self.build_import_command(source)
            tool = find_tool(command[0])
            if tool is None:
                raise FileNotFoundError(f"ISIS command not found: {command[0]}. Activate the isis Conda environment first.")
            command[0] = str(tool)
        except (FileNotFoundError, ValueError, ElementTree.ParseError) as error:
            messagebox.showerror("Cannot import product", str(error))
            self.status.set("Import not started")
            return
        self.last_output = output
        self.output_path.set(str(output))
        self.import_button.configure(state="disabled")
        self.status.set(f"Importing {product_type}...")
        self.write_log(f"$ {' '.join(command)}\n")
        self.worker = threading.Thread(target=self.run_command, args=(command,), daemon=True)
        self.worker.start()

    def run_command(self, command: list[str]) -> None:
        try:
            process = subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
            assert process.stdout is not None
            for line in process.stdout:
                self.process_queue.put(("log", line))
            return_code = process.wait()
            self.process_queue.put(("done", str(return_code)))
        except OSError as error:
            self.process_queue.put(("error", str(error)))

    def consume_process_output(self) -> None:
        try:
            while True:
                kind, value = self.process_queue.get_nowait()
                if kind == "log":
                    self.write_log(value)
                elif kind == "done":
                    if value == "0":
                        self.status.set("Import complete")
                        self.write_log("\nImport complete. You can open the generated product.\n")
                        messagebox.showinfo("ISIS import complete", "The ISIS cube was created successfully.")
                    else:
                        self.status.set(f"ISIS exited with code {value}")
                        self.write_log(f"\nISIS exited with code {value}.\n")
                    self.import_button.configure(state="normal")
                elif kind == "error":
                    self.status.set("ISIS process failed")
                    self.write_log(f"\nProcess error: {value}\n")
                    self.import_button.configure(state="normal")
        except queue.Empty:
            pass
        self.after(100, self.consume_process_output)

    def open_selected(self) -> None:
        selected = Path(self.selected_path.get())
        target = self.last_output if self.last_output and self.last_output.is_file() else selected
        if not target.is_file() or target.suffix.lower() not in {".cub", ".tif", ".tiff"}:
            messagebox.showinfo("Import first", "Select an existing .cub/.tiff product or import an OHRC/NAC source first.")
            return
        qview = find_tool("qview")
        if qview is None:
            messagebox.showerror("ISIS not found", "qview was not found. Activate the isis Conda environment first.")
            return
        try:
            subprocess.Popen([str(qview), str(target)], cwd=ROOT, start_new_session=True)
            self.status.set("Opened in qview")
            self.write_log(f"$ {qview} {target}\n")
        except OSError as error:
            messagebox.showerror("Could not open qview", str(error))


def main() -> None:
    IsisLauncher().mainloop()


if __name__ == "__main__":
    main()
