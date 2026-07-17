/**
 * Teacher label adapter — internal type only.
 *
 * Teacher labels are not present in the packet yet. This adapter isolates
 * ingestion of a normalized local JSONL label file so the shell can show
 * "teacher label not loaded" or, if imported, display labels alongside the
 * oracle. No repository-wide schema or manifest is added here.
 *
 * The label file format is normalized JSONL, one record per line:
 *   {"stream_sha256":"sha256:...","decision_policy_seq":N,"action":{...},"label":"..."}
 * keyed by the canonical decision identity (stream_sha256, decision_policy_seq).
 *
 * Provider-specific response parsing must NOT happen in UI code; the imported
 * file is already normalized.
 */

import type { Action } from "./types";

export type TeacherLabel = {
  stream_sha256: string;
  decision_policy_seq: number;
  action: Action;
  label: string;
};

export type TeacherLabelMap = Map<string, TeacherLabel>;

export type TeacherLabelImportResult =
  | { ok: true; labels: TeacherLabelMap }
  | { ok: false; errors: string[]; partial: TeacherLabelMap };

export function teacherLabelKey(
  streamSha256: string,
  decisionPolicySeq: number,
): string {
  return `${streamSha256}\x00${decisionPolicySeq}`;
}

export function parseTeacherLabels(text: string): TeacherLabelImportResult {
  const labels: TeacherLabelMap = new Map();
  const errors: string[] = [];
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
    const err = validateLabel(parsed);
    if (err) {
      errors.push(`line ${lineNo}: ${err}`);
      continue;
    }
    const l = parsed as TeacherLabel;
    const key = teacherLabelKey(l.stream_sha256, l.decision_policy_seq);
    if (labels.has(key)) {
      errors.push(`line ${lineNo}: duplicate label ${key}`);
      continue;
    }
    labels.set(key, l);
  }
  if (errors.length > 0) return { ok: false, errors, partial: labels };
  return { ok: true, labels };
}

function validateLabel(l: unknown): string | null {
  if (typeof l !== "object" || l === null) return "not an object";
  const rec = l as Record<string, unknown>;
  if (typeof rec.stream_sha256 !== "string" || !rec.stream_sha256.startsWith("sha256:")) {
    return "stream_sha256 must be a sha256: string";
  }
  if (typeof rec.decision_policy_seq !== "number" || !Number.isInteger(rec.decision_policy_seq) || rec.decision_policy_seq < 0) {
    return "decision_policy_seq must be a non-negative integer";
  }
  if (typeof rec.action !== "object" || rec.action === null || typeof (rec.action as Record<string, unknown>).type !== "string") {
    return "action must have a type string";
  }
  if (typeof rec.label !== "string") return "label must be a string";
  return null;
}

export function lookupTeacherLabel(
  map: TeacherLabelMap,
  streamSha256: string,
  decisionPolicySeq: number,
): TeacherLabel | null {
  return map.get(teacherLabelKey(streamSha256, decisionPolicySeq)) ?? null;
}

function canon(value: unknown): string {
  if (value === null || typeof value !== "object") return JSON.stringify(value);
  if (Array.isArray(value)) return `[${value.map(canon).join(",")}]`;
  const record = value as Record<string, unknown>;
  return `{${Object.keys(record)
    .sort()
    .map((key) => `${JSON.stringify(key)}:${canon(record[key])}`)
    .join(",")}}`;
}

/** D2 equivalence: faithful integrate/respond wording is semantically reviewed, not causal. */
export function actionsAreCausallyEquivalent(teacher: Action, oracle: Action): boolean {
  if (teacher.type !== oracle.type) return false;
  if (teacher.type === "integrate" && oracle.type === "integrate") {
    return teacher.result_event_id === oracle.result_event_id;
  }
  if (teacher.type === "respond" && oracle.type === "respond") {
    return teacher.reply_to_event_id === oracle.reply_to_event_id;
  }
  return canon(teacher) === canon(oracle);
}
