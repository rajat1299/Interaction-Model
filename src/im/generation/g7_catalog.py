"""Additive G7 fresh-session recipes; this is deliberately not a scenario DSL."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from im.assets.model import (
    AssetRecord,
    CorpusFamily,
    LookupAssetPayload,
    Split,
    TextAssetPayload,
    TextForm,
    TimerAssetPayload,
    artifact_digest,
)
from im.assets.registry import AssetBundle, AssetRegistry
from im.canonical_json import canonicalize_tim_json, parse_tim_json
from im.generation.ingestion import ScheduledSamplerFrame
from im.generation.mark_negative_policy import mark_negative_idle_reason
from im.generation.oracle import BeatOpening, BeatResponseWarrant, ResponseWarrantKind
from im.generation.scenarios import (
    BeatStaleResults,
    CounterfactualDeclaration,
    DeclaredPerturbation,
    ScenarioProgram,
    select_approved_scenario_inputs,
)
from im.generation.timer_instruction_semantics import (
    TimerInstructionSemanticsV1,
    render_timer_instruction_v1,
    validate_timer_asset_semantics_v1,
)
from im.generation.timing import TimingPlan, TimingSeed, materialize_timing_plan
from im.schema.actions import (
    DelegateAction,
    IdleAction,
    IdleReason,
    IntegrateAction,
    MarkAction,
    NudgeAction,
    RespondAction,
    ScheduleAction,
    Span,
)
from im.schema.common import ToolName
from im.schema.textspan import utf16_len
from im.tools import ScriptedToolResult

G7_FRESH_SHAPES = (
    ("g7-fresh-neutral-10i", CorpusFamily.NEUTRAL_TYPING, "10I"),
    ("g7-fresh-mark-positive-a-5i-7m", CorpusFamily.MARK_POSITIVE, "5I+7M"),
    ("g7-fresh-mark-positive-b-6i-8m", CorpusFamily.MARK_POSITIVE, "6I+8M"),
    ("g7-fresh-mark-negative-7i-3m", CorpusFamily.MARK_NEGATIVE, "7I+3M"),
    ("g7-fresh-lookup-live-2i-2d-2g", CorpusFamily.LOOKUP_LIVE, "2I+2D+2G"),
    (
        "g7-fresh-timer-normal-wide-3i-5h-10n",
        CorpusFamily.TIMER_NORMAL,
        "3I+5H+10N",
    ),
    (
        "g7-fresh-timer-normal-compact-4i-4h-6n",
        CorpusFamily.TIMER_NORMAL,
        "4I+4H+6N",
    ),
    (
        "g7-fresh-timer-contention-control-2i-2h-2m",
        CorpusFamily.TIMER_CONTENTION,
        "2I+2H+2M",
    ),
    ("g7-fresh-reserved-10i", CorpusFamily.RESERVED, "10I"),
    (
        "g7-fresh-timer-normal-wide-context-3i-5h-10n",
        CorpusFamily.TIMER_NORMAL,
        "3I+5H+10N",
    ),
    (
        "g7-fresh-timer-normal-compact-context-4i-4h-6n",
        CorpusFamily.TIMER_NORMAL,
        "4I+4H+6N",
    ),
)

_TIMER_NORMAL_WIDE = {
    Split.TRAIN: "g7-timer-normal-wide-semantic-v2:train:39",
    Split.DEV: "g7-timer-normal-wide-semantic-v2:dev:7",
    Split.TEST: "g7-timer-normal-wide-semantic-v2:test:45",
    Split.DEMO: "g7-timer-normal-wide-semantic-v2:demo:5",
}
_TIMER_NORMAL_COMPACT = {
    Split.TRAIN: "g7-timer-normal-compact-semantic-v2:train:3687",
    Split.DEV: "g7-timer-normal-compact-semantic-v2:dev:5212",
    Split.TEST: "g7-timer-normal-compact-semantic-v2:test:1419",
    Split.DEMO: "g7-timer-normal-compact-semantic-v2:demo:2438",
}
_CONTENTION = {
    Split.TRAIN: "g7-c3-12",
    Split.DEV: "g7-c3-101",
    Split.TEST: "g7-c3-5",
    Split.DEMO: "g7-c3-72",
}
_PERTURBATION = {
    CorpusFamily.NEUTRAL_TYPING: "draft_revision",
    CorpusFamily.MARK_POSITIVE: "mark_targeting",
    CorpusFamily.MARK_NEGATIVE: "mark_restraint",
    CorpusFamily.LOOKUP_LIVE: "tool_result",
    CorpusFamily.TIMER_NORMAL: "timer_fire",
    CorpusFamily.TIMER_CONTENTION: "external_event_contention",
    CorpusFamily.RESERVED: "annotation_safety",
}
_RESPONSE_FAMILIES = (
    CorpusFamily.NEUTRAL_TYPING,
    CorpusFamily.MARK_POSITIVE,
    CorpusFamily.MARK_NEGATIVE,
    CorpusFamily.LOOKUP_LIVE,
    CorpusFamily.LOOKUP_STALE,
)
_TIMER_CONTEXTS = (
    "desk note",
    "field log",
    "archive checklist",
    "notebook draft",
    "registry page",
    "shoreline notes",
    "cistern sketch",
    "atlas card",
    "planning sheet",
    "rehearsal notes",
)


@dataclass(frozen=True, slots=True)
class FloorOpeningTwinPrograms:
    """The two inseparable members of one G7 floor-opening contrast."""

    family: CorpusFamily
    group_id: str
    variant: int
    programs: tuple[ScenarioProgram, ScenarioProgram]

    def __post_init__(self) -> None:
        active, yielded = self.programs
        expected_ids = ("active", "yielded")
        if (
            self.variant < 0
            or active.family is not self.family
            or yielded.family is not self.family
            or active.bundle != yielded.bundle
            or active.template != yielded.template
            or active.master_seed != yielded.master_seed
            or active.timing_plan != yielded.timing_plan
            or active.tool_results != yielded.tool_results
            or active.annotations != yielded.annotations
            or active.config != yielded.config
            or active.beat_ids != yielded.beat_ids
            or active.stale_results_by_beat != yielded.stale_results_by_beat
            or active.perturbations != yielded.perturbations
            or active.counterfactual is None
            or yielded.counterfactual is None
        ):
            raise ValueError("floor-opening twin members must remain a complete shared pair")
        for member, member_id in zip(self.programs, expected_ids, strict=True):
            link = member.counterfactual
            assert link is not None
            if (
                link.kind.value != "twin"
                or link.group_id != self.group_id
                or link.member_id != member_id
                or link.member_ids != expected_ids
                or link.flipped_perturbation.value != "floor_opening"
            ):
                raise ValueError("floor-opening twin linkage is incomplete")
        active_frames = tuple(parse_tim_json(frame.raw_bytes) for frame in active.frames)
        yielded_frames = tuple(parse_tim_json(frame.raw_bytes) for frame in yielded.frames)
        if len(active_frames) != len(yielded_frames) or any(
            not isinstance(left, dict)
            or not isinstance(right, dict)
            or left.get("activity") != "active"
            or right.get("activity") != "paused"
            or frame_a.at_ms != frame_b.at_ms
            or {key: value for key, value in left.items() if key != "activity"}
            != {key: value for key, value in right.items() if key != "activity"}
            for frame_a, frame_b, left, right in zip(
                active.frames,
                yielded.frames,
                active_frames,
                yielded_frames,
                strict=True,
            )
        ):
            raise ValueError("floor-opening twins may flip only frame activity")
        if (
            len(active.response_warrants_by_beat) != len(active.actions)
            or len(yielded.response_warrants_by_beat) != len(yielded.actions)
            or active.openings_by_beat != ()
            or yielded.openings_by_beat is None
            or tuple(item.beat_id for item in yielded.openings_by_beat) != yielded.beat_ids
        ):
            raise ValueError("floor-opening twins must declare only yielded openings")
        if any(
            not isinstance(left, IdleAction)
            or left.reason is not IdleReason.AWAITING_OPENING
            or not isinstance(right, RespondAction)
            or left.related_event_id != active.response_warrants_by_beat[index].snapshot_event_id
            or right.reply_to_event_id != yielded.response_warrants_by_beat[index].snapshot_event_id
            or yielded.openings_by_beat[index].snapshot_event_id != right.reply_to_event_id
            for index, (left, right) in enumerate(zip(active.actions, yielded.actions, strict=True))
        ):
            raise ValueError("floor-opening twin actions are not exact idle/respond mirrors")


@dataclass(frozen=True, slots=True)
class G7FamilyInputs:
    """Approved, family-specific inputs used by the additive G7 recipes."""

    template_id: str
    asset_ids: tuple[str, ...]


def build_g7_fresh_session_programs(
    registry: AssetRegistry,
    *,
    split: Split | str,
    inputs: Mapping[CorpusFamily, G7FamilyInputs],
    master_seed: str,
    explicit_lookup_requests: bool = False,
) -> tuple[tuple[str, ScenarioProgram], ...]:
    """Build each newly reachable G7 fresh-session action shape once."""
    selected = {
        family: select_approved_scenario_inputs(
            registry,
            split=split,
            template_id=_inputs_for(inputs, family).template_id,
            asset_ids=_inputs_for(inputs, family).asset_ids,
        )
        for family in {shape[1] for shape in G7_FRESH_SHAPES}
    }
    return (
        (
            G7_FRESH_SHAPES[0][0],
            _idle_recipe(
                *selected[CorpusFamily.NEUTRAL_TYPING], CorpusFamily.NEUTRAL_TYPING, master_seed
            ),
        ),
        (
            G7_FRESH_SHAPES[1][0],
            _mark_recipe(
                *selected[CorpusFamily.MARK_POSITIVE], CorpusFamily.MARK_POSITIVE, master_seed, 5, 7
            ),
        ),
        (
            G7_FRESH_SHAPES[2][0],
            _mark_recipe(
                *selected[CorpusFamily.MARK_POSITIVE], CorpusFamily.MARK_POSITIVE, master_seed, 6, 8
            ),
        ),
        (
            G7_FRESH_SHAPES[3][0],
            _mark_recipe(
                *selected[CorpusFamily.MARK_NEGATIVE], CorpusFamily.MARK_NEGATIVE, master_seed, 7, 3
            ),
        ),
        (
            G7_FRESH_SHAPES[4][0],
            _lookup_recipe(
                *selected[CorpusFamily.LOOKUP_LIVE],
                master_seed,
                explicit_requests=explicit_lookup_requests,
            ),
        ),
        (
            G7_FRESH_SHAPES[5][0],
            _timer_normal_wide(*selected[CorpusFamily.TIMER_NORMAL], master_seed),
        ),
        (
            G7_FRESH_SHAPES[6][0],
            _timer_normal_compact(*selected[CorpusFamily.TIMER_NORMAL], master_seed),
        ),
        (
            G7_FRESH_SHAPES[7][0],
            _timer_contention_control(*selected[CorpusFamily.TIMER_CONTENTION], master_seed),
        ),
        (
            G7_FRESH_SHAPES[8][0],
            _idle_recipe(*selected[CorpusFamily.RESERVED], CorpusFamily.RESERVED, master_seed),
        ),
        (
            G7_FRESH_SHAPES[9][0],
            _timer_normal_wide(*selected[CorpusFamily.TIMER_NORMAL], master_seed, contextual=True),
        ),
        (
            G7_FRESH_SHAPES[10][0],
            _timer_normal_compact(
                *selected[CorpusFamily.TIMER_NORMAL], master_seed, contextual=True
            ),
        ),
    )


def build_g7_timer_wave0_fresh_programs(
    registry: AssetRegistry,
    *,
    split: Split | str,
    normal_inputs: G7FamilyInputs,
    contention_inputs: G7FamilyInputs,
    master_seed: str,
    normal_contextual: bool = False,
    post_confirmation_gap_ms: int = 0,
    accumulated_requests: bool = False,
) -> tuple[tuple[str, ScenarioProgram], ...]:
    """Build only the three timer shapes needed by a Phase 2 wave-zero canary.

    This narrow public entry point deliberately reuses the exact fresh-session
    recipes below without forcing a caller to manufacture inputs for every
    unrelated G7 family.  It is split-parametric and therefore does not alter
    the historical TEST readiness catalog.
    """
    if post_confirmation_gap_ms and not 3_000 <= post_confirmation_gap_ms <= 5_000:
        raise ValueError("post-confirmation gap must be zero or 3–5 seconds")
    if post_confirmation_gap_ms and accumulated_requests:
        raise ValueError("timer repair modes are mutually exclusive")
    normal = select_approved_scenario_inputs(
        registry,
        split=split,
        template_id=normal_inputs.template_id,
        asset_ids=normal_inputs.asset_ids,
    )
    contention = select_approved_scenario_inputs(
        registry,
        split=split,
        template_id=contention_inputs.template_id,
        asset_ids=contention_inputs.asset_ids,
    )
    return (
        (
            "timer-normal-wide",
            _timer_normal_wide(
                *normal,
                master_seed,
                contextual=normal_contextual,
                post_confirmation_gap_ms=post_confirmation_gap_ms,
                accumulated_requests=accumulated_requests,
            ),
        ),
        (
            "timer-normal-compact",
            _timer_normal_compact(
                *normal,
                master_seed,
                contextual=normal_contextual,
                post_confirmation_gap_ms=post_confirmation_gap_ms,
                accumulated_requests=accumulated_requests,
            ),
        ),
        (
            "timer-contention-control",
            _timer_contention_control(
                *contention,
                master_seed,
                post_confirmation_gap_ms=post_confirmation_gap_ms,
                accumulated_requests=accumulated_requests,
            ),
        ),
    )


def build_g7_mark_fresh_programs(
    registry: AssetRegistry,
    *,
    split: Split | str,
    positive_inputs: G7FamilyInputs,
    negative_inputs: G7FamilyInputs,
    master_seed: str,
) -> tuple[tuple[str, ScenarioProgram], ...]:
    """Build only the three quota-shaped mark programs."""
    positive = select_approved_scenario_inputs(
        registry,
        split=split,
        template_id=positive_inputs.template_id,
        asset_ids=positive_inputs.asset_ids,
    )
    negative = select_approved_scenario_inputs(
        registry,
        split=split,
        template_id=negative_inputs.template_id,
        asset_ids=negative_inputs.asset_ids,
    )
    return (
        (
            "mark-positive-a",
            _mark_recipe(*positive, CorpusFamily.MARK_POSITIVE, master_seed, 5, 7),
        ),
        (
            "mark-positive-b",
            _mark_recipe(*positive, CorpusFamily.MARK_POSITIVE, master_seed, 6, 8),
        ),
        (
            "mark-negative",
            _mark_recipe(*negative, CorpusFamily.MARK_NEGATIVE, master_seed, 7, 3),
        ),
    )


def build_g7_lookup_live_program(
    registry: AssetRegistry,
    *,
    split: Split | str,
    inputs: G7FamilyInputs,
    master_seed: str,
) -> ScenarioProgram:
    """Build the live-lookup shape with explicit requests and natural result text."""
    selected = select_approved_scenario_inputs(
        registry,
        split=split,
        template_id=inputs.template_id,
        asset_ids=inputs.asset_ids,
    )
    return _lookup_recipe(
        *selected,
        master_seed,
        explicit_requests=True,
    )


def build_g7_floor_opening_twin_programs(
    registry: AssetRegistry,
    *,
    split: Split | str,
    inputs: Mapping[CorpusFamily, G7FamilyInputs],
    master_seed: str,
    variant: int = 0,
) -> tuple[FloorOpeningTwinPrograms, ...]:
    """Build all five inseparable response-floor pairs for one review variant."""
    if isinstance(variant, bool) or variant not in (0, 1, 2):
        raise ValueError("variant must be one of 0, 1, or 2")
    return tuple(
        _floor_opening_twin(
            *select_approved_scenario_inputs(
                registry,
                split=split,
                template_id=_inputs_for(inputs, family).template_id,
                asset_ids=_inputs_for(inputs, family).asset_ids,
            ),
            family,
            master_seed,
            variant,
        )
        for family in _RESPONSE_FAMILIES
    )


def _idle_recipe(
    bundle: AssetBundle, template: AssetRecord, family: CorpusFamily, master_seed: str
) -> ScenarioProgram:
    plan = _timing(bundle.split, f"g7-fresh:{family.value}:{master_seed}", 10)
    text = _family_text(bundle, family)
    return _program(
        bundle,
        template,
        family,
        master_seed,
        plan,
        _decision_frames(text, plan),
        (_idle(),) * 10,
    )


def _mark_recipe(
    bundle: AssetBundle,
    template: AssetRecord,
    family: CorpusFamily,
    master_seed: str,
    idle_count: int,
    mark_count: int,
    *,
    lead_in: str | None = None,
) -> ScenarioProgram:
    if family is CorpusFamily.MARK_NEGATIVE:
        return _negative_mark_recipe(
            bundle,
            template,
            master_seed,
            idle_count,
            mark_count,
            lead_in=lead_in,
        )
    plan = _timing(
        bundle.split,
        f"g7-fresh:{family.value}:{idle_count}:{master_seed}",
        idle_count + mark_count,
    )
    asset = _text_asset(bundle, family)
    instruction = asset.payload.text
    assert isinstance(asset.payload, TextAssetPayload)
    target = next(
        (item for item in asset.protected_values if item in instruction), instruction.split()[0]
    )
    visible_instruction = f"{lead_in}\n{instruction}" if lead_in else instruction
    target_text = _multi_target_text(instruction, target, mark_count)
    if lead_in:
        target_text = f"{lead_in}\n{target_text}"
    target_at = plan.service_ms[0] + 1
    last_mark_done = target_at + sum(plan.service_ms[1 : mark_count + 1])
    at_ms = last_mark_done + plan.service_ms[mark_count + 1] + 1
    frames = [_frame(0, visible_instruction), _frame(target_at, target_text)]
    for index in range(idle_count - 2):
        frames.append(_frame(at_ms, visible_instruction))
        at_ms += plan.service_ms[mark_count + 2 + index] + 1
    marks = tuple(
        MarkAction(
            type="mark",
            instruction=_span("e_000002", visible_instruction, instruction),
            target=_span_occurrence("e_000003", target_text, target, index + 1),
        )
        for index in range(mark_count)
    )
    actions = (_idle(), *marks, *(_idle() for _ in range(idle_count - 1)))
    return _program(bundle, template, family, master_seed, plan, tuple(frames), actions)


def _negative_mark_recipe(
    bundle: AssetBundle,
    template: AssetRecord,
    master_seed: str,
    idle_count: int,
    mark_count: int,
    *,
    lead_in: str | None = None,
) -> ScenarioProgram:
    """Keep the direct control in history while non-direct states own every idle beat."""
    family = CorpusFamily.MARK_NEGATIVE
    plan = _timing(
        bundle.split,
        f"g7-fresh:{family.value}:{idle_count}:{master_seed}",
        idle_count + mark_count,
    )
    control = _text_asset(bundle, CorpusFamily.MARK_POSITIVE)
    assert isinstance(control.payload, TextAssetPayload)
    if control.payload.form is not TextForm.DIRECT:
        raise ValueError("mark-negative G7 recipe requires a direct positive control asset")
    target = next(
        (item for item in control.protected_values if item in control.payload.text),
        control.payload.text.split()[0],
    )
    negative_assets = tuple(
        item
        for item in bundle.assets
        if family in item.coverage
        and isinstance(item.payload, TextAssetPayload)
        and item.payload.form is not TextForm.DIRECT
    )
    if not negative_assets:
        raise ValueError("mark-negative G7 recipe requires non-direct negative-state assets")

    def idle_for(asset: AssetRecord) -> IdleAction:
        assert isinstance(asset.payload, TextAssetPayload)
        reason = mark_negative_idle_reason(
            asset.payload.form,
            partial_form_reason=IdleReason.TYPING_ACTIVE,
        )
        return _idle(reason)

    s = plan.service_ms
    control_text = control.payload.text
    visible_control = f"{lead_in}\n{control_text}" if lead_in else control_text
    first_negative = negative_assets[0]
    assert isinstance(first_negative.payload, TextAssetPayload)
    target_text = _multi_target_text(control_text, target, mark_count)
    if lead_in:
        target_text = f"{lead_in}\n{target_text}"
    target_at = s[0] + 1
    frames = [_frame(0, visible_control), _frame(target_at, target_text)]
    if first_negative.payload.form is TextForm.AMBIGUOUS:
        negative_sequence = (
            first_negative,
            first_negative,
            *(
                negative_assets[(index + 1) % len(negative_assets)]
                for index in range(idle_count - 4)
            ),
        )
    else:
        negative_sequence = tuple(
            negative_assets[index % len(negative_assets)]
            for index in range(idle_count - 2)
        )
    at_ms = target_at + sum(s[1 : mark_count + 2]) + 1
    for index, asset in enumerate(negative_sequence):
        assert isinstance(asset.payload, TextAssetPayload)
        text = asset.payload.text
        if index == 0:
            text = f"{target_text}\n{text}"
        elif index == 1 and first_negative.payload.form is TextForm.AMBIGUOUS:
            text = (
                f"{target_text}\n{first_negative.payload.text}\n"
                f"A later note mentions {target}."
            )
        frames.append(
            _frame(
                at_ms,
                text,
                activity=(
                    "active"
                    if asset.payload.form in {TextForm.AMBIGUOUS, TextForm.PARTIAL}
                    else "paused"
                ),
            )
        )
        if index + 1 < len(negative_sequence):
            at_ms += s[mark_count + 2 + index] + 1
    marks = tuple(
        MarkAction(
            type="mark",
            instruction=_span("e_000002", visible_control, control_text),
            target=_span_occurrence("e_000003", target_text, target, index + 1),
        )
        for index in range(mark_count)
    )
    actions = (
        _idle(),
        *marks,
        _idle(),
        *(idle_for(asset) for asset in negative_sequence),
    )
    return _program(bundle, template, family, master_seed, plan, tuple(frames), actions)


def _lookup_recipe(
    bundle: AssetBundle,
    template: AssetRecord,
    master_seed: str,
    *,
    explicit_requests: bool = False,
    restate_subject: bool = False,
) -> ScenarioProgram:
    family = CorpusFamily.LOOKUP_LIVE
    first_lookup, second_lookup = _lookup_assets(bundle)
    plan = _timing(bundle.split, f"g7-fresh:{family.value}:{master_seed}", 6)
    latency = max(plan.service_ms[1], plan.service_ms[4]) + 100
    first_result_at = plan.service_ms[0] + latency
    third_at = first_result_at + plan.service_ms[2] + 1
    fourth_at = third_at + plan.service_ms[3] + 1
    first_source = (
        f"Look up {first_lookup.query}." if explicit_requests else first_lookup.query
    )
    second_source = (
        f"Look up {second_lookup.query}." if explicit_requests else second_lookup.query
    )
    first_result = (
        f"{first_lookup.query}: {first_lookup.result_a}"
        if restate_subject
        else first_lookup.result_a
    )
    second_result = (
        f"{second_lookup.query}: {second_lookup.result_b}"
        if restate_subject
        else second_lookup.result_b
    )
    actions = (
        _delegate("e_000002", first_lookup.query, source=first_source),
        _idle(IdleReason.AWAITING_TOOL, "e_000002"),
        IntegrateAction(type="integrate", result_event_id="e_000006", text=first_result),
        _delegate("e_000008", second_lookup.query, source=second_source),
        _idle(IdleReason.AWAITING_TOOL, "e_000008"),
        IntegrateAction(type="integrate", result_event_id="e_000012", text=second_result),
    )
    return _program(
        bundle,
        template,
        family,
        master_seed,
        plan,
        (
            _frame(0, first_source),
            _frame(plan.service_ms[0] + 1, first_source),
            _frame(third_at, second_source),
            _frame(fourth_at, second_source),
        ),
        actions,
        tool_results=(
            ScriptedToolResult(latency_ms=latency, data={"nonce": first_result}),
            ScriptedToolResult(latency_ms=latency, data={"nonce": second_result}),
        ),
        openings=(BeatOpening("b2", "e_000005"), BeatOpening("b5", "e_000011")),
    )


def _timer_normal_wide(
    bundle: AssetBundle,
    template: AssetRecord,
    master_seed: str,
    *,
    contextual: bool = False,
    post_confirmation_gap_ms: int = 0,
    accumulated_requests: bool = False,
) -> ScenarioProgram:
    family = CorpusFamily.TIMER_NORMAL
    seed = _TIMER_NORMAL_WIDE[bundle.split]
    plan = _timing(bundle.split, seed, 30 if post_confirmation_gap_ms else 18)
    timer = _payload(bundle, family, TimerAssetPayload)
    assert isinstance(timer, TimerAssetPayload)
    semantics = _timer_variants(_timer_semantics(timer), master_seed, "timer-normal-wide", 5)
    s = plan.service_ms
    texts = _timer_texts(
        master_seed,
        "timer-normal-wide",
        tuple(
            render_timer_instruction_v1(
                item.interval_ms,
                item.message,
                explicit_additional=bool(
                    (post_confirmation_gap_ms or accumulated_requests) and index
                ),
            )
            for index, item in enumerate(semantics)
        ),
        contextual=contextual,
    )
    source_ids = ("e_000002", "e_000005", "e_000008", "e_000011", "e_000014")
    if not post_confirmation_gap_ms:
        source_ids = ("e_000002", "e_000003", "e_000006", "e_000009", "e_000012")
    sources = (
        tuple("\n".join(texts[: index + 1]) for index in range(len(texts)))
        if accumulated_requests
        else texts
    )
    schedules = tuple(
        _schedule(
            event_id,
            text,
            item,
            explicit_additional=bool(
                (post_confirmation_gap_ms or accumulated_requests) and index
            ),
        )
        for index, (event_id, text, item) in enumerate(
            zip(source_ids, sources, semantics, strict=True)
        )
    )
    schedule_wave = (
        tuple(action for schedule in schedules for action in (schedule, _idle()))
        if post_confirmation_gap_ms
        else (*schedules, _idle())
    )
    if post_confirmation_gap_ms:
        first_fire_ids = tuple(f"e_{event:06d}" for event in (17, 19, 21, 23, 25))
        second_fire_ids = tuple(f"e_{event:06d}" for event in (27, 29, 31, 33, 35))
        nudge_wave = tuple(
            action
            for fire_event_id in (*first_fire_ids, *second_fire_ids)
            for action in (
                NudgeAction(type="nudge", fire_event_id=fire_event_id),
                _idle(IdleReason.ALREADY_HANDLED, first_fire_ids[0]),
            )
        )
        actions = (*schedule_wave, *nudge_wave)
    else:
        first_fire_ids = tuple(f"e_{event:06d}" for event in (17, 18, 20, 22, 24))
        second_fire_ids = tuple(f"e_{event:06d}" for event in (27, 28, 30, 32, 34))
        handled_idle = (
            _idle(IdleReason.ALREADY_HANDLED, first_fire_ids[0])
            if accumulated_requests
            else _idle()
        )
        actions = (
            *schedule_wave,
            *(NudgeAction(type="nudge", fire_event_id=event_id) for event_id in first_fire_ids),
            handled_idle,
            *(NudgeAction(type="nudge", fire_event_id=event_id) for event_id in second_fire_ids),
            handled_idle,
        )
    if post_confirmation_gap_ms:
        at_ms = [0]
        for action_index in (0, 2, 4, 6):
            at_ms.append(at_ms[-1] + s[action_index] + post_confirmation_gap_ms)
    else:
        at_ms = [0, s[0] - 1, s[0] + s[1] - 1, s[0] + s[1] + s[2] - 1, sum(s[:4]) - 1]
    return _program(
        bundle,
        template,
        family,
        master_seed,
        plan,
        tuple(_frame(at, text) for at, text in zip(at_ms, sources, strict=True)),
        actions,
    )


def _timer_normal_compact(
    bundle: AssetBundle,
    template: AssetRecord,
    master_seed: str,
    *,
    contextual: bool = False,
    post_confirmation_gap_ms: int = 0,
    accumulated_requests: bool = False,
) -> ScenarioProgram:
    family = CorpusFamily.TIMER_NORMAL
    seed = _TIMER_NORMAL_COMPACT[bundle.split]
    plan = _timing(bundle.split, seed, 21 if post_confirmation_gap_ms else 14)
    timer = _payload(bundle, family, TimerAssetPayload)
    assert isinstance(timer, TimerAssetPayload)
    semantics = _timer_variants(_timer_semantics(timer), master_seed, "timer-normal-compact", 4)
    s = plan.service_ms
    texts = _timer_texts(
        master_seed,
        "timer-normal-compact",
        tuple(
            render_timer_instruction_v1(
                item.interval_ms,
                item.message,
                explicit_additional=bool(
                    (post_confirmation_gap_ms or accumulated_requests) and index
                ),
            )
            for index, item in enumerate(semantics)
        ),
        contextual=contextual,
    )
    source_ids = (
        ("e_000003", "e_000006", "e_000009", "e_000012")
        if post_confirmation_gap_ms
        else ("e_000003", "e_000004", "e_000007", "e_000010")
    )
    sources = (
        tuple("\n".join(texts[: index + 1]) for index in range(len(texts)))
        if accumulated_requests
        else texts
    )
    schedules = tuple(
        _schedule(
            event_id,
            text,
            item,
            explicit_additional=bool(
                (post_confirmation_gap_ms or accumulated_requests) and index
            ),
        )
        for index, (event_id, text, item) in enumerate(
            zip(source_ids, sources, semantics, strict=True)
        )
    )
    schedule_wave = (
        tuple(action for schedule in schedules for action in (schedule, _idle()))
        if post_confirmation_gap_ms
        else (*schedules, _idle())
    )
    if post_confirmation_gap_ms:
        first_fire_ids = tuple(f"e_{event:06d}" for event in (15, 17, 19, 21))
        second_fire_ids = tuple(f"e_{event:06d}" for event in (23, 25))
        nudge_wave = tuple(
            action
            for fire_event_id in (*first_fire_ids, *second_fire_ids)
            for action in (
                NudgeAction(type="nudge", fire_event_id=fire_event_id),
                _idle(IdleReason.ALREADY_HANDLED, first_fire_ids[0]),
            )
        )
        actions = (_idle(), *schedule_wave, *nudge_wave)
    else:
        first_fire_ids = tuple(f"e_{event:06d}" for event in (15, 16, 18, 20))
        second_fire_ids = tuple(f"e_{event:06d}" for event in (23, 24))
        handled_idle = (
            _idle(IdleReason.ALREADY_HANDLED, first_fire_ids[0])
            if accumulated_requests
            else _idle()
        )
        actions = (
            _idle(),
            *schedule_wave,
            *(NudgeAction(type="nudge", fire_event_id=event_id) for event_id in first_fire_ids),
            handled_idle,
            *(NudgeAction(type="nudge", fire_event_id=event_id) for event_id in second_fire_ids),
            handled_idle,
        )
    first_schedule_at = s[0] + 1
    if post_confirmation_gap_ms:
        schedule_at = [first_schedule_at]
        for action_index in (1, 3, 5):
            schedule_at.append(schedule_at[-1] + s[action_index] + post_confirmation_gap_ms)
    else:
        schedule_at = [
            first_schedule_at,
            first_schedule_at + s[1] - 1,
            first_schedule_at + s[1] + s[2] - 1,
            first_schedule_at + s[1] + s[2] + s[3] - 1,
        ]
    return _program(
        bundle,
        template,
        family,
        master_seed,
        plan,
        (
            _frame(0, _timer_preface()),
            *(_frame(at, text) for at, text in zip(schedule_at, sources, strict=True)),
        ),
        actions,
    )


def _timer_preface() -> str:
    """Return a deterministic neutral preface before the compact timer wave."""
    return "The next reminder is being prepared."


def _timer_contention_control(
    bundle: AssetBundle,
    template: AssetRecord,
    master_seed: str,
    *,
    post_confirmation_gap_ms: int = 0,
    accumulated_requests: bool = False,
) -> ScenarioProgram:
    family = CorpusFamily.TIMER_CONTENTION
    seed = _CONTENTION[bundle.split]
    plan = _timing(bundle.split, seed, 8 if post_confirmation_gap_ms else 6)
    timer = _payload(bundle, family, TimerAssetPayload)
    mark_asset = _text_asset(bundle, CorpusFamily.MARK_POSITIVE)
    assert isinstance(timer, TimerAssetPayload)
    semantics = _timer_variants(_timer_semantics(timer), master_seed, "timer-contention-control", 2)
    assert isinstance(mark_asset.payload, TextAssetPayload)
    mark_text = mark_asset.payload.text
    target = next(
        (item for item in mark_asset.protected_values if item in mark_text), mark_text.split()[0]
    )
    texts = _timer_texts(
        master_seed,
        "timer-contention-control",
        tuple(
            render_timer_instruction_v1(
                item.interval_ms,
                item.message,
                explicit_additional=bool(
                    (post_confirmation_gap_ms or accumulated_requests) and index
                ),
            )
            for index, item in enumerate(semantics)
        ),
        contextual=True,
    )
    opening = f"{texts[0]}\n{mark_text}"
    second_source = f"{opening}\n{texts[1]}" if accumulated_requests else texts[1]
    target_text = _multi_target_text(mark_text, target, 2)
    second_schedule_at = plan.service_ms[0] + (
        post_confirmation_gap_ms if post_confirmation_gap_ms else -1
    )
    target_at = second_schedule_at + (
        plan.service_ms[2] + plan.service_ms[3] + 100
        if post_confirmation_gap_ms
        else plan.service_ms[1]
    )
    idle_text = "The notebook is open beside the window."
    mark_start_index = 4 if post_confirmation_gap_ms else 2
    first_idle_at = (
        target_at + plan.service_ms[mark_start_index] + plan.service_ms[mark_start_index + 1] + 1
    )
    first_schedule = _schedule("e_000002", opening, semantics[0])
    second_schedule = _schedule(
        "e_000005" if post_confirmation_gap_ms else "e_000003",
        second_source,
        semantics[1],
        explicit_additional=bool(post_confirmation_gap_ms or accumulated_requests),
    )
    schedule_wave = (
        (first_schedule, _idle(), second_schedule, _idle())
        if post_confirmation_gap_ms
        else (first_schedule, second_schedule)
    )
    actions = (
        *schedule_wave,
        MarkAction(
            type="mark",
            instruction=_span("e_000002", opening, mark_text),
            target=_span_occurrence(
                "e_000008" if post_confirmation_gap_ms else "e_000006",
                target_text,
                target,
                1,
            ),
        ),
        MarkAction(
            type="mark",
            instruction=_span("e_000002", opening, mark_text),
            target=_span_occurrence(
                "e_000008" if post_confirmation_gap_ms else "e_000006",
                target_text,
                target,
                2,
            ),
        ),
        _idle(),
        _idle(),
    )
    return _program(
        bundle,
        template,
        family,
        master_seed,
        plan,
        (
            _frame(0, opening),
            _frame(second_schedule_at, second_source),
            _frame(target_at, target_text),
            _frame(first_idle_at, idle_text),
        ),
        actions,
    )


def _floor_opening_twin(
    bundle: AssetBundle,
    template: AssetRecord,
    family: CorpusFamily,
    master_seed: str,
    variant: int,
) -> FloorOpeningTwinPrograms:
    plan = _timing(bundle.split, f"g7-floor-opening:{family.value}:{master_seed}:v{variant}", 10)
    invitations, replies = _response_openings(_family_text(bundle, family), variant)
    group_id = (
        "g7-floor-"
        + artifact_digest(
            {
                "family": family.value,
                "master_seed": master_seed,
                "variant": variant,
                "assets": tuple(asset.asset_id for asset in bundle.assets),
            }
        )[7:23]
    )
    yielded_ids = tuple(f"e_{2 * index + 2:06d}" for index in range(10))
    active = _program(
        bundle,
        template,
        family,
        master_seed,
        plan,
        _decision_frames_for_texts(invitations, plan, activity="active"),
        tuple(_idle(IdleReason.AWAITING_OPENING, f"e_{index + 2:06d}") for index in range(10)),
        counterfactual=_floor_link(group_id, "active"),
        warrants=tuple(
            BeatResponseWarrant(f"b{index}", f"e_{index + 2:06d}", ResponseWarrantKind.INVITATION)
            for index in range(10)
        ),
    )
    yielded = _program(
        bundle,
        template,
        family,
        master_seed,
        plan,
        _decision_frames_for_texts(invitations, plan),
        tuple(
            RespondAction(type="respond", reply_to_event_id=event_id, text=reply)
            for event_id, reply in zip(yielded_ids, replies, strict=True)
        ),
        counterfactual=_floor_link(group_id, "yielded"),
        warrants=tuple(
            BeatResponseWarrant(f"b{index}", event_id, ResponseWarrantKind.INVITATION)
            for index, event_id in enumerate(yielded_ids)
        ),
        openings=tuple(
            BeatOpening(f"b{index}", event_id) for index, event_id in enumerate(yielded_ids)
        ),
    )
    return FloorOpeningTwinPrograms(family, group_id, variant, (active, yielded))


def _program(
    bundle: AssetBundle,
    template: AssetRecord,
    family: CorpusFamily,
    master_seed: str,
    plan: TimingPlan,
    frames: tuple[ScheduledSamplerFrame, ...],
    actions: tuple[object, ...],
    *,
    tool_results: tuple[ScriptedToolResult, ...] = (),
    counterfactual: CounterfactualDeclaration | None = None,
    warrants: tuple[BeatResponseWarrant, ...] = (),
    openings: tuple[BeatOpening, ...] = (),
) -> ScenarioProgram:
    beats = tuple(f"b{index}" for index in range(len(actions)))
    perturbation = "floor_opening" if counterfactual is not None else _PERTURBATION[family]
    return ScenarioProgram(
        bundle=bundle,
        template=template,
        family=family,
        master_seed=master_seed,
        timing_plan=plan,
        frames=frames,
        actions=actions,
        tool_results=tool_results,
        beat_ids=beats,
        stale_results_by_beat=tuple(BeatStaleResults(beat, ()) for beat in beats),
        perturbations=(DeclaredPerturbation(perturbation),),
        counterfactual=counterfactual,
        response_warrants_by_beat=warrants,
        openings_by_beat=openings,
    )


def _floor_link(group_id: str, member_id: str) -> CounterfactualDeclaration:
    return CounterfactualDeclaration(
        kind="twin",
        group_id=group_id,
        member_id=member_id,
        member_ids=("active", "yielded"),
        flipped_perturbation="floor_opening",
    )


def _timing(split: Split, seed: str, count: int) -> TimingPlan:
    return materialize_timing_plan(TimingSeed(split, seed), count)


def _inputs_for(
    inputs: Mapping[CorpusFamily, G7FamilyInputs], family: CorpusFamily
) -> G7FamilyInputs:
    try:
        selected = inputs[family]
    except KeyError as error:
        raise ValueError(f"G7 inputs are missing {family.value}") from error
    if not isinstance(selected, G7FamilyInputs):
        raise TypeError("each G7 input selection must be a G7FamilyInputs")
    return selected


def _rotated_choices(master_seed: str, namespace: str, values: tuple[str, ...]) -> tuple[str, ...]:
    start = int(artifact_digest({"seed": master_seed, "namespace": namespace})[7:15], 16)
    start %= len(values)
    return values[start:] + values[:start]


def _timer_texts(
    master_seed: str,
    namespace: str,
    instructions: tuple[str, ...],
    *,
    contextual: bool,
) -> tuple[str, ...]:
    if not instructions:
        raise ValueError("timer text wave requires at least one instruction")
    if not contextual:
        return instructions
    contexts = _rotated_choices(master_seed, f"{namespace}-context", _TIMER_CONTEXTS)[
        : len(instructions)
    ]
    return tuple(
        f"The {context} remains open beside the notebook.\n{instruction}"
        for context, instruction in zip(contexts, instructions, strict=True)
    )


def _timer_variants(
    base: TimerInstructionSemanticsV1,
    master_seed: str,
    namespace: str,
    count: int,
) -> tuple[TimerInstructionSemanticsV1, ...]:
    contexts = _rotated_choices(master_seed, f"{namespace}-message", _TIMER_CONTEXTS)
    messages = (base.message, *(f"{base.message} for the {value}" for value in contexts))
    return tuple(
        TimerInstructionSemanticsV1(base.interval_ms, base.surface_interval, message)
        for message in messages[:count]
    )


def _payload(
    bundle: AssetBundle,
    family: CorpusFamily,
    expected: type[LookupAssetPayload] | type[TimerAssetPayload],
) -> LookupAssetPayload | TimerAssetPayload:
    payload = next(
        (
            asset.payload
            for asset in bundle.assets
            if family in asset.coverage and isinstance(asset.payload, expected)
        ),
        None,
    )
    if payload is None:
        raise ValueError(f"{family.value} requires an approved {expected.__name__}")
    return payload


def _timer_semantics(timer: TimerAssetPayload) -> TimerInstructionSemanticsV1:
    return validate_timer_asset_semantics_v1(timer.instruction, timer.interval_ms, timer.message)


def _lookup_assets(bundle: AssetBundle) -> tuple[LookupAssetPayload, LookupAssetPayload]:
    first = next(
        (
            asset
            for asset in bundle.assets
            if CorpusFamily.LOOKUP_LIVE in asset.coverage
            and isinstance(asset.payload, LookupAssetPayload)
        ),
        None,
    )
    second = next(
        (
            asset
            for asset in bundle.assets
            if isinstance(asset.payload, LookupAssetPayload)
            and asset.asset_id != (None if first is None else first.asset_id)
            and (first is None or asset.payload.query != first.payload.query)
        ),
        None,
    )
    if first is None or second is None:
        raise ValueError(
            "live-lookup G7 recipes require one live-family seed "
            "and a second approved distinct query"
        )
    assert isinstance(first.payload, LookupAssetPayload)
    assert isinstance(second.payload, LookupAssetPayload)
    return first.payload, second.payload


def _text_asset(bundle: AssetBundle, family: CorpusFamily) -> AssetRecord:
    asset = next(
        (
            item
            for item in bundle.assets
            if family in item.coverage and isinstance(item.payload, TextAssetPayload)
        ),
        None,
    )
    if asset is None:
        raise ValueError(f"{family.value} requires an approved text asset")
    return asset


def _family_text(bundle: AssetBundle, family: CorpusFamily) -> str:
    asset = next(item for item in bundle.assets if family in item.coverage)
    if isinstance(asset.payload, TextAssetPayload):
        return asset.payload.text
    if isinstance(asset.payload, LookupAssetPayload):
        return asset.payload.query
    assert isinstance(asset.payload, TimerAssetPayload)
    return asset.payload.instruction


def _frame(at_ms: int, text: str, activity: str = "paused") -> ScheduledSamplerFrame:
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


def _decision_frames(
    text: str, plan: TimingPlan, *, activity: str = "paused"
) -> tuple[ScheduledSamplerFrame, ...]:
    return _decision_frames_for_texts((text,) * len(plan.service_ms), plan, activity=activity)


def _decision_frames_for_texts(
    texts: tuple[str, ...], plan: TimingPlan, *, activity: str = "paused"
) -> tuple[ScheduledSamplerFrame, ...]:
    if len(texts) != len(plan.service_ms):
        raise ValueError("response texts must align with the timing plan")
    at_ms = 0
    frames = []
    for text, service_ms in zip(texts, plan.service_ms, strict=True):
        frames.append(_frame(at_ms, text, activity))
        at_ms += service_ms + 1
    return tuple(frames)


def _response_openings(context: str, variant: int) -> tuple[tuple[str, ...], tuple[str, ...]]:
    lead = (
        "For context, the earlier note said",
        "An earlier note reads",
        "Here is the relevant background",
    )[variant]
    questions = (
        "Could you help me identify the next step?",
        "What should I check first?",
        "Which detail from this note deserves attention?",
        "Could you suggest a practical follow-up?",
        "What is a clear way to move this forward?",
        "Would you help me turn this into one small action?",
        "What should I keep in mind before proceeding?",
        "Could you help me choose a sensible priority?",
        "What is the most useful next move here?",
        "Would you offer a brief recommendation?",
    )
    replies = (
        "I’d isolate the note’s key detail, then take one concrete follow-up step.",
        "First, I’d verify the central detail in the earlier note before changing anything.",
        "The most useful detail is the one that determines the immediate follow-up.",
        "A practical follow-up is to record the key point and act on it once.",
        "I’d turn the note into a short, concrete next action.",
        "Start with the smallest action that directly addresses the earlier note.",
        "Keep the note’s stated detail in view and avoid adding assumptions.",
        "Prioritize the action that responds most directly to the earlier note.",
        "The useful next move is a focused check tied to the note’s main detail.",
        "My recommendation is to capture the key detail and make one deliberate follow-up.",
    )
    return tuple(f"{lead}: “{context}”\n{question}" for question in questions), replies


def _span(event_id: str, text: str, selected: str, *, last: bool = False) -> Span:
    start = text.rindex(selected) if last else text.index(selected)
    return Span(
        event_id=event_id,
        start_utf16=utf16_len(text[:start]),
        end_utf16=utf16_len(text[:start]) + utf16_len(selected),
        text=selected,
    )


def _span_occurrence(event_id: str, text: str, selected: str, occurrence: int) -> Span:
    starts = []
    start = 0
    while (index := text.find(selected, start)) >= 0:
        starts.append(index)
        start = index + len(selected)
    selected_start = starts[occurrence]
    return Span(
        event_id=event_id,
        start_utf16=utf16_len(text[:selected_start]),
        end_utf16=utf16_len(text[:selected_start]) + utf16_len(selected),
        text=selected,
    )


def _multi_target_text(instruction: str, target: str, count: int) -> str:
    shells = (
        "The shoreline note also mentions {}.",
        "A margin note refers to {}.",
        "The field log includes {}.",
        "The archive card records {}.",
        "A notebook page calls out {}.",
        "The desk copy mentions {} again.",
        "A separate note points to {}.",
        "The final line retains {}.",
    )
    if not 1 <= count <= len(shells):
        raise ValueError("mark target count exceeds the natural text inventory")
    return instruction + "\n" + "\n".join(shell.format(target) for shell in shells[:count])


def _idle(
    reason: IdleReason = IdleReason.NO_TRIGGER, related_event_id: str | None = None
) -> IdleAction:
    return IdleAction(type="idle", reason=reason, related_event_id=related_event_id)


def _delegate(event_id: str, query: str, *, source: str | None = None) -> DelegateAction:
    return DelegateAction(
        type="delegate",
        fact=_span(event_id, query if source is None else source, query),
        tool=ToolName.LOOKUP,
        args={"query": query},
    )


def _schedule(
    event_id: str,
    text: str,
    semantics: TimerInstructionSemanticsV1,
    *,
    explicit_additional: bool = False,
) -> ScheduleAction:
    instruction = render_timer_instruction_v1(
        semantics.interval_ms,
        semantics.message,
        explicit_additional=explicit_additional,
    )
    return ScheduleAction(
        type="schedule",
        instruction=_span(event_id, text, instruction),
        interval_ms=semantics.interval_ms,
        message=semantics.message,
    )
