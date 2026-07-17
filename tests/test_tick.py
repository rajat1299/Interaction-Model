"""Serialized tick-loop, execution, and wake-semantics tests."""

import asyncio
from datetime import UTC, datetime
from pathlib import Path

import pytest

from im.canonical_json import canonicalize_tim_json, parse_tim_json
from im.policy.base import ScriptedPolicy
from im.scheduler import ManualClock, TimerScheduler
from im.schema.actions import (
    CancelAction,
    CancelTimerTarget,
    DelegateAction,
    IdleAction,
    IdleReason,
    IntegrateAction,
    MarkAction,
    NudgeAction,
    RespondAction,
    ScheduleAction,
    SkipAction,
    SkipReason,
    Span,
)
from im.schema.common import Disposition, LicenseBlockCode, ToolResultStatus
from im.schema.events import ActionExecutedEvent, TimerFireEvent
from im.store import PolicyEventDraft, Store
from im.tick import RenderKind, TickPhase, TickRuntime, build_license_view
from im.tools import ScriptedToolResult, ToolAdapter


def snapshot_draft(
    store: Store,
    clock: ManualClock,
    text: str,
    *,
    activity: str = "active",
) -> PolicyEventDraft:
    event_id = store.allocate_id("event")
    payload = {
        "text": text,
        "selection_start_utf16": len(text.encode("utf-16-le")) // 2,
        "selection_end_utf16": len(text.encode("utf-16-le")) // 2,
        "is_composing": False,
        "edit_kind": "insert",
    }
    store.append_ingress(
        event_id=event_id,
        received_utc=clock.wall_utc().isoformat(),
        received_mono_ns=clock.monotonic_ns(),
        source="user",
        kind="snapshot",
        payload=canonicalize_tim_json(payload),
    )
    return PolicyEventDraft(
        id=event_id,
        source="user",
        kind="snapshot",
        payload=payload,
        occurred_mono_ns=clock.monotonic_ns(),
        activity=activity,
    )


def span(draft: PolicyEventDraft, text: str, start: int = 0) -> Span:
    return Span(
        event_id=draft.id,
        start_utf16=start,
        end_utf16=start + len(text.encode("utf-16-le")) // 2,
        text=text,
    )


def make_runtime(
    tmp_path: Path,
    actions: list[object],
    *,
    render_sink=None,
    tool_script=None,
    measurement_audits: bool = False,
) -> tuple[Store, ManualClock, TimerScheduler, ToolAdapter, ScriptedPolicy, TickRuntime]:
    store = Store(tmp_path / "session.sqlite3")
    clock = ManualClock(wall_utc=datetime(2026, 7, 12, 12, tzinfo=UTC))
    scheduler = TimerScheduler(store, clock)
    tools = ToolAdapter(store, clock)
    policy = ScriptedPolicy(actions)
    runtime = TickRuntime(
        store=store,
        policy=policy,
        scheduler=scheduler,
        tools=tools,
        clock=clock,
        render_sink=render_sink,
        tool_script=tool_script,
        measurement_audits=measurement_audits,
    )
    return store, clock, scheduler, tools, policy, runtime


def action_types(store: Store) -> list[str]:
    return [
        record.event.payload.action.type
        for record in store.policy_records()
        if isinstance(record.event, ActionExecutedEvent)
    ]


@pytest.mark.asyncio
async def test_idle_audits_attempt_without_committing_action_or_continuing(tmp_path: Path) -> None:
    store, clock, _scheduler, _tools, policy, runtime = make_runtime(
        tmp_path,
        [IdleAction(type="idle", reason=IdleReason.NO_TRIGGER, related_event_id=None)],
    )
    try:
        runtime.enqueue_committed_ingress(snapshot_draft(store, clock, "typing"))
        await runtime.run_until_idle()

        assert runtime.phase is TickPhase.IDLE
        assert runtime.tick_count == policy.call_count == 1
        assert action_types(store) == []
        assert store._connection.execute("SELECT rowid, kind, payload FROM audit").fetchall() == [
            (
                1,
                "action_attempt",
                b'{"decision_id":"d_000001","observed_through_policy_seq":0,"raw":{"reason":"no_trigger","related_event_id":null,"type":"idle"}}',
            )
        ]
    finally:
        store.close()


@pytest.mark.asyncio
async def test_decision_start_keeps_coalesced_snapshot_arrivals_in_order(tmp_path: Path) -> None:
    store, clock, _scheduler, _tools, _policy, runtime = make_runtime(
        tmp_path,
        [IdleAction(type="idle", reason=IdleReason.NO_TRIGGER, related_event_id=None)],
        measurement_audits=True,
    )
    try:
        first = snapshot_draft(store, clock, "first")
        second = snapshot_draft(store, clock, "second")
        runtime.enqueue_committed_ingress(first)
        runtime.enqueue_committed_ingress(second)
        await runtime.run_until_idle()

        (row,) = store._connection.execute(
            "SELECT payload FROM audit WHERE kind = 'decision_started'"
        ).fetchall()
        assert parse_tim_json(bytes(row[0])) == {
            "decision_id": "d_000001",
            "observed_through_policy_seq": 0,
            "started_mono_ns": 0,
            "arrivals": [
                {
                    "event_id": first.id,
                    "source": "user",
                    "kind": "snapshot",
                    "arrived_while_inferring": False,
                    "replaced_pending_snapshot": False,
                },
                {
                    "event_id": second.id,
                    "source": "user",
                    "kind": "snapshot",
                    "arrived_while_inferring": False,
                    "replaced_pending_snapshot": True,
                },
            ],
        }
    finally:
        store.close()


@pytest.mark.asyncio
async def test_mark_and_respond_emit_only_after_committed_action(tmp_path: Path) -> None:
    effects = []
    store = Store(tmp_path / "session.sqlite3")
    clock = ManualClock(wall_utc=datetime(2026, 7, 12, 12, tzinfo=UTC))
    first = snapshot_draft(store, clock, "mark cat")
    mark = MarkAction(
        type="mark",
        instruction=span(first, "mark", 0),
        target=span(first, "cat", 5),
    )
    second = snapshot_draft(store, clock, "done", activity="paused")
    respond = RespondAction(type="respond", reply_to_event_id=second.id, text="Okay")
    scheduler = TimerScheduler(store, clock)
    tools = ToolAdapter(store, clock)
    policy = ScriptedPolicy(
        [
            mark,
            IdleAction(type="idle", reason=IdleReason.NO_TRIGGER, related_event_id=None),
            respond,
        ]
    )

    async def sink(effect) -> None:
        assert any(record.event.id == effect.action_event_id for record in store.policy_records())
        effects.append(effect)

    runtime = TickRuntime(
        store=store,
        policy=policy,
        scheduler=scheduler,
        tools=tools,
        clock=clock,
        render_sink=sink,
    )
    try:
        runtime.enqueue_committed_ingress(first)
        await runtime.run_until_idle()
        assert len(build_license_view(store, runtime.config).applied_marks) == 1
        runtime.enqueue_committed_ingress(second)
        await runtime.run_until_idle()

        assert action_types(store) == ["mark", "respond"]
        assert [effect.kind for effect in effects] == [RenderKind.MARK, RenderKind.RESPOND]
        assert build_license_view(store, runtime.config).applied_marks == ()
    finally:
        store.close()


@pytest.mark.gate
@pytest.mark.asyncio
async def test_cancel_fire_race(tmp_path: Path) -> None:
    effects = []
    store = Store(tmp_path / "session.sqlite3")
    clock = ManualClock(wall_utc=datetime(2026, 7, 12, 12, tzinfo=UTC))
    instruction = snapshot_draft(store, clock, "remind me to breathe", activity="paused")
    schedule = ScheduleAction(
        type="schedule",
        instruction=span(instruction, "remind me to breathe"),
        interval_ms=1_000,
        message="breathe",
    )
    scheduler = TimerScheduler(store, clock)
    tools = ToolAdapter(store, clock)
    policy = ScriptedPolicy(
        [schedule, IdleAction(type="idle", reason=IdleReason.NO_TRIGGER, related_event_id=None)]
    )
    runtime = TickRuntime(
        store=store,
        policy=policy,
        scheduler=scheduler,
        tools=tools,
        clock=clock,
        render_sink=effects.append,
    )
    try:
        runtime.enqueue_committed_ingress(instruction)
        await runtime.run_until_idle()
        timer = store.active_timers()[0]

        clock.advance_ms(1_000)
        (fire,) = scheduler.claim_due()
        stop = snapshot_draft(store, clock, "stop", activity="paused")
        runtime.enqueue_committed_ingress(fire.draft)
        runtime.enqueue_committed_ingress(stop)
        policy._actions.extend(
            [
                CancelAction(
                    type="cancel",
                    instruction=span(stop, "stop"),
                    target=CancelTimerTarget(kind="timer", timer_id=timer.timer_id),
                ),
                SkipAction(
                    type="skip",
                    target_event_id=fire.event_id,
                    reason=SkipReason.CANCELED_TIMER,
                ),
                IdleAction(type="idle", reason=IdleReason.NO_TRIGGER, related_event_id=None),
            ]
        )
        await runtime.run_until_idle()

        assert runtime.tick_count == policy.call_count == 5
        assert action_types(store) == ["schedule", "cancel", "skip"]
        assert store.get_disposition(fire.event_id).state is Disposition.SKIPPED  # type: ignore[union-attr]
        assert all(effect.kind is not RenderKind.NUDGE for effect in effects)
        clock.advance_ms(2_000)
        assert scheduler.claim_due() == ()
    finally:
        store.close()


class BlockingRespondPolicy:
    def __init__(self, response: RespondAction) -> None:
        self.response = response
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.call_count = 0
        self.observed_policy_bytes: list[bytes] = []

    async def decide(self, policy_bytes: bytes) -> object:
        self.call_count += 1
        self.observed_policy_bytes.append(policy_bytes)
        if self.call_count == 1:
            self.started.set()
            await self.release.wait()
            return self.response
        return IdleAction(type="idle", reason=IdleReason.NO_TRIGGER, related_event_id=None)


class BlockingSchedulePolicy:
    def __init__(self, schedule: ScheduleAction) -> None:
        self.schedule = schedule
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.call_count = 0

    async def decide(self, _policy_bytes: bytes) -> object:
        self.call_count += 1
        if self.call_count == 1:
            self.started.set()
            await self.release.wait()
            return self.schedule
        return IdleAction(type="idle", reason=IdleReason.NO_TRIGGER, related_event_id=None)


@pytest.mark.asyncio
async def test_new_snapshot_during_inference_blocks_stale_respond_then_ticks_fresh_stream(
    tmp_path: Path,
) -> None:
    store = Store(tmp_path / "session.sqlite3")
    clock = ManualClock(wall_utc=datetime(2026, 7, 12, 12, tzinfo=UTC))
    first = snapshot_draft(store, clock, "first", activity="paused")
    policy = BlockingRespondPolicy(
        RespondAction(type="respond", reply_to_event_id=first.id, text="old reply")
    )
    runtime = TickRuntime(
        store=store,
        policy=policy,
        scheduler=TimerScheduler(store, clock),
        tools=ToolAdapter(store, clock),
        clock=clock,
    )
    try:
        runtime.enqueue_committed_ingress(first)
        task = asyncio.create_task(runtime.run_until_idle())
        await policy.started.wait()
        clock.advance_ms(1)
        second = snapshot_draft(store, clock, "second", activity="paused")
        await runtime.submit_committed_ingress(second)
        policy.release.set()
        await task

        assert policy.call_count == runtime.tick_count == 2
        assert action_types(store) == []
        block_rows = store._connection.execute(
            "SELECT payload FROM audit WHERE kind = 'action_blocked'"
        ).fetchall()
        assert [parse_tim_json(bytes(row[0]))["code"] for row in block_rows] == [
            LicenseBlockCode.STALE_DECISION.value
        ]
        assert store.policy_records()[-1].event.id == second.id
    finally:
        store.close()


@pytest.mark.asyncio
async def test_arrival_during_render_is_not_marked_as_inferring(tmp_path: Path) -> None:
    render_started = asyncio.Event()
    release_render = asyncio.Event()

    async def sink(_effect) -> None:
        render_started.set()
        await release_render.wait()

    store = Store(tmp_path / "session.sqlite3")
    clock = ManualClock(wall_utc=datetime(2026, 7, 12, 12, tzinfo=UTC))
    first = snapshot_draft(store, clock, "first", activity="paused")
    runtime = TickRuntime(
        store=store,
        policy=ScriptedPolicy(
            [
                RespondAction(type="respond", reply_to_event_id=first.id, text="reply"),
                IdleAction(type="idle", reason=IdleReason.NO_TRIGGER, related_event_id=None),
            ]
        ),
        scheduler=TimerScheduler(store, clock),
        tools=ToolAdapter(store, clock),
        clock=clock,
        render_sink=sink,
        measurement_audits=True,
    )
    try:
        runtime.enqueue_committed_ingress(first)
        task = asyncio.create_task(runtime.run_until_idle())
        await render_started.wait()
        assert store._connection.execute(
            "SELECT 1 FROM audit WHERE kind = 'decision_finished'"
        ).fetchone()

        second = snapshot_draft(store, clock, "second", activity="paused")
        runtime.enqueue_committed_ingress(second)
        release_render.set()
        await task

        rows = store._connection.execute(
            "SELECT payload FROM audit WHERE kind = 'decision_started' ORDER BY rowid"
        ).fetchall()
        assert parse_tim_json(bytes(rows[1][0]))["arrivals"] == [
            {
                "event_id": second.id,
                "source": "user",
                "kind": "snapshot",
                "arrived_while_inferring": False,
                "replaced_pending_snapshot": False,
            }
        ]
    finally:
        store.close()


@pytest.mark.asyncio
async def test_mid_inference_ingress_commits_before_permitted_action_and_forces_next_tick(
    tmp_path: Path,
) -> None:
    store = Store(tmp_path / "session.sqlite3")
    clock = ManualClock(wall_utc=datetime(2026, 7, 12, 12, tzinfo=UTC))
    instruction = snapshot_draft(store, clock, "breathe", activity="paused")
    policy = BlockingSchedulePolicy(
        ScheduleAction(
            type="schedule",
            instruction=span(instruction, "breathe"),
            interval_ms=1_000,
            message="breathe",
        )
    )
    runtime = TickRuntime(
        store=store,
        policy=policy,
        scheduler=TimerScheduler(store, clock),
        tools=ToolAdapter(store, clock),
        clock=clock,
        measurement_audits=True,
    )
    try:
        runtime.enqueue_committed_ingress(instruction)
        task = asyncio.create_task(runtime.run_until_idle())
        await policy.started.wait()
        clock.advance_ms(1)
        fresh = snapshot_draft(store, clock, "breathe now", activity="paused")
        await runtime.submit_committed_ingress(fresh)
        clock.advance_ms(1)
        policy.release.set()
        await task

        records = store.policy_records()
        fresh_seq = next(record.seq for record in records if record.event_id == fresh.id)
        action_seq = next(
            record.seq
            for record in records
            if isinstance(record.event, ActionExecutedEvent)
            and record.event.payload.action.type == "schedule"
        )
        assert fresh_seq < action_seq
        assert policy.call_count == runtime.tick_count == 2
        assert action_types(store) == ["schedule"]
        assert len(store.active_timers()) == 1
        assert runtime.pending == ()
        rows = store._connection.execute(
            "SELECT payload FROM audit WHERE kind = 'decision_started' ORDER BY rowid"
        ).fetchall()
        arrivals = [parse_tim_json(bytes(row[0]))["arrivals"] for row in rows]
        assert arrivals == [
            [
                {
                    "event_id": instruction.id,
                    "source": "user",
                    "kind": "snapshot",
                    "arrived_while_inferring": False,
                    "replaced_pending_snapshot": False,
                }
            ],
            [
                {
                    "event_id": fresh.id,
                    "source": "user",
                    "kind": "snapshot",
                    "arrived_while_inferring": True,
                    "replaced_pending_snapshot": False,
                }
            ],
        ]
    finally:
        store.close()


@pytest.mark.asyncio
async def test_continuation_decision_explicitly_audits_empty_arrivals(tmp_path: Path) -> None:
    store = Store(tmp_path / "session.sqlite3")
    clock = ManualClock(wall_utc=datetime(2026, 7, 12, 12, tzinfo=UTC))
    snapshot = snapshot_draft(store, clock, "breathe", activity="paused")
    schedule = ScheduleAction(
        type="schedule",
        instruction=span(snapshot, "breathe"),
        interval_ms=1_000,
        message="breathe",
    )
    runtime = TickRuntime(
        store=store,
        policy=ScriptedPolicy(
            [schedule, IdleAction(type="idle", reason=IdleReason.NO_TRIGGER, related_event_id=None)]
        ),
        scheduler=TimerScheduler(store, clock),
        tools=ToolAdapter(store, clock),
        clock=clock,
        measurement_audits=True,
    )
    try:
        runtime.enqueue_committed_ingress(snapshot)
        await runtime.run_until_idle()

        rows = store._connection.execute(
            "SELECT payload FROM audit WHERE kind = 'decision_started' ORDER BY rowid"
        ).fetchall()
        assert [parse_tim_json(bytes(row[0]))["arrivals"] for row in rows] == [
            [
                {
                    "event_id": snapshot.id,
                    "source": "user",
                    "kind": "snapshot",
                    "arrived_while_inferring": False,
                    "replaced_pending_snapshot": False,
                }
            ],
            [],
        ]
    finally:
        store.close()


@pytest.mark.asyncio
async def test_decision_timing_brackets_policy_without_changing_attempt_or_bytes(
    tmp_path: Path,
) -> None:
    store = Store(tmp_path / "session.sqlite3")
    clock = ManualClock(wall_utc=datetime(2026, 7, 12, 12, tzinfo=UTC))
    snapshot = snapshot_draft(store, clock, "first", activity="paused")
    policy = BlockingRespondPolicy(
        RespondAction(type="respond", reply_to_event_id=snapshot.id, text="reply")
    )
    runtime = TickRuntime(
        store=store,
        policy=policy,
        scheduler=TimerScheduler(store, clock),
        tools=ToolAdapter(store, clock),
        clock=clock,
        measurement_audits=True,
    )
    try:
        runtime.enqueue_committed_ingress(snapshot)
        task = asyncio.create_task(runtime.run_until_idle())
        await policy.started.wait()
        policy_bytes = store.policy_bytes()
        clock.advance_ns(17)
        policy.release.set()
        await task

        rows = store._connection.execute(
            """
            SELECT kind, payload FROM audit
            WHERE kind IN ('decision_started', 'decision_finished', 'action_attempt')
            ORDER BY rowid
            """
        ).fetchall()
        start, finish, attempt = [parse_tim_json(bytes(row[1])) for row in rows]
        assert [row[0] for row in rows] == [
            "decision_started",
            "decision_finished",
            "action_attempt",
        ]
        assert start == {
            "decision_id": "d_000001",
            "observed_through_policy_seq": 0,
            "started_mono_ns": 0,
            "arrivals": [
                {
                    "event_id": snapshot.id,
                    "source": "user",
                    "kind": "snapshot",
                    "arrived_while_inferring": False,
                    "replaced_pending_snapshot": False,
                }
            ],
        }
        assert finish == {"decision_id": "d_000001", "finished_mono_ns": 17}
        assert policy.observed_policy_bytes == [policy_bytes]
        assert attempt == {
            "decision_id": "d_000001",
            "observed_through_policy_seq": 0,
            "raw": {
                "type": "respond",
                "reply_to_event_id": snapshot.id,
                "text": "reply",
            },
        }
    finally:
        store.close()


@pytest.mark.asyncio
async def test_delegate_result_integrate_lifecycle(tmp_path: Path) -> None:
    store = Store(tmp_path / "session.sqlite3")
    clock = ManualClock(wall_utc=datetime(2026, 7, 12, 12, tzinfo=UTC))
    fact = snapshot_draft(store, clock, "lookup nonce", activity="paused")
    delegate = DelegateAction(
        type="delegate",
        fact=span(fact, "nonce", 7),
        tool="lookup",
        args={"query": "nonce"},
    )
    policy = ScriptedPolicy([delegate])
    tools = ToolAdapter(store, clock)
    runtime = TickRuntime(
        store=store,
        policy=policy,
        scheduler=TimerScheduler(store, clock),
        tools=tools,
        clock=clock,
        tool_script=lambda _action: ScriptedToolResult(latency_ms=10, data={"answer": "n-42"}),
    )
    try:
        runtime.enqueue_committed_ingress(fact)
        await runtime.run_until_idle()
        assert action_types(store) == ["delegate"]
        assert len(store.pending_tool_requests()) == 1

        clock.advance_ms(10)
        (delivery,) = tools.deliver_due()
        policy._actions.append(
            IntegrateAction(
                type="integrate",
                result_event_id=delivery.event_id,
                text="The answer is n-42.",
            )
        )
        runtime.enqueue_committed_ingress(delivery.as_policy_draft())
        await runtime.run_until_idle()

        assert action_types(store) == ["delegate", "integrate"]
        assert store.get_disposition(delivery.event_id).state is Disposition.HANDLED  # type: ignore[union-attr]
    finally:
        store.close()


@pytest.mark.asyncio
async def test_failed_result_response_consumes_result_without_retry_loop(tmp_path: Path) -> None:
    effects = []
    store = Store(tmp_path / "session.sqlite3")
    clock = ManualClock(wall_utc=datetime(2026, 7, 12, 12, tzinfo=UTC))
    fact = snapshot_draft(store, clock, "lookup nonce", activity="paused")
    delegate = DelegateAction(
        type="delegate",
        fact=span(fact, "nonce", 7),
        tool="lookup",
        args={"query": "nonce"},
    )
    policy = ScriptedPolicy([delegate])
    tools = ToolAdapter(store, clock)
    runtime = TickRuntime(
        store=store,
        policy=policy,
        scheduler=TimerScheduler(store, clock),
        tools=tools,
        clock=clock,
        render_sink=effects.append,
        tool_script=lambda _action: ScriptedToolResult(
            latency_ms=0,
            status=ToolResultStatus.FAILED,
            data={"error": "unavailable"},
        ),
    )
    try:
        runtime.enqueue_committed_ingress(fact)
        await runtime.run_until_idle()
        (delivery,) = tools.deliver_due()
        policy._actions.append(
            RespondAction(
                type="respond",
                reply_to_event_id=delivery.event_id,
                text="The lookup failed.",
            )
        )

        runtime.enqueue_committed_ingress(delivery.as_policy_draft())
        await runtime.run_until_idle()

        assert action_types(store) == ["delegate", "respond"]
        assert store.get_disposition(delivery.event_id).state is Disposition.HANDLED  # type: ignore[union-attr]
        assert policy.call_count == runtime.tick_count == 2
        assert effects[-1].kind is RenderKind.RESPOND
        assert effects[-1].payload["reply_to_event_id"] == delivery.event_id
    finally:
        store.close()


@pytest.mark.asyncio
async def test_ordinary_response_is_one_shot_without_consuming_other_snapshot_actions(
    tmp_path: Path,
) -> None:
    store = Store(tmp_path / "session.sqlite3")
    clock = ManualClock(wall_utc=datetime(2026, 7, 12, 12, tzinfo=UTC))
    user = snapshot_draft(store, clock, "Which timer should I stop?", activity="paused")
    response = RespondAction(
        type="respond",
        reply_to_event_id=user.id,
        text="Which timer should I stop?",
    )
    policy = ScriptedPolicy([response, response])
    runtime = TickRuntime(
        store=store,
        policy=policy,
        scheduler=TimerScheduler(store, clock),
        tools=ToolAdapter(store, clock),
        clock=clock,
    )
    try:
        runtime.enqueue_committed_ingress(user)
        await runtime.run_until_idle()

        clock.advance_ms(1)
        annotation_id = store.allocate_id("event")
        runtime.enqueue_committed_ingress(
            PolicyEventDraft(
                id=annotation_id,
                source="user",
                kind="annotation",
                payload={"text": "wake"},
                occurred_mono_ns=clock.monotonic_ns(),
            )
        )
        await runtime.run_until_idle()

        assert action_types(store) == ["respond"]
        assert store.response_disposition(user.id) is not None
        same = snapshot_draft(store, clock, user.payload["text"], activity="paused")
        store.commit_policy(same)
        assert build_license_view(store, runtime.config).latest_snapshot == (
            build_license_view(store, runtime.config).event(same.id)
        )
        assert build_license_view(store, runtime.config).latest_snapshot.responded_to

        changed = snapshot_draft(
            store, clock, "Which timer should I stop first?", activity="paused"
        )
        store.commit_policy(changed)
        assert not build_license_view(store, runtime.config).latest_snapshot.responded_to
        repeated = snapshot_draft(store, clock, user.payload["text"], activity="paused")
        store.commit_policy(repeated)
        assert not build_license_view(store, runtime.config).latest_snapshot.responded_to

        block = store._connection.execute(
            "SELECT payload FROM audit WHERE kind = 'action_blocked' ORDER BY rowid DESC LIMIT 1"
        ).fetchone()
        assert parse_tim_json(bytes(block[0]))["code"] == (
            LicenseBlockCode.TARGET_ALREADY_HANDLED.value
        )
    finally:
        store.close()


@pytest.mark.asyncio
async def test_nudge_consumes_fire_and_uses_canonical_timer_message(tmp_path: Path) -> None:
    effects = []
    store = Store(tmp_path / "session.sqlite3")
    clock = ManualClock(wall_utc=datetime(2026, 7, 12, 12, tzinfo=UTC))
    origin = snapshot_draft(store, clock, "breathe", activity="paused")
    scheduler = TimerScheduler(store, clock)
    scheduler.schedule(
        instruction_id="i_001",
        instruction=span(origin, "breathe"),
        interval_ms=1_000,
        message="canonical breathe",
    )
    clock.advance_ms(1_000)
    (fire,) = scheduler.claim_due()
    policy = ScriptedPolicy(
        [
            NudgeAction(type="nudge", fire_event_id=fire.event_id),
            IdleAction(type="idle", reason=IdleReason.NO_TRIGGER, related_event_id=None),
        ]
    )
    runtime = TickRuntime(
        store=store,
        policy=policy,
        scheduler=scheduler,
        tools=ToolAdapter(store, clock),
        clock=clock,
        render_sink=effects.append,
    )
    try:
        runtime.enqueue_committed_ingress(origin)
        runtime.enqueue_committed_ingress(fire.draft)
        await runtime.run_until_idle()

        assert store.get_disposition(fire.event_id).state is Disposition.HANDLED  # type: ignore[union-attr]
        assert effects[-1].kind is RenderKind.NUDGE
        assert effects[-1].payload["message"] == "canonical breathe"
    finally:
        store.close()


@pytest.mark.asyncio
async def test_high_priority_action_drains_marks_before_rollover_can_observe_baseline(
    tmp_path: Path,
) -> None:
    store = Store(tmp_path / "session.sqlite3")
    clock = ManualClock(wall_utc=datetime(2026, 7, 12, 12, tzinfo=UTC))
    snapshot = snapshot_draft(store, clock, "mark animals cat", activity="paused")
    scheduler = TimerScheduler(store, clock)
    scheduler.schedule(
        instruction_id="i_001",
        instruction=span(snapshot, "mark animals", 0),
        interval_ms=1_000,
        message="breathe",
    )
    clock.advance_ms(1_000)
    (fire,) = scheduler.claim_due()
    mark = MarkAction(
        type="mark",
        instruction=span(snapshot, "mark animals", 0),
        target=span(snapshot, "cat", 13),
    )
    policy = ScriptedPolicy(
        [
            NudgeAction(type="nudge", fire_event_id=fire.event_id),
            mark,
            {"type": "respond"},
            IdleAction(type="idle", reason=IdleReason.NO_TRIGGER, related_event_id=None),
        ]
    )
    runtime = TickRuntime(
        store=store,
        policy=policy,
        scheduler=scheduler,
        tools=ToolAdapter(store, clock),
        clock=clock,
    )
    try:
        runtime.enqueue_committed_ingress(snapshot)
        runtime.enqueue_committed_ingress(fire.draft)
        await runtime.run_until_idle()

        assert action_types(store) == ["nudge", "mark"]
        assert policy.call_count == runtime.tick_count == 4
        assert runtime.mark_quiescent
    finally:
        store.close()


@pytest.mark.asyncio
async def test_repeated_blocked_mark_continuation_fails_explicitly(tmp_path: Path) -> None:
    store = Store(tmp_path / "session.sqlite3")
    clock = ManualClock(wall_utc=datetime(2026, 7, 12, 12, tzinfo=UTC))
    snapshot = snapshot_draft(store, clock, "mark cat", activity="paused")
    mark = MarkAction(
        type="mark",
        instruction=span(snapshot, "mark", 0),
        target=span(snapshot, "cat", 5),
    )
    policy = ScriptedPolicy(
        [mark, {"type": "respond"}, {"type": "respond"}, {"type": "respond"}]
    )
    runtime = TickRuntime(
        store=store,
        policy=policy,
        scheduler=TimerScheduler(store, clock),
        tools=ToolAdapter(store, clock),
        clock=clock,
    )
    try:
        runtime.enqueue_committed_ingress(snapshot)

        with pytest.raises(RuntimeError, match="mark-quiescence"):
            await runtime.run_until_idle()

        assert not runtime.mark_quiescent
        assert action_types(store) == ["mark"]
        assert policy.call_count == runtime.tick_count == 4
    finally:
        store.close()


@pytest.mark.asyncio
async def test_committed_fire_is_superseded_by_newest_fire_with_accumulated_count(
    tmp_path: Path,
) -> None:
    store, clock, scheduler, _tools, policy, runtime = make_runtime(
        tmp_path,
        [
            IdleAction(type="idle", reason=IdleReason.NO_TRIGGER, related_event_id=None),
            IdleAction(type="idle", reason=IdleReason.NO_TRIGGER, related_event_id=None),
        ],
    )
    origin = snapshot_draft(store, clock, "breathe", activity="paused")
    timer = scheduler.schedule(
        instruction_id="i_001",
        instruction=span(origin, "breathe"),
        interval_ms=1_000,
        message="breathe",
    )
    try:
        clock.advance_ms(1_000)
        first = scheduler.claim_due()[0]
        runtime.enqueue_committed_ingress(origin)
        runtime.enqueue_committed_ingress(first.draft)
        await runtime.run_until_idle()

        clock.advance_ms(1_000)
        second = scheduler.claim_due()[0]
        runtime.enqueue_committed_ingress(second.draft)
        await runtime.run_until_idle()

        assert store.get_disposition(first.event_id).state is Disposition.SUPERSEDED  # type: ignore[union-attr]
        assert store.get_disposition(second.event_id).state is Disposition.OPEN  # type: ignore[union-attr]
        committed_second = next(
            record.event for record in store.policy_records() if record.event.id == second.event_id
        )
        assert isinstance(committed_second, TimerFireEvent)
        assert committed_second.payload.timer_id == timer.timer_id
        assert committed_second.payload.missed_count == 1
        assert policy.call_count == 2
    finally:
        store.close()


@pytest.mark.asyncio
async def test_schedule_failure_after_action_append_rolls_back_entire_execution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = Store(tmp_path / "session.sqlite3")
    clock = ManualClock(wall_utc=datetime(2026, 7, 12, 12, tzinfo=UTC))
    origin = snapshot_draft(store, clock, "breathe", activity="paused")
    schedule = ScheduleAction(
        type="schedule",
        instruction=span(origin, "breathe"),
        interval_ms=1_000,
        message="breathe",
    )
    runtime = TickRuntime(
        store=store,
        policy=ScriptedPolicy([schedule]),
        scheduler=TimerScheduler(store, clock),
        tools=ToolAdapter(store, clock),
        clock=clock,
    )

    def fail_ack(_kind: str, _payload: dict[str, object]) -> None:
        raise RuntimeError("forced ack failure")

    monkeypatch.setattr(runtime, "_commit_ack", fail_ack)
    try:
        runtime.enqueue_committed_ingress(origin)
        with pytest.raises(RuntimeError, match="forced ack failure"):
            await runtime.run_until_idle()

        assert action_types(store) == []
        assert store.timers() == ()
        assert store.allocate_id("event") == "e_000002"
        assert store.allocate_id("instruction") == "i_001"
        assert store.allocate_id("timer") == "t_001"
    finally:
        store.close()


@pytest.mark.asyncio
async def test_malformed_action_is_blocked_without_state_change(tmp_path: Path) -> None:
    store, clock, _scheduler, _tools, _policy, runtime = make_runtime(
        tmp_path,
        [[{"type": "idle"}, {"type": "idle"}]],
    )
    try:
        runtime.enqueue_committed_ingress(snapshot_draft(store, clock, "text"))
        await runtime.run_until_idle()

        assert action_types(store) == []
        row = store._connection.execute(
            "SELECT payload FROM audit WHERE kind = 'action_blocked'"
        ).fetchone()
        assert parse_tim_json(bytes(row[0]))["code"] == LicenseBlockCode.MALFORMED_ACTION.value
    finally:
        store.close()
