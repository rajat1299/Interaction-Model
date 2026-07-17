/** Virtual-time execution of the unchanged production textarea sampler. */

import { createInputScriptPlayer, type InputScript, type InputScriptStep, type WaitStep } from "./input-synthesis";
import type { ClientSnapshotFrame } from "./protocol";
import { attachSampler, type SamplerOptions } from "./sampler";

export type SamplerHarnessOptions = Pick<SamplerOptions, "sampler_throttle_ms" | "pause_ms" | "now"> & {
  /** Supplied by Vitest fake timers in Node; no test dependency reaches production code. */
  advanceTimersByTime: (milliseconds: number) => void;
  /** Optional observer for the exact production sampler callback. */
  onFrame?: (frame: ClientSnapshotFrame) => void;
  textarea?: HTMLTextAreaElement;
};

export type SamplerHarness = {
  textarea: HTMLTextAreaElement;
  frames: ClientSnapshotFrame[];
  advance: (milliseconds: number) => void;
  run: (script: InputScript) => void;
  detach: () => void;
};

export type SamplerFrameComparison = {
  equivalent: boolean;
  differences: string[];
};

function assertDelay(milliseconds: number): void {
  if (!Number.isSafeInteger(milliseconds) || milliseconds < 0) {
    throw new RangeError("virtual-time delays must be non-negative integers");
  }
}

function isWait(step: InputScriptStep): step is WaitStep {
  return step.kind === "wait";
}

/**
 * Drive an input script through the exact `attachSampler` import. Callers own
 * fake-timer setup and can advance after a script to observe paused frames.
 */
export function createSamplerHarness(options: SamplerHarnessOptions): SamplerHarness {
  const textarea = options.textarea ?? document.createElement("textarea");
  const ownsTextarea = options.textarea === undefined;
  if (!textarea.isConnected) {
    document.body.append(textarea);
  }
  textarea.focus();

  const frames: ClientSnapshotFrame[] = [];
  const detachSampler = attachSampler(textarea, (frame) => {
    frames.push({ ...frame });
    options.onFrame?.(frame);
  }, {
    sampler_throttle_ms: options.sampler_throttle_ms,
    pause_ms: options.pause_ms,
    now: options.now,
  });
  const player = createInputScriptPlayer(textarea);

  const advance = (milliseconds: number): void => {
    assertDelay(milliseconds);
    options.advanceTimersByTime(milliseconds);
  };

  return {
    textarea,
    frames,
    advance,
    run: (script): void => {
      for (const step of script) {
        if (isWait(step)) {
          advance(step.ms);
        } else {
          player.apply(step);
        }
      }
    },
    detach: (): void => {
      detachSampler();
      if (ownsTextarea) {
        textarea.remove();
      }
    },
  };
}

/**
 * Future browser-equivalence tests supply independently recorded browser
 * frames here. This module deliberately contains no fabricated browser data.
 */
export function compareSamplerFrameSequences(
  expected: readonly ClientSnapshotFrame[],
  actual: readonly ClientSnapshotFrame[],
  timingToleranceMs: number,
): SamplerFrameComparison {
  if (!Number.isFinite(timingToleranceMs) || timingToleranceMs < 0) {
    throw new RangeError("timingToleranceMs must be a non-negative finite number");
  }

  const differences: string[] = [];
  if (expected.length !== actual.length) {
    differences.push(`frame count ${expected.length} != ${actual.length}`);
  }

  const frameCount = Math.min(expected.length, actual.length);
  const expectedOrigin = expected[0]?.client_ts ?? 0;
  const actualOrigin = actual[0]?.client_ts ?? 0;
  for (let index = 0; index < frameCount; index += 1) {
    const left = expected[index]!;
    const right = actual[index]!;
    for (const field of [
      "text",
      "selection_start",
      "selection_end",
      "is_composing",
      "input_type",
      "activity",
    ] as const) {
      if (left[field] !== right[field]) {
        differences.push(`frame ${index} ${field} differs`);
      }
    }
    const timingDelta = Math.abs(
      (left.client_ts - expectedOrigin) - (right.client_ts - actualOrigin),
    );
    if (timingDelta > timingToleranceMs) {
      differences.push(`frame ${index} relative client_ts exceeds ${timingToleranceMs}ms tolerance`);
    }
  }
  return { equivalent: differences.length === 0, differences };
}
