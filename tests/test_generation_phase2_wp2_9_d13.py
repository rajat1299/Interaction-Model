"""WP2-9 D13 reconstruction, the mark correction, and the reserve promotion guard."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest

from im.generation.phase2_wp2_9_d13 import (
    CORRECTED_MARK_TOTALS,
    PUBLISHED_MARK_TOTALS,
    build_mark_correction,
    corrected_mark_decisions,
    d13_authority_index,
    mark_populations,
    reconstruct_mark,
)
from im.generation.phase2_wp2_9_freeze import (
    Wp29PreflightError,
    assert_promotable,
    load_wp2_9_candidates,
)

ROOT = Path(__file__).resolve().parents[1]


def test_mark_populations_partition_the_accepted_pool() -> None:
    selected, reserve, mark = mark_populations(ROOT)
    assert not selected & reserve
    assert selected | reserve == set(mark)
    assert len(selected) == 106
    assert len(reserve) == 2
    assert sum(mark[digest]["decision_count"] for digest in selected) == 500
    assert sum(mark[digest]["decision_count"] for digest in reserve) == 24


def test_mark_origin_reconstructs_to_the_corrected_totals() -> None:
    _records, summary = reconstruct_mark(ROOT)
    assert summary["selected"] == CORRECTED_MARK_TOTALS
    assert summary["selected"] != PUBLISHED_MARK_TOTALS
    # The reserve is derived independently and is never folded into the 500.
    assert summary["reserve"] == {"oracle_teacher_agreement": 24, "total": 24}


def test_the_fifty_two_corrected_decisions_never_become_human() -> None:
    """Regression: the published 285/215 counted these as human without individual evidence."""
    affected = corrected_mark_decisions(ROOT)
    assert len(affected) == 52
    for record in affected:
        assert record.label_origin == "oracle_teacher_agreement"
        assert record.comparison == "equivalent"
        # Agreement is the only basis; no owner record exists for any of them.
        assert record.owner_evidence is None
        assert record.execution.startswith("mark-wave-1")


def test_correction_sidecar_binds_the_evidence_and_claims_no_material_change() -> None:
    files = build_mark_correction(ROOT)
    payload = json.loads(files["mark-label-origin-correction.json"])
    assert payload["affected_decision_count"] == 52
    assert payload["corrected_totals"] == CORRECTED_MARK_TOTALS
    assert payload["published_totals_superseded"] == PUBLISHED_MARK_TOTALS
    assert len(payload["decisions"]) == 52
    for decision in payload["decisions"]:
        assert decision["comparison"] == "equivalent"
        assert decision["individually_owner_reviewed"] is False
        # Full-action equivalence evidence, not merely a verdict.
        assert decision["oracle_action"] == decision["teacher_action"]
    assert payload["wave1_disposition"]["sha256"].startswith("sha256:")
    assert "no training byte changed" in payload["no_material_change"]
    assert b"SHA256SUMS" not in files["SHA256SUMS"]


def test_promotion_guard_blocks_reserve_streams_carrying_setup_decisions() -> None:
    preflight = load_wp2_9_candidates(ROOT)
    authorised = d13_authority_index(ROOT)
    unauthorised = [
        stream
        for stream in preflight.streams
        if any(
            (stream.stream_sha256, decision.decision_policy_seq) not in authorised
            for decision in stream.decisions
        )
    ]
    # The 44 idle top-up setup decisions live in twelve reserve streams and have no authority.
    assert unauthorised, "expected the unauthorised idle top-up setup decisions to be present"
    with pytest.raises(Wp29PreflightError, match="promotion blocked"):
        assert_promotable(preflight, [unauthorised[0].stream_sha256], root=ROOT)


def test_promotion_guard_admits_a_fully_authorised_stream() -> None:
    preflight = load_wp2_9_candidates(ROOT)
    authorised = d13_authority_index(ROOT)
    clean = next(
        stream
        for stream in preflight.streams
        if all(
            (stream.stream_sha256, decision.decision_policy_seq) in authorised
            for decision in stream.decisions
        )
    )
    assert_promotable(preflight, [clean.stream_sha256], root=ROOT)


def _binding() -> frozenset[str]:
    from im.generation.phase2_wp2_9_d13 import load_binding_selection

    return load_binding_selection(ROOT)


def test_trust_completion_covers_exactly_the_recorded_gap() -> None:
    """Exactly the 308 response/idle decisions are completed; any new gap must fail closed."""
    from im.generation.phase2_wp2_9_d13 import (
        TRUST_COMPLETION_AUTHORITY,
        TRUST_COMPLETION_CLUSTERS,
        TRUST_COMPLETION_COUNT,
        TRUST_VERSION,
        emit_d13,
    )

    emitted = emit_d13(ROOT, binding=_binding())
    completions = emitted["completions"]
    assert len(completions) == TRUST_COMPLETION_COUNT == 308
    assert {item["cluster"] for item in completions} == TRUST_COMPLETION_CLUSTERS
    counts = Counter(item["cluster"] for item in completions)
    assert counts == {"response": 60, "idle": 248}
    # Identities are bound individually, not by cluster totals.
    assert len({(i["stream_sha256"], i["decision_policy_seq"]) for i in completions}) == 308
    amended = [
        record
        for record in emitted["records"]
        if record["trust_version_authority"] == TRUST_COMPLETION_AUTHORITY
    ]
    assert len(amended) == 308
    assert all(record["trust_matrix_version"] == TRUST_VERSION for record in amended)
    # Everything else must still be bound to a source artifact.
    assert all(
        record["trust_version_authority"] == "recorded_by_source_artifact"
        for record in emitted["records"]
        if record["cluster"] not in TRUST_COMPLETION_CLUSTERS
    )


def test_d13_closes_with_two_thousand_unique_records() -> None:
    from im.generation.phase2_wp2_9_d13 import emit_d13

    emitted = emit_d13(ROOT, binding=_binding())
    records = emitted["records"]
    assert len(records) == 2_000
    assert len({(r["stream_sha256"], r["decision_policy_seq"]) for r in records}) == 2_000
    assert emitted["totals"] == {"human": 512, "oracle_teacher_agreement": 1_488}
    assert emitted["totals"].get("teacher_auto_trusted", 0) == 0
    assert all(
        record["trust_matrix_version"] and record["review_batch_id"] for record in records
    )
    registry = emitted["batch_registry"]
    assert all(record["review_batch_id"] in registry for record in records)
    # An agreement row never borrows a human-review batch.
    assert not [
        record
        for record in records
        if record["label_origin"] == "oracle_teacher_agreement"
        and record["authority_kind"]
        in {"owner-review-record", "mandatory-review-evidence", "cluster-owner-review"}
    ]
