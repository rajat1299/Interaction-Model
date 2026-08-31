#!/usr/bin/env python3
"""Build the checksum-bound offline Phase 3X audit of frozen step-30 outputs."""

from __future__ import annotations

import argparse
import copy
import gzip
import json
import subprocess
from collections import defaultdict
from collections.abc import Mapping, Sequence
from hashlib import sha256
from pathlib import Path

from pydantic import ValidationError

from im.assets.model import canonical_artifact_bytes
from im.canonical_json import TimJsonError, canonicalize_tim_json, parse_tim_json
from im.generation.publication import publish_directory_transaction
from im.schema.actions import ACTION_ADAPTER
from im.schema.textspan import utf16_len
from im.training.phase3r import D10_ACTION_TYPES, TERMINAL_TOKEN_ID, classify_span_action

ROOT = Path(__file__).resolve().parents[1]
STEP30 = Path("review/phase3/wp3r-7-step30-planner-review-v1")
WP3_2 = Path("review/phase3/wp3-2-offline-candidate-v4")
GRADES = STEP30 / "step30-grades.jsonl"
INVENTORY = WP3_2 / "dev-state-inventory.jsonl.gz"
GRADER = WP3_2 / "grader-contract.json"
METRICS = STEP30 / "step30-metrics-pending-human.json"
RETENTION = STEP30 / "step30-retention-v3.json"
OUTPUT = Path("review/phase3/wp3x-1-step30-executable-audit-v1")
TERMINAL_TEXT = "<|im_end|>"
SPAN_POLICY = "unique-exact-text-lexical-v1"
APPROVED_R3_POLICY = "phase3r-span-canonicalization-r3-v1"
STEP30_MANIFEST_SHA256 = "1bad291e65d74c4465aa0e6b552ca33cddfc29ce0911ba795fe38307a3433b8f"
WP3_2_MANIFEST_SHA256 = "b26ce03fbf46de2ed0b75c71ca925b79dee3d42d77e05f323271ffd5125dcace"

OPEN_TEXT_FAIL = {
    "dev:a5a564738bd3f89bfc5c2012932f5332043d30e1a38d1e545d1c3fa66d47df47:1"
}
OPEN_TEXT_WRONG_CAUSAL = {
    "dev:54d1f184698905f78a5c5bb096934c4c019df6c2c1a765d00b170082c9b66a3d:22",
    "dev:637dbaef9a4a2ceae7c9974aebf7c90b597319593d5a1ce54f9a2251a2789670:22",
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    build(args.output, source_commit=args.source_commit)


def build(output: Path, *, source_commit: str) -> None:
    _verify_tracked_source(ROOT, source_commit)
    files, _ = _candidate_files(ROOT, source_commit)
    publish_directory_transaction(output, files)


def _candidate_files(root: Path, source_commit: str) -> tuple[dict[str, bytes], dict[str, object]]:
    step30_manifest = _verify_sha256sums(root / STEP30, STEP30_MANIFEST_SHA256)
    wp3_2_manifest = _verify_sha256sums(root / WP3_2, WP3_2_MANIFEST_SHA256)
    grades = _read_jsonl(root / GRADES)
    inventory = _read_jsonl_gzip(root / INVENTORY)
    grader = _read_json(root / GRADER)
    frozen_metrics = _read_json(root / METRICS)
    retention = _read_json(root / RETENTION)
    if not all(isinstance(value, Mapping) for value in (grader, frozen_metrics, retention)):
        raise ValueError("audit contracts are malformed")

    grades_by_id = _unique_rows(grades, "grade")
    states_by_id = _unique_rows(inventory, "inventory")
    if len(grades_by_id) != 300 or set(grades_by_id) != set(states_by_id):
        raise ValueError("grade/inventory identity closure is not exactly 300 states")
    rubrics = {
        str(row["state_id"]): row
        for row in _mapping_list(_mapping(grader, "open_text"), "rows")
    }

    rows: list[dict[str, object]] = []
    adjudications: list[dict[str, object]] = []
    for state in inventory:
        state_id = str(state["state_id"])
        grade = grades_by_id[state_id]
        raw_action = _authenticated_raw_action(grade)
        _verify_state_grade_identity(state, grade)
        _verify_union_grade(raw_action, grade)
        strict_match = _nested(grade, "executed", "match") is True
        manual = _open_text_adjudication(grade, rubrics.get(state_id))
        if manual is not None:
            adjudications.append(manual)
        texts, result_data = _state_facts(state)
        span_intent = _same_span_intent(state.get("expected_action"), raw_action)
        span_resolution = _resolve_exact_spans(raw_action, texts)
        approved_r3 = _approved_r3(state, raw_action, texts, strict_match)
        semantic = _semantic_status(state, raw_action, strict_match, manual, span_intent)
        resolution = _resolved_status(
            state,
            grade,
            raw_action,
            result_data,
            strict_match,
            manual,
            span_resolution,
        )
        cluster = _failure_cluster(state, grade, raw_action, strict_match, manual, span_intent)
        post_license = _post_license(state, grade, raw_action, strict_match, manual)
        rows.append(
            {
                "audit_context": {
                    "active_floor_expected_idle": _nested(
                        state, "coverage_evidence", "active_floor_expected_idle"
                    )
                    is True,
                },
                "expected_action_type": state["action_type"],
                "failure_cluster": cluster,
                "post_license": post_license,
                "raw_action_type": raw_action.get("type") if raw_action is not None else None,
                "raw_output_sha256": _nested(grade, "raw", "output_bytes_sha256"),
                "resolution": resolution,
                "semantic_intent": semantic,
                "span_resolution": {
                    **span_resolution,
                    "approved_r3": approved_r3,
                },
                "state_id": state_id,
                "strict_v1": {
                    "duplicate_action": _nested(grade, "executed", "duplicate_action"),
                    "hard_failures": list(_mapping(grade, "executed").get("hard_failures", [])),
                    "licensed": _nested(grade, "structural", "licensed"),
                    "match": strict_match,
                    "oracle_valid": _nested(grade, "executed", "oracle_valid"),
                    "parse_error": _nested(grade, "structural", "parse_error"),
                    "parse_union_valid": _nested(grade, "structural", "parse_union_valid"),
                    "reference_integrity": _nested(
                        grade, "structural", "reference_integrity"
                    ),
                },
            }
        )

    summary = _summary(
        rows,
        source_commit=source_commit,
        frozen_metrics=frozen_metrics,
        retention=retention,
        bindings={
            "dev_inventory_sha256": _digest_file(root / INVENTORY),
            "grader_contract_sha256": _digest_file(root / GRADER),
            "step30_grades_sha256": _digest_file(root / GRADES),
            "step30_metrics_sha256": _digest_file(root / METRICS),
            "step30_retention_sha256": _digest_file(root / RETENTION),
            "step30_root_sha256sums_sha256": step30_manifest,
            "wp3_2_root_sha256sums_sha256": wp3_2_manifest,
        },
    )
    clusters = _cluster_report(rows)
    adjudication_artifact = {
        "adjudication_count": len(adjudications),
        "decisions": adjudications,
        "kind": "phase3x-step30-open-text-adjudications-v1",
        "method": "manual raw-output inspection against frozen per-state rubrics",
        "no_llm_or_heuristic_scorer": True,
    }
    files = {
        "audit-rows.jsonl": b"".join(
            canonical_artifact_bytes(row) + b"\n" for row in rows
        ),
        "failure-clusters.json": canonical_artifact_bytes(clusters),
        "open-text-adjudications.json": canonical_artifact_bytes(adjudication_artifact),
        "summary.json": canonical_artifact_bytes(summary),
    }
    files["SHA256SUMS"] = _checksums(files)
    return files, summary


def _authenticated_raw_action(grade: Mapping[str, object]) -> Mapping[str, object] | None:
    raw = _mapping(grade, "raw")
    framing = _mapping(grade, "framing")
    decoded = raw.get("decoded_utf8")
    if not isinstance(decoded, str):
        raise ValueError("raw decoded output is missing")
    raw_bytes = decoded.encode("utf-8")
    if _digest_bytes(raw_bytes) != raw.get("output_bytes_sha256"):
        raise ValueError("raw output digest mismatch")
    if framing.get("raw_output_sha256") != raw.get("output_bytes_sha256"):
        raise ValueError("framing/raw output binding mismatch")
    token_ids = raw.get("output_token_ids")
    if (
        not isinstance(token_ids, list)
        or not token_ids
        or token_ids[-1] != TERMINAL_TOKEN_ID
        or framing.get("consumed_token_id") != TERMINAL_TOKEN_ID
        or framing.get("consumed_token_count") != 1
        or framing.get("terminal_projection_status") != "projected"
        or not decoded.endswith(TERMINAL_TEXT)
    ):
        raise ValueError("authenticated terminal projection is invalid")
    parser_input = decoded[: -len(TERMINAL_TEXT)].encode("utf-8")
    if _digest_bytes(parser_input) != framing.get("parser_input_sha256"):
        raise ValueError("parser-input digest mismatch")
    try:
        value = parse_tim_json(parser_input)
    except TimJsonError:
        return None
    return value if isinstance(value, Mapping) else None


def _verify_state_grade_identity(
    state: Mapping[str, object], grade: Mapping[str, object]
) -> None:
    if (
        state.get("state_id") != grade.get("state_id")
        or state.get("action_type") != grade.get("expected_action_type")
        or _nested(grade, "raw", "state_id") != state.get("state_id")
    ):
        raise ValueError("grade/inventory row binding mismatch")
    expected = state.get("expected_action")
    if not isinstance(expected, Mapping) or expected.get("type") != state.get("action_type"):
        raise ValueError("inventory expected action is malformed")


def _verify_union_grade(
    raw_action: Mapping[str, object] | None, grade: Mapping[str, object]
) -> None:
    typed = None
    if raw_action is not None:
        try:
            typed = ACTION_ADAPTER.validate_python(raw_action)
        except ValidationError:
            pass
    union_valid = typed is not None
    if union_valid != (_nested(grade, "structural", "parse_union_valid") is True):
        raise ValueError("recomputed action-union validity conflicts with frozen grade")
    predicted = grade.get("predicted_action")
    if typed is not None and typed.model_dump(mode="json") != predicted:
        raise ValueError("recomputed typed action conflicts with frozen predicted action")
    if typed is None and predicted is not None:
        raise ValueError("invalid raw action unexpectedly has a frozen typed prediction")


def _open_text_adjudication(
    grade: Mapping[str, object], rubric: Mapping[str, object] | None
) -> dict[str, object] | None:
    if _nested(grade, "executed", "semantic_status") != "pending_semantic_assessment":
        return None
    state_id = str(grade["state_id"])
    if rubric is None or rubric.get("state_id") != state_id:
        raise ValueError("pending open-text row lacks its frozen rubric")
    failed = state_id in OPEN_TEXT_FAIL
    wrong_causal = state_id in OPEN_TEXT_WRONG_CAUSAL
    reason_codes = (
        ["missing_required_fact", "unsupported_claim"]
        if failed
        else ["required_content_preserved"]
    )
    if wrong_causal:
        reason_codes.append("wrong_causal_reference")
    return {
        "action_type": grade["expected_action_type"],
        "output_bytes_sha256": _nested(grade, "raw", "output_bytes_sha256"),
        "reason_codes": reason_codes,
        "rubric_sha256": rubric["rubric_sha256"],
        "state_id": state_id,
        "status": "fail" if failed else "pass",
        "subtype": rubric["subtype"],
    }


def _state_facts(
    state: Mapping[str, object],
) -> tuple[dict[str, str], dict[str, object]]:
    texts: dict[str, str] = {}
    result_data: dict[str, object] = {}
    messages = state.get("messages")
    if not isinstance(messages, list):
        raise ValueError("inventory messages are malformed")
    for message in messages:
        if not isinstance(message, Mapping) or message.get("role") != "user":
            continue
        content = message.get("content")
        if not isinstance(content, str):
            raise ValueError("inventory user content is malformed")
        for line in content.encode("utf-8").splitlines():
            if not line.startswith(b"{"):
                continue
            try:
                value = parse_tim_json(line)
            except TimJsonError:
                continue
            _collect_state_facts(value, texts, result_data)
    return texts, result_data


def _collect_state_facts(
    value: object, texts: dict[str, str], result_data: dict[str, object]
) -> None:
    if isinstance(value, Mapping):
        event_id, payload = value.get("id"), value.get("payload")
        if isinstance(event_id, str) and isinstance(payload, Mapping):
            text = payload.get("text")
            if isinstance(text, str):
                texts[event_id] = text
            if value.get("source") == "tool" and value.get("kind") == "result":
                result_data[event_id] = payload.get("data")
            snapshot = payload.get("snapshot")
            if isinstance(snapshot, Mapping):
                snapshot_id, snapshot_text = snapshot.get("event_id"), snapshot.get("text")
                if isinstance(snapshot_id, str) and isinstance(snapshot_text, str):
                    texts[snapshot_id] = snapshot_text
            open_results = payload.get("open_tool_results")
            if isinstance(open_results, list):
                for result in open_results:
                    if isinstance(result, Mapping) and isinstance(result.get("event_id"), str):
                        result_data[str(result["event_id"])] = result.get("data")
        for child in value.values():
            _collect_state_facts(child, texts, result_data)
    elif isinstance(value, list):
        for child in value:
            _collect_state_facts(child, texts, result_data)


def _resolve_exact_spans(
    raw_action: Mapping[str, object] | None, event_texts: Mapping[str, str]
) -> dict[str, object]:
    if raw_action is None or raw_action.get("type") not in {"mark", "delegate"}:
        return {"policy_version": SPAN_POLICY, "status": "not_span_action"}
    candidate = copy.deepcopy(dict(raw_action))
    keys = ("instruction", "target") if raw_action.get("type") == "mark" else ("fact",)
    occurrence_counts: dict[str, int] = {}
    for key in keys:
        span = candidate.get(key)
        if not isinstance(span, dict):
            return {"policy_version": SPAN_POLICY, "status": "malformed_span"}
        event_id, selected = span.get("event_id"), span.get("text")
        source = event_texts.get(str(event_id))
        if not isinstance(event_id, str) or not isinstance(selected, str) or source is None:
            return {"policy_version": SPAN_POLICY, "status": "non_addressable_span"}
        starts = _occurrences(source, selected)
        occurrence_counts[key] = len(starts)
        if not starts:
            return {
                "occurrence_counts": occurrence_counts,
                "policy_version": SPAN_POLICY,
                "status": "missing_exact_text",
            }
        if len(starts) != 1:
            return {
                "occurrence_counts": occurrence_counts,
                "policy_version": SPAN_POLICY,
                "status": "nonunique_exact_ambiguous",
            }
        start, end = starts[0], starts[0] + len(selected)
        if not _complete_lexical_boundary(source, start, end):
            return {
                "occurrence_counts": occurrence_counts,
                "policy_version": SPAN_POLICY,
                "status": "lexical_boundary_failure",
            }
        start_utf16 = utf16_len(source[:start])
        span["start_utf16"] = start_utf16
        span["end_utf16"] = start_utf16 + utf16_len(selected)
    try:
        action = ACTION_ADAPTER.validate_python(candidate)
    except ValidationError:
        return {
            "occurrence_counts": occurrence_counts,
            "policy_version": SPAN_POLICY,
            "status": "resolved_action_invalid",
        }
    resolved = action.model_dump(mode="json")
    return {
        "occurrence_counts": occurrence_counts,
        "policy_version": SPAN_POLICY,
        "resolved_action_sha256": _digest_bytes(canonicalize_tim_json(resolved)),
        "resolved_action": resolved,
        "status": "unique_exact_resolved",
    }


def _approved_r3(
    state: Mapping[str, object],
    raw_action: Mapping[str, object] | None,
    event_texts: Mapping[str, str],
    strict_match: bool,
) -> dict[str, object]:
    expected = state["expected_action"]
    if state["action_type"] not in {"mark", "delegate"}:
        return {"policy_version": APPROVED_R3_POLICY, "status": "not_span_action"}
    classification = classify_span_action(
        expected,
        raw_action,
        event_texts,
        strict_action_match=strict_match,
    )
    correct = classification.get("canonicalizable") is True and _same_span_intent(
        expected, raw_action
    )
    return {
        "canonicalizable_correct": correct,
        "policy_version": APPROVED_R3_POLICY,
        "primary_category": classification["primary_category"],
        "status": "canonicalizable" if correct else "not_canonicalizable",
    }


def _same_span_intent(expected: object, raw_action: Mapping[str, object] | None) -> bool:
    if not isinstance(expected, Mapping) or raw_action is None:
        return False
    if expected.get("type") not in {"mark", "delegate"} or raw_action.get("type") != expected.get(
        "type"
    ):
        return False
    amended = copy.deepcopy(dict(raw_action))
    keys = ("instruction", "target") if expected.get("type") == "mark" else ("fact",)
    for key in keys:
        wanted, actual = expected.get(key), amended.get(key)
        if not isinstance(wanted, Mapping) or not isinstance(actual, dict):
            return False
        if actual.get("event_id") != wanted.get("event_id") or actual.get("text") != wanted.get(
            "text"
        ):
            return False
        actual["start_utf16"] = wanted.get("start_utf16")
        actual["end_utf16"] = wanted.get("end_utf16")
    return amended == expected


def _semantic_status(
    state: Mapping[str, object],
    raw_action: Mapping[str, object] | None,
    strict_match: bool,
    manual: Mapping[str, object] | None,
    span_intent: bool,
) -> dict[str, object]:
    if strict_match:
        return {"basis": "strict_v1_match", "status": "pass"}
    if manual is not None:
        return {
            "basis": "manual_frozen_open_text_rubric",
            "reason_codes": manual["reason_codes"],
            "status": manual["status"],
        }
    if span_intent:
        return {"basis": "same_action_reference_and_exact_text", "status": "pass"}
    if (
        state["action_type"] == "idle"
        and raw_action is not None
        and raw_action.get("type") == "idle"
    ):
        return {"basis": "same_noop_effect_different_idle_reason", "status": "effect_equivalent"}
    if _same_target_skip(state.get("expected_action"), raw_action):
        return {"basis": "same_target_different_skip_reason", "status": "ambiguous"}
    return {"basis": "raw_action_selection_or_reference_mismatch", "status": "fail"}


def _resolved_status(
    state: Mapping[str, object],
    grade: Mapping[str, object],
    raw_action: Mapping[str, object] | None,
    result_data: Mapping[str, object],
    strict_match: bool,
    manual: Mapping[str, object] | None,
    span_resolution: Mapping[str, object],
) -> dict[str, object]:
    if strict_match:
        return {"basis": "strict_v1_action", "match": True, "status": "resolved"}
    expected = state["expected_action"]
    if state["action_type"] == "integrate" and manual is not None and manual["status"] == "pass":
        result_id = raw_action.get("result_event_id") if raw_action is not None else None
        if isinstance(result_id, str) and result_id in result_data:
            candidate = {
                "result_event_id": result_id,
                "text": canonicalize_tim_json(result_data[result_id]).decode("utf-8"),
                "type": "integrate",
            }
            return {
                "basis": "canonical_committed_result_fallback",
                "match": result_id == expected.get("result_event_id"),
                "resolved_action_sha256": _digest_bytes(canonicalize_tim_json(candidate)),
                "status": "resolved",
            }
        return {"basis": "canonical_result_unavailable", "match": False, "status": "failed_closed"}
    if state["action_type"] == "respond" and manual is not None:
        match = (
            manual["status"] == "pass"
            and _nested(grade, "structural", "structural_pass") is True
        )
        return {
            "basis": "manual_text_plus_exact_warrant" if match else "open_text_or_warrant_failure",
            "match": match,
            "status": "resolved" if match else "failed_closed",
        }
    candidate = span_resolution.get("resolved_action")
    if isinstance(candidate, Mapping):
        return {
            "basis": SPAN_POLICY,
            "match": candidate == expected,
            "status": "resolved" if candidate == expected else "resolved_incorrect",
        }
    return {"basis": span_resolution["status"], "match": False, "status": "failed_closed"}


def _failure_cluster(
    state: Mapping[str, object],
    grade: Mapping[str, object],
    raw_action: Mapping[str, object] | None,
    strict_match: bool,
    manual: Mapping[str, object] | None,
    span_intent: bool,
) -> str | None:
    if strict_match:
        return None
    if manual is not None:
        return (
            "open_text_correct_user_intent_wrong_causal"
            if _nested(grade, "executed", "wrong_causal_result") is True
            else "open_text_semantic_review"
        )
    if span_intent:
        return "span_intent_offset_defect"
    if (
        state["action_type"] == "idle"
        and raw_action is not None
        and raw_action.get("type") == "idle"
    ):
        return "idle_reason_only_same_noop"
    if state["action_type"] == "idle" and raw_action is not None:
        return "intrusive_nonidle_on_expected_idle"
    hard = set(_mapping(grade, "executed").get("hard_failures", []))
    if raw_action is not None and raw_action.get("type") == state["action_type"] and hard & {
        "cancel_target_mismatch",
        "wrong_causal_result",
    }:
        return "wrong_causal_or_target_same_route"
    return "action_selection_or_parse_miss"


def _post_license(
    state: Mapping[str, object],
    grade: Mapping[str, object],
    raw_action: Mapping[str, object] | None,
    strict_match: bool,
    manual: Mapping[str, object] | None,
) -> dict[str, object]:
    licensed = _nested(grade, "structural", "licensed") is True
    correct = strict_match or (
        manual is not None
        and manual["status"] == "pass"
        and _nested(grade, "structural", "structural_pass") is True
    )
    admitted_incorrect = (
        licensed
        and not correct
        and raw_action is not None
        and raw_action.get("type") != "idle"
    )
    unsafe_codes: list[str] = []
    if admitted_incorrect:
        if _same_target_skip(state.get("expected_action"), raw_action):
            unsafe_codes.append("provenance_unsafe_skip_reason")
        else:
            unsafe_codes.append("wrong_mutation_or_content")
        if state["action_type"] in {"cancel", "integrate", "nudge", "skip"}:
            unsafe_codes.append("wrong_timer_result_or_fire_execution")
        if "rollover_violation" in _mapping(grade, "executed").get("hard_failures", []):
            unsafe_codes.append("wrong_rollover_mutation")
    return {
        "admitted_incorrect": admitted_incorrect,
        "licensed": licensed,
        "unsafe_codes": unsafe_codes,
    }


def _summary(
    rows: Sequence[Mapping[str, object]],
    *,
    source_commit: str,
    frozen_metrics: Mapping[str, object],
    retention: Mapping[str, object],
    bindings: Mapping[str, str],
) -> dict[str, object]:
    d10 = [row for row in rows if row["expected_action_type"] in D10_ACTION_TYPES]
    strict = [row for row in rows if _nested(row, "strict_v1", "match") is True]
    strict_d10 = [row for row in d10 if _nested(row, "strict_v1", "match") is True]
    semantic_d10 = [row for row in d10 if _nested(row, "semantic_intent", "status") == "pass"]
    resolved_d10 = [row for row in d10 if _nested(row, "resolution", "match") is True]
    span_rows = [row for row in rows if row["expected_action_type"] in {"mark", "delegate"}]
    strict_span = [row for row in span_rows if _nested(row, "strict_v1", "match") is True]
    semantic_span = [
        row for row in span_rows if _nested(row, "semantic_intent", "status") == "pass"
    ]
    approved_r3_span = [
        row
        for row in span_rows
        if _nested(row, "span_resolution", "approved_r3", "canonicalizable_correct") is True
    ]
    unique_exact_span = [
        row for row in span_rows if _nested(row, "resolution", "match") is True
    ]
    semantic_full = [
        row for row in rows if _nested(row, "semantic_intent", "status") == "pass"
    ]
    idle_effect = [
        row
        for row in rows
        if _nested(row, "semantic_intent", "status") == "effect_equivalent"
    ]
    ambiguous_skip_effect = [
        row
        for row in rows
        if _nested(row, "semantic_intent", "status") == "ambiguous"
        and _nested(row, "semantic_intent", "basis") == "same_target_different_skip_reason"
    ]
    resolved_full = [row for row in rows if _nested(row, "resolution", "match") is True]
    approved_r3_d10 = [
        row
        for row in d10
        if _nested(row, "strict_v1", "match") is True
        or (
            row["expected_action_type"] == "integrate"
            and _nested(row, "resolution", "match") is True
        )
        or _nested(row, "span_resolution", "approved_r3", "canonicalizable_correct") is True
    ]
    mark_semantic = [
        row
        for row in rows
        if row["expected_action_type"] == "mark"
        and _nested(row, "semantic_intent", "status") == "pass"
    ]
    parse_valid = sum(_nested(row, "strict_v1", "parse_union_valid") is True for row in rows)
    active_floor_errors = sum(
        _nested(row, "audit_context", "active_floor_expected_idle") is True
        and row["raw_action_type"] == "respond"
        for row in rows
    )
    duplicate_errors = sum(
        _nested(row, "strict_v1", "duplicate_action") is True
        and row["raw_action_type"] in {"delegate", "schedule"}
        for row in rows
    )
    hard_failures = [
        failure for row in rows for failure in _nested(row, "strict_v1", "hard_failures")
    ]
    admitted = [row for row in rows if _nested(row, "post_license", "admitted_incorrect")]
    wrong_lifecycle = sum(
        "wrong_timer_result_or_fire_execution"
        in _nested(row, "post_license", "unsafe_codes")
        for row in rows
    )
    wrong_rollover = sum(
        "wrong_rollover_mutation" in _nested(row, "post_license", "unsafe_codes")
        for row in rows
    )
    gate = {
        "active_floor_respond": {
            "observed": f"{active_floor_errors}/12",
            "passed": active_floor_errors == 0,
            "required": "0/12",
        },
        "duplicate_delegate_schedule_errors": {
            "observed": duplicate_errors,
            "passed": duplicate_errors == 0,
            "required": 0,
        },
        "mark_semantic_selection": {
            "observed": f"{len(mark_semantic)}/34",
            "passed": len(mark_semantic) >= 27,
            "required": ">=27/34",
        },
        "resolved_six_action": {
            "observed": f"{len(resolved_d10)}/123",
            "passed": len(resolved_d10) >= 111,
            "required": ">=111/123",
        },
        "rollover_mutation_errors": {
            "observed": wrong_rollover,
            "passed": wrong_rollover == 0,
            "required": 0,
        },
        "strict_json_union": {
            "observed": f"{parse_valid}/300",
            "passed": parse_valid >= 294,
            "required": ">=294/300 (98%)",
        },
        "wrong_timer_result_fire_execution": {
            "observed": wrong_lifecycle,
            "passed": wrong_lifecycle == 0,
            "required": 0,
        },
    }
    reproduced = {
        "admitted": len(admitted),
        "approved_r3_d10": len(approved_r3_d10),
        "hard_failures": len(hard_failures),
        "mark_semantic": len(mark_semantic),
        "parse_valid": parse_valid,
        "resolved_d10": len(resolved_d10),
        "semantic_d10": len(semantic_d10),
        "strict": len(strict),
        "strict_d10": len(strict_d10),
        "wrong_lifecycle": wrong_lifecycle,
        "wrong_rollover": wrong_rollover,
    }
    expected_counts = {
        "admitted": 8,
        "approved_r3_d10": 91,
        "hard_failures": 48,
        "mark_semantic": 26,
        "parse_valid": 290,
        "resolved_d10": 93,
        "semantic_d10": 111,
        "strict": 204,
        "strict_d10": 74,
        "wrong_lifecycle": 6,
        "wrong_rollover": 4,
    }
    if reproduced != expected_counts:
        raise ValueError(f"step-30 counts changed: {reproduced}")
    if (
        len(semantic_full) != 251
        or len(idle_effect) != 22
        or len(ambiguous_skip_effect) != 4
        or len(resolved_full) != 231
    ):
        raise ValueError("full-state semantic/effect metrics changed")
    if (
        active_floor_errors != 1
        or duplicate_errors != 0
        or frozen_metrics.get("parse_union_validity") != 290 / 300
        or frozen_metrics.get("forbidden_error_count") != 48
    ):
        raise ValueError("derived mechanics counts conflict with frozen step-30 metrics")
    detector = _mapping(_mapping(retention, "evidence"), "detector_v3")
    return {
        "authorization": {
            "checkpoint_access": False,
            "dpo": False,
            "provider_calls": False,
            "retention_60": False,
            "sealed_test": False,
            "secrets": False,
            "spend": False,
        },
        "bindings": dict(bindings),
        "failure_counts": {
            "admitted_incorrect_rows": len(admitted),
            "hard_failure_occurrences": len(hard_failures),
            "hard_failure_rows": sum(
                bool(_nested(row, "strict_v1", "hard_failures")) for row in rows
            ),
            "wrong_rollover_mutation_rows": wrong_rollover,
            "wrong_timer_result_fire_execution_rows": wrong_lifecycle,
        },
        "kind": "phase3x-step30-executable-policy-audit-v1",
        "metrics": {
            "approved_r3_canonicalizable_span_accuracy": _metric(
                approved_r3_span, span_rows
            ),
            "approved_r3_resolved_six_action": _metric(approved_r3_d10, d10),
            "mark_semantic_selection": _metric(mark_semantic, [
                row for row in rows if row["expected_action_type"] == "mark"
            ]),
            "raw_strict_full": _metric(strict, rows),
            "raw_strict_six_action": _metric(strict_d10, d10),
            "raw_unconstrained_json_union_validity": {"count": parse_valid, "denominator": 300},
            "resolved_full": _metric(resolved_full, rows),
            "resolved_plus_idle_noop_effect_full": _metric(
                [*resolved_full, *idle_effect], rows
            ),
            "resolved_plus_idle_and_same_target_skip_effect_full": _metric(
                [*resolved_full, *idle_effect, *ambiguous_skip_effect], rows
            ),
            "semantic_intent_full": _metric(semantic_full, rows),
            "semantic_plus_idle_noop_effect_full": _metric(
                [*semantic_full, *idle_effect], rows
            ),
            "semantic_six_action": _metric(semantic_d10, d10),
            "semantic_span_action_accuracy": _metric(semantic_span, span_rows),
            "six_action_breakdown": _six_action_breakdown(d10),
            "strict_span_action_accuracy": _metric(strict_span, span_rows),
            "unique_exact_resolved_span_accuracy": _metric(unique_exact_span, span_rows),
            "unique_exact_resolved_six_action": _metric(resolved_d10, d10),
        },
        "resolution_policy": {
            "approved_r3": APPROVED_R3_POLICY,
            "diagnostic": SPAN_POLICY,
            "gold_used_to_construct_candidate": False,
            "nearest_or_fuzzy_matching": False,
        },
        "retention_context": {
            "genuine_generation_loop_count": detector["high_confidence_generation_loop_count"],
            "new_length_termination_count": detector["new_length_termination_count"],
            "promotion_gate_rewritten": False,
        },
        "skip_sft": all(check["passed"] for check in gate.values()),
        "skip_sft_gate": gate,
        "source_commit": source_commit,
        "status": "complete_offline",
        "tinker_constrained_decoding_available": False,
    }


def _cluster_report(rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    grouped: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        cluster = row.get("failure_cluster")
        if isinstance(cluster, str):
            grouped[cluster].append(row)
    counts = {name: len(selected) for name, selected in sorted(grouped.items())}
    expected = {
        "action_selection_or_parse_miss": 14,
        "idle_reason_only_same_noop": 22,
        "intrusive_nonidle_on_expected_idle": 7,
        "open_text_correct_user_intent_wrong_causal": 2,
        "open_text_semantic_review": 26,
        "span_intent_offset_defect": 20,
        "wrong_causal_or_target_same_route": 5,
    }
    if counts != expected:
        raise ValueError(f"failure clusters changed: {counts}")
    return {
        "clusters": {
            name: {
                "count": len(selected),
                "raw_output_sha256s": [row["raw_output_sha256"] for row in selected],
                "state_ids": [row["state_id"] for row in selected],
            }
            for name, selected in sorted(grouped.items())
        },
        "kind": "phase3x-step30-failure-clusters-v1",
        "strict_failure_count": sum(counts.values()),
    }


def _same_target_skip(expected: object, raw_action: Mapping[str, object] | None) -> bool:
    return (
        isinstance(expected, Mapping)
        and raw_action is not None
        and expected.get("type") == raw_action.get("type") == "skip"
        and expected.get("target_event_id") == raw_action.get("target_event_id")
        and expected.get("reason") != raw_action.get("reason")
    )


def _occurrences(source: str, selected: str) -> tuple[int, ...]:
    if not selected:
        return ()
    starts: list[int] = []
    cursor = 0
    while (found := source.find(selected, cursor)) >= 0:
        starts.append(found)
        cursor = found + 1
    return tuple(starts)


def _complete_lexical_boundary(source: str, start: int, end: int) -> bool:
    def word(character: str) -> bool:
        return character.isalnum() or character == "_"

    return (start == 0 or not (word(source[start - 1]) and word(source[start]))) and (
        end == len(source) or not (word(source[end - 1]) and word(source[end]))
    )


def _metric(success: Sequence[object], denominator: Sequence[object]) -> dict[str, object]:
    return {
        "count": len(success),
        "denominator": len(denominator),
        "fraction": f"{len(success)}/{len(denominator)}",
    }


def _six_action_breakdown(rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for action in sorted(D10_ACTION_TYPES):
        selected = [row for row in rows if row["expected_action_type"] == action]
        result[action] = {
            "denominator": len(selected),
            "resolved": sum(_nested(row, "resolution", "match") is True for row in selected),
            "semantic": sum(
                _nested(row, "semantic_intent", "status") == "pass" for row in selected
            ),
            "strict": sum(_nested(row, "strict_v1", "match") is True for row in selected),
        }
    return result


def _mapping(parent: Mapping[str, object], key: str) -> Mapping[str, object]:
    value = parent.get(key)
    if not isinstance(value, Mapping):
        raise ValueError(f"{key} is not a mapping")
    return value


def _mapping_list(parent: Mapping[str, object], key: str) -> list[Mapping[str, object]]:
    value = parent.get(key)
    if not isinstance(value, list) or any(not isinstance(row, Mapping) for row in value):
        raise ValueError(f"{key} is not a mapping list")
    return value


def _nested(parent: Mapping[str, object], *keys: str) -> object:
    value: object = parent
    for key in keys:
        if not isinstance(value, Mapping):
            return None
        value = value.get(key)
    return value


def _unique_rows(
    rows: Sequence[Mapping[str, object]], label: str
) -> dict[str, Mapping[str, object]]:
    result: dict[str, Mapping[str, object]] = {}
    for row in rows:
        state_id = row.get("state_id")
        if not isinstance(state_id, str) or state_id in result:
            raise ValueError(f"{label} state IDs are malformed or duplicated")
        result[state_id] = row
    return result


def _read_json(path: Path) -> object:
    return json.loads(path.read_bytes())


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_bytes().splitlines() if line]


def _read_jsonl_gzip(path: Path) -> list[dict[str, object]]:
    with gzip.open(path, "rb") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def _verify_sha256sums(directory: Path, expected_manifest_sha256: str) -> str:
    manifest = directory / "SHA256SUMS"
    actual_manifest_sha256 = sha256(manifest.read_bytes()).hexdigest()
    if actual_manifest_sha256 != expected_manifest_sha256:
        raise ValueError(f"frozen manifest digest mismatch: {manifest}")
    for line in manifest.read_text(encoding="ascii").splitlines():
        digest, relative = line.split("  ", 1)
        if sha256((directory / relative).read_bytes()).hexdigest() != digest:
            raise ValueError(f"checksum mismatch: {directory / relative}")
    return f"sha256:{actual_manifest_sha256}"


def _verify_tracked_source(root: Path, source_commit: str) -> None:
    if len(source_commit) != 40 or any(
        character not in "0123456789abcdef" for character in source_commit
    ):
        raise ValueError("source commit must be one lowercase 40-character Git SHA")
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()
    if head != source_commit:
        raise ValueError("source commit does not match HEAD")
    for command in (["git", "diff", "--quiet"], ["git", "diff", "--cached", "--quiet"]):
        if subprocess.run(command, cwd=root, check=False).returncode:
            raise ValueError("tracked source tree is not clean")


def _digest_file(path: Path) -> str:
    return _digest_bytes(path.read_bytes())


def _digest_bytes(raw: bytes) -> str:
    return f"sha256:{sha256(raw).hexdigest()}"


def _checksums(files: Mapping[str, bytes]) -> bytes:
    return "".join(
        f"{sha256(raw).hexdigest()}  {name}\n" for name, raw in sorted(files.items())
    ).encode("ascii")


if __name__ == "__main__":
    main()
