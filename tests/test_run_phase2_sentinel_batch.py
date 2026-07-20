from __future__ import annotations

import argparse
import json
import socket
import sys
from decimal import Decimal
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import run_phase2_sentinel_batch as script  # noqa: E402
from scripts.run_phase2_sentinel_batch import _run, _verify_packet, load_plan  # noqa: E402

from im.assets.model import canonical_artifact_bytes  # noqa: E402
from im.probes.harness.batch_api import BatchApiObservation, BatchCreateUncertain  # noqa: E402
from im.probes.harness.cache import HarnessCache  # noqa: E402


@pytest.mark.asyncio
async def test_authorized_sentinel_plan_reproduces_exact_offline_shard(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = ROOT

    def no_network(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("plan-only verification must stay offline")

    monkeypatch.setattr(socket, "create_connection", no_network)
    plan = load_plan(repository)
    await _run(
        argparse.Namespace(
            mode="plan",
            repository=repository,
            approve_live_ceiling_usd=Decimal("0.639536"),
            batch_poll_seconds=600,
            batch_id=None,
            input_sha256=None,
        )
    )

    assert len(plan.shard.items) == 8
    assert plan.shard.estimated_input_tokens == 118_413
    assert plan.shard.input_sha256 == plan.manifest["input_sha256"]
    assert (
        plan.shard.input_jsonl
        == (
            repository / "review/phase2/sentinel-0-executable-v2" / plan.manifest["input_path"]
        ).read_bytes()
    )


def test_packet_verification_rejects_manifest_tampering(tmp_path: Path) -> None:
    source = ROOT / "review/phase2/sentinel-0-executable-v2"
    for relative_path in (
        "SHA256SUMS",
        "REVIEW.md",
        "teacher-input/sentinel-0-executable-v2-shard-000.jsonl",
        "teacher-plan.json",
    ):
        target = tmp_path / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((source / relative_path).read_bytes())
    (tmp_path / "teacher-plan.json").write_text("{}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="teacher-plan.json"):
        _verify_packet(tmp_path)


def _observation(payload: dict[str, object]) -> BatchApiObservation:
    return BatchApiObservation(payload=payload, raw=canonical_artifact_bytes(payload))


class _Gateway:
    def __init__(self, plan, *, status: str = "completed", uncertain: bool = False) -> None:
        self.plan = plan
        self.status = status
        self.uncertain = uncertain
        self.upload_calls = 0
        self.create_calls = 0
        self.retrieve_calls = 0

    async def upload(self, input_jsonl: bytes, filename: str) -> BatchApiObservation:
        assert input_jsonl == self.plan.shard.input_jsonl
        assert filename.endswith(".jsonl")
        self.upload_calls += 1
        return _observation({"id": "file_input"})

    async def create(self, input_file_id: str, metadata: dict[str, str]) -> BatchApiObservation:
        self.create_calls += 1
        if self.uncertain:
            raise TimeoutError("outcome unknown")
        return _observation(
            {
                "endpoint": "/v1/responses",
                "id": "batch_test",
                "input_file_id": input_file_id,
                "metadata": metadata,
                "status": "validating",
            }
        )

    async def retrieve(self, batch_id: str) -> BatchApiObservation:
        self.retrieve_calls += 1
        return _observation(
            {
                "endpoint": "/v1/responses",
                "error_file_id": None,
                "id": batch_id,
                "input_file_id": "file_input",
                "metadata": {
                    "im_input_sha256": self.plan.shard.input_sha256.removeprefix("sha256:"),
                    "im_shard": "0",
                    "im_stage": "s0v2",
                },
                "output_file_id": "file_output" if self.status == "completed" else None,
                "status": self.status,
            }
        )

    async def download(self, file_id: str) -> bytes:
        assert file_id == "file_output"
        return b"".join(
            canonical_artifact_bytes(
                {
                    "custom_id": item.custom_id,
                    "response": {
                        "body": {
                            "output": [
                                {
                                    "content": [
                                        {
                                            "text": canonical_artifact_bytes(
                                                self.plan.targets[item.custom_id]["oracle_action"]
                                            ).decode(),
                                            "type": "output_text",
                                        }
                                    ],
                                    "type": "message",
                                }
                            ],
                            "status": "completed",
                            "usage": {"input_tokens": 11, "output_tokens": 7},
                        },
                        "request_id": f"req_{item.custom_id}",
                        "status_code": 200,
                    },
                }
            )
            + b"\n"
            for item in self.plan.shard.items
        )

    async def aclose(self) -> None:
        return None


def _args(repository: Path, mode: str = "run") -> argparse.Namespace:
    return argparse.Namespace(
        mode=mode,
        repository=repository,
        approve_live_ceiling_usd=Decimal("0.639536"),
        batch_poll_seconds=1,
        batch_id=None,
        input_sha256=None,
    )


@pytest.mark.asyncio
async def test_live_adapter_writes_eight_comparisons_and_resumes_without_resubmit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    plan = load_plan(ROOT)
    gateway = _Gateway(plan)
    monkeypatch.setattr(script, "load_plan", lambda _repository: plan)
    monkeypatch.setattr(script, "OpenAIBatchGateway", lambda **_kwargs: gateway)
    monkeypatch.setenv("OPENAI_API_KEY", "test")

    await _run(_args(tmp_path))
    await _run(_args(tmp_path, "resume"))

    comparison = json.loads(
        (tmp_path / script._EXECUTION / "comparison.json").read_text(encoding="utf-8")
    )
    state = json.loads(
        (tmp_path / script._EXECUTION / "execution-state.json").read_text(encoding="utf-8")
    )
    assert comparison["mandatory_review_count"] == 8
    assert comparison["non_equivalent_count"] == 0
    assert state["api_call_performed"] is True
    assert gateway.upload_calls == gateway.create_calls == gateway.retrieve_calls == 1


@pytest.mark.asyncio
async def test_uncertain_create_requires_adopt_before_resume(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    plan = load_plan(ROOT)
    uncertain_gateway = _Gateway(plan, uncertain=True)
    monkeypatch.setattr(script, "load_plan", lambda _repository: plan)
    monkeypatch.setattr(script, "OpenAIBatchGateway", lambda **_kwargs: uncertain_gateway)
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    with pytest.raises(BatchCreateUncertain):
        await _run(_args(tmp_path))
    with pytest.raises(BatchCreateUncertain):
        await _run(_args(tmp_path, "resume"))
    assert uncertain_gateway.create_calls == 1

    adopt_args = _args(tmp_path, "adopt")
    adopt_args.batch_id = "batch_test"
    adopt_args.input_sha256 = plan.shard.input_sha256
    await _run(adopt_args)
    completed_gateway = _Gateway(plan)
    monkeypatch.setattr(script, "OpenAIBatchGateway", lambda **_kwargs: completed_gateway)
    await _run(_args(tmp_path, "resume"))
    assert completed_gateway.upload_calls == completed_gateway.create_calls == 0
    assert completed_gateway.retrieve_calls == 1


@pytest.mark.asyncio
async def test_terminal_failure_is_preserved_without_comparison(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    plan = load_plan(ROOT)
    gateway = _Gateway(plan, status="failed")
    monkeypatch.setattr(script, "load_plan", lambda _repository: plan)
    monkeypatch.setattr(script, "OpenAIBatchGateway", lambda **_kwargs: gateway)
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    with pytest.raises(RuntimeError, match="terminal status 'failed'"):
        await _run(_args(tmp_path))
    assert not (tmp_path / script._EXECUTION / "comparison.json").exists()
    with HarnessCache(tmp_path / script._EXECUTION / "ledger.sqlite") as cache:
        assert cache.get_batch_job(plan.shard.input_sha256).status == "failed"
