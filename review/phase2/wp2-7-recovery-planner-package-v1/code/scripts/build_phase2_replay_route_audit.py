#!/usr/bin/env python3
"""Emit the WP2-7 route audit and the 22-row pilot selection. No provider calls.

Everything a reviewer needs to check routing *before* anything bills: every comparison prompt,
every allowlisted missing-information prompt, a deterministic sample from each remaining family,
totals, complete OASST path lineage, the balanced replacement queue, and the multi-turn
feasibility proof.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from hashlib import sha256
from pathlib import Path

LEDGER_DIR = Path("review/phase2/replay-ledger-v41")
SAMPLE_PER_FAMILY = 6
PILOT_PER_FAMILY = 2

#: Families inspected in full rather than sampled: comparison because its route is the most
#: keyword-fragile, missing-information because it is the one family no route may fill.
FULL_INSPECTION = (
    "evidence-grounded comparison/recommendation",
    "refusal/uncertainty/missing-information",
)
#: Families with no multi-turn supply by construction, so the pilot uses single-turn rows there.
SINGLE_TURN_OK = ("context-grounded QA", "refusal/uncertainty/missing-information")


def _rank(prompt: dict, seed: str) -> str:
    return sha256(f"{seed}:{prompt['prompt_id']}".encode()).hexdigest()


def _excerpt(prompt: dict, limit: int = 240) -> str:
    turns = []
    contexts = prompt["assistant_context_turns"]
    for index, turn in enumerate(prompt["user_turns"]):
        text = " ".join(turn.split())
        turns.append(f"U{index + 1}: {text if len(text) <= limit else text[:limit] + '…'}")
        if index < len(contexts):
            context = " ".join(contexts[index].split())
            turns.append(
                f"A{index + 1} (source context): "
                f"{context if len(context) <= limit else context[:limit] + '…'}"
            )
    return "\n\n   > ".join(turns)


def select_pilot(prompts: list[dict], seed: str) -> list[dict]:
    """Two per family, preferring a multi-turn row wherever that family has one."""
    by_family: dict[str, list[dict]] = {}
    for prompt in prompts:
        by_family.setdefault(prompt["task_family"], []).append(prompt)
    pilot: list[dict] = []
    for family, rows in sorted(by_family.items()):
        ordered = sorted(rows, key=lambda row: _rank(row, seed))
        multi = [row for row in ordered if row["is_multi_turn"]]
        single = [row for row in ordered if not row["is_multi_turn"]]
        chosen = ([] if family in SINGLE_TURN_OK else multi[:1]) + single
        chosen = (chosen + ordered)[:PILOT_PER_FAMILY]
        seen: set[str] = set()
        deduped = [r for r in chosen if not (r["prompt_id"] in seen or seen.add(r["prompt_id"]))]
        pilot.extend(deduped[:PILOT_PER_FAMILY])
    return pilot


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, default=LEDGER_DIR)
    args = parser.parse_args()

    ledger = json.loads((args.ledger / "prompt-ledger.json").read_bytes())
    report = json.loads((args.ledger / "capacity-report.json").read_bytes())
    queue = json.loads((args.ledger / "replacement-queue.json").read_bytes())
    prompts = ledger["prompts"]
    seed = ledger["selection_seed"]

    by_family: dict[str, list[dict]] = {}
    for prompt in prompts:
        by_family.setdefault(prompt["task_family"], []).append(prompt)

    ledger_digest = sha256((args.ledger / "prompt-ledger.json").read_bytes()).hexdigest()
    lines: list[str] = [
        "# WP2-7 replay route audit",
        "",
        "Pre-generation inspection of prompt routing. **No provider call has occurred.** Every",
        "prompt below is a pinned upstream row; no teacher output or generated completion was used",
        "to route or select it. Multi-turn rows show exact zero-loss source assistant context.",
        "",
        f"- prompt ledger `sha256:{ledger_digest}`",
        f"- selection seed `{seed}`",
        f"- selected **{len(prompts)}** across **{len(by_family)}** families",
        f"- shortfalls: {report['shortfalls'] or 'none'}",
        "",
        "## Totals by family, source, and turn count",
        "",
        "| family | n | multi | dolly | oasst |",
        "|---|---:|---:|---:|---:|",
    ]
    for family in sorted(by_family):
        rows = by_family[family]
        src = Counter(row["dataset_source_id"].split("/")[-1] for row in rows)
        multi = sum(1 for row in rows if row["is_multi_turn"])
        lines.append(
            f"| {family} | {len(rows)} | {multi} | "
            f"{src.get('databricks-dolly-15k', 0)} | {src.get('oasst2', 0)} |"
        )
    total_multi = sum(1 for row in prompts if row["is_multi_turn"])
    lines += [
        f"| **total** | **{len(prompts)}** | **{total_multi}** | "
        f"**{sum(1 for r in prompts if 'dolly' in r['dataset_source_id'])}** | "
        f"**{sum(1 for r in prompts if 'oasst' in r['dataset_source_id'])}** |",
        "",
        "## Final-quota feasibility (binding)",
        "",
        "Measured on the selected ledger against each family's **final 1,000-row quota**. Raw",
        "inventory and sampler-cap figures are diagnostics only and appear below.",
        "",
        "```json",
        json.dumps(report["final_quota_feasibility"], indent=1, sort_keys=True),
        "```",
        "",
        "## Diagnostics: raw inventory and sampler cap",
        "",
        "```json",
        json.dumps(report["multi_turn_diagnostics"], indent=1, sort_keys=True),
        "```",
        "",
        "## Routing dispositions",
        "",
        "Accepted plus every rejection reason, so a stricter router cannot silently eliminate",
        "useful supply without it showing here.",
        "",
        "```json",
        json.dumps(report["routing_dispositions"]["by_reason"], indent=1, sort_keys=True),
        "```",
        "",
        "## Missing-information allowlist",
        "",
        "```json",
        json.dumps(report["refusal_allowlist"], indent=1, sort_keys=True),
        "```",
        "",
        "## Replacement queue (balanced)",
        "",
        f"Total routed reserve **{queue['total_routed_inventory_reserve']:,}**; packaged "
        f"**{len(queue['prompts'])}** rows at {queue['packaged_per_family']} per family, in the "
        "deterministic promotion order recorded in `replacement-queue.json`.",
        "",
        "| family | packaged |",
        "|---|---:|",
    ]
    for family, ids in sorted(queue["promotion_order_by_family"].items()):
        lines.append(f"| {family} | {len(ids)} |")

    for family in sorted(by_family):
        rows = by_family[family]
        full = family in FULL_INSPECTION
        shown = (
            sorted(rows, key=lambda row: _rank(row, seed))
            if full
            else sorted(rows, key=lambda row: _rank(row, seed))[:SAMPLE_PER_FAMILY]
        )
        heading = "all" if full else f"deterministic sample of {len(shown)}"
        lines += ["", f"## {family} — {heading} of {len(rows)}", ""]
        for index, row in enumerate(shown, start=1):
            turns = len(row["user_turns"])
            ids = ", ".join(f"`{i}`" for i in row["source_message_ids"])
            lines += [
                f"{index}. **{row['dataset_source_id'].split('/')[-1]}** · "
                f"{turns} user turn{'s' if turns > 1 else ''} · "
                f"{len(row['source_message_ids'])} path id"
                f"{'s' if len(row['source_message_ids']) > 1 else ''}",
                "",
                f"   > {_excerpt(row)}",
                "",
                f"   path: {ids}",
                "",
            ]

    pilot = select_pilot(prompts, seed)
    pilot_calls = sum(row["generation_calls_required"] for row in pilot)
    lines += [
        "",
        "## Retained 22-row pilot",
        "",
        f"Two per family, multi-turn preferred where the family has it; "
        f"{', '.join(SINGLE_TURN_OK)} use single-turn rows by construction.",
        "",
        "| family | prompt_id | turns | calls |",
        "|---|---|---:|---:|",
    ]
    for row in pilot:
        lines.append(
            f"| {row['task_family']} | `{row['prompt_id'][:16]}` | "
            f"{len(row['user_turns'])} | {row['generation_calls_required']} |"
        )
    lines += [
        f"| **total** | **{len(pilot)} rows** | | **{pilot_calls}** |",
        "",
        "## Call ceilings, recomputed from this ledger",
        "",
        f"- pilot: **{len(pilot)} rows / {pilot_calls} calls**",
        f"- full run: **{len(prompts)} rows / {report['generation_calls_required']} calls**",
        "- every row costs one call: only the final supervised answer is generated",
        "",
        "## Deferred",
        "",
        "Overlap scans against the interaction response corpus, dev, test, and demo, the nonce and",
        "heldout-asset-name lint, the 100-example stratified review, and the freeze are",
        "**NOT RUN**",
        "— they belong to WP2-9. WP2-7 creates no WP2-9 review sample.",
        "",
    ]

    audit = "\n".join(lines)
    (args.ledger / "route-audit.md").write_text(audit)
    (args.ledger / "pilot-selection.json").write_bytes(
        json.dumps(
            {
                "format_version": 1,
                "kind": "phase2-replay-pilot-selection",
                "pilot_calls": pilot_calls,
                "prompts": pilot,
                "selection_seed": seed,
            },
            indent=1,
            sort_keys=True,
        ).encode()
        + b"\n"
    )
    names = sorted(p.name for p in args.ledger.iterdir() if p.is_file() and p.name != "SHA256SUMS")
    (args.ledger / "SHA256SUMS").write_bytes(
        "".join(
            f"{sha256((args.ledger / name).read_bytes()).hexdigest()}  {name}\n" for name in names
        ).encode()
    )
    print(f"route audit: {len(audit.splitlines())} lines")
    print(f"pilot: {len(pilot)} rows / {pilot_calls} calls")
    print(f"full run: {len(prompts)} rows / {report['generation_calls_required']} calls")


if __name__ == "__main__":
    main()
