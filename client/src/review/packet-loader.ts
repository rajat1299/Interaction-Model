/**
 * Local packet loader: parse, verify SHA256SUMS, validate paths.
 * DOM-free core (path->text entries) plus a thin browser wrapper.
 */

import type {
  CanonicalEventEnvelope,
  CheckpointSelection,
  LoadedPacket,
  LoadedSegment,
  LoadedStream,
  Manifest,
  RuntimeLedger,
  Sidecar,
  SourceIndex,
} from "./types";

export type PacketLoadResult =
  | { ok: true; packet: LoadedPacket }
  | { ok: false; errors: string[] };

export type PacketEntry = { path: string; text: string };

const HASH_RE = /^[0-9a-f]{64}$/;
const EVENT_KINDS = new Set([
  "session_start",
  "snapshot",
  "annotation",
  "scheduled",
  "fire",
  "cancel_ack",
  "tool_requested",
  "result",
  "action_executed",
  "action_rejected",
  "state_checkpoint",
]);
const ACTION_TYPES = new Set([
  "mark",
  "delegate",
  "integrate",
  "skip",
  "respond",
  "schedule",
  "cancel",
  "nudge",
  "idle",
]);

type JsonRecord = Record<string, unknown>;

function problem(e: unknown): string {
  return e instanceof Error ? e.message : String(e);
}

function record(value: unknown, label: string): JsonRecord {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new Error(`${label} must be an object`);
  }
  return value as JsonRecord;
}

function string(value: unknown, label: string): string {
  if (typeof value !== "string") throw new Error(`${label} must be a string`);
  return value;
}

function integer(value: unknown, label: string, min = 0): number {
  if (!Number.isInteger(value) || (value as number) < min) {
    throw new Error(`${label} must be an integer >= ${min}`);
  }
  return value as number;
}

function number(value: unknown, label: string, min = 0): number {
  if (typeof value !== "number" || !Number.isFinite(value) || value < min) {
    throw new Error(`${label} must be a finite number >= ${min}`);
  }
  return value;
}

function bool(value: unknown, label: string): boolean {
  if (typeof value !== "boolean") throw new Error(`${label} must be a boolean`);
  return value;
}

function list(value: unknown, label: string): unknown[] {
  if (!Array.isArray(value)) throw new Error(`${label} must be an array`);
  return value;
}

function stringList(value: unknown, label: string): string[] {
  return list(value, label).map((item, i) => string(item, `${label}[${i}]`));
}

function hash(value: unknown, label: string): string {
  const valueString = string(value, label);
  if (!HASH_RE.test(stripSha(valueString))) throw new Error(`${label} must be a SHA-256`);
  return valueString;
}

function oneOf(value: unknown, label: string, values: Set<string>): string {
  const valueString = string(value, label);
  if (!values.has(valueString)) throw new Error(`${label} is invalid: ${valueString}`);
  return valueString;
}

function span(value: unknown, label: string): void {
  const item = record(value, label);
  string(item.event_id, `${label}.event_id`);
  integer(item.start_utf16, `${label}.start_utf16`);
  integer(item.end_utf16, `${label}.end_utf16`);
  string(item.text, `${label}.text`);
}

function action(value: unknown, label: string): void {
  const item = record(value, label);
  const type = oneOf(item.type, `${label}.type`, ACTION_TYPES);
  switch (type) {
    case "mark":
      span(item.instruction, `${label}.instruction`);
      span(item.target, `${label}.target`);
      return;
    case "delegate": {
      span(item.fact, `${label}.fact`);
      if (item.tool !== "lookup") throw new Error(`${label}.tool must be lookup`);
      string(record(item.args, `${label}.args`).query, `${label}.args.query`);
      return;
    }
    case "integrate":
      string(item.result_event_id, `${label}.result_event_id`);
      string(item.text, `${label}.text`);
      return;
    case "skip":
      string(item.target_event_id, `${label}.target_event_id`);
      oneOf(item.reason, `${label}.reason`, new Set(["stale_tool_result", "canceled_timer", "superseded_query"]));
      return;
    case "respond":
      string(item.reply_to_event_id, `${label}.reply_to_event_id`);
      string(item.text, `${label}.text`);
      return;
    case "schedule":
      span(item.instruction, `${label}.instruction`);
      integer(item.interval_ms, `${label}.interval_ms`, 1);
      string(item.message, `${label}.message`);
      return;
    case "cancel": {
      span(item.instruction, `${label}.instruction`);
      const target = record(item.target, `${label}.target`);
      const kind = oneOf(target.kind, `${label}.target.kind`, new Set(["timer", "timers", "all_active"]));
      if (kind === "timer") string(target.timer_id, `${label}.target.timer_id`);
      if (kind === "timers") stringList(target.timer_ids, `${label}.target.timer_ids`);
      return;
    }
    case "nudge":
      string(item.fire_event_id, `${label}.fire_event_id`);
      return;
    case "idle":
      oneOf(item.reason, `${label}.reason`, new Set([
        "no_trigger",
        "typing_active",
        "awaiting_tool",
        "awaiting_opening",
        "instruction_not_direct",
        "ambiguous",
        "already_handled",
      ]));
      if (item.related_event_id !== null) string(item.related_event_id, `${label}.related_event_id`);
      return;
  }
}

function checkpointPayload(value: unknown, label: string): void {
  const payload = record(value, label);
  const segment = record(payload.segment, `${label}.segment`);
  integer(segment.segment_index, `${label}.segment.segment_index`);
  integer(segment.covers_through_policy_seq, `${label}.segment.covers_through_policy_seq`);
  hash(segment.previous_segment_hash, `${label}.segment.previous_segment_hash`);

  const capabilities = record(payload.capabilities, `${label}.capabilities`);
  for (const key of ["min_timer_interval_ms", "max_timer_interval_ms", "max_active_timers", "max_timer_message_bytes"]) {
    integer(capabilities[key], `${label}.capabilities.${key}`);
  }

  const snapshot = record(payload.snapshot, `${label}.snapshot`);
  string(snapshot.event_id, `${label}.snapshot.event_id`);
  oneOf(snapshot.activity, `${label}.snapshot.activity`, new Set(["active", "paused"]));
  string(snapshot.text, `${label}.snapshot.text`);
  integer(snapshot.selection_start_utf16, `${label}.snapshot.selection_start_utf16`);
  integer(snapshot.selection_end_utf16, `${label}.snapshot.selection_end_utf16`);
  bool(snapshot.is_composing, `${label}.snapshot.is_composing`);
  oneOf(snapshot.edit_kind, `${label}.snapshot.edit_kind`, new Set(["insert", "delete", "replace", "paste", "cursor_move", "none"]));
  number(snapshot.age_ms, `${label}.snapshot.age_ms`);

  for (const key of ["timers", "open_timer_fires", "open_tool_results", "pending_tools", "prior_uses", "applied_marks", "ambiguous_marks", "recent_events", "dispositions"]) {
    list(payload[key], `${label}.${key}`);
  }
  for (const [i, timer] of list(payload.timers, `${label}.timers`).entries()) {
    const item = record(timer, `${label}.timers[${i}]`);
    string(item.timer_id, `${label}.timers[${i}].timer_id`);
    string(item.instruction_id, `${label}.timers[${i}].instruction_id`);
    string(item.instruction_text, `${label}.timers[${i}].instruction_text`);
    integer(item.interval_ms, `${label}.timers[${i}].interval_ms`, 1);
    string(item.message, `${label}.timers[${i}].message`);
    oneOf(item.status, `${label}.timers[${i}].status`, new Set(["active", "canceled"]));
    if (item.next_due_in_ms !== null) number(item.next_due_in_ms, `${label}.timers[${i}].next_due_in_ms`);
    integer(item.fire_count, `${label}.timers[${i}].fire_count`);
  }
  for (const [i, fire] of list(payload.open_timer_fires, `${label}.open_timer_fires`).entries()) {
    const item = record(fire, `${label}.open_timer_fires[${i}]`);
    string(item.event_id, `${label}.open_timer_fires[${i}].event_id`);
  }
  for (const [i, result] of list(payload.open_tool_results, `${label}.open_tool_results`).entries()) {
    const item = record(result, `${label}.open_tool_results[${i}]`);
    string(item.event_id, `${label}.open_tool_results[${i}].event_id`);
    string(item.request_id, `${label}.open_tool_results[${i}].request_id`);
    string(item.fact_event_id, `${label}.open_tool_results[${i}].fact_event_id`);
    string(item.fact_text, `${label}.open_tool_results[${i}].fact_text`);
    if (item.tool !== "lookup") throw new Error(`${label}.open_tool_results[${i}].tool must be lookup`);
    string(record(item.args, `${label}.open_tool_results[${i}].args`).query, `${label}.open_tool_results[${i}].args.query`);
    oneOf(item.status, `${label}.open_tool_results[${i}].status`, new Set(["succeeded", "failed"]));
  }
  for (const [i, pending] of list(payload.pending_tools, `${label}.pending_tools`).entries()) {
    const item = record(pending, `${label}.pending_tools[${i}]`);
    string(item.request_id, `${label}.pending_tools[${i}].request_id`);
    string(item.fact_event_id, `${label}.pending_tools[${i}].fact_event_id`);
    string(item.fact_text, `${label}.pending_tools[${i}].fact_text`);
    if (item.tool !== "lookup") throw new Error(`${label}.pending_tools[${i}].tool must be lookup`);
    string(record(item.args, `${label}.pending_tools[${i}].args`).query, `${label}.pending_tools[${i}].args.query`);
  }
  for (const [i, mark] of list(payload.applied_marks, `${label}.applied_marks`).entries()) {
    const item = record(mark, `${label}.applied_marks[${i}]`);
    string(item.mark_event_id, `${label}.applied_marks[${i}].mark_event_id`);
    string(item.instruction_text, `${label}.applied_marks[${i}].instruction_text`);
    span(item.target, `${label}.applied_marks[${i}].target`);
  }
  for (const [i, mark] of list(payload.ambiguous_marks, `${label}.ambiguous_marks`).entries()) {
    const item = record(mark, `${label}.ambiguous_marks[${i}]`);
    string(item.mark_event_id, `${label}.ambiguous_marks[${i}].mark_event_id`);
    string(item.instruction_text, `${label}.ambiguous_marks[${i}].instruction_text`);
    const targets = list(item.targets, `${label}.ambiguous_marks[${i}].targets`);
    if (targets.length === 0) {
      throw new Error(`${label}.ambiguous_marks[${i}].targets must not be empty`);
    }
    targets.forEach((target, j) =>
      span(target, `${label}.ambiguous_marks[${i}].targets[${j}]`),
    );
  }
  for (const [i, disposition] of list(payload.dispositions, `${label}.dispositions`).entries()) {
    const item = record(disposition, `${label}.dispositions[${i}]`);
    string(item.event_id, `${label}.dispositions[${i}].event_id`);
    oneOf(item.state, `${label}.dispositions[${i}].state`, new Set(["handled", "skipped", "superseded"]));
    oneOf(item.relation, `${label}.dispositions[${i}].relation`, new Set(["event", "responded_to"]));
  }
  record(payload.hashes, `${label}.hashes`);
}

function validateEvent(value: unknown, label: string): CanonicalEventEnvelope {
  const event = record(value, label);
  if (event.v !== 1) throw new Error(`${label}.v must be 1`);
  string(event.id, `${label}.id`);
  integer(event.seq, `${label}.seq`);
  number(event.dt_ms, `${label}.dt_ms`);
  const kind = oneOf(event.kind, `${label}.kind`, EVENT_KINDS);
  const expectedSource: Record<string, string> = {
    session_start: "runtime", snapshot: "user", annotation: "user", scheduled: "runtime",
    fire: "timer", cancel_ack: "runtime", tool_requested: "runtime", result: "tool",
    action_executed: "model", action_rejected: "runtime", state_checkpoint: "runtime",
  };
  if (event.source !== expectedSource[kind]) throw new Error(`${label}.source is invalid for ${kind}`);
  const payload = record(event.payload, `${label}.payload`);

  switch (kind) {
    case "session_start": {
      if (payload.schema_version !== 1 || payload.hash_algorithm !== "sha256") throw new Error(`${label}.payload session metadata is invalid`);
      for (const key of ["renderer_id", "canonicalizer_id", "schema_hash", "spec_hash", "prompt_hash", "config_hash"]) string(payload[key], `${label}.payload.${key}`);
      integer(payload.tool_registry_version, `${label}.payload.tool_registry_version`);
      const capabilities = record(payload.capabilities, `${label}.payload.capabilities`);
      for (const key of ["min_timer_interval_ms", "max_timer_interval_ms", "max_active_timers", "max_timer_message_bytes"]) integer(capabilities[key], `${label}.payload.capabilities.${key}`);
      break;
    }
    case "snapshot":
      string(payload.text, `${label}.payload.text`);
      integer(payload.selection_start_utf16, `${label}.payload.selection_start_utf16`);
      integer(payload.selection_end_utf16, `${label}.payload.selection_end_utf16`);
      bool(payload.is_composing, `${label}.payload.is_composing`);
      oneOf(payload.edit_kind, `${label}.payload.edit_kind`, new Set(["insert", "delete", "replace", "paste", "cursor_move", "none"]));
      oneOf(event.activity, `${label}.activity`, new Set(["active", "paused"]));
      break;
    case "annotation":
      string(payload.text, `${label}.payload.text`);
      break;
    case "scheduled":
      for (const key of ["timer_id", "instruction_id", "message"]) string(payload[key], `${label}.payload.${key}`);
      integer(payload.interval_ms, `${label}.payload.interval_ms`, 1);
      number(payload.first_due_in_ms, `${label}.payload.first_due_in_ms`);
      break;
    case "fire":
      string(payload.timer_id, `${label}.payload.timer_id`);
      integer(payload.fire_count, `${label}.payload.fire_count`);
      number(payload.late_ms, `${label}.payload.late_ms`);
      integer(payload.missed_count, `${label}.payload.missed_count`);
      break;
    case "cancel_ack":
      stringList(payload.timer_ids, `${label}.payload.timer_ids`);
      break;
    case "tool_requested":
      string(payload.request_id, `${label}.payload.request_id`);
      if (payload.tool !== "lookup") throw new Error(`${label}.payload.tool must be lookup`);
      string(record(payload.args, `${label}.payload.args`).query, `${label}.payload.args.query`);
      break;
    case "result":
      string(payload.request_id, `${label}.payload.request_id`);
      oneOf(payload.status, `${label}.payload.status`, new Set(["succeeded", "failed"]));
      break;
    case "action_executed":
      if (record(payload.action, `${label}.payload.action`).type === "idle") {
        throw new Error(`${label}.payload.action cannot execute idle`);
      }
      action(payload.action, `${label}.payload.action`);
      break;
    case "action_rejected":
      oneOf(payload.reason, `${label}.payload.reason`, new Set([
        "malformed_action", "unknown_reference", "span_mismatch", "result_not_ready", "fire_not_open",
        "timer_not_active", "duplicate_schedule", "duplicate_tool_request", "floor_owned",
        "target_already_handled", "reason_mismatch", "timer_limit_exceeded", "payload_limit_exceeded", "stale_decision",
      ]));
      if (payload.attempted_action !== undefined) {
        throw new Error(`${label}.payload.attempted_action is not part of event-v1`);
      }
      break;
    case "state_checkpoint":
      checkpointPayload(payload, `${label}.payload`);
      break;
  }
  return value as CanonicalEventEnvelope;
}

export async function sha256Hex(text: string): Promise<string> {
  const data = new TextEncoder().encode(text);
  const hash = await crypto.subtle.digest("SHA-256", data);
  return Array.from(new Uint8Array(hash))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

function parseSha256sums(text: string): Map<string, string> {
  const out = new Map<string, string>();
  for (const line of text.split("\n")) {
    const trimmed = line.trimEnd();
    if (trimmed === "") continue;
    const m = trimmed.match(/^([0-9a-f]{64})\s\s+(.+)$/);
    if (!m) {
      throw new Error(`malformed SHA256SUMS line: ${trimmed.slice(0, 80)}`);
    }
    if (out.has(m[2])) {
      throw new Error(`duplicate SHA256SUMS path: ${m[2]}`);
    }
    out.set(m[2], m[1]);
  }
  return out;
}

export function parseJsonl(text: string): CanonicalEventEnvelope[] {
  const events: CanonicalEventEnvelope[] = [];
  let lineNo = 0;
  for (const line of text.split("\n")) {
    lineNo++;
    const trimmed = line.trim();
    if (trimmed === "") continue;
    let parsed: unknown;
    try {
      parsed = JSON.parse(trimmed);
    } catch (e) {
      throw new Error(`JSONL parse error at line ${lineNo}: ${(e as Error).message}`);
    }
    events.push(validateEvent(parsed, `${lineNo}`));
  }
  return events;
}

/** Per-segment: reject duplicates / non-monotonic; allow non-zero start (rollover). */
export function validateSegmentSequence(
  events: CanonicalEventEnvelope[],
  path: string,
): void {
  let prev = -1;
  for (const ev of events) {
    if (typeof ev.seq !== "number" || !Number.isInteger(ev.seq) || ev.seq < 0) {
      throw new Error(`${path}: event seq missing/invalid`);
    }
    if (ev.seq === prev) {
      throw new Error(`${path}: duplicate event seq ${ev.seq}`);
    }
    if (prev >= 0 && ev.seq !== prev + 1) {
      throw new Error(
        `${path}: non-monotonic event seq: expected ${prev + 1}, got ${ev.seq}`,
      );
    }
    prev = ev.seq;
  }
}

export function stripSha(s: string): string {
  return s.startsWith("sha256:") ? s.slice(7) : s;
}

function isTopLevelFile(path: string): boolean {
  return path === "SHA256SUMS";
}

function validateManifest(value: unknown): Manifest {
  const manifest = record(value, "manifest.json");
  if (manifest.format_version !== 1) {
    throw new Error("manifest.json.format_version must be 1");
  }
  const streams = list(manifest.streams, "manifest.json.streams");
  if (streams.length === 0) throw new Error("manifest.json.streams must not be empty");
  for (const [i, rawStream] of streams.entries()) {
    const stream = record(rawStream, `manifest.json.streams[${i}]`);
    hash(stream.stream_sha256, `manifest.json.streams[${i}].stream_sha256`);
    string(stream.family, `manifest.json.streams[${i}].family`);
    integer(stream.decision_count, `manifest.json.streams[${i}].decision_count`);
    const segments = list(stream.teacher_segment_sha256s, `manifest.json.streams[${i}].teacher_segment_sha256s`);
    if (segments.length === 0) throw new Error(`manifest.json.streams[${i}].teacher_segment_sha256s must not be empty`);
    segments.forEach((segment, j) => hash(segment, `manifest.json.streams[${i}].teacher_segment_sha256s[${j}]`));
    hash(stream.sidecar_sha256, `manifest.json.streams[${i}].sidecar_sha256`);
    stringList(stream.declared_perturbations, `manifest.json.streams[${i}].declared_perturbations`);
    string(stream.master_seed, `manifest.json.streams[${i}].master_seed`);
    string(stream.split, `manifest.json.streams[${i}].split`);
    hash(stream.capture_sha256, `manifest.json.streams[${i}].capture_sha256`);
  }
  return value as Manifest;
}

function sourceCheckpoint(value: unknown, label: string): void {
  const checkpoint = record(value, label);
  integer(checkpoint.checkpoint_seq, `${label}.checkpoint_seq`);
  hash(checkpoint.previous_segment_hash, `${label}.previous_segment_hash`);
  integer(checkpoint.segment_index, `${label}.segment_index`, 1);
  hash(checkpoint.segment_sha256, `${label}.segment_sha256`);
  list(checkpoint.selected_call_indices, `${label}.selected_call_indices`).forEach((call, i) => integer(call, `${label}.selected_call_indices[${i}]`));
  hash(checkpoint.stream_sha256, `${label}.stream_sha256`);
}

function validateSourceIndex(value: unknown): SourceIndex {
  const index = record(value, "source-index.json");
  if (index.batch !== 1) throw new Error("source-index.json.batch must be 1");
  if (index.format_version !== 1) {
    throw new Error("source-index.json.format_version must be 1");
  }
  string(index.source_identity_rule, "source-index.json.source_identity_rule");
  const sources = list(index.sources, "source-index.json.sources");
  if (sources.length === 0) throw new Error("source-index.json.sources must not be empty");
  for (const [i, rawSource] of sources.entries()) {
    const source = record(rawSource, `source-index.json.sources[${i}]`);
    for (const key of ["family", "master_seed", "role", "shape_id", "source_kind"]) string(source[key], `source-index.json.sources[${i}].${key}`);
    const parents = list(source.parent_stream_sha256s, `source-index.json.sources[${i}].parent_stream_sha256s`);
    const raws = list(source.raw_source_sha256s, `source-index.json.sources[${i}].raw_source_sha256s`);
    const sidecars = list(source.sidecar_sha256s, `source-index.json.sources[${i}].sidecar_sha256s`);
    const counts = list(source.source_decision_counts, `source-index.json.sources[${i}].source_decision_counts`);
    if (parents.length === 0 || raws.length !== parents.length || sidecars.length !== parents.length || counts.length !== parents.length) {
      throw new Error(`source-index.json.sources[${i}] identities must align`);
    }
    parents.forEach((item, j) => hash(item, `source-index.json.sources[${i}].parent_stream_sha256s[${j}]`));
    raws.forEach((item, j) => hash(item, `source-index.json.sources[${i}].raw_source_sha256s[${j}]`));
    sidecars.forEach((item, j) => hash(item, `source-index.json.sources[${i}].sidecar_sha256s[${j}]`));
    counts.forEach((item, j) => integer(item, `source-index.json.sources[${i}].source_decision_counts[${j}]`));
    if (source.checkpoint !== null) {
      const checkpoint = record(source.checkpoint, `source-index.json.sources[${i}].checkpoint`);
      if (checkpoint.candidates !== undefined) {
        const candidates = list(checkpoint.candidates, `source-index.json.sources[${i}].checkpoint.candidates`);
        if (candidates.length === 0) throw new Error(`source-index.json.sources[${i}].checkpoint.candidates must not be empty`);
        candidates.forEach((candidate, j) => sourceCheckpoint(candidate, `source-index.json.sources[${i}].checkpoint.candidates[${j}]`));
      } else {
        sourceCheckpoint(checkpoint, `source-index.json.sources[${i}].checkpoint`);
      }
    }
  }
  return value as SourceIndex;
}

function validateSidecar(value: unknown, label: string): Sidecar {
  const sidecar = record(value, label);
  integer(sidecar.format_version, `${label}.format_version`, 1);
  string(sidecar.family, `${label}.family`);
  hash(sidecar.stream_sha256, `${label}.stream_sha256`);
  string(sidecar.split, `${label}.split`);
  list(sidecar.perturbations, `${label}.perturbations`);
  list(sidecar.assets, `${label}.assets`);
  for (const key of ["capture_sha256", "regeneration_identity", "scenario_input_sha256", "world_script_sha256"]) hash(sidecar[key], `${label}.${key}`);
  const decisions = list(sidecar.decisions, `${label}.decisions`);
  const seenPolicySeqs = new Set<number>();
  const seenCallIndices = new Set<number>();
  let previousPolicySeq = -1;
  let previousCallIndex = 0;
  for (const [i, rawDecision] of decisions.entries()) {
    const decision = record(rawDecision, `${label}.decisions[${i}]`);
    action(decision.action, `${label}.decisions[${i}].action`);
    const policySeq = integer(decision.observed_policy_seq, `${label}.decisions[${i}].observed_policy_seq`);
    if (seenPolicySeqs.has(policySeq)) throw new Error(`${label}.decisions[${i}].observed_policy_seq is duplicated`);
    if (policySeq <= previousPolicySeq) throw new Error(`${label}.decisions[${i}].observed_policy_seq is not increasing`);
    seenPolicySeqs.add(policySeq);
    previousPolicySeq = policySeq;
    const callIndex = integer(decision.call_index, `${label}.decisions[${i}].call_index`, 1);
    if (seenCallIndices.has(callIndex)) throw new Error(`${label}.decisions[${i}].call_index is duplicated`);
    if (callIndex <= previousCallIndex) throw new Error(`${label}.decisions[${i}].call_index is not increasing`);
    seenCallIndices.add(callIndex);
    previousCallIndex = callIndex;
    string(decision.beat_id, `${label}.decisions[${i}].beat_id`);
    for (const key of ["active_timer_ids", "canceled_timer_ids", "pending_request_ids", "open_tool_result_event_ids", "stale_tool_result_event_ids", "open_timer_fire_event_ids"]) stringList(decision[key], `${label}.decisions[${i}].${key}`);
    bool(decision.floor_open, `${label}.decisions[${i}].floor_open`);
    bool(decision.floor_owned, `${label}.decisions[${i}].floor_owned`);
  }
  return value as Sidecar;
}

function validateRuntimeLedger(value: unknown, label: string): RuntimeLedger {
  const ledger = record(value, label);
  for (const key of ["dispositions", "response_dispositions", "timers", "tool_requests"]) list(ledger[key], `${label}.${key}`);
  for (const [i, rawDisposition] of list(ledger.dispositions, `${label}.dispositions`).entries()) {
    const disposition = record(rawDisposition, `${label}.dispositions[${i}]`);
    string(disposition.event_id, `${label}.dispositions[${i}].event_id`);
    if (disposition.by_action_event_id !== null) string(disposition.by_action_event_id, `${label}.dispositions[${i}].by_action_event_id`);
    oneOf(disposition.state, `${label}.dispositions[${i}].state`, new Set(["open", "handled", "skipped", "superseded"]));
  }
  for (const [i, rawDisposition] of list(ledger.response_dispositions, `${label}.response_dispositions`).entries()) {
    const disposition = record(rawDisposition, `${label}.response_dispositions[${i}]`);
    string(disposition.event_id, `${label}.response_dispositions[${i}].event_id`);
    string(disposition.by_action_event_id, `${label}.response_dispositions[${i}].by_action_event_id`);
    if (disposition.state !== undefined) oneOf(disposition.state, `${label}.response_dispositions[${i}].state`, new Set(["handled", "skipped", "superseded"]));
  }
  for (const [i, rawTimer] of list(ledger.timers, `${label}.timers`).entries()) {
    const timer = record(rawTimer, `${label}.timers[${i}]`);
    string(timer.timer_id, `${label}.timers[${i}].timer_id`);
    integer(timer.interval_ms, `${label}.timers[${i}].interval_ms`, 1);
    oneOf(timer.status, `${label}.timers[${i}].status`, new Set(["active", "canceled"]));
    integer(timer.fire_count, `${label}.timers[${i}].fire_count`);
  }
  for (const [i, rawRequest] of list(ledger.tool_requests, `${label}.tool_requests`).entries()) {
    const request = record(rawRequest, `${label}.tool_requests[${i}]`);
    string(request.request_id, `${label}.tool_requests[${i}].request_id`);
    oneOf(request.status, `${label}.tool_requests[${i}].status`, new Set(["completed", "pending", "stale"]));
    if (request.result_event_id !== undefined && request.result_event_id !== null) string(request.result_event_id, `${label}.tool_requests[${i}].result_event_id`);
    if (request.result_status !== undefined) oneOf(request.result_status, `${label}.tool_requests[${i}].result_status`, new Set(["succeeded", "failed"]));
  }
  return value as RuntimeLedger;
}

function validateCheckpointSelection(value: unknown, label: string): CheckpointSelection {
  const selection = record(value, label);
  integer(selection.format_version, `${label}.format_version`, 1);
  integer(selection.checkpoint_seq, `${label}.checkpoint_seq`);
  hash(selection.parent_sidecar_sha256, `${label}.parent_sidecar_sha256`);
  hash(selection.parent_stream_sha256, `${label}.parent_stream_sha256`);
  hash(selection.previous_segment_hash, `${label}.previous_segment_hash`);
  integer(selection.segment_index, `${label}.segment_index`, 1);
  hash(selection.segment_sha256, `${label}.segment_sha256`);
  list(selection.selected_call_indices, `${label}.selected_call_indices`).forEach((item, i) => integer(item, `${label}.selected_call_indices[${i}]`));
  return value as CheckpointSelection;
}

function reconcileSourceIdentities(manifest: Manifest, sourceIndex: SourceIndex, errors: string[]): void {
  const streamsByHash = new Map(
    manifest.streams.map((stream) => [stripSha(stream.stream_sha256), stream]),
  );
  const sources = new Map<string, SourceIndex["sources"][number]>();
  for (const source of sourceIndex.sources) {
    const parents = source.parent_stream_sha256s.map(stripSha);
    const boundStreams = parents
      .map((parent) => streamsByHash.get(parent))
      .filter((stream): stream is Manifest["streams"][number] => stream !== undefined);
    if (boundStreams.length === parents.length) {
      const declaredSidecars = source.sidecar_sha256s.map(stripSha).sort();
      const boundSidecars = boundStreams.map((stream) => stripSha(stream.sidecar_sha256)).sort();
      if (JSON.stringify(declaredSidecars) !== JSON.stringify(boundSidecars)) {
        errors.push(`source-index.json: sidecar identities do not close over source unit`);
      }
      const declaredCounts = [...source.source_decision_counts].sort((a, b) => a - b);
      let boundCounts: number[];
      if (source.checkpoint === null) {
        boundCounts = boundStreams.map((stream) => stream.decision_count);
      } else {
        const checkpoint = source.checkpoint as unknown as JsonRecord;
        const candidates = Array.isArray(checkpoint.candidates)
          ? checkpoint.candidates
          : [checkpoint];
        const candidateRecords = candidates.map((candidate) =>
          record(candidate, "source checkpoint"),
        );
        boundCounts = candidateRecords.map(
          (candidate) => list(candidate.selected_call_indices, "selected calls").length,
        );
        const candidateSegments = candidateRecords
          .map((candidate) => stripSha(string(candidate.segment_sha256, "segment_sha256")))
          .sort();
        const rawSegments = source.raw_source_sha256s.map(stripSha).sort();
        if (JSON.stringify(candidateSegments) !== JSON.stringify(rawSegments)) {
          errors.push(`source-index.json: checkpoint segments do not close over raw sources`);
        }
        const candidateStreams = candidateRecords
          .map((candidate) => stripSha(string(candidate.stream_sha256, "stream_sha256")))
          .sort();
        if (JSON.stringify(candidateStreams) !== JSON.stringify(parents.slice().sort())) {
          errors.push(`source-index.json: checkpoint streams do not close over parents`);
        }
      }
      boundCounts.sort((a, b) => a - b);
      if (JSON.stringify(declaredCounts) !== JSON.stringify(boundCounts)) {
        errors.push(`source-index.json: decision counts do not close over source unit`);
      }
    }
    source.parent_stream_sha256s.forEach((parent) => {
      const streamHash = stripSha(parent);
      if (sources.has(streamHash)) errors.push(`source-index.json: duplicate parent stream identity ${streamHash}`);
      sources.set(streamHash, source);
    });
  }
  if (sources.size !== manifest.streams.length) {
    errors.push(`source-index.json: ${sources.size} stream identities != manifest ${manifest.streams.length}`);
  }
  for (const stream of manifest.streams) {
    const streamHash = stripSha(stream.stream_sha256);
    const source = sources.get(streamHash);
    if (!source) {
      errors.push(`source-index.json: missing identity for manifest stream ${streamHash}`);
      continue;
    }
    if (source.family !== stream.family || source.master_seed !== stream.master_seed) {
      errors.push(`source-index.json: identity metadata mismatch for stream ${streamHash}`);
    }
  }
}

export async function loadPacketFromEntries(
  entries: PacketEntry[],
): Promise<PacketLoadResult> {
  try {
    return await loadPacketUnchecked(entries);
  } catch (e) {
    return { ok: false, errors: [`packet load: ${problem(e)}`] };
  }
}

async function loadPacketUnchecked(entries: PacketEntry[]): Promise<PacketLoadResult> {
  const errors: string[] = [];
  const byPath = new Map<string, string>();
  if (!Array.isArray(entries)) return { ok: false, errors: ["packet entries must be an array"] };
  for (const [i, rawEntry] of entries.entries()) {
    const entry = record(rawEntry, `entry ${i}`);
    const path = string(entry.path, `entry ${i}.path`);
    const text = string(entry.text, `entry ${i}.text`);
    if (byPath.has(path)) {
      errors.push(`duplicate path: ${path}`);
    }
    byPath.set(path, text);
  }
  if (errors.length > 0) return { ok: false, errors };

  const manifestText = byPath.get("manifest.json");
  const sourceIndexText = byPath.get("source-index.json");
  const shaText = byPath.get("SHA256SUMS");

  if (!manifestText) errors.push("missing manifest.json");
  if (!sourceIndexText) errors.push("missing source-index.json");
  if (!shaText) errors.push("missing SHA256SUMS");
  if (errors.length > 0) return { ok: false, errors };

  let shaSums: Map<string, string>;
  try {
    shaSums = parseSha256sums(shaText!);
  } catch (e) {
    return { ok: false, errors: [`SHA256SUMS parse: ${problem(e)}`] };
  }

  for (const path of ["manifest.json", "source-index.json"]) {
    if (!shaSums.has(path)) errors.push(`SHA256SUMS missing required entry: ${path}`);
  }

  for (const [relPath, expectedHash] of shaSums) {
    const text = byPath.get(relPath);
    if (text === undefined) {
      errors.push(`missing file declared in SHA256SUMS: ${relPath}`);
      continue;
    }
    let actualHash: string;
    try {
      actualHash = await sha256Hex(text);
    } catch (e) {
      errors.push(`hash error for ${relPath}: ${(e as Error).message}`);
      continue;
    }
    if (actualHash !== expectedHash) {
      errors.push(
        `hash mismatch for ${relPath}: expected ${expectedHash}, got ${actualHash}`,
      );
    }
  }

  const declared = new Set<string>(shaSums.keys());
  for (const path of byPath.keys()) {
    if (!declared.has(path) && !isTopLevelFile(path)) {
      errors.push(`undeclared file not in SHA256SUMS: ${path}`);
    }
  }

  if (errors.length > 0) return { ok: false, errors };

  let manifest: Manifest;
  let sourceIndex: SourceIndex;
  try {
    manifest = validateManifest(JSON.parse(manifestText!));
  } catch (e) {
    return { ok: false, errors: [`manifest.json: ${problem(e)}`] };
  }
  try {
    sourceIndex = validateSourceIndex(JSON.parse(sourceIndexText!));
  } catch (e) {
    return { ok: false, errors: [`source-index.json: ${problem(e)}`] };
  }

  reconcileSourceIdentities(manifest, sourceIndex, errors);
  if (errors.length > 0) return { ok: false, errors };

  const seenStreamHashes = new Set<string>();
  const streams: LoadedStream[] = [];

  for (const ms of manifest.streams) {
    const streamHash = stripSha(ms.stream_sha256);
    if (!HASH_RE.test(streamHash)) {
      errors.push(`manifest stream_sha256 invalid: ${ms.stream_sha256}`);
      continue;
    }
    if (seenStreamHashes.has(streamHash)) {
      errors.push(`duplicate manifest stream_sha256: ${streamHash}`);
      continue;
    }
    seenStreamHashes.add(streamHash);

    const sidecarPath = `reviewer/${streamHash}/sidecar.json`;
    const ledgerPath = `reviewer/${streamHash}/runtime-ledger.json`;
    const checkpointPath = `reviewer/${streamHash}/checkpoint-selection.json`;

    const sidecarText = byPath.get(sidecarPath);
    const ledgerText = byPath.get(ledgerPath);
    if (!sidecarText) errors.push(`missing ${sidecarPath}`);
    if (!ledgerText) errors.push(`missing ${ledgerPath}`);

    const segmentHashes = ms.teacher_segment_sha256s.map(stripSha);
    const segments: LoadedSegment[] = [];
    for (let i = 0; i < segmentHashes.length; i++) {
      const segHash = segmentHashes[i];
      if (!HASH_RE.test(segHash)) {
        errors.push(`manifest teacher_segment_sha256s[${i}] invalid for ${streamHash}`);
        continue;
      }
      const segPath = `teacher/${streamHash}/${segHash}.jsonl`;
      const segText = byPath.get(segPath);
      if (!segText) {
        errors.push(`missing ${segPath}`);
        continue;
      }
      const contentHash = await sha256Hex(segText);
      if (contentHash !== segHash) {
        errors.push(
          `${segPath}: content hash ${contentHash} != declared segment ${segHash}`,
        );
        continue;
      }
      let events: CanonicalEventEnvelope[];
      try {
        events = parseJsonl(segText);
        validateSegmentSequence(events, segPath);
      } catch (e) {
        errors.push(`${segPath}: ${(e as Error).message}`);
        continue;
      }
      segments.push({ sha256: segHash, events });
    }

    // Checkpoint linkage for multi-segment streams.
    for (let i = 1; i < segments.length; i++) {
      const first = segments[i].events[0];
      if (!first || first.kind !== "state_checkpoint") {
        errors.push(
          `teacher/${streamHash}/${segments[i].sha256}.jsonl: expected leading state_checkpoint`,
        );
        continue;
      }
      const prevHash = stripSha(first.payload.segment.previous_segment_hash);
      if (prevHash !== segments[i - 1].sha256) {
        errors.push(
          `stream ${streamHash}: segment ${i} previous_segment_hash ${prevHash} != ${segments[i - 1].sha256}`,
        );
      }
    }

    // Concatenated stream must be globally monotonic.
    if (segments.length > 1) {
      const all = segments.flatMap((s) => s.events);
      try {
        validateSegmentSequence(all, `stream ${streamHash} concatenated`);
      } catch (e) {
        errors.push((e as Error).message);
      }
    }

    let sidecar: Sidecar | null = null;
    if (sidecarText) {
      try {
        sidecar = validateSidecar(JSON.parse(sidecarText), sidecarPath);
      } catch (e) {
        errors.push(`${sidecarPath}: ${problem(e)}`);
      }
    }

    let ledger: RuntimeLedger | null = null;
    if (ledgerText) {
      try {
        ledger = validateRuntimeLedger(JSON.parse(ledgerText), ledgerPath);
      } catch (e) {
        errors.push(`${ledgerPath}: ${problem(e)}`);
      }
    }

    let checkpointSelection: CheckpointSelection | null = null;
    const cpText = byPath.get(checkpointPath);
    if (cpText !== undefined) {
      try {
        checkpointSelection = validateCheckpointSelection(JSON.parse(cpText), checkpointPath);
      } catch (e) {
        errors.push(`${checkpointPath}: ${problem(e)}`);
      }
    }

    if (sidecar) {
      if (stripSha(sidecar.stream_sha256) !== streamHash) {
        errors.push(
          `${sidecarPath}: stream_sha256 mismatch (sidecar ${sidecar.stream_sha256} vs manifest ${streamHash})`,
        );
      }
      if (sidecar.family !== ms.family || sidecar.split !== ms.split) {
        errors.push(`${sidecarPath}: family or split mismatch with manifest`);
      }
      if (stripSha(sidecar.capture_sha256) !== stripSha(ms.capture_sha256)) {
        errors.push(`${sidecarPath}: capture_sha256 mismatch with manifest`);
      }
      if (sidecar.decisions.length !== ms.decision_count) {
        errors.push(`${sidecarPath}: decisions ${sidecar.decisions.length} != manifest decision_count ${ms.decision_count}`);
      }
      const eventSeqs = new Set(segments.flatMap((segment) => segment.events.map((event) => event.seq)));
      for (const decision of sidecar.decisions) {
        if (!eventSeqs.has(decision.observed_policy_seq)) {
          errors.push(`${sidecarPath}: decision policy_seq ${decision.observed_policy_seq} is not in the stream`);
        }
      }
    }

    const declaredSidecarHash = stripSha(ms.sidecar_sha256);
    if (sidecarText) {
      const actualSidecarHash = await sha256Hex(sidecarText);
      if (actualSidecarHash !== declaredSidecarHash) {
        errors.push(
          `${sidecarPath}: sidecar hash mismatch (manifest ${declaredSidecarHash} vs actual ${actualSidecarHash})`,
        );
      }
    }

    if (checkpointSelection) {
      const segment = segments[checkpointSelection.segment_index];
      const selectedCalls =
        sidecar?.decisions
          .filter((decision) => decision.observed_policy_seq > checkpointSelection.checkpoint_seq)
          .map((decision) => decision.call_index) ?? [];
      if (
        stripSha(checkpointSelection.parent_stream_sha256) !== streamHash ||
        stripSha(checkpointSelection.parent_sidecar_sha256) !== declaredSidecarHash ||
        !segment ||
        checkpointSelection.segment_sha256 !== `sha256:${segment.sha256}` ||
        (checkpointSelection.segment_index > 0 &&
          stripSha(checkpointSelection.previous_segment_hash) !== segments[checkpointSelection.segment_index - 1]?.sha256) ||
        JSON.stringify(checkpointSelection.selected_call_indices) !== JSON.stringify(selectedCalls)
      ) {
        errors.push(`${checkpointPath}: identity mismatch with manifest segments`);
      }
    }

    if (sidecar && ledger && segments.length > 0) {
      streams.push({
        sha256: streamHash,
        family: ms.family,
        decisionCount: ms.decision_count,
        declaredPerturbations: ms.declared_perturbations,
        split: ms.split,
        counterfactual: ms.counterfactual,
        segments,
        sidecar,
        runtimeLedger: ledger,
        checkpointSelection,
      });
    }
  }

  if (errors.length > 0) return { ok: false, errors };

  if (streams.length !== manifest.streams.length) {
    return {
      ok: false,
      errors: [`loaded stream count ${streams.length} != manifest ${manifest.streams.length}`],
    };
  }

  return {
    ok: true,
    packet: {
      manifest,
      sourceIndex,
      streams,
      integrity: {
        manifestSha256: shaSums.get("manifest.json")!,
        sourceIndexSha256: shaSums.get("source-index.json")!,
      },
    },
  };
}

/** Browser wrapper: read a directory FileList into entries, then load. */
export async function loadPacketFromFiles(files: File[]): Promise<PacketLoadResult> {
  try {
    const entries: PacketEntry[] = [];
    for (const file of files) {
      const relPath = file.webkitRelativePath || file.name;
      const slashIdx = relPath.indexOf("/");
      const stripped = slashIdx >= 0 ? relPath.slice(slashIdx + 1) : relPath;
      if (stripped === "") continue;
      if (stripped.startsWith(".DS_Store") || stripped.includes("/.DS_Store")) continue;
      const text = await file.text();
      entries.push({ path: stripped, text });
    }
    return loadPacketFromEntries(entries);
  } catch (e) {
    return { ok: false, errors: [`packet files: ${problem(e)}`] };
  }
}

/** Concatenate segment events for a loaded stream (immutable input; returns new array). */
export function concatStreamEvents(stream: LoadedStream): CanonicalEventEnvelope[] {
  const out: CanonicalEventEnvelope[] = [];
  for (const seg of stream.segments) {
    for (const ev of seg.events) out.push(ev);
  }
  return out;
}
