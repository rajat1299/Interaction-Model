from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace

import pytest

import im.training.phase3_run_freeze as freeze

ROOT = Path(__file__).resolve().parents[1]


def test_derived_wp3_4_freeze_is_deterministic_and_fail_closed() -> None:
    source = "0" * 40
    first = freeze.derive_phase3_run_freeze(repository_root=ROOT, source_commit=source)
    second = freeze.derive_phase3_run_freeze(repository_root=ROOT, source_commit=source)
    assert first == second
    assert set(first) == {
        "SHA256SUMS",
        "automatic-retention-12.json",
        "derived-run-manifest.json",
    }
    expected_sums = "".join(
        f"{sha256(first[name]).hexdigest()}  {name}\n"
        for name in sorted(name for name in first if name != "SHA256SUMS")
    ).encode()
    assert first["SHA256SUMS"] == expected_sums

    retention = json.loads(first["automatic-retention-12.json"])
    manifest = json.loads(first["derived-run-manifest.json"])
    assert manifest["format_version"] == "phase3-derived-run-freeze-v2"
    assert manifest["bindings"]["materialized_datums"]["sha256"] == (
        "sha256:0d5cf2040ee686a6ba606f8c4f51c01c3eb1722233820b7b52db7285c70ea406"
    )
    assert manifest["bindings"]["wp3_1_sha256sums"]["sha256"] == (
        "sha256:3cbdcf46f0b80675ca60b1d6fe89341a09c62d55500f27bc53b9cd706f8ceaea"
    )
    cadence_amendment = manifest["derived_amendments"]["automatic_retention_epoch_boundary_v1"]
    assert cadence_amendment["owner_approved_for_offline_preparation"] is True
    assert cadence_amendment["candidate_self_approval"] is False
    assert cadence_amendment["requires_final_candidate_owner_approval"] is True
    assert retention["row_count"] == 12
    assert retention["total_input_token_count"] == 2248
    assert {row["baseline"]["finish_reason"] for row in retention["rows"]} == {"stop"}
    assert (
        sorted(
            sum(
                (
                    [row["selection_role"]]
                    for row in retention["rows"]
                    if row["capability_group"] == group
                ),
                [],
            )
            for group in {row["capability_group"] for row in retention["rows"]}
        )
        == [["deterministic_or_format_sensitive", "longer_completed"]] * 6
    )
    assert retention["training_effect"]["optimizer_abort"] is False
    assert retention["training_effect"]["d13_score_input"] is False
    assert retention["coverage_gap"]["status"] == "unavailable_in_approved_retention_roster"

    two = manifest["evaluation_and_checkpoint_schedule"]["two_epoch"]
    three = manifest["evaluation_and_checkpoint_schedule"]["three_epoch_if_D12_authorized"]
    assert two["counts"] == {
        "automatic_retention_12": 8,
        "fast_dev_only": 6,
        "full_dev": 8,
        "full_states": 8,
        "sampler_exports": 14,
    }
    assert three["counts"] == {
        "automatic_retention_12": 12,
        "fast_dev_only": 9,
        "full_dev": 12,
        "full_states": 12,
        "sampler_exports": 21,
    }
    assert two["epoch_boundaries"] == [63, 126]
    assert three["epoch_boundaries"] == [63, 126, 189]
    lifecycle = manifest["evaluation_and_checkpoint_schedule"]
    assert lifecycle["boundary_sampler_retained_after_evaluation"] is False
    assert lifecycle["fast_only_checkpoint_selection_eligible"] is False
    assert (
        lifecycle["all_training_sampler_lifecycle"]["explicit_delete_after_scheduled_evaluation"]
        is True
    )
    assert lifecycle["all_training_sampler_lifecycle"]["fast_only_sampler_retained"] is False
    assert (
        lifecycle["post_trajectory_retention_sampler_lifecycle"][
            "explicit_delete_after_blind_retention_evaluation"
        ]
        is True
    )
    assert lifecycle["post_trajectory_retention_sampler_lifecycle"]["short_ttl_required"] is True

    budget = manifest["budget"]
    assert abs(budget["two_epoch"]["modeled_total_usd"] - 114.8272655346) < 1e-12
    assert (
        abs(budget["three_epoch_if_D12_authorized"]["modeled_total_usd"] - 171.4927875876) < 1e-12
    )
    assert budget["two_epoch"]["owner_ceiling_usd"] == 130.0
    assert budget["three_epoch_if_D12_authorized"]["owner_ceiling_usd"] == 190.0
    assert budget["recovery_320_usd_preauthorized"] is False
    assert budget["two_epoch"]["checkpoint_count_upper_bound"] == {
        "full_states": 8,
        "post_trajectory_retention_sampler_exports": 2,
        "selected_durable_sampler_export": 1,
        "total_sampler_exports": 17,
        "training_sampler_exports": 14,
    }

    auth = manifest["authorization"]
    assert not any(auth[key] for key in auth if key != "offline_preparation")
    assert manifest["paid_execution_gate"]["balance_check_authorized_by_this_candidate"] is False
    assert manifest["recovery"]["financially_preauthorized"] is False
    assert manifest["sealed_test"] == {
        "path_argument_allowed": False,
        "status": "unread",
    }
    assert manifest["evaluation_execution"]["physical_prompt_deduplication"] == {
        "byte_identical_duplicate_group_count": 13,
        "byte_mismatch_duplicate_group_count": 2,
        "duplicate_group_count": 15,
        "enabled": False,
        "logical_request_count": 300,
        "logical_rows_in_duplicate_groups": 51,
        "reason": (
            "immutable baseline contains two duplicate-prompt groups with differing output bytes"
        ),
        "unique_prompt_count": 264,
    }


def test_materialization_enforces_source_binding_and_no_overwrite(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    source = "a" * 40
    git = {"head": source, "status": ""}

    def fake_git(command: list[str], **_: object) -> SimpleNamespace:
        stdout = git["head"] if command[1] == "rev-parse" else git["status"]
        return SimpleNamespace(stdout=stdout)

    monkeypatch.setattr(freeze.subprocess, "run", fake_git)
    freeze._verify_source_commit(ROOT, source)
    with pytest.raises(freeze.Phase3RunFreezeError, match="full lowercase"):
        freeze._verify_source_commit(ROOT, "bad")
    git["head"] = "b" * 40
    with pytest.raises(freeze.Phase3RunFreezeError, match="does not match"):
        freeze._verify_source_commit(ROOT, source)
    git["head"] = source
    git["status"] = " M source.py\n"
    with pytest.raises(freeze.Phase3RunFreezeError, match="must be clean"):
        freeze._verify_source_commit(ROOT, source)

    git["status"] = ""
    output = tmp_path / "candidate"
    freeze.materialize_phase3_run_freeze(output, repository_root=ROOT, source_commit=source)
    assert (output / "SHA256SUMS").is_file()
    with pytest.raises(freeze.Phase3RunFreezeError, match="already exists"):
        freeze.materialize_phase3_run_freeze(output, repository_root=ROOT, source_commit=source)

    failed_output = tmp_path / "failed-candidate"

    def fail_replace(_: Path, __: Path) -> None:
        raise OSError("injected publication failure")

    monkeypatch.setattr(freeze.os, "replace", fail_replace)
    with pytest.raises(OSError, match="injected publication failure"):
        freeze.materialize_phase3_run_freeze(
            failed_output, repository_root=ROOT, source_commit=source
        )
    assert not failed_output.exists()

    bad_inputs = dict(freeze._INPUTS)
    path, _ = bad_inputs["static_v2"]
    bad_inputs["static_v2"] = (path, "0" * 64)
    monkeypatch.setattr(freeze, "_INPUTS", bad_inputs)
    with pytest.raises(freeze.Phase3RunFreezeError, match="static_v2 digest drifted"):
        freeze.derive_phase3_run_freeze(repository_root=ROOT, source_commit=source)
