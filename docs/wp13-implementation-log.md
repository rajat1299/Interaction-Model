# WP13 implementation log

## 2026-07-12 — OpenAI-direct dry-run boundary

### Design decisions

- Use the OpenAI Responses API with `gpt-5.6-terra`, standard reasoning mode, and high reasoning
  effort. The clean-context calibration scored Terra high 6/6 versus Terra medium and Luna xhigh at
  5/6.
- Keep provider configuration outside `RuntimeConfig`: runtime config is a frozen integer/string
  hash preimage, while provider model, reasoning, timeout, and output limits are operational policy
  settings.
- Split the frozen prompt template at `{{policy_stream}}`. The behavior spec, action schema, and
  instruction remain one stable system prefix; exact policy bytes occupy the user lane. This
  reconstructs the template byte-for-byte while enabling prefix caching.
- Use an explicit cache breakpoint only after the stable system prefix. This avoids paying a new
  GPT-5.6 cache write for every growing stream snapshot. The cache key is derived from the prompt
  template hash and contains no session/user data.
- Store exact provider request and response bodies in a dedicated `policy_calls` BLOB table. The
  ordinary canonical audit payload has frozen 4 KiB string / 16 KiB object limits and therefore
  cannot hold the approximately 50 KiB static request without weakening model-facing limits.
- Default `max_output_tokens=8192`. This caps reasoning plus visible output spend while leaving room
  for the bounded v1 action payload; the dry-run estimator also reports the cap-based ceiling.

### Deviations and interpretations

- WP13 originally named OpenRouter and a placeholder provider/model. The user ratified direct
  OpenAI usage and selected Terra high after an identical-input calibration.
- OpenAI strict Structured Outputs requires an object root and rejects `allOf` and
  `if`/`then`/`else`. The frozen action export is a bare root union and uses those conditional
  keywords. WP13's already-specified provider fallback therefore applies: request JSON mode,
  preserve the bare action output, validate with `ACTION_ADAPTER`, and retry once. No wrapper,
  flattened parallel schema, or null-stripping conversion path was introduced.
- The old temperature-zero instruction is not sent. OpenAI reasoning is controlled by
  `reasoning.effort`; omitting temperature avoids an unsupported or misleading sampling control.

### Tradeoffs

- Offline tokens use the project's deterministic bytes-div-4 estimate. It is reproducible and
  conservative enough for credit planning, but actual API usage (especially hidden reasoning
  tokens and cache hits) remains authoritative.
- Batch estimates apply the documented 50% Batch discount and assume no cache benefit. Warm-cache
  synchronous cost is reported separately rather than promising that asynchronous scheduling will
  preserve cache affinity.

### Open items

- The live browser acceptance run and transcript are intentionally pending explicit user approval.
  No OpenAI model request was made while building or testing this slice.
- Recalculate WP15 cost from its exact generated manifest after WP14 fixes request counts and prompt
  sizes; today's large-run estimate is planning guidance, not a funding commitment.
