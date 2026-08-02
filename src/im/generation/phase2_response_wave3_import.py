"""Strict import for the final WP2-5 response Wave-3 Chat output."""

from __future__ import annotations

from pathlib import Path

from im.generation.phase2_response_wave2_import import (
    ResponseWave2Import,
    build_response_wave2_import,
)
from im.generation.phase2_response_wave3 import DEFAULT_RESPONSE_WAVE3_RESULTS
from im.generation.publication import publish_directory_transaction

_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RESPONSE_WAVE3_EXECUTION = (
    _ROOT / "review" / "phase2" / "response-wave-3-execution"
)


def build_response_wave3_import(
    results: Path = DEFAULT_RESPONSE_WAVE3_RESULTS,
    *,
    repository_root: Path = _ROOT,
) -> ResponseWave2Import:
    return build_response_wave2_import(
        results,
        repository_root=repository_root,
        packet_path=Path("review/phase2/response-wave-3"),
        expected_cases=28,
        expected_exact=14,
        mode="response_wave3_topup",
        wave_label="Wave-3",
        diagnosis_kind="phase2-response-wave3-diagnosis",
    )


def materialize_response_wave3_import(
    output: Path = DEFAULT_RESPONSE_WAVE3_EXECUTION,
    *,
    results: Path = DEFAULT_RESPONSE_WAVE3_RESULTS,
    repository_root: Path = _ROOT,
) -> ResponseWave2Import:
    imported = build_response_wave3_import(
        results,
        repository_root=repository_root,
    )
    publish_directory_transaction(output, imported.files)
    return imported
