from __future__ import annotations

from pathlib import Path

import pytest

from im.config import RuntimeConfig
from im.generation.runtime import RuntimeIngestionHarness, TimedDecision
from im.schema.actions import DelegateAction, IdleAction, LookupArgs, ScheduleAction, Span
from im.schema.common import ToolName
from im.schema.events import SnapshotEvent, StateCheckpointEvent, TimerFireEvent, ToolResultEvent
from im.tools import ScriptedToolResult


def idle() -> IdleAction:
    return IdleAction(type="idle", reason="no_trigger", related_event_id=None)


def frame(text: str, *, activity: str = "active") -> dict[str, object]:
    cursor = len(text.encode("utf-16-le")) // 2
    return {
        "text": text,
        "selection_start": cursor,
        "selection_end": cursor,
        "is_composing": False,
        "input_type": "insertText",
        "activity": activity,
        "client_ts": 0,
    }


@pytest.mark.asyncio
async def test_harness_commits_exact_frames_through_runtime_session(tmp_path: Path) -> None:
    async with RuntimeIngestionHarness(
        session_id="s_generation_exact",
        directory=tmp_path / "session",
        decisions=(TimedDecision(25, idle()),),
    ) as harness:
        event_id = harness.accept_snapshot(frame("draft 😀"))
        await harness.drive_until_decisions(1)
        await harness.wait_until_idle()

        snapshots = [
            record.event
            for record in harness.session.store.policy_records()
            if isinstance(record.event, SnapshotEvent)
        ]
        assert event_id == "e_000002"
        assert [event.payload.text for event in snapshots] == ["draft 😀"]
        assert harness.policy.observed_policy_bytes == [harness.session.store.policy_bytes()]
        assert harness.policy.timings[0].service_ms == 25


@pytest.mark.asyncio
async def test_same_time_pump_starts_first_inference_before_next_frame_time(tmp_path: Path) -> None:
    async with RuntimeIngestionHarness(
        session_id="s_generation_same_time",
        directory=tmp_path / "session",
        decisions=(TimedDecision(910, idle()), TimedDecision(0, idle())),
    ) as harness:
        harness.accept_snapshot(frame("first"))
        await harness.progress_at_current_time()

        assert harness.policy.active_deadline_ns == 910_000_000
        await harness.advance_ms(2_000)
        harness.accept_snapshot(frame("second"))
        await harness.progress_at_current_time()
        await harness.drive_until_decisions(2)
        await harness.wait_until_idle()

        assert harness.policy.timings[0].started_mono_ns == 0
        assert harness.policy.timings[0].completed_mono_ns == 910_000_000
        assert harness.policy.timings[0].completed_mono_ns < 2_000_000_000


@pytest.mark.asyncio
async def test_busy_inference_uses_real_pending_snapshot_coalescing(tmp_path: Path) -> None:
    async with RuntimeIngestionHarness(
        session_id="s_generation_coalesce",
        directory=tmp_path / "session",
        decisions=(TimedDecision(100, idle()), TimedDecision(0, idle())),
    ) as harness:
        harness.accept_snapshot(frame("initial"))
        await harness.policy.wait_until_entered(1)
        await harness.advance_ms(50)
        harness.accept_snapshot(frame("intermediate"))
        harness.accept_snapshot(frame("latest"))
        await harness.drive_until_decisions(2)
        await harness.wait_until_idle()

        snapshots = [
            record.event.payload.text
            for record in harness.session.store.policy_records()
            if isinstance(record.event, SnapshotEvent)
        ]
        assert snapshots == ["initial", "latest"]
        assert b"intermediate" not in harness.policy.observed_policy_bytes[1]
        assert harness.policy.timings[0].service_ms == 100


@pytest.mark.asyncio
async def test_timer_fire_arrives_during_virtual_policy_service(tmp_path: Path) -> None:
    instruction = "Remind me every 75 milliseconds to stretch"
    schedule = ScheduleAction(
        type="schedule",
        instruction=Span(
            event_id="e_000002",
            start_utf16=0,
            end_utf16=len(instruction),
            text=instruction,
        ),
        interval_ms=75,
        message="stretch",
    )
    config = RuntimeConfig(min_timer_interval_ms=75, max_timer_interval_ms=10_000)
    async with RuntimeIngestionHarness(
        session_id="s_generation_timer",
        directory=tmp_path / "session",
        config=config,
        decisions=(
            TimedDecision(0, schedule),
            TimedDecision(100, idle()),
            TimedDecision(0, idle()),
        ),
    ) as harness:
        harness.accept_snapshot(frame(instruction, activity="paused"))
        await harness.drive_until_decisions(3)
        await harness.wait_until_idle()

        fires = [
            record.event
            for record in harness.session.store.policy_records()
            if isinstance(record.event, TimerFireEvent)
        ]
        assert len(fires) == 1
        assert fires[0].payload.fire_count == 1
        assert fires[0].payload.late_ms == 0
        assert b'"source":"timer","kind":"fire"' in harness.policy.observed_policy_bytes[2]


@pytest.mark.asyncio
async def test_tool_result_arrives_during_virtual_policy_service(tmp_path: Path) -> None:
    fact = "lookup the Lydon score"
    delegate = DelegateAction(
        type="delegate",
        fact=Span(event_id="e_000002", start_utf16=0, end_utf16=len(fact), text=fact),
        tool=ToolName.LOOKUP,
        args=LookupArgs(query="Lydon score"),
    )
    async with RuntimeIngestionHarness(
        session_id="s_generation_tool",
        directory=tmp_path / "session",
        decisions=(
            TimedDecision(0, delegate),
            TimedDecision(100, idle()),
            TimedDecision(0, idle()),
        ),
        tool_script=lambda _action: ScriptedToolResult(
            latency_ms=60,
            data={"name": "Lydon", "score": 73},
        ),
    ) as harness:
        harness.accept_snapshot(frame(fact, activity="paused"))
        await harness.drive_until_decisions(1)
        harness.accept_snapshot(frame(f"{fact}. Waiting.", activity="active"))
        await harness.drive_until_decisions(3)
        await harness.wait_until_idle()

        results = [
            record.event
            for record in harness.session.store.policy_records()
            if isinstance(record.event, ToolResultEvent)
        ]
        assert len(results) == 1
        assert results[0].payload.data == {"name": "Lydon", "score": 73}
        assert b'"source":"tool","kind":"result"' in harness.policy.observed_policy_bytes[2]


@pytest.mark.asyncio
async def test_driver_advances_to_timer_deadline_without_dummy_ingress(tmp_path: Path) -> None:
    instruction = "Remind me every 75 milliseconds to stretch"
    schedule = ScheduleAction(
        type="schedule",
        instruction=Span(
            event_id="e_000002",
            start_utf16=0,
            end_utf16=len(instruction),
            text=instruction,
        ),
        interval_ms=75,
        message="stretch",
    )
    async with RuntimeIngestionHarness(
        session_id="s_generation_timer_gap",
        directory=tmp_path / "session",
        config=RuntimeConfig(min_timer_interval_ms=75, max_timer_interval_ms=10_000),
        decisions=(
            TimedDecision(0, schedule),
            TimedDecision(0, idle()),
            TimedDecision(0, idle()),
        ),
    ) as harness:
        harness.accept_snapshot(frame(instruction, activity="paused"))
        await harness.progress_at_current_time()
        await harness.drive_until_decisions(3)
        await harness.wait_until_idle()

        fires = [
            record.event
            for record in harness.session.store.policy_records()
            if isinstance(record.event, TimerFireEvent)
        ]
        assert len(fires) == 1
        assert harness.policy.timings[2].started_mono_ns == 75_000_000


@pytest.mark.asyncio
async def test_driver_advances_to_tool_deadline_without_dummy_ingress(tmp_path: Path) -> None:
    fact = "lookup the Lydon score"
    delegate = DelegateAction(
        type="delegate",
        fact=Span(event_id="e_000002", start_utf16=0, end_utf16=len(fact), text=fact),
        tool=ToolName.LOOKUP,
        args=LookupArgs(query="Lydon score"),
    )
    async with RuntimeIngestionHarness(
        session_id="s_generation_tool_gap",
        directory=tmp_path / "session",
        decisions=(TimedDecision(0, delegate), TimedDecision(0, idle())),
        tool_script=lambda _action: ScriptedToolResult(
            latency_ms=60, data={"name": "Lydon", "score": 73}
        ),
    ) as harness:
        harness.accept_snapshot(frame(fact, activity="paused"))
        await harness.progress_at_current_time()
        await harness.drive_until_decisions(2)
        await harness.wait_until_idle()

        results = [
            record.event
            for record in harness.session.store.policy_records()
            if isinstance(record.event, ToolResultEvent)
        ]
        assert len(results) == 1
        assert harness.policy.timings[1].started_mono_ns == 60_000_000


@pytest.mark.asyncio
async def test_harness_keeps_production_rollover_enabled(tmp_path: Path) -> None:
    async with RuntimeIngestionHarness(
        session_id="s_generation_rollover",
        directory=tmp_path / "session",
        config=RuntimeConfig(context_budget_tokens=100),
        decisions=(TimedDecision(0, idle()),),
    ) as harness:
        harness.accept_snapshot(frame("A sufficiently visible rollover probe.", activity="paused"))
        await harness.drive_until_decisions(1)
        await harness.wait_until_idle()

        checkpoints = [
            record.event
            for record in harness.session.store.policy_records()
            if isinstance(record.event, StateCheckpointEvent)
        ]
        assert len(checkpoints) == 1
        assert checkpoints[0].payload.segment.segment_index == 1


@pytest.mark.asyncio
async def test_drive_until_decisions_is_bounded_when_runtime_has_no_wake_source(
    tmp_path: Path,
) -> None:
    async with RuntimeIngestionHarness(
        session_id="s_generation_no_wake",
        directory=tmp_path / "session",
        decisions=(TimedDecision(0, idle()),),
    ) as harness:
        with pytest.raises(RuntimeError, match="completed 0 decisions; expected 1"):
            await harness.drive_until_decisions(1, max_turns=5)
