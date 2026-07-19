/** Checksum-bound Phase 2 evidence parser and independently recomputed closure checks. */

import type {
  LoadedStream,
  Phase2DecisionEvidence,
  Phase2DecisionIdentity,
  Phase2ReviewEvidence,
  SidecarDecision,
} from "./types";

const DIGEST_RE = /^sha256:[0-9a-f]{64}$/;
const COMPARISONS = new Set([
  "equivalent", "semantic_review_required", "causal_disagreement", "teacher_label_missing",
]);
const LICENSE_CODES = new Set([
  "malformed_action", "unknown_reference", "span_mismatch", "result_not_ready",
  "fire_not_open", "timer_not_active", "duplicate_schedule", "duplicate_tool_request",
  "floor_owned", "target_already_handled", "reason_mismatch", "timer_limit_exceeded",
  "payload_limit_exceeded", "stale_decision",
]);
const PROTOCOLS = new Set(["generation", "pairwise", "listwise", "semantic_text"]);
const FAMILIES = new Set([
  "neutral_typing_revision_pause", "mark_activation_positive", "mark_lifecycle_negative",
  "live_lookup_lifecycle", "lookup_latency_duplicate_pressure", "stale_result_opening_boundary",
  "timer_creation_normal_fire", "timer_cancel_quoting_stale_fire",
  "timer_contention_backpressure", "rollover_continuity", "reserved_annotation_unknown_kind",
]);
const FLOORS = new Set(["open", "owned", "closed"]);
const BOUNDARIES = new Set([
  "ordinary", "partial_instruction", "active_floor_response", "schedule_similar_distinct",
  "schedule_semantic_duplicate", "lookup_refresh_superseded", "lookup_abandoned_stale",
  "ambiguous_cancel",
]);
const RISK_FLAGS = new Set([
  "oracle_teacher_non_equivalence", "teacher_low_confidence",
  "schedule_semantic_duplicate_boundary", "cancel_semantic_referent_resolution",
  "skip_reason_selection", "active_floor_response_boundary",
  "rollover_or_checkpoint_projection", "first_instances_of_new_template",
]);
const LABEL_ORIGINS = new Set([
  "human", "human_authored", "teacher_auto_trusted", "teacher_human_confirmed",
  "oracle_teacher_agreement",
]);
const BOUNDARY_RISK = new Map([
  ["active_floor_response", "active_floor_response_boundary"],
  ["schedule_similar_distinct", "schedule_semantic_duplicate_boundary"],
  ["schedule_semantic_duplicate", "schedule_semantic_duplicate_boundary"],
  ["lookup_refresh_superseded", "skip_reason_selection"],
  ["lookup_abandoned_stale", "skip_reason_selection"],
  ["ambiguous_cancel", "cancel_semantic_referent_resolution"],
]);

type RecordValue = Record<string, unknown>;
export type ActionValidator = (value: unknown, label: string) => void;

function record(value: unknown, label: string): RecordValue {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new Error(`${label} must be an object`);
  }
  return value as RecordValue;
}

function string(value: unknown, label: string): string {
  if (typeof value !== "string" || !value.trim()) throw new Error(`${label} must be a non-empty string`);
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

function digest(value: unknown, label: string): string {
  const result = string(value, label);
  if (!DIGEST_RE.test(result)) throw new Error(`${label} must be a sha256: digest`);
  return result;
}

function oneOf(value: unknown, label: string, values: Set<string>): string {
  const item = string(value, label);
  if (!values.has(item)) throw new Error(`${label} is invalid: ${item}`);
  return item;
}

function canonicalJson(value: unknown): string {
  if (value === null || typeof value !== "object") {
    const encoded = JSON.stringify(value);
    if (encoded === undefined) throw new Error("canonical JSON value is unsupported");
    return encoded;
  }
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(",")}]`;
  const item = value as RecordValue;
  return `{${Object.keys(item).sort().map((name) => `${JSON.stringify(name)}:${canonicalJson(item[name])}`).join(",")}}`;
}

async function sha256Bytes(value: string): Promise<Uint8Array> {
  const bytes = new TextEncoder().encode(value);
  return new Uint8Array(await crypto.subtle.digest("SHA-256", bytes));
}

async function sha256Canonical(value: unknown): Promise<string> {
  const bytes = await sha256Bytes(canonicalJson(value));
  return `sha256:${Array.from(bytes).map((item) => item.toString(16).padStart(2, "0")).join("")}`;
}

function identity(value: unknown, label: string): Phase2DecisionIdentity {
  const item = record(value, label);
  return {
    stream_sha256: digest(item.stream_sha256, `${label}.stream_sha256`),
    decision_policy_seq: integer(item.decision_policy_seq, `${label}.decision_policy_seq`),
  };
}

function key(value: Phase2DecisionIdentity): string {
  return `${value.stream_sha256}\x00${value.decision_policy_seq}`;
}

function semanticActionSkeleton(value: unknown): RecordValue {
  const action = { ...record(value, "semantic action") };
  if (action.type === "respond" || action.type === "integrate") delete action.text;
  return action;
}

export async function phase2ClusterSignature(decision: Phase2DecisionEvidence): Promise<string> {
  return sha256Canonical({
    boundary_class: decision.review_evidence.boundary_class,
    causal_state_class: decision.review_evidence.causal_state_class,
    comparison: decision.comparison,
    family: decision.review_evidence.trust_cell.family,
    floor: decision.review_evidence.trust_cell.floor,
    idle_boundary: decision.review_evidence.idle_boundary,
    oracle_action: semanticActionSkeleton(decision.oracle_action),
    protocol: decision.review_evidence.trust_cell.protocol,
    risk_flags: decision.review_evidence.risk_flags,
    rollover: decision.review_evidence.rollover,
    teacher_action: decision.candidates.find((candidate) => candidate.reveal.origin === "teacher")
      ? semanticActionSkeleton(decision.candidates.find((candidate) => candidate.reveal.origin === "teacher")!.action)
      : null,
    template: decision.review_evidence.template_id,
  });
}

export async function phase2CandidateOriginOrder(
  blindCommitment: string,
  decisionIdentity: Phase2DecisionIdentity,
): Promise<["oracle" | "teacher", "oracle" | "teacher"]> {
  const rank = await sha256Bytes(`${blindCommitment}|${key(decisionIdentity)}`);
  return rank[0] % 2 === 0 ? ["oracle", "teacher"] : ["teacher", "oracle"];
}

async function rankConfirmations(
  commitment: string,
  signature: string,
  members: Phase2DecisionEvidence[],
): Promise<Phase2DecisionEvidence[]> {
  const ranked = await Promise.all(members.slice(1).map(async (decision) => ({
    decision,
    rank: await sha256Bytes(`${commitment}|${signature}|${key(decision)}`),
  })));
  ranked.sort((left, right) => {
    for (let index = 0; index < left.rank.length; index++) {
      if (left.rank[index] !== right.rank[index]) return left.rank[index] - right.rank[index];
    }
    return 0;
  });
  const selected: Phase2DecisionEvidence[] = [];
  const sources = new Set([members[0].source_unit_id]);
  for (const item of ranked) {
    if (!sources.has(item.decision.source_unit_id)) {
      sources.add(item.decision.source_unit_id);
      selected.push(item.decision);
    }
    if (selected.length === 2) break;
  }
  return selected;
}

function validateRoute(value: unknown, label: string): void {
  const route = record(value, label);
  const reviewRequired = bool(route.review_required, `${label}.review_required`);
  const mandatory = bool(route.mandatory, `${label}.mandatory`);
  const rate = route.sample_rate;
  if (typeof rate !== "number" || !Number.isFinite(rate) || rate < 0 || rate > 1) {
    throw new Error(`${label}.sample_rate must be finite within [0, 1]`);
  }
  const reasons = stringList(route.reasons, `${label}.reasons`);
  if (new Set(reasons).size !== reasons.length) throw new Error(`${label}.reasons must be unique`);
  if (mandatory && (!reviewRequired || rate !== 1)) {
    throw new Error(`${label} mandatory routes must require review at sample_rate 1`);
  }
  if (reviewRequired) {
    if (!reasons.length || route.provisional_label_origin !== null) {
      throw new Error(`${label} required routes need reasons and no provisional origin`);
    }
  } else if (reasons.length || !LABEL_ORIGINS.has(route.provisional_label_origin as string)) {
    throw new Error(`${label} non-required routes need no reasons and a closed provisional origin`);
  }
}

function validateCandidate(value: unknown, label: string, validateAction: ActionValidator): RecordValue {
  const candidate = record(value, label);
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
  if (!Object.keys(provenance).length) throw new Error(`${label}.reveal.provenance must not be empty`);
  Object.entries(provenance).forEach(([name, item]) => string(item, `${label}.reveal.provenance.${name}`));
  return candidate;
}

/** Structural and cryptographic validation using only the public commitment. */
export async function parsePhase2ReviewEvidence(
  value: unknown,
  validateAction: ActionValidator,
): Promise<Phase2ReviewEvidence> {
  const evidence = record(value, "phase2-review-evidence.json");
  const label = "phase2-review-evidence.json";
  if (evidence.format_version !== 1) throw new Error(`${label}.format_version must be 1`);
  digest(evidence.teacher_evidence_identity, `${label}.teacher_evidence_identity`);
  const commitment = digest(evidence.blind_seed_sha256, `${label}.blind_seed_sha256`);
  const rawDecisions = list(evidence.decisions, `${label}.decisions`);
  const rawClusters = list(evidence.clusters, `${label}.clusters`);
  if (!rawDecisions.length) throw new Error(`${label}.decisions must not be empty`);
  const invariant = record(evidence.mechanical_invariants, `${label}.mechanical_invariants`);
  if (invariant.all_packet_decisions_included !== true) throw new Error(`${label}.mechanical_invariants.all_packet_decisions_included must be true`);
  const identities = new Set<string>();
  const ranks: number[] = [];
  let nonEquivalent = 0;

  for (const [index, value] of rawDecisions.entries()) {
    const decisionLabel = `${label}.decisions[${index}]`;
    const decision = record(value, decisionLabel);
    const decisionIdentity = identity(decision, decisionLabel);
    const decisionKey = key(decisionIdentity);
    if (identities.has(decisionKey)) throw new Error(`${decisionLabel} has duplicate identity`);
    identities.add(decisionKey);
    validateAction(decision.oracle_action, `${decisionLabel}.oracle_action`);
    const comparison = oneOf(decision.comparison, `${decisionLabel}.comparison`, COMPARISONS);
    const candidates = list(decision.candidates, `${decisionLabel}.candidates`);
    const nonEquivalentDecision = comparison === "semantic_review_required" || comparison === "causal_disagreement";
    if (nonEquivalentDecision) {
      nonEquivalent++;
      digest(decision.cluster_signature, `${decisionLabel}.cluster_signature`);
      if (candidates.length !== 2) throw new Error(`${decisionLabel} requires exactly two candidates`);
      const parsed = candidates.map((candidate, candidateIndex) => validateCandidate(candidate, `${decisionLabel}.candidates[${candidateIndex}]`, validateAction));
      if (parsed[0].candidate_id !== "A" || parsed[1].candidate_id !== "B") throw new Error(`${decisionLabel} candidate order must be canonical A then B`);
      const expectedOrigins = await phase2CandidateOriginOrder(commitment, decisionIdentity);
      for (const [candidateIndex, candidate] of parsed.entries()) {
        const reveal = record(candidate.reveal, `${decisionLabel}.candidate reveal`);
        if (reveal.origin !== expectedOrigins[candidateIndex]) throw new Error(`${decisionLabel} candidate A/B order does not match the blind seed commitment`);
        const matchesOracle = canonicalJson(candidate.action) === canonicalJson(decision.oracle_action);
        if ((reveal.origin === "oracle") !== matchesOracle) throw new Error(`${decisionLabel} candidate origin does not close over the packet action`);
      }
    } else if (candidates.length || decision.cluster_signature !== null) {
      throw new Error(`${decisionLabel} equivalent evidence cannot carry candidates or a cluster`);
    }
    ranks.push(integer(decision.priority_rank, `${decisionLabel}.priority_rank`));
    string(decision.source_unit_id, `${decisionLabel}.source_unit_id`);
    const review = record(decision.review_evidence, `${decisionLabel}.review_evidence`);
    ["wave_id", "template_id", "causal_state_class"].forEach((name) => string(review[name], `${decisionLabel}.review_evidence.${name}`));
    const boundary = oneOf(review.boundary_class, `${decisionLabel}.review_evidence.boundary_class`, BOUNDARIES);
    if (review.idle_boundary !== null) string(review.idle_boundary, `${decisionLabel}.review_evidence.idle_boundary`);
    bool(review.rollover, `${decisionLabel}.review_evidence.rollover`);
    const flags = stringList(review.risk_flags, `${decisionLabel}.review_evidence.risk_flags`);
    if (flags.some((flag) => !RISK_FLAGS.has(flag)) || flags.join("\x00") !== [...new Set(flags)].sort().join("\x00")) throw new Error(`${decisionLabel}.review_evidence.risk_flags are not closed, sorted, and unique`);
    if (nonEquivalentDecision !== flags.includes("oracle_teacher_non_equivalence")) throw new Error(`${decisionLabel} non-equivalence risk flag is inconsistent`);
    const requiredRisk = BOUNDARY_RISK.get(boundary);
    if (requiredRisk && !flags.includes(requiredRisk)) throw new Error(`${decisionLabel} boundary risk flag is missing`);
    const cell = record(review.trust_cell, `${decisionLabel}.review_evidence.trust_cell`);
    oneOf(cell.protocol, `${decisionLabel}.review_evidence.trust_cell.protocol`, PROTOCOLS);
    oneOf(cell.family, `${decisionLabel}.review_evidence.trust_cell.family`, FAMILIES);
    oneOf(cell.floor, `${decisionLabel}.review_evidence.trust_cell.floor`, FLOORS);
    validateRoute(review.review_route, `${decisionLabel}.review_evidence.review_route`);
  }

  if (ranks.slice().sort((a, b) => a - b).some((rank, index) => rank !== index)) throw new Error(`${label}.decisions must carry a closed priority order`);
  if (integer(invariant.decision_identity_count, `${label}.mechanical_invariants.decision_identity_count`) !== rawDecisions.length || integer(invariant.non_equivalent_decision_count, `${label}.mechanical_invariants.non_equivalent_decision_count`) !== nonEquivalent) throw new Error(`${label}.mechanical_invariants counts do not close over decisions`);

  const result = evidence as Phase2ReviewEvidence;
  const decisions = result.decisions;
  const byKey = new Map(decisions.map((decision) => [key(decision), decision]));
  const groups = new Map<string, Phase2DecisionEvidence[]>();
  for (const decision of decisions) {
    if (decision.cluster_signature === null) continue;
    const expectedSignature = await phase2ClusterSignature(decision);
    if (decision.cluster_signature !== expectedSignature) throw new Error(`${label} D7 cluster signature does not match decision evidence`);
    const members = groups.get(expectedSignature) ?? [];
    members.push(decision);
    groups.set(expectedSignature, members);
  }
  if (groups.size !== rawClusters.length) throw new Error(`${label} clusters do not close over non-equivalent decisions`);
  const signatures = new Set<string>();
  for (const [index, rawCluster] of rawClusters.entries()) {
    const clusterLabel = `${label}.clusters[${index}]`;
    const cluster = record(rawCluster, clusterLabel);
    const signature = digest(cluster.signature, `${clusterLabel}.signature`);
    if (signatures.has(signature)) throw new Error(`${clusterLabel} signature is duplicated`);
    signatures.add(signature);
    const members = list(cluster.member_identities, `${clusterLabel}.member_identities`).map((item, memberIndex) => identity(item, `${clusterLabel}.member_identities[${memberIndex}]`));
    if (members.length < 3) throw new Error(`${clusterLabel} must have at least three members`);
    const expected = [...(groups.get(signature) ?? [])].sort((left, right) => left.priority_rank - right.priority_rank);
    if (canonicalJson(members.map(key)) !== canonicalJson(expected.map(key))) throw new Error(`${clusterLabel} members are not in priority order`);
    const representative = identity(cluster.representative, `${clusterLabel}.representative`);
    if (key(representative) !== key(expected[0])) throw new Error(`${clusterLabel} representative is not the first priority member`);
    if (integer(cluster.priority_rank, `${clusterLabel}.priority_rank`) !== expected[0].priority_rank) throw new Error(`${clusterLabel} priority rank is inconsistent`);
    const confirmations = list(cluster.confirmations, `${clusterLabel}.confirmations`).map((item, confirmationIndex) => identity(item, `${clusterLabel}.confirmations[${confirmationIndex}]`));
    if (confirmations.length !== 2) throw new Error(`${clusterLabel} must have exactly two confirmations`);
    const expectedConfirmations = await rankConfirmations(commitment, signature, expected);
    if (canonicalJson(confirmations.map(key)) !== canonicalJson(expectedConfirmations.map(key))) throw new Error(`${clusterLabel} confirmations do not match the blind seed commitment`);
    const selectedSources = [representative, ...confirmations].map((item) => byKey.get(key(item))?.source_unit_id);
    if (selectedSources.some((source) => source === undefined) || new Set(selectedSources).size !== 3) throw new Error(`${clusterLabel} does not prove three distinct source units`);
    const report = record(cluster.mechanical_invariants, `${clusterLabel}.mechanical_invariants`);
    if (report.all_members_non_equivalent !== true || report.three_distinct_source_units !== true) throw new Error(`${clusterLabel} invariant report is invalid`);
    if (integer(report.member_count, `${clusterLabel}.mechanical_invariants.member_count`, 1) !== members.length || integer(report.distinct_source_unit_count, `${clusterLabel}.mechanical_invariants.distinct_source_unit_count`, 1) !== new Set(expected.map((item) => item.source_unit_id)).size) throw new Error(`${clusterLabel} source counts do not match members`);
    const priorityDigest = await sha256Canonical(members);
    if (digest(report.priority_order_sha256, `${clusterLabel}.mechanical_invariants.priority_order_sha256`) !== priorityDigest) throw new Error(`${clusterLabel} priority digest does not match members`);
  }
  return result;
}

/** Closure against canonical sidecars plus a second async recomputation at the load boundary. */
export async function validatePhase2EvidenceClosure(
  evidence: Phase2ReviewEvidence,
  streams: LoadedStream[],
): Promise<string[]> {
  const errors: string[] = [];
  const sidecars = new Map<string, SidecarDecision>();
  streams.forEach((stream) => stream.sidecar.decisions.forEach((decision) => sidecars.set(key({ stream_sha256: stream.sidecar.stream_sha256, decision_policy_seq: decision.observed_policy_seq }), decision)));
  const byKey = new Map(evidence.decisions.map((decision) => [key(decision), decision]));
  if (byKey.size !== sidecars.size || [...sidecars.keys()].some((item) => !byKey.has(item))) return ["decision identities do not close over loaded sidecars"];
  sidecars.forEach((sidecar, sidecarKey) => {
    if (canonicalJson(byKey.get(sidecarKey)!.oracle_action) !== canonicalJson(sidecar.action)) errors.push(`oracle action does not match sidecar for ${sidecarKey}`);
  });
  for (const cluster of evidence.clusters) {
    const members = cluster.member_identities.map((item) => byKey.get(key(item))!);
    const expectedSignature = members.length ? await phase2ClusterSignature(members[0]) : "";
    const priorityDigest = await sha256Canonical(cluster.member_identities);
    if (expectedSignature !== cluster.signature || priorityDigest !== cluster.mechanical_invariants.priority_order_sha256) errors.push(`cluster ${cluster.signature} cryptographic closure failed`);
  }
  return errors;
}
