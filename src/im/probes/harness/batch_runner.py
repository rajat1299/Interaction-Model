"""Four-stage resumable Batch execution followed by shared WP15 grading."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import ValidationError

from im.policy.prompted import ResponsesRequestBuilder
from im.probes.grading import grade_generation_structure
from im.probes.harness.artifacts import ApprovedProbeCatalog
from im.probes.harness.batch import (
    BatchWorkItem,
    decode_batch_completion,
    parse_batch_artifacts,
    plan_correction,
    plan_primary_work,
    plan_semantic_work,
    shard_work,
    validation_error_from_completion,
)
from im.probes.harness.batch_api import (
    BatchGateway,
    BatchLifecycleError,
    execute_batch_shard,
)
from im.probes.harness.cache import HarnessCache
from im.probes.harness.client import usage_from_traces
from im.probes.harness.models import BatchJobRecord, HarnessRun, ProviderUsage
from im.probes.harness.protocols import ProtocolPromptBuilder, ProtocolRequest
from im.probes.harness.runner import ProbeHarnessRunner
from im.probes.validate import ProbeValidationError, assert_reference_integrity
from im.schema.actions import ACTION_ADAPTER, Action


@dataclass(frozen=True, slots=True)
class BatchHarnessConfig:
    max_enqueued_tokens: int
    poll_seconds: float = 15

    def __post_init__(self) -> None:
        if (
            isinstance(self.max_enqueued_tokens, bool)
            or not isinstance(self.max_enqueued_tokens, int)
            or self.max_enqueued_tokens <= 0
        ):
            raise ValueError("max_enqueued_tokens must be a positive integer")
        if self.poll_seconds <= 0:
            raise ValueError("poll_seconds must be positive")


@dataclass(frozen=True, slots=True)
class BatchHarnessResult:
    run: HarnessRun
    jobs: tuple[BatchJobRecord, ...]
    submitted_this_invocation_usage: ProviderUsage


class BatchProbeHarnessRunner:
    """Execute P0/P1/S0/S1 through Batch, then reuse the production grader."""

    def __init__(
        self,
        catalog: ApprovedProbeCatalog,
        *,
        generation_builder: ResponsesRequestBuilder,
        prompts: ProtocolPromptBuilder,
        gateway: BatchGateway,
        cache: HarnessCache,
        config: BatchHarnessConfig,
    ) -> None:
        self.catalog = catalog
        self.generation_builder = generation_builder
        self.prompts = prompts
        self.gateway = gateway
        self.cache = cache
        self.config = config
        self._jobs: dict[str, BatchJobRecord] = {}
        self._submitted_usage = ProviderUsage()

    async def run(self) -> BatchHarnessResult:
        primary = plan_primary_work(
            self.catalog,
            self.generation_builder,
            self.prompts,
        )
        await self._execute_stage("p0", primary)
        primary_corrections = self._plan_corrections(primary)
        await self._execute_stage("p1", primary_corrections)

        semantic = self._plan_semantic(primary)
        await self._execute_stage("s0", semantic)
        semantic_corrections = self._plan_corrections(semantic)
        await self._execute_stage("s1", semantic_corrections)

        run = await ProbeHarnessRunner(
            self.catalog,
            generation_builder=self.generation_builder,
            prompts=self.prompts,
            backend=_CacheOnlyBackend(),
            cache=self.cache,
        ).run()
        return BatchHarnessResult(
            run=run,
            jobs=tuple(
                self._jobs[key]
                for key in sorted(
                    self._jobs,
                    key=lambda key: (
                        self._jobs[key].stage,
                        self._jobs[key].shard_index,
                        key,
                    ),
                )
            ),
            submitted_this_invocation_usage=self._submitted_usage,
        )

    async def _execute_stage(
        self,
        stage: str,
        items: tuple[BatchWorkItem, ...],
    ) -> None:
        shards = shard_work(
            stage,
            items,
            max_enqueued_tokens=self.config.max_enqueued_tokens,
        )
        for shard in shards:
            before = self.cache.get_batch_job(shard.input_sha256)
            submitted_now = before is None or before.batch_id is None
            record = await execute_batch_shard(
                shard,
                cache=self.cache,
                gateway=self.gateway,
                poll_seconds=self.config.poll_seconds,
            )
            self._jobs[record.input_sha256] = record
            artifacts = parse_batch_artifacts(
                shard.items,
                output_jsonl=record.output_jsonl,
                error_jsonl=record.error_jsonl,
            )
            indeterminate: list[str] = []
            for item in shard.items:
                history = self.cache.history(item.identity)
                if any(
                    trace.execution_mode != "batch"
                    for completion in history
                    for trace in completion.traces
                ):
                    raise BatchLifecycleError(
                        "the all-Batch run cannot consume synchronous completion provenance"
                    )
                if any(
                    trace.batch_custom_id == item.custom_id
                    for completion in history
                    for trace in completion.traces
                ):
                    continue
                prior_traces = (
                    history[-1].traces if item.attempt_index == 2 and history else ()
                )
                decoded = decode_batch_completion(
                    item,
                    artifacts[item.custom_id],
                    batch_id=record.batch_id or "",
                    stage=stage,
                    shard_index=shard.shard_index,
                    prior_traces=prior_traces,
                )
                self.cache.put(item.identity, decoded.completion)
                if submitted_now:
                    self._submitted_usage += usage_from_traces(
                        (decoded.completion.traces[-1],)
                    )
                if decoded.completion.outcome in {"batch_error", "http_error"}:
                    indeterminate.append(item.identity.digest)
            if record.status != "completed":
                raise BatchLifecycleError(
                    f"Batch {record.batch_id} ended in terminal status {record.status!r}"
                )
            if indeterminate:
                raise BatchLifecycleError(
                    "Batch contained indeterminate provider items: "
                    + ", ".join(indeterminate)
                )

    def _plan_corrections(
        self,
        items: tuple[BatchWorkItem, ...],
    ) -> tuple[BatchWorkItem, ...]:
        corrected: list[BatchWorkItem] = []
        for item in items:
            completion = self.cache.get(item.identity)
            if completion is None:
                raise BatchLifecycleError(
                    f"Batch stage did not materialize cache identity {item.identity.digest}"
                )
            if completion.outcome not in {"incomplete", "invalid"}:
                continue
            if completion.traces and completion.traces[-1].attempt_index >= 2:
                continue
            validation_error = validation_error_from_completion(item, completion)
            if validation_error is None:
                raise BatchLifecycleError(
                    "invalid Batch completion lacks deterministic correction evidence"
                )
            corrected.append(plan_correction(item, validation_error))
        return tuple(corrected)

    def _plan_semantic(
        self,
        primary: tuple[BatchWorkItem, ...],
    ) -> tuple[BatchWorkItem, ...]:
        generation = {item.identity.probe_id: item for item in primary[:144]}
        semantic: list[BatchWorkItem] = []
        for probe in self.catalog.manifest.probes:
            variant = probe.variants[0]
            expected = grade_generation_structure(
                variant.expected_action,
                variant.expected_action,
            )
            if expected.text_rule is None:
                continue
            completion = self.cache.get(generation[probe.probe_id].identity)
            if completion is None:
                raise BatchLifecycleError("generation completion is absent before S0")
            try:
                actual: Action = ACTION_ADAPTER.validate_python(completion.value)
                assert_reference_integrity(
                    actual,
                    self.catalog.views[(probe.probe_id, "v1")],
                )
            except (ProbeValidationError, ValidationError, ValueError):
                continue
            if not grade_generation_structure(
                variant.expected_action,
                actual,
            ).structural_match:
                continue
            semantic.append(
                plan_semantic_work(
                    self.catalog,
                    self.generation_builder,
                    self.prompts,
                    probe_id=probe.probe_id,
                    actual=actual,
                    rule=expected.text_rule,
                )
            )
        return tuple(semantic)


class _CacheOnlyBackend:
    async def generate(self, _policy_bytes: bytes):
        raise BatchLifecycleError("final grading encountered a missing generation cache row")

    async def complete(self, _request: ProtocolRequest, _validator):
        raise BatchLifecycleError("final grading encountered a missing protocol cache row")

    async def aclose(self) -> None:
        return None
