"""Fail-closed, detached executor for the approved Phase 3R rank-16 LR-5e-5 run.

This module deliberately has no import-time provider, checkpoint, or secret access.
``execute`` is the sole paid path and stops at (or before) global step 40.
"""

from __future__ import annotations

import json
import math
import os
import plistlib
import re
import subprocess
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

import tinker

from im.assets.model import canonical_artifact_bytes
from im.training.phase3_data import load_pinned_tokenizer
from im.training.phase3_full_run import (
    _checkpoint_path,
    _gradient_evidence,
    _provider_result,
    _stage,
    _write_status,
)
from im.training.phase3_full_tinker import (
    TinkerEvaluator,
    TinkerRunProvider,
    _load_sampling_requests,
)
from im.training.phase3_sampling import read_tinker_api_key
from im.training.phase3r import (
    repeated_ngram_signature,
    repetition_diagnostics_v3,
    retention_catastrophe_v3,
)
from im.training.phase3r_rank16_run import (
    BATCH_PLAN_SHA256,
    DATUMS_SHA256,
    Rank16Contract,
    Rank16RunError,
    _evaluator_contract,
    _loss_breakdown,
)
from im.training.phase3r_rank16_run import (
    load_contract as load_rank16_contract,
)

CANDIDATE = Path("review/phase3/wp3r-8-rank16-lr5e5-step40-candidate-v2")
FREEZE_APPROVAL = Path("review/phase3/wp3r-8-rank16-lr5e5-step40-freeze-approval-v1")
EXECUTION_DIRECTORY = Path("review/phase3/wp3r-8-rank16-lr5e5-step40-paid-execution-v2")
RUN_OUTPUT = Path("review/phase3/wp3r-8-rank16-lr5e5-step40-run-v2")
EARLY_FAILURE_OUTPUT = Path("review/phase3/wp3r-8-rank16-lr5e5-step40-early-failure-v2")
TOKENIZER_DIRECTORY = Path(".cache/replay-sources/995ad96eacd98c81ed38be0c5b274b04031597b0")
RUN_ID = "phase3r-rank16-lr5e5-step40-v2"
LAUNCHD_LABEL = "com.interactionmodel.phase3r-rank16-lr5e5-step40-v2"
LAUNCHD_ENV = "PHASE3R_RANK16_LR5E5_LAUNCHD_LABEL"
STDOUT_LOG = Path.home() / "Library/Logs/interactionmodel-phase3r-rank16-lr5e5-v2.stdout.log"
STDERR_LOG = Path.home() / "Library/Logs/interactionmodel-phase3r-rank16-lr5e5-v2.stderr.log"
EXPECTED_CANDIDATE_SUMS = "sha256:2a25dba756039167524b996522d2210392a8c245090cde5bc9b4b1cb055d020c"
EXPECTED_FREEZE_APPROVAL_SUMS = (
    "sha256:85893c0eea81c66bebc8048efd0abb9fa033285fd6bfe5012da36e4b53b89b55"
)
EXPECTED_RANK16_SUMS = "sha256:056c1238a899d45fa78902940793a9a1d602820b195b11ab157b5109b0b2e139"
EXPECTED_DETECTOR_SUMS = "sha256:e0c9e6b7f26b07665390ac560eff26535365ada471f06abdf93a9439a892aae6"
PREDECESSOR_RUN_SUMS = "sha256:a015973801163bb0d169ee3e2cc98a06a5a8d62192ef90377fa5cf7018bff1f6"
PREDECESSOR_STATUS_SHA256 = (
    "sha256:1068a383d9c1312f9828ad001cd81e57dededd69329c5c2df2d69b06026772b1"
)
MAXIMUM_SPEND_USD = 39
STATE_BYTES_EACH = 3_305_164_149
SAMPLER_BYTES_EACH = 1_102_005_840
MAXIMUM_STATE_BYTES = STATE_BYTES_EACH * 3
MAXIMUM_SAMPLER_BYTES = SAMPLER_BYTES_EACH * 6
STATE_TTL_SECONDS = 777_600
SAMPLER_TTL_SECONDS = 3_600
SEED = 20260801
MAX_STEP = 40
EVALUATION_STEPS = frozenset({10, 20, 25, 30, 35, 40})
SCHEDULED_STATE_STEPS = frozenset({20, 30, 40})
CONDITIONAL_STATE_STEPS = frozenset({10, 25, 35})
FULL_DEV_STEPS = frozenset({20, 30, 40})
FAST_DEV_STEPS = frozenset({10})
TOKENIZER_FILE_SHA256S = {
    "chat_template.jinja": (
        "sha256:e84f32a23fdda27689f868aa4a1a5621f41133e51a48d7f3efcbea2839574259"
    ),
    "merges.txt": "sha256:a9d356d7bdf1ef4949e3e748e95b8e10ad9d4e2e838eddc38a0a7b6b94d1db8d",
    "tokenizer.json": "sha256:5f9e4d4901a92b997e463c1f46055088b6cca5ca61a6522d1b9f64c4bb81cb42",
    "tokenizer_config.json": (
        "sha256:5186f0defcd7f232382c7f0aebcd2252d073bb921ab240e407b7ae8745d2b29b"
    ),
    "vocab.json": "sha256:ce99b4cb2983d118806ce0a8b777a35b093e2000a503ebde25853284c9dfa003",
}
OPTIMIZER = {
    "beta1": 0.9,
    "beta2": 0.95,
    "eps": 1e-8,
    "weight_decay": 0.0,
    "grad_clip_norm": 1.0,
}
_SOURCE_PATHS = (
    Path("src/im/training/phase3r_rank16_lr5e5_run.py"),
    Path("scripts/run_phase3r_rank16_lr5e5_step40.py"),
    Path("tests/test_phase3r_rank16_lr5e5_run.py"),
)


class LR5E5RunError(Rank16RunError):
    """The v2 paid-execution boundary did not close."""


@dataclass(slots=True)
class StorageLedger:
    """Full-month storage envelope from the $39 immutable cost model."""

    state_bytes: int = 0
    state_objects: int = 0
    sampler_bytes: int = 0
    sampler_objects: int = 0

    def add_state(self, size: object) -> int:
        if not isinstance(size, int) or isinstance(size, bool) or not 0 < size <= STATE_BYTES_EACH:
            raise LR5E5RunError("full state exceeds the model-specific storage upper input")
        self.state_bytes += size
        self.state_objects += 1
        if self.state_objects > 3 or self.state_bytes > MAXIMUM_STATE_BYTES:
            raise LR5E5RunError("full-state count exceeds the three-state $39 envelope")
        return size

    def add_sampler(self, size: object) -> int:
        if (
            not isinstance(size, int)
            or isinstance(size, bool)
            or not 0 < size <= SAMPLER_BYTES_EACH
        ):
            raise LR5E5RunError("sampler exceeds the model-specific storage upper input")
        self.sampler_bytes += size
        self.sampler_objects += 1
        if self.sampler_objects > 6 or self.sampler_bytes > MAXIMUM_SAMPLER_BYTES:
            raise LR5E5RunError("sampler exports exceed the six-object $39 envelope")
        return size


@dataclass(frozen=True, slots=True)
class LR5E5Contract:
    rank16: Rank16Contract
    raw: Mapping[str, object]
    cost: Mapping[str, object]
    approval: Mapping[str, object]


def _digest(raw: bytes) -> str:
    return f"sha256:{sha256(raw).hexdigest()}"


def _json(path: Path) -> Mapping[str, object]:
    value = json.loads(path.read_bytes())
    if not isinstance(value, Mapping):
        raise LR5E5RunError(f"expected JSON object: {path.name}")
    return value


def _verify_sums(directory: Path, *, allowed_extra: frozenset[str] = frozenset()) -> None:
    names: set[str] = set()
    for line in (directory / "SHA256SUMS").read_text(encoding="ascii").splitlines():
        expected, name = line.split("  ", 1)
        if (
            Path(name).name != name
            or _digest((directory / name).read_bytes()) != f"sha256:{expected}"
        ):
            raise LR5E5RunError("candidate checksum entry drifted")
        names.add(name)
    actual = (
        {item.name for item in directory.iterdir() if item.is_file()}
        - {"SHA256SUMS"}
        - allowed_extra
    )
    if names != actual:
        raise LR5E5RunError("candidate checksum inventory drifted")


def load_contract(root: Path) -> LR5E5Contract:
    """Load only immutable offline bytes; this does not initialize a provider."""
    root = root.resolve(strict=True)
    candidate = root / CANDIDATE
    if _digest((candidate / "SHA256SUMS").read_bytes()) != EXPECTED_CANDIDATE_SUMS:
        raise LR5E5RunError("approved v2 candidate root drifted")
    _verify_sums(candidate)
    raw = _json(candidate / "experiment-contract.json")
    cost = _json(candidate / "cost-model.json")
    report = _json(candidate / "candidate-report.json")
    approval_directory = root / FREEZE_APPROVAL
    if _digest((approval_directory / "SHA256SUMS").read_bytes()) != EXPECTED_FREEZE_APPROVAL_SUMS:
        raise LR5E5RunError("owner freeze-approval root drifted")
    _verify_sums(approval_directory)
    approval = _json(approval_directory / "owner-decision.json")
    source = raw.get("source_artifact_hashes", {})
    optimizer = raw.get("optimizer", {})
    schedule = raw.get("schedule", {})
    if (
        not isinstance(source, Mapping)
        or not isinstance(optimizer, Mapping)
        or not isinstance(schedule, Mapping)
    ):
        raise LR5E5RunError("v2 candidate has malformed immutable sections")
    if (
        raw.get("kind") != "phase3r-rank16-lr5e5-step40-contract-v2"
        or source.get("rank16_root_sha256sums") != EXPECTED_RANK16_SUMS
        or source.get("detector_v3_root_sha256sums") != EXPECTED_DETECTOR_SUMS
        or report.get("contract_sha256")
        != _digest((candidate / "experiment-contract.json").read_bytes())
        or report.get("cost_model_sha256") != _digest((candidate / "cost-model.json").read_bytes())
        or approval.get("decision") != "approved"
        or approval.get("approved_candidate", {}).get("root_sha256sums_sha256")
        != EXPECTED_CANDIDATE_SUMS
        or approval.get("maximum_spend_planning_ceiling_usd") != MAXIMUM_SPEND_USD
        or approval.get("authorization", {}).get("paid_execution") is not False
        or optimizer.get("peak_learning_rate") != 5e-5
        or optimizer.get("learning_rate_by_step_1_through_40")
        != [learning_rate(step) for step in range(1, 41)]
        or schedule.get("maximum_global_step") != MAX_STEP
        or schedule.get("automatic_step_41") is not False
        or raw.get("sealed_test") != {"path_argument_allowed": False, "status": "unread"}
        or cost.get("proposed_ceiling_usd") != MAXIMUM_SPEND_USD
        or float(cost.get("modeled_total_usd", math.inf)) > MAXIMUM_SPEND_USD
    ):
        raise LR5E5RunError("candidate does not authorize this exact mechanical run")
    rank16 = load_rank16_contract(root)
    if len(rank16.batches) != 63 or len(rank16.datums) != 3000:
        raise LR5E5RunError("frozen datums or batch plan drifted")
    return LR5E5Contract(rank16, raw, cost, approval)


def learning_rate(step: int) -> float:
    if not 1 <= step <= 126:
        raise LR5E5RunError("scheduler position is outside the frozen horizon")
    if step <= 10:
        return 5e-5 * step / 10
    return 5e-5 * 0.5 * (1 + math.cos(math.pi * (step - 10) / 116))


def verify_local_preflight(root: Path, contract: LR5E5Contract) -> dict[str, object]:
    """Check pinned tokenizer bytes, datum archive, and exact first forty batches."""
    identity = contract.raw["fresh_run_identity_preflight"]
    if not isinstance(identity, Mapping):
        raise LR5E5RunError("identity preflight is malformed")
    tokenizer = identity.get("tokenizer_identity")
    lora = identity.get("lora")
    if not isinstance(tokenizer, Mapping) or not isinstance(lora, Mapping):
        raise LR5E5RunError("identity preflight is incomplete")
    if (
        identity.get("requested_model") != "Qwen/Qwen3.6-35B-A3B"
        or identity.get("batch_plan_sha256") != BATCH_PLAN_SHA256
        or identity.get("datum_archive_sha256") != DATUMS_SHA256
        or lora != {"lora_rank": 16, "train_attn": True, "train_mlp": True, "train_unembed": False}
        or tokenizer.get("pinned_revision") != TOKENIZER_DIRECTORY.name
        or tokenizer.get("pinned_file_sha256s") != TOKENIZER_FILE_SHA256S
    ):
        raise LR5E5RunError("fresh-run identity binding drifted")
    directory = root / TOKENIZER_DIRECTORY
    hashes: dict[str, str] = {}
    for name, expected in TOKENIZER_FILE_SHA256S.items():
        path = directory / name
        if path.is_symlink() or not path.is_file() or _digest(path.read_bytes()) != expected:
            raise LR5E5RunError(f"pinned tokenizer byte drift: {name}")
        hashes[name] = expected
    if len(contract.rank16.batches[:MAX_STEP]) != MAX_STEP or any(
        not batch.membership_sha256 for batch in contract.rank16.batches[:MAX_STEP]
    ):
        raise LR5E5RunError("first forty exact batch memberships are unavailable")
    return {
        "datum_archive_sha256": DATUMS_SHA256,
        "batch_plan_sha256": BATCH_PLAN_SHA256,
        "tokenizer_files": hashes,
    }


def verify_provider_identity(identity: Mapping[str, object]) -> None:
    training = identity.get("training_identity")
    if not isinstance(training, Mapping):
        raise LR5E5RunError("provider did not return explicit training identity")
    if (
        identity.get("base_model") != "Qwen/Qwen3.6-35B-A3B"
        or identity.get("lora_rank") != 16
        or identity.get("train_attn") is not True
        or identity.get("train_mlp") is not True
        or identity.get("train_unembed") is not False
        or training.get("tokenizer_id") != "Qwen/Qwen3.6-35B-A3B"
        or training.get("tokenizer_resolution") != "explicit"
        or training.get("model_data_model_name") != "Qwen/Qwen3.6-35B-A3B"
    ):
        raise LR5E5RunError("provider model/tokenizer/LoRA identity did not exactly match")


def verify_provider_tokenizer_equivalence(
    provider_tokenizer: object, local_tokenizer: object
) -> Mapping[str, object]:
    """Prove exact token-ID namespace equality for the pretokenized Tinker path."""

    def snapshot(tokenizer: object) -> tuple[bytes, bytes, bytes]:
        backend = getattr(tokenizer, "backend_tokenizer", None)
        to_str = getattr(backend, "to_str", None)
        get_vocab = getattr(tokenizer, "get_vocab", None)
        if not callable(to_str) or not callable(get_vocab):
            raise LR5E5RunError("tokenizer exposes no auditable token-ID namespace")
        backend_raw = to_str().encode("utf-8")
        vocab = get_vocab()
        if (
            not isinstance(vocab, Mapping)
            or len(vocab) != 248_077
            or any(
                not isinstance(token, str) or not isinstance(index, int)
                for token, index in vocab.items()
            )
            or set(vocab.values()) != set(range(248_077))
        ):
            raise LR5E5RunError("tokenizer vocabulary is malformed or non-contiguous")
        vocab_raw = canonical_artifact_bytes(dict(vocab))
        special = {
            "all_special_ids": list(getattr(tokenizer, "all_special_ids", ())),
            "chat_template": getattr(tokenizer, "chat_template", None),
            "eos_token_id": getattr(tokenizer, "eos_token_id", None),
            "pad_token_id": getattr(tokenizer, "pad_token_id", None),
            "special_tokens_map": {
                str(key): str(value)
                for key, value in dict(getattr(tokenizer, "special_tokens_map", {})).items()
            },
        }
        return backend_raw, vocab_raw, canonical_artifact_bytes(special)

    provider_backend, provider_vocab, provider_special = snapshot(provider_tokenizer)
    local_backend, local_vocab, local_special = snapshot(local_tokenizer)
    if provider_vocab != local_vocab or provider_special != local_special:
        raise LR5E5RunError("provider and pinned local token-ID namespaces are not equivalent")
    return {
        "backend_serialization_equal": provider_backend == local_backend,
        "equivalence_scope": "exact_pretokenized_token_id_namespace",
        "local_backend_tokenizer_sha256": _digest(local_backend),
        "provider_backend_tokenizer_sha256": _digest(provider_backend),
        "special_and_template_sha256": _digest(local_special),
        "token_id_vocabulary_sha256": _digest(local_vocab),
        "provider_local_exact_token_id_equivalence": True,
        "provider_tokenizer_encoding_or_decoding_used_by_runner": False,
    }


def _verify_source(root: Path, source_commit: str) -> None:
    """Require an exact clean, tracked checkout before a paid secret is read."""
    if not re.fullmatch(r"[0-9a-f]{40}", source_commit):
        raise LR5E5RunError("source commit is malformed")
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if head != source_commit:
        raise LR5E5RunError("paid source commit must exactly match HEAD")
    for path in _SOURCE_PATHS:
        for command in (
            ["git", "ls-files", "--error-unmatch", path.as_posix()],
            ["git", "cat-file", "-e", f"{source_commit}:{path.as_posix()}"],
        ):
            if subprocess.run(command, cwd=root, check=False, capture_output=True).returncode:
                raise LR5E5RunError("paid runner source is not frozen in the declared commit")
    for command in (["git", "diff", "--quiet"], ["git", "diff", "--cached", "--quiet"]):
        if subprocess.run(command, cwd=root, check=False).returncode:
            raise LR5E5RunError("tracked worktree changed after paid source freeze")
    status = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    untracked_outside_evidence = [
        line[3:]
        for line in status
        if line.startswith("?? ") and not line[3:].startswith("review/phase3/")
    ]
    if untracked_outside_evidence:
        raise LR5E5RunError(
            "untracked path outside review/phase3 blocks paid execution: "
            + ", ".join(untracked_outside_evidence)
        )


def _verify_launchd() -> None:
    if (
        sys.platform != "darwin"
        or os.getppid() != 1
        or os.environ.get(LAUNCHD_ENV) != LAUNCHD_LABEL
    ):
        raise LR5E5RunError("paid path must execute as the detached frozen LaunchAgent")
    result = subprocess.run(
        ["launchctl", "print", f"gui/{os.getuid()}/{LAUNCHD_LABEL}"],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    if result.returncode or f"pid = {os.getpid()}" not in result.stdout:
        raise LR5E5RunError("LaunchAgent process identity mismatch")


def _verify_launch_slot_clear() -> None:
    """Reject ambiguous prior jobs or detached logs before packet publication."""
    if sys.platform != "darwin":
        raise LR5E5RunError("detached execution preparation requires macOS")
    result = subprocess.run(
        ["launchctl", "print", f"gui/{os.getuid()}/{LAUNCHD_LABEL}"],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    if result.returncode == 0:
        raise LR5E5RunError("LaunchAgent label is already loaded")
    if STDOUT_LOG.exists() or STDERR_LOG.exists():
        raise LR5E5RunError("detached log path is already occupied")


def _write_sums(directory: Path) -> None:
    names = sorted(
        path.name for path in directory.iterdir() if path.is_file() and path.name != "SHA256SUMS"
    )
    (directory / "SHA256SUMS").write_text(
        "".join(
            f"{sha256((directory / name).read_bytes()).hexdigest()}  {name}\n" for name in names
        ),
        encoding="ascii",
    )


def prepare_execution(root: Path, source_commit: str) -> Path:
    """Make the detached packet; it never reads a secret or calls a provider."""
    root = root.resolve(strict=True)
    if len(source_commit) != 40 or any(char not in "0123456789abcdef" for char in source_commit):
        raise LR5E5RunError("source commit must be a lowercase full SHA")
    _verify_source(root, source_commit)
    _verify_launch_slot_clear()
    contract = load_contract(root)
    verify_local_preflight(root, contract)
    destination = root / EXECUTION_DIRECTORY
    if destination.exists() or (root / RUN_OUTPUT).exists():
        raise LR5E5RunError("canonical execution or output directory already exists")
    destination.mkdir(mode=0o700, parents=True)
    script = root / "scripts/run_phase3r_rank16_lr5e5_step40.py"
    argv = [
        str(root / ".venv/bin/python"),
        str(script),
        "--mode",
        "execute",
        "--repository-root",
        str(root),
        "--source-commit",
        source_commit,
        "--execution-packet",
        (EXECUTION_DIRECTORY / "execution-packet.json").as_posix(),
        "--authorization",
        (EXECUTION_DIRECTORY / "owner-authorization.json").as_posix(),
        "--output",
        RUN_OUTPUT.as_posix(),
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
    (destination / f"{LAUNCHD_LABEL}.plist").write_bytes(plist)
    launch = {
        "bootstrap_argv": [
            "/bin/launchctl",
            "bootstrap",
            f"gui/{os.getuid()}",
            str(destination / f"{LAUNCHD_LABEL}.plist"),
        ],
        "keep_alive": False,
        "kickstart_argv": [
            "/bin/launchctl",
            "kickstart",
            f"gui/{os.getuid()}/{LAUNCHD_LABEL}",
        ],
        "label": LAUNCHD_LABEL,
        "program_arguments": argv,
        "run_at_load": False,
        "status_argv": [
            "/bin/launchctl",
            "print",
            f"gui/{os.getuid()}/{LAUNCHD_LABEL}",
        ],
        "capture_logs_argv": [
            str(root / ".venv/bin/python"),
            str(script),
            "--mode",
            "capture-logs",
            "--repository-root",
            str(root),
        ],
        "bootout_after_log_capture_argv": [
            "/bin/launchctl",
            "bootout",
            f"gui/{os.getuid()}/{LAUNCHD_LABEL}",
        ],
        "stderr_path": str(STDERR_LOG),
        "stdout_path": str(STDOUT_LOG),
    }
    launch_raw = canonical_artifact_bytes(launch)
    (destination / "launch-plan.json").write_bytes(launch_raw)
    packet = {
        "candidate_root_sha256sums_sha256": EXPECTED_CANDIDATE_SUMS,
        "candidate_source_commit": contract.raw["source_commit"],
        "detector_v3_root_sha256sums_sha256": EXPECTED_DETECTOR_SUMS,
        "freeze_approval_root_sha256sums_sha256": EXPECTED_FREEZE_APPROVAL_SUMS,
        "kind": "phase3r-rank16-lr5e5-paid-execution-packet-v2",
        "launch_plan_sha256": _digest(launch_raw),
        "launchagent_plist_sha256": _digest(plist),
        "maximum_spend_usd": MAXIMUM_SPEND_USD,
        "no_application_retry": True,
        "operations": {
            "conditional_state_steps": [10, 25, 35],
            "evaluation_steps": sorted(EVALUATION_STEPS),
            "maximum_step": MAX_STEP,
            "scheduled_state_steps": [20, 30, 40],
        },
        "output_directory": RUN_OUTPUT.as_posix(),
        "predecessor_failed_preflight": {
            "executed_optimizer_steps": 0,
            "root_sha256sums_sha256": PREDECESSOR_RUN_SUMS,
            "status_sha256": PREDECESSOR_STATUS_SHA256,
        },
        "run_id": RUN_ID,
        "prohibited": ["step_41", "TEST", "full_retention_60", "DPO", "automatic_resume"],
        "rank16_root_sha256sums_sha256": EXPECTED_RANK16_SUMS,
        "source_commit": source_commit,
        "tokenizer_equivalence_rule": {
            "backend_wrapper_serialization_is_gating": False,
            "exact_provider_local_token_id_vocabulary_is_gating": True,
            "provider_encoding_or_decoding_used_by_runner": False,
            "scope": "pretokenized_tinker_model_input_and_output_token_ids",
        },
    }
    packet_raw = canonical_artifact_bytes(packet)
    (destination / "execution-packet.json").write_bytes(packet_raw)
    template = {
        "allowed_secret_name": "TINKER_API_KEY",
        "checkpoint_access": True,
        "checkpoint_creation": True,
        "decision": "pending_owner_binding",
        "execution_packet_sha256": _digest(packet_raw),
        "kind": "phase3r-rank16-lr5e5-paid-authorization-template-v2",
        "maximum_spend_usd": MAXIMUM_SPEND_USD,
        "no_application_retry": True,
        "owner_instruction": None,
        "provider_calls": True,
        "sealed_test_access": "forbidden",
        "source_commit": source_commit,
    }
    (destination / "owner-authorization-template.json").write_bytes(
        canonical_artifact_bytes(template)
    )
    _write_sums(destination)
    return destination


def _load_execution(
    root: Path, packet_path: Path, auth_path: Path, source_commit: str
) -> tuple[LR5E5Contract, Mapping[str, object], Mapping[str, object]]:
    contract = load_contract(root)
    directory = root / EXECUTION_DIRECTORY
    _verify_sums(directory, allowed_extra=frozenset({"owner-authorization.json"}))
    packet_file = (packet_path if packet_path.is_absolute() else root / packet_path).resolve(
        strict=True
    )
    auth_file = (auth_path if auth_path.is_absolute() else root / auth_path).resolve(strict=True)
    if (
        packet_file != (directory / "execution-packet.json").resolve()
        or auth_file != (directory / "owner-authorization.json").resolve()
    ):
        raise LR5E5RunError("execution packet or owner authorization path is noncanonical")
    packet, auth = _json(packet_file), _json(auth_file)
    plist_path = directory / f"{LAUNCHD_LABEL}.plist"
    launch_path = directory / "launch-plan.json"
    if (
        packet.get("kind") != "phase3r-rank16-lr5e5-paid-execution-packet-v2"
        or packet.get("source_commit") != source_commit
        or packet.get("candidate_source_commit") != contract.raw["source_commit"]
        or packet.get("rank16_root_sha256sums_sha256") != EXPECTED_RANK16_SUMS
        or packet.get("detector_v3_root_sha256sums_sha256") != EXPECTED_DETECTOR_SUMS
        or packet.get("freeze_approval_root_sha256sums_sha256") != EXPECTED_FREEZE_APPROVAL_SUMS
        or packet.get("maximum_spend_usd") != MAXIMUM_SPEND_USD
        or packet.get("operations")
        != {
            "conditional_state_steps": [10, 25, 35],
            "evaluation_steps": [10, 20, 25, 30, 35, 40],
            "maximum_step": 40,
            "scheduled_state_steps": [20, 30, 40],
        }
        or packet.get("output_directory") != RUN_OUTPUT.as_posix()
        or packet.get("predecessor_failed_preflight")
        != {
            "executed_optimizer_steps": 0,
            "root_sha256sums_sha256": PREDECESSOR_RUN_SUMS,
            "status_sha256": PREDECESSOR_STATUS_SHA256,
        }
        or packet.get("run_id") != RUN_ID
        or packet.get("no_application_retry") is not True
        or packet.get("prohibited")
        != ["step_41", "TEST", "full_retention_60", "DPO", "automatic_resume"]
        or packet.get("tokenizer_equivalence_rule")
        != {
            "backend_wrapper_serialization_is_gating": False,
            "exact_provider_local_token_id_vocabulary_is_gating": True,
            "provider_encoding_or_decoding_used_by_runner": False,
            "scope": "pretokenized_tinker_model_input_and_output_token_ids",
        }
        or packet.get("launchagent_plist_sha256") != _digest(plist_path.read_bytes())
        or packet.get("launch_plan_sha256") != _digest(launch_path.read_bytes())
        or auth.get("kind") != "phase3r-rank16-lr5e5-paid-authorization-v2"
        or auth.get("decision") != "authorized"
        or auth.get("execution_packet_sha256") != _digest(packet_file.read_bytes())
        or auth.get("maximum_spend_usd") != MAXIMUM_SPEND_USD
        or auth.get("no_application_retry") is not True
        or auth.get("allowed_secret_name") != "TINKER_API_KEY"
        or auth.get("checkpoint_access") is not True
        or auth.get("checkpoint_creation") is not True
        or auth.get("provider_calls") is not True
        or auth.get("sealed_test_access") != "forbidden"
        or auth.get("source_commit") != source_commit
        or not isinstance(auth.get("owner_instruction"), str)
        or not str(auth.get("owner_instruction")).strip()
    ):
        raise LR5E5RunError("owner authorization does not bind the exact paid packet")
    _verify_source(root, source_commit)
    _verify_launchd()
    return contract, packet, auth


def _retention_v3(output: Path, step: int) -> Mapping[str, object]:
    directory = output / "evaluations" / f"step-{step:03d}" / "automatic-retention-12"
    raw_paths = sorted((directory / "raw").glob("*/raw-generation.json"))
    if len(raw_paths) != 12:
        raise LR5E5RunError("all twelve raw retention outputs must persist before detector v3")
    report = _json(directory / "report.json")
    old_rows = report.get("rows")
    if not isinstance(old_rows, list) or len(old_rows) != 12:
        raise LR5E5RunError("projected retention report is malformed")
    prior_by_id = {str(row.get("request_id")): row for row in old_rows if isinstance(row, Mapping)}
    rows = []
    evidence = []
    for path in raw_paths:
        record = _json(path)
        tokens = record.get("output_token_ids")
        if not isinstance(tokens, list) or any(not isinstance(token, int) for token in tokens):
            raise LR5E5RunError("retention raw output is malformed")
        state_id = str(record.get("state_id"))
        prior = prior_by_id.get(state_id)
        if not isinstance(prior, Mapping):
            raise LR5E5RunError("projected retention report does not close over raw identities")
        detector = prior.get("catastrophe_detector")
        if not isinstance(detector, Mapping):
            raise LR5E5RunError("projected retention row lacks shared detector findings")
        raw_sha = _digest(path.read_bytes())
        if prior.get("raw_record_sha256") != raw_sha:
            raise LR5E5RunError("projected retention report raw hash drifted")
        if repeated_ngram_signature(tokens) != detector.get("repetition_signature"):
            raise LR5E5RunError("projected retention report repetition evidence drifted")
        diagnostic = repetition_diagnostics_v3(tokens)
        rows.append(
            {
                "empty_output": detector.get("empty_output") is True,
                "high_confidence_generation_loop": diagnostic["high_confidence_generation_loop"],
                "high_confidence_refusal": detector.get("high_confidence_refusal") is True,
                "stylistic_or_structural_repetition": diagnostic[
                    "stylistic_or_structural_repetition"
                ],
                "interaction_protocol_imitation": (
                    detector.get("interaction_protocol_imitation") is True
                ),
                "new_length_termination": detector.get("new_length_termination") is True,
            }
        )
        evidence.append(
            {
                "finish_reason": record.get("finish_reason"),
                "output_token_count": len(tokens),
                "raw_record_sha256": raw_sha,
                "request_id": state_id,
                "projected_detector": detector,
                "v3": diagnostic,
            }
        )
    judgment = retention_catastrophe_v3(rows)
    return {
        "detector_v3": judgment,
        "raw_record_count": len(rows),
        "raw_records_sha256": _digest(
            canonical_artifact_bytes([_digest(path.read_bytes()) for path in raw_paths])
        ),
        "rows": evidence,
    }


def pause_decision(retention: Mapping[str, object], step: int) -> tuple[bool, bool]:
    """Return ``(hard_abort, planner_pause)`` with hard abort taking precedence."""
    detector = retention.get("detector_v3", retention)
    if not isinstance(detector, Mapping):
        raise LR5E5RunError("retention detector v3 is malformed")
    hard = detector.get("abort_optimizer") is True
    single = (
        int(detector.get("high_confidence_generation_loop_count", 0)) >= 1
        or int(detector.get("new_length_termination_count", 0)) >= 1
    )
    return hard, (not hard and (single or step == MAX_STEP))


def _next_batch_membership(contract: LR5E5Contract, next_step: int) -> str | None:
    if not 1 <= next_step <= len(contract.rank16.batches):
        return None
    return contract.rank16.batches[next_step - 1].membership_sha256


def write_pause_control(path: Path, control: Mapping[str, object]) -> str:
    """Atomically persist and fsync the pause handoff plus its parent directory."""
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    raw = canonical_artifact_bytes(dict(control))
    with NamedTemporaryFile(
        mode="wb", dir=path.parent, prefix=f".{path.name}.", delete=False
    ) as temporary:
        temporary.write(raw)
        temporary.flush()
        os.fsync(temporary.fileno())
        temporary_path = Path(temporary.name)
    os.replace(temporary_path, path)
    directory_fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)
    return _digest(raw)


def _modeled_spend_to_step(
    root: Path,
    contract: LR5E5Contract,
    *,
    cumulative_train_tokens: int,
    completed_fast: bool,
    completed_full_steps: frozenset[int],
    completed_retention_steps: frozenset[int],
    storage: StorageLedger,
) -> float:
    """Model only work already completed, using the frozen per-token pricing formula."""
    requests = {str(row["request_id"]): row for row in _load_sampling_requests(root)}
    evaluation = contract.rank16.evaluation
    automatic = evaluation.get("automatic_retention_12", {})
    fast = evaluation.get("step_10", {})
    if not isinstance(automatic, Mapping) or not isinstance(fast, Mapping):
        raise LR5E5RunError("frozen evaluation identities are malformed")
    retention_ids = automatic.get("request_ids")
    fast_ids = fast.get("fast_11_request_ids")
    full_ids = [item for item, row in requests.items() if row.get("kind") == "interaction_dev"]
    if (
        not isinstance(retention_ids, list)
        or not isinstance(fast_ids, list)
        or len(retention_ids) != 12
        or len(fast_ids) != 11
        or len(full_ids) != 300
    ):
        raise LR5E5RunError("frozen evaluation roster count drifted")
    request_ids = list(retention_ids) * len(completed_retention_steps)
    if completed_fast:
        request_ids.extend(fast_ids)
    request_ids.extend(full_ids * len(completed_full_steps))
    if any(not isinstance(item, str) or item not in requests for item in request_ids):
        raise LR5E5RunError("frozen evaluation roster identity drifted")
    prefill = sum(int(requests[item]["input_token_count"]) for item in request_ids)
    pricing = contract.cost.get("pricing_usd")
    if not isinstance(pricing, Mapping):
        raise LR5E5RunError("frozen price schedule is malformed")
    modeled = (
        cumulative_train_tokens * float(pricing["train_per_million_tokens"]) / 1_000_000
        + prefill * float(pricing["uncached_prefill_per_million_tokens"]) / 1_000_000
        + len(request_ids) * 1024 * float(pricing["sample_output_per_million_tokens"]) / 1_000_000
        + (storage.state_bytes + storage.sampler_bytes)
        * float(pricing["checkpoint_gb_month"])
        / 1_000_000_000
    )
    if modeled > MAXIMUM_SPEND_USD:
        raise LR5E5RunError("completed-work upper projection exceeds the $39 hard ceiling")
    return modeled


async def _save_state(
    client: Any,
    provider: TinkerRunProvider,
    output: Path,
    status: dict[str, object],
    stages: list[dict[str, str]],
    storage: StorageLedger,
    step: int,
) -> Mapping[str, object]:
    saved = await _provider_result(
        client.save_state_async(f"phase3r-rank16-lr5e5-state-{step}", ttl_seconds=STATE_TTL_SECONDS)
    )
    path = _checkpoint_path(saved)
    try:
        size = storage.add_state(await _provider_result(provider.checkpoint_size(path)))
        metadata = await _provider_result(provider.checkpoint_metadata(path))
        remaining = metadata.get("remaining_ttl_seconds")
        if metadata.get("checkpoint_is_durable") is not True and (
            not isinstance(remaining, int) or remaining < 691_200
        ):
            raise LR5E5RunError("state TTL cannot preserve required planner review")
    except BaseException:
        try:
            await _provider_result(provider.delete_checkpoint(path))
            _stage(
                output,
                status,
                stages,
                "invalid_state_cleanup",
                {"deleted": True, "path": path, "step": step},
            )
        except BaseException as cleanup_error:
            _stage(
                output,
                status,
                stages,
                "invalid_state_cleanup_failed",
                {
                    "error_type": type(cleanup_error).__name__,
                    "path": path,
                    "step": step,
                    "ttl_fallback_seconds": STATE_TTL_SECONDS,
                },
            )
        raise
    record = {"step": step, "path": path, "size_bytes": size, **metadata}
    _stage(output, status, stages, "exact_full_state", record)
    return record


async def execute(
    *,
    root: Path,
    source_commit: str,
    packet_path: Path,
    authorization_path: Path,
    output_path: Path = RUN_OUTPUT,
    service_factory: Any = tinker.ServiceClient,
    secret_reader: Any = read_tinker_api_key,
) -> Mapping[str, object]:
    """Run exactly the authorized prefix, with no application-level retry or step 41."""
    root = root.resolve(strict=True)
    contract, packet, authorization = _load_execution(
        root, packet_path, authorization_path, source_commit
    )
    local = verify_local_preflight(root, contract)
    if (
        output_path != RUN_OUTPUT
        or (root / output_path).exists()
        or (root / EARLY_FAILURE_OUTPUT).exists()
    ):
        raise LR5E5RunError("canonical run or early-failure evidence already exists")
    output = root / output_path
    status: dict[str, object] = {
        "kind": "phase3r-rank16-lr5e5-run-status-v2",
        "run_id": RUN_ID,
        "status": "running",
        "executed_steps": 0,
        "preflight": local,
        "packet_sha256": _digest((root / packet_path).read_bytes()),
        "authorization_sha256": _digest((root / authorization_path).read_bytes()),
    }
    stages: list[dict[str, str]] = []
    key = ""
    try:
        key = secret_reader(root / ".env")
    except BaseException as error:
        early = root / EARLY_FAILURE_OUTPUT
        early.mkdir(mode=0o700, parents=True)
        status.update(
            {
                "error_type": type(error).__name__,
                "failure_stage": "authorized_secret_read_before_provider_initialization",
                "status": "failed_pre_provider",
            }
        )
        _write_status(early / "status.json", status)
        _seal_run(early)
        os.environ.pop("TINKER_API_KEY", None)
        raise
    provider: TinkerRunProvider | None = None
    sampler_path: str | None = None
    cumulative_tokens = 0
    storage = StorageLedger()
    completed_fast = False
    completed_full_steps: set[int] = set()
    completed_retention_steps: set[int] = set()
    try:
        output.mkdir(mode=0o700, parents=True)
        _stage(output, status, stages, "local_preflight_complete", local)
        os.environ["TINKER_API_KEY"] = key
        key = ""
        provider = TinkerRunProvider(service_factory, RUN_ID, lora_rank=16, phase="phase3r-lr5e5")
        identity = await _provider_result(provider.initialize())
        verify_provider_identity(identity)
        client = await _provider_result(provider.create_training_client())
        tokenizer = load_pinned_tokenizer(root, root / TOKENIZER_DIRECTORY)
        tokenizer_equivalence = verify_provider_tokenizer_equivalence(
            client.get_tokenizer(), tokenizer.tokenizer
        )
        _stage(
            output,
            status,
            stages,
            "provider_identity_pre_step_1",
            {**dict(identity), "tokenizer_equivalence": tokenizer_equivalence},
        )
        evaluator = TinkerEvaluator(
            root, output, tokenizer, _evaluator_contract(contract.rank16), RUN_ID, provider
        )
        for step, batch in enumerate(contract.rank16.batches[:MAX_STEP], start=1):
            data = [contract.rank16.datums[item].tinker_datum() for item in batch.datum_ids]
            cumulative_tokens += sum(
                len(contract.rank16.datums[item].input_tokens) for item in batch.datum_ids
            )
            forward = await _provider_result(client.forward_backward_async(data, "cross_entropy"))
            loss = _loss_breakdown(batch, data, forward)
            _stage(output, status, stages, "loss", {"step": step, **loss})
            lr = learning_rate(step)
            optimizer = await _provider_result(
                client.optim_step_async(tinker.AdamParams(**(OPTIMIZER | {"learning_rate": lr})))
            )
            _stage(
                output,
                status,
                stages,
                "optimizer_update",
                {
                    "step": step,
                    "learning_rate": lr,
                    "gradient": _gradient_evidence(getattr(optimizer, "metrics", None)),
                    "loss": loss,
                },
            )
            status["executed_steps"] = step
            _write_status(output / "status.json", status)
            if step not in EVALUATION_STEPS:
                continue
            state: Mapping[str, object] | None = None
            if step in SCHEDULED_STATE_STEPS:
                state = await _save_state(client, provider, output, status, stages, storage, step)
            sampler = await _provider_result(
                client.save_weights_for_sampler_async(
                    f"phase3r-rank16-lr5e5-sampler-{step}", ttl_seconds=SAMPLER_TTL_SECONDS
                )
            )
            sampler_path = _checkpoint_path(sampler)
            sampler_size = storage.add_sampler(
                await _provider_result(provider.checkpoint_size(sampler_path))
            )
            _stage(
                output,
                status,
                stages,
                "sampler_checkpoint",
                {
                    "step": step,
                    "path": sampler_path,
                    "size_bytes": sampler_size,
                    "ttl_seconds": SAMPLER_TTL_SECONDS,
                },
            )
            try:
                persisted = await evaluator(
                    "automatic_retention_12", step, sampler_path, contract.rank16.retention_rows
                )
                _stage(
                    output,
                    status,
                    stages,
                    "automatic_retention_12_persisted",
                    {"step": step, **dict(persisted)},
                )
                completed_retention_steps.add(step)
                retention = _retention_v3(output, step)
                _stage(
                    output, status, stages, "automatic_retention_v3", {"step": step, **retention}
                )
                hard_abort, planner_pause = pause_decision(retention, step)
                if planner_pause and state is None:
                    state = await _save_state(
                        client, provider, output, status, stages, storage, step
                    )
                if not hard_abort and step in FAST_DEV_STEPS:
                    _stage(
                        output,
                        status,
                        stages,
                        "fast_dev",
                        {"step": step, **dict(await evaluator("fast_dev", step, sampler_path, ()))},
                    )
                    completed_fast = True
                if not hard_abort and step in FULL_DEV_STEPS:
                    _stage(
                        output,
                        status,
                        stages,
                        "full_dev_pending_human",
                        {"step": step, **dict(await evaluator("full_dev", step, sampler_path, ()))},
                    )
                    completed_full_steps.add(step)
                if planner_pause:
                    if state is None:
                        raise LR5E5RunError("planner stop lacks its exact state")
                    next_step = step + 1
                    control = {
                        "logical_run_id": RUN_ID,
                        "provider_lineage": identity,
                        "completed_global_step": step,
                        "next_global_step": next_step,
                        "next_batch_membership_sha256": _next_batch_membership(contract, next_step),
                        "optimizer_state_path": state["path"],
                        "optimizer_state_identity": _digest(str(state["path"]).encode()),
                        "scheduler_position": step,
                        "expected_next_step_learning_rate": learning_rate(next_step)
                        if next_step <= 126
                        else None,
                        "training_seed": SEED,
                        "data_order_identity": BATCH_PLAN_SHA256,
                        "checkpoint_created_at": state.get("checkpoint_created_at"),
                        "checkpoint_expires_at": state.get("checkpoint_expires_at"),
                        "checkpoint_remaining_ttl_seconds": state.get("remaining_ttl_seconds"),
                        "cumulative_train_token_count": cumulative_tokens,
                        "cumulative_spend_usd": _modeled_spend_to_step(
                            root,
                            contract,
                            cumulative_train_tokens=cumulative_tokens,
                            completed_fast=completed_fast,
                            completed_full_steps=frozenset(completed_full_steps),
                            completed_retention_steps=frozenset(completed_retention_steps),
                            storage=storage,
                        ),
                        "cumulative_spend_basis": (
                            "model-derived upper projection for completed work; "
                            "provider billing not queried"
                        ),
                        "storage_ledger": {
                            "sampler_bytes": storage.sampler_bytes,
                            "sampler_objects": storage.sampler_objects,
                            "state_bytes": storage.state_bytes,
                            "state_objects": storage.state_objects,
                        },
                    }
                    control_hash = write_pause_control(
                        output / f"step-{step:03d}-pause-control.json", control
                    )
                    _stage(
                        output,
                        status,
                        stages,
                        "pause_control_fsynced",
                        {"step": step, "sha256": control_hash},
                    )
                    status["status"] = "stopped_pending_planner_review"
                if hard_abort:
                    status["status"] = "stopped_retention_catastrophe_v3"
                if hard_abort or planner_pause:
                    break
            finally:
                if sampler_path is not None:
                    await _provider_result(provider.delete_checkpoint(sampler_path))
                    _stage(
                        output,
                        status,
                        stages,
                        "sampler_cleanup",
                        {"step": step, "path": sampler_path, "deleted": True},
                    )
                    sampler_path = None
        else:
            raise LR5E5RunError("step 40 must create the mandatory planner pause")
    except BaseException as error:
        status.update({"error_type": type(error).__name__, "status": "failed_pipeline"})
        raise
    finally:
        key = ""
        if sampler_path is not None and provider is not None:
            try:
                await _provider_result(provider.delete_checkpoint(sampler_path))
            except BaseException:
                status["sampler_cleanup"] = "failed_ttl_fallback"
        os.environ.pop("TINKER_API_KEY", None)
        _write_status(output / "status.json", status)
        _seal_run(output)
    return status


def _seal_run(output: Path) -> str:
    paths = sorted(
        path for path in output.rglob("*") if path.is_file() and path != output / "SHA256SUMS"
    )
    payload = "".join(
        f"{sha256(path.read_bytes()).hexdigest()}  {path.relative_to(output).as_posix()}\n"
        for path in paths
    )
    (output / "SHA256SUMS").write_text(payload, encoding="ascii")
    return _digest(payload.encode())


def capture_logs(root: Path) -> Mapping[str, object]:
    """Bind detached stdout/stderr after process exit, before LaunchAgent bootout."""
    root = root.resolve(strict=True)
    running = subprocess.run(
        ["launchctl", "print", f"gui/{os.getuid()}/{LAUNCHD_LABEL}"],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    if running.returncode == 0 and re.search(r"\bpid = [1-9][0-9]*", running.stdout):
        raise LR5E5RunError("detached logs may be captured only after process exit")
    parent = root / (RUN_OUTPUT if (root / RUN_OUTPUT).exists() else EARLY_FAILURE_OUTPUT)
    destination = parent / "launch"
    if destination.exists():
        raise LR5E5RunError("detached launch logs are already captured")
    destination.mkdir(mode=0o700, parents=True)
    records: dict[str, object] = {}
    for name, source in (("stdout.log", STDOUT_LOG), ("stderr.log", STDERR_LOG)):
        raw = source.read_bytes()
        (destination / name).write_bytes(raw)
        records[name] = {
            "sha256": _digest(raw),
            "size_bytes": len(raw),
            "source": str(source),
        }
    manifest = {
        "kind": "phase3r-rank16-lr5e5-launch-log-manifest-v1",
        "logs": records,
    }
    manifest_raw = canonical_artifact_bytes(manifest)
    (destination / "launch-log-manifest.json").write_bytes(manifest_raw)
    _write_sums(destination)
    root_sums = _seal_run(parent)
    return {
        "launch_log_manifest_sha256": _digest(manifest_raw),
        "output_directory": parent.relative_to(root).as_posix(),
        "root_sha256sums_sha256": root_sums,
    }
