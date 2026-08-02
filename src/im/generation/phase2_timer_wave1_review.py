"""Materialize the completed Timer Wave-1 Batch as a review-UI packet."""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

from im.assets.model import canonical_artifact_bytes
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
    parse_phase2_review_evidence,
    project_phase2_review_evidence,
)
from im.generation.phase2_timer_wave0 import load_timer_wave0_inputs
from im.generation.phase2_timer_wave1 import (
    DEFAULT_TIMER_WAVE1_OUTPUT,
    _execute,
    _packet,
    _streams,
)
from im.generation.publication import publish_directory_transaction
from im.license import Allowed, Blocked, check
from im.probes.harness.models import HarnessProtocol
from im.schema.actions import ACTION_ADAPTER

_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_TIMER_WAVE1_EXECUTION = _ROOT / "review" / "phase2" / "timer-wave-1-execution"
DEFAULT_TIMER_WAVE1_REVIEW_OUTPUT = DEFAULT_TIMER_WAVE1_EXECUTION / "review"
_EXPECTED_DECISIONS = 82
_EXPECTED_SOURCE_UNITS = 12
_PROVIDER_FILES = (
    "comparison.json",
    "plan.json",
    "shards/0000/comparison.json",
    "shards/0000/errors.jsonl",
    "shards/0000/execution-state.json",
    "shards/0000/output.jsonl",
    "shards/0000/provider-batch.json",
    "shards/0001/comparison.json",
    "shards/0001/errors.jsonl",
    "shards/0001/execution-state.json",
    "shards/0001/output.jsonl",
    "shards/0001/provider-batch.json",
)


class TimerWave1ReviewError(ValueError):
    """The completed Wave-1 artifacts cannot be made safe for owner review."""


@dataclass(frozen=True, slots=True)
class TimerWave1ReviewPacket:
    files: dict[str, bytes]
    review_count: int
    non_equivalent_count: int
    individual_queue_count: int


@dataclass(frozen=True, slots=True)
class _UnroutedProjectionInput:
    decision: DecisionEvidence
    oracle_license: CandidateLicense
    teacher_license: CandidateLicense | None
    oracle_provenance: dict[str, str]
    teacher_provenance: dict[str, str] | None
    priority_rank: int


async def materialize_timer_wave1_review_packet(
    output: Path = DEFAULT_TIMER_WAVE1_REVIEW_OUTPUT,
    *,
    execution_root: Path = DEFAULT_TIMER_WAVE1_EXECUTION,
    repository_root: Path = _ROOT,
) -> TimerWave1ReviewPacket:
    """Regenerate the sealed canary and create a checksum-bound review packet.

    The provider output is never regenerated or normalized: its retained bytes
    are copied into the packet and referenced by the blinded review evidence.
    """
    repository_root = repository_root.resolve()
    execution_root = execution_root.resolve()
    registry = load_timer_wave0_inputs(
        approved_root=repository_root / "review" / "phase1" / "approved",
        selection_contract_path=repository_root / "spec" / "phase2-selection-v1.json",
    )
    streams = _streams(registry)
    with TemporaryDirectory(prefix="phase2-timer-wave1-review-") as temporary:
        executed = await _execute(streams, Path(temporary), repository_root)
        plan = _packet(executed, repository_root)
        _verify_planned_packet(
            repository_root / DEFAULT_TIMER_WAVE1_OUTPUT.relative_to(_ROOT), plan.files
        )
        packet = build_timer_wave1_review_packet(
            executed,
            plan.files,
            execution_root=execution_root,
            repository_root=repository_root,
        )
    publish_directory_transaction(output, packet.files)
    return packet


def build_timer_wave1_review_packet(
    executed: tuple[object, ...],
    planned_files: dict[str, bytes],
    *,
    execution_root: Path,
    repository_root: Path = _ROOT,
) -> TimerWave1ReviewPacket:
    """Render a review packet from regenerated parents and retained Batch bytes."""
    if len(executed) != 15:
        raise TimerWave1ReviewError("Wave-1 review requires the complete fifteen-stream inventory")
    if not isinstance(planned_files.get("teacher-plan.json"), bytes):
        raise TimerWave1ReviewError("Wave-1 review requires the canonical teacher plan")
    plan = _canonical_object(planned_files["teacher-plan.json"], "teacher plan")
    provider_files, provider_evidence = _provider_files(execution_root, repository_root)
    comparison = _canonical_object(
        provider_files["provider/comparison.json"], "provider comparison"
    )
    rows = comparison.get("rows")
    if not isinstance(rows, list) or len(rows) != _EXPECTED_DECISIONS:
        raise TimerWave1ReviewError("provider comparison does not contain all 82 decisions")
    if comparison.get("request_count") != _EXPECTED_DECISIONS:
        raise TimerWave1ReviewError("provider comparison request count is not closed")

    by_stream = {item.generated.stream.sha256: item for item in executed}
    if len(by_stream) != len(executed):
        raise TimerWave1ReviewError("regenerated streams are not unique")
    targets = _targets(plan)
    if len(targets) != _EXPECTED_DECISIONS:
        raise TimerWave1ReviewError("teacher plan target inventory is incomplete")

    output_hashes = _output_hashes(provider_files)
    inputs = _projection_inputs(rows, targets, by_stream, output_hashes, provider_evidence)
    routes = route_wave(
        tuple(item.decision for item in inputs), {}, sampling_seed="phase2-timer-wave1-route-v1"
    )
    routed = tuple(
        DecisionProjectionInput(
            decision=input_.decision,
            route=route,
            oracle_license=input_.oracle_license,
            teacher_license=input_.teacher_license,
            oracle_provenance=input_.oracle_provenance,
            teacher_provenance=input_.teacher_provenance,
            priority_rank=input_.priority_rank,
        )
        for input_, route in zip(inputs, routes, strict=True)
    )
    identities = tuple(
        (item.decision.stream_sha256, item.decision.decision_policy_seq) for item in routed
    )
    review_bytes = project_phase2_review_evidence(
        routed,
        packet_decision_identities=identities,
        teacher_evidence_identity=_digest(provider_evidence),
        blind_seed="phase2-timer-wave1-review-blind-v1",
    )
    review = parse_phase2_review_evidence(review_bytes)
    decisions = review["decisions"]
    clusters = review["clusters"]
    assert isinstance(decisions, list) and isinstance(clusters, list)
    non_equivalent_count = sum(item["comparison"] != "equivalent" for item in decisions)
    clustered_count = sum(len(item["member_identities"]) for item in clusters)
    individual_queue_count = non_equivalent_count - clustered_count

    manifest = PackageManifest.build(item.generated for item in executed)
    source_index = _source_index(tuple(executed))
    files = {
        "README.md": _readme(
            decision_count=len(decisions),
            source_count=len(source_index["sources"]),
            review_count=sum(
                bool(item["review_evidence"]["review_route"]["review_required"])
                for item in decisions
            ),
            non_equivalent_count=non_equivalent_count,
            individual_queue_count=individual_queue_count,
        ).encode("utf-8"),
        "manifest.json": manifest.canonical_bytes,
        "source-index.json": canonical_artifact_bytes(source_index),
        "phase2-review-evidence.json": review_bytes,
        "provider-evidence.json": provider_evidence,
        "review-packet.json": canonical_artifact_bytes(
            {
                "format_version": 1,
                "kind": "phase2-timer-wave1-owner-review",
                "owner_dispositions_present": False,
                "provider_evidence_sha256": _digest(provider_evidence),
                "review_evidence_sha256": _digest(review_bytes),
            }
        ),
        "teacher-plan.json": planned_files["teacher-plan.json"],
        "raw-streams.json": planned_files["raw-streams.json"],
        **{
            path: value
            for path, value in planned_files.items()
            if path.startswith("teacher-input/")
        },
        **_runtime_files(tuple(executed)),
        **provider_files,
    }
    return TimerWave1ReviewPacket(
        files={**files, "SHA256SUMS": _checksums(files)},
        review_count=sum(
            bool(item["review_evidence"]["review_route"]["review_required"])
            for item in decisions
        ),
        non_equivalent_count=non_equivalent_count,
        individual_queue_count=individual_queue_count,
    )


def _verify_planned_packet(packet_root: Path, files: dict[str, bytes]) -> None:
    for relative_path, content in files.items():
        path = packet_root / relative_path
        if not path.is_file() or path.read_bytes() != content:
            raise TimerWave1ReviewError(
                f"regenerated plan differs from executed packet: {relative_path}"
            )


def _provider_files(
    execution_root: Path, repository_root: Path
) -> tuple[dict[str, bytes], bytes]:
    files: dict[str, bytes] = {}
    inventory: list[dict[str, str]] = []
    for relative_path in _PROVIDER_FILES:
        source = execution_root / relative_path
        if not source.is_file():
            raise TimerWave1ReviewError(f"retained provider artifact is missing: {relative_path}")
        value = source.read_bytes()
        review_path = f"provider/{relative_path}"
        files[review_path] = value
        inventory.append(
            {
                "execution_path": source.relative_to(repository_root).as_posix(),
                "review_path": review_path,
                "sha256": _digest(value),
            }
        )
    evidence = canonical_artifact_bytes(
        {
            "format_version": 1,
            "kind": "phase2-timer-wave1-provider-evidence",
            "files": inventory,
            "provider_comparison_sha256": _digest(files["provider/comparison.json"]),
        }
    )
    return files, evidence


def _output_hashes(provider_files: dict[str, bytes]) -> dict[int, str]:
    hashes: dict[int, str] = {}
    for shard_index in range(2):
        path = f"provider/shards/{shard_index:04d}/output.jsonl"
        if path not in provider_files:
            raise TimerWave1ReviewError(f"provider output is absent for shard {shard_index}")
        hashes[shard_index] = _digest(provider_files[path])
    return hashes


def _projection_inputs(
    rows: list[object],
    targets: dict[str, dict[str, object]],
    by_stream: dict[str, object],
    output_hashes: dict[int, str],
    provider_evidence: bytes,
) -> tuple[_UnroutedProjectionInput, ...]:
    inputs: list[_UnroutedProjectionInput] = []
    seen: set[str] = set()
    comparison_sha256 = _digest(provider_evidence)
    for priority_rank, raw in enumerate(rows):
        if not isinstance(raw, dict):
            raise TimerWave1ReviewError("provider comparison row is malformed")
        custom_id = raw.get("custom_id")
        if not isinstance(custom_id, str) or custom_id in seen or custom_id not in targets:
            raise TimerWave1ReviewError("provider comparison custom IDs do not close over the plan")
        seen.add(custom_id)
        target = targets[custom_id]
        if raw.get("target") != target or raw.get("oracle_action") != target.get("oracle_action"):
            raise TimerWave1ReviewError(f"provider comparison target drifted for {custom_id}")
        stream_sha256 = target.get("stream_sha256")
        program_index = target.get("program_action_index")
        shard_index = raw.get("shard_index")
        if (
            not isinstance(stream_sha256, str)
            or stream_sha256 not in by_stream
            or isinstance(program_index, bool)
            or not isinstance(program_index, int)
            or isinstance(shard_index, bool)
            or not isinstance(shard_index, int)
            or shard_index not in output_hashes
        ):
            raise TimerWave1ReviewError(f"provider comparison metadata is invalid for {custom_id}")
        executed = by_stream[stream_sha256]
        if not 0 <= program_index < len(executed.generated.sidecar.decisions):
            raise TimerWave1ReviewError(f"program action index is invalid for {custom_id}")
        sidecar_decision = executed.generated.sidecar.decisions[program_index]
        boundary = executed.generated.decision_boundaries[program_index]
        oracle = executed.stream.program.actions[program_index]
        if (
            oracle.model_dump(mode="json") != target["oracle_action"]
            or _digest(boundary.policy_bytes) != target.get("policy_prefix_sha256")
            or executed.stream.source_unit_id != target.get("source_unit_id")
        ):
            raise TimerWave1ReviewError(f"regenerated decision evidence drifted for {custom_id}")

        teacher_raw = raw.get("teacher_action")
        teacher = None
        teacher_license = None
        teacher_provenance = None
        if teacher_raw is not None:
            try:
                teacher = ACTION_ADAPTER.validate_python(teacher_raw)
            except (TypeError, ValueError) as error:
                raise TimerWave1ReviewError(
                    f"teacher action is not canonical for {custom_id}"
                ) from error
            teacher_license = _license(teacher, boundary.license_view)
            teacher_provenance = {
                "comparison_sha256": comparison_sha256,
                "custom_id": custom_id,
                "provider_output_sha256": output_hashes[shard_index],
                "request_body_sha256": _required_digest(target, "request_body_sha256", custom_id),
            }
        expected_equivalent = (
            teacher is not None and teacher.model_dump(mode="json") == target["oracle_action"]
        )
        if raw.get("comparison") != ("equivalent" if expected_equivalent else "non_equivalent"):
            raise TimerWave1ReviewError(
                f"provider comparison classification drifted for {custom_id}"
            )

        cell = _record(target.get("cell"), f"target trust cell for {custom_id}")
        flags = _string_tuple(target.get("risk_flags"), f"risk flags for {custom_id}")
        decision = DecisionEvidence(
            stream_sha256=stream_sha256,
            decision_policy_seq=sidecar_decision.observed_policy_seq,
            wave_id="timer-wave-1",
            cell=TrustCellKey(
                HarnessProtocol(cell["protocol"]),
                executed.stream.program.family,
                FloorClass(cell["floor"]),
            ),
            template_id=executed.stream.program.template.asset_id,
            source_unit_id=executed.stream.source_unit_id,
            oracle_action=oracle,
            teacher_action=teacher,
            causal_state_class=_required_string(target, "causal_state_class", custom_id),
            boundary_class=BoundaryClass(_required_string(target, "boundary_class", custom_id)),
            risk_flags=tuple(
                sorted(
                    set(flags)
                    | (
                        {"oracle_teacher_non_equivalence"}
                        if teacher is not None and teacher != oracle
                        else set()
                    )
                )
            ),
            idle_boundary=target.get("idle_boundary"),
            rollover=target.get("rollover"),
        )
        inputs.append(
            _UnroutedProjectionInput(
                decision=decision,
                oracle_license=_license(oracle, boundary.license_view),
                teacher_license=teacher_license,
                oracle_provenance={
                    "sidecar_sha256": executed.generated.sidecar.sha256,
                    "stream_sha256": stream_sha256,
                },
                teacher_provenance=teacher_provenance,
                priority_rank=priority_rank,
            )
        )
    if len(seen) != len(targets):
        raise TimerWave1ReviewError("provider comparison does not cover every planned request")
    return tuple(inputs)


def _license(action: object, view: object) -> CandidateLicense:
    result = check(action, view)
    if isinstance(result, Allowed):
        return CandidateLicense("licensed", ())
    assert isinstance(result, Blocked)
    return CandidateLicense("blocked", (result.code,))


def _runtime_files(executed: tuple[object, ...]) -> dict[str, bytes]:
    files: dict[str, bytes] = {}
    for item in executed:
        generated = item.generated
        stream = generated.stream.sha256.removeprefix("sha256:")
        for segment in generated.stream.segments:
            files[f"teacher/{stream}/{segment.sha256.removeprefix('sha256:')}.jsonl"] = (
                segment.policy_bytes
            )
        files[f"reviewer/{stream}/sidecar.json"] = generated.sidecar.canonical_bytes
        files[f"reviewer/{stream}/runtime-ledger.json"] = (
            generated.stream.final_ledger.canonical_bytes
        )
    return files


def _source_index(executed: tuple[object, ...]) -> dict[str, object]:
    by_source: defaultdict[str, list[object]] = defaultdict(list)
    for item in executed:
        by_source[item.stream.source_unit_id].append(item)
    if len(by_source) != _EXPECTED_SOURCE_UNITS:
        raise TimerWave1ReviewError("Wave-1 source-unit inventory is not twelve")
    sources = []
    for source_unit_id, members in sorted(by_source.items()):
        ordered = sorted(members, key=lambda item: item.generated.stream.sha256)
        first = ordered[0]
        if any(
            item.stream.program.family != first.stream.program.family
            or item.stream.program.master_seed != first.stream.program.master_seed
            for item in ordered
        ):
            raise TimerWave1ReviewError(f"source unit {source_unit_id} has incompatible parents")
        sources.append(
            {
                "checkpoint": None,
                "family": first.stream.program.family.value,
                "master_seed": first.stream.program.master_seed,
                "parent_stream_sha256s": [item.generated.stream.sha256 for item in ordered],
                "raw_source_sha256s": [item.generated.stream.capture_sha256 for item in ordered],
                "role": "timer_wave1_runtime_parent",
                "shape_id": source_unit_id,
                "sidecar_sha256s": [item.generated.sidecar.sha256 for item in ordered],
                "source_decision_counts": [
                    len(item.generated.sidecar.decisions) for item in ordered
                ],
                "source_kind": "runtime_parent",
                "source_unit_id": source_unit_id,
            }
        )
    return {
        "batch": 1,
        "format_version": 1,
        "source_identity_rule": "source_unit_id groups complete regenerated runtime parents",
        "sources": sources,
    }


def _targets(plan: dict[str, object]) -> dict[str, dict[str, object]]:
    raw = plan.get("targets")
    if not isinstance(raw, list):
        raise TimerWave1ReviewError("teacher plan does not contain targets")
    targets = {
        item["custom_id"]: item
        for item in raw
        if isinstance(item, dict) and isinstance(item.get("custom_id"), str)
    }
    if len(targets) != len(raw):
        raise TimerWave1ReviewError("teacher plan target identifiers are malformed")
    return targets


def _record(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise TimerWave1ReviewError(f"{label} is malformed")
    return value


def _required_string(value: dict[str, object], key: str, custom_id: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item:
        raise TimerWave1ReviewError(f"{key} is missing for {custom_id}")
    return item


def _required_digest(value: dict[str, object], key: str, custom_id: str) -> str:
    item = _required_string(value, key, custom_id)
    if not item.startswith("sha256:") or len(item) != 71:
        raise TimerWave1ReviewError(f"{key} is not a digest for {custom_id}")
    return item


def _string_tuple(value: object, label: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise TimerWave1ReviewError(f"{label} is malformed")
    return tuple(value)


def _canonical_object(data: bytes, label: str) -> dict[str, object]:
    try:
        value = json.loads(data)
    except (TypeError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise TimerWave1ReviewError(f"{label} is not JSON") from error
    if not isinstance(value, dict) or canonical_artifact_bytes(value) != data:
        raise TimerWave1ReviewError(f"{label} is not canonical JSON")
    return value


def _digest(value: bytes) -> str:
    return f"sha256:{sha256(value).hexdigest()}"


def _checksums(files: dict[str, bytes]) -> bytes:
    return "".join(
        f"{sha256(files[path]).hexdigest()}  {path}\n" for path in sorted(files)
    ).encode("ascii")


def _readme(
    *,
    decision_count: int,
    source_count: int,
    review_count: int,
    non_equivalent_count: int,
    individual_queue_count: int,
) -> str:
    return "\n".join(
        (
            "# Phase 2 timer Wave-1 owner review packet",
            "",
            (
                "This packet binds the completed provider Batch output to the regenerated "
                "runtime parents."
            ),
            (
                f"Decisions: {decision_count}; logical source units: {source_count}; review "
                f"routes: {review_count}."
            ),
            (
                f"Non-equivalences: {non_equivalent_count}; individually queued without a "
                f"D7 cluster: {individual_queue_count}."
            ),
            "",
            "The blinded A/B candidates and provider evidence are retained for owner review.",
            "No owner disposition or adjudication is included in this packet.",
            "",
        )
    )
