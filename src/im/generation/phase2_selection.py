"""Frozen Phase 2 corpus-selection contract validation.

The optimizer itself is intentionally deferred to WP2-9.  Candidate generation may begin only
after this contract validates and is committed; this module prevents a later implementation from
quietly adding teacher-derived selection features or drifting the frozen allocation.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from im.assets.model import CorpusFamily, canonical_artifact_bytes
from im.schema.actions import IdleReason


class SelectionContractError(ValueError):
    """The frozen Phase 2 selection contract is missing or internally inconsistent."""


_ACTION_TOTALS = {
    "cancel": 61,
    "delegate": 131,
    "idle": 1_000,
    "integrate": 112,
    "mark": 222,
    "nudge": 182,
    "respond": 90,
    "schedule": 100,
    "skip": 102,
}
_REQUIRED_FEATURES = (
    "family",
    "action_type",
    "idle_reason",
    "source_unit_id",
    "timing_regime",
    "floor_class",
    "template_id",
    "asset_ids",
    "difficulty_tags",
    "stream_length",
    "rollover_status",
)
_TEACHER_DERIVED = (
    "teacher_agreement",
    "teacher_action",
    "teacher_confidence",
    "teacher_label",
    "disagreement_category",
)
_ELIGIBILITY_GATES = (
    "split_is_train",
    "mechanical_validation_passed",
    "leak_lint_passed",
    "stream_coherence_approved",
    "mandatory_reviews_complete",
    "no_unresolved_contract_gap",
    "whole_stream_accepted",
)
_OBJECTIVE_TERMS = (
    "maximum_decisions_from_one_source_unit",
    "sum_squared_source_unit_counts",
    "sum_squared_template_counts_within_family",
    "sum_squared_timing_regime_counts_within_family",
    "sum_squared_floor_class_counts_within_family_action",
    "sum_squared_difficulty_tag_counts_within_family",
    "sum_squared_stream_length_bucket_counts_within_family",
    "candidate_order_rank_sum",
)
_TOP_LEVEL_KEYS = {
    "candidate_order",
    "eligibility",
    "family_action_quotas",
    "features",
    "forbidden_features",
    "format_version",
    "idle_reason_quotas",
    "objective",
    "reserve",
    "seed",
    "stream_length_buckets",
    "target_decisions",
    "whole_streams_only",
}


@dataclass(frozen=True, slots=True)
class SelectionContract:
    path: Path
    sha256: str
    seed: str
    target_decisions: int
    action_totals: dict[str, int]
    idle_reason_quotas: dict[str, int]


def load_selection_contract(path: Path) -> SelectionContract:
    """Load and fully validate the pre-generation selection contract."""
    raw, value = _read_contract(path)
    _validate_contract(value)
    return SelectionContract(
        path=path.resolve(),
        sha256=f"sha256:{sha256(raw).hexdigest()}",
        seed=str(value["seed"]),
        target_decisions=int(value["target_decisions"]),
        action_totals=_action_totals(value),
        idle_reason_quotas={
            str(reason): int(count)
            for reason, count in _mapping(value, "idle_reason_quotas").items()
        },
    )


def canonical_selection_contract_bytes(path: Path) -> bytes:
    """Return canonical bytes for a validated contract, for freeze reports."""
    _raw, contract = _read_contract(path)
    _validate_contract(contract)
    return canonical_artifact_bytes(contract)


def _read_contract(path: Path) -> tuple[bytes, dict[str, object]]:
    try:
        raw = path.read_bytes()
        value = json.loads(raw)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SelectionContractError("selection contract is not readable JSON") from error
    if not isinstance(value, dict):
        raise SelectionContractError("selection contract must be an object")
    return raw, value


def _validate_contract(value: dict[str, object]) -> None:
    if set(value) != _TOP_LEVEL_KEYS:
        raise SelectionContractError("selection contract top-level shape is not closed")
    if value.get("format_version") != 1:
        raise SelectionContractError("selection contract format_version must be 1")
    if value.get("target_decisions") != 2_000 or value.get("whole_streams_only") is not True:
        raise SelectionContractError("selection must target 2,000 decisions in whole streams")
    if not isinstance(value.get("seed"), str) or not str(value["seed"]).strip():
        raise SelectionContractError("selection seed must be non-empty")

    if value.get("candidate_order") != {
        "algorithm": "sha256",
        "input": "phase2-selection-v1|<seed>|<stream_sha256>|<decision_policy_seq>",
    }:
        raise SelectionContractError("candidate ordering differs from the frozen algorithm")
    if value.get("objective") != {
        "direction": "lexicographic_minimum",
        "terms": list(_OBJECTIVE_TERMS),
    }:
        raise SelectionContractError("selection objective differs from the frozen algorithm")
    if value.get("stream_length_buckets") != [
        {"maximum": 10, "minimum": 1, "name": "short"},
        {"maximum": 20, "minimum": 11, "name": "standard"},
    ]:
        raise SelectionContractError("stream-length buckets differ from the frozen contract")

    family_quotas = _mapping(value, "family_action_quotas")
    if set(family_quotas) != {family.value for family in CorpusFamily}:
        raise SelectionContractError("family quotas must cover the closed corpus-family set")
    family_total = 0
    for family, quotas in family_quotas.items():
        if not isinstance(quotas, dict) or not quotas:
            raise SelectionContractError(f"family {family} has no action quotas")
        for action, count in quotas.items():
            if action not in _ACTION_TOTALS or not _positive_int(count):
                raise SelectionContractError(f"family {family} has invalid {action} quota")
            family_total += count
    if family_total != 2_000 or _action_totals(value) != _ACTION_TOTALS:
        raise SelectionContractError("family/action quotas do not match the frozen allocation")

    idle_quotas = _mapping(value, "idle_reason_quotas")
    if set(idle_quotas) != {reason.value for reason in IdleReason}:
        raise SelectionContractError("idle quotas must cover the closed idle-reason set")
    if any(not _positive_int(count) for count in idle_quotas.values()):
        raise SelectionContractError("idle-reason quotas must be positive integers")
    if sum(idle_quotas.values()) != 1_000:
        raise SelectionContractError("idle-reason quotas must sum to exactly 1,000")

    features = value.get("features")
    forbidden = value.get("forbidden_features")
    if not isinstance(features, list) or tuple(features) != _REQUIRED_FEATURES:
        raise SelectionContractError("selection feature set differs from the frozen contract")
    if not isinstance(forbidden, list) or tuple(forbidden) != _TEACHER_DERIVED:
        raise SelectionContractError("teacher-derived forbidden features are incomplete")
    if set(features) & set(_TEACHER_DERIVED):
        raise SelectionContractError("teacher-derived evidence may not select the corpus")

    eligibility = value.get("eligibility")
    if not isinstance(eligibility, list) or tuple(eligibility) != _ELIGIBILITY_GATES:
        raise SelectionContractError("selection eligibility differs from the frozen gate set")
    reserve = _mapping(value, "reserve")
    if reserve != {
        "maximum_decisions": 300,
        "minimum_decisions": 200,
        "target_decisions": 250,
        "whole_streams_only": True,
    }:
        raise SelectionContractError("reserve must be the frozen 10-15% whole-stream band")


def _action_totals(value: dict[str, object]) -> dict[str, int]:
    totals = {action: 0 for action in _ACTION_TOTALS}
    for quotas in _mapping(value, "family_action_quotas").values():
        if not isinstance(quotas, dict):
            raise SelectionContractError("family action quotas must be objects")
        for action, count in quotas.items():
            if isinstance(action, str) and _positive_int(count):
                totals[action] = totals.get(action, 0) + count
    return dict(sorted(totals.items()))


def _mapping(value: dict[str, object], key: str) -> dict[str, object]:
    result = value.get(key)
    if not isinstance(result, dict):
        raise SelectionContractError(f"{key} must be an object")
    return result


def _positive_int(value: object) -> bool:
    return not isinstance(value, bool) and isinstance(value, int) and value > 0
