from __future__ import annotations

from dataclasses import dataclass

from im.assets.model import artifact_digest
from im.generation.phase2_replay_allocation import (
    AllocationResult,
    choose_maximum_token_selection,
    review_rounds_sha256,
)


@dataclass(frozen=True, slots=True)
class _Candidate:
    completion_id: str
    task_family: str
    length_band: str
    turn_kind: str
    assistant_token_count: int


def test_allocator_compares_multi_turn_availability_across_all_replay_bands() -> None:
    candidates = (
        _Candidate("short-multi-a", "family", "short", "multi", 10),
        _Candidate("short-multi-b", "family", "short", "multi", 9),
        _Candidate("short-single-a", "family", "short", "single", 9),
        _Candidate("short-single-b", "family", "short", "single", 8),
        _Candidate("medium-multi-a", "family", "medium", "multi", 20),
        _Candidate("medium-multi-b", "family", "medium", "multi", 19),
        _Candidate("medium-single-a", "family", "medium", "single", 12),
        _Candidate("medium-single-b", "family", "medium", "single", 11),
        _Candidate("long-multi-a", "family", "long", "multi", 30),
        _Candidate("long-multi-b", "family", "long", "multi", 29),
        _Candidate("long-single-a", "family", "long", "single", 28),
        _Candidate("long-single-b", "family", "long", "single", 27),
    )

    result = choose_maximum_token_selection(
        candidates,
        family_quotas={"family": 6},
        replay_bands=(
            ("short", (1, 10, 2)),
            ("medium", (11, 20, 2)),
            ("long", (21, 30, 2)),
        ),
        multi_turn_target=3,
        target_examples=6,
        supervised_token_minimum=0,
        classify=lambda candidate: (
            candidate.task_family,
            candidate.length_band,
            candidate.turn_kind,
        ),
        token_count=lambda candidate: candidate.assistant_token_count,
        rank=lambda candidate: candidate.completion_id,
    )

    assert isinstance(result, AllocationResult)
    assert result.supervised_token_total == 114
    selected_multi_by_band = {
        band: sum(
            candidate.length_band == band and candidate.turn_kind == "multi"
            for candidate in result.selected
        )
        for band in ("short", "medium", "long")
    }
    assert selected_multi_by_band == {"short": 0, "medium": 2, "long": 1}


def test_review_history_identity_uses_the_project_canonical_digest() -> None:
    first = (("sha256:" + "1" * 64, {"completion-b": False, "completion-a": True}),)
    reordered = (("sha256:" + "1" * 64, {"completion-a": True, "completion-b": False}),)

    assert review_rounds_sha256(first) == review_rounds_sha256(reordered)
    assert review_rounds_sha256(first) == artifact_digest(
        [
            {
                "review_plan_sha256": "sha256:" + "1" * 64,
                "decisions": {"completion-b": False, "completion-a": True},
            }
        ]
    )
