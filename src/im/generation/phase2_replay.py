"""Deterministic offline replay filtering and quota selection for Phase 2 chat data."""

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
MULTI_TURN_TARGET = 200
TARGET_EXAMPLES = 1_000
BACKBONE_REVISION = "Qwen/Qwen3.6-35B-A3B"
RENDERER = "qwen3_5_disable_thinking"
TEMPERATURE = 0.2
MAX_COMPLETION_TOKENS = 512
NEAR_DUPLICATE_JACCARD = 0.8

_BANDS = tuple(LENGTH_BANDS)
_TURN_KINDS = ("single", "multi")
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


class ReplaySelectionDeficitError(ValueError):
    """The accepted replay slice cannot satisfy its closed quotas."""

    def __init__(self, report: ReplayDeficitReport) -> None:
        self.report = report
        super().__init__(f"replay selection is infeasible: {report.summary()}")


@dataclass(frozen=True, slots=True)
class ChatMessage:
    role: str
    content: str


@dataclass(frozen=True, slots=True)
class ReplayCandidate:
    """Validated native-chat replay row, retaining only selection-safe metadata."""

    candidate_id: str
    task_family: str
    messages: tuple[ChatMessage, ...]
    assistant_token_count: int
    prompt_source_id: str
    prompt_source_revision: str
    backbone_revision: str
    renderer: str
    temperature: float
    tools: tuple[object, ...]
    max_completion_tokens: int
    selection_seed: str
    flags: tuple[str, ...] = ()

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
        raise ValueError("validated candidate has no assistant length band")


@dataclass(frozen=True, slots=True)
class ReplayFilterOutcome:
    raw: Mapping[str, object]
    candidate: ReplayCandidate | None
    rejection_reasons: tuple[str, ...]
    flags: tuple[str, ...]

    @property
    def candidate_id(self) -> str | None:
        return None if self.candidate is None else self.candidate.candidate_id

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
        if self.joint_constraint_failure:
            parts.append("joint family/length/turn allocation")
        return "; ".join(parts) or "unknown allocation failure"


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
) -> ReplayFilterReport:
    """Filter already-sampled rows without rendering prompts or calling a model."""
    if not isinstance(candidates, Sequence) or isinstance(candidates, (str, bytes)):
        raise TypeError("candidates must be a sequence of candidate mappings")
    overlap_sets = {
        "interaction_overlap": _normalised_set(interaction_texts, "interaction_texts"),
        "development_overlap": _normalised_set(development_texts, "development_texts"),
        "test_overlap": _normalised_set(test_texts, "test_texts"),
        "demo_overlap": _normalised_set(demo_texts, "demo_texts"),
        "approved_response_overlap": _normalised_set(approved_responses, "approved_responses"),
    }
    outcomes = [_initial_outcome(raw, overlap_sets) for raw in candidates]
    _reject_duplicate_candidate_ids(outcomes)
    _reject_exact_duplicates(outcomes)
    _reject_near_duplicates(outcomes)
    return ReplayFilterReport(tuple(outcomes))


def select_replay_candidates(
    report: ReplayFilterReport, *, selection_seed: str
) -> ReplaySelection:
    """Select exactly 1,000 accepted rows or fail closed with actionable deficits."""
    if not isinstance(report, ReplayFilterReport):
        raise TypeError("report must be a ReplayFilterReport")
    if not _nonempty_text(selection_seed):
        raise ValueError("selection_seed must be non-empty")
    accepted = tuple(outcome.candidate for outcome in report.accepted)
    candidates = tuple(candidate for candidate in accepted if candidate is not None)
    mismatches = tuple(
        candidate.candidate_id
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
        grouped[key].sort(
            key=lambda candidate: _candidate_rank(selection_seed, candidate.candidate_id)
        )

    counts = None
    for multi_by_band in _multi_band_allocations(grouped, selection_seed):
        counts = _solve_allocation(grouped, multi_by_band)
        if counts is not None:
            break
    if counts is None:
        raise ReplaySelectionDeficitError(
            ReplayDeficitReport({}, {}, 0, 0, joint_constraint_failure=True)
        )

    selected: list[ReplayCandidate] = []
    for key in sorted(counts):
        selected.extend(grouped[key][: counts[key]])
    selected.sort(key=lambda candidate: _candidate_rank(selection_seed, candidate.candidate_id))
    if len(selected) != TARGET_EXAMPLES:
        raise AssertionError("allocation solver did not select exactly 1,000 rows")

    review_sample = _stratified_review_sample(tuple(selected), selection_seed)
    flagged = tuple(candidate for candidate in selected if candidate.flags)
    reviewed_ids = {candidate.candidate_id for candidate in review_sample}
    review_queue = review_sample + tuple(
        candidate for candidate in flagged if candidate.candidate_id not in reviewed_ids
    )
    return ReplaySelection(tuple(selected), review_sample, flagged, review_queue)


def _initial_outcome(
    raw: Mapping[str, object], overlap_sets: Mapping[str, set[str]]
) -> ReplayFilterOutcome:
    if not isinstance(raw, Mapping):
        return ReplayFilterOutcome({}, None, ("candidate_must_be_mapping",), ())
    reasons: list[str] = []
    flags: list[str] = []
    candidate_id = _required_text(raw, "candidate_id", reasons)
    task_family = _required_text(raw, "task_family", reasons)
    if task_family is not None and task_family not in COMPOSITION_QUOTAS:
        _add_once(reasons, "task_family_not_in_closed_composition")
    messages = _parse_messages(raw.get("messages"), reasons)
    token_count = _parse_token_count(raw, reasons)
    source_id = _required_text(raw, "prompt_source_id", reasons)
    source_revision = _required_text(raw, "prompt_source_revision", reasons)
    seed = _required_text(raw, "selection_seed", reasons)
    _validate_frozen_metadata(raw, reasons)
    _reject_teacher_evidence(raw, reasons)

    if messages:
        _content_checks(messages, task_family, overlap_sets, reasons, flags)
    required_values = (
        candidate_id,
        task_family,
        messages,
        token_count,
        source_id,
        source_revision,
        seed,
    )
    if reasons or None in required_values:
        return ReplayFilterOutcome(raw, None, tuple(reasons), tuple(flags))
    candidate = ReplayCandidate(
        candidate_id=candidate_id,
        task_family=task_family,
        messages=messages,
        assistant_token_count=token_count,
        prompt_source_id=source_id,
        prompt_source_revision=source_revision,
        backbone_revision=BACKBONE_REVISION,
        renderer=RENDERER,
        temperature=TEMPERATURE,
        tools=tuple(raw["tools"]),  # validated empty; preserve the frozen no-tools identity.
        max_completion_tokens=MAX_COMPLETION_TOKENS,
        selection_seed=seed,
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


def _parse_token_count(raw: Mapping[str, object], reasons: list[str]) -> int | None:
    if "assistant_token_count" not in raw:
        _add_once(reasons, "assistant_token_count_missing")
        return None
    value = raw["assistant_token_count"]
    if isinstance(value, bool) or not isinstance(value, int):
        _add_once(reasons, "assistant_token_count_not_measured")
        return None
    if not LENGTH_BANDS["short"][0] <= value <= LENGTH_BANDS["long"][1]:
        _add_once(reasons, "assistant_token_count_out_of_band")
        return None
    return value


def _validate_frozen_metadata(raw: Mapping[str, object], reasons: list[str]) -> None:
    if raw.get("backbone_revision") != BACKBONE_REVISION:
        _add_once(reasons, "backbone_revision_mismatch")
    if raw.get("renderer") != RENDERER:
        _add_once(reasons, "renderer_mismatch")
    if raw.get("temperature") != TEMPERATURE or isinstance(raw.get("temperature"), bool):
        _add_once(reasons, "temperature_mismatch")
    tools = raw.get("tools")
    if not isinstance(tools, (list, tuple)) or tools:
        _add_once(reasons, "tools_must_be_disabled")
    if raw.get("max_completion_tokens") != MAX_COMPLETION_TOKENS:
        _add_once(reasons, "max_completion_tokens_mismatch")


def _reject_teacher_evidence(raw: Mapping[str, object], reasons: list[str]) -> None:
    for key, value in raw.items():
        name = str(key).casefold()
        if "teacher" in name:
            _add_once(reasons, "teacher_evidence_forbidden")
        if name in {"author", "answer_author", "label_author", "authorship"} and isinstance(
            value, str
        ) and "teacher" in value.casefold():
            _add_once(reasons, "teacher_authorship_forbidden")


def _content_checks(
    messages: tuple[ChatMessage, ...],
    task_family: str | None,
    overlap_sets: Mapping[str, set[str]],
    reasons: list[str],
    flags: list[str],
) -> None:
    all_text = "\n".join(message.content for message in messages)
    for name, texts in overlap_sets.items():
        compared = (messages[-1].content,) if name == "approved_response_overlap" else tuple(
            message.content for message in messages
        )
        if texts and any(_normalise_text(text) in texts for text in compared):
            _add_once(reasons, name)
    if _PROTOCOL_RE.search(all_text):
        _add_once(reasons, "protocol_imitation")
    if _HIDDEN_REASONING_RE.search(all_text):
        _add_once(reasons, "hidden_reasoning")
    if _TOOL_TRANSCRIPT_RE.search(all_text):
        _add_once(reasons, "tool_transcript")
    if _FAST_FACT_RE.search(all_text):
        _add_once(reasons, "fast_changing_fact")
    if _REFUSAL_RE.search(messages[-1].content):
        _add_once(flags, "refusal_or_uncertainty")
    if _BOILERPLATE_RE.search(messages[-1].content):
        _add_once(flags, "boilerplate")
    if _CODE_RE.search(all_text):
        _add_once(flags, "code_spot_check")
    if task_family == "math/data reasoning" or _ARITHMETIC_RE.search(all_text):
        _add_once(flags, "arithmetic_spot_check")


def _reject_duplicate_candidate_ids(outcomes: list[ReplayFilterOutcome]) -> None:
    indexes: dict[str, list[int]] = defaultdict(list)
    for index, outcome in enumerate(outcomes):
        if outcome.candidate_id is not None:
            indexes[outcome.candidate_id].append(index)
    for duplicate_indexes in indexes.values():
        if len(duplicate_indexes) > 1:
            for index in duplicate_indexes:
                _add_rejection(outcomes, index, "duplicate_candidate_id")


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

    token_sets: dict[int, set[str]] = {}
    for index in indexes:
        candidate = outcomes[index].candidate
        if candidate is None:
            raise AssertionError("accepted candidate disappeared during near-duplicate scanning")
        token_sets[index] = _near_duplicate_tokens(candidate)
    # ponytail: O(n²) scan is bounded by the ~1,250-row replay pool; use MinHash/LSH if it grows.
    for left, right in combinations(indexes, 2):
        if _jaccard(token_sets[left], token_sets[right]) >= NEAR_DUPLICATE_JACCARD:
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
        strata[key].sort(
            key=lambda candidate: _review_rank(selection_seed, candidate.candidate_id)
        )
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
    return sha256(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def _near_duplicate_tokens(candidate: ReplayCandidate) -> set[str]:
    text = " ".join(message.content.casefold() for message in candidate.messages)
    return set(re.findall(r"\w+", text))


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _normalised_set(values: Sequence[str], field: str) -> set[str]:
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
        raise TypeError(f"{field} must be a sequence of strings")
    if any(not isinstance(value, str) for value in values):
        raise TypeError(f"{field} must contain only strings")
    return {_normalise_text(value) for value in values if _normalise_text(value)}


def _normalise_text(value: str) -> str:
    return " ".join(value.casefold().split())


def _candidate_rank(selection_seed: str, candidate_id: str) -> str:
    return sha256(f"phase2-replay-v1|{selection_seed}|{candidate_id}".encode()).hexdigest()


def _review_rank(selection_seed: str, candidate_id: str) -> str:
    return sha256(f"phase2-replay-review-v1|{selection_seed}|{candidate_id}".encode()).hexdigest()


def _add_rejection(outcomes: list[ReplayFilterOutcome], index: int, reason: str) -> None:
    outcome = outcomes[index]
    if reason not in outcome.rejection_reasons:
        outcomes[index] = replace(
            outcome, rejection_reasons=outcome.rejection_reasons + (reason,)
        )


def _add_once(values: list[str], value: str) -> None:
    if value not in values:
        values.append(value)


def _nonempty_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())
