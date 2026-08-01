# WP2-2 timer Wave-1 — owner disposition and repair closure

**Authority.** The owner reviewed the Wave-1 packet, exported the decision file, corrected the
identified rows in conversation on 2026-07-21 and 2026-07-22, approved the exact replacement
limitation text, and authorized the scoped repair calls. This sidecar transcribes those decisions.
The assistant's additional role was to run the authorized falsification canaries and apply the
already-ratified D1–D3 rules; empirical findings below are labeled separately and do not imply a new
owner decision.

**Recording method.** Sidecar only. The checksum-bound review packet is unchanged. Its evidence
file is `sha256:66a7ffcf669846967ef34997aca5f7b9f2c2bb86203fef1aaea421ff40f6a210`.
The corrected owner export is
`sha256:da67e2a09805f3c58ae5509440000b52ec12cfafce04a11eb49975415870343c`.

## Owner disposition

- Accept the reviewed decisions except for the attributed cases below.
- The seven post-schedule `already_handled` disagreements are one pre-repair prompt ambiguity, not
  seven independent teacher failures. Their human label is `idle(no_trigger)`; none enters a D1
  qualification window under prompt v1.
- The rollover instruction-span disagreement remains a genuine `teacher_error`: the teacher starts
  and ends one UTF-16 code unit early. Its cell remains locked UNCLEARED for Phase 2.
- The original `normal-compact-a` and `normal-wide-a` streams are `template_error` and are excluded
  from training eligibility (`whole_stream_accepted=false`):
  - `sha256:f2f2beceb6faed2db08f12af235fdb1787a104a76e596862faa4e3933fb305c4`
  - `sha256:ffa9c61e296a79556a2c47a7620d7e2243afc1ef46de8bbec62969e4bb7ae1f7`
- Their replacement semantics are state-dependent. After a successful confirmation, an explicit
  additional instruction creates a second reminder; replacing the single visible sentence requests
  an unsupported modification and receives the owner-approved TRAIN response candidate 5:

  > I can’t change an existing reminder. Please cancel it and create a new one.

## Scoped repair evidence

Prompt v2 (`sha256:84f02c6a942f539b48541f477bfe86ca9beab1a81851309509d40b0ac87cb4db`)
was tested in Batch `batch_6a6057f5177c8190b0542b8c6e43da0e` for `$0.052973250`.
Its comparison is
`sha256:eb6f4eb45c0166f61366c1feb89802ef5cea90524af951085ccaffbb05d6a1c9`.

- All four frozen, byte-distinct post-schedule failure prefixes matched `idle(no_trigger)`.
- The delayed explicit “another reminder” request matched the second `schedule` exactly.
- Consumed `integrate` and `skip` subjects matched `already_handled`.
- The replacement selected `respond` for the correct snapshot. Its provider-authored prose is
  ineligible under D2 and is replaced by owner-approved candidate 5.
- Retained-response and handled-fire tails still returned `no_trigger`, so v2 did not close the
  prompt repair.

Prompt v3 (`sha256:31bea45fa5639c1eae8ad411779262d027bc705b499cf5eda3437a76a6d49ec9`)
added only the general invariant that visible event consumption persists across inert later text.
It named no target class, event ID, output label, or precedence. Batch
`batch_6a605cd039148190ab98791a4ff0c536` cost `$0.02696006250`; its comparison is
`sha256:1e0c8cb59d3ea8b3a6082c635b8effb91a24b6433d2df121908c6ade564334a1`.

- The handled timer-fire tail changed to the required `already_handled`.
- The frozen post-schedule control remained `no_trigger`.
- The retained responded-snapshot tail still returned `no_trigger`. Prompt refinement stops here:
  this is a confirmed `teacher_error`, not justification for more steering. The affected
  `generation × timer_creation_normal_fire × closed` cell is locked UNCLEARED for the remainder of
  Phase 2 and remains human-labeled.

## Gate result

The Wave-1 repair gate is closed with no unresolved `contract_gap`. Prompt v3 is the current timer
generation prompt. Passing canary rows begin a new v3 evidence window but do not clear any cell;
D1 still requires 30 reviewed decisions across five source units and three templates. Mandatory D2
review and every permanent-UNCLEARED rule remain unchanged. Wave 2 may proceed with the two original
malformed streams excluded and the retained-response teacher weakness explicitly routed to human
review.
