"""Generator-side selection and rendering for G7 timer cancellations."""

from __future__ import annotations

from dataclasses import dataclass

from im.generation.cancel_resolution import (
    ActiveTimer,
    CancelResolution,
    resolve_cancel_utterance,
)

_ORDINALS = (
    "first",
    "second",
    "third",
    "fourth",
    "fifth",
    "sixth",
    "seventh",
    "eighth",
    "ninth",
    "tenth",
)
_DESCRIPTORS = (
    ("amber-blinds", "amber blinds"),
    ("mint-envelope", "mint envelope"),
)


@dataclass(frozen=True, slots=True)
class PlannedCancel:
    utterance: str
    target_timer_id: str
    active_before: tuple[ActiveTimer, ...]
    resolution: CancelResolution


class G7CancelPlan:
    """Track generated active timers and prove each rendered target independently."""

    def __init__(self) -> None:
        self._active: list[ActiveTimer] = []
        self._canceled_count = 0

    def schedule(self, message: str) -> str:
        timer_id = f"t_{len(self._active) + self._canceled_count + 1:03d}"
        self._active.append(ActiveTimer(timer_id, message, self._next_order))
        return timer_id

    def cancel(self, timer_id: str) -> PlannedCancel:
        target = next((timer for timer in self._active if timer.timer_id == timer_id), None)
        if target is None:
            raise ValueError("planned cancel target is not active")
        descriptor, phrase = next(
            ((label, phrase) for label, phrase in _DESCRIPTORS if phrase in target.message),
            (None, None),
        )
        if descriptor is None or phrase is None:
            raise ValueError("planned timer message has no closed cancellation descriptor")
        peers = tuple(timer for timer in self._active if phrase in timer.message)
        ordinal = peers.index(target)
        if ordinal >= len(_ORDINALS):
            raise ValueError("planned cancellation exceeds the closed ordinal grammar")
        utterance = f"Cancel the {_ORDINALS[ordinal]} active {descriptor} reminder."
        active_before = tuple(self._active)
        resolution = resolve_cancel_utterance(utterance, active_before)
        if resolution.resolved_timer_id != timer_id:
            raise ValueError("independent cancellation resolution disagrees with scripted target")
        self._active.remove(target)
        self._canceled_count += 1
        return PlannedCancel(utterance, timer_id, active_before, resolution)

    @property
    def _next_order(self) -> int:
        return len(self._active) + self._canceled_count
