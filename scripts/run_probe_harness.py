#!/usr/bin/env python3
"""Estimate or run the signed WP15 generation/pairwise/listwise teacher probe."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
from dataclasses import asdict, is_dataclass
from decimal import Decimal, InvalidOperation
from enum import Enum
from pathlib import Path
from typing import cast

from dotenv import load_dotenv

from im.policy.prompted import (
    PromptArtifacts,
    PromptedPolicyConfig,
    PromptRenderer,
    ReasoningEffort,
    ResponsesRequestBuilder,
)
from im.probes.harness.artifacts import load_approved_catalog
from im.probes.harness.backend import OpenAIHarnessBackend, OracleHarnessBackend
from im.probes.harness.cache import HarnessCache
from im.probes.harness.cost import estimate_harness_cost
from im.probes.harness.metrics import compute_metrics
from im.probes.harness.protocols import ProtocolPromptBuilder
from im.probes.harness.report import render_report
from im.probes.harness.runner import HarnessRunnerConfig, ProbeHarnessRunner


def _positive(value: str) -> int:
    parsed = int(value)
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
    parser.add_argument("--mode", choices=("estimate", "mock", "live"), default="estimate")
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--cache", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--raw-summary", type=Path)
    parser.add_argument("--concurrency", type=_positive)
    parser.add_argument("--approve-live-estimate-usd", type=_nonnegative_decimal)
    parser.add_argument(
        "--retry-indeterminate-cache-key",
        action="append",
        default=[],
        metavar="HEX_DIGEST",
        help="authorize one retry for this exact indeterminate cache identity",
    )
    return parser.parse_args()


async def _run(args: argparse.Namespace) -> None:
    repository = args.repository.resolve()
    load_dotenv(repository / ".env", override=False)
    config = PromptedPolicyConfig(
        model=os.getenv("IM_TEACHER_MODEL", "gpt-5.6-terra").strip(),
        reasoning_effort=cast(
            ReasoningEffort,
            os.getenv("IM_TEACHER_REASONING_EFFORT", "high").strip(),
        ),
        max_output_tokens=int(os.getenv("IM_TEACHER_MAX_OUTPUT_TOKENS", "8192")),
    )
    concurrency = args.concurrency or int(os.getenv("IM_TEACHER_CONCURRENCY", "8"))
    catalog = await load_approved_catalog(repository)
    artifacts = PromptArtifacts.from_repository(repository)
    generation_builder = ResponsesRequestBuilder(PromptRenderer(artifacts), config)
    prompts = ProtocolPromptBuilder(artifacts, config)
    estimate = estimate_harness_cost(catalog, generation_builder, prompts)
    print(
        json.dumps(
            {
                "api_call_performed": False,
                "estimate": estimate.as_json(),
                "manifest_sha256": catalog.manifest_sha256,
                "mode": args.mode,
                "model": config.model,
                "reasoning_effort": config.reasoning_effort,
            },
            indent=2,
            sort_keys=True,
        ),
        flush=True,
    )
    if args.mode == "estimate":
        return
    if args.mode == "live":
        required_approval = max(
            estimate.synchronous_no_cache_usd,
            estimate.all_calls_one_retry_warm_cache_usd,
        )
        if (
            args.approve_live_estimate_usd is None
            or args.approve_live_estimate_usd < required_approval
        ):
            raise RuntimeError(
                "live run requires --approve-live-estimate-usd at least "
                f"{required_approval:.6f}; this is an estimate acknowledgement, not a provider cap"
            )

    cache_path = _resolve(
        repository,
        args.cache,
        Path(
            f"probes/results/raw/wp15-{config.model.replace('/', '-')}-"
            f"{config.reasoning_effort}.sqlite"
        ),
    )
    report_path = _resolve(
        repository,
        args.report,
        Path(
            "probes/results/wp15-mocked.md"
            if args.mode == "mock"
            else f"probes/results/wp15-{config.model.replace('/', '-')}-"
            f"{config.reasoning_effort}.md"
        ),
    )
    raw_summary_path = _resolve(
        repository,
        args.raw_summary,
        Path(
            f"probes/results/raw/wp15-{config.model.replace('/', '-')}-"
            f"{config.reasoning_effort}-summary.json"
        ),
    )
    if args.mode == "mock":
        backend = OracleHarnessBackend(
            {
                variant.policy_stream_sha256: variant.expected_action
                for probe in catalog.manifest.probes
                for variant in probe.variants
            }
        )
        run_kind = "mocked-oracle"
    else:
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is required for --mode live")
        backend = OpenAIHarnessBackend(
            generation_builder,
            api_key=api_key,
            organization_id=os.getenv("OPENAI_ORG_ID", "").strip() or None,
            project_id=os.getenv("OPENAI_PROJECT_ID", "").strip() or None,
        )
        run_kind = "live-openai"
    try:
        with HarnessCache(
            cache_path,
            retry_indeterminate_keys=frozenset(args.retry_indeterminate_cache_key),
        ) as cache:
            run = await ProbeHarnessRunner(
                catalog,
                generation_builder=generation_builder,
                prompts=prompts,
                backend=backend,
                cache=cache,
                config=HarnessRunnerConfig(concurrency=concurrency),
            ).run()
    finally:
        await backend.aclose()
    metrics = compute_metrics(run)
    report = render_report(
        run,
        metrics,
        estimate,
        run_kind=run_kind,
        repository_commit=_repository_commit(repository),
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")
    raw_summary_path.parent.mkdir(parents=True, exist_ok=True)
    raw_summary_path.write_text(
        json.dumps(
            {
                "cost_estimate": estimate.as_json(),
                "metrics": metrics,
                "run": _jsonable(run),
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
                "cache": str(cache_path),
                "fresh_usage": run.fresh_usage.as_json(),
                "raw_summary": str(raw_summary_path),
                "report": str(report_path),
            },
            indent=2,
            sort_keys=True,
        )
    )


def _resolve(repository: Path, provided: Path | None, default: Path) -> Path:
    value = default if provided is None else provided
    return value if value.is_absolute() else repository / value


def _repository_commit(repository: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


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
