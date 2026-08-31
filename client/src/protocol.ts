/** Closed WebSocket protocol shared by the browser sampler and harness. */

export type Activity = "active" | "paused";

/** The v1 client-to-server raw sampler frame (`ClientSnapshotFrame` on the server). */
export type ClientSnapshotFrame = {
  text: string;
  selection_start: number;
  selection_end: number;
  is_composing: boolean;
  input_type: string | null;
  activity: Activity;
  client_ts: number;
};

export type Span = {
  event_id: string;
  start_utf16: number;
  end_utf16: number;
  text: string;
};

export type NudgeAnnotationFrame = {
  type: "nudge_annotation";
  action_event_id: string;
  fire_event_id: string;
  timer_id: string;
  message: string;
  fire_count: number;
  missed_count: number;
};

export type MarkRenderFrame = {
  type: "mark_render";
  action_event_id: string;
  instruction: Span;
  target: Span;
};

export type RespondTextFrame = {
  type: "respond_text";
  action_event_id: string;
  reply_to_event_id: string;
  text: string;
};

export type TimerStatusFrame = {
  type: "timer_status";
  timer_id: string;
  instruction_id: string;
  interval_ms: number;
  message: string;
  status: "active" | "canceled";
  next_due_in_ms: number | null;
  fire_count: number;
};

export type CheckpointNoticeFrame = {
  type: "checkpoint_notice";
  checkpoint_event_id: string;
  segment_index: number;
  covers_through_policy_seq: number;
};

export type HeldContextFrame = {
  type: "held_context";
  result_event_id: string;
  text: string;
  query: string;
  source: "tool";
};

export type PolicyIntentType =
  | "idle"
  | "mark"
  | "delegate"
  | "integrate"
  | "skip"
  | "respond"
  | "schedule"
  | "cancel"
  | "nudge";

export type JsonValue = string | number | boolean | null | JsonValue[] | { [key: string]: JsonValue };

export type ParsedPolicyIntent = {
  type: PolicyIntentType;
  [key: string]: JsonValue;
};

export type ExactBytes = { encoding: "utf8" | "hex"; data: string };

/** One terminal, durable record of a model decision. */
export type DecisionTraceV1 = {
  version: "decision_trace_v1";
  decision_id: string;
  observed_through_policy_seq: number | null;
  final_policy_seq: number | null;
  audit_sha256: string;
  operator_mode: "fixed_sandbox";
  raw_provider_output: ExactBytes;
  raw_provider_output_sha256: string;
  parser_input: ExactBytes | null;
  parser_input_sha256: string | null;
  parser_input_binding: string;
  parsed_raw_intent: ParsedPolicyIntent | null;
  frozen_policy_sha256: string;
  frozen_license_view_sha256: string;
  frozen_registry_sha256: string;
  resolution: JsonValue;
  initial_license: JsonValue;
  pending_license: JsonValue;
  fresh_license: JsonValue;
  executed_event: JsonValue;
  effect: JsonValue;
  latency_ms: number;
};

export type DecisionTraceFrame = {
  type: "decision_trace";
  trace: DecisionTraceV1;
};

export type SnapshotProjectionFrame = {
  type: "snapshot_projection";
  event_id: string;
  text: string;
  client_ts: number | null;
};

/** The server-to-client document projections accepted by the browser. */
export type ServerRenderFrame =
  | NudgeAnnotationFrame
  | MarkRenderFrame
  | RespondTextFrame
  | TimerStatusFrame
  | CheckpointNoticeFrame
  | HeldContextFrame;

export type FilmLiveFrame = ServerRenderFrame | DecisionTraceFrame;

export type FilmReplayEvent = ServerRenderFrame | DecisionTraceFrame | SnapshotProjectionFrame;

export type FilmReplay = {
  session_id: string;
  events: FilmReplayEvent[];
};
