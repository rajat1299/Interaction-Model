"""Offline WP3-2 DEV reconstruction, raw capture, and deterministic grading."""

from __future__ import annotations

import asyncio
import gzip
import json
import math
import re
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from secrets import token_hex
from tempfile import TemporaryDirectory

from pydantic import ValidationError

from im.assets.model import Split, canonical_artifact_bytes
from im.assets.registry import AssetRegistry
from im.canonical_json import TimJsonError, parse_tim_json
from im.generation.g7_rollover_checkpoint import build_g7_rollover_checkpoint_catalog
from im.generation.oracle import validate_oracle_action
from im.generation.phase2_dev_states import _execute, _program_plan, _registry
from im.generation.phase2_review_projection import parse_phase2_review_evidence
from im.generation.publication import publish_directory_transaction
from im.generation.runtime import DecisionBoundary
from im.generation.scenarios import GeneratedScenario, ScenarioValidationError
from im.generation.sidecar import BeatEvidence
from im.license import Allowed, SnapshotView, TimerFireView, ToolResultView, blocking_codes, check
from im.probes.grading import (
    GenerationStructureGrade,
    OpenTextRule,
    SemanticTextAssessment,
    finalize_generation_grade,
    grade_generation_structure,
)
from im.probes.validate import ProbeValidationError, assert_reference_integrity
from im.schema.actions import (
    ACTION_ADAPTER,
    Action,
    CancelAction,
    DelegateAction,
    IdleAction,
    IntegrateAction,
    NudgeAction,
    RespondAction,
    ScheduleAction,
    SkipAction,
)
from im.schema.common import Disposition, LicenseBlockCode, TimerStatus, ToolResultStatus
from im.training.phase3_data import (
    BACKBONE,
    PINNED_STOP_SEQUENCE,
    SEALED_TEST_RELATIVE_PATH,
    PinnedTokenizer,
    _generation_prefix_tokens,
    _literal_tokens,
    _read_bytes,
    _verify_checksum_manifest,
    _verify_source_revision,
    _wp3_1_prompt_messages,
    guard_read_path,
    load_pinned_tokenizer,
    verify_phase2_inputs,
)
from im.training.phase3_framing import (
    TERMINAL_FRAMING_VERSION,
    TerminalFramingError,
    TokenDecoder,
    project_terminal_output,
)

DEV_CLOSEOUT_MANIFEST = "sha256:94d76d8ddcccfea2db937f33b8beabda3a5fc1fe89ddbf6361b69b0e669a57e7"
DEV_PACKET_MANIFEST = "sha256:fd79f652f0531f5595879051310dccc4c377c3aea7bf93fcbeba252e830282f8"
DEV_EVIDENCE_SHA256 = "sha256:908d8a2b0cf5c9c711fdb221426233cb73103bc5b6aa9a56f2c8dfeb60b70c42"
DEV_PLAN_SHA256 = "sha256:cd493c42b04dad1279ef05b244044c1ee30dfb97d703f8adb8ea486b6e8fe116"
STATIC_V2_SHA256 = "sha256:586c91088eabfda9a369ff557c5d0c28fb334dd11f56aed988f1f8a7d6ea1f75"
RUN_MANIFEST_SHA256 = "sha256:0746089410b55405cebcb01d8376ce68807108c8418230da3b60bb85c6fdc945"
RETENTION_PACKET_SHA256 = "sha256:1b1fc7e0df7396b6f5716c35741a33d17c5b716ddd893892f866093e9cfca54c"
FROZEN_ROLLOVER_A_STREAM_SHA256 = (
    "sha256:c0fab470b1f5e8e1564e1d0bd6c0e9d21ae5eeb63e109eeb2e6b2614b8c02640"
)
FROZEN_ROLLOVER_A_SIDECAR_SHA256 = (
    "sha256:87749ec56078c59fd2e2ab9da0d6add00c96b293d6ea6681d5efc83c1b7fdd0d"
)
ACTION_TYPES = (
    "cancel",
    "delegate",
    "idle",
    "integrate",
    "mark",
    "nudge",
    "respond",
    "schedule",
    "skip",
)
OPEN_TEXT_RUBRIC_VERSION = "phase3-open-text-rubric-v1"
FROZEN_ACTIVE_FLOOR_DENOMINATOR = 12
FROZEN_POSITIVE_ACTION_DENOMINATOR = 153
FROZEN_SAMPLING_REQUESTS_SHA256 = (
    "sha256:674c8a91c732bdf0b6661a91e7b2ee365d22ba7a3e08d549276d655c22a746f6"
)
FROZEN_SAMPLING_MANIFEST_SHA256 = (
    "sha256:1f05d80c49baa9a79311ec2567a46995babf9e90a26f674a18b7b9f8c09940d5"
)
FROZEN_CANARY_STATE_IDS = (
    "dev:637dbaef9a4a2ceae7c9974aebf7c90b597319593d5a1ce54f9a2251a2789670:11",
    "dev:675cdaa119719089c0735f390292067a527ae9f5f782f06e8afb3a08df5de32c:5",
    "dev:0b4e98978d5f14e3afb723a8df2a8c3b674f9e8c108afa9a8cc26e52d3b1a1fd:1",
)
FROZEN_SMALL_SLICE_IDS = (
    "dev:6b594f01fd4d75abbcffbc439b52bf587b2f0dbfd835f0f3e24b538fb99213e8:4",
    "dev:8fbbe685d1935f98cbe5d952b7adb71261528f240503b98dcc0a2dab65e5e1e0:4",
    "dev:017810fc0e54016a1a28ae1b57d7900bce834645d3b5f32fd58ea1ed4b386eb4:4",
    "dev:fc79907db4bfe68f486634419f2d2b1022d89245788b0fa22b235fb1e5469c38:4",
    "dev:7a5c2658e17319c9fe480fa4caa21988f6e7631779dc6b646fa9b1fd510966f4:4",
    "dev:808c5cc4351a56e758a3cc9d46fe32e60563ba46215989fd4727755e6f09fc32:4",
    "dev:ae754f8a2bcfc39abd500a0c9113f6b589a6f58e8e8001e85d8dc3763f307af0:4",
    "dev:07017c50b42d832068b38f59f78b2cbebf6678f4c5c14bebf996461289c31099:27",
    "dev:f5a1fd14742beb2b796e1c91ff32dec633da2f94594546a234ab4aab0ee8800f:24",
)
SAMPLING = {
    "max_tokens": 1024,
    "seed": 20260801,
    "stop": list(PINNED_STOP_SEQUENCE),
    "temperature": 0.0,
    "top_k": -1,
    "top_p": 1.0,
}
HARD_PROVENANCE_CODES = frozenset(
    {
        LicenseBlockCode.UNKNOWN_REFERENCE,
        LicenseBlockCode.SPAN_MISMATCH,
        LicenseBlockCode.RESULT_NOT_READY,
        LicenseBlockCode.FIRE_NOT_OPEN,
        LicenseBlockCode.TIMER_NOT_ACTIVE,
    }
)
REQUIRED_SENTINEL_TAGS = frozenset(
    {
        *(f"action:{name}" for name in ACTION_TYPES),
        "hard:active_floor",
        "hard:already_handled_negative",
        "hard:cancel_target",
        "hard:duplicate_delegate_negative",
        "hard:duplicate_schedule_negative",
        "hard:fire_not_open",
        "hard:hidden_thinking",
        "hard:inactive_timer",
        "hard:nudge_fire",
        "hard:result_not_ready",
        "hard:rollover",
        "hard:timer_identity",
        "hard:timer_interval_message",
        "hard:tool_provenance",
        "hard:unknown_reference",
        "hard:utf16_span",
        "hard:wrong_causal_result",
    }
)
SENTINEL_TAG_RULES = {
    **{f"action:{name}": f"frozen expected action type is {name}" for name in ACTION_TYPES},
    "hard:active_floor": "gold idle(awaiting_opening) and authenticated LicenseView.floor_owned",
    "hard:already_handled_negative": "captured view retains handled event ids",
    "hard:cancel_target": "frozen expected action is cancel",
    "hard:duplicate_delegate_negative": "gold idle view has pending tool requests",
    "hard:duplicate_schedule_negative": "gold idle view has an exact matching timer schedule",
    "hard:fire_not_open": "captured view retains a non-open timer fire",
    "hard:hidden_thinking": "all raw outputs are scanned for think tags",
    "hard:inactive_timer": "captured view retains a non-active timer",
    "hard:nudge_fire": "frozen expected action is nudge",
    "hard:result_not_ready": "captured view retains an incomplete or non-succeeded result",
    "hard:rollover": "authenticated DEV decision is a rollover decision",
    "hard:timer_identity": "captured view retains at least one timer",
    "hard:timer_interval_message": "frozen expected action is schedule",
    "hard:tool_provenance": "captured view retains a pending request or tool result",
    "hard:unknown_reference": "frozen expected action has a reference-bearing non-idle route",
    "hard:utf16_span": "span-bearing expected action has a captured latest snapshot",
    "hard:wrong_causal_result": "captured view/evidence has an alternative same-route subject",
}
_THINKING = re.compile(r"<think(?:\s|>)|</think\s*>", re.IGNORECASE)


class Phase3EvalError(ValueError):
    """An offline WP3-2 trust boundary or grading invariant failed."""


@dataclass(frozen=True, slots=True)
class DevEvalState:
    """One authenticated DEV decision plus its faithfully rebuilt runtime evidence."""

    state_id: str
    priority_rank: int
    source_unit_id: str
    stream_sha256: str
    decision_policy_seq: int
    family: str
    shape_id: str
    rollover: bool
    boundary_class: str
    risk_flags: tuple[str, ...]
    expected: Action
    prompt_hash: str
    messages: tuple[Mapping[str, str], ...]
    input_tokens: tuple[int, ...]
    visible_prefix_sha256: str
    boundary: DecisionBoundary
    evidence: BeatEvidence

    @property
    def action_type(self) -> str:
        return str(self.expected.type)

    def inventory_row(self) -> dict[str, object]:
        return {
            "action_type": self.action_type,
            "boundary_class": self.boundary_class,
            "coverage_evidence": sentinel_evidence(self),
            "coverage_tags": sorted(sentinel_tags(self)),
            "decision_policy_seq": self.decision_policy_seq,
            "expected_action": self.expected.model_dump(mode="json"),
            "family": self.family,
            "input_token_count": len(self.input_tokens),
            "input_token_ids": list(self.input_tokens),
            "input_token_ids_sha256": _token_digest(self.input_tokens),
            "messages": [dict(message) for message in self.messages],
            "priority_rank": self.priority_rank,
            "prompt_hash": self.prompt_hash,
            "risk_flags": list(self.risk_flags),
            "rollover": self.rollover,
            "shape_id": self.shape_id,
            "source_unit_id": self.source_unit_id,
            "state_id": self.state_id,
            "stream_sha256": self.stream_sha256,
            "visible_prefix_sha256": self.visible_prefix_sha256,
        }


@dataclass(frozen=True, slots=True)
class RawGeneration:
    """Immutable raw-first record written before parsing or grading."""

    evaluation_run_id: str
    model_identity: str
    checkpoint_identity: str
    sampling_manifest_sha256: str
    state_id: str
    output_token_ids: tuple[int, ...]
    decoded_bytes: bytes
    finish_reason: str
    latency_ms: int | None

    @property
    def length_invalid(self) -> bool:
        return self.finish_reason in {"length", "max_tokens"}

    def as_json_object(self) -> dict[str, object]:
        decoded = self.decoded_bytes.decode("utf-8")
        return {
            "checkpoint_identity": self.checkpoint_identity,
            "decoded_utf8": decoded,
            "evaluation_run_id": self.evaluation_run_id,
            "finish_reason": self.finish_reason,
            "hidden_thinking": bool(_THINKING.search(decoded)),
            "kind": "phase3-wp3-2-raw-generation",
            "latency_ms": self.latency_ms,
            "length_invalid": self.length_invalid,
            "output_bytes_sha256": f"sha256:{sha256(self.decoded_bytes).hexdigest()}",
            "output_token_count": len(self.output_token_ids),
            "output_token_ids": list(self.output_token_ids),
            "output_token_ids_sha256": _token_digest(self.output_token_ids),
            "model_identity": self.model_identity,
            "sampling_manifest_sha256": self.sampling_manifest_sha256,
            "schema_version": 1,
            "state_id": self.state_id,
        }


@dataclass(frozen=True, slots=True)
class PersistedRawGeneration:
    """Create-only raw record identity; grading always reloads its exact bytes."""

    path: Path
    sha256: str


@dataclass(frozen=True, slots=True)
class OpenTextRubric:
    """One frozen, row-specific semantic rubric; it is never scored automatically."""

    state_id: str
    action_type: str
    subtype: str
    required_points: tuple[str, ...]
    forbidden_claims: tuple[str, ...]
    support_event_ids: tuple[str, ...]
    paraphrase_policy: str
    failure_reason_codes: tuple[str, ...]

    def as_json_object(self) -> dict[str, object]:
        value = {
            "action_type": self.action_type,
            "failure_reason_codes": list(self.failure_reason_codes),
            "forbidden_claims": list(self.forbidden_claims),
            "paraphrase_policy": self.paraphrase_policy,
            "required_points": list(self.required_points),
            "state_id": self.state_id,
            "subtype": self.subtype,
            "support_event_ids": list(self.support_event_ids),
            "version": OPEN_TEXT_RUBRIC_VERSION,
        }
        value["rubric_sha256"] = f"sha256:{sha256(canonical_artifact_bytes(value)).hexdigest()}"
        return value


@dataclass(frozen=True, slots=True)
class FrozenHumanAssessment:
    """A human semantic decision bound to exactly one frozen rubric row."""

    state_id: str
    rubric_sha256: str
    output_bytes_sha256: str
    passed: bool
    reason_codes: tuple[str, ...]

    def as_json_object(self) -> dict[str, object]:
        return {
            "output_bytes_sha256": self.output_bytes_sha256,
            "passed": self.passed,
            "reason_codes": list(self.reason_codes),
            "rubric_sha256": self.rubric_sha256,
            "state_id": self.state_id,
        }


async def rebuild_dev_states(
    repository_root: Path, tokenizer: PinnedTokenizer
) -> tuple[DevEvalState, ...]:
    """Rebuild exactly the 300 owner-reviewed DEV decisions without touching TEST."""
    root = guard_read_path(repository_root, repository_root)
    phase2 = verify_phase2_inputs(root)
    if phase2.manifests.get("dev") != DEV_CLOSEOUT_MANIFEST:
        raise Phase3EvalError("Phase 2 DEV closeout binding drifted")
    closeout = _json(_read_bytes(root, root / "review/phase2/dev-gate-c-closeout/DEV-FREEZE.json"))
    packet = closeout.get("packet")
    if not isinstance(packet, Mapping) or {
        "decision_count": packet.get("decision_count"),
        "stream_count": packet.get("stream_count"),
        "sha256sums_sha256": packet.get("sha256sums_sha256"),
        "phase2_review_evidence_sha256": packet.get("phase2_review_evidence_sha256"),
        "selected_state_plan_sha256": packet.get("selected_state_plan_sha256"),
    } != {
        "decision_count": 300,
        "stream_count": 167,
        "sha256sums_sha256": DEV_PACKET_MANIFEST,
        "phase2_review_evidence_sha256": DEV_EVIDENCE_SHA256,
        "selected_state_plan_sha256": DEV_PLAN_SHA256,
    }:
        raise Phase3EvalError("frozen DEV closeout metadata drifted")
    packet_root = root / "review/phase2/dev-gate-c-repaired"
    packet_digest, captured = _verify_checksum_manifest(
        root,
        packet_root / "SHA256SUMS",
        capture=frozenset({"phase2-review-evidence.json", "selected-state-plan.json"}),
    )
    if packet_digest != DEV_PACKET_MANIFEST:
        raise Phase3EvalError("repaired DEV packet manifest drifted")
    if (
        f"sha256:{sha256(captured['phase2-review-evidence.json']).hexdigest()}"
        != DEV_EVIDENCE_SHA256
    ):
        raise Phase3EvalError("DEV review evidence drifted")
    if f"sha256:{sha256(captured['selected-state-plan.json']).hexdigest()}" != DEV_PLAN_SHA256:
        raise Phase3EvalError("DEV selected-state plan drifted")
    evidence_json = parse_phase2_review_evidence(captured["phase2-review-evidence.json"])
    evidence_rows = evidence_json.get("decisions")
    if not isinstance(evidence_rows, list) or len(evidence_rows) != 300:
        raise Phase3EvalError("DEV review evidence does not contain exactly 300 decisions")

    with TemporaryDirectory(prefix="phase3-dev-rebuild-") as temporary:
        registry = _registry()
        plan, preexecuted = await _program_plan(registry, Path(temporary) / "plan")
        preexecuted["g7-rollover-a"] = await _frozen_rollover_a(
            root, registry, Path(temporary) / "rollover-a-frozen"
        )
        generated = await _execute(plan, preexecuted, Path(temporary) / "runtime")
    if len(plan.selected) != 300 or len(generated) != 167:
        raise Phase3EvalError("deterministic DEV rebuild count drifted")

    states: list[DevEvalState] = []
    for rank, (selected, frozen) in enumerate(zip(plan.selected, evidence_rows, strict=True)):
        if not isinstance(frozen, Mapping):
            raise Phase3EvalError("DEV evidence row is malformed")
        parent = generated[selected.logical_stream_id]
        sidecar = parent.sidecar.decisions[selected.program_index]
        boundary = parent.decision_boundaries[selected.program_index]
        identity = (parent.stream.sha256, sidecar.observed_policy_seq)
        if identity != (frozen.get("stream_sha256"), frozen.get("decision_policy_seq")):
            raise Phase3EvalError(f"DEV rebuild identity drifted at priority {rank}")
        expected = ACTION_ADAPTER.validate_python(frozen.get("oracle_action"))
        if expected != selected.action or sidecar.action != selected.action:
            raise Phase3EvalError(f"DEV gold action drifted at priority {rank}")
        review = frozen.get("review_evidence")
        trust = review.get("trust_cell") if isinstance(review, Mapping) else None
        if not isinstance(review, Mapping) or not isinstance(trust, Mapping):
            raise Phase3EvalError("DEV review metadata is malformed")
        prompt_hash, messages, _hashes = _wp3_1_prompt_messages(
            root, boundary.policy_bytes, identity=f"DEV priority {rank}"
        )
        tokens = _generation_prefix_tokens(tokenizer, messages)
        state_id = f"dev:{identity[0].removeprefix('sha256:')}:{identity[1]}"
        states.append(
            DevEvalState(
                state_id=state_id,
                priority_rank=rank,
                source_unit_id=selected.logical_stream_id,
                stream_sha256=identity[0],
                decision_policy_seq=identity[1],
                family=str(trust.get("family")),
                shape_id=selected.shape_id,
                rollover=selected.rollover,
                boundary_class=str(review.get("boundary_class")),
                risk_flags=tuple(str(flag) for flag in review.get("risk_flags", ())),
                expected=expected,
                prompt_hash=prompt_hash,
                messages=tuple(messages),
                input_tokens=tokens,
                visible_prefix_sha256=f"sha256:{sha256(boundary.policy_bytes).hexdigest()}",
                boundary=boundary,
                evidence=sidecar.evidence,
            )
        )
    if len({state.state_id for state in states}) != 300:
        raise Phase3EvalError("DEV state identities repeat")
    if len(_active_floor_states(states)) != FROZEN_ACTIVE_FLOOR_DENOMINATOR:
        raise Phase3EvalError("frozen DEV active-floor denominator drifted")
    return tuple(states)


def sentinel_tags(state: DevEvalState) -> frozenset[str]:
    """Return only mechanically evidenced coverage tags for one DEV state."""
    view = state.boundary.license_view
    tags = {f"action:{state.action_type}", "hard:hidden_thinking"}
    if state.action_type != "idle":
        tags.add("hard:unknown_reference")
    if state.action_type in {"mark", "delegate", "schedule", "cancel"} and view.latest_snapshot:
        tags.add("hard:utf16_span")
    if view.pending_tool_requests or any(
        isinstance(event, ToolResultView) for event in view.events
    ):
        tags.add("hard:tool_provenance")
    if _has_wrong_causal_probe(state):
        tags.add("hard:wrong_causal_result")
    if view.timers:
        tags.add("hard:timer_identity")
    if state.action_type == "schedule":
        tags.add("hard:timer_interval_message")
    if state.action_type == "cancel":
        tags.add("hard:cancel_target")
    if state.action_type == "nudge":
        tags.add("hard:nudge_fire")
    if any(
        isinstance(event, TimerFireView) and event.disposition is not Disposition.OPEN
        for event in view.events
    ):
        tags.add("hard:fire_not_open")
    if any(timer.status is not TimerStatus.ACTIVE for timer in view.timers):
        tags.add("hard:inactive_timer")
    if any(
        isinstance(event, ToolResultView)
        and (not event.completed or event.status is not ToolResultStatus.SUCCEEDED)
        for event in view.events
    ):
        tags.add("hard:result_not_ready")
    if state.rollover:
        tags.add("hard:rollover")
    if _is_active_floor_idle(state):
        tags.add("hard:active_floor")
    if view.pending_tool_requests and isinstance(state.expected, IdleAction):
        tags.add("hard:duplicate_delegate_negative")
    if view.visible_handled_event_ids:
        tags.add("hard:already_handled_negative")
    if isinstance(state.expected, IdleAction) and _has_duplicate_schedule_probe(state):
        tags.add("hard:duplicate_schedule_negative")
    return frozenset(tags)


def _is_active_floor_idle(state: DevEvalState) -> bool:
    """The active-floor negative is only a gold idle decision that owns the floor."""
    return (
        isinstance(state.expected, IdleAction)
        and state.expected.reason == "awaiting_opening"
        and state.boundary.license_view.floor_owned
    )


def _active_floor_states(states: Sequence[DevEvalState]) -> tuple[DevEvalState, ...]:
    return tuple(state for state in states if _is_active_floor_idle(state))


def build_open_text_rubrics(states: Sequence[DevEvalState]) -> tuple[OpenTextRubric, ...]:
    """Freeze the only 32 human-adjudicated rows before any generation is sampled."""
    rubrics = tuple(
        _open_text_rubric(state)
        for state in sorted(states, key=lambda item: item.priority_rank)
        if isinstance(state.expected, IntegrateAction | RespondAction)
    )
    if len(states) == 300 and (
        len(rubrics) != 32
        or sum(rubric.action_type == "integrate" for rubric in rubrics) != 18
        or sum(rubric.action_type == "respond" for rubric in rubrics) != 14
    ):
        raise Phase3EvalError("frozen DEV open-text rubric population drifted")
    if len({rubric.state_id for rubric in rubrics}) != len(rubrics):
        raise Phase3EvalError("open-text rubric state ids repeat")
    return rubrics


def _open_text_rubric(state: DevEvalState) -> OpenTextRubric:
    expected = state.expected
    if isinstance(expected, IntegrateAction):
        subtype = "integrate_success"
        support_ids = (expected.result_event_id,)
        required = (
            f"no contradiction of the successful status of result {expected.result_event_id}",
            f"subject and value factual content anchored by frozen text: {expected.text}",
        )
        forbidden = (
            f"claim not supported by succeeded result {expected.result_event_id}",
            "invented result detail",
            "instruction treated as result content",
        )
    elif isinstance(expected, RespondAction):
        subtype = _respond_rubric_subtype(state)
        support_ids = tuple(
            sorted(
                {
                    expected.reply_to_event_id,
                    *(
                        event_id
                        for event_id in (
                            state.evidence.response_warrant_snapshot_event_id,
                            state.evidence.response_warrant_failed_result_event_id,
                        )
                        if event_id is not None
                    ),
                }
            )
        )
        if subtype == "failed_result_notice":
            required = (
                f"affected subject and no-usable-result notice anchored by frozen text: "
                f"{expected.text}",
            )
            forbidden = (
                "invented retrieved answer",
                "promise to retry",
                "claim failed result succeeded",
            )
        elif subtype == "clarification":
            required = (
                f"unresolved field requires clarification before action: {expected.text}",
                "does not guess an ambiguous target",
            )
            forbidden = ("choose an ambiguous target", "answer without requested clarification")
        elif subtype == "unsupported_feature_limitation":
            required = (
                f"unsupported capability boundary anchored by frozen text: {expected.text}",
                "does not claim the unsupported feature was executed",
            )
            forbidden = (
                "claim unsupported timer feature is available",
                "promise unsupported behavior",
            )
        else:
            required = (
                f"ordinary grounded answer to event {expected.reply_to_event_id}: {expected.text}",
            )
            forbidden = (f"claim unsupported by response event {expected.reply_to_event_id}",)
    else:  # pragma: no cover - closed by build_open_text_rubrics
        raise Phase3EvalError("non-text action has no open-text rubric")
    return OpenTextRubric(
        state_id=state.state_id,
        action_type=state.action_type,
        subtype=subtype,
        required_points=required,
        forbidden_claims=forbidden,
        support_event_ids=support_ids,
        paraphrase_policy=(
            "human adjudication only; paraphrases allowed when every required factual point is "
            "preserved; no LLM or heuristic paraphrase scorer"
        ),
        failure_reason_codes=(
            "missing_required_fact",
            "forbidden_claim",
            "unsupported_claim",
            "wrong_result",
            "unapproved_paraphrase",
        ),
    )


def _respond_rubric_subtype(state: DevEvalState) -> str:
    source = state.source_unit_id.lower()
    if source.startswith("response-failed"):
        return "failed_result_notice"
    if "clarification" in source or "ambiguous-cancel" in source:
        return "clarification"
    if "unsupported" in source:
        return "unsupported_feature_limitation"
    return "ordinary_grounded_answer"


def _rubric_index(states: Sequence[DevEvalState]) -> dict[str, OpenTextRubric]:
    return {rubric.state_id: rubric for rubric in build_open_text_rubrics(states)}


def _validated_human_text_assessment(
    state: DevEvalState,
    rubric: OpenTextRubric,
    rule: OpenTextRule | None,
    assessment: FrozenHumanAssessment,
    raw: Mapping[str, object],
) -> SemanticTextAssessment:
    """Convert only a state-and-rubric-bound human decision for the structural grader."""
    if rule is None or assessment.state_id != state.state_id:
        raise Phase3EvalError("semantic assessment is bound to the wrong DEV state")
    rubric_sha256 = rubric.as_json_object()["rubric_sha256"]
    if assessment.rubric_sha256 != rubric_sha256:
        raise Phase3EvalError("semantic assessment uses the wrong frozen rubric hash")
    if assessment.output_bytes_sha256 != raw.get("output_bytes_sha256"):
        raise Phase3EvalError("semantic assessment is bound to different raw output bytes")
    if not isinstance(assessment.passed, bool) or not assessment.reason_codes:
        raise Phase3EvalError("semantic assessment requires a pass bit and reason codes")
    if assessment.passed:
        if assessment.reason_codes != ("all_required_points_present", "no_forbidden_claims"):
            raise Phase3EvalError(
                "approved semantic assessment lacks frozen factual decision codes"
            )
    elif any(code not in rubric.failure_reason_codes for code in assessment.reason_codes):
        raise Phase3EvalError("failed semantic assessment has an unknown frozen reason code")
    return SemanticTextAssessment(
        rule=rule,
        passed=assessment.passed,
        rationale=",".join(assessment.reason_codes),
    )


def sentinel_evidence(state: DevEvalState) -> dict[str, object]:
    """Publish the exact captured facts used to attribute sentinel tags."""
    view = state.boundary.license_view
    return {
        "active_floor_boundary": _is_active_floor_idle(state),
        "active_floor_expected_idle": isinstance(state.expected, IdleAction)
        and state.expected.reason == "awaiting_opening",
        "active_floor_owned": view.floor_owned,
        "causal_alternative_actions": [
            candidate.model_dump(mode="json") for candidate in _wrong_causal_candidates(state)
        ],
        "duplicate_schedule_timer_ids": list(_duplicate_schedule_timer_ids(state)),
        "handled_event_ids": sorted(view.visible_handled_event_ids),
        "inactive_timer_ids": sorted(
            timer.timer_id for timer in view.timers if timer.status is not TimerStatus.ACTIVE
        ),
        "latest_snapshot_event_id": (
            None if view.latest_snapshot is None else view.latest_snapshot.event_id
        ),
        "non_open_fire_event_ids": sorted(
            event.event_id
            for event in view.events
            if isinstance(event, TimerFireView) and event.disposition is not Disposition.OPEN
        ),
        "not_ready_result_event_ids": sorted(
            event.event_id
            for event in view.events
            if isinstance(event, ToolResultView)
            and (not event.completed or event.status is not ToolResultStatus.SUCCEEDED)
        ),
        "pending_tool_request_ids": sorted(
            request.request_id for request in view.pending_tool_requests
        ),
        "rollover": state.rollover,
        "timer_ids": sorted(timer.timer_id for timer in view.timers),
        "tool_result_event_ids": sorted(
            event.event_id for event in view.events if isinstance(event, ToolResultView)
        ),
    }


def select_fast_sentinels(states: Sequence[DevEvalState]) -> tuple[DevEvalState, ...]:
    """Select a deterministic exact minimum cover of actions and evidenced hard classes."""
    if not states:
        raise Phase3EvalError("cannot select sentinels from an empty DEV set")
    required = set(REQUIRED_SENTINEL_TAGS)
    candidates = [(state, sentinel_tags(state) & required) for state in states]
    for tag in required:
        if not any(tag in tags for _state, tags in candidates):
            raise Phase3EvalError(f"DEV cannot cover sentinel tag {tag}")
    by_tags: dict[frozenset[str], DevEvalState] = {}
    for state, tags in candidates:
        prior = by_tags.get(tags)
        if prior is None or (len(state.input_tokens), state.state_id) < (
            len(prior.input_tokens),
            prior.state_id,
        ):
            by_tags[tags] = state
    tags_in_order = sorted(required)
    bit = {tag: 1 << index for index, tag in enumerate(tags_in_order)}
    full = (1 << len(tags_in_order)) - 1
    dp: dict[int, tuple[DevEvalState, ...]] = {0: ()}
    for tags, state in sorted(by_tags.items(), key=lambda item: item[1].state_id):
        mask = sum(bit[tag] for tag in tags)
        for covered, chosen in tuple(dp.items()):
            combined = covered | mask
            option = tuple(sorted((*chosen, state), key=lambda item: item.state_id))
            current = dp.get(combined)
            if current is None or _cover_score(option) < _cover_score(current):
                dp[combined] = option
    best = dp.get(full)
    if best is None:
        raise Phase3EvalError("no exact fast-sentinel cover exists")
    return best


def select_canary_sentinels(fast: Sequence[DevEvalState]) -> tuple[DevEvalState, ...]:
    """Bind exactly three short sentinels by deterministic coverage and token length."""
    eligible = [state for state in fast if len(state.input_tokens) <= 18_182]
    if len(eligible) < 3:
        raise Phase3EvalError("fewer than three fast sentinels fit the canary ceiling")
    chosen: list[DevEvalState] = []
    covered: set[str] = set()
    while len(chosen) < 3:
        state = min(
            (item for item in eligible if item not in chosen),
            key=lambda item: (
                -len(sentinel_tags(item) - covered),
                len(item.input_tokens),
                item.state_id,
            ),
        )
        chosen.append(state)
        covered.update(sentinel_tags(state))
    return tuple(chosen)


def capture_raw_generation(
    *,
    evaluation_run_id: str,
    model_identity: str,
    checkpoint_identity: str,
    sampling_manifest_sha256: str,
    state_id: str,
    output_token_ids: Iterable[int],
    decoded_bytes: bytes,
    finish_reason: str,
    latency_ms: int | None = None,
) -> RawGeneration:
    """Create the immutable record that must be persisted before parsing."""
    tokens = tuple(output_token_ids)
    identities = (evaluation_run_id, model_identity, checkpoint_identity, state_id)
    if any(not isinstance(value, str) or not value for value in identities) or any(
        isinstance(token, bool) or not isinstance(token, int) or token < 0 for token in tokens
    ):
        raise Phase3EvalError(
            "raw generation requires closed identities and non-negative integer token ids"
        )
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", sampling_manifest_sha256):
        raise Phase3EvalError("raw generation sampling manifest identity is malformed")
    if not isinstance(decoded_bytes, bytes):
        raise Phase3EvalError("raw generation must retain decoded bytes")
    try:
        decoded_bytes.decode("utf-8")
    except UnicodeDecodeError as error:
        raise Phase3EvalError("decoded model output must be exact UTF-8 bytes") from error
    if not isinstance(finish_reason, str) or not finish_reason:
        raise Phase3EvalError("raw generation requires a finish reason")
    if latency_ms is not None and (
        isinstance(latency_ms, bool) or not isinstance(latency_ms, int) or latency_ms < 0
    ):
        raise Phase3EvalError("latency_ms must be non-negative or null")
    return RawGeneration(
        evaluation_run_id=evaluation_run_id,
        model_identity=model_identity,
        checkpoint_identity=checkpoint_identity,
        sampling_manifest_sha256=sampling_manifest_sha256,
        state_id=state_id,
        output_token_ids=tokens,
        decoded_bytes=decoded_bytes,
        finish_reason=finish_reason,
        latency_ms=latency_ms,
    )


def persist_raw_generation(
    repository_root: Path, output: Path, raw: RawGeneration
) -> PersistedRawGeneration:
    """Atomically publish one create-only raw record before any parsing occurs."""
    record = canonical_artifact_bytes(raw.as_json_object())
    digest = f"sha256:{sha256(record).hexdigest()}"
    identity = sha256(
        "\x00".join(
            (
                raw.evaluation_run_id,
                raw.model_identity,
                raw.checkpoint_identity,
                raw.state_id,
                raw.sampling_manifest_sha256,
            )
        ).encode()
    ).hexdigest()
    directory = guard_read_path(repository_root, output) / identity
    publish_directory_transaction(directory, {"raw-generation.json": record})
    return PersistedRawGeneration(directory / "raw-generation.json", digest)


def grade_persisted_generation(
    repository_root: Path,
    state: DevEvalState,
    persisted: PersistedRawGeneration,
    *,
    semantic_assessment: FrozenHumanAssessment | None = None,
    tokenizer: TokenDecoder | None = None,
) -> dict[str, object]:
    """Reload one persisted raw record, then grade its unmodified bytes."""
    raw = _load_persisted_raw(repository_root, persisted)
    return _grade_raw_generation(
        state,
        raw,
        semantic_assessment=semantic_assessment,
        tokenizer=tokenizer,
    )


def _grade_raw_generation(
    state: DevEvalState,
    raw: RawGeneration,
    *,
    semantic_assessment: FrozenHumanAssessment | None = None,
    tokenizer: TokenDecoder | None = None,
) -> dict[str, object]:
    """Internal fixture/shared grader after the raw persistence boundary."""
    if raw.state_id != state.state_id:
        raise Phase3EvalError("raw generation is bound to the wrong DEV state")
    raw_record = raw.as_json_object()
    parsed: Action | None = None
    parse_error: str | None = None
    parser_input = raw.decoded_bytes
    framing: dict[str, object]
    if tokenizer is not None:
        try:
            projection = project_terminal_output(
                finish_reason=raw.finish_reason,
                output_token_ids=raw.output_token_ids,
                decoded_bytes=raw.decoded_bytes,
                tokenizer=tokenizer,
            )
        except TerminalFramingError as error:
            parse_error = f"terminal_framing:{error.reason}"
            framing = {
                "consumed_token_count": 0,
                "consumed_token_id": None,
                "failure_reason": error.reason,
                "format_version": TERMINAL_FRAMING_VERSION,
                "parser_input_sha256": None,
                "raw_output_sha256": raw_record["output_bytes_sha256"],
                "terminal_projection_status": "failed",
            }
        else:
            parser_input = projection.parser_input
            framing = projection.audit_record()
    else:
        framing = {
            "consumed_token_count": 0,
            "consumed_token_id": None,
            "format_version": TERMINAL_FRAMING_VERSION,
            "parser_input_sha256": raw_record["output_bytes_sha256"],
            "raw_output_sha256": raw_record["output_bytes_sha256"],
            "terminal_projection_status": "not_applied_offline_fixture",
        }
    if parse_error is None and raw.length_invalid:
        parse_error = "length_termination"
    elif parse_error is None:
        try:
            parsed = ACTION_ADAPTER.validate_python(parse_tim_json(parser_input))
        except (TimJsonError, ValidationError, TypeError, ValueError, UnicodeDecodeError) as error:
            parse_error = type(error).__name__
    licensed = False
    codes: tuple[LicenseBlockCode, ...] = (LicenseBlockCode.MALFORMED_ACTION,)
    reference_integrity = False
    structure: GenerationStructureGrade | None = None
    executed_match = False
    oracle_valid = False
    semantic_status = "not_applicable"
    if parsed is not None:
        codes = blocking_codes(parsed, state.boundary.license_view)
        licensed = isinstance(check(parsed, state.boundary.license_view), Allowed)
        try:
            assert_reference_integrity(parsed, state.boundary.license_view)
            reference_integrity = True
        except ProbeValidationError:
            reference_integrity = False
        try:
            validate_oracle_action(state.boundary, parsed, state.evidence)
            oracle_valid = True
        except (ScenarioValidationError, TypeError, ValueError):
            oracle_valid = False
        structure = grade_generation_structure(state.expected, parsed)
        if structure.text_rule is None:
            executed_match = (
                structure.structural_match and licensed and reference_integrity and oracle_valid
            )
        elif semantic_assessment is None:
            semantic_status = "pending_semantic_assessment"
        else:
            try:
                rubric = _open_text_rubric(state)
                text_assessment = _validated_human_text_assessment(
                    state, rubric, structure.text_rule, semantic_assessment, raw_record
                )
                finalized = finalize_generation_grade(
                    structure,
                    text_assessment=text_assessment,
                ).passed
            except ValueError as error:
                raise Phase3EvalError("semantic assessment uses the wrong frozen rubric") from error
            semantic_status = "passed" if text_assessment.passed else "failed"
            executed_match = finalized and licensed and reference_integrity and oracle_valid
    intrusive = (
        isinstance(state.expected, IdleAction)
        and parsed is not None
        and not isinstance(parsed, IdleAction)
    )
    duplicate = bool(
        set(codes)
        & {
            LicenseBlockCode.DUPLICATE_SCHEDULE,
            LicenseBlockCode.DUPLICATE_TOOL_REQUEST,
            LicenseBlockCode.TARGET_ALREADY_HANDLED,
        }
    )
    causal_failure = None if parsed is None else _causal_failure(state.expected, parsed)
    wrong_causal_result = causal_failure is not None
    provenance = bool(set(codes) & HARD_PROVENANCE_CODES) or wrong_causal_result
    hard_failures = _hard_failures(
        state,
        parsed,
        raw_record,
        codes,
        wrong_causal_result=wrong_causal_result,
        reference_integrity=reference_integrity,
        structure=structure,
    )
    return {
        "executed": {
            "duplicate_action": duplicate,
            "causal_failure": causal_failure,
            "hard_failures": hard_failures,
            "intrusive_action": intrusive,
            "match": executed_match,
            "oracle_valid": oracle_valid,
            "provenance_violation": provenance,
            "semantic_status": semantic_status,
            "wrong_causal_result": wrong_causal_result,
        },
        "expected_action_type": state.action_type,
        "framing": framing,
        "predicted_action": None if parsed is None else parsed.model_dump(mode="json"),
        "raw": raw_record,
        "state_id": state.state_id,
        "structural": {
            "closed_field_match": False if structure is None else structure.structural_match,
            "license_block_codes": [code.value for code in codes],
            "licensed": licensed,
            "parse_error": parse_error,
            "parse_union_valid": parsed is not None,
            "reference_integrity": reference_integrity,
            "structural_pass": bool(
                structure is not None
                and structure.structural_match
                and reference_integrity
                and oracle_valid
            ),
            "text_rule": None
            if structure is None or structure.text_rule is None
            else structure.text_rule.value,
        },
    }


def compute_dev_metrics(
    repository_root: Path,
    states: Sequence[DevEvalState],
    persisted: Sequence[PersistedRawGeneration],
    *,
    expected_evaluation_identity: tuple[str, str, str, str],
    semantic_assessments: Mapping[str, FrozenHumanAssessment] | None = None,
    tokenizer: TokenDecoder | None = None,
) -> dict[str, object]:
    """Reload and regrade exactly 300 persisted records before aggregation."""
    if len(states) != 300 or len(persisted) != 300:
        raise Phase3EvalError("DEV metrics require exactly 300 states and raw records")
    if (
        len(expected_evaluation_identity) != 4
        or any(not isinstance(value, str) or not value for value in expected_evaluation_identity)
        or not re.fullmatch(r"sha256:[0-9a-f]{64}", expected_evaluation_identity[3])
    ):
        raise Phase3EvalError("expected DEV evaluation identity is malformed")
    by_id = {state.state_id: state for state in states}
    assessments = semantic_assessments or {}
    grades = []
    seen: set[str] = set()
    for record in persisted:
        raw = _load_persisted_raw(repository_root, record)
        if (
            raw.evaluation_run_id,
            raw.model_identity,
            raw.checkpoint_identity,
            raw.sampling_manifest_sha256,
        ) != expected_evaluation_identity:
            raise Phase3EvalError("persisted DEV records mix evaluation identities")
        state = by_id.get(raw.state_id)
        if state is None or raw.state_id in seen:
            raise Phase3EvalError("persisted DEV raw identities are missing or repeated")
        seen.add(raw.state_id)
        grades.append(
            _grade_raw_generation(
                state,
                raw,
                semantic_assessment=assessments.get(raw.state_id),
                tokenizer=tokenizer,
            )
        )
    if seen != set(by_id) or set(assessments) - seen:
        raise Phase3EvalError("persisted DEV raw and semantic identities do not close")
    return _compute_dev_metrics_from_grades(states, grades)


def _compute_dev_metrics_from_grades(
    states: Sequence[DevEvalState], grades: Sequence[Mapping[str, object]]
) -> dict[str, object]:
    """Internal aggregation after production regrading."""
    if len(states) != 300 or len(grades) != 300:
        raise Phase3EvalError("DEV metrics require exactly 300 states and 300 grades")
    by_id = {state.state_id: state for state in states}
    if len(by_id) != 300 or {str(grade.get("state_id")) for grade in grades} != set(by_id):
        raise Phase3EvalError("DEV grade identities do not exactly match the frozen states")
    ordered = sorted(grades, key=lambda grade: by_id[str(grade["state_id"])].priority_rank)
    pending = [
        str(grade["state_id"])
        for grade in ordered
        if _nested(grade, "executed", "semantic_status") == "pending_semantic_assessment"
    ]
    parse = sum(bool(_nested(grade, "structural", "parse_union_valid")) for grade in ordered)
    closed = sum(bool(_nested(grade, "structural", "closed_field_match")) for grade in ordered)
    success = {
        str(grade["state_id"]): bool(_nested(grade, "executed", "match")) for grade in ordered
    }
    grade_by_id = {str(grade["state_id"]): grade for grade in ordered}
    streams: dict[str, list[bool]] = {}
    for state in states:
        streams.setdefault(state.stream_sha256, []).append(success[state.state_id])
    sequence_success = sum(all(values) for values in streams.values()) / len(streams)
    idle_ids = [state.state_id for state in states if state.action_type == "idle"]
    positive_ids = [state.state_id for state in states if state.action_type != "idle"]
    intrusive = sum(bool(_nested(grade, "executed", "intrusive_action")) for grade in ordered)
    duplicate = sum(bool(_nested(grade, "executed", "duplicate_action")) for grade in ordered)
    provenance = sum(bool(_nested(grade, "executed", "provenance_violation")) for grade in ordered)
    active_floor_ids = [state.state_id for state in _active_floor_states(states)]
    active_floor_respond = sum(
        isinstance(grade_by_id[state_id].get("predicted_action"), Mapping)
        and grade_by_id[state_id]["predicted_action"].get("type") == "respond"  # type: ignore[union-attr]
        for state_id in active_floor_ids
    )
    duplicate_schedule = sum(
        "duplicate_schedule" in (_nested(grade, "structural", "license_block_codes") or ())
        for grade in ordered
    )
    duplicate_delegate = sum(
        "duplicate_tool_request" in (_nested(grade, "structural", "license_block_codes") or ())
        for grade in ordered
    )
    mechanics_opportunities = [
        (state, opportunity)
        for state in states
        for opportunity in _duplicate_mechanics_opportunities(state)
    ]
    mechanics_duplicate = sum(
        ("duplicate_tool_request" if opportunity == "duplicate_delegate" else "duplicate_schedule")
        in (_nested(grade_by_id[state.state_id], "structural", "license_block_codes") or ())
        for state, opportunity in mechanics_opportunities
    )
    hidden_thinking = sum(bool(_nested(grade, "raw", "hidden_thinking")) for grade in ordered)
    hard_failure_counts = Counter(
        failure
        for grade in ordered
        for failure in (_nested(grade, "executed", "hard_failures") or ())
    )
    action_counts = Counter(state.action_type for state in states)
    small_slice_ids = {
        action: [state.state_id for state in states if state.action_type == action]
        for action, count in action_counts.items()
        if count < 10
    }
    slice_errors = {
        action: sum(
            not bool(_nested(grade_by_id[state_id], "executed", "match")) for state_id in state_ids
        )
        for action, state_ids in small_slice_ids.items()
    }
    result = {
        "active_floor_denominator": len(active_floor_ids),
        "active_floor_respond_rate": (
            active_floor_respond / len(active_floor_ids) if active_floor_ids else 0.0
        ),
        "baseline_failure_count": sum(not matched for matched in success.values()),
        "baseline_failure_state_ids": [
            state_id for state_id, matched in success.items() if not matched
        ],
        "closed_field_accuracy": closed / 300,
        "duplicate_action_rate": duplicate / 300,
        "duplicate_delegate_rate": duplicate_delegate / 300,
        "duplicate_delegate_schedule_rate": (duplicate_delegate + duplicate_schedule) / 300,
        "duplicate_delegate_schedule_opportunity_count": len(mechanics_opportunities),
        "duplicate_delegate_schedule_opportunity_rate": (
            mechanics_duplicate / len(mechanics_opportunities) if mechanics_opportunities else 0.0
        ),
        "duplicate_schedule_rate": duplicate_schedule / 300,
        "executed_success_rate": sum(success.values()) / 300,
        "hidden_thinking_count": hidden_thinking,
        "forbidden_error_count": sum(hard_failure_counts.values()),
        "forbidden_errors": dict(sorted(hard_failure_counts.items())),
        "intrusive_action_rate": intrusive / len(idle_ids),
        "parse_union_validity": parse / 300,
        "positive_action_denominator": len(positive_ids),
        "positive_action_micro_accuracy": (
            sum(success[state_id] for state_id in positive_ids) / len(positive_ids)
            if positive_ids
            else 0.0
        ),
        "provenance_violation_rate": provenance / 300,
        "sequence_success": sequence_success,
        "small_action_slice_errors": dict(sorted(slice_errors.items())),
        "small_action_slice_state_ids": small_slice_ids,
    }
    result["d13_score"] = (
        sequence_success
        - 5 * result["intrusive_action_rate"]
        - 3 * result["duplicate_action_rate"]
        - 5 * result["provenance_violation_rate"]
    )
    result["pending_semantic_assessment_count"] = len(pending)
    result["pending_semantic_state_ids"] = pending
    gate_checks = {
        "active_floor_respond_rate": result["active_floor_respond_rate"] <= 0.05,
        "duplicate_delegate_schedule_opportunity_rate": (
            result["duplicate_delegate_schedule_opportunity_rate"] <= 0.10
        ),
        "forbidden_error_count": result["forbidden_error_count"] == 0,
        "parse_union_validity": result["parse_union_validity"] >= 0.98,
        "positive_action_micro_accuracy": result["positive_action_micro_accuracy"] >= 0.90,
        "small_action_slices": all(error_count <= 1 for error_count in slice_errors.values()),
    }
    result["mechanics_gate"] = {
        "checks": gate_checks,
        "passed": all(gate_checks.values()),
    }
    return result


async def build_offline_candidate(
    *,
    repository_root: Path,
    tokenizer_directory: Path,
    source_commit: str,
    blinding_nonce: str,
) -> tuple[dict[str, bytes], bytes]:
    """Build a no-provider, no-TEST WP3-2 candidate from a clean source commit."""
    root = guard_read_path(repository_root, repository_root)
    _verify_source_revision(root, source_commit)
    static = _bound_json(
        root,
        root / "review/phase3/wp3-0-static-v2-candidate-v2/phase3-static-v2-candidate.json",
        STATIC_V2_SHA256,
    )
    run_manifest = _bound_json(
        root,
        root / "review/phase3/wp3-1-materialization-candidate-v5/run-manifest.json",
        RUN_MANIFEST_SHA256,
    )
    if static.get("model") != BACKBONE or run_manifest.get("static_v2_sha256") != STATIC_V2_SHA256:
        raise Phase3EvalError("approved static-v2 and run manifest do not bind each other")
    runtime_contract = static.get("runtime_contract")
    pricing_contract = (
        runtime_contract.get("pricing_usd") if isinstance(runtime_contract, Mapping) else None
    )
    if not isinstance(pricing_contract, Mapping):
        raise Phase3EvalError("approved static-v2 has no pricing contract")
    input_rate = float(pricing_contract.get("uncached_prefill_per_million_tokens", -1))
    output_rate = float(pricing_contract.get("sample_output_per_million_tokens", -1))
    if input_rate != 0.54 or output_rate != 1.335:
        raise Phase3EvalError("approved sampling pricing drifted")
    tokenizer = load_pinned_tokenizer(root, tokenizer_directory)
    states = await rebuild_dev_states(root, tokenizer)
    fast = select_fast_sentinels(states)
    canary = select_canary_sentinels(fast)
    rubrics = build_open_text_rubrics(states)
    if len(fast) != 11 or tuple(state.state_id for state in canary) != FROZEN_CANARY_STATE_IDS:
        raise Phase3EvalError("frozen fast or canary sentinel selection drifted")
    if (
        len([state for state in states if state.action_type != "idle"])
        != FROZEN_POSITIVE_ACTION_DENOMINATOR
    ):
        raise Phase3EvalError("frozen full-payload positive denominator drifted")
    action_counts = Counter(state.action_type for state in states)
    small_slice_ids = {
        action: [state.state_id for state in states if state.action_type == action]
        for action, count in action_counts.items()
        if count < 10
    }
    if small_slice_ids != {"cancel": list(FROZEN_SMALL_SLICE_IDS)}:
        raise Phase3EvalError("frozen small action slice identities drifted")
    retention = _retention_template(root, tokenizer, blinding_nonce=blinding_nonce)
    inventory = [state.inventory_row() for state in states]
    if set(SENTINEL_TAG_RULES) != REQUIRED_SENTINEL_TAGS:
        raise Phase3EvalError("sentinel tag rules do not close over the frozen universe")
    tag_vectors = [
        {"coverage_tags": row["coverage_tags"], "state_id": row["state_id"]} for row in inventory
    ]
    fast_manifest = {
        "candidate_tag_vector_count": len(tag_vectors),
        "candidate_tag_vectors_sha256": (
            f"sha256:{sha256(canonical_artifact_bytes(tag_vectors)).hexdigest()}"
        ),
        "canary_state_ids": [state.state_id for state in canary],
        "coverage_tags": sorted(set().union(*(sentinel_tags(state) for state in fast))),
        "format_version": 1,
        "kind": "phase3-wp3-2-fast-sentinel-manifest",
        "minimality_lower_bound": len(ACTION_TYPES),
        "minimality_proof": "exact_bitmask_dp_over_all_distinct_authenticated_tag_vectors",
        "required_coverage_tags": sorted(REQUIRED_SENTINEL_TAGS),
        "tag_rules": SENTINEL_TAG_RULES,
        "selection_rule": "exact_minimum_set_cover_then_shortest_tokens_then_state_id",
        "expected_fast_sentinel_count": 11,
        "frozen_canary_state_ids": list(FROZEN_CANARY_STATE_IDS),
        "sentinels": [_sentinel_row(state) for state in fast],
    }
    requests = [
        {
            "input_token_count": len(state.input_tokens),
            "input_token_ids": list(state.input_tokens),
            "input_token_ids_sha256": _token_digest(state.input_tokens),
            "kind": "interaction_dev",
            "messages": [dict(message) for message in state.messages],
            "messages_sha256": "sha256:"
            + sha256(canonical_artifact_bytes(list(state.messages))).hexdigest(),
            "request_id": state.state_id,
        }
        for state in states
    ] + retention["requests"]
    input_tokens = sum(int(row["input_token_count"]) for row in requests)
    output_ceiling = len(requests) * int(SAMPLING["max_tokens"])
    request_bytes = canonical_artifact_bytes(requests)
    pricing = {
        "bound_input_usd_per_million": input_rate,
        "bound_output_usd_per_million": output_rate,
        "input_token_count": input_tokens,
        "max_output_token_count": output_ceiling,
        "static_v2_sha256": STATIC_V2_SHA256,
    }
    pricing["modeled_upper_usd"] = (
        input_tokens / 1_000_000 * input_rate + output_ceiling / 1_000_000 * output_rate
    )
    pricing["authorization_ceiling_usd"] = (
        math.ceil(float(pricing["modeled_upper_usd"]) * 125) / 100
    )
    sampling_manifest = {
        "authorization": {
            "checkpoint_creation_authorized": False,
            "paid_call_authorized": False,
            "provider_spend_authorized": False,
            "secret_access_authorized": False,
            "sealed_test_access_authorized": False,
        },
        "format_version": 1,
        "kind": "phase3-wp3-2-backbone-sampling-request",
        "model": BACKBONE,
        "pricing_projection": pricing,
        "request_count": len(requests),
        "request_serialization": "canonical_json_array_utf8",
        "requests_file": "sampling-requests.json.gz",
        "requests_sha256": f"sha256:{sha256(request_bytes).hexdigest()}",
        "retention_prompt_rule": "all_source_messages_except_final_assistant_reference",
        "retention_count": len(retention["requests"]),
        "sampling": SAMPLING,
        "dev_count": len(states),
    }
    sampling_manifest_bytes = canonical_artifact_bytes(sampling_manifest)
    _assert_frozen_sampling_payloads(request_bytes, sampling_manifest_bytes)
    grader_contract = {
        "d10_gates": {
            "active_floor_denominator": FROZEN_ACTIVE_FLOOR_DENOMINATOR,
            "active_floor_respond_rate_max": 0.05,
            "duplicate_delegate_schedule_opportunity_rate_max": 0.10,
            "forbidden_error_count_max": 0,
            "forbidden_error_classes": [
                "cancel_target_mismatch",
                "fire_not_open",
                "hidden_thinking",
                "nudge_target_mismatch",
                "reference_integrity",
                "result_not_ready",
                "rollover_violation",
                "span_mismatch",
                "timer_interval_message_mismatch",
                "timer_not_active",
                "unknown_reference",
                "wrong_causal_result",
            ],
            "parse_union_validity_min": 0.98,
            "positive_action_denominator": FROZEN_POSITIVE_ACTION_DENOMINATOR,
            "positive_action_micro_accuracy_min": 0.90,
            "small_slice_state_ids": {"cancel": list(FROZEN_SMALL_SLICE_IDS)},
            "small_slice_under_10_max_errors": 1,
        },
        "d13_score": "sequence_success - 5*intrusive - 3*duplicate - 5*provenance",
        "format_version": 1,
        "kind": "phase3-wp3-2-grader-contract",
        "open_text": {
            "human_assessment": (
                "state_id + rubric_sha256 + raw output bytes sha256 + frozen reason codes; "
                "no LLM or heuristic scorer"
            ),
            "integrate_count": 18,
            "respond_count": 14,
            "rows": [rubric.as_json_object() for rubric in rubrics],
            "version": OPEN_TEXT_RUBRIC_VERSION,
        },
        "baseline_failures": (
            "report failed raw generations; never abort, suppress, repair, or resample"
        ),
        "raw_first": "persist token ids and decoded bytes before parse; no repair or parse retry",
    }
    report = {
        "authorization_status": "offline_only_no_paid_call",
        "canary_sentinel_count": len(canary),
        "dev_action_counts": dict(sorted(Counter(state.action_type for state in states).items())),
        "dev_state_count": len(states),
        "dev_stream_count": len({state.stream_sha256 for state in states}),
        "fast_sentinel_count": len(fast),
        "format_version": 1,
        "kind": "phase3-wp3-2-offline-report",
        "maximum_dev_input_tokens": max(len(state.input_tokens) for state in states),
        "provider_calls": 0,
        "grader": {
            "active_floor_denominator": FROZEN_ACTIVE_FLOOR_DENOMINATOR,
            "open_text_integrate_count": 18,
            "open_text_respond_count": 14,
            "open_text_rubric_version": OPEN_TEXT_RUBRIC_VERSION,
            "positive_action_denominator": FROZEN_POSITIVE_ACTION_DENOMINATOR,
        },
        "sampling_execution_plan": {
            "await_first_manifested_interaction_before_concurrency": True,
            "first_request_id": str(requests[0]["request_id"]),
            "interaction_then_retention": True,
            "memoize_duplicate_prompts": False,
            "one_base_model_sampling_client": True,
            "outer_retry": False,
            "physical_request_count": len(requests),
            "record_cache_evidence": [
                "prompt_cache_hit_tokens_per_response",
                "billing_usage_when_available",
            ],
        },
        "rebuild_compatibility": {
            "g7-rollover-a": {
                "explicit_lookup_request": False,
                "reason": "reproduce_exact_frozen_phase2_stream_and_runtime_view",
                "sidecar_sha256": FROZEN_ROLLOVER_A_SIDECAR_SHA256,
                "stream_sha256": FROZEN_ROLLOVER_A_STREAM_SHA256,
            }
        },
        "retention_count": len(retention["requests"]),
        "sealed_test": {"path_argument_present": False, "status": "unread"},
        "source_commit": source_commit,
    }
    fixture_report = _gold_fixture_report(states, tokenizer)
    files = {
        "dev-state-inventory.jsonl.gz": _gzip_jsonl(inventory),
        "fast-sentinel-manifest.json": canonical_artifact_bytes(fast_manifest),
        "grader-contract.json": canonical_artifact_bytes(grader_contract),
        "grader-fixture-report.json": canonical_artifact_bytes(fixture_report),
        "retention-blind-template.json": canonical_artifact_bytes(retention["template"]),
        "sampling-requests.json.gz": gzip.compress(request_bytes, compresslevel=9, mtime=0),
        "sampling-request-manifest.json": sampling_manifest_bytes,
        "wp3-2-offline-report.json": canonical_artifact_bytes(report),
    }
    bindings = {
        "dev_evidence_sha256": DEV_EVIDENCE_SHA256,
        "format_version": 1,
        "kind": "phase3-wp3-2-artifact-bindings",
        "run_manifest_sha256": RUN_MANIFEST_SHA256,
        "retention_blind_identity_map_sha256": (
            "sha256:" + sha256(canonical_artifact_bytes(retention["identity_map"])).hexdigest()
        ),
        "sealed_test": {"path": SEALED_TEST_RELATIVE_PATH.as_posix(), "status": "unread"},
        "source_commit": source_commit,
        "static_v2_sha256": STATIC_V2_SHA256,
        **{
            name.replace(".", "_") + "_sha256": f"sha256:{sha256(data).hexdigest()}"
            for name, data in files.items()
        },
    }
    files["artifact-bindings.json"] = canonical_artifact_bytes(bindings)
    files["SHA256SUMS"] = _sha256sums(files)
    return files, canonical_artifact_bytes(retention["identity_map"])


async def materialize_offline_candidate(
    output: Path,
    owner_map_output: Path,
    *,
    repository_root: Path,
    tokenizer_directory: Path,
    source_commit: str,
) -> dict[str, bytes]:
    files, identity_map = await build_offline_candidate(
        repository_root=repository_root,
        tokenizer_directory=tokenizer_directory,
        source_commit=source_commit,
        blinding_nonce=token_hex(32),
    )
    owner_files = {"retention-blind-identity-map.json": identity_map}
    owner_files["SHA256SUMS"] = _sha256sums(owner_files)
    publish_directory_transaction(guard_read_path(repository_root, owner_map_output), owner_files)
    publish_directory_transaction(guard_read_path(repository_root, output), files)
    return files


def _retention_template(
    root: Path, tokenizer: PinnedTokenizer, *, blinding_nonce: str
) -> dict[str, object]:
    if not re.fullmatch(r"[0-9a-f]{64}", blinding_nonce):
        raise Phase3EvalError("retention blinding nonce is malformed")
    path = root / "review/phase3/wp3-0-static-contract/retention-owner-packet.json"
    raw = _read_bytes(root, path)
    if f"sha256:{sha256(raw).hexdigest()}" != RETENTION_PACKET_SHA256:
        raise Phase3EvalError("approved retention packet drifted")
    packet = _json(raw)
    rows = packet.get("rows")
    if packet.get("owner_approved") is not True or not isinstance(rows, list) or len(rows) != 60:
        raise Phase3EvalError("retention packet is not the approved 60-row roster")
    backbone_slots = _counterbalanced_retention_slots(rows, blinding_nonce)
    requests = []
    template_rows = []
    assignments = []
    for row in rows:
        if not isinstance(row, Mapping) or row.get("owner_approved") is not True:
            raise Phase3EvalError("retention row is not owner approved")
        messages = row.get("messages")
        if (
            not isinstance(messages, list)
            or len(messages) < 2
            or messages[-1].get("role") != "assistant"
        ):
            raise Phase3EvalError("retention row conversation is malformed")
        prompt = [dict(message) for message in messages[:-1]]
        tokens = _generation_prefix_tokens(tokenizer, prompt)
        prompt_id = str(row.get("prompt_id"))
        request_id = f"retention:{prompt_id}"
        backbone_slot = backbone_slots[prompt_id]
        checkpoint_slot = "B" if backbone_slot == "A" else "A"
        requests.append(
            {
                "input_token_count": len(tokens),
                "input_token_ids": list(tokens),
                "input_token_ids_sha256": _token_digest(tokens),
                "kind": "retention",
                "messages": prompt,
                "messages_sha256": f"sha256:{sha256(canonical_artifact_bytes(prompt)).hexdigest()}",
                "request_id": request_id,
            }
        )
        template_rows.append(
            {
                "capability_group": row.get("capability_group"),
                "comparison_id": "cmp-" + sha256(prompt_id.encode()).hexdigest()[:20],
                "prompt_id": prompt_id,
                "reference_answer_sha256": "sha256:"
                + sha256(str(row.get("reference_answer")).encode()).hexdigest(),
                "request_id": request_id,
                "review_status": "blinded_pending_sampling",
                "slots": {
                    "A": {"output_sha256": None, "raw_output_ref": None},
                    "B": {"output_sha256": None, "raw_output_ref": None},
                },
                "verdict": None,
            }
        )
        assignments.append(
            {
                "backbone_slot": backbone_slot,
                "checkpoint_identity": "pending_wp3_5_selection",
                "checkpoint_slot": checkpoint_slot,
                "prompt_id": prompt_id,
            }
        )
    identity_map = {
        "assignments": assignments,
        "assignment_rule": "deterministic_nonce_rank_5_5_within_capability_group",
        "format_version": 1,
        "kind": "phase3-wp3-2-retention-blind-identity-map",
        "owner_only": True,
        "reviewer_packet_allowed": False,
        "shuffle_nonce": blinding_nonce,
    }
    return {
        "requests": requests,
        "identity_map": identity_map,
        "template": {
            "assignment_rule": "deterministic_nonce_rank_5_5_within_capability_group",
            "format_version": 1,
            "identity_map_sha256": (
                f"sha256:{sha256(canonical_artifact_bytes(identity_map)).hexdigest()}"
            ),
            "kind": "phase3-wp3-2-retention-blind-template",
            "rubric": ["A_better", "tie", "B_better"],
            "rows": template_rows,
            "source_packet_sha256": RETENTION_PACKET_SHA256,
        },
    }


def _counterbalanced_retention_slots(rows: Sequence[object], blinding_nonce: str) -> dict[str, str]:
    """Assign backbone A/B exactly 5/5 inside each frozen ten-row capability group."""
    groups: dict[str, list[str]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            raise Phase3EvalError("retention row is malformed")
        group = row.get("capability_group")
        prompt_id = row.get("prompt_id")
        if not isinstance(group, str) or not isinstance(prompt_id, str):
            raise Phase3EvalError("retention row lacks group or prompt identity")
        groups.setdefault(group, []).append(prompt_id)
    if len(groups) != 6 or any(len(prompt_ids) != 10 for prompt_ids in groups.values()):
        raise Phase3EvalError("retention capability groups are not six-by-ten")
    if len({prompt_id for prompt_ids in groups.values() for prompt_id in prompt_ids}) != 60:
        raise Phase3EvalError("retention prompt identities repeat")
    slots: dict[str, str] = {}
    for group, prompt_ids in sorted(groups.items()):
        ranked = sorted(
            prompt_ids,
            key=lambda prompt_id: (
                sha256(f"{blinding_nonce}\x00{group}\x00{prompt_id}".encode()).digest(),
                prompt_id,
            ),
        )
        slots.update(
            {prompt_id: "A" if index < 5 else "B" for index, prompt_id in enumerate(ranked)}
        )
    return slots


def _gold_fixture_report(
    states: Sequence[DevEvalState], tokenizer: PinnedTokenizer
) -> dict[str, object]:
    rubrics = _rubric_index(states)
    rows = []
    for state in states:
        raw_bytes = canonical_artifact_bytes(state.expected.model_dump(mode="json"))
        raw = capture_raw_generation(
            evaluation_run_id="offline-gold-fixtures",
            model_identity=BACKBONE,
            checkpoint_identity="frozen-dev-gold",
            sampling_manifest_sha256="sha256:" + "0" * 64,
            state_id=state.state_id,
            output_token_ids=_literal_tokens(tokenizer, raw_bytes.decode("utf-8")),
            decoded_bytes=raw_bytes,
            finish_reason="stop",
        )
        rubric = rubrics.get(state.state_id)
        grade = _grade_raw_generation(state, raw)
        rows.append(
            {
                "action_type": state.action_type,
                "license_block_codes": _nested(grade, "structural", "license_block_codes"),
                "licensed": _nested(grade, "structural", "licensed"),
                "oracle_valid": _nested(grade, "executed", "oracle_valid"),
                "human_assessment": None,
                "rubric_sha256": None
                if rubric is None
                else rubric.as_json_object()["rubric_sha256"],
                "semantic_status": _nested(grade, "executed", "semantic_status"),
                "state_id": state.state_id,
                "structural_pass": _nested(grade, "structural", "structural_pass"),
            }
        )
    failed = [row["state_id"] for row in rows if row["structural_pass"] is not True]
    pending = [
        row["state_id"] for row in rows if row["semantic_status"] == "pending_semantic_assessment"
    ]
    if (
        failed
        or len(pending) != len(rubrics)
        or len(rubrics) != sum(state.action_type in {"integrate", "respond"} for state in states)
    ):
        raise Phase3EvalError("gold grader fixtures do not reproduce frozen expectations")
    return {
        "fixture_count": len(rows),
        "format_version": 1,
        "kind": "phase3-wp3-2-grader-fixture-report",
        "open_text_assessment_count": 0,
        "open_text_pending_count": len(pending),
        "open_text_status": "pending_human_assessment",
        "open_text_rubric_version": OPEN_TEXT_RUBRIC_VERSION,
        "negative_mutations": _negative_mutation_fixture_report(states),
        "rubrics": [rubric.as_json_object() for rubric in rubrics.values()],
        "rows": rows,
        "structural_pass_count": len(rows),
    }


def _negative_mutation_fixture_report(states: Sequence[DevEvalState]) -> dict[str, object]:
    """Small production negatives plus fixture-declared (not human) semantic cases."""

    def pick(label: str, predicate: object) -> DevEvalState:
        selected = next((state for state in states if predicate(state)), None)  # type: ignore[operator]
        if selected is None:
            raise Phase3EvalError(f"missing frozen negative fixture source: {label}")
        return selected

    def production(
        name: str,
        state: DevEvalState,
        value: Mapping[str, object] | bytes,
        *,
        parse_invalid: bool = False,
        license_codes: tuple[LicenseBlockCode, ...] = (),
        hard_failures: tuple[str, ...] = (),
        exact_hard_failures: bool = False,
        intrusive: bool = False,
    ) -> dict[str, object]:
        raw_bytes = value if isinstance(value, bytes) else canonical_artifact_bytes(value)
        raw = capture_raw_generation(
            evaluation_run_id="offline-negative-fixtures",
            model_identity=BACKBONE,
            checkpoint_identity="frozen-dev-negative",
            sampling_manifest_sha256="sha256:" + "1" * 64,
            state_id=state.state_id,
            output_token_ids=(),
            decoded_bytes=raw_bytes,
            finish_reason="stop",
        )
        grade = _grade_raw_generation(state, raw)
        if _nested(grade, "executed", "match") is True:
            raise Phase3EvalError(f"negative mutation was accepted: {name}")
        parsed = _nested(grade, "structural", "parse_union_valid")
        observed_codes = set(_nested(grade, "structural", "license_block_codes") or ())
        observed_hard = set(_nested(grade, "executed", "hard_failures") or ())
        if parse_invalid != (parsed is False):
            raise Phase3EvalError(f"negative mutation has wrong parse outcome: {name}")
        if not {code.value for code in license_codes}.issubset(observed_codes):
            raise Phase3EvalError(f"negative mutation missed licensed rejection: {name}")
        if not set(hard_failures).issubset(observed_hard):
            raise Phase3EvalError(f"negative mutation missed hard rejection: {name}")
        if exact_hard_failures and observed_hard != set(hard_failures):
            raise Phase3EvalError(f"negative mutation has extra hard rejection: {name}")
        if intrusive and _nested(grade, "executed", "intrusive_action") is not True:
            raise Phase3EvalError(
                f"negative mutation missed intrusive active-floor response: {name}"
            )
        raw_record = raw.as_json_object()
        return {
            "candidate_action": None if isinstance(value, bytes) else dict(value),
            "check": "production",
            "hard_failures": _nested(grade, "executed", "hard_failures"),
            "license_block_codes": _nested(grade, "structural", "license_block_codes"),
            "name": name,
            "required_rejection": {
                "hard_failures": list(hard_failures),
                "exact_hard_failures": exact_hard_failures,
                "license_block_codes": [code.value for code in license_codes],
                "parse_invalid": parse_invalid,
                "intrusive_action": intrusive,
            },
            "observed_rejection_codes": {
                "hard_failures": _nested(grade, "executed", "hard_failures"),
                "license_block_codes": _nested(grade, "structural", "license_block_codes"),
                "parse_error": _nested(grade, "structural", "parse_error"),
            },
            "output_bytes_sha256": raw_record["output_bytes_sha256"],
            "parse_error": _nested(grade, "structural", "parse_error"),
            "raw_utf8": raw_bytes.decode("utf-8"),
            "rejected": True,
            "state_id": state.state_id,
        }

    def semantic(name: str, state: DevEvalState, text: str, reason_code: str) -> dict[str, object]:
        if not isinstance(state.expected, IntegrateAction | RespondAction):
            raise Phase3EvalError("semantic negative requires an open-text action")
        payload = state.expected.model_dump(mode="json")
        payload["text"] = text
        raw_bytes = canonical_artifact_bytes(payload)
        rubric = _open_text_rubric(state)
        raw = capture_raw_generation(
            evaluation_run_id="offline-negative-fixtures",
            model_identity=BACKBONE,
            checkpoint_identity="frozen-dev-negative",
            sampling_manifest_sha256="sha256:" + "1" * 64,
            state_id=state.state_id,
            output_token_ids=(),
            decoded_bytes=raw_bytes,
            finish_reason="stop",
        )
        assessment = FrozenHumanAssessment(
            state_id=state.state_id,
            rubric_sha256=str(rubric.as_json_object()["rubric_sha256"]),
            output_bytes_sha256=str(raw.as_json_object()["output_bytes_sha256"]),
            passed=False,
            reason_codes=(reason_code,),
        )
        grade = _grade_raw_generation(state, raw, semantic_assessment=assessment)
        if _nested(grade, "executed", "match") is True:
            raise Phase3EvalError(f"semantic negative mutation was accepted: {name}")
        if _nested(grade, "executed", "semantic_status") != "failed":
            raise Phase3EvalError(
                f"fixture-declared semantic mutation did not reach grader: {name}"
            )
        return {
            "fixture_declared_assessment": {
                "output_bytes_sha256": assessment.output_bytes_sha256,
                "passed": False,
                "reason_codes": list(assessment.reason_codes),
                "rubric_sha256": assessment.rubric_sha256,
            },
            "assessment_provenance": "fixture_declared_not_human",
            "check": "fixture_declared_semantic",
            "candidate_action": payload,
            "mutated_text": text,
            "name": name,
            "observed_rejection_codes": {
                "reason_codes": list(assessment.reason_codes),
                "semantic_status": _nested(grade, "executed", "semantic_status"),
            },
            "rejected": True,
            "state_id": state.state_id,
        }

    base = states[0]
    integrate = pick("integrate", lambda state: isinstance(state.expected, IntegrateAction))
    mark = pick("mark", lambda state: state.action_type == "mark")
    schedule = pick("schedule", lambda state: isinstance(state.expected, ScheduleAction))
    cancel = pick("cancel", lambda state: isinstance(state.expected, CancelAction))
    non_ready = pick(
        "non-ready-result",
        lambda state: (
            isinstance(state.expected, IntegrateAction)
            and any(
                isinstance(event, ToolResultView)
                and (not event.completed or event.status is not ToolResultStatus.SUCCEEDED)
                for event in state.boundary.license_view.events
            )
        ),
    )
    wrong_result = pick(
        "wrong-result",
        lambda state: (
            isinstance(state.expected, IntegrateAction) and _wrong_causal_candidates(state)
        ),
    )
    handled_nudge = pick(
        "handled-nudge",
        lambda state: any(
            isinstance(event, TimerFireView) and event.disposition is not Disposition.OPEN
            for event in state.boundary.license_view.events
        ),
    )
    inactive_nudge = pick(
        "inactive-nudge",
        lambda state: (
            any(
                timer.status is not TimerStatus.ACTIVE
                for timer in state.boundary.license_view.timers
            )
            and any(
                isinstance(event, TimerFireView) for event in state.boundary.license_view.events
            )
        ),
    )
    unknown_reference = integrate.expected.model_dump(mode="json")
    unknown_reference["result_event_id"] = "e_999999"
    span_mismatch = mark.expected.model_dump(mode="json")
    target = span_mismatch["target"]
    if not isinstance(target, dict):  # pragma: no cover - action schema closes this
        raise Phase3EvalError("mark fixture target is malformed")
    target["text"] = "x" * (int(target["end_utf16"]) - int(target["start_utf16"]))
    wrong_result_payload = _wrong_causal_candidates(wrong_result)[0].model_dump(mode="json")
    non_ready_event = next(
        event
        for event in non_ready.boundary.license_view.events
        if isinstance(event, ToolResultView)
        and (not event.completed or event.status is not ToolResultStatus.SUCCEEDED)
    )
    non_ready_payload = non_ready.expected.model_dump(mode="json")
    non_ready_payload["result_event_id"] = non_ready_event.event_id
    timer_payload = schedule.expected.model_dump(mode="json")
    timer_payload["interval_ms"] = int(timer_payload["interval_ms"]) + 1
    timer_payload["message"] = str(timer_payload["message"]) + " again"
    cancel_payload = cancel.expected.model_dump(mode="json")
    if cancel_payload["target"] != {"kind": "all_active"}:
        cancel_payload["target"] = {"kind": "all_active"}
    else:
        timer = next(iter(cancel.boundary.license_view.active_timers), None)
        if timer is None:
            raise Phase3EvalError("cancel negative has no alternative active timer")
        cancel_payload["target"] = {"kind": "timer", "timer_id": timer.timer_id}
    handled_fire = next(
        event
        for event in handled_nudge.boundary.license_view.events
        if isinstance(event, TimerFireView) and event.disposition is not Disposition.OPEN
    )
    inactive_timer_ids = {
        timer.timer_id
        for timer in inactive_nudge.boundary.license_view.timers
        if timer.status is not TimerStatus.ACTIVE
    }
    inactive_fire = next(
        event
        for event in inactive_nudge.boundary.license_view.events
        if isinstance(event, TimerFireView) and event.timer_id in inactive_timer_ids
    )
    active_floor = _active_floor_states(states)[0]
    snapshot = active_floor.boundary.license_view.latest_snapshot
    if snapshot is None:
        raise Phase3EvalError("active-floor negative has no reply target")
    delegate_duplicate = _duplicate_mutation_action(states, "duplicate_delegate")
    schedule_duplicate = _duplicate_mutation_action(states, "duplicate_schedule")
    objective_rows = [
        production("malformed", base, b"{", parse_invalid=True),
        production("unknown_action", base, {"type": "unknown"}, parse_invalid=True),
        production(
            "unknown_reference",
            integrate,
            unknown_reference,
            license_codes=(LicenseBlockCode.UNKNOWN_REFERENCE,),
            hard_failures=("unknown_reference",),
        ),
        production(
            "span_mismatch",
            mark,
            span_mismatch,
            license_codes=(LicenseBlockCode.SPAN_MISMATCH,),
            hard_failures=("span_mismatch",),
        ),
        production(
            "wrong_result",
            wrong_result,
            wrong_result_payload,
            hard_failures=("wrong_causal_result",),
        ),
        production(
            "non_ready_result",
            non_ready,
            non_ready_payload,
            license_codes=(LicenseBlockCode.RESULT_NOT_READY,),
            hard_failures=("result_not_ready",),
        ),
        production(
            "wrong_timer_interval_message",
            schedule,
            timer_payload,
            hard_failures=("timer_interval_message_mismatch",),
            exact_hard_failures=True,
        ),
        production(
            "wrong_cancel_target",
            cancel,
            cancel_payload,
            hard_failures=("cancel_target_mismatch",),
            exact_hard_failures=True,
        ),
        production(
            "handled_nudge",
            handled_nudge,
            {"type": "nudge", "fire_event_id": handled_fire.event_id},
            license_codes=(LicenseBlockCode.FIRE_NOT_OPEN,),
            hard_failures=("fire_not_open",),
        ),
        production(
            "inactive_nudge",
            inactive_nudge,
            {"type": "nudge", "fire_event_id": inactive_fire.event_id},
            license_codes=(LicenseBlockCode.TIMER_NOT_ACTIVE,),
            hard_failures=("timer_not_active",),
        ),
        production(
            "active_floor_respond",
            active_floor,
            {"type": "respond", "reply_to_event_id": snapshot.event_id, "text": "x"},
            license_codes=(LicenseBlockCode.FLOOR_OWNED,),
            intrusive=True,
        ),
        production(
            "duplicate_delegate",
            delegate_duplicate[0],
            delegate_duplicate[1],
            license_codes=(LicenseBlockCode.DUPLICATE_TOOL_REQUEST,),
        ),
        production(
            "duplicate_schedule",
            schedule_duplicate[0],
            schedule_duplicate[1],
            license_codes=(LicenseBlockCode.DUPLICATE_SCHEDULE,),
        ),
    ]
    return {
        "objective": objective_rows,
        "semantic": [
            semantic(
                "unsupported_claim",
                integrate,
                "The result includes an unsupported seventh shell.",
                "unsupported_claim",
            ),
            semantic("missing_required_fact", integrate, "", "missing_required_fact"),
        ],
    }


def _duplicate_mutation_action(
    states: Sequence[DevEvalState], opportunity: str
) -> tuple[DevEvalState, dict[str, object]]:
    code = (
        LicenseBlockCode.DUPLICATE_TOOL_REQUEST
        if opportunity == "duplicate_delegate"
        else LicenseBlockCode.DUPLICATE_SCHEDULE
    )
    action_type = "delegate" if opportunity == "duplicate_delegate" else "schedule"
    actions = [state.expected for state in states if state.action_type == action_type]
    for state in states:
        if opportunity not in _duplicate_mechanics_opportunities(state):
            continue
        for action in actions:
            if code in blocking_codes(action, state.boundary.license_view):
                return state, action.model_dump(mode="json")
    raise Phase3EvalError(f"missing authenticated {opportunity} mutation")


async def _frozen_rollover_a(
    root: Path, registry: AssetRegistry, directory: Path
) -> GeneratedScenario:
    """Reproduce the one repaired DEV parent whose frozen flag differs from the helper."""
    entries = await build_g7_rollover_checkpoint_catalog(
        registry,
        directory=directory,
        repository_root=root,
        split=Split.DEV,
        template_id="a_4a403aaa78fb587f5ca4d4d0",
        rollover_lookup_asset_id="a_2c90afbdb043178f1b9c6f00",
        stale_lookup_asset_id="a_8bb0112712dae80287d2d014",
        mark_asset_id="a_c8e980d7f52144f826f11b9c",
        first_timer_asset_id="a_f2abae3f71742fb32ac2dbf7",
        recurring_timer_asset_id="a_eace0b11d0909880600e2ee0",
        shape_ids=("g7-checkpoint-rollover-a",),
        prompt_template="prompt-template-v4.txt",
        master_seed="wp2-8-dev-gold-v1:rollover",
        explicit_lookup_request=False,
    )
    if len(entries) != 1:
        raise Phase3EvalError("frozen rollover-A rebuild did not return exactly one parent")
    parent = entries[0].parent
    if (
        parent.stream.sha256 != FROZEN_ROLLOVER_A_STREAM_SHA256
        or parent.sidecar.sha256 != FROZEN_ROLLOVER_A_SIDECAR_SHA256
    ):
        raise Phase3EvalError("frozen rollover-A compatibility rebuild drifted")
    return parent


def _sentinel_row(state: DevEvalState) -> dict[str, object]:
    return {
        "action_type": state.action_type,
        "coverage_tags": sorted(sentinel_tags(state)),
        "input_token_count": len(state.input_tokens),
        "input_token_ids_sha256": _token_digest(state.input_tokens),
        "state_id": state.state_id,
    }


def _cover_score(states: Sequence[DevEvalState]) -> tuple[int, int, tuple[str, ...]]:
    return (
        len(states),
        sum(len(state.input_tokens) for state in states),
        tuple(state.state_id for state in states),
    )


def _has_duplicate_schedule_probe(state: DevEvalState) -> bool:
    return bool(_duplicate_schedule_timer_ids(state))


def _duplicate_mechanics_opportunities(state: DevEvalState) -> tuple[str, ...]:
    """Authenticated negative opportunities, counted by route rather than by all DEV rows."""
    if not isinstance(state.expected, IdleAction):
        return ()
    opportunities = []
    if state.boundary.license_view.pending_tool_requests:
        opportunities.append("duplicate_delegate")
    if _has_duplicate_schedule_probe(state):
        opportunities.append("duplicate_schedule")
    return tuple(opportunities)


def _duplicate_schedule_timer_ids(state: DevEvalState) -> tuple[str, ...]:
    matches = []
    for timer in state.boundary.license_view.active_timers:
        instruction = timer.current_instruction or timer.instruction
        if instruction is None or timer.interval_ms is None or timer.message is None:
            continue
        probe = ScheduleAction(
            type="schedule",
            instruction=instruction,
            interval_ms=timer.interval_ms,
            message=timer.message,
        )
        if LicenseBlockCode.DUPLICATE_SCHEDULE in blocking_codes(
            probe, state.boundary.license_view
        ):
            matches.append(timer.timer_id)
    return tuple(sorted(matches))


def _causal_failure(expected: Action, actual: Action) -> str | None:
    """Classify only exact same-route causal-subject mismatches."""
    if type(expected) is not type(actual):
        return None
    fields = {
        DelegateAction: ("fact",),
        IntegrateAction: ("result_event_id",),
        NudgeAction: ("fire_event_id",),
        RespondAction: ("reply_to_event_id",),
        SkipAction: ("target_event_id", "reason"),
    }.get(type(expected))
    if fields is None:
        return None
    return next(
        (
            f"{expected.type}_{field}_mismatch"
            for field in fields
            if getattr(expected, field) != getattr(actual, field)
        ),
        None,
    )


def _has_wrong_causal_probe(state: DevEvalState) -> bool:
    """Require an authenticated alternative causal subject at this boundary."""
    return bool(_wrong_causal_candidates(state))


def _wrong_causal_candidates(state: DevEvalState) -> tuple[Action, ...]:
    expected = state.expected
    events = state.boundary.license_view.events
    candidates: Iterable[Action]
    if isinstance(expected, IntegrateAction):
        candidates = (
            expected.model_copy(update={"result_event_id": event.event_id})
            for event in events
            if isinstance(event, ToolResultView)
        )
    elif isinstance(expected, NudgeAction):
        candidates = (
            expected.model_copy(update={"fire_event_id": event.event_id})
            for event in events
            if isinstance(event, TimerFireView)
        )
    elif isinstance(expected, RespondAction):
        candidates = (
            expected.model_copy(update={"reply_to_event_id": event.event_id})
            for event in events
            if isinstance(event, SnapshotView | ToolResultView)
        )
    elif isinstance(expected, SkipAction):
        candidates = (
            expected.model_copy(update={"target_event_id": event.event_id})
            for event in events
            if isinstance(event, TimerFireView | ToolResultView)
        )
    else:
        candidates = state.evidence.future_actions
    return tuple(
        candidate for candidate in candidates if _causal_failure(expected, candidate) is not None
    )


def _hard_failures(
    state: DevEvalState,
    parsed: Action | None,
    raw: Mapping[str, object],
    codes: Sequence[LicenseBlockCode],
    *,
    wrong_causal_result: bool,
    reference_integrity: bool,
    structure: GenerationStructureGrade | None,
) -> list[str]:
    failures = {code.value for code in codes if code in HARD_PROVENANCE_CODES}
    if raw.get("hidden_thinking") is True:
        failures.add("hidden_thinking")
    if wrong_causal_result:
        failures.add("wrong_causal_result")
    if (
        parsed is not None
        and isinstance(parsed, ScheduleAction)
        and isinstance(state.expected, ScheduleAction)
    ):
        if (parsed.interval_ms, parsed.message) != (
            state.expected.interval_ms,
            state.expected.message,
        ):
            failures.add("timer_interval_message_mismatch")
    if (
        parsed is not None
        and isinstance(parsed, CancelAction)
        and isinstance(state.expected, CancelAction)
    ):
        if parsed.target != state.expected.target:
            failures.add("cancel_target_mismatch")
    if (
        parsed is not None
        and isinstance(parsed, NudgeAction)
        and isinstance(state.expected, NudgeAction)
    ):
        if parsed.fire_event_id != state.expected.fire_event_id:
            failures.add("nudge_target_mismatch")
    if not reference_integrity and parsed is not None:
        failures.add("reference_integrity")
    if state.rollover and (
        structure is None or not structure.structural_match or not reference_integrity
    ):
        failures.add("rollover_violation")
    return sorted(failures)


def _nested(value: Mapping[str, object], first: str, second: str) -> object:
    node = value.get(first)
    return node.get(second) if isinstance(node, Mapping) else None


def _json(raw: bytes) -> Mapping[str, object]:
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise Phase3EvalError("bound JSON artifact is malformed") from error
    if not isinstance(value, Mapping):
        raise Phase3EvalError("bound JSON artifact is not an object")
    return value


def _bound_json(root: Path, path: Path, expected_sha256: str) -> Mapping[str, object]:
    raw = _read_bytes(root, path)
    if f"sha256:{sha256(raw).hexdigest()}" != expected_sha256:
        raise Phase3EvalError(f"approved artifact drifted: {path.name}")
    return _json(raw)


def _load_persisted_raw(repository_root: Path, persisted: PersistedRawGeneration) -> RawGeneration:
    raw_bytes = _read_bytes(repository_root, persisted.path)
    if f"sha256:{sha256(raw_bytes).hexdigest()}" != persisted.sha256:
        raise Phase3EvalError("persisted raw generation digest drifted")
    value = _json(raw_bytes)
    if canonical_artifact_bytes(value) != raw_bytes or value.get("kind") != (
        "phase3-wp3-2-raw-generation"
    ):
        raise Phase3EvalError("persisted raw generation is not canonical")
    tokens = value.get("output_token_ids")
    decoded = value.get("decoded_utf8")
    if (
        not isinstance(tokens, list)
        or any(isinstance(token, bool) or not isinstance(token, int) for token in tokens)
        or not isinstance(decoded, str)
        or value.get("output_token_count") != len(tokens)
        or value.get("output_token_ids_sha256") != _token_digest(tokens)
        or value.get("output_bytes_sha256") != f"sha256:{sha256(decoded.encode()).hexdigest()}"
    ):
        raise Phase3EvalError("persisted raw token/byte evidence is inconsistent")
    latency = value.get("latency_ms")
    if latency is not None and (isinstance(latency, bool) or not isinstance(latency, int)):
        raise Phase3EvalError("persisted raw latency is malformed")
    raw = capture_raw_generation(
        evaluation_run_id=str(value.get("evaluation_run_id", "")),
        model_identity=str(value.get("model_identity", "")),
        checkpoint_identity=str(value.get("checkpoint_identity", "")),
        sampling_manifest_sha256=str(value.get("sampling_manifest_sha256", "")),
        state_id=str(value.get("state_id", "")),
        output_token_ids=tokens,
        decoded_bytes=decoded.encode(),
        finish_reason=str(value.get("finish_reason", "")),
        latency_ms=latency,
    )
    expected = raw.as_json_object()
    if expected != value:
        raise Phase3EvalError("persisted raw derived fields drifted")
    return raw


def _token_digest(tokens: Sequence[int]) -> str:
    return f"sha256:{sha256(canonical_artifact_bytes(list(tokens))).hexdigest()}"


def _assert_frozen_sampling_payloads(request_bytes: bytes, manifest_bytes: bytes) -> None:
    """This grader repair must not change the owner-approved sampling payloads."""
    request_sha256 = f"sha256:{sha256(request_bytes).hexdigest()}"
    manifest_sha256 = f"sha256:{sha256(manifest_bytes).hexdigest()}"
    if request_sha256 != FROZEN_SAMPLING_REQUESTS_SHA256:
        raise Phase3EvalError("owner-approved sampling requests drifted")
    if manifest_sha256 != FROZEN_SAMPLING_MANIFEST_SHA256:
        raise Phase3EvalError("owner-approved sampling manifest drifted")


def _gzip_jsonl(rows: Sequence[Mapping[str, object]]) -> bytes:
    raw = b"".join(canonical_artifact_bytes(dict(row)) + b"\n" for row in rows)
    return gzip.compress(raw, compresslevel=9, mtime=0)


def _sha256sums(files: Mapping[str, bytes]) -> bytes:
    return "".join(
        f"{sha256(files[name]).hexdigest()}  {name}\n" for name in sorted(files)
    ).encode()


def run_materialize_offline_candidate(**kwargs: object) -> dict[str, bytes]:
    """Synchronous CLI boundary; generation itself remains async."""
    return asyncio.run(materialize_offline_candidate(**kwargs))
