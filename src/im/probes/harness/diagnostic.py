"""Pre-registered post-amendment diagnostic population and gates."""

from __future__ import annotations

import json
from collections.abc import Collection
from hashlib import sha256

from im.probes.harness.batch import (
    BatchDecoder,
    BatchWorkItem,
    select_primary_work,
)
from im.probes.harness.models import HarnessRun

ACTIVE_FLOOR_PROBE_IDS = tuple(f"f10-t{index:02d}-a" for index in range(1, 7))
YIELDED_FLOOR_PROBE_IDS = tuple(f"f10-t{index:02d}-b" for index in range(1, 7))
CONTROL_PROBE_IDS = tuple(f"f07-t{index:02d}-a" for index in range(1, 7))
DIAGNOSTIC_PROBE_IDS = (
    *ACTIVE_FLOOR_PROBE_IDS,
    *YIELDED_FLOOR_PROBE_IDS,
    *CONTROL_PROBE_IDS,
)

_EXPECTED_PRIMARY_COUNTS = {
    BatchDecoder.ACTION: 18,
    BatchDecoder.PAIRWISE: 108,
    BatchDecoder.LISTWISE: 18,
}

DIAGNOSTIC_SPEC = {
    "spec_id": "wp15-active-floor-diagnostic-v1",
    "model": "gpt-5.6-terra",
    "reasoning_effort": "high",
    "max_output_tokens": 8192,
    "probe_strata": {
        "active_floor": list(ACTIVE_FLOOR_PROBE_IDS),
        "yielded_floor": list(YIELDED_FLOOR_PROBE_IDS),
        "active_nudge_controls": list(CONTROL_PROBE_IDS),
    },
    "presentations": {
        "generation": {"variants": ["v1"], "per_probe": 1},
        "pairwise": {
            "variants": ["v1", "v2", "v3"],
            "expected_positions": ["A", "B"],
            "per_probe": 6,
        },
        "listwise": {"variants": ["v1"], "per_probe": 1},
        "semantic_text": {
            "conditional_on_structural_match": True,
            "expected_probe_ids": list(YIELDED_FLOOR_PROBE_IDS),
        },
    },
    "gates": {
        "every_generation_schema_reference_license": "18/18",
        "each_stratum_generation": "6/6",
        "each_stratum_pairwise": "36/36",
        "each_stratum_listwise_top1_and_order": "6/6",
        "yielded_semantic_text": "6/6 when structurally eligible",
        "pairwise_position": "54/54 for A and 54/54 for B",
        "family10_variant": "24/24 for each of v1, v2, and v3",
    },
}


def diagnostic_spec_sha256() -> str:
    """Return the stable identity of the pre-registered diagnostic design."""
    encoded = json.dumps(
        DIAGNOSTIC_SPEC,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return "sha256:" + sha256(encoded).hexdigest()


def select_diagnostic_work(
    primary: tuple[BatchWorkItem, ...],
) -> tuple[BatchWorkItem, ...]:
    """Select the exact 144 signed primary requests without rebuilding their bodies."""
    selected_ids = frozenset(DIAGNOSTIC_PROBE_IDS)
    selected = select_primary_work(primary, selected_ids)
    counts = {
        decoder: sum(item.decoder is decoder for item in selected)
        for decoder in BatchDecoder
    }
    if any(counts[decoder] != count for decoder, count in _EXPECTED_PRIMARY_COUNTS.items()):
        raise ValueError(f"diagnostic primary protocol counts changed: {counts}")
    if counts[BatchDecoder.SEMANTIC] != 0 or len(selected) != 144:
        raise ValueError("diagnostic primary plan must contain exactly 144 requests")
    if any(
        sum(item.identity.probe_id == probe_id for item in selected) != 8
        for probe_id in selected_ids
    ):
        raise ValueError("each diagnostic probe must contribute exactly eight primary requests")
    return selected


def compute_diagnostic_metrics(run: HarnessRun) -> dict[str, object]:
    """Score only the frozen diagnostic boundary with explicit small-sample gates."""
    _assert_population(run)
    active = _protocol_rates(run, ACTIVE_FLOOR_PROBE_IDS)
    yielded = _protocol_rates(run, YIELDED_FLOOR_PROBE_IDS)
    controls = _protocol_rates(run, CONTROL_PROBE_IDS)
    yielded_semantic = _rate(
        [
            result.executed and result.response_valid and result.passed
            for result in run.semantic_text
        ]
    )
    generation_safety = _rate(
        [
            result.schema_valid and result.reference_valid and result.license_allowed
            for result in run.generation
        ]
    )
    expected_a = _rate(
        [result.correct for result in run.pairwise if result.expected_position == "A"]
    )
    expected_b = _rate(
        [result.correct for result in run.pairwise if result.expected_position == "B"]
    )
    position_bias = abs(float(expected_a["rate"]) - float(expected_b["rate"]))
    family10_pairwise = [result for result in run.pairwise if result.family_id == 10]
    variant_rates = {
        variant_id: _rate(
            [result.correct for result in family10_pairwise if result.variant_id == variant_id]
        )
        for variant_id in ("v1", "v2", "v3")
    }
    family10_paraphrase_spread = max(
        float(rate["rate"]) for rate in variant_rates.values()
    ) - min(float(rate["rate"]) for rate in variant_rates.values())
    gates = {
        "generation_schema_reference_license": _gate(
            float(generation_safety["rate"]), 1.0, ">="
        ),
        "active_floor_generation": _gate(
            float(active["generation"]["rate"]), 1.0, ">="
        ),
        "active_floor_pairwise": _gate(
            float(active["pairwise"]["rate"]), 1.0, ">="
        ),
        "active_floor_listwise": _gate(
            float(active["listwise"]["rate"]), 1.0, ">="
        ),
        "yielded_floor_generation": _gate(
            float(yielded["generation"]["rate"]), 1.0, ">="
        ),
        "yielded_floor_pairwise": _gate(
            float(yielded["pairwise"]["rate"]), 1.0, ">="
        ),
        "yielded_floor_listwise": _gate(
            float(yielded["listwise"]["rate"]), 1.0, ">="
        ),
        "yielded_semantic_text": _gate(float(yielded_semantic["rate"]), 1.0, ">="),
        "control_generation": _gate(
            float(controls["generation"]["rate"]), 1.0, ">="
        ),
        "control_pairwise": _gate(float(controls["pairwise"]["rate"]), 1.0, ">="),
        "control_listwise": _gate(float(controls["listwise"]["rate"]), 1.0, ">="),
        "pairwise_expected_a": _gate(float(expected_a["rate"]), 1.0, ">="),
        "pairwise_expected_b": _gate(float(expected_b["rate"]), 1.0, ">="),
        "family10_pairwise_v1": _gate(
            float(variant_rates["v1"]["rate"]), 1.0, ">="
        ),
        "family10_pairwise_v2": _gate(
            float(variant_rates["v2"]["rate"]), 1.0, ">="
        ),
        "family10_pairwise_v3": _gate(
            float(variant_rates["v3"]["rate"]), 1.0, ">="
        ),
        "position_bias": _gate(position_bias, 0.0, "<="),
        "family10_paraphrase_spread": _gate(
            family10_paraphrase_spread, 0.10, "<="
        ),
    }
    return {
        "population": {
            "logical_probes": len(DIAGNOSTIC_PROBE_IDS),
            "primary_requests": 144,
            "expected_semantic_requests": 6,
            "passing_path_requests": 150,
            "absolute_one_correction_ceiling": 300,
            "diagnostic_spec_sha256": diagnostic_spec_sha256(),
            "active_floor_probe_ids": list(ACTIVE_FLOOR_PROBE_IDS),
            "yielded_floor_probe_ids": list(YIELDED_FLOOR_PROBE_IDS),
            "control_probe_ids": list(CONTROL_PROBE_IDS),
        },
        "active_floor": active,
        "yielded_floor": yielded,
        "yielded_semantic_text": yielded_semantic,
        "controls": controls,
        "generation_safety": generation_safety,
        "pairwise_position": {
            "expected_a": expected_a,
            "expected_b": expected_b,
            "bias": position_bias,
        },
        "family10_pairwise_variant_accuracy": variant_rates,
        "family10_paraphrase_spread": family10_paraphrase_spread,
        "gates": gates,
        "all_gates_passed": all(bool(gate["passed"]) for gate in gates.values()),
    }


def render_diagnostic_report(
    *,
    metrics: dict[str, object],
    cost_estimate: dict[str, object],
    actual_cost_usd: str,
    repository_commit: str,
    manifest_sha256: str,
    review_sha256: str,
    model: str,
    reasoning_effort: str,
    jobs: list[dict[str, object]],
    total_usage: dict[str, int],
    submitted_usage: dict[str, int],
) -> str:
    """Render the immutable human-readable diagnostic result."""
    verdict = "PASS" if metrics["all_gates_passed"] else "FAIL"
    gates = metrics["gates"]
    if not isinstance(gates, dict):  # pragma: no cover - internal typed construction.
        raise TypeError("diagnostic gates must be a mapping")
    gate_rows = []
    for name, raw_gate in gates.items():
        if not isinstance(raw_gate, dict):  # pragma: no cover - internal typed construction.
            raise TypeError("diagnostic gate must be a mapping")
        gate_rows.append(
            "| "
            + " | ".join(
                (
                    str(name),
                    str(raw_gate["comparison"]),
                    f"{float(raw_gate['threshold']):.4f}",
                    f"{float(raw_gate['observed']):.4f}",
                    "PASS" if raw_gate["passed"] else "FAIL",
                )
            )
            + " |"
        )
    job_lines = [
        f"- `{job['stage']}` shard {job['shard_index']}: `{job['batch_id']}`; "
        f"{job['request_count']} requests; input `{job['input_sha256']}`; "
        f"output `{job['output_sha256']}`; error `{job['error_sha256']}`; "
        f"status `{job['status']}`."
        for job in jobs
    ]
    return "\n".join(
        (
            "# WP15 Active-Floor Diagnostic",
            "",
            f"**Verdict: {verdict}.**",
            "",
            "## Frozen identity",
            "",
            f"- Diagnostic spec: `{diagnostic_spec_sha256()}`.",
            f"- Repository commit: `{repository_commit}`.",
            f"- Manifest: `{manifest_sha256}`.",
            f"- Review: `{review_sha256}`.",
            f"- Model: `{model}` with reasoning effort `{reasoning_effort}`.",
            "- Provider path: OpenAI Batch API targeting `/v1/responses`.",
            "",
            "## Pre-registered gates",
            "",
            "| Gate | Comparison | Threshold | Observed | Verdict |",
            "|---|---:|---:|---:|---:|",
            *gate_rows,
            "",
            "## Cost",
            "",
            f"- Provider-usage charge under pinned Batch pricing: `${actual_cost_usd}`.",
            "- Total decoded provider usage:",
            "",
            "```json",
            json.dumps(total_usage, indent=2, sort_keys=True),
            "```",
            "- Usage submitted during the final/resume invocation:",
            "",
            "```json",
            json.dumps(submitted_usage, indent=2, sort_keys=True),
            "```",
            "- Offline estimate:",
            "",
            "```json",
            json.dumps(cost_estimate, indent=2, sort_keys=True),
            "```",
            "",
            "## Batch jobs",
            "",
            *(job_lines or ["- No provider jobs were submitted."]),
            "",
            "## Full diagnostic metrics",
            "",
            "```json",
            json.dumps(metrics, indent=2, sort_keys=True),
            "```",
            "",
        )
    )


def _assert_population(run: HarnessRun) -> None:
    expected = frozenset(DIAGNOSTIC_PROBE_IDS)
    generation_ids = [result.probe_id for result in run.generation]
    listwise_ids = [result.probe_id for result in run.listwise]
    pairwise_ids = [result.probe_id for result in run.pairwise]
    semantic_ids = [result.probe_id for result in run.semantic_text]
    if len(generation_ids) != 18 or set(generation_ids) != expected:
        raise ValueError("diagnostic run must contain one generation result per probe")
    if len(listwise_ids) != 18 or set(listwise_ids) != expected:
        raise ValueError("diagnostic run must contain one listwise result per probe")
    if len(pairwise_ids) != 108 or set(pairwise_ids) != expected:
        raise ValueError("diagnostic run must contain six pairwise results per probe")
    expected_presentations = {
        (variant_id, position)
        for variant_id in ("v1", "v2", "v3")
        for position in ("A", "B")
    }
    for probe_id in expected:
        presentations = [
            (result.variant_id, result.expected_position)
            for result in run.pairwise
            if result.probe_id == probe_id
        ]
        if len(presentations) != 6 or set(presentations) != expected_presentations:
            raise ValueError(
                f"diagnostic pairwise presentation matrix changed for {probe_id}"
            )
    if len(semantic_ids) != 6 or set(semantic_ids) != frozenset(YIELDED_FLOOR_PROBE_IDS):
        raise ValueError("diagnostic semantic grading must cover all six yielded responses")


def _protocol_rates(run: HarnessRun, probe_ids: Collection[str]) -> dict[str, object]:
    selected = frozenset(probe_ids)
    return {
        "generation": _rate(
            [result.generation_passed for result in run.generation if result.probe_id in selected]
        ),
        "pairwise": _rate(
            [result.correct for result in run.pairwise if result.probe_id in selected]
        ),
        "listwise": _rate(
            [
                result.top1_correct and result.expected_above_tempting
                for result in run.listwise
                if result.probe_id in selected
            ]
        ),
    }


def _rate(values: list[bool]) -> dict[str, float | int]:
    if not values:
        raise ValueError("diagnostic rate cannot have an empty denominator")
    passed = sum(values)
    return {"passed": passed, "total": len(values), "rate": passed / len(values)}


def _gate(observed: float, threshold: float, comparison: str) -> dict[str, object]:
    if comparison == ">=":
        passed = observed >= threshold
    elif comparison == "<":
        passed = observed < threshold
    elif comparison == "<=":
        passed = observed <= threshold
    else:  # pragma: no cover - closed local calls.
        raise ValueError(f"unsupported diagnostic comparison: {comparison}")
    return {
        "comparison": comparison,
        "observed": observed,
        "passed": passed,
        "threshold": threshold,
    }
