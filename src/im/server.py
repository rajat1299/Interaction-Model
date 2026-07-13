"""FastAPI transport and persistent per-session runtime wiring."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Annotated, Literal
from uuid import uuid4

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, status
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictStr,
    TypeAdapter,
    ValidationError,
    model_validator,
)

from im.canonical_json import (
    CANONICALIZER_ID,
    TimJsonError,
    TimJsonLimits,
    canonicalize_tim_json,
    parse_tim_json,
)
from im.coalesce import SnapshotState, derive_edit_kind
from im.config import MAX_SAFE_INTEGER, RuntimeConfig, estimate_tokens
from im.policy.base import AsyncClosablePolicy, Policy
from im.rollover import rollover, should_rollover
from im.scheduler import AsyncioClock, Clock, DueTimerFire, TimerScheduler
from im.schema.actions import Span
from im.schema.common import (
    Activity,
    EventId,
    InstructionId,
    NonNegativeInt,
    PositiveInt,
    TimerId,
)
from im.schema.events import SnapshotEvent
from im.serialize import RENDERER_ID
from im.store import IdKind, PolicyEventDraft, Store, TimerLedgerRecord
from im.tick import RenderCommand, RenderKind, TickRuntime, ToolScript
from im.tools import ToolAdapter, ToolResultDelivery

TOOL_REGISTRY_VERSION = 1


class ClientFrameError(ValueError):
    """Raised after raw ingress retention when a client frame is invalid."""


class SessionUnavailableError(RuntimeError):
    """Raised when a session's persistent runtime has failed or stopped."""


class _WireModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ClientSnapshotFrame(_WireModel):
    """The complete browser sampler fact accepted by the v1 WebSocket."""

    text: StrictStr
    selection_start: NonNegativeInt
    selection_end: NonNegativeInt
    is_composing: StrictBool
    input_type: StrictStr | None
    activity: Activity
    client_ts: Annotated[int, Field(strict=True, ge=0, le=MAX_SAFE_INTEGER)]

    @model_validator(mode="after")
    def validate_snapshot(self) -> ClientSnapshotFrame:
        SnapshotState(
            text=self.text,
            selection_start_utf16=self.selection_start,
            selection_end_utf16=self.selection_end,
            is_composing=self.is_composing,
        )
        return self


class NudgeAnnotationFrame(_WireModel):
    type: Literal["nudge_annotation"]
    action_event_id: EventId
    fire_event_id: EventId
    timer_id: TimerId
    message: StrictStr
    fire_count: PositiveInt
    missed_count: NonNegativeInt


class MarkRenderFrame(_WireModel):
    type: Literal["mark_render"]
    action_event_id: EventId
    instruction: Span
    target: Span


class RespondTextFrame(_WireModel):
    type: Literal["respond_text"]
    action_event_id: EventId
    reply_to_event_id: EventId
    text: StrictStr


class TimerStatusFrame(_WireModel):
    type: Literal["timer_status"]
    timer_id: TimerId
    instruction_id: InstructionId
    interval_ms: PositiveInt
    message: StrictStr
    status: Literal["active", "canceled"]
    next_due_in_ms: NonNegativeInt | None
    fire_count: NonNegativeInt


class CheckpointNoticeFrame(_WireModel):
    type: Literal["checkpoint_notice"]
    checkpoint_event_id: EventId
    segment_index: PositiveInt
    covers_through_policy_seq: NonNegativeInt


ServerRenderFrame = Annotated[
    NudgeAnnotationFrame
    | MarkRenderFrame
    | RespondTextFrame
    | TimerStatusFrame
    | CheckpointNoticeFrame,
    Field(discriminator="type"),
]
SERVER_FRAME_ADAPTER = TypeAdapter(ServerRenderFrame)


class SessionCreated(_WireModel):
    session_id: StrictStr


@dataclass(frozen=True, slots=True)
class ArtifactPaths:
    """Exact runtime artifacts whose bytes identify a reproducible session."""

    event_schema: Path
    action_schema: Path
    behavior_spec: Path
    prompt_template: Path

    @classmethod
    def from_repository(cls, root: Path) -> ArtifactPaths:
        return cls(
            event_schema=root / "spec/schema/event-v1.json",
            action_schema=root / "spec/schema/action-v1.json",
            behavior_spec=root / "spec/behavior-spec.md",
            prompt_template=root / "spec/prompt-template-v1.txt",
        )


@dataclass(frozen=True, slots=True)
class SessionArtifacts:
    hashes: dict[str, str]
    preimages: dict[str, bytes]


def _digest(data: bytes) -> str:
    return f"sha256:{sha256(data).hexdigest()}"


def load_session_artifacts(paths: ArtifactPaths, config: RuntimeConfig) -> SessionArtifacts:
    """Read and hash the frozen preimages without normalizing their bytes."""
    inputs = {
        "event_schema": paths.event_schema.read_bytes(),
        "action_schema": paths.action_schema.read_bytes(),
        "spec": paths.behavior_spec.read_bytes(),
        "prompt": paths.prompt_template.read_bytes(),
    }
    for name, data in inputs.items():
        try:
            data.decode("utf-8")
        except UnicodeDecodeError as error:
            raise ValueError(f"{name} artifact is not valid UTF-8") from error
    schema_preimage = inputs["event_schema"] + b"\n" + inputs["action_schema"]
    config_preimage = canonicalize_tim_json(config.as_json_object())
    preimages = {
        "schema": schema_preimage,
        "spec": inputs["spec"],
        "prompt": inputs["prompt"],
        "config": config_preimage,
    }
    hashes = {name: _digest(data) for name, data in preimages.items()}
    return SessionArtifacts(hashes=hashes, preimages=preimages)


def retain_session_artifacts(directory: Path, artifacts: SessionArtifacts) -> dict[str, str]:
    """Retain every exact hash preimage in a session-local content-addressed store."""
    objects = directory / "sha256"
    objects.mkdir(parents=True, exist_ok=True)
    mapping: dict[str, str] = {}
    for name, data in artifacts.preimages.items():
        digest = artifacts.hashes[name]
        path = objects / digest.removeprefix("sha256:")
        if path.exists():
            if path.read_bytes() != data:
                raise RuntimeError("content-addressed artifact collision")
        else:
            path.write_bytes(data)
        mapping[name] = digest
    return mapping


class _UnconfiguredPolicy:
    async def decide(self, _policy_bytes: bytes) -> object:
        raise RuntimeError("no policy factory was configured for this server")


type PolicyFactory = Callable[[str], Policy]
type ClockFactory = Callable[[str], Clock]
type ToolScriptFactory = Callable[[str], ToolScript | None]


class RuntimeSession:
    """One durable session and its structured-concurrency lifetime."""

    def __init__(
        self,
        *,
        session_id: str,
        directory: Path,
        policy: Policy,
        clock: Clock,
        config: RuntimeConfig,
        artifacts: SessionArtifacts,
        tool_script: ToolScript | None = None,
    ) -> None:
        self.session_id = session_id
        self.directory = directory
        self.clock = clock
        self.config = config
        self.store = Store(directory / "session.sqlite3")
        self.scheduler = TimerScheduler(self.store, clock, config)
        self.tools = ToolAdapter(self.store, clock)
        self._socket: WebSocket | None = None
        self._socket_lock = asyncio.Lock()
        self._tick_wake = asyncio.Event()
        self._render_queue: asyncio.Queue[
            tuple[WebSocket, dict[str, object]] | None
        ] = asyncio.Queue()
        self._closed = False
        self._background_error: BaseException | None = None
        self._runner: asyncio.Task[None] | None = None
        self.tick = TickRuntime(
            store=self.store,
            policy=policy,
            scheduler=self.scheduler,
            tools=self.tools,
            clock=clock,
            config=config,
            render_sink=self._on_render_command,
            tool_script=tool_script,
        )
        self._initialize(artifacts)

    def _initialize(self, artifacts: SessionArtifacts) -> None:
        artifact_mapping = retain_session_artifacts(self.directory / "artifacts", artifacts)
        payload = {
            "schema_version": 1,
            "renderer_id": RENDERER_ID,
            "canonicalizer_id": CANONICALIZER_ID,
            "tool_registry_version": TOOL_REGISTRY_VERSION,
            "hash_algorithm": "sha256",
            "capabilities": self.config.timer_capabilities(),
            "schema_hash": artifacts.hashes["schema"],
            "spec_hash": artifacts.hashes["spec"],
            "prompt_hash": artifacts.hashes["prompt"],
            "config_hash": artifacts.hashes["config"],
        }
        now_mono_ns = self._monotonic_ns()
        raw_payload = canonicalize_tim_json(payload)
        with self.store.transaction():
            event_id = self.store.allocate_id(IdKind.EVENT)
            self.store.append_ingress(
                event_id=event_id,
                received_utc=self._received_utc(),
                received_mono_ns=now_mono_ns,
                source="runtime",
                kind="session_start",
                payload=raw_payload,
            )
            self.store.commit_policy(
                PolicyEventDraft(
                    id=event_id,
                    source="runtime",
                    kind="session_start",
                    payload=payload,
                    occurred_mono_ns=now_mono_ns,
                )
            )
            self.store.set_meta("runtime_config", self.config.as_json_object())
            self.store.set_meta("artifact_hashes", artifact_mapping)
            self.store.set_meta(
                "session_hashes",
                {
                    "schema_hash": artifacts.hashes["schema"],
                    "spec_hash": artifacts.hashes["spec"],
                    "prompt_hash": artifacts.hashes["prompt"],
                    "config_hash": artifacts.hashes["config"],
                    "renderer_id": RENDERER_ID,
                    "canonicalizer_id": CANONICALIZER_ID,
                },
            )

    def start(self) -> None:
        if self._runner is not None:
            raise RuntimeError("session runtime already started")
        self._runner = asyncio.create_task(self._run(), name=f"session:{self.session_id}")
        self._runner.add_done_callback(self._runner_done)

    async def _run(self) -> None:
        async with asyncio.TaskGroup() as tasks:
            tasks.create_task(self._run_ticks(), name=f"tick:{self.session_id}")
            tasks.create_task(
                self.scheduler.run(self._on_timer_fire), name=f"timers:{self.session_id}"
            )
            tasks.create_task(self.tools.run(self._on_tool_result), name=f"tools:{self.session_id}")
            tasks.create_task(self._run_render_output(), name=f"render:{self.session_id}")

    def _runner_done(self, task: asyncio.Task[None]) -> None:
        if task.cancelled():
            return
        error = task.exception()
        if error is not None:
            self._background_error = error
            if not self._closed:
                self.store.audit(
                    "session_runtime_failed",
                    {"error": f"{type(error).__name__}: {error}"},
                )

    def assert_healthy(self) -> None:
        if self._closed:
            raise SessionUnavailableError("session runtime is closed")
        if self._background_error is not None:
            raise SessionUnavailableError(
                f"session runtime failed: {type(self._background_error).__name__}"
            )

    async def attach(self, websocket: WebSocket) -> bool:
        """Accept exactly one active browser transport for this session."""
        async with self._socket_lock:
            self.assert_healthy()
            if self._socket is not None:
                return False
            await websocket.accept()
            self._socket = websocket
            return True

    async def detach(self, websocket: WebSocket) -> None:
        async with self._socket_lock:
            if self._socket is websocket:
                self._socket = None

    def owns_transport(self, websocket: WebSocket) -> bool:
        """Return whether this socket is still the session's sole ingress owner."""
        return self._socket is websocket

    def reject_raw_frame(self, raw: bytes, reason: str) -> str:
        """Retain unsupported transport bytes before recording their rejection."""
        event_id, _now_mono_ns = self._append_raw_snapshot_ingress(raw)
        self.store.audit("ingress_rejected", {"event_id": event_id, "error": reason})
        return event_id

    def accept_snapshot(self, raw: bytes) -> str:
        """Retain one raw sampler frame, validate it, and wake the tick actor."""
        self.assert_healthy()
        if not isinstance(raw, bytes):
            raise TypeError("raw client frame must be bytes")
        event_id, now_mono_ns = self._append_raw_snapshot_ingress(raw)
        try:
            parsed = parse_tim_json(raw, TimJsonLimits.from_config(self.config))
            frame = ClientSnapshotFrame.model_validate(parsed)
        except (TimJsonError, ValidationError, TypeError, ValueError) as error:
            self.store.audit(
                "ingress_rejected",
                {"event_id": event_id, "error": f"{type(error).__name__}: {error}"},
            )
            raise ClientFrameError("invalid snapshot frame") from error

        current = SnapshotState(
            text=frame.text,
            selection_start_utf16=frame.selection_start,
            selection_end_utf16=frame.selection_end,
            is_composing=frame.is_composing,
        )
        previous = self._latest_committed_snapshot()
        edit_kind = derive_edit_kind(previous, current, frame.input_type)
        self.tick.enqueue_committed_ingress(
            PolicyEventDraft(
                id=event_id,
                source="user",
                kind="snapshot",
                activity=frame.activity,
                payload={
                    "text": frame.text,
                    "selection_start_utf16": frame.selection_start,
                    "selection_end_utf16": frame.selection_end,
                    "is_composing": frame.is_composing,
                    "edit_kind": edit_kind.value,
                },
                occurred_mono_ns=now_mono_ns,
            )
        )
        self._tick_wake.set()
        return event_id

    def _append_raw_snapshot_ingress(self, raw: bytes) -> tuple[str, int]:
        self.assert_healthy()
        if not isinstance(raw, bytes):
            raise TypeError("raw client frame must be bytes")
        now_mono_ns = self._monotonic_ns()
        event_id: str
        with self.store.transaction():
            event_id = self.store.allocate_id(IdKind.EVENT)
            self.store.append_ingress(
                event_id=event_id,
                received_utc=self._received_utc(),
                received_mono_ns=now_mono_ns,
                source="user",
                kind="snapshot",
                payload=raw,
            )
        return event_id, now_mono_ns

    def _latest_committed_snapshot(self) -> SnapshotState | None:
        record = next(
            (
                record
                for record in reversed(self.store.policy_records())
                if isinstance(record.event, SnapshotEvent)
            ),
            None,
        )
        if record is None:
            return None
        payload = record.event.payload
        return SnapshotState(
            text=payload.text,
            selection_start_utf16=payload.selection_start_utf16,
            selection_end_utf16=payload.selection_end_utf16,
            is_composing=payload.is_composing,
        )

    async def _run_ticks(self) -> None:
        while not self._closed:
            await self._tick_wake.wait()
            self._tick_wake.clear()
            if self._closed:
                break
            tick_count = self.tick.tick_count
            await self.tick.run_until_idle()
            if self.tick.tick_count != tick_count:
                self._rollover_if_needed()

    def _rollover_if_needed(self) -> None:
        if not self.tick.mark_quiescent:
            return
        policy_tokens = estimate_tokens(
            self.store.policy_bytes(), self.config.len_estimator_id
        )
        if not should_rollover(policy_tokens, self.config):
            return
        result = rollover(
            self.store,
            checkpoint_mono_ns=self._monotonic_ns(),
            config=self.config,
        )
        self._enqueue_frame(
            {
                "type": "checkpoint_notice",
                "checkpoint_event_id": result.event_id,
                "segment_index": result.payload.segment.segment_index,
                "covers_through_policy_seq": result.payload.segment.covers_through_policy_seq,
            }
        )

    async def _on_timer_fire(self, fire: DueTimerFire) -> None:
        timer = self.store.get_timer(fire.payload.timer_id)
        if timer is None:
            raise RuntimeError("claimed timer disappeared before transport projection")
        self._enqueue_frame(self._timer_status_frame(timer))
        self.tick.enqueue_committed_ingress(fire.draft)
        self._tick_wake.set()

    async def _on_tool_result(self, delivery: ToolResultDelivery) -> None:
        self.tick.enqueue_committed_ingress(delivery.as_policy_draft())
        self._tick_wake.set()

    def _on_render_command(self, command: RenderCommand) -> None:
        payload = {"type": command.kind.value, **command.payload}
        if command.kind is not RenderKind.TIMER_STATUS:
            payload["action_event_id"] = command.action_event_id
        self._enqueue_frame(payload)

    def _timer_status_frame(self, timer: TimerLedgerRecord) -> dict[str, object]:
        if timer.status.value == "active":
            if timer.next_due_mono_ns is None:
                raise RuntimeError("active timer lacks next_due_mono_ns")
            next_due_in_ms: int | None = max(
                0, (timer.next_due_mono_ns - self._monotonic_ns()) // 1_000_000
            )
        else:
            next_due_in_ms = None
        return {
            "type": "timer_status",
            "timer_id": timer.timer_id,
            "instruction_id": timer.instruction_id,
            "interval_ms": timer.interval_ms,
            "message": timer.message,
            "status": timer.status.value,
            "next_due_in_ms": next_due_in_ms,
            "fire_count": timer.fire_count,
        }

    def _enqueue_frame(self, value: object) -> None:
        frame = SERVER_FRAME_ADAPTER.validate_python(value)
        socket = self._socket
        if socket is None:
            return
        self._render_queue.put_nowait((socket, frame.model_dump(mode="json")))

    async def _run_render_output(self) -> None:
        while True:
            item = await self._render_queue.get()
            if item is None:
                return
            socket, frame = item
            if self._socket is not socket:
                continue
            try:
                await socket.send_json(frame)
            except Exception as error:
                self.store.audit(
                    "transport_render_failed",
                    {
                        "type": str(frame["type"]),
                        "error": f"{type(error).__name__}: {error}",
                    },
                )
                await self.detach(socket)
                try:
                    await socket.close(code=status.WS_1011_INTERNAL_ERROR)
                except RuntimeError:
                    pass

    def _monotonic_ns(self) -> int:
        value = self.clock.monotonic_ns()
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError("clock.monotonic_ns() must return an integer")
        if value < 0:
            raise ValueError("clock.monotonic_ns() must be non-negative")
        return value

    def _received_utc(self) -> str:
        value = self.clock.wall_utc()
        if not isinstance(value, datetime):
            raise TypeError("clock.wall_utc() must return a datetime")
        if value.tzinfo is None:
            raise ValueError("clock.wall_utc() must be timezone-aware")
        return value.astimezone(UTC).isoformat(timespec="microseconds")

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self.scheduler.close()
        self.tools.close()
        self._tick_wake.set()
        self._render_queue.put_nowait(None)
        runner = self._runner
        if runner is not None:
            runner.cancel()
            await asyncio.gather(runner, return_exceptions=True)
        socket = self._socket
        self._socket = None
        cleanup_error: BaseException | None = None
        if socket is not None:
            try:
                await socket.close(code=status.WS_1001_GOING_AWAY)
            except RuntimeError:
                pass
            except BaseException as error:
                cleanup_error = error
        try:
            if isinstance(self.tick.policy, AsyncClosablePolicy):
                await self.tick.policy.aclose()
        except BaseException as error:
            if cleanup_error is None:
                cleanup_error = error
        finally:
            try:
                self.store.close()
            except BaseException as error:
                if cleanup_error is None:
                    cleanup_error = error
        if cleanup_error is not None:
            raise cleanup_error


class SessionRegistry:
    def __init__(
        self,
        *,
        root: Path,
        config: RuntimeConfig,
        artifact_paths: ArtifactPaths,
        policy_factory: PolicyFactory,
        clock_factory: ClockFactory,
        tool_script_factory: ToolScriptFactory,
    ) -> None:
        self.root = root
        self.config = config
        self.artifacts = load_session_artifacts(artifact_paths, config)
        self.policy_factory = policy_factory
        self.clock_factory = clock_factory
        self.tool_script_factory = tool_script_factory
        self.sessions: dict[str, RuntimeSession] = {}

    def create(self) -> RuntimeSession:
        session_id = f"s_{uuid4().hex}"
        session = RuntimeSession(
            session_id=session_id,
            directory=self.root / session_id,
            policy=self.policy_factory(session_id),
            clock=self.clock_factory(session_id),
            config=self.config,
            artifacts=self.artifacts,
            tool_script=self.tool_script_factory(session_id),
        )
        session.start()
        self.sessions[session_id] = session
        return session

    def get(self, session_id: str) -> RuntimeSession | None:
        return self.sessions.get(session_id)

    async def close(self) -> None:
        await asyncio.gather(
            *(session.close() for session in self.sessions.values()),
            return_exceptions=True,
        )


def create_app(
    *,
    session_root: Path | None = None,
    repository_root: Path | None = None,
    artifact_paths: ArtifactPaths | None = None,
    config: RuntimeConfig | None = None,
    policy_factory: PolicyFactory | None = None,
    clock_factory: ClockFactory | None = None,
    tool_script_factory: ToolScriptFactory | None = None,
) -> FastAPI:
    """Build the injectable Phase-0 server without hiding runtime dependencies."""
    repo = repository_root or Path(__file__).resolve().parents[2]
    runtime_config = config or RuntimeConfig()
    registry = SessionRegistry(
        root=session_root or repo / ".im/sessions",
        config=runtime_config,
        artifact_paths=artifact_paths or ArtifactPaths.from_repository(repo),
        policy_factory=policy_factory or (lambda _session_id: _UnconfiguredPolicy()),
        clock_factory=clock_factory or (lambda _session_id: AsyncioClock()),
        tool_script_factory=tool_script_factory or (lambda _session_id: None),
    )

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        try:
            yield
        finally:
            await registry.close()

    application = FastAPI(lifespan=lifespan)
    application.state.session_registry = registry

    @application.post("/session", response_model=SessionCreated)
    async def create_session() -> SessionCreated:
        try:
            session = registry.create()
        except (OSError, ValueError, RuntimeError) as error:
            raise HTTPException(status_code=500, detail=str(error)) from error
        return SessionCreated(session_id=session.session_id)

    @application.websocket("/session/{session_id}")
    async def session_socket(websocket: WebSocket, session_id: str) -> None:
        session = registry.get(session_id)
        if session is None:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        try:
            attached = await session.attach(websocket)
        except SessionUnavailableError:
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
            return
        if not attached:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        try:
            while True:
                message = await websocket.receive()
                if message["type"] == "websocket.disconnect":
                    break
                if not session.owns_transport(websocket):
                    await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                    break
                text = message.get("text")
                if text is None:
                    raw = message.get("bytes")
                    if isinstance(raw, bytes):
                        session.reject_raw_frame(raw, "binary WebSocket frames are unsupported")
                    await websocket.close(code=status.WS_1003_UNSUPPORTED_DATA)
                    break
                try:
                    raw = text.encode("utf-8")
                    session.accept_snapshot(raw)
                except (UnicodeEncodeError, ClientFrameError, SessionUnavailableError):
                    await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                    break
        except WebSocketDisconnect:
            pass
        finally:
            await session.detach(websocket)

    return application


app = create_app()
