"""Bind completed timer Wave-2 Batch outputs into the Phase-2 review packet."""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

from im.assets.model import canonical_artifact_bytes
from im.generation.packaging import PackageManifest
from im.generation.phase2_review import (
    BoundaryClass,
    DecisionEvidence,
    FloorClass,
    LabelOrigin,
    ReviewRoute,
    TeacherComparison,
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
from im.generation.phase2_timer_wave2 import build_timer_wave2_plan
from im.generation.phase2_timer_wave2_packet import (
    DEFAULT_TIMER_WAVE2_PACKET_OUTPUT,
    _execute,
    _execute_rollovers,
    _packet,
    _program_specs,
    _validate_executed,
)
from im.generation.publication import publish_directory_transaction
from im.license import Allowed, Blocked, check
from im.policy.prompted import ModelPricing
from im.probes.harness.batch import (
    BatchShard,
    BatchWorkItem,
    decode_batch_completion,
    parse_batch_artifacts,
)
from im.probes.harness.cost import usage_cost
from im.probes.harness.models import HarnessProtocol, ProviderUsage
from im.schema.actions import ACTION_ADAPTER, SkipAction

_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_TIMER_WAVE2_EXECUTION = _ROOT / "review" / "phase2" / "timer-wave-2-execution"
DEFAULT_TIMER_WAVE2_REVIEW_OUTPUT = DEFAULT_TIMER_WAVE2_EXECUTION / "review"
_EXPECTED_DECISIONS = 698
_EXPECTED_CANDIDATES = 46
_EXPECTED_SOURCE_UNITS = 45
_EXPECTED_SOURCE_ENTRIES = 46
_SHARD_COUNT = 17


class TimerWave2ReviewError(ValueError):
    """Completed Wave-2 artifacts cannot be bound safely for owner review."""


@dataclass(frozen=True, slots=True)
class TimerWave2ReviewPacket:
    files: dict[str, bytes]
    review_count: int
    non_equivalent_count: int
    cluster_count: int
    individual_queue_count: int


async def materialize_timer_wave2_review_packet(
    output: Path = DEFAULT_TIMER_WAVE2_REVIEW_OUTPUT,
    *,
    execution_root: Path = DEFAULT_TIMER_WAVE2_EXECUTION,
    repository_root: Path = _ROOT,
) -> TimerWave2ReviewPacket:
    """Regenerate signed parents, retain provider bytes, and publish one review packet."""
    root = repository_root.resolve()
    registry = load_timer_wave0_inputs(
        approved_root=root / "review" / "phase1" / "approved",
        selection_contract_path=root / "spec" / "phase2-selection-v1.json",
    )
    candidate_plan = build_timer_wave2_plan(repository_root=root)
    with TemporaryDirectory(prefix="phase2-timer-wave2-review-") as temporary:
        directory = Path(temporary)
        executed = await _execute(_program_specs(registry), directory, root)
        executed += await _execute_rollovers(registry, directory, root)
        _validate_executed(executed, root)
        planned = _packet(executed, candidate_plan.files["plan.json"], root)
        retained_files = _retained_planned_files(
            root / DEFAULT_TIMER_WAVE2_PACKET_OUTPUT.relative_to(_ROOT), planned.files
        )
        packet = build_timer_wave2_review_packet(
            executed,
            retained_files,
            planned_items=planned.items,
            planned_shards=planned.shards,
            execution_root=execution_root.resolve(),
            repository_root=root,
        )
    publish_directory_transaction(output, packet.files)
    return packet


def build_timer_wave2_review_packet(
    executed: tuple[object, ...],
    planned_files: dict[str, bytes],
    *,
    planned_items: tuple[BatchWorkItem, ...],
    planned_shards: tuple[BatchShard, ...],
    execution_root: Path,
    repository_root: Path = _ROOT,
) -> TimerWave2ReviewPacket:
    if len(executed) != _EXPECTED_CANDIDATES:
        raise TimerWave2ReviewError("Wave-2 review requires all 46 candidate units")
    plan_bytes = planned_files.get("teacher-plan.json")
    if not isinstance(plan_bytes, bytes):
        raise TimerWave2ReviewError("Wave-2 review requires the canonical teacher plan")
    plan = _canonical_object(plan_bytes, "teacher plan")
    provider_files, provider_evidence = _provider_files(execution_root, repository_root)
    comparison = _canonical_object(provider_files["provider/comparison.json"], "comparison")
    targets = _targets(plan)
    _reconcile_provider_outputs(
        planned_items,
        planned_shards,
        targets,
        provider_files,
        comparison,
        packet_sha256=_digest(planned_files["SHA256SUMS"]),
    )
    rows = comparison.get("rows")
    if (
        not isinstance(rows, list)
        or len(rows) != _EXPECTED_DECISIONS
        or comparison.get("request_count") != _EXPECTED_DECISIONS
    ):
        raise TimerWave2ReviewError("provider comparison does not close over 698 decisions")
    if comparison.get("actual_usd") != "4.40614581250":
        raise TimerWave2ReviewError("Wave-2 provider cost drifted from the completed execution")

    by_stream = {item.parent.stream.sha256: item for item in executed}
    if len(by_stream) != _EXPECTED_CANDIDATES:
        raise TimerWave2ReviewError("regenerated Wave-2 parents are not unique")
    output_hashes = _output_hashes(provider_files)
    inputs = _projection_inputs(
        rows,
        targets,
        by_stream,
        output_hashes,
        comparison_sha256=_digest(provider_files["provider/comparison.json"]),
    )
    routes = _review_routes(inputs)
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
        blind_seed="phase2-timer-wave2-review-blind-v1",
    )
    review = parse_phase2_review_evidence(review_bytes)
    decisions = review["decisions"]
    clusters = review["clusters"]
    assert isinstance(decisions, list) and isinstance(clusters, list)
    non_equivalent_count = sum(item["comparison"] != "equivalent" for item in decisions)
    clustered_count = sum(len(item["member_identities"]) for item in clusters)
    review_count = sum(
        bool(item["review_evidence"]["review_route"]["review_required"])
        for item in decisions
    )
    individual_queue_count = non_equivalent_count - clustered_count

    source_index = _source_index(executed)
    files = {
        "README.md": _readme(
            decision_count=len(decisions),
            source_count=_EXPECTED_SOURCE_UNITS,
            review_count=review_count,
            non_equivalent_count=non_equivalent_count,
            cluster_count=len(clusters),
            individual_queue_count=individual_queue_count,
        ).encode(),
        "manifest.json": PackageManifest.build(item.parent for item in executed).canonical_bytes,
        "source-index.json": canonical_artifact_bytes(source_index),
        "phase2-review-evidence.json": review_bytes,
        "provider-evidence.json": provider_evidence,
        "review-packet.json": canonical_artifact_bytes(
            {
                "format_version": 1,
                "kind": "phase2-timer-wave2-owner-review",
                "owner_dispositions_present": False,
                "provider_evidence_sha256": _digest(provider_evidence),
                "review_evidence_sha256": _digest(review_bytes),
            }
        ),
        "teacher-plan.json": plan_bytes,
        "raw-streams.json": planned_files["raw-streams.json"],
        **{
            path: value
            for path, value in planned_files.items()
            if path.startswith("teacher-input/")
        },
        **_runtime_files(executed),
        **provider_files,
    }
    return TimerWave2ReviewPacket(
        files={**files, "SHA256SUMS": _checksums(files)},
        review_count=review_count,
        non_equivalent_count=non_equivalent_count,
        cluster_count=len(clusters),
        individual_queue_count=individual_queue_count,
    )


@dataclass(frozen=True, slots=True)
class _ProjectionInput:
    decision: DecisionEvidence
    static_d2_route: dict[str, object]
    oracle_license: CandidateLicense
    teacher_license: CandidateLicense
    oracle_provenance: dict[str, str]
    teacher_provenance: dict[str, str]
    priority_rank: int


def _projection_inputs(
    rows: list[object],
    targets: dict[str, dict[str, object]],
    by_stream: dict[str, object],
    output_hashes: dict[int, str],
    comparison_sha256: str,
) -> tuple[_ProjectionInput, ...]:
    inputs = []
    seen: set[str] = set()
    for priority_rank, raw in enumerate(rows):
        if not isinstance(raw, dict):
            raise TimerWave2ReviewError("provider comparison row is malformed")
        custom_id = raw.get("custom_id")
        if not isinstance(custom_id, str) or custom_id in seen or custom_id not in targets:
            raise TimerWave2ReviewError("provider comparison custom IDs do not close over plan")
        seen.add(custom_id)
        target = targets[custom_id]
        stream_sha256 = target.get("stream_sha256")
        index = target.get("program_action_index")
        shard_index = raw.get("shard_index")
        if (
            raw.get("target") != target
            or raw.get("oracle_action") != target.get("oracle_action")
            or not isinstance(stream_sha256, str)
            or stream_sha256 not in by_stream
            or isinstance(index, bool)
            or not isinstance(index, int)
            or isinstance(shard_index, bool)
            or not isinstance(shard_index, int)
            or shard_index not in output_hashes
        ):
            raise TimerWave2ReviewError(f"provider metadata drifted for {custom_id}")
        executed = by_stream[stream_sha256]
        if index not in executed.action_indices:
            raise TimerWave2ReviewError(f"decision escaped its candidate unit: {custom_id}")
        boundary = executed.parent.decision_boundaries[index]
        sidecar = executed.parent.sidecar.decisions[index]
        oracle = executed.parent.program.actions[index]
        if (
            oracle.model_dump(mode="json") != target["oracle_action"]
            or _digest(boundary.policy_bytes) != target.get("policy_prefix_sha256")
            or executed.spec.source_unit_id != target.get("source_unit_id")
        ):
            raise TimerWave2ReviewError(f"regenerated evidence drifted for {custom_id}")
        try:
            teacher = ACTION_ADAPTER.validate_python(raw.get("teacher_action"))
        except (TypeError, ValueError) as error:
            raise TimerWave2ReviewError(f"teacher action is invalid for {custom_id}") from error
        equivalent = teacher.model_dump(mode="json") == target["oracle_action"]
        if raw.get("comparison") != ("equivalent" if equivalent else "non_equivalent"):
            raise TimerWave2ReviewError(f"comparison classification drifted for {custom_id}")

        floor = (
            FloorClass.OPEN
            if sidecar.floor_open
            else FloorClass.OWNED
            if sidecar.floor_owned
            else FloorClass.CLOSED
        )
        risks = set()
        if isinstance(oracle, SkipAction):
            risks.add("skip_reason_selection")
        if executed.spec.checkpoint:
            risks.add("rollover_or_checkpoint_projection")
        if not equivalent:
            risks.add("oracle_teacher_non_equivalence")
        decision = DecisionEvidence(
            stream_sha256=stream_sha256,
            decision_policy_seq=sidecar.observed_policy_seq,
            wave_id="timer-wave-2",
            cell=TrustCellKey(HarnessProtocol.GENERATION, executed.parent.program.family, floor),
            template_id=executed.parent.program.template.asset_id,
            source_unit_id=executed.spec.source_unit_id,
            oracle_action=oracle,
            teacher_action=teacher,
            causal_state_class=executed.spec.kind,
            boundary_class=BoundaryClass.ORDINARY,
            risk_flags=tuple(sorted(risks)),
            rollover=executed.spec.kind.startswith("rollover_"),
        )
        static_route = target.get("static_d2_route")
        if not isinstance(static_route, dict):
            raise TimerWave2ReviewError(f"static D2 route is missing for {custom_id}")
        inputs.append(
            _ProjectionInput(
                decision=decision,
                static_d2_route=static_route,
                oracle_license=_license(oracle, boundary.license_view),
                teacher_license=_license(teacher, boundary.license_view),
                oracle_provenance={
                    "sidecar_sha256": executed.parent.sidecar.sha256,
                    "stream_sha256": stream_sha256,
                },
                teacher_provenance={
                    "comparison_sha256": comparison_sha256,
                    "custom_id": custom_id,
                    "provider_output_sha256": output_hashes[shard_index],
                    "request_body_sha256": _required_digest(target, "request_body_sha256"),
                },
                priority_rank=priority_rank,
            )
        )
    if len(seen) != len(targets):
        raise TimerWave2ReviewError("provider comparison does not cover the plan")
    return tuple(inputs)


def _reconcile_provider_outputs(
    planned_items: tuple[BatchWorkItem, ...],
    planned_shards: tuple[BatchShard, ...],
    targets: dict[str, dict[str, object]],
    provider_files: dict[str, bytes],
    comparison: dict[str, object],
    *,
    packet_sha256: str,
) -> None:
    """Rebuild the signed comparison from retained raw Batch artifacts."""
    if (
        len(planned_items) != _EXPECTED_DECISIONS
        or len(planned_shards) != _SHARD_COUNT
        or tuple(item for shard in planned_shards for item in shard.items) != planned_items
    ):
        raise TimerWave2ReviewError("planned Batch inventory is incomplete")
    rows = []
    batch_ids = []
    usage = ProviderUsage()
    for shard in planned_shards:
        prefix = f"provider/shards/{shard.shard_index:04d}"
        state = _canonical_object(
            provider_files[f"{prefix}/execution-state.json"], "execution state"
        )
        batch_id = state.get("batch_id")
        if (
            state.get("status") != "completed"
            or state.get("input_sha256") != shard.input_sha256
            or not isinstance(batch_id, str)
            or not batch_id
        ):
            raise TimerWave2ReviewError("provider execution state drifted")
        batch_ids.append(batch_id)
        artifacts = parse_batch_artifacts(
            shard.items,
            output_jsonl=provider_files[f"{prefix}/output.jsonl"],
            error_jsonl=provider_files[f"{prefix}/errors.jsonl"],
        )
        shard_rows = []
        for item in shard.items:
            target = targets[item.custom_id]
            decoded = decode_batch_completion(
                item,
                artifacts[item.custom_id],
                batch_id=batch_id,
                stage=shard.stage,
                shard_index=shard.shard_index,
            )
            usage += decoded.completion.usage
            teacher = decoded.completion.value
            oracle = target["oracle_action"]
            equivalent = (
                decoded.completion.outcome == "completed"
                and decoded.validation_error is None
                and teacher == oracle
            )
            reasons = _review_reasons(target, equivalent)
            shard_rows.append(
                {
                    "comparison": "equivalent" if equivalent else "non_equivalent",
                    "custom_id": item.custom_id,
                    "equivalence": equivalent,
                    "oracle_action": oracle,
                    "outcome": decoded.completion.outcome,
                    "review_reasons": reasons,
                    "review_required": bool(reasons),
                    "shard_index": shard.shard_index,
                    "target": target,
                    "teacher_action": teacher,
                    "validation_error": decoded.validation_error,
                }
            )
        stored_shard = _canonical_object(
            provider_files[f"{prefix}/comparison.json"], "shard comparison"
        )
        if stored_shard != {"rows": shard_rows}:
            raise TimerWave2ReviewError("raw provider output disagrees with shard comparison")
        rows.extend(shard_rows)
    expected = {
        "actual_usage": usage.as_json(),
        "actual_usd": format(
            usage_cost(
                usage,
                ModelPricing(model="gpt-5.6-terra"),
                billing_multiplier=Decimal("0.50"),
            ),
            "f",
        ),
        "batch_ids": batch_ids,
        "mandatory_review_count": sum(bool(row["review_required"]) for row in rows),
        "non_equivalent_count": sum(not bool(row["equivalence"]) for row in rows),
        "packet_sha256": packet_sha256,
        "request_count": len(rows),
        "rows": rows,
    }
    if comparison != expected:
        raise TimerWave2ReviewError("raw provider output disagrees with root comparison")


def _review_reasons(target: dict[str, object], equivalent: bool) -> list[str]:
    route = target.get("static_d2_route")
    if not isinstance(route, dict) or not isinstance(route.get("reasons"), list):
        raise TimerWave2ReviewError("signed static D2 route is invalid")
    reasons = list(route["reasons"])
    if route.get("review_required") and not reasons:
        reasons.append("static_d2_route")
    if not equivalent:
        reasons.append("teacher_oracle_disagreement")
    return list(dict.fromkeys(reasons))


def _review_routes(inputs: tuple[_ProjectionInput, ...]) -> tuple[ReviewRoute, ...]:
    """Preserve signed D2 sampling and add actual disagreements monotonically."""
    routes = []
    for input_ in inputs:
        if input_.decision.comparison is not TeacherComparison.EQUIVALENT:
            routes.append(
                route_wave(
                    (input_.decision,),
                    {},
                    sampling_seed="phase2-timer-wave2-d2-v1",
                )[0]
            )
            continue
        static = input_.static_d2_route
        required = static.get("review_required")
        route = ReviewRoute(
            identity=input_.decision.identity,
            review_required=required,
            mandatory=static.get("mandatory_review"),
            sample_rate=static.get("sample_rate"),
            reasons=tuple(static.get("reasons", ())),
            provisional_label_origin=(
                None if required else LabelOrigin.ORACLE_TEACHER_AGREEMENT
            ),
        )
        route.validate_for(input_.decision)
        routes.append(route)
    return tuple(routes)


def _provider_files(execution_root: Path, repository_root: Path) -> tuple[dict[str, bytes], bytes]:
    relative_paths = ["comparison.json", "plan.json"]
    for shard_index in range(_SHARD_COUNT):
        relative_paths.extend(
            f"shards/{shard_index:04d}/{name}"
            for name in (
                "comparison.json",
                "errors.jsonl",
                "execution-state.json",
                "output.jsonl",
                "provider-batch.json",
            )
        )
    files: dict[str, bytes] = {}
    inventory = []
    for relative_path in relative_paths:
        source = execution_root / relative_path
        if not source.is_file():
            raise TimerWave2ReviewError(f"provider artifact is missing: {relative_path}")
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
            "files": inventory,
            "format_version": 1,
            "kind": "phase2-timer-wave2-provider-evidence",
            "provider_comparison_sha256": _digest(files["provider/comparison.json"]),
        }
    )
    return files, evidence


def _output_hashes(provider_files: dict[str, bytes]) -> dict[int, str]:
    return {
        shard_index: _digest(
            provider_files[f"provider/shards/{shard_index:04d}/output.jsonl"]
        )
        for shard_index in range(_SHARD_COUNT)
    }


def _runtime_files(executed: tuple[object, ...]) -> dict[str, bytes]:
    files: dict[str, bytes] = {}
    for item in executed:
        stream = item.parent.stream.sha256.removeprefix("sha256:")
        for segment in item.parent.stream.segments:
            files[f"teacher/{stream}/{segment.sha256.removeprefix('sha256:')}.jsonl"] = (
                segment.policy_bytes
            )
        files[f"reviewer/{stream}/sidecar.json"] = item.parent.sidecar.canonical_bytes
        files[f"reviewer/{stream}/runtime-ledger.json"] = (
            item.parent.stream.final_ledger.canonical_bytes
        )
        if item.candidate is not None:
            files[f"reviewer/{stream}/checkpoint-selection.json"] = canonical_artifact_bytes(
                {
                    "checkpoint_seq": item.candidate.checkpoint_seq,
                    "format_version": 1,
                    "parent_sidecar_sha256": item.parent.sidecar.sha256,
                    "parent_stream_sha256": item.parent.stream.sha256,
                    "previous_segment_hash": item.candidate.previous_segment_hash,
                    "segment_index": item.candidate.segment_index,
                    "segment_sha256": item.candidate.segment.sha256,
                    "selected_call_indices": list(item.candidate.selected_call_indices),
                }
            )
    return files


def _source_index(executed: tuple[object, ...]) -> dict[str, object]:
    by_source: defaultdict[tuple[str, str], list[object]] = defaultdict(list)
    for item in executed:
        by_source[(item.spec.source_unit_id, item.parent.program.master_seed)].append(item)
    if (
        len(by_source) != _EXPECTED_SOURCE_ENTRIES
        or len({source_unit_id for source_unit_id, _ in by_source})
        != _EXPECTED_SOURCE_UNITS
    ):
        raise TimerWave2ReviewError("Wave-2 source identity inventory drifted")
    sources = []
    for (source_unit_id, _), members in sorted(by_source.items()):
        ordered = sorted(members, key=lambda item: item.parent.stream.sha256)
        first = ordered[0]
        checkpoint_candidates = [
            item.candidate.as_json_object()
            for item in ordered
            if item.candidate is not None
        ]
        if first.spec.checkpoint != (len(checkpoint_candidates) == len(ordered)):
            raise TimerWave2ReviewError("checkpoint source identity is incomplete")
        sources.append(
            {
                "checkpoint": (
                    None
                    if not checkpoint_candidates
                    else checkpoint_candidates[0]
                    if len(checkpoint_candidates) == 1
                    else {"candidates": checkpoint_candidates}
                ),
                "family": first.parent.program.family.value,
                "master_seed": first.parent.program.master_seed,
                "parent_stream_sha256s": [item.parent.stream.sha256 for item in ordered],
                "raw_source_sha256s": [
                    (
                        item.candidate.segment.sha256
                        if item.candidate is not None
                        else item.parent.stream.capture_sha256
                    )
                    for item in ordered
                ],
                "role": "timer_wave2_runtime_parent",
                "shape_id": first.spec.kind,
                "sidecar_sha256s": [item.parent.sidecar.sha256 for item in ordered],
                "source_decision_counts": [len(item.actions) for item in ordered],
                "source_kind": (
                    "checkpoint_segment" if first.spec.checkpoint else "runtime_parent"
                ),
                "source_unit_id": source_unit_id,
            }
        )
    return {
        # Review packet format generation, not the curriculum wave number.
        "batch": 1,
        "format_version": 1,
        "source_identity_rule": "source_unit_id groups complete Wave-2 candidate units",
        "sources": sources,
    }


def _retained_planned_files(packet_root: Path, current: dict[str, bytes]) -> dict[str, bytes]:
    retained = {
        path.relative_to(packet_root).as_posix(): path.read_bytes()
        for path in packet_root.rglob("*")
        if path.is_file()
    }
    if set(retained) != set(current):
        raise TimerWave2ReviewError("executed packet inventory drifted")
    for name in set(current) - {"SHA256SUMS", "teacher-plan.json"}:
        if retained[name] != current[name]:
            raise TimerWave2ReviewError(f"executed packet input drifted: {name}")

    old_plan = _canonical_object(retained["teacher-plan.json"], "retained teacher plan")
    new_plan = _canonical_object(current["teacher-plan.json"], "current teacher plan")
    if old_plan == new_plan:
        return retained
    old_bindings = old_plan.get("source_bindings")
    new_bindings = new_plan.get("source_bindings")
    if not isinstance(old_bindings, dict) or not isinstance(new_bindings, dict):
        raise TimerWave2ReviewError("executed packet source bindings are malformed")
    old_seals = old_bindings.get("approved_input_sha256")
    new_seals = new_bindings.get("approved_input_sha256")
    if not isinstance(old_seals, dict) or not isinstance(new_seals, dict):
        raise TimerWave2ReviewError("executed packet asset bindings are malformed")
    for key in ("registry.jsonl", "train-seal.json"):
        old_seals[key] = new_seals.get(key)
    if old_plan != new_plan:
        raise TimerWave2ReviewError(
            "executed packet drifted beyond cumulative TRAIN bindings"
        )
    return retained


def _targets(plan: dict[str, object]) -> dict[str, dict[str, object]]:
    raw = plan.get("targets")
    if not isinstance(raw, list):
        raise TimerWave2ReviewError("teacher plan has no targets")
    targets = {
        item["custom_id"]: item
        for item in raw
        if isinstance(item, dict) and isinstance(item.get("custom_id"), str)
    }
    if len(targets) != _EXPECTED_DECISIONS:
        raise TimerWave2ReviewError("teacher target inventory is incomplete")
    return targets


def _license(action: object, view: object) -> CandidateLicense:
    result = check(action, view)
    if isinstance(result, Allowed):
        return CandidateLicense("licensed", ())
    assert isinstance(result, Blocked)
    return CandidateLicense("blocked", (result.code,))


def _required_digest(value: dict[str, object], key: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item.startswith("sha256:") or len(item) != 71:
        raise TimerWave2ReviewError(f"{key} is not a digest")
    return item


def _canonical_object(data: bytes, label: str) -> dict[str, object]:
    try:
        value = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise TimerWave2ReviewError(f"{label} is not JSON") from error
    if not isinstance(value, dict) or canonical_artifact_bytes(value) != data:
        raise TimerWave2ReviewError(f"{label} is not canonical JSON")
    return value


def _digest(value: bytes) -> str:
    return f"sha256:{sha256(value).hexdigest()}"


def _checksums(files: dict[str, bytes]) -> bytes:
    return "".join(
        f"{sha256(data).hexdigest()}  {path}\n" for path, data in sorted(files.items())
    ).encode()


def _readme(
    *,
    decision_count: int,
    source_count: int,
    review_count: int,
    non_equivalent_count: int,
    cluster_count: int,
    individual_queue_count: int,
) -> str:
    return "\n".join(
        (
            "# Phase 2 timer Wave-2 owner review packet",
            "",
            "Completed provider output is bound to regenerated sealed TRAIN parents.",
            (
                f"Decisions: {decision_count}; source units: {source_count}; "
                f"review routes: {review_count}."
            ),
            (
                f"Non-equivalences: {non_equivalent_count}; D7 clusters: {cluster_count}; "
                f"unclustered disagreements: {individual_queue_count}."
            ),
            "Actual Batch cost: $4.40614581250.",
            "",
            "Candidates stay blinded until an owner disposition is saved.",
            "No owner disposition is included in this packet.",
            "",
        )
    )
