from __future__ import annotations

import asyncio
import json
import plistlib
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from im.training.phase3r_rank16_lr5e5_run import (
    EXPECTED_CANDIDATE_SUMS,
    EXPECTED_DETECTOR_SUMS,
    MAX_STEP,
    MAXIMUM_SPEND_USD,
    PREDECESSOR_RUN_SUMS,
    SAMPLER_BYTES_EACH,
    STATE_BYTES_EACH,
    LR5E5RunError,
    StorageLedger,
    _digest,
    _next_batch_membership,
    capture_logs,
    execute,
    learning_rate,
    load_contract,
    pause_decision,
    prepare_execution,
    verify_provider_tokenizer_equivalence,
    write_pause_control,
)

ROOT = Path(__file__).resolve().parents[1]


def test_v2_contract_is_checksum_bound_and_is_only_lr_change() -> None:
    contract = load_contract(ROOT)
    assert (
        _digest(
            (ROOT / "review/phase3/wp3r-8-rank16-lr5e5-step40-candidate-v2/SHA256SUMS").read_bytes()
        )
        == EXPECTED_CANDIDATE_SUMS
    )
    assert contract.raw["optimizer"]["peak_learning_rate"] == 5e-5
    assert contract.raw["schedule"]["maximum_global_step"] == MAX_STEP
    assert contract.cost["proposed_ceiling_usd"] == MAXIMUM_SPEND_USD
    assert contract.raw["sealed_test"]["status"] == "unread"
    assert contract.approval["decision"] == "approved"
    assert contract.approval["authorization"]["paid_execution"] is False


def test_exact_lr_schedule_has_warmup_ten_and_horizon_126() -> None:
    assert learning_rate(1) == pytest.approx(5e-6)
    assert learning_rate(10) == pytest.approx(5e-5)
    assert learning_rate(40) == pytest.approx(4.2192486471335585e-5)
    assert learning_rate(126) == pytest.approx(0.0)
    with pytest.raises(LR5E5RunError):
        learning_rate(127)


def test_single_signal_pauses_but_hard_abort_has_precedence() -> None:
    assert pause_decision(
        {
            "abort_optimizer": False,
            "high_confidence_generation_loop_count": 1,
            "new_length_termination_count": 0,
        },
        25,
    ) == (False, True)


def test_step40_pause_binds_the_real_step41_batch() -> None:
    contract = load_contract(ROOT)
    assert _next_batch_membership(contract, 41) == contract.rank16.batches[40].membership_sha256
    assert pause_decision(
        {
            "abort_optimizer": True,
            "high_confidence_generation_loop_count": 2,
            "new_length_termination_count": 0,
        },
        25,
    ) == (True, False)
    assert pause_decision(
        {
            "abort_optimizer": False,
            "high_confidence_generation_loop_count": 0,
            "new_length_termination_count": 0,
        },
        40,
    ) == (False, True)


def test_pause_control_is_atomic_json_with_required_handoff_fields(tmp_path: Path) -> None:
    required = {
        "logical_run_id": "run",
        "provider_lineage": {},
        "completed_global_step": 10,
        "next_global_step": 11,
        "next_batch_membership_sha256": "sha256:batch",
        "optimizer_state_path": "state",
        "optimizer_state_identity": "sha256:state",
        "scheduler_position": 10,
        "expected_next_step_learning_rate": learning_rate(11),
        "training_seed": 20260801,
        "data_order_identity": "sha256:order",
        "checkpoint_created_at": 1,
        "checkpoint_expires_at": 2,
        "checkpoint_remaining_ttl_seconds": 3,
        "cumulative_train_token_count": 4,
        "cumulative_spend_usd": 5.0,
    }
    path = tmp_path / "pause.json"
    assert write_pause_control(path, required) == _digest(path.read_bytes())
    assert json.loads(path.read_bytes()) == required
    assert not list(tmp_path.glob(".pause.json.*"))


def test_storage_envelope_permits_only_three_states_and_six_sampler_exports() -> None:
    ledger = StorageLedger()
    for _ in range(3):
        assert ledger.add_state(STATE_BYTES_EACH) == STATE_BYTES_EACH
    with pytest.raises(LR5E5RunError):
        ledger.add_state(STATE_BYTES_EACH)
    for _ in range(6):
        assert ledger.add_sampler(SAMPLER_BYTES_EACH) == SAMPLER_BYTES_EACH
    with pytest.raises(LR5E5RunError):
        ledger.add_sampler(SAMPLER_BYTES_EACH)


def test_provider_tokenizer_requires_exact_pretokenized_id_namespace_equivalence() -> None:
    class Backend:
        def __init__(self, raw: str) -> None:
            self.raw = raw

        def to_str(self) -> str:
            return self.raw

    class Tokenizer:
        def __init__(self, backend: str, *, changed_vocab: bool = False) -> None:
            self.backend_tokenizer = Backend(backend)
            self.all_special_ids = [1, 2]
            self.chat_template = "template"
            self.eos_token_id = 2
            self.pad_token_id = 1
            self.special_tokens_map = {"eos_token": "<eos>", "pad_token": "<pad>"}

            self._vocab = {f"token-{index}": index for index in range(248_077)}
            if changed_vocab:
                self._vocab["token-0"], self._vocab["token-1"] = 1, 0

        def get_vocab(self) -> dict[str, int]:
            return self._vocab

    evidence = verify_provider_tokenizer_equivalence(Tokenizer("provider"), Tokenizer("local"))
    assert evidence["provider_local_exact_token_id_equivalence"] is True
    assert evidence["backend_serialization_equal"] is False
    with pytest.raises(LR5E5RunError, match="token-ID namespaces are not equivalent"):
        verify_provider_tokenizer_equivalence(
            Tokenizer("provider", changed_vocab=True), Tokenizer("local")
        )


def test_secret_read_failure_is_sealed_before_provider_and_does_not_claim_running(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import im.training.phase3r_rank16_lr5e5_run as runner

    packet = tmp_path / "packet.json"
    authorization = tmp_path / "authorization.json"
    packet.write_text("{}", encoding="utf-8")
    authorization.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(runner, "RUN_OUTPUT", Path("run"))
    monkeypatch.setattr(runner, "EARLY_FAILURE_OUTPUT", Path("early-failure"))
    monkeypatch.setattr(
        runner,
        "_load_execution",
        lambda *_args, **_kwargs: (SimpleNamespace(), {}, {}),
    )
    monkeypatch.setattr(runner, "verify_local_preflight", lambda *_args: {"verified": True})

    def missing_secret(_path: Path) -> str:
        raise LR5E5RunError("missing secret")

    with pytest.raises(LR5E5RunError, match="missing secret"):
        asyncio.run(
            execute(
                root=tmp_path,
                source_commit="a" * 40,
                packet_path=packet,
                authorization_path=authorization,
                output_path=Path("run"),
                secret_reader=missing_secret,
            )
        )
    assert not (tmp_path / "run").exists()
    status = json.loads((tmp_path / "early-failure/status.json").read_bytes())
    assert status["status"] == "failed_pre_provider"
    assert status["failure_stage"] == "authorized_secret_read_before_provider_initialization"
    assert (tmp_path / "early-failure/SHA256SUMS").is_file()
    assert "TINKER_API_KEY" not in runner.os.environ


def test_prepare_emits_detached_launchagent_and_checksum_bound_lineage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import im.training.phase3r_rank16_lr5e5_run as runner

    destination = tmp_path / "packet"
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    seen: list[str] = []
    launch_slot_checks: list[bool] = []

    def source_guard(_root: Path, source_commit: str) -> None:
        seen.append(source_commit)

    monkeypatch.setattr(runner, "EXECUTION_DIRECTORY", destination)
    monkeypatch.setattr(runner, "RUN_OUTPUT", tmp_path / "output")
    monkeypatch.setattr(runner, "_verify_source", source_guard)
    monkeypatch.setattr(
        runner, "_verify_launch_slot_clear", lambda: launch_slot_checks.append(True)
    )
    monkeypatch.setattr(
        runner, "load_contract", lambda _root: SimpleNamespace(raw={"source_commit": "b" * 40})
    )
    monkeypatch.setattr(runner, "verify_local_preflight", lambda _root, _contract: {})
    prepared = prepare_execution(ROOT, head)
    plist = plistlib.loads((prepared / f"{runner.LAUNCHD_LABEL}.plist").read_bytes())
    packet = json.loads((prepared / "execution-packet.json").read_bytes())
    assert prepared == destination
    assert plist["KeepAlive"] is False
    assert plist["RunAtLoad"] is False
    assert seen == [head]
    assert launch_slot_checks == [True]
    assert packet["detector_v3_root_sha256sums_sha256"] == EXPECTED_DETECTOR_SUMS
    assert packet["operations"]["maximum_step"] == 40
    assert packet["predecessor_failed_preflight"]["root_sha256sums_sha256"] == PREDECESSOR_RUN_SUMS
    assert packet["tokenizer_equivalence_rule"] == {
        "backend_wrapper_serialization_is_gating": False,
        "exact_provider_local_token_id_vocabulary_is_gating": True,
        "provider_encoding_or_decoding_used_by_runner": False,
        "scope": "pretokenized_tinker_model_input_and_output_token_ids",
    }
    launch = json.loads((prepared / "launch-plan.json").read_bytes())
    assert launch["capture_logs_argv"][2:4] == ["--mode", "capture-logs"]


def test_capture_logs_binds_external_bytes_after_exit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import im.training.phase3r_rank16_lr5e5_run as runner

    stdout, stderr = tmp_path / "stdout.log", tmp_path / "stderr.log"
    stdout.write_bytes(b"out\n")
    stderr.write_bytes(b"err\n")
    monkeypatch.setattr(runner, "RUN_OUTPUT", Path("run"))
    monkeypatch.setattr(runner, "EARLY_FAILURE_OUTPUT", Path("early-failure"))
    monkeypatch.setattr(runner, "STDOUT_LOG", stdout)
    monkeypatch.setattr(runner, "STDERR_LOG", stderr)
    monkeypatch.setattr(
        runner.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=1, stdout=""),
    )
    result = capture_logs(tmp_path)
    destination = tmp_path / "early-failure/launch"
    assert result["output_directory"] == "early-failure"
    assert (destination / "stdout.log").read_bytes() == b"out\n"
    assert (destination / "stderr.log").read_bytes() == b"err\n"
    assert (tmp_path / "early-failure/SHA256SUMS").is_file()
