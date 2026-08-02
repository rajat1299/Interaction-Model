"""Frozen Phase 2 corpus-selection contract validation.

The optimizer itself is intentionally deferred to WP2-9.  Candidate generation may begin only
after this contract validates and is committed; this module prevents a later implementation from
quietly adding teacher-derived selection features or drifting the frozen allocation.
"""

from __future__ import annotations

import json
import re
from collections import Counter
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
_V1_TOP_LEVEL_KEYS = {
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
_V2_TOP_LEVEL_KEYS = _V1_TOP_LEVEL_KEYS | {"amendment", "supersedes"}
_V1_SHA256 = "sha256:c1b8b1345bf289f27ae156e91ef71c145546710ae3c7222cd3cfe302b4208d97"
_V2_SHA256 = "sha256:72e234e0767c5ea6e8a620e053746584cf7e9d546ba3d3dfeef929d209d85ea3"
_V2_IDLE_REASON_QUOTAS = {
    "already_handled": 70,
    "ambiguous": 50,
    "awaiting_opening": 100,
    "awaiting_tool": 100,
    "instruction_not_direct": 100,
    "no_trigger": 520,
    "typing_active": 60,
}
_V3_IDLE_REASON_QUOTAS = {
    "already_handled": 52,
    "ambiguous": 30,
    "awaiting_opening": 88,
    "awaiting_tool": 188,
    "instruction_not_direct": 72,
    "no_trigger": 540,
    "typing_active": 30,
}
_ELIGIBILITY_LEDGER_KEYS = {
    "format_version",
    "kind",
    "owner_evidence",
    "selection_contract_sha256",
    "source_evidence",
    "streams",
}
_ELIGIBILITY_RECORD_KEYS = {
    "action_counts",
    "features",
    "gates",
    "rejection_disposition",
    "stream_sha256",
}
_OWNER_EVIDENCE_KEYS = {
    "owner_disposition_path",
    "owner_disposition_sha256",
    "owner_export_sha256",
    "review_evidence_path",
    "review_evidence_sha256",
}
_SOURCE_EVIDENCE_KEYS = {
    "manifest_path",
    "manifest_sha256",
    "raw_streams_path",
    "raw_streams_sha256",
}
_ACTION_COUNT_KEYS = {"idle_reasons", "types"}
_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_EXCLUDED_TIMER_WAVE1_STREAMS = {
    "sha256:f2f2beceb6faed2db08f12af235fdb1787a104a76e596862faa4e3933fb305c4",
    "sha256:ffa9c61e296a79556a2c47a7620d7e2243afc1ef46de8bbec62969e4bb7ae1f7",
}


@dataclass(frozen=True, slots=True)
class SelectionContract:
    path: Path
    sha256: str
    seed: str
    target_decisions: int
    action_totals: dict[str, int]
    family_action_quotas: dict[str, dict[str, int]]
    idle_reason_quotas: dict[str, int]


@dataclass(frozen=True, slots=True)
class WholeStreamEligibilityRecord:
    """One all-or-nothing Wave-1 stream admission decision."""

    stream_sha256: str
    action_counts: dict[str, dict[str, int]]
    features: dict[str, object]
    gates: dict[str, bool]
    rejection_disposition: str | None

    @property
    def whole_stream_accepted(self) -> bool:
        return self.gates["whole_stream_accepted"]


@dataclass(frozen=True, slots=True)
class WholeStreamEligibilityLedger:
    """Closed owner-reviewed Wave-1 eligibility ledger, before selection exists."""

    path: Path
    selection_contract_sha256: str
    owner_evidence: dict[str, str]
    source_evidence: dict[str, str]
    records: tuple[WholeStreamEligibilityRecord, ...]

    @property
    def accepted_records(self) -> tuple[WholeStreamEligibilityRecord, ...]:
        return tuple(record for record in self.records if record.whole_stream_accepted)


def load_selection_contract(path: Path) -> SelectionContract:
    """Load and fully validate the pre-generation selection contract."""
    raw, value = _read_contract(path)
    _validate_contract(value)
    _validate_v2_evidence(value, path)
    return SelectionContract(
        path=path.resolve(),
        sha256=f"sha256:{sha256(raw).hexdigest()}",
        seed=str(value["seed"]),
        target_decisions=int(value["target_decisions"]),
        action_totals=_action_totals(value),
        family_action_quotas={
            family: {action: int(count) for action, count in quotas.items()}
            for family, quotas in _mapping(value, "family_action_quotas").items()
            if isinstance(family, str) and isinstance(quotas, dict)
        },
        idle_reason_quotas={
            str(reason): int(count)
            for reason, count in _mapping(value, "idle_reason_quotas").items()
        },
    )


def canonical_selection_contract_bytes(path: Path) -> bytes:
    """Return canonical bytes for a validated contract, for freeze reports."""
    _raw, contract = _read_contract(path)
    _validate_contract(contract)
    _validate_v2_evidence(contract, path)
    return canonical_artifact_bytes(contract)


def load_whole_stream_eligibility(path: Path) -> WholeStreamEligibilityLedger:
    """Load the closed, non-teacher-derived Wave-1 whole-stream eligibility ledger."""
    _raw, value = _read_contract(path)
    if set(value) != _ELIGIBILITY_LEDGER_KEYS:
        raise SelectionContractError("whole-stream eligibility top-level shape is not closed")
    if value.get("format_version") != 1 or value.get("kind") != "phase2-timer-wave1-eligibility-v1":
        raise SelectionContractError("whole-stream eligibility version differs from frozen ledger")
    selection_contract_sha256 = _digest_value(
        value.get("selection_contract_sha256"), "selection contract hash"
    )
    owner_evidence = _string_mapping(value.get("owner_evidence"), _OWNER_EVIDENCE_KEYS, "owner")
    source_evidence = _string_mapping(value.get("source_evidence"), _SOURCE_EVIDENCE_KEYS, "source")
    for key in (
        "owner_disposition_sha256",
        "owner_export_sha256",
        "review_evidence_sha256",
    ):
        _digest_value(owner_evidence[key], f"owner evidence {key}")
    for key in ("manifest_sha256", "raw_streams_sha256"):
        _digest_value(source_evidence[key], f"source evidence {key}")

    streams = value.get("streams")
    if not isinstance(streams, list) or not streams:
        raise SelectionContractError("whole-stream eligibility records must be a nonempty list")
    records = tuple(_eligibility_record(item) for item in streams)
    hashes = {record.stream_sha256 for record in records}
    if len(hashes) != len(records):
        raise SelectionContractError("whole-stream eligibility repeats a stream hash")
    if not _EXCLUDED_TIMER_WAVE1_STREAMS.issubset(hashes):
        raise SelectionContractError("whole-stream eligibility omits an owner-excluded stream")
    return WholeStreamEligibilityLedger(
        path=path.resolve(),
        selection_contract_sha256=selection_contract_sha256,
        owner_evidence=owner_evidence,
        source_evidence=source_evidence,
        records=records,
    )


def validate_whole_stream_eligibility_sources(
    ledger: WholeStreamEligibilityLedger, repository_root: Path
) -> None:
    """Fail closed if the ledger no longer describes its frozen Wave-1 evidence."""
    root = repository_root.resolve()
    owner_disposition = _verify_evidence_file(
        root,
        ledger.owner_evidence["owner_disposition_path"],
        ledger.owner_evidence["owner_disposition_sha256"],
    )
    if ledger.owner_evidence["owner_export_sha256"].encode("ascii") not in owner_disposition:
        raise SelectionContractError("owner export attestation is absent from owner disposition")
    _verify_evidence_file(
        root,
        ledger.owner_evidence["review_evidence_path"],
        ledger.owner_evidence["review_evidence_sha256"],
    )
    manifest_bytes = _verify_evidence_file(
        root,
        ledger.source_evidence["manifest_path"],
        ledger.source_evidence["manifest_sha256"],
    )
    raw_streams_bytes = _verify_evidence_file(
        root,
        ledger.source_evidence["raw_streams_path"],
        ledger.source_evidence["raw_streams_sha256"],
    )
    manifest = _json_object(manifest_bytes, "Wave-1 manifest")
    raw_streams = _json_object(raw_streams_bytes, "Wave-1 raw streams")
    manifest_streams = _stream_mapping(manifest.get("streams"), "Wave-1 manifest")
    raw_by_hash = _stream_mapping(raw_streams.get("streams"), "Wave-1 raw streams")
    if set(raw_by_hash) != {record.stream_sha256 for record in ledger.records}:
        raise SelectionContractError("whole-stream eligibility stream inventory drifted")
    for record in ledger.records:
        raw = raw_by_hash[record.stream_sha256]
        manifest_stream = manifest_streams.get(record.stream_sha256)
        if manifest_stream is None:
            raise SelectionContractError("whole-stream eligibility manifest stream is missing")
        _validate_record_sources(record, raw, manifest_stream)


def _read_contract(path: Path) -> tuple[bytes, dict[str, object]]:
    try:
        raw = path.read_bytes()
        value = json.loads(raw)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SelectionContractError("selection contract is not readable JSON") from error
    if not isinstance(value, dict):
        raise SelectionContractError("selection contract must be an object")
    return raw, value


def _eligibility_record(value: object) -> WholeStreamEligibilityRecord:
    if not isinstance(value, dict) or set(value) != _ELIGIBILITY_RECORD_KEYS:
        raise SelectionContractError("whole-stream eligibility record shape is not closed")
    stream_sha256 = _digest_value(value.get("stream_sha256"), "whole-stream hash")
    action_counts = value.get("action_counts")
    if not isinstance(action_counts, dict) or set(action_counts) != _ACTION_COUNT_KEYS:
        raise SelectionContractError("whole-stream action counts are not closed")
    action_types = _count_mapping(action_counts.get("types"), "action counts")
    idle_reasons = _count_mapping(
        action_counts.get("idle_reasons"), "idle-reason counts", allow_empty=True
    )
    if sum(action_types.values()) <= 0 or action_types.get("idle", 0) != sum(idle_reasons.values()):
        raise SelectionContractError("whole-stream action counts are inconsistent")
    if any(action not in _ACTION_TOTALS for action in action_types):
        raise SelectionContractError("whole-stream action count has an unknown action")

    features = value.get("features")
    if not isinstance(features, dict) or set(features) != set(_REQUIRED_FEATURES):
        raise SelectionContractError("whole-stream selection features are not closed")
    if set(features).intersection(_TEACHER_DERIVED):
        raise SelectionContractError("teacher-derived selection fields are forbidden")
    _validate_features(features, action_types, idle_reasons)

    gates = value.get("gates")
    if not isinstance(gates, dict) or set(gates) != set(_ELIGIBILITY_GATES):
        raise SelectionContractError("whole-stream eligibility gates differ from the frozen set")
    if any(not isinstance(gate, bool) for gate in gates.values()):
        raise SelectionContractError("whole-stream eligibility gates must be boolean")
    disposition = value.get("rejection_disposition")
    if disposition not in (None, "template_error"):
        raise SelectionContractError("whole-stream rejection disposition is invalid")
    accepted = gates["whole_stream_accepted"]
    prerequisites = (value for key, value in gates.items() if key != "whole_stream_accepted")
    if accepted and not all(prerequisites):
        raise SelectionContractError("accepted whole stream has a failed eligibility gate")
    if accepted != (disposition is None):
        raise SelectionContractError("whole-stream acceptance and disposition disagree")
    if stream_sha256 in _EXCLUDED_TIMER_WAVE1_STREAMS and (
        accepted or disposition != "template_error"
    ):
        raise SelectionContractError("owner-excluded stream can never be accepted")
    return WholeStreamEligibilityRecord(
        stream_sha256=stream_sha256,
        action_counts={"types": action_types, "idle_reasons": idle_reasons},
        features=dict(features),
        gates={key: gates[key] for key in _ELIGIBILITY_GATES},
        rejection_disposition=disposition,
    )


def _validate_features(
    features: dict[str, object], action_types: dict[str, int], idle_reasons: dict[str, int]
) -> None:
    if features["family"] not in {family.value for family in CorpusFamily}:
        raise SelectionContractError("whole-stream family feature is invalid")
    if features["action_type"] != sorted(action_types):
        raise SelectionContractError("whole-stream action-type feature disagrees with counts")
    if features["idle_reason"] != sorted(idle_reasons):
        raise SelectionContractError("whole-stream idle-reason feature disagrees with counts")
    if not isinstance(features["source_unit_id"], str) or not features["source_unit_id"]:
        raise SelectionContractError("whole-stream source-unit feature is invalid")
    if not isinstance(features["timing_regime"], str) or not features["timing_regime"]:
        raise SelectionContractError("whole-stream timing-regime feature is invalid")
    if not isinstance(features["template_id"], str) or not features["template_id"]:
        raise SelectionContractError("whole-stream template feature is invalid")
    for key in ("asset_ids", "difficulty_tags", "floor_class"):
        item = features[key]
        if not isinstance(item, list) or any(
            not isinstance(value, str) or not value for value in item
        ):
            raise SelectionContractError(f"whole-stream {key} feature is invalid")
        if item != sorted(set(item)):
            raise SelectionContractError(f"whole-stream {key} feature must be sorted and unique")
    if not _positive_int(features["stream_length"]):
        raise SelectionContractError("whole-stream length feature is invalid")
    if not isinstance(features["rollover_status"], bool):
        raise SelectionContractError("whole-stream rollover feature is invalid")


def _string_mapping(value: object, keys: set[str], label: str) -> dict[str, str]:
    if not isinstance(value, dict) or set(value) != keys:
        raise SelectionContractError(f"whole-stream {label} evidence shape is not closed")
    if any(not isinstance(item, str) or not item for item in value.values()):
        raise SelectionContractError(f"whole-stream {label} evidence must be nonempty strings")
    return {key: value[key] for key in keys}


def _count_mapping(value: object, label: str, *, allow_empty: bool = False) -> dict[str, int]:
    if (
        not isinstance(value, dict)
        or (not allow_empty and not value)
        or any(not isinstance(key, str) or not _positive_int(count) for key, count in value.items())
    ):
        raise SelectionContractError(f"whole-stream {label} must contain positive counts")
    return {key: value[key] for key in sorted(value)}


def _digest_value(value: object, label: str) -> str:
    if not isinstance(value, str) or _DIGEST.fullmatch(value) is None:
        raise SelectionContractError(f"{label} must be a sha256 digest")
    return value


def _verify_evidence_file(root: Path, relative: str, expected: str) -> bytes:
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts:
        raise SelectionContractError("whole-stream evidence path is unsafe")
    target = (root / path).resolve()
    if not target.is_relative_to(root):
        raise SelectionContractError("whole-stream evidence path escapes the repository")
    try:
        data = target.read_bytes()
    except OSError as error:
        raise SelectionContractError("whole-stream evidence file is unreadable") from error
    if f"sha256:{sha256(data).hexdigest()}" != expected:
        raise SelectionContractError("whole-stream evidence digest drifted")
    return data


def _json_object(data: bytes, label: str) -> dict[str, object]:
    try:
        value = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SelectionContractError(f"{label} is not readable JSON") from error
    if not isinstance(value, dict):
        raise SelectionContractError(f"{label} must be an object")
    return value


def _stream_mapping(value: object, label: str) -> dict[str, dict[str, object]]:
    if not isinstance(value, list):
        raise SelectionContractError(f"{label} streams must be a list")
    streams = {}
    for stream in value:
        if not isinstance(stream, dict):
            raise SelectionContractError(f"{label} stream is invalid")
        stream_sha256 = stream.get("stream_sha256")
        if not isinstance(stream_sha256, str) or stream_sha256 in streams:
            raise SelectionContractError(f"{label} stream hash is invalid")
        streams[stream_sha256] = stream
    return streams


def _validate_record_sources(
    record: WholeStreamEligibilityRecord,
    raw: dict[str, object],
    manifest: dict[str, object],
) -> None:
    sidecar = raw.get("sidecar")
    actions = raw.get("actions")
    if not isinstance(sidecar, dict) or not isinstance(actions, list):
        raise SelectionContractError("whole-stream raw evidence is invalid")
    decisions = sidecar.get("decisions")
    assets = sidecar.get("assets")
    template = sidecar.get("template")
    timing = manifest.get("timing")
    if (
        not isinstance(decisions, list)
        or not isinstance(assets, list)
        or not isinstance(template, dict)
        or not isinstance(timing, dict)
    ):
        raise SelectionContractError("whole-stream raw feature evidence is invalid")
    action_types = Counter(
        action.get("type")
        for action in actions
        if isinstance(action, dict) and isinstance(action.get("type"), str)
    )
    idle_reasons = Counter(
        action.get("reason")
        for action in actions
        if isinstance(action, dict)
        and action.get("type") == "idle"
        and isinstance(action.get("reason"), str)
    )
    expected_features = {
        "family": sidecar.get("family"),
        "action_type": sorted(action_types),
        "idle_reason": sorted(idle_reasons),
        "source_unit_id": raw.get("source_unit_id"),
        "timing_regime": timing.get("class"),
        "floor_class": sorted({_floor_class(item) for item in decisions if isinstance(item, dict)}),
        "template_id": template.get("asset_id"),
        "asset_ids": sorted(
            item.get("asset_id")
            for item in assets
            if isinstance(item, dict) and isinstance(item.get("asset_id"), str)
        ),
        "difficulty_tags": sorted(
            item.get("kind")
            for item in sidecar.get("perturbations", [])
            if isinstance(item, dict) and isinstance(item.get("kind"), str)
        ),
        "stream_length": len(actions),
        "rollover_status": sidecar.get("family") == "rollover_continuity",
    }
    expected_counts = {
        "types": dict(sorted(action_types.items())),
        "idle_reasons": dict(sorted(idle_reasons.items())),
    }
    if record.action_counts != expected_counts or record.features != expected_features:
        raise SelectionContractError("whole-stream evidence features or counts drifted")


def _floor_class(decision: dict[str, object]) -> str:
    if decision.get("floor_open") is True:
        return "open"
    if decision.get("floor_owned") is True:
        return "owned"
    return "closed"


def _validate_contract(value: dict[str, object]) -> None:
    version = value.get("format_version")
    expected_keys = _V1_TOP_LEVEL_KEYS if version == 1 else _V2_TOP_LEVEL_KEYS
    if set(value) != expected_keys:
        raise SelectionContractError("selection contract top-level shape is not closed")
    if version not in (1, 2, 3):
        raise SelectionContractError("selection contract format_version must be 1, 2, or 3")
    if version == 2:
        _validate_v2_amendment(value)
    if version == 3:
        _validate_v3_amendment(value)
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
    if version == 2 and idle_quotas != _V2_IDLE_REASON_QUOTAS:
        raise SelectionContractError("v2 idle-reason quotas differ from the owner amendment")
    if version == 3 and idle_quotas != _V3_IDLE_REASON_QUOTAS:
        raise SelectionContractError("v3 idle-reason quotas differ from the owner amendment")

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


def _validate_v2_amendment(value: dict[str, object]) -> None:
    if value.get("supersedes") != {
        "path": "spec/phase2-selection-v1.json",
        "sha256": _V1_SHA256,
    }:
        raise SelectionContractError("v2 must supersede the immutable v1 contract")
    amendment = value.get("amendment")
    if not isinstance(amendment, dict) or set(amendment) != {
        "changes",
        "decision_path",
        "decision_sha256",
        "rationale",
        "teacher_derived_evidence_used",
    }:
        raise SelectionContractError("v2 amendment shape is not closed")
    if amendment["changes"] != ["idle_reason_quotas"]:
        raise SelectionContractError("v2 may amend only the idle-reason quotas")
    _digest_value(amendment["decision_sha256"], "v2 owner decision hash")
    if (
        amendment["decision_path"]
        != "review/phase2/wp2-6-selection-v2-amendment/OWNER-DISPOSITION.md"
        or not isinstance(amendment["rationale"], str)
        or not amendment["rationale"].strip()
        or amendment["teacher_derived_evidence_used"] is not False
    ):
        raise SelectionContractError("v2 amendment authority or rationale is invalid")


def _validate_v3_amendment(value: dict[str, object]) -> None:
    if value.get("supersedes") != {
        "path": "spec/phase2-selection-v2.json",
        "sha256": _V2_SHA256,
    }:
        raise SelectionContractError("v3 must supersede the immutable v2 contract")
    amendment = value.get("amendment")
    if not isinstance(amendment, dict) or set(amendment) != {
        "changes",
        "decision_path",
        "decision_sha256",
        "rationale",
        "teacher_derived_evidence_used",
    }:
        raise SelectionContractError("v3 amendment shape is not closed")
    if amendment["changes"] != ["idle_reason_quotas"]:
        raise SelectionContractError("v3 may amend only the idle-reason quotas")
    _digest_value(amendment["decision_sha256"], "v3 owner decision hash")
    if (
        amendment["decision_path"]
        != "review/phase2/wp2-6-selection-v3-amendment/OWNER-DISPOSITION.md"
        or not isinstance(amendment["rationale"], str)
        or not amendment["rationale"].strip()
        or amendment["teacher_derived_evidence_used"] is not False
    ):
        raise SelectionContractError("v3 amendment authority or rationale is invalid")


def _validate_v2_evidence(value: dict[str, object], path: Path) -> None:
    version = value.get("format_version")
    if version not in (2, 3):
        return
    root = path.resolve().parent.parent
    supersedes = _mapping(value, "supersedes")
    amendment = _mapping(value, "amendment")
    _verify_contract_evidence(
        root,
        supersedes["path"],
        supersedes["sha256"],
        f"v{version - 1} contract",
    )
    _verify_contract_evidence(
        root,
        amendment["decision_path"],
        amendment["decision_sha256"],
        f"v{version} owner decision",
    )


def _verify_contract_evidence(
    root: Path, relative: object, expected: object, label: str
) -> None:
    if not isinstance(relative, str) or not isinstance(expected, str):
        raise SelectionContractError(f"{label} binding is invalid")
    target = (root / relative).resolve()
    if not target.is_relative_to(root):
        raise SelectionContractError(f"{label} path escapes the repository")
    try:
        data = target.read_bytes()
    except OSError as error:
        raise SelectionContractError(f"{label} is unreadable") from error
    if f"sha256:{sha256(data).hexdigest()}" != expected:
        raise SelectionContractError(f"{label} digest drifted")


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
