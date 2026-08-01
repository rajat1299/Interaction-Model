"""Smallest branch-complete offline TRAIN proof for the WP2-3 lookup cluster."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

from im.assets import AssetRegistry, CorpusFamily, Split
from im.assets.model import LookupAssetPayload, canonical_artifact_bytes
from im.canonical_json import parse_tim_json
from im.generation.corpus_segments import CorpusSegmentCandidate, CorpusSegmentError
from im.generation.g7_catalog import G7FamilyInputs, build_g7_lookup_live_program
from im.generation.g7_checkpoint_catalog import build_g7_lookup_checkpoint_program
from im.generation.packaging import PackageManifest
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
from im.generation.phase2_timer_wave0 import load_timer_wave0_inputs
from im.generation.publication import publish_directory_transaction
from im.generation.scenarios import (
    GeneratedScenario,
    ScenarioProgram,
    execute_scenario,
    validate_generated_scenario,
)
from im.probes.harness.models import HarnessProtocol
from im.schema.actions import (
    DelegateAction,
    IntegrateAction,
    SkipAction,
    SkipReason,
)

_REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_APPROVED_ROOT = _REPOSITORY_ROOT / "review" / "phase1" / "approved"
DEFAULT_SELECTION_CONTRACT = _REPOSITORY_ROOT / "spec" / "phase2-selection-v1.json"
DEFAULT_LOOKUP_WAVE0_OUTPUT = _REPOSITORY_ROOT / "review" / "phase2" / "lookup-wave-0"

WAVE_ID = "lookup-wave-0"
PACK_KIND = "phase2-lookup-wave0-offline-packet"
_TRUST_MATRIX_VERSION = "phase2-trust-v1"
_CHECKPOINT_RISK = "rollover_or_checkpoint_projection"
_SKIP_RISK = "skip_reason_selection"

_DUPLICATE_A_TYPES = (
    "idle",
    "idle",
    "idle",
    "idle",
    "idle",
    "integrate",
    "delegate",
    "integrate",
    "delegate",
    "skip",
    "idle",
)
_DUPLICATE_B_TYPES = (
    "idle",
    "idle",
    "idle",
    "idle",
    "idle",
    "delegate",
    "delegate",
    "delegate",
    "idle",
    "skip",
    "skip",
    "integrate",
    "idle",
)
_STALE_TYPES = ("idle", "idle", "skip", "skip", "skip", "skip", "skip", "idle")


class LookupWave0Error(ValueError):
    """The fixed lookup Wave-0 inventory or evidence is invalid."""


@dataclass(frozen=True, slots=True)
class _StreamSpec:
    logical_stream_id: str
    shape_id: str
    source_unit_id: str
    family: CorpusFamily
    template_id: str
    lookup_asset_ids: tuple[str, ...]
    text_asset_ids: tuple[str, ...]
    master_seed: str
    primary_lookup_asset_id: str | None = None
    selected_types: tuple[str, ...] | None = None

    @property
    def checkpoint(self) -> bool:
        return self.selected_types is not None


@dataclass(frozen=True, slots=True)
class LookupWave0Program:
    spec: _StreamSpec
    program: ScenarioProgram


@dataclass(frozen=True, slots=True)
class ExecutedLookupWave0Stream:
    spec: _StreamSpec
    generated: GeneratedScenario
    selected_segment: CorpusSegmentCandidate | None


_SPECS = (
    _StreamSpec(
        "live-fresh-a",
        "lookup-live",
        "lookup-live-source-a",
        CorpusFamily.LOOKUP_LIVE,
        "a_93beb83846363b159a8f8f67",
        ("a_7960c7b84f8755e53ee4941e", "a_0c280681c3a090e5c4901abd"),
        (),
        "phase2-lookup-wave0:live:a",
    ),
    _StreamSpec(
        "live-fresh-b",
        "lookup-live",
        "lookup-live-source-b",
        CorpusFamily.LOOKUP_LIVE,
        "a_93beb83846363b159a8f8f67",
        ("a_1cf8a5df42e379dcb0fc2472", "a_12a569c4e22df60dcf02afba"),
        (),
        "phase2-lookup-wave0:live:b",
    ),
    _StreamSpec(
        "duplicate-replacement-a",
        "g7-checkpoint-lookup-duplicate-a",
        "lookup-duplicate-a-source-a",
        CorpusFamily.LOOKUP_DUPLICATE,
        "a_0c05ad0e07dcb3adfcea1ca1",
        (
            "a_8c0437dc190d45e10531aef6",
            "a_9cb5bcdbda0a0ab215869885",
            "a_99ff6eea712fcf4cdf3052d8",
            "a_20768c51f96d20c7f5824e31",
        ),
        ("a_0a86fd6dd35ddf5743c1f5c1", "a_1fac3cb0c0ab2e4c3274ce17"),
        "phase2-lookup-wave0:duplicate-a:1",
        "a_8c0437dc190d45e10531aef6",
        _DUPLICATE_A_TYPES,
    ),
    _StreamSpec(
        "duplicate-replacement-b",
        "g7-checkpoint-lookup-duplicate-a",
        "lookup-duplicate-a-source-b",
        CorpusFamily.LOOKUP_DUPLICATE,
        "a_0c05ad0e07dcb3adfcea1ca1",
        (
            "a_fcc686f6168c2583bf7c4875",
            "a_23b3d0a6cc4216d09016c9c2",
            "a_1d2adb2b20a4058e6ade6fa8",
            "a_51585c013e336c7b96dcb9ea",
        ),
        ("a_925e8f56a405335c1622ab7c", "a_a84c08c816ea620b935c58fa"),
        "phase2-lookup-wave0:duplicate-a:2",
        "a_fcc686f6168c2583bf7c4875",
        _DUPLICATE_A_TYPES,
    ),
    _StreamSpec(
        "duplicate-abandonment-a",
        "g7-checkpoint-lookup-duplicate-b",
        "lookup-duplicate-b-source-a",
        CorpusFamily.LOOKUP_DUPLICATE,
        "a_0c05ad0e07dcb3adfcea1ca1",
        (
            "a_9d103897ae0a9bd144c20317",
            "a_adeb16c7dd41c777848bda5d",
            "a_b1fdb6410d66f0c129caaabf",
        ),
        ("a_bac0d5ac8c3be1075ff65976", "a_d0a35f5f140d791a52af02fa"),
        "phase2-lookup-wave0:duplicate-b:1",
        "a_9d103897ae0a9bd144c20317",
        _DUPLICATE_B_TYPES,
    ),
    _StreamSpec(
        "duplicate-abandonment-b",
        "g7-checkpoint-lookup-duplicate-b",
        "lookup-duplicate-b-source-b",
        CorpusFamily.LOOKUP_DUPLICATE,
        "a_0c05ad0e07dcb3adfcea1ca1",
        (
            "a_51405b13e0ed8b68a36e30ca",
            "a_b48a45684dfbda39d18a4593",
            "a_454be9498f422c97c29f0eba",
        ),
        ("a_f9de5705e1b34cc0980d8fb8", "a_0a86fd6dd35ddf5743c1f5c1"),
        "phase2-lookup-wave0:duplicate-b:2",
        "a_51405b13e0ed8b68a36e30ca",
        _DUPLICATE_B_TYPES,
    ),
    _StreamSpec(
        "stale-refresh-a",
        "g7-checkpoint-lookup-stale",
        "lookup-stale-source-a",
        CorpusFamily.LOOKUP_STALE,
        "a_dd5c4e7300588ffc83ce7bb2",
        (
            "a_efabb862b744596e6c7369aa",
            "a_9da25dd83e75a6af3a18823c",
            "a_bc0c6abcb2b7aa943ed3bd0c",
            "a_5d37f24ad969004441c6e3dd",
        ),
        ("a_1fac3cb0c0ab2e4c3274ce17", "a_925e8f56a405335c1622ab7c"),
        "phase2-lookup-wave0:stale:1",
        "a_efabb862b744596e6c7369aa",
        _STALE_TYPES,
    ),
    _StreamSpec(
        "stale-refresh-b",
        "g7-checkpoint-lookup-stale",
        "lookup-stale-source-b",
        CorpusFamily.LOOKUP_STALE,
        "a_dd5c4e7300588ffc83ce7bb2",
        (
            "a_f69d2349f61b400e204460b6",
            "a_4d235a01aeab61806b36d016",
            "a_2861ef1e5f1afc8e8257e78e",
            "a_9b4d08db0b81ec451ad91397",
        ),
        ("a_a84c08c816ea620b935c58fa", "a_bac0d5ac8c3be1075ff65976"),
        "phase2-lookup-wave0:stale:2",
        "a_f69d2349f61b400e204460b6",
        _STALE_TYPES,
    ),
)


def load_lookup_wave0_inputs() -> AssetRegistry:
    """Load the same complete TRAIN-sealed registry used by timer Wave-0."""
    registry = load_timer_wave0_inputs()
    load_selection_contract(DEFAULT_SELECTION_CONTRACT)
    return registry


def build_lookup_wave0_programs(
    registry: AssetRegistry,
) -> tuple[LookupWave0Program, ...]:
    """Build the fixed eight-stream offline proof without invoking a teacher."""
    if not isinstance(registry, AssetRegistry):
        raise TypeError("registry must be an AssetRegistry")
    _validate_specs(registry)
    return tuple(LookupWave0Program(spec, _program_for(registry, spec)) for spec in _SPECS)


async def execute_lookup_wave0(
    programs: tuple[LookupWave0Program, ...],
    *,
    directory: Path,
    repository_root: Path | None = None,
) -> tuple[ExecutedLookupWave0Stream, ...]:
    """Execute every complete parent and select the intended later checkpoint segment."""
    if tuple(item.spec for item in programs) != _SPECS:
        raise LookupWave0Error("lookup Wave-0 program inventory is not closed")
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
        selected = _checkpoint_candidate(item.spec, generated)
        _validate_stream(item.spec, generated, selected)
        executed.append(ExecutedLookupWave0Stream(item.spec, generated, selected))
    return tuple(executed)


def build_lookup_wave0_packet(
    executed: tuple[ExecutedLookupWave0Stream, ...],
    *,
    approved_root: Path = DEFAULT_APPROVED_ROOT,
    selection_contract_path: Path = DEFAULT_SELECTION_CONTRACT,
) -> dict[str, bytes]:
    """Render the checksum-bound, provider-free owner review packet."""
    if tuple(item.spec for item in executed) != _SPECS:
        raise LookupWave0Error("packet execution inventory differs from the fixed plan")
    review_bytes, review_summary = _review_projection(executed)
    manifest_bytes = PackageManifest.build(
        item.generated for item in executed
    ).canonical_bytes
    review_packet = {
        "api_call_performed": False,
        "d13_label_placeholders": review_summary,
        "format_version": 1,
        "kind": PACK_KIND,
        "manifest_sha256": _digest(manifest_bytes),
        "owner_action_required": (
            "Review each interaction as a user: start explicit lookups once, show live results, "
            "and ignore results only when their request was replaced or abandoned."
        ),
        "selection_contract_sha256": _digest(selection_contract_path.read_bytes()),
        "source_registry_sha256": _digest((approved_root / "registry.jsonl").read_bytes()),
        "stream_review_count": len(executed),
        "train_seal_sha256": _digest((approved_root / "train-seal.json").read_bytes()),
    }
    raw = {"format_version": 1, "streams": [_raw_stream(item) for item in executed]}
    files = {
        "README.md": _readme(review_summary).encode(),
        "REVIEW.md": _review_guide().encode(),
        "manifest.json": manifest_bytes,
        "source-index.json": canonical_artifact_bytes(_source_index(executed)),
        "phase2-review-evidence.json": review_bytes,
        "raw-stream-evidence.json": canonical_artifact_bytes(raw),
        "review-packet.json": canonical_artifact_bytes(review_packet),
        **_runtime_files(executed),
    }
    return {**files, "SHA256SUMS": _checksums(files)}


async def materialize_lookup_wave0_packet(
    output: Path = DEFAULT_LOOKUP_WAVE0_OUTPUT,
    *,
    repository_root: Path = _REPOSITORY_ROOT,
) -> dict[str, bytes]:
    """Build, execute, validate, and create-only publish the offline packet."""
    programs = build_lookup_wave0_programs(load_lookup_wave0_inputs())
    with TemporaryDirectory(prefix="phase2-lookup-wave0-runtime-") as temporary:
        executed = await execute_lookup_wave0(
            programs,
            directory=Path(temporary),
            repository_root=repository_root,
        )
        files = build_lookup_wave0_packet(executed)
    publish_directory_transaction(output, files)
    return files


def _program_for(registry: AssetRegistry, spec: _StreamSpec) -> ScenarioProgram:
    if not spec.checkpoint:
        return build_g7_lookup_live_program(
            registry,
            split=Split.TRAIN,
            inputs=G7FamilyInputs(spec.template_id, spec.lookup_asset_ids),
            master_seed=spec.master_seed,
        )
    assert spec.primary_lookup_asset_id is not None
    return build_g7_lookup_checkpoint_program(
        registry,
        split=Split.TRAIN,
        shape_id=spec.shape_id,
        template_id=spec.template_id,
        primary_lookup_asset_id=spec.primary_lookup_asset_id,
        lookup_asset_ids=spec.lookup_asset_ids,
        text_asset_ids=(spec.text_asset_ids[0], spec.text_asset_ids[1]),
        master_seed=spec.master_seed,
    )


def _checkpoint_candidate(
    spec: _StreamSpec,
    generated: GeneratedScenario,
) -> CorpusSegmentCandidate | None:
    if spec.selected_types is None:
        return None
    matches = []
    for index in range(1, len(generated.stream.segments)):
        try:
            candidate = CorpusSegmentCandidate(generated, index, spec.shape_id)
        except CorpusSegmentError:
            continue
        if tuple(action.type for action in candidate.selected_actions) == spec.selected_types:
            matches.append(candidate)
    if len(matches) != 1:
        raise LookupWave0Error(f"{spec.logical_stream_id} lacks one exact checkpoint segment")
    return matches[0]


def _selected_actions(
    generated: GeneratedScenario,
    candidate: CorpusSegmentCandidate | None,
) -> tuple[object, ...]:
    return generated.program.actions if candidate is None else candidate.selected_actions


def _validate_stream(
    spec: _StreamSpec,
    generated: GeneratedScenario,
    candidate: CorpusSegmentCandidate | None,
) -> None:
    program = generated.program
    actions = _selected_actions(generated, candidate)
    if program.bundle.split is not Split.TRAIN or program.family is not spec.family:
        raise LookupWave0Error(f"{spec.logical_stream_id} escaped its TRAIN family")
    if spec.selected_types is not None and tuple(action.type for action in actions) != (
        spec.selected_types
    ):
        raise LookupWave0Error(f"{spec.logical_stream_id} checkpoint action vector drifted")
    frames = tuple(parse_tim_json(frame.raw_bytes)["text"] for frame in program.frames)
    delegates = tuple(action for action in program.actions if isinstance(action, DelegateAction))
    if not all(
        action.fact.text == action.args.query
        and any(
            action.args.query in frame
            and ("look up" in frame.lower() or "refresh" in frame.lower())
            for frame in frames
        )
        for action in delegates
    ):
        raise LookupWave0Error(f"{spec.logical_stream_id} contains an implicit lookup request")
    approved_results = {
        result
        for asset in program.bundle.assets
        if isinstance(asset.payload, LookupAssetPayload)
        for result in (asset.payload.result_a, asset.payload.result_b)
    }
    results = tuple(result.data for result in program.tool_results)
    if len(results) != len(delegates) or not all(
        isinstance(result, dict)
        and isinstance(result.get("nonce"), str)
        and (
            result["nonce"] in approved_results
            or (
                result["nonce"].startswith(f"{delegate.args.query}: ")
                and any(value in result["nonce"] for value in approved_results)
            )
        )
        for delegate, result in zip(delegates, results, strict=True)
    ):
        raise LookupWave0Error(f"{spec.logical_stream_id} contains an unapproved result")
    integrations = tuple(
        action for action in program.actions if isinstance(action, IntegrateAction)
    )
    if not all(action.text in approved_results for action in integrations):
        raise LookupWave0Error(f"{spec.logical_stream_id} has an unapproved integration")
    if any(
        action.text.startswith(f"{delegate.args.query}: ")
        for action in integrations
        for delegate in delegates
    ):
        raise LookupWave0Error(f"{spec.logical_stream_id} exposes a raw query prefix")
    reasons = Counter(
        action.reason for action in program.actions if isinstance(action, SkipAction)
    )
    expected = {
        "lookup-live": Counter(),
        "g7-checkpoint-lookup-duplicate-a": Counter({SkipReason.SUPERSEDED_QUERY: 1}),
        "g7-checkpoint-lookup-duplicate-b": Counter({SkipReason.STALE_TOOL_RESULT: 2}),
        "g7-checkpoint-lookup-stale": Counter(
            {SkipReason.SUPERSEDED_QUERY: 1, SkipReason.STALE_TOOL_RESULT: 5}
        ),
    }[spec.shape_id]
    if reasons != expected:
        raise LookupWave0Error(f"{spec.logical_stream_id} skip semantics drifted")


def _validate_specs(registry: AssetRegistry) -> None:
    if len(_SPECS) != 8 or len({spec.logical_stream_id for spec in _SPECS}) != 8:
        raise LookupWave0Error("lookup Wave-0 must contain eight unique streams")
    pool = registry.pool(Split.TRAIN)
    by_id = {item.asset_id: item for item in (*pool.assets, *pool.templates)}
    for spec in _SPECS:
        ids = (spec.template_id, *spec.lookup_asset_ids, *spec.text_asset_ids)
        if any(
            asset_id not in by_id or not registry.is_approved(by_id[asset_id])
            for asset_id in ids
        ):
            raise LookupWave0Error(f"{spec.logical_stream_id} uses an unapproved TRAIN source")
        if spec.family not in by_id[spec.template_id].coverage:
            raise LookupWave0Error(f"{spec.logical_stream_id} template family is wrong")
        if not any(spec.family in by_id[asset_id].coverage for asset_id in spec.lookup_asset_ids):
            raise LookupWave0Error(f"{spec.logical_stream_id} lacks a family-covered lookup")


def _review_projection(
    executed: tuple[ExecutedLookupWave0Stream, ...],
) -> tuple[bytes, dict[str, object]]:
    decisions = []
    for item in executed:
        candidate = item.selected_segment
        selected = (
            enumerate(item.generated.program.actions)
            if candidate is None
            else zip(
                (call_index - 1 for call_index in candidate.selected_call_indices),
                candidate.selected_actions,
                strict=True,
            )
        )
        for program_index, action in selected:
            policy_seq = item.generated.sidecar.decisions[
                program_index
            ].observed_policy_seq
            boundary = BoundaryClass.ORDINARY
            risks = [_CHECKPOINT_RISK] if candidate is not None else []
            if isinstance(action, SkipAction):
                boundary = (
                    BoundaryClass.LOOKUP_REFRESH_SUPERSEDED
                    if action.reason is SkipReason.SUPERSEDED_QUERY
                    else BoundaryClass.LOOKUP_ABANDONED_STALE
                )
                risks.append(_SKIP_RISK)
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
                    boundary_class=boundary,
                    risk_flags=tuple(sorted(risks)),
                    rollover=candidate is not None,
                )
            )
    route = route_wave(tuple(decisions), {}, sampling_seed="phase2-lookup-wave0-review-v1")
    if len(decisions) != 76 or not all(item.review_required for item in route):
        raise LookupWave0Error("lookup Wave-0 must route all 76 decisions to owner review")
    by_stream = {
        item.generated.stream.sha256: item.generated.sidecar.sha256 for item in executed
    }
    projected = project_phase2_review_evidence(
        tuple(
            DecisionProjectionInput(
                decision=decision,
                route=review,
                oracle_license=CandidateLicense("licensed", ()),
                teacher_license=None,
                oracle_provenance={
                    "sidecar_sha256": by_stream[decision.stream_sha256],
                    "stream_sha256": decision.stream_sha256,
                },
                teacher_provenance=None,
                priority_rank=index,
            )
            for index, (decision, review) in enumerate(zip(decisions, route, strict=True))
        ),
        packet_decision_identities=tuple(
            (decision.stream_sha256, decision.decision_policy_seq) for decision in decisions
        ),
        teacher_evidence_identity=_digest(b"phase2-lookup-wave0-v1:no-teacher-evidence"),
        blind_seed="phase2-lookup-wave0-blind-v1",
    )
    return projected, {
        "all_labels_pending_human_review": True,
        "decision_count": len(decisions),
        "label_origin": None,
        "review_batch_id": None,
        "route_count": len(route),
        "trust_matrix_version": _TRUST_MATRIX_VERSION,
    }


def _runtime_files(
    executed: tuple[ExecutedLookupWave0Stream, ...],
) -> dict[str, bytes]:
    files: dict[str, bytes] = {}
    for item in executed:
        generated = item.generated
        stream = generated.stream.sha256.removeprefix("sha256:")
        for segment in generated.stream.segments:
            segment_hash = segment.sha256.removeprefix("sha256:")
            files[f"teacher/{stream}/{segment_hash}.jsonl"] = segment.policy_bytes
        files[f"reviewer/{stream}/sidecar.json"] = generated.sidecar.canonical_bytes
        files[f"reviewer/{stream}/runtime-ledger.json"] = (
            generated.stream.final_ledger.canonical_bytes
        )
        candidate = item.selected_segment
        if candidate is not None:
            files[f"reviewer/{stream}/checkpoint-selection.json"] = (
                canonical_artifact_bytes(
                    {
                        "checkpoint_seq": candidate.checkpoint_seq,
                        "format_version": 1,
                        "parent_sidecar_sha256": generated.sidecar.sha256,
                        "parent_stream_sha256": generated.stream.sha256,
                        "previous_segment_hash": candidate.previous_segment_hash,
                        "segment_index": candidate.segment_index,
                        "segment_sha256": candidate.segment.sha256,
                        "selected_call_indices": list(candidate.selected_call_indices),
                    }
                )
            )
    return files


def _source_index(
    executed: tuple[ExecutedLookupWave0Stream, ...],
) -> dict[str, object]:
    return {
        "batch": 1,
        "format_version": 1,
        "source_identity_rule": "one complete regenerated runtime parent per lookup source unit",
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
                "role": "lookup_wave0_runtime_parent",
                "shape_id": item.spec.shape_id,
                "sidecar_sha256s": [item.generated.sidecar.sha256],
                "source_decision_counts": [
                    len(_selected_actions(item.generated, item.selected_segment))
                ],
                "source_kind": (
                    "runtime_parent"
                    if item.selected_segment is None
                    else "checkpoint_segment"
                ),
                "source_unit_id": item.spec.source_unit_id,
            }
            for item in executed
        ],
    }


def _raw_stream(item: ExecutedLookupWave0Stream) -> dict[str, object]:
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
                "policy_bytes_utf8": segment.policy_bytes.decode(),
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


def _readme(review: dict[str, object]) -> str:
    return "\n".join(
        (
            "# Phase 2 lookup Wave-0 offline packet",
            "",
            "Outcome: prove the smallest TRAIN lookup slice before any teacher or bulk generation.",
            "",
            "Hypothesis: explicit lookup requests are started once; fresh results are shown with",
            "their full subject; replaced and abandoned results are ignored for the right reason.",
            "",
            "Prediction: 8 streams and 76 selected decisions pass the final-stream mechanical",
            "battery and remain queued for owner review. No teacher/provider call is performed.",
            "",
            f"Actual: 8 streams and {review['decision_count']} decisions passed and were packeted.",
            "",
        )
    )


def _review_guide() -> str:
    return """# What to review

Use the review UI and judge each moment as the person using the product. You do not
need to read event IDs or raw JSON.

- When the user clearly asks for a fact, the product should start that lookup once.
- While a requested lookup is still running, unrelated writing should not start it again.
- A fresh result for a request the user still wants should be shown.
- If the user replaces one lookup with another, the old result should be ignored as replaced.
- If the user explicitly abandons a lookup, its later result should be ignored as stale.
- Every shown result should be a natural standalone answer that identifies its subject. Do not
  prepend the user's raw query as a label.

Review all eight interactions. The five checkpoint interactions include earlier context because
the correctness of ignoring a result depends on what the user kept, replaced, or abandoned.
"""


def _checksums(files: dict[str, bytes]) -> bytes:
    return "".join(
        f"{sha256(files[name]).hexdigest()}  {name}\n" for name in sorted(files)
    ).encode("ascii")


def _digest(data: bytes) -> str:
    return f"sha256:{sha256(data).hexdigest()}"
