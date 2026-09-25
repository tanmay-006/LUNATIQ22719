"""Command-line orchestration for lunar image registration."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Sequence

import cv2
import numpy as np

from .cub_loader import load_cub_with_isis
from .footprint import crop_to_overlap
from .matching import match_features
from .projection import project_reference_via_isis
from .ransac import fit_transform
from .validation import measure_accuracy


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Register a source ISIS cube against a reference ISIS cube."
    )
    parser.add_argument("source", type=Path, help="source .cub path")
    parser.add_argument("reference", type=Path, help="reference .cub path")
    parser.add_argument("output", type=Path, help="directory for registration outputs")
    parser.add_argument(
        "--method",
        choices=("auto", "sift", "loftr"),
        default="sift",
        help="feature matcher (default: sift; auto tries LoFTR first)",
    )
    parser.add_argument(
        "--ratio",
        type=float,
        default=0.7,
        help="SIFT Lowe ratio threshold (default: 0.7)",
    )
    parser.add_argument(
        "--ransac-threshold",
        type=float,
        default=3.0,
        help="RANSAC reprojection threshold in pixels (default: 3.0)",
    )
    parser.add_argument(
        "--projection-method",
        choices=("auto", "fallback"),
        default="fallback",
        help="projection strategy (default: fallback to avoid long cam2map runs)",
    )
    parser.add_argument(
        "--max-dimension",
        type=int,
        default=1024,
        help="resize overlap to this maximum side length before matching (default: 1024)",
    )
    return parser


def _write_matches(path: Path, source: np.ndarray, reference: np.ndarray, confidence: np.ndarray, mask: np.ndarray) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(("source_x", "source_y", "reference_x", "reference_y", "confidence", "inlier"))
        writer.writerows(
            (
                float(source[index, 0]),
                float(source[index, 1]),
                float(reference[index, 0]),
                float(reference[index, 1]),
                float(confidence[index]),
                bool(mask[index]),
            )
            for index in range(source.shape[0])
        )


def _resize_pair(source: np.ndarray, reference: np.ndarray, max_dimension: int) -> tuple[np.ndarray, np.ndarray, float]:
    if max_dimension <= 0:
        raise ValueError("max_dimension must be positive")
    longest = max(source.shape[0], source.shape[1], reference.shape[0], reference.shape[1])
    scale = min(1.0, max_dimension / float(longest))
    if scale >= 1.0:
        return source, reference, 1.0
    size = (
        max(1, int(round(source.shape[1] * scale))),
        max(1, int(round(source.shape[0] * scale))),
    )
    return (
        cv2.resize(source, size, interpolation=cv2.INTER_AREA),
        cv2.resize(reference, size, interpolation=cv2.INTER_AREA),
        scale,
    )


def register(
    source_path: Path,
    reference_path: Path,
    output_dir: Path,
    *,
    method: str,
    ratio: float,
    ransac_threshold: float,
    projection_method: str,
    max_dimension: int,
) -> dict[str, object]:
    """Run registration and write the registered raster, matches, and metrics."""

    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"[1/6] Loading source cube: {source_path}", flush=True)
    source = load_cub_with_isis(source_path, max_dimension=max_dimension)
    print(f"[2/6] Projecting reference cube: {reference_path}", flush=True)
    projected = project_reference_via_isis(
        source_path,
        reference_path,
        use_cam2map=projection_method == "auto",
        max_dimension=max_dimension,
    )
    print(f"      projection method: {projected['method']}", flush=True)
    print("[3/6] Cropping to shared footprint", flush=True)
    overlap = crop_to_overlap(
        source["image"],
        projected["image"],
        source["metadata"],
        projected["metadata"],
    )
    source_overlap, reference_overlap, scale = _resize_pair(
        overlap["source"],
        overlap["reference"],
        max_dimension,
    )
    if scale < 1.0:
        print(
            f"      overlap: {overlap['source'].shape[1]} x {overlap['source'].shape[0]} -> "
            f"{source_overlap.shape[1]} x {source_overlap.shape[0]} (scale {scale:.3f})",
            flush=True,
        )
    else:
        print(f"      overlap: {overlap['source'].shape[1]} x {overlap['source'].shape[0]}", flush=True)
    print(f"[4/6] Matching features ({method})", flush=True)
    matches = match_features(
        source_overlap,
        reference_overlap,
        method=method,
        ratio_threshold=ratio,
    )
    count = matches["source_points"].shape[0]
    print(f"      matches: {count}", flush=True)
    if count < 3:
        raise ValueError(f"at least three matches are required; found {count}")
    print("[5/6] Fitting RANSAC transform", flush=True)
    fit = fit_transform(
        matches["source_points"],
        matches["reference_points"],
        threshold=ransac_threshold,
    )
    metrics = measure_accuracy(
        matches["source_points"],
        matches["reference_points"],
        inlier_mask=fit["inlier_mask"],
        transform=fit["transform"],
        image_shape=source_overlap.shape,
    )
    print("[6/6] Writing outputs", flush=True)
    matrix = np.vstack((fit["transform"], [0.0, 0.0, 1.0]))
    registered = cv2.warpAffine(
        source_overlap,
        fit["transform"],
        (reference_overlap.shape[1], reference_overlap.shape[0]),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=0,
    )
    registered_path = output_dir / "registered.tif"
    if not cv2.imwrite(str(registered_path), np.asarray(registered)):
        raise OSError(f"could not write registered raster: {registered_path}")
    _write_matches(
        output_dir / "matches.csv",
        matches["source_points"],
        matches["reference_points"],
        matches["confidence"],
        fit["inlier_mask"],
    )
    result = {
        "source": str(source_path.resolve()),
        "reference": str(reference_path.resolve()),
        "projection_method": projected["method"],
        "matching_method": matches["method"],
        "max_dimension": max_dimension,
        "resize_scale": scale,
        "transform": matrix.tolist(),
        "metrics": dict(metrics),
        "outputs": {
            "registered": str(registered_path),
            "matches": str(output_dir / "matches.csv"),
        },
    }
    with (output_dir / "metrics.json").open("w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2)
        handle.write("\n")
    print(f"Registered image: {registered_path}")
    print(f"Metrics: {output_dir / 'metrics.json'}")
    print(f"Inliers: {fit['inlier_count']}/{count} ({fit['inlier_ratio']:.2%})")
    print(f"RMSE: {metrics['rmse']:.4f} px")
    return result


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        register(
            args.source,
            args.reference,
            args.output,
            method=args.method,
            ratio=args.ratio,
            ransac_threshold=args.ransac_threshold,
            projection_method=args.projection_method,
            max_dimension=args.max_dimension,
        )
    except (FileNotFoundError, OSError, RuntimeError, ValueError) as error:
        print(f"Registration failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
