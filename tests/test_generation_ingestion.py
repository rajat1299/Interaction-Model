"""Runtime-backed generation ingestion tests."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from im.assets.model import Split
from im.canonical_json import canonicalize_tim_json
from im.config import RuntimeConfig
from im.generation.ingestion import (
    RuntimeIngestionRunner,
    ScheduledSamplerFrame,
)
from im.generation.timing import TimingPopulation, TimingSeed, materialize_timing_plan
from im.schema.actions import IdleAction
from im.schema.events import StateCheckpointEvent
from im.serialize import parse_event


def raw_frame(text: str) -> bytes:
    cursor = len(text.encode("utf-16-le")) // 2
    return canonicalize_tim_json(
        {
            "text": text,
            "selection_start": cursor,
            "selection_end": cursor,
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
    name: str,
    count: int = 1,
    population: TimingPopulation = TimingPopulation.TRAINING,
    config: RuntimeConfig | None = None,
) -> RuntimeIngestionRunner:
    plan = materialize_timing_plan(TimingSeed(Split.TEST, name, population), count)
    return RuntimeIngestionRunner(
        session_id=f"s_{name}",
        directory=tmp_path / name,
        timing_plan=plan,
        scripted_attempts=tuple(idle() for _ in range(count)),
        template_id="neutral-typing-v1",
        asset_ids=("a_alpha", "a_beta"),
        master_seed="generation-seed",
        config=config,
    )


@pytest.mark.asyncio
async def test_identical_runs_preserve_raw_frames_hashes_prefixes_and_timing(
    tmp_path: Path,
) -> None:
    plan = materialize_timing_plan(TimingSeed(Split.TEST, "same"), 1)
    frames = (ScheduledSamplerFrame(0, raw_frame("draft 😀")),)
    first = RuntimeIngestionRunner(
        session_id="s_same",
        directory=tmp_path / "first",
        timing_plan=plan,
        scripted_attempts=(idle(),),
        template_id="neutral-typing-v1",
        asset_ids=("a_alpha", "a_beta"),
        master_seed="generation-seed",
    )
    second = RuntimeIngestionRunner(
        session_id="s_same",
        directory=tmp_path / "second",
        timing_plan=plan,
        scripted_attempts=(idle(),),
        template_id="neutral-typing-v1",
        asset_ids=("a_beta", "a_alpha"),
        master_seed="generation-seed",
    )

    left = await first.run(frames)
    right = await second.run(frames)

    assert left.sha256 == right.sha256
    assert left.capture_sha256 == right.capture_sha256
    assert left.provenance.identity == right.provenance.identity
    assert left.segments == right.segments
    assert left.decisions == right.decisions
    assert left.sha256 != left.capture_sha256
    assert left.decisions[0].timing.service_ms == plan.service_ms[0]
    with sqlite3.connect(left.database_path) as connection:
        payload = connection.execute(
            "SELECT payload FROM ingress WHERE source = 'user' ORDER BY rowid"
        ).fetchone()
    assert payload == (frames[0].raw_bytes,)


@pytest.mark.asyncio
async def test_exact_frame_schedule_changes_derived_regeneration_identity(tmp_path: Path) -> None:
    alpha = await runner(tmp_path, name="identity-alpha").run(
        (ScheduledSamplerFrame(0, raw_frame("alpha")),)
    )
    beta_runner = RuntimeIngestionRunner(
        session_id="s_identity_beta",
        directory=tmp_path / "identity-beta",
        timing_plan=alpha.timing_plan,
        scripted_attempts=(idle(),),
        template_id=alpha.provenance.template_id,
        asset_ids=alpha.provenance.asset_ids,
        master_seed=alpha.provenance.master_seed,
    )
    beta = await beta_runner.run((ScheduledSamplerFrame(0, raw_frame("beta")),))

    assert alpha.provenance.frame_schedule_hash != beta.provenance.frame_schedule_hash
    assert alpha.provenance.identity != beta.provenance.identity


@pytest.mark.asyncio
async def test_tied_schedule_is_stable_and_decreasing_schedule_is_rejected(tmp_path: Path) -> None:
    first = ScheduledSamplerFrame(0, raw_frame("first"))
    second = ScheduledSamplerFrame(0, raw_frame("second"))
    stream = await runner(tmp_path, name="ties", count=2).run((first, second))

    assert stream.frames == (first, second)
    with sqlite3.connect(stream.database_path) as connection:
        payloads = tuple(
            row[0]
            for row in connection.execute(
                "SELECT payload FROM ingress WHERE source = 'user' ORDER BY rowid"
            )
        )
    assert payloads == (first.raw_bytes, second.raw_bytes)

    with pytest.raises(ValueError, match="nondecreasing"):
        await runner(tmp_path, name="decreasing").run(
            (ScheduledSamplerFrame(1, second.raw_bytes), first)
        )


@pytest.mark.asyncio
async def test_real_rollover_captures_multiple_segments_only_at_checkpoint(tmp_path: Path) -> None:
    stream = await runner(
        tmp_path,
        name="rollover",
        config=RuntimeConfig(context_budget_tokens=100),
    ).run((ScheduledSamplerFrame(0, raw_frame("A sufficiently visible rollover probe.")),))

    assert len(stream.segments) == 2
    checkpoint = parse_event(stream.segments[1].policy_bytes.splitlines()[0])
    assert isinstance(checkpoint, StateCheckpointEvent)
    assert checkpoint.payload.segment.covers_through_policy_seq >= 0


@pytest.mark.asyncio
async def test_stress_population_is_preserved_in_separate_provenance(tmp_path: Path) -> None:
    stream = await runner(
        tmp_path,
        name="stress",
        population=TimingPopulation.STRESS_EVAL,
    ).run((ScheduledSamplerFrame(0, raw_frame("stress input")),))

    assert stream.population is TimingPopulation.STRESS_EVAL
    assert stream.provenance.population is TimingPopulation.STRESS_EVAL
