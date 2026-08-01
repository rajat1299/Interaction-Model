"""Frozen whole-pair selection for WP2-5 response Wave-2."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from im.assets.model import canonical_artifact_bytes
from im.generation.phase2_response_wave2 import _checksums, _verify_directory
from im.generation.publication import publish_directory_transaction
from im.probes.harness.identity import digest

_ROOT = Path(__file__).resolve().parents[3]
_PACKET = Path("review/phase2/response-wave-2")
_EXECUTION = Path("review/phase2/response-wave-2-execution")
DEFAULT_RESPONSE_WAVE2_SELECTION = (
    _ROOT / "review" / "phase2" / "response-wave-2-selection"
)
_SEED = "phase2-response-wave2-selection-v1"


class ResponseWave2SelectionError(ValueError):
    """The response selection inputs or frozen allocation drifted."""


@dataclass(frozen=True, slots=True)
class ResponseWave2Selection:
    files: dict[str, bytes]
    decision_count: int
    pair_count: int


def build_response_wave2_selection(
    *,
    repository_root: Path = _ROOT,
    packet_path: Path = _PACKET,
    execution_path: Path = _EXECUTION,
    candidate_pair_count: int = 33,
    selected_pair_count: int = 15,
    seed: str = _SEED,
    wave_label: str = "Wave-2",
) -> ResponseWave2Selection:
    """Select one complete eligible pair per response record using the frozen seed."""
    root = repository_root.resolve()
    packet = root / packet_path
    execution = root / execution_path
    _verify_directory(packet)
    _verify_directory(execution)
    disposition = (execution / "OWNER-DISPOSITION.md").read_text()
    approval = (
        f"Approve all {candidate_pair_count} non-exact paused responses "
        "as `text_equivalent`."
    )
    if approval not in disposition:
        raise ResponseWave2SelectionError("owner approval is absent")

    plan = _object(packet / "teacher-plan.json")
    streams = _object(packet / "raw-streams.json")["streams"]
    targets = plan["targets"]
    if not isinstance(streams, list) or not isinstance(targets, list):
        raise ResponseWave2SelectionError("candidate inventory is malformed")
    by_pair: dict[tuple[int, int], list[dict[str, object]]] = {}
    for row in targets:
        key = (row["response_candidate_ordinal"], row["variant"])
        by_pair.setdefault(key, []).append(row)
    if len(by_pair) != candidate_pair_count or any(
        {row["member"] for row in pair} != {"active", "yielded"}
        for pair in by_pair.values()
    ):
        raise ResponseWave2SelectionError("complete candidate twin inventory drifted")

    ordinals = sorted({ordinal for ordinal, _ in by_pair})
    selected_pairs = []
    selected_ids = set()
    for ordinal in ordinals:
        variants = sorted(variant for item, variant in by_pair if item == ordinal)
        variant = min(
            variants,
            key=lambda value: sha256(f"{seed}:{ordinal}:{value}".encode()).hexdigest(),
        )
        pair = sorted(
            by_pair[(ordinal, variant)], key=lambda row: str(row["member"])
        )
        selected_pairs.append(
            {
                "candidate_ordinal": ordinal,
                "logical_stream_ids": [row["logical_stream_id"] for row in pair],
                "rank_sha256": sha256(
                    f"{seed}:{ordinal}:{variant}".encode()
                ).hexdigest(),
                "variant": variant,
            }
        )
        selected_ids.update(row["logical_stream_id"] for row in pair)
    selected_streams = [
        stream for stream in streams if stream["logical_stream_id"] in selected_ids
    ]
    if len(ordinals) != selected_pair_count or len(selected_streams) != selected_pair_count * 2:
        raise ResponseWave2SelectionError("selected response quota drifted")

    candidate_variants = Counter(row["variant"] for row in targets if row["member"] == "yielded")
    selected_variants = Counter(row["variant"] for row in selected_pairs)
    report = {
        "action_counts": {"idle": selected_pair_count, "respond": selected_pair_count},
        "candidate_pair_count": candidate_pair_count,
        "decision_count": selected_pair_count * 2,
        "format_version": 1,
        "generated_vs_selected": {
            "candidate": {
                "action": {
                    "idle": candidate_pair_count,
                    "respond": candidate_pair_count,
                },
                "floor": {
                    "active": candidate_pair_count,
                    "yielded": candidate_pair_count,
                },
                "variant": _counter(candidate_variants),
            },
            "selected": {
                "action": {
                    "idle": selected_pair_count,
                    "respond": selected_pair_count,
                },
                "floor": {
                    "active": selected_pair_count,
                    "yielded": selected_pair_count,
                },
                "variant": _counter(selected_variants),
            },
        },
        "kind": "phase2-response-wave2-whole-pair-selection",
        "payload_substitution_count": 0,
        "selected_pair_count": selected_pair_count,
        "selected_pairs": selected_pairs,
        "selection_seed": seed,
        "source_bindings": {
            "execution_sha256": digest((execution / "SHA256SUMS").read_bytes()),
            "packet_sha256": digest((packet / "SHA256SUMS").read_bytes()),
        },
        "teacher_agreement_used_as_selection_feature": False,
        "whole_twin_pairs_only": True,
    }
    files = {
        "README.md": (
            f"# WP2-5 response {wave_label} selection\n\n".encode()
            +
            b"One complete active/paused pair is selected per response record using the frozen "
            b"seed. Teacher agreement is not a selection feature; approved response payloads "
            b"remain unchanged.\n"
        ),
        "selected-raw-streams.json": canonical_artifact_bytes(
            {
                "format_version": 1,
                "kind": f"phase2-response-{wave_label.lower()}-selected-streams",
                "streams": selected_streams,
            }
        ),
        "selection-report.json": canonical_artifact_bytes(report),
    }
    files["SHA256SUMS"] = _checksums(files)
    return ResponseWave2Selection(
        files,
        selected_pair_count * 2,
        selected_pair_count,
    )


def materialize_response_wave2_selection(
    output: Path = DEFAULT_RESPONSE_WAVE2_SELECTION,
    *,
    repository_root: Path = _ROOT,
) -> ResponseWave2Selection:
    selection = build_response_wave2_selection(repository_root=repository_root)
    publish_directory_transaction(output, selection.files)
    return selection


def _counter(counter: Counter[object]) -> dict[str, int]:
    return {str(key): value for key, value in sorted(counter.items())}


def _object(path: Path) -> dict[str, object]:
    value = json.loads(path.read_bytes())
    if not isinstance(value, dict):
        raise ResponseWave2SelectionError(f"{path.name} is malformed")
    return value
