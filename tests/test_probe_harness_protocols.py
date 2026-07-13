"""WP15 teacher-safe protocol prompt and JSON transport tests."""

import json
from pathlib import Path

import httpx
import pytest

from im.policy.prompted import PromptArtifacts, PromptedPolicyConfig
from im.probes.grading import OpenTextRule
from im.probes.harness.client import JsonResponsesClient, response_usage
from im.probes.harness.models import (
    ListwiseRanking,
    PairwiseChoice,
    SemanticTextVerdict,
)
from im.probes.harness.protocols import ProtocolPromptBuilder, RankedCandidate
from im.schema.actions import IdleAction


def repository_root() -> Path:
    return Path(__file__).resolve().parents[1]


def prompt_builder() -> ProtocolPromptBuilder:
    return ProtocolPromptBuilder(
        PromptArtifacts.from_repository(repository_root()),
        PromptedPolicyConfig(),
    )


def idle(reason: str = "no_trigger") -> IdleAction:
    return IdleAction(type="idle", reason=reason, related_event_id=None)


def response(text: str, *, usage: dict[str, object] | None = None) -> dict[str, object]:
    value: dict[str, object] = {
        "id": "resp_test",
        "object": "response",
        "output": [
            {
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": text}],
            }
        ],
        "status": "completed",
    }
    if usage is not None:
        value["usage"] = usage
    return value


def test_pairwise_prompt_has_no_manifest_labels_or_preferred_position() -> None:
    request = prompt_builder().pairwise(
        policy_stream='{"v":1}',
        candidate_a=idle().model_dump(mode="json"),
        candidate_b=idle("typing_active").model_dump(mode="json"),
    )
    body = json.loads(request.request_bytes)
    rendered = body["input"][1]["content"][0]["text"]

    assert '"candidate_a"' in rendered
    assert '"candidate_b"' in rendered
    assert "negative_class" not in rendered
    assert "expected_action" not in rendered
    assert "tempting" not in rendered
    assert "preferred" not in rendered


def test_listwise_prompt_requires_complete_ranking_without_label_leakage() -> None:
    request = prompt_builder().listwise(
        policy_stream='{"v":1}',
        candidates=(
            RankedCandidate("c01", idle()),
            RankedCandidate("c02", idle("typing_active")),
        ),
    )
    body = json.loads(request.request_bytes)
    user = json.loads(body["input"][1]["content"][0]["text"])

    assert user["response_contract"] == {
        "ranking": "array containing every candidate id exactly once, best to worst"
    }
    assert user["response_contract"]["ranking"] != ["c01", "c02"]
    assert {candidate["id"] for candidate in user["candidates"]} == {"c01", "c02"}
    assert "expected" not in json.dumps(user)


def test_semantic_prompt_uses_rubric_but_not_reference_sentence() -> None:
    action = idle()
    request = prompt_builder().semantic_text(
        policy_stream='{"v":1}',
        action=action,
        rule=OpenTextRule.RESPOND,
    )
    rendered = request.request_bytes.decode("utf-8")

    assert "response_warrant_and_answer_quality_rubric" in rendered
    assert "hidden reference sentence" in rendered
    assert "expected_text" not in rendered


@pytest.mark.asyncio
async def test_json_client_retries_invalid_pairwise_then_retains_usage() -> None:
    payloads = [
        response('{"choice":"left"}'),
        response(
            '{"choice":"A"}',
            usage={
                "input_tokens": 100,
                "input_tokens_details": {
                    "cached_tokens": 80,
                    "cache_write_tokens": 10,
                },
                "output_tokens": 7,
                "output_tokens_details": {"reasoning_tokens": 4},
            },
        ),
    ]
    requests: list[bytes] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request.content)
        return httpx.Response(200, json=payloads.pop(0))

    async with httpx.AsyncClient(
        base_url="https://api.openai.com/v1",
        transport=httpx.MockTransport(handler),
    ) as http_client:
        client = JsonResponsesClient(
            PromptedPolicyConfig(), api_key="test-key", client=http_client
        )
        completion = await client.complete(
            prompt_builder().pairwise(
                policy_stream='{"v":1}',
                candidate_a=idle().model_dump(mode="json"),
                candidate_b=idle("typing_active").model_dump(mode="json"),
            ),
            PairwiseChoice.model_validate,
        )

    assert isinstance(completion.value, PairwiseChoice)
    assert completion.value.choice == "A"
    assert [trace.outcome for trace in completion.traces] == ["invalid", "completed"]
    assert len(requests) == 2
    assert completion.usage.input_tokens == 100
    assert completion.usage.cached_input_tokens == 80
    assert completion.usage.cache_write_tokens == 10
    assert completion.usage.output_tokens == 7
    assert completion.usage.reasoning_tokens == 4


def test_protocol_response_models_close_their_shapes() -> None:
    assert ListwiseRanking.model_validate({"ranking": ["c02", "c01"]}).ranking == (
        "c02",
        "c01",
    )
    assert SemanticTextVerdict.model_validate(
        {"passed": True, "rationale": "The result supports the sentence."}
    ).passed
    with pytest.raises(ValueError, match="duplicate"):
        ListwiseRanking.model_validate({"ranking": ["c01", "c01"]})


def test_usage_parser_ignores_malformed_optional_counts() -> None:
    usage = response_usage(
        {
            "usage": {
                "input_tokens": 10,
                "input_tokens_details": {"cached_tokens": -1, "cache_write_tokens": "bad"},
                "output_tokens": 4,
                "output_tokens_details": {"reasoning_tokens": True},
            }
        }
    )

    assert usage.input_tokens == 10
    assert usage.cached_input_tokens == 0
    assert usage.cache_write_tokens == 0
    assert usage.output_tokens == 4
    assert usage.reasoning_tokens == 0
