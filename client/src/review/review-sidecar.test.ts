import { describe, expect, it } from "vitest";
import {
  exportReviewSidecar,
  mergeReviewRecords,
  parseReviewSidecar,
  recordKey,
  type Phase2ClusterReviewAudit,
  type ReviewRecord,
} from "./review-sidecar";
import { loadPacketFromEntries } from "./packet-loader";
import { loadCanaryEntries, loadCanaryReviewDecisions } from "./test-fixtures";
import type { Phase2DecisionEvidence, Phase2ReviewEvidence } from "./types";

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
const phase2EvidenceSha = "sha256:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff";

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

  it("round-trips the paired Phase 2 candidate choice and D3 category", () => {
    const phase2: ReviewRecord = {
      ...sample[2],
      candidate_choice: "B",
      disagreement_category: "teacher_error",
      phase2_evidence_sha256: phase2EvidenceSha,
      note: "Candidate B preserves the causal reference.",
    };
    const parsed = parseReviewSidecar(exportReviewSidecar([phase2]));
    expect(parsed.ok).toBe(true);
    if (!parsed.ok) return;
    expect(parsed.records[0]).toMatchObject({
      candidate_choice: "B",
      disagreement_category: "teacher_error",
      phase2_evidence_sha256: phase2EvidenceSha,
    });
    expect(parseReviewSidecar(JSON.stringify({ ...phase2, disagreement_category: undefined }))).toMatchObject({
      ok: false,
      errors: [expect.stringContaining("paired")],
    });
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

    const conflict: ReviewRecord = { ...first, candidate_choice: "A", disagreement_category: "teacher_error", phase2_evidence_sha256: phase2EvidenceSha };
    const conflicted = mergeReviewRecords(existing, [conflict], knownStreams, knownSeqs);
    expect(conflicted.ok).toBe(false);
    // Existing must remain unchanged.
    expect(existing.get(recordKey(first))?.note).toBe("a");
  });

  it("closes imported cluster audit roles, membership, category, and evidence hash", () => {
    const identity = (letter: string, decision_policy_seq: number) => ({
      stream_sha256: `sha256:${letter.repeat(64)}`,
      decision_policy_seq,
    });
    const identities = [identity("a", 1), identity("b", 2), identity("c", 3)];
    const decisions = identities.map((item, index) => ({
      ...item,
      comparison: "causal_disagreement",
      candidates: [
        { candidate_id: "A", action: { type: "idle", reason: "no_trigger", related_event_id: null } },
        { candidate_id: "B", action: { type: "nudge", fire_event_id: "e_1" } },
      ],
      priority_rank: index,
    })) as Phase2DecisionEvidence[];
    const signature = `sha256:${"c".repeat(64)}`;
    const cluster = {
      signature,
      representative: identities[0],
      confirmations: [identities[1], identities[2]],
      member_identities: identities,
    };
    const evidence = { decisions, clusters: [cluster] } as Phase2ReviewEvidence;
    const reviewed_evidence: Phase2ClusterReviewAudit["reviewed_evidence"] = [
      { role: "representative" as const, ...identities[0] },
      { role: "confirmation_1" as const, ...identities[1] },
      { role: "confirmation_2" as const, ...identities[2] },
    ];
    const record: ReviewRecord = {
      ...identities[0],
      decision: "flag",
      reason_code: "cluster_disposition",
      note: "Audited cluster disposition.",
      candidate_choice: "A",
      disagreement_category: "teacher_error",
      phase2_evidence_sha256: phase2EvidenceSha,
      cluster_review: { cluster_signature: signature, reviewed_evidence },
    };
    const knownStreams = new Set(identities.map((item) => item.stream_sha256));
    const knownSeqs = new Map(identities.map((item) => [item.stream_sha256, new Set([item.decision_policy_seq])]));
    const context = { evidenceSha256: phase2EvidenceSha, evidence };
    expect(mergeReviewRecords(new Map(), [record], knownStreams, knownSeqs, context).ok).toBe(true);

    const wrongRoles = structuredClone(record);
    wrongRoles.cluster_review!.reviewed_evidence.reverse();
    expect(mergeReviewRecords(new Map(), [wrongRoles], knownStreams, knownSeqs, context).ok).toBe(false);
    const wrongCategory = { ...record, disagreement_category: "text_equivalent" as const };
    expect(mergeReviewRecords(new Map(), [wrongCategory], knownStreams, knownSeqs, context).ok).toBe(false);
    const wrongHash = { ...record, phase2_evidence_sha256: `sha256:${"0".repeat(64)}` };
    expect(mergeReviewRecords(new Map(), [wrongHash], knownStreams, knownSeqs, context).ok).toBe(false);
  });

  it("accepts the repaired canary's completed WP1-8 sidecar", async () => {
    const packet = await loadPacketFromEntries(loadCanaryEntries());
    expect(packet.ok).toBe(true);
    if (!packet.ok) return;
    const parsed = parseReviewSidecar(loadCanaryReviewDecisions());
    expect(parsed.ok).toBe(true);
    if (!parsed.ok) return;

    const knownStreams = new Set(
      packet.packet.streams.map((stream) => `sha256:${stream.sha256}`),
    );
    const knownSeqs = new Map(
      packet.packet.streams.map((stream) => [
        `sha256:${stream.sha256}`,
        new Set(stream.sidecar.decisions.map((decision) => decision.observed_policy_seq)),
      ]),
    );
    const merged = mergeReviewRecords(new Map(), parsed.records, knownStreams, knownSeqs);
    expect(merged.ok).toBe(true);
    if (!merged.ok) return;
    expect(merged.added).toBe(77);
    expect(parsed.records.filter((record) => record.decision_policy_seq !== null)).toHaveLength(50);
  });
});
