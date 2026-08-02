"""Deterministic D1 virtual service-time plans.

Timing seeds are split-scoped identities of their own.  They are not lexical
assets and are intentionally not covered by lexical asset-pool seals.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from hashlib import sha256

from im.assets.model import Split

TIMING_PROFILE_ID = "phase1-d1-service-time-v1"
TIMING_RNG_VERSION = "sha256-named-stream-v1"


class TimingPopulation(StrEnum):
    """Mutually exclusive D1 service-time populations."""

    TRAINING = "training"
    STRESS_EVAL = "stress_eval"


class TimingClass(StrEnum):
    """A stream-wide D1 latency class."""

    CORE = "core"
    ROBUSTNESS = "robustness"
    STRESS = "stress"


# Frozen one-percent inverse-CDF bins.  The 50th, 90th, and 99th percentiles
# are 650, 950, and 1,500 ms respectively; the minimum is 250 ms.
CORE_SERVICE_TABLE_MS = (
    250,
    300,
    330,
    360,
    390,
    410,
    430,
    445,
    460,
    470,
    480,
    490,
    500,
    510,
    520,
    530,
    540,
    550,
    560,
    570,
    580,
    585,
    590,
    595,
    600,
    605,
    610,
    615,
    620,
    623,
    625,
    628,
    630,
    633,
    635,
    638,
    640,
    642,
    644,
    646,
    648,
    650,
    650,
    650,
    650,
    650,
    650,
    650,
    650,
    650,
    650,
    650,
    650,
    650,
    650,
    650,
    660,
    670,
    680,
    690,
    700,
    710,
    720,
    730,
    740,
    750,
    760,
    770,
    780,
    790,
    800,
    810,
    820,
    830,
    840,
    850,
    860,
    870,
    880,
    890,
    900,
    910,
    920,
    930,
    940,
    945,
    948,
    949,
    950,
    950,
    950,
    980,
    1_010,
    1_040,
    1_080,
    1_120,
    1_200,
    1_300,
    1_500,
    1_500,
)


@dataclass(frozen=True, slots=True)
class TimingSeed:
    """A stable, split-scoped source of named timing substreams."""

    split: Split
    seed: str
    population: TimingPopulation = TimingPopulation.TRAINING

    def __post_init__(self) -> None:
        try:
            split = Split(self.split)
        except (TypeError, ValueError) as error:
            raise ValueError("split must be a known corpus split") from error
        try:
            population = TimingPopulation(self.population)
        except (TypeError, ValueError) as error:
            raise ValueError("population must be training or stress_eval") from error
        if not isinstance(self.seed, str):
            raise TypeError("seed must be a string")
        if not self.seed or self.seed.strip() != self.seed:
            raise ValueError("seed must be a non-blank trimmed string")
        object.__setattr__(self, "split", split)
        object.__setattr__(self, "population", population)

    @property
    def timing_seed_id(self) -> str:
        """Stable opaque timing identity suitable for a generation manifest."""
        return (
            "sha256:"
            + sha256(
                "\0".join(
                    (TIMING_PROFILE_ID, self.split.value, self.population.value, self.seed)
                ).encode("utf-8")
            ).hexdigest()
        )


def named_stream_u64(seed: TimingSeed, stream: str) -> int:
    """Return one stable draw for a versioned named stream."""
    if not isinstance(seed, TimingSeed):
        raise TypeError("seed must be a TimingSeed")
    if not isinstance(stream, str):
        raise TypeError("stream must be a string")
    if not stream or stream.strip() != stream:
        raise ValueError("stream must be a non-blank trimmed string")
    preimage = "\0".join(
        (
            TIMING_RNG_VERSION,
            TIMING_PROFILE_ID,
            seed.split.value,
            seed.population.value,
            seed.seed,
            stream,
        )
    )
    return int.from_bytes(sha256(preimage.encode("utf-8")).digest()[:8], "big")


def _stream_class(seed: TimingSeed) -> TimingClass:
    if seed.population is TimingPopulation.STRESS_EVAL:
        return TimingClass.STRESS
    return (
        TimingClass.ROBUSTNESS
        if named_stream_u64(seed, "stream-class") % 10 == 0
        else TimingClass.CORE
    )


def _service_ms(seed: TimingSeed, stream_class: TimingClass, index: int) -> int:
    draw = named_stream_u64(seed, f"service-time:{index}")
    if stream_class is TimingClass.CORE:
        return CORE_SERVICE_TABLE_MS[draw % len(CORE_SERVICE_TABLE_MS)]
    if stream_class is TimingClass.ROBUSTNESS:
        return 1_500 + draw % 1_501
    return 2_000 + draw % 3_001


@dataclass(frozen=True, slots=True)
class TimingPlan:
    """Materialized, immutable service times for one generated stream."""

    seed: TimingSeed
    stream_class: TimingClass
    service_ms: tuple[int, ...]
    profile_id: str = field(default=TIMING_PROFILE_ID, init=False)
    rng_version: str = field(default=TIMING_RNG_VERSION, init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.seed, TimingSeed):
            raise TypeError("seed must be a TimingSeed")
        try:
            stream_class = TimingClass(self.stream_class)
        except (TypeError, ValueError) as error:
            raise ValueError("stream_class must be a known timing class") from error
        if not isinstance(self.service_ms, tuple):
            raise TypeError("service_ms must be an immutable tuple")
        expected_class = _stream_class(self.seed)
        expected = tuple(
            _service_ms(self.seed, expected_class, index) for index in range(len(self.service_ms))
        )
        if stream_class is not expected_class or self.service_ms != expected:
            raise ValueError("TimingPlan must match its seed's named timing streams")
        object.__setattr__(self, "stream_class", stream_class)

    @property
    def population(self) -> TimingPopulation:
        return self.seed.population


def materialize_timing_plan(seed: TimingSeed, decision_count: int) -> TimingPlan:
    """Materialize one population-safe service-time plan from its timing seed."""
    if not isinstance(seed, TimingSeed):
        raise TypeError("seed must be a TimingSeed")
    if isinstance(decision_count, bool) or not isinstance(decision_count, int):
        raise TypeError("decision_count must be an integer")
    if decision_count < 0:
        raise ValueError("decision_count must be non-negative")
    stream_class = _stream_class(seed)
    return TimingPlan(
        seed=seed,
        stream_class=stream_class,
        service_ms=tuple(_service_ms(seed, stream_class, index) for index in range(decision_count)),
    )
