"""Small declarative adapter from G7 recipe beats to factual-need lineage."""

from __future__ import annotations

from dataclasses import dataclass

from im.generation.need_lineage import (
    BeatNeedLineage,
    DelegateProvenance,
    NeedBasisKind,
    NeedLineage,
    NeedStatus,
)
from im.schema.actions import Action, DelegateAction

__all__ = ("G7NeedPlan", "build_g7_need_evidence")


@dataclass(frozen=True, slots=True)
class G7NeedPlan:
    """One delegate and its optional terminal transition."""

    need_id: str
    delegate_index: int
    terminal_index: int | None = None
    terminal_status: NeedStatus | None = None
    terminal_basis_kind: NeedBasisKind | None = None
    terminal_basis_event_id: str | None = None
    superseded_by_need_id: str | None = None
    birth_index: int | None = None

    def __post_init__(self) -> None:
        if isinstance(self.delegate_index, bool) or not isinstance(self.delegate_index, int):
            raise TypeError("delegate_index must be an integer")
        if self.delegate_index < 0:
            raise ValueError("delegate_index must be non-negative")
        birth = self.delegate_index if self.birth_index is None else self.birth_index
        if (
            isinstance(birth, bool)
            or not isinstance(birth, int)
            or not 0 <= birth <= self.delegate_index
        ):
            raise ValueError("birth_index must precede its delegate")
        terminal = (
            self.terminal_index,
            self.terminal_status,
            self.terminal_basis_kind,
            self.terminal_basis_event_id,
        )
        if any(value is not None for value in terminal) != all(
            value is not None for value in terminal
        ):
            raise ValueError("terminal need evidence must be complete")
        if self.terminal_index is not None and self.terminal_index <= birth:
            raise ValueError("terminal transition must follow need birth")
        if self.terminal_status not in {
            None,
            NeedStatus.ABANDONED,
            NeedStatus.SUPERSEDED,
            NeedStatus.SATISFIED,
        }:
            raise ValueError("terminal_status must close a live need")
        object.__setattr__(self, "birth_index", birth)


def build_g7_need_evidence(
    beat_ids: tuple[str, ...],
    actions: tuple[Action, ...],
    plans: tuple[G7NeedPlan, ...],
) -> tuple[tuple[BeatNeedLineage, ...], tuple[DelegateProvenance, ...]]:
    """Expand concise recipe plans into the complete strict sidecar declaration."""
    if len(beat_ids) != len(actions):
        raise ValueError("beat ids and actions must align")
    if not isinstance(plans, tuple) or not all(isinstance(plan, G7NeedPlan) for plan in plans):
        raise TypeError("plans must contain G7NeedPlan values")
    if tuple(plan.need_id for plan in plans) != tuple(sorted({plan.need_id for plan in plans})):
        raise ValueError("need plans must be sorted and unique")
    delegate_indices = tuple(
        index for index, action in enumerate(actions) if isinstance(action, DelegateAction)
    )
    if tuple(sorted(plan.delegate_index for plan in plans)) != delegate_indices:
        raise ValueError("need plans must cover every delegate exactly once")

    provenance = tuple(
        DelegateProvenance(
            beat_id=beat_ids[plan.delegate_index],
            need_id=plan.need_id,
            query_slot=_delegate(actions, plan.delegate_index).fact,
        )
        for plan in sorted(plans, key=lambda item: item.delegate_index)
    )
    lineage = tuple(
        BeatNeedLineage(
            beat_id,
            tuple(
                _need_at(plan, actions, index)
                for plan in plans
                if index >= plan.birth_index
            ),
        )
        for index, beat_id in enumerate(beat_ids)
    )
    return lineage, provenance


def _need_at(plan: G7NeedPlan, actions: tuple[Action, ...], index: int) -> NeedLineage:
    if plan.terminal_index is None or index < plan.terminal_index:
        return NeedLineage(
            plan.need_id,
            NeedStatus.LIVE,
            _delegate(actions, plan.delegate_index).fact.event_id,
        )
    assert plan.terminal_status is not None
    assert plan.terminal_basis_kind is not None
    assert plan.terminal_basis_event_id is not None
    return NeedLineage(
        plan.need_id,
        plan.terminal_status,
        plan.terminal_basis_event_id,
        superseded_by_need_id=plan.superseded_by_need_id,
        basis_kind=plan.terminal_basis_kind,
    )


def _delegate(actions: tuple[Action, ...], index: int) -> DelegateAction:
    action = actions[index]
    if not isinstance(action, DelegateAction):
        raise ValueError("need plan delegate_index does not identify a delegate")
    return action
