"""Deterministic review-bundle binding tests."""

from hashlib import sha256
from pathlib import Path
from zipfile import ZipFile

import pytest

from im.review_bundle import BUNDLE_SHA256SUMS, build_review_bundle

_REQUIRED_REVIEW_FILES = (
    "docs/phase-0-implementation.md",
    "docs/phase0a-implementation-log.md",
    "docs/wp14-implementation-log.md",
    "docs/wp15-implementation-log.md",
    "golden/double_rollover/ingress.jsonl",
    "golden/double_rollover/policy/segment-000.bin",
    "golden/double_rollover/policy/segment-001.bin",
    "golden/double_rollover/policy/segment-002.bin",
    "golden/double_rollover/replay.json",
    "golden/plain_typing/ingress.jsonl",
    "golden/plain_typing/policy/segment-000.bin",
    "golden/plain_typing/replay.json",
    "golden/timer_cancel_race/ingress.jsonl",
    "golden/timer_cancel_race/policy/segment-000.bin",
    "golden/timer_cancel_race/replay.json",
    "golden/tool_integrate/ingress.jsonl",
    "golden/tool_integrate/policy/segment-000.bin",
    "golden/tool_integrate/replay.json",
    "probes/states/manifest.json",
    "probes/states/REVIEW.md",
    "probes/states/SHA256SUMS",
    "spec/FREEZE.md",
    "spec/behavior-spec.md",
    "spec/prompt-template-v1.txt",
    "spec/schema/action-v1.json",
    "spec/schema/event-v1.json",
)


def test_review_bundle_is_deterministic_and_binds_every_payload(
    tmp_path: Path,
) -> None:
    repository = Path(__file__).resolve().parents[1]
    first = tmp_path / "first.zip"
    second = tmp_path / "second.zip"

    first_digest = build_review_bundle(repository, first)
    second_digest = build_review_bundle(repository, second)

    assert first.read_bytes() == second.read_bytes()
    assert first_digest == second_digest == sha256(first.read_bytes()).hexdigest()
    with ZipFile(first) as archive:
        expected_names = sorted(_REQUIRED_REVIEW_FILES)
        assert archive.namelist() == [*expected_names, BUNDLE_SHA256SUMS]
        checksum_lines = archive.read(BUNDLE_SHA256SUMS).decode("utf-8").splitlines()
        assert checksum_lines == [
            f"{sha256(archive.read(name)).hexdigest()}  {name}" for name in expected_names
        ]


def test_review_bundle_rejects_output_inside_golden_input_tree() -> None:
    repository = Path(__file__).resolve().parents[1]

    with pytest.raises(ValueError, match="golden input tree"):
        build_review_bundle(repository, repository / "golden" / "candidate.zip")


def test_review_bundle_cannot_overwrite_a_fixed_input() -> None:
    repository = Path(__file__).resolve().parents[1]
    fixed_input = repository / "spec" / "FREEZE.md"
    before = fixed_input.read_bytes()

    with pytest.raises(ValueError, match="overwrite a review input"):
        build_review_bundle(repository, fixed_input)

    assert fixed_input.read_bytes() == before
