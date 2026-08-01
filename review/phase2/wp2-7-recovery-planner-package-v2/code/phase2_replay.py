"""Deterministic offline replay filtering and raw-input review-round planning."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256

from im.assets.model import artifact_digest
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
    "ReplayPoolFeasibility",
    "ReplayPlan",
    "ReplayProvenance",
    "ReplayReferenceManifest",
    "ReplayReviewError",
    "ReplaySelection",
    "ReplaySelectionDeficitError",
    "filter_replay_candidates",
    "finalize_replay_selection",
    "assess_replay_pool_feasibility",
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
_WP2_7_DEFERRED_CHECKS = (
    "interaction_overlap",
    "development_overlap",
    "test_overlap",
    "demo_overlap",
    "approved_response_overlap",
    "project_nonce_overlap",
    "heldout_asset_overlap",
    "stratified_human_review",
    "training_input_freeze",
)
_RUN_MANIFEST_KEYS = frozenset(
    {
        "final_max_completion_tokens",
        "fallbacks_enabled",
        "generation_seed",
        "kind",
        "model_slug",
        "prompt_ledger_sha256",
        "provider",
        "provider_model",
        "quantization",
        "reasoning_mode",
        "renderer",
        "selection_seed",
        "serialized_row_token_limit",
        "source_context_max_tokens",
        "source_context_supervised",
        "system_instruction_sha256",
        "temperature",
        "tokenizer_commit",
        "tokenizer_file_sha256",
        "tokenizer_revision",
        "tools_enabled",
    }
)
_GENERATION_AUDIT_KEYS = frozenset(
    {
        "calls",
        "completion_id",
        "generation_calls",
        "is_multi_turn",
        "prompt_id",
        "router_metadata",
        "run_manifest_sha256",
        "source_context_assistant_tokens",
        "serialized_row_token_count",
        "source_message_ids",
        "supervised_final_tokens",
    }
)
_CALL_RECORD_KEYS = frozenset(
    {
        "assistant_token_count",
        "call_index",
        "call_role",
        "completion_sha256",
        "max_completion_tokens",
        "router_metadata",
        "usage",
    }
)
_ROUTER_METADATA_KEYS = frozenset(
    {
        "attempt",
        "endpoint",
        "finish_reason",
        "generation_id",
        "is_byok",
        "model",
        "reasoning_tokens",
        "region",
        "selected_provider",
        "strategy",
    }
)
_ENDPOINT_KEYS = frozenset(
    {"context_length", "provider", "quantization", "served_model", "status", "tag"}
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


@dataclass(frozen=True, slots=True)
class ReplayPoolFeasibility:
    filter_report: ReplayFilterReport
    run_manifest_sha256: str
    selection_seed: str
    witness_selected: tuple[ReplayCandidate, ...]
    reserve: tuple[ReplayCandidate, ...]
    supervised_token_total: int
    deferred_checks: tuple[str, ...] = _WP2_7_DEFERRED_CHECKS


def assess_replay_pool_feasibility(
    candidates: Sequence[Mapping[str, object]],
    *,
    generation_audit: Sequence[Mapping[str, object]],
    run_manifest: Mapping[str, object],
    selection_seed: str,
    project_vocabulary_phrases: Sequence[str],
) -> ReplayPoolFeasibility:
    """Prove WP2-7 allocation feasibility without running WP2-9 review or overlap gates."""
    reference_manifest = {
        "interaction_texts": (),
        "development_texts": (),
        "test_texts": (),
        "demo_texts": (),
        "approved_responses": (),
        "heldout_assets": {},
        "project_nonces": (),
        "project_vocabulary_phrases": project_vocabulary_phrases,
    }
    _validate_raw_inputs(candidates, reference_manifest, selection_seed)
    run_manifest_sha256 = _validate_generation_audit(
        candidates, generation_audit, run_manifest, selection_seed
    )
    report = filter_replay_candidates(candidates, reference_manifest)
    accepted = tuple(
        outcome.candidate for outcome in report.accepted if outcome.candidate is not None
    )
    selected = _select_candidates(accepted, selection_seed)
    selected_ids = {candidate.completion_id for candidate in selected}
    reserve = tuple(
        sorted(
            (candidate for candidate in accepted if candidate.completion_id not in selected_ids),
            key=lambda candidate: _candidate_rank(selection_seed, candidate.completion_id),
        )
    )
    return ReplayPoolFeasibility(
        report,
        run_manifest_sha256,
        selection_seed,
        selected,
        reserve,
        sum(candidate.assistant_token_count for candidate in selected),
    )


def _validate_generation_audit(
    candidates: Sequence[Mapping[str, object]],
    audit_records: Sequence[Mapping[str, object]],
    run_manifest: Mapping[str, object],
    selection_seed: str,
) -> str:
    if set(run_manifest) != _RUN_MANIFEST_KEYS:
        raise ValueError("run_manifest must have the closed WP2-7 key set")
    if run_manifest["kind"] != "phase2-replay-run-manifest":
        raise ValueError("run_manifest kind is invalid")
    if run_manifest["selection_seed"] != selection_seed:
        raise ValueError("run_manifest selection seed does not match feasibility seed")
    if (
        run_manifest["final_max_completion_tokens"] != MAX_COMPLETION_TOKENS
        or run_manifest["source_context_max_tokens"] != 512
        or run_manifest["source_context_supervised"] is not False
        or run_manifest["serialized_row_token_limit"] != 3_072
        or run_manifest["generation_seed"] != 7
        or run_manifest["temperature"] != TEMPERATURE
        or run_manifest["tokenizer_revision"] != BACKBONE_REVISION
        or run_manifest["reasoning_mode"] != "none"
        or run_manifest["renderer"] != RENDERER
        or run_manifest["fallbacks_enabled"] is not False
        or run_manifest["tools_enabled"] is not False
        or any(
            not _nonempty_text(run_manifest[field])
            for field in (
                "model_slug",
                "provider",
                "provider_model",
                "quantization",
                "tokenizer_commit",
            )
        )
    ):
        raise ValueError("run_manifest does not match the frozen replay configuration")
    for field in (
        "prompt_ledger_sha256",
        "system_instruction_sha256",
        "tokenizer_file_sha256",
    ):
        if (
            not isinstance(run_manifest[field], str)
            or _SHA256_RE.fullmatch(run_manifest[field]) is None
        ):
            raise ValueError(f"run_manifest {field} must be a SHA-256 identity")
    run_manifest_sha256 = artifact_digest(run_manifest)
    audits: dict[str, Mapping[str, object]] = {}
    for audit in audit_records:
        if not isinstance(audit, Mapping) or set(audit) != _GENERATION_AUDIT_KEYS:
            raise ValueError("generation audit record must have the closed WP2-7 key set")
        prompt_id = audit["prompt_id"]
        if not _nonempty_text(prompt_id) or prompt_id in audits:
            raise ValueError("generation audit prompt IDs must be non-empty and unique")
        audits[prompt_id] = audit
    candidates_by_prompt = {
        candidate.get("prompt_id"): candidate
        for candidate in candidates
        if isinstance(candidate, Mapping) and _nonempty_text(candidate.get("prompt_id"))
    }
    if len(candidates_by_prompt) != len(candidates) or set(audits) != set(candidates_by_prompt):
        raise ValueError("generation audit must exactly cover candidate prompt IDs")
    for prompt_id, candidate in candidates_by_prompt.items():
        audit = audits[prompt_id]
        messages = candidate.get("messages")
        if not isinstance(messages, Sequence) or isinstance(messages, (str, bytes)):
            raise ValueError("audited candidate messages must be a sequence")
        system_messages = [
            message
            for message in messages
            if isinstance(message, Mapping) and message.get("role") == "system"
        ]
        if (
            len(system_messages) != 1
            or messages[0] != system_messages[0]
            or artifact_digest(system_messages[0].get("content"))
            != run_manifest["system_instruction_sha256"]
        ):
            raise ValueError(f"candidate {prompt_id} does not bind the replay system instruction")
        user_turns = sum(
            isinstance(message, Mapping) and message.get("role") == "user" for message in messages
        )
        source_ids = audit["source_message_ids"]
        expected_source_ids = (
            1 if candidate.get("dataset_source_role") == "primary" else (2 * user_turns) - 1
        )
        calls = audit["calls"]
        if (
            audit["completion_id"] != candidate.get("completion_id")
            or audit["generation_calls"] != 1
            or audit["is_multi_turn"] is not (user_turns > 1)
            or audit["run_manifest_sha256"] != run_manifest_sha256
            or not isinstance(source_ids, Sequence)
            or isinstance(source_ids, (str, bytes))
            or any(not _nonempty_text(source_id) for source_id in source_ids)
            or len(source_ids) != expected_source_ids
            or len(set(source_ids)) != len(source_ids)
            or audit["serialized_row_token_count"] > run_manifest["serialized_row_token_limit"]
            or audit["supervised_final_tokens"]
            != candidate.get("assistant_token_count", {}).get("count")
            or not isinstance(calls, Sequence)
            or isinstance(calls, (str, bytes))
            or len(calls) != 1
        ):
            raise ValueError(f"generation audit does not bind candidate {prompt_id}")
        for call_index, call in enumerate(calls):
            if not isinstance(call, Mapping) or set(call) != _CALL_RECORD_KEYS:
                raise ValueError("generation call record must have the closed WP2-7 key set")
            if (
                call["call_index"] != call_index
                or call["call_role"] != "supervised"
                or call["max_completion_tokens"] != run_manifest["final_max_completion_tokens"]
                or isinstance(call["assistant_token_count"], bool)
                or not isinstance(call["assistant_token_count"], int)
                or call["assistant_token_count"] < 1
            ):
                raise ValueError(f"generation call record is invalid for {prompt_id}")
            _validate_router_metadata(call["router_metadata"], run_manifest)
        source_context_tokens = audit["source_context_assistant_tokens"]
        if (
            audit["router_metadata"] != calls[-1]["router_metadata"]
            or isinstance(source_context_tokens, bool)
            or not isinstance(source_context_tokens, int)
            or source_context_tokens < 0
            or (user_turns == 1 and source_context_tokens != 0)
            or (user_turns > 1 and source_context_tokens < 1)
            or audit["supervised_final_tokens"] != calls[-1]["assistant_token_count"]
        ):
            raise ValueError(f"generation call accounting is invalid for {prompt_id}")
        _validate_router_metadata(audit["router_metadata"], run_manifest)
    return run_manifest_sha256


def _validate_router_metadata(value: object, run_manifest: Mapping[str, object]) -> None:
    if not isinstance(value, Mapping) or set(value) != _ROUTER_METADATA_KEYS:
        raise ValueError("router_metadata must have the closed pilot evidence key set")
    endpoint = value["endpoint"]
    if not isinstance(endpoint, Mapping) or set(endpoint) != _ENDPOINT_KEYS:
        raise ValueError("router endpoint evidence must have the closed key set")
    if (
        value["attempt"] != 1
        or value["finish_reason"] != "stop"
        or not _nonempty_text(value["generation_id"])
        or value["model"] != run_manifest["model_slug"]
        or value["reasoning_tokens"] != 0
        or value["is_byok"] is not False
        or value["selected_provider"] != endpoint["provider"]
        or value["strategy"] != "direct"
        or endpoint["tag"] != run_manifest["provider"]
        or endpoint["served_model"] != run_manifest["provider_model"]
        or endpoint["quantization"] != run_manifest["quantization"]
    ):
        raise ValueError("router metadata does not prove the pinned first-attempt endpoint")


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
