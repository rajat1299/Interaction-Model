"""Closed neutral-generation metadata for response text, never policy input."""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from difflib import SequenceMatcher
from enum import StrEnum
from math import isfinite
from re import escape, findall, finditer, fullmatch, search

from im.generation.pinned_embedding import EMBEDDING_SIMILARITY_THRESHOLD

__all__ = (
    "AnswerContract",
    "AnswerPoint",
    "AnswerQualityDiagnostics",
    "EXPECTED_RESPONSE_KIND_COUNTS",
    "QualityFlag",
    "ProtectedClaimScope",
    "RequiredAnswerPoint",
    "ResponseContractError",
    "ResponseKind",
    "neutral_generation_payload",
    "serialize_neutral_generation_request",
    "validate_response_kind_counts",
    "validate_response_text",
)

_SUBJECT_ID = r"[a-z][a-z0-9_-]{0,127}"
_WORD = r"[^\W_]+(?:['’][^\W_]+)*"
_NUMBER = r"\d+(?:[,.]\d+)*%?"
_WORD_TOKENS = rf"{_WORD}|{_NUMBER}"
_NAMED_ENTITY = r"\b(?:[A-Z][a-z]+|[A-Z]{2,}(?:-[A-Z0-9]+)*)\b"
_META_LEAK = (
    "answer contract",
    "instruction",
    "label",
    "metadata",
    "oracle",
    "prompt",
    "review metadata",
    "system message",
    "teacher-visible",
)
_NON_ENTITIES = frozenset(
    {
        "A",
        "An",
        "And",
        "As",
        "But",
        "Can",
        "Could",
        "Do",
        "For",
        "Here",
        "How",
        "I",
        "If",
        "In",
        "It",
        "No",
        "Please",
        "Sorry",
        "The",
        "That",
        "These",
        "This",
        "Those",
        "To",
        "We",
        "What",
        "When",
        "Where",
        "Which",
        "Who",
        "Why",
        "You",
        "Your",
    }
)


class ResponseContractError(ValueError):
    """A response or its closed contract is invalid."""


class ResponseKind(StrEnum):
    ORDINARY_GROUNDED = "ordinary_grounded"
    AMBIGUITY_CLARIFICATION = "ambiguity_clarification"
    UNSUPPORTED_FEATURE_LIMITATION = "unsupported_feature_limitation"
    FAILED_TOOL_NOTICE = "failed_tool_notice"


class ProtectedClaimScope(StrEnum):
    """Closed scopes whose protected concepts require explicit refusals."""

    CALENDAR_TIMER = "calendar_timer"


class QualityFlag(StrEnum):
    EIGHT_GRAM_OVERUSE = "8gram_overuse"
    TOKEN_SIMILARITY = "token_similarity"
    CHAR_FIVE_GRAM_JACCARD = "char_5gram_jaccard"
    OPENING_FOUR_GRAM_OVERUSE = "opening_4gram_overuse"
    EMBEDDING_SIMILARITY = "embedding_similarity"


EXPECTED_RESPONSE_KIND_COUNTS: Mapping[ResponseKind, int] = {
    ResponseKind.ORDINARY_GROUNDED: 50,
    ResponseKind.AMBIGUITY_CLARIFICATION: 15,
    ResponseKind.UNSUPPORTED_FEATURE_LIMITATION: 15,
    ResponseKind.FAILED_TOOL_NOTICE: 10,
}

_APPROVED_PROTECTED_SCOPE_RESPONSES: Mapping[ProtectedClaimScope, tuple[str, ...]] = {
    ProtectedClaimScope.CALENDAR_TIMER: (
        "I can’t add calendar events or schedule reminders for a specific clock time. "
        "I can only set indefinite fixed-interval recurring reminders.",
        "I cannot add calendar events. I cannot schedule reminders for a specific clock time; "
        "only indefinite fixed-interval recurring reminders are available.",
        "I can’t add calendar events. I can’t schedule reminders for a specific clock time; "
        "I can only set indefinite reminders that repeat at a fixed interval.",
    ),
}


@dataclass(frozen=True, slots=True)
class RequiredAnswerPoint:
    """One required idea, expressed by one explicit accepted alternative."""

    accepted_alternatives: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_phrases(self.accepted_alternatives, "accepted_alternatives")
        if len(set(self.accepted_alternatives)) != len(self.accepted_alternatives):
            raise ResponseContractError("accepted_alternatives must be unique")

    def as_json_object(self) -> dict[str, object]:
        return {"accepted_alternatives": list(self.accepted_alternatives)}


AnswerPoint = RequiredAnswerPoint


@dataclass(frozen=True, slots=True)
class AnswerContract:
    """Immutable neutral-generation metadata, never used as policy input."""

    response_kind: ResponseKind | str
    subject_id: str
    support_event_ids: tuple[str, ...]
    required_answer_points: tuple[RequiredAnswerPoint, ...]
    forbidden_claims: tuple[str, ...]
    grounding_allowlist: tuple[str, ...] = ()
    protected_claim_scope: ProtectedClaimScope | str | None = None

    def __post_init__(self) -> None:
        try:
            kind = ResponseKind(self.response_kind)
        except (TypeError, ValueError) as error:
            raise ResponseContractError("response_kind is not closed") from error
        if not isinstance(self.subject_id, str) or fullmatch(_SUBJECT_ID, self.subject_id) is None:
            raise ResponseContractError("subject_id must be a stable lowercase identifier")
        _require_identifiers(self.support_event_ids, "support_event_ids")
        if not isinstance(self.required_answer_points, tuple) or not self.required_answer_points:
            raise ResponseContractError(
                "required_answer_points must be a non-empty immutable tuple"
            )
        if not all(isinstance(point, RequiredAnswerPoint) for point in self.required_answer_points):
            raise TypeError("required_answer_points must contain RequiredAnswerPoint values")
        _require_phrases(self.forbidden_claims, "forbidden_claims", allow_empty=True)
        _require_phrases(self.grounding_allowlist, "grounding_allowlist", allow_empty=True)
        scope = None
        if self.protected_claim_scope is not None:
            try:
                scope = ProtectedClaimScope(self.protected_claim_scope)
            except (TypeError, ValueError) as error:
                raise ResponseContractError("protected_claim_scope is not closed") from error
            if kind is not ResponseKind.UNSUPPORTED_FEATURE_LIMITATION:
                raise ResponseContractError(
                    "protected_claim_scope requires unsupported-feature response"
                )
            _validate_protected_scope_contract(scope, self.required_answer_points)
        object.__setattr__(self, "response_kind", kind)
        object.__setattr__(self, "protected_claim_scope", scope)

    def as_json_object(self) -> dict[str, object]:
        result = {
            "response_kind": self.response_kind.value,
            "subject_id": self.subject_id,
            "support_event_ids": list(self.support_event_ids),
            "required_answer_points": [
                point.as_json_object() for point in self.required_answer_points
            ],
            "forbidden_claims": list(self.forbidden_claims),
            "grounding_allowlist": list(self.grounding_allowlist),
        }
        if self.protected_claim_scope is not None:
            result["protected_claim_scope"] = self.protected_claim_scope.value
        return result


@dataclass(frozen=True, slots=True)
class AnswerQualityDiagnostics:
    """Non-blocking corpus-quality signals for one otherwise valid response."""

    flags: tuple[QualityFlag, ...] = ()

    @property
    def is_clear(self) -> bool:
        return not self.flags


def neutral_generation_payload(
    teacher_visible_prefix: str,
    invitation: str,
    answer_contract: AnswerContract,
) -> dict[str, object]:
    """Return the only metadata exposed to the neutral response generator."""
    if not isinstance(teacher_visible_prefix, str):
        raise TypeError("teacher_visible_prefix must be a string")
    if not isinstance(invitation, str) or not invitation.strip():
        raise ResponseContractError("invitation must be a non-blank string")
    if not isinstance(answer_contract, AnswerContract):
        raise TypeError("answer_contract must be an AnswerContract")
    return {
        "teacher_visible_prefix": teacher_visible_prefix,
        "invitation": invitation,
        "answer_contract": answer_contract.as_json_object(),
    }


def serialize_neutral_generation_request(
    teacher_visible_prefix: str,
    invitation: str,
    answer_contract: AnswerContract,
) -> bytes:
    """Serialize only the visible prefix, invitation, and answer contract."""
    return json.dumps(
        neutral_generation_payload(teacher_visible_prefix, invitation, answer_contract),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()


def validate_response_text(
    text: str,
    answer_contract: AnswerContract,
    *,
    visible_support_by_event_id: Mapping[str, str],
    previous_answers: Iterable[str] = (),
    embedding_scorer: Callable[[str, str], float] | None = None,
) -> AnswerQualityDiagnostics:
    """Validate generated text or the final labelled ``respond.text`` with one path."""
    if not isinstance(text, str) or text.strip() != text or not text:
        raise ResponseContractError("response text must be a non-blank trimmed string")
    if not isinstance(answer_contract, AnswerContract):
        raise TypeError("answer_contract must be an AnswerContract")
    if not isinstance(visible_support_by_event_id, Mapping):
        raise TypeError("visible_support_by_event_id must be a mapping")
    previous = tuple(previous_answers)
    if not all(isinstance(answer, str) for answer in previous):
        raise TypeError("previous_answers must contain strings")
    if _normal(text) in {_normal(answer) for answer in previous}:
        raise ResponseContractError("normalized exact duplicate response text")

    words = _tokens(text)
    if not 1 <= len(words) <= 40:
        raise ResponseContractError("response text must contain 1-40 words")
    if _sentence_count(text) > 2:
        raise ResponseContractError("response text must contain at most two sentences")
    _validate_no_meta_leak(text)
    support = _support_text(answer_contract, visible_support_by_event_id)
    _validate_answer_points(text, answer_contract)
    _validate_forbidden_claims(text, answer_contract)
    _validate_protected_claim_scope(text, answer_contract)
    _validate_kind(text, answer_contract.response_kind)
    _validate_no_tautological_adapter_error_clause(
        text, answer_contract, visible_support_by_event_id
    )
    _validate_grounding(text, support, answer_contract.grounding_allowlist)

    return _quality_diagnostics(text, previous, embedding_scorer)


def validate_response_kind_counts(contracts: Iterable[AnswerContract]) -> None:
    """Require the fixed G7 50/15/15/10 response-kind distribution."""
    materialized = tuple(contracts)
    if not all(isinstance(contract, AnswerContract) for contract in materialized):
        raise TypeError("contracts must contain AnswerContract values")
    observed = Counter(contract.response_kind for contract in materialized)
    if observed != Counter(EXPECTED_RESPONSE_KIND_COUNTS):
        expected = {kind.value: count for kind, count in EXPECTED_RESPONSE_KIND_COUNTS.items()}
        actual = {kind.value: observed[kind] for kind in ResponseKind}
        raise ResponseContractError(f"response-kind counts must be {expected}, got {actual}")


def _require_identifiers(values: object, name: str) -> None:
    if not isinstance(values, tuple) or not values:
        raise ResponseContractError(f"{name} must be a non-empty immutable tuple")
    if not all(isinstance(value, str) and value.strip() == value and value for value in values):
        raise ResponseContractError(f"{name} must contain non-blank strings")
    if len(set(values)) != len(values):
        raise ResponseContractError(f"{name} must be unique")


def _require_phrases(values: object, name: str, *, allow_empty: bool = False) -> None:
    if not isinstance(values, tuple) or (not values and not allow_empty):
        raise ResponseContractError(
            f"{name} must be an immutable {'non-empty ' if not allow_empty else ''}tuple"
        )
    if not all(isinstance(value, str) and value.strip() == value and value for value in values):
        raise ResponseContractError(f"{name} must contain non-blank strings")
    if len(set(values)) != len(values):
        raise ResponseContractError(f"{name} must be unique")


def _tokens(text: str) -> tuple[str, ...]:
    return tuple(findall(_WORD_TOKENS, text))


def _sentence_count(text: str) -> int:
    return len(findall(r"[!?]+|(?<!\d)\.(?!\d)", text))


def _validate_no_meta_leak(text: str) -> None:
    lowered = text.casefold()
    if any(term in lowered for term in _META_LEAK):
        raise ResponseContractError("response text leaks instruction or metadata")


def _support_text(contract: AnswerContract, visible_support_by_event_id: Mapping[str, str]) -> str:
    support: list[str] = []
    for event_id in contract.support_event_ids:
        try:
            value = visible_support_by_event_id[event_id]
        except KeyError as error:
            raise ResponseContractError(f"missing visible support for {event_id}") from error
        if not isinstance(value, str):
            raise TypeError("visible support values must be strings")
        support.append(value)
    return "\n".join(support)


def _normal(text: str) -> str:
    return " ".join(text.casefold().split())


def _validate_answer_points(text: str, contract: AnswerContract) -> None:
    normalized = _phrase_normal(text)
    if any(
        not any(
            _phrase_normal(alternative) in normalized for alternative in point.accepted_alternatives
        )
        for point in contract.required_answer_points
    ):
        raise ResponseContractError("response text misses a required answer point")


def _validate_forbidden_claims(text: str, contract: AnswerContract) -> None:
    normalized = _phrase_normal(text)
    if any(_phrase_normal(claim) in normalized for claim in contract.forbidden_claims):
        raise ResponseContractError("response text contains a forbidden claim")


def _validate_protected_scope_contract(
    scope: ProtectedClaimScope, points: tuple[RequiredAnswerPoint, ...]
) -> None:
    if not any(
        all(
            any(
                _phrase_normal(alternative) in _phrase_normal(response)
                for alternative in point.accepted_alternatives
            )
            for point in points
        )
        for response in _APPROVED_PROTECTED_SCOPE_RESPONSES[scope]
    ):
        raise ResponseContractError(
            "protected_claim_scope requires accepted negative refusals compatible with an "
            "approved complete response"
        )


def _validate_protected_claim_scope(text: str, contract: AnswerContract) -> None:
    scope = contract.protected_claim_scope
    if scope is None:
        return
    approved = {_normal(response) for response in _APPROVED_PROTECTED_SCOPE_RESPONSES[scope]}
    if _normal(text) not in approved:
        raise ResponseContractError(
            "response text is not an approved complete protected claim scope response"
        )


def _validate_grounding(text: str, support: str, allowlist: tuple[str, ...]) -> None:
    visible = _normal(support)
    allowed = tuple(_normal(value) for value in allowlist)
    introduced = set(_introduced_entities(text)) | set(findall(_NUMBER, text))
    for value in introduced:
        normalized = _normal(value)
        if value in _NON_ENTITIES or normalized in allowed or normalized in visible:
            continue
        raise ResponseContractError(
            f"response text introduces unsupported entity or number: {value}"
        )


def _introduced_entities(text: str) -> tuple[str, ...]:
    entities: list[str] = []
    current: list[str] = []
    end = -1
    for match in finditer(_NAMED_ENTITY, text):
        if current and text[end : match.start()].strip():
            entities.extend(_without_non_entities(current))
            current = []
        current.append(match.group())
        end = match.end()
    entities.extend(_without_non_entities(current))
    return tuple(entities)


def _without_non_entities(parts: list[str]) -> tuple[str, ...]:
    while parts and parts[0] in _NON_ENTITIES:
        parts.pop(0)
    return (" ".join(parts),) if parts else ()


def _phrase_normal(text: str) -> str:
    return " ".join(token.casefold() for token in _tokens(text))


def _validate_kind(text: str, kind: ResponseKind) -> None:
    lowered = text.casefold()
    if kind is ResponseKind.ORDINARY_GROUNDED:
        if "?" in text:
            raise ResponseContractError("ordinary-grounded response must not ask a question")
        return
    if kind is ResponseKind.AMBIGUITY_CLARIFICATION:
        if len(findall(r"\?+", text)) != 1 or _sentence_count(text) != 1:
            raise ResponseContractError(
                "ambiguity clarification must be exactly one question without a bundled answer"
            )
        return
    if kind is ResponseKind.UNSUPPORTED_FEATURE_LIMITATION:
        if not search(
            r"\b(cannot|can['’]t|unable|not available|do not support|doesn['’]t support)\b",
            lowered,
        ):
            raise ResponseContractError("unsupported-feature response must state a limitation")
        if search(r"\b(sorry|apologies|i apologize)\b", lowered):
            raise ResponseContractError(
                "unsupported-feature response must not use apology boilerplate"
            )
        if search(
            r"\b(?:"
            r"i(?:'ve| have)?\s+(?:scheduled|set|booked)"
            r"|i(?:'ll| will| can)\s+(?:schedule|set|book)"
            r"|it\s+(?:will\s+be|is|was)\s+(?:scheduled|set|booked)"
            r"|your\s+(?:schedule|reminder)\s+(?:is|was)\s+(?:set|booked)"
            r")\b",
            lowered,
        ) or search(r"\b(?:about|around|approximately|roughly)\b", lowered):
            raise ResponseContractError(
                "unsupported-feature response must not claim a schedule or approximation"
            )
        return
    if kind is ResponseKind.FAILED_TOOL_NOTICE:
        if not search(
            r"\b(failed|failure|error|unavailable|couldn't complete|cannot complete|no result)\b",
            lowered,
        ):
            raise ResponseContractError("failed-tool response must state the failure")
        if search(
            r"\b(?:i(?:'ll| will)|it will|will)\s+(?:automatically\s+)?retry\b"
            r"|\b(?:automatically|auto)\s+retry\b"
            r"|\bretry\s+automatically\b",
            lowered,
        ):
            raise ResponseContractError("failed-tool response must not promise an automatic retry")


def _validate_no_tautological_adapter_error_clause(
    text: str,
    contract: AnswerContract,
    visible_support_by_event_id: Mapping[str, str],
) -> None:
    if contract.response_kind is not ResponseKind.FAILED_TOOL_NOTICE:
        return
    error_text = visible_support_by_event_id[contract.support_event_ids[-1]].strip().rstrip(".!?")
    if not error_text:
        return
    lowered = text.casefold()
    error_clause = search(
        rf":\s*{escape(error_text.casefold())}(?=\s*(?:[;.!?]|$))", lowered
    )
    if error_clause is not None and search(
        r"\b(?:failed|failure|error|unavailable|couldn't complete|cannot complete)\b",
        lowered[: error_clause.start()],
    ):
        raise ResponseContractError(
            "failed-tool response must not repeat adapter error as a tautological colon clause"
        )


def _quality_diagnostics(
    text: str,
    previous: tuple[str, ...],
    embedding_scorer: Callable[[str, str], float] | None,
) -> AnswerQualityDiagnostics:
    flags: list[QualityFlag] = []
    candidate_tokens = tuple(token.casefold() for token in _tokens(text))
    prior_tokens = tuple(
        tuple(token.casefold() for token in _tokens(answer)) for answer in previous
    )
    candidate_eight_grams = _ngrams(candidate_tokens, 8)
    all_eight_grams = Counter(
        gram for tokens in (*prior_tokens, candidate_tokens) for gram in set(_ngrams(tokens, 8))
    )
    if any(all_eight_grams[gram] > 2 for gram in candidate_eight_grams):
        flags.append(QualityFlag.EIGHT_GRAM_OVERUSE)
    if any(SequenceMatcher(a=candidate_tokens, b=tokens).ratio() > 0.75 for tokens in prior_tokens):
        flags.append(QualityFlag.TOKEN_SIMILARITY)

    candidate_char_grams = _char_ngrams(text, 5)
    if any(_jaccard(candidate_char_grams, _char_ngrams(answer, 5)) > 0.65 for answer in previous):
        flags.append(QualityFlag.CHAR_FIVE_GRAM_JACCARD)
    opening = candidate_tokens[:4]
    if (
        opening
        and len(opening) == 4
        and sum(tokens[:4] == opening for tokens in prior_tokens) + 1 > 3
    ):
        flags.append(QualityFlag.OPENING_FOUR_GRAM_OVERUSE)
    if embedding_scorer is not None:
        if not callable(embedding_scorer):
            raise TypeError("embedding_scorer must be callable")
        for answer in previous:
            score = embedding_scorer(text, answer)
            if (
                not isinstance(score, (int, float))
                or isinstance(score, bool)
                or not isfinite(score)
            ):
                raise TypeError("embedding_scorer must return a finite number")
            if score > EMBEDDING_SIMILARITY_THRESHOLD:
                flags.append(QualityFlag.EMBEDDING_SIMILARITY)
                break
    return AnswerQualityDiagnostics(tuple(flags))


def _ngrams(tokens: tuple[str, ...], width: int) -> tuple[tuple[str, ...], ...]:
    return tuple(tuple(tokens[index : index + width]) for index in range(len(tokens) - width + 1))


def _char_ngrams(text: str, width: int) -> set[str]:
    normalized = _normal(text)
    return {normalized[index : index + width] for index in range(len(normalized) - width + 1)}


def _jaccard(left: set[object], right: set[object]) -> float:
    return len(left & right) / len(left | right) if left or right else 0.0
