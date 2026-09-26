"""Project a reference cube into the source image grid."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import TypedDict

import cv2
import numpy as np

from .cub_loader import CubLoaderError, CubMetadata, extract_cub_array, load_cub_with_isis


class ProjectedReference(TypedDict):
    image: np.ndarray
    metadata: CubMetadata
    method: str
    projection_error: str | None


def _tool(name: str) -> str | None:
    for directory in (
        os.environ.get("ISISROOT"),
        os.environ.get("CONDA_PREFIX"),
        str(Path(__import__("sys").executable).resolve().parent),
    ):
        if directory:
            candidate = Path(directory) / "bin" / name
            if candidate.is_file() and os.access(candidate, os.X_OK):
                return str(candidate)
    return shutil.which(name)


def _normalise(image: np.ndarray) -> np.ndarray:
    array = np.asarray(image, dtype=np.float32)
    finite = np.isfinite(array)
    if not finite.any():
        return np.zeros(array.shape, dtype=np.float32)
    low, high = np.percentile(array[finite], (2, 98))
    if high <= low:
        return np.zeros(array.shape, dtype=np.float32)
    return np.clip((array - low) / (high - low), 0, 1)


def _affine_fallback(source: np.ndarray, reference: np.ndarray) -> np.ndarray:
    """Resize and phase-align the reference when map projection is unavailable."""

    source_shape = source.shape[-2:]
    resized = cv2.resize(
        _normalise(reference),
        (source_shape[1], source_shape[0]),
        interpolation=cv2.INTER_AREA,
    )
    source_small = cv2.resize(_normalise(source), (min(1024, source_shape[1]), min(1024, source_shape[0])))
    reference_small = cv2.resize(resized, (source_small.shape[1], source_small.shape[0]))
    shift, _ = cv2.phaseCorrelate(source_small, reference_small)
    matrix = np.float32([[1, 0, shift[0]], [0, 1, shift[1]]])
    return cv2.warpAffine(
        np.asarray(reference, dtype=np.float32),
        matrix,
        (source_shape[1], source_shape[0]),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=0,
    )


def _try_cam2map(
    source_cub: Path, ref_cub: Path, source_shape: tuple[int, int]
) -> tuple[np.ndarray | None, str | None]:
    """Try ISIS cam2map and retain its diagnostic when camera setup fails."""

    cam2map = _tool("cam2map")
    if cam2map is None:
        return None, "cam2map was not found in the active ISIS environment"
    with tempfile.TemporaryDirectory(prefix="lunareg-map-") as directory:
        output = Path(directory) / "projected.cub"
        try:
            completed = subprocess.run(
                [
                    cam2map,
                    f"from={ref_cub}",
                    f"to={output}",
                    f"map={Path(os.environ.get('ISISROOT', '')) / 'appdata/templates/maps/sinusoidal.map'}",
                    "-NOGUI",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            projected = extract_cub_array(output)
        except subprocess.CalledProcessError as error:
            detail = (error.stdout or error.stderr or "").strip().replace("\n", " ")
            return None, detail[-500:] or f"cam2map exited with status {error.returncode}"
        except (OSError, CubLoaderError) as error:
            return None, str(error)
    return (
        cv2.resize(projected, (source_shape[1], source_shape[0]), interpolation=cv2.INTER_LINEAR),
        None,
    )


def project_reference_via_isis(
    source_cub: str | os.PathLike[str],
    ref_cub: str | os.PathLike[str],
    *,
    use_cam2map: bool = True,
    max_dimension: int | None = None,
) -> ProjectedReference:
    """Return a reference image on the source grid, using ISIS or affine fallback."""

    source = load_cub_with_isis(source_cub, max_dimension=max_dimension)
    reference = load_cub_with_isis(ref_cub, max_dimension=max_dimension)
    source_shape = source["image"].shape[-2:]
    projection_error = None
    if use_cam2map:
        projected, projection_error = _try_cam2map(
            Path(source_cub), Path(ref_cub), source_shape
        )
    else:
        projected = None
    method = "cam2map" if projected is not None else "affine-fallback"
    if projected is None:
        projected = _affine_fallback(source["image"], reference["image"])
    metadata = dict(reference["metadata"])
    metadata["dimensions"] = (source_shape[1], source_shape[0])
    # The projected image is resampled onto the source's pixel grid, so its
    # geotransform/pixel scale must come from the source, not the reference.
    source_metadata = source["metadata"]
    if "geotransform" in source_metadata:
        metadata["geotransform"] = source_metadata["geotransform"]
    else:
        metadata.pop("geotransform", None)
    if "gsd" in source_metadata:
        metadata["gsd"] = source_metadata["gsd"]
    else:
        metadata.pop("gsd", None)
    return {
        "image": np.asarray(projected),
        "metadata": metadata,
        "method": method,
        "projection_error": projection_error,
    }
