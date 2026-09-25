"""Find and crop the common footprint of two image arrays."""

from __future__ import annotations

from typing import TypedDict

import numpy as np

from .cub_loader import CubMetadata


class OverlapBounds(TypedDict):
    source: tuple[int, int, int, int]
    reference: tuple[int, int, int, int]


class OverlapResult(TypedDict):
    source: np.ndarray
    reference: np.ndarray
    bounds: OverlapBounds


def _extent(array: np.ndarray, metadata: CubMetadata) -> tuple[float, float, float, float]:
    height, width = array.shape[-2:]
    transform = metadata.get("geotransform")
    if not transform:
        return (0.0, 0.0, float(width), float(height))
    origin_x, pixel_x, _, origin_y, _, pixel_y = transform
    x2 = origin_x + width * pixel_x
    y2 = origin_y + height * pixel_y
    return (min(origin_x, x2), min(origin_y, y2), max(origin_x, x2), max(origin_y, y2))


def crop_to_overlap(
    source_array: np.ndarray,
    ref_array: np.ndarray,
    source_metadata: CubMetadata,
    ref_metadata: CubMetadata,
) -> OverlapResult:
    """Crop arrays to their geospatial intersection or their shared pixel extent."""

    source = np.asarray(source_array)
    reference = np.asarray(ref_array)
    if source.ndim != 2 or reference.ndim != 2:
        raise ValueError("crop_to_overlap expects two-dimensional image arrays")
    sx0, sy0, sx1, sy1 = _extent(source, source_metadata)
    rx0, ry0, rx1, ry1 = _extent(reference, ref_metadata)
    left, top = max(sx0, rx0), max(sy0, ry0)
    right, bottom = min(sx1, rx1), min(sy1, ry1)
    if right <= left or bottom <= top:
        raise ValueError("Source and reference images have no overlapping footprint")

    def window(array: np.ndarray, metadata: CubMetadata) -> tuple[slice, slice, tuple[int, int, int, int]]:
        x0, y0, x1, y1 = _extent(array, metadata)
        transform = metadata.get("geotransform")
        if transform:
            origin_x, pixel_x, _, origin_y, _, pixel_y = transform
            first_x = (left - origin_x) / pixel_x
            last_x = (right - origin_x) / pixel_x
            first_y = (top - origin_y) / pixel_y
            last_y = (bottom - origin_y) / pixel_y
            start_x, end_x = int(np.floor(min(first_x, last_x))), int(np.ceil(max(first_x, last_x)))
            start_y, end_y = int(np.floor(min(first_y, last_y))), int(np.ceil(max(first_y, last_y)))
        else:
            height, width = array.shape
            start_x, start_y = int(left), int(top)
            end_x, end_y = min(int(right), width), min(int(bottom), height)
        start_x, end_x = max(0, start_x), min(array.shape[1], end_x)
        start_y, end_y = max(0, start_y), min(array.shape[0], end_y)
        return slice(start_y, end_y), slice(start_x, end_x), (start_x, start_y, end_x, end_y)

    source_y, source_x, source_bounds = window(source, source_metadata)
    ref_y, ref_x, ref_bounds = window(reference, ref_metadata)
    cropped_source = source[source_y, source_x]
    cropped_reference = reference[ref_y, ref_x]
    if cropped_source.size == 0 or cropped_reference.size == 0:
        raise ValueError("Computed overlap is empty after converting to pixel windows")
    return {
        "source": cropped_source,
        "reference": cropped_reference,
        "bounds": {"source": source_bounds, "reference": ref_bounds},
    }
