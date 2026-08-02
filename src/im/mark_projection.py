"""Deterministic occurrence projection through full-snapshot revisions."""

from collections.abc import Iterable
from difflib import SequenceMatcher

from im.schema.actions import Span
from im.schema.events import SnapshotEvent
from im.schema.textspan import py_index, utf16_len, utf16_slice

type RevisionOpcode = tuple[str, int, int, int, int]


def _revision_opcodes(previous: str, current: str) -> tuple[RevisionOpcode, ...]:
    """Return deterministic disjoint edit alignment with repeated-text heuristics disabled."""
    return tuple(SequenceMatcher(None, previous, current, autojunk=False).get_opcodes())


def _project_python_range(
    previous: str,
    current: str,
    start: int,
    end: int,
) -> tuple[int, int] | None:
    block = _equal_block_for_range(previous, current, start, end)
    if block is not None:
        previous_start, _previous_end, current_start, _current_end = block
        return current_start + start - previous_start, current_start + end - previous_start
    return None


def _equal_block_for_range(
    previous: str,
    current: str,
    start: int,
    end: int,
) -> tuple[int, int, int, int] | None:
    for tag, previous_start, previous_end, current_start, current_end in _revision_opcodes(
        previous, current
    ):
        if tag == "equal" and start >= previous_start and end <= previous_end:
            return previous_start, previous_end, current_start, current_end
    return None


def _occurrences(text: str, fragment: str) -> tuple[int, ...]:
    matches: list[int] = []
    start = 0
    while True:
        index = text.find(fragment, start)
        if index < 0:
            return tuple(matches)
        matches.append(index)
        start = index + 1


def _project_unique_python_range(
    previous: str,
    current: str,
    start: int,
    end: int,
) -> tuple[int, int] | None:
    """Map only through an unchanged context block unique on both sides.

    SequenceMatcher supplies a deterministic alignment, but repeated equal blocks can admit another
    equally plausible occurrence identity. Requiring the containing maximal equal block to occur
    exactly once in each snapshot turns the alignment into a conservative identity proof.
    """
    block = _equal_block_for_range(previous, current, start, end)
    if block is None:
        return None
    previous_start, previous_end, current_start, _current_end = block
    context = previous[previous_start:previous_end]
    if len(_occurrences(previous, context)) != 1 or len(_occurrences(current, context)) != 1:
        return None
    return current_start + start - previous_start, current_start + end - previous_start


def project_span(
    source_span: Span,
    snapshots: Iterable[SnapshotEvent],
) -> Span | None:
    """Carry one source occurrence only through regions unchanged by every revision.

    Prefix/suffix preservation is deliberately conservative. A target touched by a revision's
    changed middle has ambiguous identity and is dropped instead of being guessed from matching
    text elsewhere.
    """
    ordered = tuple(snapshots)
    source_index = next(
        (index for index, snapshot in enumerate(ordered) if snapshot.id == source_span.event_id),
        None,
    )
    if source_index is None:
        return None

    source = ordered[source_index]
    try:
        if utf16_slice(
            source.payload.text,
            source_span.start_utf16,
            source_span.end_utf16,
        ) != source_span.text:
            return None
        start = py_index(source.payload.text, source_span.start_utf16)
        end = py_index(source.payload.text, source_span.end_utf16)
    except (TypeError, ValueError):
        return None

    previous_text = source.payload.text
    latest_event_id = source.id
    for snapshot in ordered[source_index + 1 :]:
        projected = _project_unique_python_range(
            previous_text,
            snapshot.payload.text,
            start,
            end,
        )
        if projected is None:
            return None
        start, end = projected
        previous_text = snapshot.payload.text
        latest_event_id = snapshot.id

    if previous_text[start:end] != source_span.text:
        return None
    return Span(
        event_id=latest_event_id,
        start_utf16=utf16_len(previous_text[:start]),
        end_utf16=utf16_len(previous_text[:end]),
        text=source_span.text,
    )


def _matching_occurrences(
    text: str,
    needle: str,
    candidate_start: int,
    candidate_end: int,
) -> tuple[tuple[int, int], ...]:
    """Return equal-text occurrences local to one candidate's aligned edit interval."""
    matches: list[tuple[int, int]] = []
    start = 0
    while True:
        index = text.find(needle, start)
        if index < 0:
            break
        end = index + len(needle)
        overlaps_candidate = (
            index < candidate_end and end > candidate_start
            if candidate_start < candidate_end
            else index < candidate_start < end
        )
        if overlaps_candidate:
            matches.append((index, end))
        start = index + 1
    return tuple(matches)


def project_ambiguous_mark_targets(
    target: Span,
    snapshots: Iterable[SnapshotEvent],
) -> tuple[Span, ...]:
    """Map only the occurrence set that can descend from a touched marked target.

    Unchanged prefix/suffix regions preserve exact occurrence identity. When a revision touches a
    candidate, only equal-text occurrences overlapping that revision's changed window remain
    candidates. Equal text elsewhere is never admitted, and an empty candidate set is terminal.
    """
    ordered = tuple(snapshots)
    source_index = next(
        (index for index, snapshot in enumerate(ordered) if snapshot.id == target.event_id),
        None,
    )
    if source_index is None:
        return ()

    source = ordered[source_index]
    try:
        if utf16_slice(
            source.payload.text,
            target.start_utf16,
            target.end_utf16,
        ) != target.text:
            return ()
        candidates = {
            (
                py_index(source.payload.text, target.start_utf16),
                py_index(source.payload.text, target.end_utf16),
            )
        }
    except (TypeError, ValueError):
        return ()

    previous_text = source.payload.text
    touched = False
    latest_event_id = source.id
    for snapshot in ordered[source_index + 1 :]:
        current_text = snapshot.payload.text
        opcodes = _revision_opcodes(previous_text, current_text)
        mapped: set[tuple[int, int]] = set()
        for start, end in candidates:
            exact = _project_unique_python_range(previous_text, current_text, start, end)
            if exact is not None:
                mapped.add(exact)
                continue
            touched = True
            repeated_block = _equal_block_for_range(previous_text, current_text, start, end)
            if repeated_block is not None:
                previous_start, previous_end, _current_start, _current_end = repeated_block
                context = previous_text[previous_start:previous_end]
                relative_start = start - previous_start
                relative_end = end - previous_start
                for context_start in _occurrences(current_text, context):
                    candidate = (
                        context_start + relative_start,
                        context_start + relative_end,
                    )
                    if current_text[candidate[0] : candidate[1]] == target.text:
                        mapped.add(candidate)
                continue
            affected = [
                (current_start, current_end)
                for _tag, previous_start, previous_end, current_start, current_end in opcodes
                if (
                    max(start, previous_start) < min(end, previous_end)
                    or (previous_start == previous_end and start < previous_start < end)
                )
            ]
            if not affected:
                continue
            candidate_start = min(item[0] for item in affected)
            candidate_end = max(item[1] for item in affected)
            replacements = _matching_occurrences(
                current_text,
                target.text,
                candidate_start,
                candidate_end,
            )
            # A coarse replacement containing multiple equal strings cannot identify which one
            # descends from this occurrence. Dropping is safer than suppressing unrelated marks.
            if len(replacements) == 1:
                mapped.add(replacements[0])
        if not mapped:
            return ()
        candidates = mapped
        previous_text = current_text
        latest_event_id = snapshot.id

    if not touched:
        return ()
    return tuple(
        Span(
            event_id=latest_event_id,
            start_utf16=utf16_len(previous_text[:start]),
            end_utf16=utf16_len(previous_text[:end]),
            text=target.text,
        )
        for start, end in sorted(candidates)
        if previous_text[start:end] == target.text
    )
