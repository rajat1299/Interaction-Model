"""Closed C5 twin and lookup-provenance groups.

The runtime owns stream validity.  This module only binds independently valid
streams to the one deliberate construction-time variation that produced them.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import StrEnum
from hashlib import sha256
from pathlib import Path

from im.assets.model import (
    AssetRecord,
    CorpusFamily,
    LookupAssetPayload,
    Split,
    artifact_digest,
    canonical_artifact_bytes,
)
from im.assets.registry import AssetBundle, AssetRegistry
from im.generation.scenario_catalog import _build_selected_family_program
from im.generation.scenarios import (
    CounterfactualDeclaration,
    GeneratedScenario,
    ScenarioProgram,
    execute_scenario,
    select_approved_scenario_inputs,
    validate_generated_scenario,
)
from im.schema.actions import (
    DelegateAction,
    IdleAction,
    IdleReason,
    IntegrateAction,
    MarkAction,
    NudgeAction,
    SkipAction,
)
from im.schema.events import ActionExecutedEvent, ToolResultEvent
from im.schema.textspan import utf16_len
from im.serialize import parse_event

_GROUP_VERSION = "phase1-c5-counterfactual-groups-v1"


class TwinAxis(StrEnum):
    DIRECTNESS = "directness"
    LEXICAL_BOUNDARY = "lexical_boundary"
    TOOL_LATENCY = "tool_latency"
    REQUEST_PRESENCE = "request_presence"
    TIMER_STATUS = "timer_status"
    FLOOR_STATE = "floor_state"
    TOPIC_FRESHNESS = "topic_freshness"
    ROLLOVER_BOUNDARY = "rollover_boundary"


TWIN_AXIS_VALUES: dict[TwinAxis, tuple[str, str]] = {
    TwinAxis.DIRECTNESS: ("direct", "quoted"),
    TwinAxis.LEXICAL_BOUNDARY: ("standalone", "embedded"),
    TwinAxis.TOOL_LATENCY: ("700ms", "8000ms"),
    TwinAxis.REQUEST_PRESENCE: ("absent", "pending"),
    TwinAxis.TIMER_STATUS: ("active", "canceled"),
    TwinAxis.FLOOR_STATE: ("typing", "paused"),
    TwinAxis.TOPIC_FRESHNESS: ("current", "changed"),
    TwinAxis.ROLLOVER_BOUNDARY: ("pre", "post"),
}

_AXIS_FAMILY = {
    TwinAxis.DIRECTNESS: CorpusFamily.MARK_POSITIVE,
    TwinAxis.LEXICAL_BOUNDARY: CorpusFamily.MARK_POSITIVE,
    TwinAxis.TOOL_LATENCY: CorpusFamily.LOOKUP_LIVE,
    TwinAxis.REQUEST_PRESENCE: CorpusFamily.LOOKUP_DUPLICATE,
    TwinAxis.TIMER_STATUS: CorpusFamily.TIMER_CANCEL,
    TwinAxis.FLOOR_STATE: CorpusFamily.TIMER_CONTENTION,
    TwinAxis.TOPIC_FRESHNESS: CorpusFamily.LOOKUP_STALE,
    TwinAxis.ROLLOVER_BOUNDARY: CorpusFamily.ROLLOVER,
}
_AXIS_PERTURBATION = {
    TwinAxis.DIRECTNESS: "mark_targeting",
    TwinAxis.LEXICAL_BOUNDARY: "mark_targeting",
    TwinAxis.TOOL_LATENCY: "tool_result",
    TwinAxis.REQUEST_PRESENCE: "pending_tool_pressure",
    TwinAxis.TIMER_STATUS: "timer_cancel_race",
    TwinAxis.FLOOR_STATE: "external_event_contention",
    TwinAxis.TOPIC_FRESHNESS: "topic_change",
    TwinAxis.ROLLOVER_BOUNDARY: "state_checkpoint",
}


class CounterfactualGroupError(ValueError):
    """Twin or triplet linkage is incomplete, mutated, or causally inconsistent."""


def _bytes_digest(value: bytes) -> str:
    return f"sha256:{sha256(value).hexdigest()}"


def _group_id(kind: str, variable: str, common_inputs: dict[str, object]) -> str:
    return (
        f"g_{artifact_digest({'kind': kind, 'variable': variable, 'common': common_inputs})[7:31]}"
    )


def _common_inputs(
    *,
    family: CorpusFamily,
    bundle: AssetBundle,
    template: AssetRecord,
    master_seed: str,
    program: ScenarioProgram,
) -> dict[str, object]:
    plan = program.timing_plan
    return {
        "version": _GROUP_VERSION,
        "family": family.value,
        "split": bundle.split.value,
        "master_seed": master_seed,
        "template": {"asset_id": template.asset_id, "content_sha256": template.content_sha256},
        "assets": [
            {"asset_id": asset.asset_id, "content_sha256": asset.content_sha256}
            for asset in bundle.assets
        ],
        "timing": {
            "seed": plan.seed.seed,
            "seed_id": plan.seed.timing_seed_id,
            "profile_id": plan.profile_id,
            "rng_version": plan.rng_version,
            "population": plan.population.value,
        },
    }


def _member_id(value: str) -> str:
    return value if value[0].isalpha() else f"v_{value}"


def _declaration(
    *,
    kind: str,
    group_id: str,
    member_id: str,
    member_ids: tuple[str, ...],
    flipped_perturbation: str,
) -> CounterfactualDeclaration:
    return CounterfactualDeclaration(
        kind=kind,
        group_id=group_id,
        member_id=member_id,
        member_ids=member_ids,
        flipped_perturbation=flipped_perturbation,
    )


@dataclass(frozen=True, slots=True)
class TwinPrograms:
    group_id: str
    axis: TwinAxis
    master_seed: str
    common_inputs: bytes
    common_inputs_sha256: str
    variant_inputs: tuple[bytes, bytes]
    variant_inputs_sha256: tuple[str, str]
    programs: tuple[ScenarioProgram, ScenarioProgram]

    def __post_init__(self) -> None:
        if self.axis not in TWIN_AXIS_VALUES:
            raise CounterfactualGroupError("unknown twin axis")
        if self.common_inputs_sha256 != artifact_digest(json.loads(self.common_inputs)):
            raise CounterfactualGroupError("common input hash does not match canonical inputs")
        if len(self.variant_inputs) != 2 or len(self.programs) != 2:
            raise CounterfactualGroupError("a twin requires exactly two siblings")
        if self.variant_inputs_sha256 != tuple(
            _bytes_digest(value) for value in self.variant_inputs
        ):
            raise CounterfactualGroupError("variant input hashes do not match canonical inputs")


def build_twin_programs(
    axis: TwinAxis | str,
    registry: AssetRegistry,
    *,
    split: Split | str,
    template_id: str,
    asset_ids: tuple[str, ...],
    master_seed: str,
) -> TwinPrograms:
    """Construct exactly the two fixed variants from one recipe and master seed."""
    axis = TwinAxis(axis)
    family = _AXIS_FAMILY[axis]
    values = TWIN_AXIS_VALUES[axis]
    bundle, template = select_approved_scenario_inputs(
        registry,
        split=split,
        template_id=template_id,
        asset_ids=asset_ids,
    )
    probe = _build_selected_family_program(
        family,
        bundle,
        template,
        master_seed,
        _variant=(axis.value, values[0]),
    )
    common = _common_inputs(
        family=family,
        bundle=bundle,
        template=template,
        master_seed=master_seed,
        program=probe,
    )
    group_id = _group_id("twin", axis.value, common)
    member_ids = tuple(sorted(_member_id(value) for value in values))
    programs = tuple(
        _build_selected_family_program(
            family,
            bundle,
            template,
            master_seed,
            _variant=(axis.value, value),
            counterfactual=_declaration(
                kind="twin",
                group_id=group_id,
                member_id=_member_id(value),
                member_ids=member_ids,
                flipped_perturbation=_AXIS_PERTURBATION[axis],
            ),
        )
        for value in values
    )
    variants = tuple(program.canonical_input_bytes for program in programs)
    return TwinPrograms(
        group_id=group_id,
        axis=axis,
        master_seed=master_seed,
        common_inputs=canonical_artifact_bytes(common),
        common_inputs_sha256=artifact_digest(common),
        variant_inputs=variants,
        variant_inputs_sha256=tuple(program.input_hash for program in programs),
        programs=programs,
    )


@dataclass(frozen=True, slots=True)
class ByteDiffEvidence:
    left_stream_sha256: str
    right_stream_sha256: str
    first_difference: int | None
    differing_bytes: int
    left_size: int
    right_size: int

    @classmethod
    def between(
        cls, left: bytes, right: bytes, left_hash: str, right_hash: str
    ) -> ByteDiffEvidence:
        shared = min(len(left), len(right))
        differing = sum(one != two for one, two in zip(left[:shared], right[:shared], strict=True))
        differing += abs(len(left) - len(right))
        first = next(
            (index for index, pair in enumerate(zip(left, right)) if pair[0] != pair[1]), None
        )
        if first is None and len(left) != len(right):
            first = shared
        return cls(left_hash, right_hash, first, differing, len(left), len(right))


@dataclass(frozen=True, slots=True)
class TwinMember:
    value: str
    generated: GeneratedScenario
    variant_inputs_sha256: str


@dataclass(frozen=True, slots=True)
class TwinGroup:
    programs: TwinPrograms
    members: tuple[TwinMember, TwinMember]
    byte_diff: ByteDiffEvidence
    canonical_bytes: bytes = field(init=False)
    sha256: str = field(init=False)

    def __post_init__(self) -> None:
        value = {
            "group_id": self.programs.group_id,
            "axis": self.programs.axis.value,
            "master_seed": self.programs.master_seed,
            "common_inputs_sha256": self.programs.common_inputs_sha256,
            "members": [
                {
                    "value": member.value,
                    "stream_sha256": member.generated.stream.sha256,
                    "sibling_stream_sha256s": tuple(
                        sibling.generated.stream.sha256
                        for sibling in self.members
                        if sibling.value != member.value
                    ),
                    "capture_sha256": member.generated.stream.capture_sha256,
                    "sidecar_sha256": member.generated.sidecar.sha256,
                    "variant_inputs_sha256": member.variant_inputs_sha256,
                }
                for member in self.members
            ],
            "byte_diff": {
                "left_stream_sha256": self.byte_diff.left_stream_sha256,
                "right_stream_sha256": self.byte_diff.right_stream_sha256,
                "first_difference": self.byte_diff.first_difference,
                "differing_bytes": self.byte_diff.differing_bytes,
                "left_size": self.byte_diff.left_size,
                "right_size": self.byte_diff.right_size,
            },
        }
        canonical = canonical_artifact_bytes(value)
        object.__setattr__(self, "canonical_bytes", canonical)
        object.__setattr__(self, "sha256", artifact_digest(value))


async def execute_twin_programs(
    programs: TwinPrograms, *, directory: Path, repository_root: Path | None = None
) -> TwinGroup:
    """Run siblings sequentially; each gets its own real production session."""
    generated = []
    for value, program in zip(TWIN_AXIS_VALUES[programs.axis], programs.programs, strict=True):
        generated.append(
            await execute_scenario(
                program,
                session_id=f"s_{programs.group_id}_{value}",
                directory=directory / value,
                repository_root=repository_root,
            )
        )
    members = tuple(
        TwinMember(value, scenario, digest)
        for value, scenario, digest in zip(
            TWIN_AXIS_VALUES[programs.axis],
            generated,
            programs.variant_inputs_sha256,
            strict=True,
        )
    )
    left, right = members
    return TwinGroup(
        programs=programs,
        members=members,
        byte_diff=ByteDiffEvidence.between(
            left.generated.stream.canonical_segment_bytes,
            right.generated.stream.canonical_segment_bytes,
            left.generated.stream.sha256,
            right.generated.stream.sha256,
        ),
    )


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CounterfactualGroupError(message)


def _validate_link(
    generated: GeneratedScenario,
    *,
    kind: str,
    group_id: str,
    member_id: str,
    member_ids: tuple[str, ...],
    flipped_perturbation: str,
) -> None:
    sidecar = validate_generated_scenario(generated)
    link = sidecar.counterfactual
    _require(link is not None, "scenario sidecar is missing its counterfactual link")
    _require(link.kind.value == kind, "scenario sidecar has the wrong counterfactual kind")
    _require(link.group_id == group_id, "scenario sidecar has the wrong group id")
    _require(
        link.member_id == member_id and link.member_ids == member_ids, "sidecar member link differs"
    )
    _require(
        link.flipped_perturbation.value == flipped_perturbation,
        "scenario sidecar has the wrong flipped perturbation",
    )


def _validate_axis_effect(axis: TwinAxis, members: tuple[TwinMember, TwinMember]) -> None:
    """Check the observable state/action contrast owned by each fixed axis."""
    left, right = members
    left_program, right_program = left.generated.program, right.generated.program
    left_facts = left.generated.sidecar.decisions
    right_facts = right.generated.sidecar.decisions
    if axis is TwinAxis.DIRECTNESS:
        _require(
            any(isinstance(action, MarkAction) for action in left_program.actions)
            and not any(isinstance(action, MarkAction) for action in right_program.actions)
            and isinstance(right_program.actions[-1], IdleAction)
            and right_program.actions[-1].reason is IdleReason.INSTRUCTION_NOT_DIRECT,
            "directness does not produce the required mark/restraint contrast",
        )
    elif axis is TwinAxis.LEXICAL_BOUNDARY:
        _require(
            any(isinstance(action, MarkAction) for action in left_program.actions)
            and not any(isinstance(action, MarkAction) for action in right_program.actions)
            and isinstance(right_program.actions[-1], IdleAction)
            and right_program.actions[-1].reason is IdleReason.TYPING_ACTIVE,
            "lexical-boundary does not produce the required mark/restraint contrast",
        )
    elif axis is TwinAxis.TOOL_LATENCY:
        _require(
            left_program.tool_results[0].latency_ms == 700
            and right_program.tool_results[0].latency_ms == 8_000,
            "tool-latency twin does not isolate the fixed latency values",
        )
    elif axis is TwinAxis.REQUEST_PRESENCE:
        _require(
            not left_facts[0].pending_request_ids
            and isinstance(left_program.actions[0], DelegateAction)
            and right_facts[-1].pending_request_ids
            and isinstance(right_program.actions[-1], IdleAction)
            and right_program.actions[-1].reason is IdleReason.AWAITING_TOOL,
            "request-presence twin does not expose absent versus pending state",
        )
    elif axis is TwinAxis.TIMER_STATUS:
        _require(
            any(
                decision.active_timer_ids and isinstance(decision.action, NudgeAction)
                for decision in left_facts
            )
            and any(
                decision.canceled_timer_ids and isinstance(decision.action, SkipAction)
                for decision in right_facts
            ),
            "timer-status twin does not expose active versus canceled handling",
        )
    elif axis is TwinAxis.FLOOR_STATE:
        typing_nudge_index = next(
            (
                index
                for index, decision in enumerate(left_facts)
                if decision.floor_owned and isinstance(decision.action, NudgeAction)
            ),
            None,
        )
        paused_mark = next(
            (
                decision.action
                for decision in right_facts
                if not decision.floor_owned and isinstance(decision.action, MarkAction)
            ),
            None,
        )
        typing_target_text = json.loads(left_program.frames[-1].raw_bytes)["text"]
        paused_target_text = json.loads(right_program.frames[-1].raw_bytes)["text"]
        _require(
            typing_nudge_index is not None
            and typing_nudge_index + 1 < len(left_facts)
            and isinstance(left_facts[typing_nudge_index + 1].action, IdleAction)
            and left_facts[typing_nudge_index + 1].action.reason is IdleReason.TYPING_ACTIVE
            and isinstance(paused_mark, MarkAction),
            "floor-state twin does not expose typing versus paused handling",
        )
        _require(
            not any(isinstance(decision.action, MarkAction) for decision in left_facts),
            "floor-state typing member must not mark",
        )
        assert isinstance(paused_mark, MarkAction)  # narrowed by the axis contract above.
        _require(
            typing_target_text == paused_target_text
            and paused_target_text.endswith(paused_mark.target.text)
            and paused_mark.target.end_utf16 == utf16_len(paused_target_text),
            "floor-state twins must share a bare snapshot-end mark target",
        )
    elif axis is TwinAxis.TOPIC_FRESHNESS:
        _require(
            any(isinstance(decision.action, IntegrateAction) for decision in left_facts)
            and any(
                decision.stale_tool_result_event_ids and isinstance(decision.action, SkipAction)
                for decision in right_facts
            ),
            "topic-freshness twin does not expose integrate versus stale skip",
        )
    else:
        _require(
            len(left.generated.stream.segments) == 1 and len(right.generated.stream.segments) >= 2,
            "rollover twin does not isolate pre versus post checkpoint placement",
        )


def validate_twin_group(group: TwinGroup) -> TwinGroup:
    """Prove the fixed axis contract and runtime identity for a generated twin."""
    programs = group.programs
    values = TWIN_AXIS_VALUES[programs.axis]
    _require(
        tuple(member.value for member in group.members) == values, "twin values are not canonical"
    )
    _require(
        programs.common_inputs_sha256 == artifact_digest(json.loads(programs.common_inputs)),
        "common inputs were mutated",
    )
    expected_common = _common_inputs(
        family=_AXIS_FAMILY[programs.axis],
        bundle=programs.programs[0].bundle,
        template=programs.programs[0].template,
        master_seed=programs.master_seed,
        program=programs.programs[0],
    )
    _require(
        programs.common_inputs == canonical_artifact_bytes(expected_common),
        "common inputs differ from the shared recipe",
    )
    _require(
        programs.group_id == _group_id("twin", programs.axis.value, expected_common),
        "twin group id does not bind its axis and common inputs",
    )
    _require(
        programs.variant_inputs_sha256
        == tuple(_bytes_digest(value) for value in programs.variant_inputs),
        "variant inputs were mutated",
    )
    _require(
        programs.variant_inputs
        == tuple(program.canonical_input_bytes for program in programs.programs)
        and programs.variant_inputs_sha256
        == tuple(program.input_hash for program in programs.programs),
        "compiled variant inputs differ",
    )
    member_ids = tuple(sorted(_member_id(value) for value in values))
    expected_programs = tuple(
        _build_selected_family_program(
            _AXIS_FAMILY[programs.axis],
            programs.programs[0].bundle,
            programs.programs[0].template,
            programs.master_seed,
            _variant=(programs.axis.value, value),
            counterfactual=_declaration(
                kind="twin",
                group_id=programs.group_id,
                member_id=_member_id(value),
                member_ids=member_ids,
                flipped_perturbation=_AXIS_PERTURBATION[programs.axis],
            ),
        )
        for value in values
    )
    _require(
        programs.programs == expected_programs,
        "twin programs differ from the fixed one-axis compiler",
    )
    for member, expected_program in zip(group.members, expected_programs, strict=True):
        _require(
            member.generated.program == expected_program
            and member.variant_inputs_sha256 == expected_program.input_hash,
            "generated twin member does not bind its compiled program",
        )
        _validate_link(
            member.generated,
            kind="twin",
            group_id=programs.group_id,
            member_id=_member_id(member.value),
            member_ids=member_ids,
            flipped_perturbation=_AXIS_PERTURBATION[programs.axis],
        )
    streams = tuple(member.generated.stream for member in group.members)
    provenance = tuple(stream.provenance for stream in streams)
    _require(
        all(item.master_seed == programs.master_seed for item in provenance), "twin seed differs"
    )
    _require(len({item.template_id for item in provenance}) == 1, "twin template differs")
    _require(len({item.asset_ids for item in provenance}) == 1, "twin assets differ")
    _require(
        len(
            {
                (item.timing_seed_id, item.timing_profile_id, item.timing_rng_version)
                for item in provenance
            }
        )
        == 1,
        "twin timing identity differs",
    )
    shared_decisions = min(len(item.timing_plan.service_ms) for item in streams)
    _require(
        len({item.timing_plan.service_ms[:shared_decisions] for item in streams}) == 1,
        "twin named timing draws differ before their causal horizons diverge",
    )
    if programs.axis is not TwinAxis.ROLLOVER_BOUNDARY:
        _require(
            len({item.artifact_hashes for item in provenance}) == 1,
            "twin runtime artifacts differ",
        )
    recomputed = ByteDiffEvidence.between(
        streams[0].canonical_segment_bytes,
        streams[1].canonical_segment_bytes,
        streams[0].sha256,
        streams[1].sha256,
    )
    _require(recomputed == group.byte_diff, "twin byte-diff evidence was mutated")
    _require(recomputed.differing_bytes > 0, "twin streams are byte-identical")
    _validate_axis_effect(programs.axis, group.members)
    _require(
        group.sha256 == artifact_digest(json.loads(group.canonical_bytes)),
        "twin group bytes were mutated",
    )
    return group


@dataclass(frozen=True, slots=True)
class LookupTripletPrograms:
    group_id: str
    master_seed: str
    lookup_asset_id: str
    common_inputs: bytes
    common_inputs_sha256: str
    result_payload_hashes: tuple[str, str, str]
    programs: tuple[ScenarioProgram, ScenarioProgram, ScenarioProgram]


def _lookup_asset(bundle: AssetBundle) -> AssetRecord:
    asset = next(
        (item for item in bundle.assets if isinstance(item.payload, LookupAssetPayload)), None
    )
    if asset is None:
        raise CounterfactualGroupError("lookup triplet requires one LookupAssetPayload")
    return asset


def build_lookup_triplet_programs(
    registry: AssetRegistry,
    *,
    split: Split | str,
    template_id: str,
    asset_ids: tuple[str, ...],
    master_seed: str,
) -> LookupTripletPrograms:
    """Build the fixed A/B/no-result provenance control from one lookup asset."""
    family = CorpusFamily.LOOKUP_LIVE
    bundle, template = select_approved_scenario_inputs(
        registry,
        split=split,
        template_id=template_id,
        asset_ids=asset_ids,
    )
    probe = _build_selected_family_program(
        family,
        bundle,
        template,
        master_seed,
        _variant=("provenance_result", "a"),
    )
    lookup_asset = _lookup_asset(bundle)
    common = _common_inputs(
        family=family,
        bundle=bundle,
        template=template,
        master_seed=master_seed,
        program=probe,
    )
    group_id = _group_id("triplet", "provenance_result", common)
    outcomes = ("a", "b", "none")
    programs = tuple(
        _build_selected_family_program(
            family,
            bundle,
            template,
            master_seed,
            _variant=("provenance_result", outcome),
            counterfactual=_declaration(
                kind="triplet",
                group_id=group_id,
                member_id=_member_id(outcome),
                member_ids=outcomes,
                flipped_perturbation="tool_result",
            ),
        )
        for outcome in outcomes
    )
    return LookupTripletPrograms(
        group_id=group_id,
        master_seed=master_seed,
        lookup_asset_id=lookup_asset.asset_id,
        common_inputs=canonical_artifact_bytes(common),
        common_inputs_sha256=artifact_digest(common),
        result_payload_hashes=tuple(
            artifact_digest(program.tool_results[0].data) for program in programs
        ),
        programs=programs,
    )


@dataclass(frozen=True, slots=True)
class LookupTriplet:
    programs: LookupTripletPrograms
    generated: tuple[GeneratedScenario, GeneratedScenario, GeneratedScenario]
    canonical_bytes: bytes = field(init=False)
    sha256: str = field(init=False)

    def __post_init__(self) -> None:
        value = {
            "group_id": self.programs.group_id,
            "master_seed": self.programs.master_seed,
            "lookup_asset_id": self.programs.lookup_asset_id,
            "common_inputs_sha256": self.programs.common_inputs_sha256,
            "result_payload_hashes": self.programs.result_payload_hashes,
            "siblings": [
                {
                    "outcome": outcome,
                    "stream_sha256": scenario.stream.sha256,
                    "sidecar_sha256": scenario.sidecar.sha256,
                }
                for outcome, scenario in zip(("a", "b", "none"), self.generated, strict=True)
            ],
        }
        object.__setattr__(self, "canonical_bytes", canonical_artifact_bytes(value))
        object.__setattr__(self, "sha256", artifact_digest(value))


async def execute_lookup_triplet(
    programs: LookupTripletPrograms, *, directory: Path, repository_root: Path | None = None
) -> LookupTriplet:
    generated = []
    for outcome, program in zip(("a", "b", "none"), programs.programs, strict=True):
        generated.append(
            await execute_scenario(
                program,
                session_id=f"s_{programs.group_id}_{outcome}",
                directory=directory / outcome,
                repository_root=repository_root,
            )
        )
    return LookupTriplet(programs=programs, generated=tuple(generated))


def _executed_actions(generated: GeneratedScenario) -> tuple[object, ...]:
    return tuple(
        event.payload.action
        for segment in generated.stream.segments
        for line in segment.policy_bytes.splitlines()
        if isinstance((event := parse_event(line)), ActionExecutedEvent)
    )


def validate_lookup_triplet(triplet: LookupTriplet) -> LookupTriplet:
    """Prove result A/B provenance and a truly pending no-result control."""
    programs = triplet.programs
    outcomes = ("a", "b", "none")
    _require(
        programs.common_inputs_sha256 == artifact_digest(json.loads(programs.common_inputs)),
        "triplet common inputs were mutated",
    )
    first_program = programs.programs[0]
    expected_common = _common_inputs(
        family=CorpusFamily.LOOKUP_LIVE,
        bundle=first_program.bundle,
        template=first_program.template,
        master_seed=programs.master_seed,
        program=first_program,
    )
    _require(
        programs.common_inputs == canonical_artifact_bytes(expected_common)
        and programs.group_id == _group_id("triplet", "provenance_result", expected_common),
        "triplet common inputs or group id differ from the fixed recipe",
    )
    expected_programs = tuple(
        _build_selected_family_program(
            CorpusFamily.LOOKUP_LIVE,
            first_program.bundle,
            first_program.template,
            programs.master_seed,
            _variant=("provenance_result", outcome),
            counterfactual=_declaration(
                kind="triplet",
                group_id=programs.group_id,
                member_id=_member_id(outcome),
                member_ids=outcomes,
                flipped_perturbation="tool_result",
            ),
        )
        for outcome in outcomes
    )
    _require(
        programs.programs == expected_programs,
        "triplet programs differ from the fixed provenance compiler",
    )
    for outcome, generated, expected_program in zip(
        outcomes, triplet.generated, expected_programs, strict=True
    ):
        _require(
            generated.program == expected_program,
            "generated triplet member does not bind its compiled program",
        )
        _validate_link(
            generated,
            kind="triplet",
            group_id=programs.group_id,
            member_id=_member_id(outcome),
            member_ids=outcomes,
            flipped_perturbation="tool_result",
        )
    streams = tuple(item.stream for item in triplet.generated)
    provenance = tuple(stream.provenance for stream in streams)
    _require(
        all(item.master_seed == programs.master_seed for item in provenance), "triplet seed differs"
    )
    _require(len({item.template_id for item in provenance}) == 1, "triplet template differs")
    _require(len({item.asset_ids for item in provenance}) == 1, "triplet assets differ")
    _require(len({stream.sha256 for stream in streams}) == 3, "triplet streams are not distinct")
    _require(streams[0].frames == streams[1].frames == streams[2].frames, "triplet frames differ")
    common_prefixes = tuple(
        tuple(decision.prefix_bytes for decision in stream.decisions[:2]) for stream in streams
    )
    _require(
        programs.programs[0].actions[:2]
        == programs.programs[1].actions[:2]
        == programs.programs[2].actions[:2]
        and len(set(common_prefixes)) == 1,
        "triplet common decision horizon differs before result presence can act",
    )
    _require(
        streams[0].timing_plan == streams[1].timing_plan,
        "A/B timing plans differ",
    )
    _require(
        streams[2].timing_plan.seed == streams[0].timing_plan.seed
        and streams[2].timing_plan.service_ms == streams[0].timing_plan.service_ms[:2],
        "none timing does not share the A/B timing prefix",
    )
    _require(
        programs.result_payload_hashes
        == tuple(artifact_digest(program.tool_results[0].data) for program in programs.programs),
        "triplet payload hash differs",
    )
    first_data, second_data = (
        programs.programs[0].tool_results[0].data,
        programs.programs[1].tool_results[0].data,
    )
    _require(
        isinstance(first_data, dict)
        and isinstance(second_data, dict)
        and set(first_data) == set(second_data),
        "A/B result data shapes differ",
    )
    _require(
        programs.programs[0].tool_results[0].latency_ms
        == programs.programs[1].tool_results[0].latency_ms
        == 700,
        "A/B result latency differs",
    )
    for expected, generated in zip(("a", "b"), triplet.generated[:2], strict=True):
        results = [
            event
            for segment in generated.stream.segments
            for line in segment.policy_bytes.splitlines()
            if isinstance((event := parse_event(line)), ToolResultEvent)
        ]
        _require(len(results) == 1, f"{expected} result was not delivered exactly once")
        _require(
            results[0].payload.data
            == programs.programs[0 if expected == "a" else 1].tool_results[0].data,
            f"{expected} result payload differs",
        )
        actions = tuple(
            action for action in _executed_actions(generated) if isinstance(action, IntegrateAction)
        )
        _require(
            len(actions) == 1
            and actions[0].result_event_id == results[0].id
            and actions[0].text
            == programs.programs[0 if expected == "a" else 1].tool_results[0].data["nonce"],
            f"{expected} was not faithfully integrated from its result event",
        )
    none = triplet.generated[2]
    _require(
        not any(
            isinstance(parse_event(line), ToolResultEvent)
            for segment in none.stream.segments
            for line in segment.policy_bytes.splitlines()
        ),
        "none control delivered a tool result",
    )
    _require(
        not any(isinstance(action, IntegrateAction) for action in _executed_actions(none)),
        "none control integrated a result",
    )
    _require(
        any(decision.pending_request_ids for decision in none.sidecar.decisions),
        "none control has no oracle decision over its pending request",
    )
    ledger = json.loads(none.stream.final_ledger.canonical_bytes)
    _require(
        any(item["status"] == "pending" for item in ledger["tool_requests"]),
        "none control did not retain a pending request",
    )
    _require(
        triplet.sha256 == artifact_digest(json.loads(triplet.canonical_bytes)),
        "triplet bytes changed",
    )
    return triplet
