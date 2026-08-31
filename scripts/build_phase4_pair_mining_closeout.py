#!/usr/bin/env python3
"""Publish the offline WP4-0 incomplete-run closeout and WP4-0R decision packet."""

from __future__ import annotations

import argparse
import gzip
import io
import json
import re
import subprocess
import zipfile
from collections import Counter, defaultdict
from hashlib import sha256
from pathlib import Path
from typing import Any

from im.assets.model import canonical_artifact_bytes
from im.generation.publication import publish_directory_transaction
from im.training.phase4_pair_mining import (
    PAIR_TARGETS,
    AdjudicationOutcome,
    BranchAdjudication,
    MiningRequest,
    MiningSourceRecord,
    PairCategory,
    digest,
    select_eligible_request_ids,
)

ROOT = Path(__file__).resolve().parents[1]
RUN = Path("review/phase4/wp4-0-on-policy-pair-mining-run-v1")
V2 = Path("review/phase4/wp4-0-on-policy-pair-mining-candidate-v2")
DEV = Path("review/phase3/wp3-2-offline-candidate-v4")
SFT_RUN = Path("review/phase3/wp3x-2-semantic-intent-sft-run-v3")
STEP63 = Path(
    "review/phase3/wp3x-2-semantic-intent-sft-run-v3/evaluations/step-063/full_dev"
)
OUTPUT = Path("review/phase4/wp4-0-on-policy-pair-mining-closeout-v1")
LEAN_OUTPUT = Path("review/phase4/wp4-0-on-policy-pair-mining-planner-review-v1")
LEAN_ZIP = Path("review/phase4/wp4-0-on-policy-pair-mining-planner-review-v1.zip")
EXPECTED_MANIFESTS = {
    RUN: "a64010a4370896cf215e2ef2249663cff30487a378b50d162cd32d9372396c5b",
    V2: "a9f385de7984e41ea6192c404b3a8ea70ff4f93c7d6365656e31bd005eb09caf",
    DEV: "b26ce03fbf46de2ed0b75c71ca925b79dee3d42d77e05f323271ffd5125dcace",
    SFT_RUN: "8cab70681539e17e42e3c3c9bf92ce3ef056b1916808b9098865a9da9429d111",
    STEP63: "60d82b92d8faeceb091f15750278da6a90d2db7dfaed1f3929c6d79925308ab1",
}
DEFICITS = {
    PairCategory.STALE_INTEGRATE_VS_SKIP: 5,
    PairCategory.ACTIVE_FLOOR_RESPOND_VS_IDLE: 45,
    PairCategory.CANCELED_FIRE_NUDGE_VS_SKIP: 28,
    PairCategory.PURE_NO_TRIGGER_RESTRAINT: 25,
    PairCategory.MIRRORED_POSITIVE_CONTROLS: 13,
}
EXPECTED_OUTCOMES = {
    PairCategory.STALE_INTEGRATE_VS_SKIP: {
        "preference_error": 86,
        "non_target_error": 134,
    },
    PairCategory.DUPLICATE_DELEGATE_VS_IDLE: {
        "on_policy_acceptable": 10,
        "preference_error": 130,
    },
    PairCategory.SEMANTIC_DUPLICATE_SCHEDULE_VS_IDLE: {"preference_error": 140},
    PairCategory.ACTIVE_FLOOR_RESPOND_VS_IDLE: {"on_policy_acceptable": 180},
    PairCategory.CANCELED_FIRE_NUDGE_VS_SKIP: {
        "on_policy_acceptable": 84,
        "mechanics_evidence": 34,
        "preference_error": 2,
    },
    PairCategory.AMBIGUOUS_CANCEL_VS_CLARIFICATION: {
        "preference_error": 119,
        "non_target_error": 1,
    },
    PairCategory.MARK_VS_RESTRAINT: {
        "on_policy_acceptable": 17,
        "preference_error": 163,
    },
    PairCategory.PURE_NO_TRIGGER_RESTRAINT: {"on_policy_acceptable": 100},
    PairCategory.MIRRORED_POSITIVE_CONTROLS: {
        "on_policy_acceptable": 62,
        "preference_error": 10,
        "mechanics_evidence": 5,
        "non_target_error": 3,
    },
}
SOURCE_FILES = (
    Path("scripts/build_phase4_pair_mining_closeout.py"),
    Path("tests/test_phase4_pair_mining_closeout.py"),
)


def _sha(raw: bytes) -> str:
    return f"sha256:{sha256(raw).hexdigest()}"


def _verify_manifest(root: Path, relative: Path, expected: str, *, closed: bool = True) -> None:
    directory = root / relative
    sums_path = directory / "SHA256SUMS"
    if sums_path.is_symlink() or not sums_path.is_file():
        raise ValueError(f"missing immutable manifest: {relative}")
    sums = sums_path.read_bytes()
    if sha256(sums).hexdigest() != expected:
        raise ValueError(f"manifest root drifted: {relative}")
    seen: set[str] = set()
    for line in sums.decode("ascii").splitlines():
        checksum, name = line.split("  ", 1)
        path = directory / name
        if name in seen or path.is_symlink() or not path.is_file():
            raise ValueError(f"malformed manifest entry: {relative}/{name}")
        seen.add(name)
        if sha256(path.read_bytes()).hexdigest() != checksum:
            raise ValueError(f"artifact drifted: {relative}/{name}")
    actual = {
        path.relative_to(directory).as_posix()
        for path in directory.rglob("*")
        if path.is_file() and path != sums_path
    }
    if (closed and actual != seen) or any(path.is_symlink() for path in directory.rglob("*")):
        raise ValueError(f"manifest inventory drifted: {relative}")


def _verify_source(root: Path, source_commit: str) -> dict[str, str]:
    if re.fullmatch(r"[0-9a-f]{40}", source_commit) is None:
        raise ValueError("source commit must be an exact Git SHA")
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()
    dirty = any(
        subprocess.run(["git", *args], cwd=root, check=False).returncode
        for args in (("diff", "--quiet"), ("diff", "--cached", "--quiet"))
    )
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    if head != source_commit or dirty or any(
        name.startswith(("src/", "scripts/", "tests/", "spec/")) or "/" not in name
        for name in untracked
    ):
        raise ValueError("closeout requires the exact clean source commit")
    bindings: dict[str, str] = {}
    for relative in SOURCE_FILES:
        raw = (root / relative).read_bytes()
        committed = subprocess.run(
            ["git", "show", f"{source_commit}:{relative.as_posix()}"],
            cwd=root,
            check=False,
            capture_output=True,
        )
        if committed.returncode or committed.stdout != raw:
            raise ValueError(f"source file is not commit-bound: {relative}")
        bindings[relative.as_posix()] = _sha(raw)
    return bindings


def _gzip_rows(rows: list[dict[str, Any]]) -> bytes:
    raw = b"\n".join(canonical_artifact_bytes(row) for row in rows) + b"\n"
    return gzip.compress(raw, compresslevel=9, mtime=0)


def _gzip_inventory(path: Path, model, key: str) -> dict[str, Any]:
    rows = gzip.decompress(path.read_bytes()).splitlines()
    parsed = [model.model_validate_json(row) for row in rows]
    return {str(getattr(row, key)): row for row in parsed}


def _run_records(root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    run = root / RUN
    requests = _gzip_inventory(
        root / V2 / "mining-request-inventory.jsonl.gz", MiningRequest, "request_id"
    )
    sources = _gzip_inventory(
        root / V2 / "mining-source-inventory.jsonl.gz", MiningSourceRecord, "mining_state_id"
    )
    outcomes: dict[str, AdjudicationOutcome] = {}
    records: list[dict[str, Any]] = []
    counts: dict[PairCategory, Counter[str]] = defaultdict(Counter)
    surfaces: dict[PairCategory, dict[int, Counter[str]]] = defaultdict(
        lambda: defaultdict(Counter)
    )
    concept_rows: dict[PairCategory, dict[int, dict[int, str]]] = defaultdict(
        lambda: defaultdict(dict)
    )
    paths = sorted((run / "adjudications").glob("*.selected.json"))
    if len(paths) != 1280 or len(requests) != 1280 or len(sources) != 1280:
        raise ValueError("run/request/source cardinality drifted")
    for path in paths:
        raw_adjudication = path.read_bytes()
        adjudication = BranchAdjudication.model_validate_json(raw_adjudication)
        request = requests[adjudication.request_id]
        source = sources[request.mining_state_id]
        if request.category is not adjudication.category:
            raise ValueError("request/adjudication category drifted")
        source_digest = digest(canonical_artifact_bytes(source.model_dump(mode="json")))
        if source_digest != request.source_lineage_sha256:
            raise ValueError("source lineage drifted")
        ordinal = int(adjudication.request_id.rsplit(":", 1)[1])
        target = PAIR_TARGETS[adjudication.category]
        concept, surface = ordinal % target, ordinal // target
        if surface not in range(4):
            raise ValueError("surface index drifted")
        stem = adjudication.request_id.replace(":", "_")
        raw_branch = (run / "raw" / f"{stem}.selected.json").read_bytes()
        inspection = (run / "inspections" / f"{stem}.selected.json").read_bytes()
        provider = (run / "provider" / f"{stem}.json").read_bytes()
        provider_raw = (run / "provider-raw" / f"{stem}.json").read_bytes()
        branch = json.loads(raw_branch)
        if _sha(raw_branch) != adjudication.raw_branch_artifact_sha256:
            raise ValueError("raw branch binding drifted")
        if _sha(inspection) != adjudication.inspection_sha256:
            raise ValueError("inspection binding drifted")
        if _sha(provider) != branch["provider_response_sha256"]:
            raise ValueError("provider evidence binding drifted")
        outcomes[adjudication.request_id] = adjudication.outcome
        counts[adjudication.category][adjudication.outcome.value] += 1
        surfaces[adjudication.category][surface][adjudication.outcome.value] += 1
        concept_rows[adjudication.category][concept][surface] = adjudication.outcome.value
        records.append(
            {
                "adjudication": adjudication,
                "adjudication_sha256": _sha(raw_adjudication),
                "branch": branch,
                "category": adjudication.category,
                "concept": concept,
                "inspection_sha256": _sha(inspection),
                "mining_state_id": request.mining_state_id,
                "provider_evidence_sha256": _sha(provider),
                "provider_raw_sha256": _sha(provider_raw),
                "request": request,
                "surface": surface,
            }
        )
    actual = {category: dict(counter) for category, counter in counts.items()}
    if actual != EXPECTED_OUTCOMES:
        raise ValueError("frozen outcome breakdown drifted")
    eligible = select_eligible_request_ids(outcomes)
    expected_eligible = {
        category: PAIR_TARGETS[category] - DEFICITS.get(category, 0) for category in PAIR_TARGETS
    }
    if {category: len(rows) for category, rows in eligible.items()} != expected_eligible:
        raise ValueError("concept-first eligible inventory drifted")
    if sum(expected_eligible.values()) != 204 or sum(DEFICITS.values()) != 116:
        raise AssertionError("frozen partial closure arithmetic drifted")
    analysis = {
        "category_outcomes": {
            category.value: {
                "all_surfaces": dict(sorted(counts[category].items())),
                "by_surface": {
                    str(surface): dict(sorted(surfaces[category][surface].items()))
                    for surface in range(4)
                },
                "concepts_eligible": len(eligible[category]),
                "concepts_missing": DEFICITS.get(category, 0),
                "concepts_target": PAIR_TARGETS[category],
            }
            for category in PAIR_TARGETS
        },
        "concept_surface_rows": [
            {
                "category": category.value,
                "concept_index": concept,
                "kind": "phase4-mining-concept-surface-outcomes-v1",
                "surfaces": {
                    str(surface): concept_rows[category][concept][surface]
                    for surface in range(4)
                },
            }
            for category, target in PAIR_TARGETS.items()
            for concept in range(target)
        ],
        "eligible": eligible,
    }
    return records, analysis


def _provisional_rows(
    records: list[dict[str, Any]], eligible: dict[PairCategory, list[str]]
) -> list[dict[str, Any]]:
    selected = {request_id for values in eligible.values() for request_id in values}
    rows: list[dict[str, Any]] = []
    for record in records:
        adjudication: BranchAdjudication = record["adjudication"]
        if adjudication.request_id not in selected:
            continue
        branch = record["branch"]
        request: MiningRequest = record["request"]
        rows.append(
            {
                "adjudication_sha256": record["adjudication_sha256"],
                "adjudicator_authority_sha256": adjudication.adjudicator_authority_sha256,
                "category": adjudication.category.value,
                "concept_index": record["concept"],
                "decoded_bytes_sha256": branch["decoded_bytes_sha256"],
                "dpo_materialized": False,
                "expected_effect_sha256": adjudication.expected_effect_sha256,
                "input_token_ids_sha256": request.input_token_ids_sha256,
                "inspection_sha256": record["inspection_sha256"],
                "kind": "phase4-provisional-eligible-outcome-v1",
                "mining_state_id": record["mining_state_id"],
                "outcome": "preference_error",
                "pair_approved": False,
                "provider_evidence_sha256": record["provider_evidence_sha256"],
                "provider_raw_sha256": record["provider_raw_sha256"],
                "raw_branch_sha256": adjudication.raw_branch_artifact_sha256,
                "request_id": adjudication.request_id,
                "reuse_authorized": False,
                "status": "provisional_evidence_only",
                "surface_index": record["surface"],
            }
        )
    rows.sort(key=lambda row: (row["category"], row["concept_index"]))
    if len(rows) != 204 or len({row["request_id"] for row in rows}) != 204:
        raise ValueError("provisional eligible inventory does not close 204 unique concepts")
    return rows


def closeout_files(root: Path, source_commit: str) -> dict[str, bytes]:
    for directory, expected in EXPECTED_MANIFESTS.items():
        _verify_manifest(root, directory, expected, closed=directory != STEP63)
    source_bindings = _verify_source(root, source_commit)
    records, analysis = _run_records(root)
    provisional = _provisional_rows(records, analysis["eligible"])
    outcome_counts = Counter(record["adjudication"].outcome.value for record in records)
    concept_rows = analysis.pop("concept_surface_rows")
    analysis.pop("eligible")
    bindings = {
        "dev_sha256sums_sha256": f"sha256:{EXPECTED_MANIFESTS[DEV]}",
        "run_sha256sums_sha256": f"sha256:{EXPECTED_MANIFESTS[RUN]}",
        "selected_sft_run_sha256sums_sha256": f"sha256:{EXPECTED_MANIFESTS[SFT_RUN]}",
        "step63_dev_sha256sums_sha256": f"sha256:{EXPECTED_MANIFESTS[STEP63]}",
        "v2_sha256sums_sha256": f"sha256:{EXPECTED_MANIFESTS[V2]}",
    }
    post_run = {
        "authorization": False,
        "bindings": bindings,
        "dpo_materialized": False,
        "kind": "phase4-pair-mining-incomplete-closeout-v1",
        "launchable": False,
        "outcome_counts": dict(sorted(outcome_counts.items())),
        "pair_count": 0,
        "provisional_eligible_count": 204,
        "quota_deficit": 116,
        "record_closure": {
            "adjudications": 2560,
            "attempts": 1280,
            "inspections": 2560,
            "provider_evidence": 1280,
            "provider_raw": 1280,
            "raw_branches": 2560,
        },
        "result": "completed_incomplete_quota",
        "runner_or_adjudicator_failure": False,
        "sampler_deleted": True,
        "selected_state_unchanged": True,
        "source_bindings": source_bindings,
        "source_commit": source_commit,
        "test_or_retention_60_opened": False,
    }
    structural_gap = {
        "authorization": False,
        "comparison_axes": [
            "prompt_length",
            "event_count",
            "distractor_alias_count_and_kind",
            "active_yielded_twin_structure",
            "rollover_checkpoint_history",
            "competing_valid_actions",
        ],
        "conclusion": "simplified_synthetic_contexts_were_too_easy_not_direct_target_leakage",
        "dev_content_exported": False,
        "dev_identifiers_exported": False,
        "direct_target_leakage_found": False,
        "evidence": {
            "active_floor_all_surfaces_acceptable": 180,
            "pure_no_trigger_all_surfaces_acceptable": 100,
            "canceled_fire": {
                "mechanics_evidence": 34,
                "on_policy_acceptable": 84,
                "preference_error": 2,
            },
            "mirrored_controls": {
                "mechanics_evidence": 5,
                "non_target_error": 3,
                "on_policy_acceptable": 62,
                "preference_error": 10,
            },
            "deficit_category_synthetic_scaffold": {
                "active_floor_rows": {"count": 180, "matched_yielded_twins": 0},
                "alias_kind_totals": {
                    "fire": 132,
                    "instruction": 0,
                    "pending_fact": 0,
                    "result": 232,
                    "timer": 24,
                    "user": 920,
                },
                "alias_total": {"max": 3, "mean": 1.9, "median": 2},
                "event_count": {"max": 4, "mean": 2.8, "median": 3, "min": 2},
                "input_tokens": {
                    "max": 1437,
                    "mean": 1290,
                    "median": 1297,
                    "min": 1184,
                },
                "mechanically_licensable_route_lower_bound": {
                    "max": 3,
                    "mean": 1.6,
                    "median": 2,
                },
                "multi_alias_kind_rows": 376,
                "multi_route_rows": 376,
                "rollover_rows": 0,
                "rows": 700,
            },
            "step63_dev_failure_structure_aggregate": {
                "active_yielded_twins": {
                    "asymmetric_failure_pairs": 8,
                    "both_members_fail_pairs": 6,
                    "pairs": 14,
                },
                "alias_kind_totals": {
                    "fire": 18,
                    "instruction": 16,
                    "pending_fact": 2,
                    "result": 31,
                    "timer": 21,
                    "user": 213,
                },
                "alias_total": {"max": 15, "mean": 3.3, "median": 3},
                "event_count": {"max": 17, "mean": 5.6, "median": 5, "min": 2},
                "floor_owned_rows": 20,
                "input_tokens": {
                    "max": 14616,
                    "mean": 2076,
                    "median": 1559,
                    "min": 1159,
                },
                "mechanically_licensable_route_lower_bound": {
                    "max": 3,
                    "mean": 1.2,
                    "median": 1,
                },
                "multi_alias_kind_rows": 37,
                "multi_route_rows": 22,
                "post_checkpoint_rows": 10,
                "rollover_rows": 13,
                "rows": 91,
            },
            "structural_interpretation": (
                "The deficit scaffold has more multi-route states, so arbitrary extra route "
                "competition is not the missing variable. Its hard ceilings on history and "
                "aliases, absence of rollover/checkpoints, and unpaired active-floor states "
                "are the stronger gap."
            ),
        },
        "kind": "phase4-structural-distribution-gap-v1",
        "methodological_caveat": (
            "Aggregate DEV failure structure informed the recovery design. A successor mining "
            "yield is therefore diagnostic, not an independent DEV confirmation; no DEV IDs, "
            "labels, lexical bytes, or state payloads may enter successor requests."
        ),
        "test_or_retention_60_opened": False,
        **bindings,
    }
    recovery = {
        "authorization": False,
        "dpo_materialization": False,
        "dpo_training": False,
        "frozen_204": {
            "count": 204,
            "status": "provisional_evidence_only",
            "successor_reuse_requires_explicit_owner_amendment": True,
        },
        "kind": "phase4-wp4-0r-owner-decision-v1",
        "launchable": False,
        "methodology": {
            "concept_first_selection": True,
            "four_predetermined_surfaces_per_concept": True,
            "lexically_and_conceptually_disjoint": True,
            "structurally_matched_from_aggregate_failure_features_only": True,
        },
        "modeled_cost_bound": {
            "authorization": False,
            "current_rate_refresh_required_before_secret_or_provider": True,
            "full_recovery": {
                "hard_ceiling_recommendation_usd": 16,
                "maximum_input_tokens": 27_840_000,
                "maximum_output_tokens": 118_784,
                "maximum_requests": 464,
                "modeled_worst_case_usd": 15.19233,
            },
            "rates_per_million_tokens_usd": {"output": 1.335, "prefill": 0.54},
            "sampler_storage_usd": 0.000153,
            "sentinel": {
                "hard_ceiling_recommendation_usd": 0.5,
                "maximum_input_tokens": 720_000,
                "maximum_output_tokens": 3_072,
                "maximum_requests": 12,
                "modeled_worst_case_usd": 0.393054,
            },
        },
        "missing_concepts": {category.value: count for category, count in DEFICITS.items()},
        "missing_concepts_total": 116,
        "next_authorized_action": None,
        "owner_decisions_required": [
            "create a new WP4-0R authority without reinterpreting WP4-0 as successful",
            "permit or reject reuse of the checksum-bound provisional 204",
            "freeze exactly the 116-category deficit vector and successor request inventory",
            "separately authorize any checkpoint, provider, sampler, spend, or launch access",
        ],
        "recovery_status": "offline_planner_owner_decision_only",
        "sentinel_recommendation": {
            "bulk_calls_authorized": False,
            "calls": 12,
            "design": (
                "one concept times four surfaces for active-floor, canceled-fire, and no-trigger"
            ),
            "pass": "at least one mechanics-valid preference error in each 4-request category",
            "stop": "any category closes zero of four eligible outcomes",
        },
        "test_or_retention_60_access": False,
        **bindings,
    }
    files = {
        "concept-surface-outcomes.jsonl.gz": _gzip_rows(concept_rows),
        "outcome-breakdown.json": canonical_artifact_bytes(analysis),
        "post-run-analysis.json": canonical_artifact_bytes(post_run),
        "provisional-eligible-outcomes.jsonl.gz": _gzip_rows(provisional),
        "structural-gap-analysis.json": canonical_artifact_bytes(structural_gap),
        "wp4-0r-owner-decision.json": canonical_artifact_bytes(recovery),
    }
    sums = "".join(
        f"{sha256(raw).hexdigest()}  {name}\n" for name, raw in sorted(files.items())
    ).encode("ascii")
    return {**files, "SHA256SUMS": sums}


def _representative_examples(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    wanted = {
        PairCategory.STALE_INTEGRATE_VS_SKIP: {
            AdjudicationOutcome.PREFERENCE_ERROR,
            AdjudicationOutcome.NON_TARGET_ERROR,
        },
        PairCategory.ACTIVE_FLOOR_RESPOND_VS_IDLE: {
            AdjudicationOutcome.ON_POLICY_ACCEPTABLE
        },
        PairCategory.CANCELED_FIRE_NUDGE_VS_SKIP: {
            AdjudicationOutcome.ON_POLICY_ACCEPTABLE,
            AdjudicationOutcome.PREFERENCE_ERROR,
            AdjudicationOutcome.MECHANICS_EVIDENCE,
        },
        PairCategory.PURE_NO_TRIGGER_RESTRAINT: {
            AdjudicationOutcome.ON_POLICY_ACCEPTABLE
        },
        PairCategory.MIRRORED_POSITIVE_CONTROLS: {
            AdjudicationOutcome.ON_POLICY_ACCEPTABLE,
            AdjudicationOutcome.PREFERENCE_ERROR,
            AdjudicationOutcome.MECHANICS_EVIDENCE,
            AdjudicationOutcome.NON_TARGET_ERROR,
        },
    }
    selected: dict[tuple[PairCategory, AdjudicationOutcome], dict[str, Any]] = {}
    for record in sorted(records, key=lambda item: item["adjudication"].request_id):
        adjudication: BranchAdjudication = record["adjudication"]
        key = adjudication.category, adjudication.outcome
        if adjudication.outcome in wanted.get(adjudication.category, set()) and key not in selected:
            selected[key] = {
                "adjudication": adjudication.model_dump(mode="json"),
                "adjudication_sha256": record["adjudication_sha256"],
                "kind": "phase4-planner-representative-example-v1",
                "raw_branch": record["branch"],
                "raw_branch_sha256": adjudication.raw_branch_artifact_sha256,
            }
    if set(selected) != {
        (category, outcome) for category, outcomes in wanted.items() for outcome in outcomes
    }:
        raise ValueError("representative outcome coverage drifted")
    order = sorted(selected, key=lambda item: (item[0].value, item[1].value))
    return [selected[key] for key in order]


def lean_review_files(root: Path, closeout_directory: Path) -> dict[str, bytes]:
    closeout_root = root / closeout_directory
    closeout_sums = closeout_root.joinpath("SHA256SUMS").read_bytes()
    _verify_manifest(root, closeout_directory, sha256(closeout_sums).hexdigest())
    records, analysis = _run_records(root)
    provisional_raw = closeout_root.joinpath("provisional-eligible-outcomes.jsonl.gz").read_bytes()
    recovery = json.loads(closeout_root.joinpath("wp4-0r-owner-decision.json").read_bytes())
    structural_raw = closeout_root.joinpath("structural-gap-analysis.json").read_bytes()
    lifecycle = {
        "detached_logs": json.loads((root / RUN / "detached-logs.json").read_bytes()),
        "lifecycle_closeout": json.loads(
            (root / RUN / "evidence/0006-lifecycle_closeout.json").read_bytes()
        ),
        "sampler_deletion": json.loads((root / RUN / "sampler-deletion.json").read_bytes()),
        "status": json.loads((root / RUN / "status.json").read_bytes()),
    }
    category_summary = {
        category: {
            "all_surface_outcomes": values["all_surfaces"],
            "eligible_concepts": values["concepts_eligible"],
            "missing_concepts": values["concepts_missing"],
            "target_concepts": values["concepts_target"],
        }
        for category, values in analysis["category_outcomes"].items()
    }
    review = {
        "authority_constraints": {
            "current_paid_authority_expired": True,
            "dpo_materialization_or_training_authorized": False,
            "provider_checkpoint_secret_or_spend_authorized": False,
            "retry_resample_or_quota_reduction_authorized": False,
            "test_or_retention_60_access_authorized": False,
        },
        "category_summary": category_summary,
        "closeout_sha256sums_sha256": _sha(closeout_sums),
        "deficit": recovery["missing_concepts"],
        "deficit_total": 116,
        "kind": "phase4-incomplete-mining-lean-planner-review-v1",
        "lifecycle": lifecycle,
        "provisional_inventory": {
            "count": 204,
            "dpo_materialized": False,
            "pair_approved": False,
            "path": f"{closeout_directory.as_posix()}/provisional-eligible-outcomes.jsonl.gz",
            "sha256": _sha(provisional_raw),
        },
        "recovery_proposal": recovery,
        "run_archive": {
            "included_in_bundle": False,
            "path": RUN.as_posix(),
            "sha256sums_sha256": f"sha256:{EXPECTED_MANIFESTS[RUN]}",
        },
        "status": "completed_incomplete_quota",
    }
    message = f"""WP4-0 planner review: completed_incomplete_quota

The authorized run completed 1,280/1,280 one-shot requests with zero optimizer calls; the sampler
was deleted, selected step63 stayed unchanged, and detached logs were sealed. Run root:
sha256:{EXPECTED_MANIFESTS[RUN]}.

Concept-first preference eligibility closed 204/320, but the frozen all-category gate requires all
320, so pair_count remains 0. Exact deficit: stale 5, canceled-fire 28, active-floor 45,
mirrored controls 13, pure no-trigger 25 (116 total). Active-floor was 180/180 acceptable and pure
no-trigger 100/100 acceptable; the shortfall is predominantly absent on-policy errors, not runner
or adjudicator failure. The 204 are checksum-bound provisional evidence only at
{_sha(provisional_raw)}.

Aggregate structural comparison indicates the deficit scaffolds were too easy: they cap at 4 events
and 3 aliases, have no rollover/checkpoint history, and the 180 active-floor rows have no matched
yielded twins. Disjoint DEV failures reach 17 events and 15 aliases, include 13 rollover rows and
14 active/yielded pairs. This is DEV-adaptive design evidence, so any recovery yield is diagnostic,
not independent DEV confirmation; no DEV identifiers, labels, text, or hashes may enter requests.

Proposal: prepare exactly 116 harder, disjoint concepts with four frozen surfaces each. Before any
bulk calls, run a 12-request sentinel (one concept x four surfaces for active-floor, canceled-fire,
and no-trigger); stop if any category yields 0/4 mechanics-valid preference errors. Current-rate
conservative bounds are $0.393054 sentinel / $15.192330 full, with recommended ceilings $0.50 / $16
and a mandatory fresh public pricing check before secrets or provider access.

No retry, resampling, quota reduction, reuse of the 204, provider/checkpoint access, TEST,
retention-60, DPO materialization, or DPO training is currently authorized. A new explicit owner
amendment and separate execution authorization are required.
""".encode()
    files = {
        "planner-message.txt": message,
        "planner-review.json": canonical_artifact_bytes(review),
        "representative-raw-adjudication-examples.jsonl.gz": _gzip_rows(
            _representative_examples(records)
        ),
        "structural-gap-analysis.json": structural_raw,
    }
    sums = "".join(
        f"{sha256(raw).hexdigest()}  {name}\n" for name, raw in sorted(files.items())
    ).encode("ascii")
    return {**files, "SHA256SUMS": sums}


def _zip_bytes(directory_name: str, files: dict[str, bytes]) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, raw in sorted(files.items()):
            info = zipfile.ZipInfo(f"{directory_name}/{name}", date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, raw)
    return output.getvalue()


def build_lean_review(output: Path, zip_path: Path, closeout_directory: Path) -> None:
    files = lean_review_files(ROOT, closeout_directory)
    publish_directory_transaction(output, files)
    archive = _zip_bytes(output.name, files)
    checksum_path = zip_path.with_suffix(zip_path.suffix + ".sha256")
    archive_exists = zip_path.exists() or zip_path.is_symlink()
    checksum_exists = checksum_path.exists() or checksum_path.is_symlink()
    if archive_exists or checksum_exists:
        raise FileExistsError("refusing to replace an existing planner-review archive")
    zip_path.write_bytes(archive)
    checksum_path.write_text(f"{sha256(archive).hexdigest()}  {zip_path.name}\n", encoding="ascii")


def build(output: Path, source_commit: str) -> None:
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"refusing to replace existing closeout: {output}")
    publish_directory_transaction(output, closeout_files(ROOT, source_commit))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--lean-output", type=Path, default=LEAN_OUTPUT)
    parser.add_argument("--lean-zip", type=Path, default=LEAN_ZIP)
    args = parser.parse_args()
    build(args.output, args.source_commit)
    build_lean_review(args.lean_output, args.lean_zip, args.output)


if __name__ == "__main__":
    main()
