/** Blinded comparison, D3 gating, and D7 batch review controls. */

import {
  recordKey,
  type ReviewMap,
  type ReviewRecord,
} from "./review-sidecar";
import {
  categoriesFor,
  clusterEvidenceCases,
  clusterReviewAudit,
  type D3DisagreementCategory,
  type Phase2ReviewedEvidenceCase,
} from "./phase2-review-policy";
import type {
  Phase2Cluster,
  Phase2DecisionEvidence,
  Phase2ReviewEvidence,
} from "./types";

export const PHASE2_COMPARE_HTML = `
  <div id="phase2-compare" hidden></div>
  <p id="phase2-reveal" class="status"></p>`;

export const PHASE2_DECISION_FIELDS_HTML = `
  <div id="phase2-fields" hidden>
    <p>Choose the stronger candidate, frozen category, and human rationale.</p>
    <div role="radiogroup" aria-label="Candidate choice">
      <label><input id="phase2-choice-A" type="radio" name="phase2-choice" value="A" /> Candidate A</label>
      <label><input id="phase2-choice-B" type="radio" name="phase2-choice" value="B" /> Candidate B</label>
    </div>
    <label for="phase2-category">Disagreement category</label>
    <select id="phase2-category"></select>
  </div>`;

export const PHASE2_CLUSTER_HTML = `
  <section id="cluster-context" class="cluster-context" aria-label="D7 cluster evidence" hidden></section>
  <section id="cluster-batch" class="cluster-batch" aria-label="Cluster batch disposition" hidden>
    <p>After all three evidence cases are acknowledged, use the representative choice, category, and rationale for this cluster.</p>
    <button type="button" id="btn-save-cluster" disabled>Apply disposition to cluster</button>
    <p id="cluster-status" class="status" role="status"></p>
  </section>`;

export const REVIEW_SHELL_HTML = `
<header class="shell-header"><h1>Interaction Review Desk</h1><p class="shell-sub">Phase 1-compatible, Phase 2-capable · packet bytes are never mutated</p></header>
<section class="shell-load" aria-label="Packet load">
  <div class="load-controls">
    <div class="file-control"><label for="packet-dir">Packet directory</label><input id="packet-dir" type="file" webkitdirectory directory multiple /></div>
    <div class="file-control"><label for="import-review">Review sidecar</label><input id="import-review" type="file" accept=".jsonl,application/x-ndjson,text/plain" disabled /></div>
    <div class="file-control"><label for="import-teacher">Comparison labels</label><input id="import-teacher" type="file" accept=".jsonl,application/x-ndjson,text/plain" disabled /></div>
    <div class="load-action"><span>Portable review record</span><button type="button" id="btn-export" disabled>Export review sidecar</button></div>
  </div>
  <pre id="load-status" class="status" role="status" aria-live="polite"></pre><p id="progress" class="status" role="status"></p>
</section>
<section id="empty-state" class="empty-state" aria-labelledby="empty-title"><p class="empty-kicker">Review intake</p><h2 id="empty-title">Load a checksum-verified packet to begin</h2><p>Select a packet directory above. The desk verifies every declared file before revealing navigation, evidence, or review controls.</p></section>
<div id="review-workspace" hidden>
<div id="divergence" class="divergence" hidden></div><div class="shell-layout">
  <aside class="shell-sidebar" aria-label="Streams"><label for="filter-family">Family</label><select id="filter-family"></select><label for="filter-action">Action</label><select id="filter-action"></select><div id="stream-list" class="stream-list"></div><section id="cluster-rail" class="cluster-rail" aria-label="D7 cluster worklist"></section></aside>
  <main class="shell-main">
    <div class="shell-nav" aria-label="Navigation"><button type="button" id="btn-prev-event">Prev event (k)</button><button type="button" id="btn-next-event">Next event (j)</button><button type="button" id="btn-prev-decision">Prev decision (p)</button><button type="button" id="btn-next-decision">Next decision (n)</button><button type="button" id="btn-play" aria-pressed="false">Play</button><label for="play-speed">Speed</label><select id="play-speed"><option value="1x">1×</option><option value="4x">4×</option><option value="16x">16×</option></select><span id="nav-meta"></span></div>
    <div id="viewport"></div>
    <section class="compare" aria-label="Candidate comparison">${PHASE2_COMPARE_HTML}<div id="oracle-panel" class="panel"></div><div id="teacher-panel" class="panel"></div></section>
    <section class="review-forms" aria-label="Review decisions">
      <fieldset><legend>Stream-level accept/reject/flag</legend><label>Decision <select id="stream-decision"><option value="">—</option><option value="accept">accept</option><option value="reject">reject</option><option value="flag">flag</option></select></label><label>Reason code <input id="stream-reason" type="text" /></label><label>Note <textarea id="stream-note" rows="2"></textarea></label><button type="button" id="btn-save-stream">Save stream review</button></fieldset>
      <fieldset><legend>Per-decision note</legend><label>Decision <select id="decision-decision"><option value="">—</option><option value="accept">accept</option><option value="reject">reject</option><option value="flag">flag</option></select></label><label>Reason code <input id="decision-reason" type="text" /></label><label>Note <textarea id="decision-note" rows="2"></textarea></label>${PHASE2_DECISION_FIELDS_HTML}<button type="button" id="btn-save-decision">Save decision review</button></fieldset>
    </section>
    ${PHASE2_CLUSTER_HTML}
    <details class="inspector"><summary>Raw JSON inspector</summary><h3>Current event</h3><pre id="inspect-event"></pre><h3>Decision record</h3><pre id="inspect-oracle"></pre><h3>Candidate evidence</h3><pre id="inspect-teacher"></pre><h3>Derived reducer state</h3><pre id="inspect-state"></pre></details>
  </main>
  <aside class="shell-help" aria-label="Keyboard shortcuts"><h2>Shortcuts</h2><ul><li><kbd>j</kbd>/<kbd>↓</kbd> next event</li><li><kbd>k</kbd>/<kbd>↑</kbd> prev event</li><li><kbd>n</kbd> next decision</li><li><kbd>p</kbd> prev decision</li><li><kbd>space</kbd> play/pause</li><li><kbd>1</kbd>/<kbd>4</kbd> playback speed</li><li><kbd>[</kbd>/<kbd>]</kbd> prev/next stream</li></ul></aside>
</div></div>`;

export function phase2DecisionFor(
  evidence: Phase2ReviewEvidence | null,
  streamSha256: string,
  policySeq: number | null,
): Phase2DecisionEvidence | null {
  if (!evidence || policySeq === null) return null;
  return evidence.decisions.find(
    (decision) => decision.stream_sha256 === streamSha256 && decision.decision_policy_seq === policySeq,
  ) ?? null;
}

export { categoriesFor, clusterEvidenceCases, textEquivalentAllowed } from "./phase2-review-policy";

export function isPhase2Revealed(
  reviews: ReviewMap,
  decision: Phase2DecisionEvidence,
  phase2EvidenceSha256: string | null,
): boolean {
  const record = reviews.get(recordKey(decision));
  return Boolean(
    record &&
    phase2EvidenceSha256 &&
    record.phase2_evidence_sha256 === phase2EvidenceSha256 &&
    (record.candidate_choice === "A" || record.candidate_choice === "B") &&
    record.disagreement_category &&
    categoriesFor(decision).includes(record.disagreement_category) &&
    record.note.trim(),
  );
}

function actionText(value: unknown): string {
  return JSON.stringify(value, null, 2);
}

/** Renders only neutral Candidate A/B copy until a decision record exists. */
export function renderBlindedComparison(
  target: HTMLElement,
  decision: Phase2DecisionEvidence | null,
  revealed: boolean,
): boolean {
  if (!decision || (decision.comparison !== "semantic_review_required" && decision.comparison !== "causal_disagreement")) return false;
  target.replaceChildren();
  target.className = "phase2-candidates";
  for (const candidate of decision.candidates) {
    const panel = document.createElement("article");
    panel.className = "phase2-candidate";
    const heading = document.createElement("h3");
    heading.textContent = `Candidate ${candidate.candidate_id}`;
    const license = document.createElement("p");
    license.className = "candidate-license";
    license.textContent = candidate.license.codes.length
      ? `License: ${candidate.license.result} (${candidate.license.codes.join(", ")})`
      : `License: ${candidate.license.result}`;
    const action = document.createElement("pre");
    action.textContent = actionText(candidate.action);
    panel.append(heading, license, action);
    if (revealed) {
      const origin = document.createElement("p");
      origin.className = "candidate-origin";
      origin.textContent = `Origin: ${candidate.reveal.origin} · ${Object.entries(candidate.reveal.provenance).map(([name, value]) => `${name}=${value}`).join(" · ")}`;
      panel.append(origin);
    }
    target.append(panel);
  }
  return true;
}

export function phase2IsBlinded(decision: Phase2DecisionEvidence | null, revealed: boolean): boolean {
  return Boolean(
    decision &&
    (decision.comparison === "semantic_review_required" || decision.comparison === "causal_disagreement") &&
    !revealed,
  );
}

export function renderPhase2Shell(
  decision: Phase2DecisionEvidence | null,
  revealed: boolean,
  controls: {
    comparison: HTMLElement;
    oraclePanel: HTMLElement;
    teacherPanel: HTMLElement;
    fields: HTMLElement;
    announcement: HTMLElement;
    category: HTMLSelectElement;
  },
): boolean {
  const active = renderBlindedComparison(controls.comparison, decision, revealed);
  controls.comparison.hidden = !active;
  controls.oraclePanel.hidden = active;
  controls.teacherPanel.hidden = active;
  controls.fields.hidden = !active;
  if (!active || !decision) return false;
  controls.announcement.textContent = revealed
    ? "Disposition saved. Candidate origins and provenance are now revealed."
    : "Candidates remain blinded until a valid disposition is saved.";
  controls.announcement.setAttribute("aria-live", "polite");
  controls.category.replaceChildren(new Option("Choose a category", "", true, true));
  controls.category.options[0].disabled = true;
  categoriesFor(decision).forEach((value) => controls.category.add(new Option(value.replaceAll("_", " "), value)));
  return true;
}

export type Phase2Selection = {
  candidate_choice: "A" | "B";
  disagreement_category: D3DisagreementCategory;
  rationale: string;
};

/** Native controls, with the first missing field focused for rapid adjudication. */
export function validatePhase2Selection(
  decision: Phase2DecisionEvidence,
  choice: HTMLInputElement | null,
  category: HTMLSelectElement,
  rationale: HTMLTextAreaElement,
): Phase2Selection | null {
  const selected = choice?.value === "A" || choice?.value === "B" ? choice.value : null;
  const validCategories = categoriesFor(decision);
  const categoryValue = category.value as D3DisagreementCategory;
  const reason = rationale.value.trim();
  for (const [control, valid, message] of [
    [choice, selected !== null, "Choose Candidate A or Candidate B."],
    [category, validCategories.includes(categoryValue), "Choose a frozen disagreement category."],
    [rationale, reason.length > 0, "Enter the human rationale before saving."],
  ] as const) {
    if (!valid) {
      control?.setCustomValidity(message);
      control?.focus();
      return null;
    }
    control?.setCustomValidity("");
  }
  return { candidate_choice: selected!, disagreement_category: categoryValue, rationale: reason };
}

export function renderClusterRail(
  target: HTMLElement,
  evidence: Phase2ReviewEvidence | null,
  selected: string | null,
  onSelect: (cluster: Phase2Cluster) => void,
): void {
  target.replaceChildren();
  if (!evidence || evidence.clusters.length === 0) return;
  const title = document.createElement("h2");
  title.textContent = "D7 cluster worklist";
  const list = document.createElement("ul");
  for (const cluster of [...evidence.clusters].sort((left, right) => left.priority_rank - right.priority_rank)) {
    const row = document.createElement("li");
    const button = document.createElement("button");
    button.type = "button";
    button.className = `cluster-item${cluster.signature === selected ? " active" : ""}`;
    button.textContent = `Priority ${cluster.priority_rank + 1} · ${cluster.member_identities.length} decisions · 2 confirmations`;
    button.addEventListener("click", () => onSelect(cluster));
    row.append(button);
    list.append(row);
  }
  target.append(title, list);
}

export function renderClusterContext(
  target: HTMLElement,
  cluster: Phase2Cluster | null,
  currentIdentity: string | null,
  opened: ReadonlySet<string>,
  acknowledged: ReadonlySet<string>,
  onOpen: (item: Phase2ReviewedEvidenceCase) => void,
  onAcknowledge: (item: Phase2ReviewedEvidenceCase, checked: boolean) => void,
): void {
  target.replaceChildren();
  if (!cluster) return;
  const title = document.createElement("h2");
  title.textContent = "Cluster evidence";
  const instructions = document.createElement("p");
  instructions.textContent = "Open and explicitly acknowledge the representative and both confirmations.";
  const cases = document.createElement("ol");
  cases.className = "cluster-evidence-cases";
  for (const item of clusterEvidenceCases(cluster)) {
    const itemKey = recordKey(item);
    const row = document.createElement("li");
    if (itemKey === currentIdentity) row.classList.add("current");
    const role = document.createElement("strong");
    role.textContent = item.role.replace("_", " ");
    const identity = document.createElement("span");
    identity.textContent = `${item.stream_sha256.slice(0, 16)}… / ${item.decision_policy_seq}`;
    const open = document.createElement("button");
    open.type = "button";
    open.className = "cluster-open-evidence";
    open.textContent = itemKey === currentIdentity ? "Evidence open" : "Open evidence";
    open.addEventListener("click", () => onOpen(item));
    const acknowledge = document.createElement("label");
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.className = "cluster-acknowledge";
    checkbox.disabled = !opened.has(itemKey);
    checkbox.checked = acknowledged.has(itemKey);
    checkbox.addEventListener("change", () => onAcknowledge(item, checkbox.checked));
    acknowledge.append(checkbox, " Evidence reviewed");
    row.append(role, identity, open, acknowledge);
    cases.append(row);
  }
  const completion = document.createElement("p");
  completion.className = "cluster-completion";
  completion.textContent = `${clusterEvidenceCases(cluster).filter((item) => acknowledged.has(recordKey(item))).length} of 3 evidence cases acknowledged`;
  const report = document.createElement("pre");
  report.className = "cluster-invariants";
  report.textContent = JSON.stringify(cluster.mechanical_invariants, null, 2);
  target.append(title, instructions, cases, completion, report);
}

/**
 * Batch disposition follows the representative's selected hidden origin, then
 * uses every member's local A/B position. It never copies a literal A/B.
 */
export function applyClusterDisposition(
  reviews: ReviewMap,
  evidence: Phase2ReviewEvidence,
  phase2EvidenceSha256: string,
  cluster: Phase2Cluster,
  representativeChoice: "A" | "B",
  category: D3DisagreementCategory,
  rationale: string,
  acknowledgedIdentities: ReadonlySet<string>,
): ReviewMap {
  const reason = rationale.trim();
  if (!reason) throw new Error("cluster rationale must be nonblank");
  if (!/^sha256:[0-9a-f]{64}$/.test(phase2EvidenceSha256)) throw new Error("Phase 2 evidence hash is invalid");
  if (!evidence.clusters.some((item) => item.signature === cluster.signature)) throw new Error("cluster is not part of the loaded evidence");
  const byKey = new Map(evidence.decisions.map((decision) => [recordKey(decision), decision]));
  const representative = byKey.get(recordKey(cluster.representative));
  const reviewedEvidence = clusterEvidenceCases(cluster);
  const requiredAcknowledgments = new Set(reviewedEvidence.map(recordKey));
  if (acknowledgedIdentities.size !== 3 || [...requiredAcknowledgments].some((item) => !acknowledgedIdentities.has(item))) throw new Error("open and acknowledge exactly three selected evidence cases first");
  const members = cluster.member_identities.map((identity) => byKey.get(recordKey(identity)));
  if (members.some((decision) => !decision)) throw new Error("cluster member evidence is missing");
  if (members.some((decision) => !categoriesFor(decision!).includes(category))) throw new Error("disagreement category is not valid for every cluster member");
  if (!representative || (representativeChoice !== "A" && representativeChoice !== "B")) throw new Error("representative candidate choice is invalid");
  const winningOrigin = representative.candidates.find(
    (candidate) => candidate.candidate_id === representativeChoice,
  )?.reveal.origin;
  if (!winningOrigin) throw new Error("representative candidate origin is unavailable");
  const audit = clusterReviewAudit(cluster);
  const records = cluster.member_identities.map((identity): ReviewRecord => {
    const decision = byKey.get(recordKey(identity));
    const localChoice = decision?.candidates.find((candidate) => candidate.reveal.origin === winningOrigin)?.candidate_id;
    if (!decision || !localChoice) throw new Error("cluster member does not carry the representative origin");
    return {
      stream_sha256: identity.stream_sha256,
      decision_policy_seq: identity.decision_policy_seq,
      decision: "flag",
      reason_code: "cluster_disposition",
      note: reason,
      candidate_choice: localChoice,
      disagreement_category: category,
      phase2_evidence_sha256: phase2EvidenceSha256,
      cluster_review: audit,
    };
  });
  const next = new Map(reviews);
  records.forEach((record) => next.set(recordKey(record), record));
  return next;
}
