from __future__ import annotations

import json
from pathlib import Path

from im.generation.phase2_response_closeout import build_response_closeout


def test_response_closeout_has_exact_reviewed_floor_pairs() -> None:
    root = Path(__file__).resolve().parents[1]
    files = build_response_closeout(repository_root=root)
    report = json.loads(files["exit-report.json"])
    streams = json.loads(files["selected-raw-streams.json"])["streams"]

    assert report["status"] == "closed"
    assert report["accepted_pool"]["action_counts"] == {"idle": 30, "respond": 30}
    assert report["payload_substitution_count"] == 0
    assert report["label_origin"]["teacher_auto_trusted"] == 0
    assert len(streams) == 60
