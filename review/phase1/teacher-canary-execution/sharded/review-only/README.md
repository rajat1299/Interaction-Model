# WP1-9 teacher canary: quarantined review-only labels

**Not an official teacher-label corpus. The canary failed closed.** This directory exists only so
WP1-8 can display the 263 valid retained responses for disagreement review. It must never be used
for training, corpus admission, or a claim that the 265-decision canary completed successfully.

- Valid retained labels: 263/265
- Automatic passes: 179
- Causal disagreements: 77
- Semantic-review cases: 7
- Invalid/missing labels: 2
- Provider calls made to create this directory: zero
- Source provider cost: `$1.6182388750`

To exercise WP1-8, load `review/phase1/teacher-canary` as the packet directory and then import
`teacher-labels.review-only.jsonl` as teacher labels. The shell should report 84 unresolved
disagreements. The two invalid decisions are deliberately absent and remain failures:

- `tc0.0d7964b15c8f169715feb75e4845337c5720f68ae799449c448d4b6349bde197.c0004.a1`: stream `sha256:0d7964b15c8f169715feb75e4845337c5720f68ae799449c448d4b6349bde197`, call 4, policy seq 10; `ValidationError: 1 validation error for tagged-union[function-after[validate_related_event(), IdleAction],MarkAction,DelegateAction,IntegrateAction,SkipAction,RespondAction,ScheduleAction,CancelAction,NudgeAction]
schedule.instruction
  Value error, span text length does not match its UTF-16 range [type=value_error, input_value={'end_utf16': 147, 'event...or the cistern sketch.'}, input_type=dict]
    For further information visit https://errors.pydantic.dev/2.13/v/value_error`
- `tc0.15dba05b27b3d92dd5fa56659352c64ec85f96f116926593a007e1f7ce73509b.c0004.a1`: stream `sha256:15dba05b27b3d92dd5fa56659352c64ec85f96f116926593a007e1f7ce73509b`, call 4, policy seq 10; `ValidationError: 1 validation error for tagged-union[function-after[validate_related_event(), IdleAction],MarkAction,DelegateAction,IntegrateAction,SkipAction,RespondAction,ScheduleAction,CancelAction,NudgeAction]
schedule.instruction
  Value error, span text length does not match its UTF-16 range [type=value_error, input_value={'end_utf16': 124, 'event...or the notebook draft.'}, input_type=dict]
    For further information visit https://errors.pydantic.dev/2.13/v/value_error`

## Completed disagreement review

`review-decisions.jsonl` is the WP1-8 review sidecar. It records all 84 valid disagreements plus
the two invalid decisions, followed by one D2 whole-stream outcome for each of the 28 affected
streams. It remains review evidence only and does not turn the partial labels into a corpus.

- Valid disagreements: 7 accepted as equivalent, 32 rejected as non-equivalent, 45 flagged for
  oracle/template repair.
- Invalid teacher outputs: 2 rejected and retained as missing labels.
- Whole-stream outcomes: 6 accepted, 20 rejected, 2 flagged.
- Provider calls made during review: zero.

The flags cluster in five repeatable problems: quoted-command idle reasons; bare lookup-trigger
ambiguity; retained-need, topic-change, and conflict-order handling; nested-versus-wrapper schedule
spans; and one unquoted behavioral-filler stream. These findings block a full Phase 2 labeling run
until the affected templates/oracles are repaired and the canary is rerun with separate owner
authorization for any new provider call.

Source bindings:

- `9211cc880c816c038580e0831d2386018f49ba8d6661884d4f09b04c7a4f9701  review/phase1/teacher-canary-execution/sharded/failure.json`
- `de07e04460378f4526febdd6c70ab5047fae6a55237b9c39cff154f61b58d866  review/phase1/teacher-canary-execution/sharded/plan.json`
- `0f4a19b73a0c830882c5e1a3a261eaee4e840341d3f557c289bf03bfdb3c0163  review/phase1/teacher-canary-execution/sharded/shards/tc0-0000-d8863242bb19/provider-output.jsonl`
- `fa70f32b67433d8967072bbe32c7ec202e2f2f4f9b5ba1e42ab2c85e2ab6bfa1  review/phase1/teacher-canary-execution/sharded/shards/tc0-0001-14089f73ba3c/provider-output.jsonl`
- `0f4b56f4c421b579b9b7149082b11cc3f979ca68fbabf66db0023daa46ad96fa  review/phase1/teacher-canary-execution/sharded/shards/tc0-0002-7f3dce05f936/provider-output.jsonl`
- `72d2d25ab92a36de2d79e25c9e9c0e328343a002c5adfeb54bdea9cccf1d5df8  review/phase1/teacher-canary-execution/sharded/shards/tc0-0003-3619236d1eeb/provider-output.jsonl`
- `e9b6852bae9d724eea2b58635429012fd632068dc61d933965a6ed34aa8ba043  review/phase1/teacher-canary-execution/sharded/shards/tc0-0004-571cd4ba8510/provider-output.jsonl`
