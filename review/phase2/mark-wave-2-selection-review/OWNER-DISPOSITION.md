# WP2-4 mark Wave-2 selection — owner disposition

**Authority.** The project owner reviewed the checksum-bound packet in the review UI on
2026-07-25. The assistant validated identities, explained the three flagged decisions in ordinary
product terms, and transcribed the owner's subsequent approval. No owner judgment is inferred from
teacher agreement.

**Recording method.** Sidecar only. The original packet remains bound by its existing
`SHA256SUMS`. The byte-preserved UI export is `owner-review-decisions-original.jsonl`
(`sha256:d3b19f250be5fe1e2f3133f63f763b2445cf4767f3ab07cdaea6bfa2dbbddef4`).
The resolved record is `owner-review-decisions.jsonl`
(`sha256:ab7953332eb9b39c99035ed6970e014f240a651bb0af3ae59682c9bd6b702eed`).

## Disposition

Approve all 122 routed decisions.

- A complete question still waits while the user has not paused; its yielded twin answers it.
- “Highlight the specimen beside the margin” remains unresolved until visible text identifies one
  concrete specimen. The reviewed streams do not provide that evidence.
- The remaining 119 decisions were accepted directly in the UI.

The review contains 122 accepts, zero rejects, zero unresolved flags, and no missing or duplicate
decision identities.

## Scoped response-prompt repair

The action labels are approved, but the owner also confirmed a separate content-quality defect in
the selected ordinary-response twins: generic prompts combine unrelated value types into
unnatural statements such as treating a person and a measurement as inventory items.

Those affected twins must be replaced by a scoped packet with natural, product-like visible
situations. Their already selected response meanings remain unchanged. The other reviewed streams
remain approved and must not be regenerated or re-reviewed.
