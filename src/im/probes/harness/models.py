"""Typed run, provider, cache, and protocol records for WP15."""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from im.policy.base import PolicyCallTrace
from im.probes.model import NegativeClass

Digest = Annotated[str, StringConstraints(pattern=r"^sha256:[0-9a-f]{64}$")]


class HarnessProtocol(StrEnum):
    GENERATION = "generation"
    PAIRWISE = "pairwise"
    LISTWISE = "listwise"
    SEMANTIC_TEXT = "semantic_text"


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class PairwiseChoice(_StrictModel):
    choice: Literal["A", "B"]


CandidateId = Annotated[str, StringConstraints(pattern=r"^c[0-9]{2}$")]


class ListwiseRanking(_StrictModel):
    ranking: Annotated[tuple[CandidateId, ...], Field(min_length=2)]

    @model_validator(mode="after")
    def unique_candidates(self) -> ListwiseRanking:
        if len(self.ranking) != len(set(self.ranking)):
            raise ValueError("listwise ranking contains duplicate candidate ids")
        return self


class SemanticTextVerdict(_StrictModel):
    passed: bool
    rationale: Annotated[str, StringConstraints(min_length=1, max_length=2_000)]


@dataclass(frozen=True, slots=True)
class ProviderUsage:
    input_tokens: int = 0
    cached_input_tokens: int = 0
    cache_write_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0

    def __add__(self, other: ProviderUsage) -> ProviderUsage:
        return ProviderUsage(
            input_tokens=self.input_tokens + other.input_tokens,
            cached_input_tokens=self.cached_input_tokens + other.cached_input_tokens,
            cache_write_tokens=self.cache_write_tokens + other.cache_write_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            reasoning_tokens=self.reasoning_tokens + other.reasoning_tokens,
        )

    def as_json(self) -> dict[str, int]:
        return {
            "input_tokens": self.input_tokens,
            "cached_input_tokens": self.cached_input_tokens,
            "cache_write_tokens": self.cache_write_tokens,
            "output_tokens": self.output_tokens,
            "reasoning_tokens": self.reasoning_tokens,
        }


@dataclass(frozen=True, slots=True)
class HarnessCompletion:
    """One parsed or terminal provider outcome and every underlying call trace."""

    value: object
    outcome: str
    traces: tuple[PolicyCallTrace, ...] = ()
    usage: ProviderUsage = ProviderUsage()
    from_cache: bool = False


@dataclass(frozen=True, slots=True)
class CacheIdentity:
    """Collision-resistant identity for one resumable protocol presentation."""

    manifest_sha256: Digest
    probe_id: str
    protocol: HarnessProtocol
    variant_id: str
    presentation: str
    model: str
    reasoning_effort: str
    prompt_hash: Digest
    request_hash: Digest

    @property
    def digest(self) -> str:
        encoded = json.dumps(
            {
                "manifest_sha256": self.manifest_sha256,
                "model": self.model,
                "presentation": self.presentation,
                "probe_id": self.probe_id,
                "prompt_hash": self.prompt_hash,
                "protocol": self.protocol.value,
                "reasoning_effort": self.reasoning_effort,
                "request_hash": self.request_hash,
                "variant_id": self.variant_id,
            },
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return sha256(encoded).hexdigest()


def traces_to_json(traces: tuple[PolicyCallTrace, ...]) -> str:
    return json.dumps(
        [
            {
                "attempt_index": trace.attempt_index,
                "http_status": trace.http_status,
                "latency_ms": trace.latency_ms,
                "model": trace.model,
                "outcome": trace.outcome,
                "prompt_hash": trace.prompt_hash,
                "request_base64": base64.b64encode(trace.request).decode("ascii"),
                "response_base64": base64.b64encode(trace.response).decode("ascii"),
            }
            for trace in traces
        ],
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def traces_from_json(value: str) -> tuple[PolicyCallTrace, ...]:
    parsed = json.loads(value)
    if not isinstance(parsed, list):
        raise ValueError("cached provider traces must be an array")
    return tuple(
        PolicyCallTrace(
            attempt_index=int(item["attempt_index"]),
            model=str(item["model"]),
            prompt_hash=str(item["prompt_hash"]),
            request=base64.b64decode(item["request_base64"], validate=True),
            response=base64.b64decode(item["response_base64"], validate=True),
            latency_ms=int(item["latency_ms"]),
            http_status=(
                None if item["http_status"] is None else int(item["http_status"])
            ),
            outcome=str(item["outcome"]),
        )
        for item in parsed
    )


@dataclass(frozen=True, slots=True)
class GenerationResult:
    probe_id: str
    family_id: int
    variant_id: str
    expected_type: str
    actual_action: dict[str, object] | None
    provider_outcome: str
    schema_valid: bool
    reference_valid: bool
    license_allowed: bool
    license_block_code: str | None
    structural_match: bool
    semantic_rule: str | None
    semantic_passed: bool | None
    semantic_rationale: str | None
    generation_passed: bool
    invented_arguments: bool
    intrusive_action: bool
    from_cache: bool
    usage: ProviderUsage
    fresh_usage: ProviderUsage


@dataclass(frozen=True, slots=True)
class SemanticTextResult:
    probe_id: str
    family_id: int
    variant_id: Literal["v1"]
    rule: str
    executed: bool
    provider_outcome: str
    response_valid: bool
    passed: bool
    rationale: str | None
    from_cache: bool
    usage: ProviderUsage
    fresh_usage: ProviderUsage


@dataclass(frozen=True, slots=True)
class PairwiseResult:
    probe_id: str
    family_id: int
    variant_id: str
    expected_position: Literal["A", "B"]
    negative_class: NegativeClass
    restraint_pair: bool
    provider_outcome: str
    response_valid: bool
    choice: Literal["A", "B"] | None
    correct: bool
    from_cache: bool
    usage: ProviderUsage
    fresh_usage: ProviderUsage


@dataclass(frozen=True, slots=True)
class ListwiseResult:
    probe_id: str
    family_id: int
    variant_id: Literal["v1"]
    candidate_count: int
    candidate_action_types: tuple[str, ...]
    provider_outcome: str
    response_valid: bool
    ranking: tuple[str, ...]
    expected_candidate_id: str
    tempting_candidate_id: str
    top1_correct: bool
    expected_above_tempting: bool
    from_cache: bool
    usage: ProviderUsage
    fresh_usage: ProviderUsage


@dataclass(frozen=True, slots=True)
class HarnessRun:
    manifest_sha256: Digest
    review_sha256: Digest
    model: str
    reasoning_effort: str
    generation: tuple[GenerationResult, ...]
    semantic_text: tuple[SemanticTextResult, ...]
    pairwise: tuple[PairwiseResult, ...]
    listwise: tuple[ListwiseResult, ...]

    @property
    def usage(self) -> ProviderUsage:
        total = ProviderUsage()
        for result in (
            *self.generation,
            *self.semantic_text,
            *self.pairwise,
            *self.listwise,
        ):
            total += result.usage
        return total

    @property
    def fresh_usage(self) -> ProviderUsage:
        total = ProviderUsage()
        for result in (
            *self.generation,
            *self.semantic_text,
            *self.pairwise,
            *self.listwise,
        ):
            total += result.fresh_usage
        return total
