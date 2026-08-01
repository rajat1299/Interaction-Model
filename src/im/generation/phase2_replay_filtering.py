"""Closed raw-input filtering pipeline for deterministic Phase 2 replay candidates."""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from dataclasses import field as dataclass_field
from itertools import combinations

from im.assets.model import artifact_digest

COMPOSITION_QUOTAS = {
    "rewrite/edit/summarize": 180,
    "extraction/classification/format conversion": 140,
    "context-grounded QA": 140,
    "practical planning": 100,
    "coding/debug": 100,
    "math/data reasoning": 80,
    "stable-knowledge explanation": 80,
    "evidence-grounded comparison/recommendation": 60,
    "translation/language transformation": 40,
    "refusal/uncertainty/missing-information": 40,
    "light creative/casual": 40,
}
LENGTH_BANDS = {
    "short": (1, 50, 500),
    "medium": (51, 150, 350),
    "long": (151, 350, 150),
}
BACKBONE_REVISION = "Qwen/Qwen3.6-35B-A3B"
NO_ROBOTS_AUTHOR_REVISION = "HuggingFaceH4/no_robots@e6f9a4ac5c37faeb744ba9ecf0473184d7f8105b"
OASST2_AUTHOR_REVISION = "OpenAssistant/oasst2@179dd21fc55192153d94adb0e0ce8f69e222bf75"
PROJECT_AUTHORED_RECOVERY_REVISION = "interactionmodel/wp2-9-replay-recovery@v1"
REPLAY_AUTHOR_REVISIONS = {
    "backbone_self_replay": frozenset({BACKBONE_REVISION}),
    "qwen_family_distillation": frozenset(
        {"qwen/qwen3.7-max-20260520", "qwen/qwen3.7-plus-20260602"}
    ),
    "public_authored_dataset": frozenset({NO_ROBOTS_AUTHOR_REVISION, OASST2_AUTHOR_REVISION}),
    "project_authored_recovery": frozenset({PROJECT_AUTHORED_RECOVERY_REVISION}),
}
RENDERER = "qwen3_5_disable_thinking"
TEMPERATURE = 0.2
MAX_COMPLETION_TOKENS = 512
_AUTHOR_CONFIG = {
    "backbone_self_replay": (RENDERER, TEMPERATURE, MAX_COMPLETION_TOKENS),
    "qwen_family_distillation": (RENDERER, TEMPERATURE, MAX_COMPLETION_TOKENS),
    "public_authored_dataset": ("native_source_chat", 0.0, 0),
    "project_authored_recovery": ("native_source_chat", 0.0, 0),
}
MAX_SOURCE_CONTEXT_TOKENS = 512
CONCISE_OUTPUT_FAMILIES = frozenset(
    {
        "coding/debug",
        "extraction/classification/format conversion",
        "stable-knowledge explanation",
        "translation/language transformation",
    }
)
MAX_DATASET_SOURCES = 4
NEAR_DUPLICATE_JACCARD = 0.8
#: Substring containment is only evidence of overlap when both sides carry this much text.
_MINIMUM_CONTAINMENT_LENGTH = 8

_ROW_KEYS = frozenset(
    {
        "completion_id",
        "prompt_id",
        "dataset_source_id",
        "dataset_source_revision",
        "dataset_source_role",
        "task_family",
        "messages",
        "assistant_token_count",
        "provenance",
        "selection_seed",
    }
)
_PROVENANCE_KEYS = frozenset(
    {
        "author_kind",
        "model_revision",
        "tokenizer_revision",
        "renderer",
        "temperature",
        "tools_enabled",
        "max_completion_tokens",
        "completion_count",
        "completion_index",
        "prompt_sha256",
        "request_sha256",
        "completion_sha256",
    }
)
_TOKEN_COUNT_KEYS = frozenset({"count", "tokenizer_revision"})
_MANIFEST_KEYS = frozenset(
    {
        "interaction_texts",
        "development_texts",
        "test_texts",
        "demo_texts",
        "approved_responses",
        "heldout_assets",
        "project_nonces",
        "project_vocabulary_phrases",
    }
)
_REFERENCE_FIELDS = (
    ("interaction_texts", "interaction_overlap"),
    ("development_texts", "development_overlap"),
    ("test_texts", "test_overlap"),
    ("demo_texts", "demo_overlap"),
    ("approved_responses", "approved_response_overlap"),
    ("project_nonces", "project_nonce_overlap"),
    ("project_vocabulary_phrases", "project_vocabulary_overlap"),
)
_DATASET_ROLES = frozenset({"primary", "secondary", "synthetic"})
_PROJECT_PROTOCOL_FIELDS = frozenset(
    {
        "event_id",
        "related_event_id",
        "reply_to_event_id",
        "fire_event_id",
        "target_event_id",
        "result_event_id",
        "decision_policy_seq",
        "stream_sha256",
        "prompt_hash",
        "policy_seq",
        "idle_reason",
        "call_index",
        "interval_ms",
    }
)
_ACTION_TYPES = frozenset(
    {"cancel", "delegate", "idle", "integrate", "mark", "nudge", "respond", "schedule", "skip"}
)
_PROTOCOL_RE = re.compile(
    r"\b(?:" + "|".join(sorted(_PROJECT_PROTOCOL_FIELDS)) + r")\b|"
    r"(?:[\"'](?:type|action)[\"']|\b(?:type|action))\s*:\s*"
    r"(?:[\"'](?:"
    + "|".join(sorted(_ACTION_TYPES))
    + r")[\"']|(?:"
    + "|".join(sorted(_ACTION_TYPES))
    + r")\b)",
    re.IGNORECASE,
)
_HIDDEN_REASONING_RE = re.compile(r"</?(?:think|analysis|reasoning)\b[^>]*>", re.IGNORECASE)
_TOOL_TRANSCRIPT_RE = re.compile(
    r"</?(?:tool|tool_call|function)\b[^>]*>|\b(?:tool_calls|tool_call_id|function_call)\b|"
    r"assistant\s+to=",
    re.IGNORECASE,
)
_CORRUPT_TEXT_RE = re.compile("\N{REPLACEMENT CHARACTER}")
_SYSTEM_PROMPT_REQUEST_RE = re.compile(
    r"\b(?:system (?:prompt|instruction)|instructions? (?:above|before)|"
    r"written above all (?:the )?prompts?)\b",
    re.IGNORECASE,
)
_SYSTEM_PROMPT_DISCLOSURE_RE = re.compile(
    r"\b(?:system instruction|foundational (?:directive|instruction)|"
    r"above all (?:the )?prompts?)\b",
    re.IGNORECASE,
)
_VOLATILE_CLAIM_RE = re.compile(
    r"\bas of (?:today|now)\b|"
    r"\b(?:current|latest|today'?s)\s+"
    r"(?:price|news|weather|score|ceo|president|stock|exchange rate|release|version)\b|"
    r"\bthe\s+(?:current|latest)\s+"
    r"(?:price|ceo|president|score|version|release)\s+(?:is|was)\b|"
    r"\bcurrently,?\s+"
    r"(?:the|there|it|[A-Z][\w.-]*)\s+(?:is|are|has|have|costs?|trades?)\b",
    re.IGNORECASE,
)
_GROUNDING_CUE_RE = re.compile(
    r"\b(?:according to|based on|the (?:provided|supplied|quoted) "
    r"(?:passage|text|context|material)|the passage (?:says|states|reports))\b",
    re.IGNORECASE,
)
_DATED_OR_STATUS_CLAIM_RE = re.compile(
    r"\bas of (?:[a-z]+ )?\d{4}\b|"
    r"\b(?:is|are|has|have)\s+now\b|"
    r"\bcurrently\b",
    re.IGNORECASE,
)
_SOURCE_PREDICTION_RE = re.compile(
    r"\bwill\s+(?:probably|likely)\b[^.?!]{0,100}\bnext\s+"
    r"(?:few|\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+"
    r"(?:days?|months?|years?)\b",
    re.IGNORECASE,
)
_REFUSAL_ACT_RE = re.compile(
    r"^\s*(?:sorry[,.]?\s*)?(?:i|we)\s+"
    r"(?:(?:can(?:not|'t)|won't)\s+"
    r"(?:help|assist|provide|fulfill|comply|create|write|give|verify)|"
    r"(?:am|are)\s+unable\s+to\s+"
    r"(?:help|assist|provide|fulfill|comply|create|write|give|verify))\b",
    re.IGNORECASE,
)
_UNCERTAINTY_RE = re.compile(
    r"\b(?:there is|there's|i have|we have)\s+not enough information\b|"
    r"\bi(?:'m| am) not sure\b",
    re.IGNORECASE,
)
_LEXICAL_CONSTRAINT_RE = re.compile(
    r"\b(?:exactly|at most|no more than)\s+"
    r"(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+"
    r"(?:letters?|words?|sentences?|items?|bullets?|lines?)\b|"
    r"\b(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten)"
    r"[- ](?:letter|word|sentence|item|bullet|line)\b",
    re.IGNORECASE,
)
_BOILERPLATE_RE = re.compile(
    r"^(?:sure|certainly|ok(?:ay)?)\.?$|"
    r"\b(?:as an ai(?: language model)?|as a language model ai|i am a language model|"
    r"i hope (?:that )?helps|"
    r"let me know if[^.?!]{0,100}\b(?:questions?|anything else)\b|"
    r"hi,? how can i help you today|i (?:am not|['’]?m not) smart enough|"
    r"wait for me to become more intelligent)\b",
    re.IGNORECASE,
)
_RUNTIME_IDENTITY_CONTEXT_RE = re.compile(
    r"\bopen ?assistant\b|"
    r"\bas an autonomous [^.?!]{0,40}\bai\b|"
    r"\bi am (?:just )?an? ai\b|"
    r"\bi am a virtual assistant\b|"
    r"\bi(?:'m| am) not able to read or (?:write|respond) in \w+\b|"
    r"\bi(?:'m| am) (?:currently )?unable to (?:look up|access|retrieve|search)\b|"
    r"\b(?:i|my)\b[^.?!]{0,120}\b(?:language model|large language model|"
    r"trained (?:on words|in a large corpus))\b",
    re.IGNORECASE,
)
_CODE_RE = re.compile(r"```|\b(?:def|class|function|python|javascript|sql)\b", re.IGNORECASE)
_ARITHMETIC_RE = re.compile(r"\b\d+\s*[+\-*/]\s*\d+\b")
_SHA256_RE = re.compile(r"sha256:[0-9a-f]{64}\Z")

Fingerprint = tuple[frozenset[str], frozenset[tuple[str, ...]]]


def source_context_rejection_reasons(
    text: str, count_tokens: Callable[[str], int]
) -> tuple[str, ...]:
    """Pre-generation checks for zero-loss OASST assistant context."""
    reasons: list[str] = []
    count = count_tokens(text)
    if not 1 <= count <= MAX_SOURCE_CONTEXT_TOKENS:
        reasons.append("source_context_token_count_out_of_band")
    if text.count("```") % 2:
        reasons.append("unclosed_code_fence")
    for reason, pattern in (
        ("protocol_imitation", _PROTOCOL_RE),
        ("hidden_reasoning", _HIDDEN_REASONING_RE),
        ("tool_transcript", _TOOL_TRANSCRIPT_RE),
        ("fast_changing_fact", _VOLATILE_CLAIM_RE),
        ("boilerplate", _BOILERPLATE_RE),
        ("runtime_identity", _RUNTIME_IDENTITY_CONTEXT_RE),
        ("fast_changing_fact", _SOURCE_PREDICTION_RE),
    ):
        if pattern.search(text):
            reasons.append(reason)
    return tuple(reasons)


@dataclass(frozen=True, slots=True)
class ChatMessage:
    role: str
    content: str


@dataclass(frozen=True, slots=True)
class ReplayProvenance:
    author_kind: str
    model_revision: str
    tokenizer_revision: str
    renderer: str
    temperature: float
    tools_enabled: bool
    max_completion_tokens: int
    completion_count: int
    completion_index: int
    prompt_sha256: str
    request_sha256: str
    completion_sha256: str


@dataclass(frozen=True, slots=True)
class ReplayCandidate:
    completion_id: str
    prompt_id: str
    dataset_source_id: str
    dataset_source_revision: str
    dataset_source_role: str
    task_family: str
    messages: tuple[ChatMessage, ...]
    assistant_token_count: int
    provenance: ReplayProvenance
    selection_seed: str
    prompt_fingerprint: str
    flags: tuple[str, ...] = ()

    @property
    def is_multi_turn(self) -> bool:
        return sum(message.role == "user" for message in self.messages) > 1

    @property
    def length_band(self) -> str:
        for name, (minimum, maximum, _target) in LENGTH_BANDS.items():
            if minimum <= self.assistant_token_count <= maximum:
                return name
        raise AssertionError("validated candidate has no assistant length band")


@dataclass(frozen=True, slots=True)
class ReplayFilterOutcome:
    raw: Mapping[str, object]
    candidate: ReplayCandidate | None
    rejection_reasons: tuple[str, ...]
    flags: tuple[str, ...]

    @property
    def candidate_id(self) -> str | None:
        if self.candidate is not None:
            return self.candidate.completion_id
        value = self.raw.get("completion_id")
        return value if _nonempty_text(value) else None

    @property
    def accepted(self) -> bool:
        return self.candidate is not None and not self.rejection_reasons


@dataclass(frozen=True, slots=True)
class ReplayFilterReport:
    outcomes: tuple[ReplayFilterOutcome, ...]

    @property
    def accepted(self) -> tuple[ReplayFilterOutcome, ...]:
        return tuple(outcome for outcome in self.outcomes if outcome.accepted)


@dataclass(frozen=True, slots=True)
class ReplayReferenceManifest:
    references: tuple[tuple[str, tuple[str, ...]], ...]
    sha256: str
    reference_fingerprints: tuple[tuple[str, tuple[Fingerprint, ...]], ...] = dataclass_field(
        init=False, repr=False, compare=False
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "reference_fingerprints",
            tuple(
                (reason, tuple(_fingerprint(value) for value in values))
                for reason, values in self.references
            ),
        )


def filter_replay_candidates(
    candidates: Sequence[Mapping[str, object]], reference_manifest: Mapping[str, object]
) -> ReplayFilterReport:
    if not isinstance(candidates, Sequence) or isinstance(candidates, (str, bytes)):
        raise TypeError("candidates must be a sequence of raw candidate mappings")
    manifest = load_reference_manifest(reference_manifest)
    outcomes = [_initial_outcome(raw, manifest) for raw in candidates]
    _reject_duplicate_completion_ids(outcomes)
    _enforce_dataset_sources(outcomes)
    _reject_exact_duplicates(outcomes)
    _enforce_dataset_sources(outcomes)
    _reject_near_duplicates(outcomes)
    _enforce_dataset_sources(outcomes)
    _reject_duplicate_prompts(outcomes)
    _enforce_dataset_sources(outcomes)
    return ReplayFilterReport(tuple(outcomes))


def load_reference_manifest(value: Mapping[str, object]) -> ReplayReferenceManifest:
    if not isinstance(value, Mapping) or set(value) != _MANIFEST_KEYS:
        raise ValueError("reference_manifest must have the closed required category set")
    references: list[tuple[str, tuple[str, ...]]] = []
    canonical: dict[str, object] = {}
    for field, reason in _REFERENCE_FIELDS:
        normalised = _normalised_values(value[field], field)
        references.append((reason, normalised))
        canonical[field] = list(normalised)
    assets = value["heldout_assets"]
    if not isinstance(assets, Mapping) or any(
        not _nonempty_text(name) or not isinstance(content, str) for name, content in assets.items()
    ):
        raise TypeError("heldout_assets must map non-empty names to strings")
    asset_pairs = tuple(
        sorted(
            (_normalise_text(name), _normalise_text(content)) for name, content in assets.items()
        )
    )
    asset_references = tuple(item for pair in asset_pairs for item in pair if item)
    references.append(("heldout_asset_overlap", asset_references))
    canonical["heldout_assets"] = [list(pair) for pair in asset_pairs]
    references.sort(key=lambda item: item[0])
    return ReplayReferenceManifest(tuple(references), artifact_digest(canonical))


def _initial_outcome(
    raw: Mapping[str, object], manifest: ReplayReferenceManifest
) -> ReplayFilterOutcome:
    if not isinstance(raw, Mapping):
        return ReplayFilterOutcome({}, None, ("candidate_must_be_mapping",), ())
    reasons: list[str] = []
    flags: list[str] = []
    if set(raw) != _ROW_KEYS:
        _add_once(reasons, "candidate_shape_not_closed")
    completion_id = _required_text(raw, "completion_id", reasons)
    prompt_id = _required_text(raw, "prompt_id", reasons)
    source_id = _required_text(raw, "dataset_source_id", reasons)
    source_revision = _required_text(raw, "dataset_source_revision", reasons)
    source_role = _required_text(raw, "dataset_source_role", reasons)
    if source_role is not None and source_role not in _DATASET_ROLES:
        _add_once(reasons, "dataset_source_role_invalid")
    task_family = _required_text(raw, "task_family", reasons)
    if task_family is not None and task_family not in COMPOSITION_QUOTAS:
        _add_once(reasons, "task_family_not_in_closed_composition")
    messages = _parse_messages(raw.get("messages"), reasons)
    token_count, tokenizer_revision = _parse_token_count(
        raw.get("assistant_token_count"), task_family, reasons, flags
    )
    seed = _required_text(raw, "selection_seed", reasons)
    provenance = _parse_provenance(raw.get("provenance"), messages, reasons)
    if messages:
        _content_checks(messages, task_family, manifest, reasons, flags)
    required_values = (
        completion_id,
        prompt_id,
        source_id,
        source_revision,
        source_role,
        task_family,
        messages,
        token_count,
        tokenizer_revision,
        seed,
        provenance,
    )
    if reasons or None in required_values:
        return ReplayFilterOutcome(raw, None, tuple(reasons), tuple(flags))
    return ReplayFilterOutcome(
        raw,
        ReplayCandidate(
            completion_id,
            prompt_id,
            source_id,
            source_revision,
            source_role,
            task_family,
            messages,
            token_count,
            provenance,
            seed,
            _prompt_fingerprint(messages),
            tuple(flags),
        ),
        (),
        tuple(flags),
    )


def _parse_messages(value: object, reasons: list[str]) -> tuple[ChatMessage, ...] | None:
    if not isinstance(value, (list, tuple)):
        _add_once(reasons, "messages_missing")
        return None
    if len(value) < 2:
        _add_once(reasons, "chat_too_short")
        return None
    messages: list[ChatMessage] = []
    roles: list[str] = []
    for item in value:
        if not isinstance(item, Mapping) or set(item) != {"role", "content"}:
            _add_once(reasons, "chat_message_shape_invalid")
            continue
        role, content = item["role"], item["content"]
        if role not in {"system", "user", "assistant"}:
            _add_once(reasons, "chat_roles_must_be_native")
            continue
        if not _nonempty_text(content):
            _add_once(reasons, "chat_content_empty")
            continue
        roles.append(role)
        messages.append(ChatMessage(role, content.strip()))
    if len(messages) != len(value):
        return None
    task_roles = roles[1:] if roles and roles[0] == "system" else roles
    if len(task_roles) > 6:
        _add_once(reasons, "chat_not_short")
    if (
        not task_roles
        or task_roles[0] != "user"
        or roles[-1] != "assistant"
        or any(
            role != ("user" if index % 2 == 0 else "assistant")
            for index, role in enumerate(task_roles)
        )
        or "system" in task_roles
    ):
        _add_once(reasons, "chat_turn_order_invalid")
    return tuple(messages)


def _parse_token_count(
    value: object,
    task_family: str | None,
    reasons: list[str],
    flags: list[str],
) -> tuple[int | None, str | None]:
    if not isinstance(value, Mapping):
        _add_once(reasons, "assistant_token_count_missing")
        return None, None
    if set(value) != _TOKEN_COUNT_KEYS:
        _add_once(reasons, "assistant_token_count_shape_invalid")
        return None, None
    count, tokenizer_revision = value["count"], value["tokenizer_revision"]
    if isinstance(count, bool) or not isinstance(count, int):
        _add_once(reasons, "assistant_token_count_not_measured")
        return None, None
    if not 1 <= count <= LENGTH_BANDS["long"][1]:
        _add_once(reasons, "assistant_token_count_out_of_band")
    elif count < 5:
        if task_family not in CONCISE_OUTPUT_FAMILIES:
            _add_once(reasons, "assistant_token_count_below_default_minimum")
        else:
            _add_once(flags, "concise_atomic_output_review")
    if tokenizer_revision != BACKBONE_REVISION:
        _add_once(reasons, "assistant_tokenizer_revision_mismatch")
    return count, tokenizer_revision if isinstance(tokenizer_revision, str) else None


def _parse_provenance(
    value: object, messages: tuple[ChatMessage, ...] | None, reasons: list[str]
) -> ReplayProvenance | None:
    if not isinstance(value, Mapping):
        _add_once(reasons, "provenance_missing")
        return None
    if set(value) != _PROVENANCE_KEYS:
        _add_once(reasons, "provenance_shape_not_closed")
        return None
    allowed_revisions = REPLAY_AUTHOR_REVISIONS.get(value["author_kind"])
    if allowed_revisions is None:
        _add_once(reasons, "provenance_author_kind_invalid")
    elif value["model_revision"] not in allowed_revisions:
        _add_once(reasons, "provenance_model_revision_mismatch")
    author_config = _AUTHOR_CONFIG.get(value["author_kind"])
    checks = (("tokenizer_revision", BACKBONE_REVISION, "provenance_tokenizer_revision_mismatch"),)
    if author_config is not None:
        checks += (
            ("renderer", author_config[0], "provenance_renderer_mismatch"),
            ("max_completion_tokens", author_config[2], "provenance_max_completion_mismatch"),
        )
    for field, expected, reason in checks:
        if value[field] != expected:
            _add_once(reasons, reason)
    expected_temperature = author_config[1] if author_config is not None else TEMPERATURE
    if value["temperature"] != expected_temperature or isinstance(value["temperature"], bool):
        _add_once(reasons, "provenance_temperature_mismatch")
    if value["tools_enabled"] is not False:
        _add_once(reasons, "provenance_tools_not_disabled")
    if value["completion_count"] != 1 or value["completion_index"] != 0:
        _add_once(reasons, "provenance_completion_cardinality_invalid")
    identities = ("prompt_sha256", "request_sha256", "completion_sha256")
    if any(
        not isinstance(value[name], str) or _SHA256_RE.fullmatch(value[name]) is None
        for name in identities
    ):
        _add_once(reasons, "provenance_identity_invalid")
    if messages:
        if value["prompt_sha256"] != artifact_digest(_chat_messages(messages[:-1])):
            _add_once(reasons, "provenance_prompt_identity_mismatch")
        if value["completion_sha256"] != artifact_digest(messages[-1].content):
            _add_once(reasons, "provenance_completion_identity_mismatch")
    if value["request_sha256"] != artifact_digest(_request_identity(value)):
        _add_once(reasons, "provenance_request_identity_mismatch")
    if reasons:
        return None
    return ReplayProvenance(
        value["author_kind"],
        value["model_revision"],
        value["tokenizer_revision"],
        value["renderer"],
        value["temperature"],
        value["tools_enabled"],
        value["max_completion_tokens"],
        value["completion_count"],
        value["completion_index"],
        value["prompt_sha256"],
        value["request_sha256"],
        value["completion_sha256"],
    )


def _content_checks(
    messages: tuple[ChatMessage, ...],
    task_family: str | None,
    manifest: ReplayReferenceManifest,
    reasons: list[str],
    flags: list[str],
) -> None:
    task_messages = messages[1:] if messages[0].role == "system" else messages
    all_text = "\n".join(message.content for message in task_messages)
    for (reason, values), (fingerprint_reason, fingerprints) in zip(
        manifest.references, manifest.reference_fingerprints, strict=True
    ):
        if reason != fingerprint_reason:
            raise AssertionError("reference fingerprints are not aligned with their values")
        compared = (
            (messages[-1].content,)
            if reason == "approved_response_overlap"
            else (
                *(message.content for message in task_messages),
                all_text,
            )
        )
        if any(_reference_overlap(text, values, fingerprints) for text in compared):
            _add_once(reasons, reason)
    if _PROTOCOL_RE.search(all_text):
        _add_once(reasons, "protocol_imitation")
    if _HIDDEN_REASONING_RE.search(all_text):
        _add_once(reasons, "hidden_reasoning")
    if _TOOL_TRANSCRIPT_RE.search(all_text):
        _add_once(reasons, "tool_transcript")
    if _CORRUPT_TEXT_RE.search(all_text):
        _add_once(reasons, "text_encoding_corrupt")
    answer = messages[-1].content
    context = "\n".join(message.content for message in task_messages[:-1])
    user_text = "\n".join(message.content for message in task_messages if message.role == "user")
    if _SYSTEM_PROMPT_REQUEST_RE.search(user_text) and _SYSTEM_PROMPT_DISCLOSURE_RE.search(answer):
        _add_once(reasons, "system_prompt_disclosure")
    if task_family == "refusal/uncertainty/missing-information":
        _add_once(flags, "refusal_family_review")
    if _VOLATILE_CLAIM_RE.search(answer):
        if _context_contains_volatile_claim(context) or _GROUNDING_CUE_RE.search(answer):
            _add_once(flags, "source_grounded_volatile_claim_review")
        else:
            _add_once(reasons, "fast_changing_fact")
    elif _DATED_OR_STATUS_CLAIM_RE.search(answer):
        _add_once(flags, "dated_or_status_claim_review")
    if _BOILERPLATE_RE.search(messages[-1].content):
        _add_once(reasons, "boilerplate")
    if _REFUSAL_ACT_RE.search(answer):
        if task_family == "refusal/uncertainty/missing-information":
            _add_once(flags, "intentional_refusal_review")
        else:
            _add_once(reasons, "refusal_outside_intentional_family")
    elif _UNCERTAINTY_RE.search(answer):
        _add_once(flags, "uncertainty_review")
    if _CODE_RE.search(all_text):
        _add_once(flags, "code_spot_check")
    if task_family == "math/data reasoning" or _ARITHMETIC_RE.search(all_text):
        _add_once(flags, "arithmetic_spot_check")
    if task_family == "translation/language transformation":
        _add_once(flags, "language_transformation_review")
    if _LEXICAL_CONSTRAINT_RE.search(
        "\n".join(message.content for message in task_messages if message.role == "user")
    ):
        _add_once(flags, "lexical_constraint_review")
    if sum(message.role == "user" for message in task_messages) > 1:
        _add_once(flags, "multi_turn_review")


def _context_contains_volatile_claim(text: str) -> bool:
    return any(
        _VOLATILE_CLAIM_RE.search(sentence) and "?" not in sentence
        for sentence in re.split(r"(?<=[.!?])\s+|\n+", text)
    )


def _reject_duplicate_completion_ids(outcomes: list[ReplayFilterOutcome]) -> None:
    grouped: dict[str, list[int]] = defaultdict(list)
    for index, outcome in enumerate(outcomes):
        if outcome.accepted and outcome.candidate is not None:
            grouped[outcome.candidate.completion_id].append(index)
    for indexes in grouped.values():
        if len(indexes) > 1:
            for index in indexes:
                _add_rejection(outcomes, index, "duplicate_completion_id")


def _enforce_dataset_sources(outcomes: list[ReplayFilterOutcome]) -> None:
    accepted = [
        (index, outcome.candidate) for index, outcome in enumerate(outcomes) if outcome.accepted
    ]
    source_ids = sorted(
        {candidate.dataset_source_id for _index, candidate in accepted if candidate}
    )
    allowed = frozenset(source_ids[:MAX_DATASET_SOURCES])
    for index, candidate in accepted:
        if candidate is not None and candidate.dataset_source_id not in allowed:
            _add_rejection(outcomes, index, "dataset_source_limit_exceeded")
    by_source: dict[str, list[tuple[int, ReplayCandidate]]] = defaultdict(list)
    for index, outcome in enumerate(outcomes):
        if outcome.accepted and outcome.candidate is not None:
            by_source[outcome.candidate.dataset_source_id].append((index, outcome.candidate))
    for records in by_source.values():
        if len({candidate.dataset_source_revision for _index, candidate in records}) != 1:
            for index, _candidate in records:
                _add_rejection(outcomes, index, "dataset_source_revision_not_frozen")
        if len({candidate.dataset_source_role for _index, candidate in records}) != 1:
            for index, _candidate in records:
                _add_rejection(outcomes, index, "dataset_source_role_inconsistent")
    primary_ids = {
        outcome.candidate.dataset_source_id
        for outcome in outcomes
        if outcome.accepted
        and outcome.candidate is not None
        and outcome.candidate.dataset_source_role == "primary"
    }
    if len(primary_ids) != 1:
        for index, outcome in enumerate(outcomes):
            if outcome.accepted:
                _add_rejection(outcomes, index, "dataset_primary_source_invalid")


def _reject_exact_duplicates(outcomes: list[ReplayFilterOutcome]) -> None:
    grouped: dict[str, list[int]] = defaultdict(list)
    for index, outcome in enumerate(outcomes):
        if outcome.accepted and outcome.candidate is not None:
            grouped[artifact_digest(_chat_messages(outcome.candidate.messages))].append(index)
    _reject_grouped_duplicates(outcomes, grouped, "exact_duplicate")


def _reject_near_duplicates(outcomes: list[ReplayFilterOutcome]) -> None:
    indexes = [index for index, outcome in enumerate(outcomes) if outcome.accepted]
    parent = {index: index for index in indexes}

    def root(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        left_root, right_root = root(left), root(right)
        if left_root != right_root:
            parent[max(left_root, right_root)] = min(left_root, right_root)

    fingerprints = {
        index: _fingerprint(
            " ".join(
                message.content
                for message in outcomes[index].candidate.messages
                if message.role != "system"
            )
        )
        for index in indexes
        if outcomes[index].candidate is not None
    }
    # ponytail: O(n²) is bounded by the ~1,250-row pool; use MinHash/LSH if it grows.
    for left, right in combinations(indexes, 2):
        if _near_match(*fingerprints[left], *fingerprints[right]):
            union(left, right)
    groups: dict[int, list[int]] = defaultdict(list)
    for index in indexes:
        groups[root(index)].append(index)
    for values in groups.values():
        _reject_grouped_duplicates(outcomes, {"component": values}, "near_duplicate")


def _reject_duplicate_prompts(outcomes: list[ReplayFilterOutcome]) -> None:
    for field in ("prompt_id", "prompt_fingerprint"):
        grouped: dict[str, list[int]] = defaultdict(list)
        for index, outcome in enumerate(outcomes):
            if outcome.accepted and outcome.candidate is not None:
                grouped[str(getattr(outcome.candidate, field))].append(index)
        _reject_grouped_duplicates(outcomes, grouped, f"duplicate_{field}")


def _reject_grouped_duplicates(
    outcomes: list[ReplayFilterOutcome], groups: Mapping[object, Sequence[int]], reason: str
) -> None:
    for indexes in groups.values():
        leader = min(indexes, key=lambda index: outcomes[index].candidate_id or "")
        leader_id = outcomes[leader].candidate_id
        for index in indexes:
            if index != leader:
                _add_rejection(outcomes, index, f"{reason}:{leader_id}")


def _prompt_fingerprint(messages: tuple[ChatMessage, ...]) -> str:
    return artifact_digest(
        [
            {"role": message.role, "content": _normalise_text(message.content)}
            for message in messages[:-1]
            if message.role != "system"
        ]
    )


def _reference_overlap(
    text: str, references: tuple[str, ...], reference_fingerprints: tuple[Fingerprint, ...]
) -> bool:
    normalised = _normalise_text(text)
    if not normalised:
        return False
    fingerprint = _fingerprint(normalised)
    for reference, reference_fingerprint in zip(references, reference_fingerprints, strict=True):
        # The minimum length binds both sides.  Guarding only the reference made the
        # `normalised in reference` direction fire for any very short answer that happened to sit
        # inside a long reference, e.g. the answer "15" inside "remind me at 7:15 am ...".
        if min(len(reference), len(normalised)) >= _MINIMUM_CONTAINMENT_LENGTH and (
            reference in normalised or normalised in reference
        ):
            return True
        if _near_match(*fingerprint, *reference_fingerprint):
            return True
    return False


def _fingerprint(text: str) -> Fingerprint:
    tokens = re.findall(r"\w+", text.casefold())
    return frozenset(tokens), frozenset(
        tuple(tokens[index : index + 3]) for index in range(len(tokens) - 2)
    )


def _near_match(
    left_tokens: frozenset[str],
    left_shingles: frozenset[tuple[str, ...]],
    right_tokens: frozenset[str],
    right_shingles: frozenset[tuple[str, ...]],
) -> bool:
    return _jaccard(left_tokens, right_tokens) >= NEAR_DUPLICATE_JACCARD or (
        bool(left_shingles)
        and bool(right_shingles)
        and _jaccard(left_shingles, right_shingles) >= NEAR_DUPLICATE_JACCARD
    )


def _normalised_values(value: object, field: str) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise TypeError(f"{field} must be a sequence of strings")
    if any(not isinstance(item, str) for item in value):
        raise TypeError(f"{field} must contain only strings")
    return tuple(sorted({_normalise_text(item) for item in value if _normalise_text(item)}))


def _required_text(raw: Mapping[str, object], field: str, reasons: list[str]) -> str | None:
    value = raw.get(field)
    if not _nonempty_text(value):
        _add_once(reasons, f"{field}_missing")
        return None
    return value.strip()


def _request_identity(provenance: Mapping[str, object]) -> dict[str, object]:
    return {
        name: provenance[name]
        for name in (
            "prompt_sha256",
            "model_revision",
            "tokenizer_revision",
            "renderer",
            "temperature",
            "tools_enabled",
            "max_completion_tokens",
            "completion_count",
            "completion_index",
        )
    }


def _chat_messages(messages: Sequence[ChatMessage]) -> list[dict[str, str]]:
    return [{"role": message.role, "content": message.content} for message in messages]


def _normalise_text(value: str) -> str:
    return " ".join(value.casefold().split())


def _jaccard(left: frozenset[object], right: frozenset[object]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _add_rejection(outcomes: list[ReplayFilterOutcome], index: int, reason: str) -> None:
    outcome = outcomes[index]
    if reason not in outcome.rejection_reasons:
        outcomes[index] = replace(outcome, rejection_reasons=outcome.rejection_reasons + (reason,))


def _add_once(values: list[str], value: str) -> None:
    if value not in values:
        values.append(value)


def _nonempty_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())
