"""Split-scoped loading, selection, review, and sealing for Phase 1 assets."""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass

from pydantic import TypeAdapter, ValidationError

from im.assets.model import (
    AssetKind,
    AssetProvenance,
    AssetRecord,
    CorpusFamily,
    ReviewDecision,
    ReviewRecord,
    Split,
    TemplateAssetPayload,
    canonical_artifact_bytes,
)


class AssetRegistryError(ValueError):
    """Asset artifacts violate identity, split, review, or seal invariants."""


def _is_scenario_asset(asset: AssetRecord) -> bool:
    return (
        not isinstance(asset.payload, TemplateAssetPayload)
        and asset.provenance is not AssetProvenance.RECORDED
    )


@dataclass(frozen=True, slots=True)
class AssetBundle:
    split: Split
    assets: tuple[AssetRecord, ...]

    def __post_init__(self) -> None:
        ids = tuple(asset.asset_id for asset in self.assets)
        if not self.assets:
            raise AssetRegistryError("asset bundle must not be empty")
        if any(asset.split is not self.split for asset in self.assets):
            raise AssetRegistryError("asset bundle cannot mix splits")
        if any(not _is_scenario_asset(asset) for asset in self.assets):
            raise AssetRegistryError("asset bundle accepts only scenario-eligible atomic assets")
        if ids != tuple(sorted(ids)) or len(ids) != len(set(ids)):
            raise AssetRegistryError("asset bundle ids must be uniquely sorted")


class SplitPool:
    """The only scenario-facing asset selection boundary."""

    def __init__(self, registry: AssetRegistry, split: Split) -> None:
        self._registry = registry
        self.split = split

    @property
    def records(self) -> tuple[AssetRecord, ...]:
        return tuple(asset for asset in self._registry.assets if asset.split is self.split)

    @property
    def assets(self) -> tuple[AssetRecord, ...]:
        """Atomic records allowed to provide scenario content."""
        return tuple(asset for asset in self.records if _is_scenario_asset(asset))

    @property
    def templates(self) -> tuple[AssetRecord, ...]:
        return tuple(
            asset for asset in self.records if isinstance(asset.payload, TemplateAssetPayload)
        )

    @property
    def recorded_fixtures(self) -> tuple[AssetRecord, ...]:
        return tuple(
            asset for asset in self.records if asset.provenance is AssetProvenance.RECORDED
        )

    @property
    def corpus_records(self) -> tuple[AssetRecord, ...]:
        """Reviewed records that define a generated corpus split."""
        return tuple(
            asset for asset in self.records if asset.provenance is not AssetProvenance.RECORDED
        )

    def select(
        self,
        *,
        kind: AssetKind | None = None,
        family: CorpusFamily | None = None,
        approved_only: bool = True,
    ) -> tuple[AssetRecord, ...]:
        selected = []
        for asset in self.assets:
            if kind is not None and asset.payload.kind is not kind:
                continue
            if family is not None and family not in asset.coverage:
                continue
            if approved_only and not self._registry.is_approved(asset):
                continue
            selected.append(asset)
        return tuple(selected)

    def bundle(self, *asset_ids: str) -> AssetBundle:
        unique = tuple(sorted(set(asset_ids)))
        if not unique or len(unique) != len(asset_ids):
            raise AssetRegistryError("bundle ids must be nonempty and unique")
        by_id = {asset.asset_id: asset for asset in self.assets}
        try:
            assets = tuple(by_id[asset_id] for asset_id in unique)
        except KeyError as error:
            raise AssetRegistryError("bundle id is absent from the split pool") from error
        unapproved = [asset.asset_id for asset in assets if not self._registry.is_approved(asset)]
        if unapproved:
            raise AssetRegistryError(f"bundle assets are not approved: {unapproved}")
        return AssetBundle(split=self.split, assets=assets)


class AssetRegistry:
    def __init__(
        self,
        *,
        assets: Iterable[AssetRecord],
        reviews: Iterable[ReviewRecord] = (),
    ) -> None:
        self.assets = tuple(sorted(assets, key=lambda item: item.asset_id))
        self.reviews = tuple(sorted(reviews, key=lambda item: (item.asset_id, item.content_sha256)))
        self._validate()
        self._reviews = {
            (review.asset_id, review.content_sha256): review for review in self.reviews
        }

    def _validate(self) -> None:
        asset_ids = [asset.asset_id for asset in self.assets]
        review_keys = [(review.asset_id, review.content_sha256) for review in self.reviews]
        if len(asset_ids) != len(set(asset_ids)):
            raise AssetRegistryError("asset ids must be unique")
        if len(review_keys) != len(set(review_keys)):
            raise AssetRegistryError("review identity pairs must be unique")

        assets_by_id = {asset.asset_id: asset for asset in self.assets}
        for template in self.assets:
            if not isinstance(template.payload, TemplateAssetPayload):
                continue
            for seed_id in template.payload.seed_asset_ids:
                seed = assets_by_id.get(seed_id)
                if seed is None:
                    raise AssetRegistryError("template seed asset does not exist")
                if (
                    seed.split is not template.split
                    or seed.payload.kind is not template.payload.expands_kind
                    or seed.provenance is not AssetProvenance.SEED_AUTHORED
                ):
                    raise AssetRegistryError(
                        "template seeds must be seed-authored assets of its split and kind"
                    )
        for asset in self.assets:
            if asset.template_asset_id is None:
                continue
            template = assets_by_id.get(asset.template_asset_id)
            if template is None or not isinstance(template.payload, TemplateAssetPayload):
                raise AssetRegistryError("expanded asset template does not exist")
            if (
                template.split is not asset.split
                or template.payload.expands_kind is not asset.payload.kind
            ):
                raise AssetRegistryError("expanded asset must match template split and kind")
        for review in self.reviews:
            if review.asset_id not in assets_by_id:
                raise AssetRegistryError("review refers to an unknown asset")

    def pool(self, split: Split | str) -> SplitPool:
        return SplitPool(self, Split(split))

    def current_review(self, asset: AssetRecord) -> ReviewRecord | None:
        return self._reviews.get((asset.asset_id, asset.content_sha256))

    def is_approved(self, asset: AssetRecord) -> bool:
        review = self.current_review(asset)
        return review is not None and review.decision is ReviewDecision.APPROVED


_ASSET_ADAPTER = TypeAdapter(AssetRecord)
_REVIEW_ADAPTER = TypeAdapter(ReviewRecord)


def render_registry_jsonl(registry: AssetRegistry) -> bytes:
    rows: list[dict[str, object]] = []
    rows.extend(
        {"record_type": "asset", "record": asset.model_dump(mode="json")}
        for asset in registry.assets
    )
    rows.extend(
        {"record_type": "review", "record": review.model_dump(mode="json")}
        for review in registry.reviews
    )
    return b"".join(canonical_artifact_bytes(row) + b"\n" for row in rows)


def load_registry_jsonl(data: bytes) -> AssetRegistry:
    if not isinstance(data, bytes):
        raise TypeError("asset registry JSONL must be bytes")
    if data and not data.endswith(b"\n"):
        raise AssetRegistryError("asset registry JSONL must end with LF")
    assets: list[AssetRecord] = []
    reviews: list[ReviewRecord] = []
    try:
        lines = data.splitlines()
        for line in lines:
            row = json.loads(line)
            if set(row) != {"record_type", "record"}:
                raise AssetRegistryError("registry row has an unknown shape")
            record_type = row["record_type"]
            if record_type == "asset":
                assets.append(_ASSET_ADAPTER.validate_python(row["record"]))
            elif record_type == "review":
                reviews.append(_REVIEW_ADAPTER.validate_python(row["record"]))
            else:
                raise AssetRegistryError("unknown registry record_type")
    except (UnicodeDecodeError, json.JSONDecodeError, ValidationError, TypeError) as error:
        raise AssetRegistryError("invalid asset registry JSONL") from error
    registry = AssetRegistry(assets=assets, reviews=reviews)
    if render_registry_jsonl(registry) != data:
        raise AssetRegistryError("asset registry JSONL is not canonical")
    return registry
