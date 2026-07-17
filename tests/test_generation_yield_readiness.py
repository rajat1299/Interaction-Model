from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from im.assets import (
    AssetRegistry,
    CorpusFamily,
    ReviewDecision,
    ReviewRecord,
    Split,
    build_seed_registry,
)
from im.generation.counterfactuals import TwinAxis, build_twin_programs
from im.generation.pilot_catalog import build_c5_pilot_programs
from im.generation.scenarios import execute_scenario
from im.generation.yield_readiness import (
    G7EvidenceUnit,
    G7ShapeAllocation,
    G7YieldReadiness,
    YieldReadinessError,
    build_yield_inventory_delta,
)


def _reviewed_registry() -> AssetRegistry:
    seeds = build_seed_registry()
    return AssetRegistry(
        assets=seeds.assets,
        reviews=tuple(
            ReviewRecord(
                asset_id=asset.asset_id,
                content_sha256=asset.content_sha256,
                reviewer_id="yield-readiness-test",
                reviewed_at_utc="2026-07-15T00:00:00Z",
                decision=ReviewDecision.APPROVED,
            )
            for asset in seeds.assets
        ),
    )


def _digest(value: int) -> str:
    return f"sha256:{value:064x}"


def test_inventory_delta_rejects_prior_bytes_outside_readiness_binding() -> None:
    readiness = object.__new__(G7YieldReadiness)
    object.__setattr__(readiness, "prior_inventory_sha256", _digest(0))

    with pytest.raises(YieldReadinessError, match="do not match"):
        build_yield_inventory_delta(readiness, b'\n{"families":[]}\n')


def test_allocation_derives_multiplicity_from_distinct_source_units() -> None:
    source = G7EvidenceUnit((_digest(1),), (10,))
    allocation = G7ShapeAllocation(
        family=CorpusFamily.NEUTRAL_TYPING,
        shape_id="g7-test-neutral-10i",
        action_counts=(10, 0, 0, 0, 0, 0, 0, 0, 0),
        source_kind="scenario",
        source_units=(source,),
    )

    assert allocation.multiplicity == len(allocation.source_units) == 1
    with pytest.raises(YieldReadinessError, match="fund one unit only"):
        G7ShapeAllocation(
            family=CorpusFamily.NEUTRAL_TYPING,
            shape_id="g7-test-neutral-10i",
            action_counts=(10, 0, 0, 0, 0, 0, 0, 0, 0),
            source_kind="scenario",
            source_units=(source,) * 2_000,
        )


def test_only_terminal_response_floor_twins_get_the_one_decision_exception() -> None:
    pair = G7EvidenceUnit((_digest(10), _digest(11)), (1, 1))
    action_counts = (1, 0, 0, 0, 0, 0, 0, 1, 0)
    floor = G7ShapeAllocation(
        family=CorpusFamily.NEUTRAL_TYPING,
        shape_id="g7-response-floor-test",
        action_counts=action_counts,
        source_kind="counterfactual",
        source_units=(pair,),
    )
    ordinary = replace(floor, shape_id="g7-non-floor-test")

    assert floor.within_target_band
    assert floor.decision_band_exception == "terminal_floor_counterfactual"
    assert floor.as_json_object()["within_6_20_decision_band"] is False
    assert not ordinary.within_target_band
    assert ordinary.decision_band_exception is None


def test_readiness_rejects_one_source_reused_across_shapes(monkeypatch: pytest.MonkeyPatch) -> None:
    from im.generation.packaging import FAMILY_ACTION_TARGETS

    for family in CorpusFamily:
        monkeypatch.setitem(FAMILY_ACTION_TARGETS, family, {})
    monkeypatch.setitem(FAMILY_ACTION_TARGETS, CorpusFamily.NEUTRAL_TYPING, {"idle": 20})
    source = G7EvidenceUnit((_digest(2),), (10,))
    allocations = tuple(
        G7ShapeAllocation(
            family=CorpusFamily.NEUTRAL_TYPING,
            shape_id=f"g7-test-neutral-{suffix}",
            action_counts=(10, 0, 0, 0, 0, 0, 0, 0, 0),
            source_kind="scenario",
            source_units=(source,),
        )
        for suffix in ("a", "b")
    )

    with pytest.raises(YieldReadinessError, match="fund only one"):
        G7YieldReadiness("sha256:" + "0" * 64, allocations)


@pytest.mark.asyncio
async def test_scenario_units_bind_distinct_validated_streams(tmp_path: Path) -> None:
    program = dict(build_c5_pilot_programs(_reviewed_registry()))["c5-mark-negative"]
    generated = []
    second = replace(
        program,
        master_seed="concrete-two",
        config=replace(program.config, pause_ms=program.config.pause_ms + 1),
    )
    for index, candidate in enumerate((program, second)):
        generated.append(
            await execute_scenario(
                candidate,
                session_id=f"s_yield_concrete_{index}",
                directory=tmp_path / f"concrete-{index}",
                repository_root=Path(__file__).parents[1],
            )
        )
    generated = tuple(generated)

    allocation = G7ShapeAllocation.from_scenarios(
        "g7-test-concrete-units", ((generated[0],), (generated[1],))
    )

    assert allocation.multiplicity == 2
    assert len(allocation.source_units) == len(set(allocation.source_sha256s)) == 2
    assert all(len(unit.source_sha256s) == 1 for unit in allocation.source_units)


@pytest.mark.asyncio
async def test_counterfactual_unit_rejects_unrelated_program_with_matching_link(
    tmp_path: Path,
) -> None:
    registry = _reviewed_registry()
    pool = registry.pool(Split.TRAIN)
    family = CorpusFamily.MARK_POSITIVE
    template = next(item for item in pool.templates if family in item.coverage)
    assets = tuple(item.asset_id for item in pool.assets if family in item.coverage)
    twins = build_twin_programs(
        TwinAxis.DIRECTNESS,
        registry,
        split=Split.TRAIN,
        template_id=template.asset_id,
        asset_ids=assets,
        master_seed="shared-counterfactual-seed",
    )
    programs = (twins.programs[0], replace(twins.programs[1], master_seed="unrelated-seed"))
    generated = []
    for index, program in enumerate(programs):
        generated.append(
            await execute_scenario(
                program,
                session_id=f"s_yield_unrelated_{index}",
                directory=tmp_path / f"unrelated-{index}",
                repository_root=Path(__file__).parents[1],
            )
        )
    generated = tuple(generated)

    with pytest.raises(YieldReadinessError, match="incomplete or inconsistent"):
        G7ShapeAllocation.from_scenarios("g7-test-counterfactual", (generated,))
