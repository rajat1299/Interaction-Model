/**
 * Interaction viewport — plain DOM rendering primitives.
 * Independent of shell navigation so Phase 6 can restyle without changing semantics.
 */

import type { Action, CanonicalEventEnvelope } from "./types";
import type { VisibleState } from "./reducer";

export type Utf16Span = { start: number; end: number; className: string };

/** Highlight by UTF-16 code-unit offsets (JS string indices). */
export function buildHighlightedNodes(
  text: string,
  spans: Utf16Span[],
): DocumentFragment {
  const frag = document.createDocumentFragment();
  const len = text.length;

  type Boundary = { at: number; kind: "start" | "end"; className: string; order: number };
  const boundaries: Boundary[] = [];
  spans.forEach((s, i) => {
    const start = Math.max(0, Math.min(len, s.start));
    const end = Math.max(start, Math.min(len, s.end));
    if (start === end) return;
    boundaries.push({ at: start, kind: "start", className: s.className, order: i });
    boundaries.push({ at: end, kind: "end", className: s.className, order: i });
  });
  boundaries.sort((a, b) => {
    if (a.at !== b.at) return a.at - b.at;
    if (a.kind !== b.kind) return a.kind === "end" ? -1 : 1;
    return a.order - b.order;
  });

  let cursor = 0;
  const active: string[] = [];
  const flush = (until: number) => {
    if (until <= cursor) return;
    const slice = text.slice(cursor, until);
    if (active.length === 0) {
      frag.appendChild(document.createTextNode(slice));
    } else {
      const el = document.createElement("span");
      el.className = [...new Set(active)].join(" ");
      el.textContent = slice;
      frag.appendChild(el);
    }
    cursor = until;
  };

  for (const b of boundaries) {
    flush(b.at);
    if (b.kind === "start") active.push(b.className);
    else {
      const idx = active.lastIndexOf(b.className);
      if (idx >= 0) active.splice(idx, 1);
    }
  }
  flush(len);
  return frag;
}

function el(tag: string, className: string, parent: HTMLElement): HTMLElement {
  const node = document.createElement(tag);
  node.className = className;
  parent.appendChild(node);
  return node;
}

export function renderSnapshotSurface(host: HTMLElement, state: VisibleState): void {
  host.replaceChildren();
  host.className = "vp-snapshot";
  host.setAttribute("role", "region");
  host.setAttribute("aria-label", "Text snapshot");

  const spans: Utf16Span[] = [];
  const selStart = Math.min(state.selectionStart, state.selectionEnd);
  const selEnd = Math.max(state.selectionStart, state.selectionEnd);
  if (selStart !== selEnd) {
    spans.push({ start: selStart, end: selEnd, className: "vp-selection" });
  }
  for (const m of state.marks) {
    spans.push({ start: m.targetStart, end: m.targetEnd, className: "vp-mark" });
  }
  for (const group of state.ambiguousMarks) {
    for (const target of group.targets) {
      spans.push({
        start: target.targetStart,
        end: target.targetEnd,
        className: "vp-mark-ambiguous",
      });
    }
  }

  const pre = el("pre", "vp-snapshot-text", host);
  pre.appendChild(buildHighlightedNodes(state.text, spans));

}

export function renderMarkList(host: HTMLElement, state: VisibleState): void {
  host.replaceChildren();
  host.className = "vp-marks";
  host.setAttribute("aria-label", "Marks");
  if (state.marks.length === 0 && state.ambiguousMarks.length === 0) {
    host.textContent = "No marks";
    return;
  }
  const ul = document.createElement("ul");
  for (const m of state.marks) {
    const li = document.createElement("li");
    li.className = "vp-mark-row";
    li.textContent = `mark ${m.markEventId}: [${m.targetStart},${m.targetEnd}] “${m.targetText}” ← “${m.instructionText}”`;
    ul.appendChild(li);
  }
  for (const group of state.ambiguousMarks) {
    const li = document.createElement("li");
    li.className = "vp-mark-row vp-mark-row-ambiguous";
    li.textContent =
      `ambiguous mark ${group.markEventId}: ` +
      group.targets
        .map((target) => `[${target.targetStart},${target.targetEnd}] “${target.targetText}”`)
        .join(" or ");
    ul.appendChild(li);
  }
  host.appendChild(ul);
}

export function renderToolCards(host: HTMLElement, state: VisibleState): void {
  host.replaceChildren();
  host.className = "vp-tools";
  host.setAttribute("aria-label", "Tool requests");
  if (state.toolRequests.length === 0) {
    host.textContent = "No tool requests";
    return;
  }
  for (const t of state.toolRequests) {
    const card = el("article", `vp-tool-card vp-tool-${t.status}`, host);
    const title = el("h4", "", card);
    title.textContent = `${t.requestId} · ${t.status}`;
    const body = el("pre", "", card);
    body.textContent = JSON.stringify(
      {
        query: t.query,
        fact: t.factText || null,
        resultEventId: t.resultEventId,
        resultStatus: t.resultStatus,
        open: state.openToolResultEventIds.includes(t.resultEventId ?? ""),
      },
      null,
      2,
    );
  }
}

export function renderIntegrations(host: HTMLElement, state: VisibleState): void {
  host.replaceChildren();
  host.className = "vp-integrations";
  host.setAttribute("aria-label", "Integrations and responses");
  const parts: string[] = [];
  for (const i of state.integrations) parts.push(`integrate ${i.resultEventId}: ${i.text}`);
  for (const r of state.responses) parts.push(`respond → ${r.replyToEventId}: ${r.text}`);
  host.textContent = parts.length ? parts.join("\n") : "No integrations/responses";
}

export function renderNudgeChips(host: HTMLElement, state: VisibleState): void {
  host.replaceChildren();
  host.className = "vp-nudges";
  host.setAttribute("aria-label", "Nudges");
  if (state.nudges.length === 0) {
    host.textContent = "No nudges";
    return;
  }
  for (const n of state.nudges) {
    const chip = el("span", "vp-nudge-chip", host);
    chip.textContent = `nudge ${n.fireEventId}`;
  }
}

export function renderTimerStatus(host: HTMLElement, state: VisibleState): void {
  host.replaceChildren();
  host.className = "vp-timers";
  host.setAttribute("aria-label", "Timers");
  if (state.timers.length === 0) {
    host.textContent = "No timers";
    return;
  }
  const ul = document.createElement("ul");
  for (const t of state.timers) {
    const li = document.createElement("li");
    li.className = `vp-timer vp-timer-${t.status}`;
    li.textContent = `${t.timerId} ${t.status} fires=${t.fireCount} “${t.message}”`;
    ul.appendChild(li);
  }
  const open = el("div", "", host);
  open.textContent = `open fires: ${state.openTimerFireEventIds.join(", ") || "none"}`;
  host.prepend(ul);
}

export function renderActionRow(
  host: HTMLElement,
  opts: {
    executed: Action | null;
    attempted: Action | null;
    license: string | null;
    oracle: Action | null;
  },
): void {
  host.replaceChildren();
  host.className = "vp-action-row";
  host.setAttribute("aria-label", "Model action");

  const row = (label: string, value: string) => {
    const d = document.createElement("div");
    const s = document.createElement("strong");
    s.textContent = `${label}: `;
    d.append(s, document.createTextNode(value));
    host.appendChild(d);
  };

  row("executed", opts.executed ? JSON.stringify(opts.executed) : "—");
  row(
    "raw attempted",
    opts.attempted ? JSON.stringify(opts.attempted) : "not present in packet",
  );
  row("license", opts.license ?? "not present in packet");
  row("oracle", opts.oracle ? JSON.stringify(opts.oracle) : "—");
}

export type OracleEvidenceOverlay = {
  floorOpen: boolean;
  staleToolResultEventIds: string[];
  openTimerFireEventIds?: string[];
};

export function renderVisibleContext(
  host: HTMLElement,
  state: VisibleState,
  oracleEvidence: OracleEvidenceOverlay | null = null,
): void {
  host.replaceChildren();
  host.className = "vp-context";
  host.setAttribute("aria-label", "Visible context");
  const pre = el("pre", "", host);
  pre.textContent = JSON.stringify(
    {
      floorOwned: state.floorOwned,
      // Oracle evidence — not reconstructed by the stream reducer.
      floorOpen: oracleEvidence?.floorOpen ?? "not reconstructed from stream",
      staleToolResultEventIds:
        oracleEvidence?.staleToolResultEventIds ?? "not reconstructed from stream",
      pendingRequestIds: state.pendingRequestIds,
      openToolResultEventIds: state.openToolResultEventIds,
      openTimerFireEventIds: state.openTimerFireEventIds,
      dispositions: state.dispositions.filter((d) => d.state !== "open"),
    },
    null,
    2,
  );
}

export function renderCheckpointMarker(host: HTMLElement, state: VisibleState): void {
  host.replaceChildren();
  host.className = "vp-checkpoint";
  if (!state.checkpoint) {
    host.hidden = true;
    return;
  }
  host.hidden = false;
  host.textContent =
    `checkpoint boundary · segment ${state.checkpoint.segmentIndex}` +
    ` · covers_through_policy_seq ${state.checkpoint.coversThroughPolicySeq}` +
    ` · prev ${state.checkpoint.previousSegmentHash.slice(0, 19)}…`;
}

export type ActionReferences = {
  timerMessages: ReadonlyMap<string, string>;
  fireMessages: ReadonlyMap<string, string>;
  resultSubjects: ReadonlyMap<string, string>;
};

export function actionReferencesFor(
  events: CanonicalEventEnvelope[],
  beforeSeq = Number.POSITIVE_INFINITY,
): ActionReferences {
  const timerMessages = new Map<string, string>();
  const fireMessages = new Map<string, string>();
  const requestSubjects = new Map<string, string>();
  const resultSubjects = new Map<string, string>();
  for (const event of events) {
    if (event.seq > beforeSeq) break;
    if (event.kind === "scheduled") timerMessages.set(event.payload.timer_id, event.payload.message);
    if (event.kind === "fire") fireMessages.set(event.id, timerMessages.get(event.payload.timer_id) ?? "due reminder");
    if (event.kind === "state_checkpoint") {
      event.payload.pending_tools.forEach((item) => requestSubjects.set(item.request_id, item.args.query));
      event.payload.open_tool_results.forEach((item) => resultSubjects.set(item.event_id, item.args.query));
    }
    if (event.kind === "tool_requested") requestSubjects.set(event.payload.request_id, event.payload.args.query);
    if (event.kind === "result") {
      const subject = requestSubjects.get(event.payload.request_id);
      if (subject) resultSubjects.set(event.id, subject);
    }
  }
  return { timerMessages, fireMessages, resultSubjects };
}

function elapsedTimes(events: CanonicalEventEnvelope[]): Map<number, number> {
  let elapsed = 0;
  const result = new Map<number, number>();
  for (const event of events) {
    elapsed += event.dt_ms;
    result.set(event.seq, elapsed);
  }
  return result;
}

function elapsedLabel(ms: number): string {
  if (ms < 1_000) return `${ms} ms`;
  if (ms < 60_000) return `${(ms / 1_000).toFixed(1)}s`;
  const minutes = Math.floor(ms / 60_000);
  const remainder = ms % 60_000;
  if (remainder === 0) return `${minutes} minute${minutes === 1 ? "" : "s"}`;
  return `${minutes}m ${(remainder / 1_000).toFixed(1)}s`;
}

function renderTimeline(
  host: HTMLElement,
  events: CanonicalEventEnvelope[],
  currentSeq: number,
  references: ActionReferences,
): void {
  const times = elapsedTimes(events);
  const list = document.createElement("ol");
  list.className = "vp-timeline-list";
  let priorText: string | null = null;
  const add = (event: CanonicalEventEnvelope, text: string) => {
    const item = document.createElement("li");
    const time = document.createElement("time");
    time.textContent = `+${elapsedLabel(times.get(event.seq) ?? 0)}`;
    const description = document.createElement("span");
    description.textContent = text;
    item.append(time, description);
    list.append(item);
  };

  for (const event of events) {
    if (event.seq >= currentSeq) break;
    switch (event.kind) {
      case "snapshot":
        if (event.payload.text !== priorText) {
          add(event, `User wrote: “${event.payload.text}”`);
          priorText = event.payload.text;
        }
        break;
      case "annotation":
        add(event, `User added a note: “${event.payload.text}”`);
        break;
      case "scheduled":
        add(event, `Reminder created: “${event.payload.message}” — repeats every ${elapsedLabel(event.payload.interval_ms)}.`);
        break;
      case "fire":
        add(event, `Reminder became due: “${references.fireMessages.get(event.id) ?? "due reminder"}”.`);
        break;
      case "tool_requested":
        add(event, `Lookup started for “${event.payload.args.query}”.`);
        break;
      case "result":
        add(event, `The lookup ${event.payload.status === "succeeded" ? "returned a result" : "failed"}.`);
        break;
      case "action_rejected":
        add(event, `A proposed action was blocked because of ${event.payload.reason.replaceAll("_", " ")}.`);
        break;
      case "action_executed": {
        const action = event.payload.action;
        if (action.type === "nudge") add(event, `Reminder delivered: “${references.fireMessages.get(action.fire_event_id) ?? "due reminder"}”.`);
        else if (action.type === "cancel") {
          const messages = action.target.kind === "timer"
            ? [references.timerMessages.get(action.target.timer_id) ?? "selected reminder"]
            : action.target.kind === "timers"
              ? action.target.timer_ids.map((id) => references.timerMessages.get(id) ?? "selected reminder")
              : ["all active reminders"];
          add(event, `Reminder canceled: ${messages.map((message) => `“${message}”`).join(", ")}.`);
        } else if (action.type === "respond") add(event, `Assistant replied: “${action.text}”`);
        else if (action.type === "delegate") add(event, `Assistant requested a lookup for “${action.args.query}”.`);
        else if (action.type === "integrate") add(event, `Assistant used the lookup result: “${action.text}”`);
        else if (action.type === "skip") add(event, `Assistant left a result unused because it was ${action.reason.replaceAll("_", " ")}.`);
        else if (action.type === "mark") add(event, `Assistant marked “${action.target.text}”.`);
        break;
      }
      default:
        break;
    }
  }
  host.replaceChildren(list);
}

function renderAttention(
  host: HTMLElement,
  state: VisibleState,
  events: CanonicalEventEnvelope[],
  evidence: OracleEvidenceOverlay | null,
  references: ActionReferences,
): void {
  host.replaceChildren();
  host.className = "vp-attention";
  const title = el("h3", "", host);
  title.textContent = "What needs attention now";
  const text = el("p", "", host);
  if (state.activity === "active" || state.isComposing) {
    text.textContent = "The user is still typing, so the assistant should not interrupt.";
    return;
  }
  const openFires = evidence?.openTimerFireEventIds ?? state.openTimerFireEventIds;
  const target = openFires.at(-1);
  if (target) {
    const event = events.find((item) => item.id === target);
    const times = elapsedTimes(events);
    const age = Math.max(0, (times.get(state.eventSeq) ?? state.elapsedMs) - (event ? times.get(event.seq) ?? 0 : 0));
    text.textContent = `The reminder “${references.fireMessages.get(target) ?? "due reminder"}” became due ${elapsedLabel(age)} ago.`;
  } else if (evidence?.staleToolResultEventIds.length) {
    text.textContent = "A lookup result is stale and should not be used as if it were current.";
  } else if (state.openToolResultEventIds.length) {
    text.textContent = "A lookup result is ready for the assistant to use or explicitly leave unused.";
  } else if (state.pendingRequestIds.length) {
    text.textContent = "A lookup is still running; the assistant should wait for its result.";
  } else {
    text.textContent = "No pending reminder or lookup explains this decision. Review the proposed action against the visible request and state.";
  }
}

function renderSituationFacts(
  host: HTMLElement,
  state: VisibleState,
  oracleEvidence: OracleEvidenceOverlay | null,
): void {
  host.replaceChildren();
  host.className = "vp-facts";
  const facts: string[] = [
    state.activity === "active"
      ? "The user is still editing and owns the floor."
      : "The user has paused editing.",
  ];
  if (oracleEvidence?.floorOpen) facts.push("A response window is open for the assistant.");

  const activeTimers = state.timers.filter((timer) => timer.status === "active");
  if (activeTimers.length) {
    facts.push(`Active reminders: ${activeTimers.map((timer) => `“${timer.message}”`).join(", ")}.`);
  } else {
    facts.push("There are no active reminders.");
  }
  const openFires = oracleEvidence?.openTimerFireEventIds ?? state.openTimerFireEventIds;
  if (openFires.length) facts.push(`${openFires.length} reminder${openFires.length === 1 ? " is" : "s are"} due now.`);
  if (state.pendingRequestIds.length) facts.push(`${state.pendingRequestIds.length} lookup request${state.pendingRequestIds.length === 1 ? " is" : "s are"} still pending.`);
  if (state.openToolResultEventIds.length) facts.push(`${state.openToolResultEventIds.length} lookup result${state.openToolResultEventIds.length === 1 ? " is" : "s are"} available.`);
  if (oracleEvidence?.staleToolResultEventIds.length) facts.push(`${oracleEvidence.staleToolResultEventIds.length} lookup result${oracleEvidence.staleToolResultEventIds.length === 1 ? " is" : "s are"} stale.`);
  if (state.marks.length || state.ambiguousMarks.length) facts.push(`${state.marks.length + state.ambiguousMarks.length} text mark${state.marks.length + state.ambiguousMarks.length === 1 ? " is" : "s are"} in scope.`);

  const list = document.createElement("ul");
  for (const fact of facts) {
    const item = document.createElement("li");
    item.textContent = fact;
    list.append(item);
  }
  host.append(list);
}

export function renderViewport(
  root: HTMLElement,
  state: VisibleState,
  oracle: Action | null,
  oracleEvidence: OracleEvidenceOverlay | null = null,
  events: CanonicalEventEnvelope[] = [],
): void {
  root.replaceChildren();
  root.className = "vp-root";

  const section = (cls: string) => el("div", cls, root);

  const heading = section("vp-heading");
  const title = el("h2", "", heading);
  title.textContent = `Review at +${elapsedLabel(state.elapsedMs)}`;
  const guidance = el("p", "", heading);
  guidance.textContent = "This story stops immediately before the proposed action you are judging.";

  const references = actionReferencesFor(events, state.eventSeq);
  renderAttention(section("vp-attention"), state, events, oracleEvidence, references);

  const timeline = section("vp-timeline");
  const timelineTitle = el("h3", "", timeline);
  timelineTitle.textContent = "Earlier in this interaction";
  const timelineBody = el("div", "", timeline);
  renderTimeline(timelineBody, events, state.eventSeq, references);

  const snapshot = section("vp-visible-text");
  const snapshotLabel = el("p", "vp-snapshot-label", snapshot);
  snapshotLabel.textContent = "Still visible in the editor";
  const snapshotSurface = el("div", "vp-snapshot-surface", snapshot);
  renderSnapshotSurface(snapshotSurface, state);
  renderSituationFacts(section("vp-facts"), state, oracleEvidence);

  const technical = document.createElement("details");
  technical.className = "vp-technical";
  const technicalLabel = document.createElement("summary");
  technicalLabel.textContent = "Technical details";
  technical.append(technicalLabel);
  root.append(technical);
  const technicalSection = (cls: string) => el("div", cls, technical);
  renderCheckpointMarker(technicalSection("vp-checkpoint"), state);
  renderActionRow(technicalSection("vp-action-row"), {
    executed: state.executedAction,
    attempted: state.rawAttemptedAction,
    license: state.licenseBlockCode,
    oracle,
  });
  renderVisibleContext(technicalSection("vp-context"), state, oracleEvidence);
  renderMarkList(technicalSection("vp-marks"), state);
  renderToolCards(technicalSection("vp-tools"), state);
  renderTimerStatus(technicalSection("vp-timers"), state);
  renderIntegrations(technicalSection("vp-integrations"), state);
  renderNudgeChips(technicalSection("vp-nudges"), state);
}
