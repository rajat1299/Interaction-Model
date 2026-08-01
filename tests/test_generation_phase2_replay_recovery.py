from collections import Counter

from im.assets.model import artifact_digest
from im.generation.phase2_replay_recovery import (
    CALL_TARGETS,
    PILOT_TARGETS,
    contract_id_for,
    synthetic_topup_rows,
)


def _row(family: str, prompt: str, *, multi: bool = False) -> dict[str, object]:
    return {
        "dataset_source_id": "OpenAssistant/oasst2",
        "is_multi_turn": multi,
        "origin": "human_source",
        "task_family": family,
        "user_turns": [prompt],
    }


def test_recovery_matrices_and_synthetic_policy() -> None:
    assert sum(CALL_TARGETS.values()) == 722
    assert sum(PILOT_TARGETS.values()) == 96
    assert (
        sum(count for (_family, band, _turn), count in PILOT_TARGETS.items() if band == "short")
        == 75
    )
    assert (
        sum(count for (_family, band, _turn), count in PILOT_TARGETS.items() if band == "medium")
        == 21
    )
    assert (
        sum(count for (_family, _band, turn), count in PILOT_TARGETS.items() if turn == "multi")
        == 8
    )

    rows = synthetic_topup_rows()
    assert Counter(row["task_family"] for row in rows) == {
        "coding/debug": 155,
        "math/data reasoning": 191,
        "practical planning": 156,
        "rewrite/edit/summarize": 135,
        "translation/language transformation": 20,
    }
    assert all(row["origin"] == "synthetic_topup" for row in rows)
    assert all(not row["is_multi_turn"] for row in rows)
    assert all(row["dataset_source_role"] == "synthetic" for row in rows)
    assert not any(row["task_family"] == "refusal/uncertainty/missing-information" for row in rows)
    assert any(contract_id_for(row, "short") for row in rows)
    assert any(contract_id_for(row, "medium") for row in rows)
    assert all(
        row["prompt_id"]
        == artifact_digest(
            {
                "category": row["source_category"],
                "prompt": row["user_turns"][0],
            }
        ).removeprefix("sha256:")[:32]
        for row in rows
    )


def test_contracts_reject_materialized_scope_mismatches() -> None:
    assert (
        contract_id_for(
            _row("coding/debug", "Create a Svelte app for tracking daily tasks."),
            "medium",
        )
        is None
    )
    for prompt in (
        "Write one 150-word paragraph and another 150-word paragraph.",
        "Please answer in about 100 words.",
    ):
        assert contract_id_for(_row("light creative/casual", prompt), "short") is None
    assert (
        contract_id_for(
            _row(
                "rewrite/edit/summarize",
                "I will rephrase. What happens when salt is put on a chair?",
                multi=True,
            ),
            "medium",
        )
        is None
    )
    for prompt in (
        "Please rewrite all of the steps into a bullet point list.",
        "Can you rewrite it in Java?",
        "Now rewrite it in Python3.",
        "Can you summarize it in only one sentence?",
        "Do not rewrite the paragraphs; only remove one sentence from each.",
        "Could you rewrite that using proper formula formating?",
        "Rephrase the tweet to sound more professional.",
    ):
        assert contract_id_for(_row("rewrite/edit/summarize", prompt, multi=True), "medium") is None
    assert (
        contract_id_for(
            _row(
                "rewrite/edit/summarize",
                "Summarize https://example.com/video",
                multi=True,
            ),
            "short",
        )
        is None
    )
    assert (
        contract_id_for(
            _row(
                "rewrite/edit/summarize",
                "Summarize each section in two or three sentences.",
                multi=True,
            ),
            "short",
        )
        is None
    )
    assert (
        contract_id_for(
            _row(
                "coding/debug",
                "Give 3 use cases, write an example script, and explain how it works.",
                multi=True,
            ),
            "short",
        )
        is None
    )
    assert (
        contract_id_for(
            _row(
                "evidence-grounded comparison/recommendation",
                "Compare two engines. " + "Define and contrast every property. " * 30,
            ),
            "short",
        )
        is None
    )
    assert (
        contract_id_for(
            _row(
                "light creative/casual",
                "Write an average length poem naming at least three Java EE servers.",
            ),
            "short",
        )
        is None
    )
    for prompt in (
        "What is the typical market price for this tank?",
        "What is the tobacco consumption trend since 1990? Provide sources.",
        "What are ISO compliant crypto currencies?",
        "Who is the prime minister of India?",
        "Who was Else Schmitz-Gohr?",
        "What is the Nehemiah Hubbard House?",
        "How many moons orbit Jupiter?",
        "What is your biggest pet peeve?",
    ):
        assert contract_id_for(_row("stable-knowledge explanation", prompt), "short") is None
