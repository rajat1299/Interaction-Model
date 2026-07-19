"""Deterministic offline replay filtering, planning, and review-gated finalization."""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict, deque
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from hashlib import sha256
from itertools import combinations

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
    "short": (5, 50, 500),
    "medium": (51, 150, 350),
    "long": (151, 350, 150),
}
BACKBONE_REVISION = "Qwen/Qwen3.6-35B-A3B"
RENDERER = "qwen3_5_disable_thinking"
TEMPERATURE = 0.2
MAX_COMPLETION_TOKENS = 512
MAX_DATASET_SOURCES = 2
MULTI_TURN_TARGET = 200
TARGET_EXAMPLES = 1_000
SUPERVISED_TOKEN_MIN = 100_000
SUPERVISED_TOKEN_MAX = 130_000
NEAR_DUPLICATE_JACCARD = 0.8

_BANDS = tuple(LENGTH_BANDS)
_TURN_KINDS = ("single", "multi")
_ROW_KEYS = frozenset(
    {
        "completion_id",
        "prompt_id",
        "dataset_source_id",
        "dataset_source_revision",
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
_PROTOCOL_RE = re.compile(
    r"\b(?:event_id|related_event_id|reply_to_event_id|decision_policy_seq|"
    r"stream_sha256|prompt_hash|policy_seq|idle_reason|call_index)\b|"
    r'"(?:related_event_id|reply_to_event_id|interval_ms)"\s*:|'
    r'"type"\s*:\s*"(?:cancel|delegate|idle|integrate|mark|nudge|respond|schedule|skip)"',
    re.IGNORECASE,
)
_HIDDEN_REASONING_RE = re.compile(r"</?(?:think|analysis|reasoning)\b[^>]*>", re.IGNORECASE)
_TOOL_TRANSCRIPT_RE = re.compile(
    r"</?(?:tool|tool_call|function)\b[^>]*>|\b(?:tool_calls|tool_call_id|function_call)\b|"
    r"assistant\s+to=",
    re.IGNORECASE,
)
_FAST_FACT_RE = re.compile(
    r"\b(?:current|latest|live|today'?s|breaking|recent)\s+"
    r"(?:price|news|weather|score|ceo|president|stock|exchange rate|release|version)\b|"
    r"\b(?:who is|what is)\s+the\s+(?:current|latest)\b",
    re.IGNORECASE,
)
_REFUSAL_RE = re.compile(
    r"\b(?:i (?:can(?:not|'t)|won't)|unable to|not enough information|"
    r"i(?:'m| am) not sure)\b",
    re.IGNORECASE,
)
_BOILERPLATE_RE = re.compile(
    r"\b(?:as an ai language model|i hope this helps|"
    r"let me know if you have any other questions)\b",
    re.IGNORECASE,
)
_CODE_RE = re.compile(r"```|\b(?:def|class|function|python|javascript|sql)\b", re.IGNORECASE)
_ARITHMETIC_RE = re.compile(r"\b\d+\s*[+\-*/]\s*\d+\b")
_SHA256_RE = re.compile(r"sha256:[0-9a-f]{64}\Z")


class ReplaySelectionDeficitError(ValueError):
    """The accepted replay slice cannot satisfy its closed quotas."""

    def __init__(self, report: ReplayDeficitReport) -> None:
        self.report = report
        super().__init__(f"replay selection is infeasible: {report.summary()}")


class ReplayReviewError(ValueError):
    """A provisional plan lacks approvals or needs a fresh replacement review."""

    def __init__(self, message: str, replacement_plan: ReplayPlan | None = None) -> None:
        self.replacement_plan = replacement_plan
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class ChatMessage:
    role: str
    content: str


@dataclass(frozen=True, slots=True)
class ReplayProvenance:
    """Closed, immutable evidence that one completion is backbone self-replay."""

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
    """Validated replay row, with no caller-controlled selection evidence."""

    completion_id: str
    prompt_id: str
    dataset_source_id: str
    dataset_source_revision: str
    task_family: str
    messages: tuple[ChatMessage, ...]
    assistant_token_count: int
    assistant_tokenizer_revision: str
    provenance: ReplayProvenance
    selection_seed: str
    prompt_fingerprint: str
    flags: tuple[str, ...] = ()

    @property
    def candidate_id(self) -> str:
        """Compatibility name for raw-slice reporting; it is the completion identity."""
        return self.completion_id

    @property
    def final_answer(self) -> str:
        return self.messages[-1].content

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

    @property
    def rejected(self) -> tuple[ReplayFilterOutcome, ...]:
        return tuple(outcome for outcome in self.outcomes if not outcome.accepted)


@dataclass(frozen=True, slots=True)
class ReplayDeficitReport:
    task_family_deficits: dict[str, int]
    length_band_deficits: dict[str, int]
    multi_turn_deficit: int
    single_turn_deficit: int
    selection_seed_mismatches: tuple[str, ...] = ()
    supervised_token_total: int | None = None
    joint_constraint_failure: bool = False

    def summary(self) -> str:
        parts: list[str] = []
        if self.task_family_deficits:
            parts.append(f"task families={self.task_family_deficits}")
        if self.length_band_deficits:
            parts.append(f"length bands={self.length_band_deficits}")
        if self.multi_turn_deficit:
            parts.append(f"multi-turn={self.multi_turn_deficit}")
        if self.single_turn_deficit:
            parts.append(f"single-turn={self.single_turn_deficit}")
        if self.selection_seed_mismatches:
            parts.append(f"selection seed mismatch={self.selection_seed_mismatches}")
        if self.supervised_token_total is not None:
            parts.append(f"supervised tokens={self.supervised_token_total}")
        if self.joint_constraint_failure:
            parts.append("joint family/length/turn allocation")
        return "; ".join(parts) or "unknown allocation failure"


@dataclass(frozen=True, slots=True)
class ReplayPlan:
    """Provisional selection; it cannot become frozen data until review approval."""

    filter_report: ReplayFilterReport
    eligible: tuple[ReplayCandidate, ...]
    selection_seed: str
    provisional_selected: tuple[ReplayCandidate, ...]
    human_review_sample: tuple[ReplayCandidate, ...]
    flagged_selected: tuple[ReplayCandidate, ...]
    human_review_queue: tuple[ReplayCandidate, ...]


@dataclass(frozen=True, slots=True)
class ReplaySelection:
    selected: tuple[ReplayCandidate, ...]
    human_review_sample: tuple[ReplayCandidate, ...]
    flagged_selected: tuple[ReplayCandidate, ...]
    human_review_queue: tuple[ReplayCandidate, ...]


def filter_replay_candidates(
    candidates: Sequence[Mapping[str, object]],
    *,
    interaction_texts: Sequence[str] = (),
    development_texts: Sequence[str] = (),
    test_texts: Sequence[str] = (),
    demo_texts: Sequence[str] = (),
    approved_responses: Sequence[str] = (),
    heldout_assets: Mapping[str, str] = {},
    project_nonces: Sequence[str] = (),
    project_vocabulary_phrases: Sequence[str] = (),
) -> ReplayFilterReport:
    """Filter raw, already-sampled rows without prompting, networking, or model calls."""
    if not isinstance(candidates, Sequence) or isinstance(candidates, (str, bytes)):
        raise TypeError("candidates must be a sequence of raw candidate mappings")
    references = _reference_sets(
        interaction_texts=interaction_texts,
        development_texts=development_texts,
        test_texts=test_texts,
        demo_texts=demo_texts,
        approved_responses=approved_responses,
        heldout_assets=heldout_assets,
        project_nonces=project_nonces,
        project_vocabulary_phrases=project_vocabulary_phrases,
    )
    outcomes = [_initial_outcome(raw, references) for raw in candidates]
    _reject_duplicate_completion_ids(outcomes)
    _limit_dataset_sources(outcomes)
    _reject_exact_duplicates(outcomes)
    _reject_near_duplicates(outcomes)
    _reject_duplicate_prompts(outcomes)
    return ReplayFilterReport(tuple(outcomes))


def plan_replay_selection(
    candidates: Sequence[Mapping[str, object]],
    *,
    selection_seed: str,
    interaction_texts: Sequence[str] = (),
    development_texts: Sequence[str] = (),
    test_texts: Sequence[str] = (),
    demo_texts: Sequence[str] = (),
    approved_responses: Sequence[str] = (),
    heldout_assets: Mapping[str, str] = {},
    project_nonces: Sequence[str] = (),
    project_vocabulary_phrases: Sequence[str] = (),
) -> ReplayPlan:
    """Build a provisional 1,000-row replay plan directly from raw candidate rows."""
    if not isinstance(candidates, Sequence) or isinstance(candidates, (str, bytes)):
        raise TypeError("candidates must be raw candidate mappings, not a filter report")
    if not _nonempty_text(selection_seed):
        raise ValueError("selection_seed must be non-empty")
    report = filter_replay_candidates(
        candidates,
        interaction_texts=interaction_texts,
        development_texts=development_texts,
        test_texts=test_texts,
        demo_texts=demo_texts,
        approved_responses=approved_responses,
        heldout_assets=heldout_assets,
        project_nonces=project_nonces,
        project_vocabulary_phrases=project_vocabulary_phrases,
    )
    eligible = tuple(outcome.candidate for outcome in report.accepted)
    accepted = tuple(candidate for candidate in eligible if candidate)
    return _plan_from_eligible(report, accepted, selection_seed)


def finalize_replay_selection(
    plan: ReplayPlan, *, review_approvals: Mapping[str, bool]
) -> ReplaySelection:
    """Freeze only a plan whose complete deterministic review queue is explicitly approved."""
    if not isinstance(plan, ReplayPlan):
        raise TypeError("plan must be returned by plan_replay_selection")
    if not isinstance(review_approvals, Mapping):
        raise TypeError("review_approvals must map every queued completion ID to a bool")
    expected_ids = tuple(candidate.completion_id for candidate in plan.human_review_queue)
    if set(review_approvals) != set(expected_ids) or any(
        not isinstance(value, bool) for value in review_approvals.values()
    ):
        raise ReplayReviewError("explicit approval is required for every queued ID")
    failed = frozenset(key for key, value in review_approvals.items() if not value)
    if failed:
        replacement = _plan_from_eligible(
            plan.filter_report,
            tuple(
                candidate for candidate in plan.eligible if candidate.completion_id not in failed
            ),
            plan.selection_seed,
        )
        raise ReplayReviewError(
            "failed reviews were removed; replacement review is required before finalization",
            replacement,
        )
    return ReplaySelection(
        plan.provisional_selected,
        plan.human_review_sample,
        plan.flagged_selected,
        plan.human_review_queue,
    )


def _plan_from_eligible(
    report: ReplayFilterReport, candidates: tuple[ReplayCandidate, ...], selection_seed: str
) -> ReplayPlan:
    selected = _select_candidates(candidates, selection_seed)
    review_sample = _stratified_review_sample(selected, selection_seed)
    flagged = tuple(candidate for candidate in selected if candidate.flags)
    reviewed_ids = {candidate.completion_id for candidate in review_sample}
    review_queue = review_sample + tuple(
        candidate for candidate in flagged if candidate.completion_id not in reviewed_ids
    )
    return ReplayPlan(
        report,
        candidates,
        selection_seed,
        selected,
        review_sample,
        flagged,
        review_queue,
    )


def _initial_outcome(
    raw: Mapping[str, object], references: Mapping[str, tuple[str, ...]]
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
    task_family = _required_text(raw, "task_family", reasons)
    if task_family is not None and task_family not in COMPOSITION_QUOTAS:
        _add_once(reasons, "task_family_not_in_closed_composition")
    messages = _parse_messages(raw.get("messages"), reasons)
    token_count, tokenizer_revision = _parse_token_count(raw.get("assistant_token_count"), reasons)
    seed = _required_text(raw, "selection_seed", reasons)
    provenance = _parse_provenance(raw.get("provenance"), messages, reasons)
    if messages:
        _content_checks(messages, task_family, references, reasons, flags)
    required_values = (
        completion_id,
        prompt_id,
        source_id,
        source_revision,
        task_family,
        messages,
        token_count,
        tokenizer_revision,
        seed,
        provenance,
    )
    if reasons or None in required_values:
        return ReplayFilterOutcome(raw, None, tuple(reasons), tuple(flags))
    candidate = ReplayCandidate(
        completion_id=completion_id,
        prompt_id=prompt_id,
        dataset_source_id=source_id,
        dataset_source_revision=source_revision,
        task_family=task_family,
        messages=messages,
        assistant_token_count=token_count,
        assistant_tokenizer_revision=tokenizer_revision,
        provenance=provenance,
        selection_seed=seed,
        prompt_fingerprint=_prompt_fingerprint(messages),
        flags=tuple(flags),
    )
    return ReplayFilterOutcome(raw, candidate, (), tuple(flags))


def _required_text(raw: Mapping[str, object], field: str, reasons: list[str]) -> str | None:
    value = raw.get(field)
    if not _nonempty_text(value):
        _add_once(reasons, f"{field}_missing")
        return None
    return value.strip()


def _parse_messages(value: object, reasons: list[str]) -> tuple[ChatMessage, ...] | None:
    if not isinstance(value, (list, tuple)):
        _add_once(reasons, "messages_missing")
        return None
    if len(value) < 2:
        _add_once(reasons, "chat_too_short")
        return None
    if len(value) > 6:
        _add_once(reasons, "chat_not_short")
    messages: list[ChatMessage] = []
    roles: list[str] = []
    for item in value:
        if not isinstance(item, Mapping) or set(item) != {"role", "content"}:
            _add_once(reasons, "chat_message_shape_invalid")
            continue
        role = item["role"]
        content = item["content"]
        if role not in {"user", "assistant"}:
            _add_once(reasons, "chat_roles_must_be_native")
            continue
        if not _nonempty_text(content):
            _add_once(reasons, "chat_content_empty")
            continue
        roles.append(role)
        messages.append(ChatMessage(role, content.strip()))
    if len(messages) != len(value):
        return None
    if roles[0] != "user" or roles[-1] != "assistant" or any(
        role != ("user" if index % 2 == 0 else "assistant")
        for index, role in enumerate(roles)
    ):
        _add_once(reasons, "chat_turn_order_invalid")
    return tuple(messages)


def _parse_token_count(value: object, reasons: list[str]) -> tuple[int | None, str | None]:
    if not isinstance(value, Mapping):
        _add_once(reasons, "assistant_token_count_missing")
        return None, None
    if set(value) != _TOKEN_COUNT_KEYS:
        _add_once(reasons, "assistant_token_count_shape_invalid")
        return None, None
    count = value["count"]
    tokenizer_revision = value["tokenizer_revision"]
    if isinstance(count, bool) or not isinstance(count, int):
        _add_once(reasons, "assistant_token_count_not_measured")
        return None, None
    if not LENGTH_BANDS["short"][0] <= count <= LENGTH_BANDS["long"][1]:
        _add_once(reasons, "assistant_token_count_out_of_band")
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
    author_kind = value["author_kind"]
    if author_kind != "backbone_self_replay":
        _add_once(reasons, "provenance_author_kind_invalid")
    if value["model_revision"] != BACKBONE_REVISION:
        _add_once(reasons, "provenance_model_revision_mismatch")
    if value["tokenizer_revision"] != BACKBONE_REVISION:
        _add_once(reasons, "provenance_tokenizer_revision_mismatch")
    if value["renderer"] != RENDERER:
        _add_once(reasons, "provenance_renderer_mismatch")
    if value["temperature"] != TEMPERATURE or isinstance(value["temperature"], bool):
        _add_once(reasons, "provenance_temperature_mismatch")
    if value["tools_enabled"] is not False:
        _add_once(reasons, "provenance_tools_not_disabled")
    if value["max_completion_tokens"] != MAX_COMPLETION_TOKENS:
        _add_once(reasons, "provenance_max_completion_mismatch")
    if value["completion_count"] != 1 or value["completion_index"] != 0:
        _add_once(reasons, "provenance_completion_cardinality_invalid")
    identities = ("prompt_sha256", "request_sha256", "completion_sha256")
    if any(not _is_sha256(value[name]) for name in identities):
        _add_once(reasons, "provenance_identity_invalid")
    if messages:
        prompt = [
            {"role": item.role, "content": item.content}
            for item in messages
            if item.role == "user"
        ]
        if value["prompt_sha256"] != _sha_identity(prompt):
            _add_once(reasons, "provenance_prompt_identity_mismatch")
        if value["completion_sha256"] != _sha_identity(messages[-1].content):
            _add_once(reasons, "provenance_completion_identity_mismatch")
    if value["request_sha256"] != _sha_identity(_request_identity(value)):
        _add_once(reasons, "provenance_request_identity_mismatch")
    if reasons:
        return None
    return ReplayProvenance(
        author_kind=author_kind,
        model_revision=value["model_revision"],
        tokenizer_revision=value["tokenizer_revision"],
        renderer=value["renderer"],
        temperature=value["temperature"],
        tools_enabled=value["tools_enabled"],
        max_completion_tokens=value["max_completion_tokens"],
        completion_count=value["completion_count"],
        completion_index=value["completion_index"],
        prompt_sha256=value["prompt_sha256"],
        request_sha256=value["request_sha256"],
        completion_sha256=value["completion_sha256"],
    )


def _content_checks(
    messages: tuple[ChatMessage, ...],
    task_family: str | None,
    references: Mapping[str, tuple[str, ...]],
    reasons: list[str],
    flags: list[str],
) -> None:
    all_text = "\n".join(message.content for message in messages)
    for name, values in references.items():
        compared = (messages[-1].content,) if name == "approved_response_overlap" else (
            *(message.content for message in messages),
            all_text,
        )
        if any(_reference_overlap(text, values) for text in compared):
            _add_once(reasons, name)
    if _PROTOCOL_RE.search(all_text):
        _add_once(reasons, "protocol_imitation")
    if _HIDDEN_REASONING_RE.search(all_text):
        _add_once(reasons, "hidden_reasoning")
    if _TOOL_TRANSCRIPT_RE.search(all_text):
        _add_once(reasons, "tool_transcript")
    if _FAST_FACT_RE.search(all_text):
        _add_once(reasons, "fast_changing_fact")
    if _BOILERPLATE_RE.search(messages[-1].content):
        _add_once(reasons, "boilerplate")
    if _REFUSAL_RE.search(messages[-1].content):
        if task_family == "refusal/uncertainty/missing-information":
            _add_once(flags, "intentional_refusal_review")
        else:
            _add_once(reasons, "refusal_outside_intentional_family")
    if _CODE_RE.search(all_text):
        _add_once(flags, "code_spot_check")
    if task_family == "math/data reasoning" or _ARITHMETIC_RE.search(all_text):
        _add_once(flags, "arithmetic_spot_check")


def _reference_sets(
    *,
    interaction_texts: Sequence[str],
    development_texts: Sequence[str],
    test_texts: Sequence[str],
    demo_texts: Sequence[str],
    approved_responses: Sequence[str],
    heldout_assets: Mapping[str, str],
    project_nonces: Sequence[str],
    project_vocabulary_phrases: Sequence[str],
) -> dict[str, tuple[str, ...]]:
    if not isinstance(heldout_assets, Mapping) or any(
        not _nonempty_text(name) or not isinstance(value, str)
        for name, value in heldout_assets.items()
    ):
        raise TypeError("heldout_assets must map non-empty asset names to strings")
    heldout = tuple(heldout_assets) + tuple(heldout_assets.values())
    return {
        "interaction_overlap": _normalised_values(interaction_texts, "interaction_texts"),
        "development_overlap": _normalised_values(development_texts, "development_texts"),
        "test_overlap": _normalised_values(test_texts, "test_texts"),
        "demo_overlap": _normalised_values(demo_texts, "demo_texts"),
        "approved_response_overlap": _normalised_values(approved_responses, "approved_responses"),
        "heldout_asset_overlap": _normalised_values(heldout, "heldout_assets"),
        "project_nonce_overlap": _normalised_values(project_nonces, "project_nonces"),
        "project_vocabulary_overlap": _normalised_values(
            project_vocabulary_phrases, "project_vocabulary_phrases"
        ),
    }


def _reject_duplicate_completion_ids(outcomes: list[ReplayFilterOutcome]) -> None:
    groups: dict[str, list[int]] = defaultdict(list)
    for index, outcome in enumerate(outcomes):
        if outcome.accepted and outcome.candidate is not None:
            groups[outcome.candidate.completion_id].append(index)
    for indexes in groups.values():
        if len(indexes) > 1:
            for index in indexes:
                _add_rejection(outcomes, index, "duplicate_completion_id")


def _limit_dataset_sources(outcomes: list[ReplayFilterOutcome]) -> None:
    source_pairs = sorted(
        {
            (outcome.candidate.dataset_source_id, outcome.candidate.dataset_source_revision)
            for outcome in outcomes
            if outcome.accepted and outcome.candidate is not None
        }
    )
    allowed = frozenset(source_pairs[:MAX_DATASET_SOURCES])
    for index, outcome in enumerate(outcomes):
        if outcome.accepted and outcome.candidate is not None:
            source = (
                outcome.candidate.dataset_source_id,
                outcome.candidate.dataset_source_revision,
            )
            if source not in allowed:
                _add_rejection(outcomes, index, "dataset_source_limit_exceeded")


def _reject_exact_duplicates(outcomes: list[ReplayFilterOutcome]) -> None:
    grouped: dict[str, list[int]] = defaultdict(list)
    for index, outcome in enumerate(outcomes):
        if outcome.accepted and outcome.candidate is not None:
            grouped[_exact_fingerprint(outcome.candidate)].append(index)
    for indexes in grouped.values():
        leader = min(indexes, key=lambda index: outcomes[index].candidate_id or "")
        leader_id = outcomes[leader].candidate_id
        for index in indexes:
            if index != leader:
                _add_rejection(outcomes, index, f"exact_duplicate:{leader_id}")


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

    fingerprints: dict[int, tuple[set[str], set[tuple[str, ...]]]] = {}
    for index in indexes:
        candidate = outcomes[index].candidate
        if candidate is None:
            raise AssertionError("accepted candidate disappeared during near-duplicate scanning")
        text = " ".join(message.content for message in candidate.messages)
        fingerprints[index] = (_token_set(text), _shingles(text))
    # ponytail: O(n²) scan is bounded by ~1,250 rows; use MinHash/LSH if the replay pool grows.
    for left, right in combinations(indexes, 2):
        if _near_match(*fingerprints[left], *fingerprints[right]):
            union(left, right)
    components: dict[int, list[int]] = defaultdict(list)
    for index in indexes:
        components[root(index)].append(index)
    for component in components.values():
        leader = min(component, key=lambda index: outcomes[index].candidate_id or "")
        leader_id = outcomes[leader].candidate_id
        for index in component:
            if index != leader:
                _add_rejection(outcomes, index, f"near_duplicate:{leader_id}")


def _reject_duplicate_prompts(outcomes: list[ReplayFilterOutcome]) -> None:
    _reject_duplicate_prompt_field(outcomes, "prompt_id")
    _reject_duplicate_prompt_field(outcomes, "prompt_fingerprint")


def _reject_duplicate_prompt_field(outcomes: list[ReplayFilterOutcome], field: str) -> None:
    grouped: dict[str, list[int]] = defaultdict(list)
    for index, outcome in enumerate(outcomes):
        if outcome.accepted and outcome.candidate is not None:
            grouped[str(getattr(outcome.candidate, field))].append(index)
    for indexes in grouped.values():
        leader = min(indexes, key=lambda index: outcomes[index].candidate_id or "")
        leader_id = outcomes[leader].candidate_id
        for index in indexes:
            if index != leader:
                _add_rejection(outcomes, index, f"duplicate_{field}:{leader_id}")


def _select_candidates(
    candidates: tuple[ReplayCandidate, ...], selection_seed: str
) -> tuple[ReplayCandidate, ...]:
    mismatches = tuple(
        candidate.completion_id
        for candidate in candidates
        if candidate.selection_seed != selection_seed
    )
    if mismatches:
        raise ReplaySelectionDeficitError(
            ReplayDeficitReport({}, {}, 0, 0, tuple(sorted(mismatches)))
        )
    deficit = _obvious_deficits(candidates)
    if deficit.task_family_deficits or deficit.length_band_deficits or (
        deficit.multi_turn_deficit or deficit.single_turn_deficit
    ):
        raise ReplaySelectionDeficitError(deficit)

    grouped: dict[tuple[str, str, str], list[ReplayCandidate]] = defaultdict(list)
    for candidate in candidates:
        grouped[
            (
                candidate.task_family,
                candidate.length_band,
                "multi" if candidate.is_multi_turn else "single",
            )
        ].append(candidate)
    for key in grouped:
        grouped[key].sort(key=lambda item: _candidate_rank(selection_seed, item.completion_id))

    counts = None
    for multi_by_band in _multi_band_allocations(grouped, selection_seed):
        counts = _solve_allocation(grouped, multi_by_band)
        if counts is not None:
            break
    if counts is None:
        raise ReplaySelectionDeficitError(
            ReplayDeficitReport({}, {}, 0, 0, joint_constraint_failure=True)
        )
    selected_by_key = {key: list(grouped[key][: count]) for key, count in counts.items()}
    selected = _enforce_supervised_token_total(selected_by_key, grouped, selection_seed)
    if len(selected) != TARGET_EXAMPLES:
        raise AssertionError("allocation solver did not select exactly 1,000 rows")
    return tuple(
        sorted(selected, key=lambda item: _candidate_rank(selection_seed, item.completion_id))
    )


def _obvious_deficits(candidates: Sequence[ReplayCandidate]) -> ReplayDeficitReport:
    family_counts = Counter(candidate.task_family for candidate in candidates)
    band_counts = Counter(candidate.length_band for candidate in candidates)
    multi_count = sum(candidate.is_multi_turn for candidate in candidates)
    return ReplayDeficitReport(
        {
            family: quota - family_counts[family]
            for family, quota in COMPOSITION_QUOTAS.items()
            if family_counts[family] < quota
        },
        {
            band: target - band_counts[band]
            for band, (_minimum, _maximum, target) in LENGTH_BANDS.items()
            if band_counts[band] < target
        },
        max(0, MULTI_TURN_TARGET - multi_count),
        max(0, (TARGET_EXAMPLES - MULTI_TURN_TARGET) - (len(candidates) - multi_count)),
    )


def _enforce_supervised_token_total(
    selected_by_key: dict[tuple[str, str, str], list[ReplayCandidate]],
    grouped: Mapping[tuple[str, str, str], Sequence[ReplayCandidate]],
    selection_seed: str,
) -> list[ReplayCandidate]:
    selected = [candidate for values in selected_by_key.values() for candidate in values]
    total = sum(candidate.assistant_token_count for candidate in selected)
    if total < SUPERVISED_TOKEN_MIN:
        total = _swap_token_total(
            selected_by_key, grouped, total, SUPERVISED_TOKEN_MIN, selection_seed, increase=True
        )
    elif total > SUPERVISED_TOKEN_MAX:
        total = _swap_token_total(
            selected_by_key, grouped, total, SUPERVISED_TOKEN_MAX, selection_seed, increase=False
        )
    selected = [candidate for values in selected_by_key.values() for candidate in values]
    if not SUPERVISED_TOKEN_MIN <= total <= SUPERVISED_TOKEN_MAX:
        raise ReplaySelectionDeficitError(
            ReplayDeficitReport({}, {}, 0, 0, supervised_token_total=total)
        )
    return selected


def _swap_token_total(
    selected_by_key: dict[tuple[str, str, str], list[ReplayCandidate]],
    grouped: Mapping[tuple[str, str, str], Sequence[ReplayCandidate]],
    total: int,
    limit: int,
    selection_seed: str,
    *,
    increase: bool,
) -> int:
    swaps: list[tuple[int, tuple[str, str, str], ReplayCandidate, ReplayCandidate]] = []
    for key, current in selected_by_key.items():
        current_ids = {candidate.completion_id for candidate in current}
        extras = [
            candidate for candidate in grouped[key] if candidate.completion_id not in current_ids
        ]
        if increase:
            sources = sorted(
                current,
                key=lambda item: (
                    item.assistant_token_count,
                    _candidate_rank(selection_seed, item.completion_id),
                ),
            )
            targets = sorted(
                extras,
                key=lambda item: (
                    -item.assistant_token_count,
                    _candidate_rank(selection_seed, item.completion_id),
                ),
            )
        else:
            sources = sorted(
                current,
                key=lambda item: (
                    -item.assistant_token_count,
                    _candidate_rank(selection_seed, item.completion_id),
                ),
            )
            targets = sorted(
                extras,
                key=lambda item: (
                    item.assistant_token_count,
                    _candidate_rank(selection_seed, item.completion_id),
                ),
            )
        for source, target in zip(sources, targets, strict=False):
            delta = target.assistant_token_count - source.assistant_token_count
            if (increase and delta > 0) or (not increase and delta < 0):
                swaps.append((abs(delta), key, source, target))
    swaps.sort(reverse=True, key=lambda value: value[0])
    for delta, key, source, target in swaps:
        if (increase and total >= limit) or (not increase and total <= limit):
            break
        current = selected_by_key[key]
        index = next(
            (
                index
                for index, candidate in enumerate(current)
                if candidate.completion_id == source.completion_id
            ),
            None,
        )
        if index is None:
            continue
        current[index] = target
        total += target.assistant_token_count - source.assistant_token_count
    return total


def _multi_band_allocations(
    grouped: Mapping[tuple[str, str, str], Sequence[ReplayCandidate]], selection_seed: str
) -> tuple[tuple[int, int, int], ...]:
    bounds: list[tuple[int, int]] = []
    preferred: list[int] = []
    for band in _BANDS:
        target = LENGTH_BANDS[band][2]
        multi_available = sum(
            len(grouped.get((family, band, "multi"), ())) for family in COMPOSITION_QUOTAS
        )
        single_available = sum(
            len(grouped.get((family, band, "single"), ())) for family in COMPOSITION_QUOTAS
        )
        bounds.append((max(0, target - single_available), min(target, multi_available)))
        preferred.append(target * MULTI_TURN_TARGET // TARGET_EXAMPLES)
    allocations: list[tuple[int, int, int]] = []
    for short in range(bounds[0][0], bounds[0][1] + 1):
        for medium in range(bounds[1][0], bounds[1][1] + 1):
            long = MULTI_TURN_TARGET - short - medium
            if bounds[2][0] <= long <= bounds[2][1]:
                allocations.append((short, medium, long))
    return tuple(
        sorted(
            allocations,
            key=lambda allocation: (
                sum(abs(value - ideal) for value, ideal in zip(allocation, preferred, strict=True)),
                sha256(
                    f"phase2-replay-multi-v1|{selection_seed}|{allocation}".encode()
                ).hexdigest(),
            ),
        )
    )


def _solve_allocation(
    grouped: Mapping[tuple[str, str, str], Sequence[ReplayCandidate]],
    multi_by_band: tuple[int, int, int],
) -> dict[tuple[str, str, str], int] | None:
    families = tuple(COMPOSITION_QUOTAS)
    source, sink = 0, 1
    family_nodes = {family: index + 2 for index, family in enumerate(families)}
    band_turns = tuple((band, turn) for band in _BANDS for turn in _TURN_KINDS)
    band_type_nodes = {
        (band, turn): index + 2 + len(families)
        for index, (band, turn) in enumerate(band_turns)
    }
    band_nodes = {
        band: index + 2 + len(families) + len(band_type_nodes)
        for index, band in enumerate(_BANDS)
    }
    graph = _Dinic(2 + len(family_nodes) + len(band_type_nodes) + len(band_nodes))
    for family, quota in COMPOSITION_QUOTAS.items():
        graph.add_edge(source, family_nodes[family], quota)
    chosen_edges: dict[tuple[str, str, str], tuple[int, int, int]] = {}
    for family in families:
        for band in _BANDS:
            for turn in _TURN_KINDS:
                key = (family, band, turn)
                capacity = len(grouped.get(key, ()))
                edge_index = graph.add_edge(
                    family_nodes[family], band_type_nodes[(band, turn)], capacity
                )
                chosen_edges[key] = (family_nodes[family], edge_index, capacity)
    for index, band in enumerate(_BANDS):
        multi = multi_by_band[index]
        target = LENGTH_BANDS[band][2]
        graph.add_edge(band_type_nodes[(band, "multi")], band_nodes[band], multi)
        graph.add_edge(band_type_nodes[(band, "single")], band_nodes[band], target - multi)
        graph.add_edge(band_nodes[band], sink, target)
    if graph.max_flow(source, sink) != TARGET_EXAMPLES:
        return None
    return {
        key: capacity - graph.residual(node, edge_index)
        for key, (node, edge_index, capacity) in chosen_edges.items()
    }


def _stratified_review_sample(
    selected: tuple[ReplayCandidate, ...], selection_seed: str
) -> tuple[ReplayCandidate, ...]:
    strata: dict[tuple[str, str, bool], list[ReplayCandidate]] = defaultdict(list)
    for candidate in selected:
        strata[(candidate.task_family, candidate.length_band, candidate.is_multi_turn)].append(
            candidate
        )
    ordered_strata = tuple(sorted(strata))
    for key in ordered_strata:
        strata[key].sort(key=lambda item: _review_rank(selection_seed, item.completion_id))
    sample: list[ReplayCandidate] = []
    offsets = {key: 0 for key in ordered_strata}
    while len(sample) < 100:
        advanced = False
        for key in ordered_strata:
            offset = offsets[key]
            if offset < len(strata[key]):
                sample.append(strata[key][offset])
                offsets[key] += 1
                advanced = True
                if len(sample) == 100:
                    break
        if not advanced:
            raise AssertionError("selected corpus has fewer than 100 rows")
    return tuple(sample)


@dataclass(slots=True)
class _Edge:
    target: int
    reverse: int
    capacity: int


class _Dinic:
    def __init__(self, node_count: int) -> None:
        self.graph: list[list[_Edge]] = [[] for _ in range(node_count)]
        self.level: list[int] = []
        self.iterator: list[int] = []

    def add_edge(self, source: int, target: int, capacity: int) -> int:
        edge_index = len(self.graph[source])
        self.graph[source].append(_Edge(target, len(self.graph[target]), capacity))
        self.graph[target].append(_Edge(source, edge_index, 0))
        return edge_index

    def residual(self, source: int, edge_index: int) -> int:
        return self.graph[source][edge_index].capacity

    def max_flow(self, source: int, sink: int) -> int:
        total = 0
        while self._build_levels(source, sink):
            self.iterator = [0] * len(self.graph)
            while flow := self._send(source, sink, TARGET_EXAMPLES):
                total += flow
        return total

    def _build_levels(self, source: int, sink: int) -> bool:
        self.level = [-1] * len(self.graph)
        self.level[source] = 0
        queue = deque([source])
        while queue:
            node = queue.popleft()
            for edge in self.graph[node]:
                if edge.capacity and self.level[edge.target] < 0:
                    self.level[edge.target] = self.level[node] + 1
                    queue.append(edge.target)
        return self.level[sink] >= 0

    def _send(self, node: int, sink: int, flow: int) -> int:
        if node == sink:
            return flow
        while self.iterator[node] < len(self.graph[node]):
            edge_index = self.iterator[node]
            edge = self.graph[node][edge_index]
            if edge.capacity and self.level[node] < self.level[edge.target]:
                sent = self._send(edge.target, sink, min(flow, edge.capacity))
                if sent:
                    edge.capacity -= sent
                    self.graph[edge.target][edge.reverse].capacity += sent
                    return sent
            self.iterator[node] += 1
        return 0


def _exact_fingerprint(candidate: ReplayCandidate) -> str:
    value = [{"role": message.role, "content": message.content} for message in candidate.messages]
    return _sha_identity(value)


def _prompt_fingerprint(messages: tuple[ChatMessage, ...]) -> str:
    return _normalise_text(
        "\n".join(message.content for message in messages if message.role == "user")
    )


def _reference_overlap(text: str, references: Sequence[str]) -> bool:
    normalised = _normalise_text(text)
    if not normalised:
        return False
    tokens = _token_set(normalised)
    shingles = _shingles(normalised)
    for reference in references:
        if len(reference) >= 8 and (reference in normalised or normalised in reference):
            return True
        if _near_match(tokens, shingles, _token_set(reference), _shingles(reference)):
            return True
    return False


def _near_match(
    left_tokens: set[str],
    left_shingles: set[tuple[str, ...]],
    right_tokens: set[str],
    right_shingles: set[tuple[str, ...]],
) -> bool:
    return _jaccard(left_tokens, right_tokens) >= NEAR_DUPLICATE_JACCARD or (
        bool(left_shingles)
        and bool(right_shingles)
        and _jaccard(left_shingles, right_shingles) >= NEAR_DUPLICATE_JACCARD
    )


def _token_set(text: str) -> set[str]:
    return set(re.findall(r"\w+", text.casefold()))


def _shingles(text: str) -> set[tuple[str, ...]]:
    tokens = re.findall(r"\w+", text.casefold())
    return {tuple(tokens[index : index + 3]) for index in range(len(tokens) - 2)}


def _jaccard(left: set[object], right: set[object]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _normalised_values(values: Sequence[str], field: str) -> tuple[str, ...]:
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
        raise TypeError(f"{field} must be a sequence of strings")
    if any(not isinstance(value, str) for value in values):
        raise TypeError(f"{field} must contain only strings")
    return tuple(sorted({_normalise_text(value) for value in values if _normalise_text(value)}))


def _normalise_text(value: str) -> str:
    return " ".join(value.casefold().split())


def _sha_identity(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()
    return f"sha256:{sha256(encoded).hexdigest()}"


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


def _is_sha256(value: object) -> bool:
    return isinstance(value, str) and _SHA256_RE.fullmatch(value) is not None


def _candidate_rank(selection_seed: str, completion_id: str) -> str:
    return sha256(f"phase2-replay-v2|{selection_seed}|{completion_id}".encode()).hexdigest()


def _review_rank(selection_seed: str, completion_id: str) -> str:
    return sha256(f"phase2-replay-review-v2|{selection_seed}|{completion_id}".encode()).hexdigest()


def _add_rejection(outcomes: list[ReplayFilterOutcome], index: int, reason: str) -> None:
    outcome = outcomes[index]
    if reason not in outcome.rejection_reasons:
        outcomes[index] = replace(outcome, rejection_reasons=outcome.rejection_reasons + (reason,))


def _add_once(values: list[str], value: str) -> None:
    if value not in values:
        values.append(value)


def _nonempty_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())
