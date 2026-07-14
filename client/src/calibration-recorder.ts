/**
 * Opt-in, in-memory calibration recording for the browser harness.
 *
 * This deliberately records a sidecar only. It neither sends frames nor
 * participates in the policy/corpus paths; callers decide when and where an
 * exported bundle is persisted.
 */

import type { ClientSnapshotFrame } from "./protocol";

export const CALIBRATION_RECORDING_VERSION = "calibration-recording/v1";

/** Versions understood by this recorder. Additive format changes require a new entry. */
export const CALIBRATION_RECORDING_VERSIONS = [CALIBRATION_RECORDING_VERSION] as const;

export type CalibrationRecordingVersion = (typeof CALIBRATION_RECORDING_VERSIONS)[number];

/** The six D3 recording regimes. Calibration bundles are never untagged. */
export const CALIBRATION_REGIMES = [
  "natural-drafting",
  "revision-heavy-writing",
  "copied-or-scripted-typing",
  "cursor-and-selection-edits",
  "short-command-like-inputs",
  "pauses-and-resumptions",
] as const;

export type CalibrationRegime = (typeof CALIBRATION_REGIMES)[number];

export type RawTextareaEventKind =
  | "input"
  | "selectionchange"
  | "compositionstart"
  | "compositionupdate"
  | "compositionend";

/**
 * A raw browser interaction as observed at the attached textarea. Selection
 * offsets are textarea DOM offsets, which are UTF-16 code-unit positions.
 */
export type RawTextareaInteraction = {
  ordinal: number;
  relative_ms: number;
  kind: RawTextareaEventKind;
  input_type: string | null;
  data: string | null;
  text: string;
  selection_start: number;
  selection_end: number;
  is_composing: boolean;
};

/** A sampler frame with capture order and the recorder's monotonic timeline. */
export type RecordedSamplerFrame = {
  ordinal: number;
  relative_ms: number;
  frame: ClientSnapshotFrame;
};

/** JSON-safe, sidecar-only output for one calibration session. */
export type CalibrationRecordingBundle = {
  version: CalibrationRecordingVersion;
  runtime_session_id: string;
  regime: CalibrationRegime;
  raw_events: RawTextareaInteraction[];
  sampler_frames: RecordedSamplerFrame[];
};

export type CalibrationRecorderOptions = {
  version: CalibrationRecordingVersion;
  /** Joins this browser sidecar to the server policy/session recording. */
  runtime_session_id: string;
  regime: CalibrationRegime;
  /** Injectable for deterministic tests and scripted harness replays. */
  now?: () => number;
};

export type CalibrationRecorder = {
  /** Pass this directly as the sampler's emit callback or through a wrapper. */
  captureSamplerFrame: (frame: ClientSnapshotFrame) => void;
  /** Produces a fresh JSON-safe snapshot; calling it never changes recorded data. */
  exportBundle: () => CalibrationRecordingBundle;
  /** Stops raw event capture and ignores later sampler frames. Safe to call twice. */
  detach: () => void;
};

function isKnownValue(value: unknown, values: readonly string[]): value is string {
  return typeof value === "string" && values.includes(value);
}

function assertKnownOption(value: unknown, values: readonly string[], name: string): void {
  if (!isKnownValue(value, values)) {
    throw new RangeError(`${name} must be one of: ${values.join(", ")}`);
  }
}

function finiteTime(value: number): number {
  if (!Number.isFinite(value)) {
    throw new RangeError("now must return a finite number");
  }
  return value;
}

function eventString(event: Event, property: "data" | "inputType"): string | null {
  const value = (event as Event & Record<string, unknown>)[property];
  return typeof value === "string" ? value : null;
}

function copyRawEvent(record: RawTextareaInteraction): RawTextareaInteraction {
  return { ...record };
}

function copySamplerFrame(record: RecordedSamplerFrame): RecordedSamplerFrame {
  return { ...record, frame: { ...record.frame } };
}

/**
 * Attach an opt-in calibration sidecar recorder to one textarea.
 *
 * It observes the same document-level `selectionchange` source as the sampler,
 * but only while this textarea is focused. The returned `captureSamplerFrame`
 * callback is intentionally separate so this module does not modify sampler or
 * websocket behavior.
 */
export function attachCalibrationRecorder(
  textarea: HTMLTextAreaElement,
  options: CalibrationRecorderOptions,
): CalibrationRecorder {
  assertKnownOption(options.version, CALIBRATION_RECORDING_VERSIONS, "version");
  assertKnownOption(options.regime, CALIBRATION_REGIMES, "regime");
  if (
    typeof options.runtime_session_id !== "string" ||
    options.runtime_session_id.trim().length === 0 ||
    options.runtime_session_id.trim() !== options.runtime_session_id ||
    options.runtime_session_id.length > 256
  ) {
    throw new RangeError("runtime_session_id must be a nonempty string of at most 256 characters");
  }

  const version = options.version;
  const runtimeSessionId = options.runtime_session_id;
  const regime = options.regime;
  const now = options.now ?? (() => performance.now());
  const startedAt = finiteTime(now());
  const rawEvents: RawTextareaInteraction[] = [];
  const samplerFrames: RecordedSamplerFrame[] = [];
  let isComposing = false;
  let captureOrdinal = 0;
  let lastRelativeMs = 0;
  let detached = false;

  const relativeNow = (): number => {
    const elapsed = finiteTime(now()) - startedAt;
    if (elapsed < lastRelativeMs || elapsed < 0) {
      throw new RangeError("now must be monotonic during calibration recording");
    }
    lastRelativeMs = elapsed;
    return lastRelativeMs;
  };

  const nextOrdinal = (): number => {
    captureOrdinal += 1;
    return captureOrdinal;
  };

  const recordRawEvent = (
    kind: RawTextareaEventKind,
    inputType: string | null,
    data: string | null,
  ): void => {
    if (detached) {
      return;
    }
    const relativeMs = relativeNow();
    rawEvents.push({
      ordinal: nextOrdinal(),
      relative_ms: relativeMs,
      kind,
      input_type: inputType,
      data,
      text: textarea.value,
      selection_start: textarea.selectionStart,
      selection_end: textarea.selectionEnd,
      is_composing: isComposing,
    });
  };

  const onInput = (event: Event): void => {
    recordRawEvent("input", eventString(event, "inputType"), eventString(event, "data"));
  };
  const onSelectionChange = (): void => {
    if (document.activeElement === textarea) {
      recordRawEvent("selectionchange", null, null);
    }
  };
  const onCompositionStart = (event: Event): void => {
    isComposing = true;
    recordRawEvent("compositionstart", null, eventString(event, "data"));
  };
  const onCompositionUpdate = (event: Event): void => {
    recordRawEvent("compositionupdate", null, eventString(event, "data"));
  };
  const onCompositionEnd = (event: Event): void => {
    isComposing = false;
    recordRawEvent("compositionend", null, eventString(event, "data"));
  };

  textarea.addEventListener("input", onInput);
  document.addEventListener("selectionchange", onSelectionChange);
  textarea.addEventListener("compositionstart", onCompositionStart);
  textarea.addEventListener("compositionupdate", onCompositionUpdate);
  textarea.addEventListener("compositionend", onCompositionEnd);

  return {
    captureSamplerFrame: (frame): void => {
      if (detached) {
        return;
      }
      const relativeMs = relativeNow();
      samplerFrames.push({
        ordinal: nextOrdinal(),
        relative_ms: relativeMs,
        frame: { ...frame },
      });
    },
    exportBundle: (): CalibrationRecordingBundle => ({
      version,
      runtime_session_id: runtimeSessionId,
      regime,
      raw_events: rawEvents.map(copyRawEvent),
      sampler_frames: samplerFrames.map(copySamplerFrame),
    }),
    detach: (): void => {
      if (detached) {
        return;
      }
      detached = true;
      textarea.removeEventListener("input", onInput);
      document.removeEventListener("selectionchange", onSelectionChange);
      textarea.removeEventListener("compositionstart", onCompositionStart);
      textarea.removeEventListener("compositionupdate", onCompositionUpdate);
      textarea.removeEventListener("compositionend", onCompositionEnd);
    },
  };
}
