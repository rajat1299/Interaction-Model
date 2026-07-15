"""Canonical C6 manifests and split-isolation ledgers for generated scenarios."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from re import fullmatch

from im.assets.model import (
    CorpusFamily,
    LookupAssetPayload,
    Split,
    TimerAssetPayload,
    artifact_digest,
    canonical_artifact_bytes,
)
from im.generation.scenarios import (
    CounterfactualDeclaration,
    GeneratedScenario,
    ScenarioProgram,
    validate_generated_scenario,
)
from im.schema.actions import DelegateAction, ScheduleAction

_DIGEST = r"sha256:[0-9a-f]{64}"
_FORMAT_VERSION = 1
_ACTION_ORDER = (
    "idle",
    "mark",
    "nudge",
    "delegate",
    "integrate",
    "skip",
    "schedule",
    "respond",
    "cancel",
)

# Build-plan §3 action targets.  These are a reachability contract, not a
# license to rebalance a shortfall away from its family.
FAMILY_ACTION_TARGETS: dict[CorpusFamily, dict[str, int]] = {
    CorpusFamily.NEUTRAL_TYPING: {"idle": 250, "respond": 30},
    CorpusFamily.MARK_POSITIVE: {"idle": 120, "mark": 150, "respond": 10},
    CorpusFamily.MARK_NEGATIVE: {"idle": 150, "mark": 60, "respond": 10},
    CorpusFamily.LOOKUP_LIVE: {
        "idle": 100,
        "delegate": 80,
        "integrate": 80,
        "respond": 20,
    },
    CorpusFamily.LOOKUP_DUPLICATE: {
        "idle": 130,
        "delegate": 50,
        "integrate": 30,
        "skip": 30,
    },
    CorpusFamily.LOOKUP_STALE: {"idle": 50, "skip": 50, "respond": 20},
    CorpusFamily.TIMER_NORMAL: {"idle": 50, "schedule": 70, "nudge": 130},
    CorpusFamily.TIMER_CANCEL: {
        "idle": 70,
        "schedule": 20,
        "cancel": 50,
        "nudge": 20,
        "skip": 20,
    },
    CorpusFamily.TIMER_CONTENTION: {
        "idle": 30,
        "schedule": 10,
        "cancel": 10,
        "nudge": 30,
        "mark": 10,
    },
    CorpusFamily.ROLLOVER: {
        "idle": 40,
        "mark": 2,
        "delegate": 1,
        "integrate": 2,
        "skip": 2,
        "cancel": 1,
        "nudge": 2,
    },
    CorpusFamily.RESERVED: {"idle": 10},
}


class PackagingError(ValueError):
    """A package or split ledger violates a C6 identity invariant."""


def _digest(value: object, name: str) -> str:
    if not isinstance(value, str) or fullmatch(_DIGEST, value) is None:
        raise PackagingError(f"{name} must be a sha256 digest")
    return value


def _nonblank(value: object, name: str) -> str:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise PackagingError(f"{name} must be a non-blank trimmed string")
    return value


def _sorted_unique(values: object, name: str) -> tuple[str, ...]:
    if not isinstance(values, tuple) or any(not isinstance(value, str) for value in values):
        raise TypeError(f"{name} must be an immutable tuple of strings")
    if values != tuple(sorted(set(values))):
        raise PackagingError(f"{name} must be sorted and unique")
    return values


@dataclass(frozen=True, slots=True)
class CounterfactualLink:
    """The non-prompt linkage declared for one counterfactual stream."""

    kind: str
    group_id: str
    member_id: str
    member_ids: tuple[str, ...]
    flipped_perturbation: str

    @classmethod
    def from_declaration(cls, declaration: CounterfactualDeclaration) -> CounterfactualLink:
        return cls(
            kind=declaration.kind.value,
            group_id=declaration.group_id,
            member_id=declaration.member_id,
            member_ids=declaration.member_ids,
            flipped_perturbation=declaration.flipped_perturbation.value,
        )

    def __post_init__(self) -> None:
        for name in ("kind", "group_id", "member_id", "flipped_perturbation"):
            _nonblank(getattr(self, name), name)
        _sorted_unique(self.member_ids, "member_ids")
        if self.member_id not in self.member_ids:
            raise PackagingError("counterfactual member_id is not declared")

    def as_json_object(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "group_id": self.group_id,
            "member_id": self.member_id,
            "member_ids": list(self.member_ids),
            "flipped_perturbation": self.flipped_perturbation,
        }


@dataclass(frozen=True, slots=True)
class StreamManifest:
    """The immutable package record for one already-validated generated stream."""

    engine_version: str
    split: Split | str
    family: CorpusFamily | str
    template_id: str
    template_content_sha256: str
    assets: tuple[tuple[str, str], ...]
    master_seed: str
    timing_seed_id: str
    timing_profile_id: str
    timing_rng_version: str
    timing_population: str
    timing_class: str
    stream_sha256: str
    capture_sha256: str
    sidecar_sha256: str
    teacher_segment_sha256s: tuple[str, ...]
    decision_count: int
    regeneration_identity: str
    scenario_input_sha256: str
    world_script_sha256: str
    declared_perturbations: tuple[str, ...]
    counterfactual: CounterfactualLink | None
    canonical_bytes: bytes = field(init=False)
    sha256: str = field(init=False)

    def __post_init__(self) -> None:
        for name in (
            "engine_version",
            "template_id",
            "master_seed",
            "timing_profile_id",
            "timing_rng_version",
            "timing_population",
            "timing_class",
        ):
            _nonblank(getattr(self, name), name)
        try:
            split = Split(self.split)
            family = CorpusFamily(self.family)
        except (TypeError, ValueError) as error:
            raise PackagingError("split or family is not closed") from error
        if not isinstance(self.assets, tuple) or not self.assets:
            raise PackagingError("assets must be a non-empty immutable tuple")
        asset_ids = tuple(asset_id for asset_id, _digest_value in self.assets)
        if asset_ids != tuple(sorted(set(asset_ids))):
            raise PackagingError("asset ids must be sorted and unique")
        for asset_id, digest in self.assets:
            _nonblank(asset_id, "asset_id")
            _digest(digest, "asset content hash")
        for name in (
            "template_content_sha256",
            "timing_seed_id",
            "stream_sha256",
            "capture_sha256",
            "sidecar_sha256",
            "regeneration_identity",
            "scenario_input_sha256",
            "world_script_sha256",
        ):
            _digest(getattr(self, name), name)
        if not isinstance(self.teacher_segment_sha256s, tuple) or not self.teacher_segment_sha256s:
            raise PackagingError("teacher_segment_sha256s must be a non-empty immutable tuple")
        for digest in self.teacher_segment_sha256s:
            _digest(digest, "teacher segment hash")
        if isinstance(self.decision_count, bool) or not isinstance(self.decision_count, int):
            raise TypeError("decision_count must be an integer")
        if self.decision_count < 0:
            raise PackagingError("decision_count must be non-negative")
        _sorted_unique(self.declared_perturbations, "declared_perturbations")
        if self.counterfactual is not None and not isinstance(
            self.counterfactual, CounterfactualLink
        ):
            raise TypeError("counterfactual must be a CounterfactualLink or None")
        object.__setattr__(self, "split", split)
        object.__setattr__(self, "family", family)
        canonical = canonical_artifact_bytes(self.as_json_object())
        object.__setattr__(self, "canonical_bytes", canonical)
        object.__setattr__(self, "sha256", artifact_digest(self.as_json_object()))

    @classmethod
    def from_generated(cls, generated: GeneratedScenario) -> StreamManifest:
        """Build only from the existing complete runtime and sidecar proof."""
        try:
            sidecar = validate_generated_scenario(generated)
        except (TypeError, ValueError) as error:
            raise PackagingError("generated scenario does not validate") from error
        program = generated.program
        stream = generated.stream
        return cls(
            engine_version=stream.provenance.engine_version,
            split=sidecar.split,
            family=sidecar.family,
            template_id=sidecar.template_id,
            template_content_sha256=sidecar.template_content_sha256,
            assets=tuple(zip(sidecar.asset_ids, sidecar.asset_content_sha256s, strict=True)),
            master_seed=stream.provenance.master_seed,
            timing_seed_id=stream.timing_plan.seed.timing_seed_id,
            timing_profile_id=stream.timing_plan.profile_id,
            timing_rng_version=stream.timing_plan.rng_version,
            timing_population=stream.timing_plan.population.value,
            timing_class=stream.timing_plan.stream_class.value,
            stream_sha256=stream.sha256,
            capture_sha256=stream.capture_sha256,
            sidecar_sha256=sidecar.sha256,
            teacher_segment_sha256s=tuple(segment.sha256 for segment in stream.segments),
            decision_count=len(sidecar.decisions),
            regeneration_identity=stream.provenance.identity,
            scenario_input_sha256=program.input_hash,
            world_script_sha256=program.world_script_hash,
            declared_perturbations=tuple(item.kind.value for item in sidecar.perturbations),
            counterfactual=(
                None
                if sidecar.counterfactual is None
                else CounterfactualLink.from_declaration(sidecar.counterfactual)
            ),
        )

    def as_json_object(self) -> dict[str, object]:
        return {
            "format_version": _FORMAT_VERSION,
            "engine_version": self.engine_version,
            "split": self.split.value,
            "family": self.family.value,
            "template": {
                "asset_id": self.template_id,
                "content_sha256": self.template_content_sha256,
            },
            "assets": [
                {"asset_id": asset_id, "content_sha256": digest}
                for asset_id, digest in self.assets
            ],
            "master_seed": self.master_seed,
            "timing": {
                "seed_id": self.timing_seed_id,
                "profile_id": self.timing_profile_id,
                "rng_version": self.timing_rng_version,
                "population": self.timing_population,
                "class": self.timing_class,
            },
            "stream_sha256": self.stream_sha256,
            "capture_sha256": self.capture_sha256,
            "sidecar_sha256": self.sidecar_sha256,
            "teacher_segment_sha256s": list(self.teacher_segment_sha256s),
            "decision_count": self.decision_count,
            "identities": {
                "regeneration": self.regeneration_identity,
                "scenario_input": self.scenario_input_sha256,
                "world_script": self.world_script_sha256,
            },
            "declared_perturbations": list(self.declared_perturbations),
            "counterfactual": (
                None if self.counterfactual is None else self.counterfactual.as_json_object()
            ),
        }


@dataclass(frozen=True, slots=True)
class PackageManifest:
    """A deterministic batch manifest with one record per unique stream identity."""

    streams: tuple[StreamManifest, ...]
    canonical_bytes: bytes = field(init=False)
    sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.streams, tuple) or not self.streams:
            raise PackagingError("streams must be a non-empty immutable tuple")
        if not all(isinstance(stream, StreamManifest) for stream in self.streams):
            raise TypeError("streams must contain StreamManifest instances")
        identities = tuple(stream.stream_sha256 for stream in self.streams)
        if identities != tuple(sorted(identities)):
            raise PackagingError("streams must be sorted by stream identity")
        if len(identities) != len(set(identities)):
            raise PackagingError("duplicate stream identity")
        canonical = canonical_artifact_bytes(self.as_json_object())
        object.__setattr__(self, "canonical_bytes", canonical)
        object.__setattr__(self, "sha256", artifact_digest(self.as_json_object()))

    @classmethod
    def build(cls, generated: Iterable[GeneratedScenario]) -> PackageManifest:
        streams = tuple(StreamManifest.from_generated(item) for item in generated)
        return cls(streams=tuple(sorted(streams, key=lambda item: item.stream_sha256)))

    def as_json_object(self) -> dict[str, object]:
        return {
            "format_version": _FORMAT_VERSION,
            "streams": [stream.as_json_object() for stream in self.streams],
        }


def _scalar_values(value: object) -> tuple[object, ...]:
    if isinstance(value, dict):
        return tuple(item for child in value.values() for item in _scalar_values(child))
    if isinstance(value, list):
        return tuple(item for child in value for item in _scalar_values(child))
    return (value,)


def _value_digest(label: str, value: object) -> str:
    return artifact_digest({label: value})


@dataclass(frozen=True, slots=True)
class SplitLedgerEntry:
    """One safe-to-share row: only IDs and digests, never teacher prompt text."""

    split: Split | str
    stream_sha256: str
    template_id: str
    asset_ids: tuple[str, ...]
    timing_seed_material_sha256: str
    lookup_value_sha256s: tuple[str, ...]
    tool_result_sha256s: tuple[str, ...]
    timer_message_sha256s: tuple[str, ...]
    canonical_bytes: bytes = field(init=False)
    sha256: str = field(init=False)

    def __post_init__(self) -> None:
        try:
            split = Split(self.split)
        except (TypeError, ValueError) as error:
            raise PackagingError("ledger split is not closed") from error
        _digest(self.stream_sha256, "stream_sha256")
        _nonblank(self.template_id, "template_id")
        _sorted_unique(self.asset_ids, "asset_ids")
        for name in (
            "timing_seed_material_sha256",
            "lookup_value_sha256s",
            "tool_result_sha256s",
            "timer_message_sha256s",
        ):
            value = getattr(self, name)
            if isinstance(value, tuple):
                _sorted_unique(value, name)
                for digest in value:
                    _digest(digest, name)
            else:
                _digest(value, name)
        object.__setattr__(self, "split", split)
        canonical = canonical_artifact_bytes(self.as_json_object())
        object.__setattr__(self, "canonical_bytes", canonical)
        object.__setattr__(self, "sha256", artifact_digest(self.as_json_object()))

    @classmethod
    def from_generated(
        cls, generated: GeneratedScenario, manifest: StreamManifest
    ) -> SplitLedgerEntry:
        program = generated.program
        lookup_values: list[object] = []
        timer_messages: list[str] = []
        for asset in program.bundle.assets:
            if isinstance(asset.payload, LookupAssetPayload):
                lookup_values.extend(
                    (
                        asset.payload.query,
                        asset.payload.result_a,
                        asset.payload.result_b,
                        asset.payload.no_result_code,
                    )
                )
            elif isinstance(asset.payload, TimerAssetPayload) and asset.payload.message is not None:
                timer_messages.append(asset.payload.message)
        for action in program.actions:
            if isinstance(action, DelegateAction):
                lookup_values.extend((action.fact.text, action.args.query))
            elif isinstance(action, ScheduleAction):
                timer_messages.append(action.message)
        for result in program.tool_results:
            lookup_values.extend(_scalar_values(result.data))
        return cls(
            split=manifest.split,
            stream_sha256=manifest.stream_sha256,
            template_id=manifest.template_id,
            asset_ids=tuple(asset_id for asset_id, _digest_value in manifest.assets),
            timing_seed_material_sha256=_value_digest(
                "raw_timing_seed", program.timing_plan.seed.seed
            ),
            lookup_value_sha256s=tuple(
                sorted({_value_digest("lookup_value", value) for value in lookup_values})
            ),
            tool_result_sha256s=tuple(
                sorted(
                    {_value_digest("tool_result", result.data) for result in program.tool_results}
                )
            ),
            timer_message_sha256s=tuple(
                sorted({_value_digest("timer_message", message) for message in timer_messages})
            ),
        )

    def as_json_object(self) -> dict[str, object]:
        return {
            "split": self.split.value,
            "stream_sha256": self.stream_sha256,
            "template_id": self.template_id,
            "asset_ids": list(self.asset_ids),
            "timing_seed_material_sha256": self.timing_seed_material_sha256,
            "lookup_value_sha256s": list(self.lookup_value_sha256s),
            "tool_result_sha256s": list(self.tool_result_sha256s),
            "timer_message_sha256s": list(self.timer_message_sha256s),
        }


@dataclass(frozen=True, slots=True)
class SplitLedger:
    """Batch-wide, mechanical proof that tracked inputs do not cross split boundaries."""

    entries: tuple[SplitLedgerEntry, ...]
    canonical_bytes: bytes = field(init=False)
    sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.entries, tuple) or not self.entries:
            raise PackagingError("entries must be a non-empty immutable tuple")
        if not all(isinstance(entry, SplitLedgerEntry) for entry in self.entries):
            raise TypeError("entries must contain SplitLedgerEntry instances")
        identities = tuple(entry.stream_sha256 for entry in self.entries)
        if identities != tuple(sorted(identities)):
            raise PackagingError("ledger entries must be sorted by stream identity")
        if len(identities) != len(set(identities)):
            raise PackagingError("duplicate stream identity")
        self._reject_cross_split_reuse()
        canonical = canonical_artifact_bytes(self.as_json_object())
        object.__setattr__(self, "canonical_bytes", canonical)
        object.__setattr__(self, "sha256", artifact_digest(self.as_json_object()))

    @classmethod
    def build(cls, generated: Iterable[GeneratedScenario]) -> SplitLedger:
        scenarios = tuple(generated)
        manifest = PackageManifest.build(scenarios)
        by_stream = {item.stream.sha256: item for item in scenarios}
        entries = tuple(
            SplitLedgerEntry.from_generated(by_stream[item.stream_sha256], item)
            for item in manifest.streams
        )
        return cls(entries=entries)

    def _reject_cross_split_reuse(self) -> None:
        checks = (
            ("template_id", lambda entry: (entry.template_id,)),
            ("asset_id", lambda entry: entry.asset_ids),
            ("timing seed material", lambda entry: (entry.timing_seed_material_sha256,)),
            ("lookup value", lambda entry: entry.lookup_value_sha256s),
            ("tool result", lambda entry: entry.tool_result_sha256s),
            ("timer message", lambda entry: entry.timer_message_sha256s),
        )
        for label, values in checks:
            owners: dict[str, set[Split]] = {}
            for entry in self.entries:
                for value in values(entry):
                    owners.setdefault(value, set()).add(entry.split)
            for value, splits in sorted(owners.items()):
                if len(splits) > 1:
                    names = ", ".join(sorted(split.value for split in splits))
                    raise PackagingError(f"cross-split {label} reuse: {value} in {names}")

    def as_json_object(self) -> dict[str, object]:
        return {
            "format_version": _FORMAT_VERSION,
            "entries": [entry.as_json_object() for entry in self.entries],
        }


def package_generated_streams(generated: Iterable[GeneratedScenario]) -> PackageManifest:
    """Build the canonical batch manifest from validated generated scenarios."""
    return PackageManifest.build(generated)


def build_split_ledger(generated: Iterable[GeneratedScenario]) -> SplitLedger:
    """Build the canonical split ledger and reject any tracked cross-split reuse."""
    return SplitLedger.build(generated)


def _count_actions(actions: tuple[object, ...]) -> tuple[int, ...]:
    counts = {name: 0 for name in _ACTION_ORDER}
    for action in actions:
        name = getattr(action, "type", None)
        if name not in counts:
            raise PackagingError("candidate program has an unknown action class")
        counts[name] += 1
    return tuple(counts[name] for name in _ACTION_ORDER)


def _counts_object(counts: tuple[int, ...]) -> dict[str, int]:
    return dict(zip(_ACTION_ORDER, counts, strict=True))


@dataclass(frozen=True, slots=True)
class YieldCandidate:
    """One reusable action shape and the concrete units that supplied it."""

    candidate_sha256: str
    source_unit_sha256s: tuple[str, ...]
    source_program_count: int
    action_counts: tuple[int, ...]

    def __post_init__(self) -> None:
        _digest(self.candidate_sha256, "candidate_sha256")
        _sorted_unique(self.source_unit_sha256s, "source_unit_sha256s")
        if not self.source_unit_sha256s:
            raise PackagingError("yield candidate must have at least one source unit")
        for digest in self.source_unit_sha256s:
            _digest(digest, "source_unit_sha256")
        if (
            isinstance(self.source_program_count, bool)
            or not isinstance(self.source_program_count, int)
            or self.source_program_count < len(self.source_unit_sha256s)
        ):
            raise PackagingError("source_program_count must cover every source unit")
        if len(self.action_counts) != len(_ACTION_ORDER) or any(
            isinstance(value, bool) or not isinstance(value, int) or value < 0
            for value in self.action_counts
        ):
            raise PackagingError("candidate action_counts are invalid")
        if not any(self.action_counts):
            raise PackagingError("candidate program has no decisions")

    def as_json_object(self) -> dict[str, object]:
        return {
            "candidate_sha256": self.candidate_sha256,
            "source_unit_sha256s": list(self.source_unit_sha256s),
            "source_program_count": self.source_program_count,
            "action_counts": _counts_object(self.action_counts),
        }


@dataclass(frozen=True, slots=True)
class YieldGap:
    """An explicit action deficit when whole-program vectors cannot hit a target."""

    action: str
    target_minus: int
    reason: str

    def __post_init__(self) -> None:
        if self.action not in _ACTION_ORDER:
            raise PackagingError("yield gap action is not closed")
        if isinstance(self.target_minus, bool) or not isinstance(self.target_minus, int):
            raise TypeError("yield gap target_minus must be an integer")
        if self.target_minus <= 0:
            raise PackagingError("yield gap target_minus must be positive")
        _nonblank(self.reason, "yield gap reason")

    def as_json_object(self) -> dict[str, object]:
        return {"action": self.action, "target_minus": self.target_minus, "reason": self.reason}


@dataclass(frozen=True, slots=True)
class FamilyYield:
    """Target reachability and actual supplied-batch tally for one corpus family."""

    family: CorpusFamily | str
    target_action_counts: tuple[int, ...]
    realized_action_counts: tuple[int, ...]
    candidates: tuple[YieldCandidate, ...]
    reachable: bool
    multiplicities: tuple[tuple[str, int], ...]
    gaps: tuple[YieldGap, ...]

    def __post_init__(self) -> None:
        try:
            family = CorpusFamily(self.family)
        except (TypeError, ValueError) as error:
            raise PackagingError("yield family is not closed") from error
        for name in ("target_action_counts", "realized_action_counts"):
            counts = getattr(self, name)
            if len(counts) != len(_ACTION_ORDER) or any(
                isinstance(value, bool) or not isinstance(value, int) or value < 0
                for value in counts
            ):
                raise PackagingError(f"{name} is invalid")
        if not isinstance(self.candidates, tuple) or not all(
            isinstance(candidate, YieldCandidate) for candidate in self.candidates
        ):
            raise TypeError("candidates must contain YieldCandidate instances")
        identities = tuple(candidate.candidate_sha256 for candidate in self.candidates)
        if identities != tuple(sorted(identities)) or len(identities) != len(set(identities)):
            raise PackagingError("yield candidates must be uniquely sorted")
        if not isinstance(self.reachable, bool):
            raise TypeError("reachable must be a bool")
        if not isinstance(self.multiplicities, tuple) or any(
            not isinstance(identity, str)
            or isinstance(count, bool)
            or not isinstance(count, int)
            or count <= 0
            for identity, count in self.multiplicities
        ):
            raise TypeError("multiplicities must be positive immutable identity/count pairs")
        if tuple(identity for identity, _count in self.multiplicities) != tuple(
            sorted(identity for identity, _count in self.multiplicities)
        ):
            raise PackagingError("multiplicities must be sorted")
        if any(identity not in identities for identity, _count in self.multiplicities):
            raise PackagingError("multiplicity refers to an unknown yield candidate")
        if not isinstance(self.gaps, tuple) or not all(
            isinstance(gap, YieldGap) for gap in self.gaps
        ):
            raise TypeError("gaps must contain YieldGap instances")
        if self.reachable != (not self.gaps):
            raise PackagingError("reachable and gaps disagree")
        if not self.reachable and self.multiplicities:
            raise PackagingError("unreachable family cannot claim a solution")
        object.__setattr__(self, "family", family)

    def as_json_object(self) -> dict[str, object]:
        return {
            "family": self.family.value,
            "target_action_counts": _counts_object(self.target_action_counts),
            "realized_action_counts": _counts_object(self.realized_action_counts),
            "candidates": [candidate.as_json_object() for candidate in self.candidates],
            "reachable": self.reachable,
            "multiplicities": [
                {"candidate_sha256": identity, "count": count}
                for identity, count in self.multiplicities
            ],
            "gaps": [gap.as_json_object() for gap in self.gaps],
        }


def _add_counts(left: tuple[int, ...], right: tuple[int, ...], multiplier: int) -> tuple[int, ...]:
    return tuple(value + multiplier * added for value, added in zip(left, right, strict=True))


def _within_target(counts: tuple[int, ...], target: tuple[int, ...]) -> bool:
    return all(value <= limit for value, limit in zip(counts, target, strict=True))


def _reachable_states(
    candidates: tuple[YieldCandidate, ...], target: tuple[int, ...]
) -> dict[tuple[int, ...], tuple[int, ...]]:
    """Exact bounded DP; every state is a non-overshooting whole-program total."""
    states: dict[tuple[int, ...], tuple[int, ...]] = {tuple(0 for _ in target): ()}
    for candidate in candidates:
        next_states: dict[tuple[int, ...], tuple[int, ...]] = {}
        positive = tuple(
            limit // value
            for value, limit in zip(candidate.action_counts, target, strict=True)
            if value
        )
        bound = min(positive, default=0)
        for state, multiplicities in states.items():
            for count in range(bound + 1):
                total = _add_counts(state, candidate.action_counts, count)
                if _within_target(total, target):
                    next_states.setdefault(total, multiplicities + (count,))
        states = next_states
    return states


def _family_yield(
    family: CorpusFamily, candidates: tuple[YieldCandidate, ...]
) -> FamilyYield:
    target = tuple(FAMILY_ACTION_TARGETS[family].get(action, 0) for action in _ACTION_ORDER)
    realized = tuple(
        sum(
            len(candidate.source_unit_sha256s) * candidate.action_counts[index]
            for candidate in candidates
        )
        for index in range(len(target))
    )
    states = _reachable_states(candidates, target)
    multiplicities = states.get(target)
    if multiplicities is not None:
        return FamilyYield(
            family=family,
            target_action_counts=target,
            realized_action_counts=realized,
            candidates=candidates,
            reachable=True,
            multiplicities=tuple(
                (candidate.candidate_sha256, count)
                for candidate, count in zip(candidates, multiplicities, strict=True)
                if count
            ),
            gaps=(),
        )
    closest = min(
        states,
        key=lambda counts: (
            sum(limit - value for value, limit in zip(counts, target, strict=True)),
            tuple(limit - value for value, limit in zip(counts, target, strict=True)),
        ),
    )
    available = tuple(
        sum(row.action_counts[index] for row in candidates) for index in range(len(target))
    )
    gaps = tuple(
        YieldGap(
            action=action,
            target_minus=limit - value,
            reason=(
                "missing action class"
                if available[index] == 0
                else "no exact whole-program combination"
            ),
        )
        for index, (action, value, limit) in enumerate(
            zip(_ACTION_ORDER, closest, target, strict=True)
        )
        if value < limit
    )
    return FamilyYield(
        family=family,
        target_action_counts=target,
        realized_action_counts=realized,
        candidates=candidates,
        reachable=False,
        multiplicities=(),
        gaps=gaps,
    )


@dataclass(frozen=True, slots=True)
class YieldInventory:
    """Canonical G-7 dry-run: candidate reachability is separate from batch realization."""

    families: tuple[FamilyYield, ...]
    canonical_bytes: bytes = field(init=False)
    sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.families, tuple) or not all(
            isinstance(family, FamilyYield) for family in self.families
        ):
            raise TypeError("families must contain FamilyYield instances")
        ids = tuple(family.family.value for family in self.families)
        if ids != tuple(sorted(ids)) or len(ids) != len(set(ids)):
            raise PackagingError("yield families must be uniquely sorted")
        if set(ids) != {family.value for family in CorpusFamily}:
            raise PackagingError("yield inventory must cover every corpus family")
        canonical = canonical_artifact_bytes(self.as_json_object())
        object.__setattr__(self, "canonical_bytes", canonical)
        object.__setattr__(self, "sha256", artifact_digest(self.as_json_object()))

    def as_json_object(self) -> dict[str, object]:
        return {
            "format_version": _FORMAT_VERSION,
            "families": [family.as_json_object() for family in self.families],
        }


def build_yield_inventory(
    candidates: Iterable[ScenarioProgram | GeneratedScenario],
) -> YieldInventory:
    """Count supplied whole programs and prove, or disprove, exact family-target reachability."""
    grouped: dict[CorpusFamily, list[tuple[str, int, tuple[int, ...]]]] = {
        family: [] for family in CorpusFamily
    }
    counterfactual_groups: dict[str, list[ScenarioProgram]] = {}
    input_hashes: set[str] = set()
    for candidate in candidates:
        if isinstance(candidate, GeneratedScenario):
            validate_generated_scenario(candidate)
            program = candidate.program
        elif isinstance(candidate, ScenarioProgram):
            program = candidate
        else:
            raise TypeError("yield candidates must be ScenarioProgram or GeneratedScenario")
        if program.input_hash in input_hashes:
            raise PackagingError(f"duplicate yield candidate for {program.family.value}")
        input_hashes.add(program.input_hash)
        if program.counterfactual is None:
            grouped[program.family].append(
                (program.input_hash, 1, _count_actions(program.actions))
            )
        else:
            counterfactual_groups.setdefault(program.counterfactual.group_id, []).append(program)

    for group_id, programs in sorted(counterfactual_groups.items()):
        first = programs[0]
        declaration = first.counterfactual
        assert declaration is not None
        member_ids = tuple(
            sorted(
                program.counterfactual.member_id
                for program in programs
                if program.counterfactual is not None
            )
        )
        declaration_shape = (
            declaration.kind,
            declaration.member_ids,
            declaration.flipped_perturbation,
        )
        if (
            len(programs) != len(declaration.member_ids)
            or member_ids != declaration.member_ids
            or any(program.family is not first.family for program in programs)
            or any(
                program.counterfactual is None
                or (
                    program.counterfactual.kind,
                    program.counterfactual.member_ids,
                    program.counterfactual.flipped_perturbation,
                )
                != declaration_shape
                for program in programs
            )
        ):
            raise PackagingError(f"counterfactual group {group_id} is incomplete or inconsistent")
        member_hashes = tuple(sorted(program.input_hash for program in programs))
        grouped[first.family].append(
            (
                artifact_digest(
                    {"counterfactual_group_id": group_id, "member_inputs": member_hashes}
                ),
                len(programs),
                tuple(
                    sum(_count_actions(program.actions)[index] for program in programs)
                    for index in range(len(_ACTION_ORDER))
                ),
            )
        )
    families = []
    for family in sorted(CorpusFamily, key=lambda item: item.value):
        by_counts: dict[tuple[int, ...], list[tuple[str, int]]] = {}
        for unit_sha256, program_count, action_counts in grouped[family]:
            by_counts.setdefault(action_counts, []).append((unit_sha256, program_count))
        rows = tuple(
            sorted(
                (
                    YieldCandidate(
                        candidate_sha256=artifact_digest(
                            {"yield_shape": _counts_object(action_counts)}
                        ),
                        source_unit_sha256s=tuple(
                            sorted(unit_sha256 for unit_sha256, _count in units)
                        ),
                        source_program_count=sum(count for _unit_sha256, count in units),
                        action_counts=action_counts,
                    )
                    for action_counts, units in by_counts.items()
                ),
                key=lambda item: item.candidate_sha256,
            )
        )
        families.append(_family_yield(family, rows))
    return YieldInventory(families=tuple(families))
