"""Detached preservation and analysis for the failed Phase 3 SFT negative controls."""

from __future__ import annotations

import asyncio
import gzip
import inspect
import json
import math
import os
import subprocess
import sys
import tarfile
import time
import urllib.request
import zipfile
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from hashlib import sha256
from pathlib import Path
from typing import Any

import tinker
import torch
from pydantic import ValidationError
from safetensors import safe_open

from im.assets.model import canonical_artifact_bytes
from im.schema.actions import ACTION_ADAPTER
from im.training.phase3_data import load_pinned_tokenizer
from im.training.phase3_framing import TerminalFramingError, project_terminal_output
from im.training.phase3_sampling import read_tinker_api_key
from im.training.phase3_tinker import _verify_info, _verify_weights_info, _weights_evidence

BACKBONE = "Qwen/Qwen3.6-35B-A3B"
SAMPLING = {
    "max_tokens": 1024,
    "seed": 20260801,
    "stop": [248046],
    "temperature": 0.0,
    "top_k": -1,
    "top_p": 1.0,
}
STATE_PATHS = {
    step: (f"tinker://5ac8e275-3277-5751-a257-68f7c54cc145:train:0/weights/wp3-4-state-{step}")
    for step in (20, 40, 60, 63, 80, 100, 120, 126)
}
NEGATIVE_CONTROL_STEPS = (40, 63)
SAMPLER_TTL_SECONDS = 21_600
MAXIMUM_INCREMENTAL_SAMPLING_USD = 3.0
PREFILL_USD_PER_MILLION = 0.54
SAMPLE_USD_PER_MILLION = 1.335
MAXIMUM_ARCHIVE_BYTES = 8 * 1024**3
MAXIMUM_EXTRACTED_BYTES = 16 * 1024**3
MAXIMUM_ARCHIVE_MEMBERS = 256
DRIVE_FOLDER_ID = "1TC4-VK7Jp4UGQLYsluYwgsDopwroQOB-"
LAUNCHD_LABEL = "com.interactionmodel.phase3r-negative-controls"
LAUNCHD_ENV_NAME = "INTERACTIONMODEL_PHASE3R_LAUNCHD_LABEL"


class NegativeControlError(RuntimeError):
    """The authorized preservation path failed closed."""


def verify_source(
    root: Path,
    source_commit: str,
    authorization: Mapping[str, object],
    *,
    authorization_kind: str,
) -> None:
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()
    if head != source_commit:
        raise NegativeControlError("source commit does not match HEAD")
    for command in (["git", "diff", "--quiet"], ["git", "diff", "--cached", "--quiet"]):
        if subprocess.run(command, cwd=root, check=False).returncode:
            raise NegativeControlError("tracked worktree is not clean")
    expected_hashes = {
        "runner_module_sha256": _digest_file(root / "src/im/training/phase3r_negative_controls.py"),
        "runner_script_sha256": _digest_file(root / "scripts/run_phase3r_negative_controls.py"),
        "runner_test_sha256": _digest_file(root / "tests/test_phase3r_negative_controls.py"),
    }
    for relative in (
        "src/im/training/phase3r_negative_controls.py",
        "scripts/run_phase3r_negative_controls.py",
        "tests/test_phase3r_negative_controls.py",
    ):
        if subprocess.run(
            ["git", "ls-files", "--error-unmatch", relative],
            cwd=root,
            check=False,
            capture_output=True,
        ).returncode:
            raise NegativeControlError("authorized runner source is not tracked by Git")
    expected = {
        "allowed_secret_name": "TINKER_API_KEY",
        "drive_folder_id": DRIVE_FOLDER_ID,
        "kind": authorization_kind,
        "launchd_label": LAUNCHD_LABEL,
        "maximum_incremental_sampling_usd": MAXIMUM_INCREMENTAL_SAMPLING_USD,
        "owner_decision": "authorized",
        "sealed_test_access": "forbidden",
        "source_commit": source_commit,
        "state_paths": {str(step): path for step, path in STATE_PATHS.items()},
        **expected_hashes,
    }
    if any(authorization.get(name) != value for name, value in expected.items()):
        raise NegativeControlError("owner authorization does not bind this source and operation")


def load_authorization(path: Path, *, cleanup_mode: bool) -> Mapping[str, object]:
    authorization = _read_json(path)
    expected = (
        {"delete_full_states": list(STATE_PATHS), "optimizer_steps": 0}
        if cleanup_mode
        else {
            "delete_ephemeral_samplers": True,
            "delete_full_states": [],
            "download_sampler_archives": [40, 63],
            "evaluate_training_slice": [40, 63],
            "export_ephemeral_samplers": [40, 63],
            "optimizer_steps": 0,
        }
    )
    if authorization.get("provider_operations") != expected:
        raise NegativeControlError("owner authorization provider operations are malformed")
    return authorization


def verify_launchd_execution() -> None:
    if (
        sys.platform != "darwin"
        or os.getppid() != 1
        or os.environ.get(LAUNCHD_ENV_NAME) != LAUNCHD_LABEL
    ):
        raise NegativeControlError("provider work must run as the frozen detached LaunchAgent")
    result = subprocess.run(
        ["launchctl", "print", f"gui/{os.getuid()}/{LAUNCHD_LABEL}"],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    if result.returncode != 0 or f"pid = {os.getpid()}" not in result.stdout:
        raise NegativeControlError("LaunchAgent identity does not match this provider process")


def prompt_tokens(datum: Mapping[str, object]) -> list[int]:
    inputs, weights = datum.get("input_tokens"), datum.get("weights")
    if (
        not isinstance(inputs, list)
        or not isinstance(weights, list)
        or len(inputs) != len(weights)
        or any(not isinstance(token, int) for token in inputs)
    ):
        raise NegativeControlError("training datum is malformed")
    positive = [index for index, weight in enumerate(weights) if float(weight) > 0]
    if not positive:
        raise NegativeControlError("training datum has no target span")
    return inputs[: positive[0] + 1]


def grade_training_output(
    *, datum: Mapping[str, object], tokens: Sequence[int], finish_reason: str, tokenizer: Any
) -> dict[str, object]:
    lineage = datum.get("lineage")
    action_text = lineage.get("action_utf8") if isinstance(lineage, Mapping) else None
    if not isinstance(action_text, str):
        raise NegativeControlError("training datum lacks its gold action")
    expected = ACTION_ADAPTER.validate_json(action_text)
    decoded = tokenizer.decode(list(tokens), skip_special_tokens=False)
    raw = decoded.encode("utf-8")
    result: dict[str, object] = {
        "decoded_utf8": decoded,
        "action_type": str(expected.type),
        "finish_reason": finish_reason,
        "output_bytes_sha256": _digest(raw),
        "output_token_count": len(tokens),
        "output_token_ids": list(tokens),
    }
    try:
        projected = project_terminal_output(
            finish_reason=finish_reason,
            output_token_ids=tokens,
            decoded_bytes=raw,
            tokenizer=tokenizer,
        )
        predicted = ACTION_ADAPTER.validate_json(projected.parser_input)
    except (TerminalFramingError, ValidationError, UnicodeError) as error:
        result.update({"strict_match": False, "failure": type(error).__name__})
        return result
    result.update(
        {
            "framing": projected.audit_record(),
            "predicted_action": predicted.model_dump(mode="json"),
            "strict_match": predicted == expected,
        }
    )
    return result


def sampling_cost_upper(prompt_count: int, prompt_tokens_total: int) -> dict[str, float | int]:
    output_tokens = prompt_count * int(SAMPLING["max_tokens"])
    prefill = prompt_tokens_total * PREFILL_USD_PER_MILLION / 1_000_000
    output = output_tokens * SAMPLE_USD_PER_MILLION / 1_000_000
    return {
        "maximum_output_tokens": output_tokens,
        "maximum_output_usd": output,
        "prefill_tokens": prompt_tokens_total,
        "prefill_usd": prefill,
        "total_usd": prefill + output,
    }


async def preserve(
    *,
    root: Path,
    output: Path,
    archive_directory: Path,
    source_commit: str,
    authorization_path: Path,
) -> None:
    authorization = load_authorization(authorization_path, cleanup_mode=False)
    verify_source(
        root,
        source_commit,
        authorization,
        authorization_kind="phase3r-negative-control-preservation-owner-authorization-v1",
    )
    verify_launchd_execution()
    if output.exists() or archive_directory.exists():
        raise NegativeControlError("preservation output already exists")
    selection = _read_json(
        root / "review/phase3/wp3r-1-offline-forensics-candidate-v1/train-vs-dev-slice.json"
    )
    selected_ids = [str(row["datum_id"]) for row in selection["rows"]]
    datums = _load_datums(
        root / "review/phase3/wp3-1-materialization-candidate-v5/materialized-datums.jsonl.gz",
        set(selected_ids),
    )
    prompts = {datum_id: prompt_tokens(datums[datum_id]) for datum_id in selected_ids}
    cost = sampling_cost_upper(
        len(selected_ids) * len(NEGATIVE_CONTROL_STEPS),
        sum(len(tokens) for tokens in prompts.values()) * len(NEGATIVE_CONTROL_STEPS),
    )
    if float(cost["total_usd"]) > MAXIMUM_INCREMENTAL_SAMPLING_USD:
        raise NegativeControlError("negative-control sampling exceeds the local $3 safety stop")

    output.mkdir(mode=0o700, parents=True)
    archive_directory.mkdir(mode=0o700, parents=True)
    status = {
        "kind": "phase3r-negative-control-preservation-status-v1",
        "source_commit": source_commit,
        "authorization_sha256": _digest_file(authorization_path),
        "state_paths": {str(step): STATE_PATHS[step] for step in STATE_PATHS},
        "sampling_cost_upper": cost,
        "status": "starting",
    }
    _write_json(output / "status.json", status)
    key = read_tinker_api_key(root / ".env")
    try:
        service = tinker.ServiceClient(
            api_key=key,
            user_metadata={"phase": "phase3r", "purpose": "negative-control-preservation"}
        )
        rest = service.create_rest_client()
        capabilities = await service.get_server_capabilities_async()
    finally:
        key = ""
    _write_json(output / "server-capabilities.json", _jsonable(capabilities))

    archives: dict[int, Path] = {}
    try:
        for step in NEGATIVE_CONTROL_STEPS:
            state_path = STATE_PATHS[step]
            weights = await _get_weights_info(rest, state_path)
            _verify_weights_info(weights)
            weights_evidence = _weights_evidence(weights)
            client = await service.create_training_client_from_state_with_optimizer_async(
                state_path,
                user_metadata={"phase": "phase3r", "negative_control_step": str(step)},
            )
            info = await client.get_info_async()
            run = await rest.get_training_run_async(str(info.model_id))
            identity = _verify_info(info, run)
            _write_json(
                output / f"step-{step:03d}-identity.json",
                {"training_run": identity, "weights": weights_evidence},
            )
            sampler_receipt = await _resolve(
                await client.save_weights_for_sampler_async(
                    f"phase3r-negative-control-{step}", ttl_seconds=SAMPLER_TTL_SECONDS
                )
            )
            sampler_path = str(sampler_receipt.path)
            _write_json(
                output / f"step-{step:03d}-sampler.json",
                {
                    "path": sampler_path,
                    "state_path": state_path,
                    "ttl_seconds": SAMPLER_TTL_SECONDS,
                },
            )
            try:
                sampler = await service.create_sampling_client_async(model_path=sampler_path)
                sample_rows = await _sample_training_slice(
                    sampler=sampler,
                    step=step,
                    sampler_path=sampler_path,
                    selected_ids=selected_ids,
                    datums=datums,
                    prompts=prompts,
                    tokenizer=load_pinned_tokenizer(
                        root,
                        root / ".cache/replay-sources/995ad96eacd98c81ed38be0c5b274b04031597b0",
                    ).tokenizer,
                    output=output,
                )
                _write_json(
                    output / f"step-{step:03d}-train-metrics.json", _train_metrics(sample_rows)
                )
                archive_url = await _resolve(
                    rest.get_checkpoint_archive_url_from_tinker_path_async(sampler_path)
                )
                archive_path = archive_directory / f"phase3-sft-v1-step-{step:03d}-adapter.archive"
                archive_evidence = await asyncio.to_thread(
                    _download, str(archive_url.url), archive_path
                )
                archives[step] = archive_path
                _write_json(
                    output / f"step-{step:03d}-adapter.json",
                    {
                        **archive_evidence,
                        "local_path": str(archive_path),
                        "sampler_path": sampler_path,
                    },
                )
            finally:
                await rest.delete_checkpoint_from_tinker_path_async(sampler_path)
                _write_json(
                    output / f"step-{step:03d}-sampler-deletion.json",
                    {"deleted": True, "path": sampler_path},
                )
        tensor_report = await asyncio.to_thread(_tensor_report, archives, archive_directory)
        _write_json(output / "adapter-tensor-report.json", tensor_report)
        status["status"] = "preserved_locally_pending_drive_upload"
        status["archive_sha256"] = {
            str(step): _digest_file(path) for step, path in archives.items()
        }
        _write_json(output / "status.json", status)
        _write_sha256sums(output)
    except BaseException as error:
        status.update({"error_type": type(error).__name__, "status": "failed_sources_retained"})
        _write_json(output / "status.json", status)
        _write_sha256sums(output)
        raise


async def cleanup(
    *,
    root: Path,
    output: Path,
    source_commit: str,
    drive_receipt: Path,
    authorization_path: Path,
) -> None:
    authorization = load_authorization(authorization_path, cleanup_mode=True)
    verify_source(
        root,
        source_commit,
        authorization,
        authorization_kind="phase3r-negative-control-cleanup-owner-authorization-v1",
    )
    verify_launchd_execution()
    if (
        authorization.get("drive_receipt_sha256") != _digest_file(drive_receipt)
        or authorization.get("drive_verification_source") != "google-drive-api-readback"
    ):
        raise NegativeControlError("cleanup authorization does not bind verified Drive evidence")
    status = _read_json(output / "status.json")
    if status.get("status") != "preserved_locally_pending_drive_upload":
        raise NegativeControlError("local preservation did not complete")
    tensor_report = _read_json(output / "adapter-tensor-report.json")
    if tensor_report.get("validated") is not True:
        raise NegativeControlError("adapter tensor evidence is not validated")
    receipt = _read_json(drive_receipt)
    if (
        receipt.get("kind") != "phase3r-negative-control-drive-upload-receipt-v1"
        or receipt.get("drive_folder_id") != DRIVE_FOLDER_ID
        or receipt.get("verification_source") != "google-drive-api-readback"
    ):
        raise NegativeControlError("Drive receipt kind is not authorized")
    archives = receipt.get("archives")
    if not isinstance(archives, Mapping) or set(archives) != {"40", "63"}:
        raise NegativeControlError("Drive receipt does not bind both negative controls")
    for step in NEGATIVE_CONTROL_STEPS:
        local = _read_json(output / f"step-{step:03d}-adapter.json")
        uploaded = archives[str(step)]
        local_path = Path(str(local.get("local_path")))
        if (
            not isinstance(uploaded, Mapping)
            or uploaded.get("sha256") != local.get("sha256")
            or uploaded.get("bytes") != local.get("bytes")
            or uploaded.get("drive_folder_id") != DRIVE_FOLDER_ID
            or uploaded.get("private") is not True
            or uploaded.get("verified") is not True
            or not isinstance(uploaded.get("drive_file_id"), str)
            or not uploaded.get("drive_file_id")
            or not isinstance(uploaded.get("drive_url"), str)
            or not str(uploaded.get("drive_url")).startswith("https://drive.google.com/")
            or not local_path.is_file()
            or _digest_file(local_path) != local.get("sha256")
        ):
            raise NegativeControlError("Drive adapter hash does not match local evidence")
    key = read_tinker_api_key(root / ".env")
    try:
        service = tinker.ServiceClient(
            api_key=key,
            user_metadata={"phase": "phase3r", "purpose": "authorized-negative-control-cleanup"}
        )
        rest = service.create_rest_client()
    finally:
        key = ""
    deleted = {}
    for step, path in STATE_PATHS.items():
        await rest.delete_checkpoint_from_tinker_path_async(path)
        deleted[str(step)] = path
        _write_json(output / "full-state-deletion-progress.json", deleted)
    _write_json(
        output / "full-state-cleanup.json",
        {"deleted": deleted, "drive_receipt_sha256": _digest_file(drive_receipt)},
    )
    _write_sha256sums(output)


async def _sample_training_slice(
    *,
    sampler: Any,
    step: int,
    sampler_path: str,
    selected_ids: Sequence[str],
    datums: Mapping[str, Mapping[str, object]],
    prompts: Mapping[str, Sequence[int]],
    tokenizer: Any,
    output: Path,
) -> list[dict[str, object]]:
    raw_directory = output / f"step-{step:03d}-train-raw"
    grade_directory = output / f"step-{step:03d}-train-grades"
    raw_directory.mkdir(mode=0o700)
    grade_directory.mkdir(mode=0o700)

    async def one(datum_id: str) -> dict[str, object]:
        started = time.monotonic()
        response = await sampler.sample_async(
            prompt=tinker.ModelInput.from_ints(list(prompts[datum_id])),
            num_samples=1,
            sampling_params=tinker.SamplingParams(**SAMPLING),
        )
        if len(response.sequences) != 1:
            raise NegativeControlError("training-slice sampling returned the wrong sequence count")
        sequence = response.sequences[0]
        key = sha256(datum_id.encode()).hexdigest()
        raw = {
            "checkpoint_identity": sampler_path,
            "datum_id": datum_id,
            "finish_reason": str(sequence.stop_reason),
            "latency_ms": round((time.monotonic() - started) * 1000),
            "output_token_ids": list(sequence.tokens),
            "prompt_token_count": len(prompts[datum_id]),
            "step": step,
        }
        _write_json(raw_directory / f"{key}.json", raw)
        row = grade_training_output(
            datum=datums[datum_id],
            tokens=tuple(sequence.tokens),
            finish_reason=str(sequence.stop_reason),
            tokenizer=tokenizer,
        )
        row.update(
            {
                "checkpoint_identity": sampler_path,
                "datum_id": datum_id,
                "latency_ms": round((time.monotonic() - started) * 1000),
                "prompt_token_count": len(prompts[datum_id]),
                "step": step,
            }
        )
        row["raw_record_sha256"] = _digest_file(raw_directory / f"{key}.json")
        _write_json(grade_directory / f"{key}.json", row)
        return row

    rows = [await one(selected_ids[0])]
    semaphore = asyncio.Semaphore(4)

    async def limited(datum_id: str) -> dict[str, object]:
        async with semaphore:
            return await one(datum_id)

    rows.extend(await asyncio.gather(*(limited(datum_id) for datum_id in selected_ids[1:])))
    return rows


def _train_metrics(rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    totals, correct = Counter(), Counter()
    for row in rows:
        action = str(row.get("action_type", "invalid"))
        totals[action] += 1
        correct[action] += row.get("strict_match") is True
    return {
        "action_correct": dict(sorted(correct.items())),
        "action_total": dict(sorted(totals.items())),
        "strict_accuracy": sum(correct.values()) / len(rows),
        "strict_correct": sum(correct.values()),
        "total": len(rows),
    }


def _download(url: str, destination: Path) -> dict[str, object]:
    partial = destination.with_suffix(destination.suffix + ".part")
    digest = sha256()
    size = 0
    with urllib.request.urlopen(url, timeout=120) as response, partial.open("xb") as stream:  # noqa: S310
        while chunk := response.read(8 * 1024 * 1024):
            if size + len(chunk) > MAXIMUM_ARCHIVE_BYTES:
                raise NegativeControlError("adapter archive exceeds the 8 GiB ceiling")
            stream.write(chunk)
            digest.update(chunk)
            size += len(chunk)
        stream.flush()
        os.fsync(stream.fileno())
    if size == 0:
        raise NegativeControlError("downloaded adapter archive is empty")
    os.replace(partial, destination)
    return {"bytes": size, "sha256": f"sha256:{digest.hexdigest()}"}


def _tensor_report(archives: Mapping[int, Path], work: Path) -> dict[str, object]:
    extracted = {
        step: _extract_safetensors(path, work / f"step-{step:03d}-tensors")
        for step, path in archives.items()
    }
    indexes = {step: _tensor_index(paths) for step, paths in extracted.items()}
    if set(indexes[40]) != set(indexes[63]):
        raise NegativeControlError("negative-control tensor identities differ")
    aggregate: dict[str, dict[str, float | int]] = defaultdict(
        lambda: {
            "parameter_count": 0,
            "step_40_l2_sq": 0.0,
            "step_63_l2_sq": 0.0,
            "delta_l2_sq": 0.0,
        }
    )
    inventories: dict[str, list[dict[str, object]]] = {"40": [], "63": []}
    for name in sorted(indexes[40]):
        with (
            safe_open(indexes[40][name], framework="pt", device="cpu") as left_file,
            safe_open(indexes[63][name], framework="pt", device="cpu") as right_file,
        ):
            left = left_file.get_tensor(name)
            right = right_file.get_tensor(name)
            if tuple(left.shape) != tuple(right.shape) or left.dtype != right.dtype:
                raise NegativeControlError("negative-control tensor metadata differs")
            category = _tensor_category(name)
            if category == "other":
                raise NegativeControlError(f"unexpected adapter tensor category: {name}")
            metadata = {
                "category": category,
                "dtype": str(left.dtype),
                "name": name,
                "parameter_count": left.numel(),
                "shape": list(left.shape),
            }
            inventories["40"].append(metadata)
            inventories["63"].append(metadata)
            aggregate[category]["parameter_count"] += left.numel()
            for start in range(0, left.numel(), 1_000_000):
                a = left.reshape(-1)[start : start + 1_000_000].float()
                b = right.reshape(-1)[start : start + 1_000_000].float()
                aggregate[category]["step_40_l2_sq"] += float(torch.sum(a * a))
                aggregate[category]["step_63_l2_sq"] += float(torch.sum(b * b))
                aggregate[category]["delta_l2_sq"] += float(torch.sum((b - a) ** 2))
    if "attention" not in aggregate or not ({"mlp", "router_shared_moe"} & set(aggregate)):
        raise NegativeControlError("adapter tensor inventory lacks trained module categories")
    return {
        "by_module": {
            category: {
                "delta_l2": math.sqrt(float(values.pop("delta_l2_sq"))),
                "step_40_l2": math.sqrt(float(values.pop("step_40_l2_sq"))),
                "step_63_l2": math.sqrt(float(values.pop("step_63_l2_sq"))),
                **values,
            }
            for category, values in sorted(aggregate.items())
        },
        "kind": "phase3r-negative-control-adapter-tensor-report-v1",
        "tensor_count": len(indexes[40]),
        "tensor_inventory": inventories,
        "validated": True,
    }


def _extract_safetensors(archive: Path, destination: Path) -> list[Path]:
    destination.mkdir(mode=0o700)
    paths = []
    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as bundle:
            members = [name for name in bundle.namelist() if name.endswith(".safetensors")]
            _verify_archive_members(
                len(members), sum(bundle.getinfo(name).file_size for name in members), archive
            )
            for index, name in enumerate(members):
                target = destination / f"{index:03d}-{Path(name).name}"
                with bundle.open(name) as source, target.open("xb") as output:
                    while chunk := source.read(8 * 1024 * 1024):
                        output.write(chunk)
                paths.append(target)
    elif tarfile.is_tarfile(archive):
        with tarfile.open(archive) as bundle:
            members = [
                member
                for member in bundle.getmembers()
                if member.isfile() and member.name.endswith(".safetensors")
            ]
            _verify_archive_members(len(members), sum(member.size for member in members), archive)
            for index, member in enumerate(members):
                source = bundle.extractfile(member)
                if source is None:
                    raise NegativeControlError("adapter tensor member cannot be read")
                target = destination / f"{index:03d}-{Path(member.name).name}"
                with source, target.open("xb") as output:
                    while chunk := source.read(8 * 1024 * 1024):
                        output.write(chunk)
                paths.append(target)
    if not paths:
        raise NegativeControlError("adapter archive contains no safetensors")
    return paths


def _verify_archive_members(count: int, expanded_bytes: int, archive: Path) -> None:
    if count == 0 or count > MAXIMUM_ARCHIVE_MEMBERS:
        raise NegativeControlError("adapter archive tensor-member count is outside its ceiling")
    if expanded_bytes > MAXIMUM_EXTRACTED_BYTES:
        raise NegativeControlError("adapter archive exceeds the 16 GiB extraction ceiling")
    compressed = archive.stat().st_size
    if compressed == 0 or expanded_bytes > compressed * 8:
        raise NegativeControlError("adapter archive expansion ratio exceeds its ceiling")


def _tensor_index(paths: Sequence[Path]) -> dict[str, Path]:
    result = {}
    for path in paths:
        with safe_open(path, framework="pt", device="cpu") as tensors:
            for name in tensors.keys():
                if name in result:
                    raise NegativeControlError("adapter tensor identity repeats")
                result[name] = path
    return result


def _tensor_category(name: str) -> str:
    lowered = name.lower()
    if any(part in lowered for part in ("q_proj", "k_proj", "v_proj", "o_proj", "attn")):
        return "attention"
    if any(part in lowered for part in ("router", "expert", "moe")):
        return "router_shared_moe"
    if any(part in lowered for part in ("mlp", "up_proj", "down_proj", "gate_proj")):
        return "mlp"
    return "other"


def _load_datums(path: Path, selected: set[str]) -> dict[str, Mapping[str, object]]:
    result = {}
    with gzip.open(path, "rb") as stream:
        for line in stream:
            row = json.loads(line)
            if row.get("datum_id") in selected:
                result[str(row["datum_id"])] = row
    if set(result) != selected:
        raise NegativeControlError("training slice datum identities are incomplete")
    return result


async def _resolve(value: Any) -> Any:
    resolved = await value if inspect.isawaitable(value) else value
    return await resolved.result_async() if hasattr(resolved, "result_async") else resolved


async def _get_weights_info(rest: Any, path: str) -> Any:
    """The pinned SDK exposes this lookup as a sync method returning an async result handle."""
    return await _resolve(rest.get_weights_info_by_tinker_path(path))


def _jsonable(value: object) -> object:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, str | int | float | bool) or value is None:
        return value
    return repr(value)


def _read_json(path: Path) -> Mapping[str, object]:
    value = json.loads(path.read_bytes())
    if not isinstance(value, Mapping):
        raise NegativeControlError(f"JSON object expected: {path}")
    return value


def _write_json(path: Path, value: object) -> None:
    raw = canonical_artifact_bytes(value)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(raw)
    os.replace(temporary, path)


def _write_sha256sums(directory: Path) -> None:
    rows = []
    for path in sorted(directory.rglob("*")):
        if path.is_file() and path.name != "SHA256SUMS":
            rows.append(f"{sha256(path.read_bytes()).hexdigest()}  {path.relative_to(directory)}\n")
    (directory / "SHA256SUMS").write_text("".join(rows), encoding="ascii")


def _digest(raw: bytes) -> str:
    return f"sha256:{sha256(raw).hexdigest()}"


def _digest_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(8 * 1024 * 1024):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"
