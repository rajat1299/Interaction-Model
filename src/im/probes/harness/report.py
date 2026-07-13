"""Deterministic Markdown report for WP15 teacher bakeoff results."""

from __future__ import annotations

import json
from decimal import Decimal

from im.policy.prompted import ModelPricing
from im.probes.harness.cost import HarnessCostEstimate, usage_cost
from im.probes.harness.models import HarnessRun, ProviderUsage


def render_report(
    run: HarnessRun,
    metrics: dict[str, object],
    estimate: HarnessCostEstimate,
    *,
    run_kind: str,
    repository_commit: str,
    billing_multiplier: Decimal = Decimal(1),
    fresh_usage_override: ProviderUsage | None = None,
    execution_details: tuple[str, ...] = (),
) -> str:
    pricing = ModelPricing(model=run.model)
    fresh_usage = run.fresh_usage if fresh_usage_override is None else fresh_usage_override
    corpus_cost = usage_cost(
        run.usage,
        pricing,
        billing_multiplier=billing_multiplier,
    )
    fresh_cost = usage_cost(
        fresh_usage,
        pricing,
        billing_multiplier=billing_multiplier,
    )
    lines = [
        f"# WP15 teacher probe — {run.model} / {run.reasoning_effort}",
        "",
        "## Verdict",
        "",
        ("PASS" if metrics["all_gates_passed"] else "FAIL")
        + ". This verdict applies only to the frozen WP15 promotion gates.",
        "",
        "## Run identity",
        "",
        f"- Run kind: `{run_kind}`",
        f"- Repository commit: `{repository_commit}`",
        f"- Manifest: `{run.manifest_sha256}`",
        f"- Human review: `{run.review_sha256}`",
        f"- Model: `{run.model}`",
        f"- Reasoning effort: `{run.reasoning_effort}`",
        *(
            [f"- Billing multiplier: `{billing_multiplier}`"]
            if billing_multiplier != Decimal(1)
            else []
        ),
        "- Base protocol calls represented: "
        f"{len(run.generation) + len(run.pairwise) + len(run.listwise)}",
        f"- Open-text rubric records: {len(run.semantic_text)} "
        f"({sum(result.executed for result in run.semantic_text)} provider calls executed)",
        "- Semantic authority: same model and reasoning configuration as generation; this is "
        "self-grading, not independent human adjudication.",
        *execution_details,
        "",
        "## Promotion gates",
        "",
        "| Gate | Observed | Requirement | Verdict |",
        "| --- | ---: | ---: | --- |",
    ]
    gates = metrics["gates"]
    for name, gate in gates.items():
        lines.append(
            f"| {name.replace('_', ' ')} | {_percent(gate['observed'])} | "
            f"`{gate['comparison']} {_percent(gate['threshold'])}` | "
            f"{'PASS' if gate['passed'] else 'FAIL'} |"
        )
    lines.extend(
        [
            "",
            "## Generate versus recognize",
            "",
            "| Family | Generation schema | Generation structural | Generation overall | "
            "Pairwise | Paraphrase spread | Listwise top-1 | Expected > tempting |",
            "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for family_id, family in metrics["families"].items():
        lines.append(
            f"| {family_id} | {_rate(family['generation_schema'])} | "
            f"{_rate(family['generation_structural'])} | "
            f"{_rate(family['generation_pass'])} | {_rate(family['pairwise_accuracy'])} | "
            f"{_percent(family['paraphrase_spread'])} | {_rate(family['listwise_top1'])} | "
            f"{_rate(family['listwise_expected_above_tempting'])} |"
        )
    generation = metrics["generation"]
    pairwise = metrics["pairwise"]
    listwise = metrics["listwise"]
    lines.extend(
        [
            "",
            "## Global diagnostics",
            "",
            f"- Generation schema validity: {_rate(generation['schema_validity'])}",
            f"- Generation reference validity: {_rate(generation['reference_validity'])}",
            f"- Raw license allowance: {_rate(generation['raw_license_allowance'])}",
            f"- Structural match: {_rate(generation['structural_match'])}",
            f"- Open-text semantic grade: {_rate(generation['semantic_text'])}",
            "- Open-text rubric outcomes: "
            + ", ".join(
                f"{outcome}={sum(item.provider_outcome == outcome for item in run.semantic_text)}"
                for outcome in sorted({item.provider_outcome for item in run.semantic_text})
            ),
            f"- Overall generation: {_rate(generation['overall'])}",
            f"- Intrusive action rate on idle-expected probes: "
            f"{_rate(generation['intrusive_action_rate_on_idle_expected'])}",
            f"- Invented/non-exact non-text arguments: "
            f"{_rate(generation['invented_argument_rate'])}",
            f"- Pairwise overall: {_rate(pairwise['accuracy'])}",
            f"- Semantic preference recognition: "
            f"{_rate(pairwise['semantic_preference_recognition'])}",
            f"- Mechanical constraint recognition: "
            f"{_rate(pairwise['mechanical_constraint_recognition'])}",
            f"- Rollover invariance recognition: {_rate(pairwise['rollover_invariance'])}",
            f"- Position bias: {_percent(pairwise['position_bias'])}",
            f"- Listwise top-1: {_rate(listwise['top1'])}",
            f"- Listwise expected above tempting: "
            f"{_rate(listwise['expected_above_tempting'])}",
            f"- Listwise candidate range: {listwise['candidate_count_min']}–"
            f"{listwise['candidate_count_max']}",
            "",
            "## Cost and usage",
            "",
            f"- Offline warm-cache estimate: ${_money(estimate.synchronous_warm_cache_usd)}",
            f"- Offline no-cache estimate: ${_money(estimate.synchronous_no_cache_usd)}",
            *(
                [f"- Offline Batch no-cache estimate: ${_money(estimate.batch_no_cache_usd)}"]
                if billing_multiplier != Decimal(1)
                else []
            ),
            f"- Offline all-calls-retry warm estimate: "
            f"${_money(estimate.all_calls_one_retry_warm_cache_usd)}",
            "- Provider usage represented by this report: "
            f"`{json.dumps(run.usage.as_json(), sort_keys=True)}`",
            f"- Estimated charge represented by cached corpus results: ${_money(corpus_cost)}",
            "- Fresh usage in this invocation: "
            f"`{json.dumps(fresh_usage.as_json(), sort_keys=True)}`",
            f"- Estimated incremental charge for this invocation: ${_money(fresh_cost)}",
            "- Provider billing remains authoritative.",
            "",
            "## Raw generation failures",
            "",
        ]
    )
    failures = [result for result in run.generation if not result.generation_passed]
    if not failures:
        lines.append("None.")
    else:
        lines.extend(
            [
                "| Probe | Expected | Actual | Schema/ref/license | Structural | Semantic |",
                "| --- | --- | --- | --- | --- | --- |",
            ]
        )
        for result in failures:
            actual = (
                "provider-invalid"
                if result.actual_action is None
                else str(result.actual_action.get("type", "unknown"))
            )
            lines.append(
                f"| `{result.probe_id}` | `{result.expected_type}` | `{actual}` | "
                f"{result.schema_valid}/{result.reference_valid}/{result.license_allowed}"
                f"{('/' + result.license_block_code) if result.license_block_code else ''} | "
                f"{result.structural_match} | "
                f"{result.semantic_passed if result.semantic_rule else 'n/a'} |"
            )
    pairwise_failures = [result for result in run.pairwise if not result.correct]
    listwise_failures = [result for result in run.listwise if not result.top1_correct]
    lines.extend(
        [
            "",
            "## Recognition failure indices",
            "",
            "- Pairwise: "
            + (
                "none"
                if not pairwise_failures
                else ", ".join(
                    f"{item.probe_id}/{item.variant_id}/{item.expected_position}"
                    for item in pairwise_failures
                )
            ),
            "- Listwise top-1: "
            + (
                "none"
                if not listwise_failures
                else ", ".join(item.probe_id for item in listwise_failures)
            ),
            "",
            "## Interpretation",
            "",
            "This generated report records measurements and exact failure indices. Product-level "
            "interpretation must be added only after inspecting the retained raw outputs; a "
            "passing "
            "aggregate does not waive that review.",
        ]
    )
    return "\n".join(lines) + "\n"


def _rate(value: dict[str, object]) -> str:
    rate = value["rate"]
    if rate is None:
        return f"n/a ({value['passed']}/{value['total']})"
    return f"{_percent(rate)} ({value['passed']}/{value['total']})"


def _percent(value: object) -> str:
    return f"{float(value) * 100:.2f}%"


def _money(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.000001")), "f")
