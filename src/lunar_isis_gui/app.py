from __future__ import annotations

import os
import json
import queue
import subprocess
import sys
import threading
import tkinter as tk
import xml.etree.ElementTree as ElementTree
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import cv2

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
        self.registration_source = tk.StringVar()
        self.registration_references: list[Path] = []
        self.registration_output = tk.StringVar(value=str(ROOT / "outputs" / "lunareg-gui"))
        self.registration_method = tk.StringVar(value="sift")
        self.registration_projection = tk.StringVar(value="auto")
        self.registration_max_dimension = tk.StringVar(value="1024")
        self.registration_status = tk.StringVar(value="Ready for registration")
        self.registration_batch_root = Path(self.registration_output.get())
        self.registration_stage = tk.StringVar(value="Waiting to start")
        self.registration_preview: tk.PhotoImage | None = None
        self.active_registration_output: Path | None = None
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
        viewport = ttk.Frame(self, style="App.TFrame")
        viewport.pack(fill="both", expand=True)
        canvas = tk.Canvas(viewport, background="#11191c", highlightthickness=0)
        scrollbar = ttk.Scrollbar(viewport, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        outer = ttk.Frame(canvas, style="App.TFrame", padding=28)
        window_id = canvas.create_window((0, 0), window=outer, anchor="nw")
        outer.bind("<Configure>", lambda _event: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda event: canvas.itemconfigure(window_id, width=event.width))
        canvas.bind_all("<MouseWheel>", lambda event: canvas.yview_scroll(-int(event.delta / 120), "units"))
        canvas.bind_all("<Button-4>", lambda _event: canvas.yview_scroll(-3, "units"))
        canvas.bind_all("<Button-5>", lambda _event: canvas.yview_scroll(3, "units"))
        ttk.Label(outer, text="Lunar ISIS Workbench", style="Title.TLabel").pack(anchor="w")
        ttk.Label(outer, text="Import products, register OHRC against NAC, and inspect every pipeline stage.", style="Subtle.TLabel").pack(anchor="w", pady=(5, 18))

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

        registration_panel = ttk.Frame(outer, style="Panel.TFrame", padding=18)
        registration_panel.pack(fill="x", pady=(0, 18))
        ttk.Label(registration_panel, text="VISUAL REGISTRATION PIPELINE", style="PanelHead.TLabel").pack(anchor="w")
        source_row = ttk.Frame(registration_panel, style="Panel.TFrame")
        source_row.pack(fill="x", pady=(10, 6))
        ttk.Label(source_row, text="OHRC source", style="Panel.TLabel", width=14).pack(side="left")
        ttk.Entry(source_row, textvariable=self.registration_source, state="readonly").pack(side="left", fill="x", expand=True, ipady=5)
        ttk.Button(source_row, text="Choose OHRC", command=self.choose_registration_source, style="Secondary.TButton").pack(side="left", padx=(8, 0))
        reference_row = ttk.Frame(registration_panel, style="Panel.TFrame")
        reference_row.pack(fill="x", pady=6)
        ttk.Label(reference_row, text="NAC references", style="Panel.TLabel", width=14).pack(side="left", anchor="n")
        self.reference_list = tk.Listbox(
            reference_row, height=3, selectmode="extended", background="#0b1012",
            foreground="#c5d1ce", selectbackground="#536b36", relief="flat",
        )
        self.reference_list.pack(side="left", fill="x", expand=True)
        ref_buttons = ttk.Frame(reference_row, style="Panel.TFrame")
        ref_buttons.pack(side="left", padx=(8, 0), anchor="n")
        ttk.Button(ref_buttons, text="Add NAC files", command=self.choose_registration_references, style="Secondary.TButton").pack(fill="x")
        ttk.Button(ref_buttons, text="Add NAC folder", command=self.choose_registration_folder, style="Secondary.TButton").pack(fill="x", pady=(6, 0))
        ttk.Button(ref_buttons, text="Use all derived NAC", command=self.add_all_derived_references, style="Secondary.TButton").pack(fill="x", pady=(6, 0))
        ttk.Button(ref_buttons, text="Clear list", command=self.clear_registration_references, style="Secondary.TButton").pack(fill="x", pady=(6, 0))
        options = ttk.Frame(registration_panel, style="Panel.TFrame")
        options.pack(fill="x", pady=(6, 0))
        ttk.Label(options, text="Projection", style="Panel.TLabel").pack(side="left")
        ttk.Combobox(options, textvariable=self.registration_projection, values=("auto", "fallback"), state="readonly", width=10).pack(side="left", padx=(6, 14))
        ttk.Label(options, text="Matcher", style="Panel.TLabel").pack(side="left")
        ttk.Combobox(options, textvariable=self.registration_method, values=("sift", "auto", "loftr"), state="readonly", width=10).pack(side="left", padx=(6, 14))
        ttk.Label(options, text="Max dimension", style="Panel.TLabel").pack(side="left")
        ttk.Entry(options, textvariable=self.registration_max_dimension, width=8).pack(side="left", padx=(6, 14))
        self.registration_button = ttk.Button(options, text="Run visual registration", command=self.run_registration, style="Accent.TButton")
        self.registration_button.pack(side="left", padx=(4, 0))
        ttk.Label(options, textvariable=self.registration_status, style="Subtle.TLabel").pack(side="right")

        monitor = ttk.Frame(outer, style="Panel.TFrame", padding=18)
        monitor.pack(fill="both", expand=True)
        ttk.Label(monitor, text="PIPELINE MONITOR", style="PanelHead.TLabel").pack(anchor="w")
        monitor_body = ttk.Frame(monitor, style="Panel.TFrame")
        monitor_body.pack(fill="both", expand=True, pady=(10, 0))
        left = ttk.Frame(monitor_body, style="Panel.TFrame")
        left.pack(side="left", fill="y", padx=(0, 18))
        self.stage_labels: list[ttk.Label] = []
        for index, label in enumerate(("1  Load source", "2  Project reference", "3  Crop overlap", "4  Match features", "5  Fit RANSAC", "6  Write outputs")):
            stage = ttk.Label(left, text=f"○  {label}", style="Panel.TLabel", width=24)
            stage.pack(anchor="w", pady=3)
            self.stage_labels.append(stage)
        ttk.Label(left, textvariable=self.registration_stage, style="Subtle.TLabel", wraplength=190).pack(anchor="w", pady=(14, 0))
        self.preview_label = ttk.Label(monitor_body, text="Intermediate images will appear here", style="Panel.TLabel", anchor="center")
        self.preview_label.pack(side="left", fill="both", expand=True)

        output_panel = ttk.Frame(outer, style="Panel.TFrame", padding=18)
        output_panel.pack(fill="x", pady=(0, 18))
        ttk.Label(output_panel, text="ISIS OUTPUT", style="PanelHead.TLabel").pack(anchor="w")
        ttk.Label(output_panel, textvariable=self.output_path, style="Panel.TLabel", wraplength=850).pack(anchor="w", pady=(10, 0))

        log_panel = ttk.Frame(outer, style="Panel.TFrame", padding=18)
        log_panel.pack(fill="both", expand=True)
        ttk.Label(log_panel, text="COMMAND LOG", style="PanelHead.TLabel").pack(anchor="w")
        log_frame = ttk.Frame(log_panel, style="Panel.TFrame")
        log_frame.pack(fill="both", expand=True, pady=(10, 0))
        self.log = tk.Text(log_frame, height=18, background="#0b1012", foreground="#c5d1ce", insertbackground="#d7f36b", relief="flat", padx=12, pady=10, wrap="word")
        scrollbar = ttk.Scrollbar(log_frame, orient="vertical", command=self.log.yview)
        self.log.configure(yscrollcommand=scrollbar.set)
        self.log.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def choose_registration_source(self) -> None:
        path = filedialog.askopenfilename(
            title="Choose OHRC source cube",
            initialdir=str(ROOT / "data"),
            filetypes=[("ISIS cubes", "*.cub"), ("All files", "*")],
        )
        if path:
            self.registration_source.set(str(Path(path).resolve()))
            self.registration_status.set("OHRC source selected")

    def choose_registration_references(self) -> None:
        paths = filedialog.askopenfilenames(
            title="Choose NAC reference cubes",
            initialdir=str(ROOT / "data"),
            filetypes=[("ISIS cubes", "*.cub"), ("All files", "*")],
        )
        if paths:
            self.add_reference_paths(list(paths))

    def add_reference_paths(self, paths: tuple[str, ...] | list[Path]) -> None:
        for value in paths:
            resolved = Path(value).resolve()
            if resolved.is_file() and resolved not in self.registration_references:
                self.registration_references.append(resolved)
                self.reference_list.insert("end", str(resolved))
        self.registration_status.set(f"{len(self.registration_references)} NAC reference(s) selected")

    def choose_registration_folder(self) -> None:
        folder = filedialog.askdirectory(title="Choose folder containing NAC cubes", initialdir=str(ROOT / "data"))
        if folder:
            self.add_reference_paths(sorted(Path(folder).glob("*.cub")))

    def add_all_derived_references(self) -> None:
        self.add_reference_paths(sorted((DERIVED_ROOT / "nac").glob("*.cub")))

    def clear_registration_references(self) -> None:
        self.registration_references.clear()
        self.reference_list.delete(0, "end")
        self.registration_status.set("No NAC references selected")

    def set_stage(self, index: int) -> None:
        for position, label in enumerate(self.stage_labels):
            prefix = "●" if position == index else ("✓" if position < index else "○")
            label.configure(text=f"{prefix}  {label.cget('text')[3:]}")

    def update_preview(self, path: Path) -> None:
        if not path.is_file():
            return
        image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        if image is None:
            return
        height, width = image.shape[:2]
        scale = min(1.0, 560 / max(width, height))
        if scale < 1:
            image = cv2.resize(image, (max(1, int(width * scale)), max(1, int(height * scale))), interpolation=cv2.INTER_AREA)
        preview = path.with_suffix(".preview.png")
        cv2.imwrite(str(preview), image)
        self.registration_preview = tk.PhotoImage(file=str(preview))
        self.preview_label.configure(image=self.registration_preview, text="")

    def run_registration(self) -> None:
        if self.worker and self.worker.is_alive():
            return
        if not self.registration_source.get() or not self.registration_references:
            messagebox.showwarning("Select products", "Choose one OHRC source and at least one NAC reference.")
            return
        try:
            max_dimension = int(self.registration_max_dimension.get())
            if max_dimension <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Invalid dimension", "Max dimension must be a positive integer.")
            return
        self.registration_button.configure(state="disabled")
        self.registration_status.set("Running...")
        self.registration_stage.set("Starting registration batch")
        self.write_log("\n=== Visual registration batch ===\n")
        self.registration_batch_root = Path(self.registration_output.get())
        self.worker = threading.Thread(
            target=self.run_registration_batch,
            args=(
                Path(self.registration_source.get()),
                list(self.registration_references),
                max_dimension,
                self.registration_batch_root,
            ),
            daemon=True,
        )
        self.worker.start()

    def run_registration_batch(
        self, source: Path, references: list[Path], max_dimension: int, batch_root: Path
    ) -> None:
        batch_root.mkdir(parents=True, exist_ok=True)
        for reference in references:
            output = batch_root / reference.stem
            command = [
                sys.executable, "-m", "lunar_isis_gui.register", str(source), str(reference), str(output),
                "--projection-method", self.registration_projection.get(),
                "--method", self.registration_method.get(),
                "--max-dimension", str(max_dimension), "--save-intermediates",
            ]
            environment = os.environ.copy()
            source_root = str(ROOT / "src")
            existing_pythonpath = environment.get("PYTHONPATH")
            environment["PYTHONPATH"] = (
                f"{source_root}{os.pathsep}{existing_pythonpath}"
                if existing_pythonpath
                else source_root
            )
            self.process_queue.put(("reg_start", reference.stem))
            try:
                process = subprocess.Popen(
                    command,
                    cwd=ROOT,
                    env=environment,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                )
                assert process.stdout is not None
                for line in process.stdout:
                    self.process_queue.put(("reg_log", f"[{reference.stem}] {line}"))
                code = process.wait()
                self.process_queue.put(("reg_done", json.dumps({"reference": reference.stem, "output": str(output), "code": code})))
            except OSError as error:
                self.process_queue.put(("reg_error", str(error)))
        self.process_queue.put(("reg_batch_done", ""))

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
                elif kind == "reg_start":
                    self.registration_stage.set(f"Running {value}")
                    self.registration_status.set(f"Processing {value}")
                    self.active_registration_output = self.registration_batch_root / value
                    self.set_stage(0)
                elif kind == "reg_log":
                    self.write_log(value)
                    for index, marker in enumerate(("[1/6]", "[2/6]", "[3/6]", "[4/6]", "[5/6]", "[6/6]")):
                        if marker in value:
                            self.set_stage(index)
                            self.registration_stage.set(value.strip())
                            checkpoint = {
                                1: "02_projection.png",
                                2: "03_overlap.png",
                                3: "04_matches.png",
                                4: "05_ransac.png",
                            }.get(index)
                            if checkpoint and self.active_registration_output:
                                preview_path = self.active_registration_output / checkpoint
                                self.after(250, lambda path=preview_path: self.update_preview(path))
                elif kind == "reg_done":
                    payload = json.loads(value)
                    output = Path(payload["output"])
                    diagnostic = output / "diagnostic.png"
                    if diagnostic.is_file():
                        self.update_preview(diagnostic)
                    elif (output / "05_ransac.png").is_file():
                        self.update_preview(output / "05_ransac.png")
                    elif (output / "04_matches.png").is_file():
                        self.update_preview(output / "04_matches.png")
                    status = "accepted" if payload["code"] == 0 else "rejected"
                    self.write_log(f"[{payload['reference']}] {status}; checkpoints: {output}\n")
                elif kind == "reg_error":
                    self.write_log(f"Registration process error: {value}\n")
                elif kind == "reg_batch_done":
                    self.registration_button.configure(state="normal")
                    self.registration_status.set("Batch complete")
                    self.registration_stage.set("All selected references processed; inspect the log and previews.")
                    self.set_stage(6)
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
