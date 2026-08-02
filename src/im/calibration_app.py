"""Zero-network application wiring for browser calibration recordings."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI

from im.policy.latency_stub import LatencyStubPolicy
from im.server import create_app


def create_calibration_app(
    repository_root: Path | None = None, *, session_root: Path | None = None
) -> FastAPI:
    """Construct the calibration-only app without loading credentials or live policy code."""
    root = repository_root or Path(__file__).resolve().parents[2]
    return create_app(
        repository_root=root,
        session_root=session_root,
        calibration_policy_factory=lambda session_id: LatencyStubPolicy(session_id),
        calibration_only=True,
    )
