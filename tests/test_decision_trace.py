from __future__ import annotations

from pathlib import Path

import pytest

from im.canonical_json import canonicalize_tim_json
from im.config import RuntimeConfig
from im.decision_trace import build_trace, digest, exact_bytes, film_replay, read_traces
from im.generation.runtime import RuntimeIngestionHarness, TimedDecision
from im.policy.base import ScriptedIntentPolicy
from im.policy.intent import IntentResolution, ResolutionStatus
from im.scheduler import ManualClock, TimerScheduler
from im.schema.actions import RespondAction, Span
from im.schema.common import ToolResultStatus
from im.server import ArtifactPaths, RuntimeSession, load_session_artifacts
from im.store import PolicyEventDraft, Store
from im.tools import ScriptedToolResult


def _trace(**updates):
    values = {
        "decision_id": "d_000001",
        "observed_through_policy_seq": 1,
        "final_policy_seq": 1,
        "raw_provider_output": {"encoding": "utf8", "data": "raw<|im_end|>"},
        "raw_provider_output_sha256": "sha256:" + "1" * 64,
        "parser_input": {"encoding": "utf8", "data": "raw"},
        "parser_input_sha256": "sha256:" + "5" * 64,
        "parser_input_binding": "authenticated_terminal_framing",
        "parsed_raw_intent": {"type": "idle", "reason": "no_trigger", "related": None},
        "frozen_policy_sha256": "sha256:" + "2" * 64,
        "frozen_license_view_sha256": "sha256:" + "3" * 64,
        "frozen_registry_sha256": "sha256:" + "4" * 64,
        "resolution": {"status": "resolved_action", "action": {"type": "idle"}},
        "initial_license": {"status": "allowed"},
        "pending_license": {"status": "allowed"},
        "fresh_license": {"status": "not_checked"},
        "executed_event": None,
        "effect": None,
        "latency_ms": 0,
    }
    values.update(updates)
    return build_trace(**values)


def test_trace_reader_rejects_tampered_audit_hash(tmp_path: Path) -> None:
    with Store(tmp_path / "trace.sqlite3") as store:
        trace = _trace()
        store.audit("decision_trace_v1", trace.model_dump(mode="json"))
        assert read_traces(store) == (trace,)

        payload = trace.model_dump(mode="json")
        payload["latency_ms"] = 9
        store._connection.execute(
            "UPDATE audit SET payload = ? WHERE kind = 'decision_trace_v1'",
            (canonicalize_tim_json(payload),),
        )
        with pytest.raises(ValueError, match="audit hash mismatch"):
            read_traces(store)


def test_timer_fire_live_projection_is_reconstructible_from_durable_rows(
    tmp_path: Path,
) -> None:
    clock = ManualClock()
    with Store(tmp_path / "timer.sqlite3") as store:
        event_id = store.allocate_id("event")
        store.commit_policy(
            PolicyEventDraft(
                id=event_id,
                source="user",
                kind="annotation",
                payload={"text": "breathe"},
                occurred_mono_ns=clock.monotonic_ns(),
            )
        )
        scheduler = TimerScheduler(store, clock)
        timer = scheduler.schedule(
            instruction_id="i_001",
            instruction=Span(
                event_id=event_id,
                start_utf16=0,
                end_utf16=7,
                text="breathe",
            ),
            interval_ms=1_000,
            message="breathe",
        )
        clock.advance_ms(1_000)
        (fire,) = scheduler.claim_due()
        store.commit_policy(fire.draft)

        replay = film_replay(store, "s_timer")
        assert replay["events"] == [
            {
                "type": "timer_status",
                "timer_id": timer.timer_id,
                "instruction_id": "i_001",
                "interval_ms": 1_000,
                "message": "breathe",
                "status": "active",
                "next_due_in_ms": 1_000,
                "fire_count": 1,
            }
        ]


@pytest.mark.asyncio
async def test_semantic_idle_commits_trace_and_replay_without_effect(tmp_path: Path) -> None:
    root = Path(__file__).parents[1]
    config = RuntimeConfig()
    session = RuntimeSession(
        session_id="s_trace_idle",
        directory=tmp_path / "session",
        policy=ScriptedIntentPolicy(
            [{"type": "idle", "reason": "typing_active", "related": None}]
        ),
        clock=ManualClock(),
        config=config,
        artifacts=load_session_artifacts(ArtifactPaths.from_repository(root), config),
    )
    session.start()
    try:
        session.accept_snapshot(
            b'{"activity":"active","client_ts":0,"input_type":"insertText",'
            b'"is_composing":false,"selection_end":6,"selection_start":6,"text":"typing"}'
        )
        for _ in range(100):
            if read_traces(session.store):
                break
            await __import__("asyncio").sleep(0)
        traces = read_traces(session.store)
        assert len(traces) == 1
        assert traces[0].parsed_raw_intent == {
            "type": "idle",
            "reason": "typing_active",
            "related": None,
        }
        assert traces[0].executed_event is None
        replay = film_replay(session.store, session.session_id)
        assert [event["type"] for event in replay["events"]] == [
            "snapshot_projection",
            "decision_trace",
        ]
    finally:
        await session.close()


@pytest.mark.asyncio
async def test_malformed_intent_fails_closed_with_exact_output_hash(tmp_path: Path) -> None:
    raw = {"type": "mark", "broken": True}
    async with RuntimeIngestionHarness(
        session_id="s_trace_malformed",
        directory=tmp_path / "malformed",
        decisions=(TimedDecision(17, raw),),
        semantic_intents=True,
    ) as harness:
        harness.accept_snapshot(
            {
                "text": "typing",
                "selection_start": 6,
                "selection_end": 6,
                "is_composing": False,
                "input_type": "insertText",
                "activity": "active",
                "client_ts": 0,
            }
        )
        await harness.drive_until_decisions(1)
        await harness.wait_until_idle()
        (trace,) = read_traces(harness.session.store)
        assert trace.parsed_raw_intent is None
        assert trace.resolution["status"] == "failed_closed"
        assert trace.executed_event is None
        raw_bytes = canonicalize_tim_json(raw) + b"<|im_end|>"
        assert trace.raw_provider_output == exact_bytes(raw_bytes)
        assert trace.raw_provider_output_sha256 == digest(raw_bytes)
        assert trace.latency_ms == 17


@pytest.mark.asyncio
async def test_valid_but_unresolvable_intent_fails_closed(tmp_path: Path) -> None:
    raw = {
        "type": "mark",
        "instruction": {
            "kind": "visible",
            "source": "u1",
            "text": "mark",
            "occurrence": 0,
        },
        "source": "u1",
        "text": "quokka",
        "occurrence": 0,
    }
    async with RuntimeIngestionHarness(
        session_id="s_trace_unresolvable",
        directory=tmp_path / "unresolvable",
        decisions=(TimedDecision(0, raw),),
        semantic_intents=True,
    ) as harness:
        harness.accept_snapshot(
            {
                "text": "mark quokka",
                "selection_start": 11,
                "selection_end": 11,
                "is_composing": False,
                "input_type": "insertText",
                "activity": "paused",
                "client_ts": 0,
            }
        )
        await harness.drive_until_decisions(1)
        await harness.wait_until_idle()
        (trace,) = read_traces(harness.session.store)
        assert trace.parsed_raw_intent == raw
        assert trace.resolution["status"] == "failed_closed"
        assert trace.executed_event is None
        assert trace.effect is None


@pytest.mark.asyncio
async def test_pending_snapshot_block_preserves_all_three_license_stages(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def realize(request, _text):
        return IntentResolution(
            ResolutionStatus.RESOLVED_ACTION,
            RespondAction(
                type="respond",
                reply_to_event_id=request.reference_event_id,
                text="lookup failed",
            ),
        )

    monkeypatch.setattr("im.policy.intent.complete_language_realization", realize)
    delegate = {"type": "delegate", "source": "u0", "query": "quokka", "occurrence": 0}
    respond = {"type": "respond", "warrant": "r0", "response_kind": "failed_result_notice"}
    async with RuntimeIngestionHarness(
        session_id="s_trace_pending",
        directory=tmp_path / "pending",
        decisions=(
            TimedDecision(0, delegate),
            TimedDecision(100, respond),
            TimedDecision(0, {"type": "idle", "reason": "no_trigger", "related": None}),
        ),
        tool_script=lambda _action: ScriptedToolResult(
            latency_ms=1,
            data={"code": "lookup_failed", "message": "lookup failed"},
            status=ToolResultStatus.FAILED,
        ),
        semantic_intents=True,
    ) as harness:
        frame = {
            "text": "quokka",
            "selection_start": 6,
            "selection_end": 6,
            "is_composing": False,
            "input_type": "insertText",
            "activity": "paused",
            "client_ts": 0,
        }
        harness.accept_snapshot(frame)
        await harness.drive_until_decisions(1)
        await harness.advance_ms(1)
        await harness.policy.wait_until_entered(2)
        harness.accept_snapshot(
            {
                **frame,
                "text": "quokka now",
                "selection_start": 10,
                "selection_end": 10,
                "client_ts": 1,
            }
        )
        await harness.drive_until_decisions(3)
        await harness.wait_until_idle()
        trace = read_traces(harness.session.store)[1]
        assert trace.initial_license["status"] == "allowed"
        assert trace.pending_license == {"status": "blocked", "code": "stale_decision"}
        assert trace.fresh_license == {"status": "not_checked"}
        assert trace.executed_event is None


@pytest.mark.asyncio
async def test_initial_hard_block_is_terminal_and_effect_free(tmp_path: Path) -> None:
    text = "Remind me every five seconds to stretch."
    schedule = {
        "type": "schedule",
        "instruction": {
            "kind": "visible",
            "source": "u0",
            "text": text,
            "occurrence": 0,
        },
    }
    async with RuntimeIngestionHarness(
        session_id="s_trace_initial_block",
        directory=tmp_path / "initial-block",
        decisions=(TimedDecision(0, schedule),),
        config=RuntimeConfig(min_timer_interval_ms=1_000, max_timer_interval_ms=2_000),
        semantic_intents=True,
    ) as harness:
        frame = {
            "text": text,
            "selection_start": len(text),
            "selection_end": len(text),
            "is_composing": False,
            "input_type": "insertText",
            "activity": "paused",
            "client_ts": 0,
        }
        harness.accept_snapshot(frame)
        await harness.drive_until_decisions(1)
        await harness.wait_until_idle()
        trace = read_traces(harness.session.store)[0]
        assert trace.initial_license == {
            "status": "blocked",
            "code": "timer_limit_exceeded",
        }
        assert trace.pending_license == {"status": "not_checked"}
        assert trace.fresh_license == {"status": "not_checked"}
        assert trace.executed_event is None
        assert trace.effect is None
