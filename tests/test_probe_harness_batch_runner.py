"""Full-corpus offline acceptance for the four-stage Batch coordinator."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from im.policy.base import PolicyCallTrace
from im.policy.prompted import (
    PromptArtifacts,
    PromptedPolicyConfig,
    PromptRenderer,
    ResponsesRequestBuilder,
)
from im.probes.harness.artifacts import load_approved_catalog
from im.probes.harness.batch import (
    BatchArtifactItem,
    decode_batch_completion,
    plan_correction,
    plan_primary_work,
    shard_work,
)
from im.probes.harness.batch_api import (
    BatchApiObservation,
    BatchLifecycleError,
    execute_batch_shard,
)
from im.probes.harness.batch_runner import (
    BatchHarnessConfig,
    BatchProbeHarnessRunner,
    materialize_batch_stage,
)
from im.probes.harness.cache import HarnessCache
from im.probes.harness.diagnostic import (
    DIAGNOSTIC_PROBE_IDS,
    compute_diagnostic_metrics,
)
from im.probes.harness.metrics import compute_metrics
from im.probes.harness.models import HarnessCompletion
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
        metadata: dict[str, str],
    ) -> BatchApiObservation:
        self.create_count += 1
        batch_id = f"batch_{self.create_count}"
        output_file_id = f"file_output_{self.create_count}"
        self.files[output_file_id] = self._answer(self.files[input_file_id])
        return _observation(
            {
                "endpoint": "/v1/responses",
                "error_file_id": None,
                "id": batch_id,
                "input_file_id": input_file_id,
                "metadata": metadata,
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


class _TokenLimitOnceGateway(_OracleBatchGateway):
    async def create(
        self,
        input_file_id: str,
        metadata: dict[str, str],
    ) -> BatchApiObservation:
        if self.create_count == 0:
            self.create_count += 1
            return _observation(
                {
                    "endpoint": "/v1/responses",
                    "error_file_id": None,
                    "errors": {
                        "data": [
                            {
                                "code": "token_limit_exceeded",
                                "message": "controlled quota",
                            }
                        ],
                        "object": "list",
                    },
                    "id": "batch_token_limit",
                    "input_file_id": input_file_id,
                    "metadata": metadata,
                    "output_file_id": None,
                    "request_counts": {"completed": 0, "failed": 0, "total": 0},
                    "status": "failed",
                    "usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
                }
            )
        return await super().create(input_file_id, metadata)


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
            config=BatchHarnessConfig(max_enqueued_tokens=1_000_000),
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
    assert second.jobs == first.jobs
    assert second.submitted_this_invocation_usage.input_tokens == 0


@pytest.mark.asyncio
async def test_targeted_batch_diagnostic_uses_shared_execution_and_grading(
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
    with HarnessCache(tmp_path / "diagnostic.sqlite") as cache:
        result = await BatchProbeHarnessRunner(
            catalog,
            generation_builder=builder,
            prompts=prompts,
            gateway=gateway,
            cache=cache,
            config=BatchHarnessConfig(max_enqueued_tokens=100_000_000),
        ).run(probe_ids=DIAGNOSTIC_PROBE_IDS)

    assert len(result.run.generation) == 18
    assert len(result.run.pairwise) == 108
    assert len(result.run.listwise) == 18
    assert len(result.run.semantic_text) == 6
    assert len(result.jobs) == 2
    assert gateway.upload_count == 2
    assert compute_diagnostic_metrics(result.run)["all_gates_passed"] is True


@pytest.mark.asyncio
async def test_downloaded_job_is_recovered_before_changed_cap_can_reshard(
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
    work = plan_primary_work(catalog, builder, prompts)[:4]
    original = shard_work("p0", work, max_enqueued_tokens=100_000_000)[0]
    with HarnessCache(tmp_path / "batch.sqlite") as cache:
        downloaded = await execute_batch_shard(
            original,
            cache=cache,
            gateway=gateway,
            poll_seconds=1,
        )
        assert downloaded.output_jsonl
        assert all(not cache.history(item.identity) for item in work)

        recovered = await materialize_batch_stage(
            "p0",
            work,
            cache=cache,
            gateway=gateway,
            config=BatchHarnessConfig(max_enqueued_tokens=1),
        )

        assert all(cache.history(item.identity) for item in work)
    assert recovered.jobs == (downloaded,)
    assert recovered.submitted_this_invocation_usage.input_tokens == 0
    assert gateway.create_count == 1


@pytest.mark.asyncio
async def test_correction_plan_remains_stable_after_attempt_two_is_materialized(
    tmp_path: Path,
) -> None:
    repository = Path(__file__).resolve().parents[1]
    catalog = await load_approved_catalog(repository)
    artifacts = PromptArtifacts.from_repository(repository)
    config = PromptedPolicyConfig()
    builder = ResponsesRequestBuilder(PromptRenderer(artifacts), config)
    prompts = ProtocolPromptBuilder(artifacts, config)
    initial = plan_primary_work(catalog, builder, prompts)[144]
    invalid_payload = _response_body('{"choice":"left"}')
    first = decode_batch_completion(
        initial,
        BatchArtifactItem(
            custom_id=initial.custom_id,
            status_code=200,
            request_id="req_first",
            body=invalid_payload,
            error=None,
        ),
        batch_id="batch_p0",
        stage="p0",
        shard_index=0,
    )
    correction = plan_correction(initial, first.validation_error or "invalid")
    second = decode_batch_completion(
        correction,
        BatchArtifactItem(
            custom_id=correction.custom_id,
            status_code=200,
            request_id="req_second",
            body=_response_body('{"choice":"A"}'),
            error=None,
        ),
        batch_id="batch_p1",
        stage="p1",
        shard_index=0,
        prior_traces=first.completion.traces,
    )
    gateway = _OracleBatchGateway(
        {
            (probe.probe_id, variant.variant_id): variant.expected_action.model_dump(
                mode="json"
            )
            for probe in catalog.manifest.probes
            for variant in probe.variants
        }
    )
    with HarnessCache(tmp_path / "batch.sqlite") as cache:
        cache.put(initial.identity, first.completion)
        cache.put(initial.identity, second.completion)
        runner = BatchProbeHarnessRunner(
            catalog,
            generation_builder=builder,
            prompts=prompts,
            gateway=gateway,
            cache=cache,
            config=BatchHarnessConfig(max_enqueued_tokens=1_000_000),
        )
        assert runner._plan_corrections((initial,)) == (correction,)


def _response_body(text: str) -> dict[str, object]:
    return {
        "output": [
            {
                "content": [{"text": text, "type": "output_text"}],
                "role": "assistant",
                "type": "message",
            }
        ],
        "status": "completed",
    }


@pytest.mark.asyncio
async def test_explicit_provider_retry_uses_distinct_custom_id_without_consuming_correction(
    tmp_path: Path,
) -> None:
    repository = Path(__file__).resolve().parents[1]
    catalog = await load_approved_catalog(repository)
    artifacts = PromptArtifacts.from_repository(repository)
    config = PromptedPolicyConfig()
    builder = ResponsesRequestBuilder(PromptRenderer(artifacts), config)
    prompts = ProtocolPromptBuilder(artifacts, config)
    item = plan_primary_work(catalog, builder, prompts)[0]
    path = tmp_path / "batch.sqlite"
    failed_trace = PolicyCallTrace(
        attempt_index=1,
        model=item.identity.model,
        prompt_hash=item.prompt_hash,
        request=item.request_bytes,
        response=b"{}",
        latency_ms=0,
        http_status=None,
        outcome="batch_error",
        execution_mode="batch",
        batch_custom_id=item.custom_id,
        batch_id="batch_failed",
        batch_stage="p0",
        batch_shard=0,
        batch_request_line=item.request_line,
        batch_error_line=b'{"custom_id":"failed"}\n',
    )
    with HarnessCache(path) as cache:
        cache.put(
            item.identity,
            HarnessCompletion(
                value={"provider_indeterminate": True},
                outcome="batch_error",
                traces=(failed_trace,),
            ),
        )
    gateway = _OracleBatchGateway(
        {
            (probe.probe_id, variant.variant_id): variant.expected_action.model_dump(
                mode="json"
            )
            for probe in catalog.manifest.probes
            for variant in probe.variants
        }
    )
    with HarnessCache(
        path,
        retry_indeterminate_keys=frozenset({item.identity.digest}),
    ) as cache:
        result = await materialize_batch_stage(
            "p0",
            (item,),
            cache=cache,
            gateway=gateway,
            config=BatchHarnessConfig(max_enqueued_tokens=1_000_000),
        )
        current = cache.get(item.identity)
        history = cache.history(item.identity)

    assert current is not None and current.outcome == "completed"
    assert [completion.outcome for completion in history] == [
        "batch_error",
        "completed",
    ]
    assert [trace.batch_custom_id for trace in current.traces] == [
        item.custom_id,
        f"{item.custom_id}.r1",
    ]
    assert [trace.attempt_index for trace in current.traces] == [1, 1]
    assert result.submitted_this_invocation_usage.input_tokens == 10
    assert gateway.create_count == 1


@pytest.mark.asyncio
async def test_zero_usage_token_limit_failure_can_be_safely_resharded(
    tmp_path: Path,
) -> None:
    repository = Path(__file__).resolve().parents[1]
    catalog = await load_approved_catalog(repository)
    artifacts = PromptArtifacts.from_repository(repository)
    config = PromptedPolicyConfig()
    builder = ResponsesRequestBuilder(PromptRenderer(artifacts), config)
    prompts = ProtocolPromptBuilder(artifacts, config)
    work = plan_primary_work(catalog, builder, prompts)[:4]
    gateway = _TokenLimitOnceGateway(
        {
            (probe.probe_id, variant.variant_id): variant.expected_action.model_dump(
                mode="json"
            )
            for probe in catalog.manifest.probes
            for variant in probe.variants
        }
    )
    with HarnessCache(tmp_path / "batch.sqlite") as cache:
        with pytest.raises(BatchLifecycleError, match="smaller"):
            await materialize_batch_stage(
                "p0",
                work,
                cache=cache,
                gateway=gateway,
                config=BatchHarnessConfig(max_enqueued_tokens=1_000_000),
            )
        assert all(not cache.history(item.identity) for item in work)
        first_job = cache.batch_jobs(stage="p0")[0]
        assert first_job.status == "failed"

        resumed = await materialize_batch_stage(
            "p0",
            work,
            cache=cache,
            gateway=gateway,
            config=BatchHarnessConfig(max_enqueued_tokens=30_000),
        )

        assert all(cache.get(item.identity).outcome == "completed" for item in work)
    assert resumed.jobs[0] == first_job
    assert all(job.status == "completed" for job in resumed.jobs[1:])
    assert resumed.submitted_this_invocation_usage.input_tokens == 40
