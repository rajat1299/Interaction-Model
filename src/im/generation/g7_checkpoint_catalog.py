"""Causally complete G7 shapes selected from real later checkpoint segments."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from hashlib import sha256
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
from im.assets.registry import AssetBundle, AssetRegistry, SplitPool
from im.canonical_json import canonicalize_tim_json
from im.config import RuntimeConfig
from im.generation.corpus_segments import CorpusSegmentCandidate
from im.generation.g7_cancel_plan import G7CancelPlan
from im.generation.g7_checkpoint_context import build_checkpoint_working_document
from im.generation.g7_need_plan import G7NeedPlan, build_g7_need_evidence
from im.generation.ingestion import ScheduledSamplerFrame
from im.generation.need_lineage import (
    CancelResolutionEvidence,
    NeedBasisKind,
    NeedStatus,
)
from im.generation.scenarios import (
    BeatOpening,
    BeatStaleResults,
    DeclaredPerturbation,
    GeneratedScenario,
    ScenarioProgram,
    execute_scenario,
    select_approved_scenario_inputs,
    validate_generated_scenario,
)
from im.generation.timer_instruction_semantics import (
    parse_timer_instruction_v1,
    render_timer_instruction_v1,
)
from im.generation.timing import TimingPlan, TimingSeed, materialize_timing_plan
from im.schema.actions import (
    CancelAction,
    CancelTimerTarget,
    DelegateAction,
    IdleAction,
    IdleReason,
    IntegrateAction,
    NudgeAction,
    ScheduleAction,
    SkipAction,
    SkipReason,
    Span,
)
from im.schema.common import ToolName
from im.schema.textspan import utf16_len
from im.tools import ScriptedToolResult

__all__ = ("G7CheckpointCatalogEntry", "build_g7_checkpoint_catalog")


_FRAME_GAP_MS = 5_000
_RESULT_GAP_MS = 2_500
_LONG_PENDING_MS = 8_000_000
_PRELUDE_DOCUMENT_COUNT = 8


@dataclass(frozen=True, slots=True)
class G7CheckpointCatalogEntry:
    """One valid full parent plus a selected later runtime segment."""

    shape_id: str
    family: CorpusFamily
    parent: GeneratedScenario
    candidate: CorpusSegmentCandidate

    def __post_init__(self) -> None:
        if self.candidate.parent is not self.parent:
            raise ValueError("checkpoint candidate must retain its complete parent")
        if self.candidate.shape_id != self.shape_id:
            raise ValueError("checkpoint candidate and catalog shape disagree")
        validate_generated_scenario(self.parent)
        if self.parent.program.family is not self.family:
            raise ValueError("checkpoint parent and catalog family disagree")


@dataclass(frozen=True, slots=True)
class _CheckpointSpec:
    shape_id: str
    family: CorpusFamily
    builder: Callable[[AssetRegistry, str], ScenarioProgram]
    expected_actions: tuple[type[object], ...]


@dataclass(slots=True)
class _Recipe:
    """Concrete event-id ledger for one deterministic production run."""

    frames: list[ScheduledSamplerFrame]
    actions: list[object]
    next_event: int = 2  # e_000001 is runtime session_start.
    next_at_ms: int = 0

    def snapshot(self, text: str, *, at_ms: int | None = None) -> tuple[str, int]:
        at = self.next_at_ms if at_ms is None else at_ms
        event_id = f"e_{self.next_event:06d}"
        self.frames.append(_frame(at, text))
        self.next_event += 1
        self.next_at_ms = max(self.next_at_ms, at) + _FRAME_GAP_MS
        return event_id, at

    def action(self, value: object, *, runtime_events: int = 1) -> int:
        index = len(self.actions)
        self.actions.append(value)
        self.next_event += runtime_events
        return index

    def checkpoint(self) -> str:
        event_id = f"e_{self.next_event:06d}"
        self.next_event += 1
        return event_id

    def world_event(self) -> str:
        event_id = f"e_{self.next_event:06d}"
        self.next_event += 1
        return event_id


@dataclass(frozen=True, slots=True)
class _ToolPlan:
    action_index: int
    source_at_ms: int
    due_at_ms: int
    data: object


def _nonce_plans(
    *plans: tuple[int, int, int, object],
) -> tuple[_ToolPlan, ...]:
    return tuple(
        _ToolPlan(action, source_at, due_at, {"nonce": data})
        for action, source_at, due_at, data in plans
    )


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


def _span(event_id: str, text: str, selected: str | None = None, *, last: bool = False) -> Span:
    selected = text if selected is None else selected
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


def _delegate(event_id: str, text: str, query: str) -> DelegateAction:
    return DelegateAction(
        type="delegate",
        fact=_span(event_id, text, query),
        tool=ToolName.LOOKUP,
        args={"query": query},
    )


def _delegate_snapshot(
    recipe: _Recipe, source: str, query: str, *, at_ms: int | None = None
) -> tuple[str, int, int]:
    event_id, source_at_ms = recipe.snapshot(source, at_ms=at_ms)
    action = recipe.action(_delegate(event_id, source, query), runtime_events=2)
    return event_id, source_at_ms, action


def _triggered_delegate_snapshot(
    recipe: _Recipe,
    source: str,
    query: str,
    trigger: str,
    *,
    at_ms: int | None = None,
) -> tuple[str, int, int]:
    event_id, source_at_ms = recipe.snapshot(source, at_ms=at_ms)
    recipe.snapshot(trigger)
    action = recipe.action(_delegate(event_id, source, query), runtime_events=2)
    return event_id, source_at_ms, action


def _schedule(event_id: str, text: str, timer: TimerAssetPayload) -> ScheduleAction:
    if timer.interval_ms is None or timer.message is None:
        raise ValueError("checkpoint timer recipes require a supported timer")
    return ScheduleAction(
        type="schedule",
        instruction=_span(event_id, text, timer.instruction),
        interval_ms=timer.interval_ms,
        message=timer.message,
    )


def _schedule_literal_action(
    recipe: _Recipe,
    event_id: str,
    source: str,
    *,
    instruction: str | None = None,
    interval_ms: int,
    message: str,
) -> int:
    instruction = source if instruction is None else instruction
    semantics = parse_timer_instruction_v1(instruction)
    if (semantics.interval_ms, semantics.message) != (interval_ms, message):
        raise ValueError("schedule payload must match the rendered timer instruction")
    return recipe.action(
        ScheduleAction(
            type="schedule",
            instruction=_span(event_id, source, instruction, last=True),
            interval_ms=interval_ms,
            message=message,
        ),
        runtime_events=2,
    )


def _cancel(
    event_id: str, text: str, timer_id: str, *, instruction: str | None = None
) -> CancelAction:
    return CancelAction(
        type="cancel",
        instruction=_span(event_id, text, text if instruction is None else instruction, last=True),
        target=CancelTimerTarget(kind="timer", timer_id=timer_id),
    )


def _asset_text(asset: AssetRecord) -> str:
    payload = asset.payload
    if isinstance(payload, TextAssetPayload):
        return payload.text
    if isinstance(payload, LookupAssetPayload):
        return payload.query
    if isinstance(payload, TimerAssetPayload):
        return payload.instruction
    raise TypeError("working documents use atomic source assets")


def _lookups(pool: SplitPool) -> tuple[AssetRecord, ...]:
    return tuple(item for item in pool.assets if isinstance(item.payload, LookupAssetPayload))


def _supported_timer(pool: SplitPool) -> TimerAssetPayload:
    timer = next(
        (
            item.payload
            for item in pool.assets
            if isinstance(item.payload, TimerAssetPayload)
            and item.payload.form is TimerForm.SUPPORTED
        ),
        None,
    )
    if timer is None:
        raise ValueError("applied test pool lacks a supported timer")
    return timer


def _lookup(pool: SplitPool, family: CorpusFamily) -> LookupAssetPayload:
    payload = next(
        (
            item.payload
            for item in pool.assets
            if family in item.coverage and isinstance(item.payload, LookupAssetPayload)
        ),
        None,
    )
    if payload is None:
        raise ValueError(f"applied test pool lacks {family.value}")
    return payload


def _working_document(pool: SplitPool) -> str:
    values = {item.asset_id: _asset_text(item) for item in pool.assets}
    return build_checkpoint_working_document(values.values())


def _quiet_sources(pool: SplitPool) -> tuple[str, ...]:
    texts = tuple(
        item.payload.text for item in pool.assets if isinstance(item.payload, TextAssetPayload)
    )
    if len(texts) < 2:
        raise ValueError("applied test pool lacks quiet notebook text")
    first, second = texts[-2:]
    return (
        first,
        second,
        f"{first} {second}",
        f"{second} {first}",
        f"The open page keeps this sentence: “{first}”",
        f"Beside the margin sits this sentence: “{second}”",
        f"The notebook still holds “{first}” near “{second}”",
        f"On the desk, “{second}” remains beside “{first}”",
        f"The margin is quiet: “{first}” and “{second}”",
        f"The page remains open with “{second}” beside “{first}”",
        f"The two lines stay visible: “{first}” / “{second}”",
        f"A calm page keeps “{first}” close to “{second}”",
        f"The notebook has room for “{second}” and “{first}”",
        f"The desk note carries “{first}” with “{second}”",
    )


def _seeded_quiet_sources(pool: SplitPool, master_seed: str, count: int) -> tuple[str, ...]:
    """Select neutral sealed text without perturbing the fixed timer race plan."""
    choices = _quiet_sources(pool)
    draw = int.from_bytes(
        sha256(f"g7-timer-quiet-v1\0{master_seed}".encode()).digest(),
        "big",
    )
    selected = []
    for _ in range(count):
        draw, index = divmod(draw, len(choices))
        selected.append(choices[index])
    return tuple(selected)


def _inputs(
    registry: AssetRegistry, family: CorpusFamily
) -> tuple[AssetBundle, AssetRecord, SplitPool]:
    pool = registry.pool(Split.TEST)
    sources = tuple(sorted(pool.assets, key=lambda item: item.asset_id))
    template = next((item for item in pool.templates if family in item.coverage), None)
    if template is None:
        raise ValueError(f"applied test pool lacks a {family.value} template")
    bundle, selected_template = select_approved_scenario_inputs(
        registry,
        split=Split.TEST,
        template_id=template.asset_id,
        asset_ids=tuple(item.asset_id for item in sources),
    )
    return bundle, selected_template, pool


def _timing(
    bundle: AssetBundle, family: CorpusFamily, master_seed: str, action_count: int
) -> TimingPlan:
    return materialize_timing_plan(
        TimingSeed(bundle.split, f"g7-checkpoint-v2:{family.value}:{master_seed}"),
        action_count,
    )


def _causal_at(timing: TimingPlan, *boundaries: tuple[int, int], floor: int = 0) -> int:
    return max(floor, *(at_ms + timing.service_ms[index] + 100 for index, at_ms in boundaries))


def _materialize(
    bundle: AssetBundle,
    template: AssetRecord,
    family: CorpusFamily,
    master_seed: str,
    recipe: _Recipe,
    tools: tuple[_ToolPlan, ...] = (),
    stale: tuple[tuple[int, tuple[str, ...]], ...] = (),
    openings: tuple[tuple[int, str], ...] = (),
    config: RuntimeConfig | None = None,
    need_plans: tuple[G7NeedPlan, ...] = (),
    timing_plan: TimingPlan | None = None,
) -> ScenarioProgram:
    actions = tuple(recipe.actions)
    timing = (
        _timing(bundle, family, master_seed, len(actions)) if timing_plan is None else timing_plan
    )
    if len(timing.service_ms) != len(actions):
        raise ValueError("timing plan and action ledger must align")
    tool_results = tuple(
        ScriptedToolResult(
            latency_ms=plan.due_at_ms - (plan.source_at_ms + timing.service_ms[plan.action_index]),
            data=plan.data,
        )
        for plan in tools
    )
    if any(item.latency_ms < 0 for item in tool_results):
        raise ValueError("tool result precedes its real delegate action")
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
        family=family,
        master_seed=master_seed,
        timing_plan=timing,
        frames=tuple(recipe.frames),
        actions=actions,
        tool_results=tool_results,
        beat_ids=beats,
        stale_results_by_beat=tuple(
            BeatStaleResults(beat, stale_by_index.get(index, ()))
            for index, beat in enumerate(beats)
        ),
        perturbations=(DeclaredPerturbation(_perturbation(family)),),
        config=RuntimeConfig() if config is None else config,
        openings_by_beat=tuple(
            BeatOpening(beats[index], snapshot_id) for index, snapshot_id in openings
        ),
        need_lineage_by_beat=need_lineage,
        delegate_provenance_by_beat=delegate_provenance,
        cancel_resolution_evidence_by_beat=cancel_evidence,
        require_g7_evidence=True,
    )


def _perturbation(family: CorpusFamily) -> str:
    return {
        CorpusFamily.LOOKUP_DUPLICATE: "pending_tool_pressure",
        CorpusFamily.LOOKUP_STALE: "topic_change",
        CorpusFamily.TIMER_CANCEL: "timer_cancel_race",
        CorpusFamily.ROLLOVER: "state_checkpoint",
    }[family]


def _prelude(recipe: _Recipe, document: str, *, count: int = _PRELUDE_DOCUMENT_COUNT) -> None:
    for _ in range(count):
        recipe.snapshot(document)
        recipe.action(_idle(IdleReason.INSTRUCTION_NOT_DIRECT), runtime_events=0)


def _lookup_duplicate_a_program(registry: AssetRegistry, master_seed: str) -> ScenarioProgram:
    bundle, template, pool = _inputs(registry, CorpusFamily.LOOKUP_DUPLICATE)
    duplicate = _lookup(pool, CorpusFamily.LOOKUP_DUPLICATE)
    other = tuple(item.payload for item in _lookups(pool) if item.payload is not duplicate)
    if len(other) < 3:
        raise ValueError("lookup duplicate A needs three other applied lookup subjects")
    first, second, third, fourth = duplicate, other[0], other[1], other[2]
    total_actions = 21
    timing = _timing(bundle, CorpusFamily.LOOKUP_DUPLICATE, master_seed, total_actions)
    recipe = _Recipe([], [])
    _prelude(recipe, _working_document(pool))

    first_source = f"Please look up {first.query}."
    first_id, first_at, first_action = _delegate_snapshot(recipe, first_source, first.query)
    second_source = f"Keep {first.query} active. Please look up {second.query}."
    second_id, second_at, second_action = _delegate_snapshot(
        recipe,
        second_source,
        second.query,
        at_ms=_causal_at(
            timing,
            (first_action, first_at),
            floor=recipe.next_at_ms,
        ),
    )
    recipe.checkpoint()

    quiet = _quiet_sources(pool)
    latest_quiet_id = ""
    latest_quiet_at = 0
    latest_quiet_idle = -1
    quiet_at = _causal_at(
        timing,
        (second_action, second_at),
        floor=recipe.next_at_ms,
    )
    for index, text in enumerate(quiet[:5]):
        latest_quiet_id, latest_quiet_at = recipe.snapshot(
            text,
            at_ms=quiet_at if index == 0 else None,
        )
        latest_quiet_idle = recipe.action(
            _idle(IdleReason.AWAITING_TOOL, first_id), runtime_events=0
        )

    first_result_at = latest_quiet_at + _RESULT_GAP_MS
    first_result = recipe.world_event()
    first_integrate = recipe.action(
        IntegrateAction(type="integrate", result_event_id=first_result, text=first.result_a)
    )
    first_integrate_at = max(
        first_result_at,
        latest_quiet_at + timing.service_ms[latest_quiet_idle],
    )
    third_source = f"Keep {second.query} active. Please look up {third.query}."
    third_id, third_at, third_action = _delegate_snapshot(
        recipe,
        third_source,
        third.query,
        at_ms=_causal_at(
            timing,
            (first_integrate, first_integrate_at),
            floor=recipe.next_at_ms,
        ),
    )
    second_result_at = _causal_at(timing, (third_action, third_at))
    second_result = recipe.world_event()
    second_integrate = recipe.action(
        IntegrateAction(type="integrate", result_event_id=second_result, text=second.result_a)
    )
    fourth_source = f"I no longer need {third.query}; instead, please look up {fourth.query}."
    fourth_id, fourth_at, fourth_action = _delegate_snapshot(
        recipe,
        fourth_source,
        fourth.query,
        at_ms=_causal_at(
            timing,
            (second_integrate, second_result_at),
            floor=recipe.next_at_ms,
        ),
    )
    third_result_at = _causal_at(timing, (fourth_action, fourth_at))
    third_result = recipe.world_event()
    recipe.action(
        SkipAction(type="skip", target_event_id=third_result, reason=SkipReason.SUPERSEDED_QUERY)
    )
    recipe.action(_idle(IdleReason.AWAITING_TOOL, fourth_id), runtime_events=0)

    if len(recipe.actions) != total_actions:
        raise RuntimeError("duplicate A action ledger drifted")

    return _materialize(
        bundle,
        template,
        CorpusFamily.LOOKUP_DUPLICATE,
        master_seed,
        recipe,
        _nonce_plans(
            (first_action, first_at, first_result_at, first.result_a),
            (second_action, second_at, second_result_at, second.result_a),
            (third_action, third_at, third_result_at, third.result_a),
            (fourth_action, fourth_at, fourth_at + _LONG_PENDING_MS, fourth.result_a),
        ),
        openings=(
            (first_integrate, latest_quiet_id),
            (second_integrate, third_id),
        ),
        need_plans=(
            G7NeedPlan(
                "n_001",
                first_action,
                third_action,
                NeedStatus.SATISFIED,
                NeedBasisKind.RESULT,
                first_result,
            ),
            G7NeedPlan(
                "n_002",
                second_action,
                fourth_action,
                NeedStatus.SATISFIED,
                NeedBasisKind.RESULT,
                second_result,
            ),
            G7NeedPlan(
                "n_003",
                third_action,
                fourth_action,
                NeedStatus.SUPERSEDED,
                NeedBasisKind.SUPERSEDED,
                fourth_id,
                "n_004",
            ),
            G7NeedPlan("n_004", fourth_action),
        ),
    )


def _lookup_duplicate_b_program(registry: AssetRegistry, master_seed: str) -> ScenarioProgram:
    bundle, template, pool = _inputs(registry, CorpusFamily.LOOKUP_DUPLICATE)
    first = _lookup(pool, CorpusFamily.LOOKUP_DUPLICATE)
    others = tuple(item.payload for item in _lookups(pool) if item.payload is not first)
    if len(others) < 2:
        raise ValueError("lookup duplicate B needs two other applied lookup subjects")
    second, third = others[:2]
    pressure_document = _working_document(pool) + (
        " The writer leaves the atlas open with the cards undisturbed, keeping the familiar "
        "page available for one brief factual heading after the pause."
    )
    if len(pressure_document.encode("utf-8")) > 4_096:
        raise ValueError("duplicate B working document exceeds the sampler-size ceiling")
    total_actions = 22
    timing = _timing(bundle, CorpusFamily.LOOKUP_DUPLICATE, master_seed, total_actions)
    recipe = _Recipe([], [])
    _prelude(recipe, pressure_document)
    pre_checkpoint = (
        "The next notebook heading is Morrow Glen cistern fill percentage; the writer keeps "
        "that short factual line in view before returning to the page."
    )
    recipe.snapshot(pre_checkpoint)
    recipe.action(_idle(), runtime_events=0)
    recipe.checkpoint()

    quiet = _quiet_sources(pool)
    for text in quiet[:5]:
        recipe.snapshot(text)
        recipe.action(_idle(), runtime_events=0)

    first_source = f"Please look up {first.query}."
    first_id, first_at, first_action = _delegate_snapshot(recipe, first_source, first.query)
    second_source = f"Keep {first.query} active. Please look up {second.query}."
    second_id, second_at, second_action = _delegate_snapshot(recipe, second_source, second.query)
    third_source = f"Keep {first.query} active. Please look up {third.query}."
    third_id, third_at = recipe.snapshot(third_source)
    superseding_snapshot = (
        f"Keep {first.query} active. I no longer need {second.query} or {third.query}; "
        "those lookups are abandoned."
    )
    superseding_id, _ = recipe.snapshot(superseding_snapshot, at_ms=third_at)
    third_action = recipe.action(_delegate(third_id, third_source, third.query), runtime_events=2)
    awaiting_results = recipe.action(_idle(IdleReason.AWAITING_TOOL, first_id), runtime_events=0)

    first_result = recipe.world_event()
    second_result = recipe.world_event()
    third_result = recipe.world_event()
    first_skip = recipe.action(
        SkipAction(type="skip", target_event_id=second_result, reason=SkipReason.STALE_TOOL_RESULT)
    )
    second_skip = recipe.action(
        SkipAction(type="skip", target_event_id=third_result, reason=SkipReason.STALE_TOOL_RESULT)
    )
    first_integrate = recipe.action(
        IntegrateAction(type="integrate", result_event_id=first_result, text=first.result_a)
    )
    result_at = _causal_at(
        timing,
        (first_action, first_at),
        (second_action, second_at),
        (third_action, third_at),
        (awaiting_results, third_at + timing.service_ms[third_action]),
    )
    recipe.snapshot(
        "The first lookup result is now recorded in the notebook.",
        at_ms=max(
            recipe.next_at_ms,
            result_at
            + sum(timing.service_ms[index] for index in (first_skip, second_skip, first_integrate))
            + 100,
        ),
    )
    terminal_idle = recipe.action(
        _idle(IdleReason.ALREADY_HANDLED, first_result), runtime_events=0
    )
    if len(recipe.actions) != total_actions:
        raise RuntimeError("duplicate B action ledger drifted")
    return _materialize(
        bundle,
        template,
        CorpusFamily.LOOKUP_DUPLICATE,
        master_seed,
        recipe,
        _nonce_plans(
            (first_action, first_at, result_at, first.result_a),
            (second_action, second_at, result_at, second.result_a),
            (third_action, third_at, result_at, third.result_a),
        ),
        stale=(
            (first_skip, (second_result, third_result)),
            (second_skip, (third_result,)),
        ),
        openings=((first_integrate, superseding_id),),
        need_plans=(
            G7NeedPlan(
                "n_001",
                first_action,
                terminal_idle,
                NeedStatus.SATISFIED,
                NeedBasisKind.RESULT,
                first_result,
            ),
            G7NeedPlan(
                "n_002",
                second_action,
                first_skip,
                NeedStatus.ABANDONED,
                NeedBasisKind.ABANDONED,
                superseding_id,
            ),
            G7NeedPlan(
                "n_003",
                third_action,
                first_skip,
                NeedStatus.ABANDONED,
                NeedBasisKind.ABANDONED,
                superseding_id,
            ),
        ),
    )


def _lookup_stale_program(registry: AssetRegistry, master_seed: str) -> ScenarioProgram:
    bundle, template, pool = _inputs(registry, CorpusFamily.LOOKUP_STALE)
    original = _lookup(pool, CorpusFamily.LOOKUP_STALE)
    others = tuple(item.payload for item in _lookups(pool) if item.payload is not original)
    if len(others) != 3:
        raise ValueError("stale lookup shape needs the other three applied lookup subjects")
    fable, morrow, alder = others
    pressure_document = _working_document(pool) + (
        " The writer returns to the same open atlas, where the card edges remain aligned and "
        "the notebook keeps its unhurried account of the desk, the light, and the visible margins. "
        "The last card stays beside the pencil while the quiet page remains open for the next note."
    )
    if len(pressure_document.encode("utf-8")) > 4_096:
        raise ValueError("stale working document exceeds the sampler-size ceiling")
    total_actions = 20
    timing = _timing(bundle, CorpusFamily.LOOKUP_STALE, master_seed, total_actions)
    recipe = _Recipe([], [])
    _prelude(recipe, pressure_document, count=1)

    original_source = (
        f"Please refresh this atlas fact when the current note is settled: {original.query}. "
        "Keep the lookup tied to the gallery-wing entry, not the nearby courtyard caption. "
        "The atlas is open beside a ruled notebook, with the relevant card resting above the "
        "margin and a pencil marking the line that prompted the question. The surrounding notes "
        "describe the building in a calm, continuous paragraph so the requested fact should remain "
        "the only external detail being checked. Nothing else on the page changes the subject: the "
        "desk lamp, the paper edges, and the quiet room are merely context for the same atlas "
        "entry. "
        "When the answer arrives, it belongs with this card and can be compared with the later "
        "refresh rather than folded into any unrelated station or cistern note. The writer is "
        "still working through the same outline, leaving enough space below the card for a concise "
        "result "
        "and keeping the rest of the notebook deliberately unchanged while the lookup is pending."
    )
    original_id, original_at, original_action = _delegate_snapshot(
        recipe, original_source, original.query
    )
    quiet_trigger = "Still."
    fable_id, fable_at, fable_action = _triggered_delegate_snapshot(
        recipe,
        fable.query,
        fable.query,
        quiet_trigger,
        at_ms=_causal_at(
            timing,
            (original_action, original_at),
            floor=recipe.next_at_ms,
        ),
    )
    original_idle = recipe.action(_idle(IdleReason.AWAITING_TOOL, original_id), runtime_events=0)
    morrow_id, morrow_at, morrow_action = _triggered_delegate_snapshot(
        recipe,
        morrow.query,
        morrow.query,
        quiet_trigger,
        at_ms=_causal_at(
            timing,
            (original_idle, fable_at + timing.service_ms[fable_action]),
            floor=recipe.next_at_ms,
        ),
    )
    morrow_idle = recipe.action(_idle(IdleReason.AWAITING_TOOL, original_id), runtime_events=0)
    alder_id, alder_at, alder_action = _triggered_delegate_snapshot(
        recipe,
        alder.query,
        alder.query,
        quiet_trigger,
        at_ms=_causal_at(
            timing,
            (morrow_idle, morrow_at + timing.service_ms[morrow_action]),
            floor=recipe.next_at_ms,
        ),
    )
    recipe.action(_idle(IdleReason.AWAITING_TOOL, original_id), runtime_events=0)
    original_result = recipe.world_event()
    original_result_at = recipe.next_at_ms + _RESULT_GAP_MS
    result_idle = recipe.action(_idle(IdleReason.AWAITING_TOOL, fable_id), runtime_events=0)

    refreshed_query = original.query
    refresh_source = f"Refresh {refreshed_query}."
    refresh_at = _causal_at(
        timing,
        (result_idle, original_result_at),
        floor=recipe.next_at_ms,
    )
    refresh_id, refresh_at = recipe.snapshot(refresh_source, at_ms=refresh_at)
    original_skip = recipe.action(
        SkipAction(
            type="skip",
            target_event_id=original_result,
            reason=SkipReason.SUPERSEDED_QUERY,
        )
    )
    refresh_action = recipe.action(
        _delegate(refresh_id, refresh_source, refreshed_query), runtime_events=2
    )
    combined_query = f"{fable.query} and {alder.query}"
    combined_result = f"{fable.result_a} {alder.result_a}"
    _, combined_at, combined_action = _triggered_delegate_snapshot(
        recipe,
        combined_query,
        combined_query,
        quiet_trigger,
        at_ms=_causal_at(
            timing,
            (refresh_action, refresh_at + timing.service_ms[original_skip]),
            floor=recipe.next_at_ms,
        ),
    )
    recipe.checkpoint()
    refresh_idle = recipe.action(_idle(IdleReason.AWAITING_TOOL, fable_id), runtime_events=0)

    abandoned = (
        f"Those lookups — {fable.query}, {morrow.query}, and {alder.query}, "
        "including the refreshed gallery-wing and combined requests — are no longer relevant; "
        "I’m returning to the notebook outline."
    )
    abandoned_at = max(
        recipe.next_at_ms,
        refresh_at + timing.service_ms[refresh_action] + timing.service_ms[refresh_idle] + 100,
    )
    abandoned_id, _ = recipe.snapshot(
        abandoned,
        at_ms=abandoned_at,
    )
    abandoned_idle = recipe.action(_idle(IdleReason.AWAITING_TOOL, fable_id), runtime_events=0)

    # Deliver the abandoned results during the evidence-bearing idle decision so the
    # next tick sees both the visible abandonment and every late result.
    due_at = abandoned_at + 1_000
    fable_result = recipe.world_event()
    morrow_result = recipe.world_event()
    alder_result = recipe.world_event()
    refresh_result = recipe.world_event()
    combined_result_event = recipe.world_event()
    stale_results = (
        fable_result,
        morrow_result,
        alder_result,
        refresh_result,
        combined_result_event,
    )
    skips = tuple(
        recipe.action(
            SkipAction(
                type="skip",
                target_event_id=result,
                reason=SkipReason.STALE_TOOL_RESULT,
            )
        )
        for result in stale_results
    )
    recipe.action(_idle(), runtime_events=0)
    if len(recipe.actions) != total_actions:
        raise RuntimeError("stale lookup action ledger drifted")
    return _materialize(
        bundle,
        template,
        CorpusFamily.LOOKUP_STALE,
        master_seed,
        recipe,
        _nonce_plans(
            (original_action, original_at, original_result_at, original.result_a),
            (fable_action, fable_at, due_at, fable.result_a),
            (morrow_action, morrow_at, due_at, morrow.result_a),
            (alder_action, alder_at, due_at, alder.result_a),
            (
                refresh_action,
                refresh_at + timing.service_ms[original_skip],
                due_at,
                original.result_b,
            ),
            (combined_action, combined_at, due_at, combined_result),
        ),
        stale=(
            (skips[0], stale_results),
            (skips[1], stale_results[1:]),
            (skips[2], stale_results[2:]),
            (skips[3], stale_results[3:]),
            (skips[4], stale_results[4:]),
        ),
        config=RuntimeConfig(context_budget_tokens=3_800),
        need_plans=(
            G7NeedPlan(
                "n_001",
                original_action,
                original_skip,
                NeedStatus.SUPERSEDED,
                NeedBasisKind.SUPERSEDED,
                refresh_id,
                "n_005",
            ),
            G7NeedPlan(
                "n_002",
                fable_action,
                abandoned_idle,
                NeedStatus.ABANDONED,
                NeedBasisKind.ABANDONED,
                abandoned_id,
            ),
            G7NeedPlan(
                "n_003",
                morrow_action,
                abandoned_idle,
                NeedStatus.ABANDONED,
                NeedBasisKind.ABANDONED,
                abandoned_id,
            ),
            G7NeedPlan(
                "n_004",
                alder_action,
                abandoned_idle,
                NeedStatus.ABANDONED,
                NeedBasisKind.ABANDONED,
                abandoned_id,
            ),
            G7NeedPlan(
                "n_005",
                refresh_action,
                abandoned_idle,
                NeedStatus.ABANDONED,
                NeedBasisKind.ABANDONED,
                abandoned_id,
                birth_index=original_skip,
            ),
            G7NeedPlan(
                "n_006",
                combined_action,
                abandoned_idle,
                NeedStatus.ABANDONED,
                NeedBasisKind.ABANDONED,
                abandoned_id,
            ),
        ),
    )


def _timer_cancel_program(registry: AssetRegistry, master_seed: str) -> ScenarioProgram:
    _, template, pool = _inputs(registry, CorpusFamily.TIMER_CANCEL)
    timer_records = tuple(
        item
        for item in pool.assets
        if isinstance(item.payload, TimerAssetPayload) and item.payload.form is TimerForm.SUPPORTED
    )
    short_record = min(timer_records, key=lambda item: item.payload.interval_ms or 0)
    long_record = max(timer_records, key=lambda item: item.payload.interval_ms or 0)
    family_record = next(
        item
        for item in pool.assets
        if CorpusFamily.TIMER_CANCEL in item.coverage
        and isinstance(item.payload, TimerAssetPayload)
    )
    short = short_record.payload
    long = long_record.payload
    if (
        short.interval_ms is None
        or long.interval_ms is None
        or short.message is None
        or long.message is None
    ):
        raise ValueError("timer checkpoint recipe requires applied supported timers")
    bundle, template = select_approved_scenario_inputs(
        registry,
        split=Split.TEST,
        template_id=template.asset_id,
        asset_ids=tuple(
            sorted(
                (
                    family_record.asset_id,
                    short_record.asset_id,
                    long_record.asset_id,
                )
            )
        ),
    )

    # The fourth pre-existing timer fires during its own cancellation. The
    # newly scheduled timer then supplies two handled fires and one canceled
    # fire, leaving two independent canceled targets without lookup lineage.
    total_actions = 26
    timing = materialize_timing_plan(
        TimingSeed(bundle.split, "g7-timer-compact:29460"), total_actions
    )
    neutral = iter(_seeded_quiet_sources(pool, master_seed, 4))
    recipe = _Recipe([], [])
    cancel_plan = G7CancelPlan()
    pressure_unit = (
        "The atlas remains open beside the notebook while the field cards and pencil stay in "
        "their original places. "
    )
    pressure = (pressure_unit * 80)[:4_020]
    additional_long_instruction = render_timer_instruction_v1(
        long.interval_ms, long.message, explicit_additional=True
    )
    initial_schedules = (
        (short.instruction, short.interval_ms, short.message),
        (long.instruction, long.interval_ms, long.message),
        (additional_long_instruction, long.interval_ms, long.message),
        (additional_long_instruction, long.interval_ms, long.message),
    )
    next_at = 0
    initial_timer_ids = []
    fourth_due_at = 0
    for instruction, interval_ms, message in initial_schedules:
        source = instruction
        event_id, source_at = recipe.snapshot(source, at_ms=next_at)
        recipe.snapshot(pressure, at_ms=source_at + 100)
        schedule_index = _schedule_literal_action(
            recipe,
            event_id,
            source,
            instruction=instruction,
            interval_ms=interval_ms,
            message=message,
        )
        initial_timer_ids.append(cancel_plan.schedule(message))
        if len(initial_timer_ids) == 4:
            fourth_due_at = source_at + timing.service_ms[schedule_index] + interval_ms
        idle_index = recipe.action(_idle(), runtime_events=0)
        next_at = (
            source_at + timing.service_ms[schedule_index] + timing.service_ms[idle_index] + 1_000
        )
    if tuple(initial_timer_ids) != (
        "t_001",
        "t_002",
        "t_003",
        "t_004",
    ):
        raise RuntimeError("timer cancel plan identity drifted")
    first_cancel_at = next_at + 5_000
    recipe.checkpoint()

    def selected_cancel(timer_id: str, *, at_ms: int) -> int:
        source = cancel_plan.cancel(timer_id).utterance
        event_id, _ = recipe.snapshot(source, at_ms=at_ms)
        cancel_index = recipe.action(_cancel(event_id, source, timer_id), runtime_events=2)
        idle_index = recipe.action(_idle(), runtime_events=0)
        return at_ms + timing.service_ms[cancel_index] + timing.service_ms[idle_index] + 1_000

    next_cancel_at = selected_cancel("t_001", at_ms=first_cancel_at)
    next_cancel_at = selected_cancel("t_002", at_ms=next_cancel_at)
    next_cancel_at = selected_cancel("t_003", at_ms=next_cancel_at)

    recipe.snapshot(next(neutral), at_ms=next_cancel_at)
    extra_idle = recipe.action(_idle(), runtime_events=0)
    next_cancel_at += timing.service_ms[extra_idle] + 1_000

    fourth_cancel_at = max(next_cancel_at, fourth_due_at - 100)
    fourth_cancel_source = cancel_plan.cancel("t_004").utterance
    fourth_cancel_id, _ = recipe.snapshot(fourth_cancel_source, at_ms=fourth_cancel_at)
    fourth_fire = recipe.world_event()
    recurring_interval_ms = 1_000
    recurring_source = render_timer_instruction_v1(recurring_interval_ms, short.message)
    recurring_id, _ = recipe.snapshot(
        recurring_source,
        at_ms=fourth_cancel_at + 100,
    )
    recipe.action(_cancel(fourth_cancel_id, fourth_cancel_source, "t_004"), runtime_events=2)
    recurring_schedule = _schedule_literal_action(
        recipe,
        recurring_id,
        recurring_source,
        interval_ms=recurring_interval_ms,
        message=short.message,
    )
    if recurring_schedule != 16 or cancel_plan.schedule(short.message) != "t_005":
        raise RuntimeError("recurring timer action ledger drifted")
    recurring_anchor = (
        fourth_cancel_at + timing.service_ms[15] + timing.service_ms[recurring_schedule]
    )
    first_fire = recipe.world_event()
    first_skip = recipe.action(
        SkipAction(
            type="skip",
            target_event_id=fourth_fire,
            reason=SkipReason.CANCELED_TIMER,
        )
    )
    recipe.snapshot(
        next(neutral),
        at_ms=recurring_anchor + timing.service_ms[first_skip] + 100,
    )
    first_nudge = recipe.action(
        NudgeAction(type="nudge", fire_event_id=first_fire), runtime_events=1
    )

    second_fire = recipe.world_event()
    first_idle = recipe.action(_idle(), runtime_events=0)
    recipe.snapshot(
        next(neutral),
        at_ms=(
            recurring_anchor
            + timing.service_ms[first_skip]
            + timing.service_ms[first_nudge]
            + timing.service_ms[first_idle]
            + 100
        ),
    )
    recipe.action(NudgeAction(type="nudge", fire_event_id=second_fire), runtime_events=1)
    recipe.action(_idle(), runtime_events=0)

    third_due_at = recurring_anchor + 3 * recurring_interval_ms
    carrier_source = long.instruction
    carrier_id, _ = recipe.snapshot(carrier_source, at_ms=third_due_at - 100)
    third_fire = recipe.world_event()
    if cancel_plan.schedule(long.message) != "t_006":
        raise RuntimeError("carrier timer identity drifted")
    final_cancel_instruction = cancel_plan.cancel("t_005").utterance
    final_cancel_id, _ = recipe.snapshot(
        final_cancel_instruction,
        at_ms=third_due_at + 150,
    )
    carrier_schedule = _schedule_literal_action(
        recipe,
        carrier_id,
        carrier_source,
        interval_ms=long.interval_ms,
        message=long.message,
    )
    if carrier_schedule != 22:
        raise RuntimeError("carrier timer action ledger drifted")

    final_cancel = recipe.action(
        _cancel(
            final_cancel_id,
            final_cancel_instruction,
            "t_005",
            instruction=final_cancel_instruction,
        ),
        runtime_events=2,
    )
    recipe.snapshot(
        next(neutral),
        at_ms=(
            third_due_at
            - 100
            + timing.service_ms[carrier_schedule]
            + timing.service_ms[final_cancel]
            + 100
        ),
    )
    recipe.action(
        SkipAction(type="skip", target_event_id=third_fire, reason=SkipReason.CANCELED_TIMER)
    )
    recipe.action(_idle(), runtime_events=0)

    if len(recipe.actions) != total_actions:
        raise RuntimeError("timer checkpoint action ledger drifted")
    return _materialize(
        bundle,
        template,
        CorpusFamily.TIMER_CANCEL,
        master_seed,
        recipe,
        config=RuntimeConfig(context_budget_tokens=7_200),
        timing_plan=timing,
    )


def _candidate(
    parent: GeneratedScenario, shape_id: str, expected: tuple[type[object], ...]
) -> CorpusSegmentCandidate:
    matches = []
    for index in range(1, len(parent.stream.segments)):
        candidate = CorpusSegmentCandidate(parent, index, shape_id)
        if tuple(type(action) for action in candidate.selected_actions) == expected:
            matches.append(candidate)
    if len(matches) != 1:
        raise ValueError(f"{shape_id} requires one exact later checkpoint segment")
    return matches[0]


_CHECKPOINT_SPECS = (
    _CheckpointSpec(
        "g7-checkpoint-lookup-duplicate-a",
        CorpusFamily.LOOKUP_DUPLICATE,
        _lookup_duplicate_a_program,
        (
            *((IdleAction,) * 5),
            IntegrateAction,
            DelegateAction,
            IntegrateAction,
            DelegateAction,
            SkipAction,
            IdleAction,
        ),
    ),
    _CheckpointSpec(
        "g7-checkpoint-lookup-duplicate-b",
        CorpusFamily.LOOKUP_DUPLICATE,
        _lookup_duplicate_b_program,
        (
            *((IdleAction,) * 5),
            *((DelegateAction,) * 3),
            IdleAction,
            SkipAction,
            SkipAction,
            IntegrateAction,
            IdleAction,
        ),
    ),
    _CheckpointSpec(
        "g7-checkpoint-lookup-stale",
        CorpusFamily.LOOKUP_STALE,
        _lookup_stale_program,
        (
            IdleAction,
            IdleAction,
            *((SkipAction,) * 5),
            IdleAction,
        ),
    ),
    _CheckpointSpec(
        "g7-checkpoint-timer-cancel",
        CorpusFamily.TIMER_CANCEL,
        _timer_cancel_program,
        (
            *((CancelAction, IdleAction) * 3),
            IdleAction,
            CancelAction,
            ScheduleAction,
            SkipAction,
            NudgeAction,
            IdleAction,
            NudgeAction,
            IdleAction,
            ScheduleAction,
            CancelAction,
            SkipAction,
            IdleAction,
        ),
    ),
)


async def build_g7_checkpoint_catalog(
    registry: AssetRegistry,
    *,
    directory: Path,
    master_seed: str = "g7-checkpoint-catalog-v2",
    repository_root: Path | None = None,
) -> tuple[G7CheckpointCatalogEntry, ...]:
    """Execute TEST-sealed parents and retain their exact later segments.

    TEST is deliberately fixed: the applied review registry seals TEST and
    DEMO only, and these canary shapes must not rely on in-memory TRAIN review.
    """
    entries = []
    for spec in _CHECKPOINT_SPECS:
        parent = await execute_scenario(
            spec.builder(registry, master_seed),
            session_id=spec.shape_id,
            directory=directory / spec.shape_id,
            repository_root=repository_root,
        )
        entries.append(
            G7CheckpointCatalogEntry(
                spec.shape_id,
                spec.family,
                parent,
                _candidate(parent, spec.shape_id, spec.expected_actions),
            )
        )
    return tuple(entries)
