# Phase 0 Freeze

Status: **frozen** by explicit user decision on 2026-07-14.

The annotated git tag `phase0-freeze` identifies the authoritative repository commit. Artifact
digests use SHA-256 and serialize as `sha256:` followed by lowercase hexadecimal.

## Version identifiers

- schema_version: `1`
- tool_registry_version: `1`
- renderer_id: `serialize-v1`
- canonicalizer_id: `tim-json-v1`
- hash_algorithm: `sha256`

## Frozen artifacts

- `spec/schema/event-v1.json`:
  `sha256:75fc9635d41e60b83089587d1216608fcbcedff22243a82e2f4dcd38883c02e5`
- `spec/schema/action-v1.json`:
  `sha256:09b64516ba1612d269f33397ffe291cb3cc26ca0ae3e621b319e539fd2f725f3`
- combined schema preimage, event bytes + one LF + action bytes:
  `sha256:77327b087f7e182ded920df88fa14a9a8c858c6f83e33d72351393f4ff900b09`
- `spec/behavior-spec.md`:
  `sha256:a31d19e1982f63ee154a7c8cf5f18e9ed68dbfd3ad731b78ecd263f34cf506c9`
- `spec/prompt-template-v1.txt`:
  `sha256:f130c1927f72a073d9a6c9397a65acb9c915d8919c9536aec9cda8d7fd771fa9`
- `src/im/serialize.py` source:
  `sha256:d41af28c9e00eb997807297daf3a197229edc17815c476ed14341409d6747df1`

The exported schema files are compact sorted-key UTF-8 with no trailing newline. The model-facing
schema hash uses the combined preimage above. `renderer_id` and `canonicalizer_id` are identifiers,
not source digests.

## Approval and evidence bindings

- `spec/APPROVALS.md`:
  `sha256:3e4178304a073c014ddedfadd907a4aeb1113e2227437d5c10dc63d0c97cf543`
- Original full WP15 report:
  `sha256:02d738a00ce9053b417835d36f71ddc803af47b82932a6488eaf0af6e2992adf`
- Original full WP15 provenance:
  `sha256:fe803228bec793f2e9905c3ee9df7ac42a13b22cf2aa35a0fc1ee1936e010ef5`
- Frozen-byte targeted WP15 diagnostic report:
  `sha256:42749c68c1a4beb0ad7e5bfe92cccda16f60e1cdcd4c8a436de8d52f869003b0`
- Frozen-byte targeted WP15 diagnostic provenance:
  `sha256:1dde51e1e63ffd9f5259edc50b3591be190a096d8e736d82d3bcfae4a73e1045`
- WP16 Qwen student-model sanity report:
  `sha256:d80d0d89ce082455ac50d9dfa5848af87d55111b51286536ffba373542ead42e`
- WP16 provenance:
  `sha256:6ea7294867c82ab9d4b8760909d8ea8eb95020555efec66b14db4406ca2a78c2`

WP15 remains **FAIL**. The user-approved exception in `spec/APPROVALS.md` defines the only cleared
teacher cells at protocol × family × floor-state granularity. No full-corpus WP15 run exists against
all frozen bytes; expanding teacher trust requires such a run and a new human adjudication. WP16 is
only a pre-training sanity baseline for Qwen, the checkpoint that will be trained into the
Interaction Model.

## Known v2 issue

The openings bullet says that an explicit question, invitation, or yield can open the floor without
the intended “at a pause” qualifier. The v1 respond forbidden-column, idle precedence, and examples
disambiguate the frozen behavior. V2 must qualify that sentence; v1 remains byte-identical to its
approved hash.

## Change control

After `phase0-freeze`, changing a frozen schema, union, behavior contract, prompt byte, renderer, or
canonicalizer requires a new version identifier and a written migration note. Routine schema export
must never create or overwrite this manifest.
