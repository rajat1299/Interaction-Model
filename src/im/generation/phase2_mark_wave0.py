"""Small owner-reviewed TRAIN preflight for WP2-4 mark behavior."""

from __future__ import annotations

from dataclasses import dataclass, replace
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

from im.assets import AssetRegistry, CorpusFamily, Split
from im.assets.model import canonical_artifact_bytes
from im.canonical_json import parse_tim_json
from im.generation.packaging import PackageManifest
from im.generation.phase2_lookup_wave0 import (
    _raw_stream,
    _runtime_files,
    load_lookup_wave0_inputs,
)
from im.generation.phase2_review import (
    BoundaryClass,
    DecisionEvidence,
    FloorClass,
    TrustCellKey,
    route_wave,
)
from im.generation.phase2_review_projection import (
    CandidateLicense,
    DecisionProjectionInput,
    project_phase2_review_evidence,
)
from im.generation.publication import publish_directory_transaction
from im.generation.scenario_catalog import build_family_program
from im.generation.scenarios import (
    GeneratedScenario,
    ScenarioProgram,
    execute_scenario,
    validate_generated_scenario,
)
from im.probes.harness.models import HarnessProtocol
from im.schema.actions import IdleAction, IdleReason, MarkAction

_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MARK_WAVE0_OUTPUT = _ROOT / "review" / "phase2" / "mark-wave-0"
_POSITIVE_TEMPLATE = "a_a1c85d29665460b9b04ffcd2"
_NEGATIVE_TEMPLATE = "a_cf3fb85cbef8786d98724b33"
_PROMPT_TEMPLATE = "prompt-template-v3.txt"
_TRUST_MATRIX_VERSION = "phase2-trust-v1"


class MarkWave0Error(ValueError):
    """The mark preflight does not preserve the approved control semantics."""


@dataclass(frozen=True, slots=True)
class MarkWave0Spec:
    logical_stream_id: str
    source_unit_id: str
    family: CorpusFamily
    template_id: str
    asset_id: str
    subtype: str

    @property
    def shape_id(self) -> str:
        return f"mark-wave0-{self.subtype}"


@dataclass(frozen=True, slots=True)
class MarkWave0Program:
    spec: MarkWave0Spec
    program: ScenarioProgram


@dataclass(frozen=True, slots=True)
class ExecutedMarkWave0:
    spec: MarkWave0Spec
    generated: GeneratedScenario
    selected_segment: None = None


_SPECS = (
    MarkWave0Spec(
        "positive-harbor",
        "mark-wave0-positive-harbor",
        CorpusFamily.MARK_POSITIVE,
        _POSITIVE_TEMPLATE,
        "a_fd6da4920d7808b5fa348adb",
        "direct_positive",
    ),
    MarkWave0Spec(
        "positive-date",
        "mark-wave0-positive-date",
        CorpusFamily.MARK_POSITIVE,
        _POSITIVE_TEMPLATE,
        "a_4d9e7e5fdf179993fd3d8367",
        "date_target_verbatim",
    ),
    MarkWave0Spec(
        "negative-stop",
        "mark-wave0-negative-stop",
        CorpusFamily.MARK_NEGATIVE,
        _NEGATIVE_TEMPLATE,
        "a_f23b664ce3f705453eb63437",
        "direct_stop",
    ),
    MarkWave0Spec(
        "negative-replacement",
        "mark-wave0-negative-replacement",
        CorpusFamily.MARK_NEGATIVE,
        _NEGATIVE_TEMPLATE,
        "a_047297e7827179204b66c329",
        "direct_replacement",
    ),
    MarkWave0Spec(
        "negative-ambiguous",
        "mark-wave0-negative-ambiguous",
        CorpusFamily.MARK_NEGATIVE,
        _NEGATIVE_TEMPLATE,
        "a_76f996251354c25a3c5d4a1d",
        "ambiguous",
    ),
    MarkWave0Spec(
        "negative-quoted",
        "mark-wave0-negative-quoted",
        CorpusFamily.MARK_NEGATIVE,
        _NEGATIVE_TEMPLATE,
        "a_1e24348f52635e4451ccf7ec",
        "quoted",
    ),
    MarkWave0Spec(
        "negative-code",
        "mark-wave0-negative-code",
        CorpusFamily.MARK_NEGATIVE,
        _NEGATIVE_TEMPLATE,
        "a_f474eca1aed953454b2fcdc7",
        "code",
    ),
    MarkWave0Spec(
        "negative-partial",
        "mark-wave0-negative-partial",
        CorpusFamily.MARK_NEGATIVE,
        _NEGATIVE_TEMPLATE,
        "a_87a385b4ca57e3d7c0cf237b",
        "partial",
    ),
)


def build_mark_wave0_programs(
    registry: AssetRegistry,
) -> tuple[MarkWave0Program, ...]:
    if not isinstance(registry, AssetRegistry):
        raise TypeError("registry must be an AssetRegistry")
    programs = []
    for spec in _SPECS:
        program = build_family_program(
            spec.family,
            registry,
            split=Split.TRAIN,
            template_id=spec.template_id,
            asset_ids=(spec.asset_id,),
            master_seed=f"phase2-mark-wave0:{spec.subtype}",
        )
        programs.append(
            MarkWave0Program(
                spec,
                replace(program, prompt_template=_PROMPT_TEMPLATE),
            )
        )
    return tuple(programs)


async def execute_mark_wave0(
    programs: tuple[MarkWave0Program, ...],
    *,
    directory: Path,
    repository_root: Path = _ROOT,
) -> tuple[ExecutedMarkWave0, ...]:
    if tuple(item.spec for item in programs) != _SPECS:
        raise MarkWave0Error("mark Wave-0 program inventory is not closed")
    executed = []
    for item in programs:
        generated = await execute_scenario(
            item.program,
            session_id=f"mark-wave0-{item.spec.logical_stream_id}",
            directory=directory / item.spec.logical_stream_id,
            repository_root=repository_root,
        )
        validate_generated_scenario(generated)
        _validate(item.spec, generated)
        executed.append(ExecutedMarkWave0(item.spec, generated))
    return tuple(executed)


def build_mark_wave0_packet(
    executed: tuple[ExecutedMarkWave0, ...],
) -> dict[str, bytes]:
    if tuple(item.spec for item in executed) != _SPECS:
        raise MarkWave0Error("packet execution inventory differs from the fixed preflight")
    review_bytes = _review_projection(executed)
    manifest = PackageManifest.build(
        item.generated for item in executed
    ).canonical_bytes
    expansion = _template_expansion(executed)
    files = {
        "README.md": _readme().encode(),
        "REVIEW.md": _review_guide().encode(),
        "manifest.json": manifest,
        "phase2-review-evidence.json": review_bytes,
        "raw-stream-evidence.json": canonical_artifact_bytes(
            {
                "format_version": 1,
                "streams": [_raw_stream(item) for item in executed],
            }
        ),
        "review-packet.json": canonical_artifact_bytes(
            {
                "api_call_performed": False,
                "decision_count": 14,
                "format_version": 1,
                "kind": "phase2-mark-wave0-offline-packet",
                "manifest_sha256": _digest(manifest),
                "owner_action_required": (
                    "Review the eight natural mark interactions and approve or reject the "
                    "rendered stop/replacement/partial semantics."
                ),
                "stream_review_count": 8,
                "template_expansion_sha256": _digest(expansion),
                "wave_id": "mark-wave-0",
            }
        ),
        "source-index.json": canonical_artifact_bytes(_source_index(executed)),
        "template-expansion.json": expansion,
        **_runtime_files(executed),  # type: ignore[arg-type]
    }
    files["SHA256SUMS"] = _checksums(files)
    return files


async def materialize_mark_wave0_packet(
    output: Path = DEFAULT_MARK_WAVE0_OUTPUT,
    *,
    repository_root: Path = _ROOT,
) -> dict[str, bytes]:
    programs = build_mark_wave0_programs(load_lookup_wave0_inputs())
    with TemporaryDirectory(prefix="phase2-mark-wave0-") as temporary:
        executed = await execute_mark_wave0(
            programs,
            directory=Path(temporary),
            repository_root=repository_root,
        )
        files = build_mark_wave0_packet(executed)
    publish_directory_transaction(output, files)
    return files


def _validate(spec: MarkWave0Spec, generated: GeneratedScenario) -> None:
    program = generated.program
    if program.bundle.split is not Split.TRAIN or program.prompt_template != _PROMPT_TEMPLATE:
        raise MarkWave0Error(f"{spec.logical_stream_id} escaped TRAIN/prompt-v3")
    actions = program.actions
    frames = tuple(parse_tim_json(frame.raw_bytes)["text"] for frame in program.frames)
    if spec.family is CorpusFamily.MARK_POSITIVE:
        marks = tuple(action for action in actions if isinstance(action, MarkAction))
        if len(marks) != 1 or tuple(action.type for action in actions) != (
            "idle",
            "mark",
            "idle",
        ):
            raise MarkWave0Error(f"{spec.logical_stream_id} positive vector drifted")
        if spec.subtype == "date_target_verbatim" and marks[0].target.text != "17 October 2031":
            raise MarkWave0Error("date target was not rendered verbatim")
        return
    if any(isinstance(action, MarkAction) for action in actions):
        raise MarkWave0Error(f"{spec.logical_stream_id} negative control emitted mark")
    expected = {
        "direct_stop": (IdleReason.NO_TRIGGER, 2),
        "direct_replacement": (IdleReason.NO_TRIGGER, 2),
        "ambiguous": (IdleReason.AMBIGUOUS, 1),
        "quoted": (IdleReason.INSTRUCTION_NOT_DIRECT, 1),
        "code": (IdleReason.INSTRUCTION_NOT_DIRECT, 1),
        "partial": (IdleReason.TYPING_ACTIVE, 1),
    }[spec.subtype]
    if len(actions) != expected[1] or not all(
        isinstance(action, IdleAction) and action.reason is expected[0]
        for action in actions[-1:]
    ):
        raise MarkWave0Error(f"{spec.logical_stream_id} idle semantics drifted")
    if spec.subtype == "direct_stop" and frames != (
        "Mark every occurrence of the copper ibis.",
        "Stop marking the copper ibis.",
    ):
        raise MarkWave0Error("direct stop lost its matching active control")
    if spec.subtype == "direct_replacement" and frames != (
        "Mark every occurrence of animal labels.",
        "Switch from animal labels to color labels.",
    ):
        raise MarkWave0Error("direct replacement lost its matching active control")


def _review_projection(executed: tuple[ExecutedMarkWave0, ...]) -> bytes:
    decisions = []
    sidecars = {}
    for item in executed:
        generated = item.generated
        sidecars[generated.stream.sha256] = generated.sidecar.sha256
        for index, action in enumerate(generated.program.actions):
            sidecar = generated.sidecar.decisions[index]
            decisions.append(
                DecisionEvidence(
                    stream_sha256=generated.stream.sha256,
                    decision_policy_seq=sidecar.observed_policy_seq,
                    wave_id="mark-wave-0",
                    cell=TrustCellKey(
                        HarnessProtocol.GENERATION,
                        item.spec.family,
                        FloorClass.CLOSED,
                    ),
                    template_id=item.spec.template_id,
                    source_unit_id=item.spec.source_unit_id,
                    oracle_action=action,
                    teacher_action=None,
                    causal_state_class=item.spec.subtype,
                    boundary_class=(
                        BoundaryClass.PARTIAL_INSTRUCTION
                        if item.spec.subtype == "partial"
                        else BoundaryClass.ORDINARY
                    ),
                    risk_flags=("first_instances_of_new_template",),
                    idle_boundary=(
                        "partial_instruction"
                        if item.spec.subtype == "partial"
                        else None
                    ),
                    rollover=False,
                )
            )
    routes = route_wave(
        tuple(decisions),
        {},
        sampling_seed="phase2-mark-wave0-owner-review-v1",
    )
    if len(decisions) != 14 or not all(route.review_required for route in routes):
        raise MarkWave0Error("all 14 preflight decisions must route to owner review")
    return project_phase2_review_evidence(
        tuple(
            DecisionProjectionInput(
                decision=decision,
                route=route,
                oracle_license=CandidateLicense("licensed", ()),
                teacher_license=None,
                oracle_provenance={
                    "sidecar_sha256": sidecars[decision.stream_sha256],
                    "stream_sha256": decision.stream_sha256,
                },
                teacher_provenance=None,
                priority_rank=index,
            )
            for index, (decision, route) in enumerate(zip(decisions, routes, strict=True))
        ),
        packet_decision_identities=tuple(
            (decision.stream_sha256, decision.decision_policy_seq)
            for decision in decisions
        ),
        teacher_evidence_identity=_digest(b"mark-wave0:no-teacher-evidence"),
        blind_seed="phase2-mark-wave0-blind-v1",
    )


def _template_expansion(
    executed: tuple[ExecutedMarkWave0, ...],
) -> bytes:
    replacement = next(
        item for item in executed if item.spec.subtype == "direct_replacement"
    )
    program = replacement.generated.program
    return canonical_artifact_bytes(
        {
            "actions": [action.model_dump(mode="json") for action in program.actions],
            "format_version": 1,
            "preserves_direct_replacement": True,
            "rendered_frames": [
                parse_tim_json(frame.raw_bytes)["text"] for frame in program.frames
            ],
            "seed_asset_id": replacement.spec.asset_id,
            "template_asset_id": replacement.spec.template_id,
        }
    )


def _source_index(
    executed: tuple[ExecutedMarkWave0, ...],
) -> dict[str, object]:
    return {
        "batch": 1,
        "format_version": 1,
        "source_identity_rule": "one complete TRAIN runtime parent per mark preflight unit",
        "sources": [
            {
                "checkpoint": None,
                "family": item.spec.family.value,
                "master_seed": item.generated.program.master_seed,
                "parent_stream_sha256s": [item.generated.stream.sha256],
                "raw_source_sha256s": [item.generated.stream.capture_sha256],
                "role": item.spec.subtype,
                "shape_id": item.spec.shape_id,
                "sidecar_sha256s": [item.generated.sidecar.sha256],
                "source_decision_counts": [len(item.generated.program.actions)],
                "source_kind": "runtime_parent",
                "source_unit_id": item.spec.source_unit_id,
            }
            for item in executed
        ],
    }


def _readme() -> str:
    return """# WP2-4 mark Wave-0 — owner preflight

Eight TRAIN-bound interactions exercise direct marking, exact target spans, direct stop,
direct replacement, genuine ambiguity, quoted/code text, and a partial instruction. All 14
decisions passed the production runtime and mechanical checks. No teacher or provider call was
performed.
"""


def _review_guide() -> str:
    return """# What to review

Judge each interaction as the person using the product:

- A direct mark instruction only affects a matching occurrence that appears later.
- The date `17 October 2031` must remain exact in both the instruction and marked target.
- A direct stop or replacement follows a matching visible active control and should itself do
  nothing: no mark and no ambiguity.
- `Underli` is unfinished, so the product should wait for typing.
- A genuinely unresolved target should wait as ambiguous.
- Quoted or code-form mark wording is not a direct instruction and should be ignored.

Approve or reject the eight interactions. `template-expansion.json` records the required rendered
direct-replacement expansion of template `a_cf3fb85cbef8786d98724b33`.
"""


def _checksums(files: dict[str, bytes]) -> bytes:
    return "".join(
        f"{sha256(data).hexdigest()}  {name}\n" for name, data in sorted(files.items())
    ).encode()


def _digest(data: bytes) -> str:
    return f"sha256:{sha256(data).hexdigest()}"
