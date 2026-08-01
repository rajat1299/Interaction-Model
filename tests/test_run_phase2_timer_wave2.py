from __future__ import annotations

import argparse
import json
import socket
import sys
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import run_phase2_timer_wave2 as script  # noqa: E402

from im.assets.model import canonical_artifact_bytes  # noqa: E402
from im.config import estimate_tokens  # noqa: E402
from im.probes.harness.batch import BatchDecoder, BatchShard, BatchWorkItem  # noqa: E402
from im.probes.harness.batch_api import BatchApiObservation  # noqa: E402
from im.probes.harness.identity import cache_identity, digest  # noqa: E402
from im.probes.harness.models import HarnessProtocol  # noqa: E402

_CEILING = Decimal("57.246605")


@dataclass(frozen=True)
class _Packet:
    files: dict[str, bytes]
    items: tuple[BatchWorkItem, ...]
    shards: tuple[BatchShard, ...]


def _observation(payload: dict[str, object]) -> BatchApiObservation:
    return BatchApiObservation(payload=payload, raw=canonical_artifact_bytes(payload))


def _packet() -> _Packet:
    items, targets = [], []
    for index in range(698):
        custom_id = f"t2w2.stream-{index // 14:02d}.d{index:03}.a1"
        body = {
            "input": f"Wave-2 decision {index}",
            "max_output_tokens": 8192,
            "model": "gpt-5.6-terra",
            "reasoning": {"effort": "high"},
        }
        identity = cache_identity(
            manifest_sha256="sha256:" + "1" * 64,
            probe_id=custom_id,
            protocol=HarnessProtocol.GENERATION,
            variant_id="timer-wave-2",
            presentation=f"policy-{index}",
            model="gpt-5.6-terra",
            reasoning_effort="high",
            prompt_hash=script._PROMPT_V3_SHA256,
            request_bytes=canonical_artifact_bytes(body),
        )
        items.append(
            BatchWorkItem(
                custom_id=custom_id,
                identity=identity,
                body=body,
                prompt_hash=script._PROMPT_V3_SHA256,
                decoder=BatchDecoder.ACTION,
            )
        )
        oracle = (
            {"fire_event_id": "e_000001", "type": "nudge"}
            if index == 1
            else {"reason": "no_trigger", "related_event_id": None, "type": "idle"}
        )
        targets.append(
            {
                "candidate_selected_program_action_indices": [index],
                "custom_id": custom_id,
                "d13": {
                    "label_origin": None,
                    "pending_origin": "teacher_outcome_then_d2_review",
                    "review_batch_id": None,
                    "trust_matrix_version": "phase2-trust-v1",
                },
                "oracle_action": oracle,
                "program_action_index": index,
                "prompt_hash": script._PROMPT_V3_SHA256,
                "request_body_sha256": digest(canonical_artifact_bytes(body)),
                "static_d2_route": {
                    "add_review_if": [
                        "teacher_low_confidence",
                        "teacher_oracle_disagreement",
                    ],
                    "mandatory_review": index == 0,
                    "reasons": ["rollover_or_checkpoint_projection"] if index == 0 else [],
                    "review_required": index == 0,
                    "sample_rate": 0.1,
                },
            }
        )
    item_tuple = tuple(items)
    shards = []
    start = 0
    for shard_index, size in enumerate((42, *(41 for _ in range(16)))):
        shard_items = item_tuple[start : start + size]
        input_jsonl = b"".join(item.request_line for item in shard_items)
        shards.append(
            BatchShard(
                stage="t2w2",
                shard_index=shard_index,
                items=shard_items,
                input_jsonl=input_jsonl,
                estimated_input_tokens=sum(
                    estimate_tokens(item.request_bytes) for item in shard_items
                ),
                input_sha256=digest(input_jsonl),
            )
        )
        start += size
    manifest = {
        "candidate_decision_count": 698,
        "cost_estimate": {"approval_ceiling_usd": format(_CEILING, "f")},
        "format_version": 1,
        "kind": "phase2-timer-wave2-teacher-plan",
        "max_enqueued_tokens": 700_000,
        "max_output_tokens_per_request": 8192,
        "model": "gpt-5.6-terra",
        "prompt_bindings": {
            "runtime_prompt_hashes": [script._PROMPT_V3_SHA256],
            "teacher_prompt_hash": script._PROMPT_V3_SHA256,
        },
        "reasoning_effort": "high",
        "request_count": 698,
        "shard_count": 17,
        "shards": [
            {
                "estimated_input_tokens": shard.estimated_input_tokens,
                "input_path": f"teacher-input/shard-{shard.shard_index:03}.jsonl",
                "input_sha256": shard.input_sha256,
                "request_count": len(shard.items),
                "shard_index": shard.shard_index,
                "stage": "t2w2",
            }
            for shard in shards
        ],
        "stage": "t2w2",
        "targets": targets,
    }
    files = {"teacher-plan.json": canonical_artifact_bytes(manifest)}
    files.update(
        {
            f"teacher-input/shard-{shard.shard_index:03}.jsonl": shard.input_jsonl
            for shard in shards
        }
    )
    files["SHA256SUMS"] = "".join(
        f"{digest(data).removeprefix('sha256:')}  {path}\n"
        for path, data in sorted(files.items())
    ).encode()
    return _Packet(files=files, items=item_tuple, shards=tuple(shards))


def _materialize(repository: Path, packet: _Packet) -> None:
    for relative_path, data in packet.files.items():
        path = repository / script._PACKET / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


def _install_packet(monkeypatch: pytest.MonkeyPatch, packet: _Packet, repository: Path) -> None:
    _materialize(repository, packet)

    async def builder(_repository: Path) -> _Packet:
        return packet

    monkeypatch.setattr(script, "_build_packet", builder)


def _args(repository: Path, mode: str = "run") -> argparse.Namespace:
    return argparse.Namespace(
        mode=mode,
        repository=repository,
        approve_live_ceiling_usd=_CEILING,
        batch_max_enqueued_tokens=700_000,
        batch_poll_seconds=1,
        batch_id=None,
        input_sha256=None,
    )


class _Gateway:
    def __init__(self, packet: _Packet, *, mismatch_custom_id: str | None = None) -> None:
        self.shards = {shard.input_jsonl: shard for shard in packet.shards}
        manifest = json.loads(packet.files["teacher-plan.json"])
        self.actions = {
            target["custom_id"]: target["oracle_action"] for target in manifest["targets"]
        }
        self.mismatch_custom_id = mismatch_custom_id
        self.upload_calls = self.create_calls = self.retrieve_calls = 0

    async def upload(self, input_jsonl: bytes, _filename: str) -> BatchApiObservation:
        shard = self.shards[input_jsonl]
        self.upload_calls += 1
        return _observation({"id": f"input_{shard.shard_index}"})

    async def create(self, input_file_id: str, metadata: dict[str, str]) -> BatchApiObservation:
        index = int(input_file_id.removeprefix("input_"))
        shard = next(shard for shard in self.shards.values() if shard.shard_index == index)
        assert metadata == {
            "im_input_sha256": shard.input_sha256.removeprefix("sha256:"),
            "im_shard": str(index),
            "im_stage": "t2w2",
        }
        self.create_calls += 1
        return _observation(
            {
                "endpoint": "/v1/responses",
                "id": f"batch_{index}",
                "input_file_id": input_file_id,
                "metadata": metadata,
                "status": "validating",
            }
        )

    async def retrieve(self, batch_id: str) -> BatchApiObservation:
        index = int(batch_id.removeprefix("batch_"))
        shard = next(shard for shard in self.shards.values() if shard.shard_index == index)
        self.retrieve_calls += 1
        return _observation(
            {
                "endpoint": "/v1/responses",
                "error_file_id": None,
                "id": batch_id,
                "input_file_id": f"input_{index}",
                "metadata": {
                    "im_input_sha256": shard.input_sha256.removeprefix("sha256:"),
                    "im_shard": str(index),
                    "im_stage": "t2w2",
                },
                "output_file_id": f"output_{index}",
                "status": "completed",
            }
        )

    async def download(self, file_id: str) -> bytes:
        index = int(file_id.removeprefix("output_"))
        shard = next(shard for shard in self.shards.values() if shard.shard_index == index)
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
                                                {"fire_event_id": "e_000001", "type": "nudge"}
                                                if item.custom_id == self.mismatch_custom_id
                                                else self.actions[item.custom_id]
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
            for item in shard.items
        )

    async def aclose(self) -> None:
        return None


@pytest.mark.asyncio
async def test_plan_is_offline_and_requires_the_sealed_698_request_packet(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    packet = _packet()
    _install_packet(monkeypatch, packet, tmp_path)
    monkeypatch.setattr(
        socket,
        "create_connection",
        lambda *_args, **_kwargs: pytest.fail("plan must stay offline"),
    )

    loaded = await script.load_plan(tmp_path)
    await script._run(_args(tmp_path, "plan"))

    assert len(loaded.items) == 698
    assert [len(shard.items) for shard in loaded.shards] == [42, *(41 for _ in range(16))]


@pytest.mark.asyncio
async def test_execution_resumes_all_signed_shards_and_writes_usage_comparison(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    packet = _packet()
    gateway = _Gateway(packet, mismatch_custom_id=packet.items[2].custom_id)
    _install_packet(monkeypatch, packet, tmp_path)
    monkeypatch.setattr(script, "OpenAIBatchGateway", lambda **_kwargs: gateway)
    monkeypatch.setenv("OPENAI_API_KEY", "test")

    await script._run(_args(tmp_path))
    await script._run(_args(tmp_path, "resume"))

    execution = tmp_path / script._EXECUTION
    comparison = json.loads((execution / "comparison.json").read_text())
    assert comparison["request_count"] == 698
    assert comparison["non_equivalent_count"] == 1
    assert comparison["actual_usage"] == {
        "cache_write_tokens": 0,
        "cached_input_tokens": 0,
        "input_tokens": 698 * 11,
        "output_tokens": 698 * 7,
        "reasoning_tokens": 0,
    }
    assert gateway.upload_calls == gateway.create_calls == gateway.retrieve_calls == 17
    assert comparison["rows"][0]["review_reasons"] == ["rollover_or_checkpoint_projection"]
    assert comparison["rows"][2]["equivalence"] is False
    assert comparison["rows"][2]["review_reasons"] == ["teacher_oracle_disagreement"]
    assert (execution / "ledger.sqlite").is_file()
    assert (execution / "shards/0016/output.jsonl").is_file()
    assert (execution / "shards/0000/comparison.json").is_file()


@pytest.mark.asyncio
async def test_tampering_or_inexact_operator_approval_is_rejected(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    packet = _packet()
    _install_packet(monkeypatch, packet, tmp_path)
    checksum = tmp_path / script._PACKET / "SHA256SUMS"
    checksum.write_bytes(b"0" * 64 + b"  teacher-plan.json\n")
    with pytest.raises(script.TimerWave2RunError, match="packet member changed"):
        script._verify_packet(tmp_path / script._PACKET)
    _materialize(tmp_path, packet)

    wrong_tokens = _args(tmp_path)
    wrong_tokens.batch_max_enqueued_tokens = 1
    with pytest.raises(script.TimerWave2RunError, match="signed 700000-token"):
        await script._run(wrong_tokens)

    wrong_ceiling = _args(tmp_path)
    wrong_ceiling.approve_live_ceiling_usd = Decimal("57.246604")
    with pytest.raises(script.TimerWave2RunError, match="exactly 57.246605"):
        await script._run(wrong_ceiling)
