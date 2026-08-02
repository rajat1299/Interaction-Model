import { describe, expect, it } from "vitest";
import {
  clearReviewDraft,
  clusterEvidenceReady,
  persistClusterProgress,
  restoreClusterProgress,
  type ClusterProgressMap,
} from "./phase2-review-draft";
import { clusterEvidenceCases } from "./phase2-review-policy";
import { recordKey } from "./review-sidecar";
import type { PacketIndex } from "./stream-cache";
import type { Phase2Cluster } from "./types";

const digest = (letter: string) => `sha256:${letter.repeat(64)}`;
const evidenceSha = digest("f");
const packetDraftKey = "draft-key";

const identities = [
  { stream_sha256: digest("a"), decision_policy_seq: 1 },
  { stream_sha256: digest("b"), decision_policy_seq: 2 },
  { stream_sha256: digest("c"), decision_policy_seq: 3 },
] as const;

const cluster: Phase2Cluster = {
  signature: digest("d"),
  priority_rank: 0,
  representative: identities[0],
  confirmations: [identities[1], identities[2]],
  member_identities: [...identities],
  mechanical_invariants: {
    all_members_non_equivalent: true,
    distinct_source_unit_count: 3,
    member_count: 3,
    priority_order_sha256: digest("e"),
    three_distinct_source_units: true,
  },
};

function indexFor(phase2EvidenceSha256: string): PacketIndex {
  return {
    packet: {
      integrity: { phase2EvidenceSha256 },
      phase2ReviewEvidence: { clusters: [cluster] },
    },
    bySha: new Map(),
    order: [],
  } as unknown as PacketIndex;
}

describe("Phase 2 cluster progress drafts", () => {
  it("clears only the current packet's review and cluster drafts", () => {
    const storage = window.localStorage;
    storage.clear();
    storage.setItem(packetDraftKey, "review");
    storage.setItem(`${packetDraftKey}:cluster-evidence`, "cluster");
    storage.setItem("another-packet", "keep");

    clearReviewDraft(storage, packetDraftKey);

    expect(storage.getItem(packetDraftKey)).toBeNull();
    expect(storage.getItem(`${packetDraftKey}:cluster-evidence`)).toBeNull();
    expect(storage.getItem("another-packet")).toBe("keep");
  });

  it("round-trips valid progress and fails closed for stale or malformed state", () => {
    const storage = window.localStorage;
    storage.clear();
    const caseKeys = clusterEvidenceCases(cluster).map(recordKey);
    const progressKey = `${evidenceSha}\x00${cluster.signature}`;
    const progress: ClusterProgressMap = new Map([[progressKey, {
      opened: new Set(caseKeys),
      acknowledged: new Set(caseKeys.slice(0, 2)),
    }]]);

    persistClusterProgress(storage, packetDraftKey, progress);
    const restored = restoreClusterProgress(storage, packetDraftKey, indexFor(evidenceSha));
    expect([...restored.get(progressKey)!.opened]).toEqual(caseKeys);
    expect([...restored.get(progressKey)!.acknowledged]).toEqual(caseKeys.slice(0, 2));
    expect(restoreClusterProgress(storage, packetDraftKey, indexFor(digest("0"))).size).toBe(0);

    const storageKey = `${packetDraftKey}:cluster-evidence`;
    storage.setItem(storageKey, "{");
    expect(restoreClusterProgress(storage, packetDraftKey, indexFor(evidenceSha)).size).toBe(0);

    storage.setItem(storageKey, JSON.stringify([{
      key: progressKey,
      opened: [caseKeys[0]],
      acknowledged: [caseKeys[0], caseKeys[1]],
    }]));
    const filtered = restoreClusterProgress(storage, packetDraftKey, indexFor(evidenceSha));
    expect([...filtered.get(progressKey)!.opened]).toEqual([caseKeys[0]]);
    expect([...filtered.get(progressKey)!.acknowledged]).toEqual([caseKeys[0]]);
    expect(clusterEvidenceReady(filtered.get(progressKey)!, cluster)).toBe(false);
  });
});
