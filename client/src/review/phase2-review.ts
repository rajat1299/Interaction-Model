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
  Action,
  Phase2Cluster,
  Phase2DecisionEvidence,
  Phase2ReviewEvidence,
} from "./types";

export const PHASE2_COMPARE_HTML = `
  <div id="phase2-compare" hidden></div>
  <p id="phase2-reveal" class="status"></p>`;

export const PHASE2_DECISION_FIELDS_HTML = `
  <div id="phase2-fields" hidden>
    <label class="field-label" for="phase2-category">Why do the candidates differ?</label>
    <select id="phase2-category" aria-describedby="phase2-category-help"></select>
    <p id="phase2-category-help" class="field-help">Choose the explanation that best accounts for the mismatch.</p>
  </div>`;

export const PHASE2_CLUSTER_HTML = `
  <section id="cluster-context" class="cluster-context" aria-label="D7 cluster evidence" hidden></section>
  <section id="cluster-batch" class="cluster-batch" aria-label="Cluster batch disposition" hidden>
    <p>After all three evidence cases are acknowledged, use the representative choice, category, and rationale for this cluster.</p>
    <button type="button" id="btn-save-cluster" disabled>Apply disposition to cluster</button>
    <p id="cluster-status" class="status" role="status"></p>
  </section>`;

export const REVIEW_SHELL_HTML = `
<header class="shell-header"><div><h1>Interaction Review</h1><p class="shell-sub">Follow one interaction in order, then judge what the assistant should do next.</p></div><div class="header-actions"><span id="save-state" class="save-state">No packet loaded</span><button type="button" id="btn-reset-packet" class="quiet-danger" disabled>Start this packet over</button><button type="button" id="btn-export" disabled>Export reviews</button></div></header>
<section class="shell-load" aria-label="Packet load">
  <div class="load-controls">
    <div class="file-control"><label for="packet-dir">Open review packet</label><input id="packet-dir" type="file" webkitdirectory directory multiple /></div>
    <details class="import-tools"><summary>Import existing work</summary><div class="import-fields"><div class="file-control"><label for="import-review">Review sidecar</label><input id="import-review" type="file" accept=".jsonl,application/x-ndjson,text/plain" disabled /></div><div class="file-control"><label for="import-teacher">Comparison labels</label><input id="import-teacher" type="file" accept=".jsonl,application/x-ndjson,text/plain" disabled /></div></div></details>
  </div>
  <pre id="load-status" class="status" role="status" aria-live="polite"></pre><p id="progress" class="status" role="status"></p>
</section>
<section id="empty-state" class="empty-state" aria-labelledby="empty-title"><h2 id="empty-title">Open a review packet to begin</h2><p>The packet is verified before any evidence appears. Once loaded, you’ll work through only the decisions that need a human judgment.</p><ol><li>Understand what happened</li><li>Choose the better blinded result</li><li>Classify the mismatch and explain why</li></ol></section>
<div id="review-workspace" hidden>
<div id="divergence" class="divergence" hidden></div><div class="shell-layout">
  <aside class="shell-sidebar" aria-label="Review queue"><div class="rail-heading"><h2>Decisions to review</h2><p>Work through each interaction in order. Each item asks what the assistant should do next.</p></div><details class="queue-filters"><summary>Filter queue</summary><label for="filter-family">Scenario family</label><select id="filter-family"></select><label for="filter-action">Action type</label><select id="filter-action"></select></details><div id="stream-list" class="stream-list"></div><section id="cluster-rail" class="cluster-rail" aria-label="Cluster worklist"></section></aside>
  <main class="shell-main">
    <div class="decision-nav" aria-label="Decision navigation"><button type="button" id="btn-prev-decision">← Previous decision</button><span id="nav-meta"></span><button type="button" id="btn-next-decision">Next decision →</button></div>
    <div id="viewport"></div>
    <section class="compare" aria-labelledby="compare-title"><div class="section-heading"><h2 id="compare-title">Which result is better?</h2><p id="compare-guidance">Judge the action that should happen in the situation above. Candidate origins stay hidden until you save.</p></div>${PHASE2_COMPARE_HTML}<div id="oracle-panel" class="panel"></div><div id="teacher-panel" class="panel"></div></section>
    <section class="review-forms" aria-label="Record this decision">
      <fieldset id="decision-review"><legend>Record your judgment</legend>${PHASE2_DECISION_FIELDS_HTML}<div id="legacy-decision-fields" class="legacy-fields"><label>Is the proposed action right? <select id="decision-decision"><option value="">Choose an outcome</option><option value="accept">Correct</option><option value="reject">Incorrect</option><option value="flag">Unsure</option></select></label><input id="decision-reason" type="hidden" /></div><label class="rationale-field" for="decision-note"><span id="decision-rationale-label" class="field-label">Why is this the better result?</span><span id="decision-rationale-help" class="field-help">State the rule or visible fact that decided the comparison.</span><textarea id="decision-note" rows="3" placeholder="Example: The request names no existing reminder, so asking a precise clarification is safer than guessing."></textarea></label><p id="decision-error" class="form-error" role="alert" hidden></p><div class="form-actions"><button type="button" id="btn-save-decision" class="primary-action">Save and continue</button><button type="button" id="btn-skip-decision">Skip for now</button></div></fieldset>
      <details class="stream-review"><summary>Review full interaction</summary><p>A full interaction is the complete event sequence. Use this only when the interaction as a whole needs a separate judgment.</p><fieldset><legend>Interaction-level review</legend><label>Is the full interaction right? <select id="stream-decision"><option value="">Choose an outcome</option><option value="accept">Correct</option><option value="reject">Incorrect</option><option value="flag">Unsure</option></select></label><label>Reason code <input id="stream-reason" type="text" /></label><label>Note <textarea id="stream-note" rows="2"></textarea></label><button type="button" id="btn-save-stream">Save interaction review</button></fieldset></details>
    </section>
    ${PHASE2_CLUSTER_HTML}
    <details class="inspector"><summary>Packet records and raw JSON</summary><p>Technical evidence for debugging or audit. You do not need this to make an ordinary review decision.</p><h3>Current event</h3><pre id="inspect-event"></pre><h3>Decision record</h3><pre id="inspect-oracle"></pre><h3>Candidate evidence</h3><pre id="inspect-teacher"></pre><h3>Derived reducer state</h3><pre id="inspect-state"></pre></details>
    <details class="playback-tools"><summary>Inspect the full event sequence</summary><p>Move through individual events when the current snapshot is not enough.</p><div class="event-controls"><button type="button" id="btn-prev-event">Previous event <kbd>k</kbd></button><button type="button" id="btn-next-event">Next event <kbd>j</kbd></button><button type="button" id="btn-play" aria-pressed="false">Play</button><label for="play-speed">Speed</label><select id="play-speed"><option value="1x">1×</option><option value="4x">4×</option><option value="16x">16×</option></select></div></details>
    <details class="shell-help"><summary>Keyboard shortcuts</summary><ul><li><kbd>n</kbd>/<kbd>p</kbd> next/previous decision</li><li><kbd>j</kbd>/<kbd>k</kbd> next/previous event</li><li><kbd>space</kbd> play or pause events</li><li><kbd>[</kbd>/<kbd>]</kbd> previous/next interaction</li></ul></details>
  </main>
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

const CATEGORY_COPY: Record<D3DisagreementCategory, { label: string; description: string }> = {
  teacher_error: { label: "Reference candidate is wrong", description: "The comparison candidate does not follow the visible evidence or behavior rules." },
  oracle_error: { label: "Expected action is wrong", description: "The expected action encoded in the packet is not the correct outcome." },
  template_error: { label: "Scenario or template caused the mismatch", description: "The rendered scenario is malformed, contradictory, or changes the intended boundary." },
  asset_ambiguity: { label: "Source text is genuinely ambiguous", description: "The source itself leaves a required meaning or referent unresolved." },
  contract_gap: { label: "Rules do not cover this case", description: "The behavior contract does not determine one defensible result." },
  text_equivalent: { label: "Same meaning, different wording", description: "Both responses do the same thing and differ only in acceptable wording." },
  both_legal_but_oracle_preferred: { label: "Both valid, one is preferred", description: "Both actions are allowed, but one better matches the expected policy behavior." },
};

export function categoryCopy(category: D3DisagreementCategory): { label: string; description: string } {
  return CATEGORY_COPY[category];
}

function quoted(text: string): string {
  return `“${text}”`;
}

function duration(ms: number): string {
  if (ms % 3_600_000 === 0) return `${ms / 3_600_000} hour${ms === 3_600_000 ? "" : "s"}`;
  if (ms % 60_000 === 0) return `${ms / 60_000} minute${ms === 60_000 ? "" : "s"}`;
  if (ms % 1_000 === 0) return `${ms / 1_000} seconds`;
  return `${ms} ms`;
}

function words(value: string): string {
  return value.replaceAll("_", " ");
}

export type ActionReferenceLabels = {
  timerMessages: ReadonlyMap<string, string>;
  fireMessages: ReadonlyMap<string, string>;
  resultSubjects?: ReadonlyMap<string, string>;
};

export function summarizeAction(action: Action, references?: ActionReferenceLabels): { verb: string; summary: string } {
  switch (action.type) {
    case "mark":
      return { verb: "Mark text", summary: `Mark ${quoted(action.target.text)} in the visible text.` };
    case "delegate":
      return { verb: "Run lookup", summary: `Look up ${quoted(action.args.query)} using the referenced fact ${quoted(action.fact.text)}.` };
    case "integrate":
      return { verb: "Use result", summary: `Add the available lookup result: ${quoted(action.text)}` };
    case "skip": {
      if (action.reason === "canceled_timer") {
        return { verb: "Skip timer fire", summary: "Leave the due reminder unused because it was canceled." };
      }
      const subject = references?.resultSubjects?.get(action.target_event_id);
      const target = subject ? `the result for ${quoted(subject)}` : "the lookup result";
      if (action.reason === "superseded_query") {
        return { verb: "Skip lookup result", summary: `Leave ${target} unused because a newer request replaced it.` };
      }
      return { verb: "Skip lookup result", summary: `Leave ${target} unused because the user abandoned that lookup.` };
    }
    case "respond":
      return { verb: "Reply to user", summary: action.text };
    case "schedule":
      return { verb: "Create reminder", summary: `Create a recurring reminder every ${duration(action.interval_ms)}: ${quoted(action.message)}.` };
    case "cancel": {
      const target = action.target.kind === "timer"
        ? references?.timerMessages.get(action.target.timer_id) ?? "the selected reminder"
        : action.target.kind === "timers"
          ? action.target.timer_ids.map((id) => references?.timerMessages.get(id) ?? "selected reminder").join(", ")
          : "all active reminders";
      return { verb: "Cancel reminder", summary: `Cancel ${quoted(target)}. Instruction: ${quoted(action.instruction.text)}` };
    }
    case "nudge":
      return { verb: "Send reminder", summary: references?.fireMessages.get(action.fire_event_id)
        ? `Send the due reminder: ${quoted(references.fireMessages.get(action.fire_event_id)!)}.`
        : "Send the reminder that is due now." };
    case "idle":
      return { verb: "Take no action", summary: `Do nothing because the state is ${words(action.reason)}.` };
  }
}

/** Renders only neutral Candidate A/B copy until a decision record exists. */
export function renderBlindedComparison(
  target: HTMLElement,
  decision: Phase2DecisionEvidence | null,
  revealed: boolean,
  references?: ActionReferenceLabels,
): boolean {
  if (!decision || (decision.comparison !== "semantic_review_required" && decision.comparison !== "causal_disagreement")) return false;
  target.replaceChildren();
  target.className = "phase2-candidates";
  for (const candidate of decision.candidates) {
    const copy = summarizeAction(candidate.action, references);
    const panel = document.createElement("article");
    panel.className = "phase2-candidate";
    const header = document.createElement("header");
    const heading = document.createElement("h3");
    heading.textContent = `Candidate ${candidate.candidate_id}`;
    const actionType = document.createElement("span");
    actionType.className = "action-type";
    actionType.textContent = copy.verb;
    const choose = document.createElement("label");
    choose.className = "candidate-choice";
    const input = document.createElement("input");
    input.id = `phase2-choice-${candidate.candidate_id}`;
    input.type = "radio";
    input.name = "phase2-choice";
    input.value = candidate.candidate_id;
    choose.append(input, ` Choose Candidate ${candidate.candidate_id}`);
    header.append(heading, actionType, choose);
    const summary = document.createElement("p");
    summary.className = "candidate-summary";
    summary.textContent = copy.summary;
    const license = document.createElement("p");
    license.className = `candidate-license ${candidate.license.result}`;
    license.textContent = candidate.license.codes.length
      ? `Blocked by action checks: ${candidate.license.codes.map(words).join(", ")}`
      : "Passes action checks";
    const technical = document.createElement("details");
    technical.className = "candidate-technical";
    const technicalLabel = document.createElement("summary");
    technicalLabel.textContent = "Technical details";
    const action = document.createElement("pre");
    action.textContent = actionText(candidate.action);
    technical.append(technicalLabel, action);
    panel.append(header, summary, license, technical);
    if (revealed) {
      const origin = document.createElement("p");
      origin.className = "candidate-origin";
      origin.textContent = `Origin: ${candidate.reveal.origin} · ${Object.entries(candidate.reveal.provenance).map(([name, value]) => `${name}=${value}`).join(" · ")}`;
      technical.append(origin);
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
  references?: ActionReferenceLabels,
): boolean {
  const active = renderBlindedComparison(controls.comparison, decision, revealed, references);
  controls.comparison.hidden = !active;
  controls.oraclePanel.hidden = active;
  controls.teacherPanel.hidden = active;
  controls.fields.hidden = !active;
  if (!active || !decision) return false;
  controls.announcement.textContent = revealed
    ? "Disposition saved. Candidate origins and provenance are now revealed."
    : "Candidates remain blinded until a valid disposition is saved.";
  controls.announcement.setAttribute("aria-live", "polite");
  controls.category.replaceChildren(new Option("Choose an explanation", "", true, true));
  controls.category.options[0].disabled = true;
  categoriesFor(decision).forEach((value) => controls.category.add(new Option(categoryCopy(value).label, value)));
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
  const choiceInputs = [...document.querySelectorAll<HTMLInputElement>('input[name="phase2-choice"]')];
  choiceInputs.forEach((input) => input.setCustomValidity(""));
  const selected = choice?.value === "A" || choice?.value === "B" ? choice.value : null;
  const validCategories = categoriesFor(decision);
  const categoryValue = category.value as D3DisagreementCategory;
  const reason = rationale.value.trim();
  for (const [control, valid, message] of [
    [choice ?? choiceInputs[0] ?? null, selected !== null, "Choose Candidate A or Candidate B."],
    [category, validCategories.includes(categoryValue), "Choose a frozen disagreement category."],
    [rationale, reason.length > 0, "Enter the human rationale before saving."],
  ] as const) {
    if (!valid) {
      control?.setCustomValidity(message);
      control?.focus();
      control?.reportValidity();
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
