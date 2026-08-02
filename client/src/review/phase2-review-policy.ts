/** Dependency-light Phase 2 category and cluster-audit policy. */

export const D3_CATEGORIES = Object.freeze([
  "teacher_error",
  "oracle_error",
  "template_error",
  "asset_ambiguity",
  "contract_gap",
  "text_equivalent",
  "both_legal_but_oracle_preferred",
] as const);

export type D3DisagreementCategory = typeof D3_CATEGORIES[number];

const D3_CATEGORY_SET: ReadonlySet<D3DisagreementCategory> = new Set(D3_CATEGORIES);

export function isD3DisagreementCategory(value: unknown): value is D3DisagreementCategory {
  return typeof value === "string" && D3_CATEGORY_SET.has(value as D3DisagreementCategory);
}

type DecisionForD3 = {
  comparison: string;
  candidates: readonly {
    action: {
      type: string;
      reply_to_event_id?: unknown;
      result_event_id?: unknown;
    };
  }[];
};

type DecisionIdentity = {
  stream_sha256: string;
  decision_policy_seq: number;
};

type ClusterSelection = {
  signature: string;
  representative: DecisionIdentity;
  confirmations: readonly [DecisionIdentity, DecisionIdentity];
};

export type Phase2ReviewedEvidenceCase = DecisionIdentity & {
  role: "representative" | "confirmation_1" | "confirmation_2";
};

export type Phase2ClusterReviewAudit = {
  cluster_signature: string;
  reviewed_evidence: readonly [
    Phase2ReviewedEvidenceCase,
    Phase2ReviewedEvidenceCase,
    Phase2ReviewedEvidenceCase,
  ];
};

export function clusterEvidenceCases(
  cluster: ClusterSelection,
): Phase2ClusterReviewAudit["reviewed_evidence"] {
  return [
    { role: "representative", ...cluster.representative },
    { role: "confirmation_1", ...cluster.confirmations[0] },
    { role: "confirmation_2", ...cluster.confirmations[1] },
  ];
}

export function clusterReviewAudit(cluster: ClusterSelection): Phase2ClusterReviewAudit {
  return {
    cluster_signature: cluster.signature,
    reviewed_evidence: clusterEvidenceCases(cluster),
  };
}

export function clusterReviewAuditEqual(
  left: Phase2ClusterReviewAudit | undefined,
  right: Phase2ClusterReviewAudit | undefined,
): boolean {
  if (!left || !right) return left === right;
  return left.cluster_signature === right.cluster_signature &&
    left.reviewed_evidence.length === right.reviewed_evidence.length &&
    left.reviewed_evidence.every((item, index) => {
      const other = right.reviewed_evidence[index];
      return other !== undefined && item.role === other.role &&
        item.stream_sha256 === other.stream_sha256 &&
        item.decision_policy_seq === other.decision_policy_seq;
    });
}

export function textEquivalentAllowed(decision: DecisionForD3): boolean {
  if (decision.comparison !== "semantic_review_required" || decision.candidates.length !== 2) return false;
  const [first, second] = decision.candidates.map((candidate) => candidate.action);
  if (first.type === "respond" && second.type === "respond") return first.reply_to_event_id === second.reply_to_event_id;
  if (first.type === "integrate" && second.type === "integrate") return first.result_event_id === second.result_event_id;
  return false;
}

export function categoriesFor(
  decision: DecisionForD3,
): D3DisagreementCategory[] {
  return D3_CATEGORIES.filter(
    (category) => category !== "text_equivalent" || textEquivalentAllowed(decision),
  );
}

export function phase2CategoryAllowed(
  decision: DecisionForD3,
  category: D3DisagreementCategory,
): boolean {
  return categoriesFor(decision).includes(category);
}
