from __future__ import annotations

from hashlib import sha256

import pytest

from im.assets import (
    AssetKind,
    AssetRecord,
    ReviewDecision,
    ReviewRecord,
    Split,
    TextAssetPayload,
    TextForm,
    TimerAssetPayload,
    TimerForm,
    create_split_seal,
)
from im.assets.expansion import AssetExpansionError, ExpansionRequest, import_expanded_asset
from im.assets.registry import AssetRegistry
from im.assets.seeds import build_seed_pools


def _template(registry: AssetRegistry, split: Split, kind: AssetKind) -> AssetRecord:
    return next(
        asset for asset in registry.pool(split).templates if asset.payload.expands_kind is kind
    )


def _request(
    template: AssetRecord,
    *,
    asset_id: str,
    payload: TextAssetPayload | TimerAssetPayload,
) -> ExpansionRequest:
    return ExpansionRequest(
        asset_id=asset_id,
        template_asset_id=template.asset_id,
        seed_asset_ids=(template.payload.seed_asset_ids[0],),
        payload=payload,
        generation_model="neutral-model/revision",
        source_bytes=b"validated model import request",
        protected_values=("expanded revision",),
    )


def test_expansion_returns_a_validated_registry_with_computed_source_digest() -> None:
    registry = build_seed_pools().registry
    template = _template(registry, Split.TRAIN, AssetKind.TEXT)
    source_bytes = b"validated model import request"
    request = _request(
        template,
        asset_id="a_train_expansion_output",
        payload=TextAssetPayload(
            text="A new neutral expansion restates the carefully separated idea.",
            form=TextForm.NEUTRAL,
        ),
    )

    updated = import_expanded_asset(registry, request)
    expanded = next(asset for asset in updated.assets if asset.asset_id == request.asset_id)

    assert len(updated.assets) == len(registry.assets) + 1
    assert expanded.split is Split.TRAIN
    assert expanded.coverage == template.coverage
    assert expanded.template_asset_id == template.asset_id
    assert expanded.source_digest == f"sha256:{sha256(source_bytes).hexdigest()}"


def test_expansion_rejects_unknown_template_wrong_kind_and_unselected_seed() -> None:
    registry = build_seed_pools().registry
    template = _template(registry, Split.TRAIN, AssetKind.TEXT)
    timer = TimerAssetPayload(
        instruction="Remind me every minute to stretch.",
        form=TimerForm.SUPPORTED,
        interval_ms=60_000,
        message="stretch",
    )

    with pytest.raises(AssetExpansionError, match="does not exist"):
        import_expanded_asset(
            registry,
            ExpansionRequest(
                asset_id="a_train_unknown_template",
                template_asset_id="a_train_missing_template",
                seed_asset_ids=(template.payload.seed_asset_ids[0],),
                payload=timer,
                generation_model="neutral-model/revision",
                source_bytes=b"unknown template",
            ),
        )
    with pytest.raises(AssetExpansionError, match="kind"):
        import_expanded_asset(
            registry,
            _request(template, asset_id="a_train_wrong_kind", payload=timer),
        )
    with pytest.raises(AssetExpansionError, match="preselect"):
        import_expanded_asset(
            registry,
            ExpansionRequest(
                asset_id="a_train_wrong_seed",
                template_asset_id=template.asset_id,
                seed_asset_ids=("a_train_missing_seed",),
                payload=TextAssetPayload(text="A distinct expansion.", form=TextForm.NEUTRAL),
                generation_model="neutral-model/revision",
                source_bytes=b"unknown seed",
            ),
        )
    with pytest.raises(AssetExpansionError, match="protected values"):
        import_expanded_asset(
            registry,
            ExpansionRequest(
                asset_id="a_train_missing_protected_values",
                template_asset_id=template.asset_id,
                seed_asset_ids=(template.payload.seed_asset_ids[0],),
                payload=TextAssetPayload(text="A distinct expansion.", form=TextForm.NEUTRAL),
                generation_model="neutral-model/revision",
                source_bytes=b"missing protected values",
            ),
        )


def test_expansion_cannot_reword_a_heldout_protected_phrase_without_declaring_it() -> None:
    registry = build_seed_pools().registry
    template = _template(registry, Split.TRAIN, AssetKind.TEXT)
    request = _request(
        template,
        asset_id="a_train_hidden_heldout_phrase",
        payload=TextAssetPayload(
            text="The revised paragraph quietly relocates the SILVER  BOOKMARK.",
            form=TextForm.NEUTRAL,
        ),
    )

    assert "silver bookmark" not in request.protected_values
    with pytest.raises(AssetExpansionError, match="fails registry validation"):
        import_expanded_asset(registry, request)


def test_expansion_refuses_a_valid_frozen_split() -> None:
    pending = build_seed_pools().registry
    reviews = tuple(
        ReviewRecord(
            asset_id=asset.asset_id,
            content_sha256=asset.content_sha256,
            reviewer_id="phase1-human-reviewer",
            reviewed_at_utc="2026-07-14T12:00:00Z",
            decision=ReviewDecision.APPROVED,
        )
        for asset in pending.pool(Split.TEST).corpus_records
    )
    registry = AssetRegistry(assets=pending.assets, reviews=reviews)
    seal = create_split_seal(registry, Split.TEST)
    template = _template(registry, Split.TEST, AssetKind.TIMER)
    request = _request(
        template,
        asset_id="a_test_expansion_output",
        payload=TimerAssetPayload(
            instruction="Remind me every ninety-seven minutes to revise the ledger.",
            form=TimerForm.SUPPORTED,
            interval_ms=5_820_000,
            message="revise the ledger",
        ),
    )

    with pytest.raises(AssetExpansionError, match="held-out split"):
        import_expanded_asset(registry, request)
    with pytest.raises(AssetExpansionError, match="cannot expand"):
        import_expanded_asset(registry, request, frozen_seals=(seal,))
