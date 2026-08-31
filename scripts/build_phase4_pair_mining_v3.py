#!/usr/bin/env python3
"""Freeze the executable-only successor to the reviewed WP4-0 v2 candidate."""

from __future__ import annotations

import argparse
import re
import subprocess
from hashlib import sha256
from pathlib import Path

from im.assets.model import canonical_artifact_bytes
from im.generation.publication import publish_directory_transaction

ROOT = Path(__file__).resolve().parents[1]
V2 = Path("review/phase4/wp4-0-on-policy-pair-mining-candidate-v2")
OUTPUT = Path("review/phase4/wp4-0-on-policy-pair-mining-candidate-v3")
V2_SHA256SUMS = "a9f385de7984e41ea6192c404b3a8ea70ff4f93c7d6365656e31bd005eb09caf"
V2_BINDINGS = {
    "v2_manifest_sha256": (
        "sha256:430634ea2fbd75c9d6553efc41b1baf662ebdef51c1890b40187ea1c48d076d6"
    ),
    "v2_amendment_sha256": (
        "sha256:c1eac9c3fa5f1f33c5f926111e67f9662927145cebcd3044512f2053aff26a94"
    ),
    "v2_pricing_sha256": (
        "sha256:fcc96e806448bc72e86f341e30cd454cb53c357f043ae67eb1f215f27b58139d"
    ),
    "v2_request_inventory_sha256": (
        "sha256:29260edb8d4baba4013ae3c816b19742f3b0e3851d7e021bbff3b3dcf4e7ffc6"
    ),
    "v2_sha256sums_sha256": f"sha256:{V2_SHA256SUMS}",
}
SOURCE_FILES = (
    Path("src/im/training/phase4_pair_mining_run.py"),
    Path("scripts/build_phase4_pair_mining_v3.py"),
    Path("scripts/run_phase4_pair_mining.py"),
    Path("tests/test_phase4_pair_mining_run.py"),
)


def _digest(raw: bytes) -> str:
    return f"sha256:{sha256(raw).hexdigest()}"


def _verify_v2(root: Path) -> None:
    directory = root / V2
    sums_path = directory / "SHA256SUMS"
    if sums_path.is_symlink() or not sums_path.is_file():
        raise ValueError("v2 SHA256SUMS is not a regular file")
    sums = sums_path.read_bytes()
    if sha256(sums).hexdigest() != V2_SHA256SUMS:
        raise ValueError("v2 SHA256SUMS drifted")
    listed: set[str] = set()
    for line in sums.decode("ascii").splitlines():
        expected, name = line.split("  ", 1)
        path = directory / name
        if name in listed or path.is_symlink() or not path.is_file():
            raise ValueError("v2 inventory is malformed")
        listed.add(name)
        if sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(f"v2 artifact drifted: {name}")
    actual = {path.name for path in directory.iterdir() if path.name != "SHA256SUMS"}
    if actual != listed:
        raise ValueError("v2 inventory has unlisted artifacts")
    exact_files = {
        "candidate-manifest.json": V2_BINDINGS["v2_manifest_sha256"],
        "mining-request-inventory.jsonl.gz": V2_BINDINGS[
            "v2_request_inventory_sha256"
        ],
        "owner-amendment-template.txt": V2_BINDINGS["v2_amendment_sha256"],
        "pricing-refresh.json": V2_BINDINGS["v2_pricing_sha256"],
    }
    if any(
        _digest((directory / name).read_bytes()) != expected
        for name, expected in exact_files.items()
    ):
        raise ValueError("v2 controlling binding drifted")


def _verify_source(root: Path, source_commit: str) -> dict[str, str]:
    if re.fullmatch(r"[0-9a-f]{40}", source_commit) is None:
        raise ValueError("source commit must be an exact Git SHA")
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()
    dirty = any(
        subprocess.run(["git", *args], cwd=root, check=False).returncode
        for args in (("diff", "--quiet"), ("diff", "--cached", "--quiet"))
    )
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    if head != source_commit or dirty or any(
        path.startswith(("src/", "scripts/", "tests/", "spec/")) or "/" not in path
        for path in untracked
    ):
        raise ValueError("v3 requires the exact clean source commit")
    bindings: dict[str, str] = {}
    for path in SOURCE_FILES:
        raw = (root / path).read_bytes()
        committed = subprocess.run(
            ["git", "show", f"{source_commit}:{path.as_posix()}"],
            cwd=root,
            check=False,
            capture_output=True,
        )
        if committed.returncode or committed.stdout != raw:
            raise ValueError(f"source file is not bound to the commit: {path}")
        bindings[path.as_posix()] = _digest(raw)
    return bindings


def candidate_files(root: Path, source_commit: str) -> dict[str, bytes]:
    _verify_v2(root)
    source_bindings = _verify_source(root, source_commit)
    contract = {
        "application_retry_or_resample": False,
        "authorization": False,
        "detached_launchagent": {
            "keep_alive": False,
            "run_at_load": False,
            "single_explicit_launch": True,
        },
        "dpo_materialization": False,
        "dpo_training": False,
        "hard_ceiling_usd": 45,
        "kind": "phase4-paid-pair-mining-execution-contract-v3",
        "maximum_requests": 1280,
        "methodology_changed_from_v2": False,
        "optimizer_calls": 0,
        "pair_target": 320,
        "raw_persisted_before_inspection_or_adjudication": True,
        "sampler": {"count": 1, "delete_after_capture": True, "ttl_seconds": 3600},
        "selected_state_unchanged": True,
        "sentinel_requests_first": 9,
        "test_and_retention_60_access": False,
        "v2_bindings": V2_BINDINGS,
    }
    contract_raw = canonical_artifact_bytes(contract)
    manifest = {
        "authorization": False,
        "candidate_source_commit": source_commit,
        "dpo_materialized": False,
        "execution_contract_sha256": _digest(contract_raw),
        "kind": "phase4-paid-pair-mining-candidate-v3",
        "launchable": False,
        "methodology_changed_from_v2": False,
        "provider_calls_made": False,
        "source_bindings": source_bindings,
        "status": "offline_execution_amendment_only",
        "test_and_retention_60_opened": False,
        "v2_candidate_directory": V2.as_posix(),
        **V2_BINDINGS,
    }
    files = {
        "candidate-manifest.json": canonical_artifact_bytes(manifest),
        "execution-contract.json": contract_raw,
    }
    sums = "".join(
        f"{sha256(raw).hexdigest()}  {name}\n" for name, raw in sorted(files.items())
    ).encode("ascii")
    return {**files, "SHA256SUMS": sums}


def build(output: Path, source_commit: str) -> None:
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"refusing to replace existing candidate: {output}")
    publish_directory_transaction(output, candidate_files(ROOT, source_commit))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    build(args.output, args.source_commit)


if __name__ == "__main__":
    main()
