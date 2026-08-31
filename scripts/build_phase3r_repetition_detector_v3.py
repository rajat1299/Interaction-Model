#!/usr/bin/env python3
"""Build the offline-only Phase 3R repetition-detector-v3 review packet."""

from __future__ import annotations

import argparse
import gzip
import json
import subprocess
from collections.abc import Mapping, Sequence
from hashlib import sha256
from pathlib import Path

from im.assets.model import canonical_artifact_bytes
from im.generation.publication import publish_directory_transaction
from im.training.phase3r import (
    TERMINAL_TOKEN_ID,
    repeated_ngram_signature,
    repetition_diagnostics_v3,
    retention_catastrophe,
    retention_catastrophe_v3,
)

ROOT = Path(__file__).resolve().parents[1]
RUN = Path("review/phase3/wp3r-4-rank16-recovery-run-v1")
STEP20 = RUN / "evaluations/step-020/automatic-retention-12"
V2_FIXTURES = Path("review/phase3/wp3r-4-rank16-recovery-fixtures-v1")
V3_FIXTURES = Path("review/phase3/wp3r-5-repetition-detector-v3-fixtures-v1")
RANK16 = Path("review/phase3/wp3r-4-rank16-recovery-candidate-v3")

RUN_SHA256SUMS_SHA256 = "sha256:6f3095a74cd2bd2fb47c5540999cbed1f887d68c1ca702e1f1d5c3bbba47abd5"
RANK16_SHA256SUMS_SHA256 = "sha256:056c1238a899d45fa78902940793a9a1d602820b195b11ab157b5109b0b2e139"
STATE_PATH_SHA256 = "sha256:65221ef55c1974284dd452d4139f537ccabb4dd3335aa404d0f3a60d01a223a9"
STEP20_STATE_SIZE_BYTES = 3_305_164_149
STEP20_STATE_EXPIRES_AT_UNIX = 1_786_942_197


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    build(args.output, source_commit=args.source_commit)


def build(output: Path, *, source_commit: str, root: Path = ROOT) -> dict[str, object]:
    _verify_tracked_source(root, source_commit)
    _verify_file(root / RUN / "SHA256SUMS", RUN_SHA256SUMS_SHA256)
    _verify_manifest(root / RUN / "SHA256SUMS", root / RUN)
    _verify_file(root / RANK16 / "SHA256SUMS", RANK16_SHA256SUMS_SHA256)
    _verify_manifest(root / RANK16 / "SHA256SUMS", root / RANK16)
    files, report = _candidate_files(root, source_commit)
    publish_directory_transaction(output, files)
    return report


def _candidate_files(root: Path, source_commit: str) -> tuple[dict[str, bytes], dict[str, object]]:
    validation = _detector_validation(root)
    regrade = _step20_regrade(root)
    amendment = _amendment(source_commit)
    continuation = _continuation_proposal(root)
    bindings = {
        "amendment_sha256": _digest_bytes(canonical_artifact_bytes(amendment)),
        "counterfactual_regrade_sha256": _digest_bytes(canonical_artifact_bytes(regrade)),
        "detector_validation_sha256": _digest_bytes(canonical_artifact_bytes(validation)),
        "exact_state_continuation_proposal_sha256": _digest_bytes(
            canonical_artifact_bytes(continuation)
        ),
        "immutable_run_sha256sums_sha256": RUN_SHA256SUMS_SHA256,
        "rank16_candidate_sha256sums_sha256": RANK16_SHA256SUMS_SHA256,
        "source_commit": source_commit,
    }
    report = {
        "authorization": {
            "checkpoint_access": False,
            "checkpoint_deletion": False,
            "checkpoint_download": False,
            "paid_execution": False,
            "provider_calls": False,
            "sampling": False,
            "sealed_test_access": False,
            "secret_access": False,
            "spend": False,
            "training": False,
        },
        "bindings": bindings,
        "candidate_status": "offline_pending_owner_review",
        "decision": {
            "historical_v2_run_status": "stopped_retention_catastrophe",
            "historical_v2_status_preserved": True,
            "step20_counterfactual_v3_status": "guard_would_not_fire",
            "step20_optimizer_state_disposition": "retain_untouched_pending_owner_decision",
        },
        "kind": "phase3r-repetition-detector-v3-candidate-v1",
        "source_commit": source_commit,
    }
    readme = """# Phase 3R repetition detector v3 candidate v1

This offline-only packet preserves the historical v2 stop and regrades the immutable
step-20 automatic-retention outputs with the narrower, pre-output detector v3.

The old detector found two broad repeated-phrase signatures. Detector v3 classifies both
as stylistic/structural repetition, finds zero high-confidence cyclic generation loops,
and leaves one genuine new length termination. The aggregate v3 guard would not fire.

The retained step-20 optimizer state was not read, downloaded, extended, or deleted.
The continuation proposal is non-authorizing and changes no training variable.
"""
    files = {
        "README.md": readme.encode("utf-8"),
        "detector-validation.json": canonical_artifact_bytes(validation),
        "exact-state-continuation-proposal.json": canonical_artifact_bytes(continuation),
        "retention-repetition-detector-v3-amendment.json": canonical_artifact_bytes(amendment),
        "step20-counterfactual-v3.json": canonical_artifact_bytes(regrade),
        "review-report.json": canonical_artifact_bytes(report),
    }
    files["SHA256SUMS"] = _checksums(files)
    return files, report


def _amendment(source_commit: str) -> dict[str, object]:
    return {
        "authorization": "offline_only",
        "detector_version": "retention-repetition-detector-v3",
        "high_confidence_generation_loop": {
            "all_conditions_required": True,
            "endpoint_slack_tokens": 16,
            "inspected_suffix_tokens": 256,
            "minimum_contiguous_cycles": 3,
            "minimum_suffix_coverage": 0.35,
            "stable_exact_token_period_required": True,
        },
        "historical_v2": {
            "artifact_mutation_allowed": False,
            "disposition": "stopped_retention_catastrophe",
            "preserved": True,
        },
        "kind": "phase3r-retention-repetition-detector-v3-amendment",
        "optimizer_abort": {
            "high_confidence_generation_loop_threshold": 2,
            "stylistic_or_structural_repetition_is_gating": False,
        },
        "output_classes": [
            "stylistic_or_structural_repetition",
            "high_confidence_generation_loop",
        ],
        "prohibited_transformations": [
            "output_repair",
            "resampling",
            "semantic_rewriting",
            "token_normalization",
        ],
        "source_commit": source_commit,
    }


def _detector_validation(root: Path) -> dict[str, object]:
    v2_fixture_path = root / V2_FIXTURES / "detector-fixtures.jsonl.gz"
    current_fixture_path = root / V3_FIXTURES / "current-structured-repetition-negatives.jsonl.gz"
    v2_rows = _read_gzip_jsonl(v2_fixture_path)
    current = _read_gzip_jsonl(current_fixture_path)
    by_class: dict[str, list[Mapping[str, object]]] = {}
    for row in v2_rows:
        by_class.setdefault(str(row["fixture_class"]), []).append(row)
    untouched = by_class["untouched_backbone_negative"]
    failed = by_class["failed_sft_v1_step20_positive"]
    synthetic_tokens = [900_001 + index for index in range(96)] + list(range(16)) * 4
    synthetic_tokens.append(TERMINAL_TOKEN_ID)
    synthetic = repetition_diagnostics_v3(synthetic_tokens)
    results = {
        "current_structured_repetition_explicit_negatives": _class_summary(current),
        "failed_sft_v1_positive_fixtures": _class_summary(failed),
        "synthetic_exact_suffix_cycle_positive": {
            "diagnostics": synthetic,
            "passed": synthetic["high_confidence_generation_loop"] is not None,
        },
        "untouched_backbone_negative_fixtures": _class_summary(untouched),
    }
    if results["untouched_backbone_negative_fixtures"]["high_confidence_loop_count"] != 0:
        raise ValueError("detector v3 flags an untouched-backbone negative")
    current_result = results["current_structured_repetition_explicit_negatives"]
    if current_result["high_confidence_loop_count"] != 0:
        raise ValueError("detector v3 flags a current structured-repetition negative")
    if current_result["stylistic_count"] != 2:
        raise ValueError("current structured-repetition fixtures lost the historical signal")
    if results["failed_sft_v1_positive_fixtures"]["high_confidence_loop_count"] < 1:
        raise ValueError("detector v3 does not detect known failed-SFT cyclic output")
    if not results["synthetic_exact_suffix_cycle_positive"]["passed"]:
        raise ValueError("detector v3 does not detect a synthetic exact suffix cycle")
    return {
        "bindings": {
            "current_fixture_archive_sha256": _digest_file(current_fixture_path),
            "current_fixture_source_manifest_sha256": _digest_file(
                root / V3_FIXTURES / "source-manifest.json"
            ),
            "historical_fixture_archive_sha256": _digest_file(v2_fixture_path),
            "historical_fixture_source_manifest_sha256": _digest_file(
                root / V2_FIXTURES / "source-manifest.json"
            ),
        },
        "kind": "phase3r-retention-repetition-detector-v3-validation",
        "results": results,
    }


def _class_summary(rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    diagnostics = [repetition_diagnostics_v3(_tokens(row)) for row in rows]
    return {
        "fixture_count": len(rows),
        "high_confidence_loop_count": sum(
            row["high_confidence_generation_loop"] is not None for row in diagnostics
        ),
        "stylistic_count": sum(
            row["stylistic_or_structural_repetition"] is not None for row in diagnostics
        ),
    }


def _step20_regrade(root: Path) -> dict[str, object]:
    report_path = root / STEP20 / "report.json"
    old = json.loads(report_path.read_bytes())
    raw_paths = sorted((root / STEP20 / "raw").glob("*/raw-generation.json"))
    raw_by_state = {}
    for path in raw_paths:
        row = json.loads(path.read_bytes())
        raw_by_state[str(row["state_id"])] = (path, row)
    if len(old.get("rows", [])) != 12 or len(raw_by_state) != 12:
        raise ValueError("step-20 automatic-retention inventory is not exactly 12")
    v3_rows = []
    aggregate_rows = []
    for prior in old["rows"]:
        state_id = str(prior["request_id"])
        path, raw = raw_by_state[state_id]
        actual_raw_sha = _digest_file(path)
        if actual_raw_sha != str(prior["raw_record_sha256"]):
            raise ValueError(f"immutable raw record hash mismatch for {state_id}")
        old_detector = prior["catastrophe_detector"]
        historical = repeated_ngram_signature(_tokens(raw))
        if historical != old_detector["repetition_signature"]:
            raise ValueError(f"historical repetition signature did not reproduce for {state_id}")
        diagnostics = repetition_diagnostics_v3(_tokens(raw))
        aggregate = {
            "empty_output": old_detector["empty_output"],
            "high_confidence_generation_loop": diagnostics["high_confidence_generation_loop"],
            "high_confidence_refusal": old_detector["high_confidence_refusal"],
            "interaction_protocol_imitation": old_detector["interaction_protocol_imitation"],
            "new_length_termination": old_detector["new_length_termination"],
            "stylistic_or_structural_repetition": diagnostics[
                "stylistic_or_structural_repetition"
            ],
        }
        aggregate_rows.append(aggregate)
        v3_rows.append(
            {
                "finish_reason": raw["finish_reason"],
                "output_token_count": len(_tokens(raw)),
                "raw_record_sha256": actual_raw_sha,
                "request_id": state_id,
                "v2_repetition_signature": historical,
                "v3": diagnostics,
            }
        )
    v2 = retention_catastrophe(
        [
            {
                **row,
                "repetition_signature": row["stylistic_or_structural_repetition"],
            }
            for row in aggregate_rows
        ]
    )
    v3 = retention_catastrophe_v3(aggregate_rows)
    if not v2["abort_optimizer"] or v3 != {
        "abort_optimizer": False,
        "high_confidence_first_person_refusal_count": 0,
        "high_confidence_generation_loop_count": 0,
        "interaction_protocol_json_count": 0,
        "kind": "phase3r-automatic-retention-catastrophe-v3",
        "new_length_termination_count": 1,
        "reasons": [],
        "stylistic_or_structural_repetition_count": 2,
        "whitespace_empty_output_count": 0,
    }:
        raise ValueError("step-20 v3 counterfactual does not match the reviewed disposition")
    return {
        "bindings": {
            "immutable_run_sha256sums_sha256": RUN_SHA256SUMS_SHA256,
            "old_step20_report_sha256": _digest_file(report_path),
        },
        "counterfactual_v3": v3,
        "counterfactual_v3_status": "guard_would_not_fire",
        "historical_v2": v2,
        "historical_v2_status": "stopped_retention_catastrophe",
        "historical_v2_status_preserved": True,
        "kind": "phase3r-rank16-step20-counterfactual-retention-v3",
        "rows": v3_rows,
    }


def _continuation_proposal(root: Path) -> dict[str, object]:
    training = json.loads((root / RANK16 / "training-contract.json").read_bytes())
    batches = json.loads((root / RANK16 / "successor-batch-plan.json").read_bytes())
    state_path_json = root / RUN / "evidence/0048-state_checkpoint.json"
    state = json.loads(state_path_json.read_bytes())["evidence"]
    state_path = str(state["path"])
    if (
        _digest_bytes(state_path.encode("utf-8")) != STATE_PATH_SHA256
        or state["size_bytes"] != STEP20_STATE_SIZE_BYTES
        or state["checkpoint_expires_at"] != STEP20_STATE_EXPIRES_AT_UNIX
    ):
        raise ValueError("retained step-20 state identity drifted")
    next_batch = batches["steps"][20]
    learning_rates = training["scheduler"]["learning_rate_by_step"]
    return {
        "authorization": {
            "checkpoint_access": False,
            "paid_execution": False,
            "provider_calls": False,
            "secret_access": False,
            "spend": False,
            "training": False,
        },
        "execution_if_separately_authorized": [
            "restore exact step-20 optimizer state",
            "train unchanged steps 21 through 25",
            "persist all automatic-retention-12 outputs and apply detector v3",
            "if clean, train unchanged steps 26 through 30",
            "persist automatic-retention-12 and full 300-state dev outputs",
            "stop for owner review regardless of outcome",
        ],
        "hard_maximum_global_step": 30,
        "kind": "phase3r-exact-step20-state-continuation-proposal-v1",
        "next_step": {
            "expected_learning_rate": learning_rates[20],
            "global_step": 21,
            "membership_sha256": next_batch["membership_sha256"],
        },
        "prohibited": [
            "automatic_continuation_beyond_step_30",
            "batch_order_change",
            "learning_rate_change",
            "optimizer_reset",
            "replay_coefficient_change",
            "scheduler_reset",
            "seed_change",
            "warmup_reset",
        ],
        "retained_state": {
            "created_at_unix": state["checkpoint_created_at"],
            "expires_at_unix": state["checkpoint_expires_at"],
            "observed_from_immutable_local_evidence": True,
            "path_sha256": STATE_PATH_SHA256,
            "remaining_ttl_seconds_at_evidence_capture": state["remaining_ttl_seconds"],
            "size_bytes": state["size_bytes"],
            "state_accessed_during_offline_preparation": False,
        },
        "training_variables_changed": [],
        "training_variables_preserved": {
            "lora": training["lora"],
            "optimizer": training["optimizer"],
            "replay_coefficient_float32": training["data"]["replay_coefficient_float32"],
            "scheduler": training["scheduler"],
            "seed": training["seed"],
            "terminal_supervision": training["data"]["terminal_supervision"],
        },
    }


def _tokens(row: Mapping[str, object]) -> list[int]:
    tokens = row.get("output_token_ids")
    if not isinstance(tokens, list) or any(not isinstance(token, int) for token in tokens):
        raise ValueError("fixture or raw output has malformed output_token_ids")
    return tokens


def _read_gzip_jsonl(path: Path) -> list[dict[str, object]]:
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def _verify_tracked_source(root: Path, source_commit: str) -> None:
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()
    if head != source_commit:
        raise ValueError(f"source commit mismatch: expected {source_commit}, got {head}")
    generator = Path(__file__).resolve().relative_to(root.resolve()).as_posix()
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", generator],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    present_in_commit = subprocess.run(
        ["git", "cat-file", "-e", f"{source_commit}:{generator}"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    if tracked.returncode != 0 or present_in_commit.returncode != 0:
        raise ValueError("packet generator is not contained in the claimed source commit")
    for args in (["git", "diff", "--quiet"], ["git", "diff", "--cached", "--quiet"]):
        result = subprocess.run(args, cwd=root, check=False)
        if result.returncode != 0:
            raise ValueError("tracked worktree must be clean before artifact generation")


def _verify_file(path: Path, expected: str) -> None:
    if _digest_file(path) != expected:
        raise ValueError(f"hash mismatch for {path}")


def _verify_manifest(path: Path, root: Path) -> None:
    for line in path.read_text(encoding="utf-8").splitlines():
        digest, relative = line.split("  ", 1)
        if _digest_file(root / relative) != f"sha256:{digest}":
            raise ValueError(f"manifest mismatch for {relative}")


def _digest_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def _digest_bytes(value: bytes) -> str:
    return f"sha256:{sha256(value).hexdigest()}"


def _checksums(files: Mapping[str, bytes]) -> bytes:
    return "".join(
        f"{sha256(contents).hexdigest()}  {name}\n"
        for name, contents in sorted(files.items())
    ).encode("utf-8")


if __name__ == "__main__":
    main()
