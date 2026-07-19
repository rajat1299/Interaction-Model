"""Phase 2 trust routing, disagreement clustering, and adjudication sidecars."""

from __future__ import annotations

import json
from collections import defaultdict, deque
from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
from math import ceil, isfinite
from re import fullmatch

from pydantic import BaseModel

from im.assets.model import CorpusFamily, canonical_artifact_bytes
from im.probes.harness.models import HarnessProtocol
from im.schema.actions import ACTION_ADAPTER, IdleReason
from im.schema.events import EVENT_ADAPTER

_DIGEST = r"sha256:[0-9a-f]{64}"


class Phase2ReviewError(ValueError):
    """Phase 2 review evidence is invalid or unsafe to route."""


class FloorClass(StrEnum):
    OPEN = "open"
    OWNED = "owned"
    CLOSED = "closed"


class TrustState(StrEnum):
    UNCLEARED = "uncleared"
    CLEARED = "cleared"


class TeacherComparison(StrEnum):
    EQUIVALENT = "equivalent"
    SEMANTIC_REVIEW = "semantic_review_required"
    DISAGREEMENT = "causal_disagreement"
    MISSING = "teacher_label_missing"


class DisagreementCategory(StrEnum):
    TEACHER_ERROR = "teacher_error"
    ORACLE_ERROR = "oracle_error"
    TEMPLATE_ERROR = "template_error"
    ASSET_AMBIGUITY = "asset_ambiguity"
    CONTRACT_GAP = "contract_gap"
    TEXT_EQUIVALENT = "text_equivalent"
    BOTH_LEGAL_ORACLE_PREFERRED = "both_legal_but_oracle_preferred"


class LabelOrigin(StrEnum):
    HUMAN = "human"
    HUMAN_AUTHORED = "human_authored"
    TEACHER_AUTO_TRUSTED = "teacher_auto_trusted"
    TEACHER_HUMAN_CONFIRMED = "teacher_human_confirmed"
    ORACLE_TEACHER_AGREEMENT = "oracle_teacher_agreement"


class BoundaryClass(StrEnum):
    ORDINARY = "ordinary"
    PARTIAL_INSTRUCTION = "partial_instruction"
    ACTIVE_FLOOR_RESPONSE = "active_floor_response"
    SCHEDULE_SIMILAR_DISTINCT = "schedule_similar_distinct"
    SCHEDULE_SEMANTIC_DUPLICATE = "schedule_semantic_duplicate"
    LOOKUP_REFRESH_SUPERSEDED = "lookup_refresh_superseded"
    LOOKUP_ABANDONED_STALE = "lookup_abandoned_stale"
    AMBIGUOUS_CANCEL = "ambiguous_cancel"


RISK_FLAGS = frozenset(
    {
        "oracle_teacher_non_equivalence",
        "teacher_low_confidence",
        "schedule_semantic_duplicate_boundary",
        "cancel_semantic_referent_resolution",
        "skip_reason_selection",
        "active_floor_response_boundary",
        "rollover_or_checkpoint_projection",
        "first_instances_of_new_template",
    }
)
_PERMANENT_RISK_FLAGS = frozenset(
    {
        "schedule_semantic_duplicate_boundary",
        "cancel_semantic_referent_resolution",
        "skip_reason_selection",
        "active_floor_response_boundary",
    }
)
_PERMANENT_BOUNDARIES = frozenset(
    {
        BoundaryClass.ACTIVE_FLOOR_RESPONSE,
        BoundaryClass.SCHEDULE_SIMILAR_DISTINCT,
        BoundaryClass.SCHEDULE_SEMANTIC_DUPLICATE,
        BoundaryClass.LOOKUP_REFRESH_SUPERSEDED,
        BoundaryClass.LOOKUP_ABANDONED_STALE,
        BoundaryClass.AMBIGUOUS_CANCEL,
    }
)
_BOUNDARY_RISK_FLAGS = {
    BoundaryClass.ACTIVE_FLOOR_RESPONSE: "active_floor_response_boundary",
    BoundaryClass.SCHEDULE_SIMILAR_DISTINCT: "schedule_semantic_duplicate_boundary",
    BoundaryClass.SCHEDULE_SEMANTIC_DUPLICATE: "schedule_semantic_duplicate_boundary",
    BoundaryClass.LOOKUP_REFRESH_SUPERSEDED: "skip_reason_selection",
    BoundaryClass.LOOKUP_ABANDONED_STALE: "skip_reason_selection",
    BoundaryClass.AMBIGUOUS_CANCEL: "cancel_semantic_referent_resolution",
}
_MANDATORY_ACTIONS = frozenset({"schedule", "cancel", "skip", "nudge"})
_POSITIVE_ACTIONS = frozenset({"mark", "delegate", "integrate", "respond"})
_FULL_IDLE_REVIEW = frozenset({"awaiting_opening", "already_handled"})
_EDGE_IDLE_BOUNDARIES = frozenset({"partial_instruction", "lexical_boundary", "ime_edge"})
_MANDATORY_REVIEW_REASONS = (
    "mandatory_action",
    "rollover",
    "teacher_oracle_disagreement",
    "teacher_low_confidence",
    "risk_flag",
    "idle_reason_100_percent",
    "idle_boundary_100_percent",
)
_REVIEW_ROUTE_REASONS = frozenset((*_MANDATORY_REVIEW_REASONS, "stratified_sample"))


@dataclass(frozen=True, slots=True, order=True)
class TrustCellKey:
    protocol: HarnessProtocol
    family: CorpusFamily
    floor: FloorClass

    def __post_init__(self) -> None:
        if not isinstance(self.protocol, HarnessProtocol):
            raise Phase2ReviewError("trust-cell protocol is not closed")
        if not isinstance(self.family, CorpusFamily):
            raise Phase2ReviewError("trust-cell family is not closed")
        if not isinstance(self.floor, FloorClass):
            raise Phase2ReviewError("trust-cell floor is not closed")


@dataclass(frozen=True, slots=True)
class TrustCellStatus:
    key: TrustCellKey
    state: TrustState = TrustState.UNCLEARED
    locked_uncleared: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.key, TrustCellKey) or not isinstance(self.state, TrustState):
            raise Phase2ReviewError("trust-cell status uses an invalid closed value")
        if not isinstance(self.locked_uncleared, bool):
            raise Phase2ReviewError("locked_uncleared must be a bool")
        if self.locked_uncleared and self.state is TrustState.CLEARED:
            raise Phase2ReviewError("a locked trust cell cannot be cleared")


@dataclass(frozen=True, slots=True)
class DecisionEvidence:
    stream_sha256: str
    decision_policy_seq: int
    wave_id: str
    cell: TrustCellKey
    template_id: str
    source_unit_id: str
    oracle_action: object
    teacher_action: object | None
    causal_state_class: str
    boundary_class: BoundaryClass
    risk_flags: tuple[str, ...] = ()
    idle_boundary: str | None = None
    rollover: bool = False

    def __post_init__(self) -> None:
        if (
            not isinstance(self.stream_sha256, str)
            or fullmatch(_DIGEST, self.stream_sha256) is None
        ):
            raise Phase2ReviewError("stream_sha256 must be a sha256 digest")
        if (
            isinstance(self.decision_policy_seq, bool)
            or not isinstance(self.decision_policy_seq, int)
            or self.decision_policy_seq < 0
        ):
            raise Phase2ReviewError("decision_policy_seq must be a non-negative integer")
        for name in ("wave_id", "template_id", "source_unit_id", "causal_state_class"):
            if not _nonempty_text(getattr(self, name)):
                raise Phase2ReviewError(f"{name} must be non-empty")
        object.__setattr__(
            self,
            "oracle_action",
            _normalize_action(self.oracle_action, "oracle action"),
        )
        if self.teacher_action is not None:
            object.__setattr__(
                self,
                "teacher_action",
                _normalize_action(self.teacher_action, "teacher action"),
            )
        if not isinstance(self.cell, TrustCellKey):
            raise Phase2ReviewError("decision trust cell is invalid")
        if not isinstance(self.boundary_class, BoundaryClass):
            raise Phase2ReviewError("boundary class is not closed")
        if (
            not isinstance(self.risk_flags, tuple)
            or not all(isinstance(flag, str) for flag in self.risk_flags)
            or tuple(sorted(set(self.risk_flags))) != self.risk_flags
        ):
            raise Phase2ReviewError("risk flags must be sorted and unique")
        unknown = set(self.risk_flags) - RISK_FLAGS
        if unknown:
            raise Phase2ReviewError(f"unknown Phase 2 risk flags: {sorted(unknown)}")
        non_equivalent = self.comparison in {
            TeacherComparison.SEMANTIC_REVIEW,
            TeacherComparison.DISAGREEMENT,
        }
        if non_equivalent != ("oracle_teacher_non_equivalence" in self.risk_flags):
            raise Phase2ReviewError("teacher non-equivalence and its risk flag must agree")
        required_risk = _BOUNDARY_RISK_FLAGS.get(self.boundary_class)
        if required_risk is not None and required_risk not in self.risk_flags:
            raise Phase2ReviewError(
                f"boundary class {self.boundary_class.value} requires risk flag {required_risk}"
            )
        if self.action_type != "idle" and self.idle_boundary is not None:
            raise Phase2ReviewError("idle_boundary is only valid for idle decisions")
        if self.idle_boundary is not None and not isinstance(self.idle_boundary, str):
            raise Phase2ReviewError("idle_boundary must be a string or None")
        if not isinstance(self.rollover, bool):
            raise Phase2ReviewError("rollover must be a bool")
        if self.action_type == "idle" and self.action_reason not in {
            reason.value for reason in IdleReason
        }:
            raise Phase2ReviewError("idle decisions require a closed idle reason")
        if (
            self.action_type == "respond"
            and self.boundary_class is not BoundaryClass.ACTIVE_FLOOR_RESPONSE
        ):
            raise Phase2ReviewError("respond decisions must identify the response-floor boundary")
        if (
            self.action_type == "idle"
            and self.action_reason == "awaiting_opening"
            and self.boundary_class is not BoundaryClass.ACTIVE_FLOOR_RESPONSE
        ):
            raise Phase2ReviewError("awaiting_opening must identify the active-floor boundary")
        if (
            self.boundary_class is BoundaryClass.PARTIAL_INSTRUCTION
            and self.idle_boundary != "partial_instruction"
        ):
            raise Phase2ReviewError("partial-instruction boundary evidence is inconsistent")

    @property
    def action_type(self) -> str:
        return str(getattr(self.oracle_action, "type"))

    @property
    def action_reason(self) -> str | None:
        return _reason(self.oracle_action)

    @property
    def teacher_action_type(self) -> str | None:
        if self.teacher_action is None:
            return None
        return str(getattr(self.teacher_action, "type"))

    @property
    def teacher_action_reason(self) -> str | None:
        return _reason(self.teacher_action)

    @property
    def comparison(self) -> TeacherComparison:
        return _compare_actions(self.oracle_action, self.teacher_action)

    @property
    def identity(self) -> str:
        return f"{self.stream_sha256}\x00{self.decision_policy_seq}"

    @property
    def permanently_uncleared(self) -> bool:
        return self.boundary_class in _PERMANENT_BOUNDARIES or bool(
            set(self.risk_flags) & _PERMANENT_RISK_FLAGS
        )


def _normalize_action(value: object, label: str) -> BaseModel:
    try:
        return ACTION_ADAPTER.validate_python(value)
    except (TypeError, ValueError) as error:
        raise Phase2ReviewError(f"{label} is not a canonical action") from error


def _normalize_event(value: object) -> BaseModel:
    try:
        return EVENT_ADAPTER.validate_python(value)
    except (TypeError, ValueError) as error:
        raise Phase2ReviewError("reservoir prefix contains a non-canonical event") from error


def _reason(action: object | None) -> str | None:
    if action is None:
        return None
    reason = getattr(action, "reason", None)
    return str(reason) if reason is not None else None


def _action_json(action: object) -> dict[str, object]:
    if not isinstance(action, BaseModel):  # pragma: no cover - normalized at construction
        raise Phase2ReviewError("action was not normalized")
    return action.model_dump(mode="json")


def _event_json(event: object) -> dict[str, object]:
    if not isinstance(event, BaseModel):  # pragma: no cover - normalized at construction
        raise Phase2ReviewError("event was not normalized")
    return event.model_dump(mode="json")


def _nonempty_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _compare_actions(oracle: object, teacher: object | None) -> TeacherComparison:
    if teacher is None:
        return TeacherComparison.MISSING
    oracle_json = _action_json(oracle)
    teacher_json = _action_json(teacher)
    if canonical_artifact_bytes(oracle_json) == canonical_artifact_bytes(teacher_json):
        return TeacherComparison.EQUIVALENT
    if oracle_json["type"] != teacher_json["type"]:
        return TeacherComparison.DISAGREEMENT
    if oracle_json["type"] == "integrate" and (
        oracle_json.get("result_event_id") == teacher_json.get("result_event_id")
    ):
        return TeacherComparison.SEMANTIC_REVIEW
    if oracle_json["type"] == "respond" and (
        oracle_json.get("reply_to_event_id") == teacher_json.get("reply_to_event_id")
    ):
        return TeacherComparison.SEMANTIC_REVIEW
    return TeacherComparison.DISAGREEMENT


@dataclass(frozen=True, slots=True)
class ReviewRoute:
    identity: str
    review_required: bool
    mandatory: bool
    sample_rate: float
    reasons: tuple[str, ...]
    provisional_label_origin: LabelOrigin | None

    def __post_init__(self) -> None:
        if not _nonempty_text(self.identity):
            raise Phase2ReviewError("review route identity must be non-empty")
        if type(self.review_required) is not bool or type(self.mandatory) is not bool:
            raise Phase2ReviewError("review route flags must be exact bools")
        if (
            isinstance(self.sample_rate, bool)
            or not isinstance(self.sample_rate, (int, float))
            or not isfinite(self.sample_rate)
            or not 0 <= self.sample_rate <= 1
        ):
            raise Phase2ReviewError("review route sample_rate must be finite within [0, 1]")
        if (
            not isinstance(self.reasons, tuple)
            or not all(_nonempty_text(reason) for reason in self.reasons)
            or len(self.reasons) != len(set(self.reasons))
        ):
            raise Phase2ReviewError("review route reasons must be unique non-empty strings")
        if any(reason not in _REVIEW_ROUTE_REASONS for reason in self.reasons):
            raise Phase2ReviewError("review route reason is not in the closed router vocabulary")
        if self.mandatory and (not self.review_required or self.sample_rate != 1):
            raise Phase2ReviewError("mandatory review routes must require review at sample_rate 1")
        if self.mandatory:
            canonical = tuple(
                reason for reason in _MANDATORY_REVIEW_REASONS if reason in self.reasons
            )
            if not self.reasons or self.reasons != canonical:
                raise Phase2ReviewError(
                    "mandatory review route reasons must be canonical router reasons"
                )
            if self.provisional_label_origin is not None:
                raise Phase2ReviewError("required review routes need no provisional origin")
        elif self.review_required:
            if (
                self.sample_rate <= 0
                or self.reasons != ("stratified_sample",)
                or self.provisional_label_origin is not None
            ):
                raise Phase2ReviewError(
                    "sampled review routes require a positive rate and only stratified_sample"
                )
        elif self.reasons or not isinstance(self.provisional_label_origin, LabelOrigin):
            raise Phase2ReviewError(
                "non-required review routes need no reasons and a closed provisional origin"
            )

    def validate_for(self, decision: DecisionEvidence) -> None:
        """Close mandatory routing reasons over the decision that caused them."""
        if not isinstance(decision, DecisionEvidence) or self.identity != decision.identity:
            raise Phase2ReviewError("review route does not match its decision")
        expected = _mandatory_reasons(decision)
        if self.mandatory != bool(expected) or (self.mandatory and self.reasons != expected):
            raise Phase2ReviewError("review route reasons do not match the canonical router")


def route_wave(
    decisions: tuple[DecisionEvidence, ...],
    cell_statuses: dict[TrustCellKey, TrustCellStatus],
    *,
    sampling_seed: str,
) -> tuple[ReviewRoute, ...]:
    """Route one wave with deterministic source/template-stratified sampling."""
    if not decisions:
        return ()
    if not _nonempty_text(sampling_seed):
        raise Phase2ReviewError("review sampling seed must be non-empty")
    if len({decision.identity for decision in decisions}) != len(decisions):
        raise Phase2ReviewError("decision identities must be unique within a wave")
    if len({decision.wave_id for decision in decisions}) != 1:
        raise Phase2ReviewError("route_wave accepts exactly one wave at a time")

    mandatory: dict[str, tuple[str, ...]] = {}
    sample_rates: dict[str, float] = {}
    grouped: defaultdict[tuple[TrustCellKey, float], list[DecisionEvidence]] = defaultdict(list)
    for decision in decisions:
        status = cell_statuses.get(decision.cell, TrustCellStatus(decision.cell))
        if status.key != decision.cell:
            raise Phase2ReviewError("trust-cell status key mismatch")
        reasons = _mandatory_reasons(decision)
        if reasons:
            mandatory[decision.identity] = reasons
            sample_rates[decision.identity] = 1.0
            continue
        rate = _review_rate(decision, status.state)
        sample_rates[decision.identity] = rate
        grouped[(decision.cell, rate)].append(decision)

    sampled: set[str] = set()
    for (cell, rate), members in grouped.items():
        if rate <= 0:
            continue
        target = max(1, ceil(len(members) * rate))
        sampled.update(
            item.identity
            for item in _stratified_take(
                members,
                target,
                seed=f"{sampling_seed}|{cell.protocol}|{cell.family}|{cell.floor}|{rate}",
            )
        )

    routes: list[ReviewRoute] = []
    for decision in decisions:
        required = decision.identity in mandatory or decision.identity in sampled
        status = cell_statuses.get(decision.cell, TrustCellStatus(decision.cell))
        origin: LabelOrigin | None = None
        if not required:
            origin = (
                LabelOrigin.TEACHER_AUTO_TRUSTED
                if status.state is TrustState.CLEARED
                else LabelOrigin.ORACLE_TEACHER_AGREEMENT
            )
        routes.append(
            ReviewRoute(
                identity=decision.identity,
                review_required=required,
                mandatory=decision.identity in mandatory,
                sample_rate=sample_rates[decision.identity],
                reasons=(
                    mandatory[decision.identity]
                    if decision.identity in mandatory
                    else (("stratified_sample",) if required else ())
                ),
                provisional_label_origin=origin,
            )
        )
        routes[-1].validate_for(decision)
    return tuple(routes)


def _mandatory_reasons(decision: DecisionEvidence) -> tuple[str, ...]:
    reasons: list[str] = []
    if decision.action_type in _MANDATORY_ACTIONS:
        reasons.append("mandatory_action")
    if decision.rollover or "rollover_or_checkpoint_projection" in decision.risk_flags:
        reasons.append("rollover")
    if decision.comparison is not TeacherComparison.EQUIVALENT:
        reasons.append("teacher_oracle_disagreement")
    if "teacher_low_confidence" in decision.risk_flags:
        reasons.append("teacher_low_confidence")
    if decision.risk_flags:
        reasons.append("risk_flag")
    if decision.action_type == "idle" and decision.action_reason in _FULL_IDLE_REVIEW:
        reasons.append("idle_reason_100_percent")
    if decision.action_type == "idle" and decision.idle_boundary in _EDGE_IDLE_BOUNDARIES:
        reasons.append("idle_boundary_100_percent")
    return tuple(dict.fromkeys(reasons))


def _review_rate(decision: DecisionEvidence, trust_state: TrustState) -> float:
    cleared = trust_state is TrustState.CLEARED
    if decision.action_type in _POSITIVE_ACTIONS:
        return 0.10 if cleared else 0.50
    if decision.action_type != "idle":
        return 1.0
    reason = decision.action_reason
    if reason in {"ambiguous", "instruction_not_direct"}:
        return 0.25 if cleared else 1.0
    if reason == "typing_active":
        return 0.10 if cleared else 0.25
    if reason == "awaiting_tool":
        return 0.10 if cleared else 0.20
    if reason == "no_trigger":
        return 0.10
    return 1.0


def _stratified_take(
    members: list[DecisionEvidence], target: int, *, seed: str
) -> tuple[DecisionEvidence, ...]:
    buckets: defaultdict[tuple[str, str], list[DecisionEvidence]] = defaultdict(list)
    for item in members:
        buckets[(item.template_id, item.source_unit_id)].append(item)
    queues: list[deque[DecisionEvidence]] = []
    for key, bucket in sorted(buckets.items(), key=lambda pair: _rank(seed, repr(pair[0]))):
        queues.append(deque(sorted(bucket, key=lambda item: _rank(seed, item.identity))))
    selected: list[DecisionEvidence] = []
    while queues and len(selected) < target:
        next_round: list[deque[DecisionEvidence]] = []
        for queue in queues:
            selected.append(queue.popleft())
            if queue:
                next_round.append(queue)
            if len(selected) == target:
                break
        queues = next_round
    return tuple(selected)


def _rank(seed: str, value: str) -> bytes:
    return sha256(f"{seed}|{value}".encode()).digest()


@dataclass(frozen=True, slots=True)
class TrustReviewEvidence:
    decision: DecisionEvidence
    category: DisagreementCategory | None
    matrix_version: str
    qualification_window_id: str
    human_reviewed: bool
    review_batch_id: str | None
    unresolved: bool = False
    known_directional_failure: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.decision, DecisionEvidence):
            raise Phase2ReviewError("trust evidence decision is invalid")
        if self.category is not None and not isinstance(self.category, DisagreementCategory):
            raise Phase2ReviewError("disagreement category is not closed")
        if not _nonempty_text(self.matrix_version) or not _nonempty_text(
            self.qualification_window_id
        ):
            raise Phase2ReviewError("trust evidence version fields must be non-empty")
        if not isinstance(self.human_reviewed, bool):
            raise Phase2ReviewError("human_reviewed must be a bool")
        if self.human_reviewed != _nonempty_text(self.review_batch_id):
            raise Phase2ReviewError("human review evidence requires exactly one review batch id")
        if self.category is not None and not self.human_reviewed:
            raise Phase2ReviewError("a disagreement disposition must be human-reviewed")
        needs_disposition = self.decision.comparison in {
            TeacherComparison.SEMANTIC_REVIEW,
            TeacherComparison.DISAGREEMENT,
        }
        if needs_disposition != (self.category is not None):
            raise Phase2ReviewError(
                "non-equivalent teacher evidence requires exactly one disagreement disposition"
            )
        if not isinstance(self.unresolved, bool) or not isinstance(
            self.known_directional_failure, bool
        ):
            raise Phase2ReviewError("trust evidence flags must be bools")


def evaluate_trust_cell(
    status: TrustCellStatus,
    evidence: tuple[TrustReviewEvidence, ...],
    *,
    matrix_version: str,
    qualification_window_id: str,
) -> TrustCellStatus:
    """Apply D1 within one post-repair window, without re-promotion cycles.

    A template/oracle repair starts a new ``qualification_window_id``. Evidence from an older
    window remains auditable but cannot qualify or poison the repaired window.
    """
    if not isinstance(status, TrustCellStatus) or not isinstance(evidence, tuple):
        raise Phase2ReviewError("trust evaluation inputs are invalid")
    if not _nonempty_text(matrix_version) or not _nonempty_text(qualification_window_id):
        raise Phase2ReviewError("trust evaluation version fields must be non-empty")
    evidence_keys = tuple(
        (
            item.decision.identity,
            item.matrix_version,
            item.qualification_window_id,
        )
        for item in evidence
    )
    if len(evidence_keys) != len(set(evidence_keys)):
        raise Phase2ReviewError("trust qualification evidence repeats a reviewed decision")
    family_window = tuple(
        item
        for item in evidence
        if item.decision.cell.family == status.key.family
        and item.matrix_version == matrix_version
        and item.qualification_window_id == qualification_window_id
    )
    if any(
        item.category is DisagreementCategory.CONTRACT_GAP or item.unresolved
        for item in family_window
    ):
        raise Phase2ReviewError("unresolved contract evidence halts the affected family")
    if status.locked_uncleared:
        return status
    if any(
        item.decision.cell == status.key and item.category is DisagreementCategory.TEACHER_ERROR
        for item in evidence
    ):
        return TrustCellStatus(status.key, TrustState.UNCLEARED, locked_uncleared=True)
    current = tuple(item for item in family_window if item.decision.cell == status.key)
    categories = {item.category for item in current}
    if any(
        item.decision.permanently_uncleared or item.known_directional_failure for item in current
    ):
        return TrustCellStatus(status.key, TrustState.UNCLEARED)
    if categories & {DisagreementCategory.ORACLE_ERROR, DisagreementCategory.TEMPLATE_ERROR}:
        return TrustCellStatus(status.key, TrustState.UNCLEARED)
    if status.state is TrustState.CLEARED:
        return status
    reviewed = tuple(item for item in current if item.human_reviewed)
    reviewed = tuple(
        item
        for item in reviewed
        if item.decision.comparison is not TeacherComparison.MISSING
        and item.category
        in {
            None,
            DisagreementCategory.TEXT_EQUIVALENT,
            DisagreementCategory.BOTH_LEGAL_ORACLE_PREFERRED,
        }
    )
    if (
        len(reviewed) >= 30
        and len({item.decision.source_unit_id for item in reviewed}) >= 5
        and len({item.decision.template_id for item in reviewed}) >= 3
    ):
        return TrustCellStatus(status.key, TrustState.CLEARED)
    return TrustCellStatus(status.key, TrustState.UNCLEARED)


def disagreement_cluster_signature(decision: DecisionEvidence) -> str:
    """Canonical D7 cluster identity; action names alone are intentionally insufficient."""
    value = {
        "causal_state_class": decision.causal_state_class,
        "boundary_class": decision.boundary_class.value,
        "comparison": decision.comparison.value,
        "family": decision.cell.family.value,
        "floor": decision.cell.floor.value,
        "oracle_action": _semantic_action_skeleton(decision.oracle_action),
        "protocol": decision.cell.protocol.value,
        "risk_flags": list(decision.risk_flags),
        "idle_boundary": decision.idle_boundary,
        "rollover": decision.rollover,
        "teacher_action": (
            _semantic_action_skeleton(decision.teacher_action)
            if decision.teacher_action is not None
            else None
        ),
        "template": decision.template_id,
    }
    return f"sha256:{sha256(canonical_artifact_bytes(value)).hexdigest()}"


def _semantic_action_skeleton(action: object) -> dict[str, object]:
    """Retain causal references while ignoring only free text for semantic actions."""
    value = _action_json(action)
    if value["type"] in {"respond", "integrate"}:
        value.pop("text", None)
    return value


@dataclass(frozen=True, slots=True)
class LabelAuditMetadata:
    label_origin: LabelOrigin
    trust_matrix_version: str
    review_batch_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.label_origin, LabelOrigin):
            raise Phase2ReviewError("label origin is not closed")
        if not _nonempty_text(self.trust_matrix_version) or not _nonempty_text(
            self.review_batch_id
        ):
            raise Phase2ReviewError("label audit metadata fields must be non-empty")

    def as_json_object(self) -> dict[str, str]:
        return {
            "label_origin": self.label_origin.value,
            "trust_matrix_version": self.trust_matrix_version,
            "review_batch_id": self.review_batch_id,
        }


@dataclass(frozen=True, slots=True)
class ReservoirRecord:
    stream_sha256: str
    decision_policy_seq: int
    policy_prefix: tuple[object, ...]
    policy_prefix_sha256: str
    chosen_action: object
    rejected_action: object
    disagreement_category: DisagreementCategory
    human_reason: str
    trust_cell: TrustCellKey
    risk_flags: tuple[str, ...]

    def __post_init__(self) -> None:
        if (
            not isinstance(self.stream_sha256, str)
            or fullmatch(_DIGEST, self.stream_sha256) is None
        ):
            raise Phase2ReviewError("reservoir stream identity must be a sha256 digest")
        if (
            isinstance(self.decision_policy_seq, bool)
            or not isinstance(self.decision_policy_seq, int)
            or self.decision_policy_seq < 0
            or not self.policy_prefix
            or not _nonempty_text(self.human_reason)
        ):
            raise Phase2ReviewError("reservoir evidence is incomplete")
        if not isinstance(self.policy_prefix, tuple):
            raise Phase2ReviewError("reservoir policy prefix must be a tuple")
        normalized_prefix = tuple(_normalize_event(event) for event in self.policy_prefix)
        object.__setattr__(self, "policy_prefix", normalized_prefix)
        object.__setattr__(
            self,
            "chosen_action",
            _normalize_action(self.chosen_action, "reservoir chosen action"),
        )
        object.__setattr__(
            self,
            "rejected_action",
            _normalize_action(self.rejected_action, "reservoir rejected action"),
        )
        if not isinstance(self.disagreement_category, DisagreementCategory):
            raise Phase2ReviewError("reservoir disagreement category is not closed")
        if not isinstance(self.trust_cell, TrustCellKey):
            raise Phase2ReviewError("reservoir trust cell is invalid")
        prefix_sequences = tuple(getattr(event, "seq") for event in self.policy_prefix)
        if any(
            isinstance(seq, bool) or not isinstance(seq, int) for seq in prefix_sequences
        ) or prefix_sequences != tuple(range(self.decision_policy_seq + 1)):
            raise Phase2ReviewError(
                "reservoir prefix must be complete and ordered through policy seq"
            )
        expected_prefix_sha256 = (
            "sha256:"
            + sha256(
                canonical_artifact_bytes([_event_json(event) for event in self.policy_prefix])
            ).hexdigest()
        )
        if (
            not isinstance(self.policy_prefix_sha256, str)
            or fullmatch(_DIGEST, self.policy_prefix_sha256) is None
            or self.policy_prefix_sha256 != expected_prefix_sha256
        ):
            raise Phase2ReviewError("reservoir policy-prefix digest mismatch")
        if canonical_artifact_bytes(_action_json(self.chosen_action)) == canonical_artifact_bytes(
            _action_json(self.rejected_action)
        ):
            raise Phase2ReviewError("reservoir chosen and rejected actions must differ")
        if (
            tuple(sorted(set(self.risk_flags))) != self.risk_flags
            or set(self.risk_flags) - RISK_FLAGS
        ):
            raise Phase2ReviewError("reservoir risk flags are invalid")

    def as_json_object(self) -> dict[str, object]:
        return {
            "chosen_action": _action_json(self.chosen_action),
            "decision_policy_seq": self.decision_policy_seq,
            "direct_dpo_eligibility": False,
            "disagreement_category": self.disagreement_category.value,
            "human_reason": self.human_reason,
            "policy_prefix": [_event_json(event) for event in self.policy_prefix],
            "policy_prefix_sha256": self.policy_prefix_sha256,
            "rejected_action": _action_json(self.rejected_action),
            "risk_flags": list(self.risk_flags),
            "source": "teacher_oracle_adjudication",
            "stream_sha256": self.stream_sha256,
            "trust_cell": {
                "family": self.trust_cell.family.value,
                "floor": self.trust_cell.floor.value,
                "protocol": self.trust_cell.protocol.value,
            },
        }


def export_reservoir_jsonl(records: tuple[ReservoirRecord, ...]) -> bytes:
    """Export the Phase 4 supplement as deterministic JSONL."""
    identities = [(record.stream_sha256, record.decision_policy_seq) for record in records]
    if len(identities) != len(set(identities)):
        raise Phase2ReviewError("reservoir decision identities must be unique")
    lines = [
        json.dumps(record.as_json_object(), sort_keys=True, separators=(",", ":"))
        for record in sorted(
            records, key=lambda item: (item.stream_sha256, item.decision_policy_seq)
        )
    ]
    return (("\n".join(lines) + "\n") if lines else "").encode()
