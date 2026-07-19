"""Deterministic offline replay filtering and raw-input review-round planning."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256

from im.generation.phase2_replay_allocation import (
    AllocationFailure,
    choose_maximum_token_selection,
    review_plan_sha256,
    review_rounds_sha256,
    stratified_review_sample,
)
from im.generation.phase2_replay_filtering import (
    BACKBONE_REVISION,
    COMPOSITION_QUOTAS,
    LENGTH_BANDS,
    MAX_COMPLETION_TOKENS,
    MAX_DATASET_SOURCES,
    NEAR_DUPLICATE_JACCARD,
    RENDERER,
    TEMPERATURE,
    ChatMessage,
    ReplayCandidate,
    ReplayFilterOutcome,
    ReplayFilterReport,
    ReplayProvenance,
    ReplayReferenceManifest,
    filter_replay_candidates,
)
from im.generation.phase2_replay_filtering import (
    load_reference_manifest as _load_reference_manifest,
)

__all__ = (
    "BACKBONE_REVISION",
    "COMPOSITION_QUOTAS",
    "LENGTH_BANDS",
    "MAX_COMPLETION_TOKENS",
    "MAX_DATASET_SOURCES",
    "MULTI_TURN_TARGET",
    "NEAR_DUPLICATE_JACCARD",
    "RENDERER",
    "SUPERVISED_TOKEN_MAX",
    "SUPERVISED_TOKEN_MIN",
    "TEMPERATURE",
    "TARGET_EXAMPLES",
    "ChatMessage",
    "ReplayCandidate",
    "ReplayDeficitReport",
    "ReplayFilterOutcome",
    "ReplayFilterReport",
    "ReplayPlan",
    "ReplayProvenance",
    "ReplayReferenceManifest",
    "ReplayReviewError",
    "ReplaySelection",
    "ReplaySelectionDeficitError",
    "filter_replay_candidates",
    "finalize_replay_selection",
    "plan_replay_review_round",
)

MULTI_TURN_TARGET = 200
TARGET_EXAMPLES = 1_000
SUPERVISED_TOKEN_MIN = 100_000
SUPERVISED_TOKEN_MAX = 130_000

_REVIEW_ROUND_KEYS = frozenset({"review_plan_sha256", "decisions"})
_SHA256_RE = re.compile(r"sha256:[0-9a-f]{64}\Z")
_REPLAY_BANDS = (
    ("short", LENGTH_BANDS["short"]),
    ("medium", LENGTH_BANDS["medium"]),
    ("long", LENGTH_BANDS["long"]),
)


class ReplaySelectionDeficitError(ValueError):
    def __init__(self, report: ReplayDeficitReport) -> None:
        self.report = report
        super().__init__(f"replay selection is infeasible: {report.summary()}")


ReplayReviewError = ValueError


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
    review_plan_sha256: str
    selection_seed: str
    provisional_selected: tuple[ReplayCandidate, ...]
    human_review_sample: tuple[ReplayCandidate, ...]
    flagged_selected: tuple[ReplayCandidate, ...]
    human_review_queue: tuple[ReplayCandidate, ...]


@dataclass(frozen=True, slots=True)
class ReplaySelection:
    selected: tuple[ReplayCandidate, ...]


def plan_replay_review_round(
    candidates: Sequence[Mapping[str, object]],
    reference_manifest: Mapping[str, object],
    *,
    selection_seed: str,
    review_rounds: Sequence[Mapping[str, object]],
) -> ReplayPlan:
    _validate_raw_inputs(candidates, reference_manifest, selection_seed)
    rounds = _load_review_rounds(review_rounds)
    return _replay_review_history(candidates, reference_manifest, selection_seed, rounds)


def finalize_replay_selection(
    candidates: Sequence[Mapping[str, object]],
    reference_manifest: Mapping[str, object],
    *,
    selection_seed: str,
    review_rounds: Sequence[Mapping[str, object]],
) -> ReplaySelection:
    _validate_raw_inputs(candidates, reference_manifest, selection_seed)
    rounds = _load_review_rounds(review_rounds)
    if not rounds:
        raise ReplayReviewError("a complete current review round is required before finalization")
    plan = _replay_review_history(candidates, reference_manifest, selection_seed, rounds[:-1])
    current_round = rounds[-1]
    _validate_review_round(plan, current_round)
    if any(not approved for approved in current_round[1].values()):
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
    review_rounds: tuple[tuple[str, dict[str, bool]], ...],
) -> ReplayPlan:
    rejected_by_review: set[str] = set()
    for round_index, review_round in enumerate(review_rounds):
        plan = _build_review_round(
            candidates,
            reference_manifest,
            selection_seed,
            rejected_by_review,
            review_rounds[:round_index],
        )
        _validate_review_round(plan, review_round, historical=True)
        rejected_by_review.update(
            completion_id for completion_id, approved in review_round[1].items() if not approved
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
    review_rounds: Sequence[tuple[str, Mapping[str, bool]]],
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
    review_sample = stratified_review_sample(
        selected,
        sample_size=100,
        stratum=lambda candidate: (
            candidate.task_family,
            candidate.length_band,
            candidate.is_multi_turn,
        ),
        rank=lambda candidate: _review_rank(selection_seed, candidate.completion_id),
    )
    flagged = tuple(candidate for candidate in selected if candidate.flags)
    sampled_ids = {candidate.completion_id for candidate in review_sample}
    queue = review_sample + tuple(
        candidate for candidate in flagged if candidate.completion_id not in sampled_ids
    )
    return ReplayPlan(
        report,
        manifest.sha256,
        review_rounds_sha256(review_rounds),
        review_plan_sha256(manifest.sha256, selection_seed, selected, queue),
        selection_seed,
        selected,
        review_sample,
        flagged,
        queue,
    )


def _validate_review_round(
    plan: ReplayPlan, review_round: tuple[str, Mapping[str, bool]], *, historical: bool = False
) -> None:
    digest, decisions = review_round
    if digest != plan.review_plan_sha256:
        raise ReplayReviewError("review round does not match the derived plan identity")
    queue_ids = {candidate.completion_id for candidate in plan.human_review_queue}
    if set(decisions) != queue_ids:
        raise ReplayReviewError("review decisions must exactly cover the derived current queue")
    if historical and all(decisions.values()):
        raise ReplayReviewError("an all-true review round is terminal and cannot be historical")


def _load_review_rounds(
    value: Sequence[Mapping[str, object]],
) -> tuple[tuple[str, dict[str, bool]], ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise TypeError("review_rounds must be an ordered sequence of complete review mappings")
    rounds: list[tuple[str, dict[str, bool]]] = []
    for review_round in value:
        if not isinstance(review_round, Mapping) or set(review_round) != _REVIEW_ROUND_KEYS:
            raise TypeError("each review round must contain only review_plan_sha256 and decisions")
        digest, decisions = review_round["review_plan_sha256"], review_round["decisions"]
        if not isinstance(digest, str) or _SHA256_RE.fullmatch(digest) is None:
            raise TypeError("review_plan_sha256 must be a SHA-256 identity")
        if not isinstance(decisions, Mapping) or any(
            not _nonempty_text(key) or not isinstance(approved, bool)
            for key, approved in decisions.items()
        ):
            raise TypeError("each review round must map non-empty completion IDs to bools")
        rounds.append((digest, dict(sorted(decisions.items()))))
    return tuple(rounds)


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
        replay_bands=_REPLAY_BANDS,
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


def _candidate_rank(selection_seed: str, completion_id: str) -> str:
    return sha256(f"phase2-replay-v3|{selection_seed}|{completion_id}".encode()).hexdigest()


def _review_rank(selection_seed: str, completion_id: str) -> str:
    return sha256(f"phase2-replay-review-v3|{selection_seed}|{completion_id}".encode()).hexdigest()


def _nonempty_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())
