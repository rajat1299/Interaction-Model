/** Checksum-bound Phase 2 evidence parser and closure checks. */

import type {
  LoadedStream,
  Phase2DecisionIdentity,
  Phase2ReviewEvidence,
  SidecarDecision,
} from "./types";

const HASH_RE = /^[0-9a-f]{64}$/;
const COMPARISONS = new Set([
  "equivalent", "semantic_review_required", "causal_disagreement", "teacher_label_missing",
]);
const LICENSE_CODES = new Set([
  "malformed_action", "unknown_reference", "span_mismatch", "result_not_ready",
  "fire_not_open", "timer_not_active", "duplicate_schedule", "duplicate_tool_request",
  "floor_owned", "target_already_handled", "reason_mismatch", "timer_limit_exceeded",
  "payload_limit_exceeded", "stale_decision",
]);

type RecordValue = Record<string, unknown>;
export type ActionValidator = (value: unknown, label: string) => void;

function record(value: unknown, label: string): RecordValue {
  if (typeof value !== "object" || value === null || Array.isArray(value)) throw new Error(`${label} must be an object`);
  return value as RecordValue;
}

function string(value: unknown, label: string): string {
  if (typeof value !== "string" || !value) throw new Error(`${label} must be a non-empty string`);
  return value;
}

function integer(value: unknown, label: string, min = 0): number {
  if (!Number.isInteger(value) || (value as number) < min) throw new Error(`${label} must be an integer >= ${min}`);
  return value as number;
}

function bool(value: unknown, label: string): boolean {
  if (typeof value !== "boolean") throw new Error(`${label} must be a boolean`);
  return value;
}

function list(value: unknown, label: string): unknown[] {
  if (!Array.isArray(value)) throw new Error(`${label} must be an array`);
  return value;
}

function stringList(value: unknown, label: string): string[] {
  return list(value, label).map((item, index) => string(item, `${label}[${index}]`));
}

function hash(value: unknown, label: string): string {
  const digest = string(value, label);
  const bare = digest.startsWith("sha256:") ? digest.slice(7) : digest;
  if (!HASH_RE.test(bare)) throw new Error(`${label} must be a SHA-256`);
  return digest;
}

function oneOf(value: unknown, label: string, values: Set<string>): string {
  const item = string(value, label);
  if (!values.has(item)) throw new Error(`${label} is invalid: ${item}`);
  return item;
}

function canonicalJson(value: unknown): string {
  if (value === null || typeof value !== "object") return JSON.stringify(value);
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(",")}]`;
  const item = value as RecordValue;
  return `{${Object.keys(item).sort().map((key) => `${JSON.stringify(key)}:${canonicalJson(item[key])}`).join(",")}}`;
}

function identity(value: unknown, label: string): Phase2DecisionIdentity {
  const item = record(value, label);
  return {
    stream_sha256: hash(item.stream_sha256, `${label}.stream_sha256`),
    decision_policy_seq: integer(item.decision_policy_seq, `${label}.decision_policy_seq`),
  };
}

function key(value: Phase2DecisionIdentity): string {
  return `${value.stream_sha256}\x00${value.decision_policy_seq}`;
}

function validateCandidate(value: unknown, label: string, validateAction: ActionValidator): void {
  const candidate = record(value, label);
  oneOf(candidate.candidate_id, `${label}.candidate_id`, new Set(["A", "B"]));
  validateAction(candidate.action, `${label}.action`);
  const license = record(candidate.license, `${label}.license`);
  const result = oneOf(license.result, `${label}.license.result`, new Set(["licensed", "blocked"]));
  const codes = stringList(license.codes, `${label}.license.codes`);
  if (codes.some((code) => !LICENSE_CODES.has(code)) || codes.join("\x00") !== [...new Set(codes)].sort().join("\x00")) {
    throw new Error(`${label}.license.codes are not closed, sorted, and unique`);
  }
  if (result === "licensed" && codes.length) throw new Error(`${label}.license licensed candidate cannot carry codes`);
  const reveal = record(candidate.reveal, `${label}.reveal`);
  oneOf(reveal.origin, `${label}.reveal.origin`, new Set(["oracle", "teacher"]));
  const provenance = record(reveal.provenance, `${label}.reveal.provenance`);
  if (Object.keys(provenance).length === 0) throw new Error(`${label}.reveal.provenance must not be empty`);
  Object.entries(provenance).forEach(([name, item]) => string(item, `${label}.reveal.provenance.${name}`));
}

/** Structural validation. The loader supplies the existing canonical action validator. */
export function parsePhase2ReviewEvidence(value: unknown, validateAction: ActionValidator): Phase2ReviewEvidence {
  const evidence = record(value, "phase2-review-evidence.json");
  const label = "phase2-review-evidence.json";
  if (evidence.format_version !== 1) throw new Error(`${label}.format_version must be 1`);
  hash(evidence.teacher_evidence_identity, `${label}.teacher_evidence_identity`);
  hash(evidence.blind_seed_sha256, `${label}.blind_seed_sha256`);
  const decisions = list(evidence.decisions, `${label}.decisions`);
  const clusters = list(evidence.clusters, `${label}.clusters`);
  const invariant = record(evidence.mechanical_invariants, `${label}.mechanical_invariants`);
  if (invariant.all_packet_decisions_included !== true) throw new Error(`${label}.mechanical_invariants.all_packet_decisions_included must be true`);
  const identities = new Set<string>();
  const ranks: number[] = [];
  let nonEquivalent = 0;
  for (const [index, value] of decisions.entries()) {
    const decision = record(value, `${label}.decisions[${index}]`);
    const decisionKey = key(identity(decision, `${label}.decisions[${index}]`));
    if (identities.has(decisionKey)) throw new Error(`${label}.decisions[${index}] has duplicate identity`);
    identities.add(decisionKey);
    validateAction(decision.oracle_action, `${label}.decisions[${index}].oracle_action`);
    const comparison = oneOf(decision.comparison, `${label}.decisions[${index}].comparison`, COMPARISONS);
    const candidates = list(decision.candidates, `${label}.decisions[${index}].candidates`);
    const nonEquivalentDecision = comparison === "semantic_review_required" || comparison === "causal_disagreement";
    if (nonEquivalentDecision) {
      nonEquivalent++;
      hash(decision.cluster_signature, `${label}.decisions[${index}].cluster_signature`);
      if (candidates.length !== 2) throw new Error(`${label}.decisions[${index}] requires exactly two candidates`);
      candidates.forEach((candidate, candidateIndex) => validateCandidate(candidate, `${label}.decisions[${index}].candidates[${candidateIndex}]`, validateAction));
      const parsed = candidates.map((candidate, candidateIndex) => record(candidate, `${label}.decisions[${index}].candidates[${candidateIndex}]`));
      const ids = new Set(parsed.map((candidate) => candidate.candidate_id));
      const origins = new Set(parsed.map((candidate) => record(candidate.reveal, "candidate reveal").origin));
      const oracleMatches = parsed.filter((candidate) => canonicalJson(candidate.action) === canonicalJson(decision.oracle_action)).length;
      if (ids.size !== 2 || !ids.has("A") || !ids.has("B") || origins.size !== 2 || oracleMatches !== 1) throw new Error(`${label}.decisions[${index}] blinded candidates do not close over actions`);
    } else if (candidates.length || decision.cluster_signature !== null) {
      throw new Error(`${label}.decisions[${index}] equivalent evidence cannot carry candidates or a cluster`);
    }
    ranks.push(integer(decision.priority_rank, `${label}.decisions[${index}].priority_rank`));
    string(decision.source_unit_id, `${label}.decisions[${index}].source_unit_id`);
    const review = record(decision.review_evidence, `${label}.decisions[${index}].review_evidence`);
    ["wave_id", "template_id", "causal_state_class", "boundary_class"].forEach((name) => string(review[name], `${label}.decisions[${index}].review_evidence.${name}`));
    if (review.idle_boundary !== null) string(review.idle_boundary, `${label}.decisions[${index}].review_evidence.idle_boundary`);
    bool(review.rollover, `${label}.decisions[${index}].review_evidence.rollover`);
    const flags = stringList(review.risk_flags, `${label}.decisions[${index}].review_evidence.risk_flags`);
    if (flags.join("\x00") !== [...new Set(flags)].sort().join("\x00")) throw new Error(`${label}.decisions[${index}].review_evidence.risk_flags are not sorted and unique`);
    const cell = record(review.trust_cell, `${label}.decisions[${index}].review_evidence.trust_cell`);
    ["protocol", "family", "floor"].forEach((name) => string(cell[name], `${label}.decisions[${index}].review_evidence.trust_cell.${name}`));
    const route = record(review.review_route, `${label}.decisions[${index}].review_evidence.review_route`);
    bool(route.review_required, `${label}.decisions[${index}].review_evidence.review_route.review_required`);
    bool(route.mandatory, `${label}.decisions[${index}].review_evidence.review_route.mandatory`);
    if (typeof route.sample_rate !== "number" || !Number.isFinite(route.sample_rate) || route.sample_rate < 0) throw new Error(`${label}.decisions[${index}].review_evidence.review_route.sample_rate is invalid`);
    stringList(route.reasons, `${label}.decisions[${index}].review_evidence.review_route.reasons`);
    if (route.provisional_label_origin !== null) string(route.provisional_label_origin, `${label}.decisions[${index}].review_evidence.review_route.provisional_label_origin`);
  }
  if (!decisions.length || ranks.slice().sort((a, b) => a - b).some((rank, index) => rank !== index)) throw new Error(`${label}.decisions must carry a closed priority order`);
  if (integer(invariant.decision_identity_count, `${label}.mechanical_invariants.decision_identity_count`) !== decisions.length || integer(invariant.non_equivalent_decision_count, `${label}.mechanical_invariants.non_equivalent_decision_count`) !== nonEquivalent) throw new Error(`${label}.mechanical_invariants counts do not close over decisions`);
  for (const [index, value] of clusters.entries()) {
    const cluster = record(value, `${label}.clusters[${index}]`);
    hash(cluster.signature, `${label}.clusters[${index}].signature`);
    integer(cluster.priority_rank, `${label}.clusters[${index}].priority_rank`);
    identity(cluster.representative, `${label}.clusters[${index}].representative`);
    const confirmations = list(cluster.confirmations, `${label}.clusters[${index}].confirmations`);
    if (confirmations.length !== 2) throw new Error(`${label}.clusters[${index}] must have exactly two confirmations`);
    confirmations.forEach((item, itemIndex) => identity(item, `${label}.clusters[${index}].confirmations[${itemIndex}]`));
    const members = list(cluster.member_identities, `${label}.clusters[${index}].member_identities`);
    if (members.length < 3) throw new Error(`${label}.clusters[${index}] must have at least three members`);
    members.forEach((item, itemIndex) => identity(item, `${label}.clusters[${index}].member_identities[${itemIndex}]`));
    const report = record(cluster.mechanical_invariants, `${label}.clusters[${index}].mechanical_invariants`);
    if (report.all_members_non_equivalent !== true || report.three_distinct_source_units !== true) throw new Error(`${label}.clusters[${index}] invariant report is invalid`);
    integer(report.member_count, `${label}.clusters[${index}].mechanical_invariants.member_count`, 1);
    integer(report.distinct_source_unit_count, `${label}.clusters[${index}].mechanical_invariants.distinct_source_unit_count`, 1);
    hash(report.priority_order_sha256, `${label}.clusters[${index}].mechanical_invariants.priority_order_sha256`);
  }
  return evidence as Phase2ReviewEvidence;
}

/** Closure validation against loaded canonical sidecars; no second manifest is introduced. */
export function validatePhase2EvidenceClosure(evidence: Phase2ReviewEvidence, streams: LoadedStream[]): string[] {
  const errors: string[] = [];
  const sidecars = new Map<string, SidecarDecision>();
  streams.forEach((stream) => stream.sidecar.decisions.forEach((decision) => sidecars.set(key({ stream_sha256: stream.sidecar.stream_sha256, decision_policy_seq: decision.observed_policy_seq }), decision)));
  const byKey = new Map(evidence.decisions.map((decision) => [key(decision), decision]));
  if (byKey.size !== sidecars.size || [...sidecars.keys()].some((item) => !byKey.has(item))) return ["decision identities do not close over loaded sidecars"];
  sidecars.forEach((sidecar, sidecarKey) => {
    if (canonicalJson(byKey.get(sidecarKey)!.oracle_action) !== canonicalJson(sidecar.action)) errors.push(`oracle action does not match sidecar for ${sidecarKey}`);
  });
  const groups = new Map<string, typeof evidence.decisions>();
  evidence.decisions.forEach((decision) => {
    if (decision.cluster_signature === null) return;
    const members = groups.get(decision.cluster_signature) ?? [];
    members.push(decision);
    groups.set(decision.cluster_signature, members);
  });
  if (groups.size !== evidence.clusters.length) return [...errors, "clusters do not close over non-equivalent decisions"];
  evidence.clusters.forEach((cluster) => {
    const expected = groups.get(cluster.signature);
    if (!expected) return errors.push(`unknown cluster signature ${cluster.signature}`);
    const ordered = [...expected].sort((a, b) => a.priority_rank - b.priority_rank);
    const memberKeys = cluster.member_identities.map(key);
    const confirmationKeys = cluster.confirmations.map(key);
    const representativeKey = key(cluster.representative);
    const selectedSources = [representativeKey, ...confirmationKeys].map((item) => byKey.get(item)?.source_unit_id);
    if (JSON.stringify(memberKeys) !== JSON.stringify(ordered.map(key)) || representativeKey !== key(ordered[0]) || cluster.priority_rank !== ordered[0].priority_rank || new Set(confirmationKeys).size !== 2 || confirmationKeys.includes(representativeKey) || confirmationKeys.some((item) => !memberKeys.includes(item)) || selectedSources.some((source) => source === undefined) || new Set(selectedSources).size !== 3 || cluster.mechanical_invariants.member_count !== memberKeys.length || cluster.mechanical_invariants.distinct_source_unit_count !== new Set(ordered.map((item) => item.source_unit_id)).size) errors.push(`cluster ${cluster.signature} does not prove three distinct source units`);
  });
  return errors;
}
