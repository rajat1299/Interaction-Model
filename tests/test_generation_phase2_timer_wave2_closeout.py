from __future__ import annotations

import json
from pathlib import Path

from im.generation.phase2_timer_wave2_closeout import build_timer_wave2_closeout

ROOT = Path(__file__).resolve().parents[1]


def test_timer_wave2_closeout_is_complete_and_honest() -> None:
    result = build_timer_wave2_closeout(repository_root=ROOT)

    assert result.accepted_stream_count == 46
    assert result.decision_count == 698
    assert result.exact_teacher_count == 502
    assert result.human_repair_count == 219

    closure = json.loads(result.files["review-closure.json"])
    assert closure["status"] == "closed"
    assert closure["d2"] == {
        "mandatory_route_count": 653,
        "review_complete_count": 664,
        "review_required_count": 664,
        "status": "passed",
    }
    assert closure["selection"]["teacher_agreement_used_as_feature"] is False
    assert closure["wave3"]["status"] == "targeted_top_up_required"

    labels = json.loads(result.files["label-audit.json"])["decisions"]
    assert sum(row["comparison"] == "equivalent" for row in labels) == 479
    assert sum(row["comparison"] == "non_equivalent" for row in labels) == 23
    assert sum(row["comparison"] == "not_reused_changed_causal_prefix" for row in labels) == 196
    assert sum(row["teacher_evidence"]["status"] == "not_reused" for row in labels) == 196

    eligibility = json.loads(result.files["whole-stream-eligibility.json"])
    assert len(eligibility["streams"]) == 46
    assert all(
        all(stream["gates"].values()) and stream["rejection_disposition"] is None
        for stream in eligibility["streams"]
    )

    coverage = json.loads(result.files["coverage-and-distribution.json"])
    assert coverage["generated_vs_accepted_equal"] is True
    assert coverage["rejected_stream_count"] == 0
    assert coverage["reserve_feasibility"]["status"] == "sufficient"
    assert all(row["target_satisfied"] for row in coverage["families"])

    reservoir = result.files["phase4-reservoir.jsonl"].splitlines()
    assert len(reservoir) == 23
    assert all(json.loads(line)["direct_dpo_eligibility"] is False for line in reservoir)


def test_timer_wave2_closeout_is_deterministic() -> None:
    first = build_timer_wave2_closeout(repository_root=ROOT)
    second = build_timer_wave2_closeout(repository_root=ROOT)

    assert first.files == second.files
