"""Canonical idle-reason policy for MARK_NEGATIVE text forms."""

from __future__ import annotations

from im.assets.model import TextForm
from im.schema.actions import IdleReason

__all__ = ("mark_negative_idle_reason",)


def mark_negative_idle_reason(
    form: TextForm,
    *,
    partial_form_reason: IdleReason,
) -> IdleReason:
    """Map a negative mark form, with the caller owning partial-form policy."""
    if not isinstance(form, TextForm):
        raise TypeError("form must be a TextForm")
    if partial_form_reason not in (
        IdleReason.TYPING_ACTIVE,
        IdleReason.INSTRUCTION_NOT_DIRECT,
    ):
        raise ValueError(
            "partial_form_reason must be typing_active or instruction_not_direct"
        )
    return {
        TextForm.DIRECT: IdleReason.NO_TRIGGER,
        TextForm.AMBIGUOUS: IdleReason.AMBIGUOUS,
        TextForm.PARTIAL: partial_form_reason,
    }.get(form, IdleReason.INSTRUCTION_NOT_DIRECT)
