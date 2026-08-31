"""Frozen Phase3X prompt construction and semantic intent resolution."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from im.license import LicenseView
from im.policy.intent import (
    POLICY_INTENT_ADAPTER,
    IntentRegistry,
    IntentResolution,
    resolve_policy_intent,
)


def digest(data: bytes) -> str:
    return f"sha256:{sha256(data).hexdigest()}"


@dataclass(frozen=True, slots=True)
class FrozenPhase3XBoundary:
    """One immutable policy, license, and registry view used for a decision."""

    policy_bytes: bytes
    license_view: LicenseView
    registry: IntentRegistry
    policy_sha256: str
    license_view_sha256: str
    registry_sha256: str
    prompt_bytes: bytes


def freeze_phase3x_boundary(
    policy_bytes: bytes,
    license_view: LicenseView,
    *,
    license_view_bytes: bytes,
) -> FrozenPhase3XBoundary:
    """Construct exactly one registry and bind every prompt input by digest."""
    if not isinstance(policy_bytes, bytes) or not policy_bytes:
        raise ValueError("policy_bytes must be non-empty")
    policy_digest = digest(policy_bytes)
    registry = IntentRegistry.from_state(
        license_view,
        policy_bytes,
        policy_digest.removeprefix("sha256:"),
    )
    registry_bytes = registry.render()
    prompt = (
        policy_bytes
        + b"\n<policy-intent-v1-registry>\n"
        + registry_bytes
        + b"\n</policy-intent-v1-registry>\n"
        + b"Emit exactly one policy_intent_v1 object."
    )
    return FrozenPhase3XBoundary(
        policy_bytes=policy_bytes,
        license_view=license_view,
        registry=registry,
        policy_sha256=policy_digest,
        license_view_sha256=digest(license_view_bytes),
        registry_sha256=digest(registry_bytes),
        prompt_bytes=prompt,
    )


def resolve_phase3x_output(
    parser_input: bytes, registry: IntentRegistry
) -> tuple[object | None, IntentResolution]:
    """Parse one raw intent and resolve it without repair or a second sample."""
    parsed: object | None = None
    try:
        from im.canonical_json import parse_tim_json

        candidate = parse_tim_json(parser_input)
        parsed_model = POLICY_INTENT_ADAPTER.validate_python(candidate)
        parsed = parsed_model.model_dump(mode="json")
    except (TypeError, ValueError):
        pass
    resolution = resolve_policy_intent(parser_input, registry)
    return parsed, resolution
