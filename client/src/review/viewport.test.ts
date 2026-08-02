import { describe, expect, it } from "vitest";
import type { VisibleState } from "./reducer";
import type { CanonicalEventEnvelope } from "./types";
import { actionReferencesFor, buildHighlightedNodes, renderViewport } from "./viewport";

describe("UTF-16 highlighting", () => {
  it("indexes by UTF-16 code units, including astral surrogate pairs", () => {
    // "A" + musical G-clef (U+1D11E, surrogate pair) + "B"
    const text = "A\uD834\uDD1EB";
    expect(text.length).toBe(4); // UTF-16 code units

    // Highlight only the astral character (units 1..3)
    const frag = buildHighlightedNodes(text, [
      { start: 1, end: 3, className: "vp-mark" },
    ]);
    const parts: { type: string; text: string; cls?: string }[] = [];
    frag.childNodes.forEach((n) => {
      if (n.nodeType === Node.TEXT_NODE) {
        parts.push({ type: "text", text: n.textContent ?? "" });
      } else if (n instanceof HTMLElement) {
        parts.push({ type: "span", text: n.textContent ?? "", cls: n.className });
      }
    });
    expect(parts).toEqual([
      { type: "text", text: "A" },
      { type: "span", text: "\uD834\uDD1E", cls: "vp-mark" },
      { type: "text", text: "B" },
    ]);
  });

  it("highlights selection ranges by code unit offsets", () => {
    const text = "hello";
    const frag = buildHighlightedNodes(text, [
      { start: 1, end: 4, className: "vp-selection" },
    ]);
    const html = Array.from(frag.childNodes)
      .map((n) =>
        n instanceof HTMLElement
          ? `<${n.className}>${n.textContent}</>`
          : n.textContent,
      )
      .join("");
    expect(html).toBe("h<vp-selection>ell</>o");
  });

  it("renders the timer story in plain language and keeps raw ids out of the primary view", () => {
    const repeatedText = "Remind me every thirty-seven minutes to open the fern ledger.";
    const events: CanonicalEventEnvelope[] = [
      { v: 1, id: "e_000001", seq: 1, dt_ms: 0, kind: "snapshot", source: "user", activity: "paused", payload: { text: repeatedText, selection_start_utf16: 61, selection_end_utf16: 61, is_composing: false, edit_kind: "insert" } },
      { v: 1, id: "e_000002", seq: 2, dt_ms: 0, kind: "scheduled", source: "runtime", payload: { timer_id: "t_002", instruction_id: "e_000001", interval_ms: 2_220_000, message: "open the fern ledger for the desk note", first_due_in_ms: 2_220_000 } },
      { v: 1, id: "e_000003", seq: 3, dt_ms: 0, kind: "snapshot", source: "user", activity: "paused", payload: { text: repeatedText, selection_start_utf16: 61, selection_end_utf16: 61, is_composing: false, edit_kind: "none" } },
      { v: 1, id: "e_000016", seq: 4, dt_ms: 2_220_000, kind: "fire", source: "timer", payload: { timer_id: "t_002", fire_count: 1, late_ms: 0, missed_count: 0 } },
      { v: 1, id: "e_000017", seq: 5, dt_ms: 580, kind: "action_executed", source: "model", payload: { action: { type: "nudge", fire_event_id: "e_000016" } } },
    ];
    const state: VisibleState = {
      text: repeatedText,
      selectionStart: 61,
      selectionEnd: 61,
      isComposing: false,
      activity: "paused",
      editKind: "none",
      snapshotEventId: "e_000003",
      elapsedMs: 2_220_580,
      marks: [],
      ambiguousMarks: [],
      toolRequests: [],
      timers: [{ timerId: "t_002", instructionId: "e_000001", instructionText: repeatedText, intervalMs: 2_220_000, message: "open the fern ledger for the desk note", status: "active", fireCount: 1, nextDueInMs: 2_220_000, scheduleActionEventId: null, instructionEventId: "e_000001" }],
      openTimerFireEventIds: [],
      openToolResultEventIds: [],
      staleToolResultEventIds: [],
      pendingRequestIds: [],
      dispositions: [],
      integrations: [],
      responses: [],
      nudges: [],
      floorOpen: false,
      floorOwned: false,
      checkpoint: null,
      executedAction: { type: "nudge", fire_event_id: "e_000016" },
      rawAttemptedAction: null,
      licenseBlockCode: null,
      eventIndex: 4,
      eventSeq: 5,
      eventKind: "action_executed",
      eventId: "e_000017",
    };
    const root = document.createElement("div");

    renderViewport(root, state, null, {
      floorOpen: false,
      staleToolResultEventIds: [],
      openTimerFireEventIds: ["e_000016"],
    }, events);

    const primary = [".vp-attention", ".vp-timeline", ".vp-visible-text", ".vp-facts"]
      .map((selector) => root.querySelector(selector)?.textContent ?? "")
      .join(" ");
    expect(root.querySelector(".vp-attention")?.textContent).toContain("open the fern ledger for the desk note");
    expect(root.querySelector(".vp-attention")?.textContent).toContain("580 ms ago");
    expect(primary).not.toMatch(/\b[et]_\d+/);
    expect(root.querySelectorAll(".vp-timeline-list li")).toHaveLength(3);
    expect(root.querySelector(".vp-timeline")?.textContent?.match(/User wrote:/g)).toHaveLength(1);
    expect(root.querySelector(".vp-visible-text")?.textContent).toContain("Still visible in the editor");
    expect(root.querySelector(".vp-technical")?.textContent).toContain("e_000016");

    expect(actionReferencesFor(events, 4).fireMessages.get("e_000016")).toBe(
      "open the fern ledger for the desk note",
    );
    renderViewport(root, state, null, {
      floorOpen: false,
      staleToolResultEventIds: [],
      openTimerFireEventIds: [],
    }, events);
    expect(root.querySelector(".vp-attention")?.textContent).toContain("Review the proposed action");
    expect(root.querySelector(".vp-attention")?.textContent).not.toContain("waiting is correct");
  });
});
