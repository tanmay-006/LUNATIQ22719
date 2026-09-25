"""Diagnostic plots for registration results."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


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
