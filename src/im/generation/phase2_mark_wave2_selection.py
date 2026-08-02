"""Deterministic whole-stream selection and owner review for mark Wave-2."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

from im.assets.model import canonical_artifact_bytes
from im.generation.packaging import PackageManifest
from im.generation.phase2_lookup_wave0 import (
    _raw_stream,
    _runtime_files,
    load_lookup_wave0_inputs,
)
from im.generation.phase2_lookup_wave2 import _response_assets
from im.generation.phase2_mark_wave2 import (
    ExecutedMarkWave2,
    _program_specs,
    _routes,
)
from im.generation.phase2_review import DecisionEvidence, LabelOrigin, ReviewRoute
from im.generation.phase2_review_projection import (
    CandidateLicense,
    DecisionProjectionInput,
    project_phase2_review_evidence,
)
from im.generation.publication import publish_directory_transaction
from im.generation.scenarios import execute_scenario, validate_generated_scenario
from im.probes.harness.identity import digest

_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MARK_WAVE2_SELECTION_OUTPUT = _ROOT / "review" / "phase2" / "mark-wave-2-selection-review"
_SOURCE = Path("review/phase2/mark-wave-2-v8")
_EXECUTION = Path("review/phase2/mark-wave-2-chat-execution")
_EXPECTED_SOURCE = "sha256:444fa5c3e99452ebea1082b93a48d8d756cb7e6c9b64e62cbd6ac9371fb6ef0f"
_EXPECTED_EXECUTION = "sha256:748086f00e321467ab8405ce82a65532de87ea5fcda4b3995ce83068373eef25"
_QUARANTINED = frozenset(
    {
        "negative-core-02",
        "negative-core-12",
        "positive-core-01",
        "positive-reserve-02",
    }
)
_SELECTED = frozenset(
    {
        "positive-core-00",
        *{f"positive-core-{value:02d}" for value in range(2, 9)},
        "positive-reserve-00",
        "positive-reserve-01",
        "positive-wide-00",
        "positive-dense-00",
        *{
            f"mark_activation_positive-response-{value:02d}-{floor}"
            for value in range(1, 5)
            for floor in ("active", "yielded")
        },
        "negative-core-00",
        "negative-core-01",
        *{f"negative-core-{value:02d}" for value in range(3, 12)},
        *{f"negative-lifecycle-{value:02d}" for value in range(4)},
        *{f"negative-boundary-{value:02d}" for value in range(4)},
        *{
            f"mark_lifecycle_negative-response-{value:02d}-{floor}"
            for value in range(1, 5)
            for floor in ("active", "yielded")
        },
    }
)
_APPROVED_TEACHER_ERRORS = frozenset(
    {
        "t2mw2.negative-boundary-01.d001.a1",
        "t2mw2.negative-core-10.d005.a1",
        "t2mw2.negative-core-09.d005.a1",
        "t2mw2.negative-core-04.d006.a1",
        "t2mw2.negative-core-03.d006.a1",
        "t2mw2.negative-core-04.d007.a1",
        "t2mw2.negative-core-03.d007.a1",
    }
)
_EXPECTED_ACTIONS = {
    "mark_activation_positive": {"idle": 63, "mark": 87, "respond": 4},
    "mark_lifecycle_negative": {"idle": 75, "mark": 33, "respond": 4},
}


class MarkWave2SelectionError(ValueError):
    """The selected mark Wave-2 evidence is incomplete or has drifted."""


@dataclass(frozen=True, slots=True)
class MarkWave2SelectionArtifact:
    files: dict[str, bytes]
    decision_count: int
    pending_review_count: int
    stream_count: int


def selected_logical_stream_ids() -> frozenset[str]:
    """Return the frozen selection without consulting teacher agreement."""
    return _SELECTED


async def build_mark_wave2_selection(
    *, repository_root: Path = _ROOT
) -> MarkWave2SelectionArtifact:
    """Rebuild the selected streams and emit one checksum-bound owner packet."""
    root = repository_root.resolve()
    source_root = root / _SOURCE
    execution_root = root / _EXECUTION
    if _verify_directory(source_root) != _EXPECTED_SOURCE:
        raise MarkWave2SelectionError("mark Wave-2 source packet drifted")
    if _verify_directory(execution_root) != _EXPECTED_EXECUTION:
        raise MarkWave2SelectionError("mark Wave-2 teacher execution drifted")
    disposition = (execution_root / "OWNER-DISPOSITION.md").read_text()
    if any(value not in disposition for value in _QUARANTINED):
        raise MarkWave2SelectionError("owner quarantine authority is incomplete")

    plan = _object(source_root / "teacher-plan.json", "teacher plan")
    comparison = _object(execution_root / "comparison.json", "comparison")
    targets = _targets(plan)
    comparison_rows = _comparison_rows(comparison)
    specs = tuple(
        spec
        for spec in _program_specs(load_lookup_wave0_inputs(), _response_assets(root))
        if spec.logical_stream_id in _SELECTED
    )
    if len(specs) != 47 or {spec.logical_stream_id for spec in specs} != _SELECTED:
        raise MarkWave2SelectionError("selected stream inventory drifted")

    with TemporaryDirectory(prefix="phase2-mark-wave2-selection-") as temporary:
        executed = []
        for spec in specs:
            generated = await execute_scenario(
                spec.program,
                session_id=f"phase2-mark-wave2-{spec.logical_stream_id}",
                directory=Path(temporary) / spec.logical_stream_id,
                repository_root=root,
            )
            validate_generated_scenario(generated)
            executed.append(ExecutedMarkWave2(spec, generated))
        values = tuple(executed)
        _validate_selection(values, targets)
        files, pending = _packet(values, targets, comparison_rows, root)
    return MarkWave2SelectionArtifact(files, 266, pending, 47)


async def materialize_mark_wave2_selection(
    output: Path = DEFAULT_MARK_WAVE2_SELECTION_OUTPUT,
    *,
    repository_root: Path = _ROOT,
) -> MarkWave2SelectionArtifact:
    artifact = await build_mark_wave2_selection(repository_root=repository_root)
    publish_directory_transaction(output, artifact.files)
    return artifact


def _validate_selection(
    executed: tuple[ExecutedMarkWave2, ...],
    targets: dict[str, dict[str, object]],
) -> None:
    action_counts: dict[str, Counter[str]] = {}
    source_units = set()
    decision_count = 0
    for item in executed:
        logical = item.spec.logical_stream_id
        stream_targets = sorted(
            (row for row in targets.values() if row["logical_stream_id"] == logical),
            key=lambda row: _integer(row, "program_action_index"),
        )
        if len(stream_targets) != len(item.generated.program.actions):
            raise MarkWave2SelectionError(f"{logical} target inventory drifted")
        for index, (action, target) in enumerate(
            zip(item.generated.program.actions, stream_targets, strict=True)
        ):
            boundary = item.generated.decision_boundaries[index]
            if (
                target["stream_sha256"] != item.generated.stream.sha256
                or target["oracle_action"] != action.model_dump(mode="json")
                or target["policy_prefix_sha256"] != digest(boundary.policy_bytes)
            ):
                raise MarkWave2SelectionError(f"{logical} no longer matches teacher evidence")
        family = item.generated.program.family.value
        counts = action_counts.setdefault(family, Counter())
        counts.update(action.type for action in item.generated.program.actions)
        source_units.add(item.spec.source_unit_id)
        decision_count += len(item.generated.program.actions)
    normalized = {
        family: dict(sorted(counts.items())) for family, counts in sorted(action_counts.items())
    }
    if (
        decision_count != 266
        or len(source_units) != 39
        or normalized != _EXPECTED_ACTIONS
        or _QUARANTINED & {item.spec.logical_stream_id for item in executed}
    ):
        raise MarkWave2SelectionError("selected allocation does not match the frozen target")


def _packet(
    executed: tuple[ExecutedMarkWave2, ...],
    targets: dict[str, dict[str, object]],
    comparison_rows: dict[str, dict[str, object]],
    root: Path,
) -> tuple[dict[str, bytes], int]:
    _validate_selected_comparisons(targets, comparison_rows)
    evidence, routes = _static_routes(executed, targets)
    source_manifest = _verify_directory(root / _SOURCE)
    execution_manifest = _verify_directory(root / _EXECUTION)
    projected = project_phase2_review_evidence(
        tuple(
            DecisionProjectionInput(
                decision=decision,
                route=route,
                oracle_license=CandidateLicense("licensed", ()),
                teacher_license=CandidateLicense("licensed", ()),
                oracle_provenance={
                    "sidecar_sha256": next(
                        item.generated.sidecar.sha256
                        for item in executed
                        if item.generated.stream.sha256 == decision.stream_sha256
                    ),
                    "stream_sha256": decision.stream_sha256,
                },
                teacher_provenance={
                    "execution_sha256": execution_manifest,
                    "label_state": "owner_adjudicated_final_label",
                    "source_packet_sha256": source_manifest,
                },
                priority_rank=index,
            )
            for index, (decision, route) in enumerate(zip(evidence, routes, strict=True))
        ),
        packet_decision_identities=tuple(
            (decision.stream_sha256, decision.decision_policy_seq) for decision in evidence
        ),
        teacher_evidence_identity=execution_manifest,
        blind_seed="phase2-mark-wave2-selection-review-v1",
    )
    prior = _prior_owner_reviews(projected, targets, comparison_rows)
    routed = sum(route.review_required for route in routes)
    pending = routed - len(prior)
    if (routed, len(prior), pending) != (122, 15, 107):
        raise MarkWave2SelectionError(
            f"owner review allocation drifted: routed={routed}, prior={len(prior)}, "
            f"pending={pending}"
        )

    manifest = PackageManifest.build(item.generated for item in executed).canonical_bytes
    report = {
        "action_counts": _EXPECTED_ACTIONS,
        "already_owner_reviewed_decisions": 15,
        "decision_count": 266,
        "family_targets_met_exactly": True,
        "format_version": 1,
        "kind": "phase2-mark-wave2-whole-stream-selection",
        "pending_owner_review_decisions": pending,
        "quarantined_streams": sorted(_QUARANTINED),
        "routed_review_decisions": routed,
        "selected_owner_adjudicated_teacher_differences": 15,
        "selected_logical_stream_ids": sorted(_SELECTED),
        "source_unit_count": 39,
        "stream_count": 47,
        "teacher_agreement_used_as_selection_feature": False,
        "whole_stream_only": True,
    }
    files = {
        "README.md": _readme().encode(),
        "REVIEW.md": _review_guide().encode(),
        "manifest.json": manifest,
        "phase2-review-evidence.json": projected,
        "prior-owner-decisions.jsonl": _review_jsonl(prior),
        "raw-stream-evidence.json": canonical_artifact_bytes(
            {
                "format_version": 1,
                "kind": "phase2-mark-wave2-selected-runtime-parents",
                "streams": [_raw_stream(item) for item in executed],  # type: ignore[arg-type]
            }
        ),
        "review-packet.json": canonical_artifact_bytes(
            {
                "already_owner_reviewed_decisions": 15,
                "api_call_performed": False,
                "decision_count": 266,
                "format_version": 1,
                "kind": "phase2-mark-wave2-owner-review",
                "manifest_sha256": _digest(manifest),
                "owner_action_required": (
                    "Import prior-owner-decisions.jsonl, then review the 107 remaining "
                    "plain-language decisions."
                ),
                "pending_owner_review_decisions": pending,
                "routed_review_decisions": routed,
                "stream_review_count": 47,
                "wave_id": "mark-wave-2",
            }
        ),
        "selection-report.json": canonical_artifact_bytes(report),
        "source-index.json": canonical_artifact_bytes(_source_index(executed)),
        **_runtime_files(executed),  # type: ignore[arg-type]
    }
    files["SHA256SUMS"] = _checksums(files)
    return files, pending


def _validate_selected_comparisons(
    targets: dict[str, dict[str, object]],
    comparison_rows: dict[str, dict[str, object]],
) -> None:
    selected_differences = {
        custom_id
        for custom_id, target in targets.items()
        if target["logical_stream_id"] in _SELECTED
        and comparison_rows[custom_id]["comparison"] != "equivalent"
    }
    response_differences = selected_differences - _APPROVED_TEACHER_ERRORS
    if (
        len(selected_differences) != 15
        or len(response_differences) != 8
        or any(not custom_id.endswith("-yielded.d000.a1") for custom_id in response_differences)
    ):
        raise MarkWave2SelectionError("selected owner-adjudicated teacher evidence drifted")


def _static_routes(
    executed: tuple[ExecutedMarkWave2, ...],
    targets: dict[str, dict[str, object]],
) -> tuple[tuple[DecisionEvidence, ...], tuple[ReviewRoute, ...]]:
    evidence, _recomputed = _routes(executed)
    target_by_identity = {
        (_string(row, "stream_sha256"), _integer(row, "decision_policy_seq")): row
        for row in targets.values()
        if row["logical_stream_id"] in _SELECTED
    }
    routes = []
    for decision in evidence:
        target = target_by_identity[(decision.stream_sha256, decision.decision_policy_seq)]
        raw = _record(target.get("static_d2_route"), "static D2 route")
        required = raw.get("review_required")
        mandatory = raw.get("mandatory_review")
        rate = raw.get("sample_rate")
        reasons = raw.get("reasons")
        if (
            type(required) is not bool
            or type(mandatory) is not bool
            or not isinstance(rate, (int, float))
            or isinstance(rate, bool)
            or not isinstance(reasons, list)
            or not all(isinstance(reason, str) for reason in reasons)
        ):
            raise MarkWave2SelectionError("static D2 route is malformed")
        route = ReviewRoute(
            identity=decision.identity,
            review_required=required,
            mandatory=mandatory,
            sample_rate=float(rate),
            reasons=tuple(reasons),
            provisional_label_origin=(None if required else LabelOrigin.ORACLE_TEACHER_AGREEMENT),
        )
        route.validate_for(decision)
        routes.append(route)
    return evidence, tuple(routes)


def _prior_owner_reviews(
    projected: bytes,
    targets: dict[str, dict[str, object]],
    comparison_rows: dict[str, dict[str, object]],
) -> list[dict[str, object]]:
    payload = json.loads(projected)
    custom_by_identity = {
        (_string(row, "stream_sha256"), _integer(row, "decision_policy_seq")): custom_id
        for custom_id, row in targets.items()
        if row["logical_stream_id"] in _SELECTED
    }
    records = []
    for decision in payload["decisions"]:
        custom_id = custom_by_identity[(decision["stream_sha256"], decision["decision_policy_seq"])]
        if comparison_rows[custom_id]["comparison"] == "equivalent":
            continue
        category = "teacher_error" if custom_id in _APPROVED_TEACHER_ERRORS else "text_equivalent"
        if decision["comparison"] != "equivalent" or decision["candidates"]:
            raise MarkWave2SelectionError("final owner label projection drifted")
        records.append(
            {
                "decision": "accept",
                "decision_policy_seq": decision["decision_policy_seq"],
                "note": (
                    "Previously reviewed: owner kept the oracle label after a teacher error."
                    if category == "teacher_error"
                    else "Previously reviewed: owner kept the human-authored response; the "
                    "teacher wording differed only cosmetically."
                ),
                "reason_code": category,
                "stream_sha256": decision["stream_sha256"],
            }
        )
    return sorted(
        records,
        key=lambda row: (row["stream_sha256"], row["decision_policy_seq"]),
    )


def _source_index(executed: tuple[ExecutedMarkWave2, ...]) -> dict[str, object]:
    return {
        "batch": 1,
        "format_version": 1,
        "source_identity_rule": (
            "one complete selected TRAIN runtime parent per reviewed stream; response twins "
            "retain their shared source unit"
        ),
        "sources": [
            {
                "checkpoint": None,
                "family": item.generated.program.family.value,
                "master_seed": str(item.generated.program.master_seed),
                "parent_stream_sha256s": [item.generated.stream.sha256],
                "raw_source_sha256s": [item.generated.stream.capture_sha256],
                "role": item.spec.kind,
                "shape_id": item.spec.kind,
                "sidecar_sha256s": [item.generated.sidecar.sha256],
                "source_decision_counts": [len(item.generated.program.actions)],
                "source_kind": "runtime_parent",
                "source_unit_id": item.spec.source_unit_id,
            }
            for item in executed
        ],
    }


def _targets(plan: dict[str, object]) -> dict[str, dict[str, object]]:
    rows = plan.get("targets")
    if not isinstance(rows, list) or len(rows) != 462:
        raise MarkWave2SelectionError("teacher target inventory is malformed")
    result = {_string(row, "custom_id"): _record(row, "teacher target") for row in rows}
    if len(result) != 462:
        raise MarkWave2SelectionError("teacher target identities are duplicated")
    return result


def _comparison_rows(comparison: dict[str, object]) -> dict[str, dict[str, object]]:
    rows = comparison.get("rows")
    if not isinstance(rows, list) or len(rows) != 462:
        raise MarkWave2SelectionError("teacher comparison inventory is malformed")
    result = {_string(row, "custom_id"): _record(row, "comparison row") for row in rows}
    if len(result) != 462:
        raise MarkWave2SelectionError("teacher comparison identities are duplicated")
    return result


def _verify_directory(directory: Path) -> str:
    data = (directory / "SHA256SUMS").read_bytes()
    for line in data.decode().splitlines():
        checksum, separator, relative = line.partition("  ")
        if not separator or sha256((directory / relative).read_bytes()).hexdigest() != checksum:
            raise MarkWave2SelectionError(f"checksum failed under {directory.name}")
    return digest(data)


def _object(path: Path, label: str) -> dict[str, object]:
    try:
        value = json.loads(path.read_bytes())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise MarkWave2SelectionError(f"{label} is unreadable") from error
    return _record(value, label)


def _record(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise MarkWave2SelectionError(f"{label} must be an object")
    return value


def _string(value: object, key: str) -> str:
    record = _record(value, key)
    item = record.get(key)
    if not isinstance(item, str) or not item:
        raise MarkWave2SelectionError(f"{key} is missing")
    return item


def _integer(value: object, key: str) -> int:
    record = _record(value, key)
    item = record.get(key)
    if isinstance(item, bool) or not isinstance(item, int) or item < 0:
        raise MarkWave2SelectionError(f"{key} is invalid")
    return item


def _review_jsonl(records: list[dict[str, object]]) -> bytes:
    return ("".join(json.dumps(row, sort_keys=True) + "\n" for row in records)).encode()


def _checksums(files: dict[str, bytes]) -> bytes:
    return "".join(
        f"{sha256(data).hexdigest()}  {name}\n" for name, data in sorted(files.items())
    ).encode()


def _digest(data: bytes) -> str:
    return f"sha256:{sha256(data).hexdigest()}"


def _readme() -> str:
    return """# Mark Wave-2 — final owner review

This packet contains the 47 complete interactions selected for training. The four interactions
with the disputed “filler words” target are absent. Selection used the frozen stream shapes and
counts, never whether the teacher agreed.

Open this whole folder in the review UI. Then import `prior-owner-decisions.jsonl`; it records the
15 teacher differences you already approved. Review the 107 decisions still left. The UI presents
them as ordinary user interactions rather than internal event records.
"""


def _review_guide() -> str:
    return """# What to check

Review the product as a user:

- A clear request such as “Highlight Apple” starts marking later, exact occurrences of Apple.
- “Stop highlighting Apple” stops it. “Switch to highlighting Orange” replaces it.
- An unclear switch pauses the old marking and waits until the user says what should replace it.
- If that unclear switch disappears before the user answers, the earlier visible marking rule
  resumes.
- Quoted examples and code are text, not instructions.
- An unfinished instruction waits for the user to finish typing.
- When the assistant must ask a question, the wording should be short, natural, and grounded in
  what the user can see.

Accept what behaves this way. Flag or reject anything that would surprise a normal user.
"""
