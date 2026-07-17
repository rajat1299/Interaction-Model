from __future__ import annotations

import json
from dataclasses import FrozenInstanceError, replace

import pytest

from im.generation.response_contracts import (
    AnswerContract,
    AnswerPoint,
    ProtectedClaimScope,
    QualityFlag,
    ResponseContractError,
    ResponseKind,
    neutral_generation_payload,
    serialize_neutral_generation_request,
    validate_response_kind_counts,
    validate_response_text,
)


def _contract(kind: ResponseKind = ResponseKind.ORDINARY_GROUNDED) -> AnswerContract:
    point = {
        ResponseKind.ORDINARY_GROUNDED: "The report names Paris.",
        ResponseKind.AMBIGUITY_CLARIFICATION: "Which Paris report do you mean?",
        ResponseKind.UNSUPPORTED_FEATURE_LIMITATION: "I cannot export the report.",
        ResponseKind.FAILED_TOOL_NOTICE: "The lookup failed.",
    }[kind]
    return AnswerContract(
        response_kind=kind,
        subject_id="paris-report",
        support_event_ids=("e_000002",),
        required_answer_points=(AnswerPoint((point,)),),
        forbidden_claims=("London",),
    )


def _support() -> dict[str, str]:
    return {"e_000002": "The report names Paris. The lookup failed."}


def test_contract_is_closed_and_immutable() -> None:
    contract = _contract()

    assert contract.response_kind is ResponseKind.ORDINARY_GROUNDED
    with pytest.raises(FrozenInstanceError):
        contract.subject_id = "other"  # type: ignore[misc]
    with pytest.raises(ResponseContractError, match="not closed"):
        replace(contract, response_kind="open-ended")
    with pytest.raises(ResponseContractError, match="immutable tuple"):
        replace(contract, support_event_ids=["e_000002"])  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("kind", "text"),
    (
        (ResponseKind.ORDINARY_GROUNDED, "The report names Paris."),
        (ResponseKind.AMBIGUITY_CLARIFICATION, "Which Paris report do you mean?"),
        (ResponseKind.UNSUPPORTED_FEATURE_LIMITATION, "I cannot export the report."),
        (ResponseKind.FAILED_TOOL_NOTICE, "The lookup failed."),
    ),
)
def test_each_closed_kind_can_validate(kind: ResponseKind, text: str) -> None:
    assert validate_response_text(
        text, _contract(kind), visible_support_by_event_id=_support()
    ).is_clear


@pytest.mark.parametrize(
    ("kind", "text", "message"),
    (
        (ResponseKind.ORDINARY_GROUNDED, "Which Paris report do you mean?", "not ask a question"),
        (
            ResponseKind.AMBIGUITY_CLARIFICATION,
            "The Paris report is unclear.",
            "exactly one question",
        ),
        (ResponseKind.UNSUPPORTED_FEATURE_LIMITATION, "The report is ready.", "state a limitation"),
        (ResponseKind.FAILED_TOOL_NOTICE, "The lookup is complete.", "state the failure"),
    ),
)
def test_kind_specific_constraints_are_not_optional(
    kind: ResponseKind, text: str, message: str
) -> None:
    contract = replace(_contract(kind), required_answer_points=(AnswerPoint((text,)),))
    with pytest.raises(ResponseContractError, match=message):
        validate_response_text(text, contract, visible_support_by_event_id=_support())


def test_text_checks_require_points_forbid_claims_and_ground_introductions() -> None:
    contract = _contract()

    with pytest.raises(ResponseContractError, match="required answer point"):
        validate_response_text(
            "Paris is mentioned.", contract, visible_support_by_event_id=_support()
        )
    with pytest.raises(ResponseContractError, match="forbidden"):
        validate_response_text(
            "The report names Paris and London.", contract, visible_support_by_event_id=_support()
        )
    with pytest.raises(ResponseContractError, match="unsupported entity"):
        validate_response_text(
            "The report names Paris and Berlin.",
            replace(contract, required_answer_points=(AnswerPoint(("The report names Paris",)),)),
            visible_support_by_event_id=_support(),
        )
    assert validate_response_text(
        "The report names Paris and Berlin.",
        replace(
            contract,
            required_answer_points=(AnswerPoint(("The report names Paris",)),),
            grounding_allowlist=("Berlin",),
        ),
        visible_support_by_event_id=_support(),
    ).is_clear


def test_protected_claim_scopes_are_closed_and_require_negative_refusals() -> None:
    contract = replace(
        _contract(ResponseKind.UNSUPPORTED_FEATURE_LIMITATION),
        required_answer_points=(
            AnswerPoint(("I cannot schedule reminders for a specific clock time",)),
        ),
        protected_claim_scope=ProtectedClaimScope.CALENDAR_TIMER,
    )

    assert contract.protected_claim_scope is ProtectedClaimScope.CALENDAR_TIMER
    with pytest.raises(ResponseContractError, match="not closed"):
        replace(contract, protected_claim_scope="open-ended")
    with pytest.raises(ResponseContractError, match="accepted negative refusals"):
        replace(
            contract,
            required_answer_points=(AnswerPoint(("specific-clock reminders are supported",)),),
        )


def test_text_checks_limit_size_block_meta_leaks_and_hard_fail_exact_duplicates() -> None:
    contract = _contract()

    with pytest.raises(ResponseContractError, match="non-blank"):
        validate_response_text(" ", contract, visible_support_by_event_id=_support())
    with pytest.raises(ResponseContractError, match="metadata"):
        validate_response_text(
            "The answer contract says the report names Paris.",
            contract,
            visible_support_by_event_id=_support(),
        )
    with pytest.raises(ResponseContractError, match="normalized exact duplicate"):
        validate_response_text(
            "the  report names Paris.",
            contract,
            visible_support_by_event_id=_support(),
            previous_answers=("The report names Paris.",),
        )


def test_text_checks_enforce_word_and_sentence_limits_and_exact_number_grounding() -> None:
    contract = replace(
        _contract(),
        required_answer_points=(AnswerPoint(("Paris",)),),
    )
    with pytest.raises(ResponseContractError, match="1-40 words"):
        validate_response_text(
            ("Paris " * 41).strip(),
            contract,
            visible_support_by_event_id=_support(),
        )
    with pytest.raises(ResponseContractError, match="at most two sentences"):
        validate_response_text(
            "Paris. Paris. Paris.",
            contract,
            visible_support_by_event_id=_support(),
        )
    with pytest.raises(ResponseContractError, match="unsupported entity or number"):
        validate_response_text(
            "Paris has 42 entries.",
            contract,
            visible_support_by_event_id=_support(),
        )
    assert validate_response_text(
        "Paris has 42 entries.",
        replace(contract, grounding_allowlist=("42",)),
        visible_support_by_event_id=_support(),
    ).is_clear


def test_subtype_rules_block_bundled_answers_boilerplate_and_retry_promises() -> None:
    clarification = replace(
        _contract(ResponseKind.AMBIGUITY_CLARIFICATION),
        required_answer_points=(AnswerPoint(("Which Paris report",)),),
    )
    with pytest.raises(ResponseContractError, match="exactly one question"):
        validate_response_text(
            "The report names Paris. Which Paris report do you mean?",
            clarification,
            visible_support_by_event_id=_support(),
        )

    limitation = _contract(ResponseKind.UNSUPPORTED_FEATURE_LIMITATION)
    curly_limitation = "I can’t export the report."
    assert validate_response_text(
        curly_limitation,
        replace(
            limitation,
            required_answer_points=(AnswerPoint((curly_limitation,)),),
        ),
        visible_support_by_event_id=_support(),
    ).is_clear
    with pytest.raises(ResponseContractError, match="apology boilerplate"):
        validate_response_text(
            "Sorry, I cannot export the report.",
            limitation,
            visible_support_by_event_id=_support(),
        )
    with pytest.raises(ResponseContractError, match="schedule or approximation"):
        validate_response_text(
            "I cannot export the report, but I will schedule it.",
            limitation,
            visible_support_by_event_id=_support(),
        )
    with pytest.raises(ResponseContractError, match="schedule or approximation"):
        validate_response_text(
            "I cannot export the report, but it will be ready around noon.",
            limitation,
            visible_support_by_event_id=_support(),
        )

    failed = _contract(ResponseKind.FAILED_TOOL_NOTICE)
    with pytest.raises(ResponseContractError, match="automatic retry"):
        validate_response_text(
            "The lookup failed, but it will retry automatically.",
            failed,
            visible_support_by_event_id=_support(),
        )


def test_failed_tool_text_cannot_echo_a_tautological_adapter_error_clause() -> None:
    contract = AnswerContract(
        response_kind=ResponseKind.FAILED_TOOL_NOTICE,
        subject_id="morrow-glen-cistern-fill",
        support_event_ids=("e_000005", "e_000008"),
        required_answer_points=(
            AnswerPoint(("Morrow Glen cistern fill percentage",)),
            AnswerPoint(("no usable answer", "lookup failed")),
        ),
        forbidden_claims=(),
    )
    support = {
        "e_000005": "Morrow Glen cistern fill percentage",
        "e_000008": "lookup failed",
    }

    with pytest.raises(ResponseContractError, match="tautological colon clause"):
        validate_response_text(
            "The lookup for Morrow Glen cistern fill percentage failed: lookup failed.",
            contract,
            visible_support_by_event_id=support,
        )
    assert validate_response_text(
        "The Morrow Glen cistern fill percentage lookup failed, so no usable answer came back.",
        contract,
        visible_support_by_event_id=support,
    ).is_clear


def test_similarity_signals_are_diagnostics_and_embedding_is_injected() -> None:
    contract = _contract()
    previous = (
        "The report names Paris in the current summary.",
        "The report names Paris in the current summary now.",
        "The report names Paris in the current summary today.",
    )
    text = "The report names Paris in the current summary clearly."
    contract = replace(contract, required_answer_points=(AnswerPoint(("The report names Paris",)),))

    diagnostics = validate_response_text(
        text,
        contract,
        visible_support_by_event_id=_support(),
        previous_answers=previous,
        embedding_scorer=lambda _left, _right: 0.93,
    )

    assert set(diagnostics.flags) == {
        QualityFlag.EIGHT_GRAM_OVERUSE,
        QualityFlag.TOKEN_SIMILARITY,
        QualityFlag.CHAR_FIVE_GRAM_JACCARD,
        QualityFlag.OPENING_FOUR_GRAM_OVERUSE,
        QualityFlag.EMBEDDING_SIMILARITY,
    }


def test_repeated_8gram_in_one_previous_reply_does_not_fake_corpus_overuse() -> None:
    contract = replace(
        _contract(),
        required_answer_points=(AnswerPoint(("The report names Paris",)),),
    )
    repeated = "The report names Paris in the current summary"

    diagnostics = validate_response_text(
        f"{repeated} clearly.",
        contract,
        visible_support_by_event_id=_support(),
        previous_answers=(f"{repeated}. {repeated}. {repeated}.",),
    )

    assert QualityFlag.EIGHT_GRAM_OVERUSE not in diagnostics.flags


def test_token_similarity_preserves_token_order() -> None:
    contract = replace(
        _contract(),
        required_answer_points=(AnswerPoint(("The report names Paris",)),),
    )

    diagnostics = validate_response_text(
        "The report names Paris today.",
        contract,
        visible_support_by_event_id=_support(),
        previous_answers=("Paris today names report The.",),
    )

    assert QualityFlag.TOKEN_SIMILARITY not in diagnostics.flags


def test_exact_subtype_distribution_is_enforced() -> None:
    contracts = tuple(
        _contract(kind)
        for kind, count in (
            (ResponseKind.ORDINARY_GROUNDED, 50),
            (ResponseKind.AMBIGUITY_CLARIFICATION, 15),
            (ResponseKind.UNSUPPORTED_FEATURE_LIMITATION, 15),
            (ResponseKind.FAILED_TOOL_NOTICE, 10),
        )
        for _ in range(count)
    )

    validate_response_kind_counts(contracts)
    with pytest.raises(ResponseContractError, match="counts"):
        validate_response_kind_counts(contracts[:-1])


def test_neutral_request_serialization_has_only_teacher_visible_fields() -> None:
    contract = replace(
        _contract(ResponseKind.UNSUPPORTED_FEATURE_LIMITATION),
        required_answer_points=(
            AnswerPoint(("I cannot schedule reminders for a specific clock time",)),
        ),
        protected_claim_scope=ProtectedClaimScope.CALENDAR_TIMER,
    )
    payload = neutral_generation_payload("exact prefix", "Please respond.", contract)
    serialized = json.loads(
        serialize_neutral_generation_request("exact prefix", "Please respond.", contract)
    )

    assert set(payload) == {"teacher_visible_prefix", "invitation", "answer_contract"}
    assert "protected_claim_scope" not in payload
    assert payload["answer_contract"]["protected_claim_scope"] == "calendar_timer"
    assert serialized == payload
    assert "oracle" not in json.dumps(payload).casefold()
