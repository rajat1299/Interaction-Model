"""Deterministic checkpoint projection and rollover continuity tests."""

from hashlib import sha256
from pathlib import Path

import pytest

from im.canonical_json import CANONICALIZER_ID, canonicalize_tim_json
from im.config import RuntimeConfig, estimate_tokens
from im.license import Allowed, Blocked, check
from im.policy.base import ScriptedPolicy
from im.rollover import ProjectionError, project, rollover, should_rollover
from im.scheduler import ManualClock, TimerScheduler
from im.schema.actions import (
    DelegateAction,
    IntegrateAction,
    MarkAction,
    RespondAction,
    ScheduleAction,
    SkipAction,
    SkipReason,
    Span,
)
from im.schema.common import Disposition, LicenseBlockCode
from im.schema.events import StateCheckpointEvent
from im.serialize import render_event
from im.store import PolicyEventDraft, Store
from im.tick import TickRuntime, build_license_view
from im.tools import ScriptedToolResult, ToolAdapter

DIGEST = "sha256:" + "1" * 64


def event_span(event_id: str, text: str, needle: str) -> Span:
    start = text.index(needle)
    return Span(
        event_id=event_id,
        start_utf16=start,
        end_utf16=start + len(needle),
        text=needle,
    )


def commit_event(
    store: Store,
    clock: ManualClock,
    *,
    source: str,
    kind: str,
    payload: object,
    activity: str | None = None,
) -> str:
    event_id = store.allocate_id("event")
    store.commit_policy(
        PolicyEventDraft(
            id=event_id,
            source=source,
            kind=kind,
            payload=payload,
            occurred_mono_ns=clock.monotonic_ns(),
            activity=activity,
        )
    )
    return event_id


def action_payload(action) -> dict[str, object]:
    return {"action": action.model_dump(mode="python")}


def set_hashes(store: Store) -> None:
    store.set_meta(
        "session_hashes",
        {
            "schema_hash": DIGEST,
            "spec_hash": DIGEST,
            "prompt_hash": DIGEST,
            "config_hash": DIGEST,
            "renderer_id": "serialize-v1",
            "canonicalizer_id": CANONICALIZER_ID,
        },
    )


def test_should_rollover_uses_exact_integer_permille_threshold() -> None:
    config = RuntimeConfig(context_budget_tokens=100, rollover_permille=720)

    assert not should_rollover(71, config)
    assert should_rollover(72, config)
    with pytest.raises(ValueError):
        should_rollover(-1, config)


def test_projection_is_byte_deterministic_for_identical_commit_facts(tmp_path: Path) -> None:
    store = Store(tmp_path / "deterministic.sqlite3")
    clock = ManualClock()
    try:
        snapshot_id = commit_event(
            store,
            clock,
            source="user",
            kind="snapshot",
            activity="paused",
            payload={
                "text": "hello",
                "selection_start_utf16": 5,
                "selection_end_utf16": 5,
                "is_composing": False,
                "edit_kind": "insert",
            },
        )
        set_hashes(store)
        seq = store.policy_records()[-1].seq + 1

        first = project(
            store,
            checkpoint_mono_ns=clock.monotonic_ns(),
            checkpoint_event_id="e_999999",
            checkpoint_seq=seq,
        )
        second = project(
            store,
            checkpoint_mono_ns=clock.monotonic_ns(),
            checkpoint_event_id="e_999999",
            checkpoint_seq=seq,
        )

        assert first == second
        assert first.snapshot.event_id == snapshot_id
        assert first.segment.previous_segment_hash == (
            f"sha256:{sha256(store.policy_bytes(0)).hexdigest()}"
        )
    finally:
        store.close()


def test_projection_drops_marks_that_cannot_target_the_latest_snapshot(tmp_path: Path) -> None:
    store = Store(tmp_path / "stale-mark.sqlite3")
    clock = ManualClock()
    try:
        first_id = commit_event(
            store,
            clock,
            source="user",
            kind="snapshot",
            activity="paused",
            payload={
                "text": "mark cat",
                "selection_start_utf16": 8,
                "selection_end_utf16": 8,
                "is_composing": False,
                "edit_kind": "insert",
            },
        )
        mark = MarkAction(
            type="mark",
            instruction=event_span(first_id, "mark cat", "mark"),
            target=event_span(first_id, "mark cat", "cat"),
        )
        commit_event(
            store, clock, source="model", kind="action_executed", payload=action_payload(mark)
        )
        commit_event(
            store,
            clock,
            source="user",
            kind="snapshot",
            activity="paused",
            payload={
                "text": "new text",
                "selection_start_utf16": 8,
                "selection_end_utf16": 8,
                "is_composing": False,
                "edit_kind": "replace",
            },
        )
        set_hashes(store)

        payload = project(
            store,
            checkpoint_mono_ns=clock.monotonic_ns(),
            checkpoint_event_id="e_999999",
            checkpoint_seq=store.policy_records()[-1].seq + 1,
        )

        assert payload.applied_marks == []
    finally:
        store.close()


def test_projection_retains_terminal_tombstone_only_for_retained_recent_action(
    tmp_path: Path,
) -> None:
    store = Store(tmp_path / "recent-tombstone.sqlite3")
    clock = ManualClock()
    try:
        commit_event(
            store,
            clock,
            source="user",
            kind="snapshot",
            activity="paused",
            payload={
                "text": "ready",
                "selection_start_utf16": 5,
                "selection_end_utf16": 5,
                "is_composing": False,
                "edit_kind": "insert",
            },
        )
        result_id = commit_event(
            store,
            clock,
            source="tool",
            kind="result",
            payload={"request_id": "r_999", "status": "succeeded", "data": {"answer": 1}},
        )
        store.set_disposition(result_id, Disposition.OPEN)
        integrate = IntegrateAction(type="integrate", result_event_id=result_id, text="one")
        action_event_id = commit_event(
            store,
            clock,
            source="model",
            kind="action_executed",
            payload=action_payload(integrate),
        )
        store.set_disposition(
            result_id,
            Disposition.HANDLED,
            by_action_event_id=action_event_id,
        )
        set_hashes(store)

        payload = project(
            store,
            checkpoint_mono_ns=clock.monotonic_ns(),
            checkpoint_event_id="e_999999",
            checkpoint_seq=store.policy_records()[-1].seq + 1,
        )

        assert [event.event_id for event in payload.recent_events] == [action_event_id]
        assert [(item.event_id, item.state) for item in payload.dispositions] == [
            (result_id, Disposition.HANDLED)
        ]
    finally:
        store.close()


def test_recent_tail_must_fit_both_its_budget_and_complete_checkpoint_reserve(
    tmp_path: Path,
) -> None:
    store = Store(tmp_path / "dual-budget.sqlite3")
    clock = ManualClock()
    try:
        snapshot_id = commit_event(
            store,
            clock,
            source="user",
            kind="snapshot",
            activity="paused",
            payload={
                "text": "ready",
                "selection_start_utf16": 5,
                "selection_end_utf16": 5,
                "is_composing": False,
                "edit_kind": "insert",
            },
        )
        respond = RespondAction(
            type="respond",
            reply_to_event_id=snapshot_id,
            text="retained only when both budgets allow it",
        )
        commit_event(
            store,
            clock,
            source="model",
            kind="action_executed",
            payload=action_payload(respond),
        )
        set_hashes(store)
        checkpoint_id = "e_999999"
        checkpoint_seq = store.policy_records()[-1].seq + 1
        mandatory = project(
            store,
            checkpoint_mono_ns=clock.monotonic_ns(),
            checkpoint_event_id=checkpoint_id,
            checkpoint_seq=checkpoint_seq,
            config=RuntimeConfig(
                checkpoint_reserved_tokens=10_000,
                recent_events_budget_tokens=1,
            ),
        )
        mandatory_rendered = render_event(
            {
                "v": 1,
                "id": checkpoint_id,
                "seq": checkpoint_seq,
                "dt_ms": 0,
                "source": "runtime",
                "kind": "state_checkpoint",
                "payload": mandatory.model_dump(mode="python"),
            }
        )
        mandatory_tokens = estimate_tokens(mandatory_rendered)

        tight = project(
            store,
            checkpoint_mono_ns=clock.monotonic_ns(),
            checkpoint_event_id=checkpoint_id,
            checkpoint_seq=checkpoint_seq,
            config=RuntimeConfig(
                checkpoint_reserved_tokens=mandatory_tokens,
                recent_events_budget_tokens=1_000,
            ),
        )

        assert mandatory.recent_events == []
        assert tight.recent_events == []
    finally:
        store.close()


@pytest.mark.gate
@pytest.mark.asyncio
async def test_double_rollover_continuity(tmp_path: Path) -> None:
    config = RuntimeConfig(
        checkpoint_reserved_tokens=4_000,
        recent_events_budget_tokens=120,
    )
    store = Store(tmp_path / "continuity.sqlite3")
    clock = ManualClock()
    scheduler = TimerScheduler(store, clock, config)
    tools = ToolAdapter(store, clock)
    text = "mark cat lookup pending lookup ready timer alpha timer beta"
    try:
        snapshot_id = commit_event(
            store,
            clock,
            source="user",
            kind="snapshot",
            activity="paused",
            payload={
                "text": text,
                "selection_start_utf16": len(text),
                "selection_end_utf16": len(text),
                "is_composing": False,
                "edit_kind": "insert",
            },
        )
        mark = MarkAction(
            type="mark",
            instruction=event_span(snapshot_id, text, "mark"),
            target=event_span(snapshot_id, text, "cat"),
        )
        mark_event_id = commit_event(
            store, clock, source="model", kind="action_executed", payload=action_payload(mark)
        )

        timer_a_action = ScheduleAction(
            type="schedule",
            instruction=event_span(snapshot_id, text, "timer alpha"),
            interval_ms=1_000,
            message="alpha",
        )
        timer_b_action = ScheduleAction(
            type="schedule",
            instruction=event_span(snapshot_id, text, "timer beta"),
            interval_ms=1_000,
            message="beta",
        )
        timer_a = scheduler.schedule(
            instruction_id=store.allocate_id("instruction"),
            instruction=timer_a_action.instruction,
            interval_ms=timer_a_action.interval_ms,
            message=timer_a_action.message,
        )
        timer_b = scheduler.schedule(
            instruction_id=store.allocate_id("instruction"),
            instruction=timer_b_action.instruction,
            interval_ms=timer_b_action.interval_ms,
            message=timer_b_action.message,
        )

        pending_action = DelegateAction(
            type="delegate",
            fact=event_span(snapshot_id, text, "lookup pending"),
            tool="lookup",
            args={"query": "pending"},
        )
        commit_event(
            store,
            clock,
            source="model",
            kind="action_executed",
            payload=action_payload(pending_action),
        )
        pending_request_id = tools.request(
            "lookup",
            {"query": "pending"},
            fact_event_id=snapshot_id,
            scripted_result=ScriptedToolResult(latency_ms=10_000, data={"pending": True}),
        )
        commit_event(
            store,
            clock,
            source="runtime",
            kind="tool_requested",
            payload={
                "request_id": pending_request_id,
                "tool": "lookup",
                "args": {"query": "pending"},
            },
        )

        ready_action = DelegateAction(
            type="delegate",
            fact=event_span(snapshot_id, text, "lookup ready"),
            tool="lookup",
            args={"query": "ready"},
        )
        commit_event(
            store,
            clock,
            source="model",
            kind="action_executed",
            payload=action_payload(ready_action),
        )
        ready_request_id = tools.request(
            "lookup",
            {"query": "ready"},
            fact_event_id=snapshot_id,
            scripted_result=ScriptedToolResult(latency_ms=0, data={"answer": 42}),
        )
        commit_event(
            store,
            clock,
            source="runtime",
            kind="tool_requested",
            payload={
                "request_id": ready_request_id,
                "tool": "lookup",
                "args": {"query": "ready"},
            },
        )
        ready_delivery = tools.deliver_due()[0]
        store.commit_policy(ready_delivery.as_policy_draft())
        store.set_disposition(ready_delivery.event_id, Disposition.OPEN)

        long_respond = RespondAction(
            type="respond",
            reply_to_event_id=snapshot_id,
            text="x" * 600,
        )
        commit_event(
            store,
            clock,
            source="model",
            kind="action_executed",
            payload=action_payload(long_respond),
        )
        historical_result_id = commit_event(
            store,
            clock,
            source="tool",
            kind="result",
            payload={"request_id": "r_999", "status": "succeeded", "data": {"old": True}},
        )
        store.set_disposition(historical_result_id, Disposition.OPEN)
        historical_integrate = IntegrateAction(
            type="integrate",
            result_event_id=historical_result_id,
            text="old result",
        )
        historical_integrate_id = commit_event(
            store,
            clock,
            source="model",
            kind="action_executed",
            payload=action_payload(historical_integrate),
        )
        store.set_disposition(
            historical_result_id,
            Disposition.HANDLED,
            by_action_event_id=historical_integrate_id,
        )

        clock.advance_ms(1_000)
        due = scheduler.claim_due()
        alpha_fire_before = next(fire for fire in due if fire.payload.timer_id == timer_a.timer_id)
        beta_fire = next(fire for fire in due if fire.payload.timer_id == timer_b.timer_id)
        store.commit_policy(alpha_fire_before.draft)
        store.set_disposition(alpha_fire_before.event_id, Disposition.OPEN)
        store.set_disposition(alpha_fire_before.event_id, Disposition.HANDLED)
        store.commit_policy(beta_fire.draft)
        store.set_disposition(beta_fire.event_id, Disposition.OPEN)
        scheduler.cancel((timer_b.timer_id,))
        set_hashes(store)

        first = rollover(store, checkpoint_mono_ns=clock.monotonic_ns(), config=config)
        segment_one_bytes = store.policy_bytes(1)
        clock.advance_ms(1)
        second = rollover(store, checkpoint_mono_ns=clock.monotonic_ns(), config=config)

        assert store.current_segment_index() == 2
        assert first.payload.segment.segment_index == 1
        assert second.payload.segment.segment_index == 2
        assert second.payload.segment.previous_segment_hash == (
            f"sha256:{sha256(segment_one_bytes).hexdigest()}"
        )
        assert second.payload.snapshot.event_id == snapshot_id
        assert [timer.timer_id for timer in second.payload.timers] == [
            timer_a.timer_id,
            timer_b.timer_id,
        ]
        assert second.payload.timers[1].status == "canceled"
        assert [item.event_id for item in second.payload.open_timer_fires] == [beta_fire.event_id]
        assert [item.event_id for item in second.payload.open_tool_results] == [
            ready_delivery.event_id
        ]
        assert [item.request_id for item in second.payload.pending_tools] == [pending_request_id]
        assert [item.mark_event_id for item in second.payload.applied_marks] == [mark_event_id]
        assert [item.event_id for item in second.payload.recent_events] == [historical_integrate_id]
        assert [(item.event_id, item.state) for item in second.payload.dispositions] == [
            (historical_result_id, Disposition.HANDLED)
        ]
        assert second.payload.timers[0].fire_count == 1
        checkpoint_event = store.policy_records(2)[0].event
        assert isinstance(checkpoint_event, StateCheckpointEvent)
        assert checkpoint_event.payload == second.payload

        view = build_license_view(store, config)
        integrate_after_rollover = IntegrateAction(
            type="integrate",
            result_event_id=ready_delivery.event_id,
            text="42",
        )
        skip_after_rollover = SkipAction(
            type="skip",
            target_event_id=beta_fire.event_id,
            reason=SkipReason.CANCELED_TIMER,
        )
        assert isinstance(check(integrate_after_rollover, view), Allowed)
        assert isinstance(check(skip_after_rollover, view), Allowed)
        duplicate_schedule = check(timer_a_action, view)
        assert duplicate_schedule == Blocked(LicenseBlockCode.DUPLICATE_SCHEDULE)
        repeated_mark = check(mark, view)
        assert repeated_mark == Blocked(LicenseBlockCode.TARGET_ALREADY_HANDLED)

        policy = ScriptedPolicy([integrate_after_rollover, skip_after_rollover])
        runtime = TickRuntime(
            store=store,
            policy=policy,
            scheduler=scheduler,
            tools=tools,
            clock=clock,
            config=config,
        )
        trigger_id = store.allocate_id("event")
        trigger_payload = {"text": "continue"}
        store.append_ingress(
            event_id=trigger_id,
            received_utc=clock.wall_utc().isoformat(),
            received_mono_ns=clock.monotonic_ns(),
            source="user",
            kind="annotation",
            payload=canonicalize_tim_json(trigger_payload),
        )
        runtime.enqueue_committed_ingress(
            PolicyEventDraft(
                id=trigger_id,
                source="user",
                kind="annotation",
                payload=trigger_payload,
                occurred_mono_ns=clock.monotonic_ns(),
            )
        )
        await runtime.run_until_idle()

        assert policy.call_count == 2
        assert store.get_disposition(ready_delivery.event_id).state is Disposition.HANDLED  # type: ignore[union-attr]
        assert store.get_disposition(beta_fire.event_id).state is Disposition.SKIPPED  # type: ignore[union-attr]

        clock.advance_ms(999)
        alpha_fire = scheduler.claim_due()
        assert len(alpha_fire) == 1
        assert alpha_fire[0].payload.timer_id == timer_a.timer_id
        assert alpha_fire[0].payload.fire_count == 2
    finally:
        store.close()


def test_projection_failure_rolls_back_event_id_and_segment_pointer(tmp_path: Path) -> None:
    store = Store(tmp_path / "budget.sqlite3")
    clock = ManualClock()
    try:
        commit_event(
            store,
            clock,
            source="user",
            kind="snapshot",
            activity="paused",
            payload={
                "text": "mandatory",
                "selection_start_utf16": 9,
                "selection_end_utf16": 9,
                "is_composing": False,
                "edit_kind": "insert",
            },
        )
        set_hashes(store)
        before_counter = store.get_meta("id_counter:event")

        with pytest.raises(ProjectionError, match="mandatory checkpoint state"):
            rollover(
                store,
                checkpoint_mono_ns=clock.monotonic_ns(),
                config=RuntimeConfig(checkpoint_reserved_tokens=1),
            )

        assert store.current_segment_index() == 0
        assert store.get_meta("id_counter:event") == before_counter
        assert len(store.policy_records()) == 1
        assert store._connection.execute(
            "SELECT kind FROM audit WHERE kind = 'checkpoint_failed'"
        ).fetchall() == [("checkpoint_failed",)]
    finally:
        store.close()
