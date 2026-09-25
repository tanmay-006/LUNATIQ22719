"""Read ISIS cubes through the command-line tools available in an ISIS install."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ElementTree
from pathlib import Path
from typing import Any, TypedDict

import numpy as np


class CubMetadata(TypedDict, total=False):
    """Metadata extracted from the cube and its adjacent product labels."""

    dimensions: tuple[int, int]
    geotransform: tuple[float, ...]
    gsd: float
    sun_vector: tuple[float, float, float]
    sun_azimuth: float
    sun_elevation: float
    label_path: str
    conversion_tool: str


class CubProduct(TypedDict):
    """Loaded cube image and metadata returned by :func:`load_cub_with_isis`."""

    image: np.ndarray
    metadata: CubMetadata


class CubLoaderError(RuntimeError):
    """Raised when a cube cannot be converted or read."""


def _find_tool(*names: str) -> tuple[str | None, str | None]:
    """Return the first executable and the environment variable that supplied it."""

    search_dirs: list[Path] = []
    source = None
    for variable in ("ISISROOT", "CONDA_PREFIX"):
        value = os.environ.get(variable)
        if value:
            search_dirs.append(Path(value) / "bin")
            source = variable
    search_dirs.append(Path(sys.executable).resolve().parent)
    for name in names:
        path = shutil.which(name)
        if path:
            return path, "PATH"
        for directory in search_dirs:
            candidate = directory / name
            if candidate.is_file() and os.access(candidate, os.X_OK):
                return str(candidate), source
    return None, None


def _run(command: list[str]) -> str:
    try:
        completed = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise CubLoaderError(f"Executable not found: {command[0]}") from exc
    except subprocess.CalledProcessError as exc:
        details = (exc.stderr or exc.stdout).strip()
        raise CubLoaderError(
            f"Command failed ({exc.returncode}): {' '.join(command)}\n{details}"
        ) from exc
    return completed.stdout


def _parse_gdalinfo(text: str) -> CubMetadata:
    metadata: CubMetadata = {}
    size_match = re.search(r"Size is (\d+),\s*(\d+)", text)
    if size_match:
        metadata["dimensions"] = (int(size_match.group(1)), int(size_match.group(2)))
    transform_match = re.search(
        r"Origin\s*=\s*\(([^,]+),([^)]+)\).*?"
        r"Pixel Size\s*=\s*\(([^,]+),([^)]+)\)",
        text,
        re.DOTALL,
    )
    if transform_match:
        origin_x, origin_y, pixel_x, pixel_y = (
            float(value) for value in transform_match.groups()
        )
        metadata["geotransform"] = (
            origin_x,
            pixel_x,
            0.0,
            origin_y,
            0.0,
            pixel_y,
        )
        metadata["gsd"] = (abs(pixel_x) + abs(pixel_y)) / 2.0
    return metadata


def _label_value(root: ElementTree.Element, *names: str) -> float | None:
    wanted = {name.casefold() for name in names}
    for element in root.iter():
        if element.tag.rsplit("}", 1)[-1].casefold() in wanted and element.text:
            try:
                return float(element.text.strip().split()[0])
            except ValueError:
                continue
    return None


def _find_label(cub_path: Path) -> Path | None:
    candidates = sorted(cub_path.parent.glob(f"{cub_path.stem}*.xml"))
    return candidates[0] if candidates else None


def _read_label_metadata(cub_path: Path, metadata: CubMetadata) -> None:
    label_path = _find_label(cub_path)
    if label_path is None:
        return
    try:
        root = ElementTree.parse(label_path).getroot()
    except (OSError, ElementTree.ParseError) as exc:
        raise CubLoaderError(f"Could not parse cube label {label_path}: {exc}") from exc
    metadata["label_path"] = str(label_path)
    gsd = _label_value(root, "gsd", "ground_sample_distance", "pixel_scale")
    if gsd is not None:
        metadata["gsd"] = gsd
    azimuth = _label_value(root, "sun_azimuth", "solar_azimuth")
    elevation = _label_value(root, "sun_elevation", "solar_elevation")
    if azimuth is not None:
        metadata["sun_azimuth"] = azimuth
    if elevation is not None:
        metadata["sun_elevation"] = elevation


def _read_raster(path: Path) -> np.ndarray:
    try:
        from osgeo import gdal  # type: ignore[import-not-found]

        dataset = gdal.Open(str(path), gdal.GA_ReadOnly)
        if dataset is None:
            raise CubLoaderError(f"GDAL could not open converted raster {path}")
        array = dataset.ReadAsArray()
        if array is None:
            raise CubLoaderError(f"GDAL returned no pixels for {path}")
        return np.asarray(array)
    except ImportError:
        try:
            from PIL import Image
        except ImportError as exc:
            raise CubLoaderError(
                "Reading converted rasters requires osgeo.gdal or Pillow"
            ) from exc
        # Lunar pushbroom products can legitimately exceed Pillow's safety limit.
        Image.MAX_IMAGE_PIXELS = None
        with Image.open(path) as image:
            return np.asarray(image)


def extract_cub_array(cub_path: str | os.PathLike[str]) -> np.ndarray:
    """Convert an ISIS cube to a temporary TIFF and return its pixel array."""

    path = Path(cub_path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"CUB file does not exist: {path}")
    converter, _ = _find_tool("cube2tiff", "gdal_translate")
    if converter is None:
        raise CubLoaderError(
            "No cube converter found. Activate the ISIS environment or install "
            "GDAL, then make cube2tiff or gdal_translate available on PATH."
        )
    with tempfile.TemporaryDirectory(prefix="lunareg-cub-") as directory:
        output = Path(directory) / "cube.tif"
        if Path(converter).name == "cube2tiff":
            command = [converter, str(path), str(output)]
        else:
            command = [converter, "-of", "GTiff", str(path), str(output)]
        _run(command)
        return np.asarray(_read_raster(output))


def load_cub_with_isis(cub_path: str | os.PathLike[str]) -> CubProduct:
    """Load a cube and return its image plus dimensions/geospatial metadata."""

    path = Path(cub_path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"CUB file does not exist: {path}")
    metadata: CubMetadata = {}
    info_tool, _ = _find_tool("gdalinfo")
    if info_tool:
        metadata.update(_parse_gdalinfo(_run([info_tool, str(path)])))
    image = extract_cub_array(path)
    if "dimensions" not in metadata:
        metadata["dimensions"] = (int(image.shape[-1]), int(image.shape[-2]))
    metadata["conversion_tool"] = "cube2tiff or gdal_translate"
    _read_label_metadata(path, metadata)
    return {"image": np.asarray(image), "metadata": metadata}
