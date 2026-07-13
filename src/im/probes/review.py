"""Human-review rendering for the WP14 probe and paraphrase gate."""

from __future__ import annotations

import json

from im.probes.model import ProbeManifest
from im.probes.validate import ProbeValidationReport


def _action_json(action: object) -> str:
    return json.dumps(action, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", "<br>")


def render_review(
    manifest: ProbeManifest,
    validation: ProbeValidationReport,
) -> str:
    """Render every logical state and rebuilt variant for the required user gate."""
    lines = [
        "# WP14 probe and paraphrase review",
        "",
        "> Status: awaiting user sign-off. Checking boxes is optional; the explicit user decision",
        "> in the implementation task is authoritative.",
        "",
        "## Validator summary",
        "",
        f"- Logical probe states: {validation.logical_probes}",
        f"- Fully rebuilt rendered states: {validation.rendered_states}",
        f"- Semantic-preference states: {validation.semantic_states}",
        f"- Mechanical-negative states: {validation.mechanical_states}",
        f"- Invariance states: {validation.invariance_states}",
        "- Every candidate passed schema and reference validation before license evaluation.",
        "- Every mechanical negative passed its one-variable release mutation.",
        "",
        "The teacher projection excludes all class, block-code, license, and validator fields.",
        "The full production-rendered bytes are in `manifest.json`; this review uses their SHA-256",
        "identities so the prose and machine artifact stay joined.",
        "",
    ]
    current_family = 0
    for probe in manifest.probes:
        if probe.family_id != current_family:
            current_family = probe.family_id
            lines.extend(
                [
                    f"## Family {probe.family_id}: {probe.family}",
                    "",
                    f"Flip: `{probe.flip_variable}`",
                    "",
                ]
            )
        lines.extend(
            [
                f"### [ ] {probe.probe_id}",
                "",
                f"- Twin: `{probe.twin_id}`; side: `{probe.side}`",
                f"- Negative class: `{probe.negative_class.value}`",
            ]
        )
        if probe.blocking_variable is not None:
            lines.append(
                f"- Isolated blocker: `{probe.blocking_variable}`; release state: "
                f"`{probe.mechanical_release_probe_id}`"
            )
        if probe.expected_action_equivalence is not None:
            lines.append(
                f"- Invariance: `{probe.expected_action_equivalence}`; pairwise negative: "
                f"`{probe.pairwise_negative_class.value}`"
            )
        if probe.secondary_assertions:
            rendered = ", ".join(f"`{value}`" for value in probe.secondary_assertions)
            lines.append(f"- Secondary assertions: {rendered}")
        lines.extend(
            [
                "",
                "| Variant | User snapshots in order | Expected action | Tempting action | "
                "Licenses | Stream |",
                "|---|---|---|---|---|---|",
            ]
        )
        for variant in probe.variants:
            expected = _action_json(variant.expected_action.model_dump(mode="json"))
            tempting = _action_json(variant.tempting_alternative.model_dump(mode="json"))
            user_texts = "<br>→ ".join(_cell(text) for text in variant.user_texts)
            tempting_license = variant.tempting_license.outcome
            if variant.tempting_license.code is not None:
                tempting_license += f":{variant.tempting_license.code.value}"
            lines.append(
                "| "
                + " | ".join(
                    (
                        variant.variant_id,
                        user_texts,
                        f"`{_cell(expected)}`",
                        f"`{_cell(tempting)}`",
                        f"expected=allow; tempting={tempting_license}",
                        f"`{variant.policy_stream_sha256}`",
                    )
                )
                + " |"
            )
        lines.append("")
    return "\n".join(lines)
