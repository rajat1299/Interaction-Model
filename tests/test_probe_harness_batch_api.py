"""Crash/restart tests for the OpenAI Batch lifecycle ledger."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from im.probes.harness.batch import BatchShard
from im.probes.harness.batch_api import (
    BatchApiObservation,
    BatchCreateRejected,
    BatchCreateUncertain,
    BatchLifecycleError,
    OpenAIBatchGateway,
    adopt_uncertain_batch,
    execute_batch_shard,
)
from im.probes.harness.cache import HarnessCache
from im.probes.harness.identity import digest
from im.probes.harness.models import BatchJobRecord


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
        return _observation(
            {
                "endpoint": "/v1/responses",
                "id": "batch_123",
                "input_file_id": input_file_id,
                "metadata": metadata,
                "status": "validating",
            }
        )

    async def retrieve(self, batch_id: str) -> BatchApiObservation:
        assert batch_id == "batch_123"
        self.retrieve_calls += 1
        if self.retrieve_calls == 1:
            return _observation(
                {
                    "endpoint": "/v1/responses",
                    "id": batch_id,
                    "input_file_id": "file_input",
                    "metadata": {
                        "im_input_sha256": _shard().input_sha256.removeprefix("sha256:"),
                        "im_shard": "0",
                        "im_stage": "p0",
                    },
                    "status": "in_progress",
                }
            )
        return _observation(
            {
                "endpoint": "/v1/responses",
                "error_file_id": None,
                "id": batch_id,
                "input_file_id": "file_input",
                "metadata": {
                    "im_input_sha256": _shard().input_sha256.removeprefix("sha256:"),
                    "im_shard": "0",
                    "im_stage": "p0",
                },
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
        replaced = adopt_uncertain_batch(
            cache,
            input_sha256=_shard().input_sha256,
            batch_id="batch_corrected",
        )
        assert replaced.batch_id == "batch_corrected"
        adopt_uncertain_batch(
            cache,
            input_sha256=_shard().input_sha256,
            batch_id="batch_123",
        )

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


class _WrongAdoptGateway(_Gateway):
    async def retrieve(self, batch_id: str) -> BatchApiObservation:
        return _observation(
            {
                "endpoint": "/v1/responses",
                "id": batch_id,
                "input_file_id": "file_unrelated",
                "metadata": {
                    "im_input_sha256": "wrong",
                    "im_shard": "0",
                    "im_stage": "p0",
                },
                "output_file_id": "file_output",
                "status": "completed",
            }
        )


class _MissingAdoptGateway(_Gateway):
    async def retrieve(self, batch_id: str) -> BatchApiObservation:
        raise BatchLifecycleError(f"Batch retrieve returned HTTP 404 for {batch_id}")


@pytest.mark.asyncio
async def test_adopted_batch_must_bind_exact_input_endpoint_and_metadata(
    tmp_path: Path,
) -> None:
    shard = _shard()
    uncertain = BatchJobRecord(
        input_sha256=shard.input_sha256,
        stage=shard.stage,
        shard_index=shard.shard_index,
        input_jsonl=shard.input_jsonl,
        request_count=len(shard.items),
        estimated_input_tokens=shard.estimated_input_tokens,
        status="create_uncertain",
        input_file_id="file_input",
    )
    with HarnessCache(tmp_path / "batch.sqlite") as cache:
        cache.put_batch_job(uncertain)
        adopt_uncertain_batch(
            cache,
            input_sha256=shard.input_sha256,
            batch_id="batch_unrelated",
        )
        with pytest.raises(BatchLifecycleError, match="input_file_id"):
            await execute_batch_shard(
                shard,
                cache=cache,
                gateway=_WrongAdoptGateway(),
                poll_seconds=1,
            )

        rejected = cache.get_batch_job(shard.input_sha256)
        assert rejected.status == "create_uncertain"
        assert rejected.batch_id is None
        corrected = adopt_uncertain_batch(
            cache,
            input_sha256=shard.input_sha256,
            batch_id="batch_corrected",
        )
        assert corrected.status == "adopted_unverified"


@pytest.mark.asyncio
async def test_unverified_adoption_can_be_replaced_after_typo_or_404(
    tmp_path: Path,
) -> None:
    shard = _shard()
    uncertain = BatchJobRecord(
        input_sha256=shard.input_sha256,
        stage=shard.stage,
        shard_index=shard.shard_index,
        input_jsonl=shard.input_jsonl,
        request_count=len(shard.items),
        estimated_input_tokens=shard.estimated_input_tokens,
        status="create_uncertain",
        input_file_id="file_input",
    )
    with HarnessCache(tmp_path / "batch.sqlite") as cache:
        cache.put_batch_job(uncertain)
        adopt_uncertain_batch(
            cache,
            input_sha256=shard.input_sha256,
            batch_id="batch_typo",
        )
        with pytest.raises(BatchLifecycleError, match="404"):
            await execute_batch_shard(
                shard,
                cache=cache,
                gateway=_MissingAdoptGateway(),
                poll_seconds=1,
            )
        replaced = adopt_uncertain_batch(
            cache,
            input_sha256=shard.input_sha256,
            batch_id="batch_corrected",
        )

    assert replaced.status == "adopted_unverified"
    assert replaced.batch_id == "batch_corrected"


@pytest.mark.asyncio
async def test_openai_gateway_uses_official_files_and_responses_batch_shapes() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/v1/files" and request.method == "POST":
            assert b'name="purpose"' in request.content
            assert b"batch" in request.content
            assert b'application/jsonl' in request.content
            return httpx.Response(200, json={"id": "file_input"})
        if request.url.path == "/v1/batches" and request.method == "POST":
            assert json.loads(request.content) == {
                "completion_window": "24h",
                "endpoint": "/v1/responses",
                "input_file_id": "file_input",
                "metadata": {"im_stage": "p0"},
            }
            return httpx.Response(200, json={"id": "batch_123", "status": "validating"})
        if request.url.path == "/v1/batches/batch_123" and request.method == "GET":
            return httpx.Response(200, json={"id": "batch_123", "status": "completed"})
        if request.url.path == "/v1/files/file_output/content" and request.method == "GET":
            return httpx.Response(200, content=b'{"custom_id":"p0.test.a1"}\n')
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    async with httpx.AsyncClient(
        base_url="https://api.openai.com/v1",
        transport=httpx.MockTransport(handler),
    ) as client:
        gateway = OpenAIBatchGateway(api_key="test-key", client=client)
        uploaded = await gateway.upload(b'{"custom_id":"p0.test.a1"}\n', "pilot.jsonl")
        created = await gateway.create("file_input", {"im_stage": "p0"})
        retrieved = await gateway.retrieve("batch_123")
        downloaded = await gateway.download("file_output")

    assert uploaded.payload["id"] == "file_input"
    assert created.payload["id"] == "batch_123"
    assert retrieved.payload["status"] == "completed"
    assert downloaded == b'{"custom_id":"p0.test.a1"}\n'
    assert len(requests) == 4


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status_code", "error_type"),
    [
        (400, BatchCreateRejected),
        (408, BatchCreateUncertain),
        (429, BatchCreateUncertain),
        (500, BatchCreateUncertain),
    ],
)
async def test_create_http_status_only_rejects_when_non_acceptance_is_definitive(
    status_code: int,
    error_type: type[Exception],
) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json={"error": "controlled"})

    async with httpx.AsyncClient(
        base_url="https://api.openai.com/v1",
        transport=httpx.MockTransport(handler),
    ) as client:
        gateway = OpenAIBatchGateway(api_key="test-key", client=client)
        with pytest.raises(error_type):
            await gateway.create("file_input", {"im_stage": "p0"})
