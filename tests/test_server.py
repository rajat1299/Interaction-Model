"""Raw WebSocket transport, session artifacts, and full scripted runtime tests."""

import asyncio
import sqlite3
import time
from hashlib import sha256
from pathlib import Path

import anyio
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from im.canonical_json import canonicalize_tim_json
from im.config import RuntimeConfig
from im.policy.base import ScriptedPolicy
from im.policy.latency_stub import LatencyStubPolicy
from im.scheduler import ManualClock
from im.schema.events import SessionStartEvent, SnapshotEvent, TimerFireEvent
from im.server import (
    ArtifactPaths,
    RuntimeSession,
    SessionUnavailableError,
    create_app,
    load_session_artifacts,
)


def sampler_frame(
    text: str,
    *,
    activity: str = "active",
    input_type: str | None = "insertText",
    client_ts: int = 1,
) -> dict[str, object]:
    return {
        "text": text,
        "selection_start": len(text),
        "selection_end": len(text),
        "is_composing": False,
        "input_type": input_type,
        "activity": activity,
        "client_ts": client_ts,
    }


async def wait_for_calls(policy: ScriptedPolicy, count: int) -> None:
    for _ in range(100):
        if policy.call_count >= count:
            return
        await asyncio.sleep(0)
    raise AssertionError(f"policy reached {policy.call_count} calls, expected {count}")


class GatedScriptedPolicy(ScriptedPolicy):
    """A deterministic script whose selected inference calls pause for test ingress."""

    def __init__(self, actions: list[object], gated_calls: set[int]) -> None:
        super().__init__(actions)
        self.entered = {call: asyncio.Event() for call in gated_calls}
        self.release = {call: asyncio.Event() for call in gated_calls}

    async def decide(self, policy_bytes: bytes) -> object:
        call = self.call_count + 1
        if call in self.entered:
            self.entered[call].set()
            await self.release[call].wait()
        return await super().decide(policy_bytes)


class FailingGatedPolicy:
    def __init__(self) -> None:
        self.entered = asyncio.Event()
        self.release = asyncio.Event()

    async def decide(self, _policy_bytes: bytes) -> object:
        self.entered.set()
        await self.release.wait()
        raise RuntimeError("calibration policy failed")


class FailingClosePolicy(ScriptedPolicy):
    async def aclose(self) -> None:
        raise RuntimeError("close failed")


class TrackingClosePolicy(ScriptedPolicy):
    def __init__(self) -> None:
        super().__init__([])
        self.closed = False

    async def aclose(self) -> None:
        self.closed = True


class FailingSocket:
    async def close(self, *, code: int) -> None:
        del code
        raise OSError("socket close failed")


async def wait_for_ingress(
    session: RuntimeSession,
    source: str,
    kind: str,
    count: int,
) -> None:
    for _ in range(200):
        actual = session.store._connection.execute(
            "SELECT COUNT(*) FROM ingress WHERE source = ? AND kind = ?",
            (source, kind),
        ).fetchone()[0]
        if actual >= count:
            return
        await asyncio.sleep(0)
    raise AssertionError(f"{source}.{kind} ingress reached {actual}, expected {count}")


def test_session_start_uses_exact_real_artifact_preimages(tmp_path: Path) -> None:
    config = RuntimeConfig(
        min_timer_interval_ms=2_000,
        max_timer_interval_ms=60_000,
        max_active_timers=3,
        max_timer_message_bytes=128,
    )
    app = create_app(
        session_root=tmp_path,
        config=config,
        policy_factory=lambda _session_id: ScriptedPolicy([]),
        clock_factory=lambda _session_id: ManualClock(),
    )

    with TestClient(app) as client:
        response = client.post("/session")
        assert response.status_code == 200
        session_id = response.json()["session_id"]
        session: RuntimeSession = app.state.session_registry.get(session_id)

        def inspect() -> tuple[object, object, object, object, bytes, list[tuple[object, ...]]]:
            record = session.store.policy_records()[0]
            return (
                record.event,
                session.store.get_meta("runtime_config"),
                session.store.get_meta("runtime_session_id"),
                session.store.get_meta("artifact_hashes"),
                record.rendered,
                session.store._connection.execute(
                    "SELECT id, source, kind, payload FROM ingress ORDER BY id"
                ).fetchall(),
            )

        event, stored_config, stored_session_id, artifact_hashes, rendered, ingress = (
            client.portal.call(inspect)
        )

    assert isinstance(event, SessionStartEvent)
    assert event.id == "e_000001"
    assert event.seq == 0
    assert event.dt_ms == 0
    assert event.payload.capabilities.model_dump(mode="python") == config.timer_capabilities()
    assert stored_config == config.as_json_object()
    assert stored_session_id == session_id
    assert artifact_hashes == {
        "config": event.payload.config_hash,
        "prompt": event.payload.prompt_hash,
        "schema": event.payload.schema_hash,
        "spec": event.payload.spec_hash,
    }
    assert ingress == [
        (
            "e_000001",
            "runtime",
            "session_start",
            canonicalize_tim_json(event.payload.model_dump(mode="json")),
        )
    ]
    assert rendered.startswith(b'{"v":1,"id":"e_000001","seq":0,"dt_ms":0')

    repo = Path(__file__).resolve().parents[1]
    event_bytes = (repo / "spec/schema/event-v1.json").read_bytes()
    action_bytes = (repo / "spec/schema/action-v1.json").read_bytes()
    spec_bytes = (repo / "spec/behavior-spec.md").read_bytes()
    prompt_bytes = (repo / "spec/prompt-template-v1.txt").read_bytes()
    schema_digest = sha256(event_bytes + b"\n" + action_bytes).hexdigest()
    assert event.payload.schema_hash == f"sha256:{schema_digest}"
    assert event.payload.spec_hash == f"sha256:{sha256(spec_bytes).hexdigest()}"
    assert event.payload.prompt_hash == f"sha256:{sha256(prompt_bytes).hexdigest()}"
    retained_preimages = {
        "schema": event_bytes + b"\n" + action_bytes,
        "spec": spec_bytes,
        "prompt": prompt_bytes,
        "config": canonicalize_tim_json(config.as_json_object()),
    }
    for name, preimage in retained_preimages.items():
        digest = artifact_hashes[name].removeprefix("sha256:")
        assert (tmp_path / session_id / "artifacts/sha256" / digest).read_bytes() == preimage


def test_calibration_session_opt_in_records_decision_measurements(tmp_path: Path) -> None:
    async def no_sleep(_delay: float) -> None:
        return None

    policies: list[LatencyStubPolicy] = []

    def calibration_policy(session_id: str) -> LatencyStubPolicy:
        policy = LatencyStubPolicy(session_id, sleep=no_sleep)
        policies.append(policy)
        return policy

    app = create_app(
        session_root=tmp_path,
        policy_factory=lambda _session_id: ScriptedPolicy([]),
        calibration_policy_factory=calibration_policy,
        clock_factory=lambda _session_id: ManualClock(),
    )

    with TestClient(app) as client:
        session_id = client.post("/session?calibration=true").json()["session_id"]
        policy = policies[0]
        session: RuntimeSession = app.state.session_registry.get(session_id)
        with client.websocket_connect(f"/session/{session_id}") as websocket:
            websocket.send_json(sampler_frame("calibrate", activity="paused"))
            client.portal.call(wait_for_calls, policy, 1)
            websocket.send_json(
                sampler_frame("calibrate again", activity="paused", client_ts=1)
            )
            client.portal.call(wait_for_calls, policy, 2)
            completed = client.post(
                f"/session/{session_id}/calibration-complete",
                json={"last_client_ts": 1, "sampler_frame_count": 2},
            )
            assert completed.status_code == 200
            assert completed.json() == {"completed": True}

        def audit_kinds() -> list[str]:
            return [
                str(row[0])
                for row in session.store._connection.execute(
                    "SELECT kind FROM audit ORDER BY rowid"
                )
            ]

        kinds = client.portal.call(audit_kinds)
        completion = client.portal.call(
            session.store.get_meta, "calibration_completed"
        )

    assert kinds == [
        "decision_started",
        "decision_finished",
        "action_attempt",
        "decision_started",
        "decision_finished",
        "action_attempt",
        "calibration_completed",
    ]
    assert completion == {
        "runtime_session_id": session_id,
        "completed_mono_ns": 0,
        "sampler_frame_count": 2,
        "last_client_ts": 1,
    }


def test_non_calibration_session_cannot_be_completed(tmp_path: Path) -> None:
    app = create_app(
        session_root=tmp_path,
        policy_factory=lambda _session_id: ScriptedPolicy([]),
        clock_factory=lambda _session_id: ManualClock(),
    )

    with TestClient(app) as client:
        session_id = client.post("/session").json()["session_id"]
        response = client.post(
            f"/session/{session_id}/calibration-complete",
            json={"last_client_ts": None, "sampler_frame_count": 0},
        )

    assert response.status_code == 409
    assert response.json() == {"detail": "session is not a calibration recording"}


@pytest.mark.asyncio
async def test_calibration_completion_cannot_hide_actor_failure(tmp_path: Path) -> None:
    repo = Path(__file__).resolve().parents[1]
    config = RuntimeConfig()
    policy = FailingGatedPolicy()
    session = RuntimeSession(
        session_id="s_failed_calibration",
        directory=tmp_path / "s_failed_calibration",
        policy=policy,
        clock=ManualClock(),
        config=config,
        artifacts=load_session_artifacts(ArtifactPaths.from_repository(repo), config),
        measurement_audits=True,
    )
    session.start()
    session.accept_snapshot(canonicalize_tim_json(sampler_frame("fails")))
    await policy.entered.wait()
    completion = asyncio.create_task(session.complete_calibration(1, 1))
    await asyncio.sleep(0)
    policy.release.set()

    with pytest.raises(SessionUnavailableError, match="session runtime failed"):
        await completion
    with pytest.raises(SessionUnavailableError, match="session runtime failed"):
        await session.complete_calibration(1, 1)
    kinds = [
        str(row[0])
        for row in session.store._connection.execute("SELECT kind FROM audit ORDER BY rowid")
    ]
    assert kinds == ["decision_started", "decision_finished", "session_runtime_failed"]
    assert session.store.get_meta("calibration_completed") is None
    await session.close()


@pytest.mark.asyncio
async def test_session_close_releases_store_when_policy_close_fails(tmp_path: Path) -> None:
    repo = Path(__file__).resolve().parents[1]
    config = RuntimeConfig()
    session = RuntimeSession(
        session_id="s_close_failure",
        directory=tmp_path / "s_close_failure",
        policy=FailingClosePolicy([]),
        clock=ManualClock(),
        config=config,
        artifacts=load_session_artifacts(ArtifactPaths.from_repository(repo), config),
    )

    with pytest.raises(RuntimeError, match="close failed"):
        await session.close()

    with pytest.raises(sqlite3.ProgrammingError, match="closed database"):
        session.store._connection.execute("SELECT 1")


@pytest.mark.asyncio
async def test_session_close_finishes_cleanup_when_socket_close_fails(tmp_path: Path) -> None:
    repo = Path(__file__).resolve().parents[1]
    config = RuntimeConfig()
    policy = TrackingClosePolicy()
    session = RuntimeSession(
        session_id="s_socket_close_failure",
        directory=tmp_path / "s_socket_close_failure",
        policy=policy,
        clock=ManualClock(),
        config=config,
        artifacts=load_session_artifacts(ArtifactPaths.from_repository(repo), config),
    )
    session._socket = FailingSocket()  # type: ignore[assignment]

    with pytest.raises(OSError, match="socket close failed"):
        await session.close()

    assert policy.closed is True
    with pytest.raises(sqlite3.ProgrammingError, match="closed database"):
        session.store._connection.execute("SELECT 1")


def test_raw_duplicate_key_frame_is_retained_then_rejected(tmp_path: Path) -> None:
    app = create_app(
        session_root=tmp_path,
        policy_factory=lambda _session_id: ScriptedPolicy([]),
        clock_factory=lambda _session_id: ManualClock(),
    )
    raw = (
        b'{"text":"a","text":"b","selection_start":1,"selection_end":1,'
        b'"is_composing":false,"input_type":"insertText","activity":"active",'
        b'"client_ts":1}'
    )

    with TestClient(app) as client:
        session_id = client.post("/session").json()["session_id"]
        session: RuntimeSession = app.state.session_registry.get(session_id)
        with client.websocket_connect(f"/session/{session_id}") as websocket:
            websocket.send_text(raw.decode("utf-8"))
            assert websocket.receive()["type"] == "websocket.close"

        def inspect() -> tuple[bytes, str]:
            payload = session.store._connection.execute(
                "SELECT payload FROM ingress WHERE source = 'user'"
            ).fetchone()[0]
            audit_kind = session.store._connection.execute(
                "SELECT kind FROM audit ORDER BY rowid DESC LIMIT 1"
            ).fetchone()[0]
            return bytes(payload), str(audit_kind)

        retained, audit_kind = client.portal.call(inspect)

    assert retained == raw
    assert audit_kind == "ingress_rejected"


def test_binary_frame_is_retained_and_audited_before_transport_rejection(tmp_path: Path) -> None:
    app = create_app(
        session_root=tmp_path,
        policy_factory=lambda _session_id: ScriptedPolicy([]),
        clock_factory=lambda _session_id: ManualClock(),
    )
    raw = b"\xff\x00not-a-text-frame"

    with TestClient(app) as client:
        session_id = client.post("/session").json()["session_id"]
        session: RuntimeSession = app.state.session_registry.get(session_id)
        with client.websocket_connect(f"/session/{session_id}") as websocket:
            websocket.send_bytes(raw)
            close = websocket.receive()
            assert close["type"] == "websocket.close"
            assert close["code"] == 1003

        def inspect() -> tuple[bytes, str]:
            payload = session.store._connection.execute(
                "SELECT payload FROM ingress WHERE source = 'user'"
            ).fetchone()[0]
            audit = session.store._connection.execute(
                "SELECT kind FROM audit ORDER BY rowid DESC LIMIT 1"
            ).fetchone()[0]
            return bytes(payload), str(audit)

        retained, audit_kind = client.portal.call(inspect)

    assert retained == raw
    assert audit_kind == "ingress_rejected"


def test_session_specific_json_limits_reject_after_raw_retention(tmp_path: Path) -> None:
    config = RuntimeConfig(max_json_bytes=300, max_json_string_bytes=100)
    app = create_app(
        session_root=tmp_path,
        config=config,
        policy_factory=lambda _session_id: ScriptedPolicy([]),
        clock_factory=lambda _session_id: ManualClock(),
    )
    frame = sampler_frame("x" * 120)
    raw = canonicalize_tim_json(frame)

    with TestClient(app) as client:
        session_id = client.post("/session").json()["session_id"]
        session: RuntimeSession = app.state.session_registry.get(session_id)
        with client.websocket_connect(f"/session/{session_id}") as websocket:
            websocket.send_text(raw.decode("utf-8"))
            assert websocket.receive()["type"] == "websocket.close"

        def inspect() -> tuple[bytes, int]:
            payload = session.store._connection.execute(
                "SELECT payload FROM ingress WHERE source = 'user'"
            ).fetchone()[0]
            committed = sum(
                isinstance(record.event, SnapshotEvent)
                for record in session.store.policy_records()
            )
            return bytes(payload), committed

        retained, committed = client.portal.call(inspect)

    assert retained == raw
    assert committed == 0


def test_second_socket_is_rejected_and_reconnect_after_detach_succeeds(tmp_path: Path) -> None:
    app = create_app(
        session_root=tmp_path,
        policy_factory=lambda _session_id: ScriptedPolicy([]),
        clock_factory=lambda _session_id: ManualClock(),
    )
    with TestClient(app) as client:
        session_id = client.post("/session").json()["session_id"]
        with client.websocket_connect(f"/session/{session_id}"):
            with pytest.raises(WebSocketDisconnect) as rejected:
                with client.websocket_connect(f"/session/{session_id}"):
                    pass
            assert rejected.value.code == 1008
        with client.websocket_connect(f"/session/{session_id}"):
            pass


def test_shutdown_cancels_a_policy_blocked_in_inference(tmp_path: Path) -> None:
    class BlockingPolicy:
        def __init__(self) -> None:
            self.entered = asyncio.Event()
            self.canceled = False

        async def decide(self, _policy_bytes: bytes) -> object:
            self.entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                self.canceled = True

    policy = BlockingPolicy()
    app = create_app(
        session_root=tmp_path,
        policy_factory=lambda _session_id: policy,
        clock_factory=lambda _session_id: ManualClock(),
    )
    started = time.monotonic()
    with TestClient(app) as client:
        session_id = client.post("/session").json()["session_id"]
        with client.websocket_connect(f"/session/{session_id}") as websocket:
            websocket.send_json(sampler_frame("still deciding"))
            client.portal.call(policy.entered.wait)

    assert time.monotonic() - started < 1
    assert policy.canceled is True


def test_paused_activity_and_edit_kind_are_server_committed_facts(tmp_path: Path) -> None:
    policy = ScriptedPolicy(
        [
            {"type": "idle", "reason": "typing_active", "related_event_id": None},
            {"type": "idle", "reason": "no_trigger", "related_event_id": None},
        ]
    )
    app = create_app(
        session_root=tmp_path,
        policy_factory=lambda _session_id: policy,
        clock_factory=lambda _session_id: ManualClock(),
    )

    with TestClient(app) as client:
        session_id = client.post("/session").json()["session_id"]
        session: RuntimeSession = app.state.session_registry.get(session_id)
        with client.websocket_connect(f"/session/{session_id}") as websocket:
            websocket.send_json(sampler_frame("hello"))
            client.portal.call(wait_for_calls, policy, 1)
            websocket.send_json(
                sampler_frame("hello", activity="paused", input_type=None, client_ts=2)
            )
            client.portal.call(wait_for_calls, policy, 2)

        def snapshots() -> list[SnapshotEvent]:
            return [
                record.event
                for record in session.store.policy_records()
                if isinstance(record.event, SnapshotEvent)
            ]

        committed = client.portal.call(snapshots)

    assert [event.activity.value for event in committed] == ["active", "paused"]
    assert [event.payload.edit_kind.value for event in committed] == ["insert", "none"]


def test_server_rollover_emits_notice_only_after_checkpoint_commit(tmp_path: Path) -> None:
    config = RuntimeConfig(context_budget_tokens=100)
    policy = ScriptedPolicy(
        [{"type": "idle", "reason": "no_trigger", "related_event_id": None}]
    )
    app = create_app(
        session_root=tmp_path,
        config=config,
        policy_factory=lambda _session_id: policy,
        clock_factory=lambda _session_id: ManualClock(),
    )

    with TestClient(app) as client:
        session_id = client.post("/session").json()["session_id"]
        session: RuntimeSession = app.state.session_registry.get(session_id)
        with client.websocket_connect(f"/session/{session_id}") as websocket:
            websocket.send_json(sampler_frame("ready", activity="paused"))
            notice = websocket.receive_json()

        def inspect() -> tuple[int, str, int]:
            record = session.store.policy_records(segment_index=1)[0]
            return session.store.current_segment_index(), record.event.kind, record.event.seq

        segment_index, kind, seq = client.portal.call(inspect)

    checkpoint_event_id = notice["checkpoint_event_id"]
    assert notice == {
        "type": "checkpoint_notice",
        "checkpoint_event_id": checkpoint_event_id,
        "segment_index": 1,
        "covers_through_policy_seq": 1,
    }
    assert checkpoint_event_id.startswith("e_")
    assert (segment_index, kind, seq) == (1, "state_checkpoint", 2)


def test_scripted_timer_nudge_cancel_race_and_silent_periods(tmp_path: Path) -> None:
    reminder = "remind me every five seconds to breathe"
    typed_snapshot_count = len(reminder)

    def event_id(number: int) -> str:
        return f"e_{number:06d}"

    final_reminder_id = event_id(typed_snapshot_count + 1)
    first_fire_id = event_id(typed_snapshot_count + 5)
    first_nudge_id = event_id(typed_snapshot_count + 6)
    second_fire_id = event_id(typed_snapshot_count + 8)
    final_stop_id = event_id(typed_snapshot_count + 12)
    policy = GatedScriptedPolicy(
        [
            {"type": "idle", "reason": "typing_active", "related_event_id": None},
            {
                "type": "schedule",
                "instruction": {
                    "event_id": final_reminder_id,
                    "start_utf16": 0,
                    "end_utf16": len(reminder),
                    "text": reminder,
                },
                "interval_ms": 5_000,
                "message": "breathe",
            },
            {"type": "idle", "reason": "no_trigger", "related_event_id": None},
            {"type": "idle", "reason": "typing_active", "related_event_id": None},
            {"type": "nudge", "fire_event_id": first_fire_id},
            {"type": "idle", "reason": "no_trigger", "related_event_id": None},
            {"type": "idle", "reason": "typing_active", "related_event_id": None},
            {
                "type": "cancel",
                "instruction": {
                    "event_id": final_stop_id,
                    "start_utf16": 0,
                    "end_utf16": 4,
                    "text": "stop",
                },
                "target": {"kind": "timer", "timer_id": "t_001"},
            },
            {
                "type": "skip",
                "target_event_id": second_fire_id,
                "reason": "canceled_timer",
            },
            {"type": "idle", "reason": "no_trigger", "related_event_id": None},
        ],
        gated_calls={1, 4, 7},
    )
    clock = ManualClock()
    app = create_app(
        session_root=tmp_path,
        policy_factory=lambda _session_id: policy,
        clock_factory=lambda _session_id: clock,
    )

    with TestClient(app) as client:
        session_id = client.post("/session").json()["session_id"]
        session: RuntimeSession = app.state.session_registry.get(session_id)
        with client.websocket_connect(f"/session/{session_id}") as websocket:
            # The first inference is deliberately held while every later keystroke arrives over
            # the real socket. The policy actor must commit only the first + newest snapshots.
            websocket.send_json(sampler_frame(reminder[:1], client_ts=1))
            client.portal.call(policy.entered[1].wait)
            for index in range(2, len(reminder) + 1):
                websocket.send_json(
                    sampler_frame(reminder[:index], client_ts=index)
                )
            client.portal.call(
                wait_for_ingress,
                session,
                "user",
                "snapshot",
                typed_snapshot_count,
            )
            client.portal.call(policy.release[1].set)
            scheduled = websocket.receive_json()
            assert scheduled == {
                "type": "timer_status",
                "timer_id": "t_001",
                "instruction_id": "i_001",
                "interval_ms": 5_000,
                "message": "breathe",
                "status": "active",
                "next_due_in_ms": 5_000,
                "fire_count": 0,
            }

            # A timer becomes due while the model is still considering a continued-typing frame.
            # The real scheduler worker persists the fire and the next tick produces the nudge.
            websocket.send_json(
                sampler_frame(f"{reminder}!", client_ts=typed_snapshot_count + 1)
            )
            client.portal.call(policy.entered[4].wait)
            client.portal.call(clock.advance_ms, 5_000)
            client.portal.call(
                wait_for_ingress,
                session,
                "timer",
                "fire",
                1,
            )
            fired = websocket.receive_json()
            client.portal.call(policy.release[4].set)
            nudge = websocket.receive_json()
            assert fired["type"] == "timer_status"
            assert fired["fire_count"] == 1
            assert nudge == {
                "type": "nudge_annotation",
                "action_event_id": first_nudge_id,
                "fire_event_id": first_fire_id,
                "timer_id": "t_001",
                "message": "breathe",
                "fire_count": 1,
                "missed_count": 0,
            }

            # Hold another inference while the second real fire and the streamed stop instruction
            # arrive. The following tick sees both, cancels, then skips the still-open fire.
            websocket.send_json(
                sampler_frame(f"{reminder}!!", client_ts=typed_snapshot_count + 2)
            )
            client.portal.call(policy.entered[7].wait)
            client.portal.call(clock.advance_ms, 5_000)
            client.portal.call(
                wait_for_ingress,
                session,
                "timer",
                "fire",
                2,
            )
            second_fire = websocket.receive_json()
            for index in range(1, 5):
                websocket.send_json(
                    sampler_frame("stop"[:index], client_ts=typed_snapshot_count + 2 + index)
                )
            client.portal.call(
                wait_for_ingress,
                session,
                "user",
                "snapshot",
                typed_snapshot_count + 6,
            )
            client.portal.call(policy.release[7].set)
            canceled = websocket.receive_json()
            client.portal.call(wait_for_calls, policy, 10)
            assert second_fire["type"] == "timer_status"
            assert second_fire["fire_count"] == 2
            assert canceled["type"] == "timer_status"
            assert canceled["status"] == "canceled"
            assert canceled["next_due_in_ms"] is None

            def counts() -> tuple[int, int, int]:
                fire_count = sum(
                    isinstance(record.event, TimerFireEvent)
                    for record in session.store.policy_records()
                )
                ingress_fire_count = session.store._connection.execute(
                    "SELECT COUNT(*) FROM ingress WHERE source = 'timer' AND kind = 'fire'"
                ).fetchone()[0]
                return fire_count, int(ingress_fire_count), session.tick.tick_count

            before = client.portal.call(counts)

            async def settle() -> None:
                for _ in range(10):
                    await asyncio.sleep(0)

            for _ in range(2):
                client.portal.call(clock.advance_ms, 5_000)
                client.portal.call(settle)
                assert client.portal.call(counts) == before
                with pytest.raises(anyio.WouldBlock):
                    websocket.portal.call(websocket._send_rx.receive_nowait)

        assert before == (2, 2, 10)
