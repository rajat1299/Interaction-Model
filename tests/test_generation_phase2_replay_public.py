from __future__ import annotations

from copy import deepcopy

from im.generation.phase2_replay_filtering import filter_replay_candidates
from im.generation.phase2_replay_public import (
    prepare_no_robots_rows,
    prepare_oasst2_original_rows,
)


def _manifest() -> dict[str, object]:
    return {
        "interaction_texts": (),
        "development_texts": (),
        "test_texts": (),
        "demo_texts": (),
        "approved_responses": (),
        "heldout_assets": {},
        "project_nonces": (),
        "project_vocabulary_phrases": (),
    }


def test_no_robots_preserves_system_context_and_binds_public_provenance() -> None:
    row = {
        "prompt_id": "source-1",
        "category": "Brainstorm",
        "messages": [
            {"role": "system", "content": "Act as a concise garden helper."},
            {"role": "user", "content": "How should I water basil?"},
            {"role": "assistant", "content": "Water when the top inch of soil feels dry."},
            {"role": "user", "content": "What about in winter?"},
            {
                "role": "assistant",
                "content": "Water less often because growth and evaporation slow.",
            },
        ],
    }

    prepared = prepare_no_robots_rows((row,), count_tokens=lambda _text: 12)
    report = filter_replay_candidates(prepared.candidates, _manifest())

    assert len(report.accepted) == 1
    assert prepared.candidates[0]["messages"][0] == row["messages"][0]
    assert prepared.lineage[0]["system_prompt_preserved"] is True
    assert "multi_turn_review" in report.accepted[0].flags


def test_public_revision_mismatch_is_rejected() -> None:
    row = {
        "prompt_id": "source-2",
        "category": "Open QA",
        "messages": [
            {"role": "user", "content": "Why do leaves change color?"},
            {"role": "assistant", "content": "Pigments become visible as chlorophyll breaks down."},
        ],
    }
    prepared = prepare_no_robots_rows((row,), count_tokens=lambda _text: 10)
    candidate = deepcopy(prepared.candidates[0])
    candidate["provenance"]["model_revision"] = "HuggingFaceH4/no_robots@main"

    report = filter_replay_candidates((candidate,), _manifest())

    assert report.outcomes[0].rejection_reasons == (
        "provenance_model_revision_mismatch",
        "provenance_request_identity_mismatch",
    )


def test_oasst2_original_reply_binds_its_exact_parent_and_passes_the_filter() -> None:
    records = {
        "prompt-1": {
            "message_id": "prompt-1",
            "parent_id": None,
            "role": "prompter",
            "lang": "en",
            "deleted": False,
            "review_result": True,
            "text": "Which details do you need?",
        },
        "reply-1": {
            "message_id": "reply-1",
            "parent_id": "prompt-1",
            "role": "assistant",
            "lang": "en",
            "deleted": False,
            "review_result": True,
            "text": "Please provide the budget and intended use.",
        },
    }

    prepared = prepare_oasst2_original_rows(
        records,
        ("reply-1",),
        count_tokens=lambda _text: 9,
        task_family="refusal/uncertainty/missing-information",
    )
    primary = prepare_no_robots_rows(
        (
            {
                "prompt_id": "primary-1",
                "category": "Brainstorm",
                "messages": [
                    {"role": "user", "content": "Suggest a garden project."},
                    {"role": "assistant", "content": "Build a small herb planter."},
                ],
            },
        ),
        count_tokens=lambda _text: 8,
    )
    report = filter_replay_candidates((*primary.candidates, *prepared.candidates), _manifest())

    assert len(report.accepted) == 2
    assert prepared.candidates[0]["prompt_id"] == "oasst2-original:prompt-1"
    assert prepared.lineage[0]["source_assistant_message_id"] == "reply-1"


def test_oasst2_original_reply_preserves_its_approved_multi_turn_path() -> None:
    records = {
        "user-1": {
            "message_id": "user-1",
            "parent_id": None,
            "role": "prompter",
            "lang": "en",
            "deleted": False,
            "review_result": True,
            "text": "How does radar work?",
        },
        "assistant-1": {
            "message_id": "assistant-1",
            "parent_id": "user-1",
            "role": "assistant",
            "lang": "en",
            "deleted": False,
            "review_result": True,
            "text": "Radar sends radio waves and measures their reflections.",
        },
        "user-2": {
            "message_id": "user-2",
            "parent_id": "assistant-1",
            "role": "prompter",
            "lang": "en",
            "deleted": False,
            "review_result": True,
            "text": "How does lidar compare?",
        },
        "assistant-2": {
            "message_id": "assistant-2",
            "parent_id": "user-2",
            "role": "assistant",
            "lang": "en",
            "deleted": False,
            "review_result": True,
            "text": "Lidar uses light, so it resolves finer detail but is more weather-sensitive.",
        },
    }

    prepared = prepare_oasst2_original_rows(
        records,
        ("assistant-2",),
        count_tokens=lambda _text: 20,
        task_family="evidence-grounded comparison/recommendation",
    )
    primary = prepare_no_robots_rows(
        (
            {
                "prompt_id": "primary-2",
                "category": "Brainstorm",
                "messages": [
                    {"role": "user", "content": "Suggest a garden project."},
                    {"role": "assistant", "content": "Build a small herb planter."},
                ],
            },
        ),
        count_tokens=lambda _text: 8,
    )
    report = filter_replay_candidates((*primary.candidates, *prepared.candidates), _manifest())

    assert len(report.accepted) == 2
    assert [item["role"] for item in prepared.candidates[0]["messages"]] == [
        "user",
        "assistant",
        "user",
        "assistant",
    ]
    assert prepared.lineage[0]["source_message_ids"] == [
        "user-1",
        "assistant-1",
        "user-2",
        "assistant-2",
    ]
    assert "multi_turn_review" in report.accepted[-1].flags


def test_source_category_wins_over_incidental_router_terms() -> None:
    row = {
        "prompt_id": "source-3",
        "category": "Summarize",
        "messages": [
            {
                "role": "user",
                "content": "Summarize this biography containing Russian names.",
            },
            {"role": "assistant", "content": "The subject shaped modern theatre."},
        ],
    }

    prepared = prepare_no_robots_rows((row,), count_tokens=lambda _text: 8)

    assert prepared.candidates[0]["task_family"] == "rewrite/edit/summarize"


def test_audited_language_row_can_override_broad_source_category() -> None:
    row = {
        "prompt_id": "9e3d7aa94979e6032896278cc9953ba21708e9c539644714e03b38049764297f",
        "category": "Open QA",
        "messages": [
            {"role": "user", "content": "How do you say bee in Japanese?"},
            {"role": "assistant", "content": 'The Japanese word is "hachi" (ハチ).'},
        ],
    }

    prepared = prepare_no_robots_rows((row,), count_tokens=lambda _text: 10)

    assert prepared.candidates[0]["task_family"] == "translation/language transformation"


def test_explicit_open_qa_math_can_override_the_broad_category() -> None:
    row = {
        "prompt_id": "source-4",
        "category": "Open QA",
        "messages": [
            {"role": "user", "content": "What is the square root of 81?"},
            {"role": "assistant", "content": "The square root of 81 is 9."},
        ],
    }

    prepared = prepare_no_robots_rows((row,), count_tokens=lambda _text: 10)

    assert prepared.candidates[0]["task_family"] == "math/data reasoning"
