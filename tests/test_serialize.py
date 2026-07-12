"""Canonical event-byte and framing tests."""

import json
from copy import deepcopy

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import BaseModel
from pydantic import ValidationError as PydanticValidationError

from im.canonical_json import DuplicateKeyError
from im.schema.actions import ACTION_ADAPTER
from im.schema.events import EVENT_ADAPTER
from im.schema.textspan import utf16_len
from im.serialize import (
    _FIELD_ORDER,
    EventSerializationError,
    _to_json_value,
    join_rendered_events,
    parse_event,
    render_event,
)
from test_actions import VALID_ACTIONS
from test_events import CHECKPOINT_PAYLOAD, DIGEST, SPAN, VALID_EVENTS, envelope

FULL_CHECKPOINT_PAYLOAD = {
    **deepcopy(CHECKPOINT_PAYLOAD),
    "open_timer_fires": [
        {
            "event_id": "e_000002",
            "timer_id": "t_001",
            "fire_count": 3,
            "missed_count": 1,
            "late_ms": 50,
            "age_ms": 10,
        }
    ],
    "open_tool_results": [
        {
            "event_id": "e_000003",
            "request_id": "r_001",
            "tool": "lookup",
            "status": "succeeded",
            "data": {"score": 4},
            "age_ms": 9,
        }
    ],
    "pending_tools": [
        {
            "request_id": "r_002",
            "fact_text": "test",
            "tool": "lookup",
            "args": {"query": "score"},
            "age_ms": 8,
        }
    ],
    "applied_marks": [
        {
            "mark_event_id": "e_000004",
            "instruction_text": "test",
            "target": SPAN,
            "age_ms": 7,
        }
    ],
    "recent_events": [{"event_id": "e_000005", "rendered": "{}"}],
    "dispositions": [{"event_id": "e_000006", "state": "handled"}],
}

FULL_VARIANT_EVENTS = [
    *VALID_EVENTS,
    envelope("runtime", "state_checkpoint", FULL_CHECKPOINT_PAYLOAD),
    *[envelope("model", "action_executed", {"action": action}) for action in VALID_ACTIONS[1:]],
    envelope(
        "model",
        "action_executed",
        {
            "action": {
                "type": "cancel",
                "instruction": SPAN,
                "target": {"kind": "timers", "timer_ids": ["t_001", "t_002"]},
            }
        },
    ),
    envelope(
        "model",
        "action_executed",
        {
            "action": {
                "type": "cancel",
                "instruction": SPAN,
                "target": {"kind": "all_active"},
            }
        },
    ),
]


def test_build_plan_snapshot_is_byte_exact() -> None:
    event = {
        "v": 1,
        "id": "e_000042",
        "seq": 42,
        "dt_ms": 650,
        "source": "user",
        "kind": "snapshot",
        "activity": "active",
        "payload": {
            "text": "remind me every five seconds to breathe",
            "selection_start_utf16": 39,
            "selection_end_utf16": 39,
            "is_composing": False,
            "edit_kind": "insert",
        },
    }

    assert render_event(event) == (
        b'{"v":1,"id":"e_000042","seq":42,"dt_ms":650,"source":"user",'
        b'"kind":"snapshot","activity":"active","payload":{"text":"remind me every '
        b'five seconds to breathe","selection_start_utf16":39,"selection_end_utf16":39,'
        b'"is_composing":false,"edit_kind":"insert"}}'
    )


@pytest.mark.parametrize("payload", VALID_EVENTS)
def test_every_event_kind_round_trips_byte_for_byte(payload: dict[str, object]) -> None:
    event = EVENT_ADAPTER.validate_python(payload)
    rendered = render_event(event)

    assert parse_event(rendered) == event
    assert render_event(parse_event(rendered)) == rendered


def test_tim_json_subtree_uses_utf16_key_order() -> None:
    event = envelope(
        "tool",
        "result",
        {
            "request_id": "r_001",
            "status": "succeeded",
            "data": {"\ue000": 1, "\U00010000": 2},
        },
    )

    assert '"data":{"𐀀":2,"":1}'.encode() in render_event(event)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda value: value.replace(b'{"v":1,', b'{ "v":1,', 1),
        lambda value: value.replace(b'"v":1,"id"', b'"id":"e_000001","v"', 1),
        lambda value: value + b"\n",
        lambda value: b"\xef\xbb\xbf" + value,
        lambda value: value.replace(b'"note"', b'"\\u006eote"'),
    ],
)
def test_parse_rejects_noncanonical_bytes(mutate) -> None:
    rendered = render_event(VALID_EVENTS[1])

    with pytest.raises(EventSerializationError):
        parse_event(mutate(rendered))


def test_parse_rejects_duplicate_keys() -> None:
    rendered = render_event(VALID_EVENTS[1])
    duplicated = rendered.replace(b'{"v":1,', b'{"v":1,"v":1,', 1)

    with pytest.raises(DuplicateKeyError):
        parse_event(duplicated)


def test_policy_context_framing_has_single_lf_and_no_trailing_newline() -> None:
    first = render_event(VALID_EVENTS[0])
    second = render_event(VALID_EVENTS[1])

    assert join_rendered_events([first, second]) == first + b"\n" + second
    assert join_rendered_events([]) == b""


def test_join_rejects_unfrozen_multiline_bytes() -> None:
    with pytest.raises(EventSerializationError, match="framing"):
        join_rendered_events([b"{}\n{}"])


@pytest.mark.parametrize("events", [[b""], [b"{}", b""], [b"\xef\xbb\xbf{}"]])
def test_join_rejects_empty_and_bom_bearing_blobs(events: list[bytes]) -> None:
    with pytest.raises(EventSerializationError):
        join_rendered_events(events)


def test_render_enforces_per_event_byte_limit() -> None:
    event = envelope("user", "annotation", {"text": "x" * 17_000})

    with pytest.raises(EventSerializationError, match="max_json_bytes"):
        render_event(event)


def test_models_are_frozen_and_render_revalidates_mutable_nested_values() -> None:
    snapshot = EVENT_ADAPTER.validate_python(VALID_EVENTS[0])
    with pytest.raises(PydanticValidationError, match="frozen"):
        snapshot.payload.selection_end_utf16 = 99

    cancel_ack = EVENT_ADAPTER.validate_python(VALID_EVENTS[6])
    cancel_ack.payload.timer_ids.append("t_000")
    with pytest.raises(PydanticValidationError, match="lexicographically sorted"):
        render_event(cancel_ack)


valid_text = st.text(
    alphabet=st.characters(exclude_categories=("Cs",)),
    max_size=40,
)
nonempty_text = st.text(
    alphabet=st.characters(exclude_categories=("Cs", "Zl", "Zp")),
    min_size=1,
    max_size=30,
).filter(lambda value: bool(value.strip()))
event_ids = st.integers(min_value=0, max_value=999_999).map(lambda value: f"e_{value:06d}")
timer_ids = st.integers(min_value=0, max_value=999).map(lambda value: f"t_{value:03d}")
request_ids = st.integers(min_value=0, max_value=999).map(lambda value: f"r_{value:03d}")
instruction_ids = st.integers(min_value=0, max_value=999).map(lambda value: f"i_{value:03d}")
small_ints = st.integers(min_value=0, max_value=100_000)
tim_json_values = st.recursive(
    st.none() | st.booleans() | st.integers(min_value=-(2**20), max_value=2**20) | valid_text,
    lambda children: (
        st.lists(children, max_size=3) | st.dictionaries(valid_text, children, max_size=3)
    ),
    max_leaves=10,
)


@st.composite
def generated_span(draw) -> dict[str, object]:
    text = draw(nonempty_text)
    start = draw(st.integers(min_value=0, max_value=20))
    return {
        "event_id": draw(event_ids),
        "start_utf16": start,
        "end_utf16": start + utf16_len(text),
        "text": text,
    }


@st.composite
def generated_action(draw, *, allow_idle: bool = True) -> dict[str, object]:
    kinds = [
        "mark",
        "delegate",
        "integrate",
        "skip",
        "respond",
        "schedule",
        "cancel",
        "nudge",
    ]
    if allow_idle:
        kinds.append("idle")
    kind = draw(st.sampled_from(kinds))
    if kind == "idle":
        reason = draw(
            st.sampled_from(
                [
                    "no_trigger",
                    "typing_active",
                    "awaiting_tool",
                    "awaiting_opening",
                    "instruction_quoted",
                    "ambiguous",
                    "already_handled",
                ]
            )
        )
        related = (
            draw(event_ids)
            if reason in {"awaiting_tool", "awaiting_opening", "already_handled"}
            else None
        )
        return {"type": "idle", "reason": reason, "related_event_id": related}
    if kind == "mark":
        return {
            "type": "mark",
            "instruction": draw(generated_span()),
            "target": draw(generated_span()),
        }
    if kind == "delegate":
        return {
            "type": "delegate",
            "fact": draw(generated_span()),
            "tool": "lookup",
            "args": {"query": draw(nonempty_text)},
        }
    if kind == "integrate":
        return {"type": "integrate", "result_event_id": draw(event_ids), "text": draw(valid_text)}
    if kind == "skip":
        return {
            "type": "skip",
            "target_event_id": draw(event_ids),
            "reason": draw(
                st.sampled_from(["stale_tool_result", "canceled_timer", "superseded_query"])
            ),
        }
    if kind == "respond":
        return {"type": "respond", "reply_to_event_id": draw(event_ids), "text": draw(valid_text)}
    if kind == "schedule":
        return {
            "type": "schedule",
            "instruction": draw(generated_span()),
            "interval_ms": draw(st.integers(min_value=1, max_value=86_400_000)),
            "message": draw(nonempty_text),
        }
    if kind == "cancel":
        target_kind = draw(st.sampled_from(["timer", "timers", "all_active"]))
        if target_kind == "timer":
            target: dict[str, object] = {"kind": "timer", "timer_id": draw(timer_ids)}
        elif target_kind == "timers":
            values = draw(st.sets(timer_ids, min_size=1, max_size=3).map(sorted))
            target = {"kind": "timers", "timer_ids": values}
        else:
            target = {"kind": "all_active"}
        return {"type": "cancel", "instruction": draw(generated_span()), "target": target}
    return {"type": "nudge", "fire_event_id": draw(event_ids)}


@st.composite
def generated_snapshot_payload(draw) -> dict[str, object]:
    text = draw(valid_text)
    length = utf16_len(text)
    start = draw(st.integers(min_value=0, max_value=length))
    end = draw(st.integers(min_value=start, max_value=length))
    return {
        "text": text,
        "selection_start_utf16": start,
        "selection_end_utf16": end,
        "is_composing": draw(st.booleans()),
        "edit_kind": draw(
            st.sampled_from(["insert", "delete", "replace", "paste", "cursor_move", "none"])
        ),
    }


@st.composite
def generated_checkpoint_payload(draw) -> dict[str, object]:
    snapshot = draw(generated_snapshot_payload())
    timer_id = draw(timer_ids)
    request_id = draw(request_ids)
    timer = {
        "timer_id": timer_id,
        "instruction_id": draw(instruction_ids),
        "instruction_text": draw(valid_text),
        "interval_ms": draw(st.integers(min_value=1, max_value=86_400_000)),
        "message": draw(valid_text),
        "status": draw(st.sampled_from(["active", "canceled"])),
        "next_due_in_ms": draw(st.none() | small_ints),
        "fire_count": draw(small_ints),
    }
    open_fire = {
        "event_id": "e_000002",
        "timer_id": timer_id,
        "fire_count": draw(st.integers(min_value=1, max_value=100_000)),
        "missed_count": draw(small_ints),
        "late_ms": draw(small_ints),
        "age_ms": draw(small_ints),
    }
    open_result = {
        "event_id": "e_000003",
        "request_id": request_id,
        "tool": "lookup",
        "status": draw(st.sampled_from(["succeeded", "failed"])),
        "data": draw(tim_json_values),
        "age_ms": draw(small_ints),
    }
    pending = {
        "request_id": "r_998",
        "fact_text": draw(valid_text),
        "tool": "lookup",
        "args": {"query": draw(nonempty_text)},
        "age_ms": draw(small_ints),
    }
    applied_mark = {
        "mark_event_id": "e_000004",
        "instruction_text": draw(valid_text),
        "target": draw(generated_span()),
        "age_ms": draw(small_ints),
    }
    return {
        "segment": {
            "segment_index": draw(st.integers(min_value=1, max_value=100)),
            "covers_through_policy_seq": draw(small_ints),
            "previous_segment_hash": DIGEST,
        },
        "snapshot": {"event_id": "e_000001", **snapshot, "age_ms": draw(small_ints)},
        "timers": [timer] if draw(st.booleans()) else [],
        "open_timer_fires": [open_fire] if draw(st.booleans()) else [],
        "open_tool_results": [open_result] if draw(st.booleans()) else [],
        "pending_tools": [pending] if draw(st.booleans()) else [],
        "applied_marks": [applied_mark] if draw(st.booleans()) else [],
        "recent_events": (
            [{"event_id": "e_000005", "rendered": draw(valid_text)}] if draw(st.booleans()) else []
        ),
        "dispositions": (
            [
                {
                    "event_id": "e_000006",
                    "state": draw(st.sampled_from(["handled", "skipped", "superseded"])),
                }
            ]
            if draw(st.booleans())
            else []
        ),
        "hashes": {
            "schema_hash": DIGEST,
            "spec_hash": DIGEST,
            "prompt_hash": DIGEST,
            "config_hash": DIGEST,
            "renderer_id": "serialize-v1",
            "canonicalizer_id": "tim-json-v1",
        },
    }


@st.composite
def generated_event(draw) -> dict[str, object]:
    kind = draw(
        st.sampled_from(
            [
                "snapshot",
                "annotation",
                "fire",
                "result",
                "session_start",
                "scheduled",
                "cancel_ack",
                "tool_requested",
                "action_rejected",
                "state_checkpoint",
                "action_executed",
            ]
        )
    )
    base: dict[str, object] = {
        "v": 1,
        "id": draw(event_ids),
        "seq": draw(small_ints),
        "dt_ms": draw(small_ints),
    }
    if kind == "snapshot":
        return {
            **base,
            "source": "user",
            "kind": kind,
            "activity": draw(st.sampled_from(["active", "paused"])),
            "payload": draw(generated_snapshot_payload()),
        }
    if kind == "annotation":
        return {**base, "source": "user", "kind": kind, "payload": {"text": draw(valid_text)}}
    if kind == "fire":
        payload = {
            "timer_id": draw(timer_ids),
            "fire_count": draw(st.integers(min_value=1, max_value=100_000)),
            "late_ms": draw(small_ints),
            "missed_count": draw(small_ints),
        }
        return {**base, "source": "timer", "kind": kind, "payload": payload}
    if kind == "result":
        payload = {
            "request_id": draw(request_ids),
            "status": draw(st.sampled_from(["succeeded", "failed"])),
            "data": draw(tim_json_values),
        }
        return {**base, "source": "tool", "kind": kind, "payload": payload}
    if kind == "session_start":
        payload = {
            "schema_version": 1,
            "renderer_id": draw(nonempty_text),
            "canonicalizer_id": "tim-json-v1",
            "tool_registry_version": 1,
            "hash_algorithm": "sha256",
            "schema_hash": DIGEST,
            "spec_hash": DIGEST,
            "prompt_hash": DIGEST,
            "config_hash": DIGEST,
        }
    elif kind == "scheduled":
        payload = {
            "timer_id": draw(timer_ids),
            "instruction_id": draw(instruction_ids),
            "interval_ms": draw(st.integers(min_value=1, max_value=86_400_000)),
            "message": draw(nonempty_text),
            "first_due_in_ms": draw(small_ints),
        }
    elif kind == "cancel_ack":
        payload = {"timer_ids": draw(st.sets(timer_ids, min_size=1, max_size=3).map(sorted))}
    elif kind == "tool_requested":
        payload = {
            "request_id": draw(request_ids),
            "tool": "lookup",
            "args": {"query": draw(nonempty_text)},
        }
    elif kind == "action_rejected":
        payload = {
            "reason": draw(
                st.sampled_from(
                    [
                        "malformed_action",
                        "unknown_reference",
                        "span_mismatch",
                        "result_not_ready",
                        "fire_not_open",
                        "timer_not_active",
                        "duplicate_schedule",
                        "duplicate_tool_request",
                        "floor_owned",
                        "target_already_handled",
                        "timer_limit_exceeded",
                        "payload_limit_exceeded",
                        "stale_decision",
                    ]
                )
            )
        }
    elif kind == "state_checkpoint":
        payload = draw(generated_checkpoint_payload())
    else:
        payload = {"action": draw(generated_action(allow_idle=False))}
    return {
        **base,
        "source": "model" if kind == "action_executed" else "runtime",
        "kind": kind,
        "payload": payload,
    }


@given(
    text=valid_text,
    seq=st.integers(min_value=0, max_value=10_000),
    dt_ms=st.integers(min_value=0, max_value=60_000),
)
def test_generated_annotation_events_round_trip(text: str, seq: int, dt_ms: int) -> None:
    payload = envelope("user", "annotation", {"text": text})
    payload["seq"] = seq
    payload["dt_ms"] = dt_ms

    rendered = render_event(payload)

    assert render_event(parse_event(rendered)) == rendered


@given(payload=generated_event())
def test_generated_full_union_payloads_round_trip(payload: dict[str, object]) -> None:
    rendered = render_event(payload)

    assert render_event(parse_event(rendered)) == rendered


def test_field_order_is_explicit_for_every_payload_model() -> None:
    for payload in FULL_VARIANT_EVENTS:
        rendered = render_event(payload)
        parsed = json.loads(rendered)

        assert list(parsed)[:6] == ["v", "id", "seq", "dt_ms", "source", "kind"]
        if payload["kind"] == "snapshot":
            assert list(parsed)[6:] == ["activity", "payload"]
        else:
            assert list(parsed)[6:] == ["payload"]


def _assert_registered_model_order(value: object, seen: set[type[BaseModel]]) -> None:
    if isinstance(value, BaseModel):
        model_type = type(value)
        if model_type in _FIELD_ORDER:
            expected = _FIELD_ORDER[model_type]
            rendered = _to_json_value(value)
            assert isinstance(rendered, dict)
            assert tuple(rendered) == expected
            assert set(expected) == set(model_type.model_fields)
            seen.add(model_type)
        for field_name in model_type.model_fields:
            _assert_registered_model_order(getattr(value, field_name), seen)
    elif isinstance(value, list):
        for item in value:
            _assert_registered_model_order(item, seen)


def test_every_registered_nested_model_is_exercised_and_complete() -> None:
    seen: set[type[BaseModel]] = set()

    for payload in FULL_VARIANT_EVENTS:
        event = EVENT_ADAPTER.validate_python(payload)
        _assert_registered_model_order(event.payload, seen)
    for payload in VALID_ACTIONS:
        _assert_registered_model_order(ACTION_ADAPTER.validate_python(payload), seen)

    assert seen == set(_FIELD_ORDER)
