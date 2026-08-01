#!/usr/bin/env python3
"""Build the last owner-review delta before the WP2-9 replay freeze."""

from __future__ import annotations

import json
from collections import defaultdict
from hashlib import sha256
from pathlib import Path

from build_phase2_wp2_9_replay_recovery_v10 import (
    BASE,
    PROGRESS,
    ROOT,
    SEED,
    V9_PACKET,
    V9_REVIEW,
    _jsonl,
)
from build_phase2_wp2_9_replay_recovery_v10 import (
    _candidates as v10_candidates,
)

from im.assets.model import canonical_artifact_bytes
from im.generation.phase2_replay import plan_replay_review_round
from im.generation.publication import publish_directory_transaction

OUTPUT = ROOT / "review/phase2/wp2-9-replay-final-review"
V10_REVIEW = ROOT / "review/phase2/wp2-9-replay-recovery-v10-owner-review-progress.json"


def _digest(path: Path) -> str:
    return f"sha256:{sha256(path.read_bytes()).hexdigest()}"


def _inputs() -> tuple[list[dict[str, object]], dict[str, object], set[str]]:
    baseline_review = json.loads(PROGRESS.read_text())
    approved = {
        completion_id
        for group in baseline_review["groups"]
        for completion_id in group["approved_completion_ids"]
    }
    rejected = {
        item["completion_id"] for group in baseline_review["groups"] for item in group["rejected"]
    }
    candidates = [
        row
        for row in _jsonl(BASE / "normalized-candidate-pool.jsonl")
        if row["completion_id"] not in rejected
    ]

    for version in range(1, 9):
        directory = ROOT / f"review/phase2/wp2-9-replay-recovery-v{version}"
        rows = _jsonl(directory / "candidate-pool.jsonl")
        disposition = json.loads((directory / "owner-disposition.json").read_text())
        decisions = {
            f"oasst2-original:{item['assistant_message_id']}": item["decision"]
            for item in disposition["reviewed"]
        }
        if any(decisions.get(str(row["completion_id"])) != "approved" for row in rows):
            raise RuntimeError(f"recovery v{version} contains a row without owner approval")
        candidates.extend(rows)
        approved.update(str(row["completion_id"]) for row in rows)

    v9_review = json.loads(V9_REVIEW.read_text())
    if v9_review["status"] != "complete":
        raise RuntimeError("v9 owner review is incomplete")
    v9_approved = set(v9_review["approved"])
    candidates.extend(
        row
        for row in json.loads(V9_PACKET.read_text())["candidates"]
        if row["completion_id"] in v9_approved
    )
    approved.update(v9_approved)

    v10_review = json.loads(V10_REVIEW.read_text())
    if v10_review["status"] != "complete":
        raise RuntimeError("v10 owner review is incomplete")
    v10_approved = set(v10_review["approved"])
    v10 = v10_candidates()
    if {str(row["completion_id"]) for row in v10} != v10_approved:
        raise RuntimeError("v10 approval does not cover its exact candidate set")
    candidates.extend(v10)
    approved.update(v10_approved)

    references = json.loads((BASE / "reference-manifest.json").read_text())["references"]
    return candidates, references, approved


def main() -> None:
    candidates, references, approved = _inputs()
    plan = plan_replay_review_round(
        candidates,
        references,
        selection_seed=SEED,
        review_rounds=(),
    )
    missing = tuple(
        candidate
        for candidate in plan.human_review_queue
        if candidate.completion_id not in approved
    )
    if len(missing) != 65:
        raise RuntimeError(f"expected 65 newly promoted review rows, found {len(missing)}")

    by_id = {str(row["completion_id"]): row for row in candidates}
    groups: dict[tuple[str, str, str], list[dict[str, object]]] = defaultdict(list)
    for candidate in missing:
        key = (
            candidate.task_family,
            candidate.length_band,
            "multi" if candidate.is_multi_turn else "single",
        )
        groups[key].append(by_id[candidate.completion_id])

    packet = {
        "candidate_count": len(missing),
        "format_version": 1,
        "groups": [
            {
                "candidates": sorted(rows, key=lambda row: str(row["completion_id"])),
                "length_band": band,
                "task_family": family,
                "turn_kind": turn,
            }
            for (family, band, turn), rows in sorted(groups.items())
        ],
        "kind": "phase2-wp2-9-replay-final-owner-review-delta",
        "review_plan_sha256": plan.review_plan_sha256,
        "scope": (
            "Only rows newly promoted into the deterministic review queue after owner "
            "rejections. Previously reviewed rows are not resubmitted."
        ),
    }
    files = {
        "review-packet.json": canonical_artifact_bytes(packet),
        "review-evidence.json": canonical_artifact_bytes(
            {
                "baseline_owner_progress_sha256": _digest(PROGRESS),
                "current_queue_count": len(plan.human_review_queue),
                "format_version": 1,
                "kind": "phase2-wp2-9-replay-final-review-evidence",
                "previously_approved_current_queue_count": len(plan.human_review_queue)
                - len(missing),
                "recovery_sha256sums_sha256": {
                    f"v{version}": _digest(
                        ROOT / f"review/phase2/wp2-9-replay-recovery-v{version}/SHA256SUMS"
                    )
                    for version in range(1, 9)
                },
                "selected_count": len(plan.provisional_selected),
                "supervised_token_total": sum(
                    row.assistant_token_count for row in plan.provisional_selected
                ),
                "v9_owner_progress_sha256": _digest(V9_REVIEW),
                "v10_owner_progress_sha256": _digest(V10_REVIEW),
            }
        ),
    }
    files["SHA256SUMS"] = "".join(
        f"{sha256(data).hexdigest()}  {name}\n" for name, data in sorted(files.items())
    ).encode()
    publish_directory_transaction(OUTPUT, files)
    print(
        f"published {len(missing)} newly promoted rows in {len(groups)} groups; "
        f"current exact selection is {len(plan.provisional_selected)} rows / "
        f"{sum(row.assistant_token_count for row in plan.provisional_selected)} tokens"
    )


if __name__ == "__main__":
    main()
