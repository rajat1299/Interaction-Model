"""Targeted final top-up for WP2-5 response-floor behavior."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

from im.assets import Split
from im.assets.model import canonical_artifact_bytes
from im.generation.g7_response_twins import (
    validate_response_floor_twin_alignment,
)
from im.generation.phase2_lookup_wave0 import load_lookup_wave0_inputs
from im.generation.phase2_lookup_wave2 import _response_assets
from im.generation.phase2_response_wave2 import (
    ExecutedResponseWave2,
    _checksums,
    _packet,
    _program_specs,
    _verify_directory,
)
from im.generation.publication import publish_directory_transaction
from im.generation.response_contracts import ResponseKind
from im.generation.scenarios import execute_scenario, validate_generated_scenario
from im.probes.harness.identity import digest
from im.schema.actions import IdleAction, IdleReason, RespondAction

_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RESPONSE_WAVE3_PLAN = _ROOT / "review" / "phase2" / "response-wave-3-plan"
DEFAULT_RESPONSE_WAVE3_OUTPUT = _ROOT / "review" / "phase2" / "response-wave-3"
DEFAULT_RESPONSE_WAVE3_RESULTS = (
    _ROOT / "review" / "phase2" / "response-wave-3-results"
)
_ORDINALS = (28, 29, 30, 31, 32, 34)
_THREE_VARIANT_ORDINALS = frozenset({28, 34})
_SELECTION_SEED = "phase2-response-wave3-selection-v1"


class ResponseWave3Error(ValueError):
    """The final response top-up is incomplete or has drifted."""


@dataclass(frozen=True, slots=True)
class ResponseWave3Packet:
    files: dict[str, bytes]
    decision_count: int
    round_count: int
    stream_count: int


def build_response_wave3_plan(*, repository_root: Path = _ROOT) -> dict[str, bytes]:
    root = repository_root.resolve()
    selection = root / "review/phase2/response-wave-2-selection"
    _verify_directory(selection)
    variants = {
        str(ordinal): 3 if ordinal in _THREE_VARIANT_ORDINALS else 2
        for ordinal in _ORDINALS
    }
    plan = {
        "action_vectors": {
            "candidate": {"idle": 14, "respond": 14},
            "selected": {"idle": 6, "respond": 6},
            "wp2_5_final": {"idle": 30, "respond": 30},
        },
        "candidate_pair_count": 14,
        "candidate_stream_count": 28,
        "format_version": 1,
        "kind": "phase2-response-wave3-frozen-allocation",
        "response_candidate_ordinals": list(_ORDINALS),
        "response_payload_substitution_count": 0,
        "selection": {
            "per_ordinal": (
                "Choose the minimum SHA-256 rank of "
                "selection_seed:candidate_ordinal:variant."
            ),
            "seed": _SELECTION_SEED,
            "teacher_agreement_used_as_feature": False,
            "whole_twin_pairs_only": True,
        },
        "source_bindings": {
            "response_wave2_selection_sha256": digest(
                (selection / "SHA256SUMS").read_bytes()
            )
        },
        "variant_counts_by_ordinal": variants,
    }
    files = {
        "README.md": (
            b"# WP2-5 response Wave-3 frozen top-up\n\n"
            b"The final six untouched response records receive 14 complete candidate twin pairs. "
            b"One pair per record is selected by the frozen seed after owner review.\n"
        ),
        "plan.json": canonical_artifact_bytes(plan),
    }
    files["SHA256SUMS"] = _checksums(files)
    return files


def materialize_response_wave3_plan(
    output: Path = DEFAULT_RESPONSE_WAVE3_PLAN,
    *,
    repository_root: Path = _ROOT,
) -> dict[str, bytes]:
    files = build_response_wave3_plan(repository_root=repository_root)
    publish_directory_transaction(output, files)
    return files


async def build_response_wave3_packet(
    *, repository_root: Path = _ROOT
) -> ResponseWave3Packet:
    root = repository_root.resolve()
    _verify_directory(root / "review/phase2/response-wave-3-plan")
    specs = _program_specs(
        load_lookup_wave0_inputs(),
        root,
        ordinals=_ORDINALS,
        three_variant_ordinals=_THREE_VARIANT_ORDINALS,
        seed_prefix="phase2-response-wave3",
    )
    with TemporaryDirectory(prefix="phase2-response-wave3-") as temporary:
        executed = []
        for spec in specs:
            generated = await execute_scenario(
                spec.program,
                session_id=f"response-wave3-{spec.logical_stream_id}",
                directory=Path(temporary) / spec.logical_stream_id,
                repository_root=root,
            )
            validate_generated_scenario(generated)
            executed.append(ExecutedResponseWave2(spec, generated))
    values = tuple(executed)
    battery = _validate(values, root)
    packet = _packet(
        values,
        battery,
        root,
        stage="t2rw3",
        ordering_seed=_SELECTION_SEED,
        wave_id="response-wave-3",
        artifact_prefix="phase2-response-wave3",
        source_bindings=_source_bindings(root),
        readme=(
            b"# WP2-5 response Wave-3 Chat teacher top-up\n\n"
            b"The final 28-case packet covers 14 complete active/paused twins over the six "
            b"untouched approved responses. Existing response payloads are never substituted.\n"
        ),
    )
    return ResponseWave3Packet(
        packet.files,
        packet.decision_count,
        packet.round_count,
        packet.stream_count,
    )


async def materialize_response_wave3_packet(
    output: Path = DEFAULT_RESPONSE_WAVE3_OUTPUT,
    *,
    repository_root: Path = _ROOT,
) -> ResponseWave3Packet:
    packet = await build_response_wave3_packet(repository_root=repository_root)
    publish_directory_transaction(output, packet.files)
    output.parent.joinpath(DEFAULT_RESPONSE_WAVE3_RESULTS.name).mkdir(exist_ok=True)
    return packet


def _validate(
    executed: tuple[ExecutedResponseWave2, ...], root: Path
) -> dict[str, object]:
    actions = Counter(
        action.type for item in executed for action in item.generated.program.actions
    )
    pairs = Counter(
        (item.spec.candidate_ordinal, item.spec.variant)
        for item in executed
        if item.spec.member == "yielded"
    )
    if (
        len(executed) != 28
        or actions != Counter(idle=14, respond=14)
        or len(pairs) != 14
        or {ordinal for ordinal, _ in pairs} != set(_ORDINALS)
    ):
        raise ResponseWave3Error("Wave-3 inventory or action vector drifted")
    prior_hashes = set()
    for relative in (
        "review/phase2/response-wave-0/raw-stream-evidence.json",
        "review/phase2/response-wave-1/raw-streams.json",
        "review/phase2/response-wave-2/raw-streams.json",
    ):
        raw = json.loads((root / relative).read_bytes())
        prior_hashes.update(row["stream_sha256"] for row in raw["streams"])
    hashes = {item.generated.stream.sha256 for item in executed}
    inputs = {item.generated.stream.decisions[0].prefix_bytes for item in executed}
    assets = _response_assets(root)
    if len(hashes) != 28 or len(inputs) != 28 or hashes & prior_hashes:
        raise ResponseWave3Error("Wave-3 repeats a stream, model input, or prior case")
    for ordinal, variant in pairs:
        pair = tuple(
            item
            for item in executed
            if (item.spec.candidate_ordinal, item.spec.variant) == (ordinal, variant)
        )
        yielded = next(item for item in pair if item.spec.member == "yielded")
        active = next(item for item in pair if item.spec.member == "active")
        validate_response_floor_twin_alignment(
            yielded.generated.program, active.generated.program
        )
        yielded_action = yielded.generated.program.actions[0]
        active_action = active.generated.program.actions[0]
        if (
            yielded.generated.program.bundle.split is not Split.TRAIN
            or yielded.generated.program.prompt_template != "prompt-template-v4.txt"
            or active.generated.program.prompt_template != "prompt-template-v4.txt"
            or assets[ordinal].draft.answer_contract.response_kind
            is not ResponseKind.ORDINARY_GROUNDED
            or not isinstance(yielded_action, RespondAction)
            or yielded_action.text != assets[ordinal].candidate_response
            or not isinstance(active_action, IdleAction)
            or active_action.reason is not IdleReason.AWAITING_OPENING
        ):
            raise ResponseWave3Error("response floor or approved payload drifted")
    return {
        "action_counts": dict(sorted(actions.items())),
        "candidate_pair_count": 14,
        "checks": {
            "all_model_inputs_unique": True,
            "all_questions_answered_by_exact_approved_payload": True,
            "all_streams_disjoint_from_prior_response_waves": True,
            "all_streams_train_prompt_v4_bound": True,
            "response_floor_twins_aligned": True,
            "response_payload_substitution_count_zero": True,
        },
        "decision_count": 28,
        "format_version": 1,
        "kind": "phase2-response-wave3-pre-upload-battery",
        "source_unit_count": 6,
        "stream_count": 28,
    }


def _source_bindings(root: Path) -> dict[str, str]:
    paths = {
        "response_selection_sha256": "review/phase2/response-tranche-selection",
        "response_wave2_execution_sha256": "review/phase2/response-wave-2-execution",
        "response_wave2_selection_sha256": "review/phase2/response-wave-2-selection",
    }
    result = {}
    for key, relative in paths.items():
        directory = root / relative
        _verify_directory(directory)
        result[key] = digest((directory / "SHA256SUMS").read_bytes())
    result["selection_contract_sha256"] = digest(
        (root / "spec/phase2-selection-v1.json").read_bytes()
    )
    return result
