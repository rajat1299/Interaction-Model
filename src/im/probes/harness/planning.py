"""Single source of truth for WP15 logical request planning."""

from __future__ import annotations

from dataclasses import dataclass

from im.policy.prompted import ResponsesRequestBuilder
from im.probes.grading import OpenTextRule
from im.probes.harness.artifacts import ApprovedProbeCatalog
from im.probes.harness.candidates import ListwisePresentation, build_listwise_presentation
from im.probes.harness.identity import cache_identity, canonical_request_bytes, digest
from im.probes.harness.models import CacheIdentity, HarnessProtocol
from im.probes.harness.protocols import ProtocolPromptBuilder, ProtocolRequest
from im.probes.model import ExpectedPosition, LogicalProbe
from im.schema.actions import Action


@dataclass(frozen=True, slots=True)
class PlannedGeneration:
    identity: CacheIdentity
    policy_bytes: bytes
    body: dict[str, object]


@dataclass(frozen=True, slots=True)
class PlannedProtocol:
    identity: CacheIdentity
    request: ProtocolRequest


@dataclass(frozen=True, slots=True)
class PlannedListwise:
    identity: CacheIdentity
    request: ProtocolRequest
    presentation: ListwisePresentation


def plan_generation(
    catalog: ApprovedProbeCatalog,
    builder: ResponsesRequestBuilder,
    probe: LogicalProbe,
) -> PlannedGeneration:
    policy_bytes = probe.variants[0].policy_stream.encode()
    body = builder.build(policy_bytes)
    return PlannedGeneration(
        identity=_identity(
            catalog,
            builder,
            probe_id=probe.probe_id,
            protocol=HarnessProtocol.GENERATION,
            variant_id="v1",
            presentation="canonical",
            prompt_hash=builder.renderer.artifacts.prompt_hash,
            request_bytes=canonical_request_bytes(body),
        ),
        policy_bytes=policy_bytes,
        body=body,
    )


def plan_pairwise(
    catalog: ApprovedProbeCatalog,
    builder: ResponsesRequestBuilder,
    prompts: ProtocolPromptBuilder,
    probe: LogicalProbe,
    variant_id: str,
    position: ExpectedPosition,
) -> PlannedProtocol:
    presentation = probe.teacher_variant(variant_id, expected_position=position)
    request = prompts.pairwise(
        policy_stream=str(presentation["policy_stream"]),
        candidate_a=presentation["candidate_a"],
        candidate_b=presentation["candidate_b"],
    )
    return PlannedProtocol(
        identity=_identity(
            catalog,
            builder,
            probe_id=probe.probe_id,
            protocol=HarnessProtocol.PAIRWISE,
            variant_id=variant_id,
            presentation=f"expected-{position.value}",
            prompt_hash=request.prompt_hash,
            request_bytes=request.request_bytes,
        ),
        request=request,
    )


def plan_listwise(
    catalog: ApprovedProbeCatalog,
    builder: ResponsesRequestBuilder,
    prompts: ProtocolPromptBuilder,
    probe: LogicalProbe,
) -> PlannedListwise:
    variant = probe.variants[0]
    presentation = build_listwise_presentation(
        probe,
        variant,
        catalog.views[(probe.probe_id, "v1")],
    )
    request = prompts.listwise(
        policy_stream=variant.policy_stream,
        candidates=presentation.candidates,
    )
    candidate_hash = digest(
        canonical_request_bytes(
            [candidate.as_prompt_json() for candidate in presentation.candidates]
        )
    )
    return PlannedListwise(
        identity=_identity(
            catalog,
            builder,
            probe_id=probe.probe_id,
            protocol=HarnessProtocol.LISTWISE,
            variant_id="v1",
            presentation=candidate_hash,
            prompt_hash=request.prompt_hash,
            request_bytes=request.request_bytes,
        ),
        request=request,
        presentation=presentation,
    )


def plan_semantic(
    catalog: ApprovedProbeCatalog,
    builder: ResponsesRequestBuilder,
    prompts: ProtocolPromptBuilder,
    *,
    probe_id: str,
    policy_stream: str,
    actual: Action,
    rule: OpenTextRule,
) -> PlannedProtocol:
    request = prompts.semantic_text(
        policy_stream=policy_stream,
        action=actual,
        rule=rule,
    )
    return PlannedProtocol(
        identity=_identity(
            catalog,
            builder,
            probe_id=probe_id,
            protocol=HarnessProtocol.SEMANTIC_TEXT,
            variant_id="v1",
            presentation=(
                f"{rule.value}:"
                f"{digest(canonical_request_bytes(actual.model_dump(mode='json')))}"
            ),
            prompt_hash=request.prompt_hash,
            request_bytes=request.request_bytes,
        ),
        request=request,
    )


def _identity(
    catalog: ApprovedProbeCatalog,
    builder: ResponsesRequestBuilder,
    *,
    probe_id: str,
    protocol: HarnessProtocol,
    variant_id: str,
    presentation: str,
    prompt_hash: str,
    request_bytes: bytes,
) -> CacheIdentity:
    return cache_identity(
        manifest_sha256=catalog.manifest_sha256,
        probe_id=probe_id,
        protocol=protocol,
        variant_id=variant_id,
        presentation=presentation,
        model=builder.config.model,
        reasoning_effort=builder.config.reasoning_effort,
        prompt_hash=prompt_hash,
        request_bytes=request_bytes,
    )
