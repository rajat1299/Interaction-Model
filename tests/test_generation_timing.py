"""Deterministic D1 service-time plan tests."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from im.assets.model import Split
from im.generation.timing import (
    CORE_SERVICE_TABLE_MS,
    TIMING_PROFILE_ID,
    TIMING_RNG_VERSION,
    TimingClass,
    TimingPlan,
    TimingPopulation,
    TimingSeed,
    materialize_timing_plan,
    named_stream_u64,
)


def test_known_seed_materializes_the_same_immutable_plan() -> None:
    seed = TimingSeed(split=Split.TRAIN, seed="pilot-0001")

    first = materialize_timing_plan(seed, 6)
    second = materialize_timing_plan(seed, 6)

    assert first == second
    assert first.profile_id == TIMING_PROFILE_ID
    assert first.rng_version == TIMING_RNG_VERSION
    assert first.service_ms == (650, 300, 410, 360, 910, 920)
    with pytest.raises(FrozenInstanceError):
        first.stream_class = TimingClass.CORE  # type: ignore[misc]
    with pytest.raises(TypeError):
        first.service_ms[0] = 250  # type: ignore[index]


def test_split_identity_changes_the_named_streams_and_seed_identity() -> None:
    train = TimingSeed(split=Split.TRAIN, seed="same-seed")
    test = TimingSeed(split=Split.TEST, seed="same-seed")

    assert train.timing_seed_id != test.timing_seed_id
    assert named_stream_u64(train, "service-time:0") != named_stream_u64(test, "service-time:0")
    assert materialize_timing_plan(train, 8) != materialize_timing_plan(test, 8)


def test_named_service_substreams_are_independent_of_plan_length_and_class_draw() -> None:
    seed = TimingSeed(split=Split.TRAIN, seed="independent-streams")

    short = materialize_timing_plan(seed, 4)
    long = materialize_timing_plan(seed, 9)

    assert short.service_ms == long.service_ms[:4]
    assert named_stream_u64(seed, "stream-class") == named_stream_u64(seed, "stream-class")
    assert named_stream_u64(seed, "service-time:3") == named_stream_u64(seed, "service-time:3")
    assert named_stream_u64(seed, "stream-class") != named_stream_u64(seed, "service-time:3")


def test_training_and_stress_populations_are_separate_and_bounded() -> None:
    training = [
        materialize_timing_plan(TimingSeed(Split.TRAIN, f"training-{index}"), 7)
        for index in range(200)
    ]
    stress = materialize_timing_plan(
        TimingSeed(Split.TEST, "stress-0001", TimingPopulation.STRESS_EVAL), 100
    )

    assert {plan.population for plan in training} == {TimingPopulation.TRAINING}
    assert {plan.stream_class for plan in training} <= {
        TimingClass.CORE,
        TimingClass.ROBUSTNESS,
    }
    assert all(250 <= service_ms <= 3_000 for plan in training for service_ms in plan.service_ms)
    assert stress.population is TimingPopulation.STRESS_EVAL
    assert stress.stream_class is TimingClass.STRESS
    assert all(2_000 <= service_ms <= 5_000 for service_ms in stress.service_ms)


@pytest.mark.parametrize(
    ("seed", "count", "error"),
    [
        (TimingSeed(Split.TRAIN, "valid"), -1, ValueError),
        (TimingSeed(Split.TRAIN, "valid"), True, TypeError),
        (TimingSeed(Split.TRAIN, "valid"), 1.0, TypeError),
    ],
)
def test_invalid_plan_inputs_are_rejected(
    seed: TimingSeed, count: object, error: type[Exception]
) -> None:
    with pytest.raises(error):
        materialize_timing_plan(seed, count)  # type: ignore[arg-type]


def test_invalid_seed_and_tampered_plan_are_rejected() -> None:
    with pytest.raises(ValueError, match="known corpus split"):
        TimingSeed("other", "seed")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="non-blank"):
        TimingSeed(Split.TRAIN, " ")
    with pytest.raises(TypeError, match="string"):
        TimingSeed(Split.TRAIN, 7)  # type: ignore[arg-type]

    plan = materialize_timing_plan(TimingSeed(Split.TRAIN, "tamper"), 1)
    with pytest.raises(ValueError, match="named timing streams"):
        TimingPlan(seed=plan.seed, stream_class=plan.stream_class, service_ms=(250,))


def test_large_cohort_has_frozen_core_quantiles_and_roughly_ten_percent_robustness() -> None:
    plans = [
        materialize_timing_plan(TimingSeed(Split.TRAIN, f"cohort-{index}"), 1)
        for index in range(20_000)
    ]
    robustness_rate = sum(plan.stream_class is TimingClass.ROBUSTNESS for plan in plans) / len(
        plans
    )
    core = sorted(plan.service_ms[0] for plan in plans if plan.stream_class is TimingClass.CORE)

    assert 0.08 <= robustness_rate <= 0.12
    assert len(core) > 17_000
    assert core[0] == 250
    assert core[round((len(core) - 1) * 0.50)] == 650
    assert core[round((len(core) - 1) * 0.90)] == 950
    assert core[round((len(core) - 1) * 0.99)] == 1_500
    assert CORE_SERVICE_TABLE_MS[0] == 250
