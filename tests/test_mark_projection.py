"""Stateless mark identity projection across user snapshot revisions."""

from im.mark_projection import project_ambiguous_mark_targets, project_span
from im.schema.actions import Span
from im.schema.events import EVENT_ADAPTER, SnapshotEvent
from im.schema.textspan import utf16_len


def snapshot(event_id: str, seq: int, text: str) -> SnapshotEvent:
    event = EVENT_ADAPTER.validate_python(
        {
            "v": 1,
            "id": event_id,
            "seq": seq,
            "dt_ms": 0,
            "source": "user",
            "kind": "snapshot",
            "activity": "paused",
            "payload": {
                "text": text,
                "selection_start_utf16": utf16_len(text),
                "selection_end_utf16": utf16_len(text),
                "is_composing": False,
                "edit_kind": "insert",
            },
        }
    )
    assert isinstance(event, SnapshotEvent)
    return event


def test_target_survives_unchanged_snapshot_identity_rollover() -> None:
    first = snapshot("e_000001", 0, "cat")
    second = snapshot("e_000002", 1, "cat")
    target = Span(event_id=first.id, start_utf16=0, end_utf16=3, text="cat")

    assert project_span(target, (first, second)) == Span(
        event_id=second.id,
        start_utf16=0,
        end_utf16=3,
        text="cat",
    )


def test_target_offsets_follow_untouched_suffix_with_utf16_prefix() -> None:
    first = snapshot("e_000001", 0, "cat")
    second = snapshot("e_000002", 1, "😀 cat")
    target = Span(event_id=first.id, start_utf16=0, end_utf16=3, text="cat")

    assert project_span(target, (first, second)) == Span(
        event_id=second.id,
        start_utf16=3,
        end_utf16=6,
        text="cat",
    )


def test_occurrence_survives_multiple_full_snapshot_revisions() -> None:
    first = snapshot("e_000001", 0, "remind me")
    second = snapshot("e_000002", 1, "Draft: remind me")
    third = snapshot("e_000003", 2, "Draft: remind me please")
    source = Span(event_id=first.id, start_utf16=0, end_utf16=9, text="remind me")

    assert project_span(source, (first, second, third)) == Span(
        event_id=third.id,
        start_utf16=7,
        end_utf16=16,
        text="remind me",
    )


def test_inserted_indistinguishable_occurrence_is_not_assigned_old_identity() -> None:
    first = snapshot("e_000001", 0, "cat")
    duplicated = snapshot("e_000002", 1, "cat cat")
    target = Span(event_id=first.id, start_utf16=0, end_utf16=3, text="cat")

    assert project_span(target, (first, duplicated)) is None
    assert project_ambiguous_mark_targets(target, (first, duplicated)) == (
        Span(event_id=duplicated.id, start_utf16=0, end_utf16=3, text="cat"),
        Span(event_id=duplicated.id, start_utf16=4, end_utf16=7, text="cat"),
    )


def test_unique_unchanged_context_disambiguates_repeated_target_text() -> None:
    first = snapshot("e_000001", 0, "ab")
    prefixed = snapshot("e_000002", 1, "aab")
    target = Span(event_id=first.id, start_utf16=0, end_utf16=1, text="a")

    assert project_span(target, (first, prefixed)) == Span(
        event_id=prefixed.id,
        start_utf16=1,
        end_utf16=2,
        text="a",
    )


def test_target_touched_by_revision_is_dropped_as_ambiguous() -> None:
    first = snapshot("e_000001", 0, "cat")
    second = snapshot("e_000002", 1, "dog")
    target = Span(event_id=first.id, start_utf16=0, end_utf16=3, text="cat")

    assert project_span(target, (first, second)) is None


def test_absent_then_reappeared_text_does_not_preserve_old_identity() -> None:
    first = snapshot("e_000001", 0, "cat")
    absent = snapshot("e_000002", 1, "dog")
    reappeared = snapshot("e_000003", 2, "cat")
    target = Span(event_id=first.id, start_utf16=0, end_utf16=3, text="cat")

    assert project_ambiguous_mark_targets(target, (first, absent, reappeared)) == ()


def test_ambiguous_continuity_tracks_occurrence_not_equal_text_elsewhere() -> None:
    first = snapshot("e_000001", 0, "cat ... cat")
    second = snapshot("e_000002", 1, "dog ... cat")
    target = Span(event_id=first.id, start_utf16=0, end_utf16=3, text="cat")

    assert project_ambiguous_mark_targets(target, (first, second)) == ()


def test_disjoint_edits_preserve_only_the_original_equal_occurrence() -> None:
    first = snapshot("e_000001", 0, "A cat B dog C cat D")
    second = snapshot("e_000002", 1, "X cat B dog C cat Y")
    target = Span(event_id=first.id, start_utf16=2, end_utf16=5, text="cat")

    assert project_span(target, (first, second)) == Span(
        event_id=second.id,
        start_utf16=2,
        end_utf16=5,
        text="cat",
    )
    assert project_ambiguous_mark_targets(target, (first, second)) == ()
