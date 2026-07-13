"""Crash/restart tests for the OpenAI Batch lifecycle ledger."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from im.probes.harness.batch import BatchShard
from im.probes.harness.batch_api import (
    BatchApiObservation,
    BatchCreateUncertain,
    adopt_uncertain_batch,
    execute_batch_shard,
)
from im.probes.harness.cache import HarnessCache
from im.probes.harness.identity import digest


def _observation(payload: dict[str, object]) -> BatchApiObservation:
    return BatchApiObservation(
        payload=payload,
        raw=json.dumps(payload, separators=(",", ":"), sort_keys=True).encode(),
    )


def _shard() -> BatchShard:
    input_jsonl = b'{"custom_id":"p0.test.a1"}\n'
    return BatchShard(
        stage="p0",
        shard_index=0,
        items=(),
        input_jsonl=input_jsonl,
        estimated_input_tokens=8,
        input_sha256=digest(input_jsonl),
    )


class _Gateway:
    def __init__(self) -> None:
        self.upload_calls = 0
        self.create_calls = 0
        self.retrieve_calls = 0
        self.download_calls: list[str] = []

    async def upload(self, input_jsonl: bytes, filename: str) -> BatchApiObservation:
        assert input_jsonl == _shard().input_jsonl
        assert filename.endswith(".jsonl")
        self.upload_calls += 1
        return _observation({"id": "file_input"})

    async def create(
        self,
        input_file_id: str,
        metadata: dict[str, str],
    ) -> BatchApiObservation:
        assert input_file_id == "file_input"
        assert metadata["im_stage"] == "p0"
        self.create_calls += 1
        return _observation({"id": "batch_123", "status": "validating"})

    async def retrieve(self, batch_id: str) -> BatchApiObservation:
        assert batch_id == "batch_123"
        self.retrieve_calls += 1
        if self.retrieve_calls == 1:
            return _observation({"id": batch_id, "status": "in_progress"})
        return _observation(
            {
                "error_file_id": None,
                "id": batch_id,
                "output_file_id": "file_output",
                "status": "completed",
            }
        )

    async def download(self, file_id: str) -> bytes:
        self.download_calls.append(file_id)
        return b'{"custom_id":"p0.test.a1","response":{}}\n'


@pytest.mark.asyncio
async def test_batch_lifecycle_resumes_without_duplicate_upload_or_create(
    tmp_path: Path,
) -> None:
    gateway = _Gateway()
    sleeps: list[float] = []

    async def no_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    with HarnessCache(tmp_path / "batch.sqlite") as cache:
        completed = await execute_batch_shard(
            _shard(),
            cache=cache,
            gateway=gateway,
            poll_seconds=1,
            sleep=no_sleep,
        )
        resumed = await execute_batch_shard(
            _shard(),
            cache=cache,
            gateway=gateway,
            poll_seconds=1,
            sleep=no_sleep,
        )
        events = cache.batch_events(_shard().input_sha256)

    assert completed == resumed
    assert completed.status == "completed"
    assert completed.output_jsonl
    assert gateway.upload_calls == 1
    assert gateway.create_calls == 1
    assert gateway.retrieve_calls == 2
    assert gateway.download_calls == ["file_output"]
    assert sleeps == [1]
    assert [kind for kind, _ in events] == [
        "planned",
        "uploaded",
        "create_intent",
        "created",
        "polled",
        "polled",
        "output_downloaded",
    ]


class _UncertainGateway(_Gateway):
    async def create(
        self,
        input_file_id: str,
        metadata: dict[str, str],
    ) -> BatchApiObservation:
        self.create_calls += 1
        raise TimeoutError("connection dropped after request bytes were sent")


@pytest.mark.asyncio
async def test_uncertain_create_never_auto_resubmits_and_requires_explicit_adoption(
    tmp_path: Path,
) -> None:
    gateway = _UncertainGateway()
    path = tmp_path / "batch.sqlite"
    with HarnessCache(path) as cache:
        with pytest.raises(BatchCreateUncertain, match="may have succeeded"):
            await execute_batch_shard(
                _shard(),
                cache=cache,
                gateway=gateway,
                poll_seconds=1,
            )
        assert cache.get_batch_job(_shard().input_sha256).status == "create_uncertain"

        with pytest.raises(BatchCreateUncertain, match="reconcile and adopt"):
            await execute_batch_shard(
                _shard(),
                cache=cache,
                gateway=gateway,
                poll_seconds=1,
            )
        assert gateway.create_calls == 1
        adopted = adopt_uncertain_batch(
            cache,
            input_sha256=_shard().input_sha256,
            batch_id="batch_123",
        )
        assert adopted.batch_id == "batch_123"

    resumed_gateway = _Gateway()
    resumed_gateway.upload_calls = 99
    with HarnessCache(path) as cache:
        completed = await execute_batch_shard(
            _shard(),
            cache=cache,
            gateway=resumed_gateway,
            poll_seconds=1,
            sleep=lambda _seconds: _done(),
        )

    assert completed.status == "completed"
    assert resumed_gateway.create_calls == 0
    assert resumed_gateway.upload_calls == 99


async def _done() -> None:
    return None
