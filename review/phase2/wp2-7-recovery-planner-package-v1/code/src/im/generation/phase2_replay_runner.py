"""Backbone self-replay generation runner (D10 step 5): prompts -> OpenRouter -> candidates.

Emits JSONL rows shaped for `phase2_replay_filtering.filter_replay_candidates`.

Four properties are enforced here because getting any of them wrong produces a corpus that looks
fine and is not reproducible:

* **Manifest binding.** Every row records the manifest digest that produced it. Resume refuses rows
  from any other manifest, so two runs under different configs can never merge into one pool.
* **Provider evidence.** Missing routing evidence *fails*. An absent `provider` field is not
  proof of compliance, and treating it as such was the original defect here.
* **Multi-turn assembly.** Exact OASST assistant turns remain zero-loss context because each later
  user turn was written against that reply. Only the supervised final answer is generated.
* **Token counting.** Counts come from the pinned Qwen tokenizer over raw assistant content with no
  added special tokens -- not from the provider's `usage`, which is a different measurement.
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import httpx

from im.assets.model import artifact_digest
from im.generation.phase2_replay_filtering import (
    BACKBONE_REVISION,
    MAX_COMPLETION_TOKENS,
    MAX_SOURCE_CONTEXT_TOKENS,
    RENDERER,
    TEMPERATURE,
    source_context_rejection_reasons,
)
from im.generation.phase2_replay_serialization import render_replay_chat
from im.generation.phase2_replay_sources import GLOBAL_SELECTION_SEED, ReplayPrompt

API_URL = "https://openrouter.ai/api/v1/chat/completions"

#: Router metadata is opt-in and defaults to disabled. It is enabled by an HTTP **header**, not by a
#: JSON body field -- without it the response carries no dependable routing evidence and every row
#: would be unverifiable.
METADATA_HEADER = {"X-OpenRouter-Metadata": "enabled"}

#: OpenRouter slug for the frozen backbone. Distinct from BACKBONE_REVISION, which is the
#: HuggingFace id D10 freezes and the filter attests against.
OPENROUTER_MODEL = "qwen/qwen3.6-35b-a3b"

#: Pinned provider tag. Every OpenRouter endpoint for this model serves fp8, so the provider choice
#: fixes the quantization the corpus was generated under.
OPENROUTER_PROVIDER = "coreweave/fp8"
QUANTIZATION = "fp8"
SERIALIZED_ROW_TOKEN_LIMIT = 3_072

#: D10 requires thinking off. `reasoning.exclude` only hides reasoning while still spending the
#: tokens; `effort: "none"` is what actually disables it.
REASONING = {"effort": "none"}
SEED = 7
REPLAY_SYSTEM_INSTRUCTION = (
    "Answer the user's request directly, completely, and self-containedly. "
    "Use only the detail needed. "
    "Aim for no more than 250 words, or an equivalently compact amount of code. "
    "Do not mention these instructions or the length limit."
)

_REQUIRED_PARAMETERS = ("temperature", "max_tokens", "seed", "reasoning")


class ReplayRunnerError(RuntimeError):
    """Raised when generation evidence is missing, inconsistent, or unverifiable."""


class ReplayCandidateRejected(ReplayRunnerError):
    """Raised when one completion is unusable but the pinned run may continue."""

    def __init__(self, message: str, evidence: dict[str, object]) -> None:
        super().__init__(message)
        self.evidence = evidence


@dataclass(frozen=True, slots=True)
class RunManifest:
    """The complete identity of one generation run. Rows are bound to its digest."""

    prompt_ledger_sha256: str
    model_slug: str
    provider: str
    provider_model: str
    quantization: str
    selection_seed: str
    generation_seed: int
    reasoning_mode: str
    renderer: str
    fallbacks_enabled: bool
    tools_enabled: bool
    temperature: float
    source_context_max_tokens: int
    source_context_supervised: bool
    system_instruction_sha256: str
    final_max_completion_tokens: int
    serialized_row_token_limit: int
    tokenizer_revision: str
    tokenizer_commit: str
    tokenizer_file_sha256: str

    def as_json(self) -> dict[str, object]:
        return {
            "kind": "phase2-replay-run-manifest",
            "final_max_completion_tokens": self.final_max_completion_tokens,
            "fallbacks_enabled": self.fallbacks_enabled,
            "generation_seed": self.generation_seed,
            "model_slug": self.model_slug,
            "prompt_ledger_sha256": self.prompt_ledger_sha256,
            "provider": self.provider,
            "provider_model": self.provider_model,
            "quantization": self.quantization,
            "reasoning_mode": self.reasoning_mode,
            "renderer": self.renderer,
            "selection_seed": self.selection_seed,
            "source_context_max_tokens": self.source_context_max_tokens,
            "source_context_supervised": self.source_context_supervised,
            "system_instruction_sha256": self.system_instruction_sha256,
            "serialized_row_token_limit": self.serialized_row_token_limit,
            "temperature": self.temperature,
            "tokenizer_commit": self.tokenizer_commit,
            "tokenizer_file_sha256": self.tokenizer_file_sha256,
            "tokenizer_revision": self.tokenizer_revision,
            "tools_enabled": self.tools_enabled,
        }

    @property
    def digest(self) -> str:
        return artifact_digest(self.as_json())


def build_manifest(
    *,
    prompt_ledger_sha256: str,
    tokenizer_commit: str,
    tokenizer_file_sha256: str,
    selection_seed: str = GLOBAL_SELECTION_SEED,
    model_slug: str = OPENROUTER_MODEL,
    provider: str = OPENROUTER_PROVIDER,
    provider_model: str = OPENROUTER_MODEL,
    quantization: str = QUANTIZATION,
) -> RunManifest:
    return RunManifest(
        prompt_ledger_sha256=prompt_ledger_sha256,
        model_slug=model_slug,
        provider=provider,
        provider_model=provider_model,
        quantization=quantization,
        selection_seed=selection_seed,
        generation_seed=SEED,
        reasoning_mode=str(REASONING["effort"]),
        renderer=RENDERER,
        fallbacks_enabled=False,
        tools_enabled=False,
        temperature=TEMPERATURE,
        source_context_max_tokens=MAX_SOURCE_CONTEXT_TOKENS,
        source_context_supervised=False,
        system_instruction_sha256=artifact_digest(REPLAY_SYSTEM_INSTRUCTION),
        final_max_completion_tokens=MAX_COMPLETION_TOKENS,
        serialized_row_token_limit=SERIALIZED_ROW_TOKEN_LIMIT,
        tokenizer_revision=BACKBONE_REVISION,
        tokenizer_commit=tokenizer_commit,
        tokenizer_file_sha256=tokenizer_file_sha256,
    )


def qwen_token_encoder(tokenizer_path: Path) -> Callable[[str], tuple[int, ...]]:
    """Encode text with the pinned Qwen tokenizer artifact."""
    try:
        from tokenizers import Tokenizer
    except ImportError as error:  # pragma: no cover - dependency guard
        raise ReplayRunnerError(
            "the `tokenizers` package is required to measure replay rows"
        ) from error
    tokenizer = Tokenizer.from_file(str(tokenizer_path))
    return lambda text: tuple(tokenizer.encode(text, add_special_tokens=False).ids)


def qwen_token_counter(tokenizer_path: Path) -> Callable[[str], int]:
    """Count raw content with the pinned Qwen tokenizer, no added special tokens.

    Uses the lightweight `tokenizers` package: the tokenizer artifact only, no model weights and no
    `transformers` dependency.
    """
    encode = qwen_token_encoder(tokenizer_path)
    return lambda text: len(encode(text))


def build_payload(
    messages: Sequence[dict[str, str]],
    *,
    max_tokens: int = MAX_COMPLETION_TOKENS,
    model_slug: str = OPENROUTER_MODEL,
    provider: str = OPENROUTER_PROVIDER,
) -> dict[str, object]:
    return {
        "model": model_slug,
        "messages": [dict(message) for message in messages],
        "temperature": TEMPERATURE,
        "max_tokens": max_tokens,
        "reasoning": REASONING,
        "seed": SEED,
        "provider": {
            "order": [provider],
            "allow_fallbacks": False,
            "require_parameters": True,
        },
    }


def preflight_endpoint(
    client: httpx.Client,
    provider: str = OPENROUTER_PROVIDER,
    provider_model: str = OPENROUTER_MODEL,
    model_slug: str = OPENROUTER_MODEL,
    quantization: str = QUANTIZATION,
) -> dict[str, object]:
    """Verify the pinned endpoint exists and supports every parameter before spending anything.

    Absence of evidence fails. A run that cannot prove its routing is not reproducible, and the
    cheapest moment to discover that is before the first billed call.
    """
    author, _, slug = model_slug.partition("/")
    response = client.get(f"https://openrouter.ai/api/v1/models/{author}/{slug}/endpoints")
    response.raise_for_status()
    endpoints = response.json().get("data", {}).get("endpoints", [])
    match = next((item for item in endpoints if item.get("tag") == provider), None)
    if match is None:
        raise ReplayRunnerError(
            f"pinned provider {provider!r} is not serving {model_slug!r}; "
            f"available: {sorted(str(item.get('tag')) for item in endpoints)}"
        )
    if match.get("quantization") != quantization:
        raise ReplayRunnerError(
            f"pinned provider quantization is {match.get('quantization')!r}, manifest says "
            f"{quantization!r}; the corpus would not be reproducible under the recorded config"
        )
    declared_model = str(match.get("name") or "").partition(" | ")[2] or match.get("model_id")
    if declared_model != provider_model:
        raise ReplayRunnerError(
            f"pinned provider model is {declared_model!r}, manifest says {provider_model!r}"
        )
    supported = set(match.get("supported_parameters") or ())
    missing = [name for name in _REQUIRED_PARAMETERS if name not in supported]
    if missing:
        raise ReplayRunnerError(f"pinned provider does not support {missing}")
    return {
        "context_length": match.get("context_length"),
        "provider": match.get("provider_name"),
        "quantization": match.get("quantization"),
        "served_model": declared_model,
        "status": match.get("status"),
        "tag": match.get("tag"),
    }


def _post_generation(
    client: httpx.Client,
    messages: Sequence[dict[str, str]],
    *,
    max_tokens: int = MAX_COMPLETION_TOKENS,
    model_slug: str = OPENROUTER_MODEL,
    provider: str = OPENROUTER_PROVIDER,
) -> httpx.Response:
    """Post one generation, retrying only transient rate limits."""
    for attempt in range(3):
        response = client.post(
            API_URL,
            json=build_payload(
                messages,
                max_tokens=max_tokens,
                model_slug=model_slug,
                provider=provider,
            ),
        )
        if response.status_code != 429:
            response.raise_for_status()
            return response
        if attempt == 2:
            detail = response.text[:500]
            raise ReplayRunnerError(f"OpenRouter rate limit persisted after 3 attempts: {detail}")
        retry_after = response.headers.get("Retry-After")
        delay = float(retry_after) if retry_after else 2 ** (attempt + 1)
        time.sleep(min(max(delay, 1), 30))
    raise AssertionError("unreachable")


def selected_endpoint(metadata: Mapping[str, object]) -> Mapping[str, object]:
    """Return the single selected entry from `endpoints.available[]`.

    Documented entry keys are `provider` (display name), `model`, and `selected`. Unknown additive
    fields are ignored, but zero or several selected entries means the route is not identified.
    """
    endpoints = metadata.get("endpoints")
    available = endpoints.get("available") if isinstance(endpoints, Mapping) else None
    if not isinstance(available, Sequence) or isinstance(available, (str, bytes)):
        raise ReplayRunnerError("openrouter_metadata.endpoints.available is missing or not a list")
    chosen = [
        item for item in available if isinstance(item, Mapping) and item.get("selected") is True
    ]
    if len(chosen) != 1:
        raise ReplayRunnerError(
            f"expected exactly one selected endpoint, found {len(chosen)}; the served route is "
            "not identified"
        )
    return chosen[0]


def resolve_generation_record(client: httpx.Client, generation_id: str) -> dict[str, object]:
    """Authoritative routing record for one generation, including every provider attempted."""
    response = client.get("https://openrouter.ai/api/v1/generation", params={"id": generation_id})
    response.raise_for_status()
    data = response.json().get("data")
    return data if isinstance(data, dict) else {}


def _assert_compliant(
    body: Mapping[str, object],
    endpoint: Mapping[str, object],
    model_slug: str = OPENROUTER_MODEL,
) -> dict[str, object]:
    """Prove the response came from the pinned endpoint, first attempt, prompt untransformed.

    Field locations follow the documented `OpenRouterMetadata` shape: `attempt` and `pipeline` are
    **top-level** on the metadata object, while `provider`/`model`/`selected` live on the entries of
    `endpoints.available[]`. Reading `attempt` off the endpoint entry instead -- as an earlier
    version did -- yields None and rejects every response.
    """
    model = body.get("model")
    if model != model_slug:
        raise ReplayRunnerError(f"model drift: pinned {model_slug!r}, served {model!r}")
    choices = body.get("choices") or []
    if not choices or not isinstance(choices[0], Mapping):
        raise ReplayRunnerError("response carries no choices")
    finish = choices[0].get("finish_reason")
    metadata = body.get("openrouter_metadata")
    if not isinstance(metadata, Mapping):
        raise ReplayRunnerError(
            "response carries no openrouter_metadata. Missing routing evidence fails rather than "
            f"passes: confirm the {tuple(METADATA_HEADER)[0]} header is being sent."
        )
    attempt = metadata.get("attempt")
    if attempt != 1:
        # Anything past the first attempt means a retry or fallback served the row, so it was not
        # produced under the pinned configuration.
        raise ReplayRunnerError(f"openrouter_metadata.attempt is {attempt!r}, expected 1")
    pipeline = metadata.get("pipeline") or ()
    if pipeline:
        # The documented example is context_compression/middle-out, which rewrites the messages.
        # Supervising an answer produced from a rewritten prompt would break the correspondence
        # between the recorded prompt and the trained target.
        raise ReplayRunnerError(
            f"a transforming pipeline was applied ({pipeline!r}); the supervised answer would not "
            "correspond to the recorded prompt"
        )
    chosen = selected_endpoint(metadata)
    served = chosen.get("provider")
    expected = str(endpoint.get("provider") or "")
    if not expected or served != expected:
        raise ReplayRunnerError(
            f"endpoint drift: selected provider {served!r} is not the pinned {expected!r}"
        )
    if chosen.get("model") != endpoint.get("served_model"):
        raise ReplayRunnerError(
            f"selected endpoint serves {chosen.get('model')!r}, not "
            f"{endpoint.get('served_model')!r}"
        )
    usage = body.get("usage")
    details = usage.get("completion_tokens_details") if isinstance(usage, Mapping) else None
    reasoning_tokens = details.get("reasoning_tokens") if isinstance(details, Mapping) else None
    if (
        not isinstance(reasoning_tokens, int)
        or isinstance(reasoning_tokens, bool)
        or reasoning_tokens < 0
    ):
        raise ReplayRunnerError("provider reasoning-token evidence is missing or invalid")
    if reasoning_tokens:
        raise ReplayRunnerError(
            f"provider reported {reasoning_tokens} reasoning tokens despite effort='none'"
        )
    evidence = {
        "attempt": attempt,
        "finish_reason": finish,
        "generation_id": body.get("id"),
        "is_byok": metadata.get("is_byok"),
        "model": model,
        "reasoning_tokens": reasoning_tokens,
        "region": metadata.get("region"),
        "selected_provider": served,
        "strategy": metadata.get("strategy"),
    }
    if finish != "stop":
        # A truncated answer is not a clean self-replay target even when its token count lands
        # in-band. The route is verified first so the rejected attempt remains auditable.
        raise ReplayCandidateRejected(
            f"finish_reason {finish!r} is not 'stop'; a truncated or filtered completion is not a "
            "usable replay target",
            evidence,
        )
    message = choices[0].get("message")
    completion = message.get("content") if isinstance(message, Mapping) else None
    if not isinstance(completion, str) or not completion.strip():
        raise ReplayCandidateRejected(
            "response carries no non-empty text completion",
            evidence,
        )
    return evidence


def build_candidate(
    prompt: ReplayPrompt,
    messages: Sequence[dict[str, str]],
    completion: str,
    *,
    manifest: RunManifest,
    count_tokens: Callable[[str], int],
    router_metadata: dict[str, object],
) -> dict[str, object]:
    """Assemble one filter-ready row.

    `messages` already alternates and excludes the final supervised answer.
    """
    self_replay = manifest.model_slug == OPENROUTER_MODEL
    identity = {
        "prompt_sha256": artifact_digest([dict(message) for message in messages]),
        "model_revision": BACKBONE_REVISION if self_replay else manifest.provider_model,
        "tokenizer_revision": BACKBONE_REVISION,
        "renderer": RENDERER,
        "temperature": TEMPERATURE,
        "tools_enabled": False,
        "max_completion_tokens": MAX_COMPLETION_TOKENS,
        "completion_count": 1,
        "completion_index": 0,
    }
    return {
        "completion_id": f"replay-{prompt.prompt_id}",
        "prompt_id": prompt.prompt_id,
        "dataset_source_id": prompt.dataset_source_id,
        "dataset_source_revision": prompt.dataset_source_revision,
        "dataset_source_role": prompt.dataset_source_role,
        "task_family": prompt.task_family,
        "messages": [dict(message) for message in messages]
        + [{"role": "assistant", "content": completion}],
        "assistant_token_count": {
            "count": count_tokens(completion),
            "tokenizer_revision": BACKBONE_REVISION,
        },
        "selection_seed": manifest.selection_seed,
        "provenance": {
            "author_kind": (
                "backbone_self_replay" if self_replay else "qwen_family_distillation"
            ),
            "request_sha256": artifact_digest(identity),
            "completion_sha256": artifact_digest(completion),
            **identity,
        },
    }


def build_audit_record(
    prompt: ReplayPrompt,
    *,
    manifest: RunManifest,
    router_metadata: dict[str, object],
    call_records: Sequence[dict[str, object]] = (),
    serialized_row_token_count: int,
    source_context_assistant_tokens: int,
) -> dict[str, object]:
    """Run evidence for one row, kept in a sidecar.

    The candidate shape is a *closed* key set enforced by the filter, so manifest binding, router
    metadata, and source message ids cannot ride on the row itself without every row being rejected
    as `candidate_shape_not_closed`. They are recorded alongside and joined on `prompt_id`.
    """
    return {
        "calls": [dict(record) for record in call_records],
        "completion_id": f"replay-{prompt.prompt_id}",
        "generation_calls": prompt.generation_calls_required,
        "is_multi_turn": prompt.is_multi_turn,
        "prompt_id": prompt.prompt_id,
        "router_metadata": router_metadata,
        "run_manifest_sha256": manifest.digest,
        "source_context_assistant_tokens": source_context_assistant_tokens,
        "serialized_row_token_count": serialized_row_token_count,
        "source_message_ids": list(prompt.source_message_ids),
        "supervised_final_tokens": int(call_records[-1]["assistant_token_count"]),
    }


def generate_replay_completions(
    prompts: Iterable[ReplayPrompt],
    *,
    output_path: Path,
    audit_path: Path,
    failure_path: Path | None = None,
    manifest: RunManifest,
    count_tokens: Callable[[str], int],
    api_key: str | None = None,
    timeout: float = 120.0,
) -> dict[str, object]:
    """Generate one supervised completion per prompt, appending JSONL.

    Resumable, but only within a single manifest.
    """
    key = api_key or os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise ReplayRunnerError("OPENROUTER_API_KEY is not set")
    done = completed_prompt_ids(audit_path, manifest)
    rejected = (
        completed_prompt_ids(failure_path, manifest, terminal_only=True)
        if failure_path
        else set()
    )
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        **METADATA_HEADER,
    }
    written = calls = 0
    with (
        httpx.Client(timeout=timeout, headers=headers) as client,
        output_path.open("a", encoding="utf-8") as sink,
        audit_path.open("a", encoding="utf-8") as audit,
    ):
        endpoint = preflight_endpoint(
            client,
            manifest.provider,
            manifest.provider_model,
            manifest.model_slug,
            manifest.quantization,
        )
        for prompt in prompts:
            if prompt.prompt_id in done or prompt.prompt_id in rejected:
                continue
            if len(prompt.assistant_context_turns) != max(0, len(prompt.user_turns) - 1):
                raise ReplayRunnerError(
                    "source assistant context does not alternate with user turns"
                )
            messages: list[dict[str, str]] = [
                {"role": "system", "content": REPLAY_SYSTEM_INSTRUCTION}
            ]
            router_metadata: dict[str, object] = {}
            call_records: list[dict[str, object]] = []
            for index, turn in enumerate(prompt.user_turns):
                messages.append({"role": "user", "content": turn})
                if index < len(prompt.assistant_context_turns):
                    context = prompt.assistant_context_turns[index]
                    reasons = source_context_rejection_reasons(context, count_tokens)
                    if reasons:
                        raise ReplayRunnerError(
                            f"source assistant context failed pre-generation checks: {reasons}"
                        )
                    messages.append({"role": "assistant", "content": context})
            response = _post_generation(
                client,
                messages,
                max_tokens=manifest.final_max_completion_tokens,
                model_slug=manifest.model_slug,
                provider=manifest.provider,
            )
            body = response.json()
            calls += 1
            try:
                router_metadata = {
                    **_assert_compliant(body, endpoint, manifest.model_slug),
                    "endpoint": endpoint,
                }
            except ReplayRunnerError as error:
                if failure_path is None:
                    raise
                evidence = (
                    error.evidence
                    if isinstance(error, ReplayCandidateRejected)
                    else {"endpoint": endpoint}
                )
                with failure_path.open("a", encoding="utf-8") as failures:
                    failures.write(
                        json.dumps(
                            {
                                "call_index": 0,
                                "call_role": "supervised",
                                "error": str(error),
                                "evidence": {**evidence, "endpoint": endpoint},
                                "generation_calls": 1,
                                "generation_id": body.get("id"),
                                "max_completion_tokens": manifest.final_max_completion_tokens,
                                "messages_before_failed_call": messages,
                                "prior_calls": call_records,
                                "prompt_id": prompt.prompt_id,
                                "response": body,
                                "run_manifest_sha256": manifest.digest,
                                "terminal_candidate_rejection": isinstance(
                                    error, ReplayCandidateRejected
                                ),
                            },
                            sort_keys=True,
                        )
                        + "\n"
                    )
                if not isinstance(error, ReplayCandidateRejected):
                    raise
                continue
            completion = body["choices"][0]["message"]["content"]
            call_records.append(
                {
                    "assistant_token_count": count_tokens(completion),
                    "call_index": 0,
                    "call_role": "supervised",
                    "completion_sha256": artifact_digest(completion),
                    "max_completion_tokens": manifest.final_max_completion_tokens,
                    "router_metadata": router_metadata,
                    "usage": body.get("usage"),
                }
            )
            row = build_candidate(
                prompt,
                messages,
                completion,
                manifest=manifest,
                count_tokens=count_tokens,
                router_metadata=router_metadata,
            )
            serialized_count = count_tokens(render_replay_chat(row["messages"]))
            if serialized_count > manifest.serialized_row_token_limit:
                if failure_path is None:
                    raise ReplayCandidateRejected(
                        "serialized replay row exceeds the frozen token limit",
                        {"serialized_row_token_count": serialized_count},
                    )
                with failure_path.open("a", encoding="utf-8") as failures:
                    failures.write(
                        json.dumps(
                            {
                                "error": "serialized replay row exceeds the frozen token limit",
                                "generation_calls": len(call_records),
                                "max_serialized_row_tokens": manifest.serialized_row_token_limit,
                                "prior_calls": call_records,
                                "prompt_id": prompt.prompt_id,
                                "run_manifest_sha256": manifest.digest,
                                "serialized_row_token_count": serialized_count,
                                "terminal_candidate_rejection": True,
                            },
                            sort_keys=True,
                        )
                        + "\n"
                    )
                continue
            sink.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            audit.write(
                json.dumps(
                    build_audit_record(
                        prompt,
                        manifest=manifest,
                        router_metadata=router_metadata,
                        call_records=call_records,
                        serialized_row_token_count=serialized_count,
                        source_context_assistant_tokens=sum(
                            count_tokens(text) for text in prompt.assistant_context_turns
                        ),
                    ),
                    sort_keys=True,
                )
                + "\n"
            )
            sink.flush()
            audit.flush()
            written += 1
    return {"calls": calls, "rows_written": written, "manifest_sha256": manifest.digest}


def completed_prompt_ids(
    audit_path: Path, manifest: RunManifest, *, terminal_only: bool = False
) -> set[str]:
    """Resume only over audit rows from this exact manifest; anything else is a hard error."""
    output_path = audit_path
    if not output_path.exists():
        return set()
    done: set[str] = set()
    with output_path.open(encoding="utf-8") as source:
        for line in source:
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("run_manifest_sha256") != manifest.digest:
                raise ReplayRunnerError(
                    f"{output_path} contains rows from manifest "
                    f"{row.get('run_manifest_sha256')!r}, but this run is {manifest.digest!r}. "
                    "Resuming across manifests would silently merge two configurations into one "
                    "pool. Start a new output file."
                )
            if not terminal_only or row.get("terminal_candidate_rejection") is True:
                done.add(str(row["prompt_id"]))
    return done


__all__ = [
    "API_URL",
    "OPENROUTER_MODEL",
    "OPENROUTER_PROVIDER",
    "QUANTIZATION",
    "REASONING",
    "ReplayRunnerError",
    "RunManifest",
    "build_audit_record",
    "build_candidate",
    "build_manifest",
    "build_payload",
    "completed_prompt_ids",
    "generate_replay_completions",
    "METADATA_HEADER",
    "preflight_endpoint",
    "selected_endpoint",
    "resolve_generation_record",
    "qwen_token_counter",
]
