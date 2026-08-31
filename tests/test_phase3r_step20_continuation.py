from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace

import pytest

from im.training import phase3r_step20_continuation as runner

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_phase3r_step20_continuation.py"
SPEC = importlib.util.spec_from_file_location("step20_builder", SCRIPT)
assert SPEC and SPEC.loader
builder = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = builder
SPEC.loader.exec_module(builder)


def test_builder_binds_exact_window_and_v3_lineage(tmp_path: Path) -> None:
    files, contract = builder._candidate_files(ROOT, "0" * 40)
    builder.publish_directory_transaction(tmp_path / "candidate", files)
    assert [row["global_step"] for row in contract["steps"]] == list(range(21, 31))
    assert contract["resume"]["next_global_step"] == 21
    assert contract["resume"]["next_learning_rate"] == pytest.approx(0.00009779760713358059)
    assert contract["evaluations"] == {
        "retention_steps": [25, 30],
        "full_dev_steps": [30],
        "retention_count": 12,
        "full_dev_count": 300,
    }
    assert contract["stops"]["automatic_step_31"] is False
    assert contract["source_commit"] == "0" * 40
    frozen = json.loads((ROOT / runner.CANDIDATE / "continuation-contract.json").read_bytes())
    assert frozen["source_commit"] == runner.CONTRACT_SOURCE_COMMIT
    assert contract["evaluation_sequence"][1:] == [
        {
            "on_abort": "stop_without_full_dev",
            "operation": "automatic_retention_12_then_detector_v3",
            "step": 30,
        },
        {
            "condition": "step_30_detector_v3_abort_optimizer_is_false",
            "operation": "full_dev_300",
            "step": 30,
        },
    ]
    cost = json.loads((tmp_path / "candidate/cost-model.json").read_bytes())
    assert cost["ceiling_usd"] == 15
    assert cost["token_counts"] == {
        "evaluation_input_tokens": 4_453_030,
        "evaluation_max_output_tokens": 331_776,
        "training_tokens": 4_991_552,
    }
    assert cost["modeled_upper_usd"] < 10


def test_continuation_v3_requires_all_raw_outputs(tmp_path: Path) -> None:
    directory = tmp_path / "evaluations/step-025/automatic-retention-12/raw"
    directory.mkdir(parents=True)
    with pytest.raises(runner.ContinuationError, match="all 12"):
        runner._retention_v3(tmp_path, 25)


def test_v3_stylistic_repetition_does_not_abort(tmp_path: Path) -> None:
    raw = tmp_path / "evaluations/step-025/automatic-retention-12/raw"
    report_rows = []
    for index in range(12):
        path = raw / str(index)
        path.mkdir(parents=True)
        repeated = [index + 1] * 16
        tokens = (
            repeated
            + list(range(100 + index * 100, 140 + index * 100))
            + repeated
            + list(range(200 + index * 100, 240 + index * 100))
            + repeated
        )
        record = path / "raw-generation.json"
        record.write_text(
            json.dumps(
                {
                    "state_id": str(index),
                    "output_token_ids": tokens,
                    "decoded_utf8": "ordinary text",
                    "finish_reason": "stop",
                }
            )
        )
        signature = runner.repeated_ngram_signature(tokens)
        report_rows.append(
            {
                "catastrophe_detector": {
                    "empty_output": False,
                    "high_confidence_refusal": False,
                    "interaction_protocol_imitation": False,
                    "new_length_termination": False,
                    "repetition_signature": signature,
                },
                "raw_record_sha256": runner._digest(record.read_bytes()),
                "request_id": str(index),
            }
        )
    report = raw.parent / "report.json"
    report.write_text(json.dumps({"rows": report_rows}))
    result = runner._retention_v3(tmp_path, 25)
    assert result["raw_record_count"] == 12
    assert result["detector_v3"]["abort_optimizer"] is False


def test_invalid_authorization_fails_before_secret_or_provider(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    execution = Path("execution")
    directory = tmp_path / execution
    directory.mkdir()
    packet = {
        "kind": "phase3r-step20-continuation-execution-packet-v1",
        "source_commit": "0" * 40,
    }
    (directory / "execution-packet.json").write_text(json.dumps(packet))
    auth = directory / "owner-authorization.json"
    auth.write_text(json.dumps({"decision": "pending_owner_binding"}))
    monkeypatch.setattr(runner, "EXECUTION", execution)
    monkeypatch.setattr(runner, "_verify_source", lambda *_args: None)
    monkeypatch.setattr(runner, "_sums", lambda *_args, **_kwargs: None)
    touched = {"secret": False, "provider": False}

    def secret_reader(_path: Path) -> str:
        touched["secret"] = True
        raise AssertionError("secret must remain unread")

    def provider_factory(*_args: object, **_kwargs: object) -> object:
        touched["provider"] = True
        raise AssertionError("provider must remain untouched")

    with pytest.raises(runner.ContinuationError, match="owner authorization"):
        asyncio.run(
            runner.execute(
                root=tmp_path,
                source_commit="0" * 40,
                authorization_path=auth,
                secret_reader=secret_reader,
                service_factory=provider_factory,
            )
        )
    assert touched == {"secret": False, "provider": False}


def test_execution_checksum_allows_only_the_separate_owner_sidecar(tmp_path: Path) -> None:
    packet = tmp_path / "execution-packet.json"
    packet.write_bytes(b"packet")
    (tmp_path / "SHA256SUMS").write_text(
        f"{sha256(packet.read_bytes()).hexdigest()}  execution-packet.json\n"
    )
    (tmp_path / "owner-authorization.json").write_bytes(b"authorization")
    runner._sums(tmp_path, allowed_extras=frozenset({"owner-authorization.json"}))
    (tmp_path / "unexpected.json").write_bytes(b"unexpected")
    with pytest.raises(runner.ContinuationError, match="inventory"):
        runner._sums(tmp_path, allowed_extras=frozenset({"owner-authorization.json"}))


def test_catastrophe_skips_full_dev_and_state_lifetime_fails_closed() -> None:
    assert runner._full_dev_allowed(30, {"detector_v3": {"abort_optimizer": True}}) is False
    assert runner._full_dev_allowed(30, {"detector_v3": {"abort_optimizer": False}}) is True
    assert runner._checkpoint_lifetime_valid(
        3_305_164_149,
        {"checkpoint_is_durable": False, "remaining_ttl_seconds": 691_200},
        minimum_ttl_seconds=691_200,
    )
    assert not runner._checkpoint_lifetime_valid(
        3_305_164_149,
        {"checkpoint_is_durable": False, "remaining_ttl_seconds": 691_199},
        minimum_ttl_seconds=691_200,
    )


def test_early_failure_logs_receive_a_root_seal(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    stdout = tmp_path / "stdout.external"
    stderr = tmp_path / "stderr.external"
    stdout.write_bytes(b"out")
    stderr.write_bytes(b"err")
    monkeypatch.setattr(runner, "STDOUT_LOG", stdout)
    monkeypatch.setattr(runner, "STDERR_LOG", stderr)
    monkeypatch.setattr(runner, "OUTPUT", Path("normal-output"))
    monkeypatch.setattr(runner, "FAILURE_OUTPUT", Path("early-failure"))
    monkeypatch.setattr(
        runner.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=1, stdout=""),
    )

    evidence = runner.capture_logs(tmp_path)

    assert evidence["destination"] == "early-failure/launch"
    assert (tmp_path / "early-failure/SHA256SUMS").is_file()
    runner._sums(tmp_path / "early-failure")
