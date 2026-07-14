"""Deterministic JSON Schema export and freeze-hash helpers."""

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from im.schema.actions import ACTION_ADAPTER
from im.schema.events import EVENT_ADAPTER

ACTION_SCHEMA_FILENAME = "action-v1.json"
EVENT_SCHEMA_FILENAME = "event-v1.json"


def canonical_schema_bytes(schema: dict[str, object]) -> bytes:
    """Render a JSON Schema using the frozen schema-hash byte contract."""
    return json.dumps(
        schema,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def action_schema_bytes() -> bytes:
    return canonical_schema_bytes(ACTION_ADAPTER.json_schema())


def event_schema_bytes() -> bytes:
    return canonical_schema_bytes(EVENT_ADAPTER.json_schema())


def sha256_digest(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


@dataclass(frozen=True, slots=True)
class SchemaHashes:
    event_schema: str
    action_schema: str
    combined_schema: str


def schema_hashes(event_schema: bytes, action_schema: bytes) -> SchemaHashes:
    """Hash individual exports and the frozen event-LF-action preimage."""
    return SchemaHashes(
        event_schema=sha256_digest(event_schema),
        action_schema=sha256_digest(action_schema),
        combined_schema=sha256_digest(event_schema + b"\n" + action_schema),
    )


def export_schema_artifacts(project_root: Path) -> SchemaHashes:
    """Export schemas without mutating the separately approved freeze manifest."""
    event_schema = event_schema_bytes()
    action_schema = action_schema_bytes()
    hashes = schema_hashes(event_schema, action_schema)
    schema_dir = project_root / "spec" / "schema"
    schema_dir.mkdir(parents=True, exist_ok=True)
    (schema_dir / EVENT_SCHEMA_FILENAME).write_bytes(event_schema)
    (schema_dir / ACTION_SCHEMA_FILENAME).write_bytes(action_schema)
    return hashes
