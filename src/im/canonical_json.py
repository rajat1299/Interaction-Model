"""The frozen integer-only `tim-json-v1` canonicalizer."""

import json
from dataclasses import dataclass
from typing import Annotated, Any, Never

from pydantic import Field, StringConstraints

from im.config import MAX_SAFE_INTEGER, RuntimeConfig

CANONICALIZER_ID = "tim-json-v1"

SafeInteger = Annotated[
    int,
    Field(strict=True, ge=-MAX_SAFE_INTEGER, le=MAX_SAFE_INTEGER),
]
TimJsonString = Annotated[
    str,
    StringConstraints(strict=True, max_length=RuntimeConfig().max_json_string_bytes),
]
TimJsonArray = Annotated[
    list["TimJsonValue"],
    Field(max_length=RuntimeConfig().max_json_array_elements),
]
TimJsonObject = Annotated[
    dict[str, "TimJsonValue"],
    Field(max_length=RuntimeConfig().max_json_members),
]
type TimJsonValue = None | bool | SafeInteger | TimJsonString | TimJsonArray | TimJsonObject


class TimJsonError(ValueError):
    """Raised when a value is outside the `tim-json-v1` domain."""


class DuplicateKeyError(TimJsonError):
    """Raised before JSON object pairs can collapse into a dictionary."""


@dataclass(frozen=True, slots=True)
class TimJsonLimits:
    max_bytes: int
    max_depth: int
    max_members: int
    max_array_elements: int
    max_string_bytes: int

    @classmethod
    def from_config(cls, config: RuntimeConfig) -> "TimJsonLimits":
        return cls(
            max_bytes=config.max_json_bytes,
            max_depth=config.max_json_depth,
            max_members=config.max_json_members,
            max_array_elements=config.max_json_array_elements,
            max_string_bytes=config.max_json_string_bytes,
        )


DEFAULT_LIMITS = TimJsonLimits.from_config(RuntimeConfig())


def _reject_float(_value: str) -> Never:
    raise TimJsonError("tim-json-v1 rejects floating-point numbers")


def _reject_constant(_value: str) -> Never:
    raise TimJsonError("tim-json-v1 rejects non-finite numbers")


def _object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateKeyError(f"duplicate object key: {key!r}")
        result[key] = value
    return result


def _utf16_sort_key(value: str) -> bytes:
    try:
        return value.encode("utf-16-be")
    except UnicodeEncodeError as error:
        raise TimJsonError("lone surrogate is not valid Unicode text") from error


def _validate_string(value: str, limits: TimJsonLimits) -> None:
    try:
        encoded = value.encode("utf-8")
    except UnicodeEncodeError as error:
        raise TimJsonError("lone surrogate is not valid Unicode text") from error
    if len(encoded) > limits.max_string_bytes:
        raise TimJsonError("string exceeds max_json_string_bytes")


def _normalize(value: object, limits: TimJsonLimits, depth: int = 0) -> TimJsonValue:
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int):
        if not -MAX_SAFE_INTEGER <= value <= MAX_SAFE_INTEGER:
            raise TimJsonError("integer is outside the safe integer domain")
        return value
    if isinstance(value, float):
        raise TimJsonError("tim-json-v1 rejects floating-point numbers")
    if isinstance(value, str):
        _validate_string(value, limits)
        return value

    if isinstance(value, list):
        container_depth = depth + 1
        if container_depth > limits.max_depth:
            raise TimJsonError("value exceeds max_json_depth")
        if len(value) > limits.max_array_elements:
            raise TimJsonError("array exceeds max_json_array_elements")
        return [_normalize(item, limits, container_depth) for item in value]

    if isinstance(value, dict):
        container_depth = depth + 1
        if container_depth > limits.max_depth:
            raise TimJsonError("value exceeds max_json_depth")
        if len(value) > limits.max_members:
            raise TimJsonError("object exceeds max_json_members")
        for key in value:
            if not isinstance(key, str):
                raise TimJsonError("object keys must be strings")
            _validate_string(key, limits)
        return {
            key: _normalize(value[key], limits, container_depth)
            for key in sorted(value, key=_utf16_sort_key)
        }

    raise TimJsonError(f"unsupported tim-json-v1 value: {type(value).__name__}")


def normalize_tim_json(
    value: object, limits: TimJsonLimits = DEFAULT_LIMITS
) -> TimJsonValue:
    """Validate a Python value and recursively order object keys canonically."""
    return _normalize(value, limits)


def canonicalize_tim_json(
    value: object, limits: TimJsonLimits = DEFAULT_LIMITS
) -> bytes:
    """Return compact UTF-8 bytes for a valid `tim-json-v1` value."""
    normalized = normalize_tim_json(value, limits)
    try:
        rendered = json.dumps(
            normalized,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeEncodeError) as error:
        raise TimJsonError("value cannot be serialized as tim-json-v1") from error
    if len(rendered) > limits.max_bytes:
        raise TimJsonError("value exceeds max_json_bytes")
    return rendered


def parse_tim_json(data: bytes, limits: TimJsonLimits = DEFAULT_LIMITS) -> TimJsonValue:
    """Parse JSON without losing duplicate keys, then validate the `tim-json-v1` domain."""
    if not isinstance(data, bytes):
        raise TypeError("tim-json-v1 input must be bytes")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise TimJsonError("malformed UTF-8") from error
    try:
        value = json.loads(
            text,
            object_pairs_hook=_object_pairs,
            parse_float=_reject_float,
            parse_constant=_reject_constant,
        )
    except TimJsonError:
        raise
    except json.JSONDecodeError as error:
        raise TimJsonError("invalid JSON") from error
    normalized = normalize_tim_json(value, limits)
    canonicalize_tim_json(normalized, limits)
    return normalized
