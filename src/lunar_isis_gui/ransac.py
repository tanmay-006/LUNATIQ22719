"""Robust affine transform estimation for matched image points."""

from __future__ import annotations

from typing import TypedDict

import cv2
import numpy as np


class TransformFit(TypedDict):
    transform: np.ndarray
    inlier_mask: np.ndarray
    residuals: np.ndarray
    inlier_count: int
    inlier_ratio: float


def fit_transform(
    source_points: np.ndarray,
    reference_points: np.ndarray,
    *,
    threshold: float = 3.0,
    confidence: float = 0.99,
    max_iterations: int = 2000,
) -> TransformFit:
    """Estimate a partial affine transform mapping source points to reference points."""

    source = np.asarray(source_points, dtype=np.float32)
    reference = np.asarray(reference_points, dtype=np.float32)
    if source.shape != reference.shape or source.ndim != 2 or source.shape[1] != 2:
        raise ValueError("source_points and reference_points must both have shape (N, 2)")
    if source.shape[0] < 3:
        raise ValueError("at least three point pairs are required")
    if threshold <= 0 or not 0 < confidence < 1 or max_iterations < 1:
        raise ValueError("threshold must be positive, confidence must be in (0, 1), and max_iterations must be positive")

    transform, mask = cv2.estimateAffinePartial2D(
        source,
        reference,
        method=cv2.RANSAC,
        ransacReprojThreshold=threshold,
        maxIters=max_iterations,
        confidence=confidence,
        refineIters=10,
    )
    if transform is None or mask is None:
        raise ValueError("RANSAC could not estimate a valid affine transform")

    predicted = cv2.transform(source.reshape(-1, 1, 2), transform).reshape(-1, 2)
    residuals = np.linalg.norm(predicted - reference, axis=1)
    inlier_mask = mask.reshape(-1).astype(bool)
    return {
        "transform": np.asarray(transform, dtype=np.float32),
        "inlier_mask": inlier_mask,
        "residuals": residuals.astype(np.float32),
        "inlier_count": int(inlier_mask.sum()),
        "inlier_ratio": float(inlier_mask.mean()),
    }
