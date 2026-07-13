"""Bounded, resumable execution of the three WP15 probe protocols."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from hashlib import sha256

from pydantic import ValidationError

from im.license import Allowed, Blocked, check
from im.policy.prompted import ResponsesRequestBuilder
from im.probes.grading import (
    SemanticTextAssessment,
    grade_generation_structure,
)
from im.probes.harness.artifacts import ApprovedProbeCatalog
from im.probes.harness.backend import HarnessBackend
from im.probes.harness.cache import HarnessCache
from im.probes.harness.candidates import build_listwise_presentation
from im.probes.harness.models import (
    CacheIdentity,
    GenerationResult,
    HarnessCompletion,
    HarnessProtocol,
    HarnessRun,
    ListwiseRanking,
    ListwiseResult,
    PairwiseChoice,
    PairwiseResult,
    ProviderUsage,
    SemanticTextVerdict,
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
        generation = await asyncio.gather(
            *(self._run_generation(probe) for probe in self.catalog.manifest.probes)
        )
        pairwise = await asyncio.gather(
            *(
                self._run_pairwise(probe, variant.variant_id, position)
                for probe in self.catalog.manifest.probes
                for variant in probe.variants
                for position in (ExpectedPosition.A, ExpectedPosition.B)
            )
        )
        listwise = await asyncio.gather(
            *(self._run_listwise(probe) for probe in self.catalog.manifest.probes)
        )
        return HarnessRun(
            manifest_sha256=self.catalog.manifest_sha256,
            review_sha256=self.catalog.review_sha256,
            model=self.generation_builder.config.model,
            reasoning_effort=self.generation_builder.config.reasoning_effort,
            generation=tuple(generation),
            pairwise=tuple(pairwise),
            listwise=tuple(listwise),
        )

    async def _run_generation(self, probe) -> GenerationResult:
        variant = probe.variants[0]
        view = self.catalog.views[(probe.probe_id, "v1")]
        policy_bytes = variant.policy_stream.encode()
        body = self.generation_builder.build(policy_bytes)
        request_bytes = _json_bytes(body)
        identity = self._identity(
            probe_id=probe.probe_id,
            protocol=HarnessProtocol.GENERATION,
            variant_id="v1",
            presentation="canonical",
            prompt_hash=self.generation_builder.renderer.artifacts.prompt_hash,
            request_bytes=request_bytes,
        )
        completion = await self._cached(identity, lambda: self.backend.generate(policy_bytes))
        actual: Action | None = None
        schema_valid = reference_valid = license_allowed = structural_match = False
        block_code: str | None = None
        semantic_rule: str | None = None
        semantic_passed: bool | None = None
        semantic_rationale: str | None = None
        semantic_completion: HarnessCompletion | None = None
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
                if structural_match and structure.text_rule is not None:
                    semantic_rule = structure.text_rule.value
                    semantic, semantic_completion = await self._grade_semantic(
                        probe_id=probe.probe_id,
                        policy_stream=variant.policy_stream,
                        actual=actual,
                        rule=structure.text_rule,
                    )
                    semantic_passed = semantic.passed
                    semantic_rationale = semantic.rationale
                    SemanticTextAssessment(
                        rule=structure.text_rule,
                        passed=semantic.passed,
                        rationale=semantic.rationale,
                    )
        actual_json = None if actual is None else actual.model_dump(mode="json")
        actual_type = None if actual is None else actual.type
        open_text_ok = semantic_passed is not False and (
            semantic_rule is None or semantic_passed is True
        )
        return GenerationResult(
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
            from_cache=(
                completion.from_cache
                and (semantic_completion is None or semantic_completion.from_cache)
            ),
            usage=(
                completion.usage
                if semantic_completion is None
                else completion.usage + semantic_completion.usage
            ),
            fresh_usage=(
                (completion.usage if not completion.from_cache else ProviderUsage())
                + (
                    ProviderUsage()
                    if semantic_completion is None or semantic_completion.from_cache
                    else semantic_completion.usage
                )
            ),
        )

    async def _grade_semantic(
        self,
        *,
        probe_id: str,
        policy_stream: str,
        actual: Action,
        rule,
    ) -> tuple[SemanticTextVerdict, HarnessCompletion]:
        request = self.prompts.semantic_text(
            policy_stream=policy_stream,
            action=actual,
            rule=rule,
        )
        identity = self._identity(
            probe_id=probe_id,
            protocol=HarnessProtocol.SEMANTIC_TEXT,
            variant_id="v1",
            presentation=f"{rule.value}:{_digest(_json_bytes(actual.model_dump(mode='json')))}",
            prompt_hash=request.prompt_hash,
            request_bytes=request.request_bytes,
        )
        completion = await self._cached(
            identity,
            lambda: self.backend.complete(request, SemanticTextVerdict.model_validate),
        )
        return SemanticTextVerdict.model_validate(completion.value), completion

    async def _run_pairwise(
        self,
        probe,
        variant_id: str,
        position: ExpectedPosition,
    ) -> PairwiseResult:
        presentation = probe.teacher_variant(variant_id, expected_position=position)
        request = self.prompts.pairwise(
            policy_stream=str(presentation["policy_stream"]),
            candidate_a=presentation["candidate_a"],
            candidate_b=presentation["candidate_b"],
        )
        identity = self._identity(
            probe_id=probe.probe_id,
            protocol=HarnessProtocol.PAIRWISE,
            variant_id=variant_id,
            presentation=f"expected-{position.value}",
            prompt_hash=request.prompt_hash,
            request_bytes=request.request_bytes,
        )
        completion = await self._cached(
            identity,
            lambda: self.backend.complete(request, PairwiseChoice.model_validate),
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
        variant = probe.variants[0]
        view = self.catalog.views[(probe.probe_id, "v1")]
        presentation = build_listwise_presentation(probe, variant, view)
        request = self.prompts.listwise(
            policy_stream=variant.policy_stream,
            candidates=presentation.candidates,
        )
        candidate_hash = _digest(
            _json_bytes([candidate.as_prompt_json() for candidate in presentation.candidates])
        )
        identity = self._identity(
            probe_id=probe.probe_id,
            protocol=HarnessProtocol.LISTWISE,
            variant_id="v1",
            presentation=candidate_hash,
            prompt_hash=request.prompt_hash,
            request_bytes=request.request_bytes,
        )
        completion = await self._cached(
            identity,
            lambda: self.backend.complete(request, ListwiseRanking.model_validate),
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
        cached = self.cache.get(identity)
        if cached is not None:
            return cached
        async with self._semaphore:
            cached = self.cache.get(identity)
            if cached is not None:
                return cached
            completion = await call()
            self.cache.put(identity, completion)
            return completion

    def _identity(
        self,
        *,
        probe_id: str,
        protocol: HarnessProtocol,
        variant_id: str,
        presentation: str,
        prompt_hash: str,
        request_bytes: bytes,
    ) -> CacheIdentity:
        return CacheIdentity(
            manifest_sha256=self.catalog.manifest_sha256,
            probe_id=probe_id,
            protocol=protocol,
            variant_id=variant_id,
            presentation=presentation,
            model=self.generation_builder.config.model,
            reasoning_effort=self.generation_builder.config.reasoning_effort,
            prompt_hash=prompt_hash,
            request_hash=_digest(request_bytes),
        )


def _json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()


def _digest(value: bytes) -> str:
    return f"sha256:{sha256(value).hexdigest()}"
