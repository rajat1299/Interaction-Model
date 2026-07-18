# Phase 1 closeout report

Phase 1 closed on 2026-07-18 by project-owner adjudication. G-1 is an explicit Option B
quantitative failure against the frozen single-user reference profile; it is not reported as a
distribution match. G-2, G-3, G-5, G-6, and G-7 pass. G-4 is accepted by the project owner from
the existing WP1-3 sampler-harness fixture evidence, with no new closeout measurement. The WP1-9
teacher canary, template repair, re-canary comparison, and disagreement review are complete.

## Gate outcomes

| Gate | Outcome | Evidence and closeout statement |
|---|---|---|
| **G-1 Distribution match** | **Closed — Option B fail** | The final one-shot result is [`calibration-trace-analysis.json`](calibration-trace-analysis.json). The non-binding owner record is [`blind-replay-owner-judgment.md`](blind-replay-owner-judgment.md), with the privacy-preserving packet in [`blind-replay-documentation/`](blind-replay-documentation/). Phase 2 uses the trace-resampled generator despite the formal failure because it is the best measured implementation and the only fitted population that passed decision rate. |
| **G-2 No heuristic action in teacher-visible artifacts** | **Pass** | The sealed readiness [`leak-lint.json`](g7-readiness-resubmission-2/leak-lint.json) and final-canary [`leak-lint.json`](teacher-canary-recanary/packet-final/leak-lint.json) pass. Teacher input is checksum-bound canonical-stream material; sidecar/oracle facts remain outside the prompt lane. |
| **G-3 Runtime faithfulness** | **Pass** | The sealed packet [`REVIEW.md`](g7-readiness-resubmission-2/REVIEW.md), [`manifest.json`](g7-readiness-resubmission-2/manifest.json), and [`SHA256SUMS`](g7-readiness-resubmission-2/SHA256SUMS) bind the canonical streams, runtime ledgers, sidecars, checkpoint segments, and validation evidence. |
| **G-4 Sampler equivalence** | **Accepted by owner** | Existing WP1-3 evidence is the production sampler harness and its fixture/comparison tests in [`sampler-harness.ts`](../../client/src/sampler-harness.ts) and [`sampler-harness.test.ts`](../../client/src/sampler-harness.test.ts). Per the closeout instruction, no new measurement was made. This is owner acceptance of the existing fixture evidence, not a claim that Phase 1 added an independent real-browser capture. |
| **G-5 Twin integrity** | **Pass** | Twin/counterfactual units and their all-or-nothing linkage are bound by the readiness [`manifest.json`](g7-readiness-resubmission-2/manifest.json), [`source-index.json`](g7-readiness-resubmission-2/source-index.json), and [`split-ledger.json`](g7-readiness-resubmission-2/split-ledger.json); the packet passed the one-axis twin and provenance validators. |
| **G-6 Reducer fidelity** | **Pass** | The integrated WP1-8 reducer test is [`reducer-fidelity.test.ts`](../../client/src/review/reducer-fidelity.test.ts). Stream-derivable fields had zero divergences on the canary; unavailable fields are shown as absent or overlaid from the checksum-bound sidecar instead of being guessed. The final canary was reviewed end-to-end through the shell. |
| **G-7 Yield readiness** | **Pass** | [`g7-readiness.json`](g7-readiness-resubmission-2/g7-readiness.json) proves the exact 2,000-decision allocation is reachable; [`throughput.json`](g7-readiness-resubmission-2/throughput.json) records five 2,000-action batches, 10,000 selected actions total; the complete packet checksum inventory passes. |

## G-1 calibration finding, fix, and residuals

The first fitted population exposed a real synthesizer defect: revision locality had a 72-character
median and 290-character p90 versus 12 and 120 in the recording, accompanied by backspace-run and
decision-cadence deltas. Parametric timing fitting was terminated after two strikes. The shipped
generator instead uses seeded, regime-conditioned interval-level timing resampling with jitter;
recorded text never enters generation. Revision behavior uses two explicit modes: immediate
cursor-local corrections dominate by count, while deliberate line-to-paragraph look-backs are a
minority design stratum.

Timing material is split inside every physical recording bundle. Both cursor/selection takes are
retained as separate atoms. Burst-aligned first approximately 60%, next 20%, and final 20% slices
feed train, dev, and test timing pools respectively, so no timing interval crosses splits while all
six regimes remain represented. The benchmark side is computed from the seven complete physical
recordings across six regimes; the final verification population draws from train slices. This can
expose within-session drift, including fatigue, without authorizing another fit.

The fixed one-shot analyzer result is a global failure with no pending or unavailable metrics:

| Observation | Synthetic | Recorded | Result |
|---|---:|---:|---|
| Decisions per minute | 58.969 | 54.277 | Pass |
| Snapshots per decision, p10/p50/p90 | 1/3/5 | 1/2/4 | Fail |
| Event contention rate | 0.7173 | 0.6348 | Fail |
| Immediate-mode revision locality, p10/p50/p90 chars | 0/7/255 | 0/12/120 | Fail |
| Backspace-run length, p10/p50/p90 | 1/1/6 | 1/1/7 | Pass |
| Per-snapshot text-length change, p10/p50/p90 | 0/1/2 | 0/1/2 | Pass |
| Snapshot cadence p90 | 509 ms | 823.7 ms | Fail |
| Exact cursor position p10 | 30 | 20 | Fail |

All six regime-conditioned comparisons fail; five also fail at least one policy-layer band. The
residual policy contention, arrival density, cadence, cursor-position, and immediate-locality
deltas are recorded rather than adjudicated away. The report makes no claim that the trace
population distribution-matches this profile.

Descriptive arithmetic on the existing run separates the designed revision modes without another
analyzer invocation. The immediate lane contains 51,635 per-event observations at 0/7/255
characters versus 0/12/120 recorded. The 933 look-back transactions have first-revision locality
25/198/319 characters and are a designed minority stratum, not banded against the n=1 profile.
Transaction annotations count 5,488 immediate corrections and 933 look-backs; those transaction
counts are intentionally different from the per-event observation count.

The owner selected the recorded side in 13/20 blind pairs and the synthetic side in 7/20, with no
indistinguishable choices. Cursor/selection was identified in all 3/3 pairs and described as too
fast or unnatural. The forced-choice instrument did not ask whether each synthetic trace was
plausible, so the former 16/20 plausibility criterion cannot be reconstructed or claimed. Text
redaction also made the task harder. The blind result is non-binding documentation and does not
change G-1.

## WP1-9 teacher canary and WP1-8 review

The real `gpt-5.6-terra` high-reasoning canary covered 265 decisions in 38 parent streams from 27
cross-family source units. The completed five-shard Batch run cost `$1.634885000`. The final
identity-preserving repaired packet is [`packet-final/`](teacher-canary-recanary/packet-final/),
checksum inventory
`sha256:caf3dbfef78774ae5e73e72fcbc7cb03229d55730060009c4a6bef1a1bcb37a8`.

All 265 raw responses re-parse fail-closed. After the narrow template repair, 215 are exact
automatic passes and 50 require the existing disagreement review. The completed WP1-8 record is
[`execution/sharded/review/README.md`](teacher-canary-recanary/execution/sharded/review/README.md):
7 decision accepts, 43 rejects, 0 flags; at whole-stream scope, 6 accepts and 21 rejects. The five
former template flags are now exact automatic passes. No replacement provider call was necessary
because all 265 teacher-visible requests and five shard inputs were proven byte-identical; only the
five reviewed oracle actions changed.

The canary protected the Phase 2 spend exactly as intended: it found and repaired a narrow oracle
contract defect, while the 43 remaining teacher errors demonstrate why raw teacher output cannot
be admitted without causal review and whole-stream disposition. D2 funnel steps 1–3 are complete.

## Cleanup and retained core

Cleanup commit `6b1b4a8` removed the v4/preflight manifest program, evidence-admission and
source-authority machinery, blind-withholding logic, superseded adjudicated report generators, and
second-population architecture. Parametric timing fitting was deleted. The retained core is the
three-layer analyzer and pre-registered bands, family drift and regime comparisons, latency-stub
policy mode, all seven recordings plus transport-failure fixtures, seed/SHA-256/commit provenance,
and the G7 stream-semantics validators, leak lint, split ledger, and causal review packet contract.

The final repaired-canary artifact and bindings landed in commit `a00c6e7`. No evidence-admission
taxonomy or new closeout gate was introduced.

## Known limitations

- The reference is one user (`n=1`): seven physical bundles across six regimes. The second
  cursor/selection take completes the recording protocol; it is not an independent user.
- Full-session reference metrics versus train-slice synthesis can expose within-session drift.
- G-1 failed globally and in all six regimes; the trace-resampled generator is an engineering
  handoff choice, not a statistical-pass claim.
- The blind packet's redacted text and forced-choice form limit the human interpretation.
- G-4 was accepted from existing WP1-3 fixture evidence; Phase 1 did not add a new independent
  real-browser comparison.
- The teacher canary covers approximately 5–10% per family, not the full label corpus, and 43 of
  265 teacher actions were non-equivalent to the oracle.

## Found, deferred

- Make cursor/selection movement less fast and mechanically recognizable.
- Investigate pre-coalescing arrival-density and policy-contention residuals without changing the
  frozen Phase 1 verdict.
- Strengthen G-4 with an independent real-browser fixture.
- Replace the single-user reference with a multi-user deployment mixture only in a future phase.

These are report findings, not authorized Phase 1 code work.

## Phase 2 handoff

Phase 2 receives the trace-resampled generator with the two-mode revision model and split-scoped
timing pools; seed-deterministic generation with SHA-256 and commit provenance; packaged pilot,
readiness, and canary artifacts with manifests, sidecars, split ledger, and leak lint; the WP1-8
review shell and causal decision sidecar; the calibration verdict and family-drift tooling; and the
stress/overload population routed aside for Phase 6.

D2 steps 4–6 are the Phase 2 operating procedure:

1. Treat systematic disagreement as a template/oracle defect and repair it before scale labeling.
2. Label a complete family only after its repair canary is accepted.
3. Run post-label disagreement review and dispose at whole-stream scope; do not salvage prefixes
   from rejected streams.

Every new batch reruns the leak lint, stream-semantics validators, split checks, and family-drift
report. Teacher labeling reuses the existing WP15 request-identity, caching, Batch, and provenance
harness. The trace-resampled generator is the Phase 2 generator irrespective of G-1's formal
Option B verdict.
