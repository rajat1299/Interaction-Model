#!/usr/bin/env python3
"""Publish the amended WP2-3 lookup closeout admitting the accepted prose-need slices.

The original `review/phase2/lookup-cluster-exit/` is immutable and is not rewritten. This builds a
new directory that references it by digest and adds only the streams whose slice reached a
pre-registered CLEAN_PASS.
"""

from __future__ import annotations

import argparse
import json
from hashlib import sha256
from pathlib import Path

from im.assets.model import canonical_artifact_bytes
from im.generation.phase2_lookup_prose_addendum import (
    checksums,
    evaluate_prose_need_gate,
    load_returned_rounds,
)
from im.generation.publication import publish_directory_transaction

ADDENDUM = Path("review/phase2/lookup-prose-need-addendum-v1")
ORIGINAL = Path("review/phase2/lookup-cluster-exit")

SLICES = (
    {
        "slice_id": "prose_need_canary",
        "packet": ADDENDUM / "packet",
        "results": ADDENDUM / "results",
        "family": "live_lookup_lifecycle",
        "shape": "prose_need",
        "frozen_pairs": ADDENDUM / "frozen-pairs.json",
        "seed": "phase2-lookup-prose-need-addendum-v2",
        "scaffold": "unresolved need vs bare mention in an empty draft",
    },
    {
        "slice_id": "prose_need_duplicate",
        "packet": ADDENDUM / "wave-packet-duplicate",
        "results": ADDENDUM / "wave-results-duplicate",
        "family": "lookup_latency_duplicate_pressure",
        "shape": "prose_need_under_contention",
        "frozen_pairs": ADDENDUM / "wave-frozen-pairs.json",
        "seed": "prose-need-wave-duplicate-v1",
        "scaffold": "unresolved need vs bare mention while an equivalent request is pending",
    },
)

STALE_SLICE_DISPOSITION = {
    "disposition": "explicitly_dropped",
    "reason": (
        "The negative arm is a plain declarative already covered by the canary and duplicate "
        "slice; the accepted lookup pool already contains multi-subject abandonment and "
        "stale-result "
        "families with reviewed skip and subsequent-need behavior. The proposed slice therefore "
        "tests an intersection rather than a missing behavior and does not justify a spec "
        "amendment, another teacher round, or more owner review."
    ),
    "slice_id": "prose_need_stale",
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ADDENDUM / "amended-lookup-closeout")
    args = parser.parse_args()

    original = json.loads((ORIGINAL / "exit-report.json").read_bytes())
    original_pool = json.loads((ORIGINAL / "accepted-pool.json").read_bytes())
    admitted, ledger_entries, slice_reports = [], [], []

    for spec in SLICES:
        outcome = evaluate_prose_need_gate(
            spec["packet"], load_returned_rounds(spec["packet"], spec["results"])
        )
        if outcome["disposition"] != "CLEAN_PASS":
            raise SystemExit(
                f"{spec['slice_id']} is {outcome['disposition']}; only CLEAN_PASS slices are "
                "admitted. Nothing published."
            )
        streams = json.loads((spec["packet"] / "raw-streams.json").read_bytes())["streams"]
        for stream in streams:
            admitted.append(
                {
                    "arm": stream["arm"],
                    "decision_count": len(stream["actions"]),
                    "family": spec["family"],
                    "logical_stream_id": stream["logical_stream_id"],
                    "shape": spec["shape"],
                    "stream_sha256": stream["stream_sha256"],
                    "wave": spec["slice_id"],
                    "whole_stream_accepted": True,
                }
            )
        ledger_entries.append(
            {
                "family": spec["family"],
                "frozen_pairs_sha256": _digest(spec["frozen_pairs"]),
                "lexical_scaffold": spec["scaffold"],
                "selection_seed": spec["seed"],
                "shape": spec["shape"],
                "split": "train",
                "split_ledger_entry": f"{spec['shape']}@{spec['family']}",
            }
        )
        slice_reports.append(
            {
                "disposition": outcome["disposition"],
                "false_delegates": outcome["false_delegates"],
                "negative_restraint": outcome["negative_restraint"],
                "positive_exact_delegates": outcome["positive_exact_delegates"],
                "slice_id": spec["slice_id"],
                "stream_count": len(streams),
            }
        )

    prior = {stream["stream_sha256"] for stream in original_pool["streams"]}
    collisions = sorted(prior & {stream["stream_sha256"] for stream in admitted})
    if collisions:
        raise SystemExit(f"admitted streams collide with the original pool: {collisions}")

    added_decisions = sum(stream["decision_count"] for stream in admitted)
    pool = {
        "amends": {
            "original_accepted_pool_sha256": _digest(ORIGINAL / "accepted-pool.json"),
            "original_exit_preserved": True,
            "original_path": str(ORIGINAL),
        },
        "format_version": 1,
        "kind": "phase2-lookup-amended-accepted-pool",
        "streams": original_pool["streams"] + admitted,
        "teacher_agreement_used_as_selection_feature": False,
    }
    report = {
        "accepted_pool": {
            "added_decision_count": added_decisions,
            "added_stream_count": len(admitted),
            "decision_count": original["accepted_pool"]["decision_count"] + added_decisions,
            "original_decision_count": original["accepted_pool"]["decision_count"],
            "original_stream_count": original["accepted_pool"]["stream_count"],
            "stream_count": original["accepted_pool"]["stream_count"] + len(admitted),
        },
        "amends": {
            "original_exit_report_sha256": _digest(ORIGINAL / "exit-report.json"),
            "original_status_preserved": original["status"],
            "rewrites_original": False,
        },
        "d7_owner_labor": {
            "chat_rounds_uploaded": 5,
            "counts_as_review_labor": True,
            "note": (
                "Three canary rounds and two duplicate-slice rounds. Owner review of returned "
                "output is included; UI and discussion time are not fabricated from unavailable "
                "timestamps."
            ),
        },
        "format_version": 1,
        "kind": "phase2-lookup-amended-exit-report",
        "label_origin": {
            "note": (
                "Every admitted decision matched its oracle without disagreement, so no "
                "adjudication arose and no human gold label was created."
            ),
            "oracle_teacher_agreement": added_decisions,
            "teacher_auto_trusted": 0,
            "total": added_decisions,
        },
        "phase4_reservoir": {
            "added_records": 0,
            "note": (
                "Explicitly zero, not omitted: no non-equivalent pair arose in either slice, so "
                "there was nothing to adjudicate and nothing to retain."
            ),
        },
        "not_admitted": [STALE_SLICE_DISPOSITION],
        "slices": slice_reports,
        "split_ledger": ledger_entries,
        "status": "closed",
        "teacher_agreement_used_as_selection_feature": False,
        "trust": {
            "cleared_cell_count": 0,
            "note": (
                "The prose_need cells enter UNCLEARED. A clean teacher run at n=6 per arm is "
                "evidence that the boundary is labelable; it is not evidence that the cell is "
                "cleared, and no confirmed directional failure exists either way."
            ),
            "prose_need_cells": "uncleared",
            "state": "all_lookup_cells_uncleared",
        },
        "work_package": "WP2-3",
    }

    files = {
        "accepted-pool.json": canonical_artifact_bytes(pool),
        "exit-report.json": canonical_artifact_bytes(report),
        "split-ledger.json": canonical_artifact_bytes(
            {
                "entries": ledger_entries,
                "format_version": 1,
                "kind": "phase2-lookup-prose-need-split-ledger",
            }
        ),
        "phase4-reservoir.jsonl": b"",
        "EXIT-REPORT.md": _markdown(report, slice_reports).encode(),
    }
    files["SHA256SUMS"] = checksums(files)
    publish_directory_transaction(args.output, files)
    print(
        f"published amended closeout: {report['accepted_pool']['stream_count']} streams "
        f"({len(admitted)} added) / {report['accepted_pool']['decision_count']} decisions "
        f"at {args.output}"
    )


def _digest(path: Path) -> str:
    return "sha256:" + sha256(path.read_bytes()).hexdigest()


def _markdown(report: dict, slices: list[dict]) -> str:
    rows = "\n".join(
        f"| {item['slice_id']} | {item['stream_count']} | {item['negative_restraint']}/6 | "
        f"{item['positive_exact_delegates']}/6 | {item['false_delegates']} | "
        f"{item['disposition']} |"
        for item in slices
    )
    pool = report["accepted_pool"]
    return f"""# WP2-3 lookup closeout — amended for accepted prose-need slices

The original exit at `review/phase2/lookup-cluster-exit/` is **immutable and preserved**. It is
referenced here by digest and is not rewritten. Its recorded status remains
`{report["amends"]["original_status_preserved"]}`.

## Admitted

| Slice | Streams | Negative restraint | Positive exact-span | False delegates | Disposition |
|---|---|---|---|---|---|
{rows}

Accepted pool: **{pool["original_stream_count"]} → {pool["stream_count"]} streams**
({pool["added_stream_count"]} added), **{pool["original_decision_count"]} →
{pool["decision_count"]} decisions** ({pool["added_decision_count"]} added).

Only slices that reached a pre-registered `CLEAN_PASS` are admitted. The builder refuses to publish
otherwise.

## Trust

The `prose_need` cells enter **UNCLEARED**. A clean teacher run at n=6 per arm shows the boundary is
labelable; it does not clear the cell, and no confirmed directional failure exists in either
direction. Teacher agreement was not used as a selection feature at any point.

## Reservoir

Zero records added, stated explicitly rather than omitted: no non-equivalent pair arose in either
slice, so there was nothing to adjudicate and nothing to retain.

## Explicitly dropped

The stale-boundary slice is **not admitted and is explicitly dropped**. Its negative arm is a
plain declarative already covered by the canary and duplicate slice. Its positive
abandonment-then-new-need behavior already exists in the accepted lookup pool at scale. The
proposed slice therefore tests an intersection rather than a missing behavior and does not justify
a spec amendment, another teacher round, or more owner review. The pre-registered frozen pairs
remain historical evidence and are not rewritten.

## Bounded claim

Twenty-four streams across two structural contexts establish that prose-need is labelable in an
empty draft and under contention. That is a corpus-coverage result, not evidence of model
generalization, which remains a Phase 3 question.
"""


if __name__ == "__main__":
    main()
