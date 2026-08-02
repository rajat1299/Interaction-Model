"""Focused WP2-9 tests: input binding, reference manifest, seed normalization, preflight."""

from __future__ import annotations

import json
from pathlib import Path
from unittest import mock

import pytest

from im.generation import phase2_wp2_9_recovery as wp2_9_recovery
from im.generation.phase2_wp2_9_freeze import load_wp2_9_candidates, preflight_report
from im.generation.phase2_wp2_9_recovery import (
    Wp29RecoveryError,
    recover_policy_stream_evidence,
)
from im.generation.phase2_wp2_9_replay import (
    CONTROLLING_INPUTS,
    WORKING_SELECTION_SEED,
    Wp29ReplayError,
    build_reference_manifest,
    normalize_candidate_pool,
    verify_controlling_inputs,
)

ROOT = Path(__file__).resolve().parents[1]


def test_controlling_inputs_verify_against_the_bound_digests() -> None:
    assert {
        "review/phase1/approved/registry.jsonl",
        "review/phase1/approved/train-seal.json",
        "review/phase1/approved/dev-seal.json",
        "review/phase1/approved/test-seal.json",
        "review/phase1/approved/demo-seal.json",
        "review/phase2/response-tranche-selection/SHA256SUMS",
        "review/phase2/dev-response-approved/SHA256SUMS",
        "review/phase2/dev-response-tranche-2-approved/SHA256SUMS",
    } <= set(CONTROLLING_INPUTS)
    verified = verify_controlling_inputs(ROOT)
    assert set(verified) == set(CONTROLLING_INPUTS)
    for path, digest in CONTROLLING_INPUTS.items():
        assert verified[path] == f"sha256:{digest}"


def test_controlling_input_drift_fails_closed(tmp_path: Path) -> None:
    for relative in (
        "spec",
        "review/phase2/wp2-6-exit",
        "review/phase2/replay-public-fallback-v1",
        "review/phase2/dev-gate-c-closeout",
    ):
        (tmp_path / relative).mkdir(parents=True, exist_ok=True)
    (tmp_path / "spec/phase2-selection-v3.json").write_bytes(b"{}")
    with pytest.raises(Wp29ReplayError):
        verify_controlling_inputs(tmp_path)


def test_every_required_reference_category_is_populated() -> None:
    reference = build_reference_manifest(ROOT)
    assert reference.sha256.startswith("sha256:")
    for category, values in reference.manifest.items():
        assert values, f"{category} must not be empty"
    # The TEST scan interpretation is recorded, not implied.
    assert "sealed heldout TEST asset corpus" in reference.provenance["test_scan_interpretation"]


def test_normalization_changes_only_the_selection_seed() -> None:
    normalized, lineage = normalize_candidate_pool(ROOT)
    source = (ROOT / "review/phase2/replay-public-fallback-v1/candidate-pool.jsonl").read_text()
    original = {
        json.loads(line)["completion_id"]: json.loads(line)
        for line in source.splitlines()
        if line.strip()
    }
    assert len(normalized) == len(original) == 1_250
    assert {row["selection_seed"] for row in normalized} == {WORKING_SELECTION_SEED}
    for row in normalized:
        before = original[row["completion_id"]]
        assert {k: v for k, v in row.items() if k != "selection_seed"} == {
            k: v for k, v in before.items() if k != "selection_seed"
        }
    # Every historical seed survives in lineage, including the two superseded ones.
    seeds = {item["original_selection_seed"] for item in lineage}
    assert seeds == {
        "phase2-replay-public-fallback-v1",
        "phase2-replay-selection-v1",
        "phase2-replay-terminal-recovery-v2",
    }


def test_interaction_preflight_admits_only_fully_bound_streams() -> None:
    preflight = load_wp2_9_candidates(ROOT, report_only=True)
    report = preflight_report(preflight)
    assert report["teacher_derived_selection_features_used"] is False
    assert len(preflight.streams) + len(preflight.blocked) == 505
    for stream in preflight.streams:
        assert stream.source_unit_id
        assert stream.template_id
        assert stream.asset_ids
        assert len(stream.decisions) == stream.stream_length
        assert all(decision.action.get("type") for decision in stream.decisions)
        assert all(
            decision.floor_class in {"closed", "open", "owned"} for decision in stream.decisions
        )
    # Every blocked stream names its exact unsatisfied binding rather than being dropped silently.
    assert all(item["reason"] for item in preflight.blocked)


def test_interaction_preflight_admits_the_whole_wp2_6_pool_after_recovery() -> None:
    """Strict mode must now succeed: WP29-2 recovery removed every blocked stream."""
    preflight = load_wp2_9_candidates(ROOT)
    assert len(preflight.streams) == 505
    assert preflight.decision_count == 2_777
    assert preflight.blocked == ()
    validation = preflight.recovery_validation
    assert validation["disagreement_count"] == 0
    assert validation["compared_decision_count"] > 0
    assert set(validation["floor_class_coverage"]) == {"closed", "open", "owned"}


def test_recovered_evidence_must_reproduce_the_real_sidecars_exactly() -> None:
    """One disagreement against a regenerated sidecar stops the recovery."""
    recovery = recover_policy_stream_evidence(ROOT)
    assert recovery.validation["disagreement_count"] == 0
    try:
        recover_policy_stream_evidence.cache_clear()
        with mock.patch.object(
            wp2_9_recovery, "_floor_class", lambda events, action_type: "closed"
        ):
            with pytest.raises(Wp29RecoveryError):
                recover_policy_stream_evidence(ROOT)
    finally:
        recover_policy_stream_evidence.cache_clear()


def test_prose_need_source_units_derive_from_the_recorded_pair_identity() -> None:
    preflight = load_wp2_9_candidates(ROOT, report_only=True)
    derived = [
        stream
        for stream in preflight.streams
        if stream.source_unit_origin == "derived_from_pair_id"
    ]
    assert len(derived) == 24
    # Twelve pairs, each arm sharing exactly one unit, asset set, and template.
    by_unit: dict[str, list[object]] = {}
    for stream in derived:
        by_unit.setdefault(stream.source_unit_id, []).append(stream)
    assert len(by_unit) == 12
    for arms in by_unit.values():
        assert len(arms) == 2
        assert len({arm.asset_ids for arm in arms}) == 1
        assert len({arm.template_id for arm in arms}) == 1
