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
    "build_g7_contention_checkpoint_catalog",
)


G7_CONTENTION_CHECKPOINT_SHAPE_ID = "g7-checkpoint-timer-contention-fires-4i-6n-2c"
_CONFIG = RuntimeConfig(context_budget_tokens=7_200)
_PRESSURE_BYTES = 4_000
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


def _idle() -> IdleAction:
    return IdleAction(type="idle", reason=IdleReason.NO_TRIGGER, related_event_id=None)


def _pressure(ordinal: int, master_seed: str) -> str:
    folio = int.from_bytes(sha256(master_seed.encode()).digest()[:4], "big")
    prefix = f"Checkpoint pressure page {ordinal}, folio {folio}: "
    filler = "the atlas notebook remains open beside the field cards. "
    return (prefix + filler * _PRESSURE_BYTES)[:_PRESSURE_BYTES]


def _inputs(registry: AssetRegistry) -> tuple[AssetBundle, AssetRecord, TimerAssetPayload]:
    pool = registry.pool(Split.TEST)
    template = next(
        item for item in pool.templates if CorpusFamily.TIMER_CONTENTION in item.coverage
    )
    timer = next(
        item
        for item in pool.assets
        if CorpusFamily.TIMER_CONTENTION in item.coverage
        and isinstance(item.payload, TimerAssetPayload)
        and item.payload.form is TimerForm.SUPPORTED
    )
    bundle, selected_template = select_approved_scenario_inputs(
        registry,
        split=Split.TEST,
        template_id=template.asset_id,
        asset_ids=(timer.asset_id,),
    )
    return bundle, selected_template, timer.payload


def _timing(interval_ms: int) -> tuple[TimingPlan, tuple[int, ...]]:
    """Pick a seeded plan where every timer fire is real before its nudge."""
    timing = materialize_timing_plan(TimingSeed(Split.TEST, _TIMING_SEED), 28)
    schedule_start = 0
    anchors = []
    for index in range(0, 12, 2):
        anchor = schedule_start + timing.service_ms[index]
        anchors.append(anchor)
        schedule_start = anchor + timing.service_ms[index + 1]
    due_at = tuple(anchor + interval_ms for anchor in anchors)
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
    timing: TimingPlan, due_at: tuple[int, ...]
) -> tuple[tuple[str, ...], str, str, int]:
    """Mirror the real event allocation order around the nudge/cancel wave."""
    next_event = 28  # session, schedules, pressure, checkpoint, and three neutral snapshots.
    fire_ids = [f"e_{next_event:06d}"]
    next_event += 1
    next_due = 1
    now = due_at[0]
    for action_index in range(19, 25):
        now += timing.service_ms[action_index]
        while next_due < len(due_at) and due_at[next_due] < now:
            fire_ids.append(f"e_{next_event:06d}")
            next_event += 1
            next_due += 1
        if action_index == 24:
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


def _program(registry: AssetRegistry, master_seed: str) -> ScenarioProgram:
    bundle, template, timer = _inputs(registry)
    base = validate_timer_asset_semantics_v1(timer.instruction, timer.interval_ms, timer.message)
    semantics = tuple(
        parse_timer_instruction_v1(render_timer_instruction_v1(base.interval_ms, message))
        for message in _MESSAGES
    )
    if len({item.message for item in semantics}) != 6 or any(
        item.interval_ms != base.interval_ms for item in semantics
    ):
        raise RuntimeError("timer semantic ledger drifted")
    timing, due_at = _timing(base.interval_ms)
    fire_ids, cancel_one_event_id, cancel_two_event_id, nudge_six_at = _fire_and_cancel_event_ids(
        timing, due_at
    )
    source = "\n".join(
        render_timer_instruction_v1(item.interval_ms, item.message) for item in semantics
    )
    cancel_one = "Cancel the first active mint-envelope reminder."
    cancel_two = "Cancel the second active mint-envelope reminder."
    cancel_one_at = nudge_six_at - timing.service_ms[24] + 100
    cancel_two_at = nudge_six_at + 100
    if cancel_one_at <= _NEUTRAL_AT_MS[-1] or cancel_two_at <= cancel_one_at:
        raise RuntimeError("timer contention cancellation timing drifted")

    schedule_event_ids = tuple(f"e_{2 + 3 * index:06d}" for index in range(6))
    instructions = source.splitlines()
    actions = (
        *(
            ScheduleAction(
                type="schedule",
                instruction=_span(event_id, instruction, instruction),
                interval_ms=item.interval_ms,
                message=item.message,
            )
            for item, instruction, event_id in zip(
                semantics, instructions, schedule_event_ids, strict=True
            )
        ),
        *(_idle() for _ in semantics),
        *(_idle() for _ in _PREFIX_PRESSURE_AT_MS),
        *(_idle() for _ in _NEUTRAL_AT_MS),
        *(NudgeAction(type="nudge", fire_event_id=event_id) for event_id in fire_ids),
        CancelAction(
            type="cancel",
            instruction=_span(cancel_one_event_id, cancel_one, cancel_one),
            target=CancelTimerTarget(kind="timer", timer_id="t_001"),
        ),
        CancelAction(
            type="cancel",
            instruction=_span(cancel_two_event_id, cancel_two, cancel_two),
            target=CancelTimerTarget(kind="timer", timer_id="t_003"),
        ),
        _idle(),
    )
    actions = (
        tuple(action for pair in zip(actions[:6], actions[6:12], strict=True) for action in pair)
        + actions[12:]
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
                for at_ms, instruction in _schedule_frames(timing, instructions)
            ),
            *(
                _frame(at_ms, _pressure(index, master_seed))
                for index, at_ms in enumerate(_PREFIX_PRESSURE_AT_MS, 1)
            ),
            *(
                _frame(at_ms, f"The notebook remains quiet after checkpoint note {index}.")
                for index, at_ms in enumerate(_NEUTRAL_AT_MS, 1)
            ),
            _frame(cancel_one_at, cancel_one),
            _frame(cancel_two_at, cancel_two),
        ),
        actions=actions,
        tool_results=(),
        beat_ids=beats,
        stale_results_by_beat=tuple(BeatStaleResults(beat, ()) for beat in beats),
        perturbations=(DeclaredPerturbation("external_event_contention"),),
        config=_CONFIG,
        cancel_resolution_evidence_by_beat=(
            CancelResolutionEvidence("b25", cancel_one_event_id, ("t_001",)),
            CancelResolutionEvidence("b26", cancel_two_event_id, ("t_003",)),
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
