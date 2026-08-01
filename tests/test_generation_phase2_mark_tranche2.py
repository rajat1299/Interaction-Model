from __future__ import annotations

import json
import socket
from pathlib import Path

import pytest

from im.assets import (
    AssetRegistry,
    Split,
    create_split_seal,
    load_registry_jsonl,
    render_registry_jsonl,
    render_split_seal_json,
)
from im.assets.model import CorpusFamily, TextForm
from im.generation.phase2_mark_tranche2 import (
    build_mark_tranche2_artifacts,
    mark_tranche2_candidates,
    materialize_mark_tranche2_packet,
)


def _premark_inputs(tmp_path: Path) -> tuple[Path, Path]:
    candidates = {asset.asset_id for asset in mark_tranche2_candidates()}
    current = load_registry_jsonl(Path("review/phase1/approved/registry.jsonl").read_bytes())
    registry = AssetRegistry(
        assets=tuple(asset for asset in current.assets if asset.asset_id not in candidates),
        reviews=tuple(review for review in current.reviews if review.asset_id not in candidates),
    )
    registry_path = tmp_path / "registry.jsonl"
    seal_path = tmp_path / "train-seal.json"
    registry_path.write_bytes(render_registry_jsonl(registry))
    seal_path.write_bytes(render_split_seal_json(create_split_seal(registry, Split.TRAIN)))
    return registry_path, seal_path


def test_mark_tranche2_repairs_only_the_targeted_mark_gaps() -> None:
    candidates = mark_tranche2_candidates()

    assert len(candidates) == len({asset.asset_id for asset in candidates}) == 8
    assert sum(CorpusFamily.MARK_POSITIVE in asset.coverage for asset in candidates) == 3
    assert sum(CorpusFamily.MARK_NEGATIVE in asset.coverage for asset in candidates) == 5
    assert {
        asset.payload.form
        for asset in candidates
        if CorpusFamily.MARK_NEGATIVE in asset.coverage
    } == {
        TextForm.DIRECT,
        TextForm.AMBIGUOUS,
        TextForm.QUOTED,
        TextForm.CODE,
        TextForm.PARTIAL,
    }


def test_mark_tranche2_packet_is_deterministic_and_battery_clean(tmp_path) -> None:
    registry, seal = _premark_inputs(tmp_path)
    first = build_mark_tranche2_artifacts(
        registry_path=registry,
        train_seal_path=seal,
    )
    second = build_mark_tranche2_artifacts(
        registry_path=registry,
        train_seal_path=seal,
    )
    packet = json.loads(first["review-packet.json"])

    assert first == second
    assert packet["candidate_count"] == packet["atomic_candidate_count"] == 8
    assert packet["template_candidate_count"] == 0
    assert packet["battery"] == {"candidate_errors": [], "candidate_review_flags": []}
    assert packet["projected_atomic_source_counts"] == {
        "mark_activation_positive": 10,
        "mark_lifecycle_negative": 12,
    }
    assert set(first) == {
        "REVIEW.md",
        "SHA256SUMS",
        "candidate-assets.jsonl",
        "review-packet.json",
    }


def test_mark_tranche2_materialization_is_offline_and_create_only(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def no_network(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("mark asset review materialization must stay offline")

    monkeypatch.setattr(socket, "create_connection", no_network)
    registry, seal = _premark_inputs(tmp_path)
    output = tmp_path / "review"
    materialize_mark_tranche2_packet(
        output,
        registry_path=registry,
        train_seal_path=seal,
    )
    with pytest.raises(FileExistsError, match="already exists"):
        materialize_mark_tranche2_packet(
            output,
            registry_path=registry,
            train_seal_path=seal,
        )
