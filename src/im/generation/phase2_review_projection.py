"""Canonical, packet-bound evidence for the three Phase 2 review additions."""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
from re import fullmatch

from im.assets.model import CorpusFamily, canonical_artifact_bytes
from im.generation.phase2_review import (
    BoundaryClass,
    DecisionEvidence,
    FloorClass,
    LabelOrigin,
    Phase2ReviewError,
    ReviewRoute,
    TeacherComparison,
    TrustCellKey,
    disagreement_cluster_signature,
)
from im.probes.harness.models import HarnessProtocol
from im.schema.common import LicenseBlockCode

_DIGEST = r"sha256:[0-9a-f]{64}"
_FORMAT_VERSION = 1
_LICENSE_RESULTS = frozenset({"licensed", "blocked"})
_NON_EQUIVALENT = frozenset({TeacherComparison.SEMANTIC_REVIEW, TeacherComparison.DISAGREEMENT})


class Phase2ReviewProjectionError(ValueError):
    """Phase 2 review evidence does not close over its packet inputs."""


@dataclass(frozen=True, slots=True)
class CandidateLicense:
    result: str
    codes: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.result not in _LICENSE_RESULTS:
            raise Phase2ReviewProjectionError("candidate license result is not closed")
        if (
            not isinstance(self.codes, tuple)
            or not all(isinstance(code, LicenseBlockCode) for code in self.codes)
            or self.codes != tuple(sorted(set(self.codes)))
        ):
            raise Phase2ReviewProjectionError("candidate license codes must be sorted and unique")
        if self.result == "licensed" and self.codes:
            raise Phase2ReviewProjectionError("licensed candidate cannot carry blocking codes")

    def as_json_object(self) -> dict[str, object]:
        return {"codes": [code.value for code in self.codes], "result": self.result}


@dataclass(frozen=True, slots=True)
class DecisionProjectionInput:
    """Closed upstream inputs for one reviewed packet decision."""

    decision: DecisionEvidence
    route: ReviewRoute
    oracle_license: CandidateLicense
    teacher_license: CandidateLicense | None
    oracle_provenance: Mapping[str, str]
    teacher_provenance: Mapping[str, str] | None
    priority_rank: int

    def __post_init__(self) -> None:
        if not isinstance(self.decision, DecisionEvidence) or not isinstance(
            self.route, ReviewRoute
        ):
            raise Phase2ReviewProjectionError("projection decision and route are required")
        if self.route.identity != self.decision.identity:
            raise Phase2ReviewProjectionError("projection route does not match decision identity")
        try:
            self.route.validate_for(self.decision)
        except Phase2ReviewError as error:
            raise Phase2ReviewProjectionError("projection route is not canonical") from error
        if not isinstance(self.oracle_license, CandidateLicense) or (
            self.teacher_license is not None
            and not isinstance(self.teacher_license, CandidateLicense)
        ):
            raise Phase2ReviewProjectionError("projection licenses are invalid")
        if self.decision.teacher_action is None:
            if self.teacher_license is not None or self.teacher_provenance is not None:
                raise Phase2ReviewProjectionError("missing teacher action cannot carry evidence")
        elif self.teacher_license is None or self.teacher_provenance is None:
            raise Phase2ReviewProjectionError("teacher action requires closed evidence")
        _provenance(self.oracle_provenance, "oracle provenance")
        if self.teacher_provenance is not None:
            _provenance(self.teacher_provenance, "teacher provenance")
        if (
            isinstance(self.priority_rank, bool)
            or not isinstance(self.priority_rank, int)
            or self.priority_rank < 0
        ):
            raise Phase2ReviewProjectionError("priority rank must be a non-negative integer")


def _provenance(value: Mapping[str, str], label: str) -> dict[str, str]:
    if not isinstance(value, Mapping) or not value:
        raise Phase2ReviewProjectionError(f"{label} must be a non-empty mapping")
    normalized: dict[str, str] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not key or not isinstance(item, str) or not item:
            raise Phase2ReviewProjectionError(f"{label} must contain non-empty strings")
        normalized[key] = item
    return dict(sorted(normalized.items()))


def _identity(value: object, label: str) -> tuple[str, int]:
    if not isinstance(value, tuple) or len(value) != 2:
        raise Phase2ReviewProjectionError(f"{label} must be a decision identity")
    stream_sha256, policy_seq = value
    if (
        not isinstance(stream_sha256, str)
        or fullmatch(_DIGEST, stream_sha256) is None
        or isinstance(policy_seq, bool)
        or not isinstance(policy_seq, int)
        or policy_seq < 0
    ):
        raise Phase2ReviewProjectionError(f"{label} is invalid")
    return stream_sha256, policy_seq


def _action_json(action: object) -> dict[str, object]:
    try:
        return action.model_dump(mode="json")  # type: ignore[union-attr]
    except AttributeError as error:  # pragma: no cover - DecisionEvidence normalizes actions
        raise Phase2ReviewProjectionError("candidate action is not canonical") from error


def _origin_order(blind_commitment: str, identity: str) -> tuple[str, str]:
    rank = sha256(f"{blind_commitment}|{identity}".encode()).digest()
    return ("oracle", "teacher") if rank[0] % 2 == 0 else ("teacher", "oracle")


def _candidate_order(input_: DecisionProjectionInput, blind_commitment: str) -> tuple[str, str]:
    """Stable A/B order derived from the emitted public seed commitment."""
    if input_.decision.teacher_action is None:  # pragma: no cover - guarded by caller
        raise Phase2ReviewProjectionError("candidate ordering requires a teacher action")
    oracle = canonical_artifact_bytes(_action_json(input_.decision.oracle_action))
    teacher = canonical_artifact_bytes(_action_json(input_.decision.teacher_action))
    if oracle == teacher:
        raise Phase2ReviewProjectionError("blinded candidates must be distinct")
    return _origin_order(blind_commitment, input_.decision.identity)


def _candidate_json(
    input_: DecisionProjectionInput, origin: str, candidate_id: str
) -> dict[str, object]:
    if origin == "oracle":
        return {
            "action": _action_json(input_.decision.oracle_action),
            "candidate_id": candidate_id,
            "license": input_.oracle_license.as_json_object(),
            "reveal": {
                "origin": "oracle",
                "provenance": _provenance(input_.oracle_provenance, "oracle provenance"),
            },
        }
    if input_.decision.teacher_action is None or input_.teacher_license is None:
        raise Phase2ReviewProjectionError("teacher candidate is incomplete")
    return {
        "action": _action_json(input_.decision.teacher_action),
        "candidate_id": candidate_id,
        "license": input_.teacher_license.as_json_object(),
        "reveal": {
            "origin": "teacher",
            "provenance": _provenance(input_.teacher_provenance or {}, "teacher provenance"),
        },
    }


def _decision_json(input_: DecisionProjectionInput, blind_commitment: str) -> dict[str, object]:
    decision = input_.decision
    non_equivalent = decision.comparison in _NON_EQUIVALENT
    candidates: list[dict[str, object]] = []
    signature: str | None = None
    if non_equivalent:
        if decision.teacher_action is None:
            raise Phase2ReviewProjectionError("non-equivalent decision requires two candidates")
        order = _candidate_order(input_, blind_commitment)
        candidates = [
            _candidate_json(input_, order[0], "A"),
            _candidate_json(input_, order[1], "B"),
        ]
        signature = disagreement_cluster_signature(decision)
    return {
        "candidates": candidates,
        "cluster_signature": signature,
        "comparison": decision.comparison.value,
        "decision_policy_seq": decision.decision_policy_seq,
        "oracle_action": _action_json(decision.oracle_action),
        "priority_rank": input_.priority_rank,
        "review_evidence": {
            "boundary_class": decision.boundary_class.value,
            "causal_state_class": decision.causal_state_class,
            "idle_boundary": decision.idle_boundary,
            "review_route": {
                "mandatory": input_.route.mandatory,
                "provisional_label_origin": (
                    input_.route.provisional_label_origin.value
                    if input_.route.provisional_label_origin is not None
                    else None
                ),
                "reasons": list(input_.route.reasons),
                "review_required": input_.route.review_required,
                "sample_rate": input_.route.sample_rate,
            },
            "risk_flags": list(decision.risk_flags),
            "rollover": decision.rollover,
            "template_id": decision.template_id,
            "trust_cell": {
                "family": decision.cell.family.value,
                "floor": decision.cell.floor.value,
                "protocol": decision.cell.protocol.value,
            },
            "wave_id": decision.wave_id,
        },
        "source_unit_id": decision.source_unit_id,
        "stream_sha256": decision.stream_sha256,
    }


def _identity_json(value: tuple[str, int]) -> dict[str, object]:
    return {"decision_policy_seq": value[1], "stream_sha256": value[0]}


def _build_clusters(
    decisions: list[tuple[DecisionProjectionInput, dict[str, object]]],
    blind_commitment: str,
) -> list[dict[str, object]]:
    by_signature: defaultdict[str, list[tuple[DecisionProjectionInput, dict[str, object]]]] = (
        defaultdict(list)
    )
    for input_, decision in decisions:
        signature = decision["cluster_signature"]
        if isinstance(signature, str):
            by_signature[signature].append((input_, decision))

    clusters: list[dict[str, object]] = []
    for signature, members in sorted(by_signature.items()):
        ordered = sorted(members, key=lambda item: item[0].priority_rank)
        representative = ordered[0]
        confirmations: list[tuple[DecisionProjectionInput, dict[str, object]]] = []
        seen_sources = {representative[0].decision.source_unit_id}
        confirmation_pool = sorted(
            ordered[1:],
            key=lambda item: sha256(
                f"{blind_commitment}|{signature}|{item[0].decision.identity}".encode()
            ).digest(),
        )
        for member in confirmation_pool:
            source = member[0].decision.source_unit_id
            if source not in seen_sources:
                seen_sources.add(source)
                confirmations.append(member)
            if len(confirmations) == 2:
                break
        if len(confirmations) != 2:
            # D7 clusters are a reviewer aid, not a precondition for retaining
            # a non-equivalent decision. The decision already carries its
            # blinded A/B candidates, so it remains individually queued.
            continue
        member_identities = [
            (input_.decision.stream_sha256, input_.decision.decision_policy_seq)
            for input_, _decision in ordered
        ]
        priority_digest = (
            "sha256:"
            + sha256(
                canonical_artifact_bytes(
                    [_identity_json(identity) for identity in member_identities]
                )
            ).hexdigest()
        )
        clusters.append(
            {
                "confirmations": [
                    _identity_json(
                        (
                            input_.decision.stream_sha256,
                            input_.decision.decision_policy_seq,
                        )
                    )
                    for input_, _decision in confirmations
                ],
                "mechanical_invariants": {
                    "all_members_non_equivalent": True,
                    "distinct_source_unit_count": len(
                        {input_.decision.source_unit_id for input_, _decision in ordered}
                    ),
                    "member_count": len(ordered),
                    "priority_order_sha256": priority_digest,
                    "three_distinct_source_units": True,
                },
                "member_identities": [_identity_json(identity) for identity in member_identities],
                "priority_rank": representative[0].priority_rank,
                "representative": _identity_json(
                    (
                        representative[0].decision.stream_sha256,
                        representative[0].decision.decision_policy_seq,
                    )
                ),
                "signature": signature,
            }
        )
    return sorted(clusters, key=lambda cluster: cluster["priority_rank"])


def project_phase2_review_evidence(
    inputs: tuple[DecisionProjectionInput, ...],
    *,
    packet_decision_identities: tuple[tuple[str, int], ...],
    teacher_evidence_identity: str,
    blind_seed: str,
) -> bytes:
    """Emit the one checksum-bound ``phase2-review-evidence.json`` root artifact."""
    if not inputs:
        raise Phase2ReviewProjectionError("projection requires packet decisions")
    if (
        not isinstance(teacher_evidence_identity, str)
        or fullmatch(_DIGEST, teacher_evidence_identity) is None
    ):
        raise Phase2ReviewProjectionError("teacher evidence identity must be a sha256 digest")
    if not isinstance(blind_seed, str) or not blind_seed.strip():
        raise Phase2ReviewProjectionError("blind seed must be non-empty")
    expected = tuple(
        _identity(value, "packet decision identity") for value in packet_decision_identities
    )
    if len(expected) != len(set(expected)):
        raise Phase2ReviewProjectionError("packet decision identities must be unique")
    if any(not isinstance(input_, DecisionProjectionInput) for input_ in inputs):
        raise Phase2ReviewProjectionError("projection inputs are invalid")
    actual = tuple(
        (input_.decision.stream_sha256, input_.decision.decision_policy_seq) for input_ in inputs
    )
    if len(actual) != len(set(actual)) or set(actual) != set(expected):
        raise Phase2ReviewProjectionError(
            "projection decisions do not close exactly over packet decisions"
        )
    ranks = sorted(input_.priority_rank for input_ in inputs)
    if ranks != list(range(len(inputs))):
        raise Phase2ReviewProjectionError("priority ranks must be a closed zero-based order")

    blind_commitment = "sha256:" + sha256(blind_seed.encode()).hexdigest()
    ordered = sorted(inputs, key=lambda input_: input_.priority_rank)
    decision_records = [(input_, _decision_json(input_, blind_commitment)) for input_ in ordered]
    clusters = _build_clusters(decision_records, blind_commitment)
    payload = {
        "clusters": clusters,
        "decisions": [record for _input, record in decision_records],
        "format_version": _FORMAT_VERSION,
        "blind_seed_sha256": blind_commitment,
        "mechanical_invariants": {
            "all_packet_decisions_included": True,
            "decision_identity_count": len(decision_records),
            "non_equivalent_decision_count": sum(
                record["comparison"]
                in {TeacherComparison.SEMANTIC_REVIEW.value, TeacherComparison.DISAGREEMENT.value}
                for _input, record in decision_records
            ),
        },
        "teacher_evidence_identity": teacher_evidence_identity,
    }
    return canonical_artifact_bytes(payload)


def _record(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise Phase2ReviewProjectionError(f"{label} must be an object")
    return value


def _string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise Phase2ReviewProjectionError(f"{label} must be a non-empty string")
    return value


def _raw_identity(value: object, label: str) -> tuple[str, int]:
    record = _record(value, label)
    return _identity((record.get("stream_sha256"), record.get("decision_policy_seq")), label)


def _raw_candidate_action(
    candidates: object,
    oracle_action: object,
    comparison: str,
    identity: tuple[str, int],
    blind_commitment: str,
) -> object | None:
    if comparison not in {item.value for item in _NON_EQUIVALENT}:
        if candidates != []:
            raise Phase2ReviewProjectionError("equivalent decision cannot carry blinded candidates")
        return oracle_action if comparison == TeacherComparison.EQUIVALENT.value else None
    if not isinstance(candidates, list) or len(candidates) != 2:
        raise Phase2ReviewProjectionError("non-equivalent decision requires two candidates")
    expected_origins = _origin_order(blind_commitment, identity[0] + "\x00" + str(identity[1]))
    teacher_action: object | None = None
    for index, candidate in enumerate(candidates):
        record = _record(candidate, "candidate")
        candidate_id = record.get("candidate_id")
        if candidate_id != ("A" if index == 0 else "B"):
            raise Phase2ReviewProjectionError("candidate order must be canonical A then B")
        license_ = _record(record.get("license"), "candidate license")
        result = license_.get("result")
        codes = license_.get("codes")
        if result not in _LICENSE_RESULTS or not isinstance(codes, list):
            raise Phase2ReviewProjectionError("candidate license is invalid")
        try:
            normalized_codes = tuple(LicenseBlockCode(code) for code in codes)
        except (TypeError, ValueError) as error:
            raise Phase2ReviewProjectionError("candidate license code is not closed") from error
        if list(code.value for code in normalized_codes) != sorted(
            set(code.value for code in normalized_codes)
        ) or (result == "licensed" and normalized_codes):
            raise Phase2ReviewProjectionError("candidate license codes are inconsistent")
        reveal = _record(record.get("reveal"), "candidate reveal")
        origin = reveal.get("origin")
        provenance = _record(reveal.get("provenance"), "candidate provenance")
        _provenance(provenance, "candidate provenance")
        if origin != expected_origins[index]:
            raise Phase2ReviewProjectionError(
                "candidate A/B order does not match the blind seed commitment"
            )
        action = record.get("action")
        try:
            action_bytes = canonical_artifact_bytes(action)
        except TypeError as error:
            raise Phase2ReviewProjectionError("candidate action is invalid") from error
        oracle_bytes = canonical_artifact_bytes(oracle_action)
        if origin == "oracle" and action_bytes != oracle_bytes:
            raise Phase2ReviewProjectionError("oracle candidate does not match the packet action")
        if origin == "teacher" and action_bytes == oracle_bytes:
            raise Phase2ReviewProjectionError("blinded candidates must be distinct")
        if origin == "teacher":
            teacher_action = action
    if teacher_action is None:  # pragma: no cover - commitment order is exhaustive
        raise Phase2ReviewProjectionError("teacher candidate is missing")
    return teacher_action


def _decision_from_raw(
    value: object, blind_commitment: str
) -> tuple[DecisionEvidence, int, str | None]:
    record = _record(value, "decision")
    identity = _raw_identity(record, "decision identity")
    priority = record.get("priority_rank")
    if isinstance(priority, bool) or not isinstance(priority, int) or priority < 0:
        raise Phase2ReviewProjectionError("decision priority rank is invalid")
    source_unit_id = _string(record.get("source_unit_id"), "source unit id")
    comparison = record.get("comparison")
    if comparison not in {item.value for item in TeacherComparison}:
        raise Phase2ReviewProjectionError("decision comparison is invalid")
    oracle_action = record.get("oracle_action")
    teacher_action = _raw_candidate_action(
        record.get("candidates"),
        oracle_action,
        comparison,
        identity,
        blind_commitment,
    )
    evidence = _record(record.get("review_evidence"), "review evidence")
    cell = _record(evidence.get("trust_cell"), "trust cell")
    route = _record(evidence.get("review_route"), "review route")
    risk_flags = evidence.get("risk_flags")
    reasons = route.get("reasons")
    try:
        decision = DecisionEvidence(
            stream_sha256=identity[0],
            decision_policy_seq=identity[1],
            wave_id=_string(evidence.get("wave_id"), "wave id"),
            cell=TrustCellKey(
                HarnessProtocol(_string(cell.get("protocol"), "trust protocol")),
                CorpusFamily(_string(cell.get("family"), "trust family")),
                FloorClass(_string(cell.get("floor"), "trust floor")),
            ),
            template_id=_string(evidence.get("template_id"), "template id"),
            source_unit_id=source_unit_id,
            oracle_action=oracle_action,
            teacher_action=teacher_action,
            causal_state_class=_string(evidence.get("causal_state_class"), "causal state class"),
            boundary_class=BoundaryClass(_string(evidence.get("boundary_class"), "boundary class")),
            risk_flags=tuple(risk_flags) if isinstance(risk_flags, list) else (),
            idle_boundary=evidence.get("idle_boundary"),
            rollover=evidence.get("rollover"),
        )
        parsed_route = ReviewRoute(
            identity=identity[0] + "\x00" + str(identity[1]),
            review_required=route.get("review_required"),
            mandatory=route.get("mandatory"),
            sample_rate=route.get("sample_rate"),
            reasons=tuple(reasons) if isinstance(reasons, list) else (),
            provisional_label_origin=(
                LabelOrigin(route["provisional_label_origin"])
                if route.get("provisional_label_origin") is not None
                else None
            ),
        )
        parsed_route.validate_for(decision)
    except (Phase2ReviewError, TypeError, ValueError) as error:
        raise Phase2ReviewProjectionError("closed review evidence is invalid") from error
    if decision.comparison.value != comparison:
        raise Phase2ReviewProjectionError("decision comparison does not match canonical actions")
    signature = record.get("cluster_signature")
    if decision.comparison in _NON_EQUIVALENT:
        expected = disagreement_cluster_signature(decision)
        if signature != expected:
            raise Phase2ReviewProjectionError(
                "D7 cluster signature does not match decision evidence"
            )
    elif signature is not None:
        raise Phase2ReviewProjectionError("equivalent decision cannot carry a cluster signature")
    return decision, priority, signature if isinstance(signature, str) else None


def parse_phase2_review_evidence(data: bytes) -> dict[str, object]:
    """Validate the projection's local invariant structure before consumers render it."""
    try:
        value = json.loads(data)
    except (TypeError, ValueError, UnicodeDecodeError) as error:
        raise Phase2ReviewProjectionError("phase2 review evidence is not JSON") from error
    if not isinstance(value, dict) or value.get("format_version") != _FORMAT_VERSION:
        raise Phase2ReviewProjectionError("phase2 review evidence format is unsupported")
    if (
        not isinstance(value.get("teacher_evidence_identity"), str)
        or fullmatch(_DIGEST, value["teacher_evidence_identity"]) is None
    ):
        raise Phase2ReviewProjectionError("teacher evidence identity is invalid")
    blind_commitment = value.get("blind_seed_sha256")
    if not isinstance(blind_commitment, str) or fullmatch(_DIGEST, blind_commitment) is None:
        raise Phase2ReviewProjectionError("blind seed identity is invalid")
    decisions = value.get("decisions")
    clusters = value.get("clusters")
    mechanical = value.get("mechanical_invariants")
    if not isinstance(decisions, list) or not isinstance(clusters, list) or not decisions:
        raise Phase2ReviewProjectionError("phase2 review evidence is incomplete")
    if (
        not isinstance(mechanical, dict)
        or mechanical.get("all_packet_decisions_included") is not True
    ):
        raise Phase2ReviewProjectionError("root mechanical invariants are invalid")
    identities: set[tuple[str, int]] = set()
    non_equivalent: dict[str, set[tuple[str, int]]] = defaultdict(set)
    decisions_by_identity: dict[tuple[str, int], DecisionEvidence] = {}
    priority_by_identity: dict[tuple[str, int], int] = {}
    ranks: list[int] = []
    for decision in decisions:
        parsed, rank, signature = _decision_from_raw(decision, blind_commitment)
        identity = parsed.stream_sha256, parsed.decision_policy_seq
        if identity in identities:
            raise Phase2ReviewProjectionError("decision identities repeat")
        identities.add(identity)
        ranks.append(rank)
        decisions_by_identity[identity] = parsed
        priority_by_identity[identity] = rank
        if signature is not None:
            non_equivalent[signature].add(identity)
    if sorted(ranks) != list(range(len(decisions))):
        raise Phase2ReviewProjectionError("decision priorities are not a closed order")
    if mechanical.get("decision_identity_count") != len(identities) or mechanical.get(
        "non_equivalent_decision_count"
    ) != sum(len(members) for members in non_equivalent.values()):
        raise Phase2ReviewProjectionError("root mechanical counts do not close over decisions")
    clustered: dict[str, set[tuple[str, int]]] = defaultdict(set)
    cluster_priority_ranks: list[int] = []
    for cluster in clusters:
        if not isinstance(cluster, dict) or not isinstance(cluster.get("confirmations"), list):
            raise Phase2ReviewProjectionError("cluster record is invalid")
        confirmations = cluster["confirmations"]
        if len(confirmations) != 2:
            raise Phase2ReviewProjectionError("D7 cluster must have exactly two confirmations")
        invariant = cluster.get("mechanical_invariants")
        if (
            not isinstance(invariant, dict)
            or invariant.get("three_distinct_source_units") is not True
        ):
            raise Phase2ReviewProjectionError("D7 three-source invariant is not proven")
        members = cluster.get("member_identities")
        if not isinstance(members, list):
            raise Phase2ReviewProjectionError("D7 cluster members are missing")
        signature = cluster.get("signature")
        if not isinstance(signature, str) or fullmatch(_DIGEST, signature) is None:
            raise Phase2ReviewProjectionError("D7 cluster signature is invalid")
        if signature in clustered:
            raise Phase2ReviewProjectionError("D7 cluster signatures must be unique")
        member_list = [_raw_identity(member, "cluster member") for member in members]
        member_ids = set(member_list)
        expected_members = sorted(
            non_equivalent.get(signature, set()),
            key=priority_by_identity.__getitem__,
        )
        if member_list != expected_members or member_ids != non_equivalent.get(signature, set()):
            raise Phase2ReviewProjectionError(
                "D7 cluster members do not close over non-equivalent decisions"
            )
        representative = cluster.get("representative")
        confirmation_list = [_raw_identity(item, "confirmation") for item in confirmations]
        confirmation_ids = set(confirmation_list)
        representative_id = _raw_identity(representative, "representative")
        if (
            len(confirmation_ids) != 2
            or representative_id not in member_ids
            or representative_id != member_list[0]
            or not confirmation_ids <= member_ids
            or representative_id in confirmation_ids
        ):
            raise Phase2ReviewProjectionError("D7 representative and confirmations are invalid")
        selected_sources = [
            decisions_by_identity[identity].source_unit_id
            for identity in (representative_id, *confirmation_list)
        ]
        if len(set(selected_sources)) != 3:
            raise Phase2ReviewProjectionError(
                "D7 selections do not use three distinct source units"
            )
        expected_confirmations: list[tuple[str, int]] = []
        seen_sources = {decisions_by_identity[representative_id].source_unit_id}
        confirmation_pool = sorted(
            member_list[1:],
            key=lambda identity: sha256(
                (f"{blind_commitment}|{signature}|{identity[0]}\x00{identity[1]}").encode()
            ).digest(),
        )
        for identity in confirmation_pool:
            source = decisions_by_identity[identity].source_unit_id
            if source not in seen_sources:
                seen_sources.add(source)
                expected_confirmations.append(identity)
            if len(expected_confirmations) == 2:
                break
        if confirmation_list != expected_confirmations:
            raise Phase2ReviewProjectionError(
                "D7 confirmations do not match the blind seed commitment"
            )
        expected_priority_digest = (
            "sha256:"
            + sha256(
                canonical_artifact_bytes([_identity_json(identity) for identity in member_list])
            ).hexdigest()
        )
        if (
            cluster.get("priority_rank") != priority_by_identity[representative_id]
            or invariant.get("priority_order_sha256") != expected_priority_digest
            or invariant.get("member_count") != len(member_ids)
            or invariant.get("distinct_source_unit_count")
            != len({decisions_by_identity[identity].source_unit_id for identity in member_ids})
        ):
            raise Phase2ReviewProjectionError("D7 mechanical source counts do not match members")
        cluster_priority_ranks.append(priority_by_identity[representative_id])
        clustered[signature] = member_ids
    if cluster_priority_ranks != sorted(cluster_priority_ranks):
        raise Phase2ReviewProjectionError("D7 clusters are not in priority order")
    # A signature group without three distinct source units is intentionally
    # absent from `clusters`; only emitted clusters must close over their group.
    return value
