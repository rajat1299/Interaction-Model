"""Focused tests for the deterministic zero-network calibration policy."""

from __future__ import annotations

import pytest

from im.generation.timing import TIMING_PROFILE_ID
from im.policy.latency_stub import (
    CORE_SERVICE_TABLE_ID,
    LATENCY_STUB_POLICY_ID,
    LATENCY_STUB_RNG_VERSION,
    LATENCY_STUB_SAMPLER_ID,
    D1LatencySampler,
    LatencyStubPolicy,
    latency_stub_metadata,
)


def test_sampler_has_a_closed_seeded_core_sequence_and_metadata() -> None:
    sampler = D1LatencySampler("calibration-17")

    assert [sampler.draw_ms(index) for index in range(5)] == [470, 1_200, 580, 648, 480]
    assert sampler.metadata.sampler_id == LATENCY_STUB_SAMPLER_ID
    assert sampler.metadata.profile_id == TIMING_PROFILE_ID
    assert sampler.metadata.rng_version == LATENCY_STUB_RNG_VERSION
    assert sampler.metadata.table_id == CORE_SERVICE_TABLE_ID
    assert sampler.metadata.seed == "calibration-17"
    assert (
        sampler.metadata.seed_id
        == "sha256:04233293711c2b87f8642bc4903523711938e23ffd4c600a2ed0add4cae71183"
    )
    assert sampler.metadata.population == "calibration_reference"
    assert sampler.metadata.latency_class == "core"
    assert latency_stub_metadata("calibration-17") == {
        "policy_id": LATENCY_STUB_POLICY_ID,
        "network": "disabled",
        "action": {"type": "idle", "reason": "no_trigger", "related_event_id": None},
        "sampler": sampler.metadata.as_json_object(),
    }


@pytest.mark.asyncio
async def test_policy_sleeps_for_its_draw_and_always_returns_idle() -> None:
    delays: list[float] = []

    async def capture_sleep(delay: float) -> None:
        delays.append(delay)

    policy = LatencyStubPolicy("calibration-17", sleep=capture_sleep)

    first = await policy.decide(b"first")
    second = await policy.decide(b"second")

    assert first == second == {"type": "idle", "reason": "no_trigger", "related_event_id": None}
    assert delays == [0.47, 1.2]
    assert policy.call_count == 2
    assert policy.last_latency_ms == 1_200
    assert policy.calibration_decision_metadata() == {
        "decision_index": 1,
        "planned_latency_ms": 1_200,
    }


@pytest.mark.parametrize(
    ("seed", "error"),
    [("", ValueError), (" seed", ValueError), (7, TypeError)],
)
def test_sampler_rejects_invalid_seeds(seed: object, error: type[Exception]) -> None:
    with pytest.raises(error):
        D1LatencySampler(seed)  # type: ignore[arg-type]
