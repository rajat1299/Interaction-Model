from __future__ import annotations

import asyncio
import json
from collections.abc import Sequence
from pathlib import Path

import httpx
import pytest

from im.config import RuntimeConfig
from im.decision_trace import decode_exact_bytes, digest, read_traces
from im.policy.base import PolicyCallCancelled, PolicyCallError, PolicyCallTrace
from im.policy.intent import LanguageRealizationRequest, ResponseKind
from im.policy.vllm_semantic import LocalVLLMConfig, LocalVLLMSemanticPolicy
from im.scheduler import ManualClock
from im.server import ArtifactPaths, RuntimeSession, load_session_artifacts
from im.store import Store
from im.training.phase3_framing import TERMINAL_MARKER, TERMINAL_TOKEN_ID


class Decoder:
    def __init__(self, parser_input: str) -> None:
        self.parser_input = parser_input

    def decode(self, token_ids: Sequence[int], *, skip_special_tokens: bool) -> str:
        assert skip_special_tokens is False
        assert list(token_ids) == [7]
        return self.parser_input


def response_bytes(parser_input: str, *, token_ids: list[int] | None = None) -> bytes:
    return json.dumps(
        {
            "choices": [
                {
                    "finish_reason": "stop",
                    "text": parser_input + TERMINAL_MARKER,
                    "token_ids": token_ids or [7, TERMINAL_TOKEN_ID],
                }
            ]
        },
        separators=(",", ":"),
    ).encode()


def policy(parser_input: str, handler) -> tuple[LocalVLLMSemanticPolicy, httpx.AsyncClient]:
    client = httpx.AsyncClient(
        base_url="http://127.0.0.1:8000/v1",
        transport=httpx.MockTransport(handler),
    )
    return (
        LocalVLLMSemanticPolicy(
            LocalVLLMConfig(adapter_model="selected-phase3x-adapter", base_model="base-model"),
            Decoder(parser_input),
            client=client,
        ),
        client,
    )


@pytest.mark.asyncio
async def test_one_shot_adapter_request_binds_authenticated_parser_bytes() -> None:
    parser_input = '{ "reason" : "no_trigger", "type" : "idle", "related" : null }'
    seen: list[bytes] = []
    seen_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.content)
        seen_paths.append(request.url.path)
        return httpx.Response(200, content=response_bytes(parser_input))

    semantic, client = policy(parser_input, handler)
    try:
        decision = await semantic.decide(b"exact frozen prompt")
    finally:
        await client.aclose()

    assert len(seen) == 1
    assert seen_paths == ["/v1/completions"]
    body = json.loads(seen[0])
    assert body == {
        "max_tokens": 256,
        "model": "selected-phase3x-adapter",
        "n": 1,
        "prompt": "exact frozen prompt",
        "return_token_ids": True,
        "skip_special_tokens": False,
        "stream": False,
        "temperature": 0.0,
    }
    assert decision.output_bytes == (parser_input + TERMINAL_MARKER).encode()
    assert decision.parser_input_bytes == parser_input.encode()
    assert decision.parser_input_binding == "authenticated_terminal_framing"
    assert decision.calls[0].request == seen[0]
    assert decision.calls[0].response == response_bytes(parser_input)


@pytest.mark.asyncio
async def test_noncanonical_json_survives_runtime_trace_byte_for_byte(tmp_path: Path) -> None:
    parser_input = '{ "reason" : "typing_active", "type" : "idle", "related" : null }'
    raw_response = response_bytes(parser_input)
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, content=raw_response)

    semantic, client = policy(parser_input, handler)
    root = Path(__file__).parents[1]
    config = RuntimeConfig()
    session = RuntimeSession(
        session_id="s_noncanonical",
        directory=tmp_path / "session",
        policy=semantic,
        clock=ManualClock(),
        config=config,
        artifacts=load_session_artifacts(ArtifactPaths.from_repository(root), config),
    )
    session.start()
    raw_request = b""
    try:
        session.accept_snapshot(
            b'{"activity":"active","client_ts":0,"input_type":"insertText",'
            b'"is_composing":false,"selection_end":6,"selection_start":6,"text":"typing"}'
        )
        for _ in range(100):
            if read_traces(session.store):
                break
            await asyncio.sleep(0)
        (trace,) = read_traces(session.store)
        raw_output = (parser_input + TERMINAL_MARKER).encode()
        assert decode_exact_bytes(trace.raw_provider_output) == raw_output
        assert trace.raw_provider_output_sha256 == digest(raw_output)
        assert trace.parser_input is not None
        assert decode_exact_bytes(trace.parser_input) == parser_input.encode()
        assert trace.parser_input_sha256 == digest(parser_input.encode())
        assert trace.parsed_raw_intent == {
            "type": "idle",
            "reason": "typing_active",
            "related": None,
        }
        raw_request = session.store.policy_call_records()[0].request
        assert session.store.policy_call_records()[0].response == raw_response
        assert calls == 1
    finally:
        await session.close()
        await client.aclose()
    reopened = Store(tmp_path / "session/session.sqlite3")
    try:
        (persisted_call,) = reopened.policy_call_records()
        assert persisted_call.request == raw_request
        assert persisted_call.response == raw_response
    finally:
        reopened.close()


@pytest.mark.asyncio
async def test_terminal_projection_mismatch_fails_closed_without_retry(tmp_path: Path) -> None:
    parser_input = '{"type":"idle","reason":"no_trigger","related":null}'
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            200,
            content=response_bytes(
                parser_input, token_ids=[7, TERMINAL_TOKEN_ID, TERMINAL_TOKEN_ID]
            ),
        )

    semantic, client = policy(parser_input, handler)
    root = Path(__file__).parents[1]
    config = RuntimeConfig()
    session = RuntimeSession(
        session_id="s_bad_binding",
        directory=tmp_path / "bad",
        policy=semantic,
        clock=ManualClock(),
        config=config,
        artifacts=load_session_artifacts(ArtifactPaths.from_repository(root), config),
    )
    session.start()
    try:
        session.accept_snapshot(
            b'{"activity":"active","client_ts":0,"input_type":"insertText",'
            b'"is_composing":false,"selection_end":1,"selection_start":1,"text":"x"}'
        )
        for _ in range(100):
            if read_traces(session.store):
                break
            await asyncio.sleep(0)
        (trace,) = read_traces(session.store)
        assert trace.parser_input is None
        assert trace.resolution["status"] == "failed_closed"
        assert trace.executed_event is None
        assert calls == 1
    finally:
        await session.close()
        await client.aclose()


@pytest.mark.asyncio
async def test_respond_prose_uses_base_model_without_adapter() -> None:
    requests: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={"choices": [{"finish_reason": "stop", "text": "Grounded prose."}]},
        )

    semantic, client = policy("{}", handler)
    request = LanguageRealizationRequest(
        "respond", "e_000002", ResponseKind.CLARIFICATION
    )
    try:
        text, calls = await semantic.realize_language(request, b'{"policy":"bytes"}')
    finally:
        await client.aclose()
    assert text == "Grounded prose."
    assert len(requests) == 1
    assert requests[0]["model"] == "base-model"
    assert "adapter" not in requests[0]
    assert "return_token_ids" not in requests[0]
    assert calls[0].attempt_index == 2


@pytest.mark.asyncio
async def test_http_error_is_one_failed_decision_without_retry() -> None:
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(503, content=b'{"error":"offline"}')

    semantic, client = policy("{}", handler)
    try:
        decision = await semantic.decide(b"exact frozen prompt")
    finally:
        await client.aclose()

    assert calls == 1
    assert decision.output_bytes == b""
    assert decision.parser_input_binding is None
    assert decision.calls[0].http_status == 503
    assert decision.calls[0].outcome == "http_error"
    assert decision.calls[0].response == b'{"error":"offline"}'


@pytest.mark.asyncio
async def test_semantic_policy_call_error_still_commits_one_terminal_trace(
    tmp_path: Path,
) -> None:
    call = PolicyCallTrace(
        attempt_index=1,
        model="selected-phase3x-adapter",
        prompt_hash="sha256:" + "0" * 64,
        request=b'{"request":"exact"}',
        response=b'{"error":"offline"}',
        latency_ms=7,
        http_status=503,
        outcome="http_error",
    )

    class FailingSemanticPolicy:
        decision_format = "policy_intent_v1"

        async def decide(self, _prompt: bytes):
            raise PolicyCallError("offline", (call,))

    root = Path(__file__).parents[1]
    config = RuntimeConfig()
    session = RuntimeSession(
        session_id="s_call_error",
        directory=tmp_path / "call-error",
        policy=FailingSemanticPolicy(),
        clock=ManualClock(),
        config=config,
        artifacts=load_session_artifacts(ArtifactPaths.from_repository(root), config),
    )
    session.start()
    try:
        session.accept_snapshot(
            b'{"activity":"active","client_ts":0,"input_type":"insertText",'
            b'"is_composing":false,"selection_end":1,"selection_start":1,"text":"x"}'
        )
        for _ in range(100):
            if read_traces(session.store):
                break
            await asyncio.sleep(0)
        (trace,) = read_traces(session.store)
        assert trace.resolution["status"] == "failed_closed"
        assert trace.executed_event is None
        assert trace.latency_ms == 7
        assert session.store.policy_call_records()[0].response == call.response
    finally:
        await session.close()


@pytest.mark.asyncio
async def test_semantic_cancellation_commits_terminal_trace_before_propagation(
    tmp_path: Path,
) -> None:
    call = PolicyCallTrace(
        attempt_index=1,
        model="selected-phase3x-adapter",
        prompt_hash="sha256:" + "0" * 64,
        request=b'{"request":"exact"}',
        response=b"",
        latency_ms=3,
        http_status=None,
        outcome="cancelled",
    )

    class CancelledSemanticPolicy:
        decision_format = "policy_intent_v1"

        async def decide(self, _prompt: bytes):
            raise PolicyCallCancelled((call,))

    root = Path(__file__).parents[1]
    config = RuntimeConfig()
    session = RuntimeSession(
        session_id="s_cancelled",
        directory=tmp_path / "cancelled",
        policy=CancelledSemanticPolicy(),
        clock=ManualClock(),
        config=config,
        artifacts=load_session_artifacts(ArtifactPaths.from_repository(root), config),
    )
    session.start()
    try:
        session.accept_snapshot(
            b'{"activity":"active","client_ts":0,"input_type":"insertText",'
            b'"is_composing":false,"selection_end":1,"selection_start":1,"text":"x"}'
        )
        for _ in range(100):
            if read_traces(session.store):
                break
            await asyncio.sleep(0)
        (trace,) = read_traces(session.store)
        assert trace.resolution["status"] == "failed_closed"
        assert trace.executed_event is None
        assert session.store.policy_call_records()[0].outcome == "cancelled"
    finally:
        await session.close()
