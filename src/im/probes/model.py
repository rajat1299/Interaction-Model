"""Strict, non-teacher-facing WP14 manifest models."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from im.schema.actions import Action
from im.schema.common import LicenseBlockCode

Digest = Annotated[str, StringConstraints(pattern=r"^sha256:[0-9a-f]{64}$")]
ProbeId = Annotated[str, StringConstraints(pattern=r"^f[0-9]{2}-t[0-9]{2}-[ab]$")]
TwinId = Annotated[str, StringConstraints(pattern=r"^f[0-9]{2}-t[0-9]{2}$")]


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class NegativeClass(StrEnum):
    """The ratified state-level category of one tempting alternative."""

    SEMANTIC_PREFERENCE = "semantic_preference"
    MECHANICAL_NEGATIVE = "mechanical_negative"
    INVARIANCE = "invariance"


class LicenseExpectation(_StrictModel):
    """Manifest assertion for one candidate under the production license."""

    outcome: Literal["allow", "block"]
    code: LicenseBlockCode | None = None

    @model_validator(mode="after")
    def validate_code(self) -> LicenseExpectation:
        if (self.outcome == "block") != (self.code is not None):
            raise ValueError("license block code must appear exactly for blocked outcomes")
        return self


class RenderedVariant(_StrictModel):
    """One fully rebuilt runtime rendering of a logical probe state."""

    variant_id: Literal["v1", "v2", "v3"]
    user_text: str
    user_texts: Annotated[tuple[str, ...], Field(min_length=1)]
    policy_stream: str
    policy_stream_sha256: Digest
    expected_action: Action
    expected_license: LicenseExpectation
    tempting_alternative: Action
    tempting_license: LicenseExpectation

    @model_validator(mode="after")
    def validate_distinct_candidates(self) -> RenderedVariant:
        if self.expected_action == self.tempting_alternative:
            raise ValueError("expected and tempting candidates must differ")
        for name, value in (
            ("user_text", self.user_text),
            ("policy_stream", self.policy_stream),
        ):
            if not value:
                raise ValueError(f"{name} must not be empty")
            try:
                value.encode("utf-8")
            except UnicodeEncodeError as error:
                raise ValueError(f"{name} must be valid UTF-8") from error
        if self.user_text not in self.user_texts:
            raise ValueError("primary user_text must be one of the rendered user snapshots")
        for value in self.user_texts:
            if not value:
                raise ValueError("rendered user snapshot text must not be empty")
            try:
                value.encode("utf-8")
            except UnicodeEncodeError as error:
                raise ValueError("rendered user snapshot text must be valid UTF-8") from error
        return self


class LogicalProbe(_StrictModel):
    """One state-side in a counterfactual twin pair, with three peer variants."""

    probe_id: ProbeId
    family_id: Annotated[int, Field(strict=True, ge=1, le=12)]
    family: str
    twin_id: TwinId
    side: Literal["a", "b"]
    flip_variable: str
    negative_class: NegativeClass
    blocking_variable: str | None = None
    mechanical_release_probe_id: ProbeId | None = None
    pairwise_negative_class: (
        Literal[
            NegativeClass.SEMANTIC_PREFERENCE,
            NegativeClass.MECHANICAL_NEGATIVE,
        ]
        | None
    ) = None
    expected_action_equivalence: Literal["exact_after_reference_rebuild"] | None = None
    secondary_assertions: tuple[str, ...] = ()
    variants: Annotated[tuple[RenderedVariant, ...], Field(min_length=3, max_length=3)]

    @model_validator(mode="after")
    def validate_class_metadata(self) -> LogicalProbe:
        expected_prefix = f"f{self.family_id:02d}-"
        if not self.probe_id.startswith(expected_prefix) or not self.twin_id.startswith(
            expected_prefix
        ):
            raise ValueError("probe and twin ids must match family_id")
        if not self.probe_id.endswith(f"-{self.side}"):
            raise ValueError("probe id must match side")
        if self.probe_id.removesuffix(f"-{self.side}") != self.twin_id:
            raise ValueError("probe id must extend twin id")
        if tuple(variant.variant_id for variant in self.variants) != ("v1", "v2", "v3"):
            raise ValueError("variants must be ordered v1, v2, v3")

        mechanical = self.negative_class is NegativeClass.MECHANICAL_NEGATIVE
        if mechanical != (self.blocking_variable is not None):
            raise ValueError("blocking_variable is required exactly for mechanical negatives")
        if mechanical != (self.mechanical_release_probe_id is not None):
            raise ValueError(
                "mechanical_release_probe_id is required exactly for mechanical negatives"
            )
        if self.mechanical_release_probe_id == self.probe_id:
            raise ValueError("mechanical release state must differ from the blocked state")
        invariance = self.negative_class is NegativeClass.INVARIANCE
        if invariance != (self.expected_action_equivalence is not None):
            raise ValueError("invariance probes require expected-action equivalence")
        if invariance != (self.pairwise_negative_class is not None):
            raise ValueError("invariance probes require a separate pairwise negative class")

        for variant in self.variants:
            if variant.expected_license.outcome != "allow":
                raise ValueError("expected actions must always be license-allowed")
            tempting_outcome = variant.tempting_license.outcome
            pairwise_class = self.pairwise_negative_class if invariance else self.negative_class
            if pairwise_class is NegativeClass.SEMANTIC_PREFERENCE:
                if tempting_outcome != "allow":
                    raise ValueError("semantic-preference alternatives must be allowed")
            elif pairwise_class is NegativeClass.MECHANICAL_NEGATIVE:
                if tempting_outcome != "block":
                    raise ValueError("mechanical alternatives must be blocked")
        return self

    def teacher_variant(self, variant_id: str) -> dict[str, object]:
        """Return only the bytes and candidates WP15 may show to a teacher."""
        variant = next(
            (candidate for candidate in self.variants if candidate.variant_id == variant_id),
            None,
        )
        if variant is None:
            raise KeyError(f"unknown variant: {variant_id}")
        return {
            "policy_stream": variant.policy_stream,
            "candidate_a": variant.expected_action.model_dump(mode="json"),
            "candidate_b": variant.tempting_alternative.model_dump(mode="json"),
        }


class ProbeManifest(_StrictModel):
    """The complete deterministic WP14 catalog."""

    format_version: Literal[1]
    logical_probe_count: Literal[144]
    rendered_state_count: Literal[432]
    variants_per_probe: Literal[3]
    probes: Annotated[tuple[LogicalProbe, ...], Field(min_length=144, max_length=144)]

    @model_validator(mode="after")
    def validate_catalog_shape(self) -> ProbeManifest:
        ids = [probe.probe_id for probe in self.probes]
        if ids != sorted(ids) or len(ids) != len(set(ids)):
            raise ValueError("probes must be uniquely sorted by probe_id")
        family_counts = {
            family_id: sum(probe.family_id == family_id for probe in self.probes)
            for family_id in range(1, 13)
        }
        if any(count != 12 for count in family_counts.values()):
            raise ValueError("every family must contain exactly 12 logical probes")
        twin_counts: dict[str, int] = {}
        for probe in self.probes:
            twin_counts[probe.twin_id] = twin_counts.get(probe.twin_id, 0) + 1
        if len(twin_counts) != 72 or any(count != 2 for count in twin_counts.values()):
            raise ValueError("catalog must contain 72 complete twin pairs")
        return self
