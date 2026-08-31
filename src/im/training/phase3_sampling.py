"""Paid, raw-first WP3-2 untouched-backbone sampling."""

from __future__ import annotations

import asyncio
import gzip
import json
import os
import re
import subprocess
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

import tinker

from im.assets.model import canonical_artifact_bytes
from im.training.phase3_data import BACKBONE, PinnedTokenizer, guard_read_path
from im.training.phase3_eval import (
    FROZEN_SAMPLING_MANIFEST_SHA256,
    FROZEN_SAMPLING_REQUESTS_SHA256,
    PersistedRawGeneration,
    capture_raw_generation,
    compute_dev_metrics,
    grade_persisted_generation,
    persist_raw_generation,
    rebuild_dev_states,
)

REQUEST_COUNT = 360
DEV_COUNT = 300
RETENTION_COUNT = 60
MAXIMUM_SPEND_USD = 3.63
INPUT_USD_PER_MILLION = 0.54
OUTPUT_USD_PER_MILLION = 1.335
MAX_OUTPUT_TOKENS = 1024
CONCURRENCY = 8
ALLOWED_SECRET_NAME = "TINKER_API_KEY"
CHECKPOINT_IDENTITY = "untouched_backbone"
CANDIDATE_SHA256SUMS_SHA256 = (
    "sha256:b26ce03fbf46de2ed0b75c71ca925b79dee3d42d77e05f323271ffd5125dcace"
)
OFFLINE_APPROVAL_RELATIVE_PATH = Path(
    "review/phase3/wp3-2-offline-freeze-approval-v1/owner-approval.json"
)
OFFLINE_APPROVAL_SHA256 = (
    "sha256:c42672cd6ea52d18259ca3667574a9ccf6da9f876710be4c10b6ffabf3e21c65"
)


class Phase3SamplingError(ValueError):
    """A paid WP3-2 execution boundary failed closed."""


@dataclass(frozen=True, slots=True)
class SamplingContract:
    requests: tuple[Mapping[str, object], ...]
    manifest: Mapping[str, object]
    manifest_sha256: str
    requests_sha256: str
    authorization_sha256: str
    source_commit: str
    modeled_upper_usd: float


def load_sampling_contract(
    repository_root: Path,
    candidate_directory: Path,
    authorization_path: Path,
) -> SamplingContract:
    """Verify every owner-bound byte before secret access or provider work."""
    root = guard_read_path(repository_root, repository_root)
    candidate = guard_read_path(root, candidate_directory)
    _verify_candidate_checksums(root, candidate)
    offline_approval = guard_read_path(root, root / OFFLINE_APPROVAL_RELATIVE_PATH).read_bytes()
    if f"sha256:{sha256(offline_approval).hexdigest()}" != OFFLINE_APPROVAL_SHA256:
        raise Phase3SamplingError("offline owner approval drifted")
    manifest_path = guard_read_path(root, candidate / "sampling-request-manifest.json")
    manifest_bytes = manifest_path.read_bytes()
    manifest_sha = f"sha256:{sha256(manifest_bytes).hexdigest()}"
    if manifest_sha != FROZEN_SAMPLING_MANIFEST_SHA256:
        raise Phase3SamplingError("sampling manifest drifted")
    manifest = _json_object(manifest_bytes, "sampling manifest")

    compressed = guard_read_path(root, candidate / "sampling-requests.json.gz").read_bytes()
    try:
        request_bytes = gzip.decompress(compressed)
    except gzip.BadGzipFile as error:
        raise Phase3SamplingError("sampling requests are not the frozen gzip payload") from error
    requests_sha = f"sha256:{sha256(request_bytes).hexdigest()}"
    if requests_sha != FROZEN_SAMPLING_REQUESTS_SHA256:
        raise Phase3SamplingError("sampling requests drifted")
    try:
        raw_requests = json.loads(request_bytes)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise Phase3SamplingError("sampling requests are malformed") from error
    if (
        not isinstance(raw_requests, list)
        or canonical_artifact_bytes(raw_requests) != request_bytes
    ):
        raise Phase3SamplingError("sampling requests are not canonical")
    requests = tuple(_request_row(row) for row in raw_requests)
    _verify_request_inventory(requests, manifest)

    authorization_bytes = guard_read_path(root, authorization_path).read_bytes()
    authorization = _json_object(authorization_bytes, "owner authorization")
    authorization_sha = f"sha256:{sha256(authorization_bytes).hexdigest()}"
    source_commit = _verify_authorization(authorization, manifest_sha)

    pricing = manifest.get("pricing_projection")
    if not isinstance(pricing, Mapping):
        raise Phase3SamplingError("pricing projection is missing")
    input_tokens = sum(int(row["input_token_count"]) for row in requests)
    modeled_upper = (
        input_tokens * INPUT_USD_PER_MILLION
        + REQUEST_COUNT * MAX_OUTPUT_TOKENS * OUTPUT_USD_PER_MILLION
    ) / 1_000_000
    if (
        input_tokens != pricing.get("input_token_count")
        or pricing.get("max_output_token_count") != REQUEST_COUNT * MAX_OUTPUT_TOKENS
        or abs(float(pricing.get("modeled_upper_usd", -1)) - modeled_upper) > 1e-12
        or float(pricing.get("authorization_ceiling_usd", -1)) != MAXIMUM_SPEND_USD
        or modeled_upper > MAXIMUM_SPEND_USD
    ):
        raise Phase3SamplingError("sampling cost ceiling drifted")
    return SamplingContract(
        requests=requests,
        manifest=manifest,
        manifest_sha256=manifest_sha,
        requests_sha256=requests_sha,
        authorization_sha256=authorization_sha,
        source_commit=source_commit,
        modeled_upper_usd=modeled_upper,
    )


def verify_execution_source(
    repository_root: Path, source_commit: str, authorization_path: Path
) -> str:
    """Require a clean descendant whose only post-source change is the authorization packet."""
    root = guard_read_path(repository_root, repository_root)
    expected_auth = guard_read_path(root, authorization_path).relative_to(root).as_posix()
    commands = (
        ("rev-parse", "HEAD"),
        (
            "status",
            "--porcelain",
            "--untracked-files=all",
            "--",
            ".",
            ":(exclude)review/phase2/wp2-10-test-closeout/**",
        ),
        ("diff", "--name-only", f"{source_commit}..HEAD"),
    )
    outputs: list[str] = []
    environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    for arguments in commands:
        result = subprocess.run(
            ["git", *arguments],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
            env=environment,
        )
        if result.returncode != 0:
            raise Phase3SamplingError("source revision could not be verified")
        outputs.append(result.stdout.strip())
    if outputs[1]:
        raise Phase3SamplingError("source worktree is not clean")
    changed = {line for line in outputs[2].splitlines() if line}
    if changed != {expected_auth}:
        raise Phase3SamplingError("post-source revision contains unauthorized changes")
    return outputs[0]


def read_tinker_api_key(env_path: Path) -> str:
    """Extract only TINKER_API_KEY without evaluating any dotenv content."""
    matches: list[str] = []
    with env_path.open(encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            name, value = stripped.split("=", 1)
            if name.strip().removeprefix("export ").strip() != ALLOWED_SECRET_NAME:
                continue
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
                value = value[1:-1]
            matches.append(value)
    if len(matches) != 1 or not matches[0]:
        raise Phase3SamplingError(".env must contain exactly one nonempty TINKER_API_KEY")
    return matches[0]


async def execute_backbone_sampling(
    *,
    repository_root: Path,
    candidate_directory: Path,
    authorization_path: Path,
    tokenizer: PinnedTokenizer,
    output_directory: Path,
    evaluation_run_id: str,
    job_label: str,
) -> dict[str, object]:
    """Run one owner-authorized baseline with SDK retries only and immutable raw evidence."""
    started = time.monotonic()
    contract = load_sampling_contract(repository_root, candidate_directory, authorization_path)
    execution_commit = verify_execution_source(
        repository_root, contract.source_commit, authorization_path
    )
    output = guard_read_path(repository_root, output_directory)
    try:
        output_relative = output.relative_to(repository_root)
    except ValueError as error:
        raise Phase3SamplingError("output directory must be inside repository_root") from error
    if (
        output_relative == Path(".")
        or output.exists()
        or re.fullmatch(r"[a-z0-9][a-z0-9._-]{7,127}", evaluation_run_id) is None
        or re.fullmatch(r"[a-z0-9][a-z0-9.-]{7,127}", job_label) is None
    ):
        raise Phase3SamplingError("output or execution identity failed preflight")
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    status_path = output / "status.json"
    state: dict[str, object] = {
        "authorization_sha256": contract.authorization_sha256,
        "completed_requests": 0,
        "evaluation_run_id": evaluation_run_id,
        "execution_commit": execution_commit,
        "job_label": job_label,
        "kind": "phase3-wp3-2-detached-status",
        "phase": "preflight_complete",
        "request_count": REQUEST_COUNT,
        "sampling_manifest_sha256": contract.manifest_sha256,
        "source_commit": contract.source_commit,
        "status": "running",
    }
    _write_status(status_path, state)

    try:
        key = read_tinker_api_key(repository_root / ".env")
        os.environ[ALLOWED_SECRET_NAME] = key
        try:
            service = tinker.ServiceClient(
                user_metadata={
                    "phase": "wp3-2",
                    "purpose": "untouched-backbone-baseline",
                    "run_id": evaluation_run_id,
                }
            )
            client = await service.create_sampling_client_async(base_model=BACKBONE)
        finally:
            os.environ.pop(ALLOWED_SECRET_NAME, None)
            key = ""
    except BaseException as error:
        state.update(
            {
                "error_type": type(error).__name__,
                "phase": "failed",
                "status": "failed",
            }
        )
        _write_status(status_path, state)
        raise

    sampling = contract.manifest["sampling"]
    params = tinker.SamplingParams(**dict(sampling))
    persisted_by_id: dict[str, PersistedRawGeneration] = {}
    index_by_id: dict[str, dict[str, object]] = {}
    failures: list[dict[str, object]] = []
    cache_hit_tokens = 0
    output_tokens = 0
    settled_requests = 0

    async def sample_one(row: Mapping[str, object]) -> None:
        nonlocal cache_hit_tokens, output_tokens
        request_id = str(row["request_id"])
        prompt = tinker.ModelInput.from_ints(list(row["input_token_ids"]))
        before = time.monotonic()
        response = await client.sample_async(
            prompt=prompt,
            num_samples=1,
            sampling_params=params,
        )
        latency_ms = round((time.monotonic() - before) * 1000)
        if len(response.sequences) != 1:
            raise Phase3SamplingError("Tinker returned an unexpected sample count")
        sequence = response.sequences[0]
        tokens = tuple(sequence.tokens)
        decoded = tokenizer.tokenizer.decode(tokens, skip_special_tokens=False)
        if not isinstance(decoded, str):
            raise Phase3SamplingError("pinned tokenizer failed to decode output tokens")
        raw = capture_raw_generation(
            evaluation_run_id=evaluation_run_id,
            model_identity=BACKBONE,
            checkpoint_identity=CHECKPOINT_IDENTITY,
            sampling_manifest_sha256=contract.manifest_sha256,
            state_id=request_id,
            output_token_ids=tokens,
            decoded_bytes=decoded.encode(),
            finish_reason=str(sequence.stop_reason),
            latency_ms=latency_ms,
        )
        persisted = persist_raw_generation(repository_root, output / "raw", raw)
        persisted_by_id[request_id] = persisted
        cache_hit_tokens += int(response.prompt_cache_hit_tokens)
        output_tokens += len(tokens)
        index_by_id[request_id] = {
            "cache_hit_prompt_tokens": int(response.prompt_cache_hit_tokens),
            "finish_reason": str(sequence.stop_reason),
            "input_token_count": int(row["input_token_count"]),
            "kind": row["kind"],
            "latency_ms": latency_ms,
            "output_token_count": len(tokens),
            "path": persisted.path.relative_to(repository_root).as_posix(),
            "request_id": request_id,
            "sha256": persisted.sha256,
        }
        state.update(
            {
                "cache_hit_prompt_tokens": cache_hit_tokens,
                "completed_requests": len(persisted_by_id),
                "last_request_id": request_id,
                "output_tokens": output_tokens,
                "phase": "sampling",
            }
        )
        _write_status(status_path, state)
        if len(persisted_by_id) % 10 == 0:
            print(f"persisted {len(persisted_by_id)}/{REQUEST_COUNT} raw generations", flush=True)

    async def attempt_once(row: Mapping[str, object]) -> None:
        nonlocal settled_requests
        request_id = str(row["request_id"])
        try:
            await sample_one(row)
        except Exception as error:
            failures.append(
                {
                    "error_type": type(error).__name__,
                    "kind": row["kind"],
                    "request_id": request_id,
                }
            )
        settled_requests += 1
        state.update(
            {
                "failed_requests": len(failures),
                "last_settled_request_id": request_id,
                "persisted_requests": len(persisted_by_id),
                "settled_requests": settled_requests,
            }
        )
        _write_status(status_path, state)

    try:
        interactions = contract.requests[:DEV_COUNT]
        retention = contract.requests[DEV_COUNT:]
        await attempt_once(interactions[0])
        semaphore = asyncio.Semaphore(CONCURRENCY)

        async def controlled(row: Mapping[str, object]) -> None:
            async with semaphore:
                await attempt_once(row)

        await asyncio.gather(*(controlled(row) for row in interactions[1:]))
        await asyncio.gather(*(controlled(row) for row in retention))
        if settled_requests != REQUEST_COUNT:
            raise Phase3SamplingError("sampling did not settle exactly 360 one-shot requests")
        if failures:
            ordered_index = [
                index_by_id[str(row["request_id"])]
                for row in contract.requests
                if str(row["request_id"]) in index_by_id
            ]
            failure_bytes = b"".join(
                canonical_artifact_bytes(failure) + b"\n"
                for failure in sorted(failures, key=lambda item: str(item["request_id"]))
            )
            incomplete = {
                "authorization_sha256": contract.authorization_sha256,
                "completed_requests": len(persisted_by_id),
                "evaluation_run_id": evaluation_run_id,
                "failed_requests": len(failures),
                "kind": "phase3-wp3-2-incomplete-backbone-report",
                "maximum_spend_usd": MAXIMUM_SPEND_USD,
                "model": BACKBONE,
                "request_count": REQUEST_COUNT,
                "sampling_manifest_sha256": contract.manifest_sha256,
                "sealed_test": "unread",
                "settled_requests": settled_requests,
                "source_commit": contract.source_commit,
            }
            incomplete_files = {
                "failures.jsonl": failure_bytes,
                "raw-index.json": canonical_artifact_bytes(ordered_index),
                "run-report.json": canonical_artifact_bytes(incomplete),
            }
            _publish_root_files(repository_root, output, incomplete_files, ordered_index)
            raise Phase3SamplingError(
                "one or more one-shot requests failed; no output was repaired or resampled"
            )
        if len(persisted_by_id) != REQUEST_COUNT:
            raise Phase3SamplingError("sampling did not persist exactly 360 raw records")

        state.update({"phase": "offline_grading"})
        _write_status(status_path, state)
        dev_states = await rebuild_dev_states(repository_root, tokenizer)
        dev_persisted = tuple(persisted_by_id[str(row["request_id"])] for row in interactions)
        expected_identity = (
            evaluation_run_id,
            BACKBONE,
            CHECKPOINT_IDENTITY,
            contract.manifest_sha256,
        )
        metrics = compute_dev_metrics(
            repository_root,
            dev_states,
            dev_persisted,
            expected_evaluation_identity=expected_identity,
            tokenizer=tokenizer.tokenizer,
        )
        dev_by_id = {item.state_id: item for item in dev_states}
        grades = [
            grade_persisted_generation(
                repository_root,
                dev_by_id[str(row["request_id"])],
                persisted_by_id[str(row["request_id"])],
                tokenizer=tokenizer.tokenizer,
            )
            for row in interactions
        ]
        ordered_index = [index_by_id[str(row["request_id"])] for row in contract.requests]
        report = {
            "authorization_sha256": contract.authorization_sha256,
            "cache_hit_prompt_tokens": cache_hit_tokens,
            "checkpoint_creation_count": 0,
            "checkpoint_identity": CHECKPOINT_IDENTITY,
            "completed_requests": REQUEST_COUNT,
            "concurrency": CONCURRENCY,
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "evaluation_run_id": evaluation_run_id,
            "execution_commit": execution_commit,
            "external_retries": 0,
            "input_tokens": sum(int(row["input_token_count"]) for row in contract.requests),
            "kind": "phase3-wp3-2-untouched-backbone-report",
            "maximum_spend_usd": MAXIMUM_SPEND_USD,
            "model": BACKBONE,
            "modeled_uncached_upper_usd": contract.modeled_upper_usd,
            "output_tokens": output_tokens,
            "provider_spend_observed_usd": None,
            "request_count": REQUEST_COUNT,
            "sampling_manifest_sha256": contract.manifest_sha256,
            "sampling_requests_sha256": contract.requests_sha256,
            "sealed_test": "unread",
            "source_commit": contract.source_commit,
        }
        files = {
            "dev-grades.jsonl": b"".join(
                canonical_artifact_bytes(grade) + b"\n" for grade in grades
            ),
            "dev-metrics.json": canonical_artifact_bytes(metrics),
            "raw-index.json": canonical_artifact_bytes(ordered_index),
            "run-report.json": canonical_artifact_bytes(report),
        }
        _publish_root_files(repository_root, output, files, ordered_index)
        state.update(
            {
                "finished": True,
                "phase": "complete",
                "report_sha256": f"sha256:{sha256(files['run-report.json']).hexdigest()}",
                "status": "complete",
            }
        )
        _write_status(status_path, state)
        print("WP3-2 backbone baseline complete", flush=True)
        return report
    except BaseException as error:
        state.update(
            {
                "error_type": type(error).__name__,
                "phase": "failed",
                "status": "failed",
            }
        )
        _write_status(status_path, state)
        raise


def _request_row(value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise Phase3SamplingError("sampling request row is malformed")
    required = {
        "input_token_count",
        "input_token_ids",
        "input_token_ids_sha256",
        "kind",
        "messages",
        "messages_sha256",
        "request_id",
    }
    if set(value) != required:
        raise Phase3SamplingError("sampling request fields drifted")
    tokens = value.get("input_token_ids")
    if (
        not isinstance(tokens, list)
        or any(
            isinstance(token, bool) or not isinstance(token, int) or token < 0
            for token in tokens
        )
        or value.get("input_token_count") != len(tokens)
        or value.get("input_token_ids_sha256")
        != f"sha256:{sha256(canonical_artifact_bytes(tokens)).hexdigest()}"
    ):
        raise Phase3SamplingError("sampling request token identity drifted")
    return value


def _verify_request_inventory(
    requests: Sequence[Mapping[str, object]], manifest: Mapping[str, object]
) -> None:
    ids = [str(row.get("request_id")) for row in requests]
    kinds = [row.get("kind") for row in requests]
    sampling = manifest.get("sampling")
    expected_sampling = {
        "max_tokens": MAX_OUTPUT_TOKENS,
        "seed": 20260801,
        "stop": [248046],
        "temperature": 0.0,
        "top_k": -1,
        "top_p": 1.0,
    }
    if (
        len(requests) != REQUEST_COUNT
        or len(set(ids)) != REQUEST_COUNT
        or kinds[:DEV_COUNT] != ["interaction_dev"] * DEV_COUNT
        or kinds[DEV_COUNT:] != ["retention"] * RETENTION_COUNT
        or manifest.get("request_count") != REQUEST_COUNT
        or manifest.get("dev_count") != DEV_COUNT
        or manifest.get("retention_count") != RETENTION_COUNT
        or manifest.get("model") != BACKBONE
        or sampling != expected_sampling
    ):
        raise Phase3SamplingError("sampling request inventory drifted")


def _verify_authorization(authorization: Mapping[str, object], manifest_sha: str) -> str:
    forbidden = authorization.get("forbidden_operations")
    source_commit = authorization.get("source_commit")
    if (
        authorization.get("kind") != "phase3-wp3-2-paid-backbone-owner-authorization"
        or authorization.get("owner_decision") != "authorized"
        or authorization.get("sampling_manifest_sha256") != manifest_sha
        or authorization.get("candidate_sha256sums_sha256")
        != CANDIDATE_SHA256SUMS_SHA256
        or authorization.get("offline_freeze_owner_approval_sha256")
        != OFFLINE_APPROVAL_SHA256
        or authorization.get("maximum_spend_usd") != MAXIMUM_SPEND_USD
        or authorization.get("allowed_secret_name") != ALLOWED_SECRET_NAME
        or authorization.get("request_count") != REQUEST_COUNT
        or authorization.get("model") != BACKBONE
        or authorization.get("detached_execution_required") is not True
        or not isinstance(forbidden, list)
        or set(forbidden)
        != {"checkpoint_creation", "sealed_test_access", "training_client", "output_repair"}
        or not isinstance(source_commit, str)
        or re.fullmatch(r"[0-9a-f]{40}", source_commit) is None
    ):
        raise Phase3SamplingError("paid owner authorization is malformed or incomplete")
    return source_commit


def _verify_candidate_checksums(repository_root: Path, candidate: Path) -> None:
    manifest_path = guard_read_path(repository_root, candidate / "SHA256SUMS")
    manifest_bytes = manifest_path.read_bytes()
    if f"sha256:{sha256(manifest_bytes).hexdigest()}" != CANDIDATE_SHA256SUMS_SHA256:
        raise Phase3SamplingError("candidate checksum manifest drifted")
    seen: set[str] = set()
    for line in manifest_bytes.decode("ascii").splitlines():
        try:
            expected, name = line.split("  ", 1)
        except ValueError as error:
            raise Phase3SamplingError("candidate checksum line is malformed") from error
        if re.fullmatch(r"[0-9a-f]{64}", expected) is None or Path(name).name != name:
            raise Phase3SamplingError("candidate checksum entry is unsafe")
        if name in seen:
            raise Phase3SamplingError("candidate checksum entry repeats")
        seen.add(name)
        raw = guard_read_path(repository_root, candidate / name).read_bytes()
        if sha256(raw).hexdigest() != expected:
            raise Phase3SamplingError(f"candidate artifact drifted: {name}")
    if seen != {
        "artifact-bindings.json",
        "dev-state-inventory.jsonl.gz",
        "fast-sentinel-manifest.json",
        "grader-contract.json",
        "grader-fixture-report.json",
        "retention-blind-template.json",
        "sampling-request-manifest.json",
        "sampling-requests.json.gz",
        "wp3-2-offline-report.json",
    }:
        raise Phase3SamplingError("candidate checksum inventory drifted")


def _json_object(raw: bytes, label: str) -> Mapping[str, object]:
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise Phase3SamplingError(f"{label} is malformed") from error
    if not isinstance(value, Mapping):
        raise Phase3SamplingError(f"{label} is not an object")
    return value


def _write_status(path: Path, value: Mapping[str, object]) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_bytes(canonical_artifact_bytes(dict(value)))
    os.replace(temporary, path)


def _write_create_only(path: Path, content: bytes) -> None:
    with path.open("xb") as handle:
        handle.write(content)


def _publish_root_files(
    repository_root: Path,
    output: Path,
    files: Mapping[str, bytes],
    raw_index: Sequence[Mapping[str, object]],
) -> None:
    for name, content in files.items():
        _write_create_only(output / name, content)
    checksum_lines = [
        f"{sha256(content).hexdigest()}  {name}\n" for name, content in sorted(files.items())
    ]
    output_relative = output.relative_to(repository_root)
    checksum_lines.extend(
        f"{str(entry['sha256']).removeprefix('sha256:')}  "
        f"{Path(str(entry['path'])).relative_to(output_relative).as_posix()}\n"
        for entry in raw_index
    )
    _write_create_only(output / "SHA256SUMS", "".join(checksum_lines).encode())
