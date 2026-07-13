"""Four-stage resumable Batch execution followed by shared WP15 grading."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, replace

from pydantic import ValidationError

from im.policy.prompted import ResponsesRequestBuilder
from im.probes.grading import grade_generation_structure
from im.probes.harness.artifacts import ApprovedProbeCatalog
from im.probes.harness.batch import (
    BatchArtifactError,
    BatchShard,
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

_INDETERMINATE_OUTCOMES = frozenset({"batch_error", "cancelled", "http_error", "transport_error"})
_PROVIDER_RETRY_SUFFIX = re.compile(r"\.r([1-9][0-9]*)$")


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


@dataclass(frozen=True, slots=True)
class BatchStageResult:
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
        result = await materialize_batch_stage(
            stage,
            items,
            cache=self.cache,
            gateway=self.gateway,
            config=self.config,
        )
        for record in result.jobs:
            self._jobs[record.input_sha256] = record
        self._submitted_usage += result.submitted_this_invocation_usage

    def _plan_corrections(
        self,
        items: tuple[BatchWorkItem, ...],
    ) -> tuple[BatchWorkItem, ...]:
        corrected: list[BatchWorkItem] = []
        for item in items:
            current = self.cache.get(item.identity)
            if current is None:
                raise BatchLifecycleError(
                    f"Batch stage did not materialize cache identity {item.identity.digest}"
                )
            initial_invalid = next(
                (
                    completion
                    for completion in self.cache.history(item.identity)
                    if completion.outcome in {"incomplete", "invalid"}
                    and completion.traces
                    and completion.traces[-1].attempt_index == 1
                ),
                None,
            )
            if initial_invalid is None:
                continue
            validation_error = validation_error_from_completion(item, initial_invalid)
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


async def materialize_batch_stage(
    stage: str,
    items: tuple[BatchWorkItem, ...],
    *,
    cache: HarnessCache,
    gateway: BatchGateway,
    config: BatchHarnessConfig,
) -> BatchStageResult:
    """Execute and decode one independently resumable stage, including pilot subsets."""
    jobs: list[BatchJobRecord] = []
    submitted_usage = ProviderUsage()
    items_by_id = {item.custom_id: item for item in items}
    if len(items_by_id) != len(items):
        raise BatchLifecycleError("Batch stage contains duplicate custom_id values")

    provider_retries: list[BatchWorkItem] = []
    for item in items:
        history = cache.history(item.identity)
        if not history or history[-1].outcome not in _INDETERMINATE_OUTCOMES:
            continue
        if cache.get(item.identity) is not None:  # pragma: no cover - guarded by outcome.
            raise AssertionError("indeterminate cache authorization did not return a retry miss")
        retry_numbers = [
            int(match.group(1))
            for completion in history
            for trace in completion.traces
            if (match := _PROVIDER_RETRY_SUFFIX.search(trace.batch_custom_id or ""))
            is not None
        ]
        retry_number = max(retry_numbers, default=0) + 1
        provider_retries.append(
            replace(item, custom_id=f"{item.custom_id}.r{retry_number}")
        )

    existing = cache.batch_jobs(stage=stage)
    for record in existing:
        shard = _recover_shard(record, items_by_id)
        recovered, usage = await _materialize_shard(
            shard,
            cache=cache,
            gateway=gateway,
            config=config,
        )
        jobs.append(recovered)
        submitted_usage += usage

    pending = tuple(
        item
        for item in (*items, *provider_retries)
        if not _is_materialized(cache, item)
    )
    shards = shard_work(
        stage,
        pending,
        max_enqueued_tokens=config.max_enqueued_tokens,
    )
    for shard in shards:
        record, usage = await _materialize_shard(
            shard,
            cache=cache,
            gateway=gateway,
            config=config,
        )
        jobs.append(record)
        submitted_usage += usage
    return BatchStageResult(
        jobs=tuple(jobs),
        submitted_this_invocation_usage=submitted_usage,
    )


async def _materialize_shard(
    shard: BatchShard,
    *,
    cache: HarnessCache,
    gateway: BatchGateway,
    config: BatchHarnessConfig,
) -> tuple[BatchJobRecord, ProviderUsage]:
    before = cache.get_batch_job(shard.input_sha256)
    submitted_now = before is None or before.batch_id is None
    record = await execute_batch_shard(
        shard,
        cache=cache,
        gateway=gateway,
        poll_seconds=config.poll_seconds,
    )
    artifacts = parse_batch_artifacts(
        shard.items,
        output_jsonl=record.output_jsonl,
        error_jsonl=record.error_jsonl,
    )
    submitted_usage = ProviderUsage()
    indeterminate: list[str] = []
    for item in shard.items:
        if _is_materialized(cache, item):
            continue
        history = cache.history(item.identity)
        prior_traces = (
            history[-1].traces
            if history
            and (
                item.attempt_index == 2
                or _PROVIDER_RETRY_SUFFIX.search(item.custom_id) is not None
            )
            else ()
        )
        decoded = decode_batch_completion(
            item,
            artifacts[item.custom_id],
            batch_id=record.batch_id or "",
            stage=shard.stage,
            shard_index=shard.shard_index,
            prior_traces=prior_traces,
        )
        cache.put(item.identity, decoded.completion)
        if submitted_now:
            submitted_usage += usage_from_traces((decoded.completion.traces[-1],))
        if decoded.completion.outcome in {"batch_error", "http_error"}:
            indeterminate.append(item.identity.digest)
    if record.status != "completed":
        raise BatchLifecycleError(
            f"Batch {record.batch_id} ended in terminal status {record.status!r}"
        )
    if indeterminate:
        raise BatchLifecycleError(
            "Batch contained indeterminate provider items: " + ", ".join(indeterminate)
        )
    return record, submitted_usage


def _is_materialized(cache: HarnessCache, item: BatchWorkItem) -> bool:
    history = cache.history(item.identity)
    if any(
        trace.execution_mode != "batch"
        for completion in history
        for trace in completion.traces
    ):
        raise BatchLifecycleError(
            "the all-Batch run cannot consume synchronous completion provenance"
        )
    return any(
        trace.batch_custom_id == item.custom_id
        for completion in history
        for trace in completion.traces
    )


def _recover_shard(
    record: BatchJobRecord,
    items_by_id: dict[str, BatchWorkItem],
) -> BatchShard:
    ordered: list[BatchWorkItem] = []
    for raw_line in record.input_jsonl.splitlines(keepends=True):
        try:
            parsed = json.loads(raw_line)
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise BatchArtifactError("retained Batch input contains invalid JSONL") from error
        custom_id = parsed.get("custom_id") if isinstance(parsed, dict) else None
        item = items_by_id.get(custom_id) if isinstance(custom_id, str) else None
        if item is None and isinstance(custom_id, str):
            base_id = _PROVIDER_RETRY_SUFFIX.sub("", custom_id)
            base_item = items_by_id.get(base_id)
            if base_item is not None:
                item = replace(base_item, custom_id=custom_id)
        if item is None:
            raise BatchLifecycleError(
                "retained Batch job is not a subset of the current signed stage plan"
            )
        ordered.append(item)
    if len(ordered) != record.request_count or len({item.custom_id for item in ordered}) != len(
        ordered
    ):
        raise BatchLifecycleError("retained Batch input count/custom_id set is inconsistent")
    exact = b"".join(item.request_line for item in ordered)
    if exact != record.input_jsonl:
        raise BatchLifecycleError("retained Batch input bytes differ from current request planning")
    return BatchShard(
        stage=record.stage,
        shard_index=record.shard_index,
        items=tuple(ordered),
        input_jsonl=record.input_jsonl,
        estimated_input_tokens=record.estimated_input_tokens,
        input_sha256=record.input_sha256,
    )
