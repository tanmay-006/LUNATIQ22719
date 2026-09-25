import numpy as np
import pytest

from lunar_isis_gui.footprint import crop_to_overlap
from lunar_isis_gui.projection import _affine_fallback


def test_matching_grids_are_preserved():
    image = np.ones((8, 8), dtype=np.uint8)
    result = crop_to_overlap(image, image, {}, {})
    assert result["source"].shape == (8, 8)
    assert result["reference"].shape == (8, 8)


def test_partial_geospatial_overlap_is_cropped():
    image = np.ones((10, 10), dtype=np.uint8)
    source_metadata = {"geotransform": (0, 1, 0, 0, 0, 1)}
    reference_metadata = {"geotransform": (5, 1, 0, 5, 0, 1)}
    result = crop_to_overlap(image, image, source_metadata, reference_metadata)
    assert result["source"].shape == (5, 5)
    assert result["reference"].shape == (5, 5)


def test_no_overlap_is_reported():
    image = np.ones((10, 10), dtype=np.uint8)
    source_metadata = {"geotransform": (0, 1, 0, 0, 0, 1)}
    reference_metadata = {"geotransform": (20, 1, 0, 20, 0, 1)}
    with pytest.raises(ValueError, match="no overlapping footprint"):
        crop_to_overlap(image, image, source_metadata, reference_metadata)


def test_invalid_arrays_are_rejected():
    with pytest.raises(ValueError, match="two-dimensional"):
        crop_to_overlap(np.ones((2, 2, 1)), np.ones((2, 2)), {}, {})


def test_affine_fallback_returns_source_grid():
    source = np.arange(100, dtype=np.uint8).reshape(10, 10)
    reference = np.flipud(source)
    projected = _affine_fallback(source, reference)
    assert projected.shape == source.shape
