#!/usr/bin/env python3
"""Plan, run, resume, or reconcile the approved Phase 2 timer Wave-1 Batch."""

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

_EXPECTED_DECISIONS = 82
_MAX_ENQUEUED_TOKENS = 700_000
_MANDATORY_ACTIONS = frozenset({"schedule", "cancel", "skip", "nudge"})
_PACKET = Path("review/phase2/timer-wave-1")
_EXECUTION = Path("review/phase2/timer-wave-1-execution")


class TimerWave1RunError(RuntimeError):
    """The signed Wave-1 plan cannot be safely executed or reported."""


@dataclass(frozen=True, slots=True)
class Wave1BatchPlan:
    raw: object
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


def _positive_integer(value: str) -> int:
    try:
        number = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("value must be a positive integer") from error
    if number <= 0:
        raise argparse.ArgumentTypeError("value must be a positive integer")
    return number


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("plan", "run", "resume", "adopt"), default="plan")
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--approve-live-ceiling-usd", type=_amount)
    parser.add_argument(
        "--batch-max-enqueued-tokens",
        default=_MAX_ENQUEUED_TOKENS,
        type=_positive_integer,
        help="must remain the signed 700000-token Wave-1 shard ceiling",
    )
    parser.add_argument("--batch-poll-seconds", type=_positive_seconds, default=300)
    parser.add_argument("--batch-id")
    parser.add_argument("--input-sha256")
    return parser.parse_args()


async def _build_plan(repository: Path):
    from im.generation.phase2_timer_wave1 import build_timer_wave1_plan

    return await build_timer_wave1_plan(repository_root=repository)


async def load_plan(repository: Path) -> Wave1BatchPlan:
    raw = await _build_plan(repository)
    packet = repository / _PACKET
    files = getattr(raw, "files", None)
    if not isinstance(files, Mapping) or not all(
        isinstance(path, str) and isinstance(content, bytes) for path, content in files.items()
    ):
        raise TimerWave1RunError("Wave-1 planner did not return canonical packet files")
    retained_files = _retained_packet_files(packet, files)

    packet_sha256 = _verify_packet(packet)
    manifest_bytes = retained_files.get("teacher-plan.json")
    if not isinstance(manifest_bytes, bytes):
        raise TimerWave1RunError("Wave-1 packet has no teacher plan")
    manifest = _json_object(manifest_bytes, "teacher plan")
    targets = _targets(manifest)
    items = tuple(getattr(raw, "items", ()))
    shards = tuple(getattr(raw, "shards", ()))
    _validate_plan(manifest, targets, items, shards)
    ceiling = _ceiling(manifest)
    return Wave1BatchPlan(
        raw=raw,
        packet=packet,
        packet_sha256=packet_sha256,
        manifest=manifest,
        targets=targets,
        items=items,
        shards=shards,
        approval_ceiling_usd=ceiling,
    )


def _retained_packet_files(packet: Path, current: Mapping[str, bytes]) -> dict[str, bytes]:
    retained = {
        path.relative_to(packet).as_posix(): path.read_bytes()
        for path in packet.rglob("*")
        if path.is_file()
    }
    if set(retained) != set(current):
        raise TimerWave1RunError("Wave-1 materialized packet inventory drifted")
    for name in set(current) - {"SHA256SUMS", "teacher-plan.json"}:
        if retained[name] != current[name]:
            raise TimerWave1RunError(f"Wave-1 materialized input drifted: {name}")

    old_plan = _json_object(retained["teacher-plan.json"], "retained teacher plan")
    new_plan = _json_object(current["teacher-plan.json"], "current teacher plan")
    if old_plan == new_plan:
        return retained
    old_bindings = old_plan.get("input_bindings")
    new_bindings = new_plan.get("input_bindings")
    if not isinstance(old_bindings, dict) or not isinstance(new_bindings, dict):
        raise TimerWave1RunError("Wave-1 teacher input bindings are malformed")
    for key in ("registry_sha256", "train_seal_sha256"):
        old_bindings[key] = new_bindings.get(key)
    if old_plan != new_plan:
        raise TimerWave1RunError("Wave-1 teacher plan drifted beyond cumulative TRAIN bindings")
    return retained


def _validate_plan(
    manifest: dict[str, object],
    targets: dict[str, dict[str, object]],
    items: tuple[BatchWorkItem, ...],
    shards: tuple[BatchShard, ...],
) -> None:
    if (
        manifest.get("model") != "gpt-5.6-terra"
        or manifest.get("reasoning_effort") != "high"
        or manifest.get("decision_count") != _EXPECTED_DECISIONS
        or manifest.get("request_count") != _EXPECTED_DECISIONS
        or manifest.get("max_enqueued_tokens") != _MAX_ENQUEUED_TOKENS
        or len(items) != _EXPECTED_DECISIONS
    ):
        raise TimerWave1RunError(
            "Wave-1 teacher plan differs from the signed model, decision, or shard configuration"
        )
    if len(shards) < 2:
        raise TimerWave1RunError("Wave-1 plan must use multiple Batch shards")
    if len(targets) != len(items):
        raise TimerWave1RunError("Wave-1 teacher targets do not cover every decision")
    if len({item.custom_id for item in items}) != len(items):
        raise TimerWave1RunError("Wave-1 Batch custom IDs are not unique")
    if {item.custom_id for item in items} != set(targets):
        raise TimerWave1RunError("Wave-1 targets do not match the signed Batch items")

    flattened = tuple(item for shard in shards for item in shard.items)
    if flattened != items:
        raise TimerWave1RunError("Wave-1 shards do not reproduce the signed item order")
    if len({shard.input_sha256 for shard in shards}) != len(shards):
        raise TimerWave1RunError("Wave-1 shards repeat an input digest")
    if [shard.shard_index for shard in shards] != list(range(len(shards))):
        raise TimerWave1RunError("Wave-1 shard indexes are not contiguous")
    manifest_shards = manifest.get("shards")
    if not isinstance(manifest_shards, list) or len(manifest_shards) != len(shards):
        raise TimerWave1RunError("Wave-1 teacher shard inventory is invalid")
    for shard in shards:
        if shard.estimated_input_tokens > _MAX_ENQUEUED_TOKENS:
            raise TimerWave1RunError("Wave-1 shard exceeds the signed token ceiling")
        if shard.input_jsonl != b"".join(item.request_line for item in shard.items):
            raise TimerWave1RunError("Wave-1 shard input bytes are not canonical")
        if shard.input_sha256 != digest(shard.input_jsonl):
            raise TimerWave1RunError("Wave-1 shard input digest changed")
        if shard.estimated_input_tokens != sum(
            estimate_tokens(item.request_bytes) for item in shard.items
        ):
            raise TimerWave1RunError("Wave-1 shard token estimate changed")
        if any(item.custom_id.split(".", 1)[0] != shard.stage for item in shard.items):
            raise TimerWave1RunError("Wave-1 shard stage does not match its item IDs")
        metadata = manifest_shards[shard.shard_index]
        if not isinstance(metadata, dict) or any(
            metadata.get(key) != value
            for key, value in {
                "estimated_input_tokens": shard.estimated_input_tokens,
                "input_sha256": shard.input_sha256,
                "request_count": len(shard.items),
                "shard_index": shard.shard_index,
                "stage": shard.stage,
            }.items()
        ):
            raise TimerWave1RunError("Wave-1 teacher shard metadata changed")
    for item in items:
        target = targets[item.custom_id]
        expected_body = target.get("request_body_sha256")
        if expected_body is not None and expected_body != digest(
            canonical_artifact_bytes(item.body)
        ):
            raise TimerWave1RunError(f"Wave-1 request body changed for {item.custom_id}")
        try:
            oracle = ACTION_ADAPTER.validate_python(target.get("oracle_action"))
        except ValueError as error:
            raise TimerWave1RunError(
                f"Wave-1 oracle action is invalid for {item.custom_id}"
            ) from error
        risk_flags = target.get("risk_flags")
        reasons = target.get("mandatory_review_reasons")
        cell = target.get("cell")
        idle_boundary = target.get("idle_boundary")
        if (
            not isinstance(target.get("causal_state_class"), str)
            or not isinstance(target.get("boundary_class"), str)
            or not isinstance(cell, dict)
            or any(not isinstance(cell.get(key), str) for key in ("protocol", "family", "floor"))
            or not isinstance(risk_flags, list)
            or not all(isinstance(flag, str) for flag in risk_flags)
            or not isinstance(target.get("rollover"), bool)
            or not isinstance(target.get("mandatory_review"), bool)
            or not isinstance(reasons, list)
            or not all(isinstance(reason, str) for reason in reasons)
            or "idle_boundary" not in target
            or idle_boundary not in {None, "partial_instruction", "lexical_boundary", "ime_edge"}
            or (idle_boundary is not None and oracle.type != "idle")
        ):
            raise TimerWave1RunError(f"Wave-1 D2 review metadata is invalid for {item.custom_id}")
        requires_review = bool(
            oracle.type in _MANDATORY_ACTIONS
            or risk_flags
            or target["rollover"] is True
            or idle_boundary
        )
        required_reasons = set()
        if oracle.type in _MANDATORY_ACTIONS:
            required_reasons.add("mandatory_action")
        if risk_flags:
            required_reasons.add("risk_flag")
        if target["rollover"] is True:
            required_reasons.add("rollover")
        if idle_boundary:
            required_reasons.add("idle_boundary_100_percent")
        if (
            bool(reasons) != target["mandatory_review"]
            or len(reasons) != len(set(reasons))
            or (requires_review and target["mandatory_review"] is not True)
            or not required_reasons.issubset(reasons)
        ):
            raise TimerWave1RunError(
                f"Wave-1 mandatory review metadata is incomplete for {item.custom_id}"
            )


def _targets(manifest: dict[str, object]) -> dict[str, dict[str, object]]:
    raw_targets = manifest.get("targets")
    if not isinstance(raw_targets, list):
        raise TimerWave1RunError("Wave-1 teacher plan has no target inventory")
    targets = {
        target["custom_id"]: target
        for target in raw_targets
        if isinstance(target, dict) and isinstance(target.get("custom_id"), str)
    }
    if len(targets) != len(raw_targets):
        raise TimerWave1RunError("Wave-1 teacher target identities are invalid")
    return targets


def _ceiling(manifest: dict[str, object]) -> Decimal:
    estimate = manifest.get("cost_estimate")
    value = estimate.get("approval_ceiling_usd") if isinstance(estimate, dict) else None
    try:
        ceiling = Decimal(str(value))
    except (InvalidOperation, ValueError) as error:
        raise TimerWave1RunError("Wave-1 teacher plan has no valid approval ceiling") from error
    if not ceiling.is_finite() or ceiling <= 0:
        raise TimerWave1RunError("Wave-1 teacher plan has no positive approval ceiling")
    return ceiling


async def _run(args: argparse.Namespace) -> None:
    repository = args.repository.resolve()
    load_dotenv(repository / ".env", override=False)
    if args.batch_max_enqueued_tokens != _MAX_ENQUEUED_TOKENS:
        raise TimerWave1RunError(
            f"Wave-1 must use the signed {_MAX_ENQUEUED_TOKENS}-token shard ceiling"
        )
    plan = await load_plan(repository)
    summary = _plan_summary(plan)
    print(json.dumps(summary, indent=2, sort_keys=True), flush=True)
    if args.mode == "plan":
        return

    execution = repository / _EXECUTION
    ledger = execution / "ledger.sqlite"
    if args.mode == "adopt":
        _adopt(args, plan, ledger, execution)
        return
    if args.approve_live_ceiling_usd != plan.approval_ceiling_usd:
        raise TimerWave1RunError(
            "Wave-1 execution requires --approve-live-ceiling-usd exactly "
            f"{plan.approval_ceiling_usd}"
        )
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise TimerWave1RunError("OPENAI_API_KEY is required for Wave-1 Batch execution")

    execution.mkdir(parents=True, exist_ok=True)
    _write_json(execution / "plan.json", summary)
    gateway = OpenAIBatchGateway(
        api_key=api_key,
        organization_id=os.getenv("OPENAI_ORG_ID", "").strip() or None,
        project_id=os.getenv("OPENAI_PROJECT_ID", "").strip() or None,
    )
    try:
        with _exclusive_lock(ledger), HarnessCache(ledger) as cache:
            if args.mode == "resume" and not any(
                cache.get_batch_job(shard.input_sha256) is not None for shard in plan.shards
            ):
                raise TimerWave1RunError("resume requires an existing Wave-1 Batch ledger")
            records = await _execute_shards(
                plan,
                cache=cache,
                gateway=gateway,
                poll_seconds=args.batch_poll_seconds,
                execution=execution,
            )
    finally:
        await gateway.aclose()

    comparison = _comparison(plan, records, execution=execution)
    _write_json(execution / "comparison.json", comparison)
    print(json.dumps(comparison, indent=2, sort_keys=True), flush=True)


def _adopt(args: argparse.Namespace, plan: Wave1BatchPlan, ledger: Path, execution: Path) -> None:
    shard = next((item for item in plan.shards if item.input_sha256 == args.input_sha256), None)
    if shard is None or not args.batch_id:
        raise TimerWave1RunError(
            "adopt requires a provider Batch ID and one planned Wave-1 input SHA-256"
        )
    with _exclusive_lock(ledger), HarnessCache(ledger) as cache:
        existing = cache.get_batch_job(shard.input_sha256)
        if existing is None or (existing.stage, existing.shard_index) != (
            shard.stage,
            shard.shard_index,
        ):
            raise TimerWave1RunError("adopt input is not an unresolved Wave-1 ledger shard")
        adopted = adopt_uncertain_batch(
            cache,
            input_sha256=shard.input_sha256,
            batch_id=args.batch_id,
        )
    _write_json(_shard_output(execution, shard) / "execution-state.json", _job_state(adopted))
    print(
        json.dumps({"api_call_performed": False, **_job_state(adopted)}, indent=2, sort_keys=True)
    )


async def _execute_shards(
    plan: Wave1BatchPlan,
    *,
    cache: HarnessCache,
    gateway,
    poll_seconds: float,
    execution: Path,
) -> tuple[BatchJobRecord, ...]:
    records: list[BatchJobRecord] = []
    for shard in plan.shards:
        try:
            record = await execute_batch_shard(
                shard,
                cache=cache,
                gateway=gateway,
                poll_seconds=poll_seconds,
            )
        except BaseException:
            latest = cache.get_batch_job(shard.input_sha256)
            if latest is not None:
                _write_record(_shard_output(execution, shard), latest)
            raise
        _write_record(_shard_output(execution, shard), record)
        if record.status != "completed":
            raise TimerWave1RunError(
                f"Wave-1 Batch shard {shard.shard_index} ended in terminal status {record.status!r}"
            )
        records.append(record)
    return tuple(records)


def _comparison(
    plan: Wave1BatchPlan,
    records: tuple[BatchJobRecord, ...],
    *,
    execution: Path,
) -> dict[str, object]:
    if len(records) != len(plan.shards):
        raise TimerWave1RunError("Wave-1 execution did not return every planned shard")
    rows: list[dict[str, object]] = []
    usage = ProviderUsage()
    for shard, record in zip(plan.shards, records, strict=True):
        artifacts = parse_batch_artifacts(
            shard.items,
            output_jsonl=record.output_jsonl,
            error_jsonl=record.error_jsonl,
        )
        shard_rows: list[dict[str, object]] = []
        for item in shard.items:
            target = plan.targets[item.custom_id]
            decoded = decode_batch_completion(
                item,
                artifacts[item.custom_id],
                batch_id=record.batch_id or "",
                stage=shard.stage,
                shard_index=shard.shard_index,
            )
            usage += decoded.completion.usage
            teacher = decoded.completion.value
            oracle = target["oracle_action"]
            teacher_type = teacher.get("type") if isinstance(teacher, dict) else None
            equivalent = (
                decoded.completion.outcome == "completed"
                and decoded.validation_error is None
                and teacher == oracle
            )
            review_required = bool(
                target.get("mandatory_review")
                or target.get("risk_flags")
                or target.get("rollover")
                or teacher_type in _MANDATORY_ACTIONS
                or not equivalent
            )
            review_reasons = list(target["mandatory_review_reasons"])
            if teacher_type in _MANDATORY_ACTIONS and "mandatory_action" not in review_reasons:
                review_reasons.append("mandatory_action")
            if not equivalent and "teacher_oracle_disagreement" not in review_reasons:
                review_reasons.append("teacher_oracle_disagreement")
            row = {
                "comparison": "equivalent" if equivalent else "non_equivalent",
                "custom_id": item.custom_id,
                "mandatory_review": review_required,
                "mandatory_review_reasons": review_reasons,
                "oracle_action": oracle,
                "outcome": decoded.completion.outcome,
                "shard_index": shard.shard_index,
                "target": target,
                "teacher_action": teacher,
                "validation_error": decoded.validation_error,
            }
            rows.append(row)
            shard_rows.append(row)
        _write_json(_shard_output(execution, shard) / "comparison.json", {"rows": shard_rows})
    pricing = ModelPricing(model=str(plan.manifest["model"]))
    return {
        "batch_ids": [record.batch_id for record in records],
        "mandatory_review_count": sum(bool(row["mandatory_review"]) for row in rows),
        "non_equivalent_count": sum(row["comparison"] != "equivalent" for row in rows),
        "packet_sha256": plan.packet_sha256,
        "provider_usage": usage.as_json(),
        "request_count": len(rows),
        "rows": rows,
        "usd": format(usage_cost(usage, pricing, billing_multiplier=Decimal("0.50")), "f"),
    }


def _plan_summary(plan: Wave1BatchPlan) -> dict[str, object]:
    return {
        "api_call_performed": False,
        "approval_ceiling_usd": format(plan.approval_ceiling_usd, "f"),
        "estimated_input_tokens": sum(shard.estimated_input_tokens for shard in plan.shards),
        "model": plan.manifest.get("model"),
        "packet": str(_PACKET),
        "packet_sha256": plan.packet_sha256,
        "reasoning_effort": plan.manifest.get("reasoning_effort"),
        "request_count": len(plan.items),
        "shards": [
            {
                "estimated_input_tokens": shard.estimated_input_tokens,
                "input_sha256": shard.input_sha256,
                "request_count": len(shard.items),
                "shard_index": shard.shard_index,
            }
            for shard in plan.shards
        ],
    }


def _verify_packet(packet: Path) -> str:
    """Verify the signed payload only; unbound OWNER-DISPOSITION sidecars are excluded by design."""
    checksum_path = packet / "SHA256SUMS"
    checksum_bytes = checksum_path.read_bytes()
    entries = checksum_bytes.decode("utf-8").splitlines()
    if not entries:
        raise TimerWave1RunError("Wave-1 packet checksum manifest is empty")
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
            raise TimerWave1RunError(
                f"Wave-1 packet member changed: {relative_path or '<invalid>'}"
            )
        seen.add(relative_path)
    return digest(checksum_bytes)


def _json_object(raw: bytes, subject: str) -> dict[str, object]:
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise TimerWave1RunError(f"Wave-1 {subject} is invalid JSON") from error
    if not isinstance(value, dict):
        raise TimerWave1RunError(f"Wave-1 {subject} is not an object")
    return value


def _shard_output(execution: Path, shard: BatchShard) -> Path:
    return execution / "shards" / f"{shard.shard_index:04d}"


def _write_record(output: Path, record: BatchJobRecord) -> None:
    _write_json(output / "execution-state.json", _job_state(record))
    if record.latest_batch_json:
        _write(output / "provider-batch.json", record.latest_batch_json)
    _write(output / "output.jsonl", record.output_jsonl)
    _write(output / "errors.jsonl", record.error_jsonl)


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
    lock_path = ledger.with_suffix(".lock")
    with lock_path.open("a+b") as lock_file:
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise TimerWave1RunError("another Wave-1 Batch process is already running") from error
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def main() -> None:
    asyncio.run(_run(_arguments()))


if __name__ == "__main__":
    main()
