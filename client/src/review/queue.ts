/**
 * Family/action filters and rare-action-first review queue.
 * Primary unit remains the complete stream — never shuffled isolated rows.
 */

import type { Action, LoadedStream, SidecarDecision } from "./types";

export type QueueFilters = {
  families: Set<string> | null;
  actionTypes: Set<string> | null;
};

export type DecisionRef = {
  streamSha256: string;
  family: string;
  decisionIdx: number;
  policySeq: number;
  actionType: string;
  rarityScore: number;
};

export type StreamQueueItem = {
  streamSha256: string;
  family: string;
  decisionCount: number;
  maxRarity: number;
  decisions: DecisionRef[];
};

function actionRarity(action: Action): number {
  // Non-idle actions outrank idle; disagreements handled by caller (+boost).
  if (action.type === "idle") return 0;
  const rare: Record<string, number> = {
    skip: 5,
    cancel: 5,
    nudge: 4,
    integrate: 4,
    respond: 4,
    schedule: 3,
    delegate: 3,
    mark: 2,
  };
  return rare[action.type] ?? 1;
}

export function decisionRarity(
  decision: SidecarDecision,
  disagreement: boolean,
): number {
  return actionRarity(decision.action) + (disagreement ? 10 : 0);
}

export function disagreementKey(streamSha256: string, policySeq: number): string {
  return `${streamSha256}\x00${policySeq}`;
}

/** Collect stream+policy keys where teacher and oracle actions are not D2-equivalent. */
export function collectDisagreementKeys(
  streams: LoadedStream[],
  isDisagreement: (streamSha256: string, decision: SidecarDecision) => boolean,
): Set<string> {
  const keys = new Set<string>();
  for (const stream of streams) {
    for (const dec of stream.sidecar.decisions) {
      if (isDisagreement(stream.sha256, dec)) {
        keys.add(disagreementKey(stream.sha256, dec.observed_policy_seq));
      }
    }
  }
  return keys;
}

export function buildStreamQueue(
  streams: LoadedStream[],
  filters: QueueFilters,
  disagreementKeys: Set<string> = new Set(),
): StreamQueueItem[] {
  const items: StreamQueueItem[] = [];

  for (const stream of streams) {
    if (filters.families && !filters.families.has(stream.family)) continue;

    const decisions: DecisionRef[] = [];
    for (let i = 0; i < stream.sidecar.decisions.length; i++) {
      const dec = stream.sidecar.decisions[i];
      const actionType = dec.action.type;
      if (filters.actionTypes && !filters.actionTypes.has(actionType)) continue;

      const key = disagreementKey(stream.sha256, dec.observed_policy_seq);
      const rarityScore = decisionRarity(dec, disagreementKeys.has(key));
      decisions.push({
        streamSha256: stream.sha256,
        family: stream.family,
        decisionIdx: i,
        policySeq: dec.observed_policy_seq,
        actionType,
        rarityScore,
      });
    }

    if (decisions.length === 0) continue;

    const sortedDecisions = [...decisions].sort((a, b) => {
      if (b.rarityScore !== a.rarityScore) return b.rarityScore - a.rarityScore;
      return a.decisionIdx - b.decisionIdx;
    });

    items.push({
      streamSha256: stream.sha256,
      family: stream.family,
      decisionCount: decisions.length,
      maxRarity: Math.max(...decisions.map((d) => d.rarityScore)),
      decisions: sortedDecisions,
    });
  }

  // Rare-action-first across streams; stable by stream sha within same rarity.
  return items.sort((a, b) => {
    if (b.maxRarity !== a.maxRarity) return b.maxRarity - a.maxRarity;
    return a.streamSha256 < b.streamSha256 ? -1 : a.streamSha256 > b.streamSha256 ? 1 : 0;
  });
}

export function listFamilies(streams: LoadedStream[]): string[] {
  return [...new Set(streams.map((s) => s.family))].sort();
}

export function listActionTypes(streams: LoadedStream[]): string[] {
  const types = new Set<string>();
  for (const s of streams) {
    for (const d of s.sidecar.decisions) types.add(d.action.type);
  }
  return [...types].sort();
}
