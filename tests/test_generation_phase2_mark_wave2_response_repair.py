from __future__ import annotations

import json
from pathlib import Path

import pytest

from im.generation.phase2_mark_wave2_response_repair import (
    build_mark_wave2_response_repair,
)

_ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.asyncio
async def test_mark_wave2_response_repair_is_scoped_and_natural() -> None:
    files = await build_mark_wave2_response_repair(repository_root=_ROOT)
    review = json.loads(files["phase2-review-evidence.json"])
    raw = json.loads(files["raw-stream-evidence.json"])
    supersession = json.loads(files["supersession.json"])

    assert len(raw["streams"]) == len(review["decisions"]) == 16
    assert len(supersession["replacements"]) == 16
    assert len({row["source_unit_id"] for row in review["decisions"]}) == 8
    assert all(
        row["review_evidence"]["review_route"]["review_required"]
        for row in review["decisions"]
    )
    assert {stream["actions"][0]["type"] for stream in raw["streams"]} == {
        "idle",
        "respond",
    }
    prompts = {stream["frames"][0]["sampler"]["text"] for stream in raw["streams"]}
    assert len(prompts) == 8
    assert not any(
        phrase in prompt
        for prompt in prompts
        for phrase in ("inventory marks", "comparison chooses", "correct value is")
    )
    assert supersession["unchanged_action_labels"] is True
