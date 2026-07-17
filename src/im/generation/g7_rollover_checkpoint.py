"""Real later-checkpoint parents for the three G7 rollover shapes."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from im.assets.model import (
    AssetRecord,
    CorpusFamily,
    LookupAssetPayload,
    Split,
    TextAssetPayload,
    TimerAssetPayload,
    TimerForm,
)
from im.assets.registry import AssetBundle, AssetRegistry
from im.canonical_json import canonicalize_tim_json
from im.config import RuntimeConfig
from im.generation.corpus_segments import CorpusSegmentCandidate
from im.generation.g7_cancel_plan import G7CancelPlan
from im.generation.g7_need_plan import G7NeedPlan, build_g7_need_evidence
from im.generation.ingestion import ScheduledSamplerFrame
from im.generation.need_lineage import (
    CancelResolutionEvidence,
    NeedBasisKind,
    NeedStatus,
)
from im.generation.oracle import BeatOpening
from im.generation.scenarios import (
    BeatStaleResults,
    DeclaredPerturbation,
    GeneratedScenario,
    ScenarioProgram,
    execute_scenario,
    select_approved_scenario_inputs,
    validate_generated_scenario,
)
from im.generation.timer_instruction_semantics import (
    TimerInstructionSemanticsV1,
    validate_timer_asset_semantics_v1,
)
from im.generation.timing import TimingSeed, materialize_timing_plan
from im.schema.actions import (
    CancelAction,
    CancelTimerTarget,
    DelegateAction,
    IdleAction,
    IdleReason,
    IntegrateAction,
    MarkAction,
    NudgeAction,
    ScheduleAction,
    SkipAction,
    SkipReason,
    Span,
)
from im.schema.common import ToolName
from im.schema.textspan import utf16_len
from im.tools import ScriptedToolResult

__all__ = (
    "G7_ROLLOVER_CHECKPOINT_SHAPES",
    "G7RolloverCheckpointEntry",
    "build_g7_rollover_checkpoint_catalog",
)


G7_ROLLOVER_CHECKPOINT_SHAPES = (
    ("g7-checkpoint-rollover-a", "14I+M+G+S"),
    ("g7-checkpoint-rollover-b", "13I+M+G+S"),
    ("g7-checkpoint-rollover-c", "13I+D+C+2N"),
)

_FRAME_GAP_MS = 5_000
_LONG_PENDING_MS = 20_000_000
_ROLLOVER_CONFIG = RuntimeConfig(context_budget_tokens=6_000)
_PRESSURE = "The notebook remains open beside the atlas. " * 95


@dataclass(frozen=True, slots=True)
class G7RolloverCheckpointEntry:
    """One complete production parent and its exact later checkpoint view."""

    shape_id: str
    parent: GeneratedScenario
    candidate: CorpusSegmentCandidate
    action_vector: str

    def __post_init__(self) -> None:
        if self.candidate.parent is not self.parent:
            raise ValueError("checkpoint candidate must retain its complete parent")
        if self.candidate.shape_id != self.shape_id:
            raise ValueError("checkpoint candidate and shape disagree")
        validate_generated_scenario(self.parent)


def _frame(at_ms: int, text: str) -> ScheduledSamplerFrame:
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
                "activity": "paused",
                "client_ts": at_ms,
            }
        ),
    )


def _span(event_id: str, text: str, selected: str, *, last: bool = False) -> Span:
    start = text.rindex(selected) if last else text.index(selected)
    return Span(
        event_id=event_id,
        start_utf16=utf16_len(text[:start]),
        end_utf16=utf16_len(text[:start]) + utf16_len(selected),
        text=selected,
    )


def _idle(
    reason: IdleReason = IdleReason.NO_TRIGGER, related_event_id: str | None = None
) -> IdleAction:
    return IdleAction(type="idle", reason=reason, related_event_id=related_event_id)


def _delegate(event_id: str, source: str, query: str) -> DelegateAction:
    return DelegateAction(
        type="delegate",
        fact=_span(event_id, source, query),
        tool=ToolName.LOOKUP,
        args={"query": query},
    )


def _schedule(
    event_id: str,
    source: str,
    timer: TimerAssetPayload,
    semantics: TimerInstructionSemanticsV1,
) -> ScheduleAction:
    return ScheduleAction(
        type="schedule",
        instruction=_span(event_id, source, timer.instruction),
        interval_ms=semantics.interval_ms,
        message=semantics.message,
    )


def _pressure_source(prefix: str) -> str:
    available = 4_096 - len(prefix.encode("utf-8")) - 1
    if available <= 0:
        raise ValueError("rollover pressure prefix exceeds the sampler limit")
    return f"{prefix}\n{_PRESSURE.encode('utf-8')[:available].decode('utf-8')}"


def _inputs(
    registry: AssetRegistry,
) -> tuple[
    AssetBundle,
    AssetRecord,
    LookupAssetPayload,
    LookupAssetPayload,
    AssetRecord,
    TimerAssetPayload,
    TimerAssetPayload,
]:
    pool = registry.pool(Split.TEST)
    template = next(item for item in pool.templates if CorpusFamily.ROLLOVER in item.coverage)
    rollover_lookup = next(
        item
        for item in pool.assets
        if CorpusFamily.ROLLOVER in item.coverage and isinstance(item.payload, LookupAssetPayload)
    )
    stale_lookup = next(
        item
        for item in pool.assets
        if isinstance(item.payload, LookupAssetPayload)
        and item.asset_id != rollover_lookup.asset_id
    )
    mark = next(
        item
        for item in pool.assets
        if CorpusFamily.MARK_POSITIVE in item.coverage
        and isinstance(item.payload, TextAssetPayload)
    )
    timer_assets = tuple(
        item
        for item in pool.assets
        if isinstance(item.payload, TimerAssetPayload) and item.payload.form is TimerForm.SUPPORTED
    )
    if len(timer_assets) < 2:
        raise ValueError("rollover checkpoint requires two supported TEST timers")
    first_timer_asset, second_timer_asset = timer_assets[:2]
    bundle, selected_template = select_approved_scenario_inputs(
        registry,
        split=Split.TEST,
        template_id=template.asset_id,
        asset_ids=tuple(
            sorted(
                (
                    rollover_lookup.asset_id,
                    stale_lookup.asset_id,
                    mark.asset_id,
                    first_timer_asset.asset_id,
                    second_timer_asset.asset_id,
                )
            )
        ),
    )
    return (
        bundle,
        selected_template,
        rollover_lookup.payload,
        stale_lookup.payload,
        mark,
        first_timer_asset.payload,
        second_timer_asset.payload,
    )


def _program(
    bundle: AssetBundle,
    template: AssetRecord,
    master_seed: str,
    shape_id: str,
    frames: tuple[ScheduledSamplerFrame, ...],
    actions: tuple[object, ...],
    *,
    tool_results: tuple[ScriptedToolResult, ...] = (),
    stale: tuple[tuple[int, tuple[str, ...]], ...] = (),
    openings: tuple[tuple[int, str], ...] = (),
    need_plans: tuple[G7NeedPlan, ...],
) -> ScenarioProgram:
    timing = materialize_timing_plan(
        TimingSeed(Split.TEST, f"g7-rollover-checkpoint-v1:{shape_id}:{master_seed}"),
        len(actions),
    )
    beats = tuple(f"b{index}" for index in range(len(actions)))
    stale_by_index = dict(stale)
    need_lineage, delegate_provenance = build_g7_need_evidence(beats, actions, need_plans)
    cancel_evidence = tuple(
        CancelResolutionEvidence(
            beat_id=beats[index],
            basis_event_id=action.instruction.event_id,
            resolved_timer_ids=(action.target.timer_id,),
        )
        for index, action in enumerate(actions)
        if isinstance(action, CancelAction) and isinstance(action.target, CancelTimerTarget)
    )
    return ScenarioProgram(
        bundle=bundle,
        template=template,
        family=CorpusFamily.ROLLOVER,
        master_seed=master_seed,
        timing_plan=timing,
        frames=frames,
        actions=actions,
        tool_results=tool_results,
        beat_ids=beats,
        stale_results_by_beat=tuple(
            BeatStaleResults(beat, stale_by_index.get(index, ()))
            for index, beat in enumerate(beats)
        ),
        perturbations=(DeclaredPerturbation("state_checkpoint"),),
        config=_ROLLOVER_CONFIG,
        openings_by_beat=tuple(BeatOpening(beats[index], event_id) for index, event_id in openings),
        need_lineage_by_beat=need_lineage,
        delegate_provenance_by_beat=delegate_provenance,
        cancel_resolution_evidence_by_beat=cancel_evidence,
        require_g7_evidence=True,
    )


def _rollover_program(
    registry: AssetRegistry, master_seed: str, shape_id: str, idle_count: int
) -> ScenarioProgram:
    bundle, template, primary, stale, mark_asset, _first_timer, _second_timer = _inputs(registry)
    mark = mark_asset.payload
    if not isinstance(mark, TextAssetPayload):  # narrowed by _inputs.
        raise RuntimeError("rollover mark ledger drifted")
    control = mark.text
    target = next(
        (value for value in mark_asset.protected_values if value in control), control.split()[0]
    )
    primary_source = _pressure_source(primary.query)
    stale_source = _pressure_source(stale.query)
    frames = [
        _frame(0, primary_source),
        _frame(_FRAME_GAP_MS, stale_source),
        _frame(2 * _FRAME_GAP_MS, _pressure_source("The quiet notebook page")),
        _frame(3 * _FRAME_GAP_MS, _pressure_source("The atlas stays open")),
    ]
    candidate_start = 4 * _FRAME_GAP_MS
    for index in range(idle_count):
        frames.append(_frame(candidate_start + index * _FRAME_GAP_MS, control))
    target_at = candidate_start + idle_count * _FRAME_GAP_MS
    target_source = (
        f"{control}\nA later line in the notebook mentions {target}.\n"
        f"Never mind, {stale.query} is no longer relevant."
    )
    frames.append(_frame(target_at, target_source))

    mark_index = 4 + idle_count
    timing = materialize_timing_plan(
        TimingSeed(Split.TEST, f"g7-rollover-checkpoint-v1:{shape_id}:{master_seed}"),
        mark_index + 4,
    )
    due_at = target_at + timing.service_ms[mark_index] - 1
    primary_result = "e_000025" if idle_count == 13 else "e_000024"
    stale_result = "e_000026" if idle_count == 13 else "e_000025"
    target_event = "e_000024" if idle_count == 13 else "e_000023"
    actions = (
        _delegate("e_000002", primary_source, primary.query),
        _delegate("e_000005", stale_source, stale.query),
        _idle(IdleReason.AWAITING_TOOL, "e_000002"),
        _idle(IdleReason.AWAITING_TOOL, "e_000002"),
        *(_idle(IdleReason.AWAITING_TOOL, "e_000002") for _ in range(idle_count)),
        MarkAction(
            type="mark",
            instruction=_span("e_000011", control, control),
            target=_span(target_event, target_source, target, last=True),
        ),
        IntegrateAction(type="integrate", result_event_id=primary_result, text=primary.result_a),
        SkipAction(type="skip", target_event_id=stale_result, reason=SkipReason.STALE_TOOL_RESULT),
        _idle(),
    )
    program = _program(
        bundle,
        template,
        master_seed,
        shape_id,
        tuple(frames),
        actions,
        tool_results=(
            ScriptedToolResult(
                latency_ms=due_at - timing.service_ms[0], data={"nonce": primary.result_a}
            ),
            ScriptedToolResult(
                latency_ms=due_at - (_FRAME_GAP_MS + timing.service_ms[1]),
                data={"nonce": stale.result_a},
            ),
        ),
        stale=((mark_index + 2, (stale_result,)),),
        openings=((mark_index + 1, target_event),),
        need_plans=(
            G7NeedPlan(
                "n_rollover_primary",
                0,
                terminal_index=mark_index + 2,
                terminal_status=NeedStatus.SATISFIED,
                terminal_basis_kind=NeedBasisKind.RESULT,
                terminal_basis_event_id=primary_result,
            ),
            G7NeedPlan(
                "n_rollover_stale",
                1,
                terminal_index=mark_index + 2,
                terminal_status=NeedStatus.ABANDONED,
                terminal_basis_kind=NeedBasisKind.ABANDONED,
                terminal_basis_event_id=target_event,
            ),
        ),
    )
    if program.timing_plan != timing:
        raise RuntimeError("rollover timing ledger drifted")
    return program


def _timer_program(registry: AssetRegistry, master_seed: str) -> ScenarioProgram:
    shape_id = "g7-checkpoint-rollover-c"
    bundle, template, _primary, followup, mark_asset, first_timer, recurring_timer = _inputs(
        registry
    )
    first_semantics = _timer_semantics(first_timer)
    recurring_semantics = _timer_semantics(recurring_timer)
    mark = mark_asset.payload
    if not isinstance(mark, TextAssetPayload):
        raise RuntimeError("rollover mark ledger drifted")
    target = next(
        (value for value in mark_asset.protected_values if value in mark.text), mark.text.split()[0]
    )
    first_source = _pressure_source(f"{first_timer.instruction}\n{mark.text}")
    recurring_source = _pressure_source(recurring_timer.instruction)
    prospective_source = _pressure_source(f"The shoreline notes mention {target} near the inlet.")
    quiet = _pressure_source("The atlas page remains quiet")
    candidate_start = 4 * _FRAME_GAP_MS
    action_count = 24
    timing = materialize_timing_plan(
        TimingSeed(Split.TEST, f"g7-rollover-checkpoint-v1:{shape_id}:{master_seed}"),
        action_count,
    )
    last_quiet_at = candidate_start + 9 * _FRAME_GAP_MS
    delegate_at = last_quiet_at + timing.service_ms[16] + 100
    cancel_at = delegate_at + timing.service_ms[17] - 1
    if cancel_at + timing.service_ms[19] >= timing.service_ms[0] + first_semantics.interval_ms:
        raise RuntimeError("timer checkpoint interval ledger drifted")
    delegate_source = followup.query
    cancel_plan = G7CancelPlan()
    if cancel_plan.schedule(first_semantics.message) != "t_001":
        raise RuntimeError("timer checkpoint cancel ledger drifted")
    cancel_plan.schedule(recurring_semantics.message)
    planned_cancel = cancel_plan.cancel("t_001")
    cancel_source = planned_cancel.utterance
    frames = [
        _frame(0, first_source),
        _frame(_FRAME_GAP_MS, recurring_source),
        _frame(2 * _FRAME_GAP_MS, prospective_source),
        _frame(3 * _FRAME_GAP_MS, quiet),
        *(
            _frame(candidate_start + index * _FRAME_GAP_MS, "The notebook remains quiet.")
            for index in range(10)
        ),
        _frame(delegate_at, delegate_source),
        _frame(cancel_at, cancel_source),
    ]
    actions = (
        _schedule("e_000002", first_source, first_timer, first_semantics),
        _idle(),
        _schedule("e_000005", recurring_source, recurring_timer, recurring_semantics),
        _idle(),
        MarkAction(
            type="mark",
            instruction=_span("e_000002", first_source, mark.text),
            target=_span("e_000008", prospective_source, target),
        ),
        _idle(),
        _idle(),
        *(_idle() for _ in range(10)),
        _delegate("e_000022", delegate_source, followup.query),
        CancelAction(
            type="cancel",
            instruction=_span("e_000023", cancel_source, cancel_source),
            target=CancelTimerTarget(kind="timer", timer_id=planned_cancel.target_timer_id),
        ),
        _idle(IdleReason.AWAITING_TOOL, "e_000022"),
        NudgeAction(type="nudge", fire_event_id="e_000028"),
        _idle(IdleReason.AWAITING_TOOL, "e_000022"),
        NudgeAction(type="nudge", fire_event_id="e_000030"),
        _idle(IdleReason.AWAITING_TOOL, "e_000022"),
    )
    program = _program(
        bundle,
        template,
        master_seed,
        shape_id,
        tuple(frames),
        actions,
        tool_results=(
            ScriptedToolResult(latency_ms=_LONG_PENDING_MS, data={"nonce": followup.result_a}),
        ),
        need_plans=(G7NeedPlan("n_rollover_followup", 17),),
    )
    if program.timing_plan != timing:
        raise RuntimeError("timer checkpoint timing ledger drifted")
    return program


def _timer_semantics(timer: TimerAssetPayload) -> TimerInstructionSemanticsV1:
    return validate_timer_asset_semantics_v1(timer.instruction, timer.interval_ms, timer.message)


def _candidate(
    parent: GeneratedScenario, shape_id: str, expected: tuple[type[object], ...]
) -> CorpusSegmentCandidate:
    validate_generated_scenario(parent)
    matches = []
    for index in range(1, len(parent.stream.segments)):
        candidate = CorpusSegmentCandidate(parent, index, shape_id)
        if tuple(type(action) for action in candidate.selected_actions) == expected:
            matches.append(candidate)
    if len(matches) != 1:
        raise ValueError(f"{shape_id} requires one exact later checkpoint segment")
    return matches[0]


async def build_g7_rollover_checkpoint_catalog(
    registry: AssetRegistry,
    *,
    directory: Path,
    master_seed: str = "g7-rollover-checkpoint-v1",
    repository_root: Path | None = None,
) -> tuple[G7RolloverCheckpointEntry, ...]:
    """Execute TEST-sealed parents and retain exact later rollover segments."""
    programs = (
        (
            "g7-checkpoint-rollover-a",
            "14I+M+G+S",
            _rollover_program(registry, master_seed, "g7-checkpoint-rollover-a", 13),
            (
                *(IdleAction for _ in range(13)),
                MarkAction,
                IntegrateAction,
                SkipAction,
                IdleAction,
            ),
        ),
        (
            "g7-checkpoint-rollover-b",
            "13I+M+G+S",
            _rollover_program(registry, master_seed, "g7-checkpoint-rollover-b", 12),
            (
                *(IdleAction for _ in range(12)),
                MarkAction,
                IntegrateAction,
                SkipAction,
                IdleAction,
            ),
        ),
        (
            "g7-checkpoint-rollover-c",
            "13I+D+C+2N",
            _timer_program(registry, master_seed),
            (
                *(IdleAction for _ in range(10)),
                DelegateAction,
                CancelAction,
                IdleAction,
                NudgeAction,
                IdleAction,
                NudgeAction,
                IdleAction,
            ),
        ),
    )
    entries = []
    for shape_id, vector, program, expected in programs:
        parent = await execute_scenario(
            program,
            session_id=shape_id,
            directory=directory / shape_id,
            repository_root=repository_root,
        )
        candidate = _candidate(parent, shape_id, expected)
        entries.append(G7RolloverCheckpointEntry(shape_id, parent, candidate, vector))
    return tuple(entries)
