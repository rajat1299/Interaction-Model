from __future__ import annotations

import json
from pathlib import Path

from im.generation.phase2_mark_closeout import build_mark_closeout

ROOT = Path(__file__).resolve().parents[1]


def test_mark_closeout_binds_owner_approval_and_exact_targets() -> None:
    artifact = build_mark_closeout(repository_root=ROOT)
    report = json.loads(artifact.files["exit-report.json"])
    decisions = artifact.files["owner-review-decisions.jsonl"].splitlines()

    assert (artifact.accepted_decisions, artifact.reserve_decisions) == (524, 24)
    assert artifact.reviewed_decisions == len(decisions) == 87
    assert report["status"] == "closed"
    assert report["final_selection"] == {
        "decision_count": 500,
        "stream_count": 106,
        "whole_streams_only": True,
    }
    assert report["label_origin"] == {
        "human": 285,
        "oracle_teacher_agreement": 215,
        "teacher_auto_trusted": 0,
        "total": 500,
    }
    assert all(row["target_satisfied"] for row in report["family_coverage"])
    assert report["accepted_pool"]["wave2_wave3_reuse"] == {
        "decision_count": 135,
        "stream_count": 16,
    }
    assert report["teacher_agreement_used_as_selection_feature"] is False
