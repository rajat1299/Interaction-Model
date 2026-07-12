"""Canonical event-byte and framing tests."""

import json
from copy import deepcopy

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import BaseModel

from im.canonical_json import DuplicateKeyError
from im.schema.actions import ACTION_ADAPTER
from im.schema.events import EVENT_ADAPTER
from im.serialize import (
    _FIELD_ORDER,
    EventSerializationError,
    _to_json_value,
    join_rendered_events,
    parse_event,
    render_event,
)
from test_actions import VALID_ACTIONS
from test_events import CHECKPOINT_PAYLOAD, SPAN, VALID_EVENTS, envelope

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


valid_text = st.text(
    alphabet=st.characters(exclude_categories=("Cs",)),
    max_size=40,
)


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


@given(
    event_index=st.integers(min_value=0, max_value=len(FULL_VARIANT_EVENTS) - 1),
    seq=st.integers(min_value=0, max_value=10_000),
    dt_ms=st.integers(min_value=0, max_value=60_000),
)
def test_generated_full_union_round_trips(event_index: int, seq: int, dt_ms: int) -> None:
    payload = deepcopy(FULL_VARIANT_EVENTS[event_index])
    payload["seq"] = seq
    payload["dt_ms"] = dt_ms

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
