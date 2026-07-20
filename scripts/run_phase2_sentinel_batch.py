#!/usr/bin/env python3
"""Run or resume the authorized eight-request WP2-1 sentinel Batch."""

from __future__ import annotations

import argparse
import asyncio
import fcntl
import json
import os
from contextlib import contextmanager
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

from dotenv import load_dotenv

from im.assets.model import canonical_artifact_bytes
from im.policy.prompted import ModelPricing, PromptArtifacts
from im.probes.harness.batch import (
    BatchDecoder,
    BatchShard,
    BatchWorkItem,
    decode_batch_completion,
    parse_batch_artifacts,
    shard_work,
)
from im.probes.harness.batch_api import (
    OpenAIBatchGateway,
    adopt_uncertain_batch,
    execute_batch_shard,
)
from im.probes.harness.cache import HarnessCache
from im.probes.harness.cost import usage_cost
from im.probes.harness.identity import cache_identity, digest
from im.probes.harness.models import HarnessProtocol, ProviderUsage

_MAX_ENQUEUED_TOKENS = 200_000


@dataclass(frozen=True, slots=True)
class SentinelBatchPlan:
    manifest: dict[str, object]
    targets: dict[str, dict[str, object]]
    shard: BatchShard
    execution: Path


@dataclass(frozen=True, slots=True)
class PacketBinding:
    packet: Path
    execution: Path
    checksum_sha256: str
    request_count: int
    stage: str


_PACKETS = {
    "sentinel-v2": PacketBinding(
        Path("review/phase2/sentinel-0-executable-v2"),
        Path("review/phase2/sentinel-0-executable-v2-execution"),
        "sha256:a9d13635488a7828b68eb4eab527dc9d96cc4d2b8a0e1d9ed4d1944d15891f01",
        8,
        "s0v2",
    ),
    "ambiguous-cancel-repair-v1": PacketBinding(
        Path("review/phase2/sentinel-0-ambiguous-cancel-repair-v1"),
        Path("review/phase2/sentinel-0-ambiguous-cancel-repair-v1-execution"),
        "sha256:9c7e3b3755c28a87a43d510bd2abfd1e20ebf5eb2294ae185b37e94660f7cde5",
        2,
        "s0r1",
    ),
}


def _amount(value: str) -> Decimal:
    try:
        amount = Decimal(value)
    except InvalidOperation as error:
        raise argparse.ArgumentTypeError("amount must be a decimal") from error
    if not amount.is_finite() or amount < 0:
        raise argparse.ArgumentTypeError("amount must be nonnegative and finite")
    return amount


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("plan", "run", "resume", "adopt"), default="plan")
    parser.add_argument("--packet", choices=tuple(_PACKETS), default="sentinel-v2")
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--approve-live-ceiling-usd", type=_amount)
    parser.add_argument("--batch-poll-seconds", type=float, default=600)
    parser.add_argument("--batch-id")
    parser.add_argument("--input-sha256")
    return parser.parse_args()


def load_plan(repository: Path, packet_name: str = "sentinel-v2") -> SentinelBatchPlan:
    binding = _PACKETS[packet_name]
    packet = repository / binding.packet
    _verify_packet(packet, binding.checksum_sha256)
    manifest_bytes = (packet / "teacher-plan.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    if not isinstance(manifest, dict):
        raise ValueError("sentinel teacher plan must be an object")
    if (
        manifest.get("authorization_state") != "not_authorized"
        or manifest.get("api_call_performed") is not False
        or manifest.get("request_count") != binding.request_count
        or manifest.get("shard_count") != 1
        or manifest.get("model") != "gpt-5.6-terra"
        or manifest.get("reasoning_effort") != "high"
    ):
        raise ValueError("sentinel teacher plan differs from the authorized offline plan")

    input_path = manifest.get("input_path")
    if not isinstance(input_path, str):
        raise ValueError("sentinel teacher input path is invalid")
    input_jsonl = (packet / input_path).read_bytes()
    if digest(input_jsonl) != manifest.get("input_sha256"):
        raise ValueError("sentinel teacher input digest changed")
    target_values = manifest.get("targets")
    if not isinstance(target_values, list) or len(target_values) != binding.request_count:
        raise ValueError("sentinel teacher target inventory is invalid")
    targets = {
        target["custom_id"]: target
        for target in target_values
        if isinstance(target, dict) and isinstance(target.get("custom_id"), str)
    }
    if len(targets) != binding.request_count:
        raise ValueError("sentinel teacher target identities are invalid")

    prompt_hash = PromptArtifacts.from_repository(repository).prompt_hash
    items = []
    for raw_line in input_jsonl.splitlines(keepends=True):
        line = json.loads(raw_line)
        custom_id = line.get("custom_id") if isinstance(line, dict) else None
        body = line.get("body") if isinstance(line, dict) else None
        target = targets.get(custom_id) if isinstance(custom_id, str) else None
        if not isinstance(body, dict) or target is None:
            raise ValueError("sentinel Batch line is not bound to one target")
        body_bytes = canonical_artifact_bytes(body)
        if digest(body_bytes) != target.get("request_body_sha256"):
            raise ValueError("sentinel Batch request body digest changed")
        identity = cache_identity(
            manifest_sha256=digest(manifest_bytes),
            probe_id=str(target["target_id"]),
            protocol=HarnessProtocol.GENERATION,
            variant_id="sentinel-v2",
            presentation=str(target["policy_prefix_sha256"]),
            model=str(manifest["model"]),
            reasoning_effort=str(manifest["reasoning_effort"]),
            prompt_hash=prompt_hash,
            request_bytes=body_bytes,
        )
        item = BatchWorkItem(
            custom_id=custom_id,
            identity=identity,
            body=body,
            prompt_hash=prompt_hash,
            decoder=BatchDecoder.ACTION,
        )
        if item.request_line != raw_line:
            raise ValueError("sentinel Batch line is not canonical")
        items.append(item)
    if any(not item.custom_id.startswith(f"{binding.stage}.") for item in items):
        raise ValueError("sentinel custom IDs differ from the bound packet stage")
    shards = shard_work(binding.stage, tuple(items), max_enqueued_tokens=_MAX_ENQUEUED_TOKENS)
    if len(shards) != 1 or shards[0].input_jsonl != input_jsonl:
        raise ValueError("sentinel Batch plan does not reproduce the sealed one-shard input")
    return SentinelBatchPlan(manifest, targets, shards[0], binding.execution)


async def _run(args: argparse.Namespace) -> None:
    repository = args.repository.resolve()
    load_dotenv(repository / ".env", override=False)
    plan = load_plan(repository, args.packet)
    ceiling = Decimal(str(plan.manifest["cost_estimate"]["approval_ceiling_usd"]))
    summary = {
        "approval_ceiling_usd": str(ceiling),
        "estimated_input_tokens": plan.shard.estimated_input_tokens,
        "input_sha256": plan.shard.input_sha256,
        "model": plan.manifest["model"],
        "reasoning_effort": plan.manifest["reasoning_effort"],
        "request_count": len(plan.shard.items),
    }
    print(json.dumps(summary, indent=2, sort_keys=True), flush=True)
    if args.mode == "plan":
        return
    execution = repository / plan.execution
    ledger = execution / "ledger.sqlite"
    if args.mode == "adopt":
        if args.input_sha256 != plan.shard.input_sha256 or not args.batch_id:
            raise ValueError("adopt requires this packet's input SHA-256 and a provider Batch ID")
        with _exclusive_lock(ledger), HarnessCache(ledger) as cache:
            adopted = adopt_uncertain_batch(
                cache,
                input_sha256=args.input_sha256,
                batch_id=args.batch_id,
            )
        print(json.dumps({"api_call_performed": False, **_job_state(adopted)}, indent=2))
        return
    if args.approve_live_ceiling_usd is None or args.approve_live_ceiling_usd < ceiling:
        raise ValueError(f"approved ceiling must be at least {ceiling}")
    if args.batch_poll_seconds <= 0:
        raise ValueError("batch poll seconds must be positive")
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise ValueError("OPENAI_API_KEY is required")

    execution.mkdir(parents=True, exist_ok=True)
    _write_json(execution / "plan.json", summary)
    gateway = OpenAIBatchGateway(
        api_key=api_key,
        organization_id=os.getenv("OPENAI_ORG_ID", "").strip() or None,
        project_id=os.getenv("OPENAI_PROJECT_ID", "").strip() or None,
    )
    try:
        with _exclusive_lock(ledger), HarnessCache(ledger) as cache:
            if args.mode == "resume" and cache.get_batch_job(plan.shard.input_sha256) is None:
                raise ValueError("resume requires this packet's existing Batch ledger")
            try:
                record = await execute_batch_shard(
                    plan.shard,
                    cache=cache,
                    gateway=gateway,
                    poll_seconds=args.batch_poll_seconds,
                )
            except BaseException:
                latest = cache.get_batch_job(plan.shard.input_sha256)
                if latest is not None:
                    _write_json(execution / "execution-state.json", _job_state(latest))
                raise
            _write_json(execution / "execution-state.json", _job_state(record))
    finally:
        await gateway.aclose()

    if record.latest_batch_json:
        _write(execution / "provider-batch.json", record.latest_batch_json)
    output_path = execution / str(plan.manifest["output_path"])
    _write(output_path, record.output_jsonl)
    _write(output_path.with_suffix(".errors.jsonl"), record.error_jsonl)
    if record.status != "completed":
        raise RuntimeError(f"sentinel Batch ended in terminal status {record.status!r}")

    artifacts = parse_batch_artifacts(
        plan.shard.items,
        output_jsonl=record.output_jsonl,
        error_jsonl=record.error_jsonl,
    )
    rows = []
    usage = ProviderUsage()
    for item in plan.shard.items:
        decoded = decode_batch_completion(
            item,
            artifacts[item.custom_id],
            batch_id=record.batch_id or "",
            stage=plan.shard.stage,
            shard_index=plan.shard.shard_index,
        )
        usage += decoded.completion.usage
        oracle = plan.targets[item.custom_id]["oracle_action"]
        teacher = decoded.completion.value
        rows.append(
            {
                "comparison": "equivalent" if teacher == oracle else "non_equivalent",
                "custom_id": item.custom_id,
                "oracle_action": oracle,
                "outcome": decoded.completion.outcome,
                "teacher_action": teacher,
                "validation_error": decoded.validation_error,
            }
        )
    comparison = {
        "batch_id": record.batch_id,
        "input_sha256": record.input_sha256,
        "provider_usage": usage.as_json(),
        "request_count": len(rows),
        "mandatory_review_count": len(rows),
        "non_equivalent_count": sum(row["comparison"] != "equivalent" for row in rows),
        "rows": rows,
        "usd": format(
            usage_cost(
                usage,
                ModelPricing(model=str(plan.manifest["model"])),
                billing_multiplier=Decimal("0.50"),
            ),
            "f",
        ),
    }
    _write_json(execution / "comparison.json", comparison)
    print(json.dumps(comparison, indent=2, sort_keys=True), flush=True)


def _job_state(record) -> dict[str, object]:
    return {
        "api_call_performed": record.status != "planned",
        "batch_id": record.batch_id,
        "input_file_id": record.input_file_id,
        "input_sha256": record.input_sha256,
        "status": record.status,
    }


def _verify_packet(
    packet: Path,
    expected_checksum_sha256: str = _PACKETS["sentinel-v2"].checksum_sha256,
) -> None:
    checksum_bytes = (packet / "SHA256SUMS").read_bytes()
    if digest(checksum_bytes) != expected_checksum_sha256:
        raise ValueError("sentinel packet checksum manifest changed")
    entries = checksum_bytes.decode("utf-8").splitlines()
    if len(entries) != 3:
        raise ValueError("sentinel packet checksum inventory changed")
    for entry in entries:
        checksum, separator, relative_path = entry.partition("  ")
        if not separator or digest((packet / relative_path).read_bytes()) != f"sha256:{checksum}":
            raise ValueError(f"sentinel packet member changed: {relative_path or '<invalid>'}")


def _write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_bytes(data)
    temporary.replace(path)


def _write_json(path: Path, value: object) -> None:
    _write(path, canonical_artifact_bytes(value))


@contextmanager
def _exclusive_lock(ledger: Path):
    lock_path = ledger.with_suffix(".lock")
    with lock_path.open("a+b") as lock_file:
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeError("another sentinel Batch process is already running") from error
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def main() -> None:
    asyncio.run(_run(_arguments()))


if __name__ == "__main__":
    main()
