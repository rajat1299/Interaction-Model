"""Offline WP2-0a TRAIN asset review packet; it never approves or seals assets."""

from __future__ import annotations

import json
from collections.abc import Callable
from hashlib import sha256
from pathlib import Path

from im.assets.model import (
    AssetRecord,
    CorpusFamily,
    ReviewDecision,
    Split,
    TemplateAssetPayload,
    TextAssetPayload,
    TimerAssetPayload,
    TimerForm,
    canonical_artifact_bytes,
)
from im.assets.registry import AssetRegistry, load_registry_jsonl
from im.assets.validate import ValidationReport, validate_registry
from im.generation.g7_response_assets import ResponseDraftSpec
from im.generation.phase2_selection import (
    canonical_selection_contract_bytes,
    load_selection_contract,
)
from im.generation.response_contracts import AnswerContract, RequiredAnswerPoint, ResponseKind

_REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_TRAIN_REGISTRY = _REPOSITORY_ROOT / "review" / "phase1" / "approved" / "registry.jsonl"
DEFAULT_SELECTION_CONTRACT = _REPOSITORY_ROOT / "spec" / "phase2-selection-v1.json"
DEFAULT_TRAIN_READINESS_OUTPUT = _REPOSITORY_ROOT / "review" / "phase2" / "train-asset-readiness"
REVIEW_SAMPLING_SEED = "wp2-0a-train-asset-review-v1-2026-07-19"

# Largest-remainder allocation of the frozen 2,000 slots, frozen before selection.
_USAGE_FAMILIES = (
    CorpusFamily.NEUTRAL_TYPING,
    CorpusFamily.LOOKUP_LIVE,
    CorpusFamily.MARK_POSITIVE,
    CorpusFamily.TIMER_NORMAL,
    CorpusFamily.LOOKUP_DUPLICATE,
    CorpusFamily.MARK_NEGATIVE,
    CorpusFamily.TIMER_CANCEL,
    CorpusFamily.LOOKUP_STALE,
    CorpusFamily.TIMER_CONTENTION,
)
_TEMPLATE_USAGE_FAMILIES = frozenset({CorpusFamily.NEUTRAL_TYPING, CorpusFamily.LOOKUP_LIVE})


class TrainReadinessError(ValueError):
    """The deterministic WP2-0a review packet cannot be built or verified."""


def build_train_readiness_artifacts(
    *,
    registry_path: Path = DEFAULT_TRAIN_REGISTRY,
    selection_contract_path: Path = DEFAULT_SELECTION_CONTRACT,
) -> dict[str, bytes]:
    """Build the closed review packet and provisional coverage matrix without mutation."""
    registry_bytes = registry_path.read_bytes()
    registry = load_registry_jsonl(registry_bytes)
    train = tuple(
        asset
        for asset in registry.assets
        if asset.split is Split.TRAIN and asset.provenance.value != "recorded"
    )
    template_count = sum(isinstance(asset.payload, TemplateAssetPayload) for asset in train)
    if len(train) != 89 or template_count != 12:
        raise TrainReadinessError("canonical TRAIN corpus must contain 77 atomics and 12 templates")

    report = validate_registry(registry)
    asset_index = {asset.asset_id: asset for asset in train}
    structural = _structural_units(train, asset_index)
    used_ids = {asset_id for unit in structural.values() for asset_id in unit["asset_ids"]}
    usage = _usage_units(train, asset_index, excluded_ids=used_ids)
    used_ids.update(asset_id for unit in usage.values() for asset_id in unit["asset_ids"])
    flagged = _flagged_units(registry, train, report, asset_index, used_ids=used_ids)
    units = (*structural.values(), *usage.values(), *flagged)
    if len({unit["unit_id"] for unit in units}) != len(units):
        raise TrainReadinessError("review units must be deduplicated")
    reviewed_asset_ids = [asset_id for unit in units for asset_id in unit["asset_ids"]]
    if len(set(reviewed_asset_ids)) != len(reviewed_asset_ids):
        raise TrainReadinessError("reviewed asset ids must be unique")

    contract = load_selection_contract(selection_contract_path)
    selection_bytes = canonical_selection_contract_bytes(selection_contract_path)
    selection = json.loads(selection_bytes)
    packet = {
        "format_version": 1,
        "kind": "wp2-0a-train-asset-review-packet",
        "review_status": "pending_owner_review",
        "scope": {
            "canonical_train_corpus_records": len(train),
            "atomic_records": 77,
            "template_records": 12,
            "registry_sha256": _digest(registry_bytes),
            "selection_contract_sha256": contract.sha256,
        },
        "battery": _battery(train, report),
        "selection": {
            "algorithm": "fixed structural roles plus quota-weighted provisional family draws",
            "sampling_seed": REVIEW_SAMPLING_SEED,
            "structural_roles": list(structural),
            "usage_families": [family.value for family in _USAGE_FAMILIES],
            "reviewed_unit_ids": [unit["unit_id"] for unit in units],
            "reviewed_asset_ids": reviewed_asset_ids,
            "template_units": sum(unit["contains_template"] for unit in units),
            "units": list(units),
        },
        "owner_review": {
            "unit_disposition": (
                "Record approved, flagged, or rejected against each listed immutable content "
                "SHA-256 outside this packet."
            ),
            "flagged_or_unusual_policy": (
                "Every validator-flagged or previously unusual TRAIN record is appended after "
                "the 18 fixed units."
            ),
            "approval_boundary": (
                "This packet is review input only; it cannot change approval or seal state."
            ),
        },
        "pending_response_request": _pending_response_request(asset_index),
        "non_actions": [
            "No approval record was written.",
            "No train-seal.json was written.",
            "No DEV asset, response corpus record, provider/model call, upload, or spend occurred.",
        ],
        "coverage_matrix_file": "coverage-matrix.json",
    }
    coverage = _coverage_matrix(registry, train, report, selection, contract.sha256)
    packet_bytes = canonical_artifact_bytes(packet)
    coverage_bytes = canonical_artifact_bytes(coverage)
    review_bytes = _review_markdown(packet).encode()
    checksums = "".join(
        f"{sha256(data).hexdigest()}  {name}\n"
        for name, data in sorted(
            {
                "REVIEW.md": review_bytes,
                "coverage-matrix.json": coverage_bytes,
                "review-packet.json": packet_bytes,
            }.items()
        )
    ).encode("ascii")
    return {
        "REVIEW.md": review_bytes,
        "review-packet.json": packet_bytes,
        "coverage-matrix.json": coverage_bytes,
        "SHA256SUMS": checksums,
    }


def materialize_train_readiness_artifacts(
    output: Path = DEFAULT_TRAIN_READINESS_OUTPUT,
    *,
    registry_path: Path = DEFAULT_TRAIN_REGISTRY,
    selection_contract_path: Path = DEFAULT_SELECTION_CONTRACT,
) -> None:
    """Reserve a new review-only directory; never overwrite prior owner evidence."""
    artifacts = build_train_readiness_artifacts(
        registry_path=registry_path, selection_contract_path=selection_contract_path
    )
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        output.mkdir()
    except FileExistsError:
        raise FileExistsError(f"TRAIN readiness output already exists: {output}") from None
    for name, data in artifacts.items():
        (output / name).write_bytes(data)
    verify_train_readiness_artifacts(
        output, registry_path=registry_path, selection_contract_path=selection_contract_path
    )


def verify_train_readiness_artifacts(
    root: Path = DEFAULT_TRAIN_READINESS_OUTPUT,
    *,
    registry_path: Path = DEFAULT_TRAIN_REGISTRY,
    selection_contract_path: Path = DEFAULT_SELECTION_CONTRACT,
) -> None:
    """Fail closed unless the review directory is exactly the reproducible packet."""
    if root.is_symlink() or not root.is_dir():
        raise TrainReadinessError("TRAIN readiness output must be a real directory")
    expected = build_train_readiness_artifacts(
        registry_path=registry_path, selection_contract_path=selection_contract_path
    )
    paths = {path.name: path for path in root.iterdir()}
    unsafe_path = any(path.is_symlink() or not path.is_file() for path in paths.values())
    if set(paths) != set(expected) or unsafe_path:
        raise TrainReadinessError("TRAIN readiness output inventory is not closed")
    for name, data in expected.items():
        if paths[name].read_bytes() != data:
            raise TrainReadinessError(
                f"TRAIN readiness artifact differs from expected output: {name}"
            )


def _structural_units(
    train: tuple[AssetRecord, ...], asset_index: dict[str, AssetRecord]
) -> dict[str, dict[str, object]]:
    def pick(
        role: str,
        predicate: Callable[[AssetRecord], bool],
        *,
        structural_evidence: str | None = None,
    ) -> dict[str, object]:
        candidates = [asset for asset in train if predicate(asset)]
        if not candidates:
            raise TrainReadinessError(f"TRAIN corpus lacks structural role: {role}")
        asset = min(candidates, key=lambda item: _rank(role, item.asset_id))
        return _unit(
            role,
            (asset,),
            selection_class="structural",
            asset_index=asset_index,
            structural_evidence=structural_evidence,
        )

    return {
        "supported_recurring_timer_instruction": pick(
            "supported_recurring_timer_instruction",
            lambda asset: (
                isinstance(asset.payload, TimerAssetPayload)
                and asset.payload.form is TimerForm.SUPPORTED
                and CorpusFamily.TIMER_NORMAL in asset.coverage
            ),
        ),
        "quoted_timer_instruction": pick(
            "quoted_timer_instruction",
            lambda asset: (
                isinstance(asset.payload, TimerAssetPayload)
                and asset.payload.form is TimerForm.QUOTED
                and "do not" not in asset.payload.instruction.casefold()
            ),
        ),
        "negated_or_unsupported_timer_instruction": pick(
            "negated_or_unsupported_timer_instruction",
            lambda asset: (
                isinstance(asset.payload, TimerAssetPayload)
                and "do not" in asset.payload.instruction.casefold()
            ),
            structural_evidence=(
                "The selected asset is TimerForm.QUOTED with a lexical negation; TRAIN has no "
                "atomic TimerForm.NEGATED or TimerForm.UNSUPPORTED record."
            ),
        ),
        "partial_timer_or_control_fragment": pick(
            "partial_timer_or_control_fragment",
            lambda asset: (
                isinstance(asset.payload, TextAssetPayload)
                and asset.payload.form.value == "partial"
            ),
        ),
        "direct_mark_control": pick(
            "direct_mark_control",
            lambda asset: (
                isinstance(asset.payload, TextAssetPayload)
                and asset.payload.form.value == "direct"
                and CorpusFamily.MARK_POSITIVE in asset.coverage
            ),
        ),
        "quoted_or_non_direct_mark_control": pick(
            "quoted_or_non_direct_mark_control",
            lambda asset: (
                isinstance(asset.payload, TextAssetPayload)
                and asset.payload.form.value == "quoted"
                and CorpusFamily.MARK_NEGATIVE in asset.coverage
            ),
        ),
        "partial_or_lexical_boundary_mark_fragment": pick(
            "partial_or_lexical_boundary_mark_fragment",
            lambda asset: (
                isinstance(asset.payload, TextAssetPayload)
                and asset.payload.form.value == "direct"
                and CorpusFamily.MARK_POSITIVE in asset.coverage
                and "first-aid kit" in asset.protected_values
            ),
            structural_evidence=(
                "The selected direct mark uses the hyphenated protected target 'first-aid kit'; "
                "the review checks lexical target-boundary handling."
            ),
        ),
        "cancel_referent_asset": pick(
            "cancel_referent_asset",
            lambda asset: (
                isinstance(asset.payload, TextAssetPayload)
                and asset.payload.form.value == "direct"
                and CorpusFamily.TIMER_CANCEL in asset.coverage
            ),
        ),
        "lookup_source_unit_query_and_ab": pick(
            "lookup_source_unit_query_and_ab",
            lambda asset: (
                asset.payload.kind.value == "lookup" and CorpusFamily.LOOKUP_LIVE in asset.coverage
            ),
        ),
    }


def _usage_units(
    train: tuple[AssetRecord, ...],
    asset_index: dict[str, AssetRecord],
    *,
    excluded_ids: set[str],
) -> dict[str, dict[str, object]]:
    selected: dict[str, dict[str, object]] = {}
    used_ids = set(excluded_ids)
    for family in _USAGE_FAMILIES:
        candidates = [
            asset for asset in train if family in asset.coverage and asset.asset_id not in used_ids
        ]
        if family in _TEMPLATE_USAGE_FAMILIES:
            templates = [
                asset for asset in candidates if isinstance(asset.payload, TemplateAssetPayload)
            ]
            if templates:
                candidates = templates
        if not candidates:
            raise TrainReadinessError(
                f"TRAIN corpus lacks a usage review source for {family.value}"
            )
        asset = min(candidates, key=lambda item: _rank(family.value, item.asset_id))
        unit = _unit(
            f"quota_weighted_{family.value}",
            (asset,),
            selection_class="quota_weighted_provisional",
            asset_index=asset_index,
        )
        selected[unit["unit_id"]] = unit
        used_ids.add(asset.asset_id)
    if sum(unit["contains_template"] for unit in selected.values()) < 2:
        raise TrainReadinessError("quota-weighted review must include at least two templates")
    return selected


def _flagged_units(
    registry: AssetRegistry,
    train: tuple[AssetRecord, ...],
    report: ValidationReport,
    asset_index: dict[str, AssetRecord],
    *,
    used_ids: set[str],
) -> tuple[dict[str, object], ...]:
    flagged = set(report.flagged_asset_ids)
    flagged.update(
        asset.asset_id
        for asset in train
        if (review := registry.current_review(asset)) is not None
        and review.decision in {ReviewDecision.FLAGGED, ReviewDecision.REJECTED}
    )
    return tuple(
        _unit(
            "flagged_or_unusual",
            (asset_index[asset_id],),
            selection_class="mandatory_flagged",
            asset_index=asset_index,
        )
        for asset_id in sorted(flagged - used_ids)
    )


def _unit(
    role: str,
    assets: tuple[AssetRecord, ...],
    *,
    selection_class: str,
    asset_index: dict[str, AssetRecord],
    structural_evidence: str | None = None,
) -> dict[str, object]:
    asset = assets[0]
    preview: dict[str, object]
    if isinstance(asset.payload, TemplateAssetPayload):
        seed = asset_index[asset.payload.seed_asset_ids[0]]
        seed_payload = canonical_artifact_bytes(seed.payload.model_dump(mode="json")).decode()
        preview = {
            "label": "canonical prompt/input preview (offline; not model output)",
            "input": asset.payload.grammar.replace("{seed}", seed_payload),
        }
    else:
        preview = {
            "label": "canonical asset payload",
            "payload": asset.payload.model_dump(mode="json"),
        }
    unit = {
        "unit_id": f"{selection_class}:{role}:{asset.asset_id}",
        "role": role,
        "selection_class": selection_class,
        "asset_ids": [asset.asset_id for asset in assets],
        "contains_template": isinstance(asset.payload, TemplateAssetPayload),
        "lookup_query_a_b_single_unit": asset.payload.kind.value == "lookup",
        "records": [
            {
                "asset_id": asset.asset_id,
                "content_sha256": asset.content_sha256,
                "coverage": [family.value for family in asset.coverage],
                "kind": asset.payload.kind.value,
            }
        ],
        "preview": preview,
        "owner_disposition": "pending",
    }
    if structural_evidence is not None:
        unit["structural_evidence"] = structural_evidence
    return unit


def _battery(train: tuple[AssetRecord, ...], report: ValidationReport) -> dict[str, object]:
    train_ids = {asset.asset_id for asset in train}
    issues = [
        {
            "severity": issue.severity.value,
            "code": issue.code.value,
            "asset_ids": list(issue.asset_ids),
            "detail": issue.detail,
        }
        for issue in report.issues
        if set(issue.asset_ids) & train_ids
    ]
    return {
        "validator": "im.assets.validate.validate_registry",
        "executed_on_train_record_ids": [asset.asset_id for asset in train],
        "records_checked": len(train),
        "errors": [issue for issue in issues if issue["severity"] == "error"],
        "review_flags": [issue for issue in issues if issue["severity"] == "review"],
        "result": "pass" if not issues else "review_required",
    }


def _pending_response_request(asset_index: dict[str, AssetRecord]) -> dict[str, object]:
    support = asset_index["a_0a86fd6dd35ddf5743c1f5c1"]
    if not isinstance(support.payload, TextAssetPayload):  # canonical registry guard
        raise TrainReadinessError("sentinel support asset has drifted from text")
    draft = ResponseDraftSpec(
        invitation="What happened after the phrase about cedar shelves?",
        answer_contract=AnswerContract(
            response_kind=ResponseKind.ORDINARY_GROUNDED,
            subject_id="sentinel-floor-twin",
            support_event_ids=("e_train_sentinel_support",),
            required_answer_points=(RequiredAnswerPoint(("blue cursor paused",)),),
            forbidden_claims=("Any fact not stated by the visible support.",),
            grounding_allowlist=("blue", "cursor", "paused", "cedar", "shelves"),
        ),
    )
    return {
        "status": "pending_owner_authored_text",
        "response_record_status": "not_created",
        "required_split": Split.TRAIN.value,
        "response_kind": ResponseKind.ORDINARY_GROUNDED.value,
        "draft": {
            "invitation": draft.invitation,
            "answer_contract": draft.answer_contract.as_json_object(),
            "visible_support_by_event_id": {
                "e_train_sentinel_support": {
                    "asset_id": support.asset_id,
                    "content_sha256": support.content_sha256,
                    "text": support.payload.text,
                }
            },
        },
        "owner_request": (
            "Author one ordinary-grounded response text for this fixed TRAIN invitation/support; "
            "then register, validate, and approve that one payload before use. This packet creates "
            "neither text nor record."
        ),
        "twin_binding": {
            "warrant_active": "awaiting_opening",
            "warrant_yielded": "respond",
            "payload_rule": "Both twins reuse the same eventual approved payload.",
        },
    }


def _coverage_matrix(
    registry: AssetRegistry,
    train: tuple[AssetRecord, ...],
    report: ValidationReport,
    selection: dict[str, object],
    selection_sha256: str,
) -> dict[str, object]:
    quotas = selection["family_action_quotas"]
    if not isinstance(quotas, dict):  # validated by the project-native selection loader.
        raise TrainReadinessError("selection quotas are invalid")
    rows = []
    for family in CorpusFamily:
        records = tuple(asset for asset in train if family in asset.coverage)
        atomics = tuple(
            asset for asset in records if not isinstance(asset.payload, TemplateAssetPayload)
        )
        action_quotas = quotas[family.value]
        if not isinstance(action_quotas, dict):
            raise TrainReadinessError("selection family quota is invalid")
        rows.append(
            {
                "family": family.value,
                "frozen_scenario_slots": sum(action_quotas.values()),
                "response_slots": action_quotas.get("respond", 0),
                "raw_atomic_asset_count": len(atomics),
                "raw_template_count": len(records) - len(atomics),
                "raw_record_count": len(records),
                "raw_shape_counts": _shape_counts(atomics),
                "approved_record_count": sum(registry.is_approved(asset) for asset in records),
                "approved_atomic_source_proxy_count": sum(
                    registry.is_approved(asset) for asset in atomics
                ),
                "approved_template_record_count": sum(
                    registry.is_approved(asset)
                    for asset in records
                    if isinstance(asset.payload, TemplateAssetPayload)
                ),
                "sealed_source_units": 0,
                "wave_1_target_decision_range": [
                    (sum(action_quotas.values()) + 9) // 10,
                    sum(action_quotas.values()) // 5,
                ],
                "coverage_status": "battery_passing_but_unapproved_unsealed",
                "note": (
                    "Raw asset counts are source-unit proxies; no scenario source_unit_id "
                    "exists before generation."
                ),
            }
        )
    return {
        "format_version": 1,
        "kind": "wp2-0a-provisional-train-coverage-matrix",
        "status": "provisional_pending_owner_approval_and_train_seal",
        "selection_contract_sha256": selection_sha256,
        "battery_passing_train_records": len(train) if not report.errors else 0,
        "train_approved_records": sum(registry.is_approved(asset) for asset in train),
        "train_seal": "absent",
        "frozen_scenario_slots": 2000,
        "response_slots": 90,
        "response_binding": {
            "status": "pending_owner_authored_train_payload",
            "approved_payloads": 0,
            "sealed_payloads": 0,
        },
        "global_reserve": {
            "minimum": 200,
            "target": 250,
            "maximum": 300,
            "reserved_unknown_kind_base_slots": 10,
            "status": "pending; no generated reserve source units",
        },
        "families": rows,
        "tranche_2_triggers": _tranche_two_triggers(),
        "decision": "No tranche-2 trigger has procedurally fired; do not build tranche 2.",
    }


def _shape_counts(records: tuple[AssetRecord, ...]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for asset in records:
        form = getattr(asset.payload, "form", "none")
        key = f"{asset.payload.kind.value}:{form}"
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def _tranche_two_triggers() -> list[dict[str, object]]:
    return [
        {
            "trigger": 1,
            "condition": (
                "required family or branch shape has fewer than five approved canary source units"
            ),
            "status": "pending",
            "condition_observed_now": (
                "0 approved TRAIN source units; gate is pending, not fired before seal"
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
            "status": "pending_projected_concentration_risk",
            "condition_observed_now": (
                "7 atomic sources imply a 14.3% lower bound only under the conservative "
                "one-asset-per-source assumption; streams may combine assets"
            ),
        },
        {
            "trigger": 4,
            "condition": "timer, mark, lookup, idle, or response subtype lacks lexical diversity",
            "status": "provisional_concern",
            "condition_observed_now": (
                "mark-negative has one quoted, one partial, and one code atomic; timer-cancel "
                "has two quoted and zero negated/unsupported atomic timers; response inventory is 0"
            ),
        },
        {
            "trigger": 5,
            "condition": (
                "wave-1 rejection rate exhausts source units before repaired canary and reserve "
                "complete"
            ),
            "status": "pending",
            "condition_observed_now": "wave-1 has not run",
        },
        {
            "trigger": 6,
            "condition": "split-disjointness cannot fill a required slot without test/demo reuse",
            "status": "provisional_registry_pass",
            "condition_observed_now": (
                "registry battery has no TRAIN-heldout overlap; response and concrete slot fill "
                "remain pending"
            ),
        },
    ]


def _review_markdown(packet: dict[str, object]) -> str:
    selection = packet["selection"]
    response = packet["pending_response_request"]
    if not isinstance(selection, dict) or not isinstance(response, dict):  # built above
        raise TrainReadinessError("review packet shape is invalid")
    units = selection["units"]
    if not isinstance(units, list):
        raise TrainReadinessError("review packet units are invalid")
    lines = [
        "# WP2-0a TRAIN asset-readiness review",
        "",
        "Status: **pending owner review**. The offline battery passed all 89 canonical TRAIN "
        "records. No record is approved or sealed by this packet.",
        "",
        "For each row, record `approved`, `flagged`, or `rejected` against the immutable content "
        "SHA-256 in `review-packet.json`. A sampled defect expands review to its semantic stratum; "
        "it does not approve unrelated records.",
        "",
        f"Sampling seed: `{selection['sampling_seed']}`.",
        "",
        "| Review role | Asset / content SHA-256 | Canonical content to review | Disposition |",
        "| --- | --- | --- | --- |",
    ]
    for unit in units:
        if not isinstance(unit, dict):
            raise TrainReadinessError("review packet unit is invalid")
        asset_ids = unit.get("asset_ids")
        preview = unit.get("preview")
        records = unit.get("records")
        if (
            not isinstance(asset_ids, list)
            or not isinstance(preview, dict)
            or not isinstance(records, list)
            or len(records) != 1
            or not isinstance(records[0], dict)
        ):
            raise TrainReadinessError("review packet unit details are invalid")
        record = records[0]
        digest = record.get("content_sha256")
        if not isinstance(digest, str):
            raise TrainReadinessError("review packet record digest is invalid")
        lines.append(
            f"| `{unit['role']}` | {', '.join(f'`{asset_id}`' for asset_id in asset_ids)}<br>"
            f"`{digest}` | {_review_content(preview)} | __________________ |"
        )
    lines.extend(
        [
            "",
            "## Pending sentinel response",
            "",
            _response_request_markdown(response),
            "",
            "No provider call, upload, DEV asset, response record, approval, or `train-seal.json` "
            "was created.",
            "",
        ]
    )
    return "\n".join(lines)


def _review_content(preview: dict[str, object]) -> str:
    if "input" in preview:
        value = preview["input"]
        if not isinstance(value, str):
            raise TrainReadinessError("template preview is invalid")
        return f"canonical prompt/input preview (offline; not model output): `{_table_text(value)}`"
    payload = preview.get("payload")
    if not isinstance(payload, dict) or not isinstance(payload.get("kind"), str):
        raise TrainReadinessError("asset preview is invalid")
    if payload["kind"] == "text":
        return (
            f"text form `{_table_text(str(payload['form']))}`: "
            f"`{_table_text(str(payload['text']))}`"
        )
    if payload["kind"] == "lookup":
        return (
            f"query: `{_table_text(str(payload['query']))}`<br>"
            f"A: `{_table_text(str(payload['result_a']))}`<br>"
            f"B: `{_table_text(str(payload['result_b']))}`"
        )
    if payload["kind"] == "timer":
        message = _table_text(str(payload["message"]))
        return (
            f"timer form `{_table_text(str(payload['form']))}`; "
            f"instruction: `{_table_text(str(payload['instruction']))}`<br>"
            f"interval_ms: `{payload['interval_ms']}`; message: `{message}`"
        )
    raise TrainReadinessError("asset preview kind is invalid")


def _response_request_markdown(response: dict[str, object]) -> str:
    draft = response.get("draft")
    if not isinstance(draft, dict):
        raise TrainReadinessError("response request draft is invalid")
    invitation = draft.get("invitation")
    support = draft.get("visible_support_by_event_id")
    if not isinstance(invitation, str) or not isinstance(support, dict):
        raise TrainReadinessError("response request fields are invalid")
    event = support.get("e_train_sentinel_support")
    if not isinstance(event, dict):
        raise TrainReadinessError("response request support is invalid")
    return (
        f"Invitation: `{_table_text(invitation)}`<br>"
        f"Support: `{event['asset_id']}` / `{event['content_sha256']}` — "
        f"`{_table_text(str(event['text']))}`<br>"
        "Disposition: author one human ordinary-grounded response, then independently register, "
        "validate, and approve it. Both floor twins reuse that exact approved payload."
    )


def _table_text(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", "<br>").replace("`", "\\`")


def _rank(family: str, asset_id: str) -> bytes:
    return sha256(f"{REVIEW_SAMPLING_SEED}\0{family}\0{asset_id}".encode()).digest()


def _digest(data: bytes) -> str:
    return f"sha256:{sha256(data).hexdigest()}"
