"""Durable SQLite cache for resumable WP15 provider calls."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from im.probes.harness.models import (
    CacheIdentity,
    HarnessCompletion,
    ProviderUsage,
    traces_from_json,
    traces_to_json,
)

_INDETERMINATE_OUTCOMES = frozenset({"cancelled", "transport_error", "http_error"})


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
        self._connection.commit()

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
