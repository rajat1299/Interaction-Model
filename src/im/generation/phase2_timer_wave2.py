"""Frozen, provider-free WP2-2 timer Wave-2 candidate plan."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_CEILING, Decimal
from hashlib import sha256
from pathlib import Path

from im.assets.model import canonical_artifact_bytes
from im.generation.phase2_selection import (
    SelectionContractError,
    WholeStreamEligibilityRecord,
    load_selection_contract,
    load_whole_stream_eligibility,
    validate_whole_stream_eligibility_sources,
)
from im.generation.publication import publish_directory_transaction

_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_TIMER_WAVE2_PLAN_OUTPUT = _ROOT / "review" / "phase2" / "timer-wave-2-plan"
DEFAULT_TIMER_WAVE1_ELIGIBILITY = (
    _ROOT
    / "review"
    / "phase2"
    / "timer-wave-1-execution"
    / "review"
    / "whole-stream-eligibility.json"
)
_SELECTION_CONTRACT_SHA256 = (
    "sha256:c1b8b1345bf289f27ae156e91ef71c145546710ae3c7222cd3cfe302b4208d97"
)
_PROMPT_V3_SHA256 = "sha256:31bea45fa5639c1eae8ad411779262d027bc705b499cf5eda3437a76a6d49ec9"
_EXCLUDED_STREAM_HASHES = (
    "sha256:f2f2beceb6faed2db08f12af235fdb1787a104a76e596862faa4e3933fb305c4",
    "sha256:ffa9c61e296a79556a2c47a7620d7e2243afc1ef46de8bbec62969e4bb7ae1f7",
)
_UNALLOCATED_TIMER_QUOTA = 570
_WAVE2_TARGET = 345

_VECTORS = {
    "normal_compact": {"idle": 4, "nudge": 6, "schedule": 4},
    "normal_wide": {"idle": 3, "nudge": 10, "schedule": 5},
    "cancel_checkpoint": {"cancel": 5, "idle": 7, "nudge": 2, "schedule": 2, "skip": 2},
    "contention_control": {"idle": 2, "mark": 2, "schedule": 2},
    "contention_checkpoint": {"cancel": 2, "idle": 4, "nudge": 6},
    "rollover_a": {"idle": 14, "integrate": 1, "mark": 1, "skip": 1},
    "rollover_b": {"idle": 13, "integrate": 1, "mark": 1, "skip": 1},
}
_ALLOCATION = (
    (
        "timer_creation_normal_fire",
        Decimal("1.7"),
        {"normal_compact": 3, "normal_wide": 6},
        {"normal_compact": 5, "normal_wide": 11},
    ),
    (
        "timer_cancel_quoting_stale_fire",
        Decimal("2.2"),
        {"cancel_checkpoint": 6},
        {"cancel_checkpoint": 14},
    ),
    (
        "timer_contention_backpressure",
        Decimal("1.7"),
        {"contention_checkpoint": 3, "contention_control": 3},
        {"contention_checkpoint": 5, "contention_control": 6},
    ),
    (
        "rollover_continuity",
        Decimal("2.2"),
        {"rollover_a": 1, "rollover_b": 1},
        {"rollover_a": 2, "rollover_b": 3},
    ),
)
_WAVE3_REMAINDER = {
    "timer_creation_normal_fire": {"idle": 20, "nudge": 52, "schedule": 28},
    "timer_cancel_quoting_stale_fire": {
        "cancel": 20,
        "idle": 28,
        "nudge": 8,
        "schedule": 8,
        "skip": 8,
    },
    "timer_contention_backpressure": {
        "cancel": 4,
        "idle": 12,
        "mark": 4,
        "nudge": 12,
        "schedule": 4,
    },
    "rollover_continuity": {"cancel": 1, "delegate": 1, "idle": 13, "nudge": 2},
}
_MULTIPLIER_RATIONALE = {
    "timer_creation_normal_fire": {
        "band": "standard",
        "multiplier": "1.7x",
        "reason": "two rejected template streams were repaired and passed scoped canaries",
    },
    "timer_cancel_quoting_stale_fire": {
        "band": "fragile",
        "multiplier": "2.2x",
        "reason": "duplicate and ambiguous-cancel boundaries remain intrinsically fragile",
    },
    "timer_contention_backpressure": {
        "band": "standard",
        "multiplier": "1.7x",
        "reason": "Wave-1 accepted all generated contention decisions",
    },
    "rollover_continuity": {
        "band": "fragile",
        "multiplier": "2.2x",
        "reason": "live checkpoint state and the confirmed span error require reserve",
    },
}


class TimerWave2PlanError(ValueError):
    """A frozen Wave-2 binding or allocation drifted."""


@dataclass(frozen=True, slots=True)
class TimerWave2Plan:
    """Offline plan files only; stream materialization is a separate bound step."""

    files: dict[str, bytes]


def build_timer_wave2_plan(
    *,
    repository_root: Path = _ROOT,
    selection_contract_path: Path | None = None,
    eligibility_path: Path | None = None,
    prompt_template_path: Path | None = None,
) -> TimerWave2Plan:
    """Build the whole-candidate-unit Wave-2 target without calling a provider."""
    root = repository_root.resolve()
    contract = load_selection_contract(
        selection_contract_path or root / "spec" / "phase2-selection-v1.json"
    )
    if contract.sha256 != _SELECTION_CONTRACT_SHA256:
        raise TimerWave2PlanError("Wave-2 selection-contract hash drifted")
    ledger = load_whole_stream_eligibility(eligibility_path or _eligibility_path(root))
    if ledger.selection_contract_sha256 != contract.sha256:
        raise TimerWave2PlanError("Wave-2 eligibility ledger binds a different selection contract")
    try:
        validate_whole_stream_eligibility_sources(ledger, root)
    except SelectionContractError as error:
        raise TimerWave2PlanError(str(error)) from error
    excluded = tuple(
        sorted(
            record.stream_sha256 for record in ledger.records if not record.whole_stream_accepted
        )
    )
    if excluded != _EXCLUDED_STREAM_HASHES:
        raise TimerWave2PlanError("Wave-2 eligibility exclusions drifted")

    prompt_hash = _digest_file(prompt_template_path or root / "spec" / "prompt-template-v3.txt")
    if prompt_hash != _PROMPT_V3_SHA256:
        raise TimerWave2PlanError("Wave-2 prompt-v3 hash drifted")

    allocation = _allocation()
    _validate_allocation(allocation)
    yield_reassessment = _yield_reassessment(ledger.records)
    payload = {
        "accepted_wave1_stream_count": len(ledger.accepted_records),
        "candidate_generation": allocation,
        "candidate_decision_count": sum(item["candidate_decisions"] for item in allocation),
        "candidate_stream_count": sum(item["candidate_streams"] for item in allocation),
        "eligibility_sidecar_sha256": _digest_file(ledger.path),
        "excluded_stream_hashes": list(_EXCLUDED_STREAM_HASHES),
        "final_selection": {
            "algorithm_execution": "deferred_until_all_accepted_streams_are_known",
            "candidate_unit": "complete_parent_or_complete_post_checkpoint_segment",
            "whole_stream_only": True,
        },
        "format_version": 2,
        "kind": "phase2-timer-wave2-candidate-plan-v2",
        "multiplier_basis": "whole_candidate_streams_not_response_text_or_decisions",
        "prompt_hash": prompt_hash,
        "selection_contract_sha256": contract.sha256,
        "unallocated_timer_quota": _UNALLOCATED_TIMER_QUOTA,
        "wave2_decision_target": _WAVE2_TARGET,
        "wave2_quota_fraction": "345/570",
        "wave3_remainder": _WAVE3_REMAINDER,
        "wave1_yield_reassessment": yield_reassessment,
        "wave_id": "timer-wave-2",
    }
    files = {"README.md": _readme(payload).encode(), "plan.json": canonical_artifact_bytes(payload)}
    return TimerWave2Plan({**files, "SHA256SUMS": _checksums(files)})


def materialize_timer_wave2_plan(
    output: Path = DEFAULT_TIMER_WAVE2_PLAN_OUTPUT,
    *,
    repository_root: Path = _ROOT,
) -> TimerWave2Plan:
    plan = build_timer_wave2_plan(repository_root=repository_root)
    publish_directory_transaction(output, plan.files)
    return plan


def _eligibility_path(root: Path) -> Path:
    return root / DEFAULT_TIMER_WAVE1_ELIGIBILITY.relative_to(_ROOT)


def _action_counts(shapes: dict[str, int]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for shape, amount in shapes.items():
        for action, count in _VECTORS[shape].items():
            counts[action] = counts.get(action, 0) + amount * count
    return dict(sorted(counts.items()))


def _decision_count(shapes: dict[str, int]) -> int:
    return sum(_action_counts(shapes).values())


def _allocation() -> list[dict[str, object]]:
    rows = []
    for family, multiplier, target_shapes, candidate_shapes in _ALLOCATION:
        target_streams = sum(target_shapes.values())
        candidate_streams = sum(candidate_shapes.values())
        rows.append(
            {
                "candidate_actions": _action_counts(candidate_shapes),
                "candidate_decisions": _decision_count(candidate_shapes),
                "candidate_shapes": candidate_shapes,
                "candidate_streams": candidate_streams,
                "family": family,
                "multiplier": f"{multiplier}x",
                "required_candidate_streams": int(
                    (Decimal(target_streams) * multiplier).to_integral_value(rounding=ROUND_CEILING)
                ),
                "target_actions": _action_counts(target_shapes),
                "target_decisions": _decision_count(target_shapes),
                "target_shapes": target_shapes,
                "target_streams": target_streams,
            }
        )
    return rows


def _yield_reassessment(
    records: tuple[WholeStreamEligibilityRecord, ...],
) -> dict[str, object]:
    observed: dict[str, dict[str, int]] = {}
    for record in records:
        family = str(record.features["family"])
        decisions = sum(record.action_counts["types"].values())
        row = observed.setdefault(family, {"accepted_decisions": 0, "generated_decisions": 0})
        row["generated_decisions"] += decisions
        if record.whole_stream_accepted:
            row["accepted_decisions"] += decisions
    expected = {
        "rollover_continuity": {"accepted_decisions": 8, "generated_decisions": 8},
        "timer_cancel_quoting_stale_fire": {
            "accepted_decisions": 26,
            "generated_decisions": 26,
        },
        "timer_contention_backpressure": {"accepted_decisions": 11, "generated_decisions": 11},
        "timer_creation_normal_fire": {"accepted_decisions": 5, "generated_decisions": 37},
    }
    if observed != expected:
        raise TimerWave2PlanError("Wave-1 accepted-decision yield drifted")
    return {
        family: {**counts, **_MULTIPLIER_RATIONALE[family]}
        for family, counts in sorted(observed.items())
    }


def _validate_allocation(allocation: list[dict[str, object]]) -> None:
    if sum(item["target_decisions"] for item in allocation) != _WAVE2_TARGET:
        raise TimerWave2PlanError("Wave-2 whole-stream targets do not sum to 345 decisions")
    if any(item["candidate_streams"] < item["required_candidate_streams"] for item in allocation):
        raise TimerWave2PlanError("Wave-2 candidate pool misses a whole-stream multiplier floor")
    if {item["family"]: item["target_actions"] for item in allocation} != {
        "timer_creation_normal_fire": {"idle": 30, "nudge": 78, "schedule": 42},
        "timer_cancel_quoting_stale_fire": {
            "cancel": 30,
            "idle": 42,
            "nudge": 12,
            "schedule": 12,
            "skip": 12,
        },
        "timer_contention_backpressure": {
            "cancel": 6,
            "idle": 18,
            "mark": 6,
            "nudge": 18,
            "schedule": 6,
        },
        "rollover_continuity": {"idle": 27, "integrate": 2, "mark": 2, "skip": 2},
    }:
        raise TimerWave2PlanError("Wave-2 family/action allocation drifted")
    rollover = next(item for item in allocation if item["family"] == "rollover_continuity")
    if (
        rollover["target_decisions"] != 33
        or sum(_WAVE3_REMAINDER["rollover_continuity"].values()) != 17
    ):
        raise TimerWave2PlanError("Wave-2 rollover is not the indivisible A+B allocation")


def _digest_file(path: Path) -> str:
    try:
        return f"sha256:{sha256(path.read_bytes()).hexdigest()}"
    except OSError as error:
        raise TimerWave2PlanError("Wave-2 bound input is unreadable") from error


def _checksums(files: dict[str, bytes]) -> bytes:
    return "".join(
        f"{sha256(data).hexdigest()}  {name}\n" for name, data in sorted(files.items())
    ).encode()


def _readme(payload: dict[str, object]) -> str:
    return "\n".join(
        (
            "# WP2-2 timer Wave-2 candidate plan",
            "",
            "This plan uses complete ordinary streams or complete post-checkpoint segments.",
            "The 345-decision target is the nearest whole-unit Wave-2 allocation to 60% of 570.",
            "Rollover C remains an exact 17-decision Wave-3 top-up.",
            f"Candidate pool: {payload['candidate_stream_count']} streams / "
            f"{payload['candidate_decision_count']} decisions.",
            "No provider call is performed by this artifact.",
            "",
        )
    )
