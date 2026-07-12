"""Phase-0a golden replay exit gate (G2–G4 remain at their source tests)."""

from pathlib import Path

import pytest

from im.golden_traces import (
    TRACE_NAMES,
    expected_segments,
    load_ingress,
    load_manifest,
    reopened_segment_bytes,
    run_trace,
)


@pytest.mark.gate
@pytest.mark.asyncio
@pytest.mark.parametrize("name", TRACE_NAMES)
async def test_g1_golden_replay_is_byte_exact_after_reopen(
    name: str,
    tmp_path: Path,
) -> None:
    project_root = Path(__file__).resolve().parents[1]
    golden_root = project_root / "golden"
    expected = expected_segments(golden_root, name)
    assert expected, f"missing expected policy segments for {name}"

    result = await run_trace(
        load_manifest(golden_root, name),
        tmp_path / name,
        project_root,
        expected_ingress=load_ingress(golden_root, name),
    )

    assert result.segment_bytes == expected
    assert reopened_segment_bytes(result.database_path, list(expected)) == expected
