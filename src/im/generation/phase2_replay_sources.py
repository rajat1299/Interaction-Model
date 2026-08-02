"""Deterministic Dolly/oasst2 prompt preparation for the Phase 2 replay pool (D10).

Feeds `phase2_replay_filtering.filter_replay_candidates`. This module turns pinned upstream
dataset rows into bucketed prompts; it never calls a model and never touches the network, so the
whole layer stays testable offline.

Three properties are load-bearing and were each got wrong on the first attempt:

* **Turn order.** The filter requires strictly alternating `user`/`assistant`. A multi-turn source
  thread contributes only its *user* turns, so the intermediate assistant replies must be generated
  by the backbone before the row is well-formed. This module therefore emits `user_turns` and
  leaves conversation assembly to the runner, rather than emitting consecutive user messages that
  the filter rejects.
* **Formatting.** Prompt text is passed through unmodified apart from Dolly's documented citation
  errata. Collapsing whitespace destroys code blocks and lists, which is silent corruption of
  exactly the buckets that depend on structure.
* **Bucket routing honesty.** A route that fires when it should not is worse than no route: it
  quietly fills a quota with the wrong material. Unroutable prompts are dropped and reported as a
  shortfall.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256

from im.generation.phase2_replay_filtering import COMPOSITION_QUOTAS
from im.generation.phase2_replay_routing import (
    REFUSAL as _ROUTER_REFUSAL,
)
from im.generation.phase2_replay_routing import (
    route_conversation,
    route_dolly,
)

DOLLY_SOURCE_ID = "databricks/databricks-dolly-15k"
OASST_SOURCE_ID = "OpenAssistant/oasst2"

#: D10 holds ~1,250 candidates against 1,000 selected; the surplus is replacement reserve.
CANDIDATE_MULTIPLIER = 1.25

#: One frozen global selection seed. Per-prompt seeds are not a selection algorithm -- they make
#: every row independently shuffled and the resulting pool unreproducible as a whole.
GLOBAL_SELECTION_SEED = "phase2-replay-selection-v1"

#: D10 wants ~200 multi-turn against ~800 single-turn in the final 1,000. Preferring multi-turn
#: unconditionally starves single-turn: an earlier pass produced 74% multi-turn and left the
#: allocator 483 single-turn rows short of what the composition needs. Multi-turn is capped at a
#: proportional share of each bucket instead, with headroom above the 20% final target.
MULTI_TURN_SHARE = 0.25

_REWRITE = "rewrite/edit/summarize"
_EXTRACT = "extraction/classification/format conversion"
_CONTEXT_QA = "context-grounded QA"
_PLANNING = "practical planning"
_CODING = "coding/debug"
_MATH = "math/data reasoning"
_EXPLAIN = "stable-knowledge explanation"
_COMPARISON = "evidence-grounded comparison/recommendation"
_TRANSLATION = "translation/language transformation"
_REFUSAL = "refusal/uncertainty/missing-information"
_CREATIVE = "light creative/casual"

# Dolly's eight categories cover seven D10 buckets. It holds no coding, math, translation, or
# refusal rows, and is entirely single-turn.
DOLLY_FAMILY_BY_CATEGORY: Mapping[str, str] = {
    "closed_qa": _CONTEXT_QA,
    "information_extraction": _EXTRACT,
    "classification": _EXTRACT,
    "summarization": _REWRITE,
    "brainstorming": _PLANNING,
    "open_qa": _EXPLAIN,
    "general_qa": _EXPLAIN,
    "creative_writing": _CREATIVE,
}

#: oasst2 routes across the **whole** closed family set, not only the four Dolly gaps. Every
#: multi-turn row in the pool comes from oasst2, so restricting it to four buckets makes the ~200
#: multi-turn target arithmetically unreachable.

#: Buckets no *automatic* route may fill. Refusal is fillable only from the audited allowlist,
#: never by a pattern. `refusal/uncertainty/missing-information` targets prompts
#: that are *accidentally* underspecified, which no keyword identifies -- an earlier length-based
#: fallback routed "What is the capital of France?" here, poisoning the one bucket D10 forbids
#: synthesizing. Unfilled is correct; wrongly filled is not recoverable.
UNROUTABLE_FAMILIES = frozenset({_REFUSAL, _CONTEXT_QA})


class ReplaySourceError(ValueError):
    """Raised when a pinned source row violates a documented preparation invariant."""


@dataclass(frozen=True, slots=True)
class ReplayPrompt:
    """One prepared prompt, pre-generation.

    `user_turns` holds the human turns. For a multi-turn row, `assistant_context_turns` holds the
    exact intervening OASST replies that those later user turns were written against. They receive
    zero loss; only the generated final assistant answer is supervised.
    """

    prompt_id: str
    dataset_source_id: str
    dataset_source_revision: str
    dataset_source_role: str
    task_family: str
    user_turns: tuple[str, ...]
    source_message_ids: tuple[str, ...]
    assistant_context_turns: tuple[str, ...] = ()
    source_category: str = ""

    @property
    def is_multi_turn(self) -> bool:
        return len(self.user_turns) > 1

    @property
    def generation_calls_required(self) -> int:
        """Only the final assistant answer is regenerated and supervised."""
        return 1


@dataclass(frozen=True, slots=True)
class PreparedPool:
    prompts: tuple[ReplayPrompt, ...]
    shortfalls: Mapping[str, int]
    multi_turn_count: int
    reserve: tuple[ReplayPrompt, ...]
    feasible_multi_turn: tuple[int, int] = (0, 0)

    @property
    def by_family(self) -> dict[str, int]:
        counts: dict[str, int] = dict.fromkeys(COMPOSITION_QUOTAS, 0)
        for prompt in self.prompts:
            counts[prompt.task_family] += 1
        return counts

    @property
    def generation_calls_required(self) -> int:
        return sum(prompt.generation_calls_required for prompt in self.prompts)


def candidate_target(task_family: str) -> int:
    """Per-bucket candidate count: the D10 quota plus reserve headroom."""
    return -(-int(COMPOSITION_QUOTAS[task_family] * CANDIDATE_MULTIPLIER * 100) // 100)


def prepare_dolly_prompts(
    rows: Iterable[Mapping[str, object]], *, revision: str, dispositions: Counter | None = None
) -> tuple[ReplayPrompt, ...]:
    """Route Dolly rows by validated task intent, preserving text byte-for-byte.

    The category is a hint checked against the instruction; mismatches are dropped rather than
    reassigned, so a noisy `creative_writing` label cannot become supply for another family.
    """
    prepared: list[ReplayPrompt] = []
    for index, row in enumerate(rows):
        category = str(row.get("category", "")).strip()
        instruction = str(row.get("instruction", "")).strip()
        context = str(row.get("context", "")).strip()
        if not instruction:
            _count(dispositions, "dolly", category, None, "empty_instruction")
            continue
        family, reason = route_dolly(category, instruction, bool(context))
        _count(dispositions, "dolly", category, family, reason)
        if family is None:
            continue
        content = f"{instruction}\n\n{context}" if context else instruction
        prepared.append(
            ReplayPrompt(
                prompt_id=_prompt_id(DOLLY_SOURCE_ID, revision, content),
                dataset_source_id=DOLLY_SOURCE_ID,
                dataset_source_revision=revision,
                dataset_source_role="primary",
                task_family=family,
                user_turns=(content,),
                source_message_ids=(str(row.get("message_id") or f"dolly:{index}"),),
                source_category=category,
            )
        )
    return tuple(prepared)


def _count(
    dispositions: Counter | None, source: str, category: str, family: str | None, reason: str | None
) -> None:
    if dispositions is not None:
        dispositions[(source, category, family or "-", reason or "accepted")] += 1


def prepare_oasst_prompts(
    threads: Iterable[Sequence[Mapping[str, object]]],
    *,
    revision: str,
    refusal_allowlist: frozenset[str] = frozenset(),
    dispositions: Counter | None = None,
) -> tuple[ReplayPrompt, ...]:
    """Route oasst2 threads by their terminal request, keeping complete path lineage."""
    prepared: list[ReplayPrompt] = []
    for thread in threads:
        turns, assistant_turns, message_ids = _oasst_turns(thread)
        if not turns:
            _count(dispositions, "oasst", "-", None, "no_usable_turns")
            continue
        if len(message_ids) != 2 * len(turns) - 1:
            _count(dispositions, "oasst", "-", None, "incomplete_lineage")
            continue
        terminal = message_ids[-1]
        if terminal in refusal_allowlist:
            family, reason = _ROUTER_REFUSAL, None
        else:
            family, reason = route_conversation(
                turns,
                source_assistant_context=bool(assistant_turns),
                assistant_context_turns=assistant_turns,
            )
        _count(dispositions, "oasst", "multi" if len(turns) > 1 else "single", family, reason)
        if family is None:
            continue
        prepared.append(
            ReplayPrompt(
                prompt_id=_prompt_id(OASST_SOURCE_ID, revision, "\n".join(turns)),
                dataset_source_id=OASST_SOURCE_ID,
                dataset_source_revision=revision,
                dataset_source_role="secondary",
                task_family=family,
                user_turns=tuple(turns),
                source_message_ids=tuple(message_ids),
                assistant_context_turns=tuple(assistant_turns),
                source_category="multi" if len(turns) > 1 else "single",
            )
        )
    return tuple(prepared)


def _oasst_turns(
    thread: Sequence[Mapping[str, object]],
) -> tuple[list[str], list[str], list[str]]:
    """Return exact alternating context plus complete source lineage."""
    if any(str(message.get("lang", "")).strip() != "en" for message in thread):
        return [], [], []
    user_turns, assistant_turns, ids = [], [], []
    for message in thread:
        ids.append(str(message.get("message_id", "")))
        role = str(message.get("role", "")).strip()
        text = str(message.get("text", "")).strip()
        if not text:
            return [], [], []
        if role == "prompter":
            user_turns.append(text)
        elif role == "assistant":
            assistant_turns.append(text)
    if len(assistant_turns) != max(0, len(user_turns) - 1):
        return [], [], []
    return user_turns, assistant_turns, ids


def sample_pool(
    prompts: Sequence[ReplayPrompt], *, selection_seed: str = GLOBAL_SELECTION_SEED
) -> PreparedPool:
    """Draw each bucket to its candidate target under one frozen global seed.

    Multi-turn is preferred, never enforced: the joint length/token constraint is solved downstream
    by `phase2_replay_allocation`, so this layer's job is to leave enough multi-turn headroom rather
    than duplicate that solver.
    """
    buckets: dict[str, list[ReplayPrompt]] = {family: [] for family in COMPOSITION_QUOTAS}
    seen: set[str] = set()
    for prompt in prompts:
        if prompt.prompt_id in seen:
            continue
        seen.add(prompt.prompt_id)
        buckets[prompt.task_family].append(prompt)

    selected: list[ReplayPrompt] = []
    reserve: list[ReplayPrompt] = []
    shortfalls: dict[str, int] = {}
    for family, available in buckets.items():
        target = candidate_target(family)
        ordered = sorted(
            available, key=lambda prompt: _shuffle_key(selection_seed, prompt.prompt_id)
        )
        multi = [prompt for prompt in ordered if prompt.is_multi_turn]
        single = sorted(
            (prompt for prompt in ordered if not prompt.is_multi_turn),
            key=lambda prompt: prompt.dataset_source_role != "primary",
        )
        # Dolly is the primary, grounded source for extraction. OASST list requests repeatedly
        # supplied open-ended advice and generation tasks under that label; use the ample curated
        # single-turn supply instead. Other families retain enough multi-turn headroom for 200.
        multi_cap = (
            0 if family == _EXTRACT else -(-int(target * MULTI_TURN_SHARE * 100) // 100)
        )
        chosen = single[: target - min(len(multi), multi_cap)]
        chosen += multi[: target - len(chosen)]
        # Only if one side is exhausted does the other backfill, so a bucket is never left short
        # merely because its supply is lopsided.
        if len(chosen) < target:
            chosen += [p for p in ordered if p not in chosen][: target - len(chosen)]
        taken = {prompt.prompt_id for prompt in chosen}
        selected.extend(chosen)
        reserve.extend(prompt for prompt in ordered if prompt.prompt_id not in taken)
        if len(chosen) < target:
            shortfalls[family] = target - len(chosen)
    low = high = 0
    for family, available in buckets.items():
        target = candidate_target(family)
        multi = sum(1 for prompt in available if prompt.is_multi_turn)
        single = len(available) - multi
        low += max(0, min(target, len(available)) - single)
        high += min(target, multi)
    return PreparedPool(
        prompts=tuple(selected),
        shortfalls=shortfalls,
        multi_turn_count=sum(1 for prompt in selected if prompt.is_multi_turn),
        reserve=tuple(reserve),
        feasible_multi_turn=(low, high),
    )


MULTI_TURN_TARGET = 200


def final_quota_bounds(pool: PreparedPool) -> dict[str, object]:
    """Binding feasibility: can the FINAL 1,000-row quotas carry exactly 200 multi-turn?

    Raw inventory and sampler-cap figures are diagnostics only. What binds is the selected ledger
    measured against each family's final quota.
    """
    selected: dict[str, list[ReplayPrompt]] = {}
    for prompt in pool.prompts:
        selected.setdefault(prompt.task_family, []).append(prompt)
    per_family: dict[str, dict[str, int]] = {}
    minimum = maximum = 0
    for family, quota in COMPOSITION_QUOTAS.items():
        rows = selected.get(family, [])
        multi = sum(1 for row in rows if row.is_multi_turn)
        single = len(rows) - multi
        forced = max(0, quota - single)
        selectable = min(quota, multi)
        minimum += forced
        maximum += selectable
        per_family[family] = {
            "forced_multi_turn": forced,
            "max_selectable_multi_turn": selectable,
            "quota": quota,
            "selected_multi_turn": multi,
            "selected_single_turn": single,
        }
    return {
        "exact_target": MULTI_TURN_TARGET,
        "feasible": minimum <= MULTI_TURN_TARGET <= maximum,
        "max_selectable_multi_turn": maximum,
        "min_forced_multi_turn": minimum,
        "per_family": per_family,
    }


def multi_turn_bounds(pool: PreparedPool) -> dict[str, object]:
    """Both feasibility questions, answered separately.

    Raw supply answers "could a pool of this shape ever carry the target". Cap-constrained answers
    "will the frozen sampler actually produce it". Publishing only the first would overstate
    feasibility; only the second would hide a supply problem behind an algorithm choice.
    """
    low, high = pool.feasible_multi_turn
    capped = 0
    per_family: dict[str, int] = {}
    for prompt in pool.prompts:
        if prompt.is_multi_turn:
            per_family[prompt.task_family] = per_family.get(prompt.task_family, 0) + 1
    for family in COMPOSITION_QUOTAS:
        target = candidate_target(family)
        capped += -(-int(target * MULTI_TURN_SHARE * 100) // 100)
    return {
        "cap_constrained_max": capped,
        "feasible_under_cap": low <= MULTI_TURN_TARGET <= capped,
        "observed": pool.multi_turn_count,
        "observed_by_family": dict(sorted(per_family.items())),
        "raw_supply_max": high,
        "raw_supply_min": low,
        "target": MULTI_TURN_TARGET,
    }


def capacity_report(pool: PreparedPool) -> dict[str, object]:
    """Pre-generation capacity, inspected before any provider call.

    Publishes the family-wise *feasible* multi-turn range, not only the observed rate: an observed
    22% says nothing about whether the exact 200-row target can be met once each family's supply is
    accounted for.
    """
    low, high = pool.feasible_multi_turn
    return {
        "final_quota_feasibility": final_quota_bounds(pool),
        "multi_turn_diagnostics": {
            **multi_turn_bounds(pool),
            "note": (
                "raw_supply_min is the multi-turn the pool is forced to carry where a family has "
                "too little single-turn supply. raw_supply_max is the most the supply could carry. "
                "cap_constrained_max is what the frozen sampler will actually allow."
            ),
        },
        "candidate_targets": {family: candidate_target(family) for family in COMPOSITION_QUOTAS},
        "generation_calls_required": pool.generation_calls_required,
        "kind": "phase2-replay-prompt-capacity-report",
        "multi_turn_count": pool.multi_turn_count,
        "multi_turn_target": 200,
        "reserve_count": len(pool.reserve),
        "selected_by_family": pool.by_family,
        "selected_count": len(pool.prompts),
        "shortfalls": dict(sorted(pool.shortfalls.items())),
        "unroutable_families": sorted(UNROUTABLE_FAMILIES),
        "unroutable_note": (
            "These buckets have no automatic route. refusal/uncertainty targets accidentally "
            "underspecified prompts, which no keyword identifies; context-grounded QA requires a "
            "supplied grounding passage, which only Dolly's closed_qa provides. Both are reported "
            "as shortfalls rather than filled by a permissive fallback."
        ),
    }


def _prompt_id(source_id: str, revision: str, content: str) -> str:
    return sha256(f"{source_id}@{revision}\n{content}".encode()).hexdigest()[:32]


def _shuffle_key(selection_seed: str, prompt_id: str) -> str:
    return sha256(f"{selection_seed}:{prompt_id}".encode()).hexdigest()


__all__ = [
    "CANDIDATE_MULTIPLIER",
    "DOLLY_FAMILY_BY_CATEGORY",
    "DOLLY_SOURCE_ID",
    "GLOBAL_SELECTION_SEED",
    "MULTI_TURN_SHARE",
    "MULTI_TURN_TARGET",
    "final_quota_bounds",
    "multi_turn_bounds",
    "OASST_SOURCE_ID",
    "UNROUTABLE_FAMILIES",
    "PreparedPool",
    "ReplayPrompt",
    "ReplaySourceError",
    "candidate_target",
    "capacity_report",
    "prepare_dolly_prompts",
    "prepare_oasst_prompts",
    "sample_pool",
]
