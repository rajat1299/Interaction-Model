# WP2-2 timer tranche 2 scoped repair — owner disposition

**Authority.** This is the project owner's decision, given on 2026-07-20 and transcribed here by the
reviewing assistant at the owner's explicit instruction. The assistant's role was analysis and
transcription; the approve/reject decision is the owner's.

**Recording method.** Sidecar only. `REVIEW.md` is checksum-bound by `SHA256SUMS`
(`915bcd33669d9245e7c09b7a38ecec4f50298800b699aa4d3b9f20154e92dc91`) and is not modified here.

## Disposition

```text
approved a_bf812f9b9f149490915e6de0 sha256:cc08aea9c4ea639c7d55acd9465d09f98a04796ebd79e4dbb4b7825b1faf5954
```

## Why the repair resolves the flag

Replacement text: *"Set a single reminder forty minutes from now to close the lilac case."*

The flag was a cross-split near-duplicate against the sealed TEST unsupported timer
*"Remind me once in twenty-three minutes to tune the sun clock."* The repair changes both axes the
flag named:

- **Construction** — different verb (`Set` vs `Remind me`), different one-shot marker (`a single` vs
  `once`), different temporal form (`forty minutes from now` vs `in twenty-three minutes`). The
  shared frame is gone, not paraphrased.
- **Interval** — forty vs twenty-three.

Mechanically verified against the sealed registry: `from now`, `single reminder`, and
`forty minutes` each occur **zero** times. The construction is novel to the corpus.

Subtype correctness is preserved: `a single reminder` is an unambiguous one-shot marker, so the
instruction remains unsupported under v1 (which supports only indefinite fixed-interval recurrence),
and `interval_ms: None` / `message: None` are correct. There is no reading under which this becomes
a recurring timer.

Coverage improves as intended. TRAIN now carries two structurally distinct unsupported forms — an
absolute clock time (`a_9bab50b82eb4b499558fdaba`, "Remind me at 6:40 PM…") and this relative
one-shot — and the corpus as a whole carries three distinct unsupported surface constructions across
splits rather than two with one duplicated.

## Seal state verified at disposition time

- Cumulative TRAIN seal: **101** entries (89 tranche-1 passing records + 12 approved timer assets),
  confirming the seal-semantics correction landed — all passing records seal, not only the reviewed
  sample.
- TEST seal 24 entries, DEMO seal 29 entries, both **byte-identical** since `phase1-close`
  (empty diff), satisfying D14.
- The superseded digest `375230a68a66bc68ce0ffb9e5a4b13f8d62d0e8fbc2be2057d25f96f850409d9` remains
  explicitly rejected and unsealed in registry history.

## Carry-forward

Wave-0 scenario invariant #3 applies to this asset: it must never be approximated into a recurring
timer. The load-bearing token is `a single` — a scenario that drops or weakens it converts an
unsupported-boundary example into a supported one and inverts the expected action.

With this approval the timer tranche is complete: 13 of 13 records approved (12 direct, 1 after
scoped repair). Remaining wave-1 preconditions are unchanged and listed in the consolidated
dispositions entry of `review/phase2/implementation-log.md`.
