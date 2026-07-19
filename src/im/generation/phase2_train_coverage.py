"""Cohesive TRAIN coverage accounting and tranche-trigger evidence."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from im.assets.model import (
    AssetRecord,
    CorpusFamily,
    Split,
    SplitSeal,
    TemplateAssetPayload,
    TextAssetPayload,
    TimerAssetPayload,
)
from im.assets.registry import AssetRegistry
from im.assets.validate import (
    ValidationIssue,
    ValidationReport,
    validate_registry,
    verify_split_seal,
)
from im.generation.g7_response_assets import HumanAuthoredResponseAsset
from im.generation.phase2_selection import SelectionContract

__all__ = ("TrainCoverageError", "TrainStatus", "build_train_coverage_matrix", "train_status")


class TrainCoverageError(ValueError):
    """TRAIN coverage inputs cannot be validated."""


@dataclass(frozen=True, slots=True)
class TrainStatus:
    errors: tuple[ValidationIssue, ...]
    review_flags: tuple[ValidationIssue, ...]

    @property
    def result(self) -> str:
        if self.errors:
            return "blocked"
        return "review_required" if self.review_flags else "pass"

    def as_json(self) -> dict[str, object]:
        return {
            "result": self.result,
            "errors": [_issue_json(issue) for issue in self.errors],
            "review_flags": [_issue_json(issue) for issue in self.review_flags],
        }


def train_status(report: ValidationReport, train: tuple[AssetRecord, ...]) -> TrainStatus:
    """Restrict registry validation findings to the TRAIN corpus."""
    train_ids = {asset.asset_id for asset in train}
    issues = tuple(
        issue
        for issue in report.issues
        if not issue.asset_ids or train_ids.intersection(issue.asset_ids)
    )
    return TrainStatus(
        tuple(issue for issue in issues if issue.severity.value == "error"),
        tuple(issue for issue in issues if issue.severity.value == "review"),
    )


def build_train_coverage_matrix(
    registry: AssetRegistry,
    contract: SelectionContract,
    *,
    train_seal: SplitSeal | None = None,
    response_asset: HumanAuthoredResponseAsset | None = None,
) -> dict[str, object]:
    """Report current TRAIN inventory, approvals, seal membership, and D14 triggers."""
    if train_seal is not None:
        if train_seal.split is not Split.TRAIN:
            raise TrainCoverageError("coverage matrix requires a TRAIN seal")
        verify_split_seal(registry, train_seal)
    if response_asset is not None and not isinstance(response_asset, HumanAuthoredResponseAsset):
        raise TypeError("response_asset must be a HumanAuthoredResponseAsset or None")
    approved_response_count = int(response_asset is not None)
    train = registry.pool(Split.TRAIN).corpus_records
    status = train_status(validate_registry(registry), train)
    sealed_ids = (
        frozenset()
        if train_seal is None
        else frozenset(entry.asset_id for entry in train_seal.entries)
    )
    rows = []
    for family in CorpusFamily:
        records = tuple(asset for asset in train if family in asset.coverage)
        atomics = tuple(
            asset for asset in records if not isinstance(asset.payload, TemplateAssetPayload)
        )
        action_quotas = contract.family_action_quotas[family.value]
        rows.append(
            {
                "family": family.value,
                "frozen_scenario_slots": sum(action_quotas.values()),
                "response_slots": action_quotas.get("respond", 0),
                "raw_atomic_asset_count": len(atomics),
                "raw_template_count": len(records) - len(atomics),
                "raw_shape_counts": dict(
                    sorted(
                        Counter(
                            f"{asset.payload.kind.value}:{getattr(asset.payload, 'form', 'none')}"
                            for asset in atomics
                        ).items()
                    )
                ),
                "approved_record_count": sum(registry.is_approved(asset) for asset in records),
                "sealed_source_units": sum(asset.asset_id in sealed_ids for asset in records),
                "wave_1_target_decision_range": [
                    (sum(action_quotas.values()) + 9) // 10,
                    sum(action_quotas.values()) // 5,
                ],
                "coverage_status": (
                    _coverage_status(status)
                    if train_seal is None
                    else "partially_sealed"
                    if any(asset.asset_id in sealed_ids for asset in records)
                    else "unsealed"
                ),
            }
        )
    return {
        "format_version": 2,
        "kind": (
            "wp2-0a-provisional-train-coverage-matrix"
            if train_seal is None
            else "wp2-0a-train-coverage-matrix"
        ),
        "status": (
            "provisional_pending_owner_approval_and_train_seal"
            if train_seal is None
            else "partial_train_seal_pending_scoped_re_review"
        ),
        "train_status": status.as_json(),
        "selection_contract_sha256": contract.sha256,
        "mechanically_valid_train_records": len(train) if not status.errors else 0,
        "train_record_readiness": status.result,
        "train_approved_records": sum(registry.is_approved(asset) for asset in train),
        "train_seal": (
            "absent"
            if train_seal is None
            else {
                "entry_count": len(train_seal.entries),
                "pool_sha256": train_seal.pool_sha256,
            }
        ),
        "frozen_scenario_slots": 2000,
        "response_slots": 90,
        "response_binding": {
            "status": (
                "pending_owner_authored_train_payload"
                if approved_response_count == 0
                else "approved_human_authored_train_payload"
            ),
            "approved_payloads": approved_response_count,
        },
        "global_reserve": {"minimum": 200, "target": 250, "maximum": 300},
        "families": rows,
        "tranche_2_triggers": _tranche_two_triggers(
            train,
            sealed_ids=sealed_ids if train_seal is not None else None,
            response_asset=response_asset,
        ),
        "decision": (
            "Do not build tranche 2 now."
            if train_seal is None
            else (
                "Keep the five repaired records pending scoped re-review; do not build tranche "
                "2 now."
            )
        ),
    }


def _coverage_status(status: TrainStatus) -> str:
    return {
        "blocked": "blocked_by_train_validation",
        "review_required": "review_required",
        "pass": "mechanically_valid_but_unapproved_unsealed",
    }[status.result]


def _tranche_two_triggers(
    train: tuple[AssetRecord, ...],
    *,
    sealed_ids: frozenset[str] | None = None,
    response_asset: HumanAuthoredResponseAsset | None = None,
) -> list[dict[str, object]]:
    families = [family.value for family in CorpusFamily]
    approved_by_family = (
        {
            family.value: sum(
                asset.asset_id in sealed_ids for asset in train if family in asset.coverage
            )
            for family in CorpusFamily
        }
        if sealed_ids is not None
        else {}
    )
    concentration_families = (
        [
            family.value
            for family in CorpusFamily
            if 0
            < sum(
                asset.asset_id in sealed_ids
                for asset in train
                if family in asset.coverage and not isinstance(asset.payload, TemplateAssetPayload)
            )
            < 10
        ]
        if sealed_ids is not None
        else families
    )
    required_subtypes = _required_lexical_subtypes(
        train,
        eligible_ids=sealed_ids,
        response_asset=response_asset,
    )
    affected_subtypes = [
        evidence for evidence in required_subtypes if evidence["atomic_source_count"] < 2
    ]
    pending_review_subtypes = [
        evidence["subtype"]
        for evidence in affected_subtypes
        if evidence["atomic_source_count"] < evidence["raw_atomic_source_count"]
    ]
    targeted_subtypes = [
        evidence["subtype"]
        for evidence in affected_subtypes
        if evidence["raw_atomic_source_count"] < 2
    ]
    return [
        {
            "trigger": 1,
            "condition": "required family or branch shape has fewer than five approved canary source units",  # noqa: E501
            "status": (
                "pending" if sealed_ids is None else "fired_approved_canary_source_shortfall"
            ),
            "condition_observed_now": (
                "owner approval has not been applied"
                if sealed_ids is None
                else "Every required family currently has fewer than five sealed source units."
            ),
            **(
                {}
                if sealed_ids is None
                else {
                    "approved_source_units_by_family": approved_by_family,
                    "affected_families": [
                        family for family, count in approved_by_family.items() if count < 5
                    ],
                }
            ),
        },
        {
            "trigger": 2,
            "condition": "quota plus reserve requires duplicate raw identities",
            "status": "pending",
            "condition_observed_now": "no generated whole streams or reserve allocation",
        },
        {
            "trigger": 3,
            "condition": "one asset exceeds about 10% of accepted family decisions",
            "status": "fired_current_inventory_concentration",
            "condition_observed_now": (
                "Every family has seven raw atomic family-covered sources, implying a >=14.3% "
                "raw-source lower bound."
                if sealed_ids is None
                else (
                    "Every family with at least one sealed atomic source has fewer than ten, so "
                    "one source must exceed 10%."
                )
            ),
            "affected_families": concentration_families,
            "required_next_step": (
                "After approval and TRAIN sealing, add targeted sources for each family still above "  # noqa: E501
                "10%; do not build them now."
            ),
        },
        {
            "trigger": 4,
            "condition": "timer, mark, lookup, idle, or response subtype lacks lexical diversity",
            "status": "fired_current_inventory_lexical_diversity",
            "condition_observed_now": (
                (
                    "MARK_NEGATIVE direct-stop has two raw sources; direct-replacement, genuinely "
                    "ambiguous, quoted, code, and partial have one each. TIMER_CANCEL quoted has "
                    "two; atomic direct-negated and unsupported timers have zero."
                )
                if sealed_ids is None
                else (
                    "The repaired direct-stop and direct-replacement sources are pending scoped "
                    "review. Sealed coverage has one each for genuine ambiguity, quoted, code, "
                    "partial, and the ordinary-grounded response; direct-negated and unsupported "
                    "timers remain absent."
                )
            ),
            "required_subtype_evidence": required_subtypes,
            "affected_subtypes": affected_subtypes,
            "pending_scoped_review_subtypes": pending_review_subtypes,
            "targeted_after_scoped_review": targeted_subtypes,
            "required_next_step": (
                "After approval and TRAIN sealing, add targeted distinct lexical sources for the "
                "listed thin or absent subtypes, including genuinely ambiguous mark controls and "
                "atomic direct-negated/unsupported timers; do not build them now."
            ),
        },
        {
            "trigger": 5,
            "condition": "wave-1 rejection rate exhausts source units before repaired canary and reserve complete",  # noqa: E501
            "status": "pending",
            "condition_observed_now": "wave-1 has not run",
        },
        {
            "trigger": 6,
            "condition": "split-disjointness cannot fill a required slot without test/demo reuse",
            "status": "provisional_registry_pass",
            "condition_observed_now": "TRAIN registry battery has no heldout overlap; concrete slot fill remains pending.",  # noqa: E501
        },
    ]


def _required_lexical_subtypes(
    train: tuple[AssetRecord, ...],
    *,
    eligible_ids: frozenset[str] | None = None,
    response_asset: HumanAuthoredResponseAsset | None = None,
) -> list[dict[str, object]]:
    mark_records = tuple(
        asset
        for asset in train
        if CorpusFamily.MARK_NEGATIVE in asset.coverage
        and isinstance(asset.payload, TextAssetPayload)
    )
    timer_records = tuple(
        asset
        for asset in train
        if CorpusFamily.TIMER_CANCEL in asset.coverage
        and isinstance(asset.payload, TimerAssetPayload)
    )

    def mark(form: str, prefix: str = "") -> tuple[AssetRecord, ...]:
        return tuple(
            asset
            for asset in mark_records
            if asset.payload.form.value == form
            and (not prefix or asset.payload.text.casefold().startswith(prefix))
        )

    def timer(form: str) -> tuple[AssetRecord, ...]:
        return tuple(asset for asset in timer_records if asset.payload.form.value == form)

    evidence = (
        ("mark:direct_stop", mark("direct", "stop marking ")),
        ("mark:direct_replacement", mark("direct", "switch from ")),
        ("mark:genuinely_ambiguous", mark("ambiguous")),
        ("mark:quoted", mark("quoted")),
        ("mark:code", mark("code")),
        ("mark:partial", mark("partial")),
        ("timer:quoted", timer("quoted")),
        ("timer:atomic_direct_negated", timer("negated")),
        ("timer:atomic_unsupported", timer("unsupported")),
    )
    rows = [
        {
            "subtype": subtype,
            "atomic_source_count": sum(
                eligible_ids is None or asset.asset_id in eligible_ids for asset in assets
            ),
            "asset_ids": [
                asset.asset_id
                for asset in assets
                if eligible_ids is None or asset.asset_id in eligible_ids
            ],
            "raw_atomic_source_count": len(assets),
        }
        for subtype, assets in evidence
    ]
    approved_response_count = int(response_asset is not None)
    rows.append(
        {
            "subtype": "response:ordinary_grounded",
            "atomic_source_count": approved_response_count,
            "asset_ids": [],
            "raw_atomic_source_count": approved_response_count,
        }
    )
    return rows


def _issue_json(issue: ValidationIssue) -> dict[str, object]:
    return {
        "severity": issue.severity.value,
        "code": issue.code.value,
        "asset_ids": list(issue.asset_ids),
        "detail": issue.detail,
    }
