from __future__ import annotations

import json
from pathlib import Path

import pytest

from im.assets import load_verified_registry_seals
from im.generation.g7_response_assets import GeneratedResponseAsset, ResponseAssetError
from im.generation.g7_response_catalog import G7_RESPONSE_DRAFT_PROFILES
from im.generation.g7_response_pipeline import (
    G7ResponseGeneration,
    _bind_profile,
    load_g7_response_generations,
    materialize_g7_failed_response_assets,
)


def _artifact() -> bytes:
    return json.dumps(
        {
            "format_version": 1,
            "generator": {
                "model": "gpt-5.6-terra",
                "reasoning_effort": "high",
                "input_fields": [
                    "teacher_visible_prefix",
                    "invitation",
                    "answer_contract",
                ],
            },
            "records": [
                {
                    "profile_id": f"profile-{index // 10:02d}",
                    "item_index": index % 10,
                    "request_sha256": f"{index:064x}",
                    "candidate_response": f"Unique response {index}.",
                }
                for index in range(90)
            ],
        }
    ).encode()


def test_generation_artifact_is_closed_sorted_and_exactly_ninety_rows() -> None:
    records = load_g7_response_generations(_artifact())

    assert len(records) == 90
    payload = json.loads(_artifact())
    payload["records"][1]["candidate_response"] = payload["records"][0][
        "candidate_response"
    ]
    with pytest.raises(ResponseAssetError, match="duplicate free"):
        load_g7_response_generations(json.dumps(payload).encode())


def test_profile_binding_requires_the_exact_captured_request_hash() -> None:
    profile = G7_RESPONSE_DRAFT_PROFILES[0]
    prefixes = tuple(f"Visible prefix {index}" for index in range(10))
    generations = []
    for index, (draft, prefix) in enumerate(zip(profile.drafts, prefixes, strict=True)):
        response = "; ".join(
            point.accepted_alternatives[0]
            for point in draft.answer_contract.required_answer_points
        ) + "."
        asset = GeneratedResponseAsset.create(
            draft,
            teacher_visible_prefix=prefix,
            candidate_response=response,
        )
        generations.append(
            G7ResponseGeneration(
                profile.profile_id,
                index,
                asset.serialized_neutral_request_sha256,
                response,
            )
        )

    assert len(_bind_profile(profile, tuple(generations), prefixes).assets) == 10
    bad = generations[0]
    generations[0] = G7ResponseGeneration(
        bad.profile_id,
        bad.item_index,
        "f" * 64,
        bad.candidate_response,
    )
    with pytest.raises(ResponseAssetError, match="request hash"):
        _bind_profile(profile, tuple(generations), prefixes)


@pytest.mark.asyncio
async def test_failed_materialization_requires_each_isolated_generation(
    tmp_path: Path,
) -> None:
    repository = Path(__file__).parents[1]
    approved = repository / "review/phase1/approved"
    registry, _seals = load_verified_registry_seals(
        (approved / "registry.jsonl").read_bytes(),
        tuple(
            (approved / name).read_bytes()
            for name in ("test-seal.json", "demo-seal.json")
        ),
    )

    with pytest.raises(ResponseAssetError, match="missing failed generation"):
        await materialize_g7_failed_response_assets(
            registry,
            generations=(),
            master_seeds={},
            directory=tmp_path,
            repository_root=repository,
        )
