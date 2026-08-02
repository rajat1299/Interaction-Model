"""Scoped detached canary for the repaired WP2-2 timer Wave-2 sources."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

from im.assets.model import canonical_artifact_bytes
from im.generation.phase2_timer_wave0 import load_timer_wave0_inputs
from im.generation.phase2_timer_wave1_repair import _checksums, _cost
from im.generation.phase2_timer_wave2_packet import (
    _PROMPT_TEMPLATE,
    _PROMPT_V3_SHA256,
    _execute,
    _execute_rollovers,
    _ExecutedCandidate,
    _program_specs,
    _raw_parent,
)
from im.generation.publication import publish_directory_transaction
from im.policy.prompted import (
    PromptArtifacts,
    PromptedPolicyConfig,
    PromptRenderer,
    ResponsesRequestBuilder,
)
from im.probes.harness.batch import BatchDecoder, BatchShard, BatchWorkItem, shard_work
from im.probes.harness.identity import cache_identity, digest
from im.probes.harness.models import HarnessProtocol
from im.schema.actions import IdleAction, IdleReason, ScheduleAction

_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_TIMER_WAVE2_REPAIR_OUTPUT = _ROOT / "review" / "phase2" / "timer-wave-2-repair"
_STAGE = "t2w2r1"
_MAX_ENQUEUED_TOKENS = 700_000
_MAX_OUTPUT_TOKENS = 8_192
_EXPECTED_DECISIONS = 15


class TimerWave2RepairError(ValueError):
    """The scoped repair canary no longer covers its seven shared repair surfaces."""


@dataclass(frozen=True, slots=True)
class TimerWave2RepairPlan:
    files: dict[str, bytes]
    items: tuple[BatchWorkItem, ...]
    shards: tuple[BatchShard, ...]


@dataclass(frozen=True, slots=True)
class _Probe:
    executed: _ExecutedCandidate
    action_indices: tuple[int, ...]
    repair_class: str


async def build_timer_wave2_repair_plan(*, repository_root: Path = _ROOT) -> TimerWave2RepairPlan:
    """Build the provider-detached 15-decision falsification probe."""
    registry = load_timer_wave0_inputs(
        approved_root=repository_root / "review" / "phase1" / "approved",
        selection_contract_path=repository_root / "spec" / "phase2-selection-v1.json",
    )
    requested = {
        "normal_compact-00",
        "normal_wide-00",
        "cancel-checkpoint-00",
        "contention-control-00",
        "contention-checkpoint-00",
    }
    specs = tuple(
        spec
        for spec in _program_specs(registry, repaired=True)
        if spec.logical_stream_id in requested
    )
    if {spec.logical_stream_id for spec in specs} != requested:
        raise TimerWave2RepairError("repair source inventory drifted")
    with TemporaryDirectory(prefix="phase2-timer-wave2-repair-") as temporary:
        directory = Path(temporary)
        executed = await _execute(specs, directory, repository_root)
        rollovers = await _execute_rollovers(registry, directory, repository_root, repaired=True)
        first_rollovers = (
            next(item for item in rollovers if item.spec.kind == "rollover_a"),
            next(item for item in rollovers if item.spec.kind == "rollover_b"),
        )
        probes = _probes((*executed, *first_rollovers))
        return _packet(probes, repository_root)


async def materialize_timer_wave2_repair_packet(
    output: Path = DEFAULT_TIMER_WAVE2_REPAIR_OUTPUT,
    *,
    repository_root: Path = _ROOT,
) -> TimerWave2RepairPlan:
    """Create-only publish of the scoped repair packet."""
    plan = await build_timer_wave2_repair_plan(repository_root=repository_root)
    publish_directory_transaction(output, plan.files)
    return plan


def _probes(executed: tuple[_ExecutedCandidate, ...]) -> tuple[_Probe, ...]:
    by_kind = {item.spec.kind: item for item in executed}
    if len(by_kind) != 7:
        raise TimerWave2RepairError("repair canary must contain one parent per repaired kind")

    compact = by_kind["normal_compact"]
    wide = by_kind["normal_wide"]
    cancel = by_kind["cancel_checkpoint"]
    control = by_kind["contention_control"]
    checkpoint = by_kind["contention_checkpoint"]
    rollover_a = by_kind["rollover_a"]
    rollover_b = by_kind["rollover_b"]

    return (
        _Probe(compact, _creation_and_handled_indices(compact), "explicit_additional_and_handled"),
        _Probe(wide, _creation_and_handled_indices(wide)[:1], "explicit_additional_wide"),
        _Probe(cancel, (_first_instruction_not_direct(cancel),), "reported_control_boundary"),
        _Probe(
            control, _second_schedule_and_final_idle(control)[:1], "contention_control_timeline"
        ),
        _Probe(
            checkpoint,
            tuple(checkpoint.action_indices[index] for index in (0, 1, 5, 7)),
            "contention_checkpoint",
        ),
        _Probe(rollover_a, rollover_a.action_indices[-5:], "stale_before_integrate_rollover_a"),
        _Probe(rollover_b, (rollover_b.action_indices[-4],), "stale_before_integrate_rollover_b"),
    )


def _creation_and_handled_indices(item: _ExecutedCandidate) -> tuple[int, int]:
    schedules = tuple(
        index
        for index, action in enumerate(item.parent.program.actions)
        if isinstance(action, ScheduleAction)
    )
    handled = tuple(
        index
        for index, action in enumerate(item.parent.program.actions)
        if isinstance(action, IdleAction) and action.reason is IdleReason.ALREADY_HANDLED
    )
    if len(schedules) < 2 or not handled:
        raise TimerWave2RepairError(f"{item.spec.logical_stream_id} lost its repair decisions")
    return schedules[1], handled[0]


def _first_instruction_not_direct(item: _ExecutedCandidate) -> int:
    for index, action in zip(item.action_indices, item.actions, strict=True):
        if isinstance(action, IdleAction) and action.reason is IdleReason.INSTRUCTION_NOT_DIRECT:
            return index
    raise TimerWave2RepairError("cancel checkpoint lost its reported-control decision")


def _second_schedule_and_final_idle(item: _ExecutedCandidate) -> tuple[int, int]:
    schedules = tuple(
        index
        for index, action in enumerate(item.parent.program.actions)
        if isinstance(action, ScheduleAction)
    )
    final_index = len(item.parent.program.actions) - 1
    if len(schedules) != 2 or not isinstance(item.parent.program.actions[final_index], IdleAction):
        raise TimerWave2RepairError("contention control repair shape drifted")
    return schedules[1], final_index


def _packet(probes: tuple[_Probe, ...], repository_root: Path) -> TimerWave2RepairPlan:
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
    if builder.renderer.artifacts.prompt_hash != _PROMPT_V3_SHA256:
        raise TimerWave2RepairError("repair canary prompt hash drifted")
    binding = digest(
        canonical_artifact_bytes(
            {
                "kind": "phase2-timer-wave2-repair-binding-v1",
                "prompt_hash": builder.renderer.artifacts.prompt_hash,
                "probes": [
                    (
                        probe.executed.spec.logical_stream_id,
                        probe.executed.parent.stream.sha256,
                        list(probe.action_indices),
                    )
                    for probe in probes
                ],
            }
        )
    )
    items = []
    targets = []
    raw_streams = []
    for probe in probes:
        executed = probe.executed
        selected = []
        for action_index in probe.action_indices:
            action = executed.parent.program.actions[action_index]
            boundary = executed.parent.decision_boundaries[action_index]
            custom_id = f"{_STAGE}.{executed.spec.logical_stream_id}.d{action_index:03}.a1"
            body = builder.build(boundary.policy_bytes)
            body_bytes = canonical_artifact_bytes(body)
            items.append(
                BatchWorkItem(
                    custom_id=custom_id,
                    identity=cache_identity(
                        manifest_sha256=binding,
                        probe_id=custom_id,
                        protocol=HarnessProtocol.GENERATION,
                        variant_id="timer-wave-2-repair-v1",
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
            target = {
                "custom_id": custom_id,
                "family": executed.parent.program.family.value,
                "logical_stream_id": executed.spec.logical_stream_id,
                "oracle_action": action.model_dump(mode="json"),
                "policy_prefix_sha256": digest(boundary.policy_bytes),
                "program_action_index": action_index,
                "prompt_hash": builder.renderer.artifacts.prompt_hash,
                "repair_class": probe.repair_class,
                "request_body_sha256": digest(body_bytes),
                "source_unit_id": executed.spec.source_unit_id,
                "stream_sha256": executed.parent.stream.sha256,
            }
            targets.append(target)
            selected.append(target)
        raw_streams.append(
            {
                "logical_stream_id": executed.spec.logical_stream_id,
                "parent": _raw_parent(executed),
                "repair_class": probe.repair_class,
                "selected_actions": selected,
            }
        )
    item_tuple = tuple(items)
    if len(item_tuple) != _EXPECTED_DECISIONS:
        raise TimerWave2RepairError("repair canary decision inventory drifted")
    shards = shard_work(_STAGE, item_tuple, max_enqueued_tokens=_MAX_ENQUEUED_TOKENS)
    if len(shards) != 1:
        raise TimerWave2RepairError("repair canary must remain one detached Batch shard")
    manifest = {
        "api_call_performed": False,
        "authorization_basis": (
            "owner instructed Wave-2 repair after approving the 52 oracle / 28 template / "
            "17 teacher-error partition and previously authorized required follow-up Batch calls"
        ),
        "authorization_state": "owner_authorized_not_submitted",
        "binding_sha256": binding,
        "cost_estimate": _cost(item_tuple, config),
        "decision_count": len(item_tuple),
        "endpoint": "/v1/responses",
        "format_version": 1,
        "kind": "phase2-timer-wave2-repair-teacher-plan",
        "max_enqueued_tokens": _MAX_ENQUEUED_TOKENS,
        "max_output_tokens_per_request": config.max_output_tokens,
        "model": config.model,
        "prompt_hash": builder.renderer.artifacts.prompt_hash,
        "reasoning_effort": config.reasoning_effort,
        "request_count": len(item_tuple),
        "runtime_prompt_hashes": [builder.renderer.artifacts.prompt_hash],
        "shard_count": 1,
        "shards": [
            {
                "estimated_input_tokens": shards[0].estimated_input_tokens,
                "input_sha256": shards[0].input_sha256,
                "request_count": len(shards[0].items),
                "shard_index": 0,
                "stage": _STAGE,
            }
        ],
        "source_unit_count": len(probes),
        "stage": _STAGE,
        "targets": targets,
        "wave_id": "timer-wave-2-repair-v1",
    }
    raw = {
        "format_version": 1,
        "kind": "phase2-timer-wave2-repair-parents",
        "streams": raw_streams,
    }
    files = {
        "README.md": _readme(manifest).encode("utf-8"),
        "raw-streams.json": canonical_artifact_bytes(raw),
        "teacher-plan.json": canonical_artifact_bytes(manifest),
        "teacher-input/shard-000.jsonl": shards[0].input_jsonl,
    }
    return TimerWave2RepairPlan({**files, "SHA256SUMS": _checksums(files)}, item_tuple, shards)


def _readme(manifest: dict[str, object]) -> str:
    return (
        "# WP2-2 timer Wave-2 scoped repair canary\n\n"
        "This packet contains only representative decisions from the seven repaired shared "
        "scenario surfaces. It does not replay the original 698-decision Wave-2 packet.\n\n"
        f"- Requests: `{manifest['request_count']}`\n"
        f"- Model: `{manifest['model']}` / `{manifest['reasoning_effort']}`\n"
        f"- Binding: `{manifest['binding_sha256']}`\n"
        "- Provider submission is detached and recorded only in the execution directory.\n"
    )
