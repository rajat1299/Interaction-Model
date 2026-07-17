/**
 * Interaction viewport — plain DOM rendering primitives.
 * Independent of shell navigation so Phase 6 can restyle without changing semantics.
 */

import type { Action } from "./types";
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

  const meta = el("div", "vp-snapshot-meta", host);
  meta.textContent = [
    `activity=${state.activity}`,
    `edit=${state.editKind}`,
    `composing=${state.isComposing}`,
    `sel=${state.selectionStart}-${state.selectionEnd} (utf16)`,
    `t=${state.elapsedMs}ms`,
  ].join(" · ");
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

export function renderViewport(
  root: HTMLElement,
  state: VisibleState,
  oracle: Action | null,
  oracleEvidence: OracleEvidenceOverlay | null = null,
): void {
  root.replaceChildren();
  root.className = "vp-root";

  const section = (cls: string) => el("div", cls, root);

  renderCheckpointMarker(section("vp-checkpoint"), state);
  renderSnapshotSurface(section("vp-snapshot"), state);
  renderActionRow(section("vp-action-row"), {
    executed: state.executedAction,
    attempted: state.rawAttemptedAction,
    license: state.licenseBlockCode,
    oracle,
  });
  renderVisibleContext(section("vp-context"), state, oracleEvidence);
  renderMarkList(section("vp-marks"), state);
  renderToolCards(section("vp-tools"), state);
  renderTimerStatus(section("vp-timers"), state);
  renderIntegrations(section("vp-integrations"), state);
  renderNudgeChips(section("vp-nudges"), state);
}
