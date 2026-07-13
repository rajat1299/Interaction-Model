"""Pure WP13 prompt, Batch, and cost construction tests."""

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import httpx
import pytest

from im.policy.base import PolicyCallTrace, PolicyDecision
from im.policy.prompted import (
    ModelPricing,
    PromptArtifacts,
    PromptedPolicy,
    PromptedPolicyConfig,
    PromptRenderer,
    ResponsesRequestBuilder,
    estimate_run_cost,
)
from im.scheduler import ManualClock, TimerScheduler
from im.schema.actions import IdleAction, IdleReason
from im.store import PolicyEventDraft, Store
from im.tick import TickRuntime
from im.tools import ToolAdapter


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


def response_payload(*, text: str | None = None, refusal: str | None = None) -> dict:
    if (text is None) == (refusal is None):
        raise ValueError("provide exactly one response content type")
    content = (
        {"type": "output_text", "text": text}
        if text is not None
        else {"type": "refusal", "refusal": refusal}
    )
    return {
        "id": "resp_test",
        "object": "response",
        "output": [{"type": "message", "role": "assistant", "content": [content]}],
        "status": "completed",
    }


def mock_client(payloads: list[dict]) -> tuple[httpx.AsyncClient, list[bytes]]:
    requests: list[bytes] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request.content)
        return httpx.Response(200, json=payloads.pop(0))

    return (
        httpx.AsyncClient(
            base_url="https://api.openai.com/v1",
            transport=httpx.MockTransport(handler),
        ),
        requests,
    )


@pytest.mark.asyncio
async def test_prompted_policy_accepts_valid_mocked_response() -> None:
    client, requests = mock_client(
        [
            response_payload(
                text='{"type":"idle","reason":"no_trigger","related_event_id":null}'
            )
        ]
    )
    async with client:
        policy = PromptedPolicy(builder(), api_key="test-key", client=client)
        decision = await policy.decide(b'{"v":1}')

    assert isinstance(decision, PolicyDecision)
    assert isinstance(decision.attempt, IdleAction)
    assert decision.attempt.reason is IdleReason.NO_TRIGGER
    assert [call.outcome for call in decision.calls] == ["completed"]
    assert decision.calls[0].request == requests[0]
    assert b"test-key" not in requests[0]


@pytest.mark.asyncio
async def test_prompted_policy_retries_invalid_then_accepts_valid() -> None:
    client, requests = mock_client(
        [
            response_payload(text='{"type":"idle","reason":"no_trigger"}'),
            response_payload(
                text='{"type":"idle","reason":"no_trigger","related_event_id":null}'
            ),
        ]
    )
    async with client:
        decision = await PromptedPolicy(
            builder(), api_key="test-key", client=client
        ).decide(b'{"v":1}')

    assert isinstance(decision, PolicyDecision)
    assert isinstance(decision.attempt, IdleAction)
    assert [call.outcome for call in decision.calls] == ["invalid", "completed"]
    assert len(requests) == 2
    retry = json.loads(requests[1])
    assert len(retry["input"]) == 3
    assert "failed local action validation" in retry["input"][2]["content"][0]["text"]


@pytest.mark.asyncio
async def test_prompted_policy_does_not_retry_refusal() -> None:
    client, requests = mock_client([response_payload(refusal="cannot comply")])
    async with client:
        decision = await PromptedPolicy(
            builder(), api_key="test-key", client=client
        ).decide(b'{"v":1}')

    assert isinstance(decision, PolicyDecision)
    assert decision.attempt == {"provider_refusal": True}
    assert [call.outcome for call in decision.calls] == ["refusal"]
    assert len(requests) == 1


class TracedIdlePolicy:
    def __init__(self, trace: PolicyCallTrace) -> None:
        self.trace = trace

    async def decide(self, _policy_bytes: bytes) -> object:
        return PolicyDecision(
            attempt=IdleAction(
                type="idle",
                reason=IdleReason.NO_TRIGGER,
                related_event_id=None,
            ),
            calls=(self.trace,),
        )


@pytest.mark.asyncio
async def test_tick_records_exact_provider_exchange_before_action_audit(tmp_path: Path) -> None:
    store = Store(tmp_path / "session.sqlite3")
    clock = ManualClock(wall_utc=datetime(2026, 7, 12, 12, tzinfo=UTC))
    trace = PolicyCallTrace(
        attempt_index=1,
        model="gpt-5.6-terra",
        prompt_hash="sha256:" + "a" * 64,
        request=b'{"large":"request"}',
        response=b'{"large":"response"}',
        latency_ms=12,
        http_status=200,
        outcome="completed",
    )
    runtime = TickRuntime(
        store=store,
        policy=TracedIdlePolicy(trace),
        scheduler=TimerScheduler(store, clock),
        tools=ToolAdapter(store, clock),
        clock=clock,
    )
    snapshot = PolicyEventDraft(
        id=store.allocate_id("event"),
        source="user",
        kind="snapshot",
        payload={
            "text": "typing",
            "selection_start_utf16": 6,
            "selection_end_utf16": 6,
            "is_composing": False,
            "edit_kind": "insert",
        },
        occurred_mono_ns=clock.monotonic_ns(),
        activity="active",
    )
    try:
        runtime.enqueue_committed_ingress(snapshot)
        await runtime.run_until_idle()

        (record,) = store.policy_call_records("d_000001")
        assert record.request == trace.request
        assert record.response == trace.response
        assert record.latency_ms == 12
        assert store._connection.execute("SELECT kind FROM audit").fetchall() == [
            ("action_attempt",)
        ]
    finally:
        store.close()
