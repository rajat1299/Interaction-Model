from __future__ import annotations

import base64
import struct

import pytest

from im.training.phase3r import (
    D10_ACTION_COUNTS,
    Phase3RError,
    append_supervised_terminal,
    canonical_d10_metrics,
    classify_span_action,
    derive_rank16_replay_coefficient,
    high_confidence_first_person_refusal,
    repeated_ngram_signature,
    retention_catastrophe,
    reweight_terminal_replay_datum,
    strict_interaction_action_json,
    summarize_terminal_target_audit,
    terminal_target_audit_row,
)


def _datum(kind: str, weight: float) -> dict[str, object]:
    weights = [0.0, weight, weight]
    return {
        "datum_id": f"{kind}:example",
        "input_tokens": [10, 20, 30],
        "kind": kind,
        "positive_token_count": 2,
        "target_tokens": [20, 30, 40],
        "weights": weights,
        "weights_float32_le_base64": base64.b64encode(
            b"".join(struct.pack("<f", value) for value in weights)
        ).decode("ascii"),
    }


@pytest.mark.parametrize(("kind", "weight"), [("interaction", 1.0), ("replay", 0.3)])
def test_terminal_transform_appends_one_weighted_target(kind: str, weight: float) -> None:
    original = _datum(kind, weight)
    amended = append_supervised_terminal(original)

    assert amended["input_tokens"] == [10, 20, 30, 40]
    assert amended["target_tokens"] == [20, 30, 40, 248046]
    assert amended["weights"] == [0.0, weight, weight, weight]
    assert amended["positive_token_count"] == 3
    assert original["target_tokens"] == [20, 30, 40]
    audit = terminal_target_audit_row(amended)
    assert audit["positive_terminal_token_count"] == 1
    assert audit["expected_final_terminal_decoded"] == "<|im_end|>"
    assert audit["final_terminal_loss_weight_float32_bits"] == (
        "0x3f800000" if kind == "interaction" else "0x3e99999a"
    )
    assert audit["tokens_after_final_positive_token_count"] == 0


def test_terminal_audit_requires_exact_frozen_inventory() -> None:
    interaction = terminal_target_audit_row(_datum("interaction", 1.0))
    replay = terminal_target_audit_row(_datum("replay", 0.3))
    with pytest.raises(Phase3RError, match="3,000"):
        summarize_terminal_target_audit([interaction, replay])


def test_rank16_replay_reweight_hits_frozen_40_percent_target() -> None:
    coefficient = derive_rank16_replay_coefficient(71_204, 101_003)
    assert coefficient == 0.4699794352054596
    assert struct.unpack("<I", struct.pack("<f", coefficient))[0] == 0x3EF0A125
    share = 101_003 * coefficient / (71_204 + 101_003 * coefficient)
    assert share == pytest.approx(0.4, abs=3e-9)

    terminal = append_supervised_terminal(_datum("replay", 0.3))
    amended = reweight_terminal_replay_datum(terminal, coefficient)
    assert amended["input_tokens"] == terminal["input_tokens"]
    assert amended["target_tokens"] == terminal["target_tokens"]
    assert amended["weights"] == [0.0, coefficient, coefficient, coefficient]
    assert amended["positive_token_count"] == terminal["positive_token_count"]
    assert terminal["weights"] == [0.0, 0.3, 0.3, 0.3]


def test_canonical_d10_denominator_is_exactly_123() -> None:
    states = []
    grades = []
    for action, count in D10_ACTION_COUNTS.items():
        for index in range(count):
            state_id = f"dev:{action}:{index}"
            states.append({"action_type": action, "state_id": state_id})
            grades.append({"executed": {"match": index > 0}, "state_id": state_id})
    metrics = canonical_d10_metrics(states, grades)
    assert metrics["denominator"] == 34 + 21 + 18 + 14 + 9 + 27 == 123
    assert metrics["success_count"] == 117


def test_canonical_d10_requires_sealed_semantic_assessment() -> None:
    states = []
    grades = []
    integrate_id = "dev:integrate:0"
    for action, count in D10_ACTION_COUNTS.items():
        for index in range(count):
            state_id = f"dev:{action}:{index}"
            states.append({"action_type": action, "state_id": state_id})
            grade: dict[str, object] = {
                "executed": {"match": True},
                "state_id": state_id,
            }
            if state_id == integrate_id:
                grade = {
                    "executed": {
                        "match": False,
                        "semantic_status": "pending_semantic_assessment",
                    },
                    "state_id": state_id,
                    "structural": {"structural_pass": True},
                }
            grades.append(grade)

    with pytest.raises(Phase3RError, match="semantic assessment is missing"):
        canonical_d10_metrics(states, grades)
    metrics = canonical_d10_metrics(states, grades, semantic_pass_by_state={integrate_id: True})
    assert metrics["success_count"] == 123


def test_repetition_and_catastrophic_stop_are_mechanical() -> None:
    loop = list(range(16)) * 3
    signature = repeated_ngram_signature(loop)
    assert signature == {
        "first_positions": [0, 16, 32],
        "ngram_width_tokens": 16,
        "period_tokens": 16,
        "repeat_count": 3,
    }
    rows = [
        {
            "new_length_termination": True,
            "repetition_signature": signature,
        },
        {
            "new_length_termination": True,
            "repetition_signature": signature,
        },
        *({} for _ in range(10)),
    ]
    result = retention_catastrophe(rows)
    assert result["abort_optimizer"] is True
    assert result["reasons"] == [
        "two_or_more_new_length_terminations",
        "repetition_signatures_in_two_or_more_rows",
    ]

    same_group = retention_catastrophe(
        [
            {"empty_output": True},
            {"empty_output": True},
            {"high_confidence_refusal": True},
            {"high_confidence_refusal": True},
            *({} for _ in range(8)),
        ]
    )
    assert same_group["abort_optimizer"] is True
    assert same_group["reasons"] == [
        "two_or_more_whitespace_empty_outputs",
        "two_or_more_high_confidence_first_person_refusals",
    ]

    with pytest.raises(Phase3RError, match="all 12"):
        retention_catastrophe([{}])


def test_retention_protocol_and_refusal_detectors_are_narrow() -> None:
    assert strict_interaction_action_json(
        '{"type":"idle","reason":"no_trigger","related_event_id":null}'
    )
    assert not strict_interaction_action_json('{"type":"idle"}')
    assert not strict_interaction_action_json(
        'Here is JSON: {"type":"idle","reason":"no_trigger","related_event_id":null}'
    )
    assert high_confidence_first_person_refusal("I cannot answer that request.")
    assert not high_confidence_first_person_refusal("The source cannot establish the date.")


def test_span_decomposition_preserves_strict_and_canonicalizable_results() -> None:
    expected = {
        "args": {"query": "red fox"},
        "fact": {
            "end_utf16": 11,
            "event_id": "e_000002",
            "start_utf16": 4,
            "text": "red fox",
        },
        "tool": "lookup",
        "type": "delegate",
    }
    predicted = {
        **expected,
        "fact": {**expected["fact"], "start_utf16": 3, "end_utf16": 12},
    }
    result = classify_span_action(
        expected,
        predicted,
        {"e_000002": "see red fox."},
        strict_action_match=False,
    )
    assert result["primary_category"] == "correct_occurrence_offset_only"
    assert result["canonicalizable"] is True
    assert result["strict_action_match"] is False


def test_span_decomposition_detects_wrong_repeated_occurrence() -> None:
    expected = {
        "args": {"query": "fox"},
        "fact": {
            "end_utf16": 3,
            "event_id": "e_000002",
            "start_utf16": 0,
            "text": "fox",
        },
        "tool": "lookup",
        "type": "delegate",
    }
    predicted = {
        **expected,
        "fact": {**expected["fact"], "start_utf16": 4, "end_utf16": 7},
    }
    result = classify_span_action(
        expected,
        predicted,
        {"e_000002": "fox fox"},
        strict_action_match=False,
    )
    assert result["primary_category"] == "wrong_repeated_occurrence"
    assert result["canonicalizable"] is False


def test_span_decomposition_never_canonicalizes_nonunique_text() -> None:
    expected = {
        "args": {"query": "red fox"},
        "fact": {
            "end_utf16": 11,
            "event_id": "e_000002",
            "start_utf16": 4,
            "text": "red fox",
        },
        "tool": "lookup",
        "type": "delegate",
    }
    predicted = {
        **expected,
        "fact": {**expected["fact"], "start_utf16": 3, "end_utf16": 12},
    }
    result = classify_span_action(
        expected,
        predicted,
        {"e_000002": "see red fox; red fox"},
        strict_action_match=False,
    )
    assert result["canonicalizable"] is False

    strict = classify_span_action(
        expected,
        expected,
        {"e_000002": "red fox; red fox"},
        strict_action_match=True,
    )
    assert strict["primary_category"] == "fully_strict"
    assert strict["strict_action_match"] is True
    assert strict["canonicalizable"] is False
