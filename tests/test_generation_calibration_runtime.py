from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from im.canonical_json import canonicalize_tim_json, parse_tim_json
from im.generation.ingestion import ScheduledSamplerFrame
from im.generation.runtime import RuntimeIngestionHarness
from im.policy.latency_stub import D1LatencySampler, latency_stub_metadata
from im.schema.events import ActionExecutedEvent, SnapshotEvent
from im.serialize import parse_event


def _frame(text: str, client_ts: int) -> bytes:
    cursor = len(text.encode("utf-16-le")) // 2
    return canonicalize_tim_json(
        {
            "text": text,
            "selection_start": cursor,
            "selection_end": cursor,
            "is_composing": False,
            "input_type": "insertText",
            "activity": "active",
            "client_ts": client_ts,
        }
    )


def _audits(database_path: Path, kind: str) -> list[dict[str, object]]:
    with sqlite3.connect(database_path) as connection:
        rows = connection.execute(
            "SELECT payload FROM audit WHERE kind = ? ORDER BY rowid", (kind,)
        ).fetchall()
    return [parse_tim_json(bytes(row[0])) for row in rows]  # type: ignore[list-item]


@pytest.mark.asyncio
async def test_calibration_replay_records_sampler_draws_and_finalizes_sqlite(
    tmp_path: Path,
) -> None:
    session_id = "s_calibration_runtime"
    harness = RuntimeIngestionHarness.calibration(
        session_id=session_id, directory=tmp_path / "session"
    )
    database_path = await harness.replay_calibration(
        (
            ScheduledSamplerFrame(0, _frame("first", 11)),
            ScheduledSamplerFrame(1_000, _frame("second", 22)),
        )
    )

    sampler = D1LatencySampler(session_id)
    assert database_path == tmp_path / "session" / "session.sqlite3"
    assert database_path.is_file()
    assert not database_path.with_name("session.sqlite3-wal").exists()
    assert [timing.service_ms for timing in harness.policy.timings] == [
        sampler.draw_ms(0),
        sampler.draw_ms(1),
    ]

    attempts = _audits(database_path, "action_attempt")
    assert [attempt["calibration"] for attempt in attempts] == [
        {"decision_index": 0, "planned_latency_ms": sampler.draw_ms(0)},
        {"decision_index": 1, "planned_latency_ms": sampler.draw_ms(1)},
    ]
    assert [attempt["raw"] for attempt in attempts] == [
        {"type": "idle", "reason": "no_trigger", "related_event_id": None},
        {"type": "idle", "reason": "no_trigger", "related_event_id": None},
    ]

    with sqlite3.connect(database_path) as connection:
        completion = parse_tim_json(
            bytes(
                connection.execute(
                    "SELECT payload FROM audit WHERE kind = 'calibration_completed'"
                ).fetchone()[0]
            )
        )
        metadata = parse_tim_json(
            bytes(
                connection.execute(
                    "SELECT value FROM meta WHERE key = 'calibration_latency'"
                ).fetchone()[0]
            )
        )
        policy_events = [
            parse_event(bytes(row[0]))
            for row in connection.execute("SELECT rendered FROM policy ORDER BY seq")
        ]
        provider_call_count = connection.execute("SELECT COUNT(*) FROM policy_calls").fetchone()[0]

    assert completion == {
        "runtime_session_id": session_id,
        "completed_mono_ns": 1_900_000_000,
        "sampler_frame_count": 2,
        "last_client_ts": 22,
    }
    assert metadata == latency_stub_metadata(session_id)
    assert not any(isinstance(event, ActionExecutedEvent) for event in policy_events)
    assert provider_call_count == 0


@pytest.mark.asyncio
async def test_calibration_replay_coalesces_multiple_busy_frames(tmp_path: Path) -> None:
    session_id = "s_calibration_coalesce"
    harness = RuntimeIngestionHarness.calibration(
        session_id=session_id, directory=tmp_path / "session"
    )
    database_path = await harness.replay_calibration(
        (
            ScheduledSamplerFrame(0, _frame("initial", 1)),
            ScheduledSamplerFrame(1, _frame("intermediate", 2)),
            ScheduledSamplerFrame(2, _frame("latest", 3)),
        )
    )

    sampler = D1LatencySampler(session_id)
    assert [timing.service_ms for timing in harness.policy.timings] == [
        sampler.draw_ms(0),
        sampler.draw_ms(1),
    ]
    with sqlite3.connect(database_path) as connection:
        snapshots = [
            parse_event(bytes(row[0])).payload.text
            for row in connection.execute("SELECT rendered FROM policy ORDER BY seq")
            if isinstance(parse_event(bytes(row[0])), SnapshotEvent)
        ]
    assert snapshots == ["initial", "latest"]

    starts = _audits(database_path, "decision_started")
    assert starts[1]["arrivals"] == [
        {
            "event_id": "e_000003",
            "source": "user",
            "kind": "snapshot",
            "arrived_while_inferring": True,
            "replaced_pending_snapshot": False,
        },
        {
            "event_id": "e_000004",
            "source": "user",
            "kind": "snapshot",
            "arrived_while_inferring": True,
            "replaced_pending_snapshot": True,
        },
    ]
