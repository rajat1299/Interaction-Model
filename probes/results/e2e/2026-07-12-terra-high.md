# WP13 live browser acceptance — Terra high

## Verdict

PASS. A single browser session executed and rendered the required `mark → schedule → cancel`
sequence through the production sampler, server, prompted policy, license layer, timer ledger, and
render sink.

## Run identity

- Local date: 2026-07-12 (America/Chicago)
- UTC window: 2026-07-13T04:38:41.469093Z–2026-07-13T04:40:16.471905Z
- Repository commit at start: `a97022a`
- Session: `s_0aa5c18e91744f47ba4397c91a06321a`
- Browser: Codex in-app browser at `http://127.0.0.1:5173/`
- Model: `gpt-5.6-terra`
- Reasoning effort: `high`
- Maximum output tokens: 8,192
- Provider attempts: 12 completed HTTP 200 calls; zero corrective retries

Artifact identities:

- Schema: `sha256:321dc69f81573f9711fb8c77d962253677eaf4c4a022e6df10f67653df75680d`
- Behavior spec: `sha256:14f17314ae82c19779544be70a0566a191238d79537059d82c4d5a8b6bcd1639`
- Prompt: `sha256:f43aeb517904481ad0bd22048ca1f179dfd162907ff0fbe66fdc792f40bed645`
- Runtime config: `sha256:007c2c5507273f74d98b92d4feeb6c9416b3aac2b4dafab89780efdb0e66975d`

## Browser transcript

The editor was changed in three prospective stages after establishing the mark instruction. Each
change traveled through the real textarea sampler as active and paused snapshots.

1. `Mark animal names.`
2. `Mark animal names. cat`
3. `Mark animal names. cat\nRemind me every 10 minutes to stretch.`
4. `Mark animal names. cat\nRemind me every 10 minutes to stretch.\nCancel the stretch timer.`

Executed model actions:

| Policy seq | Event | Action | Exact result |
| ---: | --- | --- | --- |
| 7 | `e_000008` | `mark` | instruction `e_000004[0:18]`; target `e_000007[19:22]` = `cat` |
| 10 | `e_000011` | `schedule` | instruction `e_000009[23:61]`; 600,000 ms; message `stretch` |
| 14 | `e_000015` | `cancel` | instruction `e_000013[62:87]`; target timer `t_001` |

Runtime acknowledgements:

- `e_000012` created `t_001` / `i_001` with a ten-minute fixed recurring interval.
- `e_000016` acknowledged cancellation of `t_001`.
- Final timer ledger: `status=canceled`, `fire_count=0`, `next_due_mono_ns=null`.
- Final visible browser state: annotation `Mark: cat`; timer chip `stretch · canceled`.
- No `timer.fire`, nudge, tool request, response disposition, or corrective provider retry occurred.

## Objective blocks retained in the record

Two raw attempts were correctly blocked by the mechanical license and are intentionally not hidden:

1. `d_000005` proposed the right lexical mark against active snapshot `e_000006`. Paused successor
   `e_000007` committed during inference, so the latest-snapshot rule returned `span_mismatch`.
   `d_000006` retargeted `e_000007` and executed the mark.
2. The post-mark continuation `d_000007` emitted `idle(already_handled)` for `e_000007`, but no
   qualifying disposition licensed that reason, so it returned `reason_mismatch`. Against unchanged
   bytes, `d_000008` emitted the licensed `idle(no_trigger)`.

The first is expected freshness behavior under provider latency. The second is a visible prompted
policy error and remains evaluation evidence; it did not introduce a parallel recovery path or
alter committed domain state.

## Usage and estimated charge

- Input tokens: 150,437
- Cached input tokens: 129,580
- Cache-write tokens: 11,780
- Uncached ordinary input tokens: 9,077
- Output tokens: 2,070 (including 1,616 reasoning tokens)
- Estimated charge: **$0.12295000**

The estimate applies $2.50/M ordinary input, $0.25/M cached input, the 1.25× cache-write multiplier,
and $15/M output. The provider invoice remains authoritative.

## Provider-call integrity manifest

Every request/response pair is retained exactly in the private SQLite audit. Hashes below permit
verification without committing the prompt stream or raw provider response.

| Decision | Latency ms | Request bytes | Request SHA-256 | Response bytes | Response SHA-256 | Tokens (input/cached/write/output/reasoning) |
| --- | ---: | ---: | --- | ---: | --- | --- |
| `d_000001` | 3742 | 54938 | `b5461211cbe74a9eeaf370062023719df7d350f6e3099c1fdb940c5934b65372` | 2215 | `7ed33b2efec230d792f656122263330e8e30680f3bc340ad056cd90ffb01a6f2` | 12118/0/11780/23/0 |
| `d_000002` | 979 | 55188 | `a5175c2265dc0e24c8f5302da47ec98c33501d652ccf2716a1bdeca6230a2838` | 2215 | `b8a58342cc0e8c4593838b0f0c32b5d9df8010e45d06cbef4614f2aac627511d` | 12182/11780/0/23/0 |
| `d_000003` | 2602 | 55461 | `9eb3298fdece668c8afd90d454355b5f931a75ca440d34b344af76efdd68f758` | 2368 | `45a105d1b9a9374294e4d1977d96d9ff7f0ae484559c92f181489b83cde17c08` | 12250/11780/0/172/147 |
| `d_000004` | 1711 | 55731 | `c597edc6c4198560cc88ebb7e8efa6549478f0a37894f2229980d5dfae46933a` | 2366 | `95deff73d5435890158b86258fd5bc5d78e882aa87e360c0d1e2e3691d7ad695` | 12318/11780/0/65/40 |
| `d_000005` | 2042 | 56008 | `b29db120b279a737f03e6408ae0d599a1a77d651a162e5791213ebe2564d3c44` | 2518 | `b9e57024994cc1978f093784bae8fd0a18b418d1ab15560035d296029b67402c` | 12388/11780/0/145/76 |
| `d_000006` | 2817 | 56282 | `8cfb00824bee0038e465795288b5b49c7bc5595e1159b0ebba3c7a99a04a36d3` | 2519 | `20131349cfccb19239649bede5059ae9ed818736374c79ad3140394eb97a9eb2` | 12458/11780/0/258/189 |
| `d_000007` | 3867 | 56636 | `90df847436b6722a26413bff6c0a5c14ec2d2d1bf3ac4a31cebab1d0aaff8f71` | 2381 | `9ca0491d4b7441e05e49a084dd95bffc898b36b981619119b52e0e5c88420dfd` | 12555/11780/0/290/261 |
| `d_000008` | 5732 | 56636 | `90df847436b6722a26413bff6c0a5c14ec2d2d1bf3ac4a31cebab1d0aaff8f71` | 2368 | `ba7f4acb57ca0ba1d59e800a11aca37fab141ff66406a2165eb660c48d66c109` | 12555/11780/0/510/485 |
| `d_000009` | 2567 | 56954 | `68b39968d9c752b2a22756b5c1f88001c1a593fc273cf29e40e4a434b8eab058` | 2499 | `05aad8054bd4b693652cccffd914a339d1383790930a29861b76d78cd01c70cb` | 12635/11780/0/227/168 |
| `d_000010` | 1458 | 57844 | `8fe694f617bff82feb969eafedc1508af4caf96f1bc71d74d6f13064cf25afba` | 2366 | `408ac6d4b52e124bf8600c7890d199f661d74553c8be6f8a265c84b79b055d03` | 12865/11780/0/91/66 |
| `d_000011` | 2588 | 58191 | `71028b77a230b276ef4d899436efab0f1c05e89bce12c187625144f4a29c280e` | 2492 | `ea39ba0f7794315d5eab50c10ef07edb8aad30bc789090682f875c86e0f4eb4b` | 12951/11780/0/201/144 |
| `d_000012` | 1381 | 59004 | `5ca7e43ad9decd38e6af0a3508ec43036431ef43ca85b0e0f427d61a302c3660` | 2366 | `3f9c957067bbf9152806375f605f80666f33ad06a7efc5a3311112d392866b70` | 13162/11780/0/65/40 |

## Private reproducibility unit

The ignored local archive is `probes/results/raw/wp13-e2e-20260713T043841Z/`.

- Closed SQLite database SHA-256:
  `bec1730de235e361be2213925507092115de2161277d8a74a8af0c7c9d7fcf64`
- Artifact files are content-addressed; each filename and byte digest equals the corresponding
  schema/spec/prompt/config identity listed above.
- Authorization headers and the API key are not stored in request bodies or this transcript.
