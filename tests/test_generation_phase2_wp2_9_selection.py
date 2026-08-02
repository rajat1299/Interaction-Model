"""Fixture proofs for the exact lexicographic whole-stream optimizer."""

from __future__ import annotations

from hashlib import sha256

import pytest

from im.assets.model import canonical_artifact_bytes
from im.generation.phase2_wp2_9_selection import (
    OBJECTIVE_TERMS,
    SelectionStream,
    Wp29SelectionError,
    brute_force_lexicographic,
    candidate_rank_index,
    solve_lexicographic,
)


def _stream(
    name: str,
    *,
    unit: str,
    template: str = "t",
    decisions: int = 1,
    rank_sum: int = 0,
) -> SelectionStream:
    return SelectionStream(
        stream_sha256=name,
        family="f",
        source_unit_id=unit,
        template_id=template,
        timing_regime="r",
        difficulty_tags=("d",),
        stream_length_bucket="short",
        decision_count=decisions,
        action_counts={"idle": decisions},
        idle_reason_counts={"no_trigger": decisions},
        action_floor_counts={("idle", "closed"): decisions},
        rank_sum=rank_sum,
    )


def _solve(streams, target, **kwargs):
    return solve_lexicographic(
        streams,
        target_decisions=target,
        family_action_quotas={"f": {"idle": target}},
        idle_reason_quotas={"no_trigger": target},
        **kwargs,
    )


def _brute(streams, target):
    return brute_force_lexicographic(
        streams,
        target_decisions=target,
        family_action_quotas={"f": {"idle": target}},
        idle_reason_quotas={"no_trigger": target},
    )


def test_term_one_beats_every_later_term() -> None:
    """A concentrated pair is cheaper on ranks but loses on source-unit concentration."""
    streams = [
        _stream("a", unit="u1", decisions=2, rank_sum=0),
        _stream("b", unit="u1", decisions=2, rank_sum=0),
        _stream("c", unit="u2", decisions=2, rank_sum=500),
        _stream("d", unit="u3", decisions=2, rank_sum=500),
    ]
    result = _solve(streams, 4)

    # Taking both cheap-rank streams is forbidden: they share u1 and would push the maximum to 4.
    assert result.objective_vector["maximum_decisions_from_one_source_unit"] == 2
    assert result.objective_vector["candidate_order_rank_sum"] == 500
    assert len(set(result.selected) & {"a", "b"}) == 1


def test_a_tie_on_term_one_lets_term_two_decide() -> None:
    """Every option has max 2; only the sum of squared unit counts separates them."""
    streams = [
        _stream("a", unit="u1", decisions=2),
        _stream("b", unit="u2", decisions=1),
        _stream("c", unit="u3", decisions=1),
        _stream("d", unit="u4", decisions=2),
    ]
    result = _solve(streams, 4)

    # Every feasible set ties term 1 at a maximum of 2, so term 2 decides: {a, d} concentrates
    # 2 + 2 (8) while spreading over three units gives 4 + 1 + 1 (6).
    assert result.objective_vector["maximum_decisions_from_one_source_unit"] == 2
    assert result.objective_vector["sum_squared_source_unit_counts"] == 6
    assert set(result.selected) in ({"a", "b", "c"}, {"b", "c", "d"})


def test_highs_matches_brute_force_enumeration_on_every_term() -> None:
    """The exhaustive reference is the authority; HiGHS must reproduce it exactly."""
    streams = [
        _stream("a", unit="u1", template="t1", decisions=2, rank_sum=7),
        _stream("b", unit="u2", template="t2", decisions=1, rank_sum=3),
        _stream("c", unit="u3", template="t2", decisions=1, rank_sum=11),
        _stream("d", unit="u4", template="t1", decisions=2, rank_sum=5),
        _stream("e", unit="u2", template="t3", decisions=2, rank_sum=2),
    ]
    result = _solve(streams, 4)

    assert result.objective_vector == _brute(streams, 4)


def test_every_term_is_solved_to_proved_optimality() -> None:
    streams = [
        _stream("a", unit="u1", decisions=2, rank_sum=7),
        _stream("b", unit="u2", decisions=1, rank_sum=3),
        _stream("c", unit="u3", decisions=1, rank_sum=11),
        _stream("d", unit="u4", decisions=2, rank_sum=5),
    ]
    result = _solve(streams, 4)

    assert [proof.term for proof in result.proofs] == list(OBJECTIVE_TERMS)
    for proof in result.proofs:
        assert proof.status == "Optimal"
        assert proof.mip_gap <= 1e-9
        assert abs(proof.solver_objective_value - proof.solver_objective_bound) <= 1e-6
        assert proof.optimum == round(proof.solver_objective_value)
    assert result.solver["backend"] == "HiGHS"
    assert result.solver["mip_rel_gap"] == 0.0
    assert result.solver["threads"] == 1


def test_repeated_solves_are_byte_identical() -> None:
    streams = [
        _stream("a", unit="u1", decisions=2, rank_sum=7),
        _stream("b", unit="u2", decisions=1, rank_sum=3),
        _stream("c", unit="u3", decisions=1, rank_sum=11),
        _stream("d", unit="u4", decisions=2, rank_sum=5),
    ]
    first, second = _solve(streams, 4), _solve(streams, 4)

    assert first.selected == second.selected
    assert first.objective_vector == second.objective_vector


def test_every_published_optimum_is_reproduced_by_the_exhaustive_reference() -> None:
    streams = [
        _stream("a", unit="u1", decisions=2, rank_sum=7),
        _stream("b", unit="u2", decisions=1, rank_sum=3),
        _stream("c", unit="u2", decisions=1, rank_sum=11),
        _stream("d", unit="u3", decisions=2, rank_sum=5),
    ]
    result = _solve(streams, 4)

    assert result.objective_vector == _brute(streams, 4)


def test_an_infeasible_allocation_stops_rather_than_relaxing() -> None:
    with pytest.raises(Wp29SelectionError):
        _solve([_stream("a", unit="u1", decisions=2)], 3)


def test_candidate_rank_index_is_the_frozen_sha256_order() -> None:
    keys = [(f"sha256:{value:02x}", seq) for value in range(6) for seq in (1, 2)]
    ranks = candidate_rank_index("seed", keys)

    assert sorted(ranks.values()) == list(range(len(keys)))
    assert ranks == candidate_rank_index("seed", list(reversed(keys)))
    assert ranks != candidate_rank_index("other-seed", keys)


def test_the_optimizer_cannot_see_teacher_derived_evidence() -> None:
    """Structural proof for the bias report: no teacher field can reach the optimizer.

    The argument is by construction rather than by correlation. ``SelectionStream`` is a closed
    slotted dataclass, so a teacher field cannot be attached to a candidate; the frozen contract's
    forbidden keys appear in none of its fields; and each objective's coefficient map is keyed by
    column index over that same closed feature set.
    """
    import dataclasses

    from im.generation.phase2_wp2_9_selection import _Model, _objectives

    forbidden = (
        "teacher_agreement",
        "teacher_action",
        "teacher_confidence",
        "teacher_label",
        "disagreement_category",
    )
    fields = {field.name for field in dataclasses.fields(SelectionStream)}
    assert fields == {
        "stream_sha256",
        "family",
        "source_unit_id",
        "template_id",
        "timing_regime",
        "difficulty_tags",
        "stream_length_bucket",
        "decision_count",
        "action_counts",
        "idle_reason_counts",
        "action_floor_counts",
        "rank_sum",
    }
    assert not fields & set(forbidden)
    # A candidate cannot even carry a teacher attribute: __slots__ rejects it.
    stream = _stream("a", unit="u1")
    for key in forbidden:
        with pytest.raises(AttributeError):
            object.__setattr__(stream, key, True)

    # Every objective's recorded input is a coefficient map over column indices only.
    model = _Model()
    variables = [model.column(0, 1)]
    objectives, _size = _objectives([stream], variables, model, 1, {"f": {"idle": 1}})
    assert set(objectives) == set(OBJECTIVE_TERMS)
    for coefficients, _recompute in objectives.values():
        assert all(isinstance(column, int) for column in coefficients)


def test_stage2_frozen_proof_binds_the_published_selection_exactly() -> None:
    """The frozen optimizer inputs and proof must bind the same 354-stream selection."""
    import json
    from pathlib import Path

    from im.generation.phase2_timer_wave3_chat_import import _verify_directory
    from im.generation.phase2_wp2_9_d13 import load_binding_selection

    root = Path(__file__).resolve().parents[1]
    proof_root = root / "review/phase2/wp2-9-stage2-selection-proof"
    _verify_directory(proof_root)
    proof = json.loads((proof_root / "stage2-selection-proof.json").read_text())

    assert len(proof["optimizer_inputs"]) == 505
    assert proof["optimizer_inputs_sha256"] == (
        "sha256:" + sha256(canonical_artifact_bytes(proof["optimizer_inputs"])).hexdigest()
    )
    assert frozenset(proof["selected"]) == load_binding_selection(root)
    assert proof["stream_count"] == 354
    assert proof["decision_count"] == 2_000
    assert proof["objective_vector"] == {
        "maximum_decisions_from_one_source_unit": 18,
        "sum_squared_source_unit_counts": 21_932,
        "sum_squared_template_counts_within_family": 461_200,
        "sum_squared_timing_regime_counts_within_family": 461_200,
        "sum_squared_floor_class_counts_within_family_action": 181_660,
        "sum_squared_difficulty_tag_counts_within_family": 362_144,
        "sum_squared_stream_length_bucket_counts_within_family": 436_832,
        "candidate_order_rank_sum": 2_658_434,
    }
    assert all(term["status"] == "Optimal" and term["mip_gap"] == 0.0 for term in proof["proofs"])
