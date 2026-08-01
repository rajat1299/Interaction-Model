from __future__ import annotations

import json
from collections import Counter
from hashlib import sha256
from pathlib import Path

import pytest

from im.assets import CorpusFamily, Split
from im.generation.phase2_lookup_wave0 import (
    build_lookup_wave0_packet,
    build_lookup_wave0_programs,
    execute_lookup_wave0,
    load_lookup_wave0_inputs,
)
from im.schema.actions import SkipAction, SkipReason


@pytest.mark.asyncio
async def test_lookup_wave0_is_the_closed_offline_train_proof(tmp_path: Path) -> None:
    programs = build_lookup_wave0_programs(load_lookup_wave0_inputs())

    assert len(programs) == 8
    assert len({item.spec.logical_stream_id for item in programs}) == 8
    assert Counter(item.spec.family for item in programs) == {
        CorpusFamily.LOOKUP_LIVE: 2,
        CorpusFamily.LOOKUP_DUPLICATE: 4,
        CorpusFamily.LOOKUP_STALE: 2,
    }
    assert all(item.program.bundle.split is Split.TRAIN for item in programs)

    executed = await execute_lookup_wave0(
        programs,
        directory=tmp_path / "runtime",
        repository_root=Path(__file__).resolve().parents[1],
    )
    first = build_lookup_wave0_packet(executed)
    second = build_lookup_wave0_packet(executed)
    manifest = json.loads(first["manifest.json"])
    source_index = json.loads(first["source-index.json"])
    evidence = json.loads(first["phase2-review-evidence.json"])
    packet = json.loads(first["review-packet.json"])
    selected_skips = Counter(
        action.reason
        for item in executed
        for action in (
            item.generated.program.actions
            if item.selected_segment is None
            else item.selected_segment.selected_actions
        )
        if isinstance(action, SkipAction)
    )

    assert first == second
    assert len(manifest["streams"]) == 8
    assert len(source_index["sources"]) == 8
    assert all(
        f"reviewer/{stream['stream_sha256'].removeprefix('sha256:')}/sidecar.json"
        in first
        for stream in manifest["streams"]
    )
    assert all(
        f"reviewer/{stream['stream_sha256'].removeprefix('sha256:')}/runtime-ledger.json"
        in first
        for stream in manifest["streams"]
    )
    assert packet["api_call_performed"] is False
    assert packet["stream_review_count"] == 8
    assert len(evidence["decisions"]) == 76
    expected_identities = {
        (item.generated.stream.sha256, decision.observed_policy_seq)
        for item in executed
        for decision in item.generated.sidecar.decisions
        if item.selected_segment is None
        or decision.call_index in item.selected_segment.selected_call_indices
    }
    assert {
        (decision["stream_sha256"], decision["decision_policy_seq"])
        for decision in evidence["decisions"]
    } == expected_identities
    assert selected_skips == {
        SkipReason.SUPERSEDED_QUERY: 2,
        SkipReason.STALE_TOOL_RESULT: 14,
    }
    assert evidence["mechanical_invariants"] == {
        "all_packet_decisions_included": True,
        "decision_identity_count": 76,
        "non_equivalent_decision_count": 0,
    }
    assert first["SHA256SUMS"].decode().splitlines() == [
        f"{sha256(first[name]).hexdigest()}  {name}"
        for name in sorted(set(first) - {"SHA256SUMS"})
    ]
