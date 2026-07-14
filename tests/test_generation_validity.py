"""Reopen and corruption checks for generated-stream validity."""

from __future__ import annotations

import sqlite3
from dataclasses import replace
from pathlib import Path

import pytest

from im.assets.model import Split
from im.canonical_json import canonicalize_tim_json
from im.config import RuntimeConfig
from im.generation.ingestion import (
    CapturedSegment,
    RuntimeIngestionRunner,
    ScheduledSamplerFrame,
)
from im.generation.timing import TimingSeed, materialize_timing_plan
from im.generation.validity import GeneratedStreamValidationError, validate_generated_stream
from im.schema.actions import (
    DelegateAction,
    IdleAction,
    LookupArgs,
    RespondAction,
    ScheduleAction,
    Span,
)
from im.schema.common import ToolName
from im.tools import ScriptedToolResult


def raw_frame(text: str) -> bytes:
    return canonicalize_tim_json(
        {
            "text": text,
            "selection_start": len(text),
            "selection_end": len(text),
            "is_composing": False,
            "input_type": "insertText",
            "activity": "paused",
            "client_ts": 0,
        }
    )


def idle() -> IdleAction:
    return IdleAction(type="idle", reason="no_trigger", related_event_id=None)


def runner(
    tmp_path: Path,
    *,
    name: str = "session",
    attempts: tuple[object, ...] | None = None,
) -> RuntimeIngestionRunner:
    scripted = (idle(),) if attempts is None else attempts
    plan = materialize_timing_plan(TimingSeed(Split.TEST, f"validity-{name}"), len(scripted))
    return RuntimeIngestionRunner(
        session_id=f"s_validity_{name}",
        directory=tmp_path / name,
        timing_plan=plan,
        scripted_attempts=scripted,
        template_id="validity-v1",
        asset_ids=("a_validity",),
        master_seed="seed",
    )


@pytest.mark.asyncio
async def test_validity_reopens_store_and_reconstructs_final_license_view(tmp_path: Path) -> None:
    stream = await runner(tmp_path).run((ScheduledSamplerFrame(0, raw_frame("hello")),))

    assert validate_generated_stream(stream) == stream.final_license_view


@pytest.mark.asyncio
async def test_validity_rejects_corruption_and_forged_segment_boundary(tmp_path: Path) -> None:
    stream = await runner(tmp_path, name="boundary").run(
        (ScheduledSamplerFrame(0, raw_frame("hello")),)
    )
    forged = replace(
        stream,
        segments=(CapturedSegment(1, stream.segments[0].policy_bytes),),
    )
    with pytest.raises(GeneratedStreamValidationError, match="indices"):
        validate_generated_stream(forged)

    with sqlite3.connect(stream.database_path) as connection:
        connection.execute("UPDATE policy SET rendered = ? WHERE seq = 0", (b"{}",))
        connection.commit()
    with pytest.raises(GeneratedStreamValidationError, match="policy bytes"):
        validate_generated_stream(stream)


@pytest.mark.asyncio
async def test_validity_rejects_corrupt_ingress_and_swapped_valid_prefixes(
    tmp_path: Path,
) -> None:
    corrupt = await runner(tmp_path, name="ingress").run(
        (ScheduledSamplerFrame(0, raw_frame("hello")),)
    )
    with sqlite3.connect(corrupt.database_path) as connection:
        connection.execute("UPDATE ingress SET payload = ? WHERE source = 'user'", (b"{}",))
        connection.commit()
    with pytest.raises(GeneratedStreamValidationError, match="ingress"):
        validate_generated_stream(corrupt)

    frames = (
        ScheduledSamplerFrame(0, raw_frame("first")),
        ScheduledSamplerFrame(2_000, raw_frame("second")),
    )
    stream = await runner(tmp_path, name="prefixes", attempts=(idle(), idle())).run(frames)
    first, second = stream.decisions
    swapped = replace(
        stream,
        decisions=(
            replace(first, prefix_bytes=second.prefix_bytes),
            replace(second, prefix_bytes=first.prefix_bytes),
        ),
    )
    with pytest.raises(GeneratedStreamValidationError, match="exact audit seq"):
        validate_generated_stream(swapped)


@pytest.mark.asyncio
async def test_blocked_scripted_non_idle_action_rejects_complete_stream(tmp_path: Path) -> None:
    blocked = RespondAction(type="respond", reply_to_event_id="e_999999", text="Nope")

    with pytest.raises(GeneratedStreamValidationError, match="blocked"):
        await runner(tmp_path, name="blocked", attempts=(blocked,)).run(
            (ScheduledSamplerFrame(0, raw_frame("hello")),)
        )


@pytest.mark.asyncio
async def test_validity_rejects_one_nanosecond_timer_and_tool_due_corruption(
    tmp_path: Path,
) -> None:
    instruction = "Remind me every two seconds to stretch"
    schedule = ScheduleAction(
        type="schedule",
        instruction=Span(
            event_id="e_000002",
            start_utf16=0,
            end_utf16=len(instruction),
            text=instruction,
        ),
        interval_ms=2_000,
        message="stretch",
    )
    timer_plan = materialize_timing_plan(TimingSeed(Split.TEST, "validity-timer"), 3)
    timer_runner = RuntimeIngestionRunner(
        session_id="s_validity_timer",
        directory=tmp_path / "timer",
        timing_plan=timer_plan,
        scripted_attempts=(schedule, idle(), idle()),
        template_id="validity-timer-v1",
        asset_ids=("a_timer",),
        master_seed="seed",
        config=RuntimeConfig(max_timer_interval_ms=10_000),
    )
    timer_stream = await timer_runner.run((ScheduledSamplerFrame(0, raw_frame(instruction)),))
    with sqlite3.connect(timer_stream.database_path) as connection:
        connection.execute("UPDATE timers SET next_due_mono_ns = next_due_mono_ns + 1")
        connection.commit()
    with pytest.raises(GeneratedStreamValidationError, match="ledgers"):
        validate_generated_stream(timer_stream)

    fact = "lookup the Lydon score"
    delegate = DelegateAction(
        type="delegate",
        fact=Span(event_id="e_000002", start_utf16=0, end_utf16=len(fact), text=fact),
        tool=ToolName.LOOKUP,
        args=LookupArgs(query="Lydon score"),
    )
    tool_plan = materialize_timing_plan(TimingSeed(Split.TEST, "validity-tool"), 2)
    tool_runner = RuntimeIngestionRunner(
        session_id="s_validity_tool",
        directory=tmp_path / "tool",
        timing_plan=tool_plan,
        scripted_attempts=(delegate, idle()),
        template_id="validity-tool-v1",
        asset_ids=("a_tool",),
        master_seed="seed",
        tool_script=lambda _action: ScriptedToolResult(
            latency_ms=60, data={"name": "Lydon", "score": 73}
        ),
    )
    tool_stream = await tool_runner.run((ScheduledSamplerFrame(0, raw_frame(fact)),))
    with sqlite3.connect(tool_stream.database_path) as connection:
        connection.execute("UPDATE tool_requests SET due_mono_ns = due_mono_ns + 1")
        connection.commit()
    with pytest.raises(GeneratedStreamValidationError, match="ledgers"):
        validate_generated_stream(tool_stream)
