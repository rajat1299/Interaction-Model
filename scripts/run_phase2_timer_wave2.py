#!/usr/bin/env python3
"""Plan, run, resume, or adopt the sealed provider-free timer Wave-2 Batch."""

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

_EXPECTED_DECISIONS = 698
_EXPECTED_SHARDS = 17
_MAX_ENQUEUED_TOKENS = 700_000
_MAX_OUTPUT_TOKENS = 8_192
_MODEL = "gpt-5.6-terra"
_REASONING_EFFORT = "high"
_PROMPT_V3_SHA256 = "sha256:31bea45fa5639c1eae8ad411779262d027bc705b499cf5eda3437a76a6d49ec9"
_STAGE = "t2w2"
_PACKET = Path("review/phase2/timer-wave-2")
_EXECUTION = Path("review/phase2/timer-wave-2-execution")


class TimerWave2RunError(RuntimeError):
    """The sealed Wave-2 packet cannot safely be executed or reported."""


@dataclass(frozen=True, slots=True)
class Wave2BatchPlan:
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
    parser.add_argument("--batch-poll-seconds", type=_positive_seconds, default=300)
    parser.add_argument(
        "--batch-max-enqueued-tokens",
        type=_positive_integer,
        default=_MAX_ENQUEUED_TOKENS,
        help="must remain the signed 700000-token Wave-2 shard ceiling",
    )
    parser.add_argument("--batch-id")
    parser.add_argument("--input-sha256")
    return parser.parse_args()


async def _build_packet(repository: Path):
    from im.generation.phase2_timer_wave2_packet import build_timer_wave2_packet

    return await build_timer_wave2_packet(repository_root=repository)


async def load_plan(repository: Path, *, build_packet=None) -> Wave2BatchPlan:
    packet_builder = _build_packet if build_packet is None else build_packet
    raw = await packet_builder(repository)
    files = getattr(raw, "files", None)
    if not isinstance(files, Mapping) or not all(
        isinstance(path, str) and isinstance(data, bytes) for path, data in files.items()
    ):
        raise TimerWave2RunError("Wave-2 builder did not return canonical packet files")
    packet = repository / _PACKET
    for relative_path, data in files.items():
        path = packet / relative_path
        if not path.is_file() or path.read_bytes() != data:
            raise TimerWave2RunError(f"Wave-2 packet was not materialized: {relative_path}")
    manifest = _json_object(files.get("teacher-plan.json"), "teacher plan")
    targets = _targets(manifest)
    items = tuple(getattr(raw, "items", ()))
    shards = tuple(getattr(raw, "shards", ()))
    _validate_plan(manifest, targets, items, shards)
    _verify_packet(packet, expected_files=set(files))
    return Wave2BatchPlan(
        packet=packet,
        packet_sha256=digest(files["SHA256SUMS"]),
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
) -> None:
    if (
        manifest.get("kind") != "phase2-timer-wave2-teacher-plan"
        or manifest.get("format_version") != 1
        or manifest.get("stage") != _STAGE
        or manifest.get("model") != _MODEL
        or manifest.get("reasoning_effort") != _REASONING_EFFORT
        or manifest.get("max_enqueued_tokens") != _MAX_ENQUEUED_TOKENS
        or manifest.get("max_output_tokens_per_request") != _MAX_OUTPUT_TOKENS
        or manifest.get("request_count") != _EXPECTED_DECISIONS
        or manifest.get("candidate_decision_count") != _EXPECTED_DECISIONS
        or manifest.get("shard_count") != _EXPECTED_SHARDS
        or len(items) != _EXPECTED_DECISIONS
        or len(shards) != _EXPECTED_SHARDS
    ):
        raise TimerWave2RunError(
            "Wave-2 plan differs from the signed v3 model, count, or shard configuration"
        )
    prompt_bindings = manifest.get("prompt_bindings")
    if not isinstance(prompt_bindings, dict) or prompt_bindings != {
        "runtime_prompt_hashes": [_PROMPT_V3_SHA256],
        "teacher_prompt_hash": _PROMPT_V3_SHA256,
    }:
        raise TimerWave2RunError("Wave-2 plan is not bound to prompt-template-v3")
    if len(targets) != len(items) or set(targets) != {item.custom_id for item in items}:
        raise TimerWave2RunError("Wave-2 targets do not exactly cover the signed requests")
    if len({item.custom_id for item in items}) != len(items):
        raise TimerWave2RunError("Wave-2 Batch custom IDs are not unique")
    if tuple(item for shard in shards for item in shard.items) != items:
        raise TimerWave2RunError("Wave-2 shards do not reproduce signed request order")
    if [shard.shard_index for shard in shards] != list(range(_EXPECTED_SHARDS)):
        raise TimerWave2RunError("Wave-2 shard indexes are not contiguous")
    manifest_shards = manifest.get("shards")
    if not isinstance(manifest_shards, list) or len(manifest_shards) != len(shards):
        raise TimerWave2RunError("Wave-2 signed shard inventory is invalid")
    for shard in shards:
        metadata = manifest_shards[shard.shard_index]
        expected = {
            "estimated_input_tokens": shard.estimated_input_tokens,
            "input_path": f"teacher-input/shard-{shard.shard_index:03}.jsonl",
            "input_sha256": shard.input_sha256,
            "request_count": len(shard.items),
            "shard_index": shard.shard_index,
            "stage": _STAGE,
        }
        if (
            shard.stage != _STAGE
            or shard.estimated_input_tokens > _MAX_ENQUEUED_TOKENS
            or shard.input_jsonl != b"".join(item.request_line for item in shard.items)
            or shard.input_sha256 != digest(shard.input_jsonl)
            or shard.estimated_input_tokens
            != sum(estimate_tokens(item.request_bytes) for item in shard.items)
            or not isinstance(metadata, dict)
            or any(metadata.get(key) != value for key, value in expected.items())
        ):
            raise TimerWave2RunError("Wave-2 signed shard binding changed")
    for item in items:
        target = targets[item.custom_id]
        if (
            item.prompt_hash != _PROMPT_V3_SHA256
            or target.get("prompt_hash") != _PROMPT_V3_SHA256
            or target.get("request_body_sha256") != digest(canonical_artifact_bytes(item.body))
        ):
            raise TimerWave2RunError(f"Wave-2 request binding drifted for {item.custom_id}")
        try:
            ACTION_ADAPTER.validate_python(target.get("oracle_action"))
        except ValueError as error:
            raise TimerWave2RunError(
                f"Wave-2 oracle action is invalid for {item.custom_id}"
            ) from error
        _validate_target_route(target, item.custom_id)


def _validate_target_route(target: dict[str, object], custom_id: str) -> None:
    selected = target.get("candidate_selected_program_action_indices")
    index = target.get("program_action_index")
    route = target.get("static_d2_route")
    d13 = target.get("d13")
    if (
        not isinstance(selected, list)
        or not all(isinstance(value, int) for value in selected)
        or not isinstance(index, int)
        or index not in selected
        or not isinstance(route, dict)
        or route.get("add_review_if") != ["teacher_low_confidence", "teacher_oracle_disagreement"]
        or not isinstance(route.get("mandatory_review"), bool)
        or not isinstance(route.get("review_required"), bool)
        or not isinstance(route.get("reasons"), list)
        or not all(isinstance(reason, str) for reason in route["reasons"])
        or len(route["reasons"]) != len(set(route["reasons"]))
        or not isinstance(route.get("sample_rate"), (float, int))
        or not 0 <= route["sample_rate"] <= 1
        or (route["mandatory_review"] and not route["review_required"])
        or d13 != {
            "label_origin": None,
            "pending_origin": "teacher_outcome_then_d2_review",
            "review_batch_id": None,
            "trust_matrix_version": "phase2-trust-v1",
        }
    ):
        raise TimerWave2RunError(f"Wave-2 D2/D13 routing is invalid for {custom_id}")


async def _run(args: argparse.Namespace, *, build_packet=None, gateway_factory=None) -> None:
    repository = args.repository.resolve()
    load_dotenv(repository / ".env", override=False)
    if args.batch_max_enqueued_tokens != _MAX_ENQUEUED_TOKENS:
        raise TimerWave2RunError(
            f"Wave-2 must use the signed {_MAX_ENQUEUED_TOKENS}-token shard ceiling"
        )
    plan = await load_plan(repository, build_packet=build_packet)
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
        raise TimerWave2RunError(
            "Wave-2 execution requires --approve-live-ceiling-usd exactly "
            f"{plan.approval_ceiling_usd}"
        )
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise TimerWave2RunError("OPENAI_API_KEY is required for Wave-2 Batch execution")
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
            if args.mode == "resume" and not any(
                cache.get_batch_job(shard.input_sha256) is not None for shard in plan.shards
            ):
                raise TimerWave2RunError("resume requires an existing Wave-2 Batch ledger")
            records = await _execute_shards(
                plan,
                cache=cache,
                gateway=gateway,
                poll_seconds=args.batch_poll_seconds,
                execution=execution,
            )
    finally:
        await gateway.aclose()
    comparison = _comparison(plan, records, execution)
    _write_json(execution / "comparison.json", comparison)
    print(json.dumps(comparison, indent=2, sort_keys=True), flush=True)


def _adopt(args: argparse.Namespace, plan: Wave2BatchPlan, ledger: Path, execution: Path) -> None:
    shard = next((item for item in plan.shards if item.input_sha256 == args.input_sha256), None)
    if shard is None or not args.batch_id:
        raise TimerWave2RunError(
            "adopt requires a provider Batch ID and one planned Wave-2 input SHA-256"
        )
    with _exclusive_lock(ledger), HarnessCache(ledger) as cache:
        existing = cache.get_batch_job(shard.input_sha256)
        if existing is None or (existing.stage, existing.shard_index) != (
            shard.stage,
            shard.shard_index,
        ):
            raise TimerWave2RunError("adopt input is not an unresolved Wave-2 ledger shard")
        adopted = adopt_uncertain_batch(
            cache, input_sha256=shard.input_sha256, batch_id=args.batch_id
        )
    _write_json(_shard_output(execution, shard) / "execution-state.json", _job_state(adopted))
    print(
        json.dumps({"api_call_performed": False, **_job_state(adopted)}, indent=2, sort_keys=True)
    )


async def _execute_shards(
    plan: Wave2BatchPlan, *, cache: HarnessCache, gateway, poll_seconds: float, execution: Path
) -> tuple[BatchJobRecord, ...]:
    records: list[BatchJobRecord] = []
    for shard in plan.shards:
        try:
            record = await execute_batch_shard(
                shard, cache=cache, gateway=gateway, poll_seconds=poll_seconds
            )
        except BaseException:
            latest = cache.get_batch_job(shard.input_sha256)
            if latest is not None:
                _write_record(_shard_output(execution, shard), latest)
            raise
        _write_record(_shard_output(execution, shard), record)
        if record.status != "completed":
            raise TimerWave2RunError(
                f"Wave-2 Batch shard {shard.shard_index} ended in terminal status {record.status!r}"
            )
        records.append(record)
    return tuple(records)


def _comparison(
    plan: Wave2BatchPlan, records: tuple[BatchJobRecord, ...], execution: Path
) -> dict[str, object]:
    if len(records) != len(plan.shards):
        raise TimerWave2RunError("Wave-2 execution did not return every signed shard")
    rows: list[dict[str, object]] = []
    usage = ProviderUsage()
    for shard, record in zip(plan.shards, records, strict=True):
        artifacts = parse_batch_artifacts(
            shard.items, output_jsonl=record.output_jsonl, error_jsonl=record.error_jsonl
        )
        shard_rows = []
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
            equivalent = (
                decoded.completion.outcome == "completed"
                and decoded.validation_error is None
                and teacher == oracle
            )
            reasons = _review_reasons(target, equivalent)
            row = {
                "comparison": "equivalent" if equivalent else "non_equivalent",
                "custom_id": item.custom_id,
                "equivalence": equivalent,
                "oracle_action": oracle,
                "outcome": decoded.completion.outcome,
                "review_reasons": reasons,
                "review_required": bool(reasons),
                "shard_index": shard.shard_index,
                "target": target,
                "teacher_action": teacher,
                "validation_error": decoded.validation_error,
            }
            rows.append(row)
            shard_rows.append(row)
        _write_json(_shard_output(execution, shard) / "comparison.json", {"rows": shard_rows})
    actual_usd = usage_cost(
        usage, ModelPricing(model=_MODEL), billing_multiplier=Decimal("0.50")
    )
    return {
        "actual_usage": usage.as_json(),
        "actual_usd": format(actual_usd, "f"),
        "batch_ids": [record.batch_id for record in records],
        "mandatory_review_count": sum(bool(row["review_required"]) for row in rows),
        "non_equivalent_count": sum(not bool(row["equivalence"]) for row in rows),
        "packet_sha256": plan.packet_sha256,
        "request_count": len(rows),
        "rows": rows,
    }


def _review_reasons(target: dict[str, object], equivalent: bool) -> list[str]:
    route = target["static_d2_route"]
    assert isinstance(route, dict)
    reasons = list(route["reasons"])
    if route["review_required"] and not reasons:
        reasons.append("static_d2_route")
    if not equivalent:
        reasons.append("teacher_oracle_disagreement")
    return list(dict.fromkeys(reasons))


def _targets(manifest: dict[str, object]) -> dict[str, dict[str, object]]:
    raw_targets = manifest.get("targets")
    if not isinstance(raw_targets, list):
        raise TimerWave2RunError("Wave-2 teacher plan has no target inventory")
    targets = {
        target["custom_id"]
        : target
        for target in raw_targets
        if isinstance(target, dict) and isinstance(target.get("custom_id"), str)
    }
    if len(targets) != len(raw_targets):
        raise TimerWave2RunError("Wave-2 target identities are invalid")
    return targets


def _ceiling(manifest: dict[str, object]) -> Decimal:
    estimate = manifest.get("cost_estimate")
    value = estimate.get("approval_ceiling_usd") if isinstance(estimate, dict) else None
    try:
        ceiling = Decimal(str(value))
    except (InvalidOperation, ValueError) as error:
        raise TimerWave2RunError("Wave-2 plan has no valid approval ceiling") from error
    if not ceiling.is_finite() or ceiling <= 0:
        raise TimerWave2RunError("Wave-2 plan has no positive approval ceiling")
    return ceiling


def _plan_summary(plan: Wave2BatchPlan) -> dict[str, object]:
    return {
        "api_call_performed": False,
        "approval_ceiling_usd": format(plan.approval_ceiling_usd, "f"),
        "estimated_input_tokens": sum(shard.estimated_input_tokens for shard in plan.shards),
        "model": _MODEL,
        "packet": str(_PACKET),
        "packet_sha256": plan.packet_sha256,
        "prompt_hash": _PROMPT_V3_SHA256,
        "reasoning_effort": _REASONING_EFFORT,
        "request_count": len(plan.items),
        "shard_count": len(plan.shards),
    }


def _verify_packet(packet: Path, *, expected_files: set[str] | None = None) -> str:
    try:
        checksum_bytes = (packet / "SHA256SUMS").read_bytes()
    except OSError as error:
        raise TimerWave2RunError("Wave-2 packet checksum manifest is unreadable") from error
    entries = checksum_bytes.decode("utf-8").splitlines()
    if not entries:
        raise TimerWave2RunError("Wave-2 packet checksum manifest is empty")
    seen: set[str] = set()
    for entry in entries:
        checksum, separator, relative_path = entry.partition("  ")
        path = Path(relative_path)
        if (
            not separator
            or len(checksum) != 64
            or any(character not in "0123456789abcdef" for character in checksum)
            or not relative_path
            or path.is_absolute()
            or ".." in path.parts
            or relative_path in seen
        ):
            raise TimerWave2RunError(
                f"Wave-2 packet member changed: {relative_path or '<invalid>'}"
            )
        try:
            matches = digest((packet / path).read_bytes()) == f"sha256:{checksum}"
        except OSError:
            matches = False
        if not matches:
            raise TimerWave2RunError(f"Wave-2 packet member changed: {relative_path}")
        seen.add(relative_path)
    if expected_files is not None and seen != expected_files - {"SHA256SUMS"}:
        raise TimerWave2RunError("Wave-2 packet checksum inventory differs from the signed files")
    return digest(checksum_bytes)


def _json_object(raw: object, subject: str) -> dict[str, object]:
    if not isinstance(raw, bytes):
        raise TimerWave2RunError(f"Wave-2 {subject} is absent")
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise TimerWave2RunError(f"Wave-2 {subject} is invalid JSON") from error
    if not isinstance(value, dict):
        raise TimerWave2RunError(f"Wave-2 {subject} is not an object")
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
            raise TimerWave2RunError("another Wave-2 Batch process is already running") from error
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def main() -> None:
    asyncio.run(_run(_arguments()))


if __name__ == "__main__":
    main()
