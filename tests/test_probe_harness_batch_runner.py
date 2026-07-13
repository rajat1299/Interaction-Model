"""Full-corpus offline acceptance for the four-stage Batch coordinator."""

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
from im.probes.harness.batch_api import BatchApiObservation
from im.probes.harness.batch_runner import (
    BatchHarnessConfig,
    BatchProbeHarnessRunner,
)
from im.probes.harness.cache import HarnessCache
from im.probes.harness.metrics import compute_metrics
from im.probes.harness.protocols import ProtocolPromptBuilder


def _observation(payload: dict[str, object]) -> BatchApiObservation:
    return BatchApiObservation(
        payload=payload,
        raw=json.dumps(payload, separators=(",", ":"), sort_keys=True).encode(),
    )


class _OracleBatchGateway:
    def __init__(
        self,
        expected_by_variant: dict[tuple[str, str], dict[str, object]],
    ) -> None:
        self.expected_by_variant = expected_by_variant
        self.files: dict[str, bytes] = {}
        self.upload_count = 0
        self.create_count = 0

    async def upload(self, input_jsonl: bytes, _filename: str) -> BatchApiObservation:
        self.upload_count += 1
        file_id = f"file_input_{self.upload_count}"
        self.files[file_id] = input_jsonl
        return _observation({"id": file_id})

    async def create(
        self,
        input_file_id: str,
        _metadata: dict[str, str],
    ) -> BatchApiObservation:
        self.create_count += 1
        batch_id = f"batch_{self.create_count}"
        output_file_id = f"file_output_{self.create_count}"
        self.files[output_file_id] = self._answer(self.files[input_file_id])
        return _observation(
            {
                "error_file_id": None,
                "id": batch_id,
                "output_file_id": output_file_id,
                "status": "completed",
            }
        )

    async def retrieve(self, _batch_id: str) -> BatchApiObservation:
        raise AssertionError("oracle batches complete at creation")

    async def download(self, file_id: str) -> bytes:
        return self.files[file_id]

    def _answer(self, input_jsonl: bytes) -> bytes:
        output: list[bytes] = []
        for raw_line in input_jsonl.splitlines():
            line = json.loads(raw_line)
            custom_id = line["custom_id"]
            body = line["body"]
            parts = custom_id.split(".")
            probe_id = parts[2]
            variant_id = parts[3]
            expected = self.expected_by_variant[(probe_id, variant_id)]
            if parts[1] == "g":
                value = expected
            else:
                payload = json.loads(body["input"][1]["content"][0]["text"])
                protocol = payload["protocol"]
                if protocol == "pairwise-v1":
                    value = {"choice": "A" if payload["candidate_a"] == expected else "B"}
                elif protocol == "listwise-v1":
                    expected_id = next(
                        candidate["id"]
                        for candidate in payload["candidates"]
                        if candidate["action"] == expected
                    )
                    ids = [candidate["id"] for candidate in payload["candidates"]]
                    value = {
                        "ranking": [expected_id]
                        + [candidate_id for candidate_id in ids if candidate_id != expected_id]
                    }
                elif protocol == "open-text-rubric-v1":
                    value = {"passed": True, "rationale": "The text satisfies the rubric."}
                else:  # pragma: no cover - all production protocols are enumerated above.
                    raise AssertionError(protocol)
            response_body = {
                "output": [
                    {
                        "content": [
                            {
                                "text": json.dumps(
                                    value,
                                    separators=(",", ":"),
                                    sort_keys=True,
                                ),
                                "type": "output_text",
                            }
                        ],
                        "role": "assistant",
                        "type": "message",
                    }
                ],
                "status": "completed",
                "usage": {
                    "input_tokens": 10,
                    "input_tokens_details": {"cached_tokens": 8},
                    "output_tokens": 2,
                    "output_tokens_details": {"reasoning_tokens": 1},
                },
            }
            output.append(
                json.dumps(
                    {
                        "custom_id": custom_id,
                        "error": None,
                        "id": f"request_{custom_id}",
                        "response": {
                            "body": response_body,
                            "request_id": f"req_{custom_id}",
                            "status_code": 200,
                        },
                    },
                    separators=(",", ":"),
                    sort_keys=True,
                ).encode()
            )
        return b"\n".join(reversed(output)) + b"\n"


@pytest.mark.asyncio
async def test_full_batch_oracle_matches_shared_wp15_grading_and_resumes(
    tmp_path: Path,
) -> None:
    repository = Path(__file__).resolve().parents[1]
    catalog = await load_approved_catalog(repository)
    artifacts = PromptArtifacts.from_repository(repository)
    config = PromptedPolicyConfig()
    builder = ResponsesRequestBuilder(PromptRenderer(artifacts), config)
    prompts = ProtocolPromptBuilder(artifacts, config)
    gateway = _OracleBatchGateway(
        {
            (probe.probe_id, variant.variant_id): variant.expected_action.model_dump(
                mode="json"
            )
            for probe in catalog.manifest.probes
            for variant in probe.variants
        }
    )
    path = tmp_path / "batch.sqlite"
    with HarnessCache(path) as cache:
        first = await BatchProbeHarnessRunner(
            catalog,
            generation_builder=builder,
            prompts=prompts,
            gateway=gateway,
            cache=cache,
            config=BatchHarnessConfig(max_enqueued_tokens=100_000_000),
        ).run()
        second = await BatchProbeHarnessRunner(
            catalog,
            generation_builder=builder,
            prompts=prompts,
            gateway=gateway,
            cache=cache,
            config=BatchHarnessConfig(max_enqueued_tokens=100_000_000),
        ).run()

    metrics = compute_metrics(first.run)
    assert metrics["all_gates_passed"]
    assert len(first.run.generation) == 144
    assert len(first.run.pairwise) == 864
    assert len(first.run.listwise) == 144
    assert len(first.run.semantic_text) == 22
    assert len(first.jobs) == 2
    assert gateway.upload_count == 2
    assert gateway.create_count == 2
    assert second.run == first.run
    assert second.submitted_this_invocation_usage.input_tokens == 0
