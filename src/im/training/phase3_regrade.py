"""Versioned offline regrade of the immutable WP3-2 backbone run."""

from __future__ import annotations

import json
import re
import subprocess
from collections import Counter
from collections.abc import Mapping
from hashlib import sha256
from pathlib import Path

from pydantic import ValidationError

from im.assets.model import canonical_artifact_bytes
from im.canonical_json import TimJsonError, parse_tim_json
from im.generation.publication import publish_directory_transaction
from im.schema.actions import ACTION_ADAPTER
from im.training.phase3_data import (
    _read_bytes,
    _verify_checksum_manifest,
    guard_read_path,
    load_pinned_tokenizer,
)
from im.training.phase3_eval import (
    FrozenHumanAssessment,
    PersistedRawGeneration,
    Phase3EvalError,
    _compute_dev_metrics_from_grades,
    _duplicate_mechanics_opportunities,
    _load_persisted_raw,
    build_open_text_rubrics,
    grade_persisted_generation,
    rebuild_dev_states,
)
from im.training.phase3_framing import (
    TERMINAL_FRAMING_VERSION,
    TerminalFramingError,
    project_terminal_output,
)

SAMPLING_MANIFEST_SHA256 = (
    "sha256:1f05d80c49baa9a79311ec2567a46995babf9e90a26f674a18b7b9f8c09940d5"
)
IMMUTABLE_RUN_REPORT_SHA256 = (
    "sha256:fe1628f1cd99204e4e29ffcef3b301451ff825938d3ce78aa4edff4eb06042f8"
)
OLD_RUN_SHA256SUMS_SHA256 = (
    "sha256:99ad7584c7eee312df0d1e191bc9e6b4a98a6987d5b8f387524187a98f2d34f0"
)
OLD_GRADES_SHA256 = "sha256:e5698bb277bb07e4631b602350c455d7fec36fc9922517d23deb67c96ac85233"
OLD_METRICS_SHA256 = "sha256:cced950458456e280f5e60e34b76ebba5e98a4e99f0fce5a1ba65141bcbd62df"
OFFLINE_CANDIDATE_SHA256SUMS_SHA256 = (
    "sha256:b26ce03fbf46de2ed0b75c71ca925b79dee3d42d77e05f323271ffd5125dcace"
)
FRAMING_APPROVAL_SHA256 = (
    "sha256:17b7099dd481d9b0fa7391b2dff281ac11313d121b139eec81fe9390a4df2a70"
)
FRAMING_REVIEW_BUNDLE_SHA256 = (
    "sha256:b02499343407c3c47b3a1c16a36f470a79bdf58ddfdfedd02f14b9524617f944"
)
FRAMING_REGRADE_V4_SHA256SUMS = (
    "sha256:d4ee694b7fb8371fe24a18c799677c32351d2f3ab0fea3b17a9c7115e7d497b7"
)
OPEN_TEXT_FAIL_STATE_ID = (
    "dev:a5a564738bd3f89bfc5c2012932f5332043d30e1a38d1e545d1c3fa66d47df47:1"
)
OPEN_TEXT_PROVENANCE_FAILURE_IDS = frozenset(
    {
        "dev:54d1f184698905f78a5c5bb096934c4c019df6c2c1a765d00b170082c9b66a3d:22",
        "dev:637dbaef9a4a2ceae7c9974aebf7c90b597319593d5a1ce54f9a2251a2789670:22",
    }
)


async def build_backbone_regrade(
    *, repository_root: Path, tokenizer_directory: Path, source_commit: str
) -> dict[str, bytes]:
    """Regrade immutable raw records without provider, secret, checkpoint, or TEST access."""
    root = guard_read_path(repository_root, repository_root)
    _verify_source_commit(root, source_commit)
    run_root = root / "review/phase3/wp3-2-backbone-baseline-run-v1"
    run_manifest, run_files = _verify_checksum_manifest(
        root,
        run_root / "SHA256SUMS",
        capture=frozenset(
            {"dev-grades.jsonl", "dev-metrics.json", "raw-index.json", "run-report.json"}
        ),
    )
    if run_manifest != OLD_RUN_SHA256SUMS_SHA256:
        raise Phase3EvalError("immutable WP3-2 run checksum manifest drifted")
    _require_digest(run_files["run-report.json"], IMMUTABLE_RUN_REPORT_SHA256, "run report")
    _require_digest(run_files["dev-grades.jsonl"], OLD_GRADES_SHA256, "old grades")
    _require_digest(run_files["dev-metrics.json"], OLD_METRICS_SHA256, "old metrics")
    run_report = _json_object(run_files["run-report.json"])
    if (
        run_report.get("sampling_manifest_sha256") != SAMPLING_MANIFEST_SHA256
        or run_report.get("completed_requests") != 360
        or run_report.get("sealed_test") != "unread"
    ):
        raise Phase3EvalError("immutable WP3-2 run identity drifted")

    candidate_root = root / "review/phase3/wp3-2-offline-candidate-v4"
    candidate_manifest, candidate_files = _verify_checksum_manifest(
        root,
        candidate_root / "SHA256SUMS",
        capture=frozenset({"grader-contract.json", "retention-blind-template.json"}),
    )
    if candidate_manifest != OFFLINE_CANDIDATE_SHA256SUMS_SHA256:
        raise Phase3EvalError("approved WP3-2 offline candidate drifted")
    grader_contract = _json_object(candidate_files["grader-contract.json"])
    retention_contract = _json_object(candidate_files["retention-blind-template.json"])
    retention_template = retention_contract.get("rows")
    if not isinstance(retention_template, list) or any(
        not isinstance(row, Mapping) for row in retention_template
    ):
        raise Phase3EvalError("approved retention template has invalid rows")
    approval_raw = _read_bytes(
        root,
        root / "review/phase3/wp3-2-terminal-framing-approval-v1/owner-approval.json",
    )
    _require_digest(approval_raw, FRAMING_APPROVAL_SHA256, "framing owner approval")
    framing_review_bundle = _read_bytes(
        root,
        root / "review/phase3/wp3-2-baseline-framing-review-v1.zip",
    )
    _require_digest(
        framing_review_bundle,
        FRAMING_REVIEW_BUNDLE_SHA256,
        "approved framing review bundle",
    )
    approval = _json_object(approval_raw)
    if {
        "approved_review_bundle_sha256": approval.get("approved_review_bundle_sha256"),
        "owner_decision": approval.get("owner_decision"),
        "required_format_version": approval.get("required_format_version"),
        "provider_call_authorized": approval.get("provider_call_authorized"),
        "secret_access_authorized": approval.get("secret_access_authorized"),
        "sealed_test_access_authorized": approval.get("sealed_test_access_authorized"),
    } != {
        "approved_review_bundle_sha256": FRAMING_REVIEW_BUNDLE_SHA256,
        "owner_decision": "approved",
        "required_format_version": TERMINAL_FRAMING_VERSION,
        "provider_call_authorized": False,
        "secret_access_authorized": False,
        "sealed_test_access_authorized": False,
    }:
        raise Phase3EvalError("framing owner approval contract drifted")
    v4_root = root / "review/phase3/wp3-2-backbone-baseline-regrade-v4"
    v4_manifest, v4_files = _verify_checksum_manifest(
        root,
        v4_root / "SHA256SUMS",
        capture=frozenset(
            {
                "failure-clusters.json",
                "framing-contract.json",
                "interaction-grades.jsonl",
                "interaction-metrics.json",
                "open-text-review-packet.json",
                "raw-failure-report.json",
                "retention-presentation.json",
                "runtime-parity.json",
                "wp3-2-closeout-candidate-report.json",
            }
        ),
    )
    if v4_manifest != FRAMING_REGRADE_V4_SHA256SUMS:
        raise Phase3EvalError("approved framing regrade v4 manifest drifted")

    tokenizer = load_pinned_tokenizer(root, tokenizer_directory)
    states = await rebuild_dev_states(root, tokenizer)
    raw_index = _json_list(run_files["raw-index.json"])
    interaction_rows = [row for row in raw_index if row.get("kind") == "interaction_dev"]
    retention_rows = [row for row in raw_index if row.get("kind") == "retention"]
    if len(interaction_rows) != 300 or len(retention_rows) != 60:
        raise Phase3EvalError("immutable WP3-2 raw inventory drifted")

    state_by_id = {state.state_id: state for state in states}
    initial_grades: list[dict[str, object]] = []
    raw_by_id = {}
    persisted_by_id: dict[str, PersistedRawGeneration] = {}
    parser_input_by_id: dict[str, bytes] = {}
    for row in interaction_rows:
        state_id = _row_text(row, "request_id")
        state = state_by_id.get(state_id)
        if state is None:
            raise Phase3EvalError("interaction raw record is not a frozen DEV state")
        persisted = _persisted(root, row)
        raw = _load_persisted_raw(root, persisted)
        projection = project_terminal_output(
            finish_reason=raw.finish_reason,
            output_token_ids=raw.output_token_ids,
            decoded_bytes=raw.decoded_bytes,
            tokenizer=tokenizer.tokenizer,
        )
        raw_by_id[state_id] = raw
        persisted_by_id[state_id] = persisted
        parser_input_by_id[state_id] = projection.parser_input
        initial_grades.append(
            grade_persisted_generation(root, state, persisted, tokenizer=tokenizer.tokenizer)
        )
    if len(raw_by_id) != 300:
        raise Phase3EvalError("interaction raw identities repeat")
    initial_grades.sort(key=lambda row: state_by_id[str(row["state_id"])].priority_rank)
    assessments = _owner_open_text_assessments(states, initial_grades)
    grades = [
        grade_persisted_generation(
            root,
            state,
            persisted_by_id[state.state_id],
            semantic_assessment=assessments.get(state.state_id),
            tokenizer=tokenizer.tokenizer,
        )
        for state in sorted(states, key=lambda item: item.priority_rank)
    ]
    _assert_semantic_only_delta(initial_grades, grades)
    metrics = _compute_dev_metrics_from_grades(states, grades)

    json_failures, schema_failures = _parse_failure_rows(grades, parser_input_by_id)
    union_valid_count = sum(bool(row["structural"]["parse_union_valid"]) for row in grades)
    correct_action_type_count = sum(
        isinstance(row.get("predicted_action"), Mapping)
        and row["predicted_action"].get("type") == row["expected_action_type"]
        for row in grades
    )
    closed_field_match_count = sum(
        bool(row["structural"]["closed_field_match"]) for row in grades
    )
    grade_by_id = {str(row["state_id"]): row for row in grades}
    duplicate_delegate_ids = [
        state.state_id
        for state in states
        if "duplicate_delegate" in _duplicate_mechanics_opportunities(state)
    ]
    duplicate_delegate_idle_count = sum(
        isinstance(grade_by_id[state_id].get("predicted_action"), Mapping)
        and grade_by_id[state_id]["predicted_action"].get("type") == "idle"
        for state_id in duplicate_delegate_ids
    )
    success_by_id = {
        str(row["state_id"]): bool(row["executed"]["match"]) for row in grades
    }
    positive_success_count = sum(
        success_by_id[state.state_id] for state in states if state.action_type != "idle"
    )
    stream_results: dict[str, list[bool]] = {}
    for state in states:
        stream_results.setdefault(state.stream_sha256, []).append(success_by_id[state.state_id])
    successful_stream_count = sum(all(values) for values in stream_results.values())
    metrics.update(
        {
            "closed_field_match_count": closed_field_match_count,
            "correct_strict_action_type_count": correct_action_type_count,
            "correct_strict_action_type_rate": correct_action_type_count / 300,
            "duplicate_delegate_negative_denominator": len(duplicate_delegate_ids),
            "duplicate_delegate_negative_idle_count": duplicate_delegate_idle_count,
            "duplicate_delegate_negative_idle_rate": (
                duplicate_delegate_idle_count / len(duplicate_delegate_ids)
            ),
            "executed_success_count": sum(success_by_id.values()),
            "positive_action_success_count": positive_success_count,
            "standard_json_valid_count": 300 - len(json_failures),
            "standard_json_validity": (300 - len(json_failures)) / 300,
            "strict_action_union_valid_count": union_valid_count,
            "successful_complete_stream_count": successful_stream_count,
            "successful_complete_stream_denominator": len(stream_results),
            "terminal_projection_count": 300,
        }
    )
    if (
        len(json_failures) != 9
        or len(schema_failures) != 52
        or union_valid_count != 239
        or correct_action_type_count != 209
        or closed_field_match_count != 159
        or len(duplicate_delegate_ids) != 28
        or duplicate_delegate_idle_count != 28
    ):
        raise Phase3EvalError("regraded diagnostic counts do not match approved framing evidence")
    if metrics.get("active_floor_denominator") != 12 or metrics.get(
        "active_floor_respond_rate"
    ) != 11 / 12:
        raise Phase3EvalError("active-floor diagnostic drifted")
    if {
        "baseline_failure_count": metrics.get("baseline_failure_count"),
        "d13_score": metrics.get("d13_score"),
        "executed_success_count": metrics.get("executed_success_count"),
        "forbidden_error_count": metrics.get("forbidden_error_count"),
        "hidden_thinking_count": metrics.get("hidden_thinking_count"),
        "pending_semantic_assessment_count": metrics.get(
            "pending_semantic_assessment_count"
        ),
        "positive_action_micro_accuracy": metrics.get("positive_action_micro_accuracy"),
        "positive_action_success_count": metrics.get("positive_action_success_count"),
        "sequence_success": metrics.get("sequence_success"),
        "successful_complete_stream_count": metrics.get("successful_complete_stream_count"),
        "successful_complete_stream_denominator": metrics.get(
            "successful_complete_stream_denominator"
        ),
    } != {
        "baseline_failure_count": 142,
        "d13_score": -0.7711719418306244,
        "executed_success_count": 158,
        "forbidden_error_count": 81,
        "hidden_thinking_count": 0,
        "pending_semantic_assessment_count": 0,
        "positive_action_micro_accuracy": 0.477124183006536,
        "positive_action_success_count": 73,
        "sequence_success": 0.4431137724550898,
        "successful_complete_stream_count": 74,
        "successful_complete_stream_denominator": 167,
    }:
        raise Phase3EvalError("owner-approved final semantic metrics drifted")
    mechanics_gate = metrics.get("mechanics_gate")
    if not isinstance(mechanics_gate, Mapping) or mechanics_gate.get("passed") is not False:
        raise Phase3EvalError("untouched-backbone mechanics gate unexpectedly passed")

    initial_open_text_packet = _open_text_packet(
        states, initial_grades, grader_contract, parser_input_by_id
    )
    if canonical_artifact_bytes(initial_open_text_packet) != v4_files[
        "open-text-review-packet.json"
    ]:
        raise Phase3EvalError("owner-reviewed open-text packet drifted")
    open_text_dispositions = _open_text_dispositions(
        states, grades, assessments, grader_contract
    )
    raw_failure_report = {
        "count": len(json_failures),
        "failures": json_failures,
        "kind": "phase3-wp3-2-genuine-json-failures",
        "schema_version": 1,
        "source": {"immutable_run_report_sha256": IMMUTABLE_RUN_REPORT_SHA256},
    }
    failure_clusters = _failure_clusters(grades, schema_failures)
    retention_presentation = _retention_presentation(
        root, retention_rows, retention_template, tokenizer.tokenizer
    )
    if canonical_artifact_bytes(failure_clusters) != v4_files["failure-clusters.json"]:
        raise Phase3EvalError("final semantic labels altered structural failure clusters")
    if canonical_artifact_bytes(raw_failure_report) != v4_files["raw-failure-report.json"]:
        raise Phase3EvalError("final semantic labels altered genuine JSON failures")
    if canonical_artifact_bytes(retention_presentation) != v4_files[
        "retention-presentation.json"
    ]:
        raise Phase3EvalError("final semantic labels altered retention presentation")

    files = {
        "interaction-grades.jsonl": b"".join(
            canonical_artifact_bytes(row) + b"\n" for row in grades
        ),
        "interaction-metrics.json": canonical_artifact_bytes(metrics),
        "open-text-dispositions.json": canonical_artifact_bytes(open_text_dispositions),
    }
    files["wp3-2-closeout-report.json"] = canonical_artifact_bytes(
        _final_closeout_report(
            source_commit,
            files,
            metrics,
            open_text_dispositions,
            retention_presentation,
            v4_files,
        )
    )
    files["SHA256SUMS"] = _sha256sums(files)
    return files


async def publish_backbone_regrade(
    *, repository_root: Path, tokenizer_directory: Path, source_commit: str, output: Path
) -> dict[str, bytes]:
    files = await build_backbone_regrade(
        repository_root=repository_root,
        tokenizer_directory=tokenizer_directory,
        source_commit=source_commit,
    )
    publish_directory_transaction(guard_read_path(repository_root, output), files)
    return files


def _owner_open_text_assessments(states, initial_grades):
    rubrics = {rubric.state_id: rubric for rubric in build_open_text_rubrics(states)}
    pending = {
        str(grade["state_id"])
        for grade in initial_grades
        if grade["executed"]["semantic_status"] == "pending_semantic_assessment"
    }
    if (
        len(pending) != 29
        or OPEN_TEXT_FAIL_STATE_ID not in pending
        or not OPEN_TEXT_PROVENANCE_FAILURE_IDS < pending
    ):
        raise Phase3EvalError("owner-reviewed open-text population drifted")
    grade_by_id = {str(grade["state_id"]): grade for grade in initial_grades}
    assessments = {}
    for state_id in sorted(pending):
        passed = state_id != OPEN_TEXT_FAIL_STATE_ID
        reason_codes = (
            ("all_required_points_present", "no_forbidden_claims")
            if passed
            else ("wrong_result", "missing_required_fact")
        )
        assessments[state_id] = FrozenHumanAssessment(
            state_id=state_id,
            rubric_sha256=str(rubrics[state_id].as_json_object()["rubric_sha256"]),
            output_bytes_sha256=str(grade_by_id[state_id]["raw"]["output_bytes_sha256"]),
            passed=passed,
            reason_codes=reason_codes,
        )
    return assessments


def _assert_semantic_only_delta(initial_grades, final_grades) -> None:
    initial_by_id = {str(grade["state_id"]): grade for grade in initial_grades}
    if {str(grade["state_id"]) for grade in final_grades} != set(initial_by_id):
        raise Phase3EvalError("final semantic grades changed DEV identities")
    for final in final_grades:
        initial = initial_by_id[str(final["state_id"])]
        for field in ("expected_action_type", "framing", "predicted_action", "raw", "structural"):
            if final[field] != initial[field]:
                raise Phase3EvalError(f"semantic disposition altered frozen {field}")
        initial_executed = dict(initial["executed"])
        final_executed = dict(final["executed"])
        for field in ("match", "semantic_status"):
            initial_executed.pop(field)
            final_executed.pop(field)
        if final_executed != initial_executed:
            raise Phase3EvalError("semantic disposition altered non-semantic executed evidence")


def _open_text_dispositions(states, grades, assessments, grader_contract):
    rubrics = {row.state_id: row.as_json_object() for row in build_open_text_rubrics(states)}
    contract_open_text = grader_contract.get("open_text")
    contract_rows = (
        contract_open_text.get("rows") if isinstance(contract_open_text, Mapping) else None
    )
    if not isinstance(contract_rows, list) or {
        str(row.get("state_id")): row for row in contract_rows if isinstance(row, Mapping)
    } != rubrics:
        raise Phase3EvalError("final dispositions use a different open-text rubric")
    state_by_id = {state.state_id: state for state in states}
    grade_by_id = {str(grade["state_id"]): grade for grade in grades}
    counts = Counter()
    rows = []
    for state_id, rubric in rubrics.items():
        grade = grade_by_id[state_id]
        assessment = assessments.get(state_id)
        structural_pass = bool(grade["structural"]["structural_pass"])
        if assessment is None:
            disposition = "semantic_not_applicable_wrong_action_or_structure"
        elif assessment.passed and structural_pass:
            disposition = "structural_pass_semantic_pass"
        elif not assessment.passed and structural_pass:
            disposition = "structural_pass_semantic_fail"
        elif assessment.passed:
            disposition = "semantic_pass_structural_failure"
        else:
            raise Phase3EvalError("unapproved open-text disposition combination")
        counts[disposition] += 1
        rows.append(
            {
                "assessment": None if assessment is None else assessment.as_json_object(),
                "disposition": disposition,
                "executed_match": grade["executed"]["match"],
                "expected_action": state_by_id[state_id].expected.model_dump(mode="json"),
                "predicted_action": grade["predicted_action"],
                "raw_output_sha256": grade["raw"]["output_bytes_sha256"],
                "rubric": rubric,
                "semantic_status": grade["executed"]["semantic_status"],
                "state_id": state_id,
                "structural": grade["structural"],
            }
        )
    expected_counts = {
        "semantic_not_applicable_wrong_action_or_structure": 3,
        "semantic_pass_structural_failure": 2,
        "structural_pass_semantic_fail": 1,
        "structural_pass_semantic_pass": 26,
    }
    if dict(sorted(counts.items())) != expected_counts:
        raise Phase3EvalError("final open-text disposition accounting drifted")
    for state_id in OPEN_TEXT_PROVENANCE_FAILURE_IDS:
        grade = grade_by_id[state_id]
        if (
            grade["executed"]["semantic_status"] != "passed"
            or grade["executed"]["match"] is not False
            or grade["structural"]["closed_field_match"] is not False
            or grade["structural"]["licensed"] is not False
            or "reason_mismatch" not in grade["structural"]["license_block_codes"]
            or grade["predicted_action"].get("reply_to_event_id") != "e_000020"
        ):
            raise Phase3EvalError("semantic pass erased a frozen provenance failure")
    failed = grade_by_id[OPEN_TEXT_FAIL_STATE_ID]
    if failed["executed"]["semantic_status"] != "failed" or failed["executed"][
        "match"
    ] is not False:
        raise Phase3EvalError("owner-declared wrong answer did not remain a failure")
    return {
        "accounting": {**expected_counts, "total": 32},
        "assessment_provenance": "owner_wp3_2_closeout_decision_2026-08-02",
        "kind": "phase3-wp3-2-open-text-dispositions",
        "owner_decision": {
            "failed_state_id": OPEN_TEXT_FAIL_STATE_ID,
            "failure_reason_codes": ["wrong_result", "missing_required_fact"],
            "provenance_failure_semantic_pass_state_ids": sorted(
                OPEN_TEXT_PROVENANCE_FAILURE_IDS
            ),
            "reviewed_count": 29,
            "semantic_fail_count": 1,
            "semantic_pass_count": 28,
        },
        "rows": rows,
        "schema_version": 1,
    }


def _open_text_packet(states, grades, grader_contract, parser_inputs) -> dict[str, object]:
    rubrics = {row.state_id: row.as_json_object() for row in build_open_text_rubrics(states)}
    contract_open_text = grader_contract.get("open_text")
    if not isinstance(contract_open_text, Mapping):
        raise Phase3EvalError("approved grader contract has no open-text contract")
    contract_rows = contract_open_text.get("rows")
    if not isinstance(contract_rows, list) or {
        str(row.get("state_id")): row for row in contract_rows if isinstance(row, Mapping)
    } != rubrics:
        raise Phase3EvalError("reconstructed open-text rubrics drifted")
    grade_by_id = {str(row["state_id"]): row for row in grades}
    state_by_id = {state.state_id: state for state in states}
    rows = []
    review_counts = Counter()
    for state_id, rubric in rubrics.items():
        grade = grade_by_id[state_id]
        semantic_status = grade["executed"]["semantic_status"]
        review_status = (
            "pending_human_review"
            if semantic_status == "pending_semantic_assessment"
            else "not_applicable_structural_failure"
        )
        review_counts[review_status] += 1
        rows.append(
            {
                "expected_action": state_by_id[state_id].expected.model_dump(mode="json"),
                "framing": grade["framing"],
                "human_assessment": {
                    "passed": None,
                    "reason_codes": [],
                    "review_status": review_status,
                },
                "parser_input_utf8": parser_inputs[state_id].decode("utf-8"),
                "predicted_action": grade["predicted_action"],
                "raw_output_sha256": grade["raw"]["output_bytes_sha256"],
                "rubric": rubric,
                "state_id": state_id,
                "structural": grade["structural"],
            }
        )
    if len(rows) != 32:
        raise Phase3EvalError("open-text review packet does not contain exactly 32 rows")
    return {
        "counts": {
            "integrate": 18,
            "not_applicable_structural_failure": review_counts[
                "not_applicable_structural_failure"
            ],
            "pending_human_review": review_counts["pending_human_review"],
            "respond": 14,
            "total": 32,
        },
        "kind": "phase3-wp3-2-open-text-human-review-packet",
        "rows": rows,
        "schema_version": 1,
        "status": "pending_human_review_for_structurally_valid_rows",
    }


def _parse_failure_rows(grades, parser_inputs):
    json_failures = []
    schema_failures = []
    for grade in grades:
        state_id = str(grade["state_id"])
        parser_input = parser_inputs[state_id]
        try:
            value = parse_tim_json(parser_input)
        except TimJsonError as error:
            json_failures.append(
                {
                    "error": str(error),
                    "parser_input_sha256": grade["framing"]["parser_input_sha256"],
                    "parser_input_utf8": parser_input.decode("utf-8"),
                    "raw_output_sha256": grade["raw"]["output_bytes_sha256"],
                    "state_id": state_id,
                }
            )
            continue
        try:
            ACTION_ADAPTER.validate_python(value)
        except ValidationError as error:
            schema_failures.append(
                {
                    "errors": [
                        {
                            "location": [str(part) for part in item["loc"]],
                            "message": item["msg"],
                            "type": item["type"],
                        }
                        for item in error.errors(include_input=False, include_url=False)
                    ],
                    "expected_action_type": grade["expected_action_type"],
                    "parser_input_sha256": grade["framing"]["parser_input_sha256"],
                    "predicted_json": value,
                    "raw_output_sha256": grade["raw"]["output_bytes_sha256"],
                    "state_id": state_id,
                }
            )
    return json_failures, schema_failures


def _failure_clusters(grades, schema_failures) -> dict[str, object]:
    confusion = Counter(
        (
            str(row["expected_action_type"]),
            "unparsed"
            if not isinstance(row.get("predicted_action"), Mapping)
            else str(row["predicted_action"].get("type")),
        )
        for row in grades
    )
    reference_rows = [
        {
            "expected_action_type": row["expected_action_type"],
            "hard_failures": row["executed"]["hard_failures"],
            "predicted_action": row["predicted_action"],
            "state_id": row["state_id"],
        }
        for row in grades
        if row["structural"]["parse_union_valid"]
        and not row["structural"]["reference_integrity"]
    ]
    return {
        "action_confusion": [
            {"count": count, "expected": expected, "predicted": predicted}
            for (expected, predicted), count in sorted(confusion.items())
        ],
        "hard_failure_counts": dict(
            sorted(
                Counter(
                    failure
                    for row in grades
                    for failure in row["executed"]["hard_failures"]
                ).items()
            )
        ),
        "json_syntax_failure_count": sum(
            row["structural"]["parse_error"] == "TimJsonError" for row in grades
        ),
        "kind": "phase3-wp3-2-interaction-failure-clusters",
        "license_block_counts": dict(
            sorted(
                Counter(
                    code
                    for row in grades
                    for code in row["structural"]["license_block_codes"]
                ).items()
            )
        ),
        "reference_or_span_failure_count": len(reference_rows),
        "reference_or_span_failures": reference_rows,
        "schema_union_failure_count": len(schema_failures),
        "schema_union_failures": schema_failures,
        "schema_version": 1,
    }


def _retention_presentation(root, raw_rows, template_rows, tokenizer) -> dict[str, object]:
    template_by_id = {_row_text(row, "request_id"): row for row in template_rows}
    rows = []
    projected = 0
    length_ended = 0
    for raw_row in raw_rows:
        request_id = _row_text(raw_row, "request_id")
        template = template_by_id.get(request_id)
        if template is None:
            raise Phase3EvalError("retention raw record is not in the frozen blind roster")
        persisted = _persisted(root, raw_row)
        raw = _load_persisted_raw(root, persisted)
        try:
            projection = project_terminal_output(
                finish_reason=raw.finish_reason,
                output_token_ids=raw.output_token_ids,
                decoded_bytes=raw.decoded_bytes,
                tokenizer=tokenizer,
            )
        except TerminalFramingError as error:
            if raw.finish_reason != "length":
                raise Phase3EvalError("unexpected retention framing failure") from error
            length_ended += 1
            presentation = {
                "framing_failure_reason": error.reason,
                "output_utf8": raw.decoded_bytes.decode("utf-8"),
                "status": "length_terminated",
            }
        else:
            projected += 1
            presentation = {
                "framing": projection.audit_record(),
                "output_utf8": projection.parser_input.decode("utf-8"),
                "status": "projected",
            }
        rows.append(
            {
                "capability_group": template.get("capability_group"),
                "comparison_id": template.get("comparison_id"),
                "finish_reason": raw.finish_reason,
                "presentation": presentation,
                "raw_output_sha256": raw.as_json_object()["output_bytes_sha256"],
                "raw_record_sha256": persisted.sha256,
                "reference_answer_sha256": template.get("reference_answer_sha256"),
                "request_id": request_id,
            }
        )
    if set(template_by_id) != {row["request_id"] for row in rows}:
        raise Phase3EvalError("retention presentation does not close over the blind roster")
    return {
        "counts": {"length_terminated": length_ended, "projected": projected, "total": 60},
        "kind": "phase3-wp3-2-blinded-retention-presentation",
        "reference_text_included": False,
        "rows": rows,
        "schema_version": 1,
        "terminal_framing_version": TERMINAL_FRAMING_VERSION,
    }


def _final_closeout_report(
    source_commit, files, metrics, open_text, retention, v4_files
):
    return {
        "artifact_bindings": {
            name: f"sha256:{sha256(raw).hexdigest()}" for name, raw in sorted(files.items())
        },
        "closeout_status": "closed",
        "framing_version": TERMINAL_FRAMING_VERSION,
        "immutable_run_report_sha256": IMMUTABLE_RUN_REPORT_SHA256,
        "interaction_summary": {
            "active_floor_denominator": metrics["active_floor_denominator"],
            "active_floor_respond_rate": metrics["active_floor_respond_rate"],
            "closed_field_accuracy": metrics["closed_field_accuracy"],
            "correct_strict_action_type_count": metrics["correct_strict_action_type_count"],
            "duplicate_delegate_negative_idle": {
                "count": metrics["duplicate_delegate_negative_idle_count"],
                "denominator": metrics["duplicate_delegate_negative_denominator"],
            },
            "executed_success": {
                "count": metrics["executed_success_count"],
                "denominator": 300,
                "rate": metrics["executed_success_rate"],
            },
            "mechanics_gate_passed": metrics["mechanics_gate"]["passed"],
            "open_text_roster_count": open_text["accounting"]["total"],
            "open_text_pending_human_review": metrics[
                "pending_semantic_assessment_count"
            ],
            "parse_union_validity": metrics["parse_union_validity"],
            "positive_action_success": {
                "count": metrics["positive_action_success_count"],
                "denominator": metrics["positive_action_denominator"],
                "rate": metrics["positive_action_micro_accuracy"],
            },
            "successful_complete_streams": {
                "count": metrics["successful_complete_stream_count"],
                "denominator": metrics["successful_complete_stream_denominator"],
                "rate": metrics["sequence_success"],
            },
            "standard_json_valid_count": metrics["standard_json_valid_count"],
        },
        "kind": "phase3-wp3-2-offline-closeout",
        "next_gate": "wp3-3_paid_canary_requires_separate_owner_authorization",
        "old_run_sha256sums_sha256": OLD_RUN_SHA256SUMS_SHA256,
        "owner_closeout_decision": {
            "conditions_satisfied": True,
            "decision": "approved_after_exact_mechanical_open_text_dispositions",
            "semantic_review_complete": True,
        },
        "owner_framing_approval_sha256": FRAMING_APPROVAL_SHA256,
        "owner_framing_review_bundle_sha256": FRAMING_REVIEW_BUNDLE_SHA256,
        "prior_framing_regrade_v4": {
            "artifact_sha256": {
                name: f"sha256:{sha256(raw).hexdigest()}"
                for name, raw in sorted(v4_files.items())
            },
            "sha256sums_sha256": FRAMING_REGRADE_V4_SHA256SUMS,
        },
        "provider_activity": {
            "additional_spend": False,
            "checkpoint_creation": False,
            "provider_call": False,
            "resampling": False,
            "secret_access": False,
            "sealed_test_access": False,
        },
        "retention_guard_handoff": (
            "systematic truncation means a new or materially worsened truncation pattern "
            "relative to this frozen baseline; a checkpoint does not automatically fail "
            "merely because one of the 12 already-truncated baseline prompts also reaches "
            "the identical 1,024-token ceiling"
        ),
        "retention_summary": retention["counts"],
        "sampling_manifest_sha256": SAMPLING_MANIFEST_SHA256,
        "schema_version": 1,
        "source_commit": source_commit,
        "supersedes": {
            "interaction_grades_sha256": (
                "sha256:" + sha256(v4_files["interaction-grades.jsonl"]).hexdigest()
            ),
            "interaction_metrics_sha256": (
                "sha256:" + sha256(v4_files["interaction-metrics.json"]).hexdigest()
            ),
            "open_text_review_packet_sha256": (
                "sha256:" + sha256(v4_files["open-text-review-packet.json"]).hexdigest()
            ),
            "reason": "owner_open_text_dispositions_applied",
        },
    }


def _persisted(root: Path, row: Mapping[str, object]) -> PersistedRawGeneration:
    return PersistedRawGeneration(
        path=guard_read_path(root, root / _row_text(row, "path")),
        sha256=_row_text(row, "sha256"),
    )


def _verify_source_commit(root: Path, source_commit: str) -> None:
    if not re.fullmatch(r"[0-9a-f]{40}", source_commit):
        raise Phase3EvalError("source commit must be a full lowercase git revision")
    current = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if current != source_commit:
        raise Phase3EvalError("source commit does not match HEAD")


def _require_digest(raw: bytes, expected: str, label: str) -> None:
    if f"sha256:{sha256(raw).hexdigest()}" != expected:
        raise Phase3EvalError(f"{label} digest drifted")


def _row_text(row: Mapping[str, object], field: str) -> str:
    value = row.get(field)
    if not isinstance(value, str) or not value:
        raise Phase3EvalError(f"artifact row has invalid {field}")
    return value


def _json_object(raw: bytes) -> Mapping[str, object]:
    value = json.loads(raw)
    if not isinstance(value, Mapping):
        raise Phase3EvalError("bound JSON artifact is not an object")
    return value


def _json_list(raw: bytes) -> list[Mapping[str, object]]:
    value = json.loads(raw)
    if not isinstance(value, list) or any(not isinstance(row, Mapping) for row in value):
        raise Phase3EvalError("bound JSON artifact is not an object list")
    return value


def _sha256sums(files: Mapping[str, bytes]) -> bytes:
    return "".join(
        f"{sha256(files[name]).hexdigest()}  {name}\n" for name in sorted(files)
    ).encode()
