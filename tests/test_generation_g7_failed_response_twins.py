from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest

from im.assets import Split, load_verified_registry_seals
from im.canonical_json import parse_tim_json
from im.generation.corpus_segments import CorpusSegmentCandidate
from im.generation.g7_failed_response_twins import (
    FAILED_QUERY_EVENT_ID,
    FAILED_RESPONSE_SHAPE_ID,
    FAILED_RESULT_EVENT_ID,
    build_g7_failed_response_twin_programs,
)
from im.generation.response_contracts import (
    AnswerContract,
    AnswerPoint,
    ResponseContractError,
    ResponseKind,
)
from im.generation.scenarios import execute_scenario
from im.generation.yield_readiness import G7ShapeAllocation, G7SourceUnit
from im.schema.actions import DelegateAction, IdleAction, IdleReason, IntegrateAction, RespondAction
from im.schema.common import ToolResultStatus
from im.schema.events import SnapshotEvent, StateCheckpointEvent, ToolResultEvent
from im.serialize import parse_event


def _sealed_registry():
    root = Path(__file__).parents[1]
    registry, seals = load_verified_registry_seals(
        (root / "review/phase1/approved/registry.jsonl").read_bytes(),
        tuple(
            (root / "review/phase1/approved" / name).read_bytes()
            for name in ("test-seal.json", "demo-seal.json")
        ),
    )
    assert {seal.split for seal in seals} == {Split.TEST, Split.DEMO}
    return registry


def _contract(subject: str = "Fable Station platform") -> AnswerContract:
    return AnswerContract(
        response_kind=ResponseKind.FAILED_TOOL_NOTICE,
        subject_id="lookup-failure",
        support_event_ids=(FAILED_QUERY_EVENT_ID, FAILED_RESULT_EVENT_ID),
        required_answer_points=(AnswerPoint((f"{subject} lookup failed",)),),
        forbidden_claims=(),
    )


def test_failed_result_builder_validates_the_injected_candidate_response() -> None:
    with pytest.raises(ResponseContractError):
        build_g7_failed_response_twin_programs(
            _sealed_registry(),
            invitation="Please respond about the failed lookup.",
            answer_contract=_contract(),
            candidate_response="The Fable Station platform lookup succeeded.",
        )


@pytest.mark.asyncio
async def test_failed_result_twins_are_real_later_seven_call_runtime_candidates(
    tmp_path: Path,
) -> None:
    twins = build_g7_failed_response_twin_programs(
        _sealed_registry(),
        invitation="Please respond about the failed lookup.",
        answer_contract=_contract(),
        candidate_response="The Fable Station platform lookup failed.",
        master_seed="g7-failed-response-twin-test",
    )
    yielded, active = twins.programs
    root = Path(__file__).parents[1]
    parents = tuple(
        [
            await execute_scenario(
                program,
                session_id=f"s_failed_twin_{index}",
                directory=tmp_path / f"member-{index}",
                repository_root=root,
            )
            for index, program in enumerate(twins.programs)
        ]
    )
    candidates = tuple(
        CorpusSegmentCandidate(parent, twins.checkpoint_segment_index, shape_id)
        for parent, shape_id in zip(parents, twins.candidate_shape_ids, strict=True)
    )

    assert all(
        candidate.selected_call_indices == twins.selected_call_indices
        for candidate in candidates
    )
    assert all(candidate.decision_count == 7 for candidate in candidates)
    assert all(
        tuple(type(action) for action in candidate.selected_actions[:-1])
        == (
            IdleAction,
            DelegateAction,
            DelegateAction,
            IdleAction,
            IntegrateAction,
            IntegrateAction,
        )
        for candidate in candidates
    )
    assert isinstance(candidates[0].selected_actions[-1], RespondAction)
    assert isinstance(candidates[1].selected_actions[-1], IdleAction)
    assert all(4 not in candidate.selected_call_indices for candidate in candidates)
    assert Counter(
        type(action) for candidate in candidates for action in candidate.selected_actions
    ) == {
        DelegateAction: 4,
        IdleAction: 5,
        IntegrateAction: 4,
        RespondAction: 1,
    }
    source = G7SourceUnit(
        FAILED_RESPONSE_SHAPE_ID,
        parents[0].program.family,
        "checkpoint_segment",
        parents,
        "g7-failed-response-twin-test",
        candidates,
    )
    allocation = G7ShapeAllocation.from_checkpoint_segments((candidates,))
    assert source.action_counts == allocation.action_counts
    assert allocation.multiplicity == 1

    for parent, candidate in zip(parents, candidates, strict=True):
        checkpoint = parse_event(candidate.segment.policy_bytes.splitlines()[0])
        events = tuple(
            parse_event(line)
            for segment in parent.stream.segments
            for line in segment.policy_bytes.splitlines()
        )
        failed = next(event for event in events if event.id == FAILED_RESULT_EVENT_ID)
        assert isinstance(checkpoint, StateCheckpointEvent)
        assert isinstance(failed, ToolResultEvent)
        assert failed.payload.status is ToolResultStatus.FAILED
        assert failed.seq < checkpoint.seq

    third = tuple(parent.sidecar.decisions[9] for parent in parents)
    assert all(
        decision.floor_open is False and len(decision.pending_request_ids) == 2
        for decision in third
    )
    assert all(
        decision.action.reason is IdleReason.AWAITING_TOOL
        for decision in third
        if isinstance(decision.action, IdleAction)
    )
    integrations = tuple(parent.sidecar.decisions[10:12] for parent in parents)
    assert all(
        decision.floor_open is True
        and decision.floor_opening_snapshot_event_id == "e_000018"
        for pair in integrations
        for decision in pair
    )

    final_decisions = tuple(parent.sidecar.decisions[-1] for parent in parents)
    assert all(
        decision.response_warrant_snapshot_event_id == "e_000022"
        and decision.response_warrant_failed_result_event_id == FAILED_RESULT_EVENT_ID
        for decision in final_decisions
    )
    assert final_decisions[0].floor_open is True
    assert final_decisions[0].floor_opening_snapshot_event_id == "e_000022"
    assert final_decisions[1].floor_open is False

    assert all(program.require_g7_evidence for program in twins.programs)
    assert all(
        tuple(item.beat_id for item in program.delegate_provenance_by_beat or ())
        == ("b3", "b7", "b8")
        for program in twins.programs
    )
    assert all(
        action.reason is IdleReason.INSTRUCTION_NOT_DIRECT
        for program in twins.programs
        for action in program.actions[:3]
        if isinstance(action, IdleAction)
    )
    assert all(
        next(
            need
            for need in program.need_lineage_by_beat[-1].needs
            if need.need_id == "n_failed_lookup"
        ).status.value
        == "live"
        for program in twins.programs
    )

    for parent, program in zip(parents, twins.programs, strict=True):
        snapshots = {
            event.id: event
            for segment in parent.stream.segments
            for line in segment.policy_bytes.splitlines()
            if isinstance((event := parse_event(line)), SnapshotEvent)
        }
        delegates = tuple(
            action for action in program.actions if isinstance(action, DelegateAction)
        )
        assert all(action.fact.text == action.args.query for action in delegates)
        assert all(
            f"Please look up {action.fact.text}." in snapshots[action.fact.event_id].payload.text
            for action in delegates
        )
        assert (
            "remains available for the final invitation"
            in snapshots[FAILED_QUERY_EVENT_ID].payload.text
        )

    assert yielded.frames[:-1] == active.frames[:-1]
    yielded_final = parse_tim_json(yielded.frames[-1].raw_bytes)
    active_final = parse_tim_json(active.frames[-1].raw_bytes)
    assert {key: value for key, value in yielded_final.items() if key != "activity"} == {
        key: value for key, value in active_final.items() if key != "activity"
    }
    assert (yielded_final["activity"], active_final["activity"]) == ("paused", "active")
    assert yielded.actions[:-1] == active.actions[:-1]
    assert (
        yielded.actions[-1].reply_to_event_id
        == active.actions[-1].related_event_id
        == FAILED_RESULT_EVENT_ID
    )


@pytest.mark.asyncio
async def test_failed_result_twins_commit_both_integrations_for_production_fuzz_seed(
    tmp_path: Path,
) -> None:
    subject = "Alder Loop registry"
    twins = build_g7_failed_response_twin_programs(
        _sealed_registry(),
        invitation="Could you report the result of the Alder Loop registry lookup?",
        answer_contract=_contract(subject),
        candidate_response="The Alder Loop registry lookup failed.",
        master_seed=(
            "g7-readiness-v1:throughput-2:"
            "g7-checkpoint-lookup-live-failed-response:002:000"
        ),
        failed_lookup_index=2,
    )
    root = Path(__file__).parents[1]

    generated = tuple(
        [
            await execute_scenario(
                program,
                session_id=f"s_failed_fuzz_regression_{index}",
                directory=tmp_path / f"member-{index}",
                repository_root=root,
            )
            for index, program in enumerate(twins.programs)
        ]
    )

    assert all(
        tuple(type(decision.action) for decision in parent.sidecar.decisions[10:12])
        == (IntegrateAction, IntegrateAction)
        for parent in generated
    )


@pytest.mark.parametrize(
    ("failed_lookup_index", "subject"),
    tuple(enumerate(
        (
            "Fable Station platform",
            "Morrow Glen cistern fill percentage",
            "Alder Loop registry",
            "Thistle Row gallery wing",
        )
    )),
)
def test_failed_result_twins_select_each_sealed_lookup_subject_deterministically(
    failed_lookup_index: int,
    subject: str,
) -> None:
    twins = build_g7_failed_response_twin_programs(
        _sealed_registry(),
        invitation="Please respond about the failed lookup.",
        answer_contract=_contract(subject),
        candidate_response=f"{subject} lookup failed.",
        failed_lookup_index=failed_lookup_index,
    )

    assert all(program.actions[3].fact.text == subject for program in twins.programs)
