"""Durable fixed-rate timer scheduling over the session ledger."""

import asyncio
import hashlib
import inspect
import json
import time
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol

from im.canonical_json import canonicalize_tim_json
from im.config import SQLITE_MAX_INTEGER, RuntimeConfig
from im.schema.actions import Span
from im.schema.events import TimerFirePayload
from im.store import PolicyEventDraft, Store, StoreError, TimerLedgerRecord

_NS_PER_MS = 1_000_000


class Clock(Protocol):
    """The only source of scheduler time.

    Scheduling decisions use the monotonic clock.  UTC is captured strictly for
    the durable audit/recovery anchor and is never rendered to the model.
    """

    def monotonic_ns(self) -> int:
        """Return a non-decreasing monotonic timestamp in nanoseconds."""

    def wall_utc(self) -> datetime:
        """Return an aware UTC wall-clock timestamp for operational records."""

    async def sleep_until(self, mono_ns: int) -> None:
        """Suspend until the supplied monotonic timestamp is reached."""


class AsyncioClock:
    """Production clock backed by ``time.monotonic_ns`` and ``asyncio.sleep``."""

    def monotonic_ns(self) -> int:
        return time.monotonic_ns()

    def wall_utc(self) -> datetime:
        return datetime.now(UTC)

    async def sleep_until(self, mono_ns: int) -> None:
        if isinstance(mono_ns, bool) or not isinstance(mono_ns, int):
            raise TypeError("mono_ns must be an integer")
        delay_ns = mono_ns - self.monotonic_ns()
        if delay_ns > 0:
            await asyncio.sleep(delay_ns / 1_000_000_000)


class ManualClock:
    """Deterministic clock whose callers advance time explicitly in tests."""

    def __init__(
        self,
        *,
        mono_ns: int = 0,
        wall_utc: datetime | None = None,
    ) -> None:
        if isinstance(mono_ns, bool) or not isinstance(mono_ns, int):
            raise TypeError("mono_ns must be an integer")
        if mono_ns < 0:
            raise ValueError("mono_ns must be non-negative")
        wall = wall_utc or datetime(2026, 1, 1, tzinfo=UTC)
        if wall.tzinfo is None:
            raise ValueError("wall_utc must be timezone-aware")
        self._mono_ns = mono_ns
        self._wall_utc = wall.astimezone(UTC)
        self._wall_remainder_ns = 0
        self._changed = asyncio.Event()

    def monotonic_ns(self) -> int:
        return self._mono_ns

    def wall_utc(self) -> datetime:
        return self._wall_utc

    def advance_ns(self, duration_ns: int) -> None:
        """Advance monotonic and wall time together, waking sleeping tasks."""
        if isinstance(duration_ns, bool) or not isinstance(duration_ns, int):
            raise TypeError("duration_ns must be an integer")
        if duration_ns < 0:
            raise ValueError("duration_ns must be non-negative")
        self._mono_ns += duration_ns
        wall_delta_ns = self._wall_remainder_ns + duration_ns
        wall_delta_us, self._wall_remainder_ns = divmod(wall_delta_ns, 1_000)
        self._wall_utc += timedelta(microseconds=wall_delta_us)
        self._changed.set()

    def advance_ms(self, duration_ms: int) -> None:
        if isinstance(duration_ms, bool) or not isinstance(duration_ms, int):
            raise TypeError("duration_ms must be an integer")
        if duration_ms < 0:
            raise ValueError("duration_ms must be non-negative")
        self.advance_ns(duration_ms * _NS_PER_MS)

    async def sleep_until(self, mono_ns: int) -> None:
        if isinstance(mono_ns, bool) or not isinstance(mono_ns, int):
            raise TypeError("mono_ns must be an integer")
        while self._mono_ns < mono_ns:
            changed = self._changed
            await changed.wait()
            if changed is self._changed:
                self._changed = asyncio.Event()


class SchedulerError(RuntimeError):
    """Base class for timer scheduler failures."""


class TimerIntervalError(SchedulerError):
    """Raised when a timer interval falls outside the frozen runtime limits."""


class TimerLimitExceededError(SchedulerError):
    """Raised when a new timer would exceed ``max_active_timers``."""


class TimerNotActiveError(SchedulerError):
    """Raised when an atomic cancellation target is absent or no longer active."""


class TimerLedgerInvariantError(SchedulerError):
    """Raised for durable state that cannot represent fixed-rate recurrence."""


@dataclass(frozen=True, slots=True)
class DueTimerFire:
    """One committed timer ingress record ready for the tick buffer."""

    event_id: str
    received_utc: str
    occurred_mono_ns: int
    payload: TimerFirePayload
    ingress_payload: bytes

    @property
    def draft(self) -> PolicyEventDraft:
        """Return the uncommitted policy-lane representation of this fire."""
        return PolicyEventDraft(
            id=self.event_id,
            source="timer",
            kind="fire",
            payload=self.payload.model_dump(mode="python"),
            occurred_mono_ns=self.occurred_mono_ns,
        )


type EnqueueFire = Callable[[DueTimerFire], Awaitable[None] | None]


def scheduling_idempotency_key(
    *,
    instruction_id: str,
    interval_ms: int,
    message: str,
) -> str:
    """Return the stable key for one internally retryable schedule operation."""
    preimage = canonicalize_tim_json(
        {
            "instruction_id": instruction_id,
            "interval_ms": interval_ms,
            "message": message,
        }
    )
    digest = hashlib.sha256(b"tim-schedule-idempotency-v1\x00" + preimage).hexdigest()
    return f"sha256:{digest}"


class TimerScheduler:
    """Create, cancel, and claim durable recurring timers.

    ``schedule`` is deliberately retry-idempotent rather than a policy-level
    duplicate detector.  WP6 blocks repeated model actions; callers retrying a
    transaction use the same runtime-issued ``instruction_id`` and safely get
    back the original timer record.
    """

    def __init__(
        self,
        store: Store,
        clock: Clock,
        config: RuntimeConfig | None = None,
    ) -> None:
        self.store = store
        self.clock = clock
        self.config = config or RuntimeConfig()
        self._changed = asyncio.Event()
        self._closed = False

    def _validate_schedule(
        self,
        *,
        instruction_id: str,
        instruction: Span,
        interval_ms: int,
        message: str,
    ) -> None:
        if not isinstance(instruction_id, str) or not instruction_id:
            raise ValueError("instruction_id must be a non-empty string")
        if not isinstance(instruction, Span):
            raise TypeError("instruction must be a Span")
        if isinstance(interval_ms, bool) or not isinstance(interval_ms, int):
            raise TypeError("interval_ms must be an integer")
        if not (
            self.config.min_timer_interval_ms <= interval_ms <= self.config.max_timer_interval_ms
        ):
            raise TimerIntervalError(
                "interval_ms must be within the configured timer interval bounds"
            )
        if not isinstance(message, str) or not message:
            raise ValueError("message must be a non-empty string")
        try:
            message.encode("utf-8")
        except UnicodeEncodeError as error:
            raise ValueError("message must be valid Unicode text") from error
        if message != message.strip():
            raise ValueError("message must already have normalized outer whitespace")
        if len(message.encode("utf-8")) > self.config.max_timer_message_bytes:
            raise ValueError("message exceeds max_timer_message_bytes")

    @staticmethod
    def _utc_text(value: datetime) -> str:
        if value.tzinfo is None:
            raise ValueError("clock.wall_utc() must return a timezone-aware datetime")
        return value.astimezone(UTC).isoformat(timespec="microseconds")

    def schedule(
        self,
        *,
        instruction_id: str,
        instruction: Span,
        interval_ms: int,
        message: str,
    ) -> TimerLedgerRecord:
        """Create and activate a timer, or return its internal retry result.

        The scheduled-to-active transition happens before this method returns,
        within the caller's current store transaction when one is open.  The
        execution layer can therefore append ``runtime.scheduled`` in that same
        transaction.
        """
        self._validate_schedule(
            instruction_id=instruction_id,
            instruction=instruction,
            interval_ms=interval_ms,
            message=message,
        )
        key = scheduling_idempotency_key(
            instruction_id=instruction_id,
            interval_ms=interval_ms,
            message=message,
        )
        with self.store.transaction():
            existing = self.store.get_timer_by_idempotency_key(key)
            if existing is not None:
                if (
                    existing.instruction_event_id != instruction.event_id
                    or existing.instruction_start_utf16 != instruction.start_utf16
                    or existing.instruction_end_utf16 != instruction.end_utf16
                    or existing.instruction_text != instruction.text
                ):
                    raise TimerLedgerInvariantError(
                        "idempotency key was reused with different instruction provenance"
                    )
                return existing
            if self.store.active_timer_count() >= self.config.max_active_timers:
                raise TimerLimitExceededError("max_active_timers reached")
            anchor_mono_ns = self.clock.monotonic_ns()
            if isinstance(anchor_mono_ns, bool) or not isinstance(anchor_mono_ns, int):
                raise TypeError("clock.monotonic_ns() must return an integer")
            if anchor_mono_ns < 0:
                raise ValueError("clock.monotonic_ns() must be non-negative")
            interval_ns = interval_ms * _NS_PER_MS
            if anchor_mono_ns > SQLITE_MAX_INTEGER - interval_ns:
                raise TimerIntervalError("first due time exceeds SQLite integer range")
            timer_id = self.store.allocate_id("timer")
            self.store.insert_scheduled_timer(
                timer_id=timer_id,
                instruction_id=instruction_id,
                instruction_event_id=instruction.event_id,
                instruction_start_utf16=instruction.start_utf16,
                instruction_end_utf16=instruction.end_utf16,
                instruction_text=instruction.text,
                interval_ms=interval_ms,
                message=message,
                anchor_mono_ns=anchor_mono_ns,
                anchor_utc=self._utc_text(self.clock.wall_utc()),
                next_due_mono_ns=anchor_mono_ns + interval_ns,
                idempotency_key=key,
            )
            record = self.store.activate_timer(timer_id)
        self._changed.set()
        return record

    def cancel(self, timer_ids: Iterable[str]) -> tuple[TimerLedgerRecord, ...]:
        """Cancel an exact active target set without allowing a partial result."""
        target_ids = tuple(timer_ids)
        try:
            canceled = self.store.cancel_active_timers(target_ids)
        except StoreError as error:
            raise TimerNotActiveError(str(error)) from error
        self._changed.set()
        return canceled

    def cancel_all_active(self) -> tuple[TimerLedgerRecord, ...]:
        """Cancel all active timers and return the canceled records by timer ID."""
        canceled = self.store.cancel_all_active_timers()
        if canceled:
            self._changed.set()
        return canceled

    def _claim_one_due_timer(self, record: TimerLedgerRecord, now_mono_ns: int) -> DueTimerFire:
        if record.next_due_mono_ns is None:
            raise TimerLedgerInvariantError("active timer lacks a next due timestamp")
        interval_ns = record.interval_ms * _NS_PER_MS
        expected_due = record.anchor_mono_ns + (record.fire_count + 1) * interval_ns
        if record.next_due_mono_ns != expected_due:
            raise TimerLedgerInvariantError("timer next_due_mono_ns is not fixed-rate anchored")
        elapsed_periods = (now_mono_ns - record.anchor_mono_ns) // interval_ns
        if elapsed_periods <= record.fire_count:
            raise TimerLedgerInvariantError("due timer has no unclaimed fixed-rate period")
        latest_due_mono_ns = record.anchor_mono_ns + elapsed_periods * interval_ns
        missed_count = elapsed_periods - record.fire_count - 1
        next_due_mono_ns = record.anchor_mono_ns + (elapsed_periods + 1) * interval_ns
        if next_due_mono_ns > SQLITE_MAX_INTEGER:
            raise TimerLedgerInvariantError("next due time exceeds SQLite integer range")
        late_ms = (now_mono_ns - latest_due_mono_ns) // _NS_PER_MS
        updated = self.store.advance_due_timer(
            timer_id=record.timer_id,
            expected_next_due_mono_ns=record.next_due_mono_ns,
            fire_count=elapsed_periods,
            next_due_mono_ns=next_due_mono_ns,
        )
        payload = TimerFirePayload(
            timer_id=updated.timer_id,
            fire_count=elapsed_periods,
            late_ms=late_ms,
            missed_count=missed_count,
        )
        payload_object = payload.model_dump(mode="python")
        ingress_payload = json.dumps(
            payload_object,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        event_id = self.store.allocate_id("event")
        received_utc = self._utc_text(self.clock.wall_utc())
        self.store.append_ingress(
            event_id=event_id,
            received_utc=received_utc,
            received_mono_ns=now_mono_ns,
            source="timer",
            kind="fire",
            payload=ingress_payload,
        )
        return DueTimerFire(
            event_id=event_id,
            received_utc=received_utc,
            occurred_mono_ns=now_mono_ns,
            payload=payload,
            ingress_payload=ingress_payload,
        )

    def claim_due(self) -> tuple[DueTimerFire, ...]:
        """Persist and return at most one coalesced fire per due timer.

        Ledger advancement, event-ID allocation, and raw ingress append share one
        transaction.  Returning only after that commit is the boundary that
        prevents an enqueue from observing a fire that did not become durable.
        """
        now_mono_ns = self.clock.monotonic_ns()
        if isinstance(now_mono_ns, bool) or not isinstance(now_mono_ns, int):
            raise TypeError("clock.monotonic_ns() must return an integer")
        if now_mono_ns < 0:
            raise ValueError("clock.monotonic_ns() must be non-negative")
        with self.store.transaction():
            fires = tuple(
                self._claim_one_due_timer(record, now_mono_ns)
                for record in self.store.due_active_timers(now_mono_ns)
            )
        return fires

    async def wait_for_due(self) -> tuple[DueTimerFire, ...]:
        """Wait for a durable fire, waking when schedule/cancel state changes."""
        while not self._closed:
            fires = self.claim_due()
            if fires:
                return fires
            next_due_mono_ns = self.store.next_active_due_mono_ns()
            self._changed.clear()
            if self._closed:
                break
            if next_due_mono_ns is None:
                await self._changed.wait()
                continue
            sleeper = asyncio.create_task(self.clock.sleep_until(next_due_mono_ns))
            changed = asyncio.create_task(self._changed.wait())
            _done, pending = await asyncio.wait(
                (sleeper, changed), return_when=asyncio.FIRST_COMPLETED
            )
            for task in pending:
                task.cancel()
            if pending:
                await asyncio.gather(*pending, return_exceptions=True)
        return ()

    async def run(self, enqueue: EnqueueFire) -> None:
        """Claim fires and enqueue them only after their transaction commits."""
        while not self._closed:
            fires = await self.wait_for_due()
            for fire in fires:
                result = enqueue(fire)
                if inspect.isawaitable(result):
                    await result

    def close(self) -> None:
        """Stop waiters and the optional scheduler task."""
        self._closed = True
        self._changed.set()
