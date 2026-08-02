"""Close WP2-3 lookup/skip after the repaired Wave-2 pool."""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from im.assets.model import canonical_artifact_bytes
from im.generation.phase2_timer_wave3_chat_import import _verify_directory
from im.generation.publication import publish_directory_transaction
from im.schema.actions import ACTION_ADAPTER

_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_LOOKUP_CLOSEOUT_OUTPUT = _ROOT / "review" / "phase2" / "lookup-cluster-exit"
_WAVE0 = Path("review/phase2/lookup-wave-0-repair")
_WAVE1 = Path("review/phase2/lookup-wave-1-repaired")
_WAVE1_RESULTS = Path("review/phase2/lookup-wave-1-chat-results")
_WAVE1_REPAIR = Path("review/phase2/lookup-wave-1-repair-review")
_WAVE2 = Path("review/phase2/lookup-wave-2-repaired")
_WAVE2_EXECUTION = Path("review/phase2/lookup-wave-2-chat-repair-execution")
_SELECTION_CONTRACT = Path("spec/phase2-selection-v1.json")
_EXPECTED_WAVES = {"wave_0": (8, 76), "wave_1": (9, 70), "wave_2": (155, 702)}
_EXPECTED_FAMILY_DECISIONS = {
    "live_lookup_lifecycle": 378,
    "lookup_latency_duplicate_pressure": 310,
    "stale_result_opening_boundary": 160,
}
_EXPECTED_FAMILY_STREAMS = {
    "live_lookup_lifecycle": 77,
    "lookup_latency_duplicate_pressure": 26,
    "stale_result_opening_boundary": 69,
}
_EXPECTED_LABEL_ORIGIN = {
    "human": 172,
    "oracle_teacher_agreement": 676,
    "teacher_auto_trusted": 0,
}
_EXPECTED_RESERVOIR = {
    "both_legal_but_oracle_preferred": 56,
    "teacher_error": 30,
    "template_error": 10,
}


class LookupCloseoutError(ValueError):
    """Lookup evidence cannot satisfy the frozen WP2-3 exit criteria."""


@dataclass(frozen=True, slots=True)
class LookupCloseout:
    files: dict[str, bytes]
    decision_count: int
    reserve_decisions: int
    stream_count: int


def build_lookup_closeout(*, repository_root: Path = _ROOT) -> LookupCloseout:
    root = repository_root.resolve()
    bindings = {
        "wave0_packet_sha256": _verify_directory(root / _WAVE0),
        "wave1_packet_sha256": _verify_directory(root / _WAVE1),
        "wave1_repair_sha256": _verify_directory(root / _WAVE1_REPAIR),
        "wave2_packet_sha256": _verify_directory(root / _WAVE2),
        "wave2_execution_sha256": _verify_directory(root / _WAVE2_EXECUTION),
    }
    wave0 = _wave0_rows(root)
    wave1 = _target_rows(_object(root / _WAVE1 / "teacher-plan.json")["targets"], "wave_1")
    wave2 = _target_rows(_object(root / _WAVE2 / "teacher-plan.json")["targets"], "wave_2")
    rows = (*wave0, *wave1, *wave2)
    for wave, expected in _EXPECTED_WAVES.items():
        wave_rows = [row for row in rows if row["wave"] == wave]
        streams = {row["stream_sha256"] for row in wave_rows}
        if (len(streams), len(wave_rows)) != expected:
            raise LookupCloseoutError(f"{wave} accepted inventory drifted")
    if len({row["stream_sha256"] for row in rows}) != sum(
        value[0] for value in _EXPECTED_WAVES.values()
    ):
        raise LookupCloseoutError("lookup streams repeat across waves")

    accepted_streams = _accepted_streams(rows)
    coverage = _coverage(rows, accepted_streams, root)
    label_origin = _label_origin(root)
    reservoir = _reservoir(root, wave1, wave2)
    skip_audit = _skip_audit(rows)
    trust = _trust_ledger()
    report = {
        "accepted_pool": {
            "decision_count": len(rows),
            "stream_count": len(accepted_streams),
            "waves": {
                wave: {"decision_count": decisions, "stream_count": streams}
                for wave, (streams, decisions) in _EXPECTED_WAVES.items()
            },
        },
        "d7_binding_projection": {
            "chat_submission_labor": {
                "basis": (
                    "observed first-to-last downloaded round files for lookup Wave-1, "
                    "Wave-2, and the scoped Wave-2 repair"
                ),
                "counts_as_review_labor": True,
                "minimum_hours": 0.48,
                "minimum_minutes": 29,
                "round_count": 40,
            },
            "remaining_detailed_corpus_review_hours": {"high": 8, "low": 5},
            "status": "stop_rule_not_triggered",
            "stop_rule_hours": 12,
        },
        "evidence": bindings,
        "family_coverage": coverage["families"],
        "format_version": 1,
        "kind": "phase2-lookup-cluster-exit",
        "label_origin": label_origin,
        "repair_gate": {
            "contract_gaps": 0,
            "status": "passed",
            "wave2_repair_exact": 210,
            "wave2_repair_total": 224,
        },
        "reserve": coverage["reserve"],
        "skip_review": skip_audit,
        "status": "closed",
        "teacher_agreement_used_as_selection_feature": False,
        "trust": {
            "cleared_cell_count": 0,
            "state": "all_lookup_cells_uncleared",
            "teacher_auto_trusted_count": 0,
        },
        "wave_3": {
            "decision_count": 0,
            "reason": "all frozen family-action quotas and the whole-stream reserve are satisfied",
            "status": "targeted_top_up_not_required",
            "teacher_call_required": False,
        },
        "work_package": "WP2-3",
    }
    files = {
        "EXIT-REPORT.md": _markdown(report).encode(),
        "accepted-pool.json": canonical_artifact_bytes(
            {
                "format_version": 1,
                "kind": "phase2-lookup-accepted-pool",
                "streams": accepted_streams,
                "teacher_agreement_used_as_selection_feature": False,
            }
        ),
        "exit-report.json": canonical_artifact_bytes(report),
        "phase4-reservoir.jsonl": b"\n".join(
            canonical_artifact_bytes(row) for row in reservoir
        )
        + b"\n",
        "trust-ledger.json": canonical_artifact_bytes(trust),
    }
    files["SHA256SUMS"] = _checksums(files)
    return LookupCloseout(
        files,
        len(rows),
        coverage["reserve"]["decision_count"],
        len(accepted_streams),
    )


def materialize_lookup_closeout(
    output: Path = DEFAULT_LOOKUP_CLOSEOUT_OUTPUT,
    *,
    repository_root: Path = _ROOT,
) -> LookupCloseout:
    closeout = build_lookup_closeout(repository_root=repository_root)
    publish_directory_transaction(output, closeout.files)
    return closeout


def _wave0_rows(root: Path) -> tuple[dict[str, object], ...]:
    evidence = _object(root / _WAVE0 / "phase2-review-evidence.json")
    decisions = evidence.get("decisions")
    raw = _object(root / _WAVE0 / "raw-stream-evidence.json")
    logical = {
        stream["stream_sha256"]: stream["logical_stream_id"]
        for stream in raw.get("streams", [])
        if isinstance(stream, dict)
    }
    if not isinstance(decisions, list):
        raise LookupCloseoutError("Wave-0 decisions are absent")
    rows = []
    for decision in decisions:
        if not isinstance(decision, dict):
            raise LookupCloseoutError("Wave-0 decision is malformed")
        review = decision.get("review_evidence")
        trust = review.get("trust_cell") if isinstance(review, dict) else None
        route = review.get("review_route") if isinstance(review, dict) else None
        stream_sha = decision.get("stream_sha256")
        if (
            not isinstance(trust, dict)
            or not isinstance(route, dict)
            or not isinstance(stream_sha, str)
            or stream_sha not in logical
        ):
            raise LookupCloseoutError("Wave-0 review evidence is incomplete")
        rows.append(
            {
                "action": decision["oracle_action"],
                "family": trust["family"],
                "logical_stream_id": logical[stream_sha],
                "review_route": route,
                "stream_sha256": stream_sha,
                "wave": "wave_0",
            }
        )
    return tuple(rows)


def _target_rows(values: object, wave: str) -> tuple[dict[str, object], ...]:
    if not isinstance(values, list):
        raise LookupCloseoutError(f"{wave} targets are absent")
    rows = []
    for target in values:
        if not isinstance(target, dict):
            raise LookupCloseoutError(f"{wave} target is malformed")
        rows.append(
            {
                "action": target["oracle_action"],
                "custom_id": target["custom_id"],
                "family": target["family"],
                "logical_stream_id": target["logical_stream_id"],
                "review_route": target["static_d2_route"],
                "stream_sha256": target["stream_sha256"],
                "wave": wave,
            }
        )
    return tuple(rows)


def _accepted_streams(rows: tuple[dict[str, object], ...]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[(str(row["wave"]), str(row["stream_sha256"]))].append(row)
    streams = []
    for (wave, stream_sha), decisions in sorted(grouped.items()):
        families = {str(row["family"]) for row in decisions}
        logical = {str(row["logical_stream_id"]) for row in decisions}
        if len(families) != 1 or len(logical) != 1:
            raise LookupCloseoutError("stream metadata is inconsistent")
        streams.append(
            {
                "decision_count": len(decisions),
                "family": families.pop(),
                "logical_stream_id": logical.pop(),
                "stream_sha256": stream_sha,
                "wave": wave,
                "whole_stream_accepted": True,
            }
        )
    return streams


def _coverage(
    rows: tuple[dict[str, object], ...],
    streams: list[dict[str, object]],
    root: Path,
) -> dict[str, object]:
    contract = _object(root / _SELECTION_CONTRACT)
    quotas = contract.get("family_action_quotas")
    if not isinstance(quotas, dict):
        raise LookupCloseoutError("selection quotas are absent")
    actions: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        action = ACTION_ADAPTER.validate_python(row["action"])
        actions[str(row["family"])][action.type] += 1
    stream_counts = Counter(str(stream["family"]) for stream in streams)
    families = []
    reserve_total = 0
    for family in _EXPECTED_FAMILY_DECISIONS:
        family_target = quotas.get(family)
        if not isinstance(family_target, dict):
            raise LookupCloseoutError(f"{family} target is absent")
        accepted = actions[family]
        if any(accepted[action] < count for action, count in family_target.items()):
            raise LookupCloseoutError(f"{family} has an action quota deficit")
        accepted_decisions = sum(accepted.values())
        target_decisions = sum(family_target.values())
        reserve = accepted_decisions - target_decisions
        reserve_total += reserve
        families.append(
            {
                "accepted_actions": dict(sorted(accepted.items())),
                "accepted_decisions": accepted_decisions,
                "accepted_streams": stream_counts[family],
                "family": family,
                "reserve_decisions": reserve,
                "target_actions": family_target,
                "target_decisions": target_decisions,
                "target_satisfied": True,
            }
        )
    if (
        {row["family"]: row["accepted_decisions"] for row in families}
        != _EXPECTED_FAMILY_DECISIONS
        or dict(stream_counts) != _EXPECTED_FAMILY_STREAMS
        or reserve_total != 208
    ):
        raise LookupCloseoutError("lookup coverage or reserve drifted")
    reserve_contract = contract.get("reserve")
    if (
        not isinstance(reserve_contract, dict)
        or not int(reserve_contract["minimum_decisions"])
        <= reserve_total
        <= int(reserve_contract["maximum_decisions"])
    ):
        raise LookupCloseoutError("lookup reserve is outside the frozen band")
    return {
        "families": families,
        "reserve": {
            "decision_count": reserve_total,
            "maximum_decisions": reserve_contract["maximum_decisions"],
            "minimum_decisions": reserve_contract["minimum_decisions"],
            "status": "sufficient",
            "whole_streams_only": True,
        },
    }


def _label_origin(root: Path) -> dict[str, int]:
    proof = _object(root / _WAVE1_REPAIR / "repair-proof.json")
    wave1_non_equivalent = proof.get("teacher_recomparison", {}).get(  # type: ignore[union-attr]
        "non_equivalent_count"
    )
    comparison = _object(root / _WAVE2_EXECUTION / "comparison.json")
    wave2_non_equivalent = comparison.get("non_equivalent_count")
    if wave1_non_equivalent != 9 or wave2_non_equivalent != 87:
        raise LookupCloseoutError("lookup label evidence drifted")
    origins = {
        "human": 76 + int(wave1_non_equivalent) + int(wave2_non_equivalent),
        "oracle_teacher_agreement": (70 - int(wave1_non_equivalent))
        + (702 - int(wave2_non_equivalent)),
        "teacher_auto_trusted": 0,
    }
    if origins != _EXPECTED_LABEL_ORIGIN:
        raise LookupCloseoutError("lookup label-origin composition drifted")
    return {**origins, "total": sum(origins.values())}


def _skip_audit(rows: tuple[dict[str, object], ...]) -> dict[str, object]:
    reasons: Counter[str] = Counter()
    reviewed = 0
    for row in rows:
        action = ACTION_ADAPTER.validate_python(row["action"])
        if action.type != "skip":
            continue
        route = row["review_route"]
        if not isinstance(route, dict):
            raise LookupCloseoutError("skip route is malformed")
        mandatory = route.get("mandatory_review", route.get("mandatory"))
        if route.get("review_required") is not True or mandatory is not True:
            raise LookupCloseoutError("a skip decision escaped mandatory review")
        reasons[action.reason.value] += 1  # type: ignore[union-attr]
        reviewed += 1
    if reviewed != 103 or reasons != {"stale_tool_result": 89, "superseded_query": 14}:
        raise LookupCloseoutError("skip-reason review inventory drifted")
    return {
        "decision_count": reviewed,
        "reason_counts": dict(reasons),
        "reviewed_count": reviewed,
        "reviewed_fraction": 1.0,
        "status": "complete",
    }


def _reservoir(
    root: Path,
    wave1: tuple[dict[str, object], ...],
    wave2: tuple[dict[str, object], ...],
) -> list[dict[str, object]]:
    targets = {
        str(row["custom_id"]): row
        for row in (*wave1, *wave2)
        if isinstance(row.get("custom_id"), str)
    }
    teacher1 = _wave1_teacher_outputs(root)
    comparison2 = _object(root / _WAVE2_EXECUTION / "comparison.json")
    teacher2 = {
        row["custom_id"]: row["teacher_action"]
        for row in comparison2.get("rows", [])
        if isinstance(row, dict)
    }
    cases = {
        **_round_cases(root / _WAVE1),
        **_round_cases(root / _WAVE2),
    }
    records = []
    categories: Counter[str] = Counter()
    for custom_id, teacher in {**teacher1, **teacher2}.items():
        target = targets.get(custom_id)
        if target is None or teacher == target["action"]:
            continue
        category, reason = _category(custom_id)
        categories[category] += 1
        records.append(
            {
                "custom_id": custom_id,
                "direct_dpo_eligibility": False,
                "disagreement_category": category,
                "human_chosen_action": target["action"],
                "human_reason": reason,
                "policy_prefix": cases[custom_id],
                "rejected_action": teacher,
                "risk_flags": (
                    ["active_floor_response_boundary"]
                    if category == "both_legal_but_oracle_preferred"
                    else ["oracle_teacher_non_equivalence"]
                ),
                "source": "teacher_oracle_adjudication",
                "stream_identity": {
                    "logical_stream_id": target["logical_stream_id"],
                    "stream_sha256": target["stream_sha256"],
                    "wave": target["wave"],
                },
                "trust_cell": {
                    "family": target["family"],
                    "floor": (
                        "open"
                        if category == "both_legal_but_oracle_preferred"
                        else "closed"
                    ),
                    "protocol": "generation",
                },
            }
        )
    if categories != _EXPECTED_RESERVOIR or len(records) != 96:
        raise LookupCloseoutError("Phase-4 lookup reservoir composition drifted")
    return sorted(records, key=lambda row: str(row["custom_id"]))


def _wave1_teacher_outputs(root: Path) -> dict[str, object]:
    plan = _object(root / _WAVE1 / "teacher-plan.json")
    results = root / _WAVE1_RESULTS
    outputs = {}
    for round_ in plan.get("rounds", []):
        if not isinstance(round_, dict):
            raise LookupCloseoutError("Wave-1 round is malformed")
        filename = str(round_["output_filename"])
        matches = list(results.glob(f"{filename.removesuffix('.jsonl')}*.jsonl"))
        if len(matches) != 1:
            raise LookupCloseoutError(f"{filename} is missing or duplicated")
        rows = [json.loads(line) for line in matches[0].read_text().splitlines()]
        if [row.get("custom_id") for row in rows] != round_["case_ids"]:
            raise LookupCloseoutError(f"{filename} identities changed")
        for row in rows:
            outputs[str(row["custom_id"])] = ACTION_ADAPTER.validate_python(
                row["action"]
            ).model_dump(mode="json")
    if len(outputs) != 70:
        raise LookupCloseoutError("Wave-1 teacher output inventory is incomplete")
    return outputs


def _round_cases(packet: Path) -> dict[str, str]:
    cases = {}
    for path in sorted((packet / "rounds").glob("*.md")):
        try:
            block = path.read_text().split("<cases-jsonl>\n", 1)[1].split(
                "\n</cases-jsonl>", 1
            )[0]
        except IndexError as error:
            raise LookupCloseoutError(f"{path.name} has no case block") from error
        for line in block.splitlines():
            value = json.loads(line)
            cases[str(value["custom_id"])] = str(value["policy_stream"])
    return cases


def _category(custom_id: str) -> tuple[str, str]:
    if custom_id.startswith("t2lw1."):
        if custom_id == "t2lw1.duplicate-abandonment-00.d020.a1":
            return (
                "template_error",
                "Keep the approved natural standalone integration text.",
            )
        return (
            "teacher_error",
            "The teacher contradicts the owner-approved causal lookup state.",
        )
    if re.fullmatch(r"t2lw2\.a-\d{2}\.d(?:011|015)\.a1", custom_id):
        return (
            "teacher_error",
            "The teacher contradicts the explicitly retained pending lookup.",
        )
    if re.fullmatch(r"t2lw2\.b-\d{2}\.d020\.a1", custom_id):
        return (
            "template_error",
            "Keep the natural standalone result rather than an internal query heading.",
        )
    return (
        "both_legal_but_oracle_preferred",
        "D2 retains the human-authored or human-selected grounded response payload.",
    )


def _trust_ledger() -> dict[str, object]:
    return {
        "cells": [
            {
                "confirmed_teacher_errors": 0,
                "family": "live_lookup_lifecycle",
                "locked_uncleared": False,
                "protocol": "generation",
                "state": "uncleared",
            },
            {
                "confirmed_teacher_errors": 28,
                "family": "lookup_latency_duplicate_pressure",
                "locked_uncleared": True,
                "protocol": "generation",
                "state": "uncleared",
            },
            {
                "confirmed_teacher_errors": 2,
                "family": "stale_result_opening_boundary",
                "locked_uncleared": True,
                "protocol": "generation",
                "state": "uncleared",
            },
        ],
        "format_version": 1,
        "kind": "phase2-lookup-cluster-exit-trust-ledger",
        "notes": [
            "No lookup cell was promoted and no teacher output was auto-trusted.",
            "Confirmed directional teacher failures remain UNCLEARED under D1.",
        ],
        "trust_matrix_version": "phase2-trust-v1",
    }


def _markdown(report: dict[str, object]) -> str:
    coverage = report["family_coverage"]
    assert isinstance(coverage, list)
    names = {
        "live_lookup_lifecycle": "live lookup lifecycle",
        "lookup_latency_duplicate_pressure": "duplicate / latency pressure",
        "stale_result_opening_boundary": "stale-result / opening boundary",
    }
    table = "\n".join(
        f"| {names[str(row['family'])]} | {row['accepted_streams']} | "
        f"{row['accepted_decisions']} | {row['target_decisions']} | "
        f"{row['reserve_decisions']} | pass |"
        for row in coverage
        if isinstance(row, dict)
    )
    return f"""# WP2-3 lookup + skip cluster — exit report

Status: **closed**.

The accepted lookup pool contains **172 complete streams / 848 decisions**: Wave 0 contributes
8 / 76, Wave 1 contributes 9 / 70, and repaired Wave 2 contributes 155 / 702. Every frozen
family-action quota is met with a **208-decision whole-stream reserve**, so targeted Wave 3 is
correctly empty. Generating another teacher packet would not fill any coverage gap.

## Label origin

| Origin | Decisions |
|---|---:|
| `oracle_teacher_agreement` | 676 |
| `human` | 172 |
| `teacher_auto_trusted` | 0 |
| **Total** | **848** |

Teacher agreement was not used to select streams.

## Family coverage

| Family | Accepted streams | Accepted decisions | Frozen target | Reserve | Result |
|---|---:|---:|---:|---:|---|
{table}

Exact final 2,000-decision selection remains deferred to WP2-9.

## Skip review

All **103 skip decisions** received mandatory review: 89 `stale_tool_result` and 14
`superseded_query`. No skip-reason concern or contract gap remains.

## Trust and Phase-4 evidence

No lookup cell is promoted and no label is teacher-auto-trusted. The duplicate-pressure and
stale-boundary cells with confirmed teacher failures remain locked UNCLEARED. The 96 adjudicated
non-equivalent pairs are retained in `phase4-reservoir.jsonl` with
`direct_dpo_eligibility=false`.

## Binding D7 checkpoint

Remaining detailed interaction-corpus review is projected at **5–8 owner-hours**, below the
12-hour stop threshold, so the stop rule does not fire. This covers mark, response, idle completion,
and consolidation; replay and eval-gold hours remain separate D12 lines.

Manual Chat submission counts as review labor. The observed first-to-last download windows for
lookup Wave 1, Wave 2, and the scoped repair total a conservative minimum of **29 minutes
(0.48h)**; UI review and discussion time are additional and are not reconstructed from timestamps.
"""


def _object(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_bytes())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise LookupCloseoutError(f"{path} is unreadable") from error
    if not isinstance(value, dict):
        raise LookupCloseoutError(f"{path} is not an object")
    return value


def _checksums(files: dict[str, bytes]) -> bytes:
    return "".join(
        f"{sha256(data).hexdigest()}  {name}\n" for name, data in sorted(files.items())
    ).encode()
