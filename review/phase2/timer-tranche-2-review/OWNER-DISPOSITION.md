# WP2-2 timer tranche 2 — owner disposition

Recorded 2026-07-20. This is a sidecar record; `REVIEW.md` is checksum-bound by `SHA256SUMS`
(`3bc975c9b313e40ae6db9df761bc374983bed4af099e704c0b103572a9b04a23`) and is not modified by this
disposition.

**Verdict: approve 12, flag 1.**

## Dispositions

```text
approved a_064c3dae3e3abe4e7bd7a487 sha256:e20a9b3b9aafeeedf84327182e1cbf972effecfdd4a772b04d67fd66fda4f41e
approved a_1dd4b1f488e74a020e0a0003 sha256:68542fde955db6f51c4482d87afeb1caf84c7939c6ebe578d89c3d7f8cf9c289
approved a_543b664484ba8fff0a5f3ca2 sha256:9e26fb7e1ad3340112274f88c60193a255911359d95db812696a07af947b8da5
approved a_840c2daf8a2204723142feb7 sha256:49d639bd1679ef0fb2686c160978719ec97f5dde9afc950734a5a51de903983c
approved a_9bab50b82eb4b499558fdaba sha256:7da24e60a9726666ef89659e8821815ed9ec90aa575db0fcb5708719c1d95dae
approved a_9d4278e5ace95912cec8d008 sha256:bb26daf67e55d38c6193f8c0b25ce1e8108d96808f00d017defb45da5a8b67e1
approved a_aac54a3e094340a9ef8db18a sha256:faa050848dda490b55ffe255ed7dfd2cdf500f1412ed30be1fb41668d1cffb1b
approved a_b2a1ca0b7e647ec77411d143 sha256:fe959077a6e6c3bb2c9d7a0b0c34633a99721ef501b091421df2eb6ba109be21
approved a_b3d1cce13050d3f8d4215602 sha256:14b57622af88fa9193344dcd8ad074bd965cd28c868e93983eb0fb25f9f81047
approved a_b70fe1deb0d2acee5612b5b1 sha256:64b953dd33436eb01c9911164baeb1df26db3f2d8af4adb9bfc9fd1838bce51f
approved a_f1542b0c1ef44c3e389aaee8 sha256:aeadf145a924d26c9fcb795ac5d37140a8cc8f1bc998613f02d8d7e883bc537a
approved a_f80089215d4c52eca01e39ab sha256:3ca7be22913ae5c16242947aa20baa33d18c9fcfe6b08c8a3266ff7d6fcdf19b

flagged  a_bf812f9b9f149490915e6de0 sha256:375230a68a66bc68ce0ffb9e5a4b13f8d62d0e8fbc2be2057d25f96f850409d9
```

Seal the 12 approved records. Wave 0 may proceed on approved assets; the flagged record is
unusable until its scoped re-review passes.

## Flag — cross-split near-duplicate

`a_bf812f9b9f149490915e6de0` — *"Remind me once in twenty-three minutes to close the lilac case."*

This shares both its sentence frame and its interval word with the sealed TEST unsupported timer
*"Remind me once in twenty-three minutes to tune the sun clock."* A registry scan confirmed this is
**the only `once in` asset in the entire corpus** — the two would be the only instances, and they
differ solely in the object phrase.

Why it blocks rather than passes: TEST holds exactly **one** example of the unsupported-one-shot
subtype. If TRAIN teaches a near-identical frame, TEST cannot distinguish a model that learned the
one-shot boundary from one that memorized the frame — on the only measurement it has for that
subtype, in a permanently sealed artifact. The cost asymmetry is decisive: one reword now versus an
unfixable evaluation weakness later.

Repair: reword with a different interval **and** a different construction — e.g. *"Set a single
reminder forty minutes from now to close the lilac case."* — then return that one record for scoped
re-review. This also improves TRAIN, yielding three distinct unsupported surface forms across the
corpus instead of two constructions with one duplicated.

## Data verified — no defects

The packet omitted `interval_ms` and `message`, so these were checked directly against
`candidate-assets.jsonl`:

- Six supported timers, interval arithmetic exact: 97 → 5,820,000 · 43 → 2,580,000 ·
  73 → 4,380,000 · 71 → 4,260,000 · 19 → 1,140,000 · 67 → 4,020,000 ms.
- Messages correctly stripped of the terminal full stop, per the frozen extraction rule.
- Both unsupported and both negated records correctly carry `interval_ms: None`, `message: None`.

## Wave-0 scenario invariants

These are correctness conditions for the scenario builders, not process. Verify each at wave 0
before any teacher request for this cluster.

1. **`a_064c3dae3e3abe4e7bd7a487` (ambiguous-cancel template)** must render at least two active
   timers, **no unique antecedent or positional anchor that resolves "it"**, and an active floor
   when the target is `idle(ambiguous)`. Post-yield, the same unresolved request requires one
   clarification response. A scenario that accidentally makes "it" resolvable silently stops testing
   ambiguity. This prevents recurrence of the sentinel's paused-render template defect.
2. **Negated assets** (`a_b3d1cce13050d3f8d4215602`, `a_f80089215d4c52eca01e39ab`) require that
   **no equivalent active timer exists** when used as negated-schedule restraint examples. With a
   matching active timer in scope, "don't remind me every twenty-nine minutes to rotate the ivory
   tray" reads as a *cancellation request* rather than a refusal to create — two distinct boundaries
   collapsing into one.
3. **Unsupported assets must never be approximated.** `a_9bab50b82eb4b499558fdaba` must not become a
   recurring daily timer; the reworded one-shot must not lose its single-occurrence marker and
   become a recurring timer. Per the frozen spec: never approximate an unsupported request with a
   different schedule.

## Packet fixes

1. **Rendering regression.** Timer rows must render `interval_ms` and `message`; templates must
   render a representative expansion. Verification required reading the JSON directly — interval
   falsification killed seven G7 streams, and template source alone is not reviewable by standing
   rule.
2. **Near-duplicate scan gap.** Extend the cross-split scan to short instructions: normalize out the
   object noun phrase, or n-gram the instruction skeleton, so a shared frame differing only in its
   object is caught mechanically rather than surviving to human review. This gap is the sole reason
   the flagged record reached this packet.

## Minor — no action this tranche

Intervals 71 and 73 are reused from sealed TEST/DEMO supported timers. Low risk, since the supported
frame is high-volume and the model must generalize across intervals regardless — but draw future
tranche intervals disjoint from sealed splits.

## Review provenance

Two independent reviews. The second reviewer, working from `REVIEW.md` alone, approved all 13 and
contributed the three wave-0 scenario invariants above. It could not have detected the cross-split
duplicate or verified interval arithmetic, since neither the sealed registry nor `interval_ms` is
visible in that file — which is also why packet fix #1 matters. The flag stands on registry evidence.
