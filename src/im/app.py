"""Environment-backed OpenAI policy wiring for the runnable browser server."""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from typing import cast

from dotenv import load_dotenv
from fastapi import FastAPI

from im.policy.base import Policy
from im.policy.prompted import (
    PromptArtifacts,
    PromptedPolicy,
    PromptedPolicyConfig,
    PromptRenderer,
    ReasoningEffort,
    ResponsesRequestBuilder,
)
from im.server import create_app


def _positive_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw)
    except ValueError as error:
        raise ValueError(f"{name} must be an integer") from error
    if value <= 0:
        raise ValueError(f"{name} must be positive")
    return value


def load_prompted_policy_factory(root: Path) -> Callable[[str], Policy]:
    """Load local environment once; no network activity occurs here."""
    load_dotenv(root / ".env", override=False)
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is missing; add it to .env before starting WP13")
    config = PromptedPolicyConfig(
        model=os.getenv("IM_TEACHER_MODEL", "gpt-5.6-terra").strip(),
        reasoning_effort=cast(
            ReasoningEffort,
            os.getenv("IM_TEACHER_REASONING_EFFORT", "high").strip(),
        ),
        max_output_tokens=_positive_env("IM_TEACHER_MAX_OUTPUT_TOKENS", 8_192),
    )
    builder = ResponsesRequestBuilder(
        PromptRenderer(PromptArtifacts.from_repository(root)),
        config,
    )

    def factory(_session_id: str) -> Policy:
        return PromptedPolicy(
            builder,
            api_key=api_key,
            organization_id=os.getenv("OPENAI_ORG_ID", "").strip() or None,
            project_id=os.getenv("OPENAI_PROJECT_ID", "").strip() or None,
        )

    return factory


def create_openai_app(repository_root: Path | None = None) -> FastAPI:
    """Construct the WP13 app without performing an OpenAI API request."""
    root = repository_root or Path(__file__).resolve().parents[2]
    return create_app(
        repository_root=root,
        policy_factory=load_prompted_policy_factory(root),
    )
