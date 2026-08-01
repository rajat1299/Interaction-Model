# Product

## Register

product

## Users

The primary user is the project owner reviewing model-behavior evidence in a local browser, usually alongside the implementation plan and generated review artifacts. They need to understand one interaction decision at a time, compare blinded candidates, record a defensible disposition, and move through the packet without translating raw schemas in their head.

## Product Purpose

The review desk turns checksum-verified evaluation packets into a clear human review workflow. Success means the reviewer can quickly understand what happened, what differs between candidates, what judgment is required, and what remains unfinished, while the tool preserves packet bytes, blinding, frozen review categories, and portable sidecar output.

## Brand Personality

Calm, precise, and candid. It should feel like a trustworthy expert instrument: dense where evidence demands it, plain-spoken where the reviewer must decide, and visually quiet enough for sustained use.

## Anti-references

- Raw JSON presented as the primary review experience.
- Generic analytics dashboards, consumer-product decoration, or ornamental card grids.
- Ambiguous internal labels such as “stream-level” and “per-decision” without explaining the reviewer’s job.
- Terminal-like typography for ordinary prose and form controls.
- Large forms that repeat the same concepts and force long vertical scrolling.
- Styling changes that obscure or weaken the review contract.

## Design Principles

1. Lead with the human decision: explain the situation and candidate effects before exposing implementation detail.
2. One review task at a time: selection, classification, rationale, save, and advance should form one obvious path.
3. Progressive evidence: keep raw events, reducer state, provenance, and schema details available but secondary.
4. Preserve trust boundaries: candidate origins stay blinded until a valid disposition is saved, and packet bytes remain immutable.
5. Less interface, more clarity: every control must support review speed, correctness, or auditability.

## Accessibility & Inclusion

Target WCAG 2.2 AA contrast and keyboard operation. Use visible focus states, semantic labels, non-color status cues, comfortable reading widths, reduced-motion support, and responsive layouts that remain functional at 620, 980, and 1280 pixel widths.
