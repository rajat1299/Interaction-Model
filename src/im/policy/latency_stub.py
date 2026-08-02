"""Deterministic, zero-network latency stub for calibration runs."""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from hashlib import sha256

from im.generation.timing import CORE_SERVICE_TABLE_MS, TIMING_PROFILE_ID

LATENCY_STUB_SAMPLER_ID = "phase1-c7-latency-stub-v1"
LATENCY_STUB_POLICY_ID = "calibration-idle/v1"
LATENCY_STUB_RNG_VERSION = "sha256-length-framed-modulo-v1"
_POPULATION = "calibration_reference"
_LATENCY_CLASS = "core"
_IDLE_ACTION = {"type": "idle", "reason": "no_trigger", "related_event_id": None}
CORE_SERVICE_TABLE_ID = "sha256:" + sha256(
    ",".join(str(value) for value in CORE_SERVICE_TABLE_MS).encode("ascii")
).hexdigest()

type Sleep = Callable[[float], Awaitable[object]]


def _hash_parts(*parts: str) -> bytes:
    """Hash length-framed UTF-8 strings so seed contents cannot change boundaries."""
    digest = sha256()
    for part in parts:
        encoded = part.encode("utf-8")
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
    return digest.digest()


def _validate_seed(seed: object) -> str:
    if not isinstance(seed, str):
        raise TypeError("seed must be a string")
    if not seed or seed.strip() != seed:
        raise ValueError("seed must be a non-blank trimmed string")
    try:
        seed.encode("utf-8")
    except UnicodeEncodeError as error:
        raise ValueError("seed must be valid UTF-8") from error
    return seed


@dataclass(frozen=True, slots=True)
class LatencySamplerMetadata:
    """Exact, serializable identity of this closed calibration sampler."""

    sampler_id: str
    seed: str
    seed_id: str
    profile_id: str
    rng_version: str
    table_id: str
    population: str
    latency_class: str

    def as_json_object(self) -> dict[str, str]:
        return {
            "sampler_id": self.sampler_id,
            "seed": self.seed,
            "seed_id": self.seed_id,
            "profile_id": self.profile_id,
            "rng_version": self.rng_version,
            "table_id": self.table_id,
            "population": self.population,
            "latency_class": self.latency_class,
        }


def latency_stub_metadata(seed: str) -> dict[str, object]:
    """Return the closed provenance record persisted with calibration evidence."""
    return {
        "policy_id": LATENCY_STUB_POLICY_ID,
        "network": "disabled",
        "action": dict(_IDLE_ACTION),
        "sampler": D1LatencySampler(seed).metadata.as_json_object(),
    }


class D1LatencySampler:
    """Sample the frozen core D1 inverse-CDF table from named hash draws."""

    def __init__(self, seed: str) -> None:
        self.seed = _validate_seed(seed)
        self._seed_id = "sha256:" + _hash_parts(
            LATENCY_STUB_SAMPLER_ID,
            LATENCY_STUB_RNG_VERSION,
            TIMING_PROFILE_ID,
            CORE_SERVICE_TABLE_ID,
            self.seed,
        ).hex()

    @property
    def metadata(self) -> LatencySamplerMetadata:
        return LatencySamplerMetadata(
            sampler_id=LATENCY_STUB_SAMPLER_ID,
            seed=self.seed,
            seed_id=self._seed_id,
            profile_id=TIMING_PROFILE_ID,
            rng_version=LATENCY_STUB_RNG_VERSION,
            table_id=CORE_SERVICE_TABLE_ID,
            population=_POPULATION,
            latency_class=_LATENCY_CLASS,
        )

    def draw_ms(self, decision_index: int) -> int:
        """Return one deterministic core latency for the zero-based decision index."""
        if isinstance(decision_index, bool) or not isinstance(decision_index, int):
            raise TypeError("decision_index must be an integer")
        if decision_index < 0:
            raise ValueError("decision_index must be non-negative")
        draw = int.from_bytes(
            _hash_parts(
                LATENCY_STUB_SAMPLER_ID,
                LATENCY_STUB_RNG_VERSION,
                TIMING_PROFILE_ID,
                CORE_SERVICE_TABLE_ID,
                self.seed,
                str(decision_index),
            ),
            "big",
        )
        # The authority table is the v1 piecewise-constant inverse CDF; terminal bins cap its tail.
        return CORE_SERVICE_TABLE_MS[draw % len(CORE_SERVICE_TABLE_MS)]


class LatencyStubPolicy:
    """Policy-compatible calibration stub that never performs network I/O."""

    def __init__(self, seed: str, *, sleep: Sleep = asyncio.sleep) -> None:
        if not callable(sleep):
            raise TypeError("sleep must be callable")
        self.sampler = D1LatencySampler(seed)
        self._sleep = sleep
        self.call_count = 0
        self.last_latency_ms: int | None = None

    @property
    def metadata(self) -> LatencySamplerMetadata:
        return self.sampler.metadata

    @property
    def calibration_metadata(self) -> dict[str, object]:
        return latency_stub_metadata(self.sampler.seed)

    def calibration_decision_metadata(self) -> dict[str, int]:
        if self.last_latency_ms is None or self.call_count == 0:
            raise RuntimeError("latency stub has not completed a decision")
        return {
            "decision_index": self.call_count - 1,
            "planned_latency_ms": self.last_latency_ms,
        }

    async def decide(self, policy_bytes: bytes) -> object:
        if not isinstance(policy_bytes, bytes):
            raise TypeError("policy_bytes must be bytes")
        latency_ms = self.sampler.draw_ms(self.call_count)
        self.call_count += 1
        self.last_latency_ms = latency_ms
        pending = self._sleep(latency_ms / 1_000)
        if not inspect.isawaitable(pending):
            raise TypeError("sleep must return an awaitable")
        await pending
        return dict(_IDLE_ACTION)
