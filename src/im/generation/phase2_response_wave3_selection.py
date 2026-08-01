"""Frozen whole-pair selection for WP2-5 response Wave-3."""

from __future__ import annotations

from pathlib import Path

from im.generation.phase2_response_wave2_selection import (
    ResponseWave2Selection,
    build_response_wave2_selection,
)
from im.generation.publication import publish_directory_transaction

_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RESPONSE_WAVE3_SELECTION = (
    _ROOT / "review" / "phase2" / "response-wave-3-selection"
)


def build_response_wave3_selection(
    *, repository_root: Path = _ROOT
) -> ResponseWave2Selection:
    return build_response_wave2_selection(
        repository_root=repository_root,
        packet_path=Path("review/phase2/response-wave-3"),
        execution_path=Path("review/phase2/response-wave-3-execution"),
        candidate_pair_count=14,
        selected_pair_count=6,
        seed="phase2-response-wave3-selection-v1",
        wave_label="Wave-3",
    )


def materialize_response_wave3_selection(
    output: Path = DEFAULT_RESPONSE_WAVE3_SELECTION,
    *,
    repository_root: Path = _ROOT,
) -> ResponseWave2Selection:
    selection = build_response_wave3_selection(repository_root=repository_root)
    publish_directory_transaction(output, selection.files)
    return selection
