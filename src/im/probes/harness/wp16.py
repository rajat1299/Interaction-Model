"""Frozen population, costing, and reporting for the WP16 Qwen sanity run."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from hashlib import sha256

from im.config import estimate_tokens
from im.policy.base import PolicyCallTrace
from im.policy.prompted import ResponsesRequestBuilder
from im.probes.harness.artifacts import ApprovedProbeCatalog
from im.probes.harness.identity import canonical_request_bytes
from im.probes.harness.models import HarnessCompletion, HarnessRun
from im.probes.harness.planning import plan_generation

QWEN_MODEL = "qwen/qwen3.6-35b-a3b"
QWEN_UPSTREAM_PROVIDER = "parasail"
QWEN_INPUT_USD_PER_MILLION = Decimal("0.15")
QWEN_OUTPUT_USD_PER_MILLION = Decimal("1.00")
QWEN_PRICING_SOURCE_DATE = "2026-07-14"
_EXPECTED_OUTPUT_TOKENS = 200
_MILLION = Decimal(1_000_000)

_TWIN_STEMS = (
    *(f"f{family:02d}-t01" for family in range(1, 11)),
    "f11-t01",
    "f11-t03",
    "f11-t04",
    "f11-t05",
    "f12-t01",
)
QWEN_SANITY_PROBE_IDS = tuple(
    f"{stem}-{side}" for stem in _TWIN_STEMS for side in ("a", "b")
)

QWEN_SANITY_SPEC = {
    "spec_id": "wp16-qwen-generation-v1",
    "model": QWEN_MODEL,
    "provider": "openrouter",
    "upstream_provider": QWEN_UPSTREAM_PROVIDER,
    "allow_fallbacks": False,
    "require_parameters": True,
    "router_metadata": "enabled",
    "reasoning": {"effort": "none", "exclude": True},
    "max_attempts": 1,
    "max_output_tokens": 1024,
    "probe_ids": list(QWEN_SANITY_PROBE_IDS),
}


def wp16_spec_sha256() -> str:
    encoded = json.dumps(
        QWEN_SANITY_SPEC,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return "sha256:" + sha256(encoded).hexdigest()


def selected_probes(catalog: ApprovedProbeCatalog):
    requested = frozenset(QWEN_SANITY_PROBE_IDS)
    probes = tuple(
        probe for probe in catalog.manifest.probes if probe.probe_id in requested
    )
    if len(probes) != 30 or {probe.probe_id for probe in probes} != requested:
        raise ValueError("WP16 requires its exact 30-probe population")
    families = {probe.family_id for probe in probes}
    if families != set(range(1, 13)):
        raise ValueError("WP16 population must cover all twelve probe families")
    action_types = {probe.variants[0].expected_action.type for probe in probes}
    if action_types != {
        "cancel",
        "delegate",
        "idle",
        "integrate",
        "mark",
        "nudge",
        "respond",
        "schedule",
        "skip",
    }:
        raise ValueError("WP16 population must cover the closed action union")
    return probes


@dataclass(frozen=True, slots=True)
class QwenCostEstimate:
    requests: int
    estimated_input_tokens: int
    expected_output_tokens: int
    maximum_output_tokens: int
    expected_no_cache_usd: Decimal
    ceiling_no_cache_usd: Decimal

    def as_json(self) -> dict[str, object]:
        return {
            "requests": self.requests,
            "token_assumptions": {
                "estimated_input_tokens": self.estimated_input_tokens,
                "expected_output_tokens": self.expected_output_tokens,
                "maximum_output_tokens": self.maximum_output_tokens,
            },
            "usd": {
                "expected_no_cache": _money(self.expected_no_cache_usd),
                "ceiling_no_cache": _money(self.ceiling_no_cache_usd),
            },
        }


def estimate_qwen_cost(
    catalog: ApprovedProbeCatalog,
    builder: ResponsesRequestBuilder,
) -> QwenCostEstimate:
    probes = selected_probes(catalog)
    input_tokens = sum(
        estimate_tokens(canonical_request_bytes(builder.build(probe.variants[0].policy_stream.encode())))
        for probe in probes
    )
    expected_output = len(probes) * _EXPECTED_OUTPUT_TOKENS
    maximum_output = len(probes) * builder.config.max_output_tokens
    return QwenCostEstimate(
        requests=len(probes),
        estimated_input_tokens=input_tokens,
        expected_output_tokens=expected_output,
        maximum_output_tokens=maximum_output,
        expected_no_cache_usd=_token_cost(input_tokens, QWEN_INPUT_USD_PER_MILLION)
        + _token_cost(expected_output, QWEN_OUTPUT_USD_PER_MILLION),
        ceiling_no_cache_usd=_token_cost(input_tokens, QWEN_INPUT_USD_PER_MILLION)
        + _token_cost(maximum_output, QWEN_OUTPUT_USD_PER_MILLION),
    )


def generation_completions(
    catalog: ApprovedProbeCatalog,
    builder: ResponsesRequestBuilder,
    cache,
) -> tuple[HarnessCompletion, ...]:
    completions = []
    for probe in selected_probes(catalog):
        completion = cache.get(plan_generation(catalog, builder, probe).identity)
        if completion is None:
            raise ValueError(f"missing WP16 completion for {probe.probe_id}")
        completions.append(completion)
    return tuple(completions)


def compute_qwen_metrics(
    run: HarnessRun,
    completions: tuple[HarnessCompletion, ...],
    *,
    require_provider_traces: bool = False,
) -> dict[str, object]:
    if len(run.generation) != 30 or len(completions) != 30:
        raise ValueError("WP16 metrics require exactly 30 generation results")
    if run.semantic_text or run.pairwise or run.listwise:
        raise ValueError("WP16 must contain generation protocol results only")
    expected_ids = set(QWEN_SANITY_PROBE_IDS)
    if {result.probe_id for result in run.generation} != expected_ids:
        raise ValueError("WP16 generation results do not match the frozen population")

    traces = tuple(trace for completion in completions for trace in completion.traces)
    one_trace_per_state = all(len(completion.traces) == 1 for completion in completions)
    if require_provider_traces and not one_trace_per_state:
        raise ValueError("live WP16 evidence requires exactly one provider trace per state")
    request_violations = sum(not _request_disables_reasoning(trace) for trace in traces)
    visible_reasoning = sum(_response_has_visible_reasoning(trace) for trace in traces)
    raw_reasoning_tokens = tuple(_response_reasoning_tokens(trace) for trace in traces)
    audited_reasoning_tokens = tuple(
        value for value in raw_reasoning_tokens if value is not None
    )
    action_distribution = Counter(
        "invalid"
        if result.actual_action is None
        else str(result.actual_action.get("type", "invalid"))
        for result in run.generation
    )
    expected_distribution = Counter(result.expected_type for result in run.generation)
    response_costs = tuple(
        cost for trace in traces if (cost := _response_cost(trace)) is not None
    )
    provider_cost = sum(response_costs, Decimal(0))
    response_models = sorted(
        {
            model
            for trace in traces
            if (model := _response_string(trace, "model")) is not None
        }
    )
    selected_providers = tuple(_response_selected_provider(trace) for trace in traces)
    response_providers = sorted({provider for provider in selected_providers if provider})
    routing_metadata_records = sum(provider is not None for provider in selected_providers)
    upstream_pin_verified = bool(
        traces
        and routing_metadata_records == len(traces)
        and all(
            provider is not None
            and provider.casefold() == QWEN_UPSTREAM_PROVIDER.casefold()
            for provider in selected_providers
        )
    )
    return {
        "population": len(run.generation),
        "provider_outcomes": dict(
            sorted(Counter(result.provider_outcome for result in run.generation).items())
        ),
        "schema_valid": sum(result.schema_valid for result in run.generation),
        "reference_valid": sum(result.reference_valid for result in run.generation),
        "license_allowed": sum(result.license_allowed for result in run.generation),
        "structural_match": sum(result.structural_match for result in run.generation),
        "actual_action_distribution": dict(sorted(action_distribution.items())),
        "expected_action_distribution": dict(sorted(expected_distribution.items())),
        "provider_attempts": len(traces),
        "one_trace_per_state": one_trace_per_state,
        "request_reasoning_config_violations": request_violations,
        "reasoning_usage_records": len(audited_reasoning_tokens),
        "reasoning_tokens": sum(audited_reasoning_tokens),
        "responses_with_visible_reasoning": visible_reasoning,
        "thinking_audited": (
            one_trace_per_state
            and len(traces) == len(run.generation)
            and len(audited_reasoning_tokens) == len(traces)
        ),
        "thinking_disabled": (
            one_trace_per_state
            and len(traces) == len(run.generation)
            and len(audited_reasoning_tokens) == len(traces)
            and request_violations == 0
            and sum(audited_reasoning_tokens) == 0
            and visible_reasoning == 0
        ),
        "provider_reported_cost_usd": (
            _money(provider_cost) if len(response_costs) == len(traces) and traces else None
        ),
        "response_models": response_models,
        "response_providers": response_providers,
        "routing_metadata_records": routing_metadata_records,
        "upstream_pin_verified": upstream_pin_verified,
    }


def render_qwen_report(
    *,
    run: HarnessRun,
    metrics: dict[str, object],
    estimate: QwenCostEstimate,
    repository_commit: str,
    prompt_hash: str,
    cache_path: str,
) -> str:
    return "\n".join(
        (
            "# WP16 prompted Qwen sanity run",
            "",
            "This is a serialization and configuration sanity check, not a teacher-qualification "
            "or policy-promotion result.",
            "",
            "## Identity",
            "",
            f"- Repository commit: `{repository_commit}`",
            f"- WP16 spec: `{wp16_spec_sha256()}`",
            f"- Manifest: `{run.manifest_sha256}`",
            f"- Human review: `{run.review_sha256}`",
            f"- Prompt template: `{prompt_hash}`",
            f"- Model: `{run.model}` via OpenRouter / `{QWEN_UPSTREAM_PROVIDER}`",
            "- Thinking request: `reasoning.effort=none`, `exclude=true`; one attempt per state",
            f"- Raw resumable cache: `{cache_path}`",
            "",
            "## Observations",
            "",
            f"- Provider outcomes: `{json.dumps(metrics['provider_outcomes'], sort_keys=True)}`",
            f"- Schema validity: `{metrics['schema_valid']}/30`",
            f"- Reference integrity: `{metrics['reference_valid']}/30`",
            f"- Objective license allowance: `{metrics['license_allowed']}/30`",
            f"- Structural agreement (diagnostic only): `{metrics['structural_match']}/30`",
            "- Actual action distribution: "
            f"`{json.dumps(metrics['actual_action_distribution'], sort_keys=True)}`",
            "- Population baseline: "
            f"`{json.dumps(metrics['expected_action_distribution'], sort_keys=True)}`",
            f"- Provider attempts: `{metrics['provider_attempts']}`",
            f"- Response models: `{json.dumps(metrics['response_models'])}`",
            f"- Response providers: `{json.dumps(metrics['response_providers'])}`",
            f"- Routing metadata: `{metrics['routing_metadata_records']}/30`",
            f"- Parasail pin verification: "
            f"`{'PASS' if metrics['upstream_pin_verified'] else 'FAIL'}`",
            "",
            "## Thinking-disabled verification",
            "",
            f"- Request-setting violations: `{metrics['request_reasoning_config_violations']}`",
            f"- Reasoning-usage records: `{metrics['reasoning_usage_records']}/30`",
            f"- Provider-reported reasoning tokens: `{metrics['reasoning_tokens']}`",
            "- Responses carrying visible reasoning: "
            f"`{metrics['responses_with_visible_reasoning']}`",
            f"- Thinking-disabled check: `{_thinking_status(metrics)}`",
            "",
            "## Usage and cost",
            "",
            f"- Provider usage: `{json.dumps(run.usage.as_json(), sort_keys=True)}`",
            "- Provider-reported cost: "
            + (
                f"`${metrics['provider_reported_cost_usd']}`"
                if metrics["provider_reported_cost_usd"] is not None
                else "`unavailable`"
            ),
            f"- Offline expected no-cache estimate: `${_money(estimate.expected_no_cache_usd)}`",
            f"- Offline no-cache ceiling: `${_money(estimate.ceiling_no_cache_usd)}`",
            f"- Pricing snapshot ({QWEN_PRICING_SOURCE_DATE}): "
            f"`${QWEN_INPUT_USD_PER_MILLION}/M input`, "
            f"`${QWEN_OUTPUT_USD_PER_MILLION}/M output`; provider billing is authoritative.",
            "",
        )
    )


def _request_disables_reasoning(trace: PolicyCallTrace) -> bool:
    try:
        payload = json.loads(trace.request)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return False
    return bool(
        isinstance(payload, dict)
        and payload.get("model") == QWEN_MODEL
        and payload.get("reasoning") == {"effort": "none", "exclude": True}
        and payload.get("provider")
        == {
            "allow_fallbacks": False,
            "only": [QWEN_UPSTREAM_PROVIDER],
            "require_parameters": True,
        }
    )


def _response_has_visible_reasoning(trace: PolicyCallTrace) -> bool:
    try:
        payload = json.loads(trace.response)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return False
    if not isinstance(payload, dict):
        return False
    output = payload.get("output")
    if _contains_reasoning(output):
        return True
    text = json.dumps(output, ensure_ascii=False).lower()
    return "<think" in text or "</think" in text


def _response_reasoning_tokens(trace: PolicyCallTrace) -> int | None:
    try:
        payload = json.loads(trace.response)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    usage = payload.get("usage") if isinstance(payload, dict) else None
    if not isinstance(usage, dict):
        return None
    candidates = (
        _nested_integer(usage, "output_tokens_details", "reasoning_tokens"),
        _nested_integer(usage, "completion_tokens_details", "reasoning_tokens"),
        _nonnegative_integer(usage.get("reasoning_tokens")),
    )
    present = tuple(value for value in candidates if value is not None)
    return max(present) if present else None


def _response_selected_provider(trace: PolicyCallTrace) -> str | None:
    try:
        payload = json.loads(trace.response)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    metadata = payload.get("openrouter_metadata") if isinstance(payload, dict) else None
    endpoints = metadata.get("endpoints") if isinstance(metadata, dict) else None
    available = endpoints.get("available") if isinstance(endpoints, dict) else None
    if not isinstance(available, list):
        return None
    selected = [
        item.get("provider")
        for item in available
        if isinstance(item, dict) and item.get("selected") is True
    ]
    if len(selected) != 1 or not isinstance(selected[0], str) or not selected[0]:
        return None
    return selected[0]


def _contains_reasoning(value: object) -> bool:
    if isinstance(value, list):
        return any(_contains_reasoning(item) for item in value)
    if not isinstance(value, dict):
        return False
    item_type = value.get("type")
    if isinstance(item_type, str) and "reasoning" in item_type.lower():
        return True
    for key in ("reasoning", "reasoning_content", "reasoning_details"):
        if key in value and value[key] not in (None, "", [], {}):
            return True
    return any(_contains_reasoning(item) for item in value.values())


def _response_cost(trace: PolicyCallTrace) -> Decimal | None:
    try:
        payload = json.loads(trace.response)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    usage = payload.get("usage") if isinstance(payload, dict) else None
    value = usage.get("cost") if isinstance(usage, dict) else None
    if isinstance(value, bool) or not isinstance(value, int | float | str):
        return None
    try:
        parsed = Decimal(str(value))
    except InvalidOperation:
        return None
    return parsed if parsed.is_finite() and parsed >= 0 else None


def _response_string(trace: PolicyCallTrace, key: str) -> str | None:
    try:
        payload = json.loads(trace.response)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    value = payload.get(key) if isinstance(payload, dict) else None
    return value if isinstance(value, str) and value else None


def _nested_integer(mapping: dict[object, object], outer: str, inner: str) -> int | None:
    nested = mapping.get(outer)
    return _nonnegative_integer(nested.get(inner)) if isinstance(nested, dict) else None


def _nonnegative_integer(value: object) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    return None


def _token_cost(tokens: int, rate: Decimal) -> Decimal:
    return Decimal(tokens) * rate / _MILLION


def _money(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.000001")), "f")


def _thinking_status(metrics: dict[str, object]) -> str:
    if not metrics["thinking_audited"]:
        return "NOT EVALUATED"
    return "PASS" if metrics["thinking_disabled"] else "FAIL"
