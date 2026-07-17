"""Pinned local lexical embedding cosine for response-diversity diagnostics."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from hashlib import sha256
from math import sqrt
from re import findall

__all__ = (
    "EMBEDDING_SIMILARITY_THRESHOLD",
    "PINNED_RESPONSE_EMBEDDING_IDENTITY",
    "PINNED_RESPONSE_EMBEDDING_SCORER",
    "PinnedEmbeddingIdentity",
    "PinnedLexicalEmbeddingScorer",
)

EMBEDDING_SIMILARITY_THRESHOLD = 0.92
_FEATURE_DIMENSIONS = 2048
_NGRAM_WIDTHS = (1, 2, 3)
_NGRAM_WEIGHTS = {width: 1.0 for width in _NGRAM_WIDTHS}
_TOKEN = r"[^\W_]+(?:['’][^\W_]+)*|\d+(?:[,.]\d+)*%?"
_CONFIGURATION = {
    "algorithm": "signed_sha256_feature_hashing",
    "feature_dimensions": _FEATURE_DIMENSIONS,
    "ngram_weights": {str(width): _NGRAM_WEIGHTS[width] for width in _NGRAM_WIDTHS},
    "ngram_widths": list(_NGRAM_WIDTHS),
    "scorer_id": "im.lexical_hashed_embedding",
    "scorer_version": 1,
    "tokenization": "unicode_casefold_word_tokens",
}
_CONFIGURATION_SHA256 = sha256(
    json.dumps(_CONFIGURATION, sort_keys=True, separators=(",", ":")).encode("utf-8")
).hexdigest()


@dataclass(frozen=True, slots=True)
class PinnedEmbeddingIdentity:
    """Machine-verifiable identity for the local, non-neural scorer."""

    scorer_id: str
    scorer_version: int
    configuration_sha256: str

    def as_json_object(self) -> dict[str, object]:
        return {
            **_CONFIGURATION,
            "configuration_sha256": self.configuration_sha256,
        }


PINNED_RESPONSE_EMBEDDING_IDENTITY = PinnedEmbeddingIdentity(
    scorer_id=_CONFIGURATION["scorer_id"],
    scorer_version=_CONFIGURATION["scorer_version"],
    configuration_sha256=_CONFIGURATION_SHA256,
)


@dataclass(frozen=True, slots=True)
class PinnedLexicalEmbeddingScorer:
    """Versioned signed-SHA-256 feature hashing; it is not a neural semantic model."""

    identity: PinnedEmbeddingIdentity = PINNED_RESPONSE_EMBEDDING_IDENTITY

    def __post_init__(self) -> None:
        if self.identity != PINNED_RESPONSE_EMBEDDING_IDENTITY:
            raise ValueError("pinned embedding scorer identity cannot be changed")

    def __call__(self, left: str, right: str) -> float:
        left_vector = _feature_vector(left)
        right_vector = _feature_vector(right)
        if not left_vector or not right_vector:
            return 0.0
        dot = sum(value * right_vector.get(index, 0.0) for index, value in left_vector.items())
        left_norm = sqrt(sum(value * value for value in left_vector.values()))
        right_norm = sqrt(sum(value * value for value in right_vector.values()))
        return max(-1.0, min(1.0, dot / (left_norm * right_norm)))


PINNED_RESPONSE_EMBEDDING_SCORER = PinnedLexicalEmbeddingScorer()


def _feature_vector(text: str) -> Counter[int]:
    if not isinstance(text, str):
        raise TypeError("embedding inputs must be strings")
    tokens = tuple(token.casefold() for token in findall(_TOKEN, text))
    vector: Counter[int] = Counter()
    for width in _NGRAM_WIDTHS:
        for index in range(len(tokens) - width + 1):
            digest = sha256("\x1f".join(tokens[index : index + width]).encode("utf-8")).digest()
            bucket = int.from_bytes(digest[:4], "big") % _FEATURE_DIMENSIONS
            vector[bucket] += _NGRAM_WEIGHTS[width] * (1.0 if digest[4] & 1 else -1.0)
    return vector
