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

from scripts import run_phase2_timer_wave1 as script  # noqa: E402
from scripts.run_phase2_timer_wave1 import (  # noqa: E402
    TimerWave1RunError,
    _run,
    _validate_plan,
    _verify_packet,
    load_plan,
)

from im.assets.model import canonical_artifact_bytes  # noqa: E402
from im.config import estimate_tokens  # noqa: E402
from im.probes.harness.batch import BatchDecoder, BatchShard, BatchWorkItem  # noqa: E402
from im.probes.harness.batch_api import BatchApiObservation  # noqa: E402
from im.probes.harness.identity import cache_identity, digest  # noqa: E402
from im.probes.harness.models import HarnessProtocol  # noqa: E402

_CEILING = Decimal("1.234500")


@dataclass(frozen=True)
class _PlannerResult:
    files: dict[str, bytes]
    items: tuple[BatchWorkItem, ...]
    shards: tuple[BatchShard, ...]


def _observation(payload: dict[str, object]) -> BatchApiObservation:
    return BatchApiObservation(payload=payload, raw=canonical_artifact_bytes(payload))


def _planner_result() -> _PlannerResult:
    items = []
    targets = []
    for index in range(82):
        custom_id = f"tw1.timer-{index // 5:02d}.c{index + 1:04d}.a1"
        body = {
            "input": f"Timer Wave-1 decision {index + 1}",
            "max_output_tokens": 128,
            "model": "gpt-5.6-terra",
            "reasoning": {"effort": "high"},
        }
        identity = cache_identity(
            manifest_sha256="sha256:" + "1" * 64,
            probe_id=f"timer-{index // 5:02d}",
            protocol=HarnessProtocol.GENERATION,
            variant_id=f"call-{index + 1}",
            presentation="policy-seq-1",
            model="gpt-5.6-terra",
            reasoning_effort="high",
            prompt_hash="sha256:" + "2" * 64,
            request_bytes=canonical_artifact_bytes(body),
        )
        items.append(
            BatchWorkItem(
                custom_id=custom_id,
                identity=identity,
                body=body,
                prompt_hash=identity.prompt_hash,
                decoder=BatchDecoder.ACTION,
            )
        )
        targets.append(
            {
                "boundary_class": "ambiguous_cancel" if index == 5 else "ordinary",
                "causal_state_class": f"timer-state-{index + 1}",
                "cell": {
                    "family": "timer_cancel_quoting_stale_fire",
                    "floor": "owned",
                    "protocol": "generation",
                },
                "custom_id": custom_id,
                "family": "timer_normal",
                "idle_boundary": None,
                "logical_stream_id": f"timer-{index // 5:02d}",
                "mandatory_review": index < 6,
                "mandatory_review_reasons": (
                    ["mandatory_action"]
                    if index < 4
                    else (["rollover"] if index == 4 else (["risk_flag"] if index == 5 else []))
                ),
                "oracle_action": _oracle_action(index),
                "request_body_sha256": digest(canonical_artifact_bytes(body)),
                "risk_flags": ["cancel_semantic_referent_resolution"] if index == 5 else [],
                "rollover": index == 4,
                "target_id": f"target-{index + 1}",
            }
        )
    all_items = tuple(items)
    shards = []
    for shard_index, shard_items in enumerate((all_items[:41], all_items[41:])):
        input_jsonl = b"".join(item.request_line for item in shard_items)
        shards.append(
            BatchShard(
                stage="tw1",
                shard_index=shard_index,
                items=shard_items,
                input_jsonl=input_jsonl,
                estimated_input_tokens=sum(
                    estimate_tokens(item.request_bytes) for item in shard_items
                ),
                input_sha256=digest(input_jsonl),
            )
        )
    manifest = {
        "cost_estimate": {"approval_ceiling_usd": format(_CEILING, "f")},
        "decision_count": 82,
        "max_enqueued_tokens": 700_000,
        "model": "gpt-5.6-terra",
        "reasoning_effort": "high",
        "request_count": 82,
        "shards": [
            {
                "estimated_input_tokens": shard.estimated_input_tokens,
                "input_sha256": shard.input_sha256,
                "request_count": len(shard.items),
                "shard_index": shard.shard_index,
                "stage": shard.stage,
            }
            for shard in shards
        ],
        "targets": targets,
    }
    files = {"teacher-plan.json": canonical_artifact_bytes(manifest)}
    for shard in shards:
        files[f"teacher-input/wave1-{shard.shard_index:04d}.jsonl"] = shard.input_jsonl
    checksums = [
        f"{digest(content).removeprefix('sha256:')}  {path}"
        for path, content in sorted(files.items())
    ]
    files["SHA256SUMS"] = ("\n".join(checksums) + "\n").encode()
    return _PlannerResult(files=files, items=all_items, shards=tuple(shards))


def _oracle_action(index: int) -> dict[str, object]:
    span = {"end_utf16": 5, "event_id": "e_000001", "start_utf16": 0, "text": "Timer"}
    if index == 0:
        return {"instruction": span, "interval_ms": 60_000, "message": "Timer", "type": "schedule"}
    if index == 1:
        return {
            "instruction": span,
            "target": {"kind": "timer", "timer_id": "t_001"},
            "type": "cancel",
        }
    if index == 2:
        return {"reason": "canceled_timer", "target_event_id": "e_000001", "type": "skip"}
    if index == 3:
        return {"fire_event_id": "e_000001", "type": "nudge"}
    return {"reason": "no_trigger", "related_event_id": None, "type": "idle"}


def _materialize(repository: Path, plan: _PlannerResult) -> None:
    packet = repository / script._PACKET
    for relative_path, content in plan.files.items():
        path = packet / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)


def _install_planner(
    monkeypatch: pytest.MonkeyPatch,
    plan: _PlannerResult,
    repository: Path,
) -> None:
    _materialize(repository, plan)
    monkeypatch.setattr(
        script,
        "_build_plan",
        lambda _repository: _return(plan),
    )


async def _return(plan: _PlannerResult) -> _PlannerResult:
    return plan


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
    def __init__(
        self,
        plan: _PlannerResult,
        *,
        terminal_status: str = "completed",
        mismatch_custom_id: str | None = None,
    ) -> None:
        self.by_input = {shard.input_jsonl: shard for shard in plan.shards}
        manifest = json.loads(plan.files["teacher-plan.json"])
        self.actions = {
            target["custom_id"]: target["oracle_action"] for target in manifest["targets"]
        }
        self.terminal_status = terminal_status
        self.mismatch_custom_id = mismatch_custom_id
        self.upload_calls = 0
        self.create_calls = 0
        self.retrieve_calls = 0

    async def upload(self, input_jsonl: bytes, _filename: str) -> BatchApiObservation:
        shard = self.by_input[input_jsonl]
        self.upload_calls += 1
        return _observation({"id": f"input_{shard.shard_index}"})

    async def create(self, input_file_id: str, metadata: dict[str, str]) -> BatchApiObservation:
        shard_index = int(input_file_id.removeprefix("input_"))
        shard = tuple(self.by_input.values())[shard_index]
        self.create_calls += 1
        assert metadata == {
            "im_input_sha256": shard.input_sha256.removeprefix("sha256:"),
            "im_shard": str(shard_index),
            "im_stage": "tw1",
        }
        return _observation(
            {
                "endpoint": "/v1/responses",
                "id": f"batch_{shard_index}",
                "input_file_id": input_file_id,
                "metadata": metadata,
                "status": "validating",
            }
        )

    async def retrieve(self, batch_id: str) -> BatchApiObservation:
        shard_index = int(batch_id.removeprefix("batch_"))
        shard = tuple(self.by_input.values())[shard_index]
        self.retrieve_calls += 1
        return _observation(
            {
                "endpoint": "/v1/responses",
                "error_file_id": None,
                "id": batch_id,
                "input_file_id": f"input_{shard_index}",
                "metadata": {
                    "im_input_sha256": shard.input_sha256.removeprefix("sha256:"),
                    "im_shard": str(shard_index),
                    "im_stage": "tw1",
                },
                "output_file_id": f"output_{shard_index}"
                if self.terminal_status == "completed"
                else None,
                "status": self.terminal_status,
            }
        )

    async def download(self, file_id: str) -> bytes:
        shard_index = int(file_id.removeprefix("output_"))
        shard = tuple(self.by_input.values())[shard_index]
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
async def test_plan_stays_offline_and_reconstructs_82_decisions(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    plan = _planner_result()
    _install_planner(monkeypatch, plan, tmp_path)
    monkeypatch.setattr(
        socket,
        "create_connection",
        lambda *_args, **_kwargs: pytest.fail("plan must stay offline"),
    )

    loaded = await load_plan(tmp_path)
    await _run(_args(tmp_path, "plan"))

    assert len(loaded.items) == 82
    assert [len(shard.items) for shard in loaded.shards] == [41, 41]


@pytest.mark.asyncio
async def test_real_plan_repeats_without_rewriting_materialized_packet() -> None:
    packet = ROOT / script._PACKET
    before = {
        path.relative_to(packet).as_posix(): (path.read_bytes(), path.stat().st_mtime_ns)
        for path in packet.rglob("*")
        if path.is_file()
    }

    await _run(_args(ROOT, "plan"))
    await _run(_args(ROOT, "plan"))

    after = {
        path.relative_to(packet).as_posix(): (path.read_bytes(), path.stat().st_mtime_ns)
        for path in packet.rglob("*")
        if path.is_file()
    }
    assert after == before
    targets = json.loads((packet / "teacher-plan.json").read_text())["targets"]
    lexical = next(
        target
        for target in targets
        if target["custom_id"] == "t2w1.contention-floor-typing.d004.a1"
    )
    assert lexical["idle_boundary"] == "lexical_boundary"
    assert lexical["mandatory_review"] is True


@pytest.mark.asyncio
async def test_multi_shard_execution_resumes_without_resubmit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    plan = _planner_result()
    gateway = _Gateway(plan, mismatch_custom_id=plan.items[6].custom_id)
    _install_planner(monkeypatch, plan, tmp_path)
    monkeypatch.setattr(script, "OpenAIBatchGateway", lambda **_kwargs: gateway)
    monkeypatch.setenv("OPENAI_API_KEY", "test")

    await _run(_args(tmp_path))
    await _run(_args(tmp_path, "resume"))

    execution = tmp_path / script._EXECUTION
    comparison = json.loads((execution / "comparison.json").read_text(encoding="utf-8"))
    assert comparison["request_count"] == 82
    assert comparison["non_equivalent_count"] == 1
    assert gateway.upload_calls == gateway.create_calls == gateway.retrieve_calls == 2
    rows = comparison["rows"]
    assert all(row["comparison"] == "equivalent" for row in rows[:6])
    assert all(row["mandatory_review"] for row in rows[:7])
    assert rows[4]["target"]["rollover"] is True
    assert rows[5]["target"]["risk_flags"] == ["cancel_semantic_referent_resolution"]
    assert rows[6]["comparison"] == "non_equivalent"
    assert rows[6]["mandatory_review_reasons"] == [
        "mandatory_action",
        "teacher_oracle_disagreement",
    ]
    assert rows[7]["mandatory_review"] is False
    assert json.loads((execution / "shards/0000/comparison.json").read_text())["rows"]
    assert json.loads((execution / "shards/0001/comparison.json").read_text())["rows"]


@pytest.mark.asyncio
async def test_terminal_failure_is_preserved_without_comparison(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    plan = _planner_result()
    gateway = _Gateway(plan, terminal_status="failed")
    _install_planner(monkeypatch, plan, tmp_path)
    monkeypatch.setattr(script, "OpenAIBatchGateway", lambda **_kwargs: gateway)
    monkeypatch.setenv("OPENAI_API_KEY", "test")

    with pytest.raises(TimerWave1RunError, match="terminal status 'failed'"):
        await _run(_args(tmp_path))

    execution = tmp_path / script._EXECUTION
    assert not (execution / "comparison.json").exists()
    state = json.loads((execution / "shards/0000/execution-state.json").read_text())
    assert state["status"] == "failed"


@pytest.mark.asyncio
async def test_tampering_token_and_ceiling_are_rejected(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    plan = _planner_result()
    _install_planner(monkeypatch, plan, tmp_path)
    packet = tmp_path / script._PACKET
    (packet / "teacher-plan.json").write_text("{}\n", encoding="utf-8")
    with pytest.raises(TimerWave1RunError, match="packet member changed"):
        _verify_packet(packet)
    _materialize(tmp_path, plan)

    wrong_tokens = _args(tmp_path)
    wrong_tokens.batch_max_enqueued_tokens = 1
    with pytest.raises(TimerWave1RunError, match="signed 700000-token"):
        await _run(wrong_tokens)

    wrong_ceiling = _args(tmp_path)
    wrong_ceiling.approve_live_ceiling_usd = Decimal("1.234499")
    with pytest.raises(TimerWave1RunError, match="exactly 1.234500"):
        await _run(wrong_ceiling)

    loaded = await load_plan(tmp_path)
    drifted = {**loaded.manifest, "max_enqueued_tokens": 1}
    with pytest.raises(TimerWave1RunError, match="signed model, decision, or shard"):
        _validate_plan(drifted, loaded.targets, loaded.items, loaded.shards)
