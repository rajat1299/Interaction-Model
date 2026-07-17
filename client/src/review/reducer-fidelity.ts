/**
 * Canary subset fidelity: compare stream-derivable state against the oracle
 * sidecar, checkpoint payload, and runtime ledger. Powers the shell warning;
 * it is not the independent golden-trace evidence required to establish G-6.
 */

import { reduceStream, type StreamReduction, type VisibleState } from "./reducer";
import { concatStreamEvents } from "./packet-loader";
import type {
  CanonicalEventEnvelope,
  LoadedStream,
  Sidecar,
  StateCheckpointPayload,
} from "./types";

export type Divergence = {
  streamSha256: string;
  location: string;
  field: string;
  expected: string;
  actual: string;
};

export type StreamFidelity = {
  streamSha256: string;
  divergences: Divergence[];
  decisionComparisons: number;
  checkpointComparisons: number;
  ledgerCompared: boolean;
  /** Fields that cannot be proven from stream bytes alone. */
  unavailableFields: string[];
};

function sortStr(a: string[]): string[] {
  return [...a].sort();
}

/** Stable stringify so action key order does not create false mismatches. */
function canon(value: unknown): string {
  if (value === null || typeof value !== "object") {
    return JSON.stringify(value);
  }
  if (Array.isArray(value)) {
    return `[${value.map((v) => canon(v)).join(",")}]`;
  }
  const obj = value as Record<string, unknown>;
  const keys = Object.keys(obj).sort();
  return `{${keys.map((k) => `${JSON.stringify(k)}:${canon(obj[k])}`).join(",")}}`;
}

function compareField(
  out: Divergence[],
  streamSha: string,
  location: string,
  field: string,
  expected: unknown,
  actual: unknown,
): void {
  const e = canon(expected);
  const a = canon(actual);
  if (e !== a) {
    out.push({ streamSha256: streamSha, location, field, expected: e, actual: a });
  }
}

/**
 * Map each sidecar decision to the event index of its observed_policy_seq
 * (decision-time ingress). For non-idle actions, also locate the following
 * action_executed used for oracle action association.
 */
export function mapDecisionsToEvents(
  events: CanonicalEventEnvelope[],
  sidecar: Sidecar,
): {
  eventIndex: number;
  actionEventIndex: number | null;
  actionEventCount: number;
  isIdle: boolean;
  decisionIdx: number;
}[] {
  const seqToIndex = new Map<number, number>();
  for (let i = 0; i < events.length; i++) {
    seqToIndex.set(events[i].seq, i);
  }

  const result: {
    eventIndex: number;
    actionEventIndex: number | null;
    actionEventCount: number;
    isIdle: boolean;
    decisionIdx: number;
  }[] = [];

  for (let d = 0; d < sidecar.decisions.length; d++) {
    const dec = sidecar.decisions[d];
    const ingressIdx = seqToIndex.get(dec.observed_policy_seq);
    if (ingressIdx === undefined) {
      result.push({
        eventIndex: -1,
        actionEventIndex: null,
        actionEventCount: 0,
        isIdle: dec.action.type === "idle",
        decisionIdx: d,
      });
      continue;
    }

    const isIdle = dec.action.type === "idle";
    let actionEventIndex: number | null = null;
    let actionEventCount = 0;
    const nextSeq = sidecar.decisions[d + 1]?.observed_policy_seq;
    const nextIngress = nextSeq === undefined ? events.length - 1 : seqToIndex.get(nextSeq);
    const inclusiveEnd = nextIngress ?? events.length - 1;
    for (let i = ingressIdx + 1; i <= inclusiveEnd; i++) {
      if (events[i].kind === "action_executed") {
        actionEventCount++;
        if (actionEventIndex === null) actionEventIndex = i;
      }
    }
    result.push({
      eventIndex: ingressIdx,
      actionEventIndex: actionEventCount === 1 ? actionEventIndex : null,
      actionEventCount,
      isIdle,
      decisionIdx: d,
    });
  }
  return result;
}

function compareMarkValidity(
  divergences: Divergence[],
  streamSha: string,
  location: string,
  state: VisibleState,
): void {
  const targets = [
    ...state.marks,
    ...state.ambiguousMarks.flatMap((group) => group.targets),
  ];
  for (const mark of targets) {
    const actual = state.text.slice(mark.targetStart, mark.targetEnd);
    if (actual !== mark.targetText) {
      divergences.push({
        streamSha256: streamSha,
        location,
        field: `mark.${mark.markEventId}.target`,
        expected: JSON.stringify(mark.targetText),
        actual: JSON.stringify(actual),
      });
    }
    if (state.snapshotEventId !== null && mark.targetEventId !== state.snapshotEventId) {
      divergences.push({
        streamSha256: streamSha,
        location,
        field: `mark.${mark.markEventId}.snapshot_event_id`,
        expected: JSON.stringify(state.snapshotEventId),
        actual: JSON.stringify(mark.targetEventId),
      });
    }
  }
}

function compareDecisionState(
  divergences: Divergence[],
  streamSha: string,
  loc: string,
  state: VisibleState,
  dec: Sidecar["decisions"][number],
): void {
  const actualActive = sortStr(
    state.timers.filter((t) => t.status === "active").map((t) => t.timerId),
  );
  compareField(
    divergences,
    streamSha,
    loc,
    "active_timer_ids",
    sortStr(dec.active_timer_ids),
    actualActive,
  );

  const actualCanceled = sortStr(
    state.timers.filter((t) => t.status === "canceled").map((t) => t.timerId),
  );
  compareField(
    divergences,
    streamSha,
    loc,
    "canceled_timer_ids",
    sortStr(dec.canceled_timer_ids),
    actualCanceled,
  );

  const actualPending = sortStr(
    state.toolRequests.filter((r) => r.status === "pending").map((r) => r.requestId),
  );
  compareField(
    divergences,
    streamSha,
    loc,
    "pending_request_ids",
    sortStr(dec.pending_request_ids),
    actualPending,
  );

  compareField(
    divergences,
    streamSha,
    loc,
    "open_tool_result_event_ids",
    sortStr(dec.open_tool_result_event_ids),
    sortStr(state.openToolResultEventIds),
  );

  compareField(
    divergences,
    streamSha,
    loc,
    "open_timer_fire_event_ids",
    sortStr(dec.open_timer_fire_event_ids),
    sortStr(state.openTimerFireEventIds),
  );

  // floor_open and stale_tool_result_event_ids are LicenseView / oracle evidence.
  // They are not compared here; see unavailableFields in checkStreamFidelity.
  compareField(divergences, streamSha, loc, "floor_owned", dec.floor_owned, state.floorOwned);

  compareField(
    divergences,
    streamSha,
    loc,
    "observed_policy_seq",
    dec.observed_policy_seq,
    state.eventSeq,
  );
}

export function checkStreamFidelity(
  stream: LoadedStream,
  preexisting?: StreamReduction,
): StreamFidelity {
  const allEvents = concatStreamEvents(stream);
  const reduction = preexisting ?? reduceStream(allEvents);
  const divergences: Divergence[] = [];
  const unavailableFields: string[] = [];

  // Raw attempted actions and license block codes appear only on action_rejected.
  // teacher-canary has none — shell shows "not present in packet".
  const hasRejected = allEvents.some((e) => e.kind === "action_rejected");
  if (!hasRejected) {
    unavailableFields.push("raw_attempted_action");
    unavailableFields.push("license_block_code");
  }
  // Oracle evidence not reconstructible from canonical stream bytes alone.
  // Shell overlays sidecar values at decision points for display.
  unavailableFields.push("floor_open");
  unavailableFields.push("stale_tool_result_event_ids");

  const decisionMap = mapDecisionsToEvents(allEvents, stream.sidecar);
  let decisionComparisons = 0;

  for (const dm of decisionMap) {
    if (dm.eventIndex < 0) {
      divergences.push({
        streamSha256: stream.sha256,
        location: `decision ${dm.decisionIdx}`,
        field: "event_mapping",
        expected: "valid event index",
        actual: "-1",
      });
      continue;
    }
    const state = reduction.states[dm.eventIndex];
    const dec = stream.sidecar.decisions[dm.decisionIdx];
    decisionComparisons++;
    const loc = `decision ${dm.decisionIdx} (policy_seq ${dec.observed_policy_seq})`;

    compareDecisionState(divergences, stream.sha256, loc, state, dec);
    compareMarkValidity(divergences, stream.sha256, loc, state);

    if (dm.isIdle) {
      if (dm.actionEventCount !== 0) {
        divergences.push({
          streamSha256: stream.sha256,
          location: loc,
          field: "oracle_action",
          expected: "no action_executed for idle",
          actual: `${dm.actionEventCount} action_executed event(s) in decision interval`,
        });
      }
    } else {
      if (dm.actionEventIndex === null) {
        divergences.push({
          streamSha256: stream.sha256,
          location: loc,
          field: "oracle_action",
          expected: JSON.stringify(dec.action),
          actual: `${dm.actionEventCount} action_executed event(s) in decision interval`,
        });
      } else {
        const actionState = reduction.states[dm.actionEventIndex];
        compareField(
          divergences,
          stream.sha256,
          loc,
          "oracle_action",
          dec.action,
          actionState.executedAction,
        );
      }
    }
  }

  let checkpointComparisons = 0;
  for (let i = 0; i < allEvents.length; i++) {
    if (allEvents[i].kind !== "state_checkpoint") continue;
    checkpointComparisons++;
    const cp = allEvents[i].payload as StateCheckpointPayload;
    const state = reduction.states[i];
    const loc = `checkpoint segment ${cp.segment.segment_index}`;

    compareField(divergences, stream.sha256, loc, "snapshot.text", cp.snapshot.text, state.text);
    compareField(
      divergences,
      stream.sha256,
      loc,
      "snapshot.selection_start",
      cp.snapshot.selection_start_utf16,
      state.selectionStart,
    );
    compareField(
      divergences,
      stream.sha256,
      loc,
      "snapshot.selection_end",
      cp.snapshot.selection_end_utf16,
      state.selectionEnd,
    );
    compareField(
      divergences,
      stream.sha256,
      loc,
      "snapshot.is_composing",
      cp.snapshot.is_composing,
      state.isComposing,
    );
    compareField(
      divergences,
      stream.sha256,
      loc,
      "snapshot.activity",
      cp.snapshot.activity,
      state.activity,
    );
    compareField(
      divergences,
      stream.sha256,
      loc,
      "snapshot.edit_kind",
      cp.snapshot.edit_kind,
      state.editKind,
    );

    compareField(
      divergences,
      stream.sha256,
      loc,
      "timers.ids",
      sortStr(cp.timers.map((t) => t.timer_id)),
      sortStr(state.timers.map((t) => t.timerId)),
    );

    for (const cpT of cp.timers) {
      const actual = state.timers.find((t) => t.timerId === cpT.timer_id);
      if (!actual) continue;
      compareField(
        divergences,
        stream.sha256,
        loc,
        `timer.${cpT.timer_id}.status`,
        cpT.status,
        actual.status,
      );
      compareField(
        divergences,
        stream.sha256,
        loc,
        `timer.${cpT.timer_id}.fire_count`,
        cpT.fire_count,
        actual.fireCount,
      );
      compareField(
        divergences,
        stream.sha256,
        loc,
        `timer.${cpT.timer_id}.interval_ms`,
        cpT.interval_ms,
        actual.intervalMs,
      );
      compareField(
        divergences,
        stream.sha256,
        loc,
        `timer.${cpT.timer_id}.message`,
        cpT.message,
        actual.message,
      );
    }

    compareField(
      divergences,
      stream.sha256,
      loc,
      "open_timer_fires",
      sortStr(cp.open_timer_fires.map((f) => f.event_id)),
      sortStr(state.openTimerFireEventIds),
    );
    compareField(
      divergences,
      stream.sha256,
      loc,
      "open_tool_results",
      sortStr(cp.open_tool_results.map((r) => r.event_id)),
      sortStr(state.openToolResultEventIds),
    );
    compareField(
      divergences,
      stream.sha256,
      loc,
      "pending_tools",
      sortStr(cp.pending_tools.map((p) => p.request_id)),
      sortStr(state.pendingRequestIds),
    );

    const cpDispositions = sortStr(cp.dispositions.map((d) => `${d.event_id}:${d.state}`));
    const actualDispositions = sortStr(
      state.dispositions
        .filter((d) => d.state !== "open")
        .map((d) => `${d.eventId}:${d.state}`),
    );
    compareField(divergences, stream.sha256, loc, "dispositions", cpDispositions, actualDispositions);

    const checkpointMarks = sortStr(
      cp.applied_marks.map(
        (mark) =>
          `${mark.mark_event_id}:${mark.target.event_id}:${mark.target.start_utf16}:${mark.target.end_utf16}:${mark.target.text}`,
      ),
    );
    const actualMarks = sortStr(
      state.marks.map(
        (mark) =>
          `${mark.markEventId}:${mark.targetEventId}:${mark.targetStart}:${mark.targetEnd}:${mark.targetText}`,
      ),
    );
    compareField(divergences, stream.sha256, loc, "applied_marks", checkpointMarks, actualMarks);
    const checkpointAmbiguousMarks = sortStr(
      cp.ambiguous_marks.map(
        (mark) =>
          `${mark.mark_event_id}:[${mark.targets
            .map(
              (target) =>
                `${target.event_id}:${target.start_utf16}:${target.end_utf16}:${target.text}`,
            )
            .sort()
            .join("|")}]`,
      ),
    );
    const actualAmbiguousMarks = sortStr(
      state.ambiguousMarks.map(
        (mark) =>
          `${mark.markEventId}:[${mark.targets
            .map(
              (target) =>
                `${target.targetEventId}:${target.targetStart}:${target.targetEnd}:${target.targetText}`,
            )
            .sort()
            .join("|")}]`,
      ),
    );
    compareField(
      divergences,
      stream.sha256,
      loc,
      "ambiguous_marks",
      checkpointAmbiguousMarks,
      actualAmbiguousMarks,
    );
    compareMarkValidity(divergences, stream.sha256, loc, state);
  }

  const terminal = reduction.states[reduction.states.length - 1];
  const ledger = stream.runtimeLedger;
  let ledgerCompared = false;
  if (ledger && terminal) {
    ledgerCompared = true;
    const loc = "stream_end";

    compareField(
      divergences,
      stream.sha256,
      loc,
      "ledger.timers.ids",
      sortStr(ledger.timers.map((t) => t.timer_id)),
      sortStr(terminal.timers.map((t) => t.timerId)),
    );

    for (const lt of ledger.timers) {
      const actual = terminal.timers.find((t) => t.timerId === lt.timer_id);
      if (!actual) continue;
      compareField(
        divergences,
        stream.sha256,
        loc,
        `ledger.timer.${lt.timer_id}.status`,
        lt.status,
        actual.status,
      );
      compareField(
        divergences,
        stream.sha256,
        loc,
        `ledger.timer.${lt.timer_id}.fire_count`,
        lt.fire_count,
        actual.fireCount,
      );
    }

    // Tool requests: only compare IDs and stream-derivable pending/completed.
    // Ledger may carry world-side result_status before a result event is committed.
    compareField(
      divergences,
      stream.sha256,
      loc,
      "ledger.tool_requests.ids",
      sortStr(ledger.tool_requests.map((r) => r.request_id)),
      sortStr(terminal.toolRequests.map((r) => r.requestId)),
    );

    for (const lr of ledger.tool_requests) {
      const actual = terminal.toolRequests.find((r) => r.requestId === lr.request_id);
      if (!actual) continue;
      const derivableStatus =
        lr.result_event_id != null
          ? "completed"
          : lr.status === "pending"
            ? "pending"
            : lr.status;
      if (derivableStatus === "pending" || derivableStatus === "completed") {
        compareField(
          divergences,
          stream.sha256,
          loc,
          `ledger.tool_request.${lr.request_id}.status`,
          derivableStatus,
          actual.status,
        );
      }
      if (lr.result_event_id != null && lr.result_status) {
        compareField(
          divergences,
          stream.sha256,
          loc,
          `ledger.tool_request.${lr.request_id}.result_status`,
          lr.result_status,
          actual.resultStatus,
        );
      }
    }

    // Event dispositions + response dispositions. Canary response rows omit
    // `state`; presence in response_dispositions implies handled.
    const ledgerDisp = sortStr([
      ...ledger.dispositions.map((d) => `${d.event_id}:${d.state}`),
      ...ledger.response_dispositions.map(
        (d) => `${d.event_id}:${d.state ?? "handled"}`,
      ),
    ]);
    const actualDisp = sortStr(
      terminal.dispositions.map((d) => `${d.eventId}:${d.state}`),
    );
    compareField(divergences, stream.sha256, loc, "ledger.dispositions", ledgerDisp, actualDisp);
    compareMarkValidity(divergences, stream.sha256, loc, terminal);
  }

  return {
    streamSha256: stream.sha256,
    divergences,
    decisionComparisons,
    checkpointComparisons,
    ledgerCompared,
    unavailableFields,
  };
}

export function reduceLoadedStream(stream: LoadedStream): StreamReduction {
  return reduceStream(concatStreamEvents(stream));
}
