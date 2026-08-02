"""Deterministic review packet for the targeted WP2-2 timer TRAIN tranche."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path

from im.assets.model import (
    AssetProvenance,
    AssetRecord,
    CorpusFamily,
    Split,
    TemplateAssetPayload,
    TextAssetPayload,
    TextForm,
    TimerAssetPayload,
    TimerForm,
    canonical_artifact_bytes,
)
from im.assets.registry import AssetRegistry, load_registry_jsonl, render_registry_jsonl
from im.assets.validate import validate_registry
from im.generation.publication import publish_directory_transaction

_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_REGISTRY = _ROOT / "review" / "phase1" / "approved" / "registry.jsonl"
DEFAULT_TRAIN_SEAL = _ROOT / "review" / "phase1" / "approved" / "train-seal.json"
DEFAULT_PARTIAL_APPROVAL = _ROOT / "review" / "phase2" / "timer-tranche-2-approved-12"
DEFAULT_REPAIR_REGISTRY = DEFAULT_PARTIAL_APPROVAL / "registry.jsonl"
DEFAULT_REPAIR_TRAIN_SEAL = DEFAULT_PARTIAL_APPROVAL / "train-seal.json"
DEFAULT_INITIAL_REGISTRY = (
    _ROOT / "review" / "phase2" / "train-asset-readiness-repair-review" / "registry.jsonl"
)
DEFAULT_INITIAL_TRAIN_SEAL = (
    _ROOT / "review" / "phase2" / "train-asset-readiness-repair-review" / "train-seal.json"
)
DEFAULT_OUTPUT = _ROOT / "review" / "phase2" / "timer-tranche-2-review"
DEFAULT_REPAIR_OUTPUT = _ROOT / "review" / "phase2" / "timer-tranche-2-repair-review"
DEFAULT_OWNER_DISPOSITION = DEFAULT_OUTPUT / "OWNER-DISPOSITION.md"
DEFAULT_HELDOUT_ROOTS = (_ROOT / "probes" / "states", _ROOT / "golden", _ROOT / "review" / "phase1")
_VERSION = "phase2-timer-tranche2-v1"


def build_timer_tranche2_artifacts(
    *,
    registry_path: Path = DEFAULT_INITIAL_REGISTRY,
    train_seal_path: Path = DEFAULT_INITIAL_TRAIN_SEAL,
    heldout_roots: tuple[Path, ...] = DEFAULT_HELDOUT_ROOTS,
) -> dict[str, bytes]:
    """Build the complete offline packet without approving or sealing candidates."""
    registry_bytes = registry_path.read_bytes()
    train_seal_bytes = train_seal_path.read_bytes()
    registry = load_registry_jsonl(registry_bytes)
    candidates = timer_tranche2_candidates()
    _assert_no_frozen_overlap(candidates, heldout_roots)
    augmented = AssetRegistry(assets=(*registry.assets, *candidates), reviews=registry.reviews)
    report = validate_registry(augmented)
    candidate_ids = {asset.asset_id for asset in candidates}
    relevant_issues = tuple(
        issue for issue in report.issues if candidate_ids.intersection(issue.asset_ids)
    )
    if any(issue.severity.value == "error" for issue in relevant_issues):
        raise ValueError("timer tranche-2 candidates fail the automated asset battery")

    family_counts = {
        family.value: sum(
            asset.split is Split.TRAIN
            and family in asset.coverage
            and asset.payload.kind.value != "template"
            for asset in augmented.assets
        )
        for family in (
            CorpusFamily.TIMER_NORMAL,
            CorpusFamily.TIMER_CANCEL,
            CorpusFamily.TIMER_CONTENTION,
        )
    }
    packet = {
        "format_version": 1,
        "kind": "wp2-2-timer-targeted-tranche-2-review",
        "status": "pending_owner_review",
        "source_registry_sha256": _digest(registry_bytes),
        "source_train_seal_sha256": _digest(train_seal_bytes),
        "candidate_count": len(candidates),
        "atomic_candidate_count": sum(
            not isinstance(asset.payload, TemplateAssetPayload) for asset in candidates
        ),
        "template_candidate_count": sum(
            isinstance(asset.payload, TemplateAssetPayload) for asset in candidates
        ),
        "battery": {
            "candidate_errors": [],
            "candidate_review_flags": [
                {
                    "code": issue.code.value,
                    "asset_ids": list(issue.asset_ids),
                    "detail": issue.detail,
                }
                for issue in relevant_issues
                if issue.severity.value == "review"
            ],
        },
        "projected_atomic_source_counts": family_counts,
        "coverage_repair": {
            "timer:atomic_direct_negated": 2,
            "timer:atomic_unsupported": 2,
            "timer:ambiguous_cancel_referent": 1,
            "timer:targeted_template_support": 2,
            "concentration_floor": "at least 10 atomic sources in each timer family",
        },
        "candidates": [
            {
                **asset.model_dump(mode="json"),
                "owner_disposition": "pending",
                **_review_fields(asset, candidates),
            }
            for asset in candidates
        ],
        "approval_boundary": (
            "Review input only: this packet does not alter the registry or cumulative TRAIN seal."
        ),
        "owner_reply_format": "approved|rejected <asset_id> <content_sha256> [reason]",
    }
    candidate_registry = render_registry_jsonl(AssetRegistry(assets=candidates))
    payloads = {
        "REVIEW.md": _review(packet),
        "candidate-assets.jsonl": candidate_registry,
        "review-packet.json": canonical_artifact_bytes(packet),
    }
    checksums = "".join(
        f"{sha256(data).hexdigest()}  {name}\n" for name, data in sorted(payloads.items())
    ).encode("ascii")
    return {**payloads, "SHA256SUMS": checksums}


def materialize_timer_tranche2_packet(
    output: Path = DEFAULT_OUTPUT,
    *,
    registry_path: Path = DEFAULT_INITIAL_REGISTRY,
    train_seal_path: Path = DEFAULT_INITIAL_TRAIN_SEAL,
) -> None:
    publish_directory_transaction(
        output,
        build_timer_tranche2_artifacts(
            registry_path=registry_path,
            train_seal_path=train_seal_path,
        ),
    )


def build_timer_tranche2_repair_artifacts(
    *,
    registry_path: Path = DEFAULT_REPAIR_REGISTRY,
    train_seal_path: Path = DEFAULT_REPAIR_TRAIN_SEAL,
    owner_disposition_path: Path = DEFAULT_OWNER_DISPOSITION,
    heldout_roots: tuple[Path, ...] = DEFAULT_HELDOUT_ROOTS,
) -> dict[str, bytes]:
    """Build the one-record scoped repair packet after the 12-record partial seal."""
    registry_bytes = registry_path.read_bytes()
    seal_bytes = train_seal_path.read_bytes()
    registry = load_registry_jsonl(registry_bytes)
    repaired = next(
        asset
        for asset in timer_tranche2_candidates()
        if asset.asset_id == "a_bf812f9b9f149490915e6de0"
    )
    assert isinstance(repaired.payload, TimerAssetPayload)
    prior = next((asset for asset in registry.assets if asset.asset_id == repaired.asset_id), None)
    if prior is None or prior.content_sha256 == repaired.content_sha256:
        raise ValueError("scoped timer repair requires the prior rejected registry record")
    _assert_no_frozen_overlap((repaired,), heldout_roots)
    updated = AssetRegistry(
        assets=tuple(
            repaired if asset.asset_id == repaired.asset_id else asset for asset in registry.assets
        ),
        reviews=registry.reviews,
    )
    issues = tuple(
        issue for issue in validate_registry(updated).issues if repaired.asset_id in issue.asset_ids
    )
    if issues:
        raise ValueError("repaired one-shot timer does not pass the automated asset battery")
    packet = {
        "format_version": 1,
        "kind": "wp2-2-timer-tranche-2-scoped-repair-review",
        "status": "pending_owner_review",
        "source_registry_sha256": _digest(registry_bytes),
        "source_train_seal_sha256": _digest(seal_bytes),
        "source_owner_disposition_sha256": _digest(owner_disposition_path.read_bytes()),
        "prior_rejected_content_sha256": prior.content_sha256,
        "repaired_record": repaired.model_dump(mode="json"),
        "owner_disposition": "pending",
        "battery": {"candidate_errors": [], "candidate_review_flags": []},
        "reply_format": "approved|rejected <asset_id> <repaired_content_sha256> [reason]",
        "approval_boundary": "Review input only; registry and TRAIN seal remain unchanged.",
    }
    files = {
        "REVIEW.md": (
            "# WP2-2 timer tranche 2 scoped repair\n\n"
            "Review only this replacement for the flagged one-shot timer.\n\n"
            f"- `{repaired.asset_id}` · `{repaired.content_sha256}` · "
            f"interval_ms={repaired.payload.interval_ms} · message={repaired.payload.message!r} — "
            f"{repaired.payload.instruction}\n"
        ).encode(),
        "candidate-assets.jsonl": render_registry_jsonl(AssetRegistry(assets=(repaired,))),
        "review-packet.json": canonical_artifact_bytes(packet),
    }
    return {**files, "SHA256SUMS": _checksums(files)}


def materialize_timer_tranche2_repair_packet(
    output: Path = DEFAULT_REPAIR_OUTPUT,
    *,
    registry_path: Path = DEFAULT_REPAIR_REGISTRY,
    train_seal_path: Path = DEFAULT_REPAIR_TRAIN_SEAL,
) -> None:
    publish_directory_transaction(
        output,
        build_timer_tranche2_repair_artifacts(
            registry_path=registry_path,
            train_seal_path=train_seal_path,
        ),
    )


def timer_tranche2_candidates() -> tuple[AssetRecord, ...]:
    """Return the 11 atomic and two template candidates required before wave 1."""
    supported = (
        (
            CorpusFamily.TIMER_NORMAL,
            "normal-indigo-cup",
            "Remind me every nineteen minutes to rinse the indigo cup.",
            1_140_000,
            "rinse the indigo cup",
            "indigo cup",
        ),
        (
            CorpusFamily.TIMER_NORMAL,
            "normal-willow-ledger",
            "Remind me every forty-three minutes to index the willow ledger.",
            2_580_000,
            "index the willow ledger",
            "willow ledger",
        ),
        (
            CorpusFamily.TIMER_NORMAL,
            "normal-coral-gauge",
            "Remind me every sixty-seven minutes to check the coral gauge.",
            4_020_000,
            "check the coral gauge",
            "coral gauge",
        ),
        (
            CorpusFamily.TIMER_CONTENTION,
            "contention-cobalt-slips",
            "Remind me every seventy-one minutes to file the cobalt slips.",
            4_260_000,
            "file the cobalt slips",
            "cobalt slips",
        ),
        (
            CorpusFamily.TIMER_CONTENTION,
            "contention-canvas-map",
            "Remind me every seventy-three minutes to fold the canvas map.",
            4_380_000,
            "fold the canvas map",
            "canvas map",
        ),
        (
            CorpusFamily.TIMER_CONTENTION,
            "contention-onyx-frame",
            "Remind me every ninety-seven minutes to polish the onyx frame.",
            5_820_000,
            "polish the onyx frame",
            "onyx frame",
        ),
    )
    records = [
        _timer(family, role, instruction, TimerForm.SUPPORTED, protected, interval, message)
        for family, role, instruction, interval, message, protected in supported
    ]
    cancel_records = (
        _timer(
            CorpusFamily.TIMER_CANCEL,
            "cancel-negated-ivory-tray",
            "Do not remind me every twenty-nine minutes to rotate the ivory tray.",
            TimerForm.NEGATED,
            "ivory tray",
        ),
        _timer(
            CorpusFamily.TIMER_CANCEL,
            "cancel-negated-bronze-card",
            "Don't remind me every sixty-seven minutes to stamp the bronze card.",
            TimerForm.NEGATED,
            "bronze card",
        ),
        _timer(
            CorpusFamily.TIMER_CANCEL,
            "cancel-unsupported-lilac-case",
            "Set a single reminder forty minutes from now to close the lilac case.",
            TimerForm.UNSUPPORTED,
            "lilac case",
        ),
        _timer(
            CorpusFamily.TIMER_CANCEL,
            "cancel-unsupported-cedar-folder",
            "Remind me at 6:40 PM to carry the cedar folder.",
            TimerForm.UNSUPPORTED,
            "cedar folder",
        ),
        AssetRecord.build(
            asset_id=_asset_id("cancel-ambiguous-referent"),
            split=Split.TRAIN,
            payload=TextAssetPayload(
                text="Cancel the reminder next to it.",
                form=TextForm.AMBIGUOUS,
            ),
            provenance=AssetProvenance.SEED_AUTHORED,
            protected_values=("reminder next to it",),
            coverage=(CorpusFamily.TIMER_CANCEL,),
            rollover_eligible=False,
        ),
    )
    records.extend(cancel_records)
    negated_ids = tuple(
        sorted(
            asset.asset_id
            for asset in cancel_records
            if isinstance(asset.payload, TimerAssetPayload)
            and asset.payload.form is TimerForm.NEGATED
        )
    )
    ambiguous_id = next(
        asset.asset_id for asset in cancel_records if isinstance(asset.payload, TextAssetPayload)
    )
    records.extend(
        (
            AssetRecord.build(
                asset_id=_asset_id("cancel-negated-template"),
                split=Split.TRAIN,
                payload=TemplateAssetPayload(
                    expands_kind="timer",
                    grammar=(
                        "Use {seed} verbatim as direct user control that declines a recurring "
                        "reminder; preserve the negation and do not render it as quotation."
                    ),
                    seed_asset_ids=negated_ids,
                ),
                provenance=AssetProvenance.SEED_AUTHORED,
                protected_values=(),
                coverage=(CorpusFamily.TIMER_CANCEL,),
                rollover_eligible=False,
            ),
            AssetRecord.build(
                asset_id=_asset_id("cancel-ambiguous-template"),
                split=Split.TRAIN,
                payload=TemplateAssetPayload(
                    expands_kind="text",
                    grammar=(
                        "Use {seed} verbatim as a direct cancellation request while multiple "
                        "active reminders remain visible; preserve the unresolved referent."
                    ),
                    seed_asset_ids=(ambiguous_id,),
                ),
                provenance=AssetProvenance.SEED_AUTHORED,
                protected_values=(),
                coverage=(CorpusFamily.TIMER_CANCEL,),
                rollover_eligible=False,
            ),
        )
    )
    return tuple(sorted(records, key=lambda asset: asset.asset_id))


def _timer(
    family: CorpusFamily,
    role: str,
    instruction: str,
    form: TimerForm,
    protected: str,
    interval_ms: int | None = None,
    message: str | None = None,
) -> AssetRecord:
    return AssetRecord.build(
        asset_id=_asset_id(role),
        split=Split.TRAIN,
        payload=TimerAssetPayload(
            instruction=instruction,
            form=form,
            interval_ms=interval_ms,
            message=message,
        ),
        provenance=AssetProvenance.SEED_AUTHORED,
        protected_values=(protected,),
        coverage=(family,),
        rollover_eligible=False,
    )


def _asset_id(role: str) -> str:
    return f"a_{sha256(f'{_VERSION}\0{role}'.encode()).hexdigest()[:24]}"


def _assert_no_frozen_overlap(candidates: tuple[AssetRecord, ...], roots: tuple[Path, ...]) -> None:
    needles = {
        value.encode("utf-8"): asset.asset_id
        for asset in candidates
        if not isinstance(asset.payload, TemplateAssetPayload)
        for value in (
            *asset.protected_values,
            *(
                (asset.payload.text,)
                if isinstance(asset.payload, TextAssetPayload)
                else (asset.payload.instruction,)
            ),
        )
    }
    stems = {
        stem.encode("utf-8"): asset.asset_id
        for asset in candidates
        if isinstance(asset.payload, TimerAssetPayload)
        and asset.payload.form is TimerForm.UNSUPPORTED
        and (stem := _instruction_stem(asset.payload.instruction)) is not None
    }
    for root in roots:
        if not root.is_dir():
            raise ValueError(f"heldout overlap root is missing: {root}")
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            data = _heldout_bytes(path)
            for needle, asset_id in needles.items():
                if needle in data:
                    raise ValueError(
                        f"timer tranche-2 candidate {asset_id} overlaps frozen material at {path}"
                    )
            for stem, asset_id in stems.items():
                if stem in data:
                    raise ValueError(
                        f"timer tranche-2 candidate {asset_id} repeats a frozen instruction "
                        f"frame at {path}"
                    )


def _instruction_stem(instruction: str) -> str | None:
    marker = " to "
    before, found, _ = instruction.partition(marker)
    return f"{before}{marker}" if found and len(before) >= 20 else None


def _heldout_bytes(path: Path) -> bytes:
    data = path.read_bytes()
    if path.resolve() != DEFAULT_REGISTRY.resolve():
        return data
    registry = load_registry_jsonl(data)
    heldout = tuple(asset for asset in registry.assets if asset.split in (Split.TEST, Split.DEMO))
    return render_registry_jsonl(AssetRegistry(assets=heldout))


def _review_fields(asset: AssetRecord, candidates: tuple[AssetRecord, ...]) -> dict[str, object]:
    if not isinstance(asset.payload, TemplateAssetPayload):
        return {}
    by_id = {candidate.asset_id: candidate for candidate in candidates}
    seed = by_id[asset.payload.seed_asset_ids[0]].payload
    if isinstance(seed, TextAssetPayload):
        expansion = seed.text
    else:
        assert isinstance(seed, TimerAssetPayload)
        expansion = seed.instruction
    return {"representative_expansion": expansion}


def _review(packet: dict[str, object]) -> bytes:
    candidates = packet["candidates"]
    assert isinstance(candidates, list)
    lines = [
        "# WP2-2 targeted timer TRAIN tranche 2",
        "",
        "Review all 13 candidates (11 atomic records and two narrow templates).",
        "This packet does not approve or seal anything.",
        "It repairs the timer concentration and missing direct-negated/unsupported boundaries",
        "required before wave 1; it does not add DEV assets or a new provenance process.",
        "",
        "Reply once per row as `approved|rejected <asset_id> <content_sha256> [reason]`.",
        "",
    ]
    for item in candidates:
        assert isinstance(item, dict)
        payload = item["payload"]
        assert isinstance(payload, dict)
        text = payload.get("instruction", payload.get("text", payload.get("grammar")))
        subtype = (
            f"{payload['kind']}:{payload['form']}"
            if "form" in payload
            else f"template->{payload['expands_kind']}"
        )
        detail = ""
        if payload["kind"] == "timer":
            detail = f" · interval_ms={payload['interval_ms']} · message={payload['message']!r}"
        elif payload["kind"] == "template":
            detail = f" · representative expansion: {item['representative_expansion']}"
        lines.append(
            f"- `{item['asset_id']}` · `{item['content_sha256']}` · "
            f"`{item['coverage'][0]}` / `{subtype}`{detail} — {text}"
        )
    return ("\n".join(lines) + "\n").encode()


def _digest(data: bytes) -> str:
    return f"sha256:{sha256(data).hexdigest()}"


def _checksums(files: dict[str, bytes]) -> bytes:
    return "".join(
        f"{sha256(data).hexdigest()}  {name}\n" for name, data in sorted(files.items())
    ).encode("ascii")
