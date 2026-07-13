"""Contract tests for the closed event union."""

import pytest
from pydantic import ValidationError

from im.schema.events import EVENT_ADAPTER, SnapshotEvent, StateCheckpointEvent

DIGEST = "sha256:" + "0" * 64
SNAPSHOT_PAYLOAD = {
    "text": "test",
    "selection_start_utf16": 4,
    "selection_end_utf16": 4,
    "is_composing": False,
    "edit_kind": "insert",
}
SPAN = {"event_id": "e_000001", "start_utf16": 0, "end_utf16": 4, "text": "test"}
CAPABILITIES = {
    "min_timer_interval_ms": 1_000,
    "max_timer_interval_ms": 86_400_000,
    "max_active_timers": 16,
    "max_timer_message_bytes": 512,
}


def envelope(source: str, kind: str, payload: dict[str, object], **extra) -> dict[str, object]:
    return {
        "v": 1,
        "id": "e_000001",
        "seq": 1,
        "dt_ms": 0,
        "source": source,
        "kind": kind,
        **extra,
        "payload": payload,
    }


CHECKPOINT_PAYLOAD = {
    "segment": {
        "segment_index": 1,
        "covers_through_policy_seq": 42,
        "previous_segment_hash": DIGEST,
    },
    "capabilities": CAPABILITIES,
    "snapshot": {
        "event_id": "e_000001",
        "activity": "active",
        **SNAPSHOT_PAYLOAD,
        "age_ms": 10,
    },
    "timers": [
        {
            "timer_id": "t_001",
            "instruction_id": "i_001",
            "instruction_text": "test",
            "interval_ms": 5_000,
            "message": "breathe",
            "status": "active",
            "next_due_in_ms": 1_000,
            "fire_count": 2,
        }
    ],
    "open_timer_fires": [],
    "open_tool_results": [],
    "pending_tools": [
        {
            "request_id": "r_001",
            "policy_seq": 7,
            "fact_event_id": "e_000001",
            "fact_text": "test",
            "tool": "lookup",
            "args": {"query": "test"},
            "age_ms": 8,
        }
    ],
    "prior_uses": [],
    "applied_marks": [],
    "ambiguous_marks": [],
    "recent_events": [],
    "dispositions": [],
    "hashes": {
        "schema_hash": DIGEST,
        "spec_hash": DIGEST,
        "prompt_hash": DIGEST,
        "config_hash": DIGEST,
        "renderer_id": "serialize-v1",
        "canonicalizer_id": "tim-json-v1",
    },
}

VALID_EVENTS = [
    envelope("user", "snapshot", SNAPSHOT_PAYLOAD, activity="active"),
    envelope("user", "annotation", {"text": "note"}),
    envelope(
        "timer", "fire", {"timer_id": "t_001", "fire_count": 1, "late_ms": 0, "missed_count": 0}
    ),
    envelope(
        "tool", "result", {"request_id": "r_001", "status": "succeeded", "data": {"score": 4}}
    ),
    envelope(
        "runtime",
        "session_start",
        {
            "schema_version": 1,
            "renderer_id": "serialize-v1",
            "canonicalizer_id": "tim-json-v1",
            "tool_registry_version": 1,
            "hash_algorithm": "sha256",
            "capabilities": CAPABILITIES,
            "schema_hash": DIGEST,
            "spec_hash": DIGEST,
            "prompt_hash": DIGEST,
            "config_hash": DIGEST,
        },
    ),
    envelope(
        "runtime",
        "scheduled",
        {
            "timer_id": "t_001",
            "instruction_id": "i_001",
            "interval_ms": 5_000,
            "message": "breathe",
            "first_due_in_ms": 5_000,
        },
    ),
    envelope("runtime", "cancel_ack", {"timer_ids": ["t_001"]}),
    envelope(
        "runtime",
        "tool_requested",
        {"request_id": "r_001", "tool": "lookup", "args": {"query": "score"}},
    ),
    envelope("runtime", "action_rejected", {"reason": "span_mismatch"}),
    envelope("runtime", "state_checkpoint", CHECKPOINT_PAYLOAD),
    envelope(
        "model",
        "action_executed",
        {"action": {"type": "mark", "instruction": SPAN, "target": SPAN}},
    ),
]


@pytest.mark.parametrize("payload", VALID_EVENTS)
def test_every_event_kind_validates(payload: dict[str, object]) -> None:
    event = EVENT_ADAPTER.validate_python(payload)

    assert event.kind == payload["kind"]


def test_snapshot_activity_is_closed_and_only_allowed_on_snapshots() -> None:
    with pytest.raises(ValidationError):
        EVENT_ADAPTER.validate_python(
            envelope("user", "snapshot", SNAPSHOT_PAYLOAD, activity="idle")
        )
    with pytest.raises(ValidationError):
        EVENT_ADAPTER.validate_python(
            envelope("user", "annotation", {"text": "note"}, activity="active")
        )


def test_source_kind_pair_is_closed() -> None:
    with pytest.raises(ValidationError):
        EVENT_ADAPTER.validate_python(
            envelope("runtime", "snapshot", SNAPSHOT_PAYLOAD, activity="active")
        )


@pytest.mark.parametrize(
    "payload",
    [
        envelope("user", "snapshot", SNAPSHOT_PAYLOAD),
        envelope("user", "snapshot", SNAPSHOT_PAYLOAD, activity="active", extra=True),
        envelope(
            "timer",
            "fire",
            {"timer_id": "t_001", "fire_count": True, "late_ms": 0, "missed_count": 0},
        ),
        envelope(
            "model",
            "action_executed",
            {"action": {"type": "idle", "reason": "no_trigger", "related_event_id": None}},
        ),
    ],
)
def test_missing_extra_bool_and_executed_idle_reject(payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        EVENT_ADAPTER.validate_python(payload)


@pytest.mark.parametrize("field", ["v", "schema_version", "tool_registry_version"])
def test_version_fields_reject_boolean_true(field: str) -> None:
    payload = VALID_EVENTS[4].copy()
    if field == "v":
        payload[field] = True
    else:
        payload["payload"] = {**payload["payload"], field: True}

    with pytest.raises(ValidationError, match="boolean"):
        EVENT_ADAPTER.validate_python(payload)


def test_snapshot_selection_uses_utf16_bounds() -> None:
    event = EVENT_ADAPTER.validate_python(
        envelope(
            "user",
            "snapshot",
            {
                "text": "a😀b",
                "selection_start_utf16": 3,
                "selection_end_utf16": 3,
                "is_composing": False,
                "edit_kind": "cursor_move",
            },
            activity="active",
        )
    )
    assert isinstance(event, SnapshotEvent)

    with pytest.raises(ValidationError):
        EVENT_ADAPTER.validate_python(
            envelope(
                "user",
                "snapshot",
                {**SNAPSHOT_PAYLOAD, "text": "a😀b", "selection_end_utf16": 5},
                activity="active",
            )
        )


@pytest.mark.parametrize("data", [1.5, 2**53, {"bad": "\ud800"}])
def test_tool_data_obeys_tim_json_v1(data: object) -> None:
    with pytest.raises(ValidationError):
        EVENT_ADAPTER.validate_python(
            envelope("tool", "result", {"request_id": "r_001", "status": "succeeded", "data": data})
        )


def test_free_form_json_enforces_canonical_byte_limit_in_events_and_checkpoints() -> None:
    oversized_data = ["x" * 4_096 for _ in range(5)]
    tool_event = envelope(
        "tool",
        "result",
        {"request_id": "r_001", "status": "succeeded", "data": oversized_data},
    )
    checkpoint = {
        **CHECKPOINT_PAYLOAD,
        "open_tool_results": [
            {
                "event_id": "e_000002",
                "policy_seq": 2,
                "request_id": "r_001",
                "fact_event_id": "e_000001",
                "fact_text": "test",
                "tool": "lookup",
                "args": {"query": "test"},
                "status": "succeeded",
                "data": oversized_data,
                "age_ms": 0,
            }
        ],
    }

    with pytest.raises(ValidationError, match="max_json_bytes"):
        EVENT_ADAPTER.validate_python(tool_event)
    with pytest.raises(ValidationError, match="max_json_bytes"):
        EVENT_ADAPTER.validate_python(envelope("runtime", "state_checkpoint", checkpoint))


def test_checkpoint_arrays_require_lexicographic_unique_ids() -> None:
    timers = [
        {**CHECKPOINT_PAYLOAD["timers"][0], "timer_id": "t_002"},
        CHECKPOINT_PAYLOAD["timers"][0],
    ]
    invalid = {**CHECKPOINT_PAYLOAD, "timers": timers}

    with pytest.raises(ValidationError, match="lexicographically sorted"):
        EVENT_ADAPTER.validate_python(envelope("runtime", "state_checkpoint", invalid))


def test_checkpoint_pending_tools_sort_only_by_request_id() -> None:
    first = {
        **CHECKPOINT_PAYLOAD["pending_tools"][0],
        "request_id": "r_001",
        "fact_event_id": "e_000002",
    }
    second = {
        **CHECKPOINT_PAYLOAD["pending_tools"][0],
        "request_id": "r_002",
        "fact_event_id": "e_000001",
    }
    valid = {**CHECKPOINT_PAYLOAD, "pending_tools": [first, second]}
    invalid = {**CHECKPOINT_PAYLOAD, "pending_tools": [second, first]}

    event = EVENT_ADAPTER.validate_python(envelope("runtime", "state_checkpoint", valid))
    assert isinstance(event, StateCheckpointEvent)
    with pytest.raises(ValidationError, match="lexicographically sorted"):
        EVENT_ADAPTER.validate_python(envelope("runtime", "state_checkpoint", invalid))


def test_checkpoint_fire_due_age_is_an_integrity_checked_relative_value() -> None:
    invalid = {
        **CHECKPOINT_PAYLOAD,
        "open_timer_fires": [
            {
                "event_id": "e_000002",
                "policy_seq": 2,
                "timer_id": "t_001",
                "fire_count": 1,
                "missed_count": 0,
                "late_ms": 4,
                "due_age_ms": 6,
                "age_ms": 3,
            }
        ],
    }

    with pytest.raises(ValidationError, match="due_age_ms"):
        EVENT_ADAPTER.validate_python(envelope("runtime", "state_checkpoint", invalid))


@pytest.mark.parametrize("fact_event_id", [None, "snapshot-1"])
def test_checkpoint_pending_tool_requires_valid_fact_event_id(
    fact_event_id: str | None,
) -> None:
    pending = dict(CHECKPOINT_PAYLOAD["pending_tools"][0])
    if fact_event_id is None:
        del pending["fact_event_id"]
    else:
        pending["fact_event_id"] = fact_event_id
    invalid = {**CHECKPOINT_PAYLOAD, "pending_tools": [pending]}

    with pytest.raises(ValidationError):
        EVENT_ADAPTER.validate_python(envelope("runtime", "state_checkpoint", invalid))


def test_checkpoint_is_fully_typed() -> None:
    event = EVENT_ADAPTER.validate_python(
        envelope("runtime", "state_checkpoint", CHECKPOINT_PAYLOAD)
    )

    assert isinstance(event, StateCheckpointEvent)
    assert event.payload.snapshot.event_id == "e_000001"
    assert event.payload.capabilities.max_active_timers == 16
    assert event.payload.timers[0].timer_id == "t_001"
    assert event.payload.pending_tools[0].fact_event_id == "e_000001"


def test_checkpoint_prior_uses_are_a_closed_sorted_union() -> None:
    schedule_use = {
        "kind": "schedule",
        "action_event_id": "e_000010",
        "policy_seq": 10,
        "instruction": SPAN,
        "timer_id": "t_002",
        "timer_status": "canceled",
        "age_ms": 5,
    }
    delegate_use = {
        "kind": "delegate",
        "action_event_id": "e_000009",
        "policy_seq": 9,
        "fact": SPAN,
        "request_id": "r_002",
        "tool": "lookup",
        "args": {"query": "test"},
        "result_event_id": "e_000011",
        "result_status": "succeeded",
        "result_disposition": "handled",
        "age_ms": 6,
    }
    valid = {**CHECKPOINT_PAYLOAD, "prior_uses": [delegate_use, schedule_use]}
    event = EVENT_ADAPTER.validate_python(envelope("runtime", "state_checkpoint", valid))

    assert isinstance(event, StateCheckpointEvent)
    assert [item.kind for item in event.payload.prior_uses] == ["delegate", "schedule"]

    for invalid_uses in (
        [schedule_use, delegate_use],
        [delegate_use, delegate_use],
        [{**schedule_use, "kind": "unknown"}],
        [{key: value for key, value in schedule_use.items() if key != "timer_status"}],
    ):
        with pytest.raises(ValidationError):
            EVENT_ADAPTER.validate_python(
                envelope(
                    "runtime",
                    "state_checkpoint",
                    {**CHECKPOINT_PAYLOAD, "prior_uses": invalid_uses},
                )
            )


@pytest.mark.parametrize(
    "timer_patch,capability_patch",
    [
        ({"status": "active", "next_due_in_ms": None}, {}),
        ({"status": "canceled", "next_due_in_ms": 1}, {}),
        ({"interval_ms": 999}, {}),
        ({"interval_ms": 86_400_001}, {}),
        ({"message": "é" * 257}, {}),
        ({}, {"max_active_timers": 0}),
    ],
)
def test_checkpoint_timers_must_match_visible_capabilities(
    timer_patch: dict[str, object],
    capability_patch: dict[str, object],
) -> None:
    timer = {**CHECKPOINT_PAYLOAD["timers"][0], **timer_patch}
    capabilities = {**CHECKPOINT_PAYLOAD["capabilities"], **capability_patch}
    invalid = {**CHECKPOINT_PAYLOAD, "capabilities": capabilities, "timers": [timer]}

    with pytest.raises(ValidationError):
        EVENT_ADAPTER.validate_python(envelope("runtime", "state_checkpoint", invalid))


def test_response_scoped_checkpoint_disposition_can_only_be_handled() -> None:
    invalid = {
        **CHECKPOINT_PAYLOAD,
        "dispositions": [
            {
                "event_id": "e_000001",
                "policy_seq": 1,
                "relation": "responded_to",
                "state": "skipped",
            }
        ],
    }

    with pytest.raises(ValidationError, match="responded_to"):
        EVENT_ADAPTER.validate_python(envelope("runtime", "state_checkpoint", invalid))


def test_event_schema_requires_kind_and_references_recursive_integer_json() -> None:
    schema = EVENT_ADAPTER.json_schema()

    assert "kind" in schema["$defs"]["SnapshotEvent"]["required"]
    assert "capabilities" in schema["$defs"]["SessionStartPayload"]["required"]
    assert "capabilities" in schema["$defs"]["StateCheckpointPayload"]["required"]
    assert "policy_seq" in schema["$defs"]["CheckpointOpenTimerFire"]["required"]
    assert "policy_seq" in schema["$defs"]["CheckpointOpenToolResult"]["required"]
    assert "activity" in schema["$defs"]["CheckpointSnapshot"]["required"]
    assert {
        "fact_event_id",
        "fact_text",
        "args",
    } <= set(schema["$defs"]["CheckpointOpenToolResult"]["required"])
    assert "policy_seq" in schema["$defs"]["CheckpointPendingTool"]["required"]
    assert "prior_uses" in schema["$defs"]["StateCheckpointPayload"]["required"]
    assert {"policy_seq", "relation"} <= set(
        schema["$defs"]["CheckpointDisposition"]["required"]
    )
    assert "ambiguous_marks" in schema["$defs"]["StateCheckpointPayload"]["required"]
    assert "TimJsonValue" in schema["$defs"]
    assert not any(
        branch.get("type") == "number" for branch in schema["$defs"]["TimJsonValue"]["anyOf"]
    )
