"""Bounded, resumable execution of the three WP15 probe protocols."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from pydantic import ValidationError

from im.license import Allowed, Blocked, check
from im.policy.base import PolicyCallCancelled, PolicyCallError
from im.policy.prompted import ResponsesRequestBuilder
from im.probes.grading import (
    SemanticTextAssessment,
    grade_generation_structure,
)
from im.probes.harness.artifacts import ApprovedProbeCatalog
from im.probes.harness.backend import HarnessBackend
from im.probes.harness.cache import HarnessCache
from im.probes.harness.models import (
    CacheIdentity,
    GenerationResult,
    HarnessCompletion,
    HarnessRun,
    ListwiseRanking,
    ListwiseResult,
    PairwiseChoice,
    PairwiseResult,
    ProviderUsage,
    SemanticTextResult,
    SemanticTextVerdict,
)
from im.probes.harness.planning import (
    plan_generation,
    plan_listwise,
    plan_pairwise,
    plan_semantic,
)
from im.probes.harness.protocols import ProtocolPromptBuilder
from im.probes.model import ExpectedPosition, NegativeClass
from im.probes.validate import ProbeValidationError, assert_reference_integrity
from im.schema.actions import ACTION_ADAPTER, Action, IdleAction


@dataclass(frozen=True, slots=True)
class HarnessRunnerConfig:
    concurrency: int = 8

    def __post_init__(self) -> None:
        if isinstance(self.concurrency, bool) or not isinstance(self.concurrency, int):
            raise TypeError("harness concurrency must be an integer")
        if self.concurrency <= 0:
            raise ValueError("harness concurrency must be positive")


class ProbeHarnessRunner:
    """Execute generation, pairwise, listwise, and required open-text grading."""

    def __init__(
        self,
        catalog: ApprovedProbeCatalog,
        *,
        generation_builder: ResponsesRequestBuilder,
        prompts: ProtocolPromptBuilder,
        backend: HarnessBackend,
        cache: HarnessCache,
        config: HarnessRunnerConfig | None = None,
    ) -> None:
        self.catalog = catalog
        self.generation_builder = generation_builder
        self.prompts = prompts
        self.backend = backend
        self.cache = cache
        self.config = config or HarnessRunnerConfig()
        self._semaphore = asyncio.Semaphore(self.config.concurrency)

    async def run(self) -> HarnessRun:
        generated = await _gather_phase(
            *(self._run_generation(probe) for probe in self.catalog.manifest.probes)
        )
        generation = tuple(item[0] for item in generated)
        semantic_text = tuple(item[1] for item in generated if item[1] is not None)
        pairwise = await _gather_phase(
            *(
                self._run_pairwise(probe, variant.variant_id, position)
                for probe in self.catalog.manifest.probes
                for variant in probe.variants
                for position in (ExpectedPosition.A, ExpectedPosition.B)
            )
        )
        listwise = await _gather_phase(
            *(self._run_listwise(probe) for probe in self.catalog.manifest.probes)
        )
        return HarnessRun(
            manifest_sha256=self.catalog.manifest_sha256,
            review_sha256=self.catalog.review_sha256,
            model=self.generation_builder.config.model,
            reasoning_effort=self.generation_builder.config.reasoning_effort,
            generation=generation,
            semantic_text=semantic_text,
            pairwise=tuple(pairwise),
            listwise=tuple(listwise),
        )

    async def _run_generation(
        self,
        probe,
    ) -> tuple[GenerationResult, SemanticTextResult | None]:
        variant = probe.variants[0]
        view = self.catalog.views[(probe.probe_id, "v1")]
        planned = plan_generation(self.catalog, self.generation_builder, probe)
        completion = await self._cached(
            planned.identity,
            lambda: self.backend.generate(planned.policy_bytes),
        )
        actual: Action | None = None
        schema_valid = reference_valid = license_allowed = structural_match = False
        block_code: str | None = None
        semantic_rule: str | None = None
        semantic_passed: bool | None = None
        semantic_rationale: str | None = None
        semantic_result: SemanticTextResult | None = None
        expected_structure = grade_generation_structure(
            variant.expected_action,
            variant.expected_action,
        )
        expected_rule = expected_structure.text_rule
        if expected_rule is not None:
            semantic_rule = expected_rule.value
        try:
            actual = ACTION_ADAPTER.validate_python(completion.value)
        except (ValidationError, ValueError):
            pass
        else:
            schema_valid = True
            try:
                assert_reference_integrity(actual, view)
            except ProbeValidationError:
                pass
            else:
                reference_valid = True
                license_result = check(actual, view)
                license_allowed = isinstance(license_result, Allowed)
                if isinstance(license_result, Blocked):
                    block_code = license_result.code.value
                structure = grade_generation_structure(variant.expected_action, actual)
                structural_match = structure.structural_match
                if structural_match and expected_rule is not None:
                    semantic_result = await self._grade_semantic(
                        probe_id=probe.probe_id,
                        family_id=probe.family_id,
                        policy_stream=variant.policy_stream,
                        actual=actual,
                        rule=expected_rule,
                    )
                    semantic_passed = semantic_result.passed
                    semantic_rationale = semantic_result.rationale
                    SemanticTextAssessment(
                        rule=expected_rule,
                        passed=semantic_result.passed,
                        rationale=semantic_result.rationale or "rubric response was invalid",
                    )
        if expected_rule is not None and semantic_result is None:
            semantic_passed = False
            semantic_rationale = "not run because the generated action was structurally incorrect"
            semantic_result = SemanticTextResult(
                probe_id=probe.probe_id,
                family_id=probe.family_id,
                variant_id="v1",
                rule=expected_rule.value,
                executed=False,
                provider_outcome="not_run_structural_mismatch",
                response_valid=False,
                passed=False,
                rationale=semantic_rationale,
                from_cache=False,
                usage=ProviderUsage(),
                fresh_usage=ProviderUsage(),
            )
        actual_json = None if actual is None else actual.model_dump(mode="json")
        actual_type = None if actual is None else actual.type
        open_text_ok = semantic_passed is not False and (
            semantic_rule is None or semantic_passed is True
        )
        generation_result = GenerationResult(
            probe_id=probe.probe_id,
            family_id=probe.family_id,
            variant_id="v1",
            expected_type=variant.expected_action.type,
            actual_action=actual_json,
            provider_outcome=completion.outcome,
            schema_valid=schema_valid,
            reference_valid=reference_valid,
            license_allowed=license_allowed,
            license_block_code=block_code,
            structural_match=structural_match,
            semantic_rule=semantic_rule,
            semantic_passed=semantic_passed,
            semantic_rationale=semantic_rationale,
            generation_passed=(
                schema_valid
                and reference_valid
                and license_allowed
                and structural_match
                and open_text_ok
            ),
            invented_arguments=(
                schema_valid
                and actual_type == variant.expected_action.type
                and not structural_match
            ),
            intrusive_action=(
                isinstance(variant.expected_action, IdleAction)
                and actual is not None
                and not isinstance(actual, IdleAction)
            ),
            from_cache=completion.from_cache,
            usage=completion.usage,
            fresh_usage=(completion.usage if not completion.from_cache else ProviderUsage()),
        )
        return generation_result, semantic_result

    async def _grade_semantic(
        self,
        *,
        probe_id: str,
        family_id: int,
        policy_stream: str,
        actual: Action,
        rule,
    ) -> SemanticTextResult:
        planned = plan_semantic(
            self.catalog,
            self.generation_builder,
            self.prompts,
            probe_id=probe_id,
            policy_stream=policy_stream,
            actual=actual,
            rule=rule,
        )
        completion = await self._cached(
            planned.identity,
            lambda: self.backend.complete(
                planned.request,
                SemanticTextVerdict.model_validate,
            ),
        )
        try:
            verdict = SemanticTextVerdict.model_validate(completion.value)
        except ValidationError:
            return SemanticTextResult(
                probe_id=probe_id,
                family_id=family_id,
                variant_id="v1",
                rule=rule.value,
                executed=True,
                provider_outcome=completion.outcome,
                response_valid=False,
                passed=False,
                rationale=None,
                from_cache=completion.from_cache,
                usage=completion.usage,
                fresh_usage=(
                    completion.usage if not completion.from_cache else ProviderUsage()
                ),
            )
        return SemanticTextResult(
            probe_id=probe_id,
            family_id=family_id,
            variant_id="v1",
            rule=rule.value,
            executed=True,
            provider_outcome=completion.outcome,
            response_valid=True,
            passed=verdict.passed,
            rationale=verdict.rationale,
            from_cache=completion.from_cache,
            usage=completion.usage,
            fresh_usage=(completion.usage if not completion.from_cache else ProviderUsage()),
        )

    async def _run_pairwise(
        self,
        probe,
        variant_id: str,
        position: ExpectedPosition,
    ) -> PairwiseResult:
        planned = plan_pairwise(
            self.catalog,
            self.generation_builder,
            self.prompts,
            probe,
            variant_id,
            position,
        )
        completion = await self._cached(
            planned.identity,
            lambda: self.backend.complete(
                planned.request,
                PairwiseChoice.model_validate,
            ),
        )
        choice: str | None = None
        try:
            parsed = PairwiseChoice.model_validate(completion.value)
        except ValidationError:
            response_valid = False
        else:
            response_valid = True
            choice = parsed.choice
        variant = next(item for item in probe.variants if item.variant_id == variant_id)
        negative_class = (
            probe.pairwise_negative_class
            if probe.negative_class is NegativeClass.INVARIANCE
            else probe.negative_class
        )
        if negative_class is None:
            raise ValueError("pairwise negative class is missing")
        return PairwiseResult(
            probe_id=probe.probe_id,
            family_id=probe.family_id,
            variant_id=variant_id,
            expected_position=position.value.upper(),
            negative_class=negative_class,
            restraint_pair=(
                isinstance(variant.expected_action, IdleAction)
                and not isinstance(variant.tempting_alternative, IdleAction)
            ),
            provider_outcome=completion.outcome,
            response_valid=response_valid,
            choice=choice,
            correct=response_valid and choice == position.value.upper(),
            from_cache=completion.from_cache,
            usage=completion.usage,
            fresh_usage=(completion.usage if not completion.from_cache else ProviderUsage()),
        )

    async def _run_listwise(self, probe) -> ListwiseResult:
        planned = plan_listwise(
            self.catalog,
            self.generation_builder,
            self.prompts,
            probe,
        )
        presentation = planned.presentation
        completion = await self._cached(
            planned.identity,
            lambda: self.backend.complete(
                planned.request,
                ListwiseRanking.model_validate,
            ),
        )
        ranking: tuple[str, ...] = ()
        expected_ids = tuple(candidate.candidate_id for candidate in presentation.candidates)
        try:
            parsed = ListwiseRanking.model_validate(completion.value)
        except ValidationError:
            response_valid = False
        else:
            ranking = parsed.ranking
            response_valid = len(ranking) == len(expected_ids) and set(ranking) == set(expected_ids)
        expected_index = (
            ranking.index(presentation.expected_candidate_id)
            if response_valid
            else len(expected_ids)
        )
        tempting_index = (
            ranking.index(presentation.tempting_candidate_id)
            if response_valid
            else len(expected_ids)
        )
        return ListwiseResult(
            probe_id=probe.probe_id,
            family_id=probe.family_id,
            variant_id="v1",
            candidate_count=len(presentation.candidates),
            candidate_action_types=tuple(
                candidate.action.type for candidate in presentation.candidates
            ),
            provider_outcome=completion.outcome,
            response_valid=response_valid,
            ranking=ranking,
            expected_candidate_id=presentation.expected_candidate_id,
            tempting_candidate_id=presentation.tempting_candidate_id,
            top1_correct=response_valid and ranking[0] == presentation.expected_candidate_id,
            expected_above_tempting=response_valid and expected_index < tempting_index,
            from_cache=completion.from_cache,
            usage=completion.usage,
            fresh_usage=(completion.usage if not completion.from_cache else ProviderUsage()),
        )

    async def _cached(
        self,
        identity: CacheIdentity,
        call: Callable[[], Awaitable[HarnessCompletion]],
    ) -> HarnessCompletion:
        async with self._semaphore:
            cached = self.cache.get(identity)
            if cached is not None:
                return cached
            try:
                completion = await call()
            except PolicyCallCancelled as error:
                self.cache.put(
                    identity,
                    HarnessCompletion(
                        value={"provider_indeterminate": True},
                        outcome="cancelled",
                        traces=error.calls,
                    ),
                )
                raise
            except PolicyCallError as error:
                outcome = error.calls[-1].outcome if error.calls else "transport_error"
                self.cache.put(
                    identity,
                    HarnessCompletion(
                        value={"provider_indeterminate": True},
                        outcome=outcome,
                        traces=error.calls,
                    ),
                )
                raise
            self.cache.put(identity, completion)
            return completion

async def _gather_phase[T](*awaitables: Awaitable[T]) -> tuple[T, ...]:
    """Cancel and drain an entire phase before propagating its first failure."""
    tasks = tuple(asyncio.ensure_future(awaitable) for awaitable in awaitables)
    try:
        return tuple(await asyncio.gather(*tasks))
    except BaseException:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        raise
