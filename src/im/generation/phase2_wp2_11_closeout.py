"""Build the checksum-bound WP2-11 Phase 2 report and Phase 3 handoff."""

from __future__ import annotations

import json
from collections import Counter
from hashlib import sha256
from pathlib import Path

from im.assets.model import canonical_artifact_bytes
from im.generation.phase2_wp2_9_selection import SelectionStream, solve_lexicographic
from im.generation.phase2_wp2_10_candidate import _verified_packet_files
from im.generation.publication import publish_directory_transaction
from im.policy.prompted import ModelPricing
from im.probes.harness.client import response_usage
from im.probes.harness.cost import usage_cost
from im.probes.harness.models import ProviderUsage

_ROOT = Path(__file__).resolve().parents[3]
OUTPUT = _ROOT / "review" / "phase2" / "wp2-11-phase-closeout"

_PACKETS = {
    "interaction_selection": "review/phase2/wp2-9-stage2-selection-proof",
    "d13": "review/phase2/wp2-9-d13-trust-completion",
    "bias_report": "review/phase2/wp2-9-bias-report",
    "replay": "review/phase2/wp2-9-replay-freeze",
    "dev": "review/phase2/dev-gate-c-closeout",
    "test": "review/phase2/wp2-10-test-closeout",
    "wp2_6": "review/phase2/wp2-6-exit",
}

_RESERVOIRS = (
    "review/phase2/lookup-cluster-exit/phase4-reservoir.jsonl",
    "review/phase2/lookup-prose-need-addendum-v1/amended-lookup-closeout/phase4-reservoir.jsonl",
    "review/phase2/timer-wave-2-repaired-v3-review/phase4-reservoir.jsonl",
)


class Wp211CloseoutError(ValueError):
    """Phase 2 cannot close from the published evidence."""


def _json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_bytes())
    if not isinstance(value, dict):
        raise Wp211CloseoutError(f"expected a JSON object: {path}")
    return value


def _bindings(root: Path) -> dict[str, dict[str, object]]:
    bindings: dict[str, dict[str, object]] = {}
    for name, relative in _PACKETS.items():
        path = root / relative
        files = _verified_packet_files(path)
        bindings[name] = {
            "path": relative,
            "sha256sums_sha256": "sha256:" + sha256(files["SHA256SUMS"]).hexdigest(),
        }
    return bindings


def _interaction_stats(proof: dict[str, object]) -> dict[str, object]:
    selected = set(proof["selected"])
    rows = [row for row in proof["optimizer_inputs"] if row["stream_sha256"] in selected]
    if len(rows) != proof["stream_count"]:
        raise Wp211CloseoutError("interaction proof does not bind every selected stream")
    actions: Counter[str] = Counter()
    families: Counter[str] = Counter()
    idle: Counter[str] = Counter()
    lengths: Counter[str] = Counter()
    for row in rows:
        actions.update(row["action_counts"])
        families[str(row["family"])] += int(row["decision_count"])
        idle.update(row["idle_reason_counts"])
        lengths[str(row["stream_length_bucket"])] += int(row["decision_count"])
    if sum(actions.values()) != 2_000 or actions["idle"] != 1_000:
        raise Wp211CloseoutError("interaction selection no longer has 2,000 / 1,000-idle")
    return {
        "action_counts": dict(sorted(actions.items())),
        "decision_count": sum(actions.values()),
        "family_counts": dict(sorted(families.items())),
        "idle_reason_counts": dict(sorted(idle.items())),
        "stream_count": len(rows),
        "stream_length_bucket_decisions": dict(sorted(lengths.items())),
    }


def _selection_stream(row: dict[str, object]) -> SelectionStream:
    return SelectionStream(
        stream_sha256=str(row["stream_sha256"]),
        family=str(row["family"]),
        source_unit_id=str(row["source_unit_id"]),
        template_id=str(row["template_id"]),
        timing_regime=str(row["timing_regime"]),
        difficulty_tags=tuple(str(value) for value in row["difficulty_tags"]),
        stream_length_bucket=str(row["stream_length_bucket"]),
        decision_count=int(row["decision_count"]),
        action_counts={str(key): int(value) for key, value in row["action_counts"].items()},
        idle_reason_counts={
            str(key): int(value) for key, value in row["idle_reason_counts"].items()
        },
        action_floor_counts={
            (str(item["action"]), str(item["floor"])): int(item["count"])
            for item in row["action_floor_counts"]
        },
        rank_sum=int(row["rank_sum"]),
    )


def _interaction_reserve(proof: dict[str, object]) -> dict[str, object]:
    selected = set(proof["selected"])
    remaining = [
        _selection_stream(row)
        for row in proof["optimizer_inputs"]
        if row["stream_sha256"] not in selected
    ]
    result = solve_lexicographic(
        remaining,
        target_decisions=250,
        family_action_quotas={},
        idle_reason_quotas={},
        selection_seed=str(proof["selection_seed"]),
    )
    by_digest = {stream.stream_sha256: stream for stream in remaining}
    if set(result.selected).intersection(selected):
        raise Wp211CloseoutError("interaction reserve overlaps the binding selection")
    if sum(by_digest[item].decision_count for item in result.selected) != 250:
        raise Wp211CloseoutError("interaction reserve is not exactly 250 decisions")
    return {
        "decision_count": 250,
        "disjoint_from_binding_selection": True,
        "kind": "phase2-wp2-11-interaction-reserve",
        "objective_basis": "the same eight frozen selection terms; no new evidence features",
        "objective_vector": result.objective_vector,
        "proofs": [
            {
                "mip_gap": item.mip_gap,
                "optimum": item.optimum,
                "solver_objective_bound": item.solver_objective_bound,
                "solver_objective_value": item.solver_objective_value,
                "status": item.status,
                "term": item.term,
            }
            for item in result.proofs
        ],
        "selected_stream_sha256s": sorted(result.selected),
        "solver": result.solver,
        "stream_count": len(result.selected),
        "teacher_derived_features_available_to_optimizer": [],
    }


def _canary_ledger(root: Path) -> dict[str, object]:
    ledgers = (
        "review/phase2/timer-cluster-exit/trust-ledger.json",
        "review/phase2/lookup-cluster-exit/trust-ledger.json",
        "review/phase2/mark-cluster-exit-v2/trust-ledger.json",
    )
    cells: list[dict[str, object]] = []
    evidence: list[dict[str, object]] = []
    for relative in ledgers:
        path = root / relative
        value = _json(path)
        source_cells = value.get("cells")
        if not isinstance(source_cells, list):
            raise Wp211CloseoutError(f"trust ledger lacks cells: {relative}")
        cells.extend(source_cells)
        evidence.append(
            {
                "path": relative,
                "sha256": "sha256:" + sha256(path.read_bytes()).hexdigest(),
            }
        )
    prose_path = (
        root
        / "review/phase2/lookup-prose-need-addendum-v1/amended-lookup-closeout/exit-report.json"
    )
    prose = _json(prose_path)
    for entry in prose["split_ledger"]:
        cells.append(
            {
                "family": entry["family"],
                "protocol": "generation",
                "shape": entry["shape"],
                "state": "uncleared",
            }
        )
    evidence.append(
        {
            "path": str(prose_path.relative_to(root)),
            "sha256": "sha256:" + sha256(prose_path.read_bytes()).hexdigest(),
        }
    )
    if any(cell.get("state") != "uncleared" for cell in cells):
        raise Wp211CloseoutError("Phase 2 unexpectedly contains a cleared teacher cell")
    return {
        "canary": {
            "decision_count": 265,
            "documented_in": "docs/phase-2-implementation.md",
            "stream_touch_rate": 0.55,
            "teacher_error_count": 43,
            "teacher_error_rate": 43 / 265,
        },
        "cells": cells,
        "cleared_cell_count": 0,
        "evidence": evidence,
        "teacher_auto_trusted_count": 0,
        "uncleared_cell_count": len(cells),
    }


def _reservoir_inventory(root: Path) -> dict[str, object]:
    sources: list[dict[str, object]] = []
    total = 0
    for relative in _RESERVOIRS:
        path = root / relative
        rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
        if any(row.get("direct_dpo_eligibility") is not False for row in rows):
            raise Wp211CloseoutError(f"reservoir row is directly DPO-eligible: {relative}")
        sources.append(
            {
                "direct_dpo_eligibility": False,
                "path": relative,
                "record_count": len(rows),
                "sha256": "sha256:" + sha256(path.read_bytes()).hexdigest(),
            }
        )
        total += len(rows)
    if total != 119:
        raise Wp211CloseoutError(f"expected 119 Phase 4 reservoir rows, found {total}")
    return {
        "direct_dpo_eligibility": False,
        "record_count": total,
        "sources": sources,
    }


def _walk(value: object):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def _teacher_usage(root: Path) -> dict[str, object]:
    responses: dict[str, dict[str, object]] = {}
    for path in (root / "review" / "phase2").rglob("*.jsonl"):
        if "wp2-7-recovery-planner-package" in path.as_posix():
            continue
        for line in path.read_text(errors="strict").splitlines():
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            for candidate in _walk(value):
                response = candidate.get("response")
                body = response.get("body") if isinstance(response, dict) else None
                if not isinstance(body, dict):
                    continue
                response_id = body.get("id")
                model = body.get("model")
                if (
                    isinstance(response_id, str)
                    and isinstance(model, str)
                    and model.startswith("gpt-5.6-")
                    and isinstance(body.get("usage"), dict)
                ):
                    responses[response_id] = body
    usage = ProviderUsage()
    models: Counter[str] = Counter()
    for body in responses.values():
        usage += response_usage(body)
        models[str(body["model"])] += 1
    pricing = ModelPricing()
    cost = usage_cost(usage, pricing, billing_multiplier=pricing.batch_multiplier)
    return {
        "actual_api_responses": len(responses),
        "actual_provider_usage": usage.as_json(),
        "derived_usage_cost_usd": format(cost, "f"),
        "model_counts": dict(sorted(models.items())),
        "pricing": pricing.as_json()
        if hasattr(pricing, "as_json")
        else {
            "batch_multiplier": format(pricing.batch_multiplier, "f"),
            "cache_write_multiplier": format(pricing.cache_write_multiplier, "f"),
            "cached_input_per_million": format(pricing.cached_input_per_million, "f"),
            "input_per_million": format(pricing.input_per_million, "f"),
            "output_per_million": format(pricing.output_per_million, "f"),
            "source_date": pricing.source_date,
        },
        "status": "metered_api_actual; not a complete billing-dashboard total",
        "teacher_budget_usd": {"low": 15, "high": 30},
        "unmetered_teacher_channels": {
            "fresh_chat_ui_rounds": "not_recorded",
            "note": (
                "Later GPT-5.6 Sol/high rounds used fresh Chat UI transport; no API usage "
                "artifact or marginal charge was recorded."
            ),
        },
    }


def _budget_report(root: Path) -> dict[str, object]:
    timer = _json(root / "review/phase2/timer-cluster-exit/exit-report.json")
    lookup = _json(root / "review/phase2/lookup-cluster-exit/exit-report.json")
    timer_hours = timer["d7_preliminary_projection"]["chat_submission_labor"]["minimum_hours"]
    lookup_hours = lookup["d7_binding_projection"]["chat_submission_labor"]["minimum_hours"]
    return {
        "owner_hours": {
            "honest_total_budget_hours": {"low": 19, "high": 29},
            "lines": {
                "interaction_corpus_review": {
                    "budget_hours": {"low": 12, "high": 18},
                    "evidence_backed_minimum_hours": timer_hours + lookup_hours,
                    "full_actual_hours": "not_recorded",
                },
                "asset_readiness": {
                    "budget_hours": {"low": 2, "high": 3.5},
                    "full_actual_hours": "not_recorded",
                },
                "replay_sampling_and_review": {
                    "budget_hours": {"low": 0.5, "high": 1},
                    "full_actual_hours": "not_recorded",
                },
                "dev_and_final_test_gold": {
                    "budget_hours": {"low": 4, "high": 7},
                    "full_actual_hours": "not_recorded",
                },
            },
            "status": "full_actuals_not_instrumented; no hours fabricated",
            "stop_rule": {
                "binding_checkpoint": "after timer and lookup clusters",
                "invoked": False,
                "projected_remaining_detailed_review_hours": {"low": 5, "high": 8},
                "threshold_hours": 12,
            },
        },
        "teacher_spend": _teacher_usage(root),
    }


def _phase3_handoff(bindings: dict[str, dict[str, object]]) -> dict[str, object]:
    return {
        "first_action": "pin model, tokenizer, renderer, SDK revisions, then export checkpoints",
        "inputs": {
            "dev": {**bindings["dev"], "use": "checkpoint selection and early stopping only"},
            "interaction": {
                **bindings["d13"],
                "decision_count": 2_000,
                "loss": "gold action tokens only; never compact across streams",
            },
            "replay": {
                **bindings["replay"],
                "release_constraint": (
                    "Contains No Robots rows: attribution and CC-BY-NC-4.0 non-commercial "
                    "terms apply to any released subset."
                ),
                "row_count": 1_000,
                "loss": "final assistant tokens only",
                "weight": {"start": 0.30, "allowed_range": [0.25, 0.4]},
            },
            "test": {
                **bindings["test"],
                "use": "open once after the SFT checkpoint and DPO procedure are frozen",
            },
        },
        "phase4_reservoir": "reservoir-inventory.json",
    }


def build_phase2_closeout(*, repository_root: Path = _ROOT) -> dict[str, bytes]:
    root = repository_root.resolve()
    bindings = _bindings(root)
    proof = _json(root / _PACKETS["interaction_selection"] / "stage2-selection-proof.json")
    d13 = _json(root / _PACKETS["d13"] / "closure.json")
    replay = _json(root / _PACKETS["replay"] / "selection-report.json")
    dev = _json(root / _PACKETS["dev"] / "DEV-FREEZE.json")
    test = _json(root / _PACKETS["test"] / "TEST-EVALUATION-SEAL.json")
    if (
        d13.get("record_count") != 2_000
        or d13.get("unresolved") != 0
        or replay.get("selected_count") != 1_000
        or dev.get("status") != "frozen"
        or test.get("status") != "frozen"
    ):
        raise Wp211CloseoutError("a required Phase 2 freeze is incomplete")

    interaction = _interaction_stats(proof)
    reserve = _interaction_reserve(proof)
    canary = _canary_ledger(root)
    reservoir = _reservoir_inventory(root)
    budget = _budget_report(root)
    handoff = _phase3_handoff(bindings)
    report = {
        "artifact_bindings": bindings,
        "bias": {
            "accepted_streams": 505,
            "adjudicated_streams": 517,
            "genuine_rejected_streams": 12,
            "repair_supersessions_excluded": 43,
            "teacher_agreement_used_as_selection_feature": False,
        },
        "corpora": {
            "dev": {"decision_count": 300, "family_count": 11, "status": "frozen"},
            "interaction": interaction,
            "replay": {
                "family_counts": replay["family_counts"],
                "length_band_counts": replay["length_band_counts"],
                "multi_turn_count": replay["multi_turn_count"],
                "row_count": replay["selected_count"],
                "supervised_token_total": replay["supervised_token_total"],
            },
            "test": {"decision_count": 400, "family_count": 11, "status": "sealed"},
        },
        "exit_gates": {
            "P2-1_allocation": "pass",
            "P2-2_review_coverage": "pass",
            "P2-3_selection_honesty": "pass",
            "P2-4_split_integrity": "pass",
            "P2-5_replay_contract": "pass",
            "P2-6_eval_gold": "pass",
            "P2-7_reservoir_and_audit": "pass",
            "P2-8_budget_honesty": "qualified_pass_full_owner_hours_not_instrumented",
        },
        "format_version": 1,
        "git_tag": {
            "requested": "phase2-close",
            "status": "pending_commit",
            "reason": "the current Phase 2 artifacts are not represented by repository HEAD",
        },
        "kind": "phase2-wp2-11-closeout",
        "status": "closed_with_owner_hours_telemetry_qualification",
    }
    files = {
        "budget-and-spend.json": canonical_artifact_bytes(budget),
        "canary-cleared-cell-ledger.json": canonical_artifact_bytes(canary),
        "interaction-reserve.json": canonical_artifact_bytes(reserve),
        "phase-report.json": canonical_artifact_bytes(report),
        "phase3-handoff.json": canonical_artifact_bytes(handoff),
        "reservoir-inventory.json": canonical_artifact_bytes(reservoir),
    }
    teacher = budget["teacher_spend"]
    files["PHASE-REPORT.md"] = f"""# Phase 2 closeout

**Status: closed with one telemetry qualification — 2026-07-31.**

- Interaction: 354 whole streams / 2,000 decisions / exactly 1,000 idle.
- Replay: 1,000 rows / 200 multi-turn / 100,003 supervised tokens.
- Evaluation: DEV frozen at 300; hidden TEST sealed at 400.
- D13: 512 human, 1,488 oracle-teacher agreement, zero auto-trusted, zero unresolved.
- Phase 4 reservoir: 119 records, all `direct_dpo_eligibility=false`.
- Metered teacher API evidence: {teacher["actual_api_responses"]} unique responses; derived usage
  cost ${teacher["derived_usage_cost_usd"]} under the pinned Batch pricing snapshot. Later Sol/high
  Chat UI rounds have no recorded API usage or marginal charge, so this is not a billing total.

All corpus, selection, bias, split, replay, evaluation, and audit gates pass. P2-8 is a qualified
pass because complete owner-hour actuals were never instrumented; the report preserves the four
D12 budgets and the available 2.15-hour interaction-labor lower bound without inventing totals.

The `phase2-close` Git tag remains pending until these working-tree artifacts are committed.
""".encode()
    files["SHA256SUMS"] = "".join(
        f"{sha256(payload).hexdigest()}  {name}\n" for name, payload in sorted(files.items())
    ).encode()
    return files


def materialize_phase2_closeout(
    output: Path = OUTPUT, *, repository_root: Path = _ROOT
) -> dict[str, bytes]:
    if output.exists():
        raise Wp211CloseoutError("WP2-11 closeout already exists; refusing replacement")
    files = build_phase2_closeout(repository_root=repository_root)
    publish_directory_transaction(output, files)
    return files
