/** Production sampler — Phase 1 typing simulation drives this exact module. */

import type { Activity, ClientSnapshotFrame } from "./protocol";

export type { Activity, ClientSnapshotFrame } from "./protocol";

/** Backwards-compatible name for the sampler's sole emitted frame. */
export type SamplerFrame = ClientSnapshotFrame;
export type SamplerEmit = (frame: SamplerFrame) => void;

export type SamplerOptions = {
  /** Names mirror the frozen runtime config carried by the session. */
  sampler_throttle_ms?: number;
  pause_ms?: number;
  now?: () => number;
};

const DEFAULT_SAMPLER_THROTTLE_MS = 100;
const DEFAULT_PAUSE_MS = 1_500;

function positiveDelay(value: number | undefined, fallback: number, name: string): number {
  const delay = value ?? fallback;
  if (!Number.isInteger(delay) || delay <= 0) {
    throw new RangeError(`${name} must be a positive integer`);
  }
  return delay;
}

/**
 * Sample one textarea without interpreting its contents.
 *
 * Active snapshots use a trailing throttle: a burst produces its latest state
 * at the end of each throttle window. A separate inactivity timer emits exactly
 * one paused snapshot until another observed textarea activity re-arms it.
 */
export function attachSampler(
  textarea: HTMLTextAreaElement,
  emit: SamplerEmit,
  options: SamplerOptions = {},
): (options?: { flushPending?: boolean }) => void {
  const samplerThrottleMs = positiveDelay(
    options.sampler_throttle_ms,
    DEFAULT_SAMPLER_THROTTLE_MS,
    "sampler_throttle_ms",
  );
  const pauseMs = positiveDelay(options.pause_ms, DEFAULT_PAUSE_MS, "pause_ms");
  const now = options.now ?? Date.now;

  let isComposing = false;
  let inputTypeHint: string | null = null;
  let activePending = false;
  let pausedEmitted = false;
  let detached = false;
  let throttleTimer: ReturnType<typeof setTimeout> | undefined;
  let pauseTimer: ReturnType<typeof setTimeout> | undefined;

  const snapshot = (activity: Activity): SamplerFrame => ({
    text: textarea.value,
    selection_start: textarea.selectionStart,
    selection_end: textarea.selectionEnd,
    is_composing: isComposing,
    input_type: activity === "active" ? inputTypeHint : null,
    activity,
    client_ts: now(),
  });

  const emitActive = (): void => {
    throttleTimer = undefined;
    if (detached || !activePending) {
      return;
    }
    emit(snapshot("active"));
    activePending = false;
    // Input hints describe the active edit they arrived with, never a later
    // cursor-move or paused frame.
    inputTypeHint = null;
  };

  const emitPaused = (): void => {
    pauseTimer = undefined;
    if (detached || pausedEmitted) {
      return;
    }
    // Defaults make this unnecessary, but flushing here preserves the final
    // active state even if a caller supplies pauseMs < samplerThrottleMs.
    if (throttleTimer !== undefined) {
      clearTimeout(throttleTimer);
      emitActive();
    }
    emit(snapshot("paused"));
    pausedEmitted = true;
  };

  const recordActivity = (): void => {
    if (detached) {
      return;
    }
    activePending = true;
    pausedEmitted = false;
    if (throttleTimer === undefined) {
      throttleTimer = setTimeout(emitActive, samplerThrottleMs);
    }
    if (pauseTimer !== undefined) {
      clearTimeout(pauseTimer);
    }
    pauseTimer = setTimeout(emitPaused, pauseMs);
  };

  const onInput = (event: Event): void => {
    const inputType = (event as Event & { inputType?: unknown }).inputType;
    inputTypeHint = typeof inputType === "string" && inputType.length > 0 ? inputType : null;
    recordActivity();
  };
  const onSelectionChange = (): void => {
    // `selectionchange` is document-wide, so only observe the attached control.
    if (document.activeElement === textarea) {
      recordActivity();
    }
  };
  const onCompositionStart = (): void => {
    isComposing = true;
    recordActivity();
  };
  const onCompositionUpdate = (): void => {
    recordActivity();
  };
  const onCompositionEnd = (): void => {
    isComposing = false;
    recordActivity();
  };

  textarea.addEventListener("input", onInput);
  document.addEventListener("selectionchange", onSelectionChange);
  textarea.addEventListener("compositionstart", onCompositionStart);
  textarea.addEventListener("compositionupdate", onCompositionUpdate);
  textarea.addEventListener("compositionend", onCompositionEnd);

  // A session needs a complete first snapshot even before the user edits. It
  // is not a throttled interaction, but it starts the same inactivity window.
  emit(snapshot("active"));
  pauseTimer = setTimeout(emitPaused, pauseMs);

  return (options: { flushPending?: boolean } = {}): void => {
    if (detached) {
      return;
    }
    if (options.flushPending && throttleTimer !== undefined) {
      clearTimeout(throttleTimer);
      emitActive();
    }
    detached = true;
    if (throttleTimer !== undefined) {
      clearTimeout(throttleTimer);
    }
    if (pauseTimer !== undefined) {
      clearTimeout(pauseTimer);
    }
    textarea.removeEventListener("input", onInput);
    document.removeEventListener("selectionchange", onSelectionChange);
    textarea.removeEventListener("compositionstart", onCompositionStart);
    textarea.removeEventListener("compositionupdate", onCompositionUpdate);
    textarea.removeEventListener("compositionend", onCompositionEnd);
  };
}
