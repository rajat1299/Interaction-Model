"""Virtual-time ingestion through the production RuntimeSession."""

from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from im.canonical_json import TimJsonLimits, canonicalize_tim_json, parse_tim_json
from im.config import RuntimeConfig
from im.license import LicenseView
from im.scheduler import ManualClock
from im.server import (
    ArtifactPaths,
    ClientSnapshotFrame,
    RuntimeSession,
    SessionArtifacts,
    load_session_artifacts,
)
from im.tick import TickPhase, ToolScript, build_license_view

if TYPE_CHECKING:
    from im.generation.ingestion import ScheduledSamplerFrame


@dataclass(frozen=True, slots=True)
class TimedDecision:
    """One explicit oracle attempt and its virtual policy service time."""

    service_ms: int
    attempt: object

    def __post_init__(self) -> None:
        if isinstance(self.service_ms, bool) or not isinstance(self.service_ms, int):
            raise TypeError("service_ms must be an integer")
        if self.service_ms < 0:
            raise ValueError("service_ms must be non-negative")


@dataclass(frozen=True, slots=True)
class DecisionTiming:
    call_index: int
    started_mono_ns: int
    completed_mono_ns: int

    @property
    def service_ms(self) -> int:
        return (self.completed_mono_ns - self.started_mono_ns) // 1_000_000


@dataclass(frozen=True, slots=True)
class DecisionBoundary:
    """The durable policy prefix and license projection immediately before one attempt."""

    call_index: int
    policy_bytes: bytes
    license_view: LicenseView

    def __post_init__(self) -> None:
        if isinstance(self.call_index, bool) or not isinstance(self.call_index, int):
            raise TypeError("call_index must be an integer")
        if self.call_index < 1:
            raise ValueError("call_index must be positive")
        if not isinstance(self.policy_bytes, bytes) or not self.policy_bytes:
            raise ValueError("policy_bytes must be non-empty bytes")
        if not isinstance(self.license_view, LicenseView):
            raise TypeError("license_view must be a LicenseView")


type DecisionBoundaryObserver = Callable[[DecisionBoundary], None]
type _DecisionBoundaryCapture = Callable[[int, bytes], None]


class TimedScriptedPolicy:
    """Finite scripted policy that waits on the shared production clock."""

    def __init__(
        self,
        clock: ManualClock,
        decisions: Iterable[TimedDecision],
        *,
        decision_boundary_capture: _DecisionBoundaryCapture | None = None,
    ) -> None:
        self.clock = clock
        self._decisions = deque(decisions)
        self._entered = [asyncio.Event() for _ in self._decisions]
        self.call_count = 0
        self.observed_policy_bytes: list[bytes] = []
        self.timings: list[DecisionTiming] = []
        self._active_deadline_ns: int | None = None
        self._decision_boundary_capture = decision_boundary_capture

    @property
    def remaining_count(self) -> int:
        return len(self._decisions)

    @property
    def completed_count(self) -> int:
        return len(self.timings)

    @property
    def active_deadline_ns(self) -> int | None:
        return self._active_deadline_ns

    async def wait_until_entered(self, call_index: int) -> None:
        self._validate_call_index(call_index)
        await self._entered[call_index - 1].wait()

    def has_entered(self, call_index: int) -> bool:
        self._validate_call_index(call_index)
        return self._entered[call_index - 1].is_set()

    def _validate_call_index(self, call_index: int) -> None:
        if isinstance(call_index, bool) or not isinstance(call_index, int):
            raise TypeError("call_index must be an integer")
        if not 1 <= call_index <= len(self._entered):
            raise ValueError("call_index is outside the scripted decisions")

    async def decide(self, policy_bytes: bytes) -> object:
        if not isinstance(policy_bytes, bytes):
            raise TypeError("policy_bytes must be bytes")
        if not self._decisions:
            raise RuntimeError("timed scripted policy has no remaining decision")
        decision = self._decisions.popleft()
        self.call_count += 1
        self.observed_policy_bytes.append(policy_bytes)
        if self._decision_boundary_capture is not None:
            self._decision_boundary_capture(self.call_count, policy_bytes)
        started_mono_ns = self.clock.monotonic_ns()
        self._active_deadline_ns = started_mono_ns + decision.service_ms * 1_000_000
        self._entered[self.call_count - 1].set()
        await self.clock.sleep_until(self._active_deadline_ns)
        completed_mono_ns = self.clock.monotonic_ns()
        self.timings.append(
            DecisionTiming(
                call_index=self.call_count,
                started_mono_ns=started_mono_ns,
                completed_mono_ns=completed_mono_ns,
            )
        )
        self._active_deadline_ns = None
        return decision.attempt


class VirtualLatencyStubPolicy:
    """Sampler-backed, zero-network calibration policy on the shared virtual clock."""

    def __init__(self, clock: ManualClock, seed: str) -> None:
        from im.policy.latency_stub import LatencyStubPolicy

        self.clock = clock
        self.timings: list[DecisionTiming] = []
        self._active_deadline_ns: int | None = None
        self._policy = LatencyStubPolicy(seed, sleep=self._sleep)

    @property
    def sampler(self):
        return self._policy.sampler

    @property
    def call_count(self) -> int:
        return self._policy.call_count

    @property
    def last_latency_ms(self) -> int | None:
        return self._policy.last_latency_ms

    @property
    def completed_count(self) -> int:
        return len(self.timings)

    @property
    def active_deadline_ns(self) -> int | None:
        return self._active_deadline_ns

    @property
    def calibration_metadata(self) -> dict[str, object]:
        return self._policy.calibration_metadata

    def calibration_decision_metadata(self) -> dict[str, int]:
        return self._policy.calibration_decision_metadata()

    async def decide(self, policy_bytes: bytes) -> object:
        return await self._policy.decide(policy_bytes)

    async def _sleep(self, _seconds: float) -> None:
        latency_ms = self.last_latency_ms
        if latency_ms is None:
            raise RuntimeError("latency stub has not planned a decision")
        started_mono_ns = self.clock.monotonic_ns()
        self._active_deadline_ns = started_mono_ns + latency_ms * 1_000_000
        await self.clock.sleep_until(self._active_deadline_ns)
        completed_mono_ns = self.clock.monotonic_ns()
        self.timings.append(
            DecisionTiming(
                call_index=self.call_count,
                started_mono_ns=started_mono_ns,
                completed_mono_ns=completed_mono_ns,
            )
        )
        self._active_deadline_ns = None


class RuntimeIngestionHarness:
    """Drive generated sampler bytes through one real background runtime."""

    def __init__(
        self,
        *,
        session_id: str,
        directory: Path,
        decisions: Iterable[TimedDecision] | None = None,
        config: RuntimeConfig | None = None,
        artifacts: SessionArtifacts | None = None,
        repository_root: Path | None = None,
        tool_script: ToolScript | None = None,
        decision_boundary_observer: DecisionBoundaryObserver | None = None,
        calibration: bool = False,
        measurement_audits: bool = False,
    ) -> None:
        if decision_boundary_observer is not None and not callable(decision_boundary_observer):
            raise TypeError("decision_boundary_observer must be callable or None")
        if calibration and decisions is not None:
            raise ValueError("calibration runtime does not accept scripted decisions")
        if not calibration and decisions is None:
            raise TypeError("decisions is required outside calibration mode")
        self.config = config or RuntimeConfig()
        root = repository_root or Path(__file__).resolve().parents[3]
        session_artifacts = artifacts or load_session_artifacts(
            ArtifactPaths.from_repository(root), self.config
        )
        self.clock = ManualClock()
        self._calibration = calibration
        self._calibration_replayed = False
        if calibration:
            self.policy = VirtualLatencyStubPolicy(self.clock, session_id)
        else:
            self.policy = TimedScriptedPolicy(
                self.clock,
                decisions,
                decision_boundary_capture=(
                    None
                    if decision_boundary_observer is None
                    else lambda call_index, policy_bytes: decision_boundary_observer(
                        DecisionBoundary(
                            call_index=call_index,
                            policy_bytes=policy_bytes,
                            license_view=build_license_view(self.session.store, self.config),
                        )
                    )
                ),
            )
        self.session = RuntimeSession(
            session_id=session_id,
            directory=directory,
            policy=self.policy,
            clock=self.clock,
            config=self.config,
            artifacts=session_artifacts,
            tool_script=tool_script,
            measurement_audits=calibration or measurement_audits,
        )
        self._started = False

    @classmethod
    def calibration(
        cls,
        *,
        session_id: str,
        directory: Path,
        config: RuntimeConfig | None = None,
        artifacts: SessionArtifacts | None = None,
        repository_root: Path | None = None,
    ) -> RuntimeIngestionHarness:
        """Build the sampler-backed, zero-network calibration replay mode."""
        return cls(
            session_id=session_id,
            directory=directory,
            config=config,
            artifacts=artifacts,
            repository_root=repository_root,
            calibration=True,
        )

    async def __aenter__(self) -> RuntimeIngestionHarness:
        self.start()
        return self

    async def __aexit__(self, *_exc_info: object) -> None:
        await self.close()

    def start(self) -> None:
        if self._started:
            raise RuntimeError("runtime ingestion harness already started")
        self.session.start()
        self._started = True

    def accept_snapshot(
        self,
        frame: ClientSnapshotFrame | dict[str, object] | bytes,
    ) -> str:
        if not self._started:
            raise RuntimeError("runtime ingestion harness is not started")
        if isinstance(frame, bytes):
            raw = frame
        else:
            validated = ClientSnapshotFrame.model_validate(frame)
            raw = canonicalize_tim_json(validated.model_dump(mode="json"))
        return self.session.accept_snapshot(raw)

    def accept_annotation(self, raw: bytes) -> str:
        """Route one raw user annotation through the production session ingress API."""
        if not self._started:
            raise RuntimeError("runtime ingestion harness is not started")
        if not isinstance(raw, bytes):
            raise TypeError("raw annotation must be bytes")
        return self.session.accept_annotation(raw)

    async def advance_ms(self, duration_ms: int) -> None:
        if isinstance(duration_ms, bool) or not isinstance(duration_ms, int):
            raise TypeError("duration_ms must be an integer")
        if duration_ms < 0:
            raise ValueError("duration_ms must be non-negative")
        await self._advance_to_ns(self.clock.monotonic_ns() + duration_ms * 1_000_000)

    async def _advance_to_ns(self, target_ns: int) -> None:
        await self.progress_at_current_time()
        while self.clock.monotonic_ns() < target_ns:
            now_ns = self.clock.monotonic_ns()
            policy_deadline = self.policy.active_deadline_ns
            timer_deadline = self.session.store.next_active_due_mono_ns()
            tool_deadline = self.session.store.next_pending_tool_due_mono_ns()
            next_ns = min(
                [target_ns]
                + [
                    deadline
                    for deadline in (policy_deadline, timer_deadline, tool_deadline)
                    if deadline is not None and now_ns < deadline <= target_ns
                ]
            )
            self.clock.advance_ns(next_ns - now_ns)
            await self._settle_deadline(
                next_ns,
                policy_due=policy_deadline == next_ns,
                timer_due=timer_deadline == next_ns,
                tool_due=tool_deadline == next_ns,
            )
            await self.progress_at_current_time()
        await self.progress_at_current_time()

    async def progress_at_current_time(self, *, max_turns: int = 1_000) -> None:
        """Pump actors until inference is active or same-time work is stably idle."""
        idle_observation: tuple[int, int, int] | None = None
        for _ in range(max_turns):
            self.session.assert_healthy()
            now_ns = self.clock.monotonic_ns()
            deadline = self.policy.active_deadline_ns
            due_now = any(
                world_deadline is not None and world_deadline <= now_ns
                for world_deadline in (
                    self.session.store.next_active_due_mono_ns(),
                    self.session.store.next_pending_tool_due_mono_ns(),
                )
            )
            if not due_now and deadline is not None and deadline > now_ns:
                return
            if self.session.tick.phase is TickPhase.IDLE and not self.session.tick.pending:
                observation = (
                    self.session.tick.tick_count,
                    self.policy.call_count,
                    self.session.store.current_segment_index(),
                )
                if observation == idle_observation:
                    return
                idle_observation = observation
            else:
                idle_observation = None
            await asyncio.sleep(0)
        raise RuntimeError("runtime actors did not settle at the current virtual time")

    async def _settle_deadline(
        self,
        reached_ns: int,
        *,
        policy_due: bool,
        timer_due: bool,
        tool_due: bool,
    ) -> None:
        for _ in range(1_000):
            timer_pending = self.session.store.next_active_due_mono_ns()
            tool_pending = self.session.store.next_pending_tool_due_mono_ns()
            if (
                (not policy_due or self.policy.active_deadline_ns != reached_ns)
                and (not timer_due or timer_pending is None or timer_pending > reached_ns)
                and (not tool_due or tool_pending is None or tool_pending > reached_ns)
            ):
                return
            await asyncio.sleep(0)
        raise RuntimeError("runtime actors did not settle a virtual-time deadline")

    async def _drive_until(
        self,
        complete: Callable[[], bool],
        *,
        max_turns: int,
        failure: Callable[[], RuntimeError],
    ) -> None:
        """Advance through policy deadlines without skipping earlier due work."""
        for _ in range(max_turns):
            await self.progress_at_current_time()
            if complete():
                return
            deadline = self.policy.active_deadline_ns
            if deadline is not None:
                await self._advance_to_ns(deadline)
                continue
            now_ns = self.clock.monotonic_ns()
            world_deadlines = (
                self.session.store.next_active_due_mono_ns(),
                self.session.store.next_pending_tool_due_mono_ns(),
            )
            future = tuple(
                deadline
                for deadline in world_deadlines
                if deadline is not None and deadline > now_ns
            )
            if future:
                await self._advance_to_ns(min(future))
        raise failure()

    async def drive_until_decisions(self, count: int, *, max_turns: int = 1_000) -> None:
        """Advance the finite scripted policy through a requested decision count."""
        if isinstance(count, bool) or not isinstance(count, int):
            raise TypeError("count must be an integer")
        if self._calibration:
            raise RuntimeError("calibration decisions are derived from sampler ingress")
        total_count = self.policy.call_count + self.policy.remaining_count
        if not 0 <= count <= total_count:
            raise ValueError("count is outside the scripted decisions")
        await self._drive_until(
            lambda: self.policy.completed_count >= count,
            max_turns=max_turns,
            failure=lambda: RuntimeError(
                f"runtime completed {self.policy.completed_count} decisions; expected {count}"
            ),
        )

    async def drive_until_quiescent(self, *, max_turns: int = 1_000) -> None:
        """Advance all virtual deadlines until the runtime has no remaining work."""
        await self._drive_until(
            lambda: (
                self.policy.active_deadline_ns is None
                and self.session.tick.phase is TickPhase.IDLE
                and not self.session.tick.pending
                and self.session.tick.mark_quiescent
            ),
            max_turns=max_turns,
            failure=lambda: RuntimeError("runtime ingestion harness did not become idle"),
        )

    async def replay_calibration(
        self, frames: Iterable[ScheduledSamplerFrame]
    ) -> Path:
        """Replay exact sampler frames and return the finalized SQLite artifact."""
        if not self._calibration:
            raise RuntimeError("calibration replay requires calibration mode")
        if self._calibration_replayed:
            raise RuntimeError("calibration runtime was already replayed")
        schedule = self._validated_calibration_schedule(frames)
        self._calibration_replayed = True
        if not self._started:
            self.start()
        current_at_ms = 0
        for at_ms, raw_bytes, _client_ts in schedule:
            await self.advance_ms(at_ms - current_at_ms)
            self.accept_snapshot(raw_bytes)
            await self.progress_at_current_time()
            current_at_ms = at_ms
        await self.drive_until_quiescent()
        last_client_ts = schedule[-1][2] if schedule else None
        await self.session.complete_calibration(last_client_ts, len(schedule))
        database_path = self.session.directory / "session.sqlite3"
        await self.close()
        return database_path

    def _validated_calibration_schedule(
        self, frames: Iterable[ScheduledSamplerFrame]
    ) -> tuple[tuple[int, bytes, int], ...]:
        schedule: list[tuple[int, bytes, int]] = []
        for scheduled in frames:
            try:
                at_ms = scheduled.at_ms
                raw_bytes = scheduled.raw_bytes
            except AttributeError as error:
                raise TypeError("frames must contain ScheduledSamplerFrame values") from error
            if isinstance(at_ms, bool) or not isinstance(at_ms, int):
                raise TypeError("frame.at_ms must be an integer")
            if at_ms < 0:
                raise ValueError("frame.at_ms must be non-negative")
            if not isinstance(raw_bytes, bytes):
                raise TypeError("frame.raw_bytes must be bytes")
            if schedule and at_ms < schedule[-1][0]:
                raise ValueError("scheduled sampler frames must be nondecreasing by at_ms")
            frame = ClientSnapshotFrame.model_validate(
                parse_tim_json(raw_bytes, TimJsonLimits.from_config(self.config))
            )
            schedule.append((at_ms, raw_bytes, frame.client_ts))
        return tuple(schedule)

    async def wait_for_decisions(self, count: int, *, max_turns: int = 1_000) -> None:
        if isinstance(count, bool) or not isinstance(count, int):
            raise TypeError("count must be an integer")
        if count < 0:
            raise ValueError("count must be non-negative")
        for _ in range(max_turns):
            self.session.assert_healthy()
            if self.policy.completed_count >= count:
                return
            await asyncio.sleep(0)
        raise RuntimeError(
            f"runtime completed {self.policy.completed_count} decisions; expected {count}"
        )

    async def wait_until_idle(self, *, max_turns: int = 1_000) -> None:
        for _ in range(max_turns):
            await self.progress_at_current_time()
            if (
                self.session.tick.phase is TickPhase.IDLE
                and not self.session.tick.pending
                and self.session.tick.mark_quiescent
            ):
                return
            await asyncio.sleep(0)
        raise RuntimeError("runtime ingestion harness did not become idle")

    async def close(self) -> None:
        await self.session.close()
