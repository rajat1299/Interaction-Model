/** Fitted, text-free mechanics selected by the D3 profile artifact. */

import profile from "./input-synthesis-profile.json";
import {
  createNamedInputRng,
  type InputRngSubstream,
  type InputScript,
  type InputScriptStep,
} from "./input-synthesis";
import { CALIBRATION_REGIMES, type CalibrationRegime } from "./calibration-recorder";

type CommonRegime = {
  target_utf16_length: number;
  end_backspace_runs: readonly number[];
  timing: {
    burst_gap_ms: number;
    splits: Record<CalibrationTimingSplit, TimingAtoms>;
  };
  ime_carrier?: string;
};

export type CalibrationTimingSplit = "train" | "dev" | "test";

type TimingBoundaryPoint = {
  relative_ms: number;
  event_ordinal: number | null;
  boundary_ordinal: number;
  is_burst_boundary: boolean;
  boundary_kind: "burst-start" | "recording-end";
};

type TimingAtoms = {
  initial_delay_ms: readonly number[];
  inter_key_interval_ms: readonly number[];
  burst_geometry: readonly (readonly [number, number])[];
  between_burst_gap_ms: readonly number[];
};

type PlainRegime = CommonRegime & { mode: "plain" };

type RevisionPlacement = {
  immediate_count: number;
  immediate_local_count: number;
  immediate_line_offsets: readonly number[];
  look_back_count: number;
  look_back_line_offsets: readonly number[];
};

type RevisionRegime = CommonRegime & {
  mode: "revision";
  replacement_scalar_quantiles: readonly number[];
  waited_selection_count: number;
  revision_placement: RevisionPlacement;
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
  revision_placement: RevisionPlacement;
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
  timing: {
    algorithm: "seeded-bootstrap-v1";
    jitter_ms: number;
    bundles: readonly {
      runtime_session_id: string;
      regime: CalibrationRegime;
      browser_bundle_sha256: string;
      splits: Record<CalibrationTimingSplit, {
        start: TimingBoundaryPoint;
        end: TimingBoundaryPoint;
      }>;
    }[];
  };
  regimes: Record<CalibrationRegime, CalibratedRegime>;
};

/** The committed artifact is the only default profile. It contains no source text. */
export const CALIBRATED_INPUT_PROFILE = profile as unknown as CalibratedInputProfile;
export const CALIBRATED_INPUT_PROFILE_ID = CALIBRATED_INPUT_PROFILE.input_profile_id;

function assertCalibratedProfileGaps(): void {
  for (const regime of CALIBRATION_REGIMES) {
    const profileRegime = CALIBRATED_INPUT_PROFILE.regimes[regime];
    const boundary = profileRegime.timing.burst_gap_ms;
    if (
      !Number.isInteger(boundary) ||
      boundary <= 1 ||
      Object.values(profileRegime.timing.splits).some(({ inter_key_interval_ms, between_burst_gap_ms }) =>
        inter_key_interval_ms.some((milliseconds) => milliseconds >= boundary) ||
        between_burst_gap_ms.some((milliseconds) => milliseconds < boundary),
      )
    ) {
      throw new RangeError(`calibrated ${regime} gap bins cross the frozen burst boundary`);
    }
  }
}

assertCalibratedProfileGaps();

export type CalibratedInputOptions = {
  transient_texts?: readonly string[];
  timing_split?: CalibrationTimingSplit;
};

export type CalibrationSynthesisTrace = {
  split: CalibrationTimingSplit;
  seed_id: string;
  revision: { immediate_count: number; look_back_count: number };
};

export type CalibratedInputSynthesis = {
  steps: InputScript;
  timing: CalibrationSynthesisTrace;
  look_back_input_step_ranges: readonly {
    start_step: number;
    end_step: number;
  }[];
};

function grid<T>(
  values: readonly T[],
  next: () => number,
): T {
  return values[Math.min(values.length - 1, Math.floor(next() * values.length))]!;
}

function timingSeedId(seed: string | number, split: CalibrationTimingSplit): string {
  return `timing/${split}/${typeof seed}:${String(seed)}`;
}

function jittered(
  value: number,
  next: () => number,
  minimum: number,
  maximum = Number.MAX_SAFE_INTEGER,
): number {
  const jitter = CALIBRATED_INPUT_PROFILE.timing.jitter_ms;
  const offset = Math.floor(next() * (jitter * 2 + 1)) - jitter;
  return clamp(Math.round(value) + offset, minimum, maximum);
}

function bootstrapWithinIntervals(
  duration: number,
  count: number,
  atoms: TimingAtoms,
  boundary: number,
  next: () => number,
): number[] {
  if (count === 0) {
    return [];
  }
  const intervals = Array.from({ length: count }, () => jittered(
    grid(atoms.inter_key_interval_ms, next),
    next,
    1,
    boundary - 1,
  ));
  const allocationOrder = intervals.map((_value, index) => index);
  for (let index = allocationOrder.length - 1; index > 0; index -= 1) {
    const swapIndex = Math.floor(next() * (index + 1));
    [allocationOrder[index], allocationOrder[swapIndex]] = [
      allocationOrder[swapIndex]!,
      allocationOrder[index]!,
    ];
  }
  let remaining = duration - intervals.reduce((total, value) => total + value, 0);
  for (const index of allocationOrder) {
    if (remaining === 0) {
      break;
    }
    const value = intervals[index]!;
    const adjustment = remaining > 0
      ? Math.min(remaining, boundary - 1 - value)
      : -Math.min(-remaining, value - 1);
    intervals[index] = value + adjustment;
    remaining -= adjustment;
  }
  if (remaining !== 0) {
    throw new RangeError("sampled burst duration is infeasible");
  }
  return intervals;
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

type RevisionPlacementMode = "local" | "line" | "look-back";

type SelectedRevisionPlacement = {
  index: number;
  mode: RevisionPlacementMode;
};

type RecentEditSelector = {
  boundaries: readonly number[];
  startIndex: (
    maxStart: number,
    next: () => number,
    mode: RevisionPlacementMode,
    lineOffsets?: readonly number[],
  ) => SelectedRevisionPlacement;
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
    startIndex: (maxStart, next, mode, lineOffsets = []): SelectedRevisionPlacement => {
      const local = (): SelectedRevisionPlacement => ({
        index: clamp(anchor + Math.floor(next() * 17) - 8, 0, maxStart),
        mode: "local",
      });
      if (mode === "local") {
        return local();
      }
      if (lineStarts.length <= 1) {
        return local();
      }
      const lineIndex = lineIndexAt(anchor);
      const candidates = lineOffsets
        .flatMap((offset) => [lineIndex - offset, lineIndex + offset])
        .filter(
          (index) =>
            index >= 0 &&
            index < lineStarts.length &&
            lineStarts[index]! <= maxStart,
        );
      if (candidates.length === 0) {
        return local();
      }
      const selectedLine = candidates[Math.floor(next() * candidates.length)]!;
      const start = lineStarts[selectedLine]!;
      const end = lineStarts[selectedLine + 1] ?? boundaries.length - 1;
      return {
        index: clamp(start + Math.floor(next() * Math.max(1, end - start)), 0, maxStart),
        mode,
      };
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
  mode: RevisionPlacementMode = "local",
  lineOffsets?: readonly number[],
): readonly [number, number, string, RevisionPlacementMode] {
  const { boundaries } = selector;
  if (boundaries.length === 1) {
    return [0, 0, "", "local"];
  }
  const maxStart = Math.max(0, boundaries.length - 2);
  const placement = selector.startIndex(maxStart, next, mode, lineOffsets);
  const startIndex = placement.index;
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
  return [start, end, text.slice(start, end), placement.mode];
}

function interiorScalarSlice(
  text: string,
  desiredScalars: number,
  selector: RecentEditSelector,
  next: () => number,
  mode: RevisionPlacementMode = "local",
  lineOffsets?: readonly number[],
): readonly [number, number, string, RevisionPlacementMode] {
  const { boundaries } = selector;
  const scalarCount = boundaries.length - 1;
  if (scalarCount === 0) {
    return [0, 0, "", "local"];
  }
  const count = Math.min(Math.max(1, desiredScalars), scalarCount);
  const maxStart = scalarCount - count;
  const placement = selector.startIndex(maxStart, next, mode, lineOffsets);
  const startIndex = placement.index;
  const start = boundaries[startIndex]!;
  const end = boundaries[startIndex + count]!;
  selector.update(startIndex + count);
  return [start, end, text.slice(start, end), placement.mode];
}

/** Build a closed-profile script from text-free, split-scoped timing atoms. */
export function synthesizeCalibratedInput(
  targetText: string,
  seed: string | number,
  regimeName: CalibrationRegime,
  options: CalibratedInputOptions = {},
): CalibratedInputSynthesis {
  const regime = CALIBRATED_INPUT_PROFILE.regimes[regimeName];
  const split = options.timing_split ?? "train";
  const atoms = regime.timing.splits[split];
  const burstGapMs = regime.timing.burst_gap_ms;
  const rng = createNamedInputRng(seed);
  const timingRng = createNamedInputRng(timingSeedId(seed, split));
  const steps: InputScriptStep[] = [];
  const trace: CalibrationSynthesisTrace = {
    split,
    seed_id: timingSeedId(seed, split),
    revision: { immediate_count: 0, look_back_count: 0 },
  };
  const lookBackInputStepRanges: { start_step: number; end_step: number }[] = [];
  const timing = (): number => jittered(
    grid(atoms.inter_key_interval_ms, () => timingRng.next("timing")),
    () => timingRng.next("timing"),
    1,
    burstGapMs - 1,
  );
  const between = (): number => jittered(
    grid(atoms.between_burst_gap_ms, () => timingRng.next("timing")),
    () => timingRng.next("timing"),
    burstGapMs,
  );
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
    ms: jittered(
      grid(atoms.initial_delay_ms, () => timingRng.next("timing")),
      () => timingRng.next("timing"),
      0,
    ),
    role: "initial",
  });

  const typeText = (text: string, afterInput = false): void => {
    const nextBurst = (): { remaining: number; intervals: number[]; intervalIndex: number } => {
      const [length, recordedDuration] = grid(
        atoms.burst_geometry,
        () => timingRng.next("timing"),
      );
      const intervalCount = length - 1;
      const duration = intervalCount === 0 ? 0 : jittered(
        recordedDuration,
        () => timingRng.next("timing"),
        intervalCount,
        intervalCount * (burstGapMs - 1),
      );
      return {
        remaining: length,
        intervals: bootstrapWithinIntervals(
          duration,
          intervalCount,
          atoms,
          burstGapMs,
          () => timingRng.next("timing"),
        ),
        intervalIndex: 0,
      };
    };
    let burst = nextBurst();
    if (afterInput) {
      burst.remaining -= 1;
    }
    let first = !afterInput;
    for (const character of text) {
      if (!first) {
        if (burst.remaining <= 0) {
          steps.push({ kind: "wait", ms: between(), role: "between-burst" });
          burst = nextBurst();
        } else {
          steps.push({
            kind: "wait",
            ms: burst.intervals[burst.intervalIndex++] ?? timing(),
            role: "within-burst",
          });
        }
      }
      steps.push({ kind: "insert", text: character });
      burst.remaining -= 1;
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
      const immediateCount = scaledCount(
        regime.revision_placement.immediate_count,
        targetText.length,
        regime.target_utf16_length,
      );
      const immediateLocalCount = Math.min(
        immediateCount,
        scaledCount(
          regime.revision_placement.immediate_local_count,
          targetText.length,
          regime.target_utf16_length,
        ),
      );
      const lookBackCount = scaledCount(
        regime.revision_placement.look_back_count,
        targetText.length,
        regime.target_utf16_length,
      );
      const editCount = immediateCount + lookBackCount;
      for (let index = 0; index < editCount; index += 1) {
        const immediate = index < immediateCount;
        const mode = immediate
          ? index < immediateLocalCount ? "local" : "line"
          : "look-back";
        const lineOffsets = immediate
          ? regime.revision_placement.immediate_line_offsets
          : regime.revision_placement.look_back_line_offsets;
        const [start, end, replacement, actualMode] = interiorSlice(
          targetText,
          pick(regime.replacement_scalar_quantiles, "revision"),
          selector,
          () => rng.next("revision"),
          mode,
          lineOffsets,
        );
        if (start === end) {
          continue;
        }
        const designedLookBack = actualMode === "look-back";
        if (designedLookBack) {
          trace.revision.look_back_count += 1;
        } else {
          trace.revision.immediate_count += 1;
        }
        steps.push({ kind: "selection", start_utf16: start, end_utf16: end });
        if (
          Math.floor(((index + 1) * regime.waited_selection_count) / editCount) !==
          Math.floor((index * regime.waited_selection_count) / editCount)
        ) {
          observedSelectionWait();
        }
        const transactionStart = steps.length;
        steps.push({ kind: "delete" });
        typeText(replacement, true);
        if (designedLookBack) {
          lookBackInputStepRanges.push({
            start_step: transactionStart,
            end_step: steps.length - 1,
          });
        }
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
      const intendedPlacementCount = scaledCount(
        regime.revision_placement.immediate_count + regime.revision_placement.look_back_count,
        targetText.length,
        regime.target_utf16_length,
      );
      const lookBackCount = Math.min(
        Math.max(0, editCount - 1),
        Math.round((editCount * regime.revision_placement.look_back_count) / intendedPlacementCount),
      );
      const immediateCount = editCount - lookBackCount;
      const immediateLocalCount = Math.min(
        immediateCount,
        scaledCount(
          regime.revision_placement.immediate_local_count,
          targetText.length,
          regime.target_utf16_length,
        ),
      );
      let insertedRemaining = totalInserted;
      for (let index = 0; index < editCount; index += 1) {
        const remainingEdits = editCount - index;
        const count = Math.max(1, Math.floor(insertedRemaining / remainingEdits));
        insertedRemaining -= count;
        const immediate = index < immediateCount;
        const mode = immediate
          ? index < immediateLocalCount ? "local" : "line"
          : "look-back";
        const [start, end, replacement, actualMode] = interiorScalarSlice(
          targetText,
          count,
          selector,
          () => rng.next("cursor"),
          mode,
          immediate
            ? regime.revision_placement.immediate_line_offsets
            : regime.revision_placement.look_back_line_offsets,
        );
        const designedLookBack = actualMode === "look-back";
        if (designedLookBack) {
          trace.revision.look_back_count += 1;
        } else {
          trace.revision.immediate_count += 1;
        }
        steps.push({ kind: "selection", start_utf16: start, end_utf16: end });
        const transactionStart = steps.length;
        steps.push({ kind: "delete" });
        typeText(replacement, true);
        if (designedLookBack) {
          lookBackInputStepRanges.push({
            start_step: transactionStart,
            end_step: steps.length - 1,
          });
        }
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
      trace.revision.immediate_count += 1;
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

  return { steps, timing: trace, look_back_input_step_ranges: lookBackInputStepRanges };
}

/** Compatibility wrapper for callers that only need executable steps. */
export function synthesizeCalibratedInputScript(
  targetText: string,
  seed: string | number,
  regimeName: CalibrationRegime,
  options: CalibratedInputOptions = {},
): InputScript {
  return synthesizeCalibratedInput(targetText, seed, regimeName, options).steps;
}
