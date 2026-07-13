"""Crash-safe OpenAI Batch lifecycle with an exact SQLite audit ledger."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace
from typing import Protocol

import httpx

from im.probes.harness.batch import BatchShard
from im.probes.harness.cache import HarnessCache
from im.probes.harness.models import BatchJobRecord

_TERMINAL_STATUSES = frozenset({"cancelled", "completed", "expired", "failed"})


class BatchLifecycleError(RuntimeError):
    """A Batch management or terminal-state failure that is safe to surface."""


class BatchCreateUncertain(BatchLifecycleError):
    """The create request may have succeeded and must never be repeated automatically."""


class BatchCreateRejected(BatchLifecycleError):
    """The provider definitively rejected Batch creation without enqueuing work."""


@dataclass(frozen=True, slots=True)
class BatchApiObservation:
    payload: dict[str, object]
    raw: bytes


class BatchGateway(Protocol):
    async def upload(self, input_jsonl: bytes, filename: str) -> BatchApiObservation: ...

    async def create(
        self,
        input_file_id: str,
        metadata: dict[str, str],
    ) -> BatchApiObservation: ...

    async def retrieve(self, batch_id: str) -> BatchApiObservation: ...

    async def download(self, file_id: str) -> bytes: ...


class OpenAIBatchGateway:
    """Thin official-API transport; orchestration and retry policy live above it."""

    def __init__(
        self,
        *,
        api_key: str,
        organization_id: str | None = None,
        project_id: str | None = None,
        base_url: str = "https://api.openai.com/v1",
        timeout_seconds: int = 120,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("api_key must not be empty")
        headers = {"Authorization": f"Bearer {api_key}"}
        if organization_id:
            headers["OpenAI-Organization"] = organization_id
        if project_id:
            headers["OpenAI-Project"] = project_id
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            base_url=base_url,
            headers=headers,
            timeout=timeout_seconds,
        )

    async def upload(self, input_jsonl: bytes, filename: str) -> BatchApiObservation:
        response = await self._client.post(
            "/files",
            data={"purpose": "batch"},
            files={"file": (filename, input_jsonl, "application/jsonl")},
        )
        return _observation(response, operation="Batch file upload")

    async def create(
        self,
        input_file_id: str,
        metadata: dict[str, str],
    ) -> BatchApiObservation:
        response = await self._client.post(
            "/batches",
            json={
                "completion_window": "24h",
                "endpoint": "/v1/responses",
                "input_file_id": input_file_id,
                "metadata": metadata,
            },
        )
        if not 200 <= response.status_code < 300:
            error_type = (
                BatchCreateRejected
                if 400 <= response.status_code < 500
                and response.status_code not in {408, 409, 429}
                else BatchCreateUncertain
            )
            raise error_type(
                f"Batch create returned HTTP {response.status_code}: "
                f"{response.content[:2_048]!r}"
            )
        return _observation(response, operation="Batch create")

    async def retrieve(self, batch_id: str) -> BatchApiObservation:
        response = await self._client.get(f"/batches/{batch_id}")
        return _observation(response, operation="Batch retrieve")

    async def download(self, file_id: str) -> bytes:
        response = await self._client.get(f"/files/{file_id}/content")
        if not 200 <= response.status_code < 300:
            raise BatchLifecycleError(
                f"Batch file download returned HTTP {response.status_code}: "
                f"{response.content[:2_048]!r}"
            )
        return response.content

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()


async def execute_batch_shard(
    shard: BatchShard,
    *,
    cache: HarnessCache,
    gateway: BatchGateway,
    poll_seconds: float,
    sleep: Callable[[float], Awaitable[object]] = asyncio.sleep,
) -> BatchJobRecord:
    """Resume one shard without ever recreating a possibly accepted Batch."""
    if poll_seconds <= 0:
        raise ValueError("poll_seconds must be positive")
    planned = BatchJobRecord(
        input_sha256=shard.input_sha256,
        stage=shard.stage,
        shard_index=shard.shard_index,
        input_jsonl=shard.input_jsonl,
        request_count=len(shard.items),
        estimated_input_tokens=shard.estimated_input_tokens,
    )
    record = cache.get_batch_job(shard.input_sha256)
    if record is None:
        cache.put_batch_job(
            planned,
            event_kind="planned",
            event_payload=_job_summary(planned),
        )
        record = planned
    elif (
        record.stage,
        record.shard_index,
        record.input_jsonl,
        record.request_count,
        record.estimated_input_tokens,
    ) != (
        planned.stage,
        planned.shard_index,
        planned.input_jsonl,
        planned.request_count,
        planned.estimated_input_tokens,
    ):
        raise BatchLifecycleError("Batch ledger input does not match the deterministic shard")

    if record.status == "create_uncertain":
        raise BatchCreateUncertain(
            f"Batch create outcome is uncertain for {record.input_sha256}; "
            "reconcile and adopt the provider batch id before resuming"
        )
    if record.status == "create_failed":
        raise BatchLifecycleError(
            f"Batch create previously failed definitively for {record.input_sha256}"
        )

    if record.input_file_id is None:
        upload = await gateway.upload(
            shard.input_jsonl,
            f"im-wp15-{shard.stage}-{shard.shard_index:04d}.jsonl",
        )
        input_file_id = _required_string(upload.payload, "id", "uploaded file")
        record = replace(record, status="uploaded", input_file_id=input_file_id)
        cache.put_batch_job(record, event_kind="uploaded", event_payload=upload.raw)

    if record.batch_id is None:
        uncertain = replace(record, status="create_uncertain")
        cache.put_batch_job(
            uncertain,
            event_kind="create_intent",
            event_payload=_job_summary(uncertain),
        )
        try:
            created = await gateway.create(
                record.input_file_id,
                _expected_metadata(record),
            )
            batch_id = _required_string(created.payload, "id", "created batch")
            _verify_batch_binding(created.payload, record)
        except BatchCreateRejected as error:
            failed = replace(record, status="create_failed")
            cache.put_batch_job(
                failed,
                event_kind="create_failed",
                event_payload=str(error).encode(),
            )
            raise
        except BaseException as error:
            cache.put_batch_job(
                uncertain,
                event_kind="create_uncertain",
                event_payload=f"{type(error).__name__}: {error}".encode(),
            )
            raise BatchCreateUncertain(
                f"Batch create may have succeeded for {record.input_sha256}"
            ) from error
        record = replace(
            record,
            status=str(created.payload.get("status", "submitted")),
            batch_id=batch_id,
            output_file_id=_optional_string(created.payload, "output_file_id"),
            error_file_id=_optional_string(created.payload, "error_file_id"),
            latest_batch_json=created.raw,
        )
        cache.put_batch_job(record, event_kind="created", event_payload=created.raw)

    while record.status not in _TERMINAL_STATUSES:
        observed = await gateway.retrieve(record.batch_id)
        status = _required_string(observed.payload, "status", "retrieved batch")
        observed_id = _required_string(observed.payload, "id", "retrieved batch")
        if observed_id != record.batch_id:
            raise BatchLifecycleError("retrieved Batch id does not match the ledger")
        try:
            _verify_batch_binding(observed.payload, record)
        except BatchLifecycleError:
            if record.status == "adopted_unverified":
                rejected = replace(
                    record,
                    status="create_uncertain",
                    batch_id=None,
                    latest_batch_json=observed.raw,
                )
                cache.put_batch_job(
                    rejected,
                    event_kind="adoption_rejected",
                    event_payload=observed.raw,
                )
            raise
        record = replace(
            record,
            status=status,
            output_file_id=_optional_string(observed.payload, "output_file_id"),
            error_file_id=_optional_string(observed.payload, "error_file_id"),
            latest_batch_json=observed.raw,
        )
        cache.put_batch_job(record, event_kind="polled", event_payload=observed.raw)
        if status not in _TERMINAL_STATUSES:
            await sleep(poll_seconds)

    if record.output_file_id is not None and not record.output_jsonl:
        output_jsonl = await gateway.download(record.output_file_id)
        record = replace(record, output_jsonl=output_jsonl)
        cache.put_batch_job(
            record,
            event_kind="output_downloaded",
            event_payload=output_jsonl,
        )
    if record.error_file_id is not None and not record.error_jsonl:
        error_jsonl = await gateway.download(record.error_file_id)
        record = replace(record, error_jsonl=error_jsonl)
        cache.put_batch_job(
            record,
            event_kind="error_downloaded",
            event_payload=error_jsonl,
        )
    return record


def adopt_uncertain_batch(
    cache: HarnessCache,
    *,
    input_sha256: str,
    batch_id: str,
) -> BatchJobRecord:
    """Explicitly bind a user-reconciled provider id; never guessed automatically."""
    if not batch_id:
        raise ValueError("batch_id must not be empty")
    record = cache.get_batch_job(input_sha256)
    if record is None:
        raise KeyError(f"unknown Batch input digest: {input_sha256}")
    if record.status not in {"adopted_unverified", "create_uncertain"}:
        raise ValueError("only an unresolved or unverified Batch adoption can be replaced")
    replacing = record.status == "adopted_unverified"
    adopted = replace(record, status="adopted_unverified", batch_id=batch_id)
    cache.put_batch_job(
        adopted,
        event_kind="batch_adoption_replaced" if replacing else "batch_adopted",
        event_payload=batch_id.encode(),
    )
    return adopted


def _observation(response: httpx.Response, *, operation: str) -> BatchApiObservation:
    if not 200 <= response.status_code < 300:
        raise BatchLifecycleError(
            f"{operation} returned HTTP {response.status_code}: {response.content[:2_048]!r}"
        )
    try:
        payload = json.loads(response.content)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise BatchLifecycleError(f"{operation} returned invalid JSON") from error
    if not isinstance(payload, dict):
        raise BatchLifecycleError(f"{operation} returned a non-object JSON value")
    return BatchApiObservation(payload=payload, raw=response.content)


def _required_string(payload: dict[str, object], key: str, subject: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise BatchLifecycleError(f"{subject} lacks non-empty {key}")
    return value


def _optional_string(payload: dict[str, object], key: str) -> str | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise BatchLifecycleError(f"Batch field {key} must be null or a non-empty string")
    return value


def _job_summary(record: BatchJobRecord) -> bytes:
    return json.dumps(
        {
            "estimated_input_tokens": record.estimated_input_tokens,
            "input_sha256": record.input_sha256,
            "request_count": record.request_count,
            "shard_index": record.shard_index,
            "stage": record.stage,
            "status": record.status,
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode()


def _expected_metadata(record: BatchJobRecord) -> dict[str, str]:
    return {
        "im_input_sha256": record.input_sha256.removeprefix("sha256:"),
        "im_shard": str(record.shard_index),
        "im_stage": record.stage,
    }


def _verify_batch_binding(
    payload: dict[str, object],
    record: BatchJobRecord,
) -> None:
    if payload.get("input_file_id") != record.input_file_id:
        raise BatchLifecycleError("Batch input_file_id does not match the ledger")
    if payload.get("endpoint") != "/v1/responses":
        raise BatchLifecycleError("Batch endpoint does not match /v1/responses")
    metadata = payload.get("metadata")
    if not isinstance(metadata, dict):
        raise BatchLifecycleError("Batch metadata is absent or malformed")
    expected = _expected_metadata(record)
    if any(metadata.get(key) != value for key, value in expected.items()):
        raise BatchLifecycleError("Batch metadata does not bind the signed input shard")
