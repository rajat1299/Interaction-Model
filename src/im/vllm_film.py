"""Run the film UI backend against the frozen Phase3X step-63 vLLM service."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

import uvicorn

from im.policy.vllm_semantic import LocalVLLMConfig, LocalVLLMSemanticPolicy
from im.server import create_app
from im.tinker_film import film_tool_script
from im.training.phase3_data import load_pinned_tokenizer

_BASE_REVISION = "995ad96eacd98c81ed38be0c5b274b04031597b0"


async def serve(root: Path, host: str, port: int, vllm_url: str) -> None:
    tokenizer = load_pinned_tokenizer(
        root, root / f".cache/replay-sources/{_BASE_REVISION}"
    ).tokenizer
    app = create_app(
        repository_root=root,
        policy_factory=lambda _session_id: LocalVLLMSemanticPolicy(
            LocalVLLMConfig(
                adapter_model="phase3x-step63",
                # Respond prose needs the separate LoRA-disabled base route. The
                # current GPU session intentionally serves policy actions only.
                base_model="phase3x-base-unavailable",
                base_url=vllm_url,
            ),
            tokenizer,
        ),
        tool_script_factory=lambda _session_id: film_tool_script,
    )
    print(f"Step-63 vLLM film backend ready at http://{host}:{port}", flush=True)
    await uvicorn.Server(uvicorn.Config(app, host=host, port=port, log_level="info")).serve()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8000, type=int)
    parser.add_argument("--vllm-url", default="http://127.0.0.1:18000/v1")
    args = parser.parse_args()
    asyncio.run(serve(Path.cwd(), args.host, args.port, args.vllm_url))


if __name__ == "__main__":
    main()
