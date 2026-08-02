"""WP16 generation-only Qwen population, provider, and reporting tests."""

import json
import os
import subprocess
from collections import Counter
from dataclasses import replace
from pathlib import Path

import httpx
import pytest

from im.policy.base import PolicyCallTrace
from im.policy.prompted import (
    PromptArtifacts,
    PromptedPolicy,
    PromptedPolicyConfig,
    PromptRenderer,
    ResponsesRequestBuilder,
    ResponsesRouting,
)
from im.probes.harness.artifacts import load_approved_catalog
from im.probes.harness.backend import OracleHarnessBackend
from im.probes.harness.cache import HarnessCache
from im.probes.harness.protocols import ProtocolPromptBuilder
from im.probes.harness.runner import ProbeHarnessRunner
from im.probes.harness.wp16 import (
    QWEN_MODEL,
    QWEN_SANITY_PROBE_IDS,
    QWEN_UPSTREAM_PROVIDER,
    compute_qwen_metrics,
    estimate_qwen_cost,
    generation_completions,
    render_qwen_report,
    selected_probes,
    wp16_spec_sha256,
)


@pytest.fixture(scope="module")
def repository() -> Path:
    return Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
async def catalog(repository: Path):
    return await load_approved_catalog(repository)


def qwen_builder(repository: Path) -> ResponsesRequestBuilder:
    artifacts = PromptArtifacts.from_repository(repository)
    config = PromptedPolicyConfig(
        model=QWEN_MODEL,
        provider="openrouter",
        reasoning_effort="none",
        max_output_tokens=1024,
        max_attempts=1,
        base_url="https://openrouter.ai/api/v1",
        routing=ResponsesRouting(
            only=(QWEN_UPSTREAM_PROVIDER,),
            allow_fallbacks=False,
            require_parameters=True,
        ),
    )
    return ResponsesRequestBuilder(PromptRenderer(artifacts), config)


def oracle(catalog) -> OracleHarnessBackend:
    return OracleHarnessBackend(
        {
            variant.policy_stream_sha256: variant.expected_action
            for probe in catalog.manifest.probes
            for variant in probe.variants
        }
    )


def test_population_is_thirty_symmetric_states_covering_the_contract(catalog) -> None:
    probes = selected_probes(catalog)

    assert wp16_spec_sha256() == (
        "sha256:722cdfe6b2759d441bfae7387fcff6ed7e053f02c422112df2d423718371e4bc"
    )
    assert len(QWEN_SANITY_PROBE_IDS) == 30
    assert len(set(QWEN_SANITY_PROBE_IDS)) == 30
    assert {probe.family_id for probe in probes} == set(range(1, 13))
    assert all(
        {f"{stem}-a", f"{stem}-b"}.issubset(QWEN_SANITY_PROBE_IDS)
        for stem in {probe.probe_id[:-2] for probe in probes}
    )
    assert Counter(probe.variants[0].expected_action.type for probe in probes) == {
        "cancel": 1,
        "delegate": 1,
        "idle": 9,
        "integrate": 4,
        "mark": 2,
        "nudge": 5,
        "respond": 3,
        "schedule": 1,
        "skip": 4,
    }


def test_openrouter_request_is_pinned_nonthinking_and_provider_managed_cache(
    repository: Path,
) -> None:
    body = qwen_builder(repository).build(b'W1 {"v":1}')

    assert body["model"] == QWEN_MODEL
    assert body["reasoning"] == {"effort": "none", "exclude": True}
    assert body["provider"] == {
        "allow_fallbacks": False,
        "only": [QWEN_UPSTREAM_PROVIDER],
        "require_parameters": True,
    }
    assert body["text"] == {"format": {"type": "json_object"}}
    assert "prompt_cache_key" not in body
    assert "prompt_cache_options" not in body
    assert "prompt_cache_breakpoint" not in json.dumps(body)
    assert "api_key" not in json.dumps(body).lower()


@pytest.mark.asyncio
async def test_qwen_base_rate_uses_one_attempt_without_correction(repository: Path) -> None:
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "output": [
                    {
                        "type": "message",
                        "content": [{"type": "output_text", "text": "not json"}],
                    }
                ],
                "status": "completed",
            },
        )

    async with httpx.AsyncClient(
        base_url="https://openrouter.ai/api/v1",
        transport=httpx.MockTransport(handler),
    ) as client:
        decision = await PromptedPolicy(
            qwen_builder(repository),
            api_key="test-key",
            extra_headers={"X-OpenRouter-Metadata": "enabled"},
            client=client,
        ).decide(b"stream")

    assert len(requests) == 1
    assert requests[0].headers["X-OpenRouter-Metadata"] == "enabled"
    assert decision.calls[0].outcome == "invalid"


@pytest.mark.asyncio
async def test_generation_only_runner_makes_no_recognition_or_semantic_calls(
    tmp_path: Path,
    repository: Path,
    catalog,
) -> None:
    builder = qwen_builder(repository)
    prompts = ProtocolPromptBuilder(builder.renderer.artifacts, builder.config)
    backend = oracle(catalog)
    with HarnessCache(tmp_path / "wp16.sqlite") as cache:
        run = await ProbeHarnessRunner(
            catalog,
            generation_builder=builder,
            prompts=prompts,
            backend=backend,
            cache=cache,
        ).run_generation_only(probe_ids=QWEN_SANITY_PROBE_IDS)
        completions = generation_completions(catalog, builder, cache)

    assert len(run.generation) == 30
    assert not run.semantic_text
    assert not run.pairwise
    assert not run.listwise
    assert all(result.schema_valid for result in run.generation)
    assert all(result.reference_valid for result in run.generation)
    assert all(result.license_allowed for result in run.generation)
    assert len(completions) == 30


@pytest.mark.asyncio
async def test_reasoning_audit_checks_request_usage_and_visible_response(
    tmp_path: Path,
    repository: Path,
    catalog,
) -> None:
    builder = qwen_builder(repository)
    with HarnessCache(tmp_path / "reasoning.sqlite") as cache:
        run = await ProbeHarnessRunner(
            catalog,
            generation_builder=builder,
            prompts=ProtocolPromptBuilder(builder.renderer.artifacts, builder.config),
            backend=oracle(catalog),
            cache=cache,
        ).run_generation_only(probe_ids=QWEN_SANITY_PROBE_IDS)
        completions = generation_completions(catalog, builder, cache)

    trace = PolicyCallTrace(
        attempt_index=1,
        model=QWEN_MODEL,
        prompt_hash=builder.renderer.artifacts.prompt_hash,
        request=json.dumps(builder.build(b"stream")).encode(),
        response=json.dumps(
            {
                "model": QWEN_MODEL,
                "output": [{"type": "reasoning", "summary": "should not appear"}],
                "status": "completed",
            }
        ).encode(),
        latency_ms=1,
        http_status=200,
        outcome="completed",
    )
    audited = (replace(completions[0], traces=(trace,)), *completions[1:])
    metrics = compute_qwen_metrics(run, audited)

    assert metrics["request_reasoning_config_violations"] == 0
    assert metrics["responses_with_visible_reasoning"] == 1
    assert not metrics["thinking_disabled"]


@pytest.mark.asyncio
async def test_live_audit_requires_one_complete_trace_and_zero_reasoning_evidence(
    tmp_path: Path,
    repository: Path,
    catalog,
) -> None:
    builder = qwen_builder(repository)
    with HarnessCache(tmp_path / "live-audit.sqlite") as cache:
        run = await ProbeHarnessRunner(
            catalog,
            generation_builder=builder,
            prompts=ProtocolPromptBuilder(builder.renderer.artifacts, builder.config),
            backend=oracle(catalog),
            cache=cache,
        ).run_generation_only(probe_ids=QWEN_SANITY_PROBE_IDS)
        mock_completions = generation_completions(catalog, builder, cache)

    with pytest.raises(ValueError, match="exactly one provider trace"):
        compute_qwen_metrics(run, mock_completions, require_provider_traces=True)

    response = {
        "model": QWEN_MODEL,
        "openrouter_metadata": {
            "endpoints": {
                "available": [
                    {"provider": "AkashML", "model": QWEN_MODEL, "selected": True}
                ]
            }
        },
        "output": [{"type": "message", "content": []}],
        "status": "completed",
        "usage": {
            "input_tokens": 100,
            "output_tokens": 5,
            "output_tokens_details": {"reasoning_tokens": 0},
            "cost": 0.00002,
        },
    }
    trace = PolicyCallTrace(
        attempt_index=1,
        model=QWEN_MODEL,
        prompt_hash=builder.renderer.artifacts.prompt_hash,
        request=json.dumps(builder.build(b"stream")).encode(),
        response=json.dumps(response).encode(),
        latency_ms=1,
        http_status=200,
        outcome="completed",
    )
    live_completions = tuple(
        replace(completion, traces=(trace,)) for completion in mock_completions
    )
    metrics = compute_qwen_metrics(run, live_completions, require_provider_traces=True)

    assert metrics["thinking_disabled"]
    assert metrics["reasoning_usage_records"] == 30
    assert metrics["upstream_pin_verified"]
    assert metrics["routing_metadata_records"] == 30

    response["usage"] = {"input_tokens": 100, "output_tokens": 5}
    missing_usage_trace = replace(trace, response=json.dumps(response).encode())
    missing_usage = (
        replace(live_completions[0], traces=(missing_usage_trace,)),
        *live_completions[1:],
    )
    incomplete_metrics = compute_qwen_metrics(
        run,
        missing_usage,
        require_provider_traces=True,
    )
    assert not incomplete_metrics["thinking_disabled"]
    assert incomplete_metrics["reasoning_usage_records"] == 29


@pytest.mark.asyncio
async def test_cost_and_one_page_report_are_non_promotional(
    tmp_path: Path,
    repository: Path,
    catalog,
) -> None:
    builder = qwen_builder(repository)
    estimate = estimate_qwen_cost(catalog, builder)
    with HarnessCache(tmp_path / "report.sqlite") as cache:
        run = await ProbeHarnessRunner(
            catalog,
            generation_builder=builder,
            prompts=ProtocolPromptBuilder(builder.renderer.artifacts, builder.config),
            backend=oracle(catalog),
            cache=cache,
        ).run_generation_only(probe_ids=QWEN_SANITY_PROBE_IDS)
        completions = generation_completions(catalog, builder, cache)
    metrics = compute_qwen_metrics(run, completions)
    report = render_qwen_report(
        run=run,
        metrics=metrics,
        estimate=estimate,
        repository_commit="test",
        prompt_hash=builder.renderer.artifacts.prompt_hash,
        cache_path="ignored.sqlite",
    )

    assert estimate.requests == 30
    assert estimate.expected_no_cache_usd < estimate.ceiling_no_cache_usd
    assert "not a teacher-qualification or policy-promotion result" in report
    assert "Thinking-disabled check: `NOT EVALUATED`" in report
    assert "Schema validity: `30/30`" in report
    assert len(report.splitlines()) < 70


def test_estimate_mode_needs_no_openrouter_credential(repository: Path) -> None:
    environment = os.environ.copy()
    environment.pop("OPENROUTER_API_KEY", None)
    result = subprocess.run(
        [
            str(repository / ".venv/bin/python"),
            str(repository / "scripts/run_qwen_sanity.py"),
            "--mode",
            "estimate",
            "--repository",
            str(repository),
        ],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    )
    payload = json.loads(result.stdout)

    assert payload["api_call_performed"] is False
    assert payload["estimate"]["requests"] == 30
    assert payload["model"] == QWEN_MODEL
