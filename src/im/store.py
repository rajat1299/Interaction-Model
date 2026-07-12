"""Durable SQLite lanes, runtime state, and per-session identifiers."""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from enum import StrEnum
from pathlib import Path

from im.canonical_json import TimJsonValue, canonicalize_tim_json, parse_tim_json


class StoreError(RuntimeError):
    """Base error for store contract violations."""


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

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> "Store":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    @contextmanager
    def _transaction(self) -> Iterator[None]:
        self._connection.execute("BEGIN IMMEDIATE")
        try:
            yield
            self._connection.commit()
        except BaseException:
            try:
                self._connection.rollback()
            except sqlite3.Error:
                pass
            raise

    def get_meta(self, key: str) -> TimJsonValue | None:
        row = self._connection.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return None if row is None else parse_tim_json(bytes(row[0]))

    def set_meta(self, key: str, value: object) -> None:
        if not key:
            raise ValueError("meta key must not be empty")
        encoded = canonicalize_tim_json(value)
        with self._transaction():
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
        with self._transaction():
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
