/** Deterministic, virtual-time materialization of one synthetic calibration bundle. */

import {
  CALIBRATION_RECORDING_VERSION,
  CALIBRATION_REGIMES,
  attachCalibrationRecorder,
  type CalibrationRecordingBundle,
  type CalibrationRegime,
} from "./calibration-recorder";
import {
  INPUT_SYNTHESIS_PROFILE_ID,
  synthesizeInputScript,
} from "./input-synthesis";
import { createSamplerHarness } from "./sampler-harness";

export type CalibrationSyntheticRequest = {
  runtime_session_id: string;
  regime: CalibrationRegime;
  seed: string | number;
  target_text: string;
  transient_texts: string[];
  input_profile_id: typeof INPUT_SYNTHESIS_PROFILE_ID;
  input_profile_sha256: string;
  materializer_sha256: string;
  target_source_sha256: string;
};

export type CalibrationSyntheticClock = {
  now: () => number;
  advanceTimersByTime: (milliseconds: number) => void;
};

export type CalibrationSyntheticBatchClock = CalibrationSyntheticClock & {
  /** Reset Vitest fake time before each independent calibration record. */
  reset: () => void;
};

export type CalibrationSyntheticBatchRequest = {
  format_version: "calibration-synthetic-request/v1";
  records: CalibrationSyntheticRequest[];
};

export type CalibrationSyntheticBatchResponse = {
  format_version: "calibration-synthetic-response/v1";
  input_profile_id: typeof INPUT_SYNTHESIS_PROFILE_ID;
  input_profile_sha256: string;
  materializer_sha256: string;
  records: CalibrationRecordingBundle[];
};

export const CALIBRATION_SYNTHETIC_REQUEST_VERSION = "calibration-synthetic-request/v1";
export const CALIBRATION_SYNTHETIC_RESPONSE_VERSION = "calibration-synthetic-response/v1";
export const CALIBRATION_SYNTHETIC_MAX_BATCH_RECORDS = 8;

const SYNTHETIC_PAUSE_MS = 1_500;
const REQUEST_KEYS = [
  "runtime_session_id",
  "regime",
  "seed",
  "target_text",
  "transient_texts",
  "input_profile_id",
  "input_profile_sha256",
  "materializer_sha256",
  "target_source_sha256",
] as const;
const BATCH_REQUEST_KEYS = ["format_version", "records"] as const;

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isDigest(value: unknown): value is string {
  return typeof value === "string" && /^sha256:[0-9a-f]{64}$/.test(value);
}

/** Validate the one JSON object accepted by the opt-in file adapter. */
export function parseCalibrationSyntheticRequest(value: unknown): CalibrationSyntheticRequest {
  if (!isObject(value) || Object.keys(value).length !== REQUEST_KEYS.length ||
    REQUEST_KEYS.some((key) => !(key in value))) {
    throw new RangeError(`calibration synthetic request must contain exactly: ${REQUEST_KEYS.join(", ")}`);
  }
  const {
    runtime_session_id: runtimeSessionId,
    regime,
    seed,
    target_text: targetText,
    transient_texts: transientTexts,
    input_profile_id: inputProfileId,
    input_profile_sha256: inputProfileSha256,
    materializer_sha256: materializerSha256,
    target_source_sha256: targetSourceSha256,
  } = value;
  if (typeof runtimeSessionId !== "string" || typeof targetText !== "string") {
    throw new RangeError("runtime_session_id and target_text must be strings");
  }
  if (!CALIBRATION_REGIMES.includes(regime as CalibrationRegime)) {
    throw new RangeError("regime must be one of the six calibration regimes");
  }
  if (typeof seed !== "string" && (typeof seed !== "number" || !Number.isFinite(seed))) {
    throw new RangeError("seed must be a string or finite number");
  }
  if (
    !Array.isArray(transientTexts) ||
    transientTexts.some((text) => typeof text !== "string") ||
    new Set(transientTexts).size !== transientTexts.length ||
    inputProfileId !== INPUT_SYNTHESIS_PROFILE_ID ||
    !isDigest(inputProfileSha256) ||
    !isDigest(materializerSha256) ||
    !isDigest(targetSourceSha256)
  ) {
    throw new RangeError("calibration synthetic request profile, digests, or transient_texts is invalid");
  }
  if (
    regime === "short-command-like-inputs" &&
    transientTexts.filter((text) => text.length > 0).length < 6
  ) {
    throw new RangeError("short-command-like-inputs requires six distinct transient_texts");
  }
  return {
    runtime_session_id: runtimeSessionId,
    regime: regime as CalibrationRegime,
    seed,
    target_text: targetText,
    transient_texts: transientTexts,
    input_profile_id: inputProfileId,
    input_profile_sha256: inputProfileSha256,
    materializer_sha256: materializerSha256,
    target_source_sha256: targetSourceSha256,
  };
}

/** Validate the strictly ordered, multi-record JSON request accepted by the file adapter. */
export function parseCalibrationSyntheticBatchRequest(value: unknown): CalibrationSyntheticBatchRequest {
  if (!isObject(value) || Object.keys(value).length !== BATCH_REQUEST_KEYS.length ||
    BATCH_REQUEST_KEYS.some((key) => !(key in value))) {
    throw new RangeError(
      `calibration synthetic batch request must contain exactly: ${BATCH_REQUEST_KEYS.join(", ")}`,
    );
  }
  if (value.format_version !== CALIBRATION_SYNTHETIC_REQUEST_VERSION || !Array.isArray(value.records)) {
    throw new RangeError("calibration synthetic batch request version or records is invalid");
  }
  const records = value.records.map(parseCalibrationSyntheticRequest);
  if (
    records.length === 0 ||
    records.length > CALIBRATION_SYNTHETIC_MAX_BATCH_RECORDS ||
    new Set(records.map((record) => record.runtime_session_id)).size !== records.length
  ) {
    throw new RangeError("calibration synthetic batch records must be bounded and have unique runtime_session_id values");
  }
  if (
    new Set(records.map((record) => record.input_profile_sha256)).size !== 1 ||
    new Set(records.map((record) => record.materializer_sha256)).size !== 1
  ) {
    throw new RangeError("calibration synthetic batch records must share profile and materializer digests");
  }
  return { format_version: CALIBRATION_SYNTHETIC_REQUEST_VERSION, records };
}

/**
 * Replay a synthesized script through the unmodified sampler and recorder.
 * The caller provides Vitest's fake clock, keeping this bridge free of I/O.
 */
export function materializeCalibrationSynthetic(
  request: CalibrationSyntheticRequest,
  clock: CalibrationSyntheticClock,
): CalibrationRecordingBundle {
  const script = synthesizeInputScript(
    request.target_text,
    request.seed,
    request.regime,
    undefined,
    undefined,
    { transient_texts: request.transient_texts },
  );
  const textarea = document.createElement("textarea");
  const recorder = attachCalibrationRecorder(textarea, {
    version: CALIBRATION_RECORDING_VERSION,
    runtime_session_id: request.runtime_session_id,
    regime: request.regime,
    now: clock.now,
  });
  const harness = createSamplerHarness({
    textarea,
    now: clock.now,
    advanceTimersByTime: clock.advanceTimersByTime,
    sampler_throttle_ms: script.environment.sampler_throttle_ms,
    pause_ms: SYNTHETIC_PAUSE_MS,
    onFrame: recorder.captureSamplerFrame,
  });

  try {
    harness.run(script.steps);
    harness.advance(SYNTHETIC_PAUSE_MS);
    const finalFrame = harness.frames.at(-1);
    if (textarea.value !== request.target_text || finalFrame?.activity !== "paused") {
      throw new Error("synthetic calibration replay did not reach its final paused target state");
    }
    return recorder.exportBundle();
  } finally {
    harness.detach();
    recorder.detach();
    textarea.remove();
  }
}

/** Materialize independent records in request order under one fake-timer process. */
export function materializeCalibrationSyntheticBatch(
  request: CalibrationSyntheticBatchRequest,
  clock: CalibrationSyntheticBatchClock,
): CalibrationSyntheticBatchResponse {
  return {
    format_version: CALIBRATION_SYNTHETIC_RESPONSE_VERSION,
    input_profile_id: INPUT_SYNTHESIS_PROFILE_ID,
    input_profile_sha256: request.records[0]!.input_profile_sha256,
    materializer_sha256: request.records[0]!.materializer_sha256,
    records: request.records.map((record) => {
      clock.reset();
      return materializeCalibrationSynthetic(record, clock);
    }),
  };
}
