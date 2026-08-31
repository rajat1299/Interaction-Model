from __future__ import annotations

import asyncio
import json
import os
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import tinker

from im.assets.model import canonical_artifact_bytes
from im.license import LicenseView, PendingToolRequestView, SnapshotView
from im.schema.common import ToolName
from im.schema.textspan import utf16_len
from im.training import phase3_tinker
from im.training.phase3_data import SealedTestAccessError
from im.training.phase3_tinker import (
    CANARY_PLAN,
    CANARY_PLAN_SHA256,
    FROZEN_CANARY_STATE_IDS,
    MAXIMUM_SPEND_USD,
    OPTIMIZER,
    SAMPLING,
    SAMPLING_REQUESTS_SHA256,
    CanaryContract,
    Phase3TinkerError,
    _build_batches,
    _cost_evidence,
    _read_tinker_key,
    _verify_candidate_source_lineage,
    _verify_checkpoint_ceiling,
    _verify_cost_ceiling,
    _verify_detached_execution,
    execute_paid_canary,
    load_canary_contract,
)

ROOT = Path(__file__).parents[1]


def _candidate(directory: Path, **changes: object) -> tuple[Path, str, str]:
    directory.mkdir()
    manifest = {
        "candidate_status": "pending_paid_owner_authorization",
        "canary_contract_amendment_sha256": phase3_tinker.CANARY_AMENDMENT_SHA256,
        "canary_plan_sha256": CANARY_PLAN_SHA256,
        "detached_execution_required": True,
        "fast_sentinel_manifest_sha256": (
            "sha256:0e25ce26321864afc9f6a6361625e27ca1f54eeaa8c4cfd755278552dcb1f447"
        ),
        "gradient_metric_amendment_sha256": (
            phase3_tinker.GRADIENT_METRIC_AMENDMENT_SHA256
        ),
        "kind": "phase3-wp3-3-canary-execution-candidate",
        "maximum_spend_usd": MAXIMUM_SPEND_USD,
        "model": "Qwen/Qwen3.6-35B-A3B",
        "optimizer": OPTIMIZER,
        "paid_call_authorized": False,
        "renderer": "qwen3_5_disable_thinking",
        "run_manifest_sha256": (
            "sha256:0746089410b55405cebcb01d8376ce68807108c8418230da3b60bb85c6fdc945"
        ),
        "runner_code_commit": "a" * 40,
        "sampling": SAMPLING,
        "sampling_requests_sha256": SAMPLING_REQUESTS_SHA256,
        "sealed_test_access": "forbidden",
        "sentinel_state_ids": list(FROZEN_CANARY_STATE_IDS),
        "static_v2_sha256": (
            "sha256:586c91088eabfda9a369ff557c5d0c28fb334dd11f56aed988f1f8a7d6ea1f75"
        ),
        "tinker_cookbook_version": "0.5.3",
        "tinker_sdk_version": "0.24.0",
        "tokenizer_revision": "995ad96eacd98c81ed38be0c5b274b04031597b0",
    }
    manifest.update(changes)
    manifest_bytes = canonical_artifact_bytes(manifest)
    (directory / "canary-execution-manifest.json").write_bytes(manifest_bytes)
    manifest_sha = phase3_tinker._digest(manifest_bytes)
    sums = (
        f"{manifest_sha.removeprefix('sha256:')}  canary-execution-manifest.json\n"
    ).encode()
    (directory / "SHA256SUMS").write_bytes(sums)
    return directory, manifest_sha, phase3_tinker._digest(sums)


def _authorization(path: Path, manifest_sha: str, sums_sha: str, **changes: object) -> Path:
    value = {
        "allowed_secret_name": "TINKER_API_KEY",
        "candidate_manifest_sha256": manifest_sha,
        "candidate_sha256sums_sha256": sums_sha,
        "detached_execution_required": True,
        "forbidden_operations": [
            "application_retry",
            "duplicate_checkpoint_export",
            "full_dev_evaluation",
            "full_retention_evaluation",
            "full_state_download",
            "sealed_test_access",
        ],
        "kind": "phase3-wp3-3-paid-canary-owner-authorization",
        "maximum_spend_usd": 4.0,
        "owner_decision": "authorized",
        "provider_operations": {
            "optimizer_steps": 2,
            "sampler_downloads": 1,
            "sampler_saves": 1,
            "sentinel_samples": 3,
            "state_saves": 1,
            "training_run_identity_reads": 2,
        },
        "sentinel_state_ids": list(FROZEN_CANARY_STATE_IDS),
        "source_commit": "a" * 40,
    }
    value.update(changes)
    path.write_bytes(canonical_artifact_bytes(value))
    return path


def test_contract_binds_plan_sentinels_budget_and_authorization(tmp_path: Path) -> None:
    candidate, manifest_sha, sums_sha = _candidate(tmp_path / "candidate")
    contract = load_canary_contract(
        ROOT,
        candidate,
        _authorization(tmp_path / "authorization.json", manifest_sha, sums_sha),
    )
    assert contract.candidate_manifest_sha256 == manifest_sha
    assert [row["request_id"] for row in contract.sentinels] == list(FROZEN_CANARY_STATE_IDS)
    assert [row["input_token_count"] for row in contract.sentinels] == [16416, 14723, 14398]

    bad = _authorization(
        tmp_path / "bad-authorization.json",
        manifest_sha,
        sums_sha,
        maximum_spend_usd=4.01,
    )
    with pytest.raises(Phase3TinkerError, match="authorization"):
        load_canary_contract(ROOT, candidate, bad)


def test_contract_requires_the_frozen_pipeline_integrity_amendment(tmp_path: Path) -> None:
    candidate, manifest_sha, sums_sha = _candidate(
        tmp_path / "candidate",
        canary_contract_amendment_sha256="sha256:" + "0" * 64,
    )
    with pytest.raises(Phase3TinkerError, match="manifest drifted"):
        load_canary_contract(
            ROOT,
            candidate,
            _authorization(tmp_path / "authorization.json", manifest_sha, sums_sha),
        )


def test_contract_requires_the_frozen_gradient_metric_amendment(tmp_path: Path) -> None:
    candidate, manifest_sha, sums_sha = _candidate(
        tmp_path / "candidate",
        gradient_metric_amendment_sha256="sha256:" + "0" * 64,
    )
    with pytest.raises(Phase3TinkerError, match="manifest drifted"):
        load_canary_contract(
            ROOT,
            candidate,
            _authorization(tmp_path / "authorization.json", manifest_sha, sums_sha),
        )


def test_contract_verifies_gradient_metric_amendment_hash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    candidate, manifest_sha, sums_sha = _candidate(tmp_path / "candidate")
    monkeypatch.setattr(
        phase3_tinker,
        "GRADIENT_METRIC_AMENDMENT_SHA256",
        "sha256:" + "0" * 64,
    )
    with pytest.raises(Phase3TinkerError, match="gradient metric amendment drifted"):
        load_canary_contract(
            ROOT,
            candidate,
            _authorization(tmp_path / "authorization.json", manifest_sha, sums_sha),
        )


def test_runner_code_and_execution_source_allow_only_candidate_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    candidate = tmp_path / "review/phase3/wp3-3-candidate"
    candidate.mkdir(parents=True)
    outputs = [
        SimpleNamespace(returncode=0, stdout=""),
        SimpleNamespace(
            returncode=0,
            stdout=(
                "review/phase3/wp3-3-candidate/SHA256SUMS\n"
                "review/phase3/wp3-3-candidate/canary-execution-manifest.json\n"
            ),
        ),
    ]
    monkeypatch.setattr(phase3_tinker.subprocess, "run", lambda *_args, **_kwargs: outputs.pop(0))
    _verify_candidate_source_lineage(tmp_path, "a" * 40, "b" * 40, candidate)

    outputs[:] = [
        SimpleNamespace(returncode=0, stdout=""),
        SimpleNamespace(returncode=0, stdout="unrelated.py\n"),
    ]
    with pytest.raises(Phase3TinkerError, match="lineage"):
        _verify_candidate_source_lineage(tmp_path, "a" * 40, "b" * 40, candidate)


def test_low_level_datums_preserve_raw_float32_masks() -> None:
    plan = json.loads((ROOT / CANARY_PLAN).read_bytes())
    step1, step2 = _build_batches(plan)
    assert [len(step1), len(step2)] == [14, 3]
    assert sum(datum.model_input.length for datum in step1) == 185146
    assert sum(datum.model_input.length for datum in step2) == 28765
    replay_weights = step2[-1].loss_fn_inputs["weights"].to_numpy()
    assert set(np.unique(replay_weights)) == {np.float32(0.0), np.float32(0.30000001192092896)}


def test_checkpoint_size_ceiling_fails_above_128_decimal_gb() -> None:
    _verify_checkpoint_ceiling({"state": 127_000_000_000, "sampler": 1_000_000_000})
    with pytest.raises(Phase3TinkerError, match="128 GB"):
        _verify_checkpoint_ceiling({"state": 127_000_000_001, "sampler": 1_000_000_000})


def test_actual_checkpoint_bytes_must_also_fit_four_dollar_budget() -> None:
    approved = _cost_evidence(33_207_091_200, 3072)
    assert approved["sentinel_prefill_tokens"] == 54_546
    _verify_cost_ceiling(approved)
    with pytest.raises(Phase3TinkerError, match=r"\$4"):
        _verify_cost_ceiling(_cost_evidence(40_000_000_000, 3072))


def test_paid_runner_requires_frozen_macos_launchd_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(phase3_tinker.sys, "platform", "darwin")
    monkeypatch.setattr(phase3_tinker.os, "getppid", lambda: 1)
    monkeypatch.setenv("PHASE3_LAUNCHD_LABEL", "com.interactionmodel.wp3-3-canary")
    _verify_detached_execution()

    monkeypatch.setattr(phase3_tinker.os, "getppid", lambda: 2)
    with pytest.raises(Phase3TinkerError, match="detached launchd"):
        _verify_detached_execution()


def test_secret_path_symlink_into_sealed_test_fails_before_read(tmp_path: Path) -> None:
    sealed = tmp_path / "review/phase2/wp2-10-test-closeout"
    sealed.mkdir(parents=True)
    target = sealed / "not-an-env"
    target.write_text("TINKER_API_KEY=must-not-read\n", encoding="utf-8")
    (tmp_path / ".env").symlink_to(target)

    with pytest.raises(SealedTestAccessError):
        _read_tinker_key(tmp_path)


class _Future:
    def __init__(self, value: object, calls: list[str], label: str) -> None:
        self.value = value
        self.calls = calls
        self.label = label

    async def result_async(self) -> object:
        self.calls.append(f"{self.label}:result")
        return self.value


def _model_info(model_id: str) -> object:
    return SimpleNamespace(
        is_lora=True,
        lora_rank=64,
        model_data=SimpleNamespace(
            arch="qwen3_5_moe",
            model_name="Qwen/Qwen3.6-35B-A3B",
            tokenizer_id="Qwen/Qwen3.6-35B-A3B",
        ),
        model_id=model_id,
        model_name="Qwen/Qwen3.6-35B-A3B",
    )


def _training_run(model_id: str) -> object:
    return SimpleNamespace(
        base_model="Qwen/Qwen3.6-35B-A3B",
        corrupted=False,
        is_lora=True,
        lora_rank=64,
        training_run_id=model_id,
        user_metadata={"run_id": "wp3-3-test-run", "step": "1"},
    )


def test_rest_run_identity_is_authoritative_when_get_info_fields_are_optional() -> None:
    info = SimpleNamespace(
        is_lora=None,
        lora_rank=None,
        model_data=SimpleNamespace(
            arch="qwen3_5_moe",
            model_name="Qwen/Qwen3.6-35B-A3B",
            tokenizer_id=None,
        ),
        model_id="model-1",
        model_name=None,
    )

    evidence = phase3_tinker._verify_info(info, _training_run("model-1"))

    assert evidence["rest_base_model"] == "Qwen/Qwen3.6-35B-A3B"
    assert evidence["model_name"] is None
    assert evidence["tokenizer_resolution"] == "model_name_fallback"


def test_get_info_optional_fields_may_not_contradict_rest_identity() -> None:
    info = _model_info("model-1")
    info.model_name = "Qwen/wrong"

    with pytest.raises(Phase3TinkerError, match="contradicts"):
        phase3_tinker._verify_info(info, _training_run("model-1"))


def test_tokenizer_fallback_requires_exact_model_data_name() -> None:
    info = _model_info("model-1")
    info.model_data.model_name = None
    info.model_data.tokenizer_id = None

    with pytest.raises(Phase3TinkerError, match="tokenizer fallback"):
        phase3_tinker._verify_info(info, _training_run("model-1"))


def test_explicit_tokenizer_allows_optional_model_data_name() -> None:
    info = _model_info("model-1")
    info.model_data.model_name = None

    evidence = phase3_tinker._verify_info(info, _training_run("model-1"))

    assert evidence["tokenizer_resolution"] == "explicit"


def test_no_checkpoint_path_means_no_ttl_fallback() -> None:
    evidence = phase3_tinker._checkpoint_cleanup_evidence(
        {"sampler": None, "state": None},
        {"sampler": False, "state": False},
        {"sampler": False, "state": False},
    )

    assert evidence == {
        "checkpoint_path_obtained": {"sampler": False, "state": False},
        "checkpoint_creation_status": {"sampler": "not_attempted", "state": "not_attempted"},
        "checkpoint_deletion": {"sampler": False, "state": False},
        "ttl_fallback_active": False,
    }


def test_ambiguous_checkpoint_save_activates_ttl_fallback() -> None:
    evidence = phase3_tinker._checkpoint_cleanup_evidence(
        {"sampler": None, "state": None},
        {"sampler": False, "state": False},
        {"sampler": False, "state": True},
    )

    assert evidence["checkpoint_creation_status"] == {
        "sampler": "not_attempted",
        "state": "unknown_after_attempt",
    }
    assert evidence["checkpoint_path_obtained"] == {"sampler": False, "state": False}
    assert "checkpoint_created" not in evidence
    assert evidence["ttl_fallback_active"] is True


def _weights_info() -> object:
    return SimpleNamespace(
        base_model="Qwen/Qwen3.6-35B-A3B",
        is_lora=True,
        lora_rank=64,
        train_attn=True,
        train_mlp=True,
        train_unembed=False,
    )


class _TrainingClient:
    def __init__(self, calls: list[str], step: int) -> None:
        self.calls = calls
        self.step = step

    async def get_info_async(self) -> object:
        self.calls.append(f"step{self.step}:info")
        return _model_info(f"model-{self.step}")

    async def forward_backward_async(self, data: list[object], loss: str) -> _Future:
        self.calls.append(f"step{self.step}:forward:{len(data)}:{loss}")
        value = -1.0 if self.step == 1 else -0.5
        outputs = [
            {"logprobs": tinker.TensorData([value] * datum.model_input.length, dtype="float32")}
            for datum in data
        ]
        return _Future(
            SimpleNamespace(loss_fn_outputs=outputs, metrics={"grad_norm": 0.25}),
            self.calls,
            f"step{self.step}:forward",
        )

    async def optim_step_async(self, params: object) -> _Future:
        self.calls.append(f"step{self.step}:optim")
        return _Future(
            SimpleNamespace(
                metrics={
                    "ok": 1.0,
                    "unclipped_grad_l2:mean": 0.0 if self.step == 1 else 0.25,
                }
            ),
            self.calls,
            f"step{self.step}:optim",
        )

    async def save_state_async(self, name: str, ttl_seconds: int) -> _Future:
        self.calls.append(f"save_state:{name}:{ttl_seconds}")
        return _Future(
            SimpleNamespace(path="tinker://run-1/weights/state"), self.calls, "save_state"
        )

    async def save_weights_for_sampler_async(self, name: str, ttl_seconds: int) -> _Future:
        self.calls.append(f"save_sampler:{name}:{ttl_seconds}")
        return _Future(
            SimpleNamespace(path="tinker://run-2/sampler_weights/sampler"),
            self.calls,
            "save_sampler",
        )


class _SamplingClient:
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls

    async def sample_async(self, **_: object) -> object:
        self.calls.append("sample")
        return SimpleNamespace(
            sequences=[SimpleNamespace(stop_reason="stop", tokens=(1, 248046))]
        )


class _RestClient:
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls

    def get_weights_info_by_tinker_path(self, path: str) -> _Future:
        self.calls.append(f"weights_info:{path}")
        return _Future(_weights_info(), self.calls, "weights_info")

    async def get_training_run_async(self, run_id: str) -> object:
        self.calls.append(f"run_info:{run_id}")
        return _training_run(run_id)

    async def list_checkpoints_async(self, run_id: str) -> object:
        self.calls.append(f"list:{run_id}")
        path = (
            "tinker://run-1/weights/state"
            if run_id == "run-1"
            else "tinker://run-2/sampler_weights/sampler"
        )
        return SimpleNamespace(checkpoints=[SimpleNamespace(tinker_path=path, size_bytes=1000)])

    async def get_checkpoint_archive_url_from_tinker_path_async(self, path: str) -> object:
        self.calls.append(f"archive:{path}")
        return SimpleNamespace(url="https://signed.invalid/archive")

    async def delete_checkpoint_from_tinker_path_async(self, path: str) -> None:
        self.calls.append(f"delete:{path}")


class _ServiceClient:
    calls: list[str] = []

    def __init__(self, **_: object) -> None:
        assert os.environ.get("TINKER_API_KEY") == "secret"
        self.rest = _RestClient(self.calls)

    def create_rest_client(self) -> _RestClient:
        return self.rest

    async def get_server_capabilities_async(self) -> object:
        self.calls.append("capabilities")
        return SimpleNamespace(
            supported_models=[
                SimpleNamespace(
                    max_context_length=65536,
                    model_name="Qwen/Qwen3.6-35B-A3B",
                )
            ]
        )

    async def create_lora_training_client_async(self, **_: object) -> _TrainingClient:
        assert os.environ.get("TINKER_API_KEY") == "secret"
        self.calls.append("create_lora")
        return _TrainingClient(self.calls, 1)

    async def create_training_client_from_state_with_optimizer_async(
        self, path: str, **_: object
    ) -> _TrainingClient:
        self.calls.append(f"resume:{path}")
        return _TrainingClient(self.calls, 2)

    async def create_sampling_client_async(self, **_: object) -> _SamplingClient:
        self.calls.append("create_sampler")
        return _SamplingClient(self.calls)


class _CapabilityFailureService:
    def __init__(self, **_: object) -> None:
        assert os.environ.get("TINKER_API_KEY") == "secret"

    async def get_server_capabilities_async(self) -> object:
        raise RuntimeError("provider unavailable")


class _NonFiniteTrainingClient(_TrainingClient):
    async def forward_backward_async(self, data: list[object], loss: str) -> _Future:
        self.calls.append(f"step{self.step}:forward:{len(data)}:{loss}")
        outputs = [
            {
                "logprobs": tinker.TensorData(
                    [float("nan")] * datum.model_input.length, dtype="float32"
                )
            }
            for datum in data
        ]
        return _Future(
            SimpleNamespace(loss_fn_outputs=outputs, metrics={"grad_norm": 0.25}),
            self.calls,
            f"step{self.step}:forward",
        )


class _ZeroSizeRest:
    async def list_checkpoints_async(self, run_id: str) -> object:
        return SimpleNamespace(
            checkpoints=[
                SimpleNamespace(
                    size_bytes=0,
                    tinker_path="tinker://run-1/weights/state",
                )
            ]
        )


class _EmptyArchiveResponse:
    def __enter__(self) -> _EmptyArchiveResponse:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self, _size: int) -> bytes:
        return b""


class _Tokenizer:
    def decode(self, token_ids: object, *, skip_special_tokens: bool) -> str:
        assert skip_special_tokens is False
        ids = list(token_ids)  # type: ignore[arg-type]
        action = (
            '{"args":{"query":"Renwick Landing crate mark"},'
            '"fact":{"end_utf16":34,"event_id":"e_000012",'
            '"start_utf16":6,"text":"Renwick Landing crate mark"},'
            '"tool":"lookup","type":"delegate"}'
        )
        return action + ("<|im_end|>" if ids[-1] == 248046 else "")


def test_fake_runner_uses_two_steps_two_saves_three_samples_one_download_and_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = json.loads((ROOT / CANARY_PLAN).read_bytes())
    real_candidate, manifest_sha, sums_sha = _candidate(tmp_path / "candidate")
    auth = _authorization(tmp_path / "authorization.json", manifest_sha, sums_sha)
    base = load_canary_contract(ROOT, real_candidate, auth)
    contract = CanaryContract(
        plan=plan,
        sentinels=base.sentinels,
        candidate_manifest_sha256=manifest_sha,
        candidate_sha256sums_sha256=sums_sha,
        authorization_sha256="sha256:" + "a" * 64,
        runner_code_commit="a" * 40,
        source_commit="b" * 40,
    )
    root = tmp_path / "repository"
    root.mkdir()
    _ServiceClient.calls = []
    monkeypatch.setattr(phase3_tinker, "load_canary_contract", lambda *_: contract)
    monkeypatch.setattr(phase3_tinker, "_verify_candidate_source_lineage", lambda *_: None)
    monkeypatch.setattr(phase3_tinker, "verify_execution_source", lambda *_: "c" * 40)
    monkeypatch.setattr(phase3_tinker, "_verify_detached_execution", lambda: None)
    monkeypatch.setattr(phase3_tinker, "read_tinker_api_key", lambda *_: "secret")
    monkeypatch.setattr(phase3_tinker.tinker, "ServiceClient", _ServiceClient)
    monkeypatch.setattr(
        phase3_tinker,
        "_hash_download",
        lambda _url: {"bytes": 1234, "sha256": "sha256:" + "d" * 64},
    )

    async def sentinel_states(*_args: object) -> dict[str, object]:
        return {
            state_id: SimpleNamespace(
                boundary=SimpleNamespace(
                    license_view=LicenseView(
                        events=(
                            SnapshotView("e_000012", "Lookup Renwick Landing crate mark."),
                        )
                    )
                )
            )
            for state_id in FROZEN_CANARY_STATE_IDS
        }

    monkeypatch.setattr(phase3_tinker, "_frozen_sentinel_states", sentinel_states)
    monkeypatch.setattr(
        phase3_tinker,
        "grade_persisted_generation",
        lambda *_args, **_kwargs: {
            "executed": {"match": False},
            "framing": {"terminal_projection_status": "projected"},
            "predicted_action": None,
            "structural": {
                "license_block_codes": ["malformed_action"],
                "licensed": False,
                "parse_error": "ValidationError",
                "parse_union_valid": False,
                "reference_integrity": False,
            },
        },
    )

    report = asyncio.run(
        execute_paid_canary(
            repository_root=root,
            candidate_directory=root / "candidate",
            authorization_path=root / "authorization.json",
            tokenizer=SimpleNamespace(tokenizer=_Tokenizer()),
            output_directory=root / "review/phase3/wp3-3-test-run",
            run_id="wp3-3-test-run",
        )
    )

    calls = _ServiceClient.calls
    assert calls.count("create_lora") == 1
    assert calls.count("step1:optim") == calls.count("step2:optim") == 1
    assert calls.count("save_state:wp3-canary-step-1-state:3600") == 1
    assert calls.count("save_sampler:wp3-canary-step-2-sampler:3600") == 1
    assert calls.count("sample") == 3
    assert sum(call.startswith("archive:") for call in calls) == 1
    assert sum(call.startswith("delete:") for call in calls) == 2
    assert report["status"] == "integrity_verified_pending_final_publication"
    assert report["checkpoint_deletion"] == {"sampler": True, "state": True}
    assert report["pipeline"] == {
        "definition": "pipeline_integrity_not_held_out_quality",
        "final_publication": "pending_root_checksum",
        "integrity_checks_passed": True,
    }
    assert report["gradient_metric_amendment_sha256"] == (
        phase3_tinker.GRADIENT_METRIC_AMENDMENT_SHA256
    )
    assert report["provider_operations_completed"]["get_training_run"] == 2
    assert len(report["sentinel_quality_diagnostics"]["records"]) == 3
    quality = report["sentinel_quality_diagnostics"]["records"][0]["quality"]
    assert quality["strict_action_union"]["valid"] is False
    assert quality["span"]["recoverable_delegate_span"]["recoverable"] is True
    assert report["evidence"]["gradient_step_1"] == {
        "optimizer.unclipped_grad_l2:mean": 0.0
    }
    assert report["evidence"]["gradient_step_2"] == {
        "optimizer.unclipped_grad_l2:mean": 0.25
    }
    assert report["evidence"]["parameter_update"] == {
        "causal_pair_logprobs_after": [
            report["evidence"]["step_2_loss"]["rows"][0]["logprobs_sha256"],
            report["evidence"]["step_2_loss"]["rows"][1]["logprobs_sha256"],
        ],
        "causal_pair_logprobs_before": [
            report["evidence"]["step_1_loss"]["rows"][-4]["logprobs_sha256"],
            report["evidence"]["step_1_loss"]["rows"][-3]["logprobs_sha256"],
        ],
        "changed_after_step_1_and_optimizer_resume": True,
    }
    for stage_name, expected_gradient in (
        ("step_1_exact_gradient_metric", 0.0),
        ("step_2_exact_gradient_metric", 0.25),
        ("step_1_optimizer_update", 0.0),
        ("step_2_optimizer_update", 0.25),
    ):
        stage = json.loads(
            next((root / "review/phase3/wp3-3-test-run/evidence").glob(f"*-{stage_name}.json"))
            .read_text()
        )
        if stage_name.endswith("exact_gradient_metric"):
            assert stage["evidence"] == {"optimizer.unclipped_grad_l2:mean": expected_gradient}
        else:
            assert stage["evidence"]["gradient_evidence"] == {
                "optimizer.unclipped_grad_l2:mean": expected_gradient
            }
    status = json.loads((root / "review/phase3/wp3-3-test-run/status.json").read_text())
    assert status["evidence_stage_count"] >= 18
    evidence_sums = root / "review/phase3/wp3-3-test-run/evidence/SHA256SUMS"
    assert evidence_sums.exists()
    report_chain = report["evidence_chain"]
    assert report_chain == {
        "chain_head_sha256": status["evidence_chain_head_sha256"],
        "sha256sums_sha256": phase3_tinker._digest(evidence_sums.read_bytes()),
        "stage_count": status["evidence_stage_count"],
    }
    root_sums = (root / "review/phase3/wp3-3-test-run/SHA256SUMS").read_text()
    assert f"{sha256(evidence_sums.read_bytes()).hexdigest()}  evidence/SHA256SUMS\n" in root_sums
    status_bytes = (root / "review/phase3/wp3-3-test-run/status.json").read_bytes()
    assert f"{sha256(status_bytes).hexdigest()}  status.json\n" in root_sums
    assert "TINKER_API_KEY" not in os.environ


def test_v3_provider_failure_has_its_own_pipeline_classification(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = json.loads((ROOT / CANARY_PLAN).read_bytes())
    candidate, manifest_sha, sums_sha = _candidate(tmp_path / "candidate")
    auth = _authorization(tmp_path / "authorization.json", manifest_sha, sums_sha)
    base = load_canary_contract(ROOT, candidate, auth)
    contract = CanaryContract(
        plan=plan,
        sentinels=base.sentinels,
        candidate_manifest_sha256=manifest_sha,
        candidate_sha256sums_sha256=sums_sha,
        authorization_sha256="sha256:" + "a" * 64,
        runner_code_commit="a" * 40,
        source_commit="b" * 40,
    )
    root = tmp_path / "repository"
    root.mkdir()
    monkeypatch.setattr(phase3_tinker, "load_canary_contract", lambda *_: contract)
    monkeypatch.setattr(phase3_tinker, "_verify_candidate_source_lineage", lambda *_: None)
    monkeypatch.setattr(phase3_tinker, "verify_execution_source", lambda *_: "c" * 40)
    monkeypatch.setattr(phase3_tinker, "_verify_detached_execution", lambda: None)
    monkeypatch.setattr(phase3_tinker, "read_tinker_api_key", lambda *_: "secret")
    monkeypatch.setattr(phase3_tinker.tinker, "ServiceClient", _CapabilityFailureService)

    with pytest.raises(RuntimeError, match="provider unavailable"):
        asyncio.run(
            execute_paid_canary(
                repository_root=root,
                candidate_directory=root / "candidate",
                authorization_path=root / "authorization.json",
                tokenizer=SimpleNamespace(tokenizer=_Tokenizer()),
                output_directory=root / "review/phase3/wp3-3-test-run",
                run_id="wp3-3-test-run",
            )
        )

    status = json.loads((root / "review/phase3/wp3-3-test-run/status.json").read_text())
    assert status["classification"] == "canary_incomplete_due_to_pipeline_failure"
    assert status["classification"] != "canary_incomplete_due_to_fail_fast"


def test_final_publication_failure_never_publishes_a_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = json.loads((ROOT / CANARY_PLAN).read_bytes())
    candidate, manifest_sha, sums_sha = _candidate(tmp_path / "candidate")
    auth = _authorization(tmp_path / "authorization.json", manifest_sha, sums_sha)
    base = load_canary_contract(ROOT, candidate, auth)
    contract = CanaryContract(
        plan=plan,
        sentinels=base.sentinels,
        candidate_manifest_sha256=manifest_sha,
        candidate_sha256sums_sha256=sums_sha,
        authorization_sha256="sha256:" + "a" * 64,
        runner_code_commit="a" * 40,
        source_commit="b" * 40,
    )
    root = tmp_path / "repository"
    root.mkdir()
    _ServiceClient.calls = []
    monkeypatch.setattr(phase3_tinker, "load_canary_contract", lambda *_: contract)
    monkeypatch.setattr(phase3_tinker, "_verify_candidate_source_lineage", lambda *_: None)
    monkeypatch.setattr(phase3_tinker, "verify_execution_source", lambda *_: "c" * 40)
    monkeypatch.setattr(phase3_tinker, "_verify_detached_execution", lambda: None)
    monkeypatch.setattr(phase3_tinker, "read_tinker_api_key", lambda *_: "secret")
    monkeypatch.setattr(phase3_tinker.tinker, "ServiceClient", _ServiceClient)
    monkeypatch.setattr(
        phase3_tinker,
        "_hash_download",
        lambda _url: {"bytes": 1234, "sha256": "sha256:" + "d" * 64},
    )

    async def sentinel_states(*_args: object) -> dict[str, object]:
        return {
            state_id: SimpleNamespace(
                boundary=SimpleNamespace(
                    license_view=LicenseView(
                        events=(
                            SnapshotView("e_000012", "Lookup Renwick Landing crate mark."),
                        )
                    )
                )
            )
            for state_id in FROZEN_CANARY_STATE_IDS
        }

    monkeypatch.setattr(phase3_tinker, "_frozen_sentinel_states", sentinel_states)
    monkeypatch.setattr(
        phase3_tinker,
        "grade_persisted_generation",
        lambda *_args, **_kwargs: {
            "executed": {"match": False},
            "framing": {"terminal_projection_status": "projected"},
            "predicted_action": None,
            "structural": {
                "license_block_codes": ["malformed_action"],
                "licensed": False,
                "parse_error": "ValidationError",
                "parse_union_valid": False,
                "reference_integrity": False,
            },
        },
    )
    original_write = phase3_tinker._write_artifact

    def fail_passed_status(path: Path, raw: bytes) -> None:
        if path.name == "status.json" and b'"status":"passed"' in raw:
            raise OSError("passed status write failed")
        original_write(path, raw)

    monkeypatch.setattr(phase3_tinker, "_write_artifact", fail_passed_status)

    with pytest.raises(Phase3TinkerError, match="final status publication failed"):
        asyncio.run(
            execute_paid_canary(
                repository_root=root,
                candidate_directory=root / "candidate",
                authorization_path=root / "authorization.json",
                tokenizer=SimpleNamespace(tokenizer=_Tokenizer()),
                output_directory=root / "review/phase3/wp3-3-test-run",
                run_id="wp3-3-test-run",
            )
        )

    output = root / "review/phase3/wp3-3-test-run"
    status = json.loads((output / "status.json").read_text())
    assert status["classification"] == "canary_incomplete_due_to_pipeline_failure"
    assert status["status"] == "failed"
    assert status["phase"] == "final_status_publication_failure"
    assert (output / "SHA256SUMS").exists()
    assert json.loads((output / "run-report.json").read_text())["status"] == (
        "integrity_verified_pending_final_publication"
    )
    assert next(
        (output / "evidence").glob("*-final_status_publication_failure.json")
    ).exists()


def test_numerical_failure_persists_finite_safe_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = json.loads((ROOT / CANARY_PLAN).read_bytes())
    candidate, manifest_sha, sums_sha = _candidate(tmp_path / "candidate")
    auth = _authorization(tmp_path / "authorization.json", manifest_sha, sums_sha)
    base = load_canary_contract(ROOT, candidate, auth)
    contract = CanaryContract(
        plan=plan,
        sentinels=base.sentinels,
        candidate_manifest_sha256=manifest_sha,
        candidate_sha256sums_sha256=sums_sha,
        authorization_sha256="sha256:" + "a" * 64,
        runner_code_commit="a" * 40,
        source_commit="b" * 40,
    )
    root = tmp_path / "repository"
    root.mkdir()
    _ServiceClient.calls = []
    monkeypatch.setattr(phase3_tinker, "load_canary_contract", lambda *_: contract)
    monkeypatch.setattr(phase3_tinker, "_verify_candidate_source_lineage", lambda *_: None)
    monkeypatch.setattr(phase3_tinker, "verify_execution_source", lambda *_: "c" * 40)
    monkeypatch.setattr(phase3_tinker, "_verify_detached_execution", lambda: None)
    monkeypatch.setattr(phase3_tinker, "read_tinker_api_key", lambda *_: "secret")
    monkeypatch.setattr(phase3_tinker.tinker, "ServiceClient", _ServiceClient)

    async def nonfinite_lora(*_args: object, **_kwargs: object) -> _NonFiniteTrainingClient:
        return _NonFiniteTrainingClient(_ServiceClient.calls, 1)

    monkeypatch.setattr(_ServiceClient, "create_lora_training_client_async", nonfinite_lora)

    with pytest.raises(Phase3TinkerError, match="loss is non-finite"):
        asyncio.run(
            execute_paid_canary(
                repository_root=root,
                candidate_directory=root / "candidate",
                authorization_path=root / "authorization.json",
                tokenizer=SimpleNamespace(tokenizer=_Tokenizer()),
                output_directory=root / "review/phase3/wp3-3-test-run",
                run_id="wp3-3-test-run",
            )
        )

    output = root / "review/phase3/wp3-3-test-run"
    numerical = json.loads(next((output / "evidence").glob("*-numerical_failure.json")).read_text())
    assert numerical["evidence"]["reason"] == "canary loss is non-finite"
    assert numerical["evidence"]["row_index"] == 0
    assert numerical["evidence"]["weighted_loss"] == {"classification": "nan"}
    assert numerical["evidence"]["normalized_loss"] == {"classification": "nan"}
    assert numerical["evidence"]["positive_mass"]["classification"] == "finite"
    assert "numerical_failure" in (output / "evidence" / "SHA256SUMS").read_text()
    status = json.loads((output / "status.json").read_text())
    assert status["classification"] == "canary_incomplete_due_to_pipeline_failure"
    assert status["numerical"]["weighted_loss"] == {"classification": "nan"}


def test_exact_gradient_stage_survives_later_nonfinite_optimizer_metric(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = json.loads((ROOT / CANARY_PLAN).read_bytes())
    candidate, manifest_sha, sums_sha = _candidate(tmp_path / "candidate")
    auth = _authorization(tmp_path / "authorization.json", manifest_sha, sums_sha)
    base = load_canary_contract(ROOT, candidate, auth)
    contract = CanaryContract(
        plan=plan,
        sentinels=base.sentinels,
        candidate_manifest_sha256=manifest_sha,
        candidate_sha256sums_sha256=sums_sha,
        authorization_sha256="sha256:" + "a" * 64,
        runner_code_commit="a" * 40,
        source_commit="b" * 40,
    )
    root = tmp_path / "repository"
    root.mkdir()
    _ServiceClient.calls = []
    monkeypatch.setattr(phase3_tinker, "load_canary_contract", lambda *_: contract)
    monkeypatch.setattr(phase3_tinker, "_verify_candidate_source_lineage", lambda *_: None)
    monkeypatch.setattr(phase3_tinker, "verify_execution_source", lambda *_: "c" * 40)
    monkeypatch.setattr(phase3_tinker, "_verify_detached_execution", lambda: None)
    monkeypatch.setattr(phase3_tinker, "read_tinker_api_key", lambda *_: "secret")
    monkeypatch.setattr(phase3_tinker.tinker, "ServiceClient", _ServiceClient)

    async def gradient_then_nonfinite_metric(self: _TrainingClient, _params: object) -> _Future:
        self.calls.append(f"step{self.step}:optim")
        return _Future(
            SimpleNamespace(
                metrics={
                    "unclipped_grad_l2:mean": 0.25,
                    "unrelated_optimizer_metric": float("nan"),
                }
            ),
            self.calls,
            f"step{self.step}:optim",
        )

    monkeypatch.setattr(_TrainingClient, "optim_step_async", gradient_then_nonfinite_metric)

    with pytest.raises(Phase3TinkerError, match="metric is non-finite"):
        asyncio.run(
            execute_paid_canary(
                repository_root=root,
                candidate_directory=root / "candidate",
                authorization_path=root / "authorization.json",
                tokenizer=SimpleNamespace(tokenizer=_Tokenizer()),
                output_directory=root / "review/phase3/wp3-3-test-run",
                run_id="wp3-3-test-run",
            )
        )

    output = root / "review/phase3/wp3-3-test-run"
    gradient_stage_path = next(
        (output / "evidence").glob("*-step_1_exact_gradient_metric.json")
    )
    gradient_stage = json.loads(gradient_stage_path.read_text())
    assert gradient_stage["evidence"] == {"optimizer.unclipped_grad_l2:mean": 0.25}
    assert not list((output / "evidence").glob("*-step_1_optimizer_update.json"))
    assert (
        f"{sha256(gradient_stage_path.read_bytes()).hexdigest()}  {gradient_stage_path.name}\n"
        in (output / "evidence" / "SHA256SUMS").read_text()
    )


def test_checkpoint_and_archive_records_must_be_nonempty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(Phase3TinkerError, match="checkpoint size record"):
        asyncio.run(
            phase3_tinker._checkpoint_sizes(
                _ZeroSizeRest(), ("tinker://run-1/weights/state",)
            )
        )
    monkeypatch.setattr(
        phase3_tinker.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: _EmptyArchiveResponse(),
    )
    with pytest.raises(Phase3TinkerError, match="archive download is empty"):
        phase3_tinker._hash_download("https://signed.invalid/archive")


def _boundary_only_delegate_candidate(
    *, text: str = "Renwick Landing crate mark",
    query: str = "Renwick Landing crate mark",
    event_id: str = "e_000012",
    start_utf16: int | None = None,
    end_utf16: int | None = None,
) -> dict[str, object]:
    canonical_start = utf16_len("Lookup ")
    default_end = canonical_start + utf16_len(text) + 1
    return {
        "args": {"query": query},
        "fact": {
            "end_utf16": end_utf16 if end_utf16 is not None else default_end,
            "event_id": event_id,
            "start_utf16": start_utf16 if start_utf16 is not None else canonical_start - 1,
            "text": text,
        },
        "tool": "lookup",
        "type": "delegate",
    }


def test_recoverable_delegate_span_preserves_v2_renwick_strict_failure() -> None:
    query = "Renwick Landing crate mark"
    raw_path = next(
        (ROOT / "review/phase3/wp3-3-canary-run-v2/raw").glob("*/raw-generation.json")
    )
    raw = json.loads(raw_path.read_text())
    candidate = json.loads(raw["decoded_utf8"].removesuffix("<|im_end|>"))
    view = LicenseView(events=(SnapshotView("e_000012", "x" * 14 + f" {query}."),))

    diagnostic = phase3_tinker.recoverable_delegate_span(candidate, view)

    assert diagnostic["recoverable"] is True
    assert diagnostic["strict_span_failure"] is True
    assert diagnostic["action_repaired_or_normalized"] is False
    assert diagnostic["all_other_license_rules_pass"] is True
    assert diagnostic["declared_excess_boundary_only"] is True


@pytest.mark.parametrize(
    ("candidate", "view", "reason"),
    [
        (
            _boundary_only_delegate_candidate(query="different query"),
            LicenseView(
                events=(SnapshotView("e_000012", "Lookup Renwick Landing crate mark."),)
            ),
            "fact_text_equals_query",
        ),
        (
            _boundary_only_delegate_candidate(),
            LicenseView(
                events=(
                    SnapshotView(
                        "e_000012",
                        "Renwick Landing crate mark / Renwick Landing crate mark",
                    ),
                )
            ),
            "unique_exact_text_in_referenced_event",
        ),
        (
            _boundary_only_delegate_candidate(),
            LicenseView(
                events=(SnapshotView("e_000012", "Lookup Renwick Landing crate mark."),),
                pending_tool_requests=(
                    PendingToolRequestView.from_args(
                        "r_000001",
                        "e_000012",
                        ToolName.LOOKUP,
                        {"query": "Renwick Landing crate mark"},
                    ),
                ),
            ),
            "all_other_license_rules_pass",
        ),
    ],
)
def test_recoverable_delegate_span_rejects_near_misses(
    candidate: dict[str, object], view: LicenseView, reason: str
) -> None:
    diagnostic = phase3_tinker.recoverable_delegate_span(candidate, view)

    assert diagnostic["recoverable"] is False
    assert diagnostic[reason] is False


def test_gradient_evidence_accepts_only_actual_v3_optimizer_metric_and_zero() -> None:
    expected = {"optimizer.unclipped_grad_l2:mean": 0.25}
    assert phase3_tinker._finite_gradient_evidence(
        {
            "forward_backward": {"unclipped_grad_l2:mean": 99.0},
            "optimizer": {"unclipped_grad_l2:mean": 0.25},
        },
        zero_permitted_pending_causal_pair_proof=False,
    ) == expected
    assert phase3_tinker._finite_gradient_evidence(
        {"optimizer": {"unclipped_grad_l2:mean": 0.0}},
        zero_permitted_pending_causal_pair_proof=True,
    ) == {"optimizer.unclipped_grad_l2:mean": 0.0}


def test_step_1_zero_gradient_requires_a_later_causal_pair_update() -> None:
    gradient = {"optimizer.unclipped_grad_l2:mean": 0.0}
    phase3_tinker._verify_step_1_zero_gradient_parameter_update(
        gradient,
        {"changed_after_step_1_and_optimizer_resume": True},
    )
    with pytest.raises(Phase3TinkerError, match="zero gradient lacks"):
        phase3_tinker._verify_step_1_zero_gradient_parameter_update(
            gradient,
            {"changed_after_step_1_and_optimizer_resume": False},
        )
    unchanged_step_1 = {
        "rows": [{"logprobs_sha256": f"sha256:step-1-{index}"} for index in range(14)]
    }
    unchanged_step_2 = {
        "rows": [
            {"logprobs_sha256": "sha256:step-1-10"},
            {"logprobs_sha256": "sha256:step-1-11"},
            {"logprobs_sha256": "sha256:other"},
        ]
    }
    with pytest.raises(Phase3TinkerError, match="causal-pair logprobs did not change"):
        phase3_tinker._parameter_update_evidence(unchanged_step_1, unchanged_step_2)


def test_step_2_zero_gradient_fails_without_a_post_update_observation() -> None:
    with pytest.raises(phase3_tinker._NumericalCanaryError, match="post-update observation"):
        phase3_tinker._finite_gradient_evidence(
            {"optimizer": {"unclipped_grad_l2:mean": 0.0}},
            zero_permitted_pending_causal_pair_proof=False,
        )


def test_gradient_evidence_rejects_wrong_provenance_and_lookalikes() -> None:
    with pytest.raises(phase3_tinker._NumericalCanaryError, match="no exact") as missing:
        phase3_tinker._finite_gradient_evidence(
            {"optimizer": {}}, zero_permitted_pending_causal_pair_proof=False
        )
    assert missing.value.diagnostic["observed_metric_values"] == [
        {"metrics": [], "provenance": "optimizer"}
    ]
    with pytest.raises(phase3_tinker._NumericalCanaryError) as wrong_provenance:
        phase3_tinker._finite_gradient_evidence(
            {
                "forward_backward": {"unclipped_grad_l2:mean": 0.25},
                "optimizer": {"grad_norm": 0.25},
            },
            zero_permitted_pending_causal_pair_proof=False,
        )
    assert wrong_provenance.value.diagnostic["required_metric_path"] == (
        "optimizer.unclipped_grad_l2:mean"
    )
    assert wrong_provenance.value.diagnostic["observed_metric_values"] == [
        {
            "metrics": [
                {
                    "key": "unclipped_grad_l2:mean",
                    "value": {"classification": "finite", "value": 0.25},
                }
            ],
            "provenance": "forward_backward",
        },
        {
            "metrics": [
                {
                    "key": "grad_norm",
                    "value": {"classification": "finite", "value": 0.25},
                }
            ],
            "provenance": "optimizer",
        },
    ]
    for key in ("grad_norm", "unclipped_grad_l2", "unclipped_grad_l2:mean:alias"):
        with pytest.raises(phase3_tinker._NumericalCanaryError, match="no exact"):
            phase3_tinker._finite_gradient_evidence(
                {"optimizer": {key: 0.25}},
                zero_permitted_pending_causal_pair_proof=False,
            )


@pytest.mark.parametrize(
    ("value", "message", "safe_value"),
    [
        (-0.25, "negative", {"classification": "finite", "value": -0.25}),
        (float("nan"), "non-finite", {"classification": "nan"}),
        (True, "not a numeric", {"classification": "invalid_type", "type": "bool"}),
    ],
)
def test_gradient_evidence_persists_safe_rejected_value_diagnostic(
    value: object, message: str, safe_value: dict[str, object]
) -> None:
    with pytest.raises(phase3_tinker._NumericalCanaryError, match=message) as error:
        phase3_tinker._finite_gradient_evidence(
            {"optimizer": {"unclipped_grad_l2:mean": value}},
            zero_permitted_pending_causal_pair_proof=False,
        )
    assert error.value.diagnostic["accepted_metric_value"] == safe_value
    assert error.value.diagnostic["observed_metric_values"] == [
        {
            "metrics": [
                {"key": "unclipped_grad_l2:mean", "value": safe_value},
            ],
            "provenance": "optimizer",
        }
    ]
