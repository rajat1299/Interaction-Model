/**
 * Canonical v1 event and action types for the replay reducer.
 *
 * These mirror spec/schema/event-v1.json and spec/schema/action-v1.json.
 * The reducer is DOM-free and framework-free; it only depends on these types.
 */

export type Activity = "active" | "paused";
export type EditKind = "insert" | "delete" | "replace" | "paste" | "cursor_move" | "none";
export type Disposition = "open" | "handled" | "skipped" | "superseded";
export type ToolResultStatus = "succeeded" | "failed";
export type SkipReason = "stale_tool_result" | "canceled_timer" | "superseded_query";
export type IdleReason =
  | "no_trigger"
  | "typing_active"
  | "awaiting_tool"
  | "awaiting_opening"
  | "instruction_not_direct"
  | "ambiguous"
  | "already_handled";

export type LicenseBlockCode =
  | "malformed_action"
  | "unknown_reference"
  | "span_mismatch"
  | "result_not_ready"
  | "fire_not_open"
  | "timer_not_active"
  | "duplicate_schedule"
  | "duplicate_tool_request"
  | "floor_owned"
  | "target_already_handled"
  | "reason_mismatch"
  | "timer_limit_exceeded"
  | "payload_limit_exceeded"
  | "stale_decision";

export type Span = {
  event_id: string;
  start_utf16: number;
  end_utf16: number;
  text: string;
};

export type LookupArgs = { query: string };

export type MarkAction = { type: "mark"; instruction: Span; target: Span };
export type DelegateAction = { type: "delegate"; fact: Span; tool: "lookup"; args: LookupArgs };
export type IntegrateAction = { type: "integrate"; result_event_id: string; text: string };
export type SkipAction = { type: "skip"; target_event_id: string; reason: SkipReason };
export type RespondAction = { type: "respond"; reply_to_event_id: string; text: string };
export type ScheduleAction = {
  type: "schedule";
  instruction: Span;
  interval_ms: number;
  message: string;
};
export type CancelTimerTarget = { kind: "timer"; timer_id: string };
export type CancelTimersTarget = { kind: "timers"; timer_ids: string[] };
export type CancelAllActiveTarget = { kind: "all_active" };
export type CancelTarget = CancelTimerTarget | CancelTimersTarget | CancelAllActiveTarget;
export type CancelAction = { type: "cancel"; instruction: Span; target: CancelTarget };
export type NudgeAction = { type: "nudge"; fire_event_id: string };
export type IdleAction = {
  type: "idle";
  reason: IdleReason;
  related_event_id: string | null;
};

export type Action =
  | MarkAction
  | DelegateAction
  | IntegrateAction
  | SkipAction
  | RespondAction
  | ScheduleAction
  | CancelAction
  | NudgeAction
  | IdleAction;

export type TimerCapabilities = {
  min_timer_interval_ms: number;
  max_timer_interval_ms: number;
  max_active_timers: number;
  max_timer_message_bytes: number;
};

export type SessionStartPayload = {
  schema_version: 1;
  renderer_id: string;
  canonicalizer_id: string;
  tool_registry_version: number;
  hash_algorithm: "sha256";
  capabilities: TimerCapabilities;
  schema_hash: string;
  spec_hash: string;
  prompt_hash: string;
  config_hash: string;
};

export type SnapshotPayload = {
  text: string;
  selection_start_utf16: number;
  selection_end_utf16: number;
  is_composing: boolean;
  edit_kind: EditKind;
};

export type AnnotationPayload = { text: string };

export type ScheduledPayload = {
  timer_id: string;
  instruction_id: string;
  interval_ms: number;
  message: string;
  first_due_in_ms: number;
};

export type TimerFirePayload = {
  timer_id: string;
  fire_count: number;
  late_ms: number;
  missed_count: number;
};

export type CancelAckPayload = { timer_ids: string[] };

export type ToolRequestedPayload = {
  request_id: string;
  tool: "lookup";
  args: LookupArgs;
};

export type ToolResultPayload = {
  request_id: string;
  status: ToolResultStatus;
  data: unknown;
};

export type ExecutedAction = Exclude<Action, IdleAction>;
export type ActionExecutedPayload = { action: ExecutedAction };
export type ActionRejectedPayload = { reason: LicenseBlockCode };

export type CheckpointSegment = {
  segment_index: number;
  covers_through_policy_seq: number;
  previous_segment_hash: string;
};

export type CheckpointHashes = {
  schema_hash: string;
  spec_hash: string;
  prompt_hash: string;
  config_hash: string;
  renderer_id: string;
  canonicalizer_id: string;
};

export type CheckpointSnapshot = {
  event_id: string;
  activity: Activity;
  text: string;
  selection_start_utf16: number;
  selection_end_utf16: number;
  is_composing: boolean;
  edit_kind: EditKind;
  age_ms: number;
};

export type CheckpointTimer = {
  timer_id: string;
  instruction_id: string;
  instruction_text: string;
  interval_ms: number;
  message: string;
  status: "active" | "canceled";
  next_due_in_ms: number | null;
  fire_count: number;
};

export type CheckpointOpenTimerFire = {
  event_id: string;
  policy_seq: number;
  timer_id: string;
  fire_count: number;
  missed_count: number;
  late_ms: number;
  due_age_ms: number;
  age_ms: number;
};

export type CheckpointOpenToolResult = {
  event_id: string;
  policy_seq: number;
  request_id: string;
  fact_event_id: string;
  fact_text: string;
  tool: "lookup";
  args: LookupArgs;
  status: ToolResultStatus;
  data: unknown;
  age_ms: number;
};

export type CheckpointPendingTool = {
  request_id: string;
  policy_seq: number;
  fact_event_id: string;
  fact_text: string;
  tool: "lookup";
  args: LookupArgs;
  age_ms: number;
};

export type CheckpointAppliedMark = {
  mark_event_id: string;
  instruction_text: string;
  target: Span;
  age_ms: number;
};

export type CheckpointAmbiguousMark = {
  mark_event_id: string;
  instruction_text: string;
  targets: Span[];
  age_ms: number;
};

export type CheckpointDisposition = {
  event_id: string;
  policy_seq: number;
  relation: "event" | "responded_to";
  state: "handled" | "skipped" | "superseded";
};

export type CheckpointSchedulePriorUse = {
  kind: "schedule";
  action_event_id: string;
  policy_seq: number;
  instruction: Span;
  current_span: Span;
  timer_id: string;
  timer_status: "active" | "canceled" | "exhausted" | "failed";
  age_ms: number;
};

export type CheckpointDelegatePriorUse = {
  kind: "delegate";
  action_event_id: string;
  policy_seq: number;
  fact: Span;
  current_span: Span;
  request_id: string;
  tool: "lookup";
  args: LookupArgs;
  result_event_id: string;
  result_status: ToolResultStatus;
  result_disposition: Disposition;
  age_ms: number;
};

export type CheckpointPriorUse = CheckpointSchedulePriorUse | CheckpointDelegatePriorUse;

export type CheckpointRecentEvent = {
  event_id: string;
  rendered: string;
};

export type StateCheckpointPayload = {
  segment: CheckpointSegment;
  capabilities: TimerCapabilities;
  snapshot: CheckpointSnapshot;
  timers: CheckpointTimer[];
  open_timer_fires: CheckpointOpenTimerFire[];
  open_tool_results: CheckpointOpenToolResult[];
  pending_tools: CheckpointPendingTool[];
  prior_uses: CheckpointPriorUse[];
  applied_marks: CheckpointAppliedMark[];
  ambiguous_marks: CheckpointAmbiguousMark[];
  recent_events: CheckpointRecentEvent[];
  dispositions: CheckpointDisposition[];
  hashes: CheckpointHashes;
};

export type CanonicalEvent =
  | { kind: "session_start"; source: "runtime"; payload: SessionStartPayload }
  | { kind: "snapshot"; source: "user"; activity: Activity; payload: SnapshotPayload }
  | { kind: "annotation"; source: "user"; payload: AnnotationPayload }
  | { kind: "scheduled"; source: "runtime"; payload: ScheduledPayload }
  | { kind: "fire"; source: "timer"; payload: TimerFirePayload }
  | { kind: "cancel_ack"; source: "runtime"; payload: CancelAckPayload }
  | { kind: "tool_requested"; source: "runtime"; payload: ToolRequestedPayload }
  | { kind: "result"; source: "tool"; payload: ToolResultPayload }
  | { kind: "action_executed"; source: "model"; payload: ActionExecutedPayload }
  | { kind: "action_rejected"; source: "runtime"; payload: ActionRejectedPayload }
  | { kind: "state_checkpoint"; source: "runtime"; payload: StateCheckpointPayload };

export type CanonicalEventEnvelope = CanonicalEvent & {
  v: 1;
  id: string;
  seq: number;
  dt_ms: number;
};

/** Manifest types for packet loading. */
export type ManifestStream = {
  stream_sha256: string;
  family: string;
  decision_count: number;
  teacher_segment_sha256s: string[];
  sidecar_sha256: string;
  counterfactual: unknown;
  timing: unknown;
  declared_perturbations: string[];
  master_seed: string;
  split: string;
  engine_version: string;
  format_version: number;
  assets: unknown[];
  template: unknown;
  identities: unknown;
  capture_sha256: string;
};

export type Manifest = {
  format_version: number;
  streams: ManifestStream[];
};

export type SourceIndexSource = {
  family: string;
  master_seed: string;
  parent_stream_sha256s: string[];
  raw_source_sha256s: string[];
  role: string;
  shape_id: string;
  sidecar_sha256s: string[];
  source_decision_counts: number[];
  source_kind: string;
  checkpoint: {
    checkpoint_seq: number;
    previous_segment_hash: string;
    segment_index: number;
    segment_sha256: string;
    selected_call_indices: number[];
    stream_sha256: string;
  } | null;
};

export type SourceIndex = {
  batch: number;
  batch_contract: unknown;
  format_version: number;
  source_identity_rule: string;
  sources: SourceIndexSource[];
};

/** Oracle sidecar decision record. */
export type SidecarDecision = {
  action: Action;
  observed_policy_seq: number;
  call_index: number;
  beat_id: string;
  active_timer_ids: string[];
  canceled_timer_ids: string[];
  floor_open: boolean;
  floor_owned: boolean;
  pending_request_ids: string[];
  open_tool_result_event_ids: string[];
  stale_tool_result_event_ids: string[];
  open_timer_fire_event_ids: string[];
  floor_opening_snapshot_event_id?: string;
  floor_opening_snapshot_text?: string;
  cancel_resolution_evidence?: unknown;
};

export type Sidecar = {
  format_version: number;
  family: string;
  stream_sha256: string;
  split: string;
  decisions: SidecarDecision[];
  perturbations: unknown[];
  assets: unknown[];
  template: unknown;
  capture_sha256: string;
  counterfactual: unknown;
  regeneration_identity: string;
  scenario_input_sha256: string;
  world_script_sha256: string;
};

/** Runtime ledger (terminal state) types. */
export type LedgerDisposition = {
  event_id: string;
  by_action_event_id: string | null;
  state: "open" | "handled" | "skipped" | "superseded";
};

export type LedgerResponseDisposition = {
  event_id: string;
  by_action_event_id: string;
  /** Present in schema; teacher-canary rows omit it (presence implies handled). */
  state?: "handled" | "skipped" | "superseded";
};

export type LedgerTimer = {
  timer_id: string;
  instruction_id: string;
  interval_ms: number;
  message: string;
  status: "active" | "canceled";
  fire_count: number;
  next_due_mono_ns: number;
  anchor_mono_ns: number;
  anchor_utc: string;
  idempotency_key: string;
  instruction_event_id: string;
  instruction_start_utf16: number;
  instruction_end_utf16: number;
  instruction_text: string;
};

export type LedgerToolRequest = {
  request_id: string;
  tool: "lookup";
  args: LookupArgs;
  status: "completed" | "pending" | "stale";
  fact_event_id: string;
  result_event_id?: string;
  result_status?: ToolResultStatus;
  result_data?: unknown;
  due_mono_ns: number;
  requested_mono_ns: number;
  canonical_key: string;
};

export type RuntimeLedger = {
  dispositions: LedgerDisposition[];
  response_dispositions: LedgerResponseDisposition[];
  timers: LedgerTimer[];
  tool_requests: LedgerToolRequest[];
};

export type CheckpointSelection = {
  checkpoint_seq: number;
  format_version: number;
  parent_sidecar_sha256: string;
  parent_stream_sha256: string;
  previous_segment_hash: string;
  segment_index: number;
  segment_sha256: string;
  selected_call_indices: number[];
};

/** Loaded packet structures produced by the packet loader. */
export type LoadedSegment = {
  sha256: string;
  events: CanonicalEventEnvelope[];
};

export type LoadedStream = {
  sha256: string;
  family: string;
  decisionCount: number;
  declaredPerturbations: string[];
  split: string;
  counterfactual: unknown;
  segments: LoadedSegment[];
  sidecar: Sidecar;
  runtimeLedger: RuntimeLedger;
  checkpointSelection: CheckpointSelection | null;
};

export type LoadedPacket = {
  manifest: Manifest;
  sourceIndex: SourceIndex;
  streams: LoadedStream[];
  integrity: {
    manifestSha256: string;
    sourceIndexSha256: string;
  };
};
