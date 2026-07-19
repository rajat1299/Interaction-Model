/**
 * Review decision sidecar: deterministic JSONL export/import.
 * Canonical packet files are never touched; review decisions are a separate sidecar.
 */

import type { Phase2ReviewEvidence } from "./types";
import {
  clusterReviewAudit,
  clusterReviewAuditEqual,
  isD3DisagreementCategory,
  phase2CategoryAllowed,
  type D3DisagreementCategory,
  type Phase2ClusterReviewAudit,
} from "./phase2-review-policy";

export type ReviewDecision = "accept" | "reject" | "flag";

export type ReviewRecord = {
  stream_sha256: string;
  decision_policy_seq: number | null;
  decision: ReviewDecision;
  reason_code: string;
  note: string;
  candidate_choice?: "A" | "B";
  disagreement_category?: D3DisagreementCategory;
  phase2_evidence_sha256?: string;
  cluster_review?: Phase2ClusterReviewAudit;
};

export type ImportResult =
  | { ok: true; records: ReviewRecord[] }
  | { ok: false; errors: string[]; partial: ReviewRecord[] };

export type ConflictResult =
  | { ok: true; merged: ReviewMap; added: number; skipped: number }
  | { ok: false; errors: string[] };

export type ReviewMap = Map<string, ReviewRecord>;

export type Phase2ReviewContext = {
  evidenceSha256: string;
  evidence: Phase2ReviewEvidence;
};

export function recordKey(r: { stream_sha256: string; decision_policy_seq: number | null }): string {
  return `${r.stream_sha256}\x00${r.decision_policy_seq === null ? "null" : r.decision_policy_seq}`;
}

export function exportReviewSidecar(records: ReviewRecord[]): string {
  const sorted = [...records].sort((a, b) => {
    if (a.stream_sha256 !== b.stream_sha256) return a.stream_sha256 < b.stream_sha256 ? -1 : 1;
    const aSeq = a.decision_policy_seq ?? -1;
    const bSeq = b.decision_policy_seq ?? -1;
    return aSeq - bSeq;
  });
  return sorted.map((r) => JSON.stringify(r)).join("\n") + "\n";
}

export function parseReviewSidecar(text: string): ImportResult {
  const records: ReviewRecord[] = [];
  const errors: string[] = [];
  const seen = new Set<string>();
  let lineNo = 0;
  for (const line of text.split("\n")) {
    lineNo++;
    const trimmed = line.trim();
    if (trimmed === "") continue;
    let parsed: unknown;
    try {
      parsed = JSON.parse(trimmed);
    } catch (e) {
      errors.push(`line ${lineNo}: JSON parse error: ${(e as Error).message}`);
      continue;
    }
    const err = validateRecord(parsed);
    if (err) {
      errors.push(`line ${lineNo}: ${err}`);
      continue;
    }
    const r = parsed as ReviewRecord;
    const key = recordKey(r);
    if (seen.has(key)) {
      errors.push(`line ${lineNo}: duplicate identity ${key}`);
      continue;
    }
    seen.add(key);
    records.push(r);
  }
  if (errors.length > 0) return { ok: false, errors, partial: records };
  return { ok: true, records };
}

function validateRecord(r: unknown): string | null {
  if (typeof r !== "object" || r === null) return "not an object";
  const rec = r as Record<string, unknown>;
  if (typeof rec.stream_sha256 !== "string" || !rec.stream_sha256.startsWith("sha256:")) {
    return "stream_sha256 must be a sha256: string";
  }
  if (rec.decision_policy_seq !== null && typeof rec.decision_policy_seq !== "number") {
    return "decision_policy_seq must be a number or null";
  }
  if (typeof rec.decision_policy_seq === "number" && (!Number.isInteger(rec.decision_policy_seq) || rec.decision_policy_seq < 0)) {
    return "decision_policy_seq must be a non-negative integer";
  }
  if (!["accept", "reject", "flag"].includes(rec.decision as string)) {
    return "decision must be accept, reject, or flag";
  }
  if (typeof rec.reason_code !== "string") return "reason_code must be a string";
  if (typeof rec.note !== "string") return "note must be a string";
  const hasChoice = rec.candidate_choice !== undefined;
  const hasCategory = rec.disagreement_category !== undefined;
  const hasEvidence = rec.phase2_evidence_sha256 !== undefined;
  if (new Set([hasChoice, hasCategory, hasEvidence]).size !== 1) {
    return "candidate_choice, disagreement_category, and phase2_evidence_sha256 must be paired";
  }
  if (hasChoice) {
    if (rec.decision_policy_seq === null) return "paired Phase 2 fields require a decision identity";
    if (rec.candidate_choice !== "A" && rec.candidate_choice !== "B") return "candidate_choice must be A or B";
    if (!isD3DisagreementCategory(rec.disagreement_category)) return "disagreement_category is not a frozen D3 value";
    if (typeof rec.phase2_evidence_sha256 !== "string" || !/^sha256:[0-9a-f]{64}$/.test(rec.phase2_evidence_sha256)) return "phase2_evidence_sha256 must be a sha256: digest";
    if (rec.note.trim() === "") return "paired Phase 2 fields require a nonblank rationale note";
  }
  if (rec.cluster_review !== undefined) {
    if (!hasChoice || typeof rec.cluster_review !== "object" || rec.cluster_review === null || Array.isArray(rec.cluster_review)) return "cluster_review requires paired Phase 2 fields";
    const audit = rec.cluster_review as Record<string, unknown>;
    if (typeof audit.cluster_signature !== "string" || !/^sha256:[0-9a-f]{64}$/.test(audit.cluster_signature)) return "cluster_review.cluster_signature must be a sha256: digest";
    if (!Array.isArray(audit.reviewed_evidence) || audit.reviewed_evidence.length !== 3) return "cluster_review must audit exactly three evidence cases";
    const roles = ["representative", "confirmation_1", "confirmation_2"];
    const identities = new Set<string>();
    for (const [index, value] of audit.reviewed_evidence.entries()) {
      if (typeof value !== "object" || value === null || Array.isArray(value)) return "cluster_review evidence case must be an object";
      const item = value as Record<string, unknown>;
      if (item.role !== roles[index]) return "cluster_review evidence roles must be representative then two confirmations";
      if (typeof item.stream_sha256 !== "string" || !/^sha256:[0-9a-f]{64}$/.test(item.stream_sha256)) return "cluster_review evidence stream must be a sha256: digest";
      if (!Number.isInteger(item.decision_policy_seq) || (item.decision_policy_seq as number) < 0) return "cluster_review evidence policy seq must be a non-negative integer";
      identities.add(`${item.stream_sha256}\x00${item.decision_policy_seq}`);
    }
    if (identities.size !== 3) return "cluster_review evidence identities must be distinct";
  }
  return null;
}

/**
 * Merge imported records into an existing map, rejecting unknown streams/sequences
 * and conflicting records (same identity, different content). Does not silently overwrite.
 */
export function mergeReviewRecords(
  existing: ReviewMap,
  imported: ReviewRecord[],
  knownStreams: Set<string>,
  knownSeqsByStream: Map<string, Set<number>>,
  phase2Context: Phase2ReviewContext | null = null,
): ConflictResult {
  const errors: string[] = [];
  const merged = new Map(existing);
  let added = 0;
  let skipped = 0;

  const auditedSignatures = new Set(
    imported.flatMap((record) => record.cluster_review ? [record.cluster_review.cluster_signature] : []),
  );
  for (const signature of auditedSignatures) {
    const cluster = phase2Context?.evidence.clusters.find((item) => item.signature === signature);
    const audited = imported.filter((record) => record.cluster_review?.cluster_signature === signature);
    const expectedKeys = new Set(cluster?.member_identities.map(recordKey) ?? []);
    const auditedKeys = new Set(audited.map(recordKey));
    if (
      !cluster || audited.length !== cluster.member_identities.length ||
      auditedKeys.size !== expectedKeys.size || [...expectedKeys].some((key) => !auditedKeys.has(key))
    ) {
      errors.push(`Phase 2 cluster import is not membership-complete for ${signature}`);
      continue;
    }

    const expectedAudit = clusterReviewAudit(cluster);
    const decisions = new Map(phase2Context!.evidence.decisions.map((decision) => [recordKey(decision), decision]));
    const chosenOrigins = new Set<string>();
    const categories = new Set(audited.map((record) => record.disagreement_category));
    const rationales = new Set(audited.map((record) => record.note));
    let consistent = categories.size === 1 && rationales.size === 1;
    for (const record of audited) {
      const decision = decisions.get(recordKey(record));
      const candidate = decision?.candidates.find((item) => item.candidate_id === record.candidate_choice);
      if (candidate) chosenOrigins.add(candidate.reveal.origin);
      else consistent = false;
      if (
        record.decision !== "flag" || record.reason_code !== "cluster_disposition" ||
        record.phase2_evidence_sha256 !== phase2Context!.evidenceSha256 ||
        !clusterReviewAuditEqual(record.cluster_review, expectedAudit)
      ) {
        consistent = false;
      }
    }
    if (!consistent || chosenOrigins.size !== 1) {
      errors.push(`Phase 2 cluster import disposition is inconsistent for ${signature}`);
    }
  }
  if (errors.length > 0) return { ok: false, errors };

  for (const r of imported) {
    if (r.candidate_choice && r.phase2_evidence_sha256 !== phase2Context?.evidenceSha256) {
      errors.push(`Phase 2 evidence hash mismatch for ${recordKey(r)}`);
      skipped++;
      continue;
    }
    const streamKey = r.stream_sha256;
    if (!knownStreams.has(streamKey)) {
      errors.push(`unknown stream: ${streamKey}`);
      skipped++;
      continue;
    }
    if (r.decision_policy_seq !== null) {
      const seqs = knownSeqsByStream.get(streamKey);
      if (!seqs || !seqs.has(r.decision_policy_seq)) {
        errors.push(`unknown decision_policy_seq ${r.decision_policy_seq} for stream ${streamKey.slice(0, 16)}...`);
        skipped++;
        continue;
      }
    }
    if (r.candidate_choice && phase2Context) {
      const phase2Decision = phase2Context.evidence.decisions.find(
        (decision) => recordKey(decision) === recordKey(r),
      );
      if (!phase2Decision || !phase2Decision.candidates.some((candidate) => candidate.candidate_id === r.candidate_choice)) {
        errors.push(`Phase 2 candidate choice does not close over evidence for ${recordKey(r)}`);
        skipped++;
        continue;
      }
      if (!phase2CategoryAllowed(phase2Decision, r.disagreement_category!)) {
        errors.push(`Phase 2 category is not allowed for ${recordKey(r)}`);
        skipped++;
        continue;
      }
      if (r.cluster_review) {
        const cluster = phase2Context.evidence.clusters.find(
          (item) => item.signature === r.cluster_review!.cluster_signature,
        );
        const expected = cluster ? clusterReviewAudit(cluster) : undefined;
        if (
          !cluster ||
          !cluster.member_identities.some((identity) => recordKey(identity) === recordKey(r)) ||
          !clusterReviewAuditEqual(r.cluster_review, expected)
        ) {
          errors.push(`Phase 2 cluster audit does not close over evidence for ${recordKey(r)}`);
          skipped++;
          continue;
        }
      }
    }
    const key = recordKey(r);
    const prev = merged.get(key);
    if (prev) {
      if (
        prev.decision !== r.decision ||
        prev.reason_code !== r.reason_code ||
        prev.note !== r.note ||
        prev.candidate_choice !== r.candidate_choice ||
        prev.disagreement_category !== r.disagreement_category ||
        prev.phase2_evidence_sha256 !== r.phase2_evidence_sha256 ||
        !clusterReviewAuditEqual(prev.cluster_review, r.cluster_review)
      ) {
        errors.push(`conflicting record for ${key}: existing differs from imported (not overwriting)`);
        skipped++;
        continue;
      }
      // Exact duplicate - skip silently.
      skipped++;
      continue;
    }
    merged.set(key, r);
    added++;
  }

  if (errors.length > 0) {
    return { ok: false, errors };
  }
  return { ok: true, merged, added, skipped };
}

export function recordsFromMap(map: ReviewMap): ReviewRecord[] {
  return Array.from(map.values());
}
