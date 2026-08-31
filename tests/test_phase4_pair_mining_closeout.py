from __future__ import annotations

import gzip
import importlib.util
import io
import json
import zipfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "phase4_pair_mining_closeout", ROOT / "scripts/build_phase4_pair_mining_closeout.py"
)
assert SPEC is not None and SPEC.loader is not None
closeout = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(closeout)


def test_incomplete_closeout_preserves_partial_evidence_without_authorizing_dpo(
    monkeypatch,
) -> None:
    monkeypatch.setattr(closeout, "_verify_source", lambda _root, _commit: {"test": "bound"})
    files = closeout.closeout_files(closeout.ROOT, "0" * 40)

    assert set(files) == {
        "SHA256SUMS",
        "concept-surface-outcomes.jsonl.gz",
        "outcome-breakdown.json",
        "post-run-analysis.json",
        "provisional-eligible-outcomes.jsonl.gz",
        "structural-gap-analysis.json",
        "wp4-0r-owner-decision.json",
    }
    provisional = [
        json.loads(line)
        for line in gzip.decompress(files["provisional-eligible-outcomes.jsonl.gz"]).splitlines()
    ]
    assert len(provisional) == len({row["request_id"] for row in provisional}) == 204
    assert Counter(row["category"] for row in provisional) == Counter(
        {
            "stale_integrate_vs_skip": 50,
            "duplicate_delegate_vs_idle": 35,
            "semantic_duplicate_schedule_vs_idle": 35,
            "active_floor_respond_vs_idle": 0,
            "canceled_fire_nudge_vs_skip": 2,
            "ambiguous_cancel_vs_clarification": 30,
            "mark_vs_restraint": 45,
            "pure_no_trigger_restraint": 0,
            "mirrored_positive_controls": 7,
        }
    )
    assert all(
        row["status"] == "provisional_evidence_only"
        and not row["pair_approved"]
        and not row["reuse_authorized"]
        and not row["dpo_materialized"]
        for row in provisional
    )
    analysis = json.loads(files["post-run-analysis.json"])
    assert analysis["result"] == "completed_incomplete_quota"
    assert analysis["pair_count"] == 0
    assert analysis["quota_deficit"] == 116
    assert not analysis["runner_or_adjudicator_failure"]
    recovery = json.loads(files["wp4-0r-owner-decision.json"])
    assert recovery["missing_concepts_total"] == 116
    assert recovery["sentinel_recommendation"]["calls"] == 12
    assert recovery["modeled_cost_bound"]["full_recovery"]["maximum_requests"] == 464
    assert recovery["modeled_cost_bound"]["full_recovery"]["modeled_worst_case_usd"] < 16
    assert not recovery["authorization"]
    assert not recovery["launchable"]
    assert not recovery["dpo_materialization"]
    exported = files["structural-gap-analysis.json"] + files["wp4-0r-owner-decision.json"]
    assert b"dev:" not in exported

    records, _analysis = closeout._run_records(closeout.ROOT)
    examples = closeout._representative_examples(records)
    assert len(examples) == 11
    assert all(example["raw_branch"]["origin"] == "selected_step63_sample" for example in examples)
    archive = closeout._zip_bytes("lean", {"example.json": b"{}"})
    with zipfile.ZipFile(io.BytesIO(archive)) as zipped:
        assert zipped.namelist() == ["lean/example.json"]
        assert zipped.read("lean/example.json") == b"{}"
