"""Detached, fail-closed executor for the approved Phase 3R rank-16 recovery."""

from __future__ import annotations

import json
import math
import os
import plistlib
import re
import subprocess
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

import tinker

from im.assets.model import canonical_artifact_bytes
from im.training.phase3_data import SEALED_TEST_RELATIVE_PATH, load_pinned_tokenizer
from im.training.phase3_full_run import (
    LockedRunContract,
    ReplayBatch,
    RunSchedule,
    TrainingDatum,
    _checkpoint_path,
    _gradient_evidence,
    _load_batches,
    _load_datums,
    _provider_result,
    _stage,
    _write_status,
)
from im.training.phase3_full_tinker import TinkerEvaluator, TinkerRunProvider
from im.training.phase3_sampling import read_tinker_api_key

CANDIDATE = Path("review/phase3/wp3r-4-rank16-recovery-candidate-v3")
FREEZE_APPROVAL = Path(
    "review/phase3/wp3r-4-rank16-recovery-freeze-approval-v1/owner-decision.json"
)
EXECUTION_DIRECTORY = Path("review/phase3/wp3r-4-rank16-paid-execution-v1")
RUN_OUTPUT = Path("review/phase3/wp3r-4-rank16-recovery-run-v1")
TOKENIZER_DIRECTORY = Path(".cache/replay-sources/995ad96eacd98c81ed38be0c5b274b04031597b0")
RUN_ID = "phase3r-rank16-recovery-v1"
LAUNCHD_LABEL = "com.interactionmodel.phase3r-rank16-recovery-v1"
LAUNCHD_ENV = "PHASE3R_RANK16_LAUNCHD_LABEL"
STDOUT_LOG = Path.home() / "Library/Logs/interactionmodel-phase3r-rank16-v1.stdout.log"
STDERR_LOG = Path.home() / "Library/Logs/interactionmodel-phase3r-rank16-v1.stderr.log"
EXPECTED_CANDIDATE_SUMS = "sha256:056c1238a899d45fa78902940793a9a1d602820b195b11ab157b5109b0b2e139"
EXPECTED_FREEZE_APPROVAL = "sha256:bdf4405c714316912d444d540237d1fb6e35b14e9d94d512681aa57501760c69"
DATUMS_SHA256 = "sha256:aa3c35b6ce875b203a4085608b6ca0558ca73cf059551901733476e0f5886e4a"
BATCH_PLAN_SHA256 = "sha256:c5af5c98f3c001c7d28adac836d852b04aa1bf6e789dad88acd609828481e44f"
MAXIMUM_SPEND_USD = 60
MODELED_SPEND_USD = 51.567352524
MAXIMUM_CHECKPOINT_BYTES = 34_590_720_000
STATE_TTL_SECONDS = 777_600
MINIMUM_STATE_TTL_SECONDS = 691_200
SAMPLER_TTL_SECONDS = 3_600
STATE_STEPS = frozenset({20, 40, 60, 63})
SAMPLER_STEPS = frozenset({10, 20, 40, 60, 63})
FULL_DEV_STEPS = frozenset({20, 40, 60, 63})
RETENTION_STEPS = SAMPLER_STEPS
SEED = 20260801
TERMINAL_TOKEN_ID = 248046
OPTIMIZER = {
    "learning_rate": 1e-4,
    "beta1": 0.9,
    "beta2": 0.95,
    "eps": 1e-8,
    "weight_decay": 0.0,
    "grad_clip_norm": 1.0,
}
_SOURCE_PATHS = (
    Path("src/im/training/phase3_tinker.py"),
    Path("src/im/training/phase3_full_tinker.py"),
    Path("src/im/training/phase3r_rank16_run.py"),
    Path("scripts/run_phase3r_rank16_recovery.py"),
    Path("tests/test_phase3r_rank16_run.py"),
)
_ALLOWED_UNTRACKED = (
    "review/phase3/wp3-4-sft-20260805-v4/",
    "review/phase3/wp3r-3-terminal-ablation-run-v1/",
    "review/phase3/wp3r-4-rank16-recovery-candidate-v1/",
    "review/phase3/wp3r-4-rank16-recovery-candidate-v2/",
    "review/phase3/wp3r-4-rank16-recovery-candidate-v3-review-v1/",
    "review/phase3/wp3r-4-rank16-recovery-candidate-v3/",
)


class Rank16RunError(RuntimeError):
    """A frozen trust, numerical, provider, or persistence boundary failed."""


@dataclass(frozen=True, slots=True)
class Rank16Contract:
    datums: Mapping[str, TrainingDatum]
    batches: tuple[ReplayBatch, ...]
    evaluation: Mapping[str, object]
    training: Mapping[str, object]
    retention_rows: tuple[Mapping[str, object], ...]


def _digest(raw: bytes) -> str:
    return f"sha256:{sha256(raw).hexdigest()}"


def _json(path: Path) -> Mapping[str, object]:
    value = json.loads(path.read_bytes())
    if not isinstance(value, Mapping):
        raise Rank16RunError(f"artifact is not a JSON object: {path.name}")
    return value


def _safe(root: Path, path: Path) -> Path:
    candidate = (path if path.is_absolute() else root / path).resolve(strict=True)
    try:
        relative = candidate.relative_to(root)
    except ValueError as error:
        raise Rank16RunError("artifact escapes repository root") from error
    if relative.parts[: len(SEALED_TEST_RELATIVE_PATH.parts)] == SEALED_TEST_RELATIVE_PATH.parts:
        raise Rank16RunError("sealed interaction TEST access is forbidden")
    return candidate


def _verify_sums(directory: Path) -> None:
    declared: set[str] = set()
    for line in (directory / "SHA256SUMS").read_text(encoding="ascii").splitlines():
        expected, name = line.split("  ", 1)
        if (
            Path(name).name != name
            or _digest((directory / name).read_bytes()) != f"sha256:{expected}"
        ):
            raise Rank16RunError("checksum manifest does not close")
        declared.add(name)
    actual = {path.name for path in directory.iterdir() if path.is_file()} - {"SHA256SUMS"}
    if declared != actual:
        raise Rank16RunError("checksum inventory does not close")


def load_contract(root: Path) -> Rank16Contract:
    root = root.resolve(strict=True)
    candidate = _safe(root, CANDIDATE)
    if _digest((candidate / "SHA256SUMS").read_bytes()) != EXPECTED_CANDIDATE_SUMS:
        raise Rank16RunError("rank-16 candidate root drifted")
    _verify_sums(candidate)
    approval_path = _safe(root, FREEZE_APPROVAL)
    if _digest(approval_path.read_bytes()) != EXPECTED_FREEZE_APPROVAL:
        raise Rank16RunError("rank-16 freeze approval drifted")
    approval = _json(approval_path)
    report = _json(candidate / "rank16-recovery-report.json")
    training = _json(candidate / "training-contract.json")
    evaluation = _json(candidate / "evaluation-contract.json")
    cost = _json(candidate / "cost-model.json")
    if (
        approval.get("decision") != "approved"
        or approval.get("bindings", {}).get("candidate_root_sha256sums_sha256")
        != EXPECTED_CANDIDATE_SUMS
        or report.get("rank16_datums_sha256") != DATUMS_SHA256
        or report.get("successor_batch_plan_sha256") != BATCH_PLAN_SHA256
        or report.get("sealed_test") != {"status": "unread"}
        or cost.get("first_epoch_proposed_ceiling_usd") != MAXIMUM_SPEND_USD
        or float(cost.get("first_epoch_modeled_total_usd", math.inf)) > MAXIMUM_SPEND_USD
        or training.get("automatic_retention_hard_abort") is not True
        or training.get("lora", {}).get("lora_rank") != 16
        or training.get("epochs", {}).get("default") != 1
        or evaluation.get("sealed_test") != {"path_argument_allowed": False, "status": "unread"}
    ):
        raise Rank16RunError("candidate is not the exact approved offline freeze")
    datums = _load_datums(
        root,
        {"path": (CANDIDATE / "rank16-datums.jsonl.gz").as_posix(), "sha256": DATUMS_SHA256},
    )
    batches = _load_batches(
        root,
        {"path": (CANDIDATE / "successor-batch-plan.json").as_posix()},
        datums,
    )
    if len(datums) != 3000 or len(batches) != 63:
        raise Rank16RunError("rank-16 datum or batch count drifted")
    retention = _json(
        root / "review/phase3/wp3-4-derived-run-candidate-v2/automatic-retention-12.json"
    )
    rows = tuple(retention.get("rows", ()))
    if len(rows) != 12:
        raise Rank16RunError("automatic-retention roster drifted")
    return Rank16Contract(datums, batches, evaluation, training, rows)


def learning_rate(step: int) -> float:
    if not 1 <= step <= 126:
        raise Rank16RunError("scheduler step is outside the frozen horizon")
    if step <= 10:
        return 1e-4 * step / 10
    progress = (step - 10) / 116
    return 1e-4 * 0.5 * (1 + math.cos(math.pi * progress))


def verify_source(root: Path, source_commit: str, *, allow_execution: bool) -> None:
    if not re.fullmatch(r"[0-9a-f]{40}", source_commit):
        raise Rank16RunError("source commit is malformed")
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()
    if subprocess.run(
        ["git", "merge-base", "--is-ancestor", source_commit, head], cwd=root, check=False
    ).returncode:
        raise Rank16RunError("runner source commit is not an ancestor of HEAD")
    for path in _SOURCE_PATHS:
        if subprocess.run(
            ["git", "ls-files", "--error-unmatch", path.as_posix()],
            cwd=root,
            check=False,
            capture_output=True,
        ).returncode:
            raise Rank16RunError("runner source is not tracked")
    status = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    allowed = [f"?? {prefix}" for prefix in _ALLOWED_UNTRACKED]
    if allow_execution:
        allowed.append(f"?? {EXECUTION_DIRECTORY.as_posix()}/")
    if any(not any(line.startswith(prefix) for prefix in allowed) for line in status):
        raise Rank16RunError("worktree contains unauthorized changes")
    changed = subprocess.run(
        ["git", "diff", "--name-only", f"{source_commit}..HEAD"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    if changed:
        raise Rank16RunError("tracked source changed after the runner source commit")


def _source_hashes(root: Path) -> dict[str, str]:
    return {path.as_posix(): _digest((root / path).read_bytes()) for path in _SOURCE_PATHS}


def prepare_execution(root: Path, source_commit: str) -> None:
    root = root.resolve(strict=True)
    verify_source(root, source_commit, allow_execution=False)
    load_contract(root)
    destination = root / EXECUTION_DIRECTORY
    if destination.exists() or (root / RUN_OUTPUT).exists():
        raise Rank16RunError("execution packet or run output already exists")
    destination.mkdir(mode=0o700, parents=True)
    script = root / "scripts/run_phase3r_rank16_recovery.py"
    python = root / ".venv/bin/python"
    packet_rel = EXECUTION_DIRECTORY / "execution-packet.json"
    auth_rel = EXECUTION_DIRECTORY / "owner-authorization.json"
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
            "StandardErrorPath": str(STDERR_LOG),
            "StandardOutPath": str(STDOUT_LOG),
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
        "kickstart_argv": ["/bin/launchctl", "kickstart", f"gui/{os.getuid()}/{LAUNCHD_LABEL}"],
        "keep_alive": False,
        "label": LAUNCHD_LABEL,
        "program_arguments": argv,
        "run_at_load": False,
        "stderr_path": str(STDERR_LOG),
        "stdout_path": str(STDOUT_LOG),
    }
    launch_raw = canonical_artifact_bytes(launch)
    (destination / "launch-plan.json").write_bytes(launch_raw)
    packet = {
        "candidate_root_sha256sums_sha256": EXPECTED_CANDIDATE_SUMS,
        "freeze_approval_sha256": EXPECTED_FREEZE_APPROVAL,
        "kind": "phase3r-rank16-paid-execution-packet-v1",
        "launch_plan_sha256": _digest(launch_raw),
        "launchagent_plist_sha256": _digest(plist),
        "maximum_spend_usd": MAXIMUM_SPEND_USD,
        "mode": "first_epoch_only",
        "operations": {
            "full_dev_steps": [20, 40, 60, 63],
            "optimizer_steps": 63,
            "retention_steps": [10, 20, 40, 60, 63],
            "state_steps": [20, 40, 60, 63],
        },
        "output_directory": RUN_OUTPUT.as_posix(),
        "run_id": RUN_ID,
        "sealed_test_access": "forbidden",
        "source_commit": source_commit,
        "source_hashes": _source_hashes(root),
    }
    packet_raw = canonical_artifact_bytes(packet)
    (destination / "execution-packet.json").write_bytes(packet_raw)
    template = {
        "allowed_secret_name": "TINKER_API_KEY",
        "decision": "pending_owner_binding",
        "execution_packet_sha256": _digest(packet_raw),
        "kind": "phase3r-rank16-paid-authorization-template-v1",
        "maximum_spend_usd": MAXIMUM_SPEND_USD,
        "mode": "first_epoch_only",
        "no_application_retry": True,
        "owner_instruction": None,
        "sealed_test_access": "forbidden",
        "source_commit": source_commit,
    }
    (destination / "owner-authorization-template.json").write_bytes(
        canonical_artifact_bytes(template)
    )
    _write_directory_sums(destination)


def _write_directory_sums(directory: Path) -> None:
    names = sorted(
        path.name for path in directory.iterdir() if path.is_file() and path.name != "SHA256SUMS"
    )
    (directory / "SHA256SUMS").write_text(
        "".join(
            f"{sha256((directory / name).read_bytes()).hexdigest()}  {name}\n" for name in names
        ),
        encoding="ascii",
    )


def _load_execution(
    root: Path, packet_path: Path, auth_path: Path, source_commit: str
) -> tuple[Rank16Contract, Mapping[str, object], Mapping[str, object]]:
    contract = load_contract(root)
    directory = _safe(root, EXECUTION_DIRECTORY)
    _verify_sums(directory)
    packet = _json(_safe(root, packet_path))
    auth = _json(_safe(root, auth_path))
    if (
        packet.get("kind") != "phase3r-rank16-paid-execution-packet-v1"
        or packet.get("source_commit") != source_commit
        or packet.get("maximum_spend_usd") != MAXIMUM_SPEND_USD
        or packet.get("mode") != "first_epoch_only"
        or packet.get("source_hashes") != _source_hashes(root)
        or auth.get("kind") != "phase3r-rank16-paid-authorization-v1"
        or auth.get("decision") != "authorized"
        or auth.get("owner_instruction") != "okay start"
        or auth.get("source_commit") != source_commit
        or auth.get("maximum_spend_usd") != MAXIMUM_SPEND_USD
        or auth.get("mode") != "first_epoch_only"
        or auth.get("execution_packet_sha256") != _digest(_safe(root, packet_path).read_bytes())
        or auth.get("allowed_secret_name") != "TINKER_API_KEY"
        or auth.get("no_application_retry") is not True
        or auth.get("sealed_test_access") != "forbidden"
    ):
        raise Rank16RunError("paid authorization does not bind the exact run")
    verify_source(root, source_commit, allow_execution=True)
    _verify_launchd()
    return contract, packet, auth


def _verify_launchd() -> None:
    if (
        sys.platform != "darwin"
        or os.getppid() != 1
        or os.environ.get(LAUNCHD_ENV) != LAUNCHD_LABEL
    ):
        raise Rank16RunError("paid run must execute as the frozen LaunchAgent")
    result = subprocess.run(
        ["launchctl", "print", f"gui/{os.getuid()}/{LAUNCHD_LABEL}"],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    if result.returncode or f"pid = {os.getpid()}" not in result.stdout:
        raise Rank16RunError("LaunchAgent process identity mismatch")


def _loss_breakdown(
    batch: ReplayBatch, datums: Sequence[tinker.Datum], result: Any
) -> dict[str, float]:
    outputs = getattr(result, "loss_fn_outputs", None)
    if not isinstance(outputs, Sequence) or len(outputs) != len(datums):
        raise Rank16RunError("provider returned malformed loss output")
    groups = {"interaction": [0.0, 0.0], "replay": [0.0, 0.0], "terminal": [0.0, 0.0]}
    interaction_count = len(batch.interaction_ids)
    for index, (datum, output) in enumerate(zip(datums, outputs, strict=True)):
        logprobs = output["logprobs"].to_numpy().reshape(-1)
        weights = datum.loss_fn_inputs["weights"].to_numpy().reshape(-1)
        targets = datum.loss_fn_inputs["target_tokens"].to_numpy().reshape(-1)
        if not (len(logprobs) == len(weights) == len(targets)):
            raise Rank16RunError("provider loss tensors differ from the frozen datum")
        group = "interaction" if index < interaction_count else "replay"
        for logprob, weight, token in zip(logprobs, weights, targets, strict=True):
            value = float(weight)
            groups[group][0] += -float(logprob) * value
            groups[group][1] += value
            if int(token) == TERMINAL_TOKEN_ID and value > 0:
                groups["terminal"][0] += -float(logprob) * value
                groups["terminal"][1] += value
    result_row: dict[str, float] = {}
    for group, (loss_sum, mass) in groups.items():
        if mass <= 0 or not all(math.isfinite(value) for value in (loss_sum, mass)):
            raise Rank16RunError(f"non-finite or empty {group} loss evidence")
        result_row[f"{group}_loss"] = loss_sum / mass
        result_row[f"{group}_positive_weight_mass"] = mass
    total_loss = groups["interaction"][0] + groups["replay"][0]
    total_mass = groups["interaction"][1] + groups["replay"][1]
    result_row["normalized_loss"] = total_loss / total_mass
    return result_row


def _evaluator_contract(contract: Rank16Contract) -> LockedRunContract:
    schedule = RunSchedule(
        63, SAMPLER_STEPS, STATE_STEPS, FULL_DEV_STEPS, frozenset({10}), RETENTION_STEPS
    )
    return LockedRunContract(
        EXPECTED_CANDIDATE_SUMS,
        EXPECTED_CANDIDATE_SUMS,
        "42a297ea1eda619b94a3f7172333a91604706d07",
        True,
        60,
        MODELED_SPEND_USD,
        MAXIMUM_CHECKPOINT_BYTES,
        60,
        MODELED_SPEND_USD,
        MAXIMUM_CHECKPOINT_BYTES,
        contract.datums,
        contract.batches,
        schedule,
        schedule,
        contract.retention_rows,
        True,
    )


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
    contract, packet, authorization = _load_execution(
        root, packet_path, authorization_path, source_commit
    )
    if output_path != RUN_OUTPUT or (root / output_path).exists():
        raise Rank16RunError("paid output path is non-canonical or already exists")
    output = root / output_path
    output.mkdir(mode=0o700, parents=True)
    status: dict[str, object] = {
        "kind": "phase3r-rank16-run-status-v1",
        "run_id": RUN_ID,
        "source_commit": source_commit,
        "status": "running",
        "executed_steps": 0,
        "candidate_root_sha256sums_sha256": EXPECTED_CANDIDATE_SUMS,
        "freeze_approval_sha256": EXPECTED_FREEZE_APPROVAL,
        "execution_packet_sha256": _digest(_safe(root, packet_path).read_bytes()),
        "owner_authorization_sha256": _digest(_safe(root, authorization_path).read_bytes()),
    }
    stages: list[dict[str, str]] = []
    _stage(
        output,
        status,
        stages,
        "preflight_complete",
        {
            "candidate_root_sha256sums_sha256": EXPECTED_CANDIDATE_SUMS,
            "execution_packet_sha256": status["execution_packet_sha256"],
            "freeze_approval_sha256": EXPECTED_FREEZE_APPROVAL,
            "maximum_spend_usd": 60,
            "owner_authorization_sha256": status["owner_authorization_sha256"],
            "owner_decision": authorization["decision"],
            "packet_kind": packet["kind"],
        },
    )
    key = secret_reader(root / ".env")
    os.environ["TINKER_API_KEY"] = key
    key = ""
    provider: TinkerRunProvider | None = None
    sampler_path: str | None = None
    states: list[dict[str, object]] = []
    cumulative_tokens = 0
    checkpoint_bytes = 0
    try:
        provider = TinkerRunProvider(service_factory, RUN_ID, lora_rank=16, phase="phase3r")
        identity = await _provider_result(provider.initialize())
        if identity.get("lora_rank") != 16:
            raise Rank16RunError("provider did not authenticate rank 16")
        _stage(output, status, stages, "provider_identity", dict(identity))
        client = await _provider_result(provider.create_training_client())
        tokenizer = load_pinned_tokenizer(root, root / TOKENIZER_DIRECTORY)
        evaluator = TinkerEvaluator(
            root, output, tokenizer, _evaluator_contract(contract), RUN_ID, provider
        )
        for step, batch in enumerate(contract.batches, start=1):
            data = [contract.datums[item].tinker_datum() for item in batch.datum_ids]
            cumulative_tokens += sum(
                len(contract.datums[item].input_tokens) for item in batch.datum_ids
            )
            forward = await _provider_result(client.forward_backward_async(data, "cross_entropy"))
            loss = _loss_breakdown(batch, data, forward)
            _stage(output, status, stages, "loss", {"step": step, **loss})
            lr = learning_rate(step)
            optimizer = await _provider_result(
                client.optim_step_async(tinker.AdamParams(**(OPTIMIZER | {"learning_rate": lr})))
            )
            gradient = _gradient_evidence(getattr(optimizer, "metrics", None))
            _stage(
                output,
                status,
                stages,
                "optimizer_update",
                {"step": step, "learning_rate": lr, "gradient": gradient, "loss": loss},
            )
            status["executed_steps"] = step
            _write_status(output / "status.json", status)
            if step in STATE_STEPS:
                saved = await _provider_result(
                    client.save_state_async(
                        f"phase3r-rank16-state-{step}", ttl_seconds=STATE_TTL_SECONDS
                    )
                )
                state_path = _checkpoint_path(saved)
                _stage(
                    output,
                    status,
                    stages,
                    "state_checkpoint_pending_validation",
                    {"path": state_path, "step": step},
                )
                try:
                    size = await _provider_result(provider.checkpoint_size(state_path))
                    metadata = await _provider_result(provider.checkpoint_metadata(state_path))
                    checkpoint_bytes += size
                    if size <= 0 or checkpoint_bytes > MAXIMUM_CHECKPOINT_BYTES:
                        raise Rank16RunError("full-state storage exceeds the frozen ceiling")
                    remaining = metadata.get("remaining_ttl_seconds")
                    if metadata.get("checkpoint_is_durable") is not True and (
                        not isinstance(remaining, int) or remaining < MINIMUM_STATE_TTL_SECONDS
                    ):
                        raise Rank16RunError("full state cannot survive the human-review window")
                except BaseException:
                    try:
                        await _provider_result(provider.delete_checkpoint(state_path))
                        _stage(
                            output,
                            status,
                            stages,
                            "invalid_state_cleanup",
                            {"deleted": True, "path": state_path, "step": step},
                        )
                    except BaseException as cleanup_error:
                        _stage(
                            output,
                            status,
                            stages,
                            "invalid_state_cleanup_failed",
                            {
                                "error_type": type(cleanup_error).__name__,
                                "path": state_path,
                                "step": step,
                                "ttl_fallback_seconds": STATE_TTL_SECONDS,
                            },
                        )
                    raise
                record = {"step": step, "path": state_path, "size_bytes": size, **metadata}
                states.append(record)
                _stage(output, status, stages, "state_checkpoint", record)
            if step in SAMPLER_STEPS:
                sampler = await _provider_result(
                    client.save_weights_for_sampler_async(
                        f"phase3r-rank16-sampler-{step}", ttl_seconds=SAMPLER_TTL_SECONDS
                    )
                )
                sampler_path = _checkpoint_path(sampler)
                sampler_size = await _provider_result(provider.checkpoint_size(sampler_path))
                checkpoint_bytes += sampler_size
                if sampler_size <= 0 or checkpoint_bytes > MAXIMUM_CHECKPOINT_BYTES:
                    raise Rank16RunError("checkpoint storage exceeds the frozen ceiling")
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
                    if step in FULL_DEV_STEPS:
                        full = await evaluator("full_dev", step, sampler_path, ())
                        _stage(
                            output,
                            status,
                            stages,
                            "full_dev_pending_human",
                            {"step": step, **dict(full)},
                        )
                    else:
                        fast = await evaluator("fast_dev", step, sampler_path, ())
                        _stage(
                            output,
                            status,
                            stages,
                            "fast_dev_diagnostic",
                            {"step": step, **dict(fast)},
                        )
                    retention = await evaluator(
                        "automatic_retention_12", step, sampler_path, contract.retention_rows
                    )
                    _stage(
                        output,
                        status,
                        stages,
                        "automatic_retention_12",
                        {"step": step, **dict(retention)},
                    )
                finally:
                    await _provider_result(provider.delete_checkpoint(sampler_path))
                    _stage(
                        output,
                        status,
                        stages,
                        "sampler_cleanup",
                        {"step": step, "path": sampler_path, "deleted": True},
                    )
                    sampler_path = None
                if retention.get("automatic_guard_passed") is not True:
                    status["status"] = "stopped_retention_catastrophe"
                    break
        else:
            state63 = next(row for row in states if row["step"] == 63)
            next_batch = contract.batches[0]
            control = {
                "completed_epoch": 1,
                "completed_global_step": 63,
                "cumulative_spend_usd": MODELED_SPEND_USD,
                "cumulative_train_token_count": cumulative_tokens,
                "data_order_identity": BATCH_PLAN_SHA256,
                "expected_step_64_learning_rate": learning_rate(64),
                "learning_rate_at_step_63": learning_rate(63),
                "logical_run_id": RUN_ID,
                "next_batch_membership_sha256": next_batch.membership_sha256,
                "next_epoch": 2,
                "next_global_step": 64,
                "optimizer_state_created_at_unix": state63.get("checkpoint_created_at"),
                "optimizer_state_expires_at_unix": state63.get("checkpoint_expires_at"),
                "optimizer_state_path": state63["path"],
                "optimizer_state_remaining_ttl_seconds": state63.get("remaining_ttl_seconds"),
                "optimizer_state_sha256": _digest(str(state63["path"]).encode()),
                "optimizer_state_size_bytes": state63["size_bytes"],
                "parent_provider_training_identity": identity,
                "rank16_datums_sha256": DATUMS_SHA256,
                "scheduler_horizon_steps": 126,
                "source_commit": source_commit,
                "successor_batch_plan_sha256": BATCH_PLAN_SHA256,
                "training_seed": SEED,
                "warmup_complete": True,
            }
            control_raw = canonical_artifact_bytes(control)
            (output / "step-63-resume-control-state.json").write_bytes(control_raw)
            _stage(
                output,
                status,
                stages,
                "human_review_pause",
                {"resume_control_sha256": _digest(control_raw), "step": 63},
            )
            status["status"] = "stopped_pending_human_dev_review"
    except BaseException as error:
        status.update({"error_type": type(error).__name__, "status": "failed_pipeline"})
        raise
    finally:
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
    sums = "".join(
        f"{sha256(path.read_bytes()).hexdigest()}  {path.relative_to(output).as_posix()}\n"
        for path in paths
    )
    (output / "SHA256SUMS").write_text(sums, encoding="ascii")
    return _digest(sums.encode())


def capture_logs(root: Path, output: Path, stdout: Path, stderr: Path) -> Mapping[str, object]:
    root = root.resolve(strict=True)
    if output != RUN_OUTPUT or stdout != STDOUT_LOG or stderr != STDERR_LOG:
        raise Rank16RunError("launch-log paths are non-canonical")
    running = subprocess.run(
        ["launchctl", "print", f"gui/{os.getuid()}/{LAUNCHD_LABEL}"],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    if running.returncode == 0 and re.search(r"\bpid = [1-9][0-9]*", running.stdout):
        raise Rank16RunError("logs may be captured only after process exit")
    destination = root / output / "launch"
    if destination.exists():
        raise Rank16RunError("launch logs already captured")
    destination.mkdir(mode=0o700, parents=True)
    records = {}
    for name, source in (("stdout.log", stdout), ("stderr.log", stderr)):
        raw = source.read_bytes()
        (destination / name).write_bytes(raw)
        records[name] = {"source": str(source), "size_bytes": len(raw), "sha256": _digest(raw)}
    raw = canonical_artifact_bytes(
        {"kind": "phase3r-rank16-launch-log-manifest-v1", "logs": records}
    )
    (destination / "launch-log-manifest.json").write_bytes(raw)
    _write_directory_sums(destination)
    root_sums = _seal_run(root / output)
    return {
        "launch_log_manifest_sha256": _digest(raw),
        "root_sha256sums_sha256": root_sums,
    }
