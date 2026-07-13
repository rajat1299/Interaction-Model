"""Environment-backed WP13 app construction tests."""

from pathlib import Path

import pytest

from im.app import load_prompted_policy_factory
from im.policy.prompted import PromptedPolicy


@pytest.mark.asyncio
async def test_factory_constructs_policy_without_calling_provider(monkeypatch) -> None:
    root = Path(__file__).resolve().parents[1]
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("IM_TEACHER_MODEL", "gpt-5.6-terra")
    monkeypatch.setenv("IM_TEACHER_REASONING_EFFORT", "high")

    policy = load_prompted_policy_factory(root)("s_test")
    assert isinstance(policy, PromptedPolicy)
    assert policy.builder.config.model == "gpt-5.6-terra"
    assert policy.builder.config.reasoning_effort == "high"
    await policy.aclose()


def test_factory_requires_key_before_loading_artifacts(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY is missing"):
        load_prompted_policy_factory(tmp_path)
