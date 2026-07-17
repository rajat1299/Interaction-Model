"""Reviewer-sidecar evidence, decisions, and their canonical codec."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from re import fullmatch

from im.assets.model import CorpusFamily, Split
from im.canonical_json import canonicalize_tim_json, parse_tim_json
from im.generation.ingestion import _digest
from im.generation.need_lineage import (
    CancelResolutionEvidence,
    DelegateProvenance,
    NeedLineage,
    ScenarioValidationError,
    SkipEvidence,
    skip_reason_for_need,
)
from im.schema.actions import (
    Action,
    CancelAction,
    DelegateAction,
    IdleAction,
    IdleReason,
    IntegrateAction,
    MarkAction,
    NudgeAction,
    RespondAction,
    ScheduleAction,
    SkipAction,
    SkipReason,
)

_BEAT_ID = r"[a-z][a-z0-9_-]{0,63}"
_EVENT_ID = r"e_[0-9]{6}"
_GROUP_ID = r"[a-z][a-z0-9_-]{2,127}"
ACTION_TYPES = (
    CancelAction,
    ScheduleAction,
    NudgeAction,
    SkipAction,
    MarkAction,
    IntegrateAction,
    DelegateAction,
    RespondAction,
    IdleAction,
)


class ResponseWarrantKind(StrEnum):
    YIELD = "yield"
    INVITATION = "invitation"


@dataclass(frozen=True, slots=True)
class BeatResponseWarrant:
    """The declared user snapshot warranting one scripted response beat."""

    beat_id: str
    snapshot_event_id: str
    kind: ResponseWarrantKind | str
    failed_result_event_id: str | None = None

    def __post_init__(self) -> None:
        _require_id(self.beat_id, _BEAT_ID, "beat_id")
        _require_id(self.snapshot_event_id, _EVENT_ID, "snapshot_event_id")
        try:
            kind = ResponseWarrantKind(self.kind)
        except (TypeError, ValueError) as error:
            raise ScenarioValidationError("response warrant kind is not closed") from error
        object.__setattr__(self, "kind", kind)
        if self.failed_result_event_id is not None:
            _require_id(self.failed_result_event_id, _EVENT_ID, "failed_result_event_id")

    def as_json_object(self) -> dict[str, object]:
        result: dict[str, object] = {
            "beat_id": self.beat_id,
            "snapshot_event_id": self.snapshot_event_id,
            "kind": self.kind.value,
        }
        if self.failed_result_event_id is not None:
            result["failed_result_event_id"] = self.failed_result_event_id
        return result


@dataclass(frozen=True, slots=True)
class BeatOpening:
    """The latest user snapshot judged to open one strict scenario beat."""

    beat_id: str
    snapshot_event_id: str

    def __post_init__(self) -> None:
        _require_id(self.beat_id, _BEAT_ID, "beat_id")
        _require_id(self.snapshot_event_id, _EVENT_ID, "snapshot_event_id")

    def as_json_object(self) -> dict[str, object]:
        return {"beat_id": self.beat_id, "snapshot_event_id": self.snapshot_event_id}


@dataclass(frozen=True, slots=True)
class BeatEvidence:
    """All reviewer evidence and oracle context resolved for one action beat."""

    beat_id: str
    stale_tool_result_event_ids: tuple[str, ...]
    floor_open: bool | None
    floor_opening_snapshot_event_id: str | None
    floor_opening_snapshot_text: str | None
    stale_snapshot_event_id: str | None
    stale_snapshot_text: str | None
    response_warrant_kind: ResponseWarrantKind | str | None
    response_warrant_snapshot_event_id: str | None
    response_warrant_snapshot_text: str | None
    response_warrant_failed_result_event_id: str | None
    need_lineage: tuple[NeedLineage, ...]
    delegate_provenance_by_beat: tuple[DelegateProvenance, ...]
    skip_evidence: SkipEvidence | None
    cancel_resolution_evidence: CancelResolutionEvidence | None
    future_actions: tuple[Action, ...] = field(default=(), repr=False, compare=False)
    oracle_floor_open: bool | None = field(default=None, repr=False, compare=False)
    require_floor_opening_evidence: bool = field(default=False, repr=False, compare=False)
    require_g7_evidence: bool = field(default=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        _require_id(self.beat_id, _BEAT_ID, "beat_id")
        _require_sorted_unique_ids(
            self.stale_tool_result_event_ids, _EVENT_ID, "stale tool event ids"
        )
        _require_tuple(self.need_lineage, NeedLineage, "need_lineage")
        if tuple(item.need_id for item in self.need_lineage) != tuple(
            sorted(item.need_id for item in self.need_lineage)
        ):
            raise ScenarioValidationError("need lineage must be sorted and unique by need_id")
        _require_tuple(
            self.delegate_provenance_by_beat,
            DelegateProvenance,
            "delegate_provenance_by_beat",
        )
        _require_tuple(self.future_actions, ACTION_TYPES, "future_actions")
        if self.oracle_floor_open is not None and not isinstance(self.oracle_floor_open, bool):
            raise TypeError("oracle_floor_open must be a bool or None")
        for name in ("require_floor_opening_evidence", "require_g7_evidence"):
            if not isinstance(getattr(self, name), bool):
                raise TypeError(f"{name} must be a bool")

    @property
    def delegate_provenance(self) -> DelegateProvenance | None:
        matches = tuple(
            item for item in self.delegate_provenance_by_beat if item.beat_id == self.beat_id
        )
        if len(matches) > 1:
            raise ScenarioValidationError("delegate provenance must name a beat at most once")
        return matches[0] if matches else None

    def validate_for(
        self,
        action: Action,
        *,
        floor_owned: bool,
        require_captured_facts: bool = False,
    ) -> None:
        if self.floor_open is not None and not isinstance(self.floor_open, bool):
            raise TypeError("floor_open must be a bool or None")
        if self.floor_open and floor_owned:
            raise ScenarioValidationError("an open floor cannot also be hard-owned")
        opening = self.floor_opening_snapshot_event_id, self.floor_opening_snapshot_text
        if self.floor_open is True and require_captured_facts:
            if not all(value is not None for value in opening):
                raise ScenarioValidationError("open-floor evidence must be complete")
            _validate_snapshot_evidence(*opening, "floor-opening snapshot")
        elif require_captured_facts and any(value is not None for value in opening):
            raise ScenarioValidationError("floor-opening evidence requires an open floor")

        stale_skip = (
            isinstance(action, SkipAction) and action.reason is SkipReason.STALE_TOOL_RESULT
        )
        stale = self.stale_snapshot_event_id, self.stale_snapshot_text
        if self.skip_evidence is not None and any(value is not None for value in stale):
            raise ScenarioValidationError(
                "lineage skip evidence must not duplicate stale snapshot evidence"
            )
        if (
            require_captured_facts
            and self.skip_evidence is None
            and not (stale_skip == (stale[0] is not None) == (stale[1] is not None))
        ):
            raise ScenarioValidationError(
                "stale skip snapshot evidence is required exactly for stale skips"
            )
        if require_captured_facts and stale[0] is not None:
            _validate_snapshot_evidence(*stale, "stale snapshot")

        warrant = (
            self.response_warrant_kind,
            self.response_warrant_snapshot_event_id,
            self.response_warrant_snapshot_text,
        )
        if any(value is not None for value in warrant):
            if not all(value is not None for value in warrant):
                raise ScenarioValidationError("response warrant evidence must be complete")
            if not (
                isinstance(action, RespondAction)
                or isinstance(action, IdleAction)
                and action.reason is IdleReason.AWAITING_OPENING
            ):
                raise ScenarioValidationError(
                    "response warrant evidence requires a response or awaiting-opening action"
                )
            try:
                kind = ResponseWarrantKind(self.response_warrant_kind)
            except (TypeError, ValueError) as error:
                raise ScenarioValidationError("response warrant kind is not closed") from error
            object.__setattr__(self, "response_warrant_kind", kind)
            if require_captured_facts:
                _validate_snapshot_evidence(
                    self.response_warrant_snapshot_event_id,
                    self.response_warrant_snapshot_text,
                    "response warrant snapshot",
                )
            if self.response_warrant_failed_result_event_id is not None:
                _require_id(
                    self.response_warrant_failed_result_event_id,
                    _EVENT_ID,
                    "response warrant failed result event id",
                )
        elif self.response_warrant_failed_result_event_id is not None:
            raise ScenarioValidationError(
                "failed-result warrant requires response warrant evidence"
            )

        delegate = self.delegate_provenance
        if delegate is not None:
            if not isinstance(action, DelegateAction):
                raise ScenarioValidationError("delegate provenance requires a delegate action")
        if self.skip_evidence is not None:
            if not isinstance(action, SkipAction):
                raise ScenarioValidationError("skip evidence requires a skip action")
            if self.skip_evidence.target_event_id != action.target_event_id:
                raise ScenarioValidationError("skip evidence target does not match skip action")
            if action.reason is not skip_reason_for_need(self.skip_evidence.need):
                raise ScenarioValidationError("skip reason does not match declared need status")
        if self.cancel_resolution_evidence is not None:
            if not isinstance(action, CancelAction):
                raise ScenarioValidationError("cancel resolution evidence requires a cancel action")
            if self.cancel_resolution_evidence.beat_id != self.beat_id:
                raise ScenarioValidationError(
                    "cancel resolution evidence must name this decision beat"
                )

    def as_json_object(self) -> dict[str, object]:
        result: dict[str, object] = {
            "beat_id": self.beat_id,
            "stale_tool_result_event_ids": list(self.stale_tool_result_event_ids),
        }
        if self.floor_open is not None:
            result["floor_open"] = self.floor_open
        if self.floor_opening_snapshot_event_id is not None:
            result["floor_opening_snapshot_event_id"] = self.floor_opening_snapshot_event_id
            result["floor_opening_snapshot_text"] = self.floor_opening_snapshot_text
        if self.stale_snapshot_event_id is not None:
            result["stale_snapshot_event_id"] = self.stale_snapshot_event_id
            result["stale_snapshot_text"] = self.stale_snapshot_text
        if self.response_warrant_kind is not None:
            result["response_warrant_kind"] = self.response_warrant_kind.value
            result["response_warrant_snapshot_event_id"] = self.response_warrant_snapshot_event_id
            result["response_warrant_snapshot_text"] = self.response_warrant_snapshot_text
            if self.response_warrant_failed_result_event_id is not None:
                result["response_warrant_failed_result_event_id"] = (
                    self.response_warrant_failed_result_event_id
                )
        if self.need_lineage:
            result["need_lineage"] = [item.as_json_object() for item in self.need_lineage]
        if self.delegate_provenance is not None:
            result["delegate_provenance"] = self.delegate_provenance.as_json_object()
        if self.skip_evidence is not None:
            result["skip_evidence"] = self.skip_evidence.as_json_object()
        if self.cancel_resolution_evidence is not None:
            result["cancel_resolution_evidence"] = self.cancel_resolution_evidence.as_json_object()
        return result


@dataclass(frozen=True, slots=True)
class OracleDecision:
    """One exact oracle action, separated into core facts and beat evidence."""

    call_index: int
    observed_policy_seq: int
    action: Action
    open_timer_fire_event_ids: tuple[str, ...]
    open_tool_result_event_ids: tuple[str, ...]
    pending_request_ids: tuple[str, ...]
    active_timer_ids: tuple[str, ...]
    canceled_timer_ids: tuple[str, ...]
    floor_owned: bool
    evidence: BeatEvidence

    def __post_init__(self) -> None:
        if (
            isinstance(self.call_index, bool)
            or not isinstance(self.call_index, int)
            or self.call_index < 1
        ):
            raise ScenarioValidationError("call_index must be a positive integer")
        if (
            isinstance(self.observed_policy_seq, bool)
            or not isinstance(self.observed_policy_seq, int)
            or self.observed_policy_seq < 0
        ):
            raise ScenarioValidationError("observed_policy_seq must be a non-negative integer")
        if not isinstance(self.action, ACTION_TYPES):
            raise TypeError("action must be a concrete Action")
        for values, pattern, name in (
            (self.open_timer_fire_event_ids, _EVENT_ID, "timer event ids"),
            (self.open_tool_result_event_ids, _EVENT_ID, "tool event ids"),
            (self.pending_request_ids, r"r_[0-9]{3}", "request ids"),
            (self.active_timer_ids, r"t_[0-9]{3}", "active timer ids"),
            (self.canceled_timer_ids, r"t_[0-9]{3}", "canceled timer ids"),
        ):
            _require_sorted_unique_ids(values, pattern, name)
        if not isinstance(self.floor_owned, bool):
            raise TypeError("floor_owned must be a bool")
        if not isinstance(self.evidence, BeatEvidence):
            raise TypeError("evidence must be a BeatEvidence")
        if not set(self.evidence.stale_tool_result_event_ids).issubset(
            self.open_tool_result_event_ids
        ):
            raise ScenarioValidationError("stale results must be a subset of open tool results")
        self.evidence.validate_for(
            self.action,
            floor_owned=self.floor_owned,
            require_captured_facts=True,
        )

    @property
    def beat_id(self) -> str:
        return self.evidence.beat_id

    @property
    def stale_tool_result_event_ids(self) -> tuple[str, ...]:
        return self.evidence.stale_tool_result_event_ids

    @property
    def floor_open(self) -> bool | None:
        return self.evidence.floor_open

    @property
    def floor_opening_snapshot_event_id(self) -> str | None:
        return self.evidence.floor_opening_snapshot_event_id

    @property
    def floor_opening_snapshot_text(self) -> str | None:
        return self.evidence.floor_opening_snapshot_text

    @property
    def stale_snapshot_event_id(self) -> str | None:
        return self.evidence.stale_snapshot_event_id

    @property
    def stale_snapshot_text(self) -> str | None:
        return self.evidence.stale_snapshot_text

    @property
    def response_warrant_kind(self) -> ResponseWarrantKind | None:
        return self.evidence.response_warrant_kind

    @property
    def response_warrant_snapshot_event_id(self) -> str | None:
        return self.evidence.response_warrant_snapshot_event_id

    @property
    def response_warrant_snapshot_text(self) -> str | None:
        return self.evidence.response_warrant_snapshot_text

    @property
    def response_warrant_failed_result_event_id(self) -> str | None:
        return self.evidence.response_warrant_failed_result_event_id

    @property
    def need_lineage(self) -> tuple[NeedLineage, ...]:
        return self.evidence.need_lineage

    @property
    def delegate_provenance(self) -> DelegateProvenance | None:
        return self.evidence.delegate_provenance

    @property
    def skip_evidence(self) -> SkipEvidence | None:
        return self.evidence.skip_evidence

    @property
    def cancel_resolution_evidence(self) -> CancelResolutionEvidence | None:
        return self.evidence.cancel_resolution_evidence

    def as_json_object(self) -> dict[str, object]:
        return {
            "call_index": self.call_index,
            "observed_policy_seq": self.observed_policy_seq,
            "action": self.action.model_dump(mode="json"),
            "open_timer_fire_event_ids": list(self.open_timer_fire_event_ids),
            "open_tool_result_event_ids": list(self.open_tool_result_event_ids),
            "pending_request_ids": list(self.pending_request_ids),
            "active_timer_ids": list(self.active_timer_ids),
            "canceled_timer_ids": list(self.canceled_timer_ids),
            "floor_owned": self.floor_owned,
            **self.evidence.as_json_object(),
        }


def decode_sidecar_effective_view(serialized: bytes) -> dict[str, object]:
    """Decode canonical v1 reviewer bytes, expanding decision compression."""
    parsed = parse_tim_json(serialized)
    if not isinstance(parsed, dict) or canonicalize_tim_json(parsed) != serialized:
        raise ScenarioValidationError("sidecar bytes are not canonical")
    decisions = parsed.get("decisions")
    need_states = parsed.get("need_states", [])
    shared_basis_event_texts = parsed.get("shared_basis_event_texts", {})
    if (
        not isinstance(decisions, list)
        or not isinstance(need_states, list)
        or not isinstance(shared_basis_event_texts, dict)
        or not all(
            isinstance(event_id, str) and isinstance(text, str) and text
            for event_id, text in shared_basis_event_texts.items()
        )
    ):
        raise ScenarioValidationError("sidecar compression is malformed")

    effective: list[dict[str, object]] = []
    previous_lineage: list[dict[str, object]] = []
    referenced_shared: set[str] = set()
    for compressed in decisions:
        if not isinstance(compressed, dict) or "need_lineage" in compressed:
            raise ScenarioValidationError("sidecar decision compression is malformed")
        decision = dict(compressed)
        if "need_state" in decision:
            state_id = decision.pop("need_state")
            if state_id is None:
                previous_lineage = []
            elif (
                isinstance(state_id, bool)
                or not isinstance(state_id, int)
                or not 0 <= state_id < len(need_states)
                or not isinstance(need_states[state_id], list)
                or not all(isinstance(item, dict) for item in need_states[state_id])
            ):
                raise ScenarioValidationError("sidecar need-state reference is malformed")
            else:
                previous_lineage = [dict(item) for item in need_states[state_id]]
        if previous_lineage:
            decision["need_lineage"] = [dict(item) for item in previous_lineage]

        evidence = decision.get("skip_evidence")
        if evidence is not None:
            if not isinstance(evidence, dict) or not isinstance(
                evidence.get("basis_event_id"), str
            ):
                raise ScenarioValidationError("sidecar skip evidence is malformed")
            evidence = dict(evidence)
            basis_event_id = evidence["basis_event_id"]
            if basis_event_id in shared_basis_event_texts:
                if "basis_event_text" in evidence:
                    raise ScenarioValidationError("sidecar skip basis text is duplicated")
                evidence["basis_event_text"] = shared_basis_event_texts[basis_event_id]
                referenced_shared.add(basis_event_id)
            if (
                not isinstance(evidence.get("basis_event_text"), str)
                or not evidence["basis_event_text"]
            ):
                raise ScenarioValidationError("sidecar skip basis text is incomplete")
            decision["skip_evidence"] = evidence
        effective.append(decision)
    if referenced_shared != set(shared_basis_event_texts):
        raise ScenarioValidationError("sidecar shared skip basis text is unused")

    result = dict(parsed)
    result.pop("need_states", None)
    result.pop("shared_basis_event_texts", None)
    result["decisions"] = effective
    return result


def serialize_sidecar_decisions(
    decisions: tuple[OracleDecision, ...],
) -> tuple[list[dict[str, object]], list[list[dict[str, object]]], dict[str, str]]:
    """Deduplicate repeated causal state while keeping every decision reconstructable."""
    basis_counts: dict[str, int] = {}
    basis_texts: dict[str, str] = {}
    for decision in decisions:
        evidence = decision.skip_evidence
        if evidence is None:
            continue
        event_id = evidence.need.basis_event_id
        basis_counts[event_id] = basis_counts.get(event_id, 0) + 1
        previous = basis_texts.setdefault(event_id, evidence.basis_event_text or "")
        if previous != evidence.basis_event_text:
            raise ScenarioValidationError("one basis event has conflicting reviewer text")
    shared = {
        event_id: basis_texts[event_id] for event_id, count in basis_counts.items() if count > 1
    }

    serialized: list[dict[str, object]] = []
    need_states: list[list[dict[str, object]]] = []
    need_state_ids: dict[tuple[NeedLineage, ...], int] = {}
    previous_lineage: tuple[NeedLineage, ...] = ()
    for decision in decisions:
        value = decision.as_json_object()
        value.pop("need_lineage", None)
        lineage = decision.need_lineage
        if lineage != previous_lineage:
            if lineage:
                state_id = need_state_ids.get(lineage)
                if state_id is None:
                    state_id = len(need_states)
                    need_state_ids[lineage] = state_id
                    need_states.append([item.as_json_object() for item in lineage])
                value["need_state"] = state_id
            else:
                value["need_state"] = None
        previous_lineage = lineage
        evidence = value.get("skip_evidence")
        if isinstance(evidence, dict) and evidence.get("basis_event_id") in shared:
            evidence.pop("basis_event_text", None)
        serialized.append(value)
    return serialized, need_states, shared


def _validate_snapshot_evidence(event_id: object, text: object, label: str) -> None:
    _require_id(event_id, _EVENT_ID, f"{label} event id")
    if not isinstance(text, str):
        raise TypeError(f"{label} text must be a string")
    try:
        text.encode("utf-8")
    except UnicodeEncodeError as error:
        raise ScenarioValidationError(f"{label} text must be valid UTF-8") from error


def _require_id(value: object, pattern: str, name: str) -> None:
    if not isinstance(value, str) or fullmatch(pattern, value) is None:
        raise ScenarioValidationError(f"{name} has an invalid structure")


def _require_tuple(values: object, expected: type | tuple[type, ...], name: str) -> None:
    if not isinstance(values, tuple) or not all(isinstance(value, expected) for value in values):
        expected_name = getattr(expected, "__name__", "allowed values")
        raise TypeError(f"{name} must be an immutable tuple of {expected_name}")


def _require_sorted_unique_ids(values: object, pattern: str, name: str) -> None:
    if not isinstance(values, tuple):
        raise TypeError(f"{name} must be an immutable tuple")
    if values != tuple(sorted(set(values))):
        raise ScenarioValidationError(f"{name} must be sorted and unique")
    for value in values:
        _require_id(value, pattern, name)


class PerturbationKind(StrEnum):
    DRAFT_REVISION = "draft_revision"
    FLOOR_OPENING = "floor_opening"
    MARK_TARGETING = "mark_targeting"
    MARK_RESTRAINT = "mark_restraint"
    TOOL_RESULT = "tool_result"
    PENDING_TOOL_PRESSURE = "pending_tool_pressure"
    TOPIC_CHANGE = "topic_change"
    TIMER_FIRE = "timer_fire"
    TIMER_CANCEL_RACE = "timer_cancel_race"
    EXTERNAL_EVENT_CONTENTION = "external_event_contention"
    STATE_CHECKPOINT = "state_checkpoint"
    ANNOTATION_SAFETY = "annotation_safety"


class CounterfactualKind(StrEnum):
    TWIN = "twin"
    TRIPLET = "triplet"


@dataclass(frozen=True, slots=True)
class DeclaredPerturbation:
    """One closed D3 perturbation declaration."""

    kind: PerturbationKind | str

    def __post_init__(self) -> None:
        try:
            kind = PerturbationKind(self.kind)
        except (TypeError, ValueError) as error:
            raise ScenarioValidationError("perturbation kind is not closed") from error
        object.__setattr__(self, "kind", kind)

    def as_json_object(self) -> dict[str, object]:
        return {"kind": self.kind.value}


@dataclass(frozen=True, slots=True)
class CounterfactualDeclaration:
    """A closed sibling declaration; cross-stream linkage is finalized later."""

    kind: CounterfactualKind | str
    group_id: str
    member_id: str
    member_ids: tuple[str, ...]
    flipped_perturbation: PerturbationKind | str

    def __post_init__(self) -> None:
        try:
            kind = CounterfactualKind(self.kind)
            flipped = PerturbationKind(self.flipped_perturbation)
        except (TypeError, ValueError) as error:
            raise ScenarioValidationError("counterfactual declaration is not closed") from error
        _require_id(self.group_id, _GROUP_ID, "group_id")
        _require_id(self.member_id, _BEAT_ID, "member_id")
        if not isinstance(self.member_ids, tuple):
            raise TypeError("member_ids must be an immutable tuple")
        if len(self.member_ids) != (2 if kind is CounterfactualKind.TWIN else 3):
            raise ScenarioValidationError("counterfactual member count does not match kind")
        if self.member_ids != tuple(sorted(set(self.member_ids))):
            raise ScenarioValidationError("counterfactual member_ids must be sorted and unique")
        for member in self.member_ids:
            _require_id(member, _BEAT_ID, "member_id")
        if self.member_id not in self.member_ids:
            raise ScenarioValidationError("counterfactual member_id is not declared")
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "flipped_perturbation", flipped)

    def as_json_object(self) -> dict[str, object]:
        return {
            "kind": self.kind.value,
            "group_id": self.group_id,
            "member_id": self.member_id,
            "member_ids": list(self.member_ids),
            "flipped_perturbation": self.flipped_perturbation.value,
        }


@dataclass(frozen=True, slots=True)
class OracleSidecar:
    """Non-teacher-visible provenance and state facts for one generated stream."""

    stream_sha256: str
    capture_sha256: str
    regeneration_identity: str
    split: Split | str
    family: CorpusFamily | str
    template_id: str
    template_content_sha256: str
    asset_ids: tuple[str, ...]
    asset_content_sha256s: tuple[str, ...]
    scenario_input_sha256: str
    world_script_sha256: str
    perturbations: tuple[DeclaredPerturbation, ...]
    counterfactual: CounterfactualDeclaration | None
    decisions: tuple[OracleDecision, ...]
    canonical_bytes: bytes = field(init=False)
    sha256: str = field(init=False)

    def __post_init__(self) -> None:
        for name in (
            "stream_sha256",
            "capture_sha256",
            "regeneration_identity",
            "template_content_sha256",
            "scenario_input_sha256",
            "world_script_sha256",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or fullmatch(r"sha256:[0-9a-f]{64}", value) is None:
                raise ScenarioValidationError(f"{name} must be a sha256 digest")
        try:
            split = Split(self.split)
            family = CorpusFamily(self.family)
        except (TypeError, ValueError) as error:
            raise ScenarioValidationError("sidecar split or family is invalid") from error
        _require_id(self.template_id, r"[a-z][a-z0-9_-]{2,127}", "template_id")
        if not isinstance(self.asset_ids, tuple) or self.asset_ids != tuple(
            sorted(set(self.asset_ids))
        ):
            raise ScenarioValidationError("asset_ids must be sorted and unique")
        if not isinstance(self.asset_content_sha256s, tuple):
            raise TypeError("asset_content_sha256s must be an immutable tuple")
        if not self.asset_ids or len(self.asset_ids) != len(self.asset_content_sha256s):
            raise ScenarioValidationError("asset identities and content hashes must align")
        for asset_id, digest in zip(self.asset_ids, self.asset_content_sha256s, strict=True):
            _require_id(asset_id, r"a_[a-z0-9][a-z0-9_-]{2,63}", "asset_id")
            if not isinstance(digest, str) or fullmatch(r"sha256:[0-9a-f]{64}", digest) is None:
                raise ScenarioValidationError("asset content hash must be a sha256 digest")
        _require_tuple(self.perturbations, DeclaredPerturbation, "perturbations")
        kinds = tuple(item.kind for item in self.perturbations)
        if kinds != tuple(sorted(set(kinds), key=str)):
            raise ScenarioValidationError("sidecar perturbations must be uniquely sorted")
        if self.counterfactual is not None and not isinstance(
            self.counterfactual, CounterfactualDeclaration
        ):
            raise TypeError("counterfactual must be a CounterfactualDeclaration or None")
        _require_tuple(self.decisions, OracleDecision, "decisions")
        if tuple(item.call_index for item in self.decisions) != tuple(
            range(1, len(self.decisions) + 1)
        ):
            raise ScenarioValidationError("sidecar decisions must be in call order")
        object.__setattr__(self, "split", split)
        object.__setattr__(self, "family", family)
        serialized = self.as_json_object()
        canonical = canonicalize_tim_json(serialized)
        effective = decode_sidecar_effective_view(canonical)
        expected_effective = dict(serialized)
        expected_effective.pop("need_states", None)
        expected_effective.pop("shared_basis_event_texts", None)
        expected_effective["decisions"] = [decision.as_json_object() for decision in self.decisions]
        if effective != expected_effective:
            raise ScenarioValidationError("sidecar compression does not round-trip")
        object.__setattr__(self, "canonical_bytes", canonical)
        object.__setattr__(self, "sha256", _digest(canonical))

    def as_json_object(self) -> dict[str, object]:
        decisions, need_states, shared_basis_event_texts = serialize_sidecar_decisions(
            self.decisions
        )
        result: dict[str, object] = {
            "format_version": 1,
            "stream_sha256": self.stream_sha256,
            "capture_sha256": self.capture_sha256,
            "regeneration_identity": self.regeneration_identity,
            "split": self.split.value,
            "family": self.family.value,
            "template": {
                "asset_id": self.template_id,
                "content_sha256": self.template_content_sha256,
            },
            "assets": [
                {"asset_id": asset_id, "content_sha256": digest}
                for asset_id, digest in zip(self.asset_ids, self.asset_content_sha256s, strict=True)
            ],
            "scenario_input_sha256": self.scenario_input_sha256,
            "world_script_sha256": self.world_script_sha256,
            "perturbations": [item.as_json_object() for item in self.perturbations],
            "counterfactual": (
                None if self.counterfactual is None else self.counterfactual.as_json_object()
            ),
            "decisions": decisions,
        }
        if need_states:
            result["need_states"] = need_states
        if shared_basis_event_texts:
            result["shared_basis_event_texts"] = shared_basis_event_texts
        return result
