"""Deterministic targeted WP2-2 timer Wave-3 top-up and teacher packet."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, replace
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

from im.assets import AssetRegistry, Split
from im.assets.model import canonical_artifact_bytes
from im.generation.g7_catalog import G7FamilyInputs, build_g7_timer_wave0_fresh_programs
from im.generation.g7_checkpoint_catalog import build_g7_timer_cancel_checkpoint_program
from im.generation.g7_contention_checkpoint import build_g7_contention_checkpoint_program
from im.generation.g7_rollover_checkpoint import build_g7_rollover_checkpoint_catalog
from im.generation.phase2_timer_wave0 import load_timer_wave0_inputs
from im.generation.phase2_timer_wave2_packet import (
    _CANCEL_INPUTS,
    _CANCEL_TEMPLATE,
    _CONTENTION_ASSETS,
    _CONTENTION_MARK_ASSET,
    _CONTENTION_TEMPLATE,
    _MARK_ASSETS,
    _NORMAL_ASSETS,
    _NORMAL_TEMPLATE,
    _PROMPT_TEMPLATE,
    _ROLLOVER_LOOKUPS,
    _ROLLOVER_TEMPLATE,
    _CandidateSpec,
    _execute,
    _ExecutedCandidate,
    _packet,
    _source_unit_id,
    _timer,
    _validate_source_assets,
)
from im.generation.publication import publish_directory_transaction
from im.generation.scenarios import validate_generated_scenario
from im.generation.timer_instruction_semantics import (
    has_explicit_additional_timer_marker,
)
from im.probes.harness.identity import digest
from im.schema.actions import (
    CancelAction,
    IdleAction,
    IdleReason,
    NudgeAction,
    ScheduleAction,
)

_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_TIMER_WAVE3_OUTPUT = _ROOT / "review" / "phase2" / "timer-wave-3"
_WAVE2_CLOSEOUT = Path("review/phase2/timer-wave-2-repaired-v3-review")
_WAVE2_PLAN = Path("review/phase2/timer-wave-2-plan/plan.json")
_SELECTION_CONTRACT = Path("spec/phase2-selection-v1.json")
_EXPECTED_STREAMS = 15
_EXPECTED_DECISIONS = 225
_EXPECTED_ACTIONS = {
    "cancel": 25,
    "delegate": 1,
    "idle": 73,
    "mark": 4,
    "nudge": 74,
    "schedule": 40,
    "skip": 8,
}
_KIND_VECTORS = {
    "normal_compact": Counter(idle=4, nudge=6, schedule=4),
    "normal_wide": Counter(idle=3, nudge=10, schedule=5),
    "cancel_checkpoint": Counter(cancel=5, idle=7, nudge=2, schedule=2, skip=2),
    "contention_control": Counter(idle=2, mark=2, schedule=2),
    "contention_checkpoint": Counter(cancel=2, idle=4, nudge=6),
    "rollover_c": Counter(cancel=1, delegate=1, idle=13, nudge=2),
}
_KIND_COUNTS = {
    "normal_compact": 2,
    "normal_wide": 4,
    "cancel_checkpoint": 4,
    "contention_control": 2,
    "contention_checkpoint": 2,
    "rollover_c": 1,
}


class TimerWave3Error(ValueError):
    """The targeted timer Wave-3 top-up drifted from the frozen remainder."""


@dataclass(frozen=True, slots=True)
class TimerWave3Packet:
    files: dict[str, bytes]
    request_count: int
    stream_count: int
    shard_count: int


async def build_timer_wave3_packet(*, repository_root: Path = _ROOT) -> TimerWave3Packet:
    """Execute the exact targeted top-up and render provider-free teacher requests."""
    root = repository_root.resolve()
    plan_bytes = _plan(root)
    registry = load_timer_wave0_inputs(
        approved_root=root / "review" / "phase1" / "approved",
        selection_contract_path=root / _SELECTION_CONTRACT,
    )
    with TemporaryDirectory(prefix="phase2-timer-wave3-") as temporary:
        directory = Path(temporary)
        executed = await _execute(_program_specs(registry), directory, root)
        executed += await _execute_rollover_c(registry, directory, root)
        battery = _validate(executed, root)
        packet = _packet(
            executed,
            plan_bytes,
            root,
            expected_candidates=_EXPECTED_STREAMS,
            expected_decisions=_EXPECTED_DECISIONS,
            packet_kind="phase2-timer-wave3-targeted-teacher-plan",
            review_batch_id="pending:timer-wave-3",
            sampling_seed="phase2-timer-wave3-d2-v1",
            stage="t2w3",
            wave_id="timer-wave-3",
        )
    files = {
        **packet.files,
        "README.md": _readme().encode(),
        "pre-upload-battery.json": canonical_artifact_bytes(battery),
        "wave3-plan.json": plan_bytes,
    }
    files["SHA256SUMS"] = _checksums(
        {name: data for name, data in files.items() if name != "SHA256SUMS"}
    )
    return TimerWave3Packet(
        files=files,
        request_count=len(packet.items),
        stream_count=len(executed),
        shard_count=len(packet.shards),
    )


async def materialize_timer_wave3_packet(
    output: Path = DEFAULT_TIMER_WAVE3_OUTPUT,
    *,
    repository_root: Path = _ROOT,
) -> TimerWave3Packet:
    packet = await build_timer_wave3_packet(repository_root=repository_root)
    publish_directory_transaction(output, packet.files)
    return packet


def _program_specs(registry: AssetRegistry) -> tuple[_CandidateSpec, ...]:
    _validate_source_assets(registry)
    specs: list[_CandidateSpec] = []
    for kind, count in (("normal_compact", 2), ("normal_wide", 4)):
        for ordinal in range(count):
            asset_id = _NORMAL_ASSETS[(ordinal + 6) % len(_NORMAL_ASSETS)]
            seed = f"phase2-timer-wave3:{kind}:{ordinal:02d}"
            programs = dict(
                build_g7_timer_wave0_fresh_programs(
                    registry,
                    split=Split.TRAIN,
                    normal_inputs=G7FamilyInputs(_NORMAL_TEMPLATE, (asset_id,)),
                    contention_inputs=G7FamilyInputs(
                        _CONTENTION_TEMPLATE,
                        (_CONTENTION_ASSETS[0], _CONTENTION_MARK_ASSET),
                    ),
                    master_seed=seed,
                    normal_contextual=ordinal % 2 == 1,
                    accumulated_requests=True,
                )
            )
            shape = "timer-normal-compact" if kind == "normal_compact" else "timer-normal-wide"
            program = replace(programs[shape], prompt_template=_PROMPT_TEMPLATE)
            logical = f"wave3-{kind}-{ordinal:02d}"
            specs.append(
                _CandidateSpec(
                    logical,
                    _source_unit_id(kind, program),
                    kind,
                    program,
                    f"phase2-timer-wave3-{kind}:{ordinal:02d}",
                    False,
                )
            )
    for ordinal in range(4):
        cancel_asset_id, short, long = _CANCEL_INPUTS[ordinal + 5]
        program = build_g7_timer_cancel_checkpoint_program(
            registry,
            split=Split.TRAIN,
            template_id=_CANCEL_TEMPLATE,
            cancel_asset_id=cancel_asset_id,
            timer_asset_ids=(short, long),
            master_seed=f"phase2-timer-wave3:cancel:{ordinal:02d}",
            timing_seed="phase2-timer-cancel:431842",
            repaired_controls=True,
        )
        program = replace(program, prompt_template=_PROMPT_TEMPLATE)
        logical = f"wave3-cancel-checkpoint-{ordinal:02d}"
        specs.append(
            _CandidateSpec(
                logical,
                _source_unit_id("cancel_checkpoint", program),
                "cancel_checkpoint",
                program,
                "phase2-timer-cancel:431842",
                True,
            )
        )
    for ordinal in range(2):
        asset_id = _CONTENTION_ASSETS[ordinal + 7]
        programs = dict(
            build_g7_timer_wave0_fresh_programs(
                registry,
                split=Split.TRAIN,
                normal_inputs=G7FamilyInputs(_NORMAL_TEMPLATE, (_NORMAL_ASSETS[0],)),
                contention_inputs=G7FamilyInputs(
                    _CONTENTION_TEMPLATE,
                    (asset_id, _MARK_ASSETS[ordinal + 5]),
                ),
                master_seed=f"phase2-timer-wave3:contention-control:{ordinal:02d}",
                accumulated_requests=True,
            )
        )
        program = replace(
            programs["timer-contention-control"],
            prompt_template=_PROMPT_TEMPLATE,
        )
        logical = f"wave3-contention-control-{ordinal:02d}"
        specs.append(
            _CandidateSpec(
                logical,
                _source_unit_id("contention_control", program),
                "contention_control",
                program,
                f"phase2-timer-wave3-contention-control:{ordinal:02d}",
                False,
            )
        )
    for ordinal in range(2):
        asset_id = _CONTENTION_ASSETS[ordinal + 7]
        timer = _timer(registry, asset_id)
        messages = tuple(
            f"{timer.message} beside the mint envelope on shelf {shelf}"
            for shelf in ("one", "two", "three", "four", "five", "six")
        )
        program = build_g7_contention_checkpoint_program(
            registry,
            split=Split.TRAIN,
            template_id=_CONTENTION_TEMPLATE,
            timer_asset_id=asset_id,
            master_seed=f"phase2-timer-wave3:contention-checkpoint:{ordinal:02d}",
            timing_seed="phase2-contention-checkpoint:839361",
            messages=messages,
            accumulated_requests=True,
        )
        program = replace(program, prompt_template=_PROMPT_TEMPLATE)
        logical = f"wave3-contention-checkpoint-{ordinal:02d}"
        specs.append(
            _CandidateSpec(
                logical,
                _source_unit_id("contention_checkpoint", program),
                "contention_checkpoint",
                program,
                "phase2-contention-checkpoint:839361",
                True,
            )
        )
    if len(specs) != _EXPECTED_STREAMS - 1:
        raise TimerWave3Error("non-rollover Wave-3 inventory drifted")
    return tuple(specs)


async def _execute_rollover_c(
    registry: AssetRegistry,
    directory: Path,
    repository_root: Path,
) -> tuple[_ExecutedCandidate, ...]:
    shape_id = "g7-checkpoint-rollover-c"
    (entry,) = await build_g7_rollover_checkpoint_catalog(
        registry,
        directory=directory / "wave3-rollover-c",
        master_seed="phase2-timer-wave3:rollover_c:00",
        repository_root=repository_root,
        split=Split.TRAIN,
        shape_ids=(shape_id,),
        prompt_template=_PROMPT_TEMPLATE,
        template_id=_ROLLOVER_TEMPLATE,
        rollover_lookup_asset_id=_ROLLOVER_LOOKUPS[5],
        stale_lookup_asset_id=_ROLLOVER_LOOKUPS[6],
        mark_asset_id=_MARK_ASSETS[6],
        first_timer_asset_id=_NORMAL_ASSETS[8],
        recurring_timer_asset_id=_NORMAL_ASSETS[9],
        explicit_lookup_request=True,
    )
    return (
        _ExecutedCandidate(
            _CandidateSpec(
                "wave3-rollover_c-00",
                _source_unit_id("rollover_c", entry.parent.program),
                "rollover_c",
                None,
                "phase2-timer-wave3-rollover-c:00",
                True,
            ),
            entry.parent,
            entry.candidate,
        ),
    )


def _validate(
    executed: tuple[_ExecutedCandidate, ...],
    repository_root: Path,
) -> dict[str, object]:
    kinds = Counter(item.spec.kind for item in executed)
    if kinds != _KIND_COUNTS:
        raise TimerWave3Error("Wave-3 stream shapes differ from the frozen top-up")
    if sum(len(item.actions) for item in executed) != _EXPECTED_DECISIONS:
        raise TimerWave3Error("Wave-3 decision count is not 225")
    actions = Counter()
    prior_hashes = _prior_stream_hashes(repository_root)
    for item in executed:
        validate_generated_scenario(item.parent)
        vector = Counter(str(action.type) for action in item.actions)
        if vector != _KIND_VECTORS[item.spec.kind]:
            raise TimerWave3Error(f"{item.spec.logical_stream_id} action vector drifted")
        actions.update(vector)
        if (
            item.parent.program.bundle.split is not Split.TRAIN
            or item.parent.program.prompt_template != _PROMPT_TEMPLATE
            or item.parent.stream.sha256 in prior_hashes
            or (item.spec.checkpoint and item.candidate is None)
            or (not item.spec.checkpoint and item.candidate is not None)
        ):
            raise TimerWave3Error(f"{item.spec.logical_stream_id} eligibility drifted")
    if dict(sorted(actions.items())) != _EXPECTED_ACTIONS:
        raise TimerWave3Error("Wave-3 combined actions differ from the frozen remainder")
    return _coherence_battery(executed)


def _coherence_battery(
    executed: tuple[_ExecutedCandidate, ...],
) -> dict[str, object]:
    handled_decisions = 0
    novel_cancel_pairs = 0
    reported_controls = 0
    additional_requests = 0
    accumulated_additions = 0
    for item in executed:
        if item.spec.kind in {"normal_compact", "normal_wide"}:
            consumed: list[str] = []
            for action in item.actions:
                if isinstance(action, NudgeAction):
                    consumed.append(action.fire_event_id)
                elif isinstance(action, IdleAction) and action.reason is IdleReason.ALREADY_HANDLED:
                    if not consumed or action.related_event_id != min(consumed):
                        raise TimerWave3Error(
                            f"{item.spec.logical_stream_id} lost the lowest consumed fire"
                        )
                    handled_decisions += 1

        if item.spec.kind == "cancel_checkpoint":
            second, first = item.actions[2], item.actions[4]
            if (
                not isinstance(second, CancelAction)
                or not isinstance(first, CancelAction)
                or not second.instruction.text.startswith("Cancel the second active ")
                or not first.instruction.text.startswith("Cancel the first active ")
                or second.instruction.text == first.instruction.text
                or second.instruction.event_id == first.instruction.event_id
                or second.target.timer_id == first.target.timer_id
            ):
                raise TimerWave3Error(
                    f"{item.spec.logical_stream_id} repeats a cancellation control"
                )
            novel_cancel_pairs += 1
            reported = sum(
                isinstance(action, IdleAction)
                and action.reason is IdleReason.INSTRUCTION_NOT_DIRECT
                for action in item.actions
            )
            rendered_reports = sum(
                "reports this text without requesting it" in json.loads(frame.raw_bytes)["text"]
                for frame in item.parent.program.frames
            )
            if reported != 4 or rendered_reports != reported:
                raise TimerWave3Error(
                    f"{item.spec.logical_stream_id} reported control boundary drifted"
                )
            reported_controls += reported

        request_frames = _accumulated_request_frames(item)
        for previous, current in zip(request_frames, request_frames[1:], strict=False):
            previous_text = json.loads(previous.raw_bytes)["text"]
            current_text = json.loads(current.raw_bytes)["text"]
            prefix = f"{previous_text}\n"
            if not current_text.startswith(prefix) or not has_explicit_additional_timer_marker(
                current_text[len(prefix) :]
            ):
                raise TimerWave3Error(
                    f"{item.spec.logical_stream_id} has a replacement-style reminder"
                )
            accumulated_additions += 1

        for index, action in enumerate(item.parent.program.actions):
            if not isinstance(action, ScheduleAction) or not has_explicit_additional_timer_marker(
                action.instruction.text
            ):
                continue
            if not item.parent.sidecar.decisions[index].active_timer_ids:
                raise TimerWave3Error(
                    f"{item.spec.logical_stream_id} adds a reminder without visible coexistence"
                )
            additional_requests += 1

    if (
        handled_decisions != 12
        or novel_cancel_pairs != 4
        or reported_controls != 16
        or additional_requests != 42
        or accumulated_additions != 34
    ):
        raise TimerWave3Error("Wave-3 coherence battery coverage drifted")
    return {
        "checks": {
            "additional_reminders": {
                "accumulated_editor_additions": accumulated_additions,
                "explicit_additional_requests": additional_requests,
                "replacement_races": 0,
                "visible_coexistence_required": True,
            },
            "cancel_control_novelty": {
                "ordinal_second_then_first_pairs": novel_cancel_pairs,
                "repeated_controls": 0,
            },
            "post_nudge_settling": {
                "already_handled_decisions": handled_decisions,
                "related_event_rule": "lowest_retained_consumed_fire",
            },
            "reported_cancel_controls": {
                "instruction_not_direct_decisions": reported_controls,
            },
        },
        "final_stream_sha256": sorted(item.parent.stream.sha256 for item in executed),
        "format_version": 1,
        "kind": "phase2-timer-wave3-pre-upload-coherence-battery",
        "status": "passed",
        "validated_decision_count": sum(len(item.actions) for item in executed),
        "validated_stream_count": len(executed),
        "validation_surface": "final_materialized_parent_streams_before_teacher_projection",
    }


def _accumulated_request_frames(item: _ExecutedCandidate) -> tuple[object, ...]:
    frames = item.parent.program.frames
    if item.spec.kind == "normal_compact":
        return frames[1:]
    if item.spec.kind == "normal_wide":
        return frames
    if item.spec.kind == "contention_control":
        return frames[:2]
    if item.spec.kind == "contention_checkpoint":
        return frames[:6]
    return ()


def _plan(root: Path) -> bytes:
    closeout_root = root / _WAVE2_CLOSEOUT
    closeout_manifest = _verify_directory(closeout_root)
    closeout = _object(closeout_root / "review-closure.json", "Wave-2 closure")
    coverage = _object(
        closeout_root / "coverage-and-distribution.json",
        "Wave-2 coverage",
    )
    wave2_plan = _object(root / _WAVE2_PLAN, "Wave-2 plan")
    contract_bytes = (root / _SELECTION_CONTRACT).read_bytes()
    if (
        closeout.get("status") != "closed"
        or closeout.get("wave3", {}).get("target_actions")  # type: ignore[union-attr]
        != wave2_plan.get("wave3_remainder")
        or coverage.get("reserve_feasibility", {}).get("status")  # type: ignore[union-attr]
        != "sufficient"
    ):
        raise TimerWave3Error("Wave-2 closure does not authorize the targeted top-up")
    allocation = [
        {
            "candidate_actions": actions,
            "candidate_decisions": sum(actions.values()),
            "candidate_shapes": shapes,
            "candidate_streams": sum(shapes.values()),
            "family": family,
            "multiplier": "targeted_top_up",
            "required_candidate_streams": sum(shapes.values()),
            "target_actions": actions,
            "target_decisions": sum(actions.values()),
            "target_shapes": shapes,
            "target_streams": sum(shapes.values()),
        }
        for family, actions, shapes in (
            (
                "timer_creation_normal_fire",
                {"idle": 20, "nudge": 52, "schedule": 28},
                {"normal_compact": 2, "normal_wide": 4},
            ),
            (
                "timer_cancel_quoting_stale_fire",
                {"cancel": 20, "idle": 28, "nudge": 8, "schedule": 8, "skip": 8},
                {"cancel_checkpoint": 4},
            ),
            (
                "timer_contention_backpressure",
                {"cancel": 4, "idle": 12, "mark": 4, "nudge": 12, "schedule": 4},
                {"contention_checkpoint": 2, "contention_control": 2},
            ),
            (
                "rollover_continuity",
                {"cancel": 1, "delegate": 1, "idle": 13, "nudge": 2},
                {"rollover_c": 1},
            ),
        )
    ]
    payload = {
        "accepted_wave1_stream_count": 13,
        "candidate_generation": allocation,
        "candidate_decision_count": _EXPECTED_DECISIONS,
        "candidate_stream_count": _EXPECTED_STREAMS,
        "eligibility_sidecar_sha256": digest(
            (closeout_root / "whole-stream-eligibility.json").read_bytes()
        ),
        "excluded_stream_hashes": [],
        "final_selection": {
            "algorithm_execution": "deferred_until_all_accepted_streams_are_known",
            "candidate_unit": "complete_parent_or_complete_post_checkpoint_segment",
            "whole_stream_only": True,
        },
        "format_version": 1,
        "kind": "phase2-timer-wave3-targeted-plan",
        "prompt_hash": wave2_plan["prompt_hash"],
        "selection_contract_sha256": digest(contract_bytes),
        "teacher_agreement_selection_feature": False,
        "wave2_closeout_manifest_sha256": closeout_manifest,
        "wave3_remainder": wave2_plan["wave3_remainder"],
    }
    if sum(row["candidate_decisions"] for row in allocation) != _EXPECTED_DECISIONS:
        raise TimerWave3Error("Wave-3 plan does not total 225 decisions")
    return canonical_artifact_bytes(payload)


def _prior_stream_hashes(root: Path) -> set[str]:
    raw = _object(
        root / "review/phase2/timer-wave-2-repaired-v3/raw-streams.json",
        "Wave-2 raw streams",
    )
    streams = raw.get("streams")
    if not isinstance(streams, list):
        raise TimerWave3Error("Wave-2 stream inventory is malformed")
    return {
        stream["parent"]["stream_sha256"]
        for stream in streams
        if isinstance(stream, dict)
        and isinstance(stream.get("parent"), dict)
        and isinstance(stream["parent"].get("stream_sha256"), str)
    }


def _verify_directory(directory: Path) -> str:
    manifest = directory / "SHA256SUMS"
    data = manifest.read_bytes()
    for line in data.decode().splitlines():
        checksum, separator, relative = line.partition("  ")
        path = directory / relative
        if not separator or sha256(path.read_bytes()).hexdigest() != checksum:
            raise TimerWave3Error(f"bound directory changed: {directory}")
    return digest(data)


def _object(path: Path, label: str) -> dict[str, object]:
    try:
        value = json.loads(path.read_bytes())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise TimerWave3Error(f"{label} is unreadable") from error
    if not isinstance(value, dict):
        raise TimerWave3Error(f"{label} is not an object")
    return value


def _checksums(files: dict[str, bytes]) -> bytes:
    return "".join(
        f"{sha256(data).hexdigest()}  {name}\n" for name, data in sorted(files.items())
    ).encode()


def _readme() -> str:
    return """# WP2-2 targeted timer Wave-3 packet

This is the exact 15-stream / 225-decision top-up frozen by the Wave-2 plan.
It uses complete parents or complete checkpoint segments and prompt v3.
The Wave-2 coherence-invariant battery ran against the final materialized streams and passed;
see `pre-upload-battery.json`.
The packet is provider-free: no upload or model call has occurred.
"""
