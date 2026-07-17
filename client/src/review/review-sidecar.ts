/**
 * Review decision sidecar: deterministic JSONL export/import.
 * Canonical packet files are never touched; review decisions are a separate sidecar.
 */

export type ReviewDecision = "accept" | "reject" | "flag";

export type ReviewRecord = {
  stream_sha256: string;
  decision_policy_seq: number | null;
  decision: ReviewDecision;
  reason_code: string;
  note: string;
};

export type ImportResult =
  | { ok: true; records: ReviewRecord[] }
  | { ok: false; errors: string[]; partial: ReviewRecord[] };

export type ConflictResult =
  | { ok: true; merged: ReviewMap; added: number; skipped: number }
  | { ok: false; errors: string[] };

export type ReviewMap = Map<string, ReviewRecord>;

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
): ConflictResult {
  const errors: string[] = [];
  const merged = new Map(existing);
  let added = 0;
  let skipped = 0;

  for (const r of imported) {
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
    const key = recordKey(r);
    const prev = merged.get(key);
    if (prev) {
      if (
        prev.decision !== r.decision ||
        prev.reason_code !== r.reason_code ||
        prev.note !== r.note
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
