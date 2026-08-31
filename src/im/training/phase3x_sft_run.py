"""Offline-verifiable launch boundary for the single Phase 3X semantic SFT."""

from __future__ import annotations

import base64
import gzip
import json
import math
import os
import plistlib
import re
import struct
import subprocess
import sys
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

import tinker

from im.assets.model import canonical_artifact_bytes
from im.canonical_json import canonicalize_tim_json, parse_tim_json
from im.license import Allowed, check
from im.policy.intent import (
    POLICY_INTENT_ADAPTER,
    IntentRegistry,
    LanguageRealizationRequest,
    complete_language_realization,
    resolve_policy_intent,
)
from im.training.phase3_data import load_pinned_tokenizer
from im.training.phase3_eval import (
    capture_raw_generation,
    persist_raw_generation,
    rebuild_dev_states,
    sentinel_tags,
)
from im.training.phase3_framing import TerminalFramingError, project_terminal_output
from im.training.phase3_full_run import (
    ReplayBatch,
    TrainingDatum,
    _checkpoint_path,
    _gradient_evidence,
    _provider_result,
    _stage,
    _write_status,
)
from im.training.phase3_full_tinker import TinkerRunProvider
from im.training.phase3_sampling import read_tinker_api_key

CANDIDATE_DIRECTORY = Path("review/phase3/wp3x-2-semantic-intent-sft-candidate-v3")
EXECUTION_DIRECTORY = Path("review/phase3/wp3x-2-semantic-intent-sft-execution-v3")
RUN_OUTPUT = Path("review/phase3/wp3x-2-semantic-intent-sft-run-v3")
RUN_ID = "phase3x-semantic-intent-sft-v1"
FAST_EVALUATION_FILE = "fast-policy-sanity-eval-requests.jsonl.gz"
FULL_DEV_EVALUATION_FILE = "full-dev-eval-requests.jsonl.gz"
EVALUATION_INVENTORY_FILE = "eval-request-inventory.json"
DEV_DERIVATION_FILE = "dev-derivation-proof.json"
TOKENIZER_DIRECTORY = Path(".cache/replay-sources/995ad96eacd98c81ed38be0c5b274b04031597b0")
OFFLINE_DEV_DIRECTORY = Path("review/phase3/wp3-2-offline-candidate-v4")
SAMPLER_TTL_SECONDS = 3600
LAUNCHD_LABEL = "com.interactionmodel.phase3x-semantic-sft-v3"
LAUNCHD_ENV = "PHASE3X_SFT_LAUNCHD_LABEL"
STDOUT_LOG = Path.home() / "Library/Logs/interactionmodel-phase3x-sft-v3.stdout.log"
STDERR_LOG = Path.home() / "Library/Logs/interactionmodel-phase3x-sft-v3.stderr.log"

REQUIRED_CANDIDATE_FILES = frozenset(
    {
        "batch-plan.json",
        "cost-model.json",
        "datum-index.json",
        DEV_DERIVATION_FILE,
        "eval-contract.json",
        EVALUATION_INVENTORY_FILE,
        FAST_EVALUATION_FILE,
        FULL_DEV_EVALUATION_FILE,
        "gate-1-manifest.json",
        "mask-proof.json",
        "materialized-datums.jsonl.gz",
        "policy-intent-prompt-v1.txt",
        "policy-intent-schema.json",
        "response-kind-authority.json",
        "source-lineage.json",
        "token-accounting.json",
        "training-contract.json",
    }
)
SOURCE_FILES = (
    Path("src/im/training/phase3x_sft_run.py"),
    Path("scripts/run_phase3x_sft.py"),
)

BACKBONE = "Qwen/Qwen3.6-35B-A3B"
LORA_RANK = 16
SEED = 20260801
TERMINAL_TOKEN_ID = 248046
STEPS = 63
WARMUP_STEPS = 10
PEAK_LEARNING_RATE = 1e-4
MAXIMUM_SPEND_USD = 55
FAST_SAMPLE_STEPS = frozenset({10})
FULL_DEV_STEPS = frozenset({20, 40, 63})
SAMPLER_STEPS = FAST_SAMPLE_STEPS | FULL_DEV_STEPS
OPTIMIZER = {
    "beta1": 0.9,
    "beta2": 0.95,
    "eps": 1e-8,
    "weight_decay": 0.0,
    "grad_clip_norm": 1.0,
}
_SHA256 = re.compile(r"sha256:[0-9a-f]{64}")
_GIT_SHA = re.compile(r"[0-9a-f]{40}")
PREPARED_SUMS_FILE = "PREPARED-SHA256SUMS"


class Phase3XSFTRunError(ValueError):
    """The frozen candidate or independent launch authorization failed closed."""


@dataclass(frozen=True, slots=True)
class Phase3XSFTContract:
    candidate_sha256sums_sha256: str
    candidate_source_commit: str
    datums: Mapping[str, TrainingDatum]
    batches: tuple[ReplayBatch, ...]
    evaluation: Mapping[str, object]
    evaluation_artifacts: Mapping[str, Path]
    evaluation_inventory: Mapping[str, object]
    dev_proof: Mapping[str, object]
    cost: Mapping[str, object]
    modeled_total_usd: float


def _digest(raw: bytes) -> str:
    return f"sha256:{sha256(raw).hexdigest()}"


def _token_digest(tokens: list[int]) -> str:
    return _digest(",".join(str(token) for token in tokens).encode())


def _json(raw: bytes, label: str) -> Mapping[str, object]:
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise Phase3XSFTRunError(f"{label} is malformed JSON") from error
    if not isinstance(value, Mapping):
        raise Phase3XSFTRunError(f"{label} is not a JSON object")
    return value


def _inside(root: Path, path: Path) -> Path:
    candidate = (path if path.is_absolute() else root / path).resolve(strict=True)
    try:
        candidate.relative_to(root)
    except ValueError as error:
        raise Phase3XSFTRunError("launch artifact escapes the repository root") from error
    return candidate


def _checksum_inventory(directory: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    try:
        lines = (directory / "SHA256SUMS").read_text(encoding="ascii").splitlines()
    except (OSError, UnicodeDecodeError) as error:
        raise Phase3XSFTRunError("candidate SHA256SUMS is unreadable") from error
    for line in lines:
        parts = line.split("  ", 1)
        if len(parts) != 2:
            raise Phase3XSFTRunError("candidate SHA256SUMS is malformed")
        expected, name = parts
        path = Path(name)
        if (
            not re.fullmatch(r"[0-9a-f]{64}", expected)
            or path.name != name
            or name in result
            or not (directory / name).is_file()
            or (directory / name).is_symlink()
            or sha256((directory / name).read_bytes()).hexdigest() != expected
        ):
            raise Phase3XSFTRunError("candidate checksum manifest does not close")
        result[name] = f"sha256:{expected}"
    actual = {path.name for path in directory.iterdir() if path.is_file()} - {"SHA256SUMS"}
    if set(result) != actual or not REQUIRED_CANDIDATE_FILES <= actual:
        raise Phase3XSFTRunError("candidate checksum inventory does not close")
    return result


def _prepared_execution_inventory(directory: Path) -> None:
    expected_names = {
        f"{LAUNCHD_LABEL}.plist",
        "execution-packet.json",
        "launch-plan.json",
        "owner-authorization-template.json",
    }
    try:
        lines = (directory / PREPARED_SUMS_FILE).read_text(encoding="ascii").splitlines()
    except (OSError, UnicodeDecodeError) as error:
        raise Phase3XSFTRunError("prepared execution manifest is unreadable") from error
    found: set[str] = set()
    for line in lines:
        parts = line.split("  ", 1)
        if len(parts) != 2:
            raise Phase3XSFTRunError("prepared execution manifest is malformed")
        expected, name = parts
        path = directory / name
        if (
            name not in expected_names
            or name in found
            or not re.fullmatch(r"[0-9a-f]{64}", expected)
            or not path.is_file()
            or path.is_symlink()
            or sha256(path.read_bytes()).hexdigest() != expected
        ):
            raise Phase3XSFTRunError("prepared execution manifest does not close")
        found.add(name)
    if found != expected_names:
        raise Phase3XSFTRunError("prepared execution manifest inventory drifted")


def _evaluation_artifacts(
    directory: Path, evaluation: Mapping[str, object], inventory: Mapping[str, str]
) -> dict[str, Path]:
    bindings = evaluation.get("sampling_artifacts")
    if not isinstance(bindings, Mapping) or set(bindings) != {"fast_policy_sanity", "full_dev"}:
        raise Phase3XSFTRunError("checksum-bound fast/full DEV sampling artifacts are missing")
    expected_names = {
        "fast_policy_sanity": FAST_EVALUATION_FILE,
        "full_dev": FULL_DEV_EVALUATION_FILE,
    }
    result: dict[str, Path] = {}
    request_rows: dict[str, list[Mapping[str, object]]] = {}
    for kind, binding in bindings.items():
        if not isinstance(kind, str) or not isinstance(binding, Mapping):
            raise Phase3XSFTRunError("evaluation sampling artifact binding is malformed")
        name, expected = binding.get("path"), binding.get("sha256")
        if (
            not isinstance(name, str)
            or name != expected_names[kind]
            or not isinstance(expected, str)
            or not _SHA256.fullmatch(expected)
            or inventory.get(name) != expected
        ):
            raise Phase3XSFTRunError("evaluation sampling artifact is not checksum-bound")
        path = directory / name
        try:
            rows = [
                _json(raw, f"{kind} evaluation request")
                for raw in gzip.decompress(path.read_bytes()).splitlines()
            ]
        except OSError as error:
            raise Phase3XSFTRunError("evaluation sampling artifact is not valid gzip") from error
        if not rows:
            raise Phase3XSFTRunError("evaluation sampling artifact is empty")
        request_rows[kind] = rows
        result[kind] = path
    inventory_path = directory / EVALUATION_INVENTORY_FILE
    if inventory.get(EVALUATION_INVENTORY_FILE) != _digest(inventory_path.read_bytes()):
        raise Phase3XSFTRunError("evaluation request inventory is not checksum-bound")
    _verify_evaluation_inventory(
        _json(inventory_path.read_bytes(), "evaluation request inventory"), request_rows
    )
    return result


def _verify_evaluation_inventory(
    inventory: Mapping[str, object], rows: Mapping[str, list[Mapping[str, object]]]
) -> None:
    requests, schedule = inventory.get("requests"), inventory.get("schedule")
    sampling = inventory.get("sampling")
    if (
        inventory.get("kind") != "phase3x-semantic-intent-eval-request-inventory-v1"
        or inventory.get("full_dev_state_count") != 300
        or not isinstance(inventory.get("max_expected_output_token_count"), int)
        or not 0 < int(inventory["max_expected_output_token_count"]) <= 256
        or inventory.get("request_count_across_schedule") != 911
        or not isinstance(requests, list)
        or len(requests) != 300
        or not isinstance(schedule, list)
        or len(schedule) != 4
        or sampling
        != {
            "constrained_decoding": False,
            "max_output_tokens": 256,
            "provider": "Tinker",
            "stop_token_id": TERMINAL_TOKEN_ID,
            "temperature": 0,
            "top_p": 1,
        }
    ):
        raise Phase3XSFTRunError("evaluation request inventory contract drifted")
    inventory_ids = [row.get("state_id") if isinstance(row, Mapping) else None for row in requests]
    full_ids = [row.get("state_id") for row in rows["full_dev"]]
    fast_ids = [row.get("state_id") for row in rows["fast_policy_sanity"]]
    expected_schedule = [
        {"kind": "fast_policy_sanity", "state_ids": fast_ids, "step": 10},
        *[{"kind": "full_dev", "state_ids": full_ids, "step": step} for step in (20, 40, 63)],
    ]
    if (
        len(set(inventory_ids)) != 300
        or full_ids != inventory_ids
        or len(fast_ids) != 11
        or len(set(fast_ids)) != 11
        or not set(fast_ids) <= set(full_ids)
        or schedule != expected_schedule
    ):
        raise Phase3XSFTRunError("evaluation request schedule or identities drifted")
    inventory_by_id = {str(row["state_id"]): row for row in requests if isinstance(row, Mapping)}
    for row in (*rows["fast_policy_sanity"], *rows["full_dev"]):
        state_id, tokens = row.get("state_id"), row.get("input_tokens")
        expected = inventory_by_id.get(str(state_id))
        if (
            expected is None
            or not isinstance(tokens, list)
            or not tokens
            or any(
                isinstance(token, bool) or not isinstance(token, int) or token < 0
                for token in tokens
            )
            or row.get("input_token_count") != len(tokens)
            or expected.get("input_token_count") != len(tokens)
            or row.get("input_token_ids_sha256") != _token_digest(tokens)
            or row.get("input_token_ids_sha256") != expected.get("input_token_ids_sha256")
        ):
            raise Phase3XSFTRunError("materialized evaluation request drifted")


def _load_datums(raw: bytes) -> dict[str, TrainingDatum]:
    try:
        rows = gzip.decompress(raw).splitlines()
    except OSError as error:
        raise Phase3XSFTRunError("semantic datums are not valid gzip") from error
    datums: dict[str, TrainingDatum] = {}
    for raw_row in rows:
        row = _json(raw_row, "semantic datum")
        datum_id = row.get("datum_id")
        inputs, targets = row.get("input_tokens"), row.get("target_tokens")
        encoded, declared = row.get("weights_float32_le_base64"), row.get("weights")
        if (
            not isinstance(datum_id, str)
            or datum_id in datums
            or row.get("kind") != "semantic_intent"
            or not isinstance(inputs, list)
            or not isinstance(targets, list)
            or not inputs
            or len(inputs) != len(targets)
            or any(
                isinstance(item, bool) or not isinstance(item, int) or item < 0 for item in inputs
            )
            or any(
                isinstance(item, bool) or not isinstance(item, int) or item < 0 for item in targets
            )
            or not isinstance(encoded, str)
            or not isinstance(declared, list)
            or targets[-1] != TERMINAL_TOKEN_ID
        ):
            raise Phase3XSFTRunError("semantic datum shape drifted")
        try:
            weights = base64.b64decode(encoded, validate=True)
            unpacked = struct.unpack(f"<{len(targets)}f", weights)
            declared_bytes = struct.pack(f"<{len(targets)}f", *declared)
        except (ValueError, TypeError, struct.error) as error:
            raise Phase3XSFTRunError("semantic datum weights are malformed") from error
        positive = sum(value > 0 for value in unpacked)
        if (
            weights != declared_bytes
            or positive != row.get("positive_token_count")
            or positive <= 0
            or unpacked[-1] <= 0
            or any(not math.isfinite(value) or value not in (0.0, 1.0) for value in unpacked)
        ):
            raise Phase3XSFTRunError("semantic datum mask drifted")
        datums[datum_id] = TrainingDatum(
            datum_id, "semantic_intent", tuple(inputs), tuple(targets), weights, positive
        )
    if len(datums) != 2_000:
        raise Phase3XSFTRunError("semantic candidate must contain exactly 2,000 datums")
    return datums


def _load_batches(raw: bytes, datums: Mapping[str, TrainingDatum]) -> tuple[ReplayBatch, ...]:
    plan = _json(raw, "semantic batch plan")
    rows = plan.get("steps")
    if (
        plan.get("kind") != "phase3x-semantic-intent-batch-plan-v1"
        or plan.get("no_replay") is not True
        or not isinstance(rows, list)
        or len(rows) != STEPS
    ):
        raise Phase3XSFTRunError("semantic batch plan drifted")
    seen: list[str] = []
    batches: list[ReplayBatch] = []
    for step, row in enumerate(rows, start=1):
        ids = row.get("interaction_datum_ids") if isinstance(row, Mapping) else None
        membership = {"interaction_datum_ids": ids, "step": step}
        if (
            not isinstance(row, Mapping)
            or row.get("step") != step
            or not isinstance(ids, list)
            or not ids
            or any(not isinstance(item, str) or item not in datums for item in ids)
            or row.get("membership_sha256") != _digest(canonical_artifact_bytes(membership))
        ):
            raise Phase3XSFTRunError("semantic batch membership drifted")
        seen.extend(ids)
        batches.append(
            ReplayBatch(step, tuple(ids), (), str(row["membership_sha256"]), str(len(ids)))
        )
    if len(seen) != 2_000 or len(set(seen)) != 2_000 or set(seen) != set(datums):
        raise Phase3XSFTRunError("semantic batch plan does not cover each datum exactly once")
    return tuple(batches)


def _verify_training(training: Mapping[str, object]) -> None:
    schedule = training.get("schedule")
    rates = schedule.get("learning_rates") if isinstance(schedule, Mapping) else None
    expected = {
        "backbone": BACKBONE,
        "epochs": 1,
        "kind": "phase3x-semantic-intent-training-contract-v1",
        "lora": {
            "rank": LORA_RANK,
            "train_attention": True,
            "train_mlp": True,
            "train_unembed": False,
        },
        "optimizer_steps": STEPS,
        "peak_learning_rate": PEAK_LEARNING_RATE,
        "replay_datum_count": 0,
        "restart_or_second_sft_authorized": False,
        "seed": SEED,
        "target_datum_count": 2_000,
        "terminal_token_id": TERMINAL_TOKEN_ID,
    }
    if (
        {key: training.get(key) for key in expected} != expected
        or not isinstance(schedule, Mapping)
        or schedule.get("formula")
        != "step<=10:1e-4*step/10;step>10:1e-4*0.5*(1+cos(pi*(step-10)/53))"
        or schedule.get("horizon_steps") != STEPS
        or schedule.get("kind") != "linear-warmup-then-cosine-to-zero"
        or schedule.get("warmup_steps") != WARMUP_STEPS
        or not isinstance(rates, list)
        or rates
        != [{"learning_rate": learning_rate(step), "step": step} for step in range(1, STEPS + 1)]
    ):
        raise Phase3XSFTRunError("candidate training contract drifted")


def load_candidate(
    root: Path,
    candidate_sha256sums_sha256: str,
    candidate_directory: Path = CANDIDATE_DIRECTORY,
) -> Phase3XSFTContract:
    """Prove the complete candidate bytes and frozen one-run contract without external calls."""
    if not _SHA256.fullmatch(candidate_sha256sums_sha256):
        raise Phase3XSFTRunError("candidate SHA256SUMS digest is malformed")
    root = root.resolve(strict=True)
    directory = _inside(root, candidate_directory)
    sums = (directory / "SHA256SUMS").read_bytes()
    if _digest(sums) != candidate_sha256sums_sha256:
        raise Phase3XSFTRunError("candidate root checksum binding drifted")
    inventory = _checksum_inventory(directory)
    manifest = _json((directory / "gate-1-manifest.json").read_bytes(), "gate-1 manifest")
    declared = manifest.get("files")
    manifest_files = set(inventory) - {"gate-1-manifest.json"}
    if (
        manifest.get("kind") != "phase3x-consolidated-gate-1-semantic-sft-candidate-v1"
        or manifest.get("candidate_checksum_bound") is not True
        or manifest.get("candidate_status") != "offline_unapproved_create_only"
        or not isinstance(manifest.get("source_commit"), str)
        or not _GIT_SHA.fullmatch(str(manifest["source_commit"]))
        or not isinstance(declared, Mapping)
        or dict(declared) != {name: inventory[name] for name in sorted(manifest_files)}
        or manifest.get("authorization")
        != {
            "checkpoint_access": False,
            "checksum_bound_authorization": False,
            "dpo": False,
            "launch": False,
            "provider_calls": False,
            "retention_60": False,
            "sealed_test": False,
            "secrets": False,
            "spend": False,
        }
    ):
        raise Phase3XSFTRunError("candidate manifest is not the create-only Gate 1 freeze")
    candidate_source_commit = str(manifest["source_commit"])
    bindings = manifest.get("bindings")
    offline_dev_digest = (
        bindings.get("offline_dev_sha256sums_sha256") if isinstance(bindings, Mapping) else None
    )
    offline_dev_sums = _inside(root, OFFLINE_DEV_DIRECTORY / "SHA256SUMS").read_bytes()
    if (
        not isinstance(offline_dev_digest, str)
        or not _SHA256.fullmatch(offline_dev_digest)
        or _digest(offline_dev_sums) != offline_dev_digest
    ):
        raise Phase3XSFTRunError("candidate does not bind the frozen DEV source")

    training = _json((directory / "training-contract.json").read_bytes(), "training contract")
    evaluation = _json((directory / "eval-contract.json").read_bytes(), "eval contract")
    cost = _json((directory / "cost-model.json").read_bytes(), "cost model")
    evaluation_inventory = _json(
        (directory / EVALUATION_INVENTORY_FILE).read_bytes(), "evaluation request inventory"
    )
    dev_proof = _json((directory / DEV_DERIVATION_FILE).read_bytes(), "DEV derivation proof")
    modeled = cost.get("modeled_total_usd")
    _verify_training(training)
    components = cost.get("components_usd")
    if (
        evaluation.get("checkpoints")
        != {
            "10": "fast_policy_sanity",
            "20": "full_dev",
            "40": "full_dev",
            "63": "full_dev_and_mandatory_selection",
        }
        or evaluation.get("raw_unconstrained_tinker_only") is not True
        or evaluation.get("constrained_decoding_claimed") is not False
        or evaluation.get("full_retention_during_policy_sft") is not False
        or cost.get("hard_ceiling_usd") != MAXIMUM_SPEND_USD
        or cost.get("authorization") is not False
        or cost.get("kind") != "phase3x-semantic-intent-cost-model-v1"
        or cost.get("paid_enforcement") is not False
        or cost.get("provider_calls_made") is not False
        or not isinstance(components, Mapping)
        or any(
            isinstance(value, bool)
            or not isinstance(value, int | float)
            or not math.isfinite(float(value))
            or float(value) < 0
            for value in components.values()
        )
        or isinstance(modeled, bool)
        or not isinstance(modeled, int | float)
        or not math.isfinite(float(modeled))
        or float(modeled) <= 0
        or float(modeled) > MAXIMUM_SPEND_USD
        or round(sum(float(value) for value in components.values()), 6) != float(modeled)
        or dev_proof.get("kind") != "phase3x-policy-intent-dev-derivation-proof-v1"
        or dev_proof.get("derivation_count") != 300
        or not isinstance(dev_proof.get("rows"), list)
        or len(dev_proof["rows"]) != 300
    ):
        raise Phase3XSFTRunError("candidate training, evaluation, or modeled-cost contract drifted")
    artifacts = _evaluation_artifacts(directory, evaluation, inventory)
    datums = _load_datums((directory / "materialized-datums.jsonl.gz").read_bytes())
    batches = _load_batches((directory / "batch-plan.json").read_bytes(), datums)
    return Phase3XSFTContract(
        candidate_sha256sums_sha256,
        candidate_source_commit,
        datums,
        batches,
        evaluation,
        artifacts,
        evaluation_inventory,
        dev_proof,
        cost,
        float(modeled),
    )


def learning_rate(step: int) -> float:
    """Frozen ten-step linear warmup, then cosine decay to zero at step 63."""
    if isinstance(step, bool) or not isinstance(step, int) or not 1 <= step <= STEPS:
        raise Phase3XSFTRunError("learning-rate step is outside the one-run horizon")
    if step <= WARMUP_STEPS:
        return PEAK_LEARNING_RATE * step / WARMUP_STEPS
    return PEAK_LEARNING_RATE * 0.5 * (
        1 + math.cos(math.pi * (step - WARMUP_STEPS) / (STEPS - WARMUP_STEPS))
    )


def evaluation_at(step: int) -> str | None:
    if isinstance(step, bool) or not isinstance(step, int) or not 1 <= step <= STEPS:
        raise Phase3XSFTRunError("evaluation step is outside the one-run horizon")
    if step in FAST_SAMPLE_STEPS:
        return "fast_policy_sanity"
    if step in FULL_DEV_STEPS:
        return "full_dev"
    return None


def _source_hashes(root: Path) -> dict[str, str]:
    return {path.as_posix(): _digest((root / path).read_bytes()) for path in SOURCE_FILES}


def verify_source(root: Path, source_commit: str, candidate_source_commit: str) -> None:
    """Require the exact clean reviewed checkout; this transitively binds imported code."""
    if source_commit != candidate_source_commit or not _GIT_SHA.fullmatch(source_commit):
        raise Phase3XSFTRunError("candidate and execution source commits differ")
    if subprocess.run(
        ["git", "merge-base", "--is-ancestor", source_commit, "HEAD"],
        cwd=root,
        check=False,
    ).returncode:
        raise Phase3XSFTRunError("candidate source commit is not an ancestor of HEAD")
    changed = subprocess.run(
        ["git", "diff", "--name-only", f"{source_commit}..HEAD"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    allowed_directories = (
        CANDIDATE_DIRECTORY.as_posix() + "/",
        EXECUTION_DIRECTORY.as_posix() + "/",
    )
    if any(
        path != "docs/phase3-implementation-log.md"
        and not path.startswith(allowed_directories)
        for path in changed
    ):
        raise Phase3XSFTRunError("tracked executable dependencies drifted from source commit")
    if any(
        subprocess.run(["git", *args], cwd=root, check=False).returncode
        for args in (("diff", "--quiet"), ("diff", "--cached", "--quiet"))
    ):
        raise Phase3XSFTRunError("checkout contains uncommitted tracked drift")
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    if any(
        path.startswith(("src/", "scripts/", "spec/")) or "/" not in path
        for path in untracked
    ):
        raise Phase3XSFTRunError("checkout contains unreviewed executable source")


def verify_launchd() -> None:
    if (
        sys.platform != "darwin"
        or os.getppid() != 1
        or os.environ.get(LAUNCHD_ENV) != LAUNCHD_LABEL
    ):
        raise Phase3XSFTRunError("paid run must execute as the frozen LaunchAgent")
    result = subprocess.run(
        ["launchctl", "print", f"gui/{os.getuid()}/{LAUNCHD_LABEL}"],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    if result.returncode or f"pid = {os.getpid()}" not in result.stdout:
        raise Phase3XSFTRunError("LaunchAgent process identity mismatch")


def prepare_execution(
    root: Path,
    *,
    source_commit: str,
    candidate_sha256sums_sha256: str,
    output: Path = EXECUTION_DIRECTORY,
) -> Mapping[str, object]:
    """Create a packet and pending template; never create an authorization or provider."""
    if not _GIT_SHA.fullmatch(source_commit):
        raise Phase3XSFTRunError("source commit must be an exact Git SHA")
    root = root.resolve(strict=True)
    contract = load_candidate(root, candidate_sha256sums_sha256)
    verify_source(root, source_commit, contract.candidate_source_commit)
    destination = (output if output.is_absolute() else root / output).resolve(strict=False)
    try:
        destination.relative_to(root)
    except ValueError as error:
        raise Phase3XSFTRunError("execution packet output escapes the repository root") from error
    if destination.exists() or destination.is_symlink():
        raise Phase3XSFTRunError("refusing to replace an execution packet")
    destination.mkdir(mode=0o700, parents=True)
    script = root / "scripts/run_phase3x_sft.py"
    argv = [
        str(root / ".venv/bin/python"),
        str(script),
        "--mode",
        "execute",
        "--repository-root",
        str(root),
        "--candidate-sha256",
        candidate_sha256sums_sha256,
        "--execution-packet",
        str(output / "execution-packet.json"),
        "--authorization",
        str(output / "owner-authorization.json"),
    ]
    plist = plistlib.dumps(
        {
            "EnvironmentVariables": {LAUNCHD_ENV: LAUNCHD_LABEL},
            "KeepAlive": False,
            "Label": LAUNCHD_LABEL,
            "ProgramArguments": argv,
            "RunAtLoad": False,
            "StandardErrorPath": str(STDERR_LOG),
            "StandardOutPath": str(STDOUT_LOG),
            "WorkingDirectory": str(root),
        },
        fmt=plistlib.FMT_XML,
        sort_keys=True,
    )
    plist_name = f"{LAUNCHD_LABEL}.plist"
    (destination / plist_name).write_bytes(plist)
    launch_plan = {
        "bootstrap_argv": [
            "/bin/launchctl",
            "bootstrap",
            f"gui/{os.getuid()}",
            str(destination / plist_name),
        ],
        "kickstart_argv": [
            "/bin/launchctl",
            "kickstart",
            f"gui/{os.getuid()}/{LAUNCHD_LABEL}",
        ],
        "label": LAUNCHD_LABEL,
        "stderr_path": str(STDERR_LOG),
        "stdout_path": str(STDOUT_LOG),
    }
    launch_raw = canonical_artifact_bytes(launch_plan)
    (destination / "launch-plan.json").write_bytes(launch_raw)
    packet = {
        "candidate_directory": CANDIDATE_DIRECTORY.as_posix(),
        "candidate_sha256sums_sha256": contract.candidate_sha256sums_sha256,
        "candidate_source_commit": contract.candidate_source_commit,
        "evaluation_steps": {
            "10": "fast_policy_sanity",
            "20": "full_dev",
            "40": "full_dev",
            "63": "full_dev",
        },
        "kind": "phase3x-semantic-intent-sft-execution-packet-v1",
        "launch_plan_sha256": _digest(launch_raw),
        "launchagent_plist_sha256": _digest(plist),
        "maximum_spend_usd": MAXIMUM_SPEND_USD,
        "modeled_total_usd": contract.modeled_total_usd,
        "no_replay": True,
        "no_restart_restore_or_second_sft": True,
        "optimizer_steps": STEPS,
        "output_directory": RUN_OUTPUT.as_posix(),
        "raw_unconstrained_tinker_only": True,
        "retention_sampling": False,
        "run_id": RUN_ID,
        "source_commit": source_commit,
        "source_hashes": _source_hashes(root),
    }
    packet_raw = canonical_artifact_bytes(packet)
    (destination / "execution-packet.json").write_bytes(packet_raw)
    template = {
        "allowed_secret_name": "TINKER_API_KEY",
        "candidate_sha256sums_sha256": contract.candidate_sha256sums_sha256,
        "candidate_source_commit": contract.candidate_source_commit,
        "decision": "pending_independent_owner_binding",
        "execution_packet_sha256": _digest(packet_raw),
        "kind": "phase3x-semantic-intent-sft-owner-authorization-template-v1",
        "maximum_spend_usd": MAXIMUM_SPEND_USD,
        "no_restart_restore_or_second_sft": True,
        "one_sft_only": True,
        "owner_instruction": None,
        "source_commit": source_commit,
    }
    (destination / "owner-authorization-template.json").write_bytes(
        canonical_artifact_bytes(template)
    )
    prepared_names = (
        plist_name,
        "execution-packet.json",
        "launch-plan.json",
        "owner-authorization-template.json",
    )
    (destination / PREPARED_SUMS_FILE).write_text(
        "".join(
            f"{sha256((destination / name).read_bytes()).hexdigest()}  {name}\n"
            for name in sorted(prepared_names)
        ),
        encoding="ascii",
    )
    return packet


def load_authorized_execution(
    root: Path,
    *,
    packet_path: Path,
    authorization_path: Path,
    candidate_sha256sums_sha256: str,
) -> tuple[Phase3XSFTContract, Mapping[str, object], Mapping[str, object]]:
    """Pure preflight that must complete before any secret or provider capability is used."""
    root = root.resolve(strict=True)
    contract = load_candidate(root, candidate_sha256sums_sha256)
    packet_file = _inside(root, packet_path)
    if packet_file != root / EXECUTION_DIRECTORY / "execution-packet.json":
        raise Phase3XSFTRunError("execution packet path is non-canonical")
    _prepared_execution_inventory(packet_file.parent)
    packet_raw = packet_file.read_bytes()
    authorization_file = _inside(root, authorization_path)
    if authorization_file != packet_file.parent / "owner-authorization.json":
        raise Phase3XSFTRunError("owner authorization path is non-canonical")
    authorization_raw = authorization_file.read_bytes()
    packet = _json(packet_raw, "execution packet")
    authorization = _json(authorization_raw, "owner authorization")
    source_commit = packet.get("source_commit")
    launch_raw = (packet_file.parent / "launch-plan.json").read_bytes()
    plist_raw = (packet_file.parent / f"{LAUNCHD_LABEL}.plist").read_bytes()
    expected_packet = {
        "candidate_directory": CANDIDATE_DIRECTORY.as_posix(),
        "candidate_sha256sums_sha256": candidate_sha256sums_sha256,
        "candidate_source_commit": contract.candidate_source_commit,
        "evaluation_steps": {
            "10": "fast_policy_sanity",
            "20": "full_dev",
            "40": "full_dev",
            "63": "full_dev",
        },
        "kind": "phase3x-semantic-intent-sft-execution-packet-v1",
        "launch_plan_sha256": _digest(launch_raw),
        "launchagent_plist_sha256": _digest(plist_raw),
        "maximum_spend_usd": MAXIMUM_SPEND_USD,
        "modeled_total_usd": contract.modeled_total_usd,
        "no_replay": True,
        "no_restart_restore_or_second_sft": True,
        "optimizer_steps": STEPS,
        "output_directory": RUN_OUTPUT.as_posix(),
        "raw_unconstrained_tinker_only": True,
        "retention_sampling": False,
        "run_id": RUN_ID,
        "source_commit": source_commit,
        "source_hashes": _source_hashes(root),
    }
    if (
        packet != expected_packet
        or not isinstance(source_commit, str)
        or not _GIT_SHA.fullmatch(source_commit)
    ):
        raise Phase3XSFTRunError("execution packet does not bind the exact frozen run")
    verify_source(root, source_commit, contract.candidate_source_commit)
    if authorization != {
        "allowed_secret_name": "TINKER_API_KEY",
        "candidate_sha256sums_sha256": candidate_sha256sums_sha256,
        "candidate_source_commit": contract.candidate_source_commit,
        "decision": "authorized",
        "execution_packet_sha256": _digest(packet_raw),
        "kind": "phase3x-semantic-intent-sft-owner-authorization-v1",
        "maximum_spend_usd": MAXIMUM_SPEND_USD,
        "no_restart_restore_or_second_sft": True,
        "one_sft_only": True,
        "owner_instruction": "okay start",
        "source_commit": source_commit,
    }:
        raise Phase3XSFTRunError("owner authorization does not bind the exact frozen run")
    return contract, packet, authorization


def construct_authorized_provider(
    root: Path,
    *,
    packet_path: Path,
    authorization_path: Path,
    candidate_sha256sums_sha256: str,
    service_factory: Callable[..., Any],
    provider_factory: Callable[..., Any] = TinkerRunProvider,
) -> Any:
    """Construct the reused provider only after the complete pure preflight succeeds."""
    load_authorized_execution(
        root,
        packet_path=packet_path,
        authorization_path=authorization_path,
        candidate_sha256sums_sha256=candidate_sha256sums_sha256,
    )
    verify_launchd()
    return provider_factory(service_factory, RUN_ID, lora_rank=LORA_RANK, phase="phase3x")


@dataclass(slots=True)
class Phase3XSpendLedger:
    """Fail-closed operation/storage ledger over the checksum-bound cost model."""

    cost: Mapping[str, object]
    training_steps: int = 0
    evaluation_requests: int = 0
    state_checkpoints: int = 0
    sampler_checkpoints: int = 0
    checkpoint_bytes: int = 0

    def __post_init__(self) -> None:
        if float(self.cost["modeled_total_usd"]) > MAXIMUM_SPEND_USD:
            raise Phase3XSFTRunError("modeled spend exceeds the owner ceiling")

    def train(self) -> None:
        self.training_steps += 1
        self._check()

    def evaluate(self, count: int) -> None:
        self.evaluation_requests += count
        self._check()

    def checkpoint(self, kind: str, size: int) -> None:
        storage = self.cost.get("storage_assumptions")
        if not isinstance(storage, Mapping) or isinstance(size, bool) or size <= 0:
            raise Phase3XSFTRunError("checkpoint storage evidence is malformed")
        if kind == "state":
            self.state_checkpoints += 1
            ceiling = storage.get("full_checkpoint_bytes_each")
        elif kind == "sampler":
            self.sampler_checkpoints += 1
            ceiling = storage.get("sampler_checkpoint_bytes_each")
        else:
            raise Phase3XSFTRunError("unknown checkpoint ledger kind")
        if not isinstance(ceiling, int) or size > ceiling:
            raise Phase3XSFTRunError("checkpoint exceeds checksum-bound storage assumption")
        self.checkpoint_bytes += size
        self._check()

    def _check(self) -> None:
        if (
            self.training_steps > STEPS
            or self.evaluation_requests > 911
            or self.state_checkpoints > 3
            or self.sampler_checkpoints > 4
            or float(self.cost["modeled_total_usd"]) > MAXIMUM_SPEND_USD
        ):
            raise Phase3XSFTRunError("paid operation ledger exceeded the authorized envelope")

    def evidence(self) -> dict[str, object]:
        return {
            "ceiling_usd": MAXIMUM_SPEND_USD,
            "checkpoint_bytes": self.checkpoint_bytes,
            "evaluation_requests": self.evaluation_requests,
            "modeled_total_usd": self.cost["modeled_total_usd"],
            "sampler_checkpoints": self.sampler_checkpoints,
            "state_checkpoints": self.state_checkpoints,
            "training_steps": self.training_steps,
        }


def _semantic_action_matches(
    expected: object, actual: object, *, intent_match: bool = False
) -> bool:
    expected_type = getattr(expected, "type", None)
    if isinstance(actual, LanguageRealizationRequest):
        reference = (
            getattr(expected, "reply_to_event_id", None)
            if actual.type == "respond"
            else getattr(expected, "result_event_id", None)
        )
        return (
            expected_type == actual.type
            and reference == actual.reference_event_id
            and (actual.type != "respond" or intent_match)
        )
    if actual is None or getattr(actual, "type", None) != expected_type:
        return False
    left = expected.model_dump(mode="json")
    right = actual.model_dump(mode="json")
    if expected_type in {"respond", "integrate"}:
        left.pop("text", None)
        right.pop("text", None)
    return canonical_artifact_bytes(left) == canonical_artifact_bytes(right)


def _unsafe_resolution(actual: object, *, licensed: bool, resolved: bool) -> bool:
    if isinstance(actual, LanguageRealizationRequest):
        return not resolved
    return licensed and getattr(actual, "type", None) not in (None, "idle") and not resolved


class Phase3XEvaluator:
    """Persist raw Tinker generations first, then grade semantic intent and resolution."""

    def __init__(
        self,
        root: Path,
        output: Path,
        tokenizer: Any,
        contract: Phase3XSFTContract,
        provider: TinkerRunProvider,
        states: tuple[Any, ...],
    ) -> None:
        self.root, self.output = root, output
        self.tokenizer, self.contract, self.provider = tokenizer, contract, provider
        self.states = {state.state_id: state for state in states}
        proof_rows = contract.dev_proof["rows"]
        self.proof = {str(row["state_id"]): row for row in proof_rows}
        self.requests = {
            kind: [
                _json(raw, f"{kind} materialized request")
                for raw in gzip.decompress(path.read_bytes()).splitlines()
            ]
            for kind, path in contract.evaluation_artifacts.items()
        }
        if set(self.states) != set(self.proof) or len(self.states) != 300:
            raise Phase3XSFTRunError("runtime DEV reconstruction drifted from candidate proof")

    async def __call__(self, kind: str, step: int, sampler_path: str) -> Mapping[str, object]:
        rows = self.requests[kind]
        client = await _provider_result(self.provider.sampling_client(sampler_path))
        grades: list[dict[str, object]] = []
        raw_directory = self.output / f"evaluations/step-{step:03d}/{kind}/raw"
        for row in rows:
            state_id = str(row["state_id"])
            started = time.monotonic()
            response = await _provider_result(
                client.sample_async(
                    prompt=tinker.ModelInput.from_ints(list(row["input_tokens"])),
                    num_samples=1,
                    sampling_params=tinker.SamplingParams(
                        max_tokens=256,
                        seed=SEED,
                        stop=[TERMINAL_TOKEN_ID],
                        temperature=0.0,
                        top_p=1.0,
                    ),
                )
            )
            if len(response.sequences) != 1:
                raise Phase3XSFTRunError("Tinker returned an unexpected sample count")
            sequence = response.sequences[0]
            tokens = tuple(sequence.tokens)
            decoded = self.tokenizer.tokenizer.decode(tokens, skip_special_tokens=False)
            if not isinstance(decoded, str):
                raise Phase3XSFTRunError("pinned tokenizer failed to decode DEV output")
            raw = capture_raw_generation(
                evaluation_run_id=RUN_ID,
                model_identity=BACKBONE,
                checkpoint_identity=sampler_path,
                sampling_manifest_sha256=_digest(
                    canonical_artifact_bytes(self.contract.evaluation_inventory)
                ),
                state_id=state_id,
                output_token_ids=tokens,
                decoded_bytes=decoded.encode(),
                finish_reason=str(sequence.stop_reason),
                latency_ms=round((time.monotonic() - started) * 1000),
            )
            persisted = persist_raw_generation(self.root, raw_directory, raw)
            # Raw bytes are durable before framing, parsing, resolution, or metric mutation.
            grades.append(
                _grade_evaluation(
                    self,
                    state_id,
                    tokens,
                    decoded.encode(),
                    str(sequence.stop_reason),
                    persisted.sha256,
                )
            )
        metrics = _evaluation_metrics(grades, step)
        directory = raw_directory.parent
        grades_raw = b"".join(canonical_artifact_bytes(row) + b"\n" for row in grades)
        metrics_raw = canonical_artifact_bytes(metrics)
        (directory / "grades.jsonl").write_bytes(grades_raw)
        (directory / "metrics.json").write_bytes(metrics_raw)
        (directory / "SHA256SUMS").write_text(
            f"{sha256(grades_raw).hexdigest()}  grades.jsonl\n"
            f"{sha256(metrics_raw).hexdigest()}  metrics.json\n",
            encoding="ascii",
        )
        return metrics


def _grade_evaluation(
    evaluator: Phase3XEvaluator,
    state_id: str,
    tokens: tuple[int, ...],
    decoded: bytes,
    finish_reason: str,
    raw_sha: str,
) -> dict[str, object]:
    state = evaluator.states[state_id]
    raw_valid = exact_intent = resolved = False
    actual: object = None
    try:
        projection = project_terminal_output(
            finish_reason=finish_reason,
            output_token_ids=tokens,
            decoded_bytes=decoded,
            tokenizer=evaluator.tokenizer.tokenizer,
        )
        typed = POLICY_INTENT_ADAPTER.validate_python(parse_tim_json(projection.parser_input))
        intent = typed.model_dump(mode="json")
        raw_valid = True
        exact_intent = (
            _digest(canonicalize_tim_json(intent)) == evaluator.proof[state_id]["intent_sha256"]
        )
        registry = IntentRegistry.from_state(
            state.boundary.license_view,
            state.boundary.policy_bytes,
            sha256(state.boundary.policy_bytes).hexdigest(),
        )
        actual = resolve_policy_intent(intent, registry).value
        resolved = _semantic_action_matches(state.expected, actual, intent_match=exact_intent)
    except (TerminalFramingError, TypeError, ValueError):
        pass
    actual_type = getattr(actual, "type", None)
    licensed_action = actual
    if isinstance(actual, LanguageRealizationRequest) and actual.type == "integrate":
        licensed_action = complete_language_realization(actual, None).value
    licensed = (
        licensed_action is not None
        and not isinstance(licensed_action, LanguageRealizationRequest)
        and isinstance(check(licensed_action, state.boundary.license_view), Allowed)
    )
    tags = sentinel_tags(state)
    mismatch_nonidle = _unsafe_resolution(actual, licensed=licensed, resolved=resolved)
    return {
        "active_floor_premature_respond": "hard:active_floor" in tags and actual_type == "respond",
        "duplicate_delegate_or_schedule": (
            "hard:duplicate_delegate_negative" in tags
            and actual_type == "delegate"
            or "hard:duplicate_schedule_negative" in tags
            and actual_type == "schedule"
        ),
        "exact_intent": exact_intent,
        "licensed": licensed,
        "mark_semantic_selection": state.action_type == "mark" and resolved and licensed,
        "raw_generation_sha256": raw_sha,
        "raw_intent_valid": raw_valid,
        "response_kind_match": state.action_type == "respond"
        and actual_type == "respond"
        and resolved,
        "resolved_external_action": resolved
        and (licensed or isinstance(actual, LanguageRealizationRequest)),
        "resolved_six_action": state.action_type
        in {"cancel", "delegate", "integrate", "mark", "nudge", "schedule"}
        and resolved
        and licensed,
        "resolver_match": resolved,
        "state_id": state_id,
        "timer_lifecycle_invalid": state.action_type in {"cancel", "nudge", "schedule"}
        and not (resolved and licensed),
        "unsafe_resolved_execution": mismatch_nonidle,
        "wrong_rollover_mutation": state.rollover and mismatch_nonidle,
    }


def _evaluation_metrics(grades: list[Mapping[str, object]], step: int) -> dict[str, object]:
    def count(name: str) -> int:
        return sum(row.get(name) is True for row in grades)

    metrics = {
        "active_floor_premature_respond_count": count("active_floor_premature_respond"),
        "duplicate_delegate_or_schedule_count": count("duplicate_delegate_or_schedule"),
        "licensed_action_count": count("licensed"),
        "mark_semantic_selection_count": count("mark_semantic_selection"),
        "raw_unconstrained_intent_valid_count": count("raw_intent_valid"),
        "response_kind_match_count": count("response_kind_match"),
        "request_count": len(grades),
        "resolved_external_action_count": count("resolved_external_action"),
        "resolved_six_action_count": count("resolved_six_action"),
        "resolver_match_count": count("resolver_match"),
        "step": step,
        "timer_lifecycle_invalid_count": count("timer_lifecycle_invalid"),
        "unsafe_resolved_execution_count": count("unsafe_resolved_execution"),
        "wrong_rollover_mutation_count": count("wrong_rollover_mutation"),
    }
    if len(grades) == 300:
        metrics["aspirational_gate_passed"] = (
            metrics["raw_unconstrained_intent_valid_count"] >= 294
            and metrics["resolved_six_action_count"] >= 111
            and metrics["mark_semantic_selection_count"] >= 27
            and metrics["response_kind_match_count"] == 14
            and all(
                metrics[name] == 0
                for name in (
                    "active_floor_premature_respond_count",
                    "duplicate_delegate_or_schedule_count",
                    "timer_lifecycle_invalid_count",
                    "unsafe_resolved_execution_count",
                    "wrong_rollover_mutation_count",
                )
            )
        )
    return metrics


def _batch_loss(datums: list[tinker.Datum], result: object) -> float:
    outputs = getattr(result, "loss_fn_outputs", None)
    if not isinstance(outputs, list | tuple) or len(outputs) != len(datums):
        raise Phase3XSFTRunError("provider returned malformed loss evidence")
    loss_sum = mass = 0.0
    for datum, output in zip(datums, outputs, strict=True):
        logprobs = output["logprobs"].to_numpy().reshape(-1)
        weights = datum.loss_fn_inputs["weights"].to_numpy().reshape(-1)
        if len(logprobs) != len(weights):
            raise Phase3XSFTRunError("provider loss tensors differ from frozen datum")
        for logprob, weight in zip(logprobs, weights, strict=True):
            value = float(weight)
            loss_sum += -float(logprob) * value
            mass += value
    if mass <= 0 or not math.isfinite(loss_sum):
        raise Phase3XSFTRunError("provider returned empty or non-finite loss evidence")
    return loss_sum / mass


def _select_checkpoint(
    contract: Phase3XSFTContract,
    evaluations: Mapping[int, Mapping[str, object]],
    states: Mapping[int, str],
) -> dict[str, object]:
    fallback = contract.evaluation.get("selection_fallback")
    ranking = fallback.get("ranking") if isinstance(fallback, Mapping) else None
    if (
        not isinstance(fallback, Mapping)
        or fallback.get("eligible_steps") != [20, 40, 63]
        or not isinstance(ranking, list)
        or set(evaluations) != {20, 40, 63}
        or set(states) != {20, 40, 63}
    ):
        raise Phase3XSFTRunError("mandatory checkpoint selection contract drifted")
    expected_ranking = [
        ("resolved_external_action_count", "descending"),
        ("unsafe_resolved_execution_count", "ascending"),
        ("wrong_rollover_mutation_count", "ascending"),
        ("timer_lifecycle_invalid_count", "ascending"),
        ("active_floor_premature_respond_count", "ascending"),
        ("duplicate_delegate_or_schedule_count", "ascending"),
        ("resolved_six_action_count", "descending"),
        ("mark_semantic_selection_count", "descending"),
        ("raw_unconstrained_intent_valid_count", "descending"),
        ("step", "ascending"),
    ]
    if [
        (row.get("metric"), row.get("direction")) if isinstance(row, Mapping) else None
        for row in ranking
    ] != expected_ranking:
        raise Phase3XSFTRunError("checkpoint fallback ranking drifted")
    eligible = [
        step for step, metrics in evaluations.items() if metrics.get("aspirational_gate_passed")
    ] or list(evaluations)

    def key(step: int) -> tuple[float, ...]:
        metrics = evaluations[step]
        values = []
        for metric, direction in expected_ranking:
            value = step if metric == "step" else metrics.get(metric)
            if isinstance(value, bool) or not isinstance(value, int | float):
                raise Phase3XSFTRunError("checkpoint selection metric is malformed")
            values.append(-float(value) if direction == "descending" else float(value))
        return tuple(values)

    selected = min(eligible, key=key)
    return {
        "aspirational_gate_passed": evaluations[selected].get("aspirational_gate_passed") is True,
        "metrics": dict(evaluations[selected]),
        "selected_state_path": states[selected],
        "selected_step": selected,
        "selection_mode": "passing_gate"
        if evaluations[selected].get("aspirational_gate_passed")
        else "mandatory_fail_closed_fallback",
    }


def _seal_output(output: Path) -> str:
    paths = sorted(
        path for path in output.rglob("*") if path.is_file() and path != output / "SHA256SUMS"
    )
    sums = "".join(
        f"{sha256(path.read_bytes()).hexdigest()}  {path.relative_to(output).as_posix()}\n"
        for path in paths
    ).encode("ascii")
    (output / "SHA256SUMS").write_bytes(sums)
    return _digest(sums)


def capture_detached_logs(root: Path, output_path: Path = RUN_OUTPUT) -> Mapping[str, object]:
    """Bind exited LaunchAgent stdout/stderr into the create-only run evidence."""
    root = root.resolve(strict=True)
    output = _inside(root, output_path)
    result = subprocess.run(
        ["launchctl", "print", f"gui/{os.getuid()}/{LAUNCHD_LABEL}"],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    if result.returncode == 0 and "pid =" in result.stdout:
        raise Phase3XSFTRunError("detached logs may be captured only after process exit")
    captured: dict[str, str] = {}
    for name, source in (("stdout.log", STDOUT_LOG), ("stderr.log", STDERR_LOG)):
        destination = output / name
        if destination.exists() or not source.is_file() or source.is_symlink():
            raise Phase3XSFTRunError("detached log evidence is missing or already captured")
        raw = source.read_bytes()
        destination.write_bytes(raw)
        captured[name] = _digest(raw)
    receipt = {
        "kind": "phase3x-semantic-intent-sft-detached-log-capture-v1",
        "launchd_label": LAUNCHD_LABEL,
        "logs": captured,
    }
    (output / "detached-log-capture.json").write_bytes(canonical_artifact_bytes(receipt))
    _seal_output(output)
    return receipt


async def execute(
    *,
    root: Path,
    packet_path: Path,
    authorization_path: Path,
    candidate_sha256sums_sha256: str,
    output_path: Path = RUN_OUTPUT,
    service_factory: Callable[..., Any] = tinker.ServiceClient,
    provider_factory: Callable[..., Any] = TinkerRunProvider,
    secret_reader: Callable[[Path], str] = read_tinker_api_key,
    evaluator_factory: Callable[..., Any] = Phase3XEvaluator,
) -> Mapping[str, object]:
    """Execute exactly one authorized trajectory; no restore, continuation, or retry path exists."""
    root = root.resolve(strict=True)
    contract, packet, authorization = load_authorized_execution(
        root,
        packet_path=packet_path,
        authorization_path=authorization_path,
        candidate_sha256sums_sha256=candidate_sha256sums_sha256,
    )
    verify_launchd()
    if output_path != RUN_OUTPUT or (root / output_path).exists():
        raise Phase3XSFTRunError("run output is non-canonical or already exists")
    output = root / output_path
    output.mkdir(mode=0o700, parents=True)
    status: dict[str, object] = {
        "candidate_sha256sums_sha256": candidate_sha256sums_sha256,
        "candidate_source_commit": contract.candidate_source_commit,
        "executed_steps": 0,
        "kind": "phase3x-semantic-intent-sft-run-status-v1",
        "run_id": RUN_ID,
        "status": "running",
    }
    stages: list[dict[str, str]] = []
    _stage(
        output,
        status,
        stages,
        "preflight_complete",
        {
            "authorization_sha256": _digest(_inside(root, authorization_path).read_bytes()),
            "candidate_sha256sums_sha256": candidate_sha256sums_sha256,
            "execution_packet_sha256": _digest(_inside(root, packet_path).read_bytes()),
            "modeled_total_usd": contract.modeled_total_usd,
            "owner_decision": authorization["decision"],
            "source_commit": packet["source_commit"],
        },
    )
    provider: Any = None
    all_checkpoints: list[str] = []
    sampler_paths: list[str] = []
    state_paths: dict[int, str] = {}
    evaluations: dict[int, Mapping[str, object]] = {}
    ledger: Phase3XSpendLedger | None = None
    selected_path: str | None = None
    try:
        tokenizer = load_pinned_tokenizer(root, root / TOKENIZER_DIRECTORY)
        states = await rebuild_dev_states(root, tokenizer)
        key = secret_reader(root / ".env")
        os.environ["TINKER_API_KEY"] = key
        key = ""
        ledger = Phase3XSpendLedger(contract.cost)
        provider = provider_factory(service_factory, RUN_ID, lora_rank=16, phase="phase3x")
        identity = await _provider_result(provider.initialize())
        if any(
            identity.get(name) != value
            for name, value in {
                "base_model": BACKBONE,
                "is_lora": True,
                "lora_rank": 16,
                "train_attn": True,
                "train_mlp": True,
                "train_unembed": False,
            }.items()
        ):
            raise Phase3XSFTRunError("provider identity differs from the frozen adapter")
        _stage(output, status, stages, "provider_identity", dict(identity))
        client = await _provider_result(provider.create_training_client())
        evaluator = evaluator_factory(root, output, tokenizer, contract, provider, states)
        for step, batch in enumerate(contract.batches, start=1):
            if batch.step_in_epoch != step:
                raise Phase3XSFTRunError("runtime batch order drifted")
            data = [contract.datums[datum_id].tinker_datum() for datum_id in batch.datum_ids]
            forward = await _provider_result(client.forward_backward_async(data, "cross_entropy"))
            loss = _batch_loss(data, forward)
            optimizer = await _provider_result(
                client.optim_step_async(
                    tinker.AdamParams(**(OPTIMIZER | {"learning_rate": learning_rate(step)}))
                )
            )
            ledger.train()
            gradient = _gradient_evidence(getattr(optimizer, "metrics", None))
            status["executed_steps"] = step
            _stage(
                output,
                status,
                stages,
                "optimizer_update",
                {
                    "gradient": gradient,
                    "learning_rate": learning_rate(step),
                    "loss": loss,
                    "step": step,
                },
            )
            if step in FULL_DEV_STEPS:
                saved = await _provider_result(
                    client.save_state_async(f"phase3x-state-{step}", ttl_seconds=None)
                )
                state_path = _checkpoint_path(saved)
                all_checkpoints.append(state_path)
                state_paths[step] = state_path
                size = await _provider_result(provider.checkpoint_size(state_path))
                metadata = await _provider_result(provider.checkpoint_metadata(state_path))
                if metadata.get("checkpoint_is_durable") is not True:
                    raise Phase3XSFTRunError("full-state checkpoint is not durable")
                ledger.checkpoint("state", size)
                _stage(
                    output,
                    status,
                    stages,
                    "state_checkpoint",
                    {"path": state_path, "size_bytes": size, "step": step, **dict(metadata)},
                )
            if step in SAMPLER_STEPS:
                saved = await _provider_result(
                    client.save_weights_for_sampler_async(
                        f"phase3x-sampler-{step}", ttl_seconds=SAMPLER_TTL_SECONDS
                    )
                )
                sampler_path = _checkpoint_path(saved)
                all_checkpoints.append(sampler_path)
                sampler_paths.append(sampler_path)
                size = await _provider_result(provider.checkpoint_size(sampler_path))
                metadata = await _provider_result(provider.checkpoint_metadata(sampler_path))
                if (
                    metadata.get("checkpoint_is_durable") is not False
                    or not isinstance(metadata.get("remaining_ttl_seconds"), int)
                    or int(metadata["remaining_ttl_seconds"]) <= 0
                ):
                    raise Phase3XSFTRunError("sampler checkpoint TTL evidence is malformed")
                ledger.checkpoint("sampler", size)
                kind = evaluation_at(step)
                if kind is None:
                    raise Phase3XSFTRunError("sampler schedule has no evaluation kind")
                result = await evaluator(kind, step, sampler_path)
                request_count = result.get("request_count")
                if not isinstance(request_count, int):
                    raise Phase3XSFTRunError("evaluation omitted request count")
                ledger.evaluate(request_count)
                _stage(output, status, stages, "evaluation", {"kind": kind, **dict(result)})
                if step in FULL_DEV_STEPS:
                    evaluations[step] = result
        if status["executed_steps"] != 63:
            raise Phase3XSFTRunError("one-run trajectory did not reach step 63")
        selection = _select_checkpoint(contract, evaluations, state_paths)
        selected_path = str(selection["selected_state_path"])
        (output / "checkpoint-selection.json").write_bytes(canonical_artifact_bytes(selection))
        _stage(output, status, stages, "mandatory_checkpoint_selection", selection)
        for path in all_checkpoints:
            if path != selected_path:
                await _provider_result(provider.delete_checkpoint(path))
                _stage(
                    output, status, stages, "checkpoint_cleanup", {"deleted": True, "path": path}
                )
        status.update(
            {
                "selected_state_path": selected_path,
                "selected_step": selection["selected_step"],
                "spend_ledger": ledger.evidence(),
                "status": "completed_selected_one_checkpoint",
            }
        )
    except BaseException as error:
        status.update({"error_type": type(error).__name__, "status": "failed_pipeline"})
        if provider is not None:
            for path in all_checkpoints:
                if path == selected_path:
                    continue
                try:
                    await _provider_result(provider.delete_checkpoint(path))
                except BaseException:
                    status.setdefault("cleanup_failures", []).append(path)
        raise
    finally:
        os.environ.pop("TINKER_API_KEY", None)
        _write_status(output / "status.json", status)
        _seal_output(output)
    return status
