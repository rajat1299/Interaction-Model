"""Generated-response floor twins for the five G7 response families."""

from __future__ import annotations

from dataclasses import dataclass

from im.assets.model import AssetRecord, CorpusFamily, Split, artifact_digest
from im.assets.registry import AssetBundle, AssetRegistry
from im.canonical_json import canonicalize_tim_json, parse_tim_json
from im.generation.g7_catalog import G7FamilyInputs
from im.generation.g7_response_assets import (
    GeneratedResponseAsset,
    ResponseDraftSpec,
    SimpleResponseProfile,
)
from im.generation.ingestion import ScheduledSamplerFrame
from im.generation.oracle import BeatOpening, BeatResponseWarrant, ResponseWarrantKind
from im.generation.scenarios import (
    BeatStaleResults,
    CounterfactualDeclaration,
    DeclaredPerturbation,
    ScenarioProgram,
    select_approved_scenario_inputs,
)
from im.generation.timing import TimingPlan, TimingSeed, materialize_timing_plan
from im.schema.actions import IdleAction, IdleReason, RespondAction
from im.schema.textspan import utf16_len

__all__ = (
    "G7_RESPONSE_FAMILIES",
    "ResponseFloorTwinPrograms",
    "build_g7_response_floor_twin_program",
    "build_g7_response_floor_twin_programs",
    "build_provisional_g7_response_floor_program",
    "validate_response_floor_twin_alignment",
)

_RESPONSE_COUNT = 10
G7_RESPONSE_FAMILIES = (
    CorpusFamily.NEUTRAL_TYPING,
    CorpusFamily.MARK_POSITIVE,
    CorpusFamily.MARK_NEGATIVE,
    CorpusFamily.LOOKUP_LIVE,
    CorpusFamily.LOOKUP_STALE,
)


@dataclass(frozen=True, slots=True)
class ResponseFloorTwinPrograms:
    """One independent yielded/active response-floor pair."""

    family: CorpusFamily
    group_id: str
    asset: GeneratedResponseAsset
    programs: tuple[ScenarioProgram, ScenarioProgram]

    def __post_init__(self) -> None:
        if self.family not in G7_RESPONSE_FAMILIES:
            raise ValueError("response-floor twins require a supported G7 response family")
        if not isinstance(self.asset, GeneratedResponseAsset):
            raise TypeError("asset must be a GeneratedResponseAsset")
        if not isinstance(self.programs, tuple) or len(self.programs) != 2:
            raise TypeError("programs must be the yielded and active ScenarioPrograms")
        yielded, active = self.programs
        if not isinstance(yielded, ScenarioProgram) or not isinstance(active, ScenarioProgram):
            raise TypeError("programs must contain ScenarioProgram values")
        if yielded.family is not self.family or active.family is not self.family:
            raise ValueError("response-floor twins must retain their requested family")
        validate_response_floor_twin_alignment(yielded, active)
        yielded_frame = parse_tim_json(yielded.frames[0].raw_bytes)
        yielded_action = yielded.actions[0]
        if (
            not isinstance(yielded_frame, dict)
            or yielded_frame.get("text") != self.asset.draft.invitation
            or self.asset.draft.answer_contract.support_event_ids != (_snapshot_id(),)
            or not isinstance(yielded_action, RespondAction)
            or yielded_action.text != self.asset.candidate_response
        ):
            raise ValueError("response-floor twin actions must match the external response assets")
        _validate_links(self.group_id, yielded, active)


def validate_response_floor_twin_alignment(
    yielded: ScenarioProgram, active: ScenarioProgram
) -> None:
    """Require one isolated pair whose only policy-visible difference is floor state."""
    if not isinstance(yielded, ScenarioProgram) or not isinstance(active, ScenarioProgram):
        raise TypeError("response-floor alignment requires ScenarioProgram values")
    if any(
        getattr(yielded, field) != getattr(active, field)
        for field in (
            "bundle",
            "template",
            "family",
            "master_seed",
            "timing_plan",
            "tool_results",
            "beat_ids",
            "stale_results_by_beat",
            "perturbations",
            "annotations",
            "config",
            "need_lineage_by_beat",
            "delegate_provenance_by_beat",
            "cancel_resolution_evidence_by_beat",
            "require_g7_evidence",
        )
    ):
        raise ValueError("response-floor twins must retain the same frozen prefix inputs")
    if (
        len(yielded.frames) != 1
        or len(active.frames) != 1
        or len(yielded.actions) != 1
        or len(active.actions) != 1
        or yielded.annotations
        or yielded.tool_results
    ):
        raise ValueError("response-floor twins must terminate immediately after their branch")

    yielded_frame = parse_tim_json(yielded.frames[0].raw_bytes)
    active_frame = parse_tim_json(active.frames[0].raw_bytes)
    if (
        not isinstance(yielded_frame, dict)
        or not isinstance(active_frame, dict)
        or yielded.frames[0].at_ms != active.frames[0].at_ms
        or yielded_frame.get("activity") != "paused"
        or active_frame.get("activity") != "active"
        or {key: value for key, value in yielded_frame.items() if key != "activity"}
        != {key: value for key, value in active_frame.items() if key != "activity"}
    ):
        raise ValueError("response-floor twins may differ only in sampler activity")

    snapshot_id = _snapshot_id()
    if (
        not isinstance(yielded.actions[0], RespondAction)
        or yielded.actions[0].reply_to_event_id != snapshot_id
        or not isinstance(active.actions[0], IdleAction)
        or active.actions[0].reason is not IdleReason.AWAITING_OPENING
        or active.actions[0].related_event_id != snapshot_id
        or yielded.response_warrants_by_beat
        != (BeatResponseWarrant("b0", snapshot_id, ResponseWarrantKind.INVITATION),)
        or active.response_warrants_by_beat != yielded.response_warrants_by_beat
        or yielded.openings_by_beat != (BeatOpening("b0", snapshot_id),)
        or active.openings_by_beat != ()
    ):
        raise ValueError("response-floor twins must branch on the same invitation")

    yielded_link = yielded.counterfactual
    active_link = active.counterfactual
    if (
        yielded_link is None
        or active_link is None
        or yielded_link.kind.value != "twin"
        or active_link.kind != yielded_link.kind
        or active_link.group_id != yielded_link.group_id
        or active_link.member_ids != yielded_link.member_ids
        or yielded_link.member_ids != ("active", "yielded")
        or active_link.flipped_perturbation != yielded_link.flipped_perturbation
        or yielded_link.flipped_perturbation.value != "floor_opening"
        or (yielded_link.member_id, active_link.member_id) != ("yielded", "active")
    ):
        raise ValueError("response-floor twin linkage is incomplete")


def build_g7_response_floor_twin_programs(
    registry: AssetRegistry,
    *,
    split: Split | str,
    family: CorpusFamily | str,
    inputs: G7FamilyInputs,
    profile: SimpleResponseProfile,
    master_seed: str,
) -> tuple[ResponseFloorTwinPrograms, ...]:
    """Build ten independent response-floor pairs from one generated profile."""
    family = _response_family(family)
    return tuple(
        build_g7_response_floor_twin_program(
            registry,
            split=split,
            family=family,
            inputs=inputs,
            profile=profile,
            master_seed=master_seed,
            item_index=item_index,
        )
        for item_index in range(_RESPONSE_COUNT)
    )


def build_g7_response_floor_twin_program(
    registry: AssetRegistry,
    *,
    split: Split | str,
    family: CorpusFamily | str,
    inputs: G7FamilyInputs,
    profile: SimpleResponseProfile,
    master_seed: str,
    item_index: int,
) -> ResponseFloorTwinPrograms:
    """Build one independent already-generated response-floor pair."""
    family = _response_family(family)
    return _build_twin(
        registry,
        split=split,
        family=family,
        inputs=inputs,
        profile=profile,
        master_seed=master_seed,
        item_index=item_index,
    )


def build_provisional_g7_response_floor_program(
    registry: AssetRegistry,
    *,
    split: Split | str,
    family: CorpusFamily | str,
    inputs: G7FamilyInputs,
    draft: ResponseDraftSpec,
    placeholder_response: str,
    master_seed: str,
    item_index: int,
) -> ScenarioProgram:
    """Build one isolated yielded-only neutral-prefix capture program."""
    family = _response_family(family)
    _require_inputs(inputs)
    _require_draft(draft)
    _require_text(placeholder_response, "placeholder_response")
    _require_item_index(item_index)
    bundle, template = select_approved_scenario_inputs(
        registry,
        split=split,
        template_id=inputs.template_id,
        asset_ids=inputs.asset_ids,
    )
    plan = _timing(bundle.split, family, master_seed, item_index)
    return _program(
        bundle=bundle,
        template=template,
        family=family,
        master_seed=master_seed,
        plan=plan,
        frames=_frames(draft.invitation, activity="paused"),
        actions=(
            RespondAction(
                type="respond", reply_to_event_id=_snapshot_id(), text=placeholder_response
            ),
        ),
        openings=(BeatOpening("b0", _snapshot_id()),),
    )


def _build_twin(
    registry: AssetRegistry,
    *,
    split: Split | str,
    family: CorpusFamily,
    inputs: G7FamilyInputs,
    profile: SimpleResponseProfile,
    master_seed: str,
    item_index: int,
) -> ResponseFloorTwinPrograms:
    _require_inputs(inputs)
    if not isinstance(profile, SimpleResponseProfile):
        raise TypeError("profile must be a SimpleResponseProfile")
    _require_item_index(item_index)
    bundle, template = select_approved_scenario_inputs(
        registry,
        split=split,
        template_id=inputs.template_id,
        asset_ids=inputs.asset_ids,
    )
    asset = profile.assets[item_index]
    plan = _timing(bundle.split, family, master_seed, item_index)
    group_id = (
        "g7-response-floor-"
        + artifact_digest(
            {
                "family": family.value,
                "master_seed": master_seed,
                "item_index": item_index,
                "asset_ids": tuple(asset.asset_id for asset in bundle.assets),
                "request": asset.serialized_neutral_request_sha256,
                "response": asset.candidate_response,
            }
        )[7:23]
    )
    yielded = _program(
        bundle=bundle,
        template=template,
        family=family,
        master_seed=master_seed,
        plan=plan,
        frames=_frames(asset.draft.invitation, activity="paused"),
        actions=(
            RespondAction(
                type="respond", reply_to_event_id=_snapshot_id(), text=asset.candidate_response
            ),
        ),
        counterfactual=_link(group_id, "yielded"),
        openings=(BeatOpening("b0", _snapshot_id()),),
    )
    active = _program(
        bundle=bundle,
        template=template,
        family=family,
        master_seed=master_seed,
        plan=plan,
        frames=_frames(asset.draft.invitation, activity="active"),
        actions=(
            IdleAction(
                type="idle", reason=IdleReason.AWAITING_OPENING, related_event_id=_snapshot_id()
            ),
        ),
        counterfactual=_link(group_id, "active"),
        openings=(),
    )
    return ResponseFloorTwinPrograms(family, group_id, asset, (yielded, active))


def _program(
    *,
    bundle: AssetBundle,
    template: AssetRecord,
    family: CorpusFamily,
    master_seed: str,
    plan: TimingPlan,
    frames: tuple[ScheduledSamplerFrame, ...],
    actions: tuple[RespondAction, ...] | tuple[IdleAction, ...],
    openings: tuple[BeatOpening, ...],
    counterfactual: CounterfactualDeclaration | None = None,
) -> ScenarioProgram:
    if len(actions) != 1:
        raise ValueError("response-floor programs must terminate at their only branch")
    beats = ("b0",)
    warrants = (
        BeatResponseWarrant("b0", _snapshot_id(), ResponseWarrantKind.INVITATION),
    )
    return ScenarioProgram(
        bundle=bundle,
        template=template,
        family=family,
        master_seed=master_seed,
        timing_plan=plan,
        frames=frames,
        actions=actions,
        tool_results=(),
        beat_ids=beats,
        stale_results_by_beat=tuple(BeatStaleResults(beat, ()) for beat in beats),
        perturbations=(DeclaredPerturbation("floor_opening"),),
        counterfactual=counterfactual,
        response_warrants_by_beat=warrants,
        openings_by_beat=openings,
    )


def _frames(invitation: str, *, activity: str) -> tuple[ScheduledSamplerFrame, ...]:
    cursor = utf16_len(invitation)
    return (
        ScheduledSamplerFrame(
            0,
            canonicalize_tim_json(
                {
                    "text": invitation,
                    "selection_start": cursor,
                    "selection_end": cursor,
                    "is_composing": False,
                    "input_type": "insertText",
                    "activity": activity,
                    "client_ts": 0,
                }
            ),
        ),
    )


def _timing(split: Split, family: CorpusFamily, master_seed: str, item_index: int) -> TimingPlan:
    return materialize_timing_plan(
        TimingSeed(split, f"g7-response-floor:{family.value}:{master_seed}:{item_index}"), 1
    )


def _link(group_id: str, member_id: str) -> CounterfactualDeclaration:
    return CounterfactualDeclaration(
        kind="twin",
        group_id=group_id,
        member_id=member_id,
        member_ids=("active", "yielded"),
        flipped_perturbation="floor_opening",
    )


def _validate_links(group_id: str, yielded: ScenarioProgram, active: ScenarioProgram) -> None:
    for program, member_id in ((yielded, "yielded"), (active, "active")):
        link = program.counterfactual
        if (
            link is None
            or link.kind.value != "twin"
            or link.group_id != group_id
            or link.member_id != member_id
            or link.member_ids != ("active", "yielded")
            or link.flipped_perturbation.value != "floor_opening"
        ):
            raise ValueError("response-floor twin linkage is incomplete")


def _response_family(family: CorpusFamily | str) -> CorpusFamily:
    try:
        value = CorpusFamily(family)
    except (TypeError, ValueError) as error:
        raise ValueError("family must be a known G7 response family") from error
    if value not in G7_RESPONSE_FAMILIES:
        raise ValueError("family must be a supported G7 response family")
    return value


def _require_inputs(inputs: G7FamilyInputs) -> None:
    if not isinstance(inputs, G7FamilyInputs):
        raise TypeError("inputs must be G7FamilyInputs")


def _require_draft(draft: ResponseDraftSpec) -> None:
    if not isinstance(draft, ResponseDraftSpec):
        raise TypeError("draft must be a ResponseDraftSpec")


def _require_text(value: str, name: str) -> None:
    if not isinstance(value, str) or value.strip() != value or not value:
        raise ValueError(f"{name} must be a non-blank trimmed response")


def _require_item_index(item_index: int) -> None:
    if isinstance(item_index, bool) or not isinstance(item_index, int):
        raise TypeError("item_index must be an integer")
    if not 0 <= item_index < _RESPONSE_COUNT:
        raise ValueError("item_index must select one of ten response assets")


def _snapshot_id() -> str:
    return "e_000002"
