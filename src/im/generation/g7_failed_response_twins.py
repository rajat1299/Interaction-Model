"""Later checkpoint twins for one failed lookup-result response."""

from __future__ import annotations

from dataclasses import dataclass

from im.assets.model import (
    AssetRecord,
    CorpusFamily,
    LookupAssetPayload,
    Split,
    TextAssetPayload,
    TimerAssetPayload,
    artifact_digest,
)
from im.assets.registry import AssetBundle, AssetRegistry
from im.canonical_json import canonicalize_tim_json, parse_tim_json
from im.config import RuntimeConfig
from im.generation.g7_checkpoint_context import build_checkpoint_working_document
from im.generation.g7_need_plan import G7NeedPlan, build_g7_need_evidence
from im.generation.ingestion import ScheduledSamplerFrame
from im.generation.need_lineage import NeedBasisKind, NeedStatus
from im.generation.oracle import BeatOpening, BeatResponseWarrant, ResponseWarrantKind
from im.generation.response_contracts import (
    AnswerContract,
    ResponseKind,
    validate_response_text,
)
from im.generation.scenarios import (
    BeatStaleResults,
    CounterfactualDeclaration,
    DeclaredPerturbation,
    ScenarioProgram,
    select_approved_scenario_inputs,
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
from im.schema.common import ToolName, ToolResultStatus
from im.schema.textspan import utf16_len
from im.tools import ScriptedToolResult

__all__ = (
    "FAILED_QUERY_EVENT_ID",
    "FAILED_RESPONSE_SHAPE_ID",
    "FAILED_RESULT_EVENT_ID",
    "FailedResponseTwinPrograms",
    "build_g7_failed_response_twin_programs",
)


_CHECKPOINT_SEGMENT_INDEX = 1
_SUFFIX_CALL_INDICES = (7, 8, 9, 10, 11, 12, 13)
_SUFFIX_ACTION_TYPES = (
    IdleAction,
    DelegateAction,
    DelegateAction,
    IdleAction,
    IntegrateAction,
    IntegrateAction,
)
FAILED_RESULT_EVENT_ID = "e_000008"
FAILED_QUERY_EVENT_ID = "e_000005"
_FINAL_INVITATION_EVENT_ID = "e_000022"
FAILED_RESPONSE_SHAPE_ID = "g7-checkpoint-lookup-live-failed-response"
_PRELUDE_COUNT = 3
_FRAME_GAP_MS = 5_000
_ROLLOVER_CONFIG = RuntimeConfig(context_budget_tokens=6_000)


@dataclass(frozen=True, slots=True)
class FailedResponseTwinPrograms:
    """Yielded-first programs plus the metadata needed to select both suffixes."""

    programs: tuple[ScenarioProgram, ScenarioProgram]
    candidate_shape_ids: tuple[str, str]
    checkpoint_segment_index: int = _CHECKPOINT_SEGMENT_INDEX
    selected_call_indices: tuple[int, ...] = _SUFFIX_CALL_INDICES
    failed_result_event_id: str = FAILED_RESULT_EVENT_ID

    def __post_init__(self) -> None:
        yielded, active = self.programs
        if (
            self.checkpoint_segment_index != _CHECKPOINT_SEGMENT_INDEX
            or self.selected_call_indices != _SUFFIX_CALL_INDICES
            or self.failed_result_event_id != FAILED_RESULT_EVENT_ID
            or yielded.actions[:-1] != active.actions[:-1]
            or yielded.frames[:-1] != active.frames[:-1]
            or yielded.response_warrants_by_beat != active.response_warrants_by_beat
            or tuple(type(action) for action in yielded.actions[6:-1]) != _SUFFIX_ACTION_TYPES
            or not isinstance(yielded.actions[-1], RespondAction)
            or not isinstance(active.actions[-1], IdleAction)
            or yielded.actions[-1].reply_to_event_id != FAILED_RESULT_EVENT_ID
            or active.actions[-1].reason is not IdleReason.AWAITING_OPENING
            or active.actions[-1].related_event_id != FAILED_RESULT_EVENT_ID
            or yielded.response_warrants_by_beat
            != (
                BeatResponseWarrant(
                    "b12",
                    _FINAL_INVITATION_EVENT_ID,
                    ResponseWarrantKind.INVITATION,
                    FAILED_RESULT_EVENT_ID,
                ),
            )
        ):
            raise ValueError("failed-response twins do not preserve the adjudicated suffix")
        yielded_final = parse_tim_json(yielded.frames[-1].raw_bytes)
        active_final = parse_tim_json(active.frames[-1].raw_bytes)
        if (
            yielded.frames[-1].at_ms != active.frames[-1].at_ms
            or not isinstance(yielded_final, dict)
            or not isinstance(active_final, dict)
            or yielded_final.get("activity") != "paused"
            or active_final.get("activity") != "active"
            or {key: value for key, value in yielded_final.items() if key != "activity"}
            != {key: value for key, value in active_final.items() if key != "activity"}
        ):
            raise ValueError("failed-response twins may differ only at the final floor frame")


def build_g7_failed_response_twin_programs(
    registry: AssetRegistry,
    *,
    invitation: str,
    answer_contract: AnswerContract,
    candidate_response: str,
    master_seed: str = "g7-failed-response-twins-v1",
    failed_lookup_index: int = 0,
) -> FailedResponseTwinPrograms:
    """Build the complete yielded/active failed-result pair from sealed TEST inputs."""
    if not isinstance(invitation, str) or invitation.strip() != invitation or not invitation:
        raise ValueError("invitation must be a non-blank trimmed string")
    if not isinstance(answer_contract, AnswerContract):
        raise TypeError("answer_contract must be an AnswerContract")
    if answer_contract.response_kind is not ResponseKind.FAILED_TOOL_NOTICE:
        raise ValueError("failed-response twins require a failed_tool_notice contract")
    if answer_contract.support_event_ids != (FAILED_QUERY_EVENT_ID, FAILED_RESULT_EVENT_ID):
        raise ValueError("failed-response support must bind the query and failed result")

    bundle, template, failure, first_success, second_success, document = _inputs(
        registry, failed_lookup_index
    )
    failed_result = ScriptedToolResult(
        latency_ms=100,
        data={"unused": True},
        status=ToolResultStatus.FAILED,
    )
    if not isinstance(failed_result.data, dict) or not isinstance(
        failed_result.data.get("message"), str
    ):
        raise RuntimeError("failed tool support projection drifted")
    validate_response_text(
        candidate_response,
        answer_contract,
        visible_support_by_event_id={
            FAILED_QUERY_EVENT_ID: failure.query,
            FAILED_RESULT_EVENT_ID: failed_result.data["message"],
        },
    )

    timing = materialize_timing_plan(
        TimingSeed(Split.TEST, f"g7-failed-response-twins-v1:{master_seed}"), 13
    )
    (
        frames,
        first_result_due_at,
        second_result_due_at,
        first_request_committed_at,
        second_request_committed_at,
    ) = _frames(
        document,
        failure.query,
        first_success.query,
        second_success.query,
        invitation,
        timing.service_ms,
    )
    actions = (
        *(_idle() for _ in range(_PRELUDE_COUNT)),
        _delegate("e_000005", failure.query),
        _idle(IdleReason.AWAITING_OPENING, FAILED_RESULT_EVENT_ID),
        _idle(IdleReason.AWAITING_OPENING, FAILED_RESULT_EVENT_ID),
        _idle(IdleReason.AWAITING_OPENING, FAILED_RESULT_EVENT_ID),
        _delegate("e_000012", first_success.query),
        _delegate("e_000013", second_success.query),
        _idle(IdleReason.AWAITING_TOOL, "e_000012"),
        IntegrateAction(type="integrate", result_event_id="e_000019", text=first_success.result_a),
        IntegrateAction(type="integrate", result_event_id="e_000020", text=second_success.result_a),
    )
    yielded_response = RespondAction(
        type="respond", reply_to_event_id=FAILED_RESULT_EVENT_ID, text=candidate_response
    )
    shared_results = (
        failed_result,
        _tool_result(first_result_due_at, first_request_committed_at, first_success.result_a),
        _tool_result(second_result_due_at, second_request_committed_at, second_success.result_a),
    )
    group_id = "g7-failed-response-" + artifact_digest(
        {
            "assets": tuple(asset.asset_id for asset in bundle.assets),
            "failed_query": failure.query,
            "master_seed": master_seed,
        }
    )[7:23]
    beats = tuple(f"b{index}" for index in range(13))
    need_lineage, delegate_provenance = build_g7_need_evidence(
        beats,
        (*actions, yielded_response),
        (
            G7NeedPlan("n_failed_lookup", 3),
            G7NeedPlan(
                "n_first_success",
                7,
                terminal_index=11,
                terminal_status=NeedStatus.SATISFIED,
                terminal_basis_kind=NeedBasisKind.RESULT,
                terminal_basis_event_id="e_000019",
            ),
            G7NeedPlan(
                "n_second_success",
                8,
                terminal_index=12,
                terminal_status=NeedStatus.SATISFIED,
                terminal_basis_kind=NeedBasisKind.RESULT,
                terminal_basis_event_id="e_000020",
            ),
        ),
    )
    common = dict(
        bundle=bundle,
        template=template,
        family=CorpusFamily.LOOKUP_LIVE,
        master_seed=master_seed,
        timing_plan=timing,
        tool_results=shared_results,
        beat_ids=beats,
        stale_results_by_beat=tuple(BeatStaleResults(beat, ()) for beat in beats),
        perturbations=(
            DeclaredPerturbation("floor_opening"),
            DeclaredPerturbation("tool_result"),
        ),
        config=_ROLLOVER_CONFIG,
        response_warrants_by_beat=(
            BeatResponseWarrant(
                "b12",
                _FINAL_INVITATION_EVENT_ID,
                ResponseWarrantKind.INVITATION,
                FAILED_RESULT_EVENT_ID,
            ),
        ),
        need_lineage_by_beat=need_lineage,
        delegate_provenance_by_beat=delegate_provenance,
        require_g7_evidence=True,
    )
    shared_openings = (BeatOpening("b10", "e_000018"), BeatOpening("b11", "e_000018"))
    yielded = ScenarioProgram(
        frames=(*frames[:-1], _frame(frames[-1].at_ms, invitation, "paused")),
        actions=(*actions, yielded_response),
        counterfactual=_link(group_id, "yielded"),
        openings_by_beat=(*shared_openings, BeatOpening("b12", _FINAL_INVITATION_EVENT_ID)),
        **common,
    )
    active = ScenarioProgram(
        frames=(*frames[:-1], _frame(frames[-1].at_ms, invitation, "active")),
        actions=(
            *actions,
            _idle(IdleReason.AWAITING_OPENING, FAILED_RESULT_EVENT_ID),
        ),
        counterfactual=_link(group_id, "active"),
        openings_by_beat=shared_openings,
        **common,
    )
    return FailedResponseTwinPrograms(
        (yielded, active),
        (FAILED_RESPONSE_SHAPE_ID, FAILED_RESPONSE_SHAPE_ID),
    )


def _inputs(
    registry: AssetRegistry,
    failed_lookup_index: int,
) -> tuple[
    AssetBundle,
    AssetRecord,
    LookupAssetPayload,
    LookupAssetPayload,
    LookupAssetPayload,
    str,
]:
    pool = registry.pool(Split.TEST)
    template = next(
        (item for item in pool.templates if CorpusFamily.LOOKUP_LIVE in item.coverage), None
    )
    if template is None:
        raise ValueError("sealed TEST pool lacks a live-lookup template")
    if isinstance(failed_lookup_index, bool) or not isinstance(failed_lookup_index, int):
        raise TypeError("failed_lookup_index must be an integer")
    lookups = tuple(
        sorted(
            (item for item in pool.assets if isinstance(item.payload, LookupAssetPayload)),
            key=lambda item: item.asset_id,
        )
    )
    if not 0 <= failed_lookup_index < len(lookups):
        raise ValueError("failed_lookup_index must select one sealed lookup subject")
    failure = lookups[failed_lookup_index]
    successes = tuple(item for item in lookups if item.asset_id != failure.asset_id)
    if len(successes) < 2:
        raise ValueError("failed-response twins need two distinct sealed success lookups")
    bundle, selected_template = select_approved_scenario_inputs(
        registry,
        split=Split.TEST,
        template_id=template.asset_id,
        asset_ids=tuple(item.asset_id for item in pool.assets),
    )
    assert isinstance(failure.payload, LookupAssetPayload)
    assert isinstance(successes[0].payload, LookupAssetPayload)
    assert isinstance(successes[1].payload, LookupAssetPayload)
    return (
        bundle,
        selected_template,
        failure.payload,
        successes[0].payload,
        successes[1].payload,
        build_checkpoint_working_document(_asset_text(item) for item in pool.assets),
    )


def _frames(
    document: str,
    failure_query: str,
    first_query: str,
    second_query: str,
    invitation: str,
    service_ms: tuple[int, ...],
) -> tuple[tuple[ScheduledSamplerFrame, ...], int, int, int, int]:
    prelude = tuple(
        _frame(index * _FRAME_GAP_MS, document, "paused") for index in range(_PRELUDE_COUNT)
    )
    failure_at = len(prelude) * _FRAME_GAP_MS
    precheck_at = failure_at + service_ms[3] + 200
    restraint_at = precheck_at + service_ms[4] + service_ms[5] + _FRAME_GAP_MS
    suffix_at = restraint_at + service_ms[6] + _FRAME_GAP_MS
    second_at = suffix_at + 100
    first_request_committed_at = suffix_at + service_ms[7]
    second_request_started_at = max(second_at, first_request_committed_at)
    second_request_committed_at = second_request_started_at + service_ms[8]
    # The awaiting-tool action starts with both successes pending and a closed
    # floor.  The shared opening and results arrive while that decision is in
    # flight, so the next decision commits them together before integrating.
    # The divergent final sampler frame lands during the second integration,
    # making it the newest snapshot for the final response/idle decision.
    opening_at = second_request_committed_at + 100
    results_at = second_request_committed_at + 200
    first_integration_started_at = max(
        second_request_committed_at + service_ms[9], results_at
    )
    first_integration_committed_at = first_integration_started_at + service_ms[10]
    legacy_second_latency = results_at - second_at - service_ms[8]
    legacy_second_due_at = second_request_committed_at + legacy_second_latency
    second_result_due_at = (
        legacy_second_due_at
        if legacy_second_due_at < first_integration_committed_at
        else results_at
    )
    final_trigger_at = first_integration_committed_at + 100
    return (
        (
            *prelude,
            _frame(failure_at, failure_query, "active"),
            _frame(precheck_at, document, "paused"),
            _frame(restraint_at, document, "paused"),
            _frame(suffix_at, first_query, "active"),
            _frame(second_at, second_query, "active"),
            _frame(opening_at, invitation, "paused"),
            _frame(final_trigger_at, invitation, "paused"),
        ),
        results_at,
        second_result_due_at,
        first_request_committed_at,
        second_request_committed_at,
    )


def _tool_result(
    due_at: int, request_committed_at: int, result: str
) -> ScriptedToolResult:
    latency = due_at - request_committed_at
    if latency < 0:
        raise RuntimeError("success result precedes its delegate")
    return ScriptedToolResult(latency_ms=latency, data={"nonce": result})


def _asset_text(asset: AssetRecord) -> str:
    payload = asset.payload
    if isinstance(payload, TextAssetPayload):
        return payload.text
    if isinstance(payload, LookupAssetPayload):
        return payload.query
    if isinstance(payload, TimerAssetPayload):
        return payload.instruction
    raise TypeError("checkpoint document requires atomic assets")


def _frame(at_ms: int, text: str, activity: str) -> ScheduledSamplerFrame:
    cursor = utf16_len(text)
    return ScheduledSamplerFrame(
        at_ms,
        canonicalize_tim_json(
            {
                "text": text,
                "selection_start": cursor,
                "selection_end": cursor,
                "is_composing": False,
                "input_type": "insertText",
                "activity": activity,
                "client_ts": at_ms,
            }
        ),
    )


def _delegate(event_id: str, query: str) -> DelegateAction:
    return DelegateAction(
        type="delegate",
        fact=Span(
            event_id=event_id,
            start_utf16=0,
            end_utf16=utf16_len(query),
            text=query,
        ),
        tool=ToolName.LOOKUP,
        args={"query": query},
    )


def _idle(
    reason: IdleReason = IdleReason.NO_TRIGGER, related_event_id: str | None = None
) -> IdleAction:
    return IdleAction(type="idle", reason=reason, related_event_id=related_event_id)


def _link(group_id: str, member_id: str) -> CounterfactualDeclaration:
    return CounterfactualDeclaration(
        kind="twin",
        group_id=group_id,
        member_id=member_id,
        member_ids=("active", "yielded"),
        flipped_perturbation="floor_opening",
    )
