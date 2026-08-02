from __future__ import annotations

import json
import shutil
from hashlib import sha256
from pathlib import Path

from im.assets.model import Split, TimerForm
from im.assets.validate import load_split_seal_json
from im.generation.phase2_dev_timer_gap import (
    build_dev_timer_gap_approval,
    build_dev_timer_gap_artifacts,
    dev_timer_gap_candidates,
)

_ROOT = Path(__file__).parents[1]
_GATE_B = _ROOT / "review" / "phase2" / "dev-gate-b"


def test_dev_timer_gap_packet_is_two_clean_review_only_records() -> None:
    candidates = dev_timer_gap_candidates()
    assert [asset.payload.form for asset in candidates] == [
        TimerForm.UNSUPPORTED,
        TimerForm.NEGATED,
    ]
    assert all(asset.split is Split.DEV for asset in candidates)

    arguments = {
        "registry_path": _GATE_B / "registry.jsonl",
        "dev_seal_path": _GATE_B / "dev-seal.json",
        "heldout_roots": (),
    }
    first = build_dev_timer_gap_artifacts(**arguments)
    assert first == build_dev_timer_gap_artifacts(**arguments)
    packet = json.loads(first["review-packet.json"])
    assert packet["candidate_count"] == 2
    assert packet["battery"] == {
        "candidate_errors": [],
        "candidate_review_flags": [],
    }
    assert packet["status"] == "pending_owner_review"


def test_owner_approval_adds_only_two_dev_seal_entries(tmp_path) -> None:
    source = _ROOT / "review" / "phase1" / "approved"
    approved = tmp_path / "approved"
    shutil.copytree(source, approved)
    shutil.copyfile(_GATE_B / "registry.jsonl", approved / "registry.jsonl")
    shutil.copyfile(_GATE_B / "dev-seal.json", approved / "dev-seal.json")
    artifacts = build_dev_timer_gap_approval(approved_root=approved)
    seal = load_split_seal_json(artifacts["dev-seal.json"])
    assert len(seal.entries) == 56
    assert {asset.asset_id for asset in dev_timer_gap_candidates()} <= {
        entry.asset_id for entry in seal.entries
    }
    manifest = {
        line.split("  ", 1)[1]: line.split("  ", 1)[0]
        for line in artifacts["SHA256SUMS"].decode().splitlines()
    }
    assert manifest["registry.jsonl"] == sha256(artifacts["registry.jsonl"]).hexdigest()
