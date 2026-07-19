"""Offline WP2-0a TRAIN asset-readiness packet generation."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

from im.assets.model import (
    AssetRecord,
    CorpusFamily,
    LookupAssetPayload,
    ReviewDecision,
    Split,
    TemplateAssetPayload,
    TextAssetPayload,
    TimerAssetPayload,
    canonical_artifact_bytes,
)
from im.assets.registry import AssetRegistry, load_registry_jsonl
from im.assets.validate import ValidationIssue, ValidationReport, validate_registry
from im.generation.g7_response_assets import ResponseDraftSpec
from im.generation.phase2_selection import SelectionContract, load_selection_contract
from im.generation.response_contracts import AnswerContract, RequiredAnswerPoint, ResponseKind

_REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_TRAIN_REGISTRY = _REPOSITORY_ROOT / "review" / "phase1" / "approved" / "registry.jsonl"
DEFAULT_SELECTION_CONTRACT = _REPOSITORY_ROOT / "spec" / "phase2-selection-v1.json"
DEFAULT_TRAIN_READINESS_OUTPUT = _REPOSITORY_ROOT / "review" / "phase2" / "train-asset-readiness"
REVIEW_SAMPLING_SEED = "wp2-0a-train-asset-review-v1-2026-07-19"

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
    """The deterministic WP2-0a packet cannot be built or verified."""


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


@dataclass(frozen=True, slots=True)
class ReviewUnit:
    role: str
    selection_class: str
    assets: tuple[AssetRecord, ...]
    structural_evidence: str | None = None
    defect_expansion: str | None = None
    semantic_stratum_asset_ids: tuple[str, ...] = ()

    @property
    def unit_id(self) -> str:
        ids = ",".join(asset.asset_id for asset in self.assets)
        return f"{self.selection_class}:{self.role}:{ids}"

    def as_json(self, asset_index: dict[str, AssetRecord]) -> dict[str, object]:
        value: dict[str, object] = {
            "unit_id": self.unit_id,
            "role": self.role,
            "selection_class": self.selection_class,
            "asset_ids": [asset.asset_id for asset in self.assets],
            "contains_template": any(
                isinstance(asset.payload, TemplateAssetPayload) for asset in self.assets
            ),
            "lookup_query_a_b_single_unit": len(self.assets) == 1
            and isinstance(self.assets[0].payload, LookupAssetPayload),
            "records": [_asset_json(asset, asset_index) for asset in self.assets],
            "owner_disposition": "pending",
        }
        if self.structural_evidence is not None:
            value["structural_evidence"] = self.structural_evidence
        if self.defect_expansion is not None:
            value["defect_expansion"] = self.defect_expansion
            value["semantic_stratum_asset_ids"] = list(self.semantic_stratum_asset_ids)
        return value


def build_train_readiness_artifacts(
    *,
    registry_path: Path = DEFAULT_TRAIN_REGISTRY,
    selection_contract_path: Path = DEFAULT_SELECTION_CONTRACT,
) -> dict[str, bytes]:
    """Build the closed review packet without changing approval or seal state."""
    registry_bytes = registry_path.read_bytes()
    registry = load_registry_jsonl(registry_bytes)
    train = registry.pool(Split.TRAIN).corpus_records
    if (
        len(train) != 89
        or sum(isinstance(asset.payload, TemplateAssetPayload) for asset in train) != 12
    ):
        raise TrainReadinessError("canonical TRAIN corpus must contain 77 atomics and 12 templates")

    asset_index = {asset.asset_id: asset for asset in train}
    status = _train_status(validate_registry(registry), train)
    contract = load_selection_contract(selection_contract_path)
    structural = _structural_units(train)
    usage = _usage_units(train, used_ids=_asset_ids(structural))
    flagged = _flagged_units(registry, train, status, _asset_ids((*structural, *usage)))
    base_units = (*structural, *usage, *flagged)
    expansion = _mark_negative_expansion(train, _asset_ids(base_units))
    units = (*base_units, expansion) if expansion is not None else base_units
    reviewed_ids = _asset_ids(units)

    response = _response_request(asset_index["a_0a86fd6dd35ddf5743c1f5c1"])
    packet = {
        "format_version": 2,
        "kind": "wp2-0a-train-asset-review-packet",
        "review_status": "pending_owner_review",
        "scope": {
            "canonical_train_corpus_records": len(train),
            "atomic_records": 77,
            "template_records": 12,
            "registry_sha256": _digest(registry_bytes),
            "selection_contract_sha256": contract.sha256,
        },
        "train_status": status.as_json(),
        "battery": {
            "validator": "im.assets.validate.validate_registry",
            "executed_on_train_record_ids": [asset.asset_id for asset in train],
            "records_checked": len(train),
            **status.as_json(),
        },
        "selection": {
            "algorithm": "fixed structural roles plus quota-weighted provisional family draws",
            "sampling_seed": REVIEW_SAMPLING_SEED,
            "structural_roles": [unit.role for unit in structural],
            "usage_families": [family.value for family in _USAGE_FAMILIES],
            "base_sample_unit_count": 18,
            "reviewed_unit_ids": [unit.unit_id for unit in units],
            "reviewed_asset_ids": list(reviewed_ids),
            "template_units": sum(
                any(isinstance(asset.payload, TemplateAssetPayload) for asset in unit.assets)
                for unit in units
            ),
            "units": [unit.as_json(asset_index) for unit in units],
        },
        "repair_expansion": {
            "defect": "MARK_NEGATIVE grammar omitted ambiguous inputs despite ambiguous seeds",
            "semantic_stratum": CorpusFamily.MARK_NEGATIVE.value,
            "semantic_stratum_asset_ids": [
                asset.asset_id for asset in train if CorpusFamily.MARK_NEGATIVE in asset.coverage
            ],
            "added_asset_ids": [] if expansion is None else [asset.asset_id for asset in expansion.assets],  # noqa: E501
            "reviewed_asset_ids_after_deduplication": [
                asset_id
                for asset_id in reviewed_ids
                if CorpusFamily.MARK_NEGATIVE in asset_index[asset_id].coverage
            ],
        },
        "owner_review": {
            "reply_format": (
                "approved|flagged|rejected <unit_id> <asset_id> <content_sha256> "
                "[brief reason for flagged/rejected]"
            ),
            "approval_boundary": "This packet is review input only; it cannot change approval or seal state.",  # noqa: E501
        },
        "pending_response_request": response,
        "non_actions": [
            "No approval record was written.",
            "No train-seal.json was written.",
            "No DEV asset, response corpus record, provider/model call, upload, or spend occurred.",
        ],
        "coverage_matrix_file": "coverage-matrix.json",
    }
    coverage = _coverage_matrix(registry, train, status, contract)
    review = _review_markdown(status, units, asset_index, response).encode()
    artifacts = {
        "REVIEW.md": review,
        "review-packet.json": canonical_artifact_bytes(packet),
        "coverage-matrix.json": canonical_artifact_bytes(coverage),
    }
    return {
        **artifacts,
        "SHA256SUMS": _checksums(artifacts),
    }


def materialize_train_readiness_artifacts(
    output: Path = DEFAULT_TRAIN_READINESS_OUTPUT,
    *,
    registry_path: Path = DEFAULT_TRAIN_REGISTRY,
    selection_contract_path: Path = DEFAULT_SELECTION_CONTRACT,
) -> None:
    """Stage sibling artifacts, verify them, then publish without overwriting evidence."""
    output = output.resolve()
    if output.exists():
        raise FileExistsError(f"TRAIN readiness output already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    artifacts = build_train_readiness_artifacts(
        registry_path=registry_path, selection_contract_path=selection_contract_path
    )
    with TemporaryDirectory(prefix=f".{output.name}-", dir=output.parent) as staging:
        staged = Path(staging)
        for name, data in artifacts.items():
            (staged / name).write_bytes(data)
        verify_train_readiness_artifacts(
            staged, registry_path=registry_path, selection_contract_path=selection_contract_path
        )
        if output.exists():
            raise FileExistsError(f"TRAIN readiness output already exists: {output}")
        staged.replace(output)


def verify_train_readiness_artifacts(
    root: Path = DEFAULT_TRAIN_READINESS_OUTPUT,
    *,
    registry_path: Path = DEFAULT_TRAIN_REGISTRY,
    selection_contract_path: Path = DEFAULT_SELECTION_CONTRACT,
) -> None:
    """Fail closed unless a packet is exactly reproducible and inventory-closed."""
    if root.is_symlink() or not root.is_dir():
        raise TrainReadinessError("TRAIN readiness output must be a real directory")
    expected = build_train_readiness_artifacts(
        registry_path=registry_path, selection_contract_path=selection_contract_path
    )
    paths = {path.name: path for path in root.iterdir()}
    if set(paths) != set(expected) or any(
        path.is_symlink() or not path.is_file() for path in paths.values()
    ):
        raise TrainReadinessError("TRAIN readiness output inventory is not closed")
    for name, data in expected.items():
        if paths[name].read_bytes() != data:
            raise TrainReadinessError(
                f"TRAIN readiness artifact differs from expected output: {name}"
            )


def _train_status(report: ValidationReport, train: tuple[AssetRecord, ...]) -> TrainStatus:
    train_ids = {asset.asset_id for asset in train}
    issues = tuple(
        issue for issue in report.issues if not issue.asset_ids or train_ids.intersection(issue.asset_ids)  # noqa: E501
    )
    return TrainStatus(
        tuple(issue for issue in issues if issue.severity.value == "error"),
        tuple(issue for issue in issues if issue.severity.value == "review"),
    )


def _structural_units(train: tuple[AssetRecord, ...]) -> tuple[ReviewUnit, ...]:
    def pick(
        role: str,
        payload_type: type[TextAssetPayload | LookupAssetPayload | TimerAssetPayload],
        family: CorpusFamily | None = None,
        form: str | None = None,
        text: str = "",
        absent: str = "",
        protected: str = "",
        evidence: str | None = None,
    ) -> ReviewUnit:
        candidates = [
            asset
            for asset in train
            if isinstance(asset.payload, payload_type)
            and (family is None or family in asset.coverage)
            and (form is None or getattr(asset.payload, "form", None).value == form)
            and (not text or text in _payload_text(asset).casefold())
            and (not absent or absent not in _payload_text(asset).casefold())
            and (not protected or protected in asset.protected_values)
        ]
        if not candidates:
            raise TrainReadinessError(f"TRAIN corpus lacks structural role: {role}")
        return ReviewUnit(role, "structural", (min(candidates, key=lambda a: _rank(role, a.asset_id)),), evidence)  # noqa: E501

    return tuple(
        pick(*spec)
        for spec in (
            ("supported_recurring_timer_instruction", TimerAssetPayload, CorpusFamily.TIMER_NORMAL, "supported"),  # noqa: E501
            ("quoted_timer_instruction", TimerAssetPayload, None, "quoted", "", "do not"),
            ("negated_or_unsupported_timer_instruction", TimerAssetPayload, None, None, "do not", "", "", "The selected quoted timer has lexical negation; TRAIN has no atomic TimerForm.NEGATED or TimerForm.UNSUPPORTED record."),  # noqa: E501
            ("partial_timer_or_control_fragment", TextAssetPayload, None, "partial"),
            ("direct_mark_control", TextAssetPayload, CorpusFamily.MARK_POSITIVE, "direct"),
            ("quoted_or_non_direct_mark_control", TextAssetPayload, CorpusFamily.MARK_NEGATIVE, "quoted"),  # noqa: E501
            ("partial_or_lexical_boundary_mark_fragment", TextAssetPayload, CorpusFamily.MARK_POSITIVE, "direct", "", "", "first-aid kit", "The selected direct mark uses the hyphenated protected target 'first-aid kit'; review lexical target boundaries."),  # noqa: E501
            ("cancel_referent_asset", TextAssetPayload, CorpusFamily.TIMER_CANCEL, "direct"),
            ("lookup_source_unit_query_and_ab", LookupAssetPayload, CorpusFamily.LOOKUP_LIVE),
        )
    )


def _usage_units(
    train: tuple[AssetRecord, ...], used_ids: tuple[str, ...]
) -> tuple[ReviewUnit, ...]:
    used = set(used_ids)
    units = []
    for family in _USAGE_FAMILIES:
        candidates = [
            asset for asset in train if family in asset.coverage and asset.asset_id not in used
        ]
        templates = [
            asset for asset in candidates if isinstance(asset.payload, TemplateAssetPayload)
        ]
        if family in _TEMPLATE_USAGE_FAMILIES and templates:
            candidates = templates
        if not candidates:
            raise TrainReadinessError(
                f"TRAIN corpus lacks a usage review source for {family.value}"
            )
        asset = min(candidates, key=lambda item: _rank(family.value, item.asset_id))
        units.append(
            ReviewUnit(f"quota_weighted_{family.value}", "quota_weighted_provisional", (asset,))
        )
        used.add(asset.asset_id)
    if sum(isinstance(unit.assets[0].payload, TemplateAssetPayload) for unit in units) < 2:
        raise TrainReadinessError("quota-weighted review must include at least two templates")
    return tuple(units)


def _payload_text(asset: AssetRecord) -> str:
    payload = asset.payload
    if isinstance(payload, TextAssetPayload):
        return payload.text
    return payload.instruction if isinstance(payload, TimerAssetPayload) else ""


def _flagged_units(
    registry: AssetRegistry,
    train: tuple[AssetRecord, ...],
    status: TrainStatus,
    used_ids: tuple[str, ...],
) -> tuple[ReviewUnit, ...]:
    train_index = {asset.asset_id: asset for asset in train}
    flagged = {
        asset_id
        for issue in status.review_flags
        for asset_id in issue.asset_ids
        if asset_id in train_index
    }
    flagged.update(
        asset.asset_id
        for asset in train
        if (review := registry.current_review(asset)) is not None
        and review.decision in {ReviewDecision.FLAGGED, ReviewDecision.REJECTED}
    )
    return tuple(
        ReviewUnit("flagged_or_unusual", "mandatory_flagged", (train_index[asset_id],))
        for asset_id in sorted(flagged - set(used_ids))
    )


def _mark_negative_expansion(
    train: tuple[AssetRecord, ...], used_ids: tuple[str, ...]
) -> ReviewUnit | None:
    stratum = tuple(asset for asset in train if CorpusFamily.MARK_NEGATIVE in asset.coverage)
    pending = tuple(asset for asset in stratum if asset.asset_id not in set(used_ids))
    if not pending:
        return None
    return ReviewUnit(
        "mark_negative_semantic_stratum",
        "mandatory_repair_expansion",
        pending,
        defect_expansion=(
            "MARK_NEGATIVE template grammar previously excluded ambiguous inputs despite ambiguous "
            "seed records. The repaired grammar names ambiguous, quoted, code, and partial forms."
        ),
        semantic_stratum_asset_ids=tuple(asset.asset_id for asset in stratum),
    )


def _response_request(support: AssetRecord) -> dict[str, object]:
    if not isinstance(support.payload, TextAssetPayload):
        raise TrainReadinessError("sentinel support asset must remain text")
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
        "required_split": "train",
        "response_kind": "ordinary_grounded",
        "invitation": draft.invitation,
        "answer_contract": draft.answer_contract.as_json_object(),
        "visible_support": {
            "asset_id": support.asset_id,
            "content_sha256": support.content_sha256,
            "text": support.payload.text,
        },
        "reply_format": "response_text <exact human-authored ordinary-grounded response>",
        "twin_binding": {
            "warrant_active": "awaiting_opening",
            "warrant_yielded": "respond",
            "payload_rule": "Both twins reuse the same eventual approved payload.",
        },
    }


def _coverage_matrix(
    registry: AssetRegistry,
    train: tuple[AssetRecord, ...],
    status: TrainStatus,
    contract: SelectionContract,
) -> dict[str, object]:
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
                "sealed_source_units": 0,
                "wave_1_target_decision_range": [
                    (sum(action_quotas.values()) + 9) // 10,
                    sum(action_quotas.values()) // 5,
                ],
                "coverage_status": _coverage_status(status),
            }
        )
    return {
        "format_version": 2,
        "kind": "wp2-0a-provisional-train-coverage-matrix",
        "status": "provisional_pending_owner_approval_and_train_seal",
        "train_status": status.as_json(),
        "selection_contract_sha256": contract.sha256,
        "mechanically_valid_train_records": len(train) if not status.errors else 0,
        "train_record_readiness": status.result,
        "train_approved_records": sum(registry.is_approved(asset) for asset in train),
        "train_seal": "absent",
        "frozen_scenario_slots": 2000,
        "response_slots": 90,
        "response_binding": {
            "status": "pending_owner_authored_train_payload",
            "approved_payloads": 0,
        },
        "global_reserve": {"minimum": 200, "target": 250, "maximum": 300},
        "families": rows,
        "tranche_2_triggers": _tranche_two_triggers(train),
        "decision": (
            "Do not build tranche 2 now. After owner approval and TRAIN sealing, trigger 3 requires "  # noqa: E501
            "targeted additions for every family still over 10% concentration."
        ),
    }


def _coverage_status(status: TrainStatus) -> str:
    return {
        "blocked": "blocked_by_train_validation",
        "review_required": "review_required",
        "pass": "mechanically_valid_but_unapproved_unsealed",
    }[status.result]


def _tranche_two_triggers(train: tuple[AssetRecord, ...]) -> list[dict[str, object]]:
    families = [family.value for family in CorpusFamily]
    return [
        {
            "trigger": 1,
            "condition": "required family or branch shape has fewer than five approved canary source units",  # noqa: E501
            "status": "pending",
            "condition_observed_now": "wave-1 has not run",
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
                "Every family has seven atomic family-covered sources. ScenarioProgram requires a "
                "family-covered asset per decision, so each family has a >=14.3% source lower bound."  # noqa: E501
            ),
            "affected_families": families,
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
                "MARK_NEGATIVE text:quoted, text:code, and text:partial each have exactly one "
                "atomic source. TIMER_CANCEL timer:quoted has two atomic sources and is not "
                "an affected subtype."
            ),
            "affected_subtypes": _thin_lexical_subtypes(train),
            "required_next_step": (
                "After approval and TRAIN sealing, add targeted distinct lexical sources for the "
                "listed MARK_NEGATIVE subtypes; do not build them now."
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


def _review_markdown(
    status: TrainStatus,
    units: tuple[ReviewUnit, ...],
    asset_index: dict[str, AssetRecord],
    response: dict[str, object],
) -> str:
    lines = [
        "# WP2-0a TRAIN asset-readiness review",
        "",
        f"Status: **pending owner review**. TRAIN battery status: **{status.result}**.",
        "",
        "Each asset below names its immutable content SHA-256.",
        "",
        "Reply once for each listed asset exactly as: `approved|flagged|rejected <unit_id> <asset_id> <content_sha256> [brief reason for flagged/rejected]`.",  # noqa: E501
        "The MARK_NEGATIVE repair expands review to its whole semantic stratum; listed records are deduplicated.",  # noqa: E501
        "",
        "## Review units",
    ]
    for unit in units:
        lines.extend(_unit_markdown(unit, asset_index))
    support = response["visible_support"]
    assert isinstance(support, dict)
    lines.extend(
        [
            "## Pending sentinel response",
            "",
            f"Invitation: `{response['invitation']}`",
            f"Support: `{support['asset_id']}` / `{support['content_sha256']}` — `{support['text']}`",  # noqa: E501
            "Reply exactly as: `response_text <one human-authored ordinary-grounded response>`.",
            "Then register, validate, and independently approve that exact TRAIN payload. Both floor twins reuse it.",  # noqa: E501
            "",
            "No provider call, upload, DEV asset, response record, approval, or `train-seal.json` was created.",  # noqa: E501
            "",
        ]
    )
    return "\n".join(lines)


def _unit_markdown(unit: ReviewUnit, asset_index: dict[str, AssetRecord]) -> list[str]:
    lines = ["", f"### `{unit.unit_id}`", "", f"Role: `{unit.role}` ({unit.selection_class})."]
    if unit.structural_evidence:
        lines.extend(["", unit.structural_evidence])
    if unit.defect_expansion:
        lines.extend(
            [
                "",
                unit.defect_expansion,
                "",
                "Full semantic stratum: "
                + ", ".join(f"`{asset_id}`" for asset_id in unit.semantic_stratum_asset_ids),
            ]
        )
    for asset in unit.assets:
        lines.extend(_asset_markdown(asset, asset_index))
    return lines


def _asset_markdown(asset: AssetRecord, asset_index: dict[str, AssetRecord]) -> list[str]:
    lines = ["", f"Asset `{asset.asset_id}` — digest `{asset.content_sha256}`."]
    payload = asset.payload
    if isinstance(payload, TextAssetPayload):
        return [*lines, f"Text ({payload.form.value}): `{_markdown_text(payload.text)}`"]
    if isinstance(payload, LookupAssetPayload):
        return [
            *lines,
            f"Query: `{_markdown_text(payload.query)}`",
            f"A: `{_markdown_text(payload.result_a)}`",
            f"B: `{_markdown_text(payload.result_b)}`",
        ]
    if isinstance(payload, TimerAssetPayload):
        return [
            *lines,
            f"Timer ({payload.form.value}): `{_markdown_text(payload.instruction)}`",
            f"interval_ms: `{payload.interval_ms}`; message: `{_markdown_text(payload.message or '')}`",  # noqa: E501
        ]
    if isinstance(payload, TemplateAssetPayload):
        return [
            *lines,
            f"expands_kind: `{payload.expands_kind.value}`",
            f"raw grammar: `{_markdown_text(payload.grammar)}`",
            "all seed IDs: " + ", ".join(f"`{seed_id}`" for seed_id in payload.seed_asset_ids),
            "representative offline rendered input:",
            "```text",
            _representative_rendered_template_input(payload, asset_index),
            "```",
        ]
    raise AssertionError(f"unhandled asset payload: {type(payload).__name__}")


def _asset_json(asset: AssetRecord, asset_index: dict[str, AssetRecord]) -> dict[str, object]:
    value: dict[str, object] = {
        "asset_id": asset.asset_id,
        "content_sha256": asset.content_sha256,
        "coverage": [family.value for family in asset.coverage],
        "kind": asset.payload.kind.value,
    }
    if isinstance(asset.payload, TemplateAssetPayload):
        value["template"] = {
            "expands_kind": asset.payload.expands_kind.value,
            "raw_grammar": asset.payload.grammar,
            "seed_asset_ids": list(asset.payload.seed_asset_ids),
            "representative_offline_rendered_input": _representative_rendered_template_input(
                asset.payload, asset_index
            ),
        }
    else:
        value["payload"] = asset.payload.model_dump(mode="json")
    return value


def _representative_rendered_template_input(
    template: TemplateAssetPayload, asset_index: dict[str, AssetRecord]
) -> str:
    seed = asset_index[template.seed_asset_ids[0]]
    return template.grammar.replace(
        "{seed}", canonical_artifact_bytes(seed.payload.model_dump(mode="json")).decode()
    )


def _thin_lexical_subtypes(train: tuple[AssetRecord, ...]) -> list[dict[str, object]]:
    expected = (
        (CorpusFamily.MARK_NEGATIVE, "text", "quoted"),
        (CorpusFamily.MARK_NEGATIVE, "text", "code"),
        (CorpusFamily.MARK_NEGATIVE, "text", "partial"),
    )
    evidence = []
    for family, kind, form in expected:
        assets = tuple(
            asset
            for asset in train
            if family in asset.coverage
            and isinstance(asset.payload, TextAssetPayload)
            and asset.payload.kind.value == kind
            and asset.payload.form.value == form
        )
        evidence.append(
            {
                "family": family.value,
                "subtype": f"{kind}:{form}",
                "atomic_source_count": len(assets),
                "asset_ids": [asset.asset_id for asset in assets],
            }
        )
    return evidence


def _asset_ids(units: tuple[ReviewUnit, ...]) -> tuple[str, ...]:
    ids = tuple(asset.asset_id for unit in units for asset in unit.assets)
    if len(set(ids)) != len(ids):
        raise TrainReadinessError("reviewed asset ids must be deduplicated")
    return ids


def _issue_json(issue: ValidationIssue) -> dict[str, object]:
    return {
        "severity": issue.severity.value,
        "code": issue.code.value,
        "asset_ids": list(issue.asset_ids),
        "detail": issue.detail,
    }


def _checksums(artifacts: dict[str, bytes]) -> bytes:
    return "".join(
        f"{sha256(data).hexdigest()}  {name}\n" for name, data in sorted(artifacts.items())
    ).encode("ascii")


def _rank(role: str, asset_id: str) -> bytes:
    return sha256(f"{REVIEW_SAMPLING_SEED}\0{role}\0{asset_id}".encode()).digest()


def _digest(data: bytes) -> str:
    return f"sha256:{sha256(data).hexdigest()}"


def _markdown_text(value: str) -> str:
    return value.replace("`", "\\`").replace("\n", "<br>")
