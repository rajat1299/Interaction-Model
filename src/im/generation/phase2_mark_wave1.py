"""Deterministic WP2-4 mark Wave-1 canary and oracle-blind Chat packet."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, replace
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

from im.assets import AssetRegistry, CorpusFamily, Split
from im.assets.model import canonical_artifact_bytes
from im.canonical_json import parse_tim_json
from im.config import estimate_tokens
from im.generation.counterfactuals import TwinAxis, build_twin_programs
from im.generation.g7_catalog import G7FamilyInputs, build_g7_mark_fresh_programs
from im.generation.g7_response_assets import SimpleResponseProfile
from im.generation.g7_response_twins import build_g7_response_floor_twin_program
from im.generation.phase2_lookup_wave0 import _raw_stream, load_lookup_wave0_inputs
from im.generation.phase2_lookup_wave1 import _message
from im.generation.phase2_lookup_wave2 import _response_assets
from im.generation.phase2_review import (
    BoundaryClass,
    DecisionEvidence,
    FloorClass,
    TrustCellKey,
    route_wave,
)
from im.generation.phase2_timer_wave2_chat import _round_markdown, _rounds
from im.generation.publication import publish_directory_transaction
from im.generation.scenario_catalog import build_family_program
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
DEFAULT_MARK_WAVE1_OUTPUT = _ROOT / "review" / "phase2" / "mark-wave-1"
_POSITIVE_TEMPLATE = "a_a1c85d29665460b9b04ffcd2"
_NEGATIVE_TEMPLATE = "a_cf3fb85cbef8786d98724b33"
_PROMPT_TEMPLATE = "prompt-template-v4.txt"
_EXPECTED_DECISIONS = 62
_EXPECTED_STREAMS = 14
_EXPECTED_SOURCE_UNITS = 10
_MAX_OUTPUT_TOKENS = 8_192
_MAX_ROUND_TOKENS = 120_000
_STAGE = "t2mw1"

_POSITIVE_RESPONSE_ORDINALS = (35, 36, 37, 38, 40, 41, 42, 43, 44, 45)
_NEGATIVE_RESPONSE_ORDINALS = tuple(range(46, 56))
_NEW_MARK_ASSETS = frozenset(
    {
        "a_052537ca3568ef0f0bb8d2ff",
        "a_8870dc68ae7d0dc1e044ebd9",
        "a_f351a4bfbebbcd5774458b62",
        "a_32863bc6a16105594851440b",
        "a_15ad2d6715b3cf386a1e8806",
        "a_4403c1d7dc44aa1b08e481e8",
        "a_1fb02095621d94505e18eadf",
        "a_e0c1efbe331c909d31ead541",
    }
)


class MarkWave1Error(ValueError):
    """The fixed mark canary is incomplete, repeated, or unsafe to upload."""


@dataclass(frozen=True, slots=True)
class MarkWave1Spec:
    logical_stream_id: str
    source_unit_id: str
    kind: str
    program: ScenarioProgram
    response_candidate_ordinal: int | None = None


@dataclass(frozen=True, slots=True)
class ExecutedMarkWave1:
    spec: MarkWave1Spec
    generated: GeneratedScenario
    selected_segment: None = None


@dataclass(frozen=True, slots=True)
class MarkWave1Packet:
    files: dict[str, bytes]
    decision_count: int
    round_count: int
    stream_count: int


async def build_mark_wave1_packet(*, repository_root: Path = _ROOT) -> MarkWave1Packet:
    """Execute the 62-decision TRAIN canary and render it without any upload."""
    root = repository_root.resolve()
    registry = load_lookup_wave0_inputs()
    specs, response_plan = _program_specs(registry, root)
    with TemporaryDirectory(prefix="phase2-mark-wave1-") as temporary:
        executed = []
        for spec in specs:
            generated = await execute_scenario(
                spec.program,
                session_id=f"phase2-mark-wave1-{spec.logical_stream_id}",
                directory=Path(temporary) / spec.logical_stream_id,
                repository_root=root,
            )
            validate_generated_scenario(generated)
            executed.append(ExecutedMarkWave1(spec, generated))
    values = tuple(executed)
    battery = _validate(values, root)
    return _packet(values, battery, response_plan, root)


async def materialize_mark_wave1_packet(
    output: Path = DEFAULT_MARK_WAVE1_OUTPUT,
    *,
    repository_root: Path = _ROOT,
) -> MarkWave1Packet:
    packet = await build_mark_wave1_packet(repository_root=repository_root)
    publish_directory_transaction(output, packet.files)
    return packet


def _program_specs(
    registry: AssetRegistry,
    root: Path,
) -> tuple[tuple[MarkWave1Spec, ...], dict[str, object]]:
    positive_a = G7FamilyInputs(_POSITIVE_TEMPLATE, ("a_052537ca3568ef0f0bb8d2ff",))
    positive_b = G7FamilyInputs(_POSITIVE_TEMPLATE, ("a_8870dc68ae7d0dc1e044ebd9",))
    negative_a = G7FamilyInputs(
        _NEGATIVE_TEMPLATE,
        (
            "a_f351a4bfbebbcd5774458b62",
            "a_15ad2d6715b3cf386a1e8806",
            "a_4403c1d7dc44aa1b08e481e8",
        ),
    )
    negative_b = G7FamilyInputs(
        _NEGATIVE_TEMPLATE,
        (
            "a_f351a4bfbebbcd5774458b62",
            "a_1fb02095621d94505e18eadf",
            "a_e0c1efbe331c909d31ead541",
        ),
    )
    first = dict(
        build_g7_mark_fresh_programs(
            registry,
            split=Split.TRAIN,
            positive_inputs=positive_a,
            negative_inputs=negative_a,
            master_seed="phase2-mark-wave1:core:a",
        )
    )
    second = dict(
        build_g7_mark_fresh_programs(
            registry,
            split=Split.TRAIN,
            positive_inputs=positive_b,
            negative_inputs=negative_b,
            master_seed="phase2-mark-wave1:core:b",
        )
    )
    response_assets = _response_assets(root)
    positive_profile = SimpleResponseProfile(
        tuple(response_assets[ordinal] for ordinal in _POSITIVE_RESPONSE_ORDINALS)
    )
    negative_profile = SimpleResponseProfile(
        tuple(response_assets[ordinal] for ordinal in _NEGATIVE_RESPONSE_ORDINALS)
    )
    positive_response = build_g7_response_floor_twin_program(
        registry,
        split=Split.TRAIN,
        family=CorpusFamily.MARK_POSITIVE,
        inputs=positive_a,
        profile=positive_profile,
        master_seed="phase2-mark-wave1:response:positive",
        item_index=0,
    )
    negative_response = build_g7_response_floor_twin_program(
        registry,
        split=Split.TRAIN,
        family=CorpusFamily.MARK_NEGATIVE,
        inputs=negative_a,
        profile=negative_profile,
        master_seed="phase2-mark-wave1:response:negative",
        item_index=0,
    )
    targeting = G7FamilyInputs(
        _POSITIVE_TEMPLATE,
        ("a_f351a4bfbebbcd5774458b62",),
    )
    directness = build_twin_programs(
        TwinAxis.DIRECTNESS,
        registry,
        split=Split.TRAIN,
        template_id=targeting.template_id,
        asset_ids=targeting.asset_ids,
        master_seed="phase2-mark-wave1:directness",
    )
    lexical = build_twin_programs(
        TwinAxis.LEXICAL_BOUNDARY,
        registry,
        split=Split.TRAIN,
        template_id=targeting.template_id,
        asset_ids=targeting.asset_ids,
        master_seed="phase2-mark-wave1:lexical",
    )
    lifecycle = (
        (
            "negative-stop",
            "direct_stop",
            "a_e2dd083f4916def2a997d4bf",
        ),
        (
            "negative-replacement",
            "direct_replacement",
            "a_32863bc6a16105594851440b",
        ),
    )

    def v3(program: ScenarioProgram) -> ScenarioProgram:
        return replace(program, prompt_template=_PROMPT_TEMPLATE)

    specs = [
        MarkWave1Spec(
            "positive-core-a",
            "mark-wave1-positive-core-a",
            "positive_quota_a",
            v3(first["mark-positive-a"]),
        ),
        MarkWave1Spec(
            "positive-core-b",
            "mark-wave1-positive-core-b",
            "positive_quota_b",
            v3(second["mark-positive-b"]),
        ),
    ]
    specs.extend(
        MarkWave1Spec(
            f"positive-response-{member}",
            "mark-wave1-positive-response",
            f"positive_response_{member}",
            v3(program),
            _POSITIVE_RESPONSE_ORDINALS[0],
        )
        for member, program in zip(("yielded", "active"), positive_response.programs, strict=True)
    )
    for kind, twins in (("directness", directness), ("lexical", lexical)):
        specs.extend(
            MarkWave1Spec(
                f"positive-{kind}-{program.counterfactual.member_id}",
                f"mark-wave1-positive-{kind}",
                f"positive_{kind}_{program.counterfactual.member_id}",
                v3(program),
            )
            for program in twins.programs
            if program.counterfactual is not None
        )
    specs.extend(
        (
            MarkWave1Spec(
                "negative-core-a",
                "mark-wave1-negative-core-a",
                "negative_quota_a",
                v3(first["mark-negative"]),
            ),
            MarkWave1Spec(
                "negative-core-b",
                "mark-wave1-negative-core-b",
                "negative_quota_b",
                v3(second["mark-negative"]),
            ),
        )
    )
    specs.extend(
        MarkWave1Spec(
            f"negative-response-{member}",
            "mark-wave1-negative-response",
            f"negative_response_{member}",
            v3(program),
            _NEGATIVE_RESPONSE_ORDINALS[0],
        )
        for member, program in zip(("yielded", "active"), negative_response.programs, strict=True)
    )
    specs.extend(
        MarkWave1Spec(
            logical,
            f"mark-wave1-{logical}",
            kind,
            v3(
                build_family_program(
                    CorpusFamily.MARK_NEGATIVE,
                    registry,
                    split=Split.TRAIN,
                    template_id=_NEGATIVE_TEMPLATE,
                    asset_ids=(asset_id,),
                    master_seed=f"phase2-mark-wave1:{kind}",
                )
            ),
        )
        for logical, kind, asset_id in lifecycle
    )
    plan = {
        "format_version": 1,
        "kind": "phase2-mark-response-allocation-v1",
        "mark_activation_positive": list(_POSITIVE_RESPONSE_ORDINALS),
        "mark_lifecycle_negative": list(_NEGATIVE_RESPONSE_ORDINALS),
        "rule": "fixed before candidate execution; one distinct ten-asset profile per family",
        "selection_sha256": digest(
            (root / "review/phase2/response-tranche-selection/selection.json").read_bytes()
        ),
    }
    return tuple(specs), plan


def _validate(
    executed: tuple[ExecutedMarkWave1, ...],
    root: Path,
) -> dict[str, object]:
    family_counts = Counter()
    action_counts: dict[str, Counter[str]] = {}
    assets = set()
    hashes = set()
    expected_prompt = digest((root / "spec" / _PROMPT_TEMPLATE).read_bytes())
    for item in executed:
        program = item.generated.program
        family = program.family.value
        actions = Counter(action.type for action in program.actions)
        family_counts[family] += len(program.actions)
        action_counts.setdefault(family, Counter()).update(actions)
        assets.update(program.asset_ids)
        hashes.add(item.generated.stream.sha256)
        if (
            program.bundle.split is not Split.TRAIN
            or program.prompt_template != _PROMPT_TEMPLATE
            or dict(item.generated.stream.provenance.artifact_hashes).get("prompt")
            != expected_prompt
        ):
            raise MarkWave1Error("Wave-1 escaped sealed TRAIN prompt-v3 inputs")
    if (
        len(executed) != _EXPECTED_STREAMS
        or len({item.spec.source_unit_id for item in executed}) != _EXPECTED_SOURCE_UNITS
        or sum(family_counts.values()) != _EXPECTED_DECISIONS
        or len(hashes) != _EXPECTED_STREAMS
    ):
        raise MarkWave1Error("Wave-1 stream/source/decision inventory drifted")
    expected = {
        CorpusFamily.MARK_POSITIVE.value: Counter(idle=18, mark=17, respond=1),
        CorpusFamily.MARK_NEGATIVE.value: Counter(idle=19, mark=6, respond=1),
    }
    if family_counts != {
        CorpusFamily.MARK_POSITIVE.value: 36,
        CorpusFamily.MARK_NEGATIVE.value: 26,
    } or action_counts != expected:
        raise MarkWave1Error("Wave-1 no longer matches its exact family/action vectors")
    if not _NEW_MARK_ASSETS <= assets:
        raise MarkWave1Error("a newly sealed mark asset is only nominally covered")
    if hashes & _wave0_hashes(root):
        raise MarkWave1Error("Wave-1 repeats an approved Wave-0 stream")

    by_kind = {item.spec.kind: item for item in executed}
    for kind, expected_frames in {
        "direct_stop": (
            "Mark every occurrence of the ruby otter.",
            "Stop marking the ruby otter.",
        ),
        "direct_replacement": (
            "Mark every occurrence of route names.",
            "Switch from route names to station names.",
        ),
    }.items():
        item = by_kind[kind]
        frames = tuple(
            parse_tim_json(frame.raw_bytes)["text"]
            for frame in item.generated.program.frames
        )
        if frames != expected_frames or any(
            not isinstance(action, IdleAction) or action.reason is not IdleReason.NO_TRIGGER
            for action in item.generated.program.actions
        ):
            raise MarkWave1Error(f"{kind} lost its visible prior control or idle semantics")
    embedded = by_kind["positive_lexical_embedded"].generated.program.actions
    if not (
        len(embedded) == 1
        and isinstance(embedded[0], IdleAction)
        and embedded[0].reason is IdleReason.NO_TRIGGER
    ) or not any(
        isinstance(action, IdleAction) and action.reason is IdleReason.TYPING_ACTIVE
        for item in executed
        if item.spec.kind == "negative_quota_b"
        for action in item.generated.program.actions
    ):
        raise MarkWave1Error("partial or lexical-boundary restraint disappeared")
    for family, ordinal in (
        (CorpusFamily.MARK_POSITIVE, _POSITIVE_RESPONSE_ORDINALS[0]),
        (CorpusFamily.MARK_NEGATIVE, _NEGATIVE_RESPONSE_ORDINALS[0]),
    ):
        pair = tuple(
            item
            for item in executed
            if item.generated.program.family is family
            and item.spec.response_candidate_ordinal == ordinal
        )
        actions = tuple(item.generated.program.actions[0] for item in pair)
        if (
            len(pair) != 2
            or not any(isinstance(action, RespondAction) for action in actions)
            or not any(
                isinstance(action, IdleAction)
                and action.reason is IdleReason.AWAITING_OPENING
                for action in actions
            )
        ):
            raise MarkWave1Error("response-floor twins are incomplete")
    return {
        "action_counts": {
            family: dict(sorted(counts.items()))
            for family, counts in action_counts.items()
        },
        "checks": {
            "all_eight_new_assets_rendered": True,
            "all_streams_disjoint_from_approved_wave0": True,
            "direct_stop_and_replacement_have_matching_visible_prior_controls": True,
            "final_materialized_streams_checked": True,
            "partial_and_lexical_boundaries_front_loaded": True,
            "prompt_v3_bound": True,
            "response_payloads_owner_selected_and_exact": True,
        },
        "decision_count": _EXPECTED_DECISIONS,
        "family_counts": dict(sorted(family_counts.items())),
        "format_version": 1,
        "kind": "phase2-mark-wave1-pre-upload-battery",
        "source_unit_count": _EXPECTED_SOURCE_UNITS,
        "stream_count": _EXPECTED_STREAMS,
    }


def _packet(
    executed: tuple[ExecutedMarkWave1, ...],
    battery: dict[str, object],
    response_plan: dict[str, object],
    root: Path,
) -> MarkWave1Packet:
    artifacts = PromptArtifacts(
        behavior_spec=(root / "spec/behavior-spec.md").read_bytes(),
        action_schema=(root / "spec/schema/action-v1.json").read_bytes(),
        prompt_template=(root / f"spec/{_PROMPT_TEMPLATE}").read_bytes(),
    )
    config = PromptedPolicyConfig(
        model="gpt-5.6-sol",
        reasoning_effort="high",
        max_output_tokens=_MAX_OUTPUT_TOKENS,
        max_attempts=1,
    )
    builder = ResponsesRequestBuilder(PromptRenderer(artifacts), config)
    evidence, routes = _routes(executed)
    route_by_identity = {route.identity: route for route in routes}
    binding = digest(
        canonical_artifact_bytes(
            {
                "kind": "phase2-mark-wave1-binding-v1",
                "prompt_hash": artifacts.prompt_hash,
                "response_allocation": response_plan,
                "streams": [
                    (item.spec.logical_stream_id, item.generated.stream.sha256) for item in executed
                ],
            }
        )
    )
    cases = []
    targets = []
    system_prompts = set()
    for item in executed:
        for index, action in enumerate(item.generated.program.actions):
            boundary = item.generated.decision_boundaries[index]
            custom_id = f"{_STAGE}.{item.spec.logical_stream_id}.d{index:03d}.a1"
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
                    "candidate_ordinal": index,
                    "custom_id": custom_id,
                    "input_sha256": digest(_message(body, 1).encode()),
                    "logical_stream_id": item.spec.logical_stream_id,
                    "policy_stream": _message(body, 1),
                }
            )
    if len(cases) != _EXPECTED_DECISIONS or len(system_prompts) != 1:
        raise MarkWave1Error("teacher request inventory or exact policy drifted")
    system_prompt = system_prompts.pop()
    rounds = _rounds(cases, system_prompt)
    files: dict[str, bytes] = {
        "README.md": _readme(len(rounds)).encode(),
        "pre-upload-battery.json": canonical_artifact_bytes(battery),
        "raw-streams.json": canonical_artifact_bytes(
            {
                "format_version": 1,
                "kind": "phase2-mark-wave1-parent-candidates",
                "streams": [_raw_stream(item) for item in executed],  # type: ignore[arg-type]
            }
        ),
        "response-allocation.json": canonical_artifact_bytes(response_plan),
    }
    round_manifest = []
    for ordinal, round_cases in enumerate(rounds, 1):
        name = f"round-{ordinal:03d}"
        path = f"rounds/{name}.md"
        data = _round_markdown(name, round_cases, system_prompt, f"{name}.output.jsonl")
        tokens = estimate_tokens(data)
        if tokens > _MAX_ROUND_TOKENS:
            raise MarkWave1Error(f"{name} exceeds the Chat token budget")
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
            "binding_sha256": binding,
            "decision_count": _EXPECTED_DECISIONS,
            "format_version": 1,
            "intended_model": "GPT-5.6 Sol",
            "kind": "phase2-mark-wave1-chat-ui-teacher-plan",
            "manual_model_attestation_required": True,
            "one_case_per_stream_per_round": True,
            "oracle_blinded_inputs": True,
            "prompt_hash": artifacts.prompt_hash,
            "reasoning": "high",
            "round_count": len(rounds),
            "rounds": round_manifest,
            "source_bindings": _source_bindings(root),
            "source_unit_count": _EXPECTED_SOURCE_UNITS,
            "targets": targets,
            "teacher_transport": "chat_ui_manual",
            "wave_id": "mark-wave-1",
        }
    )
    if any(
        b'"oracle_action"' in data or b'"teacher_action"' in data
        for name, data in files.items()
        if name.startswith("rounds/")
    ):
        raise MarkWave1Error("Chat input exposes a candidate label")
    files["SHA256SUMS"] = _checksums(files)
    return MarkWave1Packet(files, len(cases), len(rounds), len(executed))


def _routes(
    executed: tuple[ExecutedMarkWave1, ...],
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
                and item.spec.kind == "negative_quota_b"
            )
            lexical = (
                isinstance(action, IdleAction)
                and action.reason is IdleReason.TYPING_ACTIVE
                and item.spec.kind == "positive_lexical_embedded"
            )
            evidence.append(
                DecisionEvidence(
                    stream_sha256=item.generated.stream.sha256,
                    decision_policy_seq=sidecar.observed_policy_seq,
                    wave_id="mark-wave-1",
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
                    risk_flags=("active_floor_response_boundary",) if response_boundary else (),
                    idle_boundary=(
                        "lexical_boundary"
                        if lexical
                        else "partial_instruction"
                        if partial
                        else None
                    ),
                    rollover=False,
                )
            )
    values = tuple(evidence)
    return values, route_wave(values, {}, sampling_seed="phase2-mark-wave1-d2-v1")


def _wave0_hashes(root: Path) -> set[str]:
    packet = root / "review/phase2/mark-wave-0"
    _verify_checksums(packet)
    raw = json.loads((packet / "raw-stream-evidence.json").read_bytes())
    return {item["stream_sha256"] for item in raw["streams"]}


def _source_bindings(root: Path) -> dict[str, str]:
    approved = root / "review/phase1/approved"
    wave0 = root / "review/phase2/mark-wave-0"
    tranche = root / "review/phase2/mark-tranche-2-approved"
    selection = root / "review/phase2/response-tranche-selection"
    for directory in (wave0, tranche, selection):
        _verify_checksums(directory)
    return {
        "mark_tranche_2_approval_sha256": digest((tranche / "SHA256SUMS").read_bytes()),
        "mark_wave0_owner_disposition_sha256": digest(
            (wave0 / "OWNER-DISPOSITION.md").read_bytes()
        ),
        "mark_wave0_packet_sha256": digest((wave0 / "SHA256SUMS").read_bytes()),
        "registry_sha256": digest((approved / "registry.jsonl").read_bytes()),
        "response_selection_sha256": digest((selection / "SHA256SUMS").read_bytes()),
        "selection_contract_sha256": digest(
            (root / "spec/phase2-selection-v1.json").read_bytes()
        ),
        "train_seal_sha256": digest((approved / "train-seal.json").read_bytes()),
    }


def _verify_checksums(directory: Path) -> None:
    for line in (directory / "SHA256SUMS").read_text().splitlines():
        checksum, separator, relative = line.partition("  ")
        if not separator or sha256((directory / relative).read_bytes()).hexdigest() != checksum:
            raise MarkWave1Error(f"checksum failed under {directory.name}")


def _checksums(files: dict[str, bytes]) -> bytes:
    return "".join(
        f"{sha256(data).hexdigest()}  {name}\n" for name, data in sorted(files.items())
    ).encode()


def _readme(round_count: int) -> str:
    return f"""# WP2-4 mark Wave-1 — Chat teacher canary

The final materialized 62-decision canary passed its mechanical battery. It covers all eight
newly sealed mark assets, exact positive/negative quota shapes, partial and lexical boundaries,
direct stop/replacement controls, and both sides of owner-selected response-floor twins.

Upload each of the {round_count} files under `rounds/` separately in a fresh Temporary Chat using
GPT-5.6 Sol with high reasoning. Send:

`Read the attached round fully and return the requested downloadable JSONL file.`

Keep every requested output filename unchanged. Do not upload the local oracle or audit files.
No API call or Chat upload has occurred.
"""
