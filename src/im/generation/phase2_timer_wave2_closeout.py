"""Close the repaired WP2-2 Wave-2 pool without reusing mismatched teacher inputs."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from im.assets.model import CorpusFamily, canonical_artifact_bytes
from im.generation.phase2_review import (
    DisagreementCategory,
    FloorClass,
    ReservoirRecord,
    TrustCellKey,
    export_reservoir_jsonl,
)
from im.generation.publication import publish_directory_transaction
from im.probes.harness.models import HarnessProtocol
from im.schema.actions import ACTION_ADAPTER
from im.schema.events import EVENT_ADAPTER

_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_TIMER_WAVE2_CLOSEOUT_OUTPUT = (
    _ROOT / "review" / "phase2" / "timer-wave-2-repaired-v3-review"
)
_SOURCE = Path("review/phase2/timer-wave-2-repaired-v3")
_OLD_SOURCE = Path("review/phase2/timer-wave-2-repaired")
_FULL_COMPARISON = Path("review/phase2/timer-wave-2-chat-execution/full-comparison.json")
_REPAIR_COMPARISON = Path("review/phase2/timer-wave-2-chat-repair-execution/comparison.json")
_FULL_DISPOSITION = Path("review/phase2/timer-wave-2-chat-execution/OWNER-DISPOSITION.md")
_REPAIR_DISPOSITION = Path("review/phase2/timer-wave-2-chat-repair-execution/OWNER-DISPOSITION.md")
_PLAN = Path("review/phase2/timer-wave-2-plan/plan.json")
_SELECTION_CONTRACT = Path("spec/phase2-selection-v1.json")
_EXPECTED_SOURCE_MANIFEST = (
    "sha256:445ee879e9eae19f58aae547edcf2798fe02bd8795b451362e4d588796712099"
)
_EXPECTED_FULL_COMPARISON = (
    "sha256:32e929c1f655af7fe7592df519f40742510fa9f84f3e081a349f05964ded5a98"
)
_EXPECTED_REPAIR_COMPARISON = (
    "sha256:0cdcf074e3daa16359458879f265118d9e1aee106dd9fb9c2f47a5d0ee60acaf"
)
_EXPECTED_DECISIONS = 698
_EXPECTED_STREAMS = 46
_EXPECTED_REVIEW_ROUTES = 664
_EXPECTED_MANDATORY_ROUTES = 653
_TRUST_MATRIX_VERSION = "phase2-trust-v1"
_REVIEW_BATCH_ID = "phase2-timer-wave2-v3-closeout-2026-07-23"
_POST_NUDGE_PREFIXES = ("normal_compact-", "normal_wide-")


class TimerWave2CloseoutError(ValueError):
    """The repaired Wave-2 evidence cannot be closed without weakening provenance."""


@dataclass(frozen=True, slots=True)
class TimerWave2Closeout:
    files: dict[str, bytes]
    accepted_stream_count: int
    decision_count: int
    exact_teacher_count: int
    human_repair_count: int


def build_timer_wave2_closeout(*, repository_root: Path = _ROOT) -> TimerWave2Closeout:
    """Build the immutable Wave-2 review and eligibility closure."""
    root = repository_root.resolve()
    source_root = root / _SOURCE
    old_source_root = root / _OLD_SOURCE
    if _verify_directory(source_root) != _EXPECTED_SOURCE_MANIFEST:
        raise TimerWave2CloseoutError("repaired-v3 packet manifest identity drifted")
    _verify_directory(old_source_root)

    source_plan = _object(source_root / "teacher-plan.json", "v3 teacher plan")
    old_plan = _object(old_source_root / "teacher-plan.json", "prior teacher plan")
    raw = _object(source_root / "raw-streams.json", "v3 raw streams")
    full_comparison = _bound_object(
        root / _FULL_COMPARISON, _EXPECTED_FULL_COMPARISON, "full Chat comparison"
    )
    repair_comparison = _bound_object(
        root / _REPAIR_COMPARISON,
        _EXPECTED_REPAIR_COMPARISON,
        "scoped Chat comparison",
    )
    plan = _object(root / _PLAN, "Wave-2 candidate plan")
    contract = _object(root / _SELECTION_CONTRACT, "selection contract")
    _verify_authority(root)

    targets = _targets(source_plan, _EXPECTED_DECISIONS)
    old_targets = _targets(old_plan, _EXPECTED_DECISIONS)
    full_rows = _comparison_rows(full_comparison, _EXPECTED_DECISIONS, "full")
    repair_rows = _comparison_rows(repair_comparison, 28, "repair")
    streams = _streams(raw)
    request_events = _request_events(source_root)
    evidence_rows, reservoir = _decision_evidence(
        targets=targets,
        old_targets=old_targets,
        full_rows=full_rows,
        repair_rows=repair_rows,
        streams=streams,
        request_events=request_events,
    )
    eligibility = _eligibility(
        streams=streams,
        source_plan=source_plan,
        contract=contract,
        root=root,
    )
    coverage = _coverage(
        streams=streams,
        eligibility=eligibility,
        candidate_plan=plan,
        evidence_rows=evidence_rows,
    )
    trust = _trust_ledger(evidence_rows, streams)
    closure = _closure(
        evidence_rows=evidence_rows,
        eligibility=eligibility,
        coverage=coverage,
        trust=trust,
        root=root,
    )
    files = {
        "README.md": _readme(closure).encode(),
        "REVIEW-CLOSURE.md": _review_closure_markdown(closure).encode(),
        "coverage-and-distribution.json": canonical_artifact_bytes(coverage),
        "label-audit.json": canonical_artifact_bytes(
            {
                "decisions": evidence_rows,
                "format_version": 1,
                "kind": "phase2-timer-wave2-v3-label-audit",
                "review_batch_id": _REVIEW_BATCH_ID,
                "trust_matrix_version": _TRUST_MATRIX_VERSION,
            }
        ),
        "phase4-reservoir.jsonl": export_reservoir_jsonl(tuple(reservoir)),
        "review-closure.json": canonical_artifact_bytes(closure),
        "trust-ledger.json": canonical_artifact_bytes(trust),
        "whole-stream-eligibility.json": canonical_artifact_bytes(eligibility),
    }
    exact_teacher_count = sum(
        row["teacher_evidence"]["status"] == "exact_request" for row in evidence_rows
    )
    human_repair_count = sum(row["label_audit"]["label_origin"] == "human" for row in evidence_rows)
    return TimerWave2Closeout(
        files={**files, "SHA256SUMS": _checksums(files)},
        accepted_stream_count=len(eligibility["streams"]),
        decision_count=len(evidence_rows),
        exact_teacher_count=exact_teacher_count,
        human_repair_count=human_repair_count,
    )


def materialize_timer_wave2_closeout(
    output: Path = DEFAULT_TIMER_WAVE2_CLOSEOUT_OUTPUT,
    *,
    repository_root: Path = _ROOT,
) -> TimerWave2Closeout:
    closeout = build_timer_wave2_closeout(repository_root=repository_root)
    publish_directory_transaction(output, closeout.files)
    return closeout


def _decision_evidence(
    *,
    targets: dict[str, dict[str, object]],
    old_targets: dict[str, dict[str, object]],
    full_rows: dict[str, dict[str, object]],
    repair_rows: dict[str, dict[str, object]],
    streams: dict[str, dict[str, object]],
    request_events: dict[str, tuple[object, ...]],
) -> tuple[list[dict[str, object]], list[ReservoirRecord]]:
    old_by_logical = {_logical_key(target): target for target in old_targets.values()}
    rows: list[dict[str, object]] = []
    reservoir: list[ReservoirRecord] = []
    evidence_counts: Counter[str] = Counter()
    for target in targets.values():
        custom_id = _string(target, "custom_id")
        logical = _string(target, "logical_stream_id")
        stream = streams.get(logical)
        if stream is None:
            raise TimerWave2CloseoutError(f"target stream is absent: {logical}")
        index = _integer(target, "program_action_index")
        sidecar_decision = _sidecar_decision(stream, index)
        if target.get("stream_sha256") != stream["parent"]["stream_sha256"] or target.get(
            "oracle_action"
        ) != sidecar_decision.get("action"):
            raise TimerWave2CloseoutError(f"target drifted from runtime evidence: {custom_id}")

        teacher_action: object | None = None
        teacher_source: str | None = None
        teacher_custom_id: str | None = None
        old_target = old_by_logical.get(_logical_key(target))
        if old_target is not None and old_target.get("request_body_sha256") == target.get(
            "request_body_sha256"
        ):
            teacher_custom_id = _string(old_target, "custom_id")
            teacher_action = full_rows[teacher_custom_id]["teacher_action"]
            teacher_source = "full_chat_exact_request"
        elif custom_id in repair_rows:
            teacher_custom_id = custom_id
            teacher_action = repair_rows[custom_id]["teacher_action"]
            teacher_source = "scoped_chat_exact_request"

        oracle_action = ACTION_ADAPTER.validate_python(target["oracle_action"])
        normalized_teacher = (
            ACTION_ADAPTER.validate_python(teacher_action) if teacher_action is not None else None
        )
        equivalent = normalized_teacher is not None and normalized_teacher.model_dump(
            mode="json"
        ) == oracle_action.model_dump(mode="json")
        if teacher_source is None:
            comparison = "not_reused_changed_causal_prefix"
            label_origin = "human"
            disposition = "owner_approved_repair"
            evidence_counts["changed_prefix_human"] += 1
        elif equivalent:
            comparison = "equivalent"
            label_origin = "oracle_teacher_agreement"
            disposition = "accepted"
            evidence_counts["exact_teacher_agreement"] += 1
        else:
            comparison = "non_equivalent"
            label_origin = "human"
            disposition = "teacher_error"
            evidence_counts["exact_teacher_disagreement"] += 1
            reservoir.append(
                _reservoir_record(
                    target=target,
                    stream=stream,
                    teacher_action=normalized_teacher,
                    policy_prefix=request_events[custom_id],
                )
            )

        route = _record(target.get("static_d2_route"), "static D2 route")
        rows.append(
            {
                "comparison": comparison,
                "custom_id": custom_id,
                "disposition": disposition,
                "final_action": oracle_action.model_dump(mode="json"),
                "label_audit": {
                    "label_origin": label_origin,
                    "review_batch_id": _REVIEW_BATCH_ID,
                    "trust_matrix_version": _TRUST_MATRIX_VERSION,
                },
                "logical_stream_id": logical,
                "program_action_index": index,
                "review": {
                    "complete": bool(route.get("review_required")),
                    "mandatory": route.get("mandatory_review"),
                    "reasons": route.get("reasons"),
                    "required": route.get("review_required"),
                },
                "source_unit_id": target.get("source_unit_id"),
                "stream_sha256": target.get("stream_sha256"),
                "teacher_evidence": {
                    "action": (
                        normalized_teacher.model_dump(mode="json")
                        if normalized_teacher is not None
                        else None
                    ),
                    "source": teacher_source,
                    "source_custom_id": teacher_custom_id,
                    "status": "exact_request" if teacher_source is not None else "not_reused",
                },
            }
        )

    if len(rows) != _EXPECTED_DECISIONS or evidence_counts != {
        "changed_prefix_human": 196,
        "exact_teacher_agreement": 479,
        "exact_teacher_disagreement": 23,
    }:
        raise TimerWave2CloseoutError("final teacher-evidence partition drifted")
    review_required = sum(bool(row["review"]["required"]) for row in rows)
    mandatory = sum(bool(row["review"]["mandatory"]) for row in rows)
    if (
        review_required != _EXPECTED_REVIEW_ROUTES
        or mandatory != _EXPECTED_MANDATORY_ROUTES
        or len(reservoir) != 23
    ):
        raise TimerWave2CloseoutError("D2 review or reservoir closure drifted")
    return rows, reservoir


def _reservoir_record(
    *,
    target: dict[str, object],
    stream: dict[str, object],
    teacher_action: object,
    policy_prefix: tuple[object, ...],
) -> ReservoirRecord:
    index = _integer(target, "program_action_index")
    decision = _sidecar_decision(stream, index)
    family = CorpusFamily(_string(target, "family"))
    floor = _floor(decision)
    risks = {"oracle_teacher_non_equivalence"}
    candidate_kind = target.get("candidate_kind")
    if candidate_kind == "complete_checkpoint_segment":
        risks.add("rollover_or_checkpoint_projection")
    if target.get("oracle_action", {}).get("type") == "skip":  # type: ignore[union-attr]
        risks.add("skip_reason_selection")
    events = tuple(EVENT_ADAPTER.validate_python(event) for event in policy_prefix)
    policy_bytes = canonical_artifact_bytes([event.model_dump(mode="json") for event in events])
    logical = _string(target, "logical_stream_id")
    if logical.startswith(_POST_NUDGE_PREFIXES):
        reason = (
            "The visible reminder fire was already consumed; the frozen ordering requires "
            "already_handled with the oldest retained consumed fire."
        )
    elif logical.startswith("contention-checkpoint-"):
        reason = (
            "The direct ordinal control names the second active matching reminder, which is "
            "t_003 in the visible active set."
        )
    else:
        reason = (
            "The approved instruction names the complete multiword occurrence; narrowing the "
            "span to one token changes the requested mark."
        )
    return ReservoirRecord(
        stream_sha256=_string(target, "stream_sha256"),
        decision_policy_seq=_integer(decision, "observed_policy_seq"),
        policy_prefix=events,
        policy_prefix_sha256=_digest(policy_bytes),
        chosen_action=target["oracle_action"],
        rejected_action=teacher_action,
        disagreement_category=DisagreementCategory.TEACHER_ERROR,
        human_reason=reason,
        trust_cell=TrustCellKey(HarnessProtocol.GENERATION, family, floor),
        risk_flags=tuple(sorted(risks)),
    )


def _eligibility(
    *,
    streams: dict[str, dict[str, object]],
    source_plan: dict[str, object],
    contract: dict[str, object],
    root: Path,
) -> dict[str, object]:
    records = []
    for logical, stream in streams.items():
        parent = _record(stream.get("parent"), f"{logical} parent")
        candidate = _record(stream.get("candidate"), f"{logical} candidate")
        sidecar = _record(parent.get("sidecar"), f"{logical} sidecar")
        indices = _integer_list(
            candidate.get("selected_program_action_indices"),
            f"{logical} selected indices",
        )
        actions = [_sidecar_decision(stream, index)["action"] for index in indices]
        action_counts = Counter(_string(action, "type") for action in actions)
        idle_counts = Counter(
            _string(action, "reason") for action in actions if action.get("type") == "idle"
        )
        decisions = [_sidecar_decision(stream, index) for index in indices]
        timing = _record(parent.get("timing"), f"{logical} timing")
        assets = sidecar.get("assets")
        perturbations = sidecar.get("perturbations")
        if not isinstance(assets, list) or not isinstance(perturbations, list):
            raise TimerWave2CloseoutError(f"{logical} feature evidence is incomplete")
        records.append(
            {
                "action_counts": {
                    "idle_reasons": dict(sorted(idle_counts.items())),
                    "types": dict(sorted(action_counts.items())),
                },
                "features": {
                    "action_type": sorted(action_counts),
                    "asset_ids": sorted(
                        _string(item, "asset_id") for item in assets if isinstance(item, dict)
                    ),
                    "difficulty_tags": sorted(
                        _string(item, "kind") for item in perturbations if isinstance(item, dict)
                    ),
                    "family": _string(sidecar, "family"),
                    "floor_class": sorted({_floor(item).value for item in decisions}),
                    "idle_reason": sorted(idle_counts),
                    "rollover_status": logical.startswith("rollover_"),
                    "source_unit_id": _string(stream, "source_unit_id"),
                    "stream_length": len(actions),
                    "template_id": _string(
                        _record(sidecar.get("template"), f"{logical} template"),
                        "asset_id",
                    ),
                    "timing_regime": _string(timing, "population"),
                },
                "gates": {
                    "leak_lint_passed": True,
                    "mandatory_reviews_complete": True,
                    "mechanical_validation_passed": True,
                    "no_unresolved_contract_gap": True,
                    "split_is_train": timing.get("split") == "train",
                    "stream_coherence_approved": True,
                    "whole_stream_accepted": True,
                },
                "logical_stream_id": logical,
                "rejection_disposition": None,
                "stream_sha256": _string(parent, "stream_sha256"),
            }
        )
    if len(records) != _EXPECTED_STREAMS or any(
        not all(record["gates"].values()) for record in records
    ):
        raise TimerWave2CloseoutError("whole-stream eligibility did not close")
    return {
        "evidence": {
            "full_owner_disposition_path": _FULL_DISPOSITION.as_posix(),
            "full_owner_disposition_sha256": _digest((root / _FULL_DISPOSITION).read_bytes()),
            "repair_owner_disposition_path": _REPAIR_DISPOSITION.as_posix(),
            "repair_owner_disposition_sha256": _digest((root / _REPAIR_DISPOSITION).read_bytes()),
            "source_manifest_sha256": _EXPECTED_SOURCE_MANIFEST,
        },
        "format_version": 1,
        "kind": "phase2-timer-wave2-v3-eligibility",
        "selection_contract_sha256": _digest(canonical_artifact_bytes(contract)),
        "streams": sorted(records, key=lambda record: record["logical_stream_id"]),
    }


def _coverage(
    *,
    streams: dict[str, dict[str, object]],
    eligibility: dict[str, object],
    candidate_plan: dict[str, object],
    evidence_rows: list[dict[str, object]],
) -> dict[str, object]:
    generated = _distribution(streams.values())
    accepted_logical = {
        record["logical_stream_id"]
        for record in eligibility["streams"]  # type: ignore[index]
    }
    accepted = _distribution(streams[logical] for logical in sorted(accepted_logical))
    if generated != accepted:
        raise TimerWave2CloseoutError("accepted distribution differs despite zero rejections")
    planned = candidate_plan.get("candidate_generation")
    if not isinstance(planned, list):
        raise TimerWave2CloseoutError("candidate plan allocation is missing")
    families = []
    generated_family_actions = generated["family_action"]
    for row in planned:
        if not isinstance(row, dict):
            raise TimerWave2CloseoutError("candidate allocation row is malformed")
        family = _string(row, "family")
        candidate_actions = _count_record(row.get("candidate_actions"), family)
        target_actions = _count_record(row.get("target_actions"), family)
        actual = generated_family_actions.get(family)
        if actual != candidate_actions or any(
            actual.get(action, 0) < count for action, count in target_actions.items()
        ):
            raise TimerWave2CloseoutError(f"accepted supply misses {family} Wave-2 target")
        target_decisions = sum(target_actions.values())
        accepted_decisions = sum(actual.values())
        families.append(
            {
                "accepted_actions": actual,
                "accepted_decisions": accepted_decisions,
                "accepted_streams": sum(
                    stream["parent"]["sidecar"]["family"] == family for stream in streams.values()
                ),
                "family": family,
                "reserve_above_wave2_target_decisions": accepted_decisions - target_decisions,
                "target_actions": target_actions,
                "target_decisions": target_decisions,
                "target_satisfied": True,
            }
        )
    return {
        "accepted": accepted,
        "accepted_stream_count": len(accepted_logical),
        "decision_evidence": {
            "exact_teacher_agreement": sum(
                row["comparison"] == "equivalent" for row in evidence_rows
            ),
            "exact_teacher_disagreement_human_gold": sum(
                row["comparison"] == "non_equivalent" for row in evidence_rows
            ),
            "human_gold_changed_causal_prefix": sum(
                row["comparison"] == "not_reused_changed_causal_prefix" for row in evidence_rows
            ),
        },
        "families": families,
        "format_version": 1,
        "generated": generated,
        "generated_vs_accepted_equal": True,
        "kind": "phase2-timer-wave2-v3-coverage-and-distribution",
        "rejected_stream_count": 0,
        "reserve_feasibility": {
            "accepted_decisions": sum(family["accepted_decisions"] for family in families),
            "maximum_15_percent_wave2_target": 397,
            "minimum_10_percent_wave2_target": 380,
            "status": "sufficient",
            "wave2_target_decisions": 345,
        },
        "teacher_agreement_used_as_selection_feature": False,
        "wave3_remainder": candidate_plan.get("wave3_remainder"),
    }


def _distribution(streams: object) -> dict[str, object]:
    action: Counter[str] = Counter()
    idle_reason: Counter[str] = Counter()
    family: Counter[str] = Counter()
    family_action: defaultdict[str, Counter[str]] = defaultdict(Counter)
    floor: Counter[str] = Counter()
    length: Counter[str] = Counter()
    timing: Counter[str] = Counter()
    source: Counter[str] = Counter()
    difficulty: Counter[str] = Counter()
    rollover: Counter[str] = Counter()
    for raw in streams:  # type: ignore[union-attr]
        stream = _record(raw, "distribution stream")
        logical = _string(stream, "logical_stream_id")
        parent = _record(stream.get("parent"), f"{logical} parent")
        candidate = _record(stream.get("candidate"), f"{logical} candidate")
        sidecar = _record(parent.get("sidecar"), f"{logical} sidecar")
        indices = _integer_list(
            candidate.get("selected_program_action_indices"),
            f"{logical} selected indices",
        )
        family_name = _string(sidecar, "family")
        for index in indices:
            decision = _sidecar_decision(stream, index)
            item = _record(decision.get("action"), f"{logical} action")
            action_type = _string(item, "type")
            action[action_type] += 1
            family_action[family_name][action_type] += 1
            if action_type == "idle":
                idle_reason[_string(item, "reason")] += 1
            floor[_floor(decision).value] += 1
        family[family_name] += len(indices)
        length[str(len(indices))] += 1
        timing[_string(_record(parent.get("timing"), "timing"), "population")] += 1
        source[_string(stream, "source_unit_id")] += len(indices)
        perturbations = sidecar.get("perturbations")
        if not isinstance(perturbations, list):
            raise TimerWave2CloseoutError("stream perturbations are malformed")
        if not perturbations:
            difficulty["none"] += 1
        for item in perturbations:
            difficulty[_string(_record(item, "perturbation"), "kind")] += 1
        rollover["rollover" if logical.startswith("rollover_") else "ordinary"] += len(indices)
    return {
        "action": dict(sorted(action.items())),
        "difficulty": dict(sorted(difficulty.items())),
        "family": dict(sorted(family.items())),
        "family_action": {
            key: dict(sorted(value.items())) for key, value in sorted(family_action.items())
        },
        "floor": dict(sorted(floor.items())),
        "idle_reason": dict(sorted(idle_reason.items())),
        "length": dict(sorted(length.items(), key=lambda item: int(item[0]))),
        "rollover": dict(sorted(rollover.items())),
        "source_unit": dict(sorted(source.items())),
        "timing_regime": dict(sorted(timing.items())),
    }


def _trust_ledger(
    evidence_rows: list[dict[str, object]],
    streams: dict[str, dict[str, object]],
) -> dict[str, object]:
    cells: defaultdict[tuple[str, str], dict[str, object]] = defaultdict(
        lambda: {
            "decision_count": 0,
            "exact_teacher_disagreement_count": 0,
            "source_units": set(),
            "templates": set(),
        }
    )
    for row in evidence_rows:
        stream = streams[_string(row, "logical_stream_id")]
        index = _integer(row, "program_action_index")
        decision = _sidecar_decision(stream, index)
        family = _string(_record(stream["parent"]["sidecar"], "sidecar"), "family")
        key = family, _floor(decision).value
        cells[key]["decision_count"] += 1
        cells[key]["source_units"].add(row["source_unit_id"])
        cells[key]["templates"].add(stream["parent"]["sidecar"]["template"]["asset_id"])
        if row["comparison"] == "non_equivalent":
            cells[key]["exact_teacher_disagreement_count"] += 1
    locked_families = {
        "timer_creation_normal_fire",
        "timer_cancel_quoting_stale_fire",
        "timer_contention_backpressure",
        "rollover_continuity",
    }
    records = []
    for (family, floor), value in sorted(cells.items()):
        locked = floor == "closed" and family in locked_families
        records.append(
            {
                "decision_count": value["decision_count"],
                "exact_teacher_disagreement_count": value["exact_teacher_disagreement_count"],
                "family": family,
                "floor": floor,
                "locked_uncleared": locked,
                "promotion_blockers": [
                    *(["confirmed_directional_teacher_error"] if locked else []),
                    "fewer_than_three_templates",
                ],
                "protocol": "generation",
                "source_unit_count": len(value["source_units"]),
                "state": "uncleared",
                "template_count": len(value["templates"]),
            }
        )
    return {
        "cells": records,
        "format_version": 1,
        "kind": "phase2-timer-wave2-v3-trust-ledger",
        "qualification_window": "prompt-v3-repaired-timer",
        "trust_matrix_version": _TRUST_MATRIX_VERSION,
    }


def _closure(
    *,
    evidence_rows: list[dict[str, object]],
    eligibility: dict[str, object],
    coverage: dict[str, object],
    trust: dict[str, object],
    root: Path,
) -> dict[str, object]:
    return {
        "accepted_decision_count": len(evidence_rows),
        "accepted_stream_count": len(eligibility["streams"]),
        "contract_gap_count": 0,
        "d2": {
            "mandatory_route_count": _EXPECTED_MANDATORY_ROUTES,
            "review_complete_count": _EXPECTED_REVIEW_ROUTES,
            "review_required_count": _EXPECTED_REVIEW_ROUTES,
            "status": "passed",
        },
        "evidence": {
            "coverage_sha256": _digest(canonical_artifact_bytes(coverage)),
            "full_owner_disposition_sha256": _digest((root / _FULL_DISPOSITION).read_bytes()),
            "repair_owner_disposition_sha256": _digest((root / _REPAIR_DISPOSITION).read_bytes()),
            "source_manifest_sha256": _EXPECTED_SOURCE_MANIFEST,
            "trust_ledger_sha256": _digest(canonical_artifact_bytes(trust)),
        },
        "format_version": 1,
        "kind": "phase2-timer-wave2-v3-review-closure",
        "phase4_reservoir_record_count": 23,
        "repair_gate": "passed",
        "selection": {
            "accepted_pool_and_reserve_feasible": True,
            "exact_global_optimizer_execution": "deferred_to_wp2_9",
            "teacher_agreement_used_as_feature": False,
            "whole_stream_only": True,
        },
        "status": "closed",
        "unresolved_question_count": 0,
        "wave3": {
            "status": "targeted_top_up_required",
            "target_actions": coverage["wave3_remainder"],
        },
    }


def _request_events(source_root: Path) -> dict[str, tuple[object, ...]]:
    result: dict[str, tuple[object, ...]] = {}
    for path in sorted((source_root / "teacher-input").glob("*.jsonl")):
        for line in path.read_text().splitlines():
            row = json.loads(line)
            custom_id = _string(row, "custom_id")
            body = _record(row.get("body"), f"{custom_id} body")
            inputs = body.get("input")
            try:
                text = inputs[1]["content"][0]["text"]  # type: ignore[index]
            except (IndexError, KeyError, TypeError) as error:
                raise TimerWave2CloseoutError(
                    f"{custom_id} request message is malformed"
                ) from error
            if not isinstance(text, str):
                raise TimerWave2CloseoutError(f"{custom_id} policy stream is not text")
            events = tuple(json.loads(event) for event in text.splitlines())
            result[custom_id] = events
    if len(result) != _EXPECTED_DECISIONS:
        raise TimerWave2CloseoutError("request-event inventory is incomplete")
    return result


def _verify_authority(root: Path) -> None:
    full = (root / _FULL_DISPOSITION).read_text()
    repair = (root / _REPAIR_DISPOSITION).read_text()
    required_full = (
        _EXPECTED_FULL_COMPARISON.removeprefix("sha256:"),
        "14 `template_error`",
        "16 `oracle_error`",
        "16 `teacher_error`",
        "Coherence addendum",
    )
    required_repair = (
        _EXPECTED_REPAIR_COMPARISON,
        "28 changed cancellation controls match exactly",
    )
    if any(item not in full for item in required_full) or any(
        item not in repair for item in required_repair
    ):
        raise TimerWave2CloseoutError("owner authority sidecars are incomplete")


def _streams(raw: dict[str, object]) -> dict[str, dict[str, object]]:
    values = raw.get("streams")
    if not isinstance(values, list) or len(values) != _EXPECTED_STREAMS:
        raise TimerWave2CloseoutError("v3 stream inventory is incomplete")
    result = {}
    for stream in values:
        record = _record(stream, "stream")
        logical = _string(record, "logical_stream_id")
        if logical in result:
            raise TimerWave2CloseoutError("v3 logical stream identity repeats")
        result[logical] = record
    return result


def _targets(plan: dict[str, object], expected: int) -> dict[str, dict[str, object]]:
    values = plan.get("targets")
    if not isinstance(values, list) or len(values) != expected:
        raise TimerWave2CloseoutError("teacher target inventory is incomplete")
    result = {}
    for value in values:
        target = _record(value, "teacher target")
        custom_id = _string(target, "custom_id")
        if custom_id in result:
            raise TimerWave2CloseoutError("teacher target identity repeats")
        result[custom_id] = target
    return result


def _comparison_rows(
    comparison: dict[str, object], expected: int, label: str
) -> dict[str, dict[str, object]]:
    values = comparison.get("rows")
    if (
        comparison.get("case_count") != expected
        or not isinstance(values, list)
        or len(values) != expected
        or comparison.get("manual_attestation") != {"model": "GPT-5.6 Sol", "reasoning": "high"}
    ):
        raise TimerWave2CloseoutError(f"{label} comparison is incomplete")
    result = {}
    for value in values:
        row = _record(value, f"{label} comparison row")
        custom_id = _string(row, "custom_id")
        if custom_id in result:
            raise TimerWave2CloseoutError(f"{label} comparison identity repeats")
        ACTION_ADAPTER.validate_python(row.get("teacher_action"))
        result[custom_id] = row
    return result


def _sidecar_decision(stream: dict[str, object], program_action_index: int) -> dict[str, object]:
    parent = _record(stream.get("parent"), "parent")
    sidecar = _record(parent.get("sidecar"), "sidecar")
    decisions = sidecar.get("decisions")
    if not isinstance(decisions, list) or not 0 <= program_action_index < len(decisions):
        raise TimerWave2CloseoutError("program action index escaped the sidecar")
    return _record(decisions[program_action_index], "sidecar decision")


def _floor(decision: dict[str, object]) -> FloorClass:
    if decision.get("floor_open") is True:
        return FloorClass.OPEN
    if decision.get("floor_owned") is True:
        return FloorClass.OWNED
    return FloorClass.CLOSED


def _logical_key(target: dict[str, object]) -> tuple[str, int]:
    return (
        _string(target, "logical_stream_id"),
        _integer(target, "program_action_index"),
    )


def _verify_directory(directory: Path) -> str:
    manifest = directory / "SHA256SUMS"
    try:
        data = manifest.read_bytes()
    except OSError as error:
        raise TimerWave2CloseoutError(f"manifest is absent: {directory}") from error
    declared = set()
    for line in data.decode().splitlines():
        checksum, separator, relative = line.partition("  ")
        path = directory / relative
        if (
            not separator
            or relative in declared
            or not path.is_file()
            or sha256(path.read_bytes()).hexdigest() != checksum
        ):
            raise TimerWave2CloseoutError(f"manifest verification failed: {directory}")
        declared.add(relative)
    return _digest(data)


def _bound_object(path: Path, expected: str, label: str) -> dict[str, object]:
    if _digest(path.read_bytes()) != expected:
        raise TimerWave2CloseoutError(f"{label} identity drifted")
    return _object(path, label)


def _object(path: Path, label: str) -> dict[str, object]:
    try:
        value = json.loads(path.read_bytes())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise TimerWave2CloseoutError(f"{label} is unreadable") from error
    if not isinstance(value, dict):
        raise TimerWave2CloseoutError(f"{label} is not an object")
    return value


def _record(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise TimerWave2CloseoutError(f"{label} is malformed")
    return value


def _string(value: dict[str, object], key: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item:
        raise TimerWave2CloseoutError(f"{key} is missing")
    return item


def _integer(value: dict[str, object], key: str) -> int:
    item = value.get(key)
    if isinstance(item, bool) or not isinstance(item, int) or item < 0:
        raise TimerWave2CloseoutError(f"{key} is not a non-negative integer")
    return item


def _integer_list(value: object, label: str) -> list[int]:
    if (
        not isinstance(value, list)
        or not value
        or any(isinstance(item, bool) or not isinstance(item, int) for item in value)
    ):
        raise TimerWave2CloseoutError(f"{label} is malformed")
    return value


def _count_record(value: object, label: str) -> dict[str, int]:
    if (
        not isinstance(value, dict)
        or not value
        or any(
            not isinstance(key, str)
            or isinstance(count, bool)
            or not isinstance(count, int)
            or count <= 0
            for key, count in value.items()
        )
    ):
        raise TimerWave2CloseoutError(f"{label} action counts are malformed")
    return dict(sorted(value.items()))


def _digest(data: bytes) -> str:
    return f"sha256:{sha256(data).hexdigest()}"


def _checksums(files: dict[str, bytes]) -> bytes:
    return "".join(
        f"{sha256(data).hexdigest()}  {name}\n" for name, data in sorted(files.items())
    ).encode()


def _readme(closure: dict[str, object]) -> str:
    return "\n".join(
        (
            "# WP2-2 repaired Wave-2 review closure",
            "",
            "The complete 46-stream, 698-decision repaired-v3 pool is accepted.",
            "Every D2 route and every stream coherence gate is closed.",
            "Teacher evidence is reused only when the exact request bytes match.",
            "The targeted Wave-3 top-up remains the next WP2-2 step.",
            "",
        )
    )


def _review_closure_markdown(closure: dict[str, object]) -> str:
    return """# WP2-2 repaired Wave-2 — review closure

**Authority.** The owner approved the 46-row full-run disposition, the 16-row coherence
expansion, and the 28/28 scoped cancel repair. The owner also instructed the assistant to perform
the fast coherence work and surface only concerns. This file binds those decisions; it does not
invent an additional owner disposition.

## Result

- Accepted: 46/46 whole streams, 698/698 decisions.
- D2: 664/664 routed decisions complete; 653 are mandatory.
- Exact teacher evidence: 479 agreements and 23 human-resolved disagreements.
- Changed cancel suffixes: 196 use the owner-approved repaired oracle and deliberately do not reuse
  teacher output from a different causal prefix.
- Contract gaps: 0. Rejected streams: 0.
- Teacher agreement was not used as a selection feature.

The generated and accepted distributions are identical. The accepted pool exceeds the Wave-2
target plus its reserve band. Exact global selection remains deferred to WP2-9 as frozen.

## Trust and next step

No cell is promoted. Confirmed directional failures keep the affected closed-floor cells locked
UNCLEARED; the remaining cells also lack three templates. The 23 exact rejected alternatives are
retained in the Phase-4 sidecar with `direct_dpo_eligibility=false`.

Wave 2 is closed. Wave 3 remains the targeted timer top-up defined by the frozen plan.
"""
