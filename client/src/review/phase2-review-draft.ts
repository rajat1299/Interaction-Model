/** Evidence-bound review and cluster-progress draft persistence. */

import {
  exportReviewSidecar,
  mergeReviewRecords,
  parseReviewSidecar,
  recordKey,
  recordsFromMap,
  type ReviewMap,
} from "./review-sidecar";
import { clusterEvidenceCases } from "./phase2-review-policy";
import type { PacketIndex } from "./stream-cache";
import type { Phase2Cluster } from "./types";

export type ClusterProgress = { opened: Set<string>; acknowledged: Set<string> };
export type ClusterProgressMap = Map<string, ClusterProgress>;

const streamKey = (sha: string) => sha.startsWith("sha256:") ? sha : `sha256:${sha}`;

export function reviewDraftKey(index: PacketIndex, teacherEvidenceId: string): string {
  const integrity = index.packet.integrity;
  return "wp1-8-review-draft:v1:" +
    `${integrity.manifestSha256}:${integrity.sourceIndexSha256}:` +
    `${integrity.phase2EvidenceSha256 ?? "none"}:${teacherEvidenceId}`;
}

export function phase2ReviewContext(index: PacketIndex) {
  const evidence = index.packet.phase2ReviewEvidence;
  const evidenceSha256 = index.packet.integrity.phase2EvidenceSha256;
  return evidence && evidenceSha256 ? { evidence, evidenceSha256 } : null;
}

export function persistReviewDraft(
  storage: Storage,
  key: string | null,
  reviews: ReviewMap,
): void {
  if (!key) return;
  try {
    storage.setItem(key, exportReviewSidecar(recordsFromMap(reviews)));
  } catch {
    // The shell's beforeunload/packet-replacement guard still protects dirty work.
  }
}

export function restoreReviewDraft(
  storage: Storage,
  index: PacketIndex,
  key: string,
): ReviewMap {
  let text: string | null;
  try {
    text = storage.getItem(key);
  } catch {
    return new Map();
  }
  if (!text) return new Map();
  const parsed = parseReviewSidecar(text);
  if (!parsed.ok) return new Map();
  const knownStreams = new Set(index.order.map(streamKey));
  const knownSeqs = new Map<string, Set<number>>();
  for (const [sha, indexed] of index.bySha) {
    knownSeqs.set(
      streamKey(sha),
      new Set(indexed.stream.sidecar.decisions.map((decision) => decision.observed_policy_seq)),
    );
  }
  const restored = mergeReviewRecords(
    new Map(),
    parsed.records,
    knownStreams,
    knownSeqs,
    phase2ReviewContext(index),
  );
  return restored.ok ? restored.merged : new Map();
}

function progressStorageKey(packetDraftKey: string | null): string | null {
  return packetDraftKey ? `${packetDraftKey}:cluster-evidence` : null;
}

export function persistClusterProgress(
  storage: Storage,
  packetDraftKey: string | null,
  progress: ClusterProgressMap,
): void {
  const key = progressStorageKey(packetDraftKey);
  if (!key) return;
  const value = [...progress.entries()]
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([progressKey, item]) => ({
      key: progressKey,
      opened: [...item.opened].sort(),
      acknowledged: [...item.acknowledged].sort(),
    }));
  try {
    storage.setItem(key, JSON.stringify(value));
  } catch {
    // Progress remains available in memory for the active review session.
  }
}

export function restoreClusterProgress(
  storage: Storage,
  packetDraftKey: string,
  index: PacketIndex,
): ClusterProgressMap {
  const key = progressStorageKey(packetDraftKey);
  const evidenceSha = index.packet.integrity.phase2EvidenceSha256;
  if (!key || !evidenceSha || !index.packet.phase2ReviewEvidence) return new Map();
  let value: unknown;
  try {
    const text = storage.getItem(key);
    if (!text) return new Map();
    value = JSON.parse(text);
  } catch {
    return new Map();
  }
  if (!Array.isArray(value)) return new Map();
  const next: ClusterProgressMap = new Map();
  const clusters = new Map(index.packet.phase2ReviewEvidence.clusters.map((cluster) => [cluster.signature, cluster]));
  for (const raw of value) {
    if (typeof raw !== "object" || raw === null || Array.isArray(raw)) continue;
    const item = raw as { key?: unknown; opened?: unknown; acknowledged?: unknown };
    if (typeof item.key !== "string" || !item.key.startsWith(`${evidenceSha}\x00`) || !Array.isArray(item.opened) || !Array.isArray(item.acknowledged)) continue;
    const cluster = clusters.get(item.key.slice(evidenceSha.length + 1));
    if (!cluster) continue;
    const allowed = new Set(clusterEvidenceCases(cluster).map(recordKey));
    const opened = new Set(item.opened.filter((identity): identity is string => typeof identity === "string" && allowed.has(identity)));
    const acknowledged = new Set(item.acknowledged.filter((identity): identity is string => typeof identity === "string" && opened.has(identity)));
    next.set(item.key, { opened, acknowledged });
  }
  return next;
}

export function progressForCluster(
  progress: ClusterProgressMap,
  evidenceSha256: string | null,
  cluster: Phase2Cluster,
): ClusterProgress {
  if (!evidenceSha256) return { opened: new Set(), acknowledged: new Set() };
  const key = `${evidenceSha256}\x00${cluster.signature}`;
  let result = progress.get(key);
  if (!result) {
    result = { opened: new Set(), acknowledged: new Set() };
    progress.set(key, result);
  }
  return result;
}

export function clusterEvidenceReady(
  progress: ClusterProgress,
  cluster: Phase2Cluster,
): boolean {
  const required = clusterEvidenceCases(cluster).map(recordKey);
  return required.length === 3 && required.every(
    (identity) => progress.opened.has(identity) && progress.acknowledged.has(identity),
  );
}
