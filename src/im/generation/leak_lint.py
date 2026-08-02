"""C6 checks that teacher prompts contain only the captured policy prefix."""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
from re import fullmatch

from im.assets.model import artifact_digest, canonical_artifact_bytes
from im.generation.scenarios import (
    GeneratedScenario,
    ScenarioValidationError,
    validate_generated_scenario,
)
from im.generation.validity import GeneratedStreamValidationError
from im.policy.prompted import PromptRenderer, RenderedPrompt


class LeakLintError(ValueError):
    """A teacher prompt exposes sidecar state or an invalid decision boundary."""


_FROZEN_ARTIFACT_SHA256S = {
    "action schema": "09b64516ba1612d269f33397ffe291cb3cc26ca0ae3e621b319e539fd2f725f3",
    "behavior spec": "a31d19e1982f63ee154a7c8cf5f18e9ed68dbfd3ad731b78ecd263f34cf506c9",
    "prompt template": "f130c1927f72a073d9a6c9397a65acb9c915d8919c9536aec9cda8d7fd771fa9",
}


@dataclass(frozen=True, slots=True)
class LeakLintPromptIdentity:
    """One exact rendered teacher prompt, keyed to its captured decision."""

    stream_sha256: str
    call_index: int
    prompt_hash: str
    prompt_sha256: str

    def __post_init__(self) -> None:
        for name in ("stream_sha256", "prompt_hash", "prompt_sha256"):
            value = getattr(self, name)
            if not isinstance(value, str) or fullmatch(r"sha256:[0-9a-f]{64}", value) is None:
                raise ValueError(f"{name} must be a sha256 digest")
        if (
            isinstance(self.call_index, bool)
            or not isinstance(self.call_index, int)
            or self.call_index < 1
        ):
            raise ValueError("call_index must be a positive integer")

    def as_json_object(self) -> dict[str, object]:
        return {
            "stream_sha256": self.stream_sha256,
            "call_index": self.call_index,
            "prompt_hash": self.prompt_hash,
            "prompt_sha256": self.prompt_sha256,
        }


@dataclass(frozen=True, slots=True)
class LeakLintReport:
    """Canonical evidence that a packaged set was rendered and checked."""

    stream_count: int
    decision_count: int
    prompts: tuple[LeakLintPromptIdentity, ...]
    canonical_bytes: bytes = field(init=False)
    sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if any(
            isinstance(value, bool) or not isinstance(value, int) or value < 1
            for value in (self.stream_count, self.decision_count)
        ):
            raise TypeError("leak-lint counts must be positive integers")
        if not isinstance(self.prompts, tuple) or not all(
            isinstance(prompt, LeakLintPromptIdentity) for prompt in self.prompts
        ):
            raise TypeError("leak-lint prompts must be an immutable identity tuple")
        if self.decision_count != len(self.prompts):
            raise ValueError("leak-lint decision count must cover every prompt")
        identities = tuple((prompt.stream_sha256, prompt.call_index) for prompt in self.prompts)
        if identities != tuple(sorted(set(identities))):
            raise ValueError("leak-lint prompt identities must be sorted and unique")
        if self.stream_count != len({prompt.stream_sha256 for prompt in self.prompts}):
            raise ValueError("leak-lint stream count must cover every stream")
        value = self.as_json_object()
        object.__setattr__(self, "canonical_bytes", canonical_artifact_bytes(value))
        object.__setattr__(self, "sha256", artifact_digest(value))

    def as_json_object(self) -> dict[str, object]:
        return {
            "format_version": 1,
            "stream_count": self.stream_count,
            "decision_count": self.decision_count,
            "prompts": [prompt.as_json_object() for prompt in self.prompts],
        }


def lint_teacher_prompts(
    generated_scenarios: tuple[GeneratedScenario, ...], renderer: PromptRenderer
) -> LeakLintReport:
    """Render and reject every sidecar or future-event leak in a generated batch."""
    if not isinstance(generated_scenarios, tuple) or not all(
        isinstance(generated, GeneratedScenario) for generated in generated_scenarios
    ):
        raise TypeError("generated_scenarios must be a tuple of GeneratedScenario")
    if not generated_scenarios:
        raise LeakLintError("generated_scenarios must not be empty")
    if not isinstance(renderer, PromptRenderer):
        raise TypeError("renderer must be a PromptRenderer")

    _assert_frozen_artifacts(renderer)
    generated_scenarios = tuple(
        sorted(generated_scenarios, key=lambda generated: generated.stream.sha256)
    )
    if len({generated.stream.sha256 for generated in generated_scenarios}) != len(
        generated_scenarios
    ):
        raise LeakLintError("generated_scenarios contain a duplicate stream identity")
    frozen_renderer = PromptRenderer(renderer.artifacts)
    prompts: list[LeakLintPromptIdentity] = []
    for generated in generated_scenarios:
        _validate_structure(generated)
        for captured in generated.stream.decisions:
            rendered = _render(
                renderer, captured.prefix_bytes, generated.stream.sha256, captured.call_index
            )
            _assert_exact_render(
                rendered,
                frozen_renderer.render(captured.prefix_bytes),
                generated.stream.sha256,
                captured.call_index,
            )
            prompts.append(
                LeakLintPromptIdentity(
                    stream_sha256=generated.stream.sha256,
                    call_index=captured.call_index,
                    prompt_hash=rendered.prompt_hash,
                    prompt_sha256=artifact_digest(
                        {
                            "system": rendered.system,
                            "user": rendered.user,
                            "prompt_hash": rendered.prompt_hash,
                        }
                    ),
                )
            )
    return LeakLintReport(len(generated_scenarios), len(prompts), tuple(prompts))


def _assert_frozen_artifacts(renderer: PromptRenderer) -> None:
    artifacts = renderer.artifacts
    values = {
        "action schema": artifacts.action_schema,
        "behavior spec": artifacts.behavior_spec,
        "prompt template": artifacts.prompt_template,
    }
    for name, value in values.items():
        if sha256(value).hexdigest() != _FROZEN_ARTIFACT_SHA256S[name]:
            raise LeakLintError(f"{name} differs from its Phase 0 frozen identity")


def _validate_structure(generated: GeneratedScenario) -> None:
    try:
        validate_generated_scenario(generated)
    except (GeneratedStreamValidationError, ScenarioValidationError) as error:
        raise LeakLintError(
            f"structural mismatch for stream {generated.stream.sha256}: {error}"
        ) from error


def _render(
    renderer: PromptRenderer, prefix_bytes: bytes, stream_sha256: str, call_index: int
) -> RenderedPrompt:
    try:
        rendered = renderer.render(prefix_bytes)
    except (TypeError, ValueError) as error:
        raise LeakLintError(
            f"could not render stream {stream_sha256} decision {call_index}: {error}"
        ) from error
    if rendered.prompt_hash != renderer.artifacts.prompt_hash:
        raise LeakLintError(
            f"structural mismatch for stream {stream_sha256} decision {call_index}: "
            "rendered prompt hash differs from its artifacts"
        )
    return rendered


def _assert_exact_render(
    rendered: RenderedPrompt,
    expected: RenderedPrompt,
    stream_sha256: str,
    call_index: int,
) -> None:
    if rendered != expected:
        raise LeakLintError(
            f"teacher prompt differs from frozen rendering for stream {stream_sha256} "
            f"decision {call_index}"
        )
