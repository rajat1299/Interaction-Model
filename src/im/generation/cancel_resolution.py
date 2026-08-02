"""Independent v1 resolver for generated ordinal timer cancellations."""

from __future__ import annotations

from dataclasses import dataclass
from re import fullmatch, sub

_ORDINALS = {
    "first": 1,
    "second": 2,
    "third": 3,
    "fourth": 4,
    "fifth": 5,
    "sixth": 6,
    "seventh": 7,
    "eighth": 8,
    "ninth": 9,
    "tenth": 10,
}
_CANCEL = (
    r"Cancel the (?P<ordinal>[a-z]+) active "
    r"(?P<descriptor>[a-z]+(?:-[a-z]+)*) reminder\."
)


@dataclass(frozen=True, slots=True)
class ActiveTimer:
    """The reviewer-visible timer facts available before one cancellation."""

    timer_id: str
    message: str
    schedule_policy_seq: int

    def __post_init__(self) -> None:
        if not self.timer_id or not self.message:
            raise ValueError("active timer identity and message must be non-empty")
        if isinstance(self.schedule_policy_seq, bool) or self.schedule_policy_seq < 0:
            raise ValueError("schedule_policy_seq must be a non-negative integer")

    def as_json_object(self) -> dict[str, object]:
        return {
            "timer_id": self.timer_id,
            "message": self.message,
            "schedule_policy_seq": self.schedule_policy_seq,
        }


@dataclass(frozen=True, slots=True)
class CancelResolution:
    """The independently parsed descriptor, candidates, and resolved target."""

    descriptor: str
    ordinal: int
    candidate_timer_ids: tuple[str, ...]
    resolved_timer_id: str | None

    def as_json_object(self) -> dict[str, object]:
        return {
            "descriptor": self.descriptor,
            "candidate_timer_ids": list(self.candidate_timer_ids),
            "resolved_ordinal": self.ordinal,
            "resolved_target": self.resolved_timer_id,
        }


def resolve_cancel_utterance(
    utterance: str, active_timers: tuple[ActiveTimer, ...]
) -> CancelResolution:
    """Resolve a closed generated cancellation without renderer implementation reuse."""
    match = fullmatch(_CANCEL, utterance)
    if match is None or match["ordinal"] not in _ORDINALS:
        raise ValueError("cancellation utterance is outside the closed v1 grammar")
    descriptor = match["descriptor"]
    phrase = descriptor.replace("-", " ")
    candidates = tuple(
        timer
        for timer in sorted(
            active_timers, key=lambda item: (item.schedule_policy_seq, item.timer_id)
        )
        if phrase in _normalized_message(timer.message)
    )
    ordinal = _ORDINALS[match["ordinal"]]
    resolved = candidates[ordinal - 1].timer_id if ordinal <= len(candidates) else None
    return CancelResolution(
        descriptor=descriptor,
        ordinal=ordinal,
        candidate_timer_ids=tuple(timer.timer_id for timer in candidates),
        resolved_timer_id=resolved,
    )


def _normalized_message(message: str) -> str:
    return sub(r"[^a-z0-9]+", " ", message.casefold()).strip()
