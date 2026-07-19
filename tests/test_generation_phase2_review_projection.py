from __future__ import annotations

import pytest

from im.assets.model import CorpusFamily, canonical_artifact_bytes
from im.generation.phase2_review import (
    BoundaryClass,
    DecisionEvidence,
    FloorClass,
    ReviewRoute,
    TrustCellKey,
)
from im.generation.phase2_review_projection import (
    CandidateLicense,
    DecisionProjectionInput,
    Phase2ReviewProjectionError,
    parse_phase2_review_evidence,
    project_phase2_review_evidence,
)
from im.probes.harness.models import HarnessProtocol
from im.schema.common import LicenseBlockCode


def _input(index: int, source: str, priority: int) -> DecisionProjectionInput:
    decision = DecisionEvidence(
        stream_sha256=f"sha256:{index:064x}",
        decision_policy_seq=index,
        wave_id="sentinel-0",
        cell=TrustCellKey(
            HarnessProtocol.GENERATION,
            CorpusFamily.NEUTRAL_TYPING,
            FloorClass.CLOSED,
        ),
        template_id="same-template",
        source_unit_id=source,
        oracle_action={"type": "idle", "reason": "no_trigger", "related_event_id": None},
        teacher_action={"type": "nudge", "fire_event_id": "e_000001"},
        causal_state_class="same-causal-state",
        boundary_class=BoundaryClass.ORDINARY,
        risk_flags=("oracle_teacher_non_equivalence",),
    )
    return DecisionProjectionInput(
        decision=decision,
        route=ReviewRoute(
            identity=decision.identity,
            review_required=True,
            mandatory=True,
            sample_rate=1.0,
            reasons=("teacher_oracle_disagreement",),
            provisional_label_origin=None,
        ),
        oracle_license=CandidateLicense("licensed", ()),
        teacher_license=CandidateLicense("blocked", (LicenseBlockCode.REASON_MISMATCH,)),
        oracle_provenance={"request_sha256": f"sha256:{(100 + index):064x}"},
        teacher_provenance={"request_sha256": f"sha256:{(200 + index):064x}"},
        priority_rank=priority,
    )


def _project(inputs: tuple[DecisionProjectionInput, ...]) -> bytes:
    identities = tuple(
        (item.decision.stream_sha256, item.decision.decision_policy_seq) for item in inputs
    )
    return project_phase2_review_evidence(
        inputs,
        packet_decision_identities=identities,
        teacher_evidence_identity=f"sha256:{'d' * 64}",
        blind_seed="phase2-review-blind-v1",
    )


def test_projection_is_canonical_and_clusters_three_distinct_sources() -> None:
    inputs = (_input(3, "source-c", 2), _input(1, "source-a", 0), _input(2, "source-b", 1))

    first = _project(inputs)
    second = _project(tuple(reversed(inputs)))

    assert first == second
    payload = parse_phase2_review_evidence(first)
    assert [item["priority_rank"] for item in payload["decisions"]] == [0, 1, 2]
    assert len(payload["clusters"]) == 1
    cluster = payload["clusters"][0]
    assert cluster["representative"]["stream_sha256"] == f"sha256:{1:064x}"
    assert {item["stream_sha256"] for item in cluster["confirmations"]} == {
        f"sha256:{2:064x}",
        f"sha256:{3:064x}",
    }
    assert cluster["mechanical_invariants"]["three_distinct_source_units"] is True
    assert len(cluster["confirmations"]) == 2


def test_projection_fails_closed_for_missing_packet_decision_or_source_reuse() -> None:
    inputs = (_input(1, "source-a", 0), _input(2, "source-b", 1), _input(3, "source-a", 2))
    identities = tuple(
        (item.decision.stream_sha256, item.decision.decision_policy_seq) for item in inputs
    )

    with pytest.raises(Phase2ReviewProjectionError, match="three distinct source units"):
        project_phase2_review_evidence(
            inputs,
            packet_decision_identities=identities,
            teacher_evidence_identity=f"sha256:{'d' * 64}",
            blind_seed="phase2-review-blind-v1",
        )

    with pytest.raises(Phase2ReviewProjectionError, match="do not close"):
        project_phase2_review_evidence(
            (_input(1, "source-a", 0), _input(2, "source-b", 1), _input(3, "source-c", 2)),
            packet_decision_identities=identities[:-1],
            teacher_evidence_identity=f"sha256:{'d' * 64}",
            blind_seed="phase2-review-blind-v1",
        )


def test_projection_parser_rejects_mutated_invariant_report() -> None:
    payload = parse_phase2_review_evidence(
        _project((_input(1, "source-a", 0), _input(2, "source-b", 1), _input(3, "source-c", 2)))
    )
    payload["clusters"][0]["mechanical_invariants"]["three_distinct_source_units"] = False
    mutated = canonical_artifact_bytes(payload)

    with pytest.raises(Phase2ReviewProjectionError, match="three-source invariant"):
        parse_phase2_review_evidence(mutated)


def test_projection_parser_recomputes_root_counts_and_rejects_duplicate_clusters() -> None:
    payload = parse_phase2_review_evidence(
        _project((_input(1, "source-a", 0), _input(2, "source-b", 1), _input(3, "source-c", 2)))
    )
    payload["mechanical_invariants"]["decision_identity_count"] = 99
    with pytest.raises(Phase2ReviewProjectionError, match="root mechanical counts"):
        parse_phase2_review_evidence(canonical_artifact_bytes(payload))

    payload = parse_phase2_review_evidence(
        _project((_input(1, "source-a", 0), _input(2, "source-b", 1), _input(3, "source-c", 2)))
    )
    payload["clusters"].append(payload["clusters"][0])
    with pytest.raises(Phase2ReviewProjectionError, match="signatures must be unique"):
        parse_phase2_review_evidence(canonical_artifact_bytes(payload))


def test_projection_parser_rejects_mutated_blind_order_and_confirmation_order() -> None:
    inputs = (_input(1, "source-a", 0), _input(2, "source-b", 1), _input(3, "source-c", 2))
    payload = parse_phase2_review_evidence(_project(inputs))
    payload["decisions"][0]["candidates"].reverse()
    with pytest.raises(Phase2ReviewProjectionError, match="canonical A then B"):
        parse_phase2_review_evidence(canonical_artifact_bytes(payload))

    payload = parse_phase2_review_evidence(_project(inputs))
    (
        payload["decisions"][0]["candidates"][0]["reveal"],
        payload["decisions"][0]["candidates"][1]["reveal"],
    ) = (
        payload["decisions"][0]["candidates"][1]["reveal"],
        payload["decisions"][0]["candidates"][0]["reveal"],
    )
    with pytest.raises(Phase2ReviewProjectionError, match="blind seed commitment"):
        parse_phase2_review_evidence(canonical_artifact_bytes(payload))

    payload = parse_phase2_review_evidence(_project(inputs))
    payload["clusters"][0]["confirmations"].reverse()
    with pytest.raises(Phase2ReviewProjectionError, match="confirmations do not match"):
        parse_phase2_review_evidence(canonical_artifact_bytes(payload))
