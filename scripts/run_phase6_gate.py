#!/usr/bin/env python3
"""Build, verify, execute, or tear down the single Phase 5/6 gate."""

from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from im.assets.model import canonical_artifact_bytes
from im.generation.phase6_cloud import (
    CONTAINER,
    NAT,
    ROUTER,
    absence_commands,
    default_runner,
    evidence_commands,
    execute_commands,
    launch_commands,
    teardown_commands,
    tunnel_command,
)
from im.generation.phase6_gate import (
    PACKAGE_RELATIVE,
    TEARDOWN_OUTPUT_RELATIVE,
    TINKER_QUALIFICATION_OUTPUT_RELATIVE,
    Phase6GateError,
    claim_authorization,
    load_authorization,
    qualify_frozen_variants,
    qualify_step63_with_tinker,
    reuse_v5_step63_adapter,
    wait_for_vllm,
    write_create_only,
    write_package,
)
from im.policy.vllm_semantic import LocalVLLMConfig, LocalVLLMSemanticPolicy
from im.training.phase3_data import load_pinned_tokenizer


def _digest(path: Path) -> str:
    return f"sha256:{_hex_file(path)}"


def _hex_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, value: object) -> None:
    write_create_only(path, canonical_artifact_bytes(value))


def _write_sha256sums(output: Path) -> None:
    lines = []
    for path in sorted(output.rglob("*")):
        if path.is_file() and path.name != "SHA256SUMS":
            lines.append(f"{_hex_file(path)}  {path.relative_to(output)}\n")
    write_create_only(output / "SHA256SUMS", "".join(lines).encode())


def _run_commands(
    commands,
    *,
    raw_directory: Path,
    attempted_mutations: list[str] | None = None,
    receipts: list[dict[str, object]] | None = None,
) -> list[dict[str, object]]:
    recorded = [] if receipts is None else receipts
    raw_directory.mkdir(parents=True, exist_ok=True)
    for command in commands:
        if command.mutating and attempted_mutations is not None:
            attempted_mutations.append(command.command_id)
        completed = default_runner(command.argv)
        write_create_only(raw_directory / f"{command.command_id}.stdout", completed.stdout.encode())
        write_create_only(raw_directory / f"{command.command_id}.stderr", completed.stderr.encode())
        execute_commands((command,), lambda _argv: completed, recorded)
    return recorded


async def _execute(root: Path, authorization: Path, output: Path) -> None:
    package = root / PACKAGE_RELATIVE
    load_authorization(root, package, authorization)
    if output.exists():
        raise Phase6GateError("execution output already exists")
    claim_authorization(root, package, authorization, output)
    output.mkdir(parents=True, mode=0o700)
    status: dict[str, object] = {
        "format_version": "phase5-6-gate-status-v14",
        "status": "authorized_preflight",
    }
    _write_json(
        output / "authorization-receipt.json",
        {
            "authorization_sha256": _digest(authorization),
            "package_sha256s_sha256": _digest(package / "SHA256SUMS"),
        },
    )
    launch_receipts: list[dict[str, object]] = []
    evidence_receipts: list[dict[str, object]] = []
    teardown_receipts: list[dict[str, object]] = []
    absence_receipts: list[dict[str, object]] = []
    tunnel: subprocess.Popen[bytes] | None = None
    tunnel_stdout = tunnel_stderr = None
    attempted_mutations: list[str] = []
    try:
        adapter = await asyncio.to_thread(reuse_v5_step63_adapter, root, output)
        await asyncio.to_thread(
            _run_commands,
            launch_commands(datetime.now(UTC), str(adapter)),
            raw_directory=output / "cloud-launch-raw",
            attempted_mutations=attempted_mutations,
            receipts=launch_receipts,
        )
        tunnel_stdout = (output / "iap-tunnel.stdout").open("xb")
        tunnel_stderr = (output / "iap-tunnel.stderr").open("xb")
        tunnel = subprocess.Popen(tunnel_command().argv, stdout=tunnel_stdout, stderr=tunnel_stderr)
        health = await wait_for_vllm()
        _write_json(output / "vllm-health-receipt.json", health)
        tokenizer = load_pinned_tokenizer(
            root, root / ".cache/replay-sources/995ad96eacd98c81ed38be0c5b274b04031597b0"
        ).tokenizer
        await qualify_frozen_variants(
            policy_factory=lambda _variant: LocalVLLMSemanticPolicy(
                LocalVLLMConfig(adapter_model="phase3x-step63", base_model="phase3x-base"),
                tokenizer,
            ),
            output=output / "qualification",
        )
        await asyncio.to_thread(
            _run_commands,
            evidence_commands(),
            raw_directory=output / "cloud-evidence-raw",
            receipts=evidence_receipts,
        )
        status["status"] = "qualification_complete_teardown_pending"
    except BaseException as error:
        status.update({"error_type": type(error).__name__, "status": "failed_teardown_pending"})
        raise
    finally:
        if tunnel is not None:
            tunnel.terminate()
            try:
                tunnel.wait(timeout=10)
            except subprocess.TimeoutExpired:
                tunnel.kill()
                tunnel.wait(timeout=10)
        if tunnel_stdout is not None:
            tunnel_stdout.close()
        if tunnel_stderr is not None:
            tunnel_stderr.close()
        try:
            if attempted_mutations:
                await asyncio.to_thread(
                    _run_commands,
                    teardown_commands(),
                    raw_directory=output / "cloud-teardown-raw",
                    receipts=teardown_receipts,
                )
                await asyncio.to_thread(
                    _run_commands,
                    absence_commands(),
                    raw_directory=output / "cloud-absence-raw",
                    receipts=absence_receipts,
                )
                status["teardown_verified"] = True
                status["derived_absence"] = {
                    CONTAINER: "the owning VM is absent",
                    NAT: f"the owning router {ROUTER} is absent",
                }
            else:
                status["teardown_verified"] = "not_required_before_first_mutation"
            if status["status"] == "qualification_complete_teardown_pending":
                status["status"] = "complete"
        except BaseException as teardown_error:
            status.update(
                {
                    "status": "teardown_verification_failed",
                    "teardown_error_type": type(teardown_error).__name__,
                }
            )
            raise
        finally:
            _write_json(
                output / "command-receipts.json",
                {
                    "absence": absence_receipts,
                    "evidence": evidence_receipts,
                    "launch": launch_receipts,
                    "teardown": teardown_receipts,
                    "tunnel": {
                        "returncode": tunnel.returncode if tunnel is not None else None,
                        "stderr_sha256": _digest(output / "iap-tunnel.stderr")
                        if tunnel_stderr is not None
                        else None,
                        "stdout_sha256": _digest(output / "iap-tunnel.stdout")
                        if tunnel_stdout is not None
                        else None,
                    },
                },
            )
            _write_json(output / "status.json", status)
            _write_sha256sums(output)


def _teardown(root: Path, authorization: Path, output: Path) -> None:
    load_authorization(root, root / PACKAGE_RELATIVE, authorization)
    if output.resolve() != (root / TEARDOWN_OUTPUT_RELATIVE).resolve():
        raise Phase6GateError("teardown receipt path is not the frozen recovery path")
    if output.exists():
        raise Phase6GateError("teardown receipt output already exists")
    output.mkdir(parents=True, mode=0o700)
    receipts = _run_commands(teardown_commands(), raw_directory=output / "raw")
    absence = _run_commands(absence_commands(), raw_directory=output / "absence-raw")
    _write_json(
        output / "teardown-receipt.json",
        {
            "absence": absence,
            "commands": receipts,
            "derived_absence": {
                CONTAINER: "the owning VM is absent",
                NAT: f"the owning router {ROUTER} is absent",
            },
        },
    )
    _write_sha256sums(output)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "mode",
        choices=(
            "build-package",
            "dry-run",
            "execute",
            "teardown",
            "tinker-qualify",
            "verify",
        ),
    )
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--source-commit")
    parser.add_argument("--authorization", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    package = root / PACKAGE_RELATIVE
    if args.mode == "build-package":
        if not args.source_commit:
            parser.error("--source-commit is required")
        print(write_package(root, args.source_commit))
    elif args.mode == "dry-run":
        print((package / "cloud-command-plan-v14.json").read_text(encoding="utf-8"), end="")
    elif args.mode == "tinker-qualify":
        output = args.output or root / TINKER_QUALIFICATION_OUTPUT_RELATIVE
        print(json.dumps(asyncio.run(qualify_step63_with_tinker(root, output)), sort_keys=True))
    elif args.authorization is None:
        parser.error("--authorization is required")
    elif args.mode == "verify":
        load_authorization(root, package, args.authorization)
        print(json.dumps({"authorized": True, "network_calls": 0}, sort_keys=True))
    elif args.output is None:
        parser.error("--output is required")
    elif args.mode == "execute":
        asyncio.run(_execute(root, args.authorization, args.output))
    else:
        _teardown(root, args.authorization, args.output)


if __name__ == "__main__":
    main()
    (claim_authorization,)
