import pathlib
import sys

import cv2
import numpy as np
import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from lunar_isis_gui.matching import FeatureMatches, match_features, select_uniform_matches


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


def test_loftr_missing_dependency_falls_back_to_sift(monkeypatch):
    source = _pattern()
    reference = source.copy()

    def unavailable(*args, **kwargs):
        raise ImportError("No module named 'torch'")

    monkeypatch.setattr("lunar_isis_gui.matching._loftr_matches", unavailable)

    matches = match_features(source, reference, method="loftr")

    assert matches["method"] == "sift"
    assert "LoFTR is unavailable" in matches["warning"]


def test_uniform_selection_keeps_highest_confidence_per_grid_cell():
    matches: FeatureMatches = {
        "source_points": np.array([[5, 5], [6, 6], [75, 5], [5, 75]], dtype=np.float32),
        "reference_points": np.array([[1, 1], [2, 2], [3, 3], [4, 4]], dtype=np.float32),
        "confidence": np.array([0.4, 0.9, 0.8, 0.7], dtype=np.float32),
        "method": "sift",
    }

    selected = select_uniform_matches(matches, (80, 80), grid_shape=(2, 2))

    np.testing.assert_allclose(selected["source_points"], [[6, 6], [75, 5], [5, 75]])
    np.testing.assert_allclose(selected["confidence"], [0.9, 0.8, 0.7])


def test_uniform_selection_preserves_empty_match_contract():
    matches: FeatureMatches = {
        "source_points": np.empty((0, 2), dtype=np.float32),
        "reference_points": np.empty((0, 2), dtype=np.float32),
        "confidence": np.empty((0,), dtype=np.float32),
        "method": "sift",
    }

    selected = select_uniform_matches(matches, (20, 20))

    assert selected["source_points"].shape == (0, 2)
    assert selected["reference_points"].shape == (0, 2)


def test_uniform_selection_rejects_misaligned_confidence():
    matches: FeatureMatches = {
        "source_points": np.zeros((2, 2), dtype=np.float32),
        "reference_points": np.zeros((2, 2), dtype=np.float32),
        "confidence": np.zeros((1,), dtype=np.float32),
        "method": "sift",
    }

    with pytest.raises(ValueError, match="one value per point"):
        select_uniform_matches(matches, (20, 20))


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
