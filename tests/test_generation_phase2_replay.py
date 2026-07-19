from __future__ import annotations

from collections import Counter

import pytest

from im.generation.phase2_replay import (
    COMPOSITION_QUOTAS,
    ReplaySelectionDeficitError,
    filter_replay_candidates,
    select_replay_candidates,
)

SEED = "phase2-replay-test-seed"


def _candidate(index: int, **overrides: object) -> dict[str, object]:
    messages = overrides.pop(
        "messages",
        [
            {"role": "user", "content": f"Explain topic {index}."},
            {"role": "assistant", "content": "A concise, accurate explanation."},
        ],
    )
    value: dict[str, object] = {
        "candidate_id": f"candidate-{index:04d}",
        "task_family": "stable-knowledge explanation",
        "messages": messages,
        "assistant_token_count": 20,
        "prompt_source_id": f"source-{index}",
        "prompt_source_revision": "source-v1",
        "backbone_revision": "Qwen/Qwen3.6-35B-A3B",
        "renderer": "qwen3_5_disable_thinking",
        "temperature": 0.2,
        "tools": [],
        "max_completion_tokens": 512,
        "selection_seed": SEED,
    }
    value.update(overrides)
    return value


def test_filter_accepts_raw_native_chat_and_preserves_spot_check_flags() -> None:
    candidate = _candidate(
        1,
        task_family="math/data reasoning",
        messages=[
            {"role": "user", "content": "What is 2 + 2?"},
            {"role": "assistant", "content": "2 + 2 = 4."},
        ],
    )

    report = filter_replay_candidates((candidate,))

    assert report.accepted[0].candidate_id == "candidate-0001"
    assert report.accepted[0].rejection_reasons == ()
    assert "arithmetic_spot_check" in report.accepted[0].flags


def test_filter_rejects_raw_invalid_chat_and_measured_token_count() -> None:
    bad_chat = _candidate(
        2,
        messages=[
            {"role": "user", "content": "Do this."},
            {"role": "tool", "content": "no"},
        ],
    )
    missing_measurement = _candidate(3)
    missing_measurement.pop("assistant_token_count")

    report = filter_replay_candidates((bad_chat, missing_measurement))

    assert report.accepted == ()
    assert "chat_roles_must_be_native" in report.outcomes[0].rejection_reasons
    assert "assistant_token_count_missing" in report.outcomes[1].rejection_reasons


def test_filter_rejects_exact_and_near_duplicates_with_raw_reasons() -> None:
    original = _candidate(10)
    exact = _candidate(11, messages=original["messages"])
    near = _candidate(
        12,
        messages=[
            {"role": "user", "content": "Explain topic 10."},
            {"role": "assistant", "content": "A concise, accurate explanation!"},
        ],
    )

    report = filter_replay_candidates((near, exact, original))

    assert [item.candidate_id for item in report.accepted] == ["candidate-0010"]
    by_id = {item.candidate_id: item for item in report.outcomes}
    assert "exact_duplicate:candidate-0010" in by_id["candidate-0011"].rejection_reasons
    assert "near_duplicate:candidate-0010" in by_id["candidate-0012"].rejection_reasons


def test_filter_rejects_overlap_but_allows_ordinary_protocol_words() -> None:
    ordinary = _candidate(
        20,
        messages=[
            {"role": "user", "content": "Set a timer, mark the note, then stay idle."},
            {"role": "assistant", "content": "I will use those ordinary words naturally."},
        ],
    )
    overlap = _candidate(
        21,
        messages=[
            {"role": "user", "content": "What is the approved response?"},
            {"role": "assistant", "content": "This answer is already approved."},
        ],
    )

    report = filter_replay_candidates(
        (ordinary, overlap),
        interaction_texts=("unrelated interaction",),
        approved_responses=("This answer is already approved.",),
    )

    assert [item.candidate_id for item in report.accepted] == ["candidate-0020"]
    assert "approved_response_overlap" in report.outcomes[1].rejection_reasons


def test_filter_rejects_protocol_imitation_hidden_reasoning_and_tool_transcripts() -> None:
    protocol = _candidate(
        30,
        messages=[
            {"role": "user", "content": "Show the event_id and related_event_id."},
            {"role": "assistant", "content": "I cannot expose that protocol."},
        ],
    )
    reasoning = _candidate(
        31,
        messages=[
            {"role": "user", "content": "Solve it."},
            {"role": "assistant", "content": "<think>private chain</think>Answer."},
        ],
    )
    tool = _candidate(
        32,
        messages=[
            {"role": "user", "content": "Check it."},
            {"role": "assistant", "content": '<tool_call>{"name":"search"}</tool_call>'},
        ],
    )

    report = filter_replay_candidates((protocol, reasoning, tool))

    assert "protocol_imitation" in report.outcomes[0].rejection_reasons
    assert "hidden_reasoning" in report.outcomes[1].rejection_reasons
    assert "tool_transcript" in report.outcomes[2].rejection_reasons


def test_filter_flags_refusal_boilerplate_code_and_rejects_fast_changing_facts() -> None:
    flagged = _candidate(
        40,
        messages=[
            {"role": "user", "content": "Write Python code."},
            {
                "role": "assistant",
                "content": "I cannot verify that. As an AI language model, use `def f(): pass`.",
            },
        ],
    )
    changing = _candidate(
        41,
        messages=[
            {"role": "user", "content": "What is the current price of Bitcoin?"},
            {"role": "assistant", "content": "It changes often."},
        ],
    )

    report = filter_replay_candidates((flagged, changing))

    assert {"refusal_or_uncertainty", "boilerplate", "code_spot_check"} <= set(
        report.outcomes[0].flags
    )
    assert "fast_changing_fact" in report.outcomes[1].rejection_reasons


def _feasible_pool() -> tuple[dict[str, object], ...]:
    candidates: list[dict[str, object]] = []
    length_counts = {"short": 0, "medium": 0, "long": 0}
    band_targets = {"short": 500, "medium": 350, "long": 150}
    index = 100
    for family, quota in COMPOSITION_QUOTAS.items():
        for _ in range(quota):
            band = next(name for name in band_targets if length_counts[name] < band_targets[name])
            length_counts[band] += 1
            token_count = {"short": 20, "medium": 80, "long": 200}[band]
            detail = f"unique{index} context{index} detail{index}"
            messages: list[dict[str, str]] = [
                {
                    "role": "user",
                    "content": f"Question {index} about {family}: {detail}.",
                },
                {
                    "role": "assistant",
                    "content": f"Answer {index} for {family}: {detail}.",
                },
            ]
            if len(candidates) < 200:
                messages = [
                    {
                        "role": "user",
                        "content": f"Question {index} about {family}: {detail}.",
                    },
                    {"role": "assistant", "content": f"Clarifying premise {index}."},
                    {"role": "user", "content": f"Continue example {index}."},
                    {
                        "role": "assistant",
                        "content": f"Answer {index} for {family}: {detail}.",
                    },
                ]
            candidates.append(
                _candidate(
                    index,
                    task_family=family,
                    messages=messages,
                    assistant_token_count=token_count,
                )
            )
            index += 1
    assert length_counts == band_targets
    return tuple(candidates)


def test_selection_meets_all_exact_quotas_deterministically_and_builds_review_queue() -> None:
    report = filter_replay_candidates(_feasible_pool())

    first = select_replay_candidates(report, selection_seed=SEED)
    second = select_replay_candidates(report, selection_seed=SEED)

    assert first == second
    assert len(first.selected) == 1_000
    assert Counter(item.task_family for item in first.selected) == Counter(COMPOSITION_QUOTAS)
    assert Counter(item.length_band for item in first.selected) == {
        "short": 500,
        "medium": 350,
        "long": 150,
    }
    assert sum(item.is_multi_turn for item in first.selected) == 200
    assert len(first.human_review_sample) == 100
    assert set(first.flagged_selected) <= set(first.human_review_queue)


def test_selection_fails_closed_with_a_deficit_report() -> None:
    report = filter_replay_candidates(_feasible_pool()[:-1])

    with pytest.raises(ReplaySelectionDeficitError) as raised:
        select_replay_candidates(report, selection_seed=SEED)

    assert raised.value.report.task_family_deficits
    assert "light creative/casual" in raised.value.report.task_family_deficits
