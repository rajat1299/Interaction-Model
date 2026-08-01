#!/usr/bin/env python3
"""Plan, run, resume, or adopt the detached v2 timer Wave-1 repair Batch."""
# ruff: noqa: E501

from __future__ import annotations

import argparse
import asyncio
import fcntl
import json
import os
from collections.abc import Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

from dotenv import load_dotenv

from im.assets.model import canonical_artifact_bytes
from im.config import estimate_tokens
from im.policy.prompted import ModelPricing
from im.probes.harness.batch import (
    BatchShard,
    BatchWorkItem,
    decode_batch_completion,
    parse_batch_artifacts,
)
from im.probes.harness.batch_api import (
    OpenAIBatchGateway,
    adopt_uncertain_batch,
    execute_batch_shard,
)
from im.probes.harness.cache import HarnessCache
from im.probes.harness.cost import usage_cost
from im.probes.harness.identity import digest
from im.probes.harness.models import BatchJobRecord, ProviderUsage
from im.schema.actions import ACTION_ADAPTER

_EXPECTED_DECISIONS = 10
_MAX_ENQUEUED_TOKENS = 700_000
_MANDATORY_ACTIONS = frozenset({"schedule", "cancel", "skip", "nudge"})
_PACKET = Path("review/phase2/timer-wave-1-repair")
_EXECUTION = Path("review/phase2/timer-wave-1-repair-execution")


class TimerWave1RepairRunError(RuntimeError):
    """The signed v2 repair plan cannot be safely executed or reported."""


@dataclass(frozen=True, slots=True)
class RepairBatchPlan:
    packet: Path
    packet_sha256: str
    manifest: dict[str, object]
    targets: dict[str, dict[str, object]]
    items: tuple[BatchWorkItem, ...]
    shards: tuple[BatchShard, ...]
    approval_ceiling_usd: Decimal


def _amount(value: str) -> Decimal:
    try:
        amount = Decimal(value)
    except InvalidOperation as error:
        raise argparse.ArgumentTypeError("amount must be a decimal") from error
    if not amount.is_finite() or amount < 0:
        raise argparse.ArgumentTypeError("amount must be nonnegative and finite")
    return amount


def _positive_seconds(value: str) -> float:
    seconds = float(value)
    if seconds <= 0:
        raise argparse.ArgumentTypeError("seconds must be positive")
    return seconds


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("plan", "run", "resume", "adopt"), default="plan")
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--approve-live-ceiling-usd", type=_amount)
    parser.add_argument("--batch-poll-seconds", type=_positive_seconds, default=300)
    parser.add_argument("--batch-id")
    parser.add_argument("--input-sha256")
    return parser.parse_args()


async def _build_plan(repository: Path):
    from im.generation.phase2_timer_wave1_repair import build_timer_wave1_repair_plan

    return await build_timer_wave1_repair_plan(repository_root=repository)


async def load_plan(
    repository: Path,
    *,
    build_plan=None,
    packet_relative_path: Path = _PACKET,
    expected_decisions: int = _EXPECTED_DECISIONS,
) -> RepairBatchPlan:
    planner = _build_plan if build_plan is None else build_plan
    raw = await planner(repository)
    files = getattr(raw, "files", None)
    if not isinstance(files, Mapping) or not all(
        isinstance(path, str) and isinstance(data, bytes) for path, data in files.items()
    ):
        raise TimerWave1RepairRunError("repair planner did not return canonical packet files")
    packet = repository / packet_relative_path
    for relative_path, data in files.items():
        path = packet / relative_path
        if not path.is_file() or path.read_bytes() != data:
            raise TimerWave1RepairRunError(f"repair planner did not materialize {relative_path}")
    manifest = _json_object(files.get("teacher-plan.json"), "teacher plan")
    targets = _targets(manifest)
    items = tuple(getattr(raw, "items", ()))
    shards = tuple(getattr(raw, "shards", ()))
    _validate_plan(manifest, targets, items, shards, expected_decisions=expected_decisions)
    return RepairBatchPlan(
        packet=packet,
        packet_sha256=_verify_packet(packet),
        manifest=manifest,
        targets=targets,
        items=items,
        shards=shards,
        approval_ceiling_usd=_ceiling(manifest),
    )


def _validate_plan(
    manifest: dict[str, object],
    targets: dict[str, dict[str, object]],
    items: tuple[BatchWorkItem, ...],
    shards: tuple[BatchShard, ...],
    *,
    expected_decisions: int = _EXPECTED_DECISIONS,
) -> None:
    if (
        manifest.get("model") != "gpt-5.6-terra"
        or manifest.get("reasoning_effort") != "high"
        or manifest.get("decision_count") != expected_decisions
        or manifest.get("request_count") != expected_decisions
        or manifest.get("max_enqueued_tokens") != _MAX_ENQUEUED_TOKENS
        or len(items) != expected_decisions
        or len(shards) != 1
    ):
        raise TimerWave1RepairRunError(
            "repair plan differs from its signed model, count, or shard configuration"
        )
    shard = shards[0]
    if (
        shard.shard_index != 0
        or shard.estimated_input_tokens > _MAX_ENQUEUED_TOKENS
        or shard.input_jsonl != b"".join(item.request_line for item in shard.items)
        or shard.input_sha256 != digest(shard.input_jsonl)
        or shard.estimated_input_tokens
        != sum(estimate_tokens(item.request_bytes) for item in shard.items)
        or tuple(shard.items) != items
        or len(targets) != len(items)
        or set(targets) != {item.custom_id for item in items}
    ):
        raise TimerWave1RepairRunError("repair plan does not reproduce its one signed shard")
    manifest_shards = manifest.get("shards")
    if not isinstance(manifest_shards, list) or len(manifest_shards) != 1:
        raise TimerWave1RepairRunError("repair shard manifest is invalid")
    expected = {
        "estimated_input_tokens": shard.estimated_input_tokens,
        "input_sha256": shard.input_sha256,
        "request_count": len(shard.items),
        "shard_index": 0,
        "stage": shard.stage,
    }
    if not isinstance(manifest_shards[0], dict) or any(
        manifest_shards[0].get(key) != value for key, value in expected.items()
    ):
        raise TimerWave1RepairRunError("repair shard manifest drifted")
    for item in items:
        target = targets[item.custom_id]
        if (
            target.get("request_body_sha256") != digest(canonical_artifact_bytes(item.body))
            or target.get("prompt_hash") != item.prompt_hash
        ):
            raise TimerWave1RepairRunError(f"repair request binding drifted for {item.custom_id}")
        try:
            ACTION_ADAPTER.validate_python(target.get("oracle_action"))
        except ValueError as error:
            raise TimerWave1RepairRunError(
                f"repair oracle action is invalid for {item.custom_id}"
            ) from error


async def _run(
    args: argparse.Namespace,
    *,
    build_plan=None,
    packet_relative_path: Path = _PACKET,
    execution_relative_path: Path = _EXECUTION,
    expected_decisions: int = _EXPECTED_DECISIONS,
    gateway_factory=None,
) -> None:
    repository = args.repository.resolve()
    load_dotenv(repository / ".env", override=False)
    plan = await load_plan(
        repository,
        build_plan=build_plan,
        packet_relative_path=packet_relative_path,
        expected_decisions=expected_decisions,
    )
    summary = _plan_summary(plan, packet_relative_path=packet_relative_path)
    print(json.dumps(summary, indent=2, sort_keys=True), flush=True)
    if args.mode == "plan":
        return
    execution = repository / execution_relative_path
    ledger = execution / "ledger.sqlite"
    if args.mode == "adopt":
        _adopt(args, plan, ledger, execution)
        return
    if args.approve_live_ceiling_usd != plan.approval_ceiling_usd:
        raise TimerWave1RepairRunError(
            "repair execution requires --approve-live-ceiling-usd exactly "
            f"{plan.approval_ceiling_usd}"
        )
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise TimerWave1RepairRunError("OPENAI_API_KEY is required for repair Batch execution")
    execution.mkdir(parents=True, exist_ok=True)
    _write_json(execution / "plan.json", summary)
    gateway_class = OpenAIBatchGateway if gateway_factory is None else gateway_factory
    gateway = gateway_class(
        api_key=api_key,
        organization_id=os.getenv("OPENAI_ORG_ID", "").strip() or None,
        project_id=os.getenv("OPENAI_PROJECT_ID", "").strip() or None,
    )
    try:
        with _exclusive_lock(ledger), HarnessCache(ledger) as cache:
            shard = plan.shards[0]
            if args.mode == "resume" and cache.get_batch_job(shard.input_sha256) is None:
                raise TimerWave1RepairRunError("resume requires an existing repair Batch ledger")
            record = await execute_batch_shard(
                shard, cache=cache, gateway=gateway, poll_seconds=args.batch_poll_seconds
            )
            _write_record(_shard_output(execution, shard), record)
    finally:
        await gateway.aclose()
    if record.status != "completed":
        raise TimerWave1RepairRunError(
            f"repair Batch shard ended in terminal status {record.status!r}"
        )
    comparison = _comparison(plan, record, execution)
    _write_json(execution / "comparison.json", comparison)
    print(json.dumps(comparison, indent=2, sort_keys=True), flush=True)


def _adopt(args: argparse.Namespace, plan: RepairBatchPlan, ledger: Path, execution: Path) -> None:
    shard = plan.shards[0]
    if args.input_sha256 != shard.input_sha256 or not args.batch_id:
        raise TimerWave1RepairRunError(
            "adopt requires the planned input SHA-256 and a provider Batch ID"
        )
    with _exclusive_lock(ledger), HarnessCache(ledger) as cache:
        existing = cache.get_batch_job(shard.input_sha256)
        if existing is None or (existing.stage, existing.shard_index) != (
            shard.stage,
            shard.shard_index,
        ):
            raise TimerWave1RepairRunError("adopt input is not an unresolved repair ledger shard")
        adopted = adopt_uncertain_batch(
            cache, input_sha256=shard.input_sha256, batch_id=args.batch_id
        )
    _write_json(_shard_output(execution, shard) / "execution-state.json", _job_state(adopted))
    print(
        json.dumps({"api_call_performed": False, **_job_state(adopted)}, indent=2, sort_keys=True)
    )


def _comparison(
    plan: RepairBatchPlan, record: BatchJobRecord, execution: Path
) -> dict[str, object]:
    shard = plan.shards[0]
    artifacts = parse_batch_artifacts(
        shard.items, output_jsonl=record.output_jsonl, error_jsonl=record.error_jsonl
    )
    rows, usage = [], ProviderUsage()
    for item in shard.items:
        target = plan.targets[item.custom_id]
        decoded = decode_batch_completion(
            item,
            artifacts[item.custom_id],
            batch_id=record.batch_id or "",
            stage=shard.stage,
            shard_index=0,
        )
        usage += decoded.completion.usage
        teacher = decoded.completion.value
        equivalent = (
            decoded.completion.outcome == "completed"
            and decoded.validation_error is None
            and teacher == target["oracle_action"]
        )
        reasons = list(target.get("mandatory_review_reasons", ()))
        if (
            isinstance(teacher, dict)
            and teacher.get("type") in _MANDATORY_ACTIONS
            and "mandatory_action" not in reasons
        ):
            reasons.append("mandatory_action")
        if not equivalent:
            reasons.append("teacher_oracle_disagreement")
        rows.append(
            {
                "comparison": "equivalent" if equivalent else "non_equivalent",
                "custom_id": item.custom_id,
                "mandatory_review": bool(reasons),
                "mandatory_review_reasons": reasons,
                "oracle_action": target["oracle_action"],
                "teacher_action": teacher,
                "validation_error": decoded.validation_error,
            }
        )
    _write_json(_shard_output(execution, shard) / "comparison.json", {"rows": rows})
    return {
        "batch_ids": [record.batch_id],
        "mandatory_review_count": sum(row["mandatory_review"] for row in rows),
        "non_equivalent_count": sum(row["comparison"] != "equivalent" for row in rows),
        "packet_sha256": plan.packet_sha256,
        "provider_usage": usage.as_json(),
        "request_count": len(rows),
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


def _targets(manifest: dict[str, object]) -> dict[str, dict[str, object]]:
    raw = manifest.get("targets")
    if not isinstance(raw, list):
        raise TimerWave1RepairRunError("repair plan has no target inventory")
    targets = {
        target.get("custom_id"): target
        for target in raw
        if isinstance(target, dict) and isinstance(target.get("custom_id"), str)
    }
    if len(targets) != len(raw):
        raise TimerWave1RepairRunError("repair target identities are invalid")
    return targets


def _ceiling(manifest: dict[str, object]) -> Decimal:
    estimate = manifest.get("cost_estimate")
    value = estimate.get("approval_ceiling_usd") if isinstance(estimate, dict) else None
    try:
        ceiling = Decimal(str(value))
    except (InvalidOperation, ValueError) as error:
        raise TimerWave1RepairRunError("repair plan has no valid approval ceiling") from error
    if not ceiling.is_finite() or ceiling <= 0:
        raise TimerWave1RepairRunError("repair plan has no positive approval ceiling")
    return ceiling


def _plan_summary(
    plan: RepairBatchPlan, *, packet_relative_path: Path = _PACKET
) -> dict[str, object]:
    shard = plan.shards[0]
    return {
        "api_call_performed": False,
        "approval_ceiling_usd": format(plan.approval_ceiling_usd, "f"),
        "estimated_input_tokens": shard.estimated_input_tokens,
        "model": plan.manifest["model"],
        "packet": str(packet_relative_path),
        "packet_sha256": plan.packet_sha256,
        "prompt_hash": plan.manifest["prompt_hash"],
        "request_count": len(plan.items),
        "shard": {"input_sha256": shard.input_sha256, "request_count": len(shard.items)},
    }


def _verify_packet(packet: Path) -> str:
    entries = (packet / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
    if not entries:
        raise TimerWave1RepairRunError("repair packet checksum manifest is empty")
    seen: set[str] = set()
    for entry in entries:
        checksum, separator, relative_path = entry.partition("  ")
        path = Path(relative_path)
        if (
            not separator
            or not relative_path
            or path.is_absolute()
            or ".." in path.parts
            or relative_path in seen
            or digest((packet / path).read_bytes()) != f"sha256:{checksum}"
        ):
            raise TimerWave1RepairRunError(
                f"repair packet member changed: {relative_path or '<invalid>'}"
            )
        seen.add(relative_path)
    return digest((packet / "SHA256SUMS").read_bytes())


def _json_object(raw: object, subject: str) -> dict[str, object]:
    if not isinstance(raw, bytes):
        raise TimerWave1RepairRunError(f"repair {subject} is absent")
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise TimerWave1RepairRunError(f"repair {subject} is invalid JSON") from error
    if not isinstance(value, dict):
        raise TimerWave1RepairRunError(f"repair {subject} is not an object")
    return value


def _shard_output(execution: Path, shard: BatchShard) -> Path:
    return execution / "shards" / f"{shard.shard_index:04d}"


def _write_record(output: Path, record: BatchJobRecord) -> None:
    _write_json(output / "execution-state.json", _job_state(record))
    _write(output / "output.jsonl", record.output_jsonl)
    _write(output / "errors.jsonl", record.error_jsonl)
    if record.latest_batch_json:
        _write(output / "provider-batch.json", record.latest_batch_json)


def _job_state(record: BatchJobRecord) -> dict[str, object]:
    return {
        "api_call_performed": record.status != "planned",
        "batch_id": record.batch_id,
        "input_file_id": record.input_file_id,
        "input_sha256": record.input_sha256,
        "status": record.status,
    }


def _write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_bytes(data)
    temporary.replace(path)


def _write_json(path: Path, value: object) -> None:
    _write(path, canonical_artifact_bytes(value))


@contextmanager
def _exclusive_lock(ledger: Path):
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with ledger.with_suffix(".lock").open("a+b") as lock_file:
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise TimerWave1RepairRunError(
                "another repair Batch process is already running"
            ) from error
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def main() -> None:
    asyncio.run(_run(_arguments()))


if __name__ == "__main__":
    main()
