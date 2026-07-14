# WP16 implementation log

## 2026-07-14 — Offline Qwen sanity-run setup

### Design decisions

- WP16 uses the existing production prompt renderer, Responses request builder, action decoder,
  reference validator, objective license, trace retention, and resumable cache. There is no Chat
  Completions adapter and no second action-decoding path.
- `PromptedPolicyConfig.provider` selects provider capabilities inside the one request builder.
  OpenAI retains its explicit-cache fields. OpenRouter omits those OpenAI-specific fields, adds
  `reasoning.exclude=true`, and accepts an explicit upstream-routing object.
- The run is exactly 30 canonical `v1` states: 15 complete counterfactual twin pairs. It includes
  `t01` from Families 1–10, four distinct rollover projections from Family 11 (`t01`, `t03`,
  `t04`, and `t05`), and `t01` from Family 12. This covers all twelve families and every member of
  the nine-action union while retaining a nearby counterfactual for every selected state.
- WP16 is generation-only in the literal protocol sense. It invokes neither pairwise/listwise
  recognition nor an open-text semantic grader. Open-text semantic quality and structural agreement
  may be reported as diagnostics, but this run is not a teacher or policy promotion evaluation.
- Each state gets exactly one provider attempt. A corrective retry would hide the first-pass schema
  base rate that WP16 is intended to measure.
- The model is `qwen/qwen3.6-35b-a3b` through OpenRouter's stateless Responses endpoint. Upstream
  provider `akashml` is pinned with `allow_fallbacks=false` and `require_parameters=true` so one
  committed report does not silently mix provider implementations.
- Thinking is disabled with `reasoning.effort=none` and suppressed with `exclude=true`. The report
  independently checks the exact request setting, provider-reported reasoning-token usage, visible
  reasoning output items/fields, and `<think>` payload leakage.
- Live requests opt into `X-OpenRouter-Metadata: enabled`. The report requires one selected
  `AkashML` endpoint in each response's routing metadata; a body-level provider allowlist alone is
  not treated as observation of the serving upstream.

### Tradeoffs

- AkashML's pinned no-cache rate (`$0.14/M` input, `$1/M` output on 2026-07-14) matches the model
  page's headline rate. Provider billing remains authoritative and is read from retained response
  usage when available.
- The population is deliberately balanced by scenario twins and contract coverage, not by expected
  action frequency. Both the expected population baseline and the model's actual action distribution
  are reported, so the unequal idle/action counts are visible rather than reweighted.

### Offline verification

- WP16 spec identity:
  `sha256:722cdfe6b2759d441bfae7387fcff6ed7e053f02c422112df2d423718371e4bc`.
- The frozen selection contains 30 distinct probes, all twelve families, and all nine actions.
- The mocked generation-only run makes 30 generation calls and zero semantic, pairwise, or listwise
  calls. Every mocked action passes schema, reference, and license validation.
- The amended offline plan estimates 441,464 input tokens and 6,000 expected output tokens. Pinned
  no-cache cost is `$0.067805`; the 1,024-token-per-response ceiling is `$0.092525`.
- The task-domain Sol review found and closed four launch blockers: mock/live cache contamination,
  missing exact-key recovery for indeterminate calls, missing proof of the selected OpenRouter
  upstream, and treating absent reasoning-usage evidence as zero. Its focused re-review found no
  remaining P1–P3 issue.
- Ruff is clean and the full repository suite passes: 467 tests, with only the existing third-party
  Starlette deprecation warning.

### Open boundary

- Estimate and mocked modes require no credential and perform no network call. Live mode prints the
  estimate first, requires explicit cost acknowledgement, then requires the OpenRouter key and a
  clean tracked worktree.
- Mock and live modes use distinct default cache files. Live evidence additionally requires exactly
  one retained provider trace and one explicit reasoning-token usage count per state, so even an
  operator-supplied cache path cannot turn trace-free oracle results into a live report. An
  indeterminate network outcome can be retried only by explicitly authorizing its exact cache key.
- The live report and its raw-cache evidence do not exist yet. WP16 is not complete until that
  approximately ten-cent run is executed, reviewed, and committed.

## 2026-07-14 — Live-provider preflight amendment

### Design decision

- The originally pinned Parasail endpoint was mechanically excluded by OpenRouter's authenticated
  account policy before inference (`attempt=0`, zero tokens). AkashML serves the identical canonical
  Qwen checkpoint at FP8, supports the same required reasoning and structured-output parameters,
  and was verified through the Responses endpoint with `reasoning_tokens=0`. WP16 is therefore
  repinned to `akashml`; the probe population, behavior contract, prompt, and model are unchanged.
- The live artifact filenames now include `akashml`. This keeps the new provider run separate from
  the five zero-usage indeterminate records retained during the Parasail routing diagnosis.

### Tradeoff

- Repinning changes the WP16 run identity and requires a new spec hash, but avoids weakening privacy
  settings or silently allowing provider fallback. A verified fixed upstream remains more important
  than preserving an endpoint that the account cannot route to.
