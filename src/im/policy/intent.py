"""Phase 3X semantic policy intent and deterministic action resolution."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictStr,
    StringConstraints,
    TypeAdapter,
    ValidationError,
    field_validator,
)

from im.assets.model import canonical_artifact_bytes
from im.canonical_json import TimJsonError, canonicalize_tim_json, parse_tim_json
from im.generation.timer_instruction_semantics import parse_runtime_timer_instruction_v1
from im.license import (
    LicenseView,
    OtherEventView,
    SnapshotView,
    TimerFireView,
    ToolResultView,
)
from im.schema.actions import (
    ACTION_ADAPTER,
    Action,
    CancelAction,
    CancelAllActiveTarget,
    CancelTimersTarget,
    CancelTimerTarget,
    DelegateAction,
    IdleAction,
    IdleReason,
    IntegrateAction,
    LookupArgs,
    MarkAction,
    NudgeAction,
    RespondAction,
    ScheduleAction,
    SkipAction,
    SkipReason,
    Span,
)
from im.schema.common import Disposition, TimerStatus, ToolName, ToolResultStatus
from im.schema.events import EVENT_ADAPTER, StateCheckpointEvent, ToolResultEvent
from im.schema.textspan import utf16_len, utf16_slice

Alias = Annotated[StrictStr, StringConstraints(pattern=r"^[upirtf](?:0|[1-9][0-9]*)$")]
NonEmptyText = Annotated[StrictStr, StringConstraints(min_length=1)]
Occurrence = Annotated[int, Field(strict=True, ge=0)]


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ResponseKind(StrEnum):
    ORDINARY_GROUNDED_ANSWER = "ordinary_grounded_answer"
    CLARIFICATION = "clarification"
    UNSUPPORTED_FEATURE_LIMITATION = "unsupported_feature_limitation"
    FAILED_RESULT_NOTICE = "failed_result_notice"


class VisibleInstruction(_StrictModel):
    kind: Literal["visible"]
    source: Alias
    text: NonEmptyText
    occurrence: Occurrence


class CommittedInstruction(_StrictModel):
    kind: Literal["committed"]
    instruction: Alias


InstructionSelector = Annotated[
    VisibleInstruction | CommittedInstruction,
    Field(discriminator="kind"),
]


class IdleIntent(_StrictModel):
    type: Literal["idle"]
    reason: IdleReason
    related: Alias | None


class MarkIntent(_StrictModel):
    type: Literal["mark"]
    instruction: InstructionSelector
    source: Alias
    text: NonEmptyText
    occurrence: Occurrence


class DelegateIntent(_StrictModel):
    type: Literal["delegate"]
    source: Alias
    query: NonEmptyText
    occurrence: Occurrence


class IntegrateIntent(_StrictModel):
    type: Literal["integrate"]
    result: Alias


class SkipIntent(_StrictModel):
    type: Literal["skip"]
    target: Alias
    reason: SkipReason


class RespondIntent(_StrictModel):
    type: Literal["respond"]
    warrant: Alias
    response_kind: ResponseKind


class ScheduleIntent(_StrictModel):
    type: Literal["schedule"]
    instruction: InstructionSelector


class CancelTimerIntentTarget(_StrictModel):
    kind: Literal["timer"]
    timer: Alias


class CancelTimersIntentTarget(_StrictModel):
    kind: Literal["timers"]
    timers: Annotated[list[Alias], Field(min_length=1)]

    @field_validator("timers")
    @classmethod
    def validate_order(cls, timers: list[str]) -> list[str]:
        if len(timers) != len(set(timers)):
            raise ValueError("timer aliases must be unique")
        if timers != sorted(timers, key=lambda alias: int(alias[1:])):
            raise ValueError("timer aliases must be numerically sorted")
        return timers


class CancelAllActiveIntentTarget(_StrictModel):
    kind: Literal["all_active"]


CancelIntentTarget = Annotated[
    CancelTimerIntentTarget | CancelTimersIntentTarget | CancelAllActiveIntentTarget,
    Field(discriminator="kind"),
]


class CancelIntent(_StrictModel):
    type: Literal["cancel"]
    instruction: InstructionSelector
    target: CancelIntentTarget


class NudgeIntent(_StrictModel):
    type: Literal["nudge"]
    fire: Alias


PolicyIntentV1 = Annotated[
    IdleIntent
    | MarkIntent
    | DelegateIntent
    | IntegrateIntent
    | SkipIntent
    | RespondIntent
    | ScheduleIntent
    | CancelIntent
    | NudgeIntent,
    Field(discriminator="type"),
]
POLICY_INTENT_ADAPTER = TypeAdapter(PolicyIntentV1)


@dataclass(frozen=True, slots=True)
class UserReference:
    alias: str
    event_id: str
    policy_seq: int
    text: str
    responded_to: bool
    latest: bool
    already_handled_eligible: bool


@dataclass(frozen=True, slots=True)
class PendingFactReference:
    alias: str
    request_id: str
    fact_event_id: str
    tool: ToolName
    canonical_key: str
    policy_seq: int


@dataclass(frozen=True, slots=True)
class InstructionReference:
    alias: str
    span: Span
    policy_seq: int
    provenance_timer_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ResultReference:
    alias: str
    event_id: str
    policy_seq: int
    completed: bool
    status: ToolResultStatus
    disposition: Disposition
    canonical_fallback: str | None
    already_handled_eligible: bool


@dataclass(frozen=True, slots=True)
class _ResultEvidence:
    request_id: str
    policy_seq: int
    status: ToolResultStatus
    canonical_fallback: str


@dataclass(frozen=True, slots=True)
class TimerReference:
    alias: str
    timer_id: str
    interval_ms: int | None
    message: str | None


@dataclass(frozen=True, slots=True)
class FireReference:
    alias: str
    event_id: str
    policy_seq: int
    timer_id: str
    timer_status: TimerStatus | None
    disposition: Disposition
    already_handled_eligible: bool


@dataclass(frozen=True, slots=True)
class IntentRegistry:
    """Immutable aliases projected only from committed runtime facts."""

    users: tuple[UserReference, ...]
    pending_facts: tuple[PendingFactReference, ...]
    instructions: tuple[InstructionReference, ...]
    results: tuple[ResultReference, ...]
    timers: tuple[TimerReference, ...]
    fires: tuple[FireReference, ...]
    source_state_sha256: str | None

    def __post_init__(self) -> None:
        aliases = [
            item.alias
            for group in (
                self.users,
                self.pending_facts,
                self.instructions,
                self.results,
                self.timers,
                self.fires,
            )
            for item in group
        ]
        if len(aliases) != len(set(aliases)):
            raise ValueError("intent registry aliases must be unique")
        for prefix, group in zip(
            "upirtf",
            (
                self.users,
                self.pending_facts,
                self.instructions,
                self.results,
                self.timers,
                self.fires,
            ),
            strict=True,
        ):
            expected = [f"{prefix}{index}" for index in range(len(group))]
            if [item.alias for item in group] != expected:
                raise ValueError("intent registry aliases must be contiguous and deterministic")

    @classmethod
    def from_state(
        cls,
        view: LicenseView,
        policy_bytes: bytes,
        expected_state_sha256: str,
    ) -> IntentRegistry:
        """Build aliases from one immutable LicenseView and its exact committed JSONL."""
        actual_state_sha256 = sha256(policy_bytes).hexdigest()
        if expected_state_sha256 != actual_state_sha256:
            raise ValueError("committed state checksum mismatch")
        return cls._from_license_view(
            view,
            _result_fallbacks(policy_bytes),
            source_state_sha256=actual_state_sha256,
        )

    @classmethod
    def from_license_view(cls, view: LicenseView) -> IntentRegistry:
        """Build aliases without open-result data; integration then fails closed."""
        return cls._from_license_view(view, {}, source_state_sha256=None)

    @classmethod
    def _from_license_view(
        cls,
        view: LicenseView,
        result_fallbacks: Mapping[str, _ResultEvidence],
        *,
        source_state_sha256: str | None,
    ) -> IntentRegistry:
        if not isinstance(view, LicenseView):
            raise TypeError("intent registry requires a LicenseView")
        fallbacks = dict(result_fallbacks)
        handled_dispositions = {
            Disposition.HANDLED,
            Disposition.SKIPPED,
            Disposition.SUPERSEDED,
        }
        handled_events = sorted(
            (
                event
                for event in view.events
                if event.event_id in view.visible_handled_event_ids
                and (
                    isinstance(event, SnapshotView)
                    and event.responded_to
                    or isinstance(event, TimerFireView | ToolResultView | OtherEventView)
                    and event.disposition in handled_dispositions
                )
            ),
            key=lambda item: (item.policy_seq, item.event_id),
        )
        oldest_handled_event_id = handled_events[0].event_id if handled_events else None
        snapshots = sorted(
            (event for event in view.events if isinstance(event, SnapshotView)),
            key=lambda item: (item.policy_seq, item.event_id),
        )
        users = tuple(
            UserReference(
                f"u{index}",
                item.event_id,
                item.policy_seq,
                item.text,
                item.responded_to,
                view.latest_snapshot is not None
                and item.event_id == view.latest_snapshot.event_id,
                item.event_id == oldest_handled_event_id,
            )
            for index, item in enumerate(snapshots)
        )
        pending_facts = tuple(
            PendingFactReference(
                f"p{index}",
                item.request_id,
                item.fact_event_id,
                item.tool,
                item.canonical_key,
                item.policy_seq,
            )
            for index, item in enumerate(
                sorted(
                    view.pending_tool_requests,
                    key=lambda item: (item.policy_seq, item.request_id),
                )
            )
        )
        snapshot_by_id = {item.event_id: item for item in snapshots}

        instruction_provenance: dict[tuple[str, int, int, str], set[str]] = {}
        for timer in view.active_timers:
            span = timer.current_instruction
            if span is None and timer.instruction is not None:
                if timer.instruction.event_id in snapshot_by_id:
                    span = timer.instruction
            if span is None:
                continue
            snapshot = snapshot_by_id.get(span.event_id)
            if snapshot is None:
                raise ValueError("committed instruction span is not addressable")
            try:
                exact = utf16_slice(snapshot.text, span.start_utf16, span.end_utf16)
            except (TypeError, ValueError) as error:
                raise ValueError("committed instruction span is invalid") from error
            if exact != span.text:
                raise ValueError("committed instruction span text does not match runtime state")
            key = (span.event_id, span.start_utf16, span.end_utf16, span.text)
            instruction_provenance.setdefault(key, set()).add(timer.timer_id)
        instruction_rows = sorted(
            instruction_provenance.items(),
            key=lambda item: (
                snapshot_by_id[item[0][0]].policy_seq,
                item[0][0],
                item[0][1],
                item[0][2],
                item[0][3],
            ),
        )
        instructions = tuple(
            InstructionReference(
                alias=f"i{index}",
                span=Span(
                    event_id=key[0],
                    start_utf16=key[1],
                    end_utf16=key[2],
                    text=key[3],
                ),
                policy_seq=snapshot_by_id[key[0]].policy_seq,
                provenance_timer_ids=tuple(sorted(timer_ids)),
            )
            for index, (key, timer_ids) in enumerate(instruction_rows)
        )

        addressable_results = sorted(
            (event for event in view.events if isinstance(event, ToolResultView)),
            key=lambda item: (item.policy_seq, item.event_id),
        )
        results = tuple(
            ResultReference(
                f"r{index}",
                item.event_id,
                item.policy_seq,
                item.completed,
                item.status,
                item.disposition,
                _validated_fallback(item, fallbacks.get(item.event_id)),
                item.event_id == oldest_handled_event_id,
            )
            for index, item in enumerate(addressable_results)
        )
        active_timers = sorted(view.active_timers, key=lambda item: item.timer_id)
        timers = tuple(
            TimerReference(f"t{index}", item.timer_id, item.interval_ms, item.message)
            for index, item in enumerate(active_timers)
        )
        fires = tuple(
            FireReference(
                f"f{index}",
                item.event_id,
                item.policy_seq,
                item.timer_id,
                (timer.status if (timer := view.timer(item.timer_id)) is not None else None),
                item.disposition,
                item.event_id == oldest_handled_event_id,
            )
            for index, item in enumerate(
                sorted(
                    (event for event in view.events if isinstance(event, TimerFireView)),
                    key=lambda item: (item.policy_seq, item.event_id),
                )
            )
        )
        return cls(
            users,
            pending_facts,
            instructions,
            results,
            timers,
            fires,
            source_state_sha256,
        )

    def render(self) -> bytes:
        return canonical_artifact_bytes(
            {
                "f": [
                    {
                        "alias": item.alias,
                        "disposition": item.disposition.value,
                        "event_id": item.event_id,
                        "policy_seq": item.policy_seq,
                        "timer_id": item.timer_id,
                        "timer_status": (
                            None if item.timer_status is None else item.timer_status.value
                        ),
                    }
                    for item in self.fires
                ],
                "i": [
                    {
                        "alias": item.alias,
                        "provenance_timer_ids": list(item.provenance_timer_ids),
                        "span": item.span.model_dump(mode="json"),
                    }
                    for item in self.instructions
                ],
                "r": [
                    {
                        "alias": item.alias,
                        "completed": item.completed,
                        "disposition": item.disposition.value,
                        "event_id": item.event_id,
                        "policy_seq": item.policy_seq,
                        "status": item.status.value,
                    }
                    for item in self.results
                ],
                "p": [
                    {
                        "alias": item.alias,
                        "canonical_key": item.canonical_key,
                        "fact_event_id": item.fact_event_id,
                        "policy_seq": item.policy_seq,
                        "request_id": item.request_id,
                        "tool": item.tool.value,
                    }
                    for item in self.pending_facts
                ],
                "t": [
                    {
                        "alias": item.alias,
                        "interval_ms": item.interval_ms,
                        "message": item.message,
                        "timer_id": item.timer_id,
                    }
                    for item in self.timers
                ],
                "u": [
                    {
                        "alias": item.alias,
                        "event_id": item.event_id,
                        "policy_seq": item.policy_seq,
                        "responded_to": item.responded_to,
                        "text": item.text,
                    }
                    for item in self.users
                ],
                "registry_amendment": "pending_fact_and_disposition_v1",
                "source_state_sha256": self.source_state_sha256,
                "version": "policy_intent_v1",
            }
        )


class ResolutionStatus(StrEnum):
    RESOLVED_ACTION = "resolved_action"
    LANGUAGE_REQUIRED = "language_realization_required"
    CANONICAL_FALLBACK = "canonical_result_fallback"
    FAILED = "failed_closed"


@dataclass(frozen=True, slots=True)
class LanguageRealizationRequest:
    type: Literal["respond", "integrate"]
    reference_event_id: str
    response_kind: ResponseKind | Literal["result_integration"]
    policy_adapter_enabled: Literal[False] = False
    canonical_fallback: str | None = None


@dataclass(frozen=True, slots=True)
class IntentResolution:
    status: ResolutionStatus
    value: Action | LanguageRealizationRequest | None
    reason: str | None = None


class _ResolutionFailure(ValueError):
    pass


def resolve_policy_intent(raw: object, registry: IntentRegistry) -> IntentResolution:
    """Resolve one strict intent without changing its semantic choice."""
    try:
        if isinstance(raw, memoryview):
            raw = raw.tobytes()
        elif isinstance(raw, bytearray):
            raw = bytes(raw)
        elif isinstance(raw, str):
            raw = raw.encode("utf-8")
        if isinstance(raw, bytes):
            raw = parse_tim_json(raw)
        intent = POLICY_INTENT_ADAPTER.validate_python(raw)
        value = _resolve(intent, registry)
    except (ValidationError, TypeError, ValueError, TimJsonError) as error:
        return IntentResolution(ResolutionStatus.FAILED, None, str(error))
    status = (
        ResolutionStatus.LANGUAGE_REQUIRED
        if isinstance(value, LanguageRealizationRequest)
        else ResolutionStatus.RESOLVED_ACTION
    )
    return IntentResolution(status, value)


def complete_language_realization(
    request: LanguageRealizationRequest,
    text: str | None,
) -> IntentResolution:
    """Form the unchanged public open-text action after the base route returns."""
    if not isinstance(request, LanguageRealizationRequest):
        return IntentResolution(ResolutionStatus.FAILED, None, "invalid language request")
    unavailable = text is None or not isinstance(text, str) or not text.strip()
    canonically_grounded = request.type == "integrate"
    if canonically_grounded:
        text = request.canonical_fallback
    elif unavailable:
        return IntentResolution(ResolutionStatus.FAILED, None, "language realization unavailable")
    if not isinstance(text, str) or not text.strip():
        return IntentResolution(ResolutionStatus.FAILED, None, "canonical fallback unavailable")
    try:
        text.encode("utf-8")
        action: Action
        if request.type == "integrate":
            action = IntegrateAction(
                type="integrate", result_event_id=request.reference_event_id, text=text
            )
        else:
            action = RespondAction(
                type="respond", reply_to_event_id=request.reference_event_id, text=text
            )
        action = ACTION_ADAPTER.validate_python(action)
    except (UnicodeEncodeError, ValidationError, TypeError, ValueError) as error:
        return IntentResolution(ResolutionStatus.FAILED, None, str(error))
    return IntentResolution(
        (
            ResolutionStatus.CANONICAL_FALLBACK
            if canonically_grounded
            else ResolutionStatus.RESOLVED_ACTION
        ),
        action,
    )


def _resolve(
    intent: PolicyIntentV1, registry: IntentRegistry
) -> Action | LanguageRealizationRequest:
    if isinstance(intent, IdleIntent):
        related = _idle_related(intent, registry)
        return IdleAction(type="idle", reason=intent.reason, related_event_id=related)
    if isinstance(intent, MarkIntent):
        return MarkAction(
            type="mark",
            instruction=_instruction(intent.instruction, registry),
            target=_visible_span(intent.source, intent.text, intent.occurrence, registry),
        )
    if isinstance(intent, DelegateIntent):
        fact = _visible_span(intent.source, intent.query, intent.occurrence, registry)
        action = DelegateAction(
            type="delegate", fact=fact, tool=ToolName.LOOKUP, args=LookupArgs(query=intent.query)
        )
        if action.args.query != intent.query:
            raise _ResolutionFailure("delegate query normalization would change selected text")
        return action
    if isinstance(intent, IntegrateIntent):
        result = _lookup(intent.result, "r", registry.results)
        if (
            not result.completed
            or result.status is not ToolResultStatus.SUCCEEDED
            or result.disposition is not Disposition.OPEN
        ):
            raise _ResolutionFailure("integrate result did not succeed")
        if result.canonical_fallback is None:
            raise _ResolutionFailure("integrate result lacks canonical fallback")
        return LanguageRealizationRequest(
            "integrate",
            result.event_id,
            "result_integration",
            canonical_fallback=result.canonical_fallback,
        )
    if isinstance(intent, SkipIntent):
        prefix = "f" if intent.reason is SkipReason.CANCELED_TIMER else "r"
        target = _lookup(
            intent.target,
            prefix,
            registry.fires if prefix == "f" else registry.results,
        )
        if target.disposition is not Disposition.OPEN:
            raise _ResolutionFailure("skip target is not open")
        if prefix == "f" and target.timer_status is not TimerStatus.CANCELED:
            raise _ResolutionFailure("canceled-timer skip requires a canceled timer fire")
        return SkipAction(
            type="skip",
            target_event_id=target.event_id,
            reason=intent.reason,
        )
    if isinstance(intent, RespondIntent):
        if intent.warrant.startswith("u"):
            warrant = _lookup(intent.warrant, "u", registry.users)
            if warrant.responded_to:
                raise _ResolutionFailure("response warrant is already handled")
            if intent.response_kind is ResponseKind.FAILED_RESULT_NOTICE:
                raise _ResolutionFailure("failed-result notice requires a result warrant")
        else:
            warrant = _lookup(intent.warrant, "r", registry.results)
            if (
                not warrant.completed
                or warrant.status is not ToolResultStatus.FAILED
                or warrant.disposition is not Disposition.OPEN
                or intent.response_kind is not ResponseKind.FAILED_RESULT_NOTICE
            ):
                raise _ResolutionFailure("result warrant requires failed-result notice")
        return LanguageRealizationRequest(
            "respond", warrant.event_id, intent.response_kind, canonical_fallback=None
        )
    if isinstance(intent, ScheduleIntent):
        instruction = _instruction(intent.instruction, registry)
        semantics = parse_runtime_timer_instruction_v1(instruction.text)
        return ScheduleAction(
            type="schedule",
            instruction=instruction,
            interval_ms=semantics.interval_ms,
            message=semantics.message,
        )
    if isinstance(intent, CancelIntent):
        instruction = _instruction(intent.instruction, registry)
        target = intent.target
        if isinstance(target, CancelTimerIntentTarget):
            resolved_target = CancelTimerTarget(
                kind="timer", timer_id=_lookup(target.timer, "t", registry.timers).timer_id
            )
        elif isinstance(target, CancelTimersIntentTarget):
            timer_ids = sorted(
                _lookup(alias, "t", registry.timers).timer_id for alias in target.timers
            )
            resolved_target = CancelTimersTarget(kind="timers", timer_ids=timer_ids)
        else:
            if not registry.timers:
                raise _ResolutionFailure("no active timers are addressable")
            resolved_target = CancelAllActiveTarget(kind="all_active")
        return CancelAction(type="cancel", instruction=instruction, target=resolved_target)
    assert isinstance(intent, NudgeIntent)
    fire = _lookup(intent.fire, "f", registry.fires)
    if (
        fire.timer_status is not TimerStatus.ACTIVE
        or fire.disposition is not Disposition.OPEN
    ):
        raise _ResolutionFailure("nudge fire timer is not active")
    return NudgeAction(type="nudge", fire_event_id=fire.event_id)


def _instruction(selector: InstructionSelector, registry: IntentRegistry) -> Span:
    if isinstance(selector, CommittedInstruction):
        return _lookup(selector.instruction, "i", registry.instructions).span
    return _visible_span(selector.source, selector.text, selector.occurrence, registry)


def _visible_span(source: str, text: str, occurrence: int, registry: IntentRegistry) -> Span:
    user = _lookup(source, "u", registry.users)
    starts = _occurrences(user.text, text)
    if occurrence >= len(starts):
        raise _ResolutionFailure("exact text occurrence is missing")
    start = starts[occurrence]
    end = start + len(text)
    if not _complete_lexical_boundary(user.text, start, end):
        raise _ResolutionFailure("exact text occurrence is not lexically complete")
    start_utf16 = utf16_len(user.text[:start])
    return Span(
        event_id=user.event_id,
        start_utf16=start_utf16,
        end_utf16=start_utf16 + utf16_len(text),
        text=text,
    )


def _occurrences(source: str, selected: str) -> tuple[int, ...]:
    if not selected:
        return ()
    starts: list[int] = []
    cursor = 0
    while (found := source.find(selected, cursor)) >= 0:
        starts.append(found)
        cursor = found + 1
    return tuple(starts)


def _complete_lexical_boundary(source: str, start: int, end: int) -> bool:
    def word(character: str) -> bool:
        return character.isalnum() or character == "_"

    left_complete = start == 0 or not (word(source[start - 1]) and word(source[start]))
    right_complete = end == len(source) or not (word(source[end - 1]) and word(source[end]))
    return left_complete and right_complete


def _idle_related(intent: IdleIntent, registry: IntentRegistry) -> str | None:
    alias = intent.related
    if intent.reason is IdleReason.AWAITING_TOOL:
        pending = _lookup(alias, "p", registry.pending_facts)
        if not registry.pending_facts or pending is not registry.pending_facts[0]:
            raise _ResolutionFailure("awaiting-tool must select the oldest pending fact")
        return pending.fact_event_id
    if intent.reason is IdleReason.AWAITING_OPENING:
        open_results = sorted(
            (
                item
                for item in registry.results
                if item.completed and item.disposition is Disposition.OPEN
            ),
            key=lambda item: (
                0 if item.status is ToolResultStatus.SUCCEEDED else 1,
                item.policy_seq,
                item.event_id,
            ),
        )
        if open_results:
            result = _lookup(alias, "r", registry.results)
            if result is not open_results[0]:
                raise _ResolutionFailure("awaiting-opening must select the eligible result")
            return result.event_id
        user = _lookup(alias, "u", registry.users)
        if not user.latest:
            raise _ResolutionFailure("awaiting-opening must select the latest visible user")
        return user.event_id
    if intent.reason is IdleReason.ALREADY_HANDLED:
        handled: UserReference | ResultReference | FireReference
        if isinstance(alias, str) and alias.startswith("u"):
            handled = _lookup(alias, "u", registry.users)
            eligible = handled.responded_to and handled.already_handled_eligible
        elif isinstance(alias, str) and alias.startswith("r"):
            handled = _lookup(alias, "r", registry.results)
            eligible = (
                handled.disposition is not Disposition.OPEN
                and handled.already_handled_eligible
            )
        else:
            handled = _lookup(alias, "f", registry.fires)
            eligible = (
                handled.disposition is not Disposition.OPEN
                and handled.already_handled_eligible
            )
        candidates = sorted(
            (
                item
                for item in (*registry.users, *registry.results, *registry.fires)
                if item.already_handled_eligible
                and (
                    isinstance(item, UserReference)
                    and item.responded_to
                    or isinstance(item, ResultReference | FireReference)
                    and item.disposition is not Disposition.OPEN
                )
            ),
            key=lambda item: (item.policy_seq, item.event_id),
        )
        if not eligible or not candidates or handled is not candidates[0]:
            raise _ResolutionFailure("already-handled must select the oldest handled event")
        return handled.event_id
    if alias is not None:
        raise _ResolutionFailure("idle reason does not accept a related alias")
    return None


def _lookup(alias: str, prefix: str, entries: tuple[object, ...]):
    if not isinstance(alias, str) or not alias.startswith(prefix):
        raise _ResolutionFailure(f"alias is not {prefix}-typed")
    for item in entries:
        if getattr(item, "alias") == alias:
            return item
    raise _ResolutionFailure(f"unknown or non-addressable alias: {alias}")


def _validated_fallback(
    result: ToolResultView, evidence: _ResultEvidence | None
) -> str | None:
    if evidence is None:
        return None
    if (
        evidence.request_id != result.request_id
        or evidence.policy_seq != result.policy_seq
        or evidence.status is not result.status
    ):
        raise ValueError("committed result evidence conflicts with runtime state")
    return evidence.canonical_fallback


def _result_fallbacks(policy_bytes: bytes) -> dict[str, _ResultEvidence]:
    if not isinstance(policy_bytes, bytes) or not policy_bytes:
        raise ValueError("policy bytes must be non-empty committed JSONL")
    results: dict[str, _ResultEvidence] = {}
    for line in policy_bytes.splitlines():
        try:
            event = EVENT_ADAPTER.validate_python(parse_tim_json(line))
        except (TimJsonError, ValidationError, TypeError, ValueError) as error:
            raise ValueError("policy bytes contain an invalid event") from error
        rows: tuple[_ResultEvidence, ...] = ()
        if isinstance(event, ToolResultEvent):
            rows = (
                _ResultEvidence(
                    event.payload.request_id,
                    event.seq,
                    event.payload.status,
                    (
                        event.payload.data
                        if isinstance(event.payload.data, str)
                        else canonicalize_tim_json(event.payload.data).decode("utf-8")
                    ),
                ),
            )
        elif isinstance(event, StateCheckpointEvent):
            for item in event.payload.open_tool_results:
                evidence = _ResultEvidence(
                    item.request_id,
                    item.policy_seq,
                    item.status,
                    canonicalize_tim_json(item.data).decode("utf-8"),
                )
                if item.event_id in results and results[item.event_id] != evidence:
                    raise ValueError("committed result data conflicts across runtime state")
                results[item.event_id] = evidence
            continue
        for evidence in rows:
            event_id = event.id
            if event_id in results and results[event_id] != evidence:
                raise ValueError("committed result data conflicts across runtime state")
            results[event_id] = evidence
    return results


__all__ = [
    "IntentRegistry",
    "IntentResolution",
    "LanguageRealizationRequest",
    "POLICY_INTENT_ADAPTER",
    "PendingFactReference",
    "PolicyIntentV1",
    "ResolutionStatus",
    "ResponseKind",
    "complete_language_realization",
    "resolve_policy_intent",
]
