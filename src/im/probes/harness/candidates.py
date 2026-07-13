"""Deterministic state-derived listwise distractors."""

from __future__ import annotations

import re
from dataclasses import dataclass
from hashlib import sha256

from im.license import Allowed, LicenseView, SnapshotView, TimerFireView, ToolResultView, check
from im.probes.harness.protocols import RankedCandidate
from im.probes.model import LogicalProbe, RenderedVariant
from im.probes.validate import ProbeValidationError, assert_reference_integrity
from im.schema.actions import (
    Action,
    CancelAction,
    CancelTimerTarget,
    DelegateAction,
    IdleAction,
    LookupArgs,
    MarkAction,
    NudgeAction,
    RespondAction,
    ScheduleAction,
    SkipAction,
    Span,
)
from im.schema.common import Disposition, TimerStatus
from im.schema.textspan import utf16_len

_WORD = re.compile(r"[^\W_]+(?:[-'][^\W_]+)*", re.UNICODE)


@dataclass(frozen=True, slots=True)
class ListwisePresentation:
    candidates: tuple[RankedCandidate, ...]
    expected_candidate_id: str
    tempting_candidate_id: str


@dataclass(frozen=True, slots=True)
class _Candidate:
    action: Action
    origin: str


def build_listwise_presentation(
    probe: LogicalProbe,
    variant: RenderedVariant,
    view: LicenseView,
) -> ListwisePresentation:
    """Retain approved contrast and add one allowed state-derived action per missing type."""
    candidates = [
        _Candidate(variant.expected_action, "expected"),
        _Candidate(variant.tempting_alternative, "tempting"),
    ]
    present_types = {candidate.action.type for candidate in candidates}
    for action in _synthetic_actions(view):
        if action.type in present_types:
            continue
        try:
            assert_reference_integrity(action, view)
        except ProbeValidationError:
            continue
        if not isinstance(check(action, view), Allowed):
            continue
        candidates.append(_Candidate(action, f"synthetic:{action.type}"))
        present_types.add(action.type)

    ordered = sorted(
        candidates,
        key=lambda candidate: sha256(
            (
                f"{probe.probe_id}|{candidate.origin}|"
                f"{candidate.action.model_dump_json(exclude_none=False)}"
            ).encode()
        ).digest(),
    )
    ranked = tuple(
        RankedCandidate(f"c{index:02d}", candidate.action)
        for index, candidate in enumerate(ordered, start=1)
    )
    expected_id = ranked[next(i for i, item in enumerate(ordered) if item.origin == "expected")]
    tempting_id = ranked[next(i for i, item in enumerate(ordered) if item.origin == "tempting")]
    return ListwisePresentation(
        candidates=ranked,
        expected_candidate_id=expected_id.candidate_id,
        tempting_candidate_id=tempting_id.candidate_id,
    )


def _synthetic_actions(view: LicenseView) -> tuple[Action, ...]:
    actions: list[Action] = [
        IdleAction(type="idle", reason="no_trigger", related_event_id=None)
    ]
    snapshot = view.latest_snapshot
    if snapshot is not None and snapshot.text:
        spans = _lexical_spans(snapshot)
        instruction_spans = (*spans, _full_span(snapshot))
        for target in spans:
            actions.append(
                MarkAction(
                    type="mark",
                    instruction=_full_span(snapshot),
                    target=target,
                )
            )
        for fact in spans:
            actions.append(
                DelegateAction(
                    type="delegate",
                    fact=fact,
                    tool="lookup",
                    args=LookupArgs(query=fact.text),
                )
            )
        interval_ms = min(
            view.max_timer_interval_ms,
            max(view.min_timer_interval_ms, 300_000),
        )
        for instruction in instruction_spans:
            actions.append(
                ScheduleAction(
                    type="schedule",
                    instruction=instruction,
                    interval_ms=interval_ms,
                    message=instruction.text.strip(),
                )
            )
        actions.append(
            RespondAction(
                type="respond",
                reply_to_event_id=snapshot.event_id,
                text="Understood.",
            )
        )
        active_timers = sorted(
            (timer for timer in view.timers if timer.status is TimerStatus.ACTIVE),
            key=lambda timer: timer.timer_id,
        )
        if active_timers:
            actions.append(
                CancelAction(
                    type="cancel",
                    instruction=_full_span(snapshot),
                    target=CancelTimerTarget(
                        kind="timer",
                        timer_id=active_timers[0].timer_id,
                    ),
                )
            )

    for event in sorted(view.events, key=lambda item: (item.policy_seq, item.event_id)):
        if isinstance(event, ToolResultView) and event.disposition is Disposition.OPEN:
            actions.append(
                SkipAction(
                    type="skip",
                    target_event_id=event.event_id,
                    reason="stale_tool_result",
                )
            )
        if isinstance(event, TimerFireView) and event.disposition is Disposition.OPEN:
            timer = next(
                (candidate for candidate in view.timers if candidate.timer_id == event.timer_id),
                None,
            )
            if timer is not None and timer.status is TimerStatus.ACTIVE:
                actions.append(NudgeAction(type="nudge", fire_event_id=event.event_id))
            elif timer is not None and timer.status is TimerStatus.CANCELED:
                actions.append(
                    SkipAction(
                        type="skip",
                        target_event_id=event.event_id,
                        reason="canceled_timer",
                    )
                )
    return tuple(actions)


def _lexical_spans(snapshot: SnapshotView) -> tuple[Span, ...]:
    return tuple(
        Span(
            event_id=snapshot.event_id,
            start_utf16=utf16_len(snapshot.text[: match.start()]),
            end_utf16=utf16_len(snapshot.text[: match.end()]),
            text=match.group(),
        )
        for match in _WORD.finditer(snapshot.text)
    )


def _full_span(snapshot: SnapshotView) -> Span:
    return Span(
        event_id=snapshot.event_id,
        start_utf16=0,
        end_utf16=utf16_len(snapshot.text),
        text=snapshot.text,
    )
