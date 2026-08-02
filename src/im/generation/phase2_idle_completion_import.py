"""Strict importer for manually returned WP2-6 idle-completion outputs."""

from __future__ import annotations

import re
from pathlib import Path

from im.generation.phase2_mark_wave1_import import (
    MarkWave1ChatImport,
    _build_scoped_import,
)
from im.generation.publication import publish_directory_transaction

_ROOT = Path(__file__).resolve().parents[3]
_PACKET = Path("review/phase2/idle-completion-chat-teacher")
DEFAULT_IDLE_COMPLETION_RESULTS = _ROOT / "review" / "phase2" / "idle-completion-results"
DEFAULT_IDLE_COMPLETION_EXECUTION = (
    _ROOT / "review" / "phase2" / "idle-completion-execution"
)
_ROUND = re.compile(r"round-(\d{3})\.output.*\.jsonl$")


def build_idle_completion_import(
    results: Path = DEFAULT_IDLE_COMPLETION_RESULTS,
    *,
    model: str = "GPT-5.6 Sol",
    reasoning: str = "high",
    repository_root: Path = _ROOT,
) -> MarkWave1ChatImport:
    return _build_scoped_import(
        results,
        model=model,
        reasoning=reasoning,
        repository_root=repository_root,
        packet_path=_PACKET,
        pattern=_ROUND,
        filename_prefix="round",
        expected_rounds=10,
        expected_cases=230,
        mode="idle_completion",
        target_id_field="teacher_case_id",
    )


def materialize_idle_completion_import(
    output: Path = DEFAULT_IDLE_COMPLETION_EXECUTION,
    *,
    results: Path = DEFAULT_IDLE_COMPLETION_RESULTS,
    model: str = "GPT-5.6 Sol",
    reasoning: str = "high",
    repository_root: Path = _ROOT,
) -> MarkWave1ChatImport:
    imported = build_idle_completion_import(
        results,
        model=model,
        reasoning=reasoning,
        repository_root=repository_root,
    )
    publish_directory_transaction(output, imported.files)
    return imported
