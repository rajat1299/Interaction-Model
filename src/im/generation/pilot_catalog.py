"""Frozen C5 pilot selections shared by review and C6 packaging."""

from __future__ import annotations

from im.assets import AssetRegistry, CorpusFamily, Split, TextAssetPayload, TimerAssetPayload
from im.generation.counterfactuals import (
    TwinAxis,
    build_lookup_triplet_programs,
    build_twin_programs,
)
from im.generation.scenario_catalog import build_family_program
from im.generation.scenarios import ScenarioProgram

C5_PILOT_SPECS = (
    (
        "c5-lookup-live",
        CorpusFamily.LOOKUP_LIVE,
        "a_f3b136f45b1b6646830c19f4",
        ("a_66d66a0cc4ccc4ed70700ca2",),
        "c5-pilot-lookup-live-v1",
    ),
    (
        "c5-timer-contention",
        CorpusFamily.TIMER_CONTENTION,
        "a_3b59764c94a070be55839190",
        ("a_52314b7d612e679be956acab", "a_7f4bb4fd0a0cc6f9bcbd10f1"),
        "c5-pilot-timer-contention-v1",
    ),
    (
        "c5-mark-negative",
        CorpusFamily.MARK_NEGATIVE,
        "a_ef1ed36384d4290e3c1f1048",
        ("a_6514bff23da1e7465cc26fd4",),
        "c5-pilot-mark-negative-v1",
    ),
    (
        "c5-rollover",
        CorpusFamily.ROLLOVER,
        "a_b2349b7ab5d479c0b04875de",
        (
            "a_52314b7d612e679be956acab",
            "a_76d6b1cf1400172aaeb06d0c",
            "a_af7454cb9fec2ce9483e9eab",
        ),
        "c5-pilot-rollover-v1",
    ),
)

_TWIN_FAMILIES = {
    TwinAxis.DIRECTNESS: CorpusFamily.MARK_POSITIVE,
    TwinAxis.LEXICAL_BOUNDARY: CorpusFamily.MARK_POSITIVE,
    TwinAxis.TOOL_LATENCY: CorpusFamily.LOOKUP_LIVE,
    TwinAxis.REQUEST_PRESENCE: CorpusFamily.LOOKUP_DUPLICATE,
    TwinAxis.TIMER_STATUS: CorpusFamily.TIMER_CANCEL,
    TwinAxis.FLOOR_STATE: CorpusFamily.TIMER_CONTENTION,
    TwinAxis.TOPIC_FRESHNESS: CorpusFamily.LOOKUP_STALE,
    TwinAxis.ROLLOVER_BOUNDARY: CorpusFamily.ROLLOVER,
}

def build_c5_pilot_programs(registry: AssetRegistry) -> tuple[tuple[str, ScenarioProgram], ...]:
    """Build the frozen four C5 pilot programs without executing them."""
    return tuple(
        (
            pilot_id,
            build_family_program(
                family,
                registry,
                split="test",
                template_id=template_id,
                asset_ids=asset_ids,
                master_seed=master_seed,
            ),
        )
        for pilot_id, family, template_id, asset_ids, master_seed in C5_PILOT_SPECS
    )


def _family_inputs(
    registry: AssetRegistry, family: CorpusFamily
) -> tuple[str, tuple[str, ...]]:
    pool = registry.pool(Split.TEST)
    selected = [next(asset for asset in pool.assets if family in asset.coverage)]
    if family in (CorpusFamily.TIMER_CONTENTION, CorpusFamily.ROLLOVER):
        selected.append(
            next(
                asset
                for asset in pool.assets
                if CorpusFamily.MARK_POSITIVE in asset.coverage
                and isinstance(asset.payload, TextAssetPayload)
            )
        )
    if family is CorpusFamily.ROLLOVER:
        selected.append(
            next(
                asset
                for asset in pool.assets
                if CorpusFamily.TIMER_NORMAL in asset.coverage
                and isinstance(asset.payload, TimerAssetPayload)
            )
        )
    template = next(item for item in pool.templates if family in item.coverage)
    return template.asset_id, tuple(asset.asset_id for asset in selected)


def build_c5_yield_audit_programs(registry: AssetRegistry) -> tuple[ScenarioProgram, ...]:
    """Build all current recipe shapes from the reviewed test pool for G-7 auditing."""
    programs = []
    for family in CorpusFamily:
        template_id, asset_ids = _family_inputs(registry, family)
        programs.append(
            build_family_program(
                family,
                registry,
                split=Split.TEST,
                template_id=template_id,
                asset_ids=asset_ids,
                master_seed=f"c6-yield-base-v1-{family.value}",
            )
        )
    for axis, family in _TWIN_FAMILIES.items():
        template_id, asset_ids = _family_inputs(registry, family)
        programs.extend(
            build_twin_programs(
                axis,
                registry,
                split=Split.TEST,
                template_id=template_id,
                asset_ids=asset_ids,
                master_seed=f"c6-yield-twin-v1-{axis.value}",
            ).programs
        )
    template_id, asset_ids = _family_inputs(registry, CorpusFamily.LOOKUP_LIVE)
    programs.extend(
        build_lookup_triplet_programs(
            registry,
            split=Split.TEST,
            template_id=template_id,
            asset_ids=asset_ids,
            master_seed="c6-yield-triplet-v1",
        ).programs
    )
    return tuple(programs)
