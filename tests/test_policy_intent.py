"""Focused checks for Phase 3X intent resolution."""

import json
from hashlib import sha256

import pytest

from im.canonical_json import parse_tim_json
from im.license import (
    LicenseEventKind,
    LicenseView,
    OtherEventView,
    PendingToolRequestView,
    SnapshotView,
    TimerFireView,
    TimerView,
    ToolResultView,
)
from im.policy.intent import (
    IntentRegistry,
    LanguageRealizationRequest,
    ResolutionStatus,
    complete_language_realization,
    resolve_policy_intent,
)
from im.schema.actions import Span
from im.schema.common import (
    Activity,
    Disposition,
    TimerStatus,
    ToolName,
    ToolResultStatus,
)
from im.schema.events import ToolResultEvent
from im.schema.textspan import utf16_len
from im.serialize import render_event

REMINDER = "Remind me every five seconds to breathe."
CANCEL = "Cancel the breathing reminder."
TARGETS = "coral badger, coral badger, and coral badger"


def _span(event_id: str, text: str) -> Span:
    return Span(event_id=event_id, start_utf16=0, end_utf16=utf16_len(text), text=text)


def _view() -> LicenseView:
    reminder = SnapshotView("e_000001", REMINDER, policy_seq=1)
    targets = SnapshotView("e_000002", TARGETS, policy_seq=2)
    cancel = SnapshotView("e_000003", CANCEL, policy_seq=3, activity=Activity.PAUSED)
    succeeded = ToolResultView(
        "e_000004",
        "r_001",
        completed=True,
        status=ToolResultStatus.SUCCEEDED,
        disposition=Disposition.OPEN,
        policy_seq=4,
    )
    failed = ToolResultView(
        "e_000005",
        "r_002",
        completed=True,
        status=ToolResultStatus.FAILED,
        disposition=Disposition.OPEN,
        policy_seq=5,
    )
    fire = TimerFireView("e_000006", "t_001", disposition=Disposition.OPEN, policy_seq=6)
    timer = TimerView(
        "t_001",
        TimerStatus.ACTIVE,
        instruction=_span(reminder.event_id, REMINDER),
        current_instruction=_span(reminder.event_id, REMINDER),
        interval_ms=5_000,
        message="breathe",
    )
    return LicenseView(
        latest_snapshot=cancel,
        events=(reminder, targets, cancel, succeeded, failed, fire),
        timers=(timer,),
    )


def _registry() -> IntentRegistry:
    policy_bytes = _result_policy_bytes()
    return IntentRegistry.from_state(_view(), policy_bytes, sha256(policy_bytes).hexdigest())


def _result_policy_bytes() -> bytes:
    rows = [
        {
            "v": 1,
            "id": "e_000004",
            "seq": 4,
            "dt_ms": 0,
            "source": "tool",
            "kind": "result",
            "payload": {
                "request_id": "r_001",
                "status": "succeeded",
                "data": {"nonce": "n-42"},
            },
        },
        {
            "v": 1,
            "id": "e_000005",
            "seq": 5,
            "dt_ms": 0,
            "source": "tool",
            "kind": "result",
            "payload": {
                "request_id": "r_002",
                "status": "failed",
                "data": {"error": "offline"},
            },
        },
    ]
    return b"\n".join(render_event(ToolResultEvent.model_validate(row)) for row in rows)


def _action(payload: dict[str, object]):
    resolution = resolve_policy_intent(payload, _registry())
    assert resolution.status is ResolutionStatus.RESOLVED_ACTION
    assert resolution.value is not None
    return resolution.value


def test_registry_is_state_local_deterministic_and_committed_only() -> None:
    registry = _registry()

    assert [item.alias for item in registry.users] == ["u0", "u1", "u2"]
    assert [item.alias for item in registry.instructions] == ["i0"]
    assert registry.instructions[0].provenance_timer_ids == ("t_001",)
    assert [item.alias for item in registry.results] == ["r0", "r1"]
    assert registry.pending_facts == ()
    assert [item.alias for item in registry.timers] == ["t0"]
    assert [item.alias for item in registry.fires] == ["f0"]
    assert registry.source_state_sha256 == sha256(_result_policy_bytes()).hexdigest()
    policy_bytes = _result_policy_bytes()
    assert IntentRegistry.from_state(
        _view(), policy_bytes, sha256(policy_bytes).hexdigest()
    ).render() == registry.render()
    rendered = parse_tim_json(registry.render())
    assert rendered["version"] == "policy_intent_v1"
    assert rendered["registry_amendment"] == "pending_fact_and_disposition_v1"
    assert rendered["r"][0]["disposition"] == "open"
    assert rendered["f"][0]["disposition"] == "open"
    assert rendered["u"][0]["policy_seq"] == 1
    assert rendered["r"][0]["policy_seq"] == 4
    assert rendered["f"][0]["policy_seq"] == 6
    assert all(
        "already_handled_eligible" not in item and "latest" not in item
        for group in (rendered["u"], rendered["r"], rendered["f"])
        for item in group
    )


def test_registry_render_is_not_limited_to_one_event_envelope() -> None:
    snapshots = tuple(
        SnapshotView(f"e_{index:06d}", f"{index}:" + "x" * 3_000, policy_seq=index)
        for index in range(1, 9)
    )
    rendered = IntentRegistry.from_license_view(
        LicenseView(latest_snapshot=snapshots[-1], events=snapshots)
    ).render()

    assert len(rendered) > 16_384
    assert len(json.loads(rendered)["u"]) == 8


def test_pending_fact_alias_is_deterministic_and_idle_awaiting_tool_only() -> None:
    view = _view()
    pending = (
        PendingToolRequestView(
            "r_new", "e_000002", ToolName.LOOKUP, "lookup:new", policy_seq=12
        ),
        PendingToolRequestView(
            "r_old", "e_000001", ToolName.LOOKUP, "lookup:old", policy_seq=11
        ),
    )
    registry = IntentRegistry.from_license_view(
        LicenseView(
            latest_snapshot=view.latest_snapshot,
            events=view.events,
            timers=view.timers,
            pending_tool_requests=pending,
        )
    )

    assert [(item.alias, item.request_id) for item in registry.pending_facts] == [
        ("p0", "r_old"),
        ("p1", "r_new"),
    ]
    resolved = resolve_policy_intent(
        {"type": "idle", "reason": "awaiting_tool", "related": "p0"}, registry
    )
    assert resolved.status is ResolutionStatus.RESOLVED_ACTION
    assert resolved.value.related_event_id == "e_000001"
    assert resolve_policy_intent(
        {"type": "idle", "reason": "awaiting_tool", "related": "p1"}, registry
    ).status is ResolutionStatus.FAILED

    forbidden = [
        {
            "type": "mark",
            "instruction": {
                "kind": "visible",
                "source": "p0",
                "text": REMINDER,
                "occurrence": 0,
            },
            "source": "u1",
            "text": "coral badger",
            "occurrence": 0,
        },
        {"type": "delegate", "source": "p0", "query": REMINDER, "occurrence": 0},
        {
            "type": "schedule",
            "instruction": {"kind": "committed", "instruction": "p0"},
        },
        {
            "type": "cancel",
            "instruction": {"kind": "committed", "instruction": "i0"},
            "target": {"kind": "timer", "timer": "p0"},
        },
        {
            "type": "respond",
            "warrant": "p0",
            "response_kind": "ordinary_grounded_answer",
        },
        {"type": "skip", "target": "p0", "reason": "stale_tool_result"},
        {"type": "nudge", "fire": "p0"},
        {"type": "integrate", "result": "p0"},
    ]
    assert all(
        resolve_policy_intent(payload, registry).status is ResolutionStatus.FAILED
        for payload in forbidden
    )


def test_idle_related_aliases_are_reason_specific_and_license_ordered() -> None:
    registry = _registry()
    assert resolve_policy_intent(
        {"type": "idle", "reason": "awaiting_opening", "related": "r0"}, registry
    ).status is ResolutionStatus.RESOLVED_ACTION
    for related in ("r1", "u2", None):
        assert resolve_policy_intent(
            {"type": "idle", "reason": "awaiting_opening", "related": related}, registry
        ).status is ResolutionStatus.FAILED

    snapshots = _view().events[:3]
    snapshot_registry = IntentRegistry.from_license_view(
        LicenseView(latest_snapshot=snapshots[-1], events=snapshots)
    )
    assert resolve_policy_intent(
        {"type": "idle", "reason": "awaiting_opening", "related": "u2"},
        snapshot_registry,
    ).status is ResolutionStatus.RESOLVED_ACTION
    assert resolve_policy_intent(
        {"type": "idle", "reason": "awaiting_opening", "related": "u1"},
        snapshot_registry,
    ).status is ResolutionStatus.FAILED
    assert resolve_policy_intent(
        {"type": "idle", "reason": "no_trigger", "related": "u2"}, snapshot_registry
    ).status is ResolutionStatus.FAILED

    handled_user = SnapshotView("e_200000", "Answered.", policy_seq=1, responded_to=True)
    handled_registry = IntentRegistry.from_license_view(
        LicenseView(latest_snapshot=handled_user, events=(handled_user,))
    )
    assert resolve_policy_intent(
        {"type": "idle", "reason": "already_handled", "related": "u0"},
        handled_registry,
    ).status is ResolutionStatus.RESOLVED_ACTION
    assert resolve_policy_intent(
        {
            "type": "respond",
            "warrant": "u0",
            "response_kind": "ordinary_grounded_answer",
        },
        handled_registry,
    ).status is ResolutionStatus.FAILED


@pytest.mark.parametrize("kind", ["result", "fire"])
def test_handled_result_or_fire_only_resolves_oldest_already_handled(kind: str) -> None:
    snapshot = SnapshotView("e_100000", "Done.", policy_seq=1)
    result = ToolResultView(
        "e_100001",
        "r_100",
        completed=True,
        status=ToolResultStatus.SUCCEEDED,
        disposition=Disposition.HANDLED,
        policy_seq=2,
    )
    timer = TimerView("t_100", TimerStatus.ACTIVE)
    fire = TimerFireView(
        "e_100002", "t_100", disposition=Disposition.SKIPPED, policy_seq=2
    )
    event = result if kind == "result" else fire
    registry = IntentRegistry.from_license_view(
        LicenseView(latest_snapshot=snapshot, events=(snapshot, event), timers=(timer,))
    )
    alias = "r0" if kind == "result" else "f0"

    resolved = resolve_policy_intent(
        {"type": "idle", "reason": "already_handled", "related": alias}, registry
    )
    assert resolved.status is ResolutionStatus.RESOLVED_ACTION
    assert resolved.value.related_event_id == event.event_id
    assert resolve_policy_intent(
        {"type": "idle", "reason": "awaiting_opening", "related": alias}, registry
    ).status is ResolutionStatus.FAILED
    executable = (
        [
            {"type": "integrate", "result": alias},
            {
                "type": "respond",
                "warrant": alias,
                "response_kind": "failed_result_notice",
            },
            {"type": "skip", "target": alias, "reason": "stale_tool_result"},
        ]
        if kind == "result"
        else [
            {"type": "nudge", "fire": alias},
            {"type": "skip", "target": alias, "reason": "canceled_timer"},
        ]
    )
    assert all(
        resolve_policy_intent(payload, registry).status is ResolutionStatus.FAILED
        for payload in executable
    )


def test_all_addressable_results_are_aliased_but_incomplete_execution_fails() -> None:
    snapshot = SnapshotView("e_300000", "Wait.", policy_seq=1)
    incomplete = ToolResultView(
        "e_300001",
        "r_300",
        completed=False,
        status=ToolResultStatus.SUCCEEDED,
        disposition=Disposition.OPEN,
        policy_seq=2,
    )
    registry = IntentRegistry.from_license_view(
        LicenseView(latest_snapshot=snapshot, events=(snapshot, incomplete))
    )

    assert [(item.alias, item.completed) for item in registry.results] == [("r0", False)]
    assert resolve_policy_intent(
        {"type": "integrate", "result": "r0"}, registry
    ).status is ResolutionStatus.FAILED
    assert resolve_policy_intent(
        {"type": "idle", "reason": "awaiting_opening", "related": "u0"}, registry
    ).status is ResolutionStatus.RESOLVED_ACTION


def test_unrepresentable_oldest_handled_event_forces_idle_failure() -> None:
    hidden_winner = OtherEventView(
        "e_400000",
        LicenseEventKind.MODEL_ACTION_EXECUTED,
        disposition=Disposition.HANDLED,
        policy_seq=1,
    )
    handled_result = ToolResultView(
        "e_400001",
        "r_400",
        completed=True,
        status=ToolResultStatus.SUCCEEDED,
        disposition=Disposition.HANDLED,
        policy_seq=2,
    )
    snapshot = SnapshotView("e_400002", "Done.", policy_seq=3)
    registry = IntentRegistry.from_license_view(
        LicenseView(
            latest_snapshot=snapshot,
            events=(hidden_winner, handled_result, snapshot),
        )
    )

    assert not registry.results[0].already_handled_eligible
    assert resolve_policy_intent(
        {"type": "idle", "reason": "already_handled", "related": "r0"}, registry
    ).status is ResolutionStatus.FAILED


@pytest.mark.parametrize(
    "raw",
    [
        '{"type":"idle","reason":"no_trigger","related":null}',
        b'{"type":"idle","reason":"no_trigger","related":null}',
        bytearray(b'{"type":"idle","reason":"no_trigger","related":null}'),
        memoryview(b'{"type":"idle","reason":"no_trigger","related":null}'),
    ],
)
def test_raw_model_json_resolves_through_strict_tim_json(raw: object) -> None:
    resolution = resolve_policy_intent(raw, _registry())

    assert resolution.status is ResolutionStatus.RESOLVED_ACTION
    assert resolution.value.type == "idle"


@pytest.mark.parametrize(
    "raw",
    [
        b'{"type":',
        b'{"type":"idle","reason":"no_trigger","related":null}garbage',
        b'{"type":"idle","reason":"no_trigger","related":null}{}',
        b'{"type":"idle","type":"idle","reason":"no_trigger","related":null}',
        b'{"type":"idle","reason":"no_trigger","related":null,"extra":1}',
        b'{"type":"idle","reason":"no_trigger","related":null}<|im_end|>',
    ],
)
def test_raw_model_json_is_not_repaired_or_transport_cleaned(raw: bytes) -> None:
    resolution = resolve_policy_intent(raw, _registry())

    assert resolution.status is ResolutionStatus.FAILED
    assert resolution.value is None


def test_all_nine_intents_resolve_without_changing_public_union() -> None:
    actions = [
        _action({"type": "idle", "reason": "no_trigger", "related": None}),
        _action(
            {
                "type": "mark",
                "instruction": {
                    "kind": "visible",
                    "source": "u0",
                    "text": REMINDER,
                    "occurrence": 0,
                },
                "source": "u1",
                "text": "coral badger",
                "occurrence": 1,
            }
        ),
        _action({"type": "delegate", "source": "u1", "query": "coral badger", "occurrence": 2}),
        _action({"type": "skip", "target": "r0", "reason": "stale_tool_result"}),
        _action(
            {
                "type": "schedule",
                "instruction": {"kind": "committed", "instruction": "i0"},
            }
        ),
        _action(
            {
                "type": "cancel",
                "instruction": {
                    "kind": "visible",
                    "source": "u2",
                    "text": CANCEL,
                    "occurrence": 0,
                },
                "target": {"kind": "timer", "timer": "t0"},
            }
        ),
        _action({"type": "nudge", "fire": "f0"}),
    ]
    integrate = resolve_policy_intent({"type": "integrate", "result": "r0"}, _registry())
    respond = resolve_policy_intent(
        {"type": "respond", "warrant": "u2", "response_kind": "clarification"},
        _registry(),
    )
    assert isinstance(integrate.value, LanguageRealizationRequest)
    assert isinstance(respond.value, LanguageRealizationRequest)
    actions.extend(
        [
            complete_language_realization(integrate.value, "The nonce is n-42.").value,
            complete_language_realization(respond.value, "Which reminder?").value,
        ]
    )

    assert {action.type for action in actions if action is not None} == {
        "idle",
        "mark",
        "delegate",
        "integrate",
        "skip",
        "respond",
        "schedule",
        "cancel",
        "nudge",
    }
    mark = actions[1]
    assert mark.target.start_utf16 == utf16_len("coral badger, ")
    assert mark.target.text == "coral badger"
    schedule = actions[4]
    assert (schedule.interval_ms, schedule.message) == (5_000, "breathe")


def test_language_requests_lock_provenance_and_integrate_is_canonically_grounded() -> None:
    integrate = resolve_policy_intent({"type": "integrate", "result": "r0"}, _registry())
    assert integrate.status is ResolutionStatus.LANGUAGE_REQUIRED
    assert integrate.value == LanguageRealizationRequest(
        "integrate",
        "e_000004",
        "result_integration",
        canonical_fallback='{"nonce":"n-42"}',
    )

    fallback = complete_language_realization(integrate.value, None)
    assert fallback.status is ResolutionStatus.CANONICAL_FALLBACK
    assert fallback.value.result_event_id == "e_000004"
    assert fallback.value.text == '{"nonce":"n-42"}'

    contradictory = complete_language_realization(
        integrate.value, "The nonce is definitely not n-42; it is invented."
    )
    assert contradictory.status is ResolutionStatus.CANONICAL_FALLBACK
    assert contradictory.value.result_event_id == "e_000004"
    assert contradictory.value.text == '{"nonce":"n-42"}'

    respond = resolve_policy_intent(
        {"type": "respond", "warrant": "u2", "response_kind": "clarification"},
        _registry(),
    )
    assert complete_language_realization(respond.value, None).status is ResolutionStatus.FAILED


@pytest.mark.parametrize(
    "payload",
    [
        {"type": "delegate", "source": "r0", "query": "coral badger", "occurrence": 0},
        {"type": "delegate", "source": "u1", "query": "coral badger", "occurrence": 3},
        {"type": "delegate", "source": "u1", "query": "oral", "occurrence": 0},
        {"type": "delegate", "source": "u1", "query": " coral badger", "occurrence": 0},
        {
            "type": "schedule",
            "instruction": {"kind": "committed", "instruction": "i1"},
        },
        {"type": "integrate", "result": "r1"},
        {"type": "respond", "warrant": "r0", "response_kind": "failed_result_notice"},
        {"type": "respond", "warrant": "u2", "response_kind": "failed_result_notice"},
        {"type": "skip", "target": "t0", "reason": "canceled_timer"},
        {"type": "skip", "target": "u0", "reason": "stale_tool_result"},
        {"type": "skip", "target": "r0", "reason": "canceled_timer"},
        {"type": "nudge", "fire": "t0"},
    ],
)
def test_invalid_ambiguous_or_wrong_kind_inputs_fail_closed(payload: dict[str, object]) -> None:
    resolution = resolve_policy_intent(payload, _registry())

    assert resolution.status is ResolutionStatus.FAILED
    assert resolution.value is None


def test_registry_rejects_unproved_instruction_spans() -> None:
    view = _view()
    timer = view.timers[0]
    broken = TimerView(
        timer.timer_id,
        timer.status,
        instruction=Span(
            event_id="e_000001",
            start_utf16=0,
            end_utf16=utf16_len("Remind"),
            text="Ignore",
        ),
    )
    with pytest.raises(ValueError, match="span text"):
        IntentRegistry.from_license_view(
            LicenseView(latest_snapshot=view.latest_snapshot, events=view.events, timers=(broken,)),
        )


def test_from_state_derives_result_fallback_only_from_committed_event_bytes() -> None:
    event = ToolResultEvent.model_validate(
        {
            "v": 1,
            "id": "e_000004",
            "seq": 4,
            "dt_ms": 0,
            "source": "tool",
            "kind": "result",
            "payload": {"request_id": "r_001", "status": "succeeded", "data": {"nonce": "n-42"}},
        }
    )
    event_bytes = render_event(event)
    registry = IntentRegistry.from_state(
        _view(), event_bytes, sha256(event_bytes).hexdigest()
    )

    assert registry.results[0].canonical_fallback == '{"nonce":"n-42"}'
    assert registry.results[1].canonical_fallback is None
    assert resolve_policy_intent(
        {"type": "integrate", "result": "r0"}, IntentRegistry.from_license_view(_view())
    ).status is ResolutionStatus.FAILED

    conflicting = event.model_copy(
        update={
            "payload": event.payload.model_copy(update={"status": ToolResultStatus.FAILED})
        }
    )
    conflicting_bytes = render_event(conflicting)
    with pytest.raises(ValueError, match="conflicts with runtime state"):
        IntentRegistry.from_state(
            _view(), conflicting_bytes, sha256(conflicting_bytes).hexdigest()
        )
    with pytest.raises(ValueError, match="checksum mismatch"):
        IntentRegistry.from_state(_view(), event_bytes, "0" * 64)


def test_nudge_rejects_open_fire_for_inactive_timer() -> None:
    view = _view()
    timer = view.timers[0]
    canceled = TimerView(
        timer.timer_id,
        TimerStatus.CANCELED,
        instruction=timer.instruction,
        current_instruction=timer.current_instruction,
        interval_ms=timer.interval_ms,
        message=timer.message,
    )
    registry = IntentRegistry.from_license_view(
        LicenseView(latest_snapshot=view.latest_snapshot, events=view.events, timers=(canceled,))
    )

    assert resolve_policy_intent({"type": "nudge", "fire": "f0"}, registry).status is (
        ResolutionStatus.FAILED
    )
    assert resolve_policy_intent(
        {"type": "skip", "target": "f0", "reason": "canceled_timer"}, registry
    ).status is ResolutionStatus.RESOLVED_ACTION
    assert resolve_policy_intent(
        {
            "type": "cancel",
            "instruction": {
                "kind": "visible",
                "source": "u2",
                "text": CANCEL,
                "occurrence": 0,
            },
            "target": {"kind": "all_active"},
        },
        registry,
    ).status is ResolutionStatus.FAILED


def test_multi_cancel_uses_numeric_alias_order_and_canonical_timer_order() -> None:
    view = _view()
    timer = view.timers[0]
    timers = tuple(
        TimerView(
            f"t_{index:03d}",
            TimerStatus.ACTIVE,
            instruction=timer.instruction,
            current_instruction=timer.current_instruction,
            interval_ms=timer.interval_ms,
            message=timer.message,
        )
        for index in range(11)
    )
    registry = IntentRegistry.from_license_view(
        LicenseView(latest_snapshot=view.latest_snapshot, events=view.events, timers=timers)
    )
    resolution = resolve_policy_intent(
        {
            "type": "cancel",
            "instruction": {"kind": "committed", "instruction": "i0"},
            "target": {"kind": "timers", "timers": ["t2", "t10"]},
        },
        registry,
    )

    assert resolution.status is ResolutionStatus.RESOLVED_ACTION
    assert resolution.value.target.timer_ids == ["t_002", "t_010"]


def test_visible_occurrence_offsets_are_exact_utf16() -> None:
    text = "🙂 coral 🙂"
    snapshot = SnapshotView("e_000010", text, policy_seq=1)
    registry = IntentRegistry.from_license_view(
        LicenseView(latest_snapshot=snapshot, events=(snapshot,), timers=())
    )

    resolution = resolve_policy_intent(
        {"type": "delegate", "source": "u0", "query": "🙂", "occurrence": 1}, registry
    )

    assert resolution.status is ResolutionStatus.RESOLVED_ACTION
    assert resolution.value.fact.start_utf16 == utf16_len("🙂 coral ")
    assert resolution.value.fact.end_utf16 == utf16_len(text)


@pytest.mark.parametrize("text", [None, "", " \t"])
def test_unavailable_language_fails_respond_and_falls_back_for_integrate(
    text: str | None,
) -> None:
    registry = _registry()
    respond = resolve_policy_intent(
        {"type": "respond", "warrant": "u2", "response_kind": "clarification"},
        registry,
    )
    integrate = resolve_policy_intent({"type": "integrate", "result": "r0"}, registry)

    assert complete_language_realization(respond.value, text).status is ResolutionStatus.FAILED
    assert complete_language_realization(integrate.value, text).status is (
        ResolutionStatus.CANONICAL_FALLBACK
    )
