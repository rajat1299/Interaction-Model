"""Strict C5 scenario inputs and oracle sidecars over the production runtime."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from re import fullmatch

from im.assets.model import AssetRecord, CorpusFamily, Split, TemplateAssetPayload
from im.assets.registry import AssetBundle, AssetRegistry
from im.canonical_json import canonicalize_tim_json, parse_tim_json
from im.config import RuntimeConfig
from im.generation.ingestion import (
    CapturedDecision,
    GeneratedStream,
    RuntimeIngestionRunner,
    ScheduledAnnotation,
    ScheduledSamplerFrame,
    _attempt_bytes,
    _digest,
    _framed_bytes,
)
from im.generation.need_lineage import (
    BeatNeedLineage,
    CancelResolutionEvidence,
    DelegateProvenance,
    FactualNeed,
    NeedBasisKind,
    NeedLineage,
    NeedStatus,
    build_skip_evidence,
    declared_need_skips,
    derive_cancel_resolution_evidence,
    validate_authored_need_lineage,
    validate_cancel_resolution_declarations,
)
from im.generation.oracle import (
    ACTION_TYPES,
    BeatOpening,
    BeatResponseWarrant,
    ResponseWarrantKind,
    ScenarioValidationError,
    validate_oracle_action,
)
from im.generation.runtime import DecisionBoundary
from im.generation.sidecar import (
    BeatEvidence,
    CounterfactualDeclaration,
    CounterfactualKind,
    DeclaredPerturbation,
    OracleDecision,
    OracleSidecar,
    PerturbationKind,
    decode_sidecar_effective_view,
)
from im.generation.timing import TimingPlan
from im.generation.validity import validate_generated_stream
from im.license import Allowed, SnapshotView, TimerFireView, ToolResultView, check
from im.schema.actions import (
    Action,
    DelegateAction,
    IdleAction,
    IdleReason,
    IntegrateAction,
    RespondAction,
    SkipAction,
    SkipReason,
)
from im.schema.common import Disposition, TimerStatus
from im.tools import ScriptedToolResult

__all__ = (
    "BeatNeedLineage",
    "BeatOpening",
    "BeatResponseWarrant",
    "CancelResolutionEvidence",
    "CounterfactualDeclaration",
    "CounterfactualKind",
    "DeclaredPerturbation",
    "DelegateProvenance",
    "FactualNeed",
    "NeedLineage",
    "NeedBasisKind",
    "NeedStatus",
    "OracleDecision",
    "OracleSidecar",
    "PerturbationKind",
    "ResponseWarrantKind",
    "decode_sidecar_effective_view",
)

_BEAT_ID = r"[a-z][a-z0-9_-]{0,63}"
_EVENT_ID = r"e_[0-9]{6}"


class ScenarioExecutionError(RuntimeError):
    """A runtime execution diverged from its finite scenario program."""


@dataclass(frozen=True, slots=True)
class BeatStaleResults:
    """The exact stale-tool subset declared for one semantic beat."""

    beat_id: str
    tool_result_event_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_id(self.beat_id, _BEAT_ID, "beat_id")
        _require_sorted_unique_ids(self.tool_result_event_ids, _EVENT_ID, "tool_result_event_ids")

    def as_json_object(self) -> dict[str, object]:
        return {
            "beat_id": self.beat_id,
            "tool_result_event_ids": list(self.tool_result_event_ids),
        }


def select_approved_scenario_inputs(
    registry: AssetRegistry,
    *,
    split: Split | str,
    template_id: str,
    asset_ids: tuple[str, ...],
) -> tuple[AssetBundle, AssetRecord]:
    """Resolve the only approval-enforced inputs accepted by public scenario builders."""
    if not isinstance(registry, AssetRegistry):
        raise TypeError("registry must be an AssetRegistry")
    pool = registry.pool(split)
    template = next((item for item in pool.templates if item.asset_id == template_id), None)
    if template is None:
        raise ScenarioValidationError("template is absent from the selected split")
    if not registry.is_approved(template):
        raise ScenarioValidationError("template is not approved")
    return pool.bundle(*asset_ids), template


@dataclass(frozen=True, slots=True)
class ScenarioProgram:
    """Frozen concrete runtime inputs; there is no symbolic action resolver."""

    bundle: AssetBundle
    template: AssetRecord
    family: CorpusFamily | str
    master_seed: str
    timing_plan: TimingPlan
    frames: tuple[ScheduledSamplerFrame, ...]
    actions: tuple[Action, ...]
    tool_results: tuple[ScriptedToolResult, ...]
    beat_ids: tuple[str, ...]
    stale_results_by_beat: tuple[BeatStaleResults, ...]
    perturbations: tuple[DeclaredPerturbation, ...]
    annotations: tuple[ScheduledAnnotation, ...] = ()
    config: RuntimeConfig = field(default_factory=RuntimeConfig)
    counterfactual: CounterfactualDeclaration | None = None
    response_warrants_by_beat: tuple[BeatResponseWarrant, ...] = ()
    openings_by_beat: tuple[BeatOpening, ...] | None = None
    need_lineage_by_beat: tuple[BeatNeedLineage, ...] | None = None
    delegate_provenance_by_beat: tuple[DelegateProvenance, ...] | None = None
    cancel_resolution_evidence_by_beat: tuple[CancelResolutionEvidence, ...] = ()
    require_g7_evidence: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.bundle, AssetBundle):
            raise TypeError("bundle must be an AssetBundle")
        if not isinstance(self.template, AssetRecord) or not isinstance(
            self.template.payload, TemplateAssetPayload
        ):
            raise ScenarioValidationError("template must be an actual template AssetRecord")
        try:
            family = CorpusFamily(self.family)
        except (TypeError, ValueError) as error:
            raise ScenarioValidationError("family must be a known corpus family") from error
        if self.template.split is not self.bundle.split:
            raise ScenarioValidationError("template and bundle must use the same split")
        if family not in self.template.coverage:
            raise ScenarioValidationError("template does not cover scenario family")
        if not any(family in asset.coverage for asset in self.bundle.assets):
            raise ScenarioValidationError("at least one selected asset must cover scenario family")
        if any(
            asset.template_asset_id not in (None, self.template.asset_id)
            for asset in self.bundle.assets
        ):
            raise ScenarioValidationError("selected asset belongs to a different template")
        if not isinstance(self.master_seed, str) or self.master_seed.strip() != self.master_seed:
            raise ScenarioValidationError("master_seed must be a non-blank trimmed string")
        if not isinstance(self.timing_plan, TimingPlan):
            raise TypeError("timing_plan must be a TimingPlan")
        if self.timing_plan.seed.split is not self.bundle.split:
            raise ScenarioValidationError("timing plan and bundle must use the same split")
        _require_tuple(self.frames, ScheduledSamplerFrame, "frames")
        _require_tuple(self.annotations, ScheduledAnnotation, "annotations")
        _require_tuple(self.actions, ACTION_TYPES, "actions")
        _require_tuple(self.tool_results, ScriptedToolResult, "tool_results")
        if not isinstance(self.beat_ids, tuple):
            raise TypeError("beat_ids must be an immutable tuple")
        for beat_id in self.beat_ids:
            _require_id(beat_id, _BEAT_ID, "beat_id")
        expected = len(self.timing_plan.service_ms)
        if len(self.actions) != expected or len(self.beat_ids) != expected:
            raise ScenarioValidationError(
                "actions, beat_ids, and timing plan must have exact lengths"
            )
        _require_tuple(self.stale_results_by_beat, BeatStaleResults, "stale_results_by_beat")
        stale_by_beat = {item.beat_id: item for item in self.stale_results_by_beat}
        if len(stale_by_beat) != len(self.stale_results_by_beat) or set(stale_by_beat) != set(
            self.beat_ids
        ):
            raise ScenarioValidationError("each beat must declare exactly one stale-result subset")
        _require_tuple(
            self.response_warrants_by_beat,
            BeatResponseWarrant,
            "response_warrants_by_beat",
        )
        warrant_by_beat = {item.beat_id: item for item in self.response_warrants_by_beat}
        if len(warrant_by_beat) != len(self.response_warrants_by_beat) or not set(
            warrant_by_beat
        ).issubset(self.beat_ids):
            raise ScenarioValidationError("response warrants must name distinct program beats")
        for beat_id, action in zip(self.beat_ids, self.actions, strict=True):
            warrant = warrant_by_beat.get(beat_id)
            if warrant is None:
                continue
            if isinstance(action, RespondAction):
                continue
            if (
                isinstance(action, IdleAction)
                and action.reason is IdleReason.AWAITING_OPENING
                and (
                    action.related_event_id == warrant.snapshot_event_id
                    or (
                        warrant.failed_result_event_id is not None
                        and action.related_event_id == warrant.failed_result_event_id
                    )
                )
            ):
                continue
            raise ScenarioValidationError(
                "response warrants may only declare matching response or awaiting-opening beats"
            )
        if tuple(item.beat_id for item in self.response_warrants_by_beat) != tuple(
            beat_id for beat_id in self.beat_ids if beat_id in warrant_by_beat
        ):
            raise ScenarioValidationError("response warrants must follow program beat order")
        if self.openings_by_beat is not None:
            _require_tuple(self.openings_by_beat, BeatOpening, "openings_by_beat")
            openings = {item.beat_id: item for item in self.openings_by_beat}
            if len(openings) != len(self.openings_by_beat) or not set(openings).issubset(
                self.beat_ids
            ):
                raise ScenarioValidationError("openings must name distinct program beats")
            if tuple(item.beat_id for item in self.openings_by_beat) != tuple(
                beat_id for beat_id in self.beat_ids if beat_id in openings
            ):
                raise ScenarioValidationError("openings must follow program beat order")
            for beat_id, action in zip(self.beat_ids, self.actions, strict=True):
                is_open = beat_id in openings
                if isinstance(action, IntegrateAction | RespondAction) and not is_open:
                    raise ScenarioValidationError("integrate and respond beats require an opening")
                if (
                    isinstance(action, IdleAction)
                    and action.reason is IdleReason.AWAITING_OPENING
                    and is_open
                ):
                    raise ScenarioValidationError(
                        "awaiting-opening beats must keep the floor closed"
                    )
        validate_authored_need_lineage(
            self.beat_ids,
            self.actions,
            self.need_lineage_by_beat,
            self.delegate_provenance_by_beat,
        )
        validate_cancel_resolution_declarations(
            self.beat_ids,
            self.actions,
            self.cancel_resolution_evidence_by_beat,
            require_evidence=self.require_g7_evidence,
        )
        _require_tuple(self.perturbations, DeclaredPerturbation, "perturbations")
        kinds = tuple(item.kind for item in self.perturbations)
        if kinds != tuple(sorted(set(kinds), key=str)):
            raise ScenarioValidationError("perturbations must be uniquely sorted by kind")
        if not isinstance(self.config, RuntimeConfig):
            raise TypeError("config must be a RuntimeConfig")
        if not isinstance(self.require_g7_evidence, bool):
            raise TypeError("require_g7_evidence must be a bool")
        if self.counterfactual is not None and not isinstance(
            self.counterfactual, CounterfactualDeclaration
        ):
            raise TypeError("counterfactual must be a CounterfactualDeclaration or None")
        if (
            self.counterfactual is not None
            and self.counterfactual.flipped_perturbation not in kinds
        ):
            raise ScenarioValidationError("counterfactual flip must be a declared perturbation")
        if sum(isinstance(action, DelegateAction) for action in self.actions) != len(
            self.tool_results
        ):
            raise ScenarioValidationError(
                "tool results must exactly match concrete delegate actions"
            )
        object.__setattr__(self, "family", family)

    @classmethod
    def select(
        cls,
        registry: AssetRegistry,
        *,
        split: Split | str,
        template_id: str,
        asset_ids: tuple[str, ...],
        family: CorpusFamily | str,
        master_seed: str,
        timing_plan: TimingPlan,
        frames: tuple[ScheduledSamplerFrame, ...],
        actions: tuple[Action, ...],
        tool_results: tuple[ScriptedToolResult, ...],
        beat_ids: tuple[str, ...],
        stale_results_by_beat: tuple[BeatStaleResults, ...],
        perturbations: tuple[DeclaredPerturbation, ...],
        annotations: tuple[ScheduledAnnotation, ...] = (),
        config: RuntimeConfig | None = None,
        counterfactual: CounterfactualDeclaration | None = None,
        response_warrants_by_beat: tuple[BeatResponseWarrant, ...] = (),
        openings_by_beat: tuple[BeatOpening, ...] | None = None,
        need_lineage_by_beat: tuple[BeatNeedLineage, ...] | None = None,
        delegate_provenance_by_beat: tuple[DelegateProvenance, ...] | None = None,
        cancel_resolution_evidence_by_beat: tuple[CancelResolutionEvidence, ...] = (),
        require_g7_evidence: bool = False,
    ) -> ScenarioProgram:
        """Build from the registry's only approval-enforced bundle selection path."""
        bundle, template = select_approved_scenario_inputs(
            registry,
            split=split,
            template_id=template_id,
            asset_ids=asset_ids,
        )
        return cls(
            bundle=bundle,
            template=template,
            family=family,
            master_seed=master_seed,
            timing_plan=timing_plan,
            frames=frames,
            actions=actions,
            tool_results=tool_results,
            beat_ids=beat_ids,
            stale_results_by_beat=stale_results_by_beat,
            perturbations=perturbations,
            annotations=annotations,
            config=config or RuntimeConfig(),
            counterfactual=counterfactual,
            response_warrants_by_beat=response_warrants_by_beat,
            openings_by_beat=openings_by_beat,
            need_lineage_by_beat=need_lineage_by_beat,
            delegate_provenance_by_beat=delegate_provenance_by_beat,
            cancel_resolution_evidence_by_beat=cancel_resolution_evidence_by_beat,
            require_g7_evidence=require_g7_evidence,
        )

    @property
    def asset_ids(self) -> tuple[str, ...]:
        return tuple(asset.asset_id for asset in self.bundle.assets)

    @property
    def input_hash(self) -> str:
        return _digest(self.canonical_input_bytes)

    @property
    def world_script_hash(self) -> str:
        return _digest(
            _framed_bytes(
                "scenario-world-script",
                (
                    canonicalize_tim_json(
                        {
                            "latency_ms": result.latency_ms,
                            "status": result.status.value,
                            "data": result.data,
                        }
                    )
                    for result in self.tool_results
                ),
            )
        )

    @property
    def canonical_input_bytes(self) -> bytes:
        metadata_object: dict[str, object] = {
            "split": self.bundle.split.value,
            "template": {
                "asset_id": self.template.asset_id,
                "content_sha256": self.template.content_sha256,
            },
            "assets": [
                {"asset_id": asset.asset_id, "content_sha256": asset.content_sha256}
                for asset in self.bundle.assets
            ],
            "family": self.family.value,
            "master_seed": self.master_seed,
            "timing": {
                "split": self.timing_plan.seed.split.value,
                "seed": self.timing_plan.seed.seed,
                "population": self.timing_plan.population.value,
                "stream_class": self.timing_plan.stream_class.value,
                "service_ms": list(self.timing_plan.service_ms),
            },
            "actions": [action.model_dump(mode="json") for action in self.actions],
            "beat_ids": list(self.beat_ids),
            "stale_results_by_beat": [item.as_json_object() for item in self.stale_results_by_beat],
            "perturbations": [item.as_json_object() for item in self.perturbations],
            "config": self.config.as_json_object(),
            "counterfactual": (
                None if self.counterfactual is None else self.counterfactual.as_json_object()
            ),
        }
        if self.response_warrants_by_beat:
            metadata_object["response_warrants_by_beat"] = [
                item.as_json_object() for item in self.response_warrants_by_beat
            ]
        if self.openings_by_beat is not None:
            metadata_object["openings_by_beat"] = [
                item.as_json_object() for item in self.openings_by_beat
            ]
        if self.need_lineage_by_beat is not None:
            metadata_object["need_lineage_by_beat"] = [
                item.as_json_object() for item in self.need_lineage_by_beat
            ]
            metadata_object["delegate_provenance_by_beat"] = [
                item.as_json_object() for item in self.delegate_provenance_by_beat or ()
            ]
        if self.cancel_resolution_evidence_by_beat:
            metadata_object["cancel_resolution_evidence_by_beat"] = [
                item.as_json_object() for item in self.cancel_resolution_evidence_by_beat
            ]
        if self.require_g7_evidence:
            metadata_object["require_g7_evidence"] = True
        metadata = canonicalize_tim_json(metadata_object)
        return _framed_bytes(
            "scenario-input",
            (
                metadata,
                _framed_bytes("frames", (frame.canonical_bytes for frame in self.frames)),
                _framed_bytes("annotations", (item.canonical_bytes for item in self.annotations)),
                _framed_bytes(
                    "tool-results",
                    (
                        canonicalize_tim_json(
                            {
                                "latency_ms": result.latency_ms,
                                "status": result.status.value,
                                "data": result.data,
                            }
                        )
                        for result in self.tool_results
                    ),
                ),
            ),
        )


@dataclass(frozen=True, slots=True)
class GeneratedScenario:
    """A teacher stream with a separate sidecar and captured runtime boundaries."""

    program: ScenarioProgram = field(repr=False, compare=False)
    stream: GeneratedStream
    sidecar: OracleSidecar
    decision_boundaries: tuple[DecisionBoundary, ...] = field(repr=False, compare=False)

    def __post_init__(self) -> None:
        if not isinstance(self.program, ScenarioProgram):
            raise TypeError("program must be a ScenarioProgram")
        if not isinstance(self.stream, GeneratedStream):
            raise TypeError("stream must be a GeneratedStream")
        if not isinstance(self.sidecar, OracleSidecar):
            raise TypeError("sidecar must be an OracleSidecar")
        _require_tuple(self.decision_boundaries, DecisionBoundary, "decision_boundaries")
        if len(self.decision_boundaries) != len(self.program.actions):
            raise ScenarioValidationError("every program action requires runtime boundary evidence")


class _DequeToolScript:
    def __init__(self, results: tuple[ScriptedToolResult, ...]) -> None:
        self._results = deque(results)

    def __call__(self, _action: DelegateAction) -> ScriptedToolResult:
        if not self._results:
            raise ScenarioExecutionError("delegate has no remaining scripted tool result")
        return self._results.popleft()

    def assert_drained(self) -> None:
        if self._results:
            raise ScenarioExecutionError("scenario left scripted tool results unconsumed")


async def execute_scenario(
    program: ScenarioProgram,
    *,
    session_id: str,
    directory: Path,
    repository_root: Path | None = None,
) -> GeneratedScenario:
    """Execute concrete C5 inputs solely through RuntimeIngestionRunner."""
    if not isinstance(program, ScenarioProgram):
        raise TypeError("program must be a ScenarioProgram")
    tool_script = _DequeToolScript(program.tool_results)
    boundaries: list[DecisionBoundary] = []
    runner = RuntimeIngestionRunner(
        session_id=session_id,
        directory=directory,
        timing_plan=program.timing_plan,
        scripted_attempts=program.actions,
        template_id=program.template.asset_id,
        asset_ids=program.asset_ids,
        master_seed=program.master_seed,
        config=program.config,
        repository_root=repository_root,
        tool_script=tool_script,
        decision_boundary_observer=boundaries.append,
        generation_input_hash=program.input_hash,
    )
    stream = await runner.run(program.frames, program.annotations)
    tool_script.assert_drained()
    validate_generated_stream(stream)
    if len(boundaries) != len(program.actions):
        raise ScenarioExecutionError("runtime did not capture every decision boundary")
    sidecar = _build_sidecar(program, stream, tuple(boundaries))
    generated = GeneratedScenario(
        program=program,
        stream=stream,
        sidecar=sidecar,
        decision_boundaries=tuple(boundaries),
    )
    validate_generated_scenario(generated)
    return generated


def validate_generated_scenario(generated: GeneratedScenario) -> OracleSidecar:
    """Validate sidecar binding and its exact captured runtime facts."""
    if not isinstance(generated, GeneratedScenario):
        raise TypeError("generated must be a GeneratedScenario")
    validate_generated_stream(generated.stream)
    sidecar = generated.sidecar
    if sidecar.canonical_bytes != canonicalize_tim_json(sidecar.as_json_object()):
        raise ScenarioValidationError("sidecar bytes are not canonical")
    if sidecar.sha256 != _digest(sidecar.canonical_bytes):
        raise ScenarioValidationError("sidecar hash does not bind canonical bytes")
    _validate_sidecar_binding(sidecar, generated.program, generated.stream)
    evidence = _resolve_beat_evidence(
        generated.program, generated.stream, generated.decision_boundaries
    )
    for boundary, decision, captured, action, evidence in zip(
        generated.decision_boundaries,
        sidecar.decisions,
        generated.stream.decisions,
        generated.program.actions,
        evidence,
        strict=True,
    ):
        _validate_decision_against_boundary(boundary, decision, captured, action, evidence)
    return sidecar


def _build_sidecar(
    program: ScenarioProgram,
    stream: GeneratedStream,
    boundaries: tuple[DecisionBoundary, ...],
) -> OracleSidecar:
    evidence = _resolve_beat_evidence(program, stream, boundaries)
    decisions = tuple(
        _decision_from_boundary(boundary, captured, action, beat)
        for boundary, captured, action, beat in zip(
            boundaries, stream.decisions, program.actions, evidence, strict=True
        )
    )
    return OracleSidecar(
        stream_sha256=stream.sha256,
        capture_sha256=stream.capture_sha256,
        regeneration_identity=stream.provenance.identity,
        split=program.bundle.split,
        family=program.family,
        template_id=program.template.asset_id,
        template_content_sha256=program.template.content_sha256,
        asset_ids=program.asset_ids,
        asset_content_sha256s=tuple(asset.content_sha256 for asset in program.bundle.assets),
        scenario_input_sha256=program.input_hash,
        world_script_sha256=program.world_script_hash,
        perturbations=program.perturbations,
        counterfactual=program.counterfactual,
        decisions=decisions,
    )


def _resolve_beat_evidence(
    program: ScenarioProgram,
    stream: GeneratedStream,
    boundaries: tuple[DecisionBoundary, ...],
) -> tuple[BeatEvidence, ...]:
    stale_by_beat = {
        item.beat_id: item.tool_result_event_ids for item in program.stale_results_by_beat
    }
    warrants_by_beat = {item.beat_id: item for item in program.response_warrants_by_beat}
    openings_by_beat = {item.beat_id: item for item in program.openings_by_beat or ()}
    lineage_by_beat = {item.beat_id: item.needs for item in program.need_lineage_by_beat or ()}
    cancellations_by_beat = {
        item.beat_id: item for item in program.cancel_resolution_evidence_by_beat
    }
    policy_segments = tuple(segment.policy_bytes for segment in stream.segments)
    delegates = program.delegate_provenance_by_beat or ()
    floor_evidence_required = program.openings_by_beat is not None
    return tuple(
        _evidence_from_boundary(
            boundary,
            captured,
            action,
            beat_id,
            stale_by_beat[beat_id],
            warrants_by_beat.get(beat_id),
            openings_by_beat.get(beat_id),
            lineage_by_beat.get(beat_id, ()),
            delegates,
            cancellations_by_beat.get(beat_id),
            policy_segments,
            floor_evidence_required,
            program.require_g7_evidence,
            program.actions[index + 1 :],
        )
        for index, (boundary, captured, action, beat_id) in enumerate(
            zip(boundaries, stream.decisions, program.actions, program.beat_ids, strict=True)
        )
    )


def _evidence_from_boundary(
    boundary: DecisionBoundary,
    captured: CapturedDecision,
    action: Action,
    beat_id: str,
    stale_tool_result_event_ids: tuple[str, ...],
    response_warrant: BeatResponseWarrant | None,
    opening: BeatOpening | None,
    need_lineage: tuple[NeedLineage, ...],
    delegate_provenance_by_beat: tuple[DelegateProvenance, ...],
    cancellation: CancelResolutionEvidence | None,
    policy_segments: tuple[bytes, ...],
    require_floor_opening_evidence: bool,
    require_g7_evidence: bool,
    future_actions: tuple[Action, ...],
) -> BeatEvidence:
    if boundary.call_index != captured.call_index or boundary.policy_bytes != captured.prefix_bytes:
        raise ScenarioExecutionError("captured runtime boundary differs from durable decision")
    observed_policy_seq = _observed_policy_seq(captured.audit_bytes)
    if captured.attempt_bytes != _action_bytes(action):
        raise ScenarioExecutionError("durable action attempt differs from scenario action")
    if not isinstance(check(action, boundary.license_view), Allowed):
        raise ScenarioExecutionError("scenario action is not allowed at its captured boundary")
    view = boundary.license_view
    warrant_snapshot = (
        view.event(response_warrant.snapshot_event_id)
        if isinstance(action, RespondAction | IdleAction) and response_warrant is not None
        else None
    )
    opening_snapshot = view.event(opening.snapshot_event_id) if opening is not None else None
    skip_evidence = next(
        (
            build_skip_evidence(
                boundary, candidate.target_event_id, need, delegate_provenance_by_beat
            )
            for candidate, need in declared_need_skips(
                boundary, need_lineage, delegate_provenance_by_beat
            )
            if candidate == action
        ),
        None,
    )
    stale_snapshot = (
        view.latest_snapshot
        if skip_evidence is None
        and isinstance(action, SkipAction)
        and action.reason is SkipReason.STALE_TOOL_RESULT
        else None
    )
    if (
        skip_evidence is None
        and isinstance(action, SkipAction)
        and action.reason is SkipReason.STALE_TOOL_RESULT
        and stale_snapshot is None
    ):
        raise ScenarioValidationError("stale skip lacks latest snapshot evidence")
    cancellation = derive_cancel_resolution_evidence(
        action, boundary, cancellation, policy_segments, observed_policy_seq
    )
    oracle_floor_open = _floor_open(boundary, action, opening, require_floor_opening_evidence)
    return BeatEvidence(
        beat_id=beat_id,
        stale_tool_result_event_ids=stale_tool_result_event_ids,
        floor_open=oracle_floor_open if require_floor_opening_evidence else None,
        floor_opening_snapshot_event_id=(
            opening_snapshot.event_id if isinstance(opening_snapshot, SnapshotView) else None
        ),
        floor_opening_snapshot_text=(
            opening_snapshot.text if isinstance(opening_snapshot, SnapshotView) else None
        ),
        stale_snapshot_event_id=None if stale_snapshot is None else stale_snapshot.event_id,
        stale_snapshot_text=None if stale_snapshot is None else stale_snapshot.text,
        response_warrant_kind=(
            response_warrant.kind if isinstance(warrant_snapshot, SnapshotView) else None
        ),
        response_warrant_snapshot_event_id=(
            warrant_snapshot.event_id if isinstance(warrant_snapshot, SnapshotView) else None
        ),
        response_warrant_snapshot_text=(
            warrant_snapshot.text if isinstance(warrant_snapshot, SnapshotView) else None
        ),
        response_warrant_failed_result_event_id=(
            response_warrant.failed_result_event_id if response_warrant is not None else None
        ),
        need_lineage=need_lineage,
        delegate_provenance_by_beat=delegate_provenance_by_beat,
        skip_evidence=skip_evidence,
        cancel_resolution_evidence=cancellation,
        future_actions=future_actions,
        oracle_floor_open=oracle_floor_open,
        require_floor_opening_evidence=require_floor_opening_evidence,
        require_g7_evidence=require_g7_evidence,
    )


def _decision_from_boundary(
    boundary: DecisionBoundary,
    captured: CapturedDecision,
    action: Action,
    evidence: BeatEvidence,
) -> OracleDecision:
    if boundary.call_index != captured.call_index or boundary.policy_bytes != captured.prefix_bytes:
        raise ScenarioValidationError("captured runtime boundary differs from durable decision")
    if captured.attempt_bytes != _action_bytes(action):
        raise ScenarioValidationError("durable action attempt differs from scenario action")
    view = boundary.license_view
    return OracleDecision(
        call_index=boundary.call_index,
        observed_policy_seq=_observed_policy_seq(captured.audit_bytes),
        action=action,
        open_timer_fire_event_ids=tuple(
            event.event_id
            for event in view.events
            if isinstance(event, TimerFireView) and event.disposition is Disposition.OPEN
        ),
        open_tool_result_event_ids=tuple(
            event.event_id
            for event in view.events
            if isinstance(event, ToolResultView) and event.disposition is Disposition.OPEN
        ),
        pending_request_ids=tuple(item.request_id for item in view.pending_tool_requests),
        active_timer_ids=tuple(
            timer.timer_id for timer in view.timers if timer.status is TimerStatus.ACTIVE
        ),
        canceled_timer_ids=tuple(
            timer.timer_id for timer in view.timers if timer.status is TimerStatus.CANCELED
        ),
        floor_owned=view.floor_owned,
        evidence=evidence,
    )


def _validate_sidecar_binding(
    sidecar: OracleSidecar,
    program: ScenarioProgram,
    stream: GeneratedStream,
) -> None:
    provenance = stream.provenance
    if (
        sidecar.stream_sha256 != stream.sha256
        or sidecar.capture_sha256 != stream.capture_sha256
        or sidecar.regeneration_identity != provenance.identity
        or sidecar.split.value != provenance.timing_split
        or sidecar.template_id != provenance.template_id
        or sidecar.asset_ids != provenance.asset_ids
        or sidecar.split is not program.bundle.split
        or sidecar.family is not program.family
        or sidecar.template_id != program.template.asset_id
        or sidecar.template_content_sha256 != program.template.content_sha256
        or sidecar.asset_ids != program.asset_ids
        or sidecar.asset_content_sha256s
        != tuple(asset.content_sha256 for asset in program.bundle.assets)
        or sidecar.scenario_input_sha256 != program.input_hash
        or sidecar.world_script_sha256 != program.world_script_hash
        or sidecar.perturbations != program.perturbations
        or sidecar.counterfactual != program.counterfactual
        or provenance.generation_input_hash != program.input_hash
        or stream.timing_plan != program.timing_plan
        or stream.frames != program.frames
        or stream.annotations != program.annotations
        or stream.config != program.config
    ):
        raise ScenarioValidationError("sidecar does not bind this program and generated stream")
    if len(sidecar.decisions) != len(stream.decisions):
        raise ScenarioValidationError("sidecar does not cover every generated decision")
    for sidecar_decision, captured in zip(sidecar.decisions, stream.decisions, strict=True):
        if (
            sidecar_decision.call_index != captured.call_index
            or sidecar_decision.observed_policy_seq != _observed_policy_seq(captured.audit_bytes)
            or captured.attempt_bytes != _action_bytes(sidecar_decision.action)
        ):
            raise ScenarioValidationError("sidecar decision differs from durable action audit")


def _validate_decision_against_boundary(
    boundary: DecisionBoundary,
    decision: OracleDecision,
    captured: CapturedDecision,
    action: Action,
    evidence: BeatEvidence,
) -> None:
    expected = _decision_from_boundary(boundary, captured, action, evidence)
    if decision != expected:
        raise ScenarioValidationError("sidecar facts differ from the captured license view")
    if not isinstance(check(decision.action, boundary.license_view), Allowed):
        raise ScenarioValidationError("sidecar action is not allowed at its captured boundary")
    validate_oracle_action(boundary, decision.action, evidence)


def _floor_open(
    boundary: DecisionBoundary,
    action: Action,
    opening: BeatOpening | None,
    floor_state_declared: bool,
) -> bool | None:
    if floor_state_declared:
        return opening is not None
    if isinstance(action, IntegrateAction | RespondAction):
        return True
    if any(
        isinstance(event, ToolResultView) and event.disposition is Disposition.OPEN
        for event in boundary.license_view.events
    ):
        return False
    return None


def _observed_policy_seq(audit_bytes: bytes) -> int:
    try:
        audit = parse_tim_json(audit_bytes)
    except (TypeError, ValueError) as error:
        raise ScenarioValidationError("durable action audit is invalid") from error
    if not isinstance(audit, dict):
        raise ScenarioValidationError("durable action audit must be an object")
    observed = audit.get("observed_through_policy_seq")
    if isinstance(observed, bool) or not isinstance(observed, int) or observed < 0:
        raise ScenarioValidationError("durable action audit lacks an observed policy sequence")
    return observed


def _action_bytes(action: Action) -> bytes:
    return _attempt_bytes(action)


def _require_tuple(values: object, expected: type | tuple[type, ...], name: str) -> None:
    if not isinstance(values, tuple) or not all(isinstance(value, expected) for value in values):
        expected_name = getattr(expected, "__name__", "allowed values")
        raise TypeError(f"{name} must be an immutable tuple of {expected_name}")


def _require_id(value: object, pattern: str, name: str) -> None:
    if not isinstance(value, str) or fullmatch(pattern, value) is None:
        raise ScenarioValidationError(f"{name} has an invalid structure")


def _require_sorted_unique_ids(values: object, pattern: str, name: str) -> None:
    if not isinstance(values, tuple):
        raise TypeError(f"{name} must be an immutable tuple")
    if values != tuple(sorted(set(values))):
        raise ScenarioValidationError(f"{name} must be sorted and unique")
    for value in values:
        _require_id(value, pattern, name)
