"""Canonical model-facing event serialization and framing."""

import json
from collections.abc import Iterable
from enum import Enum

from pydantic import BaseModel, ValidationError

from im.canonical_json import DuplicateKeyError, normalize_tim_json
from im.config import RuntimeConfig
from im.schema.actions import (
    CancelAction,
    CancelAllActiveTarget,
    CancelTimersTarget,
    CancelTimerTarget,
    DelegateAction,
    IdleAction,
    IntegrateAction,
    LookupArgs,
    MarkAction,
    NudgeAction,
    RespondAction,
    ScheduleAction,
    SkipAction,
    Span,
)
from im.schema.events import (
    EVENT_ADAPTER,
    ActionExecutedPayload,
    ActionRejectedPayload,
    AnnotationPayload,
    CancelAckPayload,
    CheckpointAppliedMark,
    CheckpointDisposition,
    CheckpointHashes,
    CheckpointOpenTimerFire,
    CheckpointOpenToolResult,
    CheckpointPendingTool,
    CheckpointRecentEvent,
    CheckpointSegment,
    CheckpointSnapshot,
    CheckpointTimer,
    Event,
    ScheduledPayload,
    SessionStartPayload,
    SnapshotEvent,
    SnapshotPayload,
    StateCheckpointPayload,
    TimerFirePayload,
    ToolRequestedPayload,
    ToolResultPayload,
)

RENDERER_ID = "serialize-v1"
_CONFIG = RuntimeConfig()


class EventSerializationError(ValueError):
    """Raised when event bytes are invalid or noncanonical."""


_FIELD_ORDER: dict[type[BaseModel], tuple[str, ...]] = {
    Span: ("event_id", "start_utf16", "end_utf16", "text"),
    LookupArgs: ("query",),
    IdleAction: ("type", "reason", "related_event_id"),
    MarkAction: ("type", "instruction", "target"),
    DelegateAction: ("type", "fact", "tool", "args"),
    IntegrateAction: ("type", "result_event_id", "text"),
    SkipAction: ("type", "target_event_id", "reason"),
    RespondAction: ("type", "reply_to_event_id", "text"),
    ScheduleAction: ("type", "instruction", "interval_ms", "message"),
    CancelTimerTarget: ("kind", "timer_id"),
    CancelTimersTarget: ("kind", "timer_ids"),
    CancelAllActiveTarget: ("kind",),
    CancelAction: ("type", "instruction", "target"),
    NudgeAction: ("type", "fire_event_id"),
    SnapshotPayload: (
        "text",
        "selection_start_utf16",
        "selection_end_utf16",
        "is_composing",
        "edit_kind",
    ),
    AnnotationPayload: ("text",),
    TimerFirePayload: ("timer_id", "fire_count", "late_ms", "missed_count"),
    ToolResultPayload: ("request_id", "status", "data"),
    SessionStartPayload: (
        "schema_version",
        "renderer_id",
        "canonicalizer_id",
        "tool_registry_version",
        "hash_algorithm",
        "schema_hash",
        "spec_hash",
        "prompt_hash",
        "config_hash",
    ),
    ScheduledPayload: (
        "timer_id",
        "instruction_id",
        "interval_ms",
        "message",
        "first_due_in_ms",
    ),
    CancelAckPayload: ("timer_ids",),
    ToolRequestedPayload: ("request_id", "tool", "args"),
    ActionRejectedPayload: ("reason",),
    CheckpointSegment: (
        "segment_index",
        "covers_through_policy_seq",
        "previous_segment_hash",
    ),
    CheckpointSnapshot: (
        "event_id",
        "text",
        "selection_start_utf16",
        "selection_end_utf16",
        "is_composing",
        "edit_kind",
        "age_ms",
    ),
    CheckpointTimer: (
        "timer_id",
        "instruction_id",
        "instruction_text",
        "interval_ms",
        "message",
        "status",
        "next_due_in_ms",
        "fire_count",
    ),
    CheckpointOpenTimerFire: (
        "event_id",
        "timer_id",
        "fire_count",
        "missed_count",
        "late_ms",
        "age_ms",
    ),
    CheckpointOpenToolResult: (
        "event_id",
        "request_id",
        "tool",
        "status",
        "data",
        "age_ms",
    ),
    CheckpointPendingTool: ("request_id", "fact_text", "tool", "args", "age_ms"),
    CheckpointAppliedMark: ("mark_event_id", "instruction_text", "target", "age_ms"),
    CheckpointRecentEvent: ("event_id", "rendered"),
    CheckpointDisposition: ("event_id", "state"),
    CheckpointHashes: (
        "schema_hash",
        "spec_hash",
        "prompt_hash",
        "config_hash",
        "renderer_id",
        "canonicalizer_id",
    ),
    StateCheckpointPayload: (
        "segment",
        "snapshot",
        "timers",
        "open_timer_fires",
        "open_tool_results",
        "pending_tools",
        "applied_marks",
        "recent_events",
        "dispositions",
        "hashes",
    ),
    ActionExecutedPayload: ("action",),
}


def _to_json_value(value: object) -> object:
    if isinstance(value, BaseModel):
        field_order = _FIELD_ORDER.get(type(value))
        if field_order is None:
            raise EventSerializationError(
                f"no canonical field order registered for {type(value).__name__}"
            )
        return {field: _to_json_value(getattr(value, field)) for field in field_order}
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, list):
        return [_to_json_value(item) for item in value]
    if isinstance(value, dict):
        normalized = normalize_tim_json(value)
        return {key: _to_json_value(item) for key, item in normalized.items()}
    if value is None or isinstance(value, bool | int | str):
        return value
    raise EventSerializationError(f"unsupported event value: {type(value).__name__}")


def _event_object(event: Event) -> dict[str, object]:
    rendered: dict[str, object] = {
        "v": event.v,
        "id": event.id,
        "seq": event.seq,
        "dt_ms": event.dt_ms,
        "source": event.source,
        "kind": event.kind,
    }
    if isinstance(event, SnapshotEvent):
        rendered["activity"] = event.activity.value
    rendered["payload"] = _to_json_value(event.payload)
    return rendered


def render_event(event: Event | object) -> bytes:
    """Validate and render one event as frozen compact UTF-8 bytes."""
    validated = EVENT_ADAPTER.validate_python(event)
    try:
        rendered = json.dumps(
            _event_object(validated),
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeEncodeError) as error:
        raise EventSerializationError("event cannot be rendered canonically") from error
    if len(rendered) > _CONFIG.max_json_bytes:
        raise EventSerializationError("event exceeds max_json_bytes")
    return rendered


def _object_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateKeyError(f"duplicate object key: {key!r}")
        result[key] = value
    return result


def parse_event(data: bytes) -> Event:
    """Parse one event and reject any byte representation that is not canonical."""
    if not isinstance(data, bytes):
        raise TypeError("event input must be bytes")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise EventSerializationError("malformed UTF-8") from error
    try:
        raw = json.loads(text, object_pairs_hook=_object_pairs)
        event = EVENT_ADAPTER.validate_python(raw)
    except DuplicateKeyError:
        raise
    except (json.JSONDecodeError, ValidationError) as error:
        raise EventSerializationError("invalid event JSON") from error
    if render_event(event) != data:
        raise EventSerializationError("event bytes are not canonical")
    return event


def join_rendered_events(events: Iterable[bytes]) -> bytes:
    """Assemble a policy context with one LF and no trailing newline."""
    rendered = list(events)
    if any(not isinstance(event, bytes) for event in rendered):
        raise TypeError("rendered events must be bytes")
    if any(not event for event in rendered):
        raise EventSerializationError("rendered event must contain one JSON object")
    if any(event.startswith(b"\xef\xbb\xbf") for event in rendered):
        raise EventSerializationError("rendered event must not contain a BOM")
    if any(b"\n" in event or b"\r" in event for event in rendered):
        raise EventSerializationError("rendered event contains a framing newline")
    return b"\n".join(rendered)
