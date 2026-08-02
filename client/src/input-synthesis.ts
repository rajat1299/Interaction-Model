/** Deterministic raw textarea scripts for calibration and sampler tests only. */

import {
  CALIBRATION_REGIMES,
  type CalibrationRegime,
} from "./calibration-recorder";
import {
  CALIBRATED_INPUT_PROFILE,
  CALIBRATED_INPUT_PROFILE_ID,
  synthesizeCalibratedInputScript,
  type CalibratedInputOptions,
} from "./calibrated-input";

export type InputRngSubstream = "timing" | "revision" | "cursor" | "paste" | "composition";

export type NamedInputRng = {
  next: (substream: InputRngSubstream) => number;
};

export type WaitStep = {
  kind: "wait";
  ms: number;
  role?:
    | "within-burst"
    | "between-burst"
    | "punctuation"
    | "hesitation"
    | "revision"
    | "composition"
    | "initial";
};
export type InsertStep = { kind: "insert"; text: string };
export type DeleteStep = {
  kind: "delete";
  input_type?: "deleteContentBackward" | "deleteContentForward";
};
export type SelectionStep = { kind: "selection"; start_utf16: number; end_utf16: number };
export type PasteStep = { kind: "paste"; text: string };
export type CompositionStartStep = { kind: "compositionstart"; data?: string };
export type CompositionUpdateStep = { kind: "compositionupdate"; text: string };
export type CompositionCommitStep = { kind: "compositioncommit"; text: string };
export type CompositionCancelStep = { kind: "compositioncancel" };

export type InputScriptStep =
  | WaitStep
  | InsertStep
  | DeleteStep
  | SelectionStep
  | PasteStep
  | CompositionStartStep
  | CompositionUpdateStep
  | CompositionCommitStep
  | CompositionCancelStep;

export type InputScript = readonly InputScriptStep[];
export type InputActionStep = Exclude<InputScriptStep, WaitStep>;

export type InputSynthesisProfile = {
  chars_per_burst: readonly [number, number];
  within_burst_ms: readonly [number, number];
  between_burst_ms: readonly [number, number];
  punctuation_pause_ms: readonly [number, number];
  hesitation_ms: readonly [number, number];
  hesitation_probability: number;
  revision_probability: number;
  cursor_move_probability: number;
  paste_probability: number;
  composition_probability: number;
  composition_cancel_probability: number;
};

export type InputSynthesisEnvironment = {
  sampler_throttle_ms: number;
};

/** Must stay aligned with the frozen production sampler default. */
export const DEFAULT_INPUT_SYNTHESIS_ENVIRONMENT: Readonly<InputSynthesisEnvironment> =
  Object.freeze({ sampler_throttle_ms: 100 });

export type SynthesizedInputScript = {
  version: "input-script/v1";
  calibration_status: typeof INPUT_SYNTHESIS_PROFILE_ID | "baseline-unfitted";
  regime: CalibrationRegime;
  seed_id: string;
  target_text: string;
  environment: InputSynthesisEnvironment;
  steps: InputScript;
};

export const INPUT_SYNTHESIS_PROFILE_ID = CALIBRATED_INPUT_PROFILE_ID;
export type InputSynthesisOptions = CalibratedInputOptions;

/**
 * Compatibility priors used only when a caller supplies an explicit custom
 * profile; default synthesis uses the calibrated JSON artifact.
 */
export const BASELINE_INPUT_PROFILES: Record<CalibrationRegime, InputSynthesisProfile> = {
  "natural-drafting": {
    chars_per_burst: [3, 9],
    within_burst_ms: [45, 115],
    between_burst_ms: [180, 600],
    punctuation_pause_ms: [140, 420],
    hesitation_ms: [250, 900],
    hesitation_probability: 0.04,
    revision_probability: 0.04,
    cursor_move_probability: 0.03,
    paste_probability: 0.01,
    composition_probability: 0.08,
    composition_cancel_probability: 0.08,
  },
  "revision-heavy-writing": {
    chars_per_burst: [2, 6],
    within_burst_ms: [55, 140],
    between_burst_ms: [220, 750],
    punctuation_pause_ms: [180, 520],
    hesitation_ms: [300, 1_100],
    hesitation_probability: 0.12,
    revision_probability: 0.28,
    cursor_move_probability: 0.28,
    paste_probability: 0.02,
    composition_probability: 0.08,
    composition_cancel_probability: 0.15,
  },
  "copied-or-scripted-typing": {
    chars_per_burst: [6, 16],
    within_burst_ms: [25, 70],
    between_burst_ms: [90, 260],
    punctuation_pause_ms: [60, 180],
    hesitation_ms: [180, 500],
    hesitation_probability: 0.01,
    revision_probability: 0.01,
    cursor_move_probability: 0.02,
    paste_probability: 0.55,
    composition_probability: 0.02,
    composition_cancel_probability: 0.05,
  },
  "cursor-and-selection-edits": {
    chars_per_burst: [2, 7],
    within_burst_ms: [50, 130],
    between_burst_ms: [170, 620],
    punctuation_pause_ms: [130, 400],
    hesitation_ms: [220, 850],
    hesitation_probability: 0.08,
    revision_probability: 0.16,
    cursor_move_probability: 0.75,
    paste_probability: 0.03,
    composition_probability: 0.06,
    composition_cancel_probability: 0.12,
  },
  "short-command-like-inputs": {
    chars_per_burst: [4, 12],
    within_burst_ms: [40, 105],
    between_burst_ms: [120, 380],
    punctuation_pause_ms: [100, 260],
    hesitation_ms: [180, 600],
    hesitation_probability: 0.03,
    revision_probability: 0.05,
    cursor_move_probability: 0.02,
    paste_probability: 0.01,
    composition_probability: 0.05,
    composition_cancel_probability: 0.08,
  },
  "pauses-and-resumptions": {
    chars_per_burst: [1, 5],
    within_burst_ms: [60, 150],
    between_burst_ms: [500, 1_800],
    punctuation_pause_ms: [450, 1_400],
    hesitation_ms: [800, 2_600],
    hesitation_probability: 0.3,
    revision_probability: 0.05,
    cursor_move_probability: 0.06,
    paste_probability: 0.01,
    composition_probability: 0.06,
    composition_cancel_probability: 0.1,
  },
};

export type InputScriptSummary = {
  waits: number;
  wait_ms: number;
  inserts: number;
  deletes: number;
  selections: number;
  pastes: number;
  compositions: number;
  burst_lengths: number[];
  burst_durations_ms: number[];
  delete_run_lengths: number[];
  delete_locality_utf16: number[];
  cursor_travel_utf16: number[];
  selection_lengths_utf16: number[];
  paste_lengths_utf16: number[];
  ime_update_counts: number[];
};

export type InputScriptCompositionState = {
  original_text: string;
  original_start: number;
  original_end: number;
  start: number;
  end: number;
};

export type InputScriptState = {
  text: string;
  selection_start_utf16: number;
  selection_end_utf16: number;
  composition: InputScriptCompositionState | null;
};

function hashSeed(seed: string | number, namespace: string): number {
  let hash = 2_166_136_261;
  const value = `${typeof seed}:${String(seed)}:${namespace}`;
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index);
    hash = Math.imul(hash, 16_777_619);
  }
  return hash >>> 0;
}

function nextRandom(state: number): [number, number] {
  const next = (state + 0x6d2b79f5) >>> 0;
  let mixed = next;
  mixed = Math.imul(mixed ^ (mixed >>> 15), mixed | 1);
  mixed ^= mixed + Math.imul(mixed ^ (mixed >>> 7), mixed | 61);
  return [next, ((mixed ^ (mixed >>> 14)) >>> 0) / 4_294_967_296];
}

/**
 * Independent named streams keep timing draws stable when another synthesis
 * concern starts consuming its own randomness.
 */
export function createNamedInputRng(seed: string | number): NamedInputRng {
  const states = new Map<InputRngSubstream, number>();

  return {
    next: (substream): number => {
      const state = states.get(substream) ?? hashSeed(seed, substream);
      const [nextState, value] = nextRandom(state);
      states.set(substream, nextState);
      return value;
    },
  };
}

function integerInRange(
  rng: NamedInputRng,
  range: readonly [number, number],
  substream: InputRngSubstream = "timing",
): number {
  const [minimum, maximum] = validateIntegerRange(range);
  return minimum + Math.floor(rng.next(substream) * (maximum - minimum + 1));
}

function validateIntegerRange(
  range: readonly [number, number],
): readonly [number, number] {
  const [minimum, maximum] = range;
  if (
    !Number.isSafeInteger(minimum) ||
    !Number.isSafeInteger(maximum) ||
    minimum < 0 ||
    maximum < minimum
  ) {
    throw new RangeError(
      "timing ranges must contain non-negative integers in ascending order",
    );
  }
  return range;
}

function assertProbability(value: number, name: string): void {
  if (!Number.isFinite(value) || value < 0 || value > 1) {
    throw new RangeError(`${name} must be in [0, 1]`);
  }
}

function validateProfile(profile: InputSynthesisProfile): void {
  validateIntegerRange(profile.chars_per_burst);
  validateIntegerRange(profile.within_burst_ms);
  validateIntegerRange(profile.between_burst_ms);
  validateIntegerRange(profile.punctuation_pause_ms);
  validateIntegerRange(profile.hesitation_ms);
  for (const name of [
    "hesitation_probability",
    "revision_probability",
    "cursor_move_probability",
    "paste_probability",
    "composition_probability",
    "composition_cancel_probability",
  ] as const) {
    assertProbability(profile[name], name);
  }
  if (profile.chars_per_burst[0] < 1) {
    throw new RangeError("chars_per_burst must be positive");
  }
}

function validateEnvironment(environment: InputSynthesisEnvironment): void {
  if (
    !Number.isSafeInteger(environment.sampler_throttle_ms) ||
    environment.sampler_throttle_ms <= 0
  ) {
    throw new RangeError("sampler_throttle_ms must be a positive integer");
  }
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

function seedId(seed: string | number): string {
  return `${typeof seed}:${String(seed)}`;
}

/** Generate one pure, regime-tagged script; DOM execution remains in C3. */
export function synthesizeInputScript(
  targetText: string,
  seed: string | number,
  regime: CalibrationRegime,
  profile?: InputSynthesisProfile,
  environment: InputSynthesisEnvironment = DEFAULT_INPUT_SYNTHESIS_ENVIRONMENT,
  options: InputSynthesisOptions = {},
): SynthesizedInputScript {
  if (!CALIBRATION_REGIMES.includes(regime)) {
    throw new RangeError("unknown input synthesis regime");
  }
  assertWellFormed(targetText);
  validateEnvironment(environment);
  if (profile === undefined) {
    if (environment.sampler_throttle_ms !== CALIBRATED_INPUT_PROFILE.sampler_throttle_ms) {
      throw new RangeError("the calibrated input profile requires sampler_throttle_ms=100");
    }
    return {
      version: "input-script/v1",
      calibration_status: INPUT_SYNTHESIS_PROFILE_ID,
      regime,
      seed_id: seedId(seed),
      target_text: targetText,
      environment: { sampler_throttle_ms: environment.sampler_throttle_ms },
      steps: synthesizeCalibratedInputScript(targetText, seed, regime, options),
    };
  }
  const selectedProfile = profile;
  validateProfile(selectedProfile);
  const rng = createNamedInputRng(seed);
  const characters = [...targetText];
  const steps: InputScriptStep[] = [];
  let index = 0;
  let burstRemaining = integerInRange(rng, selectedProfile.chars_per_burst);
  let betweenBursts = false;
  let forceOrdinaryNext = false;
  let targetOffsetUtf16 = 0;
  const compositionWait = (fullThrottleWindow = false): void => {
    steps.push({
      kind: "wait",
      ms: Math.max(
        1,
        fullThrottleWindow ? environment.sampler_throttle_ms : 0,
        integerInRange(
          rng,
          selectedProfile.within_burst_ms,
          "composition",
        ),
      ),
      role: "composition",
    });
  };
  const revisionWait = (): void => {
    steps.push({
      kind: "wait",
      ms: integerInRange(rng, selectedProfile.within_burst_ms),
      role: "revision",
    });
  };
  const appendLocalRevision = (
    prefix: readonly string[],
    substream: "revision" | "cursor",
  ): boolean => {
    if (prefix.length < 2) {
      return false;
    }
    const prefixText = prefix.join("");
    const boundaries = scalarBoundaries(prefixText);
    const endScalar = integerInRange(
      rng,
      [Math.max(1, prefix.length - 8), prefix.length - 1],
      substream,
    );
    const runLength = integerInRange(
      rng,
      [1, Math.min(3, endScalar)],
      substream,
    );
    const startScalar = endScalar - runLength;
    const start = boundaries[startScalar]!;
    const end = boundaries[endScalar]!;
    const original = prefix.slice(startScalar, endScalar).join("");
    const replacement = original === "x" ? "y" : "x";

    steps.push({ kind: "selection", start_utf16: end, end_utf16: end });
    revisionWait();
    for (let deleted = 0; deleted < runLength; deleted += 1) {
      steps.push({ kind: "delete" });
      if (deleted + 1 < runLength) {
        revisionWait();
      }
    }
    steps.push(
      rng.next("paste") < selectedProfile.paste_probability
        ? { kind: "paste", text: replacement }
        : { kind: "insert", text: replacement },
    );
    revisionWait();
    steps.push({
      kind: "selection",
      start_utf16: start,
      end_utf16: start + replacement.length,
    });
    steps.push({ kind: "delete" });
    steps.push(
      rng.next("paste") < selectedProfile.paste_probability
        ? { kind: "paste", text: original }
        : { kind: "insert", text: original },
    );
    steps.push({
      kind: "selection",
      start_utf16: prefixText.length,
      end_utf16: prefixText.length,
    });
    return true;
  };
  while (index < characters.length) {
    if (index > 0) {
      const previous = characters[index - 1]!;
      const punctuation = /[.!?,;:]/u.test(previous);
      const pauseRange = punctuation
        ? selectedProfile.punctuation_pause_ms
        : betweenBursts
          ? selectedProfile.between_burst_ms
          : selectedProfile.within_burst_ms;
      steps.push({
        kind: "wait",
        ms: integerInRange(rng, pauseRange),
        role: punctuation ? "punctuation" : betweenBursts ? "between-burst" : "within-burst",
      });
      if (betweenBursts) {
        burstRemaining = integerInRange(rng, selectedProfile.chars_per_burst);
        betweenBursts = false;
      }
      if (rng.next("timing") < selectedProfile.hesitation_probability) {
        steps.push({
          kind: "wait",
          ms: integerInRange(rng, selectedProfile.hesitation_ms),
          role: "hesitation",
        });
      }
    }

    const character = characters[index]!;
    let inserted = character;
    let consumed = 1;
    let compositionCommitted = false;
    const forceOrdinary = forceOrdinaryNext;
    forceOrdinaryNext = false;
    if (
      !forceOrdinary &&
      index + 1 < characters.length &&
      character.codePointAt(0)! > 0x7f &&
      rng.next("composition") < selectedProfile.composition_probability
    ) {
      steps.push({ kind: "compositionstart" });
      compositionWait(true);
      const updateCount = integerInRange(rng, [1, 4], "composition");
      for (let update = 0; update < updateCount; update += 1) {
        const updateText = update + 1 === updateCount ? character : update % 2 === 0 ? "·" : character;
        steps.push({ kind: "compositionupdate", text: updateText });
        compositionWait();
        if (update === 0 && rng.next("cursor") < selectedProfile.cursor_move_probability) {
          steps.push({
            kind: "selection",
            start_utf16: targetOffsetUtf16,
            end_utf16: targetOffsetUtf16 + updateText.length,
          });
          compositionWait();
        }
      }
      if (
        rng.next("composition") <
        selectedProfile.composition_cancel_probability
      ) {
        steps.push({ kind: "compositioncancel" });
        compositionWait();
        steps.push({ kind: "insert", text: character });
      } else {
        steps.push({ kind: "compositioncommit", text: character });
        compositionWait();
        compositionCommitted = true;
        forceOrdinaryNext = true;
      }
    } else if (
      !forceOrdinary &&
      index + 1 < characters.length &&
      rng.next("paste") < selectedProfile.paste_probability
    ) {
      consumed = Math.min(3, characters.length - index);
      inserted = characters.slice(index, index + consumed).join("");
      steps.push({ kind: "paste", text: inserted });
    } else {
      steps.push({ kind: "insert", text: character });
    }

    if (
      !compositionCommitted &&
      rng.next("revision") < selectedProfile.revision_probability
    ) {
      appendLocalRevision(
        characters.slice(0, index + consumed),
        "revision",
      );
    }
    index += consumed;
    targetOffsetUtf16 += inserted.length;
    burstRemaining -= consumed;
    if (burstRemaining <= 0 && index < characters.length) {
      betweenBursts = true;
    }
  }

  if (
    targetText &&
    rng.next("cursor") < selectedProfile.cursor_move_probability
  ) {
    appendLocalRevision(characters, "cursor");
  }

  return {
    version: "input-script/v1",
    calibration_status: "baseline-unfitted",
    regime,
    seed_id: seedId(seed),
    target_text: targetText,
    environment: {
      sampler_throttle_ms: environment.sampler_throttle_ms,
    },
    steps,
  };
}

export function summarizeInputScript(script: InputScript): InputScriptSummary {
  const summary: InputScriptSummary = {
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
  let state = createInputScriptState();
  let compositionUpdates = 0;
  let burstLength = 0;
  let burstDuration = 0;
  let deleteRun = 0;

  const finishBurst = (): void => {
    if (burstLength > 0) {
      summary.burst_lengths.push(burstLength);
      summary.burst_durations_ms.push(burstDuration);
      burstLength = 0;
      burstDuration = 0;
    }
  };
  const finishDeleteRun = (): void => {
    if (deleteRun > 0) {
      summary.delete_run_lengths.push(deleteRun);
      deleteRun = 0;
    }
  };
  for (const step of script) {
    if (step.kind === "wait") {
      summary.waits += 1;
      summary.wait_ms += step.ms;
      if (
        step.role === "between-burst" ||
        step.role === "punctuation" ||
        step.role === "hesitation"
      ) {
        finishBurst();
      } else if (burstLength > 0) {
        burstDuration += step.ms;
      }
      continue;
    }
    if (step.kind !== "delete") {
      finishDeleteRun();
    }
    switch (step.kind) {
      case "insert":
        summary.inserts += 1;
        burstLength += [...step.text].length;
        break;
      case "delete":
        summary.deletes += 1;
        summary.delete_locality_utf16.push(
          state.text.length - state.selection_end_utf16,
        );
        deleteRun += 1;
        break;
      case "selection":
        summary.selections += 1;
        summary.cursor_travel_utf16.push(
          Math.abs(step.start_utf16 - state.selection_end_utf16),
        );
        summary.selection_lengths_utf16.push(
          step.end_utf16 - step.start_utf16,
        );
        break;
      case "paste":
        summary.pastes += 1;
        summary.paste_lengths_utf16.push(step.text.length);
        burstLength += [...step.text].length;
        break;
      case "compositionstart":
        summary.compositions += 1;
        compositionUpdates = 0;
        break;
      case "compositionupdate":
        compositionUpdates += 1;
        break;
      case "compositioncommit":
        summary.ime_update_counts.push(compositionUpdates);
        burstLength += [...step.text].length;
        break;
      case "compositioncancel":
        summary.ime_update_counts.push(compositionUpdates);
        break;
    }
    state = transitionInputScriptState(state, step);
  }
  finishDeleteRun();
  finishBurst();
  return summary;
}

function assertRange(text: string, start: number, end: number): void {
  assertWellFormed(text);
  if (
    !Number.isSafeInteger(start) ||
    !Number.isSafeInteger(end) ||
    start < 0 ||
    end < start ||
    end > text.length ||
    !isScalarBoundary(text, start) ||
    !isScalarBoundary(text, end)
  ) {
    throw new RangeError("UTF-16 offsets must be valid Unicode-scalar textarea boundaries");
  }
}

function assertWellFormed(text: string): void {
  for (let offset = 0; offset < text.length; offset += 1) {
    const codeUnit = text.charCodeAt(offset);
    if (codeUnit >= 0xd800 && codeUnit <= 0xdbff) {
      const following = text.charCodeAt(offset + 1);
      if (!(following >= 0xdc00 && following <= 0xdfff)) {
        throw new RangeError("text must contain well-formed Unicode scalars");
      }
      offset += 1;
    } else if (codeUnit >= 0xdc00 && codeUnit <= 0xdfff) {
      throw new RangeError("text must contain well-formed Unicode scalars");
    }
  }
}

function isScalarBoundary(text: string, offset: number): boolean {
  if (offset <= 0 || offset >= text.length) {
    return true;
  }
  const previous = text.charCodeAt(offset - 1);
  const next = text.charCodeAt(offset);
  return !(previous >= 0xd800 && previous <= 0xdbff && next >= 0xdc00 && next <= 0xdfff);
}

function deletionRange(
  text: string,
  start: number,
  end: number,
  inputType: "deleteContentBackward" | "deleteContentForward",
): readonly [number, number] {
  assertRange(text, start, end);
  if (start !== end) {
    return [start, end];
  }
  if (inputType === "deleteContentBackward" && start > 0) {
    const previous = [...text.slice(0, start)].at(-1);
    return [start - (previous?.length ?? 0), start];
  }
  if (inputType === "deleteContentForward" && end < text.length) {
    const next = [...text.slice(end)].at(0);
    return [end, end + (next?.length ?? 0)];
  }
  return [start, end];
}

export function createInputScriptState(
  text = "",
  selectionStartUtf16 = text.length,
  selectionEndUtf16 = selectionStartUtf16,
): InputScriptState {
  assertRange(text, selectionStartUtf16, selectionEndUtf16);
  return {
    text,
    selection_start_utf16: selectionStartUtf16,
    selection_end_utf16: selectionEndUtf16,
    composition: null,
  };
}

function replaceState(
  state: InputScriptState,
  start: number,
  end: number,
  replacement: string,
): InputScriptState {
  assertRange(state.text, start, end);
  assertWellFormed(replacement);
  const cursor = start + replacement.length;
  return {
    ...state,
    text: `${state.text.slice(0, start)}${replacement}${state.text.slice(end)}`,
    selection_start_utf16: cursor,
    selection_end_utf16: cursor,
    composition: state.composition === null ? null : { ...state.composition },
  };
}

function requireComposition(
  state: InputScriptState,
  operation: "update" | "commit" | "cancel",
): InputScriptCompositionState {
  if (state.composition === null) {
    throw new Error(`composition ${operation} requires compositionstart`);
  }
  return state.composition;
}

/** The sole pure text/selection/composition interpreter for input scripts. */
export function transitionInputScriptState(
  state: InputScriptState,
  step: InputActionStep,
): InputScriptState {
  assertRange(
    state.text,
    state.selection_start_utf16,
    state.selection_end_utf16,
  );
  switch (step.kind) {
    case "insert":
      if (state.composition !== null) {
        throw new Error(
          "insert requires composition to be committed or canceled first",
        );
      }
      return replaceState(
        state,
        state.selection_start_utf16,
        state.selection_end_utf16,
        step.text,
      );
    case "delete": {
      if (state.composition !== null) {
        throw new Error(
          "delete requires composition to be committed or canceled first",
        );
      }
      const [start, end] = deletionRange(
        state.text,
        state.selection_start_utf16,
        state.selection_end_utf16,
        step.input_type ?? "deleteContentBackward",
      );
      return replaceState(state, start, end, "");
    }
    case "selection":
      assertRange(state.text, step.start_utf16, step.end_utf16);
      return {
        ...state,
        selection_start_utf16: step.start_utf16,
        selection_end_utf16: step.end_utf16,
        composition:
          state.composition === null ? null : { ...state.composition },
      };
    case "paste":
      if (state.composition !== null) {
        throw new Error(
          "paste requires composition to be committed or canceled first",
        );
      }
      return replaceState(
        state,
        state.selection_start_utf16,
        state.selection_end_utf16,
        step.text,
      );
    case "compositionstart":
      if (state.composition !== null) {
        throw new Error("compositionstart cannot nest");
      }
      return {
        ...state,
        composition: {
          original_text: state.text,
          original_start: state.selection_start_utf16,
          original_end: state.selection_end_utf16,
          start: state.selection_start_utf16,
          end: state.selection_end_utf16,
        },
      };
    case "compositionupdate": {
      const composition = requireComposition(state, "update");
      const next = replaceState(
        state,
        composition.start,
        composition.end,
        step.text,
      );
      return {
        ...next,
        composition: {
          ...composition,
          end: next.selection_end_utf16,
        },
      };
    }
    case "compositioncommit": {
      const composition = requireComposition(state, "commit");
      return {
        ...replaceState(
          state,
          composition.start,
          composition.end,
          step.text,
        ),
        composition: null,
      };
    }
    case "compositioncancel": {
      const composition = requireComposition(state, "cancel");
      return createInputScriptState(
        composition.original_text,
        composition.original_start,
        composition.original_end,
      );
    }
  }
}

function dispatchInput(textarea: HTMLTextAreaElement, inputType: string, data: string | null): void {
  textarea.dispatchEvent(new InputEvent("input", { inputType, data }));
  document.dispatchEvent(new Event("selectionchange"));
}

/** Apply non-time script steps to one textarea with browser-like DOM events. */
export function createInputScriptPlayer(textarea: HTMLTextAreaElement): {
  apply: (step: InputActionStep) => void;
} {
  let state = createInputScriptState(
    textarea.value,
    textarea.selectionStart,
    textarea.selectionEnd,
  );

  const focus = (): void => {
    if (document.activeElement !== textarea) {
      textarea.focus();
    }
  };
  const synchronizeExternalState = (): void => {
    if (
      state.composition === null &&
      (state.text !== textarea.value ||
        state.selection_start_utf16 !== textarea.selectionStart ||
        state.selection_end_utf16 !== textarea.selectionEnd)
    ) {
      state = createInputScriptState(
        textarea.value,
        textarea.selectionStart,
        textarea.selectionEnd,
      );
    }
  };

  return {
    apply: (step): void => {
      focus();
      synchronizeExternalState();
      const next = transitionInputScriptState(state, step);
      textarea.value = next.text;
      textarea.setSelectionRange(
        next.selection_start_utf16,
        next.selection_end_utf16,
      );
      state = next;
      switch (step.kind) {
        case "insert":
          dispatchInput(textarea, "insertText", step.text);
          return;
        case "delete":
          dispatchInput(
            textarea,
            step.input_type ?? "deleteContentBackward",
            null,
          );
          return;
        case "selection":
          document.dispatchEvent(new Event("selectionchange"));
          return;
        case "paste":
          dispatchInput(textarea, "insertFromPaste", step.text);
          return;
        case "compositionstart":
          textarea.dispatchEvent(new CompositionEvent("compositionstart", { data: step.data ?? "" }));
          return;
        case "compositionupdate":
          textarea.dispatchEvent(new CompositionEvent("compositionupdate", { data: step.text }));
          dispatchInput(textarea, "insertCompositionText", step.text);
          return;
        case "compositioncommit":
          textarea.dispatchEvent(new CompositionEvent("compositionend", { data: step.text }));
          dispatchInput(textarea, "insertCompositionText", step.text);
          return;
        case "compositioncancel":
          textarea.dispatchEvent(new CompositionEvent("compositionend", { data: "" }));
          return;
      }
    },
  };
}
