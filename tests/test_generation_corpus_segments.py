from __future__ import annotations

from pathlib import Path

import pytest

from im.assets import AssetRegistry, ReviewDecision, ReviewRecord, build_seed_registry
from im.assets.model import artifact_digest, canonical_artifact_bytes
from im.generation.corpus_segments import CorpusSegmentCandidate, CorpusSegmentError
from im.generation.pilot_catalog import build_c5_pilot_programs
from im.generation.scenarios import execute_scenario
from im.schema.events import StateCheckpointEvent
from im.serialize import parse_event


def _reviewed_registry() -> AssetRegistry:
    seeds = build_seed_registry()
    return AssetRegistry(
        assets=seeds.assets,
        reviews=tuple(
            ReviewRecord(
                asset_id=asset.asset_id,
                content_sha256=asset.content_sha256,
                reviewer_id="test-reviewer",
                reviewed_at_utc="2026-07-14T18:00:00Z",
                decision=ReviewDecision.APPROVED,
            )
            for asset in seeds.assets
        ),
    )


@pytest.mark.asyncio
async def test_candidate_selects_every_decision_from_one_complete_later_segment(
    tmp_path: Path,
) -> None:
    program = dict(build_c5_pilot_programs(_reviewed_registry()))["c5-rollover"]
    generated = await execute_scenario(
        program,
        session_id="s_corpus_segment",
        directory=tmp_path / "rollover",
        repository_root=Path(__file__).parents[1],
    )

    candidate = CorpusSegmentCandidate(generated, 1, "g7-rollover-short-v1")

    checkpoint = parse_event(candidate.segment.policy_bytes.splitlines()[0])
    assert candidate.parent is generated
    assert candidate.selected_call_indices == (2, 3, 4)
    assert candidate.selected_actions == generated.program.actions[1:4]
    assert candidate.decision_count == 3
    assert not candidate.within_target_band
    assert isinstance(checkpoint, StateCheckpointEvent)
    assert candidate.checkpoint_seq == checkpoint.seq
    assert candidate.previous_segment_hash == checkpoint.payload.segment.previous_segment_hash
    assert all(
        candidate.segment.policy_bytes.startswith(decision.prefix_bytes)
        for decision in candidate.selected_decisions
    )
    assert candidate.canonical_bytes == canonical_artifact_bytes(candidate.as_json_object())
    assert candidate.sha256 == artifact_digest(candidate.as_json_object())
    assert "parent" not in candidate.as_json_object()

    with pytest.raises(CorpusSegmentError, match="later segment"):
        CorpusSegmentCandidate(generated, 0, "g7-rollover-short-v1")
    with pytest.raises(CorpusSegmentError, match="stable lowercase"):
        CorpusSegmentCandidate(generated, 1, "G7")
    with pytest.raises(CorpusSegmentError, match="no captured decisions"):
        CorpusSegmentCandidate(generated, 3, "g7-rollover-empty-v1")
