"""Provider-free WP2-3 lookup Wave-2 candidate and Chat teacher packet."""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass, replace
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

from im.assets import AssetRegistry, CorpusFamily, Split
from im.assets.model import LookupAssetPayload, TextAssetPayload, canonical_artifact_bytes
from im.config import estimate_tokens
from im.generation.corpus_segments import CorpusSegmentCandidate
from im.generation.g7_failed_response_twins import build_g7_failed_response_twin_programs
from im.generation.g7_response_assets import (
    GeneratedResponseAsset,
    ResponseDraftSpec,
    SimpleResponseProfile,
)
from im.generation.g7_response_twins import build_g7_response_floor_twin_program
from im.generation.phase2_lookup_wave0 import (
    _DUPLICATE_A_TYPES,
    _DUPLICATE_B_TYPES,
    _STALE_TYPES,
    _checkpoint_candidate,
    _program_for,
    _selected_actions,
    _StreamSpec,
    _validate_stream,
    load_lookup_wave0_inputs,
)
from im.generation.phase2_response_tranche import _contract, _family_inputs
from im.generation.phase2_review import (
    BoundaryClass,
    DecisionEvidence,
    FloorClass,
    TrustCellKey,
    route_wave,
)
from im.generation.phase2_timer_wave2_chat import _round_markdown, _rounds
from im.generation.publication import publish_directory_transaction
from im.generation.scenarios import (
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
from im.schema.actions import IdleAction, IdleReason, RespondAction, SkipAction, SkipReason

_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_LOOKUP_WAVE2_OUTPUT = _ROOT / "review" / "phase2" / "lookup-wave-2"
_BASE_PLAN = Path("review/phase2/lookup-wave-2-plan")
_RESPONSE_SELECTION = Path("review/phase2/response-tranche-selection")
_RESPONSE_GENERATION = Path("review/phase2/response-tranche-generation")
_PRIOR_PACKETS = (
    Path("review/phase2/lookup-wave-0-repair"),
    Path("review/phase2/lookup-wave-1-repaired"),
)
_PROMPT_TEMPLATE = "prompt-template-v3.txt"
_STAGE = "t2lw2"
_MAX_OUTPUT_TOKENS = 8_192
_MAX_ROUND_TOKENS = 120_000
_EXPECTED_STREAMS = 155
_EXPECTED_SOURCE_UNITS = 99
_EXPECTED_DECISIONS = 702
_TRUST_MATRIX_VERSION = "phase2-trust-v1"

_LIVE_TEMPLATE = "a_93beb83846363b159a8f8f67"
_DUPLICATE_TEMPLATE = "a_0c05ad0e07dcb3adfcea1ca1"
_STALE_TEMPLATE = "a_dd5c4e7300588ffc83ce7bb2"
_CHECKPOINT_TEXTS = (
    "a_0a86fd6dd35ddf5743c1f5c1",
    "a_1fac3cb0c0ab2e4c3274ce17",
    "a_925e8f56a405335c1622ab7c",
    "a_a84c08c816ea620b935c58fa",
    "a_bac0d5ac8c3be1075ff65976",
    "a_d0a35f5f140d791a52af02fa",
    "a_f9de5705e1b34cc0980d8fb8",
)

_EXPECTED_KINDS = {
    "g7-fresh-lookup-live-2i-2d-2g": (14, 84),
    "g7-checkpoint-lookup-live-failed-response": (28, 224),
    "g7-response-floor-ambiguity-lookup-live": (28, 28),
    "g7-checkpoint-lookup-duplicate-a": (11, 121),
    "g7-checkpoint-lookup-duplicate-b": (9, 117),
    "g7-checkpoint-lookup-stale": (9, 72),
    "g7-response-floor-lookup-stale-mixed": (28, 28),
    "g7-response-floor-lookup-stale-unsupported": (28, 28),
}


class LookupWave2Error(ValueError):
    """The frozen lookup Wave-2 candidate packet is incomplete or unsafe."""


@dataclass(frozen=True, slots=True)
class _CandidateSpec:
    logical_stream_id: str
    source_unit_id: str
    kind: str
    program: ScenarioProgram
    lookup_spec: _StreamSpec | None = None
    checkpoint_segment_index: int | None = None
    response_candidate_ordinal: int | None = None


@dataclass(frozen=True, slots=True)
class _ExecutedCandidate:
    logical_stream_id: str
    source_unit_id: str
    kind: str
    response_candidate_ordinal: int | None
    stream_sha256: str
    sidecar_sha256: str
    family: CorpusFamily
    template_id: str
    asset_ids: tuple[str, ...]
    prompt_hash: str
    action_indices: tuple[int, ...]
    actions: tuple[object, ...]
    policy_paths: tuple[Path, ...]
    decision_policy_seqs: tuple[int, ...]
    floors: tuple[FloorClass, ...]
    checkpoint: bool


@dataclass(frozen=True, slots=True)
class LookupWave2Packet:
    files: dict[str, bytes]
    decision_count: int
    round_count: int
    stream_count: int


async def build_lookup_wave2_packet(*, repository_root: Path = _ROOT) -> LookupWave2Packet:
    """Execute the frozen candidate pool and render oracle-blind Chat rounds."""
    root = repository_root.resolve()
    registry = load_lookup_wave0_inputs()
    response_assets = _response_assets(root)
    specs = _program_specs(registry, response_assets)
    with TemporaryDirectory(prefix="phase2-lookup-wave2-") as temporary:
        executed = await _execute(specs, Path(temporary), root)
        battery = _validate(executed, response_assets, root)
        return _packet(executed, battery, root)


async def materialize_lookup_wave2_packet(
    output: Path = DEFAULT_LOOKUP_WAVE2_OUTPUT,
    *,
    repository_root: Path = _ROOT,
) -> LookupWave2Packet:
    packet = await build_lookup_wave2_packet(repository_root=repository_root)
    publish_directory_transaction(output, packet.files)
    return packet


def _program_specs(
    registry: AssetRegistry,
    response_assets: dict[int, GeneratedResponseAsset],
) -> Iterator[_CandidateSpec]:
    pool = registry.pool(Split.TRAIN)  # type: ignore[union-attr]
    lookups = tuple(
        sorted(
            asset.asset_id
            for asset in pool.assets
            if isinstance(asset.payload, LookupAssetPayload)
        )
    )
    family_lookups = {
        family: tuple(
            asset.asset_id
            for asset in pool.assets
            if isinstance(asset.payload, LookupAssetPayload) and family in asset.coverage
        )
        for family in (
            CorpusFamily.LOOKUP_LIVE,
            CorpusFamily.LOOKUP_DUPLICATE,
            CorpusFamily.LOOKUP_STALE,
        )
    }
    text_assets = {
        asset.asset_id
        for asset in pool.assets
        if isinstance(asset.payload, TextAssetPayload)
    }
    if not set(_CHECKPOINT_TEXTS) <= text_assets:
        raise LookupWave2Error("approved checkpoint text inputs are incomplete")
    texts = _CHECKPOINT_TEXTS
    for ordinal in range(14):
        lookup_spec = _lookup_spec(
            "live",
            ordinal,
            lookups,
            family_lookups[CorpusFamily.LOOKUP_LIVE],
            texts,
            kind="g7-fresh-lookup-live-2i-2d-2g",
            family=CorpusFamily.LOOKUP_LIVE,
            template_id=_LIVE_TEMPLATE,
            lookup_count=2,
        )
        yield _lookup_candidate(registry, lookup_spec)

    failed_ordinals = (*range(97, 107), *range(97, 101))
    for source_ordinal, response_ordinal in enumerate(failed_ordinals):
        asset = response_assets[response_ordinal]
        twins = build_g7_failed_response_twin_programs(
            registry,
            invitation=asset.draft.invitation,
            answer_contract=asset.draft.answer_contract,
            candidate_response=asset.candidate_response,
            master_seed=f"phase2-lookup-wave2:failed:{source_ordinal:02d}",
            failed_lookup_index=response_ordinal - 97,
            split=Split.TRAIN,
        )
        yield from _twin_specs(
            twins.programs,
            kind="g7-checkpoint-lookup-live-failed-response",
            source_ordinal=source_ordinal,
            response_ordinal=response_ordinal,
            checkpoint_segment_index=twins.checkpoint_segment_index,
        )

    ambiguity_ordinals = tuple(
        ordinal
        for ordinal in range(65, 80)
        if ordinal in response_assets
    )
    if len(ambiguity_ordinals) != 14:
        raise LookupWave2Error("approved lookup ambiguity response inventory drifted")
    for source_ordinal, response_ordinal in enumerate(ambiguity_ordinals):
        yield from _response_floor_specs(
            registry,
            response_assets[response_ordinal],
            kind="g7-response-floor-ambiguity-lookup-live",
            family=CorpusFamily.LOOKUP_LIVE,
            source_ordinal=source_ordinal,
            response_ordinal=response_ordinal,
        )

    for kind, count, family, template, lookup_count, selected_types in (
        (
            "g7-checkpoint-lookup-duplicate-a",
            11,
            CorpusFamily.LOOKUP_DUPLICATE,
            _DUPLICATE_TEMPLATE,
            4,
            _DUPLICATE_A_TYPES,
        ),
        (
            "g7-checkpoint-lookup-duplicate-b",
            9,
            CorpusFamily.LOOKUP_DUPLICATE,
            _DUPLICATE_TEMPLATE,
            3,
            _DUPLICATE_B_TYPES,
        ),
        (
            "g7-checkpoint-lookup-stale",
            9,
            CorpusFamily.LOOKUP_STALE,
            _STALE_TEMPLATE,
            4,
            _STALE_TYPES,
        ),
    ):
        for ordinal in range(count):
            lookup_spec = _lookup_spec(
                kind.rsplit("-", 1)[-1],
                ordinal,
                lookups,
                family_lookups[family],
                texts,
                kind=kind,
                family=family,
                template_id=template,
                lookup_count=lookup_count,
                selected_types=selected_types,
            )
            yield _lookup_candidate(registry, lookup_spec)

    limitations = tuple(
        ordinal
        for ordinal in (*range(82, 94), 82, 83)
        if ordinal in response_assets
    )
    mixed = tuple(
        value
        for pair in zip(ambiguity_ordinals[:7], limitations[:7], strict=True)
        for value in pair
    )
    for kind, ordinals in (
        ("g7-response-floor-lookup-stale-mixed", mixed),
        ("g7-response-floor-lookup-stale-unsupported", limitations),
    ):
        for source_ordinal, response_ordinal in enumerate(ordinals):
            yield from _response_floor_specs(
                registry,
                response_assets[response_ordinal],
                kind=kind,
                family=CorpusFamily.LOOKUP_STALE,
                source_ordinal=source_ordinal,
                response_ordinal=response_ordinal,
            )


def _lookup_spec(
    label: str,
    ordinal: int,
    lookups: tuple[str, ...],
    family_lookups: tuple[str, ...],
    texts: tuple[str, ...],
    *,
    kind: str,
    family: CorpusFamily,
    template_id: str,
    lookup_count: int,
    selected_types: tuple[str, ...] | None = None,
) -> _StreamSpec:
    primary_lookup = family_lookups[ordinal % len(family_lookups)]
    other_lookups = tuple(asset_id for asset_id in lookups if asset_id != primary_lookup)
    selected_lookups = (
        primary_lookup,
        *(
            other_lookups[(ordinal * 3 + offset) % len(other_lookups)]
            for offset in range(lookup_count - 1)
        ),
    )
    primary = selected_lookups[0] if selected_types else None
    return _StreamSpec(
        f"{label}-{ordinal:02d}",
        (
            "lookup-live"
            if selected_types is None
            else kind
        ),
        f"lookup-wave2-{kind}-{ordinal:02d}",
        family,
        template_id,
        selected_lookups,
        tuple(texts[(ordinal * 2 + offset) % len(texts)] for offset in range(2))
        if selected_types
        else (),
        f"phase2-lookup-wave2:{kind}:{ordinal:02d}",
        primary,
        selected_types,
    )


def _lookup_candidate(registry: AssetRegistry, spec: _StreamSpec) -> _CandidateSpec:
    return _CandidateSpec(
        spec.logical_stream_id,
        spec.source_unit_id,
        (
            "g7-fresh-lookup-live-2i-2d-2g"
            if spec.shape_id == "lookup-live"
            else spec.shape_id
        ),
        replace(_program_for(registry, spec), prompt_template=_PROMPT_TEMPLATE),
        lookup_spec=spec,
    )


def _response_floor_specs(
    registry: AssetRegistry,
    asset: GeneratedResponseAsset,
    *,
    kind: str,
    family: CorpusFamily,
    source_ordinal: int,
    response_ordinal: int,
) -> tuple[_CandidateSpec, _CandidateSpec]:
    context = (
        "The earlier lookup result is stale.\n"
        if kind == "g7-response-floor-lookup-stale-mixed"
        else "The previous lookup result is no longer current.\n"
        if kind == "g7-response-floor-lookup-stale-unsupported"
        else ""
    )
    if kind == "g7-response-floor-lookup-stale-unsupported" and source_ordinal >= 12:
        context += "Please use the latest information.\n"
    if context:
        invitation = context + asset.draft.invitation
        asset = GeneratedResponseAsset.create(
            replace(asset.draft, invitation=invitation),
            teacher_visible_prefix=invitation,
            candidate_response=asset.candidate_response,
        )
    profile = SimpleResponseProfile((asset,) * 10)
    twins = build_g7_response_floor_twin_program(
        registry,
        split=Split.TRAIN,
        family=family,
        inputs=_family_inputs(registry, family),
        profile=profile,
        master_seed=f"phase2-lookup-wave2:{kind}:{source_ordinal:02d}",
        item_index=0,
    )
    return _twin_specs(
        twins.programs,
        kind=kind,
        source_ordinal=source_ordinal,
        response_ordinal=response_ordinal,
    )


def _twin_specs(
    programs: tuple[ScenarioProgram, ScenarioProgram],
    *,
    kind: str,
    source_ordinal: int,
    response_ordinal: int,
    checkpoint_segment_index: int | None = None,
) -> tuple[_CandidateSpec, _CandidateSpec]:
    result = []
    source_unit_id = f"lookup-wave2-{kind}-{source_ordinal:02d}"
    for member, program in zip(("yielded", "active"), programs, strict=True):
        result.append(
            _CandidateSpec(
                f"{kind}-{source_ordinal:02d}-{member}",
                source_unit_id,
                kind,
                replace(program, prompt_template=_PROMPT_TEMPLATE),
                checkpoint_segment_index=checkpoint_segment_index,
                response_candidate_ordinal=response_ordinal,
            )
        )
    return tuple(result)  # type: ignore[return-value]


async def _execute(
    specs: Iterator[_CandidateSpec],
    directory: Path,
    repository_root: Path,
) -> tuple[_ExecutedCandidate, ...]:
    executed = []
    expected_prompt = digest(
        (repository_root / "spec" / _PROMPT_TEMPLATE).read_bytes()
    )
    for spec in specs:
        try:
            generated = await execute_scenario(
                spec.program,
                session_id=f"phase2-lookup-wave2-{spec.logical_stream_id}",
                directory=directory / spec.logical_stream_id,
                repository_root=repository_root,
            )
        except ValueError as error:
            raise LookupWave2Error(
                f"{spec.logical_stream_id} failed generation: {error}"
            ) from error
        validate_generated_scenario(generated)
        if (
            generated.program.bundle.split is not Split.TRAIN
            or generated.program.prompt_template != _PROMPT_TEMPLATE
            or dict(generated.stream.provenance.artifact_hashes).get("prompt")
            != expected_prompt
        ):
            raise LookupWave2Error("Wave-2 escaped sealed TRAIN prompt-v3 inputs")
        candidate = None
        if spec.lookup_spec is not None:
            candidate = _checkpoint_candidate(spec.lookup_spec, generated)
            _validate_stream(spec.lookup_spec, generated, candidate)
        elif spec.checkpoint_segment_index is not None:
            candidate = CorpusSegmentCandidate(
                generated,
                spec.checkpoint_segment_index,
                spec.kind,
            )
        indices = (
            tuple(range(len(generated.program.actions)))
            if candidate is None
            else tuple(index - 1 for index in candidate.selected_call_indices)
        )
        actions = _selected_actions(generated, candidate)
        sidecars = tuple(generated.sidecar.decisions[index] for index in indices)
        policy_directory = directory / "selected-policy" / spec.logical_stream_id
        policy_directory.mkdir(parents=True, exist_ok=True)
        policy_paths = []
        for index in indices:
            path = policy_directory / f"{index:03d}.jsonl"
            path.write_bytes(generated.decision_boundaries[index].policy_bytes)
            policy_paths.append(path)
        executed.append(
            _ExecutedCandidate(
                logical_stream_id=spec.logical_stream_id,
                source_unit_id=spec.source_unit_id,
                kind=spec.kind,
                response_candidate_ordinal=spec.response_candidate_ordinal,
                stream_sha256=generated.stream.sha256,
                sidecar_sha256=generated.sidecar.sha256,
                family=generated.program.family,
                template_id=generated.program.template.asset_id,
                asset_ids=generated.program.asset_ids,
                prompt_hash=dict(generated.stream.provenance.artifact_hashes)["prompt"],
                action_indices=indices,
                actions=actions,
                policy_paths=tuple(policy_paths),
                decision_policy_seqs=tuple(
                    sidecar.observed_policy_seq for sidecar in sidecars
                ),
                floors=tuple(
                    FloorClass.OPEN
                    if sidecar.floor_open
                    else FloorClass.OWNED
                    if sidecar.floor_owned
                    else FloorClass.CLOSED
                    for sidecar in sidecars
                ),
                checkpoint=candidate is not None,
            )
        )
    return tuple(executed)


def _validate(
    executed: tuple[_ExecutedCandidate, ...],
    response_assets: dict[int, GeneratedResponseAsset],
    root: Path,
) -> dict[str, object]:
    kind_counts = Counter(item.kind for item in executed)
    decision_counts = Counter(
        {
            kind: sum(len(item.actions) for item in executed if item.kind == kind)
            for kind in kind_counts
        }
    )
    if {
        kind: (kind_counts[kind], decision_counts[kind])
        for kind in sorted(kind_counts)
    } != _EXPECTED_KINDS:
        raise LookupWave2Error("Wave-2 stream or decision vectors drifted")
    if (
        len(executed) != _EXPECTED_STREAMS
        or sum(len(item.actions) for item in executed) != _EXPECTED_DECISIONS
        or len({item.source_unit_id for item in executed}) != _EXPECTED_SOURCE_UNITS
    ):
        raise LookupWave2Error("Wave-2 totals differ from the frozen plan")
    hashes = [item.stream_sha256 for item in executed]
    repeats = {value for value, count in Counter(hashes).items() if count > 1}
    historical = set(hashes) & _prior_stream_hashes(root)
    if repeats or historical:
        affected = [
            item.logical_stream_id
            for item in executed
            if item.stream_sha256 in repeats | historical
        ]
        raise LookupWave2Error(
            f"Wave-2 repeats current or historical streams: {affected}"
        )

    expected_prompt = digest((root / "spec" / _PROMPT_TEMPLATE).read_bytes())
    response_usage = Counter()
    for item in executed:
        if (
            item.family not in {
                CorpusFamily.LOOKUP_LIVE,
                CorpusFamily.LOOKUP_DUPLICATE,
                CorpusFamily.LOOKUP_STALE,
            }
            or item.prompt_hash != expected_prompt
        ):
            raise LookupWave2Error("Wave-2 escaped sealed TRAIN prompt-v3 inputs")
        if item.checkpoint and not item.action_indices:
            raise LookupWave2Error("Wave-2 checkpoint candidate is empty")
        if item.response_candidate_ordinal is not None:
            response_usage[item.response_candidate_ordinal] += 1
            approved = response_assets[item.response_candidate_ordinal].candidate_response
            for action in item.actions:
                if isinstance(action, RespondAction) and action.text != approved:
                    raise LookupWave2Error("response twin substituted unapproved text")

    action_counts = Counter(action.type for item in executed for action in item.actions)
    if action_counts != Counter(
        delegate=133,
        idle=324,
        integrate=115,
        respond=56,
        skip=74,
    ):
        raise LookupWave2Error("Wave-2 action inventory drifted")
    skip_counts = Counter(
        action.reason.value
        for item in executed
        for action in item.actions
        if isinstance(action, SkipAction)
    )
    return {
        "action_counts": dict(sorted(action_counts.items())),
        "checks": {
            "all_approved_response_payloads_exact": True,
            "all_checkpoint_segments_complete": True,
            "all_integrations_natural_and_grounded": True,
            "all_streams_unique_and_prior_disjoint": True,
            "final_materialized_streams_checked": True,
            "prompt_v3_bound": True,
            "response_floor_twins_aligned": True,
            "sealed_train_only": True,
        },
        "decision_count": _EXPECTED_DECISIONS,
        "format_version": 1,
        "kind": "phase2-lookup-wave2-pre-upload-battery",
        "prediction_result": (
            f"The complete {_EXPECTED_DECISIONS}-decision candidate pool passed the "
            "pre-teacher battery."
        ),
        "response_candidate_usage": dict(sorted(response_usage.items())),
        "skip_reason_counts": dict(sorted(skip_counts.items())),
        "source_unit_count": _EXPECTED_SOURCE_UNITS,
        "stream_count": _EXPECTED_STREAMS,
        "stream_kind_counts": dict(sorted(kind_counts.items())),
    }


def _packet(
    executed: tuple[_ExecutedCandidate, ...],
    battery: dict[str, object],
    root: Path,
) -> LookupWave2Packet:
    base_plan_root = root / _BASE_PLAN
    _verify_directory(base_plan_root)
    base_plan = _object(base_plan_root / "candidate-plan.json")
    response_root = root / _RESPONSE_SELECTION
    _verify_directory(response_root)
    resolved_plan = {
        "base_candidate_plan_sha256": digest(
            (base_plan_root / "candidate-plan.json").read_bytes()
        ),
        "candidate_generation": base_plan["candidate_generation"],
        "candidate_totals": {
            **base_plan["candidate_totals"],
            "decisions": _EXPECTED_DECISIONS,
        },
        "format_version": 1,
        "kind": "phase2-lookup-wave2-resolved-candidate-plan",
        "response_dependency": {
            "owner_disposition_sha256": digest(
                (response_root / "OWNER-DISPOSITION.md").read_bytes()
            ),
            "selection_sha256": digest((response_root / "selection.json").read_bytes()),
            "status": "owner_approved_selection_bound",
        },
        "repair_amendment": {
            "failed_response_decisions_per_stream": 8,
            "reason": (
                "The approved three-second additive-request gap produces one honest "
                "awaiting-tool settling decision in each failed-response stream."
            ),
        },
        "target": base_plan["target"],
        "wave_id": "lookup-wave-2",
    }
    resolved_plan_bytes = canonical_artifact_bytes(resolved_plan)
    artifacts = PromptArtifacts(
        behavior_spec=(root / "spec" / "behavior-spec.md").read_bytes(),
        action_schema=(root / "spec" / "schema" / "action-v1.json").read_bytes(),
        prompt_template=(root / "spec" / _PROMPT_TEMPLATE).read_bytes(),
    )
    config = PromptedPolicyConfig(
        model="gpt-5.6-sol",
        reasoning_effort="high",
        max_output_tokens=_MAX_OUTPUT_TOKENS,
        max_attempts=1,
    )
    builder = ResponsesRequestBuilder(PromptRenderer(artifacts), config)
    binding = digest(
        canonical_artifact_bytes(
            {
                "kind": "phase2-lookup-wave2-binding-v1",
                "prompt_hash": artifacts.prompt_hash,
                "resolved_plan_sha256": digest(resolved_plan_bytes),
                "streams": [
                    (item.logical_stream_id, item.stream_sha256)
                    for item in executed
                ],
            }
        )
    )
    evidence, routes = _routes(executed)
    route_by_identity = {route.identity: route for route in routes}
    targets, cases = [], []
    system_prompt: str | None = None
    for item in executed:
        for action_index, action, policy_path, policy_seq in zip(
            item.action_indices,
            item.actions,
            item.policy_paths,
            item.decision_policy_seqs,
            strict=True,
        ):
            policy_bytes = policy_path.read_bytes()
            custom_id = f"{_STAGE}.{item.logical_stream_id}.d{action_index:03d}.a1"
            body = builder.build(policy_bytes)
            body_bytes = canonical_artifact_bytes(body)
            current_prompt = _message(body, 0)
            if system_prompt is None:
                system_prompt = current_prompt
            elif current_prompt != system_prompt:
                raise LookupWave2Error("teacher requests do not share one exact policy")
            route = route_by_identity[
                f"{item.stream_sha256}\x00{policy_seq}"
            ]
            target = {
                "candidate_selected_program_action_indices": list(item.action_indices),
                "custom_id": custom_id,
                "family": item.family.value,
                "logical_stream_id": item.logical_stream_id,
                "oracle_action": action.model_dump(mode="json"),
                "policy_prefix_sha256": digest(policy_bytes),
                "program_action_index": action_index,
                "request_body_sha256": digest(body_bytes),
                "response_candidate_ordinal": item.response_candidate_ordinal,
                "source_unit_id": item.source_unit_id,
                "static_d2_route": {
                    "mandatory_review": route.mandatory,
                    "reasons": list(route.reasons),
                    "review_required": route.review_required,
                    "sample_rate": route.sample_rate,
                },
                "stream_kind": item.kind,
                "stream_sha256": item.stream_sha256,
            }
            targets.append(target)
            cases.append(_case(custom_id, body, target))
    if len(cases) != _EXPECTED_DECISIONS or system_prompt is None:
        raise LookupWave2Error("teacher request inventory is incomplete")
    rounds = _rounds(cases, system_prompt)

    files: dict[str, bytes] = {
        "README.md": _readme(len(rounds), routes).encode(),
        "pre-upload-battery.json": canonical_artifact_bytes(battery),
        "raw-streams.json": canonical_artifact_bytes(
            {
                "format_version": 1,
                "kind": "phase2-lookup-wave2-parent-candidates",
                "streams": [_raw(item) for item in executed],
            }
        ),
        "resolved-candidate-plan.json": resolved_plan_bytes,
    }
    round_manifest = []
    for ordinal, round_cases in enumerate(rounds, 1):
        name = f"round-{ordinal:03d}"
        path = f"rounds/{name}.md"
        data = _round_markdown(name, round_cases, system_prompt, f"{name}.output.jsonl")
        tokens = estimate_tokens(data)
        if tokens > _MAX_ROUND_TOKENS:
            raise LookupWave2Error(f"{name} exceeds the Chat token budget")
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
            "decision_count": len(cases),
            "format_version": 1,
            "intended_model": "GPT-5.6 Sol",
            "kind": "phase2-lookup-wave2-chat-ui-teacher-plan",
            "manual_model_attestation_required": True,
            "one_case_per_stream_per_round": True,
            "oracle_blinded_inputs": True,
            "prompt_hash": artifacts.prompt_hash,
            "reasoning": "high",
            "resolved_candidate_plan_sha256": digest(resolved_plan_bytes),
            "round_count": len(rounds),
            "rounds": round_manifest,
            "source_bindings": _source_bindings(root),
            "source_unit_count": _EXPECTED_SOURCE_UNITS,
            "static_d2_routing": {
                "review_required_count": sum(route.review_required for route in routes),
                "route_count": len(routes),
                "trust_matrix_version": _TRUST_MATRIX_VERSION,
            },
            "targets": targets,
            "teacher_transport": "chat_ui_manual",
            "wave_id": "lookup-wave-2",
        }
    )
    if any(
        b'"oracle_action"' in data or b'"teacher_action"' in data
        for name, data in files.items()
        if name.startswith("rounds/")
    ):
        raise LookupWave2Error("Chat input exposes a candidate label")
    files["SHA256SUMS"] = _checksums(files)
    return LookupWave2Packet(files, len(cases), len(rounds), len(executed))


def _routes(
    executed: tuple[_ExecutedCandidate, ...],
) -> tuple[tuple[DecisionEvidence, ...], tuple[object, ...]]:
    evidence = []
    for item in executed:
        for action, policy_seq, floor in zip(
            item.actions,
            item.decision_policy_seqs,
            item.floors,
            strict=True,
        ):
            risks = set()
            boundary = BoundaryClass.ORDINARY
            if isinstance(action, SkipAction):
                risks.add("skip_reason_selection")
                boundary = (
                    BoundaryClass.LOOKUP_REFRESH_SUPERSEDED
                    if action.reason is SkipReason.SUPERSEDED_QUERY
                    else BoundaryClass.LOOKUP_ABANDONED_STALE
                )
            if item.checkpoint:
                risks.add("rollover_or_checkpoint_projection")
            if (
                item.response_candidate_ordinal is not None
                and (
                    isinstance(action, RespondAction)
                    or isinstance(action, IdleAction)
                    and action.reason in {
                        IdleReason.AMBIGUOUS,
                        IdleReason.AWAITING_OPENING,
                    }
                )
            ):
                risks.add("active_floor_response_boundary")
                boundary = BoundaryClass.ACTIVE_FLOOR_RESPONSE
            evidence.append(
                DecisionEvidence(
                    stream_sha256=item.stream_sha256,
                    decision_policy_seq=policy_seq,
                    wave_id="lookup-wave-2",
                    cell=TrustCellKey(
                        HarnessProtocol.GENERATION,
                        item.family,
                        floor,
                    ),
                    template_id=item.template_id,
                    source_unit_id=item.source_unit_id,
                    oracle_action=action,
                    teacher_action=action,
                    causal_state_class=item.kind,
                    boundary_class=boundary,
                    risk_flags=tuple(sorted(risks)),
                    rollover=item.checkpoint,
                )
            )
    values = tuple(evidence)
    return values, route_wave(values, {}, sampling_seed="phase2-lookup-wave2-d2-v1")


def _response_assets(root: Path) -> dict[int, GeneratedResponseAsset]:
    selection_root = root / _RESPONSE_SELECTION
    _verify_directory(selection_root)
    selection = _object(selection_root / "selection.json")
    if (
        selection.get("owner_decision") != "approved"
        or selection.get("model_attestation", {}).get("status") != "owner_attested"
    ):
        raise LookupWave2Error("response selection is not owner-approved and attested")
    selected = {
        row["candidate_ordinal"]: row
        for row in selection.get("selected", [])
        if isinstance(row, dict) and isinstance(row.get("candidate_ordinal"), int)
    }
    generation_root = root / _RESPONSE_GENERATION
    _verify_directory(generation_root)
    plan = _object(generation_root / "generation-plan.json")
    planned = {
        row["candidate_ordinal"]: row
        for row in plan.get("records", [])
        if isinstance(row, dict) and isinstance(row.get("candidate_ordinal"), int)
    }
    assets = {}
    for ordinal, row in selected.items():
        source = planned[ordinal]
        request = source["neutral_request"]
        assets[ordinal] = GeneratedResponseAsset.create(
            ResponseDraftSpec(
                request["invitation"],
                _contract(request["answer_contract"]),
            ),
            teacher_visible_prefix=request["teacher_visible_prefix"],
            candidate_response=row["proposed_response"],
        )
    return assets


def _prior_stream_hashes(root: Path) -> set[str]:
    hashes = set()
    for relative in _PRIOR_PACKETS:
        packet = root / relative
        _verify_directory(packet)
        filename = (
            "raw-stream-evidence.json"
            if (packet / "raw-stream-evidence.json").exists()
            else "raw-streams.json"
        )
        raw = _object(packet / filename)
        hashes.update(
            item["stream_sha256"]
            for item in raw["streams"]
            if isinstance(item, dict) and isinstance(item.get("stream_sha256"), str)
        )
    return hashes


def _source_bindings(root: Path) -> dict[str, str]:
    return {
        "base_plan_sha256": digest((root / _BASE_PLAN / "SHA256SUMS").read_bytes()),
        "lookup_wave0_repaired_sha256": digest(
            (root / _PRIOR_PACKETS[0] / "SHA256SUMS").read_bytes()
        ),
        "lookup_wave1_repaired_sha256": digest(
            (root / _PRIOR_PACKETS[1] / "SHA256SUMS").read_bytes()
        ),
        "response_selection_sha256": digest(
            (root / _RESPONSE_SELECTION / "SHA256SUMS").read_bytes()
        ),
        "selection_contract_sha256": digest(
            (root / "spec" / "phase2-selection-v1.json").read_bytes()
        ),
    }


def _raw(item: _ExecutedCandidate) -> dict[str, object]:
    return {
        "actions": [action.model_dump(mode="json") for action in item.actions],
        "asset_ids": list(item.asset_ids),
        "family": item.family.value,
        "logical_stream_id": item.logical_stream_id,
        "response_candidate_ordinal": item.response_candidate_ordinal,
        "selected_program_action_indices": list(item.action_indices),
        "sidecar_sha256": item.sidecar_sha256,
        "source_unit_id": item.source_unit_id,
        "stream_kind": item.kind,
        "stream_sha256": item.stream_sha256,
        "template_id": item.template_id,
    }


def _case(
    custom_id: str,
    body: dict[str, object],
    target: dict[str, object],
) -> dict[str, object]:
    selected = target["candidate_selected_program_action_indices"]
    action_index = target["program_action_index"]
    assert isinstance(selected, list) and isinstance(action_index, int)
    stream = _message(body, 1)
    return {
        "candidate_ordinal": selected.index(action_index),
        "custom_id": custom_id,
        "input_sha256": digest(stream.encode()),
        "logical_stream_id": target["logical_stream_id"],
        "policy_stream": stream,
    }


def _message(body: dict[str, object], index: int) -> str:
    try:
        value = body["input"][index]["content"][0]["text"]  # type: ignore[index]
    except (IndexError, KeyError, TypeError) as error:
        raise LookupWave2Error("teacher request message shape drifted") from error
    if not isinstance(value, str):
        raise LookupWave2Error("teacher request message is not text")
    return value


def _verify_directory(directory: Path) -> None:
    for line in (directory / "SHA256SUMS").read_text().splitlines():
        checksum, separator, relative = line.partition("  ")
        if not separator or sha256((directory / relative).read_bytes()).hexdigest() != checksum:
            raise LookupWave2Error(f"bound packet changed: {directory}")


def _object(path: Path) -> dict[str, object]:
    value = json.loads(path.read_bytes())
    if not isinstance(value, dict):
        raise LookupWave2Error(f"{path.name} is not an object")
    return value


def _readme(round_count: int, routes: tuple[object, ...]) -> str:
    return f"""# WP2-3 lookup Wave-2 — offline Chat teacher packet

The repaired bulk pool contains 155 streams, 99 source units, and {_EXPECTED_DECISIONS} decisions.
The pre-upload battery ran on the final materialized streams and passed. The approved response
assets are bound without text substitution.

Upload each of the {round_count} files under `rounds/` separately in a fresh Temporary Chat using
GPT-5.6 Sol with high reasoning. Send:

`Read the attached round fully and return the requested downloadable JSONL file.`

Keep every requested output filename unchanged. Do not upload `teacher-plan.json`,
`pre-upload-battery.json`, `resolved-candidate-plan.json`, or `raw-streams.json`; they contain
local oracle and audit evidence. No API call or upload has occurred.

Static D2 routes mark {sum(route.review_required for route in routes)} decisions for review before
teacher disagreements or low-confidence outputs are added.
"""


def _checksums(files: dict[str, bytes]) -> bytes:
    return "".join(
        f"{sha256(data).hexdigest()}  {name}\n" for name, data in sorted(files.items())
    ).encode()
