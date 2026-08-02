from __future__ import annotations

import json
from pathlib import Path

import pytest

from im.generation.phase2_response_wave0 import build_response_wave0_packet


@pytest.mark.asyncio
async def test_response_wave0_is_complete_and_owner_reviewable() -> None:
    root = Path(__file__).resolve().parents[1]
    first = await build_response_wave0_packet(repository_root=root)
    second = await build_response_wave0_packet(repository_root=root)
    evidence = json.loads(first["phase2-review-evidence.json"])
    allocation = json.loads(first["response-allocation.json"])
    source_index = json.loads(first["source-index.json"])

    assert first == second
    assert len(evidence["decisions"]) == 8
    assert allocation["neutral_typing_revision_pause"] == [1, *range(6, 35)]
    assert allocation["wave0_ordinals"] == [1, 14, 15, 25]
    assert allocation["response_payload_substitution_count"] == 0
    assert len(source_index["sources"]) == 8
    assert all(
        isinstance(source["master_seed"], str) and source["master_seed"]
        for source in source_index["sources"]
    )
    assert first["review-packet.json"]
