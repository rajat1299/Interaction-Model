"""Full-corpus mocked WP15 execution and listwise construction tests."""

import asyncio
import sqlite3
from dataclasses import replace
from pathlib import Path

import pytest

from im.policy.base import PolicyCallCancelled, PolicyCallError, PolicyCallTrace
from im.policy.prompted import (
    PromptArtifacts,
    PromptedPolicyConfig,
    PromptRenderer,
    ResponsesRequestBuilder,
)
from im.probes.harness.artifacts import load_approved_catalog
from im.probes.harness.backend import OracleHarnessBackend
from im.probes.harness.cache import HarnessCache, IndeterminateCacheEntry
from im.probes.harness.candidates import build_listwise_presentation
from im.probes.harness.cost import estimate_harness_cost
from im.probes.harness.metrics import compute_metrics
from im.probes.harness.models import (
    CacheIdentity,
    HarnessCompletion,
    HarnessProtocol,
)
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


class _InvalidSemanticOracle(OracleHarnessBackend):
    async def complete(self, request, validator):
        if b"open-text-rubric-v1" in request.request_bytes:
            return HarnessCompletion(
                value={"provider_invalid": True},
                outcome="invalid",
            )
        return await super().complete(request, validator)


class _FailingPhaseBackend:
    """Start one bounded wave, fail one call, and audit cancellation of its siblings."""

    def __init__(self, *, model: str, prompt_hash: str, wave_size: int) -> None:
        self.model = model
        self.prompt_hash = prompt_hash
        self.wave_size = wave_size
        self.started = 0
        self.active = 0
        self._never = asyncio.Event()

    def _trace(self, *, index: int, outcome: str) -> PolicyCallTrace:
        return PolicyCallTrace(
            attempt_index=1,
            model=self.model,
            prompt_hash=self.prompt_hash,
            request=f"request-{index}".encode(),
            response=b"",
            latency_ms=1,
            http_status=None,
            outcome=outcome,
        )

    async def generate(self, _policy_bytes: bytes) -> HarnessCompletion:
        self.started += 1
        index = self.started
        self.active += 1
        try:
            if index == 1:
                while self.started < self.wave_size:
                    await asyncio.sleep(0)
                raise PolicyCallError(
                    "controlled provider failure",
                    (self._trace(index=index, outcome="transport_error"),),
                )
            try:
                await self._never.wait()
            except asyncio.CancelledError as error:
                raise PolicyCallCancelled(
                    (self._trace(index=index, outcome="cancelled"),)
                ) from error
            raise AssertionError("unreachable")
        finally:
            self.active -= 1

    async def complete(self, _request, _validator):
        raise AssertionError("recognition phase must not begin after generation failure")

    async def aclose(self) -> None:
        return None


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
    assert len(first.semantic_text) == 22
    assert len(first.pairwise) == 864
    assert len(first.listwise) == 144
    assert all(result.generation_passed for result in first.generation)
    assert all(result.executed and result.passed for result in first.semantic_text)
    assert all(result.correct for result in first.pairwise)
    assert all(result.top1_correct for result in first.listwise)
    assert all(result.expected_above_tempting for result in first.listwise)
    assert not any(result.from_cache for result in first.generation)
    assert not any(result.from_cache for result in first.pairwise)
    assert not any(result.from_cache for result in first.listwise)
    assert all(result.from_cache for result in second.generation)
    assert all(result.from_cache for result in second.semantic_text)
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
    assert "Base protocol calls represented: 1152" in report
    assert "Open-text rubric records: 22 (22 provider calls executed)" in report
    assert "self-grading, not independent human adjudication" in report

    one_probe_pairs = tuple(
        replace(result, correct=False)
        if (result.probe_id, result.variant_id) == ("f01-t01-a", "v1")
        else result
        for result in first.pairwise
    )
    sensitivity_metrics = compute_metrics(replace(first, pairwise=one_probe_pairs))
    assert sensitivity_metrics["pairwise"]["max_family_paraphrase_spread"] == pytest.approx(
        1 / 12
    )
    assert sensitivity_metrics["pairwise"]["max_probe_paraphrase_sensitivity"] == 1.0
    assert sensitivity_metrics["gates"]["paraphrase_collapse"]["passed"]

    two_probe_pairs = tuple(
        replace(result, correct=False)
        if (result.probe_id, result.variant_id)
        in {("f01-t01-a", "v1"), ("f01-t02-a", "v1")}
        else result
        for result in first.pairwise
    )
    collapse_metrics = compute_metrics(replace(first, pairwise=two_probe_pairs))
    assert collapse_metrics["pairwise"]["max_family_paraphrase_spread"] == pytest.approx(
        1 / 6
    )
    assert not collapse_metrics["gates"]["paraphrase_collapse"]["passed"]

    skipped_semantic = replace(
        first.semantic_text[0],
        executed=False,
        provider_outcome="not_run_structural_mismatch",
        response_valid=False,
        passed=False,
    )
    semantic_metrics = compute_metrics(
        replace(first, semantic_text=(skipped_semantic, *first.semantic_text[1:]))
    )
    assert semantic_metrics["generation"]["semantic_text"] == {
        "passed": 21,
        "total": 21,
        "rate": 1.0,
    }
    assert semantic_metrics["generation"]["semantic_text_not_run"] == 1


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


@pytest.mark.asyncio
async def test_terminal_invalid_rubric_is_recorded_and_resumable(
    tmp_path: Path,
    repository: Path,
    approved,
) -> None:
    generation_builder, prompts = _builders(repository)
    expected = {
        variant.policy_stream_sha256: variant.expected_action
        for probe in approved.manifest.probes
        for variant in probe.variants
    }
    probe = next(probe for probe in approved.manifest.probes if probe.probe_id == "f03-t01-a")
    with HarnessCache(tmp_path / "invalid-rubric.sqlite") as cache:
        runner = ProbeHarnessRunner(
            approved,
            generation_builder=generation_builder,
            prompts=prompts,
            backend=_InvalidSemanticOracle(expected),
            cache=cache,
        )
        first_generation, first_semantic = await runner._run_generation(probe)
        second_generation, second_semantic = await runner._run_generation(probe)

    assert not first_generation.generation_passed
    assert first_semantic is not None
    assert first_semantic.executed
    assert not first_semantic.response_valid
    assert first_semantic.provider_outcome == "invalid"
    assert second_semantic is not None and second_semantic.from_cache
    assert not second_generation.generation_passed


@pytest.mark.asyncio
async def test_interrupted_call_trace_is_persisted_before_propagation(
    tmp_path: Path,
    repository: Path,
    approved,
) -> None:
    generation_builder, prompts = _builders(repository)
    identity = CacheIdentity(
        manifest_sha256=approved.manifest_sha256,
        probe_id="f01-t01-a",
        protocol=HarnessProtocol.GENERATION,
        variant_id="v1",
        presentation="interrupted-test",
        model=generation_builder.config.model,
        reasoning_effort=generation_builder.config.reasoning_effort,
        prompt_hash=generation_builder.renderer.artifacts.prompt_hash,
        request_hash="sha256:" + "9" * 64,
    )
    trace = PolicyCallTrace(
        attempt_index=1,
        model=generation_builder.config.model,
        prompt_hash=identity.prompt_hash,
        request=b"request",
        response=b"",
        latency_ms=1,
        http_status=None,
        outcome="cancelled",
    )

    async def interrupted() -> HarnessCompletion:
        raise PolicyCallCancelled((trace,))

    with HarnessCache(tmp_path / "interrupted.sqlite") as cache:
        runner = ProbeHarnessRunner(
            approved,
            generation_builder=generation_builder,
            prompts=prompts,
            backend=_oracle(approved),
            cache=cache,
        )
        with pytest.raises(PolicyCallCancelled):
            await runner._cached(identity, interrupted)
        with pytest.raises(IndeterminateCacheEntry):
            cache.get(identity)


@pytest.mark.asyncio
async def test_phase_failure_cancels_and_drains_started_siblings_before_cache_closes(
    tmp_path: Path,
    repository: Path,
    approved,
) -> None:
    generation_builder, prompts = _builders(repository)
    backend = _FailingPhaseBackend(
        model=generation_builder.config.model,
        prompt_hash=generation_builder.renderer.artifacts.prompt_hash,
        wave_size=4,
    )
    cache_path = tmp_path / "phase-failure.sqlite"
    with HarnessCache(cache_path) as cache:
        runner = ProbeHarnessRunner(
            approved,
            generation_builder=generation_builder,
            prompts=prompts,
            backend=backend,
            cache=cache,
            config=HarnessRunnerConfig(concurrency=4),
        )
        with pytest.raises(PolicyCallError, match="controlled provider failure"):
            await runner.run()
        assert backend.active == 0

    with sqlite3.connect(cache_path) as connection:
        outcomes = [
            row[0]
            for row in connection.execute(
                "SELECT outcome FROM attempt_history ORDER BY attempt_id"
            ).fetchall()
        ]
    assert backend.started >= 4
    assert outcomes.count("transport_error") == 1
    assert outcomes.count("cancelled") == backend.started - 1
    assert len(outcomes) == backend.started
