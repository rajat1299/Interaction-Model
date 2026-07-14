import { afterEach, describe, expect, it, vi } from "vitest";

import {
  CALIBRATION_RECORDING_VERSION,
  attachCalibrationRecorder,
  type CalibrationRecorder,
} from "./calibration-recorder";
import type { ClientSnapshotFrame } from "./protocol";
import { attachSampler } from "./sampler";

function attach(textarea: HTMLTextAreaElement, now: () => number): CalibrationRecorder {
  return attachCalibrationRecorder(textarea, {
    version: CALIBRATION_RECORDING_VERSION,
    runtime_session_id: "session-test-001",
    regime: "natural-drafting",
    now,
  });
}

function samplerFrame(overrides: Partial<ClientSnapshotFrame> = {}): ClientSnapshotFrame {
  return {
    text: "draft",
    selection_start: 5,
    selection_end: 5,
    is_composing: false,
    input_type: "insertText",
    activity: "active",
    client_ts: 1_000,
    ...overrides,
  };
}

describe("attachCalibrationRecorder", () => {
  afterEach(() => {
    vi.useRealTimers();
    document.body.replaceChildren();
  });

  it("captures raw input data, text, and UTF-16 textarea selection", () => {
    let time = 100;
    const textarea = document.createElement("textarea");
    document.body.append(textarea);
    const recorder = attach(textarea, () => time);

    time = 125;
    textarea.value = "x😀";
    textarea.setSelectionRange(1, 3);
    textarea.dispatchEvent(new InputEvent("input", { inputType: "insertText", data: "😀" }));

    expect(recorder.exportBundle().raw_events).toEqual([
      {
        ordinal: 1,
        relative_ms: 25,
        kind: "input",
        input_type: "insertText",
        data: "😀",
        text: "x😀",
        selection_start: 1,
        selection_end: 3,
        is_composing: false,
      },
    ]);
    recorder.detach();
  });

  it("captures focused document selection changes only", () => {
    let time = 0;
    const textarea = document.createElement("textarea");
    const other = document.createElement("textarea");
    document.body.append(textarea, other);
    const recorder = attach(textarea, () => time);

    other.focus();
    document.dispatchEvent(new Event("selectionchange"));

    time = 20;
    textarea.value = "a😀b";
    textarea.setSelectionRange(1, 3);
    textarea.focus();
    document.dispatchEvent(new Event("selectionchange"));

    expect(recorder.exportBundle().raw_events).toEqual([
      expect.objectContaining({
        ordinal: 1,
        relative_ms: 20,
        kind: "selectionchange",
        input_type: null,
        data: null,
        selection_start: 1,
        selection_end: 3,
      }),
    ]);
    recorder.detach();
  });

  it("captures composition start, update, and end with lifecycle state", () => {
    let time = 0;
    const textarea = document.createElement("textarea");
    document.body.append(textarea);
    const recorder = attach(textarea, () => time);

    time = 10;
    textarea.dispatchEvent(new CompositionEvent("compositionstart", { data: "a" }));
    time = 20;
    textarea.value = "あ";
    textarea.setSelectionRange(1, 1);
    textarea.dispatchEvent(new CompositionEvent("compositionupdate", { data: "あ" }));
    time = 30;
    textarea.dispatchEvent(new CompositionEvent("compositionend", { data: "あ" }));

    expect(recorder.exportBundle().raw_events.map((event) => [event.kind, event.data, event.is_composing])).toEqual([
      ["compositionstart", "a", true],
      ["compositionupdate", "あ", true],
      ["compositionend", "あ", false],
    ]);
    recorder.detach();
  });

  it("captures cloned sampler frames with global capture ordinals", () => {
    let time = 50;
    const textarea = document.createElement("textarea");
    document.body.append(textarea);
    const recorder = attach(textarea, () => time);
    const emitted = samplerFrame();

    time = 60;
    recorder.captureSamplerFrame(emitted);
    emitted.text = "changed after emission";
    time = 90;
    recorder.captureSamplerFrame(samplerFrame({ text: "next", client_ts: 1_030 }));

    expect(recorder.exportBundle().sampler_frames).toEqual([
      expect.objectContaining({
        ordinal: 1,
        relative_ms: 10,
        frame: expect.objectContaining({ text: "draft", client_ts: 1_000 }),
      }),
      expect.objectContaining({
        ordinal: 2,
        relative_ms: 40,
        frame: expect.objectContaining({ text: "next", client_ts: 1_030 }),
      }),
    ]);
    recorder.detach();
  });

  it("captures frames emitted by the unmodified production sampler", () => {
    vi.useFakeTimers();
    let time = 0;
    const textarea = document.createElement("textarea");
    document.body.append(textarea);
    const recorder = attach(textarea, () => time);
    const detachSampler = attachSampler(textarea, recorder.captureSamplerFrame, {
      sampler_throttle_ms: 10,
      pause_ms: 100,
      now: () => time,
    });

    time = 10;
    textarea.value = "typed";
    textarea.setSelectionRange(5, 5);
    textarea.dispatchEvent(new InputEvent("input", { inputType: "insertText", data: "d" }));
    time = 20;
    vi.advanceTimersByTime(10);

    expect(recorder.exportBundle().sampler_frames).toEqual([
      expect.objectContaining({
        ordinal: 1,
        relative_ms: 0,
        frame: expect.objectContaining({ text: "", activity: "active", client_ts: 0 }),
      }),
      expect.objectContaining({
        ordinal: 3,
        relative_ms: 20,
        frame: expect.objectContaining({
          text: "typed",
          selection_start: 5,
          selection_end: 5,
          input_type: "insertText",
          client_ts: 20,
        }),
      }),
    ]);
    detachSampler();
    recorder.detach();
  });

  it("exports joinable, globally ordered, fresh JSON-safe bundles", () => {
    let time = 1_000;
    const textarea = document.createElement("textarea");
    document.body.append(textarea);
    const recorder = attach(textarea, () => time);

    time = 1_020;
    textarea.value = "first";
    textarea.dispatchEvent(new InputEvent("input", { inputType: "insertText", data: "t" }));
    time = 1_030;
    recorder.captureSamplerFrame(samplerFrame({ text: "first" }));

    const first = recorder.exportBundle();
    const second = recorder.exportBundle();
    first.raw_events[0]!.text = "mutated export";

    expect(second.runtime_session_id).toBe("session-test-001");
    expect(second.raw_events.map((event) => [event.ordinal, event.relative_ms])).toEqual([[1, 20]]);
    expect(second.sampler_frames.map((frame) => [frame.ordinal, frame.relative_ms])).toEqual([[2, 30]]);
    expect(recorder.exportBundle().raw_events[0]!.text).toBe("first");
    expect(JSON.parse(JSON.stringify(second))).toEqual(second);
    recorder.detach();
  });

  it("rejects a clock that regresses instead of distorting recorded timing", () => {
    let time = 1_000;
    const textarea = document.createElement("textarea");
    document.body.append(textarea);
    const recorder = attach(textarea, () => time);

    time = 1_020;
    recorder.captureSamplerFrame(samplerFrame());
    time = 1_010;

    expect(() => recorder.captureSamplerFrame(samplerFrame())).toThrow(RangeError);
    recorder.detach();
  });

  it("removes event listeners and ignores sampler frames after detach", () => {
    let time = 0;
    const textarea = document.createElement("textarea");
    document.body.append(textarea);
    const recorder = attach(textarea, () => time);

    textarea.value = "before detach";
    textarea.dispatchEvent(new InputEvent("input", { inputType: "insertText" }));
    recorder.detach();
    time = 10;
    textarea.value = "after detach";
    textarea.focus();
    textarea.dispatchEvent(new InputEvent("input", { inputType: "insertText" }));
    document.dispatchEvent(new Event("selectionchange"));
    textarea.dispatchEvent(new CompositionEvent("compositionstart"));
    recorder.captureSamplerFrame(samplerFrame({ text: "after detach" }));

    const bundle = recorder.exportBundle();
    expect(bundle.raw_events).toHaveLength(1);
    expect(bundle.raw_events[0]!.text).toBe("before detach");
    expect(bundle.sampler_frames).toEqual([]);
  });

  it("rejects unrecognized closed regime and version inputs", () => {
    const textarea = document.createElement("textarea");

    expect(() =>
      attachCalibrationRecorder(textarea, {
        version: CALIBRATION_RECORDING_VERSION,
        runtime_session_id: "session-test-001",
        regime: "freeform" as never,
      }),
    ).toThrow(RangeError);
    expect(() =>
      attachCalibrationRecorder(textarea, {
        version: "calibration-recording/v2" as never,
        runtime_session_id: "session-test-001",
        regime: "natural-drafting",
      }),
    ).toThrow(RangeError);
    expect(() =>
      attachCalibrationRecorder(textarea, {
        version: CALIBRATION_RECORDING_VERSION,
        runtime_session_id: " ",
        regime: "natural-drafting",
      }),
    ).toThrow(RangeError);
  });
});
