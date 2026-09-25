"""Persist registration products and diagnostics."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Mapping

import cv2
import numpy as np


def write_image(path: Path, image: np.ndarray) -> None:
    """Write an intermediate image and raise an explicit error on failure."""

    if not cv2.imwrite(str(path), np.asarray(image)):
        raise OSError(f"could not write image: {path}")


def write_intermediates(
    output_dir: Path,
    *,
    source: np.ndarray,
    projected_reference: np.ndarray,
    overlap_source: np.ndarray,
    overlap_reference: np.ndarray,
) -> dict[str, str]:
    """Write visual checkpoints for the load, projection, and overlap stages."""

    output_dir.mkdir(parents=True, exist_ok=True)
    images = {
        "source": output_dir / "01_source.tif",
        "projected_reference": output_dir / "02_projected_reference.tif",
        "overlap_source": output_dir / "03_overlap_source.tif",
        "overlap_reference": output_dir / "03_overlap_reference.tif",
    }
    for name, image in (
        ("source", source),
        ("projected_reference", projected_reference),
        ("overlap_source", overlap_source),
        ("overlap_reference", overlap_reference),
    ):
        write_image(images[name], image)
    return {name: str(path) for name, path in images.items()}


def write_matches(
    path: Path,
    source_points: np.ndarray,
    reference_points: np.ndarray,
    confidence: np.ndarray,
    inlier_mask: np.ndarray,
) -> None:
    """Write matched coordinates and inlier flags as CSV."""

    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(("source_x", "source_y", "reference_x", "reference_y", "confidence", "inlier"))
        writer.writerows(
            (
                float(source_points[index, 0]),
                float(source_points[index, 1]),
                float(reference_points[index, 0]),
                float(reference_points[index, 1]),
                float(confidence[index]),
                bool(inlier_mask[index]),
            )
            for index in range(source_points.shape[0])
        )


def write_registration_outputs(
    output_dir: Path,
    registered: np.ndarray,
    source_points: np.ndarray,
    reference_points: np.ndarray,
    confidence: np.ndarray,
    inlier_mask: np.ndarray,
    result: Mapping[str, object],
) -> dict[str, str]:
    """Write the registered raster, matches, and JSON metrics."""

    output_dir.mkdir(parents=True, exist_ok=True)
    registered_path = output_dir / "registered.tif"
    if not cv2.imwrite(str(registered_path), np.asarray(registered)):
        raise OSError(f"could not write registered raster: {registered_path}")
    matches_path = output_dir / "matches.csv"
    write_matches(matches_path, source_points, reference_points, confidence, inlier_mask)
    metrics_path = output_dir / "metrics.json"
    with metrics_path.open("w", encoding="utf-8") as handle:
        json.dump(dict(result), handle, indent=2)
        handle.write("\n")
    return {
        "registered": str(registered_path),
        "matches": str(matches_path),
        "metrics": str(metrics_path),
    }
