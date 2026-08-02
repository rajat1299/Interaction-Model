#!/usr/bin/env python3
"""Plan, run, resume, or adopt the detached v3 timer Wave-1 follow-up Batch."""

from __future__ import annotations

import asyncio
from pathlib import Path

try:
    from scripts import run_phase2_timer_wave1_repair as _repair_runner
except ModuleNotFoundError:  # Direct `python scripts/...` execution.
    import run_phase2_timer_wave1_repair as _repair_runner

_EXPECTED_DECISIONS = 3
_PACKET = Path("review/phase2/timer-wave-1-repair-v3")
_EXECUTION = Path("review/phase2/timer-wave-1-repair-v3-execution")

TimerWave1RepairRunError = _repair_runner.TimerWave1RepairRunError
OpenAIBatchGateway = _repair_runner.OpenAIBatchGateway
RepairBatchPlan = _repair_runner.RepairBatchPlan
_arguments = _repair_runner._arguments


async def _build_plan(repository: Path):
    from im.generation.phase2_timer_wave1_repair_v3 import build_timer_wave1_repair_v3_plan

    return await build_timer_wave1_repair_v3_plan(repository_root=repository)


async def load_plan(repository: Path) -> RepairBatchPlan:
    return await _repair_runner.load_plan(
        repository,
        build_plan=_build_plan,
        packet_relative_path=_PACKET,
        expected_decisions=_EXPECTED_DECISIONS,
    )


async def _run(args) -> None:
    await _repair_runner._run(
        args,
        build_plan=_build_plan,
        packet_relative_path=_PACKET,
        execution_relative_path=_EXECUTION,
        expected_decisions=_EXPECTED_DECISIONS,
        gateway_factory=OpenAIBatchGateway,
    )


def main() -> None:
    asyncio.run(_run(_arguments()))


if __name__ == "__main__":
    main()
