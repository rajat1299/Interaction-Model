import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { CALIBRATION_REGIMES } from "./calibration-recorder";
import {
  CALIBRATED_INPUT_PROFILE,
  FROZEN_BURST_GAP_MS,
} from "./calibrated-input";
import {
  BASELINE_INPUT_PROFILES,
  DEFAULT_INPUT_SYNTHESIS_ENVIRONMENT,
  synthesizeInputScript,
  type SynthesizedInputScript,
} from "./input-synthesis";
import { compareSamplerFrameSequences, createSamplerHarness } from "./sampler-harness";
import type { ClientSnapshotFrame } from "./protocol";

function percentile(values: readonly number[], quantile: number): number {
  const ordered = [...values].sort((left, right) => left - right);
  const position = (ordered.length - 1) * quantile;
  const low = Math.floor(position);
  const high = Math.ceil(position);
  return ordered[low]! + (ordered[high]! - ordered[low]!) * (position - low);
}

describe("sampler harness", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-07-14T00:00:00.000Z"));
  });

  afterEach(() => {
    vi.useRealTimers();
    document.body.replaceChildren();
  });

  it("drives exact sampler throttle and pause behavior under virtual time", () => {
    const harness = createSamplerHarness({
      advanceTimersByTime: vi.advanceTimersByTime,
      sampler_throttle_ms: 10,
      pause_ms: 100,
    });

    harness.run([
      { kind: "insert", text: "a" },
      { kind: "wait", ms: 5 },
      { kind: "insert", text: "b" },
      { kind: "wait", ms: 5 },
      { kind: "wait", ms: 95 },
    ]);

    expect(harness.frames.map((frame) => [frame.activity, frame.text, frame.input_type])).toEqual([
      ["active", "", null],
      ["active", "ab", "insertText"],
      ["paused", "ab", null],
    ]);
    harness.detach();
  });

  it("preserves non-BMP UTF-16 selections through the production sampler", () => {
    const harness = createSamplerHarness({
      advanceTimersByTime: vi.advanceTimersByTime,
      sampler_throttle_ms: 10,
      pause_ms: 100,
    });
    harness.textarea.value = "a😀b";
    harness.run([
      { kind: "selection", start_utf16: 1, end_utf16: 3 },
      { kind: "wait", ms: 10 },
    ]);

    expect(harness.frames.at(-1)).toMatchObject({
      text: "a😀b",
      selection_start: 1,
      selection_end: 3,
      input_type: null,
      activity: "active",
    });
    harness.detach();
  });

  it("drives composition lifecycle frames through the unmodified sampler", () => {
    const harness = createSamplerHarness({
      advanceTimersByTime: vi.advanceTimersByTime,
      sampler_throttle_ms: 10,
      pause_ms: 100,
    });

    harness.run([
      { kind: "compositionstart" },
      { kind: "wait", ms: 10 },
      { kind: "compositionupdate", text: "に" },
      { kind: "wait", ms: 10 },
      { kind: "compositioncommit", text: "日" },
      { kind: "wait", ms: 10 },
    ]);

    expect(harness.frames.slice(1).map((frame) => [frame.text, frame.is_composing, frame.input_type])).toEqual([
      ["", true, null],
      ["に", true, "insertCompositionText"],
      ["日", false, "insertCompositionText"],
    ]);
    harness.detach();
  });

  it("guarantees generated IME visibility at the configured production throttle", () => {
    const assertVisible = (
      script: SynthesizedInputScript,
      samplerThrottleMs: number,
      useSamplerDefault = false,
    ): void => {
      const compositionStart = script.steps.findIndex(
        (step) => step.kind === "compositionstart",
      );
      expect(script.steps[compositionStart + 1]).toMatchObject({
        kind: "wait",
        role: "composition",
        ms: expect.any(Number),
      });
      expect((script.steps[compositionStart + 1] as { ms: number }).ms).toBeGreaterThanOrEqual(
        samplerThrottleMs,
      );
      const harness = createSamplerHarness({
        advanceTimersByTime: vi.advanceTimersByTime,
        ...(useSamplerDefault ? {} : { sampler_throttle_ms: samplerThrottleMs }),
        pause_ms: 5_000,
      });

      harness.run(script.steps);
      harness.advance(samplerThrottleMs);

      const composingIndex = harness.frames.findIndex((frame) => frame.is_composing);
      const ordinaryIndex = harness.frames.findIndex(
        (frame, index) =>
          index > composingIndex &&
          !frame.is_composing &&
          frame.input_type === "insertText" &&
          frame.text === "😀x",
      );
      expect(composingIndex).toBeGreaterThan(-1);
      expect(ordinaryIndex).toBeGreaterThan(composingIndex);
      harness.detach();
    };

    for (const regime of CALIBRATION_REGIMES) {
      for (let seed = 0; seed < 8; seed += 1) {
        const script = synthesizeInputScript(
          "😀x",
          seed,
          regime,
          {
            ...BASELINE_INPUT_PROFILES[regime],
            chars_per_burst: [20, 20],
            within_burst_ms: [1, 20],
            between_burst_ms: [1, 20],
            hesitation_probability: 0,
            revision_probability: 0,
            cursor_move_probability: 1,
            paste_probability: 0,
            composition_probability: 1,
            composition_cancel_probability: seed % 2,
          },
        );
        expect(script.environment).toEqual(DEFAULT_INPUT_SYNTHESIS_ENVIRONMENT);
        assertVisible(
          script,
          DEFAULT_INPUT_SYNTHESIS_ENVIRONMENT.sampler_throttle_ms,
          true,
        );
      }
    }

    const customThrottle = 250;
    const custom = synthesizeInputScript(
      "😀x",
      99,
      "natural-drafting",
      {
        ...BASELINE_INPUT_PROFILES["natural-drafting"],
        within_burst_ms: [1, 20],
        hesitation_probability: 0,
        revision_probability: 0,
        cursor_move_probability: 0,
        paste_probability: 0,
        composition_probability: 1,
      },
      { sampler_throttle_ms: customThrottle },
    );
    expect(custom.environment.sampler_throttle_ms).toBe(customThrottle);
    assertVisible(custom, customThrottle);
  });

  it("coalesces calibrated typing into two-character sampler deltas without crossing burst boundaries", () => {
    const deltas: number[] = [];
    for (const regime of ["copied-or-scripted-typing", "pauses-and-resumptions"] as const) {
      for (let seed = 0; seed < 8; seed += 1) {
        const harness = createSamplerHarness({
          advanceTimersByTime: vi.advanceTimersByTime,
          sampler_throttle_ms: 100,
          pause_ms: 1_500,
        });
        harness.run(synthesizeInputScript("A compact sampler cadence target.", seed, regime).steps);
        harness.advance(1_500);
        for (let index = 1; index < harness.frames.length; index += 1) {
          deltas.push(harness.frames[index]!.text.length - harness.frames[index - 1]!.text.length);
        }
        harness.detach();
      }
    }

    expect(percentile(deltas, 0.9)).toBe(2);
    for (const regime of CALIBRATION_REGIMES) {
      const profile = CALIBRATED_INPUT_PROFILE.regimes[regime];
      expect(profile.within_burst_gap_ms.every((milliseconds) => milliseconds < FROZEN_BURST_GAP_MS[regime])).toBe(true);
      expect(profile.between_burst_gap_ms.every((milliseconds) => milliseconds >= FROZEN_BURST_GAP_MS[regime])).toBe(true);
    }
  });

  it("compares future browser fixtures at an explicit timing tolerance boundary", () => {
    const frame: ClientSnapshotFrame = {
      text: "same",
      selection_start: 4,
      selection_end: 4,
      is_composing: false,
      input_type: "insertText",
      activity: "active",
      client_ts: 100,
    };
    const later = { ...frame, text: "same later", client_ts: 200 };
    const shifted = { ...frame, client_ts: 1_000 };
    const shiftedLater = { ...later, client_ts: 1_112 };

    expect(compareSamplerFrameSequences([frame, later], [shifted, shiftedLater], 12)).toEqual({
      equivalent: true,
      differences: [],
    });
    expect(compareSamplerFrameSequences([frame, later], [shifted, shiftedLater], 11)).toEqual({
      equivalent: false,
      differences: ["frame 1 relative client_ts exceeds 11ms tolerance"],
    });
    expect(compareSamplerFrameSequences([frame], [{ ...shifted, text: "different" }], 12).equivalent).toBe(
      false,
    );
  });
});
