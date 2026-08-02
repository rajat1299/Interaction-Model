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
    LicenseEventKind,
    LicenseView,
    OtherEventView,
    PendingToolRequestView,
    SnapshotView,
    TimerFireView,
    TimerView,
    ToolResultView,
    blocking_codes,
    check,
)
from im.schema.actions import Span
from im.schema.common import (
    Disposition,
    LicenseBlockCode,
    TimerStatus,
    ToolName,
    ToolResultStatus,
)

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
            ToolResultView(
                RESULT_EVENT_ID,
                "r_001",
                completed=True,
                status=ToolResultStatus.SUCCEEDED,
            ),
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
    (
        "reason_mismatch",
        {
            "type": "idle",
            "reason": "awaiting_opening",
            "related_event_id": RESULT_EVENT_ID,
        },
        view,
    ),
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
        lambda: view(
            events=(
                ToolResultView(
                    RESULT_EVENT_ID,
                    "r_001",
                    completed=False,
                    status=ToolResultStatus.SUCCEEDED,
                ),
            )
        ),
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
                PendingToolRequestView.from_args(
                    "r_001",
                    CURRENT_SNAPSHOT_ID,
                    ToolName.LOOKUP,
                    {"query": "weather"},
                ),
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
                    status=ToolResultStatus.SUCCEEDED,
                    disposition=Disposition.HANDLED,
                ),
            )
        ),
        LicenseBlockCode.TARGET_ALREADY_HANDLED,
    ),
    (
        "reason_mismatch",
        {
            "type": "idle",
            "reason": "awaiting_tool",
            "related_event_id": CURRENT_SNAPSHOT_ID,
        },
        view,
        LicenseBlockCode.REASON_MISMATCH,
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


def test_blocking_codes_enumerates_independent_violations_in_frozen_order() -> None:
    raw = {**action_payload("respond"), "reply_to_event_id": "e_999999"}

    assert blocking_codes(raw, view(floor_owned=True)) == (
        LicenseBlockCode.UNKNOWN_REFERENCE,
        LicenseBlockCode.FLOOR_OWNED,
    )


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


@pytest.mark.parametrize("interval_ms", [999, 2_001])
def test_schedule_interval_must_fit_model_visible_session_capabilities(
    interval_ms: int,
) -> None:
    raw = {**action_payload("schedule"), "interval_ms": interval_ms}

    assert_blocked(
        raw,
        view(min_timer_interval_ms=1_000, max_timer_interval_ms=2_000),
        LicenseBlockCode.TIMER_LIMIT_EXCEEDED,
    )


def test_failed_result_is_not_integrable_but_can_warrant_one_failure_response() -> None:
    failed = ToolResultView(
        RESULT_EVENT_ID,
        "r_001",
        completed=True,
        status=ToolResultStatus.FAILED,
    )
    state = view(events=(failed,))

    assert_blocked(action_payload("integrate"), state, LicenseBlockCode.RESULT_NOT_READY)
    response = {
        **action_payload("respond"),
        "reply_to_event_id": RESULT_EVENT_ID,
        "text": "The lookup failed.",
    }
    assert_allowed(response, state)

    handled = ToolResultView(
        RESULT_EVENT_ID,
        "r_001",
        completed=True,
        status=ToolResultStatus.FAILED,
        disposition=Disposition.HANDLED,
    )
    assert_blocked(
        response,
        view(events=(handled,)),
        LicenseBlockCode.TARGET_ALREADY_HANDLED,
    )


def test_reserved_user_annotation_cannot_be_a_response_warrant() -> None:
    annotation = OtherEventView(
        event_id="e_000004",
        kind=LicenseEventKind.USER_ANNOTATION,
    )
    raw = {**action_payload("respond"), "reply_to_event_id": annotation.event_id}

    assert_blocked(
        raw,
        view(events=(annotation,)),
        LicenseBlockCode.UNKNOWN_REFERENCE,
    )


@pytest.mark.parametrize("reason", ["stale_tool_result", "superseded_query"])
def test_tool_skip_reasons_cannot_target_timer_fires(reason: str) -> None:
    raw = {"type": "skip", "target_event_id": FIRE_EVENT_ID, "reason": reason}

    assert_blocked(raw, view(), LicenseBlockCode.REASON_MISMATCH)


def test_canceled_timer_reason_requires_a_canceled_fire_timer() -> None:
    raw = {
        "type": "skip",
        "target_event_id": FIRE_EVENT_ID,
        "reason": "canceled_timer",
    }
    assert_blocked(raw, view(), LicenseBlockCode.REASON_MISMATCH)
    assert_allowed(raw, view(timers=(TimerView(TIMER_ID, TimerStatus.CANCELED),)))


def test_idle_referents_bind_to_pending_open_and_handled_subjects() -> None:
    awaiting_tool = {
        "type": "idle",
        "reason": "awaiting_tool",
        "related_event_id": CURRENT_SNAPSHOT_ID,
    }
    pending = PendingToolRequestView.from_args(
        "r_001",
        CURRENT_SNAPSHOT_ID,
        ToolName.LOOKUP,
        {"query": "weather"},
    )
    assert_allowed(awaiting_tool, view(pending_tool_requests=(pending,)))

    already_handled = {
        "type": "idle",
        "reason": "already_handled",
        "related_event_id": RESULT_EVENT_ID,
    }
    handled = ToolResultView(
        RESULT_EVENT_ID,
        "r_001",
        completed=True,
        status=ToolResultStatus.SUCCEEDED,
        disposition=Disposition.HANDLED,
    )
    assert_allowed(already_handled, view(events=(handled,)))
    assert_blocked(already_handled, view(), LicenseBlockCode.REASON_MISMATCH)


def test_multi_subject_idle_and_failed_response_tie_breaks_are_objective() -> None:
    older_pending = PendingToolRequestView.from_args(
        "r_002",
        "e_000010",
        ToolName.LOOKUP,
        {"query": "older"},
        policy_seq=10,
    )
    newer_pending = PendingToolRequestView.from_args(
        "r_001",
        "e_000011",
        ToolName.LOOKUP,
        {"query": "newer"},
        policy_seq=12,
    )
    awaiting_newer = {
        "type": "idle",
        "reason": "awaiting_tool",
        "related_event_id": newer_pending.fact_event_id,
    }
    awaiting_older = {**awaiting_newer, "related_event_id": older_pending.fact_event_id}
    pending_state = view(
        events=(
            SnapshotView(older_pending.fact_event_id, "older"),
            SnapshotView(newer_pending.fact_event_id, "newer"),
        ),
        pending_tool_requests=(newer_pending, older_pending),
    )
    assert_allowed(awaiting_older, pending_state)
    assert_blocked(awaiting_newer, pending_state, LicenseBlockCode.REASON_MISMATCH)

    older_failed = ToolResultView(
        "e_000020",
        "r_020",
        completed=True,
        status=ToolResultStatus.FAILED,
        policy_seq=20,
    )
    newer_failed = ToolResultView(
        "e_000021",
        "r_021",
        completed=True,
        status=ToolResultStatus.FAILED,
        policy_seq=21,
    )
    failed_state = view(events=(newer_failed, older_failed))
    assert_allowed(
        {"type": "respond", "reply_to_event_id": older_failed.event_id, "text": "failed"},
        failed_state,
    )
    assert_blocked(
        {"type": "respond", "reply_to_event_id": newer_failed.event_id, "text": "failed"},
        failed_state,
        LicenseBlockCode.REASON_MISMATCH,
    )


def test_already_handled_tie_break_ignores_checkpoint_hidden_history() -> None:
    hidden = ToolResultView(
        "e_000030",
        "r_030",
        completed=True,
        status=ToolResultStatus.SUCCEEDED,
        disposition=Disposition.HANDLED,
        policy_seq=3,
    )
    visible = ToolResultView(
        "e_000031",
        "r_031",
        completed=True,
        status=ToolResultStatus.SUCCEEDED,
        disposition=Disposition.HANDLED,
        policy_seq=31,
    )
    action = {
        "type": "idle",
        "reason": "already_handled",
        "related_event_id": visible.event_id,
    }

    assert_allowed(
        action,
        view(
            events=(hidden, visible),
            visible_handled_event_ids=frozenset({visible.event_id}),
        ),
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
