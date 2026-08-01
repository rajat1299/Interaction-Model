#!/usr/bin/env python3
"""Build the final reviewed-rejection replacement slice for WP2-9 replay."""

from __future__ import annotations

import argparse
import json
from hashlib import sha256

from build_phase2_wp2_9_replay_recovery_v9 import (
    BASE,
    PRIMARY_POOL,
    PROGRESS,
    ROOT,
    SEED,
    TOKENIZER,
    TOKENIZER_SHA256,
    _empty_manifest,
    _jsonl,
)

from im.assets.model import artifact_digest, canonical_artifact_bytes
from im.generation.phase2_replay import plan_replay_review_round
from im.generation.phase2_replay_filtering import (
    BACKBONE_REVISION,
    PROJECT_AUTHORED_RECOVERY_REVISION,
    filter_replay_candidates,
)
from im.generation.phase2_replay_runner import qwen_token_counter
from im.generation.publication import publish_directory_transaction

V9_PACKET = ROOT / "review/phase2/wp2-9-replay-recovery-v9-review/review-packet.json"
V9_REVIEW = ROOT / "review/phase2/wp2-9-replay-recovery-v9-owner-review-progress.json"
OUTPUT = ROOT / "review/phase2/wp2-9-replay-recovery-v10-review"

STABLE_ROWS = (
    (
        ("What causes ocean tides?", "The Moon's gravity is the main cause of ocean tides."),
        (
            "Why do many coasts get two high tides in roughly one day?",
            (
                "The Moon's gravity produces two broad tidal bulges, one facing the Moon and "
                "one opposite it. As Earth rotates through them, many coasts get two high and "
                "two low tides per lunar day. Local geography can change this pattern."
            ),
        ),
    ),
    (
        (
            "What is an induction cooktop?",
            "It is a cooktop that heats compatible cookware using a changing magnetic field.",
        ),
        (
            "Why does the pan get hot while the cooktop stays comparatively cool?",
            (
                "A coil beneath the glass creates a changing magnetic field that induces "
                "currents inside compatible cookware, making the pan produce heat. The glass "
                "is not heated directly, though contact with the hot pan warms it. Magnetic "
                "cookware couples best."
            ),
        ),
    ),
    (
        (
            "Why are leaves green?",
            (
                "Chlorophyll absorbs much of the red and blue light used in photosynthesis "
                "and reflects green light."
            ),
        ),
        (
            "Why do many leaves turn yellow, orange, or red in autumn?",
            (
                "Shorter days and cooler weather cause many trees to stop replacing green "
                "chlorophyll. As it breaks down, yellow and orange carotenoids become visible. "
                "Some leaves produce red anthocyanins; species and weather affect the result."
            ),
        ),
    ),
    (
        (
            "Does a GPS receiver send my location to satellites?",
            (
                "No. An ordinary GPS receiver determines its position by listening to "
                "satellite signals."
            ),
        ),
        (
            "How can it calculate a position just by listening?",
            (
                "Each satellite broadcasts its location and transmission time. The receiver "
                "uses arrival delays to estimate distances. Signals from four "
                "satellites let it solve for position and clock error by trilateration. GPS "
                "positioning is receive-only, though apps may later share the result."
            ),
        ),
    ),
    (
        (
            "What do noise-canceling headphones do?",
            "They use microphones and speakers to reduce some unwanted ambient sound.",
        ),
        (
            "Why are they usually better at removing engine hum than nearby speech?",
            (
                "Active cancellation measures outside noise and generates an opposing pressure "
                "wave. Steady, low-frequency hum changes slowly enough to track well. Speech "
                "changes rapidly and contains higher frequencies, where small timing and fit "
                "errors leave more sound audible."
            ),
        ),
    ),
    (
        (
            "What makes bread dough expand?",
            "Gas bubbles become trapped in the dough's elastic structure.",
        ),
        (
            "How do yeast and baking turn those bubbles into a risen loaf?",
            (
                "Yeast consumes sugars and releases carbon dioxide, which the dough's structure "
                "traps in small bubbles during proofing. In the oven, those gases expand and "
                "water makes steam. Heat then sets the starches and proteins, preserving the "
                "loaf's airy structure."
            ),
        ),
    ),
    (
        (
            "Why do we add leap days?",
            "They keep the calendar aligned with Earth's orbit around the Sun.",
        ),
        (
            "Why are years divisible by 100 skipped unless they are also divisible by 400?",
            (
                "A seasonal year is slightly shorter than the quarter-day assumption behind "
                "leap years every four years. Skipping most century leap days corrects that "
                "small excess. Years divisible by 400 remain leap years, keeping the calendar "
                "closely aligned with the seasons."
            ),
        ),
    ),
    (
        (
            "Why does white light form different rainbow colors?",
            (
                "Water bends different wavelengths by slightly different amounts, "
                "separating the colors."
            ),
        ),
        (
            "Why does that separated light appear as a curved bow instead of a colored patch?",
            (
                "Visible raindrops send rainbow light toward you at a fixed angle around "
                "the point opposite the Sun. Drops at that angle form a circle in your view. "
                "The ground usually hides the lower portion, leaving an arc. Each observer sees "
                "a different rainbow."
            ),
        ),
    ),
    (
        (
            "My Python service becomes slow after it has been running for several hours.",
            (
                "Collect timing and memory profiles while it is healthy and again when it "
                "slows down."
            ),
        ),
        (
            "It became slow again. Which exact line is broken?",
            (
                "There is not enough evidence to name a line yet. Compare CPU profiles, "
                "allocation or heap snapshots, request timings, and database or network waits "
                "between the healthy and slow periods. Also capture the input and workload "
                "when the slowdown begins. A growing object count suggests a leak, while stable "
                "memory with one hot function suggests a CPU bottleneck. Those measurements "
                "can identify a specific line without guessing from the symptom alone."
            ),
        ),
    ),
    (
        (
            "Class A averaged 70 points and Class B averaged 80 points.",
            (
                "Those are the two class averages, but they do not reveal how many students "
                "were in each class."
            ),
        ),
        (
            "What is the exact average across both classes?",
            (
                "The exact combined average cannot be determined without the number of students "
                "in each class. It is a weighted average: if Class A has a students and Class B "
                "has b students, the result is (70a + 80b) / (a + b). It would be 75 only if "
                "the classes were the same size. For example, 20 students in A and 30 in B "
                "would give (70×20 + 80×30) / 50 = 76."
            ),
        ),
    ),
    (
        (
            (
                "Laptop A has a faster processor and 8 GB of memory. Laptop B has a slower "
                "processor, 16 GB of memory, and twice the battery life."
            ),
            "Laptop A favors CPU speed, while Laptop B favors memory capacity and battery life.",
        ),
        (
            "Which one is better?",
            (
                "Neither is universally better from those specifications alone. Laptop A is "
                "the stronger choice for workloads dominated by processor speed, provided "
                "8 GB of memory is sufficient. Laptop B is better for heavier multitasking, "
                "larger memory demands, and long periods away from power. Other facts—price, "
                "storage, screen, weight, repairability, and the exact processors—could change "
                "the decision. Choose A for CPU-bound work and B when memory or battery life "
                "matters more."
            ),
        ),
    ),
)

ROW_FAMILIES = ("stable-knowledge explanation",) * 8 + (
    "coding/debug",
    "math/data reasoning",
    "evidence-grounded comparison/recommendation",
)


def _candidate(
    index: int,
    family: str,
    turns: tuple[tuple[str, str], tuple[str, str]],
    count_tokens: object,
) -> dict[str, object]:
    messages = [
        {"role": role, "content": content}
        for user, assistant in turns
        for role, content in (("user", user), ("assistant", assistant))
    ]
    answer = messages[-1]["content"]
    provenance: dict[str, object] = {
        "author_kind": "project_authored_recovery",
        "model_revision": PROJECT_AUTHORED_RECOVERY_REVISION,
        "tokenizer_revision": BACKBONE_REVISION,
        "renderer": "native_source_chat",
        "temperature": 0.0,
        "tools_enabled": False,
        "max_completion_tokens": 0,
        "completion_count": 1,
        "completion_index": 0,
        "prompt_sha256": artifact_digest(messages[:-1]),
        "request_sha256": "",
        "completion_sha256": artifact_digest(answer),
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
    return {
        "completion_id": f"project-replay-recovery-v10-{index:02d}",
        "prompt_id": f"project-replay-recovery-v10-{index:02d}",
        "dataset_source_id": "interactionmodel/wp2-9-synthetic-recovery",
        "dataset_source_revision": "v1",
        "dataset_source_role": "synthetic",
        "task_family": family,
        "messages": messages,
        "assistant_token_count": {
            "count": count_tokens(answer),
            "tokenizer_revision": BACKBONE_REVISION,
        },
        "provenance": provenance,
        "selection_seed": SEED,
    }


def _candidates() -> tuple[dict[str, object], ...]:
    count_tokens = qwen_token_counter(TOKENIZER)
    rows = tuple(
        _candidate(index, family, turns, count_tokens)
        for index, (family, turns) in enumerate(zip(ROW_FAMILIES, STABLE_ROWS, strict=True), 1)
    )
    primary = next(row for row in _jsonl(PRIMARY_POOL) if row["dataset_source_role"] == "primary")
    report = filter_replay_candidates((primary, *rows), _empty_manifest())
    failures = {
        outcome.candidate_id: outcome.rejection_reasons
        for outcome in report.outcomes
        if outcome.candidate_id != primary["completion_id"] and not outcome.accepted
    }
    if failures:
        raise RuntimeError(f"v10 candidates failed the closed filter: {failures}")
    bands = {row["completion_id"]: row["assistant_token_count"]["count"] for row in rows}
    expected = (range(1, 51),) * 8 + (range(51, 151),) * 3
    if any(
        row["assistant_token_count"]["count"] not in valid for row, valid in zip(rows, expected)
    ):
        raise RuntimeError(f"v10 recovery rows missed their frozen length bands: {bands}")
    return rows


def _prove(candidates: tuple[dict[str, object], ...]) -> dict[str, object]:
    original_review = json.loads(PROGRESS.read_text())
    original_rejected = {
        item["completion_id"] for group in original_review["groups"] for item in group["rejected"]
    }
    baseline = [
        row
        for row in _jsonl(BASE / "normalized-candidate-pool.jsonl")
        if row["completion_id"] not in original_rejected
    ]
    recovery = [
        row
        for version in range(1, 9)
        for row in _jsonl(
            ROOT / f"review/phase2/wp2-9-replay-recovery-v{version}/candidate-pool.jsonl"
        )
    ]
    v9_review = json.loads(V9_REVIEW.read_text())
    if v9_review["status"] != "complete":
        raise RuntimeError("v9 owner review is incomplete")
    v9_approved = set(v9_review["approved"])
    v9_rows = [
        row
        for row in json.loads(V9_PACKET.read_text())["candidates"]
        if row["completion_id"] in v9_approved
    ]
    references = json.loads((BASE / "reference-manifest.json").read_text())["references"]
    plan = plan_replay_review_round(
        (*baseline, *recovery, *v9_rows, *candidates),
        references,
        selection_seed=SEED,
        review_rounds=(),
    )
    selected = tuple(plan.provisional_selected)
    selected_ids = {item.completion_id for item in selected}
    v10_ids = {str(row["completion_id"]) for row in candidates}
    reviewed_v9 = set(v9_review["approved"]) | set(v9_review["rejected"])
    return {
        "accepted_candidate_count": len(plan.filter_report.accepted),
        "input_candidate_count": len(baseline) + len(recovery) + len(v9_rows) + len(candidates),
        "multi_turn_count": sum(item.is_multi_turn for item in selected),
        "selected_count": len(selected),
        "selected_unreviewed_v9_ids": sorted(
            selected_ids
            - reviewed_v9
            - v10_ids
            - {str(row["completion_id"]) for row in baseline}
            - {str(row["completion_id"]) for row in recovery}
        ),
        "selected_v10_ids": sorted(selected_ids & v10_ids),
        "supervised_token_total": sum(item.assistant_token_count for item in selected),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--publish-review", action="store_true")
    args = parser.parse_args()
    if sha256(TOKENIZER.read_bytes()).hexdigest() != TOKENIZER_SHA256:
        raise RuntimeError("the pinned tokenizer drifted")
    candidates = _candidates()
    proof = _prove(candidates)
    print(json.dumps(proof, indent=2, sort_keys=True))
    if not args.publish_review:
        return
    files = {
        "candidate-pool.jsonl": b"".join(
            canonical_artifact_bytes(row) + b"\n" for row in candidates
        ),
        "feasibility-probe.json": canonical_artifact_bytes(proof),
        "review-packet.json": canonical_artifact_bytes(
            {
                "candidates": candidates,
                "format_version": 1,
                "kind": "phase2-wp2-9-replay-recovery-v10-owner-review",
                "scope": "Owner review is required before any row is admitted.",
            }
        ),
    }
    files["SHA256SUMS"] = "".join(
        f"{sha256(data).hexdigest()}  {name}\n" for name, data in sorted(files.items())
    ).encode()
    publish_directory_transaction(OUTPUT, files)
    print(f"published {len(candidates)} review candidates to {OUTPUT}")


if __name__ == "__main__":
    main()
