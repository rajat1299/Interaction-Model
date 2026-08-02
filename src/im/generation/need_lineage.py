"""Reviewer-only factual-need lineage and delegate provenance checks."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from re import IGNORECASE, fullmatch, match

from im.canonical_json import canonicalize_tim_json
from im.generation.cancel_resolution import ActiveTimer, CancelResolution, resolve_cancel_utterance
from im.generation.runtime import DecisionBoundary
from im.license import SnapshotView, ToolResultView
from im.schema.actions import (
    Action,
    CancelAction,
    CancelAllActiveTarget,
    CancelTimersTarget,
    CancelTimerTarget,
    DelegateAction,
    IntegrateAction,
    RespondAction,
    ScheduleAction,
    SkipAction,
    SkipReason,
    Span,
)
from im.schema.common import Disposition, TimerStatus
from im.schema.events import (
    ActionExecutedEvent,
    CancelAckEvent,
    ScheduledEvent,
    SnapshotEvent,
    StateCheckpointEvent,
    ToolRequestedEvent,
    ToolResultEvent,
)
from im.schema.textspan import utf16_slice
from im.serialize import parse_event

_BEAT_ID = r"[a-z][a-z0-9_-]{0,63}"
_EVENT_ID = r"e_[0-9]{6}"
_NEED_ID = r"n_[a-z0-9][a-z0-9_-]{0,63}"
_TIMER_ID = r"t_[0-9]{3}"
_DELEGATE_FRAMING_PREFIX = r"(?:look\s*up|check|refresh|find|search\s+for|tell\s+me|please)\b"


class ScenarioValidationError(ValueError):
    """A frozen scenario or its reviewer sidecar violates the closed contract."""


class NeedStatus(StrEnum):
    """Reviewer-only lifecycle of one factual need."""

    LIVE = "live"
    ABANDONED = "abandoned"
    SUPERSEDED = "superseded"
    SATISFIED = "satisfied"


class NeedBasisKind(StrEnum):
    """Closed provenance kinds for the one visible basis of a factual need."""

    REQUEST = "request"
    ABANDONED = "abandoned"
    TOPIC_CHANGED = "topic_changed"
    SUPERSEDED = "superseded"
    RESULT = "result"


_NEED_BASIS_BY_STATUS = {
    NeedStatus.LIVE: frozenset({NeedBasisKind.REQUEST}),
    NeedStatus.ABANDONED: frozenset({NeedBasisKind.ABANDONED, NeedBasisKind.TOPIC_CHANGED}),
    NeedStatus.SUPERSEDED: frozenset({NeedBasisKind.SUPERSEDED}),
    NeedStatus.SATISFIED: frozenset({NeedBasisKind.RESULT}),
}


@dataclass(frozen=True, slots=True)
class NeedLineage:
    """One factual need and the single visible event supporting its current status."""

    need_id: str
    status: NeedStatus | str
    basis_event_id: str
    superseded_by_need_id: str | None = None
    basis_kind: NeedBasisKind | str | None = None

    def __post_init__(self) -> None:
        _require_id(self.need_id, _NEED_ID, "need_id")
        _require_id(self.basis_event_id, _EVENT_ID, "need basis_event_id")
        try:
            status = NeedStatus(self.status)
        except (TypeError, ValueError) as error:
            raise ScenarioValidationError("need status is not closed") from error
        try:
            basis_kind = (
                NeedBasisKind.REQUEST
                if self.basis_kind is None and status is NeedStatus.LIVE
                else NeedBasisKind.RESULT
                if self.basis_kind is None and status is NeedStatus.SATISFIED
                else NeedBasisKind.ABANDONED
                if self.basis_kind is None and status is NeedStatus.ABANDONED
                else NeedBasisKind.SUPERSEDED
                if self.basis_kind is None
                else NeedBasisKind(self.basis_kind)
            )
        except (TypeError, ValueError) as error:
            raise ScenarioValidationError("need basis_kind is not closed") from error
        if basis_kind not in _NEED_BASIS_BY_STATUS[status]:
            raise ScenarioValidationError("need status and basis_kind are incompatible")
        if status is NeedStatus.SUPERSEDED:
            _require_id(self.superseded_by_need_id, _NEED_ID, "superseded_by_need_id")
            if self.superseded_by_need_id == self.need_id:
                raise ScenarioValidationError("a need cannot supersede itself")
        elif self.superseded_by_need_id is not None:
            raise ScenarioValidationError("only a superseded need may name its replacement")
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "basis_kind", basis_kind)

    def as_json_object(self) -> dict[str, object]:
        result: dict[str, object] = {
            "need_id": self.need_id,
            "status": self.status.value,
            "basis_kind": self.basis_kind.value,
            "basis_event_id": self.basis_event_id,
        }
        if self.superseded_by_need_id is not None:
            result["superseded_by_need_id"] = self.superseded_by_need_id
        return result


FactualNeed = NeedLineage


@dataclass(frozen=True, slots=True)
class BeatNeedLineage:
    """The complete reviewer-only factual-need state at one decision beat."""

    beat_id: str
    needs: tuple[NeedLineage, ...]

    def __post_init__(self) -> None:
        _require_id(self.beat_id, _BEAT_ID, "beat_id")
        _require_tuple(self.needs, NeedLineage, "needs")
        if tuple(item.need_id for item in self.needs) != tuple(
            sorted({item.need_id for item in self.needs})
        ):
            raise ScenarioValidationError("need lineage must be sorted and unique by need_id")

    def as_json_object(self) -> dict[str, object]:
        return {"beat_id": self.beat_id, "needs": [item.as_json_object() for item in self.needs]}


@dataclass(frozen=True, slots=True)
class DelegateProvenance:
    """The reviewer-declared factual need and exact query slot for one delegate beat."""

    beat_id: str
    need_id: str
    query_slot: Span

    def __post_init__(self) -> None:
        _require_id(self.beat_id, _BEAT_ID, "beat_id")
        _require_id(self.need_id, _NEED_ID, "need_id")
        if not isinstance(self.query_slot, Span):
            raise TypeError("query_slot must be a Span")

    def as_json_object(self) -> dict[str, object]:
        return {
            "beat_id": self.beat_id,
            "need_id": self.need_id,
            "query_slot": self.query_slot.model_dump(mode="json"),
        }


@dataclass(frozen=True, slots=True)
class SkipEvidence:
    """Reviewer-only causal evidence for a stale or superseded tool result."""

    target_event_id: str
    need: NeedLineage
    original_fact_event_id: str | None = None
    original_fact_text: str | None = None
    basis_event_text: str | None = None
    successor_fact_event_id: str | None = None
    successor_fact_text: str | None = None

    def __post_init__(self) -> None:
        _require_id(self.target_event_id, _EVENT_ID, "skip target_event_id")
        if not isinstance(self.need, NeedLineage):
            raise TypeError("skip need must be a NeedLineage")
        if self.need.status not in {NeedStatus.ABANDONED, NeedStatus.SUPERSEDED}:
            raise ScenarioValidationError("skip evidence needs an abandoned or superseded need")
        _require_id(self.original_fact_event_id, _EVENT_ID, "original fact_event_id")
        if not isinstance(self.original_fact_text, str) or not self.original_fact_text:
            raise ScenarioValidationError("skip evidence needs the original fact text")
        if not isinstance(self.basis_event_text, str) or not self.basis_event_text:
            raise ScenarioValidationError("skip evidence needs visible basis text")
        if self.need.status is NeedStatus.SUPERSEDED:
            successor = (self.successor_fact_event_id, self.successor_fact_text)
            if any(value is not None for value in successor):
                _require_id(self.successor_fact_event_id, _EVENT_ID, "successor fact_event_id")
                if not isinstance(self.successor_fact_text, str) or not self.successor_fact_text:
                    raise ScenarioValidationError("superseded skip needs successor fact text")
        elif self.successor_fact_event_id is not None or self.successor_fact_text is not None:
            raise ScenarioValidationError("only superseded skip evidence has a successor fact")

    def as_json_object(self) -> dict[str, object]:
        result: dict[str, object] = {
            "target_result_event_id": self.target_event_id,
            "original_need_id": self.need.need_id,
            "original_fact_event_id": self.original_fact_event_id,
            "original_fact_text": self.original_fact_text,
            "basis_kind": self.need.basis_kind.value,
            "basis_event_id": self.need.basis_event_id,
            "basis_event_text": self.basis_event_text,
            "scripted_skip_reason": skip_reason_for_need(self.need).value,
        }
        if self.successor_fact_event_id is not None:
            result["successor_fact_event_id"] = self.successor_fact_event_id
            result["successor_fact_text"] = self.successor_fact_text
        return result


@dataclass(frozen=True, slots=True)
class CancelResolutionEvidence:
    """Optional reviewer-only evidence for the timers a cancel beat resolves."""

    beat_id: str
    basis_event_id: str
    resolved_timer_ids: tuple[str, ...]
    active_timers: tuple[ActiveTimer, ...] = ()
    resolution: CancelResolution | None = None
    scripted_target_timer_id: str | None = None

    def __post_init__(self) -> None:
        _require_id(self.beat_id, _BEAT_ID, "beat_id")
        _require_id(self.basis_event_id, _EVENT_ID, "cancel basis_event_id")
        _require_sorted_unique_ids(self.resolved_timer_ids, _TIMER_ID, "resolved_timer_ids")
        if not self.resolved_timer_ids:
            raise ScenarioValidationError("cancel resolution must identify at least one timer")
        _require_tuple(self.active_timers, ActiveTimer, "active_timers")
        if (
            self.active_timers
            and tuple(
                sorted(
                    self.active_timers, key=lambda item: (item.schedule_policy_seq, item.timer_id)
                )
            )
            != self.active_timers
        ):
            raise ScenarioValidationError(
                "active_timers must be ordered by schedule policy sequence"
            )
        if self.resolution is not None and not isinstance(self.resolution, CancelResolution):
            raise TypeError("cancel resolution must be a CancelResolution or None")
        if self.scripted_target_timer_id is not None:
            _require_id(self.scripted_target_timer_id, _TIMER_ID, "scripted_target_timer_id")
        full = (self.active_timers, self.resolution, self.scripted_target_timer_id)
        if any(value is not None and value != () for value in full) and not all(
            value is not None for value in full
        ):
            raise ScenarioValidationError("cancel resolution evidence must be complete")
        if self.resolution is not None:
            if self.resolution.resolved_timer_id != self.scripted_target_timer_id:
                raise ScenarioValidationError(
                    "resolver target does not match scripted cancel target"
                )
            if self.resolved_timer_ids != (self.scripted_target_timer_id,):
                raise ScenarioValidationError(
                    "resolved timer ids do not match scripted cancel target"
                )

    def as_json_object(self) -> dict[str, object]:
        result: dict[str, object] = {
            "beat_id": self.beat_id,
            "basis_event_id": self.basis_event_id,
            "resolved_timer_ids": list(self.resolved_timer_ids),
        }
        if self.resolution is not None:
            result["active_timers"] = [item.as_json_object() for item in self.active_timers]
            result.update(self.resolution.as_json_object())
            result["scripted_target_timer_id"] = self.scripted_target_timer_id
        return result


def validate_authored_need_lineage(
    beat_ids: tuple[str, ...],
    actions: tuple[Action, ...],
    need_lineage_by_beat: tuple[BeatNeedLineage, ...] | None,
    delegate_provenance_by_beat: tuple[DelegateProvenance, ...] | None,
) -> None:
    """Check the complete, reviewer-only declaration before runtime execution."""
    if (need_lineage_by_beat is None) != (delegate_provenance_by_beat is None):
        raise ScenarioValidationError(
            "need lineage and delegate provenance must be declared together"
        )
    if need_lineage_by_beat is None:
        return
    _require_tuple(need_lineage_by_beat, BeatNeedLineage, "need_lineage_by_beat")
    _require_tuple(
        delegate_provenance_by_beat,
        DelegateProvenance,
        "delegate_provenance_by_beat",
    )
    if tuple(item.beat_id for item in need_lineage_by_beat) != beat_ids:
        raise ScenarioValidationError("need lineage must cover every program beat in order")
    delegate_beats = tuple(
        beat_id
        for beat_id, action in zip(beat_ids, actions, strict=True)
        if isinstance(action, DelegateAction)
    )
    if tuple(item.beat_id for item in delegate_provenance_by_beat) != delegate_beats:
        raise ScenarioValidationError("delegate provenance must cover delegate beats in order")
    if len({item.need_id for item in delegate_provenance_by_beat}) != len(
        delegate_provenance_by_beat
    ):
        raise ScenarioValidationError("delegate provenance need_ids must be unique")
    provenance_by_beat = {item.beat_id: item for item in delegate_provenance_by_beat}
    provenance_by_need = {item.need_id: item for item in delegate_provenance_by_beat}
    for beat_id, action in zip(beat_ids, actions, strict=True):
        if not isinstance(action, DelegateAction):
            continue
        provenance = provenance_by_beat[beat_id]
        if provenance.query_slot != action.fact:
            raise ScenarioValidationError("delegate provenance must use the exact action fact slot")
        if action.fact.text != action.args.query or action.args.query != provenance.query_slot.text:
            raise ScenarioValidationError("delegate fact, query, and query slot must match")
        if action.fact.text[-1] in ".?!":
            raise ScenarioValidationError(
                "delegate query slot retains sentence-closing punctuation"
            )
        _validate_delegate_query_text(action.fact.text)

    births: dict[str, tuple[int, NeedLineage]] = {}
    previous: dict[str, NeedLineage] = {}
    for index, lineage in enumerate(need_lineage_by_beat):
        current = {item.need_id: item for item in lineage.needs}
        if not set(previous).issubset(current):
            raise ScenarioValidationError("factual needs cannot disappear from lineage")
        for need_id, need in current.items():
            if need_id not in previous:
                births[need_id] = (index, need)
        previous = current

    if set(births) != set(provenance_by_need):
        raise ScenarioValidationError("need lineage must exactly cover declared delegate needs")
    for need_id, (_index, need) in births.items():
        provenance = provenance_by_need[need_id]
        if (
            need.status is not NeedStatus.LIVE
            or need.basis_kind is not NeedBasisKind.REQUEST
            or need.basis_event_id != provenance.query_slot.event_id
        ):
            raise ScenarioValidationError(
                "a newly declared factual need must be live at its request snapshot"
            )

    previous = {}
    for index, lineage in enumerate(need_lineage_by_beat):
        current = {item.need_id: item for item in lineage.needs}
        for need_id, need in current.items():
            prior = previous.get(need_id)
            if prior is not None and prior.status is not NeedStatus.LIVE and need != prior:
                raise ScenarioValidationError("terminal factual-need status cannot change")
            if (
                prior is not None
                and prior.status is NeedStatus.LIVE
                and need.status is NeedStatus.LIVE
                and need != prior
            ):
                raise ScenarioValidationError("a live factual need must retain its single basis")
            if need.status is NeedStatus.SUPERSEDED:
                replacement_id = need.superseded_by_need_id or ""
                replacement_birth = births.get(replacement_id)
                if (
                    replacement_birth is None
                    or not births[need_id][0] < replacement_birth[0] <= index
                ):
                    raise ScenarioValidationError(
                        "a superseding factual need must be later and already declared"
                    )
                if prior is not None and prior.status is NeedStatus.LIVE:
                    replacement = current[replacement_id]
                    if replacement.status is not NeedStatus.LIVE:
                        raise ScenarioValidationError(
                            "a replacement factual need must be live when it supersedes"
                        )
        previous = current


def validate_cancel_resolution_declarations(
    beat_ids: tuple[str, ...],
    actions: tuple[Action, ...],
    declarations: tuple[CancelResolutionEvidence, ...],
    *,
    require_evidence: bool = False,
) -> None:
    if not isinstance(require_evidence, bool):
        raise TypeError("require_evidence must be a bool")
    _require_tuple(
        declarations,
        CancelResolutionEvidence,
        "cancel_resolution_evidence_by_beat",
    )
    by_beat = {item.beat_id: item for item in declarations}
    if len(by_beat) != len(declarations) or tuple(item.beat_id for item in declarations) != tuple(
        beat_id for beat_id in beat_ids if beat_id in by_beat
    ):
        raise ScenarioValidationError(
            "cancel resolution evidence must name distinct beats in order"
        )
    action_by_beat = dict(zip(beat_ids, actions, strict=True))
    if require_evidence and tuple(by_beat) != tuple(
        beat_id
        for beat_id, action in zip(beat_ids, actions, strict=True)
        if isinstance(action, CancelAction)
    ):
        raise ScenarioValidationError("strict programs require evidence for every cancel beat")
    for beat_id, evidence in by_beat.items():
        action = action_by_beat.get(beat_id)
        if not isinstance(action, CancelAction):
            raise ScenarioValidationError("cancel resolution evidence requires a cancel beat")
        if evidence.basis_event_id != action.instruction.event_id:
            raise ScenarioValidationError("cancel resolution basis must match its instruction")


def validate_need_lineage(
    boundary: DecisionBoundary,
    need_lineage: tuple[NeedLineage, ...],
) -> None:
    if not need_lineage:
        return
    if tuple(item.need_id for item in need_lineage) != tuple(
        sorted(item.need_id for item in need_lineage)
    ):
        raise ScenarioValidationError("need lineage must be sorted and unique by need_id")
    visible_need_ids = {item.need_id for item in need_lineage}
    for need in need_lineage:
        _validate_visible_need_basis(boundary, need)
        if (
            need.status is NeedStatus.SUPERSEDED
            and need.superseded_by_need_id not in visible_need_ids
        ):
            raise ScenarioValidationError("superseding need is absent from this lineage")


def validate_declared_delegate(
    action: Action,
    boundary: DecisionBoundary,
    need_lineage: tuple[NeedLineage, ...],
    delegate_provenance: tuple[DelegateProvenance, ...],
) -> None:
    if not isinstance(action, DelegateAction):
        return
    if not need_lineage and not delegate_provenance:
        return
    matches = tuple(item for item in delegate_provenance if item.query_slot == action.fact)
    if len(matches) != 1:
        raise ScenarioValidationError("delegate lacks one declared explicit query slot")
    provenance = matches[0]
    need = next((item for item in need_lineage if item.need_id == provenance.need_id), None)
    if need is None:
        raise ScenarioValidationError("delegate need is absent from this lineage")
    if need.status is not NeedStatus.LIVE:
        raise ScenarioValidationError("delegate need must be live")
    if action.fact.text != action.args.query or action.args.query != provenance.query_slot.text:
        raise ScenarioValidationError("delegate fact, query, and declared query slot must match")
    snapshot = boundary.license_view.event(provenance.query_slot.event_id)
    if not isinstance(snapshot, SnapshotView):
        raise ScenarioValidationError("delegate query slot is not a visible snapshot")
    try:
        query_text = utf16_slice(
            snapshot.text,
            provenance.query_slot.start_utf16,
            provenance.query_slot.end_utf16,
        )
    except (TypeError, ValueError) as error:
        raise ScenarioValidationError("delegate query slot has an invalid UTF-16 slice") from error
    if query_text != provenance.query_slot.text:
        raise ScenarioValidationError("delegate query slot does not match its UTF-16 slice")
    if action.fact.text[-1] in ".?!":
        raise ScenarioValidationError("delegate query slot retains sentence-closing punctuation")
    _validate_delegate_query_text(action.fact.text)


def declared_need_skips(
    boundary: DecisionBoundary,
    need_lineage: tuple[NeedLineage, ...],
    delegate_provenance: tuple[DelegateProvenance, ...],
) -> tuple[tuple[SkipAction, NeedLineage], ...]:
    if not need_lineage:
        return ()
    candidates: list[tuple[SkipAction, NeedLineage]] = []
    for result in boundary.license_view.events:
        if not isinstance(result, ToolResultView) or result.disposition is not Disposition.OPEN:
            continue
        need = _need_for_tool_result(boundary, result, need_lineage, delegate_provenance)
        if need.status not in {NeedStatus.ABANDONED, NeedStatus.SUPERSEDED}:
            continue
        candidates.append(
            (
                SkipAction(
                    type="skip",
                    target_event_id=result.event_id,
                    reason=skip_reason_for_need(need),
                ),
                need,
            )
        )
    return tuple(candidates)


def validate_declared_result_status(
    action: Action,
    boundary: DecisionBoundary,
    need_lineage: tuple[NeedLineage, ...],
    delegate_provenance: tuple[DelegateProvenance, ...],
) -> None:
    result_event_id = (
        action.result_event_id
        if isinstance(action, IntegrateAction)
        else action.reply_to_event_id
        if isinstance(action, RespondAction)
        else None
    )
    result = boundary.license_view.event(result_event_id)
    if not isinstance(result, ToolResultView):
        return
    need = _need_for_tool_result(boundary, result, need_lineage, delegate_provenance)
    if need.status is not NeedStatus.LIVE:
        raise ScenarioValidationError("only a live factual need may use a tool result")


def validate_cancel_resolution(
    action: Action,
    boundary: DecisionBoundary,
    evidence: CancelResolutionEvidence | None,
) -> None:
    if evidence is None:
        return
    if not isinstance(evidence, CancelResolutionEvidence):
        raise TypeError("cancel_resolution_evidence must be a CancelResolutionEvidence or None")
    if not isinstance(action, CancelAction):
        raise ScenarioValidationError("cancel resolution evidence requires a cancel action")
    if action.instruction.event_id != evidence.basis_event_id:
        raise ScenarioValidationError("cancel basis does not match the cancel instruction")
    basis = boundary.license_view.event(evidence.basis_event_id)
    if (
        not isinstance(basis, SnapshotView)
        or _visible_snapshot_ids(boundary).count(evidence.basis_event_id) != 1
    ):
        raise ScenarioValidationError("cancel basis must be visible exactly once")
    if isinstance(action.target, CancelTimerTarget):
        resolved_timer_ids = (action.target.timer_id,)
    elif isinstance(action.target, CancelTimersTarget):
        resolved_timer_ids = tuple(action.target.timer_ids)
    elif isinstance(action.target, CancelAllActiveTarget):
        resolved_timer_ids = tuple(
            timer.timer_id
            for timer in boundary.license_view.timers
            if timer.status is TimerStatus.ACTIVE
        )
    else:  # pragma: no cover - the frozen target union is closed.
        raise ScenarioValidationError("cancel target is not closed")
    if evidence.resolved_timer_ids != resolved_timer_ids:
        raise ScenarioValidationError("cancel resolution does not match resolved timers")
    if evidence.resolution is not None:
        if not isinstance(action.target, CancelTimerTarget):
            raise ScenarioValidationError("ordinal cancel evidence requires one timer target")
        resolution = resolve_cancel_utterance(action.instruction.text, evidence.active_timers)
        if resolution != evidence.resolution:
            raise ScenarioValidationError("cancel resolver output differs from evidence")
        if evidence.scripted_target_timer_id != action.target.timer_id:
            raise ScenarioValidationError("cancel evidence target differs from scripted action")


def derive_cancel_resolution_evidence(
    action: Action,
    boundary: DecisionBoundary,
    declaration: CancelResolutionEvidence | None,
    full_policy_segments: tuple[bytes, ...],
    observed_policy_seq: int,
) -> CancelResolutionEvidence | None:
    """Bind a declared ordinal cancellation to the complete emitted policy history.

    Checkpoints deliberately omit the originating schedule policy sequence, so this
    reconstructs the active ledger only from emitted schedule actions and their
    runtime acknowledgements across every retained generated segment.
    """
    if declaration is None:
        return None
    validate_cancel_resolution(action, boundary, declaration)
    if not isinstance(action, CancelAction):  # defensive after declaration validation.
        raise ScenarioValidationError("cancel resolution evidence requires a cancel action")
    if not isinstance(action.target, CancelTimerTarget):
        raise ScenarioValidationError("ordinal cancel evidence requires one timer target")
    active_timers = _active_timers_before_policy_seq(full_policy_segments, observed_policy_seq)
    try:
        resolution = resolve_cancel_utterance(action.instruction.text, active_timers)
    except ValueError as error:
        raise ScenarioValidationError(
            "cancel instruction is outside the ordinal resolver grammar"
        ) from error
    evidence = CancelResolutionEvidence(
        beat_id=declaration.beat_id,
        basis_event_id=declaration.basis_event_id,
        resolved_timer_ids=(action.target.timer_id,),
        active_timers=active_timers,
        resolution=resolution,
        scripted_target_timer_id=action.target.timer_id,
    )
    validate_cancel_resolution(action, boundary, evidence)
    return evidence


def skip_reason_for_need(need: NeedLineage) -> SkipReason:
    if need.status is NeedStatus.ABANDONED:
        return SkipReason.STALE_TOOL_RESULT
    if need.status is NeedStatus.SUPERSEDED:
        return SkipReason.SUPERSEDED_QUERY
    raise ScenarioValidationError("only abandoned or superseded needs may skip a result")


def build_skip_evidence(
    boundary: DecisionBoundary,
    target_event_id: str,
    need: NeedLineage,
    delegate_provenance: tuple[DelegateProvenance, ...],
) -> SkipEvidence:
    """Materialize the self-contained reviewer packet for one need-based skip."""
    provenance = tuple(item for item in delegate_provenance if item.need_id == need.need_id)
    if len(provenance) != 1:
        raise ScenarioValidationError("skip evidence lacks one original factual need source")
    original = provenance[0].query_slot
    successor = (
        next(
            (
                item.query_slot
                for item in delegate_provenance
                if item.need_id == need.superseded_by_need_id
            ),
            None,
        )
        if need.status is NeedStatus.SUPERSEDED
        else None
    )
    if need.status is NeedStatus.SUPERSEDED and successor is None:
        raise ScenarioValidationError("superseded skip lacks successor factual provenance")
    return SkipEvidence(
        target_event_id=target_event_id,
        need=need,
        original_fact_event_id=original.event_id,
        original_fact_text=original.text,
        basis_event_text=_visible_need_basis_text(boundary, need),
        successor_fact_event_id=None if successor is None else successor.event_id,
        successor_fact_text=None if successor is None else successor.text,
    )


def _validate_visible_need_basis(boundary: DecisionBoundary, need: NeedLineage) -> None:
    snapshots = _visible_snapshot_texts(boundary, need.basis_event_id)
    if need.basis_kind is NeedBasisKind.REQUEST:
        if len(snapshots) == 1:
            return
        checkpoint_facts = _checkpoint_fact_texts(boundary, need.basis_event_id)
        if len(snapshots) == 0 and len(checkpoint_facts) == 1:
            return
        raise ScenarioValidationError(
            "request need basis must be one visible snapshot or checkpoint fact reference"
        )
    if need.basis_kind in {
        NeedBasisKind.ABANDONED,
        NeedBasisKind.TOPIC_CHANGED,
        NeedBasisKind.SUPERSEDED,
    }:
        if len(snapshots) != 1 or not isinstance(
            boundary.license_view.event(need.basis_event_id), SnapshotView
        ):
            if (
                need.basis_kind is NeedBasisKind.SUPERSEDED
                and len(snapshots) == 0
                and len(_checkpoint_fact_texts(boundary, need.basis_event_id)) == 1
            ):
                return
            raise ScenarioValidationError("terminal need basis must be one visible snapshot")
        return
    if need.basis_kind is NeedBasisKind.RESULT:
        results = _visible_result_texts(boundary, need.basis_event_id)
        if len(results) != 1 or not isinstance(
            boundary.license_view.event(need.basis_event_id), ToolResultView
        ):
            raise ScenarioValidationError("satisfied need basis must be one visible tool result")
        return
    raise ScenarioValidationError("need basis_kind is not closed")  # pragma: no cover


def _visible_need_basis_text(boundary: DecisionBoundary, need: NeedLineage) -> str:
    _validate_visible_need_basis(boundary, need)
    if need.basis_kind in {NeedBasisKind.REQUEST, NeedBasisKind.SUPERSEDED}:
        snapshots = _visible_snapshot_texts(boundary, need.basis_event_id)
        if snapshots:
            return snapshots[0]
        return _checkpoint_fact_texts(boundary, need.basis_event_id)[0]
    if need.basis_kind is NeedBasisKind.RESULT:
        return _visible_result_texts(boundary, need.basis_event_id)[0]
    return _visible_snapshot_texts(boundary, need.basis_event_id)[0]


def _validate_delegate_query_text(text: str) -> None:
    if match(_DELEGATE_FRAMING_PREFIX, text, flags=IGNORECASE) is not None:
        raise ScenarioValidationError("delegate fact includes an operation-framing prefix")


def _active_timers_before_policy_seq(
    full_policy_segments: tuple[bytes, ...], observed_policy_seq: int
) -> tuple[ActiveTimer, ...]:
    if isinstance(observed_policy_seq, bool) or not isinstance(observed_policy_seq, int):
        raise TypeError("observed_policy_seq must be an integer")
    timers: dict[str, ActiveTimer] = {}
    scheduled_action: tuple[int, object] | None = None
    cancel_action: CancelAction | None = None
    for segment in full_policy_segments:
        if not isinstance(segment, bytes):
            raise TypeError("full policy segments must be immutable policy bytes")
        for line in segment.splitlines():
            event = parse_event(line)
            if event.seq > observed_policy_seq:
                continue
            if isinstance(event, ActionExecutedEvent):
                if isinstance(event.payload.action, ScheduleAction):
                    scheduled_action = (event.seq, event.payload.action)
                    cancel_action = None
                elif isinstance(event.payload.action, CancelAction):
                    cancel_action = event.payload.action
                    scheduled_action = None
                else:
                    scheduled_action = None
                    cancel_action = None
                continue
            if isinstance(event, ScheduledEvent):
                if scheduled_action is None:
                    raise ScenarioValidationError("scheduled acknowledgement lacks schedule action")
                schedule_seq, schedule = scheduled_action
                if event.payload.message != schedule.message:
                    raise ScenarioValidationError("scheduled acknowledgement does not match action")
                timers[event.payload.timer_id] = ActiveTimer(
                    timer_id=event.payload.timer_id,
                    message=event.payload.message,
                    schedule_policy_seq=schedule_seq,
                )
                scheduled_action = None
                continue
            if isinstance(event, CancelAckEvent):
                if cancel_action is None:
                    raise ScenarioValidationError("cancel acknowledgement lacks cancel action")
                for timer_id in event.payload.timer_ids:
                    timers.pop(timer_id, None)
                cancel_action = None
    return tuple(
        sorted(timers.values(), key=lambda item: (item.schedule_policy_seq, item.timer_id))
    )


@dataclass(frozen=True, slots=True)
class _RequestDelegateSource:
    fact_event_id: str
    fact_text: str
    query: str
    fact: Span | None = None


def _need_for_tool_result(
    boundary: DecisionBoundary,
    result: ToolResultView,
    need_lineage: tuple[NeedLineage, ...],
    delegate_provenance: tuple[DelegateProvenance, ...],
) -> NeedLineage:
    source = _request_delegate_sources(boundary).get(result.request_id)
    if source is None:
        raise ScenarioValidationError("tool result lacks visible delegate provenance")
    candidates = tuple(
        item for item in delegate_provenance if _matches_request_source(item, source)
    )
    if len(candidates) != 1:
        raise ScenarioValidationError("tool result lacks one declared factual need")
    need = next((item for item in need_lineage if item.need_id == candidates[0].need_id), None)
    if need is None:
        raise ScenarioValidationError("tool result need is absent from this lineage")
    return need


def _matches_request_source(
    provenance: DelegateProvenance,
    source: _RequestDelegateSource,
) -> bool:
    if source.fact is not None:
        return provenance.query_slot == source.fact
    return (
        provenance.query_slot.event_id == source.fact_event_id
        and provenance.query_slot.text == source.fact_text == source.query
    )


def _request_delegate_sources(boundary: DecisionBoundary) -> dict[str, _RequestDelegateSource]:
    sources: dict[str, _RequestDelegateSource] = {}
    events = tuple(parse_event(line) for line in boundary.policy_bytes.splitlines())
    for index, event in enumerate(events):
        if isinstance(event, StateCheckpointEvent):
            for result in event.payload.open_tool_results:
                sources[result.request_id] = _RequestDelegateSource(
                    result.fact_event_id, result.fact_text, result.args.query
                )
            for pending in event.payload.pending_tools:
                sources[pending.request_id] = _RequestDelegateSource(
                    pending.fact_event_id, pending.fact_text, pending.args.query
                )
            for prior in event.payload.prior_uses:
                if prior.kind == "delegate":
                    sources[prior.request_id] = _RequestDelegateSource(
                        prior.fact.event_id, prior.fact.text, prior.args.query, prior.fact
                    )
            continue
        if not isinstance(event, ToolRequestedEvent) or index == 0:
            continue
        previous = events[index - 1]
        if not isinstance(previous, ActionExecutedEvent):
            continue
        delegate = previous.payload.action
        if not isinstance(delegate, DelegateAction):
            continue
        if delegate.tool != event.payload.tool or delegate.args != event.payload.args:
            continue
        sources[event.payload.request_id] = _RequestDelegateSource(
            delegate.fact.event_id, delegate.fact.text, delegate.args.query, delegate.fact
        )
    return sources


def _visible_snapshot_ids(boundary: DecisionBoundary) -> tuple[str, ...]:
    return tuple(event_id for event_id, _text in _visible_snapshots(boundary))


def _visible_snapshot_texts(boundary: DecisionBoundary, event_id: str) -> tuple[str, ...]:
    return tuple(
        text for visible_id, text in _visible_snapshots(boundary) if visible_id == event_id
    )


def _visible_snapshots(boundary: DecisionBoundary) -> tuple[tuple[str, str], ...]:
    snapshots: list[tuple[str, str]] = []
    for line in boundary.policy_bytes.splitlines():
        event = parse_event(line)
        if isinstance(event, StateCheckpointEvent):
            snapshots.append((event.payload.snapshot.event_id, event.payload.snapshot.text))
        elif isinstance(event, SnapshotEvent):
            snapshots.append((event.id, event.payload.text))
    return tuple(snapshots)


def _checkpoint_fact_texts(boundary: DecisionBoundary, event_id: str) -> tuple[str, ...]:
    facts: list[str] = []
    for line in boundary.policy_bytes.splitlines():
        event = parse_event(line)
        if not isinstance(event, StateCheckpointEvent):
            continue
        facts.extend(
            item.fact_text
            for item in (*event.payload.open_tool_results, *event.payload.pending_tools)
            if item.fact_event_id == event_id
        )
    return tuple(facts)


def _visible_result_texts(boundary: DecisionBoundary, event_id: str) -> tuple[str, ...]:
    results: list[str] = []
    for line in boundary.policy_bytes.splitlines():
        event = parse_event(line)
        if isinstance(event, ToolResultEvent) and event.id == event_id:
            results.append(canonicalize_tim_json(event.payload.data).decode("utf-8"))
        elif isinstance(event, StateCheckpointEvent):
            results.extend(
                canonicalize_tim_json(item.data).decode("utf-8")
                for item in event.payload.open_tool_results
                if item.event_id == event_id
            )
    return tuple(results)


def _require_id(value: object, pattern: str, name: str) -> None:
    if not isinstance(value, str) or fullmatch(pattern, value) is None:
        raise ScenarioValidationError(f"{name} has an invalid structure")


def _require_tuple(values: object, expected: type | tuple[type, ...], name: str) -> None:
    if not isinstance(values, tuple) or not all(isinstance(value, expected) for value in values):
        expected_name = getattr(expected, "__name__", "allowed values")
        raise TypeError(f"{name} must be an immutable tuple of {expected_name}")


def _require_sorted_unique_ids(values: Iterable[str], pattern: str, name: str) -> None:
    if not isinstance(values, tuple):
        raise TypeError(f"{name} must be an immutable tuple")
    if values != tuple(sorted(set(values))):
        raise ScenarioValidationError(f"{name} must be sorted and unique")
    for value in values:
        _require_id(value, pattern, name)
