"""Offline Wave-0 checks for the timer boundaries added in tranche 2."""

from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

from im.assets import AssetRegistry, CorpusFamily, Split
from im.assets.model import (
    TextAssetPayload,
    TimerAssetPayload,
    artifact_digest,
    canonical_artifact_bytes,
)
from im.canonical_json import canonicalize_tim_json, parse_tim_json
from im.generation.g7_response_assets import HumanAuthoredResponseAsset, ResponseDraftSpec
from im.generation.ingestion import ScheduledSamplerFrame
from im.generation.oracle import ResponseWarrantKind
from im.generation.phase2_timer_wave0 import load_timer_wave0_inputs
from im.generation.publication import publish_directory_transaction
from im.generation.response_contracts import AnswerContract, RequiredAnswerPoint, ResponseKind
from im.generation.scenarios import (
    BeatOpening,
    BeatResponseWarrant,
    BeatStaleResults,
    CounterfactualDeclaration,
    DeclaredPerturbation,
    GeneratedScenario,
    ScenarioProgram,
    execute_scenario,
    validate_generated_scenario,
)
from im.generation.timing import TimingSeed, materialize_timing_plan
from im.schema.actions import IdleAction, IdleReason, RespondAction, ScheduleAction, Span
from im.schema.textspan import utf16_len

_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT = _ROOT / "review" / "phase2" / "timer-wave-0-boundaries"
_FAMILY = CorpusFamily.TIMER_CANCEL
_AMBIGUOUS_TEMPLATE = "a_064c3dae3e3abe4e7bd7a487"
_AMBIGUOUS_ASSET = "a_b2a1ca0b7e647ec77411d143"
_NEGATED_TEMPLATE = "a_9d4278e5ace95912cec8d008"
_NEGATED_ASSETS = ("a_b3d1cce13050d3f8d4215602", "a_f80089215d4c52eca01e39ab")
_UNSUPPORTED_TEMPLATE = "a_a240fd307b1c0cd3995e7157"
_UNSUPPORTED_ASSET = "a_9bab50b82eb4b499558fdaba"
_ONE_SHOT_ASSET = "a_bf812f9b9f149490915e6de0"
_SUPPORTED_ASSETS = ("a_067f59d6c56633412a0d45b4", "a_11d7f848364801c6724c9d75")
_CLARIFICATION = "Which reminder should I cancel: open the fern ledger or sweep the quartz step?"
_UNRESOLVED_CONTEXT = "Both reminders are visible without a selected reference point."
_CLOCK_LIMITATION = (
    "I can only create recurring interval reminders, not reminders at a specific clock time."
)
_ONE_SHOT_INSTRUCTION = "Set a single reminder forty minutes from now to close the lilac case."
_ONE_SHOT_LIMITATION = "I can only create recurring interval reminders, not single reminders."
_REVIEWER_ID = "user:phase2-owner"
_REVIEWED_AT = "2026-07-21T00:00:00Z"


@dataclass(frozen=True, slots=True)
class TimerBoundaryInputs:
    """Split, assets, and approved response texts for one timer-boundary pack.

    The behaviour, frame construction, action sequence, and invariants are the module's and
    are not parameterized. This carries only what differs between splits: which sealed pool
    the assets come from, which assets, and which approved response texts the two limitation
    branches and the clarification branch use.
    """

    split: Split
    ambiguous_template: str
    ambiguous_asset: str
    negated_template: str
    negated_assets: tuple[str, ...]
    unsupported_template: str
    unsupported_asset: str
    one_shot_asset: str
    supported_assets: tuple[str, ...]
    clarification: str
    unresolved_context: str
    clock_limitation: str
    one_shot_instruction: str
    one_shot_limitation: str


TRAIN_TIMER_BOUNDARY_INPUTS = TimerBoundaryInputs(
    split=Split.TRAIN,
    ambiguous_template=_AMBIGUOUS_TEMPLATE,
    ambiguous_asset=_AMBIGUOUS_ASSET,
    negated_template=_NEGATED_TEMPLATE,
    negated_assets=_NEGATED_ASSETS,
    unsupported_template=_UNSUPPORTED_TEMPLATE,
    unsupported_asset=_UNSUPPORTED_ASSET,
    one_shot_asset=_ONE_SHOT_ASSET,
    supported_assets=_SUPPORTED_ASSETS,
    clarification=_CLARIFICATION,
    unresolved_context=_UNRESOLVED_CONTEXT,
    clock_limitation=_CLOCK_LIMITATION,
    one_shot_instruction=_ONE_SHOT_INSTRUCTION,
    one_shot_limitation=_ONE_SHOT_LIMITATION,
)


class TimerWave0BoundaryError(ValueError):
    """The fixed boundary inventory or its mechanical evidence drifted."""


@dataclass(frozen=True, slots=True)
class BoundaryProgram:
    logical_stream_id: str
    branch: str
    program: ScenarioProgram


@dataclass(frozen=True, slots=True)
class ExecutedBoundary:
    logical_stream_id: str
    branch: str
    generated: GeneratedScenario


def build_timer_wave0_boundary_programs(
    registry: AssetRegistry,
    inputs: TimerBoundaryInputs = TRAIN_TIMER_BOUNDARY_INPUTS,
) -> tuple[BoundaryProgram, ...]:
    """Build the six sealed boundary scenarios required by the owner review."""
    active, yielded = _ambiguous_twins(registry, inputs)
    return (
        BoundaryProgram("ambiguous-cancel-active", "ambiguous_active", active),
        BoundaryProgram("ambiguous-cancel-yielded", "ambiguous_yielded", yielded),
        *(
            BoundaryProgram(
                f"negated-restraint-{index}",
                "negated_no_equivalent_timer",
                _single_boundary_program(
                    registry,
                    inputs,
                    template_id=inputs.negated_template,
                    asset_id=asset_id,
                    master_seed=f"phase2-timer-wave0:negated:{index}",
                    action=IdleAction(
                        type="idle", reason=IdleReason.NO_TRIGGER, related_event_id=None
                    ),
                ),
            )
            for index, asset_id in enumerate(inputs.negated_assets, 1)
        ),
        BoundaryProgram(
            "unsupported-absolute-time",
            "unsupported_not_approximated",
            _single_boundary_program(
                registry,
                inputs,
                template_id=inputs.unsupported_template,
                asset_id=inputs.unsupported_asset,
                master_seed="phase2-timer-wave0:unsupported:absolute",
                action=RespondAction(
                    type="respond", reply_to_event_id="e_000002", text=inputs.clock_limitation
                ),
                response_warrant=ResponseWarrantKind.UNSUPPORTED_LIMITATION,
            ),
        ),
        BoundaryProgram(
            "unsupported-one-shot",
            "unsupported_not_approximated",
            _single_boundary_program(
                registry,
                inputs,
                template_id=inputs.unsupported_template,
                asset_id=inputs.one_shot_asset,
                master_seed="phase2-timer-wave0:unsupported:one-shot",
                action=RespondAction(
                    type="respond", reply_to_event_id="e_000002", text=inputs.one_shot_limitation
                ),
                response_warrant=ResponseWarrantKind.UNSUPPORTED_LIMITATION,
            ),
        ),
    )


async def execute_timer_wave0_boundaries(
    programs: tuple[BoundaryProgram, ...],
    *,
    directory: Path,
    repository_root: Path = _ROOT,
) -> tuple[ExecutedBoundary, ...]:
    if len(programs) != 6 or len({item.logical_stream_id for item in programs}) != 6:
        raise TimerWave0BoundaryError("boundary inventory must contain six unique streams")
    results = []
    for item in programs:
        generated = await execute_scenario(
            item.program,
            session_id=f"timer-wave0-{item.logical_stream_id}",
            directory=directory / item.logical_stream_id,
            repository_root=repository_root,
        )
        validate_generated_scenario(generated)
        results.append(ExecutedBoundary(item.logical_stream_id, item.branch, generated))
    executed = tuple(results)
    _validate_invariants(executed)
    return executed


def build_timer_wave0_boundary_packet(
    executed: tuple[ExecutedBoundary, ...],
    *,
    approved_root: Path = _ROOT / "review" / "phase1" / "approved",
) -> dict[str, bytes]:
    _validate_invariants(executed)
    registry_bytes = (approved_root / "registry.jsonl").read_bytes()
    train_seal_bytes = (approved_root / "train-seal.json").read_bytes()
    rows = [_review_row(item) for item in executed]
    manifest = {
        "api_call_performed": False,
        "format_version": 1,
        "kind": "phase2-timer-wave0-boundary-packet",
        "source_registry_sha256": _digest(registry_bytes),
        "train_seal_sha256": _digest(train_seal_bytes),
        "stream_count": len(rows),
        "streams": rows,
        "one_shot_status": "owner approved, TRAIN sealed, and included in this packet",
        "response_candidate_ordinals": [2, 3, 4],
    }
    responses = build_timer_wave0_response_records()
    files = {
        "README.md": _readme(rows).encode("utf-8"),
        "manifest.json": canonical_artifact_bytes(manifest),
        "response-assets.json": canonical_artifact_bytes(
            {
                "format_version": 1,
                "kind": "phase2-approved-train-response-records",
                "records": responses,
            }
        ),
        "review-rows.json": canonical_artifact_bytes({"format_version": 1, "rows": rows}),
    }
    return {**files, "SHA256SUMS": _checksums(files)}


async def materialize_timer_wave0_boundary_packet(
    output: Path = DEFAULT_OUTPUT,
    *,
    repository_root: Path = _ROOT,
) -> dict[str, bytes]:
    registry = load_timer_wave0_inputs()
    programs = build_timer_wave0_boundary_programs(registry)
    with TemporaryDirectory(prefix="phase2-timer-wave0-boundaries-") as temporary:
        executed = await execute_timer_wave0_boundaries(
            programs,
            directory=Path(temporary),
            repository_root=repository_root,
        )
        files = build_timer_wave0_boundary_packet(executed)
    publish_directory_transaction(output, files)
    return files


def build_timer_wave0_response_records() -> list[dict[str, object]]:
    """Build owner-approved TRAIN response candidates 2–4 through the existing schema."""
    ambiguous_support = {
        "e_000002": "Remind me every thirty-seven minutes to open the fern ledger.",
        "e_000005": "Remind me every thirty-one minutes to sweep the quartz step.",
        "e_000008": _UNRESOLVED_CONTEXT,
        "e_000009": "Cancel the reminder next to it.",
    }
    specs = (
        (
            2,
            "timer-ambiguous-cancel",
            "ambiguous-cancel-yielded",
            "Cancel the reminder next to it.",
            ambiguous_support,
            ResponseKind.AMBIGUITY_CLARIFICATION,
            (
                RequiredAnswerPoint(("open the fern ledger",)),
                RequiredAnswerPoint(("sweep the quartz step",)),
            ),
            ("Both reminders were cancelled.", "A reminder was selected."),
            _CLARIFICATION,
        ),
        (
            3,
            "timer-unsupported-absolute-time",
            "unsupported-absolute-time",
            "Remind me at 6:40 PM to carry the cedar folder.",
            {"e_000002": "Remind me at 6:40 PM to carry the cedar folder."},
            ResponseKind.UNSUPPORTED_FEATURE_LIMITATION,
            (
                RequiredAnswerPoint(("recurring interval reminders",)),
                RequiredAnswerPoint(("specific clock time",)),
            ),
            ("I set a reminder.", "I scheduled a reminder."),
            _CLOCK_LIMITATION,
        ),
        (
            4,
            "timer-unsupported-one-shot",
            "unsupported-one-shot",
            _ONE_SHOT_INSTRUCTION,
            {"e_000002": _ONE_SHOT_INSTRUCTION},
            ResponseKind.UNSUPPORTED_FEATURE_LIMITATION,
            (
                RequiredAnswerPoint(("recurring interval reminders",)),
                RequiredAnswerPoint(("single reminders",)),
            ),
            ("I set a reminder.", "I scheduled a reminder."),
            _ONE_SHOT_LIMITATION,
        ),
    )
    return [
        _response_record(
            ordinal,
            subject_id,
            stream_id,
            invitation,
            support,
            kind,
            points,
            forbidden,
            response,
        )
        for (
            ordinal,
            subject_id,
            stream_id,
            invitation,
            support,
            kind,
            points,
            forbidden,
            response,
        ) in specs
    ]


def _response_record(
    ordinal: int,
    subject_id: str,
    stream_id: str,
    invitation: str,
    support: dict[str, str],
    kind: ResponseKind,
    points: tuple[RequiredAnswerPoint, ...],
    forbidden: tuple[str, ...],
    response: str,
) -> dict[str, object]:
    contract = AnswerContract(
        response_kind=kind,
        subject_id=subject_id,
        support_event_ids=tuple(support),
        required_answer_points=points,
        forbidden_claims=forbidden,
    )
    visible_prefix = "\n".join(support.values())
    asset = HumanAuthoredResponseAsset.create(
        ResponseDraftSpec(invitation=invitation, answer_contract=contract),
        teacher_visible_prefix=visible_prefix,
        response_text=response,
        visible_support_by_event_id=support,
    )
    claims = {
        "author_origin": "human_authored",
        "candidate_ordinal": ordinal,
        "candidate_response": asset.response_text,
        "neutral_request": json.loads(asset.serialized_neutral_request),
        "neutral_request_sha256": asset.serialized_neutral_request_sha256,
        "scenario_binding": {"logical_stream_id": stream_id},
        "split": Split.TRAIN.value,
        "subject_id": subject_id,
        "visible_support": support,
    }
    return {
        "format_version": 1,
        "kind": "wp2-0a-approved-train-response",
        **claims,
        "content_sha256": artifact_digest(claims),
        "review": {
            "decision": "approved",
            "reviewed_at_utc": _REVIEWED_AT,
            "reviewer_id": _REVIEWER_ID,
        },
    }


def _ambiguous_twins(
    registry: AssetRegistry, inputs: TimerBoundaryInputs
) -> tuple[ScenarioProgram, ScenarioProgram]:
    timers = tuple(_timer(registry, asset_id, inputs.split) for asset_id in inputs.supported_assets)
    cancel = _text(registry, inputs.ambiguous_asset, inputs.split)
    seed = "phase2-timer-wave0:ambiguous-cancel"
    plan = materialize_timing_plan(TimingSeed(inputs.split, seed), 6)
    second_at = sum(plan.service_ms[:2]) + 1
    context_at = second_at + sum(plan.service_ms[2:4]) + 1
    cancel_at = context_at + plan.service_ms[4] + 1
    frames = (
        _frame(0, timers[0].instruction),
        _frame(second_at, timers[1].instruction),
        _frame(context_at, inputs.unresolved_context),
        _frame(cancel_at, cancel.text, activity="active"),
    )
    common_actions = (
        _schedule("e_000002", timers[0]),
        _idle(),
        _schedule("e_000005", timers[1]),
        _idle(),
        _idle(),
    )
    group = "phase2-timer-wave0-ambiguous-cancel"
    active = _program(
        registry,
        inputs,
        template_id=inputs.ambiguous_template,
        asset_ids=(*inputs.supported_assets, inputs.ambiguous_asset),
        master_seed=seed,
        timing_plan=plan,
        frames=frames,
        actions=(
            *common_actions,
            IdleAction(type="idle", reason=IdleReason.AMBIGUOUS, related_event_id=None),
        ),
        counterfactual=_twin(group, "active"),
    )
    yielded = _program(
        registry,
        inputs,
        template_id=inputs.ambiguous_template,
        asset_ids=(*inputs.supported_assets, inputs.ambiguous_asset),
        master_seed=seed,
        timing_plan=plan,
        frames=(*frames[:-1], _frame(cancel_at, cancel.text)),
        actions=(
            *common_actions,
            RespondAction(type="respond", reply_to_event_id="e_000009", text=inputs.clarification),
        ),
        counterfactual=_twin(group, "yielded"),
        warrant=BeatResponseWarrant("b5", "e_000009", ResponseWarrantKind.AMBIGUITY_CLARIFICATION),
    )
    return active, yielded


def _single_boundary_program(
    registry: AssetRegistry,
    inputs: TimerBoundaryInputs = TRAIN_TIMER_BOUNDARY_INPUTS,
    *,
    template_id: str,
    asset_id: str,
    master_seed: str,
    action: IdleAction | RespondAction,
    response_warrant: ResponseWarrantKind | None = None,
) -> ScenarioProgram:
    asset = _timer(registry, asset_id, inputs.split)
    warrant = (
        None
        if response_warrant is None
        else BeatResponseWarrant("b0", "e_000002", response_warrant)
    )
    return _program(
        registry,
        inputs,
        template_id=template_id,
        asset_ids=(asset_id,),
        master_seed=master_seed,
        timing_plan=materialize_timing_plan(TimingSeed(inputs.split, master_seed), 1),
        frames=(_frame(0, asset.instruction),),
        actions=(action,),
        warrant=warrant,
    )


def _program(
    registry: AssetRegistry,
    inputs: TimerBoundaryInputs = TRAIN_TIMER_BOUNDARY_INPUTS,
    *,
    template_id: str,
    asset_ids: tuple[str, ...],
    master_seed: str,
    timing_plan,
    frames: tuple[ScheduledSamplerFrame, ...],
    actions: tuple[object, ...],
    counterfactual: CounterfactualDeclaration | None = None,
    warrant: BeatResponseWarrant | None = None,
) -> ScenarioProgram:
    beats = tuple(f"b{index}" for index in range(len(actions)))
    response_warrants = () if warrant is None else (warrant,)
    return ScenarioProgram.select(
        registry,
        split=inputs.split,
        template_id=template_id,
        asset_ids=asset_ids,
        family=_FAMILY,
        master_seed=master_seed,
        timing_plan=timing_plan,
        frames=frames,
        actions=actions,
        tool_results=(),
        beat_ids=beats,
        stale_results_by_beat=tuple(BeatStaleResults(beat, ()) for beat in beats),
        perturbations=(DeclaredPerturbation("floor_opening"),) if counterfactual else (),
        counterfactual=counterfactual,
        response_warrants_by_beat=response_warrants,
        openings_by_beat=(BeatOpening(warrant.beat_id, warrant.snapshot_event_id),)
        if warrant
        else None,
    )


def _validate_invariants(executed: tuple[ExecutedBoundary, ...]) -> None:
    if len(executed) != 6:
        raise TimerWave0BoundaryError("six executed boundary streams are required")
    for item in executed:
        boundary = item.generated.decision_boundaries[-1]
        action = item.generated.program.actions[-1]
        decision = item.generated.sidecar.decisions[-1]
        snapshot = boundary.license_view.latest_snapshot
        active_timers = boundary.license_view.active_timers
        if item.branch.startswith("ambiguous_"):
            frames = tuple(
                parse_tim_json(frame.raw_bytes) for frame in item.generated.program.frames
            )
            if len(active_timers) != 2 or snapshot is None:
                raise TimerWave0BoundaryError("ambiguous cancel must retain two active timers")
            if len(frames) != 4 or frames[2].get("text") != _UNRESOLVED_CONTEXT:
                raise TimerWave0BoundaryError("ambiguous cancel gained a resolving context anchor")
            if snapshot.text != "Cancel the reminder next to it.":
                raise TimerWave0BoundaryError("ambiguous cancel seed was not rendered verbatim")
        elif active_timers:
            raise TimerWave0BoundaryError(f"{item.logical_stream_id} gained an active timer")
        match item.branch:
            case "ambiguous_active":
                if (
                    snapshot is None
                    or snapshot.activity.value != "active"
                    or action
                    != IdleAction(type="idle", reason=IdleReason.AMBIGUOUS, related_event_id=None)
                    or decision.response_warrant_kind is not None
                ):
                    raise TimerWave0BoundaryError("active ambiguity target drifted")
            case "ambiguous_yielded":
                if (
                    snapshot is None
                    or snapshot.activity.value != "paused"
                    or action
                    != RespondAction(
                        type="respond",
                        reply_to_event_id=snapshot.event_id,
                        text=_CLARIFICATION,
                    )
                    or decision.response_warrant_kind
                    is not ResponseWarrantKind.AMBIGUITY_CLARIFICATION
                    or decision.floor_open is not True
                ):
                    raise TimerWave0BoundaryError("yielded ambiguity target drifted")
            case "negated_no_equivalent_timer":
                if action != _idle():
                    raise TimerWave0BoundaryError(
                        "direct negation no longer resolves to no-trigger"
                    )
            case "unsupported_not_approximated":
                limitation = (
                    _ONE_SHOT_LIMITATION
                    if item.logical_stream_id == "unsupported-one-shot"
                    else _CLOCK_LIMITATION
                )
                if (
                    snapshot is None
                    or action
                    != RespondAction(
                        type="respond",
                        reply_to_event_id=snapshot.event_id,
                        text=limitation,
                    )
                    or decision.response_warrant_kind
                    is not ResponseWarrantKind.UNSUPPORTED_LIMITATION
                    or decision.floor_open is not True
                    or any(
                        isinstance(candidate, ScheduleAction)
                        for candidate in item.generated.program.actions
                    )
                ):
                    raise TimerWave0BoundaryError(
                        "unsupported request was approximated or mislabeled"
                    )
                if (
                    item.logical_stream_id == "unsupported-one-shot"
                    and snapshot.text != _ONE_SHOT_INSTRUCTION
                ):
                    raise TimerWave0BoundaryError("one-shot wording no longer preserves 'a single'")
            case _:
                raise TimerWave0BoundaryError(f"unknown boundary branch {item.branch}")


def _review_row(item: ExecutedBoundary) -> dict[str, object]:
    generated = item.generated
    boundary = generated.decision_boundaries[-1]
    decision = generated.sidecar.decisions[-1]
    snapshot = boundary.license_view.latest_snapshot
    return {
        "action_sequence": [action.model_dump(mode="json") for action in generated.program.actions],
        "active_timer_count": len(boundary.license_view.active_timers),
        "active_timers": [
            {
                "interval_ms": timer.interval_ms,
                "message": timer.message,
                "timer_id": timer.timer_id,
            }
            for timer in boundary.license_view.active_timers
        ],
        "asset_ids": list(generated.program.asset_ids),
        "branch": item.branch,
        "floor_open": decision.floor_open,
        "floor_owned": decision.floor_owned,
        "frames": [
            {"at_ms": frame.at_ms, "snapshot": parse_tim_json(frame.raw_bytes)}
            for frame in generated.program.frames
        ],
        "input_text": None if snapshot is None else snapshot.text,
        "logical_stream_id": item.logical_stream_id,
        "oracle_action": generated.program.actions[-1].model_dump(mode="json"),
        "policy_prefix_sha256": _digest(boundary.policy_bytes),
        "response_warrant_kind": (
            None if decision.response_warrant_kind is None else decision.response_warrant_kind.value
        ),
        "response_warrant_snapshot_event_id": decision.response_warrant_snapshot_event_id,
        "response_warrant_snapshot_text": decision.response_warrant_snapshot_text,
        "snapshot_activity": None if snapshot is None else snapshot.activity.value,
        "stream_sha256": generated.stream.sha256,
        "template_id": generated.program.template.asset_id,
    }


def _timer(
    registry: AssetRegistry, asset_id: str, split: Split = Split.TRAIN
) -> TimerAssetPayload:
    payload = _asset_payload(registry, asset_id, split)
    if not isinstance(payload, TimerAssetPayload):
        raise TimerWave0BoundaryError(f"{asset_id} is not a timer asset")
    return payload


def _text(
    registry: AssetRegistry, asset_id: str, split: Split = Split.TRAIN
) -> TextAssetPayload:
    payload = _asset_payload(registry, asset_id, split)
    if not isinstance(payload, TextAssetPayload):
        raise TimerWave0BoundaryError(f"{asset_id} is not a text asset")
    return payload


def _asset_payload(registry: AssetRegistry, asset_id: str, split: Split = Split.TRAIN):
    for asset in registry.pool(split).assets:
        if asset.asset_id == asset_id and registry.is_approved(asset):
            return asset.payload
    raise TimerWave0BoundaryError(
        f"{asset_id} is not an approved {split.value.upper()} asset"
    )


def _schedule(event_id: str, timer: TimerAssetPayload) -> ScheduleAction:
    assert timer.interval_ms is not None and timer.message is not None
    return ScheduleAction(
        type="schedule",
        instruction=Span(
            event_id=event_id,
            start_utf16=0,
            end_utf16=utf16_len(timer.instruction),
            text=timer.instruction,
        ),
        interval_ms=timer.interval_ms,
        message=timer.message,
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


def _idle() -> IdleAction:
    return IdleAction(type="idle", reason=IdleReason.NO_TRIGGER, related_event_id=None)


def _twin(group_id: str, member_id: str) -> CounterfactualDeclaration:
    return CounterfactualDeclaration(
        kind="twin",
        group_id=group_id,
        member_id=member_id,
        member_ids=("active", "yielded"),
        flipped_perturbation="floor_opening",
    )


def _readme(rows: list[dict[str, object]]) -> str:
    rendered = [
        "# Timer Wave-0 tranche-2 boundary review",
        "",
        f"Review exactly {len(rows)} final boundary decisions. No provider call was made.",
        "",
    ]
    for row in rows:
        rendered.extend(
            (
                f"## {row['logical_stream_id']}",
                "",
                f"- Input: `{row['input_text']}`",
                f"- Active timers: {row['active_timer_count']}",
                f"- Oracle: `{json.dumps(row['oracle_action'], separators=(',', ':'))}`",
                "",
            )
        )
    rendered.extend(
        (
            "The owner-approved one-shot is checked without approximation.",
            "Response candidates 2–4 are registered in `response-assets.json`.",
            "",
        )
    )
    return "\n".join(rendered)


def _checksums(files: dict[str, bytes]) -> bytes:
    return "".join(f"{sha256(files[name]).hexdigest()}  {name}\n" for name in sorted(files)).encode(
        "ascii"
    )


def _digest(data: bytes) -> str:
    return f"sha256:{sha256(data).hexdigest()}"
