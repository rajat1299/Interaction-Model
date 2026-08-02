"""Deterministic, offline TRAIN canary for the Phase 2 timer-control cluster.

Wave zero deliberately proves only the smallest branch-complete set.  It does
not select corpus rows, invoke a teacher, or imply any human approval.  The
packet retains complete parents for checkpoint shapes so the owner can inspect
the causal state that makes their later segments legal.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

from im.assets import AssetRegistry, CorpusFamily, Split, load_verified_registry_seals
from im.assets.model import (
    AssetRecord,
    TimerAssetPayload,
    canonical_artifact_bytes,
)
from im.canonical_json import parse_tim_json
from im.generation.corpus_segments import CorpusSegmentCandidate, CorpusSegmentError
from im.generation.g7_catalog import G7FamilyInputs, build_g7_timer_wave0_fresh_programs
from im.generation.g7_checkpoint_catalog import build_g7_timer_cancel_checkpoint_program
from im.generation.g7_contention_checkpoint import (
    G7_CONTENTION_CHECKPOINT_SHAPE_ID,
    build_g7_contention_checkpoint_program,
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
from im.generation.phase2_selection import load_selection_contract
from im.generation.publication import publish_directory_transaction
from im.generation.scenarios import (
    BeatStaleResults,
    DeclaredPerturbation,
    GeneratedScenario,
    ScenarioProgram,
    execute_scenario,
    validate_generated_scenario,
)
from im.generation.timing import TimingSeed, materialize_timing_plan
from im.probes.harness.models import HarnessProtocol
from im.schema.actions import (
    CancelAction,
    IdleAction,
    IdleReason,
    MarkAction,
    NudgeAction,
    ScheduleAction,
    SkipAction,
)
from im.schema.textspan import utf16_len

_REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_APPROVED_ROOT = _REPOSITORY_ROOT / "review" / "phase1" / "approved"
DEFAULT_SELECTION_CONTRACT = _REPOSITORY_ROOT / "spec" / "phase2-selection-v1.json"
DEFAULT_SENTINEL_CONTRACT = _REPOSITORY_ROOT / "spec" / "phase2-sentinel-v2.json"
DEFAULT_TIMER_WAVE0_OUTPUT = _REPOSITORY_ROOT / "review" / "phase2" / "timer-wave-0"

WAVE_ID = "timer-wave-0"
PACK_KIND = "phase2-timer-wave0-offline-packet"
_TRUST_MATRIX_VERSION = "phase2-trust-v1"
_CHECKPOINT_RISK = "rollover_or_checkpoint_projection"


class TimerWave0Error(ValueError):
    """The fixed timer wave-zero selection or packet is unsafe."""


@dataclass(frozen=True, slots=True)
class _StreamSpec:
    logical_stream_id: str
    shape_id: str
    source_unit_id: str
    family: CorpusFamily
    template_id: str
    asset_ids: tuple[str, ...]
    master_seed: str
    action_vector: str
    checkpoint: bool = False
    contextual: bool = False


@dataclass(frozen=True, slots=True)
class TimerWave0Program:
    spec: _StreamSpec
    program: ScenarioProgram


@dataclass(frozen=True, slots=True)
class ExecutedTimerWave0Stream:
    spec: _StreamSpec
    generated: GeneratedScenario
    selected_segment: CorpusSegmentCandidate | None


_SPECS = (
    _StreamSpec(
        "normal-compact-a",
        "timer-normal-compact",
        "timer-normal-compact-source-a",
        CorpusFamily.TIMER_NORMAL,
        "a_77870a0d84d3da57e4b0318d",
        ("a_067f59d6c56633412a0d45b4",),
        "phase2-timer-wave0:normal-compact:a",
        "4I+4H+6N",
    ),
    _StreamSpec(
        "normal-compact-b",
        "timer-normal-compact",
        "timer-normal-compact-source-b",
        CorpusFamily.TIMER_NORMAL,
        "a_77870a0d84d3da57e4b0318d",
        ("a_11d7f848364801c6724c9d75",),
        "phase2-timer-wave0:normal-compact:b",
        "4I+4H+6N",
        contextual=True,
    ),
    _StreamSpec(
        "normal-wide-a",
        "timer-normal-wide",
        "timer-normal-wide-source-a",
        CorpusFamily.TIMER_NORMAL,
        "a_77870a0d84d3da57e4b0318d",
        ("a_5aee644a2b2f34f90485b86f",),
        "phase2-timer-wave0:normal-wide:a",
        "3I+5H+10N",
    ),
    _StreamSpec(
        "normal-wide-b",
        "timer-normal-wide",
        "timer-normal-wide-source-b",
        CorpusFamily.TIMER_NORMAL,
        "a_77870a0d84d3da57e4b0318d",
        ("a_7fbdae8ceff9c6dc9f3fd5c6",),
        "phase2-timer-wave0:normal-wide:b",
        "3I+5H+10N",
        contextual=True,
    ),
    _StreamSpec(
        "cancel-stale-a",
        "timer-cancel-stale-fire",
        "timer-cancel-source-a",
        CorpusFamily.TIMER_CANCEL,
        "a_e35790e7d64ca17bc1e3b4d9",
        (
            "a_297508c00e4e7beb6a08d268",
            "a_8dc6c9d3ac20357c23e76ef3",
            "a_c204b0a45393ceb7122064f9",
        ),
        "phase2-timer-wave0:cancel-stale:a",
        "7I+2H+5C+2S+2N",
        checkpoint=True,
    ),
    _StreamSpec(
        "cancel-stale-b",
        "timer-cancel-stale-fire",
        "timer-cancel-source-b",
        CorpusFamily.TIMER_CANCEL,
        "a_e35790e7d64ca17bc1e3b4d9",
        (
            "a_be4de3b8613309556044650f",
            "a_5aee644a2b2f34f90485b86f",
            "a_c204b0a45393ceb7122064f9",
        ),
        "phase2-timer-wave0:cancel-stale:b",
        "7I+2H+5C+2S+2N",
        checkpoint=True,
    ),
    _StreamSpec(
        "contention-control-a",
        "timer-contention-control",
        "timer-contention-control-source-a",
        CorpusFamily.TIMER_CONTENTION,
        "a_21e7ddae34d168708913157f",
        ("a_0ef6b431c2a146d9648263aa", "a_4d9e7e5fdf179993fd3d8367"),
        "phase2-timer-wave0:contention-control:a",
        "2I+2H+2M",
    ),
    _StreamSpec(
        "contention-control-b",
        "timer-contention-control",
        "timer-contention-control-source-b",
        CorpusFamily.TIMER_CONTENTION,
        "a_21e7ddae34d168708913157f",
        ("a_47742c8fc8a3969f310ec2dc", "a_4f45803171cb2679aa272baa"),
        "phase2-timer-wave0:contention-control:b",
        "2I+2H+2M",
    ),
    _StreamSpec(
        "contention-checkpoint-a",
        G7_CONTENTION_CHECKPOINT_SHAPE_ID,
        "timer-contention-checkpoint-source-a",
        CorpusFamily.TIMER_CONTENTION,
        "a_21e7ddae34d168708913157f",
        ("a_c674f2b535fce3e1b4cfc26d",),
        "phase2-timer-wave0:contention-checkpoint:a",
        "4I+6N+2C",
        checkpoint=True,
    ),
    _StreamSpec(
        "contention-checkpoint-b",
        G7_CONTENTION_CHECKPOINT_SHAPE_ID,
        "timer-contention-checkpoint-source-b",
        CorpusFamily.TIMER_CONTENTION,
        "a_21e7ddae34d168708913157f",
        ("a_7f7137db3d888630c073d4f8",),
        "phase2-timer-wave0:contention-checkpoint:b",
        "4I+6N+2C",
        checkpoint=True,
    ),
    _StreamSpec(
        "quoted-noop-a",
        "timer-quoted-non-direct",
        "timer-quoted-source-a",
        CorpusFamily.TIMER_CANCEL,
        "a_a240fd307b1c0cd3995e7157",
        ("a_4cea8a70a0bc3d075a6d7402",),
        "phase2-timer-wave0:quoted-noop:a",
        "1I",
    ),
    _StreamSpec(
        "quoted-noop-b",
        "timer-quoted-non-direct",
        "timer-quoted-source-b",
        CorpusFamily.TIMER_CANCEL,
        "a_a240fd307b1c0cd3995e7157",
        ("a_69ad488600511102654b9745",),
        "phase2-timer-wave0:quoted-noop:b",
        "1I",
    ),
)


def load_timer_wave0_inputs(
    *,
    approved_root: Path = DEFAULT_APPROVED_ROOT,
    selection_contract_path: Path = DEFAULT_SELECTION_CONTRACT,
) -> AssetRegistry:
    """Load only the full TRAIN-sealed inputs and validate selection plumbing."""
    registry_bytes = (approved_root / "registry.jsonl").read_bytes()
    seal_names = ("test-seal.json", "demo-seal.json", "train-seal.json")
    registry, seals = load_verified_registry_seals(
        registry_bytes,
        tuple((approved_root / name).read_bytes() for name in seal_names),
        required_splits=(Split.TEST, Split.DEMO, Split.TRAIN),
    )
    train = next(seal for seal in seals if seal.split is Split.TRAIN)
    if len(train.entries) < 89:
        raise TimerWave0Error("timer wave zero requires the completed initial TRAIN seal")
    load_selection_contract(selection_contract_path)
    return registry


def build_timer_wave0_programs(registry: AssetRegistry) -> tuple[TimerWave0Program, ...]:
    """Build the closed twelve-stream TRAIN canary without executing it."""
    if not isinstance(registry, AssetRegistry):
        raise TypeError("registry must be an AssetRegistry")
    _validate_specs(registry)
    return tuple(TimerWave0Program(spec, _program_for(registry, spec)) for spec in _SPECS)


async def execute_timer_wave0(
    programs: tuple[TimerWave0Program, ...],
    *,
    directory: Path,
    repository_root: Path | None = None,
) -> tuple[ExecutedTimerWave0Stream, ...]:
    """Run each complete TRAIN parent through the production runtime."""
    if len(programs) != 12 or {item.spec.logical_stream_id for item in programs} != {
        item.logical_stream_id for item in _SPECS
    }:
        raise TimerWave0Error("timer wave-zero program inventory is not closed")
    directory.mkdir(parents=True, exist_ok=True)
    executed = []
    for item in programs:
        generated = await execute_scenario(
            item.program,
            session_id=f"{WAVE_ID}-{item.spec.logical_stream_id}",
            directory=directory / item.spec.logical_stream_id,
            repository_root=repository_root,
        )
        validate_generated_scenario(generated)
        candidate = _checkpoint_candidate(item.spec, generated)
        _validate_action_vector(item.spec, generated, candidate)
        executed.append(ExecutedTimerWave0Stream(item.spec, generated, candidate))
    return tuple(executed)


def build_timer_wave0_packet(
    executed: tuple[ExecutedTimerWave0Stream, ...],
    *,
    approved_root: Path = DEFAULT_APPROVED_ROOT,
    selection_contract_path: Path = DEFAULT_SELECTION_CONTRACT,
    sentinel_contract_path: Path = DEFAULT_SENTINEL_CONTRACT,
) -> dict[str, bytes]:
    """Render the closed offline review packet; no teacher output is accepted."""
    if len(executed) != 12 or tuple(item.spec for item in executed) != _SPECS:
        raise TimerWave0Error("packet execution inventory differs from the closed wave-zero plan")
    review_bytes, review_summary = _review_projection(executed)
    raw_evidence = {"format_version": 1, "streams": [_raw_stream(item) for item in executed]}
    manifest = _manifest(
        executed,
        approved_root=approved_root,
        selection_contract_path=selection_contract_path,
        sentinel_contract_path=sentinel_contract_path,
    )
    manifest_bytes = canonical_artifact_bytes(manifest)
    review_packet = {
        "api_call_performed": False,
        "d13_label_placeholders": review_summary,
        "format_version": 1,
        "kind": "phase2-timer-wave0-review-packet",
        "manifest_sha256": _digest(manifest_bytes),
        "owner_action_required": (
            "Perform one fast coherence scan per stream; queued decisions are evidence only."
        ),
        "stream_review_count": len(executed),
        "tranche_two_gate": {
            "blocks": [],
            "status": "complete",
            "required_additions": [],
        },
    }
    files = {
        "README.md": _readme(manifest, review_summary).encode("utf-8"),
        "manifest.json": manifest_bytes,
        "phase2-review-evidence.json": review_bytes,
        "raw-stream-evidence.json": canonical_artifact_bytes(raw_evidence),
        "review-packet.json": canonical_artifact_bytes(review_packet),
    }
    return {**files, "SHA256SUMS": _checksums(files)}


async def materialize_timer_wave0_packet(
    output: Path = DEFAULT_TIMER_WAVE0_OUTPUT,
    *,
    repository_root: Path = _REPOSITORY_ROOT,
) -> dict[str, bytes]:
    """Build, execute, validate, and create-only publish the offline packet."""
    registry = load_timer_wave0_inputs()
    programs = build_timer_wave0_programs(registry)
    with TemporaryDirectory(prefix="phase2-timer-wave0-runtime-") as temporary:
        executed = await execute_timer_wave0(
            programs,
            directory=Path(temporary),
            repository_root=repository_root,
        )
        files = build_timer_wave0_packet(executed)
    publish_directory_transaction(output, files)
    return files


def _program_for(registry: AssetRegistry, spec: _StreamSpec) -> ScenarioProgram:
    if spec.shape_id in {"timer-normal-compact", "timer-normal-wide", "timer-contention-control"}:
        normal = G7FamilyInputs(spec.template_id, spec.asset_ids)
        contention = G7FamilyInputs(
            "a_21e7ddae34d168708913157f",
            ("a_0ef6b431c2a146d9648263aa", "a_4d9e7e5fdf179993fd3d8367"),
        )
        if spec.shape_id == "timer-contention-control":
            normal = G7FamilyInputs("a_77870a0d84d3da57e4b0318d", ("a_067f59d6c56633412a0d45b4",))
            contention = G7FamilyInputs(spec.template_id, spec.asset_ids)
        outputs = dict(
            build_g7_timer_wave0_fresh_programs(
                registry,
                split=Split.TRAIN,
                normal_inputs=normal,
                contention_inputs=contention,
                master_seed=spec.master_seed,
                normal_contextual=spec.contextual,
            )
        )
        return outputs[spec.shape_id]
    if spec.shape_id == "timer-cancel-stale-fire":
        return build_g7_timer_cancel_checkpoint_program(
            registry,
            split=Split.TRAIN,
            template_id=spec.template_id,
            cancel_asset_id=spec.asset_ids[0],
            timer_asset_ids=spec.asset_ids[1:],
            master_seed=spec.master_seed,
            timing_seed="phase2-timer-cancel:431842",
        )
    if spec.shape_id == G7_CONTENTION_CHECKPOINT_SHAPE_ID:
        timer = _asset(registry, spec.asset_ids[0]).payload
        assert isinstance(timer, TimerAssetPayload) and timer.message is not None
        messages = tuple(
            f"{timer.message} beside the mint envelope on shelf {shelf}"
            for shelf in ("one", "two", "three", "four", "five", "six")
        )
        return build_g7_contention_checkpoint_program(
            registry,
            split=Split.TRAIN,
            template_id=spec.template_id,
            timer_asset_id=spec.asset_ids[0],
            master_seed=spec.master_seed,
            timing_seed="phase2-contention-checkpoint:839361",
            messages=messages,
        )
    assert spec.shape_id == "timer-quoted-non-direct"
    return _quoted_noop_program(registry, spec)


def _quoted_noop_program(registry: AssetRegistry, spec: _StreamSpec) -> ScenarioProgram:
    from im.canonical_json import canonicalize_tim_json
    from im.generation.ingestion import ScheduledSamplerFrame
    from im.generation.scenarios import select_approved_scenario_inputs

    asset = _asset(registry, spec.asset_ids[0])
    if not isinstance(asset.payload, TimerAssetPayload) or asset.payload.form.value != "quoted":
        raise TimerWave0Error("quoted no-op source must be an approved quoted timer form")
    bundle, template = select_approved_scenario_inputs(
        registry,
        split=Split.TRAIN,
        template_id=spec.template_id,
        asset_ids=spec.asset_ids,
    )
    text = asset.payload.instruction
    cursor = utf16_len(text)
    return ScenarioProgram(
        bundle=bundle,
        template=template,
        family=CorpusFamily.TIMER_CANCEL,
        master_seed=spec.master_seed,
        timing_plan=materialize_timing_plan(TimingSeed(Split.TRAIN, spec.master_seed), 1),
        frames=(
            ScheduledSamplerFrame(
                0,
                canonicalize_tim_json(
                    {
                        "text": text,
                        "selection_start": cursor,
                        "selection_end": cursor,
                        "is_composing": False,
                        "input_type": "insertText",
                        "activity": "paused",
                        "client_ts": 0,
                    }
                ),
            ),
        ),
        actions=(
            IdleAction(
                type="idle",
                reason=IdleReason.INSTRUCTION_NOT_DIRECT,
                related_event_id=None,
            ),
        ),
        tool_results=(),
        beat_ids=("b0",),
        stale_results_by_beat=(BeatStaleResults("b0", ()),),
        perturbations=(DeclaredPerturbation("timer_cancel_race"),),
    )


def _checkpoint_candidate(
    spec: _StreamSpec, generated: GeneratedScenario
) -> CorpusSegmentCandidate | None:
    if not spec.checkpoint:
        return None
    expected = (
        (
            CancelAction,
            IdleAction,
            CancelAction,
            IdleAction,
            CancelAction,
            IdleAction,
            IdleAction,
            CancelAction,
            ScheduleAction,
            SkipAction,
            NudgeAction,
            IdleAction,
            NudgeAction,
            IdleAction,
            ScheduleAction,
            CancelAction,
            SkipAction,
            IdleAction,
        )
        if spec.shape_id == "timer-cancel-stale-fire"
        else (
            *(IdleAction for _ in range(3)),
            *(NudgeAction for _ in range(6)),
            *(CancelAction for _ in range(2)),
            IdleAction,
        )
    )
    matches = []
    for index in range(1, len(generated.stream.segments)):
        try:
            candidate = CorpusSegmentCandidate(generated, index, spec.shape_id)
        except CorpusSegmentError:
            continue
        if tuple(type(action) for action in candidate.selected_actions) == expected:
            matches.append(candidate)
    if len(matches) != 1:
        raise TimerWave0Error(f"{spec.logical_stream_id} has no unique later checkpoint segment")
    return matches[0]


def _validate_specs(registry: AssetRegistry) -> None:
    if len(_SPECS) != 12 or len({spec.logical_stream_id for spec in _SPECS}) != 12:
        raise TimerWave0Error("timer wave-zero must have exactly twelve unique streams")
    pool = registry.pool(Split.TRAIN)
    by_id = {item.asset_id: item for item in (*pool.assets, *pool.templates)}
    for spec in _SPECS:
        template = by_id.get(spec.template_id)
        if (
            template is None
            or not registry.is_approved(template)
            or spec.family not in template.coverage
        ):
            raise TimerWave0Error(
                f"{spec.logical_stream_id} template is not approved for its family"
            )
        if not spec.asset_ids or any(
            (asset := by_id.get(asset_id)) is None
            or not registry.is_approved(asset)
            or asset not in pool.assets
            for asset_id in spec.asset_ids
        ):
            raise TimerWave0Error(f"{spec.logical_stream_id} has an unapproved TRAIN source")
        if not any(spec.family in by_id[asset_id].coverage for asset_id in spec.asset_ids):
            raise TimerWave0Error(f"{spec.logical_stream_id} lacks a family-covered source")


def _validate_action_vector(
    spec: _StreamSpec,
    generated: GeneratedScenario,
    candidate: CorpusSegmentCandidate | None,
) -> None:
    actions = generated.program.actions if candidate is None else candidate.selected_actions
    if _vector_counts(actions) != _parse_vector(spec.action_vector):
        raise TimerWave0Error(f"{spec.logical_stream_id} action vector drifted")
    if spec.shape_id == "timer-quoted-non-direct":
        (action,) = actions
        if (
            not isinstance(action, IdleAction)
            or action.reason is not IdleReason.INSTRUCTION_NOT_DIRECT
        ):
            raise TimerWave0Error("quoted branch no longer remains non-direct")


def _review_projection(
    executed: tuple[ExecutedTimerWave0Stream, ...],
) -> tuple[bytes, dict[str, object]]:
    decisions = []
    for item in executed:
        candidate = item.selected_segment
        checkpoint = candidate is not None
        selected = (
            enumerate(item.generated.program.actions)
            if candidate is None
            else zip(
                (call_index - 1 for call_index in candidate.selected_call_indices),
                candidate.selected_actions,
                strict=True,
            )
        )
        for policy_seq, action in selected:
            decisions.append(
                DecisionEvidence(
                    stream_sha256=item.generated.stream.sha256,
                    decision_policy_seq=policy_seq,
                    wave_id=WAVE_ID,
                    cell=TrustCellKey(
                        HarnessProtocol.GENERATION,
                        item.spec.family,
                        FloorClass.CLOSED,
                    ),
                    template_id=item.generated.program.template.asset_id,
                    source_unit_id=item.spec.source_unit_id,
                    oracle_action=action,
                    teacher_action=None,
                    causal_state_class=item.spec.shape_id,
                    boundary_class=BoundaryClass.ORDINARY,
                    risk_flags=(_CHECKPOINT_RISK,) if checkpoint else (),
                    rollover=checkpoint,
                )
            )
    route = route_wave(tuple(decisions), {}, sampling_seed="phase2-timer-wave0-review-v1")
    if not all(item.review_required for item in route):
        raise TimerWave0Error("wave zero may not auto-admit an unreviewed decision")
    inputs = tuple(
        DecisionProjectionInput(
            decision=decision,
            route=review,
            oracle_license=CandidateLicense("licensed", ()),
            teacher_license=None,
            oracle_provenance={
                "sidecar_sha256": executed[
                    _stream_index(executed, decision.stream_sha256)
                ].generated.sidecar.sha256,
                "stream_sha256": decision.stream_sha256,
            },
            teacher_provenance=None,
            priority_rank=index,
        )
        for index, (decision, review) in enumerate(zip(decisions, route, strict=True))
    )
    evidence = project_phase2_review_evidence(
        inputs,
        packet_decision_identities=tuple(
            (decision.stream_sha256, decision.decision_policy_seq) for decision in decisions
        ),
        teacher_evidence_identity=_digest(b"phase2-timer-wave0-v1:no-teacher-evidence"),
        blind_seed="phase2-timer-wave0-blind-v1",
    )
    return evidence, {
        "all_labels_pending_human_review": True,
        "decision_count": len(decisions),
        "label_origin": None,
        "review_batch_id": None,
        "route_count": len(route),
        "trust_matrix_version": _TRUST_MATRIX_VERSION,
    }


def _stream_index(executed: tuple[ExecutedTimerWave0Stream, ...], stream_sha256: str) -> int:
    for index, item in enumerate(executed):
        if item.generated.stream.sha256 == stream_sha256:
            return index
    raise TimerWave0Error("review decision refers to an unknown executed stream")


def _manifest(
    executed: tuple[ExecutedTimerWave0Stream, ...],
    *,
    approved_root: Path,
    selection_contract_path: Path,
    sentinel_contract_path: Path,
) -> dict[str, object]:
    registry_bytes = (approved_root / "registry.jsonl").read_bytes()
    train_seal = (approved_root / "train-seal.json").read_bytes()
    sentinel = _canonical_object(sentinel_contract_path.read_bytes(), "sentinel contract")
    sentinel_targets = {
        item["target_id"]: item
        for item in sentinel.get("targets", [])
        if isinstance(item, dict) and isinstance(item.get("target_id"), str)
    }
    required = ("schedule_semantic_duplicate", "ambiguous_cancel")
    if not all(name in sentinel_targets for name in required):
        raise TimerWave0Error("sentinel contract no longer binds the timer boundary references")
    return {
        "api_call_performed": False,
        "format_version": 1,
        "kind": PACK_KIND,
        "selection_contract_sha256": _digest(selection_contract_path.read_bytes()),
        "sentinel_bindings": {
            "contract_path": sentinel_contract_path.relative_to(_REPOSITORY_ROOT).as_posix(),
            "contract_sha256": _digest(sentinel_contract_path.read_bytes()),
            "references": [
                {
                    "boundary_class": sentinel_targets[name]["boundary_class"],
                    "logical_stream_id": sentinel_targets[name]["logical_stream_id"],
                    "target_id": name,
                }
                for name in required
            ],
        },
        "source_registry_sha256": _digest(registry_bytes),
        "train_seal_sha256": _digest(train_seal),
        "tranche_two_status": "13_approved_and_sealed",
        "wave_id": WAVE_ID,
        "streams": [_manifest_stream(item) for item in executed],
    }


def _manifest_stream(item: ExecutedTimerWave0Stream) -> dict[str, object]:
    program = item.generated.program
    return {
        "action_vector": item.spec.action_vector,
        "asset_ids": list(program.asset_ids),
        "asset_sha256s": [asset.content_sha256 for asset in program.bundle.assets],
        "checkpoint_segment": (
            None
            if item.selected_segment is None
            else {
                "selected_call_indices": list(item.selected_segment.selected_call_indices),
                "segment_index": item.selected_segment.segment_index,
                "segment_sha256": item.selected_segment.segment.sha256,
            }
        ),
        "family": item.spec.family.value,
        "logical_stream_id": item.spec.logical_stream_id,
        "master_seed": program.master_seed,
        "shape_id": item.spec.shape_id,
        "source_unit_id": item.spec.source_unit_id,
        "stream_sha256": item.generated.stream.sha256,
        "template_id": program.template.asset_id,
        "template_sha256": program.template.content_sha256,
        "timing": {
            "class": program.timing_plan.stream_class.value,
            "population": program.timing_plan.population.value,
            "profile_id": program.timing_plan.profile_id,
            "seed": program.timing_plan.seed.seed,
            "seed_id": program.timing_plan.seed.timing_seed_id,
            "split": program.timing_plan.seed.split.value,
        },
    }


def _raw_stream(item: ExecutedTimerWave0Stream) -> dict[str, object]:
    generated = item.generated
    candidate = item.selected_segment
    return {
        "actions": [action.model_dump(mode="json") for action in generated.program.actions],
        "decision_boundaries": [
            {
                "call_index": boundary.call_index,
                "policy_prefix_sha256": _digest(boundary.policy_bytes),
            }
            for boundary in generated.decision_boundaries
        ],
        "frames": [
            {"at_ms": frame.at_ms, "sampler": parse_tim_json(frame.raw_bytes)}
            for frame in generated.program.frames
        ],
        "logical_stream_id": item.spec.logical_stream_id,
        "segments": [
            {
                "policy_bytes_utf8": segment.policy_bytes.decode("utf-8"),
                "segment_sha256": segment.sha256,
            }
            for segment in generated.stream.segments
        ],
        "selected_checkpoint": (
            None
            if candidate is None
            else {
                "actions": [
                    action.model_dump(mode="json") for action in candidate.selected_actions
                ],
                "selected_call_indices": list(candidate.selected_call_indices),
                "segment_index": candidate.segment_index,
                "segment_sha256": candidate.segment.sha256,
            }
        ),
        "sidecar": generated.sidecar.as_json_object(),
        "stream_sha256": generated.stream.sha256,
    }


def _asset(registry: AssetRegistry, asset_id: str) -> AssetRecord:
    pool = registry.pool(Split.TRAIN)
    asset = next(
        (item for item in (*pool.assets, *pool.templates) if item.asset_id == asset_id),
        None,
    )
    if asset is None:
        raise TimerWave0Error(f"TRAIN asset {asset_id} is absent")
    return asset


def _vector_counts(actions: tuple[object, ...]) -> Counter[str]:
    names = {
        IdleAction: "I",
        ScheduleAction: "H",
        NudgeAction: "N",
        CancelAction: "C",
        SkipAction: "S",
        MarkAction: "M",
    }
    counts = Counter(names[type(action)] for action in actions)
    return counts


def _parse_vector(value: str) -> Counter[str]:
    counts: Counter[str] = Counter()
    for part in value.split("+"):
        count, action = part[:-1], part[-1:]
        if action not in {"I", "H", "C", "S", "N", "M"} or not count.isdigit():
            raise TimerWave0Error("wave-zero action-vector specification is malformed")
        counts[action] = int(count)
    return counts


def _checksums(files: dict[str, bytes]) -> bytes:
    lines = (f"{sha256(files[name]).hexdigest()}  {name}\n" for name in sorted(files))
    return "".join(lines).encode("ascii")


def _digest(data: bytes) -> str:
    return f"sha256:{sha256(data).hexdigest()}"


def _canonical_object(data: bytes, label: str) -> dict[str, object]:
    canonical = data.removesuffix(b"\n")
    try:
        value = json.loads(canonical)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise TimerWave0Error(f"{label} is not JSON") from error
    if not isinstance(value, dict) or canonical_artifact_bytes(value) != canonical:
        raise TimerWave0Error(f"{label} is not canonical JSON")
    return value


def _readme(manifest: dict[str, object], review: dict[str, object]) -> str:
    return "\n".join(
        (
            "# Phase 2 timer wave-0 offline packet",
            "",
            "Outcome: execute the smallest TRAIN-sealed timer-control slice before scale-up.",
            "",
            "Hypothesis: the 12 fixed streams preserve G7 causal evidence for normal fires,",
            "direct cancellation/stale-fire handling, contention, and quoted non-direct restraint.",
            "",
            "Prediction: every stream validates mechanically and every decision remains queued for",
            "human review; no teacher/provider request or approval is performed.",
            "",
            f"Streams: {len(manifest['streams'])}; stream-level coherence scans: "
            f"{len(manifest['streams'])}.",
            f"Queued oracle decisions retained as evidence: {review['decision_count']}.",
            "",
            "Semantic-duplicate scheduling remains bound to the executable sentinel. The separate",
            "six-row boundary companion covers tranche-2 ambiguity, negation, and unsupported",
            "forms. All 13 targeted records are owner-approved and TRAIN-sealed.",
            "",
        )
    )
