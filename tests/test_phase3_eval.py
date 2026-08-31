from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from tinker import SamplingParams

from im.assets.model import canonical_artifact_bytes
from im.generation.phase2_dev_states import _registry
from im.generation.runtime import DecisionBoundary
from im.generation.sidecar import BeatEvidence
from im.license import (
    LicenseView,
    PendingToolRequestView,
    SnapshotView,
    TimerFireView,
    TimerView,
    ToolResultView,
)
from im.schema.actions import ACTION_ADAPTER
from im.schema.common import Disposition, TimerStatus, ToolName, ToolResultStatus
from im.training import phase3_eval
from im.training.phase3_data import SealedTestAccessError, guard_read_path
from im.training.phase3_eval import (
    ACTION_TYPES,
    FROZEN_SAMPLING_MANIFEST_SHA256,
    FROZEN_SAMPLING_REQUESTS_SHA256,
    REQUIRED_SENTINEL_TAGS,
    SAMPLING,
    DevEvalState,
    FrozenHumanAssessment,
    Phase3EvalError,
    _assert_frozen_sampling_payloads,
    _causal_failure,
    _compute_dev_metrics_from_grades,
    _counterbalanced_retention_slots,
    _frozen_rollover_a,
    build_open_text_rubrics,
    capture_raw_generation,
    compute_dev_metrics,
    grade_persisted_generation,
    persist_raw_generation,
    select_canary_sentinels,
    select_fast_sentinels,
    sentinel_evidence,
    sentinel_tags,
)
from im.training.phase3_framing import TERMINAL_MARKER, TERMINAL_TOKEN_ID


def _action(action_type: str):
    span = {"event_id": "e_000001", "start_utf16": 0, "end_utf16": 1, "text": "x"}
    payloads = {
        "cancel": {"type": "cancel", "instruction": span, "target": {"kind": "all_active"}},
        "delegate": {
            "type": "delegate",
            "fact": span,
            "tool": "lookup",
            "args": {"query": "x"},
        },
        "idle": {"type": "idle", "reason": "no_trigger", "related_event_id": None},
        "integrate": {"type": "integrate", "result_event_id": "e_000001", "text": "x"},
        "mark": {"type": "mark", "instruction": span, "target": span},
        "nudge": {"type": "nudge", "fire_event_id": "e_000001"},
        "respond": {"type": "respond", "reply_to_event_id": "e_000001", "text": "x"},
        "schedule": {
            "type": "schedule",
            "instruction": span,
            "interval_ms": 1000,
            "message": "x",
        },
        "skip": {
            "type": "skip",
            "target_event_id": "e_000001",
            "reason": "stale_tool_result",
        },
    }
    return ACTION_ADAPTER.validate_python(payloads[action_type])


def _evidence() -> BeatEvidence:
    return BeatEvidence(
        beat_id="beat",
        stale_tool_result_event_ids=(),
        floor_open=None,
        floor_opening_snapshot_event_id=None,
        floor_opening_snapshot_text=None,
        stale_snapshot_event_id=None,
        stale_snapshot_text=None,
        response_warrant_kind=None,
        response_warrant_snapshot_event_id=None,
        response_warrant_snapshot_text=None,
        response_warrant_failed_result_event_id=None,
        need_lineage=(),
        delegate_provenance_by_beat=(),
        skip_evidence=None,
        cancel_resolution_evidence=None,
        oracle_floor_open=False,
    )


def _state(action_type: str, rank: int = 0) -> DevEvalState:
    expected = _action(action_type)
    return DevEvalState(
        state_id=f"dev:{action_type}:{rank}",
        priority_rank=rank,
        source_unit_id=f"source-{action_type}",
        stream_sha256="sha256:" + f"{rank + 1:064x}",
        decision_policy_seq=rank + 1,
        family="ordinary",
        shape_id="ordinary",
        rollover=action_type == "mark",
        boundary_class="active_floor_response" if action_type == "respond" else "ordinary",
        risk_flags=(),
        expected=expected,
        prompt_hash="sha256:" + "a" * 64,
        messages=({"role": "user", "content": "x"},),
        input_tokens=tuple(range(rank + 2)),
        visible_prefix_sha256="sha256:" + "b" * 64,
        boundary=DecisionBoundary(call_index=1, policy_bytes=b"{}", license_view=LicenseView()),
        evidence=_evidence(),
    )


def test_raw_first_idle_grade_and_length_failure(tmp_path: Path) -> None:
    state = _state("idle")
    raw_bytes = canonical_artifact_bytes(state.expected.model_dump(mode="json"))
    raw = capture_raw_generation(
        evaluation_run_id="run-valid",
        model_identity="model",
        checkpoint_identity="checkpoint",
        sampling_manifest_sha256="sha256:" + "c" * 64,
        state_id=state.state_id,
        output_token_ids=(1, 2),
        decoded_bytes=raw_bytes,
        finish_reason="stop",
    )
    persisted = persist_raw_generation(tmp_path, tmp_path / "raw", raw)
    grade = grade_persisted_generation(tmp_path, state, persisted)
    assert grade["raw"]["output_bytes_sha256"].startswith("sha256:")
    assert grade["structural"]["parse_union_valid"] is True
    assert grade["executed"]["match"] is True
    states = tuple(_state(ACTION_TYPES[index % len(ACTION_TYPES)], index) for index in range(300))
    with pytest.raises(Phase3EvalError, match="mix evaluation identities"):
        compute_dev_metrics(
            tmp_path,
            states,
            (persisted,) * 300,
            expected_evaluation_identity=(
                "different-run",
                "model",
                "checkpoint",
                "sha256:" + "c" * 64,
            ),
        )

    length = capture_raw_generation(
        evaluation_run_id="run-length",
        model_identity="model",
        checkpoint_identity="checkpoint",
        sampling_manifest_sha256="sha256:" + "c" * 64,
        state_id=state.state_id,
        output_token_ids=(1,),
        decoded_bytes=raw_bytes,
        finish_reason="length",
    )
    persisted_length = persist_raw_generation(tmp_path, tmp_path / "raw", length)
    invalid = grade_persisted_generation(tmp_path, state, persisted_length)
    assert invalid["structural"]["parse_error"] == "length_termination"
    assert invalid["executed"]["match"] is False

    empty = capture_raw_generation(
        evaluation_run_id="run-empty",
        model_identity="model",
        checkpoint_identity="checkpoint",
        sampling_manifest_sha256="sha256:" + "c" * 64,
        state_id=state.state_id,
        output_token_ids=(),
        decoded_bytes=b"",
        finish_reason="stop",
    )
    persisted_empty = persist_raw_generation(tmp_path, tmp_path / "raw", empty)
    assert (
        grade_persisted_generation(tmp_path, state, persisted_empty)["structural"][
            "parse_union_valid"
        ]
        is False
    )
    with pytest.raises(Phase3EvalError):
        capture_raw_generation(
            evaluation_run_id="run-invalid",
            model_identity="model",
            checkpoint_identity="checkpoint",
            sampling_manifest_sha256="sha256:" + "c" * 64,
            state_id=state.state_id,
            output_token_ids=(-1,),
            decoded_bytes=b"",
            finish_reason="stop",
        )
    with pytest.raises(Phase3EvalError):
        capture_raw_generation(
            evaluation_run_id="run-invalid",
            model_identity="model",
            checkpoint_identity="checkpoint",
            sampling_manifest_sha256="sha256:" + "c" * 64,
            state_id=state.state_id,
            output_token_ids=(),
            decoded_bytes=b"",
            finish_reason="stop",
            latency_ms=1.5,  # type: ignore[arg-type]
        )


def test_open_text_gold_fixture_stays_pending_without_human_assessment(tmp_path: Path) -> None:
    state = _state("integrate")
    raw = capture_raw_generation(
        evaluation_run_id="run-open-text",
        model_identity="model",
        checkpoint_identity="checkpoint",
        sampling_manifest_sha256="sha256:" + "c" * 64,
        state_id=state.state_id,
        output_token_ids=(1,),
        decoded_bytes=canonical_artifact_bytes(state.expected.model_dump(mode="json")),
        finish_reason="stop",
    )
    persisted = persist_raw_generation(tmp_path, tmp_path / "raw", raw)
    grade = grade_persisted_generation(tmp_path, state, persisted)
    assert grade["executed"]["semantic_status"] == "pending_semantic_assessment"
    assert grade["executed"]["match"] is False


def test_open_text_pass_does_not_erase_structural_failure(tmp_path: Path) -> None:
    state = _state("respond")
    candidate = state.expected.model_dump(mode="json")
    candidate["reply_to_event_id"] = "e_000002"
    raw = capture_raw_generation(
        evaluation_run_id="run-open-text-structural-failure",
        model_identity="model",
        checkpoint_identity="checkpoint",
        sampling_manifest_sha256="sha256:" + "c" * 64,
        state_id=state.state_id,
        output_token_ids=(1,),
        decoded_bytes=canonical_artifact_bytes(candidate),
        finish_reason="stop",
    )
    persisted = persist_raw_generation(tmp_path, tmp_path / "raw", raw)
    rubric = build_open_text_rubrics((state,))[0]
    assessment = FrozenHumanAssessment(
        state_id=state.state_id,
        rubric_sha256=str(rubric.as_json_object()["rubric_sha256"]),
        output_bytes_sha256=str(raw.as_json_object()["output_bytes_sha256"]),
        passed=True,
        reason_codes=("all_required_points_present", "no_forbidden_claims"),
    )
    grade = grade_persisted_generation(
        tmp_path, state, persisted, semantic_assessment=assessment
    )
    assert grade["structural"]["closed_field_match"] is False
    assert grade["executed"]["semantic_status"] == "passed"
    assert grade["executed"]["match"] is False


def test_persisted_tinker_output_is_projected_before_strict_grading(tmp_path: Path) -> None:
    state = _state("idle")
    action = canonical_artifact_bytes(state.expected.model_dump(mode="json"))
    raw = capture_raw_generation(
        evaluation_run_id="run-framed",
        model_identity="model",
        checkpoint_identity="checkpoint",
        sampling_manifest_sha256="sha256:" + "c" * 64,
        state_id=state.state_id,
        output_token_ids=(1, TERMINAL_TOKEN_ID),
        decoded_bytes=action + TERMINAL_MARKER.encode(),
        finish_reason="stop",
    )
    persisted = persist_raw_generation(tmp_path, tmp_path / "raw", raw)

    class Decoder:
        def decode(self, token_ids, *, skip_special_tokens: bool):
            assert token_ids == [1]
            assert skip_special_tokens is False
            return action.decode()

    grade = grade_persisted_generation(tmp_path, state, persisted, tokenizer=Decoder())
    assert grade["framing"]["terminal_projection_status"] == "projected"
    assert grade["framing"]["consumed_token_id"] == TERMINAL_TOKEN_ID
    assert grade["structural"]["parse_union_valid"] is True
    assert grade["executed"]["match"] is True


def test_sampling_contract_instantiates_pinned_tinker_params() -> None:
    params = SamplingParams(**SAMPLING)
    assert params.seed == 20260801
    assert params.top_k == -1


def test_sampling_payload_hashes_are_frozen() -> None:
    assert FROZEN_SAMPLING_REQUESTS_SHA256 == (
        "sha256:674c8a91c732bdf0b6661a91e7b2ee365d22ba7a3e08d549276d655c22a746f6"
    )
    assert FROZEN_SAMPLING_MANIFEST_SHA256 == (
        "sha256:1f05d80c49baa9a79311ec2567a46995babf9e90a26f674a18b7b9f8c09940d5"
    )
    with pytest.raises(Phase3EvalError, match="sampling requests drifted"):
        _assert_frozen_sampling_payloads(b"drift", b"drift")


def test_retention_slots_are_counterbalanced_within_each_group() -> None:
    rows = [
        {"capability_group": f"group-{group}", "prompt_id": f"prompt-{group}-{index}"}
        for group in range(6)
        for index in range(10)
    ]
    slots = _counterbalanced_retention_slots(rows, "a" * 64)
    for group in range(6):
        group_slots = [slots[f"prompt-{group}-{index}"] for index in range(10)]
        assert group_slots.count("A") == group_slots.count("B") == 5


def test_fast_set_is_minimal_by_nine_action_lower_bound() -> None:
    instruction = _action("schedule").instruction
    snapshot = SnapshotView("e_000001", "x")
    rich_view = LicenseView(
        latest_snapshot=snapshot,
        events=(
            snapshot,
            TimerFireView("e_000002", "t_001", Disposition.HANDLED),
            ToolResultView("e_000003", "r_003", False, ToolResultStatus.SUCCEEDED),
            ToolResultView("e_000010", "r_010", True, ToolResultStatus.SUCCEEDED),
            ToolResultView("e_000011", "r_011", True, ToolResultStatus.SUCCEEDED),
        ),
        timers=(
            TimerView(
                "t_001",
                TimerStatus.ACTIVE,
                instruction=instruction,
                interval_ms=1000,
                message="x",
            ),
            TimerView("t_002", TimerStatus.CANCELED),
        ),
        pending_tool_requests=(
            PendingToolRequestView.from_args("r_001", "e_000001", ToolName.LOOKUP, {"query": "x"}),
        ),
    )
    boundary = DecisionBoundary(call_index=1, policy_bytes=b"{}", license_view=rich_view)
    states = [
        replace(_state(action_type, rank), boundary=boundary)
        for rank, action_type in enumerate(ACTION_TYPES)
    ]
    integrate = next(state for state in states if state.action_type == "integrate")
    wrong_causal = replace(
        integrate,
        state_id="dev:wrong-causal:1",
        expected=ACTION_ADAPTER.validate_python(
            {"type": "integrate", "result_event_id": "e_000010", "text": "x"}
        ),
        evidence=replace(
            _evidence(),
            future_actions=(
                ACTION_ADAPTER.validate_python(
                    {
                        "type": "integrate",
                        "result_event_id": "e_000011",
                        "text": "x",
                    }
                ),
            ),
        ),
        priority_rank=20,
    )
    states.append(wrong_causal)
    active_floor = replace(
        next(state for state in states if state.action_type == "idle"),
        state_id="dev:active-floor:1",
        boundary=DecisionBoundary(
            call_index=1,
            policy_bytes=b"{}",
            license_view=replace(rich_view, floor_owned=True),
        ),
        boundary_class="active_floor_response",
        expected=ACTION_ADAPTER.validate_python(
            {
                "type": "idle",
                "reason": "awaiting_opening",
                "related_event_id": "e_000001",
            }
        ),
        input_tokens=tuple(range(100)),
        priority_rank=21,
    )
    states.append(active_floor)
    active_floor_respond = replace(
        next(state for state in states if state.action_type == "respond"),
        state_id="dev:active-floor-respond:1",
        boundary=active_floor.boundary,
        boundary_class="active_floor_response",
    )
    assert (
        _causal_failure(wrong_causal.expected, wrong_causal.evidence.future_actions[0])
        == "integrate_result_event_id_mismatch"
    )
    fast = select_fast_sentinels(states)
    assert active_floor in fast
    assert "hard:active_floor" in sentinel_tags(active_floor)
    assert "hard:active_floor" not in sentinel_tags(active_floor_respond)
    assert sentinel_evidence(active_floor)["active_floor_owned"] is True
    assert {state.action_type for state in fast} == set(ACTION_TYPES)
    assert set().union(*(sentinel_tags(state) for state in fast)) >= REQUIRED_SENTINEL_TAGS
    canary = select_canary_sentinels(fast)
    assert len(canary) == 3
    assert all(len(state.input_tokens) <= 18_182 for state in canary)


def test_open_text_rubric_is_frozen_before_sampling() -> None:
    assert getattr(phase3_eval, "OPEN_TEXT_RUBRIC_VERSION", None) == ("phase3-open-text-rubric-v1")


def test_open_text_rows_have_subtype_specific_human_rubrics() -> None:
    states = (
        _state("integrate"),
        replace(_state("respond", 1), source_unit_id="response-failed-1-yielded"),
        replace(_state("respond", 2), source_unit_id="response-lookup-live-clarification-yielded"),
        replace(_state("respond", 3), source_unit_id="response-timer-ambiguous-cancel-yielded"),
        replace(_state("respond", 4), source_unit_id="response-timer-unsupported-yielded"),
        replace(_state("respond", 5), source_unit_id="response-neutral-01-yielded"),
    )
    rubrics = build_open_text_rubrics(states)
    assert [rubric.subtype for rubric in rubrics] == [
        "integrate_success",
        "failed_result_notice",
        "clarification",
        "clarification",
        "unsupported_feature_limitation",
        "ordinary_grounded_answer",
    ]
    assert all(rubric.required_points and rubric.support_event_ids for rubric in rubrics)
    assert all("paraphrases allowed" in rubric.paraphrase_policy for rubric in rubrics)


def test_d10_metrics_use_frozen_denominators() -> None:
    states = tuple(_state(ACTION_TYPES[index % len(ACTION_TYPES)], index) for index in range(300))
    grades = [
        {
            "executed": {
                "duplicate_action": False,
                "intrusive_action": False,
                "match": True,
                "provenance_violation": False,
                "semantic_status": "not_applicable",
            },
            "predicted_action": {"type": state.action_type},
            "raw": {"hidden_thinking": False},
            "state_id": state.state_id,
            "structural": {
                "closed_field_match": True,
                "license_block_codes": [],
                "parse_union_valid": True,
                "structural_pass": True,
            },
        }
        for state in states
    ]
    metrics = _compute_dev_metrics_from_grades(states, grades)
    assert metrics["parse_union_validity"] == 1.0
    assert metrics["positive_action_micro_accuracy"] == 1.0
    assert metrics["sequence_success"] == 1.0
    assert metrics["d13_score"] == 1.0
    assert metrics["intrusive_action_rate"] == 0.0
    assert metrics["duplicate_action_rate"] == 0.0
    assert metrics["provenance_violation_rate"] == 0.0
    assert metrics["positive_action_denominator"] == 266
    assert metrics["baseline_failure_count"] == 0


def test_phase3_eval_has_no_test_path_entrypoint() -> None:
    root = Path(__file__).resolve().parents[1]
    with pytest.raises(SealedTestAccessError):
        guard_read_path(root, root / "review/phase2/wp2-10-test-closeout")
    cli = (root / "scripts/evaluate_phase3.py").read_text()
    assert "--test" not in cli


@pytest.mark.asyncio
async def test_frozen_rollover_a_compatibility_rebuild(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    parent = await _frozen_rollover_a(root, _registry(), tmp_path / "rollover-a")
    assert parent.stream.sha256 == (
        "sha256:c0fab470b1f5e8e1564e1d0bd6c0e9d21ae5eeb63e109eeb2e6b2614b8c02640"
    )
    assert parent.sidecar.sha256 == (
        "sha256:87749ec56078c59fd2e2ab9da0d6add00c96b293d6ea6681d5efc83c1b7fdd0d"
    )
