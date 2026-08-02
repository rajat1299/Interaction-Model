"""Tests for browser-compatible UTF-16 span handling."""

import pytest

from im.schema.textspan import py_index, utf16_len, utf16_slice


def test_astral_emoji_uses_two_code_units() -> None:
    text = "a😀b"

    assert utf16_len(text) == 4
    assert py_index(text, 1) == 1
    assert py_index(text, 3) == 2
    assert utf16_slice(text, 1, 3) == "😀"


def test_empty_and_exact_end_offsets_are_valid() -> None:
    assert py_index("", 0) == 0
    assert py_index("abc", 3) == 3
    assert utf16_slice("abc", 2, 2) == ""


def test_zwj_family_preserves_code_point_boundaries() -> None:
    family = "👨‍👩‍👧‍👦"
    text = f"x{family}y"

    assert utf16_len(family) == 11
    assert utf16_slice(text, 1, 12) == family


def test_combining_characters_remain_separate_code_units() -> None:
    decomposed = "e\N{COMBINING ACUTE ACCENT}"

    assert utf16_len(decomposed) == 2
    assert utf16_slice(decomposed, 0, 1) == "e"
    assert utf16_slice(decomposed, 1, 2) == "\N{COMBINING ACUTE ACCENT}"


@pytest.mark.parametrize("offset", [-1, 2, 5])
def test_invalid_utf16_offsets_are_rejected(offset: int) -> None:
    with pytest.raises(ValueError):
        py_index("a😀b", offset)


def test_reversed_slice_is_rejected() -> None:
    with pytest.raises(ValueError, match="end"):
        utf16_slice("abc", 2, 1)


def test_non_integer_offset_is_rejected() -> None:
    with pytest.raises(TypeError):
        py_index("abc", True)


def test_lone_surrogate_is_rejected() -> None:
    with pytest.raises(ValueError, match="lone surrogate"):
        utf16_len("\ud800")

    with pytest.raises(ValueError, match="lone surrogate"):
        py_index("a\ud800", 0)

    with pytest.raises(ValueError, match="lone surrogate"):
        utf16_slice("a\ud800", 0, 0)


@pytest.mark.parametrize(("start", "end"), [(1, 2), (2, 3)])
def test_slice_endpoint_cannot_split_surrogate_pair(start: int, end: int) -> None:
    with pytest.raises(ValueError, match="surrogate pair"):
        utf16_slice("a😀b", start, end)
