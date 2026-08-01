"""Gate C: the deterministic 300-state DEV allocation derived from selection-v3.

The DEV allocation is not a new contract. It is the frozen TRAIN family/action table scaled
to 300 states by the owner's stated rule: every nonzero cell keeps at least one state, and
the remaining budget is distributed by proportional largest remainder with a stable
tie-break. The response cells are pinned to the owner's exact 14 twins.
"""

from __future__ import annotations

import collections
import itertools
from collections.abc import Mapping
from hashlib import sha256
from math import floor
from pathlib import Path

from im.assets.model import (
    CorpusFamily,
    Split,
    TextAssetPayload,
    TextForm,
    TimerAssetPayload,
    TimerForm,
    canonical_artifact_bytes,
)
from im.assets.registry import AssetRegistry
from im.assets.validate import load_verified_registry_seals
from im.generation.counterfactuals import _AXIS_FAMILY, TWIN_AXIS_VALUES
from im.generation.phase2_selection import SelectionContract, load_selection_contract
from im.generation.publication import publish_directory_transaction
from im.generation.scenario_catalog import _build_selected_family_program
from im.generation.scenarios import ScenarioProgram, select_approved_scenario_inputs

_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SELECTION_CONTRACT = _ROOT / "spec" / "phase2-selection-v3.json"
DEFAULT_APPROVED_ROOT = _ROOT / "review" / "phase1" / "approved"
DEFAULT_OUTPUT = _ROOT / "review" / "phase2" / "dev-gate-c-allocation"

DEV_STATE_TOTAL = 300
DEV_RESPONSE_TWINS = 14

#: Owner semantic-alignment decision (2026-07-28). Response pairs are placed where the
#: content genuinely belongs, not where proportional scaling would put them. This adds a
#: `respond` cell to `timer_cancel_quoting_stale_fire`, which selection-v3 scores at zero,
#: and reduces `stale_result_opening_boundary` from its proportional share.
DEV_RESPOND_BY_FAMILY: dict[str, int] = {
    "live_lookup_lifecycle": 3,
    "mark_activation_positive": 1,
    "mark_lifecycle_negative": 1,
    "neutral_typing_revision_pause": 5,
    "stale_result_opening_boundary": 1,
    "timer_cancel_quoting_stale_fire": 3,
}
#: 12 active partners carry `idle(awaiting_opening)`; the 2 ambiguity-clarification partners
#: carry `idle(ambiguous)` with no related event, which is what the approved twin machinery
#: and its alignment validator already require (JN-8).
DEV_AWAITING_OPENING_TWINS = 12
DEV_AMBIGUOUS_TWINS = DEV_RESPONSE_TWINS - DEV_AWAITING_OPENING_TWINS
#: Owner: `ambiguous` totals 6, the 2 clarification partners plus 4 ordinary ambiguous states.
DEV_AMBIGUOUS_TOTAL = 6


class DevAllocationError(ValueError):
    """The DEV allocation cannot be derived from the frozen contract."""


def _largest_remainder(
    ideal: dict[tuple[str, ...], float], budget: int, *, minimum: int = 1
) -> dict[tuple[str, ...], int]:
    """Give every cell `minimum`, then hand out the rest by largest fractional part."""
    if budget < minimum * len(ideal):
        raise DevAllocationError("budget cannot give every cell its minimum")
    base = {key: max(minimum, floor(value)) for key, value in ideal.items()}
    while sum(base.values()) > budget:
        # Only reachable if flooring already overshoots; trim the smallest fractions first.
        key = min(
            (item for item in base if base[item] > minimum),
            key=lambda item: (ideal[item] - base[item], item),
        )
        base[key] -= 1
    ranked = sorted(base, key=lambda key: (-(ideal[key] - base[key]), key))
    for index in range(budget - sum(base.values())):
        base[ranked[index % len(ranked)]] += 1
    return base


def build_dev_allocation(
    *,
    contract_path: Path = DEFAULT_SELECTION_CONTRACT,
    total: int = DEV_STATE_TOTAL,
    response_twins: int = DEV_RESPONSE_TWINS,
    awaiting_opening_twins: int = DEV_AWAITING_OPENING_TWINS,
    ambiguous_total: int = DEV_AMBIGUOUS_TOTAL,
    respond_by_family: dict[str, int] | None = None,
) -> dict[str, object]:
    """Return the exact DEV family/action and idle-reason allocation."""
    contract: SelectionContract = load_selection_contract(contract_path)
    quotas = contract.family_action_quotas
    source_total = sum(sum(actions.values()) for actions in quotas.values())

    placement = dict(respond_by_family or DEV_RESPOND_BY_FAMILY)
    if sum(placement.values()) != response_twins:
        raise DevAllocationError("respond placement does not sum to the twin count")
    respond = {(family, "respond"): count for family, count in placement.items()}

    other_cells = {
        (family, action): count * total / source_total
        for family, actions in quotas.items()
        for action, count in sorted(actions.items())
        if count > 0 and action != "respond"
    }
    other = _largest_remainder(other_cells, total - response_twins)
    allocation = {**respond, **other}
    if sum(allocation.values()) != total:
        raise DevAllocationError("family/action allocation does not sum to the DEV total")

    idle_total = sum(count for (_, action), count in allocation.items() if action == "idle")
    reasons = contract.idle_reason_quotas
    reason_source = sum(reasons.values())
    pinned = response_twins if awaiting_opening_twins is None else awaiting_opening_twins
    if pinned > idle_total:
        raise DevAllocationError("pinned awaiting_opening exceeds the idle budget")
    ambiguous_partners = response_twins - pinned
    if ambiguous_total < ambiguous_partners:
        raise DevAllocationError("ambiguous budget cannot hold the clarification partners")
    free = {
        (reason,): count * idle_total / reason_source
        for reason, count in reasons.items()
        if reason not in {"awaiting_opening", "ambiguous"}
    }
    idle = {
        **{
            key[0]: value
            for key, value in _largest_remainder(
                free, idle_total - pinned - ambiguous_total
            ).items()
        },
        "awaiting_opening": pinned,
        "ambiguous": ambiguous_total,
    }
    if sum(idle.values()) != idle_total or set(idle) != set(reasons):
        raise DevAllocationError("idle-reason allocation does not close over the idle budget")

    return {
        "format_version": 1,
        "kind": "wp2-8-dev-state-allocation",
        "source_contract": contract_path.relative_to(_ROOT).as_posix(),
        "source_contract_sha256": contract.sha256,
        "source_total_decisions": source_total,
        "dev_state_total": total,
        "scale": total / source_total,
        "rule": (
            "Every nonzero family/action cell keeps at least one state; the remaining budget is "
            "distributed by proportional largest remainder, tie-broken by cell name. Response "
            "cells are placed semantically, not proportionally, and are fixed before the rest "
            "is distributed."
        ),
        "semantic_alignment_deviation": {
            "decision": "owner, 2026-07-28",
            "reason": (
                "A response pair must be placed where its content genuinely belongs. Assigning "
                "generic invitations to unrelated families purely to satisfy the proportional "
                "table would make a state's declared family unreadable from what it shows."
            ),
            "respond_by_family": placement,
            "departures_from_proportional": {
                "timer_cancel_quoting_stale_fire": (
                    "selection-v3 gives this family no respond cell at all; the DEV allocation "
                    "gives it 3, because the ambiguous-cancel clarification and both "
                    "unsupported-timer limitations are timer-cancel behaviour."
                ),
                "stale_result_opening_boundary": (
                    "proportionally 3, allocated 1: only one stale-boundary response is a "
                    "genuine late-arriving-result answer."
                ),
                "neutral_typing_revision_pause": (
                    "proportionally 4, allocated 5: the ordinary grounded answers that name no "
                    "protocol subject belong here."
                ),
                "mark_activation_positive": "proportionally 2, allocated 1.",
                "mark_lifecycle_negative": "proportionally 2, allocated 1.",
            },
            "unchanged": (
                "respond stays 14 overall, idle stays at its proportional total, and the total "
                "stays at exactly 300 states. No non-respond cell was rebalanced."
            ),
        },
        "response_twins": {
            "pairs": response_twins,
            "respond_states": response_twins,
            "active_floor_states": response_twins,
            "total_states": response_twins * 2,
            "awaiting_opening_partners": pinned,
            "ambiguous_partners": ambiguous_partners,
            "active_partner_rule": (
                "12 active partners are idle(awaiting_opening) with the requesting snapshot; the "
                "2 ambiguity-clarification partners are idle(ambiguous) with no related event. "
                "This is what g7_response_twins._build_twin already produces and what "
                "validate_response_floor_twin_alignment accepts; neither is forked."
            ),
            "payload_subtypes": {
                "ordinary_grounded": 8,
                "ambiguity_clarification": 2,
                "unsupported_feature_limitation": 2,
                "failed_tool_notice": 2,
            },
        },
        "family_action": {
            family: {
                action: allocation[(family, action)]
                for action in sorted(
                    {
                        cell_action
                        for cell_family, cell_action in allocation
                        if cell_family == family
                    }
                )
            }
            for family in sorted({cell_family for cell_family, _ in allocation})
        },
        "action_totals": {
            action: sum(
                count for (_, cell_action), count in allocation.items() if cell_action == action
            )
            for action in sorted({action for _, action in allocation})
        },
        "idle_reason": dict(sorted(idle.items())),
        "idle_total": idle_total,
    }


# --------------------------------------------------------------------------------------
# Recipe reachability against the sealed DEV pool
# --------------------------------------------------------------------------------------

_AXES_BY_FAMILY: dict[CorpusFamily, list[tuple[str, str]]] = collections.defaultdict(list)
for _axis, _family in _AXIS_FAMILY.items():
    for _value in TWIN_AXIS_VALUES[_axis]:
        _AXES_BY_FAMILY[_family].append((_axis.value, _value))


def _load_sealed_registry(approved_root: Path) -> AssetRegistry:
    registry, _ = load_verified_registry_seals(
        (approved_root / "registry.jsonl").read_bytes(),
        tuple(
            (approved_root / f"{split}-seal.json").read_bytes()
            for split in ("train", "test", "demo", "dev")
        ),
        required_splits=(Split.TRAIN, Split.TEST, Split.DEMO, Split.DEV),
    )
    return registry


def build_dev_c5_programs(
    registry: AssetRegistry,
    *,
    replicas_by_family: Mapping[CorpusFamily, int] | None = None,
) -> tuple[tuple[str, ScenarioProgram], ...]:
    """Build every shared C5 recipe reachable from the sealed DEV pool."""
    replica_counts = dict(replicas_by_family or {})
    if any(
        not isinstance(family, CorpusFamily)
        or isinstance(count, bool)
        or not isinstance(count, int)
        or count < 1
        for family, count in replica_counts.items()
    ):
        raise ValueError("DEV C5 replica counts must be positive integers by family")
    pool = registry.pool(Split.DEV)
    templates = tuple(item for item in pool.templates if registry.is_approved(item))
    atomics = tuple(item for item in pool.assets if registry.is_approved(item))
    supported = tuple(
        item
        for item in atomics
        if isinstance(item.payload, TimerAssetPayload)
        and item.payload.form is TimerForm.SUPPORTED
    )
    direct_marks = tuple(
        item
        for item in atomics
        if CorpusFamily.MARK_POSITIVE in item.coverage
        and isinstance(item.payload, TextAssetPayload)
        and item.payload.form is TextForm.DIRECT
    )

    def companions(family: CorpusFamily) -> tuple[tuple[object, ...], ...]:
        if family is CorpusFamily.TIMER_CANCEL:
            return tuple((item,) for item in supported)
        if family is CorpusFamily.TIMER_CONTENTION:
            return tuple((mark, timer) for mark in direct_marks for timer in supported)
        if family is CorpusFamily.ROLLOVER:
            return tuple(
                (mark, timer)
                for mark in direct_marks
                for timer in supported
                if timer.payload.interval_ms is not None and timer.payload.interval_ms >= 1201
            )
        return ((),)

    programs = []
    seen: set[str] = set()
    for family in CorpusFamily:
        for template, asset, extra, variant in itertools.product(
            tuple(item for item in templates if family in item.coverage),
            tuple(item for item in atomics if family in item.coverage),
            companions(family),
            (None, *_AXES_BY_FAMILY.get(family, ())),
        ):
            asset_ids = tuple(sorted({asset.asset_id, *(item.asset_id for item in extra)}))
            base_id = (
                f"c5-{family.value}-{template.asset_id}-{'-'.join(asset_ids)}-{variant}"
            )
            if base_id in seen:
                continue
            seen.add(base_id)
            for replica in range(replica_counts.get(family, 1)):
                logical_id = (
                    base_id
                    if replica_counts.get(family, 1) == 1
                    else f"{base_id}-r{replica:02d}"
                )
                try:
                    bundle, resolved = select_approved_scenario_inputs(
                        registry,
                        split=Split.DEV,
                        template_id=template.asset_id,
                        asset_ids=asset_ids,
                    )
                    program = _build_selected_family_program(
                        family,
                        bundle,
                        resolved,
                        f"wp2-8-dev:{family.value}:{template.asset_id}:"
                        f"{'-'.join(asset_ids)}:{variant}:replica:{replica}",
                        _variant=variant,
                        _natural_user_text=True,
                    )
                except (ValueError, TypeError):
                    continue
                programs.append((logical_id, program))
    return tuple(programs)


def survey_dev_recipe_reachability(
    *, approved_root: Path = DEFAULT_APPROVED_ROOT
) -> dict[str, object]:
    """Enumerate every C5 family program the sealed DEV pool can build, and what it labels.

    This answers one question only: which allocation cells the shared `scenario_catalog`
    recipes can reach from DEV assets alone, and which therefore need the G7 builders the
    TRAIN waves used. It generates nothing and approves nothing.
    """
    registry = _load_sealed_registry(approved_root)
    action_support: collections.Counter[tuple[str, str]] = collections.Counter()
    reason_support: collections.Counter[str] = collections.Counter()
    programs = build_dev_c5_programs(registry)
    for _logical_id, program in programs:
        for action in program.actions:
            action_support[(program.family.value, action.type)] += 1
            if action.type == "idle":
                reason_support[action.reason.value] += 1

    allocation = build_dev_allocation()
    family_action = allocation["family_action"]
    assert isinstance(family_action, dict)
    idle_reason = allocation["idle_reason"]
    assert isinstance(idle_reason, dict)
    unreachable_cells = [
        {"family": family, "action": action, "target_states": target}
        for family, actions in sorted(family_action.items())
        for action, target in sorted(actions.items())
        if action != "respond" and action_support[(family, action)] == 0
    ]
    unreachable_reasons = [
        {"idle_reason": reason, "target_states": target}
        for reason, target in sorted(idle_reason.items())
        if reason_support[reason] == 0
    ]
    return {
        "format_version": 1,
        "kind": "wp2-8-dev-recipe-reachability",
        "buildable_c5_programs": len(programs),
        "approved_dev_templates": sum(
            registry.is_approved(item) for item in registry.pool(Split.DEV).templates
        ),
        "approved_dev_atomics": sum(
            registry.is_approved(item) for item in registry.pool(Split.DEV).assets
        ),
        "reachable_action_cells": {
            f"{family}|{action}": count
            for (family, action), count in sorted(action_support.items())
        },
        "reachable_idle_reasons": dict(sorted(reason_support.items())),
        "cells_needing_g7_builders": unreachable_cells,
        "idle_reasons_needing_g7_builders": unreachable_reasons,
        "note": (
            "`respond` is excluded from the cell scan: it is produced by the response-floor twin "
            "builder, not by a C5 family recipe. The listed cells and reasons are reachable in "
            "TRAIN through the G7 builders (g7_catalog, g7_checkpoint_catalog, "
            "g7_rollover_checkpoint, g7_contention_checkpoint, g7_cancel_plan, g7_response_twins, "
            "g7_failed_response_twins); they must be driven with DEV inputs before the 300 states "
            "can be materialized."
        ),
    }


def build_dev_allocation_artifacts(
    *, approved_root: Path = DEFAULT_APPROVED_ROOT
) -> dict[str, bytes]:
    """Build the frozen Gate-C allocation and its reachability evidence."""
    allocation = build_dev_allocation()
    reachability = survey_dev_recipe_reachability(approved_root=approved_root)
    files = {
        "ALLOCATION.md": _allocation_markdown(allocation, reachability).encode(),
        "allocation.json": canonical_artifact_bytes(allocation),
        "recipe-reachability.json": canonical_artifact_bytes(reachability),
    }
    return {**files, "SHA256SUMS": _checksums(files)}


def materialize_dev_allocation_artifacts(
    output: Path = DEFAULT_OUTPUT, *, approved_root: Path = DEFAULT_APPROVED_ROOT
) -> None:
    publish_directory_transaction(
        output, build_dev_allocation_artifacts(approved_root=approved_root)
    )


def _allocation_markdown(
    allocation: dict[str, object], reachability: dict[str, object]
) -> str:
    family_action = allocation["family_action"]
    assert isinstance(family_action, dict)
    twins = allocation["response_twins"]
    assert isinstance(twins, dict)
    lines = [
        "# WP2-8 Gate C — the 300-state DEV allocation",
        "",
        "Status: **frozen input, states not yet generated**.",
        "",
        "## How this was derived",
        "",
        f"The frozen TRAIN table in `{allocation['source_contract']}` distributes",
        f"{allocation['source_total_decisions']} decisions. Scaling it to",
        f"{allocation['dev_state_total']} states keeps every situation the training corpus",
        "contains: each nonzero cell keeps at least one state, and the leftover budget goes to",
        "whichever cells were rounded down hardest. Response cells are pinned first, to the",
        f"owner's exact {twins['pairs']} twins.",
        "",
        "## Family and action",
        "",
        "| family | " + " | ".join(sorted(_all_actions(family_action))) + " | total |",
        "|---|" + "---:|" * (len(_all_actions(family_action)) + 1),
    ]
    for family, actions in family_action.items():
        row = [f"`{family}`"]
        row.extend(str(actions.get(action, "")) for action in sorted(_all_actions(family_action)))
        row.append(str(sum(actions.values())))
        lines.append("| " + " | ".join(row) + " |")
    totals = allocation["action_totals"]
    assert isinstance(totals, dict)
    lines.extend(
        [
            "",
            "Action totals: "
            + ", ".join(f"`{action}` {count}" for action, count in totals.items())
            + f" — {allocation['dev_state_total']} states.",
            "",
            "## Idle reasons",
            "",
            "| reason | states |",
            "|---|---:|",
        ]
    )
    idle = allocation["idle_reason"]
    assert isinstance(idle, dict)
    for reason, count in idle.items():
        lines.append(f"| `{reason}` | {count} |")
    lines.extend(
        [
            "",
            f"All seven reasons are preserved; they sum to the {allocation['idle_total']} idle",
            "states in the table above.",
            "",
            "## Response twins",
            "",
            f"{twins['pairs']} pairs, {twins['total_states']} states: each pair is the same",
            "invitation and the same approved payload seen twice, once with the floor yielded",
            "(the assistant answers) and once with the user still typing (the assistant holds).",
            f"Payload subtypes: {twins['payload_subtypes']}.",
            "",
            "## What can be built today, and what cannot",
            "",
            f"The shared C5 family recipes can build {reachability['buildable_c5_programs']}",
            "distinct programs from the sealed DEV pool. They do not reach every cell:",
            "",
        ]
    )
    cells = reachability["cells_needing_g7_builders"]
    assert isinstance(cells, list)
    for row in cells:
        lines.append(
            f"- `{row['family']}` / `{row['action']}` — {row['target_states']} states, no C5 recipe"
        )
    reasons = reachability["idle_reasons_needing_g7_builders"]
    assert isinstance(reasons, list)
    for row in reasons:
        lines.append(
            f"- idle reason `{row['idle_reason']}` — {row['target_states']} states, no C5 recipe"
        )
    lines.extend(
        [
            "",
            str(reachability["note"]),
            "",
        ]
    )
    return "\n".join(lines)


def _all_actions(family_action: dict[str, object]) -> set[str]:
    actions: set[str] = set()
    for value in family_action.values():
        assert isinstance(value, dict)
        actions.update(value)
    return actions


def _checksums(files: dict[str, bytes]) -> bytes:
    return "".join(
        f"{sha256(data).hexdigest()}  {name}\n" for name, data in sorted(files.items())
    ).encode("ascii")
