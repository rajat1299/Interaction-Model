"""Single authorized Phase 5/6 adapter, cloud, qualification, and teardown gate."""

from __future__ import annotations

import asyncio
import inspect
import json
import os
import subprocess
import tarfile
import time
import zipfile
from collections.abc import Callable, Mapping
from hashlib import sha256
from pathlib import Path
from typing import Any

import httpx
import tinker
from safetensors import safe_open

from im.assets.model import canonical_artifact_bytes
from im.generation.demo_scenes import (
    DemoVariant,
    HeroBehavior,
    build_demo_variants,
    hero_contract,
    run_demo_variant,
)
from im.generation.phase6_cloud import (
    BASE_MODEL,
    BASE_REVISION,
    DLVM_IMAGE,
    DLVM_PROJECT,
    MAX_RUNTIME_HOURS,
    MAX_SPEND_USD,
    PROJECT,
    RUN_ID,
    VLLM_AMD64_DIGEST,
    VLLM_MANIFEST_DIGEST,
    plan_bytes,
)
from im.policy.base import (
    Policy,
    PolicyCallCancelled,
    PolicyCallError,
    PolicyCallTrace,
    PolicyDecision,
)
from im.training import phase3_data
from im.training.phase3_data import PinnedTokenizer, load_pinned_tokenizer
from im.training.phase3_framing import TERMINAL_TOKEN_ID, project_terminal_output
from im.training.phase3_sampling import read_tinker_api_key
from im.training.phase3_tinker import (
    Phase3TinkerError,
    _verify_info,
    _verify_weights_info,
    _weights_evidence,
)
from im.training.phase3r_negative_controls import (
    _download,
    _get_weights_info,
    _verify_archive_members,
)

STEP63_STATE = "tinker://033dbe01-6de4-5262-9e93-4a4761dafa74:train:0/weights/phase3x-state-63"
REJECTED_V1_SHA256SUMS = "sha256:e2386482c449d4637ea8933585bda520c4316b3ccd1749d94e42363f19de5ea1"
REJECTED_V2_SHA256SUMS = "sha256:9fa0aff845c6d85c9e2105d72210e16d59ee311f1187ba30923b5a830bccf08d"
REJECTED_V3_SHA256SUMS = "sha256:f3e570f3de66bb82c49f0db31f289de089f6fa6855c4e9f2c88f4727a1643a7e"
REJECTED_V4_SHA256SUMS = "sha256:e5e34a5387a977a720c01cf1a6327bb3c2b543d7be0e3c8020d0015d01fa2f0f"
REJECTED_V4_RUN_SHA256SUMS = (
    "sha256:05c392fa5a821539c3d19d15313fe1b0bd70e2b41fc7b4f4faec1e2e13b1a714"
)
REJECTED_V5_SHA256SUMS = "sha256:46a5af2e354b46b311b1a154af0910b83fd10e9be986cedfc00043bb5e2dc039"
REJECTED_V5_RUN_SHA256SUMS = (
    "sha256:c0c8ac8f9e42579e19c56ff28c7cfd8631b1f0c7123cc7628fa6c0781b16c1b0"
)
REJECTED_V6_SHA256SUMS = "sha256:f82803dbca6e553f023191c2eb9edc84b8ec8957c14917d7e14257e640e152f8"
REJECTED_V6_RUN_SHA256SUMS = (
    "sha256:a721396139406cc8ce8209ee79d85124d4d68a1b420925e815067da7455689ae"
)
REJECTED_V7_SHA256SUMS = "sha256:2b8ad59bcdfbbf1b4aea7900a8fd970bbd6ef608fd96770f06fbc8561eaa2289"
REJECTED_V7_RUN_SHA256SUMS = (
    "sha256:43673009f886121195d96aef10d890baa0afb6249ffbb2b12f475891f77f721d"
)
REJECTED_V8_SHA256SUMS = "sha256:f6a9e27133c11ae282629675608a4b9e9ea4c7780038b69926cec4b9fb690f4f"
REJECTED_V8_RUN_SHA256SUMS = (
    "sha256:dcbf9f7479b1af6c6482510dd961e8f38f297b6e147922689e0f4e7394cd9bd6"
)
REJECTED_V9_SHA256SUMS = "sha256:d851521e2a374af055ee455ad4674d8effa7998824b2691469fd11252dd84d30"
REJECTED_V9_RUN_SHA256SUMS = (
    "sha256:3f873b5d5b297eb1c0371e049e044e0b9b32d44fdfe48c1f41d90fb17717a183"
)
REJECTED_V10_SHA256SUMS = "sha256:3b16d2010ceb9fde1ce9cd2e26d44484373943c9ca7b5050557c5b05611696de"
REJECTED_V10_RUN_SHA256SUMS = (
    "sha256:6d4e3aad9d0ef2d1ac5f650589b01959661be9181ebb014a0cc1ae2b9ee2089d"
)
REJECTED_V11_SHA256SUMS = "sha256:feb6e724b68e69c0167386fbe5879cad4b8608075cbbe72a35d955dcaf7e36b0"
REJECTED_V11_RUN_SHA256SUMS = (
    "sha256:9b9305086798c4a9a404e53a2746beae5f8798b0a460b47369a41d77a5c6442c"
)
REJECTED_V12_SHA256SUMS = "sha256:1c806a16d8339ad2574b681cec70bd6b6e2f13354e067dd7ff812c7973476991"
REJECTED_V12_RUN_SHA256SUMS = (
    "sha256:93790b10171b8d4cadaf7fa6d655725121c0fe98086daba6937d04c0c578d54c"
)
REJECTED_V12_TEARDOWN_SHA256SUMS = (
    "sha256:64ff7c1c2cdb16551b17dc6eb41e5c4da0baab57a8c76873e47394e9f1c0ef4d"
)
REJECTED_V13_SHA256SUMS = "sha256:435ef3fdd9231373c9bd20d0404959c33415a68bd6e2863d2e2105992b4a54c4"
REJECTED_V13_RUN_SHA256SUMS = (
    "sha256:9fb33344e08aed0cd8d86cb01ce7e81cc949839ff9641e75c37127c1ece7f390"
)
REJECTED_V13_TEARDOWN_SHA256SUMS = (
    "sha256:fa3c4921f2a27534e88e60f0c1c75e06815bdd3276d6e15461744e6567e4bc71"
)
V5_EXECUTION_RELATIVE = Path("review/phase6/wp6-2-frozen-execution-v5")
V6_EXECUTION_RELATIVE = Path("review/phase6/wp6-2-frozen-execution-v6")
V7_EXECUTION_RELATIVE = Path("review/phase6/wp6-2-frozen-execution-v7")
V8_EXECUTION_RELATIVE = Path("review/phase6/wp6-2-frozen-execution-v8")
V9_EXECUTION_RELATIVE = Path("review/phase6/wp6-2-frozen-execution-v9")
V10_EXECUTION_RELATIVE = Path("review/phase6/wp6-2-frozen-execution-v10")
V11_EXECUTION_RELATIVE = Path("review/phase6/wp6-2-frozen-execution-v11")
V12_EXECUTION_RELATIVE = Path("review/phase6/wp6-2-frozen-execution-v12")
V13_EXECUTION_RELATIVE = Path("review/phase6/wp6-2-frozen-execution-v13")
SAMPLER_TTL_SECONDS = 3_600
PACKAGE_RELATIVE = Path("review/phase6/wp6-1-consolidated-execution-v14")
AUTHORIZATION_NAME = "owner-authorization-v14.json"
AUTHORIZATION_CLAIM_NAME = "owner-authorization-v14.claim.json"
EXECUTION_OUTPUT_RELATIVE = Path("review/phase6/wp6-2-frozen-execution-v14")
TEARDOWN_OUTPUT_RELATIVE = Path("review/phase6/wp6-2-teardown-recovery-v14")
TINKER_QUALIFICATION_OUTPUT_RELATIVE = Path("review/phase6/wp6-2-tinker-qualification-v1")
TEMPLATE_NAME = "owner-authorization-template-v14.json"
FIXED_PACKAGE_FILES = (
    "README.md",
    "cloud-command-plan-v14.json",
    "execution-manifest-v14.json",
    "model-card-v14.md",
    "release-inventory-v14.json",
    TEMPLATE_NAME,
)
GUARDED_SOURCE_FILES = (
    "client/public/source-serif-4-LICENSE.md",
    "client/src/assets/source-serif-4-variable-roman.woff2",
    "client/src/film.css",
    "client/src/film.test.ts",
    "client/src/film.ts",
    "scripts/run_phase6_gate.py",
    "src/im/generation/demo_scenes.py",
    "src/im/generation/phase6_cloud.py",
    "src/im/generation/phase6_gate.py",
    "src/im/generation/runtime.py",
    "src/im/policy/vllm_semantic.py",
    "tests/test_phase6_gate.py",
)


class Phase6GateError(RuntimeError):
    """The consolidated gate failed closed."""


def _digest(raw: bytes) -> str:
    return f"sha256:{sha256(raw).hexdigest()}"


def _file_digest(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(8 * 1024 * 1024):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def write_create_only(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def checksum_inventory(files: Mapping[str, bytes]) -> bytes:
    return "".join(
        f"{sha256(raw).hexdigest()}  {name}\n" for name, raw in sorted(files.items())
    ).encode()


def authorization_template(source_commit: str, package_sha256sums: str) -> dict[str, object]:
    """Return the only authorization accepted by the executable gate."""
    return {
        "adapter": {"state": STEP63_STATE, "step": 63, "restore": "weights_only"},
        "authorized_operations": [
            "reuse_checksum_verified_v5_step63_adapter_export",
            "run_read_only_gcp_dlvm_quota_capacity_price_preflights",
            "create_one_frozen_private_spot_vm_and_run_scoped_nat",
            "serve_exact_base_and_static_lora_over_iap_loopback",
            "run_fifteen_frozen_qualitative_variants_once",
            "record_first_whole_passing_variant_per_behavior_and_film",
            "retrieve_checksum_bound_evidence_and_teardown_every_run_resource",
        ],
        "base": {"model": BASE_MODEL, "revision": BASE_REVISION},
        "cloud": {
            "max_hours": MAX_RUNTIME_HOURS,
            "max_spend_usd": MAX_SPEND_USD,
            "project": PROJECT,
            "run_id": RUN_ID,
            "vm_count": 1,
            "relaunch": False,
            "dlvm_image": DLVM_IMAGE,
            "dlvm_project": DLVM_PROJECT,
        },
        "format_version": "phase5-6-owner-authorization-v14",
        "no_training_mining_dpo_test_resampling": True,
        "owner_decision": "DENY_REPLACE_WITH_AUTHORIZED",
        "package_sha256sums_sha256": package_sha256sums,
        "sealed_test_content_access": "forbidden",
        "source_commit": source_commit,
        "vllm": {
            "linux_amd64_digest": VLLM_AMD64_DIGEST,
            "manifest_digest": VLLM_MANIFEST_DIGEST,
            "no_retry_or_fallback": True,
            "hf_entrypoint": "hf",
            "hf_version_preflight": True,
        },
    }


def _read_object(path: Path) -> dict[str, object]:
    try:
        raw = path.read_bytes()
        value = json.loads(raw)
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as error:
        raise Phase6GateError(f"invalid JSON object: {path}") from error
    if not isinstance(value, dict) or canonical_artifact_bytes(value) != raw:
        raise Phase6GateError(f"noncanonical JSON object: {path}")
    return value


def verify_package(root: Path, package: Path) -> str:
    """Verify the fixed package before an authorization or secret is read."""
    expected = (root / PACKAGE_RELATIVE).resolve()
    if package.resolve() != expected:
        raise Phase6GateError("execution package path is not the frozen v14 path")
    lines = (package / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
    names: list[str] = []
    for line in lines:
        parts = line.split("  ", 1)
        if len(parts) != 2 or len(parts[0]) != 64:
            raise Phase6GateError("package checksum inventory is malformed")
        digest, name = parts
        names.append(name)
        if sha256((package / name).read_bytes()).hexdigest() != digest:
            raise Phase6GateError(f"package checksum mismatch: {name}")
    if tuple(names) != tuple(sorted(FIXED_PACKAGE_FILES)):
        raise Phase6GateError("package checksum inventory is incomplete")
    return _file_digest(package / "SHA256SUMS")


def verify_source(root: Path, source_commit: str) -> None:
    """Require clean tracked bytes and only the reviewed v14 package after the source commit."""
    commands = (
        ("rev-parse", "HEAD"),
        ("merge-base", "--is-ancestor", source_commit, "HEAD"),
        ("diff", "--quiet"),
        ("diff", "--cached", "--quiet"),
        (
            "status",
            "--porcelain",
            "--untracked-files=all",
            "--",
            ".",
            ":(exclude)review/phase3/**",
            ":(exclude)review/phase4/**",
            f":(exclude){(PACKAGE_RELATIVE / AUTHORIZATION_NAME).as_posix()}",
            f":(exclude){(PACKAGE_RELATIVE / AUTHORIZATION_CLAIM_NAME).as_posix()}",
            f":(exclude){EXECUTION_OUTPUT_RELATIVE.as_posix()}/**",
            ":(exclude)review/phase6/wp6-1-consolidated-execution-v4/owner-authorization-v4.json",
            ":(exclude)review/phase6/wp6-1-consolidated-execution-v4/owner-authorization-v4.claim.json",
            ":(exclude)review/phase6/wp6-2-frozen-execution-v4/**",
            ":(exclude)review/phase6/wp6-1-consolidated-execution-v5/owner-authorization-v5.json",
            ":(exclude)review/phase6/wp6-1-consolidated-execution-v5/owner-authorization-v5.claim.json",
            ":(exclude)review/phase6/wp6-2-frozen-execution-v5/**",
            ":(exclude)review/phase6/wp6-1-consolidated-execution-v6/owner-authorization-v6.json",
            ":(exclude)review/phase6/wp6-1-consolidated-execution-v6/owner-authorization-v6.claim.json",
            ":(exclude)review/phase6/wp6-2-frozen-execution-v6/**",
            ":(exclude)review/phase6/wp6-1-consolidated-execution-v7/owner-authorization-v7.json",
            ":(exclude)review/phase6/wp6-1-consolidated-execution-v7/owner-authorization-v7.claim.json",
            ":(exclude)review/phase6/wp6-2-frozen-execution-v7/**",
            ":(exclude)review/phase6/wp6-1-consolidated-execution-v8/owner-authorization-v8.json",
            ":(exclude)review/phase6/wp6-1-consolidated-execution-v8/owner-authorization-v8.claim.json",
            ":(exclude)review/phase6/wp6-2-frozen-execution-v8/**",
            ":(exclude)review/phase6/wp6-1-consolidated-execution-v9/owner-authorization-v9.json",
            ":(exclude)review/phase6/wp6-1-consolidated-execution-v9/owner-authorization-v9.claim.json",
            ":(exclude)review/phase6/wp6-2-frozen-execution-v9/**",
            ":(exclude)review/phase6/wp6-1-consolidated-execution-v10/owner-authorization-v10.json",
            ":(exclude)review/phase6/wp6-1-consolidated-execution-v10/owner-authorization-v10.claim.json",
            ":(exclude)review/phase6/wp6-2-frozen-execution-v10/**",
            ":(exclude)review/phase6/wp6-1-consolidated-execution-v11/owner-authorization-v11.json",
            ":(exclude)review/phase6/wp6-1-consolidated-execution-v11/owner-authorization-v11.claim.json",
            ":(exclude)review/phase6/wp6-2-frozen-execution-v11/**",
            ":(exclude)review/phase6/wp6-1-consolidated-execution-v12/owner-authorization-v12.json",
            ":(exclude)review/phase6/wp6-1-consolidated-execution-v12/owner-authorization-v12.claim.json",
            ":(exclude)review/phase6/wp6-2-frozen-execution-v12/**",
            ":(exclude)review/phase6/wp6-2-teardown-recovery-v12/**",
            ":(exclude)review/phase6/wp6-1-consolidated-execution-v13/owner-authorization-v13.json",
            ":(exclude)review/phase6/wp6-1-consolidated-execution-v13/owner-authorization-v13.claim.json",
            ":(exclude)review/phase6/wp6-2-frozen-execution-v13/**",
            ":(exclude)review/phase6/wp6-2-teardown-recovery-v13/**",
        ),
        ("diff", "--name-only", f"{source_commit}..HEAD"),
    )
    results = [
        subprocess.run(
            ("git", *args), cwd=root, check=False, capture_output=True, text=True, timeout=10
        )
        for args in commands
    ]
    if any(result.returncode for result in results):
        raise Phase6GateError("authorized source revision is not a clean descendant")
    if results[-2].stdout.strip():
        raise Phase6GateError("unreviewed files exist outside the disclosed historical archives")
    changed = {line for line in results[-1].stdout.splitlines() if line}
    allowed = {
        f"{PACKAGE_RELATIVE.as_posix()}/{name}" for name in (*FIXED_PACKAGE_FILES, "SHA256SUMS")
    }
    if changed != allowed:
        raise Phase6GateError("post-source commit contains bytes outside the reviewed v14 package")
    for relative in GUARDED_SOURCE_FILES:
        tracked = subprocess.run(
            ("git", "ls-files", "--error-unmatch", relative),
            cwd=root,
            check=False,
            capture_output=True,
            timeout=10,
        )
        if tracked.returncode:
            raise Phase6GateError(f"authorized source is not tracked: {relative}")


def load_authorization(root: Path, package: Path, authorization_path: Path) -> dict[str, object]:
    """Authenticate the package and source before any secret/provider/cloud operation."""
    package_digest = verify_package(root, package)
    manifest = _read_object(package / "execution-manifest-v14.json")
    source_commit = manifest.get("source_commit")
    if not isinstance(source_commit, str):
        raise Phase6GateError("execution manifest lacks the source commit")
    verify_source(root, source_commit)
    expected_hashes = {relative: _file_digest(root / relative) for relative in GUARDED_SOURCE_FILES}
    if manifest.get("source_sha256s") != expected_hashes:
        raise Phase6GateError("execution manifest source hashes drifted")
    expected_authorization = package / AUTHORIZATION_NAME
    if (
        authorization_path.resolve() != expected_authorization.resolve()
        or authorization_path.is_symlink()
    ):
        raise Phase6GateError("owner authorization must be the create-only v14 sidecar")
    tracked = subprocess.run(
        ("git", "ls-files", "--error-unmatch", str(authorization_path.relative_to(root))),
        cwd=root,
        check=False,
        capture_output=True,
        timeout=10,
    )
    if tracked.returncode == 0:
        raise Phase6GateError("owner authorization sidecar must not be tracked")
    authorization = _read_object(authorization_path)
    expected = authorization_template(source_commit, package_digest)
    expected["owner_decision"] = "AUTHORIZED"
    if authorization != expected:
        raise Phase6GateError("owner authorization does not exactly bind this gate")
    return authorization


def claim_authorization(root: Path, package: Path, authorization_path: Path, output: Path) -> None:
    """Consume the one-run authorization before any secret or external operation."""
    expected_output = (root / EXECUTION_OUTPUT_RELATIVE).resolve()
    if output.resolve() != expected_output:
        raise Phase6GateError("execution output path is not the frozen one-run path")
    claim = {
        "authorization_sha256": _file_digest(authorization_path),
        "format_version": "phase5-6-owner-authorization-claim-v14",
        "output": EXECUTION_OUTPUT_RELATIVE.as_posix(),
        "relaunch": False,
    }
    try:
        write_create_only(package / AUTHORIZATION_CLAIM_NAME, canonical_artifact_bytes(claim))
    except FileExistsError as error:
        raise Phase6GateError("owner authorization was already claimed") from error


async def _resolve(value: Any) -> Any:
    resolved = await value if inspect.isawaitable(value) else value
    return await resolved.result_async() if hasattr(resolved, "result_async") else resolved


async def _delete_sampler(rest: Any, path: str) -> None:
    await _resolve(rest.delete_checkpoint_from_tinker_path_async(path))
    try:
        await _get_weights_info(rest, path)
    except tinker.NotFoundError:
        return
    raise Phase6GateError("deleted step63 sampler remains addressable")


def _extract_adapter(archive: Path, destination: Path) -> tuple[Path, ...]:
    """Extract one provider archive without links, traversal, or expansion bombs."""
    destination.mkdir(mode=0o700)
    members: list[tuple[str, int, Callable[[], Any]]] = []
    bundle: zipfile.ZipFile | tarfile.TarFile
    if zipfile.is_zipfile(archive):
        bundle = zipfile.ZipFile(archive)
        members = [
            (item.filename, item.file_size, lambda item=item: bundle.open(item))
            for item in bundle.infolist()
            if not item.is_dir()
        ]
    elif tarfile.is_tarfile(archive):
        bundle = tarfile.open(archive)
        if any(item.issym() or item.islnk() for item in bundle.getmembers()):
            bundle.close()
            raise Phase6GateError("adapter archive contains links")
        members = [
            (item.name, item.size, lambda item=item: bundle.extractfile(item))
            for item in bundle.getmembers()
            if item.isfile()
        ]
    else:
        raise Phase6GateError("adapter archive format is unsupported")
    try:
        _verify_archive_members(len(members), sum(size for _, size, _ in members), archive)
        paths: list[Path] = []
        for name, _size, opener in members:
            relative = Path(name)
            if relative.is_absolute() or ".." in relative.parts:
                raise Phase6GateError("adapter archive path escapes its destination")
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            source = opener()
            if source is None:
                raise Phase6GateError("adapter archive member cannot be read")
            with source, target.open("xb") as output:
                while chunk := source.read(8 * 1024 * 1024):
                    output.write(chunk)
            paths.append(target)
    finally:
        bundle.close()
    configs = [path for path in paths if path.name == "adapter_config.json"]
    tensors = [path for path in paths if path.suffix == ".safetensors"]
    if len(configs) != 1 or not tensors:
        raise Phase6GateError("adapter archive lacks one config and safetensors")
    # Flatten the provider's single wrapper directory for the fixed vLLM mount.
    parent = configs[0].parent
    if parent != destination:
        for path in tuple(parent.iterdir()):
            path.replace(destination / path.name)
        parent.rmdir()
    return tuple(sorted(destination.rglob("*")))


def _tensor_inventory(adapter: Path) -> dict[str, object]:
    rows: list[dict[str, object]] = []
    names: set[str] = set()
    for path in sorted(adapter.glob("*.safetensors")):
        with safe_open(path, framework="pt", device="cpu") as tensors:
            for name in tensors.keys():
                if name in names:
                    raise Phase6GateError("adapter tensor identity repeats")
                names.add(name)
                tensor = tensors.get_tensor(name)
                rows.append(
                    {
                        "dtype": str(tensor.dtype),
                        "name": name,
                        "parameter_count": tensor.numel(),
                        "shape": list(tensor.shape),
                    }
                )
    if not rows:
        raise Phase6GateError("adapter tensor inventory is empty")
    return {
        "parameter_count": sum(int(row["parameter_count"]) for row in rows),
        "tensor_count": len(rows),
        "tensors": rows,
    }


async def _wait_for_restored_identity(client: Any, rest: Any) -> dict[str, object]:
    """Wait at most 60 seconds for Tinker's new run to appear consistently in REST."""
    expected_model_id = str(client.model_id)
    info = await client.get_info_async()
    if str(info.model_id) != expected_model_id:
        raise Phase3TinkerError("Tinker client info identity mismatch")
    for attempt in range(13):
        run = await rest.get_training_run_async(expected_model_id)
        if str(run.training_run_id) == expected_model_id:
            return {
                **_verify_info(info, run, expected_lora_rank=16),
                "rest_identity_attempts": attempt + 1,
            }
        if attempt == 12:
            raise Phase3TinkerError("Tinker REST training-run identity mismatch")
        await asyncio.sleep(5)
    raise AssertionError("unreachable")


async def export_step63_adapter(
    *,
    service: Any,
    output: Path,
    archive_url_downloader: Callable[[str, Path], dict[str, object]] = _download,
) -> dict[str, object]:
    """Export only step 63, bind its bytes/tensors/license, and delete the sampler."""
    if output.exists():
        raise Phase6GateError("adapter export output already exists")
    output.mkdir(mode=0o700, parents=True)
    rest = service.create_rest_client()
    weights = await _get_weights_info(rest, STEP63_STATE)
    _verify_weights_info(weights, expected_lora_rank=16)
    client = await service.create_training_client_from_state_async(
        STEP63_STATE, user_metadata={"phase": "phase6", "purpose": "frozen-film-qualification"}
    )
    identity = await _wait_for_restored_identity(client, rest)
    sampler_path: str | None = None
    try:
        receipt = await _resolve(
            client.save_weights_for_sampler_async(
                "phase6-step63-export", ttl_seconds=SAMPLER_TTL_SECONDS
            )
        )
        sampler_path = str(receipt.path)
        url = await _resolve(rest.get_checkpoint_archive_url_from_tinker_path_async(sampler_path))
        archive = output / "step63-adapter.archive"
        archive_evidence = await asyncio.to_thread(archive_url_downloader, str(url.url), archive)
        adapter = output / "adapter"
        await asyncio.to_thread(_extract_adapter, archive, adapter)
        tensor_inventory = await asyncio.to_thread(_tensor_inventory, adapter)
        files = {
            path.relative_to(output).as_posix(): _file_digest(path)
            for path in sorted(output.rglob("*"))
            if path.is_file()
        }
        result = {
            "archive": {**archive_evidence, "path": archive.name},
            "base": {"license": "Apache-2.0", "model": BASE_MODEL, "revision": BASE_REVISION},
            "files": files,
            "format_version": "phase3x-step63-adapter-export-receipt-v5",
            "license_status": "private_qualification_only_pending_release_notices_audit",
            "sampler": {"path": sampler_path, "ttl_seconds": SAMPLER_TTL_SECONDS},
            "sampler_deleted": True,
            "state": STEP63_STATE,
            "tensor_inventory": tensor_inventory,
            "training_identity": identity,
            "weights": _weights_evidence(weights),
        }
        deleting_sampler = sampler_path
        await _delete_sampler(rest, deleting_sampler)
        sampler_path = None
        write_create_only(output / "export-receipt.json", canonical_artifact_bytes(result))
        return result
    finally:
        if sampler_path is not None:
            await _delete_sampler(rest, sampler_path)


def reuse_v5_step63_adapter(root: Path, output: Path) -> Path:
    """Verify and reuse the immutable v5 adapter export without another Tinker call."""
    source = root / V5_EXECUTION_RELATIVE
    if source.is_symlink():
        raise Phase6GateError("v5 execution root is a symlink")
    manifest = source / "SHA256SUMS"
    if _file_digest(manifest) != REJECTED_V5_RUN_SHA256SUMS:
        raise Phase6GateError("v5 execution checksum root drifted")
    expected_files = {"SHA256SUMS"}
    for line in manifest.read_text(encoding="utf-8").splitlines():
        digest, name = line.split("  ", 1)
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts or name in expected_files:
            raise Phase6GateError("v5 execution checksum path is unsafe")
        expected_files.add(name)
        if _file_digest(source / relative) != f"sha256:{digest}":
            raise Phase6GateError(f"v5 execution checksum mismatch: {name}")
    expected_directories = {
        parent.as_posix()
        for name in expected_files
        for parent in Path(name).parents
        if parent != Path(".")
    }
    actual_files: set[str] = set()
    for path in source.rglob("*"):
        relative = path.relative_to(source).as_posix()
        if path.is_symlink():
            raise Phase6GateError(f"v5 execution contains a symlink: {relative}")
        if path.is_dir():
            if relative not in expected_directories:
                raise Phase6GateError(f"v5 execution contains an extra directory: {relative}")
        elif path.is_file():
            actual_files.add(relative)
        else:
            raise Phase6GateError(f"v5 execution contains a non-regular path: {relative}")
    if actual_files != expected_files:
        raise Phase6GateError("v5 execution file inventory drifted")

    status = _read_object(source / "status.json")
    if status != {
        "error_type": "Phase6CloudError",
        "format_version": "phase5-6-gate-status-v5",
        "status": "failed_teardown_pending",
        "teardown_verified": "not_required_before_first_mutation",
    }:
        raise Phase6GateError("v5 stopped-run status drifted")
    receipt = _read_object(source / "adapter-export/export-receipt.json")
    identity = receipt.get("training_identity")
    weights = receipt.get("weights")
    if (
        receipt.get("state") != STEP63_STATE
        or receipt.get("sampler_deleted") is not True
        or not isinstance(identity, dict)
        or identity.get("lora_rank") != 16
        or identity.get("rest_lora_rank") != 16
        or identity.get("rest_corrupted") is not False
        or identity.get("rest_is_lora") is not True
        or not isinstance(weights, dict)
        or weights.get("base_model") != BASE_MODEL
        or weights.get("lora_rank") != 16
        or weights.get("train_attn") is not True
        or weights.get("train_mlp") is not True
        or weights.get("train_unembed") is not False
    ):
        raise Phase6GateError("v5 adapter identity drifted")
    adapter = source / "adapter-export/adapter"
    if not adapter.is_dir():
        raise Phase6GateError("v5 adapter directory is absent")
    write_create_only(
        output / "adapter-reuse-receipt.json",
        canonical_artifact_bytes(
            {
                "adapter": adapter.relative_to(root).as_posix(),
                "format_version": "phase3x-step63-adapter-reuse-receipt-v14",
                "source_run_sha256sums_sha256": REJECTED_V5_RUN_SHA256SUMS,
                "state": STEP63_STATE,
            }
        ),
    )
    return adapter


async def wait_for_vllm(base_url: str = "http://127.0.0.1:8000/v1") -> dict[str, object]:
    """Bound startup health polling; this never samples the model."""
    started = time.monotonic()
    async with httpx.AsyncClient(base_url=base_url, timeout=5) as client:
        for attempt in range(1, 121):
            try:
                response = await client.get("/models")
                if response.status_code == 200:
                    payload = response.json()
                    ids = sorted(
                        str(row.get("id"))
                        for row in payload.get("data", [])
                        if isinstance(row, Mapping)
                    )
                    if ids == ["phase3x-base", "phase3x-step63"]:
                        return {
                            "attempts": attempt,
                            "latency_ms": round((time.monotonic() - started) * 1000),
                            "models": ids,
                        }
            except (httpx.HTTPError, ValueError):
                pass
            await asyncio.sleep(5)
    raise Phase6GateError("exact vLLM routes did not become healthy within ten minutes")


async def qualify_frozen_variants(
    *, policy_factory: Callable[[DemoVariant], Policy], output: Path
) -> dict[str, object]:
    """Run every fixed variant once and retain the first whole pass per behavior."""
    if output.exists():
        raise Phase6GateError("qualification output already exists")
    output.mkdir(mode=0o700, parents=True)
    rows: list[dict[str, object]] = []
    selected: dict[str, str] = {}
    for variant in build_demo_variants():
        variant_dir = output / variant.scenario_id
        policy = policy_factory(variant)
        passed = False
        error_type: str | None = None
        try:
            result = await run_demo_variant(variant, variant_dir, policy=policy)
            passed = hero_contract(result, variant)
            write_create_only(
                variant_dir / "film-replay.json",
                canonical_artifact_bytes(result.film_replay_payload),
            )
            row = {
                "film_replay_sha256": _file_digest(variant_dir / "film-replay.json"),
                "policy_call_count": result.policy_call_count,
                "raw_trace_sha256s": list(result.trace_sha256s),
                "terminal_trace_count": len(result.trace_payloads),
            }
        except Exception as error:
            error_type = type(error).__name__
            row = {
                "policy_call_count": getattr(policy, "call_count", None),
                "raw_trace_sha256s": [],
            }
        if passed and variant.hero.value not in selected:
            selected[variant.hero.value] = variant.scenario_id
        rows.append(
            {
                **row,
                "error_type": error_type,
                "hero": variant.hero.value,
                "passed_whole_variant": passed,
                "scenario_id": variant.scenario_id,
                "variant": variant.variant,
            }
        )
    result = {
        "all_fifteen_passed": all(row["passed_whole_variant"] for row in rows),
        "decision_count": sum(int(row.get("policy_call_count") or 0) for row in rows),
        "first_passing_whole_variant": selected,
        "format_version": "phase5-6-frozen-model-qualification-v14",
        "no_retry_resample_repair_substitution_or_stitching": True,
        "rows": rows,
        "successful": len(selected) == len(HeroBehavior),
    }
    write_create_only(output / "qualification-receipt.json", canonical_artifact_bytes(result))
    if result["decision_count"] != 60 or result["successful"] is not True:
        raise Phase6GateError(
            "frozen qualification lacked a whole pass per behavior or the 60-tick schedule"
        )
    return result


class TinkerSemanticPolicy:
    """Sample the exact restored step-63 adapter once per semantic tick."""

    decision_format = "policy_intent_v1"

    def __init__(
        self,
        sampler: Any,
        tokenizer: PinnedTokenizer,
        system_prompt: str,
        sampler_path: str,
    ) -> None:
        self.sampler = sampler
        self.tokenizer = tokenizer
        self.system_prompt = system_prompt
        self.sampler_path = sampler_path
        self.call_count = 0

    async def decide(self, prompt_bytes: bytes) -> PolicyDecision:
        if not isinstance(prompt_bytes, bytes):
            raise TypeError("prompt_bytes must be bytes")
        prompt_tokens = phase3_data._generation_prefix_tokens(
            self.tokenizer,
            [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt_bytes.decode("utf-8")},
            ],
        )
        request = canonical_artifact_bytes(
            {
                "max_tokens": 256,
                "num_samples": 1,
                "prompt_tokens": list(prompt_tokens),
                "seed": 20260801,
                "stop": [TERMINAL_TOKEN_ID],
                "temperature": 0.0,
                "top_p": 1.0,
            }
        )
        self.call_count += 1
        started = time.monotonic()
        try:
            response = await _resolve(
                self.sampler.sample_async(
                    prompt=tinker.ModelInput.from_ints(list(prompt_tokens)),
                    num_samples=1,
                    sampling_params=tinker.SamplingParams(
                        max_tokens=256,
                        seed=20260801,
                        stop=[TERMINAL_TOKEN_ID],
                        temperature=0.0,
                        top_p=1.0,
                    ),
                )
            )
        except asyncio.CancelledError as error:
            call = PolicyCallTrace(
                attempt_index=1,
                model=self.sampler_path,
                prompt_hash=_digest(prompt_bytes),
                request=request,
                response=b"",
                latency_ms=round((time.monotonic() - started) * 1000),
                http_status=None,
                outcome="cancelled",
            )
            raise PolicyCallCancelled((call,)) from error
        except Exception as error:
            call = PolicyCallTrace(
                attempt_index=1,
                model=self.sampler_path,
                prompt_hash=_digest(prompt_bytes),
                request=request,
                response=b"",
                latency_ms=round((time.monotonic() - started) * 1000),
                http_status=None,
                outcome="provider_error",
            )
            raise PolicyCallError("Tinker sampling failed", (call,)) from error

        latency_ms = round((time.monotonic() - started) * 1000)
        if len(response.sequences) != 1:
            raise PolicyCallError("Tinker returned an unexpected sample count", ())
        sequence = response.sequences[0]
        tokens = tuple(sequence.tokens)
        decoded = self.tokenizer.tokenizer.decode(tokens, skip_special_tokens=False)
        if not isinstance(decoded, str):
            raise PolicyCallError("pinned tokenizer failed to decode Tinker output", ())
        raw_output = decoded.encode("utf-8")
        response_bytes = canonical_artifact_bytes(
            {"stop_reason": str(sequence.stop_reason), "tokens": list(tokens)}
        )
        parser_input = parser_sha = binding = None
        outcome = "invalid_terminal_framing"
        try:
            projection = project_terminal_output(
                finish_reason=str(sequence.stop_reason),
                output_token_ids=tokens,
                decoded_bytes=raw_output,
                tokenizer=self.tokenizer.tokenizer,
            )
            parser_input = projection.parser_input
            parser_sha = projection.parser_input_sha256
            binding = "authenticated_terminal_framing"
            outcome = "completed"
        except Exception:
            pass
        call = PolicyCallTrace(
            attempt_index=1,
            model=self.sampler_path,
            prompt_hash=_digest(prompt_bytes),
            request=request,
            response=response_bytes,
            latency_ms=latency_ms,
            http_status=None,
            outcome=outcome,
        )
        return PolicyDecision(
            attempt=None,
            calls=(call,),
            output_bytes=raw_output,
            output_bytes_sha256=_digest(raw_output),
            parser_input_bytes=parser_input,
            parser_input_sha256=parser_sha,
            parser_input_binding=binding,
            latency_ms=latency_ms,
        )


async def qualify_step63_with_tinker(root: Path, output: Path) -> dict[str, object]:
    """Run the frozen 15-variant gate through one temporary Tinker sampler."""
    if output.exists():
        raise Phase6GateError("Tinker qualification output already exists")
    output.mkdir(mode=0o700, parents=True)
    status: dict[str, object] = {
        "format_version": "phase5-6-tinker-qualification-status-v1",
        "optimizer_updates": 0,
        "selected_state": STEP63_STATE,
        "status": "starting",
    }
    sampler_path: str | None = None
    rest: Any = None
    pipeline_error: BaseException | None = None
    cleanup_error: BaseException | None = None
    try:
        tokenizer = load_pinned_tokenizer(
            root, root / ".cache/replay-sources/995ad96eacd98c81ed38be0c5b274b04031597b0"
        )
        system_prompt = (root / "spec/phase3x-policy-intent-prompt-v1.txt").read_text("utf-8")
        key = read_tinker_api_key(root / ".env")
        os.environ["TINKER_API_KEY"] = key
        key = ""
        service = tinker.ServiceClient(
            user_metadata={"phase": "phase6", "purpose": "frozen-film-qualification"}
        )
        rest = service.create_rest_client()
        weights = await _get_weights_info(rest, STEP63_STATE)
        _verify_weights_info(weights, expected_lora_rank=16)
        client = await _resolve(
            service.create_training_client_from_state_async(
                STEP63_STATE,
                user_metadata={"phase": "phase6", "optimizer": "unused"},
            )
        )
        status["provider_identity"] = await _wait_for_restored_identity(client, rest)
        receipt = await _resolve(
            client.save_weights_for_sampler_async(
                "phase6-film-qualification", ttl_seconds=SAMPLER_TTL_SECONDS
            )
        )
        sampler_path = str(receipt.path)
        sampler = await _resolve(service.create_sampling_client_async(model_path=sampler_path))
        status["sampler_path"] = sampler_path
        result = await qualify_frozen_variants(
            policy_factory=lambda _variant: TinkerSemanticPolicy(
                sampler, tokenizer, system_prompt, sampler_path
            ),
            output=output / "qualification",
        )
        status.update(
            {
                "decision_count": result["decision_count"],
                "first_passing_whole_variant": result["first_passing_whole_variant"],
                "status": "qualification_complete_cleanup_pending",
            }
        )
    except BaseException as error:
        pipeline_error = error
        status.update({"error_type": type(error).__name__, "status": "failed_cleanup_pending"})
    finally:
        os.environ.pop("TINKER_API_KEY", None)
        if rest is not None and sampler_path is not None:
            try:
                await _delete_sampler(rest, sampler_path)
                _verify_weights_info(
                    await _get_weights_info(rest, STEP63_STATE), expected_lora_rank=16
                )
                status["sampler_deleted_and_verified_absent"] = True
                status["selected_state_preserved"] = True
            except BaseException as error:
                cleanup_error = error
                status.update(
                    {
                        "sampler_deleted_and_verified_absent": False,
                        "selected_state_preserved": False,
                        "status": "failed_cleanup",
                    }
                )
        if status["status"] == "qualification_complete_cleanup_pending":
            status["status"] = "complete"
        write_create_only(output / "status.json", canonical_artifact_bytes(status))
        files = {
            path.relative_to(output).as_posix(): path.read_bytes()
            for path in output.rglob("*")
            if path.is_file()
        }
        write_create_only(output / "SHA256SUMS", checksum_inventory(files))
    if cleanup_error is not None:
        raise Phase6GateError("Tinker sampler cleanup failed") from cleanup_error
    if pipeline_error is not None:
        raise pipeline_error
    return status


def package_files(root: Path, source_commit: str) -> dict[str, bytes]:
    """Render the checksum-bound v14 package from already-committed source bytes."""
    source_hashes = {relative: _file_digest(root / relative) for relative in GUARDED_SOURCE_FILES}
    manifest = {
        "authorization": False,
        "base": {"license": "Apache-2.0", "model": BASE_MODEL, "revision": BASE_REVISION},
        "checkpoint": {"identity": STEP63_STATE, "restore": "weights_only", "step": 63},
        "cloud": {
            "hard_ceiling_usd": MAX_SPEND_USD,
            "max_hours": MAX_RUNTIME_HOURS,
            "nat": "run_scoped_cloud_router_and_cloud_nat",
            "project": PROJECT,
            "run_id": RUN_ID,
            "dlvm_image": DLVM_IMAGE,
            "dlvm_project": DLVM_PROJECT,
        },
        "execution": {
            "adapter_export": "reuse_checksum_verified_v5_export_without_tinker",
            "commands": "cloud-command-plan-v14.json",
            "qualification": "15_whole_variants_60_ticks_exactly_once",
            "raw_first_trace": True,
            "retry_repair_relaunch_fallback": False,
            "teardown_absence_required": True,
        },
        "format_version": "phase5-6-consolidated-readiness-execution-v14",
        "frozen_model_qualification": False,
        "source_commit": source_commit,
        "source_sha256s": source_hashes,
        "status": "offline_executable_pending_single_owner_authorization",
        "rejected_v1": {
            "path": "review/phase6/wp6-1-consolidated-readiness-v1",
            "reasons": ["invalid_base_revision", "nonexecutable_plan"],
            "sha256sums_sha256": REJECTED_V1_SHA256SUMS,
            "status": "rejected_preserved_immutable_evidence",
        },
        "rejected_v2": {
            "path": "review/phase6/wp6-1-consolidated-execution-v2",
            "reasons": [
                "missing_exact_dlvm_image_preflight",
                "retired_huggingface_cli_entrypoint",
            ],
            "sha256sums_sha256": REJECTED_V2_SHA256SUMS,
            "status": "rejected_pre_owner_preserved_immutable_evidence",
        },
        "rejected_v3": {
            "path": "review/phase6/wp6-1-consolidated-execution-v3",
            "reasons": [
                "clean_mode_retained_technical_trace_data_and_dom",
                "clean_action_summaries_exposed_internal_aliases",
            ],
            "sha256sums_sha256": REJECTED_V3_SHA256SUMS,
            "status": "rejected_pre_owner_preserved_immutable_evidence",
        },
        "rejected_v4": {
            "path": "review/phase6/wp6-1-consolidated-execution-v4",
            "reasons": ["transient_tinker_rest_identity_race_before_adapter_export"],
            "run_path": "review/phase6/wp6-2-frozen-execution-v4",
            "run_sha256sums_sha256": REJECTED_V4_RUN_SHA256SUMS,
            "sha256sums_sha256": REJECTED_V4_SHA256SUMS,
            "status": "failed_pre_cloud_preserved_immutable_evidence",
        },
        "rejected_v5": {
            "adapter_export_reused_by_v14": True,
            "path": "review/phase6/wp6-1-consolidated-execution-v5",
            "reasons": ["expired_gcloud_auth_then_retired_dlvm_image_identity"],
            "run_path": V5_EXECUTION_RELATIVE.as_posix(),
            "run_sha256sums_sha256": REJECTED_V5_RUN_SHA256SUMS,
            "sha256sums_sha256": REJECTED_V5_SHA256SUMS,
            "status": "failed_pre_cloud_mutation_preserved_immutable_evidence",
        },
        "rejected_v6": {
            "path": "review/phase6/wp6-1-consolidated-execution-v6",
            "reasons": ["legacy_region_quota_surface_omitted_current_spot_g4_quota"],
            "run_path": V6_EXECUTION_RELATIVE.as_posix(),
            "run_sha256sums_sha256": REJECTED_V6_RUN_SHA256SUMS,
            "sha256sums_sha256": REJECTED_V6_SHA256SUMS,
            "status": "false_negative_pre_cloud_mutation_preserved_immutable_evidence",
        },
        "rejected_v7": {
            "path": "review/phase6/wp6-1-consolidated-execution-v7",
            "reasons": ["unsupported_explicit_false_value_for_cloud_nat_logging_flag"],
            "run_path": V7_EXECUTION_RELATIVE.as_posix(),
            "run_sha256sums_sha256": REJECTED_V7_RUN_SHA256SUMS,
            "sha256sums_sha256": REJECTED_V7_SHA256SUMS,
            "status": "failed_before_vm_create_teardown_verified_preserved_immutable_evidence",
        },
        "rejected_v8": {
            "path": "review/phase6/wp6-1-consolidated-execution-v8",
            "reasons": ["g4_boot_disk_requires_hyperdisk_balanced"],
            "run_path": V8_EXECUTION_RELATIVE.as_posix(),
            "run_sha256sums_sha256": REJECTED_V8_RUN_SHA256SUMS,
            "sha256sums_sha256": REJECTED_V8_SHA256SUMS,
            "status": "failed_before_vm_create_teardown_verified_preserved_immutable_evidence",
        },
        "rejected_v9": {
            "path": "review/phase6/wp6-1-consolidated-execution-v9",
            "reasons": ["selected_dlvm_image_does_not_preinstall_docker"],
            "run_path": V9_EXECUTION_RELATIVE.as_posix(),
            "run_sha256sums_sha256": REJECTED_V9_RUN_SHA256SUMS,
            "sha256sums_sha256": REJECTED_V9_SHA256SUMS,
            "status": "failed_before_model_download_teardown_verified_preserved_immutable_evidence",
        },
        "rejected_v10": {
            "path": "review/phase6/wp6-1-consolidated-execution-v10",
            "reasons": ["transient_iap_instance_lookup_race_before_remote_setup"],
            "run_path": V10_EXECUTION_RELATIVE.as_posix(),
            "run_sha256sums_sha256": REJECTED_V10_RUN_SHA256SUMS,
            "sha256sums_sha256": REJECTED_V10_SHA256SUMS,
            "status": "failed_before_remote_setup_teardown_verified_preserved_immutable_evidence",
        },
        "rejected_v11": {
            "path": "review/phase6/wp6-1-consolidated-execution-v11",
            "reasons": ["dlvm_nvidia_toolkit_metapackage_version_conflict"],
            "run_path": V11_EXECUTION_RELATIVE.as_posix(),
            "run_sha256sums_sha256": REJECTED_V11_RUN_SHA256SUMS,
            "sha256sums_sha256": REJECTED_V11_SHA256SUMS,
            "status": "failed_during_remote_setup_teardown_verified_preserved_immutable_evidence",
        },
        "rejected_v12": {
            "path": "review/phase6/wp6-1-consolidated-execution-v12",
            "reasons": ["huggingface_xet_download_stalled_and_timed_out"],
            "run_path": V12_EXECUTION_RELATIVE.as_posix(),
            "run_sha256sums_sha256": REJECTED_V12_RUN_SHA256SUMS,
            "sha256sums_sha256": REJECTED_V12_SHA256SUMS,
            "status": "failed_during_model_download_recovery_teardown_verified",
            "teardown_recovery_sha256sums_sha256": REJECTED_V12_TEARDOWN_SHA256SUMS,
        },
        "rejected_v13": {
            "path": "review/phase6/wp6-1-consolidated-execution-v13",
            "reasons": ["vllm_default_max_num_seqs_exceeded_mamba_cache_blocks"],
            "run_path": V13_EXECUTION_RELATIVE.as_posix(),
            "run_sha256sums_sha256": REJECTED_V13_RUN_SHA256SUMS,
            "sha256sums_sha256": REJECTED_V13_SHA256SUMS,
            "status": "failed_before_sampling_recovery_teardown_verified",
            "teardown_recovery_sha256sums_sha256": REJECTED_V13_TEARDOWN_SHA256SUMS,
        },
        "vllm": {
            "language_model_only": True,
            "linux_amd64_digest": VLLM_AMD64_DIGEST,
            "manifest_digest": VLLM_MANIFEST_DIGEST,
            "one_call_per_tick": True,
            "hf_entrypoint": "hf",
            "hf_version_preflight": True,
        },
    }
    readme = f"""# Phase 5/6 consolidated readiness/execution v14

Status: OFFLINE, executable, and not authorized. Versions 1 through 6 remain immutable rejected
evidence. Version 1 used a malformed base revision and lacked executable launch bytes. Version 2
lacked an exact DLVM image preflight and used the retired `huggingface-cli` entrypoint. Version 3
retained technical trace data/DOM in clean film mode and exposed internal aliases in action
summaries. Version 4 failed before adapter export or cloud access because Tinker's new restored-run
REST identity had not converged on the first read. Its sealed execution root is
`{REJECTED_V4_RUN_SHA256SUMS}`. Package `SHA256SUMS` digests are `{REJECTED_V1_SHA256SUMS}`,
`{REJECTED_V2_SHA256SUMS}`, `{REJECTED_V3_SHA256SUMS}`, and `{REJECTED_V4_SHA256SUMS}`.
Version 5 exported and deleted the ephemeral Tinker sampler successfully, then stopped before the
first cloud mutation because local gcloud authentication had expired and the pinned DLVM image was
retired. Its package and sealed run roots are `{REJECTED_V5_SHA256SUMS}` and
`{REJECTED_V5_RUN_SHA256SUMS}`. Version 6 reused that exact checksum-verified adapter directory but
stopped before the first cloud mutation because the legacy regional quota response omitted the
authoritative current G4 Spot quota. Its package and sealed run roots are
`{REJECTED_V6_SHA256SUMS}` and `{REJECTED_V6_RUN_SHA256SUMS}`. Version 7 read that quota from the
Cloud Quotas API, then failed before VM creation because the installed gcloud rejects an explicit
false value for the boolean Cloud NAT logging flag. It tore down and verified every run resource
absent. Its package and sealed run roots are `{REJECTED_V7_SHA256SUMS}` and
`{REJECTED_V7_RUN_SHA256SUMS}`. Version 8 omits that flag because Cloud NAT logging is disabled by
default. Version 8 then reached VM creation, where GCP rejected the generic persistent boot disk:
G4 supports only `hyperdisk-balanced` for boot. Its package and sealed run roots are
`{REJECTED_V8_SHA256SUMS}` and `{REJECTED_V8_RUN_SHA256SUMS}`. Version 9 uses the required G4 boot
disk type. Version 9 created and reached the VM but the current base DLVM image does not include
Docker, so it stopped before model download or sampling and verified teardown. Its package and
sealed run roots are `{REJECTED_V9_SHA256SUMS}` and `{REJECTED_V9_RUN_SHA256SUMS}`. Version 10
installs Docker and NVIDIA Container Toolkit on the fresh private VM before using the same pinned
container. Version 10 then hit a transient IAP lookup race immediately after VM creation, before
remote setup. Its package and sealed run roots are `{REJECTED_V10_SHA256SUMS}` and
`{REJECTED_V10_RUN_SHA256SUMS}`. Version 11 adds one fixed 60-second VM stabilization delay before
the single remote setup command. Version 11 reached package installation, where the DLVM's pinned
NVIDIA 1.17.8 dependency family conflicted with the newest toolkit metapackage. Its package and
sealed run roots are `{REJECTED_V11_SHA256SUMS}` and `{REJECTED_V11_RUN_SHA256SUMS}`. Version 12
pins the matching toolkit components already selected by that image, then its unauthenticated Xet
transfer stalled with eight incomplete files and hit the 30-minute timeout. Its package, run, and
recovery-teardown roots are `{REJECTED_V12_SHA256SUMS}`, `{REJECTED_V12_RUN_SHA256SUMS}`, and
`{REJECTED_V12_TEARDOWN_SHA256SUMS}`. Version 13 disables Xet and downloads the exact model, then
vLLM rejects its default 1,024 concurrent sequences because this model exposes 680 Mamba cache
blocks. Its package, run, and recovery-teardown roots are `{REJECTED_V13_SHA256SUMS}`,
`{REJECTED_V13_RUN_SHA256SUMS}`, and `{REJECTED_V13_TEARDOWN_SHA256SUMS}`. Version 14 caps
concurrency at 16 for the serialized one-sample runtime. It reads no Tinker or Hugging Face secret.

## Frozen identities and kill gates

- Source commit: `{source_commit}` with every execution source SHA-256 in the manifest.
- Only adapter: Phase3X step 63 `{STEP63_STATE}`, weights-only, LoRA rank 16.
- Base: `{BASE_MODEL}` at exact 40-character revision `{BASE_REVISION}`.
- vLLM: v0.25.1 manifest `{VLLM_MANIFEST_DIGEST}` and Linux/amd64
  `{VLLM_AMD64_DIGEST}`; no tag or image fallback.
- Serving is loopback-only with `--generation-config vllm`, `--language-model-only`,
  `--max-model-len 65536`, one static LoRA, temperature 0, n=1, token IDs returned,
  special-token skipping disabled, and authenticated terminal framing. No correction or retry.

The gate verifies this package, clean tracked source, create-only owner authorization, the complete
v5 run checksum root, adapter archive, tensor, hash, training identity, license status, and sampler
deletion before invoking GCP. It permits one launch and makes no Tinker call.

## Cloud and teardown contract

`cloud-command-plan-v14.json` freezes project `{PROJECT}`, one `g4-standard-48` Spot VM in
`us-central1-b`, a 200-GiB auto-delete disk, absolute <=24-hour DELETE termination, no restart,
replacement, relaunch, external IP, service account, or OAuth scope. A new run-scoped VPC,
subnet, Cloud Router, Cloud NAT, and IAP-only SSH firewall are mandatory; discovering an existing
run resource fails closed. The base and pinned container leave through only that NAT. The adapter
uses IAP SCP. vLLM stays on `127.0.0.1` behind an IAP tunnel.

The <=$60 envelope uses the official $1.79982/hour G4 Spot price captured on 2026-08-12:
$43.20 Spot compute, $0.66 disk, $2.28 internet egress reserve, and about $1.06 Cloud NAT
address/processing reserve, <=$47.20 estimated. Quota, machine shape, exact-zone Capacity Advisor,
current-price output, and resource absence must all return matching evidence before create. The
Spot RTX PRO 6000 limit is read from the authoritative Cloud Quotas API; the legacy regional
response remains the CPU/disk authority only. The captured hourly price is also checked at
execution against the frozen 24-hour/$60 ceiling.
The gate also describes the exact frozen DLVM image in `deeplearning-platform-release` and requires
its exact name, READY status, and selfLink before the first mutation. On the VM, the pinned image
must run `hf --version` before `hf download` starts the large, revision-pinned base transfer.
On any failure, teardown runs once and verifies absence of the VM, auto-delete disk, snapshot,
address, reservation, container/VM, firewall, NAT, router, subnet, network, and local tunnel.

## Qualification and film

The exact five behaviors x three frozen variants run once through the production virtual-time
runtime and `LocalVLLMSemanticPolicy`: lookup yield/integrate, three animal marks, sequential
`um`/`you know`, invisible idle, and recurring timer schedule/nudges/cancel/silence. All 15 takes
and exactly 60 terminal decisions are retained. Any malformed, unresolvable, or hard-blocked tick
fails its whole variant. There is no retry, resample, repair, substitution, rerun, or stitching.
The first complete passing whole variant per behavior is the only film disposition. Clean and
technical projections consume the same durable SQLite stream; effects are credential-free,
session-local timers and scripted read-only lookup fixtures only.

Opaque TEST overlap is zero over 417 commitments. TRAIN/DEV remain null and informational for
these qualitative scripts; no zero claim is made and no combined registry is reopened. Frozen
TEST remains selection-free and is neither rerun nor resampled.

## Publication and disclosure inventory

The release gate retains exact requests/responses/parser bytes/hashes/latency in SQLite, adapter
and source receipts, command/cost/resource receipts, detached vLLM logs, all 15 durable traces,
first passing film streams, teardown proof, model card, article, license/NOTICE audit, and release
inventory. The article/model card must cover architecture, data lineage, Phase3X selection,
negative-DPO fallback, frozen TEST metrics, runtime/film, limitations, failures, safety and cost.

Two process deviations remain mandatory disclosures: (1) the earlier Phase5 authority-row
preflight disclosure, with no TEST model output; and (2) the checksum-bound Phase6 boundary
incident. The TEST boundary was not unbroken. No row content was displayed, copied, or used;
implementation dependence is false and dataset contamination is not proven.

Official execution references: [G4](https://docs.cloud.google.com/compute/docs/gpus),
[Spot](https://docs.cloud.google.com/compute/docs/instances/spot),
[G4 pricing](https://cloud.google.com/products/compute/pricing/accelerator-optimized),
[Cloud NAT pricing](https://cloud.google.com/nat/pricing),
[Capacity Advisor](https://docs.cloud.google.com/sdk/gcloud/reference/beta/compute/advice/capacity),
[IAP](https://docs.cloud.google.com/iap/docs/using-tcp-forwarding),
[termination](https://docs.cloud.google.com/compute/docs/instances/limit-vm-runtime),
[vLLM text-only](https://docs.vllm.ai/en/latest/models/supported_models/), and
[Qwen revision](https://huggingface.co/{BASE_MODEL}/tree/{BASE_REVISION}).
""".encode()
    template = authorization_template(source_commit, "REPLACE_WITH_SHA256_OF_SHA256SUMS")
    model_card = f"""# Phase3X step-63 model card, qualification candidate

Status: private, offline, and not qualified on the frozen film protocol.

The candidate is the Phase3X rank-16 LoRA at `{STEP63_STATE}` over
`{BASE_MODEL}` revision `{BASE_REVISION}`. The upstream base license is Apache-2.0. Adapter
redistribution remains blocked until the exported bytes pass the license and notices audit.

The model emits the frozen Phase3X semantic-intent schema for the existing nine sandbox actions.
One tick makes one temperature-zero request. The runtime authenticates terminal framing and parses
only those bytes. It does not repair, retry, resample, substitute, or use a public action adapter.
Respond prose alone may use the LoRA-disabled base route. Integrate uses the exact committed result.

Intended use is the credential-free film sandbox with session-local timers and scripted read-only
lookup fixtures. The candidate has no authority for autonomous, external, product, or write-capable
effects. A wrong but resolvable decision takes its exact sandbox effect. Malformed, unresolvable,
hard-blocked, or canceled decisions fail the take and remain in the durable technical trace.

Qualification is pending. The gate will run all five behaviors and three fixed variants once, 60
ticks total. It retains every failure and may film only the first complete passing whole variant per
behavior. The 15/15 result already on disk is scripted runtime-contract evidence, not model quality.
Opaque TEST overlap is zero over 417 commitments. TRAIN and DEV remain unknown and informational.

Known limitations include unproven vLLM/Qwen/LoRA/G4 cold-start compatibility, Spot interruption,
no process-restart technical replay, and no frozen-model film result yet. Frozen TEST is not rerun.

The final card and article must disclose both process deviations. Phase5 preflight exposed one
authority row, with no TEST model output. Phase6 search output crossed the intended boundary. The
TEST boundary was not unbroken. No row content was displayed, copied, or used, implementation did
not depend on it, and contamination is not proven.
""".encode()
    release_inventory = {
        "adapter": {
            "archive_sha256": (
                "sha256:b19f74a9c11e4e38f878f267efc54981798c25751edbfcb058c602cd29bb4716"
            ),
            "export_receipt": (
                "review/phase6/wp6-2-frozen-execution-v5/adapter-export/export-receipt.json"
            ),
            "license_notices_audit": "pending_exported_bytes",
            "state": STEP63_STATE,
        },
        "base": {"model": BASE_MODEL, "revision": BASE_REVISION},
        "evidence": {
            "boundary_incident": "docs/phase6-boundary-incident-v1.json",
            "film_clean_and_technical": "pending_frozen_qualification",
            "frozen_test_metrics": "reference_existing_frozen_aggregate_only",
            "raw_terminal_traces": "pending_frozen_qualification",
            "scripted_runtime_contract": (
                "review/phase6/wp6-0-demo-qualification/"
                "scripted-runtime-contract-qualification-proof.json"
            ),
            "teardown_receipt": "pending_authorized_execution",
        },
        "format_version": "phase5-6-release-inventory-v14",
        "process_deviations": [
            "phase5_preflight_authority_row_disclosure_no_test_model_output",
            "phase6_checksum_bound_boundary_incident_test_boundary_not_unbroken",
        ],
        "publication": {
            "article": "pending_final_evidence",
            "failure_history": "required",
            "final_model_card": "pending_export_and_qualification",
        },
        "serving": {
            "linux_amd64_digest": VLLM_AMD64_DIGEST,
            "manifest_digest": VLLM_MANIFEST_DIGEST,
            "receipts": "pending_authorized_execution",
        },
        "source_commit": source_commit,
    }
    return {
        "README.md": readme,
        "cloud-command-plan-v14.json": plan_bytes(source_commit),
        "execution-manifest-v14.json": canonical_artifact_bytes(manifest),
        "model-card-v14.md": model_card,
        "release-inventory-v14.json": canonical_artifact_bytes(release_inventory),
        TEMPLATE_NAME: canonical_artifact_bytes(template),
    }


def write_package(root: Path, source_commit: str) -> Path:
    output = root / PACKAGE_RELATIVE
    if output.exists():
        raise Phase6GateError("v14 package already exists")
    files = package_files(root, source_commit)
    output.mkdir(parents=True, mode=0o700)
    for name, raw in files.items():
        write_create_only(output / name, raw)
    write_create_only(output / "SHA256SUMS", checksum_inventory(files))
    return output
