import pathlib
import sys

import cv2
import numpy as np
import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from lunar_isis_gui.matching import match_features


def _pattern() -> np.ndarray:
    image = np.zeros((240, 320), dtype=np.uint8)
    for x, y in [(30, 30), (90, 45), (160, 80), (250, 40), (70, 170), (210, 180)]:
        cv2.circle(image, (x, y), 12, 255, -1)
        cv2.line(image, (x - 18, y + 20), (x + 18, y - 20), 180, 3)
    return image


def test_sift_returns_aligned_point_arrays():
    source = _pattern()
    reference = cv2.warpAffine(source, np.float32([[1, 0, 8], [0, 1, 5]]), (320, 240))
    matches = match_features(source, reference, method="sift")
    assert matches["method"] == "sift"
    assert matches["source_points"].shape[1] == 2
    assert matches["source_points"].shape == matches["reference_points"].shape
    assert matches["confidence"].shape == (matches["source_points"].shape[0],)
    assert matches["source_points"].shape[0] >= 4


def test_invalid_matching_inputs_are_rejected():
    with pytest.raises(ValueError, match="two-dimensional"):
        match_features(np.zeros((2, 2, 1)), np.zeros((2, 2)), method="sift")
    with pytest.raises(ValueError, match="method"):
        match_features(np.zeros((2, 2)), np.zeros((2, 2)), method="invalid")


def test_sift_deduplicates_reference_keypoints(monkeypatch):
    source = np.full((32, 32), 128, dtype=np.uint8)
    reference = source.copy()

    class FakeDetector:
        def detectAndCompute(self, image, mask):
            keypoints = [cv2.KeyPoint(float(i), float(i), 1) for i in range(4)]
            return keypoints, np.ones((4, 4), dtype=np.float32)

    class FakeMatcher:
        def knnMatch(self, source_descriptors, reference_descriptors, k):
            return [
                [cv2.DMatch(0, 0, 0.1), cv2.DMatch(0, 1, 1.0)],
                [cv2.DMatch(1, 0, 0.2), cv2.DMatch(1, 2, 1.0)],
            ]

    monkeypatch.setattr(cv2, "SIFT_create", lambda: FakeDetector())
    monkeypatch.setattr(cv2, "BFMatcher", lambda norm: FakeMatcher())

    matches = match_features(source, reference, method="sift")

    assert matches["source_points"].shape == (1, 2)
    assert matches["reference_points"].shape == (1, 2)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
