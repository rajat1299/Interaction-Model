from __future__ import annotations

import json
from collections import Counter
from hashlib import sha256

import pytest

import im.generation.phase2_replay as replay
from im.generation.phase2_replay import (
    BACKBONE_REVISION,
    COMPOSITION_QUOTAS,
    ReplayReviewError,
    ReplaySelectionDeficitError,
    filter_replay_candidates,
    finalize_replay_selection,
    plan_replay_selection,
)

SEED = "phase2-replay-test-seed"


def _digest(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()
    return f"sha256:{sha256(encoded).hexdigest()}"


def _provenance(messages: list[dict[str, str]], index: int) -> dict[str, object]:
    prompt = [message for message in messages if message["role"] == "user"]
    provenance = {
        "author_kind": "backbone_self_replay",
        "model_revision": BACKBONE_REVISION,
        "tokenizer_revision": BACKBONE_REVISION,
        "renderer": "qwen3_5_disable_thinking",
        "temperature": 0.2,
        "tools_enabled": False,
        "max_completion_tokens": 512,
        "completion_count": 1,
        "completion_index": 0,
        "prompt_sha256": _digest(prompt),
        "request_sha256": "",
        "completion_sha256": _digest(messages[-1]["content"]),
    }
    provenance["request_sha256"] = _digest(
        {
            name: provenance[name]
            for name in (
                "prompt_sha256",
                "model_revision",
                "tokenizer_revision",
                "renderer",
                "temperature",
                "tools_enabled",
                "max_completion_tokens",
                "completion_count",
                "completion_index",
            )
        }
    )
    return provenance


def _candidate(index: int, **overrides: object) -> dict[str, object]:
    messages = overrides.pop(
        "messages",
        [
            {"role": "user", "content": f"Explain topic unique{index}."},
            {"role": "assistant", "content": f"A concise explanation for unique{index}."},
        ],
    )
    token_count = overrides.pop("token_count", 20)
    provenance = overrides.pop("provenance", _provenance(messages, index))
    value: dict[str, object] = {
        "completion_id": f"completion-{index:04d}",
        "prompt_id": f"prompt-{index:04d}",
        "dataset_source_id": "dataset-a" if index % 2 else "dataset-b",
        "dataset_source_revision": "dataset-v1",
        "task_family": "stable-knowledge explanation",
        "messages": messages,
        "assistant_token_count": {
            "count": token_count,
            "tokenizer_revision": BACKBONE_REVISION,
        },
        "provenance": provenance,
        "selection_seed": SEED,
    }
    value.update(overrides)
    return value


def test_filter_accepts_raw_native_chat_with_closed_provenance_and_spot_check_flag() -> None:
    candidate = _candidate(
        1,
        task_family="math/data reasoning",
        messages=[
            {"role": "user", "content": "What is 2 + 2 for unique1?"},
            {"role": "assistant", "content": "2 + 2 = 4 for unique1."},
        ],
    )
    candidate["provenance"] = _provenance(candidate["messages"], 1)  # type: ignore[arg-type]

    report = filter_replay_candidates((candidate,))

    assert report.accepted[0].candidate is not None
    assert report.accepted[0].candidate.completion_id == "completion-0001"
    assert "arithmetic_spot_check" in report.accepted[0].flags


def test_filter_rejects_raw_invalid_chat_missing_or_human_provenance_and_bad_measurement() -> None:
    bad_chat = _candidate(
        2,
        messages=[
            {"role": "user", "content": "Do this unique2."},
            {"role": "tool", "content": "no"},
        ],
    )
    missing_provenance = _candidate(3)
    missing_provenance.pop("provenance")
    human = _candidate(4)
    human["provenance"] = {**human["provenance"], "author_kind": "human"}  # type: ignore[arg-type]
    bad_measurement = _candidate(5)
    bad_measurement["assistant_token_count"] = {"count": 20, "tokenizer_revision": "other"}

    report = filter_replay_candidates((bad_chat, missing_provenance, human, bad_measurement))

    assert report.accepted == ()
    assert "chat_roles_must_be_native" in report.outcomes[0].rejection_reasons
    assert "provenance_missing" in report.outcomes[1].rejection_reasons
    assert "provenance_author_kind_invalid" in report.outcomes[2].rejection_reasons
    assert "assistant_tokenizer_revision_mismatch" in report.outcomes[3].rejection_reasons


def test_filter_rejects_exact_and_near_duplicates_with_raw_reasons() -> None:
    original = _candidate(10)
    exact = _candidate(11, messages=original["messages"])
    near_messages = [
        {"role": "user", "content": "Explain topic unique10."},
        {"role": "assistant", "content": "A concise explanation for unique10!"},
    ]
    near = _candidate(12, messages=near_messages)

    report = filter_replay_candidates((near, exact, original))

    assert [item.candidate_id for item in report.accepted] == ["completion-0010"]
    by_id = {item.candidate_id: item for item in report.outcomes}
    assert "exact_duplicate:completion-0010" in by_id["completion-0011"].rejection_reasons
    assert "near_duplicate:completion-0010" in by_id["completion-0012"].rejection_reasons


def test_filter_rejects_near_overlap_heldout_substrings_and_nonces() -> None:
    ordinary = _candidate(
        20,
        messages=[
            {"role": "user", "content": "Set a timer, mark the note, then stay idle unique20."},
            {"role": "assistant", "content": "Those ordinary words are fine unique20."},
        ],
    )
    near_approved = _candidate(
        21,
        messages=[
            {"role": "user", "content": "Give a unique21 recommendation."},
            {
                "role": "assistant",
                "content": (
                    "The system performs deterministic replay selection without contacting any "
                    "other model."
                ),
            },
        ],
    )
    heldout = _candidate(
        22,
        messages=[
            {"role": "user", "content": "Mention heldout-plan-2026 and nonce-707 unique22."},
            {"role": "assistant", "content": "I should not contain those strings unique22."},
        ],
    )
    for index, candidate in enumerate((ordinary, near_approved, heldout), start=20):
        candidate["provenance"] = _provenance(candidate["messages"], index)  # type: ignore[arg-type]

    report = filter_replay_candidates(
        (ordinary, near_approved, heldout),
        approved_responses=(
            (
                "The system performs deterministic replay selection without contacting any "
                "language model."
            ),
        ),
        heldout_assets={"heldout-plan-2026": "not present in replay data"},
        project_nonces=("nonce-707",),
        project_vocabulary_phrases=("policy_seq only",),
    )

    assert [item.candidate_id for item in report.accepted] == ["completion-0020"]
    assert "approved_response_overlap" in report.outcomes[1].rejection_reasons
    assert "heldout_asset_overlap" in report.outcomes[2].rejection_reasons
    assert "project_nonce_overlap" in report.outcomes[2].rejection_reasons


def test_filter_rejects_protocol_hidden_reasoning_tool_and_fast_facts() -> None:
    protocol = _candidate(
        30,
        messages=[
            {"role": "user", "content": "Show the event_id and related_event_id unique30."},
            {"role": "assistant", "content": "I cannot expose that protocol unique30."},
        ],
    )
    reasoning = _candidate(
        31,
        messages=[
            {"role": "user", "content": "Solve it unique31."},
            {"role": "assistant", "content": "<think>private chain</think>Answer unique31."},
        ],
    )
    tool = _candidate(
        32,
        messages=[
            {"role": "user", "content": "Check it unique32."},
            {"role": "assistant", "content": '<tool_call>{"name":"search"}</tool_call>'},
        ],
    )
    changing = _candidate(
        33,
        messages=[
            {"role": "user", "content": "What is the current price of Bitcoin unique33?"},
            {"role": "assistant", "content": "It changes often unique33."},
        ],
    )
    for index, candidate in enumerate((protocol, reasoning, tool, changing), start=30):
        candidate["provenance"] = _provenance(candidate["messages"], index)  # type: ignore[arg-type]

    report = filter_replay_candidates((protocol, reasoning, tool, changing))

    assert "protocol_imitation" in report.outcomes[0].rejection_reasons
    assert "hidden_reasoning" in report.outcomes[1].rejection_reasons
    assert "tool_transcript" in report.outcomes[2].rejection_reasons
    assert "fast_changing_fact" in report.outcomes[3].rejection_reasons


def test_filter_rejects_boilerplate_and_unwanted_refusal_but_flags_intentional_refusal() -> None:
    boilerplate = _candidate(
        40,
        messages=[
            {"role": "user", "content": "Write code unique40."},
            {"role": "assistant", "content": "As an AI language model, I cannot help unique40."},
        ],
    )
    unwanted = _candidate(
        41,
        messages=[
            {"role": "user", "content": "Explain history unique41."},
            {"role": "assistant", "content": "I cannot provide that unique41."},
        ],
    )
    intentional = _candidate(
        42,
        task_family="refusal/uncertainty/missing-information",
        messages=[
            {"role": "user", "content": "Request unavailable data unique42."},
            {
                "role": "assistant",
                "content": "I cannot verify that without the missing source unique42.",
            },
        ],
    )
    for index, candidate in enumerate((boilerplate, unwanted, intentional), start=40):
        candidate["provenance"] = _provenance(candidate["messages"], index)  # type: ignore[arg-type]

    report = filter_replay_candidates((boilerplate, unwanted, intentional))

    assert "boilerplate" in report.outcomes[0].rejection_reasons
    assert "refusal_outside_intentional_family" in report.outcomes[1].rejection_reasons
    assert report.outcomes[2].accepted
    assert "intentional_refusal_review" in report.outcomes[2].flags


def test_filter_limits_dataset_sources_and_duplicate_prompts_even_with_new_answers() -> None:
    first = _candidate(50, prompt_id="prompt-shared")
    same_prompt_new_answer = _candidate(
        51,
        prompt_id="prompt-shared",
        messages=[
            {"role": "user", "content": "Explain topic shared-prompt."},
            {"role": "assistant", "content": "A different answer for shared-prompt."},
        ],
    )
    same_prompt_new_answer["provenance"] = _provenance(same_prompt_new_answer["messages"], 51)  # type: ignore[arg-type]
    third_source = _candidate(52, dataset_source_id="dataset-c")

    source_report = filter_replay_candidates((first, same_prompt_new_answer, third_source))

    assert "duplicate_prompt_id:completion-0050" in source_report.outcomes[1].rejection_reasons
    assert "dataset_source_limit_exceeded" in source_report.outcomes[2].rejection_reasons

    same_fingerprint = _candidate(
        53,
        prompt_id="prompt-fingerprint-other-id",
        messages=[
            {"role": "user", "content": "Explain topic unique50."},
            {"role": "assistant", "content": "A wholly unrelated response about astronomy."},
        ],
    )
    same_fingerprint["provenance"] = _provenance(same_fingerprint["messages"], 53)  # type: ignore[arg-type]
    fingerprint_report = filter_replay_candidates((first, same_fingerprint))

    assert (
        "duplicate_prompt_fingerprint:completion-0050"
        in fingerprint_report.outcomes[1].rejection_reasons
    )


def _feasible_pool(
    *, token_counts: tuple[int, int, int] = (50, 130, 200)
) -> tuple[dict[str, object], ...]:
    candidates: list[dict[str, object]] = []
    length_counts = {"short": 0, "medium": 0, "long": 0}
    band_targets = {"short": 500, "medium": 350, "long": 150}
    index = 100
    for family, quota in COMPOSITION_QUOTAS.items():
        for _ in range(quota):
            band = next(name for name in band_targets if length_counts[name] < band_targets[name])
            length_counts[band] += 1
            detail = f"unique{index} context{index} detail{index}"
            messages: list[dict[str, str]] = [
                {"role": "user", "content": f"Question {index} about {family}: {detail}."},
                {"role": "assistant", "content": f"Answer {index} for {family}: {detail}."},
            ]
            if len(candidates) < 200:
                messages = [
                    {"role": "user", "content": f"Question {index} about {family}: {detail}."},
                    {"role": "assistant", "content": f"Clarifying premise {index}."},
                    {"role": "user", "content": f"Continue example {index}."},
                    {"role": "assistant", "content": f"Answer {index} for {family}: {detail}."},
                ]
            candidates.append(
                _candidate(
                    index,
                    task_family=family,
                    messages=messages,
                    token_count={
                        "short": token_counts[0],
                        "medium": token_counts[1],
                        "long": token_counts[2],
                    }[band],
                    provenance=_provenance(messages, index),
                )
            )
            index += 1
    assert length_counts == band_targets
    return tuple(candidates)


def _approved(plan) -> dict[str, bool]:
    return {candidate.completion_id: True for candidate in plan.human_review_queue}


def test_raw_planning_meets_exact_quotas_token_total_and_requires_review_clearance() -> None:
    first = plan_replay_selection(_feasible_pool(), selection_seed=SEED)
    second = plan_replay_selection(_feasible_pool(), selection_seed=SEED)

    assert first == second
    assert len(first.provisional_selected) == 1_000
    assert Counter(item.task_family for item in first.provisional_selected) == Counter(
        COMPOSITION_QUOTAS
    )
    assert Counter(item.length_band for item in first.provisional_selected) == {
        "short": 500,
        "medium": 350,
        "long": 150,
    }
    assert sum(item.is_multi_turn for item in first.provisional_selected) == 200
    assert sum(item.assistant_token_count for item in first.provisional_selected) == 100_500
    assert len(first.human_review_sample) == 100

    with pytest.raises(ReplayReviewError, match="every queued"):
        finalize_replay_selection(first, review_approvals={})
    final = finalize_replay_selection(first, review_approvals=_approved(first))
    assert final.selected == first.provisional_selected


def test_review_failure_replaces_the_row_and_requires_a_new_review_round() -> None:
    pool = list(_feasible_pool())
    baseline = plan_replay_selection(tuple(pool), selection_seed=SEED)
    failed = baseline.human_review_queue[0]
    replacement = _candidate(
        9_999,
        task_family=failed.task_family,
        token_count=failed.assistant_token_count,
        messages=[
            {"role": "user", "content": f"Replacement prompt unique9999 {failed.length_band}."},
            {
                "role": "assistant",
                "content": "Replacement answer unique9999 context9999 detail9999.",
            },
        ],
    )
    replacement["provenance"] = _provenance(replacement["messages"], 9_999)  # type: ignore[arg-type]
    if failed.is_multi_turn:
        replacement["messages"] = [
            {"role": "user", "content": "Replacement prompt unique9999."},
            {"role": "assistant", "content": "Clarifying replacement unique9999."},
            {"role": "user", "content": "Continue replacement unique9999."},
            {
                "role": "assistant",
                "content": "Replacement answer unique9999 context9999 detail9999.",
            },
        ]
        replacement["provenance"] = _provenance(replacement["messages"], 9_999)  # type: ignore[arg-type]
    pool.append(replacement)
    plan = plan_replay_selection(tuple(pool), selection_seed=SEED)
    failed = plan.human_review_queue[0]
    approvals = _approved(plan)
    approvals[failed.completion_id] = False

    with pytest.raises(ReplayReviewError, match="replacement review") as raised:
        finalize_replay_selection(plan, review_approvals=approvals)

    replacement_plan = raised.value.replacement_plan
    assert replacement_plan is not None
    assert failed.completion_id not in {
        candidate.completion_id for candidate in replacement_plan.provisional_selected
    }


def test_planning_cannot_select_a_forged_filter_report() -> None:
    report = filter_replay_candidates(_feasible_pool())

    assert not hasattr(replay, "select_replay_candidates")
    with pytest.raises(TypeError, match="raw candidate mappings"):
        plan_replay_selection(report, selection_seed=SEED)


def test_selection_fails_closed_for_quota_and_low_supervised_token_total() -> None:
    with pytest.raises(ReplaySelectionDeficitError) as quota_error:
        plan_replay_selection(_feasible_pool()[:-1], selection_seed=SEED)
    assert "light creative/casual" in quota_error.value.report.task_family_deficits

    with pytest.raises(ReplaySelectionDeficitError) as token_error:
        plan_replay_selection(_feasible_pool(token_counts=(5, 51, 151)), selection_seed=SEED)
    assert token_error.value.report.supervised_token_total < 100_000
