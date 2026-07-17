import { describe, expect, it } from "vitest";
import {
  actionsAreCausallyEquivalent,
  lookupTeacherLabel,
  parseTeacherLabels,
} from "./teacher-labels";
import type { Action } from "./types";

const STREAM = `sha256:${"a".repeat(64)}`;

function line(action: Action): string {
  return JSON.stringify({
    stream_sha256: STREAM,
    decision_policy_seq: 7,
    action,
    label: "completed",
  });
}

describe("teacher label decision identity", () => {
  it("finds a label even when the teacher action type disagrees", () => {
    const teacher: Action = { type: "idle", reason: "no_trigger", related_event_id: null };
    const parsed = parseTeacherLabels(line(teacher));
    expect(parsed.ok).toBe(true);
    if (!parsed.ok) return;
    expect(lookupTeacherLabel(parsed.labels, STREAM, 7)?.action).toEqual(teacher);
  });

  it("rejects duplicate labels for the same decision regardless of action type", () => {
    const idle: Action = { type: "idle", reason: "no_trigger", related_event_id: null };
    const nudge: Action = { type: "nudge", fire_event_id: "e_000001" };
    const parsed = parseTeacherLabels(`${line(idle)}\n${line(nudge)}`);
    expect(parsed.ok).toBe(false);
    if (parsed.ok) return;
    expect(parsed.errors).toEqual([expect.stringContaining("duplicate label")]);
  });
});

describe("D2 causal action equivalence", () => {
  it("accepts alternative faithful integrate/respond wording", () => {
    expect(
      actionsAreCausallyEquivalent(
        { type: "integrate", result_event_id: "e_1", text: "One wording" },
        { type: "integrate", result_event_id: "e_1", text: "Another wording" },
      ),
    ).toBe(true);
    expect(
      actionsAreCausallyEquivalent(
        { type: "respond", reply_to_event_id: "e_2", text: "One wording" },
        { type: "respond", reply_to_event_id: "e_2", text: "Another wording" },
      ),
    ).toBe(true);
  });

  it("rejects action-type, causal-reference, idle-reason, and state-payload changes", () => {
    expect(
      actionsAreCausallyEquivalent(
        { type: "idle", reason: "no_trigger", related_event_id: null },
        { type: "nudge", fire_event_id: "e_1" },
      ),
    ).toBe(false);
    expect(
      actionsAreCausallyEquivalent(
        { type: "integrate", result_event_id: "e_1", text: "x" },
        { type: "integrate", result_event_id: "e_2", text: "x" },
      ),
    ).toBe(false);
    expect(
      actionsAreCausallyEquivalent(
        { type: "idle", reason: "typing_active", related_event_id: "e_1" },
        { type: "idle", reason: "no_trigger", related_event_id: "e_1" },
      ),
    ).toBe(false);
    expect(
      actionsAreCausallyEquivalent(
        {
          type: "schedule",
          instruction: { event_id: "e_1", start_utf16: 0, end_utf16: 4, text: "ping" },
          interval_ms: 1_000,
          message: "ping",
        },
        {
          type: "schedule",
          instruction: { event_id: "e_1", start_utf16: 0, end_utf16: 4, text: "ping" },
          interval_ms: 2_000,
          message: "ping",
        },
      ),
    ).toBe(false);
  });
});
