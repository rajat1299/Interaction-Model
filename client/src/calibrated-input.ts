/** Fitted, text-free mechanics selected by the D3 profile artifact. */

import profile from "./input-synthesis-profile.json";
import {
  createNamedInputRng,
  type InputRngSubstream,
  type InputScript,
  type InputScriptStep,
} from "./input-synthesis";
import type { CalibrationRegime } from "./calibration-recorder";

type CommonRegime = {
  target_utf16_length: number;
  initial_delay_ms: readonly number[];
  burst_scalar_quantiles: readonly number[];
  within_burst_gap_ms: readonly number[];
  between_burst_gap_ms: readonly number[];
  end_backspace_runs: readonly number[];
  ime_carrier?: string;
};

type PlainRegime = CommonRegime & { mode: "plain" };

type RevisionRegime = CommonRegime & {
  mode: "revision";
  selection_edit_count: number;
  replacement_scalar_quantiles: readonly number[];
  waited_selection_count: number;
};

type CursorVariant = {
  interior_edit_count: number;
  interior_insert_scalar_count: number;
  raw_only_selection_count: number;
  waited_selection_count: number;
};

type CursorRegime = CommonRegime & {
  mode: "cursor";
  cursor_variants: readonly CursorVariant[];
  replacement_utf16_length: number;
};

type ShortRegime = CommonRegime & {
  mode: "short";
  minimum_transient_count: number;
  short_selection_only_count: number;
  transient_backspace_runs: readonly number[];
};

type CalibratedRegime = PlainRegime | RevisionRegime | CursorRegime | ShortRegime;

type CalibratedInputProfile = {
  format_version: "input-synthesis-profile/v1";
  input_profile_id: "phase1-d3-calibrated-v1";
  sampler_throttle_ms: 100;
  regimes: Record<CalibrationRegime, CalibratedRegime>;
};

/** The committed artifact is the only default profile. It contains no source text. */
export const CALIBRATED_INPUT_PROFILE = profile as CalibratedInputProfile;
export const CALIBRATED_INPUT_PROFILE_ID = CALIBRATED_INPUT_PROFILE.input_profile_id;

/** Frozen D3 classifier boundaries; profile bins may not straddle these. */
export const FROZEN_BURST_GAP_MS: Readonly<Record<CalibrationRegime, number>> = Object.freeze({
  "natural-drafting": 148,
  "revision-heavy-writing": 180,
  "copied-or-scripted-typing": 80,
  "cursor-and-selection-edits": 150,
  "short-command-like-inputs": 113,
  "pauses-and-resumptions": 325,
});

function assertCalibratedProfileGaps(): void {
  for (const regime of Object.keys(FROZEN_BURST_GAP_MS) as CalibrationRegime[]) {
    const profileRegime = CALIBRATED_INPUT_PROFILE.regimes[regime];
    const boundary = FROZEN_BURST_GAP_MS[regime];
    if (
      profileRegime.within_burst_gap_ms.some((milliseconds) => milliseconds >= boundary) ||
      profileRegime.between_burst_gap_ms.some((milliseconds) => milliseconds < boundary)
    ) {
      throw new RangeError(`calibrated ${regime} gap bins cross the frozen burst boundary`);
    }
  }
}

assertCalibratedProfileGaps();

export type CalibratedInputOptions = {
  transient_texts?: readonly string[];
};

function grid(
  values: readonly number[],
  next: () => number,
): number {
  return values[Math.min(values.length - 1, Math.floor(next() * values.length))]!;
}

function scaledCount(count: number, targetLength: number, referenceLength: number): number {
  return targetLength === 0 ? 0 : Math.max(1, Math.round((count * targetLength) / referenceLength));
}

function scalarBoundaries(text: string): number[] {
  const boundaries = [0];
  let offset = 0;
  for (const character of text) {
    offset += character.length;
    boundaries.push(offset);
  }
  return boundaries;
}

type RecentEditSelector = {
  boundaries: readonly number[];
  startIndex: (maxStart: number, next: () => number) => number;
  update: (endIndex: number) => void;
};

function clamp(value: number, minimum: number, maximum: number): number {
  return Math.min(maximum, Math.max(minimum, value));
}

function recentEditSelector(text: string): RecentEditSelector {
  const boundaries = scalarBoundaries(text);
  const lineStarts = [0];
  let scalarIndex = 0;
  for (const character of text) {
    scalarIndex += 1;
    if (character === "\n" && scalarIndex < boundaries.length - 1) {
      lineStarts.push(scalarIndex);
    }
  }
  let anchor = boundaries.length - 1;

  const lineIndexAt = (index: number): number => {
    let low = 0;
    let high = lineStarts.length - 1;
    while (low < high) {
      const middle = Math.ceil((low + high) / 2);
      if (lineStarts[middle]! <= index) {
        low = middle;
      } else {
        high = middle - 1;
      }
    }
    return low;
  };

  return {
    boundaries,
    startIndex: (maxStart, next): number => {
      // 72% within ±8 scalars, 23% at ±2–3 lines, and 5% uniform.
      const mode = next();
      if (mode < 0.72) {
        return clamp(anchor + Math.floor(next() * 17) - 8, 0, maxStart);
      }
      if (mode < 0.95) {
        if (lineStarts.length <= 3) {
          return clamp(anchor + Math.floor(next() * 17) - 8, 0, maxStart);
        }
        const lineIndex = lineIndexAt(anchor);
        const candidates = [-3, -2, 2, 3]
          .map((offset) => lineIndex + offset)
          .filter((index) => index >= 0 && index < lineStarts.length);
        const selectedLine = candidates[Math.floor(next() * candidates.length)]!;
        const start = lineStarts[selectedLine]!;
        const end = lineStarts[selectedLine + 1] ?? boundaries.length - 1;
        return clamp(start + Math.floor(next() * Math.max(1, end - start)), 0, maxStart);
      }
      return Math.floor(next() * (maxStart + 1));
    },
    update: (endIndex): void => {
      anchor = endIndex;
    },
  };
}

function repeatedBackspaces(
  steps: InputScriptStep[],
  runs: readonly number[],
  beforeInput: () => void,
): void {
  for (const run of runs) {
    for (let index = 0; index < run; index += 1) {
      beforeInput();
      steps.push({ kind: "insert", text: "~" });
    }
    for (let index = 0; index < run; index += 1) {
      beforeInput();
      steps.push({ kind: "delete" });
    }
  }
}

function interiorSlice(
  text: string,
  desiredUtf16Length: number,
  selector: RecentEditSelector,
  next: () => number,
): readonly [number, number, string] {
  const { boundaries } = selector;
  if (boundaries.length === 1) {
    return [0, 0, ""];
  }
  const maxStart = Math.max(0, boundaries.length - 2);
  const startIndex = selector.startIndex(maxStart, next);
  let endIndex = startIndex + 1;
  while (
    endIndex < boundaries.length &&
    boundaries[endIndex]! - boundaries[startIndex]! <= desiredUtf16Length
  ) {
    endIndex += 1;
  }
  endIndex = Math.max(startIndex + 1, endIndex - 1);
  const start = boundaries[startIndex]!;
  const end = boundaries[endIndex]!;
  selector.update(endIndex);
  return [start, end, text.slice(start, end)];
}

function interiorScalarSlice(
  text: string,
  desiredScalars: number,
  selector: RecentEditSelector,
  next: () => number,
): readonly [number, number, string] {
  const { boundaries } = selector;
  const scalarCount = boundaries.length - 1;
  if (scalarCount === 0) {
    return [0, 0, ""];
  }
  const count = Math.min(Math.max(1, desiredScalars), scalarCount);
  const maxStart = scalarCount - count;
  const startIndex = selector.startIndex(maxStart, next);
  const start = boundaries[startIndex]!;
  const end = boundaries[startIndex + count]!;
  selector.update(startIndex + count);
  return [start, end, text.slice(start, end)];
}

/**
 * Build the closed-profile default script. Draws choose quantile bins, never
 * reference-event order or source text, and all paths restore the final target.
 */
export function synthesizeCalibratedInputScript(
  targetText: string,
  seed: string | number,
  regimeName: CalibrationRegime,
  options: CalibratedInputOptions = {},
): InputScript {
  const regime = CALIBRATED_INPUT_PROFILE.regimes[regimeName];
  const rng = createNamedInputRng(seed);
  const steps: InputScriptStep[] = [];
  const timing = (): number => grid(regime.within_burst_gap_ms, () => rng.next("timing"));
  const between = (): number => grid(regime.between_burst_gap_ms, () => rng.next("timing"));
  const pick = (values: readonly number[], stream: InputRngSubstream): number =>
    grid(values, () => rng.next(stream));
  const withinInputWait = (): void => {
    steps.push({ kind: "wait", ms: timing(), role: "within-burst" });
  };
  const observedSelectionWait = (): void => {
    steps.push({
      kind: "wait",
      ms: Math.max(CALIBRATED_INPUT_PROFILE.sampler_throttle_ms, timing()),
      role: "revision",
    });
  };

  steps.push({
    kind: "wait",
    ms: pick(regime.initial_delay_ms, "timing"),
    role: "initial",
  });

  const typeText = (text: string, afterInput = false): void => {
    let remaining = pick(regime.burst_scalar_quantiles, "timing");
    let first = !afterInput;
    for (const character of text) {
      if (!first) {
        const role = remaining <= 0 ? "between-burst" : "within-burst";
        steps.push({ kind: "wait", ms: role === "between-burst" ? between() : timing(), role });
        if (remaining <= 0) {
          remaining = pick(regime.burst_scalar_quantiles, "timing");
        }
      }
      steps.push({ kind: "insert", text: character });
      remaining -= 1;
      first = false;
    }
  };

  const addDeterministicImeCarrier = (): boolean => {
    const bucket = [...`${typeof seed}:${String(seed)}`].reduce(
      (value, character) => (value * 31 + character.charCodeAt(0)) % 17,
      0,
    );
    if (regime.ime_carrier === undefined || bucket !== 0) {
      return false;
    }
    steps.push({ kind: "compositionstart" });
    steps.push({ kind: "wait", ms: timing(), role: "composition" });
    steps.push({ kind: "compositionupdate", text: regime.ime_carrier });
    steps.push({ kind: "wait", ms: timing(), role: "composition" });
    steps.push({ kind: "compositioncommit", text: regime.ime_carrier });
    withinInputWait();
    steps.push({ kind: "delete" });
    return true;
  };

  switch (regime.mode) {
    case "plain":
      typeText(targetText, addDeterministicImeCarrier());
      repeatedBackspaces(steps, regime.end_backspace_runs, withinInputWait);
      break;
    case "revision": {
      typeText(targetText);
      const selector = recentEditSelector(targetText);
      const editCount = scaledCount(
        regime.selection_edit_count,
        targetText.length,
        regime.target_utf16_length,
      );
      for (let index = 0; index < editCount; index += 1) {
        const [start, end, replacement] = interiorSlice(
          targetText,
          pick(regime.replacement_scalar_quantiles, "revision"),
          selector,
          () => rng.next("revision"),
        );
        if (start === end) {
          continue;
        }
        steps.push({ kind: "selection", start_utf16: start, end_utf16: end });
        if (
          Math.floor(((index + 1) * regime.waited_selection_count) / editCount) !==
          Math.floor((index * regime.waited_selection_count) / editCount)
        ) {
          observedSelectionWait();
        }
        steps.push({ kind: "delete" });
        typeText(replacement, true);
      }
      repeatedBackspaces(steps, regime.end_backspace_runs, withinInputWait);
      steps.push({ kind: "selection", start_utf16: targetText.length, end_utf16: targetText.length });
      break;
    }
    case "cursor": {
      if (targetText.length === 0) {
        break;
      }
      steps.push({ kind: "paste", text: targetText });
      const variant = regime.cursor_variants[
        Math.floor(rng.next("cursor") * regime.cursor_variants.length)
      ]!;
      const selector = recentEditSelector(targetText);
      const { boundaries } = selector;
      const editCount = scaledCount(
        variant.interior_edit_count,
        targetText.length,
        regime.target_utf16_length,
      );
      const totalInserted = scaledCount(
        variant.interior_insert_scalar_count,
        targetText.length,
        regime.target_utf16_length,
      );
      let insertedRemaining = totalInserted;
      for (let index = 0; index < editCount; index += 1) {
        const remainingEdits = editCount - index;
        const count = Math.max(1, Math.floor(insertedRemaining / remainingEdits));
        insertedRemaining -= count;
        const [start, end, replacement] = interiorScalarSlice(
          targetText,
          count,
          selector,
          () => rng.next("cursor"),
        );
        steps.push({ kind: "selection", start_utf16: start, end_utf16: end });
        steps.push({ kind: "delete" });
        typeText(replacement, true);
      }
      const waitedSelections = scaledCount(
        variant.waited_selection_count,
        targetText.length,
        regime.target_utf16_length,
      );
      for (let index = 0; index < waitedSelections; index += 1) {
        const boundary = boundaries[Math.floor(rng.next("cursor") * boundaries.length)]!;
        steps.push({ kind: "selection", start_utf16: boundary, end_utf16: boundary });
        observedSelectionWait();
      }
      const rawOnlySelections = scaledCount(
        variant.raw_only_selection_count,
        targetText.length,
        regime.target_utf16_length,
      );
      for (let index = 0; index < rawOnlySelections; index += 1) {
        const boundary = boundaries[Math.floor(rng.next("cursor") * boundaries.length)]!;
        steps.push({ kind: "selection", start_utf16: boundary, end_utf16: boundary });
      }
      const [start, end, replacement] = interiorSlice(
        targetText,
        regime.replacement_utf16_length,
        selector,
        () => rng.next("cursor"),
      );
      steps.push({ kind: "selection", start_utf16: start, end_utf16: end });
      observedSelectionWait();
      steps.push({ kind: "paste", text: replacement });
      repeatedBackspaces(steps, regime.end_backspace_runs, withinInputWait);
      steps.push({ kind: "selection", start_utf16: targetText.length, end_utf16: targetText.length });
      break;
    }
    case "short": {
      const distinct = [...new Set(options.transient_texts?.filter((text) => text.length > 0) ?? [])];
      const targetScalars = [...targetText];
      const fallback = targetScalars.length >= 3
        ? [
          targetScalars.slice(0, Math.ceil(targetScalars.length / 3)).join(""),
          targetScalars.slice(0, Math.ceil(targetScalars.length / 2)).join(""),
          targetText,
        ]
        : [];
      const transients = (distinct.length >= regime.minimum_transient_count ? distinct : fallback)
        .slice(0, regime.minimum_transient_count);
      let runIndex = 0;
      for (const [transientIndex, transient] of transients.entries()) {
        typeText(transient);
        const remainingTransients = transients.length - transientIndex;
        const remainingRuns = regime.transient_backspace_runs.length - runIndex;
        const count = Math.ceil(remainingRuns / remainingTransients);
        repeatedBackspaces(
          steps,
          regime.transient_backspace_runs.slice(runIndex, runIndex + count),
          withinInputWait,
        );
        runIndex += count;
        steps.push({ kind: "selection", start_utf16: 0, end_utf16: transient.length });
        observedSelectionWait();
        steps.push({ kind: "delete" });
      }
      typeText(targetText, transients.length > 0);
      const selectionOnly = scaledCount(
        regime.short_selection_only_count,
        targetText.length,
        regime.target_utf16_length,
      );
      const finalBoundaries = scalarBoundaries(targetText);
      for (let index = 0; index < selectionOnly; index += 1) {
        const boundary = finalBoundaries[Math.floor(rng.next("cursor") * finalBoundaries.length)]!;
        steps.push({ kind: "selection", start_utf16: boundary, end_utf16: boundary });
        observedSelectionWait();
      }
      if (targetText.length > 0) {
        steps.push({
          kind: "selection",
          start_utf16: targetText.length,
          end_utf16: targetText.length,
        });
      }
      break;
    }
  }

  return steps;
}
