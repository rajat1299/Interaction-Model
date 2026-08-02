from __future__ import annotations

import json
import tempfile
from dataclasses import replace
from pathlib import Path

import pytest

from im.generation.phase2_lookup_prose_addendum import (
    FROZEN_PAIRS_PATH,
    FrozenPair,
    ProseAddendumError,
    _check_frozen_invariants,
    build_prose_addendum_programs,
    evaluate_prose_need_gate,
    load_frozen_pairs,
    opaque_case_id,
    prose_need_battery,
)
from im.generation.phase2_lookup_wave0 import load_lookup_wave0_inputs

DENYLIST = ("look up", "lookup", "search", "can you")


def _pair(**overrides: object) -> FrozenPair:
    base = FrozenPair(
        pair_id="prose-need-99",
        asset_id="a_test",
        subject="Test Harbor tide color",
        positive_text="The note stalls because Test Harbor tide color never got written down.",
        negative_text="My heading just says Test Harbor tide color.",
        need_form="never_recorded",
    )
    return replace(base, **overrides)  # type: ignore[arg-type]


def test_frozen_pairs_on_disk_satisfy_every_static_clause() -> None:
    pairs = load_frozen_pairs()
    assert len(pairs) == 6
    assert len({pair.subject for pair in pairs}) == 6
    assert len({pair.need_form for pair in pairs}) == 6, (
        "six need-forms, not one template six times"
    )


def test_frozen_pairs_are_marked_frozen_before_generation() -> None:
    document = json.loads(FROZEN_PAIRS_PATH.read_bytes())
    assert document["frozen_before_generation"] is True
    assert document["supersedes"]["artifact"] == "frozen-pairs-v1-superseded.json"


def test_command_framing_in_a_positive_is_rejected() -> None:
    bad = _pair(positive_text="Please look up Test Harbor tide color before I finish.")
    with pytest.raises(ProseAddendumError, match="command framing"):
        _check_frozen_invariants([bad], DENYLIST)


def test_ambiguous_subject_occurrence_is_rejected() -> None:
    bad = _pair(
        positive_text=(
            "Test Harbor tide color is missing and Test Harbor tide color blocks the note."
        )
    )
    with pytest.raises(ProseAddendumError, match="unambiguous"):
        _check_frozen_invariants([bad], DENYLIST)


def test_leading_subject_is_rejected_as_a_non_interior_span() -> None:
    bad = _pair(positive_text="Test Harbor tide color is the one thing still missing.")
    with pytest.raises(ProseAddendumError, match="interior span"):
        _check_frozen_invariants([bad], DENYLIST)


def test_identical_arms_are_rejected() -> None:
    text = "The note stalls because Test Harbor tide color never got written down."
    with pytest.raises(ProseAddendumError, match="identical"):
        _check_frozen_invariants([_pair(positive_text=text, negative_text=text)], DENYLIST)


def test_case_ids_never_encode_the_arm() -> None:
    """A readable id would hand the teacher the answer and silently invalidate the canary."""
    for stream in ("prose-need-01-positive", "prose-need-01-negative"):
        for ordinal in range(3):
            case_id = opaque_case_id(stream, ordinal)
            assert "positive" not in case_id and "negative" not in case_id
            assert "prose-need" not in case_id
    assert opaque_case_id("prose-need-01-positive", 0) != opaque_case_id(
        "prose-need-01-negative", 0
    )
    assert opaque_case_id("a", 0) == opaque_case_id("a", 0), "case ids must be deterministic"


def test_programs_are_built_for_both_arms_of_every_pair() -> None:
    built = build_prose_addendum_programs(load_lookup_wave0_inputs(), load_frozen_pairs())
    assert len(built) == 12
    arms = [arm for _id, arm, _pair, _program in built]
    assert arms.count("positive") == arms.count("negative") == 6
    for _id, _arm, _pair, program in built:
        assert program.prompt_template == "prompt-template-v3.txt"
        assert program.bundle.split.value == "train"


def test_battery_rejects_a_negative_that_carries_a_delegate() -> None:
    from im.generation.phase2_lookup_prose_addendum import ExecutedProseStream
    from im.schema.actions import DelegateAction, IdleAction, IdleReason, Span

    delegate = DelegateAction(
        type="delegate",
        fact=Span(event_id="e_000002", start_utf16=4, end_utf16=8, text="tide"),
        tool="lookup",
        args={"query": "tide"},
    )
    idle = IdleAction(type="idle", reason=IdleReason.NO_TRIGGER, related_event_id=None)

    def stream(arm: str, actions: tuple[object, ...]) -> ExecutedProseStream:
        return ExecutedProseStream(
            logical_stream_id=f"s-{arm}",
            pair_id="p",
            arm=arm,
            subject="tide",
            source_text="the tide today",
            stream_sha256="sha256:x",
            sidecar_sha256="sha256:y",
            template_id="t",
            asset_ids=("a",),
            prompt_hash="sha256:p",
            actions=actions,
            policy_paths=(Path("."),),
            decision_policy_seqs=(1,),
        )

    contaminated = [stream("negative", (delegate, idle))] + [
        stream("positive", (delegate, idle, idle)) for _ in range(6)
    ]
    with pytest.raises(ProseAddendumError, match="negative_carries_no_delegate"):
        prose_need_battery(contaminated, frozenset())


def test_built_packet_is_oracle_blind_and_unsubmitted() -> None:
    packet = FROZEN_PAIRS_PATH.parent / "packet"
    if not packet.exists():  # pragma: no cover - packet is built by its script
        pytest.skip("packet not built in this checkout")
    plan = json.loads((packet / "teacher-plan.json").read_bytes())
    assert plan["api_call_performed"] is False
    assert plan["authorization_state"] == "not_submitted"
    for path in sorted((packet / "rounds").glob("*.md")):
        cases = path.read_text().split("<cases-jsonl>")[-1]
        for term in ("positive", "negative", "prose-need"):
            assert term not in cases, f"{path.name} leaks the arm to the teacher"


def test_gate_scores_the_wave_decision_not_the_context_delegate(tmp_path: Path) -> None:
    """Regression: ordinal 0 in a wave slice is the context delegate, present in BOTH arms.

    Scoring it treats every negative as a false delegate and every positive as a miss, turning a
    clean result into a spurious HALT_DIAGNOSE.
    """
    from im.generation.phase2_lookup_prose_addendum import evaluate_prose_need_gate

    packet = tmp_path / "packet"
    (packet / "rounds").mkdir(parents=True)
    index, streams, observed = {}, [], {}
    for pair in range(6):
        for arm in ("positive", "negative"):
            stream_id = f"s-{pair}-{arm}"
            subject = f"Subject {pair}"
            streams.append({"logical_stream_id": stream_id, "subject": subject, "arm": arm})
            for ordinal in (0, 1):
                case_id = f"c-{pair}-{arm}-{ordinal}"
                index[case_id] = {
                    "arm": arm,
                    "logical_stream_id": stream_id,
                    "ordinal": ordinal,
                }
                if ordinal == 0:  # context delegate on A, identical in both arms
                    observed[case_id] = {
                        "type": "delegate",
                        "fact": {"text": "Context A"},
                        "args": {"query": "Context A"},
                    }
                elif arm == "positive":
                    observed[case_id] = {"type": "delegate", "fact": {"text": subject}}
                else:
                    observed[case_id] = {
                        "type": "idle",
                        "reason": "awaiting_tool",
                        "related_event_id": "e_000002",
                    }
    (packet / "teacher-plan.json").write_text(
        json.dumps({"kind": "phase2-lookup-prose-need-wave-teacher-plan", "case_index": index})
    )
    (packet / "raw-streams.json").write_text(json.dumps({"streams": streams}))
    outcome = evaluate_prose_need_gate(packet, observed)
    assert outcome["disposition"] == "CLEAN_PASS"
    assert outcome["false_delegates"] == 0
    assert outcome["negative_restraint"] == 6
    assert outcome["positive_exact_delegates"] == 6


def test_wave_negative_requires_the_precise_reason_not_just_absence_of_delegate() -> None:
    """A wave negative that idles for the wrong reason is a divergence, not a pass."""
    with tempfile.TemporaryDirectory() as raw:
        packet = Path(raw) / "packet"
        packet.mkdir()
        index = {
            f"c-{i}": {"arm": "negative", "logical_stream_id": f"s-{i}", "ordinal": 1}
            for i in range(6)
        }
        streams = [{"logical_stream_id": f"s-{i}", "subject": f"S{i}"} for i in range(6)]
        observed = {
            f"c-{i}": {"type": "idle", "reason": "no_trigger", "related_event_id": None}
            for i in range(6)
        }
        (packet / "teacher-plan.json").write_text(
            json.dumps({"kind": "phase2-lookup-prose-need-wave-teacher-plan", "case_index": index})
        )
        (packet / "raw-streams.json").write_text(json.dumps({"streams": streams}))
        outcome = evaluate_prose_need_gate(packet, observed)
        assert outcome["negative_restraint"] == 0, "wrong idle reason must not count as restraint"
