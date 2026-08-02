"""Pure typed pending-buffer coalescing and edit-kind derivation."""

from dataclasses import dataclass, replace
from typing import Protocol

from im.schema.common import EditKind
from im.schema.events import EVENT_ADAPTER, TimerFirePayload
from im.schema.textspan import utf16_len
from im.store import PolicyEventDraft

type PendingEvent = PolicyEventDraft


class SnapshotLike(Protocol):
    """The snapshot fields needed to classify an edit."""

    text: str
    selection_start_utf16: int
    selection_end_utf16: int
    is_composing: bool


@dataclass(frozen=True, slots=True)
class SnapshotState:
    """Pre-schema snapshot state used while deriving ``edit_kind``."""

    text: str
    selection_start_utf16: int
    selection_end_utf16: int
    is_composing: bool

    def __post_init__(self) -> None:
        length = utf16_len(self.text)
        if self.selection_start_utf16 < 0 or self.selection_end_utf16 < 0:
            raise ValueError("snapshot selection must be non-negative")
        if self.selection_start_utf16 > self.selection_end_utf16:
            raise ValueError("snapshot selection start must not follow end")
        if self.selection_end_utf16 > length:
            raise ValueError("snapshot selection extends past text")


_HINT_KINDS: dict[str, EditKind] = {
    "insertText": EditKind.INSERT,
    "insertCompositionText": EditKind.INSERT,
    "insertFromDrop": EditKind.INSERT,
    "insertFromPaste": EditKind.PASTE,
    "insertReplacementText": EditKind.REPLACE,
    "deleteContentBackward": EditKind.DELETE,
    "deleteContentForward": EditKind.DELETE,
    "deleteByCut": EditKind.DELETE,
}


def _is_snapshot(event: PendingEvent) -> bool:
    return event.source == "user" and event.kind == "snapshot"


def _validate_pending_event(event: PendingEvent) -> None:
    candidate: dict[str, object] = {
        "v": 1,
        "id": event.id,
        "seq": 0,
        "dt_ms": 0,
        "source": event.source,
        "kind": event.kind,
        "payload": event.payload,
    }
    if event.activity is not None:
        candidate["activity"] = event.activity
    EVENT_ADAPTER.validate_python(candidate)


def _fire_payload(event: PendingEvent) -> TimerFirePayload | None:
    if event.source != "timer" or event.kind != "fire":
        return None
    return TimerFirePayload.model_validate(event.payload)


def coalesce(pending: list[PendingEvent], incoming: PendingEvent) -> list[PendingEvent]:
    """Return the pending arrivals after applying the frozen typed merge rules.

    A surviving replacement occupies the incoming event's arrival position. Older raw arrivals
    remain in ingress, but only the newest snapshot or same-timer fire reaches policy commit.
    """
    for event in (*pending, incoming):
        _validate_pending_event(event)

    if _is_snapshot(incoming):
        return [event for event in pending if not _is_snapshot(event)] + [incoming]

    incoming_fire = _fire_payload(incoming)
    if incoming_fire is None:
        return [*pending, incoming]

    kept: list[PendingEvent] = []
    merged_missed_count = incoming_fire.missed_count
    for event in pending:
        prior_fire = _fire_payload(event)
        if prior_fire is None or prior_fire.timer_id != incoming_fire.timer_id:
            kept.append(event)
            continue
        # Each fire represents itself plus its omitted periods. Collapsing the prior visible fire
        # therefore contributes one in addition to its existing missed count.
        merged_missed_count += prior_fire.missed_count + 1

    merged_payload = incoming_fire.model_copy(update={"missed_count": merged_missed_count})
    return [*kept, replace(incoming, payload=merged_payload)]


def _text_diff_kind(previous: str, current: str) -> EditKind:
    if previous == current:
        return EditKind.NONE

    prefix = 0
    common_limit = min(len(previous), len(current))
    while prefix < common_limit and previous[prefix] == current[prefix]:
        prefix += 1

    previous_end = len(previous)
    current_end = len(current)
    while (
        previous_end > prefix
        and current_end > prefix
        and previous[previous_end - 1] == current[current_end - 1]
    ):
        previous_end -= 1
        current_end -= 1

    removed = previous_end - prefix
    inserted = current_end - prefix
    if removed == 0:
        return EditKind.INSERT
    if inserted == 0:
        return EditKind.DELETE
    return EditKind.REPLACE


def derive_edit_kind(
    previous: SnapshotLike | None,
    current: SnapshotLike,
    input_type_hint: str | None,
) -> EditKind:
    """Classify a snapshot transition, using browser hints only when the diff agrees."""
    if previous is None:
        diff_kind = EditKind.INSERT if current.text else EditKind.NONE
    else:
        diff_kind = _text_diff_kind(previous.text, current.text)

    if diff_kind is EditKind.NONE:
        if previous is not None and (
            previous.selection_start_utf16 != current.selection_start_utf16
            or previous.selection_end_utf16 != current.selection_end_utf16
        ):
            return EditKind.CURSOR_MOVE
        return EditKind.NONE

    hinted = _HINT_KINDS.get(input_type_hint or "")
    if diff_kind is EditKind.INSERT and hinted in {EditKind.INSERT, EditKind.PASTE}:
        return hinted
    if hinted is diff_kind:
        return hinted
    return diff_kind
