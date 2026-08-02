from __future__ import annotations

import json
from pathlib import Path

import pytest

from im.generation.phase2_lookup_wave0 import load_lookup_wave0_inputs
from im.generation.phase2_mark_wave0 import (
    build_mark_wave0_packet,
    build_mark_wave0_programs,
    execute_mark_wave0,
)


@pytest.mark.asyncio
async def test_mark_wave0_is_complete_and_owner_reviewable(tmp_path: Path) -> None:
    programs = build_mark_wave0_programs(load_lookup_wave0_inputs())
    executed = await execute_mark_wave0(
        programs,
        directory=tmp_path / "runtime",
        repository_root=Path(__file__).resolve().parents[1],
    )
    first = build_mark_wave0_packet(executed)
    second = build_mark_wave0_packet(executed)
    evidence = json.loads(first["phase2-review-evidence.json"])
    expansion = json.loads(first["template-expansion.json"])
    source_index = json.loads(first["source-index.json"])

    assert first == second
    assert len(programs) == len(executed) == 8
    assert len(evidence["decisions"]) == 14
    assert expansion["rendered_frames"] == [
        "Mark every occurrence of animal labels.",
        "Switch from animal labels to color labels.",
    ]
    assert expansion["actions"] == [
        {"reason": "no_trigger", "related_event_id": None, "type": "idle"},
        {"reason": "no_trigger", "related_event_id": None, "type": "idle"},
    ]
    assert all(
        source["checkpoint"] is None
        and source["master_seed"].startswith("phase2-mark-wave0:")
        for source in source_index["sources"]
    )
    assert first["review-packet.json"]
    assert first["source-index.json"]
