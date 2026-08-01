#!/usr/bin/env python3
"""Build the minimal final-review replacement tranche for WP2-9 replay."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from collections.abc import Callable
from hashlib import sha256
from pathlib import Path

from build_phase2_wp2_9_replay_final import SEED, _inputs
from build_phase2_wp2_9_replay_recovery_v9 import PRIMARY_POOL, ROOT, _empty_manifest, _jsonl
from build_phase2_wp2_9_replay_recovery_v10 import (
    TOKENIZER,
    TOKENIZER_SHA256,
)
from build_phase2_wp2_9_replay_recovery_v10 import (
    _candidate as base_candidate,
)

from im.assets.model import artifact_digest, canonical_artifact_bytes
from im.generation.phase2_replay import finalize_replay_selection, plan_replay_review_round
from im.generation.phase2_replay_filtering import (
    BACKBONE_REVISION,
    PROJECT_AUTHORED_RECOVERY_REVISION,
    filter_replay_candidates,
)
from im.generation.phase2_replay_runner import qwen_token_counter
from im.generation.publication import publish_directory_transaction

PROGRESS = ROOT / "review/phase2/wp2-9-replay-final-owner-review-progress.json"
OUTPUT = ROOT / "review/phase2/wp2-9-replay-recovery-v11-review"
FREEZE_OUTPUT = ROOT / "review/phase2/wp2-9-replay-freeze"
V11_PROGRESS = ROOT / "review/phase2/wp2-9-replay-recovery-v11-owner-review-progress.json"
TERMINAL_PROGRESS = ROOT / "review/phase2/wp2-9-replay-terminal-owner-review-progress.json"
V12_OUTPUT = ROOT / "review/phase2/wp2-9-replay-recovery-v12-review"
V12_PROGRESS = ROOT / "review/phase2/wp2-9-replay-recovery-v12-owner-review-progress.json"

SOURCE_LICENSES = {
    "HuggingFaceH4/no_robots": "CC-BY-NC-4.0",
    "OpenAssistant/oasst2": "Apache-2.0",
    "databricks/databricks-dolly-15k": "CC-BY-SA-3.0",
    "interactionmodel/wp2-9-synthetic-recovery": "project-authored",
}

ROWS = (
    (
        "coding/debug",
        (
            (
                "My Python API now fails when some customer records omit a phone number.",
                "Inspect the traceback and the code that reads the phone field before changing it.",
            ),
            (
                "The traceback says KeyError: 'phone' on customer['phone']. What should I change?",
                (
                    "A `KeyError` means that key is absent from at least one dictionary. If the "
                    "field is optional, use `customer.get('phone')` and handle `None` explicitly, "
                    "such as returning an empty display value or skipping the call step. If the "
                    "field is required, validate each record when it enters the system and return "
                    "a clear validation error. Do not catch every exception around the endpoint; "
                    "that would hide unrelated defects."
                ),
            ),
        ),
    ),
    (
        "math/data reasoning",
        (
            (
                "A car travels one equal-distance leg at 60 mph and another at 40 mph.",
                "The average speed is not generally the simple average when "
                "the distances are equal.",
            ),
            (
                "What is the average speed for the whole trip?",
                (
                    "For equal distances, use total distance divided by total time. Let each leg "
                    "be 120 miles. The times are 120/60 = 2 hours and 120/40 = 3 hours. The car "
                    "travels 240 miles in 5 hours, so its average speed is 240/5 = 48 mph. The "
                    "simple average, 50 mph, is wrong because the car spends longer at 40 mph."
                ),
            ),
        ),
    ),
    (
        "math/data reasoning",
        (
            (
                "I roll two fair six-sided dice.",
                "Each die is independent, and each face has probability 1/6.",
            ),
            (
                "What is the probability that at least one die shows a six?",
                (
                    "Use the complement. The probability that one die is not a six is 5/6, so "
                    "the probability that neither die is a six is (5/6)^2 = 25/36. Therefore, "
                    "the probability of at least one six is 1 - 25/36 = 11/36, about 30.6%. "
                    "This includes outcomes with exactly one six and the outcome with two sixes."
                ),
            ),
        ),
    ),
    (
        "math/data reasoning",
        (
            (
                "A price starts at $100 and is reduced by 20%.",
                "After the reduction, the price is $80.",
            ),
            (
                "If it then increases by 20%, does it return to $100?",
                (
                    "No. The increase is calculated from the new $80 base, not the original "
                    "$100. Twenty percent of $80 is $16, so the increased price is $96. It ends "
                    "$4 below the original price, a net decrease of 4%. To reverse a 20% "
                    "decrease exactly, $80 must increase by $20, which is a 25% increase."
                ),
            ),
        ),
    ),
    (
        "math/data reasoning",
        (
            (
                "The sorted data set is 2, 3, 4, 5, 6.",
                "Its median is the middle value, 4.",
            ),
            (
                "If I add the outlier 100, what is the new median and why?",
                (
                    "The sorted set becomes 2, 3, 4, 5, 6, 100. With six values, the median is "
                    "the average of the two middle values: (4 + 5)/2 = 4.5. The large outlier "
                    "changes the median only slightly because the median depends on order and "
                    "middle position, not on the magnitude of every value. The mean would change "
                    "much more because it includes 100 directly in the sum."
                ),
            ),
        ),
    ),
    (
        "stable-knowledge explanation",
        (
            (
                "Is summer caused by Earth being closer to the Sun?",
                "No. The seasons are mainly caused by Earth's axial tilt.",
            ),
            (
                "How does the tilt create warmer summers and colder winters?",
                (
                    "When a hemisphere tilts toward the Sun, sunlight strikes it more directly "
                    "and the Sun stays above the horizon longer each day. That hemisphere receives "
                    "more energy and has summer. Six months later it tilts away, so sunlight "
                    "arrives at a shallower angle and days are shorter, producing winter. Earth's "
                    "changing distance from the Sun is not the main cause."
                ),
            ),
        ),
    ),
    (
        "stable-knowledge explanation",
        (
            (
                "A metal table leg and a wooden leg are in the same room.",
                "After enough time, both are usually close to the same room temperature.",
            ),
            (
                "Why does the metal still feel colder when I touch it?",
                (
                    "Metal conducts heat much better than wood. When you touch room-temperature "
                    "metal, it carries heat away from your warmer skin quickly, "
                    "cooling the contact "
                    "area and making the metal feel cold. Wood transfers heat more slowly, so your "
                    "skin near the contact stays warmer. The sensation reflects the rate of heat "
                    "flow, not necessarily a difference in the objects' temperatures."
                ),
            ),
        ),
    ),
    (
        "stable-knowledge explanation",
        (
            (
                "Does a microwave oven heat food from the inside out?",
                "Not generally. Microwave energy is absorbed within a limited depth of the food.",
            ),
            (
                "Then why can the center become hot?",
                (
                    "Microwaves make polar molecules, especially water, respond to an alternating "
                    "electric field, converting electromagnetic energy into heat throughout the "
                    "depth the waves penetrate. Heat then spreads farther by conduction. The exact "
                    "pattern depends on the food's shape, composition, and standing waves inside "
                    "the oven, which is why food can develop both hot and cold spots rather than "
                    "heating neatly from the center outward."
                ),
            ),
        ),
    ),
    (
        "stable-knowledge explanation",
        (
            (
                "Why is grass sometimes wet in the morning when it did not rain?",
                "Water vapor can condense as dew on cool grass overnight.",
            ),
            (
                "What makes the water vapor condense there?",
                (
                    "During a clear night, grass loses heat by radiating energy toward the sky and "
                    "can cool below the surrounding air temperature. If its surface reaches the "
                    "air's dew point, nearby water vapor condenses into liquid droplets. Dew is "
                    "more likely on clear, calm, humid nights. Wind can mix the air and reduce the "
                    "surface cooling that allows droplets to form."
                ),
            ),
        ),
    ),
)

V12_ROWS = (
    (
        "Write a type-safe TypeScript async map that preserves input order and rejects if any "
        "callback rejects.",
        """```ts
async function asyncMap<T, U>(
  items: readonly T[],
  callback: (item: T, index: number, items: readonly T[]) => U | Promise<U>,
): Promise<U[]> {
  return Promise.all(items.map((item, index) => callback(item, index, items)));
}
```

`T` is the input element type and `U` is the resolved output type.
`Array.prototype.map` creates the promises in input order, and `Promise.all` resolves to an array
in that same order even if individual callbacks finish out of order. If a callback throws or
returns a rejected promise, the returned promise rejects with that error. The `readonly`
annotations let callers pass mutable or readonly arrays while preventing the callback from
mutating the collection through this API. All callbacks start immediately, so this version is
appropriate when unbounded concurrency is acceptable; use a concurrency limiter when the
callback opens scarce resources such as database connections.""",
    ),
    (
        "Write an Express route that retrieves one MongoDB document by its id, validates malformed "
        "ids, returns 404 when absent, and forwards database errors.",
        """```js
const express = require("express");
const { ObjectId } = require("mongodb");
const dbo = require("../database/connection");

const router = express.Router();

router.get("/items/:id", async (req, res, next) => {
  const { id } = req.params;
  if (!ObjectId.isValid(id)) {
    return res.status(400).json({ error: "Invalid item id" });
  }

  try {
    const item = await dbo.getDb()
      .collection("items")
      .findOne({ _id: new ObjectId(id) });
    if (!item) {
      return res.status(404).json({ error: "Item not found" });
    }
    return res.json(item);
  } catch (error) {
    return next(error);
  }
});

module.exports = router;
```

The route rejects malformed identifiers before querying MongoDB, distinguishes a missing
document from a server failure, and delegates unexpected errors to Express error-handling
middleware. Rename the route and collection to match the application.""",
    ),
)


def _candidates() -> tuple[dict[str, object], ...]:
    count_tokens = qwen_token_counter(TOKENIZER)
    rows: list[dict[str, object]] = []
    for index, (family, turns) in enumerate(ROWS, 1):
        row = base_candidate(index, family, turns, count_tokens)
        row["completion_id"] = f"project-replay-recovery-v11-{index:02d}"
        row["prompt_id"] = row["completion_id"]
        rows.append(row)
    primary = next(row for row in _jsonl(PRIMARY_POOL) if row["dataset_source_role"] == "primary")
    report = filter_replay_candidates((primary, *rows), _empty_manifest())
    failures = {
        outcome.candidate_id: outcome.rejection_reasons
        for outcome in report.outcomes
        if outcome.candidate_id != primary["completion_id"] and not outcome.accepted
    }
    if failures:
        raise RuntimeError(f"v11 candidates failed the closed filter: {failures}")
    if any(not 51 <= row["assistant_token_count"]["count"] <= 150 for row in rows):
        raise RuntimeError("a v11 answer missed the required medium band")
    return tuple(rows)


def _single_candidate(
    index: int, prompt: str, answer: str, count_tokens: Callable[[str], int]
) -> dict[str, object]:
    messages = [{"role": "user", "content": prompt}, {"role": "assistant", "content": answer}]
    provenance: dict[str, object] = {
        "author_kind": "project_authored_recovery",
        "completion_count": 1,
        "completion_index": 0,
        "completion_sha256": artifact_digest(answer),
        "max_completion_tokens": 0,
        "model_revision": PROJECT_AUTHORED_RECOVERY_REVISION,
        "prompt_sha256": artifact_digest(messages[:-1]),
        "renderer": "native_source_chat",
        "request_sha256": "",
        "temperature": 0.0,
        "tokenizer_revision": BACKBONE_REVISION,
        "tools_enabled": False,
    }
    provenance["request_sha256"] = artifact_digest(
        {
            key: provenance[key]
            for key in (
                "prompt_sha256",
                "model_revision",
                "tokenizer_revision",
                "renderer",
                "temperature",
                "tools_enabled",
                "max_completion_tokens",
                "completion_count",
                "completion_index",
            )
        }
    )
    completion_id = f"project-replay-recovery-v12-{index:02d}"
    return {
        "assistant_token_count": {
            "count": count_tokens(answer),
            "tokenizer_revision": BACKBONE_REVISION,
        },
        "completion_id": completion_id,
        "dataset_source_id": "interactionmodel/wp2-9-synthetic-recovery",
        "dataset_source_revision": "v1",
        "dataset_source_role": "synthetic",
        "messages": messages,
        "prompt_id": completion_id,
        "provenance": provenance,
        "selection_seed": SEED,
        "task_family": "coding/debug",
    }


def _v12_candidates() -> tuple[dict[str, object], ...]:
    count_tokens = qwen_token_counter(TOKENIZER)
    rows = tuple(
        _single_candidate(index, prompt, answer, count_tokens)
        for index, (prompt, answer) in enumerate(V12_ROWS, 1)
    )
    primary = next(row for row in _jsonl(PRIMARY_POOL) if row["dataset_source_role"] == "primary")
    report = filter_replay_candidates((primary, *rows), _empty_manifest())
    failures = {
        outcome.candidate_id: outcome.rejection_reasons
        for outcome in report.outcomes
        if outcome.candidate_id != primary["completion_id"] and not outcome.accepted
    }
    if failures:
        raise RuntimeError(f"v12 candidates failed the closed filter: {failures}")
    if any(not 151 <= row["assistant_token_count"]["count"] <= 350 for row in rows):
        raise RuntimeError("a v12 answer missed the required long band")
    return rows


def _prove(rows: tuple[dict[str, object], ...]) -> dict[str, object]:
    candidates, references, _approved = _inputs()
    progress = json.loads(PROGRESS.read_text())
    rejected = {item["completion_id"] for item in progress["rejected"]}
    plan = plan_replay_review_round(
        (*[row for row in candidates if row["completion_id"] not in rejected], *rows),
        references,
        selection_seed=SEED,
        review_rounds=(),
    )
    selected = tuple(plan.provisional_selected)
    recovery_ids = {str(row["completion_id"]) for row in rows}
    selected_recovery = {row.completion_id for row in selected} & recovery_ids
    if selected_recovery != recovery_ids:
        raise RuntimeError("the exact repair does not select all nine v11 rows")
    return {
        "accepted_candidate_count": len(plan.filter_report.accepted),
        "format_version": 1,
        "input_candidate_count": len(candidates) - len(rejected) + len(rows),
        "kind": "phase2-wp2-9-replay-recovery-v11-feasibility-proof",
        "multi_turn_count": sum(row.is_multi_turn for row in selected),
        "selected_count": len(selected),
        "selected_v11_ids": sorted(selected_recovery),
        "supervised_token_total": sum(row.assistant_token_count for row in selected),
    }


def _digest(path: Path) -> str:
    return f"sha256:{sha256(path.read_bytes()).hexdigest()}"


def _freeze(rows: tuple[dict[str, object], ...], v12_rows: tuple[dict[str, object], ...]) -> None:
    candidates, references, approved = _inputs()
    final_progress = json.loads(PROGRESS.read_text())
    v11_progress = json.loads(V11_PROGRESS.read_text())
    terminal_progress = json.loads(TERMINAL_PROGRESS.read_text())
    v12_progress = json.loads(V12_PROGRESS.read_text())
    if any(
        progress["status"] != "complete"
        for progress in (final_progress, v11_progress, terminal_progress, v12_progress)
    ):
        raise RuntimeError("owner review is incomplete")

    rejected = {
        item["completion_id"]
        for progress in (final_progress, terminal_progress)
        for item in progress["rejected"]
    }
    v11_ids = {str(row["completion_id"]) for row in rows}
    if set(v11_progress["approved"]) != v11_ids or v11_progress["rejected"]:
        raise RuntimeError("v11 owner approval does not bind its exact candidate set")
    v12_ids = {str(row["completion_id"]) for row in v12_rows}
    if set(v12_progress["approved"]) != v12_ids or v12_progress["rejected"]:
        raise RuntimeError("v12 delegated code review does not bind its exact candidate set")
    approved.update(final_progress["approved"])
    approved.update(terminal_progress["approved"])
    approved.update(v11_ids)
    approved.update(v12_ids)
    current = (
        *[row for row in candidates if row["completion_id"] not in rejected],
        *rows,
        *v12_rows,
    )

    plan = plan_replay_review_round(current, references, selection_seed=SEED, review_rounds=())
    queue_ids = {candidate.completion_id for candidate in plan.human_review_queue}
    missing_approval = sorted(queue_ids - approved)
    if missing_approval:
        raise RuntimeError(f"current review queue has unreviewed rows: {missing_approval}")
    terminal_round = {
        "decisions": {completion_id: True for completion_id in sorted(queue_ids)},
        "review_plan_sha256": plan.review_plan_sha256,
    }
    final = finalize_replay_selection(
        current,
        references,
        selection_seed=SEED,
        review_rounds=(terminal_round,),
    )
    selected_ids = [candidate.completion_id for candidate in final.selected]
    by_id = {str(row["completion_id"]): row for row in current}
    selected_rows = [by_id[completion_id] for completion_id in selected_ids]
    selected_set = set(selected_ids)
    reserve = sorted(
        (
            outcome.candidate
            for outcome in plan.filter_report.accepted
            if outcome.candidate is not None and outcome.candidate.completion_id not in selected_set
        ),
        key=lambda candidate: candidate.completion_id,
    )
    synthetic_ids = {
        str(row["completion_id"])
        for row in selected_rows
        if row["provenance"]["author_kind"] == "project_authored_recovery"
    }
    if not synthetic_ids <= approved:
        raise RuntimeError("a project-authored recovery row lacks owner approval")

    lineage = []
    for row in selected_rows:
        source = str(row["dataset_source_id"])
        if source not in SOURCE_LICENSES:
            raise RuntimeError(f"no frozen license mapping for {source}")
        lineage.append(
            {
                "answer_author": row["provenance"]["model_revision"],
                "author_kind": row["provenance"]["author_kind"],
                "completion_id": row["completion_id"],
                "completion_sha256": row["provenance"]["completion_sha256"],
                "source_dataset": source,
                "source_license": SOURCE_LICENSES[source],
                "source_revision": row["dataset_source_revision"],
            }
        )

    source_counts = Counter(str(row["dataset_source_id"]) for row in selected_rows)
    author_counts = Counter(str(row["provenance"]["author_kind"]) for row in selected_rows)
    report = {
        "author_kind_counts": dict(sorted(author_counts.items())),
        "family_counts": dict(sorted(Counter(row.task_family for row in final.selected).items())),
        "format_version": 1,
        "kind": "phase2-wp2-9-replay-freeze-report",
        "length_band_counts": dict(
            sorted(Counter(row.length_band for row in final.selected).items())
        ),
        "multi_turn_count": sum(row.is_multi_turn for row in final.selected),
        "project_authored_recovery_count": len(synthetic_ids),
        "review_plan_sha256": plan.review_plan_sha256,
        "review_queue_count": len(queue_ids),
        "selected_count": len(final.selected),
        "source_counts": dict(sorted(source_counts.items())),
        "supervised_token_total": sum(row.assistant_token_count for row in final.selected),
    }
    if (
        report["selected_count"] != 1_000
        or report["multi_turn_count"] != 200
        or report["length_band_counts"] != {"long": 150, "medium": 350, "short": 500}
        or not 100_000 <= report["supervised_token_total"] <= 130_000
    ):
        raise RuntimeError(f"the frozen replay contract failed: {report}")

    evidence_paths = {
        "baseline": ROOT / "review/phase2/wp2-9-replay-owner-review-progress.json",
        "final_delta": PROGRESS,
        "v9": ROOT / "review/phase2/wp2-9-replay-recovery-v9-owner-review-progress.json",
        "v10": ROOT / "review/phase2/wp2-9-replay-recovery-v10-owner-review-progress.json",
        "v11": V11_PROGRESS,
        "terminal_delta": TERMINAL_PROGRESS,
        "v12": V12_PROGRESS,
    }
    owner_evidence = {
        "format_version": 1,
        "kind": "phase2-wp2-9-replay-owner-evidence",
        "progress_artifact_sha256": {
            name: _digest(path) for name, path in sorted(evidence_paths.items())
        },
        "recovery_v1_v8_sha256sums_sha256": {
            f"v{version}": _digest(
                ROOT / f"review/phase2/wp2-9-replay-recovery-v{version}/SHA256SUMS"
            )
            for version in range(1, 9)
        },
        "terminal_review_round": terminal_round,
    }
    excluded = [
        {
            "completion_id": outcome.candidate_id,
            "rejection_reasons": list(outcome.rejection_reasons),
        }
        for outcome in plan.filter_report.outcomes
        if not outcome.accepted
    ]
    files = {
        "excluded.json": canonical_artifact_bytes(excluded),
        "owner-evidence.json": canonical_artifact_bytes(owner_evidence),
        "reserve-index.json": canonical_artifact_bytes(
            {
                "count": len(reserve),
                "format_version": 1,
                "kind": "phase2-wp2-9-replay-archived-reserve",
                "rows": [
                    {
                        "completion_id": row.completion_id,
                        "owner_review_status": (
                            "approved" if row.completion_id in approved else "unreviewed"
                        ),
                    }
                    for row in reserve
                ],
            }
        ),
        "selected-replay.jsonl": b"".join(
            canonical_artifact_bytes(row) + b"\n" for row in selected_rows
        ),
        "selected-source-lineage.jsonl": b"".join(
            canonical_artifact_bytes(row) + b"\n" for row in lineage
        ),
        "selection-report.json": canonical_artifact_bytes(report),
    }
    files["freeze-manifest.json"] = canonical_artifact_bytes(
        {
            "d10_contract_sha256": _digest(ROOT / "docs/phase-2-implementation.md"),
            "file_sha256": {
                name: f"sha256:{sha256(data).hexdigest()}" for name, data in sorted(files.items())
            },
            "format_version": 1,
            "interaction_d13_closure_sha256": _digest(
                ROOT / "review/phase2/wp2-9-d13-trust-completion/closure.json"
            ),
            "interaction_selection_proof_sha256": _digest(
                ROOT / "review/phase2/wp2-9-stage2-selection-proof/stage2-selection-proof.json"
            ),
            "kind": "phase2-wp2-9-training-input-freeze",
            "reference_manifest_sha256": plan.reference_manifest_sha256,
        }
    )
    files["SHA256SUMS"] = "".join(
        f"{sha256(data).hexdigest()}  {name}\n" for name, data in sorted(files.items())
    ).encode()
    publish_directory_transaction(FREEZE_OUTPUT, files)
    print(json.dumps(report, indent=2, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--publish-review", action="store_true")
    parser.add_argument("--publish-freeze", action="store_true")
    parser.add_argument("--publish-v12-review", action="store_true")
    args = parser.parse_args()
    if sha256(TOKENIZER.read_bytes()).hexdigest() != TOKENIZER_SHA256:
        raise RuntimeError("the pinned tokenizer drifted")
    rows = _candidates()
    v12_rows = _v12_candidates()
    proof = _prove(rows)
    print(json.dumps(proof, indent=2, sort_keys=True))
    if not args.publish_review:
        if args.publish_freeze:
            _freeze(rows, v12_rows)
        if args.publish_v12_review:
            files = {
                "candidate-pool.jsonl": b"".join(
                    canonical_artifact_bytes(row) + b"\n" for row in v12_rows
                ),
                "review-packet.json": canonical_artifact_bytes(
                    {
                        "candidates": v12_rows,
                        "format_version": 1,
                        "kind": "phase2-wp2-9-replay-recovery-v12-delegated-code-review",
                        "scope": "Technical review delegated by the project owner to Codex.",
                    }
                ),
            }
            files["SHA256SUMS"] = "".join(
                f"{sha256(data).hexdigest()}  {name}\n" for name, data in sorted(files.items())
            ).encode()
            publish_directory_transaction(V12_OUTPUT, files)
        return
    files = {
        "candidate-pool.jsonl": b"".join(canonical_artifact_bytes(row) + b"\n" for row in rows),
        "feasibility-proof.json": canonical_artifact_bytes(proof),
        "review-packet.json": canonical_artifact_bytes(
            {
                "candidates": rows,
                "format_version": 1,
                "kind": "phase2-wp2-9-replay-recovery-v11-owner-review",
                "scope": "Owner review is required before any row is admitted.",
            }
        ),
    }
    files["SHA256SUMS"] = "".join(
        f"{sha256(data).hexdigest()}  {name}\n" for name, data in sorted(files.items())
    ).encode()
    publish_directory_transaction(OUTPUT, files)
    if args.publish_freeze:
        _freeze(rows, v12_rows)


if __name__ == "__main__":
    main()
