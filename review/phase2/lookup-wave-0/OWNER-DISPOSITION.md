# WP2-3 lookup Wave-0 — owner disposition

**Authority.** The project owner completed the 76-decision review on 2026-07-23 and directed the
scoped repair in conversation. This sidecar is assistant transcription of the owner's decisions;
it does not modify the checksum-bound packet.

The exported review contained 74 accepts and two flags. The two flags are corrected to accepts:

- stream `sha256:b4b19ae0d39a5f592fe0fedab38acd93bf15fff9c865100ca52f009635215d3f`,
  policy seq 28 skips the abandoned `Hollow Cinder postal zone` result;
- the same stream at policy seq 29 skips the abandoned `Quartz Fen bridge status` result.

Both skips are correct. `Juniper Arcade stall` is the separate lookup that remains active and is
integrated afterward.

Ten accepted `integrate` decisions are reclassified as `template_error`. Their action choice and
facts are correct, but the rendered `query: answer` payload is not acceptable user-visible text.
The six affected original streams remain ineligible until their natural-text replacements are
reviewed. The other 66 decisions are approved.

**Standing owner rule.** Any model-authored text shown directly to the user must be natural human
language. Internal labels, raw query prefixes, schema phrasing, and implementation-version wording
are defects even when the underlying action is correct.

Evidence:

- exported review: `sha256:b8a05fdf9f295c3fe53a756dd9c973a52e4c7995cd12330f11a8b7ef638eea82`
- packet `SHA256SUMS`: `sha256:ffc01cb212989351bed2575ed0877e4ffbe539dbfe2e297539b757478c362970`
