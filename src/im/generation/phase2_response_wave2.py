"""Frozen allocation and bulk packet for WP2-5 response Wave-2."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, replace
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

from im.assets import AssetRegistry, CorpusFamily, Split
from im.assets.model import canonical_artifact_bytes
from im.canonical_json import canonicalize_tim_json, parse_tim_json
from im.config import estimate_tokens
from im.generation.g7_response_assets import SimpleResponseProfile
from im.generation.g7_response_twins import (
    build_g7_response_floor_twin_program,
    validate_response_floor_twin_alignment,
)
from im.generation.ingestion import ScheduledSamplerFrame
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
DEFAULT_RESPONSE_WAVE2_PLAN_OUTPUT = (
    _ROOT / "review" / "phase2" / "response-wave-2-plan-v2"
)
DEFAULT_RESPONSE_WAVE2_OUTPUT = _ROOT / "review" / "phase2" / "response-wave-2"
DEFAULT_RESPONSE_WAVE2_RESULTS = (
    _ROOT / "review" / "phase2" / "response-wave-2-results"
)
_PROMPT_TEMPLATE = "prompt-template-v4.txt"
_SELECTION_SEED = "phase2-response-wave2-selection-v1"
_WAVE0_ORDINALS = (1, 14, 15, 25)
_WAVE1_ORDINALS = (6, 9, 18, 26, 33)
_WAVE2_ORDINALS = (7, 8, 10, 11, 12, 13, 16, 17, 19, 20, 21, 22, 23, 24, 27)
_WAVE3_ORDINALS = (28, 29, 30, 31, 32, 34)
_THREE_VARIANT_ORDINALS = frozenset({7, 17, 27})
_NEUTRAL_ORDINALS = (1, *range(6, 35))
_STAGE = "t2rw2"
_MAX_OUTPUT_TOKENS = 8_192
_MAX_ROUND_TOKENS = 120_000


class ResponseWave2Error(ValueError):
    """The frozen response bulk allocation or its execution drifted."""


@dataclass(frozen=True, slots=True)
class ResponseWave2Spec:
    logical_stream_id: str
    source_unit_id: str
    candidate_ordinal: int
    variant: int
    member: str
    program: ScenarioProgram


@dataclass(frozen=True, slots=True)
class ExecutedResponseWave2:
    spec: ResponseWave2Spec
    generated: GeneratedScenario
    selected_segment: None = None


@dataclass(frozen=True, slots=True)
class ResponseWave2Packet:
    files: dict[str, bytes]
    decision_count: int
    round_count: int
    stream_count: int


def build_response_wave2_plan(*, repository_root: Path = _ROOT) -> dict[str, bytes]:
    """Freeze exact source, retry, quota, and whole-pair selection rules."""
    root = repository_root.resolve()
    prior = (*_WAVE0_ORDINALS, *_WAVE1_ORDINALS)
    all_neutral = (1, *range(6, 35))
    if (
        len(set((*prior, *_WAVE2_ORDINALS, *_WAVE3_ORDINALS))) != 30
        or set((*prior, *_WAVE2_ORDINALS, *_WAVE3_ORDINALS)) != set(all_neutral)
    ):
        raise ResponseWave2Error("response wave allocation does not partition all 30 records")
    variants = {
        str(ordinal): 3 if ordinal in _THREE_VARIANT_ORDINALS else 2
        for ordinal in _WAVE2_ORDINALS
    }
    if sum(variants.values()) != 33:
        raise ResponseWave2Error("Wave-2 must generate exactly 33 candidate twin pairs")
    plan = {
        "action_vectors": {
            "candidate_pool": {"idle": 33, "respond": 33},
            "selected_wave2": {"idle": 15, "respond": 15},
            "selected_wave3_projection": {"idle": 6, "respond": 6},
            "selected_waves0_1": {"idle": 9, "respond": 9},
            "wp2_5_final_projection": {"idle": 30, "respond": 30},
            "wp2_6_remaining_neutral_idle": 220,
        },
        "candidate_pair_count": 33,
        "candidate_stream_count": 66,
        "decisions_per_stream": 1,
        "format_version": 1,
        "kind": "phase2-response-wave2-frozen-allocation-v2",
        "payload_rule": (
            "Every variant reuses its response record byte-for-byte; timing changes, response "
            "text does not."
        ),
        "response_payload_substitution_count": 0,
        "supersedes": {
            "path": "review/phase2/response-wave-2-plan",
            "reason": (
                "Terminal response-floor counterfactuals are the explicit one-decision band "
                "exception; a shared five-decision prelude would duplicate training inputs."
            ),
        },
        "selection": {
            "eligibility": (
                "Both complete twin streams pass mechanical checks and owner disposition; "
                "no prefix salvage."
            ),
            "per_ordinal": (
                "After filtering ineligible pairs, choose the minimum SHA-256 rank of "
                "selection_seed:candidate_ordinal:variant."
            ),
            "seed": _SELECTION_SEED,
            "teacher_agreement_used_as_feature": False,
            "whole_twin_pairs_only": True,
        },
        "source_bindings": _source_bindings(root),
        "variant_counts_by_ordinal": variants,
        "variant_axis": {
            "0": "cursor_at_end",
            "1": "cursor_at_start",
            "2": "whole_invitation_selected",
        },
        "wave0_ordinals": list(_WAVE0_ORDINALS),
        "wave1_ordinals": list(_WAVE1_ORDINALS),
        "wave2_ordinals": list(_WAVE2_ORDINALS),
        "wave3_ordinals": list(_WAVE3_ORDINALS),
    }
    data = canonical_artifact_bytes(plan)
    files = {
        "README.md": _plan_readme().encode(),
        "plan.json": data,
    }
    files["SHA256SUMS"] = _checksums(files)
    return files


def materialize_response_wave2_plan(
    output: Path = DEFAULT_RESPONSE_WAVE2_PLAN_OUTPUT,
    *,
    repository_root: Path = _ROOT,
) -> dict[str, bytes]:
    files = build_response_wave2_plan(repository_root=repository_root)
    publish_directory_transaction(output, files)
    return files


async def build_response_wave2_packet(
    *, repository_root: Path = _ROOT
) -> ResponseWave2Packet:
    """Execute the frozen 33-pair candidate pool and render blinded Chat rounds."""
    root = repository_root.resolve()
    _verify_directory(root / "review/phase2/response-wave-2-plan-v2")
    specs = _program_specs(load_lookup_wave0_inputs(), root)
    with TemporaryDirectory(prefix="phase2-response-wave2-") as temporary:
        executed = []
        for spec in specs:
            generated = await execute_scenario(
                spec.program,
                session_id=f"response-wave2-{spec.logical_stream_id}",
                directory=Path(temporary) / spec.logical_stream_id,
                repository_root=root,
            )
            validate_generated_scenario(generated)
            executed.append(ExecutedResponseWave2(spec, generated))
        values = tuple(executed)
        battery = _validate(values, root)
        return _packet(values, battery, root)


async def materialize_response_wave2_packet(
    output: Path = DEFAULT_RESPONSE_WAVE2_OUTPUT,
    *,
    repository_root: Path = _ROOT,
) -> ResponseWave2Packet:
    packet = await build_response_wave2_packet(repository_root=repository_root)
    publish_directory_transaction(output, packet.files)
    output.parent.joinpath(DEFAULT_RESPONSE_WAVE2_RESULTS.name).mkdir(exist_ok=True)
    return packet


def _program_specs(
    registry: AssetRegistry,
    root: Path,
    *,
    ordinals: tuple[int, ...] = _WAVE2_ORDINALS,
    three_variant_ordinals: frozenset[int] = _THREE_VARIANT_ORDINALS,
    seed_prefix: str = "phase2-response-wave2",
) -> tuple[ResponseWave2Spec, ...]:
    assets = _response_assets(root)
    profiles = tuple(
        SimpleResponseProfile(
            tuple(assets[ordinal] for ordinal in _NEUTRAL_ORDINALS[start : start + 10])
        )
        for start in range(0, 30, 10)
    )
    inputs = _family_inputs(registry, CorpusFamily.NEUTRAL_TYPING)
    specs = []
    for ordinal in ordinals:
        neutral_index = _NEUTRAL_ORDINALS.index(ordinal)
        profile_index, item_index = divmod(neutral_index, 10)
        variant_count = 3 if ordinal in three_variant_ordinals else 2
        for variant in range(variant_count):
            twin = build_g7_response_floor_twin_program(
                registry,
                split=Split.TRAIN,
                family=CorpusFamily.NEUTRAL_TYPING,
                inputs=inputs,
                profile=profiles[profile_index],
                master_seed=f"{seed_prefix}:{ordinal:03d}:v{variant}",
                item_index=item_index,
            )
            programs = _cursor_variant(twin.programs, variant)
            for member, program in zip(("yielded", "active"), programs, strict=True):
                specs.append(
                    ResponseWave2Spec(
                        f"response-{ordinal:03d}-v{variant}-{member}",
                        f"response-wave2-{ordinal:03d}",
                        ordinal,
                        variant,
                        member,
                        replace(program, prompt_template=_PROMPT_TEMPLATE),
                    )
                )
    return tuple(specs)


def _cursor_variant(
    programs: tuple[ScenarioProgram, ScenarioProgram], variant: int
) -> tuple[ScenarioProgram, ScenarioProgram]:
    if variant not in {0, 1, 2}:
        raise ResponseWave2Error("unknown response cursor variant")
    changed = []
    for program in programs:
        raw = parse_tim_json(program.frames[0].raw_bytes)
        if not isinstance(raw, dict) or not isinstance(raw.get("text"), str):
            raise ResponseWave2Error("response sampler frame is malformed")
        end = len(raw["text"].encode("utf-16-le")) // 2
        start, stop = ((end, end), (0, 0), (0, end))[variant]
        raw["selection_start"] = start
        raw["selection_end"] = stop
        changed.append(
            replace(
                program,
                frames=(
                    ScheduledSamplerFrame(
                        program.frames[0].at_ms,
                        canonicalize_tim_json(raw),
                    ),
                ),
            )
        )
    values = tuple(changed)
    assert len(values) == 2
    validate_response_floor_twin_alignment(values[0], values[1])
    return values  # type: ignore[return-value]


def _validate(
    executed: tuple[ExecutedResponseWave2, ...], root: Path
) -> dict[str, object]:
    if len(executed) != 66:
        raise ResponseWave2Error("Wave-2 must contain exactly 66 candidate streams")
    assets = _response_assets(root)
    actions = Counter(
        action.type for item in executed for action in item.generated.program.actions
    )
    variants = Counter(
        (item.spec.candidate_ordinal, item.spec.variant)
        for item in executed
        if item.spec.member == "yielded"
    )
    if (
        actions != Counter(idle=33, respond=33)
        or len(variants) != 33
        or set(variants.values()) != {1}
    ):
        raise ResponseWave2Error("Wave-2 action or pair vector drifted")
    prior_hashes = set()
    for relative in (
        "review/phase2/response-wave-0/raw-stream-evidence.json",
        "review/phase2/response-wave-1/raw-streams.json",
    ):
        prior = _object(root / relative)
        prior_hashes.update(row["stream_sha256"] for row in prior["streams"])
    hashes = {item.generated.stream.sha256 for item in executed}
    inputs = {item.generated.stream.decisions[0].prefix_bytes for item in executed}
    if len(hashes) != 66 or len(inputs) != 66 or hashes & prior_hashes:
        raise ResponseWave2Error("Wave-2 repeats a stream, model input, or prior case")
    for ordinal, variant in variants:
        pair = tuple(
            item
            for item in executed
            if (item.spec.candidate_ordinal, item.spec.variant) == (ordinal, variant)
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
            or assets[ordinal].draft.answer_contract.response_kind
            is not ResponseKind.ORDINARY_GROUNDED
            or not isinstance(yielded_action, RespondAction)
            or yielded_action.text != assets[ordinal].candidate_response
            or not isinstance(active_action, IdleAction)
            or active_action.reason is not IdleReason.AWAITING_OPENING
        ):
            raise ResponseWave2Error("response floor or approved payload drifted")
    return {
        "action_counts": dict(sorted(actions.items())),
        "candidate_pair_count": 33,
        "checks": {
            "all_model_inputs_unique": True,
            "all_questions_answered_by_exact_approved_payload": True,
            "all_streams_disjoint_from_prior_response_waves": True,
            "all_streams_train_prompt_v4_bound": True,
            "cursor_variants_visible_and_behavior_preserving": True,
            "response_floor_twins_aligned": True,
            "response_payload_substitution_count_zero": True,
            "terminal_floor_one_decision_exception_preserved": True,
        },
        "decision_count": 66,
        "format_version": 1,
        "kind": "phase2-response-wave2-pre-upload-battery",
        "source_unit_count": 15,
        "stream_count": 66,
    }


def _packet(
    executed: tuple[ExecutedResponseWave2, ...],
    battery: dict[str, object],
    root: Path,
    *,
    stage: str = _STAGE,
    ordering_seed: str = _SELECTION_SEED,
    wave_id: str = "response-wave-2",
    artifact_prefix: str = "phase2-response-wave2",
    source_bindings: dict[str, str] | None = None,
    readme: bytes | None = None,
) -> ResponseWave2Packet:
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
    evidence, routes = _routes(
        executed,
        wave_id=wave_id,
        sampling_seed=f"{artifact_prefix}-d2-v1",
    )
    route_by_identity = {route.identity: route for route in routes}
    cases = []
    targets = []
    system_prompts = set()
    for item in executed:
        action = item.generated.program.actions[0]
        boundary = item.generated.decision_boundaries[0]
        body = builder.build(boundary.policy_bytes)
        body_bytes = canonical_artifact_bytes(body)
        custom_id = f"{stage}.{item.spec.logical_stream_id}.d000.a1"
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
                "member": item.spec.member,
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
                "variant": item.spec.variant,
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
        raise ResponseWave2Error("teacher requests do not share one exact policy")
    system_prompt = system_prompts.pop()
    rounds = _rounds(cases, system_prompt, ordering_seed=ordering_seed)
    files: dict[str, bytes] = {
        "README.md": readme or _packet_readme(len(rounds)).encode(),
        "pre-upload-battery.json": canonical_artifact_bytes(battery),
        "raw-streams.json": canonical_artifact_bytes(
            {
                "format_version": 1,
                "kind": "phase2-response-wave2-parent-candidates",
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
        tokens = estimate_tokens(data)
        if tokens > _MAX_ROUND_TOKENS:
            raise ResponseWave2Error(f"{name} exceeds the Chat token budget")
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
    binding = digest(
        canonical_artifact_bytes(
            {
                "kind": f"{artifact_prefix}-binding-v1",
                "plan_sha256": digest(
                    (
                        root / "review/phase2/response-wave-2-plan-v2/SHA256SUMS"
                    ).read_bytes()
                ),
                "prompt_hash": artifacts.prompt_hash,
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
            "candidate_pair_count": len(executed) // 2,
            "decision_count": len(executed),
            "format_version": 1,
            "intended_model": "GPT-5.6 Sol",
            "kind": f"{artifact_prefix}-chat-ui-teacher-plan",
            "manual_model_attestation_required": True,
            "one_case_per_stream_per_round": True,
            "oracle_blinded_inputs": True,
            "prompt_hash": artifacts.prompt_hash,
            "reasoning": "high",
            "round_count": len(rounds),
            "rounds": round_manifest,
            "source_bindings": source_bindings or _source_bindings(root),
            "source_unit_count": len(
                {item.spec.source_unit_id for item in executed}
            ),
            "targets": targets,
            "teacher_transport": "chat_ui_manual",
            "wave_id": wave_id,
        }
    )
    files["SHA256SUMS"] = _checksums(files)
    return ResponseWave2Packet(files, len(executed), len(rounds), len(executed))


def _routes(
    executed: tuple[ExecutedResponseWave2, ...],
    *,
    wave_id: str = "response-wave-2",
    sampling_seed: str = "phase2-response-wave2-d2-v1",
) -> tuple[tuple[DecisionEvidence, ...], tuple[object, ...]]:
    evidence = tuple(
        DecisionEvidence(
            stream_sha256=item.generated.stream.sha256,
            decision_policy_seq=item.generated.sidecar.decisions[0].observed_policy_seq,
            wave_id=wave_id,
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
            causal_state_class=f"ordinary_response_{item.spec.member}_cursor_v{item.spec.variant}",
            boundary_class=BoundaryClass.ACTIVE_FLOOR_RESPONSE,
            risk_flags=("active_floor_response_boundary",),
            rollover=False,
        )
        for item in executed
    )
    return evidence, route_wave(
        evidence,
        {},
        sampling_seed=sampling_seed,
    )


def _object(path: Path) -> dict[str, object]:
    import json

    value = json.loads(path.read_bytes())
    if not isinstance(value, dict):
        raise ResponseWave2Error(f"{path.name} is not an object")
    return value


def _source_bindings(root: Path) -> dict[str, str]:
    wave0 = root / "review/phase2/response-wave-0"
    wave1 = root / "review/phase2/response-wave-1-execution"
    selection = root / "review/phase2/response-tranche-selection"
    for directory in (wave0, wave1, selection):
        _verify_directory(directory)
    return {
        "prompt_template_sha256": digest(
            (root / f"spec/{_PROMPT_TEMPLATE}").read_bytes()
        ),
        "response_selection_sha256": digest((selection / "SHA256SUMS").read_bytes()),
        "response_wave0_owner_disposition_sha256": digest(
            (wave0 / "OWNER-DISPOSITION.md").read_bytes()
        ),
        "response_wave1_owner_disposition_sha256": digest(
            (wave1 / "OWNER-DISPOSITION.md").read_bytes()
        ),
        "selection_contract_sha256": digest(
            (root / "spec/phase2-selection-v1.json").read_bytes()
        ),
    }


def _verify_directory(directory: Path) -> None:
    for line in (directory / "SHA256SUMS").read_text().splitlines():
        checksum, separator, relative = line.partition("  ")
        if not separator or sha256((directory / relative).read_bytes()).hexdigest() != checksum:
            raise ResponseWave2Error(f"checksum failed under {directory.name}")


def _checksums(files: dict[str, bytes]) -> bytes:
    return "".join(
        f"{sha256(data).hexdigest()}  {name}\n" for name, data in sorted(files.items())
    ).encode()


def _plan_readme() -> str:
    return """# WP2-5 response Wave-2 — corrected frozen allocation

Wave-2 targets 15 of the 21 remaining response records, exactly 71.4% of the remaining quota.
Thirty-three isolated terminal twins provide the frozen 2.2× fragile-stream multiplier. Variants
change only the visible cursor selection; both members of each twin differ only in active/paused
floor state. Selection keeps one whole twin pair per response record and never uses teacher
agreement as a feature. The earlier six-decision draft is preserved as superseded.
"""


def _packet_readme(round_count: int) -> str:
    return f"""# WP2-5 response Wave-2 — Chat teacher bulk

The final 66-decision packet contains 33 complete active/paused response-floor twins across 15
approved TRAIN response records. Cursor state supplies the 2.2× stream variants; response text is
never regenerated or substituted.

Upload each of the {round_count} files under `rounds/` separately in a fresh Temporary Chat using
GPT-5.6 Sol with high reasoning. Send:

`Read the attached round fully and return the requested downloadable JSONL file.`

Keep every requested output filename unchanged and place it in
`review/phase2/response-wave-2-results`. No API call or Chat upload has occurred.
"""
