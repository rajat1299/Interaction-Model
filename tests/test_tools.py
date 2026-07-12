"""Deterministic fake-tool adapter and request-ledger tests."""

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from im.schema.common import ToolResultStatus
from im.serialize import parse_event
from im.store import Store, ToolRequestStatus
from im.tools import (
    ScriptedToolResult,
    ToolAdapter,
    ToolValidationError,
    canonical_tool_key,
)


class FakeClock:
    def __init__(self, mono_ns: int = 0) -> None:
        self._mono_ns = mono_ns
        self._wall_start = datetime(2026, 7, 12, 12, 0, tzinfo=UTC)

    def monotonic_ns(self) -> int:
        return self._mono_ns

    def wall_utc(self) -> datetime:
        return self._wall_start + timedelta(microseconds=self._mono_ns // 1_000)

    async def sleep_until(self, mono_ns: int) -> None:
        self._mono_ns = mono_ns

    def advance_ms(self, delta_ms: int) -> None:
        self._mono_ns += delta_ms * 1_000_000


def test_closed_lookup_registry_and_canonical_key() -> None:
    key = canonical_tool_key("lookup", {"query": "  planet  "})

    assert key == canonical_tool_key("lookup", {"query": "planet"})
    assert key != canonical_tool_key("lookup", {"query": "planet facts"})
    assert key.startswith("sha256:")

    with pytest.raises(ToolValidationError, match="unknown tool"):
        canonical_tool_key("search", {"query": "planet"})
    with pytest.raises(ToolValidationError, match="invalid lookup args"):
        canonical_tool_key("lookup", {"query": "planet", "limit": 1})


def test_scripted_result_is_delivered_at_due_time_with_verbatim_canonical_data(
    tmp_path: Path,
) -> None:
    clock = FakeClock(mono_ns=5_000_000_000)
    with Store(tmp_path / "session.sqlite3") as store:
        adapter = ToolAdapter(store, clock)
        request_id = adapter.request(
            "lookup",
            {"query": "nonce-42"},
            fact_event_id="e_000010",
            scripted_result=ScriptedToolResult(
                latency_ms=25,
                status="succeeded",
                data={"z": [True, None], "a": {"β": "value"}},
            ),
        )
        request = store.get_tool_request(request_id)
        assert request is not None
        assert request.status is ToolRequestStatus.PENDING
        assert request.due_mono_ns == 5_025_000_000
        assert adapter.pending == frozenset({request.canonical_key})

        clock.advance_ms(24)
        assert adapter.deliver_due() == ()

        clock.advance_ms(1)
        (delivery,) = adapter.deliver_due()

        assert delivery.request_id == request_id
        assert delivery.ingress_payload == (
            b'{"data":{"a":{"\xce\xb2":"value"},"z":[true,null]},'
            b'"request_id":"r_001","status":"succeeded"}'
        )
        assert delivery.payload == {
            "data": {"a": {"β": "value"}, "z": [True, None]},
            "request_id": request_id,
            "status": "succeeded",
        }
        assert adapter.pending == frozenset()

        completed = store.get_tool_request(request_id)
        assert completed is not None
        assert completed.status is ToolRequestStatus.COMPLETED
        assert completed.result_event_id == delivery.event_id
        assert completed.result_status is ToolResultStatus.SUCCEEDED

        ingress = store._connection.execute(
            "SELECT id, received_mono_ns, source, kind, payload FROM ingress"
        ).fetchone()
        assert ingress == (
            delivery.event_id,
            5_025_000_000,
            "tool",
            "result",
            delivery.ingress_payload,
        )

        _, rendered = store.commit_policy(delivery.as_policy_draft())
        event = parse_event(rendered)
        assert event.payload.data == {"a": {"β": "value"}, "z": [True, None]}


def test_dedup_is_pending_only_and_fresh_schema_uses_partial_unique_index(tmp_path: Path) -> None:
    path = tmp_path / "session.sqlite3"
    clock = FakeClock()
    with Store(path) as store:
        adapter = ToolAdapter(store, clock)
        first = adapter.request(
            "lookup",
            {"query": "same"},
            scripted_result=ScriptedToolResult(latency_ms=1, data={"answer": 1}),
        )
        duplicate = adapter.request(
            "lookup",
            {"query": "  same  "},
            scripted_result=ScriptedToolResult(latency_ms=50, data={"answer": 2}),
        )
        assert (first, duplicate) == ("r_001", "r_001")
        assert len(store.pending_tool_requests()) == 1

        clock.advance_ms(1)
        adapter.deliver_due()
        second = adapter.request(
            "lookup",
            {"query": "same"},
            scripted_result=ScriptedToolResult(latency_ms=10, data={"answer": 3}),
        )
        assert second == "r_002"
        assert store.get_tool_request(first).status is ToolRequestStatus.COMPLETED  # type: ignore[union-attr]
        assert store.get_tool_request(second).status is ToolRequestStatus.PENDING  # type: ignore[union-attr]

    connection = sqlite3.connect(path)
    index_sql = connection.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'index' AND name = ?",
        ("tool_requests_pending_canonical_key",),
    ).fetchone()[0]
    table_sql = connection.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'tool_requests'"
    ).fetchone()[0]
    connection.close()
    assert "WHERE status = 'pending'" in index_sql
    assert "canonical_key TEXT NOT NULL UNIQUE" not in table_sql


def test_due_delivery_rolls_back_event_id_ingress_and_ledger_on_insert_failure(
    tmp_path: Path,
) -> None:
    clock = FakeClock()
    with Store(tmp_path / "session.sqlite3") as store:
        adapter = ToolAdapter(store, clock)
        request_id = adapter.request(
            "lookup",
            {"query": "atomic"},
            scripted_result=ScriptedToolResult(latency_ms=0, data={"nonce": "n-1"}),
        )
        # The adapter will allocate e_000001.  Occupying it forces the ingress
        # insert to fail after entry to the adapter's outer transaction.
        store.append_ingress(
            event_id="e_000001",
            received_utc="2026-07-12T12:00:00+00:00",
            received_mono_ns=0,
            source="user",
            kind="annotation",
            payload=b'{"text":"already here"}',
        )

        with pytest.raises(sqlite3.IntegrityError):
            adapter.deliver_due()

        request = store.get_tool_request(request_id)
        assert request is not None
        assert request.status is ToolRequestStatus.PENDING
        assert request.result_event_id is None
        assert store._connection.execute("SELECT COUNT(*) FROM ingress").fetchone()[0] == 1
        # Allocation happened in the aborted transaction, so its durable counter
        # rolls back along with the ledger and ingress mutation.
        assert store.allocate_id("event") == "e_000001"
