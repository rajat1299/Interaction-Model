from __future__ import annotations

import json
from dataclasses import replace
from hashlib import sha256

import pytest

from im.assets.model import CorpusFamily, canonical_artifact_bytes
from im.generation.phase2_review import (
    BoundaryClass,
    DecisionEvidence,
    DisagreementCategory,
    FloorClass,
    LabelAuditMetadata,
    LabelOrigin,
    Phase2ReviewError,
    ReservoirRecord,
    ReviewRoute,
    TeacherComparison,
    TrustCellKey,
    TrustCellStatus,
    TrustReviewEvidence,
    TrustState,
    disagreement_cluster_signature,
    evaluate_trust_cell,
    export_reservoir_jsonl,
    route_wave,
)
from im.probes.harness.models import HarnessProtocol


def _action(action_type: str, reason: str | None, index: int) -> dict[str, object]:
    event_id = f"e_{index:06d}"
    if action_type == "idle":
        related = (
            event_id if reason in {"awaiting_tool", "awaiting_opening", "already_handled"} else None
        )
        return {"type": "idle", "reason": reason, "related_event_id": related}
    if action_type == "respond":
        return {"type": "respond", "reply_to_event_id": event_id, "text": "Acknowledged."}
    if action_type == "schedule":
        return {
            "type": "schedule",
            "instruction": {
                "event_id": event_id,
                "start_utf16": 0,
                "end_utf16": 4,
                "text": "ping",
            },
            "interval_ms": 1_000,
            "message": "ping",
        }
    if action_type == "skip":
        return {"type": "skip", "target_event_id": event_id, "reason": reason}
    if action_type == "nudge":
        return {"type": "nudge", "fire_event_id": event_id}
    raise AssertionError(f"test action helper does not support {action_type}")


def _decision(index: int, **overrides: object) -> DecisionEvidence:
    action_type = str(overrides.pop("action_type", "idle"))
    action_reason = overrides.pop("action_reason", "no_trigger")
    teacher_action_type = overrides.pop("teacher_action_type", action_type)
    teacher_action_reason = overrides.pop("teacher_action_reason", action_reason)
    expected_comparison = overrides.pop("comparison", TeacherComparison.EQUIVALENT)
    oracle_action = overrides.pop(
        "oracle_action",
        _action(action_type, action_reason, index),  # type: ignore[arg-type]
    )
    teacher_action = overrides.pop(
        "teacher_action",
        (
            None
            if teacher_action_type is None
            else _action(str(teacher_action_type), teacher_action_reason, index)  # type: ignore[arg-type]
        ),
    )
    values: dict[str, object] = {
        "stream_sha256": f"sha256:{index:064x}",
        "decision_policy_seq": index,
        "wave_id": "sentinel-0",
        "cell": TrustCellKey(
            HarnessProtocol.GENERATION,
            CorpusFamily.NEUTRAL_TYPING,
            FloorClass.CLOSED,
        ),
        "template_id": f"template-{index % 3}",
        "source_unit_id": f"source-{index % 5}",
        "oracle_action": oracle_action,
        "teacher_action": teacher_action,
        "causal_state_class": "ordinary",
        "boundary_class": BoundaryClass.ORDINARY,
    }
    values.update(overrides)
    decision = DecisionEvidence(**values)  # type: ignore[arg-type]
    assert decision.comparison is expected_comparison
    return decision


def _disagreement(index: int, **overrides: object) -> DecisionEvidence:
    return _decision(
        index,
        teacher_action_type="nudge",
        teacher_action_reason=None,
        comparison=TeacherComparison.DISAGREEMENT,
        risk_flags=("oracle_teacher_non_equivalence",),
        **overrides,
    )


def test_order_zero_sentinel_boundaries_all_route_to_human_review() -> None:
    sentinels = (
        _decision(
            1,
            action_reason="typing_active",
            idle_boundary="partial_instruction",
            boundary_class=BoundaryClass.PARTIAL_INSTRUCTION,
        ),
        _decision(
            2,
            action_reason="awaiting_opening",
            boundary_class=BoundaryClass.ACTIVE_FLOOR_RESPONSE,
            risk_flags=("active_floor_response_boundary",),
        ),
        _decision(
            3,
            action_type="respond",
            action_reason=None,
            teacher_action_type="respond",
            teacher_action_reason=None,
            cell=TrustCellKey(
                HarnessProtocol.GENERATION,
                CorpusFamily.NEUTRAL_TYPING,
                FloorClass.OPEN,
            ),
            boundary_class=BoundaryClass.ACTIVE_FLOOR_RESPONSE,
            risk_flags=("active_floor_response_boundary",),
        ),
        _decision(
            4,
            action_type="schedule",
            action_reason=None,
            teacher_action_type="schedule",
            teacher_action_reason=None,
            cell=TrustCellKey(
                HarnessProtocol.GENERATION,
                CorpusFamily.TIMER_NORMAL,
                FloorClass.CLOSED,
            ),
            boundary_class=BoundaryClass.SCHEDULE_SIMILAR_DISTINCT,
            risk_flags=("schedule_semantic_duplicate_boundary",),
        ),
        _decision(
            5,
            action_reason="already_handled",
            boundary_class=BoundaryClass.SCHEDULE_SEMANTIC_DUPLICATE,
            risk_flags=("schedule_semantic_duplicate_boundary",),
        ),
        _decision(
            6,
            action_type="skip",
            action_reason="superseded_query",
            teacher_action_type="skip",
            teacher_action_reason="superseded_query",
            boundary_class=BoundaryClass.LOOKUP_REFRESH_SUPERSEDED,
            risk_flags=("skip_reason_selection",),
        ),
        _decision(
            7,
            action_type="skip",
            action_reason="stale_tool_result",
            teacher_action_type="skip",
            teacher_action_reason="stale_tool_result",
            boundary_class=BoundaryClass.LOOKUP_ABANDONED_STALE,
            risk_flags=("skip_reason_selection",),
        ),
        _decision(
            8,
            action_reason="ambiguous",
            boundary_class=BoundaryClass.AMBIGUOUS_CANCEL,
            risk_flags=("cancel_semantic_referent_resolution",),
        ),
    )

    routes = route_wave(sentinels, {}, sampling_seed="sentinel-route-v1")

    assert len(routes) == 8
    assert all(route.review_required and route.mandatory for route in routes)
    assert all(route.provisional_label_origin is None for route in routes)


def test_teacher_comparison_is_derived_and_cannot_bypass_review() -> None:
    reason_mismatch = _decision(
        20,
        teacher_action_reason="typing_active",
        comparison=TeacherComparison.DISAGREEMENT,
        risk_flags=("oracle_teacher_non_equivalence",),
    )
    missing = _decision(
        21,
        teacher_action=None,
        comparison=TeacherComparison.MISSING,
    )

    routes = route_wave((reason_mismatch, missing), {}, sampling_seed="comparison-v1")

    assert [decision.comparison for decision in (reason_mismatch, missing)] == [
        TeacherComparison.DISAGREEMENT,
        TeacherComparison.MISSING,
    ]
    assert all(route.mandatory for route in routes)


def test_review_route_closes_flags_rate_reasons_and_origin() -> None:
    required = {
        "identity": "decision-1",
        "review_required": True,
        "mandatory": True,
        "sample_rate": 1.0,
        "reasons": ("mandatory_action",),
        "provisional_label_origin": None,
    }
    ReviewRoute(**required)
    ReviewRoute(
        "decision-2",
        False,
        False,
        0.25,
        (),
        LabelOrigin.ORACLE_TEACHER_AGREEMENT,
    )

    with pytest.raises(Phase2ReviewError, match="sample_rate"):
        ReviewRoute(**{**required, "sample_rate": 2.5})
    with pytest.raises(Phase2ReviewError, match="mandatory"):
        ReviewRoute(**{**required, "review_required": False})
    with pytest.raises(Phase2ReviewError, match="sampled review routes"):
        ReviewRoute(**{**required, "mandatory": False, "reasons": ()})
    with pytest.raises(Phase2ReviewError, match="unique non-empty"):
        ReviewRoute(**{**required, "reasons": ("same", "same")})
    with pytest.raises(Phase2ReviewError, match="closed router vocabulary"):
        ReviewRoute(**{**required, "reasons": ("invented_reason",)})
    with pytest.raises(Phase2ReviewError, match="positive rate"):
        ReviewRoute(
            "decision-3",
            True,
            False,
            0.0,
            ("stratified_sample",),
            None,
        )

    ordinary = _decision(3)
    impossible = ReviewRoute(
        ordinary.identity,
        True,
        True,
        1.0,
        ("teacher_oracle_disagreement",),
        None,
    )
    with pytest.raises(Phase2ReviewError, match="canonical router"):
        impossible.validate_for(ordinary)


def test_non_equivalent_human_review_requires_a_disposition() -> None:
    with pytest.raises(Phase2ReviewError, match="disposition"):
        TrustReviewEvidence(
            _disagreement(1),
            None,
            "phase2-v1",
            "window-1",
            True,
            "review-1",
        )


def test_non_qualifying_dispositions_do_not_promote_a_cell() -> None:
    evidence = tuple(
        TrustReviewEvidence(
            _disagreement(index),
            DisagreementCategory.ASSET_AMBIGUITY,
            "phase2-v1",
            "window-1",
            True,
            "review-1",
        )
        for index in range(1, 31)
    )

    result = evaluate_trust_cell(
        TrustCellStatus(evidence[0].decision.cell),
        evidence,
        matrix_version="phase2-v1",
        qualification_window_id="window-1",
    )

    assert result.state is TrustState.UNCLEARED


def test_cleared_cell_audit_is_deterministic_and_stratified() -> None:
    decisions = tuple(_decision(index) for index in range(1, 31))
    cell = decisions[0].cell
    status = {cell: TrustCellStatus(cell, TrustState.CLEARED)}

    first = route_wave(decisions, status, sampling_seed="audit-v1")
    second = route_wave(decisions, status, sampling_seed="audit-v1")
    selected = [
        decision for decision, route in zip(decisions, first, strict=True) if route.review_required
    ]

    assert first == second
    assert len(selected) == 3
    assert len({(item.template_id, item.source_unit_id) for item in selected}) == 3


def test_teacher_error_locks_cell_and_contract_gap_halts_family() -> None:
    decision = _disagreement(1)
    status = TrustCellStatus(decision.cell)
    teacher_error = TrustReviewEvidence(
        decision,
        DisagreementCategory.TEACHER_ERROR,
        "phase2-v1",
        "window-1",
        True,
        "review-1",
    )

    locked = evaluate_trust_cell(
        status,
        (teacher_error,),
        matrix_version="phase2-v1",
        qualification_window_id="window-1",
    )
    assert locked == TrustCellStatus(decision.cell, TrustState.UNCLEARED, True)
    assert (
        evaluate_trust_cell(
            locked,
            tuple(
                TrustReviewEvidence(
                    _decision(index),
                    None,
                    "phase2-v1",
                    "window-1",
                    True,
                    "review-1",
                )
                for index in range(30, 60)
            ),
            matrix_version="phase2-v1",
            qualification_window_id="window-1",
        )
        == locked
    )

    contract_gap = TrustReviewEvidence(
        decision,
        DisagreementCategory.CONTRACT_GAP,
        "phase2-v1",
        "window-1",
        True,
        "review-1",
    )
    with pytest.raises(Phase2ReviewError, match="halts"):
        evaluate_trust_cell(
            status,
            (contract_gap,),
            matrix_version="phase2-v1",
            qualification_window_id="window-1",
        )


def test_promotion_requires_thirty_decisions_five_sources_three_templates() -> None:
    decisions = tuple(_decision(index) for index in range(1, 31))
    status = TrustCellStatus(decisions[0].cell)
    evidence = tuple(
        TrustReviewEvidence(
            decision,
            None,
            "phase2-v1",
            "window-1",
            True,
            "review-1",
        )
        for decision in decisions
    )

    assert (
        evaluate_trust_cell(
            status,
            evidence,
            matrix_version="phase2-v1",
            qualification_window_id="window-1",
        ).state
        is TrustState.CLEARED
    )


def test_promotion_rejects_duplicate_review_records() -> None:
    decisions = tuple(_decision(index) for index in range(1, 16))
    evidence = tuple(
        TrustReviewEvidence(
            decision,
            None,
            "phase2-v1",
            "window-1",
            True,
            "review-1",
        )
        for decision in decisions
    )

    with pytest.raises(Phase2ReviewError, match="repeats"):
        evaluate_trust_cell(
            TrustCellStatus(decisions[0].cell),
            (*evidence, *evidence),
            matrix_version="phase2-v1",
            qualification_window_id="window-1",
        )


def test_promotion_counts_only_human_reviewed_current_window_evidence() -> None:
    decisions = tuple(_decision(index) for index in range(1, 31))
    status = TrustCellStatus(decisions[0].cell)
    unreviewed = tuple(
        TrustReviewEvidence(
            decision,
            None,
            "phase2-v1",
            "window-2",
            False,
            None,
        )
        for decision in decisions
    )
    old_oracle_error = TrustReviewEvidence(
        _disagreement(1_000),
        DisagreementCategory.ORACLE_ERROR,
        "phase2-v1",
        "window-1",
        True,
        "review-old",
    )

    result = evaluate_trust_cell(
        status,
        (old_oracle_error, *unreviewed),
        matrix_version="phase2-v1",
        qualification_window_id="window-2",
    )

    assert result.state is TrustState.UNCLEARED


def test_teacher_error_lock_survives_a_repair_window_change() -> None:
    decision = _disagreement(1)
    teacher_error = TrustReviewEvidence(
        decision,
        DisagreementCategory.TEACHER_ERROR,
        "phase2-v1",
        "window-before-repair",
        True,
        "review-old",
    )

    result = evaluate_trust_cell(
        TrustCellStatus(decision.cell),
        (teacher_error,),
        matrix_version="phase2-v1",
        qualification_window_id="window-after-repair",
    )

    assert result.locked_uncleared is True


def test_closed_review_vocabularies_fail_at_construction() -> None:
    decision = _decision(1)
    with pytest.raises(Phase2ReviewError, match="category"):
        TrustReviewEvidence(
            decision,
            "not-a-category",  # type: ignore[arg-type]
            "phase2-v1",
            "window-1",
            True,
            "review-1",
        )
    with pytest.raises(Phase2ReviewError, match="label origin"):
        LabelAuditMetadata(
            "not-an-origin",  # type: ignore[arg-type]
            "phase2-v1",
            "review-1",
        )
    with pytest.raises(Phase2ReviewError, match="response-floor"):
        _decision(
            2,
            action_type="respond",
            action_reason=None,
            teacher_action_type="respond",
            teacher_action_reason=None,
            cell=TrustCellKey(
                HarnessProtocol.GENERATION,
                CorpusFamily.NEUTRAL_TYPING,
                FloorClass.OPEN,
            ),
        )


def test_permanent_boundary_cannot_promote_and_contract_gap_halts_sibling_cell() -> None:
    ordinary = tuple(_decision(index) for index in range(1, 31))
    cell = ordinary[0].cell
    permanent = _decision(
        99,
        action_reason="awaiting_opening",
        cell=TrustCellKey(
            HarnessProtocol.GENERATION,
            CorpusFamily.NEUTRAL_TYPING,
            FloorClass.OWNED,
        ),
        boundary_class=BoundaryClass.ACTIVE_FLOOR_RESPONSE,
        risk_flags=("active_floor_response_boundary",),
    )
    permanent_evidence = tuple(
        TrustReviewEvidence(
            _decision(
                100 + index,
                action_reason="awaiting_opening",
                cell=permanent.cell,
                boundary_class=BoundaryClass.ACTIVE_FLOOR_RESPONSE,
                risk_flags=("active_floor_response_boundary",),
            ),
            None,
            "phase2-v1",
            "window-1",
            True,
            "review-1",
        )
        for index in range(30)
    )
    assert (
        evaluate_trust_cell(
            TrustCellStatus(permanent.cell),
            permanent_evidence,
            matrix_version="phase2-v1",
            qualification_window_id="window-1",
        ).state
        is TrustState.UNCLEARED
    )

    sibling_gap = TrustReviewEvidence(
        _decision(
            999,
            action_reason="awaiting_opening",
            teacher_action_type="respond",
            teacher_action_reason=None,
            comparison=TeacherComparison.DISAGREEMENT,
            cell=permanent.cell,
            boundary_class=BoundaryClass.ACTIVE_FLOOR_RESPONSE,
            risk_flags=(
                "active_floor_response_boundary",
                "oracle_teacher_non_equivalence",
            ),
        ),
        DisagreementCategory.CONTRACT_GAP,
        "phase2-v1",
        "window-1",
        True,
        "review-1",
    )
    ordinary_evidence = tuple(
        TrustReviewEvidence(
            decision,
            None,
            "phase2-v1",
            "window-1",
            True,
            "review-1",
        )
        for decision in ordinary
    )
    with pytest.raises(Phase2ReviewError, match="halts"):
        evaluate_trust_cell(
            TrustCellStatus(cell),
            (sibling_gap, *ordinary_evidence),
            matrix_version="phase2-v1",
            qualification_window_id="window-1",
        )
    locked = TrustCellStatus(cell, TrustState.UNCLEARED, True)
    with pytest.raises(Phase2ReviewError, match="halts"):
        evaluate_trust_cell(
            locked,
            (sibling_gap,),
            matrix_version="phase2-v1",
            qualification_window_id="window-1",
        )


def test_cluster_signature_and_reservoir_preserve_full_boundary_evidence() -> None:
    decision = _decision(
        9,
        action_type="skip",
        action_reason="stale_tool_result",
        teacher_action_type="skip",
        teacher_action_reason="superseded_query",
        comparison=TeacherComparison.DISAGREEMENT,
        boundary_class=BoundaryClass.LOOKUP_REFRESH_SUPERSEDED,
        risk_flags=("oracle_teacher_non_equivalence", "skip_reason_selection"),
        causal_state_class="refresh-after-request",
    )
    changed = _decision(
        10,
        action_type="skip",
        action_reason="stale_tool_result",
        teacher_action_type="skip",
        teacher_action_reason="superseded_query",
        comparison=TeacherComparison.DISAGREEMENT,
        boundary_class=BoundaryClass.LOOKUP_ABANDONED_STALE,
        risk_flags=("oracle_teacher_non_equivalence", "skip_reason_selection"),
        causal_state_class="refresh-after-request",
    )
    assert disagreement_cluster_signature(decision) != disagreement_cluster_signature(changed)
    assert disagreement_cluster_signature(decision) != disagreement_cluster_signature(
        replace(decision, rollover=True)
    )
    typing = _decision(30, action_reason="typing_active")
    assert disagreement_cluster_signature(typing) != disagreement_cluster_signature(
        replace(typing, idle_boundary="lexical_boundary")
    )

    semantic_respond = _decision(
        41,
        oracle_action={"type": "respond", "reply_to_event_id": "e_000001", "text": "A"},
        teacher_action={"type": "respond", "reply_to_event_id": "e_000001", "text": "B"},
        comparison=TeacherComparison.SEMANTIC_REVIEW,
        template_id="semantic-template",
        boundary_class=BoundaryClass.ACTIVE_FLOOR_RESPONSE,
        risk_flags=("active_floor_response_boundary", "oracle_teacher_non_equivalence"),
    )
    wording_only = _decision(
        42,
        oracle_action={"type": "respond", "reply_to_event_id": "e_000001", "text": "C"},
        teacher_action={"type": "respond", "reply_to_event_id": "e_000001", "text": "D"},
        comparison=TeacherComparison.SEMANTIC_REVIEW,
        template_id="semantic-template",
        boundary_class=BoundaryClass.ACTIVE_FLOOR_RESPONSE,
        risk_flags=("active_floor_response_boundary", "oracle_teacher_non_equivalence"),
    )
    different_reference = _decision(
        43,
        oracle_action={"type": "respond", "reply_to_event_id": "e_000001", "text": "A"},
        teacher_action={"type": "respond", "reply_to_event_id": "e_000002", "text": "B"},
        comparison=TeacherComparison.DISAGREEMENT,
        template_id="semantic-template",
        boundary_class=BoundaryClass.ACTIVE_FLOOR_RESPONSE,
        risk_flags=("active_floor_response_boundary", "oracle_teacher_non_equivalence"),
    )
    assert disagreement_cluster_signature(semantic_respond) == disagreement_cluster_signature(
        wording_only
    )
    assert disagreement_cluster_signature(semantic_respond) != disagreement_cluster_signature(
        different_reference
    )

    integrate_a = _decision(
        44,
        oracle_action={"type": "integrate", "result_event_id": "e_000003", "text": "A"},
        teacher_action={"type": "integrate", "result_event_id": "e_000003", "text": "B"},
        comparison=TeacherComparison.SEMANTIC_REVIEW,
        template_id="integrate-template",
        risk_flags=("oracle_teacher_non_equivalence",),
    )
    integrate_b = _decision(
        45,
        oracle_action={"type": "integrate", "result_event_id": "e_000004", "text": "A"},
        teacher_action={"type": "integrate", "result_event_id": "e_000004", "text": "B"},
        comparison=TeacherComparison.SEMANTIC_REVIEW,
        template_id="integrate-template",
        risk_flags=("oracle_teacher_non_equivalence",),
    )
    assert disagreement_cluster_signature(integrate_a) != disagreement_cluster_signature(
        integrate_b
    )

    prefix = tuple(
        {
            "v": 1,
            "id": f"e_{seq:06d}",
            "seq": seq,
            "dt_ms": 0,
            "source": "user",
            "kind": "annotation",
            "payload": {
                "text": "refresh the lookup" if seq == 9 else f"event-{seq}",
            },
        }
        for seq in range(10)
    )
    prefix_sha256 = f"sha256:{sha256(canonical_artifact_bytes(list(prefix))).hexdigest()}"
    record = ReservoirRecord(
        decision.stream_sha256,
        decision.decision_policy_seq,
        prefix,
        prefix_sha256,
        {"type": "skip", "target_event_id": "e_000001", "reason": "superseded_query"},
        {"type": "skip", "target_event_id": "e_000001", "reason": "stale_tool_result"},
        DisagreementCategory.TEACHER_ERROR,
        "Refresh superseded the prior query.",
        decision.cell,
        decision.risk_flags,
    )
    payload = json.loads(export_reservoir_jsonl((record,)))
    assert payload["source"] == "teacher_oracle_adjudication"
    assert payload["direct_dpo_eligibility"] is False
    assert payload["policy_prefix"]

    truncated = prefix[1:]
    truncated_sha256 = f"sha256:{sha256(canonical_artifact_bytes(list(truncated))).hexdigest()}"
    with pytest.raises(Phase2ReviewError, match="complete"):
        ReservoirRecord(
            decision.stream_sha256,
            decision.decision_policy_seq,
            truncated,
            truncated_sha256,
            record.chosen_action,
            record.rejected_action,
            record.disagreement_category,
            record.human_reason,
            record.trust_cell,
            record.risk_flags,
        )


def test_canonical_action_and_event_adapters_guard_reservoir_exports() -> None:
    with pytest.raises(Phase2ReviewError, match="oracle action"):
        _decision(1, oracle_action={"type": "skip", "reason": "superseded_query"})

    decision = _disagreement(1)
    valid_event = {
        "v": 1,
        "id": "e_000000",
        "seq": 0,
        "dt_ms": 0,
        "source": "user",
        "kind": "annotation",
        "payload": {"text": "check"},
    }
    event_digest = f"sha256:{sha256(canonical_artifact_bytes([valid_event])).hexdigest()}"
    common = (
        decision.stream_sha256,
        0,
        (valid_event,),
        event_digest,
    )
    with pytest.raises(Phase2ReviewError, match="chosen action"):
        ReservoirRecord(
            *common,
            {"type": "skip", "reason": "superseded_query"},
            {"type": "nudge", "fire_event_id": "e_000000"},
            DisagreementCategory.TEACHER_ERROR,
            "malformed chosen action",
            decision.cell,
            decision.risk_flags,
        )
    with pytest.raises(Phase2ReviewError, match="non-canonical event"):
        ReservoirRecord(
            decision.stream_sha256,
            0,
            ({"seq": 0},),
            event_digest,
            {"type": "idle", "reason": "no_trigger", "related_event_id": None},
            {"type": "nudge", "fire_event_id": "e_000000"},
            DisagreementCategory.TEACHER_ERROR,
            "malformed prefix event",
            decision.cell,
            decision.risk_flags,
        )
