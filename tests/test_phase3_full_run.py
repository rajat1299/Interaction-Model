from __future__ import annotations

import asyncio
import struct
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
import tinker

from im.assets.model import canonical_artifact_bytes
from im.training import phase3_full_resume, phase3_full_run, phase3_human_review
from im.training.phase3_full_run import (
    BACKBONE,
    LockedRunContract,
    Phase3FullRunError,
    ReplayBatch,
    RunSchedule,
    SpendLedger,
    TrainingDatum,
    execute_locked_run,
    learning_rate_for_step,
    load_checksum_bound_authorization,
    load_checksum_bound_resume_authorization,
    load_locked_run_contract,
    preflight_report,
)

ROOT = Path(__file__).parents[1]


class _Future:
    def __init__(self, value: object) -> None:
        self.value = value

    async def result_async(self) -> object:
        return self.value


class _Client:
    def __init__(self, *, nonfinite: bool = False) -> None:
        self.forward_calls = 0
        self.state_paths: list[str] = []
        self.sampler_paths: list[str] = []
        self.nonfinite = nonfinite

    async def forward_backward_async(self, data: list[object], _: str) -> _Future:
        self.forward_calls += 1
        value = float("nan") if self.nonfinite else -0.5
        outputs = [{"logprobs": tinker.TensorData([value], dtype="float32")} for _datum in data]
        return _Future(SimpleNamespace(loss_fn_outputs=outputs))

    async def optim_step_async(self, _: object) -> _Future:
        return _Future(SimpleNamespace(metrics={"unclipped_grad_l2:mean": 0.25}))

    async def save_state_async(self, name: str, ttl_seconds: int | None) -> _Future:
        assert ttl_seconds is None
        path = f"state://{name}"
        self.state_paths.append(path)
        return _Future(SimpleNamespace(path=path))

    async def save_weights_for_sampler_async(self, name: str, ttl_seconds: int) -> _Future:
        assert ttl_seconds == 3600
        path = f"sampler://{name}"
        self.sampler_paths.append(path)
        return _Future(SimpleNamespace(path=path))


class _Provider:
    def __init__(self, client: _Client) -> None:
        self.client = client
        self.deleted: list[str] = []
        self.factory_calls = 0

    async def identity(self) -> dict[str, object]:
        return {
            "base_model": BACKBONE,
            "is_lora": True,
            "lora_rank": 64,
            "train_attn": True,
            "train_mlp": True,
            "train_unembed": False,
            "training_identity": {"model_id": "parent-training-1"},
        }

    async def create_training_client(self) -> _Client:
        self.factory_calls += 1
        return self.client

    async def checkpoint_size(self, _: str) -> int:
        return 10_000

    async def delete_checkpoint(self, path: str) -> None:
        self.deleted.append(path)

    async def checkpoint_metadata(self, _: str) -> dict[str, object]:
        return {
            "checkpoint_created_at": 1,
            "checkpoint_expires_at": None,
            "checkpoint_is_durable": True,
            "remaining_ttl_seconds": None,
        }


def _contract(*, approved: bool = True) -> LockedRunContract:
    datum = TrainingDatum(
        datum_id="interaction:one",
        kind="interaction",
        input_tokens=(1,),
        target_tokens=(2,),
        weights_bytes=struct.pack("<f", 1.0),
        positive_token_count=1,
    )
    batches = tuple(
        ReplayBatch(
            step_in_epoch=step,
            interaction_ids=(datum.datum_id,),
            replay_ids=(),
            membership_sha256=f"sha256:{step:064x}",
            positive_mass="1",
        )
        for step in range(1, 64)
    )
    two = RunSchedule(
        final_step=126,
        sampler_steps=frozenset({10, 20, 30, 40, 50, 60, 63, 70, 80, 90, 100, 110, 120, 126}),
        state_steps=frozenset({20, 40, 60, 63, 80, 100, 120, 126}),
        full_steps=frozenset({20, 40, 60, 63, 80, 100, 120, 126}),
        fast_only_steps=frozenset({10, 30, 50, 70, 90, 110}),
        retention_steps=frozenset({20, 40, 60, 63, 80, 100, 120, 126}),
    )
    three = RunSchedule(
        final_step=189,
        sampler_steps=two.sampler_steps | {130, 140, 150, 160, 170, 180, 189},
        state_steps=two.state_steps | {140, 160, 180, 189},
        full_steps=two.full_steps | {140, 160, 180, 189},
        fast_only_steps=two.fast_only_steps | {130, 150, 170},
        retention_steps=two.retention_steps | {140, 160, 180, 189},
    )
    return LockedRunContract(
        candidate_manifest_sha256="sha256:" + "a" * 64,
        candidate_sha256sums_sha256="sha256:" + "b" * 64,
        source_commit="c" * 40,
        owner_approved=approved,
        ceiling_usd=10.0,
        projected_two_epoch_usd=2.0,
        checkpoint_byte_ceiling_two_epochs=1_000_000,
        three_epoch_ceiling_usd=20.0,
        projected_three_epoch_usd=3.0,
        checkpoint_byte_ceiling_three_epochs=2_000_000,
        datums={datum.datum_id: datum},
        batches=batches,
        schedule_two_epochs=two,
        schedule_three_epochs=three,
        retention_rows=({"request_id": "retention:one"},),
    )


def _pause_contract() -> LockedRunContract:
    contract = _contract()
    batches = list(contract.batches)
    batches[0] = replace(batches[0], membership_sha256=phase3_full_run.EPOCH_THREE_BATCH_ONE_SHA256)
    return replace(contract, batches=tuple(batches))


def _pending_full_evidence() -> dict[str, object]:
    sha = "sha256:" + "e" * 64
    return {
        "evaluation_identity": ["wp3-4-demo", BACKBONE, "sampler://one", sha],
        "evaluation_status": "pending_human_review",
        "fast_dev_derived_sha256": sha,
        "grades_sha256": sha,
        "open_text_review_sha256": sha,
        "open_text_rows": [
            {
                "framing": {},
                "human_assessment": {"review_status": "pending_human_review"},
                "parser_input_utf8": "answer",
                "predicted_action": {"text": "answer", "type": "respond"},
                "raw_output_sha256": sha,
                "rubric": {"rubric_sha256": sha},
                "state_evidence": {
                    "messages": [{"content": "source", "role": "user"}],
                    "state_id": "dev:one",
                    "visible_prefix_sha256": sha,
                },
                "state_id": "dev:one",
                "structural": {"structural_pass": True},
            }
        ],
        "raw_index_path": "review/phase3/wp3-4-run/raw-index.json",
        "raw_index_sha256": sha,
    }


def _authorization(contract: LockedRunContract) -> dict[str, object]:
    return {
        "kind": "phase3-wp3-4-owner-launch-authorization",
        "owner_decision": "authorized",
        "candidate_manifest_sha256": contract.candidate_manifest_sha256,
        "candidate_sha256sums_sha256": contract.candidate_sha256sums_sha256,
        "derived_source_commit": contract.source_commit,
        "maximum_spend_usd": contract.ceiling_usd,
        "epoch_mode": "two_epoch_only",
        "funding_mode": "owner_monitored_live_top_up",
        "upfront_balance_confirmation_required": False,
        "owner_monitoring_required": True,
        "funding_override": {
            "owner_reported_available_usd": 28.67,
            "sha256": "sha256:" + "d" * 64,
        },
        "detached_execution_required": True,
        "allowed_secret_name": "TINKER_API_KEY",
        "one_locked_run": True,
        "automatic_recovery_authorized": False,
        "human_review_safety_buffer_seconds": 2,
        "human_review_window_seconds": 9,
        "forbidden_operations": [
            "application_retry",
            "sealed_input_access",
            "output_repair",
            "fourth_epoch",
        ],
        "run_id": "wp3-4-demo",
        "runner_source_commit": "f" * 40,
    }


def _authorization_path(root: Path, contract: LockedRunContract, **changes: object) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    receipt = canonical_artifact_bytes(
        {
            "funding_mode": "owner_monitored_live_top_up",
            "kind": "phase3-wp3-4-owner-live-funding-override",
            "maximum_spend_usd": contract.ceiling_usd,
            "owner_decision": "authorized",
            "owner_monitoring_required": True,
            "owner_reported_available_usd": 28.67,
            "upfront_balance_confirmation_required": False,
        }
    )
    receipt_path = root / "funding-override.json"
    receipt_path.write_bytes(receipt)
    authorization = _authorization(contract)
    authorization["funding_override"] = {
        "owner_reported_available_usd": 28.67,
        "sha256": phase3_full_run._digest(receipt),
    }
    authorization["funding_override_path"] = "funding-override.json"
    authorization.update(changes)
    authorization_path = root / "authorization.json"
    authorization_path.write_bytes(canonical_artifact_bytes(authorization))
    return authorization_path


def _full_state_records() -> list[dict[str, object]]:
    return [
        {
            "checkpoint_created_at": 1,
            "checkpoint_expires_at": None,
            "checkpoint_is_durable": True,
            "path": f"state://{step}",
            "remaining_ttl_seconds": None,
            "size_bytes": 1,
            "step": step,
        }
        for step in (20, 40, 60, 63, 80, 100, 120, 126)
    ]


def _resume_authorization(contract: LockedRunContract) -> dict[str, object]:
    return {
        "allowed_secret_name": "TINKER_API_KEY",
        "automatic_recovery_authorized": False,
        "balance_confirmation": {
            "available_usd": 60.0,
            "confirmation_id": "resume-credit-confirmation-1",
            "observed_at_unix": 1,
            "query_identity": "tinker-read-only-balance-v1",
            "sha256": "sha256:" + "d" * 64,
        },
        "candidate_manifest_sha256": contract.candidate_manifest_sha256,
        "candidate_sha256sums_sha256": contract.candidate_sha256sums_sha256,
        "derived_source_commit": contract.source_commit,
        "detached_execution_required": True,
        "d12_decision_sha256": "sha256:" + "1" * 64,
        "epoch_mode": "conditional_third_epoch",
        "forbidden_operations": [
            "application_retry",
            "sealed_input_access",
            "output_repair",
            "fourth_epoch",
        ],
        "human_review_dispositions_sha256": "sha256:" + "2" * 64,
        "human_review_finalization_sha256": "sha256:" + "3" * 64,
        "kind": "phase3-wp3-4-owner-resume-authorization",
        "maximum_additional_spend_usd": 60.0,
        "maximum_cumulative_spend_usd": contract.three_epoch_ceiling_usd,
        "one_locked_resume": True,
        "owner_decision": "authorized",
        "parent_authorization_sha256": "sha256:" + "4" * 64,
        "parent_balance_receipt_sha256": "sha256:" + "5" * 64,
        "resume_control_state_sha256": "sha256:" + "6" * 64,
    }


def test_child_resume_authorization_uses_a_new_receipt_and_rejects_spend_tampering(
    tmp_path: Path,
) -> None:
    contract = _contract()
    receipt = canonical_artifact_bytes(
        {
            "available_usd": 60.0,
            "confirmation_id": "resume-credit-confirmation-1",
            "observed_at_unix": 1,
            "query_identity": "tinker-read-only-balance-v1",
        }
    )
    (tmp_path / "resume-balance.json").write_bytes(receipt)
    authorization = _resume_authorization(contract)
    authorization["balance_confirmation"] = {
        "available_usd": 60.0,
        "confirmation_id": "resume-credit-confirmation-1",
        "observed_at_unix": 1,
        "query_identity": "tinker-read-only-balance-v1",
        "sha256": phase3_full_run._digest(receipt),
    }
    authorization["balance_confirmation_path"] = "resume-balance.json"
    path = tmp_path / "resume-authorization.json"
    path.write_bytes(canonical_artifact_bytes(authorization))
    loaded = load_checksum_bound_resume_authorization(tmp_path, path, contract)
    assert loaded.authorization_sha256 != authorization["parent_authorization_sha256"]
    authorization["maximum_additional_spend_usd"] = 59.0
    path.write_bytes(canonical_artifact_bytes(authorization))
    with pytest.raises(Phase3FullRunError, match="resume authorization"):
        load_checksum_bound_resume_authorization(tmp_path, path, contract)


def test_child_resume_rejects_reused_parent_balance_receipt_before_provider_access() -> None:
    parent_receipt = "sha256:" + "a" * 64
    with pytest.raises(phase3_full_resume.ResumeError, match="reused or predates"):
        phase3_full_resume.require_new_child_balance_receipt(
            parent_receipt, parent_receipt, 200, 100
        )
    with pytest.raises(phase3_full_resume.ResumeError, match="reused or predates"):
        phase3_full_resume.require_new_child_balance_receipt(
            "sha256:" + "b" * 64, parent_receipt, 99, 100
        )
    phase3_full_resume.require_new_child_balance_receipt(
        "sha256:" + "b" * 64, parent_receipt, 101, 100
    )


def test_child_resume_rejects_receipt_after_checkpoint_but_before_pause() -> None:
    with pytest.raises(phase3_full_resume.ResumeError, match="predates the pause"):
        phase3_full_resume.require_new_child_balance_receipt(
            "sha256:" + "b" * 64,
            "sha256:" + "a" * 64,
            150,
            200,
        )


def test_human_review_pause_rejects_any_short_lived_retained_full_state() -> None:
    contract = _pause_contract()
    records = _full_state_records()
    records[0].update(
        {
            "checkpoint_expires_at": 691200,
            "checkpoint_is_durable": False,
            "remaining_ttl_seconds": 691200,
        }
    )
    with pytest.raises(phase3_full_resume.ResumeError, match="lifetime"):
        phase3_full_resume.build_resume_control_state(
            candidate_manifest_sha256=contract.candidate_manifest_sha256,
            derived_source_commit=contract.source_commit,
            contract_batch_one_sha256=contract.batches[0].membership_sha256,
            run_id="wp3-4-demo",
            provider_identity={"training_identity": {"model_id": "parent"}},
            final_execution_source_commit="f" * 40,
            authorized_epoch_mode="two_epoch_only",
            authorization_sha256="sha256:" + "a" * 64,
            balance_receipt_sha256="sha256:" + "b" * 64,
            authorization_payload=_authorization(contract),
            state_records=records,
            ledger_evidence={},
            monitor=phase3_full_resume.NumericalMonitor([1.0] * 5),
            human_review_window_seconds=604800,
            safety_buffer_seconds=86400,
            learning_rate_step_126=learning_rate_for_step(126),
            learning_rate_step_127=learning_rate_for_step(127),
        )


def test_offline_preflight_binds_all_real_candidate_inputs() -> None:
    contract = load_locked_run_contract(ROOT)
    assert len(contract.datums) == 3000
    assert len(contract.batches) == 63
    assert contract.schedule_two_epochs.final_step == 126
    assert len(contract.schedule_two_epochs.sampler_steps) == 14
    assert len(contract.schedule_two_epochs.state_steps) == 8
    assert len(contract.schedule_two_epochs.full_steps) == 8
    assert len(contract.schedule_two_epochs.fast_only_steps) == 6
    assert len(contract.schedule_two_epochs.retention_steps) == 8
    assert contract.schedule_two_epochs.full_steps.isdisjoint(
        contract.schedule_two_epochs.fast_only_steps
    )
    assert preflight_report(contract)["status"] == "blocked_pending_owner_approval"


def test_all_locked_reads_guard_candidate_before_resolution(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    observed: list[Path] = []

    def sealed_guard(root: Path, path: Path) -> Path:
        assert root == tmp_path
        observed.append(path)
        raise Phase3FullRunError("sealed input")

    monkeypatch.setattr(phase3_full_run, "guard_read_path", sealed_guard)
    with pytest.raises(Phase3FullRunError, match="sealed input"):
        phase3_full_run._inside(tmp_path, Path("candidate"))
    assert observed == [Path("candidate")]


def test_frozen_lr_warmup_and_cosine_cover_the_full_189_step_schedule() -> None:
    assert learning_rate_for_step(1) == pytest.approx(3e-4 / 10)
    assert learning_rate_for_step(9) < 3e-4
    assert learning_rate_for_step(10) == pytest.approx(3e-4)
    assert learning_rate_for_step(189) == pytest.approx(0.0)
    with pytest.raises(Phase3FullRunError, match="189-step"):
        learning_rate_for_step(190)


def test_two_epoch_authorization_cannot_use_the_three_epoch_ceiling(tmp_path: Path) -> None:
    contract = _contract()
    with pytest.raises(Phase3FullRunError, match="authorization"):
        load_checksum_bound_authorization(
            tmp_path,
            _authorization_path(
                tmp_path, contract, maximum_spend_usd=contract.three_epoch_ceiling_usd
            ),
            contract,
        )


@pytest.mark.parametrize("available", [float("nan"), float("inf")])
def test_nonfinite_live_funding_report_is_rejected(available: float) -> None:
    contract = _contract()
    authorization = _authorization(contract)
    authorization["funding_override"] = {
        "owner_reported_available_usd": available,
        "sha256": "sha256:" + "d" * 64,
    }
    with pytest.raises(Phase3FullRunError, match="authorization"):
        phase3_full_run._verify_launch_payload(contract, authorization)


def test_cumulative_checkpoint_bytes_cannot_exceed_frozen_mode_ceiling() -> None:
    ledger = SpendLedger(
        ceiling_usd=10.0,
        projected_upper_usd=2.0,
        checkpoint_byte_ceiling=100,
    )
    ledger.observe_checkpoint(60)
    with pytest.raises(Phase3FullRunError, match="cumulative checkpoint bytes"):
        ledger.observe_checkpoint(41)


def test_fake_two_epoch_run_replays_all_steps_dedups_full_fast_and_cleans_samplers(
    tmp_path: Path,
) -> None:
    contract = _pause_contract()
    client = _Client()
    provider = _Provider(client)
    evaluations: list[tuple[str, int]] = []

    async def factory() -> _Provider:
        return provider

    async def evaluator(kind: str, step: int, _: str, rows: object) -> dict[str, object]:
        evaluations.append((kind, step))
        if kind == "automatic_retention_12":
            assert len(rows) == 1
        sha = "sha256:" + "e" * 64
        if kind == "full_dev":
            return _pending_full_evidence()
        if kind == "automatic_retention_12":
            return {"automatic_guard_passed": True, "raw_outputs_sha256": sha, "report_sha256": sha}
        return {"kind": kind, "step": step}

    result = asyncio.run(
        execute_locked_run(
            contract=contract,
            repository_root=tmp_path / "auth",
            authorization_path=_authorization_path(tmp_path / "auth", contract),
            provider_factory=factory,
            evaluator=evaluator,
            output_directory=tmp_path / "run",
            run_id="wp3-4-demo",
            final_execution_source_commit="f" * 40,
        )
    )
    assert result["status"] == "stopped_pending_human_dev_review"
    assert client.forward_calls == 126
    assert len(client.state_paths) == 8
    assert len(client.sampler_paths) == len(provider.deleted) == 14
    assert evaluations.count(("fast_dev", 10)) == 1
    assert evaluations.count(("fast_dev", 70)) == 1
    assert not any(kind == "fast_dev" and step == 20 for kind, step in evaluations)
    assert sum(kind == "full_dev" for kind, _ in evaluations) == 8
    assert sum(kind == "automatic_retention_12" for kind, _ in evaluations) == 8
    evidence = (tmp_path / "run" / "evidence" / "SHA256SUMS").read_text(encoding="ascii")
    assert "sampler_cleanup" in evidence


def test_hard_retention_catastrophe_stops_after_all_evidence_and_cleans_sampler(
    tmp_path: Path,
) -> None:
    contract = replace(_pause_contract(), automatic_retention_hard_abort=True)
    client = _Client()
    provider = _Provider(client)

    async def factory() -> _Provider:
        return provider

    async def evaluator(kind: str, step: int, _: str, __: object) -> dict[str, object]:
        sha = "sha256:" + "e" * 64
        if kind == "full_dev":
            return _pending_full_evidence()
        if kind == "automatic_retention_12":
            assert step == 20
            return {
                "automatic_guard_passed": False,
                "failure_signatures": ["two_or_more_new_length_terminations"],
                "raw_outputs_sha256": sha,
                "report_sha256": sha,
            }
        return {"kind": kind, "step": step}

    result = asyncio.run(
        execute_locked_run(
            contract=contract,
            repository_root=tmp_path / "auth",
            authorization_path=_authorization_path(tmp_path / "auth", contract),
            provider_factory=factory,
            evaluator=evaluator,
            output_directory=tmp_path / "run",
            run_id="wp3-4-demo",
            final_execution_source_commit="f" * 40,
        )
    )
    assert result["status"] == "stopped_retention_catastrophe"
    assert client.forward_calls == 20
    assert provider.deleted == ["sampler://wp3-4-sampler-10", "sampler://wp3-4-sampler-20"]
    evidence = (tmp_path / "run" / "evidence" / "SHA256SUMS").read_text(encoding="ascii")
    assert "retention_catastrophe" in evidence


def test_pause_rechecks_all_full_states_and_rejects_stale_lifetime_metadata(tmp_path: Path) -> None:
    class _StaleAtPauseProvider(_Provider):
        def __init__(self, client: _Client) -> None:
            super().__init__(client)
            self.metadata_reads = 0

        async def checkpoint_metadata(self, _: str) -> dict[str, object]:
            self.metadata_reads += 1
            if self.metadata_reads > 8:
                return {
                    "checkpoint_created_at": 1,
                    "checkpoint_expires_at": 691200,
                    "checkpoint_is_durable": False,
                    "remaining_ttl_seconds": 691199,
                }
            return await super().checkpoint_metadata(_)

    contract = _pause_contract()
    client = _Client()
    provider = _StaleAtPauseProvider(client)

    async def factory() -> _StaleAtPauseProvider:
        return provider

    async def evaluator(kind: str, _: int, __: str, ___: object) -> dict[str, object]:
        sha = "sha256:" + "e" * 64
        if kind == "full_dev":
            return _pending_full_evidence()
        if kind == "automatic_retention_12":
            return {"automatic_guard_passed": True, "raw_outputs_sha256": sha, "report_sha256": sha}
        return {"kind": kind}

    result = asyncio.run(
        execute_locked_run(
            contract=contract,
            repository_root=tmp_path / "auth",
            authorization_path=_authorization_path(tmp_path / "auth", contract),
            provider_factory=factory,
            evaluator=evaluator,
            output_directory=tmp_path / "run",
            run_id="wp3-4-demo",
            final_execution_source_commit="f" * 40,
        )
    )
    assert result["status"] == "failed_service_failure"
    assert client.forward_calls == 126
    assert provider.metadata_reads == 16


def test_pause_fails_closed_when_provider_cannot_recheck_full_state_metadata(
    tmp_path: Path,
) -> None:
    contract = _pause_contract()
    client = _Client()
    provider = _Provider(client)
    provider.checkpoint_metadata = None  # type: ignore[method-assign]

    async def factory() -> _Provider:
        return provider

    async def evaluator(kind: str, _: int, __: str, ___: object) -> dict[str, object]:
        sha = "sha256:" + "e" * 64
        if kind == "full_dev":
            return _pending_full_evidence()
        if kind == "automatic_retention_12":
            return {"automatic_guard_passed": True, "raw_outputs_sha256": sha, "report_sha256": sha}
        return {"kind": kind}

    result = asyncio.run(
        execute_locked_run(
            contract=contract,
            repository_root=tmp_path / "auth",
            authorization_path=_authorization_path(tmp_path / "auth", contract),
            provider_factory=factory,
            evaluator=evaluator,
            output_directory=tmp_path / "run",
            run_id="wp3-4-demo",
            final_execution_source_commit="f" * 40,
        )
    )
    assert result["status"] == "failed_service_failure"
    assert client.forward_calls == 126


def test_pending_human_full_dev_pauses_at_126_with_all_states_and_blind_control_artifacts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    contract = _pause_contract()
    client = _Client()
    provider = _Provider(client)
    monkeypatch.setattr(phase3_human_review.time, "time", lambda: 200)

    async def factory() -> _Provider:
        return provider

    async def evaluator(kind: str, _: int, __: str, rows: object) -> dict[str, object]:
        sha = "sha256:" + "e" * 64
        if kind == "full_dev":
            return _pending_full_evidence()
        if kind == "automatic_retention_12":
            assert len(rows) == 1
            return {
                "automatic_guard_passed": True,
                "failure_signatures": [],
                "raw_outputs_sha256": sha,
                "report_sha256": sha,
            }
        return {"kind": kind}

    result = asyncio.run(
        execute_locked_run(
            contract=contract,
            repository_root=tmp_path / "auth",
            authorization_path=_authorization_path(tmp_path / "auth", contract),
            provider_factory=factory,
            evaluator=evaluator,
            output_directory=tmp_path / "run",
            run_id="wp3-4-demo",
            final_execution_source_commit="f" * 40,
            human_review_window_seconds=9,
            safety_buffer_seconds=2,
        )
    )

    assert result["status"] == "stopped_pending_human_dev_review"
    assert client.forward_calls == 126
    assert len(client.state_paths) == 8
    assert len(client.sampler_paths) == len(provider.deleted) == 14
    review = tmp_path / "run" / "human-review"
    blind = (review / "blind-review-packet.json").read_text(encoding="utf-8")
    control = (review / "step-126-resume-control-state.json").read_text(encoding="utf-8")
    assert '"checkpoint_step"' not in blind
    assert '"messages"' in blind
    assert '"next_global_step":127' in control
    assert '"checkpoint_created_at":1' in control
    assert '"pause_created_at_unix":200' in control


def test_blind_dispositions_exactly_fan_out_and_d12_v2_ignores_early_retention_failures() -> None:
    sha = "sha256:" + "a" * 64
    blind = {
        "kind": "phase3-wp3-4-open-text-blind-review-packet",
        "rows": [{"opaque_review_id": "review-one"}],
    }
    sealed = {
        "rows": [
            {
                "opaque_review_id": "review-one",
                "exact_key": {
                    "state_id": "dev:one",
                    "raw_output_sha256": sha,
                    "rubric_sha256": sha,
                },
                "occurrences": [
                    {"checkpoint_step": 120},
                    {"checkpoint_step": 126},
                ],
            }
        ]
    }
    dispositions = {
        "blind_review_packet_sha256": phase3_full_run._digest(canonical_artifact_bytes(blind)),
        "rows": [
            {
                "opaque_review_id": "review-one",
                "passed": True,
                "reason_codes": ["all_required_points_present", "no_forbidden_claims"],
            }
        ],
    }
    fanout = phase3_human_review.fanout_dispositions(blind, sealed, dispositions)
    assert set(fanout) == {(120, "dev:one"), (126, "dev:one")}

    def full(step: int, score: float, active: int) -> dict[str, object]:
        return {
            "d13_score": score,
            "integer_evidence": {
                "active_floor_respond_count": active,
                "duplicate_delegate_or_schedule_error_count": 0,
                "forbidden_error_count": 0,
                "full_payload_correct_count": 200 + step,
                "low_count_action_slice_error_counts": {"nudge": 0},
                "parse_union_valid_count": 300,
                "positive_structural_correct_count": 153,
            },
            "kind": "full_dev",
            "step": step,
        }

    steps = [
        {"step": step, "loss": {"normalized_loss": 1.0 - step / 10_000}, "epoch": 2}
        for step in range(64, 127)
    ]
    full_rows = [
        full(step, 0.1 if step < 120 else 0.12 + step / 100_000, 1)
        for step in (20, 40, 60, 63, 80, 100, 120, 126)
    ]
    retention = [
        {
            "kind": "automatic_retention_12",
            "step": step,
            "automatic_guard_passed": step != 20,
            "failure_signatures": [],
        }
        for step in (20, 40, 60, 63, 80, 100, 120, 126)
    ]
    decision = phase3_full_run._derive_d12_decision(steps, [*full_rows, *retention])
    assert decision["all_conditions_pass"] is True
    assert decision["early_best_step"] == 80
    assert decision["late_best_step"] == decision["all_best_step"] == 126


def test_d12_v2_directional_regression_vetoes_when_both_gate_values_would_fail() -> None:
    early = {
        "active_floor_respond_count": 2,
        "duplicate_delegate_or_schedule_error_count": 2,
        "forbidden_error_count": 2,
        "full_payload_correct_count": 1,
        "low_count_action_slice_error_counts": {"nudge": 2},
        "parse_union_valid_count": 200,
        "positive_structural_correct_count": 100,
    }
    late = {**early, "active_floor_respond_count": 3}
    assert (
        phase3_human_review._directional_counts(early, late)["active_floor_respond_count"] is False
    )


def test_two_epoch_mode_never_resumes_and_resume_control_tampering_fails_closed() -> None:
    contract = _pause_contract()
    authorization = _authorization(contract)
    control = phase3_full_resume.build_resume_control_state(
        candidate_manifest_sha256=contract.candidate_manifest_sha256,
        derived_source_commit=contract.source_commit,
        contract_batch_one_sha256=contract.batches[0].membership_sha256,
        run_id="wp3-4-demo",
        provider_identity={"training_identity": {"model_id": "parent-training-1"}},
        final_execution_source_commit="f" * 40,
        authorized_epoch_mode="two_epoch_only",
        authorization_sha256="sha256:" + "a" * 64,
        balance_receipt_sha256="sha256:" + "b" * 64,
        authorization_payload=authorization,
        state_records=_full_state_records(),
        ledger_evidence=SpendLedger(20.0, 3.0, 2_000_000).evidence(),
        monitor=phase3_full_resume.NumericalMonitor([1.0] * 5),
        human_review_window_seconds=9,
        safety_buffer_seconds=2,
        learning_rate_step_126=learning_rate_for_step(126),
        learning_rate_step_127=learning_rate_for_step(127),
    )
    control["pause_created_at_unix"] = 200
    phase3_full_run._validate_resume_control_state(control, contract, 9, 2)
    control["authorized_epoch_mode"] = "conditional_third_epoch"
    with pytest.raises(Phase3FullRunError, match="frozen continuation"):
        phase3_full_run._validate_resume_control_state(control, contract, 9, 2)
    control["authorized_epoch_mode"] = "two_epoch_only"
    control["checkpoint_expires_at"] = 10
    control["checkpoint_is_durable"] = False
    control["remaining_ttl_seconds"] = 11
    with pytest.raises(Phase3FullRunError, match="TTL"):
        phase3_full_run._validate_resume_control_state(control, contract, 9, 2)
    control["checkpoint_expires_at"] = None
    control["checkpoint_is_durable"] = True
    control["remaining_ttl_seconds"] = None
    control["next_batch_membership_sha256"] = "sha256:" + "0" * 64
    with pytest.raises(Phase3FullRunError, match="frozen continuation"):
        phase3_full_run._validate_resume_control_state(control, contract, 9, 2)
    assert learning_rate_for_step(127) == pytest.approx(0.00008038119656225339)

    assert control["authorized_epoch_mode"] == "two_epoch_only"


def test_resume_rejects_tampered_finalization_before_provider_access(tmp_path: Path) -> None:
    factory_calls = 0

    async def provider_factory() -> SimpleNamespace:
        nonlocal factory_calls
        factory_calls += 1
        return SimpleNamespace()

    finalized = tmp_path / "human-review" / "finalized"
    finalized.mkdir(parents=True)
    control = tmp_path / "human-review" / "step-126-resume-control-state.json"
    control.write_bytes(canonical_artifact_bytes({"tampered": True}))
    (tmp_path / "human-review" / "SHA256SUMS").write_text(
        f"{'0' * 64}  {control.name}\n", encoding="ascii"
    )
    (finalized / "d12-decision.json").write_bytes(canonical_artifact_bytes({"ok": True}))
    (finalized / "finalization.json").write_bytes(
        canonical_artifact_bytes({"d12": {"all_conditions_pass": True}})
    )
    (finalized / "SHA256SUMS").write_text(
        f"{'0' * 64}  d12-decision.json\n{'0' * 64}  finalization.json\n",
        encoding="ascii",
    )
    with pytest.raises(Phase3FullRunError, match="checksum"):
        asyncio.run(
            phase3_full_run.resume_conditional_epoch_three(
                repository_root=ROOT,
                output_directory=tmp_path,
                authorization_path=tmp_path / "authorization.json",
                contract=_pause_contract(),
                provider_factory=provider_factory,  # type: ignore[arg-type]
                evaluator=SimpleNamespace(),  # type: ignore[arg-type]
                human_review_window_seconds=9,
                safety_buffer_seconds=2,
            )
        )
    assert factory_calls == 0


def test_resume_control_preserves_pending_numerical_trigger_streak() -> None:
    contract = _pause_contract()
    authorization = _authorization(contract)
    monitor = phase3_full_resume.NumericalMonitor([1.0] * 5, 2)
    control = phase3_full_resume.build_resume_control_state(
        candidate_manifest_sha256=contract.candidate_manifest_sha256,
        derived_source_commit=contract.source_commit,
        contract_batch_one_sha256=phase3_full_run.EPOCH_THREE_BATCH_ONE_SHA256,
        run_id="wp3-4-demo",
        provider_identity={"training_identity": {"model_id": "parent"}},
        final_execution_source_commit="f" * 40,
        authorized_epoch_mode="two_epoch_only",
        authorization_sha256="sha256:" + "a" * 64,
        balance_receipt_sha256="sha256:" + "b" * 64,
        authorization_payload=authorization,
        state_records=_full_state_records(),
        ledger_evidence={},
        monitor=monitor,
        human_review_window_seconds=9,
        safety_buffer_seconds=2,
        learning_rate_step_126=learning_rate_for_step(126),
        learning_rate_step_127=learning_rate_for_step(127),
    )
    control["pause_created_at_unix"] = 200
    restored = phase3_full_resume.NumericalMonitor.from_control(control)
    assert restored.post_warmup_losses == [1.0] * 5
    assert restored.consecutive_high_loss_high_grad == 2
    with pytest.raises(phase3_full_resume.RecoveryAuthorizationRequired):
        restored.observe(127, normalized_loss=3.0, gradient=2.0)


def test_invalid_authorization_stops_before_provider_factory(tmp_path: Path) -> None:
    contract = _contract()

    async def factory() -> _Provider:
        raise AssertionError("provider factory must not be called")

    async def evaluator(*_: object) -> dict[str, object]:
        raise AssertionError("evaluator must not be called")

    with pytest.raises(Phase3FullRunError, match="authorization"):
        asyncio.run(
            execute_locked_run(
                contract=contract,
                repository_root=tmp_path / "auth",
                authorization_path=tmp_path / "auth" / "missing.json",
                provider_factory=factory,
                evaluator=evaluator,
                output_directory=tmp_path / "run",
                run_id="wp3-4-demo",
            )
        )


def test_numerical_recovery_stops_once_and_requests_owner_authorization(tmp_path: Path) -> None:
    contract = _contract()
    client = _Client(nonfinite=True)
    provider = _Provider(client)

    async def factory() -> _Provider:
        return provider

    async def evaluator(*_: object) -> dict[str, object]:
        raise AssertionError("non-finite loss must stop before evaluation")

    result = asyncio.run(
        execute_locked_run(
            contract=contract,
            repository_root=tmp_path / "auth",
            authorization_path=_authorization_path(tmp_path / "auth", contract),
            provider_factory=factory,
            evaluator=evaluator,
            output_directory=tmp_path / "run",
            run_id="wp3-4-demo",
        )
    )
    assert result["status"] == "stopped_pending_owner_recovery_authorization"
    assert client.forward_calls == 1
    assert provider.factory_calls == 1
