from __future__ import annotations

import asyncio
import base64
import gzip
import json
import struct
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace

import pytest
import tinker

from im.assets.model import canonical_artifact_bytes
from im.schema.actions import RespondAction
from im.training import phase3x_sft_run as runner


def _digest(raw: bytes) -> str:
    return f"sha256:{sha256(raw).hexdigest()}"


def _candidate(root: Path) -> str:
    directory = root / runner.CANDIDATE_DIRECTORY
    directory.mkdir(parents=True)
    offline = root / runner.OFFLINE_DEV_DIRECTORY
    offline.mkdir(parents=True)
    offline_sums = b"frozen-dev\n"
    (offline / "SHA256SUMS").write_bytes(offline_sums)
    datum_ids = [f"semantic:{index:04d}" for index in range(2_000)]
    weight = struct.pack("<f", 1.0)
    datums = b"".join(
        canonical_artifact_bytes(
            {
                "datum_id": datum_id,
                "input_tokens": [1],
                "kind": "semantic_intent",
                "positive_token_count": 1,
                "target_tokens": [runner.TERMINAL_TOKEN_ID],
                "weights": [1.0],
                "weights_float32_le_base64": base64.b64encode(weight).decode("ascii"),
            }
        )
        + b"\n"
        for datum_id in datum_ids
    )
    steps = []
    offset = 0
    for step, size in enumerate([32] * 62 + [16], start=1):
        ids = datum_ids[offset : offset + size]
        offset += size
        membership = {"interaction_datum_ids": ids, "step": step}
        steps.append(
            {**membership, "membership_sha256": _digest(canonical_artifact_bytes(membership))}
        )
    dev_ids = [f"dev:{index:03d}" for index in range(300)]
    fast_ids = dev_ids[:11]
    request_rows = [
        {
            "input_token_count": 1,
            "input_token_ids_sha256": _digest(str(index + 1).encode()),
            "state_id": state_id,
        }
        for index, state_id in enumerate(dev_ids)
    ]
    materialized = [{**row, "input_tokens": [index + 1]} for index, row in enumerate(request_rows)]
    full = gzip.compress(
        b"".join(canonical_artifact_bytes(row) + b"\n" for row in materialized), mtime=0
    )
    fast = gzip.compress(
        b"".join(canonical_artifact_bytes(row) + b"\n" for row in materialized[:11]), mtime=0
    )
    eval_inventory = {
        "full_dev_state_count": 300,
        "kind": "phase3x-semantic-intent-eval-request-inventory-v1",
        "max_expected_output_token_count": 32,
        "request_count_across_schedule": 911,
        "requests": request_rows,
        "sampling": {
            "constrained_decoding": False,
            "max_output_tokens": 256,
            "provider": "Tinker",
            "stop_token_id": runner.TERMINAL_TOKEN_ID,
            "temperature": 0,
            "top_p": 1,
        },
        "schedule": [
            {"kind": "fast_policy_sanity", "state_ids": fast_ids, "step": 10},
            *[{"kind": "full_dev", "state_ids": dev_ids, "step": step} for step in (20, 40, 63)],
        ],
    }
    evaluation = {
        "checkpoints": {
            "10": "fast_policy_sanity",
            "20": "full_dev",
            "40": "full_dev",
            "63": "full_dev_and_mandatory_selection",
        },
        "constrained_decoding_claimed": False,
        "full_retention_during_policy_sft": False,
        "kind": "phase3x-semantic-intent-eval-contract-v1",
        "raw_unconstrained_tinker_only": True,
        "sampling_artifacts": {
            "fast_policy_sanity": {
                "path": runner.FAST_EVALUATION_FILE,
                "sha256": _digest(fast),
            },
            "full_dev": {"path": runner.FULL_DEV_EVALUATION_FILE, "sha256": _digest(full)},
        },
    }
    files = {
        "batch-plan.json": canonical_artifact_bytes(
            {
                "kind": "phase3x-semantic-intent-batch-plan-v1",
                "no_replay": True,
                "steps": steps,
            }
        ),
        "cost-model.json": canonical_artifact_bytes(
            {
                "authorization": False,
                "components_usd": {"training_usd": 42.5},
                "hard_ceiling_usd": 55,
                "kind": "phase3x-semantic-intent-cost-model-v1",
                "modeled_total_usd": 42.5,
                "paid_enforcement": False,
                "provider_calls_made": False,
            }
        ),
        "datum-index.json": b"[]\n",
        runner.DEV_DERIVATION_FILE: canonical_artifact_bytes(
            {
                "derivation_count": 300,
                "kind": "phase3x-policy-intent-dev-derivation-proof-v1",
                "rows": [
                    {
                        "intent_sha256": f"sha256:{index:064x}",
                        "state_id": state_id,
                    }
                    for index, state_id in enumerate(dev_ids)
                ],
            }
        ),
        "eval-contract.json": canonical_artifact_bytes(evaluation),
        runner.EVALUATION_INVENTORY_FILE: canonical_artifact_bytes(eval_inventory),
        runner.FAST_EVALUATION_FILE: fast,
        runner.FULL_DEV_EVALUATION_FILE: full,
        "mask-proof.json": b"{}\n",
        "materialized-datums.jsonl.gz": gzip.compress(datums, mtime=0),
        "policy-intent-prompt-v1.txt": b"policy\n",
        "policy-intent-schema.json": b"{}\n",
        "response-kind-authority.json": b"{}\n",
        "source-lineage.json": b"[]\n",
        "token-accounting.json": b"{}\n",
        "training-contract.json": canonical_artifact_bytes(
            {
                "backbone": runner.BACKBONE,
                "epochs": 1,
                "kind": "phase3x-semantic-intent-training-contract-v1",
                "lora": {
                    "rank": 16,
                    "train_attention": True,
                    "train_mlp": True,
                    "train_unembed": False,
                },
                "optimizer_steps": 63,
                "peak_learning_rate": 1e-4,
                "replay_datum_count": 0,
                "restart_or_second_sft_authorized": False,
                "schedule": {
                    "formula": ("step<=10:1e-4*step/10;step>10:1e-4*0.5*(1+cos(pi*(step-10)/53))"),
                    "horizon_steps": 63,
                    "kind": "linear-warmup-then-cosine-to-zero",
                    "learning_rates": [
                        {"learning_rate": runner.learning_rate(step), "step": step}
                        for step in range(1, 64)
                    ],
                    "warmup_steps": 10,
                },
                "seed": 20260801,
                "target_datum_count": 2_000,
                "terminal_token_id": 248046,
            }
        ),
    }
    manifest = {
        "authorization": {
            "checkpoint_access": False,
            "checksum_bound_authorization": False,
            "dpo": False,
            "launch": False,
            "provider_calls": False,
            "retention_60": False,
            "sealed_test": False,
            "secrets": False,
            "spend": False,
        },
        "bindings": {"offline_dev_sha256sums_sha256": _digest(offline_sums)},
        "candidate_checksum_bound": True,
        "candidate_status": "offline_unapproved_create_only",
        "files": {name: _digest(raw) for name, raw in sorted(files.items())},
        "kind": "phase3x-consolidated-gate-1-semantic-sft-candidate-v1",
        "source_commit": "0" * 40,
    }
    files["gate-1-manifest.json"] = canonical_artifact_bytes(manifest)
    for name, raw in files.items():
        (directory / name).write_bytes(raw)
    sums = "".join(
        f"{sha256(raw).hexdigest()}  {name}\n" for name, raw in sorted(files.items())
    ).encode("ascii")
    (directory / "SHA256SUMS").write_bytes(sums)
    return _digest(sums)


def test_candidate_preflight_closes_exact_one_epoch_contract(tmp_path: Path) -> None:
    digest = _candidate(tmp_path)
    contract = runner.load_candidate(tmp_path, digest)

    assert len(contract.datums) == 2_000
    assert len(contract.batches) == 63
    assert sum(len(batch.datum_ids) for batch in contract.batches) == 2_000
    assert all(not batch.replay_ids for batch in contract.batches)
    assert contract.modeled_total_usd == 42.5
    assert set(contract.evaluation_artifacts) == {"fast_policy_sanity", "full_dev"}


def test_learning_rate_and_sampling_schedule_are_exact() -> None:
    assert runner.learning_rate(1) == pytest.approx(1e-5)
    assert runner.learning_rate(10) == pytest.approx(1e-4)
    assert runner.learning_rate(63) == pytest.approx(0.0, abs=1e-15)
    assert all(
        runner.learning_rate(step) > runner.learning_rate(step + 1) for step in range(10, 63)
    )
    assert {
        step: runner.evaluation_at(step) for step in range(1, 64) if runner.evaluation_at(step)
    } == {
        10: "fast_policy_sanity",
        20: "full_dev",
        40: "full_dev",
        63: "full_dev",
    }
    with pytest.raises(runner.Phase3XSFTRunError):
        runner.learning_rate(64)


def test_response_route_match_requires_the_exact_frozen_intent() -> None:
    expected = RespondAction(type="respond", reply_to_event_id="e_000001", text="Which field?")
    request = runner.LanguageRealizationRequest(
        type="respond",
        reference_event_id="e_000001",
        response_kind="clarification",
    )

    assert not runner._semantic_action_matches(expected, request)
    assert runner._semantic_action_matches(expected, request, intent_match=True)
    assert runner._unsafe_resolution(request, licensed=False, resolved=False)
    assert not runner._unsafe_resolution(request, licensed=False, resolved=True)


def test_checksum_drift_fails_closed(tmp_path: Path) -> None:
    digest = _candidate(tmp_path)
    (tmp_path / runner.CANDIDATE_DIRECTORY / "cost-model.json").write_text("{}")

    with pytest.raises(runner.Phase3XSFTRunError, match="checksum manifest"):
        runner.load_candidate(tmp_path, digest)


def test_owner_authorization_is_separate_and_precedes_provider(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    digest = _candidate(tmp_path)
    monkeypatch.setattr(runner, "SOURCE_FILES", ())
    monkeypatch.setattr(runner, "verify_source", lambda *_args: None)
    monkeypatch.setattr(runner, "verify_launchd", lambda: None)
    runner.prepare_execution(
        tmp_path,
        source_commit="0" * 40,
        candidate_sha256sums_sha256=digest,
    )
    execution = tmp_path / runner.EXECUTION_DIRECTORY
    packet = execution / "execution-packet.json"
    template = json.loads((execution / "owner-authorization-template.json").read_bytes())
    assert template["decision"] == "pending_independent_owner_binding"
    assert not (execution / "owner-authorization.json").exists()

    called = False

    def provider(*_args: object, **_kwargs: object) -> object:
        nonlocal called
        called = True
        return object()

    with pytest.raises(runner.Phase3XSFTRunError, match="owner authorization"):
        runner.construct_authorized_provider(
            tmp_path,
            packet_path=packet.relative_to(tmp_path),
            authorization_path=(execution / "owner-authorization-template.json").relative_to(
                tmp_path
            ),
            candidate_sha256sums_sha256=digest,
            service_factory=object,
            provider_factory=provider,
        )
    assert called is False

    authorization = {
        **template,
        "decision": "authorized",
        "kind": "phase3x-semantic-intent-sft-owner-authorization-v1",
        "owner_instruction": "okay start",
    }
    auth_path = execution / "owner-authorization.json"
    auth_path.write_bytes(canonical_artifact_bytes(authorization))
    result = runner.construct_authorized_provider(
        tmp_path,
        packet_path=packet.relative_to(tmp_path),
        authorization_path=auth_path.relative_to(tmp_path),
        candidate_sha256sums_sha256=digest,
        service_factory=object,
        provider_factory=provider,
    )
    assert called is True
    assert result is not None
    (execution / "launch-plan.json").write_bytes(b"{}")
    with pytest.raises(runner.Phase3XSFTRunError, match="prepared execution manifest"):
        runner.load_authorized_execution(
            tmp_path,
            packet_path=packet.relative_to(tmp_path),
            authorization_path=auth_path.relative_to(tmp_path),
            candidate_sha256sums_sha256=digest,
        )


def test_fake_paid_path_runs_exact_one_trajectory_and_selects_checkpoint(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    datum = runner.TrainingDatum(
        "semantic:one",
        "semantic_intent",
        (1,),
        (runner.TERMINAL_TOKEN_ID,),
        struct.pack("<f", 1.0),
        1,
    )
    batches = tuple(
        runner.ReplayBatch(step, (datum.datum_id,), (), f"sha256:{step:064x}", "1")
        for step in range(1, 64)
    )
    ranking = [
        {"metric": metric, "direction": direction}
        for metric, direction in (
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
        )
    ]
    cost = {
        "modeled_total_usd": 9.0,
        "storage_assumptions": {
            "full_checkpoint_bytes_each": 100,
            "sampler_checkpoint_bytes_each": 100,
        },
    }
    contract = runner.Phase3XSFTContract(
        "sha256:" + "a" * 64,
        "0" * 40,
        {datum.datum_id: datum},
        batches,
        {"selection_fallback": {"eligible_steps": [20, 40, 63], "ranking": ranking}},
        {},
        {},
        {},
        cost,
        9.0,
    )

    class Client:
        def __init__(self) -> None:
            self.steps = 0
            self.learning_rates: list[float] = []
            self.states: list[int] = []
            self.samplers: list[int] = []

        async def forward_backward_async(self, data: list[object], _loss: str) -> object:
            return SimpleNamespace(
                loss_fn_outputs=[{"logprobs": tinker.TensorData([-0.5], dtype="float32")}]
            )

        async def optim_step_async(self, params: object) -> object:
            self.steps += 1
            self.learning_rates.append(float(params.learning_rate))
            return SimpleNamespace(metrics={"unclipped_grad_l2:mean": 0.25})

        async def save_state_async(self, name: str, ttl_seconds: int | None) -> object:
            assert ttl_seconds is None
            step = int(name.rsplit("-", 1)[1])
            self.states.append(step)
            return SimpleNamespace(path=f"state://{step}")

        async def save_weights_for_sampler_async(self, name: str, ttl_seconds: int) -> object:
            assert ttl_seconds == runner.SAMPLER_TTL_SECONDS
            step = int(name.rsplit("-", 1)[1])
            self.samplers.append(step)
            return SimpleNamespace(path=f"sampler://{step}")

    class Provider:
        instance: Provider | None = None

        def __init__(self, *_args: object, **_kwargs: object) -> None:
            self.client = Client()
            self.deleted: list[str] = []
            Provider.instance = self

        async def initialize(self) -> dict[str, object]:
            return {
                "base_model": runner.BACKBONE,
                "is_lora": True,
                "lora_rank": 16,
                "train_attn": True,
                "train_mlp": True,
                "train_unembed": False,
            }

        async def create_training_client(self) -> Client:
            return self.client

        async def checkpoint_size(self, _path: str) -> int:
            return 10

        async def checkpoint_metadata(self, path: str) -> dict[str, object]:
            state = path.startswith("state://")
            return {
                "checkpoint_created_at": 1,
                "checkpoint_expires_at": None if state else 2,
                "checkpoint_is_durable": state,
                "remaining_ttl_seconds": None if state else 100,
            }

        async def delete_checkpoint(self, path: str) -> None:
            self.deleted.append(path)

    calls: list[tuple[str, int]] = []

    class Evaluator:
        def __init__(self, *_args: object) -> None:
            pass

        async def __call__(self, kind: str, step: int, _path: str) -> dict[str, object]:
            calls.append((kind, step))
            score = {20: 200, 40: 250, 63: 225}.get(step, 10)
            return {
                "active_floor_premature_respond_count": 0,
                "aspirational_gate_passed": False,
                "duplicate_delegate_or_schedule_count": 0,
                "mark_semantic_selection_count": 27,
                "raw_unconstrained_intent_valid_count": 294,
                "request_count": 11 if step == 10 else 300,
                "resolved_external_action_count": score,
                "resolved_six_action_count": 111,
                "step": step,
                "timer_lifecycle_invalid_count": 0,
                "unsafe_resolved_execution_count": 0,
                "wrong_rollover_mutation_count": 0,
            }

    packet = tmp_path / "packet.json"
    authorization = tmp_path / "authorization.json"
    packet.write_text("{}")
    authorization.write_text("{}")
    monkeypatch.setattr(
        runner,
        "load_authorized_execution",
        lambda *_args, **_kwargs: (
            contract,
            {"source_commit": "0" * 40},
            {"decision": "authorized"},
        ),
    )
    monkeypatch.setattr(runner, "verify_launchd", lambda: None)
    monkeypatch.setattr(runner, "load_pinned_tokenizer", lambda *_args: object())
    async def rebuild(*_args: object) -> tuple[object, ...]:
        return ()

    monkeypatch.setattr(runner, "rebuild_dev_states", rebuild)
    monkeypatch.setattr(runner, "RUN_OUTPUT", Path("run"))
    result = asyncio.run(
        runner.execute(
            root=tmp_path,
            packet_path=packet,
            authorization_path=authorization,
            candidate_sha256sums_sha256=contract.candidate_sha256sums_sha256,
            output_path=Path("run"),
            provider_factory=Provider,
            service_factory=object,
            secret_reader=lambda _path: "fake",
            evaluator_factory=Evaluator,
        )
    )
    provider = Provider.instance
    assert provider is not None
    assert provider.client.steps == 63
    assert provider.client.learning_rates == pytest.approx(
        [runner.learning_rate(step) for step in range(1, 64)]
    )
    assert provider.client.states == [20, 40, 63]
    assert provider.client.samplers == [10, 20, 40, 63]
    assert calls == [
        ("fast_policy_sanity", 10),
        ("full_dev", 20),
        ("full_dev", 40),
        ("full_dev", 63),
    ]
    assert result["selected_step"] == 40
    assert result["status"] == "completed_selected_one_checkpoint"
    assert "state://40" not in provider.deleted
    assert set(provider.deleted) == {
        "sampler://10",
        "sampler://20",
        "sampler://40",
        "sampler://63",
        "state://20",
        "state://63",
    }
    sums = (tmp_path / "run/SHA256SUMS").read_text().splitlines()
    assert {line.split("  ", 1)[1] for line in sums} == {
        path.relative_to(tmp_path / "run").as_posix()
        for path in (tmp_path / "run").rglob("*")
        if path.is_file() and path != tmp_path / "run/SHA256SUMS"
    }


def test_detached_logs_are_captured_only_after_exit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    output = tmp_path / "run"
    output.mkdir()
    stdout = tmp_path / "launch.stdout"
    stderr = tmp_path / "launch.stderr"
    stdout.write_bytes(b"out\n")
    stderr.write_bytes(b"err\n")
    monkeypatch.setattr(runner, "STDOUT_LOG", stdout)
    monkeypatch.setattr(runner, "STDERR_LOG", stderr)
    monkeypatch.setattr(
        runner.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=1, stdout=""),
    )

    receipt = runner.capture_detached_logs(tmp_path, Path("run"))

    assert receipt["logs"] == {
        "stderr.log": _digest(b"err\n"),
        "stdout.log": _digest(b"out\n"),
    }
    assert (output / "SHA256SUMS").is_file()
    with pytest.raises(runner.Phase3XSFTRunError, match="already captured"):
        runner.capture_detached_logs(tmp_path, Path("run"))


def test_offline_initialization_failure_is_sealed_before_secret(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    packet = tmp_path / "packet.json"
    authorization = tmp_path / "authorization.json"
    packet.write_bytes(b"{}")
    authorization.write_bytes(b"{}")
    contract = SimpleNamespace(candidate_source_commit="0" * 40, modeled_total_usd=9.0)
    monkeypatch.setattr(
        runner,
        "load_authorized_execution",
        lambda *_args, **_kwargs: (
            contract,
            {"source_commit": "0" * 40},
            {"decision": "authorized"},
        ),
    )
    monkeypatch.setattr(runner, "verify_launchd", lambda: None)
    monkeypatch.setattr(runner, "RUN_OUTPUT", Path("run"))
    monkeypatch.setattr(
        runner,
        "load_pinned_tokenizer",
        lambda *_args: (_ for _ in ()).throw(RuntimeError("offline failure")),
    )
    secret_read = False

    def secret_reader(_path: Path) -> str:
        nonlocal secret_read
        secret_read = True
        return "never"

    with pytest.raises(RuntimeError, match="offline failure"):
        asyncio.run(
            runner.execute(
                root=tmp_path,
                packet_path=packet,
                authorization_path=authorization,
                candidate_sha256sums_sha256="sha256:" + "a" * 64,
                output_path=Path("run"),
                secret_reader=secret_reader,
            )
        )

    assert secret_read is False
    status = json.loads((tmp_path / "run/status.json").read_bytes())
    assert status["status"] == "failed_pipeline"
    assert status["error_type"] == "RuntimeError"
    assert (tmp_path / "run/SHA256SUMS").is_file()
