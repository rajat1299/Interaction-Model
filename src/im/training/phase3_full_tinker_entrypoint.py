"""Fail-closed detached entrypoint for the locked WP3-4 Tinker run."""

from __future__ import annotations

import os
import re
import stat
import subprocess
import sys
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

import tinker

from im.assets.model import canonical_artifact_bytes
from im.training.phase3_data import SEALED_TEST_RELATIVE_PATH, PinnedTokenizer, guard_read_path
from im.training.phase3_full_resume import PAUSE_STATE_MINIMUM_TTL_SECONDS
from im.training.phase3_full_run import (
    LockedRunContract,
    execute_locked_run,
    load_checksum_bound_authorization,
    load_checksum_bound_resume_authorization,
    load_locked_run_contract,
    resume_conditional_epoch_three,
)
from im.training.phase3_full_tinker import (
    Phase3FullTinkerError,
    TinkerEvaluator,
    TinkerRunProvider,
    _digest,
    _read_json,
)
from im.training.phase3_sampling import read_tinker_api_key

LAUNCHD_LABEL = "com.interactionmodel.wp3-4-sft"
LAUNCHD_ENV_NAME = "PHASE3_LAUNCHD_LABEL"
SECRET_NAME = "TINKER_API_KEY"
EXECUTION_PACKET_KIND = "phase3-wp3-4-execution-packet"
RESUME_EXECUTION_PACKET_KIND = "phase3-wp3-4-resume-execution-packet"
INITIAL_EPOCH_MODE = "two_epoch_only"
INITIAL_EPOCH_CEILING_USD = 130.0
CONDITIONAL_EPOCH_MODE = "conditional_third_epoch"
CONDITIONAL_EPOCH_CEILING_USD = 190.0
RESUME_ADDITIONAL_CEILING_USD = 60.0
HUMAN_REVIEW_WINDOW_SECONDS = 604800
HUMAN_REVIEW_SAFETY_BUFFER_SECONDS = 86400
PAUSE_AMENDMENT_SHA256 = "sha256:0bad4bb47eebf159a066ad2c052ad92d17a7459e85c4cbdf47c4726bc4e727f0"
PAUSE_AMENDMENT_ZIP_SHA256 = (
    "sha256:a41b53261e7e97d637188a5ca44745ec13697e45c08a4b9856565b6c3bb822c6"
)
INITIAL_EXECUTION_DIRECTORY = Path("review/phase3/wp3-4-paid-execution-candidate-v4")
RESUME_EXECUTION_DIRECTORY = Path("review/phase3/wp3-4-resume-execution-candidate-v1")
INITIAL_EXECUTION_PACKET_PATH = INITIAL_EXECUTION_DIRECTORY / "execution-packet.json"
INITIAL_AUTHORIZATION_PATH = INITIAL_EXECUTION_DIRECTORY / "owner-authorization.json"
INITIAL_BALANCE_RECEIPT_PATH = INITIAL_EXECUTION_DIRECTORY / "funding-override.json"
RESUME_EXECUTION_PACKET_PATH = RESUME_EXECUTION_DIRECTORY / "resume-execution-packet.json"
RESUME_AUTHORIZATION_PATH = RESUME_EXECUTION_DIRECTORY / "owner-resume-authorization.json"
RESUME_BALANCE_RECEIPT_PATH = RESUME_EXECUTION_DIRECTORY / "balance-confirmation.json"
PAUSE_AMENDMENT_PATH = Path(
    "review/phase3/wp3-4-human-review-pause-amendment-candidate-v2/"
    "human-review-pause-amendment-v2.json"
)
RUNNER_SCRIPT_PATH = Path("scripts/run_phase3_full_tinker.py")
REQUIRED_ARTIFACT_BINDINGS = frozenset(
    {
        "launch_plan",
        "launchagent_plist",
        "runner_script",
        "runner_source_diff",
        "runner_test_review",
        "pause_amendment",
    }
)
POST_SOURCE_ARTIFACT_BINDINGS = frozenset(
    {"launch_plan", "launchagent_plist", "runner_source_diff", "runner_test_review"}
)
PARENT_INVENTORY_ROLES = frozenset(
    {
        "initial_execution_packet",
        "initial_authorization",
        "initial_balance_receipt",
        "initial_launch_plan",
        "initial_launchagent_plist",
        "initial_runner_source_diff",
        "initial_runner_test_review",
    }
)
INITIAL_ARTIFACT_PATHS = {
    "launch_plan": INITIAL_EXECUTION_DIRECTORY / "launch-plan.json",
    "launchagent_plist": INITIAL_EXECUTION_DIRECTORY / "com.interactionmodel.wp3-4-sft.plist",
    "pause_amendment": PAUSE_AMENDMENT_PATH,
    "runner_script": RUNNER_SCRIPT_PATH,
    "runner_source_diff": INITIAL_EXECUTION_DIRECTORY / "runner-source-diff.patch",
    "runner_test_review": INITIAL_EXECUTION_DIRECTORY / "runner-test-review.json",
}
RESUME_ARTIFACT_PATHS = {
    "launch_plan": RESUME_EXECUTION_DIRECTORY / "launch-plan.json",
    "launchagent_plist": RESUME_EXECUTION_DIRECTORY / "com.interactionmodel.wp3-4-sft.plist",
    "pause_amendment": PAUSE_AMENDMENT_PATH,
    "runner_script": RUNNER_SCRIPT_PATH,
    "runner_source_diff": RESUME_EXECUTION_DIRECTORY / "runner-source-diff.patch",
    "runner_test_review": RESUME_EXECUTION_DIRECTORY / "runner-test-review.json",
}
_GIT_SHA = re.compile(r"[0-9a-f]{40}")
_SHA256 = re.compile(r"sha256:[0-9a-f]{64}")


@dataclass(frozen=True, slots=True)
class ExecutionPacket:
    path: Path
    sha256: str
    source_commit: str
    run_id: str
    output_directory: str
    kind: str = EXECUTION_PACKET_KIND
    artifact_bindings: Mapping[str, Mapping[str, str]] = field(default_factory=dict)
    pause_amendment_zip_sha256: str = PAUSE_AMENDMENT_ZIP_SHA256
    parent_initial_inventory: Mapping[str, Mapping[str, str]] = field(default_factory=dict)


def load_execution_packet(
    repository_root: Path, path: Path, contract: LockedRunContract
) -> ExecutionPacket:
    """Bind the initial two-epoch runner to the frozen candidate and launch artifacts."""
    return _load_execution_packet(
        repository_root,
        path,
        contract,
        kind=EXECUTION_PACKET_KIND,
        epoch_mode=INITIAL_EPOCH_MODE,
        spending={"maximum_spend_usd": INITIAL_EPOCH_CEILING_USD},
    )


def load_resume_execution_packet(
    repository_root: Path, path: Path, contract: LockedRunContract
) -> ExecutionPacket:
    """Bind the independently authorized child resume to its own launch packet."""
    return _load_execution_packet(
        repository_root,
        path,
        contract,
        kind=RESUME_EXECUTION_PACKET_KIND,
        epoch_mode=CONDITIONAL_EPOCH_MODE,
        spending={
            "maximum_additional_spend_usd": RESUME_ADDITIONAL_CEILING_USD,
            "maximum_cumulative_spend_usd": contract.three_epoch_ceiling_usd,
        },
    )


def _load_execution_packet(
    repository_root: Path,
    path: Path,
    contract: LockedRunContract,
    *,
    kind: str,
    epoch_mode: str,
    spending: Mapping[str, float],
) -> ExecutionPacket:
    root = repository_root.resolve(strict=True)
    packet_path = guard_read_path(root, path)
    raw = packet_path.read_bytes()
    packet = _read_json(packet_path, "execution packet")
    source, run_id, output_directory = (
        packet.get("runner_source_commit"),
        packet.get("run_id"),
        packet.get("output_directory"),
    )
    required = {
        "format_version": 1,
        "kind": kind,
        "candidate_manifest_sha256": contract.candidate_manifest_sha256,
        "candidate_sha256sums_sha256": contract.candidate_sha256sums_sha256,
        "derived_source_commit": contract.source_commit,
        "epoch_mode": epoch_mode,
        "human_review_window_seconds": HUMAN_REVIEW_WINDOW_SECONDS,
        "human_review_safety_buffer_seconds": HUMAN_REVIEW_SAFETY_BUFFER_SECONDS,
        "full_state_lifetime": {
            "durable_storage_allowed": True,
            "minimum_remaining_ttl_seconds": PAUSE_STATE_MINIMUM_TTL_SECONDS,
            "required_steps": [20, 40, 60, 63, 80, 100, 120, 126],
        },
        "detached_execution_required": True,
        "launchd_label": LAUNCHD_LABEL,
        "sealed_test_access": "forbidden",
        "application_retries": 0,
        "pause_amendment_zip_sha256": PAUSE_AMENDMENT_ZIP_SHA256,
    }
    required.update(spending)
    if (
        any(packet.get(name) != value for name, value in required.items())
        or not isinstance(source, str)
        or _GIT_SHA.fullmatch(source) is None
        or not isinstance(run_id, str)
        or re.fullmatch(r"wp3-4-[a-z0-9][a-z0-9.-]{3,100}", run_id) is None
        or not isinstance(output_directory, str)
    ):
        raise Phase3FullTinkerError("execution packet does not bind the locked runner source")
    output = Path(output_directory)
    if output.as_posix() != output_directory or output.is_absolute() or not output.parts:
        raise Phase3FullTinkerError("execution packet output binding is malformed")
    bindings = _verify_packet_artifact_bindings(root, packet, kind=kind)
    parent_inventory = (
        _verify_parent_initial_inventory(root, packet)
        if kind == RESUME_EXECUTION_PACKET_KIND
        else {}
    )
    return ExecutionPacket(
        path=packet_path,
        sha256=_digest(raw),
        source_commit=source,
        run_id=run_id,
        output_directory=output_directory,
        kind=kind,
        artifact_bindings=bindings,
        pause_amendment_zip_sha256=PAUSE_AMENDMENT_ZIP_SHA256,
        parent_initial_inventory=parent_inventory,
    )


def _artifact_paths_for(kind: str) -> Mapping[str, Path]:
    if kind == EXECUTION_PACKET_KIND:
        return INITIAL_ARTIFACT_PATHS
    if kind == RESUME_EXECUTION_PACKET_KIND:
        return RESUME_ARTIFACT_PATHS
    raise Phase3FullTinkerError("execution packet kind is unsupported")


def _verify_packet_artifact_bindings(
    root: Path, packet: Mapping[str, object], *, kind: str
) -> Mapping[str, Mapping[str, str]]:
    expected_paths = _artifact_paths_for(kind)
    bindings = packet.get("artifact_bindings")
    if not isinstance(bindings, Mapping) or set(bindings) != REQUIRED_ARTIFACT_BINDINGS:
        raise Phase3FullTinkerError("execution packet artifact binding inventory drifted")
    normalized: dict[str, Mapping[str, str]] = {}
    seen_paths: set[str] = set()
    for name in sorted(REQUIRED_ARTIFACT_BINDINGS):
        binding = bindings.get(name)
        if not isinstance(binding, Mapping):
            raise Phase3FullTinkerError("execution packet artifact binding is malformed")
        path, expected = binding.get("path"), binding.get("sha256")
        if (
            not isinstance(path, str)
            or not isinstance(expected, str)
            or _SHA256.fullmatch(expected) is None
        ):
            raise Phase3FullTinkerError("execution packet artifact binding is malformed")
        relative = Path(path)
        if relative.is_absolute() or relative.as_posix() != path or not relative.parts:
            raise Phase3FullTinkerError("execution packet artifact path is malformed")
        if relative != expected_paths[name]:
            raise Phase3FullTinkerError("execution packet artifact path is non-canonical")
        if path in seen_paths:
            raise Phase3FullTinkerError("execution packet artifact roles alias the same path")
        seen_paths.add(path)
        raw = guard_read_path(root, root / relative).read_bytes()
        if _digest(raw) != expected:
            raise Phase3FullTinkerError("execution packet artifact checksum drifted")
        normalized[name] = {"path": path, "sha256": expected}
    if normalized["pause_amendment"]["sha256"] != PAUSE_AMENDMENT_SHA256:
        raise Phase3FullTinkerError("execution packet pause amendment binding drifted")
    return normalized


def _verify_parent_initial_inventory(
    root: Path, packet: Mapping[str, object]
) -> Mapping[str, Mapping[str, str]]:
    """Bind a child launch to immutable v2 initial sidecars, never aliases."""
    inventory = packet.get("parent_initial_inventory")
    if not isinstance(inventory, Mapping) or set(inventory) != PARENT_INVENTORY_ROLES:
        raise Phase3FullTinkerError("resume packet parent inventory drifted")
    expected_paths = {
        "initial_execution_packet": INITIAL_EXECUTION_PACKET_PATH,
        "initial_authorization": INITIAL_AUTHORIZATION_PATH,
        "initial_balance_receipt": INITIAL_BALANCE_RECEIPT_PATH,
        "initial_launch_plan": INITIAL_ARTIFACT_PATHS["launch_plan"],
        "initial_launchagent_plist": INITIAL_ARTIFACT_PATHS["launchagent_plist"],
        "initial_runner_source_diff": INITIAL_ARTIFACT_PATHS["runner_source_diff"],
        "initial_runner_test_review": INITIAL_ARTIFACT_PATHS["runner_test_review"],
    }
    normalized: dict[str, Mapping[str, str]] = {}
    seen_paths: set[str] = set()
    for name in sorted(PARENT_INVENTORY_ROLES):
        binding = inventory.get(name)
        if not isinstance(binding, Mapping):
            raise Phase3FullTinkerError("resume packet parent inventory is malformed")
        path, expected = binding.get("path"), binding.get("sha256")
        if (
            not isinstance(path, str)
            or not isinstance(expected, str)
            or _SHA256.fullmatch(expected) is None
        ):
            raise Phase3FullTinkerError("resume packet parent inventory is malformed")
        relative = Path(path)
        if (
            relative.is_absolute()
            or relative.as_posix() != path
            or relative != expected_paths[name]
            or path in seen_paths
        ):
            raise Phase3FullTinkerError("resume packet parent inventory path is non-canonical")
        seen_paths.add(path)
        raw = guard_read_path(root, root / relative).read_bytes()
        if _digest(raw) != expected:
            raise Phase3FullTinkerError("resume packet parent inventory checksum drifted")
        normalized[name] = {"path": path, "sha256": expected}
    return normalized


def _lexical_output_relative(repository_root: Path, output: Path) -> Path:
    """Reject escape and sealed paths without resolving, statting, or creating output."""
    del repository_root  # lexical validation deliberately does not inspect the filesystem.
    if (
        output.is_absolute()
        or not output.parts
        or any(part in {".", ".."} for part in output.parts)
    ):
        raise Phase3FullTinkerError("paid output path must be a non-root repository-relative path")
    relative = Path(*output.parts)
    sealed = SEALED_TEST_RELATIVE_PATH.parts
    if relative.parts[: len(sealed)] == sealed:
        raise Phase3FullTinkerError("paid output path may not name the sealed interaction TEST")
    return relative


def _verify_authorization_binding(
    authorization: Mapping[str, object],
    packet: ExecutionPacket,
    run_id: str,
    output_relative: Path,
) -> None:
    required = {
        "execution_packet_sha256": packet.sha256,
        "runner_source_commit": packet.source_commit,
        "run_id": run_id,
        "output_directory": output_relative.as_posix(),
        "epoch_mode": INITIAL_EPOCH_MODE,
        "maximum_spend_usd": INITIAL_EPOCH_CEILING_USD,
        "human_review_window_seconds": HUMAN_REVIEW_WINDOW_SECONDS,
        "human_review_safety_buffer_seconds": HUMAN_REVIEW_SAFETY_BUFFER_SECONDS,
        "full_state_minimum_remaining_ttl_seconds": PAUSE_STATE_MINIMUM_TTL_SECONDS,
        "detached_execution_required": True,
        "launchd_label": LAUNCHD_LABEL,
        "sealed_test_access": "forbidden",
        "application_retries": 0,
        "one_locked_run": True,
        "funding_mode": "owner_monitored_live_top_up",
        "upfront_balance_confirmation_required": False,
        "owner_monitoring_required": True,
    }
    artifact_hashes = {
        f"{name}_sha256": binding["sha256"] for name, binding in packet.artifact_bindings.items()
    }
    if (
        packet.run_id != run_id
        or packet.output_directory != output_relative.as_posix()
        or any(authorization.get(name) != value for name, value in required.items())
        or authorization.get("pause_amendment_zip_sha256") != packet.pause_amendment_zip_sha256
        or any(authorization.get(name) != value for name, value in artifact_hashes.items())
    ):
        raise Phase3FullTinkerError(
            "owner authorization does not bind this packet, run, and output"
        )


def _verify_resume_authorization_binding(
    authorization: Mapping[str, object],
    packet: ExecutionPacket,
    run_id: str,
    output_relative: Path,
) -> None:
    required = {
        "resume_execution_packet_sha256": packet.sha256,
        "runner_source_commit": packet.source_commit,
        "run_id": run_id,
        "output_directory": output_relative.as_posix(),
        "epoch_mode": CONDITIONAL_EPOCH_MODE,
        "maximum_additional_spend_usd": RESUME_ADDITIONAL_CEILING_USD,
        "maximum_cumulative_spend_usd": CONDITIONAL_EPOCH_CEILING_USD,
        "human_review_window_seconds": HUMAN_REVIEW_WINDOW_SECONDS,
        "human_review_safety_buffer_seconds": HUMAN_REVIEW_SAFETY_BUFFER_SECONDS,
        "full_state_minimum_remaining_ttl_seconds": PAUSE_STATE_MINIMUM_TTL_SECONDS,
        "detached_execution_required": True,
        "launchd_label": LAUNCHD_LABEL,
        "sealed_test_access": "forbidden",
        "application_retries": 0,
        "one_locked_resume": True,
        "pause_amendment_zip_sha256": packet.pause_amendment_zip_sha256,
    }
    artifact_hashes = {
        f"{name}_sha256": binding["sha256"] for name, binding in packet.artifact_bindings.items()
    }
    if (
        packet.run_id != run_id
        or packet.output_directory != output_relative.as_posix()
        or any(authorization.get(name) != value for name, value in required.items())
        or any(authorization.get(name) != value for name, value in artifact_hashes.items())
    ):
        raise Phase3FullTinkerError(
            "owner resume authorization does not bind this child packet, run, and output"
        )


def verify_execution_lineage(
    repository_root: Path,
    packet: ExecutionPacket,
    authorization_path: Path,
    balance_receipt_path: Path,
    *,
    resume_output_relative: Path | None = None,
) -> str:
    """Allow sidecars, or only a nonempty prior output subtree for a resume."""
    root = repository_root.resolve(strict=True)
    if set(packet.artifact_bindings) != REQUIRED_ARTIFACT_BINDINGS:
        raise Phase3FullTinkerError("runner source lineage lacks bound execution artifacts")
    if resume_output_relative is not None:
        expected_output = root / resume_output_relative
        output = guard_read_path(root, expected_output)
        if output != expected_output or not output.is_dir():
            raise Phase3FullTinkerError("resume output directory is missing or not a directory")
        _verify_plain_resume_tree(output)
    child_paths = {
        packet.path.relative_to(root).as_posix(),
        guard_read_path(root, authorization_path).relative_to(root).as_posix(),
        guard_read_path(root, balance_receipt_path).relative_to(root).as_posix(),
        *(packet.artifact_bindings[name]["path"] for name in POST_SOURCE_ARTIFACT_BINDINGS),
    }
    if packet.kind == RESUME_EXECUTION_PACKET_KIND:
        parent_paths = {binding["path"] for binding in packet.parent_initial_inventory.values()}
        if set(packet.parent_initial_inventory) != PARENT_INVENTORY_ROLES:
            raise Phase3FullTinkerError(
                "resume source lineage lacks the immutable parent inventory"
            )
        if parent_paths & child_paths:
            raise Phase3FullTinkerError("resume source lineage aliases parent and child artifacts")
        allowed = parent_paths | child_paths
    elif packet.kind == EXECUTION_PACKET_KIND:
        allowed = child_paths
    else:
        raise Phase3FullTinkerError("runner source lineage has an unsupported packet kind")
    environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    commands: list[tuple[str, ...]] = [
        ("merge-base", "--is-ancestor", packet.source_commit, "HEAD"),
        ("status", "--porcelain", "--untracked-files=all"),
    ]
    if resume_output_relative is not None:
        commands.append(("ls-files", "--", resume_output_relative.as_posix()))
    commands.extend(
        (
            ("diff", "--name-only", f"{packet.source_commit}..HEAD"),
            ("rev-parse", "HEAD"),
        )
    )
    results = []
    for arguments in commands:
        result = subprocess.run(
            ["git", *arguments],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
            env=environment,
        )
        if result.returncode != 0:
            raise Phase3FullTinkerError("runner source lineage could not be verified")
        results.append(result.stdout.strip())
    tracked_output = results[2] if resume_output_relative is not None else ""
    changed_index = 3 if resume_output_relative is not None else 2
    changed = {line for line in results[changed_index].splitlines() if line}
    if (
        not _allowed_worktree_status(results[1], resume_output_relative)
        or tracked_output
        or changed != allowed
    ):
        raise Phase3FullTinkerError("runner source lineage contains unauthorized changes")
    return results[changed_index + 1]


def _allowed_worktree_status(status: str, resume_output_relative: Path | None) -> bool:
    if resume_output_relative is None:
        return not status
    lines = [line for line in status.splitlines() if line]
    if not lines:
        return False
    prefix = f"?? {resume_output_relative.as_posix()}/"
    return all(line.startswith(prefix) for line in lines)


def _verify_plain_resume_tree(directory: Path) -> None:
    """Reject links and special files before the paused run's evidence may be read."""
    try:
        with os.scandir(directory) as entries:
            for entry in entries:
                if entry.is_symlink():
                    raise Phase3FullTinkerError("resume output contains an unsafe symlink")
                if entry.is_dir(follow_symlinks=False):
                    _verify_plain_resume_tree(Path(entry.path))
                elif not entry.is_file(follow_symlinks=False):
                    raise Phase3FullTinkerError("resume output contains an unsafe special entry")
    except OSError as error:
        raise Phase3FullTinkerError("resume output tree could not be inspected safely") from error


def verify_launchd_execution() -> None:
    """Paid work must be a live macOS LaunchAgent, never this interactive shell."""
    if (
        sys.platform != "darwin"
        or os.getppid() != 1
        or os.environ.get(LAUNCHD_ENV_NAME) != LAUNCHD_LABEL
    ):
        raise Phase3FullTinkerError("paid WP3-4 must run as the frozen detached launchd job")
    result = subprocess.run(
        ["launchctl", "print", f"gui/{os.getuid()}/{LAUNCHD_LABEL}"],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    if result.returncode != 0 or f"pid = {os.getpid()}" not in result.stdout:
        raise Phase3FullTinkerError("launchd job identity does not match this paid process")


def capture_detached_launch_logs(
    *,
    repository_root: Path,
    output_directory: Path,
    stdout_path: Path,
    stderr_path: Path,
    run_id: str,
) -> Mapping[str, object]:
    """Copy exited LaunchAgent logs into checksum-bound run or early-failure evidence."""
    root = repository_root.resolve(strict=True)
    output_relative = _lexical_output_relative(root, output_directory)
    if re.fullmatch(r"wp3-4-[a-z0-9][a-z0-9.-]{3,100}", run_id) is None:
        raise Phase3FullTinkerError("launch-log run identity is malformed")
    result = subprocess.run(
        ["launchctl", "print", f"gui/{os.getuid()}/{LAUNCHD_LABEL}"],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    if result.returncode != 0 or re.search(r"\bpid = [1-9][0-9]*", result.stdout):
        raise Phase3FullTinkerError("launch logs may be captured only after the loaded job exits")
    sources = {"stdout.log": stdout_path, "stderr.log": stderr_path}
    payloads: dict[str, bytes] = {}
    source_evidence: dict[str, Mapping[str, object]] = {}
    for name, path in sources.items():
        if not path.is_absolute():
            raise Phase3FullTinkerError("launch log source path must be absolute")
        try:
            metadata = path.lstat()
        except OSError as error:
            raise Phase3FullTinkerError("launch log source is unavailable") from error
        if not stat.S_ISREG(metadata.st_mode):
            raise Phase3FullTinkerError("launch log source is not a regular file")
        raw = path.read_bytes()
        if len(raw) != metadata.st_size:
            raise Phase3FullTinkerError("launch log source changed during capture")
        payloads[name] = raw
        source_evidence[name] = {
            "sha256": _digest(raw),
            "size_bytes": len(raw),
            "source_path": path.as_posix(),
        }
    output = root / output_relative
    if output.exists():
        if output.is_symlink() or not output.is_dir():
            raise Phase3FullTinkerError("launch-log run output is unsafe")
        directory = output / "launch"
        disposition = "run_output"
    else:
        directory = root / "review/phase3" / f"{run_id}-early-failure-evidence" / "launch"
        disposition = "early_failure_evidence"
    if directory.exists():
        raise Phase3FullTinkerError("launch-log evidence directory already exists")
    directory.mkdir(mode=0o700, parents=True)
    for name, raw in payloads.items():
        _write_new_file(directory / name, raw)
    relative = directory.relative_to(root).as_posix()
    manifest = canonical_artifact_bytes(
        {
            "capture_disposition": disposition,
            "closeout_binding_required": f"{relative}/SHA256SUMS",
            "format_version": 1,
            "kind": "phase3-wp3-4-launch-log-manifest",
            "launchd_label": LAUNCHD_LABEL,
            "logs": source_evidence,
            "process_state": "exited_before_capture",
            "run_id": run_id,
        }
    )
    _write_new_file(directory / "launch-log-manifest.json", manifest)
    sums = b"".join(
        f"{_digest(raw).removeprefix('sha256:')}  {name}\n".encode("ascii")
        for name, raw in sorted({**payloads, "launch-log-manifest.json": manifest}.items())
    )
    _write_new_file(directory / "SHA256SUMS", sums)
    return {
        "capture_disposition": disposition,
        "evidence_directory": relative,
        "launch_log_manifest_sha256": _digest(manifest),
        "sha256sums_sha256": _digest(sums),
    }


def _write_new_file(path: Path, raw: bytes) -> None:
    try:
        with path.open("xb") as handle:
            handle.write(raw)
        path.chmod(0o600)
    except OSError as error:
        raise Phase3FullTinkerError("launch-log evidence could not be written") from error


def _preflight_tinker_launch(
    *,
    repository_root: Path,
    candidate_directory: Path,
    execution_packet_path: Path,
    authorization_path: Path,
    output_directory: Path,
    run_id: str,
) -> tuple[Path, LockedRunContract, ExecutionPacket, Path]:
    """Complete every byte-bound, detached preflight before a credential can be read."""
    root = repository_root.resolve(strict=True)
    _require_canonical_path(root, execution_packet_path, INITIAL_EXECUTION_PACKET_PATH, "packet")
    _require_canonical_path(root, authorization_path, INITIAL_AUTHORIZATION_PATH, "authorization")
    contract = load_locked_run_contract(root, candidate_directory)
    packet = load_execution_packet(root, execution_packet_path, contract)
    authorization = load_checksum_bound_authorization(root, authorization_path, contract)
    output_relative = _lexical_output_relative(root, output_directory)
    _verify_authorization_binding(authorization.payload, packet, run_id, output_relative)
    balance_path = authorization.payload.get("funding_override_path")
    if not isinstance(balance_path, str):
        raise Phase3FullTinkerError("launch authorization has no funding override path")
    _require_canonical_path(
        root, Path(balance_path), INITIAL_BALANCE_RECEIPT_PATH, "funding override"
    )
    verify_execution_lineage(
        root,
        packet,
        authorization_path,
        Path(balance_path),
    )
    verify_launchd_execution()
    return root, contract, packet, output_relative


def _preflight_tinker_resume(
    *,
    repository_root: Path,
    candidate_directory: Path,
    execution_packet_path: Path,
    authorization_path: Path,
    output_directory: Path,
    run_id: str,
) -> tuple[Path, LockedRunContract, ExecutionPacket, Path]:
    """Validate the distinct child packet and authorization before credential access."""
    root = repository_root.resolve(strict=True)
    _require_canonical_path(root, execution_packet_path, RESUME_EXECUTION_PACKET_PATH, "packet")
    _require_canonical_path(root, authorization_path, RESUME_AUTHORIZATION_PATH, "authorization")
    contract = load_locked_run_contract(root, candidate_directory)
    packet = load_resume_execution_packet(root, execution_packet_path, contract)
    authorization = load_checksum_bound_resume_authorization(root, authorization_path, contract)
    output_relative = _lexical_output_relative(root, output_directory)
    _verify_resume_authorization_binding(authorization.payload, packet, run_id, output_relative)
    balance_path = authorization.payload.get("balance_confirmation_path")
    if not isinstance(balance_path, str):
        raise Phase3FullTinkerError("resume authorization has no balance receipt path")
    _require_canonical_path(
        root, Path(balance_path), RESUME_BALANCE_RECEIPT_PATH, "balance receipt"
    )
    verify_execution_lineage(
        root,
        packet,
        authorization_path,
        Path(balance_path),
        resume_output_relative=output_relative,
    )
    verify_launchd_execution()
    return root, contract, packet, output_relative


def _require_canonical_path(root: Path, path: Path, expected: Path, label: str) -> None:
    canonical = root / expected
    if (path if path.is_absolute() else root / path) != canonical:
        raise Phase3FullTinkerError(f"launch {label} path is non-canonical")


def _lazy_tinker_runtime(
    *,
    root: Path,
    output: Path,
    tokenizer: PinnedTokenizer,
    contract: LockedRunContract,
    run_id: str,
    service_factory: Callable[..., tinker.ServiceClient],
    secret_reader: Callable[[Path], str],
) -> tuple[
    Callable[[], Awaitable[TinkerRunProvider]],
    Callable[[str, int, str, Sequence[Mapping[str, object]]], Awaitable[Mapping[str, object]]],
    Callable[[], None],
]:
    """Delay .env access and SDK construction until the core has passed its own disk gates."""
    provider: TinkerRunProvider | None = None
    evaluator: TinkerEvaluator | None = None
    credential_installed = False

    async def provider_factory() -> TinkerRunProvider:
        nonlocal credential_installed, evaluator, provider
        if provider is None:
            key = secret_reader(guard_read_path(root, root / ".env"))
            os.environ[SECRET_NAME] = key
            credential_installed = True
            key = ""
            provider = TinkerRunProvider(service_factory, run_id)
            evaluator = TinkerEvaluator(root, output, tokenizer, contract, run_id, provider)
        return provider

    async def evaluate(
        kind: str, step: int, sampler_path: str, rows: Sequence[Mapping[str, object]]
    ) -> Mapping[str, object]:
        if evaluator is None:
            raise Phase3FullTinkerError("evaluator requested before Tinker provider construction")
        return await evaluator(kind, step, sampler_path, rows)

    def clear_credential() -> None:
        if credential_installed:
            os.environ.pop(SECRET_NAME, None)

    return provider_factory, evaluate, clear_credential


async def execute_tinker_locked_run(
    *,
    repository_root: Path,
    candidate_directory: Path,
    execution_packet_path: Path,
    authorization_path: Path,
    tokenizer: PinnedTokenizer,
    output_directory: Path,
    run_id: str,
    service_factory: Callable[..., tinker.ServiceClient] = tinker.ServiceClient,
    secret_reader: Callable[[Path], str] = read_tinker_api_key,
) -> dict[str, object]:
    """Start the authorized initial segment; full DEV pauses at step 126 for human review."""
    root, contract, packet, output_relative = _preflight_tinker_launch(
        repository_root=repository_root,
        candidate_directory=candidate_directory,
        execution_packet_path=execution_packet_path,
        authorization_path=authorization_path,
        output_directory=output_directory,
        run_id=run_id,
    )
    provider_factory, evaluator, clear_credential = _lazy_tinker_runtime(
        root=root,
        output=root / output_relative,
        tokenizer=tokenizer,
        contract=contract,
        run_id=run_id,
        service_factory=service_factory,
        secret_reader=secret_reader,
    )
    try:
        return await execute_locked_run(
            contract=contract,
            repository_root=root,
            authorization_path=authorization_path,
            provider_factory=provider_factory,
            evaluator=evaluator,
            output_directory=root / output_relative,
            run_id=run_id,
            final_execution_source_commit=packet.source_commit,
            human_review_window_seconds=HUMAN_REVIEW_WINDOW_SECONDS,
            safety_buffer_seconds=HUMAN_REVIEW_SAFETY_BUFFER_SECONDS,
        )
    finally:
        clear_credential()


async def resume_tinker_conditional_epoch_three(
    *,
    repository_root: Path,
    candidate_directory: Path,
    execution_packet_path: Path,
    authorization_path: Path,
    tokenizer: PinnedTokenizer,
    output_directory: Path,
    run_id: str,
    service_factory: Callable[..., tinker.ServiceClient] = tinker.ServiceClient,
    secret_reader: Callable[[Path], str] = read_tinker_api_key,
) -> dict[str, object]:
    """Resume the one conditional epoch only after the core validates paused-run evidence."""
    root, contract, _packet, output_relative = _preflight_tinker_resume(
        repository_root=repository_root,
        candidate_directory=candidate_directory,
        execution_packet_path=execution_packet_path,
        authorization_path=authorization_path,
        output_directory=output_directory,
        run_id=run_id,
    )
    provider_factory, evaluator, clear_credential = _lazy_tinker_runtime(
        root=root,
        output=root / output_relative,
        tokenizer=tokenizer,
        contract=contract,
        run_id=run_id,
        service_factory=service_factory,
        secret_reader=secret_reader,
    )
    try:
        return await resume_conditional_epoch_three(
            repository_root=root,
            output_directory=root / output_relative,
            authorization_path=authorization_path,
            contract=contract,
            provider_factory=provider_factory,
            evaluator=evaluator,
            human_review_window_seconds=HUMAN_REVIEW_WINDOW_SECONDS,
            safety_buffer_seconds=HUMAN_REVIEW_SAFETY_BUFFER_SECONDS,
        )
    finally:
        clear_credential()
