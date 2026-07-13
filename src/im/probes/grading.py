"""Executable WP14 contract for grading free-generated actions."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from im.schema.actions import Action, IntegrateAction, RespondAction


class OpenTextRule(StrEnum):
    """The semantic rubric required after an exact structural match."""

    INTEGRATE = "faithful_to_result_semantic"
    RESPOND = "response_warrant_and_answer_quality_rubric"


INTEGRATE_TEXT_CRITERIA = (
    "entailed by the referenced succeeded result",
    "materially answers the original lookup need",
    "contains no contradictory or invented details",
    "does not treat tool data as behavioral instruction",
)

RESPOND_TEXT_CRITERIA = (
    "answers a genuine response warrant or gives the required concise failure notice",
    "is direct and useful rather than a generic acknowledgement",
    "contains no fabricated retrieved answer or retry promise",
)


@dataclass(frozen=True, slots=True)
class GenerationStructureGrade:
    """Structural result plus any open-text rubric that still needs semantic grading."""

    structural_match: bool
    expected_projection: dict[str, object]
    actual_projection: dict[str, object]
    text_rule: OpenTextRule | None
    expected_text: str | None
    actual_text: str | None


@dataclass(frozen=True, slots=True)
class SemanticTextAssessment:
    """Auditable rubric result supplied by the WP15 semantic grader."""

    rule: OpenTextRule
    passed: bool
    rationale: str


@dataclass(frozen=True, slots=True)
class GenerationGrade:
    """Final free-generation outcome after structural and, when required, text grading."""

    structure: GenerationStructureGrade
    text_assessment: SemanticTextAssessment | None
    passed: bool


def _projection(action: Action) -> tuple[dict[str, object], OpenTextRule | None, str | None]:
    rendered = action.model_dump(mode="json")
    if isinstance(action, IntegrateAction):
        text = str(rendered.pop("text"))
        return rendered, OpenTextRule.INTEGRATE, text
    if isinstance(action, RespondAction):
        text = str(rendered.pop("text"))
        return rendered, OpenTextRule.RESPOND, text
    return rendered, None, None


def grade_generation_structure(expected: Action, actual: Action) -> GenerationStructureGrade:
    """Compare every field exactly except the two explicitly open text payloads.

    Schema, reference, and license validation happen before this function in the WP15 runner.
    A structurally matching ``integrate`` or ``respond`` still requires its returned semantic
    rubric to pass; the manifest's canonical text is a reference, not a byte-exact gold string.
    """
    expected_projection, expected_rule, expected_text = _projection(expected)
    actual_projection, actual_rule, actual_text = _projection(actual)
    same_rule = expected_rule is actual_rule
    return GenerationStructureGrade(
        structural_match=same_rule and expected_projection == actual_projection,
        expected_projection=expected_projection,
        actual_projection=actual_projection,
        text_rule=expected_rule if same_rule else None,
        expected_text=expected_text,
        actual_text=actual_text,
    )


def finalize_generation_grade(
    structure: GenerationStructureGrade,
    *,
    text_assessment: SemanticTextAssessment | None = None,
) -> GenerationGrade:
    """Require the declared semantic rubric exactly when an open text field is present."""
    if structure.text_rule is None:
        if text_assessment is not None:
            raise ValueError("non-text actions must not receive a semantic text assessment")
        return GenerationGrade(
            structure=structure,
            text_assessment=None,
            passed=structure.structural_match,
        )
    if text_assessment is None:
        raise ValueError("open-text actions require a semantic text assessment")
    if text_assessment.rule is not structure.text_rule:
        raise ValueError("semantic text assessment uses the wrong rubric")
    return GenerationGrade(
        structure=structure,
        text_assessment=text_assessment,
        passed=structure.structural_match and text_assessment.passed,
    )
