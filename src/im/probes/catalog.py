"""Deterministic runtime construction of the complete WP14 probe catalog."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from im.config import RuntimeConfig
from im.license import Allowed, Blocked, LicenseView, check
from im.probes.model import (
    LicenseExpectation,
    LogicalProbe,
    NegativeClass,
    ProbeManifest,
    RenderedVariant,
)
from im.probes.runtime import RuntimeProbeBuilder, RuntimeProbeState
from im.probes.validate import ProbeValidationReport, validate_manifest
from im.schema.actions import (
    Action,
    CancelAction,
    CancelAllActiveTarget,
    CancelTimerTarget,
    DelegateAction,
    IdleAction,
    IntegrateAction,
    LookupArgs,
    MarkAction,
    NudgeAction,
    RespondAction,
    ScheduleAction,
    SkipAction,
    Span,
)
from im.schema.common import Activity
from im.schema.events import SnapshotEvent
from im.schema.textspan import utf16_len
from im.server import ArtifactPaths, load_session_artifacts
from im.tools import ScriptedToolResult

_VARIANT_IDS = ("v1", "v2", "v3")
_FAMILY_NAMES = {
    1: "mark: direct versus non-direct instruction",
    2: "mark: complete versus mid-word target",
    3: "tool result: live versus post-topic-change",
    4: "delegate: absent versus pending request",
    5: "tool result: opening versus mid-typing",
    6: "schedule: direct complete versus non-direct or ambiguous",
    7: "timer fire: floor-independent nudge",
    8: "timer fire: active versus canceled timer",
    9: "cancel: one versus two active timers",
    10: "respond: active floor versus explicit yield",
    11: "tool result: pre versus post rollover",
    12: "valid but unwanted versus no-trigger restraint",
}
_FLIP_VARIABLES = {
    1: "instruction_directness",
    2: "target_lexical_completeness",
    3: "result_need_staleness",
    4: "canonical_request_pending",
    5: "user_floor_open",
    6: "schedule_instruction_validity",
    7: "user_floor_open",
    8: "timer_active",
    9: "active_timer_count",
    10: "user_floor_open",
    11: "rollover_representation",
    12: "restraint_lexical_content",
}

_ANIMALS = ("cat", "horse", "whale", "eagle", "tiger", "yak")
_TASKS = (
    "stretch",
    "review notes",
    "water the fern",
    "stand up",
    "check the oven",
    "call the desk",
)
_FACTS = (
    "the Chicago forecast",
    "the match score",
    "the library hours",
    "the latest train status",
    "the current exchange rate",
    "the release date",
)


@dataclass(frozen=True, slots=True)
class BuiltProbeCatalog:
    """A serializable manifest plus non-serialized objective validation evidence."""

    manifest: ProbeManifest
    validation: ProbeValidationReport
    views: dict[tuple[str, str], LicenseView]


@dataclass(frozen=True, slots=True)
class _BuiltState:
    user_text: str
    user_texts: tuple[str, ...]
    state: RuntimeProbeState
    expected: Action
    tempting: Action


def _idle(reason: str = "no_trigger", related_event_id: str | None = None) -> IdleAction:
    return IdleAction(type="idle", reason=reason, related_event_id=related_event_id)


def _span(event_id: str, text: str, needle: str | None = None) -> Span:
    selected = text if needle is None else needle
    index = 0 if needle is None else text.index(needle)
    start = utf16_len(text[:index])
    return Span(
        event_id=event_id,
        start_utf16=start,
        end_utf16=start + utf16_len(selected),
        text=selected,
    )


def _lookup_request(fact: str, variant: int) -> str:
    return (
        f"Please look up {fact}.",
        f"Could you retrieve {fact}?",
        f"Check {fact} for me.",
    )[variant]


def _recurring_request(task: str, interval: str, variant: int) -> str:
    return (
        f"Remind me every {interval} to {task}.",
        f"Every {interval}, remind me to {task}.",
        f"Set a reminder every {interval} to {task}.",
    )[variant]


def _expectation(action: Action, view: LicenseView) -> LicenseExpectation:
    decision = check(action, view)
    if isinstance(decision, Allowed):
        return LicenseExpectation(outcome="allow")
    assert isinstance(decision, Blocked)
    return LicenseExpectation(outcome="block", code=decision.code)


class ProbeCatalogBuilder:
    """Build all 432 rendered states without inference or heuristic policy outputs."""

    def __init__(self, *, repository: Path, work_directory: Path) -> None:
        self.repository = repository
        self.work_directory = work_directory
        self.artifacts = load_session_artifacts(
            ArtifactPaths.from_repository(repository),
            config=RuntimeConfig(),
        )
        self._open_builders: list[RuntimeProbeBuilder] = []

    def _builder(self, probe_id: str, variant_id: str) -> RuntimeProbeBuilder:
        builder = RuntimeProbeBuilder(
            probe_id=f"{probe_id}-{variant_id}",
            directory=self.work_directory / probe_id / variant_id,
            artifacts=self.artifacts,
        )
        self._open_builders.append(builder)
        return builder

    async def _finish(
        self,
        builder: RuntimeProbeBuilder,
        *,
        user_text: str,
        state: RuntimeProbeState,
        expected: Action,
        tempting: Action,
    ) -> _BuiltState:
        user_texts = tuple(
            record.event.payload.text
            for record in builder.store.policy_records()
            if isinstance(record.event, SnapshotEvent)
        )
        await builder.close()
        self._open_builders.remove(builder)
        return _BuiltState(user_text, user_texts, state, expected, tempting)

    async def build(self) -> BuiltProbeCatalog:
        records: dict[tuple[str, str], _BuiltState] = {}
        try:
            for family_id in range(1, 13):
                for twin_number in range(1, 7):
                    for variant_index, variant_id in enumerate(_VARIANT_IDS):
                        left, right = await self._build_pair(
                            family_id,
                            twin_number,
                            variant_index,
                            variant_id,
                        )
                        twin_id = f"f{family_id:02d}-t{twin_number:02d}"
                        records[(f"{twin_id}-a", variant_id)] = left
                        records[(f"{twin_id}-b", variant_id)] = right
        finally:
            for builder in tuple(self._open_builders):
                await builder.close()
                self._open_builders.remove(builder)

        probes = tuple(
            self._logical_probe(family_id, twin_number, side, records)
            for family_id in range(1, 13)
            for twin_number in range(1, 7)
            for side in ("a", "b")
        )
        manifest = ProbeManifest(
            format_version=1,
            logical_probe_count=144,
            rendered_state_count=432,
            variants_per_probe=3,
            probes=probes,
        )
        views = {key: value.state.license_view for key, value in records.items()}
        validation = validate_manifest(manifest, views)
        return BuiltProbeCatalog(manifest=manifest, validation=validation, views=views)

    def _logical_probe(
        self,
        family_id: int,
        twin_number: int,
        side: str,
        records: dict[tuple[str, str], _BuiltState],
    ) -> LogicalProbe:
        twin_id = f"f{family_id:02d}-t{twin_number:02d}"
        probe_id = f"{twin_id}-{side}"
        negative_class, block_variable, release_id = self._negative_metadata(
            family_id, side, twin_id
        )
        variants = tuple(
            self._rendered_variant(variant_id, records[(probe_id, variant_id)])
            for variant_id in _VARIANT_IDS
        )
        invariance = negative_class is NegativeClass.INVARIANCE
        secondary = ("floor_invariance",) if family_id == 7 else ()
        return LogicalProbe(
            probe_id=probe_id,
            family_id=family_id,
            family=_FAMILY_NAMES[family_id],
            twin_id=twin_id,
            side=side,
            flip_variable=_FLIP_VARIABLES[family_id],
            negative_class=negative_class,
            blocking_variable=block_variable,
            mechanical_release_probe_id=release_id,
            pairwise_negative_class=(NegativeClass.SEMANTIC_PREFERENCE if invariance else None),
            expected_action_equivalence=("exact_after_reference_rebuild" if invariance else None),
            secondary_assertions=secondary,
            variants=variants,
        )

    @staticmethod
    def _negative_metadata(
        family_id: int, side: str, twin_id: str
    ) -> tuple[NegativeClass, str | None, str | None]:
        if family_id == 4 and side == "b":
            return NegativeClass.MECHANICAL_NEGATIVE, "canonical_request_pending", f"{twin_id}-a"
        if family_id == 8:
            release_side = "b" if side == "a" else "a"
            return NegativeClass.MECHANICAL_NEGATIVE, "timer_active", f"{twin_id}-{release_side}"
        if family_id == 10 and side == "a":
            return NegativeClass.MECHANICAL_NEGATIVE, "floor_owned", f"{twin_id}-b"
        if family_id == 11:
            return NegativeClass.INVARIANCE, None, None
        return NegativeClass.SEMANTIC_PREFERENCE, None, None

    @staticmethod
    def _rendered_variant(variant_id: str, built: _BuiltState) -> RenderedVariant:
        policy_stream = built.state.policy_bytes.decode("utf-8")
        return RenderedVariant(
            variant_id=variant_id,
            user_text=built.user_text,
            user_texts=built.user_texts,
            policy_stream=policy_stream,
            policy_stream_sha256=f"sha256:{sha256(built.state.policy_bytes).hexdigest()}",
            expected_action=built.expected,
            expected_license=_expectation(built.expected, built.state.license_view),
            tempting_alternative=built.tempting,
            tempting_license=_expectation(built.tempting, built.state.license_view),
        )

    async def _build_pair(
        self,
        family_id: int,
        twin_number: int,
        variant_index: int,
        variant_id: str,
    ) -> tuple[_BuiltState, _BuiltState]:
        method = getattr(self, f"_family_{family_id:02d}")
        return await method(twin_number, variant_index, variant_id)

    async def _open_result(
        self,
        builder: RuntimeProbeBuilder,
        *,
        query_text: str,
        query: str,
        latency_ms: int,
    ) -> tuple[str, str]:
        builder.script_tool_result(
            ScriptedToolResult(
                latency_ms=latency_ms,
                data={"answer": f"Verified result for {query}."},
            )
        )

        def delegate(event_id: str) -> DelegateAction:
            return DelegateAction(
                type="delegate",
                fact=_span(event_id, query_text),
                tool="lookup",
                args=LookupArgs(query=query),
            )

        fact_event_id = await builder.snapshot(query_text, decision=delegate)
        builder.advance_ms(latency_ms)
        (delivery,) = builder.deliver_tools()
        return fact_event_id, delivery.event_id

    async def _schedule(
        self,
        builder: RuntimeProbeBuilder,
        *,
        text: str,
        interval_ms: int,
        message: str,
    ) -> tuple[str, str]:
        def schedule(event_id: str) -> ScheduleAction:
            return ScheduleAction(
                type="schedule",
                instruction=_span(event_id, text),
                interval_ms=interval_ms,
                message=message,
            )

        event_id = await builder.snapshot(text, decision=schedule)
        timer_id = builder.store.active_timers()[-1].timer_id
        return event_id, timer_id

    async def _family_01(
        self, case: int, variant: int, variant_id: str
    ) -> tuple[_BuiltState, _BuiltState]:
        animal = _ANIMALS[case - 1]
        command = (
            f"Mark animal names, including {animal}.",
            f"Highlight animal names such as {animal}.",
            f"Annotate animal names like {animal}.",
        )[variant]
        quoted = f'The style guide says, "{command}"'
        target_text = (
            f"A quiet {animal} crossed the path.",
            f"Along the trail, a {animal} appeared.",
            f"We noticed a {animal} near the trees.",
        )[variant]
        twin = f"f01-t{case:02d}"

        direct = self._builder(f"{twin}-a", variant_id)
        instruction_id = await direct.snapshot(command)
        target_id, direct_state = await direct.capture_snapshot(
            target_text, activity=Activity.ACTIVE
        )
        mark = MarkAction(
            type="mark",
            instruction=_span(instruction_id, command),
            target=_span(target_id, target_text, animal),
        )
        left = await self._finish(
            direct,
            user_text=command,
            state=direct_state,
            expected=mark,
            tempting=_idle("instruction_not_direct"),
        )

        nondirect = self._builder(f"{twin}-b", variant_id)
        quoted_id = await nondirect.snapshot(quoted)
        quoted_target_id, nondirect_state = await nondirect.capture_snapshot(
            target_text, activity=Activity.ACTIVE
        )
        tempting_mark = MarkAction(
            type="mark",
            instruction=_span(quoted_id, quoted),
            target=_span(quoted_target_id, target_text, animal),
        )
        right = await self._finish(
            nondirect,
            user_text=quoted,
            state=nondirect_state,
            expected=_idle("instruction_not_direct"),
            tempting=tempting_mark,
        )
        return left, right

    async def _family_02(
        self, case: int, variant: int, variant_id: str
    ) -> tuple[_BuiltState, _BuiltState]:
        animal = _ANIMALS[case - 1]
        command = (
            "Mark animal names.",
            "Highlight animal names.",
            "Annotate animal names.",
        )[variant]
        stem = (
            "The next animal is ",
            "I noticed a ",
            "Near the path was a ",
        )[variant]
        complete_text = f"{stem}{animal} "
        incomplete_text = f"{stem}{animal}like"
        twin = f"f02-t{case:02d}"

        complete = self._builder(f"{twin}-a", variant_id)
        instruction_id = await complete.snapshot(command)
        target_id, complete_state = await complete.capture_snapshot(
            complete_text, activity=Activity.ACTIVE
        )
        complete_mark = MarkAction(
            type="mark",
            instruction=_span(instruction_id, command),
            target=_span(target_id, complete_text, animal),
        )
        left = await self._finish(
            complete,
            user_text=complete_text,
            state=complete_state,
            expected=complete_mark,
            tempting=_idle("typing_active"),
        )

        incomplete = self._builder(f"{twin}-b", variant_id)
        incomplete_instruction = await incomplete.snapshot(command)
        incomplete_id, incomplete_state = await incomplete.capture_snapshot(
            incomplete_text, activity=Activity.ACTIVE
        )
        premature_mark = MarkAction(
            type="mark",
            instruction=_span(incomplete_instruction, command),
            target=_span(incomplete_id, incomplete_text, animal),
        )
        right = await self._finish(
            incomplete,
            user_text=incomplete_text,
            state=incomplete_state,
            expected=_idle("typing_active"),
            tempting=premature_mark,
        )
        return left, right

    async def _family_03(
        self, case: int, variant: int, variant_id: str
    ) -> tuple[_BuiltState, _BuiltState]:
        fact = _FACTS[case - 1]
        query_text = _lookup_request(fact, variant)
        topics = (
            "Let's discuss lunch instead.",
            "Could we switch to lunch plans?",
            "Back to planning lunch now.",
        )
        topic = topics[variant]
        twin = f"f03-t{case:02d}"

        live = self._builder(f"{twin}-a", variant_id)
        _fact_id, result_id = await self._open_result(
            live, query_text=query_text, query=fact, latency_ms=700
        )
        live_state = await live.capture_enqueued()
        integrate = IntegrateAction(
            type="integrate",
            result_event_id=result_id,
            text=f"The lookup returned a verified answer for {fact}.",
        )
        stale = SkipAction(type="skip", target_event_id=result_id, reason="stale_tool_result")
        left = await self._finish(
            live,
            user_text=query_text,
            state=live_state,
            expected=integrate,
            tempting=stale,
        )

        changed = self._builder(f"{twin}-b", variant_id)
        _changed_fact, changed_result = await self._open_result(
            changed, query_text=query_text, query=fact, latency_ms=700
        )
        _topic_id, changed_state = await changed.capture_snapshot(topic)
        right = await self._finish(
            changed,
            user_text=topic,
            state=changed_state,
            expected=SkipAction(
                type="skip",
                target_event_id=changed_result,
                reason="stale_tool_result",
            ),
            tempting=IntegrateAction(
                type="integrate",
                result_event_id=changed_result,
                text=f"The lookup returned a verified answer for {fact}.",
            ),
        )
        return left, right

    async def _family_04(
        self, case: int, variant: int, variant_id: str
    ) -> tuple[_BuiltState, _BuiltState]:
        fact = _FACTS[case - 1]
        text = _lookup_request(fact, variant)
        twin = f"f04-t{case:02d}"

        absent = self._builder(f"{twin}-a", variant_id)
        fact_id, absent_state = await absent.capture_snapshot(text)
        delegate = DelegateAction(
            type="delegate",
            fact=_span(fact_id, text),
            tool="lookup",
            args=LookupArgs(query=fact),
        )
        left = await self._finish(
            absent,
            user_text=text,
            state=absent_state,
            expected=delegate,
            tempting=_idle(),
        )

        pending = self._builder(f"{twin}-b", variant_id)
        pending.script_tool_result(
            ScriptedToolResult(latency_ms=60_000, data={"answer": "pending"})
        )

        def pending_delegate(event_id: str) -> DelegateAction:
            return DelegateAction(
                type="delegate",
                fact=_span(event_id, text),
                tool="lookup",
                args=LookupArgs(query=fact),
            )

        pending_fact = await pending.snapshot(text, decision=pending_delegate)
        pending_state = pending.current_state()
        duplicate = pending_delegate(pending_fact)
        right = await self._finish(
            pending,
            user_text=text,
            state=pending_state,
            expected=_idle("awaiting_tool", pending_fact),
            tempting=duplicate,
        )
        return left, right

    async def _family_05(
        self, case: int, variant: int, variant_id: str
    ) -> tuple[_BuiltState, _BuiltState]:
        fact = _FACTS[case - 1]
        text = _lookup_request(fact, variant)
        latency = 700 if case <= 3 else 8_000
        twin = f"f05-t{case:02d}"

        opened = self._builder(f"{twin}-a", variant_id)
        _fact_id, result_id = await self._open_result(
            opened, query_text=text, query=fact, latency_ms=latency
        )
        _opening_id, opening_state = await opened.capture_snapshot(text, activity=Activity.PAUSED)
        integrate = IntegrateAction(
            type="integrate",
            result_event_id=result_id,
            text=f"Here is the verified result for {fact}.",
        )
        left = await self._finish(
            opened,
            user_text=text,
            state=opening_state,
            expected=integrate,
            tempting=_idle("awaiting_opening", result_id),
        )

        typing = self._builder(f"{twin}-b", variant_id)
        _typing_fact, typing_result = await self._open_result(
            typing, query_text=text, query=fact, latency_ms=latency
        )
        _typing_id, typing_state = await typing.capture_snapshot(text, activity=Activity.ACTIVE)
        right = await self._finish(
            typing,
            user_text=text,
            state=typing_state,
            expected=_idle("awaiting_opening", typing_result),
            tempting=IntegrateAction(
                type="integrate",
                result_event_id=typing_result,
                text=f"Here is the verified result for {fact}.",
            ),
        )
        return left, right

    async def _family_06(
        self, case: int, variant: int, variant_id: str
    ) -> tuple[_BuiltState, _BuiltState]:
        task = _TASKS[case - 1]
        minutes = case + 1
        interval = minutes * 60_000
        command = _recurring_request(task, f"{minutes} minutes", variant)
        if case <= 3:
            invalid = f'My coworker wrote, "{command}"'
            reason = "instruction_not_direct"
        else:
            invalid = (
                f"Remind me every so often to {task}.",
                f"Periodically remind me to {task}.",
                f"Set a recurring reminder to {task} sometime.",
            )[variant]
            reason = "ambiguous"
        twin = f"f06-t{case:02d}"

        direct = self._builder(f"{twin}-a", variant_id)
        direct_id, direct_state = await direct.capture_snapshot(command, activity=Activity.ACTIVE)
        schedule = ScheduleAction(
            type="schedule",
            instruction=_span(direct_id, command),
            interval_ms=interval,
            message=task,
        )
        left = await self._finish(
            direct,
            user_text=command,
            state=direct_state,
            expected=schedule,
            tempting=_idle(reason),
        )

        invalid_builder = self._builder(f"{twin}-b", variant_id)
        invalid_id, invalid_state = await invalid_builder.capture_snapshot(
            invalid, activity=Activity.ACTIVE
        )
        tempting_schedule = ScheduleAction(
            type="schedule",
            instruction=_span(invalid_id, invalid),
            interval_ms=interval,
            message=task,
        )
        right = await self._finish(
            invalid_builder,
            user_text=invalid,
            state=invalid_state,
            expected=_idle(reason),
            tempting=tempting_schedule,
        )
        return left, right

    async def _family_07(
        self, case: int, variant: int, variant_id: str
    ) -> tuple[_BuiltState, _BuiltState]:
        task = _TASKS[case - 1]
        schedule_text = _recurring_request(task, "two seconds", variant)
        latest = (
            "I am still writing this sentence",
            "I am continuing this draft",
            "I am composing one more thought",
        )[variant]
        twin = f"f07-t{case:02d}"

        async def side(label: str, activity: Activity) -> _BuiltState:
            builder = self._builder(f"{twin}-{label}", variant_id)
            await self._schedule(builder, text=schedule_text, interval_ms=2_000, message=task)
            builder.advance_ms(2_000)
            (fire,) = builder.claim_fires()
            _snapshot_id, state = await builder.capture_snapshot(latest, activity=activity)
            return await self._finish(
                builder,
                user_text=latest,
                state=state,
                expected=NudgeAction(type="nudge", fire_event_id=fire.event_id),
                tempting=_idle(),
            )

        return await side("a", Activity.ACTIVE), await side("b", Activity.PAUSED)

    async def _family_08(
        self, case: int, variant: int, variant_id: str
    ) -> tuple[_BuiltState, _BuiltState]:
        task = _TASKS[case - 1]
        schedule_text = _recurring_request(task, "two seconds", variant)
        cancel_text = ("Cancel that reminder.", "Stop that timer.", "End that reminder.")[variant]
        twin = f"f08-t{case:02d}"

        active = self._builder(f"{twin}-a", variant_id)
        await self._schedule(active, text=schedule_text, interval_ms=2_000, message=task)
        active.advance_ms(2_000)
        (active_fire,) = active.claim_fires()
        active_state = await active.capture_enqueued()
        left = await self._finish(
            active,
            user_text=schedule_text,
            state=active_state,
            expected=NudgeAction(type="nudge", fire_event_id=active_fire.event_id),
            tempting=SkipAction(
                type="skip",
                target_event_id=active_fire.event_id,
                reason="canceled_timer",
            ),
        )

        canceled = self._builder(f"{twin}-b", variant_id)
        _schedule_id, timer_id = await self._schedule(
            canceled, text=schedule_text, interval_ms=2_000, message=task
        )
        canceled.advance_ms(2_000)
        (canceled_fire,) = canceled.claim_fires()

        def cancel(event_id: str) -> CancelAction:
            return CancelAction(
                type="cancel",
                instruction=_span(event_id, cancel_text),
                target=CancelTimerTarget(kind="timer", timer_id=timer_id),
            )

        await canceled.snapshot(cancel_text, decision=cancel)
        canceled_state = canceled.current_state()
        right = await self._finish(
            canceled,
            user_text=cancel_text,
            state=canceled_state,
            expected=SkipAction(
                type="skip",
                target_event_id=canceled_fire.event_id,
                reason="canceled_timer",
            ),
            tempting=NudgeAction(type="nudge", fire_event_id=canceled_fire.event_id),
        )
        return left, right

    async def _family_09(
        self, case: int, variant: int, variant_id: str
    ) -> tuple[_BuiltState, _BuiltState]:
        first_task = _TASKS[case - 1]
        second_task = _TASKS[case % 6]
        stop_text = ("Stop.", "Cancel it.", "End the reminder.")[variant]
        twin = f"f09-t{case:02d}"

        one = self._builder(f"{twin}-a", variant_id)
        _first_event, first_timer = await self._schedule(
            one,
            text=_recurring_request(first_task, "five minutes", variant),
            interval_ms=300_000,
            message=first_task,
        )
        stop_id, one_state = await one.capture_snapshot(stop_text, activity=Activity.ACTIVE)
        cancel_one = CancelAction(
            type="cancel",
            instruction=_span(stop_id, stop_text),
            target=CancelTimerTarget(kind="timer", timer_id=first_timer),
        )
        left = await self._finish(
            one,
            user_text=stop_text,
            state=one_state,
            expected=cancel_one,
            tempting=_idle("ambiguous"),
        )

        two = self._builder(f"{twin}-b", variant_id)
        await self._schedule(
            two,
            text=_recurring_request(first_task, "five minutes", variant),
            interval_ms=300_000,
            message=first_task,
        )
        await self._schedule(
            two,
            text=_recurring_request(second_task, "seven minutes", variant),
            interval_ms=420_000,
            message=second_task,
        )
        ambiguous_id, two_state = await two.capture_snapshot(stop_text, activity=Activity.ACTIVE)
        cancel_all = CancelAction(
            type="cancel",
            instruction=_span(ambiguous_id, stop_text),
            target=CancelAllActiveTarget(kind="all_active"),
        )
        right = await self._finish(
            two,
            user_text=stop_text,
            state=two_state,
            expected=_idle("ambiguous"),
            tempting=cancel_all,
        )
        return left, right

    async def _family_10(
        self, case: int, variant: int, variant_id: str
    ) -> tuple[_BuiltState, _BuiltState]:
        subjects = (
            (
                "Which option would you choose?",
                "What approach would you take?",
                "What do you think?",
            ),
            (
                "Should I simplify this?",
                "Would you keep this version?",
                "Is the shorter draft clearer?",
            ),
            (
                "Can you compare these ideas?",
                "Could you weigh these options?",
                "Which tradeoff is better?",
            ),
            (
                "Does this plan make sense?",
                "Is this design coherent?",
                "Would this workflow hold up?",
            ),
            ("What should I do next?", "Which step comes next?", "How would you proceed?"),
            ("Would you recommend this?", "Do you favor this choice?", "Is this the better route?"),
        )
        question = subjects[case - 1][variant]
        answer = "I would choose the simpler option based on the information here."
        twin = f"f10-t{case:02d}"

        active = self._builder(f"{twin}-a", variant_id)
        active_id, active_state = await active.capture_snapshot(question, activity=Activity.ACTIVE)
        respond = RespondAction(type="respond", reply_to_event_id=active_id, text=answer)
        left = await self._finish(
            active,
            user_text=question,
            state=active_state,
            expected=_idle("typing_active"),
            tempting=respond,
        )

        paused = self._builder(f"{twin}-b", variant_id)
        paused_id, paused_state = await paused.capture_snapshot(question, activity=Activity.PAUSED)
        right = await self._finish(
            paused,
            user_text=question,
            state=paused_state,
            expected=RespondAction(type="respond", reply_to_event_id=paused_id, text=answer),
            tempting=_idle(),
        )
        return left, right

    async def _family_11(
        self, case: int, variant: int, variant_id: str
    ) -> tuple[_BuiltState, _BuiltState]:
        fact = _FACTS[case - 1]
        text = _lookup_request(fact, variant)
        twin = f"f11-t{case:02d}"

        async def side(label: str, do_rollover: bool) -> _BuiltState:
            builder = self._builder(f"{twin}-{label}", variant_id)
            _fact_id, result_id = await self._open_result(
                builder, query_text=text, query=fact, latency_ms=700
            )
            state = await builder.capture_enqueued()
            if do_rollover:
                builder.rollover()
                state = builder.current_state()
            return await self._finish(
                builder,
                user_text=text,
                state=state,
                expected=IntegrateAction(
                    type="integrate",
                    result_event_id=result_id,
                    text=f"Here is the verified result for {fact}.",
                ),
                tempting=SkipAction(
                    type="skip",
                    target_event_id=result_id,
                    reason="stale_tool_result",
                ),
            )

        return await side("a", False), await side("b", True)

    async def _family_12(
        self, case: int, variant: int, variant_id: str
    ) -> tuple[_BuiltState, _BuiltState]:
        texts = (
            (
                (
                    "I am drafting a note about the budget.",
                    "I am sketching a note about the budget.",
                    "I am revising a note about the budget.",
                ),
                (
                    "I am drafting a note about the roadmap.",
                    "I am sketching a note about the roadmap.",
                    "I am revising a note about the roadmap.",
                ),
            ),
            (
                (
                    "Paris is the capital of France.",
                    "France's capital is Paris.",
                    "The capital city of France is Paris.",
                ),
                (
                    "Rome is the capital of Italy.",
                    "Italy's capital is Rome.",
                    "The capital city of Italy is Rome.",
                ),
            ),
            (
                (
                    "The word cat appears here.",
                    "Here is the word cat.",
                    "This sentence contains cat.",
                ),
                (
                    "The word fox appears here.",
                    "Here is the word fox.",
                    "This sentence contains fox.",
                ),
            ),
            (
                (
                    "I might start a five-minute timer later.",
                    "I may set a five-minute reminder later.",
                    "Perhaps I will use a five-minute timer later.",
                ),
                (
                    "I might start a ten-minute timer later.",
                    "I may set a ten-minute reminder later.",
                    "Perhaps I will use a ten-minute timer later.",
                ),
            ),
            (
                (
                    "That reminder is working fine.",
                    "The reminder is useful as it is.",
                    "I like the current reminder.",
                ),
                (
                    "That timer is working fine.",
                    "The timer is useful as it is.",
                    "I like the current timer.",
                ),
            ),
            (
                ("Thanks.", "Got it.", "Understood."),
                ("Okay.", "Noted.", "All right."),
            ),
        )
        twin = f"f12-t{case:02d}"

        async def side(label: str, side_index: int) -> _BuiltState:
            builder = self._builder(f"{twin}-{label}", variant_id)
            text = texts[case - 1][side_index][variant]
            timer_id: str | None = None
            if case == 5:
                task = _TASKS[case - 1]
                _timer_event, timer_id = await self._schedule(
                    builder,
                    text=_recurring_request(task, "five minutes", variant),
                    interval_ms=300_000,
                    message=task,
                )
            event_id, state = await builder.capture_snapshot(text)
            if case in {1, 6}:
                tempting: Action = RespondAction(
                    type="respond",
                    reply_to_event_id=event_id,
                    text="I can help if you want to continue.",
                )
            elif case == 2:
                tempting = DelegateAction(
                    type="delegate",
                    fact=_span(event_id, text),
                    tool="lookup",
                    args=LookupArgs(query=text.rstrip(".")),
                )
            elif case == 3:
                target = "cat" if side_index == 0 else "fox"
                tempting = MarkAction(
                    type="mark",
                    instruction=_span(event_id, text),
                    target=_span(event_id, text, target),
                )
            elif case == 4:
                tempting = ScheduleAction(
                    type="schedule",
                    instruction=_span(event_id, text),
                    interval_ms=(5 if side_index == 0 else 10) * 60_000,
                    message="check later",
                )
            else:
                assert timer_id is not None
                tempting = CancelAction(
                    type="cancel",
                    instruction=_span(event_id, text),
                    target=CancelTimerTarget(kind="timer", timer_id=timer_id),
                )
            return await self._finish(
                builder,
                user_text=text,
                state=state,
                expected=_idle(),
                tempting=tempting,
            )

        return await side("a", 0), await side("b", 1)


async def build_probe_catalog(*, repository: Path, work_directory: Path) -> BuiltProbeCatalog:
    """Build and fully validate one complete WP14 catalog."""
    return await ProbeCatalogBuilder(
        repository=repository,
        work_directory=work_directory,
    ).build()
