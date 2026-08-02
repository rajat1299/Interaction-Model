"""Offline Batch planning, sharding, reconciliation, and decode tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from im.policy.prompted import (
    PromptArtifacts,
    PromptedPolicyConfig,
    PromptRenderer,
    ResponsesRequestBuilder,
)
from im.probes.harness.artifacts import load_approved_catalog
from im.probes.harness.batch import (
    BatchArtifactError,
    BatchArtifactItem,
    BatchDecoder,
    decode_batch_completion,
    parse_batch_artifacts,
    plan_correction,
    plan_primary_work,
    shard_work,
)
from im.probes.harness.planning import plan_generation
from im.probes.harness.protocols import ProtocolPromptBuilder


@pytest.fixture(scope="module")
def repository() -> Path:
    return Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
async def planned(repository: Path):
    catalog = await load_approved_catalog(repository)
    artifacts = PromptArtifacts.from_repository(repository)
    config = PromptedPolicyConfig()
    builder = ResponsesRequestBuilder(PromptRenderer(artifacts), config)
    prompts = ProtocolPromptBuilder(artifacts, config)
    return catalog, builder, prompts, plan_primary_work(catalog, builder, prompts)


def _provider_response(text: str, *, status: str = "completed") -> dict[str, object]:
    return {
        "output": [
            {
                "content": [{"text": text, "type": "output_text"}],
                "role": "assistant",
                "type": "message",
            }
        ],
        "status": status,
        "usage": {
            "input_tokens": 100,
            "input_tokens_details": {"cached_tokens": 80},
            "output_tokens": 5,
            "output_tokens_details": {"reasoning_tokens": 3},
        },
    }


def _artifact_line(custom_id: str, body: dict[str, object]) -> bytes:
    return (
        json.dumps(
            {
                "custom_id": custom_id,
                "error": None,
                "id": f"batch_req_{custom_id}",
                "response": {
                    "body": body,
                    "request_id": f"req_{custom_id}",
                    "status_code": 200,
                },
            },
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
        + b"\n"
    )


def test_primary_plan_is_complete_unique_and_uses_shared_identity(planned) -> None:
    catalog, builder, _, items = planned

    assert len(items) == 1_152
    assert len({item.custom_id for item in items}) == 1_152
    assert [item.decoder for item in items].count(BatchDecoder.ACTION) == 144
    assert [item.decoder for item in items].count(BatchDecoder.PAIRWISE) == 864
    assert [item.decoder for item in items].count(BatchDecoder.LISTWISE) == 144
    shared = plan_generation(catalog, builder, catalog.manifest.probes[0])
    assert items[0].identity == shared.identity
    assert items[0].body == shared.body


def test_shards_are_deterministic_newline_terminated_and_boundary_bounded(planned) -> None:
    *_, items = planned
    subset = items[:5]

    first = shard_work("p0", subset, max_enqueued_tokens=10_000_000, max_requests=2)
    second = shard_work("p0", subset, max_enqueued_tokens=10_000_000, max_requests=2)

    assert first == second
    assert [len(shard.items) for shard in first] == [2, 2, 1]
    assert all(shard.input_jsonl.endswith(b"\n") for shard in first)
    assert b"".join(shard.input_jsonl for shard in first) == b"".join(
        item.request_line for item in subset
    )


def test_artifact_reconciliation_uses_custom_ids_not_file_order(planned) -> None:
    *_, items = planned
    expected = items[:3]
    lines = [
        _artifact_line(item.custom_id, _provider_response('{"type":"idle",'
        '"reason":"no_trigger","related_event_id":null}'))
        for item in reversed(expected)
    ]

    mapped = parse_batch_artifacts(
        expected,
        output_jsonl=b"".join(lines),
        error_jsonl=b"",
    )

    assert set(mapped) == {item.custom_id for item in expected}
    assert mapped[expected[0].custom_id].request_id == f"req_{expected[0].custom_id}"

    with pytest.raises(BatchArtifactError, match="duplicate"):
        parse_batch_artifacts(
            expected,
            output_jsonl=b"".join([*lines, lines[0]]),
            error_jsonl=b"",
        )
    with pytest.raises(BatchArtifactError, match="omit"):
        parse_batch_artifacts(
            expected,
            output_jsonl=b"".join(lines[:-1]),
            error_jsonl=b"",
        )


def test_invalid_batch_result_gets_one_shared_correction_and_two_trace_history(
    planned,
) -> None:
    *_, items = planned
    initial = items[144]
    assert initial.decoder is BatchDecoder.PAIRWISE
    invalid_body = _provider_response('{"choice":"left"}')
    decoded = decode_batch_completion(
        initial,
        BatchArtifactItem(
            custom_id=initial.custom_id,
            status_code=200,
            request_id="req_initial",
            body=invalid_body,
            error=None,
            output_line=_artifact_line(initial.custom_id, invalid_body),
        ),
        batch_id="batch_p0",
        stage="p0",
        shard_index=0,
    )

    assert decoded.completion.outcome == "invalid"
    assert decoded.validation_error
    corrected = plan_correction(initial, decoded.validation_error)
    assert corrected.identity == initial.identity
    assert corrected.attempt_index == 2
    assert corrected.custom_id.startswith("p1.")
    assert b"failed local protocol validation" in corrected.request_bytes

    valid_body = _provider_response('{"choice":"A"}')
    final = decode_batch_completion(
        corrected,
        BatchArtifactItem(
            custom_id=corrected.custom_id,
            status_code=200,
            request_id="req_corrected",
            body=valid_body,
            error=None,
            output_line=_artifact_line(corrected.custom_id, valid_body),
        ),
        batch_id="batch_p1",
        stage="p1",
        shard_index=0,
        prior_traces=decoded.completion.traces,
    )

    assert final.completion.outcome == "completed"
    assert final.completion.value == {"choice": "A"}
    assert [trace.attempt_index for trace in final.completion.traces] == [1, 2]
    assert [trace.batch_id for trace in final.completion.traces] == [
        "batch_p0",
        "batch_p1",
    ]
    assert final.completion.usage.input_tokens == 200
