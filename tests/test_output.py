from __future__ import annotations

import csv
import json

import cv2
import numpy as np

from lunar_isis_gui.output import write_intermediates, write_registration_outputs
from lunar_isis_gui.plotting import plot_4panel


def test_writes_registration_outputs(tmp_path):
    points = np.array([[1, 1], [2, 2], [3, 3]], dtype=np.float32)
    paths = write_registration_outputs(
        tmp_path,
        np.zeros((8, 8), dtype=np.uint8),
        points,
        points,
        np.ones(3, dtype=np.float32),
        np.array([True, False, True]),
        {"metrics": {"inlier_count": 2}},
    )

    assert cv2.imread(paths["registered"], cv2.IMREAD_UNCHANGED).shape == (8, 8)
    with open(paths["matches"], newline="", encoding="utf-8") as handle:
        assert len(list(csv.reader(handle))) == 4
    assert json.loads(open(paths["metrics"], encoding="utf-8").read())["metrics"]["inlier_count"] == 2


def test_writes_diagnostic_plot(tmp_path):
    image = np.zeros((16, 16), dtype=np.uint8)
    points = np.array([[1, 1], [8, 8]], dtype=np.float32)
    path = tmp_path / "diagnostic.png"

    plot_4panel(image, image, image, points, points, path)

    assert path.is_file()
    assert path.stat().st_size > 0


def test_writes_intermediate_images(tmp_path):
    image = np.zeros((8, 8), dtype=np.uint8)
    outputs = write_intermediates(
        tmp_path,
        source=image,
        projected_reference=image,
        overlap_source=image,
        overlap_reference=image,
    )

    assert set(outputs) == {"source", "projected_reference", "overlap_source", "overlap_reference"}
    assert all((tmp_path / path.split("/")[-1]).is_file() for path in outputs.values())
