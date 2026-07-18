"""Fail-closed WP1-9 teacher-canary planning and sharded Batch execution."""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from im.assets.model import canonical_artifact_bytes
from im.config import estimate_tokens
from im.generation.teacher_canary import verify_teacher_canary_packet
from im.policy.prompted import (
    ModelPricing,
    PromptArtifacts,
    PromptedPolicyConfig,
    PromptRenderer,
    ResponsesRequestBuilder,
)
from im.probes.harness.batch import (
    BatchArtifactError,
    BatchDecoder,
    BatchShard,
    BatchWorkItem,
    decode_batch_completion,
    parse_batch_artifacts,
    shard_work,
)
from im.probes.harness.batch_api import BatchGateway, BatchLifecycleError
from im.probes.harness.batch_runner import BatchHarnessConfig, materialize_batch_stage
from im.probes.harness.cache import HarnessCache
from im.probes.harness.client import response_usage
from im.probes.harness.cost import usage_cost
from im.probes.harness.identity import cache_identity, digest
from im.probes.harness.models import BatchJobRecord, HarnessProtocol, ProviderUsage
from im.schema.actions import ACTION_ADAPTER
from im.schema.events import StateCheckpointEvent
from im.serialize import EventSerializationError, parse_event, render_event

_EXPECTED_DECISIONS = 265
_EXPECTED_OUTPUT_TOKENS = 300
_MAX_OUTPUT_TOKENS = 8_192
_PROVIDER_ENQUEUED_TOKEN_LIMIT = 900_000
_PACKET_SHA256 = (
    "sha256:869461d4b411fe6813916c8d19de2ce7ae877b151dfd78bd1669aca5cc05927b"
)
_STAGE = "tc0"


class TeacherCanaryRunError(RuntimeError):
    """The sealed canary cannot be planned or reported safely."""


@dataclass(frozen=True, slots=True)
class TeacherCanaryCost:
    """Expected Batch estimate and explicit maximum-spend approval ceiling."""

    input_tokens: int
    expected_output_tokens: int
    maximum_output_tokens: int
    expected_usd: Decimal
    approval_ceiling_usd: Decimal
    pricing_source_date: str
    batch_multiplier: Decimal

    def as_json(self) -> dict[str, object]:
        return {
            "batch_multiplier": format(self.batch_multiplier, "f"),
            "expected_input_tokens": self.input_tokens,
            "expected_output_tokens": self.expected_output_tokens,
            "expected_usd": format(self.expected_usd, "f"),
            "maximum_output_tokens": self.maximum_output_tokens,
            "maximum_output_tokens_per_request": _MAX_OUTPUT_TOKENS,
            "approval_ceiling_usd": format(self.approval_ceiling_usd, "f"),
            "pricing_source_date": self.pricing_source_date,
        }


@dataclass(frozen=True, slots=True)
class TeacherCanaryDecision:
    """One sealed oracle decision and its exact teacher-visible prefix."""

    stream_sha256: str
    call_index: int
    observed_policy_seq: int
    prefix_bytes: bytes
    oracle_action: dict[str, object]
    item: BatchWorkItem


@dataclass(frozen=True, slots=True)
class TeacherCanaryPlan:
    """The exact sharded provider plan derived from the frozen packet."""

    packet: Path
    packet_sha256: str
    manifest_sha256: str
    builder: ResponsesRequestBuilder
    pricing: ModelPricing
    decisions: tuple[TeacherCanaryDecision, ...]
    cost: TeacherCanaryCost
    max_enqueued_tokens: int
    shards: tuple[BatchShard, ...]

    @property
    def items(self) -> tuple[BatchWorkItem, ...]:
        return tuple(decision.item for decision in self.decisions)

    def as_json(self) -> dict[str, object]:
        return {
            "api_call_performed": False,
            "cost_estimate": self.cost.as_json(),
            "decisions": len(self.decisions),
            "manifest_sha256": self.manifest_sha256,
            "model": self.builder.config.model,
            "packet": str(self.packet),
            "packet_sha256": self.packet_sha256,
            "reasoning_effort": self.builder.config.reasoning_effort,
            "requests": len(self.items),
            "max_enqueued_tokens": self.max_enqueued_tokens,
            "shards": [
                {
                    "estimated_input_tokens": shard.estimated_input_tokens,
                    "input_bytes": len(shard.input_jsonl),
                    "input_sha256": shard.input_sha256,
                    "request_count": len(shard.items),
                    "shard_index": shard.shard_index,
                    "stage": shard.stage,
                }
                for shard in self.shards
            ],
        }


@dataclass(frozen=True, slots=True)
class TeacherCanaryExecution:
    """Completed provider evidence and its canonical all-decision comparison."""

    jobs: tuple[BatchJobRecord, ...]
    provider_usage: ProviderUsage
    report: dict[str, object]


@dataclass(frozen=True, slots=True)
class _Segment:
    index: int
    first_seq: int
    last_seq: int
    lines: tuple[bytes, ...]
    sequences: tuple[int, ...]


def plan_teacher_canary(
    repository: Path,
    packet: Path,
    *,
    max_enqueued_tokens: int,
) -> TeacherCanaryPlan:
    """Verify the frozen packet and render exactly its 265 sealed decision prefixes."""
    if max_enqueued_tokens >= _PROVIDER_ENQUEUED_TOKEN_LIMIT:
        raise TeacherCanaryRunError(
            "teacher-canary shard ceiling must stay below the known 900000-token provider limit"
        )
    repository = repository.resolve()
    packet = packet.resolve()
    try:
        verified = verify_teacher_canary_packet(packet)
    except ValueError as error:
        raise TeacherCanaryRunError(
            f"teacher-canary packet verification failed: {error}"
        ) from error
    if verified.decision_count != _EXPECTED_DECISIONS:
        raise TeacherCanaryRunError(
            f"teacher-canary packet must contain exactly {_EXPECTED_DECISIONS} decisions"
        )

    manifest_bytes = _read(packet / "manifest.json", "packet manifest")
    manifest = _json_object(manifest_bytes, "packet manifest")
    streams = manifest.get("streams")
    if not isinstance(streams, list):
        raise TeacherCanaryRunError("packet manifest has no stream list")
    packet_sha256 = digest(_read(packet / "SHA256SUMS", "packet checksums"))
    if packet_sha256 != _PACKET_SHA256:
        raise TeacherCanaryRunError("teacher-canary packet checksums changed")
    manifest_sha256 = digest(manifest_bytes)
    config = PromptedPolicyConfig(
        model="gpt-5.6-terra",
        reasoning_effort="high",
        max_output_tokens=_MAX_OUTPUT_TOKENS,
        max_attempts=1,
    )
    builder = ResponsesRequestBuilder(
        PromptRenderer(PromptArtifacts.from_repository(repository)), config
    )
    pricing = ModelPricing(model=config.model)
    decisions: list[TeacherCanaryDecision] = []

    stream_values = sorted(streams, key=lambda stream: _stream_sha(stream, "packet manifest"))
    if len(stream_values) != len(
        {_stream_sha(stream, "packet manifest") for stream in stream_values}
    ):
        raise TeacherCanaryRunError("packet manifest repeats a stream identity")
    for stream in stream_values:
        stream_sha256 = _stream_sha(stream, "packet manifest")
        stream_id = stream_sha256.removeprefix("sha256:")
        sidecar = _json_object(
            _read(packet / "reviewer" / stream_id / "sidecar.json", f"sidecar {stream_id}"),
            f"sidecar {stream_id}",
        )
        if sidecar.get("stream_sha256") != stream_sha256:
            raise TeacherCanaryRunError(f"sidecar {stream_id} does not bind its stream")
        sidecar_decisions = sidecar.get("decisions")
        if not isinstance(sidecar_decisions, list):
            raise TeacherCanaryRunError(f"sidecar {stream_id} has no decisions")
        if stream.get("decision_count") != len(sidecar_decisions):
            raise TeacherCanaryRunError(f"sidecar {stream_id} decision count changed")
        segments = _segments(packet / "teacher" / stream_id)
        for call_index, raw_decision in enumerate(sidecar_decisions, start=1):
            if not isinstance(raw_decision, dict) or raw_decision.get("call_index") != call_index:
                raise TeacherCanaryRunError(f"sidecar {stream_id} decisions are not in call order")
            observed = raw_decision.get("observed_policy_seq")
            if isinstance(observed, bool) or not isinstance(observed, int) or observed < 0:
                raise TeacherCanaryRunError(
                    f"sidecar {stream_id} has an invalid observed policy seq"
                )
            prefix = _prefix_for(segments, observed, stream_id, call_index)
            action = raw_decision.get("action")
            try:
                oracle_action = ACTION_ADAPTER.validate_python(action).model_dump(mode="json")
            except ValueError as error:
                raise TeacherCanaryRunError(
                    f"sidecar {stream_id} call {call_index} has an invalid oracle action"
                ) from error
            custom_id = f"{_STAGE}.{stream_id}.c{call_index:04d}.a1"
            body = builder.build(prefix)
            identity = cache_identity(
                manifest_sha256=manifest_sha256,
                probe_id=stream_id,
                protocol=HarnessProtocol.GENERATION,
                variant_id=f"call-{call_index}",
                presentation=f"policy-seq-{observed}",
                model=config.model,
                reasoning_effort=config.reasoning_effort,
                prompt_hash=builder.renderer.artifacts.prompt_hash,
                request_bytes=canonical_artifact_bytes(body),
            )
            decisions.append(
                TeacherCanaryDecision(
                    stream_sha256=stream_sha256,
                    call_index=call_index,
                    observed_policy_seq=observed,
                    prefix_bytes=prefix,
                    oracle_action=oracle_action,
                    item=BatchWorkItem(
                        custom_id=custom_id,
                        identity=identity,
                        body=body,
                        prompt_hash=identity.prompt_hash,
                        decoder=BatchDecoder.ACTION,
                    ),
                )
            )

    if len(decisions) != _EXPECTED_DECISIONS:
        raise TeacherCanaryRunError(
            f"reconstructed {len(decisions)} decision prefixes, expected {_EXPECTED_DECISIONS}"
        )
    items = tuple(decision.item for decision in decisions)
    if len({item.custom_id for item in items}) != len(items):
        raise TeacherCanaryRunError("teacher-canary Batch custom_id values are not unique")
    if len({item.identity.digest for item in items}) != len(items):
        raise TeacherCanaryRunError("teacher-canary cache identities are not unique")
    input_tokens = sum(estimate_tokens(item.request_bytes) for item in items)
    shards = shard_work(
        _STAGE,
        items,
        max_enqueued_tokens=max_enqueued_tokens,
    )
    if sum(len(shard.items) for shard in shards) != _EXPECTED_DECISIONS:
        raise TeacherCanaryRunError("teacher-canary Batch shards do not cover every decision")
    cost = _cost(input_tokens, pricing)
    return TeacherCanaryPlan(
        packet=packet,
        packet_sha256=packet_sha256,
        manifest_sha256=manifest_sha256,
        builder=builder,
        pricing=pricing,
        decisions=tuple(decisions),
        cost=cost,
        max_enqueued_tokens=max_enqueued_tokens,
        shards=shards,
    )


async def execute_teacher_canary(
    plan: TeacherCanaryPlan,
    *,
    cache: HarnessCache,
    gateway: BatchGateway,
    poll_seconds: float,
    output: Path,
) -> TeacherCanaryExecution:
    """Run or resume the sealed shards and materialize one complete comparison."""
    _write_plan_artifact(output, plan)
    try:
        await materialize_batch_stage(
            _STAGE,
            plan.items,
            cache=cache,
            gateway=gateway,
            config=BatchHarnessConfig(
                max_enqueued_tokens=plan.max_enqueued_tokens,
                poll_seconds=poll_seconds,
            ),
        )
    except (BatchArtifactError, BatchLifecycleError) as error:
        message = (
            "teacher-canary provider artifacts are incomplete"
            if isinstance(error, BatchArtifactError)
            else f"teacher-canary Batch transport did not complete: {error}"
        )
        jobs = cache.batch_jobs(stage=_STAGE)
        usage = _available_provider_usage(plan, jobs)
        _write_failure_artifacts(
            output,
            jobs,
            _failure_report(
                plan,
                jobs,
                message,
                usage,
                usage_complete=False,
                usage_errors=(str(error),),
            ),
        )
        raise TeacherCanaryRunError(message) from error
    jobs_by_digest = {
        job.input_sha256: job for job in cache.batch_jobs(stage=_STAGE)
    }
    jobs = tuple(
        jobs_by_digest[shard.input_sha256]
        for shard in plan.shards
        if shard.input_sha256 in jobs_by_digest
    )
    if len(jobs) != len(plan.shards) or any(
        job.status != "completed" or not job.batch_id for job in jobs
    ):
        message = "teacher-canary Batch shards are incomplete"
        usage = _available_provider_usage(plan, jobs)
        _write_failure_artifacts(
            output,
            jobs,
            _failure_report(
                plan,
                jobs,
                message,
                usage,
                usage_complete=False,
                usage_errors=(message,),
            ),
        )
        raise TeacherCanaryRunError(message)
    try:
        artifacts = {
            custom_id: artifact
            for shard, job in zip(plan.shards, jobs, strict=True)
            for custom_id, artifact in parse_batch_artifacts(
                shard.items,
                output_jsonl=job.output_jsonl,
                error_jsonl=job.error_jsonl,
            ).items()
        }
    except ValueError as error:
        message = "teacher-canary provider artifacts are incomplete"
        usage = _available_provider_usage(plan, jobs)
        _write_failure_artifacts(
            output,
            jobs,
            _failure_report(
                plan,
                jobs,
                message,
                usage,
                usage_complete=False,
                usage_errors=(str(error),),
            ),
        )
        raise TeacherCanaryRunError(message) from error
    usage, usage_errors = _usage_from_artifacts(plan, artifacts)
    if usage_errors:
        message = "teacher-canary provider usage is incomplete or malformed"
        _write_failure_artifacts(
            output,
            jobs,
            _failure_report(
                plan,
                jobs,
                message,
                usage,
                usage_complete=False,
                usage_errors=tuple(usage_errors),
            ),
        )
        raise TeacherCanaryRunError(message)
    comparisons: list[dict[str, object]] = []
    shard_by_custom_id = {
        item.custom_id: (shard, job)
        for shard, job in zip(plan.shards, jobs, strict=True)
        for item in shard.items
    }
    for decision in plan.decisions:
        shard, job = shard_by_custom_id[decision.item.custom_id]
        decoded = decode_batch_completion(
            decision.item,
            artifacts[decision.item.custom_id],
            batch_id=job.batch_id or "",
            stage=shard.stage,
            shard_index=shard.shard_index,
        )
        if decoded.completion.outcome != "completed" or decoded.validation_error is not None:
            message = (
                f"teacher-canary action {decision.item.custom_id} is not a completed valid action"
            )
            _write_failure_artifacts(
                output,
                jobs,
                _failure_report(plan, jobs, message, usage, usage_complete=True),
            )
            raise TeacherCanaryRunError(message)
        try:
            teacher_action = ACTION_ADAPTER.validate_python(decoded.completion.value).model_dump(
                mode="json"
            )
        except ValueError as error:
            message = f"teacher-canary action {decision.item.custom_id} is invalid"
            _write_failure_artifacts(
                output,
                jobs,
                _failure_report(plan, jobs, message, usage, usage_complete=True),
            )
            raise TeacherCanaryRunError(message) from error
        resolution = _comparison_resolution(teacher_action, decision.oracle_action)
        comparisons.append(
            {
                "action_mismatch": teacher_action != decision.oracle_action,
                "auto_pass": resolution == "auto_pass",
                "causal_disagreement": resolution == "causal_disagreement",
                "call_index": decision.call_index,
                "custom_id": decision.item.custom_id,
                "observed_policy_seq": decision.observed_policy_seq,
                "oracle_action": decision.oracle_action,
                "resolution": resolution,
                "semantic_review_required": resolution == "semantic_review_required",
                "stream_sha256": decision.stream_sha256,
                "teacher_action": teacher_action,
                "unresolved": resolution != "auto_pass",
            }
        )
    report = _report(plan, jobs, comparisons, usage)
    _write_artifacts(output, jobs, report)
    return TeacherCanaryExecution(jobs=jobs, provider_usage=usage, report=report)


def _segments(root: Path) -> tuple[_Segment, ...]:
    paths = sorted(root.glob("*.jsonl"))
    if not paths or len(paths) != len(list(root.iterdir())):
        raise TeacherCanaryRunError(f"teacher stream {root.name} has invalid segment files")
    segments: list[_Segment] = []
    for path in paths:
        raw = _read(path, f"teacher segment {path}")
        if not raw or raw.endswith(b"\n") or b"\r" in raw:
            raise TeacherCanaryRunError(f"teacher segment {path} has invalid framing")
        lines = tuple(raw.split(b"\n"))
        try:
            events = tuple(parse_event(line) for line in lines)
        except (EventSerializationError, ValueError) as error:
            raise TeacherCanaryRunError(f"teacher segment {path} is not canonical JSONL") from error
        if any(render_event(event) != line for event, line in zip(events, lines, strict=True)):
            raise TeacherCanaryRunError(f"teacher segment {path} is not canonical JSONL")
        sequences = tuple(event.seq for event in events)
        if sequences != tuple(range(sequences[0], sequences[0] + len(sequences))):
            raise TeacherCanaryRunError(f"teacher segment {path} has noncontiguous event sequences")
        first = events[0]
        if isinstance(first, StateCheckpointEvent):
            index = first.payload.segment.segment_index
        elif first.seq == 0:
            index = 0
        else:
            raise TeacherCanaryRunError(f"teacher segment {path} lacks its segment checkpoint")
        segments.append(
            _Segment(index, sequences[0], sequences[-1], lines, sequences)
        )
    segments.sort(key=lambda segment: segment.index)
    if [segment.index for segment in segments] != list(range(len(segments))):
        raise TeacherCanaryRunError(f"teacher stream {root.name} has duplicate or missing segments")
    return tuple(segments)


def _prefix_for(
    segments: tuple[_Segment, ...], observed: int, stream_id: str, call_index: int
) -> bytes:
    candidates = [
        segment
        for segment in segments
        if segment.first_seq <= observed <= segment.last_seq
    ]
    if not candidates:
        raise TeacherCanaryRunError(
            f"sidecar {stream_id} call {call_index} has no matching teacher segment"
        )
    segment = candidates[-1]
    try:
        index = segment.sequences.index(observed)
    except ValueError as error:
        raise TeacherCanaryRunError(
            f"sidecar {stream_id} call {call_index} has no exact observed policy event"
        ) from error
    return b"\n".join(segment.lines[: index + 1])


def _cost(input_tokens: int, pricing: ModelPricing) -> TeacherCanaryCost:
    expected_output_tokens = _EXPECTED_DECISIONS * _EXPECTED_OUTPUT_TOKENS
    maximum_output_tokens = _EXPECTED_DECISIONS * _MAX_OUTPUT_TOKENS
    expected = pricing.batch_multiplier * (
        Decimal(input_tokens) * pricing.input_per_million / Decimal(1_000_000)
        + Decimal(expected_output_tokens) * pricing.output_per_million / Decimal(1_000_000)
    )
    approval_ceiling = pricing.batch_multiplier * (
        Decimal(input_tokens) * pricing.input_per_million / Decimal(1_000_000)
        + Decimal(maximum_output_tokens) * pricing.output_per_million / Decimal(1_000_000)
    )
    return TeacherCanaryCost(
        input_tokens=input_tokens,
        expected_output_tokens=expected_output_tokens,
        maximum_output_tokens=maximum_output_tokens,
        expected_usd=expected,
        approval_ceiling_usd=approval_ceiling,
        pricing_source_date=pricing.source_date,
        batch_multiplier=pricing.batch_multiplier,
    )


def _comparison_resolution(
    teacher_action: dict[str, object], oracle_action: dict[str, object]
) -> str:
    """Auto-pass only exact actions; queue text-only decisions for WP1-8 review."""
    if teacher_action == oracle_action:
        return "auto_pass"
    action_type = teacher_action.get("type")
    if action_type != oracle_action.get("type"):
        return "causal_disagreement"
    if action_type == "integrate":
        return (
            "semantic_review_required"
            if teacher_action.get("result_event_id") == oracle_action.get("result_event_id")
            else "causal_disagreement"
        )
    if action_type == "respond":
        return (
            "semantic_review_required"
            if teacher_action.get("reply_to_event_id") == oracle_action.get("reply_to_event_id")
            else "causal_disagreement"
        )
    return "causal_disagreement"


def _report(
    plan: TeacherCanaryPlan,
    jobs: tuple[BatchJobRecord, ...],
    comparisons: list[dict[str, object]],
    usage: ProviderUsage,
) -> dict[str, object]:
    exact_mismatches = sum(bool(item["action_mismatch"]) for item in comparisons)
    disagreements = sum(bool(item["causal_disagreement"]) for item in comparisons)
    semantic_reviews = sum(bool(item["semantic_review_required"]) for item in comparisons)
    auto_passes = sum(bool(item["auto_pass"]) for item in comparisons)
    actual_cost = usage_cost(usage, plan.pricing, billing_multiplier=plan.pricing.batch_multiplier)
    return {
        "batch": _batch_summary(jobs),
        "comparison_count": len(comparisons),
        "cost_estimate": plan.cost.as_json(),
        "decisions": comparisons,
        "format_version": 2,
        "manifest_sha256": plan.manifest_sha256,
        "auto_pass_count": auto_passes,
        "causal_disagreement_count": disagreements,
        "exact_action_mismatch_count": exact_mismatches,
        "model": plan.builder.config.model,
        "packet_sha256": plan.packet_sha256,
        "provider_cost_usd": format(actual_cost, "f"),
        "provider_usage": usage.as_json(),
        "reasoning_effort": plan.builder.config.reasoning_effort,
        "semantic_review_required_count": semantic_reviews,
        "unresolved_count": disagreements + semantic_reviews,
    }


def _failure_report(
    plan: TeacherCanaryPlan,
    jobs: tuple[BatchJobRecord, ...],
    message: str,
    usage: ProviderUsage,
    *,
    usage_complete: bool,
    usage_errors: tuple[str, ...] = (),
) -> dict[str, object]:
    """Record known provider charges without presenting partial usage as actual."""
    available_cost = usage_cost(
        usage,
        plan.pricing,
        billing_multiplier=plan.pricing.batch_multiplier,
    )
    return {
        "available_provider_cost_usd": format(available_cost, "f"),
        "available_provider_usage": usage.as_json(),
        "batch": _batch_summary(jobs),
        "cost_estimate": plan.cost.as_json(),
        "failure": {"message": message, "usage_errors": list(usage_errors)},
        "format_version": 2,
        "manifest_sha256": plan.manifest_sha256,
        "model": plan.builder.config.model,
        "packet_sha256": plan.packet_sha256,
        "provider_cost_usd": format(available_cost, "f") if usage_complete else None,
        "provider_usage": usage.as_json() if usage_complete else None,
        "provider_usage_complete": usage_complete,
        "reasoning_effort": plan.builder.config.reasoning_effort,
    }


def _usage_from_artifacts(
    plan: TeacherCanaryPlan,
    artifacts: dict[str, object],
) -> tuple[ProviderUsage, list[str]]:
    usage = ProviderUsage()
    errors: list[str] = []
    for decision in plan.decisions:
        artifact = artifacts[decision.item.custom_id]
        body = getattr(artifact, "body", None)
        try:
            usage += _strict_provider_usage(body)
        except ValueError as error:
            errors.append(f"{decision.item.custom_id}: {error}")
    return usage, errors


def _available_provider_usage(
    plan: TeacherCanaryPlan,
    jobs: tuple[BatchJobRecord, ...],
) -> ProviderUsage:
    """Salvage only uniquely identified, well-formed usage from malformed artifacts."""
    expected = {decision.item.custom_id for decision in plan.decisions}
    seen: set[str] = set()
    usage = ProviderUsage()
    for job in jobs:
        for artifact_jsonl in (job.output_jsonl, job.error_jsonl):
            for line in artifact_jsonl.splitlines():
                try:
                    artifact = json.loads(line)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    continue
                if not isinstance(artifact, dict):
                    continue
                custom_id = artifact.get("custom_id")
                if (
                    not isinstance(custom_id, str)
                    or custom_id not in expected
                    or custom_id in seen
                ):
                    continue
                seen.add(custom_id)
                response = artifact.get("response")
                body = response.get("body") if isinstance(response, dict) else None
                try:
                    usage += _strict_provider_usage(body)
                except ValueError:
                    continue
    return usage


def _strict_provider_usage(payload: object) -> ProviderUsage:
    if not isinstance(payload, dict):
        raise ValueError("response body is absent")
    raw_usage = payload.get("usage")
    if not isinstance(raw_usage, dict):
        raise ValueError("usage is absent or malformed")
    for key in (
        "input_tokens",
        "prompt_tokens",
        "output_tokens",
        "completion_tokens",
        "reasoning_tokens",
        "total_tokens",
    ):
        _validate_usage_integer(raw_usage, key)
    if not any(key in raw_usage for key in ("input_tokens", "prompt_tokens")):
        raise ValueError("usage lacks input token count")
    if not any(key in raw_usage for key in ("output_tokens", "completion_tokens")):
        raise ValueError("usage lacks output token count")
    for detail_key, token_keys in (
        ("input_tokens_details", ("cached_tokens", "cache_write_tokens", "cache_creation_tokens")),
        ("prompt_tokens_details", ("cached_tokens", "cache_write_tokens", "cache_creation_tokens")),
        ("output_tokens_details", ("reasoning_tokens",)),
        ("completion_tokens_details", ("reasoning_tokens",)),
    ):
        details = raw_usage.get(detail_key)
        if details is None:
            continue
        if not isinstance(details, dict):
            raise ValueError(f"usage {detail_key} is malformed")
        for key in token_keys:
            _validate_usage_integer(details, key)
    normalized = response_usage(payload)
    if normalized.input_tokens <= 0:
        raise ValueError("usage input token count must be positive")
    if normalized.output_tokens <= 0:
        raise ValueError("usage output token count must be positive")
    if normalized.cached_input_tokens + normalized.cache_write_tokens > normalized.input_tokens:
        raise ValueError("usage cached/write token counts exceed input tokens")
    if normalized.reasoning_tokens > normalized.output_tokens:
        raise ValueError("usage reasoning tokens exceed output tokens")
    return normalized


def _validate_usage_integer(mapping: dict[str, object], key: str) -> None:
    if key not in mapping:
        return
    value = mapping[key]
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"usage {key} is malformed")


def _write_artifacts(
    output: Path,
    jobs: tuple[BatchJobRecord, ...],
    report: dict[str, object],
) -> None:
    output.mkdir(parents=True, exist_ok=True)
    (output / "failure.json").unlink(missing_ok=True)
    (output / "comparison.json").unlink(missing_ok=True)
    (output / "teacher-labels.jsonl").unlink(missing_ok=True)
    _write_raw_artifacts(output, jobs)
    _atomic_write(output / "comparison.json", canonical_artifact_bytes(report))
    decisions = report["decisions"]
    if not isinstance(decisions, list):
        raise TeacherCanaryRunError("teacher-canary comparison has no decisions")
    labels = b"".join(
        canonical_artifact_bytes(
            {
                "action": decision["teacher_action"],
                "decision_policy_seq": decision["observed_policy_seq"],
                "label": decision["resolution"],
                "oracle_action": decision["oracle_action"],
                "stream_sha256": decision["stream_sha256"],
            }
        )
        + b"\n"
        for decision in decisions
        if isinstance(decision, dict)
    )
    if labels.count(b"\n") != len(decisions):
        raise TeacherCanaryRunError("teacher-canary label materialization is incomplete")
    _atomic_write(output / "teacher-labels.jsonl", labels)


def _write_failure_artifacts(
    output: Path,
    jobs: tuple[BatchJobRecord, ...],
    failure: dict[str, object],
) -> None:
    output.mkdir(parents=True, exist_ok=True)
    (output / "comparison.json").unlink(missing_ok=True)
    (output / "teacher-labels.jsonl").unlink(missing_ok=True)
    (output / "failure.json").unlink(missing_ok=True)
    _write_raw_artifacts(output, jobs)
    _atomic_write(output / "failure.json", canonical_artifact_bytes(failure))


def _write_raw_artifacts(output: Path, jobs: tuple[BatchJobRecord, ...]) -> None:
    for job in jobs:
        suffix = job.input_sha256.removeprefix("sha256:")[:12]
        shard_output = output / "shards" / f"{job.stage}-{job.shard_index:04d}-{suffix}"
        shard_output.mkdir(parents=True, exist_ok=True)
        _atomic_write(shard_output / "batch-input.jsonl", job.input_jsonl)
        _atomic_write(shard_output / "provider-batch.json", job.latest_batch_json)
        _atomic_write(shard_output / "provider-output.jsonl", job.output_jsonl)
        _atomic_write(shard_output / "provider-error.jsonl", job.error_jsonl)


def _batch_summary(jobs: tuple[BatchJobRecord, ...]) -> dict[str, object]:
    return {
        "jobs": [
            {
                "batch_id": job.batch_id,
                "error_file_id": job.error_file_id,
                "input_file_id": job.input_file_id,
                "input_sha256": job.input_sha256,
                "output_file_id": job.output_file_id,
                "shard_index": job.shard_index,
                "status": job.status,
            }
            for job in jobs
        ],
        "status": (
            "completed"
            if jobs and all(job.status == "completed" for job in jobs)
            else "incomplete"
        ),
    }


def _write_plan_artifact(output: Path, plan: TeacherCanaryPlan) -> None:
    output = output.resolve()
    if output.is_relative_to(plan.packet):
        raise TeacherCanaryRunError(
            "teacher-canary execution artifacts must stay beside the packet"
        )
    plan_bytes = canonical_artifact_bytes(plan.as_json())
    path = output / "plan.json"
    if path.exists() and _read(path, "teacher-canary execution plan") != plan_bytes:
        raise TeacherCanaryRunError("teacher-canary execution plan changed")
    output.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        _atomic_write(path, plan_bytes)


def _atomic_write(path: Path, data: bytes) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_bytes(data)
    temporary.replace(path)


def _stream_sha(stream: object, label: str) -> str:
    if not isinstance(stream, dict):
        raise TeacherCanaryRunError(f"{label} has a non-object stream")
    value = stream.get("stream_sha256")
    if not isinstance(value, str) or not value.startswith("sha256:"):
        raise TeacherCanaryRunError(f"{label} stream has an invalid identity")
    return value


def _json_object(data: bytes, label: str) -> dict[str, object]:
    try:
        value = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise TeacherCanaryRunError(f"{label} is not readable JSON") from error
    if not isinstance(value, dict) or canonical_artifact_bytes(value) != data:
        raise TeacherCanaryRunError(f"{label} is not canonical JSON")
    return value


def _read(path: Path, label: str) -> bytes:
    try:
        return path.read_bytes()
    except OSError as error:
        raise TeacherCanaryRunError(f"{label} is not readable") from error
