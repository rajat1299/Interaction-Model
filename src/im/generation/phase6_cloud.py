"""Frozen GCP command plan and idempotent teardown for the Phase 5/6 gate."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from hashlib import sha256

from im.assets.model import canonical_artifact_bytes

PROJECT = "im-artifacts-20260805"
REGION = "us-central1"
ZONE = "us-central1-b"
RUN_ID = "im-phase56-v2"
VM = f"{RUN_ID}-vm"
NETWORK = f"{RUN_ID}-net"
SUBNET = f"{RUN_ID}-subnet"
ROUTER = f"{RUN_ID}-router"
NAT = f"{RUN_ID}-nat"
ADDRESS = f"{RUN_ID}-nat-ip"
FIREWALL = f"{RUN_ID}-iap-ssh"
CONTAINER = f"{RUN_ID}-vllm"
MACHINE_TYPE = "g4-standard-48"
SPOT_GPU_QUOTA_ID = "PREEMPTIBLE-NVIDIA-RTX-PRO-6000-GPUS-per-project-region"
SPOT_GPU_METRIC = "compute.googleapis.com/preemptible_nvidia_rtx_pro_6000_gpus"
DISK_GIB = 200
MAX_RUNTIME_HOURS = 24
MAX_SPEND_USD = 60.0
NON_COMPUTE_RESERVE_USD = Decimal("4.00")
PRICE_FRESHNESS = timedelta(hours=48)
BASE_MODEL = "Qwen/Qwen3.6-35B-A3B"
BASE_REVISION = "995ad96eacd98c81ed38be0c5b274b04031597b0"
DLVM_IMAGE = "common-cu129-ubuntu-2204-nvidia-580-v20260818"
DLVM_PROJECT = "deeplearning-platform-release"
VLLM_VERSION = "0.25.1"
VLLM_MANIFEST_DIGEST = "sha256:e4f88a835143cd22aee2397a26ec6bb80b3a4a6fe0c882bcbc63822904766089"
VLLM_AMD64_DIGEST = "sha256:f0b9a0dc75a9fca3b6811e3279367b2d6a448055a000bfd13859587d74cef268"
VLLM_MANIFEST_IMAGE = f"vllm/vllm-openai:v{VLLM_VERSION}@{VLLM_MANIFEST_DIGEST}"
VLLM_IMAGE = f"vllm/vllm-openai@{VLLM_AMD64_DIGEST}"
MAX_MODEL_LEN = 65_536
IAP_CIDR = "35.235.240.0/20"
REMOTE_PREPARE = " && ".join(
    (
        "sudo apt-get update",
        (
            "sudo env DEBIAN_FRONTEND=noninteractive apt-get install -y "
            "docker.io nvidia-container-toolkit=1.17.8-1 "
            "nvidia-container-toolkit-base=1.17.8-1 "
            "libnvidia-container-tools=1.17.8-1 libnvidia-container1=1.17.8-1"
        ),
        "sudo nvidia-ctk runtime configure --runtime=docker",
        "sudo systemctl enable --now docker",
        "sudo systemctl restart docker",
        "sudo docker version",
        "sudo mkdir -p /srv/im/base /srv/im/adapter",
        "sudo chown -R $USER /srv/im",
    )
)


class Phase6CloudError(RuntimeError):
    """The frozen cloud command boundary failed closed."""


@dataclass(frozen=True, slots=True)
class CloudCommand:
    command_id: str
    argv: tuple[str, ...]
    mutating: bool
    expect_empty_stdout: bool = False
    allow_failure: bool = False

    def as_json(self) -> dict[str, object]:
        return {
            "allow_failure": self.allow_failure,
            "argv": list(self.argv),
            "command_id": self.command_id,
            "expect_empty_stdout": self.expect_empty_stdout,
            "mutating": self.mutating,
        }


type CommandRunner = Callable[[Sequence[str]], subprocess.CompletedProcess[str]]


def _gcloud(*args: str) -> tuple[str, ...]:
    return ("gcloud", *args, f"--project={PROJECT}", "--quiet")


def termination_time(created_at: datetime) -> str:
    if created_at.tzinfo is None:
        raise ValueError("created_at must be timezone-aware")
    return (
        (created_at.astimezone(UTC) + timedelta(hours=MAX_RUNTIME_HOURS))
        .isoformat()
        .replace("+00:00", "Z")
    )


def _preflight_commands() -> tuple[CloudCommand, ...]:
    label = f"labels.phase6-run={RUN_ID}"
    empty = (
        ("instances", "instances", "list", f"--filter=name={VM}", "--format=value(name)"),
        ("disks", "disks", "list", f"--filter=name={VM}", "--format=value(name)"),
        ("snapshots", "snapshots", "list", f"--filter={label}", "--format=value(name)"),
        ("addresses", "addresses", "list", f"--filter=name={ADDRESS}", "--format=value(name)"),
        ("reservations", "reservations", "list", f"--filter={label}", "--format=value(name)"),
        ("networks", "networks", "list", f"--filter=name={NETWORK}", "--format=value(name)"),
        (
            "subnets",
            "networks",
            "subnets",
            "list",
            f"--filter=name={SUBNET}",
            "--format=value(name)",
        ),
        (
            "firewall-rules",
            "firewall-rules",
            "list",
            f"--filter=name={FIREWALL}",
            "--format=value(name)",
        ),
        (
            "routers",
            "routers",
            "list",
            f"--filter=name={ROUTER}",
            "--format=value(name)",
            f"--regions={REGION}",
        ),
    )
    commands = [
        CloudCommand(
            "dlvm-image",
            (
                "gcloud",
                "compute",
                "images",
                "describe",
                DLVM_IMAGE,
                f"--project={DLVM_PROJECT}",
                "--format=json",
                "--quiet",
            ),
            False,
        ),
        CloudCommand(
            "regional-quota",
            _gcloud("compute", "regions", "describe", REGION, "--format=json"),
            False,
        ),
        CloudCommand(
            "spot-gpu-quota",
            _gcloud(
                "beta",
                "quotas",
                "info",
                "describe",
                SPOT_GPU_QUOTA_ID,
                "--service=compute.googleapis.com",
                "--format=json",
            ),
            False,
        ),
        CloudCommand(
            "machine",
            _gcloud(
                "compute",
                "machine-types",
                "describe",
                MACHINE_TYPE,
                f"--zone={ZONE}",
                "--format=json",
            ),
            False,
        ),
        CloudCommand(
            "capacity",
            _gcloud(
                "beta",
                "compute",
                "advice",
                "capacity",
                "--provisioning-model=SPOT",
                "--size=1",
                f"--instance-selection-machine-types={MACHINE_TYPE}",
                "--target-distribution-shape=any-single-zone",
                f"--region={REGION}",
                f"--zones={ZONE}",
                "--format=json",
            ),
            False,
        ),
        CloudCommand(
            "capacity-price",
            _gcloud(
                "beta",
                "compute",
                "advice",
                "capacity-history",
                "--provisioning-model=SPOT",
                f"--machine-type={MACHINE_TYPE}",
                "--types=PREEMPTION,PRICE",
                f"--region={REGION}",
                "--format=json",
            ),
            False,
        ),
    ]
    commands.extend(
        CloudCommand(f"absent-{name}", _gcloud("compute", *args), False, True)
        for name, *args in empty
    )
    return tuple(commands)


def _remote_setup() -> str:
    return " && ".join(
        (
            f"sudo docker manifest inspect {VLLM_MANIFEST_IMAGE} | grep -F '{VLLM_AMD64_DIGEST}'",
            f"sudo docker pull {VLLM_IMAGE}",
            f"sudo docker run --rm --entrypoint hf {VLLM_IMAGE} --version",
            (
                f"sudo docker run --rm --entrypoint hf -e HF_HUB_DISABLE_XET=1 "
                f"-v /srv/im/base:/base {VLLM_IMAGE} "
                f"download {BASE_MODEL} --revision {BASE_REVISION} --local-dir /base"
            ),
            "test -s /srv/im/adapter/adapter_config.json",
            "find /srv/im/adapter -type f -name '*.safetensors' -print -quit | grep -q .",
            (
                f"sudo docker run -d --name {CONTAINER} --gpus all --ipc=host --network=host "
                "-v /srv/im/base:/models/base:ro -v /srv/im/adapter:/models/adapter:ro "
                f"{VLLM_IMAGE} --model /models/base --served-model-name phase3x-base "
                "--host 127.0.0.1 --port 8000 --generation-config vllm --language-model-only "
                "--enable-lora --max-loras 1 --max-lora-rank 16 "
                "--lora-modules phase3x-step63=/models/adapter "
                f"--tensor-parallel-size 1 --max-model-len {MAX_MODEL_LEN} --max-num-seqs 16 "
                "--gpu-memory-utilization 0.90"
            ),
        )
    )


def launch_commands(created_at: datetime, adapter_path: str) -> tuple[CloudCommand, ...]:
    deadline = termination_time(created_at)
    commands = [
        *_preflight_commands(),
        CloudCommand(
            "network-create",
            _gcloud("compute", "networks", "create", NETWORK, "--subnet-mode=custom"),
            True,
        ),
        CloudCommand(
            "subnet-create",
            _gcloud(
                "compute",
                "networks",
                "subnets",
                "create",
                SUBNET,
                f"--network={NETWORK}",
                f"--region={REGION}",
                "--range=10.42.0.0/28",
                "--enable-private-ip-google-access",
            ),
            True,
        ),
        CloudCommand(
            "router-create",
            _gcloud(
                "compute", "routers", "create", ROUTER, f"--network={NETWORK}", f"--region={REGION}"
            ),
            True,
        ),
        CloudCommand(
            "address-create",
            _gcloud(
                "compute",
                "addresses",
                "create",
                ADDRESS,
                f"--region={REGION}",
                "--network-tier=PREMIUM",
            ),
            True,
        ),
        CloudCommand(
            "nat-create",
            _gcloud(
                "compute",
                "routers",
                "nats",
                "create",
                NAT,
                f"--router={ROUTER}",
                f"--region={REGION}",
                f"--nat-external-ip-pool={ADDRESS}",
                "--nat-all-subnet-ip-ranges",
            ),
            True,
        ),
        CloudCommand(
            "firewall-create",
            _gcloud(
                "compute",
                "firewall-rules",
                "create",
                FIREWALL,
                f"--network={NETWORK}",
                "--direction=INGRESS",
                "--action=ALLOW",
                "--rules=tcp:22",
                f"--source-ranges={IAP_CIDR}",
                f"--target-tags={RUN_ID}",
            ),
            True,
        ),
        CloudCommand(
            "vm-create",
            _gcloud(
                "compute",
                "instances",
                "create",
                VM,
                f"--zone={ZONE}",
                f"--machine-type={MACHINE_TYPE}",
                "--provisioning-model=SPOT",
                "--instance-termination-action=DELETE",
                f"--termination-time={deadline}",
                "--no-restart-on-failure",
                "--maintenance-policy=TERMINATE",
                f"--boot-disk-size={DISK_GIB}GB",
            "--boot-disk-type=hyperdisk-balanced",
                "--boot-disk-auto-delete",
                f"--image={DLVM_IMAGE}",
                f"--image-project={DLVM_PROJECT}",
                f"--network-interface=network={NETWORK},subnet={SUBNET},no-address",
                "--no-service-account",
                "--no-scopes",
                f"--tags={RUN_ID}",
                f"--labels=phase6-run={RUN_ID}",
            ),
            True,
        ),
        CloudCommand("vm-stabilize", ("sleep", "60"), False),
        CloudCommand(
            "remote-prepare",
            _gcloud(
                "compute",
                "ssh",
                VM,
                f"--zone={ZONE}",
                "--tunnel-through-iap",
                f"--command={REMOTE_PREPARE}",
            ),
            True,
        ),
        CloudCommand(
            "adapter-copy",
            _gcloud(
                "compute",
                "scp",
                adapter_path,
                f"{VM}:/srv/im/",
                f"--zone={ZONE}",
                "--tunnel-through-iap",
                "--recurse",
            ),
            True,
        ),
        CloudCommand(
            "vllm-start",
            _gcloud(
                "compute",
                "ssh",
                VM,
                f"--zone={ZONE}",
                "--tunnel-through-iap",
                f"--command={_remote_setup()}",
            ),
            True,
        ),
    ]
    return tuple(commands)


def tunnel_command() -> CloudCommand:
    return CloudCommand(
        "iap-tunnel",
        (
            "gcloud",
            "compute",
            "ssh",
            VM,
            f"--zone={ZONE}",
            "--tunnel-through-iap",
            f"--project={PROJECT}",
            "--quiet",
            "--",
            "-N",
            "-L",
            "8000:localhost:8000",
        ),
        True,
    )


def evidence_commands() -> tuple[CloudCommand, ...]:
    """Capture the exact live resource and detached serving log before teardown."""
    return (
        CloudCommand(
            "resource-receipt",
            _gcloud("compute", "instances", "describe", VM, f"--zone={ZONE}", "--format=json"),
            False,
        ),
        CloudCommand(
            "vllm-detached-log",
            _gcloud(
                "compute",
                "ssh",
                VM,
                f"--zone={ZONE}",
                "--tunnel-through-iap",
                f"--command=sudo docker logs {CONTAINER}",
            ),
            False,
        ),
    )


def teardown_commands() -> tuple[CloudCommand, ...]:
    commands = (
        (
            "container-delete",
            (
                "ssh",
                VM,
                f"--zone={ZONE}",
                "--tunnel-through-iap",
                f"--command=sudo docker rm -f {CONTAINER}",
            ),
        ),
        ("vm-delete", ("instances", "delete", VM, f"--zone={ZONE}")),
        ("firewall-delete", ("firewall-rules", "delete", FIREWALL)),
        (
            "nat-delete",
            ("routers", "nats", "delete", NAT, f"--router={ROUTER}", f"--region={REGION}"),
        ),
        ("address-delete", ("addresses", "delete", ADDRESS, f"--region={REGION}")),
        ("router-delete", ("routers", "delete", ROUTER, f"--region={REGION}")),
        (
            "subnet-delete",
            ("networks", "subnets", "delete", SUBNET, f"--region={REGION}"),
        ),
        ("network-delete", ("networks", "delete", NETWORK)),
    )
    return tuple(
        CloudCommand(command_id, _gcloud("compute", *args), True, allow_failure=True)
        for command_id, args in commands
    )


def absence_commands() -> tuple[CloudCommand, ...]:
    return tuple(command for command in _preflight_commands() if command.expect_empty_stdout)


def execute_commands(
    commands: Sequence[CloudCommand],
    runner: CommandRunner,
    receipts: list[dict[str, object]] | None = None,
) -> list[dict[str, object]]:
    recorded = [] if receipts is None else receipts
    for command in commands:
        completed = runner(command.argv)
        receipt = {
            "argv_sha256": (
                f"sha256:{sha256(canonical_artifact_bytes(list(command.argv))).hexdigest()}"
            ),
            "command_id": command.command_id,
            "returncode": completed.returncode,
            "stderr_sha256": f"sha256:{sha256(completed.stderr.encode()).hexdigest()}",
            "stdout_sha256": f"sha256:{sha256(completed.stdout.encode()).hexdigest()}",
        }
        recorded.append(receipt)
        if completed.returncode and not command.allow_failure:
            raise Phase6CloudError(f"cloud command failed: {command.command_id}")
        if (
            command.command_id
            in {
                "dlvm-image",
                "regional-quota",
                "spot-gpu-quota",
                "machine",
                "capacity",
                "capacity-price",
            }
            and not completed.stdout.strip()
        ):
            raise Phase6CloudError(f"cloud preflight returned no evidence: {command.command_id}")
        if command.command_id in {
            "dlvm-image",
            "regional-quota",
            "spot-gpu-quota",
            "machine",
            "capacity",
            "capacity-price",
        }:
            _validate_preflight(command.command_id, completed.stdout)
        if command.expect_empty_stdout and completed.stdout.strip():
            raise Phase6CloudError(f"frozen resource already exists: {command.command_id}")
    return recorded


def _validate_preflight(command_id: str, stdout: str) -> None:
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as error:
        raise Phase6CloudError(f"cloud preflight is not JSON: {command_id}") from error
    if command_id == "dlvm-image":
        expected_link = (
            f"https://www.googleapis.com/compute/v1/projects/{DLVM_PROJECT}/global/images/"
            f"{DLVM_IMAGE}"
        )
        if not isinstance(payload, dict) or (
            payload.get("name"),
            payload.get("status"),
            payload.get("selfLink"),
        ) != (DLVM_IMAGE, "READY", expected_link):
            raise Phase6CloudError("DLVM image identity or readiness drifted")
        return
    if command_id == "machine":
        if not isinstance(payload, dict) or (
            payload.get("name"),
            payload.get("guestCpus"),
            payload.get("memoryMb"),
        ) != (MACHINE_TYPE, 48, 184_320):
            raise Phase6CloudError("G4 machine shape drifted")
        return
    if command_id == "capacity-price":
        if not isinstance(payload, dict) or payload.get("machineType") != MACHINE_TYPE:
            raise Phase6CloudError("Capacity Advisor price evidence targets the wrong machine")
        prices = payload.get("priceHistory")
        preemptions = payload.get("preemptionHistory")
        if not isinstance(prices, list) or not prices or not isinstance(preemptions, list):
            raise Phase6CloudError("Capacity Advisor price/preemption evidence is malformed")
        if any(
            not isinstance(row, dict) or not isinstance(row.get("interval"), dict)
            for row in prices
        ):
            raise Phase6CloudError("Capacity Advisor price history is malformed")
        timestamped = []
        for row in prices:
            raw_end = row["interval"].get("endTime")
            try:
                parsed_end = datetime.fromisoformat(str(raw_end).replace("Z", "+00:00"))
            except ValueError as error:
                raise Phase6CloudError("Capacity Advisor price timestamp is malformed") from error
            if "T" not in str(raw_end) or parsed_end.tzinfo is None:
                raise Phase6CloudError("Capacity Advisor price timestamp is malformed")
            timestamped.append((parsed_end.astimezone(UTC), row))
        now = datetime.now(UTC)
        latest_at, latest = max(timestamped, key=lambda pair: pair[0])
        if not now - PRICE_FRESHNESS <= latest_at <= now + PRICE_FRESHNESS:
            raise Phase6CloudError("Capacity Advisor current price is stale")
        money = latest.get("listPrice") if isinstance(latest, dict) else None
        if not isinstance(money, dict) or money.get("currencyCode") != "USD":
            raise Phase6CloudError("Capacity Advisor price is not USD")
        try:
            hourly = Decimal(str(money.get("units", "0"))) + (
                Decimal(str(money.get("nanos", "0"))) / Decimal(1_000_000_000)
            )
        except (InvalidOperation, TypeError, ValueError) as error:
            raise Phase6CloudError("Capacity Advisor price is malformed") from error
        projected = hourly * MAX_RUNTIME_HOURS + NON_COMPUTE_RESERVE_USD
        if hourly <= 0 or projected > Decimal(str(MAX_SPEND_USD)):
            raise Phase6CloudError("Capacity Advisor price exceeds the frozen spend ceiling")
        return
    if command_id == "capacity":
        recommendations = payload.get("recommendations") if isinstance(payload, dict) else None
        if not isinstance(recommendations, list):
            raise Phase6CloudError("Capacity Advisor availability evidence is malformed")
        matching = [
            shard
            for recommendation in recommendations
            for shard in (
                recommendation.get("shards", [])
                if isinstance(recommendation, dict)
                and isinstance(recommendation.get("shards"), list)
                else ()
            )
            if isinstance(shard, dict)
            and str(shard.get("zone", "")).rsplit("/", 1)[-1] == ZONE
            and str(shard.get("machineType", "")).rsplit("/", 1)[-1] == MACHINE_TYPE
            and shard.get("provisioningModel") == "SPOT"
            and isinstance(shard.get("instanceCount"), int)
            and not isinstance(shard["instanceCount"], bool)
            and shard["instanceCount"] >= 1
        ]
        if not matching:
            raise Phase6CloudError("Capacity Advisor found no matching Spot capacity")
        return
    if command_id == "spot-gpu-quota":
        if not isinstance(payload, dict) or (
            payload.get("quotaId"),
            payload.get("service"),
            payload.get("metric"),
            payload.get("isPrecise"),
        ) != (
            SPOT_GPU_QUOTA_ID,
            "compute.googleapis.com",
            SPOT_GPU_METRIC,
            True,
        ):
            raise Phase6CloudError("Spot GPU quota identity is malformed")
        rows = payload.get("dimensionsInfos")
        if not isinstance(rows, list):
            raise Phase6CloudError("Spot GPU quota dimensions are malformed")
        matches = [
            row
            for row in rows
            if isinstance(row, dict)
            and isinstance(row.get("applicableLocations"), list)
            and REGION in row["applicableLocations"]
            and isinstance(row.get("dimensions", {}), dict)
            and isinstance(row.get("details"), dict)
        ]
        if not matches:
            raise Phase6CloudError("Spot GPU quota does not apply to the frozen region")
        specificity = max(len(row.get("dimensions", {})) for row in matches)
        selected = [row for row in matches if len(row.get("dimensions", {})) == specificity]
        if len(selected) != 1:
            raise Phase6CloudError("Spot GPU quota dimensions are ambiguous")
        value = selected[0]["details"].get("value")
        if isinstance(value, bool) or not isinstance(value, (int, str)):
            raise Phase6CloudError("Spot GPU quota value is malformed")
        try:
            available_gpu = int(value)
        except ValueError as error:
            raise Phase6CloudError("Spot GPU quota value is malformed") from error
        if available_gpu < 1:
            raise Phase6CloudError("Spot GPU quota is insufficient")
        return
    rows = payload.get("quotas") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        raise Phase6CloudError("regional quota evidence is malformed")
    try:
        available = {
            row.get("metric"): float(row.get("limit", 0)) - float(row.get("usage", 0))
            for row in rows
            if isinstance(row, dict)
        }
    except (TypeError, ValueError) as error:
        raise Phase6CloudError("regional quota values are malformed") from error
    required = {
        "SSD_TOTAL_GB": DISK_GIB,
        "PREEMPTIBLE_CPUS": 48,
    }
    if any(available.get(metric, -1) < amount for metric, amount in required.items()):
        raise Phase6CloudError("regional CPU/disk quota is insufficient")


def plan_object(source_commit: str) -> dict[str, object]:
    placeholder = datetime(2026, 1, 1, tzinfo=UTC)
    return {
        "base_model": {"id": BASE_MODEL, "revision": BASE_REVISION},
        "commands": [
            command.as_json()
            for command in launch_commands(placeholder, "<authorized-step63-adapter-directory>")
        ],
        "cost": {
            "estimated_usd": 47.2,
            "hard_ceiling_usd": MAX_SPEND_USD,
            "includes_24h_nat_gateway_ip_and_20gib_processing": True,
        },
        "dlvm": {
            "image": DLVM_IMAGE,
            "project": DLVM_PROJECT,
            "required_status": "READY",
        },
        "format_version": "phase5-6-cloud-command-plan-v14",
        "max_runtime_hours": MAX_RUNTIME_HOURS,
        "project": PROJECT,
        "source_commit": source_commit,
        "teardown": [command.as_json() for command in teardown_commands()],
        "tunnel": tunnel_command().as_json(),
        "vllm": {
            "amd64_digest": VLLM_AMD64_DIGEST,
            "linux_amd64_image": VLLM_IMAGE,
            "manifest_image": VLLM_MANIFEST_IMAGE,
            "language_model_only": True,
            "max_model_len": MAX_MODEL_LEN,
            "version": VLLM_VERSION,
        },
        "zone": ZONE,
    }


def plan_bytes(source_commit: str) -> bytes:
    return canonical_artifact_bytes(plan_object(source_commit))


def default_runner(argv: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(list(argv), check=False, capture_output=True, text=True, timeout=1_800)


def receipt_bytes(value: object) -> bytes:
    return canonical_artifact_bytes(value)


def parse_receipt(raw: bytes) -> object:
    return json.loads(raw)
