# WP2-2 timer Wave-2 — fast coherence review

**Authority.** The assistant performed this D7 fast coherence scan after the owner instructed it
to finish the matching-decision review and surface only concerns. This is diagnostic evidence, not
a new owner disposition. The owner's 97-row disposition remains authoritative.

**Evidence bindings.** The scan uses `phase2-review-evidence.json` at
`sha256:b35597214bab16a080b820873f82fe6a66b3d2f0719efba930d8996d53643e26`,
`raw-streams.json` at
`sha256:23546b8739926c76967a2f57361d494d731285ce61aaf471c57ce61e6c85e7a8`, and
`OWNER-DISPOSITION.md` at
`sha256:ecae3b9bab8e56f086167355b7592c8b9c3b9a3b5a3d1e7e4bbba020a202dfb7`.

## Method

- Inspected the raw chronological frame and action sequence for every candidate shape, then checked
  cross-source confirmations and the exact first-disagreement position for all 46 runtime streams.
- Applied D7 early exit: 45 streams already contain an owner-disposed non-equivalent causal error,
  so matching rows after the first such error are not a second detailed-review queue.
- Scanned matching mandatory actions before each first disagreement and the complete sole
  all-equivalent stream for naturalness, causal continuity, repeated behavior, and suffix sanity.
- Rechecked schedule timing and editor replacement behavior directly from the raw frames instead of
  treating teacher/oracle agreement as evidence of correctness.

## Concern found

The sole stream without a teacher/oracle disagreement,
`sha256:e54245586b91885f089543814670b85dc3056648bf0a94e2d8b53dd7b30859b8`
(`t2w2-normal_wide-301fb4a56279c5cf`), is still a template failure. Its entire editor text is
replaced at 0, 649, 1299, 1879, and 2649 ms, yet the oracle and teacher agree on five separate
`schedule` actions. The last four snapshots neither say "another" nor coexist with the earlier
instruction. They are the rapid replacement/extension shape the owner already ruled invalid, so
agreement does not make this stream eligible.

The same coherence check found a related hidden setup defect in all five `contention_checkpoint`
candidates. Each parent manufactures six active reminders from six complete-editor replacements at
0, 728, 1913, 2963, 4023, and 5073 ms. The later sentences change only the shelf number and never
request an additional reminder. Those schedule decisions precede the selected checkpoint segment,
but the segment's nudge/cancel state depends on the six manufactured timers. The five segments are
therefore template-invalid, not valid suffixes.

Repair must cover the whole affected construction, not only disagreement rows:

- normal compact/wide streams need a 3–5 second post-confirmation boundary and either an explicit
  additional instruction or a true single-sentence replacement with the approved modification
  limitation;
- contention-control and contention-checkpoint setup must use explicit additional-reminder wording
  after confirmed creation, or must not create multiple timers;
- the malformed originals remain ineligible and must not contribute accepted decisions.

No additional concern was found beyond the already approved clusters in the cancel-checkpoint and
rollover prefixes. Their streams remain rejected for those earlier owner-disposed causal errors.

## Gate result

- 45/46 streams: rejected at their first owner-disposed non-equivalent causal error.
- 1/46 all-equivalent stream: rejected by this shared template-coherence defect.
- 0/46 Wave-2 candidate streams are currently accepted.
- The earlier statement that 551 matching mandatory routes remained as a standalone owner-review
  queue was incorrect. D7 early exit removes later rows from detailed review, and the sole
  all-match stream fails coherence.

Wave 3 remains blocked. The next work is offline repair of the affected oracle/template strata and
a small scoped re-canary; this review does not authorize or perform a provider call.
