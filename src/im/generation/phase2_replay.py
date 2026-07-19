"""Deterministic offline replay filtering and raw-input review-round planning."""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from hashlib import sha256
from itertools import combinations

from im.generation.phase2_replay_allocation import (
    AllocationFailure,
    choose_maximum_token_selection,
)

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
_DATASET_ROLES = frozenset({"primary", "secondary"})
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
    r'"type"\s*:\s*"(?:' + "|".join(sorted(_ACTION_TYPES)) + r')"',
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
    def __init__(self, report: ReplayDeficitReport) -> None:
        self.report = report
        super().__init__(f"replay selection is infeasible: {report.summary()}")


class ReplayReviewError(ValueError):
    pass


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
        return len(self.messages) > 2

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
        values = (
            (self.task_family_deficits, f"task families={self.task_family_deficits}"),
            (self.length_band_deficits, f"length bands={self.length_band_deficits}"),
            (self.multi_turn_deficit, f"multi-turn={self.multi_turn_deficit}"),
            (self.single_turn_deficit, f"single-turn={self.single_turn_deficit}"),
            (
                self.selection_seed_mismatches,
                f"selection seed mismatch={self.selection_seed_mismatches}",
            ),
            (
                self.supervised_token_total is not None,
                f"supervised tokens={self.supervised_token_total}",
            ),
            (self.joint_constraint_failure, "joint family/length/turn allocation"),
        )
        return (
            "; ".join(text for present, text in values if present) or "unknown allocation failure"
        )


@dataclass(frozen=True, slots=True)
class ReplayPlan:
    filter_report: ReplayFilterReport
    reference_manifest_sha256: str
    review_rounds_sha256: str
    selection_seed: str
    provisional_selected: tuple[ReplayCandidate, ...]
    human_review_sample: tuple[ReplayCandidate, ...]
    flagged_selected: tuple[ReplayCandidate, ...]
    human_review_queue: tuple[ReplayCandidate, ...]


@dataclass(frozen=True, slots=True)
class ReplaySelection:
    selected: tuple[ReplayCandidate, ...]


def filter_replay_candidates(
    candidates: Sequence[Mapping[str, object]], reference_manifest: Mapping[str, object]
) -> ReplayFilterReport:
    if not isinstance(candidates, Sequence) or isinstance(candidates, (str, bytes)):
        raise TypeError("candidates must be a sequence of raw candidate mappings")
    manifest = _load_reference_manifest(reference_manifest)
    outcomes = [_initial_outcome(raw, manifest) for raw in candidates]
    _reject_duplicate_completion_ids(outcomes)
    _enforce_dataset_sources(outcomes)
    _reject_exact_duplicates(outcomes)
    _reject_near_duplicates(outcomes)
    _reject_duplicate_prompts(outcomes)
    return ReplayFilterReport(tuple(outcomes))


def plan_replay_review_round(
    candidates: Sequence[Mapping[str, object]],
    reference_manifest: Mapping[str, object],
    *,
    selection_seed: str,
    review_rounds: Sequence[Mapping[str, bool]],
) -> ReplayPlan:
    _validate_raw_inputs(candidates, reference_manifest, selection_seed)
    rounds = _load_review_rounds(review_rounds)
    return _replay_review_history(candidates, reference_manifest, selection_seed, rounds)


def finalize_replay_selection(
    candidates: Sequence[Mapping[str, object]],
    reference_manifest: Mapping[str, object],
    *,
    selection_seed: str,
    review_rounds: Sequence[Mapping[str, bool]],
) -> ReplaySelection:
    _validate_raw_inputs(candidates, reference_manifest, selection_seed)
    rounds = _load_review_rounds(review_rounds)
    if not rounds:
        raise ReplayReviewError("a complete current review round is required before finalization")
    plan = _replay_review_history(candidates, reference_manifest, selection_seed, rounds[:-1])
    current_round = rounds[-1]
    _validate_review_round(plan, current_round)
    if any(not approved for approved in current_round.values()):
        raise ReplayReviewError(
            "a rejected row requires a newly derived and reviewed replacement round"
        )
    return ReplaySelection(plan.provisional_selected)


def _validate_raw_inputs(
    candidates: Sequence[Mapping[str, object]],
    reference_manifest: Mapping[str, object],
    selection_seed: str,
) -> None:
    if not isinstance(candidates, Sequence) or isinstance(candidates, (str, bytes)):
        raise TypeError("candidates must be raw candidate mappings")
    if not _nonempty_text(selection_seed):
        raise ValueError("selection_seed must be non-empty")
    _load_reference_manifest(reference_manifest)


def _replay_review_history(
    candidates: Sequence[Mapping[str, object]],
    reference_manifest: Mapping[str, object],
    selection_seed: str,
    review_rounds: tuple[dict[str, bool], ...],
) -> ReplayPlan:
    rejected_by_review: set[str] = set()
    for round_index, decisions in enumerate(review_rounds):
        plan = _build_review_round(
            candidates,
            reference_manifest,
            selection_seed,
            rejected_by_review,
            review_rounds[:round_index],
        )
        _validate_review_round(plan, decisions, historical=True)
        rejected_by_review.update(
            completion_id for completion_id, approved in decisions.items() if not approved
        )
    return _build_review_round(
        candidates,
        reference_manifest,
        selection_seed,
        rejected_by_review,
        review_rounds,
    )


def _build_review_round(
    candidates: Sequence[Mapping[str, object]],
    reference_manifest: Mapping[str, object],
    selection_seed: str,
    rejected_by_review: set[str],
    review_rounds: Sequence[Mapping[str, bool]],
) -> ReplayPlan:
    manifest = _load_reference_manifest(reference_manifest)
    report = filter_replay_candidates(candidates, reference_manifest)
    accepted = tuple(
        outcome.candidate
        for outcome in report.accepted
        if outcome.candidate is not None
        and outcome.candidate.completion_id not in rejected_by_review
    )
    selected = _select_candidates(accepted, selection_seed)
    review_sample = _stratified_review_sample(selected, selection_seed)
    flagged = tuple(candidate for candidate in selected if candidate.flags)
    sampled_ids = {candidate.completion_id for candidate in review_sample}
    queue = review_sample + tuple(
        candidate for candidate in flagged if candidate.completion_id not in sampled_ids
    )
    return ReplayPlan(
        report,
        manifest.sha256,
        _sha_identity([dict(decisions) for decisions in review_rounds]),
        selection_seed,
        selected,
        review_sample,
        flagged,
        queue,
    )


def _validate_review_round(
    plan: ReplayPlan, decisions: Mapping[str, bool], *, historical: bool = False
) -> None:
    queue_ids = {candidate.completion_id for candidate in plan.human_review_queue}
    if set(decisions) != queue_ids:
        raise ReplayReviewError("review decisions must exactly cover the derived current queue")
    if historical and all(decisions.values()):
        raise ReplayReviewError("an all-true review round is terminal and cannot be historical")


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
    token_count, tokenizer_revision = _parse_token_count(raw.get("assistant_token_count"), reasons)
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
    if len(value) > 6:
        _add_once(reasons, "chat_not_short")
    messages: list[ChatMessage] = []
    roles: list[str] = []
    for item in value:
        if not isinstance(item, Mapping) or set(item) != {"role", "content"}:
            _add_once(reasons, "chat_message_shape_invalid")
            continue
        role, content = item["role"], item["content"]
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
    if (
        roles[0] != "user"
        or roles[-1] != "assistant"
        or any(
            role != ("user" if index % 2 == 0 else "assistant") for index, role in enumerate(roles)
        )
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
    count, tokenizer_revision = value["count"], value["tokenizer_revision"]
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
    if value["author_kind"] != "backbone_self_replay":
        _add_once(reasons, "provenance_author_kind_invalid")
    checks = (
        ("model_revision", BACKBONE_REVISION, "provenance_model_revision_mismatch"),
        ("tokenizer_revision", BACKBONE_REVISION, "provenance_tokenizer_revision_mismatch"),
        ("renderer", RENDERER, "provenance_renderer_mismatch"),
        ("max_completion_tokens", MAX_COMPLETION_TOKENS, "provenance_max_completion_mismatch"),
    )
    for field, expected, reason in checks:
        if value[field] != expected:
            _add_once(reasons, reason)
    if value["temperature"] != TEMPERATURE or isinstance(value["temperature"], bool):
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
        if value["prompt_sha256"] != _sha_identity(_chat_messages(messages[:-1])):
            _add_once(reasons, "provenance_prompt_identity_mismatch")
        if value["completion_sha256"] != _sha_identity(messages[-1].content):
            _add_once(reasons, "provenance_completion_identity_mismatch")
    if value["request_sha256"] != _sha_identity(_request_identity(value)):
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
    all_text = "\n".join(message.content for message in messages)
    for name, values in manifest.references:
        compared = (
            (messages[-1].content,)
            if name == "approved_response_overlap"
            else (
                *(message.content for message in messages),
                all_text,
            )
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


def _load_reference_manifest(value: Mapping[str, object]) -> ReplayReferenceManifest:
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
    return ReplayReferenceManifest(tuple(references), _sha_identity(canonical))


def _load_review_rounds(value: Sequence[Mapping[str, bool]]) -> tuple[dict[str, bool], ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise TypeError("review_rounds must be an ordered sequence of complete review mappings")
    rounds: list[dict[str, bool]] = []
    for decisions in value:
        if not isinstance(decisions, Mapping) or any(
            not _nonempty_text(key) or not isinstance(approved, bool)
            for key, approved in decisions.items()
        ):
            raise TypeError("each review round must map non-empty completion IDs to bools")
        rounds.append(dict(sorted(decisions.items())))
    return tuple(rounds)


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
            grouped[_sha_identity(_chat_messages(outcome.candidate.messages))].append(index)
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
            " ".join(message.content for message in outcomes[index].candidate.messages)
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
    if (
        deficit.task_family_deficits
        or deficit.length_band_deficits
        or (deficit.multi_turn_deficit or deficit.single_turn_deficit)
    ):
        raise ReplaySelectionDeficitError(deficit)
    result = choose_maximum_token_selection(
        candidates,
        family_quotas=COMPOSITION_QUOTAS,
        length_bands=LENGTH_BANDS,
        multi_turn_target=MULTI_TURN_TARGET,
        target_examples=TARGET_EXAMPLES,
        supervised_token_minimum=SUPERVISED_TOKEN_MIN,
        classify=lambda candidate: (
            candidate.task_family,
            candidate.length_band,
            "multi" if candidate.is_multi_turn else "single",
        ),
        token_count=lambda candidate: candidate.assistant_token_count,
        rank=lambda candidate: _candidate_rank(selection_seed, candidate.completion_id),
    )
    if isinstance(result, AllocationFailure):
        raise ReplaySelectionDeficitError(
            ReplayDeficitReport(
                {},
                {},
                0,
                0,
                supervised_token_total=result.supervised_token_total,
                joint_constraint_failure=result.joint_constraint_failure,
            )
        )
    if result.supervised_token_total > SUPERVISED_TOKEN_MAX:
        raise AssertionError("length-band maxima should cap supervised tokens at 130,000")
    return result.selected


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


def _stratified_review_sample(
    selected: tuple[ReplayCandidate, ...], selection_seed: str
) -> tuple[ReplayCandidate, ...]:
    strata: dict[tuple[str, str, bool], list[ReplayCandidate]] = defaultdict(list)
    for candidate in selected:
        strata[(candidate.task_family, candidate.length_band, candidate.is_multi_turn)].append(
            candidate
        )
    ordered = tuple(sorted(strata))
    for key in ordered:
        strata[key].sort(
            key=lambda candidate: _review_rank(selection_seed, candidate.completion_id)
        )
    sample: list[ReplayCandidate] = []
    offsets = {key: 0 for key in ordered}
    while len(sample) < 100:
        advanced = False
        for key in ordered:
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


def _chat_messages(messages: Sequence[ChatMessage]) -> list[dict[str, str]]:
    return [{"role": message.role, "content": message.content} for message in messages]


def _prompt_fingerprint(messages: tuple[ChatMessage, ...]) -> str:
    return _sha_identity(
        [
            {"role": message.role, "content": _normalise_text(message.content)}
            for message in messages[:-1]
        ]
    )


def _reference_overlap(text: str, references: Sequence[str]) -> bool:
    normalised = _normalise_text(text)
    if not normalised:
        return False
    fingerprint = _fingerprint(normalised)
    for reference in references:
        if len(reference) >= 8 and (reference in normalised or normalised in reference):
            return True
        if _near_match(*fingerprint, *_fingerprint(reference)):
            return True
    return False


def _fingerprint(text: str) -> tuple[set[str], set[tuple[str, ...]]]:
    tokens = re.findall(r"\w+", text.casefold())
    return set(tokens), {tuple(tokens[index : index + 3]) for index in range(len(tokens) - 2)}


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


def _sha_identity(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()
    return f"sha256:{sha256(encoded).hexdigest()}"


def _normalise_text(value: str) -> str:
    return " ".join(value.casefold().split())


def _jaccard(left: set[object], right: set[object]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _candidate_rank(selection_seed: str, completion_id: str) -> str:
    return sha256(f"phase2-replay-v3|{selection_seed}|{completion_id}".encode()).hexdigest()


def _review_rank(selection_seed: str, completion_id: str) -> str:
    return sha256(f"phase2-replay-review-v3|{selection_seed}|{completion_id}".encode()).hexdigest()


def _add_rejection(outcomes: list[ReplayFilterOutcome], index: int, reason: str) -> None:
    outcome = outcomes[index]
    if reason not in outcome.rejection_reasons:
        outcomes[index] = replace(outcome, rejection_reasons=outcome.rejection_reasons + (reason,))


def _add_once(values: list[str], value: str) -> None:
    if value not in values:
        values.append(value)


def _nonempty_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())
