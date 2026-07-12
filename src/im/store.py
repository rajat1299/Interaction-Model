"""Durable SQLite lanes, runtime state, and per-session identifiers."""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from im.canonical_json import TimJsonValue, canonicalize_tim_json, parse_tim_json
from im.schema.common import Activity, Disposition
from im.serialize import join_rendered_events, render_event


class StoreError(RuntimeError):
    """Base error for store contract violations."""


class DispositionTransitionError(StoreError):
    """Raised when a disposition attempts a non-one-way transition."""


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
    canonical_key TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL,
    requested_mono_ns INTEGER NOT NULL CHECK (requested_mono_ns >= 0),
    result_event_id TEXT
) STRICT;

CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value BLOB NOT NULL
) STRICT;
"""


class Store:
    """One durable SQLite database for a single interaction session."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(self.path, isolation_level=None)
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
