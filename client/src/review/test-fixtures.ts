// @ts-nocheck — Node fs helpers for Vitest only; not part of the browser build graph.
/**
 * Load teacher-canary packet entries from the repo for Vitest.
 */

import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import type { PacketEntry } from "./packet-loader";

/** client/ cwd → current repaired teacher-canary packet */
export const CANARY_ROOT = join(
  process.cwd(),
  "../review/phase1/teacher-canary-recanary/packet-final",
);
const TIMER_WAVE1_ROOT = join(
  process.cwd(),
  "../review/phase2/timer-wave-1-execution/review",
);
const CANARY_LABELS = join(
  process.cwd(),
  "../review/phase1/teacher-canary-recanary/execution/sharded/teacher-labels.jsonl",
);
const CANARY_REVIEWS = join(
  process.cwd(),
  "../review/phase1/teacher-canary-recanary/execution/sharded/review/review-decisions.jsonl",
);

function walk(dir: string, base: string, out: PacketEntry[]): void {
  for (const name of readdirSync(dir)) {
    if (name === ".DS_Store") continue;
    const full = join(dir, name);
    const st = statSync(full);
    if (st.isDirectory()) {
      walk(full, base, out);
    } else {
      const rel = relative(base, full).split("\\").join("/");
      out.push({ path: rel, text: readFileSync(full, "utf8") });
    }
  }
}

export function loadCanaryEntries(): PacketEntry[] {
  const out: PacketEntry[] = [];
  walk(CANARY_ROOT, CANARY_ROOT, out);
  return out;
}

export function loadTimerWave1Entries(): PacketEntry[] {
  const out: PacketEntry[] = [];
  walk(TIMER_WAVE1_ROOT, TIMER_WAVE1_ROOT, out);
  const sums = out.find((entry) => entry.path === "SHA256SUMS");
  if (!sums) throw new Error("timer Wave-1 fixture has no SHA256SUMS");
  const declared = new Set([
    "SHA256SUMS",
    ...sums.text
      .split("\n")
      .map((line) => line.split("  ", 2)[1])
      .filter((path): path is string => Boolean(path)),
  ]);
  return out.filter((entry) => declared.has(entry.path));
}

export function loadCanaryTeacherLabels(): string {
  return readFileSync(CANARY_LABELS, "utf8");
}

export function loadCanaryReviewDecisions(): string {
  return readFileSync(CANARY_REVIEWS, "utf8");
}
