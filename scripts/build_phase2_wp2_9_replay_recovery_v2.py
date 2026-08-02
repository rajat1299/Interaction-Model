#!/usr/bin/env python3
"""Publish owner-approved multi-turn OASST2 recovery rows."""

from __future__ import annotations

import argparse
import gzip
import json
from collections.abc import Iterable, Mapping
from hashlib import sha256
from pathlib import Path

from im.assets.model import canonical_artifact_bytes
from im.generation.phase2_replay_filtering import filter_replay_candidates
from im.generation.phase2_replay_public import prepare_oasst2_original_rows
from im.generation.phase2_replay_runner import qwen_token_counter
from im.generation.publication import publish_directory_transaction

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "review/phase2/wp2-9-replay-recovery-v2"
SOURCE = (
    ROOT
    / ".cache/replay-sources/179dd21fc55192153d94adb0e0ce8f69e222bf75"
    / "2023-11-05_oasst2_ready.messages.jsonl.gz"
)
TOKENIZER = (
    ROOT / ".cache/replay-sources/995ad96eacd98c81ed38be0c5b274b04031597b0" / "tokenizer.json"
)
PRIMARY_POOL = ROOT / "review/phase2/replay-public-fallback-v1/candidate-pool.jsonl"
SOURCE_SHA256 = "a9f240c4c77aa1378364f70d37e753c07ba284e247b019d700e1947a0e5da751"
TOKENIZER_SHA256 = "5f9e4d4901a92b997e463c1f46055088b6cca5ca61a6522d1b9f64c4bb81cb42"
REVIEW_PACKET_SHA256 = "17819cb379bc7f2cc120450268f4fca895d06b37444117b6af0725a75856840e"
FAMILY = "evidence-grounded comparison/recommendation"
APPROVED_ASSISTANT_IDS = (
    "05cb7292-fd1d-4888-90af-36fea4d1f8bc",
    "132f4cbd-5681-4b21-ac86-85fe5c8f7f7e",
)
V3_APPROVED_ASSISTANT_IDS = ("30c03b9d-aee0-460d-9599-fb7af3b86427",)
V4_APPROVED_ASSISTANT_IDS = (
    "03a16435-bd67-4fde-a2c4-3c1541974fab",
    "1c615d53-70f5-438d-a5cd-07d029ba9728",
    "f61f459e-7837-4f47-841f-e83c5cf0af9e",
)
V5_APPROVED_ASSISTANT_IDS = ("f2746cac-88b5-4398-b5ef-920c17243e11",)
V6_APPROVED_ASSISTANT_IDS = (
    "45bcf340-c4ca-4c0b-a8a8-084788e4d877",
    "ef6d2060-437e-4e1a-ae2c-efcb0b614364",
)
V7_APPROVED_ASSISTANT_IDS = (
    "46d40943-e7e2-448d-886a-6ef3d8203124",
    "fc3f2876-3665-491e-b37d-3d397aee30fb",
)
V8_APPROVED_ASSISTANT_IDS = (
    "17a88d71-82d4-4aab-b00d-9a78ad032079",
    "3e1fe571-da75-4665-8d0f-1d2ed23387d1",
    "5d615762-4e8b-49ae-b93e-8dfb90833e10",
    "72a30794-19a2-4954-bf75-d049c1cf58e1",
    "8091568c-03aa-4f4c-ab4a-dc15460892be",
)


def _digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _source_records(message_ids: set[str]) -> dict[str, dict[str, object]]:
    records: dict[str, dict[str, object]] = {}
    pending = set(message_ids)
    while pending:
        found: dict[str, dict[str, object]] = {}
        with gzip.open(SOURCE, "rt") as stream:
            for line in stream:
                row = json.loads(line)
                message_id = row.get("message_id")
                if message_id in pending:
                    found[str(message_id)] = row
        if missing := pending - found.keys():
            raise RuntimeError(f"OASST2 recovery messages are missing: {sorted(missing)}")
        records.update(found)
        pending = {
            str(row["parent_id"])
            for row in found.values()
            if row.get("parent_id") is not None and row["parent_id"] not in records
        }
    return records


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


def _jsonl(rows: Iterable[Mapping[str, object]]) -> bytes:
    return b"".join(canonical_artifact_bytes(row) + b"\n" for row in rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    version = parser.add_mutually_exclusive_group()
    version.add_argument("--v3", action="store_true")
    version.add_argument("--v4", action="store_true")
    version.add_argument("--v5", action="store_true")
    version.add_argument("--v6", action="store_true")
    version.add_argument("--v7", action="store_true")
    version.add_argument("--v8", action="store_true")
    args = parser.parse_args()
    output = (
        ROOT / "review/phase2/wp2-9-replay-recovery-v8"
        if args.v8
        else ROOT / "review/phase2/wp2-9-replay-recovery-v7"
        if args.v7
        else ROOT / "review/phase2/wp2-9-replay-recovery-v6"
        if args.v6
        else ROOT / "review/phase2/wp2-9-replay-recovery-v5"
        if args.v5
        else ROOT / "review/phase2/wp2-9-replay-recovery-v4"
        if args.v4
        else ROOT / "review/phase2/wp2-9-replay-recovery-v3"
        if args.v3
        else OUTPUT
    )
    approved_ids = (
        V8_APPROVED_ASSISTANT_IDS
        if args.v8
        else V7_APPROVED_ASSISTANT_IDS
        if args.v7
        else V6_APPROVED_ASSISTANT_IDS
        if args.v6
        else V5_APPROVED_ASSISTANT_IDS
        if args.v5
        else V4_APPROVED_ASSISTANT_IDS
        if args.v4
        else V3_APPROVED_ASSISTANT_IDS
        if args.v3
        else APPROVED_ASSISTANT_IDS
    )
    if _digest(SOURCE) != SOURCE_SHA256 or _digest(TOKENIZER) != TOKENIZER_SHA256:
        raise RuntimeError("a pinned OASST2 recovery input drifted")
    records = _source_records(set(approved_ids))
    prepared = prepare_oasst2_original_rows(
        records,
        approved_ids,
        count_tokens=qwen_token_counter(TOKENIZER),
        task_family=(
            "math/data reasoning" if args.v8 else "light creative/casual" if args.v7 else FAMILY
        ),
    )
    token_min, token_max = (51, 150) if args.v5 or args.v6 or args.v7 else (151, 350)
    expected_user_turns = 1 if args.v6 else 2
    if any(
        not token_min <= int(row["assistant_token_count"]["count"]) <= token_max  # type: ignore[index]
        or sum(message["role"] == "user" for message in row["messages"])  # type: ignore[arg-type]
        != expected_user_turns
        for row in prepared.candidates
    ):
        raise RuntimeError("an approved recovery row left its frozen cell")
    primary = next(
        row
        for row in (json.loads(line) for line in PRIMARY_POOL.read_text().splitlines())
        if row["dataset_source_role"] == "primary"
    )
    report = filter_replay_candidates((primary, *prepared.candidates), _empty_manifest())
    recovery_ids = {str(row["completion_id"]) for row in prepared.candidates}
    failures = {
        outcome.candidate_id: outcome.rejection_reasons
        for outcome in report.outcomes
        if outcome.candidate_id in recovery_ids and not outcome.accepted
    }
    if failures:
        raise RuntimeError(f"recovery candidates failed the closed filter: {failures}")

    dispositions = [
        {
            "assistant_message_id": assistant_id,
            "assistant_text_sha256": (
                f"sha256:{sha256(str(records[assistant_id]['text']).encode()).hexdigest()}"
            ),
            "decision": "approved",
        }
        for assistant_id in approved_ids
    ]
    files = {
        "candidate-pool.jsonl": _jsonl(prepared.candidates),
        "owner-disposition.json": canonical_artifact_bytes(
            {
                "authority": "Project-owner decisions given in conversation; transcription only.",
                "format_version": 1,
                "kind": "phase2-wp2-9-oasst2-multiturn-recovery-owner-disposition",
                "review_packet_sha256": f"sha256:{REVIEW_PACKET_SHA256}",
                "reviewed": dispositions,
                "reviewed_on": "2026-07-30",
                "reviewer_id": "user:phase2-owner",
            }
        ),
        "source-inputs.json": canonical_artifact_bytes(
            {
                "dataset": "OpenAssistant/oasst2",
                "format_version": 1,
                "kind": "phase2-wp2-9-oasst2-multiturn-recovery-inputs",
                "license": "Apache-2.0",
                "revision": "179dd21fc55192153d94adb0e0ce8f69e222bf75",
                "source_file_sha256": f"sha256:{SOURCE_SHA256}",
                "tokenizer_sha256": f"sha256:{TOKENIZER_SHA256}",
            }
        ),
        "source-lineage.jsonl": _jsonl(prepared.lineage),
    }
    files["SHA256SUMS"] = "".join(
        f"{sha256(data).hexdigest()}  {name}\n" for name, data in sorted(files.items())
    ).encode()
    publish_directory_transaction(output, files)
    print(f"published {len(prepared.candidates)} candidates to {output}")


if __name__ == "__main__":
    main()
