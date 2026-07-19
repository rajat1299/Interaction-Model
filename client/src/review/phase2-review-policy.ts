/** Frozen D3 category policy, shared by UI validation and sidecar import closure. */

import type {
  D3DisagreementCategory,
  Phase2DecisionEvidence,
} from "./types";

export const D3_CATEGORIES: readonly D3DisagreementCategory[] = [
  "teacher_error",
  "oracle_error",
  "template_error",
  "asset_ambiguity",
  "contract_gap",
  "text_equivalent",
  "both_legal_but_oracle_preferred",
];

export function textEquivalentAllowed(decision: Phase2DecisionEvidence): boolean {
  if (decision.comparison !== "semantic_review_required" || decision.candidates.length !== 2) return false;
  const [first, second] = decision.candidates.map((candidate) => candidate.action);
  if (first.type === "respond" && second.type === "respond") return first.reply_to_event_id === second.reply_to_event_id;
  if (first.type === "integrate" && second.type === "integrate") return first.result_event_id === second.result_event_id;
  return false;
}

export function categoriesFor(
  decision: Phase2DecisionEvidence,
): D3DisagreementCategory[] {
  return D3_CATEGORIES.filter(
    (category) => category !== "text_equivalent" || textEquivalentAllowed(decision),
  );
}

export function phase2CategoryAllowed(
  decision: Phase2DecisionEvidence,
  category: D3DisagreementCategory,
): boolean {
  return categoriesFor(decision).includes(category);
}
