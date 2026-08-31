from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from im.assets.model import canonical_artifact_bytes
from im.training import phase3_full_tinker
from im.training import phase3_full_tinker_entrypoint as entrypoint
from im.training.phase3_full_run import LockedRunContract, Phase3FullRunError

ROOT = Path(__file__).parents[1]


def _contract() -> LockedRunContract:
    return SimpleNamespace(  # type: ignore[return-value]
        candidate_manifest_sha256="sha256:" + "a" * 64,
        candidate_sha256sums_sha256="sha256:" + "b" * 64,
        source_commit="c" * 40,
    )


def _packet(
    contract: LockedRunContract,
    root: Path,
    *,
    kind: str = entrypoint.EXECUTION_PACKET_KIND,
) -> dict[str, object]:
    expected_paths = entrypoint._artifact_paths_for(kind)
    bindings = {}
    for name in sorted(entrypoint.REQUIRED_ARTIFACT_BINDINGS):
        path = root / expected_paths[name]
        path.parent.mkdir(parents=True, exist_ok=True)
        raw = f"{name}\n".encode("ascii")
        path.write_bytes(raw)
        bindings[name] = {
            "path": expected_paths[name].as_posix(),
            "sha256": entrypoint._digest(raw),
        }
    return {
        "application_retries": 0,
        "candidate_manifest_sha256": contract.candidate_manifest_sha256,
        "candidate_sha256sums_sha256": contract.candidate_sha256sums_sha256,
        "derived_source_commit": contract.source_commit,
        "detached_execution_required": True,
        "artifact_bindings": bindings,
        "epoch_mode": entrypoint.INITIAL_EPOCH_MODE,
        "format_version": 1,
        "full_state_lifetime": {
            "durable_storage_allowed": True,
            "minimum_remaining_ttl_seconds": entrypoint.PAUSE_STATE_MINIMUM_TTL_SECONDS,
            "required_steps": [20, 40, 60, 63, 80, 100, 120, 126],
        },
        "human_review_safety_buffer_seconds": (entrypoint.HUMAN_REVIEW_SAFETY_BUFFER_SECONDS),
        "human_review_window_seconds": entrypoint.HUMAN_REVIEW_WINDOW_SECONDS,
        "kind": entrypoint.EXECUTION_PACKET_KIND,
        "launchd_label": entrypoint.LAUNCHD_LABEL,
        "maximum_spend_usd": entrypoint.INITIAL_EPOCH_CEILING_USD,
        "pause_amendment_zip_sha256": entrypoint.PAUSE_AMENDMENT_ZIP_SHA256,
        "output_directory": "review/phase3/wp3-4-test-output",
        "run_id": "wp3-4-test",
        "runner_source_commit": "d" * 40,
        "sealed_test_access": "forbidden",
    }


def _authorization(packet: entrypoint.ExecutionPacket) -> dict[str, object]:
    return {
        "application_retries": 0,
        "funding_override_path": "funding-override.json",
        "detached_execution_required": True,
        "epoch_mode": entrypoint.INITIAL_EPOCH_MODE,
        "execution_packet_sha256": packet.sha256,
        "full_state_minimum_remaining_ttl_seconds": (entrypoint.PAUSE_STATE_MINIMUM_TTL_SECONDS),
        "human_review_safety_buffer_seconds": (entrypoint.HUMAN_REVIEW_SAFETY_BUFFER_SECONDS),
        "human_review_window_seconds": entrypoint.HUMAN_REVIEW_WINDOW_SECONDS,
        "launchd_label": entrypoint.LAUNCHD_LABEL,
        "maximum_spend_usd": entrypoint.INITIAL_EPOCH_CEILING_USD,
        "one_locked_run": True,
        "funding_mode": "owner_monitored_live_top_up",
        "upfront_balance_confirmation_required": False,
        "owner_monitoring_required": True,
        "output_directory": packet.output_directory,
        "run_id": packet.run_id,
        "runner_source_commit": packet.source_commit,
        "sealed_test_access": "forbidden",
        "pause_amendment_zip_sha256": packet.pause_amendment_zip_sha256,
    }


def test_canonical_launch_path_rejects_absolute_sealed_path_without_resolving(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sealed = tmp_path / "review/phase2/wp2-9-d13-trust-completion/interaction-test/packet.json"
    resolved: list[Path] = []
    original = Path.resolve

    def tracked(path: Path, *args: object, **kwargs: object) -> Path:
        resolved.append(path)
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", tracked)
    with pytest.raises(entrypoint.Phase3FullTinkerError, match="non-canonical"):
        entrypoint._require_canonical_path(
            tmp_path, sealed, entrypoint.INITIAL_EXECUTION_PACKET_PATH, "packet"
        )
    assert sealed not in resolved


def test_canonical_launch_path_rejects_symlink_without_readlink(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sealed = tmp_path / "review/phase2/wp2-9-d13-trust-completion/interaction-test"
    link = tmp_path / "sealed-link"
    link.symlink_to(sealed, target_is_directory=True)
    readlinks: list[object] = []
    original = os.readlink

    def tracked(path: object, *args: object, **kwargs: object) -> str:
        readlinks.append(path)
        return original(path, *args, **kwargs)

    monkeypatch.setattr(os, "readlink", tracked)
    with pytest.raises(entrypoint.Phase3FullTinkerError, match="non-canonical"):
        entrypoint._require_canonical_path(
            tmp_path, link / "packet.json", entrypoint.INITIAL_EXECUTION_PACKET_PATH, "packet"
        )
    assert not readlinks


def _lineage_bindings(
    kind: str = entrypoint.EXECUTION_PACKET_KIND,
) -> dict[str, dict[str, str]]:
    expected_paths = entrypoint._artifact_paths_for(kind)
    return {
        name: {
            "path": expected_paths[name].as_posix(),
            "sha256": "sha256:" + "f" * 64,
        }
        for name in entrypoint.REQUIRED_ARTIFACT_BINDINGS
    }


def _lineage_changed(
    root: Path, packet: entrypoint.ExecutionPacket, authorization: Path, balance: Path
) -> str:
    names = [
        packet.path.relative_to(root).as_posix(),
        authorization.relative_to(root).as_posix(),
        balance.relative_to(root).as_posix(),
    ]
    names.extend(
        packet.artifact_bindings[name]["path"]
        for name in sorted(entrypoint.POST_SOURCE_ARTIFACT_BINDINGS)
    )
    return "\n".join(names) + "\n"


def test_execution_packet_binds_exact_candidate_and_runner_source(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        entrypoint,
        "PAUSE_AMENDMENT_SHA256",
        entrypoint._digest(b"pause_amendment\n"),
    )
    contract = _contract()
    packet = _packet(contract, tmp_path)
    path = tmp_path / "packet.json"
    raw = canonical_artifact_bytes(packet)
    path.write_bytes(raw)
    loaded = entrypoint.load_execution_packet(tmp_path, path, contract)
    assert loaded.sha256 == entrypoint._digest(raw)

    packet["human_review_window_seconds"] = 1
    path.write_bytes(canonical_artifact_bytes(packet))
    with pytest.raises(entrypoint.Phase3FullTinkerError, match="execution packet"):
        entrypoint.load_execution_packet(tmp_path, path, contract)


def test_invalid_initial_preflight_cannot_read_secret_or_create_provider(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    contract = _contract()
    calls = {"secret": 0, "service": 0}
    monkeypatch.setattr(entrypoint, "load_locked_run_contract", lambda *_: contract)
    monkeypatch.setattr(
        entrypoint,
        "load_execution_packet",
        lambda *_: entrypoint.ExecutionPacket(
            path=tmp_path / "packet.json",
            sha256="sha256:" + "e" * 64,
            source_commit="d" * 40,
            run_id="wp3-4-test",
            output_directory="review/phase3/wp3-4-test-output",
        ),
    )
    monkeypatch.setattr(
        entrypoint,
        "load_checksum_bound_authorization",
        lambda *_: SimpleNamespace(payload={"funding_override_path": "funding-override.json"}),
    )

    def secret(_: Path) -> str:
        calls["secret"] += 1
        return "must-not-be-read"

    def service(**_: object) -> object:
        calls["service"] += 1
        raise AssertionError("must not create provider")

    with pytest.raises(entrypoint.Phase3FullTinkerError, match="authorization"):
        asyncio.run(
            entrypoint.execute_tinker_locked_run(
                repository_root=ROOT,
                candidate_directory=Path("review/phase3/wp3-4-derived-run-candidate-v2"),
                execution_packet_path=entrypoint.INITIAL_EXECUTION_PACKET_PATH,
                authorization_path=entrypoint.INITIAL_AUTHORIZATION_PATH,
                tokenizer=SimpleNamespace(),  # type: ignore[arg-type]
                output_directory=Path("review/phase3/wp3-4-test-output"),
                run_id="wp3-4-test",
                service_factory=service,  # type: ignore[arg-type]
                secret_reader=secret,
            )
        )
    assert calls == {"secret": 0, "service": 0}


def test_valid_initial_wiring_reaches_core_without_secret_or_provider_work(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    contract = _contract()
    packet = entrypoint.ExecutionPacket(
        path=tmp_path / "packet.json",
        sha256="sha256:" + "e" * 64,
        source_commit="d" * 40,
        run_id="wp3-4-test",
        output_directory="review/phase3/wp3-4-test-output",
    )
    calls = {"secret": 0, "service": 0}

    def preflight(**kwargs: object) -> tuple[Path, LockedRunContract, object, Path]:
        return ROOT, contract, packet, Path(packet.output_directory)

    monkeypatch.setattr(
        entrypoint,
        "_preflight_tinker_launch",
        preflight,
    )

    async def core(**kwargs: object) -> dict[str, object]:
        assert kwargs["contract"] is contract
        assert kwargs["final_execution_source_commit"] == packet.source_commit
        assert kwargs["human_review_window_seconds"] == 604800
        assert kwargs["safety_buffer_seconds"] == 86400
        return {"status": "wired"}

    monkeypatch.setattr(entrypoint, "execute_locked_run", core)

    def secret(_: Path) -> str:
        calls["secret"] += 1
        return "must-not-be-read"

    def service(**_: object) -> object:
        calls["service"] += 1
        raise AssertionError("must not create provider")

    result = asyncio.run(
        entrypoint.execute_tinker_locked_run(
            repository_root=ROOT,
            candidate_directory=Path("unused"),
            execution_packet_path=Path("unused"),
            authorization_path=Path("unused"),
            tokenizer=SimpleNamespace(),  # type: ignore[arg-type]
            output_directory=Path(packet.output_directory),
            run_id=packet.run_id,
            service_factory=service,  # type: ignore[arg-type]
            secret_reader=secret,
        )
    )
    assert result == {"status": "wired"}
    assert calls == {"secret": 0, "service": 0}


def test_resume_core_gate_cannot_read_secret_or_create_provider(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    contract = _contract()
    packet = entrypoint.ExecutionPacket(
        path=tmp_path / "packet.json",
        sha256="sha256:" + "e" * 64,
        source_commit="d" * 40,
        run_id="wp3-4-test",
        output_directory="review/phase3/wp3-4-test-output",
    )
    calls = {"secret": 0, "service": 0}

    def preflight(**kwargs: object) -> tuple[Path, LockedRunContract, object, Path]:
        return ROOT, contract, packet, Path(packet.output_directory)

    monkeypatch.setattr(
        entrypoint,
        "_preflight_tinker_resume",
        preflight,
    )

    async def rejected(**kwargs: object) -> dict[str, object]:
        assert kwargs["human_review_window_seconds"] == 604800
        assert kwargs["safety_buffer_seconds"] == 86400
        raise Phase3FullRunError("D12 or control evidence rejected")

    monkeypatch.setattr(entrypoint, "resume_conditional_epoch_three", rejected)

    def secret(_: Path) -> str:
        calls["secret"] += 1
        return "must-not-be-read"

    def service(**_: object) -> object:
        calls["service"] += 1
        raise AssertionError("must not create provider")

    with pytest.raises(Phase3FullRunError, match="D12"):
        asyncio.run(
            entrypoint.resume_tinker_conditional_epoch_three(
                repository_root=ROOT,
                candidate_directory=Path("unused"),
                execution_packet_path=Path("unused"),
                authorization_path=Path("unused"),
                tokenizer=SimpleNamespace(),  # type: ignore[arg-type]
                output_directory=Path(packet.output_directory),
                run_id=packet.run_id,
                service_factory=service,  # type: ignore[arg-type]
                secret_reader=secret,
            )
        )
    assert calls == {"secret": 0, "service": 0}


def test_provider_checkpoint_metadata_uses_pinned_list_api(monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime.now(UTC)
    checkpoint = SimpleNamespace(
        expires_at=now + timedelta(hours=1),
        time=now - timedelta(seconds=2),
        tinker_path="tinker://run-one/weights/step-126",
    )

    class Rest:
        async def list_checkpoints_async(self, run_id: str) -> SimpleNamespace:
            assert run_id == "run-one"
            return SimpleNamespace(checkpoints=[checkpoint])

    provider = object.__new__(phase3_full_tinker.TinkerRunProvider)
    provider._rest = Rest()  # type: ignore[attr-defined]
    monkeypatch.setattr(phase3_full_tinker.time, "time", lambda: now.timestamp())
    metadata = asyncio.run(provider.checkpoint_metadata(checkpoint.tinker_path))
    assert metadata == {
        "checkpoint_created_at": int(checkpoint.time.timestamp()),
        "checkpoint_expires_at": int(checkpoint.expires_at.timestamp()),
        "checkpoint_is_durable": False,
        "remaining_ttl_seconds": 3600,
    }


def test_authorization_binds_packet_run_and_lexical_output_without_statting_test_path() -> None:
    packet = entrypoint.ExecutionPacket(
        path=ROOT / "review/phase3/wp3-4-derived-run-candidate-v2/derived-run-manifest.json",
        sha256="sha256:" + "a" * 64,
        source_commit="b" * 40,
        run_id="wp3-4-test",
        output_directory="review/phase3/wp3-4-test-output",
    )
    output = entrypoint._lexical_output_relative(ROOT, Path("review/phase3/wp3-4-test-output"))
    authorization = _authorization(packet)
    entrypoint._verify_authorization_binding(authorization, packet, "wp3-4-test", output)
    authorization["run_id"] = "other"
    with pytest.raises(entrypoint.Phase3FullTinkerError, match="authorization"):
        entrypoint._verify_authorization_binding(authorization, packet, "wp3-4-test", output)
    with pytest.raises(entrypoint.Phase3FullTinkerError, match="sealed"):
        entrypoint._lexical_output_relative(
            ROOT, Path("review/phase2/wp2-10-test-closeout/will-not-stat")
        )


def test_launchd_identity_requires_the_live_agent_process(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(entrypoint.sys, "platform", "darwin")
    monkeypatch.setattr(entrypoint.os, "getppid", lambda: 1)
    monkeypatch.setattr(entrypoint.os, "getpid", lambda: 123)
    monkeypatch.setenv("PHASE3_LAUNCHD_LABEL", entrypoint.LAUNCHD_LABEL)
    monkeypatch.setattr(
        entrypoint.subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess([], 0, "pid = 123\n", ""),
    )
    entrypoint.verify_launchd_execution()

    monkeypatch.setattr(entrypoint.os, "getppid", lambda: 2)
    with pytest.raises(entrypoint.Phase3FullTinkerError, match="detached launchd"):
        entrypoint.verify_launchd_execution()


@pytest.mark.parametrize("output_exists", [True, False])
def test_post_exit_launch_logs_are_checksum_bound_for_run_or_early_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, output_exists: bool
) -> None:
    root = tmp_path / "repository"
    root.mkdir()
    (root / "review/phase3").mkdir(parents=True)
    logs = tmp_path / "external-logs"
    logs.mkdir()
    stdout, stderr = logs / "stdout.log", logs / "stderr.log"
    stdout.write_bytes(b"detached stdout\n")
    stderr.write_bytes(b"detached stderr\n")
    output = Path("review/phase3/wp3-4-test-output")
    if output_exists:
        (root / output).mkdir()
    monkeypatch.setattr(
        entrypoint.subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess([], 0, "state = exited\n", ""),
    )
    result = entrypoint.capture_detached_launch_logs(
        repository_root=root,
        output_directory=output,
        stdout_path=stdout,
        stderr_path=stderr,
        run_id="wp3-4-test",
    )
    directory = root / str(result["evidence_directory"])
    assert (directory / "stdout.log").read_bytes() == b"detached stdout\n"
    assert (directory / "stderr.log").read_bytes() == b"detached stderr\n"
    entries = {
        name: digest
        for digest, name in (
            line.split("  ", 1)
            for line in (directory / "SHA256SUMS").read_text(encoding="ascii").splitlines()
        )
    }
    assert set(entries) == {"launch-log-manifest.json", "stderr.log", "stdout.log"}
    for name, expected in entries.items():
        assert entrypoint._digest((directory / name).read_bytes()) == f"sha256:{expected}"
    expected_disposition = "run_output" if output_exists else "early_failure_evidence"
    assert result["capture_disposition"] == expected_disposition


def test_launch_logs_cannot_be_captured_while_agent_is_running(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        entrypoint.subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess([], 0, "pid = 123\n", ""),
    )
    with pytest.raises(entrypoint.Phase3FullTinkerError, match="only after"):
        entrypoint.capture_detached_launch_logs(
            repository_root=tmp_path,
            output_directory=Path("review/phase3/wp3-4-test-output"),
            stdout_path=tmp_path / "missing-stdout",
            stderr_path=tmp_path / "missing-stderr",
            run_id="wp3-4-test",
        )


def test_runner_lineage_allows_only_packet_authorization_and_balance_sidecars(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    packet_path = tmp_path / "packet.json"
    authorization = tmp_path / "authorization.json"
    balance = tmp_path / "balance.json"
    for path in (packet_path, authorization, balance):
        path.write_text("{}", encoding="utf-8")
    packet = entrypoint.ExecutionPacket(
        path=packet_path,
        sha256="sha256:" + "0" * 64,
        source_commit="a" * 40,
        run_id="wp3-4-test",
        output_directory="review/phase3/wp3-4-test-output",
        artifact_bindings=_lineage_bindings(),
    )
    outputs = [
        subprocess.CompletedProcess([], 0, "", ""),
        subprocess.CompletedProcess([], 0, "", ""),
        subprocess.CompletedProcess(
            [], 0, _lineage_changed(tmp_path, packet, authorization, balance), ""
        ),
        subprocess.CompletedProcess([], 0, "b" * 40 + "\n", ""),
    ]
    monkeypatch.setattr(
        entrypoint.subprocess,
        "run",
        lambda *_args, **_kwargs: outputs.pop(0),
    )
    assert entrypoint.verify_execution_lineage(tmp_path, packet, authorization, balance) == "b" * 40


def test_only_resume_may_have_exact_prior_output_as_untracked_worktree() -> None:
    output = Path("review/phase3/wp3-4-sft-20260803-v1")
    status = f"?? {output}/status.json\n?? {output}/evidence/0001.json"
    assert entrypoint._allowed_worktree_status(status, output) is True
    assert entrypoint._allowed_worktree_status(status, None) is False
    assert entrypoint._allowed_worktree_status("", output) is False
    assert (
        entrypoint._allowed_worktree_status(status + "\n?? review/phase3/unrelated.json", output)
        is False
    )
    assert entrypoint._allowed_worktree_status(f" M {output}/status.json", output) is False


def test_resume_lineage_rejects_missing_output_before_git(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    packet_path = tmp_path / "packet.json"
    authorization = tmp_path / "authorization.json"
    balance = tmp_path / "balance.json"
    for path in (packet_path, authorization, balance):
        path.write_text("{}", encoding="utf-8")
    packet = entrypoint.ExecutionPacket(
        path=packet_path,
        sha256="sha256:" + "0" * 64,
        source_commit="a" * 40,
        run_id="wp3-4-test",
        output_directory="review/phase3/wp3-4-test-output",
        artifact_bindings=_lineage_bindings(),
    )
    monkeypatch.setattr(
        entrypoint.subprocess,
        "run",
        lambda *_args, **_kwargs: pytest.fail("missing resume output must fail before git"),
    )
    with pytest.raises(entrypoint.Phase3FullTinkerError, match="resume output directory"):
        entrypoint.verify_execution_lineage(
            tmp_path,
            packet,
            authorization,
            balance,
            resume_output_relative=Path(packet.output_directory),
        )


def test_resume_lineage_rejects_sealed_route_before_stat_or_git(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    packet_path = tmp_path / "packet.json"
    authorization = tmp_path / "authorization.json"
    balance = tmp_path / "balance.json"
    for path in (packet_path, authorization, balance):
        path.write_text("{}", encoding="utf-8")
    packet = entrypoint.ExecutionPacket(
        path=packet_path,
        sha256="sha256:" + "0" * 64,
        source_commit="a" * 40,
        run_id="wp3-4-test",
        output_directory="review/phase3/wp3-4-test-output",
        artifact_bindings=_lineage_bindings(),
    )

    def sealed_guard(root: Path, path: Path) -> Path:
        assert path == root / packet.output_directory
        raise entrypoint.Phase3FullTinkerError("sealed output route")

    monkeypatch.setattr(entrypoint, "guard_read_path", sealed_guard)
    monkeypatch.setattr(
        entrypoint.subprocess,
        "run",
        lambda *_args, **_kwargs: pytest.fail("sealed resume output must fail before git"),
    )
    monkeypatch.setattr(Path, "is_dir", lambda _: pytest.fail("must not stat sealed output"))
    with pytest.raises(entrypoint.Phase3FullTinkerError, match="sealed output route"):
        entrypoint.verify_execution_lineage(
            tmp_path,
            packet,
            authorization,
            balance,
            resume_output_relative=Path(packet.output_directory),
        )


def test_resume_lineage_rejects_mixed_tracked_and_untracked_output(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    packet_path = tmp_path / "packet.json"
    authorization = tmp_path / "authorization.json"
    balance = tmp_path / "balance.json"
    for path in (packet_path, authorization, balance):
        path.write_text("{}", encoding="utf-8")
    packet = entrypoint.ExecutionPacket(
        path=packet_path,
        sha256="sha256:" + "0" * 64,
        source_commit="a" * 40,
        run_id="wp3-4-test",
        output_directory="review/phase3/wp3-4-test-output",
        artifact_bindings=_lineage_bindings(),
    )
    output = tmp_path / packet.output_directory
    output.mkdir(parents=True)
    outputs = [
        subprocess.CompletedProcess([], 0, "", ""),
        subprocess.CompletedProcess([], 0, f"?? {packet.output_directory}/status.json\n", ""),
        subprocess.CompletedProcess([], 0, f"{packet.output_directory}/status.json\n", ""),
        subprocess.CompletedProcess(
            [], 0, _lineage_changed(tmp_path, packet, authorization, balance), ""
        ),
        subprocess.CompletedProcess([], 0, "b" * 40 + "\n", ""),
    ]
    monkeypatch.setattr(
        entrypoint.subprocess,
        "run",
        lambda *_args, **_kwargs: outputs.pop(0),
    )
    with pytest.raises(entrypoint.Phase3FullTinkerError, match="unauthorized"):
        entrypoint.verify_execution_lineage(
            tmp_path,
            packet,
            authorization,
            balance,
            resume_output_relative=Path(packet.output_directory),
        )


def test_resume_lineage_rejects_child_symlink_before_git(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    packet_path = tmp_path / "packet.json"
    authorization = tmp_path / "authorization.json"
    balance = tmp_path / "balance.json"
    for path in (packet_path, authorization, balance):
        path.write_text("{}", encoding="utf-8")
    packet = entrypoint.ExecutionPacket(
        path=packet_path,
        sha256="sha256:" + "0" * 64,
        source_commit="a" * 40,
        run_id="wp3-4-test",
        output_directory="review/phase3/wp3-4-test-output",
        artifact_bindings=_lineage_bindings(),
    )
    output = tmp_path / packet.output_directory
    output.mkdir(parents=True)
    synthetic_target = tmp_path / "synthetic-target"
    synthetic_target.mkdir()
    (output / "evidence").symlink_to(synthetic_target, target_is_directory=True)
    monkeypatch.setattr(
        entrypoint.subprocess,
        "run",
        lambda *_args, **_kwargs: pytest.fail("child symlink must fail before git"),
    )
    with pytest.raises(entrypoint.Phase3FullTinkerError, match="unsafe symlink"):
        entrypoint.verify_execution_lineage(
            tmp_path,
            packet,
            authorization,
            balance,
            resume_output_relative=Path(packet.output_directory),
        )


def test_resume_lineage_returns_verified_head(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    packet_path = tmp_path / "packet.json"
    authorization = tmp_path / "authorization.json"
    balance = tmp_path / "balance.json"
    for path in (packet_path, authorization, balance):
        path.write_text("{}", encoding="utf-8")
    packet = entrypoint.ExecutionPacket(
        path=packet_path,
        sha256="sha256:" + "0" * 64,
        source_commit="a" * 40,
        run_id="wp3-4-test",
        output_directory="review/phase3/wp3-4-test-output",
        artifact_bindings=_lineage_bindings(),
    )
    output = tmp_path / packet.output_directory
    output.mkdir(parents=True)
    (output / "status.json").write_text("{}", encoding="utf-8")
    head = "b" * 40
    outputs = [
        subprocess.CompletedProcess([], 0, "", ""),
        subprocess.CompletedProcess([], 0, f"?? {packet.output_directory}/status.json\n", ""),
        subprocess.CompletedProcess([], 0, "", ""),
        subprocess.CompletedProcess(
            [], 0, _lineage_changed(tmp_path, packet, authorization, balance), ""
        ),
        subprocess.CompletedProcess([], 0, head + "\n", ""),
    ]
    monkeypatch.setattr(
        entrypoint.subprocess,
        "run",
        lambda *_args, **_kwargs: outputs.pop(0),
    )
    assert (
        entrypoint.verify_execution_lineage(
            tmp_path,
            packet,
            authorization,
            balance,
            resume_output_relative=Path(packet.output_directory),
        )
        == head
    )


def test_sampling_inventory_and_exact_fast_retention_membership_are_closed() -> None:
    rows = phase3_full_tinker._load_sampling_requests(ROOT)
    by_id = {str(row["request_id"]): row for row in rows}
    dev = [str(row["request_id"]) for row in rows[:300]]
    retention = [str(row["request_id"]) for row in rows[300:]]
    assert len(dev) == 300
    assert len(retention) == 60
    assert len(phase3_full_tinker._exact_rows(by_id, dev, "full DEV")) == 300
    assert len(phase3_full_tinker._exact_rows(by_id, retention[:12], "retention")) == 12
    with pytest.raises(phase3_full_tinker.Phase3FullTinkerError, match="repeat"):
        phase3_full_tinker._exact_rows(by_id, (dev[0], dev[0]), "fast DEV")


def test_approved_fast_and_automatic_retention_identities_are_exact() -> None:
    fast = phase3_full_tinker._load_fast_sentinel_ids(ROOT)
    automatic = phase3_full_tinker._load_automatic_retention_rows(ROOT)
    assert len(fast) == 11
    assert len(set(fast)) == 11
    assert fast[0] == "dev:017810fc0e54016a1a28ae1b57d7900bce834645d3b5f32fd58ea1ed4b386eb4:4"
    assert len(automatic) == 12
    assert len({row["request_id"] for row in automatic}) == 12
    assert automatic[0]["request_id"] == (
        "retention:85b810a2c52be481e2f79b741fb8a02142c18d9db329189689789240bad537a6"
    )


def test_fast_evidence_is_derived_from_exact_full_dev_records_without_sampling() -> None:
    fast_ids = phase3_full_tinker._load_fast_sentinel_ids(ROOT)
    persisted = {
        state_id: SimpleNamespace(sha256=f"sha256:{index:064x}")
        for index, state_id in enumerate(fast_ids, start=1)
    }
    grades = [
        {
            "executed": {"hard_failures": [], "match": True},
            "framing": {"terminal_projection_status": "projected"},
            "state_id": state_id,
            "structural": {"parse_union_valid": True},
        }
        for state_id in fast_ids
    ]

    evidence = phase3_full_tinker._derive_fast_evidence(
        fast_ids,
        persisted,
        grades,
        derived_from="full_dev_same_300_raw_outputs",
        additional_physical_request_count=0,
    )

    assert evidence["fast_state_ids"] == list(fast_ids)
    assert evidence["request_count"] == 11
    assert evidence["additional_physical_request_count"] == 0
    assert len(evidence["mechanics_diagnostics"]) == 11


def test_full_dev_persists_fast_evidence_from_its_same_300_samples(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    evaluator = phase3_full_tinker.TinkerEvaluator(
        ROOT,
        tmp_path,
        SimpleNamespace(tokenizer=_Tokenizer()),  # type: ignore[arg-type]
        _contract(),
        "wp3-4-test",
        SimpleNamespace(),  # type: ignore[arg-type]
    )
    dev_rows = tuple(row for row in evaluator._requests if row["kind"] == "interaction_dev")
    states = tuple(
        SimpleNamespace(
            messages=(),
            state_id=str(row["request_id"]),
            visible_prefix_sha256="sha256:" + "0" * 64,
        )
        for row in dev_rows
    )
    persisted = {
        state.state_id: SimpleNamespace(path=ROOT / "AGENTS.md", sha256=f"sha256:{index:064x}")
        for index, state in enumerate(states, start=1)
    }
    sample_calls: list[tuple[str, int]] = []

    async def rebuild(_: Path, _tokenizer: object) -> tuple[SimpleNamespace, ...]:
        return states

    async def sample_rows(
        _self: object,
        _client: object,
        _step: int,
        _sampler: str,
        name: str,
        rows: tuple[object, ...],
    ) -> dict[str, SimpleNamespace]:
        sample_calls.append((name, len(rows)))
        return persisted

    def grade(_: Path, state: SimpleNamespace, __: object, **___: object) -> dict[str, object]:
        return {
            "executed": {"hard_failures": [], "match": True},
            "framing": {"terminal_projection_status": "projected"},
            "state_id": state.state_id,
            "structural": {"parse_union_valid": True},
        }

    monkeypatch.setattr(phase3_full_tinker, "rebuild_dev_states", rebuild)
    monkeypatch.setattr(phase3_full_tinker.TinkerEvaluator, "_sample_rows", sample_rows)
    monkeypatch.setattr(phase3_full_tinker, "grade_persisted_generation", grade)
    monkeypatch.setattr(phase3_full_tinker, "compute_dev_metrics", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(phase3_full_tinker, "build_open_text_rubrics", lambda _: ())

    evidence = asyncio.run(evaluator._full_dev(object(), 20, "sampler://one"))
    assert sample_calls == [("full-dev", 300)]
    assert evidence["evaluation_status"] == "pending_human_review"
    assert evidence["fast_dev_derived_sha256"].startswith("sha256:")
    artifact = tmp_path / "evaluations" / "step-020" / "full-dev" / "fast-dev-derived.json"
    assert artifact.exists()
    assert "fast-dev-derived.json" in (artifact.parent / "SHA256SUMS").read_text(encoding="ascii")


def _automatic_row(name: str) -> dict[str, object]:
    return next(
        dict(row)
        for row in phase3_full_tinker._load_automatic_retention_rows(ROOT)
        if row["row_rule"]["name"] == name
    )


def test_counter_validator_proves_the_exact_mapping_by_ast_without_executing_code(
    tmp_path: Path,
) -> None:
    marker = tmp_path / "must-not-exist"
    valid = f"""from collections import Counter
x = [3, 5, 3, 3, 5, 1]
open({str(marker)!r}, "w").write("never execute")
for value, count in Counter(x).items():
    print(f"{{value}}: {{count}}")
"""
    row = _automatic_row("python_counter_example_ast_v1")

    passed = phase3_full_tinker._retention_validator(row, valid)
    reordered = phase3_full_tinker._retention_validator(
        row,
        valid.replace("[3, 5, 3, 3, 5, 1]", "[5, 3, 1, 5, 3, 3]"),
    )
    failed = phase3_full_tinker._retention_validator(
        row,
        valid.replace("[3, 5, 3, 3, 5, 1]", "[3, 5, 3, 3, 5, 5]"),
    )
    disconnected = phase3_full_tinker._retention_validator(
        row,
        """from collections import Counter
x = [3, 5, 3, 3, 5, 1]
counts = Counter(x)
counts.items()
print("wrong")
""",
    )

    assert passed["status"] == "pass"
    assert passed["expected_mapping"] == {"1": 1, "3": 3, "5": 2}
    assert reordered["status"] == "pass"
    assert failed["status"] == "fail"
    assert disconnected["status"] == "fail"
    assert not marker.exists()


def test_portrait_validator_requires_exact_unordered_set_with_no_extra_people() -> None:
    row = _automatic_row("portrait_people_ages_exact_set_v1")
    valid = "Prince George (9), King Charles III (74), Prince William (40)"
    invalid = valid + "\nPrincess Charlotte (8)"

    assert phase3_full_tinker._retention_validator(row, valid)["status"] == "pass"
    assert phase3_full_tinker._retention_validator(row, invalid)["status"] == "fail"


def test_summary_validator_leaves_grounding_for_human_review_and_rejects_bad_shape() -> None:
    row = _automatic_row("source_summary_one_or_two_paragraphs_v1")
    unrelated = phase3_full_tinker._retention_validator(row, "Completely unrelated text.")
    malformed = phase3_full_tinker._retention_validator(row, "One.\n\nTwo.\n\nThree.")

    assert unrelated["status"] == "not_applicable"
    assert unrelated["semantic_status"] == "pending_human_review"
    assert "source_grounded_dst_summary" in unrelated["pending_semantic_requirements"]
    assert malformed["status"] == "fail"


def test_classification_validator_allows_rationale_but_requires_exact_first_label() -> None:
    row = _automatic_row("fundraising_email_classification_v1")
    dash_rationale = "Advertisement — It solicits donations from readers."
    colon_rationale = "Advertisement: It solicits donations from readers."
    period_rationale = "Advertisement. It solicits donations from readers."
    invalid = "Not advertisement. It solicits donations from readers."

    assert phase3_full_tinker._retention_validator(row, dash_rationale)["status"] == "pass"
    assert phase3_full_tinker._retention_validator(row, colon_rationale)["status"] == "pass"
    assert phase3_full_tinker._retention_validator(row, period_rationale)["status"] == "pass"
    assert phase3_full_tinker._retention_validator(row, invalid)["status"] == "fail"


def test_retention_framing_failure_and_over_concision_are_explicit_high_confidence_failures(
    tmp_path: Path,
) -> None:
    raw = {
        "decoded_utf8": "tiny",
        "finish_reason": "length",
        "hidden_thinking": False,
        "output_token_count": 1,
        "output_token_ids": [1],
    }
    path = tmp_path / "raw.json"
    path.write_bytes(canonical_artifact_bytes(raw))
    row = phase3_full_tinker._load_automatic_retention_rows(ROOT)[0]
    finding = phase3_full_tinker._retention_findings(
        row,
        SimpleNamespace(path=path, sha256="sha256:" + "f" * 64),
        SimpleNamespace(tokenizer=_Tokenizer()),  # type: ignore[arg-type]
    )
    assert finding["checks"]["new_length_termination"] is True
    assert finding["catastrophe_detector"]["new_length_termination"] is True
    assert finding["checks"]["terminal_framing_failure"] is True
    assert finding["high_confidence_failure"] is True


def test_retention_detector_treats_whitespace_as_empty(tmp_path: Path) -> None:
    raw = {
        "decoded_utf8": " \n\t",
        "finish_reason": "length",
        "hidden_thinking": False,
        "output_token_count": 1,
        "output_token_ids": [1],
    }
    path = tmp_path / "raw.json"
    path.write_bytes(canonical_artifact_bytes(raw))
    finding = phase3_full_tinker._retention_findings(
        phase3_full_tinker._load_automatic_retention_rows(ROOT)[0],
        SimpleNamespace(path=path, sha256="sha256:" + "f" * 64),
        SimpleNamespace(tokenizer=_Tokenizer()),  # type: ignore[arg-type]
    )
    assert finding["catastrophe_detector"]["empty_output"] is True


def test_automatic_retention_uses_aggregate_threshold_not_any_row(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    evaluator = phase3_full_tinker.TinkerEvaluator(
        ROOT,
        tmp_path,
        SimpleNamespace(tokenizer=_Tokenizer()),  # type: ignore[arg-type]
        _contract(),
        "wp3r-test",
        SimpleNamespace(),  # type: ignore[arg-type]
    )

    async def sample_rows(*_: object) -> dict[str, object]:
        return {
            str(row["request_id"]): SimpleNamespace(sha256="sha256:" + "a" * 64)
            for row in evaluator._automatic_rows
        }

    first_id = str(evaluator._automatic_rows[0]["request_id"])

    def finding(row: dict[str, object], *_: object) -> dict[str, object]:
        failed = str(row["request_id"]) == first_id
        return {
            "catastrophe_detector": {
                "empty_output": False,
                "high_confidence_refusal": False,
                "interaction_protocol_imitation": False,
                "new_length_termination": failed,
                "repetition_signature": None,
            },
            "checks": {"new_length_termination": failed},
            "high_confidence_failure": failed,
            "request_id": row["request_id"],
        }

    monkeypatch.setattr(phase3_full_tinker.TinkerEvaluator, "_sample_rows", sample_rows)
    monkeypatch.setattr(phase3_full_tinker, "_retention_findings", finding)
    result = asyncio.run(
        evaluator._automatic_retention(
            object(),
            10,
            "sampler://one",
            evaluator._automatic_rows,  # type: ignore[arg-type]
        )
    )
    assert result["automatic_guard_passed"] is True


def test_open_text_packet_matches_pending_v4_shape() -> None:
    state_id = "dev:example:1"
    grade = {
        "expected_action_type": "respond",
        "framing": {"terminal_projection_status": "failed"},
        "predicted_action": {"type": "respond"},
        "raw": {
            "decoded_utf8": "{}",
            "finish_reason": "length",
            "output_bytes_sha256": "sha256:" + "1" * 64,
            "output_token_ids": [1],
        },
        "state_id": state_id,
        "structural": {"structural_pass": False},
    }
    expected = SimpleNamespace(model_dump=lambda **_: {"type": "respond", "text": "answer"})
    state = SimpleNamespace(state_id=state_id, expected=expected)
    rubric = SimpleNamespace(
        action_type="respond",
        state_id=state_id,
        as_json_object=lambda: {"state_id": state_id, "rubric_sha256": "sha256:" + "2" * 64},
    )
    packet = phase3_full_tinker._open_text_packet(
        [grade],
        [state],
        [rubric],
        {state_id: SimpleNamespace(sha256="sha256:" + "3" * 64)},
        SimpleNamespace(tokenizer=_Tokenizer()),  # type: ignore[arg-type]
    )
    assert packet["counts"] == {
        "integrate": 0,
        "not_applicable_structural_failure": 1,
        "pending_human_review": 0,
        "respond": 1,
        "total": 1,
    }
    assert set(packet["rows"][0]) == {
        "expected_action",
        "framing",
        "human_assessment",
        "parser_input_utf8",
        "predicted_action",
        "raw_output_sha256",
        "rubric",
        "state_id",
        "structural",
    }


class _Tokenizer:
    def decode(self, tokens: tuple[int, ...], *, skip_special_tokens: bool) -> str:
        assert skip_special_tokens is False
        return "{}"


class _Samples:
    def __init__(self) -> None:
        self.calls = 0

    async def sample_async(self, **_: object) -> object:
        self.calls += 1
        if self.calls == 2:
            raise RuntimeError("provider failed once")
        return SimpleNamespace(sequences=[SimpleNamespace(tokens=(1,), stop_reason="stop")])


def test_raw_generation_is_persisted_before_a_later_one_shot_sample_failure() -> None:
    temporary = Path(tempfile.mkdtemp(dir=ROOT))
    try:
        evaluator = phase3_full_tinker.TinkerEvaluator(
            ROOT,
            temporary,
            SimpleNamespace(tokenizer=_Tokenizer()),  # type: ignore[arg-type]
            _contract(),
            "wp3-4-test",
            SimpleNamespace(),  # type: ignore[arg-type]
        )
        rows = (
            {"request_id": "dev:first", "input_token_ids": [1]},
            {"request_id": "dev:second", "input_token_ids": [2]},
        )
        with pytest.raises(RuntimeError, match="failed once"):
            asyncio.run(evaluator._sample_rows(_Samples(), 10, "sampler://one", "fast-dev", rows))
        raw_directory = temporary / "evaluations" / "step-010" / "fast-dev" / "raw"
        raw_files = list(raw_directory.glob("*/raw-generation.json"))
        assert len(raw_files) == 1
    finally:
        shutil.rmtree(temporary)


class _Rest:
    def __init__(self) -> None:
        self.deleted: list[str] = []

    async def get_training_run_async(self, _: str) -> object:
        return SimpleNamespace(
            base_model="Qwen/Qwen3.6-35B-A3B",
            corrupted=False,
            is_lora=True,
            lora_rank=64,
            training_run_id="run-1",
            user_metadata={},
        )

    async def delete_checkpoint_from_tinker_path_async(self, path: str) -> None:
        self.deleted.append(path)


class _Service:
    def __init__(self, **_: object) -> None:
        self.rest = _Rest()
        self.create_calls = 0
        self.key_seen_during_create = False

    def create_rest_client(self) -> _Rest:
        return self.rest

    async def get_server_capabilities_async(self) -> object:
        return SimpleNamespace(
            supported_models=[
                SimpleNamespace(model_name="Qwen/Qwen3.6-35B-A3B", max_context_length=64000)
            ]
        )

    async def create_lora_training_client_async(self, **_: object) -> object:
        self.create_calls += 1
        self.key_seen_during_create = os.environ.get("TINKER_API_KEY") == "test-key"
        return SimpleNamespace(
            model_id="run-1",
            model_data=SimpleNamespace(
                arch="qwen",
                tokenizer_id="Qwen/Qwen3.6-35B-A3B",
                model_name="Qwen/Qwen3.6-35B-A3B",
            ),
            is_lora=True,
            lora_rank=64,
            model_name="Qwen/Qwen3.6-35B-A3B",
            get_info_async=lambda: asyncio.sleep(
                0,
                result=SimpleNamespace(
                    model_id="run-1",
                    model_data=SimpleNamespace(
                        arch="qwen",
                        tokenizer_id="Qwen/Qwen3.6-35B-A3B",
                        model_name="Qwen/Qwen3.6-35B-A3B",
                    ),
                    is_lora=True,
                    lora_rank=64,
                    model_name="Qwen/Qwen3.6-35B-A3B",
                ),
            ),
        )


def test_provider_initializes_once_with_credential_and_delegates_checkpoint_cleanup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _Service()
    monkeypatch.setenv("TINKER_API_KEY", "test-key")
    provider = phase3_full_tinker.TinkerRunProvider(lambda **_: service, "wp3-4-test")
    identity = asyncio.run(provider.initialize())
    monkeypatch.delenv("TINKER_API_KEY")
    assert identity["lora_rank"] == 64
    assert service.create_calls == 1
    assert service.key_seen_during_create is True
    assert asyncio.run(provider.identity()) == identity
    assert service.create_calls == 1
    asyncio.run(provider.delete_checkpoint("tinker://run-1/weights/sampler"))
    assert service.rest.deleted == ["tinker://run-1/weights/sampler"]


def test_evaluator_reuses_one_sampling_client_for_full_retention_checkpoint_seam() -> None:
    temporary = Path(tempfile.mkdtemp(dir=ROOT))
    calls = 0

    async def sampling_client(_: str) -> object:
        nonlocal calls
        calls += 1
        return object()

    try:
        evaluator = phase3_full_tinker.TinkerEvaluator(
            ROOT,
            temporary,
            SimpleNamespace(tokenizer=_Tokenizer()),  # type: ignore[arg-type]
            _contract(),
            "wp3-4-test",
            SimpleNamespace(sampling_client=sampling_client),  # type: ignore[arg-type]
        )
        first = asyncio.run(evaluator._sampling_client("sampler://same"))
        second = asyncio.run(evaluator._sampling_client("sampler://same"))
        assert first is second
        assert calls == 1
    finally:
        shutil.rmtree(temporary)
