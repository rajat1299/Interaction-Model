"""Canonical replay chat serialization and final-answer-only loss masks."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

IGNORE_INDEX = -100


@dataclass(frozen=True, slots=True)
class SerializedReplay:
    input_ids: tuple[int, ...]
    labels: tuple[int, ...]
    context_tokens: int
    intermediate_assistant_tokens: int
    final_assistant_tokens: int

    @property
    def all_tokens(self) -> int:
        return len(self.input_ids)

    @property
    def nonzero_loss_tokens(self) -> int:
        return sum(label != IGNORE_INDEX for label in self.labels)


def render_replay_chat(messages: Sequence[Mapping[str, str]]) -> str:
    return "".join(
        f"<|im_start|>{message['role']}\n{message['content']}<|im_end|>\n"
        for message in messages
    )


def serialize_replay(
    messages: Sequence[Mapping[str, str]], encode: Callable[[str], Sequence[int]]
) -> SerializedReplay:
    if not messages or messages[-1].get("role") != "assistant":
        raise ValueError("replay chat must end with the supervised assistant answer")
    input_ids: list[int] = []
    labels: list[int] = []
    context_tokens = intermediate_tokens = final_tokens = 0
    final_index = len(messages) - 1
    for index, message in enumerate(messages):
        role, content = message.get("role"), message.get("content")
        if (
            role not in {"system", "user", "assistant"}
            or role == "system"
            and index != 0
            or not isinstance(content, str)
            or not content
        ):
            raise ValueError(
                "replay messages must be non-empty native turns with an optional leading system"
            )
        prefix = tuple(encode(f"<|im_start|>{role}\n"))
        content_ids = tuple(encode(content))
        suffix = tuple(encode("<|im_end|>\n"))
        ids = prefix + content_ids + suffix
        input_ids.extend(ids)
        if index == final_index:
            labels.extend((IGNORE_INDEX,) * len(prefix))
            labels.extend(content_ids)
            labels.extend((IGNORE_INDEX,) * len(suffix))
            final_tokens += len(content_ids)
        else:
            labels.extend((IGNORE_INDEX,) * len(ids))
            context_tokens += len(ids)
            if role == "assistant":
                intermediate_tokens += len(content_ids)
    return SerializedReplay(
        tuple(input_ids),
        tuple(labels),
        context_tokens,
        intermediate_tokens,
        final_tokens,
    )
