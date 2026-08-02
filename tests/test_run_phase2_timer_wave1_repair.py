from __future__ import annotations

# ruff: noqa: E501
import argparse
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import run_phase2_timer_wave1_repair as script  # noqa: E402

from im.assets.model import canonical_artifact_bytes  # noqa: E402
from im.generation.phase2_timer_wave1_repair import build_timer_wave1_repair_plan  # noqa: E402
from im.probes.harness.batch_api import BatchApiObservation  # noqa: E402


def _observation(payload: dict[str, object]) -> BatchApiObservation:
    return BatchApiObservation(payload=payload, raw=canonical_artifact_bytes(payload))


def _materialize(repository: Path, files: dict[str, bytes]) -> None:
    for relative_path, content in files.items():
        path = repository / script._PACKET / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)


class _Gateway:
    def __init__(self, plan) -> None:
        self.shard = plan.shards[0]
        self.actions = {
            target["custom_id"]: target["oracle_action"]
            for target in json.loads(plan.files["teacher-plan.json"])["targets"]
        }
        self.upload_calls = self.create_calls = self.retrieve_calls = 0

    async def upload(self, input_jsonl: bytes, _filename: str) -> BatchApiObservation:
        assert input_jsonl == self.shard.input_jsonl
        self.upload_calls += 1
        return _observation({"id": "input_repair"})

    async def create(self, input_file_id: str, metadata: dict[str, str]) -> BatchApiObservation:
        assert input_file_id == "input_repair"
        assert metadata == {
            "im_input_sha256": self.shard.input_sha256.removeprefix("sha256:"),
            "im_shard": "0",
            "im_stage": "t2w1r",
        }
        self.create_calls += 1
        return _observation(
            {
                "endpoint": "/v1/responses",
                "id": "batch_repair",
                "input_file_id": input_file_id,
                "metadata": metadata,
                "status": "validating",
            }
        )

    async def retrieve(self, batch_id: str) -> BatchApiObservation:
        assert batch_id == "batch_repair"
        self.retrieve_calls += 1
        return _observation(
            {
                "endpoint": "/v1/responses",
                "id": batch_id,
                "input_file_id": "input_repair",
                "metadata": {
                    "im_input_sha256": self.shard.input_sha256.removeprefix("sha256:"),
                    "im_shard": "0",
                    "im_stage": "t2w1r",
                },
                "output_file_id": "output_repair",
                "error_file_id": None,
                "status": "completed",
            }
        )

    async def download(self, file_id: str) -> bytes:
        assert file_id == "output_repair"
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
                                                self.actions[item.custom_id]
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
            for item in self.shard.items
        )

    async def aclose(self) -> None:
        return None


def _args(repository: Path, ceiling, mode: str = "run") -> argparse.Namespace:
    return argparse.Namespace(
        mode=mode,
        repository=repository,
        approve_live_ceiling_usd=ceiling,
        batch_poll_seconds=1,
        batch_id=None,
        input_sha256=None,
    )


@pytest.mark.asyncio
async def test_repair_runner_keeps_the_ten_request_packet_detached_and_resumable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    generated = await build_timer_wave1_repair_plan(repository_root=ROOT)
    _materialize(tmp_path, generated.files)

    async def planner(_repository: Path):
        return generated

    monkeypatch.setattr(script, "_build_plan", planner)
    loaded = await script.load_plan(tmp_path)
    assert len(loaded.items) == 10
    assert len(loaded.shards) == 1
    await script._run(_args(tmp_path, loaded.approval_ceiling_usd, "plan"))

    gateway = _Gateway(generated)
    monkeypatch.setattr(script, "OpenAIBatchGateway", lambda **_kwargs: gateway)
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    await script._run(_args(tmp_path, loaded.approval_ceiling_usd))
    await script._run(_args(tmp_path, loaded.approval_ceiling_usd, "resume"))

    comparison = json.loads((tmp_path / script._EXECUTION / "comparison.json").read_text())
    assert comparison["request_count"] == 10
    assert comparison["non_equivalent_count"] == 0
    assert gateway.upload_calls == gateway.create_calls == gateway.retrieve_calls == 1
