"""Response-warrant state continuity shared by ticks and rollover."""

from __future__ import annotations

from collections.abc import Iterable

from im.schema.events import SnapshotEvent


def response_handled_snapshot_ids(
    snapshots: Iterable[SnapshotEvent], directly_responded_ids: Iterable[str]
) -> frozenset[str]:
    """Propagate a response disposition through consecutive unchanged text.

    Activity, selection, and composition changes can open or close the floor,
    but they do not create a new conversational warrant.  A changed text ends
    the propagation; returning to the same text later is therefore a new state.
    """
    direct = frozenset(directly_responded_ids)
    handled: set[str] = set()
    responded_text: str | None = None
    for snapshot in snapshots:
        if snapshot.id in direct:
            handled.add(snapshot.id)
            responded_text = snapshot.payload.text
        elif responded_text is not None and snapshot.payload.text == responded_text:
            handled.add(snapshot.id)
        else:
            responded_text = None
    return frozenset(handled)


__all__ = ("response_handled_snapshot_ids",)
