"""Generate-versus-recognize metrics and WP15 promotion gates."""

from __future__ import annotations

from collections import defaultdict
from typing import TypeVar

from im.probes.harness.models import HarnessRun
from im.probes.model import NegativeClass

T = TypeVar("T")


def _rate(values: list[bool]) -> dict[str, float | int | None]:
    passed = sum(values)
    total = len(values)
    return {
        "passed": passed,
        "total": total,
        "rate": None if total == 0 else passed / total,
    }


def compute_metrics(run: HarnessRun) -> dict[str, object]:
    """Return exact denominators, family slices, diagnostics, and gate verdicts."""
    generation = run.generation
    pairwise = run.pairwise
    listwise = run.listwise
    schema = _rate([result.schema_valid for result in generation])
    reference = _rate([result.reference_valid for result in generation])
    licensed = _rate([result.license_allowed for result in generation])
    structural = _rate([result.structural_match for result in generation])
    semantic = _rate([result.passed for result in run.semantic_text])
    generation_passed = _rate([result.generation_passed for result in generation])
    intrusive = _rate(
        [result.intrusive_action for result in generation if result.expected_type == "idle"]
    )
    invented = _rate([result.invented_arguments for result in generation])
    pairwise_accuracy = _rate([result.correct for result in pairwise])
    restraint = _rate([result.correct for result in pairwise if result.restraint_pair])
    semantic_recognition = _rate(
        [
            result.correct
            for result in pairwise
            if result.negative_class is NegativeClass.SEMANTIC_PREFERENCE
        ]
    )
    mechanical_recognition = _rate(
        [
            result.correct
            for result in pairwise
            if result.negative_class is NegativeClass.MECHANICAL_NEGATIVE
        ]
    )
    rollover_invariance = _rate(
        [result.correct for result in pairwise if result.family_id == 11]
    )
    expected_a = _rate(
        [result.correct for result in pairwise if result.expected_position == "A"]
    )
    expected_b = _rate(
        [result.correct for result in pairwise if result.expected_position == "B"]
    )
    position_bias = abs(float(expected_a["rate"] or 0) - float(expected_b["rate"] or 0))
    mechanical_positive = _rate(
        [
            result.structural_match
            for result in generation
            if result.expected_type in {"mark", "schedule", "cancel"}
        ]
    )
    listwise_top1 = _rate([result.top1_correct for result in listwise])
    listwise_order = _rate([result.expected_above_tempting for result in listwise])

    by_family: dict[str, object] = {}
    family_spreads: dict[int, float] = {}
    for family_id in range(1, 13):
        family_generation = [result for result in generation if result.family_id == family_id]
        family_pairwise = [result for result in pairwise if result.family_id == family_id]
        family_listwise = [result for result in listwise if result.family_id == family_id]
        variant_rates = {
            variant_id: _rate(
                [result.correct for result in family_pairwise if result.variant_id == variant_id]
            )
            for variant_id in ("v1", "v2", "v3")
        }
        probe_spreads: dict[str, float] = {}
        for probe_id in sorted({result.probe_id for result in family_pairwise}):
            per_variant = [
                _rate(
                    [
                        result.correct
                        for result in family_pairwise
                        if result.probe_id == probe_id and result.variant_id == variant_id
                    ]
                )
                for variant_id in ("v1", "v2", "v3")
            ]
            rates = [float(rate["rate"] or 0) for rate in per_variant]
            probe_spreads[probe_id] = max(rates) - min(rates)
        spread = max(probe_spreads.values())
        family_spreads[family_id] = spread
        by_family[str(family_id)] = {
            "generation_schema": _rate(
                [result.schema_valid for result in family_generation]
            ),
            "generation_structural": _rate(
                [result.structural_match for result in family_generation]
            ),
            "generation_pass": _rate(
                [result.generation_passed for result in family_generation]
            ),
            "pairwise_accuracy": _rate(
                [result.correct for result in family_pairwise]
            ),
            "pairwise_variant_accuracy": variant_rates,
            "per_probe_paraphrase_spread": probe_spreads,
            "paraphrase_spread": spread,
            "listwise_top1": _rate(
                [result.top1_correct for result in family_listwise]
            ),
            "listwise_expected_above_tempting": _rate(
                [result.expected_above_tempting for result in family_listwise]
            ),
        }

    max_spread = max(family_spreads.values())
    gates = {
        "unconstrained_schema_validity": _gate(
            observed=float(schema["rate"] or 0), threshold=0.98, comparison=">="
        ),
        "restraint_pair_recognition": _gate(
            observed=float(restraint["rate"] or 0), threshold=0.95, comparison=">="
        ),
        "position_bias": _gate(
            observed=position_bias, threshold=0.05, comparison="<"
        ),
        "paraphrase_collapse": _gate(
            observed=max_spread, threshold=0.10, comparison="<="
        ),
        "mechanical_positive_exactness": _gate(
            observed=float(mechanical_positive["rate"] or 0),
            threshold=0.90,
            comparison=">=",
        ),
    }
    action_type_coverage: dict[str, int] = defaultdict(int)
    for result in listwise:
        for action_type in set(result.candidate_action_types):
            action_type_coverage[action_type] += 1
    return {
        "generation": {
            "schema_validity": schema,
            "reference_validity": reference,
            "raw_license_allowance": licensed,
            "structural_match": structural,
            "semantic_text": semantic,
            "overall": generation_passed,
            "invented_argument_rate": invented,
            "intrusive_action_rate_on_idle_expected": intrusive,
            "mechanical_positive_exactness": mechanical_positive,
        },
        "pairwise": {
            "accuracy": pairwise_accuracy,
            "restraint_recognition": restraint,
            "semantic_preference_recognition": semantic_recognition,
            "mechanical_constraint_recognition": mechanical_recognition,
            "rollover_invariance": rollover_invariance,
            "expected_a_accuracy": expected_a,
            "expected_b_accuracy": expected_b,
            "position_bias": position_bias,
            "max_family_paraphrase_spread": max_spread,
        },
        "listwise": {
            "top1": listwise_top1,
            "expected_above_tempting": listwise_order,
            "candidate_count_min": min(result.candidate_count for result in listwise),
            "candidate_count_max": max(result.candidate_count for result in listwise),
            "action_type_state_coverage": dict(sorted(action_type_coverage.items())),
        },
        "families": by_family,
        "gates": gates,
        "all_gates_passed": all(bool(gate["passed"]) for gate in gates.values()),
    }


def _gate(*, observed: float, threshold: float, comparison: str) -> dict[str, object]:
    if comparison == ">=":
        passed = observed >= threshold
    elif comparison == "<":
        passed = observed < threshold
    elif comparison == "<=":
        passed = observed <= threshold
    else:  # pragma: no cover - closed local calls.
        raise ValueError(f"unsupported gate comparison: {comparison}")
    return {
        "comparison": comparison,
        "observed": observed,
        "passed": passed,
        "threshold": threshold,
    }
