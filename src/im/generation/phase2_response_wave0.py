"""Small owner-reviewed TRAIN preflight for WP2-5 response timing."""

from __future__ import annotations

from dataclasses import dataclass, replace
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

from im.assets import AssetRegistry, CorpusFamily, Split
from im.assets.model import canonical_artifact_bytes
from im.generation.g7_response_assets import SimpleResponseProfile
from im.generation.g7_response_twins import (
    build_g7_response_floor_twin_program,
    validate_response_floor_twin_alignment,
)
from im.generation.packaging import PackageManifest
from im.generation.phase2_lookup_wave0 import (
    _raw_stream,
    _runtime_files,
    load_lookup_wave0_inputs,
)
from im.generation.phase2_lookup_wave2 import _response_assets
from im.generation.phase2_response_tranche import _family_inputs
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
from im.generation.phase2_sentinel_v2 import (
    build_executable_sentinel_programs,
    load_executable_sentinel_inputs,
)
from im.generation.publication import publish_directory_transaction
from im.generation.response_contracts import ResponseKind
from im.generation.scenarios import (
    GeneratedScenario,
    ScenarioProgram,
    execute_scenario,
    validate_generated_scenario,
)
from im.probes.harness.identity import digest
from im.probes.harness.models import HarnessProtocol
from im.schema.actions import IdleAction, IdleReason, RespondAction

_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RESPONSE_WAVE0_OUTPUT = _ROOT / "review" / "phase2" / "response-wave-0"
_PROMPT_TEMPLATE = "prompt-template-v4.txt"
_NEUTRAL_ORDINALS = (1, *range(6, 35))
_WAVE0_ORDINALS = (1, 14, 15, 25)


class ResponseWave0Error(ValueError):
    """The response preflight no longer proves the frozen floor branch."""


@dataclass(frozen=True, slots=True)
class ResponseWave0Spec:
    logical_stream_id: str
    source_unit_id: str
    candidate_ordinal: int
    member: str
    program: ScenarioProgram


@dataclass(frozen=True, slots=True)
class ExecutedResponseWave0:
    spec: ResponseWave0Spec
    generated: GeneratedScenario
    selected_segment: None = None


async def build_response_wave0_packet(
    *, repository_root: Path = _ROOT
) -> dict[str, bytes]:
    """Execute and package four canonical active/yielded response twins."""
    root = repository_root.resolve()
    registry = load_lookup_wave0_inputs()
    specs = _program_specs(registry, root)
    with TemporaryDirectory(prefix="phase2-response-wave0-") as temporary:
        executed = []
        for spec in specs:
            generated = await execute_scenario(
                spec.program,
                session_id=f"response-wave0-{spec.logical_stream_id}",
                directory=Path(temporary) / spec.logical_stream_id,
                repository_root=root,
            )
            validate_generated_scenario(generated)
            executed.append(ExecutedResponseWave0(spec, generated))
        values = tuple(executed)
        _validate(values, root)
        return _packet(values, root)


async def materialize_response_wave0_packet(
    output: Path = DEFAULT_RESPONSE_WAVE0_OUTPUT,
    *,
    repository_root: Path = _ROOT,
) -> dict[str, bytes]:
    files = await build_response_wave0_packet(repository_root=repository_root)
    publish_directory_transaction(output, files)
    return files


def _program_specs(
    registry: AssetRegistry, root: Path
) -> tuple[ResponseWave0Spec, ...]:
    assets = _response_assets(root)
    if set(_NEUTRAL_ORDINALS) - set(assets):
        raise ResponseWave0Error("the approved neutral response inventory is incomplete")
    profiles = tuple(
        SimpleResponseProfile(
            tuple(assets[ordinal] for ordinal in _NEUTRAL_ORDINALS[start : start + 10])
        )
        for start in range(0, 30, 10)
    )
    inputs = _family_inputs(registry, CorpusFamily.NEUTRAL_TYPING)
    contract, sentinel_registry, response = load_executable_sentinel_inputs()
    sentinel_programs = {
        item.logical_stream_id: item.program
        for item in build_executable_sentinel_programs(
            contract, sentinel_registry, response
        )
    }
    specs = [
        ResponseWave0Spec(
            "response-001-yielded",
            "response-wave0-001",
            1,
            "yielded",
            replace(
                sentinel_programs["response-open"],
                prompt_template=_PROMPT_TEMPLATE,
            ),
        ),
        ResponseWave0Spec(
            "response-001-active",
            "response-wave0-001",
            1,
            "active",
            replace(
                sentinel_programs["response-active"],
                prompt_template=_PROMPT_TEMPLATE,
            ),
        ),
    ]
    for ordinal in _WAVE0_ORDINALS[1:]:
        neutral_index = _NEUTRAL_ORDINALS.index(ordinal)
        profile_index, item_index = divmod(neutral_index, 10)
        twin = build_g7_response_floor_twin_program(
            registry,
            split=Split.TRAIN,
            family=CorpusFamily.NEUTRAL_TYPING,
            inputs=inputs,
            profile=profiles[profile_index],
            master_seed=f"phase2-response-wave0:{ordinal:03d}",
            item_index=item_index,
        )
        for member, program in zip(("yielded", "active"), twin.programs, strict=True):
            specs.append(
                ResponseWave0Spec(
                    f"response-{ordinal:03d}-{member}",
                    f"response-wave0-{ordinal:03d}",
                    ordinal,
                    member,
                    replace(program, prompt_template=_PROMPT_TEMPLATE),
                )
            )
    return tuple(specs)


def _validate(executed: tuple[ExecutedResponseWave0, ...], root: Path) -> None:
    if len(executed) != 8 or {item.spec.candidate_ordinal for item in executed} != set(
        _WAVE0_ORDINALS
    ):
        raise ResponseWave0Error("Wave-0 inventory drifted")
    approved = _response_assets(root)
    stream_hashes = {item.generated.stream.sha256 for item in executed}
    model_inputs = {
        item.generated.stream.decisions[0].prefix_bytes for item in executed
    }
    if len(stream_hashes) != 8 or len(model_inputs) != 8:
        raise ResponseWave0Error("Wave-0 contains duplicate streams or model inputs")
    for ordinal in _WAVE0_ORDINALS:
        pair = tuple(
            item for item in executed if item.spec.candidate_ordinal == ordinal
        )
        if len(pair) != 2:
            raise ResponseWave0Error("response twin is incomplete")
        yielded = next(item for item in pair if item.spec.member == "yielded")
        active = next(item for item in pair if item.spec.member == "active")
        validate_response_floor_twin_alignment(
            yielded.generated.program, active.generated.program
        )
        yielded_action = yielded.generated.program.actions[0]
        active_action = active.generated.program.actions[0]
        if (
            yielded.generated.program.bundle.split is not Split.TRAIN
            or yielded.generated.program.prompt_template != _PROMPT_TEMPLATE
            or active.generated.program.prompt_template != _PROMPT_TEMPLATE
            or approved[ordinal].draft.answer_contract.response_kind
            is not ResponseKind.ORDINARY_GROUNDED
            or not isinstance(yielded_action, RespondAction)
            or yielded_action.text != approved[ordinal].candidate_response
            or not isinstance(active_action, IdleAction)
            or active_action.reason is not IdleReason.AWAITING_OPENING
        ):
            raise ResponseWave0Error("response floor or approved payload drifted")


def _packet(
    executed: tuple[ExecutedResponseWave0, ...], root: Path
) -> dict[str, bytes]:
    manifest = PackageManifest.build(item.generated for item in executed).canonical_bytes
    allocation = canonical_artifact_bytes(
        {
            "format_version": 1,
            "kind": "phase2-response-allocation",
            "neutral_typing_revision_pause": list(_NEUTRAL_ORDINALS),
            "response_payload_substitution_count": 0,
            "selection_sha256": digest(
                (
                    root
                    / "review/phase2/response-tranche-selection/selection.json"
                ).read_bytes()
            ),
            "wave0_ordinals": list(_WAVE0_ORDINALS),
        }
    )
    files = {
        "README.md": _readme().encode(),
        "REVIEW.md": _review_guide().encode(),
        "manifest.json": manifest,
        "phase2-review-evidence.json": _review_projection(executed),
        "raw-stream-evidence.json": canonical_artifact_bytes(
            {
                "format_version": 1,
                "streams": [_raw_stream(item) for item in executed],
            }
        ),
        "response-allocation.json": allocation,
        "review-packet.json": canonical_artifact_bytes(
            {
                "api_call_performed": False,
                "decision_count": 8,
                "format_version": 1,
                "kind": "phase2-response-wave0-offline-packet",
                "manifest_sha256": digest(manifest),
                "owner_action_required": (
                    "Review four ordinary answers in active and paused editor states."
                ),
                "response_payload_substitution_count": 0,
                "stream_review_count": 8,
                "wave_id": "response-wave-0",
            }
        ),
        "source-index.json": canonical_artifact_bytes(_source_index(executed)),
        **_runtime_files(executed),  # type: ignore[arg-type]
    }
    files["SHA256SUMS"] = _checksums(files)
    return files


def _review_projection(executed: tuple[ExecutedResponseWave0, ...]) -> bytes:
    decisions = []
    sidecars = {}
    for item in executed:
        generated = item.generated
        action = generated.program.actions[0]
        sidecars[generated.stream.sha256] = generated.sidecar.sha256
        decisions.append(
            DecisionEvidence(
                stream_sha256=generated.stream.sha256,
                decision_policy_seq=generated.sidecar.decisions[0].observed_policy_seq,
                wave_id="response-wave-0",
                cell=TrustCellKey(
                    HarnessProtocol.GENERATION,
                    CorpusFamily.NEUTRAL_TYPING,
                    (
                        FloorClass.OPEN
                        if item.spec.member == "yielded"
                        else FloorClass.OWNED
                    ),
                ),
                template_id=generated.program.template.asset_id,
                source_unit_id=item.spec.source_unit_id,
                oracle_action=action,
                teacher_action=None,
                causal_state_class=f"ordinary_response_{item.spec.member}",
                boundary_class=BoundaryClass.ACTIVE_FLOOR_RESPONSE,
                risk_flags=("active_floor_response_boundary",),
                rollover=False,
            )
        )
    routes = route_wave(
        tuple(decisions),
        {},
        sampling_seed="phase2-response-wave0-owner-review-v1",
    )
    if not all(route.review_required for route in routes):
        raise ResponseWave0Error("all response-floor decisions must route to owner review")
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
        teacher_evidence_identity=digest(b"response-wave0:no-teacher-evidence"),
        blind_seed="phase2-response-wave0-blind-v1",
    )


def _source_index(
    executed: tuple[ExecutedResponseWave0, ...],
) -> dict[str, object]:
    return {
        "batch": 1,
        "format_version": 1,
        "source_identity_rule": "one complete TRAIN runtime parent per response-floor member",
        "sources": [
            {
                "checkpoint": None,
                "family": CorpusFamily.NEUTRAL_TYPING.value,
                "master_seed": item.generated.program.master_seed,
                "parent_stream_sha256s": [item.generated.stream.sha256],
                "raw_source_sha256s": [item.generated.stream.capture_sha256],
                "role": item.spec.member,
                "shape_id": "ordinary-grounded-response-floor",
                "sidecar_sha256s": [item.generated.sidecar.sha256],
                "source_decision_counts": [1],
                "source_kind": "runtime_parent",
                "source_unit_id": item.spec.source_unit_id,
            }
            for item in executed
        ],
    }


def _readme() -> str:
    return """# WP2-5 response Wave-0 — owner preflight

Four TRAIN-bound questions are shown twice with one real-world difference: in one version the user
is still typing, and in the other they have paused. The product should wait while typing and answer
after the pause. Every answer is an already approved TRAIN response; no new wording was generated.
"""


def _review_guide() -> str:
    return """# What to review

Judge each interaction as the person using the product:

- If the user is still typing, the assistant should wait.
- If the user has paused after asking the question, the assistant should answer.
- The answer must directly match the visible question and supporting text.
- The paired cases must use the same approved answer; only the typing state changes.

Approve or reject the eight interactions. No teacher or provider call was performed.
"""


def _checksums(files: dict[str, bytes]) -> bytes:
    return "".join(
        f"{sha256(data).hexdigest()}  {name}\n" for name, data in sorted(files.items())
    ).encode()
