"""Fail-closed, separately-authorized continuation from the immutable rank-16 step-20 state."""

from __future__ import annotations

import json
import os
import plistlib
import re
import subprocess
import sys
from collections.abc import Mapping
from hashlib import sha256
from pathlib import Path
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
from im.training.phase3_full_tinker import TinkerEvaluator, TinkerRunProvider
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
    _evaluator_contract,
    _loss_breakdown,
    _seal_run,
    learning_rate,
)
from im.training.phase3r_rank16_run import load_contract as load_rank16

CANDIDATE = Path("review/phase3/wp3r-6-step20-continuation-candidate-v2")
V3 = Path("review/phase3/wp3r-5-repetition-detector-v3-candidate-v1")
RUN = Path("review/phase3/wp3r-4-rank16-recovery-run-v1")
EXECUTION = Path("review/phase3/wp3r-6-step20-continuation-execution-v1")
OUTPUT = Path("review/phase3/wp3r-6-step20-continuation-run-v1")
FAILURE_OUTPUT = Path("review/phase3/wp3r-6-step20-continuation-early-failure-v1")
RUN_ID = "phase3r-rank16-step20-continuation-v1"
LABEL = "com.interactionmodel.phase3r-step20-continuation-v1"
ENV = "PHASE3R_STEP20_CONTINUATION_LABEL"
STDOUT_LOG = Path.home() / "Library/Logs/interactionmodel-phase3r-step20-v1.stdout.log"
STDERR_LOG = Path.home() / "Library/Logs/interactionmodel-phase3r-step20-v1.stderr.log"
V3_SUMS = "sha256:e0c9e6b7f26b07665390ac560eff26535365ada471f06abdf93a9439a892aae6"
RUN_SUMS = "sha256:6f3095a74cd2bd2fb47c5540999cbed1f887d68c1ca702e1f1d5c3bbba47abd5"
CONTRACT_SOURCE_COMMIT = "b4774d8c032120bc66c2077171ca71a2169bd8d7"
CEILING_USD = 15
SAMPLER_TTL_SECONDS = 3_600
STATE_TTL_SECONDS = 777_600
MINIMUM_SOURCE_STATE_TTL_SECONDS = 21_600
MINIMUM_STEP30_STATE_TTL_SECONDS = 691_200
SOURCE_STATE_SIZE_BYTES = 3_305_164_149
MAXIMUM_CHECKPOINT_BYTES = 10_000_000_000
_SOURCE_PATHS = (
    Path("src/im/training/phase3r_step20_continuation.py"),
    Path("scripts/build_phase3r_step20_continuation.py"),
    Path("scripts/run_phase3r_step20_continuation.py"),
)


class ContinuationError(RuntimeError):
    pass


def _digest(raw: bytes) -> str:
    return f"sha256:{sha256(raw).hexdigest()}"


def _json(path: Path) -> Mapping[str, object]:
    value = json.loads(path.read_bytes())
    if not isinstance(value, Mapping):
        raise ContinuationError(f"not an object: {path.name}")
    return value


def _sums(directory: Path, *, allowed_extras: frozenset[str] = frozenset()) -> None:
    seen: set[str] = set()
    for line in (directory / "SHA256SUMS").read_text("ascii").splitlines():
        digest, name = line.split("  ", 1)
        relative = Path(name)
        if (
            relative.is_absolute()
            or ".." in relative.parts
            or sha256((directory / relative).read_bytes()).hexdigest() != digest
        ):
            raise ContinuationError("checksum does not close")
        seen.add(name)
    actual = {
        path.relative_to(directory).as_posix()
        for path in directory.rglob("*")
        if path.is_file() and path != directory / "SHA256SUMS"
    }
    if actual - allowed_extras != seen or not allowed_extras.issuperset(actual - seen):
        raise ContinuationError("checksum inventory does not close")


def _verify_source(root: Path, source_commit: str) -> None:
    if not re.fullmatch(r"[0-9a-f]{40}", source_commit):
        raise ContinuationError("source commit is malformed")
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if head != source_commit:
        raise ContinuationError("continuation requires exact source HEAD")
    for path in _SOURCE_PATHS:
        for args in (
            ["git", "ls-files", "--error-unmatch", path.as_posix()],
            ["git", "cat-file", "-e", f"{source_commit}:{path.as_posix()}"],
        ):
            if subprocess.run(args, cwd=root, check=False, capture_output=True).returncode:
                raise ContinuationError("continuation source is not contained in its commit")
    for args in (["git", "diff", "--quiet"], ["git", "diff", "--cached", "--quiet"]):
        if subprocess.run(args, cwd=root, check=False).returncode:
            raise ContinuationError("tracked worktree changed after source freeze")


def _verify_launchd() -> None:
    if sys.platform != "darwin" or os.getppid() != 1 or os.environ.get(ENV) != LABEL:
        raise ContinuationError("paid continuation must run as the frozen LaunchAgent")
    result = subprocess.run(
        ["launchctl", "print", f"gui/{os.getuid()}/{LABEL}"],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    if result.returncode or f"pid = {os.getpid()}" not in result.stdout:
        raise ContinuationError("LaunchAgent process identity mismatch")


def _checkpoint_lifetime_valid(
    size_bytes: object,
    metadata: Mapping[str, object],
    *,
    minimum_ttl_seconds: int,
) -> bool:
    remaining = metadata.get("remaining_ttl_seconds")
    durable = metadata.get("checkpoint_is_durable") is True
    return (
        isinstance(size_bytes, int)
        and not isinstance(size_bytes, bool)
        and 0 < size_bytes <= MAXIMUM_CHECKPOINT_BYTES
        and (
            durable
            or (
                isinstance(remaining, int)
                and not isinstance(remaining, bool)
                and remaining >= minimum_ttl_seconds
            )
        )
    )


def _full_dev_allowed(step: int, retention: Mapping[str, object]) -> bool:
    detector = retention.get("detector_v3")
    return step == 30 and isinstance(detector, Mapping) and detector.get("abort_optimizer") is False


def load_continuation(
    root: Path,
    *,
    source_commit: str,
    expected_candidate_sums: str | None = None,
) -> tuple[Rank16Contract, Mapping[str, object], str]:
    root = root.resolve(strict=True)
    for path, digest in ((V3, V3_SUMS), (RUN, RUN_SUMS)):
        if _digest((root / path / "SHA256SUMS").read_bytes()) != digest:
            raise ContinuationError("frozen lineage root drifted")
        _sums(root / path)
    candidate_sums = _digest((root / CANDIDATE / "SHA256SUMS").read_bytes())
    if expected_candidate_sums is not None and candidate_sums != expected_candidate_sums:
        raise ContinuationError("continuation candidate root drifted")
    _sums(root / CANDIDATE)
    contract = _json(root / CANDIDATE / "continuation-contract.json")
    cost = _json(root / CANDIDATE / "cost-model.json")
    rank = load_rank16(root)
    state = _json(root / RUN / "evidence/0048-state_checkpoint.json")["evidence"]
    resume = contract.get("resume")
    steps = contract.get("steps")
    if not isinstance(resume, Mapping) or not isinstance(steps, list) or len(steps) != 10:
        raise ContinuationError("continuation contract is malformed")
    if (
        contract.get("kind") != "phase3r-exact-step20-continuation-contract-v1"
        or contract.get("source_commit") != CONTRACT_SOURCE_COMMIT
        or contract.get("training_variables_changed") != []
        or contract.get("evaluation_sequence")
        != [
            {
                "operation": "automatic_retention_12_then_detector_v3",
                "step": 25,
                "on_abort": "stop_before_step_26",
            },
            {
                "operation": "automatic_retention_12_then_detector_v3",
                "step": 30,
                "on_abort": "stop_without_full_dev",
            },
            {
                "condition": "step_30_detector_v3_abort_optimizer_is_false",
                "operation": "full_dev_300",
                "step": 30,
            },
        ]
        or contract.get("stops")
        != {"after_step": 30, "automatic_step_31": False, "catastrophe_hard_stop": True}
        or cost.get("ceiling_usd") != CEILING_USD
        or float(cost.get("modeled_upper_usd", CEILING_USD + 1)) > CEILING_USD
        or resume.get("next_global_step") != 21
        or resume.get("next_batch_membership_sha256") != rank.batches[20].membership_sha256
        or resume.get("next_learning_rate") != learning_rate(21)
        or resume.get("scheduler_horizon_steps") != 126
        or resume.get("warmup_steps") != 10
        or resume.get("seed") != 20260801
        or resume.get("order_identity") != BATCH_PLAN_SHA256
        or not isinstance(state, Mapping)
        or resume.get("retained_state", {}).get("path_sha256")
        != _digest(str(state.get("path")).encode())
    ):
        raise ContinuationError("exact step-20 continuity assertion drifted")
    for expected, row in zip(range(21, 31), steps, strict=True):
        if (
            not isinstance(row, Mapping)
            or row.get("global_step") != expected
            or row.get("membership_sha256") != rank.batches[expected - 1].membership_sha256
            or row.get("learning_rate") != learning_rate(expected)
        ):
            raise ContinuationError("frozen continuation batch or scheduler drifted")
    path = state.get("path")
    if not isinstance(path, str) or not path:
        raise ContinuationError("immutable state evidence lacks its path")
    return rank, contract, path


def prepare(root: Path, source_commit: str) -> None:
    root = root.resolve(strict=True)
    _verify_source(root, source_commit)
    _rank, _contract, state_path = load_continuation(root, source_commit=source_commit)
    if (root / EXECUTION).exists() or (root / OUTPUT).exists():
        raise ContinuationError("canonical continuation output already exists")
    destination = root / EXECUTION
    destination.mkdir(mode=0o700, parents=True)
    argv = [
        str(root / ".venv/bin/python"),
        str(root / "scripts/run_phase3r_step20_continuation.py"),
        "--mode",
        "execute",
        "--repository-root",
        str(root),
        "--source-commit",
        source_commit,
        "--authorization",
        (EXECUTION / "owner-authorization.json").as_posix(),
    ]
    plist = plistlib.dumps(
        {
            "Label": LABEL,
            "ProgramArguments": argv,
            "WorkingDirectory": str(root),
            "KeepAlive": False,
            "RunAtLoad": False,
            "EnvironmentVariables": {ENV: LABEL},
            "StandardErrorPath": str(STDERR_LOG),
            "StandardOutPath": str(STDOUT_LOG),
        },
        fmt=plistlib.FMT_XML,
        sort_keys=True,
    )
    plist_name = f"{LABEL}.plist"
    (destination / plist_name).write_bytes(plist)
    launch = {
        "bootout_argv": ["/bin/launchctl", "bootout", f"gui/{os.getuid()}/{LABEL}"],
        "bootstrap_argv": [
            "/bin/launchctl",
            "bootstrap",
            f"gui/{os.getuid()}",
            str(destination / plist_name),
        ],
        "capture_logs_argv": [
            str(root / ".venv/bin/python"),
            str(root / "scripts/run_phase3r_step20_continuation.py"),
            "--mode",
            "capture-logs",
            "--repository-root",
            str(root),
        ],
        "keep_alive": False,
        "kickstart_argv": ["/bin/launchctl", "kickstart", f"gui/{os.getuid()}/{LABEL}"],
        "label": LABEL,
        "run_at_load": False,
        "stderr_path": str(STDERR_LOG),
        "stdout_path": str(STDOUT_LOG),
    }
    launch_raw = canonical_artifact_bytes(launch)
    (destination / "launch-plan.json").write_bytes(launch_raw)
    packet = {
        "kind": "phase3r-step20-continuation-execution-packet-v1",
        "candidate_sha256": _digest((root / CANDIDATE / "SHA256SUMS").read_bytes()),
        "detector_v3_sha256": V3_SUMS,
        "immutable_run_sha256": RUN_SUMS,
        "source_commit": source_commit,
        "run_id": RUN_ID,
        "maximum_spend_usd": CEILING_USD,
        "steps": list(range(21, 31)),
        "next_step": 21,
        "state_path_sha256": _digest(state_path.encode()),
        "no_step_31": True,
        "lora_rank": 16,
        "seed": 20260801,
        "batch_plan_sha256": BATCH_PLAN_SHA256,
        "datums_sha256": DATUMS_SHA256,
        "launchagent_plist_sha256": _digest(plist),
        "launch_plan_sha256": _digest(launch_raw),
        "stdout_path": str(STDOUT_LOG),
        "stderr_path": str(STDERR_LOG),
    }
    (destination / "execution-packet.json").write_bytes(canonical_artifact_bytes(packet))
    (destination / "owner-authorization-template.json").write_bytes(
        canonical_artifact_bytes(
            {
                "kind": "phase3r-step20-continuation-authorization-v1",
                "decision": "pending_owner_binding",
                "execution_packet_sha256": _digest(
                    (destination / "execution-packet.json").read_bytes()
                ),
                "maximum_spend_usd": CEILING_USD,
                "no_application_retry": True,
                "allowed_secret_name": "TINKER_API_KEY",
                "candidate_sha256": packet["candidate_sha256"],
                "checkpoint_access": True,
                "checkpoint_creation": True,
                "provider_calls": True,
                "sealed_test_access": "forbidden",
                "source_commit": source_commit,
                "owner_instruction": None,
            }
        )
    )
    names = sorted(p.name for p in destination.iterdir())
    (destination / "SHA256SUMS").write_text(
        "".join(f"{sha256((destination / n).read_bytes()).hexdigest()}  {n}\n" for n in names),
        encoding="ascii",
    )


def capture_logs(root: Path) -> Mapping[str, object]:
    root = root.resolve(strict=True)
    running = subprocess.run(
        ["launchctl", "print", f"gui/{os.getuid()}/{LABEL}"],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    if running.returncode == 0 and re.search(r"\bpid = [1-9][0-9]*", running.stdout):
        raise ContinuationError("logs may be captured only after process exit")
    parent = root / (OUTPUT if (root / OUTPUT).exists() else FAILURE_OUTPUT)
    destination = parent / "launch"
    if destination.exists():
        raise ContinuationError("launch logs already captured")
    destination.mkdir(mode=0o700, parents=True)
    records = {}
    for name, source in (("stdout.log", STDOUT_LOG), ("stderr.log", STDERR_LOG)):
        raw = source.read_bytes()
        (destination / name).write_bytes(raw)
        records[name] = {"sha256": _digest(raw), "size_bytes": len(raw), "source": str(source)}
    manifest = {
        "kind": "phase3r-step20-continuation-launch-log-manifest-v1",
        "logs": records,
    }
    (destination / "launch-log-manifest.json").write_bytes(canonical_artifact_bytes(manifest))
    names = sorted(path.name for path in destination.iterdir() if path.is_file())
    (destination / "SHA256SUMS").write_text(
        "".join(
            f"{sha256((destination / name).read_bytes()).hexdigest()}  {name}\n" for name in names
        ),
        encoding="ascii",
    )
    _seal_run(parent)
    return {"destination": destination.relative_to(root).as_posix(), **manifest}


def _retention_v3(output: Path, step: int) -> Mapping[str, object]:
    directory = output / "evaluations" / f"step-{step:03d}" / "automatic-retention-12"
    raw = sorted((directory / "raw").glob("*/raw-generation.json"))
    if len(raw) != 12:
        raise ContinuationError("all 12 retention outputs must persist before aggregation")
    old_report = _json(directory / "report.json")
    old_rows = old_report.get("rows")
    if not isinstance(old_rows, list) or len(old_rows) != 12:
        raise ContinuationError("historical retention grader report is malformed")
    prior_by_id = {str(row.get("request_id")): row for row in old_rows if isinstance(row, Mapping)}
    rows = []
    evidence = []
    for path in raw:
        value = _json(path)
        tokens = value.get("output_token_ids")
        if not isinstance(tokens, list) or any(not isinstance(token, int) for token in tokens):
            raise ContinuationError("retention raw token evidence is malformed")
        state_id = str(value.get("state_id"))
        prior = prior_by_id.get(state_id)
        if not isinstance(prior, Mapping):
            raise ContinuationError("retention v2/v3 row identity mismatch")
        old_detector = prior.get("catastrophe_detector")
        if not isinstance(old_detector, Mapping):
            raise ContinuationError("retention v2 row lacks its detector evidence")
        raw_sha = _digest(path.read_bytes())
        if prior.get("raw_record_sha256") != raw_sha:
            raise ContinuationError("retention raw record hash drifted")
        if repeated_ngram_signature(tokens) != old_detector.get("repetition_signature"):
            raise ContinuationError("historical repetition signal did not reproduce")
        diagnostic = repetition_diagnostics_v3(tokens)
        aggregate = {
            "empty_output": old_detector.get("empty_output") is True,
            "high_confidence_generation_loop": diagnostic["high_confidence_generation_loop"],
            "high_confidence_refusal": old_detector.get("high_confidence_refusal") is True,
            "interaction_protocol_imitation": (
                old_detector.get("interaction_protocol_imitation") is True
            ),
            "new_length_termination": old_detector.get("new_length_termination") is True,
            "stylistic_or_structural_repetition": diagnostic["stylistic_or_structural_repetition"],
        }
        rows.append(aggregate)
        evidence.append(
            {
                "finish_reason": value.get("finish_reason"),
                "output_token_count": len(tokens),
                "raw_record_sha256": raw_sha,
                "request_id": state_id,
                "v2_repetition_signature": old_detector.get("repetition_signature"),
                "v3": diagnostic,
            }
        )
    result = retention_catastrophe_v3(rows)
    return {
        "detector_v3": result,
        "raw_record_count": len(rows),
        "raw_records_sha256": _digest(
            canonical_artifact_bytes([_digest(path.read_bytes()) for path in raw])
        ),
        "rows": evidence,
    }


async def execute(
    *,
    root: Path,
    authorization_path: Path,
    source_commit: str,
    service_factory: Any = tinker.ServiceClient,
    secret_reader: Any = read_tinker_api_key,
) -> Mapping[str, object]:
    root = root.resolve(strict=True)
    _verify_source(root, source_commit)
    execution_directory = root / EXECUTION
    _sums(execution_directory, allowed_extras=frozenset({"owner-authorization.json"}))
    packet_path = execution_directory / "execution-packet.json"
    packet = _json(packet_path)
    auth_path = (
        authorization_path if authorization_path.is_absolute() else root / authorization_path
    ).resolve(strict=True)
    if auth_path.parent != execution_directory or auth_path.name != "owner-authorization.json":
        raise ContinuationError("owner authorization path is non-canonical")
    auth = _json(auth_path)
    packet_sha = _digest(packet_path.read_bytes())
    if (
        packet.get("kind") != "phase3r-step20-continuation-execution-packet-v1"
        or packet.get("source_commit") != source_commit
        or packet.get("maximum_spend_usd") != CEILING_USD
        or packet.get("steps") != list(range(21, 31))
        or packet.get("next_step") != 21
        or packet.get("no_step_31") is not True
        or packet.get("run_id") != RUN_ID
        or packet.get("lora_rank") != 16
        or packet.get("seed") != 20260801
        or packet.get("detector_v3_sha256") != V3_SUMS
        or packet.get("immutable_run_sha256") != RUN_SUMS
        or packet.get("batch_plan_sha256") != BATCH_PLAN_SHA256
        or packet.get("datums_sha256") != DATUMS_SHA256
        or packet.get("launchagent_plist_sha256")
        != _digest((execution_directory / f"{LABEL}.plist").read_bytes())
        or packet.get("launch_plan_sha256")
        != _digest((execution_directory / "launch-plan.json").read_bytes())
        or auth.get("kind") != "phase3r-step20-continuation-authorization-v1"
        or auth.get("decision") != "authorized"
        or auth.get("execution_packet_sha256") != packet_sha
        or auth.get("maximum_spend_usd") != CEILING_USD
        or auth.get("no_application_retry") is not True
        or auth.get("allowed_secret_name") != "TINKER_API_KEY"
        or auth.get("candidate_sha256") != packet.get("candidate_sha256")
        or auth.get("checkpoint_access") is not True
        or auth.get("checkpoint_creation") is not True
        or auth.get("provider_calls") is not True
        or auth.get("sealed_test_access") != "forbidden"
        or auth.get("source_commit") != source_commit
        or not isinstance(auth.get("owner_instruction"), str)
        or not str(auth.get("owner_instruction")).strip()
    ):
        raise ContinuationError("owner authorization does not bind this exact continuation")
    candidate_sha = packet.get("candidate_sha256")
    if not isinstance(candidate_sha, str):
        raise ContinuationError("execution packet lacks its candidate root")
    rank, contract, state_path = load_continuation(
        root,
        source_commit=source_commit,
        expected_candidate_sums=candidate_sha,
    )
    if packet.get("state_path_sha256") != _digest(state_path.encode()):
        raise ContinuationError("execution packet state identity drifted")
    _verify_launchd()
    if (root / OUTPUT).exists():
        raise ContinuationError("canonical output already exists")
    output = root / OUTPUT
    output.mkdir(mode=0o700, parents=True)
    status: dict[str, object] = {
        "kind": "phase3r-step20-continuation-status-v1",
        "status": "running",
        "executed_steps": [],
        "maximum_spend_usd": CEILING_USD,
        "execution_packet_sha256": packet_sha,
        "owner_authorization_sha256": _digest(auth_path.read_bytes()),
        "source_commit": source_commit,
    }
    stages: list[dict[str, str]] = []
    _stage(
        output,
        status,
        stages,
        "preflight_complete",
        {
            "next_global_step": 21,
            "state_path_sha256": _digest(state_path.encode()),
            "detector_v3_sha256": V3_SUMS,
        },
    )
    key = secret_reader(root / ".env")
    os.environ["TINKER_API_KEY"] = key
    key = ""
    provider: TinkerRunProvider | None = None
    sampler_path: str | None = None
    state30_path: str | None = None
    try:
        provider = TinkerRunProvider(service_factory, RUN_ID, lora_rank=16, phase="phase3r")
        state_size = await _provider_result(provider.checkpoint_size(state_path))
        state_metadata = await _provider_result(provider.checkpoint_metadata(state_path))
        retained = contract.get("resume", {}).get("retained_state", {})
        if state_size != SOURCE_STATE_SIZE_BYTES:
            raise ContinuationError("retained source-state size drifted")
        if (
            not isinstance(retained, Mapping)
            or state_metadata.get("checkpoint_created_at") != retained.get("created_at_unix")
            or state_metadata.get("checkpoint_expires_at") != retained.get("expires_at_unix")
        ):
            raise ContinuationError("retained source-state timing identity drifted")
        remaining = state_metadata.get("remaining_ttl_seconds")
        if not isinstance(remaining, int) or remaining < MINIMUM_SOURCE_STATE_TTL_SECONDS:
            raise ContinuationError("retained source state cannot survive the continuation")
        _stage(
            output,
            status,
            stages,
            "source_state_verified",
            {
                "path_sha256": _digest(state_path.encode()),
                "size_bytes": state_size,
                **state_metadata,
            },
        )
        client = await _provider_result(
            provider.restore_training_client_with_optimizer(
                state_path, {"phase": "phase3r", "run_id": RUN_ID, "continuation_from_step": "20"}
            )
        )
        resumed_info = await _provider_result(client.get_info_async())
        _stage(
            output,
            status,
            stages,
            "optimizer_restore_verified",
            {
                "model_id": str(getattr(resumed_info, "model_id", "")),
                "next_batch_membership_sha256": rank.batches[20].membership_sha256,
                "next_global_step": 21,
                "next_learning_rate": learning_rate(21),
                "no_optimizer_reset": True,
                "no_scheduler_reset": True,
                "no_warmup_reset": True,
            },
        )
        tokenizer = load_pinned_tokenizer(
            root, root / ".cache/replay-sources/995ad96eacd98c81ed38be0c5b274b04031597b0"
        )
        evaluator = TinkerEvaluator(
            root, output, tokenizer, _evaluator_contract(rank), RUN_ID, provider
        )
        for step in range(21, 31):
            batch = rank.batches[step - 1]
            data = [rank.datums[item].tinker_datum() for item in batch.datum_ids]
            forward = await _provider_result(client.forward_backward_async(data, "cross_entropy"))
            loss = _loss_breakdown(batch, data, forward)
            _stage(output, status, stages, "loss", {"step": step, **loss})
            optimizer = await _provider_result(
                client.optim_step_async(
                    tinker.AdamParams(
                        learning_rate=learning_rate(step),
                        beta1=0.9,
                        beta2=0.95,
                        eps=1e-8,
                        weight_decay=0.0,
                        grad_clip_norm=1.0,
                    )
                )
            )
            _stage(
                output,
                status,
                stages,
                "optimizer_update",
                {
                    "step": step,
                    "learning_rate": learning_rate(step),
                    "gradient": _gradient_evidence(getattr(optimizer, "metrics", None)),
                },
            )
            status["executed_steps"].append(step)
            _write_status(output / "status.json", status)
            if step in {25, 30}:
                if step == 30:
                    saved_state = await _provider_result(
                        client.save_state_async(f"{RUN_ID}-state-30", ttl_seconds=STATE_TTL_SECONDS)
                    )
                    state30_path = _checkpoint_path(saved_state)
                    _stage(
                        output,
                        status,
                        stages,
                        "step30_state_checkpoint_pending_validation",
                        {"path": state30_path, "step": 30},
                    )
                    try:
                        state30_size = await _provider_result(
                            provider.checkpoint_size(state30_path)
                        )
                        state30_metadata = await _provider_result(
                            provider.checkpoint_metadata(state30_path)
                        )
                        if not _checkpoint_lifetime_valid(
                            state30_size,
                            state30_metadata,
                            minimum_ttl_seconds=MINIMUM_STEP30_STATE_TTL_SECONDS,
                        ):
                            raise ContinuationError(
                                "step-30 state size or human-review lifetime is invalid"
                            )
                    except BaseException:
                        try:
                            await _provider_result(provider.delete_checkpoint(state30_path))
                            _stage(
                                output,
                                status,
                                stages,
                                "invalid_step30_state_cleanup",
                                {"deleted": True, "path": state30_path},
                            )
                            state30_path = None
                        except BaseException as cleanup_error:
                            _stage(
                                output,
                                status,
                                stages,
                                "invalid_step30_state_cleanup_failed",
                                {
                                    "error_type": type(cleanup_error).__name__,
                                    "path": state30_path,
                                    "ttl_fallback_seconds": STATE_TTL_SECONDS,
                                },
                            )
                        raise
                    _stage(
                        output,
                        status,
                        stages,
                        "step30_state_checkpoint",
                        {
                            "path": state30_path,
                            "size_bytes": state30_size,
                            **state30_metadata,
                        },
                    )
                sampler = await _provider_result(
                    client.save_weights_for_sampler_async(
                        f"{RUN_ID}-sampler-{step}", ttl_seconds=SAMPLER_TTL_SECONDS
                    )
                )
                sampler_path = _checkpoint_path(sampler)
                sampler_size = await _provider_result(provider.checkpoint_size(sampler_path))
                if sampler_size <= 0 or sampler_size > MAXIMUM_CHECKPOINT_BYTES:
                    raise ContinuationError("sampler checkpoint exceeds its storage ceiling")
                _stage(
                    output,
                    status,
                    stages,
                    "sampler_checkpoint",
                    {"path": sampler_path, "size_bytes": sampler_size, "step": step},
                )
                try:
                    await evaluator(
                        "automatic_retention_12", step, sampler_path, rank.retention_rows
                    )
                    retention = _retention_v3(output, step)
                    _stage(
                        output,
                        status,
                        stages,
                        "automatic_retention_v3",
                        {"step": step, **retention},
                    )
                    if _full_dev_allowed(step, retention):
                        await evaluator("full_dev", step, sampler_path, ())
                        _stage(output, status, stages, "full_dev_pending_human", {"step": step})
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
                if retention["detector_v3"]["abort_optimizer"] is True:
                    status["status"] = "stopped_retention_catastrophe_v3"
                    break
        else:
            status["status"] = "stopped_pending_owner_review_step_30"
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
