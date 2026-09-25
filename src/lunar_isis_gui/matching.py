"""Feature matching for projected lunar image pairs."""

from __future__ import annotations

from typing import NotRequired, TypedDict

import cv2
import numpy as np


class FeatureMatches(TypedDict):
    source_points: np.ndarray
    reference_points: np.ndarray
    confidence: np.ndarray
    method: str
    warning: NotRequired[str]


def _normalise(image: np.ndarray) -> np.ndarray:
    array = np.asarray(image, dtype=np.float32)
    finite = np.isfinite(array)
    if not finite.any():
        return np.zeros(array.shape, dtype=np.uint8)
    low, high = np.percentile(array[finite], (2, 98))
    if high <= low:
        return np.zeros(array.shape, dtype=np.uint8)
    return np.clip((array - low) * 255.0 / (high - low), 0, 255).astype(np.uint8)


def _sift_matches(source: np.ndarray, reference: np.ndarray, ratio: float) -> FeatureMatches:
    detector = cv2.SIFT_create()
    source_keypoints, source_descriptors = detector.detectAndCompute(_normalise(source), None)
    reference_keypoints, reference_descriptors = detector.detectAndCompute(_normalise(reference), None)
    if source_descriptors is None or reference_descriptors is None:
        return {
            "source_points": np.empty((0, 2), dtype=np.float32),
            "reference_points": np.empty((0, 2), dtype=np.float32),
            "confidence": np.empty((0,), dtype=np.float32),
            "method": "sift",
        }
    matcher = cv2.BFMatcher(cv2.NORM_L2)
    pairs = matcher.knnMatch(source_descriptors, reference_descriptors, k=2)
    good = [pair for pair in pairs if len(pair) == 2 and pair[0].distance < ratio * pair[1].distance]
    # Repetitive or saturated regions can produce several query matches to the
    # same target keypoint. Keep only the strongest match per target location.
    unique_good: dict[int, tuple[cv2.DMatch, cv2.DMatch]] = {}
    for pair in good:
        match = pair[0]
        previous = unique_good.get(match.trainIdx)
        if previous is None or match.distance < previous[0].distance:
            unique_good[match.trainIdx] = (match, pair[1])
    good = sorted(unique_good.values(), key=lambda pair: pair[0].distance)
    source_points = np.asarray([pair[0].queryIdx for pair in good], dtype=np.int32)
    reference_points = np.asarray([pair[0].trainIdx for pair in good], dtype=np.int32)
    source_points = np.asarray([source_keypoints[index].pt for index in source_points], dtype=np.float32)
    reference_points = np.asarray([reference_keypoints[index].pt for index in reference_points], dtype=np.float32)
    confidence = np.asarray(
        [1.0 - (match.distance / max(second.distance, 1e-6)) for match, second in good],
        dtype=np.float32,
    )
    return {
        "source_points": source_points.reshape((-1, 2)),
        "reference_points": reference_points.reshape((-1, 2)),
        "confidence": confidence,
        "method": "sift",
    }


def _loftr_matches(source: np.ndarray, reference: np.ndarray, threshold: float) -> FeatureMatches:
    import torch
    from kornia.feature import LoFTR

    matcher = LoFTR(pretrained="outdoor")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    matcher = matcher.to(device).eval()
    source_tensor = torch.from_numpy(_normalise(source)).float().div(255).unsqueeze(0).unsqueeze(0).to(device)
    reference_tensor = torch.from_numpy(_normalise(reference)).float().div(255).unsqueeze(0).unsqueeze(0).to(device)
    with torch.inference_mode():
        output = matcher({"image0": source_tensor, "image1": reference_tensor})
    confidence = output["confidence"].detach().cpu().numpy()
    keep = confidence >= threshold
    return {
        "source_points": output["keypoints0"].detach().cpu().numpy()[keep].astype(np.float32),
        "reference_points": output["keypoints1"].detach().cpu().numpy()[keep].astype(np.float32),
        "confidence": confidence[keep].astype(np.float32),
        "method": "loftr",
    }


def match_features(
    source: np.ndarray,
    reference: np.ndarray,
    *,
    method: str = "auto",
    confidence_threshold: float = 0.5,
    ratio_threshold: float = 0.7,
) -> FeatureMatches:
    """Match source/reference features, preferring LoFTR and falling back to SIFT."""

    if np.asarray(source).ndim != 2 or np.asarray(reference).ndim != 2:
        raise ValueError("match_features expects two-dimensional image arrays")
    if np.asarray(source).size == 0 or np.asarray(reference).size == 0:
        raise ValueError("match_features expects non-empty image arrays")
    if method not in {"auto", "loftr", "sift"}:
        raise ValueError("method must be one of: auto, loftr, sift")
    if method in {"auto", "loftr"}:
        try:
            matches = _loftr_matches(source, reference, confidence_threshold)
            if matches["source_points"].shape[0] > 0 or method == "loftr":
                return matches
        except (ImportError, RuntimeError, OSError) as error:
            sift_matches = _sift_matches(source, reference, ratio_threshold)
            sift_matches["warning"] = (
                "LoFTR is unavailable; used SIFT instead. "
                f"Reason: {error}"
            )
            return sift_matches
    return _sift_matches(source, reference, ratio_threshold)
