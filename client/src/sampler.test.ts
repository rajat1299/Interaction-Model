import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { attachSampler, type SamplerFrame } from "./sampler";

describe("attachSampler", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-07-12T00:00:00.000Z"));
  });

  afterEach(() => {
    vi.useRealTimers();
    document.body.replaceChildren();
  });

  it("emits an initial active snapshot on attach before any user input", () => {
    const textarea = document.createElement("textarea");
    textarea.value = "initial context";
    textarea.setSelectionRange(7, 7);
    document.body.append(textarea);
    const frames: SamplerFrame[] = [];
    const detach = attachSampler(textarea, (frame) => frames.push(frame), {
      sampler_throttle_ms: 100,
      pause_ms: 1_000,
    });

    expect(frames).toEqual([
      expect.objectContaining({
        text: "initial context",
        selection_start: 7,
        selection_end: 7,
        is_composing: false,
        input_type: null,
        activity: "active",
      }),
    ]);
    detach();
  });

  it("trailing-throttles input and emits the latest textarea state", () => {
    const textarea = document.createElement("textarea");
    document.body.append(textarea);
    const frames: SamplerFrame[] = [];
    const detach = attachSampler(textarea, (frame) => frames.push(frame), {
      sampler_throttle_ms: 100,
      pause_ms: 1_000,
    });
    frames.length = 0;

    textarea.value = "a";
    textarea.setSelectionRange(1, 1);
    textarea.dispatchEvent(new InputEvent("input", { inputType: "insertText" }));
    vi.advanceTimersByTime(99);
    expect(frames).toEqual([]);

    textarea.value = "ab";
    textarea.setSelectionRange(2, 2);
    textarea.dispatchEvent(new InputEvent("input", { inputType: "insertText" }));
    vi.advanceTimersByTime(1);

    expect(frames).toEqual([
      expect.objectContaining({
        text: "ab",
        selection_start: 2,
        selection_end: 2,
        is_composing: false,
        input_type: "insertText",
        activity: "active",
      }),
    ]);
    detach();
  });

  it("emits one paused frame after inactivity and re-arms on later input", () => {
    const textarea = document.createElement("textarea");
    document.body.append(textarea);
    const frames: SamplerFrame[] = [];
    const detach = attachSampler(textarea, (frame) => frames.push(frame), {
      sampler_throttle_ms: 100,
      pause_ms: 1_000,
    });
    frames.length = 0;

    textarea.value = "a";
    textarea.setSelectionRange(1, 1);
    textarea.dispatchEvent(new InputEvent("input", { inputType: "insertText" }));
    vi.advanceTimersByTime(1_000);
    vi.advanceTimersByTime(500);

    expect(frames.map((frame) => frame.activity)).toEqual(["active", "paused"]);

    textarea.value = "ab";
    textarea.setSelectionRange(2, 2);
    textarea.dispatchEvent(new InputEvent("input", { inputType: "insertText" }));
    vi.advanceTimersByTime(1_000);

    expect(frames.map((frame) => frame.activity)).toEqual([
      "active",
      "paused",
      "active",
      "paused",
    ]);
    detach();
  });

  it("keeps a paste input hint through selection activity until its active frame", () => {
    const textarea = document.createElement("textarea");
    document.body.append(textarea);
    const frames: SamplerFrame[] = [];
    const detach = attachSampler(textarea, (frame) => frames.push(frame), {
      sampler_throttle_ms: 100,
      pause_ms: 1_000,
    });
    frames.length = 0;

    textarea.focus();
    textarea.value = "pasted";
    textarea.setSelectionRange(6, 6);
    textarea.dispatchEvent(new InputEvent("input", { inputType: "insertFromPaste" }));
    document.dispatchEvent(new Event("selectionchange"));
    vi.advanceTimersByTime(100);

    expect(frames.at(-1)?.input_type).toBe("insertFromPaste");

    document.dispatchEvent(new Event("selectionchange"));
    vi.advanceTimersByTime(100);
    expect(frames.at(-1)?.input_type).toBeNull();
    detach();
  });

  it("keeps a paste hint through intervening selection and composition events", () => {
    const textarea = document.createElement("textarea");
    document.body.append(textarea);
    const frames: SamplerFrame[] = [];
    const detach = attachSampler(textarea, (frame) => frames.push(frame), {
      sampler_throttle_ms: 100,
      pause_ms: 1_000,
    });
    frames.length = 0;

    textarea.focus();
    textarea.value = "pasted";
    textarea.setSelectionRange(6, 6);
    textarea.dispatchEvent(new InputEvent("input", { inputType: "insertFromPaste" }));
    document.dispatchEvent(new Event("selectionchange"));
    textarea.dispatchEvent(new CompositionEvent("compositionstart"));
    textarea.dispatchEvent(new CompositionEvent("compositionupdate"));
    textarea.dispatchEvent(new CompositionEvent("compositionend"));
    vi.advanceTimersByTime(100);

    expect(frames).toEqual([
      expect.objectContaining({ is_composing: false, input_type: "insertFromPaste" }),
    ]);
    detach();
  });

  it("samples explicit IME start, update, and end transitions", () => {
    const textarea = document.createElement("textarea");
    document.body.append(textarea);
    const frames: SamplerFrame[] = [];
    const detach = attachSampler(textarea, (frame) => frames.push(frame), {
      sampler_throttle_ms: 100,
      pause_ms: 1_000,
    });
    frames.length = 0;

    textarea.dispatchEvent(new CompositionEvent("compositionstart"));
    vi.advanceTimersByTime(100);
    textarea.value = "に";
    textarea.setSelectionRange(1, 1);
    textarea.dispatchEvent(new CompositionEvent("compositionupdate"));
    vi.advanceTimersByTime(100);
    textarea.dispatchEvent(new CompositionEvent("compositionend"));
    vi.advanceTimersByTime(100);

    expect(frames.map((frame) => [frame.is_composing, frame.input_type])).toEqual([
      [true, null],
      [true, null],
      [false, null],
    ]);
    detach();
  });

  it("only samples document selection changes while its textarea is focused", () => {
    const textarea = document.createElement("textarea");
    const other = document.createElement("textarea");
    document.body.append(textarea, other);
    const frames: SamplerFrame[] = [];
    const detach = attachSampler(textarea, (frame) => frames.push(frame), {
      sampler_throttle_ms: 100,
      pause_ms: 1_000,
    });
    frames.length = 0;

    other.focus();
    document.dispatchEvent(new Event("selectionchange"));
    vi.advanceTimersByTime(100);
    expect(frames).toEqual([]);

    textarea.value = "select";
    textarea.setSelectionRange(1, 4);
    textarea.focus();
    document.dispatchEvent(new Event("selectionchange"));
    vi.advanceTimersByTime(100);

    expect(frames).toEqual([
      expect.objectContaining({
        text: "select",
        selection_start: 1,
        selection_end: 4,
        input_type: null,
        activity: "active",
      }),
    ]);
    detach();
  });

  it("flushes a final active frame before pause when custom delays overlap", () => {
    const textarea = document.createElement("textarea");
    document.body.append(textarea);
    const frames: SamplerFrame[] = [];
    const detach = attachSampler(textarea, (frame) => frames.push(frame), {
      sampler_throttle_ms: 100,
      pause_ms: 50,
    });
    frames.length = 0;

    textarea.value = "final";
    textarea.setSelectionRange(5, 5);
    textarea.dispatchEvent(new InputEvent("input", { inputType: "insertText" }));
    vi.advanceTimersByTime(50);

    expect(frames.map((frame) => [frame.activity, frame.text, frame.input_type])).toEqual([
      ["active", "final", "insertText"],
      ["paused", "final", null],
    ]);
    detach();
  });

  it("removes all listeners and pending timers when detached", () => {
    const textarea = document.createElement("textarea");
    document.body.append(textarea);
    const frames: SamplerFrame[] = [];
    const detach = attachSampler(textarea, (frame) => frames.push(frame), {
      sampler_throttle_ms: 100,
      pause_ms: 1_000,
    });
    frames.length = 0;

    textarea.value = "before detach";
    textarea.dispatchEvent(new InputEvent("input", { inputType: "insertText" }));
    detach();
    textarea.focus();
    textarea.dispatchEvent(new InputEvent("input", { inputType: "insertText" }));
    document.dispatchEvent(new Event("selectionchange"));
    vi.advanceTimersByTime(2_000);

    expect(frames).toEqual([]);
  });
});
