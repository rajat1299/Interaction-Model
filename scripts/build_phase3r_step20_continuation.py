#!/usr/bin/env python3
"""Build the offline exact-state Phase 3R step-20 continuation candidate."""

from __future__ import annotations

import argparse
import gzip
import json
import math
import subprocess
from collections.abc import Mapping
from hashlib import sha256
from pathlib import Path

from im.assets.model import canonical_artifact_bytes
from im.generation.publication import publish_directory_transaction

ROOT = Path(__file__).resolve().parents[1]
V3 = Path("review/phase3/wp3r-5-repetition-detector-v3-candidate-v1")
RANK16 = Path("review/phase3/wp3r-4-rank16-recovery-candidate-v3")
RUN = Path("review/phase3/wp3r-4-rank16-recovery-run-v1")
REQUESTS = Path("review/phase3/wp3-2-offline-candidate-v4/sampling-requests.json.gz")
RETENTION = Path("review/phase3/wp3-4-derived-run-candidate-v2/automatic-retention-12.json")
V3_SUMS = "sha256:e0c9e6b7f26b07665390ac560eff26535365ada471f06abdf93a9439a892aae6"
RANK16_SUMS = "sha256:056c1238a899d45fa78902940793a9a1d602820b195b11ab157b5109b0b2e139"
RUN_SUMS = "sha256:6f3095a74cd2bd2fb47c5540999cbed1f887d68c1ca702e1f1d5c3bbba47abd5"
BATCH_PLAN_SHA256 = "sha256:c5af5c98f3c001c7d28adac836d852b04aa1bf6e789dad88acd609828481e44f"
CEILING_USD = 15


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    build(args.output, source_commit=args.source_commit)


def _digest(raw: bytes) -> str:
    return f"sha256:{sha256(raw).hexdigest()}"


def _json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_bytes())
    if not isinstance(value, dict):
        raise ValueError(f"not an object: {path}")
    return value


def _verify(root: Path, rel: Path, expected: str) -> None:
    sums = root / rel / "SHA256SUMS"
    if _digest(sums.read_bytes()) != expected:
        raise ValueError(f"frozen root drifted: {rel}")
    declared = set()
    for line in sums.read_text("ascii").splitlines():
        digest, name = line.split("  ", 1)
        relative = Path(name)
        target = root / rel / relative
        if (
            relative.is_absolute()
            or ".." in relative.parts
            or sha256(target.read_bytes()).hexdigest() != digest
        ):
            raise ValueError(f"checksum does not close: {rel}")
        declared.add(name)
    actual = {
        path.relative_to(root / rel).as_posix()
        for path in (root / rel).rglob("*")
        if path.is_file() and path != sums
    }
    if actual != declared:
        raise ValueError(f"checksum inventory does not close: {rel}")


def _verify_source(root: Path, source_commit: str) -> None:
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if head != source_commit:
        raise ValueError("source commit is not exact HEAD")
    generator = Path(__file__).resolve().relative_to(root.resolve()).as_posix()
    for args in (
        ["git", "ls-files", "--error-unmatch", generator],
        ["git", "cat-file", "-e", f"{source_commit}:{generator}"],
        ["git", "diff", "--quiet"],
        ["git", "diff", "--cached", "--quiet"],
    ):
        if subprocess.run(args, cwd=root, check=False, capture_output=True).returncode:
            raise ValueError("source commit or tracked worktree is not frozen")


def learning_rate(step: int) -> float:
    if not isinstance(step, int) or not 1 <= step <= 126:
        raise ValueError("step is outside the frozen 126-step schedule")
    if step <= 10:
        return 1e-4 * step / 10
    return 1e-4 * 0.5 * (1 + math.cos(math.pi * (step - 10) / 116))


def build(output: Path, *, source_commit: str, root: Path = ROOT) -> dict[str, object]:
    _verify_source(root, source_commit)
    files, contract = _candidate_files(root, source_commit)
    publish_directory_transaction(output, files)
    return contract


def _candidate_files(root: Path, source_commit: str) -> tuple[dict[str, bytes], dict[str, object]]:
    _verify(root, V3, V3_SUMS)
    _verify(root, RANK16, RANK16_SUMS)
    _verify(root, RUN, RUN_SUMS)
    proposal = _json(root / V3 / "exact-state-continuation-proposal.json")
    report = _json(root / V3 / "review-report.json")
    batches = _json(root / RANK16 / "successor-batch-plan.json")["steps"]
    if not isinstance(batches, list) or len(batches) != 63:
        raise ValueError("rank-16 batch plan drifted")
    selected = batches[20:30]
    if [row.get("step") for row in selected if isinstance(row, dict)] != list(range(21, 31)):
        raise ValueError("continuation batch window drifted")
    if proposal.get("next_step") != {
        "expected_learning_rate": learning_rate(21),
        "global_step": 21,
        "membership_sha256": selected[0]["membership_sha256"],
    }:
        raise ValueError("step-21 continuation assertion drifted")
    token_counts = _token_counts(root, selected)
    cost = _cost_model(token_counts)
    contract = {
        "authorization": {
            "checkpoint_access": False,
            "checkpoint_creation": False,
            "paid_execution": False,
            "provider_calls": False,
            "sealed_test_access": False,
            "secret_access": False,
            "spend": False,
        },
        "bindings": {
            "detector_v3_root_sha256sums_sha256": V3_SUMS,
            "detector_v3_review_report_sha256": _digest(
                (root / V3 / "review-report.json").read_bytes()
            ),
            "immutable_run_sha256sums_sha256": RUN_SUMS,
            "rank16_batch_plan_sha256": BATCH_PLAN_SHA256,
            "rank16_candidate_sha256sums_sha256": RANK16_SUMS,
            "source_lineage": report["bindings"],
        },
        "detector_version": "retention-repetition-detector-v3",
        "evaluation_sequence": [
            {
                "on_abort": "stop_before_step_26",
                "operation": "automatic_retention_12_then_detector_v3",
                "step": 25,
            },
            {
                "on_abort": "stop_without_full_dev",
                "operation": "automatic_retention_12_then_detector_v3",
                "step": 30,
            },
            {
                "condition": "step_30_detector_v3_abort_optimizer_is_false",
                "operation": "full_dev_300",
                "step": 30,
            },
        ],
        "evaluations": {
            "full_dev_count": 300,
            "full_dev_steps": [30],
            "retention_count": 12,
            "retention_steps": [25, 30],
        },
        "kind": "phase3r-exact-step20-continuation-contract-v1",
        "resume": {
            "exact_retained_step": 20,
            "next_batch_membership_sha256": selected[0]["membership_sha256"],
            "next_global_step": 21,
            "next_learning_rate": learning_rate(21),
            "order_identity": BATCH_PLAN_SHA256,
            "retained_state": proposal["retained_state"],
            "scheduler_horizon_steps": 126,
            "seed": 20260801,
            "warmup_steps": 10,
        },
        "source_commit": source_commit,
        "steps": [
            {
                "global_step": row["step"],
                "learning_rate": learning_rate(row["step"]),
                "membership_sha256": row["membership_sha256"],
            }
            for row in selected
        ],
        "stops": {
            "after_step": 30,
            "automatic_step_31": False,
            "catastrophe_hard_stop": True,
        },
        "terminal_state": {
            "save_full_optimizer_state_at_step_30": True,
            "state_ttl_seconds": 777_600,
        },
        "training_variables_changed": [],
        "training_variables_preserved": proposal["training_variables_preserved"],
    }
    contract_raw = canonical_artifact_bytes(contract)
    cost_raw = canonical_artifact_bytes(cost)
    candidate_report = {
        "authorization": contract["authorization"],
        "candidate_status": "offline_pending_owner_review",
        "continuation_contract_sha256": _digest(contract_raw),
        "cost_model_sha256": _digest(cost_raw),
        "kind": "phase3r-exact-step20-continuation-candidate-v2",
        "retained_state_accessed_during_preparation": False,
        "source_commit": source_commit,
    }
    files = {
        "candidate-report.json": canonical_artifact_bytes(candidate_report),
        "continuation-contract.json": contract_raw,
        "cost-model.json": cost_raw,
    }
    files["SHA256SUMS"] = "".join(
        f"{sha256(raw).hexdigest()}  {name}\n" for name, raw in sorted(files.items())
    ).encode("ascii")
    return files, contract


def _token_counts(root: Path, batches: list[object]) -> dict[str, int]:
    batch_ids = {
        datum_id
        for batch in batches
        if isinstance(batch, Mapping)
        for field in ("interaction_datum_ids", "replay_datum_ids")
        for datum_id in batch[field]
    }
    sequence_lengths = {}
    with gzip.open(root / RANK16 / "rank16-datums.jsonl.gz", "rt", encoding="utf-8") as stream:
        for line in stream:
            datum = json.loads(line)
            if datum["datum_id"] in batch_ids:
                sequence_lengths[datum["datum_id"]] = len(datum["input_tokens"])
    if sequence_lengths.keys() != batch_ids:
        raise ValueError("continuation datum token inventory does not close")
    with gzip.open(root / REQUESTS, "rt", encoding="utf-8") as stream:
        requests = json.load(stream)
    retention_ids = {row["request_id"] for row in _json(root / RETENTION)["rows"]}
    dev = [row for row in requests if str(row["request_id"]).startswith("dev:")]
    retention = [row for row in requests if row["request_id"] in retention_ids]
    if len(dev) != 300 or len(retention) != 12:
        raise ValueError("continuation evaluation inventory does not close")
    return {
        "evaluation_input_tokens": sum(len(row["input_token_ids"]) for row in dev)
        + 2 * sum(len(row["input_token_ids"]) for row in retention),
        "evaluation_max_output_tokens": (300 + 24) * 1024,
        "training_tokens": sum(sequence_lengths.values()),
    }


def _cost_model(tokens: Mapping[str, int]) -> dict[str, object]:
    components = {
        "evaluation_max_sample_output": tokens["evaluation_max_output_tokens"] / 1_000_000 * 1.335,
        "evaluation_uncached_prefill": tokens["evaluation_input_tokens"] / 1_000_000 * 0.54,
        "sampler_storage_full_month_upper": 2 * 1.3836288 * 0.10,
        "step30_state_storage_full_month_upper": 3.305164149 * 0.10,
        "training": tokens["training_tokens"] / 1_000_000 * 1.177,
    }
    modeled = sum(components.values())
    if modeled >= 12:
        raise ValueError("continuation modeled cost exceeded its planning envelope")
    return {
        "assumptions": {
            "evaluation_prefill": "fully_uncached",
            "evaluation_output": "1024_tokens_for_all_324_requests",
            "storage": "full_month_upper_despite_short_ttl_and_explicit_sampler_deletion",
        },
        "ceiling_usd": CEILING_USD,
        "components_usd": components,
        "kind": "phase3r-exact-step20-continuation-cost-v2",
        "modeled_upper_usd": modeled,
        "second_epoch": False,
        "token_counts": dict(tokens),
    }


if __name__ == "__main__":
    main()
