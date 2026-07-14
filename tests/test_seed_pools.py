"""Seed-pool data stays split-safe and awaits external held-out review."""

from __future__ import annotations

from math import ceil, floor

import pytest

from im.assets import (
    AssetKind,
    AssetProvenance,
    AssetRecord,
    AssetRegistry,
    AssetValidationError,
    CorpusFamily,
    LookupAssetPayload,
    ReviewDecision,
    ReviewRecord,
    Split,
    TemplateAssetPayload,
    TextAssetPayload,
    TextForm,
    TimerAssetPayload,
    TimerForm,
    create_split_seal,
    load_registry_jsonl,
    load_verified_registry_seals,
    render_registry_jsonl,
    render_split_seal_json,
    select_template_review_assets,
    verify_split_seal,
)
from im.assets.seeds import build_seed_pools
from im.assets.validate import select_review_assets, validate_registry


def _approved_heldout_reviews(registry: AssetRegistry) -> tuple[ReviewRecord, ...]:
    return tuple(
        ReviewRecord(
            asset_id=asset.asset_id,
            content_sha256=asset.content_sha256,
            reviewer_id="phase1-human-reviewer",
            reviewed_at_utc="2026-07-14T12:00:00Z",
            decision=ReviewDecision.APPROVED,
        )
        for split in (Split.TEST, Split.DEMO)
        for asset in registry.pool(split).corpus_records
    )


def test_seed_pool_covers_each_family_with_split_scoped_atomic_assets_and_templates() -> None:
    registry = build_seed_pools().registry
    records_by_id = {asset.asset_id: asset for asset in registry.assets}

    for family in CorpusFamily:
        atomic = tuple(
            asset
            for asset in registry.assets
            if asset.coverage == (family,) and not isinstance(asset.payload, TemplateAssetPayload)
        )
        assert len(atomic) == 10
        assert all(asset.provenance.value == "seed_authored" for asset in atomic)

        templates = tuple(
            asset
            for asset in registry.assets
            if asset.coverage == (family,) and isinstance(asset.payload, TemplateAssetPayload)
        )
        assert all(asset.coverage == (family,) for asset in templates)
        for split in Split:
            split_atomic = tuple(asset for asset in atomic if asset.split is split)
            split_templates = tuple(asset for asset in templates if asset.split is split)
            assert {asset.payload.expands_kind for asset in split_templates} == {
                asset.payload.kind for asset in split_atomic
            }
            for template in split_templates:
                assert template.payload.seed_asset_ids
                assert all(
                    records_by_id[seed_id].split is split
                    and records_by_id[seed_id].coverage == (family,)
                    and records_by_id[seed_id].payload.kind is template.payload.expands_kind
                    for seed_id in template.payload.seed_asset_ids
                )


def test_seed_payloads_have_real_mark_and_timer_depth() -> None:
    registry = build_seed_pools().registry
    atomic = tuple(
        asset for asset in registry.assets if not isinstance(asset.payload, TemplateAssetPayload)
    )
    protected = [value.casefold() for asset in atomic for value in asset.protected_values]
    lookups = [asset.payload for asset in atomic if isinstance(asset.payload, LookupAssetPayload)]
    train_mark_positive = tuple(
        asset
        for asset in registry.pool(Split.TRAIN).assets
        if asset.coverage == (CorpusFamily.MARK_POSITIVE,)
    )
    train_mark_negative = tuple(
        asset
        for asset in registry.pool(Split.TRAIN).assets
        if asset.coverage == (CorpusFamily.MARK_NEGATIVE,)
    )

    assert len(protected) == len(set(protected))
    assert all(
        payload.result_a != payload.result_b and payload.no_result_code for payload in lookups
    )
    positive_text = "\n".join(asset.payload.text for asset in train_mark_positive)
    assert all(
        target in positive_text
        for target in (
            "amber kiwi",
            "filler words um and you know",
            "category Harbor Signal as active",
            "cobalt axolotl as a new amphibian member",
            "17 October 2031",
            "Dr. Imani Voss",
            "first-aid kit",
        )
    )
    negative_text = "\n".join(asset.payload.text for asset in train_mark_negative).casefold()
    assert "stop" in negative_text and "switch" in negative_text
    assert {TextForm.QUOTED, TextForm.CODE, TextForm.PARTIAL} <= {
        asset.payload.form for asset in train_mark_negative
    }

    timer_cancel_kinds = {
        split: {
            asset.payload.kind
            for asset in registry.pool(split).assets
            if asset.coverage == (CorpusFamily.TIMER_CANCEL,)
        }
        for split in Split
    }
    assert timer_cancel_kinds == {
        Split.TRAIN: {AssetKind.TEXT, AssetKind.TIMER},
        Split.DEV: {AssetKind.TEXT},
        Split.TEST: {AssetKind.TIMER},
        Split.DEMO: {AssetKind.TEXT},
    }
    assert {
        asset.payload.form
        for asset in registry.pool(Split.TRAIN).assets
        if asset.coverage == (CorpusFamily.TIMER_CANCEL,)
        and isinstance(asset.payload, TimerAssetPayload)
    } == {TimerForm.QUOTED}


def test_seed_pool_is_validation_clean_and_train_review_is_within_the_ratified_band() -> None:
    registry = build_seed_pools().registry
    report = validate_registry(registry)
    train_atomic = {
        asset.asset_id
        for asset in registry.pool(Split.TRAIN).assets
        if not isinstance(asset.payload, TemplateAssetPayload)
    }
    selected = set(select_review_assets(registry, report))
    train_selected = selected & train_atomic
    template_ids = set(select_template_review_assets(registry))
    selected_timer_cancel_kinds = {
        asset.payload.kind
        for asset in registry.pool(Split.TRAIN).assets
        if asset.asset_id in train_selected and asset.coverage == (CorpusFamily.TIMER_CANCEL,)
    }

    assert not report.errors
    assert not report.review_flags
    assert len(train_atomic) == 77
    assert ceil(len(train_atomic) * 0.10) <= len(train_selected) <= floor(len(train_atomic) * 0.20)
    assert selected_timer_cancel_kinds == {AssetKind.TEXT, AssetKind.TIMER}
    assert not selected & template_ids
    assert len(template_ids) == 45


def test_seed_pools_await_external_heldout_reviews_before_sealing() -> None:
    pending = build_seed_pools()
    rendered = render_registry_jsonl(pending.registry)

    assert pending.pending_review_splits == (Split.TEST, Split.DEMO)
    assert not pending.registry.reviews
    assert render_registry_jsonl(build_seed_pools().registry) == rendered
    assert render_registry_jsonl(load_registry_jsonl(rendered)) == rendered
    for split in pending.pending_review_splits:
        with pytest.raises(AssetValidationError, match="cannot seal unapproved assets"):
            create_split_seal(pending.registry, split)

    reviewed = AssetRegistry(
        assets=pending.registry.assets,
        reviews=_approved_heldout_reviews(pending.registry),
    )
    seals = tuple(create_split_seal(reviewed, split) for split in pending.pending_review_splits)
    restored, persisted_seals = load_verified_registry_seals(
        render_registry_jsonl(reviewed),
        tuple(render_split_seal_json(seal) for seal in seals),
    )
    assert persisted_seals == seals
    for seal in persisted_seals:
        verify_split_seal(restored, seal)


def test_persisted_review_evidence_requires_complete_current_canonical_seals() -> None:
    pending = build_seed_pools().registry
    reviewed = AssetRegistry(
        assets=pending.assets,
        reviews=_approved_heldout_reviews(pending),
    )
    seals = tuple(create_split_seal(reviewed, split) for split in (Split.TEST, Split.DEMO))
    seal_jsons = tuple(render_split_seal_json(seal) for seal in seals)
    registry_jsonl = render_registry_jsonl(reviewed)

    for incomplete in ((), seal_jsons[:1]):
        with pytest.raises(AssetValidationError, match="required splits"):
            load_verified_registry_seals(registry_jsonl, incomplete)
    with pytest.raises(AssetValidationError, match="duplicate split seal"):
        load_verified_registry_seals(registry_jsonl, (*seal_jsons, seal_jsons[0]))
    with pytest.raises(AssetValidationError, match="not canonical"):
        load_verified_registry_seals(registry_jsonl, (seal_jsons[0] + b"\n", seal_jsons[1]))

    added = AssetRecord.build(
        asset_id="a_test_new_seal_member",
        split=Split.TEST,
        payload=TextAssetPayload(
            text="A new seal member carries a cobalt rook token.",
            form=TextForm.NEUTRAL,
        ),
        provenance=AssetProvenance.SEED_AUTHORED,
        protected_values=("cobalt rook token",),
        coverage=(CorpusFamily.NEUTRAL_TYPING,),
    )
    updated = AssetRegistry(
        assets=(*reviewed.assets, added),
        reviews=(
            *reviewed.reviews,
            ReviewRecord(
                asset_id=added.asset_id,
                content_sha256=added.content_sha256,
                reviewer_id="phase1-human-reviewer",
                reviewed_at_utc="2026-07-14T12:01:00Z",
                decision=ReviewDecision.APPROVED,
            ),
        ),
    )
    with pytest.raises(AssetValidationError, match="membership or content digest"):
        load_verified_registry_seals(render_registry_jsonl(updated), seal_jsons)
