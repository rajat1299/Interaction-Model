"""Deterministic checksum-bound WP12/WP14 review bundle construction."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

BUNDLE_SHA256SUMS = "BUNDLE-SHA256SUMS"
_FIXED_REVIEW_FILES = (
    "spec/behavior-spec.md",
    "spec/prompt-template-v1.txt",
    "spec/FREEZE.md",
    "spec/schema/event-v1.json",
    "spec/schema/action-v1.json",
    "probes/states/manifest.json",
    "probes/states/REVIEW.md",
    "probes/states/SHA256SUMS",
    "docs/phase-0-implementation.md",
    "docs/phase0a-implementation-log.md",
    "docs/wp14-implementation-log.md",
    "docs/wp15-implementation-log.md",
)
_ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
_REGULAR_FILE_MODE = 0o100644 << 16


def review_files(repository: Path) -> tuple[Path, ...]:
    """Return every canonical payload path included in the review boundary."""
    repository = repository.resolve()
    fixed = [Path(item) for item in _FIXED_REVIEW_FILES]
    goldens = [
        path.relative_to(repository)
        for path in (repository / "golden").rglob("*")
        if path.is_file() and path.name != ".gitkeep"
    ]
    paths = tuple(sorted((*fixed, *goldens), key=lambda item: item.as_posix()))
    missing = [path.as_posix() for path in paths if not (repository / path).is_file()]
    if missing:
        raise FileNotFoundError(f"review bundle inputs are missing: {missing}")
    return paths


def _zip_info(name: str) -> ZipInfo:
    info = ZipInfo(filename=name, date_time=_ZIP_TIMESTAMP)
    info.compress_type = ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = _REGULAR_FILE_MODE
    return info


def build_review_bundle(repository: Path, output: Path) -> str:
    """Write a deterministic ZIP and return its lowercase SHA-256 digest."""
    repository = repository.resolve()
    output = output.resolve()
    review_paths = review_files(repository)
    golden_root = (repository / "golden").resolve()
    if output == golden_root or output.is_relative_to(golden_root):
        raise ValueError("review bundle output cannot be inside the golden input tree")
    if output in {(repository / path).resolve() for path in review_paths}:
        raise ValueError("review bundle output cannot overwrite a review input")

    payloads = {
        path.as_posix(): (repository / path).read_bytes() for path in review_paths
    }
    checksum_bytes = "".join(
        f"{sha256(data).hexdigest()}  {name}\n" for name, data in payloads.items()
    ).encode("utf-8")

    output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output, mode="w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in payloads.items():
            archive.writestr(_zip_info(name), data)
        archive.writestr(_zip_info(BUNDLE_SHA256SUMS), checksum_bytes)
    return sha256(output.read_bytes()).hexdigest()
