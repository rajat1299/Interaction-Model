"""Fake-clock acceptance tests for the durable recurring timer scheduler."""

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from im.config import SQLITE_MAX_INTEGER, RuntimeConfig
from im.scheduler import (
    AsyncioClock,
    ManualClock,
    TimerIntervalError,
    TimerLedgerInvariantError,
    TimerLimitExceededError,
    TimerScheduler,
)
from im.schema.actions import Span
from im.schema.common import TimerStatus
from im.serialize import parse_event
from im.store import Store


def instruction(event_id: str = "e_000001", text: str = "breathe") -> Span:
    return Span(
        event_id=event_id,
        start_utf16=0,
        end_utf16=len(text),
        text=text,
    )


def make_scheduler(
    tmp_path: Path,
    *,
    config: RuntimeConfig | None = None,
) -> tuple[Store, ManualClock, TimerScheduler]:
    store = Store(tmp_path / "session.sqlite3")
    clock = ManualClock(wall_utc=datetime(2026, 7, 12, 12, tzinfo=UTC))
    return store, clock, TimerScheduler(store, clock, config)


@pytest.mark.asyncio
async def test_manual_clock_wakes_sleepers_and_preserves_utc_wall_time() -> None:
    initial_wall = datetime(2026, 7, 12, 12, tzinfo=UTC)
    clock = ManualClock(mono_ns=123, wall_utc=initial_wall)
    sleeper = asyncio.create_task(clock.sleep_until(1_000_123))

    await asyncio.sleep(0)
    assert not sleeper.done()
    clock.advance_ms(1)
    await sleeper

    assert clock.monotonic_ns() == 1_000_123
    assert clock.wall_utc() == initial_wall + timedelta(milliseconds=1)


def test_manual_clock_retains_sub_microsecond_wall_time_remainder() -> None:
    initial_wall = datetime(2026, 7, 12, 12, tzinfo=UTC)
    clock = ManualClock(wall_utc=initial_wall)

    clock.advance_ns(999)
    clock.advance_ns(999)

    assert clock.monotonic_ns() == 1_998
    assert clock.wall_utc() == initial_wall + timedelta(microseconds=1)


@pytest.mark.asyncio
async def test_asyncio_clock_uses_an_aware_utc_wall_clock() -> None:
    clock = AsyncioClock()

    await clock.sleep_until(clock.monotonic_ns())

    assert clock.wall_utc().tzinfo is UTC


def test_schedule_activates_in_the_execution_transaction_and_persists_provenance(
    tmp_path: Path,
) -> None:
    store, _clock, scheduler = make_scheduler(tmp_path)
    try:
        origin = instruction(text="remind me every second")
        record = scheduler.schedule(
            instruction_id="i_001",
            instruction=origin,
            interval_ms=1_000,
            message="breathe",
        )

        assert record.timer_id == "t_001"
        assert record.status is TimerStatus.ACTIVE
        assert record.anchor_mono_ns == 0
        assert record.anchor_utc == "2026-07-12T12:00:00.000000+00:00"
        assert record.next_due_mono_ns == 1_000_000_000
        assert (
            record.instruction_event_id,
            record.instruction_start_utf16,
            record.instruction_end_utf16,
            record.instruction_text,
        ) == ("e_000001", 0, len(origin.text), origin.text)

        # Activation and allocation roll back with a surrounding execution transaction.
        with pytest.raises(RuntimeError, match="abort execution"):
            with store.transaction():
                scheduler.schedule(
                    instruction_id="i_002",
                    instruction=instruction("e_000002", "second instruction"),
                    interval_ms=1_000,
                    message="stretch",
                )
                raise RuntimeError("abort execution")
        assert store.get_timer("t_002") is None
        assert store.allocate_id("timer") == "t_002"
    finally:
        store.close()


def test_schedule_is_defensively_idempotent_for_internal_retries(tmp_path: Path) -> None:
    store, _clock, scheduler = make_scheduler(tmp_path)
    try:
        origin = instruction()
        first = scheduler.schedule(
            instruction_id="i_001",
            instruction=origin,
            interval_ms=1_000,
            message="breathe",
        )
        retry = scheduler.schedule(
            instruction_id="i_001",
            instruction=origin,
            interval_ms=1_000,
            message="breathe",
        )
        distinct_canonical_schedule = scheduler.schedule(
            instruction_id="i_001",
            instruction=origin,
            interval_ms=2_000,
            message="breathe",
        )
        with pytest.raises(TimerLedgerInvariantError, match="different instruction provenance"):
            scheduler.schedule(
                instruction_id="i_001",
                instruction=instruction("e_000002"),
                interval_ms=1_000,
                message="breathe",
            )

        assert retry == first
        assert distinct_canonical_schedule.timer_id == "t_002"
        assert store.active_timer_count() == 2
        assert store.allocate_id("timer") == "t_003"
    finally:
        store.close()


def test_due_claims_stay_fixed_rate_under_jitter(tmp_path: Path) -> None:
    store, clock, scheduler = make_scheduler(tmp_path)
    try:
        record = scheduler.schedule(
            instruction_id="i_001",
            instruction=instruction(),
            interval_ms=1_000,
            message="breathe",
        )
        clock.advance_ms(1_234)
        first = scheduler.claim_due()

        assert len(first) == 1
        assert first[0].payload.fire_count == 1
        assert first[0].payload.missed_count == 0
        assert first[0].payload.late_ms == 234
        assert store.get_timer(record.timer_id).next_due_mono_ns == 2_000_000_000  # type: ignore[union-attr]

        clock.advance_ms(2_011)
        second = scheduler.claim_due()

        assert len(second) == 1
        assert second[0].payload.fire_count == 3
        assert second[0].payload.missed_count == 1
        assert second[0].payload.late_ms == 245
        assert store.get_timer(record.timer_id).next_due_mono_ns == 4_000_000_000  # type: ignore[union-attr]
    finally:
        store.close()


def test_busy_periods_coalesce_to_one_latest_fixed_rate_fire(tmp_path: Path) -> None:
    store, clock, scheduler = make_scheduler(tmp_path)
    try:
        record = scheduler.schedule(
            instruction_id="i_001",
            instruction=instruction(),
            interval_ms=1_000,
            message="breathe",
        )
        clock.advance_ms(5_000)
        fires = scheduler.claim_due()

        assert len(fires) == 1
        assert fires[0].payload.fire_count == 5
        assert fires[0].payload.missed_count == 4
        assert fires[0].payload.late_ms == 0
        updated = store.get_timer(record.timer_id)
        assert updated is not None
        assert updated.fire_count == 5
        assert updated.next_due_mono_ns == 6_000_000_000
    finally:
        store.close()


def test_cancel_and_due_have_a_single_durable_sequence_order(tmp_path: Path) -> None:
    store, clock, scheduler = make_scheduler(tmp_path)
    try:
        before_due = scheduler.schedule(
            instruction_id="i_001",
            instruction=instruction(),
            interval_ms=1_000,
            message="breathe",
        )
        scheduler.cancel((before_due.timer_id,))
        clock.advance_ms(10_000)
        assert scheduler.claim_due() == ()

        due_first = scheduler.schedule(
            instruction_id="i_002",
            instruction=instruction("e_000002", "second reminder"),
            interval_ms=1_000,
            message="stretch",
        )
        clock.advance_ms(1_000)
        claimed = scheduler.claim_due()
        assert [fire.payload.timer_id for fire in claimed] == [due_first.timer_id]

        canceled = scheduler.cancel((due_first.timer_id,))
        assert canceled[0].status is TimerStatus.CANCELED
        clock.advance_ms(10_000)
        assert scheduler.claim_due() == ()

        row = store._connection.execute("SELECT COUNT(*) FROM ingress").fetchone()
        assert row == (1,)
    finally:
        store.close()


def test_interval_and_active_timer_limits_are_enforced(tmp_path: Path) -> None:
    config = RuntimeConfig(max_active_timers=1)
    store, _clock, scheduler = make_scheduler(tmp_path, config=config)
    try:
        with pytest.raises(TimerIntervalError):
            scheduler.schedule(
                instruction_id="i_001",
                instruction=instruction(),
                interval_ms=999,
                message="breathe",
            )
        first = scheduler.schedule(
            instruction_id="i_001",
            instruction=instruction(),
            interval_ms=1_000,
            message="breathe",
        )
        with pytest.raises(TimerLimitExceededError):
            scheduler.schedule(
                instruction_id="i_002",
                instruction=instruction("e_000002", "stretch every second"),
                interval_ms=1_000,
                message="stretch",
            )
        scheduler.cancel((first.timer_id,))
        second = scheduler.schedule(
            instruction_id="i_002",
            instruction=instruction("e_000002", "stretch every second"),
            interval_ms=1_000,
            message="stretch",
        )
        assert second.status is TimerStatus.ACTIVE
    finally:
        store.close()


def test_config_and_anchor_reject_unstorable_due_timestamps(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="SQLite nanosecond range"):
        RuntimeConfig(max_timer_interval_ms=SQLITE_MAX_INTEGER // 1_000_000 + 1)

    store = Store(tmp_path / "overflow.sqlite3")
    clock = ManualClock(mono_ns=SQLITE_MAX_INTEGER - 500_000_000)
    scheduler = TimerScheduler(store, clock)
    try:
        with pytest.raises(TimerIntervalError, match="SQLite integer range"):
            scheduler.schedule(
                instruction_id="i_001",
                instruction=instruction(),
                interval_ms=1_000,
                message="breathe",
            )
        assert store.active_timer_count() == 0
        assert store.allocate_id("timer") == "t_001"
    finally:
        store.close()


def test_due_ledger_update_id_allocation_and_ingress_append_roll_back_together(
    tmp_path: Path,
) -> None:
    store, clock, scheduler = make_scheduler(tmp_path)
    try:
        record = scheduler.schedule(
            instruction_id="i_001",
            instruction=instruction(),
            interval_ms=1_000,
            message="breathe",
        )
        clock.advance_ms(1_000)

        with pytest.raises(RuntimeError, match="rollback due"):
            with store.transaction():
                claimed = scheduler.claim_due()
                assert claimed[0].event_id == "e_000001"
                assert store.get_timer(record.timer_id).fire_count == 1  # type: ignore[union-attr]
                raise RuntimeError("rollback due")

        restored = store.get_timer(record.timer_id)
        assert restored is not None
        assert restored.fire_count == 0
        assert restored.next_due_mono_ns == 1_000_000_000
        assert store._connection.execute("SELECT COUNT(*) FROM ingress").fetchone() == (0,)

        committed = scheduler.claim_due()
        assert committed[0].event_id == "e_000001"
        _, rendered = store.commit_policy(committed[0].draft)
        assert parse_event(rendered).payload.fire_count == 1
    finally:
        store.close()


@pytest.mark.asyncio
async def test_scheduler_enqueues_only_after_the_due_fire_commit(tmp_path: Path) -> None:
    store, clock, scheduler = make_scheduler(tmp_path)
    delivered = asyncio.Event()
    observed: list[str] = []
    try:
        scheduler.schedule(
            instruction_id="i_001",
            instruction=instruction(),
            interval_ms=1_000,
            message="breathe",
        )

        async def enqueue(fire) -> None:
            row = store._connection.execute(
                "SELECT id FROM ingress WHERE id = ?", (fire.event_id,)
            ).fetchone()
            observed.append(row[0])
            delivered.set()

        task = asyncio.create_task(scheduler.run(enqueue))
        await asyncio.sleep(0)
        clock.advance_ms(1_000)
        await asyncio.wait_for(delivered.wait(), timeout=1)
        scheduler.close()
        await asyncio.wait_for(task, timeout=1)

        assert observed == ["e_000001"]
    finally:
        scheduler.close()
        store.close()
