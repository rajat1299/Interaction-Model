"""Minimal adapter for the pinned No Robots public replay source."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass

from im.assets.model import artifact_digest
from im.generation.phase2_replay_filtering import (
    BACKBONE_REVISION,
    NO_ROBOTS_AUTHOR_REVISION,
    OASST2_AUTHOR_REVISION,
)
from im.generation.phase2_replay_routing import (
    COMPARISON,
    MATH,
    TRANSLATION,
    route_conversation,
)

NO_ROBOTS_SOURCE_ID = "HuggingFaceH4/no_robots"
NO_ROBOTS_REVISION = "e6f9a4ac5c37faeb744ba9ecf0473184d7f8105b"
NO_ROBOTS_LICENSE = "CC-BY-NC-4.0"
OASST2_SOURCE_ID = "OpenAssistant/oasst2"
OASST2_REVISION = "179dd21fc55192153d94adb0e0ce8f69e222bf75"
OASST2_LICENSE = "Apache-2.0"
SELECTION_SEED = "phase2-replay-public-fallback-v1"

_CATEGORY_FALLBACK = {
    "Brainstorm": "practical planning",
    "Classify": "extraction/classification/format conversion",
    "Closed QA": "context-grounded QA",
    "Coding": "coding/debug",
    "Extract": "extraction/classification/format conversion",
    "Generation": "light creative/casual",
    "Open QA": "stable-knowledge explanation",
    "Rewrite": "rewrite/edit/summarize",
    "Summarize": "rewrite/edit/summarize",
}
_FAMILY_OVERRIDES = {
    # Audited language tasks hidden inside No Robots' broad Open QA category.
    "39cdc3c2b2b61f9f37270a6929d05602b1acd0998fcebcde8a066f35efc952ba": TRANSLATION,
    "9e3d7aa94979e6032896278cc9953ba21708e9c539644714e03b38049764297f": TRANSLATION,
    "9bf27e8c180e768d9ee806a3252faf2d16c52265c887cfdc56077cbc5c9ccc93": TRANSLATION,
    "7267122297dc1dbea327fbc2287dde4f4c307c1caa10bd13c15ece2884778c02": TRANSLATION,
    # Audited practical-advice conversations that the generic question router calls explanation.
    "03d0aa618f3b41a27c3b07e44d697125eca1e0e77882cb044c0948c4069f1b89": "practical planning",
    "bf897d72d8e2c11c58800c2de73cf0303f9e34243242b108ab49af886846a598": "practical planning",
    "7f32b547518c6c761eec1c2a8ec8fdea0a60e741b8c89bcffc6d2260a8e78c76": "practical planning",
    "f1bd36ccaf9426e018d999075600ecd75572cffdda77a4cb4b3fd947174f6418": "practical planning",
    "2c32a0ae3602d7d115bc989fca45cd624e8b493107792faf74dce9f7cc82ba9f": "practical planning",
    "5de6e9625f898fe9426f105eb9dd48b6c3474af27793f89680e9a0c868fe5f2d": "practical planning",
    "88c00ef31e024c16e38339720e71f560b4f99749bca8ea2f141d36a422de47c4": "practical planning",
    "4bae9cfd53cfe21e5ab3ddbb7ddaf15a8f14b36f592139d272be7d39a0726d9d": COMPARISON,
    "2dd793d14fe04c1381cf99d968f37fb1d37baa18892823beb5b6ca2a133b770c": "light creative/casual",
}


@dataclass(frozen=True, slots=True)
class PreparedPublicRows:
    candidates: tuple[dict[str, object], ...]
    lineage: tuple[dict[str, object], ...]
    dispositions: Mapping[str, int]


def prepare_oasst2_original_rows(
    records: Mapping[str, Mapping[str, object]],
    assistant_message_ids: Iterable[str],
    *,
    count_tokens: Callable[[str], int],
    task_family: str,
) -> PreparedPublicRows:
    """Convert exact owner-approved OASST2 conversation paths into native chat rows."""
    candidates: list[dict[str, object]] = []
    lineage: list[dict[str, object]] = []
    requested = tuple(sorted(set(assistant_message_ids)))
    for assistant_id in requested:
        reply = records.get(assistant_id)
        if reply is None:
            raise ValueError(f"OASST2 assistant message {assistant_id} is missing")
        path: list[Mapping[str, object]] = []
        seen: set[str] = set()
        item: Mapping[str, object] | None = reply
        while item is not None:
            message_id = item.get("message_id")
            if not isinstance(message_id, str) or message_id in seen:
                raise ValueError(f"OASST2 path for {assistant_id} is cyclic or malformed")
            seen.add(message_id)
            path.append(item)
            parent_id = item.get("parent_id")
            if parent_id is None:
                item = None
            elif not isinstance(parent_id, str) or parent_id not in records:
                raise ValueError(f"OASST2 path for {assistant_id} is incomplete")
            else:
                item = records[parent_id]
        path.reverse()
        roles = tuple(item.get("role") for item in path)
        expected_roles = tuple(
            "prompter" if index % 2 == 0 else "assistant" for index in range(len(path))
        )
        if (
            len(path) < 2
            or roles != expected_roles
            or roles[-1] != "assistant"
            or any(
                item.get("lang") != "en"
                or item.get("deleted") is True
                or item.get("review_result") is False
                or not isinstance(item.get("text"), str)
                or not str(item["text"]).strip()
                for item in path
            )
        ):
            raise ValueError(
                f"OASST2 path for {assistant_id} is not an approved English chat conversation"
            )
        messages = [
            {
                "role": "user" if item["role"] == "prompter" else "assistant",
                "content": str(item["text"]).strip(),
            }
            for item in path
        ]
        answer = messages[-1]["content"]
        token_count = count_tokens(answer)
        prompt_sha256 = artifact_digest(messages[:-1])
        provenance: dict[str, object] = {
            "author_kind": "public_authored_dataset",
            "model_revision": OASST2_AUTHOR_REVISION,
            "tokenizer_revision": BACKBONE_REVISION,
            "renderer": "native_source_chat",
            "temperature": 0.0,
            "tools_enabled": False,
            "max_completion_tokens": 0,
            "completion_count": 1,
            "completion_index": 0,
            "prompt_sha256": prompt_sha256,
            "request_sha256": "",
            "completion_sha256": artifact_digest(answer),
        }
        provenance["request_sha256"] = artifact_digest(
            {
                key: provenance[key]
                for key in (
                    "prompt_sha256",
                    "model_revision",
                    "tokenizer_revision",
                    "renderer",
                    "temperature",
                    "tools_enabled",
                    "max_completion_tokens",
                    "completion_count",
                    "completion_index",
                )
            }
        )
        prompt_id = f"oasst2-original:{path[-2]['message_id']}"
        candidates.append(
            {
                "completion_id": f"oasst2-original:{assistant_id}",
                "prompt_id": prompt_id,
                "dataset_source_id": OASST2_SOURCE_ID,
                "dataset_source_revision": OASST2_REVISION,
                "dataset_source_role": "secondary",
                "task_family": task_family,
                "messages": messages,
                "assistant_token_count": {
                    "count": token_count,
                    "tokenizer_revision": BACKBONE_REVISION,
                },
                "provenance": provenance,
                "selection_seed": SELECTION_SEED,
            }
        )
        lineage.append(
            {
                "prompt_id": prompt_id,
                "source_assistant_message_id": assistant_id,
                "source_dataset": OASST2_SOURCE_ID,
                "source_license": OASST2_LICENSE,
                "source_message_ids": [str(item["message_id"]) for item in path],
                "source_prompt_id": path[-2]["message_id"],
                "source_revision": OASST2_REVISION,
                "system_prompt_preserved": False,
            }
        )
    return PreparedPublicRows(
        tuple(candidates),
        tuple(lineage),
        {"prepared": len(candidates)},
    )


def prepare_no_robots_rows(
    rows: Iterable[Mapping[str, object]],
    *,
    count_tokens: Callable[[str], int],
) -> PreparedPublicRows:
    """Convert pinned source rows, removing only outer whitespace required by the chat parser."""
    candidates: list[dict[str, object]] = []
    lineage: list[dict[str, object]] = []
    dispositions: Counter[str] = Counter()
    for row in rows:
        source_id = row.get("prompt_id")
        raw_messages = row.get("messages")
        if not isinstance(source_id, str) or not source_id:
            dispositions["invalid_prompt_id"] += 1
            continue
        if not isinstance(raw_messages, list) or not raw_messages:
            dispositions["invalid_messages"] += 1
            continue
        messages = []
        for message in raw_messages:
            if not isinstance(message, Mapping):
                continue
            content = message.get("content")
            messages.append(
                {
                    "role": message.get("role"),
                    "content": content.strip() if isinstance(content, str) else content,
                }
            )
        if len(messages) != len(raw_messages) or any(
            message["role"] not in {"system", "user", "assistant"}
            or not isinstance(message["content"], str)
            or not message["content"].strip()
            for message in messages
        ):
            dispositions["invalid_messages"] += 1
            continue
        task_messages = messages[1:] if messages[0]["role"] == "system" else messages
        if len(task_messages) > 6:
            dispositions["conversation_too_long"] += 1
            continue
        user_turns = [message["content"] for message in task_messages if message["role"] == "user"]
        assistant_context = [
            message["content"] for message in task_messages[:-1] if message["role"] == "assistant"
        ]
        category = str(row.get("category", "")).strip()
        family = _FAMILY_OVERRIDES.get(source_id, _CATEGORY_FALLBACK.get(category))
        if category in {"Chat", "Open QA"} and source_id not in _FAMILY_OVERRIDES:
            routed, _reason = route_conversation(
                user_turns,
                source_assistant_context=bool(assistant_context),
                assistant_context_turns=assistant_context,
            )
            if category == "Chat" or routed in {COMPARISON, MATH, TRANSLATION}:
                family = routed
        if family is None:
            dispositions["unrouted"] += 1
            continue
        answer = messages[-1]["content"]
        assert isinstance(answer, str)
        token_count = count_tokens(answer)
        if not 1 <= token_count <= 350:
            dispositions["answer_out_of_band"] += 1
            continue
        prompt_sha256 = artifact_digest(messages[:-1])
        provenance: dict[str, object] = {
            "author_kind": "public_authored_dataset",
            "model_revision": NO_ROBOTS_AUTHOR_REVISION,
            "tokenizer_revision": BACKBONE_REVISION,
            "renderer": "native_source_chat",
            "temperature": 0.0,
            "tools_enabled": False,
            "max_completion_tokens": 0,
            "completion_count": 1,
            "completion_index": 0,
            "prompt_sha256": prompt_sha256,
            "request_sha256": "",
            "completion_sha256": artifact_digest(answer),
        }
        provenance["request_sha256"] = artifact_digest(
            {
                key: provenance[key]
                for key in (
                    "prompt_sha256",
                    "model_revision",
                    "tokenizer_revision",
                    "renderer",
                    "temperature",
                    "tools_enabled",
                    "max_completion_tokens",
                    "completion_count",
                    "completion_index",
                )
            }
        )
        prompt_id = f"no-robots:{source_id}"
        candidates.append(
            {
                "completion_id": f"{prompt_id}:final",
                "prompt_id": prompt_id,
                "dataset_source_id": NO_ROBOTS_SOURCE_ID,
                "dataset_source_revision": NO_ROBOTS_REVISION,
                "dataset_source_role": "primary",
                "task_family": family,
                "messages": messages,
                "assistant_token_count": {
                    "count": token_count,
                    "tokenizer_revision": BACKBONE_REVISION,
                },
                "provenance": provenance,
                "selection_seed": SELECTION_SEED,
            }
        )
        lineage.append(
            {
                "prompt_id": prompt_id,
                "source_prompt_id": source_id,
                "source_dataset": NO_ROBOTS_SOURCE_ID,
                "source_revision": NO_ROBOTS_REVISION,
                "source_license": NO_ROBOTS_LICENSE,
                "source_category": category,
                "system_prompt_preserved": messages[0]["role"] == "system",
            }
        )
        dispositions["prepared"] += 1
    return PreparedPublicRows(tuple(candidates), tuple(lineage), dict(sorted(dispositions.items())))


__all__ = [
    "NO_ROBOTS_LICENSE",
    "NO_ROBOTS_REVISION",
    "NO_ROBOTS_SOURCE_ID",
    "OASST2_LICENSE",
    "OASST2_REVISION",
    "OASST2_SOURCE_ID",
    "PreparedPublicRows",
    "prepare_no_robots_rows",
    "prepare_oasst2_original_rows",
]
