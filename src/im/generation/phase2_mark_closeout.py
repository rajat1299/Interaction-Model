"""Close WP2-4 after the owner-approved Mark Wave-3 review."""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from im.assets.model import canonical_artifact_bytes
from im.generation.phase2_mark_wave2_selection import _checksums, _verify_directory
from im.generation.publication import publish_directory_transaction

_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MARK_CLUSTER_EXIT_OUTPUT = _ROOT / "review" / "phase2" / "mark-cluster-exit-v2"
_SELECTION = Path("review/phase2/mark-wave-3-selection-review")
_WAVE3_EXECUTION = Path("review/phase2/mark-wave-3-chat-execution")


class MarkCloseoutError(ValueError):
    """The owner-approved mark allocation is incomplete or inconsistent."""


@dataclass(frozen=True, slots=True)
class MarkCloseoutArtifact:
    files: dict[str, bytes]
    accepted_decisions: int
    reserve_decisions: int
    reviewed_decisions: int


def build_mark_closeout(*, repository_root: Path = _ROOT) -> MarkCloseoutArtifact:
    root = repository_root.resolve()
    selection = root / _SELECTION
    evidence = _object(selection / "phase2-review-evidence.json")
    routed = [
        row
        for row in evidence["decisions"]
        if row["review_evidence"]["review_route"]["review_required"]
    ]
    if len(routed) != 87:
        raise MarkCloseoutError("Wave-3 routed review count drifted")
    decisions = b"".join(
        canonical_artifact_bytes(
            {
                "decision": "accept",
                "decision_policy_seq": row["decision_policy_seq"],
                "note": "",
                "reason_code": "",
                "stream_sha256": row["stream_sha256"],
            }
        ).rstrip(b"\n")
        + b"\n"
        for row in routed
    )
    pool = _accepted_pool_counts(root)
    report = {
        "accepted_pool": {
            "decision_count": pool["decision_count"],
            "stream_count": pool["stream_count"],
            "source_wave_references": {
                "wave_0": {"decision_count": 14, "stream_count": 8},
                "wave_1": {"decision_count": 62, "stream_count": 14},
                "wave_2_adjusted": {"decision_count": 401, "stream_count": 63},
                "wave_3": {"decision_count": 182, "stream_count": 39},
            },
            "wave2_wave3_reuse": {"decision_count": 135, "stream_count": 16},
        },
        "evidence": _bindings(root),
        "family_coverage": [
            {
                "accepted_actions": {"idle": 132, "mark": 162, "respond": 10},
                "accepted_decisions": 304,
                "accepted_streams": 48,
                "family": "mark_activation_positive",
                "reserve_decisions": 24,
                "target_actions": {"idle": 120, "mark": 150, "respond": 10},
                "target_decisions": 280,
                "target_satisfied": True,
            },
            {
                "accepted_actions": {"idle": 150, "mark": 60, "respond": 10},
                "accepted_decisions": 220,
                "accepted_streams": 60,
                "family": "mark_lifecycle_negative",
                "reserve_decisions": 0,
                "target_actions": {"idle": 150, "mark": 60, "respond": 10},
                "target_decisions": 220,
                "target_satisfied": True,
            },
        ],
        "final_selection": {
            "decision_count": 500,
            "stream_count": 106,
            "whole_streams_only": True,
        },
        "format_version": 1,
        "kind": "phase2-mark-cluster-exit",
        "label_origin": {
            "human": 285,
            "oracle_teacher_agreement": 215,
            "teacher_auto_trusted": 0,
            "total": 500,
        },
        "repair_gate": {
            "contract_gaps": 0,
            "response_payload_substitutions": 0,
            "status": "passed",
            "wave3_exact_teacher_matches": 37,
            "wave3_text_equivalences": 10,
        },
        "reserve": {
            "decision_count": 24,
            "status": "available",
            "whole_streams_only": True,
        },
        "status": "closed",
        "teacher_agreement_used_as_selection_feature": False,
        "trust": {
            "cleared_cell_count": 0,
            "state": "all_mark_cells_uncleared",
            "teacher_auto_trusted_count": 0,
        },
        "work_package": "WP2-4",
    }
    if (
        sum(row["accepted_decisions"] for row in report["family_coverage"]) != 524
        or sum(row["reserve_decisions"] for row in report["family_coverage"]) != 24
        or sum(
            report["label_origin"][name]
            for name in ("human", "oracle_teacher_agreement", "teacher_auto_trusted")
        )
        != report["label_origin"]["total"]
    ):
        raise MarkCloseoutError("mark closeout arithmetic drifted")
    files = {
        "ACCEPTED-POOL.md": _accepted_pool().encode(),
        "EXIT-REPORT.md": _exit_report().encode(),
        "OWNER-DISPOSITION.md": _owner_disposition().encode(),
        "exit-report.json": canonical_artifact_bytes(report),
        "owner-review-decisions.jsonl": decisions,
        "trust-ledger.json": canonical_artifact_bytes(_trust_ledger()),
    }
    files["SHA256SUMS"] = _checksums(files)
    return MarkCloseoutArtifact(files, 524, 24, 87)


def materialize_mark_closeout(
    output: Path = DEFAULT_MARK_CLUSTER_EXIT_OUTPUT,
    *,
    repository_root: Path = _ROOT,
) -> MarkCloseoutArtifact:
    artifact = build_mark_closeout(repository_root=repository_root)
    publish_directory_transaction(output, artifact.files)
    return artifact


def _accepted_pool_counts(root: Path) -> dict[str, int]:
    streams = []
    streams.extend(_object(root / "review/phase2/mark-wave-0/raw-stream-evidence.json")["streams"])

    wave1 = {
        row["logical_stream_id"]: row
        for row in _object(root / "review/phase2/mark-wave-1/raw-streams.json")["streams"]
    }
    for row in _object(root / "review/phase2/mark-wave-1-repair-v4/raw-stream.json")["streams"]:
        wave1[row["logical_stream_id"]] = row
    streams.extend(wave1.values())

    quarantined = {
        "negative-core-02",
        "negative-core-12",
        "positive-core-01",
        "positive-reserve-02",
    }
    wave2 = {}
    for row in _object(root / "review/phase2/mark-wave-2-v8/raw-streams.json")["streams"]:
        logical_id = row["logical_stream_id"]
        if logical_id in quarantined or re.search(
            r"-response-0[5-9]-(active|yielded)$", logical_id
        ):
            continue
        wave2[logical_id] = row
    for row in _object(
        root / "review/phase2/mark-wave-2-response-repair-v2-review/raw-stream-evidence.json"
    )["streams"]:
        wave2[row["logical_stream_id"]] = row
    streams.extend(wave2.values())
    streams.extend(
        _object(root / "review/phase2/mark-wave-3-chat-teacher/raw-streams.json")["streams"]
    )

    unique = {row["stream_sha256"]: row for row in streams}
    family_actions: dict[str, Counter[str]] = {}
    family_streams = Counter()
    for row in unique.values():
        family = row["sidecar"]["family"]
        family_streams[family] += 1
        family_actions.setdefault(family, Counter()).update(
            action["type"] for action in _selected_actions(row)
        )
    expected = {
        "mark_activation_positive": Counter({"idle": 132, "mark": 162, "respond": 10}),
        "mark_lifecycle_negative": Counter({"idle": 150, "mark": 60, "respond": 10}),
    }
    if family_actions != expected or family_streams != {
        "mark_activation_positive": 48,
        "mark_lifecycle_negative": 60,
    }:
        raise MarkCloseoutError("unique accepted mark pool drifted")
    return {
        "decision_count": sum(sum(counts.values()) for counts in family_actions.values()),
        "stream_count": len(unique),
    }


def _selected_actions(stream: dict[str, object]) -> list[dict[str, object]]:
    checkpoint = stream.get("selected_checkpoint")
    if isinstance(checkpoint, dict):
        actions = checkpoint.get("actions")
    else:
        actions = stream.get("actions")
    if not isinstance(actions, list):
        raise MarkCloseoutError("accepted mark stream actions are malformed")
    return actions


def _bindings(root: Path) -> dict[str, str]:
    return {
        "mark_wave0": _verify_directory(root / "review/phase2/mark-wave-0"),
        "mark_wave1_final": _verify_directory(
            root / "review/phase2/mark-wave-1-repair-v4-execution"
        ),
        "mark_wave2_response_repair": _verify_directory(
            root / "review/phase2/mark-wave-2-response-repair-v2-review"
        ),
        "mark_wave2_selection": _verify_directory(
            root / "review/phase2/mark-wave-2-selection-review"
        ),
        "mark_wave3_execution": _verify_directory(root / _WAVE3_EXECUTION),
        "mark_wave3_selection": _verify_directory(root / _SELECTION),
    }


def _trust_ledger() -> dict[str, object]:
    return {
        "cells": [
            {
                "confirmed_teacher_errors": 0,
                "family": "mark_activation_positive",
                "locked_uncleared": False,
                "protocol": "generation",
                "state": "uncleared",
            },
            {
                "confirmed_teacher_errors": 7,
                "family": "mark_lifecycle_negative",
                "locked_uncleared": True,
                "protocol": "generation",
                "state": "uncleared",
            },
        ],
        "format_version": 1,
        "kind": "phase2-mark-cluster-exit-trust-ledger",
        "notes": [
            "No mark cell was promoted and no teacher output was auto-trusted.",
            "Seven Wave-2 teacher errors remain UNCLEARED under D1.",
            "Wave-3 added no teacher error, oracle error, template error, or contract gap.",
        ],
        "trust_matrix_version": "phase2-trust-v1",
    }


def _object(path: Path) -> dict[str, object]:
    value = json.loads(path.read_bytes())
    if not isinstance(value, dict):
        raise MarkCloseoutError(f"{path.name} is not an object")
    return value


def _owner_disposition() -> str:
    return """# WP2-4 owner disposition

Authority: owner decision in chat; assistant transcription.

The owner approved all 87 routed Wave-3 decisions by behavior group:

1. wait while a visible question is still being typed, then answer after pause;
2. quoted mark wording does not replace an active mark instruction;
3. code-looking mark text does not replace an active mark instruction;
4. an unfinished mark instruction waits for completion;
5. all ten concise response records are natural and correct. For the water example, both
   “Copper water.” and “The copper water entry is approved.” are acceptable; the existing concise
   approved record remains gold, so no payload substitution is made.

All repeated ordinary mark/no-action rows are accepted under the same owner-approved behavior
groups. There are zero unresolved flags or rejections.
"""


def _accepted_pool() -> str:
    return """# Mark accepted pool (deduplicated)

The accepted pool contains 524 decisions across 108 unique whole streams. The exact final
selection uses 500 decisions across 106 streams; 24 decisions across two whole streams remain as
replacement reserve. Sixteen streams reused unchanged from Wave 2 in Wave 3 are counted once.
Superseded unnatural response streams and the four rejected filler-word streams are not eligible.
"""


def _exit_report() -> str:
    return """# WP2-4 mark cluster exit

WP2-4 is closed. The exact selected allocation is:

- mark activation: 120 idle, 150 mark, 10 respond;
- mark lifecycle: 150 idle, 60 mark, 10 respond.

All 500 selected labels are owner-reviewed or exact oracle/teacher agreements. No label is
teacher-auto-trusted. Seven known Wave-2 lifecycle teacher errors remain permanently uncleared;
Wave-3 introduced no new error or contract gap. After deduplicating unchanged streams reused
across Wave 2 and Wave 3, the reserve contains 24 accepted whole-stream decisions. Teacher
agreement was never used to select a stream.
"""
