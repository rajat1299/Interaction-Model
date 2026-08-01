"""Deterministic WP2-4 mark Wave-2 candidate pool and Chat packet."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, replace
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

from im.assets import AssetRegistry, CorpusFamily, Split
from im.assets.model import TextAssetPayload, TextForm, canonical_artifact_bytes
from im.config import estimate_tokens
from im.generation.g7_catalog import (
    G7FamilyInputs,
    _frame,
    _idle,
    _mark_recipe,
    _program,
    _timing,
)
from im.generation.g7_response_assets import SimpleResponseProfile
from im.generation.g7_response_twins import build_g7_response_floor_twin_program
from im.generation.mark_negative_policy import mark_negative_idle_reason
from im.generation.phase2_lookup_wave0 import _raw_stream, load_lookup_wave0_inputs
from im.generation.phase2_lookup_wave1 import _message
from im.generation.phase2_lookup_wave2 import _response_assets
from im.generation.phase2_mark_wave1 import (
    _NEGATIVE_RESPONSE_ORDINALS,
    _NEGATIVE_TEMPLATE,
    _POSITIVE_RESPONSE_ORDINALS,
    _POSITIVE_TEMPLATE,
)
from im.generation.phase2_review import (
    BoundaryClass,
    DecisionEvidence,
    FloorClass,
    TrustCellKey,
    route_wave,
)
from im.generation.phase2_timer_wave2_chat import _round_markdown, _rounds
from im.generation.publication import publish_directory_transaction
from im.generation.scenario_catalog import _prior_mark_control
from im.generation.scenarios import (
    GeneratedScenario,
    ScenarioProgram,
    execute_scenario,
    select_approved_scenario_inputs,
    validate_generated_scenario,
)
from im.policy.prompted import (
    PromptArtifacts,
    PromptedPolicyConfig,
    PromptRenderer,
    ResponsesRequestBuilder,
)
from im.probes.harness.identity import digest
from im.probes.harness.models import HarnessProtocol
from im.schema.actions import IdleAction, IdleReason, MarkAction, RespondAction

_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MARK_WAVE2_PLAN_OUTPUT = _ROOT / "review" / "phase2" / "mark-wave-2-plan-v4"
DEFAULT_MARK_WAVE2_OUTPUT = _ROOT / "review" / "phase2" / "mark-wave-2-v8"
_PLAN = Path("review/phase2/mark-wave-2-plan-v4")
_SUPERSEDED_PLANS = (
    Path("review/phase2/mark-wave-2-plan"),
    Path("review/phase2/mark-wave-2-plan-v2"),
    Path("review/phase2/mark-wave-2-plan-v3"),
)
_PROMPT_TEMPLATE = "prompt-template-v4.txt"
_STAGE = "t2mw2"
_MAX_OUTPUT_TOKENS = 8_192
_MAX_ROUND_TOKENS = 120_000
_EXPECTED_STREAMS = 87
_EXPECTED_SOURCE_UNITS = 69
_EXPECTED_DECISIONS = 462

_POSITIVE_ASSETS = (
    "a_052537ca3568ef0f0bb8d2ff",
    "a_4d9e7e5fdf179993fd3d8367",
    "a_4f45803171cb2679aa272baa",
    "a_7a61e645a7833002d053596d",
    "a_8870dc68ae7d0dc1e044ebd9",
    "a_c6b9ea7492dd47bde4d49e30",
    "a_e8143c61556d755caef0056f",
    "a_f351a4bfbebbcd5774458b62",
    "a_f56f7e4a3e7664469a021761",
    "a_fd6da4920d7808b5fa348adb",
)
_NEGATIVE_FORMS = (
    "a_15ad2d6715b3cf386a1e8806",
    "a_15ad2d6715b3cf386a1e8806",
    "a_15ad2d6715b3cf386a1e8806",
    "a_76f996251354c25a3c5d4a1d",
    "a_76f996251354c25a3c5d4a1d",
    "a_1e24348f52635e4451ccf7ec",
    "a_1e24348f52635e4451ccf7ec",
    "a_4403c1d7dc44aa1b08e481e8",
    "a_4403c1d7dc44aa1b08e481e8",
    "a_1fb02095621d94505e18eadf",
    "a_1fb02095621d94505e18eadf",
    "a_f474eca1aed953454b2fcdc7",
    "a_f474eca1aed953454b2fcdc7",
    "a_87a385b4ca57e3d7c0cf237b",
    "a_87a385b4ca57e3d7c0cf237b",
    "a_87a385b4ca57e3d7c0cf237b",
    "a_e0c1efbe331c909d31ead541",
    "a_e0c1efbe331c909d31ead541",
    "a_e0c1efbe331c909d31ead541",
)
_LIFECYCLE_ASSETS = (
    "a_e2dd083f4916def2a997d4bf",
    "a_f23b664ce3f705453eb63437",
    "a_047297e7827179204b66c329",
    "a_32863bc6a16105594851440b",
)
_NEGATIVE_BOUNDARY_ASSETS = tuple(dict.fromkeys(_NEGATIVE_FORMS))
_POSITIVE_RESERVE_SHAPES = ((4, 7), (5, 8), (6, 7), (7, 8), (7, 7))
_CONTEXT_SUBJECT_BY_ASSET = {
    _POSITIVE_ASSETS[0]: "draft",
    _POSITIVE_ASSETS[1]: "harbor notes",
    _POSITIVE_ASSETS[2]: "interview transcript",
    _POSITIVE_ASSETS[3]: "greenhouse log",
    _POSITIVE_ASSETS[4]: "route summary",
    _POSITIVE_ASSETS[5]: "weather journal",
    _POSITIVE_ASSETS[6]: "amphibian list",
    _POSITIVE_ASSETS[7]: "inspection report",
    _POSITIVE_ASSETS[8]: "field notebook",
    _POSITIVE_ASSETS[9]: "legend",
}
_LIFECYCLE_CONTEXT_SUBJECT_BY_ASSET = {
    _LIFECYCLE_ASSETS[0]: "animal index",
    _LIFECYCLE_ASSETS[1]: "species list",
    _LIFECYCLE_ASSETS[2]: "legend",
    _LIFECYCLE_ASSETS[3]: "route summary",
}
_CONTEXT_STATES = (
    "open for review",
    "being checked",
    "ready for annotation",
    "still in the editor",
    "under revision",
    "awaiting a final pass",
    "queued for copyediting",
    "in a final review pass",
)


class MarkWave2Error(ValueError):
    """The frozen mark Wave-2 pool is incomplete or unsafe."""


@dataclass(frozen=True, slots=True)
class MarkWave2Spec:
    logical_stream_id: str
    source_unit_id: str
    kind: str
    program: ScenarioProgram
    response_candidate_ordinal: int | None = None


@dataclass(frozen=True, slots=True)
class ExecutedMarkWave2:
    spec: MarkWave2Spec
    generated: GeneratedScenario
    selected_segment: None = None


@dataclass(frozen=True, slots=True)
class MarkWave2Artifact:
    files: dict[str, bytes]
    decision_count: int
    round_count: int
    stream_count: int


def build_mark_wave2_plan(*, repository_root: Path = _ROOT) -> MarkWave2Artifact:
    """Freeze the candidate inventory before executing any stream."""
    root = repository_root.resolve()
    baseline = _baseline(root)
    plan = {
        "baseline": baseline,
        "bindings": _plan_bindings(root),
        "candidate_generation": [
            {
                "candidate_actions": {"idle": 45, "mark": 63},
                "candidate_decisions": 108,
                "candidate_streams": 9,
                "multiplier_band": "standard",
                "shape_id": "mark-positive-5i-7m",
                "target_actions": {"idle": 40, "mark": 56},
                "target_decisions": 96,
                "target_streams": 8,
            },
            {
                "candidate_actions": {"idle": 29, "mark": 37},
                "candidate_decisions": 66,
                "candidate_streams": 5,
                "multiplier_band": "reserve_only",
                "shape_id": "mark-positive-diverse-shape-reserve",
                "target_actions": {"idle": 9, "mark": 15},
                "target_decisions": 24,
                "target_streams": 2,
            },
            {
                "candidate_actions": {"idle": 12, "mark": 16},
                "candidate_decisions": 28,
                "candidate_streams": 2,
                "multiplier_band": "standard",
                "shape_id": "mark-positive-6i-8m",
                "target_actions": {"idle": 6, "mark": 8},
                "target_decisions": 14,
                "target_streams": 1,
            },
            {
                "candidate_actions": {"idle": 16, "mark": 32},
                "candidate_decisions": 48,
                "candidate_streams": 4,
                "multiplier_band": "standard",
                "shape_id": "mark-positive-dense-4i-8m",
                "target_actions": {"idle": 4, "mark": 8},
                "target_decisions": 12,
                "target_streams": 1,
            },
            {
                "candidate_actions": {"idle": 9, "respond": 9},
                "candidate_decisions": 18,
                "candidate_streams": 18,
                "multiplier_band": "fragile",
                "shape_id": "mark-positive-response-floor",
                "target_actions": {"idle": 4, "respond": 4},
                "target_decisions": 8,
                "target_streams": 8,
            },
            {
                "candidate_actions": {"idle": 95, "mark": 57},
                "candidate_decisions": 152,
                "candidate_streams": 19,
                "multiplier_band": "standard",
                "shape_id": "mark-negative-5i-3m",
                "target_actions": {"idle": 55, "mark": 33},
                "target_decisions": 88,
                "target_streams": 11,
            },
            {
                "candidate_actions": {"idle": 8},
                "candidate_decisions": 8,
                "candidate_streams": 4,
                "multiplier_band": "standard",
                "shape_id": "mark-negative-direct-lifecycle",
                "target_actions": {"idle": 8},
                "target_decisions": 8,
                "target_streams": 4,
            },
            {
                "candidate_actions": {"idle": 16},
                "candidate_decisions": 16,
                "candidate_streams": 8,
                "multiplier_band": "standard",
                "shape_id": "mark-negative-standing-control-boundary",
                "target_actions": {"idle": 8},
                "target_decisions": 8,
                "target_streams": 4,
            },
            {
                "candidate_actions": {"idle": 9, "respond": 9},
                "candidate_decisions": 18,
                "candidate_streams": 18,
                "multiplier_band": "fragile",
                "shape_id": "mark-negative-response-floor",
                "target_actions": {"idle": 4, "respond": 4},
                "target_decisions": 8,
                "target_streams": 8,
            },
        ],
        "candidate_totals": {
            "actions": {"idle": 239, "mark": 205, "respond": 18},
            "decisions": 462,
            "source_units": 69,
            "streams": 87,
        },
        "external_model_call_performed": False,
        "final_selection": {
            "algorithm_execution": "deferred_until_all_accepted_streams_are_known",
            "candidate_unit": "complete_stream",
            "whole_stream_only": True,
        },
        "format_version": 4,
        "kind": "phase2-mark-wave2-candidate-plan-v4",
        "prediction": {
            "expected_result": (
                "At least one whole-stream candidate remains for every target shape after "
                "mechanical checks and mandatory review."
            ),
            "kill_criteria": [
                "any contract_gap",
                "any repeated Wave-1 ambiguity-suspension defect",
                "any unapproved response payload",
                "any final-materialized-stream coherence failure",
                "any semantic stream or exact teacher-input duplicate",
            ],
        },
        "response_dependency": {
            "candidate_pairs_per_family": 9,
            "remaining_owner_approved_records_per_family": 9,
            "target_pairs_per_family": 4,
            "unselected_pairs_remain_wave3_reserve": True,
        },
        "target": {
            "decisions": 266,
            "families": {
                "mark_activation_positive": {
                    "actions": {"idle": 63, "mark": 87, "respond": 4},
                    "decisions": 154,
                    "fraction_of_remaining": 0.647,
                },
                "mark_lifecycle_negative": {
                    "actions": {"idle": 75, "mark": 33, "respond": 4},
                    "decisions": 112,
                    "fraction_of_remaining": 0.602,
                },
            },
            "fraction_of_remaining": 0.627,
            "source_units": 39,
            "streams": 47,
        },
        "wave3_remainder": {
            "mark_activation_positive": {"idle": 35, "mark": 44, "respond": 5},
            "mark_lifecycle_negative": {"idle": 48, "mark": 21, "respond": 5},
        },
        "wave_id": "mark-wave-2",
    }
    files = {
        "PLAN.md": _plan_readme().encode(),
        "plan.json": canonical_artifact_bytes(plan),
    }
    files["SHA256SUMS"] = _checksums(files)
    return MarkWave2Artifact(files, 266, 0, 47)


def materialize_mark_wave2_plan(
    output: Path = DEFAULT_MARK_WAVE2_PLAN_OUTPUT,
    *,
    repository_root: Path = _ROOT,
) -> MarkWave2Artifact:
    artifact = build_mark_wave2_plan(repository_root=repository_root)
    publish_directory_transaction(output, artifact.files)
    return artifact


async def build_mark_wave2_packet(*, repository_root: Path = _ROOT) -> MarkWave2Artifact:
    """Execute the frozen candidate pool and render oracle-blind Chat rounds."""
    root = repository_root.resolve()
    _verify_checksums(root / _PLAN)
    registry = load_lookup_wave0_inputs()
    specs = _program_specs(registry, _response_assets(root))
    with TemporaryDirectory(prefix="phase2-mark-wave2-") as temporary:
        executed = []
        for spec in specs:
            generated = await execute_scenario(
                spec.program,
                session_id=f"phase2-mark-wave2-{spec.logical_stream_id}",
                directory=Path(temporary) / spec.logical_stream_id,
                repository_root=root,
            )
            validate_generated_scenario(generated)
            executed.append(ExecutedMarkWave2(spec, generated))
    values = tuple(executed)
    battery = _validate(values, root)
    return _packet(values, battery, root)


async def materialize_mark_wave2_packet(
    output: Path = DEFAULT_MARK_WAVE2_OUTPUT,
    *,
    repository_root: Path = _ROOT,
) -> MarkWave2Artifact:
    packet = await build_mark_wave2_packet(repository_root=repository_root)
    publish_directory_transaction(output, packet.files)
    return packet


def _program_specs(
    registry: AssetRegistry,
    response_assets: dict[int, object],
) -> tuple[MarkWave2Spec, ...]:
    specs = []
    for ordinal, asset_id in enumerate(_POSITIVE_ASSETS[1:]):
        specs.append(
            MarkWave2Spec(
                f"positive-core-{ordinal:02d}",
                f"mark-wave2-positive-core-{ordinal:02d}",
                "mark-positive-5i-7m",
                _fresh_mark_program(
                    registry,
                    family=CorpusFamily.MARK_POSITIVE,
                    template_id=_POSITIVE_TEMPLATE,
                    asset_ids=(asset_id,),
                    seed=f"phase2-mark-wave2:positive-core:{ordinal:02d}",
                    idle_count=5,
                    mark_count=7,
                    lead_in=_lead_in(asset_id, 0),
                ),
            )
        )
    for ordinal, (idle_count, mark_count) in enumerate(_POSITIVE_RESERVE_SHAPES):
        asset_id = _POSITIVE_ASSETS[ordinal]
        specs.append(
            MarkWave2Spec(
                f"positive-reserve-{ordinal:02d}",
                f"mark-wave2-positive-reserve-{ordinal:02d}",
                "mark-positive-diverse-shape-reserve",
                _fresh_mark_program(
                    registry,
                    family=CorpusFamily.MARK_POSITIVE,
                    template_id=_POSITIVE_TEMPLATE,
                    asset_ids=(asset_id,),
                    seed=f"phase2-mark-wave2:positive-reserve:{ordinal:02d}",
                    idle_count=idle_count,
                    mark_count=mark_count,
                    lead_in=_lead_in(asset_id, 1),
                ),
            )
        )
    for ordinal in range(2):
        asset_id = _POSITIVE_ASSETS[(ordinal + 5) % len(_POSITIVE_ASSETS)]
        specs.append(
            MarkWave2Spec(
                f"positive-wide-{ordinal:02d}",
                f"mark-wave2-positive-wide-{ordinal:02d}",
                "mark-positive-6i-8m",
                _fresh_mark_program(
                    registry,
                    family=CorpusFamily.MARK_POSITIVE,
                    template_id=_POSITIVE_TEMPLATE,
                    asset_ids=(asset_id,),
                    seed=f"phase2-mark-wave2:positive-wide:{ordinal:02d}",
                    idle_count=6,
                    mark_count=8,
                    lead_in=_lead_in(asset_id, 2),
                ),
            )
        )
    for ordinal in range(4):
        asset_id = _POSITIVE_ASSETS[(ordinal + 7) % len(_POSITIVE_ASSETS)]
        specs.append(
            MarkWave2Spec(
                f"positive-dense-{ordinal:02d}",
                f"mark-wave2-positive-dense-{ordinal:02d}",
                "mark-positive-dense-4i-8m",
                _fresh_mark_program(
                    registry,
                    family=CorpusFamily.MARK_POSITIVE,
                    template_id=_POSITIVE_TEMPLATE,
                    asset_ids=(asset_id,),
                    seed=f"phase2-mark-wave2:positive-dense:{ordinal:02d}",
                    idle_count=4,
                    mark_count=8,
                    lead_in=_lead_in(asset_id, 3),
                ),
            )
        )
    for ordinal, negative_id in enumerate(_NEGATIVE_FORMS):
        positive_id = _POSITIVE_ASSETS[ordinal % len(_POSITIVE_ASSETS)]
        specs.append(
            MarkWave2Spec(
                f"negative-core-{ordinal:02d}",
                f"mark-wave2-negative-core-{ordinal:02d}",
                "mark-negative-5i-3m",
                _fresh_mark_program(
                    registry,
                    family=CorpusFamily.MARK_NEGATIVE,
                    template_id=_NEGATIVE_TEMPLATE,
                    asset_ids=(positive_id, negative_id),
                    seed=f"phase2-mark-wave2:negative-core:{ordinal:02d}",
                    idle_count=5,
                    mark_count=3,
                    lead_in=_lead_in(positive_id, 4 + ordinal // 10),
                ),
            )
        )
    for ordinal, asset_id in enumerate(_LIFECYCLE_ASSETS):
        specs.append(
            MarkWave2Spec(
                f"negative-lifecycle-{ordinal:02d}",
                f"mark-wave2-negative-lifecycle-{ordinal:02d}",
                "mark-negative-direct-lifecycle",
                _lifecycle_program(
                    registry,
                    asset_id,
                    f"phase2-mark-wave2:lifecycle:{ordinal:02d}",
                    (
                        f"The {_LIFECYCLE_CONTEXT_SUBJECT_BY_ASSET[asset_id]} "
                        "is awaiting a final pass."
                    ),
                ),
            )
        )
    for ordinal, negative_id in enumerate(_NEGATIVE_BOUNDARY_ASSETS):
        specs.append(
            MarkWave2Spec(
                f"negative-boundary-{ordinal:02d}",
                f"mark-wave2-negative-boundary-{ordinal:02d}",
                "mark-negative-standing-control-boundary",
                _negative_boundary_program(
                    registry,
                    _POSITIVE_ASSETS[ordinal],
                    negative_id,
                    f"phase2-mark-wave2:negative-boundary:{ordinal:02d}",
                    _lead_in(_POSITIVE_ASSETS[ordinal], 6),
                ),
            )
        )
    specs.extend(
        _response_specs(
            registry,
            response_assets,
            CorpusFamily.MARK_POSITIVE,
            _POSITIVE_RESPONSE_ORDINALS,
        )
    )
    specs.extend(
        _response_specs(
            registry,
            response_assets,
            CorpusFamily.MARK_NEGATIVE,
            _NEGATIVE_RESPONSE_ORDINALS,
        )
    )
    return tuple(specs)


def _fresh_mark_program(
    registry: AssetRegistry,
    *,
    family: CorpusFamily,
    template_id: str,
    asset_ids: tuple[str, ...],
    seed: str,
    idle_count: int,
    mark_count: int,
    lead_in: str,
) -> ScenarioProgram:
    bundle, template = select_approved_scenario_inputs(
        registry,
        split=Split.TRAIN,
        template_id=template_id,
        asset_ids=asset_ids,
    )
    return replace(
        _mark_recipe(
            bundle,
            template,
            family,
            seed,
            idle_count,
            mark_count,
            lead_in=lead_in,
        ),
        prompt_template=_PROMPT_TEMPLATE,
    )


def _lifecycle_program(
    registry: AssetRegistry,
    asset_id: str,
    seed: str,
    lead_in: str,
) -> ScenarioProgram:
    bundle, template = select_approved_scenario_inputs(
        registry,
        split=Split.TRAIN,
        template_id=_NEGATIVE_TEMPLATE,
        asset_ids=(asset_id,),
    )
    asset = bundle.assets[0]
    assert isinstance(asset.payload, TextAssetPayload)
    control = _prior_mark_control(asset.payload.text)
    subject = control.removeprefix("Mark every occurrence of ").removesuffix(".")
    plan = _timing(Split.TRAIN, f"g7-fresh:{seed}", 2)
    program = _program(
        bundle,
        template,
        CorpusFamily.MARK_NEGATIVE,
        seed,
        plan,
        (
            _frame(0, f"{lead_in}\n{control}\nThe current draft already mentions {subject}."),
            _frame(plan.service_ms[0] + 1, asset.payload.text),
        ),
        (_idle(), _idle()),
    )
    return replace(program, prompt_template=_PROMPT_TEMPLATE)


def _negative_boundary_program(
    registry: AssetRegistry,
    positive_id: str,
    negative_id: str,
    seed: str,
    lead_in: str,
) -> ScenarioProgram:
    bundle, template = select_approved_scenario_inputs(
        registry,
        split=Split.TRAIN,
        template_id=_NEGATIVE_TEMPLATE,
        asset_ids=(positive_id, negative_id),
    )
    positive = next(
        asset for asset in bundle.assets if CorpusFamily.MARK_POSITIVE in asset.coverage
    )
    negative = next(
        asset for asset in bundle.assets if CorpusFamily.MARK_NEGATIVE in asset.coverage
    )
    assert isinstance(positive.payload, TextAssetPayload)
    assert isinstance(negative.payload, TextAssetPayload)
    control = f"{lead_in}\n{positive.payload.text}"
    plan = _timing(Split.TRAIN, f"g7-fresh:{seed}", 2)
    reason = mark_negative_idle_reason(
        negative.payload.form,
        partial_form_reason=IdleReason.TYPING_ACTIVE,
    )
    program = _program(
        bundle,
        template,
        CorpusFamily.MARK_NEGATIVE,
        seed,
        plan,
        (
            _frame(0, control),
            _frame(
                plan.service_ms[0] + 1,
                f"{control}\n{negative.payload.text}",
                "active"
                if negative.payload.form in {TextForm.AMBIGUOUS, TextForm.PARTIAL}
                else "paused",
            ),
        ),
        (_idle(), _idle(reason)),
    )
    return replace(program, prompt_template=_PROMPT_TEMPLATE)


def _lead_in(asset_id: str, state_index: int) -> str:
    subject = _CONTEXT_SUBJECT_BY_ASSET[asset_id]
    state = _CONTEXT_STATES[state_index]
    verb = "are" if subject == "harbor notes" else "is"
    return f"The {subject} {verb} {state}."


def _response_specs(
    registry: AssetRegistry,
    response_assets: dict[int, object],
    family: CorpusFamily,
    ordinals: tuple[int, ...],
) -> tuple[MarkWave2Spec, ...]:
    profile = SimpleResponseProfile(tuple(response_assets[index] for index in ordinals))  # type: ignore[arg-type]
    specs = []
    for item_index in range(1, 10):
        asset_id = _POSITIVE_ASSETS[item_index % len(_POSITIVE_ASSETS)]
        inputs = (
            G7FamilyInputs(_POSITIVE_TEMPLATE, (asset_id,))
            if family is CorpusFamily.MARK_POSITIVE
            else G7FamilyInputs(
                _NEGATIVE_TEMPLATE,
                (asset_id, "a_15ad2d6715b3cf386a1e8806"),
            )
        )
        pair = build_g7_response_floor_twin_program(
            registry,
            split=Split.TRAIN,
            family=family,
            inputs=inputs,
            profile=profile,
            master_seed=f"phase2-mark-wave2:response:{family.value}:{item_index:02d}",
            item_index=item_index,
        )
        for member, program in zip(("yielded", "active"), pair.programs, strict=True):
            specs.append(
                MarkWave2Spec(
                    f"{family.value}-response-{item_index:02d}-{member}",
                    f"mark-wave2-{family.value}-response-{item_index:02d}",
                    f"{family.value}-response-floor",
                    replace(program, prompt_template=_PROMPT_TEMPLATE),
                    ordinals[item_index],
                )
            )
    return tuple(specs)


def _validate(
    executed: tuple[ExecutedMarkWave2, ...],
    root: Path,
) -> dict[str, object]:
    family_actions: dict[str, Counter[str]] = {}
    kind_counts = Counter()
    kind_decisions = Counter()
    assets = set()
    hashes = set()
    expected_prompt = digest((root / "spec" / _PROMPT_TEMPLATE).read_bytes())
    for item in executed:
        program = item.generated.program
        family = program.family.value
        actions = Counter(action.type for action in program.actions)
        family_actions.setdefault(family, Counter()).update(actions)
        kind_counts[item.spec.kind] += 1
        kind_decisions[item.spec.kind] += len(program.actions)
        assets.update(program.asset_ids)
        hashes.add(item.generated.stream.sha256)
        if (
            program.bundle.split is not Split.TRAIN
            or program.prompt_template != _PROMPT_TEMPLATE
            or dict(item.generated.stream.provenance.artifact_hashes).get("prompt")
            != expected_prompt
        ):
            raise MarkWave2Error("Wave-2 escaped sealed TRAIN prompt-v4 inputs")
    expected_kinds = {
        "mark-positive-5i-7m": (9, 108),
        "mark-positive-diverse-shape-reserve": (5, 66),
        "mark-positive-6i-8m": (2, 28),
        "mark-positive-dense-4i-8m": (4, 48),
        "mark-negative-5i-3m": (19, 152),
        "mark-negative-direct-lifecycle": (4, 8),
        "mark-negative-standing-control-boundary": (8, 16),
        "mark_activation_positive-response-floor": (18, 18),
        "mark_lifecycle_negative-response-floor": (18, 18),
    }
    if (
        len(executed) != _EXPECTED_STREAMS
        or len({item.spec.source_unit_id for item in executed}) != _EXPECTED_SOURCE_UNITS
        or sum(len(item.generated.program.actions) for item in executed)
        != _EXPECTED_DECISIONS
        or len(hashes) != _EXPECTED_STREAMS
        or {
            kind: (kind_counts[kind], kind_decisions[kind]) for kind in expected_kinds
        }
        != expected_kinds
    ):
        raise MarkWave2Error("Wave-2 stream/source/decision inventory drifted")
    expected_actions = {
        CorpusFamily.MARK_POSITIVE.value: Counter(idle=111, mark=148, respond=9),
        CorpusFamily.MARK_NEGATIVE.value: Counter(idle=128, mark=57, respond=9),
    }
    if family_actions != expected_actions:
        raise MarkWave2Error("Wave-2 family/action composition drifted")
    candidate_semantics = [_semantic_signature(_raw_stream(item)) for item in executed]
    if (
        len(assets) != 22
        or hashes & _prior_stream_hashes(root)
        or len(set(candidate_semantics)) != len(candidate_semantics)
        or set(candidate_semantics) & _prior_semantic_signatures(root)
    ):
        raise MarkWave2Error("Wave-2 asset coverage or stream disjointness failed")

    lifecycle = [
        item
        for item in executed
        if item.spec.kind == "mark-negative-direct-lifecycle"
    ]
    if any(
        len(item.generated.program.actions) != 2
        or len(item.generated.program.frames) != 2
        or any(
            not isinstance(action, IdleAction) or action.reason is not IdleReason.NO_TRIGGER
            for action in item.generated.program.actions
        )
        for item in lifecycle
    ):
        raise MarkWave2Error("direct stop/replacement lifecycle behavior drifted")
    boundaries = [
        item
        for item in executed
        if item.spec.kind == "mark-negative-standing-control-boundary"
    ]
    if len(boundaries) != 8 or any(
        len(item.generated.program.actions) != 2
        or not all(
            isinstance(action, IdleAction)
            for action in item.generated.program.actions
        )
        for item in boundaries
    ):
        raise MarkWave2Error("standing-control boundary inventory drifted")
    ambiguous = [
        item
        for item in executed
        if "a_15ad2d6715b3cf386a1e8806" in item.generated.program.asset_ids
        and item.spec.kind == "mark-negative-5i-3m"
    ]
    if not ambiguous or any(
        not any(
            isinstance(action, IdleAction) and action.reason is IdleReason.AMBIGUOUS
            for action in item.generated.program.actions
        )
        or sum(isinstance(action, MarkAction) for action in item.generated.program.actions) != 3
        for item in ambiguous
    ):
        raise MarkWave2Error("ambiguous suspension boundary disappeared")
    partial_reasons = {
        action.reason
        for item in executed
        if item.spec.kind == "mark-negative-5i-3m"
        for action in item.generated.program.actions
        if isinstance(action, IdleAction)
    }
    if not {
        IdleReason.AMBIGUOUS,
        IdleReason.INSTRUCTION_NOT_DIRECT,
        IdleReason.TYPING_ACTIVE,
    } <= partial_reasons:
        raise MarkWave2Error("negative subtype coverage drifted")
    response_ordinals = Counter(
        item.spec.response_candidate_ordinal
        for item in executed
        if item.spec.response_candidate_ordinal is not None
    )
    if (
        response_ordinals
        != Counter(
            {
                **{ordinal: 2 for ordinal in _POSITIVE_RESPONSE_ORDINALS[1:]},
                **{ordinal: 2 for ordinal in _NEGATIVE_RESPONSE_ORDINALS[1:]},
            }
        )
        or any(
            not isinstance(item.generated.program.actions[0], (RespondAction, IdleAction))
            for item in executed
            if item.spec.response_candidate_ordinal is not None
        )
    ):
        raise MarkWave2Error("remaining owner-approved response pairs drifted")
    date_marks = [
        action
        for item in executed
        if "a_4d9e7e5fdf179993fd3d8367" in item.generated.program.asset_ids
        for action in item.generated.program.actions
        if isinstance(action, MarkAction)
    ]
    if not date_marks or any(action.target.text != "17 October 2031" for action in date_marks):
        raise MarkWave2Error("date target no longer renders verbatim")
    return {
        "action_counts": {
            family: dict(sorted(counts.items()))
            for family, counts in sorted(family_actions.items())
        },
        "checks": {
            "all_22_sealed_mark_assets_rendered": True,
            "ambiguous_replacement_suspends_future_marks": True,
            "date_target_rendered_verbatim": True,
            "direct_stop_and_replacement_controls_visible": True,
            "final_materialized_streams_checked": True,
            "no_prior_mark_stream_reused": True,
            "no_prior_or_internal_semantic_stream_reused": True,
            "quoted_code_and_partial_boundaries_present": True,
            "remaining_response_payloads_owner_selected": True,
            "teacher_inputs_are_exactly_unique": True,
        },
        "decision_count": _EXPECTED_DECISIONS,
        "format_version": 1,
        "kind": "phase2-mark-wave2-pre-upload-battery",
        "source_unit_count": _EXPECTED_SOURCE_UNITS,
        "stream_count": _EXPECTED_STREAMS,
    }


def _packet(
    executed: tuple[ExecutedMarkWave2, ...],
    battery: dict[str, object],
    root: Path,
) -> MarkWave2Artifact:
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
            max_output_tokens=_MAX_OUTPUT_TOKENS,
            max_attempts=1,
        ),
    )
    evidence, routes = _routes(executed)
    route_by_identity = {route.identity: route for route in routes}
    cases = []
    targets = []
    system_prompts = set()
    for item in executed:
        for index, action in enumerate(item.generated.program.actions):
            boundary = item.generated.decision_boundaries[index]
            custom_id = f"{_STAGE}.{item.spec.logical_stream_id}.d{index:03d}.a1"
            teacher_case_id = (
                "case_"
                + sha256(
                    f"phase2-mark-wave2-public-v1:{custom_id}".encode()
                ).hexdigest()[:20]
            )
            body = builder.build(boundary.policy_bytes)
            body_bytes = canonical_artifact_bytes(body)
            system_prompts.add(_message(body, 0))
            sidecar = item.generated.sidecar.decisions[index]
            decision = next(
                row
                for row in evidence
                if row.stream_sha256 == item.generated.stream.sha256
                and row.decision_policy_seq == sidecar.observed_policy_seq
            )
            route = route_by_identity[decision.identity]
            targets.append(
                {
                    "candidate_selected_program_action_indices": list(
                        range(len(item.generated.program.actions))
                    ),
                    "custom_id": custom_id,
                    "teacher_case_id": teacher_case_id,
                    "decision_policy_seq": sidecar.observed_policy_seq,
                    "family": item.generated.program.family.value,
                    "logical_stream_id": item.spec.logical_stream_id,
                    "oracle_action": action.model_dump(mode="json"),
                    "policy_prefix_sha256": digest(boundary.policy_bytes),
                    "program_action_index": index,
                    "prompt_hash": artifacts.prompt_hash,
                    "request_body_sha256": digest(body_bytes),
                    "response_candidate_ordinal": item.spec.response_candidate_ordinal,
                    "source_unit_id": item.spec.source_unit_id,
                    "static_d2_route": {
                        "mandatory_review": route.mandatory,
                        "reasons": list(route.reasons),
                        "review_required": route.review_required,
                        "sample_rate": route.sample_rate,
                    },
                    "stream_sha256": item.generated.stream.sha256,
                }
            )
            cases.append(
                {
                    "candidate_ordinal": (
                        100
                        if item.spec.response_candidate_ordinal is not None
                        and item.spec.logical_stream_id.endswith("-active")
                        else 101
                        if item.spec.response_candidate_ordinal is not None
                        else index
                    ),
                    "custom_id": teacher_case_id,
                    "input_sha256": digest(_message(body, 1).encode()),
                    "logical_stream_id": item.spec.logical_stream_id,
                    "policy_stream": _message(body, 1),
                }
            )
    if (
        len(cases) != _EXPECTED_DECISIONS
        or len(system_prompts) != 1
        or len({target["request_body_sha256"] for target in targets}) != len(targets)
    ):
        raise MarkWave2Error("teacher request inventory or exact policy drifted")
    system_prompt = system_prompts.pop()
    rounds = _rounds(
        cases,
        system_prompt,
        ordering_seed="phase2-mark-wave2-v4",
    )
    source_by_id = {
        target["teacher_case_id"]: target["source_unit_id"] for target in targets
    }
    if any(
        source_by_id[left["custom_id"]] == source_by_id[right["custom_id"]]
        for round_cases in rounds
        for left, right in zip(round_cases, round_cases[1:])
    ):
        raise MarkWave2Error("paired source units are adjacent in a Chat round")
    files: dict[str, bytes] = {
        "README.md": _readme(len(rounds)).encode(),
        "pre-upload-battery.json": canonical_artifact_bytes(battery),
        "raw-streams.json": canonical_artifact_bytes(
            {
                "format_version": 1,
                "kind": "phase2-mark-wave2-parent-candidates",
                "streams": [_raw_stream(item) for item in executed],  # type: ignore[arg-type]
            }
        ),
    }
    round_manifest = []
    for ordinal, round_cases in enumerate(rounds, 1):
        name = f"round-{ordinal:03d}"
        path = f"rounds/{name}.md"
        data = _round_markdown(name, round_cases, system_prompt, f"{name}.output.jsonl")
        tokens = estimate_tokens(data)
        if tokens > _MAX_ROUND_TOKENS:
            raise MarkWave2Error(f"{name} exceeds the Chat token budget")
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
    files["teacher-plan.json"] = canonical_artifact_bytes(
        {
            "api_call_performed": False,
            "authorization_state": "not_submitted",
            "decision_count": _EXPECTED_DECISIONS,
            "format_version": 1,
            "intended_model": "GPT-5.6 Sol",
            "kind": "phase2-mark-wave2-chat-ui-teacher-plan",
            "manual_model_attestation_required": True,
            "one_case_per_stream_per_round": True,
            "oracle_blinded_inputs": True,
            "prompt_hash": artifacts.prompt_hash,
            "reasoning": "high",
            "round_count": len(rounds),
            "rounds": round_manifest,
            "source_bindings": _packet_bindings(root),
            "source_unit_count": _EXPECTED_SOURCE_UNITS,
            "targets": targets,
            "teacher_transport": "chat_ui_manual",
            "wave_id": "mark-wave-2",
        }
    )
    if any(
        b'"oracle_action"' in data or b'"teacher_action"' in data
        for name, data in files.items()
        if name.startswith("rounds/")
    ):
        raise MarkWave2Error("Chat input exposes a candidate label")
    files["SHA256SUMS"] = _checksums(files)
    return MarkWave2Artifact(files, len(cases), len(rounds), len(executed))


def _routes(
    executed: tuple[ExecutedMarkWave2, ...],
) -> tuple[tuple[DecisionEvidence, ...], tuple[object, ...]]:
    evidence = []
    for item in executed:
        for index, action in enumerate(item.generated.program.actions):
            sidecar = item.generated.sidecar.decisions[index]
            floor = (
                FloorClass.OPEN
                if sidecar.floor_open
                else FloorClass.OWNED
                if sidecar.floor_owned
                else FloorClass.CLOSED
            )
            response_boundary = item.spec.response_candidate_ordinal is not None
            partial = (
                isinstance(action, IdleAction)
                and action.reason is IdleReason.TYPING_ACTIVE
            )
            evidence.append(
                DecisionEvidence(
                    stream_sha256=item.generated.stream.sha256,
                    decision_policy_seq=sidecar.observed_policy_seq,
                    wave_id="mark-wave-2",
                    cell=TrustCellKey(
                        HarnessProtocol.GENERATION,
                        item.generated.program.family,
                        floor,
                    ),
                    template_id=item.generated.program.template.asset_id,
                    source_unit_id=item.spec.source_unit_id,
                    oracle_action=action,
                    teacher_action=action,
                    causal_state_class=item.spec.kind,
                    boundary_class=(
                        BoundaryClass.ACTIVE_FLOOR_RESPONSE
                        if response_boundary
                        else BoundaryClass.PARTIAL_INSTRUCTION
                        if partial
                        else BoundaryClass.ORDINARY
                    ),
                    risk_flags=(
                        ("active_floor_response_boundary",)
                        if response_boundary
                        else ()
                    ),
                    idle_boundary="partial_instruction" if partial else None,
                    rollover=False,
                )
            )
    values = tuple(evidence)
    return values, route_wave(values, {}, sampling_seed="phase2-mark-wave2-d2-v1")


def _baseline(root: Path) -> dict[str, object]:
    wave0 = root / "review/phase2/mark-wave-0"
    wave1 = root / "review/phase2/mark-wave-1"
    final = root / "review/phase2/mark-wave-1-repair-v4-execution"
    for directory in (wave0, wave1, final):
        _verify_checksums(directory)
    comparison = json.loads((final / "comparison.json").read_bytes())
    if comparison.get("case_count") != 10 or comparison.get("non_equivalent_count") != 0:
        raise MarkWave2Error("mark Wave-1 repair gate is not closed")
    accepted = {
        "mark_activation_positive": {"idle": 22, "mark": 19, "respond": 1},
        "mark_lifecycle_negative": {"idle": 27, "mark": 6, "respond": 1},
    }
    target = {
        "mark_activation_positive": {"idle": 120, "mark": 150, "respond": 10},
        "mark_lifecycle_negative": {"idle": 150, "mark": 60, "respond": 10},
    }
    return {
        "accepted_decisions": 76,
        "families": {
            family: {
                "accepted": accepted[family],
                "remaining": {
                    action: count - accepted[family].get(action, 0)
                    for action, count in target[family].items()
                },
                "target": target[family],
            }
            for family in target
        },
        "wave_0_decisions": 14,
        "wave_1_decisions": 62,
    }


def _prior_stream_hashes(root: Path) -> set[str]:
    hashes = set()
    for relative, filename in (
        ("review/phase2/mark-wave-0", "raw-stream-evidence.json"),
        ("review/phase2/mark-wave-1", "raw-streams.json"),
        ("review/phase2/mark-wave-1-repair", "raw-streams.json"),
        ("review/phase2/mark-wave-1-repair-v3", "raw-stream.json"),
        ("review/phase2/mark-wave-1-repair-v4", "raw-stream.json"),
    ):
        directory = root / relative
        _verify_checksums(directory)
        raw = json.loads((directory / filename).read_bytes())
        hashes.update(
            row["stream_sha256"]
            for row in raw["streams"]
            if isinstance(row, dict) and isinstance(row.get("stream_sha256"), str)
        )
    return hashes


def _prior_semantic_signatures(root: Path) -> set[str]:
    signatures = set()
    for relative, filename in (
        ("review/phase2/mark-wave-0", "raw-stream-evidence.json"),
        ("review/phase2/mark-wave-1", "raw-streams.json"),
        ("review/phase2/mark-wave-1-repair", "raw-streams.json"),
        ("review/phase2/mark-wave-1-repair-v3", "raw-stream.json"),
        ("review/phase2/mark-wave-1-repair-v4", "raw-stream.json"),
    ):
        raw = json.loads((root / relative / filename).read_bytes())
        signatures.update(_semantic_signature(row) for row in raw["streams"])
    return signatures


def _semantic_signature(row: dict[str, object]) -> str:
    frames = []
    for frame in row["frames"]:  # type: ignore[index]
        sampler = dict(frame["sampler"])  # type: ignore[index]
        sampler.pop("client_ts", None)
        frames.append(sampler)
    return digest(
        canonical_artifact_bytes(
            {
                "actions": row["actions"],
                "frames": frames,
            }
        )
    )


def _plan_bindings(root: Path) -> dict[str, str]:
    return {
        "mark_wave0_packet_sha256": digest(
            (root / "review/phase2/mark-wave-0/SHA256SUMS").read_bytes()
        ),
        "mark_wave1_final_execution_sha256": digest(
            (
                root
                / "review/phase2/mark-wave-1-repair-v4-execution/SHA256SUMS"
            ).read_bytes()
        ),
        "mark_wave1_final_owner_disposition_sha256": digest(
            (
                root
                / "review/phase2/mark-wave-1-repair-v4-execution/OWNER-DISPOSITION.md"
            ).read_bytes()
        ),
        "response_selection_sha256": digest(
            (root / "review/phase2/response-tranche-selection/SHA256SUMS").read_bytes()
        ),
        "selection_contract_sha256": digest(
            (root / "spec/phase2-selection-v1.json").read_bytes()
        ),
        **{
            f"superseded_plan_{index}_sha256": digest(
                (root / plan / "SHA256SUMS").read_bytes()
            )
            for index, plan in enumerate(_SUPERSEDED_PLANS, 1)
        },
    }


def _packet_bindings(root: Path) -> dict[str, str]:
    return {
        "mark_wave2_plan_sha256": digest((root / _PLAN / "SHA256SUMS").read_bytes()),
        "prompt_v4_sha256": digest((root / "spec/prompt-template-v4.txt").read_bytes()),
        **_plan_bindings(root),
    }


def _verify_checksums(directory: Path) -> None:
    for line in (directory / "SHA256SUMS").read_text().splitlines():
        checksum, separator, relative = line.partition("  ")
        if not separator or sha256((directory / relative).read_bytes()).hexdigest() != checksum:
            raise MarkWave2Error(f"checksum failed under {directory.name}")


def _checksums(files: dict[str, bytes]) -> bytes:
    return "".join(
        f"{sha256(data).hexdigest()}  {name}\n" for name, data in sorted(files.items())
    ).encode()


def _plan_readme() -> str:
    return """# WP2-4 mark Wave-2 candidate plan v4

This plan is frozen before candidate execution. Wave-0 and repaired Wave-1 contribute 76 accepted
decisions, leaving 424. Wave-2 targets 266 whole-stream decisions (62.7% of the remainder) and
generates 462 candidates under the standard and fragile multipliers. Selection remains deferred
until stream review; teacher agreement is not a selection feature. It supersedes the unsupported
v1 shape, v2 timing-only duplicates, and v3's inert-context deduplication. Every candidate stream
and exact teacher input must be distinct from prior approved mark evidence and from the rest of
this packet; response-twin halves are submitted in separate fresh chats.
"""


def _readme(round_count: int) -> str:
    return f"""# WP2-4 mark Wave-2 — Chat teacher packet

The final 462-decision candidate pool passed its mechanical and coherence battery. It covers all
22 sealed mark assets, ordinary and dense positive spans, ambiguous/quoted/code/partial negative
controls, direct stop/replacement, and every remaining owner-approved response pair.

Upload each of the {round_count} files under `rounds/` separately in a fresh Temporary Chat using
GPT-5.6 Sol with high reasoning. Send:

`Read the attached round fully and return the requested downloadable JSONL file.`

Keep every requested output filename unchanged. Do not upload local oracle or audit files. No API
call or Chat upload has occurred.
"""
