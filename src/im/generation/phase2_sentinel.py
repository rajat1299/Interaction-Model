"""Closed, offline plan for the Phase 2 order-zero sentinel pack."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

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
_CONTRACT_SHA256 = "sha256:358737ced79eb7861e9737af62b78450454b321efe5435f7c109b234c9125994"


class SentinelContractError(ValueError):
    """The fixed sentinel contract is malformed or has drifted."""


class SentinelPlanError(ValueError):
    """The materialized offline sentinel plan is unsafe or inconsistent."""


@dataclass(frozen=True, slots=True)
class SentinelPlan:
    canonical_bytes: bytes
    review_bytes: bytes
    routes: tuple[ReviewRoute, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.canonical_bytes, bytes) or not isinstance(self.review_bytes, bytes):
            raise SentinelPlanError("sentinel plan artifacts must be immutable bytes")
        if not isinstance(self.routes, tuple):
            raise SentinelPlanError("sentinel routes must be immutable")
        _parse_plan(self.canonical_bytes)

    def as_json_object(self) -> dict[str, object]:
        """Return a fresh parse so callers cannot mutate retained plan state."""
        return _parse_plan(self.canonical_bytes)


def build_sentinel_plan(path: Path = DEFAULT_SENTINEL_CONTRACT) -> SentinelPlan:
    """Prove the D2 floor under the counterfactual teacher-equals-oracle condition."""
    contract = _load_contract(path)
    streams = _object_list(contract.get("streams"), "contract streams")
    targets = _object_list(contract.get("targets"), "contract targets")
    stream_by_id = {stream["logical_stream_id"]: stream for stream in streams}
    planning_identities = {
        stream["logical_stream_id"]: _planning_identity(stream) for stream in streams
    }
    decisions: list[DecisionEvidence] = []
    for target in targets:
        stream = stream_by_id[target["logical_stream_id"]]
        cell = _object(target.get("cell"), "target cell")
        try:
            decisions.append(
                DecisionEvidence(
                    stream_sha256=planning_identities[stream["logical_stream_id"]],
                    decision_policy_seq=target["decision_policy_seq"],
                    wave_id=contract["wave_id"],
                    cell=TrustCellKey(
                        HarnessProtocol(cell["protocol"]),
                        CorpusFamily(cell["family"]),
                        FloorClass(cell["floor"]),
                    ),
                    template_id=stream["template_id"],
                    source_unit_id=stream["source_unit_id"],
                    oracle_action=target["oracle_action"],
                    # Counterfactual proof only; no teacher evidence is emitted or inferred.
                    teacher_action=target["oracle_action"],
                    causal_state_class=target["causal_state_class"],
                    boundary_class=BoundaryClass(target["boundary_class"]),
                    risk_flags=tuple(target["risk_flags"]),
                    idle_boundary=target["idle_boundary"],
                )
            )
        except (KeyError, TypeError, ValueError) as error:
            raise SentinelContractError(
                "sentinel target is incompatible with the router"
            ) from error
    routes = route_wave(tuple(decisions), {}, sampling_seed="phase2-sentinel-v1")
    if not all(route.review_required and route.mandatory for route in routes):
        raise SentinelContractError("sentinel target did not route to mandatory review")

    plan_bytes = canonical_artifact_bytes(
        {
            "contract_sha256": _CONTRACT_SHA256,
            "format_version": 1,
            "kind": "phase2-sentinel-plan",
            "pack_id": contract["pack_id"],
            "planning_identity_note": contract["planning_identity_note"],
            "planned_streams": [
                {
                    **stream,
                    "planning_stream_identity_sha256": planning_identities[
                        stream["logical_stream_id"]
                    ],
                }
                for stream in streams
            ],
            "targets": [
                {
                    **target,
                    "mandatory_route_if_teacher_agrees": {
                        "mandatory": route.mandatory,
                        "reasons": list(route.reasons),
                        "review_required": route.review_required,
                        "sample_rate": route.sample_rate,
                    },
                    "planning_decision_identity": decision.identity,
                    "planning_stream_identity_sha256": planning_identities[
                        target["logical_stream_id"]
                    ],
                }
                for target, decision, route in zip(targets, decisions, routes, strict=True)
            ],
            "teacher_invocation_count": 0,
            "wave_id": contract["wave_id"],
        }
    )
    return SentinelPlan(plan_bytes, _review_bytes(plan_bytes), routes)


def materialize_sentinel_plan(
    output: Path = DEFAULT_SENTINEL_OUTPUT,
    *,
    contract_path: Path = DEFAULT_SENTINEL_CONTRACT,
) -> SentinelPlan:
    """Atomically reserve a new output directory; existing output is never overwritten."""
    plan = build_sentinel_plan(contract_path)
    parent = output.parent.resolve()
    parent.mkdir(parents=True, exist_ok=True)
    output = parent / output.name
    try:
        output.mkdir()
    except FileExistsError:
        raise FileExistsError(f"sentinel output already exists: {output}") from None
    except OSError as error:
        raise SentinelPlanError(f"sentinel output cannot be reserved: {output}") from error
    for name, data in _expected_files(plan).items():
        (output / name).write_bytes(data)
    verify_sentinel_plan(output, contract_path=contract_path)
    return plan


def verify_sentinel_plan(
    root: Path = DEFAULT_SENTINEL_OUTPUT,
    *,
    contract_path: Path = DEFAULT_SENTINEL_CONTRACT,
) -> SentinelPlan:
    """Exact-compare the closed three-file packet without following symlinks."""
    if root.is_symlink():
        raise SentinelPlanError("sentinel output must be a real directory")
    root = root.resolve()
    if not root.is_dir():
        raise SentinelPlanError("sentinel output must be a real directory")
    paths = {path.name: path for path in root.iterdir()}
    plan = build_sentinel_plan(contract_path)
    expected = _expected_files(plan)
    if set(paths) != set(expected):
        raise SentinelPlanError("sentinel output inventory is not closed")
    if any(path.is_symlink() or not path.is_file() for path in paths.values()):
        raise SentinelPlanError("sentinel output contains an unsafe path")
    for name, data in expected.items():
        try:
            actual = paths[name].read_bytes()
        except OSError as error:
            raise SentinelPlanError(f"sentinel artifact is not readable: {name}") from error
        if actual != data:
            raise SentinelPlanError(f"sentinel artifact is tampered or unsafe: {name}")
    return plan


def _load_contract(path: Path) -> dict[str, object]:
    try:
        raw = path.read_bytes()
        value = json.loads(raw)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SentinelContractError("sentinel contract is not readable JSON") from error
    if not isinstance(value, dict) or canonical_artifact_bytes(value) != raw:
        raise SentinelContractError("sentinel contract must be canonical JSON")
    if _digest(raw) != _CONTRACT_SHA256:
        raise SentinelContractError("sentinel v1 contract differs from its expected SHA-256")
    return value


def _object(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise SentinelContractError(f"{label} must be an object")
    return value


def _object_list(value: object, label: str) -> tuple[dict[str, object], ...]:
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise SentinelContractError(f"{label} must be an object list")
    return tuple(value)


def _parse_plan(data: bytes) -> dict[str, object]:
    try:
        value = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SentinelPlanError("sentinel plan is not readable JSON") from error
    if not isinstance(value, dict) or canonical_artifact_bytes(value) != data:
        raise SentinelPlanError("sentinel plan is not canonical JSON")
    return value


def _planning_identity(stream: dict[str, object]) -> str:
    return _digest(
        canonical_artifact_bytes(
            {
                "contract_sha256": _CONTRACT_SHA256,
                "logical_stream_id": stream["logical_stream_id"],
                "source_unit_id": stream["source_unit_id"],
                "template_id": stream["template_id"],
            }
        )
    )


def _digest(value: bytes) -> str:
    return f"sha256:{sha256(value).hexdigest()}"


def _review_bytes(plan_bytes: bytes) -> bytes:
    targets = _object_list(_parse_plan(plan_bytes).get("targets"), "plan targets")
    lines = [
        "# WP2-1 sentinel plan",
        "",
        "Preliminary WP2-1 gate for the eight fixed D6 boundaries; it is not the WP2-1 exit.",
        (
            "Teacher invocations: 0; actual teacher evidence is absent. The mandatory-route column "
            "is the counterfactual where teacher action equals oracle action."
        ),
        "",
        (
            "Planning SHA-256 values identify logical planned streams only; they are not "
            "generated-stream digests."
        ),
        "",
        "| Target | Oracle action | Mandatory route if teacher agrees |",
        "| --- | --- | --- |",
    ]
    for target in targets:
        action = _object(target.get("oracle_action"), "plan oracle action")
        route = _object(
            target.get("mandatory_route_if_teacher_agrees"), "plan counterfactual route"
        )
        reasons = route.get("reasons")
        if not isinstance(reasons, list) or not all(isinstance(reason, str) for reason in reasons):
            raise SentinelPlanError("plan counterfactual route reasons are invalid")
        reason = action.get("reason")
        action_label = str(action["type"]) + (f"({reason})" if reason is not None else "")
        lines.append(f"| `{target['target_id']}` | `{action_label}` | `{', '.join(reasons)}` |")
    lines.extend(
        [
            "",
            (
                "Offline executable scenario construction needs no authorization. Owner "
                "authorization is required only before the exact provider/model call or upload."
            ),
            "",
        ]
    )
    return "\n".join(lines).encode()


def _expected_files(plan: SentinelPlan) -> dict[str, bytes]:
    payloads = {
        "REVIEW.md": plan.review_bytes,
        "sentinel-plan.json": plan.canonical_bytes,
    }
    checksums = "".join(
        f"{sha256(data).hexdigest()}  {name}\n" for name, data in sorted(payloads.items())
    ).encode("ascii")
    return {**payloads, "SHA256SUMS": checksums}


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="materialize the offline Phase 2 sentinel plan")
    parser.add_argument("output", nargs="?", type=Path, default=DEFAULT_SENTINEL_OUTPUT)
    parser.add_argument("--contract", type=Path, default=DEFAULT_SENTINEL_CONTRACT)
    args = parser.parse_args(argv)
    materialize_sentinel_plan(args.output, contract_path=args.contract)


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    main()
