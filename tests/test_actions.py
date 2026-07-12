"""Contract tests for the strict nine-action union."""

import json

import pytest
from pydantic import ValidationError

from im.config import RuntimeConfig
from im.schema.actions import ACTION_ADAPTER, Action, ScheduleAction

SPAN = {
    "event_id": "e_000001",
    "start_utf16": 0,
    "end_utf16": 4,
    "text": "test",
}

VALID_ACTIONS = [
    {"type": "idle", "reason": "no_trigger", "related_event_id": None},
    {"type": "mark", "instruction": SPAN, "target": SPAN},
    {
        "type": "delegate",
        "fact": SPAN,
        "tool": "lookup",
        "args": {"query": "current score"},
    },
    {"type": "integrate", "result_event_id": "e_000002", "text": "The score is 4–2."},
    {"type": "skip", "target_event_id": "e_000002", "reason": "stale_tool_result"},
    {"type": "respond", "reply_to_event_id": "e_000001", "text": "Certainly."},
    {"type": "schedule", "instruction": SPAN, "interval_ms": 5_000, "message": "breathe"},
    {
        "type": "cancel",
        "instruction": SPAN,
        "target": {"kind": "timer", "timer_id": "t_001"},
    },
    {"type": "nudge", "fire_event_id": "e_000003"},
]


@pytest.mark.parametrize("payload", VALID_ACTIONS)
def test_each_action_variant_validates(payload: dict[str, object]) -> None:
    action = ACTION_ADAPTER.validate_python(payload)

    assert action.type == payload["type"]


def test_json_union_round_trip_preserves_type_first() -> None:
    for payload in VALID_ACTIONS:
        action = ACTION_ADAPTER.validate_json(json.dumps(payload))
        rendered = ACTION_ADAPTER.dump_json(action)

        assert rendered.startswith(b'{"type":')
        assert ACTION_ADAPTER.validate_json(rendered) == action


def test_exported_schema_requires_action_and_cancel_discriminators() -> None:
    schema = ACTION_ADAPTER.json_schema()
    definitions = schema["$defs"]

    for name in [
        "IdleAction",
        "MarkAction",
        "DelegateAction",
        "IntegrateAction",
        "SkipAction",
        "RespondAction",
        "ScheduleAction",
        "CancelAction",
        "NudgeAction",
    ]:
        assert "type" in definitions[name]["required"]
    for name in ["CancelTimerTarget", "CancelTimersTarget", "CancelAllActiveTarget"]:
        assert "kind" in definitions[name]["required"]


@pytest.mark.parametrize(
    "payload",
    [
        {"type": "unknown"},
        {"type": "mark", "target": SPAN},
        {"type": "nudge", "fire_event_id": "e_000003", "timer_id": "t_001"},
        {"type": "respond", "reply_to_event_id": "not-an-event", "text": "hi"},
    ],
)
def test_unknown_missing_provenance_and_extra_fields_reject(payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        ACTION_ADAPTER.validate_python(payload)


@pytest.mark.parametrize(
    "span",
    [
        {**SPAN, "start_utf16": 4},
        {**SPAN, "end_utf16": 3},
        {**SPAN, "text": "bad"},
        {**SPAN, "text": "\ud800"},
        {**SPAN, "start_utf16": True},
    ],
)
def test_invalid_span_rejects(span: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        ACTION_ADAPTER.validate_python({"type": "mark", "instruction": SPAN, "target": span})


@pytest.mark.parametrize(
    ("reason", "related_event_id"),
    [
        ("awaiting_tool", None),
        ("awaiting_opening", None),
        ("already_handled", None),
        ("no_trigger", "e_000001"),
    ],
)
def test_idle_related_event_matches_reason(reason: str, related_event_id: str | None) -> None:
    with pytest.raises(ValidationError):
        ACTION_ADAPTER.validate_python(
            {"type": "idle", "reason": reason, "related_event_id": related_event_id}
        )


def test_lookup_query_and_timer_message_trim_outer_whitespace() -> None:
    delegate = ACTION_ADAPTER.validate_python(
        {"type": "delegate", "fact": SPAN, "tool": "lookup", "args": {"query": "  a  b  "}}
    )
    schedule = ACTION_ADAPTER.validate_python(
        {"type": "schedule", "instruction": SPAN, "interval_ms": 1, "message": "  breathe  "}
    )

    assert delegate.args.query == "a  b"
    assert isinstance(schedule, ScheduleAction)
    assert schedule.message == "breathe"


def test_outer_whitespace_is_trimmed_before_length_limits() -> None:
    delegate = ACTION_ADAPTER.validate_python(
        {
            "type": "delegate",
            "fact": SPAN,
            "tool": "lookup",
            "args": {"query": " " * 5_000 + "x"},
        }
    )
    schedule = ACTION_ADAPTER.validate_python(
        {
            "type": "schedule",
            "instruction": SPAN,
            "interval_ms": 1,
            "message": " " * 600 + "x",
        }
    )

    assert delegate.args.query == "x"
    assert schedule.message == "x"


@pytest.mark.parametrize(
    "payload",
    [
        {"type": "delegate", "fact": SPAN, "tool": "other", "args": {"query": "x"}},
        {"type": "delegate", "fact": SPAN, "tool": "lookup", "args": {"query": "   "}},
        {"type": "delegate", "fact": SPAN, "tool": "lookup", "args": {"query": "x", "k": 1}},
        {"type": "schedule", "instruction": SPAN, "interval_ms": 0, "message": "x"},
        {"type": "schedule", "instruction": SPAN, "interval_ms": True, "message": "x"},
        {"type": "schedule", "instruction": SPAN, "interval_ms": 1, "message": "   "},
    ],
)
def test_tool_and_schedule_constraints_reject(payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        ACTION_ADAPTER.validate_python(payload)


def test_lookup_and_timer_message_utf8_byte_limits() -> None:
    config = RuntimeConfig()
    long_query = "é" * (config.max_json_string_bytes // 2 + 1)
    long_message = "é" * (config.max_timer_message_bytes // 2 + 1)

    with pytest.raises(ValidationError, match="max_json_string_bytes"):
        ACTION_ADAPTER.validate_python(
            {"type": "delegate", "fact": SPAN, "tool": "lookup", "args": {"query": long_query}}
        )
    with pytest.raises(ValidationError, match="max_timer_message_bytes"):
        ACTION_ADAPTER.validate_python(
            {"type": "schedule", "instruction": SPAN, "interval_ms": 1, "message": long_message}
        )


@pytest.mark.parametrize(
    "target",
    [
        {"kind": "timers", "timer_ids": []},
        {"kind": "timers", "timer_ids": ["t_002", "t_001"]},
        {"kind": "timers", "timer_ids": ["t_001", "t_001"]},
        {"kind": "all_active", "timer_id": "t_001"},
    ],
)
def test_cancel_target_constraints_reject(target: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        ACTION_ADAPTER.validate_python({"type": "cancel", "instruction": SPAN, "target": target})


def test_cancel_target_union_accepts_sorted_set_and_all_active() -> None:
    for target in [
        {"kind": "timers", "timer_ids": ["t_001", "t_002"]},
        {"kind": "all_active"},
    ]:
        action: Action = ACTION_ADAPTER.validate_python(
            {"type": "cancel", "instruction": SPAN, "target": target}
        )
        assert action.type == "cancel"
