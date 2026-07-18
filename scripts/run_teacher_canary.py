#!/usr/bin/env python3
"""Plan, run, or resume the approved sharded-Batch WP1-9 teacher canary."""

from __future__ import annotations

import argparse
import asyncio
import fcntl
import json
import os
from contextlib import contextmanager
from decimal import Decimal, InvalidOperation
from pathlib import Path

from dotenv import load_dotenv

from im.generation.teacher_canary_runner import (
    TeacherCanaryRunError,
    execute_teacher_canary,
    plan_teacher_canary,
)
from im.probes.harness.batch_api import OpenAIBatchGateway, adopt_uncertain_batch
from im.probes.harness.cache import HarnessCache


def _amount(value: str) -> Decimal:
    try:
        amount = Decimal(value)
    except InvalidOperation as error:
        raise argparse.ArgumentTypeError("amount must be a decimal") from error
    if not amount.is_finite() or amount < 0:
        raise argparse.ArgumentTypeError("amount must be a nonnegative finite decimal")
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
        required=True,
        type=_positive_integer,
        help="explicit per-shard prompt-token ceiling",
    )
    parser.add_argument("--batch-poll-seconds", type=_positive_seconds, default=15)
    parser.add_argument("--batch-id")
    parser.add_argument("--input-sha256")
    return parser.parse_args()


async def _run(args: argparse.Namespace) -> None:
    repository = args.repository.resolve()
    load_dotenv(repository / ".env", override=False)
    packet = repository / "review/phase1/teacher-canary-recanary/packet-final"
    execution_root = repository / "review/phase1/teacher-canary-recanary/execution"
    output = execution_root / "sharded"
    plan = plan_teacher_canary(
        repository,
        packet,
        max_enqueued_tokens=args.batch_max_enqueued_tokens,
    )
    print(json.dumps(plan.as_json(), indent=2, sort_keys=True), flush=True)
    if args.mode == "plan":
        return
    cache_path = execution_root / "ledger.sqlite"
    if args.mode == "adopt":
        if not args.batch_id or not args.input_sha256:
            raise TeacherCanaryRunError(
                "adopt requires --batch-id and --input-sha256 from reconciliation"
            )
        planned_digests = {shard.input_sha256 for shard in plan.shards}
        if args.input_sha256 not in planned_digests:
            raise TeacherCanaryRunError("adopt input is not one of this canary's planned shards")
        with _exclusive_lock(cache_path):
            with HarnessCache(cache_path) as cache:
                record = cache.get_batch_job(args.input_sha256)
                if record is None or record.status not in {
                    "create_uncertain",
                    "adopted_unverified",
                }:
                    raise TeacherCanaryRunError(
                        "adopt requires this canary's unresolved Batch ledger entry"
                    )
                adopted = adopt_uncertain_batch(
                    cache,
                    input_sha256=args.input_sha256,
                    batch_id=args.batch_id,
                )
        print(
            json.dumps(
                {
                    "api_call_performed": False,
                    "batch_id": adopted.batch_id,
                    "input_sha256": adopted.input_sha256,
                    "status": adopted.status,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return
    if (
        args.approve_live_ceiling_usd is None
        or args.approve_live_ceiling_usd < plan.cost.approval_ceiling_usd
    ):
        raise TeacherCanaryRunError(
            "teacher-canary execution requires --approve-live-ceiling-usd at least "
            f"{plan.cost.approval_ceiling_usd} for the maximum 8192-token output ceiling"
        )
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise TeacherCanaryRunError("OPENAI_API_KEY is required for teacher-canary execution")
    gateway = OpenAIBatchGateway(
        api_key=api_key,
        organization_id=os.getenv("OPENAI_ORG_ID", "").strip() or None,
        project_id=os.getenv("OPENAI_PROJECT_ID", "").strip() or None,
        base_url=plan.builder.config.base_url,
        timeout_seconds=plan.builder.config.timeout_seconds,
    )
    try:
        with _exclusive_lock(cache_path):
            with HarnessCache(cache_path) as cache:
                if args.mode == "resume" and not cache.batch_jobs(
                    stage=plan.shards[0].stage
                ):
                    raise TeacherCanaryRunError(
                        "resume requires the existing teacher-canary ledger"
                    )
                execution = await execute_teacher_canary(
                    plan,
                    cache=cache,
                    gateway=gateway,
                    poll_seconds=args.batch_poll_seconds,
                    output=output,
                )
    finally:
        await gateway.aclose()
    print(
        json.dumps(
            {
                "api_call_performed": True,
                "batch_ids": [job.batch_id for job in execution.jobs],
                "comparison": str(output / "comparison.json"),
                "causal_disagreement_count": execution.report["causal_disagreement_count"],
                "provider_usage": execution.provider_usage.as_json(),
                "semantic_review_required_count": execution.report[
                    "semantic_review_required_count"
                ],
                "unresolved_count": execution.report["unresolved_count"],
            },
            indent=2,
            sort_keys=True,
        )
    )


@contextmanager
def _exclusive_lock(cache_path: Path):
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = cache_path.with_name(cache_path.name + ".lock")
    with lock_path.open("a+b") as lock_file:
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise TeacherCanaryRunError(f"another canary process owns {lock_path}") from error
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def main() -> None:
    asyncio.run(_run(_arguments()))


if __name__ == "__main__":
    main()
