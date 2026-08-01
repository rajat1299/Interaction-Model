from im.generation.phase2_replay_serialization import IGNORE_INDEX, serialize_replay


def _encode(text: str) -> tuple[int, ...]:
    return tuple(range(1, len(text.split()) + 1))


def test_single_and_multi_turn_masks_only_supervise_the_final_answer() -> None:
    single = serialize_replay(
        [
            {"role": "system", "content": "Answer directly."},
            {"role": "user", "content": "Question one"},
            {"role": "assistant", "content": "Final answer"},
        ],
        _encode,
    )
    multi = serialize_replay(
        [
            {"role": "system", "content": "Answer directly."},
            {"role": "user", "content": "Question one"},
            {"role": "assistant", "content": "Context answer"},
            {"role": "user", "content": "Follow up"},
            {"role": "assistant", "content": "Final answer"},
        ],
        _encode,
    )

    assert single.nonzero_loss_tokens == single.final_assistant_tokens
    assert multi.nonzero_loss_tokens == multi.final_assistant_tokens
    assert multi.intermediate_assistant_tokens > 0
    assert all(label == IGNORE_INDEX for label in multi.labels[: multi.context_tokens])
