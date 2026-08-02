from __future__ import annotations

import pytest

from im.generation.cancel_resolution import ActiveTimer, resolve_cancel_utterance
from im.generation.g7_cancel_plan import G7CancelPlan


def test_cancel_resolution_filters_descriptor_then_applies_live_ordinal() -> None:
    active = (
        ActiveTimer("t_004", "seal the mint envelope for notes", 40),
        ActiveTimer("t_001", "open the amber blinds for the desk", 10),
        ActiveTimer("t_003", "seal the mint envelope for cards", 30),
    )

    resolved = resolve_cancel_utterance(
        "Cancel the second active mint-envelope reminder.", active
    )

    assert resolved.candidate_timer_ids == ("t_003", "t_004")
    assert resolved.resolved_timer_id == "t_004"


def test_cancel_resolution_leaves_missing_ordinal_unresolved() -> None:
    active = (ActiveTimer("t_001", "open the amber blinds", 10),)

    resolved = resolve_cancel_utterance(
        "Cancel the second active amber-blinds reminder.", active
    )

    assert resolved.candidate_timer_ids == ("t_001",)
    assert resolved.resolved_timer_id is None


@pytest.mark.parametrize(
    "utterance",
    (
        "Cancel that reminder.",
        "Cancel the 2nd active amber-blinds reminder.",
        "Please cancel the second active amber-blinds reminder.",
    ),
)
def test_cancel_resolution_rejects_text_outside_v1_grammar(utterance: str) -> None:
    with pytest.raises(ValueError, match="closed v1 grammar"):
        resolve_cancel_utterance(utterance, ())


def test_g7_plan_renders_from_target_then_independently_resolves() -> None:
    plan = G7CancelPlan()
    amber = plan.schedule("open the amber blinds for the desk")
    first_mint = plan.schedule("seal the mint envelope for cards")
    second_mint = plan.schedule("seal the mint envelope for notes")

    assert plan.cancel(amber).utterance == "Cancel the first active amber-blinds reminder."
    assert plan.cancel(first_mint).utterance == "Cancel the first active mint-envelope reminder."
    assert plan.cancel(second_mint).utterance == "Cancel the first active mint-envelope reminder."
