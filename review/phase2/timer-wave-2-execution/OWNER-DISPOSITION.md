# WP2-2 timer Wave-2 — owner disposition of non-equivalences

**Authority.** The owner approved the exact aggregate disposition in conversation. This sidecar
transcribes that decision; the assistant supplied the raw-output analysis and category proposal.

**Recording method.** Sidecar only. The checksum-bound review packet is unchanged. Its evidence is
`sha256:b35597214bab16a080b820873f82fe6a66b3d2f0719efba930d8996d53643e26` and its
provider comparison is
`sha256:ae117b9a41becac8132ef5340b8727b74d54fe2361a7d2cf668e5be541811e56`.

## Owner disposition

The 97 oracle/teacher non-equivalences are approved as:

- **52 `oracle_error`**
  - 34 quoted or reported reminder commands labeled `idle(no_trigger)` instead of
    `idle(instruction_not_direct)`.
  - 18 visible consumed-subject tails labeled `idle(no_trigger)` instead of
    `idle(already_handled)`. Two teacher alternatives identify the wrong handled subject, so their
    repaired human labels must use the canonical lowest-policy-sequence subject rather than either
    candidate verbatim.
- **28 `template_error`**
  - 23 reminder extension/confirmation races that do not preserve the approved 3–5 second
    post-confirmation boundary or a clear additional-versus-replacement instruction.
  - 5 rollover rows whose oracle ordering acts before the concrete stale result is skipped. Three
    teacher alternatives skip the wrong stale result, so neither candidate is exact.
- **17 `teacher_error`**
  - 8 contention mark decisions.
  - 5 “second active reminder” cancel decisions.
  - 1 canceled-reminder fire that should be skipped.
  - 3 rollover mark decisions.

The five neither-candidate-exact rows remain in the approved root-cause categories above but require
new human labels during scoped repair; no provider-authored alternative is promoted as gold.

## Gate status

Non-equivalence adjudication is complete. No affected template/oracle row is training-eligible until
its scoped repair passes. Teacher-error rows remain human-labeled and their cells remain UNCLEARED.
The 551 matching mandatory-review routes still require the planned fast coherence pass, so Wave-2
whole-stream acceptance and Wave 3 remain blocked. No new provider call is authorized by this
sidecar.
