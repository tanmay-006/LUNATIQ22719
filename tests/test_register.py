from __future__ import annotations

import numpy as np

from lunar_isis_gui.register import _parser, _resize_pair


def test_resize_pair_bounds_longest_dimension() -> None:
    source = np.zeros((200, 100), dtype=np.uint8)
    reference = np.zeros((100, 300), dtype=np.uint8)

    resized_source, resized_reference, scale = _resize_pair(source, reference, 120)

    assert resized_source.shape == (80, 40)
    assert resized_reference.shape == (40, 120)
    assert scale == 0.4


def test_parser_uses_safe_high_resolution_default() -> None:
    args = _parser().parse_args(["source.cub", "reference.cub", "outputs"])

    assert args.projection_method == "fallback"
    assert args.max_dimension == 2048
    assert args.method == "sift"


def test_resize_pair_preserves_native_dimensions_with_zero_limit() -> None:
    source = np.zeros((200, 100), dtype=np.uint8)
    reference = np.zeros((100, 300), dtype=np.uint8)

    resized_source, resized_reference, scale = _resize_pair(source, reference, 0)

    assert resized_source is source
    assert resized_reference is reference
    assert scale == 1.0
