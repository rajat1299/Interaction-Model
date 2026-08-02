from __future__ import annotations

import json
from pathlib import Path

import pytest

from im.generation.phase2_mark_wave2_selection import (
    build_mark_wave2_selection,
    selected_logical_stream_ids,
)

_ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.asyncio
async def test_mark_wave2_selection_is_exact_and_reviewable() -> None:
    artifact = await build_mark_wave2_selection(repository_root=_ROOT)
    report = json.loads(artifact.files["selection-report.json"])
    source_index = json.loads(artifact.files["source-index.json"])
    review = json.loads(artifact.files["phase2-review-evidence.json"])

    assert (artifact.stream_count, artifact.decision_count, artifact.pending_review_count) == (
        47,
        266,
        107,
    )
    assert set(report["selected_logical_stream_ids"]) == selected_logical_stream_ids()
    assert report["teacher_agreement_used_as_selection_feature"] is False
    assert report["action_counts"] == {
        "mark_activation_positive": {"idle": 63, "mark": 87, "respond": 4},
        "mark_lifecycle_negative": {"idle": 75, "mark": 33, "respond": 4},
    }
    assert len(review["decisions"]) == 266
    assert (
        sum(
            row["review_evidence"]["review_route"]["review_required"] for row in review["decisions"]
        )
        == 122
    )
    assert len(artifact.files["prior-owner-decisions.jsonl"].splitlines()) == 15
    assert all(
        isinstance(source["master_seed"], str) and source["master_seed"]
        for source in source_index["sources"]
    )
