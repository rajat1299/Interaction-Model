"""Provider-free WP2-2 timer Wave-2 Batch packet."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, replace
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

from im.assets import AssetRegistry, Split
from im.assets.model import TimerAssetPayload, canonical_artifact_bytes
from im.config import estimate_tokens
from im.generation.corpus_segments import CorpusSegmentCandidate
from im.generation.g7_catalog import G7FamilyInputs, build_g7_timer_wave0_fresh_programs
from im.generation.g7_checkpoint_catalog import build_g7_timer_cancel_checkpoint_program
from im.generation.g7_contention_checkpoint import build_g7_contention_checkpoint_program
from im.generation.g7_rollover_checkpoint import build_g7_rollover_checkpoint_catalog
from im.generation.oracle import ScenarioValidationError
from im.generation.phase2_review import (
    BoundaryClass,
    DecisionEvidence,
    FloorClass,
    TrustCellKey,
    route_wave,
)
from im.generation.phase2_timer_wave0 import load_timer_wave0_inputs
from im.generation.phase2_timer_wave2 import (
    _EXCLUDED_STREAM_HASHES,
    _PROMPT_V3_SHA256,
    _VECTORS,
    build_timer_wave2_plan,
)
from im.generation.publication import publish_directory_transaction
from im.generation.scenarios import (
    GeneratedScenario,
    ScenarioProgram,
    execute_scenario,
    validate_generated_scenario,
)
from im.policy.prompted import (
    ModelPricing,
    PromptArtifacts,
    PromptedPolicyConfig,
    PromptRenderer,
    ResponsesRequestBuilder,
)
from im.probes.harness.batch import BatchDecoder, BatchShard, BatchWorkItem, shard_work
from im.probes.harness.identity import cache_identity, digest
from im.probes.harness.models import HarnessProtocol
from im.schema.actions import (
    CancelAction,
    IdleAction,
    NudgeAction,
    ScheduleAction,
    SkipAction,
)

_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_TIMER_WAVE2_PACKET_OUTPUT = _ROOT / "review" / "phase2" / "timer-wave-2"
DEFAULT_TIMER_WAVE2_REPAIRED_PACKET_OUTPUT = (
    _ROOT / "review" / "phase2" / "timer-wave-2-repaired-v3"
)
_STAGE = "t2w2"
_PROMPT_TEMPLATE = "prompt-template-v3.txt"
_MAX_ENQUEUED_TOKENS = 700_000
_MAX_OUTPUT_TOKENS = 8_192
_EXPECTED_CANDIDATES = 46
_EXPECTED_DECISIONS = 698
_EXPECTED_REPAIRED_DECISIONS = 862
_TRUST_MATRIX_VERSION = "phase2-trust-v1"
_REVIEW_BATCH_ID = "pending:timer-wave-2"

_REPAIRED_VECTORS = {
    **_VECTORS,
    "normal_compact": Counter(schedule=4, idle=11, nudge=6),
    "normal_wide": Counter(schedule=5, idle=15, nudge=10),
    "contention_control": Counter(schedule=2, idle=4, mark=2),
    "contention_checkpoint": Counter(cancel=2, idle=3, nudge=3),
    "rollover_a": Counter(idle=15, integrate=1, mark=1, skip=1),
    "rollover_b": Counter(idle=14, integrate=1, mark=1, skip=1),
}

_NORMAL_ASSETS = (
    "a_067f59d6c56633412a0d45b4",
    "a_11d7f848364801c6724c9d75",
    "a_543b664484ba8fff0a5f3ca2",
    "a_5aee644a2b2f34f90485b86f",
    "a_7fbdae8ceff9c6dc9f3fd5c6",
    "a_8dc6c9d3ac20357c23e76ef3",
    "a_a4ad7430aeaff6e0cd839a35",
    "a_b70fe1deb0d2acee5612b5b1",
    "a_c204b0a45393ceb7122064f9",
    "a_f1542b0c1ef44c3e389aaee8",
)
_CANCEL_INPUTS = (
    ("a_297508c00e4e7beb6a08d268", "a_8dc6c9d3ac20357c23e76ef3", "a_c204b0a45393ceb7122064f9"),
    ("a_75e22cef6576f69ea8c4dc5c", "a_5aee644a2b2f34f90485b86f", "a_f1542b0c1ef44c3e389aaee8"),
    ("a_be4de3b8613309556044650f", "a_a4ad7430aeaff6e0cd839a35", "a_b70fe1deb0d2acee5612b5b1"),
    ("a_bf731987afd0a3c98844fc61", "a_7fbdae8ceff9c6dc9f3fd5c6", "a_543b664484ba8fff0a5f3ca2"),
    ("a_d874ff53c5b9ba946bd23bc0", "a_11d7f848364801c6724c9d75", "a_067f59d6c56633412a0d45b4"),
    ("a_297508c00e4e7beb6a08d268", "a_8dc6c9d3ac20357c23e76ef3", "a_f1542b0c1ef44c3e389aaee8"),
    ("a_75e22cef6576f69ea8c4dc5c", "a_5aee644a2b2f34f90485b86f", "a_b70fe1deb0d2acee5612b5b1"),
    ("a_be4de3b8613309556044650f", "a_a4ad7430aeaff6e0cd839a35", "a_543b664484ba8fff0a5f3ca2"),
    ("a_bf731987afd0a3c98844fc61", "a_7fbdae8ceff9c6dc9f3fd5c6", "a_067f59d6c56633412a0d45b4"),
    ("a_d874ff53c5b9ba946bd23bc0", "a_11d7f848364801c6724c9d75", "a_c204b0a45393ceb7122064f9"),
    ("a_297508c00e4e7beb6a08d268", "a_8dc6c9d3ac20357c23e76ef3", "a_b70fe1deb0d2acee5612b5b1"),
    ("a_75e22cef6576f69ea8c4dc5c", "a_5aee644a2b2f34f90485b86f", "a_543b664484ba8fff0a5f3ca2"),
    ("a_be4de3b8613309556044650f", "a_a4ad7430aeaff6e0cd839a35", "a_067f59d6c56633412a0d45b4"),
    ("a_bf731987afd0a3c98844fc61", "a_7fbdae8ceff9c6dc9f3fd5c6", "a_c204b0a45393ceb7122064f9"),
)
_CONTENTION_ASSETS = (
    "a_0ef6b431c2a146d9648263aa",
    "a_1dd4b1f488e74a020e0a0003",
    "a_47742c8fc8a3969f310ec2dc",
    "a_4825bb1a3c21de05c0b980da",
    "a_7f7137db3d888630c073d4f8",
    "a_840c2daf8a2204723142feb7",
    "a_aac54a3e094340a9ef8db18a",
    "a_c674f2b535fce3e1b4cfc26d",
    "a_cbed0e4b0a90e183abeb575f",
    "a_f552ab88c29e296c93a47aa5",
)
_MARK_ASSETS = (
    "a_4d9e7e5fdf179993fd3d8367",
    "a_4f45803171cb2679aa272baa",
    "a_7a61e645a7833002d053596d",
    "a_c6b9ea7492dd47bde4d49e30",
    "a_e8143c61556d755caef0056f",
    "a_f56f7e4a3e7664469a021761",
    "a_fd6da4920d7808b5fa348adb",
)
_ROLLOVER_LOOKUPS = (
    "a_0c280681c3a090e5c4901abd",
    "a_12a569c4e22df60dcf02afba",
    "a_20768c51f96d20c7f5824e31",
    "a_51585c013e336c7b96dcb9ea",
    "a_5d37f24ad969004441c6e3dd",
    "a_9b4d08db0b81ec451ad91397",
    "a_faebb1a6316b74a72c2e41ce",
)
_NORMAL_TEMPLATE = "a_77870a0d84d3da57e4b0318d"
_CANCEL_TEMPLATE = "a_e35790e7d64ca17bc1e3b4d9"
_CONTENTION_TEMPLATE = "a_21e7ddae34d168708913157f"
_CONTENTION_MARK_ASSET = "a_4d9e7e5fdf179993fd3d8367"
_ROLLOVER_TEMPLATE = "a_95c425c1e1736f407ccc54db"


class TimerWave2PacketError(ValueError):
    """A closed Wave-2 source, candidate, or offline request binding drifted."""


@dataclass(frozen=True, slots=True)
class _CandidateSpec:
    logical_stream_id: str
    source_unit_id: str
    kind: str
    program: ScenarioProgram | None
    timing_seed: str
    checkpoint: bool


@dataclass(frozen=True, slots=True)
class _ExecutedCandidate:
    spec: _CandidateSpec
    parent: GeneratedScenario
    candidate: CorpusSegmentCandidate | None

    @property
    def action_indices(self) -> tuple[int, ...]:
        if self.candidate is None:
            return tuple(range(len(self.parent.program.actions)))
        return tuple(index - 1 for index in self.candidate.selected_call_indices)

    @property
    def actions(self) -> tuple[object, ...]:
        return tuple(self.parent.program.actions[index] for index in self.action_indices)


@dataclass(frozen=True, slots=True)
class TimerWave2Packet:
    """The exact offline Batch inputs; this object cannot submit them."""

    files: dict[str, bytes]
    items: tuple[BatchWorkItem, ...]
    shards: tuple[BatchShard, ...]


async def build_timer_wave2_packet(*, repository_root: Path = _ROOT) -> TimerWave2Packet:
    """Execute every sealed parent and render requests for complete candidate units only."""
    root = repository_root.resolve()
    candidate_plan = build_timer_wave2_plan(repository_root=root)
    registry = load_timer_wave0_inputs(
        approved_root=root / "review" / "phase1" / "approved",
        selection_contract_path=root / "spec" / "phase2-selection-v1.json",
    )
    specs = _program_specs(registry)
    with TemporaryDirectory(prefix="phase2-timer-wave2-") as temporary:
        directory = Path(temporary)
        executed = await _execute(specs, directory, root)
        executed += await _execute_rollovers(registry, directory, root)
        _validate_executed(executed, root)
        return _packet(executed, candidate_plan.files["plan.json"], root)


async def build_timer_wave2_repaired_packet(*, repository_root: Path = _ROOT) -> TimerWave2Packet:
    """Render the quota-compatible repaired bulk pool without a provider call."""
    root = repository_root.resolve()
    candidate_plan = build_timer_wave2_plan(repository_root=root)
    registry = load_timer_wave0_inputs(
        approved_root=root / "review" / "phase1" / "approved",
        selection_contract_path=root / "spec" / "phase2-selection-v1.json",
    )
    specs = _program_specs(registry, repaired=True, quota_compatible=True)
    with TemporaryDirectory(prefix="phase2-timer-wave2-repaired-") as temporary:
        directory = Path(temporary)
        executed = await _execute(specs, directory, root)
        executed += await _execute_rollovers(
            registry, directory, root, repaired=True, compact_repair=True
        )
        _validate_executed(executed, root, repaired=True, quota_compatible=True)
        return _packet(executed, candidate_plan.files["plan.json"], root, repaired=True)


async def materialize_timer_wave2_packet(
    output: Path = DEFAULT_TIMER_WAVE2_PACKET_OUTPUT,
    *,
    repository_root: Path = _ROOT,
) -> TimerWave2Packet:
    """Create-only publish the provider-free WP2-2 review packet."""
    packet = await build_timer_wave2_packet(repository_root=repository_root)
    publish_directory_transaction(output, packet.files)
    return packet


async def materialize_timer_wave2_repaired_packet(
    output: Path = DEFAULT_TIMER_WAVE2_REPAIRED_PACKET_OUTPUT,
    *,
    repository_root: Path = _ROOT,
) -> TimerWave2Packet:
    """Create-only publish the provider-free repaired bulk packet."""
    packet = await build_timer_wave2_repaired_packet(repository_root=repository_root)
    publish_directory_transaction(output, packet.files)
    return packet


def _program_specs(
    registry: AssetRegistry, *, repaired: bool = False, quota_compatible: bool = False
) -> tuple[_CandidateSpec, ...]:
    if quota_compatible and not repaired:
        raise ValueError("quota-compatible sources require repaired mode")
    _validate_source_assets(registry)
    specs: list[_CandidateSpec] = []
    for kind, count in (("normal_compact", 5), ("normal_wide", 11)):
        for ordinal in range(count):
            asset_id = _NORMAL_ASSETS[ordinal % len(_NORMAL_ASSETS)]
            outputs = dict(
                build_g7_timer_wave0_fresh_programs(
                    registry,
                    split=Split.TRAIN,
                    normal_inputs=G7FamilyInputs(_NORMAL_TEMPLATE, (asset_id,)),
                    contention_inputs=G7FamilyInputs(
                        _CONTENTION_TEMPLATE,
                        (_CONTENTION_ASSETS[0], _CONTENTION_MARK_ASSET),
                    ),
                    master_seed=f"phase2-timer-wave2:{kind}:{ordinal:02d}",
                    normal_contextual=ordinal % 2 == 1,
                    post_confirmation_gap_ms=4_000 if repaired and not quota_compatible else 0,
                    accumulated_requests=quota_compatible,
                )
            )
            shape = "timer-normal-compact" if kind == "normal_compact" else "timer-normal-wide"
            program = replace(outputs[shape], prompt_template=_PROMPT_TEMPLATE)
            specs.append(
                _CandidateSpec(
                    f"{kind}-{ordinal:02d}",
                    _source_unit_id(kind, program),
                    kind,
                    program,
                    f"g7-{kind}:{ordinal:02d}",
                    False,
                )
            )
    for ordinal in range(14):
        cancel_asset_id, short, long = _CANCEL_INPUTS[ordinal]
        program = build_g7_timer_cancel_checkpoint_program(
            registry,
            split=Split.TRAIN,
            template_id=_CANCEL_TEMPLATE,
            cancel_asset_id=cancel_asset_id,
            timer_asset_ids=(short, long),
            master_seed=f"phase2-timer-wave2:cancel:{ordinal:02d}",
            timing_seed="phase2-timer-cancel:431842",
            repaired_controls=repaired,
        )
        program = replace(program, prompt_template=_PROMPT_TEMPLATE)
        specs.append(
            _CandidateSpec(
                f"cancel-checkpoint-{ordinal:02d}",
                _source_unit_id("cancel_checkpoint", program),
                "cancel_checkpoint",
                program,
                "phase2-timer-cancel:431842",
                True,
            )
        )
    for ordinal in range(6):
        asset_id = _CONTENTION_ASSETS[ordinal % len(_CONTENTION_ASSETS)]
        outputs = dict(
            build_g7_timer_wave0_fresh_programs(
                registry,
                split=Split.TRAIN,
                normal_inputs=G7FamilyInputs(_NORMAL_TEMPLATE, (_NORMAL_ASSETS[0],)),
                contention_inputs=G7FamilyInputs(
                    _CONTENTION_TEMPLATE, (asset_id, _MARK_ASSETS[ordinal])
                ),
                master_seed=f"phase2-timer-wave2:contention-control:{ordinal:02d}",
                post_confirmation_gap_ms=4_000 if repaired and not quota_compatible else 0,
                accumulated_requests=quota_compatible,
            )
        )
        program = replace(outputs["timer-contention-control"], prompt_template=_PROMPT_TEMPLATE)
        specs.append(
            _CandidateSpec(
                f"contention-control-{ordinal:02d}",
                _source_unit_id("contention_control", program),
                "contention_control",
                program,
                f"g7-contention-control:{ordinal:02d}",
                False,
            )
        )
    for ordinal in range(5):
        timer = _timer(registry, _CONTENTION_ASSETS[(ordinal + 4) % len(_CONTENTION_ASSETS)])
        messages = tuple(
            f"{timer.message} beside the mint envelope on shelf {shelf}"
            for shelf in ("one", "two", "three", "four", "five", "six")
        )
        program = build_g7_contention_checkpoint_program(
            registry,
            split=Split.TRAIN,
            template_id=_CONTENTION_TEMPLATE,
            timer_asset_id=_CONTENTION_ASSETS[(ordinal + 4) % len(_CONTENTION_ASSETS)],
            master_seed=f"phase2-timer-wave2:contention-checkpoint:{ordinal:02d}",
            timing_seed=(
                "phase2-contention-checkpoint-repair:0"
                if repaired and not quota_compatible
                else "phase2-contention-checkpoint:839361"
            ),
            messages=messages,
            separated_requests=repaired and not quota_compatible,
            accumulated_requests=quota_compatible,
        )
        program = replace(program, prompt_template=_PROMPT_TEMPLATE)
        specs.append(
            _CandidateSpec(
                f"contention-checkpoint-{ordinal:02d}",
                _source_unit_id("contention_checkpoint", program),
                "contention_checkpoint",
                program,
                "phase2-contention-checkpoint:839361",
                True,
            )
        )
    if len(specs) != 41:
        raise TimerWave2PacketError("non-rollover candidate inventory drifted")
    return tuple(specs)


async def _execute(
    specs: tuple[_CandidateSpec, ...], directory: Path, repository_root: Path
) -> tuple[_ExecutedCandidate, ...]:
    executed = []
    for spec in specs:
        assert spec.program is not None
        try:
            parent = await execute_scenario(
                spec.program,
                session_id=f"phase2-timer-wave2-{spec.logical_stream_id}",
                directory=directory / spec.logical_stream_id,
                repository_root=repository_root,
            )
        except (RuntimeError, ScenarioValidationError) as error:
            raise TimerWave2PacketError(
                f"{spec.logical_stream_id} parent did not execute through the runtime"
            ) from error
        validate_generated_scenario(parent)
        executed.append(
            _ExecutedCandidate(
                spec,
                parent,
                _checkpoint(parent, spec.kind) if spec.checkpoint else None,
            )
        )
    return tuple(executed)


async def _execute_rollovers(
    registry: AssetRegistry,
    directory: Path,
    repository_root: Path,
    *,
    repaired: bool = False,
    compact_repair: bool = False,
) -> tuple[_ExecutedCandidate, ...]:
    requested = ("rollover_a", "rollover_a", "rollover_b", "rollover_b", "rollover_b")
    output = []
    for ordinal, kind in enumerate(requested):
        shape_id = (
            "g7-checkpoint-rollover-a" if kind == "rollover_a" else "g7-checkpoint-rollover-b"
        )
        (entry,) = await build_g7_rollover_checkpoint_catalog(
            registry,
            directory=directory / f"rollover-{ordinal:02d}",
            master_seed=f"phase2-timer-wave2:{kind}:{ordinal:02d}",
            repository_root=repository_root,
            split=Split.TRAIN,
            shape_ids=(shape_id,),
            prompt_template=_PROMPT_TEMPLATE,
            template_id=_ROLLOVER_TEMPLATE,
            rollover_lookup_asset_id=_ROLLOVER_LOOKUPS[ordinal],
            stale_lookup_asset_id=_ROLLOVER_LOOKUPS[ordinal + 1],
            mark_asset_id=_MARK_ASSETS[ordinal],
            first_timer_asset_id=_NORMAL_ASSETS[ordinal],
            recurring_timer_asset_id=_NORMAL_ASSETS[ordinal + 1],
            resolve_stale_first=repaired,
            compact_repair=compact_repair,
        )
        output.append(
            _ExecutedCandidate(
                _CandidateSpec(
                    f"{kind}-{ordinal:02d}",
                    _source_unit_id(kind, entry.parent.program),
                    kind,
                    None,
                    f"g7-rollover-checkpoint-v1:{shape_id}:{ordinal:02d}",
                    True,
                ),
                entry.parent,
                entry.candidate,
            )
        )
    return tuple(output)


def _checkpoint(parent: GeneratedScenario, kind: str) -> CorpusSegmentCandidate:
    expected = {
        "cancel_checkpoint": (
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
        ),
        "contention_checkpoint": (
            *(IdleAction for _ in range(3)),
            *(NudgeAction for _ in range(6)),
            *(CancelAction for _ in range(2)),
            IdleAction,
        ),
    }[kind]
    expected_variants = (expected,)
    if kind == "contention_checkpoint":
        expected_variants += (
            (
                *(action for _ in range(2) for action in (NudgeAction, IdleAction)),
                NudgeAction,
                CancelAction,
                CancelAction,
                IdleAction,
            ),
        )
    matches = []
    for index in range(1, len(parent.stream.segments)):
        candidate = CorpusSegmentCandidate(parent, index, f"t2w2-{kind}")
        if tuple(type(action) for action in candidate.selected_actions) in expected_variants:
            matches.append(candidate)
    if len(matches) != 1:
        raise TimerWave2PacketError(f"{kind} no longer has one complete checkpoint segment")
    return matches[0]


def _validate_executed(
    executed: tuple[_ExecutedCandidate, ...],
    repository_root: Path,
    *,
    repaired: bool = False,
    quota_compatible: bool = False,
) -> None:
    counts = Counter(item.spec.kind for item in executed)
    if counts != {
        "normal_compact": 5,
        "normal_wide": 11,
        "cancel_checkpoint": 14,
        "contention_control": 6,
        "contention_checkpoint": 5,
        "rollover_a": 2,
        "rollover_b": 3,
    }:
        raise TimerWave2PacketError("Wave-2 candidate pool differs from the frozen 46 units")
    expected_decisions = (
        _EXPECTED_DECISIONS
        if quota_compatible
        else _EXPECTED_REPAIRED_DECISIONS
        if repaired
        else _EXPECTED_DECISIONS
    )
    if sum(len(item.actions) for item in executed) != expected_decisions:
        raise TimerWave2PacketError(f"Wave-2 candidate decisions do not total {expected_decisions}")
    if any(item.parent.stream.sha256 in _EXCLUDED_STREAM_HASHES for item in executed):
        raise TimerWave2PacketError("Wave-2 packet repeats an excluded historical stream")
    expected_prompt = _prompt_hash(repository_root)
    if expected_prompt != _PROMPT_V3_SHA256:
        raise TimerWave2PacketError("Wave-2 prompt-template-v3 hash drifted")
    for item in executed:
        validate_generated_scenario(item.parent)
        if (
            item.parent.program.bundle.split is not Split.TRAIN
            or item.parent.program.prompt_template != _PROMPT_TEMPLATE
            or dict(item.parent.stream.provenance.artifact_hashes).get("prompt") != expected_prompt
        ):
            raise TimerWave2PacketError("Wave-2 runtime did not use sealed TRAIN v3 inputs")
        vectors = _REPAIRED_VECTORS if repaired and not quota_compatible else _VECTORS
        if Counter(getattr(action, "type") for action in item.actions) != vectors[item.spec.kind]:
            raise TimerWave2PacketError(f"{item.spec.logical_stream_id} action vector drifted")
        if item.spec.checkpoint and (
            item.candidate is None
            or item.candidate.parent is not item.parent
            or item.candidate.decision_count != len(item.actions)
            or any(index < 0 for index in item.action_indices)
        ):
            raise TimerWave2PacketError("Wave-2 checkpoint candidate is incomplete")
        if not item.spec.checkpoint and item.action_indices != tuple(
            range(len(item.parent.program.actions))
        ):
            raise TimerWave2PacketError("whole parent candidate lost a decision")


def _packet(
    executed: tuple[_ExecutedCandidate, ...],
    candidate_plan_bytes: bytes,
    repository_root: Path,
    *,
    repaired: bool = False,
    expected_candidates: int = _EXPECTED_CANDIDATES,
    expected_decisions: int = _EXPECTED_DECISIONS,
    packet_kind: str | None = None,
    review_batch_id: str | None = None,
    sampling_seed: str = "phase2-timer-wave2-d2-v1",
    stage: str | None = None,
    wave_id: str | None = None,
) -> TimerWave2Packet:
    config = PromptedPolicyConfig(
        model="gpt-5.6-terra",
        reasoning_effort="high",
        max_output_tokens=_MAX_OUTPUT_TOKENS,
        max_attempts=1,
    )
    artifacts = PromptArtifacts(
        behavior_spec=(repository_root / "spec" / "behavior-spec.md").read_bytes(),
        action_schema=(repository_root / "spec" / "schema" / "action-v1.json").read_bytes(),
        prompt_template=(repository_root / "spec" / _PROMPT_TEMPLATE).read_bytes(),
    )
    builder = ResponsesRequestBuilder(PromptRenderer(artifacts), config)
    if builder.renderer.artifacts.prompt_hash != _PROMPT_V3_SHA256:
        raise TimerWave2PacketError("teacher prompt-template-v3 hash drifted")
    identities = [_candidate_identity(item) for item in executed]
    binding = digest(
        canonical_artifact_bytes(
            {
                "candidate_plan_sha256": digest(candidate_plan_bytes),
                "kind": "phase2-timer-wave2-binding-v1",
                "prompt_hash": builder.renderer.artifacts.prompt_hash,
                "units": [
                    (item.spec.logical_stream_id, item.parent.stream.sha256, identity["sha256"])
                    for item, identity in zip(executed, identities, strict=True)
                ],
            }
        )
    )
    stage = stage or ("t2w2r3" if repaired else _STAGE)
    wave_id = wave_id or ("timer-wave-2-repaired-v3" if repaired else "timer-wave-2")
    review_batch_id = review_batch_id or (
        "pending:timer-wave-2-repaired-v3" if repaired else _REVIEW_BATCH_ID
    )
    evidence, routes = _routes(
        executed,
        sampling_seed=sampling_seed,
        wave_id=wave_id,
    )
    route_by_identity = {route.identity: route for route in routes}
    items, targets = [], []
    for item, identity in zip(executed, identities, strict=True):
        for program_action_index, action in zip(item.action_indices, item.actions, strict=True):
            boundary = item.parent.decision_boundaries[program_action_index]
            custom_id = f"{stage}.{item.spec.logical_stream_id}.d{program_action_index:03}.a1"
            body = builder.build(boundary.policy_bytes)
            body_bytes = canonical_artifact_bytes(body)
            work = BatchWorkItem(
                custom_id=custom_id,
                identity=cache_identity(
                    manifest_sha256=binding,
                    probe_id=custom_id,
                    protocol=HarnessProtocol.GENERATION,
                    variant_id=wave_id,
                    presentation=digest(boundary.policy_bytes),
                    model=config.model,
                    reasoning_effort=config.reasoning_effort,
                    prompt_hash=builder.renderer.artifacts.prompt_hash,
                    request_bytes=body_bytes,
                ),
                body=body,
                prompt_hash=builder.renderer.artifacts.prompt_hash,
                decoder=BatchDecoder.ACTION,
            )
            items.append(work)
            decision = next(
                entry
                for entry in evidence
                if entry.stream_sha256 == item.parent.stream.sha256
                and entry.decision_policy_seq == program_action_index
            )
            route = route_by_identity[decision.identity]
            targets.append(
                {
                    "candidate_identity_sha256": identity["sha256"],
                    "candidate_kind": identity["kind"],
                    "candidate_selected_call_indices": identity["selected_call_indices"],
                    "candidate_selected_program_action_indices": list(item.action_indices),
                    "custom_id": custom_id,
                    "d13": {
                        "label_origin": None,
                        "pending_origin": "teacher_outcome_then_d2_review",
                        "review_batch_id": None,
                        "trust_matrix_version": _TRUST_MATRIX_VERSION,
                    },
                    "family": item.parent.program.family.value,
                    "logical_stream_id": item.spec.logical_stream_id,
                    "oracle_action": action.model_dump(mode="json"),
                    "policy_prefix_sha256": digest(boundary.policy_bytes),
                    "program_action_index": program_action_index,
                    "prompt_hash": builder.renderer.artifacts.prompt_hash,
                    "request_body_sha256": digest(body_bytes),
                    "source_unit_id": item.spec.source_unit_id,
                    "static_d2_route": {
                        "add_review_if": [
                            "teacher_low_confidence",
                            "teacher_oracle_disagreement",
                        ],
                        "mandatory_review": route.mandatory,
                        "reasons": list(route.reasons),
                        "review_required": route.review_required,
                        "sample_rate": route.sample_rate,
                    },
                    "stream_sha256": item.parent.stream.sha256,
                }
            )
    item_tuple = tuple(items)
    if len(item_tuple) != expected_decisions or len(targets) != expected_decisions:
        raise TimerWave2PacketError(
            f"teacher requests must cover exactly {expected_decisions} candidate decisions"
        )
    if any(
        target["program_action_index"] not in target["candidate_selected_program_action_indices"]
        for target in targets
    ):
        raise TimerWave2PacketError("teacher plan includes a decision outside its candidate unit")
    shards = shard_work(stage, item_tuple, max_enqueued_tokens=_MAX_ENQUEUED_TOKENS)
    plan_payload = _canonical_object(candidate_plan_bytes, "candidate plan")
    manifest = {
        "api_call_performed": False,
        "authorization_state": "not_submitted",
        "binding_sha256": binding,
        "candidate_decision_count": expected_decisions,
        "candidate_plan_sha256": digest(candidate_plan_bytes),
        "candidate_unit_count": expected_candidates,
        "cost_estimate": _cost(item_tuple, config),
        "d13_pending_origin": {
            "label_origin": None,
            "pending_origin": "teacher_outcome_then_d2_review",
            "review_batch_id": None,
            "trust_matrix_version": _TRUST_MATRIX_VERSION,
        },
        "endpoint": "/v1/responses",
        "eligibility_bindings": {
            "excluded_stream_hashes": plan_payload["excluded_stream_hashes"],
            "sidecar_sha256": plan_payload["eligibility_sidecar_sha256"],
        },
        "excluded_historical_stream_hashes": list(_EXCLUDED_STREAM_HASHES),
        "format_version": 1,
        "kind": packet_kind
        or (
            "phase2-timer-wave2-repaired-teacher-plan"
            if repaired
            else "phase2-timer-wave2-teacher-plan"
        ),
        "max_enqueued_tokens": _MAX_ENQUEUED_TOKENS,
        "max_output_tokens_per_request": config.max_output_tokens,
        "model": config.model,
        "multiplier_reassessment": {
            "accepted_wave1_stream_count": plan_payload["accepted_wave1_stream_count"],
            "basis": "accepted-decision yield after each family Wave-1",
            "candidate_generation": plan_payload["candidate_generation"],
            "status": "pending_wave2_owner_review_before_wave3_top_up",
            "teacher_agreement_selection_feature": False,
        },
        "prompt_bindings": {
            "runtime_prompt_hashes": [builder.renderer.artifacts.prompt_hash],
            "teacher_prompt_hash": builder.renderer.artifacts.prompt_hash,
        },
        "reasoning_effort": config.reasoning_effort,
        "request_count": len(item_tuple),
        "selection_bindings": {
            "candidate_plan_sha256": digest(candidate_plan_bytes),
            "selection_contract_sha256": plan_payload["selection_contract_sha256"],
            "selection_execution": plan_payload["final_selection"],
        },
        "shard_count": len(shards),
        "shards": [
            {
                "estimated_input_tokens": shard.estimated_input_tokens,
                "input_path": f"teacher-input/shard-{shard.shard_index:03}.jsonl",
                "input_sha256": shard.input_sha256,
                "request_count": len(shard.items),
                "shard_index": shard.shard_index,
                "stage": stage,
            }
            for shard in shards
        ],
        "source_bindings": _source_bindings(executed, repository_root),
        "source_unit_count": len({item.spec.source_unit_id for item in executed}),
        "stage": stage,
        "static_d2_routing": {
            "d1_default_cell_state": "uncleared",
            "review_batch_id": review_batch_id,
            "route_count": len(routes),
            "review_required_count": sum(route.review_required for route in routes),
            "trust_matrix_version": _TRUST_MATRIX_VERSION,
        },
        "targets": targets,
        "wave_id": wave_id,
    }
    raw = {
        "format_version": 1,
        "kind": "phase2-timer-wave2-parent-candidates",
        "streams": [
            {
                "candidate": {
                    **identity,
                    "selected_actions": [action.model_dump(mode="json") for action in item.actions],
                    "selected_program_action_indices": list(item.action_indices),
                    "unit_kind": item.spec.kind,
                },
                "logical_stream_id": item.spec.logical_stream_id,
                "parent": _raw_parent(item),
                "source_unit_id": item.spec.source_unit_id,
            }
            for item, identity in zip(executed, identities, strict=True)
        ],
    }
    files = {
        "README.md": _readme(manifest).encode("utf-8"),
        "raw-streams.json": canonical_artifact_bytes(raw),
        "teacher-plan.json": canonical_artifact_bytes(manifest),
        **{
            f"teacher-input/shard-{shard.shard_index:03}.jsonl": shard.input_jsonl
            for shard in shards
        },
    }
    return TimerWave2Packet({**files, "SHA256SUMS": _checksums(files)}, item_tuple, shards)


def _routes(
    executed: tuple[_ExecutedCandidate, ...],
    *,
    sampling_seed: str = "phase2-timer-wave2-d2-v1",
    wave_id: str = "timer-wave-2",
) -> tuple[tuple[DecisionEvidence, ...], tuple[object, ...]]:
    evidence = []
    for item in executed:
        for index, action in zip(item.action_indices, item.actions, strict=True):
            sidecar = item.parent.sidecar.decisions[index]
            floor = (
                FloorClass.OPEN
                if sidecar.floor_open
                else FloorClass.OWNED
                if sidecar.floor_owned
                else FloorClass.CLOSED
            )
            risks = {"skip_reason_selection"} if isinstance(action, SkipAction) else set()
            if item.spec.checkpoint:
                risks.add("rollover_or_checkpoint_projection")
            evidence.append(
                DecisionEvidence(
                    stream_sha256=item.parent.stream.sha256,
                    decision_policy_seq=index,
                    wave_id=wave_id,
                    cell=TrustCellKey(
                        HarnessProtocol.GENERATION,
                        item.parent.program.family,
                        floor,
                    ),
                    template_id=item.parent.program.template.asset_id,
                    source_unit_id=item.spec.source_unit_id,
                    oracle_action=action,
                    # Mirror the oracle only to compute the output-independent D2 base route.
                    # The post-call router replaces this with the actual teacher action.
                    teacher_action=action,
                    causal_state_class=item.spec.kind,
                    boundary_class=BoundaryClass.ORDINARY,
                    risk_flags=tuple(sorted(risks)),
                    rollover=item.spec.kind.startswith("rollover_"),
                )
            )
    values = tuple(evidence)
    return values, route_wave(values, {}, sampling_seed=sampling_seed)


def _candidate_identity(item: _ExecutedCandidate) -> dict[str, object]:
    if item.candidate is None:
        identity = {
            "decision_count": len(item.actions),
            "kind": "complete_parent",
            "selected_call_indices": [index + 1 for index in item.action_indices],
            "shape_id": item.spec.kind,
            "stream_sha256": item.parent.stream.sha256,
        }
    else:
        identity = {"kind": "complete_checkpoint_segment", **item.candidate.as_json_object()}
    return {**identity, "sha256": digest(canonical_artifact_bytes(identity))}


def _parent_identity(item: _ExecutedCandidate) -> dict[str, object]:
    return {
        "asset_ids": list(item.parent.program.asset_ids),
        "family": item.parent.program.family.value,
        "prompt_hash": dict(item.parent.stream.provenance.artifact_hashes)["prompt"],
        "scenario_input_sha256": item.parent.sidecar.scenario_input_sha256,
        "seed": item.parent.program.master_seed,
        "sidecar_sha256": item.parent.sidecar.sha256,
        "stream_sha256": item.parent.stream.sha256,
        "template_id": item.parent.program.template.asset_id,
        "timing": {
            "population": item.parent.program.timing_plan.seed.population.value,
            "seed": item.parent.program.timing_plan.seed.seed,
            "seed_id": item.parent.program.timing_plan.seed.timing_seed_id,
            "split": item.parent.program.timing_plan.seed.split.value,
        },
    }


def _raw_parent(item: _ExecutedCandidate) -> dict[str, object]:
    return {
        **_parent_identity(item),
        "actions": [action.model_dump(mode="json") for action in item.parent.program.actions],
        "decision_boundaries": [
            {
                "call_index": boundary.call_index,
                "policy_prefix_sha256": digest(boundary.policy_bytes),
            }
            for boundary in item.parent.decision_boundaries
        ],
        "frames": [
            {"at_ms": frame.at_ms, "sampler_json": frame.raw_bytes.decode("utf-8")}
            for frame in item.parent.program.frames
        ],
        "sidecar": item.parent.sidecar.as_json_object(),
    }


def _source_bindings(executed: tuple[_ExecutedCandidate, ...], root: Path) -> dict[str, object]:
    approved = root / "review" / "phase1" / "approved"
    files = {
        name: digest((approved / name).read_bytes())
        for name in ("registry.jsonl", "train-seal.json", "test-seal.json", "demo-seal.json")
    }
    return {
        "approved_input_sha256": files,
        "parents": [_parent_identity(item) for item in executed],
        "sealed_split": Split.TRAIN.value,
    }


def _validate_source_assets(registry: AssetRegistry) -> None:
    pool = registry.pool(Split.TRAIN)
    records = {asset.asset_id: asset for asset in (*pool.assets, *pool.templates)}
    required = (
        *_NORMAL_ASSETS,
        *(asset_id for values in _CANCEL_INPUTS for asset_id in values),
        *_CONTENTION_ASSETS,
        _NORMAL_TEMPLATE,
        _CANCEL_TEMPLATE,
        _CONTENTION_TEMPLATE,
        _CONTENTION_MARK_ASSET,
        *_MARK_ASSETS,
        *_ROLLOVER_LOOKUPS,
        _ROLLOVER_TEMPLATE,
    )
    if any(
        asset_id not in records or not registry.is_approved(records[asset_id])
        for asset_id in required
    ):
        raise TimerWave2PacketError("Wave-2 requires sealed approved TRAIN source assets")


def _timer(registry: AssetRegistry, asset_id: str) -> TimerAssetPayload:
    asset = next(
        (item for item in registry.pool(Split.TRAIN).assets if item.asset_id == asset_id),
        None,
    )
    if not isinstance(getattr(asset, "payload", None), TimerAssetPayload):
        raise TimerWave2PacketError(f"{asset_id} is not a TRAIN timer asset")
    return asset.payload


def _source_unit_id(kind: str, program: ScenarioProgram) -> str:
    """Share a source unit only when its lexical asset combination and shape match."""
    value = {
        "asset_ids": sorted(program.asset_ids),
        "shape": kind,
        "template_id": program.template.asset_id,
    }
    return f"t2w2-{kind}-{digest(canonical_artifact_bytes(value))[7:23]}"


def _prompt_hash(root: Path) -> str:
    return digest((root / "spec" / _PROMPT_TEMPLATE).read_bytes())


def _cost(items: tuple[BatchWorkItem, ...], config: PromptedPolicyConfig) -> dict[str, object]:
    pricing = ModelPricing(model=config.model)
    input_tokens = sum(estimate_tokens(canonical_artifact_bytes(item.body)) for item in items)

    def amount(output_tokens: int) -> str:
        value = (
            pricing.batch_multiplier
            * (
                Decimal(input_tokens) * pricing.input_per_million
                + Decimal(output_tokens) * pricing.output_per_million
            )
            / Decimal(1_000_000)
        )
        return format(value.quantize(Decimal("0.000001")), "f")

    expected_output = 300 * len(items)
    maximum_output = config.max_output_tokens * len(items)
    return {
        "approval_ceiling_usd": amount(maximum_output),
        "batch_multiplier": format(pricing.batch_multiplier, "f"),
        "expected_input_tokens": input_tokens,
        "expected_output_tokens": expected_output,
        "expected_usd": amount(expected_output),
        "maximum_output_tokens": maximum_output,
        "pricing_source_date": pricing.source_date,
    }


def _canonical_object(data: bytes, label: str) -> dict[str, object]:
    import json

    value = json.loads(data)
    if not isinstance(value, dict) or canonical_artifact_bytes(value) != data:
        raise TimerWave2PacketError(f"{label} is not canonical JSON")
    return value


def _checksums(files: dict[str, bytes]) -> bytes:
    return "".join(
        f"{sha256(data).hexdigest()}  {name}\n" for name, data in sorted(files.items())
    ).encode("ascii")


def _readme(manifest: dict[str, object]) -> str:
    cost = manifest["cost_estimate"]
    assert isinstance(cost, dict)
    return "\n".join(
        (
            "# WP2-2 timer Wave-2 offline teacher packet",
            "",
            "Hypothesis: complete parent and checkpoint candidates preserve hard timer boundaries",
            "without selecting on teacher agreement.",
            "",
            (
                f"Candidates: {manifest['candidate_unit_count']} / "
                f"{manifest['candidate_decision_count']} decisions."
            ),
            f"Requests: {manifest['request_count']} in {manifest['shard_count']} shards.",
            (
                f"Expected Batch cost: ${cost['expected_usd']}; "
                f"approval ceiling: ${cost['approval_ceiling_usd']}."
            ),
            "No provider call or upload was performed; D2 routes and D13 origins remain pending.",
            "",
        )
    )
