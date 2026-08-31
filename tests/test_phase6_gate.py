from __future__ import annotations

import asyncio
import json
import runpy
import subprocess
import zipfile
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch
from safetensors.torch import save_file

from im.assets.model import canonical_artifact_bytes
from im.generation.demo_scenes import (
    HeroBehavior,
    _intents,
    build_demo_variants,
    run_demo_variant,
)
from im.generation.phase6_cloud import (
    BASE_REVISION,
    DISK_GIB,
    DLVM_IMAGE,
    DLVM_PROJECT,
    MACHINE_TYPE,
    MAX_MODEL_LEN,
    REGION,
    SPOT_GPU_METRIC,
    SPOT_GPU_QUOTA_ID,
    VLLM_IMAGE,
    ZONE,
    Phase6CloudError,
    absence_commands,
    execute_commands,
    launch_commands,
    plan_object,
    teardown_commands,
    tunnel_command,
)
from im.generation.phase6_gate import (
    AUTHORIZATION_CLAIM_NAME,
    AUTHORIZATION_NAME,
    FIXED_PACKAGE_FILES,
    GUARDED_SOURCE_FILES,
    PACKAGE_RELATIVE,
    TEMPLATE_NAME,
    Phase6GateError,
    TinkerSemanticPolicy,
    _wait_for_restored_identity,
    authorization_template,
    checksum_inventory,
    claim_authorization,
    export_step63_adapter,
    load_authorization,
    package_files,
    qualify_frozen_variants,
    qualify_step63_with_tinker,
    reuse_v5_step63_adapter,
)
from im.policy.base import PolicyCallCancelled, PolicyCallTrace, ScriptedIntentPolicy
from im.training.phase3_data import PinnedTokenizer
from im.training.phase3_framing import TERMINAL_MARKER, TERMINAL_TOKEN_ID
from im.training.phase3_tinker import Phase3TinkerError


class _GatedIntentPolicy(ScriptedIntentPolicy):
    def __init__(self, actions) -> None:
        super().__init__(actions)
        self.entered = asyncio.Event()
        self.release = asyncio.Event()

    async def decide(self, policy_bytes: bytes) -> object:
        self.entered.set()
        await self.release.wait()
        return await super().decide(policy_bytes)


class _ExportClient:
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls
        self.model_id = "run-63"

    async def get_info_async(self):
        return SimpleNamespace(model_id="run-63")

    async def save_weights_for_sampler_async(self, _name: str, *, ttl_seconds: int):
        self.calls.append(f"save:{ttl_seconds}")
        return SimpleNamespace(path="tinker://run-63/sampler_weights/phase6")


class _ExportRest:
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls

    def get_weights_info_by_tinker_path(self, path: str):
        self.calls.append(f"weights:{path}")
        return SimpleNamespace()

    async def get_training_run_async(self, run_id: str):
        return SimpleNamespace(training_run_id=run_id)

    async def get_checkpoint_archive_url_from_tinker_path_async(self, path: str):
        self.calls.append(f"archive:{path}")
        return SimpleNamespace(url="https://offline.invalid/adapter")

    async def delete_checkpoint_from_tinker_path_async(self, path: str):
        self.calls.append(f"delete:{path}")


class _ExportService:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.rest = _ExportRest(self.calls)

    def create_rest_client(self):
        return self.rest

    async def create_training_client_from_state_async(self, path: str, **_kwargs):
        self.calls.append(f"restore:{path}")
        return _ExportClient(self.calls)


def _argv(commands, command_id: str) -> tuple[str, ...]:
    return next(command.argv for command in commands if command.command_id == command_id)


def test_cloud_plan_freezes_private_single_spot_vm_nat_vllm_and_teardown() -> None:
    created = datetime(2026, 8, 12, 18, 0, tzinfo=UTC)
    commands = launch_commands(created, "/authorized/adapter")
    vm = _argv(commands, "vm-create")
    start = _argv(commands, "vllm-start")
    image = _argv(commands, "dlvm-image")

    assert BASE_REVISION == "995ad96eacd98c81ed38be0c5b274b04031597b0"
    assert len(BASE_REVISION) == 40
    assert image == (
        "gcloud",
        "compute",
        "images",
        "describe",
        DLVM_IMAGE,
        f"--project={DLVM_PROJECT}",
        "--format=json",
        "--quiet",
    )
    first_mutation = next(index for index, command in enumerate(commands) if command.mutating)
    assert commands[0].command_id == "dlvm-image"
    assert all(not command.mutating for command in commands[:first_mutation])
    assert "--provisioning-model=SPOT" in vm
    assert "--instance-termination-action=DELETE" in vm
    assert "--termination-time=2026-08-13T18:00:00Z" in vm
    assert f"--boot-disk-size={DISK_GIB}GB" in vm
    assert "--boot-disk-type=hyperdisk-balanced" in vm
    assert "--boot-disk-auto-delete" in vm
    assert "--no-service-account" in vm and "--no-scopes" in vm
    assert any("no-address" in part for part in vm)
    assert sum(command.command_id == "vm-create" for command in commands) == 1
    ids = [command.command_id for command in commands]
    assert ids[ids.index("vm-create") + 1] == "vm-stabilize"
    assert _argv(commands, "vm-stabilize") == ("sleep", "60")
    assert "nat-create" in {command.command_id for command in commands}
    assert "capacity" in {command.command_id for command in commands}
    assert "router-create" in {command.command_id for command in commands}
    assert "address-create" in {command.command_id for command in commands}
    assert "--nat-external-ip-pool=im-phase56-v2-nat-ip" in _argv(commands, "nat-create")
    assert not any("logging" in part for part in _argv(commands, "nat-create"))
    remote = next(part for part in start if part.startswith("--command="))
    expected_hf = (
        f"sudo docker run --rm --entrypoint hf {VLLM_IMAGE} --version && "
        f"sudo docker run --rm --entrypoint hf -e HF_HUB_DISABLE_XET=1 "
        f"-v /srv/im/base:/base {VLLM_IMAGE} download "
        f"Qwen/Qwen3.6-35B-A3B --revision {BASE_REVISION} --local-dir /base"
    )
    assert expected_hf in remote
    assert "--max-num-seqs 16" in remote
    prepare = next(
        part for part in _argv(commands, "remote-prepare") if part.startswith("--command=")
    )
    assert "nvidia-container-toolkit=1.17.8-1" in prepare
    assert "libnvidia-container1=1.17.8-1" in prepare
    assert "nvidia-ctk runtime configure --runtime=docker" in prepare
    assert "sudo docker version" in prepare
    assert "huggingface-cli" not in remote
    assert "--language-model-only" in remote
    assert "--generation-config vllm" in remote
    assert f"--max-model-len {MAX_MODEL_LEN}" in remote
    assert "--host 127.0.0.1" in remote
    assert "phase3x-step63=/models/adapter" in remote
    assert "nvidia-580" in " ".join(vm)

    teardown_ids = [command.command_id for command in teardown_commands()]
    assert teardown_ids == [
        "container-delete",
        "vm-delete",
        "firewall-delete",
        "nat-delete",
        "address-delete",
        "router-delete",
        "subnet-delete",
        "network-delete",
    ]
    assert _argv(teardown_commands(), "vm-delete")[1:4] == (
        "compute",
        "instances",
        "delete",
    )
    assert _argv(teardown_commands(), "nat-delete")[1:5] == (
        "compute",
        "routers",
        "nats",
        "delete",
    )
    assert _argv(teardown_commands(), "network-delete")[1:4] == (
        "compute",
        "networks",
        "delete",
    )
    tunnel = tunnel_command().argv
    split = tunnel.index("--")
    assert "--project=im-artifacts-20260805" in tunnel[:split]
    assert "--project=im-artifacts-20260805" not in tunnel[split:]
    absent_ids = {command.command_id for command in absence_commands()}
    assert {
        "absent-disks",
        "absent-snapshots",
        "absent-addresses",
        "absent-reservations",
        "absent-firewall-rules",
        "absent-networks",
        "absent-subnets",
        "absent-routers",
    } <= absent_ids
    plan = plan_object("a" * 40)
    assert plan["cost"]["hard_ceiling_usd"] == 60.0
    assert plan["cost"]["estimated_usd"] == 47.2
    assert plan["vllm"]["language_model_only"] is True


def test_command_runner_fails_closed_on_command_existing_resource_or_missing_preflight() -> None:
    commands = {command.command_id: command for command in launch_commands(datetime.now(UTC), "/a")}
    regional_quota = commands["regional-quota"]
    spot_gpu_quota = commands["spot-gpu-quota"]
    regional_ok = subprocess.CompletedProcess(
        ("gcloud",),
        0,
        json.dumps(
            {
                "quotas": [
                    {"metric": "SSD_TOTAL_GB", "limit": 200, "usage": 0},
                    {"metric": "PREEMPTIBLE_CPUS", "limit": 48, "usage": 0},
                ]
            }
        ),
        "",
    )
    spot_ok = subprocess.CompletedProcess(
        ("gcloud",),
        0,
        json.dumps(
            {
                "dimensionsInfos": [{"applicableLocations": [REGION], "details": {"value": "1"}}],
                "isPrecise": True,
                "metric": SPOT_GPU_METRIC,
                "quotaId": SPOT_GPU_QUOTA_ID,
                "service": "compute.googleapis.com",
            }
        ),
        "",
    )
    assert execute_commands((regional_quota,), lambda _argv: regional_ok)
    assert execute_commands((spot_gpu_quota,), lambda _argv: spot_ok)

    failed = subprocess.CompletedProcess(("gcloud",), 1, "", "no")
    with pytest.raises(Phase6CloudError, match="cloud command failed"):
        execute_commands((regional_quota,), lambda _argv: failed)
    receipts: list[dict[str, object]] = []
    with pytest.raises(Phase6CloudError, match="cloud command failed"):
        execute_commands((regional_quota,), lambda _argv: failed, receipts)
    assert [(row["command_id"], row["returncode"]) for row in receipts] == [("regional-quota", 1)]

    absent = absence_commands()[0]
    exists = subprocess.CompletedProcess(("gcloud",), 0, "existing", "")
    with pytest.raises(Phase6CloudError, match="already exists"):
        execute_commands((absent,), lambda _argv: exists)

    empty = subprocess.CompletedProcess(("gcloud",), 0, "", "")
    with pytest.raises(Phase6CloudError, match="no evidence"):
        execute_commands((regional_quota,), lambda _argv: empty)


@pytest.mark.parametrize(
    ("patch", "error"),
    [
        ({"quotaId": "wrong"}, "identity"),
        ({"dimensionsInfos": []}, "does not apply"),
        (
            {"dimensionsInfos": [{"applicableLocations": [REGION], "details": {"value": "0"}}]},
            "insufficient",
        ),
        (
            {"dimensionsInfos": [{"applicableLocations": [REGION], "details": {"value": True}}]},
            "malformed",
        ),
    ],
)
def test_spot_gpu_quota_preflight_fails_closed(patch: dict[str, object], error: str) -> None:
    command = next(
        command
        for command in launch_commands(datetime.now(UTC), "/a")
        if command.command_id == "spot-gpu-quota"
    )
    payload: dict[str, object] = {
        "dimensionsInfos": [{"applicableLocations": [REGION], "details": {"value": "1"}}],
        "isPrecise": True,
        "metric": SPOT_GPU_METRIC,
        "quotaId": SPOT_GPU_QUOTA_ID,
        "service": "compute.googleapis.com",
    }
    payload.update(patch)
    completed = subprocess.CompletedProcess(("gcloud",), 0, json.dumps(payload), "")
    with pytest.raises(Phase6CloudError, match=error):
        execute_commands((command,), lambda _argv: completed)


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {
            "name": "wrong",
            "status": "READY",
            "selfLink": (
                "https://www.googleapis.com/compute/v1/projects/"
                f"{DLVM_PROJECT}/global/images/{DLVM_IMAGE}"
            ),
        },
        {
            "name": DLVM_IMAGE,
            "status": "FAILED",
            "selfLink": (
                "https://www.googleapis.com/compute/v1/projects/"
                f"{DLVM_PROJECT}/global/images/{DLVM_IMAGE}"
            ),
        },
        {
            "name": DLVM_IMAGE,
            "status": "READY",
            "selfLink": (
                f"https://www.googleapis.com/compute/v1/projects/wrong/global/images/{DLVM_IMAGE}"
            ),
        },
    ],
)
def test_dlvm_image_preflight_rejects_malformed_wrong_or_nonready(payload: object) -> None:
    command = launch_commands(datetime.now(UTC), "/a")[0]
    completed = subprocess.CompletedProcess(("gcloud",), 0, json.dumps(payload), "")
    with pytest.raises(Phase6CloudError, match="DLVM image identity or readiness drifted"):
        execute_commands((command,), lambda _argv: completed)


def test_dlvm_image_preflight_accepts_exact_ready_identity() -> None:
    command = launch_commands(datetime.now(UTC), "/a")[0]
    payload = {
        "name": DLVM_IMAGE,
        "status": "READY",
        "selfLink": (
            "https://www.googleapis.com/compute/v1/projects/"
            f"{DLVM_PROJECT}/global/images/{DLVM_IMAGE}"
        ),
    }
    completed = subprocess.CompletedProcess(("gcloud",), 0, json.dumps(payload), "")
    assert execute_commands((command,), lambda _argv: completed)


def test_dlvm_image_malformed_json_keeps_raw_receipt_before_failing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    command = launch_commands(datetime.now(UTC), "/a")[0]
    completed = subprocess.CompletedProcess(command.argv, 0, "{malformed", "image stderr")
    script = runpy.run_path(str(Path(__file__).parents[1] / "scripts/run_phase6_gate.py"))
    run_commands = script["_run_commands"]
    monkeypatch.setitem(run_commands.__globals__, "default_runner", lambda _argv: completed)
    raw = tmp_path / "cloud-launch-raw"
    with pytest.raises(Phase6CloudError, match="cloud preflight is not JSON"):
        run_commands((command,), raw_directory=raw)
    assert (raw / "dlvm-image.stdout").read_bytes() == b"{malformed"
    assert (raw / "dlvm-image.stderr").read_bytes() == b"image stderr"


def test_capacity_preflights_bind_shape_zone_and_spend_ceiling() -> None:
    commands = {command.command_id: command for command in launch_commands(datetime.now(UTC), "/a")}
    capacity = subprocess.CompletedProcess(
        ("gcloud",),
        0,
        json.dumps(
            {
                "recommendations": [
                    {
                        "shards": [
                            {
                                "instanceCount": 1,
                                "machineType": MACHINE_TYPE,
                                "provisioningModel": "SPOT",
                                "zone": f"zones/{ZONE}",
                            }
                        ]
                    }
                ]
            }
        ),
        "",
    )
    assert execute_commands((commands["capacity"],), lambda _argv: capacity)
    capacity_payload = json.loads(capacity.stdout)
    capacity_payload["recommendations"][0]["shards"][0]["instanceCount"] = True
    malformed_capacity = subprocess.CompletedProcess(
        ("gcloud",), 0, json.dumps(capacity_payload), ""
    )
    with pytest.raises(Phase6CloudError, match="no matching Spot capacity"):
        execute_commands((commands["capacity"],), lambda _argv: malformed_capacity)

    price_payload = {
        "machineType": MACHINE_TYPE,
        "preemptionHistory": [],
        "priceHistory": [
            {
                "interval": {"endTime": "2026-08-12T07:00:00Z"},
                "listPrice": {
                    "currencyCode": "USD",
                    "nanos": "799820000",
                    "units": "1",
                },
            }
        ],
    }
    price_payload["priceHistory"][0]["interval"]["endTime"] = datetime.now(UTC).isoformat()
    price = subprocess.CompletedProcess(("gcloud",), 0, json.dumps(price_payload), "")
    assert execute_commands((commands["capacity-price"],), lambda _argv: price)

    price_payload["priceHistory"][0]["listPrice"] = {
        "currencyCode": "USD",
        "units": "3",
    }
    too_expensive = subprocess.CompletedProcess(("gcloud",), 0, json.dumps(price_payload), "")
    with pytest.raises(Phase6CloudError, match="spend ceiling"):
        execute_commands((commands["capacity-price"],), lambda _argv: too_expensive)

    price_payload["priceHistory"][0]["interval"]["endTime"] = "2020-01-01T00:00:00Z"
    stale = subprocess.CompletedProcess(("gcloud",), 0, json.dumps(price_payload), "")
    with pytest.raises(Phase6CloudError, match="stale"):
        execute_commands((commands["capacity-price"],), lambda _argv: stale)

    price_payload["priceHistory"].append(
        {
            "interval": {"endTime": "zzz"},
            "listPrice": {"currencyCode": "USD", "units": "1"},
        }
    )
    malformed = subprocess.CompletedProcess(("gcloud",), 0, json.dumps(price_payload), "")
    with pytest.raises(Phase6CloudError, match="timestamp is malformed"):
        execute_commands((commands["capacity-price"],), lambda _argv: malformed)


def _materialize_package(root: Path, source_commit: str) -> Path:
    for relative in GUARDED_SOURCE_FILES:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(relative)
    files = package_files(root, source_commit)
    package = root / PACKAGE_RELATIVE
    package.mkdir(parents=True)
    for name, raw in files.items():
        (package / name).write_bytes(raw)
    (package / "SHA256SUMS").write_bytes(checksum_inventory(files))
    return package


def test_authorization_is_exact_and_package_guard_precedes_owner_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_commit = "a" * 40
    package = _materialize_package(tmp_path, source_commit)
    monkeypatch.setattr("im.generation.phase6_gate.verify_source", lambda _root, _commit: None)
    monkeypatch.setattr(
        "im.generation.phase6_gate.subprocess.run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(("git",), 1, "", ""),
    )
    package_digest = "sha256:" + sha256((package / "SHA256SUMS").read_bytes()).hexdigest()
    authorization = authorization_template(source_commit, package_digest)
    authorization["owner_decision"] = "AUTHORIZED"
    authorization_path = package / AUTHORIZATION_NAME
    authorization_path.write_bytes(canonical_artifact_bytes(authorization))

    assert load_authorization(tmp_path, package, authorization_path) == authorization
    authorization["base"]["revision"] = "wrong"
    authorization_path.write_bytes(canonical_artifact_bytes(authorization))
    with pytest.raises(Phase6GateError, match="does not exactly bind"):
        load_authorization(tmp_path, package, authorization_path)

    (package / "README.md").write_bytes(b"drift")
    with pytest.raises(Phase6GateError, match="checksum mismatch"):
        load_authorization(tmp_path, package, tmp_path / "missing-secret-like-owner-file")


def test_authorization_claim_is_create_only_and_prevents_relaunch(tmp_path: Path) -> None:
    package = tmp_path / PACKAGE_RELATIVE
    package.mkdir(parents=True)
    authorization = package / AUTHORIZATION_NAME
    authorization.write_bytes(b"authorized")
    output = tmp_path / "review/phase6/wp6-2-frozen-execution-v14"

    claim_authorization(tmp_path, package, authorization, output)
    claim = json.loads((package / AUTHORIZATION_CLAIM_NAME).read_bytes())
    assert claim["relaunch"] is False
    with pytest.raises(Phase6GateError, match="already claimed"):
        claim_authorization(tmp_path, package, authorization, output)


def test_package_is_checksum_closed_and_prior_versions_are_explicitly_rejected(
    tmp_path: Path,
) -> None:
    source_commit = "b" * 40
    package = _materialize_package(tmp_path, source_commit)
    lines = (package / "SHA256SUMS").read_text().splitlines()
    assert [line.split("  ", 1)[1] for line in lines] == sorted(FIXED_PACKAGE_FILES)
    manifest = json.loads((package / "execution-manifest-v14.json").read_bytes())
    model_card = (package / "model-card-v14.md").read_text()
    release = json.loads((package / "release-inventory-v14.json").read_bytes())
    template = json.loads((package / TEMPLATE_NAME).read_bytes())
    assert manifest["base"]["revision"] == BASE_REVISION
    assert manifest["rejected_v1"]["status"] == "rejected_preserved_immutable_evidence"
    assert manifest["rejected_v1"]["sha256sums_sha256"].startswith("sha256:")
    assert manifest["rejected_v2"]["status"] == ("rejected_pre_owner_preserved_immutable_evidence")
    assert manifest["rejected_v2"]["sha256sums_sha256"] == (
        "sha256:9fa0aff845c6d85c9e2105d72210e16d59ee311f1187ba30923b5a830bccf08d"
    )
    assert manifest["rejected_v3"]["status"] == ("rejected_pre_owner_preserved_immutable_evidence")
    assert manifest["rejected_v3"]["sha256sums_sha256"] == (
        "sha256:f3e570f3de66bb82c49f0db31f289de089f6fa6855c4e9f2c88f4727a1643a7e"
    )
    assert manifest["rejected_v4"]["status"] == ("failed_pre_cloud_preserved_immutable_evidence")
    assert manifest["rejected_v4"]["run_sha256sums_sha256"] == (
        "sha256:05c392fa5a821539c3d19d15313fe1b0bd70e2b41fc7b4f4faec1e2e13b1a714"
    )
    assert manifest["rejected_v5"]["adapter_export_reused_by_v14"] is True
    assert manifest["rejected_v5"]["run_sha256sums_sha256"] == (
        "sha256:c0c8ac8f9e42579e19c56ff28c7cfd8631b1f0c7123cc7628fa6c0781b16c1b0"
    )
    assert manifest["rejected_v6"]["run_sha256sums_sha256"] == (
        "sha256:a721396139406cc8ce8209ee79d85124d4d68a1b420925e815067da7455689ae"
    )
    assert manifest["rejected_v7"]["run_sha256sums_sha256"] == (
        "sha256:43673009f886121195d96aef10d890baa0afb6249ffbb2b12f475891f77f721d"
    )
    assert manifest["rejected_v8"]["run_sha256sums_sha256"] == (
        "sha256:dcbf9f7479b1af6c6482510dd961e8f38f297b6e147922689e0f4e7394cd9bd6"
    )
    assert manifest["rejected_v9"]["run_sha256sums_sha256"] == (
        "sha256:3f873b5d5b297eb1c0371e049e044e0b9b32d44fdfe48c1f41d90fb17717a183"
    )
    assert manifest["rejected_v10"]["run_sha256sums_sha256"] == (
        "sha256:6d4e3aad9d0ef2d1ac5f650589b01959661be9181ebb014a0cc1ae2b9ee2089d"
    )
    assert manifest["rejected_v11"]["run_sha256sums_sha256"] == (
        "sha256:9b9305086798c4a9a404e53a2746beae5f8798b0a460b47369a41d77a5c6442c"
    )
    assert manifest["rejected_v12"]["run_sha256sums_sha256"] == (
        "sha256:93790b10171b8d4cadaf7fa6d655725121c0fe98086daba6937d04c0c578d54c"
    )
    assert manifest["rejected_v12"]["teardown_recovery_sha256sums_sha256"] == (
        "sha256:64ff7c1c2cdb16551b17dc6eb41e5c4da0baab57a8c76873e47394e9f1c0ef4d"
    )
    assert manifest["rejected_v13"]["run_sha256sums_sha256"] == (
        "sha256:9fb33344e08aed0cd8d86cb01ce7e81cc949839ff9641e75c37127c1ece7f390"
    )
    assert BASE_REVISION in model_card
    assert release["base"]["revision"] == BASE_REVISION
    assert len(release["process_deviations"]) == 2
    assert template["owner_decision"] == "DENY_REPLACE_WITH_AUTHORIZED"
    assert template["package_sha256sums_sha256"] == "REPLACE_WITH_SHA256_OF_SHA256SUMS"


def test_v14_reuses_checksum_verified_v5_adapter_without_provider(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "review/phase6/wp6-2-frozen-execution-v5"
    adapter = source / "adapter-export/adapter"
    adapter.mkdir(parents=True)
    files = {
        "adapter-export/adapter/adapter_model.safetensors": b"adapter",
        "adapter-export/export-receipt.json": canonical_artifact_bytes(
            {
                "sampler_deleted": True,
                "state": (
                    "tinker://033dbe01-6de4-5262-9e93-4a4761dafa74:train:0/weights/phase3x-state-63"
                ),
                "training_identity": {
                    "lora_rank": 16,
                    "rest_corrupted": False,
                    "rest_is_lora": True,
                    "rest_lora_rank": 16,
                },
                "weights": {
                    "base_model": "Qwen/Qwen3.6-35B-A3B",
                    "lora_rank": 16,
                    "train_attn": True,
                    "train_mlp": True,
                    "train_unembed": False,
                },
            }
        ),
        "status.json": canonical_artifact_bytes(
            {
                "error_type": "Phase6CloudError",
                "format_version": "phase5-6-gate-status-v5",
                "status": "failed_teardown_pending",
                "teardown_verified": "not_required_before_first_mutation",
            }
        ),
    }
    for name, raw in files.items():
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    manifest = checksum_inventory(files)
    (source / "SHA256SUMS").write_bytes(manifest)
    monkeypatch.setattr(
        "im.generation.phase6_gate.REJECTED_V5_RUN_SHA256SUMS",
        "sha256:" + sha256(manifest).hexdigest(),
    )
    output = tmp_path / "v14"
    output.mkdir()

    assert reuse_v5_step63_adapter(tmp_path, output) == adapter
    assert json.loads((output / "adapter-reuse-receipt.json").read_bytes())["state"].endswith(
        "phase3x-state-63"
    )

    extra = adapter / "extra.safetensors"
    extra.write_bytes(b"extra")
    with pytest.raises(Phase6GateError, match="file inventory drifted"):
        reuse_v5_step63_adapter(tmp_path, tmp_path / "extra-output")
    extra.unlink()

    model = adapter / "adapter_model.safetensors"
    same_bytes = tmp_path / "same-adapter"
    same_bytes.write_bytes(model.read_bytes())
    model.unlink()
    model.symlink_to(same_bytes)
    with pytest.raises(Phase6GateError, match="contains a symlink"):
        reuse_v5_step63_adapter(tmp_path, tmp_path / "symlink-output")


@pytest.mark.asyncio
async def test_restored_identity_waits_only_for_rest_identity_convergence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Client:
        model_id = "run-63"

        async def get_info_async(self):
            return SimpleNamespace(model_id="run-63")

    runs = iter(("source-run", "run-63"))
    queries: list[str] = []

    class Rest:
        async def get_training_run_async(self, run_id: str):
            queries.append(run_id)
            return SimpleNamespace(training_run_id=next(runs))

    sleeps: list[int] = []

    async def fake_sleep(seconds: int) -> None:
        sleeps.append(seconds)

    monkeypatch.setattr("im.generation.phase6_gate.asyncio.sleep", fake_sleep)

    def verify(info, run, *, expected_lora_rank: int):
        assert expected_lora_rank == 16
        if info.model_id != run.training_run_id:
            raise Phase3TinkerError("Tinker REST training-run identity mismatch")
        return {"lora_rank": expected_lora_rank, "model_id": info.model_id}

    monkeypatch.setattr("im.generation.phase6_gate._verify_info", verify)

    result = await _wait_for_restored_identity(Client(), Rest())
    assert result["model_id"] == "run-63"
    assert result["lora_rank"] == 16
    assert result["rest_identity_attempts"] == 2
    assert sleeps == [5]
    assert queries == ["run-63", "run-63"]


@pytest.mark.asyncio
async def test_restored_identity_does_not_retry_non_identity_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Client:
        model_id = "run-63"

        async def get_info_async(self):
            return SimpleNamespace(model_id="run-63")

    class Rest:
        async def get_training_run_async(self, _run_id: str):
            return SimpleNamespace(training_run_id="run-63")

    sleeps: list[int] = []

    async def fake_sleep(seconds: int) -> None:
        sleeps.append(seconds)

    monkeypatch.setattr("im.generation.phase6_gate.asyncio.sleep", fake_sleep)
    monkeypatch.setattr(
        "im.generation.phase6_gate._verify_info",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            Phase3TinkerError("Tinker LoRA rank identity mismatch")
        ),
    )

    with pytest.raises(Phase3TinkerError, match="LoRA rank identity mismatch"):
        await _wait_for_restored_identity(Client(), Rest())
    assert sleeps == []


@pytest.mark.asyncio
async def test_restored_identity_rejects_unanchored_client_before_rest() -> None:
    class Client:
        model_id = "run-63"

        async def get_info_async(self):
            return SimpleNamespace(model_id="wrong-run")

    class Rest:
        async def get_training_run_async(self, _run_id: str):
            raise AssertionError("REST must not be queried")

    with pytest.raises(Phase3TinkerError, match="client info identity mismatch"):
        await _wait_for_restored_identity(Client(), Rest())


@pytest.mark.asyncio
async def test_restored_identity_exhausts_bound_without_sampling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Client:
        model_id = "run-63"

        async def get_info_async(self):
            return SimpleNamespace(model_id="run-63")

    class Rest:
        calls = 0

        async def get_training_run_async(self, run_id: str):
            assert run_id == "run-63"
            self.calls += 1
            return SimpleNamespace(training_run_id="source-run")

    sleeps: list[int] = []

    async def fake_sleep(seconds: int) -> None:
        sleeps.append(seconds)

    rest = Rest()
    monkeypatch.setattr("im.generation.phase6_gate.asyncio.sleep", fake_sleep)
    with pytest.raises(Phase3TinkerError, match="REST training-run identity mismatch"):
        await _wait_for_restored_identity(Client(), rest)
    assert rest.calls == 13
    assert sleeps == [5] * 12


@pytest.mark.asyncio
async def test_step63_export_binds_archive_tensors_and_sampler_deletion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FakeNotFoundError(Exception):
        pass

    source = tmp_path / "source"
    source.mkdir()
    (source / "adapter_config.json").write_text('{"peft_type":"LORA"}')
    save_file({"model.q_proj.lora_A.weight": torch.zeros((2, 2))}, source / "adapter.safetensors")
    archive = tmp_path / "source.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.write(source / "adapter_config.json", "adapter_config.json")
        bundle.write(source / "adapter.safetensors", "adapter.safetensors")

    async def weights(_rest, path):
        if "sampler_weights" in path:
            raise FakeNotFoundError("deleted")
        return SimpleNamespace()

    monkeypatch.setattr("im.generation.phase6_gate.tinker.NotFoundError", FakeNotFoundError)
    monkeypatch.setattr("im.generation.phase6_gate._get_weights_info", weights)
    monkeypatch.setattr("im.generation.phase6_gate._verify_weights_info", lambda *_a, **_k: None)
    monkeypatch.setattr(
        "im.generation.phase6_gate._verify_info", lambda *_a, **_k: {"model_id": "run-63"}
    )
    monkeypatch.setattr(
        "im.generation.phase6_gate._weights_evidence",
        lambda _value: {"is_lora": True, "lora_rank": 16},
    )

    def download(_url: str, destination: Path):
        raw = archive.read_bytes()
        destination.write_bytes(raw)
        return {"bytes": len(raw), "sha256": "sha256:" + sha256(raw).hexdigest()}

    service = _ExportService()
    result = await export_step63_adapter(
        service=service,
        output=tmp_path / "export",
        archive_url_downloader=download,
    )
    assert result["sampler_deleted"] is True
    assert result["tensor_inventory"]["tensor_count"] == 1
    assert result["base"]["revision"] == BASE_REVISION
    assert service.calls[-1] == "delete:tinker://run-63/sampler_weights/phase6"
    assert json.loads((tmp_path / "export/export-receipt.json").read_bytes()) == result


@pytest.mark.asyncio
async def test_exact_fifteen_variant_external_policy_gate_is_sixty_one_shot_ticks(
    tmp_path: Path,
) -> None:
    result = await qualify_frozen_variants(
        policy_factory=lambda variant: ScriptedIntentPolicy(_intents(variant)),
        output=tmp_path / "qualification",
    )

    assert result["successful"] is True
    assert result["all_fifteen_passed"] is True
    assert result["decision_count"] == 60
    assert len(result["rows"]) == 15
    assert len(result["first_passing_whole_variant"]) == 5
    assert all(row["passed_whole_variant"] for row in result["rows"])
    assert all(row["film_replay_sha256"].startswith("sha256:") for row in result["rows"])
    checked = (tmp_path / "qualification/qualification-receipt.json").read_bytes()
    assert checked == canonical_artifact_bytes(result)


@pytest.mark.asyncio
async def test_external_policy_waits_for_real_response_without_virtual_spinout(
    tmp_path: Path,
) -> None:
    variant = next(item for item in build_demo_variants() if item.hero is HeroBehavior.IDLE)
    policy = _GatedIntentPolicy(_intents(variant))
    task = asyncio.create_task(run_demo_variant(variant, tmp_path / "delayed", policy=policy))
    await policy.entered.wait()
    await asyncio.sleep(0)
    assert not task.done()
    policy.release.set()
    result = await task
    assert result.policy_call_count == 1
    assert result.action_types == ()


@pytest.mark.asyncio
async def test_failed_tick_fails_the_whole_gate_without_retry(tmp_path: Path) -> None:
    with pytest.raises(Phase6GateError, match="lacked a whole pass"):
        await qualify_frozen_variants(
            policy_factory=lambda _variant: ScriptedIntentPolicy(
                [{"type": "idle", "reason": "no_trigger", "related": None}]
            ),
            output=tmp_path / "failed",
        )
    receipt = json.loads((tmp_path / "failed/qualification-receipt.json").read_bytes())
    assert receipt["successful"] is False
    assert receipt["no_retry_resample_repair_substitution_or_stitching"] is True
    assert len(receipt["rows"]) == 15


@pytest.mark.asyncio
async def test_later_variant_can_qualify_behavior_without_erasing_failed_take(
    tmp_path: Path,
) -> None:
    def policy(variant):
        intents = list(_intents(variant))
        if variant.hero is HeroBehavior.LOOKUP and variant.variant == 1:
            intents[-1] = {"type": "idle", "reason": "no_trigger", "related": None}
        return ScriptedIntentPolicy(intents)

    result = await qualify_frozen_variants(
        policy_factory=policy,
        output=tmp_path / "mixed",
    )
    failed = next(
        row for row in result["rows"] if row["scenario_id"].endswith("lookup_then_integrate-v1")
    )
    assert failed["passed_whole_variant"] is False
    assert result["all_fifteen_passed"] is False
    assert result["successful"] is True
    assert result["decision_count"] == 60
    assert result["first_passing_whole_variant"][HeroBehavior.LOOKUP.value].endswith("v2")


@pytest.mark.asyncio
async def test_qualification_cancellation_escapes_immediately_for_outer_teardown(
    tmp_path: Path,
) -> None:
    class CancelPolicy:
        decision_format = "policy_intent_v1"
        call_count = 0

        async def decide(self, _policy_bytes: bytes):
            self.call_count += 1
            raise PolicyCallCancelled(
                (
                    PolicyCallTrace(
                        attempt_index=1,
                        model="phase3x-step63",
                        prompt_hash="sha256:" + "0" * 64,
                        request=b"request",
                        response=b"",
                        latency_ms=1,
                        http_status=None,
                        outcome="cancelled",
                    ),
                )
            )

    with pytest.raises(asyncio.CancelledError):
        await qualify_frozen_variants(
            policy_factory=lambda _variant: CancelPolicy(),
            output=tmp_path / "cancelled",
        )
    assert not (tmp_path / "cancelled/qualification-receipt.json").exists()


@pytest.mark.asyncio
async def test_tinker_semantic_policy_uses_frozen_chat_prefix_and_terminal_framing() -> None:
    class Renderer:
        def build_generation_prompt(self, messages):
            assert messages == [
                {"role": "system", "content": "system"},
                {"role": "user", "content": "state"},
            ]
            return SimpleNamespace(to_ints=lambda: [10, 11])

    class Tokenizer:
        def decode(self, tokens, *, skip_special_tokens=False):
            assert skip_special_tokens is False
            if list(tokens) == [7, TERMINAL_TOKEN_ID]:
                return '{"type":"idle","reason":"no_trigger","related":null}' + TERMINAL_MARKER
            if list(tokens) == [7]:
                return '{"type":"idle","reason":"no_trigger","related":null}'
            raise AssertionError(tokens)

    class Sampler:
        async def sample_async(self, **kwargs):
            assert kwargs["prompt"].to_ints() == [10, 11]
            assert kwargs["num_samples"] == 1
            return SimpleNamespace(
                sequences=[SimpleNamespace(tokens=[7, TERMINAL_TOKEN_ID], stop_reason="stop")]
            )

    policy = TinkerSemanticPolicy(
        Sampler(), PinnedTokenizer(Tokenizer(), Renderer(), {}), "system", "sampler"
    )
    decision = await policy.decide(b"state")
    assert policy.call_count == 1
    assert decision.parser_input_bytes == (b'{"type":"idle","reason":"no_trigger","related":null}')
    assert decision.parser_input_binding == "authenticated_terminal_framing"
    assert decision.calls[0].outcome == "completed"


@pytest.mark.asyncio
async def test_tinker_qualification_deletes_sampler_and_preserves_step63(
    tmp_path: Path, monkeypatch
) -> None:
    import im.generation.phase6_gate as gate

    calls: list[str] = []
    tokenizer = object()
    (tmp_path / "spec").mkdir()
    (tmp_path / "spec/phase3x-policy-intent-prompt-v1.txt").write_text("system")

    class Client:
        async def save_weights_for_sampler_async(self, name, *, ttl_seconds):
            assert (name, ttl_seconds) == ("phase6-film-qualification", 3600)
            return SimpleNamespace(path="tinker://temporary")

    class Service:
        def __init__(self, **_kwargs):
            pass

        def create_rest_client(self):
            return object()

        async def create_training_client_from_state_async(self, *_args, **_kwargs):
            return Client()

        async def create_sampling_client_async(self, *, model_path):
            assert model_path == "tinker://temporary"
            return object()

    async def weights(_rest, path):
        calls.append(f"weights:{path}")
        return object()

    async def identity(_client, _rest):
        return {"model_id": "run-63"}

    async def qualify(*, policy_factory, output):
        policy = policy_factory(None)
        assert policy.sampler_path == "tinker://temporary"
        output.mkdir()
        return {
            "decision_count": 60,
            "first_passing_whole_variant": {"ordinary_typing_idle": "v1"},
        }

    async def delete(_rest, path):
        calls.append(f"delete:{path}")

    monkeypatch.setattr(gate, "load_pinned_tokenizer", lambda *_args: tokenizer)
    monkeypatch.setattr(gate, "read_tinker_api_key", lambda _path: "secret")
    monkeypatch.setattr(gate.tinker, "ServiceClient", Service)
    monkeypatch.setattr(gate, "_get_weights_info", weights)
    monkeypatch.setattr(gate, "_verify_weights_info", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(gate, "_wait_for_restored_identity", identity)
    monkeypatch.setattr(gate, "qualify_frozen_variants", qualify)
    monkeypatch.setattr(gate, "_delete_sampler", delete)

    output = tmp_path / "output"
    status = await qualify_step63_with_tinker(tmp_path, output)
    assert status["status"] == "complete"
    assert status["sampler_deleted_and_verified_absent"] is True
    assert status["selected_state_preserved"] is True
    assert calls[-2:] == ["delete:tinker://temporary", f"weights:{gate.STEP63_STATE}"]
    assert (output / "SHA256SUMS").is_file()
