import { afterEach, describe, expect, it, vi } from "vitest";

import { CALIBRATION_REGIMES } from "./calibration-recorder";
import {
  CALIBRATION_SYNTHETIC_REQUEST_VERSION,
  CALIBRATION_SYNTHETIC_RESPONSE_VERSION,
  CALIBRATION_SYNTHETIC_MAX_BATCH_RECORDS,
  materializeCalibrationSyntheticBatch,
  materializeCalibrationSynthetic,
  parseCalibrationSyntheticBatchRequest,
  parseCalibrationSyntheticRequest,
  type CalibrationSyntheticBatchRequest,
  type CalibrationSyntheticRequest,
} from "./calibration-synthetic";

const request: CalibrationSyntheticRequest = {
  runtime_session_id: "synthetic-session-001",
  regime: "revision-heavy-writing",
  seed: "seed-001",
  timing_split: "train",
  target_text: "Draft café 😀, then revise.",
  transient_texts: [],
  input_profile_id: "phase1-d3-calibrated-v1",
  input_profile_sha256: "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  materializer_sha256: "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
  target_source_sha256: "sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
};

function materialize(value: CalibrationSyntheticRequest) {
  vi.useFakeTimers();
  vi.setSystemTime(0);
  return materializeCalibrationSynthetic(value, {
    now: Date.now,
    advanceTimersByTime: vi.advanceTimersByTime,
  });
}

function materializeBatch(value: CalibrationSyntheticBatchRequest) {
  vi.useFakeTimers();
  return materializeCalibrationSyntheticBatch(value, {
    now: Date.now,
    advanceTimersByTime: vi.advanceTimersByTime,
    reset: () => vi.setSystemTime(0),
  });
}

function deleteBackwardRuns(bundle: ReturnType<typeof materialize>): number[] {
  const runs: number[] = [];
  let length = 0;
  for (const event of bundle.bundle.raw_events.filter((event) => event.kind === "input")) {
    if (event.input_type === "deleteContentBackward") {
      length += 1;
    } else if (length > 0) {
      runs.push(length);
      length = 0;
    }
  }
  if (length > 0) {
    runs.push(length);
  }
  return runs;
}

afterEach(() => {
  vi.useRealTimers();
  document.body.replaceChildren();
});

describe("synthetic calibration materializer", () => {
  it("emits a dense recorder bundle ending at the synthesized target's paused frame", () => {
    const bundle = materialize(request);
    const captures = [...bundle.bundle.raw_events, ...bundle.bundle.sampler_frames]
      .sort((left, right) => left.ordinal - right.ordinal);
    const finalFrame = bundle.bundle.sampler_frames.at(-1)?.frame;

    expect(bundle.bundle).toMatchObject({
      version: "calibration-recording/v1",
      runtime_session_id: request.runtime_session_id,
      regime: request.regime,
    });
    expect(Object.keys(bundle.bundle).sort()).toEqual([
      "raw_events",
      "recording_duration_ms",
      "regime",
      "runtime_session_id",
      "sampler_frames",
      "version",
    ]);
    expect(captures.map((capture) => capture.ordinal)).toEqual(
      Array.from({ length: captures.length }, (_, index) => index + 1),
    );
    expect(captures.map((capture) => capture.relative_ms)).toEqual(
      [...captures].map((capture) => capture.relative_ms).sort((left, right) => left - right),
    );
    expect(finalFrame).toMatchObject({
      text: request.target_text,
      activity: "paused",
      is_composing: false,
    });
    expect(bundle.bundle.recording_duration_ms).toBeGreaterThanOrEqual(
      bundle.bundle.sampler_frames.at(-1)!.relative_ms,
    );
    expect(bundle.timing).toMatchObject({
      split: "train",
      seed_id: "timing/train/string:seed-001",
      revision: {
        immediate_count: expect.any(Number),
        look_back_count: expect.any(Number),
        look_back_input_ordinal_ranges: expect.any(Array),
      },
    });
    const ranges = bundle.timing.revision.look_back_input_ordinal_ranges;
    expect(ranges).toHaveLength(bundle.timing.revision.look_back_count);
    const inputs = bundle.bundle.raw_events.filter((event) => event.kind === "input");
    for (const [index, range] of ranges.entries()) {
      const admitted = inputs.filter(
        (event) => event.ordinal >= range.start_ordinal && event.ordinal <= range.end_ordinal,
      );
      expect(admitted.length).toBeGreaterThan(0);
      expect(admitted[0]!.input_type).toBe("deleteContentBackward");
      expect(admitted.at(-1)!.input_type).toBe("insertText");
      if (index > 0) {
        expect(range.start_ordinal).toBeGreaterThan(ranges[index - 1]!.end_ordinal);
      }
    }
  });

  it("is reproducible and reaches the requested final text in every regime", () => {
    expect(materialize(request)).toEqual(materialize(request));

    for (const [index, regime] of CALIBRATION_REGIMES.entries()) {
      const targetText = `Regime ${index}: café 😀`;
      const bundle = materialize({ ...request, regime, seed: index, target_text: targetText });
      expect(bundle.bundle.sampler_frames.at(-1)?.frame).toMatchObject({
        text: targetText,
        activity: "paused",
      });
    }
  });

  it("declares only genuine line-distance look-backs and reclassifies unsupported ones", () => {
    const targetText = Array.from(
      { length: 36 },
      (_, index) => `line ${String(index).padStart(2, "0")} carries a stable correction target`,
    ).join("\n");
    const materialized = materialize({
      ...request,
      seed: "genuine-look-backs",
      target_text: targetText,
    });
    const { revision } = materialized.timing;
    expect(revision.immediate_count).toBeGreaterThan(revision.look_back_count);
    expect(revision.look_back_count).toBeGreaterThan(0);

    const events = materialized.bundle.raw_events;
    const lineAt = (offset: number): number => [...targetText.slice(0, offset)]
      .filter((character) => character === "\n").length;
    const signedMovements = revision.look_back_input_ordinal_ranges.map(({ start_ordinal }) => {
      const inputIndex = events.findIndex((event) => event.ordinal === start_ordinal);
      const selected = events[inputIndex - 1]!;
      const previous = events
        .slice(0, inputIndex - 1)
        .reverse()
        .find((event) => event.kind === "selectionchange")!;
      expect(selected.kind).toBe("selectionchange");
      return lineAt(selected.selection_start) - lineAt(previous.selection_start);
    });
    const movements = signedMovements.map(Math.abs);
    expect(movements.every((lines) => lines >= 8)).toBe(true);
    expect(movements.every((lines) => [8, 12, 16].includes(lines))).toBe(true);
    expect(signedMovements.some((lines) => lines < 0)).toBe(true);
    expect(signedMovements.some((lines) => lines > 0)).toBe(true);

    const singleLine = materialize({
      ...request,
      seed: "unsupported-look-backs",
      target_text: "a single line has no configured line-distance look-back location",
    });
    expect(singleLine.timing.revision.look_back_count).toBe(0);
    expect(singleLine.timing.revision.look_back_input_ordinal_ranges).toEqual([]);
  });

  it("keeps cursor variants visible to the sampler while preserving raw input and selection totals", () => {
    const targetText = "x".repeat(416);
    const bundle = materialize({
      ...request,
      regime: "cursor-and-selection-edits",
      seed: "cursor-variant-a",
      target_text: targetText,
    });
    const inputs = bundle.bundle.raw_events.filter((event) => event.kind === "input");
    const selections = bundle.bundle.raw_events.filter((event) => event.kind === "selectionchange");
    const extraSelections = selections.length - inputs.length;
    const targetFrames = bundle.bundle.sampler_frames
      .map((record) => record.frame)
      .filter((frame) => frame.text === targetText && frame.activity === "active");

    expect([[124, 121], [175, 244]]).toContainEqual([inputs.length, extraSelections]);
    expect(new Set(targetFrames.map((frame) => frame.selection_start)).size).toBeGreaterThan(20);
  });

  it("materializes frozen revision and cursor backspace runs", () => {
    const targetText = "x".repeat(416);
    const expectations = [
      ["revision-heavy-writing", [1, 1, 1, 1, 1, 1, 1, 2, 2, 2, 3, 4, 4, 4, 4, 5, 7, 7, 7, 11, 23, 29]],
      ["cursor-and-selection-edits", [...Array(16).fill(1), 2, 3, 4, 6]],
    ] as const;

    for (const [regime, expectedRuns] of expectations) {
      const runs = deleteBackwardRuns(materialize({
        ...request,
        regime,
        seed: `${regime}-backspaces`,
        target_text: targetText,
      }));
      expect(runs.slice(-expectedRuns.length)).toEqual(expectedRuns);
    }
  });

  it("uses six supplied short transients, long suffix backspaces, and restores the target", () => {
    const targetText = "final command has exactly forty two chars!!!!".slice(0, 42);
    const transientTexts = ["draft one", "draft two", "draft three", "draft four", "draft five", "draft six"];
    const bundle = materialize({
      ...request,
      regime: "short-command-like-inputs",
      seed: "short-transients",
      target_text: targetText,
      transient_texts: transientTexts,
    });
    const inputs = bundle.bundle.raw_events.filter((event) => event.kind === "input");
    const deletes = inputs.filter((event) => event.input_type === "deleteContentBackward");
    const explicitSelections = bundle.bundle.raw_events.filter((event) => event.kind === "selectionchange").length - inputs.length;

    expect(deletes.length).toBeGreaterThanOrEqual(121 + transientTexts.length);
    expect(explicitSelections).toBe(143);
    expect(bundle.bundle.sampler_frames.at(-1)?.frame).toMatchObject({ text: targetText, activity: "paused" });
  });

  it("accepts only the request object's JSON-safe shape", () => {
    expect(parseCalibrationSyntheticRequest(request)).toEqual(request);
    expect(() => parseCalibrationSyntheticRequest({ ...request, extra: true })).toThrow(RangeError);
    expect(() => parseCalibrationSyntheticRequest({ ...request, regime: "freeform" })).toThrow(RangeError);
    expect(() => parseCalibrationSyntheticRequest({ ...request, seed: Number.NaN })).toThrow(RangeError);
    expect(() => parseCalibrationSyntheticRequest({ ...request, timing_split: "preview" })).toThrow(RangeError);
    expect(() => parseCalibrationSyntheticRequest({ ...request, transient_texts: ["same", "same"] })).toThrow(RangeError);
    expect(() => parseCalibrationSyntheticRequest({ ...request, input_profile_sha256: "not-a-digest" })).toThrow(RangeError);
    expect(() => parseCalibrationSyntheticRequest({
      ...request,
      regime: "short-command-like-inputs",
      transient_texts: ["draft", "draft two", "draft three", "draft four", "draft five"],
    })).toThrow(RangeError);
  });

  it("materializes an ordered batch with unique session IDs", () => {
    const batch: CalibrationSyntheticBatchRequest = {
      format_version: CALIBRATION_SYNTHETIC_REQUEST_VERSION,
      records: [
        request,
        {
          ...request,
          runtime_session_id: "synthetic-session-002",
          regime: "pauses-and-resumptions",
          seed: "seed-002",
          target_text: "A second independent trace.",
        },
      ],
    };
    const response = materializeBatch(batch);

    expect(response).toEqual(materializeBatch(batch));
    expect(response.format_version).toBe(CALIBRATION_SYNTHETIC_RESPONSE_VERSION);
    expect(response.input_profile_id).toBe("phase1-d3-calibrated-v1");
    expect(response.input_profile_sha256).toBe(batch.records[0]!.input_profile_sha256);
    expect(response.materializer_sha256).toBe(batch.records[0]!.materializer_sha256);
    expect(Object.keys(response).sort()).toEqual([
      "format_version",
      "input_profile_id",
      "input_profile_sha256",
      "materializer_sha256",
      "records",
    ]);
    expect(response.records.map(({ bundle }) => bundle.runtime_session_id)).toEqual(
      batch.records.map((record) => record.runtime_session_id),
    );
    expect(response.records.map(({ bundle }) => bundle.sampler_frames.at(-1)?.frame.text)).toEqual(
      batch.records.map((record) => record.target_text),
    );
    expect(response.records.map(({ timing }) => timing.split)).toEqual(["train", "train"]);
    expect(parseCalibrationSyntheticBatchRequest(batch)).toEqual(batch);
    expect(() => parseCalibrationSyntheticBatchRequest({ ...batch, records: [] })).toThrow(RangeError);
    expect(() =>
      parseCalibrationSyntheticBatchRequest({ ...batch, records: [request, request] }),
    ).toThrow(RangeError);
    expect(() => parseCalibrationSyntheticBatchRequest({
      ...batch,
      records: [request, { ...request, runtime_session_id: "synthetic-session-003", materializer_sha256: "sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd" }],
    })).toThrow(RangeError);
    expect(() => parseCalibrationSyntheticBatchRequest({ ...batch, extra: true })).toThrow(RangeError);
    expect(() => parseCalibrationSyntheticBatchRequest({
      ...batch,
      records: Array.from({ length: CALIBRATION_SYNTHETIC_MAX_BATCH_RECORDS + 1 }, (_, index) => ({
        ...request,
        runtime_session_id: `synthetic-session-${index}`,
      })),
    })).toThrow(RangeError);
  });
});

const environment = (globalThis as typeof globalThis & {
  process?: { env?: Record<string, string | undefined> };
}).process?.env;
const requestPath = environment?.CALIBRATION_SYNTHETIC_REQUEST_PATH;
const outputPath = environment?.CALIBRATION_SYNTHETIC_OUTPUT_PATH;

if (requestPath !== undefined || outputPath !== undefined) {
  describe("synthetic calibration file adapter", () => {
    it("writes one materialized batch response when both paths are explicitly supplied", async () => {
      if (!requestPath || !outputPath) {
        throw new Error(
          "CALIBRATION_SYNTHETIC_REQUEST_PATH and CALIBRATION_SYNTHETIC_OUTPUT_PATH are both required",
        );
      }
      const { readFileSync, renameSync, writeFileSync } = await import("node:" + "fs");
      const parsed = parseCalibrationSyntheticBatchRequest(
        JSON.parse(readFileSync(requestPath, "utf8")),
      );
      const temporaryOutputPath = `${outputPath}.tmp`;
      writeFileSync(temporaryOutputPath, `${JSON.stringify(materializeBatch(parsed))}\n`, "utf8");
      renameSync(temporaryOutputPath, outputPath);
    });
  });
}
