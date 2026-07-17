/**
 * Pure replay reducer: (canonical events, target) -> deterministic visible state.
 * DOM-free, framework-free. Processes events in seq order.
 */

import type {
  Action,
  Activity,
  CanonicalEventEnvelope,
  EditKind,
  LicenseBlockCode,
  Span,
  StateCheckpointPayload,
} from "./types";
import { projectAppliedMark } from "./mark-projection";

export type AppliedMark = {
  markEventId: string;
  instructionEventId: string;
  instructionStart: number;
  instructionEnd: number;
  instructionText: string;
  targetEventId: string;
  targetStart: number;
  targetEnd: number;
  targetText: string;
};

export type AmbiguousMark = {
  markEventId: string;
  instructionText: string;
  targets: AppliedMark[];
};

export type ToolRequestState = {
  requestId: string;
  tool: "lookup";
  query: string;
  factEventId: string;
  factStart: number;
  factEnd: number;
  factText: string;
  status: "pending" | "completed";
  resultEventId: string | null;
  resultStatus: "succeeded" | "failed" | null;
  resultData: unknown;
};

export type TimerState = {
  timerId: string;
  instructionId: string;
  instructionText: string;
  intervalMs: number;
  message: string;
  status: "active" | "canceled";
  fireCount: number;
  nextDueInMs: number | null;
  scheduleActionEventId: string | null;
  instructionEventId: string | null;
};

export type DispositionEntry = {
  eventId: string;
  state: "open" | "handled" | "skipped" | "superseded";
  byActionEventId: string | null;
  relation: "event" | "responded_to" | null;
};

export type CheckpointInfo = {
  segmentIndex: number;
  coversThroughPolicySeq: number;
  previousSegmentHash: string;
  eventId: string;
};

export type IntegrationEntry = {
  actionEventId: string;
  resultEventId: string;
  text: string;
};

export type ResponseEntry = {
  actionEventId: string;
  replyToEventId: string;
  text: string;
};

export type NudgeEntry = {
  actionEventId: string;
  fireEventId: string;
};

export type VisibleState = {
  text: string;
  selectionStart: number;
  selectionEnd: number;
  isComposing: boolean;
  activity: Activity;
  editKind: EditKind;
  snapshotEventId: string | null;

  elapsedMs: number;

  marks: AppliedMark[];
  ambiguousMarks: AmbiguousMark[];
  toolRequests: ToolRequestState[];
  timers: TimerState[];
  openTimerFireEventIds: string[];
  openToolResultEventIds: string[];
  /**
   * Oracle evidence field — not reconstructed from stream bytes.
   * Always empty here; shell overlays sidecar values at decision points.
   */
  staleToolResultEventIds: string[];
  pendingRequestIds: string[];
  dispositions: DispositionEntry[];

  integrations: IntegrationEntry[];
  responses: ResponseEntry[];
  nudges: NudgeEntry[];

  /**
   * Oracle evidence field — not reconstructed from stream bytes.
   * Always false here; shell overlays sidecar values at decision points.
   */
  floorOpen: boolean;
  floorOwned: boolean;

  checkpoint: CheckpointInfo | null;

  executedAction: Action | null;
  rawAttemptedAction: Action | null;
  licenseBlockCode: LicenseBlockCode | null;

  eventIndex: number;
  eventSeq: number;
  eventKind: string;
  eventId: string;
};

export type StreamReduction = {
  states: VisibleState[];
  /** Event indices of action_executed / action_rejected. */
  decisionEventIndices: number[];
};

const EMPTY_SNAPSHOT = {
  text: "",
  selectionStart: 0,
  selectionEnd: 0,
  isComposing: false,
  activity: "paused" as Activity,
  editKind: "none" as EditKind,
  snapshotEventId: null as string | null,
};

type PendingSchedule = {
  instruction: Span;
  actionEventId: string;
};

type PendingDelegate = {
  fact: Span;
};

function floorOwnedOf(activity: Activity, isComposing: boolean): boolean {
  return activity === "active" || isComposing;
}

function bootstrapFromCheckpoint(
  payload: StateCheckpointPayload,
  eventId: string,
  elapsedMs: number,
  eventIndex: number,
  eventSeq: number,
): VisibleState {
  const timers: TimerState[] = payload.timers.map((t) => ({
    timerId: t.timer_id,
    instructionId: t.instruction_id,
    instructionText: t.instruction_text,
    intervalMs: t.interval_ms,
    message: t.message,
    status: t.status,
    fireCount: t.fire_count,
    nextDueInMs: t.next_due_in_ms,
    scheduleActionEventId: null,
    instructionEventId: null,
  }));

  const toolRequests: ToolRequestState[] = [];
  for (const r of payload.open_tool_results) {
    toolRequests.push({
      requestId: r.request_id,
      tool: r.tool,
      query: r.args.query,
      factEventId: r.fact_event_id,
      factStart: 0,
      factEnd: 0,
      factText: r.fact_text,
      status: "completed",
      resultEventId: r.event_id,
      resultStatus: r.status,
      resultData: r.data,
    });
  }
  for (const p of payload.pending_tools) {
    toolRequests.push({
      requestId: p.request_id,
      tool: p.tool,
      query: p.args.query,
      factEventId: p.fact_event_id,
      factStart: 0,
      factEnd: 0,
      factText: p.fact_text,
      status: "pending",
      resultEventId: null,
      resultStatus: null,
      resultData: null,
    });
  }

  // Checkpoint marks omit instruction span identity; do not invent one.
  const marks: AppliedMark[] = payload.applied_marks.map((m) => ({
    markEventId: m.mark_event_id,
    instructionEventId: "",
    instructionStart: 0,
    instructionEnd: 0,
    instructionText: m.instruction_text,
    targetEventId: m.target.event_id,
    targetStart: m.target.start_utf16,
    targetEnd: m.target.end_utf16,
    targetText: m.target.text,
  }));
  const ambiguousMarks: AmbiguousMark[] = payload.ambiguous_marks.map((ambiguous) => ({
    markEventId: ambiguous.mark_event_id,
    instructionText: ambiguous.instruction_text,
    targets: ambiguous.targets.map((target) => ({
        markEventId: ambiguous.mark_event_id,
        instructionEventId: "",
        instructionStart: 0,
        instructionEnd: 0,
        instructionText: ambiguous.instruction_text,
        targetEventId: target.event_id,
        targetStart: target.start_utf16,
        targetEnd: target.end_utf16,
        targetText: target.text,
      })),
  }));

  const dispositions: DispositionEntry[] = payload.dispositions.map((d) => ({
    eventId: d.event_id,
    state: d.state,
    byActionEventId: null,
    relation: d.relation,
  }));
  // Checkpoint open_* lists are live open dispositions even when dispositions[] is empty.
  for (const r of payload.open_tool_results) {
    if (!dispositions.some((d) => d.eventId === r.event_id)) {
      dispositions.push({
        eventId: r.event_id,
        state: "open",
        byActionEventId: null,
        relation: null,
      });
    }
  }
  for (const f of payload.open_timer_fires) {
    if (!dispositions.some((d) => d.eventId === f.event_id)) {
      dispositions.push({
        eventId: f.event_id,
        state: "open",
        byActionEventId: null,
        relation: null,
      });
    }
  }

  const openToolResultEventIds = payload.open_tool_results.map((r) => r.event_id);
  const activity = payload.snapshot.activity;
  const isComposing = payload.snapshot.is_composing;
  const floorOwned = floorOwnedOf(activity, isComposing);
  const draft: VisibleState = {
    ...EMPTY_SNAPSHOT,
    text: payload.snapshot.text,
    selectionStart: payload.snapshot.selection_start_utf16,
    selectionEnd: payload.snapshot.selection_end_utf16,
    isComposing,
    activity,
    editKind: payload.snapshot.edit_kind,
    snapshotEventId: payload.snapshot.event_id,
    elapsedMs,
    marks,
    ambiguousMarks,
    toolRequests,
    timers,
    openTimerFireEventIds: payload.open_timer_fires.map((f) => f.event_id),
    openToolResultEventIds,
    staleToolResultEventIds: [],
    pendingRequestIds: payload.pending_tools.map((p) => p.request_id),
    dispositions,
    integrations: [],
    responses: [],
    nudges: [],
    floorOpen: false,
    floorOwned,
    checkpoint: {
      segmentIndex: payload.segment.segment_index,
      coversThroughPolicySeq: payload.segment.covers_through_policy_seq,
      previousSegmentHash: payload.segment.previous_segment_hash,
      eventId,
    },
    executedAction: null,
    rawAttemptedAction: null,
    licenseBlockCode: null,
    eventIndex,
    eventSeq,
    eventKind: "state_checkpoint",
    eventId,
  };
  return draft;
}

function emptyState(elapsedMs: number, eventIndex: number, eventSeq: number): VisibleState {
  return {
    ...EMPTY_SNAPSHOT,
    elapsedMs,
    marks: [],
    ambiguousMarks: [],
    toolRequests: [],
    timers: [],
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
    executedAction: null,
    rawAttemptedAction: null,
    licenseBlockCode: null,
    eventIndex,
    eventSeq,
    eventKind: "",
    eventId: "",
  };
}

function validateEventSequence(events: CanonicalEventEnvelope[]): void {
  let prev = -1;
  for (const ev of events) {
    if (typeof ev.seq !== "number" || !Number.isInteger(ev.seq) || ev.seq < 0) {
      throw new Error(`event seq missing/invalid: ${String(ev.seq)}`);
    }
    if (ev.seq === prev) {
      throw new Error(`duplicate event seq ${ev.seq}`);
    }
    if (prev >= 0 && ev.seq !== prev + 1) {
      throw new Error(`non-monotonic event seq: expected ${prev + 1}, got ${ev.seq}`);
    }
    prev = ev.seq;
  }
}

/**
 * Reduce a concatenated canonical stream.
 * Optional targetSeq stops after that event (inclusive); omit for full stream.
 */
export function reduceStream(
  events: CanonicalEventEnvelope[],
  targetSeq?: number,
): StreamReduction {
  validateEventSequence(events);

  const states: VisibleState[] = [];
  const decisionEventIndices: number[] = [];
  let cur = emptyState(0, -1, -1);
  let pendingSchedule: PendingSchedule | null = null;
  let pendingDelegate: PendingDelegate | null = null;

  for (let i = 0; i < events.length; i++) {
    const ev = events[i];
    const applied = applyEvent(cur, ev, i, pendingSchedule, pendingDelegate);
    cur = applied.state;
    pendingSchedule = applied.pendingSchedule;
    pendingDelegate = applied.pendingDelegate;
    states.push(cur);

    if (ev.kind === "action_executed" || ev.kind === "action_rejected") {
      decisionEventIndices.push(i);
    }

    if (targetSeq !== undefined && ev.seq === targetSeq) {
      break;
    }
  }

  return { states, decisionEventIndices };
}

/** Convenience: state after processing through targetSeq (inclusive). */
export function reduceToSeq(
  events: CanonicalEventEnvelope[],
  targetSeq: number,
): VisibleState {
  const { states } = reduceStream(events, targetSeq);
  if (states.length === 0) {
    throw new Error(`no state for target seq ${targetSeq}`);
  }
  return states[states.length - 1];
}

type ApplyResult = {
  state: VisibleState;
  pendingSchedule: PendingSchedule | null;
  pendingDelegate: PendingDelegate | null;
};

function applyEvent(
  prev: VisibleState,
  ev: CanonicalEventEnvelope,
  index: number,
  pendingSchedule: PendingSchedule | null,
  pendingDelegate: PendingDelegate | null,
): ApplyResult {
  const elapsedMs = prev.elapsedMs + ev.dt_ms;

  if (ev.kind === "state_checkpoint") {
    return {
      state: bootstrapFromCheckpoint(ev.payload, ev.id, elapsedMs, index, ev.seq),
      pendingSchedule: null,
      pendingDelegate: null,
    };
  }

  const next: VisibleState = {
    ...prev,
    elapsedMs,
    executedAction: null,
    rawAttemptedAction: null,
    licenseBlockCode: null,
    eventIndex: index,
    eventSeq: ev.seq,
    eventKind: ev.kind,
    eventId: ev.id,
  };

  let nextPendingSchedule = pendingSchedule;
  let nextPendingDelegate = pendingDelegate;

  switch (ev.kind) {
    case "snapshot": {
      const appliedMarks: AppliedMark[] = [];
      const ambiguousMarks: AmbiguousMark[] = [];
      for (const mark of prev.marks) {
        const projection = projectAppliedMark(mark, prev.text, ev.id, ev.payload.text);
        if (projection.applied) appliedMarks.push(projection.applied);
        else if (projection.ambiguous.length > 0) {
          ambiguousMarks.push({
            markEventId: mark.markEventId,
            instructionText: mark.instructionText,
            targets: projection.ambiguous,
          });
        }
      }
      for (const group of prev.ambiguousMarks) {
        const candidates = group.targets.flatMap((target) => {
          const projection = projectAppliedMark(target, prev.text, ev.id, ev.payload.text);
          return projection.applied ? [projection.applied] : projection.ambiguous;
        });
        const unique = new Map(
          candidates.map((target) => [
            `${target.targetEventId}:${target.targetStart}:${target.targetEnd}`,
            target,
          ]),
        );
        if (unique.size > 0) {
          ambiguousMarks.push({ ...group, targets: [...unique.values()] });
        }
      }
      next.marks = appliedMarks;
      next.ambiguousMarks = ambiguousMarks;
      next.text = ev.payload.text;
      next.selectionStart = ev.payload.selection_start_utf16;
      next.selectionEnd = ev.payload.selection_end_utf16;
      next.isComposing = ev.payload.is_composing;
      next.activity = ev.activity;
      next.editKind = ev.payload.edit_kind;
      next.snapshotEventId = ev.id;
      next.floorOwned = floorOwnedOf(ev.activity, ev.payload.is_composing);
      break;
    }
    case "scheduled": {
      const p = ev.payload;
      const link = pendingSchedule;
      next.timers = [
        ...prev.timers.filter((t) => t.timerId !== p.timer_id),
        {
          timerId: p.timer_id,
          instructionId: p.instruction_id,
          instructionText: link?.instruction.text ?? "",
          intervalMs: p.interval_ms,
          message: p.message,
          status: "active",
          fireCount: 0,
          nextDueInMs: p.first_due_in_ms,
          scheduleActionEventId: link?.actionEventId ?? null,
          instructionEventId: link?.instruction.event_id ?? null,
        },
      ];
      nextPendingSchedule = null;
      break;
    }
    case "fire": {
      const p = ev.payload;
      next.timers = prev.timers.map((t) =>
        t.timerId === p.timer_id ? { ...t, fireCount: p.fire_count } : t,
      );
      next.openTimerFireEventIds = [...prev.openTimerFireEventIds, ev.id];
      next.dispositions = upsertDisposition(prev.dispositions, ev.id, "open", null, null);
      break;
    }
    case "cancel_ack": {
      const canceled = new Set(ev.payload.timer_ids);
      next.timers = prev.timers.map((t) =>
        canceled.has(t.timerId) ? { ...t, status: "canceled" as const } : t,
      );
      break;
    }
    case "tool_requested": {
      const p = ev.payload;
      const fact = pendingDelegate?.fact;
      next.toolRequests = [
        ...prev.toolRequests,
        {
          requestId: p.request_id,
          tool: p.tool,
          query: p.args.query,
          factEventId: fact?.event_id ?? "",
          factStart: fact?.start_utf16 ?? 0,
          factEnd: fact?.end_utf16 ?? 0,
          factText: fact?.text ?? "",
          status: "pending",
          resultEventId: null,
          resultStatus: null,
          resultData: null,
        },
      ];
      next.pendingRequestIds = [...prev.pendingRequestIds, p.request_id];
      nextPendingDelegate = null;
      break;
    }
    case "result": {
      const p = ev.payload;
      next.toolRequests = prev.toolRequests.map((r) =>
        r.requestId === p.request_id
          ? {
              ...r,
              status: "completed" as const,
              resultEventId: ev.id,
              resultStatus: p.status,
              resultData: p.data,
            }
          : r,
      );
      next.pendingRequestIds = prev.pendingRequestIds.filter((id) => id !== p.request_id);
      next.openToolResultEventIds = [...prev.openToolResultEventIds, ev.id];
      next.dispositions = upsertDisposition(prev.dispositions, ev.id, "open", null, null);
      break;
    }
    case "action_executed": {
      const action = ev.payload.action;
      next.executedAction = action;
      const effects = applyActionEffects(next, prev, action, ev.id);
      nextPendingSchedule = effects.pendingSchedule ?? nextPendingSchedule;
      nextPendingDelegate = effects.pendingDelegate ?? nextPendingDelegate;
      break;
    }
    case "action_rejected": {
      next.licenseBlockCode = ev.payload.reason;
      break;
    }
    case "session_start":
    case "annotation":
      break;
    default: {
      const _exhaustive: never = ev;
      void _exhaustive;
      break;
    }
  }

  // floorOpen / staleToolResultEventIds stay at stream-default empty; they are
  // LicenseView / oracle evidence, not reconstructible from canonical events alone.
  if (ev.kind !== "snapshot") {
    next.floorOwned = floorOwnedOf(next.activity, next.isComposing);
  }

  return {
    state: next,
    pendingSchedule: nextPendingSchedule,
    pendingDelegate: nextPendingDelegate,
  };
}

function upsertDisposition(
  dispositions: DispositionEntry[],
  eventId: string,
  state: DispositionEntry["state"],
  byActionEventId: string | null,
  relation: DispositionEntry["relation"],
): DispositionEntry[] {
  const existing = dispositions.find((d) => d.eventId === eventId);
  if (existing) {
    return dispositions.map((d) =>
      d.eventId === eventId
        ? {
            ...d,
            state,
            byActionEventId: byActionEventId ?? d.byActionEventId,
            relation: relation ?? d.relation,
          }
        : d,
    );
  }
  return [...dispositions, { eventId, state, byActionEventId, relation }];
}

function applyActionEffects(
  next: VisibleState,
  prev: VisibleState,
  action: Action,
  actionEventId: string,
): { pendingSchedule?: PendingSchedule | null; pendingDelegate?: PendingDelegate | null } {
  switch (action.type) {
    case "mark": {
      next.marks = [
        ...prev.marks,
        {
          markEventId: actionEventId,
          instructionEventId: action.instruction.event_id,
          instructionStart: action.instruction.start_utf16,
          instructionEnd: action.instruction.end_utf16,
          instructionText: action.instruction.text,
          targetEventId: action.target.event_id,
          targetStart: action.target.start_utf16,
          targetEnd: action.target.end_utf16,
          targetText: action.target.text,
        },
      ];
      return {};
    }
    case "delegate": {
      return { pendingDelegate: { fact: action.fact } };
    }
    case "integrate": {
      const resultId = action.result_event_id;
      next.openToolResultEventIds = prev.openToolResultEventIds.filter((id) => id !== resultId);
      next.dispositions = upsertDisposition(
        prev.dispositions,
        resultId,
        "handled",
        actionEventId,
        "responded_to",
      );
      next.integrations = [
        ...prev.integrations,
        { actionEventId, resultEventId: resultId, text: action.text },
      ];
      return {};
    }
    case "nudge": {
      const fireId = action.fire_event_id;
      next.openTimerFireEventIds = prev.openTimerFireEventIds.filter((id) => id !== fireId);
      next.dispositions = upsertDisposition(
        prev.dispositions,
        fireId,
        "handled",
        actionEventId,
        "event",
      );
      next.nudges = [...prev.nudges, { actionEventId, fireEventId: fireId }];
      return {};
    }
    case "skip": {
      const targetId = action.target_event_id;
      next.openTimerFireEventIds = prev.openTimerFireEventIds.filter((id) => id !== targetId);
      next.openToolResultEventIds = prev.openToolResultEventIds.filter((id) => id !== targetId);
      next.staleToolResultEventIds = prev.staleToolResultEventIds.filter((id) => id !== targetId);
      next.dispositions = upsertDisposition(
        prev.dispositions,
        targetId,
        "skipped",
        actionEventId,
        "event",
      );
      return {};
    }
    case "schedule": {
      return {
        pendingSchedule: {
          instruction: action.instruction,
          actionEventId,
        },
      };
    }
    case "cancel": {
      return {};
    }
    case "respond": {
      next.responses = [
        ...prev.responses,
        {
          actionEventId,
          replyToEventId: action.reply_to_event_id,
          text: action.text,
        },
      ];
      next.dispositions = upsertDisposition(
        prev.dispositions,
        action.reply_to_event_id,
        "handled",
        actionEventId,
        "responded_to",
      );
      return {};
    }
    case "idle": {
      return {};
    }
    default: {
      const _exhaustive: never = action;
      void _exhaustive;
      return {};
    }
  }
}
