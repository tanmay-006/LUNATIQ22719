import pathlib
import sys

import numpy as np
import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from lunar_isis_gui.validation import measure_accuracy


def test_measure_accuracy_reports_transform_errors_and_coverage():
    source = np.array([[0, 0], [10, 0], [0, 10], [10, 10]], dtype=np.float32)
    reference = source + np.array([2, -1], dtype=np.float32)
    result = measure_accuracy(
        source,
        reference,
        transform=np.array([[1, 0, 2], [0, 1, -1]], dtype=np.float32),
        image_shape=(20, 20),
    )
    assert result["rmse"] == pytest.approx(0)
    assert result["median_error"] == pytest.approx(0)
    assert result["ce90"] == pytest.approx(0)
    assert result["inlier_count"] == 4
    assert result["inlier_ratio"] == pytest.approx(1)
    assert result["coverage_percentage"] == pytest.approx(1)


def test_measure_accuracy_excludes_outlier_and_validates_checkpoints():
    source = np.array([[0, 0], [10, 0], [0, 10], [10, 10]], dtype=np.float32)
    reference = source + np.array([2, -1], dtype=np.float32)
    reference[-1] += [20, 20]
    result = measure_accuracy(
        source,
        reference,
        inlier_mask=np.array([True, True, True, False]),
        checkpoints=(np.array([[5, 5]], dtype=np.float32), np.array([[7, 4]], dtype=np.float32)),
        transform=np.array([[1, 0, 2], [0, 1, -1]], dtype=np.float32),
    )
    assert result["inlier_count"] == 3
    assert result["inlier_ratio"] == pytest.approx(0.75)
    assert result["rmse"] == pytest.approx(0)
    assert result["checkpoint_rmse"] == pytest.approx(0)


def test_measure_accuracy_rejects_invalid_inputs():
    with pytest.raises(ValueError, match="shape"):
        measure_accuracy(np.zeros((3, 2)), np.zeros((3, 3)))
    with pytest.raises(ValueError, match="one value"):
        measure_accuracy(np.zeros((3, 2)), np.zeros((3, 2)), inlier_mask=[True, False])
    with pytest.raises(ValueError, match="at least one"):
        measure_accuracy(
            np.zeros((3, 2)),
            np.zeros((3, 2)),
            inlier_mask=[False, False, False],
        )
