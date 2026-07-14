"""Load WP14's human-approved artifacts without mutating their signed bytes."""

from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

from im.license import LicenseView
from im.probes.catalog import build_probe_catalog
from im.probes.model import ProbeManifest

APPROVED_MANIFEST_SHA256 = "87c824a2dad3c24fa05f7bd474dd8ef66a87532d3131dd9feb6932a4afee63b5"
APPROVED_REVIEW_SHA256 = "761cb4a5f8c2f6755863741ad1d3c69fd1522073c5b29f3c0efc9bfed184a9e9"


class ApprovedArtifactError(ValueError):
    """The on-disk probe corpus is not the artifact pair approved at the WP14 gate."""


@dataclass(frozen=True, slots=True)
class ApprovedProbeCatalog:
    """Signed manifest plus runtime-derived objective license evidence."""

    manifest: ProbeManifest
    manifest_sha256: str
    review_sha256: str
    views: dict[tuple[str, str], LicenseView]


def _digest(data: bytes) -> str:
    return sha256(data).hexdigest()


def _manifest_bytes(manifest: ProbeManifest) -> bytes:
    return (
        json.dumps(
            manifest.model_dump(mode="json"),
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        + b"\n"
    )


def load_approved_manifest(repository: Path) -> ProbeManifest:
    """Verify both top-level anchors and the sidecar before parsing the manifest."""
    states = repository.resolve() / "probes/states"
    manifest_bytes = (states / "manifest.json").read_bytes()
    review_bytes = (states / "REVIEW.md").read_bytes()
    manifest_digest = _digest(manifest_bytes)
    review_digest = _digest(review_bytes)
    if manifest_digest != APPROVED_MANIFEST_SHA256:
        raise ApprovedArtifactError(
            f"manifest is not the approved WP14 artifact: sha256:{manifest_digest}"
        )
    if review_digest != APPROVED_REVIEW_SHA256:
        raise ApprovedArtifactError(
            f"review is not the approved WP14 artifact: sha256:{review_digest}"
        )
    expected_sidecar = (
        f"{manifest_digest}  manifest.json\n{review_digest}  REVIEW.md\n"
    ).encode()
    if (states / "SHA256SUMS").read_bytes() != expected_sidecar:
        raise ApprovedArtifactError("WP14 SHA256SUMS does not bind the approved artifact pair")
    try:
        return ProbeManifest.model_validate_json(manifest_bytes)
    except ValueError as error:
        raise ApprovedArtifactError("approved manifest no longer parses") from error


async def load_approved_catalog(repository: Path) -> ApprovedProbeCatalog:
    """Rebuild objective views and prove they correspond byte-for-byte to the signed manifest."""
    repository = repository.resolve()
    signed = load_approved_manifest(repository)
    with TemporaryDirectory(prefix="im-wp15-catalog-") as directory:
        rebuilt = await build_probe_catalog(
            repository=repository,
            work_directory=Path(directory),
        )
    if rebuilt.manifest != signed or _manifest_bytes(rebuilt.manifest) != (
        repository / "probes/states/manifest.json"
    ).read_bytes():
        raise ApprovedArtifactError(
            "production scenario rebuild diverges from the human-approved manifest"
        )
    return ApprovedProbeCatalog(
        manifest=signed,
        manifest_sha256=f"sha256:{APPROVED_MANIFEST_SHA256}",
        review_sha256=f"sha256:{APPROVED_REVIEW_SHA256}",
        views=rebuilt.views,
    )
