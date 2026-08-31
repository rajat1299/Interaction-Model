from __future__ import annotations

import gzip
import importlib.util
import json
import sys
from collections import Counter
from fractions import Fraction
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_phase3r_terminal_ablation.py"
SPEC = importlib.util.spec_from_file_location("phase3r_terminal_ablation", SCRIPT)
assert SPEC and SPEC.loader
builder = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = builder
SPEC.loader.exec_module(builder)


@pytest.fixture(scope="module")
def candidate(tmp_path_factory: pytest.TempPathFactory) -> Path:
    output = tmp_path_factory.mktemp("phase3r-terminal-ablation") / "candidate"
    files, _ = builder._candidate_files(ROOT, "0" * 40)
    builder.publish_directory_transaction(output, files)
    return output


def _json(path: Path) -> dict[str, object]:
    return json.loads(path.read_bytes())


def _fraction(value: str) -> Fraction:
    numerator, denominator = value.split("/")
    return Fraction(int(numerator), int(denominator))


def test_deterministic_gzip_jsonl() -> None:
    rows = [{"datum_id": "a", "tokens": [1, 2]}, {"datum_id": "b", "tokens": [3]}]
    first = builder._gzip_jsonl_bytes(rows)
    assert first == builder._gzip_jsonl_bytes(rows)
    assert [json.loads(line) for line in gzip.decompress(first).splitlines()] == rows


def test_sampling_input_uses_a_gzip_json_array(tmp_path: Path) -> None:
    path = tmp_path / "requests.json.gz"
    with gzip.open(path, "wb") as stream:
        stream.write(b'[{"request_id":"one"},{"request_id":"two"}]')
    assert builder._read_json_gzip(path) == [{"request_id": "one"}, {"request_id": "two"}]


def test_public_build_verifies_source_before_materializing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    checked: list[tuple[Path, str]] = []
    monkeypatch.setattr(
        builder,
        "_verify_tracked_source",
        lambda root, commit: checked.append((root, commit)),
    )
    monkeypatch.setattr(builder, "_candidate_files", lambda root, commit: ({}, {}))
    monkeypatch.setattr(builder, "publish_directory_transaction", lambda output, files: None)
    commit = "0" * 40
    builder.build(tmp_path / "candidate", source_commit=commit)
    assert checked == [(ROOT, commit)]


def test_owner_decision_rejects_a_different_static_contract(tmp_path: Path) -> None:
    owner = _json(ROOT / builder.OWNER_DECISION)
    static = tmp_path / "static.json"
    static.write_text("{}\n")
    with pytest.raises(ValueError, match="does not bind this Phase 3 static contract"):
        builder._verify_owner_bindings(
            owner,
            ROOT / builder.MATERIALIZATION / "materialized-datums.jsonl.gz",
            ROOT / builder.MATERIALIZATION / "batch-plan.json",
            static,
        )


def test_all_3000_terminal_masks_are_complete_and_untruncated(candidate: Path) -> None:
    summary = _json(candidate / "datum-mask-proof.json")
    assert summary["total_datum_count"] == 3_000
    assert summary["truncated_datum_count"] == 0
    assert summary["rows"]["interaction"] == {
        "datum_count": 2_000,
        "positive_terminal_count": 2_000,
        "prefix_unchanged_count": 2_000,
        "terminal_weight": 1.0,
        "terminal_weight_float32_bits": "0x3f800000",
        "untruncated_count": 2_000,
    }
    replay = summary["rows"]["replay"]
    assert replay["datum_count"] == replay["positive_terminal_count"] == 1_000
    assert replay["prefix_unchanged_count"] == replay["untruncated_count"] == 1_000
    assert replay["terminal_weight_float32_bits"] == "0x3e99999a"

    with gzip.open(candidate / "terminal-mask-proof.jsonl.gz", "rb") as stream:
        proof = [json.loads(line) for line in stream]
    assert Counter(row["kind"] for row in proof) == {"interaction": 2_000, "replay": 1_000}
    assert all(
        row["positive_terminal_count"] == 1
        and row["prefix_unchanged"] is True
        and row["truncated"] is False
        and row["terminal_token_id"] == 248046
        and row["tokens_after_terminal"] == 0
        for row in proof
    )
    with gzip.open(candidate / "amended-datums.jsonl.gz", "rb") as stream:
        assert sum(1 for _ in stream) == 3_000


def test_successor_preserves_all_memberships_and_recomputes_mass(candidate: Path) -> None:
    source = _json(ROOT / "review/phase3/wp3-1-materialization-candidate-v5/batch-plan.json")
    successor = _json(candidate / "successor-batch-plan.json")
    assert len(source["steps"]) == len(successor["steps"]) == 63
    replay_coefficient = Fraction(5_033_165, 16_777_216)
    for index, (before, after) in enumerate(
        zip(source["steps"], successor["steps"], strict=True), start=1
    ):
        assert after["interaction_datum_ids"] == before["interaction_datum_ids"]
        assert after["replay_datum_ids"] == before["replay_datum_ids"]
        assert after["membership_sha256"] == before["membership_sha256"]
        interaction_count, replay_count = (32, 16) if index < 63 else (16, 8)
        assert _fraction(after["positive_mass"]) == _fraction(before["positive_mass"]) + (
            interaction_count + replay_count * replay_coefficient
        )
    assert len(successor["steps"][-1]["interaction_datum_ids"]) == 16
    assert len(successor["steps"][-1]["replay_datum_ids"]) == 8


def test_first_ten_identity_and_learning_rates(candidate: Path) -> None:
    manifest = _json(candidate / "first-ten-manifest.json")
    assert manifest["first_ten_datum_count"] == 480
    assert manifest["training_sequence_tokens"] == {"amended": 4_978_216, "source": 4_977_736}
    assert manifest["preserved"]["backbone_initialization"] == "untouched_backbone"
    assert manifest["preserved"]["lora"] == {
        "lora_rank": 64,
        "train_attn": True,
        "train_mlp": True,
        "train_unembed": False,
    }
    assert manifest["preserved"]["scheduler_horizon_steps"] == 189
    assert manifest["preserved"]["learning_rate_steps_1_10"] == [
        0.00003,
        0.00006,
        0.00009,
        0.00012,
        0.00015,
        0.00018,
        0.00021,
        0.00024,
        0.00027,
        0.00030,
    ]


def test_cost_model_uses_exact_token_and_storage_arithmetic(candidate: Path) -> None:
    cost = _json(candidate / "cost-model.json")
    assert cost["token_counts"] == {
        "evaluation_prefill": 164_640,
        "evaluation_requests": 23,
        "evaluation_sample_max": 23_552,
        "training": 4_978_216,
    }
    assert cost["components_usd"] == {
        "ephemeral_sampler_full_month": pytest.approx(0.4406986362),
        "evaluation_max_sample_output": pytest.approx(0.03144192),
        "evaluation_uncached_prefill": pytest.approx(0.0889056),
        "full_state_full_month": pytest.approx(1.3220105589),
        "training": pytest.approx(5.859360232),
    }
    assert cost["modeled_total_usd"] == pytest.approx(7.7424169471)
    assert cost["owner_ceiling_usd"] == 9


def test_authorization_is_false_and_test_remains_closed(candidate: Path) -> None:
    report = _json(candidate / "terminal-ablation-report.json")
    evaluation = _json(candidate / "step-10-evaluation-contract.json")
    assert all(value is False for value in report["authorization"].values())
    assert report["sealed_test"] == {"status": "unread"}
    assert all(value is False for value in evaluation["authorization"].values())
    assert evaluation["request_count"] == 23
    assert evaluation["fast_11"]["baseline_step_10"]["integer_counts"] == {
        "active_floor_respond_error_count": 1,
        "duplicate_delegate_or_schedule_error_count": 0,
        "executed_full_payload_match_count": 4,
        "forbidden_error_count": 4,
        "parse_union_valid_count": 10,
    }
