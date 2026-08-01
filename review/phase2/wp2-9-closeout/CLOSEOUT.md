# WP2-9 training-input freeze closeout

**Status: CLOSED — 2026-07-31**

## Interaction corpus

- 354 whole streams, exactly 2,000 decisions.
- All eight frozen objective terms solved to `Optimal` with zero MIP gap; the published selection
  rebuilds exactly from the artifact adapter.
- D13 covers 2,000/2,000 decisions: 512 `human`, 1,488
  `oracle_teacher_agreement`, 0 `teacher_auto_trusted`, 0 unresolved.
- Generated-versus-accepted bias is published. The owner accepted the disclosed
  `mark_lifecycle_negative` concentration without rebalancing.

## Replay corpus

- Exactly 1,000 native-chat rows: 500 short, 350 medium, 150 long.
- Exactly 200 multi-turn rows and 100,003 supervised final-assistant tokens.
- Exact frozen family quotas hold across all 11 families.
- 461 selected rows were in the final review queue; every one has explicit owner approval or
  approval under the owner's delegated technical-code review.
- 42 selected rows are checksum-bound, project-authored offline recovery rows; all 42 received
  100% review. No provider call was made for any recovery row.
- Deferred overlap, nonce, heldout, and protocol-vocabulary filters were rerun. Three rows were
  excluded by the closed filter. The 165-row unused accepted reserve is archived and is not part
  of the training input.
- Source lineage and licenses are recorded per selected row. Because the frozen corpus contains
  No Robots material, any released subset remains subject to CC-BY-NC-4.0 attribution and
  non-commercial terms.

## Bindings

| artifact | SHA-256 of `SHA256SUMS` |
|---|---|
| Stage-2 interaction selection proof | `c6099c8ed5c3644c9581b725efa56a47fe7346e7ad2b23ed48ff19d43ce69503` |
| D13 closure | `a817f50250631dd065630592e32b3db8097f34e79485b8a3de61f9f6c6692d0e` |
| Generated-versus-accepted bias report | `c42916d2b0acc9c206c9c408f87348dbcd67add7a91b35520ed6e2b124c4aeca` |
| Replay freeze | `34416be84c30e45deef96498c8035b7921f0455f49e998e101df4ff6483d0b31` |

The DEV freeze remains bound at
`sha256:35308dab6b8d6986a8ed06eec3e57e6b352c7dd717f478aef3b2c5ba945fa894`.
WP2-10 must scan its newly generated TEST states against this replay freeze before issuing the
final TEST seal; that downstream requirement is not part of WP2-9.

