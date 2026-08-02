#!/usr/bin/env python3
"""Build the mechanically eligible WP2-7 public-fallback pool and feasibility witness."""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path

from im.generation.phase2_replay_allocation import (
    AllocationFailure,
    AllocationResult,
    choose_feasibility_witness,
)
from im.generation.phase2_replay_filtering import (
    COMPOSITION_QUOTAS,
    LENGTH_BANDS,
    filter_replay_candidates,
)
from im.generation.phase2_replay_public import (
    NO_ROBOTS_REVISION,
    NO_ROBOTS_SOURCE_ID,
    prepare_no_robots_rows,
)
from im.generation.phase2_replay_runner import qwen_token_counter
from im.generation.phase2_replay_sources import candidate_target

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "review/phase2/replay-public-fallback-v1"
NO_ROBOTS = (
    ROOT
    / ".cache/replay-sources"
    / f"no-robots-{NO_ROBOTS_REVISION}"
    / "train.jsonl"
)
TOKENIZER = (
    ROOT
    / ".cache/replay-sources"
    / "995ad96eacd98c81ed38be0c5b274b04031597b0"
    / "tokenizer.json"
)
V14 = (
    ROOT
    / "review/phase2/replay-terminal-recovery-v2/corrected-v14-working-pool.jsonl"
)
PILOT = ROOT / "review/phase2/replay-terminal-recovery-v2/execution/pool.jsonl"
SEED = "phase2-replay-public-fallback-v1"
TARGET_EXAMPLES = 1_000
MULTI_TURN_TARGET = 200
TOKEN_MINIMUM = 100_000
TOKEN_MAXIMUM = 130_000

PILOT_REJECTIONS = frozenset(
    {
        "4be87b0a8bac07d3ba3cd5bb74c785d8",
        "493df85bf833643576441863bb9c0c5c",
        "f9406da11ccdc8cdea972be611392c47",
        "97057a057505e75d6ac96f56f5a1142d",
        "910678ff009ba58050d697e0d6aa919f",
    }
)
PILOT_CONCERNS = frozenset(
    {
        "329c9418ea3aadb6eb4178db1337ff17",
        "95fa1008e253fa0069b9c5c20a8c9bdc",
        "961cc31a4e558a0d387e5364cd861bd2",
        "34bcb7a18a2cf9df4eb213dbc150c076",
        "8d3f9501136ef8d6e9dc637e84faf7b1",
        "e1ee41056e0c20406268af647b58483d",
        "ac3de262bfb3b6a582d976c4c6c840cb",
    }
)
def _jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _empty_manifest() -> dict[str, object]:
    return {
        "interaction_texts": (),
        "development_texts": (),
        "test_texts": (),
        "demo_texts": (),
        "approved_responses": (),
        "heldout_assets": {},
        "project_nonces": (),
        "project_vocabulary_phrases": (),
    }


def _band(row: dict[str, object]) -> str:
    count = row["assistant_token_count"]["count"]  # type: ignore[index]
    for band, (minimum, maximum, _target) in LENGTH_BANDS.items():
        if minimum <= count <= maximum:
            return band
    raise AssertionError(f"row outside replay bands: {row['completion_id']}")


def _multi(row: dict[str, object]) -> bool:
    return sum(message["role"] == "user" for message in row["messages"]) > 1  # type: ignore[union-attr]


def _cell(row: dict[str, object]) -> tuple[str, str, str]:
    return (
        str(row["task_family"]),
        _band(row),
        "multi" if _multi(row) else "single",
    )


def _tokens(row: dict[str, object]) -> int:
    return int(row["assistant_token_count"]["count"])  # type: ignore[index]


def _rank(row: dict[str, object]) -> str:
    return sha256(f"{SEED}|{row['completion_id']}".encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class _AllocationRow:
    completion_id: str
    task_family: str
    length_band: str
    turn_kind: str
    assistant_token_count: int
    raw: dict[str, object] = field(compare=False, hash=False)


def _normalise_qwen(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    normalised: list[dict[str, object]] = []
    for row in rows:
        copied = deepcopy(row)
        copied["dataset_source_role"] = "secondary"
        normalised.append(copied)
    return normalised


def _qwen_rows() -> tuple[list[dict[str, object]], set[str]]:
    rows = _jsonl(V14)
    pilot = [
        row
        for row in _jsonl(PILOT)
        if row["prompt_id"] not in PILOT_REJECTIONS
        and row["dataset_source_id"] != "phase2/synthetic-topup-v1"
    ]
    existing = {row["completion_id"] for row in rows}
    rows.extend(row for row in pilot if row["completion_id"] not in existing)
    return _normalise_qwen(rows), set(PILOT_CONCERNS)


def _public_rows() -> tuple[list[dict[str, object]], dict[str, dict[str, object]], Mapping]:
    prepared = prepare_no_robots_rows(
        _jsonl(NO_ROBOTS),
        count_tokens=qwen_token_counter(TOKENIZER),
    )
    lineage = {str(row["prompt_id"]): row for row in prepared.lineage}
    accepted: list[dict[str, object]] = []
    rejection_counts: Counter[str] = Counter()
    # Per-row filtering performs all content-independent checks. Cross-row duplicate checks run
    # once on the final 1,250-row pool below.
    for candidate in prepared.candidates:
        outcome = filter_replay_candidates((candidate,), _empty_manifest()).outcomes[0]
        if outcome.accepted:
            accepted.append(candidate)
        else:
            rejection_counts.update(outcome.rejection_reasons)
    return accepted, lineage, {
        "preparation": prepared.dispositions,
        "filter_rejections": dict(sorted(rejection_counts.items())),
    }


def _allocate(rows: list[dict[str, object]]) -> AllocationResult | AllocationFailure:
    wrapped = [
        _AllocationRow(
            completion_id=str(row["completion_id"]),
            task_family=str(row["task_family"]),
            length_band=_band(row),
            turn_kind="multi" if _multi(row) else "single",
            assistant_token_count=_tokens(row),
            raw=row,
        )
        for row in rows
    ]
    result = choose_feasibility_witness(
        wrapped,
        family_quotas=COMPOSITION_QUOTAS,
        replay_bands=tuple(LENGTH_BANDS.items()),
        multi_turn_target=MULTI_TURN_TARGET,
        target_examples=TARGET_EXAMPLES,
        supervised_token_minimum=TOKEN_MINIMUM,
        supervised_token_maximum=TOKEN_MAXIMUM,
        classify=lambda row: (row.task_family, row.length_band, row.turn_kind),
        token_count=lambda row: row.assistant_token_count,
        rank=lambda row: _rank(row.raw),
    )
    if isinstance(result, AllocationFailure):
        return result
    return AllocationResult(
        tuple(row.raw for row in result.selected),
        result.supervised_token_total,
    )


def _pool_with_reserve(
    available: list[dict[str, object]], selected: tuple[dict[str, object], ...]
) -> list[dict[str, object]]:
    selected_ids = {row["completion_id"] for row in selected}
    pool = list(selected)
    for family, quota in COMPOSITION_QUOTAS.items():
        reserve_needed = candidate_target(family) - quota
        reserve = sorted(
            (
                row
                for row in available
                if row["task_family"] == family and row["completion_id"] not in selected_ids
            ),
            key=_rank,
        )[:reserve_needed]
        pool.extend(reserve)
    pool_ids = {row["completion_id"] for row in pool}
    pool.extend(
        sorted(
            (row for row in available if row["completion_id"] not in pool_ids),
            key=_rank,
        )[: 1_250 - len(pool)]
    )
    if len(pool) != 1_250:
        raise RuntimeError(f"candidate-pool reserve shortfall: {len(pool)}/1250")
    pool_ids = {row["completion_id"] for row in pool}
    while sum(_multi(row) for row in pool) < 230:
        added = next(
            (
                row
                for row in sorted(available, key=_rank)
                if _multi(row) and row["completion_id"] not in pool_ids
            ),
            None,
        )
        if added is None:
            raise RuntimeError("multi-turn reserve shortfall")
        removed = next(
            (
                row
                for row in sorted(pool, key=_rank, reverse=True)
                if not _multi(row)
                and row["completion_id"] not in selected_ids
                and row["task_family"] == added["task_family"]
            ),
            None,
        )
        if removed is None:
            removed = next(
                row
                for row in sorted(pool, key=_rank, reverse=True)
                if not _multi(row) and row["completion_id"] not in selected_ids
            )
        pool.remove(removed)
        pool.append(added)
        pool_ids.remove(removed["completion_id"])
        pool_ids.add(added["completion_id"])
    return sorted(pool, key=_rank)


def _counts(rows: list[dict[str, object]]) -> dict[str, object]:
    cells = Counter(_cell(row) for row in rows)
    return {
        "examples": len(rows),
        "families": dict(sorted(Counter(row["task_family"] for row in rows).items())),
        "length_bands": dict(sorted(Counter(_band(row) for row in rows).items())),
        "turns": dict(
            sorted(Counter("multi" if _multi(row) else "single" for row in rows).items())
        ),
        "cells": {"|".join(cell): count for cell, count in sorted(cells.items())},
        "supervised_tokens": sum(_tokens(row) for row in rows),
    }


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    )


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
            for row in rows
        )
    )


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    public, public_lineage, public_report = _public_rows()
    qwen, concerns = _qwen_rows()
    available = public + qwen
    rejected_cross_row: Counter[str] = Counter()
    for _attempt in range(5):
        result = _allocate(available)
        if isinstance(result, AllocationFailure):
            raise RuntimeError(f"replay allocation infeasible: {result}")
        selected = tuple(result.selected)
        pool = _pool_with_reserve(available, selected)
        report = filter_replay_candidates(pool, _empty_manifest())
        if len(report.accepted) == len(pool):
            break
        rejected_ids = {
            outcome.candidate_id
            for outcome in report.outcomes
            if outcome.rejection_reasons and outcome.candidate_id
        }
        rejected_cross_row.update(
            reason
            for outcome in report.outcomes
            for reason in outcome.rejection_reasons
        )
        available = [row for row in available if row["completion_id"] not in rejected_ids]
    else:
        raise RuntimeError("cross-row filtering did not converge")

    selected_ids = {row["completion_id"] for row in selected}
    lineage: list[dict[str, object]] = []
    for row in pool:
        if row["dataset_source_id"] == NO_ROBOTS_SOURCE_ID:
            lineage.append(public_lineage[str(row["prompt_id"])])
        else:
            lineage.append(
                {
                    "prompt_id": row["prompt_id"],
                    "source_prompt_id": row["prompt_id"],
                    "source_dataset": row["dataset_source_id"],
                    "source_revision": row["dataset_source_revision"],
                    "source_license": (
                        "Apache-2.0"
                        if row["dataset_source_id"] == "OpenAssistant/oasst2"
                        else "CC-BY-SA-3.0"
                    ),
                    "answer_author": row["provenance"]["model_revision"],  # type: ignore[index]
                    "system_prompt_preserved": row["messages"][0]["role"] == "system",  # type: ignore[index]
                }
            )
    audit = sorted(
        pool,
        key=lambda row: (row["task_family"], _band(row), not _multi(row), _rank(row)),
    )
    audit_sample: list[dict[str, object]] = []
    seen: Counter[tuple[str, str, str]] = Counter()
    for row in audit:
        cell = _cell(row)
        if seen[cell] < 2:
            audit_sample.append(row)
            seen[cell] += 1

    _write_jsonl(OUTPUT / "candidate-pool.jsonl", pool)
    _write_jsonl(OUTPUT / "source-lineage.jsonl", lineage)
    _write_jsonl(OUTPUT / "raw-audit-sample.jsonl", audit_sample)
    _write_json(
        OUTPUT / "feasibility-witness.json",
        {
            "content_status": "mechanically_eligible_not_final_content_approval",
            "deferred_to_wp2_9": [
                "project overlap and heldout scans",
                "100-row stratified content review",
                "binding final selection and freeze",
            ],
            "pool": _counts(pool),
            "public_source_report": public_report,
            "qwen_pilot_concerns_in_pool": sorted(
                row["prompt_id"]
                for row in pool
                if row["prompt_id"] in concerns
            ),
            "selected": _counts(list(selected)),
            "selected_completion_ids": sorted(selected_ids),
            "cross_row_rejections_before_clean_pool": dict(sorted(rejected_cross_row.items())),
        },
    )
    files = sorted(
        path
        for path in OUTPUT.iterdir()
        if path.is_file() and path.name != "SHA256SUMS"
    )
    (OUTPUT / "SHA256SUMS").write_text(
        "".join(f"{sha256(path.read_bytes()).hexdigest()}  {path.name}\n" for path in files)
    )
    print(json.dumps({"pool": _counts(pool), "selected": _counts(list(selected))}, indent=2))


if __name__ == "__main__":
    main()
