from __future__ import annotations

import json
from collections import Counter
from hashlib import sha256
from pathlib import Path

import pytest

from im.assets import Split
from im.generation.phase2_timer_wave0 import (
    build_timer_wave0_packet,
    build_timer_wave0_programs,
    execute_timer_wave0,
    load_timer_wave0_inputs,
)


def test_timer_wave0_builds_the_closed_train_inventory() -> None:
    programs = build_timer_wave0_programs(load_timer_wave0_inputs())

    assert len(programs) == 12
    assert len({item.spec.logical_stream_id for item in programs}) == 12
    assert Counter(item.spec.family.value for item in programs) == {
        "timer_creation_normal_fire": 4,
        "timer_cancel_quoting_stale_fire": 4,
        "timer_contention_backpressure": 4,
    }
    assert all(item.program.bundle.split is Split.TRAIN for item in programs)
    assert all(item.program.timing_plan.seed.split is Split.TRAIN for item in programs)


@pytest.mark.asyncio
async def test_timer_wave0_executes_and_projects_only_selected_checkpoint_segments(
    tmp_path: Path,
) -> None:
    programs = build_timer_wave0_programs(load_timer_wave0_inputs())
    executed = await execute_timer_wave0(
        programs,
        directory=tmp_path / "runtime",
        repository_root=Path(__file__).resolve().parents[1],
    )
    first = build_timer_wave0_packet(executed)
    second = build_timer_wave0_packet(executed)
    manifest = json.loads(first["manifest.json"])
    evidence = json.loads(first["phase2-review-evidence.json"])
    packet = json.loads(first["review-packet.json"])

    assert first == second
    assert len(manifest["streams"]) == 12
    assert packet["api_call_performed"] is False
    assert packet["stream_review_count"] == 12
    assert packet["tranche_two_gate"] == {
        "blocks": [],
        "required_additions": [],
        "status": "complete",
    }
    assert len(evidence["decisions"]) == 138
    assert evidence["mechanical_invariants"] == {
        "all_packet_decisions_included": True,
        "decision_identity_count": 138,
        "non_equivalent_decision_count": 0,
    }
    for item in executed:
        actual = {
            decision["decision_policy_seq"]
            for decision in evidence["decisions"]
            if decision["stream_sha256"] == item.generated.stream.sha256
        }
        expected = (
            set(range(len(item.generated.program.actions)))
            if item.selected_segment is None
            else {index - 1 for index in item.selected_segment.selected_call_indices}
        )
        assert actual == expected

    checksum_rows = first["SHA256SUMS"].decode("ascii").splitlines()
    assert checksum_rows == [
        f"{sha256(first[name]).hexdigest()}  {name}" for name in sorted(set(first) - {"SHA256SUMS"})
    ]
