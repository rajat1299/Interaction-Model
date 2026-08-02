"""Golden and limit tests for `tim-json-v1`."""

from dataclasses import replace

import pytest

from im.canonical_json import (
    DEFAULT_LIMITS,
    MAX_SAFE_INTEGER,
    DuplicateKeyError,
    TimJsonError,
    canonicalize_tim_json,
    parse_tim_json,
)
from im.config import RuntimeConfig, estimate_tokens


def test_default_config_is_a_tim_json_object() -> None:
    config = RuntimeConfig()

    rendered = canonicalize_tim_json(config.as_json_object())

    assert b'"rollover_permille":720' in rendered
    assert b'"len_estimator_id":"bytes-div-4-v1"' in rendered
    assert b"0.72" not in rendered


def test_config_rejects_unknown_estimator() -> None:
    with pytest.raises(ValueError, match="unknown length estimator"):
        RuntimeConfig(len_estimator_id="unknown")  # type: ignore[arg-type]


def test_config_rejects_unsafe_integer() -> None:
    with pytest.raises(ValueError, match="safe range"):
        RuntimeConfig(context_budget_tokens=MAX_SAFE_INTEGER + 1)


def test_config_rejects_limits_above_frozen_v1_schema_caps() -> None:
    with pytest.raises(ValueError, match="frozen v1 schema cap"):
        RuntimeConfig(max_timer_message_bytes=513)


def test_length_estimator_rounds_up_bytes_divided_by_four() -> None:
    assert estimate_tokens(b"") == 0
    assert estimate_tokens(b"1234") == 1
    assert estimate_tokens(b"12345") == 2


def test_object_keys_sort_by_raw_utf16_code_units() -> None:
    value = {"\ue000": 1, "\U00010000": 2}

    assert canonicalize_tim_json(value) == '{"𐀀":2,"":1}'.encode()


def test_arrays_preserve_order_and_strings_are_not_normalized() -> None:
    composed = "é"
    decomposed = "e\N{COMBINING ACUTE ACCENT}"

    assert canonicalize_tim_json([composed, decomposed]) == ('["é","é"]'.encode())


def test_control_characters_use_json_escaping() -> None:
    assert canonicalize_tim_json({"value": "line\n\tend"}) == b'{"value":"line\\n\\tend"}'


def test_parse_rejects_duplicate_keys_before_dict_collapse() -> None:
    with pytest.raises(DuplicateKeyError):
        parse_tim_json(b'{"a":1,"a":2}')


@pytest.mark.parametrize("value", [1.5, float("nan"), float("inf"), float("-inf")])
def test_python_floats_are_rejected(value: float) -> None:
    with pytest.raises(TimJsonError, match="floating-point"):
        canonicalize_tim_json(value)


@pytest.mark.parametrize("data", [b"1.5", b"NaN", b"Infinity", b"-Infinity"])
def test_parsed_floats_are_rejected(data: bytes) -> None:
    with pytest.raises(TimJsonError):
        parse_tim_json(data)


@pytest.mark.parametrize("value", [MAX_SAFE_INTEGER + 1, -MAX_SAFE_INTEGER - 1])
def test_unsafe_integers_are_rejected(value: int) -> None:
    with pytest.raises(TimJsonError, match="safe integer"):
        canonicalize_tim_json(value)


@pytest.mark.parametrize("value", [{"bad": "\ud800"}, {"\ud800": "bad"}])
def test_lone_surrogates_are_rejected(value: object) -> None:
    with pytest.raises(TimJsonError, match="lone surrogate"):
        canonicalize_tim_json(value)


def test_non_string_object_key_is_rejected() -> None:
    with pytest.raises(TimJsonError, match="keys"):
        canonicalize_tim_json({1: "value"})


def test_malformed_utf8_is_rejected() -> None:
    with pytest.raises(TimJsonError, match="UTF-8"):
        parse_tim_json(b'"\xff"')


def test_parse_accepts_noncanonical_order_and_normalizes_it() -> None:
    parsed = parse_tim_json(b'{"z":1,"a":2}')

    assert canonicalize_tim_json(parsed) == b'{"a":2,"z":1}'


def test_parse_enforces_canonical_byte_limit() -> None:
    limits = replace(DEFAULT_LIMITS, max_bytes=2)

    with pytest.raises(TimJsonError, match="bytes"):
        parse_tim_json(b"[0]", limits)


@pytest.mark.parametrize(
    ("limits", "value", "message"),
    [
        (replace(DEFAULT_LIMITS, max_depth=1), [[0]], "depth"),
        (replace(DEFAULT_LIMITS, max_members=1), {"a": 1, "b": 2}, "members"),
        (replace(DEFAULT_LIMITS, max_array_elements=1), [1, 2], "array"),
        (replace(DEFAULT_LIMITS, max_string_bytes=1), "é", "string"),
        (replace(DEFAULT_LIMITS, max_bytes=1), {}, "bytes"),
    ],
)
def test_limits_are_enforced(limits, value: object, message: str) -> None:
    with pytest.raises(TimJsonError, match=message):
        canonicalize_tim_json(value, limits)
