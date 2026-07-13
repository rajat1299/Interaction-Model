"""Field-aware WP14 free-generation grading contract."""

import pytest

from im.probes.grading import (
    OpenTextRule,
    SemanticTextAssessment,
    finalize_generation_grade,
    grade_generation_structure,
)
from im.schema.actions import IntegrateAction, RespondAction, ScheduleAction, Span


def test_integrate_paraphrase_requires_semantic_rubric_not_exact_text() -> None:
    expected = IntegrateAction(
        type="integrate",
        result_event_id="e_000010",
        text="The Chicago forecast is 18°C and clear.",
    )
    paraphrase = IntegrateAction(
        type="integrate",
        result_event_id="e_000010",
        text="Chicago: 18°C and clear.",
    )

    structure = grade_generation_structure(expected, paraphrase)

    assert structure.structural_match
    assert structure.text_rule is OpenTextRule.INTEGRATE
    assert finalize_generation_grade(
        structure,
        text_assessment=SemanticTextAssessment(
            rule=OpenTextRule.INTEGRATE,
            passed=True,
            rationale="faithful concise paraphrase of the referenced result",
        ),
    ).passed


def test_integrate_fabrication_fails_the_required_semantic_assessment() -> None:
    expected = IntegrateAction(
        type="integrate",
        result_event_id="e_000010",
        text="The result is 18°C and clear.",
    )
    fabricated = expected.model_copy(update={"text": "The result is 30°C and stormy."})
    structure = grade_generation_structure(expected, fabricated)

    assert structure.structural_match
    assert not finalize_generation_grade(
        structure,
        text_assessment=SemanticTextAssessment(
            rule=OpenTextRule.INTEGRATE,
            passed=False,
            rationale="contradicts the referenced result",
        ),
    ).passed


def test_open_text_never_hides_a_wrong_reference() -> None:
    expected = RespondAction(
        type="respond",
        reply_to_event_id="e_000010",
        text="Fast.",
    )
    wrong_reference = expected.model_copy(
        update={"reply_to_event_id": "e_000011", "text": "“Fast” is a synonym."}
    )

    structure = grade_generation_structure(expected, wrong_reference)

    assert not structure.structural_match
    assert not finalize_generation_grade(
        structure,
        text_assessment=SemanticTextAssessment(
            rule=OpenTextRule.RESPOND,
            passed=True,
            rationale="the prose answers the question",
        ),
    ).passed


def test_non_text_actions_remain_full_object_exact() -> None:
    text = "Remind me every five minutes to stretch."
    instruction = Span(
        event_id="e_000010",
        start_utf16=0,
        end_utf16=len(text),
        text=text,
    )
    expected = ScheduleAction(
        type="schedule",
        instruction=instruction,
        interval_ms=300_000,
        message="stretch",
    )
    invented_message = expected.model_copy(update={"message": "take a break"})

    exact = grade_generation_structure(expected, expected)
    mismatch = grade_generation_structure(expected, invented_message)

    assert finalize_generation_grade(exact).passed
    assert not finalize_generation_grade(mismatch).passed
    with pytest.raises(ValueError, match="must not receive"):
        finalize_generation_grade(
            exact,
            text_assessment=SemanticTextAssessment(
                rule=OpenTextRule.RESPOND,
                passed=True,
                rationale="not applicable",
            ),
        )


def test_open_text_actions_cannot_skip_semantic_grading() -> None:
    response = RespondAction(
        type="respond",
        reply_to_event_id="e_000010",
        text="Fast.",
    )

    with pytest.raises(ValueError, match="require a semantic"):
        finalize_generation_grade(grade_generation_structure(response, response))
