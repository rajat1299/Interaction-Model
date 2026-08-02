/** Browser harness: sampler transport plus a deliberately non-policy UI. */

import "./style.css";
import type {
  CheckpointNoticeFrame,
  ClientSnapshotFrame,
  MarkRenderFrame,
  NudgeAnnotationFrame,
  RespondTextFrame,
  ServerRenderFrame,
  Span,
  TimerStatusFrame,
} from "./protocol";
import {
  CALIBRATION_RECORDING_VERSION,
  CALIBRATION_REGIMES,
  attachCalibrationRecorder,
  type CalibrationRecorder,
  type CalibrationRegime,
  type CalibrationRecordingBundle,
} from "./calibration-recorder";
import { attachSampler } from "./sampler";

type ConnectionState = "connecting" | "connected" | "disconnected" | "error";
type TimerEntry = TimerStatusFrame & { receivedAt: number };

const app = document.querySelector<HTMLDivElement>("#app");
const calibrationRegime = calibrationRegimeFromLocation();

if (app) {
  app.innerHTML = `
    <main>
      <header>
        <h1>Interaction Model harness</h1>
        <p id="connection-state" role="status" data-state="disconnected">Disconnected</p>
        <button id="reconnect" type="button">Connect</button>
      </header>
      <section aria-label="Editor">
        <label for="interaction-text">Type here</label>
        <textarea id="interaction-text" rows="12" spellcheck="true" ${calibrationRegime ? "disabled" : ""}></textarea>
      </section>
      ${
        calibrationRegime
          ? `<section aria-label="Calibration recording">
        <h2>Calibration recording</h2>
        <p id="calibration-status" role="status">Waiting for runtime session</p>
        <button id="calibration-download" type="button" disabled>Stop &amp; download JSON</button>
      </section>`
          : ""
      }
      <section aria-label="Timers">
        <h2>Timers</h2>
        <div id="timer-chips" aria-label="Timer status">No active timers</div>
      </section>
      <aside aria-label="Annotations">
        <h2>Annotations</h2>
        <ul id="annotations" aria-live="polite"></ul>
      </aside>
    </main>
  `;

  const textarea = app.querySelector<HTMLTextAreaElement>("#interaction-text")!;
  const connectionState = app.querySelector<HTMLParagraphElement>("#connection-state")!;
  const reconnect = app.querySelector<HTMLButtonElement>("#reconnect")!;
  const timerChips = app.querySelector<HTMLDivElement>("#timer-chips")!;
  const annotations = app.querySelector<HTMLUListElement>("#annotations")!;
  const calibrationStatus = app.querySelector<HTMLParagraphElement>("#calibration-status");
  const calibrationDownload = app.querySelector<HTMLButtonElement>("#calibration-download");
  const timers = new Map<string, TimerEntry>();
  let socket: WebSocket | undefined;
  let sessionId: string | undefined;
  let latestSamplerFrame: ClientSnapshotFrame | undefined;
  let calibrationRecorder: CalibrationRecorder | undefined;
  let calibrationBundle: CalibrationRecordingBundle | undefined;
  let calibrationCompleting = false;
  let calibrationInvalid = false;
  let calibrationRecoveryDownloaded = false;
  let samplerDetach: ReturnType<typeof attachSampler> | undefined;
  let renderedTimerText: string | undefined;
  let closed = false;

  const setConnectionState = (state: ConnectionState, detail?: string): void => {
    connectionState.dataset.state = state;
    connectionState.textContent = detail ? `${state}: ${detail}` : state;
    reconnect.disabled = state === "connecting" || state === "connected";
  };

  const appendAnnotation = (kind: string, text: string): void => {
    const item = document.createElement("li");
    item.textContent = `${kind}: ${text}`;
    annotations.append(item);
  };

  const duration = (milliseconds: number): string => {
    const totalSeconds = Math.max(0, Math.ceil(milliseconds / 1_000));
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;
    return minutes === 0 ? `${seconds}s` : `${minutes}m ${seconds}s`;
  };

  const renderTimerChips = (): void => {
    if (timers.size === 0) {
      if (renderedTimerText !== "No active timers") {
        timerChips.replaceChildren();
        timerChips.textContent = "No active timers";
        renderedTimerText = "No active timers";
      }
      return;
    }
    const chipTexts = [...timers.values()].map((timer) => {
      const remaining =
        timer.next_due_in_ms === null
          ? null
          : Math.max(0, timer.next_due_in_ms - (performance.now() - timer.receivedAt));
      const text =
        timer.status === "canceled"
          ? `${timer.message} · canceled`
          : `${timer.message} · every ${duration(timer.interval_ms)} · next ${duration(remaining ?? 0)}`;
      return { text, title: `Timer ${timer.timer_id}, fire ${timer.fire_count}` };
    });
    const nextRenderedTimerText = chipTexts.map((chip) => `${chip.title}|${chip.text}`).join("\n");
    if (renderedTimerText === nextRenderedTimerText) {
      return;
    }
    timerChips.replaceChildren();
    for (const { text, title } of chipTexts) {
      const chip = document.createElement("span");
      chip.textContent = text;
      chip.title = title;
      timerChips.append(chip);
    }
    renderedTimerText = nextRenderedTimerText;
  };

  const receive = (frame: ServerRenderFrame): void => {
    switch (frame.type) {
      case "nudge_annotation":
        appendAnnotation("Nudge", frame.message);
        return;
      case "mark_render":
        appendAnnotation("Mark", frame.target.text);
        return;
      case "respond_text":
        appendAnnotation("Response", frame.text);
        return;
      case "timer_status":
        timers.set(frame.timer_id, { ...frame, receivedAt: performance.now() });
        renderTimerChips();
        return;
      case "checkpoint_notice":
        appendAnnotation("Checkpoint", `segment ${frame.segment_index}`);
    }
  };

  const sendLatestSamplerFrame = (): void => {
    if (socket?.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify(latestSamplerFrame));
    }
  };

  const startSampler = (): void => {
    samplerDetach = attachSampler(textarea, (frame: ClientSnapshotFrame) => {
      latestSamplerFrame = frame;
      calibrationRecorder?.captureSamplerFrame(frame);
      sendLatestSamplerFrame();
    });
  };

  if (!calibrationRegime) {
    startSampler();
  }

  const freezeCalibration = (): CalibrationRecordingBundle | undefined => {
    textarea.disabled = true;
    samplerDetach?.({ flushPending: true });
    samplerDetach = undefined;
    if (calibrationRecorder) {
      calibrationRecorder.detach();
      calibrationBundle = calibrationRecorder.exportBundle();
      calibrationRecorder = undefined;
    }
    return calibrationBundle;
  };

  const downloadCalibrationRecovery = (bundle: CalibrationRecordingBundle): void => {
    if (!calibrationRecoveryDownloaded) {
      downloadCalibrationBundle(bundle, true);
      calibrationRecoveryDownloaded = true;
    }
  };

  const stopAndDownloadCalibration = async (): Promise<void> => {
    if (calibrationCompleting) {
      return;
    }
    calibrationCompleting = true;
    calibrationDownload!.disabled = true;
    const bundle = freezeCalibration();
    if (!bundle) {
      calibrationCompleting = false;
      return;
    }
    try {
      const response = await fetch(
        `/session/${encodeURIComponent(bundle.runtime_session_id)}/calibration-complete`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            last_client_ts: bundle.sampler_frames.at(-1)?.frame.client_ts ?? null,
            sampler_frame_count: bundle.sampler_frames.length,
          }),
        },
      );
      if (!response.ok) {
        throw new Error(`calibration completion failed (${response.status})`);
      }
      downloadCalibrationBundle(bundle);
      calibrationStatus!.textContent = "Calibration stopped; JSON downloaded";
    } catch {
      downloadCalibrationRecovery(bundle);
      calibrationCompleting = false;
      calibrationStatus!.textContent =
        "Calibration completion failed; incomplete JSON downloaded; retry completion";
      calibrationDownload!.disabled = false;
    }
  };

  if (calibrationDownload) {
    calibrationDownload.addEventListener("click", () => {
      void stopAndDownloadCalibration();
    });
  }

  const createWebSocketUrl = (sessionId: string): string => {
    const url = new URL(`/session/${encodeURIComponent(sessionId)}`, window.location.href);
    url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
    return url.toString();
  };

  const connect = async (): Promise<void> => {
    if (
      closed ||
      calibrationInvalid ||
      (calibrationRegime !== undefined && calibrationBundle !== undefined) ||
      socket?.readyState === WebSocket.OPEN ||
      socket?.readyState === WebSocket.CONNECTING
    ) {
      return;
    }
    setConnectionState("connecting");
    try {
      if (sessionId === undefined) {
        const response = await fetch(calibrationRegime ? "/session?calibration=true" : "/session", {
          method: "POST",
        });
        if (!response.ok) {
          throw new Error(`session request failed (${response.status})`);
        }
        const body: unknown = await response.json();
        if (!isSessionCreated(body)) {
          throw new Error("session response did not contain a session_id");
        }
        sessionId = body.session_id;
      }
      const candidate = new WebSocket(createWebSocketUrl(sessionId));
      socket = candidate;
      candidate.addEventListener("open", () => {
        if (socket === candidate) {
          setConnectionState("connected");
          if (calibrationRegime && !calibrationRecorder && !calibrationBundle) {
            calibrationRecorder = attachCalibrationRecorder(textarea, {
              version: CALIBRATION_RECORDING_VERSION,
              runtime_session_id: sessionId!,
              regime: calibrationRegime,
            });
            startSampler();
            textarea.disabled = false;
            calibrationStatus!.textContent = `Recording calibration: ${calibrationRegime}`;
            calibrationDownload!.disabled = false;
          } else {
            sendLatestSamplerFrame();
          }
        }
      });
      candidate.addEventListener("message", (event) => {
        if (socket !== candidate || typeof event.data !== "string") {
          return;
        }
        const frame = parseServerRenderFrame(event.data);
        if (frame) {
          receive(frame);
        }
      });
      candidate.addEventListener("error", () => {
        if (socket === candidate) {
          setConnectionState("error", "WebSocket error");
        }
      });
      candidate.addEventListener("close", () => {
        if (socket === candidate) {
          socket = undefined;
          if (!closed) {
            if (calibrationRegime && calibrationRecorder && !calibrationBundle) {
              calibrationInvalid = true;
              const recovery = freezeCalibration();
              if (recovery) {
                downloadCalibrationRecovery(recovery);
              }
              calibrationStatus!.textContent =
                "Calibration connection lost; incomplete JSON downloaded";
              calibrationDownload!.disabled = true;
              setConnectionState("error", "calibration recording disconnected");
              reconnect.disabled = true;
              return;
            }
            setConnectionState("disconnected");
            if (calibrationRegime && calibrationBundle) {
              downloadCalibrationRecovery(calibrationBundle);
              calibrationStatus!.textContent =
                "Calibration connection lost; incomplete JSON downloaded";
              reconnect.disabled = true;
            }
          }
        }
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : "unknown connection error";
      setConnectionState("error", message);
    }
  };

  reconnect.addEventListener("click", () => {
    void connect();
  });
  const countdownInterval = window.setInterval(renderTimerChips, 250);
  window.addEventListener("beforeunload", () => {
    closed = true;
    window.clearInterval(countdownInterval);
    samplerDetach?.();
    calibrationRecorder?.detach();
    socket?.close();
  });
  void connect();
}

function calibrationRegimeFromLocation(): CalibrationRegime | undefined {
  const values = new URLSearchParams(window.location.search).getAll("calibration");
  return values.length === 1 ? CALIBRATION_REGIMES.find((regime) => regime === values[0]) : undefined;
}

function downloadCalibrationBundle(
  bundle: CalibrationRecordingBundle,
  incomplete = false,
): void {
  const blob = new Blob([JSON.stringify(bundle, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `${incomplete ? "incomplete-" : ""}calibration-${bundle.regime}.json`;
  link.click();
  URL.revokeObjectURL(url);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isString(value: unknown): value is string {
  return typeof value === "string";
}

function isNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function isSpan(value: unknown): value is Span {
  return (
    isRecord(value) &&
    isString(value.event_id) &&
    isNumber(value.start_utf16) &&
    isNumber(value.end_utf16) &&
    isString(value.text)
  );
}

function isSessionCreated(value: unknown): value is { session_id: string } {
  return isRecord(value) && isString(value.session_id);
}

function isNudge(value: Record<string, unknown>): value is NudgeAnnotationFrame {
  return (
    value.type === "nudge_annotation" &&
    isString(value.action_event_id) &&
    isString(value.fire_event_id) &&
    isString(value.timer_id) &&
    isString(value.message) &&
    isNumber(value.fire_count) &&
    isNumber(value.missed_count)
  );
}

function isMark(value: Record<string, unknown>): value is MarkRenderFrame {
  return (
    value.type === "mark_render" &&
    isString(value.action_event_id) &&
    isSpan(value.instruction) &&
    isSpan(value.target)
  );
}

function isResponse(value: Record<string, unknown>): value is RespondTextFrame {
  return (
    value.type === "respond_text" &&
    isString(value.action_event_id) &&
    isString(value.reply_to_event_id) &&
    isString(value.text)
  );
}

function isTimerStatus(value: Record<string, unknown>): value is TimerStatusFrame {
  return (
    value.type === "timer_status" &&
    isString(value.timer_id) &&
    isString(value.instruction_id) &&
    isNumber(value.interval_ms) &&
    isString(value.message) &&
    (value.status === "active" || value.status === "canceled") &&
    (value.next_due_in_ms === null || isNumber(value.next_due_in_ms)) &&
    isNumber(value.fire_count)
  );
}

function isCheckpoint(value: Record<string, unknown>): value is CheckpointNoticeFrame {
  return (
    value.type === "checkpoint_notice" &&
    isString(value.checkpoint_event_id) &&
    isNumber(value.segment_index) &&
    isNumber(value.covers_through_policy_seq)
  );
}

function parseServerRenderFrame(raw: string): ServerRenderFrame | undefined {
  try {
    const value: unknown = JSON.parse(raw);
    if (!isRecord(value)) {
      return undefined;
    }
    if (isNudge(value) || isMark(value) || isResponse(value) || isTimerStatus(value) || isCheckpoint(value)) {
      return value;
    }
  } catch {
    // The server is expected to send valid frames; malformed transport data is ignored.
  }
  return undefined;
}
