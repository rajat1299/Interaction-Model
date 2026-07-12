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

/** The five server-to-client render frames accepted by `ServerRenderFrame`. */
export type ServerRenderFrame =
  | NudgeAnnotationFrame
  | MarkRenderFrame
  | RespondTextFrame
  | TimerStatusFrame
  | CheckpointNoticeFrame;
