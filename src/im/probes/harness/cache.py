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


class HarnessCache:
    """Small synchronous cache used only at async task boundaries on the event-loop thread."""

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
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
        outcome, value_json, traces_json, usage_json = row
        usage = json.loads(usage_json)
        return HarnessCompletion(
            value=json.loads(value_json),
            outcome=str(outcome),
            traces=traces_from_json(str(traces_json)),
            usage=ProviderUsage(**usage),
            from_cache=True,
        )

    def put(self, identity: CacheIdentity, completion: HarnessCompletion) -> None:
        if completion.outcome == "cancelled":
            raise ValueError("indeterminate cancelled calls require an explicit retry decision")
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
            (
                identity.digest,
                self._identity_json(identity),
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
            ),
        )
        self._connection.commit()

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
