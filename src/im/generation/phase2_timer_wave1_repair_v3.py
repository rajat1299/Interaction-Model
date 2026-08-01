"""Three-request v3 follow-up for the timer Wave-1 repair failure slice."""
# ruff: noqa: E501

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from tempfile import TemporaryDirectory

from im.assets import AssetRegistry
from im.assets.model import canonical_artifact_bytes
from im.generation.phase2_timer_wave0 import load_timer_wave0_inputs
from im.generation.phase2_timer_wave1_repair import (
    _HISTORICAL_PREFIXES,
    _V1_PROMPT_HASH,
    _checksums,
    _cost,
    _Executed,
    _raw_stream,
    _review_metadata,
    _Stream,
)
from im.generation.phase2_timer_wave1_repair import (
    _streams as _v2_streams,
)
from im.generation.publication import publish_directory_transaction
from im.generation.scenarios import execute_scenario, validate_generated_scenario
from im.policy.prompted import (
    PromptArtifacts,
    PromptedPolicyConfig,
    PromptRenderer,
    ResponsesRequestBuilder,
)
from im.probes.harness.batch import BatchDecoder, BatchShard, BatchWorkItem, shard_work
from im.probes.harness.identity import cache_identity, digest
from im.probes.harness.models import HarnessProtocol

_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_TIMER_WAVE1_REPAIR_V3_OUTPUT = _ROOT / "review" / "phase2" / "timer-wave-1-repair-v3"
_STAGE = "t2w1r3"
_MAX_ENQUEUED_TOKENS = 700_000
_MAX_OUTPUT_TOKENS = 8_192
_EXPECTED_DECISIONS = 3
_PROMPT_TEMPLATE = "prompt-template-v3.txt"
_POST_SCHEDULE_CONTROL = "timer-status-active"


class TimerWave1RepairV3Error(ValueError):
    """The v3 follow-up no longer isolates its two failed tails and one control."""


@dataclass(frozen=True, slots=True)
class TimerWave1RepairV3Plan:
    files: dict[str, bytes]
    items: tuple[BatchWorkItem, ...]
    shards: tuple[BatchShard, ...]


async def build_timer_wave1_repair_v3_plan(
    *, repository_root: Path = _ROOT
) -> TimerWave1RepairV3Plan:
    """Build the owner-authorized, provider-detached v3 falsification probe."""
    registry = load_timer_wave0_inputs(
        approved_root=repository_root / "review" / "phase1" / "approved",
        selection_contract_path=repository_root / "spec" / "phase2-selection-v1.json",
    )
    streams = _streams(registry)
    _validate_streams(streams)
    with TemporaryDirectory(prefix="phase2-timer-wave1-repair-v3-") as temporary:
        executed = await _execute(streams, Path(temporary), repository_root)
        return _packet(executed, repository_root)


async def materialize_timer_wave1_repair_v3_packet(
    output: Path = DEFAULT_TIMER_WAVE1_REPAIR_V3_OUTPUT,
    *,
    repository_root: Path = _ROOT,
) -> TimerWave1RepairV3Plan:
    """Publish only the distinct v3 packet; the v2 packet remains immutable."""
    plan = await build_timer_wave1_repair_v3_plan(repository_root=repository_root)
    publish_directory_transaction(output, plan.files)
    return plan


def _streams(registry: AssetRegistry) -> tuple[_Stream, ...]:
    v2 = {item.logical_stream_id: item for item in _v2_streams(registry)}
    requested = (
        ("post-confirmation-replacement", "retained_responded_snapshot", (3,)),
        ("already-handled-nudge", "handled_timer_fire", (3,)),
        (_POST_SCHEDULE_CONTROL, "post_schedule_no_trigger_regression", (1,)),
    )
    return tuple(
        _Stream(
            logical_stream_id=logical_stream_id,
            source_unit_id=f"repair-v3-{logical_stream_id}",
            branch=branch,
            program=replace(v2[logical_stream_id].program, prompt_template=_PROMPT_TEMPLATE),
            selected_action_indices=selected_action_indices,
        )
        for logical_stream_id, branch, selected_action_indices in requested
    )


async def _execute(
    streams: tuple[_Stream, ...], directory: Path, repository_root: Path
) -> tuple[_Executed, ...]:
    executed = []
    for stream in streams:
        generated = await execute_scenario(
            stream.program,
            session_id=f"phase2-timer-wave1-repair-v3-{stream.logical_stream_id}",
            directory=directory / stream.logical_stream_id,
            repository_root=repository_root,
        )
        validate_generated_scenario(generated)
        executed.append(_Executed(stream, generated))
    return tuple(executed)


def _packet(executed: tuple[_Executed, ...], repository_root: Path) -> TimerWave1RepairV3Plan:
    config = PromptedPolicyConfig(
        model="gpt-5.6-terra",
        reasoning_effort="high",
        max_output_tokens=_MAX_OUTPUT_TOKENS,
        max_attempts=1,
    )
    artifacts = PromptArtifacts(
        behavior_spec=(repository_root / "spec" / "behavior-spec.md").read_bytes(),
        action_schema=(repository_root / "spec" / "schema" / "action-v1.json").read_bytes(),
        prompt_template=(repository_root / "spec" / _PROMPT_TEMPLATE).read_bytes(),
    )
    builder = ResponsesRequestBuilder(PromptRenderer(artifacts), config)
    runtime_hashes = {
        dict(item.generated.stream.provenance.artifact_hashes)["prompt"] for item in executed
    }
    if runtime_hashes != {builder.renderer.artifacts.prompt_hash}:
        raise TimerWave1RepairV3Error("runtime session-start and teacher prompt hashes diverged")
    binding = digest(
        canonical_artifact_bytes(
            {
                "kind": "phase2-timer-wave1-repair-v3-binding-v1",
                "prompt_hash": builder.renderer.artifacts.prompt_hash,
                "streams": [
                    (item.stream.logical_stream_id, item.generated.stream.sha256)
                    for item in executed
                ],
            }
        )
    )
    items, targets = [], []
    for stream in executed:
        for index, (boundary, action) in enumerate(
            zip(
                stream.generated.decision_boundaries,
                stream.generated.program.actions,
                strict=True,
            )
        ):
            if index not in stream.stream.selected_action_indices:
                continue
            custom_id = f"{_STAGE}.{stream.stream.logical_stream_id}.d{index:03}.a1"
            body = builder.build(boundary.policy_bytes)
            body_bytes = canonical_artifact_bytes(body)
            items.append(
                BatchWorkItem(
                    custom_id=custom_id,
                    identity=cache_identity(
                        manifest_sha256=binding,
                        probe_id=custom_id,
                        protocol=HarnessProtocol.GENERATION,
                        variant_id="timer-wave-1-repair-v3",
                        presentation=digest(boundary.policy_bytes),
                        model=config.model,
                        reasoning_effort=config.reasoning_effort,
                        prompt_hash=builder.renderer.artifacts.prompt_hash,
                        request_bytes=body_bytes,
                    ),
                    body=body,
                    prompt_hash=builder.renderer.artifacts.prompt_hash,
                    decoder=BatchDecoder.ACTION,
                )
            )
            targets.append(
                {
                    "branch": stream.stream.branch,
                    "custom_id": custom_id,
                    "family": stream.stream.program.family.value,
                    "historical_policy_prefix_sha256": _post_schedule_control_identity(
                        stream.stream.logical_stream_id,
                        boundary.policy_bytes,
                        builder.renderer.artifacts.prompt_hash,
                    ),
                    "logical_stream_id": stream.stream.logical_stream_id,
                    "oracle_action": action.model_dump(mode="json"),
                    "program_action_index": index,
                    "prompt_hash": builder.renderer.artifacts.prompt_hash,
                    "request_body_sha256": digest(body_bytes),
                    "source_unit_id": stream.stream.source_unit_id,
                    "stream_sha256": stream.generated.stream.sha256,
                    **_review_metadata(stream, action),
                }
            )
    item_tuple = tuple(items)
    if len(item_tuple) != _EXPECTED_DECISIONS:
        raise TimerWave1RepairV3Error("v3 follow-up decision inventory drifted")
    shards = shard_work(_STAGE, item_tuple, max_enqueued_tokens=_MAX_ENQUEUED_TOKENS)
    if len(shards) != 1:
        raise TimerWave1RepairV3Error("v3 follow-up must remain one Batch shard")
    manifest = {
        "api_call_performed": False,
        "authorization_basis": "timer-wave-1-repair-v2 owner authorization reused",
        "authorization_state": "owner_authorized_not_submitted",
        "binding_sha256": binding,
        "cost_estimate": _cost(item_tuple, config),
        "decision_count": len(item_tuple),
        "endpoint": "/v1/responses",
        "format_version": 1,
        "kind": "phase2-timer-wave1-repair-v3-teacher-plan",
        "max_enqueued_tokens": _MAX_ENQUEUED_TOKENS,
        "max_output_tokens_per_request": config.max_output_tokens,
        "model": config.model,
        "prompt_hash": builder.renderer.artifacts.prompt_hash,
        "reasoning_effort": config.reasoning_effort,
        "request_count": len(item_tuple),
        "runtime_prompt_hashes": sorted(runtime_hashes),
        "shard_count": 1,
        "shards": [
            {
                "estimated_input_tokens": shards[0].estimated_input_tokens,
                "input_path": "teacher-input/shard-000.jsonl",
                "input_sha256": shards[0].input_sha256,
                "request_count": len(shards[0].items),
                "shard_index": 0,
                "stage": _STAGE,
            }
        ],
        "source_unit_count": len({item.stream.source_unit_id for item in executed}),
        "stage": _STAGE,
        "targets": targets,
        "wave_id": "timer-wave-1-repair-v3",
    }
    files = {
        "README.md": _readme(manifest).encode(),
        "raw-streams.json": canonical_artifact_bytes(
            {"format_version": 1, "streams": [_raw_stream(item) for item in executed]}
        ),
        "teacher-input/shard-000.jsonl": shards[0].input_jsonl,
        "teacher-plan.json": canonical_artifact_bytes(manifest),
    }
    return TimerWave1RepairV3Plan({**files, "SHA256SUMS": _checksums(files)}, item_tuple, shards)


def _post_schedule_control_identity(
    logical_stream_id: str, policy_bytes: bytes, prompt_hash: str
) -> str | None:
    if logical_stream_id != _POST_SCHEDULE_CONTROL:
        return None
    expected = _HISTORICAL_PREFIXES[_POST_SCHEDULE_CONTROL]
    current = prompt_hash.encode("ascii")
    if policy_bytes.count(current) != 1:
        raise TimerWave1RepairV3Error(
            "regression prefix does not contain exactly one v3 prompt hash"
        )
    normalized = policy_bytes.replace(current, _V1_PROMPT_HASH.encode("ascii"), 1)
    if digest(normalized) != expected:
        raise TimerWave1RepairV3Error(
            "post-schedule control no longer reproduces its frozen Wave-1 prefix"
        )
    return expected


def _validate_streams(streams: tuple[_Stream, ...]) -> None:
    if len(streams) != 3 or len({item.logical_stream_id for item in streams}) != 3:
        raise TimerWave1RepairV3Error("v3 stream inventory drifted")
    if sum(len(item.selected_action_indices) for item in streams) != _EXPECTED_DECISIONS:
        raise TimerWave1RepairV3Error("v3 submitted decision inventory drifted")
    if any(
        item.selected_action_indices != tuple(sorted(set(item.selected_action_indices)))
        or item.selected_action_indices[-1] >= len(item.program.actions)
        for item in streams
    ):
        raise TimerWave1RepairV3Error("v3 selected action indexes drifted")


def _readme(manifest: dict[str, object]) -> str:
    cost = manifest["cost_estimate"]
    assert isinstance(cost, dict)
    return "\n".join(
        (
            "# Phase 2 timer Wave-1 v3 follow-up",
            "",
            "Hypothesis: a retained responded snapshot and a handled timer fire remain visibly consumed, so already_handled precedes no_trigger.",
            "",
            "The packet contains only those two v2 failures plus the original post-schedule no_trigger regression prefix.",
            f"Requests: {manifest['request_count']} in one shard.",
            f"Expected Batch cost: ${cost['expected_usd']}; approval ceiling: ${cost['approval_ceiling_usd']}.",
            "",
        )
    )
