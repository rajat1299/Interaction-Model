#!/usr/bin/env python3
"""Validate WP13 configuration and estimate spend without calling OpenAI."""

from __future__ import annotations

import argparse
import json
import os
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
    estimate_run_cost,
)


def _positive(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be positive")
    return parsed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--decisions", type=_positive, default=30)
    parser.add_argument("--average-policy-bytes", type=_positive, default=12_000)
    parser.add_argument("--max-policy-bytes", type=_positive, default=48_000)
    parser.add_argument("--expected-output-tokens", type=_positive, default=2_000)
    parser.add_argument("--attempts-per-decision", type=_positive, choices=(1, 2), default=1)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = Path(__file__).resolve().parents[1]
    load_dotenv(root / ".env", override=False)
    config = PromptedPolicyConfig(
        model=os.getenv("IM_TEACHER_MODEL", "gpt-5.6-terra").strip(),
        reasoning_effort=cast(
            ReasoningEffort,
            os.getenv("IM_TEACHER_REASONING_EFFORT", "high").strip(),
        ),
        max_output_tokens=int(os.getenv("IM_TEACHER_MAX_OUTPUT_TOKENS", "8192")),
    )
    builder = ResponsesRequestBuilder(
        PromptRenderer(PromptArtifacts.from_repository(root)),
        config,
    )
    pricing = ModelPricing()
    estimate = estimate_run_cost(
        builder,
        decisions=args.decisions,
        average_policy_bytes=args.average_policy_bytes,
        max_policy_bytes=args.max_policy_bytes,
        expected_output_tokens=args.expected_output_tokens,
        attempts_per_decision=args.attempts_per_decision,
        pricing=pricing,
    )
    result = {
        "api_call_performed": False,
        "estimate": estimate.as_json(),
        "key_configured": bool(os.getenv("OPENAI_API_KEY", "").strip()),
        "model": config.model,
        "pricing": {
            "batch_discount": "50%",
            "cached_input_per_million_usd": str(pricing.cached_input_per_million),
            "input_per_million_usd": str(pricing.input_per_million),
            "output_per_million_usd": str(pricing.output_per_million),
            "source_date": pricing.source_date,
        },
        "reasoning_effort": config.reasoning_effort,
    }
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
