"""Fail-closed detached runner for the approved ten-step terminal-only ablation."""

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
from typing import Any

import tinker

from im.assets.model import canonical_artifact_bytes
from im.training.phase3_data import SEALED_TEST_RELATIVE_PATH, load_pinned_tokenizer
from im.training.phase3_full_run import (
    OPTIMIZER,
    ReplayBatch,
    TrainingDatum,
    _checkpoint_path,
    _gradient_evidence,
    _load_batches,
    _load_datums,
    _loss_evidence,
    _provider_result,
    _stage,
    _write_status,
    learning_rate_for_step,
)
from im.training.phase3_full_tinker import TinkerEvaluator, TinkerRunProvider
from im.training.phase3_sampling import read_tinker_api_key
from im.training.phase3r import repeated_ngram_signature

CANDIDATE = Path("review/phase3/wp3r-3-terminal-ablation-candidate-v1")
FREEZE_APPROVAL = Path(
    "review/phase3/wp3r-3-terminal-ablation-approval-v1/owner-decision.json"
)
EXECUTION_DIRECTORY = Path("review/phase3/wp3r-3-terminal-ablation-paid-execution-v1")
RUN_OUTPUT = Path("review/phase3/wp3r-3-terminal-ablation-run-v1")
TOKENIZER_DIRECTORY = Path(".cache/replay-sources/995ad96eacd98c81ed38be0c5b274b04031597b0")
RUN_ID = "wp3r-terminal-ablation-v1"
LAUNCHD_LABEL = "com.interactionmodel.phase3r-terminal-ablation"
LAUNCHD_ENV = "PHASE3R_TERMINAL_LAUNCHD_LABEL"
MAXIMUM_SPEND_USD = 9
SAMPLER_TTL_SECONDS = 3600
MAXIMUM_CHECKPOINT_BYTES = 30_202_922_480
EXPECTED_CANDIDATE_SUMS = (
    "sha256:b9fc9e959b29e788d22818479d931d2e3d21022708acb9e6c1c656d23eee42e4"
)
EXPECTED_FREEZE_APPROVAL = (
    "sha256:7eccdc987418e1f516a27aae04c89418733fa70e9a992467352be8fba28bc9d6"
)
_ALLOWED_PREEXISTING_UNTRACKED = "review/phase3/wp3-4-sft-20260805-v4/"
STDOUT_LOG = Path.home() / "Library/Logs/interactionmodel-wp3r-terminal-v1.stdout.log"
STDERR_LOG = Path.home() / "Library/Logs/interactionmodel-wp3r-terminal-v1.stderr.log"
_SOURCE_PATHS = (
    Path("src/im/training/phase3r_terminal_run.py"),
    Path("scripts/run_phase3r_terminal_ablation.py"),
    Path("tests/test_phase3r_terminal_run.py"),
)


class TerminalRunError(RuntimeError):
    """The terminal-only run failed a frozen trust or pipeline boundary."""


@dataclass(frozen=True, slots=True)
class TerminalRunContract:
    datums: Mapping[str, TrainingDatum]
    batches: tuple[ReplayBatch, ...]
    evaluation: Mapping[str, object]
    root_sha256sums: str = EXPECTED_CANDIDATE_SUMS
    maximum_spend_usd: int = MAXIMUM_SPEND_USD


def _digest(raw: bytes) -> str:
    return f"sha256:{sha256(raw).hexdigest()}"


def _json(path: Path) -> Mapping[str, object]:
    value = json.loads(path.read_bytes())
    if not isinstance(value, Mapping):
        raise TerminalRunError(f"artifact is not a JSON object: {path.name}")
    return value


def _safe(root: Path, path: Path) -> Path:
    candidate = (path if path.is_absolute() else root / path).resolve(strict=True)
    try:
        relative = candidate.relative_to(root)
    except ValueError as error:
        raise TerminalRunError("artifact escapes repository root") from error
    if relative.parts[: len(SEALED_TEST_RELATIVE_PATH.parts)] == SEALED_TEST_RELATIVE_PATH.parts:
        raise TerminalRunError("sealed interaction TEST access is forbidden")
    return candidate


def _verify_sums(directory: Path) -> None:
    lines = (directory / "SHA256SUMS").read_text(encoding="ascii").splitlines()
    declared = set()
    for line in lines:
        expected, name = line.split("  ", 1)
        declared.add(name)
        actual = _digest((directory / name).read_bytes())
        if Path(name).name != name or actual != f"sha256:{expected}":
            raise TerminalRunError("candidate checksum manifest does not close")
    actual_names = {path.name for path in directory.iterdir() if path.is_file()} - {"SHA256SUMS"}
    if declared != actual_names:
        raise TerminalRunError("checksum manifest inventory does not close")


def load_contract(root: Path) -> TerminalRunContract:
    root = root.resolve(strict=True)
    candidate = _safe(root, CANDIDATE)
    if _digest((candidate / "SHA256SUMS").read_bytes()) != EXPECTED_CANDIDATE_SUMS:
        raise TerminalRunError("terminal candidate root checksum drifted")
    _verify_sums(candidate)
    approval_path = _safe(root, FREEZE_APPROVAL)
    if _digest(approval_path.read_bytes()) != EXPECTED_FREEZE_APPROVAL:
        raise TerminalRunError("terminal freeze approval drifted")
    approval = _json(approval_path)
    report = _json(candidate / "terminal-ablation-report.json")
    cost = _json(candidate / "cost-model.json")
    if (
        approval.get("decision") != "approved"
        or approval.get("maximum_spend_usd") != MAXIMUM_SPEND_USD
        or report.get("source_commit") != approval.get("source_commit")
        or report.get("sealed_test") != {"status": "unread"}
        or cost.get("owner_ceiling_usd") != MAXIMUM_SPEND_USD
        or float(cost.get("modeled_total_usd", math.inf)) > MAXIMUM_SPEND_USD
    ):
        raise TerminalRunError("terminal candidate is not the owner-approved offline freeze")
    datums = _load_datums(
        root,
        {
            "path": (CANDIDATE / "amended-datums.jsonl.gz").as_posix(),
            "sha256": report["terminal_datums_sha256"],
        },
    )
    batches = _load_batches(
        root,
        {"path": (CANDIDATE / "successor-batch-plan.json").as_posix()},
        datums,
    )
    evaluation = _json(candidate / "step-10-evaluation-contract.json")
    if len(batches) != 63 or evaluation.get("stop_after_step") != 10:
        raise TerminalRunError("terminal first-ten execution contract drifted")
    return TerminalRunContract(datums, batches[:10], evaluation)


def verify_source(root: Path, source_commit: str, *, allow_execution_artifacts: bool) -> None:
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", source_commit, head], cwd=root, check=False
    )
    if not re.fullmatch(r"[0-9a-f]{40}", source_commit) or ancestor.returncode:
        raise TerminalRunError("runner source commit is not an ancestor of HEAD")
    for path in _SOURCE_PATHS:
        if subprocess.run(
            ["git", "ls-files", "--error-unmatch", path.as_posix()],
            cwd=root,
            check=False,
            capture_output=True,
        ).returncode:
            raise TerminalRunError("runner source is not tracked")
    status = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    allowed_prefixes = [f"?? {_ALLOWED_PREEXISTING_UNTRACKED}"]
    if any(not any(line.startswith(prefix) for prefix in allowed_prefixes) for line in status):
        raise TerminalRunError("worktree contains unauthorized changes")
    changed = set(
        subprocess.run(
            ["git", "diff", "--name-only", f"{source_commit}..HEAD"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.splitlines()
    )
    allowed = (
        {
            path.relative_to(root).as_posix()
            for path in (root / EXECUTION_DIRECTORY).iterdir()
            if path.is_file()
        }
        if allow_execution_artifacts and (root / EXECUTION_DIRECTORY).is_dir()
        else set()
    )
    if changed != allowed:
        raise TerminalRunError("post-source commit contains unauthorized tracked changes")


def _source_hashes(root: Path) -> dict[str, str]:
    return {path.name + "_sha256": _digest((root / path).read_bytes()) for path in _SOURCE_PATHS}


def prepare_execution(root: Path, source_commit: str, output: Path = EXECUTION_DIRECTORY) -> None:
    root = root.resolve(strict=True)
    verify_source(root, source_commit, allow_execution_artifacts=False)
    load_contract(root)
    destination = root / output
    if destination.exists():
        raise TerminalRunError("execution packet output already exists")
    destination.mkdir(mode=0o700, parents=True)
    stdout, stderr = STDOUT_LOG, STDERR_LOG
    script = root / "scripts/run_phase3r_terminal_ablation.py"
    python = root / ".venv/bin/python"
    packet_rel = output / "execution-packet.json"
    auth_rel = output / "owner-authorization.json"
    argv = [
        str(python),
        str(script),
        "--mode",
        "execute",
        "--repository-root",
        str(root),
        "--source-commit",
        source_commit,
        "--execution-packet",
        packet_rel.as_posix(),
        "--authorization",
        auth_rel.as_posix(),
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
            "StandardErrorPath": str(stderr),
            "StandardOutPath": str(stdout),
            "WorkingDirectory": str(root),
        },
        fmt=plistlib.FMT_XML,
        sort_keys=True,
    )
    plist_name = f"{LAUNCHD_LABEL}.plist"
    (destination / plist_name).write_bytes(plist)
    launch = {
        "bootstrap_argv": [
            "/bin/launchctl",
            "bootstrap",
            f"gui/{os.getuid()}",
            str(destination / plist_name),
        ],
        "capture_logs_argv": [
            str(python),
            str(script),
            "--mode",
            "capture-logs",
            "--repository-root",
            str(root),
            "--output",
            RUN_OUTPUT.as_posix(),
            "--stdout-log",
            str(stdout),
            "--stderr-log",
            str(stderr),
        ],
        "kickstart_argv": [
            "/bin/launchctl",
            "kickstart",
            f"gui/{os.getuid()}/{LAUNCHD_LABEL}",
        ],
        "keep_alive": False,
        "kind": "phase3r-terminal-ablation-launch-plan-v1",
        "label": LAUNCHD_LABEL,
        "plist_sha256": _digest(plist),
        "run_at_load": False,
        "stderr_path": str(stderr),
        "stdout_path": str(stdout),
    }
    launch_raw = canonical_artifact_bytes(launch)
    (destination / "launch-plan.json").write_bytes(launch_raw)
    packet = {
        "candidate_root_sha256sums_sha256": EXPECTED_CANDIDATE_SUMS,
        "freeze_approval_sha256": EXPECTED_FREEZE_APPROVAL,
        "kind": "phase3r-terminal-ablation-execution-packet-v1",
        "launch_plan_sha256": _digest(launch_raw),
        "launchagent_plist_sha256": _digest(plist),
        "maximum_spend_usd": MAXIMUM_SPEND_USD,
        "operations": {
            "automatic_retention_requests": 12,
            "fast_requests": 11,
            "optimizer_steps": 10,
            "sampler_checkpoints": 1,
            "state_checkpoints": 1,
        },
        "output_directory": RUN_OUTPUT.as_posix(),
        "run_id": RUN_ID,
        "sealed_test_access": "forbidden",
        "source_commit": source_commit,
        **_source_hashes(root),
    }
    packet_raw = canonical_artifact_bytes(packet)
    (destination / "execution-packet.json").write_bytes(packet_raw)
    authorization_template = {
        "allowed_secret_name": "TINKER_API_KEY",
        "decision": "pending_independent_owner_binding",
        "execution_packet_sha256": _digest(packet_raw),
        "kind": "phase3r-terminal-ablation-paid-authorization-template-v1",
        "maximum_spend_usd": MAXIMUM_SPEND_USD,
        "no_application_retry": True,
        "one_locked_run": True,
        "owner_instruction": None,
        "sealed_test_access": "forbidden",
        "source_commit": source_commit,
    }
    (destination / "owner-authorization-template.json").write_bytes(
        canonical_artifact_bytes(authorization_template)
    )
    names = sorted(path.name for path in destination.iterdir() if path.is_file())
    sums = "".join(
        f"{sha256((destination / name).read_bytes()).hexdigest()}  {name}\n" for name in names
    )
    (destination / "SHA256SUMS").write_text(sums, encoding="ascii")


def _load_execution(
    root: Path, packet_path: Path, authorization_path: Path, source_commit: str
) -> tuple[TerminalRunContract, Mapping[str, object], Mapping[str, object]]:
    contract = load_contract(root)
    execution_directory = _safe(root, EXECUTION_DIRECTORY)
    _verify_sums(execution_directory)
    packet = _json(_safe(root, packet_path))
    authorization = _json(_safe(root, authorization_path))
    launch_plan = execution_directory / "launch-plan.json"
    plist = execution_directory / f"{LAUNCHD_LABEL}.plist"
    if (
        packet.get("kind") != "phase3r-terminal-ablation-execution-packet-v1"
        or packet.get("source_commit") != source_commit
        or packet.get("maximum_spend_usd") != MAXIMUM_SPEND_USD
        or packet.get("candidate_root_sha256sums_sha256") != EXPECTED_CANDIDATE_SUMS
        or packet.get("freeze_approval_sha256") != EXPECTED_FREEZE_APPROVAL
        or packet.get("run_id") != RUN_ID
        or packet.get("output_directory") != RUN_OUTPUT.as_posix()
        or packet.get("sealed_test_access") != "forbidden"
        or packet.get("operations")
        != {
            "automatic_retention_requests": 12,
            "fast_requests": 11,
            "optimizer_steps": 10,
            "sampler_checkpoints": 1,
            "state_checkpoints": 1,
        }
        or packet.get("launch_plan_sha256") != _digest(launch_plan.read_bytes())
        or packet.get("launchagent_plist_sha256") != _digest(plist.read_bytes())
        or any(packet.get(name) != value for name, value in _source_hashes(root).items())
        or authorization.get("kind")
        != "phase3r-terminal-ablation-paid-authorization-v1"
        or authorization.get("decision") != "authorized"
        or authorization.get("source_commit") != source_commit
        or authorization.get("maximum_spend_usd") != MAXIMUM_SPEND_USD
        or authorization.get("execution_packet_sha256")
        != _digest(_safe(root, packet_path).read_bytes())
        or authorization.get("allowed_secret_name") != "TINKER_API_KEY"
        or authorization.get("sealed_test_access") != "forbidden"
        or authorization.get("no_application_retry") is not True
        or authorization.get("one_locked_run") is not True
    ):
        raise TerminalRunError("paid execution authorization does not bind this exact run")
    verify_source(root, source_commit, allow_execution_artifacts=True)
    verify_launchd()
    return contract, packet, authorization


def verify_launchd() -> None:
    if (
        sys.platform != "darwin"
        or os.getppid() != 1
        or os.environ.get(LAUNCHD_ENV) != LAUNCHD_LABEL
    ):
        raise TerminalRunError("paid terminal ablation must run as the frozen LaunchAgent")
    result = subprocess.run(
        ["launchctl", "print", f"gui/{os.getuid()}/{LAUNCHD_LABEL}"],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    if result.returncode or f"pid = {os.getpid()}" not in result.stdout:
        raise TerminalRunError("LaunchAgent process identity mismatch")


def _fast_gate(root: Path, output: Path, contract: TerminalRunContract) -> dict[str, object]:
    path = output / "evaluations/step-010/fast-dev/grades.jsonl"
    grades = [json.loads(line) for line in path.read_bytes().splitlines() if line]
    if len(grades) != 11:
        raise TerminalRunError("fast-11 grades are incomplete")
    manifest = _json(root / "review/phase3/wp3-2-offline-candidate-v4/fast-sentinel-manifest.json")
    active_ids = {
        str(row["state_id"])
        for row in manifest["sentinels"]
        if "hard:active_floor" in row.get("coverage_tags", [])
    }
    counts = {
        "active_floor_respond_error_count": sum(
            row["state_id"] in active_ids
            and isinstance(row.get("predicted_action"), Mapping)
            and row["predicted_action"].get("type") == "respond"
            for row in grades
        ),
        "duplicate_delegate_or_schedule_error_count": sum(
            row.get("executed", {}).get("duplicate_action") is True for row in grades
        ),
        "executed_full_payload_match_count": sum(
            row.get("executed", {}).get("match") is True for row in grades
        ),
        "forbidden_error_count": sum(
            len(row.get("executed", {}).get("hard_failures", [])) for row in grades
        ),
        "parse_union_valid_count": sum(
            row.get("structural", {}).get("parse_union_valid") is True for row in grades
        ),
    }
    fast = contract.evaluation["fast_11"]
    required = fast["success_requires"]
    baseline_rows = fast["baseline_step_10"]["untouched_backbone_fast_11"]["rows"]
    grade_by_id = {str(row["state_id"]): row for row in grades}
    improved = any(
        row["executed_match"] is False
        and grade_by_id[str(row["state_id"])].get("executed", {}).get("match") is True
        and not grade_by_id[str(row["state_id"])].get("executed", {}).get("hard_failures")
        for row in baseline_rows
    )
    passed = (
        counts["active_floor_respond_error_count"]
        <= required["active_floor_respond_error_count_max"]
        and counts["duplicate_delegate_or_schedule_error_count"]
        <= required["duplicate_delegate_or_schedule_error_count_max"]
        and counts["executed_full_payload_match_count"]
        >= required["executed_full_payload_match_count_min"]
        and counts["forbidden_error_count"] <= required["forbidden_error_count_max"]
        and counts["parse_union_valid_count"] >= required["parse_union_valid_count_min"]
        and improved
    )
    return {"counts": counts, "passed": passed, "untouched_backbone_improvement": improved}


def _retention_gate(output: Path, *, step: int = 10) -> dict[str, object]:
    directory = output / "evaluations" / f"step-{step:03d}" / "automatic-retention-12"
    rows = []
    for path in sorted(directory.glob("raw/*/raw-generation.json")):
        raw = _json(path)
        token_ids = raw.get("output_token_ids")
        if not isinstance(token_ids, list):
            raise TerminalRunError("retention raw output lacks token ids")
        rows.append(
            {
                "finish_reason": raw.get("finish_reason"),
                "interaction_protocol_imitation": _interaction_action_json(
                    str(raw.get("decoded_utf8", ""))
                ),
                "repetition_signature": repeated_ngram_signature(token_ids),
                "state_id": raw.get("state_id"),
            }
        )
    if len(rows) != 12:
        raise TerminalRunError("automatic-retention raw outputs are incomplete")
    counts = {
        "normal_stop_count": sum(row["finish_reason"] == "stop" for row in rows),
        "protocol_imitation_count": sum(row["interaction_protocol_imitation"] for row in rows),
        "repetition_signature_count": sum(row["repetition_signature"] is not None for row in rows),
    }
    return {
        "counts": counts,
        "passed": counts
        == {
            "normal_stop_count": 12,
            "protocol_imitation_count": 0,
            "repetition_signature_count": 0,
        },
        "rows": rows,
    }


def _interaction_action_json(text: str) -> bool:
    candidate = text.removesuffix("<|im_end|>").strip()
    try:
        value = json.loads(candidate)
    except json.JSONDecodeError:
        return False
    return isinstance(value, Mapping) and value.get("type") in {
        "cancel",
        "delegate",
        "idle",
        "integrate",
        "mark",
        "nudge",
        "respond",
        "schedule",
        "skip",
    }


def _directory_sha256sums(directory: Path) -> str:
    path = directory / "SHA256SUMS"
    if not path.is_file():
        raise TerminalRunError("evaluation checksum manifest is missing")
    _verify_sums(directory)
    return _digest(path.read_bytes())


def _seal_run(output: Path) -> str:
    paths = sorted(
        path for path in output.rglob("*") if path.is_file() and path != output / "SHA256SUMS"
    )
    sums = "".join(
        f"{sha256(path.read_bytes()).hexdigest()}  {path.relative_to(output).as_posix()}\n"
        for path in paths
    )
    (output / "SHA256SUMS").write_text(sums, encoding="ascii")
    return _digest(sums.encode("ascii"))


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
    root = root.resolve(strict=True)
    contract, _packet, _authorization = _load_execution(
        root, packet_path, authorization_path, source_commit
    )
    if output_path != RUN_OUTPUT or (root / output_path).exists():
        raise TerminalRunError("paid output path is non-canonical or already exists")
    output = root / output_path
    output.mkdir(mode=0o700, parents=True)
    status: dict[str, object] = {
        "kind": "phase3r-terminal-ablation-run-status-v1",
        "authorization_sha256": _digest(_safe(root, authorization_path).read_bytes()),
        "candidate_root_sha256sums_sha256": contract.root_sha256sums,
        "execution_packet_sha256": _digest(_safe(root, packet_path).read_bytes()),
        "run_id": RUN_ID,
        "source_commit": source_commit,
        "status": "running",
    }
    stages: list[dict[str, str]] = []
    _stage(output, status, stages, "preflight_complete", {"maximum_spend_usd": 9})
    key = secret_reader(root / ".env")
    os.environ["TINKER_API_KEY"] = key
    key = ""
    state_path: str | None = None
    sampler_path: str | None = None
    try:
        provider = TinkerRunProvider(service_factory, RUN_ID)
        identity = await _provider_result(provider.initialize())
        _stage(output, status, stages, "provider_identity", dict(identity))
        client = await _provider_result(provider.create_training_client())
        for step, batch in enumerate(contract.batches, start=1):
            data = [contract.datums[datum_id].tinker_datum() for datum_id in batch.datum_ids]
            forward = await _provider_result(client.forward_backward_async(data, "cross_entropy"))
            loss = _loss_evidence(data, forward)
            _stage(output, status, stages, "loss", {"step": step, **loss})
            optimizer = await _provider_result(
                client.optim_step_async(
                    tinker.AdamParams(
                        **(OPTIMIZER | {"learning_rate": learning_rate_for_step(step)})
                    )
                )
            )
            gradient = _gradient_evidence(getattr(optimizer, "metrics", None))
            _stage(
                output,
                status,
                stages,
                "optimizer_update",
                {"gradient": gradient, "learning_rate": learning_rate_for_step(step), "step": step},
            )
        state = await _provider_result(client.save_state_async("wp3r-terminal-state-10", None))
        state_path = _checkpoint_path(state)
        state_size = await _provider_result(provider.checkpoint_size(state_path))
        if state_size > MAXIMUM_CHECKPOINT_BYTES:
            await _provider_result(provider.delete_checkpoint(state_path))
            state_path = None
            raise TerminalRunError("full state exceeds the frozen checkpoint byte ceiling")
        _stage(
            output,
            status,
            stages,
            "state_checkpoint",
            {"path": state_path, "retained": True, "size_bytes": state_size, "step": 10},
        )
        sampler = await _provider_result(
            client.save_weights_for_sampler_async(
                "wp3r-terminal-sampler-10", ttl_seconds=SAMPLER_TTL_SECONDS
            )
        )
        sampler_path = _checkpoint_path(sampler)
        sampler_size = await _provider_result(provider.checkpoint_size(sampler_path))
        if state_size + sampler_size > MAXIMUM_CHECKPOINT_BYTES:
            await _provider_result(provider.delete_checkpoint(state_path))
            state_path = None
            raise TerminalRunError("combined checkpoints exceed the frozen byte ceiling")
        _stage(
            output,
            status,
            stages,
            "sampler_checkpoint",
            {"path": sampler_path, "size_bytes": sampler_size, "ttl_seconds": 3600},
        )
        tokenizer = load_pinned_tokenizer(root, root / TOKENIZER_DIRECTORY)
        evaluator = TinkerEvaluator(root, output, tokenizer, contract, RUN_ID, provider)  # type: ignore[arg-type]
        await evaluator("fast_dev", 10, sampler_path, ())
        fast_directory = output / "evaluations/step-010/fast-dev"
        fast = _fast_gate(root, output, contract)
        _stage(
            output,
            status,
            stages,
            "fast_11",
            {**fast, "evaluation_sha256sums_sha256": _directory_sha256sums(fast_directory)},
        )
        retention_packet = _json(
            root
            / "review/phase3/wp3-4-derived-run-candidate-v2/automatic-retention-12.json"
        )
        await evaluator(
            "automatic_retention_12",
            10,
            sampler_path,
            tuple(retention_packet["rows"]),
        )
        retention = _retention_gate(output)
        retention_directory = output / "evaluations/step-010/automatic-retention-12"
        _stage(
            output,
            status,
            stages,
            "automatic_retention_12",
            {
                **retention,
                "evaluation_sha256sums_sha256": _directory_sha256sums(retention_directory),
            },
        )
        passed = bool(fast["passed"] and retention["passed"])
        status.update(
            {
                "executed_steps": 10,
                "quality_gate_passed": passed,
                "sampler_path": sampler_path,
                "state_path": state_path,
                "status": (
                    "passed_stopped_step_10"
                    if passed
                    else "failed_quality_gate_stopped_step_10"
                ),
            }
        )
    except BaseException as error:
        status.update({"error_type": type(error).__name__, "status": "failed_pipeline"})
        _write_status(output / "status.json", status)
        raise
    finally:
        if sampler_path is not None:
            try:
                provider = locals().get("provider")
                if provider is not None:
                    await _provider_result(provider.delete_checkpoint(sampler_path))
                    _stage(
                        output,
                        status,
                        stages,
                        "sampler_cleanup",
                        {"deleted": True, "path": sampler_path},
                    )
            except BaseException:
                status.update(
                    {"sampler_cleanup": "failed_ttl_fallback", "status": "failed_pipeline"}
                )
        os.environ.pop("TINKER_API_KEY", None)
        _write_status(output / "status.json", status)
        status["root_sha256sums_sha256"] = _seal_run(output)
    return status


def capture_logs(root: Path, output: Path, stdout: Path, stderr: Path) -> Mapping[str, object]:
    root = root.resolve(strict=True)
    if output != RUN_OUTPUT or stdout != STDOUT_LOG or stderr != STDERR_LOG:
        raise TerminalRunError("launch-log capture paths are non-canonical")
    result = subprocess.run(
        ["launchctl", "print", f"gui/{os.getuid()}/{LAUNCHD_LABEL}"],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    if result.returncode == 0 and re.search(r"\bpid = [1-9][0-9]*", result.stdout):
        raise TerminalRunError("launch logs may be captured only after process exit")
    destination = root / output / "launch"
    if destination.exists():
        raise TerminalRunError("launch-log evidence already exists")
    destination.mkdir(mode=0o700, parents=True)
    records = {}
    for name, source in (("stdout.log", stdout), ("stderr.log", stderr)):
        if not source.is_absolute() or source.is_symlink() or not source.is_file():
            raise TerminalRunError("launch-log source is not a fixed regular file")
        raw = source.read_bytes()
        (destination / name).write_bytes(raw)
        records[name] = {"sha256": _digest(raw), "size_bytes": len(raw), "source": str(source)}
    manifest = canonical_artifact_bytes(
        {"kind": "phase3r-terminal-launch-log-manifest-v1", "logs": records, "run_id": RUN_ID}
    )
    (destination / "launch-log-manifest.json").write_bytes(manifest)
    sums = "".join(
        f"{sha256(path.read_bytes()).hexdigest()}  {path.name}\n"
        for path in sorted(destination.iterdir())
    )
    (destination / "SHA256SUMS").write_text(sums, encoding="ascii")
    root_sums = _seal_run(root / output)
    return {
        "launch_log_manifest_sha256": _digest(manifest),
        "root_sha256sums_sha256": root_sums,
    }
