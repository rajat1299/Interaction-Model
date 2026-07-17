"""Generate the constructive Phase-1 G7 readiness packet from sealed inputs."""

from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter

from im.assets import load_verified_registry_seals, render_split_seal_json
from im.assets.model import (
    CorpusFamily,
    LookupAssetPayload,
    Split,
    canonical_artifact_bytes,
)
from im.assets.registry import AssetRegistry
from im.generation.corpus_segments import CorpusSegmentCandidate
from im.generation.g7_catalog import (
    G7_FRESH_SHAPES,
    G7FamilyInputs,
    build_g7_fresh_session_programs,
)
from im.generation.g7_checkpoint_catalog import build_g7_checkpoint_catalog
from im.generation.g7_contention_checkpoint import (
    G7_CONTENTION_CHECKPOINT_SHAPE_ID,
    build_g7_contention_checkpoint_catalog,
)
from im.generation.g7_failed_response_twins import (
    FAILED_RESPONSE_SHAPE_ID,
    build_g7_failed_response_twin_programs,
)
from im.generation.g7_response_assets import (
    GeneratedResponseAsset,
    SimpleResponseProfile,
)
from im.generation.g7_response_catalog import G7_RESPONSE_DRAFT_PROFILES
from im.generation.g7_response_pipeline import (
    G7_FAILED_RESPONSE_PROFILE_IDS,
    G7ResponseGeneration,
    build_g7_response_corpus_gate,
    load_g7_response_generations,
    materialize_g7_failed_response_assets,
    materialize_g7_response_profiles,
    render_g7_response_corpus,
)
from im.generation.g7_response_twins import build_g7_response_floor_twin_program
from im.generation.g7_rollover_checkpoint import (
    G7_ROLLOVER_CHECKPOINT_SHAPES,
    build_g7_rollover_checkpoint_catalog,
)
from im.generation.leak_lint import lint_teacher_prompts
from im.generation.oracle import OracleDecision
from im.generation.packaging import (
    build_split_ledger,
    package_generated_streams,
)
from im.generation.scenarios import (
    GeneratedScenario,
    execute_scenario,
)
from im.generation.yield_readiness import (
    G7ShapeAllocation,
    G7SourceUnit,
    G7YieldReadiness,
    build_yield_evidence,
    build_yield_inventory_delta,
)
from im.policy.prompted import PromptArtifacts, PromptRenderer
from im.schema.actions import CancelAction, SkipAction

_APPROVED = Path("review/phase1/approved")
_PRIOR_INVENTORY = Path("review/phase1/c6-pilot/yield-inventory.json")
_RESPONSE_GENERATIONS = Path("review/phase1/g7-response-generations.json")
_PREVIOUS_RESPONSE_GENERATIONS = Path(
    "review/phase1/g7-readiness-resubmission/response-generations.json"
)
_USER_SPECIFIED_FAILED_RESPONSE = (
    "The Morrow Glen cistern fill percentage lookup failed, so no usable answer came back."
)
_USER_SPECIFIED_FAILED_RESPONSE_KEY = ("g7-response-failed-tool-05", 0)
_FRESH_SHAPES = {shape_id: family for shape_id, family, _vector in G7_FRESH_SHAPES}
_CHECKPOINT_SHAPES = {
    "g7-checkpoint-lookup-duplicate-a": CorpusFamily.LOOKUP_DUPLICATE,
    "g7-checkpoint-lookup-duplicate-b": CorpusFamily.LOOKUP_DUPLICATE,
    "g7-checkpoint-lookup-stale": CorpusFamily.LOOKUP_STALE,
    "g7-checkpoint-timer-cancel": CorpusFamily.TIMER_CANCEL,
    G7_CONTENTION_CHECKPOINT_SHAPE_ID: CorpusFamily.TIMER_CONTENTION,
    "g7-checkpoint-rollover-a": CorpusFamily.ROLLOVER,
    "g7-checkpoint-rollover-b": CorpusFamily.ROLLOVER,
    "g7-checkpoint-rollover-c": CorpusFamily.ROLLOVER,
}
_RESPONSE_DRAFT_BY_SHAPE = {
    profile.group_id: profile for profile in G7_RESPONSE_DRAFT_PROFILES
}
_RESPONSE_SHAPES = {
    shape_id: profile.family for shape_id, profile in _RESPONSE_DRAFT_BY_SHAPE.items()
}
_ROLLOVER_CHECKPOINT_SHAPES = frozenset(
    shape_id for shape_id, _vector in G7_ROLLOVER_CHECKPOINT_SHAPES
)
_REGENERATED_REVIEW_SHAPES = {
    "g7-checkpoint-timer-cancel": 1,
}
_RESPONSE_REVIEW_SHAPES = (
    "g7-response-floor-ordinary-neutral-1",
    "g7-response-floor-ordinary-mark-positive",
    "g7-response-floor-ambiguity-lookup-live",
    "g7-response-floor-lookup-stale-mixed",
)
_RESPONSE_REVIEW_PAIRS_PER_SHAPE = 3
_CANONICAL_READINESS_ROLE = "canonical_readiness_batch"
_MECHANICAL_FUZZ_ROLE = "mechanical_fuzz_witness"


@dataclass(frozen=True, slots=True)
class _Request:
    shape_id: str
    count: int


@dataclass(frozen=True, slots=True)
class _Batch:
    units: tuple[G7SourceUnit, ...]

    @property
    def generated(self) -> tuple[GeneratedScenario, ...]:
        return tuple(scenario for unit in self.units for scenario in unit.scenarios)

    @property
    def selected_action_count(self) -> int:
        return sum(sum(unit.source_decision_counts) for unit in self.units)


_ALLOCATION_REQUESTS = (
    _Request("g7-fresh-neutral-10i", 22),
    _Request("g7-response-floor-ordinary-neutral-1", 10),
    _Request("g7-response-floor-ordinary-neutral-2", 10),
    _Request("g7-response-floor-ordinary-neutral-3", 10),
    _Request("g7-fresh-mark-positive-a-5i-7m", 10),
    _Request("g7-fresh-mark-positive-b-6i-8m", 10),
    _Request("g7-response-floor-ordinary-mark-positive", 10),
    _Request("g7-fresh-mark-negative-7i-3m", 20),
    _Request("g7-response-floor-ordinary-mark-negative", 10),
    _Request("g7-fresh-lookup-live-2i-2d-2g", 20),
    _Request("g7-response-floor-ambiguity-lookup-live", 10),
    _Request(FAILED_RESPONSE_SHAPE_ID, 10),
    _Request("g7-checkpoint-lookup-duplicate-a", 10),
    _Request("g7-checkpoint-lookup-duplicate-b", 10),
    _Request("g7-checkpoint-lookup-stale", 10),
    _Request("g7-response-floor-lookup-stale-mixed", 10),
    _Request("g7-response-floor-lookup-stale-unsupported", 10),
    _Request("g7-fresh-timer-normal-wide-3i-5h-10n", 2),
    _Request("g7-fresh-timer-normal-wide-context-3i-5h-10n", 8),
    _Request("g7-fresh-timer-normal-compact-4i-4h-6n", 1),
    _Request("g7-fresh-timer-normal-compact-context-4i-4h-6n", 4),
    _Request("g7-checkpoint-timer-cancel", 10),
    _Request("g7-fresh-timer-contention-control-2i-2h-2m", 5),
    _Request(G7_CONTENTION_CHECKPOINT_SHAPE_ID, 5),
    _Request("g7-checkpoint-rollover-a", 1),
    _Request("g7-checkpoint-rollover-b", 1),
    _Request("g7-checkpoint-rollover-c", 1),
    _Request("g7-fresh-reserved-10i", 1),
)
_DEV_WITNESS_REQUESTS = (
    _Request("g7-fresh-mark-negative-7i-3m", 20),
    _Request("g7-fresh-reserved-10i", 10),
)
_TEST_WITNESS_REQUESTS = (
    _Request("g7-fresh-lookup-live-2i-2d-2g", 40),
    _Request("g7-fresh-neutral-10i", 16),
)


def _sha256(data: bytes) -> str:
    return f"sha256:{sha256(data).hexdigest()}"


def _seed(scope: str, shape_id: str, ordinal: int, attempt: int) -> str:
    return f"g7-readiness-v1:{scope}:{shape_id}:{ordinal:03d}:{attempt:03d}"


def _family_inputs(registry: AssetRegistry) -> dict[CorpusFamily, G7FamilyInputs]:
    pool = registry.pool(Split.TEST)

    def template_id(family: CorpusFamily) -> str:
        return next(item.asset_id for item in pool.templates if family in item.coverage)

    def asset_ids(*families: CorpusFamily) -> tuple[str, ...]:
        return tuple(
            item.asset_id
            for item in pool.assets
            if any(family in item.coverage for family in families)
        )

    return {
        CorpusFamily.NEUTRAL_TYPING: G7FamilyInputs(
            template_id(CorpusFamily.NEUTRAL_TYPING), asset_ids(CorpusFamily.NEUTRAL_TYPING)
        ),
        CorpusFamily.MARK_POSITIVE: G7FamilyInputs(
            template_id(CorpusFamily.MARK_POSITIVE), asset_ids(CorpusFamily.MARK_POSITIVE)
        ),
        CorpusFamily.MARK_NEGATIVE: G7FamilyInputs(
            template_id(CorpusFamily.MARK_NEGATIVE),
            asset_ids(CorpusFamily.MARK_NEGATIVE, CorpusFamily.MARK_POSITIVE),
        ),
        CorpusFamily.LOOKUP_LIVE: G7FamilyInputs(
            template_id(CorpusFamily.LOOKUP_LIVE),
            tuple(
                item.asset_id
                for item in pool.assets
                if isinstance(item.payload, LookupAssetPayload)
            ),
        ),
        CorpusFamily.LOOKUP_STALE: G7FamilyInputs(
            template_id(CorpusFamily.LOOKUP_STALE), asset_ids(CorpusFamily.LOOKUP_STALE)
        ),
        CorpusFamily.TIMER_NORMAL: G7FamilyInputs(
            template_id(CorpusFamily.TIMER_NORMAL), asset_ids(CorpusFamily.TIMER_NORMAL)
        ),
        CorpusFamily.TIMER_CONTENTION: G7FamilyInputs(
            template_id(CorpusFamily.TIMER_CONTENTION),
            asset_ids(CorpusFamily.TIMER_CONTENTION, CorpusFamily.MARK_POSITIVE),
        ),
        CorpusFamily.RESERVED: G7FamilyInputs(
            template_id(CorpusFamily.RESERVED), asset_ids(CorpusFamily.RESERVED)
        ),
    }


async def _execute(
    program: object, *, repository: Path, directory: Path, session_id: str
) -> GeneratedScenario:
    generated = await execute_scenario(
        program,  # type: ignore[arg-type]
        session_id=session_id,
        directory=directory,
        repository_root=repository,
    )
    return generated


def _record_unit(
    unit: G7SourceUnit,
    *,
    seen_sources: set[str],
    seen_streams: set[str],
    seen_seeds: set[tuple[str, str]],
) -> None:
    seed_key = (
        unit.shape_id,
        unit.master_seed
        + "\0"
        + ",".join(scenario.program.timing_plan.seed.seed for scenario in unit.scenarios),
    )
    if seed_key in seen_seeds:
        raise RuntimeError(f"generation seed was reused for {unit.shape_id}: {unit.master_seed}")
    if set(unit.source_sha256s) & seen_sources:
        raise RuntimeError(f"duplicate raw source identity for {unit.shape_id}")
    stream_sha256s = {scenario.stream.sha256 for scenario in unit.scenarios}
    if stream_sha256s & seen_streams:
        raise RuntimeError(f"duplicate raw stream identity for {unit.shape_id}")
    seen_seeds.add(seed_key)
    seen_sources.update(unit.source_sha256s)
    seen_streams.update(stream_sha256s)


async def _fresh_units(
    registry: AssetRegistry,
    inputs: dict[CorpusFamily, G7FamilyInputs],
    requests: tuple[_Request, ...],
    *,
    scope: str,
    repository: Path,
    directory: Path,
    seen_sources: set[str],
    seen_streams: set[str],
    seen_seeds: set[tuple[str, str]],
) -> list[G7SourceUnit]:
    units: list[G7SourceUnit] = []
    for request in requests:
        if request.shape_id not in _FRESH_SHAPES:
            continue
        for ordinal in range(request.count):
            for attempt in range(100):
                master_seed = _seed(scope, request.shape_id, ordinal, attempt)
                program = dict(
                    build_g7_fresh_session_programs(
                        registry, split=Split.TEST, inputs=inputs, master_seed=master_seed
                    )
                )[request.shape_id]
                generated = await _execute(
                    program,
                    repository=repository,
                    directory=directory / request.shape_id / f"{ordinal:03d}-{attempt:03d}",
                    session_id=f"s_{scope}_{request.shape_id}_{ordinal:03d}_{attempt:03d}",
                )
                unit = G7SourceUnit(
                    request.shape_id,
                    _FRESH_SHAPES[request.shape_id],
                    "scenario",
                    (generated,),
                    master_seed,
                )
                if unit.source_sha256s[0] in seen_sources:
                    continue
                _record_unit(
                    unit,
                    seen_sources=seen_sources,
                    seen_streams=seen_streams,
                    seen_seeds=seen_seeds,
                )
                units.append(unit)
                break
            else:
                raise RuntimeError(f"could not find a distinct source for {request.shape_id}")
    return units


async def _response_units(
    registry: AssetRegistry,
    inputs: dict[CorpusFamily, G7FamilyInputs],
    requests: tuple[_Request, ...],
    response_profiles: dict[str, SimpleResponseProfile],
    failed_assets: tuple[GeneratedResponseAsset, ...],
    *,
    scope: str,
    repository: Path,
    directory: Path,
    seen_sources: set[str],
    seen_streams: set[str],
    seen_seeds: set[tuple[str, str]],
    require_exact_response_provenance: bool,
) -> list[G7SourceUnit]:
    units: list[G7SourceUnit] = []
    for request in requests:
        family = _RESPONSE_SHAPES.get(request.shape_id)
        if family is None or request.shape_id == FAILED_RESPONSE_SHAPE_ID:
            continue
        if request.count != 10:
            raise RuntimeError("each response profile must fund its ten independent pairs")
        draft_profile = _RESPONSE_DRAFT_BY_SHAPE[request.shape_id]
        profile = response_profiles[draft_profile.profile_id]
        for ordinal in range(request.count):
            for attempt in range(100):
                master_seed = _seed(scope, request.shape_id, 0, attempt)
                twin = build_g7_response_floor_twin_program(
                    registry,
                    split=Split.TEST,
                    family=family,
                    inputs=inputs[family],
                    profile=profile,
                    master_seed=master_seed,
                    item_index=ordinal,
                )
                generated = []
                for member, program in zip(("yielded", "active"), twin.programs, strict=True):
                    generated.append(
                        await _execute(
                            program,
                            repository=repository,
                            directory=directory
                            / request.shape_id
                            / f"{ordinal:03d}-{attempt:03d}-{member}",
                            session_id=(
                                f"s_{scope}_{request.shape_id}_{ordinal:03d}_{attempt:03d}_{member}"
                            ),
                        )
                    )
                generated = tuple(generated)
                if require_exact_response_provenance and (
                    len(generated[0].stream.decisions) != 1
                    or generated[0].stream.decisions[0].prefix_bytes
                    != profile.assets[ordinal].teacher_visible_prefix_bytes
                ):
                    raise RuntimeError("reviewed response prefix no longer matches its source")
                unit = G7SourceUnit(
                    request.shape_id,
                    family,
                    "counterfactual",
                    generated,
                    master_seed,
                )
                if set(unit.source_sha256s) & seen_sources:
                    continue
                _record_unit(
                    unit,
                    seen_sources=seen_sources,
                    seen_streams=seen_streams,
                    seen_seeds=seen_seeds,
                )
                units.append(unit)
                break
            else:
                raise RuntimeError(
                    f"could not find a distinct response pair for {request.shape_id}"
                )

    failed_request = next(
        (request for request in requests if request.shape_id == FAILED_RESPONSE_SHAPE_ID), None
    )
    if failed_request is None:
        return units
    if failed_request.count != len(failed_assets):
        raise RuntimeError("failed-response allocation and reviewed assets do not match")
    for ordinal, asset in enumerate(failed_assets):
        for attempt in range(100):
            master_seed = _seed(scope, FAILED_RESPONSE_SHAPE_ID, ordinal, attempt)
            twin = build_g7_failed_response_twin_programs(
                registry,
                invitation=asset.draft.invitation,
                answer_contract=asset.draft.answer_contract,
                candidate_response=asset.candidate_response,
                master_seed=master_seed,
                failed_lookup_index=ordinal % 4,
            )
            generated = tuple(
                [
                    await _execute(
                        program,
                        repository=repository,
                        directory=directory
                        / FAILED_RESPONSE_SHAPE_ID
                        / f"{ordinal:03d}-{attempt:03d}-{member}",
                        session_id=(
                            f"s_{scope}_{FAILED_RESPONSE_SHAPE_ID}_"
                            f"{ordinal:03d}_{attempt:03d}_{member}"
                        ),
                    )
                    for member, program in zip(("yielded", "active"), twin.programs, strict=True)
                ]
            )
            candidates = tuple(
                CorpusSegmentCandidate(parent, twin.checkpoint_segment_index, shape_id)
                for parent, shape_id in zip(
                    generated, twin.candidate_shape_ids, strict=True
                )
            )
            unit = G7SourceUnit(
                FAILED_RESPONSE_SHAPE_ID,
                CorpusFamily.LOOKUP_LIVE,
                "checkpoint_segment",
                generated,
                master_seed,
                candidates,
            )
            if set(unit.source_sha256s) & seen_sources:
                continue
            if (
                require_exact_response_provenance
                and generated[0].stream.decisions[-1].prefix_bytes
                != asset.teacher_visible_prefix_bytes
            ):
                raise RuntimeError("reviewed failed response prefix no longer matches its source")
            _record_unit(
                unit,
                seen_sources=seen_sources,
                seen_streams=seen_streams,
                seen_seeds=seen_seeds,
            )
            units.append(unit)
            break
        else:
            raise RuntimeError("could not find a distinct failed-response pair")
    return units


async def _checkpoint_units(
    registry: AssetRegistry,
    requests: tuple[_Request, ...],
    *,
    scope: str,
    repository: Path,
    directory: Path,
    seen_sources: set[str],
    seen_streams: set[str],
    seen_seeds: set[tuple[str, str]],
) -> list[G7SourceUnit]:
    needed = {
        request.shape_id: request.count
        for request in requests
        if request.shape_id in _CHECKPOINT_SHAPES
    }
    if not needed:
        return []
    accepted: dict[str, list[G7SourceUnit]] = {shape_id: [] for shape_id in needed}
    attempt = 0
    while any(len(accepted[shape_id]) < count for shape_id, count in needed.items()):
        remaining = {
            shape_id: count - len(accepted[shape_id]) for shape_id, count in needed.items()
        }
        if attempt >= 100:
            raise RuntimeError("could not find distinct checkpoint source units")
        master_seed = _seed(scope, "checkpoint-catalog", attempt, 0)
        expected = {shape_id for shape_id, count in remaining.items() if count > 0}
        catalog = []
        if expected - _ROLLOVER_CHECKPOINT_SHAPES - {G7_CONTENTION_CHECKPOINT_SHAPE_ID}:
            catalog.extend(
                await build_g7_checkpoint_catalog(
                    registry,
                    directory=directory / f"catalog-{attempt:03d}",
                    master_seed=master_seed,
                    repository_root=repository,
                )
            )
        if G7_CONTENTION_CHECKPOINT_SHAPE_ID in expected:
            catalog.extend(
                await build_g7_contention_checkpoint_catalog(
                    registry,
                    directory=directory / f"catalog-{attempt:03d}",
                    master_seed=master_seed,
                    repository_root=repository,
                )
            )
        if expected & _ROLLOVER_CHECKPOINT_SHAPES:
            catalog.extend(
                await build_g7_rollover_checkpoint_catalog(
                    registry,
                    directory=directory / f"catalog-{attempt:03d}",
                    master_seed=master_seed,
                    repository_root=repository,
                )
            )
        by_shape = {entry.shape_id: entry for entry in catalog}
        missing = tuple(sorted(expected - set(by_shape)))
        if missing:
            raise RuntimeError("checkpoint catalog is incomplete: " + ", ".join(missing))
        for shape_id, count in needed.items():
            if shape_id not in expected or len(accepted[shape_id]) >= count:
                continue
            entry = by_shape[shape_id]
            candidate = entry.candidate
            if candidate.segment.sha256 in seen_sources:
                continue
            unit = G7SourceUnit(
                shape_id,
                _CHECKPOINT_SHAPES[shape_id],
                "checkpoint_segment",
                (entry.parent,),
                master_seed,
                (candidate,),
            )
            _record_unit(
                unit,
                seen_sources=seen_sources,
                seen_streams=seen_streams,
                seen_seeds=seen_seeds,
            )
            accepted[shape_id].append(unit)
        attempt += 1
    return [unit for shape_id in needed for unit in accepted[shape_id]]


async def _build_batch(
    registry: AssetRegistry,
    inputs: dict[CorpusFamily, G7FamilyInputs],
    response_profiles: dict[str, SimpleResponseProfile],
    failed_assets: tuple[GeneratedResponseAsset, ...],
    requests: tuple[_Request, ...],
    *,
    scope: str,
    repository: Path,
    directory: Path,
    seen_sources: set[str],
    seen_streams: set[str],
    seen_seeds: set[tuple[str, str]],
    require_exact_response_provenance: bool = False,
    reuse_reviewed_response_sources: bool = False,
) -> _Batch:
    fresh_units = await _fresh_units(
        registry,
        inputs,
        requests,
        scope=scope,
        repository=repository,
        directory=directory / "fresh",
        seen_sources=seen_sources,
        seen_streams=seen_streams,
        seen_seeds=seen_seeds,
    )
    response_seen_sources = seen_sources
    response_seen_streams = seen_streams
    if reuse_reviewed_response_sources:
        # Mechanical witnesses execute the same reviewed response assets again. Their exact
        # stream bytes may match an earlier throughput batch, but identities must remain unique
        # inside this batch and cannot collide with one of its fresh sources.
        response_seen_sources = {
            source for unit in fresh_units for source in unit.source_sha256s
        }
        response_seen_streams = {
            scenario.stream.sha256 for unit in fresh_units for scenario in unit.scenarios
        }
    response_units = await _response_units(
        registry,
        inputs,
        requests,
        response_profiles,
        failed_assets,
        scope=scope,
        repository=repository,
        directory=directory / "floor",
        seen_sources=response_seen_sources,
        seen_streams=response_seen_streams,
        seen_seeds=seen_seeds,
        require_exact_response_provenance=require_exact_response_provenance,
    )
    if reuse_reviewed_response_sources:
        seen_sources.update(
            source for unit in response_units for source in unit.source_sha256s
        )
        seen_streams.update(
            scenario.stream.sha256 for unit in response_units for scenario in unit.scenarios
        )
    checkpoint_units = await _checkpoint_units(
        registry,
        requests,
        scope=scope,
        repository=repository,
        directory=directory / "checkpoint",
        seen_sources=seen_sources,
        seen_streams=seen_streams,
        seen_seeds=seen_seeds,
    )
    units = [*fresh_units, *response_units, *checkpoint_units]
    requested = {request.shape_id: request.count for request in requests}
    actual = {shape_id: sum(unit.shape_id == shape_id for unit in units) for shape_id in requested}
    if actual != requested:
        raise RuntimeError(f"source-unit search did not satisfy requests: {actual!r}")
    batch = _Batch(tuple(units))
    generated = batch.generated
    if len({scenario.stream.sha256 for scenario in generated}) != len(generated):
        raise RuntimeError("duplicate generated stream identity")
    return batch


def _allocation(batch: _Batch, prior_inventory_sha256: str) -> G7YieldReadiness:
    allocations: list[G7ShapeAllocation] = []
    for request in _ALLOCATION_REQUESTS:
        units = tuple(unit for unit in batch.units if unit.shape_id == request.shape_id)
        if len(units) != request.count:
            raise RuntimeError(f"allocation is missing {request.shape_id}")
        first = units[0]
        if not first.checkpoint_candidates:
            allocation = G7ShapeAllocation.from_scenarios(
                request.shape_id, tuple(unit.scenarios for unit in units)
            )
        else:
            candidates = tuple(unit.checkpoint_candidates for unit in units)
            allocation = G7ShapeAllocation.from_checkpoint_segments(candidates)
        if (
            allocation.family is not first.family
            or allocation.source_kind != first.source_kind
            or allocation.action_counts != first.action_counts
        ):
            raise RuntimeError(f"canonical allocation drifted for {request.shape_id}")
        allocations.append(allocation)
    readiness = G7YieldReadiness(
        prior_inventory_sha256,
        tuple(sorted(allocations, key=lambda item: (item.family.value, item.shape_id))),
    )
    if readiness.total_decisions != 2_000:
        raise RuntimeError("G7 allocation is not exactly 2,000 actions")
    if sum(item.multiplicity for item in readiness.allocations) != 241:
        raise RuntimeError("G7 allocation must contain 241 whole source units")
    if sum(len(item.source_sha256s) for item in readiness.allocations) != 331:
        raise RuntimeError("G7 allocation must contain 331 raw source identities")
    return readiness


def _throughput_batch_contract(batch: int) -> dict[str, object]:
    """State the TEST-only readiness role of one throughput batch."""
    if isinstance(batch, bool) or not isinstance(batch, int) or batch < 1:
        raise ValueError("throughput batch must be a positive integer")
    canonical = batch == 1
    return {
        "role": _CANONICAL_READINESS_ROLE if canonical else _MECHANICAL_FUZZ_ROLE,
        "input_split": Split.TEST.value,
        "training_corpus_admission_eligible": False,
        "response_review_eligible": canonical,
        "runtime_oracle_license_validation": "validated",
        "response_subtype_and_text_gate": "validated",
        "response_asset_provenance": (
            "exact_neutral_generation_request"
            if canonical
            else "reused_semantic_asset_non_admissible"
        ),
        "response_source_identity": (
            "unique_canonical_streams"
            if canonical
            else "reviewed_stream_bytes_may_repeat_across_batches"
        ),
        "response_post_teacher_gate": (
            "required_before_template_promotion"
            if canonical
            else "not_applicable_non_admissible"
        ),
    }


def _witness(name: str, batch: _Batch, expected_actions: int) -> dict[str, object]:
    if batch.selected_action_count != expected_actions:
        raise RuntimeError(f"{name} witness has the wrong action count")
    return {
        "label": name,
        "purpose": "dry-run scale witness; not a sealed Phase-2 split",
        "input_split": Split.TEST.value,
        "whole_source_units": len(batch.units),
        "raw_source_identities": [
            source for unit in batch.units for source in unit.source_sha256s
        ],
        "action_count": batch.selected_action_count,
        "shapes": [
            {
                "shape_id": request.shape_id,
                "source_units": sum(unit.shape_id == request.shape_id for unit in batch.units),
            }
            for request in (
                _DEV_WITNESS_REQUESTS if name == "DEV-300" else _TEST_WITNESS_REQUESTS
            )
        ],
    }


def _source_index(units: tuple[G7SourceUnit, ...], *, role: str) -> list[dict[str, object]]:
    records = []
    for unit in units:
        records.append(
            {
                "role": role,
                "shape_id": unit.shape_id,
                "family": unit.family.value,
                "source_kind": unit.source_kind,
                "raw_source_sha256s": list(unit.source_sha256s),
                "source_decision_counts": list(unit.source_decision_counts),
                "master_seed": unit.master_seed,
                "parent_stream_sha256s": sorted(
                    scenario.stream.sha256 for scenario in unit.scenarios
                ),
                "sidecar_sha256s": sorted(scenario.sidecar.sha256 for scenario in unit.scenarios),
                "checkpoint": unit.checkpoint_metadata,
            }
        )
    return sorted(
        records,
        key=lambda item: (
            str(item["role"]),
            str(item["shape_id"]),
            tuple(item["raw_source_sha256s"]),
        ),
    )


def _review_units(batch: _Batch) -> tuple[G7SourceUnit, ...]:
    selected: list[G7SourceUnit] = []
    for shape_id, count in _REGENERATED_REVIEW_SHAPES.items():
        matches = tuple(unit for unit in batch.units if unit.shape_id == shape_id)
        if len(matches) < count:
            raise RuntimeError(f"review packet lacks {shape_id}")
        selected.extend(matches[:count])
    for shape_id in _RESPONSE_REVIEW_SHAPES:
        matches = tuple(unit for unit in batch.units if unit.shape_id == shape_id)
        if len(matches) < _RESPONSE_REVIEW_PAIRS_PER_SHAPE or any(
            len(unit.scenarios) != 2 for unit in matches[:_RESPONSE_REVIEW_PAIRS_PER_SHAPE]
        ):
            raise RuntimeError(f"response review must retain paired siblings for {shape_id}")
        selected.extend(matches[:_RESPONSE_REVIEW_PAIRS_PER_SHAPE])
    return tuple(selected)


def _review_scope(shape_id: str) -> str:
    if shape_id in _RESPONSE_REVIEW_SHAPES:
        return "response twin"
    return "regenerated stream"


def _review_bytes(units: tuple[G7SourceUnit, ...]) -> bytes:
    stream_rows = []
    decision_rows = []
    for unit in units:
        candidate_by_stream = {
            candidate.parent.stream.sha256: candidate
            for candidate in unit.checkpoint_candidates
        }
        for scenario in unit.scenarios:
            candidate = candidate_by_stream.get(scenario.stream.sha256)
            selected_calls = set(() if candidate is None else candidate.selected_call_indices)
            counterfactual = scenario.program.counterfactual
            stream_rows.append(
                (
                    _review_scope(unit.shape_id),
                    unit.shape_id,
                    unit.source_kind,
                    "" if counterfactual is None else counterfactual.group_id,
                    "" if counterfactual is None else counterfactual.member_id,
                    scenario.stream.sha256,
                    len(scenario.sidecar.decisions),
                    (
                        "all"
                        if candidate is None
                        else ", ".join(str(call) for call in candidate.selected_call_indices)
                    ),
                )
            )
            for decision in scenario.sidecar.decisions:
                action = json.dumps(
                    decision.action.model_dump(mode="json"),
                    ensure_ascii=False,
                    separators=(",", ":"),
                    sort_keys=True,
                ).replace("|", "\\|")
                decision_rows.append(
                    (
                        unit.shape_id,
                        scenario.stream.sha256.removeprefix("sha256:")[:12],
                        decision.call_index,
                        decision.observed_policy_seq,
                        "yes" if candidate is None or decision.call_index in selected_calls else "",
                        (
                            ""
                            if decision.response_warrant_kind is None
                            else (
                                f"{decision.response_warrant_kind.value}:"
                                f"{decision.response_warrant_snapshot_event_id}; "
                                f"floor:{decision.floor_opening_snapshot_event_id}"
                            )
                        ),
                        _causal_evidence(decision),
                        action,
                    )
                )
    lines = [
        "# G7 readiness review",
        "",
        "This is a risk-weighted human review packet. The exact 2,000-action proof is in "
        "`g7-readiness.json`; master seeds are reproduction metadata, never evidence.",
        "",
        "Review scope: one regenerated timer-cancel stream and three independent response-floor "
        "pairs for each of four rejected response shapes. `RESPONSE-DELTA.md` separately contains "
        "only the newly generated response texts that lack prior human approval. Approved "
        "failed-result and skip-basis streams are excluded; basic asset and binding artifacts are "
        "not under review.",
        "",
        "All G7 streams use sealed TEST assets and are non-admissible readiness evidence, "
        "never training rows. `throughput.json` declares batch 1 as the sole "
        "`canonical_readiness_batch`: it binds exact neutral-request provenance and the "
        "post-teacher response gate for template promotion. In production, batches 2–5 use "
        "distinct seed namespaces and are runtime-validated `mechanical_fuzz_witness` batches; "
        "they execute the same reviewed response assets again, so response stream bytes may "
        "repeat across batches.",
        "",
        "Checkpoint rows retain the complete parent stream and sidecar. `selected` marks the "
        "later-checkpoint calls that fund G7; no detached segment is presented as a stream.",
        "",
        "## Review streams",
        "",
        "| Scope | Shape | Source kind | Twin group | Member | Stream | Parent decisions | "
        "Selected checkpoint calls |",
        "|---|---|---|---|---|---|---:|---|",
    ]
    lines.extend(
        f"| {scope} | `{shape}` | `{kind}` | `{group}` | `{member}` | `{stream}` | "
        f"{count} | {calls} |"
        for scope, shape, kind, group, member, stream, count, calls in sorted(stream_rows)
    )
    lines.extend(
        (
            "",
            "## Decision table",
            "",
            "| Shape | Stream | Call | Policy seq | Selected | Yield evidence | "
            "Causal evidence | Scripted action |",
            "|---|---|---:|---:|---|---|---|---|",
        )
    )
    lines.extend(
        f"| `{shape}` | `{stream}` | {call} | {seq} | {selected} | "
        f"{yield_evidence} | `{causal_evidence}` | `{action}` |"
        for (
            shape,
            stream,
            call,
            seq,
            selected,
            yield_evidence,
            causal_evidence,
            action,
        ) in sorted(decision_rows)
    )
    return ("\n".join(lines) + "\n").encode("utf-8")


def _causal_evidence(decision: OracleDecision) -> str:
    action = decision.action
    if isinstance(action, SkipAction):
        evidence = decision.skip_evidence
        value = (
            {
                "target_result_event_id": action.target_event_id,
                "scripted_skip_reason": action.reason.value,
            }
            if evidence is None
            else evidence.as_json_object()
        )
    elif isinstance(action, CancelAction):
        evidence = decision.cancel_resolution_evidence
        if evidence is None:
            raise RuntimeError("reviewed cancel lacks resolution evidence")
        value = evidence.as_json_object()
    else:
        return ""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).replace(
        "|", "\\|"
    )


def _evidence_files(
    units: tuple[G7SourceUnit, ...], *, prefix: str = ""
) -> dict[str, bytes]:
    files: dict[str, bytes] = {}
    for unit in units:
        for scenario in unit.scenarios:
            stream = scenario.stream.sha256.removeprefix("sha256:")
            for segment in scenario.stream.segments:
                files[
                    f"{prefix}teacher/{stream}/{segment.sha256.removeprefix('sha256:')}.jsonl"
                ] = segment.policy_bytes
            files[f"{prefix}reviewer/{stream}/sidecar.json"] = scenario.sidecar.canonical_bytes
            files[f"{prefix}reviewer/{stream}/runtime-ledger.json"] = (
                scenario.stream.final_ledger.canonical_bytes
            )
        for candidate in unit.checkpoint_candidates:
            stream = candidate.parent.stream.sha256.removeprefix("sha256:")
            files[
                f"{prefix}reviewer/{stream}/checkpoint-selection.json"
            ] = canonical_artifact_bytes(
                {
                    "format_version": 1,
                    "parent_stream_sha256": candidate.parent.stream.sha256,
                    "parent_sidecar_sha256": candidate.parent.sidecar.sha256,
                    "segment_sha256": candidate.segment.sha256,
                    "segment_index": candidate.segment_index,
                    "checkpoint_seq": candidate.checkpoint_seq,
                    "previous_segment_hash": candidate.previous_segment_hash,
                    "selected_call_indices": list(candidate.selected_call_indices),
                }
            )
    return files


def _review_files(units: tuple[G7SourceUnit, ...]) -> dict[str, bytes]:
    return {"REVIEW.md": _review_bytes(units), **_evidence_files(units)}


def _response_review_delta(
    previous: tuple[G7ResponseGeneration, ...], current: tuple[G7ResponseGeneration, ...]
) -> bytes:
    """Render only newly generated response texts that lack the prior human approval."""
    previous_by_key = {(item.profile_id, item.item_index): item for item in previous}
    current_by_key = {(item.profile_id, item.item_index): item for item in current}
    if set(previous_by_key) != set(current_by_key) or len(current_by_key) != 90:
        raise RuntimeError("response review baseline does not match the current 90-record corpus")
    subject_by_key = {
        (profile.profile_id, index): draft.answer_contract.subject_id
        for profile in G7_RESPONSE_DRAFT_PROFILES
        for index, draft in enumerate(profile.drafts)
    } | {
        (profile_id, 0): f"failed-tool-{index:02d}"
        for index, profile_id in enumerate(G7_FAILED_RESPONSE_PROFILE_IDS)
    }
    changed = tuple(
        (key, previous_by_key[key], current_by_key[key])
        for key in sorted(current_by_key)
        if previous_by_key[key].candidate_response != current_by_key[key].candidate_response
    )
    user_specified = next(
        (
            item
            for item in changed
            if item[0] == _USER_SPECIFIED_FAILED_RESPONSE_KEY
            and item[2].candidate_response == _USER_SPECIFIED_FAILED_RESPONSE
        ),
        None,
    )
    if user_specified is None:
        raise RuntimeError("failed-tool-05 does not match the user-specified replacement")
    pending = tuple(item for item in changed if item is not user_specified)

    def cell(value: str) -> str:
        return value.replace("|", "\\|").replace("\n", "<br>")

    lines = [
        "# G7 response review delta",
        "",
        f"Review only these {len(pending)} newly generated response texts. "
        f"{90 - len(changed)} texts are byte-identical to the already-approved corpus; "
        "failed-tool-05 exactly matches the user-specified replacement and needs no renewed "
        "review.",
        "",
        "| Profile | Item | Subject | Previous approved text | New exact-prefix generation | "
        "Neutral request |",
        "|---|---:|---|---|---|---|",
    ]
    lines.extend(
        f"| `{key[0]}` | {key[1]} | `{subject_by_key[key]}` | "
        f"{cell(old.candidate_response)} | {cell(new.candidate_response)} | "
        f"`{new.request_sha256}` |"
        for key, old, new in pending
    )
    return ("\n".join(lines) + "\n").encode("utf-8")


async def generate_g7_readiness_packet(
    *, repository: Path, output: Path, reduced: bool = False
) -> None:
    """Write the full five-batch packet (or one complete batch for test runs)."""
    repository = repository.resolve()
    output = output if output.is_absolute() else repository / output
    if output.exists():
        raise FileExistsError(f"G7 readiness output already exists: {output}")
    approved = repository / _APPROVED
    registry_jsonl = (approved / "registry.jsonl").read_bytes()
    prior_inventory_bytes = (repository / _PRIOR_INVENTORY).read_bytes()
    response_generation_bytes = (repository / _RESPONSE_GENERATIONS).read_bytes()
    previous_response_generation_bytes = (
        repository / _PREVIOUS_RESPONSE_GENERATIONS
    ).read_bytes()
    seal_jsons = tuple(
        (approved / name).read_bytes() for name in ("test-seal.json", "demo-seal.json")
    )
    registry, seals = load_verified_registry_seals(registry_jsonl, seal_jsons)
    prior_inventory_sha256 = _sha256(prior_inventory_bytes)
    inputs = _family_inputs(registry)
    generations = load_g7_response_generations(response_generation_bytes)
    previous_generations = load_g7_response_generations(previous_response_generation_bytes)
    seen_sources: set[str] = set()
    seen_streams: set[str] = set()
    seen_seeds: set[tuple[str, str]] = set()
    batch_count = 1 if reduced else 5
    throughput: list[dict[str, object]] = []
    observed_batch_ms: list[int] = []
    throughput_artifacts: dict[str, bytes] = {}
    response_gates = []
    first_batch: _Batch | None = None
    with TemporaryDirectory(prefix="im-g7-readiness-runs-") as runs:
        run_root = Path(runs)
        response_profiles = await materialize_g7_response_profiles(
            registry,
            inputs=inputs,
            draft_profiles=G7_RESPONSE_DRAFT_PROFILES,
            generations=generations,
            master_seeds={
                profile.profile_id: _seed("throughput-1", profile.group_id, 0, 0)
                for profile in G7_RESPONSE_DRAFT_PROFILES
            },
            directory=run_root / "response-prefixes/regular",
            repository_root=repository,
        )
        failed_assets = await materialize_g7_failed_response_assets(
            registry,
            generations=generations,
            master_seeds={
                profile_id: _seed(
                    "throughput-1", FAILED_RESPONSE_SHAPE_ID, ordinal, 0
                )
                for ordinal, profile_id in enumerate(G7_FAILED_RESPONSE_PROFILE_IDS)
            },
            directory=run_root / "response-prefixes/failed",
            repository_root=repository,
        )
        for index in range(batch_count):
            batch_number = index + 1
            batch_contract = _throughput_batch_contract(batch_number)
            started = perf_counter()
            batch = await _build_batch(
                registry,
                inputs,
                response_profiles,
                failed_assets,
                _ALLOCATION_REQUESTS,
                scope=f"throughput-{batch_number}",
                repository=repository,
                directory=run_root / f"throughput-{batch_number}",
                seen_sources=seen_sources,
                seen_streams=seen_streams,
                seen_seeds=seen_seeds,
                require_exact_response_provenance=bool(
                    batch_contract["response_review_eligible"]
                ),
                reuse_reviewed_response_sources=not bool(
                    batch_contract["response_review_eligible"]
                ),
            )
            readiness = _allocation(batch, prior_inventory_sha256)
            response_gates.append(
                build_g7_response_corpus_gate(
                    batch.units,
                    response_profiles=response_profiles,
                    failed_assets=failed_assets,
                )
            )
            observed_batch_ms.append(int(round((perf_counter() - started) * 1_000)))
            throughput.append(
                {
                    "batch": batch_number,
                    "seed_namespace": f"throughput-{batch_number}",
                    **batch_contract,
                    "selected_action_count": readiness.total_decisions,
                    "whole_source_units": sum(item.multiplicity for item in readiness.allocations),
                    "raw_source_identity_count": sum(
                        len(item.source_sha256s) for item in readiness.allocations
                    ),
                    "allocation_sha256": readiness.sha256,
                }
            )
            batch_prefix = f"throughput/batch-{batch_number:03d}"
            throughput_artifacts[f"{batch_prefix}-g7-readiness.json"] = (
                readiness.canonical_bytes
            )
            throughput_artifacts[f"{batch_prefix}-manifest.json"] = (
                package_generated_streams(batch.generated).canonical_bytes
            )
            throughput_artifacts[f"{batch_prefix}-source-index.json"] = (
                canonical_artifact_bytes(
                    {
                        "format_version": 1,
                        "source_identity_rule": (
                            "raw SHA-256 identity; master_seed is reproduction metadata only"
                        ),
                        "batch": batch_number,
                        "batch_contract": batch_contract,
                        "sources": _source_index(
                            batch.units, role=str(batch_contract["role"])
                        ),
                    }
                )
            )
            throughput_artifacts.update(
                _evidence_files(batch.units, prefix=f"{batch_prefix}/evidence/")
            )
            if first_batch is None:
                first_batch = batch
        assert first_batch is not None
        if not (
            throughput[0]["role"] == _CANONICAL_READINESS_ROLE
            and throughput[0]["response_review_eligible"] is True
            and all(
                item["role"] == _MECHANICAL_FUZZ_ROLE
                and item["response_review_eligible"] is False
                for item in throughput[1:]
            )
            and all(
                item["training_corpus_admission_eligible"] is False
                and item["input_split"] == Split.TEST.value
                for item in throughput
            )
        ):
            raise RuntimeError(
                "throughput batches do not preserve the TEST-only readiness boundary"
            )
        readiness = _allocation(first_batch, prior_inventory_sha256)
        response_corpus = render_g7_response_corpus(response_gates[0])
        dev_batch = await _build_batch(
            registry,
            inputs,
            response_profiles,
            failed_assets,
            _DEV_WITNESS_REQUESTS,
            scope="dev-300-witness",
            repository=repository,
            directory=run_root / "dev-300-witness",
            seen_sources=seen_sources,
            seen_streams=seen_streams,
            seen_seeds=seen_seeds,
        )
        test_batch = await _build_batch(
            registry,
            inputs,
            response_profiles,
            failed_assets,
            _TEST_WITNESS_REQUESTS,
            scope="test-400-witness",
            repository=repository,
            directory=run_root / "test-400-witness",
            seen_sources=seen_sources,
            seen_streams=seen_streams,
            seen_seeds=seen_seeds,
        )

        all_generated = (*first_batch.generated, *dev_batch.generated, *test_batch.generated)
        manifest = package_generated_streams(all_generated)
        split_ledger = build_split_ledger(all_generated)
        leak_lint = lint_teacher_prompts(
            all_generated, PromptRenderer(PromptArtifacts.from_repository(repository))
        )
        review_units = _review_units(first_batch)
        files = {
            "manifest.json": manifest.canonical_bytes,
            "split-ledger.json": split_ledger.canonical_bytes,
            "leak-lint.json": leak_lint.canonical_bytes,
            "g7-readiness.json": readiness.canonical_bytes,
            "response-corpus.json": response_corpus,
            "response-generations.json": response_generation_bytes,
            "RESPONSE-DELTA.md": _response_review_delta(
                previous_generations, generations
            ),
            "yield-inventory-delta.json": build_yield_inventory_delta(
                readiness, prior_inventory_bytes
            ),
            "yield-evidence.json": build_yield_evidence(first_batch.generated),
            "source-index.json": canonical_artifact_bytes(
                {
                    "format_version": 1,
                    "source_identity_rule": (
                        "raw SHA-256 identity; master_seed is reproduction metadata only"
                    ),
                    "allocation_contract": _throughput_batch_contract(1),
                    "allocation": _source_index(
                        first_batch.units, role=_CANONICAL_READINESS_ROLE
                    ),
                    "dev_witness": _source_index(dev_batch.units, role="DEV-300"),
                    "test_witness": _source_index(test_batch.units, role="TEST-400"),
                }
            ),
            "scale-witnesses.json": canonical_artifact_bytes(
                {
                    "format_version": 1,
                    "witnesses": [
                        _witness("DEV-300", dev_batch, 300),
                        _witness("TEST-400", test_batch, 400),
                    ],
                }
            ),
            "throughput.json": canonical_artifact_bytes(
                {
                    "format_version": 1,
                    "mode": "reduced-one-batch" if reduced else "production-five-batch",
                    "claim": (
                        "one complete 2,000-action canonical TEST readiness batch"
                        if reduced
                        else (
                            "10,000 actual selected actions across one canonical TEST readiness "
                            "batch and four non-admissible mechanical-fuzz, seed-namespace-"
                            "distinct 2,000-action batches; reviewed response stream bytes may "
                            "repeat across batches"
                        )
                    ),
                    "total_selected_actions": sum(
                        int(item["selected_action_count"]) for item in throughput
                    ),
                    "wall_clock_timing": (
                        "observational only; emitted to stdout and excluded from packet bytes"
                    ),
                    "batches": throughput,
                }
            ),
        }
        files.update(throughput_artifacts)
        files.update(_review_files(review_units))
        files["packet.json"] = canonical_artifact_bytes(
            {
                "format_version": 1,
                "inputs": {
                    "approved_directory": _APPROVED.as_posix(),
                    "prior_inventory": {
                        "path": _PRIOR_INVENTORY.as_posix(),
                        "sha256": prior_inventory_sha256,
                    },
                    "response_generations": {
                        "path": _RESPONSE_GENERATIONS.as_posix(),
                        "sha256": _sha256(response_generation_bytes),
                    },
                    "previous_approved_response_generations": {
                        "path": _PREVIOUS_RESPONSE_GENERATIONS.as_posix(),
                        "sha256": _sha256(previous_response_generation_bytes),
                    },
                    "registry_sha256": _sha256(registry_jsonl),
                    "seals": [
                        {
                            "split": seal.split.value,
                            "pool_sha256": seal.pool_sha256,
                            "seal_sha256": _sha256(render_split_seal_json(seal)),
                        }
                        for seal in sorted(seals, key=lambda seal: seal.split.value)
                    ],
                },
                "prior_inventory_sha256": prior_inventory_sha256,
                "exact_allocation_sha256": readiness.sha256,
                "yield_inventory_delta_sha256": _sha256(
                    files["yield-inventory-delta.json"]
                ),
                "yield_evidence_sha256": _sha256(files["yield-evidence.json"]),
                "response_corpus_sha256": _sha256(files["response-corpus.json"]),
                "response_generations_sha256": _sha256(
                    files["response-generations.json"]
                ),
                "response_review_delta_sha256": _sha256(files["RESPONSE-DELTA.md"]),
                "canonical_response_review": {
                    "throughput_batch": 1,
                    "role": _CANONICAL_READINESS_ROLE,
                    "input_split": Split.TEST.value,
                    "training_corpus_admission_eligible": False,
                    "response_count": 90,
                    "neutral_request_provenance": "exact_neutral_generation_request",
                    "post_teacher_gate": "required_before_template_promotion",
                },
                "validator_evidence": {
                    "response_floor_twin_alignment": {
                        "status": "validated",
                        "group_count": sum(
                            item.multiplicity
                            for item in readiness.allocations
                            if item.decision_band_exception
                            == "terminal_floor_counterfactual"
                        ),
                        "streams_per_group": 2,
                        "decisions_after_branch": 0,
                    },
                    "semantic_duplicate_schedule": {
                        "status": "validated_at_oracle_boundary",
                        "timer_cancel_source_units": sum(
                            unit.shape_id == "g7-checkpoint-timer-cancel"
                            for unit in first_batch.units
                        ),
                    },
                    "response_prose_lint": {
                        "status": "validated",
                        "response_count": len(response_gates[0].bindings),
                    },
                },
                "throughput_sha256": _sha256(files["throughput.json"]),
                "stream_manifest_sha256": manifest.sha256,
                "split_ledger_sha256": split_ledger.sha256,
                "leak_lint_sha256": leak_lint.sha256,
                "review_stream_count": sum(len(unit.scenarios) for unit in review_units),
            }
        )

    if not reduced and sum(int(item["selected_action_count"]) for item in throughput) != 10_000:
        raise RuntimeError("production throughput did not execute exactly 10,000 selected actions")
    output.parent.mkdir(parents=True, exist_ok=True)
    checksums = "".join(
        f"{sha256(data).hexdigest()}  {path}\n" for path, data in sorted(files.items())
    ).encode("ascii")
    with TemporaryDirectory(prefix=f".{output.name}-", dir=output.parent) as staging:
        root = Path(staging)
        for path, data in files.items():
            destination = root / path
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)
        (root / "SHA256SUMS").write_bytes(checksums)
        root.replace(output)
    print(
        json.dumps(
            {
                "event": "g7-readiness-observed-timing",
                "proof_binding": "excluded-from-packet",
                "batch_elapsed_ms": observed_batch_ms,
            },
            separators=(",", ":"),
            sort_keys=True,
        )
    )


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--reduced",
        action="store_true",
        help="run one complete 2,000-action batch; production remains five batches",
    )
    return parser.parse_args()


def main() -> None:
    args = _arguments()
    asyncio.run(
        generate_g7_readiness_packet(
            repository=args.repository,
            output=args.output,
            reduced=args.reduced,
        )
    )


if __name__ == "__main__":
    main()
