"""Accuracy and coverage metrics for image registration results."""

from __future__ import annotations

from typing import TypedDict

import cv2
import numpy as np


class ValidationMetrics(TypedDict, total=False):
    """Metrics reported for a fitted registration transform."""

    rmse: float
    median_error: float
    ce90: float
    inlier_count: int
    inlier_ratio: float
    coverage_percentage: float
    checkpoint_rmse: float
    checkpoint_median_error: float


def _points(value: np.ndarray, name: str) -> np.ndarray:
    points = np.asarray(value, dtype=np.float32)
    if points.ndim != 2 or points.shape[1] != 2:
        raise ValueError(f"{name} must have shape (N, 2)")
    if points.shape[0] == 0:
        raise ValueError(f"{name} must not be empty")
    if not np.isfinite(points).all():
        raise ValueError(f"{name} must contain only finite values")
    return points


def _errors(
    source: np.ndarray,
    reference: np.ndarray,
    transform: np.ndarray | None,
) -> np.ndarray:
    if transform is None:
        return np.linalg.norm(source - reference, axis=1)
    matrix = np.asarray(transform, dtype=np.float32)
    if matrix.shape != (2, 3):
        raise ValueError("transform must have shape (2, 3)")
    predicted = cv2.transform(source.reshape(-1, 1, 2), matrix).reshape(-1, 2)
    return np.linalg.norm(predicted - reference, axis=1)


def measure_accuracy(
    source_points: np.ndarray,
    reference_points: np.ndarray,
    *,
    inlier_mask: np.ndarray | None = None,
    transform: np.ndarray | None = None,
    checkpoints: tuple[np.ndarray, np.ndarray] | None = None,
    image_shape: tuple[int, int] | None = None,
) -> ValidationMetrics:
    """Calculate registration accuracy, inlier statistics, and spatial coverage.

    ``source_points`` and ``reference_points`` are corresponding match points.
    If ``transform`` is supplied, errors are calculated after transforming source
    points; otherwise the points are compared directly. ``checkpoints`` may hold
    an independent ``(source, reference)`` point pair for hold-out validation.
    """

    source = _points(source_points, "source_points")
    reference = _points(reference_points, "reference_points")
    if source.shape != reference.shape:
        raise ValueError("source_points and reference_points must have the same shape")

    if inlier_mask is None:
        mask = np.ones(source.shape[0], dtype=bool)
    else:
        mask = np.asarray(inlier_mask, dtype=bool).reshape(-1)
        if mask.shape[0] != source.shape[0]:
            raise ValueError("inlier_mask must contain one value per point pair")
    if not mask.any():
        raise ValueError("at least one inlier is required")

    errors = _errors(source, reference, transform)
    inlier_errors = errors[mask]
    metrics: ValidationMetrics = {
        "rmse": float(np.sqrt(np.mean(inlier_errors**2))),
        "median_error": float(np.median(inlier_errors)),
        "ce90": float(np.percentile(inlier_errors, 90)),
        "inlier_count": int(mask.sum()),
        "inlier_ratio": float(mask.mean()),
    }

    if image_shape is not None:
        height, width = image_shape
        if height <= 0 or width <= 0:
            raise ValueError("image_shape dimensions must be positive")
        inlier_points = source[mask]
        occupied_x = np.unique(np.clip(np.floor(inlier_points[:, 0]).astype(int), 0, width - 1))
        occupied_y = np.unique(np.clip(np.floor(inlier_points[:, 1]).astype(int), 0, height - 1))
        metrics["coverage_percentage"] = float(
            100.0 * len(occupied_x) * len(occupied_y) / (width * height)
        )
    else:
        metrics["coverage_percentage"] = 0.0

    if checkpoints is not None:
        checkpoint_source = _points(checkpoints[0], "checkpoint source points")
        checkpoint_reference = _points(checkpoints[1], "checkpoint reference points")
        if checkpoint_source.shape != checkpoint_reference.shape:
            raise ValueError("checkpoint point arrays must have the same shape")
        checkpoint_errors = _errors(checkpoint_source, checkpoint_reference, transform)
        metrics["checkpoint_rmse"] = float(np.sqrt(np.mean(checkpoint_errors**2)))
        metrics["checkpoint_median_error"] = float(np.median(checkpoint_errors))

    return metrics
