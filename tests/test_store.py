"""Three-lane policy, ingress, audit, and disposition store tests."""

import sqlite3
from pathlib import Path

import pytest
from pydantic import ValidationError

from im.schema.common import Disposition
from im.serialize import parse_event
from im.store import (
    DispositionTransitionError,
    PolicyEventDraft,
    Store,
    StoreError,
)


def annotation_draft(
    event_id: str,
    occurred_mono_ns: int,
    text: str,
) -> PolicyEventDraft:
    return PolicyEventDraft(
        id=event_id,
        source="user",
        kind="annotation",
        payload={"text": text},
        occurred_mono_ns=occurred_mono_ns,
    )


def test_ingress_preserves_exact_bytes_and_operational_timestamps(tmp_path: Path) -> None:
    path = tmp_path / "session.sqlite3"
    raw = b'{ "text" : "exact spacing" }\r\n'

    with Store(path) as store:
        event_id = store.allocate_id("event")
        store.append_ingress(
            event_id=event_id,
            received_utc="2026-07-12T12:00:00Z",
            received_mono_ns=123_456_789,
            source="user",
            kind="snapshot",
            payload=raw,
        )

    connection = sqlite3.connect(path)
    row = connection.execute(
        "SELECT received_utc, received_mono_ns, source, kind, payload FROM ingress"
    ).fetchone()
    connection.close()
    assert row == ("2026-07-12T12:00:00Z", 123_456_789, "user", "snapshot", raw)


def test_policy_commit_assigns_dense_seq_and_occurrence_time_delta(tmp_path: Path) -> None:
    with Store(tmp_path / "session.sqlite3") as store:
        first = annotation_draft(store.allocate_id("event"), 1_000_000_000, "first")
        second = annotation_draft(store.allocate_id("event"), 1_001_999_999, "second")

        first_seq, first_bytes = store.commit_policy(first)
        second_seq, second_bytes = store.commit_policy(second)

        assert (first_seq, second_seq) == (0, 1)
        assert parse_event(first_bytes).dt_ms == 0
        assert parse_event(second_bytes).dt_ms == 1
        assert store.policy_bytes(0) == first_bytes + b"\n" + second_bytes
        assert b"occurred_mono_ns" not in store.policy_bytes(0)


def test_decreasing_occurrence_time_rolls_back_without_sequence_gap(tmp_path: Path) -> None:
    with Store(tmp_path / "session.sqlite3") as store:
        store.commit_policy(annotation_draft(store.allocate_id("event"), 2_000_000, "first"))

        with pytest.raises(StoreError, match="decreased"):
            store.commit_policy(
                annotation_draft(store.allocate_id("event"), 1_999_999, "backwards")
            )

        seq, rendered = store.commit_policy(
            annotation_draft(store.allocate_id("event"), 3_000_000, "next")
        )
        assert seq == 1
        assert parse_event(rendered).dt_ms == 1


def test_segment_boundary_resets_dt_and_policy_bytes_defaults_current(tmp_path: Path) -> None:
    with Store(tmp_path / "session.sqlite3") as store:
        _, segment_zero = store.commit_policy(
            annotation_draft(store.allocate_id("event"), 9_000_000, "zero")
        )
        seq, segment_one = store.commit_new_segment(
            annotation_draft(store.allocate_id("event"), 10_000_000, "one")
        )

        assert seq == 1
        assert parse_event(segment_one).dt_ms == 0
        assert store.policy_bytes() == segment_one
        assert store.policy_bytes(0) == segment_zero
        assert store.policy_bytes(1) == segment_one


def test_transaction_rolls_back_every_enlisted_mutation(tmp_path: Path) -> None:
    path = tmp_path / "session.sqlite3"
    with Store(path) as store:
        with pytest.raises(RuntimeError, match="forced failure"):
            with store.transaction():
                event_id = store.allocate_id("event")
                store.append_ingress(
                    event_id=event_id,
                    received_utc="2026-07-12T12:00:00Z",
                    received_mono_ns=1_000_000,
                    source="user",
                    kind="annotation",
                    payload=b'{"text":"first"}',
                )
                store.commit_policy(annotation_draft(event_id, 1_000_000, "first"))
                store.set_disposition(event_id, "open")
                store.audit("attempt", {"event_id": event_id}, ts_utc="2026-07-12T12:00:00Z")
                raise RuntimeError("forced failure")

        assert store.allocate_id("event") == "e_000001"
        assert store.policy_bytes() == b""
        assert store.get_disposition("e_000001") is None

    connection = sqlite3.connect(path)
    counts = {
        table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in ("ingress", "policy", "audit", "dispositions")
    }
    connection.close()
    assert counts == {"ingress": 0, "policy": 0, "audit": 0, "dispositions": 0}


def test_failed_new_segment_commit_rolls_back_pointer_and_event(tmp_path: Path) -> None:
    with Store(tmp_path / "session.sqlite3") as store:
        _, segment_zero = store.commit_policy(
            annotation_draft(store.allocate_id("event"), 1_000_000, "zero")
        )
        invalid = PolicyEventDraft(
            id=store.allocate_id("event"),
            source="runtime",
            kind="annotation",
            payload={"text": "invalid source-kind pair"},
            occurred_mono_ns=2_000_000,
        )

        with pytest.raises(ValidationError):
            store.commit_new_segment(invalid)

        assert store.get_meta("current_segment_index") is None
        assert store.policy_bytes() == segment_zero
        assert store.policy_bytes(1) == b""


def test_current_segment_meta_is_reserved(tmp_path: Path) -> None:
    with Store(tmp_path / "session.sqlite3") as store:
        with pytest.raises(ValueError, match="reserved"):
            store.set_meta("current_segment_index", 1)


def test_occurrence_time_cannot_decrease_across_segment_boundary(tmp_path: Path) -> None:
    with Store(tmp_path / "session.sqlite3") as store:
        store.commit_policy(annotation_draft(store.allocate_id("event"), 9_000_000, "zero"))

        with pytest.raises(StoreError, match="decreased"):
            store.commit_new_segment(
                annotation_draft(store.allocate_id("event"), 8_999_999, "regression")
            )

        assert store.get_meta("current_segment_index") is None
        seq, rendered = store.commit_new_segment(
            annotation_draft(store.allocate_id("event"), 9_000_000, "one")
        )
        assert seq == 1
        assert parse_event(rendered).dt_ms == 0


def test_policy_bytes_survive_close_and_reopen_per_segment(tmp_path: Path) -> None:
    path = tmp_path / "session.sqlite3"
    with Store(path) as store:
        _, first = store.commit_policy(
            annotation_draft(store.allocate_id("event"), 1_000_000, "first")
        )
        _, second = store.commit_policy(
            annotation_draft(store.allocate_id("event"), 2_000_000, "second")
        )
        expected = first + b"\n" + second

    with Store(path) as reopened:
        assert reopened.policy_bytes() == expected


def test_invalid_draft_rolls_back_policy_insert(tmp_path: Path) -> None:
    with Store(tmp_path / "session.sqlite3") as store:
        invalid = PolicyEventDraft(
            id=store.allocate_id("event"),
            source="runtime",
            kind="annotation",
            payload={"text": "wrong source"},
            occurred_mono_ns=1,
        )
        with pytest.raises(ValidationError):
            store.commit_policy(invalid)
        seq, _ = store.commit_policy(annotation_draft(store.allocate_id("event"), 2, "valid"))
        assert seq == 0


def test_audit_stores_canonical_payload_and_deterministic_timestamp(tmp_path: Path) -> None:
    path = tmp_path / "session.sqlite3"
    with Store(path) as store:
        row_id = store.audit(
            "action_attempt",
            {"z": 1, "a": [True, None]},
            ts_utc="2026-07-12T12:00:00Z",
        )
        assert row_id == 1

    connection = sqlite3.connect(path)
    row = connection.execute("SELECT ts_utc, kind, payload FROM audit").fetchone()
    connection.close()
    assert row == (
        "2026-07-12T12:00:00Z",
        "action_attempt",
        b'{"a":[true,null],"z":1}',
    )


@pytest.mark.parametrize("terminal", ["handled", "skipped", "superseded"])
def test_disposition_allows_only_open_to_terminal(tmp_path: Path, terminal: str) -> None:
    with Store(tmp_path / f"{terminal}.sqlite3") as store:
        assert store.get_disposition("e_000001") is None
        opened = store.set_disposition("e_000001", "open")
        assert opened.state is Disposition.OPEN
        completed = store.set_disposition("e_000001", terminal, by_action_event_id="e_000002")
        assert completed.state is Disposition(terminal)
        assert store.get_disposition("e_000001") == completed

        with pytest.raises(DispositionTransitionError):
            store.set_disposition("e_000001", "handled")


@pytest.mark.parametrize(
    ("initial", "target"),
    [(None, "handled"), (None, "skipped"), ("open", "open")],
)
def test_disposition_rejects_non_one_way_transitions(
    tmp_path: Path,
    initial: str | None,
    target: str,
) -> None:
    with Store(tmp_path / f"{initial}-{target}.sqlite3") as store:
        if initial is not None:
            store.set_disposition("e_000001", initial)
        with pytest.raises(DispositionTransitionError):
            store.set_disposition("e_000001", target)


def test_policy_api_exports_no_update_or_delete_methods() -> None:
    forbidden = {"update_policy", "delete_policy", "replace_policy"}

    assert forbidden.isdisjoint(dir(Store))
