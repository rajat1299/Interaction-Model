"""WP2-10 step 3: what the sealed TEST pool can honestly build, and a 400-state allocation.

This mirrors the DEV Gate-C survey against `Split.TEST`. It deliberately does not reuse
`build_dev_c5_programs`, which pins `Split.DEV` in three places: DEV is frozen, so adding a split
parameter there would touch a shared generator that frozen artifacts depend on. The recipe logic,
companion rules, axes, and program builder are the same shared pieces the DEV survey uses.

It surveys and publishes only reachability artifacts. Full TEST-400 candidate generation and
owner-review packet publication live in `phase2_wp2_10_candidate`; neither module issues an
evaluation seal.
"""

from __future__ import annotations

import collections
import itertools
import json
from hashlib import sha256
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
from im.generation.phase2_dev_allocation import (
    _AXES_BY_FAMILY,
    DEFAULT_APPROVED_ROOT,
    DEFAULT_SELECTION_CONTRACT,
    _largest_remainder,
    _load_sealed_registry,
)
from im.generation.phase2_selection import load_selection_contract
from im.generation.publication import publish_directory_transaction
from im.generation.scenario_catalog import _build_selected_family_program
from im.generation.scenarios import (
    ScenarioProgram,
    select_approved_scenario_inputs,
)

_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT = _ROOT / "review" / "phase2" / "wp2-10-test-reachability"

TEST_STATE_TOTAL = 400
#: 90 TRAIN responses scaled from 2,000 to 400. Pinned before anything else is distributed, with a
#: matching `awaiting_opening` partner each, so every response-floor pair is complete.
TEST_RESPONSE_STATES = 18
SEED_NAMESPACE = "wp2-10-test"


class Wp210ReachabilityError(ValueError):
    """Raised when the sealed TEST pool cannot honestly support the requested allocation."""


def build_test_c5_programs(registry: AssetRegistry) -> tuple[tuple[str, ScenarioProgram], ...]:
    """Every shared C5 recipe reachable from the sealed TEST pool, TEST inputs only."""
    pool = registry.pool(Split.TEST)
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

    programs: list[tuple[str, ScenarioProgram]] = []
    seen: set[str] = set()
    rejected: collections.Counter[str] = collections.Counter()
    for family in CorpusFamily:
        for template, asset, extra, variant in itertools.product(
            tuple(item for item in templates if family in item.coverage),
            tuple(item for item in atomics if family in item.coverage),
            companions(family),
            (None, *_AXES_BY_FAMILY.get(family, ())),
        ):
            asset_ids = tuple(sorted({asset.asset_id, *(item.asset_id for item in extra)}))
            logical_id = f"c5-{family.value}-{template.asset_id}-{'-'.join(asset_ids)}-{variant}"
            if logical_id in seen:
                continue
            seen.add(logical_id)
            try:
                bundle, resolved = select_approved_scenario_inputs(
                    registry,
                    split=Split.TEST,
                    template_id=template.asset_id,
                    asset_ids=asset_ids,
                )
                program = _build_selected_family_program(
                    family,
                    bundle,
                    resolved,
                    f"{SEED_NAMESPACE}:{family.value}:{template.asset_id}:"
                    f"{'-'.join(asset_ids)}:{variant}",
                    _variant=variant,
                    _natural_user_text=True,
                )
            except (ValueError, TypeError) as error:
                rejected[type(error).__name__] += 1
                continue
            programs.append((logical_id, program))
    build_test_c5_programs.rejected = dict(rejected)  # type: ignore[attr-defined]
    return tuple(programs)


def build_test_allocation(
    *,
    contract_path: Path = DEFAULT_SELECTION_CONTRACT,
    total: int = TEST_STATE_TOTAL,
    response_states: int = TEST_RESPONSE_STATES,
) -> dict[str, object]:
    """Scale the frozen selection-v3 family/action table to `total` TEST states.

    Same rule the DEV allocation used: every nonzero cell keeps at least one state and the
    remaining budget goes by proportional largest remainder with a stable tie-break. No quota is
    relaxed and no cell is invented.
    """
    contract = load_selection_contract(contract_path)
    quotas = contract.family_action_quotas
    source_total = sum(sum(actions.values()) for actions in quotas.values())
    # `_largest_remainder` takes proportional ideals, not raw quotas: feeding it raw counts makes
    # `floor` hand a single cell its whole TRAIN quota.
    respond_source = sum(actions.get("respond", 0) for actions in quotas.values())
    respond = {
        (family, "respond"): count
        for (family, _action), count in _largest_remainder(
            {
                (family, "respond"): actions["respond"] * response_states / respond_source
                for family, actions in quotas.items()
                if actions.get("respond", 0) > 0
            },
            response_states,
        ).items()
    }
    cells: dict[tuple[str, ...], float] = {
        (family, action): count * total / source_total
        for family, actions in quotas.items()
        for action, count in sorted(actions.items())
        if count > 0 and action != "respond"
    }
    allocated = {**respond, **_largest_remainder(cells, total - response_states)}
    family_action: dict[str, dict[str, int]] = collections.defaultdict(dict)
    for (family, action), count in allocated.items():
        family_action[family][action] = count
    if sum(sum(actions.values()) for actions in family_action.values()) != total:
        raise Wp210ReachabilityError("family/action allocation does not sum to the TEST total")

    idle_total = sum(actions.get("idle", 0) for actions in family_action.values())
    reasons = contract.idle_reason_quotas
    # Every response state needs its floor partner, so `awaiting_opening` is pinned to match the
    # response count before anything else is distributed.
    if response_states > idle_total:
        raise Wp210ReachabilityError("pinned awaiting_opening exceeds the idle budget")
    free_source = sum(
        count for reason, count in reasons.items() if reason != "awaiting_opening" and count > 0
    )
    idle_reason = {
        key[0]: value
        for key, value in _largest_remainder(
            {
                (reason,): count * (idle_total - response_states) / free_source
                for reason, count in reasons.items()
                if count > 0 and reason != "awaiting_opening"
            },
            idle_total - response_states,
        ).items()
    }
    idle_reason["awaiting_opening"] = response_states
    if sum(idle_reason.values()) != idle_total:
        raise Wp210ReachabilityError("idle-reason allocation does not close over the idle budget")
    return {
        "family_action": {
            family: dict(sorted(actions.items()))
            for family, actions in sorted(family_action.items())
        },
        "action_totals": dict(
            sorted(
                collections.Counter(
                    {
                        action: sum(
                            actions.get(action, 0) for actions in family_action.values()
                        )
                        for _family, actions in family_action.items()
                        for action in actions
                    }
                ).items()
            )
        ),
        "idle_reason": dict(sorted(idle_reason.items())),
        "idle_total": idle_total,
        "source_contract": str(contract_path.relative_to(_ROOT)),
        "source_contract_sha256": "sha256:" + sha256(contract_path.read_bytes()).hexdigest(),
        "source_total_decisions": contract.target_decisions,
        "test_state_total": total,
        "response_states_pinned": response_states,
        "awaiting_opening_partners_pinned": response_states,
        "rule": (
            "Every nonzero selection-v3 family/action cell keeps at least one state; the rest is "
            "distributed by proportional largest remainder, tie-broken by cell name. No quota is "
            "relaxed and no cell is invented. Response states are pinned first at "
            f"{response_states} (90 TRAIN responses scaled 2,000 -> {total}) with a matching "
            "`awaiting_opening` partner each, so every response-floor pair is complete."
        ),
    }


def survey_test_reachability(
    *, approved_root: Path = DEFAULT_APPROVED_ROOT, total: int = TEST_STATE_TOTAL
) -> dict[str, object]:
    """Which allocation cells the sealed TEST pool can reach, and which cannot be built."""
    registry = _load_sealed_registry(approved_root)
    action_support: collections.Counter[tuple[str, str]] = collections.Counter()
    reason_support: collections.Counter[str] = collections.Counter()
    programs = build_test_c5_programs(registry)
    per_family: collections.Counter[str] = collections.Counter()
    for _logical_id, program in programs:
        per_family[program.family.value] += 1
        for action in program.actions:
            action_support[(program.family.value, action.type)] += 1
            if action.type == "idle":
                reason_support[action.reason.value] += 1

    allocation = build_test_allocation(total=total)
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
    pool = registry.pool(Split.TEST)
    return {
        "allocation": allocation,
        "approved_test_atomics": sum(registry.is_approved(item) for item in pool.assets),
        "approved_test_templates": sum(registry.is_approved(item) for item in pool.templates),
        "buildable_c5_programs": len(programs),
        "buildable_programs_by_family": dict(sorted(per_family.items())),
        "cells_needing_g7_builders": unreachable_cells,
        "format_version": 1,
        "idle_reasons_needing_g7_builders": unreachable_reasons,
        "kind": "wp2-10-test-recipe-reachability",
        "note": (
            "`respond` is excluded from the cell scan: it comes from the response-floor twin "
            "builder, not a C5 family recipe. Cells listed here are reachable in TRAIN through "
            "the G7 builders and must be driven with TEST inputs before any state is "
            "materialized. This survey builds nothing and approves nothing."
        ),
        "reachable_action_cells": {
            f"{family}|{action}": count
            for (family, action), count in sorted(action_support.items())
        },
        "reachable_idle_reasons": dict(sorted(reason_support.items())),
        "recipe_rejections": getattr(build_test_c5_programs, "rejected", {}),
        "test_state_total": total,
    }


def build_reachability_artifacts(
    *, approved_root: Path = DEFAULT_APPROVED_ROOT, total: int = TEST_STATE_TOTAL
) -> dict[str, bytes]:
    survey = survey_test_reachability(approved_root=approved_root, total=total)
    files = {
        "test-reachability.json": canonical_artifact_bytes(survey),
        "allocation.json": canonical_artifact_bytes(survey["allocation"]),
    }
    files["SHA256SUMS"] = "".join(
        f"{sha256(payload).hexdigest()}  {name}\n" for name, payload in sorted(files.items())
    ).encode()
    return files


def materialize_reachability_artifacts(
    output: Path = DEFAULT_OUTPUT,
    *,
    approved_root: Path = DEFAULT_APPROVED_ROOT,
    total: int = TEST_STATE_TOTAL,
) -> dict[str, bytes]:
    files = build_reachability_artifacts(approved_root=approved_root, total=total)
    publish_directory_transaction(output, files)
    return files


CANDIDATE_OUTPUT = _ROOT / "review" / "phase2" / "wp2-10-test-400-candidate"
GOVERNING_SEALS = (
    "registry.jsonl",
    "train-seal.json",
    "dev-seal.json",
    "test-seal.json",
    "demo-seal.json",
)


def governing_input_digests(approved_root: Path = DEFAULT_APPROVED_ROOT) -> dict[str, str]:
    """Checksum-reference the registry and all four seals the candidate is built on.

    Reproduction must not depend on unstaged Git state, so the packet carries the digests of the
    exact approved inputs rather than a branch reference.
    """
    return {
        name: "sha256:" + sha256((approved_root / name).read_bytes()).hexdigest()
        for name in GOVERNING_SEALS
    }


def build_candidate_packet(witness: dict[str, object]) -> dict[str, bytes]:
    """Checksum-bound review candidate. This is not the final evaluation seal."""
    required = {
        "row_count": 400,
        "unique_state_identities": 400,
        "cells_matching_allocation": witness.get("cells_total"),
        "respond_rows": TEST_RESPONSE_STATES,
        "awaiting_opening_rows": TEST_RESPONSE_STATES,
    }
    for key, expected in required.items():
        if witness.get(key) != expected:
            raise Wp210ReachabilityError(f"{key} is {witness.get(key)}, expected {expected}")
    if not witness.get("idle_reason_matches"):
        raise Wp210ReachabilityError("idle-reason allocation does not match")
    if witness.get("failed_response_rows"):
        raise Wp210ReachabilityError("historical failed-response streams must not be imported")
    summary = {
        "format_version": 1,
        "kind": "phase2-wp2-10-test-400-review-candidate",
        "status": "candidate_for_owner_review_not_sealed",
        "governing_inputs": witness["governing_inputs"],
        "allocation": witness["allocation"],
        "row_count": witness["row_count"],
        "unique_state_identities": witness["unique_state_identities"],
        "unique_semantic_signatures_used": witness["unique_semantic_signatures_used"],
        "max_timing_replica": witness["max_timing_replica"],
        "replica_histogram": witness["replica_histogram"],
        "ten_replica_signatures": witness["ten_replica_signatures"],
        "distinct_timing_plans": witness["distinct_timing_plans"],
        "distinct_scenario_inputs": witness["distinct_scenario_inputs"],
        "timing_seed_namespace": witness["timing_seed_namespace"],
        "asset_concentration": witness["asset_concentration"],
        "template_concentration": witness["template_concentration"],
        "builders": witness["builders"],
        "failed_response_subtype": (
            "absent from this candidate; it does not materialize under the current inputs and no "
            "historical stream was imported"
        ),
    }
    files = {
        "review-candidate.json": canonical_artifact_bytes(summary),
        "selected-states.jsonl": b"".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
            + b"\n"
            for row in witness["rows"]  # type: ignore[union-attr]
        ),
    }
    files["SHA256SUMS"] = "".join(
        f"{sha256(payload).hexdigest()}  {name}\n" for name, payload in sorted(files.items())
    ).encode()
    return files


def publish_candidate_packet(
    witness: dict[str, object], output: Path = CANDIDATE_OUTPUT
) -> dict[str, bytes]:
    files = build_candidate_packet(witness)
    publish_directory_transaction(output, files)
    return files


# The original candidate is preserved above.  This amended recipe owns its complete rebuild and
# its owner-review evidence, so no caller can supply a trusted scratch witness.
