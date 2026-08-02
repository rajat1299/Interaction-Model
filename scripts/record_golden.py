"""Intentionally regenerate the reviewed Phase-0a ingress and policy goldens."""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from im.golden_traces import TRACE_NAMES, manifest_for, render_manifest, run_trace


async def record() -> None:
    project_root = Path(__file__).resolve().parents[1]
    golden_root = project_root / "golden"
    golden_root.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="im-golden-") as temporary:
        temp_root = Path(temporary)
        for name in TRACE_NAMES:
            manifest = manifest_for(name)
            result = await run_trace(manifest, temp_root / name, project_root)
            trace_root = golden_root / name
            policy_root = trace_root / "policy"
            policy_root.mkdir(parents=True, exist_ok=True)
            (trace_root / "replay.json").write_bytes(render_manifest(manifest))
            (trace_root / "ingress.jsonl").write_bytes(result.ingress_bytes)
            for stale in policy_root.glob("segment-*.bin"):
                stale.unlink()
            for segment_index, policy_bytes in sorted(result.segment_bytes.items()):
                path = policy_root / f"segment-{segment_index:03d}.bin"
                path.write_bytes(policy_bytes)


def main() -> None:
    asyncio.run(record())


if __name__ == "__main__":
    main()
