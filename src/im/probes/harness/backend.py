"""Live OpenAI and deterministic mocked backends for the WP15 runner."""

from __future__ import annotations

import json
from collections.abc import Callable
from hashlib import sha256
from typing import Protocol, TypeVar

from pydantic import BaseModel

from im.policy.prompted import PromptedPolicy, ResponsesRequestBuilder
from im.probes.harness.client import JsonResponsesClient, usage_from_traces
from im.probes.harness.models import HarnessCompletion
from im.probes.harness.protocols import ProtocolRequest
from im.schema.actions import Action

T = TypeVar("T")


class HarnessBackend(Protocol):
    """Provider seam shared by live and full-corpus mocked acceptance runs."""

    async def generate(self, policy_bytes: bytes) -> HarnessCompletion: ...

    async def complete(
        self,
        request: ProtocolRequest,
        validator: Callable[[object], T],
    ) -> HarnessCompletion: ...

    async def aclose(self) -> None: ...


class OpenAIHarnessBackend:
    """Use the WP13 policy for generation and JSON-mode calls for recognition."""

    def __init__(
        self,
        generation_builder: ResponsesRequestBuilder,
        *,
        api_key: str,
        organization_id: str | None = None,
        project_id: str | None = None,
    ) -> None:
        self._policy = PromptedPolicy(
            generation_builder,
            api_key=api_key,
            organization_id=organization_id,
            project_id=project_id,
        )
        self._json = JsonResponsesClient(
            generation_builder.config,
            api_key=api_key,
            organization_id=organization_id,
            project_id=project_id,
        )

    async def generate(self, policy_bytes: bytes) -> HarnessCompletion:
        decision = await self._policy.decide(policy_bytes)
        attempt = decision.attempt
        value = attempt.model_dump(mode="json") if isinstance(attempt, BaseModel) else attempt
        return HarnessCompletion(
            value=value,
            outcome=(decision.calls[-1].outcome if decision.calls else "invalid"),
            traces=decision.calls,
            usage=usage_from_traces(decision.calls),
        )

    async def complete(
        self,
        request: ProtocolRequest,
        validator: Callable[[object], T],
    ) -> HarnessCompletion:
        completion = await self._json.complete(request, validator)
        value = (
            completion.value.model_dump(mode="json")
            if isinstance(completion.value, BaseModel)
            else completion.value
        )
        return HarnessCompletion(
            value=value,
            outcome=completion.outcome,
            traces=completion.traces,
            usage=completion.usage,
        )

    async def aclose(self) -> None:
        await self._policy.aclose()
        await self._json.aclose()


class OracleHarnessBackend:
    """Leak-free mock: infer the approved answer from stream identity, never prompt labels."""

    def __init__(self, expected_by_stream_sha256: dict[str, Action]) -> None:
        self._expected = dict(expected_by_stream_sha256)

    async def generate(self, policy_bytes: bytes) -> HarnessCompletion:
        expected = self._expected[_stream_digest(policy_bytes.decode("utf-8"))]
        return HarnessCompletion(
            value=expected.model_dump(mode="json"),
            outcome="completed",
        )

    async def complete(
        self,
        request: ProtocolRequest,
        validator: Callable[[object], T],
    ) -> HarnessCompletion:
        payload = _user_payload(request)
        protocol = payload.get("protocol")
        if protocol == "open-text-rubric-v1":
            raw: object = {
                "passed": True,
                "rationale": "Mock oracle accepts the approved structurally correct text.",
            }
        else:
            stream = payload.get("policy_stream")
            if not isinstance(stream, str):
                raise ValueError("mocked protocol payload lacks a policy stream")
            expected = self._expected[_stream_digest(stream)].model_dump(mode="json")
            if protocol == "pairwise-v1":
                if payload.get("candidate_a") == expected:
                    choice = "A"
                elif payload.get("candidate_b") == expected:
                    choice = "B"
                else:
                    raise ValueError("mocked pairwise request omits the approved action")
                raw = {"choice": choice}
            elif protocol == "listwise-v1":
                candidates = payload.get("candidates")
                if not isinstance(candidates, list):
                    raise ValueError("mocked listwise request lacks candidates")
                expected_ids = [
                    candidate.get("id")
                    for candidate in candidates
                    if isinstance(candidate, dict) and candidate.get("action") == expected
                ]
                if len(expected_ids) != 1:
                    raise ValueError("mocked listwise request must contain one approved action")
                candidate_ids = [
                    str(candidate["id"])
                    for candidate in candidates
                    if isinstance(candidate, dict) and "id" in candidate
                ]
                preferred = str(expected_ids[0])
                raw = {
                    "ranking": [preferred]
                    + [candidate_id for candidate_id in candidate_ids if candidate_id != preferred]
                }
            else:
                raise ValueError(f"unknown mocked protocol: {protocol!r}")
        validated = validator(raw)
        value = validated.model_dump(mode="json") if isinstance(validated, BaseModel) else validated
        return HarnessCompletion(value=value, outcome="completed")

    async def aclose(self) -> None:
        return None


def _stream_digest(policy_stream: str) -> str:
    return f"sha256:{sha256(policy_stream.encode()).hexdigest()}"


def _user_payload(request: ProtocolRequest) -> dict[str, object]:
    body = json.loads(request.request_bytes)
    text = body["input"][1]["content"][0]["text"]
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise ValueError("protocol user payload must be an object")
    return payload
