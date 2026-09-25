"""Diagnostic plots for registration results."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def plot_stage_pair(
    left: np.ndarray,
    right: np.ndarray,
    output_path: Path,
    *,
    title: str,
    left_title: str = "Source",
    right_title: str = "Reference",
) -> None:
    """Save a stage preview that keeps both images visible for comparison."""

    figure, axes = plt.subplots(1, 2, figsize=(14, 6), constrained_layout=True)
    for axis, image, image_title in zip(axes, (left, right), (left_title, right_title)):
        axis.imshow(image, cmap="gray")
        axis.set_title(image_title)
        axis.axis("off")
    figure.suptitle(title)
    figure.savefig(output_path, dpi=150)
    plt.close(figure)


def plot_4panel(
    source: np.ndarray,
    reference: np.ndarray,
    registered: np.ndarray,
    source_points: np.ndarray,
    reference_points: np.ndarray,
    output_path: Path,
) -> None:
    """Save source, reference, registered, and correspondence diagnostics."""

    figure, axes = plt.subplots(2, 2, figsize=(12, 8), constrained_layout=True)
    panels = (
        (source, "Source"),
        (reference, "Reference"),
        (registered, "Registered"),
    )
    for axis, (image, title) in zip(axes.flat, panels):
        axis.imshow(image, cmap="gray")
        axis.set_title(title)
        axis.axis("off")
    axes[1, 1].imshow(source, cmap="gray")
    if source_points.size:
        axes[1, 1].scatter(source_points[:, 0], source_points[:, 1], s=5, c="lime", label="source")
        axes[1, 1].scatter(reference_points[:, 0], reference_points[:, 1], s=5, c="red", label="reference")
        axes[1, 1].legend(loc="upper right", fontsize="small")
    axes[1, 1].set_title("Matched points")
    axes[1, 1].axis("off")
    figure.savefig(output_path, dpi=150)
    plt.close(figure)


def plot_matches(
    source: np.ndarray,
    reference: np.ndarray,
    source_points: np.ndarray,
    reference_points: np.ndarray,
    output_path: Path,
) -> None:
    """Save a side-by-side view of every accepted feature correspondence."""

    figure, axes = plt.subplots(1, 2, figsize=(14, 6), constrained_layout=True)
    axes[0].imshow(source, cmap="gray")
    axes[1].imshow(reference, cmap="gray")
    axes[0].set_title(f"Source ({len(source_points)} matches)")
    axes[1].set_title("Reference")
    for axis in axes:
        axis.axis("off")
    if source_points.size:
        for source_point, reference_point in zip(source_points, reference_points):
            axes[0].plot(source_point[0], source_point[1], "o", color="lime", markersize=4)
            axes[1].plot(reference_point[0], reference_point[1], "o", color="red", markersize=4)
    figure.savefig(output_path, dpi=150)
    plt.close(figure)


def plot_ransac(
    source: np.ndarray,
    reference: np.ndarray,
    source_points: np.ndarray,
    reference_points: np.ndarray,
    inlier_mask: np.ndarray,
    output_path: Path,
) -> None:
    """Save the RANSAC mapping with both images and correspondence lines."""

    figure, axes = plt.subplots(1, 2, figsize=(14, 6), constrained_layout=True)
    axes[0].imshow(source, cmap="gray")
    axes[1].imshow(reference, cmap="gray")
    if source_points.size:
        mask = np.asarray(inlier_mask, dtype=bool)
        axes[0].scatter(source_points[~mask, 0], source_points[~mask, 1], c="red", s=18, label="outlier")
        axes[0].scatter(source_points[mask, 0], source_points[mask, 1], c="lime", s=22, label="inlier")
        axes[1].scatter(reference_points[~mask, 0], reference_points[~mask, 1], c="red", s=18)
        axes[1].scatter(reference_points[mask, 0], reference_points[mask, 1], c="lime", s=22)
        axes[0].legend(loc="upper right")
    axes[0].set_title("Source: RANSAC decision")
    axes[1].set_title("Reference: mapped points")
    for axis in axes:
        axis.axis("off")
    figure.suptitle("RANSAC inliers and outliers")
    figure.savefig(output_path, dpi=150)
    plt.close(figure)
