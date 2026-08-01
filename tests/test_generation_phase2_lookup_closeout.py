from __future__ import annotations

import json

from im.generation.phase2_lookup_closeout import build_lookup_closeout


def test_lookup_closeout_has_no_wave3_deficit() -> None:
    closeout = build_lookup_closeout()
    report = json.loads(closeout.files["exit-report.json"])
    reservoir = closeout.files["phase4-reservoir.jsonl"].splitlines()

    assert closeout.stream_count == 172
    assert closeout.decision_count == 848
    assert closeout.reserve_decisions == 208
    assert report["wave_3"]["decision_count"] == 0
    assert report["skip_review"] == {
        "decision_count": 103,
        "reason_counts": {
            "stale_tool_result": 89,
            "superseded_query": 14,
        },
        "reviewed_count": 103,
        "reviewed_fraction": 1.0,
        "status": "complete",
    }
    assert report["label_origin"]["teacher_auto_trusted"] == 0
    assert len(reservoir) == 96
