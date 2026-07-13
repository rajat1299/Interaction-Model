"""Deterministic OpenAI Batch planning, sharding, and artifact decoding for WP15."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum

from pydantic import BaseModel

from im.config import estimate_tokens
from im.policy.base import PolicyCallTrace
from im.policy.prompted import (
    ResponsesRequestBuilder,
    action_retry_body,
    build_batch_line,
    decode_action_response,
)
from im.probes.harness.artifacts import ApprovedProbeCatalog
from im.probes.harness.client import (
    decode_protocol_response,
    protocol_retry_body,
    usage_from_traces,
)
from im.probes.harness.identity import canonical_request_bytes, digest
from im.probes.harness.models import (
    CacheIdentity,
    HarnessCompletion,
    ListwiseRanking,
    PairwiseChoice,
    SemanticTextVerdict,
)
from im.probes.harness.planning import (
    plan_generation,
    plan_listwise,
    plan_pairwise,
    plan_semantic,
)
from im.probes.harness.protocols import ProtocolPromptBuilder
from im.probes.model import ExpectedPosition
from im.schema.actions import Action

_MAX_BATCH_REQUESTS = 50_000
_MAX_BATCH_BYTES = 190_000_000


class BatchArtifactError(ValueError):
    """Downloaded Batch output is not a total one-to-one image of its input."""


class BatchDecoder(StrEnum):
    ACTION = "action"
    PAIRWISE = "pairwise"
    LISTWISE = "listwise"
    SEMANTIC = "semantic"


@dataclass(frozen=True, slots=True)
class BatchWorkItem:
    custom_id: str
    identity: CacheIdentity
    body: dict[str, object]
    prompt_hash: str
    decoder: BatchDecoder
    attempt_index: int = 1

    @property
    def request_bytes(self) -> bytes:
        return canonical_request_bytes(self.body)

    @property
    def request_line(self) -> bytes:
        return canonical_request_bytes(build_batch_line(self.custom_id, self.body)) + b"\n"


@dataclass(frozen=True, slots=True)
class BatchShard:
    stage: str
    shard_index: int
    items: tuple[BatchWorkItem, ...]
    input_jsonl: bytes
    estimated_input_tokens: int
    input_sha256: str


@dataclass(frozen=True, slots=True)
class BatchArtifactItem:
    custom_id: str
    status_code: int | None
    request_id: str | None
    body: dict[str, object] | None
    error: object | None
    output_line: bytes = b""
    error_line: bytes = b""


@dataclass(frozen=True, slots=True)
class DecodedBatchCompletion:
    completion: HarnessCompletion
    validation_error: str | None


def plan_primary_work(
    catalog: ApprovedProbeCatalog,
    builder: ResponsesRequestBuilder,
    prompts: ProtocolPromptBuilder,
) -> tuple[BatchWorkItem, ...]:
    """Build the exact 1,152 independent P0 calls in stable manifest order."""
    items: list[BatchWorkItem] = []
    for probe in catalog.manifest.probes:
        planned = plan_generation(catalog, builder, probe)
        items.append(
            BatchWorkItem(
                custom_id=f"p0.g.{probe.probe_id}.v1.a1",
                identity=planned.identity,
                body=planned.body,
                prompt_hash=planned.identity.prompt_hash,
                decoder=BatchDecoder.ACTION,
            )
        )
    for probe in catalog.manifest.probes:
        for variant in probe.variants:
            for position in (ExpectedPosition.A, ExpectedPosition.B):
                planned = plan_pairwise(
                    catalog,
                    builder,
                    prompts,
                    probe,
                    variant.variant_id,
                    position,
                )
                items.append(
                    BatchWorkItem(
                        custom_id=(
                            f"p0.p.{probe.probe_id}.{variant.variant_id}."
                            f"{position.value}.a1"
                        ),
                        identity=planned.identity,
                        body=planned.request.body,
                        prompt_hash=planned.identity.prompt_hash,
                        decoder=BatchDecoder.PAIRWISE,
                    )
                )
    for probe in catalog.manifest.probes:
        planned = plan_listwise(catalog, builder, prompts, probe)
        items.append(
            BatchWorkItem(
                custom_id=f"p0.l.{probe.probe_id}.v1.a1",
                identity=planned.identity,
                body=planned.request.body,
                prompt_hash=planned.identity.prompt_hash,
                decoder=BatchDecoder.LISTWISE,
            )
        )
    if len(items) != 1_152 or len({item.custom_id for item in items}) != len(items):
        raise AssertionError("WP15 primary Batch plan must contain 1,152 unique calls")
    return tuple(items)


def plan_semantic_work(
    catalog: ApprovedProbeCatalog,
    builder: ResponsesRequestBuilder,
    prompts: ProtocolPromptBuilder,
    *,
    probe_id: str,
    actual: Action,
    rule,
) -> BatchWorkItem:
    probe = next(probe for probe in catalog.manifest.probes if probe.probe_id == probe_id)
    planned = plan_semantic(
        catalog,
        builder,
        prompts,
        probe_id=probe_id,
        policy_stream=probe.variants[0].policy_stream,
        actual=actual,
        rule=rule,
    )
    return BatchWorkItem(
        custom_id=f"s0.s.{probe_id}.v1.a1",
        identity=planned.identity,
        body=planned.request.body,
        prompt_hash=planned.identity.prompt_hash,
        decoder=BatchDecoder.SEMANTIC,
    )


def plan_correction(item: BatchWorkItem, validation_error: str) -> BatchWorkItem:
    if item.attempt_index != 1:
        raise ValueError("WP15 permits exactly one local validation correction")
    source_stage = item.custom_id.split(".", 1)[0]
    target_stage = {"p0": "p1", "s0": "s1"}.get(source_stage)
    if target_stage is None:
        raise ValueError(f"cannot correct Batch stage {source_stage!r}")
    body = (
        action_retry_body(item.body, validation_error)
        if item.decoder is BatchDecoder.ACTION
        else protocol_retry_body(item.body, validation_error)
    )
    suffix = item.custom_id.split(".", 1)[1]
    if not suffix.endswith(".a1"):
        raise ValueError("initial Batch custom_id must end in .a1")
    return BatchWorkItem(
        custom_id=f"{target_stage}.{suffix.removesuffix('.a1')}.a2",
        identity=item.identity,
        body=body,
        prompt_hash=item.prompt_hash,
        decoder=item.decoder,
        attempt_index=2,
    )


def shard_work(
    stage: str,
    items: tuple[BatchWorkItem, ...],
    *,
    max_enqueued_tokens: int,
    max_requests: int = _MAX_BATCH_REQUESTS,
    max_bytes: int = _MAX_BATCH_BYTES,
) -> tuple[BatchShard, ...]:
    """Pack stable consecutive shards under every documented/operator boundary."""
    for name, value in (
        ("max_enqueued_tokens", max_enqueued_tokens),
        ("max_requests", max_requests),
        ("max_bytes", max_bytes),
    ):
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(f"{name} must be a positive integer")
    if not items:
        return ()
    if any(item.custom_id.split(".", 1)[0] != stage for item in items):
        raise ValueError("every item custom_id must match its Batch stage")

    groups: list[list[BatchWorkItem]] = []
    current: list[BatchWorkItem] = []
    current_bytes = current_tokens = 0
    for item in items:
        line = item.request_line
        tokens = estimate_tokens(item.request_bytes)
        if len(line) > max_bytes or tokens > max_enqueued_tokens:
            raise ValueError(f"Batch item {item.custom_id} exceeds a shard boundary")
        would_overflow = current and (
            len(current) + 1 > max_requests
            or current_bytes + len(line) > max_bytes
            or current_tokens + tokens > max_enqueued_tokens
        )
        if would_overflow:
            groups.append(current)
            current = []
            current_bytes = current_tokens = 0
        current.append(item)
        current_bytes += len(line)
        current_tokens += tokens
    groups.append(current)

    shards: list[BatchShard] = []
    for index, group in enumerate(groups):
        input_jsonl = b"".join(item.request_line for item in group)
        tokens = sum(estimate_tokens(item.request_bytes) for item in group)
        shards.append(
            BatchShard(
                stage=stage,
                shard_index=index,
                items=tuple(group),
                input_jsonl=input_jsonl,
                estimated_input_tokens=tokens,
                input_sha256=digest(input_jsonl),
            )
        )
    return tuple(shards)


def parse_batch_artifacts(
    expected_items: tuple[BatchWorkItem, ...],
    *,
    output_jsonl: bytes,
    error_jsonl: bytes,
) -> dict[str, BatchArtifactItem]:
    """Map unordered provider artifacts by custom_id and fail closed on any mismatch."""
    expected = {item.custom_id for item in expected_items}
    if len(expected) != len(expected_items):
        raise BatchArtifactError("expected Batch custom_id values are not unique")
    found: dict[str, BatchArtifactItem] = {}
    for source, artifact in (("output", output_jsonl), ("error", error_jsonl)):
        for raw_line in artifact.splitlines(keepends=True):
            if not raw_line.strip():
                continue
            try:
                parsed = json.loads(raw_line)
            except (json.JSONDecodeError, UnicodeDecodeError) as error:
                raise BatchArtifactError(f"invalid {source} JSONL line") from error
            if not isinstance(parsed, dict) or not isinstance(parsed.get("custom_id"), str):
                raise BatchArtifactError(f"{source} line lacks a string custom_id")
            custom_id = parsed["custom_id"]
            if custom_id not in expected:
                raise BatchArtifactError(f"unknown Batch custom_id: {custom_id}")
            if custom_id in found:
                raise BatchArtifactError(f"duplicate Batch custom_id: {custom_id}")
            response = parsed.get("response")
            response = response if isinstance(response, dict) else {}
            status_code = response.get("status_code")
            body = response.get("body")
            found[custom_id] = BatchArtifactItem(
                custom_id=custom_id,
                status_code=status_code if isinstance(status_code, int) else None,
                request_id=(
                    str(response["request_id"])
                    if response.get("request_id") is not None
                    else None
                ),
                body=body if isinstance(body, dict) else None,
                error=parsed.get("error"),
                output_line=raw_line if source == "output" else b"",
                error_line=raw_line if source == "error" else b"",
            )
    missing = expected - found.keys()
    if missing:
        raise BatchArtifactError(
            "Batch artifacts omit expected custom_id values: " + ", ".join(sorted(missing))
        )
    return found


def decode_batch_completion(
    item: BatchWorkItem,
    artifact: BatchArtifactItem,
    *,
    batch_id: str,
    stage: str,
    shard_index: int,
    prior_traces: tuple[PolicyCallTrace, ...] = (),
) -> DecodedBatchCompletion:
    """Decode one artifact with the exact same production validators as synchronous calls."""
    payload = artifact.body or {}
    if artifact.status_code != 200 or artifact.body is None or artifact.error is not None:
        outcome = "http_error" if artifact.status_code is not None else "batch_error"
        validation_error = None
        value: object = {"provider_indeterminate": True}
    elif item.decoder is BatchDecoder.ACTION:
        decoded = decode_action_response(payload)
        outcome = decoded.outcome
        validation_error = decoded.validation_error
        value = decoded.attempt
    else:
        validator = {
            BatchDecoder.PAIRWISE: PairwiseChoice.model_validate,
            BatchDecoder.LISTWISE: ListwiseRanking.model_validate,
            BatchDecoder.SEMANTIC: SemanticTextVerdict.model_validate,
        }[item.decoder]
        decoded_protocol = decode_protocol_response(payload, validator)
        outcome = decoded_protocol.outcome
        validation_error = decoded_protocol.validation_error
        value = decoded_protocol.value
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    trace = PolicyCallTrace(
        attempt_index=item.attempt_index,
        model=item.identity.model,
        prompt_hash=item.prompt_hash,
        request=item.request_bytes,
        response=canonical_request_bytes(payload),
        latency_ms=0,
        http_status=artifact.status_code,
        outcome=outcome,
        execution_mode="batch",
        batch_custom_id=item.custom_id,
        batch_id=batch_id,
        batch_stage=stage,
        batch_shard=shard_index,
        batch_request_line=item.request_line,
        batch_output_line=artifact.output_line,
        batch_error_line=artifact.error_line,
        provider_request_id=artifact.request_id,
    )
    traces = (*prior_traces, trace)
    return DecodedBatchCompletion(
        completion=HarnessCompletion(
            value=value,
            outcome=outcome,
            traces=traces,
            usage=usage_from_traces(traces),
        ),
        validation_error=validation_error,
    )


def validation_error_from_completion(
    item: BatchWorkItem,
    completion: HarnessCompletion,
) -> str | None:
    """Rebuild retry eligibility from retained raw response bytes after a restart."""
    if completion.outcome not in {"incomplete", "invalid"} or not completion.traces:
        return None
    try:
        payload = json.loads(completion.traces[-1].response)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise BatchArtifactError("retained Batch response is not valid JSON") from error
    if not isinstance(payload, dict):
        raise BatchArtifactError("retained Batch response root is not an object")
    if item.decoder is BatchDecoder.ACTION:
        return decode_action_response(payload).validation_error
    validator = {
        BatchDecoder.PAIRWISE: PairwiseChoice.model_validate,
        BatchDecoder.LISTWISE: ListwiseRanking.model_validate,
        BatchDecoder.SEMANTIC: SemanticTextVerdict.model_validate,
    }[item.decoder]
    return decode_protocol_response(payload, validator).validation_error
