"""Serialized tick loop, wake semantics, and atomic action execution."""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace
from enum import StrEnum
from typing import TYPE_CHECKING

from pydantic import BaseModel

from im.canonical_json import TimJsonError, TimJsonLimits, canonicalize_tim_json
from im.coalesce import PendingEvent, coalesce
from im.config import RuntimeConfig
from im.decision_trace import (
    DecisionTraceDraft,
    DecisionTraceV1,
    digest,
    effect_payload,
    emit_trace,
    exact_bytes,
    jsonable,
    persist_trace,
)
from im.license import (
    AddressableEventView,
    Allowed,
    AmbiguousMarkView,
    AppliedMarkView,
    Blocked,
    LicenseEventKind,
    LicenseView,
    OtherEventView,
    PendingToolRequestView,
    SnapshotView,
    TimerFireView,
    TimerView,
    ToolResultView,
    check,
)
from im.mark_projection import project_ambiguous_mark_targets, project_span
from im.policy.base import (
    BaseLanguagePolicy,
    CalibrationPolicy,
    Policy,
    PolicyCallCancelled,
    PolicyCallError,
    PolicyCallTrace,
    PolicyDecision,
    SemanticIntentPolicy,
)
from im.response_state import response_handled_snapshot_ids
from im.scheduler import Clock, TimerScheduler
from im.schema.actions import (
    CancelAction,
    CancelAllActiveTarget,
    CancelTimersTarget,
    CancelTimerTarget,
    DelegateAction,
    IdleAction,
    IntegrateAction,
    MarkAction,
    NonIdleAction,
    NudgeAction,
    RespondAction,
    ScheduleAction,
    SkipAction,
    Span,
)
from im.schema.common import (
    Activity,
    Disposition,
    LicenseBlockCode,
    TimerStatus,
    ToolName,
    ToolResultStatus,
)
from im.schema.events import (
    ActionExecutedEvent,
    SnapshotEvent,
    StateCheckpointEvent,
    TimerFireEvent,
    ToolRequestedEvent,
    ToolResultEvent,
)
from im.store import IdKind, PolicyEventDraft, PolicyRecord, Store
from im.tools import ScriptedToolResult, ToolAdapter

if TYPE_CHECKING:
    from im.policy.phase3x_runtime import FrozenPhase3XBoundary


class TickPhase(StrEnum):
    IDLE = "idle"
    INFERRING = "inferring"


class RenderKind(StrEnum):
    MARK = "mark_render"
    RESPOND = "respond_text"
    NUDGE = "nudge_annotation"
    TIMER_STATUS = "timer_status"


@dataclass(frozen=True, slots=True)
class RenderCommand:
    """A committed domain effect for the transport layer to encode."""

    kind: RenderKind
    action_event_id: str
    payload: dict[str, object]


type RenderSink = Callable[[RenderCommand], Awaitable[None] | None]
type TraceSink = Callable[[DecisionTraceV1], Awaitable[None] | None]
type CommittedIngressSink = Callable[[PolicyEventDraft], None]
type ToolScript = Callable[[DelegateAction], ScriptedToolResult | None]


@dataclass(frozen=True, slots=True)
class TickResult:
    changed_state: bool
    executed_action_event_id: str | None = None
    blocked_code: LicenseBlockCode | None = None
    fresh_ingress_committed: bool = False
    mark_quiescent: bool | None = None
    force_continuation: bool = False


def _event_kind(record: PolicyRecord) -> LicenseEventKind:
    return LicenseEventKind(f"{record.event.source}.{record.event.kind}")


def _project_mark_action(store: Store, action: object) -> object:
    if not isinstance(action, MarkAction):
        return action
    snapshots = tuple(
        record.event for record in store.policy_records() if isinstance(record.event, SnapshotEvent)
    )
    target = project_span(action.target, snapshots)
    return action if target is None else action.model_copy(update={"target": target})


def build_license_view(
    store: Store,
    config: RuntimeConfig,
    *,
    payload_within_limits: bool = True,
    newer_pending_snapshot: bool = False,
) -> LicenseView:
    """Project objective license facts from one durable store snapshot."""
    records = store.policy_records()
    disposition_by_id = {item.event_id: item.state for item in store.dispositions()}
    snapshots = tuple(
        record.event for record in records if isinstance(record.event, SnapshotEvent)
    )
    responded_to_ids = response_handled_snapshot_ids(
        snapshots, (item.event_id for item in store.response_dispositions())
    )
    tool_request_policy_seq = {
        record.event.payload.request_id: record.seq
        for record in records
        if isinstance(record.event, ToolRequestedEvent)
    }
    current_records = store.policy_records(store.current_segment_index())
    visible_handled_event_ids: set[str] = set()
    for record in current_records:
        event = record.event
        if isinstance(event, StateCheckpointEvent):
            visible_handled_event_ids.update(
                item.event_id for item in event.payload.dispositions
            )
        if isinstance(event, TimerFireEvent | ToolResultEvent) and disposition_by_id.get(
            event.id
        ) in {
            Disposition.HANDLED,
            Disposition.SKIPPED,
            Disposition.SUPERSEDED,
        }:
            visible_handled_event_ids.add(event.id)
        if isinstance(event, ActionExecutedEvent):
            action = event.payload.action
            if isinstance(action, IntegrateAction):
                visible_handled_event_ids.add(action.result_event_id)
            elif isinstance(action, SkipAction):
                visible_handled_event_ids.add(action.target_event_id)
            elif isinstance(action, NudgeAction):
                visible_handled_event_ids.add(action.fire_event_id)
            elif isinstance(action, RespondAction):
                visible_handled_event_ids.add(action.reply_to_event_id)
    latest_snapshot_record = next(
        (record for record in reversed(records) if isinstance(record.event, SnapshotEvent)), None
    )
    latest_snapshot = (
        None
        if latest_snapshot_record is None
        else SnapshotView(
            event_id=latest_snapshot_record.event.id,
            text=latest_snapshot_record.event.payload.text,
            policy_seq=latest_snapshot_record.seq,
            responded_to=latest_snapshot_record.event.id in responded_to_ids,
            activity=latest_snapshot_record.event.activity,
            is_composing=latest_snapshot_record.event.payload.is_composing,
        )
    )

    event_by_id: dict[str, AddressableEventView] = {}
    applied_marks: list[AppliedMarkView] = []
    ambiguous_marks: list[AmbiguousMarkView] = []
    visible_timer_ids = {timer.timer_id for timer in store.active_timers()}

    def retain_event(event: AddressableEventView) -> None:
        event_by_id[event.event_id] = event

    for record in current_records:
        checkpoint = record.event
        if not isinstance(checkpoint, StateCheckpointEvent):
            continue
        payload = checkpoint.payload
        disposition_items = {item.event_id: item for item in payload.dispositions}
        retain_event(
            SnapshotView(
                event_id=payload.snapshot.event_id,
                text=payload.snapshot.text,
                policy_seq=(
                    disposition_items[payload.snapshot.event_id].policy_seq
                    if payload.snapshot.event_id in disposition_items
                    else 0
                ),
                responded_to=payload.snapshot.event_id in responded_to_ids,
                activity=payload.snapshot.activity,
                is_composing=payload.snapshot.is_composing,
            )
        )
        for fire in payload.open_timer_fires:
            retain_event(
                TimerFireView(
                    event_id=fire.event_id,
                    timer_id=fire.timer_id,
                    disposition=disposition_by_id.get(fire.event_id, Disposition.OPEN),
                    policy_seq=fire.policy_seq,
                )
            )
            visible_timer_ids.add(fire.timer_id)
        for result in payload.open_tool_results:
            retain_event(
                ToolResultView(
                    event_id=result.event_id,
                    request_id=result.request_id,
                    completed=True,
                    status=result.status,
                    disposition=disposition_by_id.get(result.event_id, Disposition.OPEN),
                    policy_seq=result.policy_seq,
                )
            )
        for pending in payload.pending_tools:
            if pending.fact_event_id not in event_by_id:
                retain_event(
                    OtherEventView(
                        event_id=pending.fact_event_id,
                        kind=LicenseEventKind.USER_SNAPSHOT,
                        policy_seq=pending.policy_seq,
                    )
                )
        for prior_use in payload.prior_uses:
            if prior_use.kind == "schedule":
                visible_timer_ids.add(prior_use.timer_id)
                continue
            if prior_use.result_event_id in event_by_id:
                continue
            disposition_item = disposition_items.get(prior_use.result_event_id)
            retain_event(
                ToolResultView(
                    event_id=prior_use.result_event_id,
                    request_id=prior_use.request_id,
                    completed=True,
                    status=prior_use.result_status,
                    disposition=prior_use.result_disposition,
                    policy_seq=(
                        prior_use.policy_seq
                        if disposition_item is None
                        else disposition_item.policy_seq
                    ),
                )
            )
        for disposition in payload.dispositions:
            existing = event_by_id.get(disposition.event_id)
            if disposition.relation == "responded_to":
                if isinstance(existing, SnapshotView):
                    retain_event(replace(existing, responded_to=True))
                continue
            if isinstance(existing, TimerFireView | ToolResultView | OtherEventView):
                retain_event(replace(existing, disposition=disposition.state))
            elif existing is None:
                retain_event(
                    OtherEventView(
                        event_id=disposition.event_id,
                        kind=LicenseEventKind.MODEL_ACTION_EXECUTED,
                        disposition=disposition.state,
                        policy_seq=disposition.policy_seq,
                    )
                )
        for recent in payload.recent_events:
            retain_event(
                OtherEventView(
                    event_id=recent.event_id,
                    kind=LicenseEventKind.MODEL_ACTION_EXECUTED,
                )
            )
        for mark in payload.applied_marks:
            applied_marks.append(
                AppliedMarkView(
                    mark_event_id=mark.mark_event_id,
                    instruction=None,
                    target=mark.target,
                )
            )
        for mark in payload.ambiguous_marks:
            ambiguous_marks.append(
                AmbiguousMarkView(mark_event_id=mark.mark_event_id, targets=tuple(mark.targets))
            )
        visible_timer_ids.update(timer.timer_id for timer in payload.timers)
    for record in current_records:
        event = record.event
        if isinstance(event, SnapshotEvent):
            retain_event(
                SnapshotView(
                    event_id=event.id,
                    text=event.payload.text,
                    policy_seq=record.seq,
                    responded_to=event.id in responded_to_ids,
                    activity=event.activity,
                    is_composing=event.payload.is_composing,
                )
            )
        elif isinstance(event, TimerFireEvent):
            retain_event(
                TimerFireView(
                    event_id=event.id,
                    timer_id=event.payload.timer_id,
                    disposition=disposition_by_id.get(event.id, Disposition.OPEN),
                    policy_seq=record.seq,
                )
            )
        elif isinstance(event, ToolResultEvent):
            retain_event(
                ToolResultView(
                    event_id=event.id,
                    request_id=event.payload.request_id,
                    completed=True,
                    status=event.payload.status,
                    disposition=disposition_by_id.get(event.id, Disposition.OPEN),
                    policy_seq=record.seq,
                )
            )
        else:
            retain_event(
                OtherEventView(
                    event_id=event.id,
                    kind=_event_kind(record),
                    disposition=disposition_by_id.get(event.id),
                    policy_seq=record.seq,
                )
            )
        if isinstance(event, ActionExecutedEvent) and isinstance(event.payload.action, MarkAction):
            target = project_span(event.payload.action.target, snapshots)
            if target is not None:
                applied_marks.append(
                    AppliedMarkView(
                        mark_event_id=event.id,
                        instruction=event.payload.action.instruction,
                        target=target,
                    )
                )
            else:
                targets = project_ambiguous_mark_targets(event.payload.action.target, snapshots)
                if targets:
                    ambiguous_marks.append(
                        AmbiguousMarkView(mark_event_id=event.id, targets=targets)
                    )
        if isinstance(event, TimerFireEvent):
            visible_timer_ids.add(event.payload.timer_id)
        if isinstance(event, ActionExecutedEvent) and isinstance(
            event.payload.action, CancelAction
        ):
            target = event.payload.action.target
            if isinstance(target, CancelTimerTarget):
                visible_timer_ids.add(target.timer_id)
            elif isinstance(target, CancelTimersTarget):
                visible_timer_ids.update(target.timer_ids)

    timer_views: list[TimerView] = []
    for timer in store.timers():
        instruction = Span(
            event_id=timer.instruction_event_id,
            start_utf16=timer.instruction_start_utf16,
            end_utf16=timer.instruction_end_utf16,
            text=timer.instruction_text,
        )
        timer_views.append(
            TimerView(
                timer_id=timer.timer_id,
                status=timer.status,
                instruction=instruction,
                current_instruction=project_span(instruction, snapshots),
                interval_ms=timer.interval_ms,
                message=timer.message,
            )
        )
    timers = tuple(timer_views)
    pending_tools = tuple(
        PendingToolRequestView(
            request_id=request.request_id,
            fact_event_id=request.fact_event_id,
            tool=ToolName(request.tool),
            canonical_key=request.canonical_key,
            policy_seq=tool_request_policy_seq[request.request_id],
        )
        for request in store.pending_tool_requests()
    )
    floor_owned = bool(
        latest_snapshot_record is not None
        and (
            latest_snapshot_record.event.activity is Activity.ACTIVE
            or latest_snapshot_record.event.payload.is_composing
        )
    )
    return LicenseView(
        latest_snapshot=latest_snapshot,
        events=tuple(
            sorted(event_by_id.values(), key=lambda event: (event.policy_seq, event.event_id))
        ),
        timers=timers,
        visible_timer_ids=frozenset(visible_timer_ids),
        pending_tool_requests=pending_tools,
        applied_marks=tuple(applied_marks),
        ambiguous_marks=tuple(ambiguous_marks),
        visible_handled_event_ids=frozenset(visible_handled_event_ids),
        floor_owned=floor_owned,
        payload_within_limits=payload_within_limits,
        newer_pending_snapshot=newer_pending_snapshot,
        min_timer_interval_ms=config.min_timer_interval_ms,
        max_timer_interval_ms=config.max_timer_interval_ms,
        max_active_timers=config.max_active_timers,
    )


class TickRuntime:
    """One serialized event-driven policy actor for a session."""

    def __init__(
        self,
        *,
        store: Store,
        policy: Policy,
        scheduler: TimerScheduler,
        tools: ToolAdapter,
        clock: Clock,
        config: RuntimeConfig | None = None,
        render_sink: RenderSink | None = None,
        trace_sink: TraceSink | None = None,
        committed_ingress_sink: CommittedIngressSink | None = None,
        tool_script: ToolScript | None = None,
        measurement_audits: bool = False,
    ) -> None:
        self.store = store
        self.policy = policy
        self.scheduler = scheduler
        self.tools = tools
        self.clock = clock
        self.config = config or RuntimeConfig()
        self.render_sink = render_sink
        self.trace_sink = trace_sink
        self.committed_ingress_sink = committed_ingress_sink
        self.tool_script = tool_script
        self._measurement_audits = measurement_audits
        self.phase = TickPhase.IDLE
        self.tick_count = 0
        self._decision_count = 0
        self._pending: list[PendingEvent] = []
        self._arrivals: list[dict[str, object]] = []
        self._policy_call_active = False
        self._drain_lock = asyncio.Lock()
        self._mark_quiescent = True

    @property
    def pending(self) -> tuple[PendingEvent, ...]:
        return tuple(self._pending)

    @property
    def mark_quiescent(self) -> bool:
        """Whether the latest snapshot is safe to freeze as a checkpoint baseline."""
        return self._mark_quiescent

    def enqueue_committed_ingress(self, draft: PendingEvent) -> None:
        """Queue ingress only after its raw evidence row committed durably."""
        if self._measurement_audits:
            replaced_pending_snapshot = (
                draft.source == "user"
                and draft.kind == "snapshot"
                and any(
                    event.source == "user" and event.kind == "snapshot"
                    for event in self._pending
                )
            )
            arrived_while_inferring = self._policy_call_active
        self._pending = coalesce(self._pending, draft)
        if self._measurement_audits:
            self._arrivals.append(
                {
                    "event_id": draft.id,
                    "source": draft.source,
                    "kind": draft.kind,
                    "arrived_while_inferring": arrived_while_inferring,
                    "replaced_pending_snapshot": replaced_pending_snapshot,
                }
            )

    async def submit_committed_ingress(self, draft: PendingEvent) -> None:
        self.enqueue_committed_ingress(draft)
        if self.phase is TickPhase.INFERRING:
            return
        await self.run_until_idle()

    async def run_until_idle(self) -> None:
        """Drain pending work and exact continuation ticks under one actor lock."""
        async with self._drain_lock:
            continue_tick = False
            while self._pending or continue_tick:
                result = await self._run_tick()
                if result.mark_quiescent is not None:
                    self._mark_quiescent = result.mark_quiescent
                continue_tick = result.force_continuation or result.fresh_ingress_committed or (
                    result.changed_state and self._has_open_actionable_event()
                )

    async def _run_tick(self) -> TickResult:
        self._commit_pending()
        self.phase = TickPhase.INFERRING
        self.tick_count += 1
        self._decision_count += 1
        decision_id = f"d_{self._decision_count:06d}"
        records = self.store.policy_records()
        observed_seq = records[-1].seq if records else None
        semantic = isinstance(self.policy, SemanticIntentPolicy)
        boundary = None
        if semantic:
            # Lazy import avoids the policy.intent -> generation -> server -> tick cycle.
            from im.policy.phase3x_runtime import freeze_phase3x_boundary

            policy_bytes = self.store.policy_bytes()
            frozen_view = build_license_view(self.store, self.config)
            boundary = freeze_phase3x_boundary(
                policy_bytes,
                frozen_view,
                license_view_bytes=canonicalize_tim_json(jsonable(frozen_view)),
            )
        elif self._measurement_audits:
            policy_bytes = self.store.policy_bytes()
        if self._measurement_audits:
            self.store.audit(
                "decision_started",
                {
                    "decision_id": decision_id,
                    "observed_through_policy_seq": observed_seq,
                    "started_mono_ns": self._now_mono_ns(),
                    "arrivals": self._arrivals,
                },
            )
            self._arrivals = []
        try:
            started_mono_ns = self._now_mono_ns() if boundary is not None else None
            policy_cancelled: PolicyCallCancelled | None = None
            try:
                policy_input = (
                    boundary.prompt_bytes
                    if boundary is not None
                    else policy_bytes
                    if self._measurement_audits
                    else self.store.policy_bytes()
                )
                if self._measurement_audits:
                    self._policy_call_active = True
                    try:
                        policy_result = await self.policy.decide(policy_input)
                    finally:
                        self._policy_call_active = False
                        self.store.audit(
                            "decision_finished",
                            {
                                "decision_id": decision_id,
                                "finished_mono_ns": self._now_mono_ns(),
                            },
                        )
                else:
                    policy_result = await self.policy.decide(policy_input)
            except PolicyCallCancelled as error:
                self._record_policy_call_traces(decision_id, error.calls)
                if boundary is None:
                    raise
                policy_cancelled = error
                policy_result = PolicyDecision(
                    attempt=None,
                    output_bytes=b"",
                    output_bytes_sha256=digest(b""),
                    latency_ms=sum(call.latency_ms for call in error.calls),
                )
            except PolicyCallError as error:
                self._record_policy_call_traces(decision_id, error.calls)
                if boundary is None:
                    raise
                policy_result = PolicyDecision(
                    attempt=None,
                    output_bytes=b"",
                    output_bytes_sha256=digest(b""),
                    latency_ms=sum(call.latency_ms for call in error.calls),
                )
            except Exception as error:
                if boundary is None:
                    raise
                self.store.audit(
                    "policy_failed_closed",
                    {"decision_id": decision_id, "error_type": type(error).__name__},
                )
                policy_result = PolicyDecision(
                    attempt=None,
                    output_bytes=b"",
                    output_bytes_sha256=digest(b""),
                    latency_ms=0,
                )
            if isinstance(policy_result, PolicyDecision):
                self._record_policy_call_traces(decision_id, policy_result.calls)
                raw_attempt = policy_result.attempt
            else:
                raw_attempt = policy_result
            self._audit_attempt(raw_attempt, decision_id, observed_seq)
            if boundary is None:
                decision = self._check_attempt(raw_attempt)
                if isinstance(decision, Blocked):
                    self._audit_block(decision.code, decision_id, observed_seq)
                    return TickResult(
                        False,
                        blocked_code=decision.code,
                        mark_quiescent=False if self._pending else None,
                        force_continuation=bool(self._pending),
                    )
                if isinstance(decision.action, IdleAction):
                    return TickResult(
                        False,
                        mark_quiescent=not self._pending,
                        force_continuation=bool(self._pending),
                    )
                return await self._execute(decision.action, decision_id, observed_seq, None)

            output = (
                policy_result.output_bytes
                if isinstance(policy_result, PolicyDecision)
                and policy_result.output_bytes is not None
                else b""
            )
            latency_ms = (
                policy_result.latency_ms
                if isinstance(policy_result, PolicyDecision)
                else None
            )
            if latency_ms is None:
                assert started_mono_ns is not None
                latency_ms = max(0, (self._now_mono_ns() - started_mono_ns) // 1_000_000)
            parser_input = (
                policy_result.parser_input_bytes
                if isinstance(policy_result, PolicyDecision)
                else None
            )
            (
                parsed_intent,
                resolution_payload,
                resolved_attempt,
                binding_ok,
                policy_cancelled,
            ) = await self._resolve_semantic_attempt(
                policy_result,
                output,
                parser_input,
                boundary,
                decision_id,
                policy_cancelled,
            )
            return await self._finish_semantic_attempt(
                resolved_attempt,
                parsed_intent,
                resolution_payload,
                binding_ok,
                output,
                parser_input,
                latency_ms,
                boundary,
                frozen_view,
                decision_id,
                observed_seq,
                policy_cancelled,
            )
        finally:
            self.phase = TickPhase.IDLE

    async def _finish_semantic_attempt(
        self,
        resolved_attempt: object | None,
        parsed_intent: object | None,
        resolution_payload: dict[str, object],
        binding_ok: bool,
        output: bytes,
        parser_input: bytes | None,
        latency_ms: int,
        boundary: FrozenPhase3XBoundary,
        frozen_view: LicenseView,
        decision_id: str,
        observed_seq: int | None,
        policy_cancelled: PolicyCallCancelled | None,
    ) -> TickResult:
        """Commit the terminal trace and dispatch an already-resolved semantic attempt."""
        if resolved_attempt is None:
            trace = DecisionTraceDraft(
                decision_id=decision_id,
                observed_through_policy_seq=observed_seq,
                raw_provider_output=exact_bytes(output),
                raw_provider_output_sha256=digest(output),
                parser_input=(exact_bytes(parser_input) if parser_input is not None else None),
                parser_input_sha256=(digest(parser_input) if parser_input is not None else None),
                parser_input_binding=(
                    "authenticated_terminal_framing" if binding_ok else "failed_closed"
                ),
                parsed_raw_intent=parsed_intent,
                frozen_policy_sha256=boundary.policy_sha256,
                frozen_license_view_sha256=boundary.license_view_sha256,
                frozen_registry_sha256=boundary.registry_sha256,
                resolution=resolution_payload,
                initial_license={"status": "not_checked"},
                pending_license={"status": "not_checked"},
                latency_ms=latency_ms,
            ).finish(
                final_policy_seq=observed_seq,
                fresh_license={"status": "not_checked"},
                executed_event=None,
                effect=None,
            )
            persist_trace(self.store, trace)
            await emit_trace(self.store, self.trace_sink, trace)
            if policy_cancelled is not None:
                raise policy_cancelled
            return TickResult(
                False,
                mark_quiescent=not self._pending,
                force_continuation=bool(self._pending),
            )

        initial = check(_project_mark_action(self.store, resolved_attempt), frozen_view)
        pending = (
            initial
            if isinstance(initial, Blocked)
            else check(
                _project_mark_action(self.store, initial.action),
                build_license_view(
                    self.store,
                    self.config,
                    payload_within_limits=self._payload_within_limits(initial.action),
                    newer_pending_snapshot=self._has_pending_snapshot(),
                ),
            )
        )
        assert parser_input is not None
        draft = DecisionTraceDraft(
            decision_id=decision_id,
            observed_through_policy_seq=observed_seq,
            raw_provider_output=exact_bytes(output),
            raw_provider_output_sha256=digest(output),
            parser_input=exact_bytes(parser_input),
            parser_input_sha256=digest(parser_input),
            parser_input_binding="authenticated_terminal_framing",
            parsed_raw_intent=parsed_intent,
            frozen_policy_sha256=boundary.policy_sha256,
            frozen_license_view_sha256=boundary.license_view_sha256,
            frozen_registry_sha256=boundary.registry_sha256,
            resolution=resolution_payload,
            initial_license=self._license_result(initial),
            pending_license=(
                {"status": "not_checked"}
                if isinstance(initial, Blocked)
                else self._license_result(pending)
            ),
            latency_ms=latency_ms,
        )
        if isinstance(pending, Blocked):
            self._audit_block(pending.code, decision_id, observed_seq)
            trace = draft.finish(
                final_policy_seq=observed_seq,
                fresh_license={"status": "not_checked"},
                executed_event=None,
                effect=None,
            )
            persist_trace(self.store, trace)
            await emit_trace(self.store, self.trace_sink, trace)
            return TickResult(
                False,
                blocked_code=pending.code,
                mark_quiescent=False if self._pending else None,
                force_continuation=bool(self._pending),
            )
        if isinstance(pending.action, IdleAction):
            trace = draft.finish(
                final_policy_seq=observed_seq,
                fresh_license={"status": "not_checked"},
                executed_event=None,
                effect=None,
            )
            persist_trace(self.store, trace)
            await emit_trace(self.store, self.trace_sink, trace)
            return TickResult(
                False,
                mark_quiescent=not self._pending,
                force_continuation=bool(self._pending),
            )
        return await self._execute(pending.action, decision_id, observed_seq, draft)

    async def _resolve_semantic_attempt(
        self,
        policy_result: object,
        output: bytes,
        parser_input: bytes | None,
        boundary: FrozenPhase3XBoundary,
        decision_id: str,
        policy_cancelled: PolicyCallCancelled | None,
    ) -> tuple[object | None, dict[str, object], object | None, bool, PolicyCallCancelled | None]:
        """Resolve only authenticated parser bytes and complete any required prose route."""
        binding_ok = (
            isinstance(policy_result, PolicyDecision)
            and policy_result.parser_input_binding == "authenticated_terminal_framing"
            and policy_result.output_bytes_sha256 == digest(output)
            and parser_input is not None
            and policy_result.parser_input_sha256 == digest(parser_input)
        )
        if not binding_ok:
            return (
                None,
                {
                    "status": "failed_closed",
                    "reason": "missing_or_mismatched_authenticated_parser_input",
                    "action": None,
                },
                None,
                False,
                policy_cancelled,
            )
        from im.policy.phase3x_runtime import resolve_phase3x_output

        parsed_intent, resolution = resolve_phase3x_output(parser_input, boundary.registry)
        from im.policy.intent import (
            LanguageRealizationRequest,
            complete_language_realization,
        )

        if isinstance(resolution.value, LanguageRealizationRequest):
            request = resolution.value
            prose = None
            if request.type == "respond" and isinstance(self.policy, BaseLanguagePolicy):
                try:
                    prose, calls = await self.policy.realize_language(
                        request, boundary.policy_bytes
                    )
                except PolicyCallCancelled as error:
                    self._record_policy_call_traces(decision_id, error.calls)
                    policy_cancelled = error
                except PolicyCallError as error:
                    self._record_policy_call_traces(decision_id, error.calls)
                except Exception as error:
                    self.store.audit(
                        "language_realization_failed_closed",
                        {
                            "decision_id": decision_id,
                            "error_type": type(error).__name__,
                        },
                    )
                else:
                    self._record_policy_call_traces(decision_id, calls)
            resolution = complete_language_realization(request, prose)
        return (
            parsed_intent,
            {
                "status": resolution.status.value,
                "reason": resolution.reason,
                "action": jsonable(resolution.value),
            },
            resolution.value,
            True,
            policy_cancelled,
        )

    def _commit_pending(self) -> None:
        if not self._pending:
            return
        batch = self._take_pending()
        try:
            with self.store.transaction():
                committed = self._commit_batch(batch)
        except BaseException:
            self._pending = batch + self._pending
            raise
        self._project_committed_ingress(committed)

    def _take_pending(self) -> list[PendingEvent]:
        batch, self._pending = self._pending, []
        return batch

    def _commit_batch(self, batch: list[PendingEvent]) -> tuple[PolicyEventDraft, ...]:
        committed: list[PolicyEventDraft] = []
        for draft in batch:
            draft = self._supersede_committed_fire(draft)
            self.store.commit_policy(draft)
            if (draft.source, draft.kind) in {("timer", "fire"), ("tool", "result")}:
                self.store.set_disposition(draft.id, Disposition.OPEN)
            committed.append(draft)
        return tuple(committed)

    def _project_committed_ingress(self, committed: tuple[PolicyEventDraft, ...]) -> None:
        if self.committed_ingress_sink is None:
            return
        for draft in committed:
            self.committed_ingress_sink(draft)

    def _supersede_committed_fire(self, draft: PendingEvent) -> PendingEvent:
        if draft.source != "timer" or draft.kind != "fire":
            return draft
        incoming = TimerFireEvent.model_validate(
            {
                "v": 1,
                "id": draft.id,
                "seq": 0,
                "dt_ms": 0,
                "source": "timer",
                "kind": "fire",
                "payload": draft.payload,
            }
        )
        for record in reversed(self.store.policy_records()):
            event = record.event
            if not isinstance(event, TimerFireEvent):
                continue
            if event.payload.timer_id != incoming.payload.timer_id:
                continue
            disposition = self.store.get_disposition(event.id)
            if disposition is not None and disposition.state is Disposition.OPEN:
                self.store.set_disposition(event.id, Disposition.SUPERSEDED)
                payload = incoming.payload.model_copy(
                    update={
                        "missed_count": (
                            incoming.payload.missed_count + event.payload.missed_count + 1
                        )
                    }
                )
                return replace(draft, payload=payload)
            break
        return draft

    def _check_attempt(self, raw_attempt: object) -> Allowed | Blocked:
        initial = check(
            _project_mark_action(self.store, raw_attempt),
            build_license_view(self.store, self.config),
        )
        if isinstance(initial, Blocked):
            return initial
        return check(
            _project_mark_action(self.store, initial.action),
            build_license_view(
                self.store,
                self.config,
                payload_within_limits=self._payload_within_limits(initial.action),
                newer_pending_snapshot=self._has_pending_snapshot(),
            ),
        )

    async def _execute(
        self,
        action: NonIdleAction,
        decision_id: str,
        observed_seq: int | None,
        trace_draft: DecisionTraceDraft | None,
    ) -> TickResult:
        effects: list[RenderCommand] = []
        terminal_trace: DecisionTraceV1 | None = None
        fresh_batch = self._take_pending()
        try:
            with self.store.transaction():
                # Arrivals captured during inference precede the action in real occurrence time.
                # Commit them first, then re-check the sampled action against that fresher state.
                committed_fresh = self._commit_batch(fresh_batch)
                rechecked = check(
                    _project_mark_action(self.store, action),
                    build_license_view(
                        self.store,
                        self.config,
                        payload_within_limits=self._payload_within_limits(action),
                        newer_pending_snapshot=False,
                    ),
                )
                if isinstance(rechecked, Blocked):
                    self.store.audit(
                        "action_blocked",
                        self._block_payload(rechecked.code, decision_id, observed_seq),
                    )
                    blocked = rechecked.code
                    action_event_id = None
                    if trace_draft is not None:
                        final_records = self.store.policy_records()
                        terminal_trace = trace_draft.finish(
                            final_policy_seq=final_records[-1].seq if final_records else None,
                            fresh_license=self._license_result(rechecked),
                            executed_event=None,
                            effect=None,
                        )
                        persist_trace(self.store, terminal_trace)
                else:
                    blocked = None
                    action = rechecked.action
                    action_event_id = self.store.allocate_id(IdKind.EVENT)
                    action_mono_ns = self._now_mono_ns()
                    action_seq, _rendered = self.store.commit_policy(
                        PolicyEventDraft(
                            id=action_event_id,
                            source="model",
                            kind="action_executed",
                            payload={"action": action.model_dump(mode="python")},
                            occurred_mono_ns=action_mono_ns,
                        )
                    )
                    effects.extend(self._apply_action(action, action_event_id))
                    if trace_draft is not None:
                        final_records = self.store.policy_records()
                        executed = next(
                            record.event
                            for record in reversed(final_records)
                            if record.event_id == action_event_id
                        )
                        terminal_trace = trace_draft.finish(
                            final_policy_seq=final_records[-1].seq,
                            fresh_license=self._license_result(rechecked),
                            executed_event=jsonable(executed),
                            effect=effect_payload(
                                self.store,
                                action_event_id,
                                action_seq,
                                final_records,
                                effects,
                            ),
                        )
                        persist_trace(self.store, terminal_trace)
        except BaseException:
            self._pending = fresh_batch + self._pending
            raise

        self._project_committed_ingress(committed_fresh)

        if blocked is not None:
            if terminal_trace is not None:
                await emit_trace(self.store, self.trace_sink, terminal_trace)
            return TickResult(
                False,
                blocked_code=blocked,
                fresh_ingress_committed=bool(fresh_batch),
                mark_quiescent=False if fresh_batch else None,
                force_continuation=bool(self._pending),
            )
        if action_event_id is None:  # pragma: no cover - narrowed by the branch above.
            raise RuntimeError("allowed action execution lost its event id")
        if terminal_trace is not None:
            await emit_trace(self.store, self.trace_sink, terminal_trace)
        await self._emit(effects)
        requires_mark_continuation = isinstance(
            action,
            CancelAction | ScheduleAction | NudgeAction | SkipAction | MarkAction,
        )
        return TickResult(
            True,
            executed_action_event_id=action_event_id,
            fresh_ingress_committed=bool(fresh_batch),
            mark_quiescent=not (requires_mark_continuation or fresh_batch),
            force_continuation=requires_mark_continuation,
        )

    def _apply_action(self, action: NonIdleAction, action_event_id: str) -> list[RenderCommand]:
        if isinstance(action, MarkAction):
            return [
                RenderCommand(
                    RenderKind.MARK,
                    action_event_id,
                    {
                        "instruction": action.instruction.model_dump(mode="python"),
                        "target": action.target.model_dump(mode="python"),
                    },
                )
            ]
        if isinstance(action, DelegateAction):
            script = self.tool_script(action) if self.tool_script is not None else None
            request_id = self.tools.request(
                action.tool,
                action.args.model_dump(mode="python"),
                fact_event_id=action.fact.event_id,
                scripted_result=script,
            )
            self._commit_ack(
                "tool_requested",
                {
                    "request_id": request_id,
                    "tool": action.tool.value,
                    "args": action.args.model_dump(mode="python"),
                },
            )
            return []
        if isinstance(action, IntegrateAction):
            self.store.set_disposition(
                action.result_event_id,
                Disposition.HANDLED,
                by_action_event_id=action_event_id,
            )
            return []
        if isinstance(action, SkipAction):
            self.store.set_disposition(
                action.target_event_id,
                Disposition.SKIPPED,
                by_action_event_id=action_event_id,
            )
            return []
        if isinstance(action, RespondAction):
            referenced = next(
                (
                    record.event
                    for record in self.store.policy_records()
                    if record.event.id == action.reply_to_event_id
                ),
                None,
            )
            if (
                isinstance(referenced, ToolResultEvent)
                and referenced.payload.status is ToolResultStatus.FAILED
            ):
                self.store.set_disposition(
                    referenced.id,
                    Disposition.HANDLED,
                    by_action_event_id=action_event_id,
                )
            elif isinstance(referenced, SnapshotEvent):
                self.store.set_response_disposition(
                    referenced.id,
                    by_action_event_id=action_event_id,
                )
            return [
                RenderCommand(
                    RenderKind.RESPOND,
                    action_event_id,
                    {"reply_to_event_id": action.reply_to_event_id, "text": action.text},
                )
            ]
        if isinstance(action, ScheduleAction):
            instruction_id = self.store.allocate_id(IdKind.INSTRUCTION)
            timer = self.scheduler.schedule(
                instruction_id=instruction_id,
                instruction=action.instruction,
                interval_ms=action.interval_ms,
                message=action.message,
            )
            now_mono_ns = self._now_mono_ns()
            first_due_in_ms = max(
                0,
                ((timer.next_due_mono_ns or now_mono_ns) - now_mono_ns) // 1_000_000,
            )
            self._commit_ack(
                "scheduled",
                {
                    "timer_id": timer.timer_id,
                    "instruction_id": timer.instruction_id,
                    "interval_ms": timer.interval_ms,
                    "message": timer.message,
                    "first_due_in_ms": first_due_in_ms,
                },
            )
            return [
                RenderCommand(
                    RenderKind.TIMER_STATUS,
                    action_event_id,
                    {
                        "timer_id": timer.timer_id,
                        "instruction_id": timer.instruction_id,
                        "interval_ms": timer.interval_ms,
                        "message": timer.message,
                        "status": timer.status.value,
                        "next_due_in_ms": first_due_in_ms,
                        "fire_count": timer.fire_count,
                    },
                )
            ]
        if isinstance(action, CancelAction):
            target = action.target
            if isinstance(target, CancelTimerTarget):
                canceled = self.scheduler.cancel((target.timer_id,))
            elif isinstance(target, CancelTimersTarget):
                canceled = self.scheduler.cancel(tuple(target.timer_ids))
            else:
                assert isinstance(target, CancelAllActiveTarget)
                canceled = self.scheduler.cancel_all_active()
            timer_ids = sorted(timer.timer_id for timer in canceled)
            self._commit_ack("cancel_ack", {"timer_ids": timer_ids})
            return [
                RenderCommand(
                    RenderKind.TIMER_STATUS,
                    action_event_id,
                    {
                        "timer_id": timer.timer_id,
                        "instruction_id": timer.instruction_id,
                        "interval_ms": timer.interval_ms,
                        "message": timer.message,
                        "status": TimerStatus.CANCELED.value,
                        "next_due_in_ms": None,
                        "fire_count": timer.fire_count,
                    },
                )
                for timer in canceled
            ]
        assert isinstance(action, NudgeAction)
        fire = next(
            record.event
            for record in self.store.policy_records()
            if record.event.id == action.fire_event_id and isinstance(record.event, TimerFireEvent)
        )
        timer = self.store.get_timer(fire.payload.timer_id)
        if timer is None:
            raise RuntimeError("licensed nudge timer disappeared")
        self.store.set_disposition(
            action.fire_event_id,
            Disposition.HANDLED,
            by_action_event_id=action_event_id,
        )
        return [
            RenderCommand(
                RenderKind.NUDGE,
                action_event_id,
                {
                    "fire_event_id": fire.id,
                    "timer_id": timer.timer_id,
                    "message": timer.message,
                    "fire_count": fire.payload.fire_count,
                    "missed_count": fire.payload.missed_count,
                },
            )
        ]

    def _commit_ack(self, kind: str, payload: dict[str, object]) -> None:
        self.store.commit_policy(
            PolicyEventDraft(
                id=self.store.allocate_id(IdKind.EVENT),
                source="runtime",
                kind=kind,
                payload=payload,
                occurred_mono_ns=self._now_mono_ns(),
            )
        )

    def _payload_within_limits(self, action: BaseModel) -> bool:
        try:
            canonicalize_tim_json(
                action.model_dump(mode="json"),
                TimJsonLimits.from_config(self.config),
            )
        except (TimJsonError, TypeError, ValueError):
            return False
        if isinstance(action, ScheduleAction):
            return len(action.message.encode("utf-8")) <= self.config.max_timer_message_bytes
        if isinstance(action, DelegateAction):
            return len(action.args.query.encode("utf-8")) <= self.config.max_json_string_bytes
        return True

    def _has_pending_snapshot(self) -> bool:
        return any(event.source == "user" and event.kind == "snapshot" for event in self._pending)

    def _has_open_actionable_event(self) -> bool:
        dispositions = {item.event_id: item.state for item in self.store.dispositions()}
        return any(
            isinstance(record.event, TimerFireEvent | ToolResultEvent)
            and dispositions.get(record.event.id) is Disposition.OPEN
            for record in self.store.policy_records()
        )

    def _now_mono_ns(self) -> int:
        value = self.clock.monotonic_ns()
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError("clock.monotonic_ns() must return an integer")
        if value < 0:
            raise ValueError("clock.monotonic_ns() must be non-negative")
        return value

    def _audit_attempt(self, raw: object, decision_id: str, observed_seq: int | None) -> None:
        payload = {
            "decision_id": decision_id,
            "observed_through_policy_seq": observed_seq,
            "raw": self._audit_value(raw),
        }
        if self._measurement_audits and isinstance(self.policy, CalibrationPolicy):
            payload["calibration"] = self.policy.calibration_decision_metadata()
        self.store.audit("action_attempt", payload)

    def _record_policy_call_traces(
        self, decision_id: str, calls: tuple[PolicyCallTrace, ...]
    ) -> None:
        for call in calls:
            self.store.record_policy_call(
                decision_id=decision_id,
                attempt_index=call.attempt_index,
                model=call.model,
                prompt_hash=call.prompt_hash,
                request=call.request,
                response=call.response,
                latency_ms=call.latency_ms,
                http_status=call.http_status,
                outcome=call.outcome,
            )

    def _audit_block(
        self,
        code: LicenseBlockCode,
        decision_id: str,
        observed_seq: int | None,
    ) -> None:
        self.store.audit(
            "action_blocked",
            self._block_payload(code, decision_id, observed_seq),
        )

    @staticmethod
    def _block_payload(
        code: LicenseBlockCode,
        decision_id: str,
        observed_seq: int | None,
    ) -> dict[str, object]:
        return {
            "decision_id": decision_id,
            "observed_through_policy_seq": observed_seq,
            "code": code.value,
        }

    @staticmethod
    def _audit_value(raw: object) -> object:
        if isinstance(raw, BaseModel):
            return raw.model_dump(mode="json")
        if isinstance(raw, bytes):
            try:
                return raw.decode("utf-8")
            except UnicodeDecodeError:
                return {"encoding": "hex", "data": raw.hex()}
        try:
            canonicalize_tim_json(raw)
        except (TimJsonError, TypeError, ValueError):
            return repr(raw)
        return raw

    @staticmethod
    def _license_result(result: Allowed | Blocked) -> dict[str, object]:
        if isinstance(result, Blocked):
            return {"status": "blocked", "code": result.code.value}
        return {"status": "allowed", "action": result.action.model_dump(mode="json")}

    async def _emit(self, effects: list[RenderCommand]) -> None:
        if self.render_sink is None:
            return
        for effect in effects:
            try:
                result = self.render_sink(effect)
                if inspect.isawaitable(result):
                    await result
            except Exception as error:  # transport failure cannot roll back durable execution
                self.store.audit(
                    "render_failed",
                    {
                        "action_event_id": effect.action_event_id,
                        "kind": effect.kind.value,
                        "error": f"{type(error).__name__}: {error}",
                    },
                )
