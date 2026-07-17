"""Immutable response-generation provenance and corpus bindings for G7."""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from hashlib import sha256
from types import MappingProxyType

from im.generation.pinned_embedding import (
    EMBEDDING_SIMILARITY_THRESHOLD,
    PINNED_RESPONSE_EMBEDDING_IDENTITY,
    PINNED_RESPONSE_EMBEDDING_SCORER,
    PinnedEmbeddingIdentity,
    PinnedLexicalEmbeddingScorer,
)
from im.generation.response_contracts import (
    AnswerContract,
    AnswerQualityDiagnostics,
    serialize_neutral_generation_request,
    validate_response_kind_counts,
    validate_response_text,
)
from im.schema.actions import RespondAction

__all__ = (
    "GeneratedResponseAsset",
    "EmbeddingDiagnosticRun",
    "ResponseAssetBinding",
    "ResponseAssetError",
    "ResponseCorpusGateResult",
    "ResponseDraftSpec",
    "SimpleResponseProfile",
    "validate_response_corpus",
)

_REQUEST_FIELDS = frozenset({"teacher_visible_prefix", "invitation", "answer_contract"})
_CORPUS_ASSET_COUNT = 90
_SIMPLE_PROFILE_ASSET_COUNT = 10


class ResponseAssetError(ValueError):
    """A response asset or its corpus binding is invalid."""


@dataclass(frozen=True, slots=True)
class ResponseDraftSpec:
    """Ungenerated neutral-response specification."""

    invitation: str
    answer_contract: AnswerContract

    def __post_init__(self) -> None:
        # Let the closed request serializer own invitation and contract validation.
        serialize_neutral_generation_request("", self.invitation, self.answer_contract)


@dataclass(frozen=True, slots=True)
class GeneratedResponseAsset:
    """One candidate response and the exact neutral request that produced it."""

    draft: ResponseDraftSpec
    teacher_visible_prefix: str
    teacher_visible_prefix_bytes: bytes
    serialized_neutral_request: bytes
    serialized_neutral_request_sha256: str
    candidate_response: str

    def __post_init__(self) -> None:
        if not isinstance(self.draft, ResponseDraftSpec):
            raise TypeError("draft must be a ResponseDraftSpec")
        if not isinstance(self.teacher_visible_prefix, str):
            raise TypeError("teacher_visible_prefix must be a string")
        if not isinstance(self.teacher_visible_prefix_bytes, bytes):
            raise TypeError("teacher_visible_prefix_bytes must be bytes")
        if self.teacher_visible_prefix_bytes != self.teacher_visible_prefix.encode("utf-8"):
            raise ResponseAssetError("teacher-visible prefix bytes do not match its string")
        if not isinstance(self.serialized_neutral_request, bytes):
            raise TypeError("serialized_neutral_request must be bytes")
        if not isinstance(self.candidate_response, str):
            raise TypeError("candidate_response must be a string")

        try:
            payload = json.loads(self.serialized_neutral_request)
        except (TypeError, ValueError) as error:
            raise ResponseAssetError("serialized neutral request is not JSON") from error
        if not isinstance(payload, dict) or set(payload) != _REQUEST_FIELDS:
            raise ResponseAssetError("neutral request must contain only teacher-visible fields")

        expected = serialize_neutral_generation_request(
            self.teacher_visible_prefix,
            self.draft.invitation,
            self.draft.answer_contract,
        )
        if self.serialized_neutral_request != expected:
            raise ResponseAssetError("serialized neutral request does not match its draft")
        if self.serialized_neutral_request_sha256 != sha256(expected).hexdigest():
            raise ResponseAssetError("serialized neutral request hash does not match its bytes")

    @classmethod
    def create(
        cls,
        draft: ResponseDraftSpec,
        *,
        teacher_visible_prefix: str,
        candidate_response: str,
    ) -> GeneratedResponseAsset:
        """Build a checksum-bound asset from the exact neutral request."""
        if not isinstance(draft, ResponseDraftSpec):
            raise TypeError("draft must be a ResponseDraftSpec")
        request = serialize_neutral_generation_request(
            teacher_visible_prefix, draft.invitation, draft.answer_contract
        )
        return cls(
            draft=draft,
            teacher_visible_prefix=teacher_visible_prefix,
            teacher_visible_prefix_bytes=teacher_visible_prefix.encode("utf-8"),
            serialized_neutral_request=request,
            serialized_neutral_request_sha256=sha256(request).hexdigest(),
            candidate_response=candidate_response,
        )


@dataclass(frozen=True, slots=True)
class SimpleResponseProfile:
    """The bounded ten-asset simple-response profile."""

    assets: tuple[GeneratedResponseAsset, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.assets, tuple) or not all(
            isinstance(asset, GeneratedResponseAsset) for asset in self.assets
        ):
            raise TypeError("assets must be a tuple of GeneratedResponseAsset values")
        if len(self.assets) != _SIMPLE_PROFILE_ASSET_COUNT:
            raise ResponseAssetError("simple response profile must contain exactly 10 assets")


@dataclass(frozen=True, slots=True)
class ResponseAssetBinding:
    """One asset bound to the actual supervised respond action and its visible support."""

    asset: GeneratedResponseAsset
    action: RespondAction
    visible_support_by_event_id: Mapping[str, str]

    def __post_init__(self) -> None:
        if not isinstance(self.asset, GeneratedResponseAsset):
            raise TypeError("asset must be a GeneratedResponseAsset")
        if not isinstance(self.action, RespondAction):
            raise TypeError("action must be a RespondAction")
        if not isinstance(self.visible_support_by_event_id, Mapping):
            raise TypeError("visible_support_by_event_id must be a mapping")
        object.__setattr__(
            self,
            "visible_support_by_event_id",
            MappingProxyType(dict(self.visible_support_by_event_id)),
        )


@dataclass(frozen=True, slots=True)
class EmbeddingDiagnosticRun:
    """Pinned scorer identity and observed execution for one corpus gate."""

    identity: PinnedEmbeddingIdentity
    executed: bool
    comparison_count: int

    def __post_init__(self) -> None:
        if self.identity != PINNED_RESPONSE_EMBEDDING_IDENTITY:
            raise ResponseAssetError("response embedding scorer identity is not pinned")
        if not isinstance(self.executed, bool):
            raise TypeError("response embedding execution state must be boolean")
        if (
            isinstance(self.comparison_count, bool)
            or not isinstance(self.comparison_count, int)
            or self.comparison_count < 0
        ):
            raise ResponseAssetError("response embedding comparison count is invalid")
        if self.executed != (self.comparison_count > 0):
            raise ResponseAssetError(
                "response embedding execution state does not match comparisons"
            )

    def as_json_object(self) -> dict[str, object]:
        return {
            "diagnostic_type": "lexical_hashed_embedding_cosine",
            "is_neural_semantic_model": False,
            "threshold_exclusive": EMBEDDING_SIMILARITY_THRESHOLD,
            "executed": self.executed,
            "comparison_count": self.comparison_count,
            "scorer": self.identity.as_json_object(),
        }


@dataclass(frozen=True, slots=True)
class ResponseCorpusGateResult:
    """Successful corpus validation and its non-blocking diversity diagnostics."""

    bindings: tuple[ResponseAssetBinding, ...]
    diagnostics: tuple[AnswerQualityDiagnostics, ...]
    embedding_diagnostic: EmbeddingDiagnosticRun

    def __post_init__(self) -> None:
        if not isinstance(self.bindings, tuple) or not all(
            isinstance(binding, ResponseAssetBinding) for binding in self.bindings
        ):
            raise TypeError("bindings must be a tuple of ResponseAssetBinding values")
        if not isinstance(self.diagnostics, tuple) or not all(
            isinstance(diagnostic, AnswerQualityDiagnostics) for diagnostic in self.diagnostics
        ):
            raise TypeError("diagnostics must be a tuple of AnswerQualityDiagnostics values")
        if len(self.bindings) != len(self.diagnostics):
            raise ResponseAssetError("each response binding must have one diagnostic result")
        if not isinstance(self.embedding_diagnostic, EmbeddingDiagnosticRun):
            raise TypeError("embedding_diagnostic must be an EmbeddingDiagnosticRun")
        if not self.embedding_diagnostic.executed:
            raise ResponseAssetError("response embedding diagnostic did not execute")


def validate_response_corpus(
    bindings: Iterable[ResponseAssetBinding],
    *,
    embedding_scorer: PinnedLexicalEmbeddingScorer = PINNED_RESPONSE_EMBEDDING_SCORER,
) -> ResponseCorpusGateResult:
    """Validate the exact 90 supervised texts with non-blocking pinned diagnostics."""
    materialized = tuple(bindings)
    if not all(isinstance(binding, ResponseAssetBinding) for binding in materialized):
        raise TypeError("bindings must contain ResponseAssetBinding values")
    if len(materialized) != _CORPUS_ASSET_COUNT:
        raise ResponseAssetError("response corpus must contain exactly 90 asset/action bindings")
    if not isinstance(embedding_scorer, PinnedLexicalEmbeddingScorer):
        raise TypeError("embedding_scorer must be the pinned lexical embedding scorer")

    validate_response_kind_counts(binding.asset.draft.answer_contract for binding in materialized)
    previous_answers: list[str] = []
    diagnostics: list[AnswerQualityDiagnostics] = []
    comparison_count = 0

    def counted_embedding_scorer(left: str, right: str) -> float:
        nonlocal comparison_count
        comparison_count += 1
        return embedding_scorer(left, right)

    for binding in materialized:
        diagnostic = validate_response_text(
            binding.action.text,
            binding.asset.draft.answer_contract,
            visible_support_by_event_id=binding.visible_support_by_event_id,
            previous_answers=previous_answers,
            embedding_scorer=counted_embedding_scorer,
        )
        diagnostics.append(diagnostic)
        previous_answers.append(binding.action.text)
    return ResponseCorpusGateResult(
        materialized,
        tuple(diagnostics),
        EmbeddingDiagnosticRun(
            identity=embedding_scorer.identity,
            executed=comparison_count > 0,
            comparison_count=comparison_count,
        ),
    )
