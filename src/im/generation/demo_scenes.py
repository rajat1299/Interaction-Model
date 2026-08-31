"""Offline qualification for the five owner-approved Phase 5/6 film scenes."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
from pathlib import Path

from im.assets.model import (
    AssetProvenance,
    AssetRecord,
    CorpusFamily,
    LookupAssetPayload,
    Split,
    TemplateAssetPayload,
    TextAssetPayload,
    TextForm,
    TimerAssetPayload,
    TimerForm,
    artifact_digest,
    canonical_artifact_bytes,
)
from im.assets.registry import AssetRegistry
from im.assets.validate import validate_registry
from im.config import RuntimeConfig
from im.decision_trace import film_replay, read_traces
from im.generation.packaging import SplitLedger, SplitLedgerEntry
from im.generation.runtime import RuntimeIngestionHarness, TimedDecision
from im.policy.base import Policy
from im.schema.events import ActionExecutedEvent, TimerFireEvent, ToolResultEvent
from im.tools import ScriptedToolResult

FORMAT_VERSION = "phase5-6-scripted-runtime-contract-qualification-v1"
OPAQUE_TEST_LEDGER = Path("review/phase1/g7-readiness-resubmission-2/split-ledger.json")
INCIDENT_PATH = Path("docs/phase6-boundary-incident-v1.json")
SOURCE_BINDINGS = (
    Path("client/src/film.ts"),
    Path("src/im/decision_trace.py"),
    Path("src/im/generation/demo_scenes.py"),
    Path("src/im/generation/runtime.py"),
    Path("src/im/policy/base.py"),
    Path("src/im/policy/phase3x_runtime.py"),
    Path("src/im/policy/vllm_semantic.py"),
    Path("src/im/server.py"),
    Path("src/im/tick.py"),
)


class HeroBehavior(StrEnum):
    LOOKUP = "held_lookup_then_integrate"
    ANIMAL_MARKS = "animal_marks"
    FILLER_MARKS = "filler_marks"
    IDLE = "ordinary_typing_idle"
    TIMER = "recurring_timer_cancel"


@dataclass(frozen=True, slots=True)
class DemoVariant:
    """One standalone, deterministic, DEMO-only film take."""

    scenario_id: str
    hero: HeroBehavior
    variant: int
    text: str
    timing_seed: str
    template_id: str
    asset_id: str
    service_ms: tuple[int, ...]
    lookup_query: str | None = None
    lookup_result: str | None = None
    lookup_result_b: str | None = None
    lookup_no_result_code: str | None = None
    timer_interval_ms: int | None = None
    timer_message: str | None = None

    def __post_init__(self) -> None:
        if self.variant not in {1, 2, 3}:
            raise ValueError("demo variant must be 1, 2, or 3")
        if not self.scenario_id or not self.text or not self.timing_seed:
            raise ValueError("demo identity and text must be non-empty")
        if not self.service_ms or any(value < 0 for value in self.service_ms):
            raise ValueError("demo service times must be non-empty and non-negative")
        lookup = self.hero is HeroBehavior.LOOKUP
        timer = self.hero is HeroBehavior.TIMER
        complete_lookup = all(
            value is not None
            for value in (
                self.lookup_query,
                self.lookup_result,
                self.lookup_result_b,
                self.lookup_no_result_code,
            )
        )
        if lookup != complete_lookup:
            raise ValueError("lookup metadata must exist only for lookup variants")
        if timer != (self.timer_interval_ms is not None and self.timer_message is not None):
            raise ValueError("timer metadata must exist only for timer variants")


@dataclass(frozen=True, slots=True)
class DemoRunResult:
    scenario_id: str
    hero: HeroBehavior
    variant: int
    action_types: tuple[str, ...]
    executed_actions: tuple[dict[str, object], ...]
    trace_payloads: tuple[dict[str, object], ...]
    trace_sha256s: tuple[str, ...]
    policy_call_count: int
    timer_fire_count: int
    tool_result_count: int
    post_cancel_silent: bool | None
    film_replay_payload: dict[str, object]


def _id(kind: str, hero: HeroBehavior, variant: int) -> str:
    digest = artifact_digest({"format": FORMAT_VERSION, "hero": hero, "variant": variant})
    return f"a_phase6_{kind}_{digest.removeprefix('sha256:')[:20]}"


def build_demo_variants() -> tuple[DemoVariant, ...]:
    """Return exactly five scenes with three fixed variants apiece."""
    variants: list[DemoVariant] = []
    lookup_rows = (
        ("Velin Quay", 41, (0, 20, 0, 0)),
        ("Marrow Field", 67, (7, 35, 4, 9)),
        ("Tessell Bay", 83, (15, 35, 8, 13)),
    )
    for ordinal, (subject, score, service) in enumerate(lookup_rows, start=1):
        hero = HeroBehavior.LOOKUP
        query = f"{subject} score"
        variants.append(
            DemoVariant(
                scenario_id=f"phase6-{hero.value}-v{ordinal}",
                hero=hero,
                variant=ordinal,
                text=f"Find the {query} while I draft this sentence.",
                timing_seed=f"phase6:{hero.value}:{ordinal}",
                template_id=_id("template", hero, ordinal),
                asset_id=_id("asset", hero, ordinal),
                service_ms=service,
                lookup_query=query,
                lookup_result=f"{subject} {score}",
                lookup_result_b=f"{subject} {score + 11}",
                lookup_no_result_code=f"phase6_lookup_absent_{ordinal}",
            )
        )

    animal_texts = (
        "Mark the animals in this field note: quokka, kestrel, and wombat.",
        "Mark the animals in this margin line: wombat, quokka, then kestrel.",
        "Mark the animals in this clean copy: kestrel beside quokka and wombat.",
    )
    filler_texts = (
        "In the interview notes, mark filler words. I, um, was, you know, uncertain.",
        "In the rehearsal notes, mark filler words. We, you know, were, um, early.",
        "In the transcript, mark filler words. It was, um, you know, unfinished.",
    )
    idle_texts = (
        "The kettle clicked while I rewrote the opening line.",
        "A quiet cursor moved through the cedar paragraph.",
        "I am still drafting the middle sentence about rain.",
    )
    for hero, rows, service in (
        (HeroBehavior.ANIMAL_MARKS, animal_texts, (0, 4, 8, 0)),
        (HeroBehavior.FILLER_MARKS, filler_texts, (0, 6, 0)),
        (HeroBehavior.IDLE, idle_texts, (5,)),
    ):
        for ordinal, text in enumerate(rows, start=1):
            variants.append(
                DemoVariant(
                    scenario_id=f"phase6-{hero.value}-v{ordinal}",
                    hero=hero,
                    variant=ordinal,
                    text=text,
                    timing_seed=f"phase6:{hero.value}:{ordinal}",
                    template_id=_id("template", hero, ordinal),
                    asset_id=_id("asset", hero, ordinal),
                    service_ms=tuple(value + ordinal - 1 for value in service),
                )
            )

    timer_rows = (
        (1_000, "stretch", (0, 0, 0, 0, 0, 0, 0, 0)),
        (2_000, "check the window", (3, 0, 5, 0, 7, 0, 3, 0)),
        (3_000, "turn the notebook", (9, 2, 11, 2, 13, 2, 9, 2)),
    )
    words = {1_000: "one second", 2_000: "two seconds", 3_000: "three seconds"}
    for ordinal, (interval_ms, message, service) in enumerate(timer_rows, start=1):
        hero = HeroBehavior.TIMER
        text = f"Remind me every {words[interval_ms]} to {message}."
        variants.append(
            DemoVariant(
                scenario_id=f"phase6-{hero.value}-v{ordinal}",
                hero=hero,
                variant=ordinal,
                text=text,
                timing_seed=f"phase6:{hero.value}:{ordinal}",
                template_id=_id("template", hero, ordinal),
                asset_id=_id("asset", hero, ordinal),
                service_ms=service,
                timer_interval_ms=interval_ms,
                timer_message=message,
            )
        )
    return tuple(sorted(variants, key=lambda item: item.scenario_id))


def _snapshot(text: str, *, activity: str) -> dict[str, object]:
    cursor = len(text.encode("utf-16-le")) // 2
    return {
        "text": text,
        "selection_start": cursor,
        "selection_end": cursor,
        "is_composing": False,
        "input_type": "insertText",
        "activity": activity,
        "client_ts": 0,
    }


def _visible(text: str, *, source: str = "u0") -> dict[str, object]:
    return {"kind": "visible", "source": source, "text": text, "occurrence": 0}


def _idle(reason: str = "no_trigger", related: str | None = None) -> dict[str, object]:
    return {"type": "idle", "reason": reason, "related": related}


def _intents(variant: DemoVariant) -> tuple[dict[str, object], ...]:
    if variant.hero is HeroBehavior.LOOKUP:
        assert variant.lookup_query is not None
        return (
            {
                "type": "delegate",
                "source": "u0",
                "query": variant.lookup_query,
                "occurrence": 0,
            },
            _idle("awaiting_tool", "p0"),
            _idle("typing_active"),
            {"type": "integrate", "result": "r0"},
        )
    if variant.hero is HeroBehavior.ANIMAL_MARKS:
        return tuple(
            {
                "type": "mark",
                "instruction": _visible("Mark the animals"),
                "source": "u0",
                "text": animal,
                "occurrence": 0,
            }
            for animal in ("quokka", "kestrel", "wombat")
        ) + (_idle(),)
    if variant.hero is HeroBehavior.FILLER_MARKS:
        return tuple(
            {
                "type": "mark",
                "instruction": _visible("mark filler words"),
                "source": "u0",
                "text": filler,
                "occurrence": 0,
            }
            for filler in ("um", "you know")
        ) + (_idle(),)
    if variant.hero is HeroBehavior.IDLE:
        return (_idle("typing_active"),)
    assert variant.hero is HeroBehavior.TIMER
    return (
        {"type": "schedule", "instruction": _visible(variant.text)},
        _idle(),
        {"type": "nudge", "fire": "f0"},
        _idle(),
        {"type": "nudge", "fire": "f1"},
        _idle(),
        {
            "type": "cancel",
            "instruction": _visible("Cancel this reminder.", source="u1"),
            "target": {"kind": "timer", "timer": "t0"},
        },
        _idle(),
    )


def _asset_payload(variant: DemoVariant):
    if variant.hero is HeroBehavior.LOOKUP:
        assert (
            variant.lookup_query is not None
            and variant.lookup_result is not None
            and variant.lookup_result_b is not None
            and variant.lookup_no_result_code is not None
        )
        return LookupAssetPayload(
            query=variant.lookup_query,
            result_a=variant.lookup_result,
            result_b=variant.lookup_result_b,
            no_result_code=variant.lookup_no_result_code,
        )
    if variant.hero is HeroBehavior.TIMER:
        return TimerAssetPayload(
            instruction=variant.text,
            form=TimerForm.SUPPORTED,
            interval_ms=variant.timer_interval_ms,
            message=variant.timer_message,
        )
    return TextAssetPayload(
        text=variant.text,
        form=TextForm.NEUTRAL if variant.hero is HeroBehavior.IDLE else TextForm.DIRECT,
    )


def demo_asset_registry() -> AssetRegistry:
    """Build local DEMO-only assets without touching a sealed registry."""
    records: list[AssetRecord] = []
    family_by_hero = {
        HeroBehavior.LOOKUP: CorpusFamily.LOOKUP_LIVE,
        HeroBehavior.ANIMAL_MARKS: CorpusFamily.MARK_POSITIVE,
        HeroBehavior.FILLER_MARKS: CorpusFamily.MARK_POSITIVE,
        HeroBehavior.IDLE: CorpusFamily.NEUTRAL_TYPING,
        HeroBehavior.TIMER: CorpusFamily.TIMER_NORMAL,
    }
    for variant in build_demo_variants():
        family = family_by_hero[variant.hero]
        payload = _asset_payload(variant)
        protected_values = [variant.scenario_id]
        if variant.lookup_result is not None:
            protected_values.extend((variant.lookup_result, variant.lookup_result_b or ""))
        asset = AssetRecord.build(
            asset_id=variant.asset_id,
            split=Split.DEMO,
            payload=payload,
            provenance=AssetProvenance.SEED_AUTHORED,
            protected_values=tuple(protected_values),
            coverage=(family,),
        )
        template = AssetRecord.build(
            asset_id=variant.template_id,
            split=Split.DEMO,
            payload=TemplateAssetPayload(
                expands_kind=payload.kind,
                grammar=f"Phase 6 fixed film take {variant.scenario_id} uses {{seed}} exactly.",
                seed_asset_ids=(asset.asset_id,),
            ),
            provenance=AssetProvenance.SEED_AUTHORED,
            coverage=(family,),
        )
        records.extend((asset, template))
    return AssetRegistry(assets=tuple(records))


def validate_demo_assets() -> tuple[str, ...]:
    report = validate_registry(demo_asset_registry(), require_all_families=False)
    return tuple(issue.code.value for issue in report.issues)


def _tool_script(variant: DemoVariant):
    if variant.lookup_result is None:
        return None

    def script(_action: object) -> ScriptedToolResult:
        return ScriptedToolResult(latency_ms=50, data=variant.lookup_result)

    return script


def _traces(harness: RuntimeIngestionHarness) -> tuple[dict[str, object], ...]:
    return tuple(trace.model_dump(mode="json") for trace in read_traces(harness.session.store))


async def run_demo_variant(
    variant: DemoVariant, directory: Path, *, policy: Policy | None = None
) -> DemoRunResult:
    """Run one take once through the real virtual-time RuntimeSession."""
    intents = _intents(variant)
    if len(intents) != len(variant.service_ms):
        raise ValueError("demo intent count does not match fixed service times")
    config = RuntimeConfig(min_timer_interval_ms=1_000, max_timer_interval_ms=10_000)
    harness = RuntimeIngestionHarness(
        session_id=f"s_{variant.scenario_id.replace('-', '_')}",
        directory=directory,
        decisions=(
            tuple(
                TimedDecision(service_ms, intent)
                for service_ms, intent in zip(variant.service_ms, intents, strict=True)
            )
            if policy is None
            else None
        ),
        config=config,
        tool_script=_tool_script(variant),
        semantic_intents=policy is None,
        external_policy=policy,
        external_decision_count=len(intents) if policy is not None else None,
    )
    post_cancel_silent: bool | None = None
    try:
        harness.start()
        activity = "active" if variant.hero is HeroBehavior.IDLE else "paused"
        harness.accept_snapshot(_snapshot(variant.text, activity=activity))
        if variant.hero is HeroBehavior.LOOKUP:
            await harness.drive_until_decisions(1)
            active = f"{variant.text} The next sentence is still moving."
            harness.accept_snapshot(_snapshot(active, activity="active"))
            await harness.drive_until_decisions(3)
            harness.accept_snapshot(_snapshot(active, activity="paused"))
            await harness.drive_until_decisions(4)
        elif variant.hero is HeroBehavior.TIMER:
            await harness.drive_until_decisions(6)
            before_cancel = sum(
                isinstance(record.event, TimerFireEvent)
                for record in harness.session.store.policy_records()
            )
            harness.accept_snapshot(_snapshot("Cancel this reminder.", activity="paused"))
            await harness.drive_until_decisions(8)
            assert variant.timer_interval_ms is not None
            await harness.advance_ms(variant.timer_interval_ms * 2)
            after_cancel = sum(
                isinstance(record.event, TimerFireEvent)
                for record in harness.session.store.policy_records()
            )
            post_cancel_silent = before_cancel == after_cancel
        else:
            await harness.drive_until_decisions(len(intents))
        await harness.wait_until_idle()

        records = harness.session.store.policy_records()
        actions = tuple(
            record.event.payload.action.type
            for record in records
            if isinstance(record.event, ActionExecutedEvent)
        )
        executed_actions = tuple(
            record.event.payload.action.model_dump(mode="json")
            for record in records
            if isinstance(record.event, ActionExecutedEvent)
        )
        traces = _traces(harness)
        return DemoRunResult(
            scenario_id=variant.scenario_id,
            hero=variant.hero,
            variant=variant.variant,
            action_types=actions,
            executed_actions=executed_actions,
            trace_payloads=traces,
            trace_sha256s=tuple(artifact_digest(trace) for trace in traces),
            policy_call_count=harness.policy.call_count,
            timer_fire_count=sum(isinstance(record.event, TimerFireEvent) for record in records),
            tool_result_count=sum(isinstance(record.event, ToolResultEvent) for record in records),
            post_cancel_silent=post_cancel_silent,
            film_replay_payload=film_replay(harness.session.store, harness.session.session_id),
        )
    finally:
        await harness.close()


def _value_digest(label: str, value: object) -> str:
    return artifact_digest({label: value})


def build_demo_ledger(results: tuple[DemoRunResult, ...]) -> SplitLedger:
    """Build an opaque ledger for the executed takes."""
    by_id = {item.scenario_id: item for item in results}
    entries: list[SplitLedgerEntry] = []
    for variant in build_demo_variants():
        result = by_id[variant.scenario_id]
        lookup_values: set[str] = set()
        tool_results: set[str] = set()
        timer_messages: set[str] = set()
        if variant.lookup_query is not None and variant.lookup_result is not None:
            payload = _asset_payload(variant)
            assert isinstance(payload, LookupAssetPayload)
            lookup_values.update(
                _value_digest("lookup_value", value)
                for value in (
                    payload.query,
                    payload.result_a,
                    payload.result_b,
                    payload.no_result_code,
                )
            )
            for value in (
                variant.lookup_result,
                variant.lookup_result_b,
            ):
                lookup_values.add(_value_digest("lookup_value", value))
            tool_results.add(_value_digest("tool_result", variant.lookup_result))
        if variant.timer_message is not None:
            timer_messages.add(_value_digest("timer_message", variant.timer_message))
        entries.append(
            SplitLedgerEntry(
                split=Split.DEMO,
                stream_sha256=artifact_digest(
                    {"scenario_id": variant.scenario_id, "trace_sha256s": result.trace_sha256s}
                ),
                template_id=variant.template_id,
                asset_ids=(variant.asset_id,),
                timing_seed_material_sha256=_value_digest("raw_timing_seed", variant.timing_seed),
                lookup_value_sha256s=tuple(sorted(lookup_values)),
                tool_result_sha256s=tuple(sorted(tool_results)),
                timer_message_sha256s=tuple(sorted(timer_messages)),
            )
        )
    return SplitLedger(entries=tuple(sorted(entries, key=lambda entry: entry.stream_sha256)))


_LEDGER_KEYS = {
    "split",
    "stream_sha256",
    "template_id",
    "asset_ids",
    "timing_seed_material_sha256",
    "lookup_value_sha256s",
    "tool_result_sha256s",
    "timer_message_sha256s",
}


def load_opaque_test_ledger(path: Path) -> SplitLedger:
    """Load only the closed ID and digest fields from a canonical TEST ledger."""
    data = path.read_bytes()
    payload = json.loads(data)
    if not isinstance(payload, dict) or set(payload) != {"format_version", "entries"}:
        raise ValueError("opaque ledger has an unexpected top-level shape")
    if canonical_artifact_bytes(payload) != data:
        raise ValueError("opaque ledger is not canonical")
    rows = payload["entries"]
    if not isinstance(rows, list) or not rows:
        raise ValueError("opaque ledger has no entries")
    entries: list[SplitLedgerEntry] = []
    for row in rows:
        if not isinstance(row, dict) or set(row) != _LEDGER_KEYS or row.get("split") != "test":
            raise ValueError("opaque TEST ledger contains a non-opaque or non-TEST row")
        entries.append(
            SplitLedgerEntry(
                split=row["split"],
                stream_sha256=row["stream_sha256"],
                template_id=row["template_id"],
                asset_ids=tuple(row["asset_ids"]),
                timing_seed_material_sha256=row["timing_seed_material_sha256"],
                lookup_value_sha256s=tuple(row["lookup_value_sha256s"]),
                tool_result_sha256s=tuple(row["tool_result_sha256s"]),
                timer_message_sha256s=tuple(row["timer_message_sha256s"]),
            )
        )
    return SplitLedger(entries=tuple(entries))


def prove_test_overlap(demo: SplitLedger, test: SplitLedger) -> SplitLedger:
    """Reuse SplitLedger's canonical cross-split rejection over DEMO and opaque TEST."""
    return SplitLedger(
        entries=tuple(sorted((*demo.entries, *test.entries), key=lambda item: item.stream_sha256))
    )


def hero_contract(result: DemoRunResult, variant: DemoVariant) -> bool:
    """Bind one proof row to the exact owner-approved behavior and payloads."""
    traces = result.trace_payloads
    expected_intents = _intents(variant)
    if (
        result.policy_call_count != len(traces)
        or len(traces) != len(expected_intents)
        or any(
            trace.get("parsed_raw_intent") != intent
            for trace, intent in zip(traces, expected_intents, strict=True)
        )
        or any(
            not isinstance(trace.get("resolution"), dict)
            or trace["resolution"].get("status")
            not in {"resolved_action", "canonical_result_fallback"}
            or not isinstance(trace.get("initial_license"), dict)
            or trace["initial_license"].get("status") != "allowed"
            or not isinstance(trace.get("pending_license"), dict)
            or trace["pending_license"].get("status") != "allowed"
            or isinstance(trace.get("fresh_license"), dict)
            and trace["fresh_license"].get("status") == "blocked"
            for trace in traces
        )
    ):
        return False
    if variant.hero is HeroBehavior.LOOKUP:
        expected_text = variant.lookup_result
        return (
            result.action_types == ("delegate", "integrate")
            and result.tool_result_count == 1
            and all(
                traces[index].get("executed_event") is None and traces[index].get("effect") is None
                for index in (1, 2)
            )
            and result.executed_actions[0]["args"]["query"] == variant.lookup_query
            and result.executed_actions[0]["fact"]["text"] == variant.lookup_query
            and result.executed_actions[1]["text"] == expected_text
        )
    if variant.hero is HeroBehavior.ANIMAL_MARKS:
        return result.action_types == ("mark", "mark", "mark") and [
            action["target"]["text"] for action in result.executed_actions
        ] == ["quokka", "kestrel", "wombat"]
    if variant.hero is HeroBehavior.FILLER_MARKS:
        return result.action_types == ("mark", "mark") and [
            action["target"]["text"] for action in result.executed_actions
        ] == ["um", "you know"]
    if variant.hero is HeroBehavior.IDLE:
        return (
            result.action_types == ()
            and result.executed_actions == ()
            and len(traces) == 1
            and traces[0].get("executed_event") is None
            and traces[0].get("effect") is None
        )
    if result.action_types != ("schedule", "nudge", "nudge", "cancel"):
        return False
    schedule, _first_nudge, _second_nudge, cancel = result.executed_actions
    schedule_effect = traces[0].get("effect")
    scheduled_timers = (
        schedule_effect.get("timers", []) if isinstance(schedule_effect, dict) else []
    )
    return (
        schedule["instruction"]["text"] == variant.text
        and schedule["interval_ms"] == variant.timer_interval_ms
        and schedule["message"] == variant.timer_message
        and len(scheduled_timers) == 1
        and cancel["target"] == {"kind": "timer", "timer_id": scheduled_timers[0].get("timer_id")}
        and result.timer_fire_count == 2
        and result.post_cancel_silent is True
    )


def qualification_proof(
    results: tuple[DemoRunResult, ...], *, repository_root: Path
) -> dict[str, object]:
    demo_ledger = build_demo_ledger(results)
    test_path = repository_root / OPAQUE_TEST_LEDGER
    test_ledger = load_opaque_test_ledger(test_path)
    combined = prove_test_overlap(demo_ledger, test_ledger)
    variants = {variant.scenario_id: variant for variant in build_demo_variants()}
    hero_contracts = {
        result.scenario_id: hero_contract(result, variants[result.scenario_id])
        for result in results
    }
    incident_path = repository_root / INCIDENT_PATH
    return {
        "format_version": FORMAT_VERSION,
        "evidence_kind": "scripted_offline_runtime_contract_qualification",
        "frozen_model_qualification": False,
        "method": {
            "hypothesis": "at least one fixed variant per hero behavior completes without retry",
            "prediction": (
                "contiguous marks resolve; the committed lookup remains held out of the document "
                "during active typing and integrates after yield; idle has no effect; canceled "
                "timers remain silent"
            ),
            "smallest_test": "run every fixed scripted intent once through RuntimeIngestionHarness",
            "kill_conditions": [
                "public_schema_change",
                "cross_split_overlap",
                "technical_replay_sampling",
                "gold_substitution_or_retry",
                "non_atomic_terminal_trace",
                "all_three_variants_fail",
            ],
        },
        "scenario_count": len(results),
        "hero_counts": {
            hero.value: sum(result.hero is hero for result in results) for hero in HeroBehavior
        },
        "all_scripted_runtime_contract_variants_completed": all(hero_contracts.values()),
        "hero_contracts": hero_contracts,
        "raw_trace_count": sum(len(result.trace_payloads) for result in results),
        "raw_trace_set_sha256": artifact_digest(
            sorted(digest for result in results for digest in result.trace_sha256s)
        ),
        "visible_asset_validation": {
            "scope": "demo_only",
            "issue_codes": list(validate_demo_assets()),
            "train_dev_comparison": "informational_unknown_not_required_for_qualitative_demo",
        },
        "demo_ledger_sha256": demo_ledger.sha256,
        "opaque_test_ledger": {
            "path": OPAQUE_TEST_LEDGER.as_posix(),
            "sha256": artifact_digest(json.loads(test_path.read_bytes())),
            "entry_count": len(test_ledger.entries),
        },
        "combined_demo_test_opaque_ledger_sha256": combined.sha256,
        "cross_split_overlap": {"test": 0, "train": None, "dev": None},
        "boundary_incident": {
            "path": INCIDENT_PATH.as_posix(),
            "sha256": _file_digest(incident_path),
            "classification": ("disclosed_process_deviation_not_proven_dataset_contamination"),
            "test_boundary_was_unbroken": False,
        },
        "source_bindings": {
            path.as_posix(): _file_digest(repository_root / path) for path in SOURCE_BINDINGS
        },
        "technical_replay_scope": (
            "durable in SQLite and replayable while the originating server process retains "
            "the stopped session; process-restart read-only reopen is not supported"
        ),
        "qualification_complete": False,
        "remaining_blockers_to_frozen_model_demo_qualification": [
            "frozen-model checkpoint qualification has not been authorized or run"
        ],
        "informational_limitations": [
            "TRAIN and DEV full-dimension overlap remain unknown; no zero-overlap claim is made",
            "process-restart technical replay lacks a read-only Store reopen capability",
        ],
        "results": [
            {
                "scenario_id": result.scenario_id,
                "hero": result.hero.value,
                "variant": result.variant,
                "action_types": list(result.action_types),
                "policy_call_count": result.policy_call_count,
                "trace_count": len(result.trace_payloads),
                "timer_fire_count": result.timer_fire_count,
                "tool_result_count": result.tool_result_count,
                "post_cancel_silent": result.post_cancel_silent,
            }
            for result in sorted(results, key=lambda item: item.scenario_id)
        ],
    }


def render_qualification_proof(proof: dict[str, object]) -> bytes:
    return canonical_artifact_bytes(proof)


def _file_digest(path: Path) -> str:
    return f"sha256:{sha256(path.read_bytes()).hexdigest()}"
