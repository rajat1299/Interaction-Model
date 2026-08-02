"""Small v2-prompt repair canary for the Phase 2 timer Wave-1 failure slice."""
# ruff: noqa: E501

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

from im.assets import AssetRegistry, CorpusFamily, Split
from im.assets.model import (
    LookupAssetPayload,
    TimerAssetPayload,
    artifact_digest,
    canonical_artifact_bytes,
)
from im.config import estimate_tokens
from im.generation.g7_response_assets import HumanAuthoredResponseAsset, ResponseDraftSpec
from im.generation.ingestion import ScheduledSamplerFrame
from im.generation.oracle import ResponseWarrantKind
from im.generation.phase2_timer_wave0 import load_timer_wave0_inputs
from im.generation.phase2_timer_wave1 import _streams as _historical_wave1_streams
from im.generation.publication import publish_directory_transaction
from im.generation.response_contracts import AnswerContract, RequiredAnswerPoint, ResponseKind
from im.generation.scenario_catalog import build_family_program
from im.generation.scenarios import (
    BeatOpening,
    BeatResponseWarrant,
    BeatStaleResults,
    GeneratedScenario,
    ScenarioProgram,
    execute_scenario,
    select_approved_scenario_inputs,
    validate_generated_scenario,
)
from im.generation.timing import TimingSeed, materialize_timing_plan
from im.policy.prompted import (
    ModelPricing,
    PromptArtifacts,
    PromptedPolicyConfig,
    PromptRenderer,
    ResponsesRequestBuilder,
)
from im.probes.harness.batch import BatchDecoder, BatchShard, BatchWorkItem, shard_work
from im.probes.harness.identity import cache_identity, digest
from im.probes.harness.models import HarnessProtocol
from im.schema.actions import (
    DelegateAction,
    IdleAction,
    IdleReason,
    IntegrateAction,
    RespondAction,
    ScheduleAction,
    Span,
)
from im.schema.common import ToolName
from im.schema.events import SessionStartEvent
from im.schema.textspan import utf16_len
from im.serialize import parse_event
from im.tools import ScriptedToolResult

_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_TIMER_WAVE1_REPAIR_OUTPUT = _ROOT / "review" / "phase2" / "timer-wave-1-repair"
_STAGE = "t2w1r"
_MAX_ENQUEUED_TOKENS = 700_000
_MAX_OUTPUT_TOKENS = 8_192
_EXPECTED_DECISIONS = 10
_PROMPT_TEMPLATE = "prompt-template-v2.txt"
_REPLACEMENT_RESPONSE = (
    "I can’t change an existing reminder. Please cancel it and create a new one."
)
_V1_PROMPT_HASH = "sha256:f130c1927f72a073d9a6c9397a65acb9c915d8919c9536aec9cda8d7fd771fa9"
_HISTORICAL_PREFIXES = {
    "timer-status-active": "sha256:25a134113348cbf4a94d93b90b7932f4552ee8d557f134279f607ddd29a6cd57",
    "ambiguous-cancel-active": "sha256:a658e6ec7631f30749bee8481c6978e1e38c237af849283874d045c346c100c3",
    "schedule-similar-duplicate-a": "sha256:4932ed4a5ba697b34b823f551475252517df0038337dfeb689f8db3dfea08e9e",
    "contention-floor-typing": "sha256:d66cb21d2073ba3b50de6d02df19a81df63ef5cc466673e528dfbba9af9835fb",
}


class TimerWave1RepairError(ValueError):
    """The narrowly scoped repair canary no longer proves its stated hypothesis."""


@dataclass(frozen=True, slots=True)
class _Stream:
    logical_stream_id: str
    source_unit_id: str
    branch: str
    program: ScenarioProgram
    selected_action_indices: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class _Executed:
    stream: _Stream
    generated: GeneratedScenario


@dataclass(frozen=True, slots=True)
class TimerWave1RepairPlan:
    files: dict[str, bytes]
    items: tuple[BatchWorkItem, ...]
    shards: tuple[BatchShard, ...]


async def build_timer_wave1_repair_plan(*, repository_root: Path = _ROOT) -> TimerWave1RepairPlan:
    """Build the one-shard offline falsification canary; never call a provider."""
    registry = load_timer_wave0_inputs(
        approved_root=repository_root / "review" / "phase1" / "approved",
        selection_contract_path=repository_root / "spec" / "phase2-selection-v1.json",
    )
    streams = _streams(registry)
    _validate_streams(streams)
    with TemporaryDirectory(prefix="phase2-timer-wave1-repair-") as temporary:
        executed = await _execute(streams, Path(temporary), repository_root)
        return _packet(executed, repository_root)


async def materialize_timer_wave1_repair_packet(
    output: Path = DEFAULT_TIMER_WAVE1_REPAIR_OUTPUT,
    *,
    repository_root: Path = _ROOT,
) -> TimerWave1RepairPlan:
    """Create-only publication for the new v2 evidence; historical Wave-1 is untouched."""
    plan = await build_timer_wave1_repair_plan(repository_root=repository_root)
    publish_directory_transaction(output, plan.files)
    return plan


def build_timer_wave1_repair_response_record() -> dict[str, object]:
    """Register the owner's exact candidate-5 limitation through the existing schema."""
    support = {
        "e_000002": "Remind me every thirty-seven minutes to open the fern ledger.",
        "e_000005": "Remind me every thirty-seven minutes to open the fern ledger for the desk note.",
    }
    contract = AnswerContract(
        response_kind=ResponseKind.UNSUPPORTED_FEATURE_LIMITATION,
        subject_id="timer-post-confirmation-replacement",
        support_event_ids=tuple(support),
        required_answer_points=(
            RequiredAnswerPoint(("can’t change an existing reminder",)),
            RequiredAnswerPoint(("cancel it and create a new one",)),
        ),
        forbidden_claims=("I changed the reminder.", "I created a new reminder."),
    )
    asset = HumanAuthoredResponseAsset.create(
        ResponseDraftSpec(invitation=support["e_000005"], answer_contract=contract),
        teacher_visible_prefix="\n".join(support.values()),
        response_text=_REPLACEMENT_RESPONSE,
        visible_support_by_event_id=support,
    )
    claims = {
        "author_origin": "human_authored",
        "candidate_ordinal": 5,
        "candidate_response": asset.response_text,
        "neutral_request": json.loads(asset.serialized_neutral_request),
        "neutral_request_sha256": asset.serialized_neutral_request_sha256,
        "scenario_binding": {"logical_stream_id": "post-confirmation-replacement"},
        "split": Split.TRAIN.value,
        "subject_id": contract.subject_id,
        "visible_support": support,
    }
    return {
        "format_version": 1,
        "kind": "wp2-2-approved-train-response",
        **claims,
        "content_sha256": artifact_digest(claims),
        "review": {
            "decision": "approved",
            "reviewed_at_utc": "2026-07-22T00:00:00Z",
            "reviewer_id": "user:phase2-owner",
        },
    }


def _streams(registry: AssetRegistry) -> tuple[_Stream, ...]:
    historical = {item.logical_stream_id: item for item in _historical_wave1_streams(registry)}
    original_failure_representatives = (
        "timer-status-active",
        "ambiguous-cancel-active",
        "schedule-similar-duplicate-a",
        "contention-floor-typing",
    )
    return (
        *(
            _Stream(
                logical_id,
                f"repair-original-{logical_id}",
                "pre_repair_no_trigger_prefix",
                replace(historical[logical_id].program, prompt_template=_PROMPT_TEMPLATE),
                (1,),
            )
            for logical_id in original_failure_representatives
        ),
        _Stream(
            "post-confirmation-additional",
            "repair-post-confirmation-additional",
            "explicit_additional_reminder",
            _additional_reminder(registry),
            (2,),
        ),
        _Stream(
            "post-confirmation-replacement",
            "repair-post-confirmation-replacement",
            "replacement_limitation",
            _replacement(registry),
            (2, 3),
        ),
        _Stream(
            "already-handled-integrate",
            "repair-already-handled-integrate",
            "already_handled_integrate",
            _integrate_control(registry),
            (3,),
        ),
        _Stream(
            "already-handled-skip",
            "repair-already-handled-skip",
            "already_handled_skip",
            _handled_tail(
                build_family_program(
                    CorpusFamily.LOOKUP_STALE,
                    registry,
                    split=Split.TRAIN,
                    template_id="a_dd5c4e7300588ffc83ce7bb2",
                    asset_ids=("a_1d2adb2b20a4058e6ade6fa8",),
                    master_seed="phase2-timer-wave1-repair:skip",
                ),
                "e_000006",
            ),
            (3,),
        ),
        _Stream(
            "already-handled-nudge",
            "repair-already-handled-nudge",
            "already_handled_nudge",
            _handled_tail(
                build_family_program(
                    CorpusFamily.TIMER_NORMAL,
                    registry,
                    split=Split.TRAIN,
                    template_id="a_77870a0d84d3da57e4b0318d",
                    asset_ids=("a_067f59d6c56633412a0d45b4",),
                    master_seed="phase2-timer-wave1-repair:nudge",
                ),
                "e_000005",
            ),
            (3,),
        ),
    )


def _additional_reminder(registry: AssetRegistry) -> ScenarioProgram:
    bundle, template = _timer_inputs(
        registry, ("a_067f59d6c56633412a0d45b4", "a_11d7f848364801c6724c9d75")
    )
    first = _timer(bundle, "a_067f59d6c56633412a0d45b4")
    second = _timer(bundle, "a_11d7f848364801c6724c9d75")
    plan = materialize_timing_plan(
        TimingSeed(Split.TRAIN, "phase2-timer-wave1-repair:additional"), 4
    )
    second_at = plan.service_ms[0] + 4_000
    additional = "Also create another reminder every thirty-one minutes to sweep the quartz step."
    return _program(
        bundle=bundle,
        template=template,
        family=CorpusFamily.TIMER_NORMAL,
        master_seed="phase2-timer-wave1-repair:additional",
        plan=plan,
        frames=(_frame(0, first.instruction), _frame(second_at, additional)),
        actions=(
            _schedule("e_000002", first),
            _idle(),
            _schedule("e_000005", second, instruction=additional),
            _idle(),
        ),
    )


def _replacement(registry: AssetRegistry) -> ScenarioProgram:
    bundle, template = _timer_inputs(registry, ("a_067f59d6c56633412a0d45b4",))
    timer = _timer(bundle, "a_067f59d6c56633412a0d45b4")
    plan = materialize_timing_plan(
        TimingSeed(Split.TRAIN, "phase2-timer-wave1-repair:replacement"), 4
    )
    second_at = plan.service_ms[0] + 4_000
    replacement = "Remind me every thirty-seven minutes to open the fern ledger for the desk note."
    return _program(
        bundle=bundle,
        template=template,
        family=CorpusFamily.TIMER_NORMAL,
        master_seed="phase2-timer-wave1-repair:replacement",
        plan=plan,
        frames=(
            _frame(0, timer.instruction),
            _frame(second_at, replacement),
            _frame(second_at + plan.service_ms[2] + 1, "No other change requested."),
        ),
        actions=(
            _schedule("e_000002", timer),
            _idle(),
            RespondAction(type="respond", reply_to_event_id="e_000005", text=_REPLACEMENT_RESPONSE),
            IdleAction(type="idle", reason=IdleReason.ALREADY_HANDLED, related_event_id="e_000005"),
        ),
        response_warrants=(
            BeatResponseWarrant("b2", "e_000005", ResponseWarrantKind.UNSUPPORTED_LIMITATION),
        ),
        openings=(BeatOpening("b2", "e_000005"),),
    )


def _integrate_control(registry: AssetRegistry) -> ScenarioProgram:
    bundle, template = select_approved_scenario_inputs(
        registry,
        split=Split.TRAIN,
        template_id="a_93beb83846363b159a8f8f67",
        asset_ids=("a_1cf8a5df42e379dcb0fc2472",),
    )
    lookup = bundle.assets[0].payload
    if not isinstance(lookup, LookupAssetPayload):
        raise TimerWave1RepairError("integrate control lost its sealed lookup asset")
    plan = materialize_timing_plan(
        TimingSeed(Split.TRAIN, "phase2-timer-wave1-repair:integrate"), 4
    )
    return _program(
        bundle=bundle,
        template=template,
        family=CorpusFamily.LOOKUP_LIVE,
        master_seed="phase2-timer-wave1-repair:integrate",
        plan=plan,
        frames=(
            _frame(0, lookup.query),
            _frame(plan.service_ms[0] + 1, lookup.query),
            _frame(plan.service_ms[0] + 700 + plan.service_ms[2] + 1, lookup.query),
        ),
        actions=(
            DelegateAction(
                type="delegate",
                fact=_span("e_000002", lookup.query),
                tool=ToolName.LOOKUP,
                args={"query": lookup.query},
            ),
            IdleAction(type="idle", reason=IdleReason.AWAITING_TOOL, related_event_id="e_000002"),
            IntegrateAction(type="integrate", result_event_id="e_000006", text=lookup.result_a),
            IdleAction(type="idle", reason=IdleReason.ALREADY_HANDLED, related_event_id="e_000006"),
        ),
        tool_results=(ScriptedToolResult(latency_ms=700, data={"nonce": lookup.result_a}),),
        openings=(BeatOpening("b2", "e_000005"),),
    )


def _handled_tail(program: ScenarioProgram, related_event_id: str) -> ScenarioProgram:
    return replace(
        program,
        actions=(
            *program.actions[:-1],
            IdleAction(
                type="idle", reason=IdleReason.ALREADY_HANDLED, related_event_id=related_event_id
            ),
        ),
        prompt_template=_PROMPT_TEMPLATE,
    )


async def _execute(
    streams: tuple[_Stream, ...], directory: Path, repository_root: Path
) -> tuple[_Executed, ...]:
    executed = []
    for stream in streams:
        generated = await execute_scenario(
            stream.program,
            session_id=f"phase2-timer-wave1-repair-{stream.logical_stream_id}",
            directory=directory / stream.logical_stream_id,
            repository_root=repository_root,
        )
        validate_generated_scenario(generated)
        executed.append(_Executed(stream, generated))
    return tuple(executed)


def _packet(executed: tuple[_Executed, ...], repository_root: Path) -> TimerWave1RepairPlan:
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
        raise TimerWave1RepairError("runtime session-start and teacher prompt hashes diverged")
    binding = digest(
        canonical_artifact_bytes(
            {
                "kind": "phase2-timer-wave1-repair-binding-v1",
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
            zip(stream.generated.decision_boundaries, stream.generated.program.actions, strict=True)
        ):
            if index not in stream.stream.selected_action_indices:
                continue
            historical_prefix = _historical_prefix_identity(
                stream.stream.logical_stream_id,
                boundary.policy_bytes,
                builder.renderer.artifacts.prompt_hash,
            )
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
                        variant_id="timer-wave-1-repair",
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
                    "historical_policy_prefix_sha256": historical_prefix,
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
        raise TimerWave1RepairError("repair canary decision inventory drifted")
    shards = shard_work(_STAGE, item_tuple, max_enqueued_tokens=_MAX_ENQUEUED_TOKENS)
    if len(shards) != 1:
        raise TimerWave1RepairError("repair canary must remain one Batch shard")
    inputs = {"teacher-input/shard-000.jsonl": shards[0].input_jsonl}
    response_record = build_timer_wave1_repair_response_record()
    manifest = {
        "api_call_performed": False,
        "authorization_state": "owner_authorized_not_submitted",
        "binding_sha256": binding,
        "cost_estimate": _cost(item_tuple, config),
        "decision_count": len(item_tuple),
        "endpoint": "/v1/responses",
        "format_version": 1,
        "kind": "phase2-timer-wave1-repair-teacher-plan",
        "max_enqueued_tokens": _MAX_ENQUEUED_TOKENS,
        "max_output_tokens_per_request": config.max_output_tokens,
        "model": config.model,
        "prompt_hash": builder.renderer.artifacts.prompt_hash,
        "reasoning_effort": config.reasoning_effort,
        "request_count": len(item_tuple),
        "response_candidate_ordinals": [5],
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
        "wave_id": "timer-wave-1-repair-v2",
    }
    raw = {"format_version": 1, "streams": [_raw_stream(item) for item in executed]}
    files = {
        "README.md": _readme(manifest).encode(),
        "raw-streams.json": canonical_artifact_bytes(raw),
        "response-assets.json": canonical_artifact_bytes(
            {
                "format_version": 1,
                "kind": "phase2-approved-train-response-records",
                "records": [response_record],
            }
        ),
        "teacher-plan.json": canonical_artifact_bytes(manifest),
        **inputs,
    }
    return TimerWave1RepairPlan({**files, "SHA256SUMS": _checksums(files)}, item_tuple, shards)


def _historical_prefix_identity(
    logical_stream_id: str, policy_bytes: bytes, prompt_hash: str
) -> str | None:
    expected = _HISTORICAL_PREFIXES.get(logical_stream_id)
    if expected is None:
        return None
    current = prompt_hash.encode("ascii")
    if policy_bytes.count(current) != 1:
        raise TimerWave1RepairError("repair prefix does not contain exactly one v2 prompt hash")
    normalized = policy_bytes.replace(current, _V1_PROMPT_HASH.encode("ascii"), 1)
    if digest(normalized) != expected:
        raise TimerWave1RepairError(
            f"{logical_stream_id} no longer reproduces its frozen Wave-1 failure prefix"
        )
    return expected


def _review_metadata(stream: _Executed, action: object) -> dict[str, object]:
    action_type = str(getattr(action, "type"))
    reasons = []
    risks: list[str] = []
    if action_type in {"schedule", "skip", "nudge"}:
        reasons.append("mandatory_action")
    if isinstance(action, IdleAction) and action.reason is IdleReason.ALREADY_HANDLED:
        reasons.append("idle_reason_100_percent")
    if (
        stream.stream.logical_stream_id == "post-confirmation-replacement"
        and action_type == "respond"
    ):
        risks.append("post_confirmation_modification_boundary")
        reasons.append("risk_flag")
    return {
        "mandatory_review": bool(reasons),
        "mandatory_review_reasons": reasons,
        "risk_flags": risks,
        "rollover": False,
    }


def _raw_stream(item: _Executed) -> dict[str, object]:
    session_start = parse_event(item.generated.stream.segments[0].policy_bytes.splitlines()[0])
    if not isinstance(session_start, SessionStartEvent):
        raise TimerWave1RepairError("repair runtime did not begin with session_start")
    return {
        "actions": [action.model_dump(mode="json") for action in item.stream.program.actions],
        "branch": item.stream.branch,
        "logical_stream_id": item.stream.logical_stream_id,
        "prompt_hash": dict(item.generated.stream.provenance.artifact_hashes)["prompt"],
        "session_start_prompt_hash": session_start.payload.prompt_hash,
        "frames": [
            {"at_ms": frame.at_ms, "sampler_json": frame.raw_bytes.decode("utf-8")}
            for frame in item.stream.program.frames
        ],
        "sidecar": item.generated.sidecar.as_json_object(),
        "source_unit_id": item.stream.source_unit_id,
        "stream_sha256": item.generated.stream.sha256,
    }


def _validate_streams(streams: tuple[_Stream, ...]) -> None:
    if len(streams) != 9 or len({item.logical_stream_id for item in streams}) != len(streams):
        raise TimerWave1RepairError("repair stream inventory drifted")
    if sum(len(item.selected_action_indices) for item in streams) != _EXPECTED_DECISIONS:
        raise TimerWave1RepairError("repair submitted decision inventory drifted")
    if any(
        not item.selected_action_indices
        or item.selected_action_indices != tuple(sorted(set(item.selected_action_indices)))
        or item.selected_action_indices[-1] >= len(item.program.actions)
        for item in streams
    ):
        raise TimerWave1RepairError("repair selected action indexes drifted")
    if len({item.source_unit_id for item in streams}) < 5:
        raise TimerWave1RepairError("repair canary needs at least five source units")


def _timer_inputs(registry: AssetRegistry, asset_ids: tuple[str, ...]):
    return select_approved_scenario_inputs(
        registry,
        split=Split.TRAIN,
        template_id="a_77870a0d84d3da57e4b0318d",
        asset_ids=asset_ids,
    )


def _program(
    *,
    bundle,
    template,
    family: CorpusFamily,
    master_seed: str,
    plan,
    frames: tuple[ScheduledSamplerFrame, ...],
    actions: tuple[object, ...],
    tool_results: tuple[ScriptedToolResult, ...] = (),
    response_warrants: tuple[BeatResponseWarrant, ...] = (),
    openings: tuple[BeatOpening, ...] | None = None,
) -> ScenarioProgram:
    beat_ids = tuple(f"b{index}" for index in range(len(actions)))
    return ScenarioProgram(
        bundle=bundle,
        template=template,
        family=family,
        master_seed=master_seed,
        timing_plan=plan,
        frames=frames,
        actions=actions,
        tool_results=tool_results,
        beat_ids=beat_ids,
        stale_results_by_beat=tuple(BeatStaleResults(beat_id, ()) for beat_id in beat_ids),
        perturbations=(),
        prompt_template=_PROMPT_TEMPLATE,
        response_warrants_by_beat=response_warrants,
        openings_by_beat=openings,
    )


def _timer(bundle, asset_id: str) -> TimerAssetPayload:
    payload = next((asset.payload for asset in bundle.assets if asset.asset_id == asset_id), None)
    if not isinstance(payload, TimerAssetPayload):
        raise TimerWave1RepairError(f"{asset_id} is not a selected timer asset")
    return payload


def _schedule(
    event_id: str, timer: TimerAssetPayload, *, instruction: str | None = None
) -> ScheduleAction:
    if timer.interval_ms is None or timer.message is None:
        raise TimerWave1RepairError("repair schedule requires a supported timer")
    text = timer.instruction if instruction is None else instruction
    return ScheduleAction(
        type="schedule",
        instruction=_span(event_id, text),
        interval_ms=timer.interval_ms,
        message=timer.message,
    )


def _idle() -> IdleAction:
    return IdleAction(type="idle", reason=IdleReason.NO_TRIGGER, related_event_id=None)


def _frame(at_ms: int, text: str) -> ScheduledSamplerFrame:
    cursor = utf16_len(text)
    return ScheduledSamplerFrame(
        at_ms,
        canonical_artifact_bytes(
            {
                "activity": "paused",
                "client_ts": at_ms,
                "input_type": "insertText",
                "is_composing": False,
                "selection_end": cursor,
                "selection_start": cursor,
                "text": text,
            }
        ),
    )


def _span(event_id: str, text: str) -> Span:
    return Span(event_id=event_id, start_utf16=0, end_utf16=utf16_len(text), text=text)


def _cost(items: tuple[BatchWorkItem, ...], config: PromptedPolicyConfig) -> dict[str, object]:
    pricing = ModelPricing(model=config.model)
    inputs = sum(estimate_tokens(canonical_artifact_bytes(item.body)) for item in items)

    def amount(output: int) -> str:
        value = (
            pricing.batch_multiplier
            * (
                Decimal(inputs) * pricing.input_per_million
                + Decimal(output) * pricing.output_per_million
            )
            / Decimal(1_000_000)
        )
        return format(value.quantize(Decimal("0.000001")), "f")

    return {
        "approval_ceiling_usd": amount(config.max_output_tokens * len(items)),
        "expected_input_tokens": inputs,
        "expected_output_tokens": 300 * len(items),
        "expected_usd": amount(300 * len(items)),
        "maximum_output_tokens": config.max_output_tokens * len(items),
        "pricing_source_date": pricing.source_date,
    }


def _checksums(files: dict[str, bytes]) -> bytes:
    return "".join(f"{sha256(files[name]).hexdigest()}  {name}\n" for name in sorted(files)).encode(
        "ascii"
    )


def _readme(manifest: dict[str, object]) -> str:
    cost = manifest["cost_estimate"]
    assert isinstance(cost, dict)
    return "\n".join(
        (
            "# Phase 2 timer Wave-1 v2 repair canary",
            "",
            "Hypothesis: schedule is prior-use protection, not already_handled; only integrate, skip, nudge, and respond consume an already_handled subject.",
            "",
            "The packet replays four byte-distinct pre-repair no_trigger prefixes, then tests an explicit delayed second reminder, a post-confirmation replacement limitation, and all four positive controls.",
            f"Requests: {manifest['request_count']} in one shard.",
            f"Expected Batch cost: ${cost['expected_usd']}; approval ceiling: ${cost['approval_ceiling_usd']}.",
            "",
        )
    )
