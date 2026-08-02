"""Build the exact 300-state WP2-8 DEV gold-review packet."""

from __future__ import annotations

import asyncio
import collections
from dataclasses import dataclass, replace
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

from im.assets.model import CorpusFamily, Split, canonical_artifact_bytes
from im.assets.registry import AssetRegistry
from im.assets.validate import load_verified_registry_seals
from im.canonical_json import canonicalize_tim_json, parse_tim_json
from im.generation.g7_catalog import (
    G7FamilyInputs,
    build_g7_mark_fresh_programs,
    build_g7_timer_wave0_fresh_programs,
)
from im.generation.g7_checkpoint_catalog import build_g7_lookup_checkpoint_program
from im.generation.g7_contention_checkpoint import build_g7_contention_checkpoint_program
from im.generation.g7_failed_response_twins import build_g7_failed_response_twin_programs
from im.generation.g7_response_assets import GeneratedResponseAsset, SimpleResponseProfile
from im.generation.g7_response_twins import build_g7_response_floor_twin_program
from im.generation.g7_rollover_checkpoint import build_g7_rollover_checkpoint_catalog
from im.generation.ingestion import ScheduledSamplerFrame
from im.generation.packaging import PackageManifest
from im.generation.phase2_dev_allocation import (
    DEFAULT_APPROVED_ROOT,
    build_dev_allocation,
    build_dev_c5_programs,
)
from im.generation.phase2_dev_responses import dev_response_records, dev_response_records_v2
from im.generation.phase2_review import (
    BoundaryClass,
    DecisionEvidence,
    FloorClass,
    TrustCellKey,
    route_wave,
)
from im.generation.phase2_review_projection import (
    CandidateLicense,
    DecisionProjectionInput,
    project_phase2_review_evidence,
)
from im.generation.phase2_timer_wave0_boundaries import (
    TimerBoundaryInputs,
    build_timer_wave0_boundary_programs,
)
from im.generation.publication import publish_directory_transaction
from im.generation.scenarios import (
    CounterfactualDeclaration,
    DeclaredPerturbation,
    GeneratedScenario,
    ScenarioProgram,
    execute_scenario,
    validate_generated_scenario,
)
from im.probes.harness.models import HarnessProtocol
from im.schema.actions import IdleAction, IdleReason, RespondAction, SkipAction, SkipReason

_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT = _ROOT / "review" / "phase2" / "dev-gate-c-review"
_PROMPT_TEMPLATE = "prompt-template-v4.txt"
_SEED = "wp2-8-dev-gold-v1"
_OWNER_LABEL_CORRECTIONS = {
    (
        "c5-neutral_typing_revision_pause-a_f9fb7e61b8bd7a9477003568-"
        "a_1e853564f00b768d7e097326-None-r08",
        0,
    ): IdleAction(type="idle", reason=IdleReason.NO_TRIGGER, related_event_id=None),
    (
        "c5-neutral_typing_revision_pause-a_f9fb7e61b8bd7a9477003568-"
        "a_9709064b5e4c0e2c5fd96af9-None-r08",
        1,
    ): IdleAction(type="idle", reason=IdleReason.NO_TRIGGER, related_event_id=None),
    (
        "c5-timer_creation_normal_fire-a_8757bfbc6cba684b27e651f4-"
        "a_eace0b11d0909880600e2ee0-None-r00",
        3,
    ): IdleAction(
        type="idle",
        reason=IdleReason.ALREADY_HANDLED,
        related_event_id="e_000005",
    ),
}


class DevStateError(ValueError):
    """The frozen 300-state DEV packet cannot be built."""


@dataclass(frozen=True, slots=True)
class DevProgram:
    logical_stream_id: str
    shape_id: str
    program: ScenarioProgram
    eligible_indices: tuple[int, ...]
    required_indices: tuple[int, ...] = ()
    rollover: bool = False


@dataclass(frozen=True, slots=True)
class DevState:
    logical_stream_id: str
    shape_id: str
    program_index: int
    family: CorpusFamily
    action: object
    required: bool
    rollover: bool

    @property
    def key(self) -> tuple[str, int]:
        return self.logical_stream_id, self.program_index


@dataclass(frozen=True, slots=True)
class DevStatePlan:
    programs: tuple[DevProgram, ...]
    selected: tuple[DevState, ...]


@dataclass(frozen=True, slots=True)
class DevStatePacket:
    files: dict[str, bytes]
    stream_count: int
    state_count: int = 300


def _registry(approved_root: Path = DEFAULT_APPROVED_ROOT) -> AssetRegistry:
    registry, _ = load_verified_registry_seals(
        (approved_root / "registry.jsonl").read_bytes(),
        tuple(
            (approved_root / f"{split}-seal.json").read_bytes()
            for split in ("train", "test", "demo", "dev")
        ),
        required_splits=(Split.TRAIN, Split.TEST, Split.DEMO, Split.DEV),
    )
    return registry


def _with_prompt(program: ScenarioProgram) -> ScenarioProgram:
    return replace(program, prompt_template=_PROMPT_TEMPLATE)


def _human_as_generated(record: object) -> GeneratedResponseAsset:
    return GeneratedResponseAsset.create(
        record.draft,
        teacher_visible_prefix=record.teacher_visible_prefix,
        candidate_response=record.response_text,
    )


def _response_programs(registry: AssetRegistry) -> tuple[DevProgram, ...]:
    original = dev_response_records()
    additions = dev_response_records_v2()
    ordinary = (
        ("neutral-01", CorpusFamily.NEUTRAL_TYPING, ("a_1e853564f00b768d7e097326",), original[0]),
        ("neutral-04", CorpusFamily.NEUTRAL_TYPING, ("a_40fdf7ad18f9751d29f86a52",), original[3]),
        ("neutral-05", CorpusFamily.NEUTRAL_TYPING, ("a_9709064b5e4c0e2c5fd96af9",), original[4]),
        ("neutral-06", CorpusFamily.NEUTRAL_TYPING, ("a_1e853564f00b768d7e097326",), original[5]),
        ("neutral-07", CorpusFamily.NEUTRAL_TYPING, ("a_40fdf7ad18f9751d29f86a52",), original[6]),
        ("mark-positive", CorpusFamily.MARK_POSITIVE, additions[0][1], additions[0][3]),
        ("mark-negative", CorpusFamily.MARK_NEGATIVE, additions[1][1], additions[1][3]),
        ("lookup-stale", CorpusFamily.LOOKUP_STALE, additions[2][1], additions[2][3]),
        ("lookup-live-clarification", CorpusFamily.LOOKUP_LIVE, additions[3][1], additions[3][3]),
    )
    templates = {
        CorpusFamily.NEUTRAL_TYPING: "a_f9fb7e61b8bd7a9477003568",
        CorpusFamily.MARK_POSITIVE: "a_484a98cb9f3aa72092073a01",
        CorpusFamily.MARK_NEGATIVE: "a_88bfb610f62f2a089e399fa7",
        CorpusFamily.LOOKUP_LIVE: "a_a5ace13e4faac673508a08e2",
        CorpusFamily.LOOKUP_STALE: "a_55b04143a35783594eb56789",
    }
    programs: list[DevProgram] = []
    for name, family, asset_ids, record in ordinary:
        asset = _human_as_generated(record)
        pair = build_g7_response_floor_twin_program(
            registry,
            split=Split.DEV,
            family=family,
            inputs=G7FamilyInputs(templates[family], tuple(asset_ids)),
            profile=SimpleResponseProfile((asset,) * 10),
            master_seed=f"{_SEED}:response:{name}",
            item_index=0,
        )
        for member, program in zip(("yielded", "active"), pair.programs, strict=True):
            programs.append(
                DevProgram(
                    f"response-{name}-{member}",
                    f"response-floor-{name}",
                    _with_prompt(program),
                    (0,),
                    (0,),
                )
            )

    approved_lookups = tuple(
        sorted(
            (
                item
                for item in registry.pool(Split.DEV).assets
                if registry.is_approved(item) and item.payload.kind.value == "lookup"
            ),
            key=lambda item: item.asset_id,
        )
    )
    for ordinal, addition_index in enumerate((5, 6), 1):
        _, supporting_ids, _, record = additions[addition_index]
        failure_id = supporting_ids[0]
        failed_index = next(
            index for index, item in enumerate(approved_lookups) if item.asset_id == failure_id
        )
        successes = tuple(
            item.asset_id for item in approved_lookups if item.asset_id != failure_id
        )[:2]
        pair = build_g7_failed_response_twin_programs(
            registry,
            invitation=record.draft.invitation,
            answer_contract=record.draft.answer_contract,
            candidate_response=record.response_text,
            master_seed=f"{_SEED}:failed-response:{ordinal}",
            failed_lookup_index=failed_index,
            split=Split.DEV,
            asset_ids=(failure_id, *successes),
        )
        for member, program in zip(("yielded", "active"), pair.programs, strict=True):
            final = len(program.actions) - 1
            eligible = (
                tuple(
                    index
                    for index, action in enumerate(program.actions)
                    if action.type in {"delegate", "integrate"}
                )
                + (final,)
                if member == "yielded"
                else (final,)
            )
            programs.append(
                DevProgram(
                    f"response-failed-{ordinal}-{member}",
                    "failed-tool-response-floor",
                    _with_prompt(program),
                    eligible,
                    (final,),
                    True,
                )
            )

    timer_inputs = TimerBoundaryInputs(
        split=Split.DEV,
        ambiguous_template="a_fce6b3157ebedc9e449b8811",
        ambiguous_asset="a_bc624fb9cff53e987d7da5c7",
        negated_template="a_f5ad757de32a28f139519a46",
        negated_assets=("a_f4e2996fb52b7b0eb0224b72", "a_678147b687192e08e582ad3a"),
        unsupported_template="a_3609287c695dd95bc0ced3ae",
        unsupported_asset="a_424f9094ff831faf5f20ed78",
        one_shot_asset="a_cc65a76eb1bf198aeb8680df",
        supported_assets=("a_f2abae3f71742fb32ac2dbf7", "a_eace0b11d0909880600e2ee0"),
        clarification=original[8].response_text,
        unresolved_context="Both reminders are visible without a selected reference point.",
        clock_limitation=original[10].response_text,
        one_shot_instruction="Remind me three times to seal the birch crate, then stop.",
        one_shot_limitation=additions[4][3].response_text,
    )
    by_id = {
        item.logical_stream_id: item for item in build_timer_wave0_boundary_programs(
            registry, timer_inputs
        )
    }
    for logical_id in ("ambiguous-cancel-active", "ambiguous-cancel-yielded"):
        program = by_id[logical_id].program
        final = len(program.actions) - 1
        programs.append(
            DevProgram(
                f"response-timer-{logical_id}",
                "timer-boundary-response-floor",
                _with_prompt(program),
                (final,),
                (final,),
            )
        )
    for logical_id in ("unsupported-absolute-time", "unsupported-one-shot"):
        yielded, active = _timer_limitation_pair(logical_id, by_id[logical_id].program)
        for member, program in (("yielded", yielded), ("active", active)):
            programs.append(
                DevProgram(
                    f"response-timer-{logical_id}-{member}",
                    "timer-boundary-response-floor",
                    _with_prompt(program),
                    (0,),
                    (0,),
                )
            )
    return tuple(programs)


def _timer_limitation_pair(
    logical_id: str, yielded: ScenarioProgram
) -> tuple[ScenarioProgram, ScenarioProgram]:
    """Add the active-floor partner omitted by the historical yielded-only boundary."""
    if (
        len(yielded.frames) != 1
        or len(yielded.actions) != 1
        or not isinstance(yielded.actions[0], RespondAction)
    ):
        raise DevStateError("timer limitation source is not an isolated yielded response")
    payload = parse_tim_json(yielded.frames[0].raw_bytes)
    if not isinstance(payload, dict) or payload.get("activity") != "paused":
        raise DevStateError("timer limitation yielded frame is malformed")
    payload["activity"] = "active"
    active_frame = ScheduledSamplerFrame(
        yielded.frames[0].at_ms, canonicalize_tim_json(payload)
    )
    group_id = f"wp2-8-{logical_id}"

    def link(member_id: str) -> CounterfactualDeclaration:
        return CounterfactualDeclaration(
            kind="twin",
            group_id=group_id,
            member_id=member_id,
            member_ids=("active", "yielded"),
            flipped_perturbation="floor_opening",
        )

    perturbations = (DeclaredPerturbation("floor_opening"),)
    yielded = replace(
        yielded,
        perturbations=perturbations,
        counterfactual=link("yielded"),
    )
    active = replace(
        yielded,
        frames=(active_frame,),
        actions=(
            IdleAction(
                type="idle",
                reason=IdleReason.AWAITING_OPENING,
                related_event_id="e_000002",
            ),
        ),
        counterfactual=link("active"),
        openings_by_beat=(),
    )
    return yielded, active


def _special_programs(registry: AssetRegistry) -> tuple[DevProgram, ...]:
    programs: list[DevProgram] = []
    positive = G7FamilyInputs(
        "a_484a98cb9f3aa72092073a01", ("a_c8e980d7f52144f826f11b9c",)
    )
    negative = G7FamilyInputs(
        "a_88bfb610f62f2a089e399fa7",
        (
            "a_c8e980d7f52144f826f11b9c",
            "a_2d32e2214634e63889837d0a",
            "a_4b9ff1fa143be8c680ed4de9",
            "a_809ae00555172f10aba68375",
            "a_cf844b577e94c3b5fbdaea34",
        ),
    )
    for ordinal in range(9):
        built = dict(
            build_g7_mark_fresh_programs(
                registry,
                split=Split.DEV,
                positive_inputs=positive,
                negative_inputs=negative,
                master_seed=f"{_SEED}:mark-negative:{ordinal}",
            )
        )
        program = built["mark-negative"]
        indices = tuple(
            index
            for index, action in enumerate(program.actions)
            if action.type == "mark" or isinstance(action, IdleAction)
        )
        programs.append(
            DevProgram(
                f"g7-mark-negative-{ordinal:02d}",
                "g7-fresh-mark-negative",
                _with_prompt(program),
                indices,
            )
        )
        if ordinal < 2:
            member = f"mark-positive-{'ab'[ordinal]}"
            positive_program = built[member]
            programs.append(
                DevProgram(
                    f"g7-mark-positive-{ordinal:02d}",
                    f"g7-fresh-{member}",
                    _with_prompt(positive_program),
                    tuple(
                        index
                        for index, action in enumerate(positive_program.actions)
                        if action.type == "mark"
                    ),
                )
            )

    lookup_ids = (
        "a_894c16c53e7c0f0b87918031",
        "a_bf592f83b7159cb6fff91ec0",
        "a_e4ec125895d174c4d906fefd",
        "a_79eeaa1a638190bb4adc6371",
    )
    for ordinal in range(5):
        program = build_g7_lookup_checkpoint_program(
            registry,
            split=Split.DEV,
            shape_id="g7-checkpoint-lookup-duplicate-a",
            template_id="a_6c844e1ea5fe440103f76aad",
            primary_lookup_asset_id=lookup_ids[ordinal % 3],
            lookup_asset_ids=lookup_ids,
            text_asset_ids=(
                "a_1e853564f00b768d7e097326",
                "a_40fdf7ad18f9751d29f86a52",
            ),
            master_seed=f"{_SEED}:lookup-duplicate:{ordinal}",
        )
        indices = tuple(
            index
            for index, action in enumerate(program.actions)
            if action.type in {"integrate", "skip"}
            or (
                isinstance(action, IdleAction)
                and action.reason
                in {IdleReason.AWAITING_TOOL, IdleReason.INSTRUCTION_NOT_DIRECT}
            )
        )
        programs.append(
            DevProgram(
                f"g7-lookup-duplicate-{ordinal:02d}",
                "g7-checkpoint-lookup-duplicate-a",
                _with_prompt(program),
                indices,
                rollover=True,
            )
        )

    contention_timers = (
        "a_0923f7b5dc1fba54d543ce43",
        "a_0e151a3d216733fadb664aef",
        "a_1916b86768312565ab12b106",
    )
    for ordinal in range(8):
        program = build_g7_contention_checkpoint_program(
            registry,
            master_seed=f"{_SEED}:contention:{ordinal}",
            split=Split.DEV,
            template_id="a_d9e4797beeb4b756ddc5a1ec",
            timer_asset_id=contention_timers[ordinal % len(contention_timers)],
            timing_seed="g7-contention-checkpoint-v1:g7-contention-checkpoint-test:153024",
            messages=(
                "seal the mint envelope for checkpoint lane one",
                "check the amber blinds for checkpoint lane two",
                "seal the mint envelope for checkpoint lane three",
                "check the amber blinds for checkpoint lane four",
                "seal the mint envelope for checkpoint lane five",
                "check the amber blinds for checkpoint lane six",
            ),
            separated_requests=True,
        )
        indices = tuple(
            index
            for index, action in enumerate(program.actions)
            if action.type == "cancel"
            or (
                isinstance(action, IdleAction)
                and action.reason is IdleReason.ALREADY_HANDLED
            )
        )
        programs.append(
            DevProgram(
                f"g7-contention-{ordinal:02d}",
                "g7-checkpoint-timer-contention",
                _with_prompt(program),
                indices,
                rollover=True,
            )
        )

    timer_normal = dict(
        build_g7_timer_wave0_fresh_programs(
            registry,
            split=Split.DEV,
            normal_inputs=G7FamilyInputs(
                "a_8757bfbc6cba684b27e651f4",
                ("a_5edbec1a7f9e4cf2cea4151c",),
            ),
            contention_inputs=G7FamilyInputs(
                "a_d9e4797beeb4b756ddc5a1ec",
                ("a_0923f7b5dc1fba54d543ce43", "a_c8e980d7f52144f826f11b9c"),
            ),
            master_seed=f"{_SEED}:timer-handled",
            post_confirmation_gap_ms=3_000,
        )
    )["timer-normal-wide"]
    programs.append(
        DevProgram(
            "g7-timer-normal-handled",
            "g7-timer-normal-post-confirmation",
            _with_prompt(timer_normal),
            tuple(
                index
                for index, action in enumerate(timer_normal.actions)
                if isinstance(action, IdleAction)
                and action.reason is IdleReason.ALREADY_HANDLED
            ),
        )
    )
    return tuple(programs)


async def _rollover_programs(
    registry: AssetRegistry, directory: Path
) -> tuple[tuple[DevProgram, GeneratedScenario], ...]:
    entries = await build_g7_rollover_checkpoint_catalog(
        registry,
        directory=directory,
        repository_root=_ROOT,
        split=Split.DEV,
        template_id="a_4a403aaa78fb587f5ca4d4d0",
        rollover_lookup_asset_id="a_2c90afbdb043178f1b9c6f00",
        stale_lookup_asset_id="a_8bb0112712dae80287d2d014",
        mark_asset_id="a_c8e980d7f52144f826f11b9c",
        first_timer_asset_id="a_f2abae3f71742fb32ac2dbf7",
        recurring_timer_asset_id="a_eace0b11d0909880600e2ee0",
        shape_ids=("g7-checkpoint-rollover-a", "g7-checkpoint-rollover-c"),
        prompt_template=_PROMPT_TEMPLATE,
        master_seed=f"{_SEED}:rollover",
        explicit_lookup_request=True,
    )
    built = []
    for entry in entries:
        wanted = "integrate" if entry.shape_id.endswith("-a") else "cancel"
        index = next(
            index
            for index, action in enumerate(entry.parent.program.actions)
            if action.type == wanted
        )
        built.append(
            (
                DevProgram(
                    f"g7-rollover-{entry.shape_id.rsplit('-', 1)[-1]}",
                    entry.shape_id,
                    entry.parent.program,
                    (index,),
                    rollover=True,
                ),
                entry.parent,
            )
        )
    return tuple(built)


def _states(programs: tuple[DevProgram, ...]) -> tuple[DevState, ...]:
    result = []
    for item in programs:
        required = set(item.required_indices)
        for index in item.eligible_indices:
            result.append(
                DevState(
                    item.logical_stream_id,
                    item.shape_id,
                    index,
                    item.program.family,
                    item.program.actions[index],
                    index in required,
                    item.rollover,
                )
            )
    return tuple(result)


def _rank(state: DevState) -> bytes:
    return sha256(f"{_SEED}|{state.logical_stream_id}|{state.program_index}".encode()).digest()


def _take_spread(candidates: list[DevState], count: int) -> list[DevState]:
    by_program: dict[str, list[DevState]] = collections.defaultdict(list)
    for candidate in candidates:
        by_program[candidate.logical_stream_id].append(candidate)
    queues = [
        collections.deque(sorted(values, key=_rank))
        for _, values in sorted(
            by_program.items(),
            key=lambda item: sha256(f"{_SEED}|{item[0]}".encode()).digest(),
        )
    ]
    selected: list[DevState] = []
    while queues and len(selected) < count:
        next_round = []
        for queue in queues:
            selected.append(queue.popleft())
            if queue:
                next_round.append(queue)
            if len(selected) == count:
                break
        queues = next_round
    if len(selected) != count:
        raise DevStateError(f"candidate supply {len(selected)} cannot fill target {count}")
    return selected


def _idle_transport(
    family_needs: dict[str, int],
    reason_needs: dict[str, int],
    supply: collections.Counter[tuple[str, str]],
) -> dict[tuple[str, str], int]:
    source, sink = "source", "sink"
    graph: dict[str, dict[str, int]] = collections.defaultdict(dict)

    def edge(left: str, right: str, capacity: int) -> None:
        graph[left][right] = capacity
        graph[right].setdefault(left, 0)

    for family, count in sorted(family_needs.items()):
        edge(source, f"f:{family}", count)
    for (family, reason), count in sorted(supply.items()):
        if family_needs.get(family, 0) and reason_needs.get(reason, 0):
            edge(f"f:{family}", f"r:{reason}", count)
    for reason, count in sorted(reason_needs.items()):
        edge(f"r:{reason}", sink, count)

    total = 0
    while True:
        parent = {source: ""}
        queue = collections.deque((source,))
        while queue and sink not in parent:
            left = queue.popleft()
            for right, capacity in sorted(graph[left].items()):
                if capacity > 0 and right not in parent:
                    parent[right] = left
                    queue.append(right)
        if sink not in parent:
            break
        flow = min(
            graph[parent[node]][node]
            for node in _path_nodes(parent, sink)
        )
        node = sink
        while node != source:
            left = parent[node]
            graph[left][node] -= flow
            graph[node][left] += flow
            node = left
        total += flow
    required = sum(family_needs.values())
    if total != required or required != sum(reason_needs.values()):
        raise DevStateError("idle family/reason allocation is infeasible")
    return {
        (family, reason): graph[f"r:{reason}"].get(f"f:{family}", 0)
        for family in family_needs
        for reason in reason_needs
        if graph[f"r:{reason}"].get(f"f:{family}", 0)
    }


def _path_nodes(parent: dict[str, str], sink: str) -> tuple[str, ...]:
    nodes = []
    node = sink
    while parent[node]:
        nodes.append(node)
        node = parent[node]
    return tuple(nodes)


def _select(programs: tuple[DevProgram, ...]) -> tuple[DevState, ...]:
    allocation = build_dev_allocation()
    all_states = _states(programs)
    required = [state for state in all_states if state.required]
    selected = list(required)
    used = {state.key for state in required}

    family_action = {
        (family, action): count
        for family, actions in allocation["family_action"].items()
        for action, count in actions.items()
    }
    idle_reasons = dict(allocation["idle_reason"])
    for state in required:
        family_action[(state.family.value, state.action.type)] -= 1
        if isinstance(state.action, IdleAction):
            idle_reasons[state.action.reason.value] -= 1
    if any(count < 0 for count in (*family_action.values(), *idle_reasons.values())):
        raise DevStateError("required response states exceed the frozen allocation")

    available = [state for state in all_states if state.key not in used and not state.required]
    for (family, action), count in sorted(family_action.items()):
        if action == "idle" or count == 0:
            continue
        candidates = [
            state
            for state in available
            if state.family.value == family and state.action.type == action
        ]
        if len(candidates) < count:
            raise DevStateError(
                f"{family}/{action} has {len(candidates)} candidates for {count} states"
            )
        taken = _take_spread(candidates, count)
        selected.extend(taken)
        used.update(state.key for state in taken)

    idle_family = {
        family: count
        for (family, action), count in family_action.items()
        if action == "idle"
    }
    idle_candidates: dict[tuple[str, str], list[DevState]] = collections.defaultdict(list)
    for state in available:
        if state.key in used or not isinstance(state.action, IdleAction):
            continue
        idle_candidates[(state.family.value, state.action.reason.value)].append(state)
    transport = _idle_transport(
        idle_family,
        idle_reasons,
        collections.Counter({key: len(value) for key, value in idle_candidates.items()}),
    )
    for key, count in sorted(transport.items()):
        taken = _take_spread(idle_candidates[key], count)
        selected.extend(taken)
        used.update(state.key for state in taken)

    ordered = tuple(
        sorted(selected, key=lambda state: (state.logical_stream_id, state.program_index))
    )
    _validate_selected(ordered, allocation)
    return ordered


def _validate_selected(
    selected: tuple[DevState, ...], allocation: dict[str, object]
) -> None:
    family_action = collections.Counter(
        (state.family.value, state.action.type) for state in selected
    )
    expected_family_action = {
        (family, action): count
        for family, actions in allocation["family_action"].items()
        for action, count in actions.items()
    }
    reasons = collections.Counter(
        state.action.reason.value
        for state in selected
        if isinstance(state.action, IdleAction)
    )
    if (
        len(selected) != 300
        or len({state.key for state in selected}) != 300
        or dict(family_action) != expected_family_action
        or dict(reasons) != dict(allocation["idle_reason"])
    ):
        raise DevStateError("selected DEV states do not match the frozen allocation exactly")


def _apply_owner_label_corrections(plan: DevStatePlan) -> DevStatePlan:
    program_actions: dict[str, list[object]] = {}
    corrected_states = []
    found = set()
    for state in plan.selected:
        action = _OWNER_LABEL_CORRECTIONS.get(state.key, state.action)
        if state.key in _OWNER_LABEL_CORRECTIONS:
            found.add(state.key)
            program_actions.setdefault(
                state.logical_stream_id,
                list(next(
                    item.program.actions
                    for item in plan.programs
                    if item.logical_stream_id == state.logical_stream_id
                )),
            )[state.program_index] = action
        corrected_states.append(replace(state, action=action))
    if found != set(_OWNER_LABEL_CORRECTIONS):
        raise DevStateError("owner label corrections do not bind the frozen selected states")
    programs = tuple(
        replace(
            item,
            program=replace(
                item.program,
                actions=tuple(program_actions[item.logical_stream_id]),
            ),
        )
        if item.logical_stream_id in program_actions
        else item
        for item in plan.programs
    )
    reasons = collections.Counter(
        state.action.reason.value
        for state in corrected_states
        if isinstance(state.action, IdleAction)
    )
    expected = {
        **build_dev_allocation()["idle_reason"],
        "already_handled": 9,
        "no_trigger": 80,
        "typing_active": 2,
    }
    if dict(reasons) != expected:
        raise DevStateError("owner-corrected DEV idle reasons drifted")
    return DevStatePlan(programs, tuple(corrected_states))


async def _program_plan(
    registry: AssetRegistry, directory: Path
) -> tuple[DevStatePlan, dict[str, GeneratedScenario]]:
    c5 = tuple(
        DevProgram(
            logical_id,
            "shared-c5-recipe",
            _with_prompt(program),
            tuple(range(len(program.actions))),
        )
        for logical_id, program in build_dev_c5_programs(
            registry,
            replicas_by_family={
                CorpusFamily.LOOKUP_LIVE: 2,
                CorpusFamily.LOOKUP_DUPLICATE: 1,
                CorpusFamily.MARK_POSITIVE: 1,
                CorpusFamily.MARK_NEGATIVE: 1,
                CorpusFamily.NEUTRAL_TYPING: 10,
                CorpusFamily.LOOKUP_STALE: 2,
                CorpusFamily.TIMER_NORMAL: 7,
            },
        )
    )
    rollover = await _rollover_programs(registry, directory / "rollover")
    programs = (
        *c5,
        *_special_programs(registry),
        *_response_programs(registry),
        *(item[0] for item in rollover),
    )
    if len({item.logical_stream_id for item in programs}) != len(programs):
        raise DevStateError("DEV program ids repeat")
    selected = _select(tuple(programs))
    plan = _apply_owner_label_corrections(DevStatePlan(tuple(programs), selected))
    return plan, {
        item.logical_stream_id: generated for item, generated in rollover
    }


async def _execute(
    plan: DevStatePlan,
    preexecuted: dict[str, GeneratedScenario],
    directory: Path,
) -> dict[str, GeneratedScenario]:
    selected_ids = {state.logical_stream_id for state in plan.selected}
    by_id = {item.logical_stream_id: item for item in plan.programs}
    result = dict(preexecuted)
    semaphore = asyncio.Semaphore(8)

    async def one(logical_id: str) -> tuple[str, GeneratedScenario]:
        async with semaphore:
            generated = await execute_scenario(
                by_id[logical_id].program,
                session_id=f"wp2-8-{logical_id}",
                directory=directory / logical_id,
                repository_root=_ROOT,
            )
            validate_generated_scenario(generated)
            return logical_id, generated

    pending = sorted(selected_ids - set(result))
    for logical_id, generated in await asyncio.gather(*(one(item) for item in pending)):
        result[logical_id] = generated
    if set(result) != selected_ids:
        raise DevStateError("executed stream inventory does not match selected states")
    return result


def _floor(decision: object) -> FloorClass:
    if decision.floor_owned:
        return FloorClass.OWNED
    if decision.floor_open:
        return FloorClass.OPEN
    return FloorClass.CLOSED


def _review_evidence(
    plan: DevStatePlan, generated: dict[str, GeneratedScenario]
) -> bytes:
    decisions = []
    for state in plan.selected:
        parent = generated[state.logical_stream_id]
        sidecar = parent.sidecar.decisions[state.program_index]
        risks = {"dev_gold_100_percent"}
        boundary = BoundaryClass.ORDINARY
        if isinstance(state.action, RespondAction) or (
            isinstance(state.action, IdleAction)
            and state.action.reason is IdleReason.AWAITING_OPENING
        ):
            boundary = BoundaryClass.ACTIVE_FLOOR_RESPONSE
            risks.add("active_floor_response_boundary")
        elif isinstance(state.action, SkipAction):
            risks.add("skip_reason_selection")
            boundary = (
                BoundaryClass.LOOKUP_REFRESH_SUPERSEDED
                if state.action.reason is SkipReason.SUPERSEDED_QUERY
                else BoundaryClass.LOOKUP_ABANDONED_STALE
            )
        if state.rollover:
            risks.add("rollover_or_checkpoint_projection")
        decisions.append(
            DecisionEvidence(
                stream_sha256=parent.stream.sha256,
                decision_policy_seq=sidecar.observed_policy_seq,
                wave_id="wp2-8-dev-gold",
                cell=TrustCellKey(
                    HarnessProtocol.GENERATION,
                    state.family,
                    _floor(sidecar),
                ),
                template_id=parent.program.template.asset_id,
                source_unit_id=state.logical_stream_id,
                oracle_action=state.action,
                teacher_action=None,
                causal_state_class=state.shape_id,
                boundary_class=boundary,
                risk_flags=tuple(sorted(risks)),
                rollover=state.rollover,
            )
        )
    routes = route_wave(tuple(decisions), {}, sampling_seed=f"{_SEED}:review")
    if not all(route.review_required and route.mandatory for route in routes):
        raise DevStateError("every DEV gold state must route to mandatory owner review")
    return project_phase2_review_evidence(
        tuple(
            DecisionProjectionInput(
                decision=decision,
                route=route,
                oracle_license=CandidateLicense("licensed", ()),
                teacher_license=None,
                oracle_provenance={
                    "sidecar_sha256": generated[state.logical_stream_id].sidecar.sha256,
                    "stream_sha256": generated[state.logical_stream_id].stream.sha256,
                },
                teacher_provenance=None,
                priority_rank=index,
            )
            for index, (state, decision, route) in enumerate(
                zip(plan.selected, decisions, routes, strict=True)
            )
        ),
        packet_decision_identities=tuple(
            (decision.stream_sha256, decision.decision_policy_seq) for decision in decisions
        ),
        teacher_evidence_identity="sha256:" + sha256(b"wp2-8:no-teacher").hexdigest(),
        blind_seed=f"{_SEED}:blind",
    )


def _runtime_files(generated: dict[str, GeneratedScenario]) -> dict[str, bytes]:
    files = {}
    for item in generated.values():
        stream = item.stream.sha256.removeprefix("sha256:")
        for segment in item.stream.segments:
            files[f"teacher/{stream}/{segment.sha256.removeprefix('sha256:')}.jsonl"] = (
                segment.policy_bytes
            )
        files[f"reviewer/{stream}/sidecar.json"] = item.sidecar.canonical_bytes
        files[f"reviewer/{stream}/runtime-ledger.json"] = item.stream.final_ledger.canonical_bytes
    return files


def _source_index(
    plan: DevStatePlan, generated: dict[str, GeneratedScenario]
) -> dict[str, object]:
    selected = collections.Counter(state.logical_stream_id for state in plan.selected)
    return {
        "batch": 1,
        "format_version": 1,
        "source_identity_rule": (
            "Each source is a complete deterministic DEV runtime parent; "
            "phase2-review-evidence.json binds the selected gold states."
        ),
        "sources": [
            {
                "checkpoint": None,
                "family": item.program.family.value,
                "master_seed": item.program.master_seed,
                "parent_stream_sha256s": [generated[logical_id].stream.sha256],
                "raw_source_sha256s": [generated[logical_id].stream.capture_sha256],
                "role": "wp2_8_dev_gold_runtime_parent",
                "shape_id": item.shape_id,
                "sidecar_sha256s": [generated[logical_id].sidecar.sha256],
                "source_decision_counts": [len(generated[logical_id].sidecar.decisions)],
                "source_kind": "runtime_parent",
                "source_unit_id": logical_id,
                "selected_gold_state_count": selected[logical_id],
            }
            for logical_id, item in sorted(
                (
                    logical_id,
                    next(
                        program
                        for program in plan.programs
                        if program.logical_stream_id == logical_id
                    ),
                )
                for logical_id in generated
            )
        ],
    }


def _selection_report(plan: DevStatePlan) -> dict[str, object]:
    return {
        "format_version": 1,
        "kind": "wp2-8-dev-gold-state-selection",
        "selection_seed": _SEED,
        "state_count": len(plan.selected),
        "stream_count": len({state.logical_stream_id for state in plan.selected}),
        "teacher_agreement_used_as_selection_feature": False,
        "selection_unit": "individual runtime decision with its complete parent retained",
        "states": [
            {
                "logical_stream_id": state.logical_stream_id,
                "shape_id": state.shape_id,
                "program_index": state.program_index,
                "family": state.family.value,
                "action": state.action.type,
                "idle_reason": (
                    state.action.reason.value if isinstance(state.action, IdleAction) else None
                ),
                "required_response_twin": state.required,
                "rollover_or_checkpoint": state.rollover,
            }
            for state in plan.selected
        ],
    }


async def build_dev_state_packet(
    *, approved_root: Path = DEFAULT_APPROVED_ROOT
) -> DevStatePacket:
    registry = _registry(approved_root)
    with TemporaryDirectory(prefix="wp2-8-dev-gold-") as temporary:
        directory = Path(temporary)
        plan, preexecuted = await _program_plan(registry, directory)
        generated = await _execute(plan, preexecuted, directory / "runtime")
        stream_ids: dict[str, list[str]] = collections.defaultdict(list)
        for logical_id, item in generated.items():
            stream_ids[item.stream.sha256].append(logical_id)
        duplicates = [ids for ids in stream_ids.values() if len(ids) > 1]
        if duplicates:
            raise DevStateError(f"selected runtime parents repeat: {duplicates}")
        selected_generated = tuple(generated[key] for key in sorted(generated))
        files = {
            "README.md": _readme(len(generated)).encode(),
            "manifest.json": PackageManifest.build(selected_generated).canonical_bytes,
            "phase2-review-evidence.json": _review_evidence(plan, generated),
            "review-packet.json": canonical_artifact_bytes(
                {
                    "api_call_performed": False,
                    "decision_count": 300,
                    "format_version": 1,
                    "kind": "wp2-8-dev-gold-owner-review",
                    "owner_action_required": "Review all 300 states in plain language.",
                    "routed_review_decisions": 300,
                    "stream_review_count": len(generated),
                    "wave_id": "wp2-8-dev-gold",
                }
            ),
            "selected-state-plan.json": canonical_artifact_bytes(_selection_report(plan)),
            "source-index.json": canonical_artifact_bytes(_source_index(plan, generated)),
            **_runtime_files(generated),
        }
    files["SHA256SUMS"] = _checksums(files)
    return DevStatePacket(files, len(generated))


async def materialize_dev_state_packet(
    output: Path = DEFAULT_OUTPUT, *, approved_root: Path = DEFAULT_APPROVED_ROOT
) -> DevStatePacket:
    packet = await build_dev_state_packet(approved_root=approved_root)
    publish_directory_transaction(output, packet.files)
    return packet


def _checksums(files: dict[str, bytes]) -> bytes:
    return "".join(
        f"{sha256(data).hexdigest()}  {name}\n" for name, data in sorted(files.items())
    ).encode()


def _readme(stream_count: int) -> str:
    return f"""# WP2-8 Gate C — DEV gold review

This packet contains exactly 300 DEV states across {stream_count} complete runtime parents.
Every state is routed to mandatory owner review. No teacher or provider call was made.

Open the whole folder in the local review UI. Review every state, export the decisions, and
return the exported JSONL. The full interaction prefix is retained for context, but only the
300 checksum-bound states in `phase2-review-evidence.json` are part of this gold review.
"""
