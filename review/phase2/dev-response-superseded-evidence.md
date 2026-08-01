# DEV response packets — superseded digests and why they changed

Authority: owner decision in chat; assistant transcription. JN-12 accepted 2026-07-28: canonical
event ids are required construction metadata.

## What changed, and what did not

The twin builders bind their support events by fixed id. `g7_response_twins` requires an answer
contract whose `support_event_ids` is exactly `("e_000002",)` — the snapshot the twin branches on
— and `g7_failed_response_twins` requires exactly `("e_000005", "e_000008")`. The DEV records were
first authored with descriptive placeholders (`e_dev_response_15`, `e_dev_response_13_query`, …),
so every record was refused at construction before a single state could be built.

All 21 records now carry the canonical ids.

**Unchanged, byte for byte:** every invitation, every line of visible support text, and every
response text. Every `response_text_sha256` in both approval sidecars is identical before and
after. The owner-approved user-visible content was never touched.

**Changed:** each record's `serialized_neutral_request_sha256`, and therefore each packet's
`SHA256SUMS`. The event-id key sits inside the serialized neutral request, so renaming it moves
that hash even though no wording moved. The approval sidecars were re-issued over the corrected
records so that what is approved and what is buildable are the same bytes.

## Digest chain

| artifact | superseded | current |
|---|---|---|
| `dev-response-tranche/SHA256SUMS` | `24a583e34e0204c28eefe2c16ef372c7ec759ed07ac97bdc7d3e6bf7c7ae4c10` | `e3ba5911fdd03b1252a8dd9c7abff67f73acf13d981d5e1873647cafc5d35ec2` |
| `dev-response-tranche-2/SHA256SUMS` | `e34ad4b341aa3867c599f7720d3f611005dde7071747a718a39731249880dbc8` | `50d15aad37e016ec8652d73d927fa54fd44afcc34dc0e7ed47c23c7796315f1c` |
| `dev-response-approved/SHA256SUMS` | not captured — see below | `7d7a0f3ec5735d53c19641c32195c2269ea1d680e46d2e68511ab584783f282c` |
| `dev-response-tranche-2-approved/SHA256SUMS` | first issued after the rebind | `e922504343da12987b0ac61c32181125d4c68bf535b73714f37bfd28b3072cb3` |

`dev-response-tranche-2`'s superseded digest also predates the evidence-metadata correction
(`family_supporting_dev_asset_ids`, `content_authority`), so that row covers two changes, not one.

## One gap, stated rather than papered over

The pre-rebind `dev-response-approved/SHA256SUMS` digest was not recorded before that directory was
republished, and the response packets are untracked, so there is no history to recover it from.
What is recoverable and is recorded above: the tranche digest that sidecar was bound to
(`24a583e3…`, preserved in its own `source_response_packet_sha256` at the time) and the fact that
its 14 `response_text_sha256` values are unchanged across the rebind. The approved wording is
therefore still provable; the manifest digest of that one superseded directory is not.

Going forward, every DEV packet digest is recorded in
`review/phase2/dev-lane-implementation-log.md` at the time of publication.
