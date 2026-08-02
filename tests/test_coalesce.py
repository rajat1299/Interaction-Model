"""Typed pending-buffer and edit-kind tests."""

from collections import Counter

import pytest
from hypothesis import given
from hypothesis import strategies as st

from im.coalesce import SnapshotState, coalesce, derive_edit_kind
from im.schema.common import EditKind
from im.schema.events import TimerFirePayload
from im.schema.textspan import utf16_len
from im.store import PolicyEventDraft


def draft(
    index: int,
    source: str,
    kind: str,
    payload: object,
    *,
    activity: str | None = None,
) -> PolicyEventDraft:
    return PolicyEventDraft(
        id=f"e_{index + 1:06d}",
        source=source,
        kind=kind,
        payload=payload,
        occurred_mono_ns=(index + 1) * 1_000_000,
        activity=activity,
    )


def snapshot(index: int, text: str) -> PolicyEventDraft:
    return draft(
        index,
        "user",
        "snapshot",
        {
            "text": text,
            "selection_start_utf16": len(text),
            "selection_end_utf16": len(text),
            "is_composing": False,
            "edit_kind": "insert",
        },
        activity="active",
    )


def fire(index: int, timer_id: str, fire_count: int, missed_count: int) -> PolicyEventDraft:
    return draft(
        index,
        "timer",
        "fire",
        {
            "timer_id": timer_id,
            "fire_count": fire_count,
            "late_ms": index,
            "missed_count": missed_count,
        },
    )


def apply(events: list[PolicyEventDraft]) -> list[PolicyEventDraft]:
    pending: list[PolicyEventDraft] = []
    for event in events:
        pending = coalesce(pending, event)
    return pending


def test_snapshot_replacement_uses_latest_arrival_position() -> None:
    result = apply(
        [
            snapshot(0, "old"),
            draft(
                1,
                "tool",
                "result",
                {"request_id": "r_001", "status": "succeeded", "data": {"opaque": True}},
            ),
            snapshot(2, "new"),
        ]
    )

    assert [event.id for event in result] == ["e_000002", "e_000003"]


def test_same_timer_fire_merge_preserves_cardinality_and_latest_identity() -> None:
    result = apply(
        [
            fire(0, "t_001", 3, 2),
            draft(1, "runtime", "cancel_ack", {"timer_ids": ["t_002"]}),
            fire(2, "t_001", 5, 1),
        ]
    )

    assert [event.id for event in result] == ["e_000002", "e_000003"]
    payload = TimerFirePayload.model_validate(result[-1].payload)
    assert payload == TimerFirePayload(
        timer_id="t_001",
        fire_count=5,
        late_ms=2,
        missed_count=4,
    )


def test_fires_never_merge_across_timers() -> None:
    result = apply([fire(0, "t_001", 1, 0), fire(1, "t_002", 1, 0)])

    assert [event.id for event in result] == ["e_000001", "e_000002"]


def test_invalid_incoming_event_cannot_evict_valid_pending_state() -> None:
    valid = snapshot(0, "valid")
    pending = [valid]
    invalid = draft(1, "user", "snapshot", {"text": 123}, activity="active")

    with pytest.raises(ValueError):
        coalesce(pending, invalid)

    assert pending == [valid]


@pytest.mark.gate
@given(
    st.lists(
        st.sampled_from(["snapshot", "fire-1", "fire-2", "result", "ack"]),
        max_size=100,
    )
)
def test_never_drops_property(kinds: list[str]) -> None:
    events: list[PolicyEventDraft] = []
    for index, kind in enumerate(kinds):
        if kind == "snapshot":
            events.append(snapshot(index, str(index)))
        elif kind == "fire-1":
            events.append(fire(index, "t_001", index + 1, index % 3))
        elif kind == "fire-2":
            events.append(fire(index, "t_002", index + 1, index % 2))
        elif kind == "result":
            events.append(
                draft(
                    index,
                    "tool",
                    "result",
                    {
                        "request_id": f"r_{index + 1:03d}",
                        "status": "succeeded",
                        "data": {"value": index},
                    },
                )
            )
        else:
            events.append(
                draft(
                    index,
                    "runtime",
                    "cancel_ack",
                    {"timer_ids": [f"t_{index + 1:03d}"]},
                )
            )

    result = apply(events)
    latest_snapshot_id = next(
        (event.id for event in reversed(events) if event.kind == "snapshot"), None
    )
    latest_fire_ids: dict[str, str] = {}
    for event in events:
        if event.source == "timer" and event.kind == "fire":
            latest_fire_ids[TimerFirePayload.model_validate(event.payload).timer_id] = event.id
    expected_ids: list[str] = []
    for event in events:
        if event.kind == "snapshot":
            if event.id == latest_snapshot_id:
                expected_ids.append(event.id)
        elif event.source == "timer" and event.kind == "fire":
            timer_id = TimerFirePayload.model_validate(event.payload).timer_id
            if event.id == latest_fire_ids[timer_id]:
                expected_ids.append(event.id)
        else:
            expected_ids.append(event.id)
    assert [event.id for event in result] == expected_ids

    input_fire_periods: Counter[str] = Counter()
    output_fire_periods: Counter[str] = Counter()
    latest_fire_payloads: dict[str, TimerFirePayload] = {}
    for event in events:
        payload = TimerFirePayload.model_validate(event.payload) if event.kind == "fire" else None
        if payload is not None:
            input_fire_periods[payload.timer_id] += payload.missed_count + 1
            latest_fire_payloads[payload.timer_id] = payload
    for event in result:
        payload = TimerFirePayload.model_validate(event.payload) if event.kind == "fire" else None
        if payload is not None:
            output_fire_periods[payload.timer_id] += payload.missed_count + 1
    assert output_fire_periods == input_fire_periods
    output_fires = [
        TimerFirePayload.model_validate(event.payload)
        for event in result
        if event.source == "timer" and event.kind == "fire"
    ]
    assert len(output_fires) == len(latest_fire_payloads)
    for payload in output_fires:
        latest = latest_fire_payloads[payload.timer_id]
        assert (payload.fire_count, payload.late_ms) == (latest.fire_count, latest.late_ms)

    snapshots = [event for event in events if event.kind == "snapshot"]
    output_snapshots = [event for event in result if event.kind == "snapshot"]
    assert output_snapshots == ([] if not snapshots else [snapshots[-1]])


@pytest.mark.parametrize(
    ("before", "after", "hint", "expected"),
    [
        ("cat", "cats", "insertText", EditKind.INSERT),
        ("cats", "cat", "deleteContentBackward", EditKind.DELETE),
        ("cat", "cut", "insertReplacementText", EditKind.REPLACE),
        ("cat", "cat fact", "insertFromPaste", EditKind.PASTE),
        ("cat", "cut", "insertFromPaste", EditKind.REPLACE),
        ("cat", "cats", "deleteContentBackward", EditKind.INSERT),
        ("cat", "cat", "insertText", EditKind.NONE),
    ],
)
def test_edit_kind_text_diff_and_hint_precedence(
    before: str,
    after: str,
    hint: str,
    expected: EditKind,
) -> None:
    previous = SnapshotState(before, len(before), len(before), False)
    current = SnapshotState(after, len(after), len(after), False)

    assert derive_edit_kind(previous, current, hint) is expected


def test_pure_cursor_move() -> None:
    previous = SnapshotState("cats", 4, 4, False)
    current = SnapshotState("cats", 1, 1, False)

    assert derive_edit_kind(previous, current, None) is EditKind.CURSOR_MOVE


def test_ime_composition_sequence() -> None:
    empty = SnapshotState("", 0, 0, False)
    composing = SnapshotState("あ", 1, 1, True)
    committed = SnapshotState("あ", 1, 1, False)

    assert derive_edit_kind(empty, composing, "insertCompositionText") is EditKind.INSERT
    assert derive_edit_kind(composing, committed, None) is EditKind.NONE


def test_utf16_astral_combining_and_ime_replacement() -> None:
    text = "😀é"
    emoji = SnapshotState(text, utf16_len(text), utf16_len(text), False)
    moved = SnapshotState(text, 2, 2, False)
    before_ime = SnapshotState("a", 1, 1, False)
    composing = SnapshotState("😀", 2, 2, True)
    committed = SnapshotState("😀", 2, 2, False)

    assert derive_edit_kind(emoji, moved, None) is EditKind.CURSOR_MOVE
    assert derive_edit_kind(before_ime, composing, "insertCompositionText") is EditKind.REPLACE
    assert derive_edit_kind(composing, committed, None) is EditKind.NONE


def test_initial_and_identical_snapshots() -> None:
    empty = SnapshotState("", 0, 0, False)
    text = SnapshotState("hello", 5, 5, False)

    assert derive_edit_kind(None, empty, None) is EditKind.NONE
    assert derive_edit_kind(None, text, "insertFromPaste") is EditKind.PASTE
    assert derive_edit_kind(text, text, None) is EditKind.NONE
