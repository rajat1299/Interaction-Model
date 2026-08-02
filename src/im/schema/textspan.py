"""Conversions between Python string indices and browser UTF-16 offsets."""


def _code_units(character: str) -> int:
    """Return the UTF-16 width of one Unicode scalar value."""
    codepoint = ord(character)
    if 0xD800 <= codepoint <= 0xDFFF:
        raise ValueError("lone surrogate is not valid Unicode text")
    return 2 if codepoint > 0xFFFF else 1


def _validate_text(text: str) -> None:
    for character in text:
        _code_units(character)


def utf16_len(text: str) -> int:
    """Return the number of UTF-16 code units in *text*."""
    return sum(_code_units(character) for character in text)


def py_index(text: str, utf16_offset: int) -> int:
    """Convert a UTF-16 offset to a Python index on a code-point boundary.

    Browser offsets can technically point between a surrogate pair. Python strings cannot
    represent that boundary without manufacturing invalid Unicode, so such offsets are rejected.
    """
    if isinstance(utf16_offset, bool) or not isinstance(utf16_offset, int):
        raise TypeError("UTF-16 offset must be an integer")
    if utf16_offset < 0:
        raise ValueError("UTF-16 offset must be non-negative")

    _validate_text(text)

    units = 0
    for index, character in enumerate(text):
        if units == utf16_offset:
            return index
        width = _code_units(character)
        if units < utf16_offset < units + width:
            raise ValueError("UTF-16 offset splits a surrogate pair")
        units += width

    if units == utf16_offset:
        return len(text)
    raise ValueError("UTF-16 offset is past the end of the text")


def utf16_slice(text: str, start: int, end: int) -> str:
    """Slice *text* using half-open UTF-16 offsets."""
    if end < start:
        raise ValueError("UTF-16 slice end must not precede start")
    return text[py_index(text, start) : py_index(text, end)]
