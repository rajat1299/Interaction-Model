# WP16 prompted Qwen sanity run

This is a serialization and configuration sanity check, not a teacher-qualification or policy-promotion result.

## Identity

- Repository commit: `d93b2e8c8f2a33e3ef9b1167e1f903a4fc10bd05`
- WP16 spec: `sha256:722cdfe6b2759d441bfae7387fcff6ed7e053f02c422112df2d423718371e4bc`
- Manifest: `sha256:87c824a2dad3c24fa05f7bd474dd8ef66a87532d3131dd9feb6932a4afee63b5`
- Human review: `sha256:761cb4a5f8c2f6755863741ad1d3c69fd1522073c5b29f3c0efc9bfed184a9e9`
- Prompt template: `sha256:f130c1927f72a073d9a6c9397a65acb9c915d8919c9536aec9cda8d7fd771fa9`
- Model: `qwen/qwen3.6-35b-a3b` via OpenRouter / `akashml`
- Thinking request: `reasoning.effort=none`, `exclude=true`; one attempt per state
- Raw resumable cache: `/Users/rajattiwari/interactionmodel/probes/results/raw/wp16-qwen3.6-35b-a3b-openrouter-akashml.sqlite`

## Observations

- Provider outcomes: `{"completed": 26, "invalid": 4}`
- Schema validity: `26/30`
- Reference integrity: `26/30`
- Objective license allowance: `24/30`
- Structural agreement (diagnostic only): `20/30`
- Actual action distribution: `{"cancel": 1, "idle": 9, "integrate": 4, "invalid": 4, "nudge": 5, "respond": 5, "skip": 2}`
- Population baseline: `{"cancel": 1, "delegate": 1, "idle": 9, "integrate": 4, "mark": 2, "nudge": 5, "respond": 3, "schedule": 1, "skip": 4}`
- Provider attempts: `30`
- Response models: `["qwen/qwen3.6-35b-a3b"]`
- Response providers: `["AkashML"]`
- Routing metadata: `30/30`
- Upstream pin verification: `PASS`

## Thinking-disabled verification

- Request-setting violations: `0`
- Reasoning-usage records: `30/30`
- Provider-reported reasoning tokens: `0`
- Responses carrying visible reasoning: `0`
- Thinking-disabled check: `PASS`

## Usage and cost

- Provider usage: `{"cache_write_tokens": 0, "cached_input_tokens": 0, "input_tokens": 432893, "output_tokens": 948, "reasoning_tokens": 0}`
- Provider-reported cost: `$0.061553`
- Offline expected no-cache estimate: `$0.067805`
- Offline no-cache ceiling: `$0.092525`
- Pricing snapshot (2026-07-14): `$0.14/M input`, `$1.00/M output`; provider billing is authoritative.
