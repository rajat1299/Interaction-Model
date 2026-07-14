"""Concrete, runtime-backed C5 family programs.

This module deliberately contains eleven small recipe branches, not a scenario
language.  Every action uses the production runtime's deterministic ids.
"""

from __future__ import annotations

from collections.abc import Iterable

from im.assets.model import (
    AssetRecord,
    CorpusFamily,
    LookupAssetPayload,
    Split,
    TemplateAssetPayload,
    TextAssetPayload,
    TextForm,
    TimerAssetPayload,
    TimerForm,
)
from im.assets.registry import AssetBundle, AssetRegistry
from im.canonical_json import canonicalize_tim_json
from im.config import RuntimeConfig
from im.generation.ingestion import ScheduledAnnotation, ScheduledSamplerFrame
from im.generation.scenarios import (
    BeatStaleResults,
    CounterfactualDeclaration,
    DeclaredPerturbation,
    ScenarioProgram,
    select_approved_scenario_inputs,
)
from im.generation.timing import TimingPlan, TimingSeed, materialize_timing_plan
from im.schema.actions import (
    CancelAction,
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

_CATALOG_VERSION = "phase1-c5-family-catalog-v1"
_LONG_PENDING_MS = 8_000_000
_PERTURBATIONS = {
    CorpusFamily.NEUTRAL_TYPING: "draft_revision",
    CorpusFamily.MARK_POSITIVE: "mark_targeting",
    CorpusFamily.MARK_NEGATIVE: "mark_restraint",
    CorpusFamily.LOOKUP_LIVE: "tool_result",
    CorpusFamily.LOOKUP_DUPLICATE: "pending_tool_pressure",
    CorpusFamily.LOOKUP_STALE: "topic_change",
    CorpusFamily.TIMER_NORMAL: "timer_fire",
    CorpusFamily.TIMER_CANCEL: "timer_cancel_race",
    CorpusFamily.TIMER_CONTENTION: "external_event_contention",
    CorpusFamily.ROLLOVER: "state_checkpoint",
    CorpusFamily.RESERVED: "annotation_safety",
}


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


def _annotation(at_ms: int, text: str) -> ScheduledAnnotation:
    return ScheduledAnnotation(at_ms, canonicalize_tim_json({"text": text}))


def _span(event_id: str, text: str, selected: str | None = None) -> Span:
    selected = text if selected is None else selected
    try:
        start = text.index(selected)
    except ValueError as error:
        raise ValueError("scenario target is absent from its source text") from error
    start_utf16 = utf16_len(text[:start])
    return Span(
        event_id=event_id,
        start_utf16=start_utf16,
        end_utf16=start_utf16 + utf16_len(selected),
        text=selected,
    )


def _idle(
    reason: IdleReason = IdleReason.NO_TRIGGER, related_event_id: str | None = None
) -> IdleAction:
    return IdleAction(type="idle", reason=reason, related_event_id=related_event_id)


def _mark(
    event_id: str,
    text: str,
    target: str,
    *,
    instruction: str | None = None,
) -> MarkAction:
    return MarkAction(
        type="mark",
        instruction=_span(event_id, text, instruction),
        target=_span(event_id, text, target),
    )


def _delegate(event_id: str, text: str, query: str) -> DelegateAction:
    return DelegateAction(
        type="delegate",
        fact=_span(event_id, text, query),
        tool=ToolName.LOOKUP,
        args={"query": query},
    )


def _schedule(
    event_id: str, payload: TimerAssetPayload, source: str | None = None
) -> ScheduleAction:
    if payload.interval_ms is None or payload.message is None:  # narrowed by asset selection.
        raise ValueError("timer family requires a supported timer asset")
    return ScheduleAction(
        type="schedule",
        instruction=_span(
            event_id,
            payload.instruction if source is None else source,
            payload.instruction,
        ),
        interval_ms=payload.interval_ms,
        message=payload.message,
    )


def _selected_payload(
    bundle: AssetBundle,
    family: CorpusFamily,
    payload_type: type[TextAssetPayload] | type[LookupAssetPayload] | type[TimerAssetPayload],
) -> TextAssetPayload | LookupAssetPayload | TimerAssetPayload:
    candidates = tuple(
        asset.payload
        for asset in bundle.assets
        if family in asset.coverage and isinstance(asset.payload, payload_type)
    )
    if not candidates:
        raise ValueError(f"{family.value} requires an approved {payload_type.__name__} asset")
    return candidates[0]


def _mark_target(asset: AssetRecord, text: str) -> str:
    target = next((value for value in asset.protected_values if value in text), None)
    if target is not None:
        return target
    return text.split(maxsplit=1)[0]


def _selected_text_asset(
    bundle: AssetBundle,
    family: CorpusFamily | None,
    *,
    form: TextForm | None = None,
) -> AssetRecord:
    asset = next(
        (
            item
            for item in bundle.assets
            if (family is None or family in item.coverage)
            and isinstance(item.payload, TextAssetPayload)
            and (form is None or item.payload.form is form)
        ),
        None,
    )
    if asset is None:
        label = "scenario" if family is None else family.value
        raise ValueError(f"{label} requires an approved TextAssetPayload asset")
    return asset


def _supported_timer(bundle: AssetBundle) -> TimerAssetPayload:
    timer = next(
        (
            item.payload
            for item in bundle.assets
            if isinstance(item.payload, TimerAssetPayload)
            and item.payload.form is TimerForm.SUPPORTED
        ),
        None,
    )
    if timer is None:
        raise ValueError("scenario requires an approved supported timer asset")
    return timer


def _validate_inputs(
    family: CorpusFamily,
    bundle: AssetBundle,
    template: AssetRecord,
    master_seed: str,
) -> None:
    if not isinstance(bundle, AssetBundle):
        raise TypeError("bundle must be an AssetBundle selected from an approved split pool")
    if not isinstance(template, AssetRecord) or not isinstance(
        template.payload, TemplateAssetPayload
    ):
        raise TypeError("template must be a template AssetRecord")
    if template.split is not bundle.split or family not in template.coverage:
        raise ValueError("template must cover the family in the bundle's split")
    if not isinstance(master_seed, str) or not master_seed or master_seed.strip() != master_seed:
        raise ValueError("master_seed must be a non-blank trimmed string")


def _timing_plan(
    bundle: AssetBundle, family: CorpusFamily, master_seed: str, count: int
) -> TimingPlan:
    return materialize_timing_plan(
        TimingSeed(bundle.split, f"{_CATALOG_VERSION}:{family.value}:{master_seed}"), count
    )


def _variant_value(variant: tuple[str, str] | None, key: str, default: str) -> str:
    return variant[1] if variant is not None and variant[0] == key else default


def _decision_count(
    family: CorpusFamily,
    variant: tuple[str, str] | None,
    bundle: AssetBundle,
) -> int:
    if family is CorpusFamily.NEUTRAL_TYPING:
        return 3
    if family is CorpusFamily.MARK_POSITIVE:
        return (
            1
            if variant
            and variant[0] in {"directness", "lexical_boundary"}
            and variant[1] in {"quoted", "embedded"}
            else 2
        )
    if family is CorpusFamily.MARK_NEGATIVE:
        return 1
    if family is CorpusFamily.LOOKUP_LIVE:
        return 2 if _variant_value(variant, "provenance_result", "a") == "none" else 3
    if family is CorpusFamily.LOOKUP_DUPLICATE:
        return 1 if _variant_value(variant, "request_presence", "pending") == "absent" else 2
    if family is CorpusFamily.LOOKUP_STALE:
        return 3 if _variant_value(variant, "topic_freshness", "changed") == "current" else 4
    if family is CorpusFamily.TIMER_NORMAL:
        return 4
    if family is CorpusFamily.TIMER_CANCEL:
        primary = next(
            item
            for item in bundle.assets
            if family in item.coverage
            and isinstance(item.payload, (TextAssetPayload, TimerAssetPayload))
        )
        if (
            isinstance(primary.payload, TimerAssetPayload)
            and primary.payload.form is not TimerForm.SUPPORTED
        ) or (
            isinstance(primary.payload, TextAssetPayload)
            and primary.payload.form is not TextForm.DIRECT
        ):
            return 1
        return 4 if _variant_value(variant, "timer_status", "canceled") == "active" else 5
    if family is CorpusFamily.TIMER_CONTENTION:
        return 4 if _variant_value(variant, "floor_state", "paused") == "typing" else 6
    if family is CorpusFamily.ROLLOVER:
        return 6
    assert family is CorpusFamily.RESERVED
    return 1


def _compile(
    family: CorpusFamily,
    bundle: AssetBundle,
    timing_plan: TimingPlan,
    variant: tuple[str, str] | None,
) -> tuple[
    tuple[ScheduledSamplerFrame, ...],
    tuple[ScheduledAnnotation, ...],
    tuple[object, ...],
    tuple[ScriptedToolResult, ...],
    RuntimeConfig,
    tuple[tuple[str, tuple[str, ...]], ...],
]:
    service = timing_plan.service_ms
    config = RuntimeConfig()
    stale: tuple[tuple[str, tuple[str, ...]], ...] = ()
    if family is CorpusFamily.NEUTRAL_TYPING:
        text = _selected_payload(bundle, family, TextAssetPayload)
        assert isinstance(text, TextAssetPayload)
        first = text.text
        second = f"{first} Revised."
        third = f"{second}"
        return (
            (
                _frame(0, first, activity="active"),
                _frame(service[0] + 1, second, activity="active"),
                _frame(service[0] + service[1] + 2, third),
            ),
            (),
            (_idle(IdleReason.TYPING_ACTIVE), _idle(IdleReason.TYPING_ACTIVE), _idle()),
            (),
            config,
            stale,
        )
    if family is CorpusFamily.MARK_POSITIVE:
        asset = _selected_text_asset(bundle, family)
        text = asset.payload
        assert isinstance(text, TextAssetPayload)
        if text.form is not TextForm.DIRECT:
            raise ValueError("mark-positive scenarios require direct text assets")
        target = _mark_target(asset, text.text)
        mode = _variant_value(variant, "directness", "direct")
        boundary = _variant_value(variant, "lexical_boundary", "standalone")
        source = text.text if mode == "direct" else f'The note quotes "{text.text}".'
        if boundary == "embedded":
            source = source.replace(target, f"{target}field", 1)
        actions: tuple[object, ...] = (
            (_idle(IdleReason.INSTRUCTION_NOT_DIRECT),)
            if mode == "quoted" or boundary == "embedded"
            else (_mark("e_000002", source, target), _idle())
        )
        return ((_frame(0, source),), (), actions, (), config, stale)
    if family is CorpusFamily.MARK_NEGATIVE:
        text = _selected_payload(bundle, family, TextAssetPayload)
        assert isinstance(text, TextAssetPayload)
        if text.form is TextForm.DIRECT:
            raise ValueError("mark-negative scenarios require non-direct text assets")
        return (
            (_frame(0, text.text),),
            (),
            (_idle(IdleReason.INSTRUCTION_NOT_DIRECT),),
            (),
            config,
            stale,
        )
    if family is CorpusFamily.LOOKUP_LIVE:
        lookup = _selected_payload(bundle, family, LookupAssetPayload)
        assert isinstance(lookup, LookupAssetPayload)
        outcome = _variant_value(variant, "provenance_result", "a")
        latency = int(_variant_value(variant, "tool_latency", "700ms").removesuffix("ms"))
        frames = (_frame(0, lookup.query), _frame(service[0] + 1, lookup.query))
        if outcome == "none":
            return (
                frames,
                (),
                (
                    _delegate("e_000002", lookup.query, lookup.query),
                    _idle(IdleReason.AWAITING_TOOL, "e_000002"),
                ),
                (
                    ScriptedToolResult(
                        latency_ms=_LONG_PENDING_MS,
                        data={"nonce": lookup.no_result_code},
                    ),
                ),
                config,
                stale,
            )
        result = lookup.result_b if outcome == "b" else lookup.result_a
        return (
            frames,
            (),
            (
                _delegate("e_000002", lookup.query, lookup.query),
                _idle(IdleReason.AWAITING_TOOL, "e_000002"),
                IntegrateAction(type="integrate", result_event_id="e_000006", text=result),
            ),
            (ScriptedToolResult(latency_ms=latency, data={"nonce": result}),),
            config,
            stale,
        )
    if family is CorpusFamily.LOOKUP_DUPLICATE:
        lookup = _selected_payload(bundle, family, LookupAssetPayload)
        assert isinstance(lookup, LookupAssetPayload)
        presence = _variant_value(variant, "request_presence", "pending")
        if presence == "absent":
            return (
                (_frame(0, lookup.query),),
                (),
                (_delegate("e_000002", lookup.query, lookup.query),),
                (
                    ScriptedToolResult(
                        latency_ms=_LONG_PENDING_MS,
                        data={"nonce": lookup.result_a},
                    ),
                ),
                config,
                stale,
            )
        return (
            (_frame(0, lookup.query), _frame(service[0] + 1, lookup.query)),
            (),
            (
                _delegate("e_000002", lookup.query, lookup.query),
                _idle(IdleReason.AWAITING_TOOL, "e_000002"),
            ),
            (ScriptedToolResult(latency_ms=_LONG_PENDING_MS, data={"nonce": lookup.result_a}),),
            config,
            stale,
        )
    if family is CorpusFamily.LOOKUP_STALE:
        lookup = _selected_payload(bundle, family, LookupAssetPayload)
        assert isinstance(lookup, LookupAssetPayload)
        freshness = _variant_value(variant, "topic_freshness", "changed")
        topic = lookup.query if freshness == "current" else f"Different topic after {lookup.query}."
        final = (
            IntegrateAction(type="integrate", result_event_id="e_000006", text=lookup.result_a)
            if freshness == "current"
            else SkipAction(
                type="skip", target_event_id="e_000006", reason=SkipReason.STALE_TOOL_RESULT
            )
        )
        stale = (("b2", ("e_000006",)),) if freshness == "changed" else ()
        actions = (
            (_delegate("e_000002", lookup.query, lookup.query), _idle(), final)
            if freshness == "current"
            else (_delegate("e_000002", lookup.query, lookup.query), _idle(), final, _idle())
        )
        return (
            (_frame(0, lookup.query), _frame(service[0] + 300, topic)),
            (),
            actions,
            (ScriptedToolResult(latency_ms=700, data={"nonce": lookup.result_a}),),
            config,
            stale,
        )
    if family is CorpusFamily.TIMER_NORMAL:
        timer = _selected_payload(bundle, family, TimerAssetPayload)
        assert isinstance(timer, TimerAssetPayload) and timer.interval_ms is not None
        return (
            (_frame(0, timer.instruction),),
            (),
            (
                _schedule("e_000002", timer),
                _idle(),
                NudgeAction(type="nudge", fire_event_id="e_000005"),
                _idle(),
            ),
            (),
            config,
            stale,
        )
    if family is CorpusFamily.TIMER_CANCEL:
        primary = next(
            item.payload
            for item in bundle.assets
            if family in item.coverage
            and isinstance(item.payload, (TextAssetPayload, TimerAssetPayload))
        )
        if (isinstance(primary, TimerAssetPayload) and primary.form is not TimerForm.SUPPORTED) or (
            isinstance(primary, TextAssetPayload) and primary.form is not TextForm.DIRECT
        ):
            text = primary.instruction if isinstance(primary, TimerAssetPayload) else primary.text
            return (
                (_frame(0, text),),
                (),
                (_idle(IdleReason.INSTRUCTION_NOT_DIRECT),),
                (),
                config,
                stale,
            )
        timer = _supported_timer(bundle)
        cancel_text = (
            primary.text if isinstance(primary, TextAssetPayload) else "Cancel the active reminder."
        )
        assert timer.interval_ms is not None
        status = _variant_value(variant, "timer_status", "canceled")
        if status == "active":
            return (
                (_frame(0, timer.instruction),),
                (),
                (
                    _schedule("e_000002", timer),
                    _idle(),
                    NudgeAction(type="nudge", fire_event_id="e_000005"),
                    _idle(),
                ),
                (),
                config,
                stale,
            )
        stop_at = service[0] + timer.interval_ms - 100
        if stop_at <= service[0] + service[1]:
            raise ValueError(
                "timer cancel family requires an interval safely beyond the continuation"
            )
        return (
            (_frame(0, timer.instruction), _frame(stop_at, cancel_text)),
            (),
            (
                _schedule("e_000002", timer),
                _idle(),
                CancelAction(
                    type="cancel",
                    instruction=_span("e_000005", cancel_text),
                    target={"kind": "timer", "timer_id": "t_001"},
                ),
                SkipAction(
                    type="skip", target_event_id="e_000006", reason=SkipReason.CANCELED_TIMER
                ),
                _idle(),
            ),
            (),
            config,
            stale,
        )
    if family is CorpusFamily.TIMER_CONTENTION:
        timer = _selected_payload(bundle, family, TimerAssetPayload)
        mark_asset = _selected_text_asset(bundle, CorpusFamily.MARK_POSITIVE, form=TextForm.DIRECT)
        mark_text = mark_asset.payload
        assert isinstance(timer, TimerAssetPayload) and timer.interval_ms is not None
        assert isinstance(mark_text, TextAssetPayload)
        floor = _variant_value(variant, "floor_state", "paused")
        at_ms = service[0] + timer.interval_ms - 100
        if at_ms <= service[0] + service[1]:
            raise ValueError("timer contention family requires a long timer interval")
        source = f"{timer.instruction}\n{mark_text.text}"
        mark_target = _mark_target(mark_asset, mark_text.text)
        actions: tuple[object, ...]
        if floor == "typing":
            actions = (
                _schedule("e_000002", timer, source),
                _idle(),
                _idle(IdleReason.TYPING_ACTIVE),
                _idle(IdleReason.TYPING_ACTIVE),
            )
        else:
            actions = (
                _schedule("e_000002", timer, source),
                _idle(),
                _idle(),
                NudgeAction(type="nudge", fire_event_id="e_000006"),
                _mark("e_000005", source, mark_target, instruction=mark_text.text),
                _idle(),
            )
        return (
            (
                _frame(0, source),
                _frame(at_ms, source, activity="active" if floor == "typing" else "paused"),
            ),
            (),
            actions,
            (),
            config,
            stale,
        )
    if family is CorpusFamily.ROLLOVER:
        lookup = _selected_payload(bundle, family, LookupAssetPayload)
        timer = _supported_timer(bundle)
        mark_asset = _selected_text_asset(bundle, CorpusFamily.MARK_POSITIVE, form=TextForm.DIRECT)
        mark_text = mark_asset.payload
        assert isinstance(lookup, LookupAssetPayload)
        assert isinstance(mark_text, TextAssetPayload)
        followup_query = f"{lookup.query} followup"
        source = "\n".join((mark_text.text, timer.instruction, lookup.query, followup_query))
        target = _mark_target(mark_asset, mark_text.text)
        boundary = _variant_value(variant, "rollover_boundary", "post")
        rollover_config = RuntimeConfig(context_budget_tokens=12_000 if boundary == "pre" else 100)
        topic_changed_at = sum(service[:3]) + 699
        topic_event_id = "e_000009" if boundary == "post" else "e_000008"
        result_event_id = "e_000010" if boundary == "post" else "e_000009"
        return (
            (_frame(0, source), _frame(topic_changed_at, followup_query)),
            (),
            (
                _mark("e_000002", source, target, instruction=mark_text.text),
                _schedule("e_000002", timer, source),
                _delegate("e_000002", source, lookup.query),
                _idle(),
                SkipAction(
                    type="skip",
                    target_event_id=result_event_id,
                    reason=SkipReason.STALE_TOOL_RESULT,
                ),
                _delegate(topic_event_id, followup_query, followup_query),
            ),
            (
                ScriptedToolResult(latency_ms=700, data={"nonce": lookup.result_a}),
                ScriptedToolResult(latency_ms=_LONG_PENDING_MS, data={"nonce": lookup.result_b}),
            ),
            rollover_config,
            (("b4", (result_event_id,)),),
        )
    assert family is CorpusFamily.RESERVED
    text = next(
        (item.payload.text for item in bundle.assets if isinstance(item.payload, TextAssetPayload)),
        "unknown-kind safety note",
    )
    return ((), (_annotation(0, text),), (_idle(),), (), config, stale)


def _stale_beats(
    beat_ids: tuple[str, ...], stale: Iterable[tuple[str, tuple[str, ...]]]
) -> tuple[BeatStaleResults, ...]:
    explicit = dict(stale)
    return tuple(
        BeatStaleResults(beat_id=beat_id, tool_result_event_ids=explicit.get(beat_id, ()))
        for beat_id in beat_ids
    )


def _build_selected_family_program(
    family: CorpusFamily | str,
    bundle: AssetBundle,
    template: AssetRecord,
    master_seed: str,
    *,
    counterfactual: CounterfactualDeclaration | None = None,
    _variant: tuple[str, str] | None = None,
) -> ScenarioProgram:
    """Compile one program after the public registry boundary selected its inputs."""
    family = CorpusFamily(family)
    _validate_inputs(family, bundle, template, master_seed)
    count = _decision_count(family, _variant, bundle)
    timing_plan = _timing_plan(bundle, family, master_seed, count)
    frames, annotations, actions, tool_results, config, stale = _compile(
        family, bundle, timing_plan, _variant
    )
    if len(actions) != count:  # pragma: no cover - keeps recipes and timing coupled.
        raise RuntimeError("family recipe action count drifted from its timing plan")
    beat_ids = tuple(f"b{index}" for index in range(len(actions)))
    kind = _PERTURBATIONS[family]
    return ScenarioProgram(
        bundle=bundle,
        template=template,
        family=family,
        master_seed=master_seed,
        timing_plan=timing_plan,
        frames=frames,
        annotations=annotations,
        actions=actions,
        tool_results=tool_results,
        beat_ids=beat_ids,
        stale_results_by_beat=_stale_beats(beat_ids, stale),
        perturbations=(DeclaredPerturbation(kind=kind),),
        config=config,
        counterfactual=counterfactual,
    )


def build_family_program(
    family: CorpusFamily | str,
    registry: AssetRegistry,
    *,
    split: Split | str,
    template_id: str,
    asset_ids: tuple[str, ...],
    master_seed: str,
) -> ScenarioProgram:
    """Build one seed-stable family program through C1's approval boundary."""
    bundle, template = select_approved_scenario_inputs(
        registry,
        split=split,
        template_id=template_id,
        asset_ids=asset_ids,
    )
    return _build_selected_family_program(
        family,
        bundle,
        template,
        master_seed,
    )
