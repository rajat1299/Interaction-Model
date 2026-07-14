"""Strict C5 scenario inputs and oracle sidecars over the production runtime."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from enum import StrEnum
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
from im.generation.runtime import DecisionBoundary
from im.generation.timing import TimingPlan
from im.generation.validity import validate_generated_stream
from im.license import Allowed, TimerFireView, ToolResultView, check
from im.schema.actions import (
    Action,
    CancelAction,
    DelegateAction,
    IdleAction,
    IntegrateAction,
    MarkAction,
    NudgeAction,
    RespondAction,
    ScheduleAction,
    SkipAction,
)
from im.schema.common import Disposition, TimerStatus
from im.tools import ScriptedToolResult

_ACTION_TYPES = (
    IdleAction,
    MarkAction,
    DelegateAction,
    IntegrateAction,
    SkipAction,
    RespondAction,
    ScheduleAction,
    CancelAction,
    NudgeAction,
)
_BEAT_ID = r"[a-z][a-z0-9_-]{0,63}"
_GROUP_ID = r"[a-z][a-z0-9_-]{2,127}"
_EVENT_ID = r"e_[0-9]{6}"


class ScenarioValidationError(ValueError):
    """A frozen scenario or its sidecar violates C5's closed contract."""


class ScenarioExecutionError(RuntimeError):
    """A runtime execution diverged from its finite scenario program."""


class PerturbationKind(StrEnum):
    DRAFT_REVISION = "draft_revision"
    MARK_TARGETING = "mark_targeting"
    MARK_RESTRAINT = "mark_restraint"
    TOOL_RESULT = "tool_result"
    PENDING_TOOL_PRESSURE = "pending_tool_pressure"
    TOPIC_CHANGE = "topic_change"
    TIMER_FIRE = "timer_fire"
    TIMER_CANCEL_RACE = "timer_cancel_race"
    EXTERNAL_EVENT_CONTENTION = "external_event_contention"
    STATE_CHECKPOINT = "state_checkpoint"
    ANNOTATION_SAFETY = "annotation_safety"


class CounterfactualKind(StrEnum):
    TWIN = "twin"
    TRIPLET = "triplet"


@dataclass(frozen=True, slots=True)
class DeclaredPerturbation:
    """One closed D3 perturbation declaration."""

    kind: PerturbationKind | str

    def __post_init__(self) -> None:
        try:
            kind = PerturbationKind(self.kind)
        except (TypeError, ValueError) as error:
            raise ScenarioValidationError("perturbation kind is not closed") from error
        object.__setattr__(self, "kind", kind)

    def as_json_object(self) -> dict[str, object]:
        return {"kind": self.kind.value}


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


@dataclass(frozen=True, slots=True)
class CounterfactualDeclaration:
    """A closed sibling declaration; cross-stream linkage is finalized later."""

    kind: CounterfactualKind | str
    group_id: str
    member_id: str
    member_ids: tuple[str, ...]
    flipped_perturbation: PerturbationKind | str

    def __post_init__(self) -> None:
        try:
            kind = CounterfactualKind(self.kind)
            flipped = PerturbationKind(self.flipped_perturbation)
        except (TypeError, ValueError) as error:
            raise ScenarioValidationError("counterfactual declaration is not closed") from error
        _require_id(self.group_id, _GROUP_ID, "group_id")
        _require_id(self.member_id, _BEAT_ID, "member_id")
        if not isinstance(self.member_ids, tuple):
            raise TypeError("member_ids must be an immutable tuple")
        if len(self.member_ids) != (2 if kind is CounterfactualKind.TWIN else 3):
            raise ScenarioValidationError("counterfactual member count does not match kind")
        if self.member_ids != tuple(sorted(set(self.member_ids))):
            raise ScenarioValidationError("counterfactual member_ids must be sorted and unique")
        for member in self.member_ids:
            _require_id(member, _BEAT_ID, "member_id")
        if self.member_id not in self.member_ids:
            raise ScenarioValidationError("counterfactual member_id is not declared")
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "flipped_perturbation", flipped)

    def as_json_object(self) -> dict[str, object]:
        return {
            "kind": self.kind.value,
            "group_id": self.group_id,
            "member_id": self.member_id,
            "member_ids": list(self.member_ids),
            "flipped_perturbation": self.flipped_perturbation.value,
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
        _require_tuple(self.actions, _ACTION_TYPES, "actions")
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
        _require_tuple(self.perturbations, DeclaredPerturbation, "perturbations")
        kinds = tuple(item.kind for item in self.perturbations)
        if kinds != tuple(sorted(set(kinds), key=str)):
            raise ScenarioValidationError("perturbations must be uniquely sorted by kind")
        if not isinstance(self.config, RuntimeConfig):
            raise TypeError("config must be a RuntimeConfig")
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
        metadata = canonicalize_tim_json(
            {
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
                "stale_results_by_beat": [
                    item.as_json_object() for item in self.stale_results_by_beat
                ],
                "perturbations": [item.as_json_object() for item in self.perturbations],
                "config": self.config.as_json_object(),
                "counterfactual": (
                    None if self.counterfactual is None else self.counterfactual.as_json_object()
                ),
            }
        )
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
class OracleDecision:
    """One exact oracle action and its captured objective pre-action facts."""

    call_index: int
    observed_policy_seq: int
    action: Action
    beat_id: str
    open_timer_fire_event_ids: tuple[str, ...]
    open_tool_result_event_ids: tuple[str, ...]
    stale_tool_result_event_ids: tuple[str, ...]
    pending_request_ids: tuple[str, ...]
    active_timer_ids: tuple[str, ...]
    canceled_timer_ids: tuple[str, ...]
    floor_owned: bool

    def __post_init__(self) -> None:
        if isinstance(self.call_index, bool) or not isinstance(self.call_index, int):
            raise TypeError("call_index must be an integer")
        if self.call_index < 1:
            raise ScenarioValidationError("call_index must be positive")
        if isinstance(self.observed_policy_seq, bool) or not isinstance(
            self.observed_policy_seq, int
        ):
            raise TypeError("observed_policy_seq must be an integer")
        if self.observed_policy_seq < 0:
            raise ScenarioValidationError("observed_policy_seq must be non-negative")
        if not isinstance(self.action, _ACTION_TYPES):
            raise TypeError("action must be a concrete Action")
        _require_id(self.beat_id, _BEAT_ID, "beat_id")
        _require_sorted_unique_ids(self.open_timer_fire_event_ids, _EVENT_ID, "timer event ids")
        _require_sorted_unique_ids(self.open_tool_result_event_ids, _EVENT_ID, "tool event ids")
        _require_sorted_unique_ids(
            self.stale_tool_result_event_ids, _EVENT_ID, "stale tool event ids"
        )
        _require_sorted_unique_ids(self.pending_request_ids, r"r_[0-9]{3}", "request ids")
        _require_sorted_unique_ids(self.active_timer_ids, r"t_[0-9]{3}", "active timer ids")
        _require_sorted_unique_ids(self.canceled_timer_ids, r"t_[0-9]{3}", "canceled timer ids")
        if not isinstance(self.floor_owned, bool):
            raise TypeError("floor_owned must be a bool")
        if not set(self.stale_tool_result_event_ids).issubset(self.open_tool_result_event_ids):
            raise ScenarioValidationError("stale results must be a subset of open tool results")

    def as_json_object(self) -> dict[str, object]:
        return {
            "call_index": self.call_index,
            "observed_policy_seq": self.observed_policy_seq,
            "action": self.action.model_dump(mode="json"),
            "beat_id": self.beat_id,
            "open_timer_fire_event_ids": list(self.open_timer_fire_event_ids),
            "open_tool_result_event_ids": list(self.open_tool_result_event_ids),
            "stale_tool_result_event_ids": list(self.stale_tool_result_event_ids),
            "pending_request_ids": list(self.pending_request_ids),
            "active_timer_ids": list(self.active_timer_ids),
            "canceled_timer_ids": list(self.canceled_timer_ids),
            "floor_owned": self.floor_owned,
        }


@dataclass(frozen=True, slots=True)
class OracleSidecar:
    """Non-teacher-visible provenance and state facts for one generated stream."""

    stream_sha256: str
    capture_sha256: str
    regeneration_identity: str
    split: Split | str
    family: CorpusFamily | str
    template_id: str
    template_content_sha256: str
    asset_ids: tuple[str, ...]
    asset_content_sha256s: tuple[str, ...]
    scenario_input_sha256: str
    world_script_sha256: str
    perturbations: tuple[DeclaredPerturbation, ...]
    counterfactual: CounterfactualDeclaration | None
    decisions: tuple[OracleDecision, ...]
    canonical_bytes: bytes = field(init=False)
    sha256: str = field(init=False)

    def __post_init__(self) -> None:
        for name in (
            "stream_sha256",
            "capture_sha256",
            "regeneration_identity",
            "template_content_sha256",
            "scenario_input_sha256",
            "world_script_sha256",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or fullmatch(r"sha256:[0-9a-f]{64}", value) is None:
                raise ScenarioValidationError(f"{name} must be a sha256 digest")
        try:
            split = Split(self.split)
            family = CorpusFamily(self.family)
        except (TypeError, ValueError) as error:
            raise ScenarioValidationError("sidecar split or family is invalid") from error
        _require_id(self.template_id, r"[a-z][a-z0-9_-]{2,127}", "template_id")
        if not isinstance(self.asset_ids, tuple) or self.asset_ids != tuple(
            sorted(set(self.asset_ids))
        ):
            raise ScenarioValidationError("asset_ids must be sorted and unique")
        if not isinstance(self.asset_content_sha256s, tuple):
            raise TypeError("asset_content_sha256s must be an immutable tuple")
        if not self.asset_ids or len(self.asset_ids) != len(self.asset_content_sha256s):
            raise ScenarioValidationError("asset identities and content hashes must align")
        for asset_id, digest in zip(self.asset_ids, self.asset_content_sha256s, strict=True):
            _require_id(asset_id, r"a_[a-z0-9][a-z0-9_-]{2,63}", "asset_id")
            if not isinstance(digest, str) or fullmatch(r"sha256:[0-9a-f]{64}", digest) is None:
                raise ScenarioValidationError("asset content hash must be a sha256 digest")
        _require_tuple(self.perturbations, DeclaredPerturbation, "perturbations")
        kinds = tuple(item.kind for item in self.perturbations)
        if kinds != tuple(sorted(set(kinds), key=str)):
            raise ScenarioValidationError("sidecar perturbations must be uniquely sorted")
        if self.counterfactual is not None and not isinstance(
            self.counterfactual, CounterfactualDeclaration
        ):
            raise TypeError("counterfactual must be a CounterfactualDeclaration or None")
        _require_tuple(self.decisions, OracleDecision, "decisions")
        if tuple(item.call_index for item in self.decisions) != tuple(
            range(1, len(self.decisions) + 1)
        ):
            raise ScenarioValidationError("sidecar decisions must be in call order")
        object.__setattr__(self, "split", split)
        object.__setattr__(self, "family", family)
        canonical = canonicalize_tim_json(self.as_json_object())
        object.__setattr__(self, "canonical_bytes", canonical)
        object.__setattr__(self, "sha256", _digest(canonical))

    def as_json_object(self) -> dict[str, object]:
        return {
            "format_version": 1,
            "stream_sha256": self.stream_sha256,
            "capture_sha256": self.capture_sha256,
            "regeneration_identity": self.regeneration_identity,
            "split": self.split.value,
            "family": self.family.value,
            "template": {
                "asset_id": self.template_id,
                "content_sha256": self.template_content_sha256,
            },
            "assets": [
                {"asset_id": asset_id, "content_sha256": digest}
                for asset_id, digest in zip(self.asset_ids, self.asset_content_sha256s, strict=True)
            ],
            "scenario_input_sha256": self.scenario_input_sha256,
            "world_script_sha256": self.world_script_sha256,
            "perturbations": [item.as_json_object() for item in self.perturbations],
            "counterfactual": (
                None if self.counterfactual is None else self.counterfactual.as_json_object()
            ),
            "decisions": [item.as_json_object() for item in self.decisions],
        }


@dataclass(frozen=True, slots=True)
class GeneratedScenario:
    """A teacher stream with a separate sidecar and runtime-only validation evidence."""

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
    """Validate sidecar binding and, when retained, exact runtime boundary facts."""
    if not isinstance(generated, GeneratedScenario):
        raise TypeError("generated must be a GeneratedScenario")
    validate_generated_stream(generated.stream)
    sidecar = generated.sidecar
    if sidecar.canonical_bytes != canonicalize_tim_json(sidecar.as_json_object()):
        raise ScenarioValidationError("sidecar bytes are not canonical")
    if sidecar.sha256 != _digest(sidecar.canonical_bytes):
        raise ScenarioValidationError("sidecar hash does not bind canonical bytes")
    _validate_sidecar_binding(sidecar, generated.program, generated.stream)
    stale_by_beat = {
        item.beat_id: item.tool_result_event_ids for item in generated.program.stale_results_by_beat
    }
    for boundary, decision, captured, action, beat_id in zip(
        generated.decision_boundaries,
        sidecar.decisions,
        generated.stream.decisions,
        generated.program.actions,
        generated.program.beat_ids,
        strict=True,
    ):
        _validate_decision_against_boundary(
            boundary,
            decision,
            captured,
            action=action,
            beat_id=beat_id,
            stale_tool_result_event_ids=stale_by_beat[beat_id],
        )
    return sidecar


def _build_sidecar(
    program: ScenarioProgram,
    stream: GeneratedStream,
    boundaries: tuple[DecisionBoundary, ...],
) -> OracleSidecar:
    stale_by_beat = {
        item.beat_id: item.tool_result_event_ids for item in program.stale_results_by_beat
    }
    decisions = tuple(
        _decision_from_boundary(
            boundary=boundary,
            captured=stream.decisions[index],
            action=program.actions[index],
            beat_id=program.beat_ids[index],
            stale_tool_result_event_ids=stale_by_beat[program.beat_ids[index]],
        )
        for index, boundary in enumerate(boundaries)
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


def _decision_from_boundary(
    *,
    boundary: DecisionBoundary,
    captured: CapturedDecision,
    action: Action,
    beat_id: str,
    stale_tool_result_event_ids: tuple[str, ...],
) -> OracleDecision:
    if boundary.call_index != captured.call_index or boundary.policy_bytes != captured.prefix_bytes:
        raise ScenarioExecutionError("captured runtime boundary differs from durable decision")
    observed_policy_seq = _observed_policy_seq(captured.audit_bytes)
    if captured.attempt_bytes != _action_bytes(action):
        raise ScenarioExecutionError("durable action attempt differs from scenario action")
    if not isinstance(check(action, boundary.license_view), Allowed):
        raise ScenarioExecutionError("scenario action is not allowed at its captured boundary")
    decision = _decision_from_view(
        boundary=boundary,
        action=action,
        beat_id=beat_id,
        stale_tool_result_event_ids=stale_tool_result_event_ids,
        observed_policy_seq=observed_policy_seq,
    )
    _validate_decision_against_boundary(
        boundary,
        decision,
        captured,
        action=action,
        beat_id=beat_id,
        stale_tool_result_event_ids=stale_tool_result_event_ids,
    )
    return decision


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
    *,
    action: Action,
    beat_id: str,
    stale_tool_result_event_ids: tuple[str, ...],
) -> None:
    expected = _decision_from_view(
        boundary=boundary,
        action=action,
        beat_id=beat_id,
        stale_tool_result_event_ids=stale_tool_result_event_ids,
        observed_policy_seq=_observed_policy_seq(captured.audit_bytes),
    )
    if (
        boundary.call_index != captured.call_index
        or boundary.policy_bytes != captured.prefix_bytes
        or decision != expected
    ):
        raise ScenarioValidationError("sidecar facts differ from the captured license view")
    if not isinstance(check(decision.action, boundary.license_view), Allowed):
        raise ScenarioValidationError("sidecar action is not allowed at its captured boundary")


def _decision_from_view(
    *,
    boundary: DecisionBoundary,
    action: Action,
    beat_id: str,
    stale_tool_result_event_ids: tuple[str, ...],
    observed_policy_seq: int,
) -> OracleDecision:
    view = boundary.license_view
    return OracleDecision(
        call_index=boundary.call_index,
        observed_policy_seq=observed_policy_seq,
        action=action,
        beat_id=beat_id,
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
        stale_tool_result_event_ids=stale_tool_result_event_ids,
        pending_request_ids=tuple(item.request_id for item in view.pending_tool_requests),
        active_timer_ids=tuple(
            timer.timer_id for timer in view.timers if timer.status is TimerStatus.ACTIVE
        ),
        canceled_timer_ids=tuple(
            timer.timer_id for timer in view.timers if timer.status is TimerStatus.CANCELED
        ),
        floor_owned=view.floor_owned,
    )


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
