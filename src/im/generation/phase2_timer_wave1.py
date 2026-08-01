"""Deterministic offline WP2-2 Timer Wave-1 canary packet."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

from im.assets import CorpusFamily, Split
from im.assets.model import TimerAssetPayload, canonical_artifact_bytes
from im.config import estimate_tokens
from im.generation.ingestion import ScheduledSamplerFrame
from im.generation.phase2_review import BoundaryClass, FloorClass
from im.generation.phase2_timer_wave0 import (
    build_timer_wave0_programs,
    load_timer_wave0_inputs,
)
from im.generation.phase2_timer_wave0_boundaries import build_timer_wave0_boundary_programs
from im.generation.publication import publish_directory_transaction
from im.generation.scenario_catalog import _build_selected_family_program, build_family_program
from im.generation.scenarios import (
    BeatStaleResults,
    DeclaredPerturbation,
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
from im.schema.actions import IdleAction, IdleReason, ScheduleAction, Span
from im.schema.textspan import utf16_len

_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_TIMER_WAVE1_OUTPUT = _ROOT / "review" / "phase2" / "timer-wave-1"
_STAGE = "t2w1"
_MAX_ENQUEUED_TOKENS = 700_000
_MAX_OUTPUT_TOKENS = 8_192
_EXPECTED_DECISIONS = 82
_EXPECTED_SOURCE_UNITS = 12


class TimerWave1Error(ValueError):
    """The fixed wave-one canary no longer matches its approved plan."""


@dataclass(frozen=True, slots=True)
class _Stream:
    logical_stream_id: str
    source_unit_id: str
    branch: str
    program: ScenarioProgram


@dataclass(frozen=True, slots=True)
class _Executed:
    stream: _Stream
    generated: GeneratedScenario


@dataclass(frozen=True, slots=True)
class TimerWave1Plan:
    """Offline packet plus the exact Batch work derived from it."""

    files: dict[str, bytes]
    items: tuple[BatchWorkItem, ...]
    shards: tuple[BatchShard, ...]


async def build_timer_wave1_plan(*, repository_root: Path = _ROOT) -> TimerWave1Plan:
    """Execute the fixed 82-decision TRAIN canary and render Batch inputs locally."""
    repository_root = repository_root.resolve()
    registry = load_timer_wave0_inputs(
        approved_root=repository_root / "review" / "phase1" / "approved",
        selection_contract_path=repository_root / "spec" / "phase2-selection-v1.json",
    )
    streams = _streams(registry)
    _validate_streams(streams)
    with TemporaryDirectory(prefix="phase2-timer-wave1-") as temporary:
        executed = await _execute(streams, Path(temporary), repository_root)
        return _packet(executed, repository_root)


async def materialize_timer_wave1_packet(
    output: Path = DEFAULT_TIMER_WAVE1_OUTPUT,
    *,
    repository_root: Path = _ROOT,
) -> TimerWave1Plan:
    """Create-only publish the offline packet; this function never calls a provider."""
    plan = await build_timer_wave1_plan(repository_root=repository_root)
    publish_directory_transaction(output, plan.files)
    return plan


def _streams(registry) -> tuple[_Stream, ...]:
    wave0 = {
        item.spec.logical_stream_id: item.program for item in build_timer_wave0_programs(registry)
    }
    status_bundle, status_template = select_approved_scenario_inputs(
        registry,
        split=Split.TRAIN,
        template_id="a_e35790e7d64ca17bc1e3b4d9",
        asset_ids=("a_297508c00e4e7beb6a08d268", "a_067f59d6c56633412a0d45b4"),
    )
    contention_bundle, contention_template = select_approved_scenario_inputs(
        registry,
        split=Split.TRAIN,
        template_id="a_21e7ddae34d168708913157f",
        asset_ids=("a_0ef6b431c2a146d9648263aa", "a_4d9e7e5fdf179993fd3d8367"),
    )

    def status(state: str) -> ScenarioProgram:
        return _build_selected_family_program(
            CorpusFamily.TIMER_CANCEL,
            status_bundle,
            status_template,
            "phase2-timer-wave1:status:a",
            _variant=("timer_status", state),
        )

    def floor(state: str) -> ScenarioProgram:
        return _build_selected_family_program(
            CorpusFamily.TIMER_CONTENTION,
            contention_bundle,
            contention_template,
            "phase2-timer-wave1:contention-floor:a",
            _variant=("floor_state", state),
        )

    return (
        _Stream(
            "normal-compact-a", "normal-compact-a", "normal_compact", wave0["normal-compact-a"]
        ),
        _Stream("normal-wide-a", "normal-wide-a", "normal_wide", wave0["normal-wide-a"]),
        _Stream("timer-status-active", "timer-status-a", "timer_status_active", status("active")),
        _Stream(
            "timer-status-canceled", "timer-status-a", "timer_status_canceled", status("canceled")
        ),
        _Stream(
            "quoted-restraint-a", "quoted-restraint-a", "quoted_non_direct", wave0["quoted-noop-b"]
        ),
        *(
            _Stream(
                item.logical_stream_id,
                "boundary-ambiguous-cancel"
                if item.logical_stream_id.startswith("ambiguous-cancel")
                else f"boundary-{item.logical_stream_id}",
                item.branch,
                item.program,
            )
            for item in build_timer_wave0_boundary_programs(registry)
        ),
        _Stream(
            "schedule-similar-duplicate-a",
            "schedule-duplicate-a",
            "schedule_duplicate",
            _duplicate_program(registry),
        ),
        _Stream(
            "contention-floor-typing", "contention-floor-a", "contention_typing", floor("typing")
        ),
        _Stream(
            "contention-floor-paused", "contention-floor-a", "contention_paused", floor("paused")
        ),
        _Stream(
            "rollover-a",
            "rollover-a",
            "rollover",
            build_family_program(
                CorpusFamily.ROLLOVER,
                registry,
                split=Split.TRAIN,
                template_id="a_95c425c1e1736f407ccc54db",
                asset_ids=(
                    "a_0c280681c3a090e5c4901abd",
                    "a_067f59d6c56633412a0d45b4",
                    "a_4d9e7e5fdf179993fd3d8367",
                ),
                master_seed="phase2-timer-wave1:rollover:a",
            ),
        ),
    )


def _duplicate_program(registry) -> ScenarioProgram:
    """The one new Wave-1 branch: distinct schedule followed by true duplicate restraint."""
    bundle, template = select_approved_scenario_inputs(
        registry,
        split=Split.TRAIN,
        template_id="a_77870a0d84d3da57e4b0318d",
        asset_ids=("a_067f59d6c56633412a0d45b4", "a_11d7f848364801c6724c9d75"),
    )
    first = _timer(bundle, "a_067f59d6c56633412a0d45b4")
    second = _timer(bundle, "a_11d7f848364801c6724c9d75")
    plan = materialize_timing_plan(
        TimingSeed(Split.TRAIN, "phase2-timer-wave1:semantic-duplicate:a"), 5
    )
    actions = (
        _schedule("e_000002", first),
        _idle(),
        _schedule("e_000005", second),
        _idle(),
        _idle(),
    )
    second_at = sum(plan.service_ms[:2]) + 1
    duplicate_at = second_at + sum(plan.service_ms[2:4]) + 1
    return ScenarioProgram(
        bundle=bundle,
        template=template,
        family=CorpusFamily.TIMER_NORMAL,
        master_seed="phase2-timer-wave1:semantic-duplicate:a",
        timing_plan=plan,
        frames=(
            _frame(0, first.instruction),
            _frame(second_at, second.instruction),
            _frame(duplicate_at, second.instruction),
        ),
        actions=actions,
        tool_results=(),
        beat_ids=tuple(f"b{index}" for index in range(len(actions))),
        stale_results_by_beat=tuple(
            BeatStaleResults(f"b{index}", ()) for index in range(len(actions))
        ),
        perturbations=(DeclaredPerturbation("timer_fire"),),
    )


async def _execute(
    streams: tuple[_Stream, ...], directory: Path, repository_root: Path
) -> tuple[_Executed, ...]:
    results = []
    for stream in streams:
        generated = await execute_scenario(
            stream.program,
            session_id=f"phase2-timer-wave1-{stream.logical_stream_id}",
            directory=directory / stream.logical_stream_id,
            repository_root=repository_root,
        )
        validate_generated_scenario(generated)
        results.append(_Executed(stream, generated))
    return tuple(results)


def _packet(executed: tuple[_Executed, ...], repository_root: Path) -> TimerWave1Plan:
    config = PromptedPolicyConfig(
        model="gpt-5.6-terra",
        reasoning_effort="high",
        max_output_tokens=_MAX_OUTPUT_TOKENS,
        max_attempts=1,
    )
    builder = ResponsesRequestBuilder(
        PromptRenderer(PromptArtifacts.from_repository(repository_root)), config
    )
    binding = digest(
        canonical_artifact_bytes(
            {
                "kind": "phase2-timer-wave1-binding-v1",
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
                        variant_id="timer-wave-1",
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
                    "call_index": boundary.call_index,
                    **_review_metadata(stream, index, action),
                    "custom_id": custom_id,
                    "family": stream.stream.program.family.value,
                    "logical_stream_id": stream.stream.logical_stream_id,
                    "oracle_action": action.model_dump(mode="json"),
                    "program_action_index": index,
                    "policy_prefix_sha256": digest(boundary.policy_bytes),
                    "request_body_sha256": digest(body_bytes),
                    "source_unit_id": stream.stream.source_unit_id,
                    "stream_sha256": stream.generated.stream.sha256,
                }
            )
    item_tuple = tuple(items)
    if len(item_tuple) != _EXPECTED_DECISIONS:
        raise TimerWave1Error("wave one must contain exactly 82 decision requests")
    shards = shard_work(_STAGE, item_tuple, max_enqueued_tokens=_MAX_ENQUEUED_TOKENS)
    if len(shards) < 2:
        raise TimerWave1Error("wave one must remain split across at least two Batch shards")
    inputs = {
        f"teacher-input/shard-{shard.shard_index:03}.jsonl": shard.input_jsonl for shard in shards
    }
    cost = _cost(item_tuple, config)
    manifest = {
        "api_call_performed": False,
        "authorization_state": "owner_authorized_not_submitted",
        "binding_sha256": binding,
        "cost_estimate": cost,
        "decision_count": len(item_tuple),
        "endpoint": "/v1/responses",
        "format_version": 1,
        "kind": "phase2-timer-wave1-teacher-plan",
        "max_enqueued_tokens": _MAX_ENQUEUED_TOKENS,
        "max_output_tokens_per_request": config.max_output_tokens,
        "model": config.model,
        "reasoning_effort": config.reasoning_effort,
        "request_count": len(item_tuple),
        "shard_count": len(shards),
        "shards": [
            {
                "estimated_input_tokens": shard.estimated_input_tokens,
                "input_path": f"teacher-input/shard-{shard.shard_index:03}.jsonl",
                "input_sha256": shard.input_sha256,
                "request_count": len(shard.items),
                "shard_index": shard.shard_index,
                "stage": _STAGE,
            }
            for shard in shards
        ],
        "input_bindings": _input_bindings(repository_root),
        "source_inputs": _source_inputs(executed),
        "source_unit_count": len({item.stream.source_unit_id for item in executed}),
        "stage": _STAGE,
        "targets": targets,
        "wave_id": "timer-wave-1",
    }
    raw = {"format_version": 1, "streams": [_raw_stream(item) for item in executed]}
    files = {
        "README.md": _readme(manifest).encode(),
        "raw-streams.json": canonical_artifact_bytes(raw),
        "teacher-plan.json": canonical_artifact_bytes(manifest),
        **inputs,
    }
    return TimerWave1Plan({**files, "SHA256SUMS": _checksums(files)}, item_tuple, shards)


def _review_metadata(stream: _Executed, index: int, action: object) -> dict[str, object]:
    """Bind the static D1/D2 route inputs before teacher output exists."""
    decision = stream.generated.sidecar.decisions[index]
    action_type = str(getattr(action, "type"))
    boundary = BoundaryClass.ORDINARY
    risks: set[str] = set()
    logical_id = stream.stream.logical_stream_id
    if logical_id == "schedule-similar-duplicate-a" and index == 2:
        boundary = BoundaryClass.SCHEDULE_SIMILAR_DISTINCT
        risks.add("schedule_semantic_duplicate_boundary")
    elif logical_id == "schedule-similar-duplicate-a" and index == 4:
        boundary = BoundaryClass.SCHEDULE_SEMANTIC_DUPLICATE
        risks.add("schedule_semantic_duplicate_boundary")
    elif logical_id == "ambiguous-cancel-active" and index == 5:
        boundary = BoundaryClass.AMBIGUOUS_CANCEL
        risks.add("cancel_semantic_referent_resolution")
    elif action_type == "respond":
        boundary = BoundaryClass.ACTIVE_FLOOR_RESPONSE
        risks.add("active_floor_response_boundary")
        if logical_id == "ambiguous-cancel-yielded":
            risks.add("cancel_semantic_referent_resolution")
    if action_type == "skip":
        risks.add("skip_reason_selection")
    rollover = logical_id == "rollover-a"
    if rollover:
        risks.add("rollover_or_checkpoint_projection")

    reasons = []
    if action_type in {"schedule", "cancel", "skip", "nudge"}:
        reasons.append("mandatory_action")
    if rollover:
        reasons.append("rollover")
    if risks:
        reasons.append("risk_flag")
    idle_boundary = (
        "lexical_boundary"
        if logical_id == "contention-floor-typing" and index == 4
        else None
    )
    if idle_boundary:
        reasons.append("idle_boundary_100_percent")
    if action_type == "idle" and str(getattr(action, "reason", "")) in {
        "awaiting_opening",
        "already_handled",
        "ambiguous",
        "instruction_not_direct",
    }:
        reasons.append("idle_reason_100_percent")
    floor = (
        FloorClass.OPEN
        if decision.floor_open
        else FloorClass.OWNED
        if decision.floor_owned
        else FloorClass.CLOSED
    )
    return {
        "boundary_class": boundary.value,
        "causal_state_class": stream.stream.branch,
        "cell": {
            "family": stream.stream.program.family.value,
            "floor": floor.value,
            "protocol": HarnessProtocol.GENERATION.value,
        },
        "mandatory_review": bool(reasons),
        "mandatory_review_reasons": reasons,
        "idle_boundary": idle_boundary,
        "risk_flags": sorted(risks),
        "rollover": rollover,
    }


def _validate_streams(streams: tuple[_Stream, ...]) -> None:
    if len(streams) != 15 or len({item.logical_stream_id for item in streams}) != len(streams):
        raise TimerWave1Error("wave one stream inventory drifted")
    if sum(len(item.program.actions) for item in streams) != _EXPECTED_DECISIONS:
        raise TimerWave1Error("wave one decision inventory drifted")
    if len({item.source_unit_id for item in streams}) != _EXPECTED_SOURCE_UNITS:
        raise TimerWave1Error("wave one requires exactly twelve source units")


def _source_inputs(executed: tuple[_Executed, ...]) -> list[dict[str, object]]:
    return [
        {
            "assets": [
                {
                    "asset_id": asset.asset_id,
                    "content_sha256": asset.content_sha256,
                }
                for asset in item.stream.program.bundle.assets
            ],
            "logical_stream_id": item.stream.logical_stream_id,
            "source_unit_id": item.stream.source_unit_id,
            "template": {
                "asset_id": item.stream.program.template.asset_id,
                "content_sha256": item.stream.program.template.content_sha256,
            },
        }
        for item in executed
    ]


def _input_bindings(repository_root: Path) -> dict[str, str]:
    registry = repository_root / "review" / "phase1" / "approved" / "registry.jsonl"
    seal = repository_root / "review" / "phase1" / "approved" / "train-seal.json"
    return {
        "registry_path": registry.relative_to(repository_root).as_posix(),
        "registry_sha256": digest(registry.read_bytes()),
        "train_seal_path": seal.relative_to(repository_root).as_posix(),
        "train_seal_sha256": digest(seal.read_bytes()),
    }


def _raw_stream(item: _Executed) -> dict[str, object]:
    return {
        "actions": [action.model_dump(mode="json") for action in item.stream.program.actions],
        "branch": item.stream.branch,
        "decision_boundaries": [
            {
                "call_index": boundary.call_index,
                "policy_prefix_sha256": digest(boundary.policy_bytes),
            }
            for boundary in item.generated.decision_boundaries
        ],
        "frames": [
            {"at_ms": frame.at_ms, "sampler_json": frame.raw_bytes.decode("utf-8")}
            for frame in item.stream.program.frames
        ],
        "logical_stream_id": item.stream.logical_stream_id,
        "sidecar": item.generated.sidecar.as_json_object(),
        "source_unit_id": item.stream.source_unit_id,
        "stream_sha256": item.generated.stream.sha256,
    }


def _cost(items: tuple[BatchWorkItem, ...], config: PromptedPolicyConfig) -> dict[str, object]:
    pricing = ModelPricing(model=config.model)
    inputs = sum(estimate_tokens(canonical_artifact_bytes(item.body)) for item in items)
    expected_output = 300 * len(items)
    maximum_output = config.max_output_tokens * len(items)

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
        "approval_ceiling_usd": amount(maximum_output),
        "batch_multiplier": format(pricing.batch_multiplier, "f"),
        "expected_input_tokens": inputs,
        "expected_output_tokens": expected_output,
        "expected_usd": amount(expected_output),
        "maximum_output_tokens": maximum_output,
        "pricing_source_date": pricing.source_date,
    }


def _schedule(event_id: str, payload: TimerAssetPayload) -> ScheduleAction:
    if payload.interval_ms is None or payload.message is None:
        raise TimerWave1Error("semantic-duplicate branch requires supported timers")
    return ScheduleAction(
        type="schedule",
        instruction=_span(event_id, payload.instruction),
        interval_ms=payload.interval_ms,
        message=payload.message,
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


def _timer(bundle, asset_id: str) -> TimerAssetPayload:
    payload = next(
        (item.payload for item in bundle.assets if item.asset_id == asset_id),
        None,
    )
    if not isinstance(payload, TimerAssetPayload):
        raise TimerWave1Error(f"{asset_id} is not a selected timer asset")
    return payload


def _checksums(files: dict[str, bytes]) -> bytes:
    return "".join(f"{sha256(files[name]).hexdigest()}  {name}\n" for name in sorted(files)).encode(
        "ascii"
    )


def _readme(manifest: dict[str, object]) -> str:
    cost = manifest["cost_estimate"]
    assert isinstance(cost, dict)
    return "\n".join(
        (
            "# Phase 2 timer Wave-1 teacher canary",
            "",
            "Outcome: inspect the fixed TRAIN timer slice before any bulk generation.",
            "",
            "Hypothesis: the 82 decisions preserve normal, cancellation, duplicate, boundary,",
            "contention-floor, and rollover behavior without reopening approved assets.",
            "",
            f"Requests: {manifest['request_count']} across {len(manifest['shards'])} shards.",
            f"Expected Batch cost: ${cost['expected_usd']}; "
            f"approval ceiling: ${cost['approval_ceiling_usd']}.",
            "Raw streams and the exact oracle mapping are included for per-decision review.",
            "",
        )
    )
