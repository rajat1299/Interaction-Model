#!/usr/bin/env python3
"""Plan, pilot, resume, and report the signed WP15 run through OpenAI Batch."""

from __future__ import annotations

import argparse
import asyncio
import fcntl
import json
import os
import subprocess
from contextlib import contextmanager
from dataclasses import asdict, is_dataclass
from decimal import Decimal, InvalidOperation
from enum import Enum
from pathlib import Path
from typing import cast

from dotenv import load_dotenv

from im.policy.prompted import (
    ModelPricing,
    PromptArtifacts,
    PromptedPolicyConfig,
    PromptRenderer,
    ReasoningEffort,
    ResponsesRequestBuilder,
)
from im.probes.harness.artifacts import load_approved_catalog
from im.probes.harness.batch import BatchWorkItem, plan_primary_work, shard_work
from im.probes.harness.batch_api import OpenAIBatchGateway, adopt_uncertain_batch
from im.probes.harness.batch_runner import (
    BatchHarnessConfig,
    BatchProbeHarnessRunner,
    materialize_batch_stage,
)
from im.probes.harness.cache import HarnessCache
from im.probes.harness.cost import estimate_harness_cost
from im.probes.harness.identity import digest
from im.probes.harness.metrics import compute_metrics
from im.probes.harness.models import BatchJobRecord
from im.probes.harness.protocols import ProtocolPromptBuilder
from im.probes.harness.report import render_report


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be positive")
    return parsed


def _positive_float(value: str) -> float:
    parsed = float(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be positive")
    return parsed


def _nonnegative_decimal(value: str) -> Decimal:
    try:
        parsed = Decimal(value)
    except InvalidOperation as error:
        raise argparse.ArgumentTypeError("value must be a decimal amount") from error
    if not parsed.is_finite() or parsed < 0:
        raise argparse.ArgumentTypeError("value must be a nonnegative finite amount")
    return parsed


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("plan", "pilot", "live", "adopt"), default="plan")
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--cache", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--raw-summary", type=Path)
    parser.add_argument("--batch-max-enqueued-tokens", type=_positive_int)
    parser.add_argument("--batch-pilot-requests", type=_positive_int)
    parser.add_argument("--batch-poll-seconds", type=_positive_float, default=15)
    parser.add_argument("--approve-live-estimate-usd", type=_nonnegative_decimal)
    parser.add_argument(
        "--retry-indeterminate-cache-key",
        action="append",
        default=[],
        metavar="HEX_DIGEST",
        help="authorize one Batch provider retry for this exact cache identity",
    )
    parser.add_argument("--input-sha256")
    parser.add_argument("--batch-id")
    return parser.parse_args()


async def _run(args: argparse.Namespace) -> None:
    repository = args.repository.resolve()
    run_commit = _repository_commit(repository)
    load_dotenv(repository / ".env", override=False)
    config = PromptedPolicyConfig(
        model=os.getenv("IM_TEACHER_MODEL", "gpt-5.6-terra").strip(),
        reasoning_effort=cast(
            ReasoningEffort,
            os.getenv("IM_TEACHER_REASONING_EFFORT", "high").strip(),
        ),
        max_output_tokens=int(os.getenv("IM_TEACHER_MAX_OUTPUT_TOKENS", "8192")),
    )
    catalog = await load_approved_catalog(repository)
    artifacts = PromptArtifacts.from_repository(repository)
    builder = ResponsesRequestBuilder(PromptRenderer(artifacts), config)
    prompts = ProtocolPromptBuilder(artifacts, config)
    estimate = estimate_harness_cost(catalog, builder, prompts)
    cache_path = _resolve(
        repository,
        args.cache,
        Path(
            f"probes/results/raw/wp15-{config.model.replace('/', '-')}-"
            f"{config.reasoning_effort}-batch"
            f"{'-pilot' if args.mode == 'pilot' else ''}.sqlite"
        ),
    )
    print(
        json.dumps(
            {
                "api_call_performed": False,
                "batch_cache": str(cache_path),
                "estimate": estimate.as_json(),
                "manifest_sha256": catalog.manifest_sha256,
                "mode": args.mode,
                "model": config.model,
                "reasoning_effort": config.reasoning_effort,
                "repository_commit": run_commit,
            },
            indent=2,
            sort_keys=True,
        ),
        flush=True,
    )

    if args.mode == "adopt":
        if not args.input_sha256 or not args.batch_id:
            raise RuntimeError("adopt requires --input-sha256 and --batch-id")
        with _exclusive_cache_lock(cache_path):
            with HarnessCache(
                cache_path,
                retry_indeterminate_keys=frozenset(args.retry_indeterminate_cache_key),
            ) as cache:
                record = adopt_uncertain_batch(
                    cache,
                    input_sha256=args.input_sha256,
                    batch_id=args.batch_id,
                )
        print(json.dumps(_job_summary(record), indent=2, sort_keys=True))
        return

    if args.batch_max_enqueued_tokens is None:
        raise RuntimeError(
            f"--mode {args.mode} requires an explicit --batch-max-enqueued-tokens"
        )
    primary = plan_primary_work(catalog, builder, prompts)
    if args.mode == "plan":
        shards = shard_work(
            "p0",
            primary,
            max_enqueued_tokens=args.batch_max_enqueued_tokens,
        )
        print(
            json.dumps(
                {
                    "api_call_performed": False,
                    "p0": {
                        "estimated_input_tokens": sum(
                            shard.estimated_input_tokens for shard in shards
                        ),
                        "input_bytes": sum(len(shard.input_jsonl) for shard in shards),
                        "requests": len(primary),
                        "shards": [
                            {
                                "estimated_input_tokens": shard.estimated_input_tokens,
                                "input_bytes": len(shard.input_jsonl),
                                "input_sha256": shard.input_sha256,
                                "request_count": len(shard.items),
                                "shard_index": shard.shard_index,
                            }
                            for shard in shards
                        ],
                    }
                },
                indent=2,
                sort_keys=True,
            )
        )
        return

    pilot_count = args.batch_pilot_requests
    if args.mode == "pilot":
        if pilot_count is None:
            raise RuntimeError("--mode pilot requires --batch-pilot-requests")
        if pilot_count < 3:
            raise RuntimeError("pilot requires at least three requests to cover every P0 protocol")
        if pilot_count > len(primary):
            raise RuntimeError(f"pilot requests cannot exceed {len(primary)}")
        approval_ceiling = (
            estimate.batch_no_cache_usd
            * Decimal(2)
            * Decimal(pilot_count)
            / Decimal(len(primary))
        )
    else:
        approval_ceiling = estimate.batch_no_cache_usd * Decimal(2)
    if (
        args.approve_live_estimate_usd is None
        or args.approve_live_estimate_usd < approval_ceiling
    ):
        raise RuntimeError(
            "Batch execution requires --approve-live-estimate-usd at least "
            f"{approval_ceiling:.6f}; this acknowledges an estimate, not a provider cap"
        )

    _require_clean_tracked_tree(repository)

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required for Batch execution")
    gateway = OpenAIBatchGateway(
        api_key=api_key,
        organization_id=os.getenv("OPENAI_ORG_ID", "").strip() or None,
        project_id=os.getenv("OPENAI_PROJECT_ID", "").strip() or None,
        base_url=config.base_url,
        timeout_seconds=config.timeout_seconds,
    )
    batch_config = BatchHarnessConfig(
        max_enqueued_tokens=args.batch_max_enqueued_tokens,
        poll_seconds=args.batch_poll_seconds,
    )
    pilot_work = _pilot_work(primary, pilot_count) if args.mode == "pilot" else ()
    try:
        with _exclusive_cache_lock(cache_path):
            with HarnessCache(
                cache_path,
                retry_indeterminate_keys=frozenset(args.retry_indeterminate_cache_key),
            ) as cache:
                if args.mode == "pilot":
                    pilot = await materialize_batch_stage(
                        "p0",
                        pilot_work,
                        cache=cache,
                        gateway=gateway,
                        config=batch_config,
                    )
                    outcomes = {
                        outcome: sum(
                            cache.get(item.identity).outcome == outcome
                            for item in pilot_work
                        )
                        for outcome in sorted(
                            {
                                cache.get(item.identity).outcome
                                for item in pilot_work
                            }
                        )
                    }
                    print(
                        json.dumps(
                            {
                                "api_call_performed": True,
                                "jobs": [_job_summary(job) for job in pilot.jobs],
                                "outcomes": outcomes,
                                "requests": pilot_count,
                                "submitted_usage": (
                                    pilot.submitted_this_invocation_usage.as_json()
                                ),
                            },
                            indent=2,
                            sort_keys=True,
                        )
                    )
                    return
                result = await BatchProbeHarnessRunner(
                    catalog,
                    generation_builder=builder,
                    prompts=prompts,
                    gateway=gateway,
                    cache=cache,
                    config=batch_config,
                ).run()
    finally:
        await gateway.aclose()

    metrics = compute_metrics(result.run)
    report_path = _resolve(
        repository,
        args.report,
        Path(
            f"probes/results/wp15-{config.model.replace('/', '-')}-"
            f"{config.reasoning_effort}-batch.md"
        ),
    )
    raw_summary_path = _resolve(
        repository,
        args.raw_summary,
        Path(
            f"probes/results/raw/wp15-{config.model.replace('/', '-')}-"
            f"{config.reasoning_effort}-batch-summary.json"
        ),
    )
    report = render_report(
        result.run,
        metrics,
        estimate,
        run_kind="live-openai-batch",
        repository_commit=run_commit,
        billing_multiplier=ModelPricing(model=config.model).batch_multiplier,
        fresh_usage_override=result.submitted_this_invocation_usage,
        execution_details=(
            "- Provider path: OpenAI Batch API targeting `/v1/responses`; no synchronous "
            "completion is included.",
            f"- Batch jobs: {len(result.jobs)}.",
            "- Batch input artifacts: "
            + ", ".join(job.input_sha256 for job in result.jobs),
        ),
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")
    raw_summary_path.parent.mkdir(parents=True, exist_ok=True)
    raw_summary_path.write_text(
        json.dumps(
            {
                "cost_estimate": estimate.as_json(),
                "jobs": [_job_summary(job) for job in result.jobs],
                "metrics": metrics,
                "repository_commit": run_commit,
                "run": _jsonable(result.run),
                "submitted_this_invocation_usage": (
                    result.submitted_this_invocation_usage.as_json()
                ),
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "all_gates_passed": metrics["all_gates_passed"],
                "api_call_performed": True,
                "batch_cache": str(cache_path),
                "jobs": [_job_summary(job) for job in result.jobs],
                "raw_summary": str(raw_summary_path),
                "report": str(report_path),
                "submitted_usage": result.submitted_this_invocation_usage.as_json(),
            },
            indent=2,
            sort_keys=True,
        )
    )


def _job_summary(job: BatchJobRecord) -> dict[str, object]:
    return {
        "batch_id": job.batch_id,
        "error_bytes": len(job.error_jsonl),
        "error_file_id": job.error_file_id,
        "error_sha256": digest(job.error_jsonl) if job.error_jsonl else None,
        "estimated_input_tokens": job.estimated_input_tokens,
        "input_bytes": len(job.input_jsonl),
        "input_file_id": job.input_file_id,
        "input_sha256": job.input_sha256,
        "output_bytes": len(job.output_jsonl),
        "output_file_id": job.output_file_id,
        "output_sha256": digest(job.output_jsonl) if job.output_jsonl else None,
        "request_count": job.request_count,
        "shard_index": job.shard_index,
        "stage": job.stage,
        "status": job.status,
    }


def _pilot_work(
    primary: tuple[BatchWorkItem, ...],
    count: int,
) -> tuple[BatchWorkItem, ...]:
    """Cover generation, pairwise, and listwise before filling in stable P0 order."""
    anchors = (primary[0], primary[144], primary[1_008])
    selected = list(anchors)
    selected_ids = {item.custom_id for item in selected}
    for item in primary:
        if len(selected) == count:
            break
        if item.custom_id not in selected_ids:
            selected.append(item)
            selected_ids.add(item.custom_id)
    return tuple(selected)


def _resolve(repository: Path, provided: Path | None, default: Path) -> Path:
    value = default if provided is None else provided
    return value if value.is_absolute() else repository / value


@contextmanager
def _exclusive_cache_lock(cache_path: Path):
    """Prevent concurrent processes from submitting the same deterministic shard twice."""
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = cache_path.with_name(cache_path.name + ".lock")
    with lock_path.open("a+b") as lock_file:
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeError(
                f"another Batch process owns the cache lock {lock_path}"
            ) from error
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def _repository_commit(repository: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _require_clean_tracked_tree(repository: Path) -> None:
    result = subprocess.run(
        ["git", "status", "--short", "--untracked-files=no"],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    )
    if result.stdout.strip():
        raise RuntimeError(
            "Batch execution requires a clean tracked worktree so report provenance binds "
            "the exact running code"
        )


def _jsonable(value: object) -> object:
    if is_dataclass(value) and not isinstance(value, type):
        return _jsonable(asdict(value))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, tuple | list):
        return [_jsonable(item) for item in value]
    return value


def main() -> None:
    asyncio.run(_run(_arguments()))


if __name__ == "__main__":
    main()
