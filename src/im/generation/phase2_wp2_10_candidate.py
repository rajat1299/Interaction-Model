"""WP2-10 amended TEST-400 owner-review candidate generation and publication.

This module performs the deterministic full candidate rebuild, writes its review evidence, and
publishes only the versioned owner-review packet. It does not issue an evaluation seal.
"""

from __future__ import annotations

import collections
import itertools
import json
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

import highspy

from im.assets.model import CorpusFamily, LookupAssetPayload, Split, canonical_artifact_bytes
from im.assets.registry import AssetRegistry
from im.assets.validate import load_split_seal_json, validate_registry
from im.canonical_json import canonicalize_tim_json
from im.generation.g7_catalog import (
    G7FamilyInputs,
    build_g7_fresh_session_programs,
    build_g7_lookup_live_program,
)
from im.generation.g7_checkpoint_catalog import build_g7_checkpoint_catalog
from im.generation.g7_contention_checkpoint import build_g7_contention_checkpoint_catalog
from im.generation.g7_failed_response_twins import (
    FAILED_QUERY_EVENT_ID,
    FAILED_RESULT_EVENT_ID,
    build_g7_failed_response_twin_programs,
)
from im.generation.g7_response_assets import HumanAuthoredResponseAsset, ResponseDraftSpec
from im.generation.g7_response_catalog import G7_RESPONSE_DRAFT_PROFILES
from im.generation.g7_response_pipeline import (
    load_g7_response_generations,
    materialize_g7_response_profiles,
)
from im.generation.g7_response_twins import (
    build_g7_response_floor_twin_program,
    validate_response_floor_twin_alignment,
)
from im.generation.g7_rollover_checkpoint import build_g7_rollover_checkpoint_catalog
from im.generation.ingestion import ScheduledSamplerFrame
from im.generation.phase2_dev_allocation import DEFAULT_APPROVED_ROOT, _load_sealed_registry
from im.generation.phase2_wp2_10_reachability import (
    CANDIDATE_OUTPUT,
    TEST_RESPONSE_STATES,
    TEST_STATE_TOTAL,
    Wp210ReachabilityError,
    build_test_allocation,
    governing_input_digests,
)
from im.generation.publication import directory_bytes, publish_directory_transaction
from im.generation.response_contracts import (
    AnswerContract,
    ProtectedClaimScope,
    RequiredAnswerPoint,
    ResponseKind,
)
from im.generation.scenarios import (
    BeatOpening,
    BeatResponseWarrant,
    BeatStaleResults,
    CounterfactualDeclaration,
    DeclaredPerturbation,
    GeneratedScenario,
    ResponseWarrantKind,
    ScenarioProgram,
    execute_scenario,
)
from im.generation.timing import TimingSeed, materialize_timing_plan
from im.schema.actions import (
    DelegateAction,
    IdleAction,
    IdleReason,
    IntegrateAction,
    RespondAction,
    Span,
)
from im.schema.common import ToolName
from im.schema.textspan import utf16_len
from im.tools import ScriptedToolResult

_ROOT = Path(__file__).resolve().parents[3]

CANDIDATE_V2_OUTPUT = _ROOT / "review" / "phase2" / "wp2-10-test-400-candidate-v2"
V2_SEED_NAMESPACE = "wp2-10-test-400-v2"
CANDIDATE_V3_OUTPUT = _ROOT / "review" / "phase2" / "wp2-10-test-400-candidate-v3"
V3_SEED_NAMESPACE = "wp2-10-test-400-v3"
TEST_CLOSEOUT_OUTPUT = _ROOT / "review" / "phase2" / "wp2-10-test-closeout"
OWNER_REVIEW_PROGRESS = _ROOT / "review" / "phase2" / "wp2-10-owner-review-progress.json"
_FRESH_SEEDS = 12
_CHECKPOINT_ATTEMPTS = 10
_RESPONSE_ITEMS = 10
_FAILED_RESPONSE_SPECS = (
    {
        "pair_id": "wp2-10-failed-result-a",
        "invitation": "Did you find any platform information for Fable Station?",
        "response": (
            "I couldn’t complete the check, so I don’t have the platform information yet. "
            "I can try again if you’d like."
        ),
        "result_mode": "lookup_failed",
        "answer_points": (("couldn’t complete",), ("platform information",)),
    },
    {
        "pair_id": "wp2-10-failed-result-b",
        "invitation": "Was any platform information available for Fable Station?",
        "response": (
            "I checked, but the platform information was unavailable, so I don’t have "
            "anything to add to the line."
        ),
        "result_mode": "no_usable_data",
        "answer_points": (("unavailable",), ("platform information",)),
    },
)
_FAILED_RESULT_SUPPORT = {
    "lookup_failed": {"code": "lookup_failed", "message": "lookup failed"},
    "no_usable_data": {
        "code": "no_usable_data",
        "message": "lookup returned no usable data",
    },
}
_ORDINARY_LIVE_RESPONSE_SPECS = (
    {
        "pair_id": "wp2-10-ordinary-live-c",
        "invitation": "Which platform does Fable Station use?",
        "response": "Fable Station uses platform 3.",
        "result": "Fable Station uses platform 3.",
    },
    {
        "pair_id": "wp2-10-ordinary-live-d",
        "invitation": "What platform is listed for Fable Station?",
        "response": "Fable Station uses platform 8.",
        "result": "Fable Station uses platform 8.",
    },
)
_LIVE_RESULT_QUERY_EVENT_ID = "e_000002"
_LIVE_RESULT_EVENT_ID = "e_000006"
_LIVE_RESULT_INVITATION_EVENT_ID = "e_000009"
_OWNER_APPROVAL = {
    "decision_source": "owner_chat",
    "recorded_at_utc": "2026-07-31T22:58:40Z",
}
_OWNER_REVIEW_RESPONSE = {
    "decision_source": "owner_chat",
    "source_progress": "review/phase2/wp2-10-owner-review-progress.json",
}
_OWNER_APPROVED_CALENDAR_RESPONSE = (
    "I can't add it to your calendar or set it for 7 PM. "
    "I can remind you after a set amount of time instead."
)
_AMBIGUITY_REPLACEMENT_SPECS = (
    {
        "replacement_id": "wp2-10-ambiguity-recipe-name-v3",
        "item_index": 3,
        "invitation": "Can you look up ingredients for a recipe? I haven't said which recipe.",
    },
    {
        "replacement_id": "wp2-10-ambiguity-station-name-v3",
        "item_index": 4,
        "invitation": "Can you check departure times? I haven't said which station.",
    },
    {
        "replacement_id": "wp2-10-ambiguity-book-edition-v3",
        "item_index": 5,
        "invitation": "Can you look up a book? I haven't said which edition.",
    },
)


def _test_family_inputs(registry: AssetRegistry) -> dict[CorpusFamily, G7FamilyInputs]:
    """Reuse the sealed TEST family-input recipe without importing its CLI script."""
    pool = registry.pool(Split.TEST)

    def template_id(family: CorpusFamily) -> str:
        return next(item.asset_id for item in pool.templates if family in item.coverage)

    def asset_ids(*families: CorpusFamily) -> tuple[str, ...]:
        return tuple(
            item.asset_id
            for item in pool.assets
            if any(family in item.coverage for family in families)
        )

    return {
        CorpusFamily.NEUTRAL_TYPING: G7FamilyInputs(
            template_id(CorpusFamily.NEUTRAL_TYPING), asset_ids(CorpusFamily.NEUTRAL_TYPING)
        ),
        CorpusFamily.MARK_POSITIVE: G7FamilyInputs(
            template_id(CorpusFamily.MARK_POSITIVE), asset_ids(CorpusFamily.MARK_POSITIVE)
        ),
        CorpusFamily.MARK_NEGATIVE: G7FamilyInputs(
            template_id(CorpusFamily.MARK_NEGATIVE),
            asset_ids(CorpusFamily.MARK_NEGATIVE, CorpusFamily.MARK_POSITIVE),
        ),
        CorpusFamily.LOOKUP_LIVE: G7FamilyInputs(
            template_id(CorpusFamily.LOOKUP_LIVE),
            tuple(
                item.asset_id
                for item in pool.assets
                if isinstance(item.payload, LookupAssetPayload)
            ),
        ),
        CorpusFamily.LOOKUP_STALE: G7FamilyInputs(
            template_id(CorpusFamily.LOOKUP_STALE), asset_ids(CorpusFamily.LOOKUP_STALE)
        ),
        CorpusFamily.TIMER_NORMAL: G7FamilyInputs(
            template_id(CorpusFamily.TIMER_NORMAL), asset_ids(CorpusFamily.TIMER_NORMAL)
        ),
        CorpusFamily.TIMER_CONTENTION: G7FamilyInputs(
            template_id(CorpusFamily.TIMER_CONTENTION),
            asset_ids(CorpusFamily.TIMER_CONTENTION, CorpusFamily.MARK_POSITIVE),
        ),
        CorpusFamily.RESERVED: G7FamilyInputs(
            template_id(CorpusFamily.RESERVED), asset_ids(CorpusFamily.RESERVED)
        ),
    }


def _timing_plan_identity(generated: GeneratedScenario) -> str:
    """Hash the materialized plan itself, never a scenario-input hash or seed label."""
    plan = generated.program.timing_plan
    return (
        "sha256:"
        + sha256(
            canonical_artifact_bytes(
                {
                    "population": plan.population.value,
                    "profile_id": plan.profile_id,
                    "rng_version": plan.rng_version,
                    "seed_id": plan.seed.timing_seed_id,
                    "service_ms": list(plan.service_ms),
                    "stream_class": plan.stream_class.value,
                }
            )
        ).hexdigest()
    )


def _semantic_key(
    family: str, decision: object, action: object, checkpoint: int | None = None
) -> str:
    return json.dumps(
        {
            "family": family,
            "type": action.type,
            "reason": getattr(action, "reason", None) and action.reason.value,
            "message": getattr(action, "message", None),
            "fact": str(getattr(action, "fact", None)),
            "floor_owned": decision.floor_owned,
            "active_timers": len(decision.active_timer_ids or ()),
            "canceled_timers": len(decision.canceled_timer_ids or ()),
            "open_timer_fires": len(decision.open_timer_fire_event_ids or ()),
            "open_tool_results": len(decision.open_tool_result_event_ids or ()),
            "pending_requests": len(decision.pending_request_ids or ()),
            "policy_seq": decision.observed_policy_seq,
            "checkpoint_seq": checkpoint,
        },
        sort_keys=True,
    )


def _candidate_row(
    generated: GeneratedScenario,
    decision: object,
    *,
    builder: str,
    shape_id: str,
    timing_seed: str,
) -> dict[str, object]:
    link = generated.program.counterfactual
    return {
        "stream_sha256": generated.sidecar.stream_sha256,
        "sidecar_sha256": generated.sidecar.sha256,
        "call_index": decision.call_index,
        "timing_seed": timing_seed,
        "timing_seed_id": generated.program.timing_plan.seed.timing_seed_id,
        "timing_plan_identity": _timing_plan_identity(generated),
        "asset_ids": tuple(generated.sidecar.asset_ids),
        "template_id": generated.sidecar.template_id,
        "scenario_input_sha256": generated.sidecar.scenario_input_sha256,
        "world_script_sha256": generated.sidecar.world_script_sha256,
        "builder": builder,
        "shape_id": shape_id,
        "counterfactual_group_id": None if link is None else link.group_id,
        "counterfactual_member_id": None if link is None else link.member_id,
    }


class _CandidatePool:
    """Unique generated decision identities, grouped for signature-first selection."""

    def __init__(self) -> None:
        self.by_signature: dict[str, list[dict[str, object]]] = collections.defaultdict(list)
        self.signature_meta: dict[str, dict[str, object]] = {}
        self.signature_by_identity: dict[tuple[str, int], str] = {}
        self.parents: dict[str, GeneratedScenario] = {}
        self._seen: set[tuple[str, int]] = set()

    def absorb(self, item: object, *, builder: str, shape_id: str, timing_seed: str) -> None:
        checkpoint = None
        selected: set[int] | None = None
        parent = item
        if hasattr(item, "selected_call_indices"):
            checkpoint = item.checkpoint_seq
            selected = set(item.selected_call_indices)
            parent = item.parent
        if not isinstance(parent, GeneratedScenario):
            raise TypeError("candidate pool requires generated scenarios")
        self.parents[parent.sidecar.stream_sha256] = parent
        family = parent.program.family.value
        for decision in parent.sidecar.decisions:
            if selected is not None and decision.call_index not in selected:
                continue
            identity = (parent.sidecar.stream_sha256, decision.call_index)
            if identity in self._seen:
                continue
            self._seen.add(identity)
            key = _semantic_key(family, decision, decision.action, checkpoint)
            self.signature_meta.setdefault(
                key,
                {
                    "family": family,
                    "action": decision.action.type,
                    "reason": getattr(decision.action, "reason", None)
                    and decision.action.reason.value,
                    "builder": builder,
                    "shape_id": shape_id,
                },
            )
            self.signature_by_identity[identity] = key
            self.by_signature[key].append(
                _candidate_row(
                    parent,
                    decision,
                    builder=builder,
                    shape_id=shape_id,
                    timing_seed=timing_seed,
                )
            )


async def _collect_regular_candidates(
    registry: AssetRegistry,
    *,
    root: Path,
    work: Path,
    seed_namespace: str = V2_SEED_NAMESPACE,
    explicit_lookup_requests: bool = False,
    exclude_response_items: frozenset[tuple[str, int]] = frozenset(),
    exclude_checkpoint_shapes: frozenset[str] = frozenset(),
) -> _CandidatePool:
    inputs = _test_family_inputs(registry)
    pool = _CandidatePool()
    for index in range(_FRESH_SEEDS):
        seed = f"{seed_namespace}:fresh:{index:03d}"
        for shape_id, program in build_g7_fresh_session_programs(
            registry,
            split=Split.TEST,
            inputs=inputs,
            master_seed=seed,
            explicit_lookup_requests=explicit_lookup_requests,
        ):
            generated = await execute_scenario(
                program,
                session_id=(
                    f"s_wp2_10_fresh_{index:03d}_{sha256(shape_id.encode()).hexdigest()[:8]}"
                ),
                directory=work / "fresh" / shape_id / f"{index:03d}",
                repository_root=root,
            )
            pool.absorb(generated, builder="g7_catalog.fresh", shape_id=shape_id, timing_seed=seed)

    for name, builder in (
        ("g7_checkpoint_catalog", build_g7_checkpoint_catalog),
        ("g7_contention_checkpoint", build_g7_contention_checkpoint_catalog),
        ("g7_rollover_checkpoint", build_g7_rollover_checkpoint_catalog),
    ):
        for attempt in range(_CHECKPOINT_ATTEMPTS):
            seed = f"{seed_namespace}:{name}:{attempt:03d}"
            kwargs: dict[str, object] = {}
            if name == "g7_rollover_checkpoint":
                kwargs["explicit_lookup_request"] = explicit_lookup_requests
            entries = await builder(
                registry,
                directory=work / name / f"{attempt:03d}",
                master_seed=seed,
                repository_root=root,
                **kwargs,
            )
            for entry in entries:
                if entry.shape_id in exclude_checkpoint_shapes:
                    continue
                pool.absorb(entry.parent, builder=name, shape_id=entry.shape_id, timing_seed=seed)

    generations = load_g7_response_generations(
        (root / "review/phase1/g7-response-generations.json").read_bytes()
    )
    profiles = await materialize_g7_response_profiles(
        registry,
        inputs=inputs,
        draft_profiles=G7_RESPONSE_DRAFT_PROFILES,
        generations=generations,
        master_seeds={
            profile.profile_id: f"{seed_namespace}:response-prefix:{profile.profile_id}"
            for profile in G7_RESPONSE_DRAFT_PROFILES
        },
        directory=work / "response-prefixes",
        repository_root=root,
    )
    pool.response_profiles = profiles
    pool.response_inputs = inputs
    for profile_spec in G7_RESPONSE_DRAFT_PROFILES:
        profile = profiles[profile_spec.profile_id]
        shape_id = profile_spec.group_id
        for item_index in range(_RESPONSE_ITEMS):
            if (shape_id, item_index) in exclude_response_items:
                continue
            seed = f"{seed_namespace}:response:{shape_id}:{item_index:03d}"
            twin = build_g7_response_floor_twin_program(
                registry,
                split=Split.TEST,
                family=profile_spec.family,
                inputs=inputs[profile_spec.family],
                profile=profile,
                master_seed=seed,
                item_index=item_index,
            )
            for member, program in zip(("yielded", "active"), twin.programs, strict=True):
                generated = await execute_scenario(
                    program,
                    session_id=(
                        f"s_wp2_10_response_{item_index:03d}_{member}_"
                        f"{sha256(shape_id.encode()).hexdigest()[:8]}"
                    ),
                    directory=work / "response" / shape_id / f"{item_index:03d}" / member,
                    repository_root=root,
                )
                pool.absorb(
                    generated,
                    builder="g7_response_twins",
                    shape_id=shape_id,
                    timing_seed=seed,
                )
    return pool


async def _failed_response_pairs(
    registry: AssetRegistry,
    *,
    root: Path,
    work: Path,
    pool: _CandidatePool,
    seed_namespace: str = V2_SEED_NAMESPACE,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    lookups = tuple(
        sorted(
            (
                item
                for item in registry.pool(Split.TEST).assets
                if registry.is_approved(item) and isinstance(item.payload, LookupAssetPayload)
            ),
            key=lambda item: item.asset_id,
        )
    )
    failure_index = next(
        (
            index
            for index, item in enumerate(lookups)
            if item.payload.query == "Fable Station platform"
        ),
        None,
    )
    if failure_index is None:
        raise Wp210ReachabilityError("current TEST lookup pool lacks Fable Station platform")
    failure = lookups[failure_index].payload
    selected_rows: list[dict[str, object]] = []
    records: list[dict[str, object]] = []
    for spec in _FAILED_RESPONSE_SPECS:
        mode = str(spec["result_mode"])
        contract = AnswerContract(
            response_kind=ResponseKind.FAILED_TOOL_NOTICE,
            subject_id=str(spec["pair_id"]),
            support_event_ids=(FAILED_QUERY_EVENT_ID, FAILED_RESULT_EVENT_ID),
            required_answer_points=tuple(
                RequiredAnswerPoint(tuple(point)) for point in spec["answer_points"]
            ),
            forbidden_claims=(),
        )
        seed = f"{seed_namespace}:failed-response:{spec['pair_id']}"
        twin = build_g7_failed_response_twin_programs(
            registry,
            invitation=str(spec["invitation"]),
            answer_contract=contract,
            candidate_response=str(spec["response"]),
            master_seed=seed,
            failed_lookup_index=failure_index,
            split=Split.TEST,
            result_mode=mode,
        )
        generated_members = []
        for member, program in zip(("yielded", "active"), twin.programs, strict=True):
            generated = await execute_scenario(
                program,
                session_id=f"s_wp2_10_{spec['pair_id']}_{member}",
                directory=work / "failed-response" / str(spec["pair_id"]) / member,
                repository_root=root,
            )
            pool.parents[generated.sidecar.stream_sha256] = generated
            generated_members.append((member, generated))
        yielded = generated_members[0][1]
        response_asset = HumanAuthoredResponseAsset.create(
            ResponseDraftSpec(str(spec["invitation"]), contract),
            teacher_visible_prefix=yielded.stream.decisions[-2].prefix_bytes.decode("utf-8"),
            response_text=str(spec["response"]),
            visible_support_by_event_id={
                FAILED_QUERY_EVENT_ID: failure.query,
                FAILED_RESULT_EVENT_ID: _FAILED_RESULT_SUPPORT[mode]["message"],
            },
        )
        response_id = str(spec["pair_id"])
        members = []
        for member, generated in generated_members:
            decision = generated.sidecar.decisions[-1]
            row = _candidate_row(
                generated,
                decision,
                builder="wp2_10.human_failed_response",
                shape_id="g7-checkpoint-lookup-live-failed-response",
                timing_seed=seed,
            )
            row.update(
                {
                    "family": generated.program.family.value,
                    "action": decision.action.type,
                    "reason": getattr(decision.action, "reason", None)
                    and decision.action.reason.value,
                    "semantic_signature_id": "sig-"
                    + sha256(
                        (mode + "\0" + decision.action.type + "\0" + member).encode()
                    ).hexdigest()[:16],
                    "timing_replica_depth": 1,
                    "failed_response_pair_id": response_id,
                    "failed_response_result_mode": mode,
                    "human_response_id": response_id,
                    "human_response_pair_id": response_id,
                }
            )
            selected_rows.append(row)
            members.append(
                {
                    "member": member,
                    "stream_sha256": generated.sidecar.stream_sha256,
                    "call_index": decision.call_index,
                    "action": decision.action.type,
                    "idle_reason": getattr(decision.action, "reason", None)
                    and decision.action.reason.value,
                    "counterfactual_group_id": row["counterfactual_group_id"],
                }
            )
        records.append(
            {
                "pair_id": response_id,
                "pair_kind": "failed_or_no_data",
                "content_authority": "human_authored_owner_approved",
                "owner_disposition": "approved",
                "owner_review": _OWNER_APPROVAL,
                "invitation": response_asset.draft.invitation,
                "answer_contract": response_asset.draft.answer_contract.as_json_object(),
                "visible_support": dict(response_asset.visible_support_by_event_id),
                "result_projection": _FAILED_RESULT_SUPPORT[mode],
                "result_mode": mode,
                "teacher_visible_prefix": response_asset.teacher_visible_prefix,
                "teacher_visible_prefix_sha256": "sha256:"
                + sha256(response_asset.teacher_visible_prefix.encode()).hexdigest(),
                "serialized_neutral_request": json.loads(
                    response_asset.serialized_neutral_request.decode("utf-8")
                ),
                "serialized_neutral_request_sha256": "sha256:"
                + response_asset.serialized_neutral_request_sha256,
                "response_text": response_asset.response_text,
                "response_text_sha256": "sha256:"
                + sha256(response_asset.response_text.encode()).hexdigest(),
                "members": members,
            }
        )
    return selected_rows, records


def _live_result_response_frame(
    at_ms: int, invitation: str, *, activity: str
) -> ScheduledSamplerFrame:
    cursor = utf16_len(invitation)
    return ScheduledSamplerFrame(
        at_ms,
        canonicalize_tim_json(
            {
                "text": invitation,
                "selection_start": cursor,
                "selection_end": cursor,
                "is_composing": False,
                "input_type": "insertText",
                "activity": activity,
                "client_ts": at_ms,
            }
        ),
    )


def _human_ordinary_live_twin_programs(
    registry: AssetRegistry,
    *,
    inputs: G7FamilyInputs,
    invitation: str,
    response: str,
    result: str,
    master_seed: str,
) -> tuple[ScenarioProgram, ScenarioProgram]:
    """Retain the sealed live result and flip only the final response floor."""
    base = build_g7_lookup_live_program(
        registry,
        split=Split.TEST,
        inputs=inputs,
        master_seed=master_seed,
    )
    if (
        len(base.actions) != 6
        or getattr(base.actions[0], "fact", None).event_id != _LIVE_RESULT_QUERY_EVENT_ID
        or getattr(base.actions[2], "result_event_id", None) != _LIVE_RESULT_EVENT_ID
        or len(base.tool_results) != 2
    ):
        raise Wp210ReachabilityError("sealed live-result source recipe drifted")
    group_id = (
        "wp2-10-ordinary-live-"
        + sha256(
            canonical_artifact_bytes(
                {
                    "invitation": invitation,
                    "master_seed": master_seed,
                    "result": result,
                }
            )
        ).hexdigest()[:16]
    )
    timing = materialize_timing_plan(base.timing_plan.seed, 5)
    shared_actions = (
        *base.actions[:2],
        IntegrateAction(type="integrate", result_event_id=_LIVE_RESULT_EVENT_ID, text=result),
        IdleAction(type="idle", reason=IdleReason.NO_TRIGGER, related_event_id=None),
    )
    shared_results = (replace(base.tool_results[0], data={"result": result}),)
    final_at_ms = base.frames[2].at_ms + timing.service_ms[3] + 1
    common = {
        "actions": shared_actions,
        "tool_results": shared_results,
        "perturbations": (
            DeclaredPerturbation("floor_opening"),
            *base.perturbations,
        ),
        "response_warrants_by_beat": (
            BeatResponseWarrant(
                "b4", _LIVE_RESULT_INVITATION_EVENT_ID, ResponseWarrantKind.INVITATION
            ),
        ),
    }
    yielded = replace(
        base,
        frames=(
            *base.frames[:2],
            _live_result_response_frame(
                base.frames[2].at_ms, "The note remains open.", activity="paused"
            ),
            _live_result_response_frame(final_at_ms, invitation, activity="paused"),
        ),
        actions=(
            *common["actions"],
            RespondAction(
                type="respond",
                reply_to_event_id=_LIVE_RESULT_INVITATION_EVENT_ID,
                text=response,
            ),
        ),
        timing_plan=timing,
        tool_results=common["tool_results"],
        beat_ids=base.beat_ids[:5],
        stale_results_by_beat=base.stale_results_by_beat[:5],
        perturbations=common["perturbations"],
        counterfactual=CounterfactualDeclaration(
            "twin", group_id, "yielded", ("active", "yielded"), "floor_opening"
        ),
        response_warrants_by_beat=common["response_warrants_by_beat"],
        openings_by_beat=(
            BeatOpening("b2", "e_000005"),
            BeatOpening("b4", _LIVE_RESULT_INVITATION_EVENT_ID),
        ),
    )
    active = replace(
        base,
        frames=(
            *base.frames[:2],
            _live_result_response_frame(
                base.frames[2].at_ms, "The note remains open.", activity="paused"
            ),
            _live_result_response_frame(final_at_ms, invitation, activity="active"),
        ),
        actions=(
            *common["actions"],
            IdleAction(
                type="idle",
                reason=IdleReason.AWAITING_OPENING,
                related_event_id=_LIVE_RESULT_INVITATION_EVENT_ID,
            ),
        ),
        timing_plan=timing,
        tool_results=common["tool_results"],
        beat_ids=base.beat_ids[:5],
        stale_results_by_beat=base.stale_results_by_beat[:5],
        perturbations=common["perturbations"],
        counterfactual=CounterfactualDeclaration(
            "twin", group_id, "active", ("active", "yielded"), "floor_opening"
        ),
        response_warrants_by_beat=common["response_warrants_by_beat"],
        openings_by_beat=(BeatOpening("b2", "e_000005"),),
    )
    warrant = BeatResponseWarrant(
        "b4", _LIVE_RESULT_INVITATION_EVENT_ID, ResponseWarrantKind.INVITATION
    )
    if (
        shared_results[0].status != "succeeded"
        or shared_results[0].data != {"result": result}
        or not isinstance(yielded.actions[-1], RespondAction)
        or yielded.actions[-1].reply_to_event_id != _LIVE_RESULT_INVITATION_EVENT_ID
        or not isinstance(active.actions[-1], IdleAction)
        or active.actions[-1].reason is not IdleReason.AWAITING_OPENING
        or active.actions[-1].related_event_id != _LIVE_RESULT_INVITATION_EVENT_ID
        or yielded.response_warrants_by_beat != (warrant,)
        or active.response_warrants_by_beat != (warrant,)
    ):
        raise Wp210ReachabilityError(
            "ordinary live response twins lost their succeeded-result link"
        )
    return yielded, active


async def _ordinary_live_response_pairs(
    registry: AssetRegistry,
    *,
    root: Path,
    work: Path,
    pool: _CandidatePool,
    seed_namespace: str = V2_SEED_NAMESPACE,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    live_assets = tuple(
        sorted(
            (
                asset
                for asset in registry.pool(Split.TEST).assets
                if registry.is_approved(asset) and isinstance(asset.payload, LookupAssetPayload)
            ),
            key=lambda asset: asset.asset_id,
        )
    )
    fable = next(
        (asset for asset in live_assets if asset.payload.query == "Fable Station platform"), None
    )
    companion = next((asset for asset in live_assets if asset is not fable), None)
    if fable is None or companion is None:
        raise Wp210ReachabilityError("sealed TEST pool lacks the Fable Station live-result source")
    template = next(
        template
        for template in registry.pool(Split.TEST).templates
        if registry.is_approved(template) and CorpusFamily.LOOKUP_LIVE in template.coverage
    )
    inputs = G7FamilyInputs(template.asset_id, (fable.asset_id, companion.asset_id))
    selected_rows: list[dict[str, object]] = []
    records: list[dict[str, object]] = []
    for spec in _ORDINARY_LIVE_RESPONSE_SPECS:
        contract = AnswerContract(
            response_kind=ResponseKind.ORDINARY_GROUNDED,
            subject_id=str(spec["pair_id"]),
            support_event_ids=(_LIVE_RESULT_QUERY_EVENT_ID, _LIVE_RESULT_EVENT_ID),
            required_answer_points=(
                RequiredAnswerPoint(("Fable Station",)),
                RequiredAnswerPoint((str(spec["result"]),)),
            ),
            forbidden_claims=(),
        )
        if (
            contract.support_event_ids != (_LIVE_RESULT_QUERY_EVENT_ID, _LIVE_RESULT_EVENT_ID)
            or FAILED_RESULT_EVENT_ID in contract.support_event_ids
        ):
            raise Wp210ReachabilityError("ordinary response contract lost its succeeded result")
        seed = f"{seed_namespace}:ordinary-live:{spec['pair_id']}"
        programs = _human_ordinary_live_twin_programs(
            registry,
            inputs=inputs,
            invitation=str(spec["invitation"]),
            response=str(spec["response"]),
            result=str(spec["result"]),
            master_seed=seed,
        )
        generated_members = []
        for member, program in zip(("yielded", "active"), programs, strict=True):
            generated = await execute_scenario(
                program,
                session_id=f"s_wp2_10_{spec['pair_id']}_{member}",
                directory=work / "ordinary-live" / str(spec["pair_id"]) / member,
                repository_root=root,
            )
            pool.parents[generated.sidecar.stream_sha256] = generated
            generated_members.append((member, generated))
        yielded = generated_members[0][1]
        response_asset = HumanAuthoredResponseAsset.create(
            ResponseDraftSpec(str(spec["invitation"]), contract),
            teacher_visible_prefix=yielded.stream.decisions[-1].prefix_bytes.decode("utf-8"),
            response_text=str(spec["response"]),
            visible_support_by_event_id={
                _LIVE_RESULT_QUERY_EVENT_ID: fable.payload.query,
                _LIVE_RESULT_EVENT_ID: str(spec["result"]),
            },
        )
        pair_id = str(spec["pair_id"])
        members = []
        for member, generated in generated_members:
            decision = generated.sidecar.decisions[-1]
            row = _candidate_row(
                generated,
                decision,
                builder="wp2_10.human_ordinary_live_response",
                shape_id="wp2-10-ordinary-live-result-response",
                timing_seed=seed,
            )
            row.update(
                {
                    "family": generated.program.family.value,
                    "action": decision.action.type,
                    "reason": getattr(decision.action, "reason", None)
                    and decision.action.reason.value,
                    "semantic_signature_id": "sig-"
                    + sha256(
                        (pair_id + "\0" + decision.action.type + "\0" + member).encode()
                    ).hexdigest()[:16],
                    "timing_replica_depth": 1,
                    "human_response_pair_id": pair_id,
                }
            )
            selected_rows.append(row)
            members.append(
                {
                    "member": member,
                    "stream_sha256": generated.sidecar.stream_sha256,
                    "call_index": decision.call_index,
                    "action": decision.action.type,
                    "idle_reason": getattr(decision.action, "reason", None)
                    and decision.action.reason.value,
                    "counterfactual_group_id": row["counterfactual_group_id"],
                }
            )
        records.append(
            {
                "pair_id": pair_id,
                "pair_kind": "ordinary_live_result",
                "content_authority": "human_authored_owner_approved",
                "owner_disposition": "approved",
                "owner_review": _OWNER_APPROVAL,
                "invitation": response_asset.draft.invitation,
                "answer_contract": response_asset.draft.answer_contract.as_json_object(),
                "visible_support": dict(response_asset.visible_support_by_event_id),
                "result_projection": {"query": fable.payload.query, "result": spec["result"]},
                "teacher_visible_prefix": response_asset.teacher_visible_prefix,
                "teacher_visible_prefix_sha256": "sha256:"
                + sha256(response_asset.teacher_visible_prefix.encode()).hexdigest(),
                "serialized_neutral_request": json.loads(
                    response_asset.serialized_neutral_request.decode("utf-8")
                ),
                "serialized_neutral_request_sha256": "sha256:"
                + response_asset.serialized_neutral_request_sha256,
                "response_text": response_asset.response_text,
                "response_text_sha256": "sha256:"
                + sha256(response_asset.response_text.encode()).hexdigest(),
                "members": members,
            }
        )
    return selected_rows, records


def _response_floor_frame(
    invitation: str, *, activity: str, at_ms: int = 0
) -> ScheduledSamplerFrame:
    cursor = utf16_len(invitation)
    return ScheduledSamplerFrame(
        at_ms,
        canonicalize_tim_json(
            {
                "text": invitation,
                "selection_start": cursor,
                "selection_end": cursor,
                "is_composing": False,
                "input_type": "insertText",
                "activity": activity,
                "client_ts": at_ms,
            }
        ),
    )


def _owner_rebuilt_floor_programs(
    yielded: ScenarioProgram,
    active: ScenarioProgram,
    *,
    invitation: str,
    response_text: str,
    replacement_id: str,
) -> tuple[ScenarioProgram, ScenarioProgram]:
    """Rebind a reviewed floor pair to human-authored request or response text."""
    group_id = (
        "wp2-10-v3-"
        + sha256(
            canonical_artifact_bytes(
                {
                    "invitation": invitation,
                    "replacement_id": replacement_id,
                    "response_text": response_text,
                    "timing_seed": yielded.master_seed,
                }
            )
        ).hexdigest()[:16]
    )
    rebuilt_yielded = replace(
        yielded,
        frames=(_response_floor_frame(invitation, activity="paused"),),
        actions=(
            RespondAction(
                type="respond",
                reply_to_event_id="e_000002",
                text=response_text,
            ),
        ),
        counterfactual=CounterfactualDeclaration(
            "twin", group_id, "yielded", ("active", "yielded"), "floor_opening"
        ),
    )
    rebuilt_active = replace(
        active,
        frames=(_response_floor_frame(invitation, activity="active"),),
        counterfactual=CounterfactualDeclaration(
            "twin", group_id, "active", ("active", "yielded"), "floor_opening"
        ),
    )
    validate_response_floor_twin_alignment(rebuilt_yielded, rebuilt_active)
    return rebuilt_yielded, rebuilt_active


async def _ambiguity_replacement_rows(
    registry: AssetRegistry,
    *,
    root: Path,
    work: Path,
    pool: _CandidatePool,
    seed_namespace: str,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Replace only the three owner-rejected clarification requests."""
    profiles = getattr(pool, "response_profiles", None)
    inputs = getattr(pool, "response_inputs", None)
    if not isinstance(profiles, dict) or not isinstance(inputs, dict):
        raise Wp210ReachabilityError("response profiles were not retained for owner rebuild")
    profile = profiles["g7-response-ambiguity-lookup-live"]
    selected_rows: list[dict[str, object]] = []
    records: list[dict[str, object]] = []
    for spec in _AMBIGUITY_REPLACEMENT_SPECS:
        replacement_id = str(spec["replacement_id"])
        invitation = str(spec["invitation"])
        item_index = int(spec["item_index"])
        seed = f"{seed_namespace}:owner-ambiguity:{replacement_id}"
        twin = build_g7_response_floor_twin_program(
            registry,
            split=Split.TEST,
            family=CorpusFamily.LOOKUP_LIVE,
            inputs=inputs[CorpusFamily.LOOKUP_LIVE],
            profile=profile,
            master_seed=seed,
            item_index=item_index,
        )
        response_text = twin.asset.candidate_response
        programs = _owner_rebuilt_floor_programs(
            *twin.programs,
            invitation=invitation,
            response_text=response_text,
            replacement_id=replacement_id,
        )
        generated_members = []
        for member, program in zip(("yielded", "active"), programs, strict=True):
            generated = await execute_scenario(
                program,
                session_id=f"s_wp2_10_{replacement_id}_{member}",
                directory=work / "owner-ambiguity" / replacement_id / member,
                repository_root=root,
            )
            pool.parents[generated.sidecar.stream_sha256] = generated
            generated_members.append((member, generated))
        yielded = generated_members[0][1]
        response_asset = HumanAuthoredResponseAsset.create(
            ResponseDraftSpec(invitation, twin.asset.draft.answer_contract),
            teacher_visible_prefix=yielded.stream.decisions[-1].prefix_bytes.decode("utf-8"),
            response_text=response_text,
            visible_support_by_event_id={"e_000002": invitation},
        )
        members = []
        for member, generated in generated_members:
            decision = generated.sidecar.decisions[-1]
            row = _candidate_row(
                generated,
                decision,
                builder="wp2_10.owner_rebuilt_ambiguity",
                shape_id="wp2-10-owner-rebuilt-ambiguity",
                timing_seed=seed,
            )
            row.update(
                {
                    "family": generated.program.family.value,
                    "action": decision.action.type,
                    "reason": getattr(decision.action, "reason", None)
                    and decision.action.reason.value,
                    "semantic_signature_id": "sig-"
                    + sha256((replacement_id + "\0" + member).encode()).hexdigest()[:16],
                    "timing_replica_depth": 1,
                    "owner_ambiguity_replacement_id": replacement_id,
                }
            )
            members.append(
                {
                    "member": member,
                    "stream_sha256": generated.sidecar.stream_sha256,
                    "call_index": decision.call_index,
                    "action": decision.action.type,
                    "idle_reason": getattr(decision.action, "reason", None)
                    and decision.action.reason.value,
                    "counterfactual_group_id": row["counterfactual_group_id"],
                }
            )
            if member == "active":
                selected_rows.append(row)
        records.append(
            {
                "replacement_id": replacement_id,
                "disposition": "rejected_rebuild",
                "repair": "natural_incomplete_user_request",
                "invitation": invitation,
                "answer_contract": response_asset.draft.answer_contract.as_json_object(),
                "response_text": response_asset.response_text,
                "response_text_sha256": "sha256:"
                + sha256(response_asset.response_text.encode()).hexdigest(),
                "teacher_visible_prefix": response_asset.teacher_visible_prefix,
                "teacher_visible_prefix_sha256": "sha256:"
                + sha256(response_asset.teacher_visible_prefix.encode()).hexdigest(),
                "serialized_neutral_request": json.loads(
                    response_asset.serialized_neutral_request.decode("utf-8")
                ),
                "serialized_neutral_request_sha256": "sha256:"
                + response_asset.serialized_neutral_request_sha256,
                "selected_member": "active",
                "members": members,
            }
        )
    return selected_rows, records


async def _calendar_response_replacement_pair(
    registry: AssetRegistry,
    *,
    root: Path,
    work: Path,
    pool: _CandidatePool,
    seed_namespace: str,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    """Replace the one rejected stale-response pair with the owner's exact response."""
    profiles = getattr(pool, "response_profiles", None)
    inputs = getattr(pool, "response_inputs", None)
    if not isinstance(profiles, dict) or not isinstance(inputs, dict):
        raise Wp210ReachabilityError("response profiles were not retained for owner rebuild")
    profile = profiles["g7-response-lookup-stale-mixed"]
    invitation = profile.assets[5].draft.invitation
    contract = AnswerContract(
        response_kind=ResponseKind.UNSUPPORTED_FEATURE_LIMITATION,
        subject_id="unsupported-stale-calendar-event",
        support_event_ids=("e_000002",),
        required_answer_points=(
            RequiredAnswerPoint(("can't add it to your calendar or set it for 7 PM",)),
            RequiredAnswerPoint(("can remind you after a set amount of time instead",)),
        ),
        forbidden_claims=("I added it to your calendar", "scheduled the recital at 7 PM"),
        protected_claim_scope=ProtectedClaimScope.CALENDAR_TIMER,
    )
    replacement_id = "wp2-10-calendar-floor-owner-response-v3"
    seed = f"{seed_namespace}:owner-calendar-response"
    twin = build_g7_response_floor_twin_program(
        registry,
        split=Split.TEST,
        family=CorpusFamily.LOOKUP_STALE,
        inputs=inputs[CorpusFamily.LOOKUP_STALE],
        profile=profile,
        master_seed=seed,
        item_index=5,
    )
    programs = _owner_rebuilt_floor_programs(
        *twin.programs,
        invitation=invitation,
        response_text=_OWNER_APPROVED_CALENDAR_RESPONSE,
        replacement_id=replacement_id,
    )
    generated_members = []
    for member, program in zip(("yielded", "active"), programs, strict=True):
        generated = await execute_scenario(
            program,
            session_id=f"s_wp2_10_{replacement_id}_{member}",
            directory=work / "owner-calendar-response" / member,
            repository_root=root,
        )
        pool.parents[generated.sidecar.stream_sha256] = generated
        generated_members.append((member, generated))
    yielded = generated_members[0][1]
    response_asset = HumanAuthoredResponseAsset.create(
        ResponseDraftSpec(invitation, contract),
        teacher_visible_prefix=yielded.stream.decisions[-1].prefix_bytes.decode("utf-8"),
        response_text=_OWNER_APPROVED_CALENDAR_RESPONSE,
        visible_support_by_event_id={"e_000002": invitation},
    )
    rows = []
    members = []
    for member, generated in generated_members:
        decision = generated.sidecar.decisions[-1]
        row = _candidate_row(
            generated,
            decision,
            builder="wp2_10.owner_calendar_response",
            shape_id="wp2-10-owner-calendar-response",
            timing_seed=seed,
        )
        row.update(
            {
                "family": generated.program.family.value,
                "action": decision.action.type,
                "reason": getattr(decision.action, "reason", None) and decision.action.reason.value,
                "semantic_signature_id": "sig-"
                + sha256((replacement_id + "\0" + member).encode()).hexdigest()[:16],
                "timing_replica_depth": 1,
                "human_response_pair_id": replacement_id,
                "owner_response_replacement_id": replacement_id,
            }
        )
        rows.append(row)
        members.append(
            {
                "member": member,
                "stream_sha256": generated.sidecar.stream_sha256,
                "call_index": decision.call_index,
                "action": decision.action.type,
                "idle_reason": getattr(decision.action, "reason", None)
                and decision.action.reason.value,
                "counterfactual_group_id": row["counterfactual_group_id"],
            }
        )
    return rows, {
        "pair_id": replacement_id,
        "pair_kind": "owner_replaced_calendar_response",
        "content_authority": "human_authored_owner_approved",
        "owner_disposition": "approved_replacement",
        "owner_review": _OWNER_REVIEW_RESPONSE,
        "invitation": response_asset.draft.invitation,
        "answer_contract": response_asset.draft.answer_contract.as_json_object(),
        "visible_support": dict(response_asset.visible_support_by_event_id),
        "teacher_visible_prefix": response_asset.teacher_visible_prefix,
        "teacher_visible_prefix_sha256": "sha256:"
        + sha256(response_asset.teacher_visible_prefix.encode()).hexdigest(),
        "serialized_neutral_request": json.loads(
            response_asset.serialized_neutral_request.decode("utf-8")
        ),
        "serialized_neutral_request_sha256": "sha256:"
        + response_asset.serialized_neutral_request_sha256,
        "response_text": response_asset.response_text,
        "response_text_sha256": "sha256:"
        + sha256(response_asset.response_text.encode()).hexdigest(),
        "members": members,
    }


def _standalone_no_trigger_program(
    base: ScenarioProgram, *, source: str, master_seed: str, at_ms: int
) -> ScenarioProgram:
    """Keep a reviewed bare phrase as an actual no-trigger state, not a request."""
    timing = materialize_timing_plan(TimingSeed(base.bundle.split, master_seed), 1)
    return replace(
        base,
        master_seed=master_seed,
        timing_plan=timing,
        frames=(_response_floor_frame(source, activity="paused", at_ms=at_ms),),
        actions=(IdleAction(type="idle", reason=IdleReason.NO_TRIGGER, related_event_id=None),),
        tool_results=(),
        beat_ids=("b0",),
        stale_results_by_beat=(BeatStaleResults("b0", ()),),
        perturbations=(DeclaredPerturbation("draft_revision"),),
        counterfactual=None,
        openings_by_beat=None,
        need_lineage_by_beat=None,
        delegate_provenance_by_beat=None,
        cancel_resolution_evidence_by_beat=(),
        response_warrants_by_beat=(),
        require_g7_evidence=False,
    )


def _source_safe_stale_lifecycle_program(
    base: ScenarioProgram, *, master_seed: str
) -> ScenarioProgram:
    """Create one complete natural lookup lifecycle over sealed stale-family inputs."""
    payload = next(
        (
            asset.payload
            for asset in base.bundle.assets
            if isinstance(asset.payload, LookupAssetPayload)
            and CorpusFamily.LOOKUP_STALE in asset.coverage
        ),
        None,
    )
    if payload is None:
        raise Wp210ReachabilityError("stale-family replacement lacks a lookup asset")
    query = payload.query
    source = f"Look up {query}."
    timing = materialize_timing_plan(TimingSeed(base.bundle.split, master_seed), 4)
    start = utf16_len("Look up ")
    return replace(
        base,
        master_seed=master_seed,
        timing_plan=timing,
        frames=(
            _response_floor_frame(source, activity="paused"),
            ScheduledSamplerFrame(
                timing.service_ms[0] + 1,
                _response_floor_frame(source, activity="paused").raw_bytes,
            ),
            ScheduledSamplerFrame(
                timing.service_ms[0] + 700 + timing.service_ms[2] + 1,
                _response_floor_frame(source, activity="paused").raw_bytes,
            ),
        ),
        actions=(
            DelegateAction(
                type="delegate",
                fact=Span(
                    event_id="e_000002",
                    start_utf16=start,
                    end_utf16=start + utf16_len(query),
                    text=query,
                ),
                tool=ToolName.LOOKUP,
                args={"query": query},
            ),
            IdleAction(
                type="idle",
                reason=IdleReason.AWAITING_TOOL,
                related_event_id="e_000002",
            ),
            IntegrateAction(
                type="integrate",
                result_event_id="e_000006",
                text=payload.result_a,
            ),
            IdleAction(
                type="idle",
                reason=IdleReason.ALREADY_HANDLED,
                related_event_id="e_000006",
            ),
        ),
        tool_results=(ScriptedToolResult(latency_ms=700, data={"nonce": payload.result_a}),),
        beat_ids=("b0", "b1", "b2", "b3"),
        stale_results_by_beat=tuple(
            BeatStaleResults(beat, ()) for beat in ("b0", "b1", "b2", "b3")
        ),
        perturbations=(DeclaredPerturbation("tool_result"),),
        counterfactual=None,
        openings_by_beat=None,
        need_lineage_by_beat=None,
        delegate_provenance_by_beat=None,
        cancel_resolution_evidence_by_beat=(),
        response_warrants_by_beat=(),
        require_g7_evidence=False,
    )


async def _relabelled_bare_phrase_rows(
    *,
    root: Path,
    work: Path,
    pool: _CandidatePool,
    seed_namespace: str,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Retain all 16 reviewed bare phrases as no-trigger examples."""
    neutral_base = next(
        parent.program
        for parent in pool.parents.values()
        if parent.program.family is CorpusFamily.NEUTRAL_TYPING
    )
    subjects = (
        *("Fable Station platform",) * 8,
        *("Morrow Glen cistern fill percentage",) * 7,
        "Alder Loop registry",
    )
    rows: list[dict[str, object]] = []
    records: list[dict[str, object]] = []
    for index, subject in enumerate(subjects):
        seed = f"{seed_namespace}:owner-relabel:{index:03d}"
        program = _standalone_no_trigger_program(
            neutral_base,
            source=subject,
            master_seed=seed,
            at_ms=index + 1,
        )
        generated = await execute_scenario(
            program,
            session_id=f"s_wp2_10_owner_relabel_{index:03d}",
            directory=work / "owner-relabel" / f"{index:03d}",
            repository_root=root,
        )
        pool.parents[generated.sidecar.stream_sha256] = generated
        decision = generated.sidecar.decisions[-1]
        row = _candidate_row(
            generated,
            decision,
            builder="wp2_10.owner_relabelled_bare_phrase",
            shape_id="wp2-10-owner-relabelled-bare-phrase",
            timing_seed=seed,
        )
        row.update(
            {
                "family": CorpusFamily.NEUTRAL_TYPING.value,
                "action": decision.action.type,
                "reason": IdleReason.NO_TRIGGER.value,
                "semantic_signature_id": "sig-"
                + sha256((subject + "\0" + str(index)).encode()).hexdigest()[:16],
                "timing_replica_depth": 1,
                "owner_relabelled_bare_phrase": subject,
            }
        )
        rows.append(row)
        records.append(
            {
                "source": subject,
                "family": CorpusFamily.NEUTRAL_TYPING.value,
                "original_source_family": (
                    CorpusFamily.ROLLOVER.value
                    if index == len(subjects) - 1
                    else CorpusFamily.LOOKUP_LIVE.value
                ),
                "disposition": "rejected_relabel",
                "replacement_action": "idle",
                "replacement_reason": "no_trigger",
                "state_identity": {
                    "stream_sha256": row["stream_sha256"],
                    "call_index": row["call_index"],
                },
            }
        )
    return rows, records


async def _source_safe_stale_idle_rows(
    *, root: Path, work: Path, pool: _CandidatePool, seed_namespace: str
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Fill stale-family idle capacity without malformed checkpoint ancestry."""
    base = next(
        parent.program
        for parent in pool.parents.values()
        if parent.program.family is CorpusFamily.LOOKUP_STALE
    )
    rows: list[dict[str, object]] = []
    records: list[dict[str, object]] = []
    query = next(
        asset.payload.query
        for asset in base.bundle.assets
        if isinstance(asset.payload, LookupAssetPayload)
        and CorpusFamily.LOOKUP_STALE in asset.coverage
    )
    for index in range(4):
        seed = f"{seed_namespace}:source-safe-stale-idle:{index:03d}"
        program = _source_safe_stale_lifecycle_program(base, master_seed=seed)
        generated = await execute_scenario(
            program,
            session_id=f"s_wp2_10_source_safe_stale_{index:03d}",
            directory=work / "source-safe-stale-idle" / f"{index:03d}",
            repository_root=root,
        )
        pool.parents[generated.sidecar.stream_sha256] = generated
        decision = next(
            item
            for item in generated.sidecar.decisions
            if isinstance(item.action, IdleAction)
            and item.action.reason is IdleReason.AWAITING_TOOL
        )
        row = _candidate_row(
            generated,
            decision,
            builder="wp2_10.source_safe_stale_idle",
            shape_id="wp2-10-source-safe-stale-idle",
            timing_seed=seed,
        )
        row.update(
            {
                "family": CorpusFamily.LOOKUP_STALE.value,
                "action": "idle",
                "reason": IdleReason.AWAITING_TOOL.value,
                "semantic_signature_id": "sig-"
                + sha256(b"source-safe-stale-idle").hexdigest()[:16],
                "timing_replica_depth": index + 1,
                "source_safe_replacement": "malformed_checkpoint_descendants",
            }
        )
        rows.append(row)
        records.append(
            {
                "state_identity": {
                    "stream_sha256": row["stream_sha256"],
                    "call_index": row["call_index"],
                },
                "source": f"Look up {query}.",
                "family": CorpusFamily.LOOKUP_STALE.value,
                "action": "idle",
                "reason": "awaiting_tool",
                "replaces": "malformed_checkpoint_descendants",
            }
        )
    return rows, records


_TWIN_MATCH_FIELDS = (
    "family",
    "builder",
    "shape_id",
    "timing_seed",
    "timing_seed_id",
    "timing_plan_identity",
    "asset_ids",
    "template_id",
    "world_script_sha256",
)


def _validate_response_floor_pairs(
    rows: list[dict[str, object]], *, expected_pairs: int = TEST_RESPONSE_STATES
) -> None:
    """Require every selected response floor state to retain its exact counterpart."""
    floor_rows = [
        row
        for row in rows
        if row["action"] == "respond"
        or (row["action"] == "idle" and row["reason"] == "awaiting_opening")
    ]
    if len(floor_rows) != 2 * expected_pairs:
        raise Wp210ReachabilityError(
            f"selected response-floor rows do not total {expected_pairs} complete pairs"
        )
    by_group: dict[str | None, list[dict[str, object]]] = collections.defaultdict(list)
    for row in floor_rows:
        by_group[row["counterfactual_group_id"]].append(row)
    if None in by_group or len(by_group) != expected_pairs:
        raise Wp210ReachabilityError(
            "selected response-floor rows have missing or singleton groups"
        )
    for group_id, members in by_group.items():
        if len(members) != 2:
            raise Wp210ReachabilityError(f"response-floor group {group_id} is not a pair")
        response = [
            row
            for row in members
            if row["action"] == "respond" and row["counterfactual_member_id"] == "yielded"
        ]
        awaiting = [
            row
            for row in members
            if row["action"] == "idle"
            and row["reason"] == "awaiting_opening"
            and row["counterfactual_member_id"] == "active"
        ]
        if len(response) != 1 or len(awaiting) != 1:
            raise Wp210ReachabilityError(
                f"response-floor group {group_id} lacks yielded/respond and active/awaiting-opening"
            )
        for field in _TWIN_MATCH_FIELDS:
            if response[0][field] != awaiting[0][field]:
                raise Wp210ReachabilityError(
                    f"response-floor group {group_id} differs across its floor variants: {field}"
                )


def _select_regular_response_floor_pairs(
    pool: _CandidatePool, target_by_family: dict[str, int]
) -> list[dict[str, object]]:
    """Select response twins as units, before independent cell selection begins."""
    groups: dict[str, list[tuple[str, dict[str, object]]]] = collections.defaultdict(list)
    for signature, candidates in pool.by_signature.items():
        for candidate in candidates:
            group_id = candidate["counterfactual_group_id"]
            if group_id is not None:
                groups[str(group_id)].append((signature, candidate))

    pair = tuple[tuple[str, dict[str, object]], tuple[str, dict[str, object]]]
    pairs_by_family: dict[str, dict[tuple[str, str], list[pair]]] = collections.defaultdict(
        lambda: collections.defaultdict(list)
    )
    for group_id, entries in groups.items():
        response = [
            entry
            for entry in entries
            if pool.signature_meta[entry[0]]["action"] == "respond"
            and entry[1]["counterfactual_member_id"] == "yielded"
        ]
        awaiting = [
            entry
            for entry in entries
            if pool.signature_meta[entry[0]]["action"] == "idle"
            and pool.signature_meta[entry[0]]["reason"] == "awaiting_opening"
            and entry[1]["counterfactual_member_id"] == "active"
        ]
        if len(response) != 1 or len(awaiting) != 1:
            continue
        response_signature, response_candidate = response[0]
        awaiting_signature, awaiting_candidate = awaiting[0]
        response_row = {**pool.signature_meta[response_signature], **response_candidate}
        awaiting_row = {**pool.signature_meta[awaiting_signature], **awaiting_candidate}
        _validate_response_floor_pairs([response_row, awaiting_row], expected_pairs=1)
        family = str(response_row["family"])
        pair_signature = (response_signature, awaiting_signature)
        pairs_by_family[family][pair_signature].append(
            ((response_signature, response_candidate), (awaiting_signature, awaiting_candidate))
        )

    selected: list[pair] = []
    for family, target in sorted(target_by_family.items()):
        if target == 0:
            continue
        buckets = pairs_by_family[family]
        cursor = {signature: 0 for signature in buckets}
        for signature in buckets:
            buckets[signature].sort(
                key=lambda pair: (
                    str(pair[0][1]["timing_seed"]),
                    str(pair[0][1]["stream_sha256"]),
                )
            )
        selected_count = 0
        for _depth in itertools.count(1):
            if selected_count == target:
                break
            progressed = False
            for signature in sorted(buckets):
                if selected_count == target:
                    break
                index = cursor[signature]
                if index >= len(buckets[signature]):
                    continue
                selected.append(buckets[signature][index])
                cursor[signature] += 1
                selected_count += 1
                progressed = True
            if not progressed:
                available = sum(len(items) for items in buckets.values())
                raise Wp210ReachabilityError(
                    f"response-floor pair shortfall for {family}: need {target}, have {available}"
                )

    depths: collections.Counter[str] = collections.Counter()
    rows: list[dict[str, object]] = []
    for pair in selected:
        for signature, candidate in pair:
            depths[signature] += 1
            rows.append(
                {
                    **pool.signature_meta[signature],
                    **candidate,
                    "semantic_signature_id": "sig-" + sha256(signature.encode()).hexdigest()[:16],
                    "timing_replica_depth": depths[signature],
                }
            )
    _validate_response_floor_pairs(rows, expected_pairs=sum(target_by_family.values()))
    return rows


def _solve_idle_split(
    family_idle: dict[str, int],
    reason_target: dict[str, int],
    available: dict[tuple[str, str], int],
) -> dict[tuple[str, str], int]:
    keys = sorted(available)
    model = highspy.Highs()
    model.setOptionValue("output_flag", False)
    model.setOptionValue("threads", 1)
    for key in keys:
        model.addVar(0, available[key])
    model.changeColsIntegrality(
        len(keys), list(range(len(keys))), [highspy.HighsVarType.kInteger] * len(keys)
    )
    for family, target in family_idle.items():
        indices = [index for index, key in enumerate(keys) if key[0] == family]
        if not indices and target:
            raise Wp210ReachabilityError(f"no idle candidates for family {family}")
        model.addRow(target, target, len(indices), indices, [1.0] * len(indices))
    for reason, target in reason_target.items():
        indices = [index for index, key in enumerate(keys) if key[1] == reason]
        if not indices and target:
            raise Wp210ReachabilityError(f"no idle candidates for reason {reason}")
        model.addRow(target, target, len(indices), indices, [1.0] * len(indices))
    model.run()
    if model.getModelStatus() != highspy.HighsModelStatus.kOptimal:
        raise Wp210ReachabilityError(f"idle split infeasible: {model.getModelStatus()}")
    return {
        keys[index]: int(round(value)) for index, value in enumerate(model.getSolution().col_value)
    }


def _select_exact_400(
    pool: _CandidatePool,
    allocation: dict[str, object],
    preselected_pair_rows: list[dict[str, object]],
) -> dict[str, object]:
    family_action = allocation["family_action"]
    idle_reason = allocation["idle_reason"]
    assert isinstance(family_action, dict) and isinstance(idle_reason, dict)
    normal_actions = {family: dict(actions) for family, actions in family_action.items()}
    preselected_response_by_family = collections.Counter(
        str(row["family"]) for row in preselected_pair_rows if row["action"] == "respond"
    )
    regular_pair_target = {
        str(family): int(actions.get("respond", 0)) - preselected_response_by_family[str(family)]
        for family, actions in normal_actions.items()
    }
    if any(target < 0 for target in regular_pair_target.values()):
        raise Wp210ReachabilityError("reserved response pairs exceed the response allocation")
    regular_pair_rows = _select_regular_response_floor_pairs(pool, regular_pair_target)
    pair_rows = [*preselected_pair_rows, *regular_pair_rows]
    _validate_response_floor_pairs(pair_rows)
    selected_identities = {(str(row["stream_sha256"]), int(row["call_index"])) for row in pair_rows}
    if len(selected_identities) != len(pair_rows):
        raise Wp210ReachabilityError("preselected rows contain duplicate state identities")

    reserved_cells = collections.Counter(
        (str(row["family"]), str(row["action"])) for row in pair_rows
    )
    reserved_reasons = collections.Counter(
        str(row["reason"]) for row in pair_rows if row["action"] == "idle"
    )
    for (family, action), count in reserved_cells.items():
        normal_actions[family][action] -= count
        if normal_actions[family][action] < 0:
            raise Wp210ReachabilityError(f"reserved response pair exceeds {family}|{action}")
    normal_reasons = dict(idle_reason)
    for reason, count in reserved_reasons.items():
        normal_reasons[reason] -= count
        if normal_reasons[reason] < 0:
            raise Wp210ReachabilityError(f"reserved response pair exceeds idle reason {reason}")

    by_cell: dict[tuple[str, str], list[str]] = collections.defaultdict(list)
    idle_available: dict[tuple[str, str], int] = collections.defaultdict(int)
    for key, meta in pool.signature_meta.items():
        by_cell[(str(meta["family"]), str(meta["action"]))].append(key)
        if meta["action"] == "idle":
            idle_available[(str(meta["family"]), str(meta["reason"]))] += len(
                pool.by_signature[key]
            )
    idle_split = _solve_idle_split(
        {
            family: actions.get("idle", 0)
            for family, actions in normal_actions.items()
            if actions.get("idle", 0)
        },
        normal_reasons,
        dict(idle_available),
    )
    rows: list[dict[str, object]] = list(pair_rows)

    def draw(signatures: list[str], count: int, label: str) -> None:
        buckets = sorted(signatures, key=lambda key: (-len(pool.by_signature[key]), key))
        cursor = {key: 0 for key in buckets}
        selected = 0
        for depth in itertools.count(1):
            if selected == count:
                return
            progressed = False
            for key in buckets:
                if selected == count:
                    return
                index = cursor[key]
                while index < len(pool.by_signature[key]):
                    candidate = pool.by_signature[key][index]
                    cursor[key] += 1
                    index += 1
                    identity = (
                        str(candidate["stream_sha256"]),
                        int(candidate["call_index"]),
                    )
                    if identity not in selected_identities:
                        break
                else:
                    continue
                rows.append(
                    {
                        **pool.signature_meta[key],
                        **candidate,
                        "semantic_signature_id": "sig-" + sha256(key.encode()).hexdigest()[:16],
                        "timing_replica_depth": depth,
                    }
                )
                selected_identities.add(identity)
                selected += 1
                progressed = True
            if not progressed:
                available = sum(len(pool.by_signature[key]) for key in buckets)
                raise Wp210ReachabilityError(
                    f"selection shortfall for {label}: need {count}, have {available}"
                )

    for family, actions in normal_actions.items():
        for action, target in actions.items():
            if action == "idle":
                continue
            draw(by_cell[(family, action)], target, f"{family}|{action}")
    for (family, reason), target in sorted(idle_split.items()):
        if not target:
            continue
        draw(
            [
                key
                for key in by_cell[(family, "idle")]
                if pool.signature_meta[key]["reason"] == reason
            ],
            target,
            f"{family}|idle|{reason}",
        )
    rows.sort(
        key=lambda row: (
            str(row["family"]),
            str(row["action"]),
            str(row["reason"]),
            str(row["semantic_signature_id"]),
            str(row["timing_seed"]),
            str(row["stream_sha256"]),
            int(row["call_index"]),
        )
    )
    return {"rows": rows, "idle_split": idle_split}


def _preflight_idle_reason_capacity(
    pool: _CandidatePool,
    allocation: dict[str, object],
    preselected_rows: list[dict[str, object]],
) -> dict[str, object]:
    """Run the existing exact allocator before v3 packet assembly and assert all seven totals."""
    selected = _select_exact_400(pool, allocation, preselected_rows)
    rows = selected["rows"]
    idle_reason = allocation["idle_reason"]
    assert isinstance(rows, list)
    assert isinstance(idle_reason, dict)
    actual = collections.Counter(str(row["reason"]) for row in rows if row["action"] == "idle")
    if actual != collections.Counter(idle_reason):
        raise Wp210ReachabilityError("idle-reason preflight does not close all seven totals")
    return selected


def _foreign_timing_seed_ids(root: Path) -> dict[str, object]:
    ids: set[str] = set()
    packets = 0
    for path in sorted((root / "review").rglob("manifest.json")):
        try:
            payload = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        streams = payload.get("streams") if isinstance(payload, dict) else None
        if not isinstance(streams, list):
            continue
        packets += 1
        for stream in streams:
            if not isinstance(stream, dict) or stream.get("split") not in {"train", "dev", "demo"}:
                continue
            timing = stream.get("timing")
            if isinstance(timing, dict) and isinstance(timing.get("seed_id"), str):
                ids.add(timing["seed_id"])
    return {
        "manifest_packet_count": packets,
        "seed_ids": tuple(sorted(ids)),
        "seed_ids_sha256": "sha256:" + sha256(canonical_artifact_bytes(sorted(ids))).hexdigest(),
    }


def _validate_v2_witness(
    witness: dict[str, object],
    *,
    foreign_timing: dict[str, object],
    timing_namespace: str = V2_SEED_NAMESPACE,
    expected_human_pairs: int = 4,
) -> None:
    rows = witness["rows"]
    allocation = witness["allocation"]
    failed_pairs = witness["failed_response_pairs"]
    human_pairs = witness["human_response_pairs"]
    assert isinstance(rows, list)
    assert isinstance(allocation, dict)
    assert isinstance(failed_pairs, list)
    assert isinstance(human_pairs, list)
    cells = collections.Counter((row["family"], row["action"]) for row in rows)
    target_cells = {
        (family, action): count
        for family, actions in allocation["family_action"].items()
        for action, count in actions.items()
    }
    if len(rows) != TEST_STATE_TOTAL or cells != target_cells:
        raise Wp210ReachabilityError("rebuilt rows do not exactly match the 400-state allocation")
    identities = {(row["stream_sha256"], row["call_index"]) for row in rows}
    if len(identities) != TEST_STATE_TOTAL:
        raise Wp210ReachabilityError("rebuilt rows do not have 400 unique state identities")
    reasons = collections.Counter(row["reason"] for row in rows if row["action"] == "idle")
    if reasons != collections.Counter(allocation["idle_reason"]):
        raise Wp210ReachabilityError("rebuilt rows do not match idle-reason allocation")
    if sum(row["action"] == "respond" for row in rows) != TEST_RESPONSE_STATES:
        raise Wp210ReachabilityError("rebuilt rows do not have 18 respond states")
    if reasons["awaiting_opening"] != TEST_RESPONSE_STATES:
        raise Wp210ReachabilityError("rebuilt rows do not have 18 awaiting-opening states")
    _validate_response_floor_pairs(rows)
    failed = [row for row in rows if "failed_response_pair_id" in row]
    if len(failed_pairs) != 2 or len(failed) != 4:
        raise Wp210ReachabilityError(
            "rebuilt rows do not contain exactly two failed-response pairs"
        )
    if {pair["result_mode"] for pair in failed_pairs} != {"lookup_failed", "no_usable_data"}:
        raise Wp210ReachabilityError("failed-response result modes are not distinct")
    if collections.Counter(row["failed_response_pair_id"] for row in failed) != {
        pair["pair_id"]: 2 for pair in failed_pairs
    }:
        raise Wp210ReachabilityError("failed-response rows do not retain both members of each pair")
    for pair in failed_pairs:
        members = pair["members"]
        if (
            len(members) != 2
            or {member["action"] for member in members} != {"respond", "idle"}
            or next(member for member in members if member["action"] == "idle")["idle_reason"]
            != "awaiting_opening"
            or len({member["counterfactual_group_id"] for member in members}) != 1
        ):
            raise Wp210ReachabilityError("failed-response pair structure is incomplete")
    human_rows = [row for row in rows if "human_response_pair_id" in row]
    if len(human_pairs) != expected_human_pairs or len(human_rows) != 2 * expected_human_pairs:
        raise Wp210ReachabilityError("rebuilt rows do not retain every human response pair")
    if collections.Counter(row["human_response_pair_id"] for row in human_rows) != {
        pair["pair_id"]: 2 for pair in human_pairs
    }:
        raise Wp210ReachabilityError("human response pairs do not retain both floor members")
    if any(
        pair.get("content_authority") != "human_authored_owner_approved"
        or pair.get("owner_disposition") not in {"approved", "approved_replacement"}
        or pair.get("owner_review") not in (_OWNER_APPROVAL, _OWNER_REVIEW_RESPONSE)
        for pair in human_pairs
    ):
        raise Wp210ReachabilityError("human response approval evidence is incomplete")
    ordinary_pairs = [
        pair for pair in human_pairs if pair.get("pair_kind") == "ordinary_live_result"
    ]
    if {pair["pair_id"] for pair in ordinary_pairs} != {
        spec["pair_id"] for spec in _ORDINARY_LIVE_RESPONSE_SPECS
    }:
        raise Wp210ReachabilityError("ordinary live response pairs are incomplete")
    for pair in ordinary_pairs:
        contract = pair["answer_contract"]
        if (
            not isinstance(contract, dict)
            or tuple(contract.get("support_event_ids", ()))
            != (_LIVE_RESULT_QUERY_EVENT_ID, _LIVE_RESULT_EVENT_ID)
            or FAILED_RESULT_EVENT_ID in contract.get("support_event_ids", ())
        ):
            raise Wp210ReachabilityError("ordinary response pair lost succeeded-result support")
    selected_seed_ids = {str(row["timing_seed_id"]) for row in rows}
    foreign_ids = set(foreign_timing["seed_ids"])
    if selected_seed_ids & foreign_ids:
        raise Wp210ReachabilityError("TEST timing seed identity overlaps TRAIN/DEV/DEMO")
    if not all(str(row["timing_seed"]).startswith(timing_namespace) for row in rows):
        raise Wp210ReachabilityError("rebuilt rows escaped the WP2-10 TEST timing namespace")


def _runtime_evidence_files(
    rows: list[dict[str, object]],
    parents: dict[str, GeneratedScenario],
    human_pairs: list[dict[str, object]],
) -> tuple[dict[str, bytes], bytes]:
    files: dict[str, bytes] = {}
    evidence_rows = []
    human_by_id = {str(pair["pair_id"]): pair for pair in human_pairs}
    for row in rows:
        stream_hash = str(row["stream_sha256"])
        generated = parents[stream_hash]
        stream_dir = stream_hash.removeprefix("sha256:")
        for segment in generated.stream.segments:
            files[f"teacher/{stream_dir}/{segment.sha256.removeprefix('sha256:')}.jsonl"] = (
                segment.policy_bytes
            )
        files[f"reviewer/{stream_dir}/sidecar.json"] = generated.sidecar.canonical_bytes
        files[f"reviewer/{stream_dir}/runtime-ledger.json"] = (
            generated.stream.final_ledger.canonical_bytes
        )
        call_index = int(row["call_index"])
        decision = generated.sidecar.decisions[call_index - 1]
        captured = generated.stream.decisions[call_index - 1]
        if decision.action.type != row["action"]:
            raise Wp210ReachabilityError("selected row action disagrees with its sidecar")
        evidence = {
            "state_identity": {
                "stream_sha256": stream_hash,
                "call_index": call_index,
            },
            "selection": row,
            "oracle_action": decision.action.model_dump(mode="json"),
            "sidecar_decision": decision.as_json_object(),
            "policy_prefix_utf8": captured.prefix_bytes.decode("utf-8"),
            "policy_prefix_sha256": "sha256:" + sha256(captured.prefix_bytes).hexdigest(),
            "action_attempt_audit": json.loads(captured.audit_bytes.decode("utf-8")),
            "teacher_segment_paths": sorted(
                f"teacher/{stream_dir}/{segment.sha256.removeprefix('sha256:')}.jsonl"
                for segment in generated.stream.segments
            ),
            "sidecar_path": f"reviewer/{stream_dir}/sidecar.json",
            "runtime_ledger_path": f"reviewer/{stream_dir}/runtime-ledger.json",
        }
        if response_id := row.get("human_response_pair_id"):
            pair = human_by_id[str(response_id)]
            evidence["human_authored_response"] = {
                "pair_id": pair["pair_id"],
                "pair_kind": pair["pair_kind"],
                "content_authority": pair["content_authority"],
                "owner_disposition": pair["owner_disposition"],
                "owner_review": pair["owner_review"],
                "invitation": pair["invitation"],
                "response_text": pair["response_text"],
                "response_text_sha256": pair["response_text_sha256"],
                "teacher_visible_prefix_sha256": pair["teacher_visible_prefix_sha256"],
                "split": "test",
                "counterfactual_group_id": row["counterfactual_group_id"],
                "member": next(
                    member["member"]
                    for member in pair["members"]
                    if member["stream_sha256"] == stream_hash and member["call_index"] == call_index
                ),
            }
        evidence_rows.append(evidence)
    return files, b"".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode() + b"\n"
        for row in evidence_rows
    )


def _load_owner_review_progress(root: Path) -> tuple[dict[str, object], str]:
    path = root / OWNER_REVIEW_PROGRESS.relative_to(_ROOT)
    try:
        source = path.read_bytes()
        progress = json.loads(source)
    except (OSError, json.JSONDecodeError) as error:
        raise Wp210ReachabilityError("owner review progress is unavailable or malformed") from error
    if not isinstance(progress, dict):
        raise Wp210ReachabilityError("owner review progress must be an object")
    summary = progress.get("review_summary")
    expected_summary = {
        "reviewed_decisions": 400,
        "approved": 342,
        "rejected_rebuild": 42,
        "rejected_relabel": 16,
        "open_decisions": 0,
    }
    if (
        progress.get("format_version") != 1
        or progress.get("kind") != "wp2-10-test-owner-review-progress"
        or progress.get("status") != "owner_review_complete_rebuild_required"
        or progress.get("source_packet") != "review/phase2/wp2-10-test-400-candidate-v2"
        or summary != expected_summary
    ):
        raise Wp210ReachabilityError("owner review progress does not close the v2 review")
    v2_sums = root / "review/phase2/wp2-10-test-400-candidate-v2/SHA256SUMS"
    source_digest = "sha256:" + sha256(v2_sums.read_bytes()).hexdigest()
    if progress.get("source_sha256sums_sha256") != source_digest:
        raise Wp210ReachabilityError("owner review progress is not bound to the v2 candidate")
    return progress, "sha256:" + sha256(source).hexdigest()


def _validate_v3_owner_repairs(
    witness: dict[str, object],
    *,
    parents: dict[str, GeneratedScenario],
    ambiguity_records: list[dict[str, object]],
    relabel_records: list[dict[str, object]],
) -> None:
    rows = witness["rows"]
    human_pairs = witness["human_response_pairs"]
    assert isinstance(rows, list)
    assert isinstance(human_pairs, list)
    ambiguity_rows = [row for row in rows if "owner_ambiguity_replacement_id" in row]
    if len(ambiguity_rows) != len(_AMBIGUITY_REPLACEMENT_SPECS) or any(
        row["action"] != "idle" or row["reason"] != "ambiguous" for row in ambiguity_rows
    ):
        raise Wp210ReachabilityError("owner-rejected ambiguity rows were not rebuilt")
    if len(ambiguity_records) != len(_AMBIGUITY_REPLACEMENT_SPECS):
        raise Wp210ReachabilityError("owner ambiguity replacement evidence is incomplete")
    for record in ambiguity_records:
        members = record["members"]
        assert isinstance(members, list)
        active = next(member for member in members if member["member"] == "active")
        prefix = (
            parents[str(active["stream_sha256"])]
            .stream.decisions[int(active["call_index"]) - 1]
            .prefix_bytes.decode("utf-8")
        )
        if str(record["invitation"]) not in prefix:
            raise Wp210ReachabilityError("ambiguity rebuild did not retain its natural request")
    calendar = [
        pair for pair in human_pairs if pair.get("pair_kind") == "owner_replaced_calendar_response"
    ]
    if len(calendar) != 1 or calendar[0].get("response_text") != _OWNER_APPROVED_CALENDAR_RESPONSE:
        raise Wp210ReachabilityError("owner-approved calendar response was not retained exactly")
    relabel_rows = [row for row in rows if "owner_relabelled_bare_phrase" in row]
    if len(relabel_rows) != 16 or any(
        row["action"] != "idle" or row["reason"] != "no_trigger" for row in relabel_rows
    ):
        raise Wp210ReachabilityError("bare phrase relabel coverage is incomplete")
    if len(relabel_records) != 16:
        raise Wp210ReachabilityError("bare phrase relabel evidence is incomplete")
    source_safe = [row for row in rows if "source_safe_replacement" in row]
    if len(source_safe) != 4 or any(
        row["action"] != "idle" or row["reason"] != "awaiting_tool" for row in source_safe
    ):
        raise Wp210ReachabilityError("stale pending-state replacements are incomplete")
    if any(
        row["shape_id"] == "g7-checkpoint-lookup-stale" and row["call_index"] in {6, 8, 9, 13}
        for row in rows
    ):
        raise Wp210ReachabilityError("v3 retained a rejected stale checkpoint decision")
    malformed = {
        "Could you clarify the missing recipe name for the ingredient lookup?",
        "Could you clarify the missing station name for the departure lookup?",
        "Could you clarify the missing edition for the book lookup?",
    }
    selected_prefixes = {
        parents[str(row["stream_sha256"])]
        .stream.decisions[int(row["call_index"]) - 1]
        .prefix_bytes.decode("utf-8")
        for row in rows
    }
    if any(text in prefix for prefix in selected_prefixes for text in malformed):
        raise Wp210ReachabilityError("v3 still depends on a malformed ambiguity request")


async def build_v2_candidate_packet(*, repository_root: Path = _ROOT) -> dict[str, bytes]:
    """Rebuild and verify the amended TEST-400 owner-review candidate in memory."""
    root = repository_root.resolve()
    registry = _load_sealed_registry(DEFAULT_APPROVED_ROOT)
    with TemporaryDirectory(prefix="wp2-10-test-400-v2-") as temporary:
        pool = await _collect_regular_candidates(registry, root=root, work=Path(temporary))
        failed_rows, failed_pairs = await _failed_response_pairs(
            registry, root=root, work=Path(temporary), pool=pool
        )
        ordinary_rows, ordinary_pairs = await _ordinary_live_response_pairs(
            registry, root=root, work=Path(temporary), pool=pool
        )
        human_rows = [*failed_rows, *ordinary_rows]
        human_pairs = [*failed_pairs, *ordinary_pairs]
        allocation = build_test_allocation()
        selected = _select_exact_400(pool, allocation, human_rows)
        rows = selected["rows"]
        assert isinstance(rows, list)
        foreign_timing = _foreign_timing_seed_ids(root)
        witness: dict[str, object] = {
            "allocation": allocation,
            "rows": rows,
            "failed_response_pairs": failed_pairs,
            "human_response_pairs": human_pairs,
        }
        _validate_v2_witness(witness, foreign_timing=foreign_timing)
        runtime_files, selected_evidence = _runtime_evidence_files(rows, pool.parents, human_pairs)

    depths = collections.Counter(int(row["timing_replica_depth"]) for row in rows)
    plan_ids = {str(row["timing_plan_identity"]) for row in rows}
    signature_ids = {str(row["semantic_signature_id"]) for row in rows}
    v1_sums = CANDIDATE_OUTPUT / "SHA256SUMS"
    summary = {
        "format_version": 2,
        "kind": "phase2-wp2-10-test-400-review-candidate",
        "status": "candidate_for_owner_review_not_sealed",
        "supersedes": {
            "path": str(CANDIDATE_OUTPUT.relative_to(_ROOT)),
            "sha256": "sha256:" + sha256(v1_sums.read_bytes()).hexdigest(),
        },
        "governing_inputs": governing_input_digests(),
        "allocation": allocation,
        "row_count": len(rows),
        "unique_state_identities": len({(row["stream_sha256"], row["call_index"]) for row in rows}),
        "unique_semantic_signatures_used": len(signature_ids),
        "max_timing_replica_depth": max(depths),
        "replica_depth_counts": dict(sorted(depths.items())),
        "ten_replica_signatures": [
            {
                "semantic_signature_id": row["semantic_signature_id"],
                "cell": f"{row['family']}|{row['action']}",
                "reason": row["reason"],
                "builder": row["builder"],
                "shape_id": row["shape_id"],
            }
            for row in rows
            if row["timing_replica_depth"] == 10
        ],
        "distinct_timing_plan_identities": len(plan_ids),
        "timing_seed_namespace": V2_SEED_NAMESPACE,
        "timing_disjointness": {
            "selected_seed_id_count": len({row["timing_seed_id"] for row in rows}),
            "foreign": {key: value for key, value in foreign_timing.items() if key != "seed_ids"},
            "overlap_count": 0,
        },
        "asset_concentration": dict(
            collections.Counter(asset for row in rows for asset in row["asset_ids"]).most_common()
        ),
        "template_concentration": dict(
            collections.Counter(
                row["template_id"] for row in rows if row["template_id"]
            ).most_common()
        ),
        "builders": dict(collections.Counter(row["builder"] for row in rows)),
        "failed_response_pairs": 2,
        "failed_response_rows": 4,
        "human_authored_response_pairs": 4,
        "human_authored_response_rows": 8,
        "human_response_owner_approvals": 4,
        "complete_response_floor_pairs": TEST_RESPONSE_STATES,
        "historical_failed_response_rows": 0,
        "review_evidence": {
            "selected_state_evidence": "selected-evidence.jsonl",
            "human_authored_response_pairs": "human-authored-response-pairs.json",
            "policy_prefixes": "embedded per selected identity",
            "runtime_streams": "teacher/ and reviewer/",
        },
    }
    files = {
        "review-candidate.json": canonical_artifact_bytes(summary),
        "selected-states.jsonl": b"".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
            + b"\n"
            for row in rows
        ),
        "selected-evidence.jsonl": selected_evidence,
        "failed-response-pairs.json": canonical_artifact_bytes(
            {
                "format_version": 1,
                "kind": "wp2-10-human-authored-failed-response-candidates",
                "owner_approval_recorded": True,
                "records": failed_pairs,
            }
        ),
        "human-authored-response-pairs.json": canonical_artifact_bytes(
            {
                "format_version": 1,
                "kind": "wp2-10-human-authored-response-pairs",
                "owner_approval_recorded": True,
                "records": human_pairs,
            }
        ),
        **runtime_files,
    }
    files["SHA256SUMS"] = "".join(
        f"{sha256(payload).hexdigest()}  {path}\n" for path, payload in sorted(files.items())
    ).encode()
    return files


async def materialize_v2_candidate_packet(
    output: Path = CANDIDATE_V2_OUTPUT, *, repository_root: Path = _ROOT
) -> dict[str, bytes]:
    """Atomically replace only the known v2 candidate; never issue an evaluation seal."""
    files = await build_v2_candidate_packet(repository_root=repository_root)
    expected_before = frozenset(directory_bytes(output)) if output.exists() else None
    publish_directory_transaction(output, files, expected_before=expected_before)
    return files


async def build_v3_candidate_packet(*, repository_root: Path = _ROOT) -> dict[str, bytes]:
    """Rebuild the owner-complete v3 TEST-400 candidate without issuing a seal."""
    root = repository_root.resolve()
    owner_progress, owner_progress_digest = _load_owner_review_progress(root)
    registry = _load_sealed_registry(DEFAULT_APPROVED_ROOT)
    excluded_response_items = frozenset(
        {
            *(("g7-response-floor-ambiguity-lookup-live", index) for index in (3, 4, 5)),
            ("g7-response-floor-lookup-stale-mixed", 5),
        }
    )
    with TemporaryDirectory(prefix="wp2-10-test-400-v3-") as temporary:
        pool = await _collect_regular_candidates(
            registry,
            root=root,
            work=Path(temporary),
            seed_namespace=V3_SEED_NAMESPACE,
            explicit_lookup_requests=True,
            exclude_response_items=excluded_response_items,
        )
        rejected_stale_calls = {6, 8, 9, 13}
        for key, bucket in tuple(pool.by_signature.items()):
            kept = [
                row
                for row in bucket
                if not (
                    row["shape_id"] == "g7-checkpoint-lookup-stale"
                    and row["call_index"] in rejected_stale_calls
                )
            ]
            if kept:
                pool.by_signature[key] = kept
            else:
                del pool.by_signature[key]
                del pool.signature_meta[key]
        failed_rows, failed_pairs = await _failed_response_pairs(
            registry,
            root=root,
            work=Path(temporary),
            pool=pool,
            seed_namespace=V3_SEED_NAMESPACE,
        )
        ordinary_rows, ordinary_pairs = await _ordinary_live_response_pairs(
            registry,
            root=root,
            work=Path(temporary),
            pool=pool,
            seed_namespace=V3_SEED_NAMESPACE,
        )
        ambiguity_rows, ambiguity_records = await _ambiguity_replacement_rows(
            registry,
            root=root,
            work=Path(temporary),
            pool=pool,
            seed_namespace=V3_SEED_NAMESPACE,
        )
        calendar_rows, calendar_pair = await _calendar_response_replacement_pair(
            registry,
            root=root,
            work=Path(temporary),
            pool=pool,
            seed_namespace=V3_SEED_NAMESPACE,
        )
        relabel_rows, relabel_records = await _relabelled_bare_phrase_rows(
            root=root,
            work=Path(temporary),
            pool=pool,
            seed_namespace=V3_SEED_NAMESPACE,
        )
        stale_idle_rows, stale_idle_records = await _source_safe_stale_idle_rows(
            root=root,
            work=Path(temporary),
            pool=pool,
            seed_namespace=V3_SEED_NAMESPACE,
        )
        human_rows = [*failed_rows, *ordinary_rows, *calendar_rows]
        human_pairs = [*failed_pairs, *ordinary_pairs, calendar_pair]
        allocation = build_test_allocation()
        selected = _preflight_idle_reason_capacity(
            pool,
            allocation,
            [*human_rows, *ambiguity_rows, *relabel_rows, *stale_idle_rows],
        )
        rows = selected["rows"]
        assert isinstance(rows, list)
        foreign_timing = _foreign_timing_seed_ids(root)
        witness: dict[str, object] = {
            "allocation": allocation,
            "rows": rows,
            "failed_response_pairs": failed_pairs,
            "human_response_pairs": human_pairs,
        }
        _validate_v2_witness(
            witness,
            foreign_timing=foreign_timing,
            timing_namespace=V3_SEED_NAMESPACE,
            expected_human_pairs=5,
        )
        _validate_v3_owner_repairs(
            witness,
            parents=pool.parents,
            ambiguity_records=ambiguity_records,
            relabel_records=relabel_records,
        )
        runtime_files, selected_evidence = _runtime_evidence_files(rows, pool.parents, human_pairs)

    depths = collections.Counter(int(row["timing_replica_depth"]) for row in rows)
    plan_ids = {str(row["timing_plan_identity"]) for row in rows}
    signature_ids = {str(row["semantic_signature_id"]) for row in rows}
    v2_sums = root / "review/phase2/wp2-10-test-400-candidate-v2/SHA256SUMS"
    review_binding = {
        "path": "review/phase2/wp2-10-owner-review-progress.json",
        "sha256": owner_progress_digest,
        "source_packet": owner_progress["source_packet"],
        "source_sha256sums_sha256": owner_progress["source_sha256sums_sha256"],
        "status": owner_progress["status"],
        "review_summary": owner_progress["review_summary"],
    }
    closeout = {
        "format_version": 1,
        "kind": "wp2-10-test-owner-review-closeout",
        "status": "owner_review_complete_v3_candidate_not_sealed",
        "owner_review_progress": review_binding,
        "dispositions_before_rebuild": owner_progress["review_summary"],
        "dispositions_after_rebuild": {
            "approved_carried_under_the_same_allocation": 342,
            "rejected_rebuild_replaced": 42,
            "rejected_relabel_preserved_as_idle_no_trigger": 16,
            "open_decisions": 0,
        },
        "repair_counts": {
            "natural_explicit_request_paths": {
                "fresh_delegate_integrate_awaiting": 15,
                "rollover_delegate_integrate_awaiting_no_trigger": 7,
            },
            "excluded_malformed_checkpoint_descendants": 4,
            "source_safe_stale_replacements": {
                "awaiting_tool": 4,
            },
            "natural_incomplete_clarification_requests": 3,
            "owner_exact_calendar_response_pairs": 1,
            "bare_phrase_idle_no_trigger_rows": 16,
        },
        "selection_adjustment": {
            "kind": "quota_neutral_substitution",
            "removed": {
                "redundant_neutral_no_trigger_rows": 16,
                "malformed_stale_checkpoint_descendants": 4,
                "rejected_calendar_floor_pair": 1,
                "malformed_ambiguity_active_rows": 3,
            },
            "added": {
                "owner_relabelled_bare_phrase_no_trigger_rows": 16,
                "owner_calendar_floor_pair": 1,
                "natural_ambiguity_active_rows": 3,
                "source_safe_stale_replacements": len(stale_idle_records),
            },
            "family_action_allocation_changed": False,
            "idle_reason_allocation_changed": False,
        },
        "allocation": allocation,
        "row_count": len(rows),
        "unique_state_identities": len({(row["stream_sha256"], row["call_index"]) for row in rows}),
        "evaluation_seal": "not_issued",
    }
    summary = {
        "format_version": 3,
        "kind": "phase2-wp2-10-test-400-review-candidate",
        "status": "owner_review_complete_v3_candidate_not_sealed",
        "supersedes": {
            "path": "review/phase2/wp2-10-test-400-candidate-v2",
            "sha256": "sha256:" + sha256(v2_sums.read_bytes()).hexdigest(),
        },
        "owner_review_progress": review_binding,
        "governing_inputs": governing_input_digests(),
        "allocation": allocation,
        "row_count": len(rows),
        "unique_state_identities": len({(row["stream_sha256"], row["call_index"]) for row in rows}),
        "unique_semantic_signatures_used": len(signature_ids),
        "max_timing_replica_depth": max(depths),
        "replica_depth_counts": dict(sorted(depths.items())),
        "distinct_timing_plan_identities": len(plan_ids),
        "timing_seed_namespace": V3_SEED_NAMESPACE,
        "timing_disjointness": {
            "selected_seed_id_count": len({row["timing_seed_id"] for row in rows}),
            "foreign": {key: value for key, value in foreign_timing.items() if key != "seed_ids"},
            "overlap_count": 0,
        },
        "asset_concentration": dict(
            collections.Counter(asset for row in rows for asset in row["asset_ids"]).most_common()
        ),
        "template_concentration": dict(
            collections.Counter(
                row["template_id"] for row in rows if row["template_id"]
            ).most_common()
        ),
        "builders": dict(collections.Counter(row["builder"] for row in rows)),
        "failed_response_pairs": 2,
        "failed_response_rows": 4,
        "human_authored_response_pairs": 5,
        "human_authored_response_rows": 10,
        "complete_response_floor_pairs": TEST_RESPONSE_STATES,
        "owner_rebuilt_ambiguity_rows": 3,
        "owner_relabelled_bare_phrase_rows": 16,
        "source_safe_stale_replacements": {
            "awaiting_tool": 4,
        },
        "historical_failed_response_rows": 0,
        "evaluation_seal": "not_issued",
        "review_evidence": {
            "selected_state_evidence": "selected-evidence.jsonl",
            "owner_review_closeout": "owner-review-closeout.json",
            "human_authored_response_pairs": "human-authored-response-pairs.json",
            "owner_ambiguity_replacements": "owner-ambiguity-replacements.json",
            "owner_relabelled-bare-phrases": "owner-relabelled-bare-phrases.json",
            "source_safe_stale_idle_replacements": "source-safe-stale-idle-replacements.json",
            "policy_prefixes": "embedded per selected identity",
            "runtime_streams": "teacher/ and reviewer/",
        },
    }
    files = {
        "review-candidate.json": canonical_artifact_bytes(summary),
        "owner-review-closeout.json": canonical_artifact_bytes(closeout),
        "selected-states.jsonl": b"".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
            + b"\n"
            for row in rows
        ),
        "selected-evidence.jsonl": selected_evidence,
        "failed-response-pairs.json": canonical_artifact_bytes(
            {
                "format_version": 1,
                "kind": "wp2-10-human-authored-failed-response-candidates",
                "owner_approval_recorded": True,
                "records": failed_pairs,
            }
        ),
        "human-authored-response-pairs.json": canonical_artifact_bytes(
            {
                "format_version": 1,
                "kind": "wp2-10-human-authored-response-pairs",
                "owner_approval_recorded": True,
                "records": human_pairs,
            }
        ),
        "owner-ambiguity-replacements.json": canonical_artifact_bytes(
            {"format_version": 1, "records": ambiguity_records}
        ),
        "owner-relabelled-bare-phrases.json": canonical_artifact_bytes(
            {
                "format_version": 1,
                "selection_adjustment": "replaced 16 redundant neutral no_trigger rows",
                "records": relabel_records,
            }
        ),
        "source-safe-stale-idle-replacements.json": canonical_artifact_bytes(
            {"format_version": 1, "records": stale_idle_records}
        ),
        **runtime_files,
    }
    files["SHA256SUMS"] = "".join(
        f"{sha256(payload).hexdigest()}  {path}\n" for path, payload in sorted(files.items())
    ).encode()
    return files


async def materialize_v3_candidate_packet(
    output: Path = CANDIDATE_V3_OUTPUT, *, repository_root: Path = _ROOT
) -> dict[str, bytes]:
    """Create the v3 review candidate without overwriting any prior candidate packet."""
    if output.exists():
        raise Wp210ReachabilityError("v3 candidate output already exists; refusing replacement")
    files = await build_v3_candidate_packet(repository_root=repository_root)
    publish_directory_transaction(output, files)
    return files


def _verified_packet_files(directory: Path) -> dict[str, bytes]:
    """Read one closed checksum-bound packet without trusting undeclared files."""
    files = directory_bytes(directory)
    manifest = files.get("SHA256SUMS")
    if manifest is None:
        raise Wp210ReachabilityError("candidate packet has no SHA256SUMS")
    try:
        rows = manifest.decode("ascii").splitlines()
    except UnicodeDecodeError as error:
        raise Wp210ReachabilityError("candidate SHA256SUMS is not ASCII") from error
    declared: dict[str, str] = {}
    for line in rows:
        digest, separator, name = line.partition("  ")
        if (
            not separator
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
            or name == "SHA256SUMS"
            or name in declared
            or name not in files
        ):
            raise Wp210ReachabilityError("candidate SHA256SUMS has an invalid entry")
        declared[name] = digest
    actual = {
        name: sha256(payload).hexdigest() for name, payload in files.items() if name != "SHA256SUMS"
    }
    if declared != actual:
        raise Wp210ReachabilityError("candidate SHA256SUMS does not bind its exact inventory")
    return files


def build_test_closeout_packet(*, repository_root: Path = _ROOT) -> dict[str, bytes]:
    """Bind the owner-approved TEST-400 packet and issue its final evaluation seal."""
    root = repository_root.resolve()
    candidate = root / CANDIDATE_V3_OUTPUT.relative_to(_ROOT)
    approved = root / DEFAULT_APPROVED_ROOT.relative_to(_ROOT)
    source_files = _verified_packet_files(candidate)
    summary = json.loads(source_files["review-candidate.json"])
    owner_closeout = json.loads(source_files["owner-review-closeout.json"])
    rows = [json.loads(line) for line in source_files["selected-states.jsonl"].splitlines()]
    evidence = [json.loads(line) for line in source_files["selected-evidence.jsonl"].splitlines()]

    if summary.get("status") != "owner_review_complete_v3_candidate_not_sealed":
        raise Wp210ReachabilityError("candidate is not owner-review complete")
    if owner_closeout.get("status") != "owner_review_complete_v3_candidate_not_sealed":
        raise Wp210ReachabilityError("owner closeout is not complete")
    if len(rows) != TEST_STATE_TOTAL or len(evidence) != TEST_STATE_TOTAL:
        raise Wp210ReachabilityError("candidate does not contain 400 states and evidence rows")
    identities = {(row["stream_sha256"], row["call_index"]) for row in rows}
    evidence_identities = {
        (row["state_identity"]["stream_sha256"], row["state_identity"]["call_index"])
        for row in evidence
    }
    if len(identities) != TEST_STATE_TOTAL or identities != evidence_identities:
        raise Wp210ReachabilityError("selected states and evidence do not bind 400 identities")

    allocation = summary["allocation"]
    actions = collections.Counter(row["action"] for row in rows)
    reasons = collections.Counter(row["reason"] for row in rows if row["action"] == "idle")
    family_actions = collections.Counter((row["family"], row["action"]) for row in rows)
    expected_family_actions = {
        (family, action): count
        for family, family_counts in allocation["family_action"].items()
        for action, count in family_counts.items()
    }
    if (
        actions != collections.Counter(allocation["action_totals"])
        or reasons != collections.Counter(allocation["idle_reason"])
        or family_actions != collections.Counter(expected_family_actions)
    ):
        raise Wp210ReachabilityError("candidate no longer matches its frozen allocation")
    _validate_response_floor_pairs(rows)

    dispositions = owner_closeout["dispositions_after_rebuild"]
    if dispositions != {
        "approved_carried_under_the_same_allocation": 342,
        "rejected_rebuild_replaced": 42,
        "rejected_relabel_preserved_as_idle_no_trigger": 16,
        "open_decisions": 0,
    }:
        raise Wp210ReachabilityError("owner dispositions drifted")

    registry = _load_sealed_registry(approved)
    validation = validate_registry(registry)
    if validation.errors or validation.review_flags:
        raise Wp210ReachabilityError("approved registry no longer passes split validation")
    seals = {
        split: load_split_seal_json((approved / f"{split}-seal.json").read_bytes())
        for split in ("train", "dev", "test", "demo")
    }
    seal_ids = {split: {entry.asset_id for entry in seal.entries} for split, seal in seals.items()}
    selected_asset_ids = {asset_id for row in rows for asset_id in row["asset_ids"]} | {
        row["template_id"] for row in rows if row["template_id"] is not None
    }
    if selected_asset_ids != seal_ids["test"]:
        raise Wp210ReachabilityError("selected TEST material does not equal the sealed TEST pool")
    foreign_asset_overlap = selected_asset_ids.intersection(
        seal_ids["train"] | seal_ids["dev"] | seal_ids["demo"]
    )
    if foreign_asset_overlap:
        raise Wp210ReachabilityError("selected TEST material overlaps another split")

    selected_timing_ids = {row["timing_seed_id"] for row in rows}
    foreign_timing = _foreign_timing_seed_ids(root)
    timing_overlap = selected_timing_ids.intersection(foreign_timing["seed_ids"])
    if timing_overlap or any(
        not str(row["timing_seed"]).startswith(f"{V3_SEED_NAMESPACE}:") for row in rows
    ):
        raise Wp210ReachabilityError("TEST timing seeds overlap another split")

    governing = governing_input_digests(approved)
    if summary["governing_inputs"] != governing:
        raise Wp210ReachabilityError("governing registry or seal digest drifted")
    candidate_manifest_digest = "sha256:" + sha256(source_files["SHA256SUMS"]).hexdigest()
    disjointness = {
        "format_version": 1,
        "kind": "wp2-10-final-split-disjointness-ledger",
        "split": "test",
        "governing_inputs": governing,
        "selected_test_material": {
            "asset_and_template_count": len(selected_asset_ids),
            "equals_test_seal": True,
            "train_overlap": 0,
            "dev_overlap": 0,
            "demo_overlap": 0,
        },
        "timing": {
            "namespace": V3_SEED_NAMESPACE,
            "selected_seed_id_count": len(selected_timing_ids),
            "foreign_seed_id_count": len(foreign_timing["seed_ids"]),
            "overlap_count": 0,
            "foreign_seed_ids_sha256": foreign_timing["seed_ids_sha256"],
        },
        "lexical_material": {
            "validator": "im.assets.validate.validate_registry",
            "dimensions": ["assets", "templates", "protected_facts", "messages"],
            "errors": 0,
            "review_flags": 0,
        },
        "demo_material": {
            "demo_seal_entry_count": len(seal_ids["demo"]),
            "selected_test_overlap": 0,
        },
    }
    disjointness_bytes = canonical_artifact_bytes(disjointness)
    seal = {
        "format_version": 1,
        "kind": "wp2-10-test-evaluation-seal",
        "status": "frozen",
        "split": "test",
        "frozen_on": "2026-07-31",
        "packet": {
            "path": "review/phase2/wp2-10-test-400-candidate-v3",
            "sha256sums_sha256": candidate_manifest_digest,
            "selected_states_sha256": "sha256:"
            + sha256(source_files["selected-states.jsonl"]).hexdigest(),
            "selected_evidence_sha256": "sha256:"
            + sha256(source_files["selected-evidence.jsonl"]).hexdigest(),
            "decision_count": TEST_STATE_TOTAL,
            "stream_count": len({row["stream_sha256"] for row in rows}),
            "family_count": len({row["family"] for row in rows}),
            "response_floor_pair_count": TEST_RESPONSE_STATES,
        },
        "owner_review": {
            "reviewed_decision_count": TEST_STATE_TOTAL,
            "approved_carried": 342,
            "approved_rebuilt": 42,
            "approved_relabelled": 16,
            "open_decisions": 0,
            "closeout_sha256": "sha256:"
            + sha256(source_files["owner-review-closeout.json"]).hexdigest(),
        },
        "disjointness_ledger_sha256": "sha256:" + sha256(disjointness_bytes).hexdigest(),
        "checks": {
            "all_states_owner_reviewed": True,
            "exact_allocation": True,
            "unique_state_identities": True,
            "packet_checksums_verified": True,
            "split_disjointness_verified": True,
            "open_label_or_wording_defects": 0,
        },
        "teacher_or_provider_calls": 0,
        "immutability": "Final hidden TEST evaluation artifact; no post-seal mutation is allowed.",
    }
    readme = b"""# WP2-10 TEST evaluation closeout

WP2-10 is closed. The checksum-bound 400-decision TEST packet at
`review/phase2/wp2-10-test-400-candidate-v3` is the final hidden evaluation set.

All 400 decisions received owner semantic review. The final packet preserves the exact frozen
family/action and idle-reason allocation, contains 400 unique state identities, and passes the
recorded split-disjointness checks. No teacher or provider call was used for TEST gold.

`TEST-EVALUATION-SEAL.json` is final: later work may read it but must not mutate or regenerate it.
"""
    files = {
        "TEST-EVALUATION-SEAL.json": canonical_artifact_bytes(seal),
        "disjointness-ledger.json": disjointness_bytes,
        "README.md": readme,
    }
    files["SHA256SUMS"] = "".join(
        f"{sha256(payload).hexdigest()}  {name}\n" for name, payload in sorted(files.items())
    ).encode()
    return files


def materialize_test_closeout(
    output: Path = TEST_CLOSEOUT_OUTPUT, *, repository_root: Path = _ROOT
) -> dict[str, bytes]:
    """Publish the final TEST seal once; an existing closeout is immutable."""
    if output.exists():
        raise Wp210ReachabilityError("TEST closeout already exists; refusing replacement")
    files = build_test_closeout_packet(repository_root=repository_root)
    publish_directory_transaction(output, files)
    return files
