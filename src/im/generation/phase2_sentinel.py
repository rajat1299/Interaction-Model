"""Closed, offline plan for the Phase 2 order-zero sentinel pack."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from re import fullmatch
from tempfile import TemporaryDirectory

from im.assets.model import CorpusFamily, canonical_artifact_bytes
from im.generation.phase2_review import (
    BoundaryClass,
    DecisionEvidence,
    FloorClass,
    ReviewRoute,
    TrustCellKey,
    route_wave,
)
from im.probes.harness.models import HarnessProtocol

_REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SENTINEL_CONTRACT = _REPOSITORY_ROOT / "spec" / "phase2-sentinel-v1.json"
DEFAULT_SENTINEL_OUTPUT = _REPOSITORY_ROOT / "review" / "phase2" / "sentinel-0-plan"
_DIGEST = r"sha256:[0-9a-f]{64}"
_PLAN_FILES = ("REVIEW.md", "sentinel-plan.json")
_CONTRACT_KEYS = {
    "format_version",
    "kind",
    "pack_id",
    "planning_identity_note",
    "streams",
    "teacher_invocation_count",
    "targets",
    "wave_id",
}
_STREAM_KEYS = {"logical_stream_id", "source_unit_id", "target_ids", "template_id"}
_TARGET_KEYS = {
    "boundary_class",
    "causal_state_class",
    "cell",
    "decision_policy_seq",
    "idle_boundary",
    "logical_stream_id",
    "oracle_action",
    "risk_flags",
    "target_id",
}
_CELL_KEYS = {"family", "floor", "protocol"}


class SentinelContractError(ValueError):
    """The fixed sentinel contract is malformed or has drifted."""


class SentinelPlanError(ValueError):
    """The materialized offline sentinel plan is unsafe or inconsistent."""


@dataclass(frozen=True, slots=True)
class SentinelPlan:
    value: dict[str, object]
    routes: tuple[ReviewRoute, ...]

    def as_json_object(self) -> dict[str, object]:
        return self.value

    @property
    def canonical_bytes(self) -> bytes:
        return canonical_artifact_bytes(self.as_json_object())


_TARGET_REQUIREMENTS = (
    (
        "partial_instruction", "partial", 0, "idle", "typing_active",
        BoundaryClass.PARTIAL_INSTRUCTION, CorpusFamily.NEUTRAL_TYPING, FloorClass.CLOSED,
        (), "partial_instruction",
    ),
    (
        "active_floor_idle", "response-active", 0, "idle", "awaiting_opening",
        BoundaryClass.ACTIVE_FLOOR_RESPONSE, CorpusFamily.NEUTRAL_TYPING, FloorClass.OWNED,
        ("active_floor_response_boundary",), None,
    ),
    (
        "open_floor_respond", "response-open", 0, "respond", None,
        BoundaryClass.ACTIVE_FLOOR_RESPONSE, CorpusFamily.NEUTRAL_TYPING, FloorClass.OPEN,
        ("active_floor_response_boundary",), None,
    ),
    (
        "schedule_similar_distinct", "timer-pair", 0, "schedule", None,
        BoundaryClass.SCHEDULE_SIMILAR_DISTINCT, CorpusFamily.TIMER_NORMAL, FloorClass.CLOSED,
        ("schedule_semantic_duplicate_boundary",), None,
    ),
    (
        "schedule_semantic_duplicate", "timer-pair", 1, "idle", "already_handled",
        BoundaryClass.SCHEDULE_SEMANTIC_DUPLICATE, CorpusFamily.TIMER_NORMAL, FloorClass.CLOSED,
        ("schedule_semantic_duplicate_boundary",), None,
    ),
    (
        "lookup_refresh_superseded", "lookup-pair", 0, "skip", "superseded_query",
        BoundaryClass.LOOKUP_REFRESH_SUPERSEDED, CorpusFamily.LOOKUP_STALE, FloorClass.CLOSED,
        ("skip_reason_selection",), None,
    ),
    (
        "lookup_abandoned_stale", "lookup-pair", 1, "skip", "stale_tool_result",
        BoundaryClass.LOOKUP_ABANDONED_STALE, CorpusFamily.LOOKUP_STALE, FloorClass.CLOSED,
        ("skip_reason_selection",), None,
    ),
    (
        "ambiguous_cancel", "ambiguous-cancel", 0, "idle", "ambiguous",
        BoundaryClass.AMBIGUOUS_CANCEL, CorpusFamily.TIMER_CANCEL, FloorClass.CLOSED,
        ("cancel_semantic_referent_resolution",), None,
    ),
)


def _load_contract(path: Path) -> tuple[dict[str, object], str]:
    try:
        raw = path.read_bytes()
        value = json.loads(raw)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SentinelContractError("sentinel contract is not readable canonical JSON") from error
    if not isinstance(value, dict) or canonical_artifact_bytes(value) != raw:
        raise SentinelContractError("sentinel contract must be canonical JSON")
    _validate_contract(value)
    return value, _digest(raw)


def build_sentinel_plan(path: Path = DEFAULT_SENTINEL_CONTRACT) -> SentinelPlan:
    """Derive the no-provider plan and prove every target is mandatory review."""
    contract, contract_sha256 = _load_contract(path)
    streams = _streams(contract)
    stream_by_id = {str(stream["logical_stream_id"]): stream for stream in streams}
    decisions: list[DecisionEvidence] = []
    targets = _targets(contract)
    for target in targets:
        stream = stream_by_id[str(target["logical_stream_id"])]
        cell = target["cell"]
        assert isinstance(cell, dict)  # closed by _validate_contract
        try:
            decisions.append(
                DecisionEvidence(
                    stream_sha256=_planning_identity(contract_sha256, stream),
                    decision_policy_seq=int(target["decision_policy_seq"]),
                    wave_id=str(contract["wave_id"]),
                    cell=TrustCellKey(
                        HarnessProtocol(cell["protocol"]),
                        CorpusFamily(cell["family"]),
                        FloorClass(cell["floor"]),
                    ),
                    template_id=str(stream["template_id"]),
                    source_unit_id=str(stream["source_unit_id"]),
                    oracle_action=target["oracle_action"],
                    teacher_action=None,
                    causal_state_class=str(target["causal_state_class"]),
                    boundary_class=BoundaryClass(target["boundary_class"]),
                    risk_flags=tuple(target["risk_flags"]),
                    idle_boundary=target["idle_boundary"],
                )
            )
        except (KeyError, TypeError, ValueError) as error:
            raise SentinelContractError(
                "sentinel target is incompatible with the Phase 2 router"
            ) from error
    routes = route_wave(tuple(decisions), {}, sampling_seed="phase2-sentinel-v1")
    if not all(route.review_required and route.mandatory for route in routes):
        raise SentinelContractError("sentinel target did not route to mandatory review")
    identities = {
        str(stream["logical_stream_id"]): _planning_identity(contract_sha256, stream)
        for stream in streams
    }
    return SentinelPlan(
        {
            "contract_sha256": contract_sha256,
            "format_version": 1,
            "kind": "phase2-sentinel-plan",
            "pack_id": contract["pack_id"],
            "planning_identity_note": contract["planning_identity_note"],
            "planned_streams": [
                {
                    **stream,
                    "planning_stream_identity_sha256": identities[
                        str(stream["logical_stream_id"])
                    ],
                }
                for stream in streams
            ],
            "targets": [
                {
                    **target,
                    "planning_decision_identity": decision.identity,
                    "planning_stream_identity_sha256": identities[str(target["logical_stream_id"])],
                    "review_route": {
                        "mandatory": route.mandatory,
                        "reasons": list(route.reasons),
                        "review_required": route.review_required,
                        "sample_rate": route.sample_rate,
                    },
                    "teacher_action": None,
                }
                for target, decision, route in zip(targets, decisions, routes, strict=True)
            ],
            "teacher_invocation_count": 0,
            "wave_id": contract["wave_id"],
        },
        routes,
    )


def materialize_sentinel_plan(
    output: Path = DEFAULT_SENTINEL_OUTPUT,
    *,
    contract_path: Path = DEFAULT_SENTINEL_CONTRACT,
) -> SentinelPlan:
    """Atomically publish a new plan directory; existing output is never overwritten."""
    plan = build_sentinel_plan(contract_path)
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"sentinel output already exists: {output}")
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=f".{output.name}.", dir=output.parent) as temporary:
        root = Path(temporary) / output.name
        root.mkdir()
        (root / "sentinel-plan.json").write_bytes(plan.canonical_bytes)
        (root / "REVIEW.md").write_bytes(_review_bytes(plan))
        _write_sha256s(root)
        verify_sentinel_plan(root, contract_path=contract_path)
        if output.exists() or output.is_symlink():
            raise FileExistsError(f"sentinel output already exists: {output}")
        root.rename(output)
    return plan


def verify_sentinel_plan(
    root: Path = DEFAULT_SENTINEL_OUTPUT,
    *,
    contract_path: Path = DEFAULT_SENTINEL_CONTRACT,
) -> SentinelPlan:
    """Check exact inventory, canonical bytes, safe checksums, and router coverage offline."""
    if root.is_symlink():
        raise SentinelPlanError("sentinel output must be a real directory")
    root = root.resolve()
    if not root.is_dir():
        raise SentinelPlanError("sentinel output must be a real directory")
    files = {
        path.relative_to(root).as_posix(): path
        for path in root.rglob("*")
        if path.is_file() or path.is_symlink()
    }
    if set(files) != {*_PLAN_FILES, "SHA256SUMS"}:
        raise SentinelPlanError("sentinel output inventory is not closed")
    if any(path.is_symlink() for path in files.values()):
        raise SentinelPlanError("sentinel output may not contain symlinks")
    _verify_sha256s(root)
    plan = build_sentinel_plan(contract_path)
    expected = plan.canonical_bytes
    actual = _read(root / "sentinel-plan.json", "sentinel plan")
    try:
        value = json.loads(actual)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SentinelPlanError("sentinel plan is not readable canonical JSON") from error
    if not isinstance(value, dict) or canonical_artifact_bytes(value) != actual:
        raise SentinelPlanError("sentinel plan is not canonical JSON")
    if actual != expected:
        raise SentinelPlanError("sentinel plan does not match the closed contract")
    if _read(root / "REVIEW.md", "sentinel review") != _review_bytes(plan):
        raise SentinelPlanError("sentinel review does not match the closed plan")
    return plan


def _validate_contract(value: dict[str, object]) -> None:
    if set(value) != _CONTRACT_KEYS:
        raise SentinelContractError("sentinel contract top-level shape is not closed")
    if (
        value.get("format_version") != 1
        or value.get("kind") != "phase2-sentinel-v1"
        or value.get("pack_id") != "sentinel-0"
        or value.get("wave_id") != "sentinel-0"
        or value.get("teacher_invocation_count") != 0
    ):
        raise SentinelContractError("sentinel contract identity is invalid")
    note = value.get("planning_identity_note")
    if not isinstance(note, str) or "planning" not in note.lower() or "not" not in note.lower():
        raise SentinelContractError("planning identities must be explicitly labeled")

    streams = _streams(value)
    stream_ids = tuple(str(stream["logical_stream_id"]) for stream in streams)
    expected_stream_ids = tuple(dict.fromkeys(item[1] for item in _TARGET_REQUIREMENTS))
    if stream_ids != expected_stream_ids:
        raise SentinelContractError("sentinel stream inventory drifted")
    if not all(
        isinstance(stream["source_unit_id"], str)
        and stream["source_unit_id"].strip()
        and isinstance(stream["template_id"], str)
        and stream["template_id"].strip()
        for stream in streams
    ):
        raise SentinelContractError("sentinel source/template identifiers must be logical text")
    source_ids = {stream["source_unit_id"] for stream in streams}
    if len(source_ids) != 5:
        raise SentinelContractError("sentinel plan must retain five source units")
    sources = {str(stream["logical_stream_id"]): stream["source_unit_id"] for stream in streams}
    if sources["response-active"] != sources["response-open"]:
        raise SentinelContractError("response twins must share one source unit")

    targets = _targets(value)
    expected_target_ids = [item[0] for item in _TARGET_REQUIREMENTS]
    if [target.get("target_id") for target in targets] != expected_target_ids:
        raise SentinelContractError("sentinel target inventory is not the closed D6 set")
    identities = {
        (target["logical_stream_id"], target["decision_policy_seq"]) for target in targets
    }
    if len(identities) != len(targets):
        raise SentinelContractError("sentinel target identities must be unique")
    for target, required in zip(targets, _TARGET_REQUIREMENTS, strict=True):
        if set(target) != _TARGET_KEYS or not isinstance(target.get("cell"), dict):
            raise SentinelContractError("sentinel target shape is not closed")
        if set(target["cell"]) != _CELL_KEYS:
            raise SentinelContractError("sentinel target cell is not closed")
        action = target["oracle_action"]
        cell = target["cell"]
        if not isinstance(action, dict):
            raise SentinelContractError("sentinel target action is not an object")
        actual = (
            target["target_id"],
            target["logical_stream_id"],
            target["decision_policy_seq"],
            action.get("type"),
            action.get("reason"),
            target["boundary_class"],
            cell["family"],
            cell["floor"],
            tuple(target["risk_flags"]) if isinstance(target["risk_flags"], list) else None,
            target["idle_boundary"],
        )
        expected = (
            required[0],
            required[1],
            required[2],
            required[3],
            required[4],
            required[5].value,
            required[6].value,
            required[7].value,
            required[8],
            required[9],
        )
        if actual != expected:
            raise SentinelContractError("sentinel target action, risk flag, or cell mismatches D6")
        if not isinstance(target["risk_flags"], list) or target["risk_flags"] != sorted(
            set(target["risk_flags"])
        ):
            raise SentinelContractError("sentinel risk flags must be sorted and unique")
    by_stream = {
        stream_id: tuple(
            target["target_id"] for target in targets if target["logical_stream_id"] == stream_id
        )
        for stream_id in stream_ids
    }
    if any(
        tuple(stream["target_ids"]) != by_stream[stream["logical_stream_id"]]
        for stream in streams
    ):
        raise SentinelContractError("sentinel stream targets do not close over the D6 inventory")


def _streams(value: dict[str, object]) -> list[dict[str, object]]:
    streams = value.get("streams")
    if not isinstance(streams, list) or len(streams) != 6:
        raise SentinelContractError("sentinel contract must contain six planned streams")
    if not all(isinstance(stream, dict) and set(stream) == _STREAM_KEYS for stream in streams):
        raise SentinelContractError("sentinel stream shape is not closed")
    return streams


def _targets(value: dict[str, object]) -> list[dict[str, object]]:
    targets = value.get("targets")
    if not isinstance(targets, list) or not all(isinstance(target, dict) for target in targets):
        raise SentinelContractError("sentinel target inventory is invalid")
    if len(targets) != 8:
        raise SentinelContractError("sentinel contract must contain eight D6 targets")
    return targets


def _planning_identity(contract_sha256: str, stream: dict[str, object]) -> str:
    """Hash a plan descriptor only; it is never an identity of generated stream bytes."""
    return _digest(
        canonical_artifact_bytes(
            {
                "contract_sha256": contract_sha256,
                "logical_stream_id": stream["logical_stream_id"],
                "source_unit_id": stream["source_unit_id"],
                "template_id": stream["template_id"],
            }
        )
    )


def _digest(value: bytes) -> str:
    return f"sha256:{sha256(value).hexdigest()}"


def _review_bytes(plan: SentinelPlan) -> bytes:
    targets = plan.as_json_object()["targets"]
    assert isinstance(targets, list)
    lines = [
        "# WP2-1 sentinel plan",
        "",
        "Offline order-zero planning artifact for the eight fixed D6 boundaries.",
        (
            "Teacher invocations: 0. This is not executable scenario generation or a "
            "teacher-label packet."
        ),
        "",
        (
            "Planning SHA-256 values identify logical planned streams only; they are not "
            "generated-stream digests."
        ),
        "",
        "| Target | Oracle action | Mandatory route |",
        "| --- | --- | --- |",
    ]
    for target in targets:
        assert isinstance(target, dict)
        action = target["oracle_action"]
        assert isinstance(action, dict)
        reason = action.get("reason")
        label = str(action["type"]) + (f"({reason})" if reason is not None else "")
        route = target["review_route"]
        assert isinstance(route, dict)
        lines.append(f"| `{target['target_id']}` | `{label}` | `{', '.join(route['reasons'])}` |")
    lines.extend(
        [
            "",
            (
                "Run executable scenario generation only after the owner authorizes the pinned "
                "teacher run plan."
            ),
            "",
        ]
    )
    return "\n".join(lines).encode()


def _write_sha256s(root: Path) -> None:
    entries = "".join(
        f"{sha256((root / name).read_bytes()).hexdigest()}  {name}\n"
        for name in sorted(_PLAN_FILES)
    )
    (root / "SHA256SUMS").write_text(entries, encoding="ascii")


def _verify_sha256s(root: Path) -> None:
    data = _read(root / "SHA256SUMS", "sentinel checksums")
    try:
        entries = data.decode("ascii").splitlines()
    except UnicodeDecodeError as error:
        raise SentinelPlanError("sentinel SHA256SUMS is not ASCII") from error
    expected: dict[str, str] = {}
    for entry in entries:
        digest, separator, relative = entry.partition("  ")
        if (
            not separator
            or fullmatch(r"[0-9a-f]{64}", digest) is None
            or relative not in _PLAN_FILES
            or relative in expected
        ):
            raise SentinelPlanError("sentinel SHA256SUMS has an unsafe entry")
        expected[relative] = digest
    if tuple(expected) != tuple(sorted(_PLAN_FILES)):
        raise SentinelPlanError("sentinel SHA256SUMS inventory is not closed")
    if any(
        sha256(_read(root / name, name)).hexdigest() != digest
        for name, digest in expected.items()
    ):
        raise SentinelPlanError("sentinel SHA256SUMS digest mismatch")


def _read(path: Path, label: str) -> bytes:
    try:
        return path.read_bytes()
    except OSError as error:
        raise SentinelPlanError(f"{label} is not readable") from error


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="materialize the offline Phase 2 sentinel plan")
    parser.add_argument("output", nargs="?", type=Path, default=DEFAULT_SENTINEL_OUTPUT)
    parser.add_argument("--contract", type=Path, default=DEFAULT_SENTINEL_CONTRACT)
    args = parser.parse_args(argv)
    materialize_sentinel_plan(args.output, contract_path=args.contract)


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    main()
