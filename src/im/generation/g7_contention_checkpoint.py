"""One real later-checkpoint G7 timer-contention parent."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from im.assets.model import (
    AssetRecord,
    CorpusFamily,
    Split,
    TimerAssetPayload,
    TimerForm,
)
from im.assets.registry import AssetBundle, AssetRegistry
from im.canonical_json import canonicalize_tim_json
from im.config import RuntimeConfig
from im.generation.corpus_segments import CorpusSegmentCandidate, CorpusSegmentError
from im.generation.g7_cancel_plan import G7CancelPlan
from im.generation.ingestion import ScheduledSamplerFrame
from im.generation.need_lineage import CancelResolutionEvidence
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
    parse_timer_instruction_v1,
    render_timer_instruction_v1,
    validate_timer_asset_semantics_v1,
)
from im.generation.timing import TimingPlan, TimingSeed, materialize_timing_plan
from im.schema.actions import (
    CancelAction,
    CancelTimerTarget,
    IdleAction,
    IdleReason,
    NudgeAction,
    ScheduleAction,
    Span,
)
from im.schema.textspan import utf16_len

__all__ = (
    "G7_CONTENTION_CHECKPOINT_SHAPE_ID",
    "G7ContentionCheckpointEntry",
    "build_g7_contention_checkpoint_program",
    "build_g7_contention_checkpoint_catalog",
)


G7_CONTENTION_CHECKPOINT_SHAPE_ID = "g7-checkpoint-timer-contention-fires-4i-6n-2c"
_CONFIG = RuntimeConfig(context_budget_tokens=7_200)
_REPAIRED_CONFIG = RuntimeConfig(context_budget_tokens=2_500)
_PRESSURE_BYTES = 4_000
_REPAIRED_PRESSURE_BYTES = 2_000
_ACCUMULATED_PRESSURE_BYTES = 3_600
_PREFIX_PRESSURE_AT_MS = (100_000, 120_000, 140_000, 160_000)
_NEUTRAL_AT_MS = (200_000, 220_000, 240_000)
_TIMING_SEED = "g7-contention-checkpoint-v1:g7-contention-checkpoint-test:153024"
_MESSAGES = tuple(
    f"seal the mint envelope for checkpoint lane {ordinal}" for ordinal in range(1, 7)
)


@dataclass(frozen=True, slots=True)
class G7ContentionCheckpointEntry:
    """One complete production parent and its exact later checkpoint view."""

    shape_id: str
    parent: GeneratedScenario
    candidate: CorpusSegmentCandidate
    action_vector: str = "4I+6N+2C"

    def __post_init__(self) -> None:
        if self.shape_id != G7_CONTENTION_CHECKPOINT_SHAPE_ID:
            raise ValueError("contention checkpoint shape id drifted")
        if self.candidate.parent is not self.parent or self.candidate.shape_id != self.shape_id:
            raise ValueError("contention checkpoint candidate does not retain its parent")
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


def _span(event_id: str, source: str, text: str) -> Span:
    start = source.index(text)
    return Span(
        event_id=event_id,
        start_utf16=utf16_len(source[:start]),
        end_utf16=utf16_len(source[:start]) + utf16_len(text),
        text=text,
    )


def _idle(
    reason: IdleReason = IdleReason.NO_TRIGGER, related_event_id: str | None = None
) -> IdleAction:
    return IdleAction(type="idle", reason=reason, related_event_id=related_event_id)


def _pressure(ordinal: int, master_seed: str, size: int = _PRESSURE_BYTES) -> str:
    folio = int.from_bytes(sha256(master_seed.encode()).digest()[:4], "big")
    prefix = f"Checkpoint pressure page {ordinal}, folio {folio}: "
    filler = "the atlas notebook remains open beside the field cards. "
    return (prefix + filler * size)[:size]


def _inputs(
    registry: AssetRegistry,
    *,
    split: Split = Split.TEST,
    template_id: str | None = None,
    timer_asset_id: str | None = None,
) -> tuple[AssetBundle, AssetRecord, TimerAssetPayload]:
    pool = registry.pool(split)
    template = next(
        (
            item
            for item in pool.templates
            if CorpusFamily.TIMER_CONTENTION in item.coverage
            and (template_id is None or item.asset_id == template_id)
        ),
        None,
    )
    timer = next(
        (
            item
            for item in pool.assets
            if CorpusFamily.TIMER_CONTENTION in item.coverage
            and isinstance(item.payload, TimerAssetPayload)
            and item.payload.form is TimerForm.SUPPORTED
            and (timer_asset_id is None or item.asset_id == timer_asset_id)
        ),
        None,
    )
    if template is None or timer is None:
        raise ValueError("contention checkpoint inputs are absent or unapproved in the split")
    bundle, selected_template = select_approved_scenario_inputs(
        registry,
        split=split,
        template_id=template.asset_id,
        asset_ids=(timer.asset_id,),
    )
    return bundle, selected_template, timer.payload


def _timing(
    interval_ms: int,
    *,
    split: Split = Split.TEST,
    timing_seed: str = _TIMING_SEED,
    separated_requests: bool = False,
) -> tuple[TimingPlan, tuple[int, ...]]:
    """Pick a seeded plan where every timer fire is real before its nudge."""
    timing = materialize_timing_plan(
        TimingSeed(split, timing_seed), 20 if separated_requests else 28
    )
    anchors = []
    if separated_requests:
        source_at = 0
        for index in range(0, 8, 2):
            anchor = source_at + timing.service_ms[index]
            anchors.append(anchor)
            source_at = anchor + 4_000
    else:
        schedule_start = 0
        for index in range(0, 12, 2):
            anchor = schedule_start + timing.service_ms[index]
            anchors.append(anchor)
            schedule_start = anchor + timing.service_ms[index + 1]
    due_at = tuple(anchor + interval_ms for anchor in anchors)
    if separated_requests:
        for ordinal in range(3):
            nudge_index = 10 + 2 * ordinal
            settled_at = (
                due_at[ordinal]
                + timing.service_ms[nudge_index]
                + timing.service_ms[nudge_index + 1]
            )
            if settled_at >= due_at[ordinal + 1]:
                raise RuntimeError("timer contention settling decision overlaps the next fire")
    else:
        now = due_at[0]
        next_fire = 1
        for ordinal, action_index in enumerate(range(19, 25)):
            if due_at[ordinal] > now:
                raise RuntimeError("timer contention timing no longer reaches its next fire")
            now += timing.service_ms[action_index]
            while next_fire < len(due_at) and due_at[next_fire] < now:
                next_fire += 1
        if next_fire != len(due_at):
            raise RuntimeError("timer contention timing no longer opens every fire")
    return timing, due_at


def _fire_and_cancel_event_ids(
    timing: TimingPlan,
    due_at: tuple[int, ...],
    *,
    separated_requests: bool = False,
) -> tuple[tuple[str, ...], str, str, int]:
    """Mirror the real event allocation order around the nudge/cancel wave."""
    if separated_requests:
        fire_ids = tuple(f"e_{event:06d}" for event in (16, 19, 21, 23))
        last_nudge_at = due_at[-1] + timing.service_ms[16]
        return fire_ids, "e_000024", "e_000026", last_nudge_at

    next_event = 28
    fire_ids = [f"e_{next_event:06d}"]
    next_event += 1
    next_due = 1
    now = due_at[0]
    nudge_indices = range(19, 25)
    for action_index in nudge_indices:
        now += timing.service_ms[action_index]
        while next_due < len(due_at) and due_at[next_due] < now:
            fire_ids.append(f"e_{next_event:06d}")
            next_event += 1
            next_due += 1
        if action_index == nudge_indices.stop - 1:
            cancel_one_event_id = f"e_{next_event:06d}"
            next_event += 1
        next_event += 1  # the nudge action itself
    if len(fire_ids) != 6:
        raise RuntimeError("timer contention timing no longer opens every fire")

    cancel_two_event_id = f"e_{next_event:06d}"
    next_event += 1
    next_event += 2  # first cancel action and its acknowledgement
    return tuple(fire_ids), cancel_one_event_id, cancel_two_event_id, now


def _schedule_frames(
    timing: TimingPlan, instructions: tuple[str, ...]
) -> tuple[tuple[int, str], ...]:
    schedule_start = 0
    frames = []
    for index, instruction in enumerate(instructions):
        action_index = 2 * index
        source_at = 0 if index == 0 else schedule_start - timing.service_ms[action_index - 1] + 100
        frames.append((source_at, instruction))
        schedule_start += timing.service_ms[action_index] + timing.service_ms[action_index + 1]
    return tuple(frames)


def _separated_schedule_frames(
    timing: TimingPlan, instructions: tuple[str, ...]
) -> tuple[tuple[int, str], ...]:
    source_at = 0
    frames = []
    for index, instruction in enumerate(instructions):
        frames.append((source_at, instruction))
        source_at += timing.service_ms[2 * index] + 4_000
    return tuple(frames)


def _program(registry: AssetRegistry, master_seed: str) -> ScenarioProgram:
    """Retain the historical TEST program and its fixed timing identity."""
    return build_g7_contention_checkpoint_program(registry, master_seed=master_seed)


def build_g7_contention_checkpoint_program(
    registry: AssetRegistry,
    *,
    master_seed: str,
    split: Split | str = Split.TEST,
    template_id: str | None = None,
    timer_asset_id: str | None = None,
    timing_seed: str = _TIMING_SEED,
    messages: tuple[str, ...] | None = None,
    separated_requests: bool = False,
    accumulated_requests: bool = False,
) -> ScenarioProgram:
    """Build the complete contention parent against explicit approved inputs.

    Defaults preserve the sealed TEST parent.  Phase 2 can provide TRAIN
    source/template identities and a new timing seed without changing that
    historical program.
    """
    split = Split(split)
    if separated_requests and accumulated_requests:
        raise ValueError("contention repair modes are mutually exclusive")
    bundle, template, timer = _inputs(
        registry,
        split=split,
        template_id=template_id,
        timer_asset_id=timer_asset_id,
    )
    base = validate_timer_asset_semantics_v1(timer.instruction, timer.interval_ms, timer.message)
    messages = _MESSAGES if messages is None else messages
    if len(messages) != 6 or len(set(messages)) != 6:
        raise ValueError("contention checkpoint requires six distinct reminder messages")
    instructions = tuple(
        render_timer_instruction_v1(
            base.interval_ms,
            message,
            explicit_additional=bool((separated_requests or accumulated_requests) and index),
        )
        for index, message in enumerate(messages)
    )
    if separated_requests:
        instructions = instructions[:4]
    sources = (
        tuple("\n".join(instructions[: index + 1]) for index in range(len(instructions)))
        if accumulated_requests
        else instructions
    )
    semantics = tuple(parse_timer_instruction_v1(instruction) for instruction in instructions)
    expected_timer_count = 4 if separated_requests else 6
    if len({item.message for item in semantics}) != expected_timer_count or any(
        item.interval_ms != base.interval_ms for item in semantics
    ):
        raise RuntimeError("timer semantic ledger drifted")
    timing, due_at = _timing(
        base.interval_ms,
        split=split,
        timing_seed=timing_seed,
        separated_requests=separated_requests,
    )
    fire_ids, cancel_one_event_id, cancel_two_event_id, nudge_six_at = _fire_and_cancel_event_ids(
        timing, due_at, separated_requests=separated_requests
    )
    if separated_requests:
        cancel_plan = G7CancelPlan()
        for item in semantics:
            cancel_plan.schedule(item.message)
        first_cancel = cancel_plan.cancel("t_001")
        second_cancel = cancel_plan.cancel("t_002")
        cancel_one = first_cancel.utterance
        cancel_two = second_cancel.utterance
    else:
        cancel_one = "Cancel the first active mint-envelope reminder."
        cancel_two = "Cancel the second active mint-envelope reminder."
    pressure_at = (_PREFIX_PRESSURE_AT_MS[0],) if separated_requests else _PREFIX_PRESSURE_AT_MS
    neutral_at = (_NEUTRAL_AT_MS[0],) if separated_requests else _NEUTRAL_AT_MS
    last_nudge_index = 16 if separated_requests else 24
    cancel_one_at = nudge_six_at - timing.service_ms[last_nudge_index] + 100
    cancel_two_at = nudge_six_at + 100
    if cancel_one_at <= neutral_at[-1] or cancel_two_at <= cancel_one_at:
        raise RuntimeError("timer contention cancellation timing drifted")

    schedule_event_ids = tuple(f"e_{2 + 3 * index:06d}" for index in range(len(instructions)))
    schedules = tuple(
        ScheduleAction(
            type="schedule",
            instruction=_span(
                event_id,
                source,
                instruction,
            ),
            interval_ms=item.interval_ms,
            message=item.message,
        )
        for item, instruction, source, event_id in zip(
            semantics, instructions, sources, schedule_event_ids, strict=True
        )
    )
    setup = tuple(
        action
        for pair in zip(schedules, (_idle() for _ in schedules), strict=True)
        for action in pair
    )
    nudges = tuple(NudgeAction(type="nudge", fire_event_id=event_id) for event_id in fire_ids)
    nudge_wave = (
        tuple(
            action
            for index, nudge in enumerate(nudges)
            for action in (
                (
                    nudge,
                    _idle(
                        IdleReason.ALREADY_HANDLED,
                        fire_ids[0] if index == 0 else fire_ids[1],
                    ),
                )
                if index < len(nudges) - 1
                else (nudge,)
            )
        )
        if separated_requests
        else nudges
    )
    actions = (
        *setup,
        *(_idle() for _ in pressure_at),
        *(_idle() for _ in neutral_at),
        *nudge_wave,
        CancelAction(
            type="cancel",
            instruction=_span(cancel_one_event_id, cancel_one, cancel_one),
            target=CancelTimerTarget(kind="timer", timer_id="t_001"),
        ),
        CancelAction(
            type="cancel",
            instruction=_span(cancel_two_event_id, cancel_two, cancel_two),
            target=CancelTimerTarget(
                kind="timer",
                timer_id="t_002" if separated_requests else "t_003",
            ),
        ),
        _idle(
            IdleReason.ALREADY_HANDLED if separated_requests else IdleReason.NO_TRIGGER,
            fire_ids[1] if separated_requests else None,
        ),
    )
    if len(actions) != len(timing.service_ms):
        raise RuntimeError("timer contention action ledger drifted")
    beats = tuple(f"b{index}" for index in range(len(actions)))
    return ScenarioProgram(
        bundle=bundle,
        template=template,
        family=CorpusFamily.TIMER_CONTENTION,
        master_seed=master_seed,
        timing_plan=timing,
        frames=(
            *(
                _frame(at_ms, instruction)
                for at_ms, instruction in (
                    _separated_schedule_frames(timing, sources)
                    if separated_requests
                    else _schedule_frames(timing, sources)
                )
            ),
            *(
                _frame(
                    at_ms,
                    _pressure(
                        index,
                        master_seed,
                        _REPAIRED_PRESSURE_BYTES
                        if separated_requests
                        else _ACCUMULATED_PRESSURE_BYTES
                        if accumulated_requests
                        else _PRESSURE_BYTES,
                    ),
                )
                for index, at_ms in enumerate(pressure_at, 1)
            ),
            *(
                _frame(at_ms, f"The notebook remains quiet after checkpoint note {index}.")
                for index, at_ms in enumerate(neutral_at, 1)
            ),
            _frame(cancel_one_at, cancel_one),
            _frame(cancel_two_at, cancel_two),
        ),
        actions=actions,
        tool_results=(),
        beat_ids=beats,
        stale_results_by_beat=tuple(BeatStaleResults(beat, ()) for beat in beats),
        perturbations=(DeclaredPerturbation("external_event_contention"),),
        config=_REPAIRED_CONFIG if separated_requests else _CONFIG,
        cancel_resolution_evidence_by_beat=(
            CancelResolutionEvidence(beats[-3], cancel_one_event_id, ("t_001",)),
            CancelResolutionEvidence(
                beats[-2],
                cancel_two_event_id,
                ("t_002" if separated_requests else "t_003",),
            ),
        ),
        require_g7_evidence=True,
    )


def _candidate(parent: GeneratedScenario) -> CorpusSegmentCandidate:
    expected = (
        *(IdleAction for _ in range(3)),
        *(NudgeAction for _ in range(6)),
        *(CancelAction for _ in range(2)),
        IdleAction,
    )
    matches = []
    for index in range(1, len(parent.stream.segments)):
        try:
            candidate = CorpusSegmentCandidate(parent, index, G7_CONTENTION_CHECKPOINT_SHAPE_ID)
        except CorpusSegmentError:
            continue
        if tuple(type(action) for action in candidate.selected_actions) == expected:
            matches.append(candidate)
    if len(matches) != 1:
        raise ValueError("contention checkpoint requires one exact later segment")
    return matches[0]


async def build_g7_contention_checkpoint_catalog(
    registry: AssetRegistry,
    *,
    directory: Path,
    master_seed: str = "g7-contention-checkpoint-v1",
    repository_root: Path | None = None,
) -> tuple[G7ContentionCheckpointEntry, ...]:
    """Execute the TEST-sealed production parent and retain its later segment."""
    parent = await execute_scenario(
        _program(registry, master_seed),
        session_id=G7_CONTENTION_CHECKPOINT_SHAPE_ID,
        directory=directory / G7_CONTENTION_CHECKPOINT_SHAPE_ID,
        repository_root=repository_root,
    )
    return (
        G7ContentionCheckpointEntry(
            G7_CONTENTION_CHECKPOINT_SHAPE_ID,
            parent,
            _candidate(parent),
        ),
    )
