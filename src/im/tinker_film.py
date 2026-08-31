"""Run the film UI backend against the frozen Phase3X step-63 sampler."""

from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path
from typing import Any

import tinker
import uvicorn

from im.generation.phase6_gate import (
    STEP63_STATE,
    TinkerSemanticPolicy,
    _delete_sampler,
    _get_weights_info,
    _resolve,
    _verify_weights_info,
    _wait_for_restored_identity,
)
from im.schema.actions import DelegateAction
from im.server import create_app
from im.tools import ScriptedToolResult
from im.training.phase3_data import load_pinned_tokenizer
from im.training.phase3_sampling import read_tinker_api_key

_BASE_REVISION = "995ad96eacd98c81ed38be0c5b274b04031597b0"
FILM_SAMPLER_TTL_SECONDS = 21_600
_MATCH_RESULT = "Argentina 3, France 3 (Argentina won 4-2 on penalties)"


def film_tool_script(action: DelegateAction) -> ScriptedToolResult | None:
    """Return the single safe held-fact fixture used by the live film UI."""
    query = action.args.query.casefold()
    if "argentina" in query and "france" in query and "2022" in query:
        return ScriptedToolResult(latency_ms=500, data=_MATCH_RESULT)
    return None


class _SerializedTinkerPolicy(TinkerSemanticPolicy):
    def __init__(self, *args: Any, lock: asyncio.Lock, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._lock = lock

    async def decide(self, prompt_bytes: bytes):
        # ponytail: one global lock is enough for a single filming browser.
        async with self._lock:
            return await super().decide(prompt_bytes)


async def serve(root: Path, host: str, port: int) -> None:
    tokenizer = load_pinned_tokenizer(root, root / f".cache/replay-sources/{_BASE_REVISION}")
    system_prompt = (root / "spec/phase3x-policy-intent-prompt-v1.txt").read_text("utf-8")
    os.environ["TINKER_API_KEY"] = read_tinker_api_key(root / ".env")
    service = tinker.ServiceClient(user_metadata={"phase": "phase6", "purpose": "live-film-ui"})
    rest = service.create_rest_client()
    sampler_path: str | None = None
    try:
        _verify_weights_info(await _get_weights_info(rest, STEP63_STATE), expected_lora_rank=16)
        client = await _resolve(
            service.create_training_client_from_state_async(
                STEP63_STATE,
                user_metadata={"phase": "phase6", "optimizer": "unused", "purpose": "live-film-ui"},
            )
        )
        await _wait_for_restored_identity(client, rest)
        receipt = await _resolve(
            client.save_weights_for_sampler_async(
                "phase6-live-film", ttl_seconds=FILM_SAMPLER_TTL_SECONDS
            )
        )
        sampler_path = str(receipt.path)
        sampler = await _resolve(service.create_sampling_client_async(model_path=sampler_path))
        lock = asyncio.Lock()
        app = create_app(
            repository_root=root,
            policy_factory=lambda _session_id: _SerializedTinkerPolicy(
                sampler,
                tokenizer,
                system_prompt,
                sampler_path,
                lock=lock,
            ),
            tool_script_factory=lambda _session_id: film_tool_script,
        )
        print(f"Step-63 film backend ready at http://{host}:{port}", flush=True)
        await uvicorn.Server(
            uvicorn.Config(app, host=host, port=port, log_level="info")
        ).serve()
    finally:
        os.environ.pop("TINKER_API_KEY", None)
        if sampler_path is not None:
            await _delete_sampler(rest, sampler_path)
            _verify_weights_info(
                await _get_weights_info(rest, STEP63_STATE), expected_lora_rank=16
            )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8000, type=int)
    args = parser.parse_args()
    asyncio.run(serve(Path.cwd(), args.host, args.port))


if __name__ == "__main__":
    main()
