"""Full-corpus mocked WP15 execution and listwise construction tests."""

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
from im.probes.harness.cache import HarnessCache
from im.probes.harness.candidates import build_listwise_presentation
from im.probes.harness.cost import estimate_harness_cost
from im.probes.harness.metrics import compute_metrics
from im.probes.harness.protocols import ProtocolPromptBuilder
from im.probes.harness.report import render_report
from im.probes.harness.runner import HarnessRunnerConfig, ProbeHarnessRunner
from im.probes.validate import assert_reference_integrity


@pytest.fixture(scope="module")
def repository() -> Path:
    return Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
async def approved(repository: Path):
    return await load_approved_catalog(repository)


def _builders(repository: Path):
    artifacts = PromptArtifacts.from_repository(repository)
    config = PromptedPolicyConfig()
    return (
        ResponsesRequestBuilder(PromptRenderer(artifacts), config),
        ProtocolPromptBuilder(artifacts, config),
    )


def _oracle(approved) -> OracleHarnessBackend:
    return OracleHarnessBackend(
        {
            variant.policy_stream_sha256: variant.expected_action
            for probe in approved.manifest.probes
            for variant in probe.variants
        }
    )


def test_listwise_candidates_preserve_approved_contrast_and_reference_integrity(
    approved,
) -> None:
    for probe in approved.manifest.probes:
        variant = probe.variants[0]
        view = approved.views[(probe.probe_id, "v1")]
        presentation = build_listwise_presentation(probe, variant, view)
        actions = {
            candidate.candidate_id: candidate.action
            for candidate in presentation.candidates
        }

        assert actions[presentation.expected_candidate_id] == variant.expected_action
        assert actions[presentation.tempting_candidate_id] == variant.tempting_alternative
        assert 2 <= len(actions) <= 10
        for action in actions.values():
            assert_reference_integrity(action, view)


@pytest.mark.asyncio
async def test_full_mocked_harness_runs_all_protocols_and_resumes(
    tmp_path: Path,
    repository: Path,
    approved,
) -> None:
    generation_builder, prompts = _builders(repository)
    cache_path = tmp_path / "wp15-cache.sqlite"
    with HarnessCache(cache_path) as cache:
        first_runner = ProbeHarnessRunner(
            approved,
            generation_builder=generation_builder,
            prompts=prompts,
            backend=_oracle(approved),
            cache=cache,
            config=HarnessRunnerConfig(concurrency=16),
        )
        first = await first_runner.run()
        second_runner = ProbeHarnessRunner(
            approved,
            generation_builder=generation_builder,
            prompts=prompts,
            backend=_oracle(approved),
            cache=cache,
            config=HarnessRunnerConfig(concurrency=16),
        )
        second = await second_runner.run()

    assert len(first.generation) == 144
    assert len(first.pairwise) == 864
    assert len(first.listwise) == 144
    assert all(result.generation_passed for result in first.generation)
    assert all(result.correct for result in first.pairwise)
    assert all(result.top1_correct for result in first.listwise)
    assert all(result.expected_above_tempting for result in first.listwise)
    assert not any(result.from_cache for result in first.generation)
    assert not any(result.from_cache for result in first.pairwise)
    assert not any(result.from_cache for result in first.listwise)
    assert all(result.from_cache for result in second.generation)
    assert all(result.from_cache for result in second.pairwise)
    assert all(result.from_cache for result in second.listwise)
    assert second.fresh_usage.input_tokens == 0
    assert second.fresh_usage.output_tokens == 0

    metrics = compute_metrics(first)
    estimate = estimate_harness_cost(approved, generation_builder, prompts)
    report = render_report(
        first,
        metrics,
        estimate,
        run_kind="mocked-oracle",
        repository_commit="test",
    )
    assert metrics["all_gates_passed"]
    assert estimate.generation_requests == 144
    assert estimate.pairwise_requests == 864
    assert estimate.listwise_requests == 144
    assert estimate.semantic_requests == 22
    assert estimate.total_requests == 1_174
    assert "PASS. This verdict applies only" in report
    assert "Protocol calls represented: 1152" in report


def test_generation_and_pairwise_population_is_frozen(approved) -> None:
    expected_types = [
        probe.variants[0].expected_action.type for probe in approved.manifest.probes
    ]

    assert expected_types.count("idle") == 58
    assert expected_types.count("mark") == 12
    assert expected_types.count("nudge") == 20
    assert expected_types.count("integrate") == 14
    assert expected_types.count("skip") == 14
    assert expected_types.count("respond") == 8
    assert expected_types.count("cancel") == 6
    assert expected_types.count("delegate") == 6
    assert expected_types.count("schedule") == 6
    assert sum(
        1
        for probe in approved.manifest.probes
        for variant in probe.variants
        for _position in ("A", "B")
    ) == 864
