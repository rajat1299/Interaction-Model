"""Deterministic Phase-0a golden trace construction and replay."""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from pathlib import Path

from im.config import RuntimeConfig
from im.policy.base import ScriptedPolicy
from im.rollover import rollover
from im.scheduler import ManualClock
from im.schema.actions import DelegateAction
from im.server import ArtifactPaths, RuntimeSession, load_session_artifacts
from im.store import Store
from im.tools import ScriptedToolResult

TRACE_FORMAT = "im-golden-replay-v1"
TRACE_NAMES = (
    "plain_typing",
    "timer_cancel_race",
    "tool_integrate",
    "double_rollover",
)


@dataclass(frozen=True, slots=True)
class IngressRow:
    event_id: str
    received_utc: str
    received_mono_ns: int
    source: str
    kind: str
    payload: bytes

    def as_json_object(self) -> dict[str, object]:
        return {
            "id": self.event_id,
            "received_utc": self.received_utc,
            "received_mono_ns": self.received_mono_ns,
            "source": self.source,
            "kind": self.kind,
            "payload_b64": base64.b64encode(self.payload).decode("ascii"),
        }


@dataclass(frozen=True, slots=True)
class TraceRun:
    database_path: Path
    ingress_bytes: bytes
    segment_bytes: dict[int, bytes]


def _frame(
    text: str,
    *,
    activity: str,
    client_ts: int,
    input_type: str | None = "insertText",
) -> bytes:
    # Match browser JSON.stringify insertion order rather than canonical order;
    # G1 must prove raw ingress retention and policy rendering are separate.
    return json.dumps(
        {
            "text": text,
            "selection_start": len(text),
            "selection_end": len(text),
            "is_composing": False,
            "input_type": input_type,
            "activity": activity,
            "client_ts": client_ts,
        },
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")


def _snapshot_step(event_id: str, raw: bytes) -> dict[str, object]:
    return {
        "op": "snapshot",
        "expect_ingress_id": event_id,
        "payload_b64": base64.b64encode(raw).decode("ascii"),
    }


def _idle() -> dict[str, object]:
    return {"type": "idle", "reason": "awaiting_opening", "related_event_id": None}


def manifest_for(name: str) -> dict[str, object]:
    """Return the reviewed control fixture for one trace, separate from all lanes."""
    config = RuntimeConfig()
    if name == "plain_typing":
        policy_attempts = [_idle(), _idle(), _idle()]
        steps = [
            {"op": "bootstrap"},
            _snapshot_step("e_000002", _frame("helo", activity="active", client_ts=1)),
            {"op": "drain"},
            {"op": "advance_ms", "ms": 100},
            _snapshot_step("e_000003", _frame("hello", activity="active", client_ts=2)),
            {"op": "drain"},
            {"op": "advance_ms", "ms": 1_500},
            _snapshot_step(
                "e_000004",
                _frame("hello", activity="paused", client_ts=3, input_type=None),
            ),
            {"op": "drain"},
        ]
        tool_scripts: list[dict[str, object]] = []
    elif name == "timer_cancel_race":
        policy_attempts = [
            {
                "type": "schedule",
                "instruction": {
                    "event_id": "e_000002",
                    "start_utf16": 0,
                    "end_utf16": 20,
                    "text": "remind me to breathe",
                },
                "interval_ms": 1_000,
                "message": "breathe",
            },
            {
                "type": "cancel",
                "instruction": {
                    "event_id": "e_000006",
                    "start_utf16": 0,
                    "end_utf16": 4,
                    "text": "stop",
                },
                "target": {"kind": "timer", "timer_id": "t_001"},
            },
            {"type": "skip", "target_event_id": "e_000005", "reason": "canceled_timer"},
        ]
        steps = [
            {"op": "bootstrap"},
            _snapshot_step(
                "e_000002",
                _frame("remind me to breathe", activity="paused", client_ts=1),
            ),
            {"op": "drain"},
            {"op": "advance_ms", "ms": 1_000},
            {"op": "claim_due", "expect_ingress_ids": ["e_000005"]},
            _snapshot_step("e_000006", _frame("stop", activity="paused", client_ts=2)),
            {"op": "drain"},
        ]
        tool_scripts = []
    elif name == "tool_integrate":
        policy_attempts = [
            {
                "type": "delegate",
                "fact": {
                    "event_id": "e_000002",
                    "start_utf16": 0,
                    "end_utf16": 12,
                    "text": "lookup nonce",
                },
                "tool": "lookup",
                "args": {"query": "nonce"},
            },
            {"type": "integrate", "result_event_id": "e_000005", "text": "nonce n-42"},
        ]
        steps = [
            {"op": "bootstrap"},
            _snapshot_step("e_000002", _frame("lookup nonce", activity="paused", client_ts=1)),
            {"op": "drain"},
            {"op": "advance_ms", "ms": 100},
            {"op": "deliver_due", "expect_ingress_ids": ["e_000005"]},
            {"op": "drain"},
        ]
        tool_scripts = [{"latency_ms": 100, "status": "succeeded", "data": {"nonce": "n-42"}}]
    elif name == "double_rollover":
        config = RuntimeConfig(
            checkpoint_reserved_tokens=4_000,
            recent_events_budget_tokens=120,
        )
        policy_attempts = [_idle()]
        steps = [
            {"op": "bootstrap"},
            _snapshot_step("e_000002", _frame("roll over", activity="paused", client_ts=1)),
            {"op": "drain"},
            {"op": "force_rollover", "expect_event_id": "e_000003"},
            {"op": "advance_ms", "ms": 1},
            {"op": "force_rollover", "expect_event_id": "e_000004"},
        ]
        tool_scripts = []
    else:
        raise ValueError(f"unknown golden trace: {name}")
    return {
        "format": TRACE_FORMAT,
        "name": name,
        "config": config.as_json_object(),
        "policy_attempts": policy_attempts,
        "tool_scripts": tool_scripts,
        "steps": steps,
    }


def render_manifest(manifest: dict[str, object]) -> bytes:
    return (json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode(
        "utf-8"
    )


def parse_manifest(data: bytes) -> dict[str, object]:
    value = json.loads(data)
    if not isinstance(value, dict) or value.get("format") != TRACE_FORMAT:
        raise ValueError("unknown golden replay manifest format")
    return value


def _query_ingress(session: RuntimeSession) -> list[IngressRow]:
    rows = session.store._connection.execute(
        """
        SELECT id, received_utc, received_mono_ns, source, kind, payload
        FROM ingress ORDER BY rowid
        """
    ).fetchall()
    return [
        IngressRow(
            event_id=str(event_id),
            received_utc=str(received_utc),
            received_mono_ns=int(received_mono_ns),
            source=str(source),
            kind=str(kind),
            payload=bytes(payload),
        )
        for event_id, received_utc, received_mono_ns, source, kind, payload in rows
    ]


def render_ingress_jsonl(rows: list[IngressRow]) -> bytes:
    return b"\n".join(
        json.dumps(
            row.as_json_object(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        for row in rows
    )


def parse_ingress_jsonl(data: bytes) -> list[IngressRow]:
    result: list[IngressRow] = []
    for line in data.splitlines():
        value = json.loads(line)
        result.append(
            IngressRow(
                event_id=str(value["id"]),
                received_utc=str(value["received_utc"]),
                received_mono_ns=int(value["received_mono_ns"]),
                source=str(value["source"]),
                kind=str(value["kind"]),
                payload=base64.b64decode(value["payload_b64"], validate=True),
            )
        )
    return result


def _list(value: object, name: str) -> list[object]:
    if not isinstance(value, list):
        raise ValueError(f"golden manifest {name} must be an array")
    return value


def _dict(value: object, name: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"golden manifest {name} must be an object")
    return value


async def run_trace(
    manifest: dict[str, object],
    directory: Path,
    project_root: Path,
    *,
    expected_ingress: list[IngressRow] | None = None,
) -> TraceRun:
    """Execute the manifest through real source APIs and compare the ingress oracle."""
    if manifest.get("format") != TRACE_FORMAT:
        raise ValueError("unknown golden replay manifest format")
    name = str(manifest.get("name"))
    config = RuntimeConfig(**_dict(manifest.get("config"), "config"))  # type: ignore[arg-type]
    policy = ScriptedPolicy(_list(manifest.get("policy_attempts"), "policy_attempts"))
    tool_scripts = [
        _dict(item, "tool script") for item in _list(manifest.get("tool_scripts"), "tool_scripts")
    ]

    def tool_script(_action: DelegateAction) -> ScriptedToolResult:
        if not tool_scripts:
            raise AssertionError("golden policy delegated without a tool script")
        script = tool_scripts.pop(0)
        return ScriptedToolResult(
            latency_ms=int(script["latency_ms"]),
            status=str(script["status"]),
            data=script["data"],
        )

    artifacts = load_session_artifacts(ArtifactPaths.from_repository(project_root), config)
    session = RuntimeSession(
        session_id=f"golden-{name}",
        directory=directory,
        policy=policy,
        clock=ManualClock(),
        config=config,
        artifacts=artifacts,
        tool_script=tool_script,
    )
    oracle_by_id = (
        {} if expected_ingress is None else {row.event_id: row for row in expected_ingress}
    )
    clock = session.clock
    assert isinstance(clock, ManualClock)
    try:
        for raw_step in _list(manifest.get("steps"), "steps"):
            step = _dict(raw_step, "step")
            operation = step.get("op")
            if operation == "bootstrap":
                continue
            if operation == "snapshot":
                expected_id = str(step["expect_ingress_id"])
                raw = base64.b64decode(str(step["payload_b64"]), validate=True)
                if expected_id in oracle_by_id and oracle_by_id[expected_id].payload != raw:
                    raise AssertionError("snapshot control bytes differ from ingress oracle")
                actual_id = session.accept_snapshot(raw)
                if actual_id != expected_id:
                    raise AssertionError(f"expected {expected_id}, allocated {actual_id}")
                continue
            if operation == "drain":
                await session.tick.run_until_idle()
                continue
            if operation == "advance_ms":
                clock.advance_ms(int(step["ms"]))
                continue
            if operation == "claim_due":
                fires = session.scheduler.claim_due()
                actual_ids = [fire.event_id for fire in fires]
                if actual_ids != step["expect_ingress_ids"]:
                    raise AssertionError("timer ingress IDs differ from replay manifest")
                for fire in fires:
                    session.tick.enqueue_committed_ingress(fire.draft)
                continue
            if operation == "deliver_due":
                deliveries = session.tools.deliver_due()
                actual_ids = [delivery.event_id for delivery in deliveries]
                if actual_ids != step["expect_ingress_ids"]:
                    raise AssertionError("tool ingress IDs differ from replay manifest")
                for delivery in deliveries:
                    session.tick.enqueue_committed_ingress(delivery.as_policy_draft())
                continue
            if operation == "force_rollover":
                result = rollover(
                    session.store,
                    checkpoint_mono_ns=clock.monotonic_ns(),
                    config=config,
                )
                if result.event_id != step["expect_event_id"]:
                    raise AssertionError("checkpoint ID differs from replay manifest")
                continue
            raise ValueError(f"unknown golden replay operation: {operation}")

        if policy.remaining_count:
            raise AssertionError("golden replay left policy attempts unused")
        if tool_scripts:
            raise AssertionError("golden replay left tool scripts unused")
        actual_ingress = _query_ingress(session)
        if expected_ingress is not None and actual_ingress != expected_ingress:
            raise AssertionError("replayed ingress rows differ from the byte oracle")
        ingress_bytes = render_ingress_jsonl(actual_ingress)
        segment_bytes = {
            index: session.store.policy_bytes(index)
            for index in range(session.store.current_segment_index() + 1)
        }
    finally:
        await session.close()
    return TraceRun(
        database_path=directory / "session.sqlite3",
        ingress_bytes=ingress_bytes,
        segment_bytes=segment_bytes,
    )


def load_manifest(golden_root: Path, name: str) -> dict[str, object]:
    return parse_manifest((golden_root / name / "replay.json").read_bytes())


def load_ingress(golden_root: Path, name: str) -> list[IngressRow]:
    return parse_ingress_jsonl((golden_root / name / "ingress.jsonl").read_bytes())


def expected_segments(golden_root: Path, name: str) -> dict[int, bytes]:
    policy_root = golden_root / name / "policy"
    return {
        int(path.stem.split("-", 1)[1]): path.read_bytes()
        for path in sorted(policy_root.glob("segment-*.bin"))
    }


def reopened_segment_bytes(database_path: Path, indexes: list[int]) -> dict[int, bytes]:
    with Store(database_path) as store:
        return {index: store.policy_bytes(index) for index in indexes}
