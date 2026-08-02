"""Canonical WP15 request serialization and resume identities."""

from __future__ import annotations

import json
from hashlib import sha256

from im.probes.harness.models import CacheIdentity, HarnessProtocol


def canonical_request_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()


def digest(value: bytes) -> str:
    return f"sha256:{sha256(value).hexdigest()}"


def cache_identity(
    *,
    manifest_sha256: str,
    probe_id: str,
    protocol: HarnessProtocol,
    variant_id: str,
    presentation: str,
    model: str,
    reasoning_effort: str,
    prompt_hash: str,
    request_bytes: bytes,
) -> CacheIdentity:
    return CacheIdentity(
        manifest_sha256=manifest_sha256,
        probe_id=probe_id,
        protocol=protocol,
        variant_id=variant_id,
        presentation=presentation,
        model=model,
        reasoning_effort=reasoning_effort,
        prompt_hash=prompt_hash,
        request_hash=digest(request_bytes),
    )
