"""Runtime configuration and closed registries."""

from dataclasses import asdict, dataclass
from typing import Literal

LengthEstimatorId = Literal["bytes-div-4-v1"]
MAX_SAFE_INTEGER = (1 << 53) - 1
SQLITE_MAX_INTEGER = (1 << 63) - 1

V1_MAX_TIMER_MESSAGE_BYTES = 512
V1_MAX_JSON_BYTES = 16_384
V1_MAX_JSON_DEPTH = 8
V1_MAX_JSON_MEMBERS = 64
V1_MAX_JSON_ARRAY_ELEMENTS = 64
V1_MAX_JSON_STRING_BYTES = 4_096


@dataclass(frozen=True, slots=True)
class RuntimeConfig:
    """All Phase 0 runtime constants in a hashable, JSON-safe representation."""

    pause_ms: int = 1_500
    sampler_throttle_ms: int = 100
    context_budget_tokens: int = 12_000
    rollover_permille: int = 720
    checkpoint_reserved_tokens: int = 2_000
    recent_events_budget_tokens: int = 1_000
    len_estimator_id: LengthEstimatorId = "bytes-div-4-v1"
    min_timer_interval_ms: int = 1_000
    max_timer_interval_ms: int = 86_400_000
    max_active_timers: int = 16
    max_timer_message_bytes: int = V1_MAX_TIMER_MESSAGE_BYTES
    max_json_bytes: int = V1_MAX_JSON_BYTES
    max_json_depth: int = V1_MAX_JSON_DEPTH
    max_json_members: int = V1_MAX_JSON_MEMBERS
    max_json_array_elements: int = V1_MAX_JSON_ARRAY_ELEMENTS
    max_json_string_bytes: int = V1_MAX_JSON_STRING_BYTES

    def __post_init__(self) -> None:
        integer_fields = {
            name: value for name, value in asdict(self).items() if name != "len_estimator_id"
        }
        has_non_integer = any(
            isinstance(value, bool) or not isinstance(value, int)
            for value in integer_fields.values()
        )
        if has_non_integer:
            raise TypeError("runtime configuration numeric fields must be integers")
        if any(value <= 0 for value in integer_fields.values()):
            raise ValueError("runtime configuration numeric fields must be positive")
        if any(value > MAX_SAFE_INTEGER for value in integer_fields.values()):
            raise ValueError("runtime configuration integer exceeds tim-json-v1 safe range")
        if self.len_estimator_id != "bytes-div-4-v1":
            raise ValueError(f"unknown length estimator: {self.len_estimator_id}")
        if not 1 <= self.rollover_permille <= 1_000:
            raise ValueError("rollover_permille must be between 1 and 1000")
        if self.min_timer_interval_ms > self.max_timer_interval_ms:
            raise ValueError("minimum timer interval exceeds maximum timer interval")
        if self.max_timer_interval_ms > SQLITE_MAX_INTEGER // 1_000_000:
            raise ValueError("maximum timer interval exceeds SQLite nanosecond range")
        v1_caps = {
            "max_timer_message_bytes": V1_MAX_TIMER_MESSAGE_BYTES,
            "max_json_bytes": V1_MAX_JSON_BYTES,
            "max_json_depth": V1_MAX_JSON_DEPTH,
            "max_json_members": V1_MAX_JSON_MEMBERS,
            "max_json_array_elements": V1_MAX_JSON_ARRAY_ELEMENTS,
            "max_json_string_bytes": V1_MAX_JSON_STRING_BYTES,
        }
        for name, hard_cap in v1_caps.items():
            if integer_fields[name] > hard_cap:
                raise ValueError(f"{name} exceeds the frozen v1 schema cap")

    def as_json_object(self) -> dict[str, int | str]:
        """Return the exact `tim-json-v1` config-hash preimage object."""
        return asdict(self)

    def timer_capabilities(self) -> dict[str, int]:
        """Return the behavior-relevant timer limits shown to the policy."""
        return {
            "min_timer_interval_ms": self.min_timer_interval_ms,
            "max_timer_interval_ms": self.max_timer_interval_ms,
            "max_active_timers": self.max_active_timers,
            "max_timer_message_bytes": self.max_timer_message_bytes,
        }


def estimate_tokens(data: bytes, estimator_id: LengthEstimatorId = "bytes-div-4-v1") -> int:
    """Resolve and apply a registered deterministic length estimator."""
    if estimator_id != "bytes-div-4-v1":
        raise ValueError(f"unknown length estimator: {estimator_id}")
    return (len(data) + 3) // 4
