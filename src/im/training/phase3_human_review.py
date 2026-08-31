"""Pure WP3-4 human-review blinding, regrading, and D12 v2 evidence."""

from __future__ import annotations

import json
import math
import os
import re
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

from im.assets.model import canonical_artifact_bytes
from im.training.phase3_eval import (
    FrozenHumanAssessment,
    PersistedRawGeneration,
    compute_dev_metrics,
)

HUMAN_REVIEW_AMENDMENT = Path(
    "review/phase3/wp3-4-human-review-pause-amendment-candidate-v2/"
    "human-review-pause-amendment-v2.json"
)
HUMAN_REVIEW_AMENDMENT_SHA256 = (
    "sha256:0bad4bb47eebf159a066ad2c052ad92d17a7459e85c4cbdf47c4726bc4e727f0"
)
EXPECTED_DERIVED_MANIFEST = (
    "sha256:599ca75686cee444c430ba059b3389d0bbcf24066612cce123be603f2d521d90"
)
CHECKSUMS = "SHA256SUMS"
SEED = 20260801
BLIND_DOMAIN = "phase3-wp3-4-open-text-blind-v1"
_SHA256 = re.compile(r"sha256:[0-9a-f]{64}")


class HumanReviewError(ValueError):
    """A blind-review, disposition, or D12 byte contract is invalid."""


@dataclass(frozen=True, slots=True)
class HumanReviewAmendment:
    sha256: str
    early_steps: tuple[int, ...]
    final_steps: tuple[int, ...]
    all_steps: tuple[int, ...]


def digest(raw: bytes) -> str:
    return f"sha256:{sha256(raw).hexdigest()}"


def load_human_review_amendment(repository_root: Path) -> HumanReviewAmendment:
    root = repository_root.resolve(strict=True)
    raw = _read(root, HUMAN_REVIEW_AMENDMENT)
    if digest(raw) != HUMAN_REVIEW_AMENDMENT_SHA256:
        raise HumanReviewError("human-review pause amendment drifted")
    value = _json_object(raw, "human-review pause amendment")
    d12 = value.get("d12")
    bindings = value.get("bindings")
    if (
        not isinstance(d12, Mapping)
        or value.get("kind") != "phase3-wp3-4-human-review-pause-amendment-candidate"
        or value.get("format_version") != "phase3-wp3-4-human-review-pause-amendment-v2"
        or value.get("owner_approved") is not False
        or not isinstance(bindings, Mapping)
        or not isinstance(bindings.get("derived_run_manifest"), Mapping)
        or bindings["derived_run_manifest"].get("sha256") != EXPECTED_DERIVED_MANIFEST
    ):
        raise HumanReviewError("human-review pause amendment contract drifted")
    return HumanReviewAmendment(
        sha256=digest(raw),
        early_steps=_exact_steps(d12.get("early_full_dev_steps"), (20, 40, 60, 63, 80)),
        final_steps=_exact_steps(d12.get("final_full_dev_steps"), (120, 126)),
        all_steps=_exact_steps(d12.get("all_full_dev_steps"), (20, 40, 60, 63, 80, 100, 120, 126)),
    )


def build_blind_packet(pending_full: Sequence[Mapping[str, object]]) -> dict[str, object]:
    occurrences: dict[tuple[str, str, str], list[dict[str, object]]] = {}
    structural_na: list[dict[str, object]] = []
    rows_by_key: dict[tuple[str, str, str], Mapping[str, object]] = {}
    for full in pending_full:
        step, rows = full.get("step"), full.get("open_text_rows")
        if not isinstance(step, int) or not isinstance(rows, list):
            raise HumanReviewError("pending full DEV review rows are malformed")
        for row in rows:
            if not isinstance(row, Mapping):
                raise HumanReviewError("pending full DEV review row is malformed")
            assessment, structural = row.get("human_assessment"), row.get("structural")
            state_id, raw_sha, rubric_sha = (
                row.get("state_id"),
                row.get("raw_output_sha256"),
                _rubric_sha(row),
            )
            if (
                not isinstance(assessment, Mapping)
                or not isinstance(structural, Mapping)
                or not all(isinstance(value, str) for value in (state_id, raw_sha, rubric_sha))
                or _SHA256.fullmatch(raw_sha) is None
                or _SHA256.fullmatch(rubric_sha) is None
            ):
                raise HumanReviewError("pending human-review row has malformed exact key")
            occurrence = {
                "checkpoint_step": step,
                "raw_output_sha256": raw_sha,
                "rubric_sha256": rubric_sha,
                "state_id": state_id,
            }
            if assessment.get("review_status") != "pending_human_review":
                structural_na.append(
                    {**occurrence, "review_status": "not_applicable_structural_failure"}
                )
                continue
            key = (state_id, raw_sha, rubric_sha)
            occurrences.setdefault(key, []).append(occurrence)
            rows_by_key.setdefault(key, row)
    if not occurrences or sum(len(value) for value in occurrences.values()) > 256:
        raise HumanReviewError("human-review exact occurrence inventory is malformed")
    blinded, sealed = [], []
    for key, values in occurrences.items():
        first = rows_by_key[key]
        rubric, predicted = first.get("rubric"), first.get("predicted_action")
        if not isinstance(rubric, Mapping) or not isinstance(predicted, Mapping):
            raise HumanReviewError("pending human-review prediction is malformed")
        text = predicted.get("text")
        if not isinstance(text, str):
            raise HumanReviewError("pending human-review prediction is malformed")
        opaque = blind_id(key)
        blinded.append(
            {
                "frozen_rubric": dict(rubric),
                "opaque_review_id": opaque,
                "predicted_text": text,
                "state_evidence": _visible_state_evidence(first, key[0]),
            }
        )
        sealed.append(
            {
                "exact_key": {
                    "raw_output_sha256": key[1],
                    "rubric_sha256": key[2],
                    "state_id": key[0],
                },
                "occurrences": values,
                "opaque_review_id": opaque,
            }
        )
    blinded.sort(key=lambda row: blind_rank(str(row["opaque_review_id"])))
    sealed.sort(key=lambda row: str(row["opaque_review_id"]))
    return {
        "blind_packet": {
            "deduplication": "exact_state_raw_rubric_only",
            "kind": "phase3-wp3-4-open-text-blind-review-packet",
            "ordering": {"domain": BLIND_DOMAIN, "seed": SEED},
            "rows": blinded,
        },
        "sealed_occurrence_mapping": {
            "kind": "phase3-wp3-4-open-text-sealed-occurrence-mapping",
            "rows": sealed,
            "structural_not_applicable_occurrences": structural_na,
        },
    }


def persist_human_review_pause(
    output: Path,
    pending_full: Sequence[Mapping[str, object]],
    resume_control: Mapping[str, object],
) -> dict[str, object]:
    expected = (20, 40, 60, 63, 80, 100, 120, 126)
    if tuple(sorted(int(row.get("step", -1)) for row in pending_full)) != expected:
        raise HumanReviewError("human-review pause lacks all eight full DEV records")
    review = build_blind_packet(pending_full)
    directory = output / "human-review"
    directory.mkdir(mode=0o700, exist_ok=False)
    blind, sealed = (
        canonical_artifact_bytes(review["blind_packet"]),
        canonical_artifact_bytes(review["sealed_occurrence_mapping"]),
    )
    _write_atomic(directory / "blind-review-packet.json", blind)
    _write_atomic(directory / "sealed-occurrence-mapping.json", sealed)
    pause_created_at_unix = int(time.time())
    checkpoint_created = resume_control.get("checkpoint_created_at")
    if (
        isinstance(checkpoint_created, bool)
        or not isinstance(checkpoint_created, int)
        or pause_created_at_unix < checkpoint_created
    ):
        raise HumanReviewError("human-review pause timestamp is malformed")
    control = canonical_artifact_bytes(
        {**resume_control, "pause_created_at_unix": pause_created_at_unix}
    )
    _write_atomic(directory / "step-126-resume-control-state.json", control)
    _write_sums(
        directory,
        (
            "blind-review-packet.json",
            "sealed-occurrence-mapping.json",
            "step-126-resume-control-state.json",
        ),
    )
    return {
        "blind_review_packet_sha256": digest(blind),
        "resume_control_state_sha256": digest(control),
        "pause_created_at_unix": pause_created_at_unix,
        "retained_full_state_steps": list(expected),
        "sealed_occurrence_mapping_sha256": digest(sealed),
    }


def fanout_dispositions(
    blind: Mapping[str, object], sealed: Mapping[str, object], dispositions: Mapping[str, object]
) -> dict[tuple[int, str], FrozenHumanAssessment]:
    rows, sealed_rows, decisions = blind.get("rows"), sealed.get("rows"), dispositions.get("rows")
    if (
        blind.get("kind") != "phase3-wp3-4-open-text-blind-review-packet"
        or not isinstance(rows, list)
        or not isinstance(sealed_rows, list)
        or not isinstance(decisions, list)
        or dispositions.get("blind_review_packet_sha256")
        != digest(canonical_artifact_bytes(dict(blind)))
    ):
        raise HumanReviewError("human-review disposition packet is malformed")
    by_id = {row.get("opaque_review_id"): row for row in sealed_rows if isinstance(row, Mapping)}
    visible = {row.get("opaque_review_id") for row in rows if isinstance(row, Mapping)}
    if len(by_id) != len(sealed_rows) or set(by_id) != visible:
        raise HumanReviewError("blind and sealed review identities drifted")
    result: dict[tuple[int, str], FrozenHumanAssessment] = {}
    seen: set[str] = set()
    for decision in decisions:
        if not isinstance(decision, Mapping):
            raise HumanReviewError("human-review judgment is malformed")
        opaque, passed, codes = (
            decision.get("opaque_review_id"),
            decision.get("passed"),
            decision.get("reason_codes"),
        )
        sealed_row = by_id.get(opaque)
        if (
            not isinstance(opaque, str)
            or opaque in seen
            or not isinstance(sealed_row, Mapping)
            or type(passed) is not bool
            or not isinstance(codes, list)
            or any(not isinstance(code, str) for code in codes)
        ):
            raise HumanReviewError("human-review judgment identity is malformed")
        seen.add(opaque)
        key, occurrences = sealed_row.get("exact_key"), sealed_row.get("occurrences")
        if not isinstance(key, Mapping) or not isinstance(occurrences, list):
            raise HumanReviewError("sealed review occurrence is malformed")
        state_id, raw_sha, rubric_sha = (
            key.get("state_id"),
            key.get("raw_output_sha256"),
            key.get("rubric_sha256"),
        )
        if not all(isinstance(value, str) for value in (state_id, raw_sha, rubric_sha)):
            raise HumanReviewError("sealed review occurrence has malformed exact key")
        for occurrence in occurrences:
            step = occurrence.get("checkpoint_step") if isinstance(occurrence, Mapping) else None
            if not isinstance(step, int):
                raise HumanReviewError("sealed review occurrence is malformed")
            result[(step, state_id)] = FrozenHumanAssessment(
                state_id, rubric_sha, raw_sha, passed, tuple(codes)
            )
    if seen != visible:
        raise HumanReviewError("human-review dispositions do not close over blind rows")
    return result


def finalize_human_review_pause(
    *,
    repository_root: Path,
    output_directory: Path,
    dispositions_path: Path,
    states: Sequence[Any],
    tokenizer: Any,
) -> dict[str, object]:
    root, output = repository_root.resolve(strict=True), output_directory.resolve(strict=True)
    amendment = load_human_review_amendment(root)
    evidence = validated_evidence_chain(output)
    pending = [row["evidence"] for row in evidence if row["stage"] == "full_dev_pending_human"]
    retention = [row["evidence"] for row in evidence if row["stage"] == "automatic_retention_12"]
    if len(pending) != len(amendment.all_steps) or len(retention) != len(amendment.all_steps):
        raise HumanReviewError("paused run does not contain all human-review evidence")
    blind, sealed = load_pause_packet(output)
    dispositions_raw = _read(root, dispositions_path)
    assessments = fanout_dispositions(
        blind, sealed, _json_object(dispositions_raw, "human-review dispositions")
    )
    final_directory = output / "human-review" / "finalized"
    final_directory.mkdir(mode=0o700, exist_ok=False)
    regraded = []
    for full in sorted(pending, key=lambda row: int(row["step"])):
        record = _regrade_pending_full_dev(root, full, states, tokenizer, assessments)
        regraded.append(record)
        _write_atomic(
            final_directory / f"metrics-step-{record['step']:03d}.json",
            canonical_artifact_bytes(record),
        )
    steps = [row["evidence"] for row in evidence if row["stage"] == "optimizer_update"]
    decision = derive_d12_v2(steps, [*regraded, *retention])
    finalization = {
        "amendment_sha256": amendment.sha256,
        "d12": decision,
        "d12_decision_sha256": digest(canonical_artifact_bytes(decision)),
        "dispositions_sha256": digest(dispositions_raw),
        "kind": "phase3-wp3-4-human-review-finalization",
        "regraded_full_dev_steps": [row["step"] for row in regraded],
    }
    _write_atomic(final_directory / "d12-decision.json", canonical_artifact_bytes(decision))
    _write_atomic(final_directory / "finalization.json", canonical_artifact_bytes(finalization))
    _write_sums(
        final_directory,
        tuple(sorted(path.name for path in final_directory.iterdir() if path.name != CHECKSUMS)),
    )
    return finalization


def validated_evidence_chain(output: Path) -> list[dict[str, object]]:
    directory = output / "evidence"
    entries = verify_local_sums(directory, (directory / CHECKSUMS).read_bytes())
    records: list[dict[str, object]] = []
    previous: str | None = None
    for name in sorted(entries):
        raw = (directory / name).read_bytes()
        value = _json_object(raw, "run evidence")
        evidence = value.get("evidence")
        if (
            value.get("previous_stage_sha256") != previous
            or not isinstance(value.get("stage"), str)
            or not isinstance(evidence, Mapping)
        ):
            raise HumanReviewError("run evidence chain is discontinuous")
        previous = digest(raw)
        records.append({"evidence": dict(evidence), "stage": value["stage"]})
    return records


def verify_local_sums(directory: Path, raw: bytes) -> dict[str, str]:
    try:
        lines = raw.decode("ascii").splitlines()
    except UnicodeDecodeError as error:
        raise HumanReviewError("local checksum manifest is not ASCII") from error
    entries: dict[str, str] = {}
    for line in lines:
        try:
            entry, name = line.split("  ", 1)
        except ValueError as error:
            raise HumanReviewError("local checksum manifest is malformed") from error
        if (
            re.fullmatch(r"[0-9a-f]{64}", entry) is None
            or Path(name).name != name
            or name in entries
            or not (directory / name).is_file()
            or sha256((directory / name).read_bytes()).hexdigest() != entry
        ):
            raise HumanReviewError("local checksum binding failed")
        entries[name] = entry
    if not entries:
        raise HumanReviewError("local checksum manifest is empty")
    return entries


def load_pause_packet(output: Path) -> tuple[Mapping[str, object], Mapping[str, object]]:
    directory = output / "human-review"
    entries = verify_local_sums(directory, (directory / CHECKSUMS).read_bytes())
    if not {"blind-review-packet.json", "sealed-occurrence-mapping.json"} <= set(entries):
        raise HumanReviewError("human-review packet inventory is incomplete")
    return (
        _json_object((directory / "blind-review-packet.json").read_bytes(), "blind review packet"),
        _json_object(
            (directory / "sealed-occurrence-mapping.json").read_bytes(),
            "sealed occurrence mapping",
        ),
    )


def derive_d12_v2(
    steps: Sequence[Mapping[str, object]], evaluations: Sequence[Mapping[str, object]]
) -> dict[str, object]:
    expected, early, final = (20, 40, 60, 63, 80, 100, 120, 126), (20, 40, 60, 63, 80), (120, 126)
    full = {int(row["step"]): row for row in evaluations if row.get("kind") == "full_dev"}
    retention = {
        int(row["step"]): row for row in evaluations if row.get("kind") == "automatic_retention_12"
    }
    if tuple(sorted(full)) != expected or tuple(sorted(retention)) != expected:
        raise HumanReviewError("D12 evidence is incomplete")
    early_best, late_best, all_best = (
        max(early, key=lambda step: _rank(full[step])),
        max(final, key=lambda step: _rank(full[step])),
        max(expected, key=lambda step: _rank(full[step])),
    )
    window = [
        row for row in steps if isinstance(row.get("step"), int) and 111 <= row["step"] <= 126
    ]
    if len(window) != 16 or {row["step"] for row in window} != set(range(111, 127)):
        raise HumanReviewError("D12 loss window drifted")
    slope = _slope_111_126(window)
    directional = _directional_counts(
        full[early_best]["integer_evidence"], full[late_best]["integer_evidence"]
    )
    repeated = set(retention[120].get("failure_signatures", [])) & set(
        retention[126].get("failure_signatures", [])
    )
    conditions = {
        "late_best_equals_all_best": late_best == all_best,
        "minimum_d13_gain": float(full[late_best]["d13_score"])
        >= float(full[early_best]["d13_score"]) + 0.01,
        "negative_loss_slope_111_126": slope < 0,
        "directional_integer_counts": all(directional.values()),
        "step_126_automatic_guard": retention[126].get("automatic_guard_passed") is True,
        "late_best_automatic_guard": retention[late_best].get("automatic_guard_passed") is True,
        "no_repeated_final_defect": not repeated,
    }
    return {
        **conditions,
        "all_conditions_pass": all(conditions.values()),
        "all_best_step": all_best,
        "directional_counts": directional,
        "early_best_step": early_best,
        "final_quarter_loss_slope": slope,
        "final_quarter_loss_steps": list(range(111, 127)),
        "late_best_step": late_best,
        "late_best_tie_break_evidence": _rank(full[late_best]),
        "repeated_final_defect_intersection": sorted(repeated),
    }


def _regrade_pending_full_dev(
    root: Path,
    full: Mapping[str, object],
    states: Sequence[Any],
    tokenizer: Any,
    assessments: Mapping[tuple[int, str], FrozenHumanAssessment],
) -> dict[str, object]:
    step, raw_index_path, identity = (
        full.get("step"),
        full.get("raw_index_path"),
        full.get("evaluation_identity"),
    )
    if (
        not isinstance(step, int)
        or not isinstance(raw_index_path, str)
        or not isinstance(identity, list)
    ):
        raise HumanReviewError("pending full DEV regrade input is malformed")
    index_raw = _read(root, Path(raw_index_path))
    if digest(index_raw) != full.get("raw_index_sha256"):
        raise HumanReviewError("pending full DEV raw index checksum drifted")
    try:
        index = json.loads(index_raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise HumanReviewError("pending full DEV raw index is malformed") from error
    if not isinstance(index, list) or len(index) != 300:
        raise HumanReviewError("pending full DEV raw index does not contain 300 records")
    persisted: list[PersistedRawGeneration] = []
    semantic: dict[str, FrozenHumanAssessment] = {}
    for item in index:
        if not isinstance(item, Mapping):
            raise HumanReviewError("pending full DEV raw index row is malformed")
        state_id, path, raw_sha = item.get("state_id"), item.get("path"), item.get("sha256")
        if not all(isinstance(value, str) for value in (state_id, path, raw_sha)):
            raise HumanReviewError("pending full DEV raw index row is malformed")
        persisted.append(PersistedRawGeneration(_inside(root, Path(path)), raw_sha))
        assessment = assessments.get((step, state_id))
        if assessment is not None:
            semantic[state_id] = assessment
    if len({record.path for record in persisted}) != 300:
        raise HumanReviewError("pending full DEV raw records repeat")
    expected_identity = tuple(identity)
    if len(expected_identity) != 4 or any(
        not isinstance(value, str) for value in expected_identity
    ):
        raise HumanReviewError("pending full DEV evaluation identity is malformed")
    metrics = compute_dev_metrics(
        root,
        states,
        persisted,
        expected_evaluation_identity=expected_identity,  # type: ignore[arg-type]
        semantic_assessments=semantic,
        tokenizer=tokenizer,
    )
    if metrics.get("pending_semantic_assessment_count") != 0:
        raise HumanReviewError("human-review dispositions left pending semantic rows")
    return {
        "d13_score": metrics["d13_score"],
        "evidence_sha256": digest(canonical_artifact_bytes(metrics)),
        "grades_sha256": full["grades_sha256"],
        "integer_evidence": _integer_metric_evidence(metrics),
        "kind": "full_dev",
        "mechanics_gates": metrics["mechanics_gate"]["checks"],
        "metrics": metrics,
        "raw_outputs_sha256": full["raw_index_sha256"],
        "step": step,
    }


def _integer_metric_evidence(metrics: Mapping[str, object]) -> dict[str, object]:
    active = _integer(metrics.get("active_floor_denominator"))
    positive = _integer(metrics.get("positive_action_denominator"))
    return {
        "active_floor_respond_count": round(float(metrics["active_floor_respond_rate"]) * active),
        "duplicate_delegate_or_schedule_error_count": round(
            float(metrics["duplicate_delegate_schedule_rate"]) * 300
        ),
        "forbidden_error_count": _integer(metrics.get("forbidden_error_count")),
        "full_payload_correct_count": round(float(metrics["executed_success_rate"]) * 300),
        "low_count_action_slice_error_counts": metrics["small_action_slice_errors"],
        "parse_union_valid_count": round(float(metrics["parse_union_validity"]) * 300),
        "positive_structural_correct_count": round(
            float(metrics["positive_action_micro_accuracy"]) * positive
        ),
    }


def _rank(record: Mapping[str, object]) -> tuple[float, int, int, int]:
    integers = record.get("integer_evidence")
    score, step = record.get("d13_score"), record.get("step")
    if (
        not isinstance(integers, Mapping)
        or isinstance(score, bool)
        or not isinstance(score, int | float)
        or not math.isfinite(float(score))
        or not isinstance(step, int)
    ):
        raise HumanReviewError("D12 v2 rank evidence is malformed")
    return (
        float(score),
        _integer(integers.get("full_payload_correct_count")),
        -_integer(integers.get("active_floor_respond_count")),
        -step,
    )


def _directional_counts(early: object, late: object) -> dict[str, bool]:
    if not isinstance(early, Mapping) or not isinstance(late, Mapping):
        raise HumanReviewError("D12 v2 directional evidence is malformed")
    checks = {
        name: _integer(early.get(name)) >= _integer(late.get(name))
        for name in (
            "active_floor_respond_count",
            "duplicate_delegate_or_schedule_error_count",
            "forbidden_error_count",
        )
    }
    checks.update(
        {
            name: _integer(early.get(name)) <= _integer(late.get(name))
            for name in ("parse_union_valid_count", "positive_structural_correct_count")
        }
    )
    before, after = (
        early.get("low_count_action_slice_error_counts"),
        late.get("low_count_action_slice_error_counts"),
    )
    if (
        not isinstance(before, Mapping)
        or not isinstance(after, Mapping)
        or set(before) != set(after)
    ):
        raise HumanReviewError("D12 v2 low-count evidence is malformed")
    checks["low_count_action_slice_error_counts"] = all(
        _integer(before[key]) >= _integer(after[key]) for key in before
    )
    return checks


def _slope_111_126(rows: Sequence[Mapping[str, object]]) -> float:
    x = [int(row["step"]) for row in rows]
    try:
        y = [float(row["loss"]["normalized_loss"]) for row in rows]  # type: ignore[index]
    except (KeyError, TypeError) as error:
        raise HumanReviewError("D12 v2 loss evidence is malformed") from error
    if not all(math.isfinite(value) for value in y):
        raise HumanReviewError("D12 v2 loss evidence is non-finite")
    xmean, ymean = sum(x) / len(x), sum(y) / len(y)
    return sum((a - xmean) * (b - ymean) for a, b in zip(x, y, strict=True)) / sum(
        (a - xmean) ** 2 for a in x
    )


def _visible_state_evidence(row: Mapping[str, object], state_id: str) -> dict[str, object]:
    evidence = row.get("state_evidence")
    messages = evidence.get("messages") if isinstance(evidence, Mapping) else None
    if (
        not isinstance(evidence, Mapping)
        or evidence.get("state_id") != state_id
        or not isinstance(messages, list)
        or any(not isinstance(message, Mapping) for message in messages)
    ):
        raise HumanReviewError("pending human-review row lacks visible state evidence")
    return {
        "messages": [dict(message) for message in messages],
        "state_id": state_id,
        "visible_prefix_sha256": evidence.get("visible_prefix_sha256"),
    }


def _rubric_sha(row: Mapping[str, object]) -> object:
    rubric = row.get("rubric")
    return rubric.get("rubric_sha256") if isinstance(rubric, Mapping) else None


def blind_id(key: tuple[str, str, str]) -> str:
    return "review-" + sha256("\x00".join((BLIND_DOMAIN, str(SEED), *key)).encode()).hexdigest()


def blind_rank(opaque: str) -> bytes:
    return sha256(f"{BLIND_DOMAIN}\x00{SEED}\x00{opaque}".encode()).digest()


def _exact_steps(value: object, expected: tuple[int, ...]) -> tuple[int, ...]:
    if not isinstance(value, list) or tuple(value) != expected:
        raise HumanReviewError("human-review pause amendment D12 steps drifted")
    return expected


def _integer(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise HumanReviewError("integer evidence is malformed")
    return value


def _read(root: Path, path: Path) -> bytes:
    safe = _inside(root, path)
    if not safe.is_file():
        raise HumanReviewError("required locked artifact is missing")
    return safe.read_bytes()


def _inside(root: Path, path: Path) -> Path:
    resolved = (
        path.resolve(strict=False) if path.is_absolute() else (root / path).resolve(strict=False)
    )
    try:
        resolved.relative_to(root)
    except ValueError as error:
        raise HumanReviewError("artifact path escapes repository root") from error
    return resolved


def _json_object(raw: bytes, label: str) -> Mapping[str, object]:
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise HumanReviewError(f"{label} is malformed") from error
    if not isinstance(value, Mapping):
        raise HumanReviewError(f"{label} is not an object")
    return value


def _write_atomic(path: Path, content: bytes) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(content)
    os.replace(temporary, path)


def _write_sums(directory: Path, names: Sequence[str]) -> None:
    _write_atomic(
        directory / CHECKSUMS,
        "".join(
            f"{sha256((directory / name).read_bytes()).hexdigest()}  {name}\n" for name in names
        ).encode("ascii"),
    )
