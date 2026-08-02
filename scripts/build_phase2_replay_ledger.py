#!/usr/bin/env python3
"""Materialize the frozen WP2-7 replay prompt ledger and capacity report. No provider calls.

Pins both dataset revisions and the Qwen tokenizer artifact, reconstructs oasst2 conversation
threads from the flat message table, routes and samples under one global seed, and writes the
ledger plus a deterministic replacement queue. Nothing here contacts a model.
"""

from __future__ import annotations

import argparse
import gzip
import json
from collections import Counter
from hashlib import sha256
from pathlib import Path

import httpx

from im.assets.model import canonical_artifact_bytes
from im.generation.phase2_replay_filtering import source_context_rejection_reasons
from im.generation.phase2_replay_runner import qwen_token_counter
from im.generation.phase2_replay_sources import (
    GLOBAL_SELECTION_SEED,
    capacity_report,
    prepare_dolly_prompts,
    prepare_oasst_prompts,
    sample_pool,
)

DOLLY_REPO = "databricks/databricks-dolly-15k"
DOLLY_REVISION = "bdd27f4d94b9c1f951818a7da7fd7aeea5dbff1a"
OASST_REPO = "OpenAssistant/oasst2"
OASST_REVISION = "179dd21fc55192153d94adb0e0ce8f69e222bf75"
TOKENIZER_REPO = "Qwen/Qwen3.6-35B-A3B"
TOKENIZER_COMMIT = "995ad96eacd98c81ed38be0c5b274b04031597b0"
TOKENIZER_FILE_SHA256 = "5f9e4d4901a92b997e463c1f46055088b6cca5ca61a6522d1b9f64c4bb81cb42"

#: Exact pinned files. Downloaded with httpx plus stdlib gzip/json rather than a dataset stack:
#: two pinned files do not justify pandas and pyarrow in the lockfile.
DOLLY_FILE = "databricks-dolly-15k.jsonl"
OASST_FILE = "2023-11-05_oasst2_ready.messages.jsonl.gz"

DEFAULT_OUTPUT = Path("review/phase2/replay-ledger-v43")
#: Historical ledgers stay immutable. The v3 amendment starts from v18's verified allowlist,
#: removes eight answerable tasks, and adds five strict missing-input roots.
BASE_REFUSAL_ALLOWLIST = (
    Path("review/phase2/replay-ledger-v18-superseded-prepilot-audit")
    / "refusal-allowlist.json"
)
REFUSAL_AMENDMENT_DIR = Path("review/phase2/replay-refusal-allowlist-v3")
REFUSAL_AMENDMENT = REFUSAL_AMENDMENT_DIR / "refusal-allowlist-amendment.json"
DEFAULT_CACHE = Path(".cache/replay-sources")


def _resolve_url(kind: str, repo: str, revision: str, filename: str) -> str:
    prefix = "datasets/" if kind == "dataset" else ""
    return f"https://huggingface.co/{prefix}{repo}/resolve/{revision}/{filename}"


def fetch_pinned(
    kind: str, repo: str, revision: str, filename: str, cache: Path
) -> tuple[bytes, dict[str, object]]:
    """Download one revision-pinned file, recording URL, byte hash, and size."""
    url = _resolve_url(kind, repo, revision, filename)
    target = cache / revision / filename
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        with httpx.stream("GET", url, follow_redirects=True, timeout=600) as response:
            response.raise_for_status()
            with target.open("wb") as sink:
                for chunk in response.iter_bytes():
                    sink.write(chunk)
    payload = target.read_bytes()
    return payload, {
        "byte_sha256": sha256(payload).hexdigest(),
        "bytes": len(payload),
        "filename": filename,
        "repo": repo,
        "revision": revision,
        "url": url,
    }


def _read_jsonl(payload: bytes, filename: str) -> list[dict[str, object]]:
    raw = gzip.decompress(payload) if filename.endswith(".gz") else payload
    return [json.loads(line) for line in raw.splitlines() if line.strip()]


#: oasst2 is volunteer-authored, so rows are filtered on the dataset's own moderation fields before
#: any routing. We only ever take the prompts, but a deleted or unreviewed turn is not a prompt we
#: want to condition the backbone on.
_MAX_TURNS = 6


def oasst_threads(rows) -> list[list[dict[str, object]]]:
    """Rebuild prompter-terminated conversation paths from the flat message table."""
    by_id: dict[str, dict[str, object]] = {}
    children: dict[str, list[str]] = {}
    for row in rows:
        if row["deleted"] or row["lang"] != "en" or row.get("synthetic"):
            continue
        if row.get("review_result") is False:
            continue
        by_id[row["message_id"]] = row
        parent = row.get("parent_id")
        if parent:
            children.setdefault(parent, []).append(row["message_id"])

    threads: list[list[dict[str, object]]] = []
    for message_id, row in by_id.items():
        if row["role"] != "prompter":
            continue
        # EVERY prompter turn is a candidate, not only childless leaves. Requiring a leaf discards
        # every root prompt -- in oasst2 almost all of them have an assistant reply -- which left
        # the oasst-only buckets (coding, math, translation, comparison) 100% multi-turn and the
        # pool 114 single-turn rows short. The source answer is retained only when it lies between
        # two selected user turns; it is zero-loss context for the follow-up, never a target.
        path: list[dict[str, object]] = []
        cursor: str | None = message_id
        while cursor and cursor in by_id and len(path) <= _MAX_TURNS * 2:
            path.append(by_id[cursor])
            cursor = by_id[cursor].get("parent_id")  # type: ignore[assignment]
        path.reverse()
        if sum(1 for item in path if item["role"] == "prompter") <= _MAX_TURNS:
            threads.append(path)
    return threads


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--limit-oasst", type=int, default=0, help="0 = all")
    parser.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    parser.add_argument(
        "--reserve-per-family",
        type=int,
        default=40,
        help="Number of deterministic reserve rows to package per populated family.",
    )
    args = parser.parse_args()

    dolly_bytes, dolly_source = fetch_pinned(
        "dataset", DOLLY_REPO, DOLLY_REVISION, DOLLY_FILE, args.cache
    )
    oasst_bytes, oasst_source = fetch_pinned(
        "dataset", OASST_REPO, OASST_REVISION, OASST_FILE, args.cache
    )
    _tokenizer_bytes, tokenizer_source = fetch_pinned(
        "model", TOKENIZER_REPO, TOKENIZER_COMMIT, "tokenizer.json", args.cache
    )
    if tokenizer_source["byte_sha256"] != TOKENIZER_FILE_SHA256:
        raise SystemExit("pinned tokenizer byte hash mismatch")
    dolly = _read_jsonl(dolly_bytes, DOLLY_FILE)
    oasst = _read_jsonl(oasst_bytes, OASST_FILE)
    rows = oasst[: args.limit_oasst] if args.limit_oasst else oasst

    dispositions: Counter = Counter()
    dolly_prompts = prepare_dolly_prompts(
        ({**row, "message_id": f"dolly:{index}"} for index, row in enumerate(dolly)),
        revision=DOLLY_REVISION,
        dispositions=dispositions,
    )
    base_allowlist = json.loads(BASE_REFUSAL_ALLOWLIST.read_bytes())
    amendment = json.loads(REFUSAL_AMENDMENT.read_bytes())
    if amendment["base_allowlist"] != str(BASE_REFUSAL_ALLOWLIST):
        raise SystemExit("refusal allowlist amendment names the wrong base")
    review = REFUSAL_AMENDMENT_DIR / amendment["review_artifact"]
    if sha256(review.read_bytes()).hexdigest() != amendment["review_artifact_sha256"]:
        raise SystemExit("refusal allowlist amendment review digest mismatch")
    removed = set(amendment["removed_message_ids"])
    base_ids = {entry["message_id"] for entry in base_allowlist["entries"]}
    if not removed <= base_ids:
        raise SystemExit("refusal allowlist amendment removes an unknown id")
    entries = [
        entry for entry in base_allowlist["entries"] if entry["message_id"] not in removed
    ] + amendment["added"]
    if len(entries) != amendment["result_count"] or len(
        {entry["message_id"] for entry in entries}
    ) != len(entries):
        raise SystemExit("refusal allowlist amendment count or uniqueness mismatch")
    allowlist = {
        **base_allowlist,
        "count": len(entries),
        "entries": entries,
        "note": (
            "Base raw-source allowlist plus the checksum-bound v3 amendment. This remains the "
            "only sanctioned way to fill the missing-information family."
        ),
    }
    by_id = {row["message_id"]: row for row in rows}
    verified: set[str] = set()
    for entry in allowlist["entries"]:
        source = by_id.get(entry["message_id"])
        if source is None:
            raise SystemExit(f"allowlist id absent from pinned source: {entry['message_id']}")
        if sha256(source["text"].encode()).hexdigest() != entry["text_sha256"]:
            raise SystemExit(f"allowlist text hash mismatch: {entry['message_id']}")
        if (
            source["role"] != "prompter"
            or source["lang"] != "en"
            or source["deleted"]
            or source.get("synthetic")
            or source.get("review_result") is False
            or source.get("parent_id") is not None
        ):
            raise SystemExit(f"allowlist row fails source invariants: {entry['message_id']}")
        verified.add(entry["message_id"])
    if len(verified) != allowlist["count"]:
        raise SystemExit("allowlist verification count mismatch")

    threads = oasst_threads(rows)
    oasst_prompts = prepare_oasst_prompts(
        threads,
        revision=OASST_REVISION,
        refusal_allowlist=frozenset(verified),
        dispositions=dispositions,
    )
    count_tokens = qwen_token_counter(args.cache / TOKENIZER_COMMIT / "tokenizer.json")
    context_rejections: Counter[str] = Counter()
    eligible_oasst = []
    for prompt in oasst_prompts:
        reasons = {
            reason
            for text in prompt.assistant_context_turns
            for reason in source_context_rejection_reasons(text, count_tokens)
        }
        if reasons:
            context_rejections.update(reasons)
        else:
            eligible_oasst.append(prompt)
    pool = sample_pool(dolly_prompts + tuple(eligible_oasst))

    report = {
        **capacity_report(pool),
        "replacement_queue": {
            "packaged_by_family": {
                family: min(len(rows), args.reserve_per_family)
                for family, rows in sorted(
                    {
                        f: [p for p in pool.reserve if p.task_family == f]
                        for f in {p.task_family for p in pool.reserve}
                    }.items()
                )
            },
            "total_routed_inventory_reserve": len(pool.reserve),
        },
        "inventory": {
            "dolly_rows": len(dolly),
            "dolly_routed": len(dolly_prompts),
            "oasst_messages": len(rows),
            "oasst_routed": len(oasst_prompts),
            "oasst_source_context_eligible": len(eligible_oasst),
            "source_context_rejections": dict(sorted(context_rejections.items())),
            "oasst_threads": len(threads),
        },
        "routing_dispositions": {
            "by_reason": {
                reason: sum(count for (*_k, r), count in dispositions.items() if r == reason)
                for reason in sorted({r for *_k, r in dispositions})
            },
            "by_source_category_family_reason": {
                " | ".join(key): value for key, value in sorted(dispositions.items())
            },
            "note": (
                "Accepted plus every rejection reason, by source and original category. Publishes "
                "whether the stricter router silently eliminates useful supply."
            ),
        },
        "refusal_allowlist": {
            "count": allowlist["count"],
            "amendment": str(REFUSAL_AMENDMENT),
            "amendment_sha256": sha256(REFUSAL_AMENDMENT.read_bytes()).hexdigest(),
            "base": str(BASE_REFUSAL_ALLOWLIST),
            "review_artifact_path": str(review),
            "review_artifact_sha256": amendment["review_artifact_sha256"],
            "verified_against_pinned_source": len(verified),
        },
        "sources": {
            "dolly": dolly_source,
            "oasst": oasst_source,
            "tokenizer": {**tokenizer_source, "commit": TOKENIZER_COMMIT},
        },
    }

    def serialize(prompt) -> dict[str, object]:
        return {
            "dataset_source_id": prompt.dataset_source_id,
            "dataset_source_revision": prompt.dataset_source_revision,
            "dataset_source_role": prompt.dataset_source_role,
            "generation_calls_required": prompt.generation_calls_required,
            "is_multi_turn": prompt.is_multi_turn,
            "prompt_id": prompt.prompt_id,
            "source_category": prompt.source_category,
            "source_message_ids": list(prompt.source_message_ids),
            "assistant_context_turns": list(prompt.assistant_context_turns),
            "assistant_context_token_counts": [
                count_tokens(text) for text in prompt.assistant_context_turns
            ],
            "task_family": prompt.task_family,
            "user_turns": list(prompt.user_turns),
        }

    ledger = {
        "format_version": 1,
        "frozen_before_generation": True,
        "kind": "phase2-replay-prompt-ledger",
        "prompts": [serialize(prompt) for prompt in pool.prompts],
        "selection_seed": GLOBAL_SELECTION_SEED,
        "sources": report["sources"],
    }
    # A flat head-slice of the reserve is family-biased: the reserve is concatenated per family, so
    # the first 2,000 rows covered only two families and could not replace a rejected coding, math,
    # or translation prompt. Package a small balanced queue instead, in deterministic per-family
    # promotion order.
    per_family = args.reserve_per_family
    if per_family < 1:
        raise SystemExit("--reserve-per-family must be positive")
    by_family: dict[str, list] = {}
    for prompt in pool.reserve:
        by_family.setdefault(prompt.task_family, []).append(prompt)
    packaged = {family: rows[:per_family] for family, rows in sorted(by_family.items())}
    queue = {
        "format_version": 1,
        "kind": "phase2-replay-replacement-queue",
        "note": (
            "Deterministic per-family promotion order under the same global seed. A row is "
            "promoted only to replace one rejected by a downstream filter, never to change a "
            "result. Promotion consumes a family's list in the order given here."
        ),
        "packaged_per_family": per_family,
        "promotion_order_by_family": {
            family: [prompt.prompt_id for prompt in rows] for family, rows in packaged.items()
        },
        "prompts": [serialize(prompt) for rows in packaged.values() for prompt in rows],
        "selection_seed": GLOBAL_SELECTION_SEED,
        "total_routed_inventory_reserve": len(pool.reserve),
    }

    files = {
        "prompt-ledger.json": canonical_artifact_bytes(ledger),
        "replacement-queue.json": canonical_artifact_bytes(queue),
        "capacity-report.json": canonical_artifact_bytes(report),
        "refusal-allowlist.json": canonical_artifact_bytes(allowlist),
    }
    files["SHA256SUMS"] = "".join(
        f"{sha256(data).hexdigest()}  {name}\n" for name, data in sorted(files.items())
    ).encode()
    args.output.mkdir(parents=True, exist_ok=True)
    for name, data in files.items():
        (args.output / name).write_bytes(data)

    print(json.dumps(report, indent=1, sort_keys=True))
    print(f"\nledger sha256: {sha256(files['prompt-ledger.json']).hexdigest()}")
    print(f"written to {args.output}")


if __name__ == "__main__":
    main()
