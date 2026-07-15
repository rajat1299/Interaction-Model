from __future__ import annotations

import json
import re
import runpy
from hashlib import sha256
from pathlib import Path

import pytest


def _files(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


@pytest.mark.asyncio
async def test_c6_package_is_deterministic_hash_named_and_reports_gates(tmp_path: Path) -> None:
    repository = Path(__file__).parents[1]
    generate = runpy.run_path(
        str(repository / "scripts/generate_c6_pilot_package.py")
    )["generate_c6_pilot_package"]
    approved = repository / "review/phase1/approved"
    inputs = {
        "repository": repository,
        "registry_jsonl": (approved / "registry.jsonl").read_bytes(),
        "seal_jsons": (
            (approved / "test-seal.json").read_bytes(),
            (approved / "demo-seal.json").read_bytes(),
        ),
    }
    first, second = tmp_path / "first", tmp_path / "second"
    await generate(output=first, **inputs)
    await generate(output=second, **inputs)

    files = _files(first)
    assert files == _files(second)
    assert set(files) >= {
        "SHA256SUMS",
        "manifest.json",
        "split-ledger.json",
        "leak-lint.json",
        "yield-inventory.json",
    }
    hash_path = re.compile(r"^teacher/[0-9a-f]{64}/[0-9a-f]{64}\.jsonl$")
    teacher_paths = tuple(path for path in files if path.startswith("teacher/"))
    assert teacher_paths and all(hash_path.fullmatch(path) for path in teacher_paths)
    manifest = json.loads(files["manifest.json"])
    approved_manifest = json.loads(
        (repository / "review/phase1/pilots/manifest.json").read_bytes()
    )
    lint = json.loads(files["leak-lint.json"])
    inventory = json.loads(files["yield-inventory.json"])
    assert len(manifest["streams"]) == lint["stream_count"] == 4
    assert sorted(stream["stream_sha256"] for stream in manifest["streams"]) == sorted(
        pilot["identities"]["stream_sha256"] for pilot in approved_manifest["pilots"]
    )
    assert sum(stream["decision_count"] for stream in manifest["streams"]) == lint[
        "decision_count"
    ]
    assert not all(family["reachable"] for family in inventory["families"])
    assert all(family["candidates"] for family in inventory["families"])
    assert sum(
        len(candidate["source_unit_sha256s"])
        for family in inventory["families"]
        for candidate in family["candidates"]
    ) == 20
    assert sum(
        candidate["source_program_count"]
        for family in inventory["families"]
        for candidate in family["candidates"]
    ) == 30
    assert all(
        candidate["action_counts"]["respond"] == 0
        for family in inventory["families"]
        for candidate in family["candidates"]
    )
    expected_checksums = "".join(
        f"{sha256(data).hexdigest()}  {path}\n"
        for path, data in sorted(files.items())
        if path != "SHA256SUMS"
    ).encode("ascii")
    assert files["SHA256SUMS"] == expected_checksums
