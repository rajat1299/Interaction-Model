"""Owner-approved WP2-6 v2 idle-reason feasibility top-up."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, replace
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

from im.assets import AssetRegistry, CorpusFamily, Split
from im.assets.model import LookupAssetPayload, canonical_artifact_bytes
from im.canonical_json import canonicalize_tim_json, parse_tim_json
from im.config import estimate_tokens
from im.generation.g7_response_assets import SimpleResponseProfile
from im.generation.g7_response_twins import build_g7_response_floor_twin_program
from im.generation.ingestion import ScheduledSamplerFrame
from im.generation.packaging import PackageManifest
from im.generation.phase2_lookup_wave0 import _raw_stream, _runtime_files
from im.generation.phase2_lookup_wave2 import _response_assets
from im.generation.phase2_response_tranche import _family_inputs
from im.generation.phase2_timer_wave0 import load_timer_wave0_inputs
from im.generation.phase2_timer_wave0_boundaries import (
    _frame as _timer_frame,
)
from im.generation.phase2_timer_wave0_boundaries import (
    _program as _timer_cancel_program,
)
from im.generation.phase2_timer_wave0_boundaries import (
    _schedule,
    _timer,
)
from im.generation.phase2_timer_wave2_chat import _round_markdown, _rounds
from im.generation.publication import publish_directory_transaction
from im.generation.scenario_catalog import build_family_program
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
    PromptArtifacts,
    PromptedPolicyConfig,
    PromptRenderer,
    ResponsesRequestBuilder,
)
from im.probes.harness.identity import digest
from im.schema.actions import (
    DelegateAction,
    IdleAction,
    IdleReason,
    IntegrateAction,
    NudgeAction,
    RespondAction,
    Span,
    ToolName,
)
from im.schema.textspan import utf16_len
from im.tools import ScriptedToolResult

_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_IDLE_TOPUP_OUTPUT = _ROOT / "review" / "phase2" / "wp2-6-idle-topup"
DEFAULT_IDLE_TOPUP_REPAIR_OUTPUT = _ROOT / "review" / "phase2" / "wp2-6-idle-topup-repair"
DEFAULT_IDLE_TOPUP_TYPING_OUTPUT = (
    _ROOT / "review" / "phase2" / "wp2-6-idle-topup-typing-shortfall"
)
_PROMPT_TEMPLATE = "prompt-template-v4.txt"
_SELECTION_CONTRACT = Path("spec/phase2-selection-v2.json")
_OWNER_DECISION = Path("review/phase2/wp2-6-selection-v2-amendment/OWNER-DISPOSITION.md")
_MAX_ROUND_TOKENS = 120_000

_TIMER_TEMPLATE = "a_77870a0d84d3da57e4b0318d"
_TIMER_ASSETS = (
    "a_067f59d6c56633412a0d45b4",
    "a_11d7f848364801c6724c9d75",
    "a_543b664484ba8fff0a5f3ca2",
    "a_5aee644a2b2f34f90485b86f",
    "a_7fbdae8ceff9c6dc9f3fd5c6",
    "a_8dc6c9d3ac20357c23e76ef3",
    "a_a4ad7430aeaff6e0cd839a35",
)
_MARK_POSITIVE_TEMPLATE = "a_a1c85d29665460b9b04ffcd2"
_MARK_POSITIVE_ASSETS = (
    "a_052537ca3568ef0f0bb8d2ff",
    "a_4d9e7e5fdf179993fd3d8367",
    "a_4f45803171cb2679aa272baa",
    "a_7a61e645a7833002d053596d",
    "a_8870dc68ae7d0dc1e044ebd9",
    "a_c6b9ea7492dd47bde4d49e30",
)
_MARK_PARTIALS = (
    "Highlight the phrase Silver Orcha",
    "Highlight 17 October 20",
    "Highlight the filler words um and you kn",
    "Mark Dr. Imani Vo",
    "Underline every occurrence of Meridian Fin",
    "Underline the first-aid ki",
)
_MARK_SHORTFALL_PARTIALS = (
    "Highlight the phrase Silver Orch",
    "Highlight 17 October 203",
    "Highlight the filler words um and you kno",
    "Mark Dr. Imani V",
    "Underline every occurrence of Meridian Finc",
    "Underline the first-aid k",
    "Highlight the phrase Silver Orchar",
)
_LOOKUP_TEMPLATE = "a_93beb83846363b159a8f8f67"
_LOOKUP_ASSETS = (
    "a_1cf8a5df42e379dcb0fc2472",
    "a_23b3d0a6cc4216d09016c9c2",
    "a_7960c7b84f8755e53ee4941e",
    "a_9cb5bcdbda0a0ab215869885",
    "a_adeb16c7dd41c777848bda5d",
    "a_b48a45684dfbda39d18a4593",
    "a_bc0c6abcb2b7aa943ed3bd0c",
)
_MARK_NEGATIVE_TEMPLATE = "a_cf3fb85cbef8786d98724b33"
_AMBIGUOUS_REPLACEMENT_ASSET = "a_15ad2d6715b3cf386a1e8806"
_AMBIGUOUS_REFERENT_ASSET = "a_76f996251354c25a3c5d4a1d"
_AMBIGUOUS_CANCEL_TEMPLATE = "a_064c3dae3e3abe4e7bd7a487"
_AMBIGUOUS_CANCEL_ASSET = "a_b2a1ca0b7e647ec77411d143"
_MARK_CONTEXTS = (
    ("Apple", "Orange"),
    ("cedar label", "willow label"),
    ("north gate", "south gate"),
    ("blue token", "amber token"),
    ("draft total", "final total"),
    ("route name", "station name"),
)
_MARK_REPLACEMENT_CONTEXTS = (
    ("Apple", "Orange", "Pear"),
    ("cedar label", "willow label", "maple label"),
    ("north gate", "south gate", "east gate"),
    ("blue token", "amber token", "green token"),
    ("draft total", "final total", "revised total"),
    ("route name", "station name", "platform name"),
)


class IdleTopupError(ValueError):
    """The approved v2 feasibility top-up drifted."""


@dataclass(frozen=True, slots=True)
class IdleTopupSpec:
    logical_stream_id: str
    source_unit_id: str
    shape_id: str
    target_indices: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class ExecutedIdleTopup:
    spec: IdleTopupSpec
    generated: GeneratedScenario
    selected_segment: object | None = None


@dataclass(frozen=True, slots=True)
class IdleTopupPacket:
    files: dict[str, bytes]
    stream_count: int
    target_decision_count: int
    round_count: int


def _registry(root: Path) -> AssetRegistry:
    return load_timer_wave0_inputs(
        approved_root=root / "review/phase1/approved",
        selection_contract_path=root / _SELECTION_CONTRACT,
    )


def _single_idle(
    registry: AssetRegistry,
    *,
    family: CorpusFamily,
    template_id: str,
    asset_id: str,
    seed: str,
    text: str,
    reason: IdleReason,
    composing: bool,
) -> ScenarioProgram:
    bundle, template = select_approved_scenario_inputs(
        registry,
        split=Split.TRAIN,
        template_id=template_id,
        asset_ids=(asset_id,),
    )
    plan = materialize_timing_plan(TimingSeed(Split.TRAIN, seed), 1)
    beat = "b0"
    return ScenarioProgram(
        bundle=bundle,
        template=template,
        family=family,
        master_seed=seed,
        timing_plan=plan,
        frames=(_frame(0, text, composing=composing),),
        actions=(IdleAction(type="idle", reason=reason, related_event_id=None),),
        tool_results=(),
        beat_ids=(beat,),
        stale_results_by_beat=(BeatStaleResults(beat, ()),),
        perturbations=(
            DeclaredPerturbation(
                "draft_revision" if reason is IdleReason.TYPING_ACTIVE else "mark_restraint"
            ),
        ),
        prompt_template=_PROMPT_TEMPLATE,
    )


def _typing_streams(registry: AssetRegistry) -> list[tuple[IdleTopupSpec, ScenarioProgram]]:
    streams: list[tuple[IdleTopupSpec, ScenarioProgram]] = []
    for index, asset_id in enumerate(_TIMER_ASSETS, 1):
        payload = _timer(registry, asset_id)
        partial = payload.instruction.rsplit(" to ", 1)[0] + " to "
        streams.append(
            _target(
                registry,
                f"typing-timer-{index:02d}",
                "partial_timer_control",
                CorpusFamily.TIMER_NORMAL,
                _TIMER_TEMPLATE,
                asset_id,
                partial,
                IdleReason.TYPING_ACTIVE,
                index % 2 == 0,
            )
        )
    for index, (asset_id, partial) in enumerate(
        zip(_MARK_POSITIVE_ASSETS, _MARK_PARTIALS, strict=True), 1
    ):
        streams.append(
            _target(
                registry,
                f"typing-mark-{index:02d}",
                "partial_mark_control",
                CorpusFamily.MARK_POSITIVE,
                _MARK_POSITIVE_TEMPLATE,
                asset_id,
                partial,
                IdleReason.TYPING_ACTIVE,
                index % 2 == 1,
            )
        )
    for index, asset_id in enumerate(_LOOKUP_ASSETS, 1):
        query = _lookup_query(registry, asset_id)
        subject, final_word = query.rsplit(" ", 1)
        partial = f"Look up {subject} {final_word[:-2]}"
        streams.append(
            _target(
                registry,
                f"typing-lookup-{index:02d}",
                "incomplete_lookup_subject",
                CorpusFamily.LOOKUP_LIVE,
                _LOOKUP_TEMPLATE,
                asset_id,
                partial,
                IdleReason.TYPING_ACTIVE,
                index % 2 == 0,
            )
        )
    return streams


def _typing_shortfall_streams(
    registry: AssetRegistry,
) -> list[tuple[IdleTopupSpec, ScenarioProgram]]:
    streams: list[tuple[IdleTopupSpec, ScenarioProgram]] = []
    for index, asset_id in enumerate(_TIMER_ASSETS, 1):
        text = _timer(registry, asset_id).instruction
        streams.append(
            _target(
                registry,
                f"typing-shortfall-timer-{index:02d}",
                "partial_timer_message",
                CorpusFamily.TIMER_NORMAL,
                _TIMER_TEMPLATE,
                asset_id,
                text[:-3],
                IdleReason.TYPING_ACTIVE,
                index % 2 == 1,
                seed_prefix="phase2-idle-topup-v2-typing-shortfall",
            )
        )
    for index, (asset_id, partial) in enumerate(
        zip(
            (*_MARK_POSITIVE_ASSETS, _MARK_POSITIVE_ASSETS[0]),
            _MARK_SHORTFALL_PARTIALS,
            strict=True,
        ),
        1,
    ):
        streams.append(
            _target(
                registry,
                f"typing-shortfall-mark-{index:02d}",
                "partial_mark_control",
                CorpusFamily.MARK_POSITIVE,
                _MARK_POSITIVE_TEMPLATE,
                asset_id,
                partial,
                IdleReason.TYPING_ACTIVE,
                index % 2 == 0,
                seed_prefix="phase2-idle-topup-v2-typing-shortfall",
            )
        )
    for index, asset_id in enumerate(_LOOKUP_ASSETS, 1):
        query = _lookup_query(registry, asset_id)
        streams.append(
            _target(
                registry,
                f"typing-shortfall-lookup-{index:02d}",
                "incomplete_lookup_subject",
                CorpusFamily.LOOKUP_LIVE,
                _LOOKUP_TEMPLATE,
                asset_id,
                f"Look up {query[:-3]}",
                IdleReason.TYPING_ACTIVE,
                index % 2 == 1,
                seed_prefix="phase2-idle-topup-v2-typing-shortfall",
            )
        )
    return streams


def _target(
    registry: AssetRegistry,
    logical_id: str,
    shape: str,
    family: CorpusFamily,
    template_id: str,
    asset_id: str,
    text: str,
    reason: IdleReason,
    composing: bool,
    *,
    seed_prefix: str = "phase2-idle-topup-v2",
) -> tuple[IdleTopupSpec, ScenarioProgram]:
    seed = f"{seed_prefix}:{logical_id}"
    return (
        IdleTopupSpec(logical_id, f"idle-topup-{logical_id}", shape, (0,)),
        _single_idle(
            registry,
            family=family,
            template_id=template_id,
            asset_id=asset_id,
            seed=seed,
            text=text,
            reason=reason,
            composing=composing,
        ),
    )


def _mark_ambiguous_streams(
    registry: AssetRegistry,
) -> list[tuple[IdleTopupSpec, ScenarioProgram]]:
    streams = []
    for index, (standing, alternative) in enumerate(_MARK_CONTEXTS, 1):
        text = (
            f"Highlight every mention of {standing}.\n"
            f"The draft contains {standing} and {alternative}.\n"
            "Switch to the other label category."
        )
        streams.append(
            _target(
                registry,
                f"ambiguous-mark-replacement-{index:02d}",
                "ambiguous_mark_replacement",
                CorpusFamily.MARK_NEGATIVE,
                _MARK_NEGATIVE_TEMPLATE,
                _AMBIGUOUS_REPLACEMENT_ASSET,
                text,
                IdleReason.AMBIGUOUS,
                False,
            )
        )
    for index, (first, second) in enumerate(_MARK_CONTEXTS, 1):
        text = (
            f"The margin shows the {first} specimen and the {second} specimen.\n"
            "Highlight the specimen beside the margin."
        )
        streams.append(
            _target(
                registry,
                f"ambiguous-mark-referent-{index:02d}",
                "ambiguous_mark_referent",
                CorpusFamily.MARK_NEGATIVE,
                _MARK_NEGATIVE_TEMPLATE,
                _AMBIGUOUS_REFERENT_ASSET,
                text,
                IdleReason.AMBIGUOUS,
                False,
            )
        )
    return streams


def _mark_replacement_repair_streams(
    registry: AssetRegistry,
) -> list[tuple[IdleTopupSpec, ScenarioProgram]]:
    streams = []
    for index, (standing, first, second) in enumerate(_MARK_REPLACEMENT_CONTEXTS, 1):
        text = (
            f"Highlight every mention of {standing}.\n"
            f"The draft contains {standing}, {first}, and {second}.\n"
            "Switch to the other label category."
        )
        streams.append(
            _target(
                registry,
                f"ambiguous-mark-replacement-repair-{index:02d}",
                "ambiguous_mark_replacement",
                CorpusFamily.MARK_NEGATIVE,
                _MARK_NEGATIVE_TEMPLATE,
                _AMBIGUOUS_REPLACEMENT_ASSET,
                text,
                IdleReason.AMBIGUOUS,
                False,
                seed_prefix="phase2-idle-topup-v2-repair",
            )
        )
    return streams


def _timer_ambiguous_streams(
    registry: AssetRegistry,
) -> list[tuple[IdleTopupSpec, ScenarioProgram]]:
    pairs = tuple(zip(_TIMER_ASSETS, _TIMER_ASSETS[1:] + _TIMER_ASSETS[:1], strict=True))[:6]
    streams = []
    for index, (first_id, second_id) in enumerate(pairs, 1):
        first = _timer(registry, first_id)
        second = _timer(registry, second_id)
        seed = f"phase2-idle-topup-v2:ambiguous-timer-{index:02d}"
        plan = materialize_timing_plan(TimingSeed(Split.TRAIN, seed), 6)
        second_at = sum(plan.service_ms[:2]) + 1
        context_at = second_at + sum(plan.service_ms[2:4]) + 1
        cancel_at = context_at + plan.service_ms[4] + 1
        program = _timer_cancel_program(
            registry,
            template_id=_AMBIGUOUS_CANCEL_TEMPLATE,
            asset_ids=(first_id, second_id, _AMBIGUOUS_CANCEL_ASSET),
            master_seed=seed,
            timing_plan=plan,
            frames=(
                _timer_frame(0, first.instruction),
                _timer_frame(second_at, second.instruction),
                _timer_frame(
                    context_at,
                    "Both reminders are active; neither reminder is selected or identified.",
                ),
                _timer_frame(cancel_at, "Cancel the reminder next to it.", activity="active"),
            ),
            actions=(
                _schedule("e_000002", first),
                _idle(IdleReason.NO_TRIGGER),
                _schedule("e_000005", second),
                _idle(IdleReason.NO_TRIGGER),
                _idle(IdleReason.NO_TRIGGER),
                _idle(IdleReason.AMBIGUOUS),
            ),
        )
        streams.append(
            (
                IdleTopupSpec(
                    f"ambiguous-timer-{index:02d}",
                    f"idle-topup-ambiguous-timer-{index:02d}",
                    "ambiguous_timer_referent",
                    (5,),
                ),
                replace(program, prompt_template=_PROMPT_TEMPLATE),
            )
        )
    return streams


def _handled_streams(
    registry: AssetRegistry, root: Path
) -> list[tuple[IdleTopupSpec, ScenarioProgram]]:
    streams: list[tuple[IdleTopupSpec, ScenarioProgram]] = []
    assets = _response_assets(root)
    ordinals = tuple(range(6, 16))
    profile = SimpleResponseProfile(tuple(assets[ordinal] for ordinal in ordinals))
    inputs = _family_inputs(registry, CorpusFamily.NEUTRAL_TYPING)
    for index, ordinal in enumerate((6, 7), 1):
        twin = build_g7_response_floor_twin_program(
            registry,
            split=Split.TRAIN,
            family=CorpusFamily.NEUTRAL_TYPING,
            inputs=inputs,
            profile=profile,
            master_seed=f"phase2-idle-topup-v2:handled-response-{index:02d}",
            item_index=ordinals.index(ordinal),
        )
        yielded = next(
            program for program in twin.programs if isinstance(program.actions[0], RespondAction)
        )
        streams.append(
            (
                IdleTopupSpec(
                    f"handled-response-{index:02d}",
                    f"idle-topup-handled-response-{index:02d}",
                    "answered_warrant_consumed",
                    (1,),
                ),
                _append_handled(
                    yielded,
                    yielded.actions[0].reply_to_event_id,
                ),
            )
        )
    for index, asset_id in enumerate(
        ("a_1cf8a5df42e379dcb0fc2472", "a_23b3d0a6cc4216d09016c9c2"),
        1,
    ):
        base = _handled_lookup_program(registry, asset_id, index)
        streams.append(
            (
                IdleTopupSpec(
                    f"handled-result-{index:02d}",
                    f"idle-topup-handled-result-{index:02d}",
                    "consumed_lookup_result",
                    (len(base.actions) - 1,),
                ),
                base,
            )
        )
    for index, asset_id in enumerate(_TIMER_ASSETS[:2], 1):
        base = build_family_program(
            CorpusFamily.TIMER_NORMAL,
            registry,
            split=Split.TRAIN,
            template_id=_TIMER_TEMPLATE,
            asset_ids=(asset_id,),
            master_seed=f"phase2-idle-topup-v2:handled-fire-{index:02d}",
        )
        nudge = next(action for action in base.actions if isinstance(action, NudgeAction))
        streams.append(
            (
                IdleTopupSpec(
                    f"handled-fire-{index:02d}",
                    f"idle-topup-handled-fire-{index:02d}",
                    "handled_timer_fire",
                    (len(base.actions) - 1,),
                ),
                _append_handled(base, nudge.fire_event_id),
            )
        )
    return streams


def _append_handled(program: ScenarioProgram, related_event_id: str) -> ScenarioProgram:
    if isinstance(program.actions[-1], IdleAction):
        return replace(
            program,
            master_seed=f"{program.master_seed}:handled",
            actions=(
                *program.actions[:-1],
                IdleAction(
                    type="idle",
                    reason=IdleReason.ALREADY_HANDLED,
                    related_event_id=related_event_id,
                ),
            ),
            prompt_template=_PROMPT_TEMPLATE,
            counterfactual=None,
        )
    index = len(program.actions)
    beat = f"b{index}"
    plan = materialize_timing_plan(program.timing_plan.seed, index + 1)
    frames = program.frames
    if isinstance(program.actions[-1], RespondAction):
        latest = parse_tim_json(program.frames[-1].raw_bytes)
        frames = (
            *program.frames,
            _snapshot_frame(
                plan.service_ms[0] + 1,
                str(latest["text"]),
                activity=str(latest["activity"]),
                composing=bool(latest["is_composing"]),
            ),
        )
    return replace(
        program,
        master_seed=f"{program.master_seed}:handled",
        timing_plan=plan,
        frames=frames,
        actions=(
            *program.actions,
            IdleAction(
                type="idle",
                reason=IdleReason.ALREADY_HANDLED,
                related_event_id=related_event_id,
            ),
        ),
        beat_ids=(*program.beat_ids, beat),
        stale_results_by_beat=(*program.stale_results_by_beat, BeatStaleResults(beat, ())),
        prompt_template=_PROMPT_TEMPLATE,
        counterfactual=None,
    )


def _handled_lookup_program(registry: AssetRegistry, asset_id: str, index: int) -> ScenarioProgram:
    bundle, template = select_approved_scenario_inputs(
        registry,
        split=Split.TRAIN,
        template_id=_LOOKUP_TEMPLATE,
        asset_ids=(asset_id,),
    )
    payload = bundle.assets[0].payload
    if not isinstance(payload, LookupAssetPayload):
        raise IdleTopupError("handled-result source is not a lookup asset")
    seed = f"phase2-idle-topup-v2:handled-result-{index:02d}"
    plan = materialize_timing_plan(TimingSeed(Split.TRAIN, seed), 4)
    query = payload.query
    return ScenarioProgram(
        bundle=bundle,
        template=template,
        family=CorpusFamily.LOOKUP_LIVE,
        master_seed=seed,
        timing_plan=plan,
        frames=(
            _snapshot_frame(0, query, activity="paused"),
            _snapshot_frame(plan.service_ms[0] + 1, query, activity="paused"),
            _snapshot_frame(
                plan.service_ms[0] + 700 + plan.service_ms[2] + 1,
                query,
                activity="paused",
            ),
        ),
        actions=(
            DelegateAction(
                type="delegate",
                fact=Span(
                    event_id="e_000002",
                    start_utf16=0,
                    end_utf16=utf16_len(query),
                    text=query,
                ),
                tool=ToolName.LOOKUP,
                args={"query": query},
            ),
            IdleAction(
                type="idle",
                reason=IdleReason.AWAITING_TOOL,
                related_event_id="e_000002",
            ),
            IntegrateAction(
                type="integrate",
                result_event_id="e_000006",
                text=payload.result_a,
            ),
            IdleAction(
                type="idle",
                reason=IdleReason.ALREADY_HANDLED,
                related_event_id="e_000006",
            ),
        ),
        tool_results=(ScriptedToolResult(latency_ms=700, data={"nonce": payload.result_a}),),
        beat_ids=("b0", "b1", "b2", "b3"),
        stale_results_by_beat=tuple(
            BeatStaleResults(beat, ()) for beat in ("b0", "b1", "b2", "b3")
        ),
        perturbations=(),
        prompt_template=_PROMPT_TEMPLATE,
    )


async def _execute(
    root: Path,
    directory: Path,
    *,
    repair_only: bool = False,
    typing_shortfall_only: bool = False,
) -> tuple[ExecutedIdleTopup, ...]:
    if repair_only and typing_shortfall_only:
        raise IdleTopupError("top-up scopes are mutually exclusive")
    registry = _registry(root)
    planned = (
        _mark_replacement_repair_streams(registry)
        if repair_only
        else _typing_shortfall_streams(registry)
        if typing_shortfall_only
        else [
            *_typing_streams(registry),
            *_mark_ambiguous_streams(registry),
            *_timer_ambiguous_streams(registry),
            *_handled_streams(registry, root),
        ]
    )
    executed = []
    for spec, program in planned:
        generated = await execute_scenario(
            program,
            session_id=f"phase2-idle-topup-{spec.logical_stream_id}",
            directory=directory / spec.logical_stream_id,
            repository_root=root,
        )
        validate_generated_scenario(generated)
        executed.append(ExecutedIdleTopup(spec, generated))
    return tuple(executed)


def _validate(
    executed: tuple[ExecutedIdleTopup, ...],
    root: Path,
    *,
    repair_only: bool = False,
    typing_shortfall_only: bool = False,
) -> dict[str, object]:
    targets = Counter()
    policy_hashes = set()
    stream_hashes = set()
    shape_counts = Counter()
    for item in executed:
        if item.generated.program.bundle.split is not Split.TRAIN:
            raise IdleTopupError("top-up escaped TRAIN")
        stream_hashes.add(item.generated.stream.sha256)
        shape_counts[item.spec.shape_id] += 1
        for index in item.spec.target_indices:
            action = item.generated.program.actions[index]
            if not isinstance(action, IdleAction):
                raise IdleTopupError("top-up target is not idle")
            targets[action.reason.value] += 1
            policy_hashes.add(digest(item.generated.decision_boundaries[index].policy_bytes))
    expected = (
        {"ambiguous": 6}
        if repair_only
        else {"typing_active": 21}
        if typing_shortfall_only
        else {"already_handled": 6, "ambiguous": 18, "typing_active": 20}
    )
    if targets != expected:
        raise IdleTopupError(f"top-up reason inventory drifted: {dict(targets)}")
    expected_count = 6 if repair_only else 21 if typing_shortfall_only else 44
    if (
        len(executed) != expected_count
        or len(stream_hashes) != len(executed)
        or len(policy_hashes) != expected_count
    ):
        raise IdleTopupError("top-up streams or target inputs are not unique")
    if digest((root / _SELECTION_CONTRACT).read_bytes()) != (
        "sha256:72e234e0767c5ea6e8a620e053746584cf7e9d546ba3d3dfeef929d209d85ea3"
    ):
        raise IdleTopupError("v2 selection contract drifted")
    return {
        "checks": {
            "all_target_actions_are_genuine_idle_boundaries": True,
            "all_target_policy_inputs_unique": True,
            "all_topup_streams_train_bound": True,
            "ordinary_active_drafting_relabel_count": 0,
            "teacher_derived_selection_feature_count": 0,
            "whole_runtime_streams_preserved": True,
        },
        "format_version": 1,
        "kind": "phase2-wp2-6-idle-topup-pre-upload-battery",
        "reason_counts": dict(sorted(targets.items())),
        "shape_counts": dict(sorted(shape_counts.items())),
        "status": "passed",
        "stream_count": len(executed),
        "target_decision_count": sum(targets.values()),
    }


def _teacher_files(
    executed: tuple[ExecutedIdleTopup, ...],
    root: Path,
    *,
    repair_only: bool = False,
    typing_shortfall_only: bool = False,
) -> tuple[dict[str, bytes], int]:
    artifacts = PromptArtifacts(
        behavior_spec=(root / "spec/behavior-spec.md").read_bytes(),
        action_schema=(root / "spec/schema/action-v1.json").read_bytes(),
        prompt_template=(root / f"spec/{_PROMPT_TEMPLATE}").read_bytes(),
    )
    builder = ResponsesRequestBuilder(
        PromptRenderer(artifacts),
        PromptedPolicyConfig(
            model="gpt-5.6-sol",
            reasoning_effort="high",
            max_output_tokens=8_192,
            max_attempts=1,
        ),
    )
    cases = []
    targets = []
    system_prompt = None
    for item in executed:
        for index in item.spec.target_indices:
            boundary = item.generated.decision_boundaries[index]
            action = item.generated.program.actions[index]
            prefix = "t2i2r" if repair_only else "t2i2t" if typing_shortfall_only else "t2i2"
            internal_id = f"{prefix}.{item.spec.logical_stream_id}.d{index:03d}.a1"
            public_id = (
                "case_"
                + sha256(
                    (
                        "phase2-idle-topup-repair-public-v2:"
                        if repair_only
                        else "phase2-idle-topup-typing-public-v2:"
                        if typing_shortfall_only
                        else "phase2-idle-topup-public-v2:"
                    ).encode()
                    + internal_id.encode()
                ).hexdigest()[:20]
            )
            body = builder.build(boundary.policy_bytes)
            prompt = _message(body, 0)
            if system_prompt is None:
                system_prompt = prompt
            elif system_prompt != prompt:
                raise IdleTopupError("teacher system prompt drifted within the top-up")
            policy_stream = _message(body, 1)
            cases.append(
                {
                    "candidate_ordinal": index,
                    "custom_id": public_id,
                    "input_sha256": digest(policy_stream.encode()),
                    "logical_stream_id": item.spec.logical_stream_id,
                    "policy_stream": policy_stream,
                }
            )
            targets.append(
                {
                    "custom_id": internal_id,
                    "decision_policy_seq": item.generated.sidecar.decisions[
                        index
                    ].observed_policy_seq,
                    "family": item.generated.program.family.value,
                    "logical_stream_id": item.spec.logical_stream_id,
                    "oracle_action": action.model_dump(mode="json"),
                    "policy_prefix_sha256": digest(boundary.policy_bytes),
                    "program_action_index": index,
                    "prompt_hash": artifacts.prompt_hash,
                    "request_body_sha256": digest(canonical_artifact_bytes(body)),
                    "shape_id": item.spec.shape_id,
                    "source_unit_id": item.spec.source_unit_id,
                    "stream_sha256": item.generated.stream.sha256,
                    "teacher_case_id": public_id,
                }
            )
    expected_count = 6 if repair_only else 21 if typing_shortfall_only else 44
    if len(cases) != expected_count or system_prompt is None:
        raise IdleTopupError("teacher target inventory drifted")
    rounds = _rounds(
        cases,
        system_prompt,
        ordering_seed=(
            "phase2-idle-topup-repair-v2"
            if repair_only
            else "phase2-idle-topup-typing-v2"
            if typing_shortfall_only
            else "phase2-idle-topup-v2"
        ),
    )
    files: dict[str, bytes] = {}
    round_manifest = []
    for ordinal, round_cases in enumerate(rounds, 1):
        name = f"round-{ordinal:03d}"
        path = f"rounds/{name}.md"
        data = _round_markdown(name, round_cases, system_prompt, f"{name}.output.jsonl")
        tokens = estimate_tokens(data)
        if tokens > _MAX_ROUND_TOKENS:
            raise IdleTopupError(f"{name} exceeds the Chat token budget")
        files[path] = data
        round_manifest.append(
            {
                "case_count": len(round_cases),
                "case_ids": [case["custom_id"] for case in round_cases],
                "estimated_tokens": tokens,
                "input_path": path,
                "input_sha256": digest(data),
                "output_filename": f"{name}.output.jsonl",
            }
        )
    plan = {
        "api_call_performed": False,
        "format_version": 1,
        "intended_model": "GPT-5.6 Sol",
        "kind": (
            "phase2-wp2-6-idle-topup-repair-chat-ui-teacher-plan"
            if repair_only
            else "phase2-wp2-6-idle-topup-typing-chat-ui-teacher-plan"
            if typing_shortfall_only
            else "phase2-wp2-6-idle-topup-chat-ui-teacher-plan"
        ),
        "manual_model_attestation_required": True,
        "oracle_blinded_inputs": True,
        "prompt_hash": artifacts.prompt_hash,
        "reasoning": "high",
        "round_count": len(round_manifest),
        "rounds": round_manifest,
        "source_bindings": {
            "owner_decision_sha256": digest((root / _OWNER_DECISION).read_bytes()),
            "selection_contract_v2_sha256": digest((root / _SELECTION_CONTRACT).read_bytes()),
        },
        "target_decision_count": len(targets),
        "targets": targets,
    }
    files["teacher-plan.json"] = canonical_artifact_bytes(plan)
    return files, len(round_manifest)


def _packet(
    executed: tuple[ExecutedIdleTopup, ...],
    root: Path,
    *,
    repair_only: bool = False,
    typing_shortfall_only: bool = False,
) -> IdleTopupPacket:
    battery = _validate(
        executed,
        root,
        repair_only=repair_only,
        typing_shortfall_only=typing_shortfall_only,
    )
    teacher_files, round_count = _teacher_files(
        executed,
        root,
        repair_only=repair_only,
        typing_shortfall_only=typing_shortfall_only,
    )
    manifest = PackageManifest.build(item.generated for item in executed).canonical_bytes
    files = {
        "README.md": _readme(
            repair_only=repair_only,
            typing_shortfall_only=typing_shortfall_only,
        ).encode(),
        "manifest.json": manifest,
        "pre-upload-battery.json": canonical_artifact_bytes(battery),
        "raw-streams.json": canonical_artifact_bytes(
            {
                "format_version": 1,
                "streams": [_raw_stream(item) for item in executed],  # type: ignore[arg-type]
            }
        ),
        "source-index.json": canonical_artifact_bytes(_source_index(executed)),
        **teacher_files,
        **_runtime_files(executed),  # type: ignore[arg-type]
    }
    files["SHA256SUMS"] = _checksums(files)
    return IdleTopupPacket(files, len(executed), len(executed), round_count)


async def build_idle_topup_packet(
    *,
    repository_root: Path = _ROOT,
    repair_only: bool = False,
    typing_shortfall_only: bool = False,
) -> IdleTopupPacket:
    root = repository_root.resolve()
    with TemporaryDirectory(prefix="phase2-idle-topup-") as temporary:
        executed = await _execute(
            root,
            Path(temporary),
            repair_only=repair_only,
            typing_shortfall_only=typing_shortfall_only,
        )
        return _packet(
            executed,
            root,
            repair_only=repair_only,
            typing_shortfall_only=typing_shortfall_only,
        )


async def materialize_idle_topup_packet(
    output: Path = DEFAULT_IDLE_TOPUP_OUTPUT,
    *,
    repository_root: Path = _ROOT,
    repair_only: bool = False,
    typing_shortfall_only: bool = False,
) -> IdleTopupPacket:
    packet = await build_idle_topup_packet(
        repository_root=repository_root,
        repair_only=repair_only,
        typing_shortfall_only=typing_shortfall_only,
    )
    publish_directory_transaction(output, packet.files)
    return packet


def _source_index(executed: tuple[ExecutedIdleTopup, ...]) -> dict[str, object]:
    return {
        "batch": 1,
        "format_version": 1,
        "source_identity_rule": "one complete TRAIN runtime source per v2 top-up unit",
        "sources": [
            {
                "checkpoint": (
                    None
                    if item.selected_segment is None
                    else item.selected_segment.as_json_object()
                ),
                "family": item.generated.program.family.value,
                "master_seed": item.generated.program.master_seed,
                "parent_stream_sha256s": [item.generated.stream.sha256],
                "raw_source_sha256s": [
                    (
                        item.generated.stream.capture_sha256
                        if item.selected_segment is None
                        else item.selected_segment.segment.sha256
                    )
                ],
                "role": item.spec.shape_id,
                "shape_id": item.spec.shape_id,
                "sidecar_sha256s": [item.generated.sidecar.sha256],
                "source_decision_counts": [
                    (
                        len(item.generated.program.actions)
                        if item.selected_segment is None
                        else len(item.selected_segment.selected_actions)
                    )
                ],
                "source_kind": (
                    "runtime_parent" if item.selected_segment is None else "checkpoint_segment"
                ),
                "source_unit_id": item.spec.source_unit_id,
            }
            for item in executed
        ],
    }


def _lookup_query(registry: AssetRegistry, asset_id: str) -> str:
    asset = next(
        item
        for item in registry.pool(Split.TRAIN).assets
        if item.asset_id == asset_id and registry.is_approved(item)
    )
    query = getattr(asset.payload, "query", None)
    if not isinstance(query, str):
        raise IdleTopupError(f"{asset_id} is not a lookup asset")
    return query


def _frame(at_ms: int, text: str, *, composing: bool = False) -> ScheduledSamplerFrame:
    return _snapshot_frame(at_ms, text, activity="active", composing=composing)


def _snapshot_frame(
    at_ms: int,
    text: str,
    *,
    activity: str,
    composing: bool = False,
) -> ScheduledSamplerFrame:
    cursor = utf16_len(text)
    return ScheduledSamplerFrame(
        at_ms,
        canonicalize_tim_json(
            {
                "activity": activity,
                "client_ts": at_ms,
                "input_type": "insertCompositionText" if composing else "insertText",
                "is_composing": composing,
                "selection_end": cursor,
                "selection_start": cursor,
                "text": text,
            }
        ),
    )


def _idle(reason: IdleReason) -> IdleAction:
    return IdleAction(type="idle", reason=reason, related_event_id=None)


def _message(body: dict[str, object], index: int) -> str:
    try:
        value = body["input"][index]["content"][0]["text"]  # type: ignore[index]
    except (IndexError, KeyError, TypeError) as error:
        raise IdleTopupError("teacher request message shape drifted") from error
    if not isinstance(value, str):
        raise IdleTopupError("teacher request message is not text")
    return value


def _readme(
    *,
    repair_only: bool = False,
    typing_shortfall_only: bool = False,
) -> str:
    if repair_only:
        return """# WP2-6 v2 idle-reason top-up scoped repair

This packet replaces only the six ambiguous mark-replacement targets whose
original context exposed exactly one alternative. Each repaired context exposes
two alternatives, so “the other label category” remains genuinely unresolved.

Submit the single round in a fresh GPT-5.6 Sol/high chat and return the requested
JSONL file. No API call is part of this packet.
"""
    if typing_shortfall_only:
        return """# WP2-6 typing-active shortfall packet

This scoped packet adds 21 genuine incomplete-action boundaries after the normalized accepted
pool proved that the earlier approximate inventory had counted ineligible material. It contains
seven partial timer messages, seven partial mark controls, and seven incomplete lookup subjects.
Ordinary active drafting is not relabeled.

Submit the single round in a fresh GPT-5.6 Sol/high chat and return its JSONL output.
"""
    return """# WP2-6 v2 idle-reason top-up

This packet contains the small owner-approved feasibility top-up for
`phase2-selection-v2`:

- 20 genuine incomplete-action `typing_active` targets;
- 18 genuinely unresolved `ambiguous` targets;
- 6 consumed-event `already_handled` targets.

Ordinary active drafting is never relabeled as `typing_active`. Setup actions remain in their
complete runtime streams so the later feasibility witness sees the real whole-stream coupling.
The Chat rounds are oracle-blind and require GPT-5.6 Sol with high reasoning.
"""


def _checksums(files: dict[str, bytes]) -> bytes:
    return "".join(
        f"{sha256(data).hexdigest()}  {name}\n" for name, data in sorted(files.items())
    ).encode()
