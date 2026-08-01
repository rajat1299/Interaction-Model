"""Deterministic WP2-5 response Wave-1 teacher canary."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, replace
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

from im.assets import AssetRegistry, CorpusFamily, Split
from im.assets.model import canonical_artifact_bytes
from im.config import estimate_tokens
from im.generation.g7_response_assets import SimpleResponseProfile
from im.generation.g7_response_twins import (
    build_g7_response_floor_twin_program,
    validate_response_floor_twin_alignment,
)
from im.generation.phase2_lookup_wave0 import _raw_stream, load_lookup_wave0_inputs
from im.generation.phase2_lookup_wave1 import _message
from im.generation.phase2_lookup_wave2 import _response_assets
from im.generation.phase2_response_tranche import _family_inputs
from im.generation.phase2_review import (
    BoundaryClass,
    DecisionEvidence,
    FloorClass,
    TrustCellKey,
    route_wave,
)
from im.generation.phase2_timer_wave2_chat import _round_markdown, _rounds
from im.generation.publication import publish_directory_transaction
from im.generation.response_contracts import ResponseKind
from im.generation.scenarios import (
    GeneratedScenario,
    ScenarioProgram,
    execute_scenario,
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
from im.schema.actions import IdleAction, IdleReason, RespondAction

_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RESPONSE_WAVE1_OUTPUT = _ROOT / "review" / "phase2" / "response-wave-1"
DEFAULT_RESPONSE_WAVE1_RESULTS = _ROOT / "review" / "phase2" / "response-wave-1-results"
_PROMPT_TEMPLATE = "prompt-template-v4.txt"
_NEUTRAL_ORDINALS = (1, *range(6, 35))
_WAVE1_ORDINALS = (6, 9, 18, 26, 33)
_STAGE = "t2rw1"
_MAX_OUTPUT_TOKENS = 8_192
_MAX_ROUND_TOKENS = 120_000


class ResponseWave1Error(ValueError):
    """The response canary is incomplete, repeated, or unsafe to upload."""


@dataclass(frozen=True, slots=True)
class ResponseWave1Spec:
    logical_stream_id: str
    source_unit_id: str
    candidate_ordinal: int
    member: str
    program: ScenarioProgram


@dataclass(frozen=True, slots=True)
class ExecutedResponseWave1:
    spec: ResponseWave1Spec
    generated: GeneratedScenario
    selected_segment: None = None


@dataclass(frozen=True, slots=True)
class ResponseWave1Packet:
    files: dict[str, bytes]
    decision_count: int
    round_count: int
    stream_count: int


async def build_response_wave1_packet(
    *, repository_root: Path = _ROOT
) -> ResponseWave1Packet:
    """Execute the ten-decision TRAIN canary and render one blinded Chat round."""
    root = repository_root.resolve()
    specs = _program_specs(load_lookup_wave0_inputs(), root)
    with TemporaryDirectory(prefix="phase2-response-wave1-") as temporary:
        executed = []
        for spec in specs:
            generated = await execute_scenario(
                spec.program,
                session_id=f"response-wave1-{spec.logical_stream_id}",
                directory=Path(temporary) / spec.logical_stream_id,
                repository_root=root,
            )
            validate_generated_scenario(generated)
            executed.append(ExecutedResponseWave1(spec, generated))
        values = tuple(executed)
        battery = _validate(values, root)
        return _packet(values, battery, root)


async def materialize_response_wave1_packet(
    output: Path = DEFAULT_RESPONSE_WAVE1_OUTPUT,
    *,
    repository_root: Path = _ROOT,
) -> ResponseWave1Packet:
    packet = await build_response_wave1_packet(repository_root=repository_root)
    publish_directory_transaction(output, packet.files)
    output.parent.joinpath(DEFAULT_RESPONSE_WAVE1_RESULTS.name).mkdir(exist_ok=True)
    return packet


def _program_specs(
    registry: AssetRegistry, root: Path
) -> tuple[ResponseWave1Spec, ...]:
    assets = _response_assets(root)
    profiles = tuple(
        SimpleResponseProfile(
            tuple(assets[ordinal] for ordinal in _NEUTRAL_ORDINALS[start : start + 10])
        )
        for start in range(0, 30, 10)
    )
    inputs = _family_inputs(registry, CorpusFamily.NEUTRAL_TYPING)
    specs = []
    for ordinal in _WAVE1_ORDINALS:
        neutral_index = _NEUTRAL_ORDINALS.index(ordinal)
        profile_index, item_index = divmod(neutral_index, 10)
        twin = build_g7_response_floor_twin_program(
            registry,
            split=Split.TRAIN,
            family=CorpusFamily.NEUTRAL_TYPING,
            inputs=inputs,
            profile=profiles[profile_index],
            master_seed=f"phase2-response-wave1:{ordinal:03d}",
            item_index=item_index,
        )
        for member, program in zip(("yielded", "active"), twin.programs, strict=True):
            specs.append(
                ResponseWave1Spec(
                    f"response-{ordinal:03d}-{member}",
                    f"response-wave1-{ordinal:03d}",
                    ordinal,
                    member,
                    replace(program, prompt_template=_PROMPT_TEMPLATE),
                )
            )
    return tuple(specs)


def _validate(
    executed: tuple[ExecutedResponseWave1, ...], root: Path
) -> dict[str, object]:
    if len(executed) != 10 or {item.spec.candidate_ordinal for item in executed} != set(
        _WAVE1_ORDINALS
    ):
        raise ResponseWave1Error("Wave-1 inventory drifted")
    approved = _response_assets(root)
    actions = Counter(
        action.type for item in executed for action in item.generated.program.actions
    )
    if actions != Counter(idle=5, respond=5):
        raise ResponseWave1Error("Wave-1 action vector drifted")
    wave0 = _object(root / "review/phase2/response-wave-0/raw-stream-evidence.json")
    prior_hashes = {row["stream_sha256"] for row in wave0["streams"]}
    hashes = {item.generated.stream.sha256 for item in executed}
    inputs = {item.generated.stream.decisions[0].prefix_bytes for item in executed}
    if len(hashes) != 10 or len(inputs) != 10 or hashes & prior_hashes:
        raise ResponseWave1Error("Wave-1 repeats a stream, model input, or Wave-0 case")
    for ordinal in _WAVE1_ORDINALS:
        pair = tuple(
            item for item in executed if item.spec.candidate_ordinal == ordinal
        )
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
            raise ResponseWave1Error("response floor or approved payload drifted")
    return {
        "action_counts": dict(sorted(actions.items())),
        "checks": {
            "all_questions_answered_by_exact_approved_payload": True,
            "all_streams_disjoint_from_wave0": True,
            "all_streams_train_prompt_v4_bound": True,
            "natural_standalone_response_rule_applied": True,
            "response_floor_twins_aligned": True,
            "response_payload_substitution_count_zero": True,
        },
        "decision_count": 10,
        "format_version": 1,
        "kind": "phase2-response-wave1-pre-upload-battery",
        "source_unit_count": 5,
        "stream_count": 10,
    }


def _packet(
    executed: tuple[ExecutedResponseWave1, ...],
    battery: dict[str, object],
    root: Path,
) -> ResponseWave1Packet:
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
        action = item.generated.program.actions[0]
        boundary = item.generated.decision_boundaries[0]
        body = builder.build(boundary.policy_bytes)
        body_bytes = canonical_artifact_bytes(body)
        custom_id = f"{_STAGE}.{item.spec.logical_stream_id}.d000.a1"
        system_prompts.add(_message(body, 0))
        sidecar = item.generated.sidecar.decisions[0]
        decision = next(
            row
            for row in evidence
            if row.stream_sha256 == item.generated.stream.sha256
        )
        route = route_by_identity[decision.identity]
        targets.append(
            {
                "candidate_selected_program_action_indices": [0],
                "custom_id": custom_id,
                "decision_policy_seq": sidecar.observed_policy_seq,
                "family": CorpusFamily.NEUTRAL_TYPING.value,
                "logical_stream_id": item.spec.logical_stream_id,
                "oracle_action": action.model_dump(mode="json"),
                "policy_prefix_sha256": digest(boundary.policy_bytes),
                "program_action_index": 0,
                "prompt_hash": artifacts.prompt_hash,
                "request_body_sha256": digest(body_bytes),
                "response_candidate_ordinal": item.spec.candidate_ordinal,
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
                "candidate_ordinal": 0,
                "custom_id": custom_id,
                "input_sha256": digest(_message(body, 1).encode()),
                "logical_stream_id": item.spec.logical_stream_id,
                "policy_stream": _message(body, 1),
            }
        )
    if len(system_prompts) != 1:
        raise ResponseWave1Error("teacher requests do not share one exact policy")
    system_prompt = system_prompts.pop()
    rounds = _rounds(cases, system_prompt)
    files: dict[str, bytes] = {
        "README.md": _readme(len(rounds)).encode(),
        "pre-upload-battery.json": canonical_artifact_bytes(battery),
        "raw-streams.json": canonical_artifact_bytes(
            {
                "format_version": 1,
                "kind": "phase2-response-wave1-parent-candidates",
                "streams": [_raw_stream(item) for item in executed],
            }
        ),
    }
    round_manifest = []
    for index, round_cases in enumerate(rounds, 1):
        name = f"round-{index:03d}"
        path = f"rounds/{name}.md"
        data = _round_markdown(
            name, round_cases, system_prompt, f"{name}.output.jsonl"
        )
        if estimate_tokens(data) > _MAX_ROUND_TOKENS:
            raise ResponseWave1Error(f"{name} exceeds the Chat token budget")
        files[path] = data
        round_manifest.append(
            {
                "case_count": len(round_cases),
                "case_ids": [case["custom_id"] for case in round_cases],
                "input_path": path,
                "input_sha256": digest(data),
                "output_filename": f"{name}.output.jsonl",
            }
        )
    binding = digest(
        canonical_artifact_bytes(
            {
                "kind": "phase2-response-wave1-binding-v1",
                "prompt_hash": artifacts.prompt_hash,
                "response_ordinals": list(_WAVE1_ORDINALS),
                "streams": [
                    (item.spec.logical_stream_id, item.generated.stream.sha256)
                    for item in executed
                ],
            }
        )
    )
    files["teacher-plan.json"] = canonical_artifact_bytes(
        {
            "api_call_performed": False,
            "authorization_state": "not_submitted",
            "binding_sha256": binding,
            "decision_count": 10,
            "format_version": 1,
            "intended_model": "GPT-5.6 Sol",
            "kind": "phase2-response-wave1-chat-ui-teacher-plan",
            "manual_model_attestation_required": True,
            "one_case_per_stream_per_round": True,
            "oracle_blinded_inputs": True,
            "prompt_hash": artifacts.prompt_hash,
            "reasoning": "high",
            "round_count": len(rounds),
            "rounds": round_manifest,
            "source_bindings": _source_bindings(root),
            "source_unit_count": 5,
            "targets": targets,
            "teacher_transport": "chat_ui_manual",
            "wave_id": "response-wave-1",
        }
    )
    files["SHA256SUMS"] = _checksums(files)
    return ResponseWave1Packet(files, 10, len(rounds), 10)


def _routes(
    executed: tuple[ExecutedResponseWave1, ...],
) -> tuple[tuple[DecisionEvidence, ...], tuple[object, ...]]:
    evidence = tuple(
        DecisionEvidence(
            stream_sha256=item.generated.stream.sha256,
            decision_policy_seq=item.generated.sidecar.decisions[0].observed_policy_seq,
            wave_id="response-wave-1",
            cell=TrustCellKey(
                HarnessProtocol.GENERATION,
                CorpusFamily.NEUTRAL_TYPING,
                (
                    FloorClass.OPEN
                    if item.spec.member == "yielded"
                    else FloorClass.OWNED
                ),
            ),
            template_id=item.generated.program.template.asset_id,
            source_unit_id=item.spec.source_unit_id,
            oracle_action=item.generated.program.actions[0],
            teacher_action=item.generated.program.actions[0],
            causal_state_class=f"ordinary_response_{item.spec.member}",
            boundary_class=BoundaryClass.ACTIVE_FLOOR_RESPONSE,
            risk_flags=("active_floor_response_boundary",),
            rollover=False,
        )
        for item in executed
    )
    return evidence, route_wave(
        evidence,
        {},
        sampling_seed="phase2-response-wave1-d2-v1",
    )


def _source_bindings(root: Path) -> dict[str, str]:
    wave0 = root / "review/phase2/response-wave-0"
    selection = root / "review/phase2/response-tranche-selection"
    for directory in (wave0, selection):
        _verify_directory(directory)
    return {
        "response_selection_sha256": digest((selection / "SHA256SUMS").read_bytes()),
        "response_wave0_owner_disposition_sha256": digest(
            (wave0 / "OWNER-DISPOSITION.md").read_bytes()
        ),
        "response_wave0_packet_sha256": digest((wave0 / "SHA256SUMS").read_bytes()),
        "selection_contract_sha256": digest(
            (root / "spec/phase2-selection-v1.json").read_bytes()
        ),
    }


def _object(path: Path) -> dict[str, object]:
    import json

    value = json.loads(path.read_bytes())
    if not isinstance(value, dict):
        raise ResponseWave1Error(f"{path.name} is not an object")
    return value


def _verify_directory(directory: Path) -> None:
    for line in (directory / "SHA256SUMS").read_text().splitlines():
        checksum, separator, relative = line.partition("  ")
        if not separator or sha256((directory / relative).read_bytes()).hexdigest() != checksum:
            raise ResponseWave1Error(f"checksum failed under {directory.name}")


def _checksums(files: dict[str, bytes]) -> bytes:
    return "".join(
        f"{sha256(data).hexdigest()}  {name}\n" for name, data in sorted(files.items())
    ).encode()


def _readme(round_count: int) -> str:
    return f"""# WP2-5 response Wave-1 — Chat teacher canary

The final ten-decision canary contains five ordinary questions, each paired across the only
behavior change under review: the user is still typing or has paused. Every answer is an exact
owner-approved TRAIN payload and the substitution count is zero.

Upload each of the {round_count} files under `rounds/` separately in a fresh Temporary Chat using
GPT-5.6 Sol with high reasoning. Send:

`Read the attached round fully and return the requested downloadable JSONL file.`

Keep every requested output filename unchanged and place it in
`review/phase2/response-wave-1-results`. No API call or Chat upload has occurred.
"""
