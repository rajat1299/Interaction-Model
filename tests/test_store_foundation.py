"""SQLite schema, metadata, and durable identifier tests."""

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from im.store import IdKind, Store, StoreError

EXPECTED_TABLES = {
    "ingress",
    "policy",
    "audit",
    "dispositions",
    "timers",
    "tool_requests",
    "meta",
}


class CommitFailingConnection:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection
        self.rollback_called = False

    def execute(self, *args, **kwargs):
        return self.connection.execute(*args, **kwargs)

    def commit(self) -> None:
        raise sqlite3.OperationalError("forced commit failure")

    def rollback(self) -> None:
        self.rollback_called = True
        self.connection.rollback()

    def close(self) -> None:
        self.connection.close()


def table_columns(connection: sqlite3.Connection, table: str) -> list[str]:
    return [row[1] for row in connection.execute(f"PRAGMA table_info({table})")]


def test_store_creates_wal_database_and_all_owned_tables(tmp_path: Path) -> None:
    path = tmp_path / "session.sqlite3"

    with Store(path):
        pass

    connection = sqlite3.connect(path)
    tables = {
        row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }
    assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    assert EXPECTED_TABLES <= tables
    strict_tables = {
        row[1]
        for row in connection.execute("PRAGMA table_list")
        if row[1] in EXPECTED_TABLES and row[5]
    }
    assert strict_tables == EXPECTED_TABLES
    assert table_columns(connection, "policy") == [
        "seq",
        "segment_index",
        "event_id",
        "dt_ms",
        "occurred_mono_ns",
        "rendered",
    ]
    connection.close()


def test_allocate_id_uses_closed_prefixes_and_durable_counters(tmp_path: Path) -> None:
    path = tmp_path / "session.sqlite3"
    with Store(path) as store:
        assert store.allocate_id(IdKind.EVENT) == "e_000001"
        assert store.allocate_id("event") == "e_000002"
        assert store.allocate_id("timer") == "t_001"
        assert store.allocate_id("request") == "r_001"
        assert store.allocate_id("instruction") == "i_001"

    with Store(path) as reopened:
        assert reopened.allocate_id("event") == "e_000003"
        assert reopened.allocate_id("timer") == "t_002"


def test_allocate_id_rejects_unknown_kind_without_consuming_counter(tmp_path: Path) -> None:
    with Store(tmp_path / "session.sqlite3") as store:
        with pytest.raises(ValueError, match="unknown id kind"):
            store.allocate_id("tool")
        assert store.allocate_id("event") == "e_000001"


def test_independent_connections_allocate_unique_contiguous_ids(tmp_path: Path) -> None:
    path = tmp_path / "session.sqlite3"
    with Store(path):
        pass

    def allocate_one(_index: int) -> str:
        with Store(path) as store:
            return store.allocate_id("event")

    with ThreadPoolExecutor(max_workers=4) as executor:
        allocated = list(executor.map(allocate_one, range(20)))

    assert sorted(allocated) == [f"e_{value:06d}" for value in range(1, 21)]


def test_corrupted_counter_rolls_back_and_can_be_repaired(tmp_path: Path) -> None:
    with Store(tmp_path / "session.sqlite3") as store:
        store.set_meta("id_counter:event", True)
        with pytest.raises(StoreError, match="counter"):
            store.allocate_id("event")
        store.set_meta("id_counter:event", 4)
        assert store.allocate_id("event") == "e_000005"


def test_meta_round_trips_tim_json_values_across_reopen(tmp_path: Path) -> None:
    path = tmp_path / "session.sqlite3"
    value = {"segment": 2, "ids": ["e_000001", None], "active": True}

    with Store(path) as store:
        assert store.get_meta("state") is None
        store.set_meta("state", value)
        assert store.get_meta("state") == value

    with Store(path) as reopened:
        assert reopened.get_meta("state") == value


def test_meta_rejects_empty_key_and_non_tim_json_value(tmp_path: Path) -> None:
    with Store(tmp_path / "session.sqlite3") as store:
        with pytest.raises(ValueError, match="key"):
            store.set_meta("", 1)
        with pytest.raises(ValueError, match="floating-point"):
            store.set_meta("bad", 1.5)


def test_store_creates_parent_directory(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "session.sqlite3"

    with Store(path):
        assert path.exists()


def test_commit_failure_rolls_back_and_does_not_poison_connection(tmp_path: Path) -> None:
    store = Store(tmp_path / "session.sqlite3")
    original = store._connection
    failing = CommitFailingConnection(original)
    store._connection = failing

    with pytest.raises(sqlite3.OperationalError, match="forced commit"):
        store.set_meta("state", 1)
    assert failing.rollback_called

    store._connection = original
    assert store.get_meta("state") is None
    store.set_meta("state", 2)
    assert store.get_meta("state") == 2
    store.close()
