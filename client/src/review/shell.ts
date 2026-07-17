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
  listActionTypes,
  listFamilies,
  type QueueFilters,
  type StreamQueueItem,
} from "./queue";
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
  lookupTeacherLabel,
  parseTeacherLabels,
  teacherReviewStatus,
  type TeacherLabelMap,
} from "./teacher-labels";
import type { Action, LoadedPacket, SidecarDecision } from "./types";

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
};

function $(id: string): HTMLElement {
  const el = document.getElementById(id);
  if (!el) throw new Error(`missing #${id}`);
  return el;
}

function streamKey(sha: string): string {
  return sha.startsWith("sha256:") ? sha : `sha256:${sha}`;
}

function draftKey(index: PacketIndex): string {
  const integrity = index.packet.integrity;
  return (
    "wp1-8-review-draft:v1:" +
    `${integrity.manifestSha256}:${integrity.sourceIndexSha256}:${state.teacherEvidenceId}`
  );
}

function persistReviewDraft(): void {
  if (!state.packetDraftKey) return;
  try {
    window.localStorage.setItem(
      state.packetDraftKey,
      exportReviewSidecar(recordsFromMap(state.reviews)),
    );
  } catch {
    // beforeunload/packet-replacement guards still protect an unexported review.
  }
}

function markReviewChanged(): void {
  state.dirty = true;
  persistReviewDraft();
}

function restoreReviewDraft(index: PacketIndex): ReviewMap {
  const key = draftKey(index);
  state.packetDraftKey = key;
  let text: string | null = null;
  try {
    text = window.localStorage.getItem(key);
  } catch {
    return new Map();
  }
  if (!text) return new Map();
  const parsed = parseReviewSidecar(text);
  if (!parsed.ok) return new Map();
  const knownStreams = new Set(index.order.map(streamKey));
  const knownSeqs = new Map<string, Set<number>>();
  for (const [sha, indexed] of index.bySha) {
    knownSeqs.set(
      streamKey(sha),
      new Set(indexed.stream.sidecar.decisions.map((decision) => decision.observed_policy_seq)),
    );
  }
  const restored = mergeReviewRecords(new Map(), parsed.records, knownStreams, knownSeqs);
  return restored.ok ? restored.merged : new Map();
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

function renderDivergence(): void {
  const box = $("divergence");
  const indexed = currentIndexed();
  if (!indexed) {
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

function renderInspector(indexed: IndexedStream, vis: ReturnType<typeof stateAtEvent>): void {
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
  ($("inspect-oracle") as HTMLPreElement).textContent = JSON.stringify(oracleRec, null, 2);
  ($("inspect-teacher") as HTMLPreElement).textContent = JSON.stringify(teacher, null, 2);
  ($("inspect-state") as HTMLPreElement).textContent = JSON.stringify(vis, null, 2);
}

function renderAll(): void {
  const status = $("load-status");
  const indexed = currentIndexed();
  if (!state.index || !indexed) {
    status.textContent = "No packet loaded.";
    return;
  }

  const vis = stateAtEvent(indexed, state.eventIndex);
  const decision = currentDecision();
  const oracle = currentOracleAction();
  const counts = progressCounts();

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

  renderDivergence();
  const oracleEvidence = decision
    ? {
        floorOpen: decision.floor_open,
        staleToolResultEventIds: decision.stale_tool_result_event_ids,
      }
    : null;
  renderViewport($("viewport"), vis, oracle, oracleEvidence);

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

  renderInspector(indexed, vis);
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

function saveDecisionReview(): void {
  const indexed = currentIndexed();
  const decisionIdx = currentDecisionIdx();
  if (!indexed || decisionIdx === null) return;
  const decision = ($("decision-decision") as HTMLSelectElement).value as ReviewDecision | "";
  if (!decision) return;
  const policySeq = indexed.stream.sidecar.decisions[decisionIdx].observed_policy_seq;
  const rec: ReviewRecord = {
    stream_sha256: streamKey(indexed.stream.sha256),
    decision_policy_seq: policySeq,
    decision,
    reason_code: ($("decision-reason") as HTMLInputElement).value,
    note: ($("decision-note") as HTMLTextAreaElement).value,
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
  persistReviewDraft();
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
  const merged = mergeReviewRecords(state.reviews, parsed.records, knownStreams, knownSeqs);
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
  persistReviewDraft();
  const normalized = [...parsed.labels.entries()]
    .sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0))
    .map(([, label]) => JSON.stringify(label))
    .join("\n");
  state.teacherEvidenceId = await sha256Hex(normalized);
  state.teacherLabels = parsed.labels;
  if (state.index) {
    state.reviews = restoreReviewDraft(state.index);
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
    return;
  }
  state.index = indexPacket(result.packet);
  state.reviews = restoreReviewDraft(state.index);
  state.dirty = false;
  rebuildQueue();
  populateFilters();
  const first = state.queue[0]?.streamSha256 ?? state.index.order[0];
  const firstItem = state.queue.find((item) => item.streamSha256 === first);
  if (firstItem) setQueueItem(firstItem);
  else setStream(first);
}

function statusMessage(msg: string): void {
  $("load-status").textContent = msg;
}

function populateFilters(): void {
  if (!state.index) return;
  const fam = $("filter-family") as HTMLSelectElement;
  const act = $("filter-action") as HTMLSelectElement;
  fam.replaceChildren();
  act.replaceChildren();
  const allFam = document.createElement("option");
  allFam.value = "";
  allFam.textContent = "All families";
  fam.appendChild(allFam);
  for (const f of listFamilies(state.index.packet.streams)) {
    const o = document.createElement("option");
    o.value = f;
    o.textContent = f;
    fam.appendChild(o);
  }
  const allAct = document.createElement("option");
  allAct.value = "";
  allAct.textContent = "All actions";
  act.appendChild(allAct);
  for (const a of listActionTypes(state.index.packet.streams)) {
    const o = document.createElement("option");
    o.value = a;
    o.textContent = a;
    act.appendChild(o);
  }
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
  state.index = indexPacket(packet);
  state.reviews = restoreReviewDraft(state.index);
  state.dirty = false;
  rebuildQueue();
  populateFilters();
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
  });
  root.innerHTML = SHELL_HTML;

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

const SHELL_HTML = `
<header class="shell-header">
  <h1>WP1-8 Review Shell</h1>
  <p class="shell-sub">Local diagnostic instrument · packet bytes are never mutated</p>
</header>

<section class="shell-load" aria-label="Packet load">
  <label for="packet-dir">Packet directory</label>
  <input id="packet-dir" type="file" webkitdirectory directory multiple />
  <label for="import-review">Import review sidecar</label>
  <input id="import-review" type="file" accept=".jsonl,application/x-ndjson,text/plain" />
  <label for="import-teacher">Import teacher labels</label>
  <input id="import-teacher" type="file" accept=".jsonl,application/x-ndjson,text/plain" />
  <button type="button" id="btn-export">Export review sidecar</button>
  <pre id="load-status" class="status" role="status" aria-live="polite"></pre>
  <p id="progress" class="status" role="status"></p>
</section>

<div id="divergence" class="divergence" hidden></div>

<div class="shell-layout">
  <aside class="shell-sidebar" aria-label="Streams">
    <label for="filter-family">Family</label>
    <select id="filter-family"></select>
    <label for="filter-action">Action</label>
    <select id="filter-action"></select>
    <div id="stream-list" class="stream-list"></div>
  </aside>

  <main class="shell-main">
    <div class="shell-nav" aria-label="Navigation">
      <button type="button" id="btn-prev-event">Prev event (k)</button>
      <button type="button" id="btn-next-event">Next event (j)</button>
      <button type="button" id="btn-prev-decision">Prev decision (p)</button>
      <button type="button" id="btn-next-decision">Next decision (n)</button>
      <button type="button" id="btn-play" aria-pressed="false">Play</button>
      <label for="play-speed">Speed</label>
      <select id="play-speed">
        <option value="1x">1×</option>
        <option value="4x">4×</option>
        <option value="16x">16×</option>
      </select>
      <span id="nav-meta"></span>
    </div>

    <div id="viewport"></div>

    <section class="compare" aria-label="Oracle vs teacher">
      <div id="oracle-panel" class="panel"></div>
      <div id="teacher-panel" class="panel"></div>
    </section>

    <section class="review-forms" aria-label="Review decisions">
      <fieldset>
        <legend>Stream-level accept/reject/flag</legend>
        <label>Decision
          <select id="stream-decision">
            <option value="">—</option>
            <option value="accept">accept</option>
            <option value="reject">reject</option>
            <option value="flag">flag</option>
          </select>
        </label>
        <label>Reason code <input id="stream-reason" type="text" /></label>
        <label>Note <textarea id="stream-note" rows="2"></textarea></label>
        <button type="button" id="btn-save-stream">Save stream review</button>
      </fieldset>
      <fieldset>
        <legend>Per-decision note</legend>
        <label>Decision
          <select id="decision-decision">
            <option value="">—</option>
            <option value="accept">accept</option>
            <option value="reject">reject</option>
            <option value="flag">flag</option>
          </select>
        </label>
        <label>Reason code <input id="decision-reason" type="text" /></label>
        <label>Note <textarea id="decision-note" rows="2"></textarea></label>
        <button type="button" id="btn-save-decision">Save decision review</button>
      </fieldset>
    </section>

    <details class="inspector">
      <summary>Raw JSON inspector</summary>
      <h3>Current event</h3>
      <pre id="inspect-event"></pre>
      <h3>Oracle record</h3>
      <pre id="inspect-oracle"></pre>
      <h3>Teacher record</h3>
      <pre id="inspect-teacher"></pre>
      <h3>Derived reducer state</h3>
      <pre id="inspect-state"></pre>
    </details>
  </main>

  <aside class="shell-help" aria-label="Keyboard shortcuts">
    <h2>Shortcuts</h2>
    <ul>
      <li><kbd>j</kbd>/<kbd>↓</kbd> next event</li>
      <li><kbd>k</kbd>/<kbd>↑</kbd> prev event</li>
      <li><kbd>n</kbd> next decision</li>
      <li><kbd>p</kbd> prev decision</li>
      <li><kbd>space</kbd> play/pause</li>
      <li><kbd>1</kbd>/<kbd>4</kbd> playback speed</li>
      <li><kbd>[</kbd>/<kbd>]</kbd> prev/next stream</li>
    </ul>
  </aside>
</div>
`;
