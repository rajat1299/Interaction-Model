from __future__ import annotations

import json
from pathlib import Path

from im.generation.phase2_response_wave3_selection import (
    build_response_wave3_selection,
)


def test_response_wave3_selection_is_seeded_and_pair_complete() -> None:
    root = Path(__file__).resolve().parents[1]
    selected = build_response_wave3_selection(repository_root=root)
    report = json.loads(selected.files["selection-report.json"])

    assert (selected.pair_count, selected.decision_count) == (6, 12)
    assert report["teacher_agreement_used_as_selection_feature"] is False
    assert report["payload_substitution_count"] == 0
