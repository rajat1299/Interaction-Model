"""Pure WP13 prompt, Batch, and cost construction tests."""

import json
from decimal import Decimal
from pathlib import Path

import pytest

from im.policy.prompted import (
    ModelPricing,
    PromptArtifacts,
    PromptedPolicyConfig,
    PromptRenderer,
    ResponsesRequestBuilder,
    estimate_run_cost,
)


def repository_root() -> Path:
    return Path(__file__).resolve().parents[1]


def builder() -> ResponsesRequestBuilder:
    artifacts = PromptArtifacts.from_repository(repository_root())
    return ResponsesRequestBuilder(PromptRenderer(artifacts), PromptedPolicyConfig())


def test_renderer_preserves_frozen_template_across_message_boundary() -> None:
    artifacts = PromptArtifacts.from_repository(repository_root())
    rendered = PromptRenderer(artifacts).render(b'{"v":1}')
    expected = (
        artifacts.prompt_template.decode("utf-8")
        .replace("{{behavior_spec}}", artifacts.behavior_spec.decode("utf-8"))
        .replace("{{action_schema}}", artifacts.action_schema.decode("utf-8"))
        .replace("{{policy_stream}}", '{"v":1}')
    )

    assert rendered.system + rendered.user == expected
    assert rendered.prompt_hash.startswith("sha256:")
    assert len(rendered.prompt_hash) == 71


def test_responses_body_is_openai_direct_cached_json_mode_without_credentials() -> None:
    body = builder().build(b'{"kind":"snapshot"}')

    assert body["model"] == "gpt-5.6-terra"
    assert body["reasoning"] == {"effort": "high"}
    assert body["text"] == {"format": {"type": "json_object"}}
    assert body["store"] is False
    assert body["prompt_cache_options"] == {"mode": "explicit", "ttl": "30m"}
    assert body["input"][0]["content"][0]["prompt_cache_breakpoint"] == {  # type: ignore[index]
        "mode": "explicit"
    }
    assert "api_key" not in json.dumps(body).lower()
    assert "authorization" not in json.dumps(body).lower()


def test_batch_jsonl_reuses_exact_sync_body() -> None:
    request_builder = builder()
    policy = b'{"v":1}'
    rendered = request_builder.render_batch_jsonl([("probe:001", policy)])
    line = json.loads(rendered)

    assert rendered.endswith(b"\n")
    assert line == {
        "body": request_builder.build(policy),
        "custom_id": "probe:001",
        "method": "POST",
        "url": "/v1/responses",
    }


def test_batch_rejects_duplicate_or_unsafe_ids() -> None:
    request_builder = builder()
    with pytest.raises(ValueError, match="unique"):
        request_builder.render_batch_jsonl([("same", b"one"), ("same", b"two")])
    with pytest.raises(ValueError, match="safe ASCII"):
        request_builder.build_batch_line("not safe", b"one")


def test_cost_estimate_exposes_expected_and_conservative_scenarios() -> None:
    estimate = estimate_run_cost(
        builder(),
        decisions=10,
        average_policy_bytes=8_000,
        expected_output_tokens=1_000,
    )

    assert estimate.fixed_input_tokens_per_attempt > 1_024
    assert estimate.variable_input_tokens_per_attempt > 0
    assert estimate.synchronous_warm_cache.expected_usd < (
        estimate.synchronous_no_cache.expected_usd
    )
    assert estimate.batch_no_cache.expected_usd == (
        estimate.synchronous_no_cache.expected_usd * Decimal("0.50")
    )
    assert estimate.synchronous_no_cache.ceiling_usd > (
        estimate.synchronous_no_cache.expected_usd
    )


def test_cost_estimate_rejects_wrong_model_pricing() -> None:
    with pytest.raises(ValueError, match="pricing model"):
        estimate_run_cost(
            builder(),
            decisions=1,
            average_policy_bytes=100,
            expected_output_tokens=100,
            pricing=ModelPricing(model="different"),
        )
