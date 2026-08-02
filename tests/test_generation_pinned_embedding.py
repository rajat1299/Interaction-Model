from im.generation.pinned_embedding import PINNED_RESPONSE_EMBEDDING_SCORER


def test_pinned_embedding_is_deterministic_symmetric_and_bounded() -> None:
    left = "The report names Paris in the current summary."
    right = "The report names Paris in the current summary!"

    score = PINNED_RESPONSE_EMBEDDING_SCORER(left, right)

    assert score == PINNED_RESPONSE_EMBEDDING_SCORER(left, right)
    assert score == PINNED_RESPONSE_EMBEDDING_SCORER(right, left)
    assert -1.0 <= score <= 1.0
    assert score > 0.92
