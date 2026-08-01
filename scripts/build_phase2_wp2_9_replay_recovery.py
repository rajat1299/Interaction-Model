#!/usr/bin/env python3
"""Build the owner-approved OASST2-original WP2-9 replay recovery tranche."""

from __future__ import annotations

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
OUTPUT = ROOT / "review/phase2/wp2-9-replay-recovery-v1"
SOURCE = (
    ROOT
    / ".cache/replay-sources/179dd21fc55192153d94adb0e0ce8f69e222bf75"
    / "2023-11-05_oasst2_ready.messages.jsonl.gz"
)
TOKENIZER = (
    ROOT
    / ".cache/replay-sources/995ad96eacd98c81ed38be0c5b274b04031597b0"
    / "tokenizer.json"
)
PRIMARY_POOL = ROOT / "review/phase2/replay-public-fallback-v1/candidate-pool.jsonl"
SOURCE_SHA256 = "a9f240c4c77aa1378364f70d37e753c07ba284e247b019d700e1947a0e5da751"
TOKENIZER_SHA256 = "5f9e4d4901a92b997e463c1f46055088b6cca5ca61a6522d1b9f64c4bb81cb42"
REVIEW_PACKET_SHA256 = "17819cb379bc7f2cc120450268f4fca895d06b37444117b6af0725a75856840e"
FAMILY = "refusal/uncertainty/missing-information"

APPROVED_ASSISTANT_IDS = (
    "07ea741e-e6bb-4215-824a-b0e2e7189780",
    "2ed2236a-4d6c-408d-b811-e34b448bc17e",
    "3445ff20-fd7b-472e-b13a-5284da814b63",
    "3c340a9b-d949-4193-8233-63b7cbfb8a9d",
    "43c7e306-78e5-45a0-a65d-c3adb1dbac52",
    "811bece9-4e5d-4a72-b1b4-d5b9195a6b43",
    "cf4b02aa-fb42-4ea9-8ebe-70712ac127ee",
    "e6357edc-3c2e-4bb1-8b84-50957ae251be",
    "f89894d4-5a63-429d-a6d6-6c16cbe64b6a",
)
REJECTED_ASSISTANT_IDS = {
    "b86d8f78-ed10-4d3d-abd6-889969e40f32": (
        "The answer invents f[0] = an although the prompt supplies no initial condition."
    )
}
MECHANICALLY_EXCLUDED_IDS = {
    "034d2236-e07b-428d-9bc1-edfdab8469c3": (
        "Owner approved the content, but the frozen filter rejects its generic closing boilerplate."
    )
}


def _digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _source_records(message_ids: set[str]) -> dict[str, dict[str, object]]:
    records: dict[str, dict[str, object]] = {}
    with gzip.open(SOURCE, "rt") as stream:
        for line in stream:
            row = json.loads(line)
            if row.get("message_id") in message_ids:
                records[str(row["message_id"])] = row
    missing = message_ids - records.keys()
    if missing:
        raise RuntimeError(f"OASST2 review messages are missing: {sorted(missing)}")
    parent_ids = {str(row["parent_id"]) for row in records.values()}
    with gzip.open(SOURCE, "rt") as stream:
        for line in stream:
            row = json.loads(line)
            if row.get("message_id") in parent_ids:
                records[str(row["message_id"])] = row
    missing = parent_ids - records.keys()
    if missing:
        raise RuntimeError(f"OASST2 parent messages are missing: {sorted(missing)}")
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
    if _digest(SOURCE) != SOURCE_SHA256 or _digest(TOKENIZER) != TOKENIZER_SHA256:
        raise RuntimeError("a pinned OASST2 recovery input drifted")
    reviewed_ids = {
        *APPROVED_ASSISTANT_IDS,
        *REJECTED_ASSISTANT_IDS,
        *MECHANICALLY_EXCLUDED_IDS,
    }
    records = _source_records(reviewed_ids)
    if any(
        records[str(records[item]["parent_id"])].get("parent_id") is not None
        for item in reviewed_ids
    ):
        raise RuntimeError("the recovery tranche must remain single-turn")

    prepared = prepare_oasst2_original_rows(
        records,
        APPROVED_ASSISTANT_IDS,
        count_tokens=qwen_token_counter(TOKENIZER),
        task_family=FAMILY,
    )
    if any(
        not 151 <= int(row["assistant_token_count"]["count"]) <= 350  # type: ignore[index]
        for row in prepared.candidates
    ):
        raise RuntimeError("an approved recovery answer left the long band")
    primary = next(
        row
        for row in (json.loads(line) for line in PRIMARY_POOL.read_text().splitlines())
        if row["dataset_source_role"] == "primary"
    )
    report = filter_replay_candidates((primary, *prepared.candidates), _empty_manifest())
    accepted_ids = {
        outcome.candidate_id for outcome in report.outcomes if outcome.accepted
    }
    recovery_ids = {str(row["completion_id"]) for row in prepared.candidates}
    if not recovery_ids <= accepted_ids:
        failures = {
            outcome.candidate_id: outcome.rejection_reasons
            for outcome in report.outcomes
            if outcome.candidate_id in recovery_ids and not outcome.accepted
        }
        raise RuntimeError(f"recovery candidates failed the closed filter: {failures}")

    reviewed = []
    for assistant_id in sorted(reviewed_ids):
        reply = records[assistant_id]
        prompt = records[str(reply["parent_id"])]
        reviewed.append(
            {
                "assistant_message_id": assistant_id,
                "assistant_text_sha256": (
                    f"sha256:{sha256(str(reply['text']).encode()).hexdigest()}"
                ),
                "decision": (
                    "approved"
                    if assistant_id in APPROVED_ASSISTANT_IDS
                    else (
                        "excluded_mechanical"
                        if assistant_id in MECHANICALLY_EXCLUDED_IDS
                        else "rejected"
                    )
                ),
                "note": (
                    REJECTED_ASSISTANT_IDS.get(assistant_id)
                    or MECHANICALLY_EXCLUDED_IDS.get(assistant_id)
                    or (
                        "Owner accepted the explicitly caveated rough estimate."
                        if assistant_id == "2ed2236a-4d6c-408d-b811-e34b448bc17e"
                        else ""
                    )
                ),
                "prompt_message_id": reply["parent_id"],
                "prompt_text_sha256": f"sha256:{sha256(str(prompt['text']).encode()).hexdigest()}",
            }
        )
    files = {
        "candidate-pool.jsonl": _jsonl(
            sorted(prepared.candidates, key=lambda row: str(row["completion_id"]))
        ),
        "owner-disposition.json": canonical_artifact_bytes(
            {
                "authority": "Project-owner decisions given in conversation; transcription only.",
                "format_version": 1,
                "kind": "phase2-wp2-9-oasst2-recovery-owner-disposition",
                "review_packet_sha256": f"sha256:{REVIEW_PACKET_SHA256}",
                "reviewed": reviewed,
                "reviewed_on": "2026-07-30",
                "reviewer_id": "user:phase2-owner",
            }
        ),
        "source-inputs.json": canonical_artifact_bytes(
            {
                "dataset": "OpenAssistant/oasst2",
                "format_version": 1,
                "kind": "phase2-wp2-9-oasst2-recovery-inputs",
                "license": "Apache-2.0",
                "revision": "179dd21fc55192153d94adb0e0ce8f69e222bf75",
                "source_file_sha256": f"sha256:{SOURCE_SHA256}",
                "tokenizer_sha256": f"sha256:{TOKENIZER_SHA256}",
            }
        ),
        "source-lineage.jsonl": _jsonl(
            sorted(prepared.lineage, key=lambda row: str(row["prompt_id"]))
        ),
    }
    files["SHA256SUMS"] = "".join(
        f"{sha256(data).hexdigest()}  {name}\n" for name, data in sorted(files.items())
    ).encode()
    publish_directory_transaction(OUTPUT, files)
    print(f"published {len(prepared.candidates)} candidates to {OUTPUT}")


if __name__ == "__main__":
    main()
