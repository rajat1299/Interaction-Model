"""Validated import of neutral-model atomic assets."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from hashlib import sha256

from im.assets.model import (
    AssetId,
    AssetPayload,
    AssetProvenance,
    AssetRecord,
    Split,
    SplitSeal,
    TemplateAssetPayload,
)
from im.assets.registry import AssetRegistry
from im.assets.validate import AssetValidationError, validate_registry, verify_split_seal


class AssetExpansionError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ExpansionRequest:
    """One imported output already bound to a selected template and seed subset."""

    asset_id: AssetId
    template_asset_id: AssetId
    seed_asset_ids: tuple[AssetId, ...]
    payload: AssetPayload
    generation_model: str
    source_bytes: bytes
    protected_values: tuple[str, ...] = ()


def _source_digest(source_bytes: bytes) -> str:
    if not source_bytes:
        raise AssetExpansionError("expansion source bytes must not be empty")
    return f"sha256:{sha256(source_bytes).hexdigest()}"


def import_expanded_asset(
    registry: AssetRegistry,
    request: ExpansionRequest,
    *,
    frozen_seals: Iterable[SplitSeal] = (),
) -> AssetRegistry:
    """Atomically validate and attach a preselected neutral-model import.

    The returned registry is the only successful result, so callers cannot use
    an imported candidate without rerunning pool validation.
    """
    template = next(
        (asset for asset in registry.assets if asset.asset_id == request.template_asset_id),
        None,
    )
    if template is None or not isinstance(template.payload, TemplateAssetPayload):
        raise AssetExpansionError("template asset does not exist")
    if isinstance(request.payload, TemplateAssetPayload):
        raise AssetExpansionError("neutral expansion must produce an atomic asset")
    if request.payload.kind is not template.payload.expands_kind:
        raise AssetExpansionError("expanded payload kind does not match its template")
    if (
        not request.seed_asset_ids
        or tuple(sorted(set(request.seed_asset_ids))) != request.seed_asset_ids
        or not set(request.seed_asset_ids) <= set(template.payload.seed_asset_ids)
    ):
        raise AssetExpansionError("expansion must preselect sorted template seed ids")
    if not request.protected_values:
        raise AssetExpansionError("expansion must declare protected values")

    for seal in frozen_seals:
        if seal.split is template.split:
            try:
                verify_split_seal(registry, seal)
            except AssetValidationError as error:
                raise AssetExpansionError("supplied frozen seal is not valid") from error
            raise AssetExpansionError("cannot expand a split after its seal is frozen")
    if template.split in {Split.TEST, Split.DEMO}:
        raise AssetExpansionError("cannot expand a held-out split")

    candidate = AssetRecord.build(
        asset_id=request.asset_id,
        split=template.split,
        payload=request.payload,
        provenance=AssetProvenance.MODEL_EXPANDED,
        template_asset_id=template.asset_id,
        generation_model=request.generation_model,
        source_digest=_source_digest(request.source_bytes),
        protected_values=request.protected_values,
        coverage=template.coverage,
        rollover_eligible=template.rollover_eligible,
    )
    try:
        updated = AssetRegistry(assets=(*registry.assets, candidate), reviews=registry.reviews)
        validate_registry(updated).raise_for_errors()
    except (AssetValidationError, ValueError) as error:
        raise AssetExpansionError("expanded import fails registry validation") from error
    return updated
