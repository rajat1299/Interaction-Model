"""Durable SQLite cache for resumable WP15 provider calls."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from im.probes.harness.models import (
    BatchJobRecord,
    CacheIdentity,
    HarnessCompletion,
    ProviderUsage,
    traces_from_json,
    traces_to_json,
)

_INDETERMINATE_OUTCOMES = frozenset(
    {"batch_error", "cancelled", "transport_error", "http_error"}
)


class IndeterminateCacheEntry(RuntimeError):
    """A prior call may have been billed but lacks a definitive provider completion."""


class HarnessCache:
    """Small synchronous cache used only at async task boundaries on the event-loop thread."""

    def __init__(
        self,
        path: Path,
        *,
        retry_indeterminate_keys: frozenset[str] = frozenset(),
    ) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.retry_indeterminate_keys = frozenset(retry_indeterminate_keys)
        self._retry_consumed: set[str] = set()
        self._connection = sqlite3.connect(path)
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA synchronous=FULL")
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            self._initialize_schema()
            self._connection.commit()
        except BaseException:
            self._connection.rollback()
            self._connection.close()
            raise

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> HarnessCache:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def get(self, identity: CacheIdentity) -> HarnessCompletion | None:
        row = self._connection.execute(
            """
            SELECT outcome, value_json, traces_json, usage_json
            FROM completions WHERE cache_key = ? AND identity_json = ?
            """,
            (identity.digest, self._identity_json(identity)),
        ).fetchone()
        if row is None:
            return None
        outcome = row[0]
        if str(outcome) in _INDETERMINATE_OUTCOMES:
            if identity.digest not in self.retry_indeterminate_keys:
                raise IndeterminateCacheEntry(
                    "cached call is indeterminate; explicitly authorize only this identity with "
                    f"--retry-indeterminate-cache-key {identity.digest}"
                )
            if identity.digest in self._retry_consumed:
                raise IndeterminateCacheEntry(
                    "indeterminate retry authorization was already consumed for cache key "
                    f"{identity.digest}"
                )
            self._retry_consumed.add(identity.digest)
            return None
        return self._completion_from_row(row, from_cache=True)

    def put(self, identity: CacheIdentity, completion: HarnessCompletion) -> None:
        values = self._row_values(identity, completion)
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO attempt_history (
                    cache_key, identity_json, outcome, value_json, traces_json, usage_json
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                values,
            )
            self._connection.execute(
                """
                INSERT INTO completions (
                    cache_key, identity_json, outcome, value_json, traces_json, usage_json
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(cache_key) DO UPDATE SET
                    identity_json = excluded.identity_json,
                    outcome = excluded.outcome,
                    value_json = excluded.value_json,
                    traces_json = excluded.traces_json,
                    usage_json = excluded.usage_json
                """,
                values,
            )

    def history(self, identity: CacheIdentity) -> tuple[HarnessCompletion, ...]:
        """Return append-only evidence for every attempt at this exact presentation."""
        rows = self._connection.execute(
            """
            SELECT outcome, value_json, traces_json, usage_json
            FROM attempt_history
            WHERE cache_key = ? AND identity_json = ?
            ORDER BY attempt_id
            """,
            (identity.digest, self._identity_json(identity)),
        ).fetchall()
        return tuple(self._completion_from_row(row, from_cache=True) for row in rows)

    def get_batch_job(self, input_sha256: str) -> BatchJobRecord | None:
        row = self._connection.execute(
            """
            SELECT input_sha256, stage, shard_index, input_jsonl, request_count,
                   estimated_input_tokens, status, input_file_id, batch_id,
                   output_file_id, error_file_id, latest_batch_json,
                   output_jsonl, error_jsonl
            FROM batch_jobs WHERE input_sha256 = ?
            """,
            (input_sha256,),
        ).fetchone()
        if row is None:
            return None
        return BatchJobRecord(*row)

    def put_batch_job(
        self,
        record: BatchJobRecord,
        *,
        event_kind: str | None = None,
        event_payload: bytes = b"",
    ) -> None:
        """Upsert mutable lifecycle state while collision-checking immutable input."""
        existing = self.get_batch_job(record.input_sha256)
        if existing is not None and (
            existing.stage,
            existing.shard_index,
            existing.input_jsonl,
            existing.request_count,
            existing.estimated_input_tokens,
        ) != (
            record.stage,
            record.shard_index,
            record.input_jsonl,
            record.request_count,
            record.estimated_input_tokens,
        ):
            raise ValueError("Batch input digest collides with different immutable job data")
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO batch_jobs (
                    input_sha256, stage, shard_index, input_jsonl, request_count,
                    estimated_input_tokens, status, input_file_id, batch_id,
                    output_file_id, error_file_id, latest_batch_json,
                    output_jsonl, error_jsonl
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(input_sha256) DO UPDATE SET
                    status = excluded.status,
                    input_file_id = excluded.input_file_id,
                    batch_id = excluded.batch_id,
                    output_file_id = excluded.output_file_id,
                    error_file_id = excluded.error_file_id,
                    latest_batch_json = excluded.latest_batch_json,
                    output_jsonl = excluded.output_jsonl,
                    error_jsonl = excluded.error_jsonl
                """,
                (
                    record.input_sha256,
                    record.stage,
                    record.shard_index,
                    record.input_jsonl,
                    record.request_count,
                    record.estimated_input_tokens,
                    record.status,
                    record.input_file_id,
                    record.batch_id,
                    record.output_file_id,
                    record.error_file_id,
                    record.latest_batch_json,
                    record.output_jsonl,
                    record.error_jsonl,
                ),
            )
            if event_kind is not None:
                self._connection.execute(
                    """
                    INSERT INTO batch_events (input_sha256, event_kind, payload)
                    VALUES (?, ?, ?)
                    """,
                    (record.input_sha256, event_kind, event_payload),
                )

    def batch_events(self, input_sha256: str) -> tuple[tuple[str, bytes], ...]:
        rows = self._connection.execute(
            """
            SELECT event_kind, payload FROM batch_events
            WHERE input_sha256 = ? ORDER BY event_id
            """,
            (input_sha256,),
        ).fetchall()
        return tuple((str(kind), bytes(payload)) for kind, payload in rows)

    def _initialize_schema(self) -> None:
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS completions (
                cache_key TEXT PRIMARY KEY,
                identity_json TEXT NOT NULL,
                outcome TEXT NOT NULL,
                value_json TEXT NOT NULL,
                traces_json TEXT NOT NULL,
                usage_json TEXT NOT NULL
            )
            """
        )
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS attempt_history (
                attempt_id INTEGER PRIMARY KEY AUTOINCREMENT,
                cache_key TEXT NOT NULL,
                identity_json TEXT NOT NULL,
                outcome TEXT NOT NULL,
                value_json TEXT NOT NULL,
                traces_json TEXT NOT NULL,
                usage_json TEXT NOT NULL
            )
            """
        )
        self._connection.execute(
            """
            CREATE INDEX IF NOT EXISTS attempt_history_identity_idx
            ON attempt_history(cache_key, identity_json, attempt_id)
            """
        )
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS batch_jobs (
                input_sha256 TEXT PRIMARY KEY,
                stage TEXT NOT NULL,
                shard_index INTEGER NOT NULL,
                input_jsonl BLOB NOT NULL,
                request_count INTEGER NOT NULL,
                estimated_input_tokens INTEGER NOT NULL,
                status TEXT NOT NULL,
                input_file_id TEXT,
                batch_id TEXT,
                output_file_id TEXT,
                error_file_id TEXT,
                latest_batch_json BLOB NOT NULL,
                output_jsonl BLOB NOT NULL,
                error_jsonl BLOB NOT NULL
            )
            """
        )
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS batch_events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                input_sha256 TEXT NOT NULL REFERENCES batch_jobs(input_sha256),
                event_kind TEXT NOT NULL,
                payload BLOB NOT NULL
            )
            """
        )
        self._connection.execute(
            """
            CREATE INDEX IF NOT EXISTS batch_events_job_idx
            ON batch_events(input_sha256, event_id)
            """
        )
        self._connection.execute(
            """
            INSERT INTO attempt_history (
                cache_key, identity_json, outcome, value_json, traces_json, usage_json
            )
            SELECT
                current.cache_key,
                current.identity_json,
                current.outcome,
                current.value_json,
                current.traces_json,
                current.usage_json
            FROM completions AS current
            WHERE NOT EXISTS (
                SELECT 1
                FROM attempt_history AS history
                WHERE history.cache_key = current.cache_key
                  AND history.identity_json = current.identity_json
                  AND history.outcome = current.outcome
                  AND history.value_json = current.value_json
                  AND history.traces_json = current.traces_json
                  AND history.usage_json = current.usage_json
            )
            """
        )

    @classmethod
    def _completion_from_row(
        cls,
        row: tuple[object, object, object, object],
        *,
        from_cache: bool,
    ) -> HarnessCompletion:
        outcome, value_json, traces_json, usage_json = row
        usage = json.loads(str(usage_json))
        return HarnessCompletion(
            value=json.loads(str(value_json)),
            outcome=str(outcome),
            traces=traces_from_json(str(traces_json)),
            usage=ProviderUsage(**usage),
            from_cache=from_cache,
        )

    @classmethod
    def _row_values(
        cls,
        identity: CacheIdentity,
        completion: HarnessCompletion,
    ) -> tuple[str, str, str, str, str, str]:
        return (
            identity.digest,
            cls._identity_json(identity),
            completion.outcome,
            json.dumps(
                completion.value,
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
                sort_keys=True,
            ),
            traces_to_json(completion.traces),
            json.dumps(completion.usage.as_json(), separators=(",", ":"), sort_keys=True),
        )

    @staticmethod
    def _identity_json(identity: CacheIdentity) -> str:
        return json.dumps(
            {
                "manifest_sha256": identity.manifest_sha256,
                "model": identity.model,
                "presentation": identity.presentation,
                "probe_id": identity.probe_id,
                "prompt_hash": identity.prompt_hash,
                "protocol": identity.protocol.value,
                "reasoning_effort": identity.reasoning_effort,
                "request_hash": identity.request_hash,
                "variant_id": identity.variant_id,
            },
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
