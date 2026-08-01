"""Strict importer for the manual WP2-6 v2 idle top-up teacher outputs."""

from __future__ import annotations

import re
from pathlib import Path

from im.generation.phase2_mark_wave1_import import (
    MarkWave1ChatImport,
    _build_scoped_import,
)
from im.generation.publication import publish_directory_transaction

_ROOT = Path(__file__).resolve().parents[3]
_PACKET = Path("review/phase2/wp2-6-idle-topup")
_REPAIR_PACKET = Path("review/phase2/wp2-6-idle-topup-repair")
_TYPING_PACKET = Path("review/phase2/wp2-6-idle-topup-typing-shortfall")
DEFAULT_IDLE_TOPUP_RESULTS = _ROOT / "review" / "phase2" / "wp2-6-idle-topup-results"
DEFAULT_IDLE_TOPUP_REPAIR_RESULTS = _ROOT / "review" / "phase2" / "wp2-6-idle-topup-repair-results"
DEFAULT_IDLE_TOPUP_TYPING_RESULTS = (
    _ROOT / "review" / "phase2" / "wp2-6-idle-topup-typing-shortfall-results"
)
DEFAULT_IDLE_TOPUP_EXECUTION = _ROOT / "review" / "phase2" / "wp2-6-idle-topup-execution"
DEFAULT_IDLE_TOPUP_REPAIR_EXECUTION = (
    _ROOT / "review" / "phase2" / "wp2-6-idle-topup-repair-execution"
)
DEFAULT_IDLE_TOPUP_TYPING_EXECUTION = (
    _ROOT / "review" / "phase2" / "wp2-6-idle-topup-typing-shortfall-execution"
)
_ROUND = re.compile(r"round-(\d{3})\.output.*\.jsonl$")


def build_idle_topup_import(
    results: Path = DEFAULT_IDLE_TOPUP_RESULTS,
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
        expected_rounds=4,
        expected_cases=44,
        mode="wp2_6_idle_topup_v2",
        target_id_field="teacher_case_id",
    )


def materialize_idle_topup_import(
    output: Path = DEFAULT_IDLE_TOPUP_EXECUTION,
    *,
    results: Path = DEFAULT_IDLE_TOPUP_RESULTS,
    model: str = "GPT-5.6 Sol",
    reasoning: str = "high",
    repository_root: Path = _ROOT,
) -> MarkWave1ChatImport:
    imported = build_idle_topup_import(
        results,
        model=model,
        reasoning=reasoning,
        repository_root=repository_root,
    )
    publish_directory_transaction(output, imported.files)
    return imported


def materialize_idle_topup_repair_import(
    output: Path = DEFAULT_IDLE_TOPUP_REPAIR_EXECUTION,
    *,
    results: Path = DEFAULT_IDLE_TOPUP_REPAIR_RESULTS,
    model: str = "GPT-5.6 Sol",
    reasoning: str = "high",
    repository_root: Path = _ROOT,
) -> MarkWave1ChatImport:
    imported = _build_scoped_import(
        results,
        model=model,
        reasoning=reasoning,
        repository_root=repository_root,
        packet_path=_REPAIR_PACKET,
        pattern=_ROUND,
        filename_prefix="round",
        expected_rounds=1,
        expected_cases=6,
        mode="wp2_6_idle_topup_repair_v2",
        target_id_field="teacher_case_id",
    )
    publish_directory_transaction(output, imported.files)
    return imported


def build_idle_topup_typing_import(
    results: Path = DEFAULT_IDLE_TOPUP_TYPING_RESULTS,
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
        packet_path=_TYPING_PACKET,
        pattern=_ROUND,
        filename_prefix="round",
        expected_rounds=1,
        expected_cases=21,
        mode="wp2_6_idle_topup_typing_shortfall_v2",
        target_id_field="teacher_case_id",
    )


def materialize_idle_topup_typing_import(
    output: Path = DEFAULT_IDLE_TOPUP_TYPING_EXECUTION,
    *,
    results: Path = DEFAULT_IDLE_TOPUP_TYPING_RESULTS,
    model: str = "GPT-5.6 Sol",
    reasoning: str = "high",
    repository_root: Path = _ROOT,
) -> MarkWave1ChatImport:
    imported = build_idle_topup_typing_import(
        results,
        model=model,
        reasoning=reasoning,
        repository_root=repository_root,
    )
    publish_directory_transaction(output, imported.files)
    return imported
