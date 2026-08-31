from __future__ import annotations

import gzip
import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_phase3x_semantic_intent.py"
SPEC = importlib.util.spec_from_file_location("phase3x_semantic_intent", SCRIPT)
assert SPEC and SPEC.loader
builder = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = builder
SPEC.loader.exec_module(builder)


@pytest.fixture(scope="module")
def semantic_candidate() -> tuple[list[dict[str, object]], dict[str, object]]:
    return builder._semantic_records(ROOT)


@pytest.fixture(scope="module")
def dev_candidate() -> tuple[list[dict[str, object]], dict[str, object], list[str]]:
    return builder._dev_derivation_records(ROOT)


def test_all_approved_actions_have_one_resolving_semantic_target(
    semantic_candidate: tuple[list[dict[str, object]], dict[str, object]],
) -> None:
    rows, _authority = semantic_candidate

    assert len(rows) == 2_000
    assert len({row["datum_id"] for row in rows}) == 2_000
    assert Counter(row["action_type"] for row in rows) == Counter(
        {
            "idle": 1_000,
            "mark": 222,
            "delegate": 131,
            "integrate": 112,
            "skip": 102,
            "respond": 90,
            "schedule": 100,
            "cancel": 61,
            "nudge": 182,
        }
    )
    assert all(row["lineage"]["intent_sha256"].startswith("sha256:") for row in rows)


def test_response_kind_authority_is_exact_disjoint_90_row_partition(
    semantic_candidate: tuple[list[dict[str, object]], dict[str, object]],
) -> None:
    _rows, authority = semantic_candidate

    assert authority["kind"] == "response-kind-projection-v1"
    assert authority["counts"] == {
        "ordinary_grounded_answer": 50,
        "clarification": 15,
        "unsupported_feature_limitation": 13,
        "failed_result_notice": 12,
    }
    assert authority["overlap_count"] == authority["unmatched_count"] == 0
    assert len(authority["rows"]) == 90
    assert all(len(row["predicate_matches"]) <= 1 for row in authority["rows"])
    assert len(authority["limitation_texts"]) == 10
    assert len(authority["failed_result_notice_texts"]) == 11
    assert len(authority["train_failed_result_notice_texts"]) == 9
    assert (
        sum(row["response_kind"] == "unsupported_feature_limitation" for row in authority["rows"])
        == 13
    )


def test_dev_derivation_closes_all_300_rows_and_required_alias_slices(
    dev_candidate: tuple[list[dict[str, object]], dict[str, object], list[str]],
) -> None:
    rows, proof, fast_ids = dev_candidate

    assert len(rows) == proof["derivation_count"] == 300
    assert len(fast_ids) == 11
    assert {key: len(value) for key, value in proof["slices"].items()} == {
        "checkpoint_open_result_idle_awaiting_opening": 2,
        "handled_fire_idle_already_handled": 9,
        "rollover_pending_fact_idle_awaiting_tool": 8,
    }
    assert proof["response_kind_projection"]["counts"] == {
        "clarification": 2,
        "failed_result_notice": 2,
        "ordinary_grounded_answer": 10,
    }


def test_original_interaction_batch_order_is_preserved_without_replay(
    semantic_candidate: tuple[list[dict[str, object]], dict[str, object]],
) -> None:
    rows, _authority = semantic_candidate
    plan = builder._batch_plan(ROOT, {str(row["datum_id"]) for row in rows})

    assert plan["original_interaction_order_preserved"] is True
    assert plan["no_replay"] is True
    assert len(plan["steps"]) == 63
    assert [len(step["interaction_datum_ids"]) for step in plan["steps"]] == [32] * 62 + [16]


def test_prompt_contains_no_current_gold_target(
    semantic_candidate: tuple[list[dict[str, object]], dict[str, object]],
) -> None:
    rows, _authority = semantic_candidate
    row = next(item for item in rows if item["action_type"] == "mark")
    prompt = builder._user_prompt(row)

    assert "<policy-intent-v1-registry>" in prompt
    assert builder.canonicalize_tim_json(row["intent"]).decode("utf-8") not in prompt
    assert "Return exactly one compact" in (ROOT / builder.PROMPT).read_text()


def test_frozen_source_manifests_and_training_contract_close(
    semantic_candidate: tuple[list[dict[str, object]], dict[str, object]],
) -> None:
    rows, _authority = semantic_candidate
    bindings = builder._source_bindings(ROOT)
    eval_inventory = {
        "request_count_across_schedule": 911,
        "weighted_input_token_count": 1_000_000,
    }
    sampling_artifacts = {
        "fast_policy_sanity": {"path": "fast", "sha256": "sha256:fast"},
        "full_dev": {"path": "full", "sha256": "sha256:full"},
    }
    contracts = builder._contracts(
        [
            {
                "input_token_count": 10,
                "prefix_token_count": 8,
                "supervised_token_count": 2,
            }
            for _row in rows
        ],
        eval_inventory,
        sampling_artifacts,
    )

    assert bindings == {
        "original_materialization_sha256sums_sha256": builder.ORIGINAL_MATERIALIZATION_MANIFEST,
        "offline_dev_sha256sums_sha256": builder.OFFLINE_DEV_MANIFEST,
        "phase3x_audit_sha256sums_sha256": builder.PHASE3X_AUDIT_MANIFEST,
        "phase3x_closeout_sha256sums_sha256": builder.PHASE3X_CLOSEOUT_MANIFEST,
    }
    training = contracts["training"]
    assert training["backbone"] == "Qwen/Qwen3.6-35B-A3B"
    assert training["epochs"] == 1
    assert training["optimizer_steps"] == 63
    assert training["lora"] == {
        "rank": 16,
        "train_attention": True,
        "train_mlp": True,
        "train_unembed": False,
    }
    rates = training["schedule"]["learning_rates"]
    assert len(rates) == 63
    assert rates[0]["learning_rate"] == pytest.approx(0.00001)
    assert rates[9]["learning_rate"] == pytest.approx(0.0001)
    assert rates[-1]["learning_rate"] == pytest.approx(0.0)
    assert contracts["eval"]["raw_unconstrained_tinker_only"] is True
    assert contracts["eval"]["sampling_artifacts"] == sampling_artifacts
    assert contracts["eval"]["deferred_serving_gate"]["constrained_intent_validity"] == "100%"
    assert contracts["cost"]["hard_ceiling_usd"] == 55
    assert contracts["cost"]["modeled_total_usd"] <= 55
    assert contracts["cost"]["authorization"] is False


def test_build_is_create_only(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    output = tmp_path / "candidate"
    monkeypatch.setattr(builder, "_verify_clean_source", lambda *_args: None)
    monkeypatch.setattr(builder, "_candidate_files", lambda *_args: {"artifact": b"frozen"})

    builder.build(output, tokenizer_directory=tmp_path, source_commit="0" * 40)
    assert (output / "artifact").read_bytes() == b"frozen"
    with pytest.raises(FileExistsError, match="refusing to replace"):
        builder.build(output, tokenizer_directory=tmp_path, source_commit="0" * 40)


def test_full_candidate_serializes_terminal_masks_and_false_authorization(
    monkeypatch: pytest.MonkeyPatch,
    semantic_candidate: tuple[list[dict[str, object]], dict[str, object]],
    tmp_path: Path,
) -> None:
    rows, authority = semantic_candidate

    class Tokens:
        def __init__(self, values: list[int]) -> None:
            self.values = values

        def to_ints(self) -> list[int]:
            return self.values

    class Tokenizer:
        def encode(self, text: str, *, add_special_tokens: bool) -> list[int]:
            assert add_special_tokens is False
            return list(text.encode("utf-8"))

        def decode(self, values: tuple[int, ...], *, skip_special_tokens: bool) -> str:
            assert skip_special_tokens is False
            return bytes(values).decode("utf-8")

    class Renderer:
        def build_generation_prompt(self, _messages: object) -> Tokens:
            return Tokens([1, 2])

    pinned = SimpleNamespace(tokenizer=Tokenizer(), renderer=Renderer())
    monkeypatch.setattr(builder, "_semantic_records", lambda _root: (rows, authority))
    monkeypatch.setattr(builder.phase3_data, "load_pinned_tokenizer", lambda *_args: pinned)

    files = builder._candidate_files(ROOT, tmp_path, "0" * 40)
    datums = [
        json.loads(line)
        for line in gzip.decompress(files["materialized-datums.jsonl.gz"]).splitlines()
    ]
    manifest = json.loads(files["gate-1-manifest.json"])

    assert len(datums) == 2_000
    assert all(row["target_tokens"][-1] == 248046 for row in datums)
    assert all(row["weights"][-1] == 1.0 for row in datums)
    assert manifest["candidate_checksum_bound"] is True
    assert manifest["authorization"]["checksum_bound_authorization"] is False
    assert manifest["authorization"]["launch"] is False
    assert "dev-derivation-proof.json" in files
    assert "eval-request-inventory.json" in files
    assert "fast-policy-sanity-eval-requests.jsonl.gz" in files
    assert "full-dev-eval-requests.jsonl.gz" in files
    cost = json.loads(files["cost-model.json"])
    assert cost["modeled_total_usd"] <= 55

    for name in (
        "fast-policy-sanity-eval-requests.jsonl.gz",
        "full-dev-eval-requests.jsonl.gz",
    ):
        for raw in gzip.decompress(files[name]).splitlines():
            row = json.loads(raw)
            assert set(row) == {
                "input_token_count",
                "input_token_ids_sha256",
                "input_tokens",
                "state_id",
            }
    inventory = json.loads(files["eval-request-inventory.json"])
    fast_rows = [
        json.loads(line)
        for line in gzip.decompress(
            files["fast-policy-sanity-eval-requests.jsonl.gz"]
        ).splitlines()
    ]
    assert [row["state_id"] for row in fast_rows] == inventory["schedule"][0]["state_ids"]
    assert all("intent" not in row and "expected_action" not in row for row in fast_rows)
