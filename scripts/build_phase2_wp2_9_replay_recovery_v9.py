#!/usr/bin/env python3
"""Build and prove the final OASST2 multi-turn replay recovery review slice."""

from __future__ import annotations

import argparse
import gzip
import json
from hashlib import sha256
from pathlib import Path

from im.assets.model import artifact_digest, canonical_artifact_bytes
from im.generation.phase2_replay import plan_replay_review_round
from im.generation.phase2_replay_filtering import (
    BACKBONE_REVISION,
    PROJECT_AUTHORED_RECOVERY_REVISION,
    filter_replay_candidates,
)
from im.generation.phase2_replay_public import prepare_oasst2_original_rows
from im.generation.phase2_replay_runner import qwen_token_counter
from im.generation.publication import publish_directory_transaction

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (
    ROOT
    / ".cache/replay-sources/179dd21fc55192153d94adb0e0ce8f69e222bf75"
    / "2023-11-05_oasst2_ready.messages.jsonl.gz"
)
TOKENIZER = (
    ROOT / ".cache/replay-sources/995ad96eacd98c81ed38be0c5b274b04031597b0" / "tokenizer.json"
)
PRIMARY_POOL = ROOT / "review/phase2/replay-public-fallback-v1/candidate-pool.jsonl"
BASE = ROOT / "review/phase2/wp2-9-replay-review"
PROGRESS = ROOT / "review/phase2/wp2-9-replay-owner-review-progress.json"
OUTPUT = ROOT / "review/phase2/wp2-9-replay-recovery-v9-review"
SOURCE_SHA256 = "a9f240c4c77aa1378364f70d37e753c07ba284e247b019d700e1947a0e5da751"
TOKENIZER_SHA256 = "5f9e4d4901a92b997e463c1f46055088b6cca5ca61a6522d1b9f64c4bb81cb42"
SEED = "phase2-replay-public-fallback-v1"

IDS_BY_FAMILY = {
    "stable-knowledge explanation": (
        "0b0c22eb-022d-4d09-8802-a23c724bb603",
        "105eaf49-b618-4eac-b0ea-2d0cacedd944",
        "1229392d-de23-4081-88de-caa9df14f827",
        "12cdb3c8-aecf-4eea-9f5f-88c0b5813ad1",
        "18a76fdf-d9cb-4772-8dae-152274fcf080",
        "201724d8-c9b4-4a15-9a23-fe7847bb2e53",
        "2baaa828-c9a1-4bd6-916f-a011ac07b86d",
        "30243eff-f528-4fe3-a0af-cdb8e0d6fc61",
        "30ef0886-7656-4eb5-9bab-00270751930f",
        "3aa8cf18-48da-46a1-b94d-3daada44c56a",
        "49fa9a1c-0568-408f-95c8-f30bb8f39452",
        "4939f68a-8193-4ea4-92f0-b6723d17da52",
        "4bb7bb9a-f429-4318-aec6-9677daafa6e2",
        "5645f19b-746a-4a5c-901d-d3774561683c",
        "591cc2f4-e1e2-4a61-82fe-50cfe7ca2988",
        "4f554e02-b17a-4aca-a366-134dada3c5b3",
        "504f3b71-4491-4526-8755-188c8c4b8ffa",
        "5a670a29-eb4b-4b04-aa99-a69efb997a23",
        "64f38f06-796d-4e00-a76b-c92466f00f41",
        "70eced09-051b-4f9b-b7aa-19acb6e98039",
        "75cb3367-6cd2-4368-8104-323e12bb3800",
        "797b3655-e4ae-4ec4-ae2d-d7aae4bb13ba",
        "81abc71d-e078-4f11-9675-08903f8b9c2b",
        "85709faf-e910-4732-b3ff-98bde8e5210a",
        "8a43cf12-43cf-4cd4-8e1b-f4db0096f26c",
        "8e45f560-9704-4d64-b5ee-7a27486e3e70",
        "941287db-0ba1-4021-b469-0180062d6ebb",
        "93fb76b5-a5b7-4b89-a163-48485231d726",
        "987b6bda-d0dc-4a72-87ab-bd8d19db7cf6",
        "9c9d41c3-e67d-4dbe-9c91-8ace0a675005",
        "abc1b4e4-6f50-4f21-895e-c9ab4f4321eb",
        "0ac90ba7-387c-41ab-831c-147bec7f73e5",
        "159cbe08-fc24-41b9-afdd-b42ce1b3c71e",
        "19531c4c-1fab-4085-867d-b312e47fdca6",
        "c9317970-760b-4522-a0e2-0bc61938545c",
        "cd03c464-e460-45c8-ac32-f8c3f84d92cb",
        "d230f60a-b7b3-496b-b2b6-f7c7c73238c5",
        "d3147eec-908d-4d44-a16c-490a20be40ee",
        "d5cc9005-8f2b-4d21-9d40-c734b93344e7",
        "de1a086e-9321-4b1d-b83f-e4d8b33082ea",
        "e19ba0fc-1192-471c-9f72-1a90238adf56",
        "dcfc9564-2c7c-4390-b960-6053dd3f86ac",
        "f17d6b5a-1940-4951-8aac-9afe5a67009e",
        "f5022e8d-5ada-4fc4-abb1-6ece6f9d32a3",
        "f7a70d3b-305b-4bc5-a7e6-ece801144078",
    ),
    "translation/language transformation": (
        "04628eb7-fe52-4881-a02c-4349d9579769",
        "5c915bf8-c963-4504-b880-da426ea19aa5",
        "69296321-1b60-49bf-acfb-970e1e05248a",
        "85ab6c59-e562-4cd8-a094-7962bf51acb7",
    ),
    "refusal/uncertainty/missing-information": ("85ed9def-0534-4048-a05d-e47788e7b911",),
}

SYNTHETIC_TRANSLATIONS = (
    (
        ("Translate “Good morning” into Spanish.", "Buenos días."),
        (
            "Now translate “The train arrives at eight” into English: «El tren llega a las ocho».",
            "The train arrives at eight.",
        ),
    ),
    (
        ("How do you say “Thank you very much” in French?", "Merci beaucoup."),
        ("And translate “See you tomorrow” into French.", "À demain."),
    ),
    (
        ("Translate “Where is the library?” into German.", "Wo ist die Bibliothek?"),
        (
            "Now translate “The meeting starts at noon” into German.",
            "Die Besprechung beginnt um zwölf Uhr.",
        ),
    ),
    (
        (
            "Translate “Please close the window” into Italian.",
            "Per favore, chiudi la finestra.",
        ),
        (
            "What does “Il museo è chiuso il lunedì” mean in English?",
            "The museum is closed on Mondays.",
        ),
    ),
    (
        ("How do you say “Hello” in Japanese?", "こんにちは。"),
        ("Now translate “また明日。” into English.", "See you tomorrow."),
    ),
    (
        (
            "Translate “The weather is nice today” into Portuguese.",
            "O tempo está bom hoje.",
        ),
        (
            "What is “A loja abre às nove” in English?",
            "The store opens at nine.",
        ),
    ),
    (
        (
            "Translate “I need an appointment for tomorrow” into German.",
            "Ich brauche einen Termin für morgen.",
        ),
        (
            "Now put “The doctor will call you this afternoon” into German.",
            "Der Arzt wird Sie heute Nachmittag anrufen.",
        ),
    ),
    (
        ("Translate “The book is on the table” into Dutch.", "Het boek ligt op tafel."),
        (
            "What does “De bus vertrekt over tien minuten” mean in English?",
            "The bus leaves in ten minutes.",
        ),
    ),
    (
        (
            "Translate “Where is the nearest station?” into Korean.",
            "가장 가까운 역이 어디예요?",
        ),
        ("Now translate “감사합니다.” into English.", "Thank you."),
    ),
    (
        ("Translate “The café closes at six” into Russian.", "Кафе закрывается в шесть."),
        (
            "What does «Билет стоит пять евро» mean in English?",
            "The ticket costs five euros.",
        ),
    ),
    (
        ("Translate “Good night” into Polish.", "Dobranoc."),
        (
            "Now translate “The office is open today” into Polish.",
            "Biuro jest dziś otwarte.",
        ),
    ),
    (
        (
            "Translate “I would like a cup of coffee” into Swedish.",
            "Jag skulle vilja ha en kopp kaffe.",
        ),
        ("What does “Tåget är försenat” mean in English?", "The train is delayed."),
    ),
    (
        ("How do you say “Welcome” in Arabic?", "مرحبًا."),
        ("Now translate “المطار قريب” into English.", "The airport is nearby."),
    ),
    (
        (
            "Translate “The restaurant is open” into Greek.",
            "Το εστιατόριο είναι ανοιχτό.",
        ),
        (
            "What does “Το νερό είναι κρύο” mean in English?",
            "The water is cold.",
        ),
    ),
    (
        ("Translate “How much is this?” into Turkish.", "Bu ne kadar?"),
        (
            "Now translate “Otobüs saat üçte geliyor” into English.",
            "The bus arrives at three.",
        ),
    ),
    (
        ("Translate “The room is ready” into Norwegian.", "Rommet er klart."),
        (
            "What does “Butikken stenger snart” mean in English?",
            "The store is closing soon.",
        ),
    ),
    (
        ("Translate “The road is closed” into Ukrainian.", "Дорога закрита."),
        (
            "What does “Потяг прибуває о сьомій” mean in English?",
            "The train arrives at seven.",
        ),
    ),
    (
        (
            "Translate “The keys are on the desk” into Finnish.",
            "Avaimet ovat työpöydällä.",
        ),
        ("What does “Kokous alkaa pian” mean in English?", "The meeting starts soon."),
    ),
    (
        ("Translate “I need help” into Czech.", "Potřebuji pomoc."),
        (
            "What does “Lékárna je vedle banky” mean in English?",
            "The pharmacy is next to the bank.",
        ),
    ),
)

SYNTHETIC_UNCERTAINTY = (
    (
        "My laptop sometimes shuts down without warning. What should I check first?",
        (
            "Start by checking whether it is overheating: make sure the vents are clear, "
            "the fans are running, and the shutdowns are not limited to heavy workloads. "
            "Also note whether it happens on battery power, AC power, or both."
        ),
    ),
    (
        "It shut down again. Tell me exactly which component failed.",
        (
            "There is not enough evidence to identify one failed component yet. Record the "
            "temperature and system logs around the next shutdown, test battery and AC power "
            "separately, and note whether the machine loses power instantly or shows an error. "
            "Those observations can distinguish overheating, power, battery, memory, and "
            "software causes without guessing."
        ),
    ),
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


def _source_records(ids: set[str]) -> dict[str, dict[str, object]]:
    with gzip.open(SOURCE, "rt") as stream:
        all_records = {row["message_id"]: row for row in map(json.loads, stream)}
    pending = set(ids)
    while pending:
        missing = pending - all_records.keys()
        if missing:
            raise RuntimeError(f"OASST2 messages are missing: {sorted(missing)}")
        parents = {
            str(all_records[item]["parent_id"])
            for item in pending
            if all_records[item].get("parent_id") is not None
        }
        ids.update(pending)
        pending = parents - ids
    return {item: all_records[item] for item in ids}


def _candidates() -> tuple[dict[str, object], ...]:
    ids = {item for values in IDS_BY_FAMILY.values() for item in values}
    records = _source_records(ids)
    count_tokens = qwen_token_counter(TOKENIZER)
    candidates = tuple(
        candidate
        for family, assistant_ids in IDS_BY_FAMILY.items()
        for candidate in prepare_oasst2_original_rows(
            records,
            assistant_ids,
            count_tokens=count_tokens,
            task_family=family,
        ).candidates
    )
    synthetic_rows = tuple(
        ("translation/language transformation", turns) for turns in SYNTHETIC_TRANSLATIONS
    ) + (("refusal/uncertainty/missing-information", SYNTHETIC_UNCERTAINTY),)
    for index, (family, turns) in enumerate(synthetic_rows, 1):
        messages = [
            {"role": role, "content": content}
            for pair in turns
            for role, content in (("user", pair[0]), ("assistant", pair[1]))
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
        candidates += (
            {
                "completion_id": f"project-replay-recovery-{index:02d}",
                "prompt_id": f"project-replay-recovery-{index:02d}",
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
            },
        )
    if any(sum(message["role"] == "user" for message in row["messages"]) < 2 for row in candidates):
        raise RuntimeError("the recovery slice must remain entirely multi-turn")
    primary = next(row for row in _jsonl(PRIMARY_POOL) if row["dataset_source_role"] == "primary")
    report = filter_replay_candidates((primary, *candidates), _empty_manifest())
    failures = {
        outcome.candidate_id: outcome.rejection_reasons
        for outcome in report.outcomes
        if outcome.candidate_id != primary["completion_id"] and not outcome.accepted
    }
    if failures:
        raise RuntimeError(f"recovery candidates failed the closed filter: {failures}")
    return candidates


def _prove(candidates: tuple[dict[str, object], ...]) -> dict[str, object]:
    progress = json.loads(PROGRESS.read_text())
    rejected = {item["completion_id"] for group in progress["groups"] for item in group["rejected"]}
    baseline = [
        row
        for row in _jsonl(BASE / "normalized-candidate-pool.jsonl")
        if row["completion_id"] not in rejected
    ]
    recovery = [
        row
        for version in range(1, 9)
        for row in _jsonl(
            ROOT / f"review/phase2/wp2-9-replay-recovery-v{version}/candidate-pool.jsonl"
        )
    ]
    references = json.loads((BASE / "reference-manifest.json").read_text())["references"]
    report = filter_replay_candidates((*baseline, *recovery, *candidates), references)
    candidate_ids = {str(row["completion_id"]) for row in candidates}
    failures = {
        outcome.candidate_id: outcome.rejection_reasons
        for outcome in report.outcomes
        if outcome.candidate_id in candidate_ids and not outcome.accepted
    }
    if failures:
        raise RuntimeError(f"recovery candidates conflict with the reviewed pool: {failures}")
    accepted_family_counts: dict[str, int] = {}
    for outcome in report.outcomes:
        if outcome.accepted and outcome.candidate is not None:
            family = outcome.candidate.task_family
            accepted_family_counts[family] = accepted_family_counts.get(family, 0) + 1
    if accepted_family_counts.get("translation/language transformation", 0) < 40:
        displaced = {
            outcome.candidate_id: outcome.rejection_reasons
            for outcome in report.outcomes
            if not outcome.accepted
            and any(
                candidate_id in str(outcome.rejection_reasons) for candidate_id in candidate_ids
            )
        }
        raise RuntimeError(
            "translation recovery displaced existing rows: "
            f"accepted={accepted_family_counts.get('translation/language transformation', 0)}, "
            f"displaced={displaced}"
        )
    plan = plan_replay_review_round(
        (*baseline, *recovery, *candidates),
        references,
        selection_seed=SEED,
        review_rounds=(),
    )
    selected = tuple(plan.provisional_selected)
    return {
        "accepted_candidate_count": len(plan.filter_report.accepted),
        "input_candidate_count": len(baseline) + len(recovery) + len(candidates),
        "selected_count": len(selected),
        "supervised_token_total": sum(item.assistant_token_count for item in selected),
        "multi_turn_count": sum(item.is_multi_turn for item in selected),
        "selected_recovery_ids": sorted(
            item.completion_id
            for item in selected
            if item.completion_id in {str(row["completion_id"]) for row in candidates}
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--publish-review", action="store_true")
    args = parser.parse_args()
    if (
        sha256(SOURCE.read_bytes()).hexdigest() != SOURCE_SHA256
        or sha256(TOKENIZER.read_bytes()).hexdigest() != TOKENIZER_SHA256
    ):
        raise RuntimeError("a pinned recovery input drifted")
    candidates = _candidates()
    proof = _prove(candidates)
    print(json.dumps(proof, indent=2, sort_keys=True))
    if not args.publish_review:
        return
    files = {
        "candidate-pool.jsonl": b"".join(
            canonical_artifact_bytes(row) + b"\n"
            for row in sorted(candidates, key=lambda row: str(row["completion_id"]))
        ),
        "feasibility-probe.json": canonical_artifact_bytes(proof),
        "review-packet.json": canonical_artifact_bytes(
            {
                "candidates": sorted(candidates, key=lambda row: str(row["completion_id"])),
                "format_version": 1,
                "kind": "phase2-wp2-9-replay-recovery-v9-owner-review",
                "scope": (
                    "Owner review is required before any row is admitted. "
                    "Translation has no honest source reserve."
                ),
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
