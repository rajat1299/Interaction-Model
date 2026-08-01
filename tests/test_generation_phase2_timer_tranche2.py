from __future__ import annotations

import json
import socket
from pathlib import Path

import pytest

from im.assets.model import (
    CorpusFamily,
    TemplateAssetPayload,
    TextAssetPayload,
    TimerAssetPayload,
    TimerForm,
)
from im.generation.phase2_timer_tranche2 import (
    build_timer_tranche2_artifacts,
    build_timer_tranche2_repair_artifacts,
    materialize_timer_tranche2_packet,
    timer_tranche2_candidates,
)
from im.generation.timer_instruction_semantics import parse_timer_instruction_v1


def test_timer_tranche2_repairs_only_the_targeted_timer_gaps() -> None:
    candidates = timer_tranche2_candidates()
    timers = tuple(asset for asset in candidates if isinstance(asset.payload, TimerAssetPayload))
    ambiguous = tuple(asset for asset in candidates if isinstance(asset.payload, TextAssetPayload))
    templates = tuple(
        asset for asset in candidates if isinstance(asset.payload, TemplateAssetPayload)
    )

    assert len(candidates) == 13
    assert len({asset.asset_id for asset in candidates}) == 13
    assert sum(CorpusFamily.TIMER_NORMAL in asset.coverage for asset in candidates) == 3
    assert sum(CorpusFamily.TIMER_CONTENTION in asset.coverage for asset in candidates) == 3
    assert (
        sum(
            CorpusFamily.TIMER_CANCEL in asset.coverage
            and not isinstance(asset.payload, TemplateAssetPayload)
            for asset in candidates
        )
        == 5
    )
    assert sum(asset.payload.form is TimerForm.NEGATED for asset in timers) == 2
    assert sum(asset.payload.form is TimerForm.UNSUPPORTED for asset in timers) == 2
    assert len(ambiguous) == 1
    assert len(templates) == 2
    assert {template.payload.expands_kind.value for template in templates} == {"text", "timer"}
    for asset in timers:
        if asset.payload.form is TimerForm.SUPPORTED:
            parsed = parse_timer_instruction_v1(asset.payload.instruction)
            assert (parsed.interval_ms, parsed.message) == (
                asset.payload.interval_ms,
                asset.payload.message,
            )


def test_timer_tranche2_packet_is_deterministic_and_has_a_clean_battery() -> None:
    first = build_timer_tranche2_artifacts()
    second = build_timer_tranche2_artifacts()
    packet = json.loads(first["review-packet.json"])

    assert first == second
    assert packet["status"] == "pending_owner_review"
    assert packet["candidate_count"] == 13
    assert packet["atomic_candidate_count"] == 11
    assert packet["template_candidate_count"] == 2
    assert packet["battery"] == {"candidate_errors": [], "candidate_review_flags": []}
    assert packet["projected_atomic_source_counts"] == {
        "timer_cancel_quoting_stale_fire": 12,
        "timer_contention_backpressure": 10,
        "timer_creation_normal_fire": 10,
    }
    assert packet["coverage_repair"]["timer:atomic_direct_negated"] == 2
    assert packet["coverage_repair"]["timer:atomic_unsupported"] == 2
    templates = [item for item in packet["candidates"] if item["payload"]["kind"] == "template"]
    assert all(item["representative_expansion"] for item in templates)
    review = first["REVIEW.md"].decode()
    assert "interval_ms=" in review
    assert "representative expansion:" in review
    assert set(first) == {
        "REVIEW.md",
        "SHA256SUMS",
        "candidate-assets.jsonl",
        "review-packet.json",
    }


def test_timer_tranche2_rejects_frozen_generated_overlap(tmp_path: Path) -> None:
    heldout = tmp_path / "heldout"
    heldout.mkdir()
    (heldout / "state.jsonl").write_text(
        '{"text":"Cancel the reminder next to it."}\n', encoding="utf-8"
    )

    with pytest.raises(ValueError, match="overlaps frozen material"):
        build_timer_tranche2_artifacts(heldout_roots=(heldout,))


def test_timer_tranche2_rejects_unsupported_instruction_frame_overlap(tmp_path: Path) -> None:
    heldout = tmp_path / "heldout"
    heldout.mkdir()
    (heldout / "state.jsonl").write_text(
        '{"text":"Set a single reminder forty minutes from now to open the cedar box."}\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="repeats a frozen instruction frame"):
        build_timer_tranche2_artifacts(heldout_roots=(heldout,))


def test_timer_tranche2_materialization_is_offline_and_create_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def no_network(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("timer asset review materialization must stay offline")

    monkeypatch.setattr(socket, "create_connection", no_network)
    output = tmp_path / "review"
    materialize_timer_tranche2_packet(output)
    with pytest.raises(FileExistsError, match="already exists"):
        materialize_timer_tranche2_packet(output)


def test_timer_tranche2_scoped_repair_is_clean_and_bound_to_rejected_digest() -> None:
    files = build_timer_tranche2_repair_artifacts()
    packet = json.loads(files["review-packet.json"])
    record = packet["repaired_record"]

    assert packet["status"] == "pending_owner_review"
    assert packet["prior_rejected_content_sha256"] == (
        "sha256:375230a68a66bc68ce0ffb9e5a4b13f8d62d0e8fbc2be2057d25f96f850409d9"
    )
    assert record["asset_id"] == "a_bf812f9b9f149490915e6de0"
    assert record["content_sha256"] != packet["prior_rejected_content_sha256"]
    assert record["payload"]["instruction"] == (
        "Set a single reminder forty minutes from now to close the lilac case."
    )
    assert packet["battery"] == {"candidate_errors": [], "candidate_review_flags": []}
