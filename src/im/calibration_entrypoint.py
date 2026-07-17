"""Uvicorn entrypoint for deterministic, zero-network calibration."""

from im.calibration_app import create_calibration_app

app = create_calibration_app()
