"""Offline WP15 cost forecast and usage-based charge calculation."""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass
from decimal import Decimal

from im.config import estimate_tokens
from im.policy.prompted import ModelPricing, ResponsesRequestBuilder
from im.probes.grading import grade_generation_structure
from im.probes.harness.artifacts import ApprovedProbeCatalog
from im.probes.harness.candidates import build_listwise_presentation
from im.probes.harness.models import ProviderUsage
from im.probes.harness.protocols import ProtocolPromptBuilder, ProtocolRequest
from im.probes.model import ExpectedPosition

_MILLION = Decimal(1_000_000)


@dataclass(frozen=True, slots=True)
class HarnessCostEstimate:
    generation_requests: int
    pairwise_requests: int
    listwise_requests: int
    semantic_requests: int
    expected_input_tokens: int
    expected_output_tokens: int
    synchronous_no_cache_usd: Decimal
    synchronous_warm_cache_usd: Decimal
    batch_no_cache_usd: Decimal
    all_calls_one_retry_warm_cache_usd: Decimal

    @property
    def total_requests(self) -> int:
        return (
            self.generation_requests
            + self.pairwise_requests
            + self.listwise_requests
            + self.semantic_requests
        )

    def as_json(self) -> dict[str, object]:
        def money(value: Decimal) -> str:
            return format(value.quantize(Decimal("0.000001")), "f")

        return {
            "request_counts": {
                "generation": self.generation_requests,
                "listwise": self.listwise_requests,
                "pairwise": self.pairwise_requests,
                "semantic_text_grading": self.semantic_requests,
                "total": self.total_requests,
            },
            "token_assumptions": {
                "expected_input_tokens": self.expected_input_tokens,
                "expected_output_tokens": self.expected_output_tokens,
            },
            "usd": {
                "all_calls_one_retry_warm_cache": money(
                    self.all_calls_one_retry_warm_cache_usd
                ),
                "batch_no_cache": money(self.batch_no_cache_usd),
                "synchronous_no_cache": money(self.synchronous_no_cache_usd),
                "synchronous_warm_cache": money(self.synchronous_warm_cache_usd),
            },
        }


@dataclass(frozen=True, slots=True)
class _EstimatedRequest:
    cache_key: str
    system_tokens: int
    variable_tokens: int
    output_tokens: int


def estimate_harness_cost(
    catalog: ApprovedProbeCatalog,
    generation_builder: ResponsesRequestBuilder,
    prompts: ProtocolPromptBuilder,
    *,
    pricing: ModelPricing | None = None,
    probe_ids: Collection[str] | None = None,
) -> HarnessCostEstimate:
    """Price the exact signed task population without making a provider call."""
    probes = catalog.manifest.probes
    if probe_ids is not None:
        requested = frozenset(probe_ids)
        if not requested:
            raise ValueError("cost probe selection cannot be empty")
        probes = tuple(probe for probe in probes if probe.probe_id in requested)
        if {probe.probe_id for probe in probes} != requested:
            raise KeyError("cost probe selection contains an unknown probe id")
    requests: list[_EstimatedRequest] = []
    generation_count = pairwise_count = listwise_count = semantic_count = 0
    for probe in probes:
        variant = probe.variants[0]
        generation_body = generation_builder.build(variant.policy_stream.encode())
        requests.append(_estimate_request(generation_body, expected_output_tokens=300))
        generation_count += 1
        structure = grade_generation_structure(
            variant.expected_action,
            variant.expected_action,
        )
        if structure.text_rule is not None:
            semantic_request = prompts.semantic_text(
                policy_stream=variant.policy_stream,
                action=variant.expected_action,
                rule=structure.text_rule,
            )
            requests.append(_estimate_protocol_request(semantic_request, output_tokens=250))
            semantic_count += 1
        presentation = build_listwise_presentation(
            probe,
            variant,
            catalog.views[(probe.probe_id, "v1")],
        )
        listwise_request = prompts.listwise(
            policy_stream=variant.policy_stream,
            candidates=presentation.candidates,
        )
        requests.append(_estimate_protocol_request(listwise_request, output_tokens=400))
        listwise_count += 1
        for peer in probe.variants:
            for position in (ExpectedPosition.A, ExpectedPosition.B):
                pair = probe.teacher_variant(
                    peer.variant_id,
                    expected_position=position,
                )
                pairwise_request = prompts.pairwise(
                    policy_stream=str(pair["policy_stream"]),
                    candidate_a=pair["candidate_a"],
                    candidate_b=pair["candidate_b"],
                )
                requests.append(
                    _estimate_protocol_request(pairwise_request, output_tokens=200)
                )
                pairwise_count += 1

    rates = pricing or ModelPricing(model=generation_builder.config.model)
    if rates.model != generation_builder.config.model:
        raise ValueError("pricing model does not match harness model")
    expected_input = sum(item.system_tokens + item.variable_tokens for item in requests)
    expected_output = sum(item.output_tokens for item in requests)
    no_cache = _token_cost(expected_input, rates.input_per_million) + _token_cost(
        expected_output, rates.output_per_million
    )
    warm_input = Decimal(0)
    seen_cache_keys: set[str] = set()
    for item in requests:
        if item.cache_key in seen_cache_keys:
            system_rate = rates.cached_input_per_million
        else:
            seen_cache_keys.add(item.cache_key)
            system_rate = rates.input_per_million * rates.cache_write_multiplier
        warm_input += _token_cost(item.system_tokens, system_rate)
        warm_input += _token_cost(item.variable_tokens, rates.input_per_million)
    warm = warm_input + _token_cost(expected_output, rates.output_per_million)
    retry_feedback_tokens = 600 * len(requests)
    retry_warm = warm * 2 + _token_cost(retry_feedback_tokens, rates.input_per_million)
    return HarnessCostEstimate(
        generation_requests=generation_count,
        pairwise_requests=pairwise_count,
        listwise_requests=listwise_count,
        semantic_requests=semantic_count,
        expected_input_tokens=expected_input,
        expected_output_tokens=expected_output,
        synchronous_no_cache_usd=no_cache,
        synchronous_warm_cache_usd=warm,
        batch_no_cache_usd=no_cache * rates.batch_multiplier,
        all_calls_one_retry_warm_cache_usd=retry_warm,
    )


def usage_cost(
    usage: ProviderUsage,
    pricing: ModelPricing,
    *,
    billing_multiplier: Decimal = Decimal(1),
) -> Decimal:
    """Apply the pinned pricing snapshot to provider-reported token classes."""
    if not billing_multiplier.is_finite() or billing_multiplier <= 0:
        raise ValueError("billing_multiplier must be a positive finite decimal")
    cached = min(usage.input_tokens, usage.cached_input_tokens)
    writable = min(max(0, usage.input_tokens - cached), usage.cache_write_tokens)
    ordinary = max(0, usage.input_tokens - cached - writable)
    return billing_multiplier * (
        _token_cost(ordinary, pricing.input_per_million)
        + _token_cost(cached, pricing.cached_input_per_million)
        + _token_cost(
            writable,
            pricing.input_per_million * pricing.cache_write_multiplier,
        )
        + _token_cost(usage.output_tokens, pricing.output_per_million)
    )


def _estimate_protocol_request(
    request: ProtocolRequest,
    *,
    output_tokens: int,
) -> _EstimatedRequest:
    return _estimate_request(request.body, expected_output_tokens=output_tokens)


def _estimate_request(
    body: dict[str, object],
    *,
    expected_output_tokens: int,
) -> _EstimatedRequest:
    input_items = body["input"]
    if not isinstance(input_items, list) or len(input_items) < 2:
        raise ValueError("request body lacks system and user inputs")
    system = input_items[0]
    user = input_items[1]
    system_text = system["content"][0]["text"]
    user_text = user["content"][0]["text"]
    cache_key = body.get("prompt_cache_key")
    if not all(isinstance(value, str) for value in (system_text, user_text, cache_key)):
        raise ValueError("request prompt components must be strings")
    return _EstimatedRequest(
        cache_key=cache_key,
        system_tokens=estimate_tokens(system_text.encode()) + 16,
        variable_tokens=estimate_tokens(user_text.encode()) + 16,
        output_tokens=expected_output_tokens,
    )


def _token_cost(tokens: int, rate: Decimal) -> Decimal:
    return Decimal(tokens) * rate / _MILLION
