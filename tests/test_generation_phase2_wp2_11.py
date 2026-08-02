from __future__ import annotations

import json
from pathlib import Path

from im.generation.phase2_wp2_11_closeout import build_phase2_closeout

ROOT = Path(__file__).resolve().parents[1]


def test_wp2_11_closeout_rebuilds_from_frozen_phase2_evidence() -> None:
    files = build_phase2_closeout(repository_root=ROOT)
    report = json.loads(files["phase-report.json"])
    reserve = json.loads(files["interaction-reserve.json"])
    reservoir = json.loads(files["reservoir-inventory.json"])
    budget = json.loads(files["budget-and-spend.json"])

    assert report["corpora"]["interaction"]["decision_count"] == 2_000
    assert report["corpora"]["interaction"]["action_counts"]["idle"] == 1_000
    assert report["corpora"]["replay"]["row_count"] == 1_000
    assert reserve["decision_count"] == 250
    assert reserve["stream_count"] == 109
    assert reserve["disjoint_from_binding_selection"] is True
    assert reserve["objective_vector"]["candidate_order_rank_sum"] == 381_481
    assert all(
        proof["status"] == "Optimal" and proof["mip_gap"] == 0 for proof in reserve["proofs"]
    )
    assert reservoir["record_count"] == 119
    assert reservoir["direct_dpo_eligibility"] is False
    assert (
        budget["owner_hours"]["lines"]["interaction_corpus_review"]["full_actual_hours"]
        == "not_recorded"
    )
    assert report["git_tag"]["status"] == "pending_commit"
