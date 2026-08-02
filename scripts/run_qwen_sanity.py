#!/usr/bin/env python3
"""Estimate or run the frozen WP16 generation-only Qwen sanity check."""

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

from dotenv import load_dotenv

from im.policy.prompted import (
    PromptArtifacts,
    PromptedPolicyConfig,
    PromptRenderer,
    ResponsesRequestBuilder,
    ResponsesRouting,
)
from im.probes.harness.artifacts import load_approved_catalog
from im.probes.harness.backend import OracleHarnessBackend, ResponsesHarnessBackend
from im.probes.harness.cache import HarnessCache
from im.probes.harness.protocols import ProtocolPromptBuilder
from im.probes.harness.runner import HarnessRunnerConfig, ProbeHarnessRunner
from im.probes.harness.wp16 import (
    QWEN_MODEL,
    QWEN_SANITY_PROBE_IDS,
    QWEN_UPSTREAM_PROVIDER,
    compute_qwen_metrics,
    estimate_qwen_cost,
    generation_completions,
    render_qwen_report,
    wp16_spec_sha256,
)


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
    parser.add_argument("--concurrency", type=_positive, default=4)
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
        model=QWEN_MODEL,
        provider="openrouter",
        reasoning_effort="none",
        max_output_tokens=1024,
        max_attempts=1,
        base_url="https://openrouter.ai/api/v1",
        routing=ResponsesRouting(
            only=(QWEN_UPSTREAM_PROVIDER,),
            allow_fallbacks=False,
            require_parameters=True,
        ),
    )
    catalog = await load_approved_catalog(repository)
    artifacts = PromptArtifacts.from_repository(repository)
    builder = ResponsesRequestBuilder(PromptRenderer(artifacts), config)
    estimate = estimate_qwen_cost(catalog, builder)
    print(
        json.dumps(
            {
                "api_call_performed": False,
                "estimate": estimate.as_json(),
                "manifest_sha256": catalog.manifest_sha256,
                "mode": args.mode,
                "model": config.model,
                "provider": config.provider,
                "upstream_provider": QWEN_UPSTREAM_PROVIDER,
                "wp16_spec_sha256": wp16_spec_sha256(),
            },
            indent=2,
            sort_keys=True,
        ),
        flush=True,
    )
    if args.mode == "estimate":
        return
    if args.mode == "live":
        if (
            args.approve_live_estimate_usd is None
            or args.approve_live_estimate_usd < estimate.ceiling_no_cache_usd
        ):
            raise RuntimeError(
                "live run requires --approve-live-estimate-usd at least "
                f"{estimate.ceiling_no_cache_usd:.6f}; this acknowledges an estimate, not a cap"
            )
        if _tracked_changes(repository):
            raise RuntimeError("live WP16 execution requires a clean tracked worktree")

    cache_path = _resolve(
        repository,
        args.cache,
        Path(
            "probes/results/raw/wp16-qwen3.6-35b-a3b-mocked.sqlite"
            if args.mode == "mock"
            else "probes/results/raw/wp16-qwen3.6-35b-a3b-openrouter-akashml.sqlite"
        ),
    )
    report_path = _resolve(
        repository,
        args.report,
        Path(
            "probes/results/wp16-qwen3.6-35b-a3b-mocked.md"
            if args.mode == "mock"
            else "probes/results/wp16-qwen3.6-35b-a3b-openrouter-akashml.md"
        ),
    )
    raw_summary_path = _resolve(
        repository,
        args.raw_summary,
        Path(
            "probes/results/raw/wp16-qwen3.6-35b-a3b-mocked-summary.json"
            if args.mode == "mock"
            else "probes/results/raw/wp16-qwen3.6-35b-a3b-openrouter-akashml-summary.json"
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
    else:
        api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("OPENROUTER_API_KEY is required for --mode live")
        backend = ResponsesHarnessBackend(
            builder,
            api_key=api_key,
            extra_headers={"X-OpenRouter-Metadata": "enabled"},
        )

    try:
        with HarnessCache(
            cache_path,
            retry_indeterminate_keys=frozenset(args.retry_indeterminate_cache_key),
        ) as cache:
            run = await ProbeHarnessRunner(
                catalog,
                generation_builder=builder,
                prompts=ProtocolPromptBuilder(artifacts, config),
                backend=backend,
                cache=cache,
                config=HarnessRunnerConfig(concurrency=args.concurrency),
            ).run_generation_only(probe_ids=QWEN_SANITY_PROBE_IDS)
            completions = generation_completions(catalog, builder, cache)
    finally:
        await backend.aclose()

    metrics = compute_qwen_metrics(
        run,
        completions,
        require_provider_traces=args.mode == "live",
    )
    report = render_qwen_report(
        run=run,
        metrics=metrics,
        estimate=estimate,
        repository_commit=_repository_commit(repository),
        prompt_hash=artifacts.prompt_hash,
        cache_path=str(cache_path),
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
                "wp16_spec_sha256": wp16_spec_sha256(),
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
                "cache": str(cache_path),
                "metrics": metrics,
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
    return _git(repository, "rev-parse", "HEAD").strip()


def _tracked_changes(repository: Path) -> bool:
    return bool(_git(repository, "status", "--porcelain", "--untracked-files=no").strip())


def _git(repository: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


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
