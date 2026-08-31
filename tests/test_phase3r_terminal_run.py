from __future__ import annotations

import asyncio
import os
import struct
from pathlib import Path
from types import SimpleNamespace

import pytest
import tinker

from im.assets.model import canonical_artifact_bytes
from im.training import phase3r_terminal_run as runner
from im.training.phase3_full_run import ReplayBatch, TrainingDatum

ROOT = Path(__file__).parents[1]


class _Future:
    def __init__(self, value: object) -> None:
        self.value = value

    async def result_async(self) -> object:
        return self.value


class _Client:
    def __init__(self) -> None:
        self.forward_calls = 0
        self.states: list[str] = []
        self.samplers: list[str] = []

    async def forward_backward_async(self, data: list[object], _: str) -> _Future:
        self.forward_calls += 1
        outputs = [{"logprobs": tinker.TensorData([-0.5], dtype="float32")} for _ in data]
        return _Future(SimpleNamespace(loss_fn_outputs=outputs))

    async def optim_step_async(self, _: object) -> _Future:
        return _Future(SimpleNamespace(metrics={"unclipped_grad_l2:mean": 0.25}))

    async def save_state_async(self, name: str, ttl_seconds: int | None) -> _Future:
        assert ttl_seconds is None
        self.states.append(name)
        return _Future(SimpleNamespace(path=f"state://{name}"))

    async def save_weights_for_sampler_async(self, name: str, ttl_seconds: int) -> _Future:
        assert ttl_seconds == 3600
        self.samplers.append(name)
        return _Future(SimpleNamespace(path=f"sampler://{name}"))


class _Provider:
    instance: _Provider | None = None

    def __init__(self, *_: object) -> None:
        self.client = _Client()
        self.deleted: list[str] = []
        _Provider.instance = self

    async def initialize(self) -> dict[str, object]:
        return {
            "base_model": "Qwen/Qwen3.6-35B-A3B",
            "is_lora": True,
            "lora_rank": 64,
            "train_attn": True,
            "train_mlp": True,
            "train_unembed": False,
        }

    async def create_training_client(self) -> _Client:
        return self.client

    async def checkpoint_size(self, _: str) -> int:
        return 10_000

    async def delete_checkpoint(self, path: str) -> None:
        self.deleted.append(path)


class _Evaluator:
    def __init__(self, root: Path, output: Path, *_: object) -> None:
        self.root = root
        self.output = output

    async def __call__(self, kind: str, *_: object) -> dict[str, object]:
        return {"kind": kind}


class _OversizeProvider(_Provider):
    async def checkpoint_size(self, _: str) -> int:
        return runner.MAXIMUM_CHECKPOINT_BYTES + 1


def _tiny_contract() -> runner.TerminalRunContract:
    datum = TrainingDatum(
        "interaction:one", "interaction", (1,), (2,), struct.pack("<f", 1.0), 1
    )
    batches = tuple(
        ReplayBatch(step, (datum.datum_id,), (), f"sha256:{step:064x}", "1/1")
        for step in range(1, 11)
    )
    return runner.TerminalRunContract({datum.datum_id: datum}, batches, {})


def test_contract_binds_all_terminal_masks_and_first_ten() -> None:
    contract = runner.load_contract(ROOT)
    assert len(contract.datums) == 3_000
    assert len(contract.batches) == 10
    assert sum(row.kind == "interaction" for row in contract.datums.values()) == 2_000
    assert all(
        row.target_tokens[-1] == 248046
        and struct.unpack(f"<{len(row.target_tokens)}f", row.weights_bytes)[-1] > 0
        for row in contract.datums.values()
    )


def test_frozen_v1_retention_slice_triggers_terminal_ablation_kill_gate() -> None:
    result = runner._retention_gate(
        ROOT / "review/phase3/wp3-4-sft-20260805-v4", step=20
    )
    assert result["passed"] is False
    assert result["counts"]["normal_stop_count"] == 0
    assert result["counts"]["repetition_signature_count"] >= 2


def test_action_json_detection_is_independent_of_key_order() -> None:
    assert runner._interaction_action_json('{"instruction":"x","type":"mark"}<|im_end|>')
    assert not runner._interaction_action_json('{"answer":"ordinary chat"}<|im_end|>')


def test_fast_gate_treats_null_predicted_action_as_a_failed_action(tmp_path: Path) -> None:
    manifest = runner._json(
        ROOT / "review/phase3/wp3-2-offline-candidate-v4/fast-sentinel-manifest.json"
    )
    directory = tmp_path / "evaluations/step-010/fast-dev"
    directory.mkdir(parents=True)
    rows = [
        {
            "executed": {"duplicate_action": False, "hard_failures": [], "match": False},
            "predicted_action": None,
            "state_id": row["state_id"],
            "structural": {"parse_union_valid": False},
        }
        for row in manifest["sentinels"]
    ]
    (directory / "grades.jsonl").write_bytes(
        b"".join(canonical_artifact_bytes(row) + b"\n" for row in rows)
    )
    result = runner._fast_gate(ROOT, tmp_path, runner.load_contract(ROOT))
    assert result["counts"]["active_floor_respond_error_count"] == 0
    assert result["passed"] is False


def test_log_capture_rejects_arbitrary_paths() -> None:
    with pytest.raises(runner.TerminalRunError, match="non-canonical"):
        runner.capture_logs(
            ROOT,
            runner.RUN_OUTPUT,
            ROOT / "review/phase2/interaction-test/forbidden",
            runner.STDERR_LOG,
        )


def test_prepare_emits_only_a_pending_authorization_template(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(runner, "verify_source", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(runner, "load_contract", lambda *_args: _tiny_contract())
    monkeypatch.setattr(runner, "_source_hashes", lambda *_args: {})
    runner.prepare_execution(tmp_path, "0" * 40, Path("packet"))
    packet = tmp_path / "packet"
    assert not (packet / "owner-authorization.json").exists()
    template = runner._json(packet / "owner-authorization-template.json")
    assert template["decision"] == "pending_independent_owner_binding"


def test_log_capture_reseals_the_complete_run(monkeypatch, tmp_path: Path) -> None:
    output_relative = Path("tmp-phase3r-log-capture")
    output = ROOT / output_relative
    output.mkdir()
    (output / "status.json").write_text("{}\n")
    stdout, stderr = tmp_path / "stdout.log", tmp_path / "stderr.log"
    stdout.write_text("out")
    stderr.write_text("err")
    monkeypatch.setattr(runner, "RUN_OUTPUT", output_relative)
    monkeypatch.setattr(runner, "STDOUT_LOG", stdout)
    monkeypatch.setattr(runner, "STDERR_LOG", stderr)
    monkeypatch.setattr(
        runner.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stdout="state = exited"),
    )
    try:
        runner.capture_logs(ROOT, output_relative, stdout, stderr)
        declared = {
            line.split("  ", 1)[1]
            for line in (output / "SHA256SUMS").read_text().splitlines()
        }
        actual = {
            path.relative_to(output).as_posix()
            for path in output.rglob("*")
            if path.is_file() and path != output / "SHA256SUMS"
        }
        assert declared == actual
    finally:
        for path in sorted(output.rglob("*"), reverse=True):
            path.unlink() if path.is_file() else path.rmdir()
        output.rmdir()


def test_preflight_failure_occurs_before_secret_read(monkeypatch, tmp_path: Path) -> None:
    called = False

    def secret(_: Path) -> str:
        nonlocal called
        called = True
        return "secret"

    monkeypatch.setattr(
        runner,
        "_load_execution",
        lambda *_args: (_ for _ in ()).throw(runner.TerminalRunError("blocked")),
    )
    monkeypatch.setattr(runner, "RUN_OUTPUT", Path("tmp-terminal-preflight"))
    try:
        try:
            asyncio.run(
                runner.execute(
                    root=ROOT,
                    source_commit="0" * 40,
                    packet_path=Path("missing"),
                    authorization_path=Path("missing"),
                    output_path=Path("tmp-terminal-preflight"),
                    secret_reader=secret,
                )
            )
        except runner.TerminalRunError:
            pass
        assert called is False
    finally:
        path = ROOT / "tmp-terminal-preflight"
        if path.exists():
            path.rmdir()


def test_fake_execution_runs_ten_steps_and_cleans_only_sampler(monkeypatch, tmp_path: Path) -> None:
    output_relative = Path("tmp-phase3r-terminal-fake")
    output = ROOT / output_relative
    if output.exists():
        raise AssertionError("fake output unexpectedly exists")
    monkeypatch.setattr(runner, "RUN_OUTPUT", output_relative)
    monkeypatch.setattr(runner, "_load_execution", lambda *_args: (_tiny_contract(), {}, {}))
    monkeypatch.setattr(runner, "TinkerRunProvider", _Provider)
    monkeypatch.setattr(runner, "TinkerEvaluator", _Evaluator)
    monkeypatch.setattr(runner, "load_pinned_tokenizer", lambda *_args: object())
    monkeypatch.setattr(runner, "_fast_gate", lambda *_args: {"passed": True})
    monkeypatch.setattr(runner, "_retention_gate", lambda *_args: {"passed": True})
    monkeypatch.setattr(runner, "_directory_sha256sums", lambda *_args: "sha256:" + "a" * 64)
    try:
        result = asyncio.run(
            runner.execute(
                root=ROOT,
                source_commit="0" * 40,
                packet_path=runner.FREEZE_APPROVAL,
                authorization_path=runner.FREEZE_APPROVAL,
                output_path=output_relative,
                secret_reader=lambda _: "test-key",
            )
        )
        provider = _Provider.instance
        assert provider is not None
        assert provider.client.forward_calls == 10
        assert provider.client.states == ["wp3r-terminal-state-10"]
        assert provider.client.samplers == ["wp3r-terminal-sampler-10"]
        assert provider.deleted == ["sampler://wp3r-terminal-sampler-10"]
        assert result["status"] == "passed_stopped_step_10"
        assert (output / "SHA256SUMS").is_file()
        assert "TINKER_API_KEY" not in os.environ
    finally:
        if output.exists():
            for path in sorted(output.rglob("*"), reverse=True):
                path.unlink() if path.is_file() else path.rmdir()
            output.rmdir()


def test_oversized_durable_state_is_deleted_before_failure(monkeypatch) -> None:
    output_relative = Path("tmp-phase3r-terminal-oversize")
    output = ROOT / output_relative
    monkeypatch.setattr(runner, "RUN_OUTPUT", output_relative)
    monkeypatch.setattr(runner, "_load_execution", lambda *_args: (_tiny_contract(), {}, {}))
    monkeypatch.setattr(runner, "TinkerRunProvider", _OversizeProvider)
    try:
        with pytest.raises(runner.TerminalRunError, match="checkpoint byte ceiling"):
            asyncio.run(
                runner.execute(
                    root=ROOT,
                    source_commit="0" * 40,
                    packet_path=runner.FREEZE_APPROVAL,
                    authorization_path=runner.FREEZE_APPROVAL,
                    output_path=output_relative,
                    secret_reader=lambda _: "test-key",
                )
            )
        provider = _Provider.instance
        assert provider is not None
        assert provider.deleted == ["state://wp3r-terminal-state-10"]
    finally:
        if output.exists():
            for path in sorted(output.rglob("*"), reverse=True):
                path.unlink() if path.is_file() else path.rmdir()
            output.rmdir()
