"""Executable, TRAIN-sealed programs for the Phase 2 order-zero sentinel pack."""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

from im.assets import AssetRegistry, Split, load_verified_registry_seals
from im.assets.model import (
    AssetRecord,
    LookupAssetPayload,
    TextAssetPayload,
    TimerAssetPayload,
    canonical_artifact_bytes,
)
from im.canonical_json import canonicalize_tim_json
from im.config import estimate_tokens
from im.generation.g7_need_plan import G7NeedPlan, build_g7_need_evidence
from im.generation.g7_response_assets import HumanAuthoredResponseAsset, ResponseDraftSpec
from im.generation.ingestion import ScheduledSamplerFrame
from im.generation.need_lineage import NeedBasisKind, NeedStatus
from im.generation.publication import publish_directory_transaction
from im.generation.response_contracts import AnswerContract, RequiredAnswerPoint
from im.generation.scenarios import (
    BeatOpening,
    BeatResponseWarrant,
    BeatStaleResults,
    CounterfactualDeclaration,
    DeclaredPerturbation,
    GeneratedScenario,
    ResponseWarrantKind,
    ScenarioProgram,
    execute_scenario,
)
from im.generation.timing import TimingPlan, TimingSeed, materialize_timing_plan
from im.policy.prompted import (
    ModelPricing,
    PromptArtifacts,
    PromptedPolicyConfig,
    PromptRenderer,
    ResponsesRequestBuilder,
)
from im.schema.actions import (
    Action,
    DelegateAction,
    IdleAction,
    IdleReason,
    RespondAction,
    ScheduleAction,
    SkipAction,
    SkipReason,
    Span,
)
from im.schema.common import ToolName
from im.schema.textspan import utf16_len
from im.tools import ScriptedToolResult

_REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SENTINEL_V2_CONTRACT = _REPOSITORY_ROOT / "spec" / "phase2-sentinel-v2.json"
DEFAULT_APPROVED_ROOT = (
    _REPOSITORY_ROOT / "review" / "phase2" / "train-asset-readiness-repair-review"
)
DEFAULT_HELDOUT_SEAL_ROOT = _REPOSITORY_ROOT / "review" / "phase1" / "approved"
DEFAULT_SENTINEL_RESPONSE = (
    _REPOSITORY_ROOT
    / "review"
    / "phase2"
    / "train-asset-readiness-repair-review"
    / "sentinel-response.json"
)
DEFAULT_SENTINEL_V2_OUTPUT = _REPOSITORY_ROOT / "review" / "phase2" / "sentinel-0-executable-v2"
_CONTRACT_SHA256 = "sha256:bf693f83bc7a382b2b0a66d167d620078dac4992d6b32aadd3bd17bc5b337fc2"
_EXPECTED_OUTPUT_TOKENS = 300
_MILLION = Decimal(1_000_000)


class ExecutableSentinelError(ValueError):
    """The executable sentinel contract or its sealed inputs are inconsistent."""


@dataclass(frozen=True, slots=True)
class SentinelProgram:
    logical_stream_id: str
    program: ScenarioProgram


@dataclass(frozen=True, slots=True)
class ExecutedSentinelStream:
    logical_stream_id: str
    generated: GeneratedScenario


@dataclass(frozen=True, slots=True)
class SentinelTeacherPacket:
    """Exact local Batch input and approval summary; it cannot submit itself."""

    input_path: str
    input_jsonl: bytes
    manifest_bytes: bytes
    review_bytes: bytes


def load_executable_sentinel_inputs(
    *,
    contract_path: Path = DEFAULT_SENTINEL_V2_CONTRACT,
    approved_root: Path = DEFAULT_APPROVED_ROOT,
    heldout_seal_root: Path = DEFAULT_HELDOUT_SEAL_ROOT,
    response_path: Path = DEFAULT_SENTINEL_RESPONSE,
) -> tuple[dict[str, object], AssetRegistry, HumanAuthoredResponseAsset]:
    """Load the digest-locked v2 contract and its complete approval evidence."""
    contract_bytes = contract_path.read_bytes()
    contract = _canonical_object(contract_bytes, "sentinel v2 contract")
    if f"sha256:{sha256(contract_bytes).hexdigest()}" != _CONTRACT_SHA256:
        raise ExecutableSentinelError("sentinel v2 contract differs from its expected SHA-256")
    if contract.get("kind") != "phase2-sentinel-v2" or contract.get("format_version") != 2:
        raise ExecutableSentinelError("sentinel v2 contract kind or version is invalid")

    registry_bytes = (approved_root / "registry.jsonl").read_bytes()
    seal_bytes = (
        (heldout_seal_root / "test-seal.json").read_bytes(),
        (heldout_seal_root / "demo-seal.json").read_bytes(),
        (approved_root / "train-seal.json").read_bytes(),
    )
    registry_claim = contract.get("registry")
    if not isinstance(registry_claim, dict):
        raise ExecutableSentinelError("sentinel v2 registry claim is invalid")
    if registry_claim != {
        "registry_sha256": f"sha256:{sha256(registry_bytes).hexdigest()}",
        "train_seal_entry_count": 89,
        "train_seal_sha256": f"sha256:{sha256(seal_bytes[2]).hexdigest()}",
    }:
        raise ExecutableSentinelError("sentinel v2 registry claim does not match approved bytes")
    registry, seals = load_verified_registry_seals(
        registry_bytes,
        seal_bytes,
        required_splits=(Split.TEST, Split.DEMO, Split.TRAIN),
    )
    train_seal = next(seal for seal in seals if seal.split is Split.TRAIN)
    if len(train_seal.entries) != 89:
        raise ExecutableSentinelError("sentinel v2 requires the complete 89-entry TRAIN seal")

    response_bytes = response_path.read_bytes()
    response_claim = contract.get("response")
    receipt = _canonical_object(response_bytes, "sentinel response receipt")
    if not isinstance(response_claim, dict) or response_claim.get("receipt_sha256") != (
        f"sha256:{sha256(response_bytes).hexdigest()}"
    ):
        raise ExecutableSentinelError("sentinel response receipt does not match the v2 contract")
    response = _human_response(receipt)
    if (
        response_claim.get("candidate_response") != response.response_text
        or response_claim.get("content_sha256") != receipt.get("content_sha256")
        or response_claim.get("support_asset_id")
        != receipt.get("visible_support", {}).get("asset_id")
    ):
        raise ExecutableSentinelError("sentinel response claim differs from the approved receipt")
    support_id = response_claim["support_asset_id"]
    visible_support = receipt.get("visible_support")
    support = next(
        (asset for asset in registry.pool(Split.TRAIN).assets if asset.asset_id == support_id),
        None,
    )
    if (
        support is None
        or not registry.is_approved(support)
        or not isinstance(support.payload, TextAssetPayload)
        or not isinstance(visible_support, dict)
        or support.payload.text != visible_support.get("text")
        or support.content_sha256 != visible_support.get("content_sha256")
    ):
        raise ExecutableSentinelError(
            "sentinel response support does not match its approved TRAIN asset"
        )
    return contract, registry, response


def build_executable_sentinel_programs(
    contract: dict[str, object],
    registry: AssetRegistry,
    response: HumanAuthoredResponseAsset,
) -> tuple[SentinelProgram, ...]:
    """Compile the six fixed logical streams from their exact sealed selections."""
    streams = _object_list(contract.get("streams"), "sentinel streams")
    by_id = {stream["logical_stream_id"]: stream for stream in streams}
    expected = {
        "partial",
        "response-active",
        "response-open",
        "timer-pair",
        "lookup-pair",
        "ambiguous-cancel",
    }
    if set(by_id) != expected:
        raise ExecutableSentinelError("sentinel v2 stream inventory is not closed")
    response_claim = contract.get("response")
    if not isinstance(response_claim, dict):
        raise ExecutableSentinelError("sentinel v2 response claim is invalid")
    response_streams = (by_id["response-active"], by_id["response-open"])
    if (
        any(
            stream.get("asset_ids") != [response_claim.get("support_asset_id")]
            for stream in response_streams
        )
        or response_streams[0].get("template_asset_id")
        != response_streams[1].get("template_asset_id")
        or response_streams[0].get("master_seed") != response_streams[1].get("master_seed")
    ):
        raise ExecutableSentinelError("sentinel response twins do not share one sealed selection")
    builders = {
        "partial": lambda stream: _partial_program(registry, stream),
        "response-active": lambda stream: _response_program(registry, stream, response, False),
        "response-open": lambda stream: _response_program(registry, stream, response, True),
        "timer-pair": lambda stream: _timer_program(registry, stream),
        "lookup-pair": lambda stream: _lookup_program(registry, stream),
        "ambiguous-cancel": lambda stream: _ambiguous_cancel_program(registry, stream),
    }
    return tuple(
        SentinelProgram(stream_id, builders[stream_id](by_id[stream_id]))
        for stream_id in (
            "partial",
            "response-active",
            "response-open",
            "timer-pair",
            "lookup-pair",
            "ambiguous-cancel",
        )
    )


async def execute_executable_sentinel(
    programs: tuple[SentinelProgram, ...],
    *,
    directory: Path,
    repository_root: Path | None = None,
) -> tuple[ExecutedSentinelStream, ...]:
    """Run every v2 program through the production virtual-time runtime."""
    directory.mkdir(parents=True, exist_ok=True)
    generated = []
    for selected in programs:
        result = await execute_scenario(
            selected.program,
            session_id=f"phase2-sentinel-v2-{selected.logical_stream_id}",
            directory=directory / selected.logical_stream_id,
            repository_root=repository_root,
        )
        generated.append(ExecutedSentinelStream(selected.logical_stream_id, result))
    return tuple(generated)


def sentinel_target_actions(
    contract: dict[str, object],
    generated: tuple[ExecutedSentinelStream, ...],
) -> tuple[Action, ...]:
    """Return the eight target actions only after exact contract comparison."""
    by_id = {item.logical_stream_id: item.generated for item in generated}
    actions = []
    for target in _object_list(contract.get("targets"), "sentinel targets"):
        scenario = by_id.get(target["logical_stream_id"])
        index = target.get("program_action_index")
        if scenario is None or isinstance(index, bool) or not isinstance(index, int):
            raise ExecutableSentinelError("sentinel target does not identify a program action")
        try:
            action = scenario.program.actions[index]
        except IndexError as error:
            raise ExecutableSentinelError("sentinel target action index is out of range") from error
        if action.model_dump(mode="json") != target.get("oracle_action"):
            raise ExecutableSentinelError("executed sentinel action differs from its v2 contract")
        actions.append(action)
    if len(actions) != 8:
        raise ExecutableSentinelError("sentinel v2 must expose exactly eight target actions")
    return tuple(actions)


def build_sentinel_teacher_packet(
    contract: dict[str, object],
    generated: tuple[ExecutedSentinelStream, ...],
    *,
    repository_root: Path = _REPOSITORY_ROOT,
) -> SentinelTeacherPacket:
    """Render the exact eight-request local Batch file without any provider access."""
    sentinel_target_actions(contract, generated)
    teacher = contract.get("teacher_plan")
    if not isinstance(teacher, dict):
        raise ExecutableSentinelError("sentinel v2 teacher plan is invalid")
    if (
        teacher.get("execution_mode") != "batch"
        or teacher.get("status") != "offline_planned_not_submitted"
        or teacher.get("request_count") != 8
        or teacher.get("shard_count") != 1
        or teacher.get("endpoint") != "/v1/responses"
    ):
        raise ExecutableSentinelError("sentinel v2 teacher plan is not the closed offline plan")
    input_path = teacher.get("input_path")
    output_path = teacher.get("output_path")
    model = teacher.get("model")
    effort = teacher.get("reasoning_effort")
    maximum = teacher.get("max_output_tokens")
    if (
        not isinstance(input_path, str)
        or not isinstance(output_path, str)
        or not isinstance(model, str)
        or not isinstance(effort, str)
        or isinstance(maximum, bool)
        or not isinstance(maximum, int)
    ):
        raise ExecutableSentinelError("sentinel v2 teacher settings are invalid")
    _safe_relative_path(input_path)
    _safe_relative_path(output_path)
    config = PromptedPolicyConfig(
        model=model,
        reasoning_effort=effort,
        max_output_tokens=maximum,
        max_attempts=1,
    )
    builder = ResponsesRequestBuilder(
        PromptRenderer(PromptArtifacts.from_repository(repository_root)), config
    )
    by_id = {item.logical_stream_id: item.generated for item in generated}
    requests: list[tuple[str, bytes]] = []
    bodies: list[dict[str, object]] = []
    target_records = []
    for target in _object_list(contract.get("targets"), "sentinel targets"):
        logical_id = target["logical_stream_id"]
        index = target["program_action_index"]
        target_id = target["target_id"]
        if (
            not isinstance(logical_id, str)
            or not isinstance(target_id, str)
            or not isinstance(index, int)
        ):
            raise ExecutableSentinelError("sentinel target teacher mapping is invalid")
        scenario = by_id[logical_id]
        boundary = scenario.decision_boundaries[index]
        custom_id = f"s0v2.{target_id}.a1"
        body = builder.build(boundary.policy_bytes)
        requests.append((custom_id, boundary.policy_bytes))
        bodies.append(body)
        target_records.append(
            {
                "call_index": boundary.call_index,
                "custom_id": custom_id,
                "logical_stream_id": logical_id,
                "oracle_action": target["oracle_action"],
                "policy_prefix_sha256": _digest(boundary.policy_bytes),
                "program_action_index": index,
                "request_body_sha256": _digest(canonical_artifact_bytes(body)),
                "stream_sha256": scenario.stream.sha256,
                "target_id": target_id,
            }
        )
    input_jsonl = builder.render_batch_jsonl(requests)
    input_tokens = sum(estimate_tokens(canonical_artifact_bytes(body)) for body in bodies)
    pricing = ModelPricing(model=model)
    cost = _batch_cost(
        pricing,
        input_tokens=input_tokens,
        requests=len(requests),
        maximum_output_tokens=maximum,
    )
    manifest = {
        "api_call_performed": False,
        "authorization_state": "not_authorized",
        "contract_sha256": _CONTRACT_SHA256,
        "cost_estimate": cost,
        "endpoint": teacher["endpoint"],
        "format_version": 1,
        "input_path": input_path,
        "input_sha256": _digest(input_jsonl),
        "kind": "phase2-sentinel-v2-teacher-plan",
        "max_output_tokens_per_request": maximum,
        "model": model,
        "output_path": output_path,
        "reasoning_effort": effort,
        "request_count": len(requests),
        "shard_count": 1,
        "streams": [
            {
                "decision_count": len(item.generated.program.actions),
                "logical_stream_id": item.logical_stream_id,
                "stream_sha256": item.generated.stream.sha256,
            }
            for item in generated
        ],
        "targets": target_records,
    }
    manifest_bytes = canonical_artifact_bytes(manifest)
    return SentinelTeacherPacket(
        input_path=input_path,
        input_jsonl=input_jsonl,
        manifest_bytes=manifest_bytes,
        review_bytes=_teacher_review(manifest),
    )


async def materialize_executable_sentinel_packet(
    output: Path = DEFAULT_SENTINEL_V2_OUTPUT,
    *,
    repository_root: Path = _REPOSITORY_ROOT,
) -> SentinelTeacherPacket:
    """Execute locally, then atomically publish the closed offline approval packet."""
    contract, registry, response = load_executable_sentinel_inputs()
    programs = build_executable_sentinel_programs(contract, registry, response)
    with TemporaryDirectory(prefix="phase2-sentinel-v2-runtime-") as temporary:
        generated = await execute_executable_sentinel(
            programs,
            directory=Path(temporary),
            repository_root=repository_root,
        )
        packet = build_sentinel_teacher_packet(
            contract,
            generated,
            repository_root=repository_root,
        )
    publish_directory_transaction(output, _teacher_packet_files(packet))
    return packet


def _partial_program(registry: AssetRegistry, stream: dict[str, object]) -> ScenarioProgram:
    text = _text(registry, stream, 0)
    return _program(
        registry,
        stream,
        (_frame(0, text.text, activity="active"),),
        (IdleAction(type="idle", reason=IdleReason.TYPING_ACTIVE, related_event_id=None),),
        perturbation="mark_restraint",
    )


def _response_program(
    registry: AssetRegistry,
    stream: dict[str, object],
    response: HumanAuthoredResponseAsset,
    yielded: bool,
) -> ScenarioProgram:
    visible = f"{response.teacher_visible_prefix}\n\n{response.draft.invitation}"
    action = (
        RespondAction(type="respond", reply_to_event_id="e_000002", text=response.response_text)
        if yielded
        else IdleAction(
            type="idle", reason=IdleReason.AWAITING_OPENING, related_event_id="e_000002"
        )
    )
    beat = "b0"
    member = "yielded" if yielded else "active"
    return _program(
        registry,
        stream,
        (_frame(0, visible, activity="paused" if yielded else "active"),),
        (action,),
        perturbation="floor_opening",
        response_warrants=(BeatResponseWarrant(beat, "e_000002", ResponseWarrantKind.INVITATION),),
        openings=(BeatOpening(beat, "e_000002"),) if yielded else (),
        counterfactual=CounterfactualDeclaration(
            kind="twin",
            group_id="phase2-sentinel-response-v2",
            member_id=member,
            member_ids=("active", "yielded"),
            flipped_perturbation="floor_opening",
        ),
    )


def _timer_program(registry: AssetRegistry, stream: dict[str, object]) -> ScenarioProgram:
    first, second = (_timer(registry, stream, index) for index in range(2))
    plan = _timing(stream, 5)
    second_at = sum(plan.service_ms[:2]) + 1
    duplicate_at = second_at + sum(plan.service_ms[2:4]) + 1
    return _program(
        registry,
        stream,
        (
            _frame(0, first.instruction),
            _frame(second_at, second.instruction),
            _frame(duplicate_at, second.instruction),
        ),
        (
            _schedule("e_000002", first),
            IdleAction(type="idle", reason=IdleReason.NO_TRIGGER, related_event_id=None),
            _schedule("e_000005", second),
            IdleAction(type="idle", reason=IdleReason.NO_TRIGGER, related_event_id=None),
            IdleAction(type="idle", reason=IdleReason.NO_TRIGGER, related_event_id=None),
        ),
        perturbation="timer_fire",
        timing=plan,
    )


def _lookup_program(registry: AssetRegistry, stream: dict[str, object]) -> ScenarioProgram:
    lookup = _lookup(registry, stream, 0)
    plan = _timing(stream, 7)
    refresh_at = plan.service_ms[0] + 1
    refresh_source = f"Refresh {lookup.query}."
    abandon_at = sum(plan.service_ms[:4]) + 3
    abandon_source = f"Never mind; {lookup.query} is no longer relevant."
    actions = (
        _delegate("e_000002", lookup.query, lookup.query),
        IdleAction(type="idle", reason=IdleReason.AWAITING_TOOL, related_event_id="e_000002"),
        SkipAction(type="skip", target_event_id="e_000006", reason=SkipReason.SUPERSEDED_QUERY),
        _delegate("e_000005", refresh_source, lookup.query),
        IdleAction(type="idle", reason=IdleReason.NO_TRIGGER, related_event_id=None),
        SkipAction(type="skip", target_event_id="e_000011", reason=SkipReason.STALE_TOOL_RESULT),
        IdleAction(type="idle", reason=IdleReason.NO_TRIGGER, related_event_id=None),
    )
    beats = tuple(f"b{index}" for index in range(len(actions)))
    need_lineage, provenance = build_g7_need_evidence(
        beats,
        actions,
        (
            G7NeedPlan(
                "n_original",
                0,
                2,
                NeedStatus.SUPERSEDED,
                NeedBasisKind.SUPERSEDED,
                "e_000005",
                "n_refresh",
            ),
            G7NeedPlan(
                "n_refresh",
                3,
                4,
                NeedStatus.ABANDONED,
                NeedBasisKind.ABANDONED,
                "e_000010",
                birth_index=2,
            ),
        ),
    )
    return _program(
        registry,
        stream,
        (
            _frame(0, lookup.query),
            _frame(refresh_at, refresh_source),
            _frame(abandon_at, abandon_source),
        ),
        actions,
        perturbation="topic_change",
        timing=plan,
        tool_results=(
            ScriptedToolResult(
                latency_ms=plan.service_ms[1] + 2,
                data={"nonce": lookup.result_a},
            ),
            ScriptedToolResult(
                latency_ms=plan.service_ms[4] + 2,
                data={"nonce": lookup.result_b},
            ),
        ),
        stale_by_beat={"b5": ("e_000011",)},
        need_lineage=need_lineage,
        delegate_provenance=provenance,
        require_g7_evidence=True,
    )


def _ambiguous_cancel_program(
    registry: AssetRegistry, stream: dict[str, object]
) -> ScenarioProgram:
    first, second = (_timer(registry, stream, index) for index in range(2))
    cancel = _text(registry, stream, 2)
    plan = _timing(stream, 5)
    second_at = sum(plan.service_ms[:2]) + 1
    cancel_at = second_at + sum(plan.service_ms[2:4]) + 1
    return _program(
        registry,
        stream,
        (
            _frame(0, first.instruction),
            _frame(second_at, second.instruction),
            _frame(cancel_at, cancel.text),
        ),
        (
            _schedule("e_000002", first),
            IdleAction(type="idle", reason=IdleReason.NO_TRIGGER, related_event_id=None),
            _schedule("e_000005", second),
            IdleAction(type="idle", reason=IdleReason.NO_TRIGGER, related_event_id=None),
            IdleAction(type="idle", reason=IdleReason.AMBIGUOUS, related_event_id=None),
        ),
        perturbation="timer_cancel_race",
        timing=plan,
    )


def _program(
    registry: AssetRegistry,
    stream: dict[str, object],
    frames: tuple[ScheduledSamplerFrame, ...],
    actions: tuple[Action, ...],
    *,
    perturbation: str,
    timing: TimingPlan | None = None,
    tool_results: tuple[ScriptedToolResult, ...] = (),
    stale_by_beat: dict[str, tuple[str, ...]] | None = None,
    response_warrants: tuple[BeatResponseWarrant, ...] = (),
    openings: tuple[BeatOpening, ...] | None = None,
    counterfactual: CounterfactualDeclaration | None = None,
    need_lineage=None,
    delegate_provenance=None,
    require_g7_evidence: bool = False,
) -> ScenarioProgram:
    count = len(actions)
    plan = _timing(stream, count) if timing is None else timing
    beats = tuple(f"b{index}" for index in range(count))
    stale = stale_by_beat or {}
    return ScenarioProgram.select(
        registry,
        split=Split.TRAIN,
        template_id=stream["template_asset_id"],
        asset_ids=tuple(stream["asset_ids"]),
        family=stream["family"],
        master_seed=stream["master_seed"],
        timing_plan=plan,
        frames=frames,
        actions=actions,
        tool_results=tool_results,
        beat_ids=beats,
        stale_results_by_beat=tuple(BeatStaleResults(beat, stale.get(beat, ())) for beat in beats),
        perturbations=(DeclaredPerturbation(perturbation),),
        counterfactual=counterfactual,
        response_warrants_by_beat=response_warrants,
        openings_by_beat=openings,
        need_lineage_by_beat=need_lineage,
        delegate_provenance_by_beat=delegate_provenance,
        require_g7_evidence=require_g7_evidence,
    )


def _timing(stream: dict[str, object], count: int) -> TimingPlan:
    return materialize_timing_plan(
        TimingSeed(Split.TRAIN, stream["master_seed"]),
        count,
    )


def _frame(at_ms: int, text: str, *, activity: str = "paused") -> ScheduledSamplerFrame:
    cursor = utf16_len(text)
    return ScheduledSamplerFrame(
        at_ms,
        canonicalize_tim_json(
            {
                "text": text,
                "selection_start": cursor,
                "selection_end": cursor,
                "is_composing": False,
                "input_type": "insertText",
                "activity": activity,
                "client_ts": at_ms,
            }
        ),
    )


def _span(event_id: str, source: str, selected: str) -> Span:
    start = source.index(selected)
    return Span(
        event_id=event_id,
        start_utf16=utf16_len(source[:start]),
        end_utf16=utf16_len(source[:start]) + utf16_len(selected),
        text=selected,
    )


def _schedule(event_id: str, timer: TimerAssetPayload) -> ScheduleAction:
    assert timer.interval_ms is not None and timer.message is not None
    return ScheduleAction(
        type="schedule",
        instruction=_span(event_id, timer.instruction, timer.instruction),
        interval_ms=timer.interval_ms,
        message=timer.message,
    )


def _delegate(event_id: str, source: str, query: str) -> DelegateAction:
    return DelegateAction(
        type="delegate",
        fact=_span(event_id, source, query),
        tool=ToolName.LOOKUP,
        args={"query": query},
    )


def _record(registry: AssetRegistry, stream: dict[str, object], index: int) -> AssetRecord:
    asset_id = stream["asset_ids"][index]
    return next(asset for asset in registry.pool(Split.TRAIN).assets if asset.asset_id == asset_id)


def _text(registry: AssetRegistry, stream: dict[str, object], index: int) -> TextAssetPayload:
    payload = _record(registry, stream, index).payload
    if not isinstance(payload, TextAssetPayload):
        raise ExecutableSentinelError("sentinel stream expected a text asset")
    return payload


def _timer(registry: AssetRegistry, stream: dict[str, object], index: int) -> TimerAssetPayload:
    payload = _record(registry, stream, index).payload
    if (
        not isinstance(payload, TimerAssetPayload)
        or payload.interval_ms is None
        or payload.message is None
    ):
        raise ExecutableSentinelError("sentinel stream expected a supported timer asset")
    return payload


def _lookup(registry: AssetRegistry, stream: dict[str, object], index: int) -> LookupAssetPayload:
    payload = _record(registry, stream, index).payload
    if not isinstance(payload, LookupAssetPayload):
        raise ExecutableSentinelError("sentinel stream expected a lookup asset")
    return payload


def _human_response(receipt: dict[str, object]) -> HumanAuthoredResponseAsset:
    request = receipt.get("neutral_request")
    if not isinstance(request, dict) or receipt.get("split") != Split.TRAIN.value:
        raise ExecutableSentinelError("sentinel response receipt is not TRAIN-bound")
    raw_contract = request.get("answer_contract")
    support = receipt.get("visible_support")
    if not isinstance(raw_contract, dict) or not isinstance(support, dict):
        raise ExecutableSentinelError("sentinel response receipt lacks visible support")
    contract = AnswerContract(
        response_kind=raw_contract["response_kind"],
        subject_id=raw_contract["subject_id"],
        support_event_ids=tuple(raw_contract["support_event_ids"]),
        required_answer_points=tuple(
            RequiredAnswerPoint(tuple(point["accepted_alternatives"]))
            for point in raw_contract["required_answer_points"]
        ),
        forbidden_claims=tuple(raw_contract["forbidden_claims"]),
        grounding_allowlist=tuple(raw_contract["grounding_allowlist"]),
    )
    return HumanAuthoredResponseAsset.create(
        ResponseDraftSpec(invitation=request["invitation"], answer_contract=contract),
        teacher_visible_prefix=request["teacher_visible_prefix"],
        response_text=receipt["candidate_response"],
        visible_support_by_event_id={contract.support_event_ids[0]: support["text"]},
    )


def _batch_cost(
    pricing: ModelPricing,
    *,
    input_tokens: int,
    requests: int,
    maximum_output_tokens: int,
) -> dict[str, object]:
    expected_output = requests * _EXPECTED_OUTPUT_TOKENS
    maximum_output = requests * maximum_output_tokens

    def cost(output_tokens: int) -> str:
        value = (
            pricing.batch_multiplier
            * (
                Decimal(input_tokens) * pricing.input_per_million
                + Decimal(output_tokens) * pricing.output_per_million
            )
            / _MILLION
        )
        return format(value.quantize(Decimal("0.000001")), "f")

    return {
        "approval_ceiling_usd": cost(maximum_output),
        "batch_multiplier": format(pricing.batch_multiplier, "f"),
        "expected_input_tokens": input_tokens,
        "expected_output_tokens": expected_output,
        "expected_usd": cost(expected_output),
        "maximum_output_tokens": maximum_output,
        "pricing_source_date": pricing.source_date,
    }


def _teacher_review(manifest: dict[str, object]) -> bytes:
    cost = manifest["cost_estimate"]
    assert isinstance(cost, dict)
    lines = [
        "# WP2-1 executable sentinel — provider approval packet",
        "",
        "The six TRAIN-sealed streams execute locally and expose the eight fixed D6 targets.",
        "This packet contains the exact Batch input, but no upload or provider call has occurred.",
        "",
        f"- Model: `{manifest['model']}` with `{manifest['reasoning_effort']}` reasoning",
        f"- Requests: `{manifest['request_count']}` in one Batch shard",
        f"- Input: `{manifest['input_path']}` (`{manifest['input_sha256']}`)",
        f"- Expected Batch cost: `${cost['expected_usd']}`",
        f"- Approval ceiling: `${cost['approval_ceiling_usd']}`",
        f"- Planned provider output: `{manifest['output_path']}`",
        "",
        (
            "A later continuation requires explicit owner authorization for this exact input "
            "and ceiling."
        ),
        "",
    ]
    return "\n".join(lines).encode()


def _teacher_packet_files(packet: SentinelTeacherPacket) -> dict[str, bytes]:
    payloads = {
        "REVIEW.md": packet.review_bytes,
        "teacher-plan.json": packet.manifest_bytes,
        packet.input_path: packet.input_jsonl,
    }
    checksums = "".join(
        f"{sha256(data).hexdigest()}  {name}\n" for name, data in sorted(payloads.items())
    ).encode("ascii")
    return {**payloads, "SHA256SUMS": checksums}


def _safe_relative_path(value: str) -> None:
    path = Path(value)
    if path.is_absolute() or not path.parts or ".." in path.parts or path.as_posix() != value:
        raise ExecutableSentinelError("sentinel packet path is unsafe")


def _digest(data: bytes) -> str:
    return f"sha256:{sha256(data).hexdigest()}"


def _canonical_object(data: bytes, label: str) -> dict[str, object]:
    canonical = data.removesuffix(b"\n")
    value = json.loads(canonical)
    if not isinstance(value, dict) or canonical_artifact_bytes(value) != canonical:
        raise ExecutableSentinelError(f"{label} must be canonical JSON")
    return value


def _object_list(value: object, label: str) -> tuple[dict[str, object], ...]:
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise ExecutableSentinelError(f"{label} must be an object list")
    return tuple(value)
