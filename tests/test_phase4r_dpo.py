from __future__ import annotations

from hashlib import sha256
from pathlib import Path

import pytest

from im.generation.scenarios import execute_scenario
from im.policy.intent import IntentRegistry, ResolutionStatus, resolve_policy_intent
from im.training.phase4_pair_mining import PairCategory
from im.training.phase4r_dpo import (
    _canceled_long_programs,
    _capture_runtime_surface_async,
    _dev_preference_category,
    _offline_concepts,
    _strata,
    _surface_assets,
    _surface_label,
    _twin_common_inputs,
    _variant_programs,
)


def test_dev_preference_roster_is_mechanical_and_includes_positive_routes() -> None:
    base = {
        "coverage_tags": [],
        "expected_action": {"type": "delegate"},
        "source_unit_id": "frozen-source",
    }
    assert _dev_preference_category({**base, "action_type": "delegate"})[0] == (
        PairCategory.MIRRORED_POSITIVE_CONTROLS.value
    )
    assert _dev_preference_category(
        {
            **base,
            "action_type": "schedule",
            "expected_action": {"type": "schedule"},
        }
    )[0] == PairCategory.MIRRORED_POSITIVE_CONTROLS.value
    assert _dev_preference_category(
        {
            **base,
            "action_type": "idle",
            "coverage_tags": ["hard:duplicate_delegate_negative"],
            "expected_action": {"type": "idle", "reason": "awaiting_tool"},
        }
    )[0] == PairCategory.DUPLICATE_DELEGATE_VS_IDLE.value
    assert _dev_preference_category(
        {
            **base,
            "action_type": "idle",
            "expected_action": {"type": "idle", "reason": "already_handled"},
        }
    )[0] is None


@pytest.mark.asyncio
async def test_canceled_long_runtime_twin_exposes_resolver_contract_boundary(
    tmp_path: Path,
) -> None:
    """The real canceled fire is addressable, but nudge is resolver-blocked before license.

    This is intentionally a narrow construction proof: it prevents a future materializer
    from claiming that an active-fire nudge can be used as a resolver-valid rejected arm
    against the distinct canceled-fire prompt.
    """
    category = PairCategory.CANCELED_FIRE_NUDGE_VS_SKIP
    bundle, template = _surface_assets(category, concept=0, surface=0)
    target, target_index, twin, twin_index = _canceled_long_programs(
        bundle, template, category=category, concept=0, surface=0
    )
    assert target.frames == twin.frames
    assert target.timing_plan == twin.timing_plan
    assert target.world_script_hash == twin.world_script_hash
    assert target.actions[:5] == twin.actions[:5]
    assert target.actions[5:] != twin.actions[5:]
    assert target_index == twin_index == 6

    target_generated = await execute_scenario(
        target,
        session_id="s_p4r_test_canceled_target",
        directory=tmp_path / "target",
        repository_root=Path(__file__).resolve().parents[1],
    )
    twin_generated = await execute_scenario(
        twin,
        session_id="s_p4r_test_canceled_active_twin",
        directory=tmp_path / "twin",
        repository_root=Path(__file__).resolve().parents[1],
    )

    target_boundary = target_generated.decision_boundaries[target_index]
    target_registry = IntentRegistry.from_state(
        target_boundary.license_view,
        target_boundary.policy_bytes,
        sha256(target_boundary.policy_bytes).hexdigest(),
    )
    assert len(target_boundary.license_view.events) == 11
    assert len(target_registry.users) + len(target_registry.fires) == 6
    target_fires = [
        (fire.alias, fire.event_id, fire.timer_status.value) for fire in target_registry.fires
    ]
    assert target_fires == [("f0", "e_000009", "canceled")]
    assert (
        resolve_policy_intent({"type": "nudge", "fire": "f0"}, target_registry).status
        is ResolutionStatus.FAILED
    )

    twin_boundary = twin_generated.decision_boundaries[twin_index]
    twin_registry = IntentRegistry.from_state(
        twin_boundary.license_view,
        twin_boundary.policy_bytes,
        sha256(twin_boundary.policy_bytes).hexdigest(),
    )
    assert 8 <= len(twin_boundary.license_view.events) <= 12
    assert (
        6
        <= sum(
            len(group)
            for group in (
                twin_registry.users,
                twin_registry.pending_facts,
                twin_registry.instructions,
                twin_registry.results,
                twin_registry.timers,
                twin_registry.fires,
            )
        )
        <= 10
    )
    assert [(fire.alias, fire.timer_status.value) for fire in twin_registry.fires] == [
        ("f0", "active")
    ]


@pytest.mark.asyncio
async def test_canceled_long_capture_allows_only_the_authorized_resolver_block() -> None:
    runtime = await _capture_runtime_surface_async(
        Path(__file__).resolve().parents[1],
        PairCategory.CANCELED_FIRE_NUDGE_VS_SKIP,
        concept=0,
        surface=0,
        stratum="long",
    )

    assert runtime.target_kind == "canceled_active_fire_long"
    assert runtime.rejected == {"type": "nudge", "fire": "f0"}
    rejected = resolve_policy_intent(runtime.rejected, runtime.registry)
    assert rejected.status is ResolutionStatus.FAILED
    assert rejected.reason == "nudge fire timer is not active"


@pytest.mark.asyncio
async def test_active_floor_long_surface_has_two_runtime_alias_kinds() -> None:
    runtime = await _capture_runtime_surface_async(
        Path(__file__).resolve().parents[1],
        PairCategory.ACTIVE_FLOOR_RESPOND_VS_IDLE,
        concept=21,
        surface=0,
        stratum="long",
    )
    assert 8 <= len(runtime.license_view.events) <= 12
    assert runtime.registry.users and runtime.registry.timers


@pytest.mark.asyncio
async def test_rollover_and_mirrored_recipes_use_captured_runtime_state() -> None:
    root = Path(__file__).resolve().parents[1]
    active = await _capture_runtime_surface_async(
        root,
        PairCategory.ACTIVE_FLOOR_RESPOND_VS_IDLE,
        concept=32,
        surface=0,
        stratum="rollover",
    )
    no_trigger = await _capture_runtime_surface_async(
        root,
        PairCategory.PURE_NO_TRIGGER_RESTRAINT,
        concept=0,
        surface=0,
        stratum="rollover",
    )
    mirrored = await _capture_runtime_surface_async(
        root,
        PairCategory.MIRRORED_POSITIVE_CONTROLS,
        concept=3,
        surface=0,
        stratum="medium",
    )

    assert active.chosen["reason"] == "awaiting_opening"
    assert no_trigger.rejected["type"] == "delegate"
    assert mirrored.chosen["type"] == "delegate"
    assert all(len(runtime.license_view.events) >= 8 for runtime in (active, no_trigger))


def test_feasibility_strata_close_exact_frozen_counts() -> None:
    counts = {}
    for stratum in _strata().values():
        counts[stratum] = counts.get(stratum, 0) + 1
    assert counts == {"medium": 39, "long": 39, "rollover": 38}


def test_all_offline_surface_labels_are_unique() -> None:
    labels = [
        _surface_label(category, concept, surface)
        for category, concept, _origin in _offline_concepts()
        for surface in range(4)
    ]
    assert len(labels) == len(set(labels)) == 464


@pytest.mark.parametrize(
    ("category", "stratum"),
    [
        (PairCategory.STALE_INTEGRATE_VS_SKIP, "medium"),
        (PairCategory.CANCELED_FIRE_NUDGE_VS_SKIP, "long"),
        (PairCategory.MIRRORED_POSITIVE_CONTROLS, "medium"),
    ],
)
def test_stock_variants_close_under_authoritative_c5_twin_contract(
    category: PairCategory, stratum: str
) -> None:
    target, _target_index, twin, _twin_index, _kind = _variant_programs(
        category, 0, 0, stratum
    )
    common = _twin_common_inputs(target, twin)
    assert common["master_seed"] == target.master_seed == twin.master_seed
    assert target.input_hash != twin.input_hash
