"""Pre-registered WP15 post-amendment diagnostic tests."""

from dataclasses import replace
from pathlib import Path

import pytest

from im.policy.prompted import (
    PromptArtifacts,
    PromptedPolicyConfig,
    PromptRenderer,
    ResponsesRequestBuilder,
)
from im.probes.harness.artifacts import load_approved_catalog
from im.probes.harness.backend import OracleHarnessBackend
from im.probes.harness.batch import BatchDecoder, plan_primary_work
from im.probes.harness.cache import HarnessCache
from im.probes.harness.cost import estimate_harness_cost
from im.probes.harness.diagnostic import (
    ACTIVE_FLOOR_PROBE_IDS,
    CONTROL_PROBE_IDS,
    DIAGNOSTIC_PROBE_IDS,
    YIELDED_FLOOR_PROBE_IDS,
    compute_diagnostic_metrics,
    diagnostic_spec_sha256,
    render_diagnostic_report,
    select_diagnostic_work,
)
from im.probes.harness.models import (
    GenerationResult,
    HarnessRun,
    ListwiseResult,
    PairwiseResult,
    ProviderUsage,
    SemanticTextResult,
)
from im.probes.harness.protocols import ProtocolPromptBuilder
from im.probes.harness.runner import ProbeHarnessRunner
from im.probes.model import NegativeClass


@pytest.mark.asyncio
async def test_diagnostic_plan_is_exact_signed_144_request_subset() -> None:
    repository = Path(__file__).resolve().parents[1]
    catalog = await load_approved_catalog(repository)
    artifacts = PromptArtifacts.from_repository(repository)
    config = PromptedPolicyConfig()
    builder = ResponsesRequestBuilder(PromptRenderer(artifacts), config)
    prompts = ProtocolPromptBuilder(artifacts, config)

    selected = select_diagnostic_work(plan_primary_work(catalog, builder, prompts))

    assert len(selected) == 144
    assert {item.identity.probe_id for item in selected} == set(DIAGNOSTIC_PROBE_IDS)
    assert sum(item.decoder is BatchDecoder.ACTION for item in selected) == 18
    assert sum(item.decoder is BatchDecoder.PAIRWISE for item in selected) == 108
    assert sum(item.decoder is BatchDecoder.LISTWISE for item in selected) == 18
    assert len({item.identity.digest for item in selected}) == 144

    estimate = estimate_harness_cost(
        catalog,
        builder,
        prompts,
        probe_ids=DIAGNOSTIC_PROBE_IDS,
    )
    assert estimate.generation_requests == 18
    assert estimate.pairwise_requests == 108
    assert estimate.listwise_requests == 18
    assert estimate.semantic_requests == 6
    assert estimate.total_requests == 150


@pytest.mark.asyncio
async def test_shared_runner_grades_only_the_diagnostic_selection(tmp_path: Path) -> None:
    repository = Path(__file__).resolve().parents[1]
    catalog = await load_approved_catalog(repository)
    artifacts = PromptArtifacts.from_repository(repository)
    config = PromptedPolicyConfig()
    builder = ResponsesRequestBuilder(PromptRenderer(artifacts), config)
    prompts = ProtocolPromptBuilder(artifacts, config)
    backend = OracleHarnessBackend(
        {
            variant.policy_stream_sha256: variant.expected_action
            for probe in catalog.manifest.probes
            for variant in probe.variants
        }
    )
    with HarnessCache(tmp_path / "diagnostic.sqlite") as cache:
        run = await ProbeHarnessRunner(
            catalog,
            generation_builder=builder,
            prompts=prompts,
            backend=backend,
            cache=cache,
        ).run(probe_ids=DIAGNOSTIC_PROBE_IDS)

    assert len(run.generation) == 18
    assert len(run.pairwise) == 108
    assert len(run.listwise) == 18
    assert len(run.semantic_text) == 6
    assert compute_diagnostic_metrics(run)["all_gates_passed"] is True


def test_perfect_diagnostic_passes_every_preregistered_gate() -> None:
    run = _perfect_run()

    metrics = compute_diagnostic_metrics(run)

    assert metrics["all_gates_passed"] is True
    assert metrics["active_floor"]["generation"] == {  # type: ignore[index]
        "passed": 6,
        "total": 6,
        "rate": 1.0,
    }
    assert metrics["yielded_floor"]["pairwise"] == {  # type: ignore[index]
        "passed": 36,
        "total": 36,
        "rate": 1.0,
    }
    assert metrics["controls"]["listwise"] == {  # type: ignore[index]
        "passed": 6,
        "total": 6,
        "rate": 1.0,
    }


def test_one_active_floor_generation_failure_fails_diagnostic() -> None:
    run = _perfect_run()
    first = run.generation[0]
    failed = replace(first, generation_passed=False, intrusive_action=True)

    metrics = compute_diagnostic_metrics(
        replace(run, generation=(failed, *run.generation[1:]))
    )

    assert metrics["all_gates_passed"] is False
    assert metrics["gates"]["active_floor_generation"]["passed"] is False  # type: ignore[index]


def test_diagnostic_rejects_duplicate_pairwise_presentations() -> None:
    run = _perfect_run()
    first = run.pairwise[0]
    duplicate = replace(run.pairwise[1], expected_position=first.expected_position)

    with pytest.raises(ValueError, match="presentation matrix changed"):
        compute_diagnostic_metrics(replace(run, pairwise=(first, duplicate, *run.pairwise[2:])))


def test_diagnostic_report_binds_spec_inputs_jobs_and_cost() -> None:
    metrics = compute_diagnostic_metrics(_perfect_run())

    assert diagnostic_spec_sha256() == (
        "sha256:c1a960f570b63a62d6bb4fcaf1e40581ae2fcc9f2deeb97f60e580a3349b288d"
    )

    report = render_diagnostic_report(
        metrics=metrics,
        cost_estimate={"usd": {"batch_no_cache": "2.817811"}},
        actual_cost_usd="2.500000",
        repository_commit="abc123",
        manifest_sha256="sha256:" + "2" * 64,
        review_sha256="sha256:" + "3" * 64,
        model="gpt-5.6-terra",
        reasoning_effort="high",
        jobs=[
            {
                "stage": "p0",
                "shard_index": 0,
                "batch_id": "batch_test",
                "request_count": 60,
                "input_sha256": "sha256:" + "4" * 64,
                "output_sha256": "sha256:" + "5" * 64,
                "error_sha256": None,
                "status": "completed",
            }
        ],
        total_usage={"input_tokens": 100, "output_tokens": 5},
        submitted_usage={"input_tokens": 100, "output_tokens": 5},
    )

    assert "**Verdict: PASS.**" in report
    assert diagnostic_spec_sha256() in report
    assert "`batch_test`" in report
    assert "$2.500000" in report
    assert '"input_tokens": 100' in report


def _perfect_run() -> HarnessRun:
    usage = ProviderUsage()
    generation: list[GenerationResult] = []
    pairwise: list[PairwiseResult] = []
    listwise: list[ListwiseResult] = []
    active = frozenset(ACTIVE_FLOOR_PROBE_IDS)
    yielded = frozenset(YIELDED_FLOOR_PROBE_IDS)
    controls = frozenset(CONTROL_PROBE_IDS)
    assert active | yielded | controls == frozenset(DIAGNOSTIC_PROBE_IDS)
    for probe_id in DIAGNOSTIC_PROBE_IDS:
        family_id = int(probe_id[1:3])
        expected_type = "idle" if probe_id in active else "respond"
        generation.append(
            GenerationResult(
                probe_id=probe_id,
                family_id=family_id,
                variant_id="v1",
                expected_type=expected_type,
                actual_action={"type": expected_type},
                provider_outcome="completed",
                schema_valid=True,
                reference_valid=True,
                license_allowed=True,
                license_block_code=None,
                structural_match=True,
                semantic_rule=None,
                semantic_passed=None,
                semantic_rationale=None,
                generation_passed=True,
                invented_arguments=False,
                intrusive_action=False,
                from_cache=False,
                usage=usage,
                fresh_usage=usage,
            )
        )
        for variant_id in ("v1", "v2", "v3"):
            for position in ("A", "B"):
                pairwise.append(
                    PairwiseResult(
                        probe_id=probe_id,
                        family_id=family_id,
                        variant_id=variant_id,
                        expected_position=position,  # type: ignore[arg-type]
                        negative_class=NegativeClass.SEMANTIC_PREFERENCE,
                        restraint_pair=probe_id in active,
                        provider_outcome="completed",
                        response_valid=True,
                        choice=position,  # type: ignore[arg-type]
                        correct=True,
                        from_cache=False,
                        usage=usage,
                        fresh_usage=usage,
                    )
                )
        listwise.append(
            ListwiseResult(
                probe_id=probe_id,
                family_id=family_id,
                variant_id="v1",
                candidate_count=2,
                candidate_action_types=("idle", "respond"),
                provider_outcome="completed",
                response_valid=True,
                ranking=("c01", "c02"),
                expected_candidate_id="c01",
                tempting_candidate_id="c02",
                top1_correct=True,
                expected_above_tempting=True,
                from_cache=False,
                usage=usage,
                fresh_usage=usage,
            )
        )
    return HarnessRun(
        manifest_sha256="sha256:" + "0" * 64,
        review_sha256="sha256:" + "1" * 64,
        model="gpt-5.6-terra",
        reasoning_effort="high",
        generation=tuple(generation),
        semantic_text=tuple(
            SemanticTextResult(
                probe_id=probe_id,
                family_id=10,
                variant_id="v1",
                rule="response_warrant_and_answer_quality",
                executed=True,
                provider_outcome="completed",
                response_valid=True,
                passed=True,
                rationale="The response satisfies the rubric.",
                from_cache=False,
                usage=usage,
                fresh_usage=usage,
            )
            for probe_id in YIELDED_FLOOR_PROBE_IDS
        ),
        pairwise=tuple(pairwise),
        listwise=tuple(listwise),
    )
