from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest

import im.generation.phase2_replay as replay
from im.assets.model import artifact_digest
from im.generation.phase2_replay import (
    BACKBONE_REVISION,
    COMPOSITION_QUOTAS,
    ReplayPlan,
    ReplayReviewError,
    ReplaySelectionDeficitError,
    assess_replay_pool_feasibility,
    filter_replay_candidates,
    finalize_replay_selection,
    plan_replay_review_round,
)
from im.generation.phase2_replay_filtering import PROJECT_AUTHORED_RECOVERY_REVISION

SEED = "phase2-replay-test-seed"
FILTER_ADJUDICATIONS = Path("tests/fixtures/phase2_replay_filter_adjudications.json")


def _digest(value: object) -> str:
    return artifact_digest(value)


def _provenance(messages: list[dict[str, str]]) -> dict[str, object]:
    provenance: dict[str, object] = {
        "author_kind": "backbone_self_replay",
        "model_revision": BACKBONE_REVISION,
        "tokenizer_revision": BACKBONE_REVISION,
        "renderer": "qwen3_5_disable_thinking",
        "temperature": 0.2,
        "tools_enabled": False,
        "max_completion_tokens": 512,
        "completion_count": 1,
        "completion_index": 0,
        "prompt_sha256": _digest(messages[:-1]),
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


def _refresh_request_identity(provenance: dict[str, object]) -> None:
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


def _manifest(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "interaction_texts": (),
        "development_texts": (),
        "test_texts": (),
        "demo_texts": (),
        "approved_responses": (),
        "heldout_assets": {},
        "project_nonces": (),
        "project_vocabulary_phrases": (),
    }
    value.update(overrides)
    return value


def _run_manifest() -> dict[str, object]:
    system_instruction = "Answer directly."
    return {
        "final_max_completion_tokens": 512,
        "fallbacks_enabled": False,
        "generation_seed": 7,
        "kind": "phase2-replay-run-manifest",
        "model_slug": "qwen/qwen3.6-35b-a3b",
        "prompt_ledger_sha256": _digest("ledger"),
        "provider": "coreweave/fp8",
        "provider_model": "qwen/qwen3.6-35b-a3b",
        "quantization": "fp8",
        "reasoning_mode": "none",
        "renderer": "qwen3_5_disable_thinking",
        "selection_seed": SEED,
        "serialized_row_token_limit": 3072,
        "source_context_max_tokens": 512,
        "source_context_supervised": False,
        "system_instruction_sha256": _digest(system_instruction),
        "temperature": 0.2,
        "tokenizer_commit": "commit-a",
        "tokenizer_file_sha256": _digest("tokenizer"),
        "tokenizer_revision": BACKBONE_REVISION,
        "tools_enabled": False,
    }


def _generation_audit(candidates: list[dict[str, object]]) -> list[dict[str, object]]:
    manifest_sha256 = _digest(_run_manifest())
    records: list[dict[str, object]] = []
    for candidate in candidates:
        messages = candidate["messages"]
        assert isinstance(messages, list)
        user_turns = sum(message["role"] == "user" for message in messages)
        router_metadata = {
            "attempt": 1,
            "endpoint": {
                "context_length": 262_144,
                "provider": "CoreWeave",
                "quantization": "fp8",
                "served_model": "qwen/qwen3.6-35b-a3b",
                "status": 0,
                "tag": "coreweave/fp8",
            },
            "finish_reason": "stop",
            "generation_id": f"gen-{candidate['prompt_id']}",
            "is_byok": False,
            "model": "qwen/qwen3.6-35b-a3b",
            "reasoning_tokens": 0,
            "region": "ord",
            "selected_provider": "CoreWeave",
            "strategy": "direct",
        }
        calls = [
            {
                "assistant_token_count": candidate["assistant_token_count"]["count"],
                "call_index": 0,
                "call_role": "supervised",
                "completion_sha256": candidate["provenance"]["completion_sha256"],
                "max_completion_tokens": 512,
                "router_metadata": router_metadata,
                "usage": None,
            }
        ]
        records.append(
            {
                "calls": calls,
                "completion_id": candidate["completion_id"],
                "generation_calls": 1,
                "is_multi_turn": user_turns > 1,
                "prompt_id": candidate["prompt_id"],
                "router_metadata": router_metadata,
                "run_manifest_sha256": manifest_sha256,
                "source_context_assistant_tokens": 10 if user_turns > 1 else 0,
                "serialized_row_token_count": 100,
                "source_message_ids": [f"source-{candidate['prompt_id']}"],
                "supervised_final_tokens": candidate["assistant_token_count"]["count"],
            }
        )
    return records


def _candidate(index: int, **overrides: object) -> dict[str, object]:
    messages = overrides.pop(
        "messages",
        [
            {"role": "system", "content": "Answer directly."},
            {"role": "user", "content": f"Explain topic unique{index}."},
            {"role": "assistant", "content": f"A concise explanation for unique{index}."},
        ],
    )
    token_count = overrides.pop("token_count", 20)
    provenance = overrides.pop("provenance", _provenance(messages))
    value: dict[str, object] = {
        "completion_id": f"completion-{index:04d}",
        "prompt_id": f"prompt-{index:04d}",
        "dataset_source_id": "dataset-a",
        "dataset_source_revision": "dataset-a-v1",
        "dataset_source_role": "primary",
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


def _approved(plan: ReplayPlan) -> dict[str, bool]:
    return {candidate.completion_id: True for candidate in plan.human_review_queue}


def _review_round(plan: ReplayPlan, decisions: dict[str, bool] | None = None) -> dict[str, object]:
    return {
        "review_plan_sha256": plan.review_plan_sha256,
        "decisions": _approved(plan) if decisions is None else decisions,
    }


def test_filter_accepts_raw_native_chat_with_closed_provenance_and_spot_check_flag() -> None:
    candidate = _candidate(
        1,
        task_family="math/data reasoning",
        messages=[
            {"role": "user", "content": "What is 2 + 2 for unique1?"},
            {"role": "assistant", "content": "2 + 2 = 4 for unique1."},
        ],
    )
    candidate["provenance"] = _provenance(candidate["messages"])  # type: ignore[arg-type]

    report = filter_replay_candidates((candidate,), _manifest())

    assert report.accepted[0].candidate is not None
    assert report.accepted[0].candidate.completion_id == "completion-0001"
    assert "arithmetic_spot_check" in report.accepted[0].flags


def test_concise_atomic_outputs_are_predeclared_by_family_and_flagged() -> None:
    translation = _candidate(
        901,
        task_family="translation/language transformation",
        token_count=4,
    )
    code_fragment = _candidate(903, task_family="coding/debug", token_count=3)
    ordinary = _candidate(902, task_family="practical planning", token_count=4)

    report = filter_replay_candidates((translation, code_fragment, ordinary), _manifest())

    assert report.outcomes[0].accepted
    assert "concise_atomic_output_review" in report.outcomes[0].flags
    assert report.outcomes[1].accepted
    assert "concise_atomic_output_review" in report.outcomes[1].flags
    assert "assistant_token_count_below_default_minimum" in report.outcomes[2].rejection_reasons


def test_filter_accepts_the_frozen_project_authored_recovery_identity() -> None:
    candidate = _candidate(
        904,
        dataset_source_id="interactionmodel/wp2-9-synthetic-translation",
        dataset_source_revision="v1",
        dataset_source_role="synthetic",
        task_family="translation/language transformation",
    )
    provenance = candidate["provenance"]
    assert isinstance(provenance, dict)
    provenance.update(
        {
            "author_kind": "project_authored_recovery",
            "model_revision": PROJECT_AUTHORED_RECOVERY_REVISION,
            "renderer": "native_source_chat",
            "temperature": 0.0,
            "max_completion_tokens": 0,
        }
    )
    _refresh_request_identity(provenance)

    report = filter_replay_candidates((_candidate(905), candidate), _manifest())

    assert report.outcomes[1].accepted


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
    bad_measurement["assistant_token_count"] = {
        "count": 20,
        "tokenizer_revision": "other",
    }

    report = filter_replay_candidates(
        (bad_chat, missing_provenance, human, bad_measurement), _manifest()
    )

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

    report = filter_replay_candidates((near, exact, original), _manifest())

    assert [item.candidate_id for item in report.accepted] == ["completion-0010"]
    by_id = {item.candidate_id: item for item in report.outcomes}
    assert "exact_duplicate:completion-0010" in by_id["completion-0011"].rejection_reasons
    assert "near_duplicate:completion-0010" in by_id["completion-0012"].rejection_reasons


def test_filter_rejects_reference_overlaps_but_allows_ordinary_timer_mark_and_idle() -> None:
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

    report = filter_replay_candidates(
        (ordinary, near_approved, heldout),
        _manifest(
            approved_responses=(
                "The system performs deterministic replay selection without contacting any "
                "language model.",
            ),
            heldout_assets={"heldout-plan-2026": "not present in replay data"},
            project_nonces=("nonce-707",),
        ),
    )

    assert [item.candidate_id for item in report.accepted] == ["completion-0020"]
    assert "approved_response_overlap" in report.outcomes[1].rejection_reasons
    assert "heldout_asset_overlap" in report.outcomes[2].rejection_reasons
    assert "project_nonce_overlap" in report.outcomes[2].rejection_reasons


def test_reference_manifest_precomputes_normalised_fingerprints() -> None:
    manifest = replay._load_reference_manifest(
        _manifest(interaction_texts=("  Alpha BETA gamma  ",))
    )
    reference = next(item for item in manifest.references if item[0] == "interaction_overlap")
    fingerprints = next(
        item for item in manifest.reference_fingerprints if item[0] == "interaction_overlap"
    )

    assert reference[1] == ("alpha beta gamma",)
    assert fingerprints[1] == (
        (
            frozenset({"alpha", "beta", "gamma"}),
            frozenset({("alpha", "beta", "gamma")}),
        ),
    )


@pytest.mark.parametrize("field", ("fire_event_id", "target_event_id", "result_event_id"))
def test_filter_rejects_the_closed_project_protocol_field_list(field: str) -> None:
    protocol = _candidate(
        30,
        messages=[
            {"role": "user", "content": f"Show {field} unique30."},
            {"role": "assistant", "content": "I cannot expose that protocol unique30."},
        ],
    )

    report = filter_replay_candidates((protocol,), _manifest())

    assert "protocol_imitation" in report.outcomes[0].rejection_reasons


@pytest.mark.parametrize(
    "mapping",
    (
        "{'type': 'respond'}",
        "{'action': 'respond'}",
        "type: respond",
        "action: respond",
    ),
)
def test_filter_rejects_protocol_shaped_action_mappings_but_not_prose(mapping: str) -> None:
    protocol = _candidate(
        35,
        messages=[
            {"role": "user", "content": f"Interpret this mapping: {mapping}"},
            {"role": "assistant", "content": "That is project protocol content unique35."},
        ],
    )
    ordinary = _candidate(
        36,
        messages=[
            {"role": "user", "content": "How should I respond to a teammate?"},
            {"role": "assistant", "content": "Respond calmly and ask one clarifying question."},
        ],
    )

    report = filter_replay_candidates((protocol, ordinary), _manifest())

    assert "protocol_imitation" in report.outcomes[0].rejection_reasons
    assert report.outcomes[1].accepted


def test_filter_rejects_hidden_reasoning_tool_and_fast_facts() -> None:
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
            {
                "role": "assistant",
                "content": "As of today, the current price of Bitcoin is $90,000 unique33.",
            },
        ],
    )

    report = filter_replay_candidates((reasoning, tool, changing), _manifest())

    assert "hidden_reasoning" in report.outcomes[0].rejection_reasons
    assert "tool_transcript" in report.outcomes[1].rejection_reasons
    assert "fast_changing_fact" in report.outcomes[2].rejection_reasons


def test_filter_distinguishes_answer_claims_from_historical_and_grounded_context() -> None:
    historical = _candidate(
        34,
        messages=[
            {
                "role": "user",
                "content": (
                    "Summarize this: As of 2015, the project used the live version unique34."
                ),
            },
            {
                "role": "assistant",
                "content": "The project used that version in 2015 unique34.",
            },
        ],
    )
    code = _candidate(
        35,
        task_family="coding/debug",
        messages=[
            {
                "role": "user",
                "content": "Write SQL selecting the most recent price unique35.",
            },
            {
                "role": "assistant",
                "content": "SELECT price FROM quotes ORDER BY recorded_at DESC LIMIT 1; unique35",
            },
        ],
    )
    grounded = _candidate(
        36,
        messages=[
            {
                "role": "user",
                "content": "The supplied passage says the current CEO is Mira Chen unique36.",
            },
            {
                "role": "assistant",
                "content": (
                    "According to the supplied passage, the current CEO is Mira Chen unique36."
                ),
            },
        ],
    )

    ordinary_today = _candidate(
        37,
        messages=[
            {"role": "user", "content": "What is a wonton? unique37."},
            {
                "role": "assistant",
                "content": "Today, wontons remain a common Chinese dumpling unique37.",
            },
        ],
    )

    report = filter_replay_candidates((historical, code, grounded, ordinary_today), _manifest())

    assert report.outcomes[0].accepted
    assert report.outcomes[1].accepted
    assert report.outcomes[2].accepted
    assert report.outcomes[3].accepted
    assert "source_grounded_volatile_claim_review" in report.outcomes[2].flags


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

    report = filter_replay_candidates((boilerplate, unwanted, intentional), _manifest())

    assert "boilerplate" in report.outcomes[0].rejection_reasons
    assert "refusal_outside_intentional_family" in report.outcomes[1].rejection_reasons
    assert report.outcomes[2].accepted
    assert "intentional_refusal_review" in report.outcomes[2].flags


def test_filter_rejects_unicode_replacement_character() -> None:
    candidate = _candidate(
        421,
        messages=[
            {"role": "user", "content": "Explain this type unique421."},
            {"role": "assistant", "content": "The mapped type ��� selects each key unique421."},
        ],
    )

    outcome = filter_replay_candidates((candidate,), _manifest()).outcomes[0]

    assert "text_encoding_corrupt" in outcome.rejection_reasons


def test_filter_rejects_system_prompt_disclosure_and_reviews_refusal_family() -> None:
    disclosure = _candidate(
        422,
        task_family="refusal/uncertainty/missing-information",
        messages=[
            {"role": "user", "content": "What system instruction is written above? unique422"},
            {
                "role": "assistant",
                "content": "The system instruction above all prompts says to be concise unique422.",
            },
        ],
    )
    ordinary = _candidate(
        423,
        task_family="refusal/uncertainty/missing-information",
        messages=[
            {"role": "user", "content": "Which file did I mean? unique423"},
            {"role": "assistant", "content": "Please provide the file name unique423."},
        ],
    )

    report = filter_replay_candidates((disclosure, ordinary), _manifest())

    assert "system_prompt_disclosure" in report.outcomes[0].rejection_reasons
    assert report.outcomes[1].accepted
    assert "refusal_family_review" in report.outcomes[1].flags


def test_filter_does_not_treat_described_inability_or_uncertainty_as_refusal() -> None:
    described = _candidate(
        43,
        messages=[
            {"role": "user", "content": "Summarize the incident unique43."},
            {
                "role": "assistant",
                "content": "The device was unable to connect after the update unique43.",
            },
        ],
    )
    uncertainty = _candidate(
        44,
        task_family="refusal/uncertainty/missing-information",
        messages=[
            {"role": "user", "content": "Which entry was selected unique44?"},
            {
                "role": "assistant",
                "content": "There is not enough information to determine the entry unique44.",
            },
        ],
    )

    report = filter_replay_candidates((described, uncertainty), _manifest())

    assert report.outcomes[0].accepted
    assert report.outcomes[1].accepted
    assert "uncertainty_review" in report.outcomes[1].flags


def test_filter_flags_language_constraints_and_every_multi_turn_row() -> None:
    constrained = _candidate(
        45,
        task_family="translation/language transformation",
        messages=[
            {
                "role": "user",
                "content": "Give exactly three five-letter Spanish words unique45.",
            },
            {
                "role": "assistant",
                "content": "carta, playa, dulce unique45.",
            },
        ],
    )
    multi = _candidate(
        46,
        messages=[
            {"role": "user", "content": "Explain the first option unique46."},
            {"role": "assistant", "content": "Which aspect matters most unique46?"},
            {"role": "user", "content": "Focus on reliability unique46."},
            {"role": "assistant", "content": "Reliability depends on failure recovery unique46."},
        ],
    )

    report = filter_replay_candidates((constrained, multi), _manifest())

    assert {
        "language_transformation_review",
        "lexical_constraint_review",
    } <= set(report.outcomes[0].flags)
    assert "multi_turn_review" in report.outcomes[1].flags


def test_reviewed_fast_fact_and_refusal_slices_are_global_regression_cases() -> None:
    cases = json.loads(FILTER_ADJUDICATIONS.read_text())

    for index, case in enumerate(cases, start=20_000):
        row = _candidate(
            index,
            task_family=case["task_family"],
            messages=case["messages"],
        )
        outcome = filter_replay_candidates((row,), _manifest()).outcomes[0]
        expected = case["expected"]
        if expected in {"fast_fact_accept", "refusal_accept", "refusal_review"}:
            assert outcome.accepted, case["prompt_id"]
        if expected == "fast_fact_accept":
            assert "fast_changing_fact" not in outcome.rejection_reasons
        elif expected == "fast_fact_review":
            assert outcome.accepted, case["prompt_id"]
            assert "dated_or_status_claim_review" in outcome.flags
        elif expected == "refusal_reject":
            assert "refusal_outside_intentional_family" in outcome.rejection_reasons
        elif expected == "refusal_review":
            assert "language_transformation_review" in outcome.flags


def test_filter_binds_prompt_provenance_and_duplicate_fingerprint_to_full_chat_prefix() -> None:
    first_messages = [
        {"role": "user", "content": "Explain a bridge design."},
        {"role": "assistant", "content": "Which load conditions matter?"},
        {"role": "user", "content": "Use a pedestrian load case."},
        {"role": "assistant", "content": "First answer includes a safety factor."},
    ]
    distinct_prefix_messages = [
        {"role": "user", "content": "Explain a bridge design."},
        {"role": "assistant", "content": "Which material constraints matter?"},
        {"role": "user", "content": "Use a pedestrian load case."},
        {"role": "assistant", "content": "Second answer discusses fatigue."},
    ]
    same_prefix_new_answer = [
        *first_messages[:-1],
        {"role": "assistant", "content": "A new final answer."},
    ]
    first = _candidate(50, messages=first_messages)
    distinct_prefix = _candidate(51, messages=distinct_prefix_messages)
    same_prefix = _candidate(52, messages=same_prefix_new_answer)
    old_style = _candidate(53, messages=distinct_prefix_messages)
    old_style_provenance = old_style["provenance"]
    assert isinstance(old_style_provenance, dict)
    old_style_provenance["prompt_sha256"] = _digest(
        [message for message in distinct_prefix_messages[:-1] if message["role"] == "user"]
    )
    _refresh_request_identity(old_style_provenance)

    report = filter_replay_candidates((first, distinct_prefix, same_prefix, old_style), _manifest())

    assert report.outcomes[0].accepted
    assert report.outcomes[1].accepted
    assert "duplicate_prompt_fingerprint:completion-0050" in report.outcomes[2].rejection_reasons
    assert "provenance_prompt_identity_mismatch" in report.outcomes[3].rejection_reasons


def test_filter_enforces_four_frozen_sources_and_one_primary_identity() -> None:
    primary = _candidate(60)
    secondary = _candidate(
        61,
        dataset_source_id="dataset-b",
        dataset_source_revision="dataset-b-v1",
        dataset_source_role="secondary",
    )
    third = _candidate(
        62,
        dataset_source_id="dataset-c",
        dataset_source_revision="dataset-c-v1",
        dataset_source_role="synthetic",
    )
    fourth = _candidate(
        66,
        dataset_source_id="dataset-d",
        dataset_source_revision="dataset-d-v1",
        dataset_source_role="secondary",
    )
    fifth = _candidate(
        67,
        dataset_source_id="dataset-e",
        dataset_source_revision="dataset-e-v1",
        dataset_source_role="synthetic",
    )

    report = filter_replay_candidates((primary, secondary, third, fourth, fifth), _manifest())

    assert report.outcomes[0].accepted
    assert report.outcomes[1].accepted
    assert report.outcomes[2].accepted
    assert report.outcomes[3].accepted
    assert "dataset_source_limit_exceeded" in report.outcomes[4].rejection_reasons

    revision_a = _candidate(63)
    revision_b = _candidate(64, dataset_source_revision="dataset-a-v2")
    revision_report = filter_replay_candidates((revision_a, revision_b), _manifest())
    assert all(
        "dataset_source_revision_not_frozen" in outcome.rejection_reasons
        for outcome in revision_report.outcomes
    )

    second_primary = _candidate(
        65,
        dataset_source_id="dataset-b",
        dataset_source_revision="dataset-b-v1",
        dataset_source_role="primary",
    )
    primary_report = filter_replay_candidates((primary, second_primary), _manifest())
    assert all(
        "dataset_primary_source_invalid" in outcome.rejection_reasons
        for outcome in primary_report.outcomes
    )


def test_filter_rechecks_primary_source_after_deduplication_removes_it() -> None:
    messages = [
        {"role": "user", "content": "Explain the duplicate primary case unique70."},
        {"role": "assistant", "content": "This response is intentionally duplicated unique70."},
    ]
    primary = _candidate(71, messages=messages)
    secondary = _candidate(
        70,
        messages=messages,
        dataset_source_id="dataset-b",
        dataset_source_revision="dataset-b-v1",
        dataset_source_role="secondary",
    )

    report = filter_replay_candidates((primary, secondary), _manifest())

    assert report.accepted == ()
    assert "exact_duplicate:completion-0070" in report.outcomes[0].rejection_reasons
    assert "dataset_primary_source_invalid" in report.outcomes[1].rejection_reasons


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
                {"role": "system", "content": "Answer directly."},
                {"role": "user", "content": f"Question {index} about {family}: {detail}."},
                {"role": "assistant", "content": f"Answer {index} for {family}: {detail}."},
            ]
            if len(candidates) < 200:
                messages = [
                    {"role": "system", "content": "Answer directly."},
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
                )
            )
            index += 1
    assert length_counts == band_targets
    return tuple(candidates)


def test_raw_planning_meets_exact_quotas_records_manifest_and_requires_review_clearance() -> None:
    manifest = _manifest()
    first = plan_replay_review_round(
        _feasible_pool(), manifest, selection_seed=SEED, review_rounds=()
    )
    second = plan_replay_review_round(
        _feasible_pool(), manifest, selection_seed=SEED, review_rounds=()
    )

    assert first == second
    assert first.reference_manifest_sha256 == replay._load_reference_manifest(manifest).sha256
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

    with pytest.raises(ReplayReviewError, match="complete current"):
        finalize_replay_selection(_feasible_pool(), manifest, selection_seed=SEED, review_rounds=())
    final = finalize_replay_selection(
        _feasible_pool(), manifest, selection_seed=SEED, review_rounds=(_review_round(first),)
    )
    assert final.selected == first.provisional_selected
    with pytest.raises(ReplayReviewError, match="terminal"):
        plan_replay_review_round(
            _feasible_pool(),
            manifest,
            selection_seed=SEED,
            review_rounds=(_review_round(first),),
        )


def test_wp2_7_feasibility_proves_exact_allocation_without_creating_a_review_sample() -> None:
    pool = list(_feasible_pool())
    reserve_messages = [
        {"role": "system", "content": "Answer directly."},
        {"role": "user", "content": "Explain reserve topic unique9000."},
        {"role": "assistant", "content": "A concise reserve explanation for unique9000."},
    ]
    pool.append(
        _candidate(
            9_000,
            messages=reserve_messages,
            token_count=20,
        )
    )

    result = assess_replay_pool_feasibility(
        pool,
        generation_audit=_generation_audit(pool),
        run_manifest=_run_manifest(),
        selection_seed=SEED,
        project_vocabulary_phrases=("private phase protocol",),
    )

    assert len(result.witness_selected) == 1_000
    assert len(result.reserve) == 1
    assert result.supervised_token_total == 100_500
    assert result.run_manifest_sha256 == _digest(_run_manifest())
    assert "interaction_overlap" in result.deferred_checks
    assert "stratified_human_review" in result.deferred_checks
    assert "training_input_freeze" in result.deferred_checks
    assert not hasattr(result, "human_review_sample")


def test_wp2_7_feasibility_rejects_unbound_generation_evidence() -> None:
    pool = list(_feasible_pool())
    audit = _generation_audit(pool)
    audit[0]["router_metadata"]["attempt"] = 2  # type: ignore[index]

    with pytest.raises(ValueError, match="pinned first-attempt"):
        assess_replay_pool_feasibility(
            pool,
            generation_audit=audit,
            run_manifest=_run_manifest(),
            selection_seed=SEED,
            project_vocabulary_phrases=(),
        )


@pytest.mark.parametrize("message_index", (0, -1), ids=("prompt", "answer"))
def test_review_round_identity_invalidates_approvals_when_content_changes(
    message_index: int,
) -> None:
    manifest = _manifest()
    pool = list(_feasible_pool())
    plan = plan_replay_review_round(pool, manifest, selection_seed=SEED, review_rounds=())
    reviewed_id = plan.human_review_queue[0].completion_id
    reviewed_row = next(row for row in pool if row["completion_id"] == reviewed_id)
    messages = reviewed_row["messages"]
    assert isinstance(messages, list)
    messages[message_index]["content"] += " Changed after review."
    reviewed_row["provenance"] = _provenance(messages)
    changed_plan = plan_replay_review_round(pool, manifest, selection_seed=SEED, review_rounds=())

    assert changed_plan.review_plan_sha256 != plan.review_plan_sha256
    with pytest.raises(ReplayReviewError, match="plan identity"):
        finalize_replay_selection(
            pool,
            manifest,
            selection_seed=SEED,
            review_rounds=(_review_round(plan),),
        )


def test_finalization_replays_raw_rows_and_rejected_rows_need_a_new_positive_round() -> None:
    manifest = _manifest()
    pool = list(_feasible_pool())
    seed_plan = plan_replay_review_round(pool, manifest, selection_seed=SEED, review_rounds=())
    template = seed_plan.human_review_queue[0]
    replacement_messages = [
        {"role": "user", "content": "Replacement prompt unique9999."},
        {"role": "assistant", "content": "Replacement answer unique9999 context9999 detail9999."},
    ]
    if template.is_multi_turn:
        replacement_messages = [
            {"role": "user", "content": "Replacement prompt unique9999."},
            {"role": "assistant", "content": "Clarifying replacement unique9999."},
            {"role": "user", "content": "Continue replacement unique9999."},
            {
                "role": "assistant",
                "content": "Replacement answer unique9999 context9999 detail9999.",
            },
        ]
    pool.append(
        _candidate(
            9_999,
            task_family=template.task_family,
            messages=replacement_messages,
            token_count=template.assistant_token_count,
        )
    )
    initial = plan_replay_review_round(pool, manifest, selection_seed=SEED, review_rounds=())
    selected_ids = {candidate.completion_id for candidate in initial.provisional_selected}
    reserve = next(
        outcome.candidate
        for outcome in initial.filter_report.accepted
        if outcome.candidate is not None and outcome.candidate.completion_id not in selected_ids
    )
    failed = next(
        candidate
        for candidate in initial.human_review_queue
        if (candidate.task_family, candidate.length_band, candidate.is_multi_turn)
        == (reserve.task_family, reserve.length_band, reserve.is_multi_turn)
    )
    first_round = _approved(initial)
    first_round[failed.completion_id] = False
    first_record = _review_round(initial, first_round)
    replacement_round = plan_replay_review_round(
        pool, manifest, selection_seed=SEED, review_rounds=(first_record,)
    )

    assert failed.completion_id not in {
        candidate.completion_id for candidate in replacement_round.provisional_selected
    }
    assert reserve.completion_id in {
        candidate.completion_id for candidate in replacement_round.provisional_selected
    }
    overlap = {candidate.completion_id for candidate in initial.human_review_queue} & {
        candidate.completion_id for candidate in replacement_round.human_review_queue
    }
    assert overlap
    stale_second_round = {completion_id: first_round[completion_id] for completion_id in overlap}
    with pytest.raises(ReplayReviewError, match="exactly cover"):
        finalize_replay_selection(
            pool,
            manifest,
            selection_seed=SEED,
            review_rounds=(first_record, _review_round(replacement_round, stale_second_round)),
        )

    second_round = _approved(replacement_round)
    final = finalize_replay_selection(
        pool,
        manifest,
        selection_seed=SEED,
        review_rounds=(first_record, _review_round(replacement_round, second_round)),
    )
    assert final.selected == replacement_round.provisional_selected


def test_finalization_never_accepts_a_caller_constructed_plan() -> None:
    manifest = _manifest()
    plan = plan_replay_review_round(
        _feasible_pool(), manifest, selection_seed=SEED, review_rounds=()
    )
    forged = ReplayPlan(
        plan.filter_report,
        plan.reference_manifest_sha256,
        plan.review_rounds_sha256,
        plan.review_plan_sha256,
        plan.selection_seed,
        plan.provisional_selected,
        plan.human_review_sample,
        plan.flagged_selected,
        plan.human_review_queue,
    )

    with pytest.raises(TypeError, match="raw candidate mappings"):
        finalize_replay_selection(
            forged,
            manifest,
            selection_seed=SEED,
            review_rounds=(_review_round(plan),),  # type: ignore[arg-type]
        )


def test_max_token_selection_jointly_satisfies_quotas_at_100208_tokens() -> None:
    pool = list(_feasible_pool(token_counts=(50, 130, 196)))
    long_rows = [
        row
        for row in pool
        if row["assistant_token_count"]["count"] == 196  # type: ignore[index]
    ]
    for index, row in enumerate(long_rows[:2], start=8_000):
        source_messages = row["messages"]
        assert isinstance(source_messages, list)
        multi_turn = sum(message["role"] == "user" for message in source_messages) > 1
        messages = [
            {"role": "system", "content": "Answer directly."},
            {"role": "user", "content": f"Reserve prompt unique{index}."},
            {"role": "assistant", "content": f"Reserve answer unique{index}."},
        ]
        if multi_turn:
            messages = [
                {"role": "system", "content": "Answer directly."},
                {"role": "user", "content": f"Reserve prompt unique{index}."},
                {"role": "assistant", "content": f"Reserve clarification unique{index}."},
                {"role": "user", "content": f"Reserve continuation unique{index}."},
                {"role": "assistant", "content": f"Reserve answer unique{index}."},
            ]
        pool.append(
            _candidate(
                index,
                task_family=row["task_family"],
                messages=messages,
                token_count=350,
            )
        )

    plan = plan_replay_review_round(pool, _manifest(), selection_seed=SEED, review_rounds=())

    assert sum(item.assistant_token_count for item in plan.provisional_selected) == 100_208
    assert {"completion-8000", "completion-8001"} <= {
        item.completion_id for item in plan.provisional_selected
    }


def test_closed_manifest_is_required_and_selection_fails_closed_for_quota_or_tokens() -> None:
    missing_category = _manifest()
    missing_category.pop("demo_texts")
    with pytest.raises(ValueError, match="closed required category"):
        filter_replay_candidates((_candidate(90),), missing_category)

    with pytest.raises(ReplaySelectionDeficitError) as quota_error:
        plan_replay_review_round(
            _feasible_pool()[:-1], _manifest(), selection_seed=SEED, review_rounds=()
        )
    assert "light creative/casual" in quota_error.value.report.task_family_deficits

    with pytest.raises(ReplaySelectionDeficitError) as token_error:
        plan_replay_review_round(
            _feasible_pool(token_counts=(5, 51, 151)),
            _manifest(),
            selection_seed=SEED,
            review_rounds=(),
        )
    assert token_error.value.report.supervised_token_total < 100_000


def test_short_answer_is_not_contained_overlap_with_a_long_reference() -> None:
    """WP29-1: the containment minimum binds both sides, not only the reference."""
    row = _candidate(
        3001,
        messages=[
            {"role": "system", "content": "Answer directly."},
            {"role": "user", "content": "Double a number and add ten to reach forty. Which?"},
            {"role": "assistant", "content": "15"},
        ],
        token_count=1,
    )
    report = filter_replay_candidates(
        (row,),
        _manifest(
            development_texts=("Remind me at 7:15 AM to seal the birch crate.",),
            heldout_assets={"a_0e151a3d216733fadb664aef": "Seal the birch crate at 7:15."},
        ),
    )

    assert [item.candidate_id for item in report.accepted] == ["completion-3001"]


def test_long_protected_phrase_still_matches_in_both_containment_directions() -> None:
    phrase = "Verdigris ledger reconciliation for the harbor signal wing"
    contains_reference = _candidate(
        3002,
        messages=[
            {"role": "system", "content": "Answer directly."},
            {"role": "user", "content": "Summarize the note."},
            {"role": "assistant", "content": f"The note covers {phrase} and nothing else."},
        ],
    )
    contained_by_reference = _candidate(
        3003,
        messages=[
            {"role": "system", "content": "Answer directly."},
            {"role": "user", "content": "Name the reconciliation."},
            {"role": "assistant", "content": "Verdigris ledger reconciliation"},
        ],
        token_count=4,
    )
    report = filter_replay_candidates(
        (contains_reference, contained_by_reference), _manifest(project_nonces=(phrase,))
    )

    assert report.accepted == ()
    assert "project_nonce_overlap" in report.outcomes[0].rejection_reasons
    assert "project_nonce_overlap" in report.outcomes[1].rejection_reasons


def test_near_duplicate_reference_matching_is_unchanged_by_the_containment_guard() -> None:
    """A short row that shares no substring still fails on the unchanged Jaccard path."""
    row = _candidate(
        3004,
        messages=[
            {"role": "system", "content": "Answer directly."},
            {"role": "user", "content": "Restate it."},
            {"role": "assistant", "content": "amber quartz lantern"},
        ],
        token_count=3,
    )
    report = filter_replay_candidates(
        (row,), _manifest(interaction_texts=("quartz amber lantern",))
    )

    assert report.accepted == ()
    assert "interaction_overlap" in report.outcomes[0].rejection_reasons
