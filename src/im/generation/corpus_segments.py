"""Immutable G7 views over complete later runtime segments."""

from __future__ import annotations

from dataclasses import dataclass, field
from re import fullmatch

from im.assets.model import artifact_digest, canonical_artifact_bytes
from im.generation.ingestion import CapturedDecision, CapturedSegment
from im.generation.scenarios import (
    GeneratedScenario,
    _observed_policy_seq,
    validate_generated_scenario,
)
from im.schema.actions import Action
from im.schema.events import StateCheckpointEvent
from im.serialize import parse_event

_SHAPE_ID = r"[a-z][a-z0-9_-]{2,127}"


class CorpusSegmentError(ValueError):
    """A proposed G7 corpus segment is not a complete valid view."""


@dataclass(frozen=True, slots=True)
class CorpusSegmentCandidate:
    """One complete later segment, selected only from validated parent evidence."""

    parent: GeneratedScenario = field(repr=False, compare=False)
    segment_index: int
    shape_id: str
    segment: CapturedSegment = field(init=False)
    selected_decisions: tuple[CapturedDecision, ...] = field(init=False)
    selected_call_indices: tuple[int, ...] = field(init=False)
    checkpoint_seq: int = field(init=False)
    previous_segment_hash: str = field(init=False)
    within_target_band: bool = field(init=False)
    canonical_bytes: bytes = field(init=False)
    sha256: str = field(init=False)

    def __post_init__(self) -> None:
        validate_generated_scenario(self.parent)
        if isinstance(self.segment_index, bool) or not isinstance(self.segment_index, int):
            raise TypeError("segment_index must be an integer")
        if self.segment_index <= 0:
            raise CorpusSegmentError("segment_index must select a later segment")
        if not isinstance(self.shape_id, str) or fullmatch(_SHAPE_ID, self.shape_id) is None:
            raise CorpusSegmentError("shape_id must be a stable lowercase identifier")
        if self.segment_index >= len(self.parent.stream.segments):
            raise CorpusSegmentError("segment_index is absent from the parent stream")

        segment = self.parent.stream.segments[self.segment_index]
        events = tuple(parse_event(line) for line in segment.policy_bytes.splitlines())
        checkpoint = events[0]
        if not isinstance(checkpoint, StateCheckpointEvent):
            raise CorpusSegmentError("selected segment must begin with a state checkpoint")
        if checkpoint.payload.segment.segment_index != self.segment_index:
            raise CorpusSegmentError("checkpoint segment index does not match selection")

        selected = tuple(
            decision
            for decision in self.parent.stream.decisions
            if checkpoint.seq <= _observed_policy_seq(decision.audit_bytes) <= events[-1].seq
        )
        if not selected:
            raise CorpusSegmentError("selected segment contains no captured decisions")
        if len(selected) > 20:
            raise CorpusSegmentError("selected segment exceeds the 20-decision ceiling")
        if any(not segment.policy_bytes.startswith(item.prefix_bytes) for item in selected):
            raise CorpusSegmentError("selected decision prefix is not rooted at the checkpoint")

        call_indices = tuple(item.call_index for item in selected)
        object.__setattr__(self, "segment", segment)
        object.__setattr__(self, "selected_decisions", selected)
        object.__setattr__(self, "selected_call_indices", call_indices)
        object.__setattr__(self, "checkpoint_seq", checkpoint.seq)
        object.__setattr__(
            self, "previous_segment_hash", checkpoint.payload.segment.previous_segment_hash
        )
        object.__setattr__(self, "within_target_band", 6 <= len(selected) <= 20)
        canonical = canonical_artifact_bytes(self.as_json_object())
        object.__setattr__(self, "canonical_bytes", canonical)
        object.__setattr__(self, "sha256", artifact_digest(self.as_json_object()))

    @property
    def decisions(self) -> tuple[CapturedDecision, ...]:
        """The mechanically selected decisions; retained as parent references."""
        return self.selected_decisions

    @property
    def call_indices(self) -> tuple[int, ...]:
        """The mechanically selected decision call indices."""
        return self.selected_call_indices

    @property
    def selected_actions(self) -> tuple[Action, ...]:
        """The exact parent-program actions at the selected call indices."""
        return tuple(
            self.parent.program.actions[call_index - 1] for call_index in self.selected_call_indices
        )

    @property
    def decision_count(self) -> int:
        """The number of selected decisions."""
        return len(self.selected_decisions)

    def as_json_object(self) -> dict[str, object]:
        """Return the canonical, non-teacher-visible candidate identity."""
        sidecar = self.parent.sidecar
        return {
            "format_version": 1,
            "stream_sha256": self.parent.stream.sha256,
            "capture_sha256": self.parent.stream.capture_sha256,
            "sidecar_sha256": sidecar.sha256,
            "scenario_input_sha256": sidecar.scenario_input_sha256,
            "world_script_sha256": sidecar.world_script_sha256,
            "split": sidecar.split.value,
            "family": sidecar.family.value,
            "shape_id": self.shape_id,
            "segment_index": self.segment_index,
            "segment_sha256": self.segment.sha256,
            "checkpoint_seq": self.checkpoint_seq,
            "previous_segment_hash": self.previous_segment_hash,
            "selected_call_indices": list(self.selected_call_indices),
            "decision_count": self.decision_count,
        }
