from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from im.generation.phase2_review_projection import parse_phase2_review_evidence
from im.generation.phase2_timer_wave0 import load_timer_wave0_inputs
from im.generation.phase2_timer_wave1 import _execute, _packet, _streams
from im.generation.phase2_timer_wave1_review import (
    DEFAULT_TIMER_WAVE1_EXECUTION,
    build_timer_wave1_review_packet,
)


@pytest.mark.asyncio
async def test_completed_wave1_builder_retains_individual_blinded_review_items() -> None:
    repository_root = Path(__file__).resolve().parents[1]
    registry = load_timer_wave0_inputs(
        approved_root=repository_root / "review" / "phase1" / "approved",
        selection_contract_path=repository_root / "spec" / "phase2-selection-v1.json",
    )
    with TemporaryDirectory(prefix="test-phase2-timer-wave1-review-") as temporary:
        executed = await _execute(_streams(registry), Path(temporary), repository_root)
        plan = _packet(executed, repository_root)
        packet = build_timer_wave1_review_packet(
            executed,
            plan.files,
            execution_root=DEFAULT_TIMER_WAVE1_EXECUTION,
            repository_root=repository_root,
        )

    evidence = parse_phase2_review_evidence(packet.files["phase2-review-evidence.json"])
    source_index = json.loads(packet.files["source-index.json"])
    checksums = packet.files["SHA256SUMS"].decode("ascii")

    assert len(evidence["decisions"]) == 82
    assert packet.review_count == 74
    assert packet.non_equivalent_count == 26
    assert packet.individual_queue_count == 26
    assert evidence["clusters"] == []
    assert sum(len(row["candidates"]) == 2 for row in evidence["decisions"]) == 26
    assert len(source_index["sources"]) == 12
    assert "provider/comparison.json" in packet.files
    assert "provider/shards/0000/output.jsonl" in packet.files
    assert not any("disposition" in path for path in packet.files)
    assert all(f"  {path}\n" in checksums for path in packet.files if path != "SHA256SUMS")
