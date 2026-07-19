/**
 * Diagnostic review shell — dense local instrument, not the future demo.
 */

import {
  loadPacketFromEntries,
  loadPacketFromFiles,
  sha256Hex,
  type PacketEntry,
} from "./packet-loader";
import {
  eventIndexForPolicySeq,
  indexPacket,
  stateAtEvent,
  type IndexedStream,
  type PacketIndex,
} from "./stream-cache";
import {
  buildStreamQueue,
  collectDisagreementKeys,
  type QueueFilters,
  type StreamQueueItem,
} from "./queue";
import {
  populateReviewFilters,
  setWorkspaceLoaded,
} from "./review-workspace";
import { renderViewport } from "./viewport";
import {
  exportReviewSidecar,
  mergeReviewRecords,
  parseReviewSidecar,
  recordKey,
  recordsFromMap,
  type ReviewDecision,
  type ReviewMap,
  type ReviewRecord,
} from "./review-sidecar";
import {
  clusterEvidenceReady,
  persistClusterProgress,
  persistReviewDraft,
  phase2ReviewContext,
  progressForCluster,
  restoreClusterProgress,
  restoreReviewDraft,
  reviewDraftKey,
  type ClusterProgressMap,
} from "./phase2-review-draft";
import {
  lookupTeacherLabel,
  parseTeacherLabels,
  teacherReviewStatus,
  type TeacherLabelMap,
} from "./teacher-labels";
import {
  applyClusterDisposition,
  clusterEvidenceCases,
  isPhase2Revealed,
  phase2DecisionFor,
  phase2IsBlinded,
  REVIEW_SHELL_HTML,
  renderPhase2Shell,
  renderClusterContext,
  renderClusterRail,
  validatePhase2Selection,
} from "./phase2-review";
import type {
  Action,
  LoadedPacket,
  Phase2Cluster,
  Phase2DecisionIdentity,
  SidecarDecision,
} from "./types";

const PLAYBACK_MS: Record<string, number> = { "1x": 400, "4x": 100, "16x": 25 };

type ShellState = {
  index: PacketIndex | null;
  streamSha: string | null;
  eventIndex: number;
  filters: QueueFilters;
  queue: StreamQueueItem[];
  reviews: ReviewMap;
  packetDraftKey: string | null;
  teacherEvidenceId: string;
  dirty: boolean;
  teacherLabels: TeacherLabelMap;
  playing: boolean;
  playSpeed: keyof typeof PLAYBACK_MS;
  playTimer: number | null;
  selectedCluster: string | null;
  clusterProgress: ClusterProgressMap;
};

const state: ShellState = {
  index: null,
  streamSha: null,
  eventIndex: 0,
  filters: { families: null, actionTypes: null },
  queue: [],
  reviews: new Map(),
  packetDraftKey: null,
  teacherEvidenceId: "none",
  dirty: false,
  teacherLabels: new Map(),
  playing: false,
  playSpeed: "1x",
  playTimer: null,
  selectedCluster: null,
  clusterProgress: new Map(),
};

function $(id: string): HTMLElement {
  const el = document.getElementById(id);
  if (!el) throw new Error(`missing #${id}`);
  return el;
}

function streamKey(sha: string): string {
  return sha.startsWith("sha256:") ? sha : `sha256:${sha}`;
}

function markReviewChanged(): void {
  state.dirty = true;
  persistReviewDraft(window.localStorage, state.packetDraftKey, state.reviews);
}

function restorePacketDrafts(index: PacketIndex): void {
  state.packetDraftKey = reviewDraftKey(index, state.teacherEvidenceId);
  state.reviews = restoreReviewDraft(window.localStorage, index, state.packetDraftKey);
  state.clusterProgress = restoreClusterProgress(
    window.localStorage,
    state.packetDraftKey,
    index,
  );
}

function confirmReviewReplacement(): boolean {
  return !state.dirty || window.confirm("Discard unexported review changes and load another packet?");
}

function currentIndexed(): IndexedStream | null {
  if (!state.index || !state.streamSha) return null;
  return state.index.bySha.get(state.streamSha) ?? null;
}

function currentDecisionIdx(): number | null {
  const indexed = currentIndexed();
  if (!indexed) return null;
  const seq = indexed.reduction.states[state.eventIndex]?.eventSeq;
  return seq === undefined ? null : (indexed.policySeqToDecision.get(seq) ?? null);
}

function stopPlayback(): void {
  state.playing = false;
  if (state.playTimer !== null) {
    window.clearInterval(state.playTimer);
    state.playTimer = null;
  }
  const btn = $("btn-play") as HTMLButtonElement;
  btn.textContent = "Play";
  btn.setAttribute("aria-pressed", "false");
}

function teacherOracleNeedsReview(
  streamSha: string,
  dec: SidecarDecision,
): boolean {
  const label = lookupTeacherLabel(
    state.teacherLabels,
    streamKey(streamSha),
    dec.observed_policy_seq,
  );
  return Boolean(label && teacherReviewStatus(label, dec.action) !== "causally_equivalent");
}

function rebuildQueue(): void {
  if (!state.index) {
    state.queue = [];
    return;
  }
  const disagreementKeys = collectDisagreementKeys(
    state.index.packet.streams,
    teacherOracleNeedsReview,
  );
  state.queue = buildStreamQueue(
    state.index.packet.streams,
    state.filters,
    disagreementKeys,
  );
}

function setStream(sha: string, eventIndex?: number): void {
  state.streamSha = sha;
  const indexed = currentIndexed();
  if (!indexed) return;
  let target = eventIndex;
  if (target === undefined) {
    const firstDecision = indexed.stream.sidecar.decisions[0];
    target = firstDecision
      ? eventIndexForPolicySeq(indexed, firstDecision.observed_policy_seq)
      : 0;
  }
  state.eventIndex = Math.max(0, Math.min(target, indexed.reduction.states.length - 1));
  renderAll();
}

function setQueueItem(item: StreamQueueItem): void {
  state.streamSha = item.streamSha256;
  const indexed = currentIndexed();
  if (!indexed) return;
  const target = item.decisions[0];
  setStream(
    item.streamSha256,
    target ? eventIndexForPolicySeq(indexed, target.policySeq) : undefined,
  );
}

function gotoDecision(delta: number): void {
  const indexed = currentIndexed();
  if (!indexed) return;
  const decisions = indexed.stream.sidecar.decisions;
  if (decisions.length === 0) return;

  const exact = currentDecisionIdx();
  let idx: number;
  if (exact !== null) {
    idx = Math.max(0, Math.min(decisions.length - 1, exact + delta));
  } else {
    const positions = decisions.map((decision) =>
      eventIndexForPolicySeq(indexed, decision.observed_policy_seq),
    );
    if (delta < 0) {
      let prior = -1;
      for (let i = positions.length - 1; i >= 0; i--) {
        if (positions[i] < state.eventIndex) {
          prior = i;
          break;
        }
      }
      idx = prior < 0 ? 0 : prior;
    } else {
      const next = positions.findIndex((position) => position > state.eventIndex);
      idx = next < 0 ? decisions.length - 1 : next;
    }
  }

  const dec = decisions[idx];
  const eventIndex = eventIndexForPolicySeq(indexed, dec.observed_policy_seq);
  state.eventIndex = eventIndex >= 0 ? eventIndex : state.eventIndex;
  renderAll();
}

function gotoEvent(delta: number): void {
  const indexed = currentIndexed();
  if (!indexed) return;
  state.eventIndex = Math.max(
    0,
    Math.min(indexed.reduction.states.length - 1, state.eventIndex + delta),
  );
  renderAll();
}

function progressCounts(): {
  reviewedStreams: number;
  flaggedRejected: number;
  unresolvedDisagreements: number;
  totalStreams: number;
} {
  if (!state.index) {
    return {
      reviewedStreams: 0,
      flaggedRejected: 0,
      unresolvedDisagreements: 0,
      totalStreams: 0,
    };
  }
  let reviewedStreams = 0;
  let flaggedRejected = 0;
  let unresolvedDisagreements = 0;
  const disagreementKeys = collectDisagreementKeys(
    state.index.packet.streams,
    teacherOracleNeedsReview,
  );
  for (const sha of state.index.order) {
    const key = recordKey({
      stream_sha256: streamKey(sha),
      decision_policy_seq: null,
    });
    const rec = state.reviews.get(key);
    if (rec) {
      reviewedStreams++;
      if (rec.decision === "flag" || rec.decision === "reject") flaggedRejected++;
    }
  }
  for (const dkey of disagreementKeys) {
    const sep = dkey.indexOf("\x00");
    const sha = dkey.slice(0, sep);
    const policySeq = Number(dkey.slice(sep + 1));
    const reviewKey = recordKey({
      stream_sha256: streamKey(sha),
      decision_policy_seq: policySeq,
    });
    if (!state.reviews.has(reviewKey)) unresolvedDisagreements++;
  }
  return {
    reviewedStreams,
    flaggedRejected,
    unresolvedDisagreements,
    totalStreams: state.index.order.length,
  };
}

function currentDecision(): SidecarDecision | null {
  const indexed = currentIndexed();
  const decisionIdx = currentDecisionIdx();
  if (!indexed || decisionIdx === null) return null;
  return indexed.stream.sidecar.decisions[decisionIdx] ?? null;
}

function currentOracleAction(): Action | null {
  return currentDecision()?.action ?? null;
}

function currentPhase2Decision() {
  const indexed = currentIndexed();
  return phase2DecisionFor(
    state.index?.packet.phase2ReviewEvidence ?? null,
    indexed ? streamKey(indexed.stream.sha256) : "",
    currentDecision()?.observed_policy_seq ?? null,
  );
}

function selectedCluster(): Phase2Cluster | null {
  return state.index?.packet.phase2ReviewEvidence?.clusters.find(
    (cluster) => cluster.signature === state.selectedCluster,
  ) ?? null;
}

function phase2EvidenceSha256(): string | null {
  return state.index?.packet.integrity.phase2EvidenceSha256 ?? null;
}

function currentPhase2IdentityKey(): string | null {
  const decision = currentPhase2Decision();
  return decision ? recordKey(decision) : null;
}

function renderDivergence(blinded = false): void {
  const box = $("divergence");
  const indexed = currentIndexed();
  if (!indexed) {
    box.hidden = true;
    box.textContent = "";
    return;
  }
  if (blinded) {
    box.hidden = true;
    box.textContent = "";
    return;
  }
  const divs = indexed.fidelity.divergences;
  if (divs.length === 0) {
    box.hidden = true;
    box.textContent = "";
    return;
  }
  box.hidden = false;
  box.setAttribute("role", "alert");
  box.textContent =
    `DIVERGENCE: ${divs.length} mismatch(es). ` +
    divs
      .slice(0, 5)
      .map((d) => `${d.location} ${d.field}: expected ${d.expected} got ${d.actual}`)
      .join(" | ");
}

function renderInspector(
  indexed: IndexedStream,
  vis: ReturnType<typeof stateAtEvent>,
  blinded: boolean,
): void {
  const event = indexed.stream.segments
    .flatMap((s) => s.events)
    .find((e) => e.seq === vis.eventSeq);
  const oracleRec = currentDecision();
  let teacher: unknown = "teacher label not loaded";
  if (oracleRec) {
    const label = lookupTeacherLabel(
      state.teacherLabels,
      streamKey(indexed.stream.sha256),
      oracleRec.observed_policy_seq,
    );
    teacher = label ?? "teacher label not loaded";
  }
  ($("inspect-event") as HTMLPreElement).textContent = JSON.stringify(event ?? null, null, 2);
  ($("inspect-oracle") as HTMLPreElement).textContent = blinded
    ? "Blinded candidate origin and provenance are unavailable until a valid Phase 2 disposition is saved."
    : JSON.stringify(oracleRec, null, 2);
  ($("inspect-teacher") as HTMLPreElement).textContent = blinded
    ? "Blinded candidate origin and provenance are unavailable until a valid Phase 2 disposition is saved."
    : JSON.stringify(teacher, null, 2);
  ($("inspect-state") as HTMLPreElement).textContent = JSON.stringify(vis, null, 2);
}

function renderAll(): void {
  const status = $("load-status");
  const indexed = currentIndexed();
  if (!state.index || !indexed) {
    status.textContent = "No packet loaded.";
    setWorkspaceLoaded(false);
    return;
  }
  setWorkspaceLoaded(true);

  const vis = stateAtEvent(indexed, state.eventIndex);
  const decision = currentDecision();
  const oracle = currentOracleAction();
  const counts = progressCounts();
  const phase2Decision = currentPhase2Decision();
  const phase2Revealed = phase2Decision
    ? isPhase2Revealed(state.reviews, phase2Decision, phase2EvidenceSha256())
    : false;
  const phase2Blinded = phase2IsBlinded(phase2Decision, phase2Revealed);

  status.textContent =
    `Packet OK · ${state.index.order.length} streams · ` +
    `checksums verified · current ${indexed.stream.sha256.slice(0, 12)}… ` +
    `family=${indexed.stream.family}`;

  ($("progress") as HTMLElement).textContent =
    `Reviewed streams: ${counts.reviewedStreams}/${counts.totalStreams} · ` +
    `flagged/rejected: ${counts.flaggedRejected} · ` +
    `unresolved disagreements: ${counts.unresolvedDisagreements}`;

  ($("nav-meta") as HTMLElement).textContent =
    `event ${state.eventIndex + 1}/${indexed.reduction.states.length} ` +
    `seq=${vis.eventSeq} kind=${vis.eventKind} · ` +
    `decision ${currentDecisionIdx() !== null ? currentDecisionIdx()! + 1 : "—"}/` +
    `${indexed.stream.sidecar.decisions.length}`;

  renderDivergence(phase2Blinded);
  const oracleEvidence = decision
    ? {
        floorOpen: decision.floor_open,
        staleToolResultEventIds: decision.stale_tool_result_event_ids,
      }
    : null;
  renderViewport($("viewport"), vis, phase2Blinded ? null : oracle, phase2Blinded ? null : oracleEvidence);
  const actionRow = $("viewport").querySelector<HTMLElement>(".vp-action-row");
  if (actionRow) {
    actionRow.hidden = phase2Blinded;
    actionRow.setAttribute("aria-hidden", String(phase2Blinded));
  }

  const phase2Active = renderPhase2Shell(phase2Decision, phase2Revealed, {
    comparison: $("phase2-compare"), oraclePanel: $("oracle-panel"), teacherPanel: $("teacher-panel"),
    fields: $("phase2-fields"), announcement: $("phase2-reveal"), category: $("phase2-category") as HTMLSelectElement,
  });
  const teacherBox = $("teacher-panel");
  if (decision) {
    const label = lookupTeacherLabel(
      state.teacherLabels,
      streamKey(indexed.stream.sha256),
      decision.observed_policy_seq,
    );
    if (!label) {
      teacherBox.textContent = "Teacher label not loaded.";
    } else {
      const status = teacherReviewStatus(label, decision.action);
      const display = {
        causal_disagreement: "CAUSAL DISAGREEMENT",
        causally_equivalent: "causally equivalent",
        semantic_review_required: "SEMANTIC REVIEW REQUIRED",
      }[status];
      teacherBox.textContent = `Teacher (${display}): ${JSON.stringify(label)}`;
    }
  } else {
    teacherBox.textContent = "Teacher label not loaded.";
  }
  ($("oracle-panel") as HTMLElement).textContent = decision
    ? `Oracle: ${JSON.stringify(decision.action)}`
    : "Oracle: (navigate to a decision)";

  // Review form
  const streamRec = state.reviews.get(
    recordKey({
      stream_sha256: streamKey(indexed.stream.sha256),
      decision_policy_seq: null,
    }),
  );
  ($("stream-decision") as HTMLSelectElement).value = streamRec?.decision ?? "";
  ($("stream-reason") as HTMLInputElement).value = streamRec?.reason_code ?? "";
  ($("stream-note") as HTMLTextAreaElement).value = streamRec?.note ?? "";

  const policySeq = decision?.observed_policy_seq ?? null;
  const decRec =
    policySeq !== null
      ? state.reviews.get(
          recordKey({
            stream_sha256: streamKey(indexed.stream.sha256),
            decision_policy_seq: policySeq,
          }),
        )
      : undefined;
  ($("decision-decision") as HTMLSelectElement).value = decRec?.decision ?? "";
  ($("decision-reason") as HTMLInputElement).value = decRec?.reason_code ?? "";
  ($("decision-note") as HTMLTextAreaElement).value = decRec?.note ?? "";
  if (phase2Active) {
    const choice = decRec?.candidate_choice;
    for (const input of document.querySelectorAll<HTMLInputElement>('input[name="phase2-choice"]')) input.checked = input.value === choice;
    const category = $("phase2-category") as HTMLSelectElement;
    if (decRec?.disagreement_category && [...category.options].some((option) => option.value === decRec.disagreement_category)) category.value = decRec.disagreement_category;
  }

  // Stream list
  const list = $("stream-list");
  list.replaceChildren();
  for (const item of state.queue) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className =
      "stream-item" + (item.streamSha256 === state.streamSha ? " active" : "");
    btn.textContent = `${item.family} · ${item.streamSha256.slice(0, 10)}… · d=${item.decisionCount} · rare=${item.maxRarity}`;
    btn.addEventListener("click", () => setQueueItem(item));
    list.appendChild(btn);
  }

  renderClusterRail($("cluster-rail"), state.index.packet.phase2ReviewEvidence, state.selectedCluster, selectCluster);
  const cluster = selectedCluster();
  $("cluster-context").hidden = cluster === null;
  $("cluster-batch").hidden = cluster === null;
  const progress = cluster
    ? progressForCluster(state.clusterProgress, phase2EvidenceSha256(), cluster)
    : { opened: new Set<string>(), acknowledged: new Set<string>() };
  renderClusterContext(
    $("cluster-context"),
    cluster,
    currentPhase2IdentityKey(),
    progress.opened,
    progress.acknowledged,
    openClusterEvidence,
    acknowledgeClusterEvidence,
  );
  const clusterSave = $("btn-save-cluster") as HTMLButtonElement;
  clusterSave.disabled = !cluster || !clusterEvidenceReady(progress, cluster);
  clusterSave.setAttribute("aria-disabled", String(clusterSave.disabled));
  renderInspector(indexed, vis, phase2Active && !phase2Revealed);
}

function saveStreamReview(): void {
  const indexed = currentIndexed();
  if (!indexed) return;
  const decision = ($("stream-decision") as HTMLSelectElement).value as ReviewDecision | "";
  if (!decision) return;
  const rec: ReviewRecord = {
    stream_sha256: streamKey(indexed.stream.sha256),
    decision_policy_seq: null,
    decision,
    reason_code: ($("stream-reason") as HTMLInputElement).value,
    note: ($("stream-note") as HTMLTextAreaElement).value,
  };
  state.reviews.set(recordKey(rec), rec);
  markReviewChanged();
  renderAll();
}

function selectCluster(cluster: Phase2Cluster): void {
  state.selectedCluster = cluster.signature;
  openClusterEvidence(cluster.representative);
}

function openClusterEvidence(item: Phase2DecisionIdentity): void {
  const cluster = selectedCluster();
  if (!cluster || !clusterEvidenceCases(cluster).some((candidate) => recordKey(candidate) === recordKey(item))) return;
  const indexed = state.index?.bySha.get(item.stream_sha256.slice(7));
  if (!indexed) {
    ($("cluster-status") as HTMLElement).textContent = "The selected evidence case is not present in this packet.";
    return renderAll();
  }
  progressForCluster(state.clusterProgress, phase2EvidenceSha256(), cluster).opened.add(recordKey(item));
  persistClusterProgress(window.localStorage, state.packetDraftKey, state.clusterProgress);
  setStream(
    indexed.stream.sha256,
    eventIndexForPolicySeq(indexed, item.decision_policy_seq),
  );
}

function acknowledgeClusterEvidence(item: Phase2DecisionIdentity, checked: boolean): void {
  const cluster = selectedCluster();
  if (!cluster) return;
  const progress = progressForCluster(state.clusterProgress, phase2EvidenceSha256(), cluster);
  const identity = recordKey(item);
  if (!progress.opened.has(identity)) return;
  if (checked) progress.acknowledged.add(identity);
  else progress.acknowledged.delete(identity);
  persistClusterProgress(window.localStorage, state.packetDraftKey, state.clusterProgress);
  if (checked && clusterEvidenceReady(progress, cluster)) {
    ($("cluster-status") as HTMLElement).textContent = "Three evidence cases acknowledged. Returned to the representative for the batch disposition.";
    openClusterEvidence(cluster.representative);
    return;
  }
  renderAll();
}

function saveClusterDisposition(): void {
  const cluster = selectedCluster();
  const evidence = state.index?.packet.phase2ReviewEvidence;
  const evidenceSha = phase2EvidenceSha256();
  const phase2 = currentPhase2Decision();
  if (!cluster || !evidence || !evidenceSha || !phase2) return;
  const progress = progressForCluster(state.clusterProgress, evidenceSha, cluster);
  if (!clusterEvidenceReady(progress, cluster)) {
    ($("cluster-status") as HTMLElement).textContent = "Open and acknowledge all three selected evidence cases before applying a batch disposition.";
    return;
  }
  if (recordKey(phase2) !== recordKey(cluster.representative)) {
    openClusterEvidence(cluster.representative);
    ($("cluster-status") as HTMLElement).textContent = "Batch not applied. Choose the representative candidate and apply again.";
    ($("phase2-choice-A") as HTMLInputElement).focus();
    return;
  }
  const selection = validatePhase2Selection(
    phase2,
    document.querySelector<HTMLInputElement>('input[name="phase2-choice"]:checked'),
    $("phase2-category") as HTMLSelectElement,
    $("decision-note") as HTMLTextAreaElement,
  );
  if (!selection) return;
  try {
    state.reviews = applyClusterDisposition(
      state.reviews,
      evidence,
      evidenceSha,
      cluster,
      selection.candidate_choice,
      selection.disagreement_category,
      selection.rationale,
      progress.acknowledged,
    );
  } catch (error) {
    ($("cluster-status") as HTMLElement).textContent = error instanceof Error ? error.message : String(error);
    return;
  }
  markReviewChanged();
  ($("cluster-status") as HTMLElement).textContent = "Cluster disposition saved for its members.";
  renderAll();
}

function saveDecisionReview(): void {
  const indexed = currentIndexed();
  const decisionIdx = currentDecisionIdx();
  if (!indexed || decisionIdx === null) return;
  const decision = ($("decision-decision") as HTMLSelectElement).value as ReviewDecision | "";
  if (!decision) return;
  const policySeq = indexed.stream.sidecar.decisions[decisionIdx].observed_policy_seq;
  const phase2 = currentPhase2Decision();
  const selection = phase2 && (phase2.comparison === "semantic_review_required" || phase2.comparison === "causal_disagreement")
    ? validatePhase2Selection(
        phase2,
        document.querySelector<HTMLInputElement>('input[name="phase2-choice"]:checked'),
        $("phase2-category") as HTMLSelectElement,
        $("decision-note") as HTMLTextAreaElement,
      )
    : null;
  if (phase2 && phase2.candidates.length === 2 && !selection) return;
  const evidenceSha = phase2EvidenceSha256();
  if (selection && !evidenceSha) return;
  const rec: ReviewRecord = {
    stream_sha256: streamKey(indexed.stream.sha256),
    decision_policy_seq: policySeq,
    decision,
    reason_code: ($("decision-reason") as HTMLInputElement).value,
    note: selection?.rationale ?? ($("decision-note") as HTMLTextAreaElement).value,
    ...(selection ? {
      candidate_choice: selection.candidate_choice,
      disagreement_category: selection.disagreement_category,
      phase2_evidence_sha256: evidenceSha!,
    } : {}),
  };
  state.reviews.set(recordKey(rec), rec);
  markReviewChanged();
  renderAll();
}

function exportReviews(): void {
  const text = exportReviewSidecar(recordsFromMap(state.reviews));
  const blob = new Blob([text], { type: "application/x-ndjson" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "review-decisions.jsonl";
  a.click();
  URL.revokeObjectURL(url);
  state.dirty = false;
  persistReviewDraft(window.localStorage, state.packetDraftKey, state.reviews);
}

async function importReviews(file: File): Promise<void> {
  if (!state.index) {
    alert("Load a packet first.");
    return;
  }
  const text = await file.text();
  const parsed = parseReviewSidecar(text);
  if (!parsed.ok) {
    alert(`Import rejected:\n${parsed.errors.join("\n")}`);
    return;
  }
  const knownStreams = new Set(state.index.order.map(streamKey));
  const knownSeqs = new Map<string, Set<number>>();
  for (const [sha, indexed] of state.index.bySha) {
    knownSeqs.set(
      streamKey(sha),
      new Set(indexed.stream.sidecar.decisions.map((d) => d.observed_policy_seq)),
    );
  }
  const merged = mergeReviewRecords(
    state.reviews,
    parsed.records,
    knownStreams,
    knownSeqs,
    state.index ? phase2ReviewContext(state.index) : null,
  );
  if (!merged.ok) {
    alert(`Import conflicts/unknown identities:\n${merged.errors.join("\n")}`);
    return;
  }
  state.reviews = merged.merged;
  markReviewChanged();
  renderAll();
}

async function importTeacherLabels(file: File): Promise<void> {
  const text = await file.text();
  const error = await loadTeacherLabelsText(text);
  if (error) alert(`Teacher label import rejected:\n${error}`);
}

/** Test/helper: import normalized labels without browser file plumbing. */
export async function loadTeacherLabelsText(text: string): Promise<string | null> {
  const parsed = parseTeacherLabels(text);
  if (!parsed.ok) {
    return parsed.errors.join("\n");
  }
  persistReviewDraft(window.localStorage, state.packetDraftKey, state.reviews);
  const normalized = [...parsed.labels.entries()]
    .sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0))
    .map(([, label]) => JSON.stringify(label))
    .join("\n");
  state.teacherEvidenceId = await sha256Hex(normalized);
  state.teacherLabels = parsed.labels;
  if (state.index) {
    restorePacketDrafts(state.index);
    state.dirty = false;
  }
  rebuildQueue();
  renderAll();
  return null;
}

async function onPacketSelected(files: FileList | null): Promise<void> {
  if (!files || files.length === 0) return;
  if (!confirmReviewReplacement()) return;
  stopPlayback();
  statusMessage("Verifying packet checksums…");
  const result = await loadPacketFromFiles(Array.from(files));
  if (!result.ok) {
    statusMessage(`BLOCKED:\n${result.errors.slice(0, 20).join("\n")}`);
    state.index = null;
    state.streamSha = null;
    setWorkspaceLoaded(false);
    return;
  }
  state.index = indexPacket(result.packet);
  restorePacketDrafts(state.index);
  state.dirty = false;
  rebuildQueue();
  populateReviewFilters(state.index.packet.streams);
  const first = state.queue[0]?.streamSha256 ?? state.index.order[0];
  const firstItem = state.queue.find((item) => item.streamSha256 === first);
  if (firstItem) setQueueItem(firstItem);
  else setStream(first);
}

function statusMessage(msg: string): void {
  $("load-status").textContent = msg;
}

function applyFilters(): void {
  const fam = ($("filter-family") as HTMLSelectElement).value;
  const act = ($("filter-action") as HTMLSelectElement).value;
  state.filters = {
    families: fam ? new Set([fam]) : null,
    actionTypes: act ? new Set([act]) : null,
  };
  rebuildQueue();
  renderAll();
}

function togglePlay(): void {
  if (state.playing) {
    stopPlayback();
    return;
  }
  state.playing = true;
  ($("btn-play") as HTMLButtonElement).textContent = "Pause";
  ($("btn-play") as HTMLButtonElement).setAttribute("aria-pressed", "true");
  const tick = () => {
    const indexed = currentIndexed();
    if (!indexed) {
      stopPlayback();
      return;
    }
    if (state.eventIndex >= indexed.reduction.states.length - 1) {
      stopPlayback();
      return;
    }
    gotoEvent(1);
  };
  state.playTimer = window.setInterval(tick, PLAYBACK_MS[state.playSpeed]);
}

function onKey(e: KeyboardEvent): void {
  const tag = (e.target as HTMLElement | null)?.tagName;
  if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;

  switch (e.key) {
    case "j":
    case "ArrowDown":
      e.preventDefault();
      gotoEvent(1);
      break;
    case "k":
    case "ArrowUp":
      e.preventDefault();
      gotoEvent(-1);
      break;
    case "n":
      e.preventDefault();
      gotoDecision(1);
      break;
    case "p":
      e.preventDefault();
      gotoDecision(-1);
      break;
    case " ":
      e.preventDefault();
      togglePlay();
      break;
    case "1":
      state.playSpeed = "1x";
      if (state.playing) {
        stopPlayback();
        togglePlay();
      }
      break;
    case "4":
      state.playSpeed = "4x";
      if (state.playing) {
        stopPlayback();
        togglePlay();
      }
      break;
    case "]": {
      if (!state.index || !state.streamSha) break;
      const i = state.queue.findIndex((item) => item.streamSha256 === state.streamSha);
      if (i >= 0 && i < state.queue.length - 1) setQueueItem(state.queue[i + 1]);
      break;
    }
    case "[": {
      if (!state.index || !state.streamSha) break;
      const i = state.queue.findIndex((item) => item.streamSha256 === state.streamSha);
      if (i > 0) setQueueItem(state.queue[i - 1]);
      break;
    }
    default:
      break;
  }
}

function adoptPacket(packet: LoadedPacket): void {
  stopPlayback();
  state.selectedCluster = null;
  state.index = indexPacket(packet);
  setWorkspaceLoaded(true);
  restorePacketDrafts(state.index);
  state.dirty = false;
  rebuildQueue();
  populateReviewFilters(state.index.packet.streams);
  const first = state.queue[0]?.streamSha256 ?? state.index.order[0];
  const firstItem = state.queue.find((item) => item.streamSha256 === first);
  if (firstItem) setQueueItem(firstItem);
  else setStream(first);
}

/** Test/helper: load a packet from in-memory entries (same path as directory pick). */
export async function loadPacketEntries(entries: PacketEntry[]): Promise<string | null> {
  if (!confirmReviewReplacement()) return "packet replacement canceled";
  stopPlayback();
  const result = await loadPacketFromEntries(entries);
  if (!result.ok) {
    statusMessage(`BLOCKED:\n${result.errors.slice(0, 20).join("\n")}`);
    state.index = null;
    state.streamSha = null;
    setWorkspaceLoaded(false);
    return result.errors.join("\n");
  }
  adoptPacket(result.packet);
  return null;
}

/** Test helper: adopt an already-parsed packet (skips filesystem hash gate). */
export function adoptLoadedPacket(packet: LoadedPacket): void {
  adoptPacket(packet);
}

export function mountReviewShell(root: HTMLElement): () => void {
  if (state.playTimer !== null) window.clearInterval(state.playTimer);
  Object.assign(state, {
    index: null,
    streamSha: null,
    eventIndex: 0,
    filters: { families: null, actionTypes: null },
    queue: [],
    reviews: new Map(),
    packetDraftKey: null,
    teacherEvidenceId: "none",
    dirty: false,
    teacherLabels: new Map(),
    playing: false,
    playSpeed: "1x",
    playTimer: null,
    selectedCluster: null,
    clusterProgress: new Map(),
  });
  root.innerHTML = REVIEW_SHELL_HTML;
  setWorkspaceLoaded(false);

  const packetInput = $("packet-dir") as HTMLInputElement;
  packetInput.addEventListener("change", () => void onPacketSelected(packetInput.files));

  $("btn-prev-event").addEventListener("click", () => gotoEvent(-1));
  $("btn-next-event").addEventListener("click", () => gotoEvent(1));
  $("btn-prev-decision").addEventListener("click", () => gotoDecision(-1));
  $("btn-next-decision").addEventListener("click", () => gotoDecision(1));
  $("btn-play").addEventListener("click", () => togglePlay());
  ($("play-speed") as HTMLSelectElement).addEventListener("change", (e) => {
    state.playSpeed = (e.target as HTMLSelectElement).value as keyof typeof PLAYBACK_MS;
    if (state.playing) {
      stopPlayback();
      togglePlay();
    }
  });
  $("filter-family").addEventListener("change", () => applyFilters());
  $("filter-action").addEventListener("change", () => applyFilters());
  $("btn-save-stream").addEventListener("click", () => saveStreamReview());
  $("btn-save-decision").addEventListener("click", () => saveDecisionReview());
  $("btn-save-cluster").addEventListener("click", () => saveClusterDisposition());
  $("btn-export").addEventListener("click", () => exportReviews());
  ($("import-review") as HTMLInputElement).addEventListener("change", (e) => {
    const f = (e.target as HTMLInputElement).files?.[0];
    if (f) void importReviews(f);
  });
  ($("import-teacher") as HTMLInputElement).addEventListener("change", (e) => {
    const f = (e.target as HTMLInputElement).files?.[0];
    if (f) void importTeacherLabels(f);
  });

  const onKeyBound = (e: KeyboardEvent) => onKey(e);
  window.addEventListener("keydown", onKeyBound);
  const onUnload = (event: BeforeUnloadEvent) => {
    stopPlayback();
    if (state.dirty) {
      event.preventDefault();
      event.returnValue = "";
    }
  };
  window.addEventListener("beforeunload", onUnload);

  statusMessage("Select a local packet directory (e.g. review/phase1/teacher-canary).");

  return () => {
    stopPlayback();
    window.removeEventListener("keydown", onKeyBound);
    window.removeEventListener("beforeunload", onUnload);
  };
}
