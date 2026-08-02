from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from im.generation.phase2_mark_wave3_selection import build_mark_wave3_selection

ROOT = Path(__file__).resolve().parents[1]


async def test_mark_wave3_selection_is_exact_teacher_blind_and_reviewable() -> None:
    artifact = await build_mark_wave3_selection(repository_root=ROOT)
    report = json.loads(artifact.files["selection-report.json"])
    packet = json.loads(artifact.files["review-packet.json"])
    raw = json.loads(artifact.files["raw-stream-evidence.json"])

    assert (artifact.stream_count, artifact.decision_count) == (37, 158)
    assert report["positive_configuration"] == "positive_b"
    assert report["teacher_agreement_used_as_selection_feature"] is False
    assert report["teacher_exact_matches"] == 37
    assert report["teacher_text_equivalences"] == 10
    assert len(raw["streams"]) == 37
    assert packet["routed_review_decisions"] == artifact.review_count
    assert Counter(
        action["type"]
        for stream in raw["streams"]
        for action in stream["actions"]
    ) == Counter(idle=83, mark=65, respond=10)
