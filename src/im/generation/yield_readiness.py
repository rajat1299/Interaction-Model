"""Constructive G7 allocation proof over validated concrete source units."""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from hashlib import sha256
from re import fullmatch

from im.assets.model import CorpusFamily, artifact_digest, canonical_artifact_bytes
from im.generation.corpus_segments import CorpusSegmentCandidate
from im.generation.g7_catalog import FloorOpeningTwinPrograms
from im.generation.g7_failed_response_twins import FailedResponseTwinPrograms
from im.generation.g7_response_twins import validate_response_floor_twin_alignment
from im.generation.packaging import (
    _ACTION_ORDER,
    FAMILY_ACTION_TARGETS,
    StreamManifest,
    _count_actions,
)
from im.generation.scenarios import (
    GeneratedScenario,
    PerturbationKind,
    ScenarioProgram,
    validate_generated_scenario,
)
from im.schema.actions import RespondAction

_DIGEST = r"sha256:[0-9a-f]{64}"
_SHAPE_ID = r"[a-z][a-z0-9_-]{2,127}"


class YieldReadinessError(ValueError):
    """A proposed G7 allocation is incomplete or not causally evidenced."""


def _counts_object(counts: tuple[int, ...]) -> dict[str, int]:
    return dict(zip(_ACTION_ORDER, counts, strict=True))


@dataclass(frozen=True, slots=True)
class G7SourceUnit:
    """Concrete scenario or checkpoint source retained through proof packaging."""

    shape_id: str
    family: CorpusFamily
    source_kind: str
    scenarios: tuple[GeneratedScenario, ...]
    master_seed: str
    checkpoint_candidates: tuple[CorpusSegmentCandidate, ...] = ()

    def __post_init__(self) -> None:
        if not self.scenarios:
            raise YieldReadinessError("source units must retain generated scenarios")
        if fullmatch(_SHAPE_ID, self.shape_id) is None:
            raise YieldReadinessError("source-unit shape_id is invalid")
        if not self.checkpoint_candidates:
            family, _shape, _counts, source_kind, _evidence = _scenario_unit(
                self.scenarios, shape_id=self.shape_id
            )
            if (self.family, self.source_kind) != (family, source_kind):
                raise YieldReadinessError("scenario source metadata does not match its evidence")
            return
        family, shape_id, _counts, source_kind, _evidence = _checkpoint_unit(
            self.checkpoint_candidates
        )
        if (
            self.scenarios != tuple(candidate.parent for candidate in self.checkpoint_candidates)
            or (self.family, self.shape_id, self.source_kind)
            != (family, shape_id, source_kind)
        ):
            raise YieldReadinessError("checkpoint source metadata does not match its candidate")

    @property
    def source_sha256s(self) -> tuple[str, ...]:
        if self.checkpoint_candidates:
            return tuple(
                candidate.segment.sha256
                for candidate in sorted(
                    self.checkpoint_candidates, key=lambda item: item.segment.sha256
                )
            )
        return tuple(sorted(scenario.stream.sha256 for scenario in self.scenarios))

    @property
    def source_decision_counts(self) -> tuple[int, ...]:
        if self.checkpoint_candidates:
            return tuple(
                candidate.decision_count
                for candidate in sorted(
                    self.checkpoint_candidates, key=lambda item: item.segment.sha256
                )
            )
        return tuple(
            len(scenario.sidecar.decisions)
            for scenario in sorted(self.scenarios, key=lambda item: item.stream.sha256)
        )

    @property
    def selected_call_indices(self) -> tuple[int, ...]:
        if len(self.checkpoint_candidates) == 1:
            return self.checkpoint_candidates[0].selected_call_indices
        return ()

    @property
    def selected_call_indices_by_source(self) -> tuple[tuple[int, ...], ...]:
        return tuple(
            candidate.selected_call_indices
            for candidate in sorted(
                self.checkpoint_candidates, key=lambda item: item.segment.sha256
            )
        )

    @property
    def action_counts(self) -> tuple[int, ...]:
        actions = (
            tuple(
                action
                for candidate in self.checkpoint_candidates
                for action in candidate.selected_actions
            )
            if self.checkpoint_candidates
            else tuple(action for scenario in self.scenarios for action in scenario.program.actions)
        )
        return _count_actions(actions)

    @property
    def checkpoint_metadata(self) -> dict[str, object] | None:
        if not self.checkpoint_candidates:
            return None
        if len(self.checkpoint_candidates) > 1:
            return {
                "candidates": [
                    _checkpoint_metadata(candidate)
                    for candidate in sorted(
                        self.checkpoint_candidates, key=lambda item: item.segment.sha256
                    )
                ]
            }
        candidate = self.checkpoint_candidates[0]
        return _checkpoint_metadata(candidate)


def _checkpoint_metadata(candidate: CorpusSegmentCandidate) -> dict[str, object]:
    return {
        "stream_sha256": candidate.parent.stream.sha256,
        "segment_sha256": candidate.segment.sha256,
        "segment_index": candidate.segment_index,
        "checkpoint_seq": candidate.checkpoint_seq,
        "previous_segment_hash": candidate.previous_segment_hash,
        "selected_call_indices": list(candidate.selected_call_indices),
    }


@dataclass(frozen=True, slots=True)
class G7EvidenceUnit:
    """One concrete selectable unit, possibly a complete counterfactual group."""

    source_sha256s: tuple[str, ...]
    source_decision_counts: tuple[int, ...]

    def __post_init__(self) -> None:
        if (
            not self.source_sha256s
            or self.source_sha256s != tuple(sorted(set(self.source_sha256s)))
            or any(fullmatch(_DIGEST, value) is None for value in self.source_sha256s)
        ):
            raise YieldReadinessError("source identities must be unique sorted sha256 digests")
        if len(self.source_sha256s) != len(self.source_decision_counts) or any(
            isinstance(value, bool) or not isinstance(value, int) or value <= 0
            for value in self.source_decision_counts
        ):
            raise YieldReadinessError("source decision counts must align with source identities")

    @property
    def decision_count(self) -> int:
        return sum(self.source_decision_counts)

    def as_json_object(self) -> dict[str, object]:
        return {
            "source_sha256s": list(self.source_sha256s),
            "source_decision_counts": list(self.source_decision_counts),
        }


@dataclass(frozen=True, slots=True)
class G7ShapeAllocation:
    """One selectable shape bound to one distinct source unit per multiplicity."""

    family: CorpusFamily
    shape_id: str
    action_counts: tuple[int, ...]
    source_kind: str
    source_units: tuple[G7EvidenceUnit, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.family, CorpusFamily):
            raise TypeError("family must be a CorpusFamily")
        if not isinstance(self.shape_id, str) or fullmatch(_SHAPE_ID, self.shape_id) is None:
            raise YieldReadinessError("shape_id must be a stable lowercase identifier")
        if len(self.action_counts) != len(_ACTION_ORDER) or any(
            isinstance(value, bool) or not isinstance(value, int) or value < 0
            for value in self.action_counts
        ):
            raise YieldReadinessError("action_counts are invalid")
        if self.source_kind not in {"scenario", "counterfactual", "checkpoint_segment"}:
            raise YieldReadinessError("source_kind is not closed")
        if not self.source_units or not all(
            isinstance(unit, G7EvidenceUnit) for unit in self.source_units
        ):
            raise TypeError("source_units must contain G7EvidenceUnit values")
        if self.source_kind == "scenario" and any(
            len(unit.source_sha256s) != 1 for unit in self.source_units
        ):
            raise YieldReadinessError("scenario units must bind exactly one stream")
        if self.source_kind == "counterfactual" and any(
            len(unit.source_sha256s) < 2 for unit in self.source_units
        ):
            raise YieldReadinessError("counterfactual units must bind every sibling stream")
        if self.source_units != tuple(
            sorted(self.source_units, key=lambda unit: unit.source_sha256s)
        ):
            raise YieldReadinessError("source units must be sorted by source identity")
        if any(unit.decision_count != sum(self.action_counts) for unit in self.source_units):
            raise YieldReadinessError("source decision counts do not match the action vector")
        source_sha256s = self.source_sha256s
        if len(source_sha256s) != len(set(source_sha256s)):
            raise YieldReadinessError(
                "a source stream or checkpoint segment may fund one unit only"
            )

    @classmethod
    def from_scenarios(
        cls,
        shape_id: str,
        scenario_units: tuple[tuple[GeneratedScenario, ...], ...],
    ) -> G7ShapeAllocation:
        """Bind one allocation unit to each validated stream or complete sibling group."""
        if not isinstance(scenario_units, tuple):
            raise TypeError("scenario_units must be an immutable tuple")
        details = tuple(
            (family, shape_id, action_counts, source_kind, evidence)
            for family, _unit_shape, action_counts, source_kind, evidence in (
                _scenario_unit(unit, shape_id=shape_id) for unit in scenario_units
            )
        )
        return cls._from_units(shape_id, details)

    @classmethod
    def from_checkpoint_segments(
        cls,
        segment_units: tuple[tuple[CorpusSegmentCandidate, ...], ...],
    ) -> G7ShapeAllocation:
        """Bind one allocation unit to each validated checkpoint selection or sibling group."""
        if not isinstance(segment_units, tuple):
            raise TypeError("segment_units must be an immutable tuple")
        details = tuple(_checkpoint_unit(unit) for unit in segment_units)
        return cls._from_units(details[0][1] if details else "", details)

    @classmethod
    def _from_units(
        cls,
        shape_id: str,
        details: tuple[tuple[CorpusFamily, str, tuple[int, ...], str, G7EvidenceUnit], ...],
    ) -> G7ShapeAllocation:
        if not details:
            raise YieldReadinessError("shape must include at least one concrete source unit")
        family, unit_shape_id, action_counts, source_kind, _unit = details[0]
        if shape_id != unit_shape_id:
            raise YieldReadinessError("source units do not match the allocation shape")
        if any(
            (candidate_family, candidate_shape_id, candidate_counts, candidate_kind)
            != (family, unit_shape_id, action_counts, source_kind)
            for (
                candidate_family,
                candidate_shape_id,
                candidate_counts,
                candidate_kind,
                _candidate_unit,
            ) in details
        ):
            raise YieldReadinessError("source units must share one family, shape, vector, and kind")
        return cls(
            family=family,
            shape_id=shape_id,
            action_counts=action_counts,
            source_kind=source_kind,
            source_units=tuple(
                sorted((unit for *_detail, unit in details), key=lambda unit: unit.source_sha256s)
            ),
        )

    @property
    def multiplicity(self) -> int:
        """Concrete source-unit count; it cannot be claimed independently."""
        return len(self.source_units)

    @property
    def source_sha256s(self) -> tuple[str, ...]:
        return tuple(source for unit in self.source_units for source in unit.source_sha256s)

    @property
    def source_decision_counts(self) -> tuple[int, ...]:
        return tuple(count for unit in self.source_units for count in unit.source_decision_counts)

    @property
    def within_target_band(self) -> bool:
        return all(6 <= count <= 20 for count in self.source_decision_counts) or bool(
            self.decision_band_exception
        )

    @property
    def decision_band_exception(self) -> str | None:
        """Name the honest exception required by terminal floor counterfactuals."""
        counts = _counts_object(self.action_counts)
        if (
            self.shape_id.startswith("g7-response-floor-")
            and self.source_kind == "counterfactual"
            and counts["idle"] == counts["respond"] == 1
            and sum(counts.values()) == 2
            and all(unit.source_decision_counts == (1, 1) for unit in self.source_units)
        ):
            return "terminal_floor_counterfactual"
        return None

    def as_json_object(self) -> dict[str, object]:
        return {
            "shape_id": self.shape_id,
            "source_kind": self.source_kind,
            "source_units": [unit.as_json_object() for unit in self.source_units],
            "within_6_20_decision_band": all(
                6 <= count <= 20 for count in self.source_decision_counts
            ),
            "decision_band_exception": self.decision_band_exception,
            "multiplicity": self.multiplicity,
            "action_counts_per_unit": _counts_object(self.action_counts),
            "allocated_action_counts": _counts_object(
                tuple(value * self.multiplicity for value in self.action_counts)
            ),
        }


def _scenario_unit(
    scenarios: tuple[GeneratedScenario, ...],
    *,
    shape_id: str = "",
) -> tuple[CorpusFamily, str, tuple[int, ...], str, G7EvidenceUnit]:
    if not isinstance(scenarios, tuple) or not scenarios:
        raise YieldReadinessError("each scenario source unit must be a non-empty tuple")
    for scenario in scenarios:
        validate_generated_scenario(scenario)
    programs = tuple(scenario.program for scenario in scenarios)
    source_kind = _counterfactual_kind(programs, shape_id=shape_id)
    manifests = tuple(
        sorted(
            (StreamManifest.from_generated(scenario) for scenario in scenarios),
            key=lambda manifest: manifest.stream_sha256,
        )
    )
    return (
        programs[0].family,
        "",
        tuple(
            sum(_count_actions(program.actions)[index] for program in programs)
            for index in range(len(_ACTION_ORDER))
        ),
        source_kind,
        G7EvidenceUnit(
            source_sha256s=tuple(manifest.stream_sha256 for manifest in manifests),
            source_decision_counts=tuple(manifest.decision_count for manifest in manifests),
        ),
    )


def _checkpoint_unit(
    candidates: tuple[CorpusSegmentCandidate, ...],
) -> tuple[CorpusFamily, str, tuple[int, ...], str, G7EvidenceUnit]:
    if not isinstance(candidates, tuple) or not candidates:
        raise YieldReadinessError("each checkpoint source unit must be a non-empty tuple")
    if not all(isinstance(candidate, CorpusSegmentCandidate) for candidate in candidates):
        raise TypeError("checkpoint source units must contain CorpusSegmentCandidate values")
    programs = tuple(candidate.parent.program for candidate in candidates)
    source_kind = _counterfactual_kind(programs, shape_id=candidates[0].shape_id)
    if source_kind == "scenario" and len(candidates) != 1:
        raise YieldReadinessError("ordinary checkpoint source units must contain one segment")
    if len({candidate.shape_id for candidate in candidates}) != 1:
        raise YieldReadinessError("checkpoint sibling segments must share one shape")
    for candidate in candidates:
        validate_generated_scenario(candidate.parent)
    ordered = tuple(sorted(candidates, key=lambda candidate: candidate.segment.sha256))
    return (
        programs[0].family,
        candidates[0].shape_id,
        tuple(
            sum(_count_actions(candidate.selected_actions)[index] for candidate in candidates)
            for index in range(len(_ACTION_ORDER))
        ),
        "checkpoint_segment",
        G7EvidenceUnit(
            source_sha256s=tuple(candidate.segment.sha256 for candidate in ordered),
            source_decision_counts=tuple(candidate.decision_count for candidate in ordered),
        ),
    )


def _counterfactual_kind(programs: tuple[ScenarioProgram, ...], *, shape_id: str = "") -> str:
    if not programs or any(program.family is not programs[0].family for program in programs):
        raise YieldReadinessError("source unit programs must share one family")
    declarations = tuple(program.counterfactual for program in programs)
    if len(programs) == 1:
        if declarations[0] is not None:
            raise YieldReadinessError("counterfactual source units must include every sibling")
        return "scenario"
    if any(declaration is None for declaration in declarations):
        raise YieldReadinessError("multi-program source units must be one counterfactual group")
    first = declarations[0]
    assert first is not None
    declaration_key = (
        first.kind,
        first.group_id,
        first.member_ids,
        first.flipped_perturbation,
    )
    if (
        len(programs) != len(first.member_ids)
        or tuple(
            sorted(declaration.member_id for declaration in declarations if declaration is not None)
        )
        != first.member_ids
        or any(
            declaration is None
            or (
                declaration.kind,
                declaration.group_id,
                declaration.member_ids,
                declaration.flipped_perturbation,
            )
            != declaration_key
            for declaration in declarations
        )
        or any(_common_inputs(program) != _common_inputs(programs[0]) for program in programs[1:])
    ):
        raise YieldReadinessError("counterfactual source unit is incomplete or inconsistent")
    if first.flipped_perturbation is PerturbationKind.FLOOR_OPENING:
        by_member = {
            program.counterfactual.member_id: program
            for program in programs
            if program.counterfactual is not None
        }
        if set(by_member) != {"active", "yielded"}:
            raise YieldReadinessError("floor-opening source unit must be a complete twin")
        if shape_id.startswith("g7-response-floor-"):
            try:
                validate_response_floor_twin_alignment(
                    by_member["yielded"], by_member["active"]
                )
            except ValueError as error:
                raise YieldReadinessError(
                    "response-floor source is not an isolated terminal twin"
                ) from error
        else:
            try:
                FloorOpeningTwinPrograms(
                    programs[0].family,
                    first.group_id,
                    0,
                    (by_member["active"], by_member["yielded"]),
                )
            except ValueError:
                try:
                    FailedResponseTwinPrograms(
                        (by_member["yielded"], by_member["active"]),
                        ("yielded", "active"),
                    )
                except ValueError as error:
                    raise YieldReadinessError(
                        "floor-opening source unit is not an exact twin"
                    ) from error
    return "counterfactual"


def _common_inputs(program: ScenarioProgram) -> tuple[object, ...]:
    """Program inputs that must remain shared before a generic sibling contrast."""
    return (
        program.family,
        program.bundle.split,
        program.master_seed,
        program.timing_plan,
        program.template,
        program.bundle,
        program.config,
        program.annotations,
        program.perturbations,
    )


@dataclass(frozen=True, slots=True)
class G7YieldReadiness:
    """An exact, constructive 2,000-decision allocation bound to source evidence."""

    prior_inventory_sha256: str
    allocations: tuple[G7ShapeAllocation, ...]
    canonical_bytes: bytes = field(init=False)
    sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if fullmatch(_DIGEST, self.prior_inventory_sha256) is None:
            raise YieldReadinessError("prior inventory identity must be a sha256 digest")
        if not self.allocations or not all(
            isinstance(item, G7ShapeAllocation) for item in self.allocations
        ):
            raise TypeError("allocations must contain G7ShapeAllocation values")
        keys = tuple((item.family.value, item.shape_id) for item in self.allocations)
        if keys != tuple(sorted(set(keys))):
            raise YieldReadinessError("allocations must be uniquely sorted by family and shape")
        source_sha256s = tuple(
            source for allocation in self.allocations for source in allocation.source_sha256s
        )
        if len(source_sha256s) != len(set(source_sha256s)):
            raise YieldReadinessError("one concrete source may fund only one allocation unit")
        if not all(item.within_target_band for item in self.allocations):
            raise YieldReadinessError(
                "every allocation source must contain 6–20 decisions or be a terminal floor twin"
            )
        for family in CorpusFamily:
            target = tuple(FAMILY_ACTION_TARGETS[family].get(action, 0) for action in _ACTION_ORDER)
            actual = tuple(
                sum(
                    item.action_counts[index] * item.multiplicity
                    for item in self.allocations
                    if item.family is family
                )
                for index in range(len(_ACTION_ORDER))
            )
            if actual != target:
                raise YieldReadinessError(
                    f"{family.value} does not exactly reach its frozen target"
                )
        canonical = canonical_artifact_bytes(self.as_json_object())
        object.__setattr__(self, "canonical_bytes", canonical)
        object.__setattr__(self, "sha256", artifact_digest(self.as_json_object()))

    @property
    def total_decisions(self) -> int:
        return sum(sum(item.action_counts) * item.multiplicity for item in self.allocations)

    def as_json_object(self) -> dict[str, object]:
        families = []
        for family in sorted(CorpusFamily, key=lambda item: item.value):
            rows = tuple(item for item in self.allocations if item.family is family)
            families.append(
                {
                    "family": family.value,
                    "target_action_counts": FAMILY_ACTION_TARGETS[family],
                    "allocations": [item.as_json_object() for item in rows],
                }
            )
        return {
            "format_version": 1,
            "prior_inventory_sha256": self.prior_inventory_sha256,
            "exactly_reachable": True,
            "total_decisions": self.total_decisions,
            "all_sources_within_6_20_decision_band": all(
                all(6 <= count <= 20 for count in item.source_decision_counts)
                for item in self.allocations
            ),
            "terminal_floor_counterfactual_exception_count": sum(
                item.multiplicity
                for item in self.allocations
                if item.decision_band_exception is not None
            ),
            "all_sources_satisfy_packaging_target": all(
                item.within_target_band for item in self.allocations
            ),
            "families": families,
        }


def build_yield_inventory_delta(
    readiness: G7YieldReadiness, prior_inventory_bytes: bytes
) -> bytes:
    """Bind the formerly unreachable inventory to the exact additive G7 proof."""
    prior_inventory_sha256 = f"sha256:{sha256(prior_inventory_bytes).hexdigest()}"
    if readiness.prior_inventory_sha256 != prior_inventory_sha256:
        raise YieldReadinessError("prior inventory bytes do not match the G7 readiness proof")
    try:
        prior = json.loads(prior_inventory_bytes)
        prior_families = {item["family"]: item for item in prior["families"]}
    except (KeyError, TypeError, json.JSONDecodeError) as error:
        raise YieldReadinessError("prior yield inventory is not structurally valid") from error
    if set(prior_families) != {family.value for family in CorpusFamily}:
        raise YieldReadinessError("prior yield inventory does not cover every family")

    rows = []
    for family in sorted(CorpusFamily, key=lambda item: item.value):
        before = prior_families[family.value]
        target = {
            action: FAMILY_ACTION_TARGETS[family].get(action, 0)
            for action in _ACTION_ORDER
        }
        if before.get("target_action_counts") != target:
            raise YieldReadinessError(f"prior target drifted for {family.value}")
        allocations = tuple(item for item in readiness.allocations if item.family is family)
        allocated = {
            action: sum(
                item.action_counts[index] * item.multiplicity for item in allocations
            )
            for index, action in enumerate(_ACTION_ORDER)
        }
        if allocated != target:
            raise YieldReadinessError(f"G7 allocation does not close {family.value}")
        rows.append(
            {
                "family": family.value,
                "before_reachable": before.get("reachable") is True,
                "before_gaps": before.get("gaps", []),
                "after_reachable": True,
                "target_action_counts": target,
                "allocated_action_counts": allocated,
                "additive_shape_ids": sorted(item.shape_id for item in allocations),
            }
        )
    return canonical_artifact_bytes(
        {
            "format_version": 1,
            "prior_inventory_sha256": prior_inventory_sha256,
            "g7_readiness_sha256": readiness.sha256,
            "approved_c5_pilot_bytes_mutated": False,
            "before_reachable_family_count": sum(
                row["before_reachable"] is True for row in rows
            ),
            "after_reachable_family_count": len(rows),
            "exact_2000_action_allocation_reachable": readiness.total_decisions == 2_000,
            "families": rows,
        }
    )


def build_yield_evidence(scenarios: Iterable[GeneratedScenario]) -> bytes:
    """Bind every ordinary response to its warrant and open-floor snapshot."""
    evidence = []
    for scenario in scenarios:
        for decision in scenario.sidecar.decisions:
            if not isinstance(decision.action, RespondAction):
                continue
            if (
                decision.response_warrant_kind is None
                or decision.response_warrant_snapshot_event_id is None
                or decision.floor_open is not True
            ):
                raise YieldReadinessError("respond decision lacks complete yield evidence")
            evidence.append(
                {
                    "stream_sha256": scenario.stream.sha256,
                    "call_index": decision.call_index,
                    "observed_policy_seq": decision.observed_policy_seq,
                    "response_warrant_kind": decision.response_warrant_kind.value,
                    "response_warrant_snapshot_event_id": (
                        decision.response_warrant_snapshot_event_id
                    ),
                    "floor_opening_snapshot_event_id": (
                        decision.floor_opening_snapshot_event_id
                    ),
                }
            )
    if len(evidence) != 90:
        raise YieldReadinessError("G7 allocation must evidence all 90 respond actions")
    return canonical_artifact_bytes(
        {
            "format_version": 1,
            "respond_decision_count": len(evidence),
            "evidence": sorted(
                evidence, key=lambda item: (item["stream_sha256"], item["call_index"])
            ),
        }
    )
