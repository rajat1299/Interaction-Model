from __future__ import annotations

import json
from dataclasses import replace

import pytest

from im.assets.model import canonical_artifact_bytes
from im.generation.g7_response_assets import (
    GeneratedResponseAsset,
    ResponseAssetBinding,
    ResponseAssetError,
    ResponseDraftSpec,
    SimpleResponseProfile,
    validate_response_corpus,
)
from im.generation.g7_response_pipeline import (
    render_g7_response_corpus,
    validate_g7_teacher_response_texts,
)
from im.generation.pinned_embedding import PINNED_RESPONSE_EMBEDDING_SCORER
from im.generation.response_contracts import (
    AnswerContract,
    AnswerPoint,
    QualityFlag,
    ResponseContractError,
    ResponseKind,
)
from im.schema.actions import RespondAction


def _text(kind: ResponseKind, index: int) -> str:
    match kind:
        case ResponseKind.ORDINARY_GROUNDED:
            return f"Item {index} is ready."
        case ResponseKind.AMBIGUITY_CLARIFICATION:
            return f"Which item {index} do you mean?"
        case ResponseKind.UNSUPPORTED_FEATURE_LIMITATION:
            return f"I cannot export item {index}."
        case ResponseKind.FAILED_TOOL_NOTICE:
            return f"The lookup failed for item {index}."


def _asset(kind: ResponseKind, index: int) -> GeneratedResponseAsset:
    text = _text(kind, index)
    return GeneratedResponseAsset.create(
        ResponseDraftSpec(
            invitation="Please respond.",
            answer_contract=AnswerContract(
                response_kind=kind,
                subject_id=f"item-{index}",
                support_event_ids=("e_000002",),
                required_answer_points=(AnswerPoint((text,)),),
                forbidden_claims=("London",),
            ),
        ),
        teacher_visible_prefix=f"Visible item {index}",
        candidate_response=text,
    )


def _binding(asset: GeneratedResponseAsset, text: str | None = None) -> ResponseAssetBinding:
    text = asset.candidate_response if text is None else text
    return ResponseAssetBinding(
        asset,
        RespondAction(type="respond", reply_to_event_id="e_000002", text=text),
        {"e_000002": asset.candidate_response},
    )


def _with_contract(
    asset: GeneratedResponseAsset, contract: AnswerContract
) -> GeneratedResponseAsset:
    return GeneratedResponseAsset.create(
        ResponseDraftSpec(asset.draft.invitation, contract),
        teacher_visible_prefix=asset.teacher_visible_prefix,
        candidate_response=asset.candidate_response,
    )


def _corpus() -> tuple[ResponseAssetBinding, ...]:
    kinds = (
        *((ResponseKind.ORDINARY_GROUNDED,) * 50),
        *((ResponseKind.AMBIGUITY_CLARIFICATION,) * 15),
        *((ResponseKind.UNSUPPORTED_FEATURE_LIMITATION,) * 15),
        *((ResponseKind.FAILED_TOOL_NOTICE,) * 10),
    )
    return tuple(_binding(_asset(kind, index)) for index, kind in enumerate(kinds))


def test_asset_binds_exact_prefix_request_and_hash() -> None:
    asset = _asset(ResponseKind.ORDINARY_GROUNDED, 0)

    assert asset.teacher_visible_prefix_bytes == asset.teacher_visible_prefix.encode("utf-8")
    with pytest.raises(ResponseAssetError, match="prefix bytes"):
        replace(asset, teacher_visible_prefix_bytes=b"tampered")
    with pytest.raises(ResponseAssetError, match="does not match"):
        replace(asset, serialized_neutral_request=asset.serialized_neutral_request + b" ")
    with pytest.raises(ResponseAssetError, match="hash"):
        replace(asset, serialized_neutral_request_sha256="0" * 64)


def test_simple_response_profile_is_exactly_ten_assets() -> None:
    assets = tuple(_asset(ResponseKind.ORDINARY_GROUNDED, index) for index in range(10))

    assert len(SimpleResponseProfile(assets).assets) == 10
    with pytest.raises(ResponseAssetError, match="exactly 10"):
        SimpleResponseProfile(assets[:-1])


def test_corpus_gate_requires_exact_kind_distribution_and_actual_action_text() -> None:
    bindings = _corpus()

    result = validate_response_corpus(bindings)
    assert len(result.bindings) == 90
    with pytest.raises(ResponseAssetError, match="exactly 90"):
        validate_response_corpus(bindings[:-1])
    with pytest.raises(ResponseContractError, match="response-kind counts"):
        wrong_count = _binding(_asset(ResponseKind.ORDINARY_GROUNDED, 89))
        validate_response_corpus((*bindings[:-1], wrong_count))
    with pytest.raises(ResponseContractError, match="required answer point"):
        validate_response_corpus(
            (
                replace(bindings[0], action=bindings[0].action.model_copy(update={"text": "No."})),
                *bindings[1:],
            )
        )


def test_complete_response_review_artifact_is_canonical_and_keeps_all_ninety_rows() -> None:
    gate = validate_response_corpus(_corpus())
    rendered = render_g7_response_corpus(gate)
    payload = json.loads(rendered)

    assert len(payload["records"]) == 90
    assert gate.embedding_diagnostic.executed is True
    assert gate.embedding_diagnostic.comparison_count > 0
    assert payload["embedding_similarity"] == gate.embedding_diagnostic.as_json_object()
    assert payload["embedding_similarity"]["is_neural_semantic_model"] is False
    assert (
        payload["embedding_similarity"]["scorer"]
        == PINNED_RESPONSE_EMBEDDING_SCORER.identity.as_json_object()
    )
    assert rendered == canonical_artifact_bytes(payload)


def test_corpus_gate_can_rerun_after_teacher_replaces_valid_text() -> None:
    bindings = _corpus()
    original = bindings[0]
    final_text = "Item 0 is ready now."
    final = replace(
        original,
        action=original.action.model_copy(update={"text": final_text}),
        visible_support_by_event_id={"e_000002": final_text},
    )

    assert validate_response_corpus((final, *bindings[1:])).bindings[0].action.text == final_text


def test_corpus_gate_blocks_exact_duplicates_and_returns_near_duplicate_diagnostics() -> None:
    bindings = list(_corpus())
    first = bindings[0]
    second = bindings[1]
    duplicate_contract = replace(
        second.asset.draft.answer_contract,
        required_answer_points=(AnswerPoint((first.action.text,)),),
    )
    duplicate_asset = _with_contract(second.asset, duplicate_contract)
    bindings[1] = ResponseAssetBinding(
        duplicate_asset,
        second.action.model_copy(update={"text": first.action.text}),
        {"e_000002": first.action.text},
    )
    with pytest.raises(ResponseContractError, match="exact duplicate"):
        validate_response_corpus(bindings)

    near_first = "The report names Paris in the current summary."
    near_second = "The report names Paris in the current summary!"
    for index, text in enumerate((near_first, near_second)):
        binding = bindings[index]
        contract = replace(
            binding.asset.draft.answer_contract,
            required_answer_points=(AnswerPoint(("The report names Paris",)),),
        )
        asset = _with_contract(binding.asset, contract)
        bindings[index] = ResponseAssetBinding(
            asset,
            binding.action.model_copy(update={"text": text}),
            {"e_000002": f"{near_first} {near_second}"},
        )

    draft_gate = validate_response_corpus(bindings)
    diagnostics = draft_gate.diagnostics[1]
    assert QualityFlag.TOKEN_SIMILARITY in diagnostics.flags
    assert QualityFlag.EMBEDDING_SIMILARITY in diagnostics.flags

    final_gate = validate_g7_teacher_response_texts(
        draft_gate,
        {
            binding.asset.serialized_neutral_request_sha256: binding.action.text
            for binding in draft_gate.bindings
        },
    )
    assert QualityFlag.EMBEDDING_SIMILARITY in final_gate.diagnostics[1].flags
    assert final_gate.embedding_diagnostic.executed is True
    assert final_gate.embedding_diagnostic.identity == PINNED_RESPONSE_EMBEDDING_SCORER.identity
