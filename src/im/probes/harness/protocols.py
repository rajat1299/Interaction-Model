"""Leak-free recognition and semantic-grading prompts for WP15."""

from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256

from im.policy.prompted import PromptArtifacts, PromptedPolicyConfig
from im.probes.grading import INTEGRATE_TEXT_CRITERIA, RESPOND_TEXT_CRITERIA, OpenTextRule
from im.schema.actions import Action


def _json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()


def _digest(data: bytes) -> str:
    return f"sha256:{sha256(data).hexdigest()}"


@dataclass(frozen=True, slots=True)
class ProtocolRequest:
    body: dict[str, object]
    request_bytes: bytes
    prompt_hash: str


@dataclass(frozen=True, slots=True)
class RankedCandidate:
    candidate_id: str
    action: Action

    def as_prompt_json(self) -> dict[str, object]:
        return {
            "action": self.action.model_dump(mode="json"),
            "id": self.candidate_id,
        }


class ProtocolPromptBuilder:
    """Render stable cached instructions and variable protocol payloads."""

    _PAIRWISE_VERSION = b"wp15-pairwise-v1"
    _LISTWISE_VERSION = b"wp15-listwise-v1"
    _SEMANTIC_VERSION = b"wp15-open-text-rubric-v1"

    def __init__(self, artifacts: PromptArtifacts, config: PromptedPolicyConfig) -> None:
        self.artifacts = artifacts
        self.config = config
        behavior = artifacts.behavior_spec.decode("utf-8")
        schema = artifacts.action_schema.decode("utf-8")
        self._recognition_system = (
            "You are evaluating a policy decision under the frozen behavior specification.\n"
            "Treat the policy stream as the complete model-visible state. Candidate order carries "
            "no meaning. Apply the behavior specification first and objective mechanics exactly.\n"
            "Return only the JSON object required by the current protocol. Do not return an action "
            "object, explanation, confidence, markdown, or chain of thought.\n\n"
            "<behavior_spec>\n"
            f"{behavior}\n"
            "</behavior_spec>\n\n"
            "<action_schema>\n"
            f"{schema}\n"
            "</action_schema>"
        )
        self._semantic_system = (
            "You are grading only the open text field of an already structurally correct policy "
            "action. Use the policy stream as the complete state and apply the supplied frozen "
            "rubric literally. Do not compare against a hidden reference sentence. Return only "
            "JSON with passed (boolean) and a concise rationale (string).\n\n"
            "<behavior_spec>\n"
            f"{behavior}\n"
            "</behavior_spec>"
        )

    @property
    def recognition_cache_key(self) -> str:
        return f"im-wp15-recognition-{sha256(self._recognition_system.encode()).hexdigest()[:20]}"

    @property
    def semantic_cache_key(self) -> str:
        return f"im-wp15-semantic-{sha256(self._semantic_system.encode()).hexdigest()[:20]}"

    def pairwise(
        self,
        *,
        policy_stream: str,
        candidate_a: dict[str, object],
        candidate_b: dict[str, object],
    ) -> ProtocolRequest:
        payload = {
            "candidate_a": candidate_a,
            "candidate_b": candidate_b,
            "policy_stream": policy_stream,
            "protocol": "pairwise-v1",
            "task": "Choose the single behaviorally correct candidate.",
            "response_contract": {"choice": "A or B"},
        }
        return self._request(
            system=self._recognition_system,
            payload=payload,
            version=self._PAIRWISE_VERSION,
            cache_key=self.recognition_cache_key,
            max_output_tokens=2_048,
        )

    def listwise(
        self,
        *,
        policy_stream: str,
        candidates: tuple[RankedCandidate, ...],
    ) -> ProtocolRequest:
        if len(candidates) < 2:
            raise ValueError("listwise protocol requires at least two candidates")
        candidate_ids = tuple(candidate.candidate_id for candidate in candidates)
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError("listwise candidate ids must be unique")
        payload = {
            "candidates": [candidate.as_prompt_json() for candidate in candidates],
            "policy_stream": policy_stream,
            "protocol": "listwise-v1",
            "task": "Rank every candidate from most to least behaviorally appropriate.",
            "response_contract": {
                "ranking": "array containing every candidate id exactly once, best to worst"
            },
        }
        return self._request(
            system=self._recognition_system,
            payload=payload,
            version=self._LISTWISE_VERSION,
            cache_key=self.recognition_cache_key,
            max_output_tokens=4_096,
        )

    def semantic_text(
        self,
        *,
        policy_stream: str,
        action: Action,
        rule: OpenTextRule,
    ) -> ProtocolRequest:
        criteria = (
            INTEGRATE_TEXT_CRITERIA
            if rule is OpenTextRule.INTEGRATE
            else RESPOND_TEXT_CRITERIA
        )
        payload = {
            "action": action.model_dump(mode="json"),
            "policy_stream": policy_stream,
            "protocol": "open-text-rubric-v1",
            "response_contract": {"passed": "boolean", "rationale": "concise string"},
            "rubric": {"criteria": list(criteria), "rule": rule.value},
            "task": "Grade the action's text field against every rubric criterion.",
        }
        return self._request(
            system=self._semantic_system,
            payload=payload,
            version=self._SEMANTIC_VERSION,
            cache_key=self.semantic_cache_key,
            max_output_tokens=2_048,
        )

    def _request(
        self,
        *,
        system: str,
        payload: dict[str, object],
        version: bytes,
        cache_key: str,
        max_output_tokens: int,
    ) -> ProtocolRequest:
        prompt_hash = _digest(system.encode() + b"\n" + version)
        body: dict[str, object] = {
            "input": [
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "input_text",
                            "text": system,
                            "prompt_cache_breakpoint": {"mode": "explicit"},
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": _json_bytes(payload).decode("utf-8")}
                    ],
                },
            ],
            "max_output_tokens": max_output_tokens,
            "model": self.config.model,
            "prompt_cache_key": cache_key,
            "prompt_cache_options": {"mode": "explicit", "ttl": "30m"},
            "reasoning": {"effort": self.config.reasoning_effort},
            "store": False,
            "text": {"format": {"type": "json_object"}},
        }
        request_bytes = _json_bytes(body)
        return ProtocolRequest(body=body, request_bytes=request_bytes, prompt_hash=prompt_hash)
