#!/usr/bin/env python3
"""Prove the first WP2-9 owner-review recovery remains exactly feasible."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from hashlib import sha256
from pathlib import Path

from im.assets.model import canonical_artifact_bytes
from im.generation.phase2_replay import plan_replay_review_round
from im.generation.publication import publish_directory_transaction

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "review/phase2/wp2-9-replay-review"
RECOVERY = ROOT / "review/phase2/wp2-9-replay-recovery-v1"
RECOVERY_V2 = ROOT / "review/phase2/wp2-9-replay-recovery-v2"
RECOVERY_V3 = ROOT / "review/phase2/wp2-9-replay-recovery-v3"
RECOVERY_V4 = ROOT / "review/phase2/wp2-9-replay-recovery-v4"
RECOVERY_V5 = ROOT / "review/phase2/wp2-9-replay-recovery-v5"
RECOVERY_V6 = ROOT / "review/phase2/wp2-9-replay-recovery-v6"
RECOVERY_V7 = ROOT / "review/phase2/wp2-9-replay-recovery-v7"
RECOVERY_V8 = ROOT / "review/phase2/wp2-9-replay-recovery-v8"
PROGRESS = ROOT / "review/phase2/wp2-9-replay-owner-review-progress.json"
OUTPUT = ROOT / "review/phase2/wp2-9-replay-recovery-witness-v1"
SEED = "phase2-replay-public-fallback-v1"


def _jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _digest(path: Path) -> str:
    return f"sha256:{sha256(path.read_bytes()).hexdigest()}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--include-v2", action="store_true")
    parser.add_argument("--include-v3", action="store_true")
    parser.add_argument("--include-v4", action="store_true")
    parser.add_argument("--include-v5", action="store_true")
    parser.add_argument("--include-v6", action="store_true")
    parser.add_argument("--include-v7", action="store_true")
    parser.add_argument("--include-v8", action="store_true")
    args = parser.parse_args()
    recoveries = (
        (
            RECOVERY,
            RECOVERY_V2,
            RECOVERY_V3,
            RECOVERY_V4,
            RECOVERY_V5,
            RECOVERY_V6,
            RECOVERY_V7,
            RECOVERY_V8,
        )
        if args.include_v8
        else (
            RECOVERY,
            RECOVERY_V2,
            RECOVERY_V3,
            RECOVERY_V4,
            RECOVERY_V5,
            RECOVERY_V6,
            RECOVERY_V7,
        )
        if args.include_v7
        else (RECOVERY, RECOVERY_V2, RECOVERY_V3, RECOVERY_V4, RECOVERY_V5, RECOVERY_V6)
        if args.include_v6
        else (RECOVERY, RECOVERY_V2, RECOVERY_V3, RECOVERY_V4, RECOVERY_V5)
        if args.include_v5
        else (RECOVERY, RECOVERY_V2, RECOVERY_V3, RECOVERY_V4)
        if args.include_v4
        else (RECOVERY, RECOVERY_V2, RECOVERY_V3)
        if args.include_v3
        else (RECOVERY, RECOVERY_V2)
        if args.include_v2
        else (RECOVERY,)
    )
    output = (
        ROOT
        / (
            "review/phase2/wp2-9-replay-recovery-witness-v8"
            if args.include_v8
            else "review/phase2/wp2-9-replay-recovery-witness-v7"
            if args.include_v7
            else "review/phase2/wp2-9-replay-recovery-witness-v6"
            if args.include_v6
            else "review/phase2/wp2-9-replay-recovery-witness-v5"
            if args.include_v5
            else "review/phase2/wp2-9-replay-recovery-witness-v4"
            if args.include_v4
            else "review/phase2/wp2-9-replay-recovery-witness-v3"
            if args.include_v3
            else "review/phase2/wp2-9-replay-recovery-witness-v2"
        )
        if (
            args.include_v2
            or args.include_v3
            or args.include_v4
            or args.include_v5
            or args.include_v6
            or args.include_v7
            or args.include_v8
        )
        else OUTPUT
    )
    progress = json.loads(PROGRESS.read_text())
    rejected = {item["completion_id"] for group in progress["groups"] for item in group["rejected"]}
    baseline = _jsonl(BASE / "normalized-candidate-pool.jsonl")
    recovery = [
        row for recovery_dir in recoveries for row in _jsonl(recovery_dir / "candidate-pool.jsonl")
    ]
    candidates = [row for row in baseline if row["completion_id"] not in rejected] + recovery
    references = json.loads((BASE / "reference-manifest.json").read_text())["references"]
    plan = plan_replay_review_round(
        candidates,
        references,
        selection_seed=SEED,
        review_rounds=(),
    )

    selected = tuple(plan.provisional_selected)
    selected_ids = tuple(sorted(item.completion_id for item in selected))
    recovery_ids = tuple(
        sorted(item for item in selected_ids if item.startswith("oasst2-original:"))
    )
    exclusions = tuple(
        {
            "completion_id": outcome.candidate_id,
            "rejection_reasons": list(outcome.rejection_reasons),
        }
        for outcome in plan.filter_report.outcomes
        if not outcome.accepted
    )
    tokens = sum(item.assistant_token_count for item in selected)
    if (
        len(selected) != 1_000
        or tokens < 100_000
        or len(recovery_ids) != len(recovery)
        or rejected & set(selected_ids)
    ):
        raise RuntimeError("the owner-review recovery is not an exact feasible repair")

    baseline_selected = {
        row["completion_id"] for row in _jsonl(BASE / "provisional-selection.jsonl")
    }
    files = {
        "feasibility-witness.json": canonical_artifact_bytes(
            {
                "accepted_candidate_count": len(plan.filter_report.accepted),
                "added_selected_completion_ids": sorted(set(selected_ids) - baseline_selected),
                "baseline_review_packet_sha256": _digest(BASE / "review-packet.json"),
                "excluded": list(exclusions),
                "format_version": 1,
                "input_candidate_count": len(candidates),
                "kind": "phase2-wp2-9-owner-review-recovery-feasibility-witness",
                "length_band_counts": dict(
                    sorted(Counter(item.length_band for item in selected).items())
                ),
                "multi_turn_count": sum(item.is_multi_turn for item in selected),
                "owner_progress_sha256": _digest(PROGRESS),
                "recovery_sha256sums_sha256": {
                    recovery_dir.name: _digest(recovery_dir / "SHA256SUMS")
                    for recovery_dir in recoveries
                },
                "recovery_selected_completion_ids": list(recovery_ids),
                "removed_owner_rejected_completion_ids": sorted(rejected),
                "removed_selected_completion_ids": sorted(baseline_selected - set(selected_ids)),
                "scope": (
                    "Non-binding feasibility witness after the first owner-reviewed fragile "
                    "cell; the baseline review packet remains immutable."
                ),
                "selected_count": len(selected),
                "selection_seed": SEED,
                "supervised_token_total": tokens,
                "task_family_counts": dict(
                    sorted(Counter(item.task_family for item in selected).items())
                ),
            }
        ),
        "selected-completion-ids.json": canonical_artifact_bytes(
            {
                "completion_ids": list(selected_ids),
                "format_version": 1,
                "kind": "phase2-wp2-9-owner-review-recovery-selected-identities",
            }
        ),
    }
    files["SHA256SUMS"] = "".join(
        f"{sha256(data).hexdigest()}  {name}\n" for name, data in sorted(files.items())
    ).encode()
    publish_directory_transaction(output, files)
    print(
        f"published exact witness: {len(selected)} rows, {tokens} tokens, "
        f"{len(recovery_ids)} recovery rows"
    )


if __name__ == "__main__":
    main()
