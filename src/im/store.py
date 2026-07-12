"""Durable SQLite lanes, runtime state, and per-session identifiers."""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from im.canonical_json import TimJsonValue, canonicalize_tim_json, parse_tim_json
from im.schema.common import Activity, Disposition, TimerStatus, ToolResultStatus
from im.schema.events import Event
from im.serialize import join_rendered_events, parse_event, render_event


class StoreError(RuntimeError):
    """Base error for store contract violations."""


class DispositionTransitionError(StoreError):
    """Raised when a disposition attempts a non-one-way transition."""


class DuplicatePendingToolRequestError(StoreError):
    """Raised when a canonical tool request is already pending."""


class ToolRequestDeliveryError(StoreError):
    """Raised when a scripted tool result cannot be delivered atomically."""


@dataclass(frozen=True, slots=True)
class PolicyEventDraft:
    """Operational event state carried from ingress to policy commit."""

    id: str
    source: str
    kind: str
    payload: object
    occurred_mono_ns: int
    activity: Activity | str | None = None

    def __post_init__(self) -> None:
        if isinstance(self.occurred_mono_ns, bool) or not isinstance(self.occurred_mono_ns, int):
            raise TypeError("occurred_mono_ns must be an integer")
        if self.occurred_mono_ns < 0:
            raise ValueError("occurred_mono_ns must be non-negative")


@dataclass(frozen=True, slots=True)
class DispositionRecord:
    event_id: str
    state: Disposition
    by_action_event_id: str | None


@dataclass(frozen=True, slots=True)
class PolicyRecord:
    """One immutable policy row with its validated event projection."""

    seq: int
    segment_index: int
    event_id: str
    dt_ms: int
    occurred_mono_ns: int
    rendered: bytes
    event: Event


@dataclass(frozen=True, slots=True)
class TimerLedgerRecord:
    """The durable timer state needed by the scheduler and checkpoint projection.

    These fields deliberately include the originating span verbatim.  They are
    operational ledger data, not a model-facing event payload; retaining them is
    what lets later checkpoint projection preserve causal instruction text.
    """

    timer_id: str
    instruction_id: str
    instruction_event_id: str
    instruction_start_utf16: int
    instruction_end_utf16: int
    instruction_text: str
    interval_ms: int
    message: str
    anchor_mono_ns: int
    anchor_utc: str
    next_due_mono_ns: int | None
    fire_count: int
    status: TimerStatus
    idempotency_key: str


class ToolRequestStatus(StrEnum):
    """Lifecycle of a fake-tool request, distinct from the result outcome."""

    PENDING = "pending"
    COMPLETED = "completed"


@dataclass(frozen=True, slots=True)
class ToolRequestRecord:
    """Durable scripted request state owned by the deterministic tool adapter."""

    request_id: str
    fact_event_id: str
    tool: str
    args: TimJsonValue
    canonical_key: str
    status: ToolRequestStatus
    requested_mono_ns: int
    due_mono_ns: int
    result_status: ToolResultStatus
    result_data: TimJsonValue
    result_event_id: str | None


class IdKind(StrEnum):
    EVENT = "event"
    TIMER = "timer"
    REQUEST = "request"
    INSTRUCTION = "instruction"


_ID_FORMAT: dict[IdKind, tuple[str, int]] = {
    IdKind.EVENT: ("e", 6),
    IdKind.TIMER: ("t", 3),
    IdKind.REQUEST: ("r", 3),
    IdKind.INSTRUCTION: ("i", 3),
}

_CURRENT_SEGMENT_KEY = "current_segment_index"

_TIMER_SELECT = """
    timer_id,
    instruction_id,
    instruction_event_id,
    instruction_start_utf16,
    instruction_end_utf16,
    instruction_text,
    interval_ms,
    message,
    anchor_mono_ns,
    anchor_utc,
    next_due_mono_ns,
    fire_count,
    status,
    idempotency_key
"""

_SCHEMA = """
CREATE TABLE IF NOT EXISTS ingress (
    id TEXT PRIMARY KEY,
    received_utc TEXT NOT NULL,
    received_mono_ns INTEGER NOT NULL CHECK (received_mono_ns >= 0),
    source TEXT NOT NULL,
    kind TEXT NOT NULL,
    payload BLOB NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS policy (
    seq INTEGER PRIMARY KEY,
    segment_index INTEGER NOT NULL CHECK (segment_index >= 0),
    event_id TEXT NOT NULL UNIQUE,
    dt_ms INTEGER NOT NULL CHECK (dt_ms >= 0),
    occurred_mono_ns INTEGER NOT NULL CHECK (occurred_mono_ns >= 0),
    rendered BLOB NOT NULL
) STRICT;

CREATE INDEX IF NOT EXISTS policy_segment_seq ON policy(segment_index, seq);

CREATE TABLE IF NOT EXISTS audit (
    rowid INTEGER PRIMARY KEY,
    ts_utc TEXT NOT NULL,
    kind TEXT NOT NULL,
    payload BLOB NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS dispositions (
    event_id TEXT PRIMARY KEY,
    state TEXT NOT NULL CHECK (state IN ('open', 'handled', 'skipped', 'superseded')),
    by_action_event_id TEXT
) STRICT;

CREATE TABLE IF NOT EXISTS timers (
    timer_id TEXT PRIMARY KEY,
    instruction_id TEXT NOT NULL,
    instruction_event_id TEXT NOT NULL,
    instruction_start_utf16 INTEGER NOT NULL CHECK (instruction_start_utf16 >= 0),
    instruction_end_utf16 INTEGER NOT NULL
        CHECK (instruction_end_utf16 > instruction_start_utf16),
    instruction_text TEXT NOT NULL,
    interval_ms INTEGER NOT NULL CHECK (interval_ms > 0),
    message TEXT NOT NULL,
    anchor_mono_ns INTEGER NOT NULL CHECK (anchor_mono_ns >= 0),
    anchor_utc TEXT NOT NULL,
    next_due_mono_ns INTEGER,
    fire_count INTEGER NOT NULL DEFAULT 0 CHECK (fire_count >= 0),
    status TEXT NOT NULL
        CHECK (status IN ('scheduled', 'active', 'canceled', 'exhausted', 'failed')),
    idempotency_key TEXT NOT NULL UNIQUE
) STRICT;

CREATE TABLE IF NOT EXISTS tool_requests (
    request_id TEXT PRIMARY KEY,
    fact_event_id TEXT NOT NULL,
    tool TEXT NOT NULL,
    args BLOB NOT NULL,
    canonical_key TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending', 'completed')),
    requested_mono_ns INTEGER NOT NULL CHECK (requested_mono_ns >= 0),
    due_mono_ns INTEGER NOT NULL CHECK (due_mono_ns >= 0),
    result_status TEXT NOT NULL CHECK (result_status IN ('succeeded', 'failed')),
    result_data BLOB NOT NULL,
    result_event_id TEXT
) STRICT;

CREATE UNIQUE INDEX IF NOT EXISTS tool_requests_pending_canonical_key
ON tool_requests(canonical_key)
WHERE status = 'pending';

CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value BLOB NOT NULL
) STRICT;
"""

_EVOLVED_TABLE_COLUMNS = {
    "timers": (
        "timer_id",
        "instruction_id",
        "instruction_event_id",
        "instruction_start_utf16",
        "instruction_end_utf16",
        "instruction_text",
        "interval_ms",
        "message",
        "anchor_mono_ns",
        "anchor_utc",
        "next_due_mono_ns",
        "fire_count",
        "status",
        "idempotency_key",
    ),
    "tool_requests": (
        "request_id",
        "fact_event_id",
        "tool",
        "args",
        "canonical_key",
        "status",
        "requested_mono_ns",
        "due_mono_ns",
        "result_status",
        "result_data",
        "result_event_id",
    ),
}


class Store:
    """One durable SQLite database for a single interaction session."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(self.path, isolation_level=None)
        try:
            self._reject_incompatible_existing_schema()
        except BaseException:
            self._connection.close()
            raise
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._connection.execute("PRAGMA busy_timeout = 5000")
        self._connection.execute("PRAGMA synchronous = NORMAL")
        journal_mode = self._connection.execute("PRAGMA journal_mode = WAL").fetchone()[0]
        if str(journal_mode).lower() != "wal":
            self._connection.close()
            raise StoreError("SQLite WAL mode is unavailable")
        self._connection.executescript(_SCHEMA)
        self._transaction_depth = 0
        self._savepoint_counter = 0

    def _reject_incompatible_existing_schema(self) -> None:
        """Fail clearly rather than half-opening a pre-contract session database.

        Phase 0 has no persisted-session migration contract. Timer provenance and scripted tool
        delivery both changed atomically before the runtime shipped, so silently patching old
        tables would manufacture incomplete state. Fresh sessions are the only safe upgrade path.
        """
        for table, expected in _EVOLVED_TABLE_COLUMNS.items():
            rows = self._connection.execute(f"PRAGMA table_info({table})").fetchall()
            if rows and tuple(str(row[1]) for row in rows) != expected:
                raise StoreError(
                    f"incompatible {table} schema; create a new Phase 0 session database"
                )

        tool_columns = self._connection.execute("PRAGMA table_info(tool_requests)").fetchall()
        if not tool_columns:
            return
        for index in self._connection.execute("PRAGMA index_list(tool_requests)").fetchall():
            index_name = str(index[1])
            unique = bool(index[2])
            partial = bool(index[4])
            columns = tuple(
                str(row[2])
                for row in self._connection.execute(f"PRAGMA index_info({index_name})").fetchall()
            )
            if unique and not partial and columns == ("canonical_key",):
                raise StoreError(
                    "incompatible tool_requests uniqueness; create a new Phase 0 session database"
                )

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> "Store":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    @contextmanager
    def transaction(self) -> Iterator[None]:
        """Open a composable write transaction for one atomic unit of work."""
        is_root = self._transaction_depth == 0
        savepoint: str | None = None
        if is_root:
            self._connection.execute("BEGIN IMMEDIATE")
        else:
            savepoint = f"im_store_{self._savepoint_counter}"
            self._savepoint_counter += 1
            self._connection.execute(f"SAVEPOINT {savepoint}")
        self._transaction_depth += 1
        try:
            yield
            if is_root:
                self._connection.commit()
            else:
                self._connection.execute(f"RELEASE SAVEPOINT {savepoint}")
        except BaseException:
            try:
                if is_root:
                    self._connection.rollback()
                else:
                    self._connection.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
                    self._connection.execute(f"RELEASE SAVEPOINT {savepoint}")
            except sqlite3.Error:
                pass
            raise
        finally:
            self._transaction_depth -= 1

    def get_meta(self, key: str) -> TimJsonValue | None:
        row = self._connection.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return None if row is None else parse_tim_json(bytes(row[0]))

    def _current_segment_index(self) -> int:
        value = self.get_meta(_CURRENT_SEGMENT_KEY)
        if value is None:
            return 0
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise StoreError("current_segment_index must be a non-negative integer")
        return value

    def current_segment_index(self) -> int:
        """Return the active immutable-context segment index."""
        return self._current_segment_index()

    def set_meta(self, key: str, value: object) -> None:
        if not key:
            raise ValueError("meta key must not be empty")
        if key == _CURRENT_SEGMENT_KEY:
            raise ValueError("current_segment_index is reserved for commit_new_segment")
        encoded = canonicalize_tim_json(value)
        with self.transaction():
            self._connection.execute(
                """
                INSERT INTO meta(key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (key, encoded),
            )

    def allocate_id(self, kind: IdKind | str) -> str:
        try:
            id_kind = IdKind(kind)
        except ValueError as error:
            raise ValueError(f"unknown id kind: {kind}") from error
        counter_key = f"id_counter:{id_kind.value}"
        with self.transaction():
            row = self._connection.execute(
                "SELECT value FROM meta WHERE key = ?", (counter_key,)
            ).fetchone()
            previous = 0 if row is None else parse_tim_json(bytes(row[0]))
            if isinstance(previous, bool) or not isinstance(previous, int) or previous < 0:
                raise StoreError(f"invalid persisted counter for {id_kind.value}")
            current = previous + 1
            self._connection.execute(
                """
                INSERT INTO meta(key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (counter_key, canonicalize_tim_json(current)),
            )
        prefix, width = _ID_FORMAT[id_kind]
        return f"{prefix}_{current:0{width}d}"

    def append_ingress(
        self,
        *,
        event_id: str,
        received_utc: str,
        received_mono_ns: int,
        source: str,
        kind: str,
        payload: bytes,
    ) -> None:
        """Append one ingress record, preserving payload bytes exactly as received."""
        if not all((event_id, received_utc, source, kind)):
            raise ValueError("ingress text fields must not be empty")
        if isinstance(received_mono_ns, bool) or not isinstance(received_mono_ns, int):
            raise TypeError("received_mono_ns must be an integer")
        if received_mono_ns < 0:
            raise ValueError("received_mono_ns must be non-negative")
        if not isinstance(payload, bytes):
            raise TypeError("ingress payload must be bytes")
        with self.transaction():
            self._connection.execute(
                """
                INSERT INTO ingress(id, received_utc, received_mono_ns, source, kind, payload)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (event_id, received_utc, received_mono_ns, source, kind, payload),
            )

    @staticmethod
    def _timer_record(row: tuple[object, ...] | None) -> TimerLedgerRecord | None:
        if row is None:
            return None
        return TimerLedgerRecord(
            timer_id=str(row[0]),
            instruction_id=str(row[1]),
            instruction_event_id=str(row[2]),
            instruction_start_utf16=int(row[3]),
            instruction_end_utf16=int(row[4]),
            instruction_text=str(row[5]),
            interval_ms=int(row[6]),
            message=str(row[7]),
            anchor_mono_ns=int(row[8]),
            anchor_utc=str(row[9]),
            next_due_mono_ns=None if row[10] is None else int(row[10]),
            fire_count=int(row[11]),
            status=TimerStatus(str(row[12])),
            idempotency_key=str(row[13]),
        )

    @staticmethod
    def _require_timer_text(value: object, name: str) -> str:
        if not isinstance(value, str) or not value:
            raise ValueError(f"{name} must be a non-empty string")
        try:
            value.encode("utf-8")
        except UnicodeEncodeError as error:
            raise ValueError(f"{name} must be valid Unicode text") from error
        return value

    @staticmethod
    def _require_nonnegative_int(value: object, name: str) -> int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError(f"{name} must be an integer")
        if value < 0:
            raise ValueError(f"{name} must be non-negative")
        return value

    @classmethod
    def _require_positive_int(cls, value: object, name: str) -> int:
        value = cls._require_nonnegative_int(value, name)
        if value == 0:
            raise ValueError(f"{name} must be positive")
        return value

    def get_timer(self, timer_id: str) -> TimerLedgerRecord | None:
        """Return one timer ledger record without exposing the SQLite connection."""
        self._require_timer_text(timer_id, "timer_id")
        row = self._connection.execute(
            f"SELECT {_TIMER_SELECT} FROM timers WHERE timer_id = ?", (timer_id,)
        ).fetchone()
        return self._timer_record(row)

    def get_timer_by_idempotency_key(self, idempotency_key: str) -> TimerLedgerRecord | None:
        """Return the retry target for a canonical scheduling operation, if any."""
        self._require_timer_text(idempotency_key, "idempotency_key")
        row = self._connection.execute(
            f"SELECT {_TIMER_SELECT} FROM timers WHERE idempotency_key = ?",
            (idempotency_key,),
        ).fetchone()
        return self._timer_record(row)

    def insert_scheduled_timer(
        self,
        *,
        timer_id: str,
        instruction_id: str,
        instruction_event_id: str,
        instruction_start_utf16: int,
        instruction_end_utf16: int,
        instruction_text: str,
        interval_ms: int,
        message: str,
        anchor_mono_ns: int,
        anchor_utc: str,
        next_due_mono_ns: int,
        idempotency_key: str,
    ) -> TimerLedgerRecord:
        """Insert a timer at the first ``scheduled`` state of its lifecycle.

        Callers normally activate it in the same enclosing transaction.  Keeping
        the two ledger transitions explicit gives the execution layer a durable
        all-or-nothing boundary with its scheduled acknowledgement event.
        """
        timer_id = self._require_timer_text(timer_id, "timer_id")
        instruction_id = self._require_timer_text(instruction_id, "instruction_id")
        instruction_event_id = self._require_timer_text(
            instruction_event_id, "instruction_event_id"
        )
        start = self._require_nonnegative_int(instruction_start_utf16, "instruction_start_utf16")
        end = self._require_positive_int(instruction_end_utf16, "instruction_end_utf16")
        if end <= start:
            raise ValueError("instruction span end must follow start")
        instruction_text = self._require_timer_text(instruction_text, "instruction_text")
        interval_ms = self._require_positive_int(interval_ms, "interval_ms")
        message = self._require_timer_text(message, "message")
        anchor_mono_ns = self._require_nonnegative_int(anchor_mono_ns, "anchor_mono_ns")
        anchor_utc = self._require_timer_text(anchor_utc, "anchor_utc")
        next_due_mono_ns = self._require_nonnegative_int(next_due_mono_ns, "next_due_mono_ns")
        if next_due_mono_ns <= anchor_mono_ns:
            raise ValueError("next_due_mono_ns must follow the anchor")
        idempotency_key = self._require_timer_text(idempotency_key, "idempotency_key")

        with self.transaction():
            self._connection.execute(
                """
                INSERT INTO timers(
                    timer_id, instruction_id, instruction_event_id,
                    instruction_start_utf16, instruction_end_utf16, instruction_text,
                    interval_ms, message, anchor_mono_ns, anchor_utc, next_due_mono_ns,
                    fire_count, status, idempotency_key
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
                """,
                (
                    timer_id,
                    instruction_id,
                    instruction_event_id,
                    start,
                    end,
                    instruction_text,
                    interval_ms,
                    message,
                    anchor_mono_ns,
                    anchor_utc,
                    next_due_mono_ns,
                    TimerStatus.SCHEDULED.value,
                    idempotency_key,
                ),
            )
            record = self.get_timer(timer_id)
            if record is None:
                raise StoreError("inserted timer is not readable")
            return record

    def activate_timer(self, timer_id: str) -> TimerLedgerRecord:
        """Transition one just-created timer from ``scheduled`` to ``active``."""
        timer_id = self._require_timer_text(timer_id, "timer_id")
        with self.transaction():
            cursor = self._connection.execute(
                """
                UPDATE timers SET status = ?
                WHERE timer_id = ? AND status = ?
                """,
                (TimerStatus.ACTIVE.value, timer_id, TimerStatus.SCHEDULED.value),
            )
            if cursor.rowcount != 1:
                raise StoreError("timer is not scheduled")
            record = self.get_timer(timer_id)
            if record is None:
                raise StoreError("activated timer is not readable")
            return record

    def active_timer_count(self) -> int:
        """Return the number of currently firing timer sources."""
        row = self._connection.execute(
            "SELECT COUNT(*) FROM timers WHERE status = ?", (TimerStatus.ACTIVE.value,)
        ).fetchone()
        return int(row[0])

    def active_timers(self) -> tuple[TimerLedgerRecord, ...]:
        """Return active timers in deterministic timer-id order."""
        rows = self._connection.execute(
            f"SELECT {_TIMER_SELECT} FROM timers WHERE status = ? ORDER BY timer_id",
            (TimerStatus.ACTIVE.value,),
        ).fetchall()
        return tuple(self._timer_record(row) for row in rows if row is not None)

    def timers(self) -> tuple[TimerLedgerRecord, ...]:
        """Return the complete timer ledger in deterministic ID order."""
        rows = self._connection.execute(
            f"SELECT {_TIMER_SELECT} FROM timers ORDER BY timer_id"
        ).fetchall()
        return tuple(self._timer_record(row) for row in rows if row is not None)

    def due_active_timers(self, now_mono_ns: int) -> tuple[TimerLedgerRecord, ...]:
        """Return active timers due at ``now_mono_ns`` in deterministic due order."""
        now_mono_ns = self._require_nonnegative_int(now_mono_ns, "now_mono_ns")
        rows = self._connection.execute(
            f"""
            SELECT {_TIMER_SELECT}
            FROM timers
            WHERE status = ? AND next_due_mono_ns <= ?
            ORDER BY next_due_mono_ns, timer_id
            """,
            (TimerStatus.ACTIVE.value, now_mono_ns),
        ).fetchall()
        return tuple(self._timer_record(row) for row in rows if row is not None)

    def next_active_due_mono_ns(self) -> int | None:
        """Return the next active due timestamp, if any."""
        row = self._connection.execute(
            """
            SELECT next_due_mono_ns FROM timers
            WHERE status = ?
            ORDER BY next_due_mono_ns, timer_id LIMIT 1
            """,
            (TimerStatus.ACTIVE.value,),
        ).fetchone()
        return None if row is None else int(row[0])

    def advance_due_timer(
        self,
        *,
        timer_id: str,
        expected_next_due_mono_ns: int,
        fire_count: int,
        next_due_mono_ns: int,
    ) -> TimerLedgerRecord:
        """Atomically claim one due active timer for a coalesced fire."""
        timer_id = self._require_timer_text(timer_id, "timer_id")
        expected_next_due_mono_ns = self._require_nonnegative_int(
            expected_next_due_mono_ns, "expected_next_due_mono_ns"
        )
        fire_count = self._require_positive_int(fire_count, "fire_count")
        next_due_mono_ns = self._require_nonnegative_int(next_due_mono_ns, "next_due_mono_ns")
        if next_due_mono_ns <= expected_next_due_mono_ns:
            raise ValueError("next due time must advance")
        with self.transaction():
            cursor = self._connection.execute(
                """
                UPDATE timers
                SET fire_count = ?, next_due_mono_ns = ?
                WHERE timer_id = ? AND status = ? AND next_due_mono_ns = ?
                """,
                (
                    fire_count,
                    next_due_mono_ns,
                    timer_id,
                    TimerStatus.ACTIVE.value,
                    expected_next_due_mono_ns,
                ),
            )
            if cursor.rowcount != 1:
                raise StoreError("due timer claim lost its active state")
            record = self.get_timer(timer_id)
            if record is None:
                raise StoreError("claimed timer is not readable")
            return record

    def cancel_active_timers(self, timer_ids: tuple[str, ...]) -> tuple[TimerLedgerRecord, ...]:
        """Cancel the exact active target set, or make no ledger change at all."""
        if not timer_ids:
            raise ValueError("timer_ids must not be empty")
        if len(timer_ids) != len(set(timer_ids)) or timer_ids != tuple(sorted(timer_ids)):
            raise ValueError("timer_ids must be unique and lexicographically sorted")
        for timer_id in timer_ids:
            self._require_timer_text(timer_id, "timer_id")

        placeholders = ", ".join("?" for _ in timer_ids)
        with self.transaction():
            rows = self._connection.execute(
                f"""
                SELECT {_TIMER_SELECT} FROM timers
                WHERE timer_id IN ({placeholders})
                ORDER BY timer_id
                """,
                timer_ids,
            ).fetchall()
            records = tuple(self._timer_record(row) for row in rows if row is not None)
            if len(records) != len(timer_ids) or any(
                record.status is not TimerStatus.ACTIVE for record in records
            ):
                raise StoreError("all cancellation targets must be active timers")
            self._connection.execute(
                f"""
                UPDATE timers
                SET status = ?, next_due_mono_ns = NULL
                WHERE timer_id IN ({placeholders}) AND status = ?
                """,
                (TimerStatus.CANCELED.value, *timer_ids, TimerStatus.ACTIVE.value),
            )
            canceled = tuple(self.get_timer(timer_id) for timer_id in timer_ids)
            if any(record is None for record in canceled):
                raise StoreError("canceled timer is not readable")
            return tuple(record for record in canceled if record is not None)

    def cancel_all_active_timers(self) -> tuple[TimerLedgerRecord, ...]:
        """Cancel every currently active timer as one transaction."""
        with self.transaction():
            active_ids = tuple(record.timer_id for record in self.active_timers())
            if not active_ids:
                return ()
            return self.cancel_active_timers(active_ids)

    def commit_policy(self, draft: PolicyEventDraft) -> tuple[int, bytes]:
        """Assign global sequence and segment-relative time, then freeze one event."""
        if not isinstance(draft, PolicyEventDraft):
            raise TypeError("commit_policy requires a PolicyEventDraft")
        with self.transaction():
            segment_index = self._current_segment_index()
            return self._commit_policy_in_transaction(draft, segment_index, starts_segment=False)

    def commit_new_segment(self, first_draft: PolicyEventDraft) -> tuple[int, bytes]:
        """Advance exactly one segment and atomically commit its first event."""
        if not isinstance(first_draft, PolicyEventDraft):
            raise TypeError("commit_new_segment requires a PolicyEventDraft")
        with self.transaction():
            segment_index = self._current_segment_index() + 1
            self._connection.execute(
                """
                INSERT INTO meta(key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (_CURRENT_SEGMENT_KEY, canonicalize_tim_json(segment_index)),
            )
            return self._commit_policy_in_transaction(
                first_draft, segment_index, starts_segment=True
            )

    def _commit_policy_in_transaction(
        self,
        draft: PolicyEventDraft,
        segment_index: int,
        *,
        starts_segment: bool,
    ) -> tuple[int, bytes]:
        predecessor = self._connection.execute(
            """
            SELECT seq, segment_index, occurred_mono_ns
            FROM policy ORDER BY seq DESC LIMIT 1
            """
        ).fetchone()
        if predecessor is None:
            if starts_segment:
                raise StoreError("cannot advance from an empty initial segment")
            if segment_index != 0:
                raise StoreError("initial policy event must belong to segment zero")
            seq = 0
            dt_ms = 0
        else:
            previous_seq = int(predecessor[0])
            previous_segment_index = int(predecessor[1])
            previous_mono_ns = int(predecessor[2])
            if draft.occurred_mono_ns < previous_mono_ns:
                raise StoreError("policy occurrence time decreased")
            if starts_segment:
                if segment_index != previous_segment_index + 1:
                    raise StoreError("new policy segment must advance exactly one index")
                dt_ms = 0
            else:
                if segment_index != previous_segment_index:
                    raise StoreError("a new policy segment must begin with commit_new_segment")
                dt_ms = (draft.occurred_mono_ns - previous_mono_ns) // 1_000_000
            seq = previous_seq + 1

        event: dict[str, object] = {
            "v": 1,
            "id": draft.id,
            "seq": seq,
            "dt_ms": dt_ms,
            "source": draft.source,
            "kind": draft.kind,
        }
        if draft.activity is not None:
            event["activity"] = draft.activity
        event["payload"] = draft.payload
        rendered = render_event(event)
        self._connection.execute(
            """
            INSERT INTO policy(
                seq, segment_index, event_id, dt_ms, occurred_mono_ns, rendered
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (seq, segment_index, draft.id, dt_ms, draft.occurred_mono_ns, rendered),
        )
        return seq, rendered

    def policy_bytes(self, segment_index: int | None = None) -> bytes:
        """Return frozen context bytes for one segment; default to the current segment."""
        if segment_index is None:
            segment_index = self._current_segment_index()
        if isinstance(segment_index, bool) or not isinstance(segment_index, int):
            raise TypeError("segment_index must be an integer")
        if segment_index < 0:
            raise ValueError("segment_index must be non-negative")
        rows = self._connection.execute(
            "SELECT rendered FROM policy WHERE segment_index = ? ORDER BY seq", (segment_index,)
        ).fetchall()
        return join_rendered_events(bytes(row[0]) for row in rows)

    def policy_records(self, segment_index: int | None = None) -> tuple[PolicyRecord, ...]:
        """Return validated immutable policy rows, optionally restricted to one segment."""
        if segment_index is not None:
            if isinstance(segment_index, bool) or not isinstance(segment_index, int):
                raise TypeError("segment_index must be an integer")
            if segment_index < 0:
                raise ValueError("segment_index must be non-negative")
            rows = self._connection.execute(
                """
                SELECT seq, segment_index, event_id, dt_ms, occurred_mono_ns, rendered
                FROM policy WHERE segment_index = ? ORDER BY seq
                """,
                (segment_index,),
            ).fetchall()
        else:
            rows = self._connection.execute(
                """
                SELECT seq, segment_index, event_id, dt_ms, occurred_mono_ns, rendered
                FROM policy ORDER BY seq
                """
            ).fetchall()
        return tuple(
            PolicyRecord(
                seq=int(row[0]),
                segment_index=int(row[1]),
                event_id=str(row[2]),
                dt_ms=int(row[3]),
                occurred_mono_ns=int(row[4]),
                rendered=bytes(row[5]),
                event=parse_event(bytes(row[5])),
            )
            for row in rows
        )

    def audit(self, kind: str, payload: object, *, ts_utc: str | None = None) -> int:
        """Append one canonical audit record and return its row id."""
        if not kind:
            raise ValueError("audit kind must not be empty")
        timestamp = ts_utc or datetime.now(UTC).isoformat(timespec="microseconds")
        if not timestamp:
            raise ValueError("audit timestamp must not be empty")
        encoded = canonicalize_tim_json(payload)
        with self.transaction():
            cursor = self._connection.execute(
                "INSERT INTO audit(ts_utc, kind, payload) VALUES (?, ?, ?)",
                (timestamp, kind, encoded),
            )
            row_id = int(cursor.lastrowid)
        return row_id

    def create_tool_request(
        self,
        *,
        request_id: str,
        fact_event_id: str,
        tool: str,
        args: object,
        canonical_key: str,
        requested_mono_ns: int,
        due_mono_ns: int,
        result_status: ToolResultStatus | str,
        result_data: object,
    ) -> ToolRequestRecord:
        """Persist one scripted tool request with a pending-only dedup key.

        Tool registry validation intentionally belongs to ``im.tools``.  This
        ledger method only enforces durable representation and lifecycle
        mechanics, which lets the later license projection read the same rows.
        """
        if not all((request_id, tool, canonical_key)):
            raise ValueError("tool request identifiers and key must not be empty")
        if not isinstance(fact_event_id, str):
            raise TypeError("fact_event_id must be a string")
        for name, value in (
            ("requested_mono_ns", requested_mono_ns),
            ("due_mono_ns", due_mono_ns),
        ):
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"{name} must be an integer")
            if value < 0:
                raise ValueError(f"{name} must be non-negative")
        if due_mono_ns < requested_mono_ns:
            raise ValueError("tool result due time precedes request time")
        try:
            normalized_status = ToolResultStatus(result_status)
        except ValueError as error:
            raise ValueError(f"unknown tool result status: {result_status}") from error
        encoded_args = canonicalize_tim_json(args)
        encoded_result_data = canonicalize_tim_json(result_data)
        with self.transaction():
            try:
                self._connection.execute(
                    """
                    INSERT INTO tool_requests(
                        request_id, fact_event_id, tool, args, canonical_key, status,
                        requested_mono_ns, due_mono_ns, result_status, result_data, result_event_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
                    """,
                    (
                        request_id,
                        fact_event_id,
                        tool,
                        encoded_args,
                        canonical_key,
                        ToolRequestStatus.PENDING.value,
                        requested_mono_ns,
                        due_mono_ns,
                        normalized_status.value,
                        encoded_result_data,
                    ),
                )
            except sqlite3.IntegrityError as error:
                if self.find_pending_tool_request(canonical_key) is not None:
                    raise DuplicatePendingToolRequestError(
                        "an equivalent tool request is already pending"
                    ) from error
                raise
        record = self.get_tool_request(request_id)
        if record is None:  # pragma: no cover - guarded by the successful insert above.
            raise StoreError("inserted tool request is unavailable")
        return record

    def get_tool_request(self, request_id: str) -> ToolRequestRecord | None:
        """Return one durable tool request, if it exists."""
        row = self._connection.execute(
            """
            SELECT request_id, fact_event_id, tool, args, canonical_key, status,
                   requested_mono_ns, due_mono_ns, result_status, result_data, result_event_id
            FROM tool_requests WHERE request_id = ?
            """,
            (request_id,),
        ).fetchone()
        return None if row is None else self._tool_request_record(row)

    def find_pending_tool_request(self, canonical_key: str) -> ToolRequestRecord | None:
        """Find the one equivalent request protected by the partial unique index."""
        if not canonical_key:
            raise ValueError("canonical_key must not be empty")
        row = self._connection.execute(
            """
            SELECT request_id, fact_event_id, tool, args, canonical_key, status,
                   requested_mono_ns, due_mono_ns, result_status, result_data, result_event_id
            FROM tool_requests
            WHERE canonical_key = ? AND status = ?
            """,
            (canonical_key, ToolRequestStatus.PENDING.value),
        ).fetchone()
        return None if row is None else self._tool_request_record(row)

    def pending_tool_requests(self) -> tuple[ToolRequestRecord, ...]:
        """Return all pending requests in stable request-id order."""
        rows = self._connection.execute(
            """
            SELECT request_id, fact_event_id, tool, args, canonical_key, status,
                   requested_mono_ns, due_mono_ns, result_status, result_data, result_event_id
            FROM tool_requests
            WHERE status = ?
            ORDER BY request_id
            """,
            (ToolRequestStatus.PENDING.value,),
        ).fetchall()
        return tuple(self._tool_request_record(row) for row in rows)

    def tool_requests(self) -> tuple[ToolRequestRecord, ...]:
        """Return the complete tool ledger in deterministic request-ID order."""
        rows = self._connection.execute(
            """
            SELECT request_id, fact_event_id, tool, args, canonical_key, status,
                   requested_mono_ns, due_mono_ns, result_status, result_data, result_event_id
            FROM tool_requests ORDER BY request_id
            """
        ).fetchall()
        return tuple(self._tool_request_record(row) for row in rows)

    def due_tool_requests(self, now_mono_ns: int) -> tuple[ToolRequestRecord, ...]:
        """Return pending scripted requests whose result time has arrived."""
        if isinstance(now_mono_ns, bool) or not isinstance(now_mono_ns, int):
            raise TypeError("now_mono_ns must be an integer")
        if now_mono_ns < 0:
            raise ValueError("now_mono_ns must be non-negative")
        rows = self._connection.execute(
            """
            SELECT request_id, fact_event_id, tool, args, canonical_key, status,
                   requested_mono_ns, due_mono_ns, result_status, result_data, result_event_id
            FROM tool_requests
            WHERE status = ? AND due_mono_ns <= ?
            ORDER BY due_mono_ns, request_id
            """,
            (ToolRequestStatus.PENDING.value, now_mono_ns),
        ).fetchall()
        return tuple(self._tool_request_record(row) for row in rows)

    def next_pending_tool_due_mono_ns(self) -> int | None:
        """Return the earliest pending scripted-result deadline, if any."""
        row = self._connection.execute(
            """
            SELECT due_mono_ns FROM tool_requests
            WHERE status = ?
            ORDER BY due_mono_ns, request_id LIMIT 1
            """,
            (ToolRequestStatus.PENDING.value,),
        ).fetchone()
        return None if row is None else int(row[0])

    def deliver_due_tool_request(
        self,
        *,
        request_id: str,
        event_id: str,
        received_utc: str,
        received_mono_ns: int,
        ingress_payload: bytes,
    ) -> ToolRequestRecord:
        """Atomically append a due result ingress row and complete its ledger row.

        The caller supplies the already allocated event id and exact ingress
        bytes.  Both are included in this transaction with ``result_event_id``;
        a failed ingress insert therefore leaves the request pending.
        """
        if not event_id:
            raise ValueError("event_id must not be empty")
        if not received_utc:
            raise ValueError("received_utc must not be empty")
        if isinstance(received_mono_ns, bool) or not isinstance(received_mono_ns, int):
            raise TypeError("received_mono_ns must be an integer")
        if received_mono_ns < 0:
            raise ValueError("received_mono_ns must be non-negative")
        if not isinstance(ingress_payload, bytes):
            raise TypeError("ingress_payload must be bytes")
        with self.transaction():
            record = self.get_tool_request(request_id)
            if record is None:
                raise ToolRequestDeliveryError("tool request does not exist")
            if record.status is not ToolRequestStatus.PENDING:
                raise ToolRequestDeliveryError("tool request is no longer pending")
            if received_mono_ns < record.due_mono_ns:
                raise ToolRequestDeliveryError("tool result is not due")
            expected_payload = canonicalize_tim_json(
                {
                    "request_id": record.request_id,
                    "status": record.result_status.value,
                    "data": record.result_data,
                }
            )
            if ingress_payload != expected_payload:
                raise ToolRequestDeliveryError(
                    "tool result ingress payload does not match the scripted request"
                )
            self.append_ingress(
                event_id=event_id,
                received_utc=received_utc,
                received_mono_ns=received_mono_ns,
                source="tool",
                kind="result",
                payload=ingress_payload,
            )
            self._connection.execute(
                """
                UPDATE tool_requests
                SET status = ?, result_event_id = ?
                WHERE request_id = ? AND status = ?
                """,
                (
                    ToolRequestStatus.COMPLETED.value,
                    event_id,
                    request_id,
                    ToolRequestStatus.PENDING.value,
                ),
            )
        completed = self.get_tool_request(request_id)
        if completed is None:  # pragma: no cover - guarded by the pre-update read.
            raise StoreError("completed tool request is unavailable")
        return completed

    @staticmethod
    def _tool_request_record(row: tuple[object, ...]) -> ToolRequestRecord:
        return ToolRequestRecord(
            request_id=str(row[0]),
            fact_event_id=str(row[1]),
            tool=str(row[2]),
            args=parse_tim_json(bytes(row[3])),
            canonical_key=str(row[4]),
            status=ToolRequestStatus(str(row[5])),
            requested_mono_ns=int(row[6]),
            due_mono_ns=int(row[7]),
            result_status=ToolResultStatus(str(row[8])),
            result_data=parse_tim_json(bytes(row[9])),
            result_event_id=None if row[10] is None else str(row[10]),
        )

    def get_disposition(self, event_id: str) -> DispositionRecord | None:
        row = self._connection.execute(
            "SELECT state, by_action_event_id FROM dispositions WHERE event_id = ?", (event_id,)
        ).fetchone()
        if row is None:
            return None
        return DispositionRecord(
            event_id=event_id,
            state=Disposition(row[0]),
            by_action_event_id=row[1],
        )

    def dispositions(self) -> tuple[DispositionRecord, ...]:
        """Return every external-event disposition in deterministic event-ID order."""
        rows = self._connection.execute(
            "SELECT event_id, state, by_action_event_id FROM dispositions ORDER BY event_id"
        ).fetchall()
        return tuple(
            DispositionRecord(
                event_id=str(row[0]),
                state=Disposition(str(row[1])),
                by_action_event_id=None if row[2] is None else str(row[2]),
            )
            for row in rows
        )

    def set_disposition(
        self,
        event_id: str,
        state: Disposition | str,
        *,
        by_action_event_id: str | None = None,
    ) -> DispositionRecord:
        """Create `open` or perform exactly one `open` to terminal transition."""
        if not event_id:
            raise ValueError("event_id must not be empty")
        try:
            target = Disposition(state)
        except ValueError as error:
            raise ValueError(f"unknown disposition: {state}") from error
        with self.transaction():
            row = self._connection.execute(
                "SELECT state FROM dispositions WHERE event_id = ?", (event_id,)
            ).fetchone()
            if row is None:
                if target is not Disposition.OPEN:
                    raise DispositionTransitionError("initial disposition must be open")
                self._connection.execute(
                    """
                    INSERT INTO dispositions(event_id, state, by_action_event_id)
                    VALUES (?, ?, ?)
                    """,
                    (event_id, target.value, by_action_event_id),
                )
            else:
                current = Disposition(row[0])
                terminal = {
                    Disposition.HANDLED,
                    Disposition.SKIPPED,
                    Disposition.SUPERSEDED,
                }
                if current is not Disposition.OPEN or target not in terminal:
                    raise DispositionTransitionError(
                        f"invalid disposition transition: {current.value} -> {target.value}"
                    )
                self._connection.execute(
                    """
                    UPDATE dispositions SET state = ?, by_action_event_id = ? WHERE event_id = ?
                    """,
                    (target.value, by_action_event_id, event_id),
                )
        return DispositionRecord(event_id, target, by_action_event_id)
