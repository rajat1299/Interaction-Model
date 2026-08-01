"""Deterministic whole-stream selection and owner review for mark Wave-3."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, replace
from pathlib import Path
from tempfile import TemporaryDirectory

from im.assets.model import canonical_artifact_bytes
from im.generation.packaging import PackageManifest
from im.generation.phase2_lookup_wave0 import _raw_stream, _runtime_files
from im.generation.phase2_mark_wave2 import ExecutedMarkWave2, _routes
from im.generation.phase2_mark_wave2_selection import (
    _checksums,
    _source_index,
    _verify_directory,
)
from im.generation.phase2_mark_wave3 import (
    _CONFIGURATIONS,
    _NEW_IDS,
    _REUSED,
    _candidate_specs,
)
from im.generation.phase2_review import (
    DecisionEvidence,
    LabelOrigin,
    ReviewRoute,
    route_wave,
)
from im.generation.phase2_review_projection import (
    CandidateLicense,
    DecisionProjectionInput,
    project_phase2_review_evidence,
)
from im.generation.publication import publish_directory_transaction
from im.generation.scenarios import execute_scenario, validate_generated_scenario
from im.probes.harness.identity import digest
from im.schema.actions import ACTION_ADAPTER

_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MARK_WAVE3_SELECTION_OUTPUT = (
    _ROOT / "review" / "phase2" / "mark-wave-3-selection-review"
)
_SOURCE = Path("review/phase2/mark-wave-3-chat-teacher")
_EXECUTION = Path("review/phase2/mark-wave-3-chat-execution")
_WAVE2 = Path("review/phase2/mark-wave-2-v8")
_SELECTED = frozenset(
    {
        *_CONFIGURATIONS["positive_b"],
        *{f"negative-core-{value:02d}" for value in range(13, 19)},
        *{f"negative-boundary-{value:02d}" for value in range(4, 8)},
        *{
            f"mark_lifecycle_negative-response-{value:02d}-{floor}"
            for value in range(5, 10)
            for floor in ("active", "yielded")
        },
        "wave3-negative-quoted",
    }
)
_EXPECTED_ACTIONS = {
    "mark_activation_positive": {"idle": 35, "mark": 44, "respond": 5},
    "mark_lifecycle_negative": {"idle": 48, "mark": 21, "respond": 5},
}


class MarkWave3SelectionError(ValueError):
    """The final Wave-3 selection or its teacher evidence drifted."""


@dataclass(frozen=True, slots=True)
class MarkWave3SelectionArtifact:
    files: dict[str, bytes]
    decision_count: int
    review_count: int
    stream_count: int


async def build_mark_wave3_selection(
    *, repository_root: Path = _ROOT
) -> MarkWave3SelectionArtifact:
    root = repository_root.resolve()
    source = root / _SOURCE
    execution = root / _EXECUTION
    source_sha256 = _verify_directory(source)
    execution_sha256 = _verify_directory(execution)
    comparison = _object(execution / "comparison.json")
    if comparison.get("source_packet_sha256") != source_sha256:
        raise MarkWave3SelectionError("teacher execution is not bound to the Wave-3 packet")
    specs = _candidate_specs(root)
    with TemporaryDirectory(prefix="phase2-mark-wave3-selection-") as temporary:
        executed = []
        for spec in specs:
            session = (
                f"phase2-mark-wave2-{spec.logical_stream_id}"
                if spec.logical_stream_id in _REUSED
                else f"phase2-mark-wave3-{spec.logical_stream_id}"
            )
            generated = await execute_scenario(
                spec.program,
                session_id=session,
                directory=Path(temporary) / spec.logical_stream_id,
                repository_root=root,
            )
            validate_generated_scenario(generated)
            executed.append(ExecutedMarkWave2(spec, generated))
        candidates = tuple(executed)
        selected = tuple(
            item for item in candidates if item.spec.logical_stream_id in _SELECTED
        )
        _validate(candidates, selected, source, comparison)
        files, review_count = _packet(
            candidates,
            selected,
            source,
            comparison,
            source_sha256,
            execution_sha256,
            root,
        )
    return MarkWave3SelectionArtifact(files, 158, review_count, 37)


async def materialize_mark_wave3_selection(
    output: Path = DEFAULT_MARK_WAVE3_SELECTION_OUTPUT,
    *,
    repository_root: Path = _ROOT,
) -> MarkWave3SelectionArtifact:
    artifact = await build_mark_wave3_selection(repository_root=repository_root)
    publish_directory_transaction(output, artifact.files)
    return artifact


def _validate(
    candidates: tuple[ExecutedMarkWave2, ...],
    selected: tuple[ExecutedMarkWave2, ...],
    source: Path,
    comparison: dict[str, object],
) -> None:
    raw = {
        row["logical_stream_id"]: row
        for row in _object(source / "raw-streams.json")["streams"]
    }
    if any(_raw_stream(item) != raw.get(item.spec.logical_stream_id) for item in candidates):
        raise MarkWave3SelectionError("candidate streams no longer match teacher inputs")
    rows = comparison.get("rows")
    if not isinstance(rows, list) or len(rows) != 47:
        raise MarkWave3SelectionError("teacher comparison is incomplete")
    differences = [row for row in rows if row.get("comparison") != "equivalent"]
    if len(differences) != 10 or any(not _text_equivalent(row) for row in differences):
        raise MarkWave3SelectionError("Wave-3 has a non-text-equivalent teacher difference")
    if len(selected) != 37 or {item.spec.logical_stream_id for item in selected} != _SELECTED:
        raise MarkWave3SelectionError("selected stream inventory drifted")
    counts: dict[str, Counter[str]] = {}
    for item in selected:
        counts.setdefault(item.generated.program.family.value, Counter()).update(
            action.type for action in item.generated.program.actions
        )
    if {
        family: dict(sorted(actions.items())) for family, actions in sorted(counts.items())
    } != _EXPECTED_ACTIONS:
        raise MarkWave3SelectionError("selected action counts drifted")

    by_logical = {item.spec.logical_stream_id: item for item in candidates}
    maximum_a = max(
        len(by_logical[value].generated.program.actions) for value in _CONFIGURATIONS["positive_a"]
    )
    maximum_b = max(
        len(by_logical[value].generated.program.actions) for value in _CONFIGURATIONS["positive_b"]
    )
    if (maximum_a, maximum_b) != (15, 14):
        raise MarkWave3SelectionError("selection objective no longer prefers positive_b")


def _text_equivalent(row: dict[str, object]) -> bool:
    oracle = row.get("oracle_action")
    teacher = row.get("teacher_action")
    if not isinstance(oracle, dict) or not isinstance(teacher, dict):
        return False
    if (
        oracle.get("type") != "respond"
        or teacher.get("type") != "respond"
        or oracle.get("reply_to_event_id") != teacher.get("reply_to_event_id")
    ):
        return False
    gold = str(oracle.get("text", "")).lower().strip(" .?!")
    proposed = str(teacher.get("text", "")).lower().strip(" .?!")
    return bool(gold) and gold in proposed


def _packet(
    candidates: tuple[ExecutedMarkWave2, ...],
    selected: tuple[ExecutedMarkWave2, ...],
    source: Path,
    comparison: dict[str, object],
    source_sha256: str,
    execution_sha256: str,
    root: Path,
) -> tuple[dict[str, bytes], int]:
    selected_by_stream = {item.generated.stream.sha256: item for item in selected}
    all_new = tuple(
        item for item in candidates if item.spec.logical_stream_id in _NEW_IDS
    )
    base_evidence, _ = _routes(selected)
    new_evidence, _ = _routes(all_new)
    old_targets = _object(root / _WAVE2 / "teacher-plan.json")["targets"]
    old_routes = {
        _identity(row): _review_route(row)
        for row in old_targets
        if row["logical_stream_id"] in _SELECTED
    }
    new_targets = _object(source / "teacher-plan.json")["targets"]
    target_by_identity = {
        _identity(row): row for row in new_targets
    }
    comparison_by_case = {
        row["teacher_case_id"]: row for row in comparison["rows"]
    }
    new_teacher = {
        identity: ACTION_ADAPTER.validate_python(
            comparison_by_case[target["teacher_case_id"]]["teacher_action"]
        )
        for identity, target in target_by_identity.items()
    }
    actual_new = tuple(
        _with_teacher(decision, new_teacher[decision.identity])
        for decision in new_evidence
    )
    new_routes = route_wave(
        actual_new,
        {},
        sampling_seed="phase2-mark-wave3-d2-v1",
    )
    new_route_by_identity = {route.identity: route for route in new_routes}
    decisions = []
    routes = []
    logical_by_stream = {
        item.generated.stream.sha256: item.spec.logical_stream_id for item in selected
    }
    for decision in base_evidence:
        logical = logical_by_stream[decision.stream_sha256]
        identity = decision.identity
        teacher_action = (
            new_teacher[identity] if logical in _NEW_IDS else decision.oracle_action
        )
        decisions.append(
            _with_teacher(decision, teacher_action)
        )
        routes.append(
            new_route_by_identity[identity] if logical in _NEW_IDS else old_routes[identity]
        )
    routed = sum(route.review_required for route in routes)
    projected = project_phase2_review_evidence(
        tuple(
            DecisionProjectionInput(
                decision=decision,
                route=route,
                oracle_license=CandidateLicense("licensed", ()),
                teacher_license=CandidateLicense("licensed", ()),
                oracle_provenance={
                    "stream_sha256": decision.stream_sha256,
                    "wave3_source_packet_sha256": source_sha256,
                },
                teacher_provenance={
                    "label_state": (
                        "prior_exact_agreement"
                        if logical_by_stream[decision.stream_sha256] in _REUSED
                        else "wave3_chat_result"
                    ),
                    "wave3_execution_sha256": execution_sha256,
                },
                priority_rank=index,
            )
            for index, (decision, route) in enumerate(zip(decisions, routes, strict=True))
        ),
        packet_decision_identities=tuple(
            (decision.stream_sha256, decision.decision_policy_seq)
            for decision in decisions
        ),
        teacher_evidence_identity=digest(
            f"{source_sha256}|{execution_sha256}".encode()
        ),
        blind_seed="phase2-mark-wave3-selection-review-v1",
    )
    manifest = PackageManifest.build(item.generated for item in selected).canonical_bytes
    files = {
        "README.md": _readme(routed).encode(),
        "REVIEW.md": _review_guide().encode(),
        "manifest.json": manifest,
        "phase2-review-evidence.json": projected,
        "raw-stream-evidence.json": canonical_artifact_bytes(
            {
                "format_version": 1,
                "kind": "phase2-mark-wave3-selected-runtime-parents",
                "streams": [_raw_stream(item) for item in selected],
            }
        ),
        "review-packet.json": canonical_artifact_bytes(
            {
                "api_call_performed": False,
                "decision_count": 158,
                "format_version": 1,
                "kind": "phase2-mark-wave3-owner-review",
                "owner_action_required": (
                    f"Review the {routed} routed decisions in plain language."
                ),
                "routed_review_decisions": routed,
                "stream_review_count": 37,
                "wave_id": "mark-wave-3",
            }
        ),
        "selection-report.json": canonical_artifact_bytes(
            {
                "action_counts": _EXPECTED_ACTIONS,
                "candidate_decisions": 182,
                "candidate_streams": 39,
                "decision_count": 158,
                "format_version": 1,
                "kind": "phase2-mark-wave3-whole-stream-selection",
                "positive_configuration": "positive_b",
                "positive_configuration_reason": (
                    "first lexicographic objective term: maximum decisions from one "
                    "source unit is 14 versus 15"
                ),
                "selected_logical_stream_ids": sorted(_SELECTED),
                "stream_count": 37,
                "teacher_agreement_used_as_selection_feature": False,
                "teacher_exact_matches": 37,
                "teacher_text_equivalences": 10,
                "whole_stream_only": True,
            }
        ),
        "source-index.json": canonical_artifact_bytes(_source_index(selected)),
        **_runtime_files(selected),
    }
    files["SHA256SUMS"] = _checksums(files)
    if len(selected_by_stream) != 37:
        raise MarkWave3SelectionError("selected stream hashes repeat")
    return files, routed


def _review_route(target: dict[str, object]) -> ReviewRoute:
    raw = target.get("static_d2_route")
    if not isinstance(raw, dict):
        raise MarkWave3SelectionError("reused D2 route is missing")
    return ReviewRoute(
        identity=_identity(target),
        review_required=raw["review_required"],
        mandatory=raw["mandatory_review"],
        sample_rate=float(raw["sample_rate"]),
        reasons=tuple(raw["reasons"]),
        provisional_label_origin=(
            None
            if raw["review_required"]
            else LabelOrigin.ORACLE_TEACHER_AGREEMENT
        ),
    )


def _with_teacher(
    decision: DecisionEvidence, teacher_action: object
) -> DecisionEvidence:
    normalized = ACTION_ADAPTER.validate_python(teacher_action)
    risk_flags = set(decision.risk_flags)
    if (
        normalized.model_dump(mode="json")
        != decision.oracle_action.model_dump(mode="json")
    ):
        risk_flags.add("oracle_teacher_non_equivalence")
    return replace(
        decision,
        wave_id="mark-wave-3",
        teacher_action=normalized,
        risk_flags=tuple(sorted(risk_flags)),
    )


def _identity(target: dict[str, object]) -> str:
    return f"{target['stream_sha256']}\x00{target['decision_policy_seq']}"


def _object(path: Path) -> dict[str, object]:
    value = json.loads(path.read_bytes())
    if not isinstance(value, dict):
        raise MarkWave3SelectionError(f"{path.name} is not an object")
    return value


def _readme(review_count: int) -> str:
    return f"""# Mark Wave-3 — final owner review

This packet contains the exact 37-stream / 158-decision top-up. Selection chose the positive
configuration whose largest source contributes 14 decisions rather than 15, the first frozen
lexicographic objective term. Teacher agreement was not used.

Open this whole folder in the review UI and review the {review_count} routed decisions. The ten
teacher differences are only fuller-sentence versions of the already owner-selected concise
answers; the UI still asks you to judge the visible product behavior.
"""


def _review_guide() -> str:
    return """# What to check

Review the product as a user:

- A clear mark request highlights later exact occurrences, not earlier text.
- Quoted mark wording is text, not a new instruction.
- When the user is still typing, the assistant waits.
- A visible question is answered only after the user pauses.
- User-facing answers should be short, natural, and grounded in the visible situation.

Accept what behaves this way. Flag only behavior that would surprise a normal user.
"""
