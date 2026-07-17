import { describe, expect, it } from "vitest";
import {
  exportReviewSidecar,
  mergeReviewRecords,
  parseReviewSidecar,
  recordKey,
  type ReviewRecord,
} from "./review-sidecar";

const sample: ReviewRecord[] = [
  {
    stream_sha256: "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    decision_policy_seq: 2,
    decision: "flag",
    reason_code: "looks_off",
    note: "b",
  },
  {
    stream_sha256: "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    decision_policy_seq: null,
    decision: "accept",
    reason_code: "",
    note: "stream ok",
  },
  {
    stream_sha256: "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    decision_policy_seq: 1,
    decision: "reject",
    reason_code: "disagree",
    note: "a",
  },
];

describe("review sidecar export/import", () => {
  it("exports lexicographically sorted deterministic JSONL", () => {
    const text = exportReviewSidecar(sample);
    const lines = text.trimEnd().split("\n");
    expect(lines).toHaveLength(3);
    const parsed = lines.map((l) => JSON.parse(l) as ReviewRecord);
    expect(parsed[0].stream_sha256 < parsed[1].stream_sha256 || parsed[0].decision_policy_seq === null).toBe(
      true,
    );
    expect(parsed.map((r) => `${r.stream_sha256}:${r.decision_policy_seq}`)).toEqual([
      "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa:null",
      "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa:1",
      "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb:2",
    ]);
    // Round-trip exact restore.
    const again = parseReviewSidecar(text);
    expect(again.ok).toBe(true);
    if (!again.ok) return;
    expect(again.records).toEqual(parsed);
  });

  it("rejects duplicate identities on import", () => {
    const line = JSON.stringify(sample[0]);
    const result = parseReviewSidecar(`${line}\n${line}\n`);
    expect(result.ok).toBe(false);
    if (result.ok) return;
    expect(result.errors.some((e) => e.includes("duplicate"))).toBe(true);
  });

  it("rejects unknown streams/sequences and conflicting records", () => {
    const knownStreams = new Set([
      "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    ]);
    const knownSeqs = new Map([
      [
        "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        new Set([1]),
      ],
    ]);
    const existing = new Map<string, ReviewRecord>();
    const first = sample[2];
    existing.set(recordKey(first), first);

    const unknownStream = mergeReviewRecords(
      existing,
      [sample[0]],
      knownStreams,
      knownSeqs,
    );
    expect(unknownStream.ok).toBe(false);

    const unknownSeq: ReviewRecord = {
      ...first,
      decision_policy_seq: 99,
    };
    const badSeq = mergeReviewRecords(existing, [unknownSeq], knownStreams, knownSeqs);
    expect(badSeq.ok).toBe(false);

    const conflict: ReviewRecord = { ...first, note: "changed" };
    const conflicted = mergeReviewRecords(existing, [conflict], knownStreams, knownSeqs);
    expect(conflicted.ok).toBe(false);
    // Existing must remain unchanged.
    expect(existing.get(recordKey(first))?.note).toBe("a");
  });
});
