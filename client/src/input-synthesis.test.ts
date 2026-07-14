import { afterEach, describe, expect, it } from "vitest";

import { CALIBRATION_REGIMES, type CalibrationRegime } from "./calibration-recorder";
import {
  BASELINE_INPUT_PROFILES,
  DEFAULT_INPUT_SYNTHESIS_ENVIRONMENT,
  createInputScriptState,
  createInputScriptPlayer,
  createNamedInputRng,
  summarizeInputScript,
  synthesizeInputScript,
  transitionInputScriptState,
  type InputActionStep,
  type InputScript,
  type InputScriptSummary,
  type InputSynthesisProfile,
} from "./input-synthesis";

function applyScriptResult(script: InputScript): {
  text: string;
  selection_start_utf16: number;
  selection_end_utf16: number;
} {
  const textarea = document.createElement("textarea");
  document.body.append(textarea);
  const player = createInputScriptPlayer(textarea);
  for (const step of script) {
    if (step.kind !== "wait") {
      player.apply(step);
    }
  }
  return {
    text: textarea.value,
    selection_start_utf16: textarea.selectionStart,
    selection_end_utf16: textarea.selectionEnd,
  };
}

function applyScript(script: InputScript): string {
  return applyScriptResult(script).text;
}

function applyGeneratedScript(regime: CalibrationRegime, seed: number): string {
  const target = "Draft café 😀, then revise.";
  const generated = synthesizeInputScript(target, seed, regime);
  return applyScript(generated.steps);
}

function aggregate(regime: CalibrationRegime): InputScriptSummary {
  const total: InputScriptSummary = {
    waits: 0,
    wait_ms: 0,
    inserts: 0,
    deletes: 0,
    selections: 0,
    pastes: 0,
    compositions: 0,
    burst_lengths: [],
    burst_durations_ms: [],
    delete_run_lengths: [],
    delete_locality_utf16: [],
    cursor_travel_utf16: [],
    selection_lengths_utf16: [],
    paste_lengths_utf16: [],
    ime_update_counts: [],
  };
  const target = "A measured café 😀 paragraph, with e\u0301 punctuation, supports stable structural checks.";
  for (let seed = 0; seed < 200; seed += 1) {
    const summary = summarizeInputScript(
      synthesizeInputScript(target, seed, regime).steps,
    );
    for (const key of [
      "waits",
      "wait_ms",
      "inserts",
      "deletes",
      "selections",
      "pastes",
      "compositions",
    ] as const) {
      total[key] += summary[key];
    }
    for (const key of [
      "burst_lengths",
      "burst_durations_ms",
      "delete_run_lengths",
      "delete_locality_utf16",
      "cursor_travel_utf16",
      "selection_lengths_utf16",
      "paste_lengths_utf16",
      "ime_update_counts",
    ] as const) {
      total[key].push(...summary[key]);
    }
  }
  return total;
}

function forcedProfile(overrides: Partial<InputSynthesisProfile>): InputSynthesisProfile {
  return { ...BASELINE_INPUT_PROFILES["natural-drafting"], ...overrides };
}

function mean(values: readonly number[]): number {
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

describe("input synthesis", () => {
  afterEach(() => {
    document.body.replaceChildren();
  });

  it("emits forced between-burst waits from explicit burst state", () => {
    const script = synthesizeInputScript(
      "abcd",
      1,
      "natural-drafting",
      forcedProfile({
        chars_per_burst: [1, 1],
        within_burst_ms: [3, 3],
        between_burst_ms: [11, 11],
        punctuation_pause_ms: [5, 5],
        hesitation_probability: 0,
        revision_probability: 0,
        cursor_move_probability: 0,
        paste_probability: 0,
        composition_probability: 0,
      }),
    );

    expect(script.steps.filter((step) => step.kind === "wait")).toEqual([
      { kind: "wait", ms: 11, role: "between-burst" },
      { kind: "wait", ms: 11, role: "between-burst" },
      { kind: "wait", ms: 11, role: "between-burst" },
    ]);
    expect(summarizeInputScript(script.steps).burst_lengths).toEqual([1, 1, 1, 1]);
  });

  it("keeps named RNG substreams independent", () => {
    const baseline = createNamedInputRng(42);
    const baselineTiming = [baseline.next("timing"), baseline.next("timing")];
    const withOtherDraws = createNamedInputRng(42);

    withOtherDraws.next("revision");
    withOtherDraws.next("revision");
    withOtherDraws.next("composition");

    expect([withOtherDraws.next("timing"), withOtherDraws.next("timing")]).toEqual(baselineTiming);
  });

  it("domain-separates seed types and hashes every non-BMP code unit", () => {
    const samples = (seed: string | number): number[] => {
      const rng = createNamedInputRng(seed);
      return [rng.next("timing"), rng.next("timing"), rng.next("timing")];
    };

    expect(samples("😀")).toEqual(samples("😀"));
    expect(samples("😀")).not.toEqual(samples("😁"));
    expect(samples("42")).not.toEqual(samples(42));
  });

  it("applies selection, paste, delete, and non-BMP UTF-16 offsets", () => {
    const textarea = document.createElement("textarea");
    textarea.value = "a😀b";
    document.body.append(textarea);
    const player = createInputScriptPlayer(textarea);

    player.apply({ kind: "selection", start_utf16: 1, end_utf16: 3 });
    player.apply({ kind: "paste", text: "XY" });
    player.apply({ kind: "selection", start_utf16: 1, end_utf16: 3 });
    player.apply({ kind: "delete" });

    expect(textarea.value).toBe("ab");
    expect([textarea.selectionStart, textarea.selectionEnd]).toEqual([1, 1]);

    textarea.value = "a😀b";
    textarea.setSelectionRange(3, 3);
    player.apply({ kind: "delete" });
    expect(textarea.value).toBe("ab");

    textarea.value = "a😀b";
    textarea.setSelectionRange(1, 1);
    player.apply({ kind: "delete", input_type: "deleteContentForward" });
    expect(textarea.value).toBe("ab");
  });

  it("rejects mid-surrogate cursor and deletion offsets without mutation", () => {
    const textarea = document.createElement("textarea");
    textarea.value = "a😀b";
    document.body.append(textarea);
    const player = createInputScriptPlayer(textarea);

    expect(() =>
      player.apply({ kind: "selection", start_utf16: 2, end_utf16: 2 }),
    ).toThrow(RangeError);
    expect(textarea.value).toBe("a😀b");

    textarea.setSelectionRange(2, 2);
    expect(() => player.apply({ kind: "delete" })).toThrow(RangeError);
    expect(textarea.value).toBe("a😀b");

    textarea.setSelectionRange(2, 2);
    expect(() =>
      player.apply({ kind: "delete", input_type: "deleteContentForward" }),
    ).toThrow(RangeError);
    expect(textarea.value).toBe("a😀b");
  });

  it("commits and cancels generic composition replacements", () => {
    const textarea = document.createElement("textarea");
    textarea.value = "a😀b";
    textarea.setSelectionRange(1, 3);
    document.body.append(textarea);
    const player = createInputScriptPlayer(textarea);

    player.apply({ kind: "compositionstart" });
    player.apply({ kind: "compositionupdate", text: "に" });
    player.apply({ kind: "compositioncommit", text: "日" });
    expect(textarea.value).toBe("a日b");
    textarea.setSelectionRange(1, 2);
    player.apply({ kind: "compositionstart" });
    player.apply({ kind: "compositionupdate", text: "本語" });
    player.apply({ kind: "compositioncancel" });

    expect(textarea.value).toBe("a日b");
    expect([textarea.selectionStart, textarea.selectionEnd]).toEqual([1, 2]);
  });

  it("keeps reducer, summary, and DOM player invalid-sequence errors in parity", () => {
    const errorOf = (operation: () => unknown): { name: string; message: string } | null => {
      try {
        operation();
        return null;
      } catch (error) {
        return {
          name: (error as Error).name,
          message: (error as Error).message,
        };
      }
    };
    const cases: Array<{
      prelude: InputActionStep[];
      invalid: InputActionStep;
    }> = [
      {
        prelude: [],
        invalid: { kind: "compositionupdate", text: "x" },
      },
      {
        prelude: [{ kind: "compositionstart" }],
        invalid: { kind: "compositionstart" },
      },
      {
        prelude: [{ kind: "compositionstart" }],
        invalid: { kind: "insert", text: "x" },
      },
      {
        prelude: [],
        invalid: { kind: "compositioncancel" },
      },
    ];

    for (const { prelude, invalid } of cases) {
      let state = createInputScriptState();
      const textarea = document.createElement("textarea");
      document.body.append(textarea);
      const player = createInputScriptPlayer(textarea);
      for (const step of prelude) {
        state = transitionInputScriptState(state, step);
        player.apply(step);
      }
      const before = JSON.parse(JSON.stringify(state));
      const expected = errorOf(() => transitionInputScriptState(state, invalid));

      expect(errorOf(() => summarizeInputScript([...prelude, invalid]))).toEqual(expected);
      expect(errorOf(() => player.apply(invalid))).toEqual(expected);
      expect(state).toEqual(before);
      expect(textarea.value).toBe(state.text);
      textarea.remove();
    }
  });

  it("generates bounded earlier revisions and restores target and caret", () => {
    const target = "abcdefghi";
    const profile = forcedProfile({
      chars_per_burst: [20, 20],
      hesitation_probability: 0,
      revision_probability: 1,
      cursor_move_probability: 0,
      paste_probability: 0,
      composition_probability: 0,
    });
    const localities = new Set<number>();
    let sawMultiScalarRun = false;
    let sawSelectionEdit = false;

    for (let seed = 0; seed < 40; seed += 1) {
      const script = synthesizeInputScript(
        target,
        seed,
        "revision-heavy-writing",
        profile,
      );
      const summary = summarizeInputScript(script.steps);
      summary.delete_locality_utf16.forEach((value) => localities.add(value));
      sawMultiScalarRun ||= summary.delete_run_lengths.some((length) => length > 1);
      sawSelectionEdit ||= script.steps.some(
        (step, index) =>
          step.kind === "selection" &&
          ["delete", "insert", "paste"].includes(
            script.steps
              .slice(index + 1)
              .find((candidate) => candidate.kind !== "wait")?.kind ?? "",
          ),
      );
      expect(summary.delete_locality_utf16.every((distance) => distance > 0 && distance <= 11)).toBe(
        true,
      );
      expect(applyScriptResult(script.steps)).toEqual({
        text: target,
        selection_start_utf16: target.length,
        selection_end_utf16: target.length,
      });
    }

    expect(localities.size).toBeGreaterThan(1);
    expect(sawMultiScalarRun).toBe(true);
    expect(sawSelectionEdit).toBe(true);
  });

  it("makes cursor-and-selection activity perform a real local edit", () => {
    const target = "cursor editing target";
    const profile = forcedProfile({
      revision_probability: 0,
      cursor_move_probability: 1,
      paste_probability: 0,
      composition_probability: 0,
    });
    const localities = new Set<number>();

    for (let seed = 0; seed < 30; seed += 1) {
      const script = synthesizeInputScript(
        target,
        seed,
        "cursor-and-selection-edits",
        profile,
      );
      const summary = summarizeInputScript(script.steps);
      summary.delete_locality_utf16.forEach((value) => localities.add(value));
      expect(
        script.steps.some(
          (step, index) =>
            step.kind === "selection" &&
            script.steps
              .slice(index + 1)
              .find((candidate) => candidate.kind !== "wait")?.kind === "delete",
        ),
      ).toBe(true);
      expect(applyScriptResult(script.steps)).toEqual({
        text: target,
        selection_start_utf16: target.length,
        selection_end_utf16: target.length,
      });
    }
    expect(localities.size).toBeGreaterThan(1);
  });

  it("generates the D4 IME lifecycle with updates, active selection, and ordinary next input", () => {
    const committedProfile = forcedProfile({
      chars_per_burst: [20, 20],
      hesitation_probability: 0,
      revision_probability: 0,
      cursor_move_probability: 1,
      paste_probability: 0,
      composition_probability: 1,
      composition_cancel_probability: 0,
    });
    const target = "😀e\u0301z";
    const committed = synthesizeInputScript(
      target,
      9,
      "natural-drafting",
      committedProfile,
    );
    const summary = summarizeInputScript(committed.steps);
    const compositionWaits = committed.steps
      .filter((step) => step.kind === "wait")
      .filter((step) => step.role === "composition");

    expect(summary.ime_update_counts).toHaveLength(2);
    expect(summary.ime_update_counts.every((count) => count >= 1 && count <= 4)).toBe(true);
    expect(compositionWaits.length).toBeGreaterThan(0);
    expect(compositionWaits.every((step) => step.ms > 0)).toBe(true);
    expect(compositionWaits[0]!.ms).toBeGreaterThanOrEqual(
      DEFAULT_INPUT_SYNTHESIS_ENVIRONMENT.sampler_throttle_ms,
    );
    for (const [index, step] of committed.steps.entries()) {
      if (step.kind === "compositioncommit") {
        expect(committed.steps.slice(index + 1).find((candidate) => candidate.kind !== "wait")?.kind).toBe(
          "insert",
        );
      }
    }
    expect(applyScript(committed.steps)).toBe(target);

    const updateCounts = new Set<number>();
    for (let seed = 0; seed < 40; seed += 1) {
      updateCounts.add(
        summarizeInputScript(
          synthesizeInputScript("😀x", seed, "natural-drafting", committedProfile).steps,
        ).ime_update_counts[0]!,
      );
    }
    expect([...updateCounts].sort()).toEqual([1, 2, 3, 4]);

    const canceled = synthesizeInputScript(
      "😀x",
      3,
      "natural-drafting",
      { ...committedProfile, composition_cancel_probability: 1 },
    );
    const cancelIndex = canceled.steps.findIndex((step) => step.kind === "compositioncancel");
    expect(canceled.steps.slice(cancelIndex + 1).find((step) => step.kind !== "wait")?.kind).toBe("insert");
    expect(applyScript(canceled.steps)).toBe("😀x");
  });

  it("summarizes the D3 raw-input distributions without fitting claims", () => {
    const summary = summarizeInputScript([
      { kind: "insert", text: "abcd" },
      { kind: "wait", ms: 7, role: "within-burst" },
      { kind: "selection", start_utf16: 1, end_utf16: 3 },
      { kind: "paste", text: "😀" },
      { kind: "selection", start_utf16: 1, end_utf16: 3 },
      { kind: "delete" },
      { kind: "wait", ms: 20, role: "between-burst" },
      { kind: "compositionstart" },
      { kind: "compositionupdate", text: "·" },
      { kind: "compositionupdate", text: "😀" },
      { kind: "compositioncommit", text: "😀" },
      { kind: "insert", text: "z" },
    ]);

    expect(summary).toMatchObject({
      burst_lengths: [5, 2],
      burst_durations_ms: [7, 0],
      delete_run_lengths: [1],
      delete_locality_utf16: [1],
      cursor_travel_utf16: [3, 2],
      selection_lengths_utf16: [2, 2],
      paste_lengths_utf16: [2],
      ime_update_counts: [2],
    });
  });

  it("generates deterministic, regime-tagged scripts that preserve target text", () => {
    for (const regime of CALIBRATION_REGIMES) {
      const first = synthesizeInputScript("Draft café 😀, then revise.", 17, regime);
      const second = synthesizeInputScript("Draft café 😀, then revise.", 17, regime);

      expect(first).toEqual(second);
      expect(first).toMatchObject({
        version: "input-script/v1",
        calibration_status: "baseline-unfitted",
        regime,
        seed_id: "number:17",
        environment: DEFAULT_INPUT_SYNTHESIS_ENVIRONMENT,
      });
      expect(applyGeneratedScript(regime, 17)).toBe(first.target_text);
    }
  });

  it("distinguishes the six baseline regimes structurally across seeds", () => {
    const natural = aggregate("natural-drafting");
    const revision = aggregate("revision-heavy-writing");
    const copied = aggregate("copied-or-scripted-typing");
    const cursor = aggregate("cursor-and-selection-edits");
    const command = aggregate("short-command-like-inputs");
    const paused = aggregate("pauses-and-resumptions");

    for (const stats of [natural, revision, copied, cursor, command, paused]) {
      expect(stats.burst_lengths.length).toBeGreaterThan(0);
      expect(stats.burst_durations_ms).toHaveLength(stats.burst_lengths.length);
      expect(stats.ime_update_counts.length).toBeGreaterThan(0);
      expect(stats.ime_update_counts.every((count) => count >= 1 && count <= 4)).toBe(true);
    }
    expect(revision.deletes).toBeGreaterThan(natural.deletes * 3);
    expect(copied.pastes).toBeGreaterThan(natural.pastes * 10);
    expect(cursor.selections).toBeGreaterThan(natural.selections * 3);
    expect(mean(command.burst_lengths)).toBeGreaterThan(mean(natural.burst_lengths));
    expect(paused.wait_ms).toBeGreaterThan(natural.wait_ms * 3);
  });

  it("rejects unknown regimes and malformed Unicode", () => {
    expect(() =>
      synthesizeInputScript("text", 1, "unknown" as CalibrationRegime),
    ).toThrow(RangeError);
    expect(() =>
      synthesizeInputScript("\ud83d", 1, "natural-drafting"),
    ).toThrow(RangeError);
    expect(() =>
      synthesizeInputScript(
        "😀x",
        1,
        "natural-drafting",
        undefined,
        { sampler_throttle_ms: 0 },
      ),
    ).toThrow(RangeError);
    expect(() =>
      synthesizeInputScript(
        "😀x",
        1,
        "natural-drafting",
        undefined,
        { sampler_throttle_ms: 1.5 },
      ),
    ).toThrow(RangeError);
  });
});
