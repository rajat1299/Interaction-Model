from __future__ import annotations

from dataclasses import dataclass

from im.assets.model import artifact_digest
from im.generation.phase2_replay_allocation import (
    AllocationResult,
    choose_deterministic_selection,
    choose_feasibility_witness,
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

    result = choose_deterministic_selection(
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
        supervised_token_maximum=120,
        classify=lambda candidate: (
            candidate.task_family,
            candidate.length_band,
            candidate.turn_kind,
        ),
        token_count=lambda candidate: candidate.assistant_token_count,
        rank=lambda candidate: candidate.completion_id,
    )

    assert isinstance(result, AllocationResult)
    assert result.supervised_token_total == 109
    selected_multi_by_band = {
        band: sum(
            candidate.length_band == band and candidate.turn_kind == "multi"
            for candidate in result.selected
        )
        for band in ("short", "medium", "long")
    }
    assert selected_multi_by_band == {"short": 1, "medium": 1, "long": 1}


def test_allocator_uses_tokens_only_to_reach_the_hard_floor() -> None:
    candidates = (
        _Candidate("a", "family", "short", "single", 1),
        _Candidate("b", "family", "short", "single", 2),
        _Candidate("c", "family", "short", "single", 20),
    )

    result = choose_deterministic_selection(
        candidates,
        family_quotas={"family": 2},
        replay_bands=(
            ("short", (1, 20, 2)),
            ("medium", (21, 30, 0)),
            ("long", (31, 40, 0)),
        ),
        multi_turn_target=0,
        target_examples=2,
        supervised_token_minimum=21,
        supervised_token_maximum=30,
        classify=lambda candidate: (
            candidate.task_family,
            candidate.length_band,
            candidate.turn_kind,
        ),
        token_count=lambda candidate: candidate.assistant_token_count,
        rank=lambda candidate: candidate.completion_id,
    )

    assert isinstance(result, AllocationResult)
    assert tuple(candidate.completion_id for candidate in result.selected) == ("a", "c")
    assert result.supervised_token_total == 21


def test_feasibility_witness_proves_constraints_without_binding_seed_order() -> None:
    candidates = (
        _Candidate("a", "family", "short", "single", 1),
        _Candidate("b", "family", "short", "single", 20),
        _Candidate("c", "family", "medium", "multi", 30),
    )

    result = choose_feasibility_witness(
        candidates,
        family_quotas={"family": 2},
        replay_bands=(
            ("short", (1, 20, 1)),
            ("medium", (21, 30, 1)),
            ("long", (31, 40, 0)),
        ),
        multi_turn_target=1,
        target_examples=2,
        supervised_token_minimum=50,
        supervised_token_maximum=50,
        classify=lambda candidate: (
            candidate.task_family,
            candidate.length_band,
            candidate.turn_kind,
        ),
        token_count=lambda candidate: candidate.assistant_token_count,
        rank=lambda candidate: candidate.completion_id,
    )

    assert isinstance(result, AllocationResult)
    assert {candidate.completion_id for candidate in result.selected} == {"b", "c"}
    assert result.supervised_token_total == 50


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
