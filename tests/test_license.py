"""Objective-contract tests for the pure WP6 license layer."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from im.license import (
    Allowed,
    Blocked,
    LicenseView,
    PendingToolRequestView,
    SnapshotView,
    TimerFireView,
    TimerView,
    ToolResultView,
    check,
)
from im.schema.actions import Span
from im.schema.common import Disposition, LicenseBlockCode, TimerStatus, ToolName

CURRENT_SNAPSHOT_ID = "e_000001"
RESULT_EVENT_ID = "e_000002"
FIRE_EVENT_ID = "e_000003"
TIMER_ID = "t_001"
TEXT = "remind breathe"
INSTRUCTION = {
    "event_id": CURRENT_SNAPSHOT_ID,
    "start_utf16": 0,
    "end_utf16": 6,
    "text": "remind",
}
TARGET = {
    "event_id": CURRENT_SNAPSHOT_ID,
    "start_utf16": 7,
    "end_utf16": 14,
    "text": "breathe",
}


def action_payload(kind: str) -> dict[str, object]:
    """Return one fully valid payload for each action variant."""
    payloads: dict[str, dict[str, object]] = {
        "idle": {"type": "idle", "reason": "no_trigger", "related_event_id": None},
        "mark": {"type": "mark", "instruction": INSTRUCTION, "target": TARGET},
        "delegate": {
            "type": "delegate",
            "fact": INSTRUCTION,
            "tool": "lookup",
            "args": {"query": "weather"},
        },
        "integrate": {
            "type": "integrate",
            "result_event_id": RESULT_EVENT_ID,
            "text": "It is sunny.",
        },
        "skip": {
            "type": "skip",
            "target_event_id": RESULT_EVENT_ID,
            "reason": "stale_tool_result",
        },
        "respond": {
            "type": "respond",
            "reply_to_event_id": CURRENT_SNAPSHOT_ID,
            "text": "Certainly.",
        },
        "schedule": {
            "type": "schedule",
            "instruction": INSTRUCTION,
            "interval_ms": 5_000,
            "message": "breathe",
        },
        "cancel": {
            "type": "cancel",
            "instruction": INSTRUCTION,
            "target": {"kind": "timer", "timer_id": TIMER_ID},
        },
        "nudge": {"type": "nudge", "fire_event_id": FIRE_EVENT_ID},
    }
    return json.loads(json.dumps(payloads[kind]))


def view(**overrides: Any) -> LicenseView:
    """A complete objective projection in which every standard action is valid."""
    defaults: dict[str, Any] = {
        "latest_snapshot": SnapshotView(CURRENT_SNAPSHOT_ID, TEXT),
        "events": (
            ToolResultView(RESULT_EVENT_ID, "r_001", completed=True),
            TimerFireView(FIRE_EVENT_ID, TIMER_ID),
        ),
        "timers": (TimerView(TIMER_ID, TimerStatus.ACTIVE),),
    }
    defaults.update(overrides)
    return LicenseView(**defaults)


def assert_allowed(raw: object, state: LicenseView) -> Allowed:
    decision = check(raw, state)
    assert isinstance(decision, Allowed)
    return decision


def assert_blocked(raw: object, state: LicenseView, code: LicenseBlockCode) -> None:
    decision = check(raw, state)
    assert decision == Blocked(code)


PositiveCase = tuple[str, object, Callable[[], LicenseView]]

POSITIVE_CASES: list[PositiveCase] = [
    ("malformed_action", json.dumps(action_payload("idle")), view),
    ("unknown_reference", action_payload("respond"), view),
    ("span_mismatch", action_payload("mark"), view),
    ("result_not_ready", action_payload("integrate"), view),
    ("fire_not_open", action_payload("nudge"), view),
    ("timer_not_active", action_payload("cancel"), view),
    ("duplicate_schedule", action_payload("schedule"), view),
    ("duplicate_tool_request", action_payload("delegate"), view),
    ("floor_owned", action_payload("respond"), view),
    ("target_already_handled", action_payload("skip"), view),
    ("timer_limit_exceeded", action_payload("schedule"), lambda: view(max_active_timers=2)),
    ("payload_limit_exceeded", action_payload("idle"), view),
    ("stale_decision", action_payload("respond"), view),
]


@pytest.mark.parametrize(("objective_check", "raw", "state"), POSITIVE_CASES)
def test_objective_checks_allow_their_valid_case(
    objective_check: str, raw: object, state: Callable[[], LicenseView]
) -> None:
    """Each frozen objective check has a mechanically valid counterpart."""
    del objective_check
    assert_allowed(raw, state())


NEGATIVE_CASES: list[tuple[str, object, Callable[[], LicenseView], LicenseBlockCode]] = [
    (
        "malformed_action",
        b'{"type":',
        view,
        LicenseBlockCode.MALFORMED_ACTION,
    ),
    (
        "unknown_reference",
        {**action_payload("respond"), "reply_to_event_id": "e_999999"},
        view,
        LicenseBlockCode.UNKNOWN_REFERENCE,
    ),
    (
        "span_mismatch_after_snapshot_revision",
        {
            **action_payload("mark"),
            "target": {**TARGET, "text": "almost!"},
        },
        view,
        LicenseBlockCode.SPAN_MISMATCH,
    ),
    (
        "result_not_ready",
        action_payload("integrate"),
        lambda: view(events=(ToolResultView(RESULT_EVENT_ID, "r_001", completed=False),)),
        LicenseBlockCode.RESULT_NOT_READY,
    ),
    (
        "fire_not_open",
        action_payload("nudge"),
        lambda: view(events=(TimerFireView(FIRE_EVENT_ID, TIMER_ID, Disposition.HANDLED),)),
        LicenseBlockCode.FIRE_NOT_OPEN,
    ),
    (
        "timer_not_active",
        action_payload("nudge"),
        lambda: view(timers=(TimerView(TIMER_ID, TimerStatus.CANCELED),)),
        LicenseBlockCode.TIMER_NOT_ACTIVE,
    ),
    (
        "duplicate_schedule",
        action_payload("schedule"),
        lambda: view(
            timers=(
                TimerView(
                    TIMER_ID,
                    TimerStatus.ACTIVE,
                    instruction=_parse_span(INSTRUCTION),
                    interval_ms=5_000,
                    message="breathe",
                ),
            )
        ),
        LicenseBlockCode.DUPLICATE_SCHEDULE,
    ),
    (
        "duplicate_tool_request",
        {**action_payload("delegate"), "args": {"query": "  weather  "}},
        lambda: view(
            pending_tool_requests=(
                PendingToolRequestView.from_args("r_001", ToolName.LOOKUP, {"query": "weather"}),
            )
        ),
        LicenseBlockCode.DUPLICATE_TOOL_REQUEST,
    ),
    (
        "floor_owned",
        action_payload("respond"),
        lambda: view(floor_owned=True),
        LicenseBlockCode.FLOOR_OWNED,
    ),
    (
        "target_already_handled",
        action_payload("integrate"),
        lambda: view(
            events=(
                ToolResultView(
                    RESULT_EVENT_ID,
                    "r_001",
                    completed=True,
                    disposition=Disposition.HANDLED,
                ),
            )
        ),
        LicenseBlockCode.TARGET_ALREADY_HANDLED,
    ),
    (
        "timer_limit_exceeded",
        action_payload("schedule"),
        lambda: view(max_active_timers=1),
        LicenseBlockCode.TIMER_LIMIT_EXCEEDED,
    ),
    (
        "payload_limit_exceeded",
        action_payload("idle"),
        lambda: view(payload_within_limits=False),
        LicenseBlockCode.PAYLOAD_LIMIT_EXCEEDED,
    ),
    (
        "stale_decision",
        action_payload("respond"),
        lambda: view(newer_pending_snapshot=True),
        LicenseBlockCode.STALE_DECISION,
    ),
]


def _parse_span(raw: dict[str, object]) -> Span:
    return Span(**raw)


@pytest.mark.parametrize(("_name", "raw", "state", "code"), NEGATIVE_CASES)
def test_objective_checks_block_their_invalid_case(
    _name: str, raw: object, state: Callable[[], LicenseView], code: LicenseBlockCode
) -> None:
    assert_blocked(raw, state(), code)


def test_every_frozen_block_code_has_an_objective_negative_case() -> None:
    assert {case[3] for case in NEGATIVE_CASES} == set(LicenseBlockCode)


def test_quoted_instruction_is_not_a_license_policy_shortcut() -> None:
    quoted_text = "“remind breathe”"
    quoted_instruction = {**INSTRUCTION, "start_utf16": 1, "end_utf16": 7}
    raw = {**action_payload("schedule"), "instruction": quoted_instruction}

    assert_allowed(raw, view(latest_snapshot=SnapshotView(CURRENT_SNAPSHOT_ID, quoted_text)))


def test_multiple_actions_in_one_raw_policy_output_are_malformed() -> None:
    assert_blocked(
        [action_payload("idle"), action_payload("respond")],
        view(),
        LicenseBlockCode.MALFORMED_ACTION,
    )


def test_schedule_consumes_instruction_even_if_payload_changes() -> None:
    raw = {**action_payload("schedule"), "interval_ms": 10_000, "message": "stretch"}
    timer = TimerView(
        TIMER_ID,
        TimerStatus.ACTIVE,
        instruction=_parse_span(INSTRUCTION),
        interval_ms=5_000,
        message="breathe",
    )

    assert_blocked(
        raw,
        view(timers=(timer,)),
        LicenseBlockCode.DUPLICATE_SCHEDULE,
    )


def test_raw_action_json_rejects_duplicate_keys_before_collapse() -> None:
    raw = (
        b'{"type":"delegate","fact":{"event_id":"e_000001","start_utf16":0,'
        b'"end_utf16":4,"text":"fact"},"tool":"lookup","args":'
        b'{"query":"first","query":"second"}}'
    )

    assert_blocked(raw, view(), LicenseBlockCode.MALFORMED_ACTION)


FUZZED_RAW_ACTIONS = st.one_of(
    st.sampled_from(
        [
            action_payload(kind)
            for kind in [
                "idle",
                "mark",
                "delegate",
                "integrate",
                "skip",
                "respond",
                "schedule",
                "cancel",
                "nudge",
            ]
        ]
    ),
    st.binary(max_size=128),
    st.text(max_size=128),
    st.integers(),
    st.lists(st.integers(), max_size=4),
    st.none(),
)


@settings(max_examples=200, deadline=None)
@given(
    raw=FUZZED_RAW_ACTIONS,
    floor_owned=st.booleans(),
    payload_within_limits=st.booleans(),
    newer_pending_snapshot=st.booleans(),
)
def test_license_fuzz_returns_only_allowed_or_a_closed_block_code(
    raw: object,
    floor_owned: bool,
    payload_within_limits: bool,
    newer_pending_snapshot: bool,
) -> None:
    decision = check(
        raw,
        view(
            floor_owned=floor_owned,
            payload_within_limits=payload_within_limits,
            newer_pending_snapshot=newer_pending_snapshot,
        ),
    )

    assert isinstance(decision, Allowed | Blocked)
    if isinstance(decision, Blocked):
        assert decision.code in LicenseBlockCode
