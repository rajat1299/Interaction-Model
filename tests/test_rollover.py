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
    IdleAction,
    IdleReason,
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


def commit_pending_lookup(
    store: Store,
    clock: ManualClock,
    tools: ToolAdapter,
    *,
    fact_event_id: str,
    fact_text: str,
    query: str,
    ledger_fact_event_id: str | None = None,
) -> str:
    action = DelegateAction(
        type="delegate",
        fact=event_span(fact_event_id, fact_text, fact_text),
        tool="lookup",
        args={"query": query},
    )
    commit_event(
        store,
        clock,
        source="model",
        kind="action_executed",
        payload=action_payload(action),
    )
    request_id = tools.request(
        "lookup",
        {"query": query},
        fact_event_id=ledger_fact_event_id or fact_event_id,
        scripted_result=ScriptedToolResult(latency_ms=10_000, data={"query": query}),
    )
    commit_event(
        store,
        clock,
        source="runtime",
        kind="tool_requested",
        payload={"request_id": request_id, "tool": "lookup", "args": {"query": query}},
    )
    return request_id


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
        assert payload.ambiguous_marks == []
    finally:
        store.close()


def test_surviving_mark_target_is_projected_and_deduplicated_after_rollover(
    tmp_path: Path,
) -> None:
    store = Store(tmp_path / "surviving-mark.sqlite3")
    clock = ManualClock()
    try:
        text = "mark cat"
        first_id = commit_event(
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
            instruction=event_span(first_id, text, "mark"),
            target=event_span(first_id, text, "cat"),
        )
        mark_event_id = commit_event(
            store,
            clock,
            source="model",
            kind="action_executed",
            payload=action_payload(mark),
        )
        second_id = commit_event(
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
                "edit_kind": "none",
            },
        )
        set_hashes(store)

        checkpoint = rollover(store, checkpoint_mono_ns=clock.monotonic_ns())

        assert len(checkpoint.payload.applied_marks) == 1
        projected = checkpoint.payload.applied_marks[0]
        assert projected.mark_event_id == mark_event_id
        assert projected.target.event_id == second_id
        repeated = MarkAction(
            type="mark",
            instruction=event_span(second_id, text, "mark"),
            target=event_span(second_id, text, "cat"),
        )
        assert check(repeated, build_license_view(store, RuntimeConfig())) == Blocked(
            LicenseBlockCode.TARGET_ALREADY_HANDLED
        )
    finally:
        store.close()


def test_ambiguous_mark_identity_survives_repeated_rollover_as_tombstone(
    tmp_path: Path,
) -> None:
    store = Store(tmp_path / "ambiguous-mark.sqlite3")
    clock = ManualClock()
    try:
        original = "mark aaa"
        first_id = commit_event(
            store,
            clock,
            source="user",
            kind="snapshot",
            activity="paused",
            payload={
                "text": original,
                "selection_start_utf16": len(original),
                "selection_end_utf16": len(original),
                "is_composing": False,
                "edit_kind": "insert",
            },
        )
        mark = MarkAction(
            type="mark",
            instruction=event_span(first_id, original, "mark"),
            target=Span(
                event_id=first_id,
                start_utf16=6,
                end_utf16=8,
                text="aa",
            ),
        )
        mark_event_id = commit_event(
            store,
            clock,
            source="model",
            kind="action_executed",
            payload=action_payload(mark),
        )
        revised = "mark aa dog"
        revised_id = commit_event(
            store,
            clock,
            source="user",
            kind="snapshot",
            activity="paused",
            payload={
                "text": revised,
                "selection_start_utf16": len(revised),
                "selection_end_utf16": len(revised),
                "is_composing": False,
                "edit_kind": "replace",
            },
        )
        set_hashes(store)

        first = rollover(store, checkpoint_mono_ns=clock.monotonic_ns())
        clock.advance_ms(1)
        second = rollover(store, checkpoint_mono_ns=clock.monotonic_ns())

        for checkpoint in (first, second):
            assert checkpoint.payload.applied_marks == []
            assert len(checkpoint.payload.ambiguous_marks) == 1
            ambiguous = checkpoint.payload.ambiguous_marks[0]
            assert ambiguous.mark_event_id == mark_event_id
            assert [target.event_id for target in ambiguous.targets] == [revised_id]
            assert [target.text for target in ambiguous.targets] == ["aa"]

        repeated_ambiguous = MarkAction(
            type="mark",
            instruction=event_span(revised_id, revised, "mark"),
            target=event_span(revised_id, revised, "aa"),
        )
        unrelated = MarkAction(
            type="mark",
            instruction=event_span(revised_id, revised, "mark"),
            target=event_span(revised_id, revised, "dog"),
        )
        view = build_license_view(store, RuntimeConfig())
        assert check(repeated_ambiguous, view) == Blocked(
            LicenseBlockCode.TARGET_ALREADY_HANDLED
        )
        assert isinstance(check(unrelated, view), Allowed)
    finally:
        store.close()


def test_mark_tombstone_does_not_resurrect_after_text_disappears(
    tmp_path: Path,
) -> None:
    store = Store(tmp_path / "expired-ambiguous-mark.sqlite3")
    clock = ManualClock()
    try:
        original = "mark cat"
        first_id = commit_event(
            store,
            clock,
            source="user",
            kind="snapshot",
            activity="paused",
            payload={
                "text": original,
                "selection_start_utf16": len(original),
                "selection_end_utf16": len(original),
                "is_composing": False,
                "edit_kind": "insert",
            },
        )
        mark = MarkAction(
            type="mark",
            instruction=event_span(first_id, original, "mark"),
            target=event_span(first_id, original, "cat"),
        )
        commit_event(
            store,
            clock,
            source="model",
            kind="action_executed",
            payload=action_payload(mark),
        )
        commit_event(
            store,
            clock,
            source="user",
            kind="snapshot",
            activity="paused",
            payload={
                "text": "dog",
                "selection_start_utf16": 3,
                "selection_end_utf16": 3,
                "is_composing": False,
                "edit_kind": "replace",
            },
        )
        set_hashes(store)

        first = rollover(store, checkpoint_mono_ns=clock.monotonic_ns())
        assert first.payload.applied_marks == []
        assert first.payload.ambiguous_marks == []

        clock.advance_ms(1)
        commit_event(
            store,
            clock,
            source="user",
            kind="snapshot",
            activity="paused",
            payload={
                "text": "cat",
                "selection_start_utf16": 3,
                "selection_end_utf16": 3,
                "is_composing": False,
                "edit_kind": "replace",
            },
        )
        second = rollover(store, checkpoint_mono_ns=clock.monotonic_ns())

        assert second.payload.applied_marks == []
        assert second.payload.ambiguous_marks == []
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


def test_already_handled_selection_uses_only_checkpoint_visible_dispositions(
    tmp_path: Path,
) -> None:
    store = Store(tmp_path / "visible-disposition.sqlite3")
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
        handled: list[tuple[str, str]] = []
        for request_id, answer in (("r_998", "old"), ("r_999", "new")):
            result_id = commit_event(
                store,
                clock,
                source="tool",
                kind="result",
                payload={
                    "request_id": request_id,
                    "status": "succeeded",
                    "data": {"answer": answer},
                },
            )
            store.set_disposition(result_id, Disposition.OPEN)
            action = IntegrateAction(
                type="integrate",
                result_event_id=result_id,
                text=answer,
            )
            action_event_id = commit_event(
                store,
                clock,
                source="model",
                kind="action_executed",
                payload=action_payload(action),
            )
            store.set_disposition(
                result_id,
                Disposition.HANDLED,
                by_action_event_id=action_event_id,
            )
            handled.append((result_id, action_event_id))
        set_hashes(store)
        latest_action = next(
            record for record in store.policy_records() if record.event.id == handled[-1][1]
        )
        config = RuntimeConfig(
            checkpoint_reserved_tokens=4_000,
            recent_events_budget_tokens=estimate_tokens(
                latest_action.rendered,
                RuntimeConfig().len_estimator_id,
            ),
        )

        checkpoint = rollover(store, checkpoint_mono_ns=clock.monotonic_ns(), config=config)

        assert [item.event_id for item in checkpoint.payload.dispositions] == [handled[-1][0]]
        action = IdleAction(
            type="idle",
            reason=IdleReason.ALREADY_HANDLED,
            related_event_id=handled[-1][0],
        )
        assert isinstance(check(action, build_license_view(store, config)), Allowed)
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


def test_two_pending_fact_identities_survive_two_rollovers_in_request_order(
    tmp_path: Path,
) -> None:
    store = Store(tmp_path / "pending-provenance.sqlite3")
    clock = ManualClock()
    tools = ToolAdapter(store, clock)
    try:
        first_fact_event_id = commit_event(
            store,
            clock,
            source="user",
            kind="snapshot",
            activity="paused",
            payload={
                "text": "same fact",
                "selection_start_utf16": 9,
                "selection_end_utf16": 9,
                "is_composing": False,
                "edit_kind": "insert",
            },
        )
        first_request_id = commit_pending_lookup(
            store,
            clock,
            tools,
            fact_event_id=first_fact_event_id,
            fact_text="same fact",
            query="alpha",
        )
        second_fact_event_id = commit_event(
            store,
            clock,
            source="user",
            kind="snapshot",
            activity="paused",
            payload={
                "text": "same fact",
                "selection_start_utf16": 9,
                "selection_end_utf16": 9,
                "is_composing": False,
                "edit_kind": "replace",
            },
        )
        second_request_id = commit_pending_lookup(
            store,
            clock,
            tools,
            fact_event_id=second_fact_event_id,
            fact_text="same fact",
            query="beta",
        )
        set_hashes(store)

        first = rollover(
            store,
            checkpoint_mono_ns=clock.monotonic_ns(),
            config=RuntimeConfig(checkpoint_reserved_tokens=4_000),
        )
        clock.advance_ms(1)
        second = rollover(
            store,
            checkpoint_mono_ns=clock.monotonic_ns(),
            config=RuntimeConfig(checkpoint_reserved_tokens=4_000),
        )

        expected = [
            (first_request_id, first_fact_event_id, "same fact"),
            (second_request_id, second_fact_event_id, "same fact"),
        ]
        assert [
            (item.request_id, item.fact_event_id, item.fact_text)
            for item in first.payload.pending_tools
        ] == expected
        assert [
            (item.request_id, item.fact_event_id, item.fact_text)
            for item in second.payload.pending_tools
        ] == expected
    finally:
        store.close()


def test_projection_rejects_tool_ledger_fact_provenance_disagreement(tmp_path: Path) -> None:
    store = Store(tmp_path / "pending-provenance-mismatch.sqlite3")
    clock = ManualClock()
    tools = ToolAdapter(store, clock)
    try:
        fact_event_id = commit_event(
            store,
            clock,
            source="user",
            kind="snapshot",
            activity="paused",
            payload={
                "text": "lookup this",
                "selection_start_utf16": 11,
                "selection_end_utf16": 11,
                "is_composing": False,
                "edit_kind": "insert",
            },
        )
        commit_pending_lookup(
            store,
            clock,
            tools,
            fact_event_id=fact_event_id,
            fact_text="lookup this",
            query="mismatch",
            ledger_fact_event_id="e_999998",
        )
        set_hashes(store)

        with pytest.raises(ProjectionError, match="provenance disagrees"):
            project(
                store,
                checkpoint_mono_ns=clock.monotonic_ns(),
                checkpoint_event_id="e_999999",
                checkpoint_seq=store.policy_records()[-1].seq + 1,
            )
    finally:
        store.close()


def test_canceled_schedule_prior_use_remains_visible_across_rollover(tmp_path: Path) -> None:
    config = RuntimeConfig(checkpoint_reserved_tokens=4_000)
    store = Store(tmp_path / "schedule-prior-use.sqlite3")
    clock = ManualClock()
    scheduler = TimerScheduler(store, clock, config)
    text = "remind me every second to stretch"
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
        action = ScheduleAction(
            type="schedule",
            instruction=event_span(snapshot_id, text, text),
            interval_ms=1_000,
            message="stretch",
        )
        action_event_id = commit_event(
            store,
            clock,
            source="model",
            kind="action_executed",
            payload=action_payload(action),
        )
        timer = scheduler.schedule(
            instruction_id=store.allocate_id("instruction"),
            instruction=action.instruction,
            interval_ms=action.interval_ms,
            message=action.message,
        )
        scheduler.cancel((timer.timer_id,))
        set_hashes(store)

        first = rollover(store, checkpoint_mono_ns=clock.monotonic_ns(), config=config)
        clock.advance_ms(1)
        second = rollover(store, checkpoint_mono_ns=clock.monotonic_ns(), config=config)

        for payload in (first.payload, second.payload):
            assert [item.action_event_id for item in payload.prior_uses] == [action_event_id]
            prior_use = payload.prior_uses[0]
            assert prior_use.kind == "schedule"
            assert prior_use.instruction == action.instruction
            assert prior_use.timer_id == timer.timer_id
            assert prior_use.timer_status == "canceled"
        assert check(action, build_license_view(store, config)) == Blocked(
            LicenseBlockCode.DUPLICATE_SCHEDULE
        )
        newer_text = "a genuinely new request"
        commit_event(
            store,
            clock,
            source="user",
            kind="snapshot",
            activity="paused",
            payload={
                "text": newer_text,
                "selection_start_utf16": len(newer_text),
                "selection_end_utf16": len(newer_text),
                "is_composing": False,
                "edit_kind": "replace",
            },
        )
        third = rollover(store, checkpoint_mono_ns=clock.monotonic_ns(), config=config)
        assert third.payload.prior_uses == []
        assert check(action, build_license_view(store, config)) == Blocked(
            LicenseBlockCode.UNKNOWN_REFERENCE
        )
    finally:
        store.close()


def test_completed_lookup_prior_use_is_mandatory_without_recent_events(tmp_path: Path) -> None:
    config = RuntimeConfig(
        checkpoint_reserved_tokens=4_000,
        recent_events_budget_tokens=1,
    )
    store = Store(tmp_path / "lookup-prior-use.sqlite3")
    clock = ManualClock()
    tools = ToolAdapter(store, clock)
    text = "look up nonce"
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
        delegate = DelegateAction(
            type="delegate",
            fact=event_span(snapshot_id, text, text),
            tool="lookup",
            args={"query": "nonce"},
        )
        delegate_event_id = commit_event(
            store,
            clock,
            source="model",
            kind="action_executed",
            payload=action_payload(delegate),
        )
        request_id = tools.request(
            "lookup",
            {"query": "nonce"},
            fact_event_id=snapshot_id,
            scripted_result=ScriptedToolResult(latency_ms=0, data={"nonce": "n-1"}),
        )
        commit_event(
            store,
            clock,
            source="runtime",
            kind="tool_requested",
            payload={"request_id": request_id, "tool": "lookup", "args": {"query": "nonce"}},
        )
        delivery = tools.deliver_due()[0]
        store.commit_policy(delivery.as_policy_draft())
        store.set_disposition(delivery.event_id, Disposition.OPEN)
        integrate = IntegrateAction(
            type="integrate",
            result_event_id=delivery.event_id,
            text="n-1",
        )
        integrate_event_id = commit_event(
            store,
            clock,
            source="model",
            kind="action_executed",
            payload=action_payload(integrate),
        )
        store.set_disposition(
            delivery.event_id,
            Disposition.HANDLED,
            by_action_event_id=integrate_event_id,
        )
        set_hashes(store)

        first = rollover(store, checkpoint_mono_ns=clock.monotonic_ns(), config=config)
        clock.advance_ms(1)
        second = rollover(store, checkpoint_mono_ns=clock.monotonic_ns(), config=config)

        assert first.payload.recent_events == []
        for payload in (first.payload, second.payload):
            assert [item.action_event_id for item in payload.prior_uses] == [delegate_event_id]
            prior_use = payload.prior_uses[0]
            assert prior_use.kind == "delegate"
            assert prior_use.fact == delegate.fact
            assert prior_use.request_id == request_id
            assert prior_use.args == delegate.args
            assert prior_use.result_event_id == delivery.event_id
            assert prior_use.result_status == "succeeded"
            assert prior_use.result_disposition is Disposition.HANDLED
            assert [item.event_id for item in payload.dispositions] == [delivery.event_id]
        already_handled = IdleAction(
            type="idle",
            reason=IdleReason.ALREADY_HANDLED,
            related_event_id=delivery.event_id,
        )
        assert isinstance(check(already_handled, build_license_view(store, config)), Allowed)

        newer_text = "new topic"
        commit_event(
            store,
            clock,
            source="user",
            kind="snapshot",
            activity="paused",
            payload={
                "text": newer_text,
                "selection_start_utf16": len(newer_text),
                "selection_end_utf16": len(newer_text),
                "is_composing": False,
                "edit_kind": "replace",
            },
        )
        third = rollover(store, checkpoint_mono_ns=clock.monotonic_ns(), config=config)
        assert third.payload.prior_uses == []
        assert check(delegate, build_license_view(store, config)) == Blocked(
            LicenseBlockCode.UNKNOWN_REFERENCE
        )
    finally:
        store.close()


@pytest.mark.gate
@pytest.mark.asyncio
async def test_double_rollover_continuity(tmp_path: Path) -> None:
    config = RuntimeConfig(
        checkpoint_reserved_tokens=4_000,
        recent_events_budget_tokens=120,
        max_timer_interval_ms=60_000,
        max_active_timers=3,
        max_timer_message_bytes=128,
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
        timer_a_action_event_id = commit_event(
            store,
            clock,
            source="model",
            kind="action_executed",
            payload=action_payload(timer_a_action),
        )
        timer_b_action_event_id = commit_event(
            store,
            clock,
            source="model",
            kind="action_executed",
            payload=action_payload(timer_b_action),
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
        ready_action_event_id = commit_event(
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
        long_respond_id = commit_event(
            store,
            clock,
            source="model",
            kind="action_executed",
            payload=action_payload(long_respond),
        )
        store.set_response_disposition(snapshot_id, by_action_event_id=long_respond_id)
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
        assert second.payload.capabilities.model_dump(mode="python") == (
            config.timer_capabilities()
        )
        assert second.payload.snapshot.event_id == snapshot_id
        assert second.payload.snapshot.activity == "paused"
        assert [timer.timer_id for timer in second.payload.timers] == [
            timer_a.timer_id,
            timer_b.timer_id,
        ]
        assert second.payload.timers[1].status == "canceled"
        assert [item.event_id for item in second.payload.open_timer_fires] == [beta_fire.event_id]
        assert second.payload.open_timer_fires[0].due_age_ms == (
            second.payload.open_timer_fires[0].age_ms
            + second.payload.open_timer_fires[0].late_ms
        )
        assert [item.event_id for item in second.payload.open_tool_results] == [
            ready_delivery.event_id
        ]
        assert [item.action_event_id for item in second.payload.prior_uses] == [
            timer_a_action_event_id,
            timer_b_action_event_id,
            ready_action_event_id,
        ]
        ready_result = second.payload.open_tool_results[0]
        assert ready_result.fact_event_id == snapshot_id
        assert ready_result.fact_text == "lookup ready"
        assert ready_result.args.query == "ready"
        assert [
            (item.request_id, item.policy_seq, item.fact_event_id, item.fact_text)
            for item in second.payload.pending_tools
        ] == [(pending_request_id, 5, snapshot_id, "lookup pending")]
        assert [item.mark_event_id for item in second.payload.applied_marks] == [mark_event_id]
        assert [item.event_id for item in second.payload.recent_events] == [historical_integrate_id]
        assert [
            (item.event_id, item.policy_seq, item.relation, item.state)
            for item in second.payload.dispositions
        ] == [
            (snapshot_id, 0, "responded_to", Disposition.HANDLED),
            (historical_result_id, 10, "event", Disposition.HANDLED)
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

        policy = ScriptedPolicy(
            [
                integrate_after_rollover,
                skip_after_rollover,
                IdleAction(type="idle", reason=IdleReason.NO_TRIGGER, related_event_id=None),
            ]
        )
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

        assert policy.call_count == 3
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
