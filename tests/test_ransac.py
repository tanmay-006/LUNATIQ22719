import pathlib
import sys

import numpy as np
import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from lunar_isis_gui.ransac import fit_transform


def test_fit_transform_rejects_outliers():
    source = np.array(
        [[0, 0], [20, 0], [0, 20], [20, 20], [40, 10], [10, 40], [80, 80]],
        dtype=np.float32,
    )
    reference = source + np.array([8, -4], dtype=np.float32)
    reference[-1] = [300, -200]
    result = fit_transform(source, reference)
    assert result["transform"].shape == (2, 3)
    assert result["inlier_count"] >= 6
    assert result["inlier_ratio"] >= 6 / 7
    assert result["residuals"].shape == (7,)
    assert result["residuals"][-1] > 100


def test_fit_transform_requires_matching_point_pairs():
    with pytest.raises(ValueError, match="shape"):
        fit_transform(np.zeros((3, 2)), np.zeros((4, 2)))
    with pytest.raises(ValueError, match="three"):
        fit_transform(np.zeros((2, 2)), np.zeros((2, 2)))


def test_fit_transform_rejects_degenerate_matches():
    points = np.zeros((3, 2), dtype=np.float32)
    with pytest.raises(ValueError, match="valid affine"):
        fit_transform(points, points)
