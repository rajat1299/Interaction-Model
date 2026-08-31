/** Film entrypoint for a live clean session or a read-only durable replay. */

import "./film.css";
import { attachSampler } from "./sampler";
import type {
  ClientSnapshotFrame,
  DecisionTraceV1,
  FilmLiveFrame,
  FilmReplay,
  FilmReplayEvent,
  JsonValue,
  MarkRenderFrame,
  ParsedPolicyIntent,
  ServerRenderFrame,
  Span,
  TimerStatusFrame,
} from "./protocol";

type FilmMode = "clean" | "technical";
type RailEntry = { id: string; text: string };
type HeldContext = { id: string; text: string; query: string; source: string };
type RenderedLine = { id: string; kind: "response" | "nudge" | "integration"; text: string };

const app = document.querySelector<HTMLDivElement>("#app");

if (app) {
  const parameters = new URLSearchParams(window.location.search);
  const mode: FilmMode = parameters.get("mode") === "technical" ? "technical" : "clean";
  const replaySessionId = parameters.get("session")?.trim() || null;

  app.innerHTML = `
    <a class="skip-link" href="#film-document">Skip to document</a>
    <main class="film">
      <header class="film__header">
        <h1 class="film__title">Interaction Model</h1>
        <p class="film__clock" id="film-clock" role="status">${mode === "clean" ? "sampling..." : "recorded"}</p>
      </header>
      <section class="film__workspace" aria-label="Interaction record">
        <article class="document" id="film-document" aria-label="Live document">
          <div class="document__text" id="document-text"><span class="document__empty">Start writing.</span></div>
          <div class="document__responses" id="document-responses" aria-live="polite"></div>
        </article>
        <aside class="rail" aria-label="${mode === "clean" ? "Model actions" : "Recorded decision traces"}">
          <section class="rail__section" id="context-section" hidden>
            <h2 class="rail__heading">Internal context</h2>
            <div id="context-list"></div>
          </section>
          <section class="rail__section">
            <h2 class="rail__heading">${mode === "clean" ? "Model actions" : "Decision traces"}</h2>
            <ol class="action-list" id="action-list"></ol>
            ${mode === "technical" ? '<div class="technical-list" id="technical-list"></div>' : ""}
          </section>
        </aside>
      </section>
      <section class="composer" aria-label="Composer">
        <label class="composer__label" for="film-input">Document text</label>
        <textarea class="composer__input" id="film-input" rows="3" spellcheck="true" ${mode === "technical" ? "readonly" : "disabled"}></textarea>
        ${mode === "clean" ? '<button class="composer__reset" id="new-take" type="button">Reset</button>' : ""}
      </section>
    </main>
  `;

  const clock = required<HTMLParagraphElement>("#film-clock");
  const documentText = required<HTMLDivElement>("#document-text");
  const documentResponses = required<HTMLDivElement>("#document-responses");
  const textarea = required<HTMLTextAreaElement>("#film-input");
  const actionList = required<HTMLOListElement>("#action-list");
  const technicalList =
    mode === "technical" ? required<HTMLDivElement>("#technical-list") : null;
  const contextSection = required<HTMLElement>("#context-section");
  const contextList = required<HTMLDivElement>("#context-list");
  const newTake = document.querySelector<HTMLButtonElement>("#new-take");
  const marks: MarkRenderFrame[] = [];
  const railEntries: RailEntry[] = [];
  const heldContexts = new Map<string, HeldContext>();
  const timers = new Map<string, TimerStatusFrame>();
  const renderedLines: RenderedLine[] = [];
  const traces: DecisionTraceV1[] = [];
  const seenTraceHashes = new Set<string>();
  let currentText = "";
  let latestSamplerFrame: ClientSnapshotFrame | undefined;
  let socket: WebSocket | undefined;
  let detachSampler: ReturnType<typeof attachSampler> | undefined;
  let closed = false;
  let currentSessionId: string | undefined;
  let takeGeneration = 0;
  let decisionCount = 0;
  let cleanWarmupReady = mode === "technical";
  let cleanWarmupFailed = false;
  const startedAt = performance.now();

  const renderDocument = (): void => {
    documentText.replaceChildren();
    if (!currentText) {
      const empty = document.createElement("span");
      empty.className = "document__empty";
      empty.textContent = mode === "technical" ? "No recorded document text." : "Start writing.";
      documentText.append(empty);
      return;
    }
    const visibleMarks = marks
      .map((frame) => frame.target)
      .filter((span) => currentText.slice(span.start_utf16, span.end_utf16) === span.text)
      .sort((left, right) => left.start_utf16 - right.start_utf16 || left.end_utf16 - right.end_utf16);
    let cursor = 0;
    for (const span of visibleMarks) {
      if (span.start_utf16 < cursor) {
        continue;
      }
      documentText.append(document.createTextNode(currentText.slice(cursor, span.start_utf16)));
      const mark = document.createElement("mark");
      mark.textContent = currentText.slice(span.start_utf16, span.end_utf16);
      documentText.append(mark);
      cursor = span.end_utf16;
    }
    documentText.append(document.createTextNode(currentText.slice(cursor)));
  };

  const renderResponses = (): void => {
    documentResponses.replaceChildren(
      ...renderedLines.map((line) => {
        const paragraph = document.createElement("p");
        paragraph.dataset.kind = line.kind;
        paragraph.textContent = line.text;
        return paragraph;
      }),
    );
  };

  const renderRail = (latestTrace?: DecisionTraceV1): void => {
    if (mode === "clean") {
      actionList.hidden = false;
      actionList.replaceChildren(
        ...railEntries.map((entry) => {
          const item = document.createElement("li");
          item.dataset.decisionId = entry.id;
          item.textContent = entry.text;
          return item;
        }),
      );
      return;
    }
    actionList.hidden = true;
    actionList.replaceChildren();
    if (latestTrace) {
      const details = document.createElement("details");
      details.className = "trace";
      const summary = document.createElement("summary");
      summary.textContent = traceSummary(latestTrace);
      const pre = document.createElement("pre");
      pre.textContent = JSON.stringify(latestTrace, null, 2);
      details.append(summary, pre);
      technicalList?.prepend(details);
    }
  };

  const renderContext = (): void => {
    const rows = [
      ...heldContexts.values(),
      ...[...timers.values()]
        .filter((timer) => timer.status === "active")
        .map((timer) => ({
          id: timer.timer_id,
          text: timer.message,
          query: `every ${formatDuration(timer.interval_ms)}`,
          source: "timer",
        })),
    ];
    contextSection.hidden = rows.length === 0;
    contextList.replaceChildren(
      ...rows.map((context) => {
        const row = document.createElement("div");
        row.className = "context-row";
        const value = document.createElement("span");
        value.textContent = context.text;
        const source = document.createElement("span");
        source.className = "context-row__source";
        source.textContent = context.source;
        const query = document.createElement("span");
        query.className = "context-row__query";
        query.textContent = context.query;
        row.append(value, source, query);
        return row;
      }),
    );
  };

  const applyTrace = (trace: DecisionTraceV1): void => {
    if (seenTraceHashes.has(trace.audit_sha256)) {
      return;
    }
    seenTraceHashes.add(trace.audit_sha256);
    decisionCount += 1;
    if (mode === "technical") {
      traces.push(trace);
    }
    const intent = trace.parsed_raw_intent;
    const action = resolvedAction(trace.resolution);
    if (mode === "clean" && intent && intent.type !== "idle" && isExecuted(trace.executed_event)) {
      railEntries.unshift({
        id: trace.decision_id,
        text: summarizeIntent(intent, action, trace.effect, timers),
      });
    }
    if (action?.type === "skip" && isExecuted(trace.executed_event)) {
      const targetEventId = stringField(action, "target_event_id");
      if (targetEventId) {
        heldContexts.delete(targetEventId);
        renderContext();
      }
    }
    if (action?.type === "integrate" && isExecuted(trace.executed_event)) {
      const text = stringField(action, "text");
      const resultEventId = stringField(action, "result_event_id");
      if (text && !renderedLines.some((line) => line.id === trace.audit_sha256)) {
        renderedLines.push({ id: trace.audit_sha256, kind: "integration", text });
      }
      if (resultEventId) {
        heldContexts.delete(resultEventId);
      }
      renderResponses();
      renderContext();
    }
    renderRail(mode === "technical" ? trace : undefined);
    clock.textContent = mode === "technical" ? `recorded · ${decisionCount} decisions` : elapsed();
  };

  const applyRenderFrame = (frame: ServerRenderFrame): void => {
    switch (frame.type) {
      case "mark_render":
        marks.push(frame);
        renderDocument();
        return;
      case "respond_text":
        appendRenderedLine(frame.action_event_id, "response", frame.text);
        return;
      case "nudge_annotation":
        appendRenderedLine(frame.action_event_id, "nudge", frame.message);
        return;
      case "timer_status":
        timers.set(frame.timer_id, frame);
        renderContext();
        return;
      case "held_context":
        heldContexts.set(frame.result_event_id, {
          id: frame.result_event_id,
          text: frame.text,
          query: frame.query,
          source: frame.source,
        });
        renderContext();
        return;
      case "checkpoint_notice":
        return;
    }
  };

  const appendRenderedLine = (
    id: string,
    kind: RenderedLine["kind"],
    text: string,
  ): void => {
    if (!renderedLines.some((line) => line.id === id)) {
      renderedLines.push({ id, kind, text });
      renderResponses();
    }
  };

  const applyReplayEvent = (event: FilmReplayEvent): void => {
    if (event.type === "snapshot_projection") {
      currentText = event.text;
      textarea.value = event.text;
      renderDocument();
    } else if (event.type === "decision_trace") {
      applyTrace(event.trace);
    } else {
      applyRenderFrame(event);
    }
  };

  const showFailure = (message: string): void => {
    if (mode === "clean") {
      cleanWarmupReady = false;
      cleanWarmupFailed = true;
      textarea.disabled = true;
    }
    clock.textContent = "unavailable";
    const paragraph = document.createElement("p");
    paragraph.className = "film__error";
    paragraph.textContent = message;
    documentText.replaceChildren(paragraph);
  };

  const startClean = async (): Promise<void> => {
    const generation = ++takeGeneration;
    cleanWarmupReady = false;
    cleanWarmupFailed = false;
    textarea.disabled = true;
    let warmupBaselineCaptured = false;
    let warmupBaselineText = "";
    let warmupPausePending = false;
    let firstUserSegmentPending = true;
    let firstUserSegmentStarted = false;
    let decisionInFlight = false;
    const sendLatestFrame = (): void => {
      if (
        generation !== takeGeneration ||
        closed ||
        decisionInFlight ||
        !latestSamplerFrame ||
        socket?.readyState !== WebSocket.OPEN
      ) {
        return;
      }
      const frame = latestSamplerFrame;
      latestSamplerFrame = undefined;
      decisionInFlight = true;
      socket.send(JSON.stringify(frame));
    };
    detachSampler?.({ flushPending: false });
    detachSampler = attachSampler(textarea, (frame) => {
      if (!cleanWarmupReady && warmupBaselineCaptured) {
        warmupPausePending = false;
        return;
      }
      if (warmupPausePending) {
        warmupPausePending = false;
        if (frame.activity === "paused") {
          return;
        }
      }
      if (!warmupBaselineCaptured) {
        warmupBaselineCaptured = true;
        warmupBaselineText = frame.text;
        warmupPausePending = true;
      }
      currentText = frame.text;
      renderDocument();
      clock.textContent = "sampling...";
      if (cleanWarmupReady && firstUserSegmentPending) {
        if (!firstUserSegmentStarted && frame.text === warmupBaselineText) {
          latestSamplerFrame = undefined;
          return;
        }
        firstUserSegmentStarted = true;
        if (frame.activity === "active") {
          latestSamplerFrame = undefined;
          return;
        }
        firstUserSegmentPending = false;
      }
      latestSamplerFrame = frame;
      sendLatestFrame();
    });
    try {
      const response = await fetch("/session", { method: "POST" });
      if (!response.ok) {
        throw new Error(`session request failed (${response.status})`);
      }
      const body = await response.json();
      if (!isSessionCreated(body)) {
        throw new Error("session request returned an invalid response");
      }
      if (closed || generation !== takeGeneration) {
        void stopSession(body.session_id, true);
        return;
      }
      currentSessionId = body.session_id;
      socket = new WebSocket(webSocketUrl(body.session_id));
      socket.addEventListener("open", () => {
        if (generation === takeGeneration) {
          sendLatestFrame();
        }
      });
      socket.addEventListener("message", (message) => {
        if (generation !== takeGeneration) {
          return;
        }
        const frame = parseLiveFrame(message.data);
        if (!frame) {
          socket?.close();
          showFailure("The session returned an invalid film event.");
          return;
        }
        if (frame.type === "decision_trace") {
          if (cleanWarmupFailed) {
            return;
          }
          if (!cleanWarmupReady) {
            if (frame.trace.parsed_raw_intent === null) {
              detachSampler?.({ flushPending: false });
              detachSampler = undefined;
              latestSamplerFrame = undefined;
              decisionInFlight = false;
              showFailure("The session warm-up decision was invalid.");
              return;
            }
            decisionInFlight = false;
            cleanWarmupReady = true;
            applyTrace(frame.trace);
            textarea.disabled = false;
            textarea.focus();
            sendLatestFrame();
            return;
          }
          decisionInFlight = false;
          applyTrace(frame.trace);
          sendLatestFrame();
        } else {
          applyRenderFrame(frame);
        }
      });
      socket.addEventListener("close", () => {
        if (!closed && generation === takeGeneration && !cleanWarmupFailed) {
          clock.textContent = "disconnected";
        }
      });
      socket.addEventListener("error", () => {
        if (generation === takeGeneration) {
          clock.textContent = "unavailable";
        }
      });
    } catch (error) {
      if (generation === takeGeneration) {
        detachSampler?.({ flushPending: false });
        detachSampler = undefined;
        showFailure(error instanceof Error ? error.message : "The session could not be opened.");
      }
    }
  };

  const stopSession = async (sessionId: string, keepalive = false): Promise<boolean> => {
    try {
      const response = await fetch(`/session/${encodeURIComponent(sessionId)}/stop`, {
        method: "POST",
        keepalive,
      });
      return response.ok;
    } catch {
      // The sandbox remains server-owned if the browser disappears mid-stop.
      return false;
    }
  };

  const clearTake = (): void => {
    currentText = "";
    latestSamplerFrame = undefined;
    textarea.disabled = mode === "clean";
    marks.length = 0;
    railEntries.length = 0;
    heldContexts.clear();
    timers.clear();
    renderedLines.length = 0;
    traces.length = 0;
    decisionCount = 0;
    seenTraceHashes.clear();
    textarea.value = "";
    renderDocument();
    renderResponses();
    renderRail();
    renderContext();
    clock.textContent = "sampling...";
  };

  newTake?.addEventListener("click", async () => {
    newTake.disabled = true;
    takeGeneration += 1;
    detachSampler?.({ flushPending: false });
    detachSampler = undefined;
    socket?.close();
    socket = undefined;
    const oldSession = currentSessionId;
    currentSessionId = undefined;
    if (oldSession) {
      if (!(await stopSession(oldSession))) {
        currentSessionId = oldSession;
        showFailure("The previous sandbox could not be stopped.");
        newTake.disabled = false;
        return;
      }
    }
    clearTake();
    await startClean();
    newTake.disabled = false;
  });

  const startTechnical = async (): Promise<void> => {
    if (!replaySessionId) {
      showFailure("Technical mode needs an existing session id in the URL.");
      return;
    }
    try {
      const response = await fetch(
        `/session/${encodeURIComponent(replaySessionId)}/decision-traces`,
        { method: "GET" },
      );
      if (!response.ok) {
        throw new Error(`recorded session request failed (${response.status})`);
      }
      const replay = await response.json();
      if (!isFilmReplay(replay)) {
        throw new Error("recorded session returned an invalid event stream");
      }
      if (replay.session_id !== replaySessionId) {
        throw new Error("recorded session id does not match the requested session");
      }
      for (const event of replay.events) {
        applyReplayEvent(event);
      }
      clock.textContent = `recorded · ${decisionCount} decisions`;
    } catch (error) {
      showFailure(error instanceof Error ? error.message : "The recorded session could not be read.");
    }
  };

  window.addEventListener("beforeunload", () => {
    closed = true;
    takeGeneration += 1;
    detachSampler?.({ flushPending: false });
    socket?.close();
    if (currentSessionId) {
      void stopSession(currentSessionId, true);
    }
  });

  if (mode === "technical") {
    void startTechnical();
  } else {
    void startClean();
  }

  function elapsed(): string {
    return `t=${((performance.now() - startedAt) / 1_000).toFixed(2)}s`;
  }
}

function required<T extends Element>(selector: string): T {
  const element = document.querySelector<T>(selector);
  if (!element) {
    throw new Error(`film element missing: ${selector}`);
  }
  return element;
}

function summarizeIntent(
  intent: ParsedPolicyIntent,
  action: { [key: string]: JsonValue } | null,
  effect: JsonValue,
  timers: ReadonlyMap<string, TimerStatusFrame>,
): string {
  switch (intent.type) {
    case "mark":
      return `called out ${stringField(intent, "text") ?? "text"}`;
    case "delegate":
      return "delegate lookup";
    case "integrate":
      return `integrated ${stringField(action, "text") ?? "held result"}`;
    case "skip":
      return `skipped ${humanize(stringField(intent, "reason") ?? "result")}`;
    case "respond":
      return "responded";
    case "schedule":
      return scheduleSummary(action);
    case "cancel":
      return `canceled ${knownTimerMessage(action, effect, timers) ?? "reminder"}`;
    case "nudge":
      return `nudged ${knownTimerMessage(action, effect, timers) ?? "reminder"}`;
    case "idle":
      return "";
  }
}

function scheduleSummary(action: { [key: string]: JsonValue } | null): string {
  const message = stringField(action, "message") ?? "recurring reminder";
  const interval = numberField(action, "interval_ms");
  return interval === null ? `scheduled ${message}` : `scheduled ${message} · every ${formatDuration(interval)}`;
}

function knownTimerMessage(
  action: { [key: string]: JsonValue } | null,
  effect: JsonValue,
  timers: ReadonlyMap<string, TimerStatusFrame>,
): string | null {
  if (isRecord(action?.target)) {
    const timerId = stringField(action.target, "timer_id");
    if (timerId && timers.has(timerId)) {
      return timers.get(timerId)?.message ?? null;
    }
  }
  if (!isRecord(effect)) {
    return null;
  }
  const renderFrames = effect.render_frames;
  if (Array.isArray(renderFrames)) {
    for (const frame of renderFrames) {
      const message = stringField(frame, "message");
      if (message) {
        return message;
      }
    }
  }
  const effectTimers = effect.timers;
  if (Array.isArray(effectTimers)) {
    for (const timer of effectTimers) {
      const message = stringField(timer, "message");
      if (message) {
        return message;
      }
    }
  }
  return null;
}

function traceSummary(trace: DecisionTraceV1): string {
  const intent = trace.parsed_raw_intent;
  return intent ? `${trace.decision_id} · ${humanize(intent.type)}` : `${trace.decision_id} · unresolved`;
}

function humanize(value: string): string {
  return value.replaceAll("_", " ");
}

function formatDuration(milliseconds: number): string {
  const seconds = Math.max(1, Math.round(milliseconds / 1_000));
  return seconds < 60 ? `${seconds}s` : `${Math.round(seconds / 60)}m`;
}

function webSocketUrl(sessionId: string): string {
  const url = new URL(`/session/${encodeURIComponent(sessionId)}`, window.location.href);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  return url.toString();
}

function stringField(value: JsonValue, key: string): string | null {
  return isRecord(value) && typeof value[key] === "string" ? value[key] : null;
}

function numberField(value: JsonValue, key: string): number | null {
  return isRecord(value) && typeof value[key] === "number" ? value[key] : null;
}

function resolvedAction(resolution: JsonValue): { [key: string]: JsonValue } | null {
  if (!isRecord(resolution)) {
    return null;
  }
  const action = resolution.action;
  if (isRecord(action) && typeof action.type === "string") {
    return action;
  }
  const value = resolution.value;
  if (isRecord(value) && typeof value.type === "string") {
    return value;
  }
  return typeof resolution.type === "string" ? resolution : null;
}

function isExecuted(event: JsonValue): boolean {
  return isRecord(event) && (event.kind === "action_executed" || event.type === "action_executed");
}

function isSessionCreated(value: unknown): value is { session_id: string } {
  return isRecord(value) && typeof value.session_id === "string" && value.session_id.length > 0;
}

function parseLiveFrame(raw: unknown): FilmLiveFrame | null {
  if (typeof raw !== "string") {
    return null;
  }
  try {
    const value: unknown = JSON.parse(raw);
    return isLiveFrame(value) ? value : null;
  } catch {
    return null;
  }
}

function isFilmReplay(value: unknown): value is FilmReplay {
  return (
    isRecord(value) &&
    typeof value.session_id === "string" &&
    Array.isArray(value.events) &&
    value.events.every(isReplayEvent)
  );
}

function isReplayEvent(value: unknown): value is FilmReplayEvent {
  return (
    isLiveFrame(value) ||
    (isRecord(value) &&
      value.type === "snapshot_projection" &&
      typeof value.event_id === "string" &&
      typeof value.text === "string" &&
      (value.client_ts === null || typeof value.client_ts === "number"))
  );
}

function isLiveFrame(value: unknown): value is FilmLiveFrame {
  if (!isRecord(value) || typeof value.type !== "string") {
    return false;
  }
  switch (value.type) {
    case "decision_trace":
      return isDecisionTrace(value.trace);
    case "mark_render":
      return typeof value.action_event_id === "string" && isSpan(value.instruction) && isSpan(value.target);
    case "respond_text":
      return (
        typeof value.action_event_id === "string" &&
        typeof value.reply_to_event_id === "string" &&
        typeof value.text === "string"
      );
    case "nudge_annotation":
      return (
        typeof value.action_event_id === "string" &&
        typeof value.fire_event_id === "string" &&
        typeof value.timer_id === "string" &&
        typeof value.message === "string" &&
        typeof value.fire_count === "number" &&
        typeof value.missed_count === "number"
      );
    case "timer_status":
      return (
        typeof value.timer_id === "string" &&
        typeof value.instruction_id === "string" &&
        typeof value.interval_ms === "number" &&
        typeof value.message === "string" &&
        (value.status === "active" || value.status === "canceled") &&
        (value.next_due_in_ms === null || typeof value.next_due_in_ms === "number") &&
        typeof value.fire_count === "number"
      );
    case "held_context":
      return (
        typeof value.result_event_id === "string" &&
        typeof value.text === "string" &&
        typeof value.query === "string" &&
        value.source === "tool"
      );
    case "checkpoint_notice":
      return (
        typeof value.checkpoint_event_id === "string" &&
        typeof value.segment_index === "number" &&
        typeof value.covers_through_policy_seq === "number"
      );
    default:
      return false;
  }
}

function isSpan(value: unknown): value is Span {
  return (
    isRecord(value) &&
    typeof value.event_id === "string" &&
    typeof value.start_utf16 === "number" &&
    typeof value.end_utf16 === "number" &&
    typeof value.text === "string"
  );
}

function isDecisionTrace(value: unknown): value is DecisionTraceV1 {
  return (
    isRecord(value) &&
    value.version === "decision_trace_v1" &&
    typeof value.decision_id === "string" &&
    (value.observed_through_policy_seq === null ||
      typeof value.observed_through_policy_seq === "number") &&
    (value.final_policy_seq === null || typeof value.final_policy_seq === "number") &&
    typeof value.audit_sha256 === "string" &&
    value.operator_mode === "fixed_sandbox" &&
    typeof value.raw_provider_output_sha256 === "string" &&
    isExactBytes(value.raw_provider_output) &&
    (value.parser_input === null || isExactBytes(value.parser_input)) &&
    (value.parser_input_sha256 === null || typeof value.parser_input_sha256 === "string") &&
    typeof value.parser_input_binding === "string" &&
    (value.parsed_raw_intent === null || isParsedIntent(value.parsed_raw_intent)) &&
    typeof value.frozen_policy_sha256 === "string" &&
    typeof value.frozen_license_view_sha256 === "string" &&
    typeof value.frozen_registry_sha256 === "string" &&
    isJsonValue(value.resolution) &&
    isJsonValue(value.initial_license) &&
    isJsonValue(value.pending_license) &&
    isJsonValue(value.fresh_license) &&
    isJsonValue(value.executed_event) &&
    isJsonValue(value.effect) &&
    typeof value.latency_ms === "number"
  );
}

function isExactBytes(value: unknown): boolean {
  return (
    isRecord(value) &&
    (value.encoding === "utf8" || value.encoding === "hex") &&
    typeof value.data === "string"
  );
}

function isParsedIntent(value: unknown): value is ParsedPolicyIntent {
  return isRecord(value) && isIntentType(value.type) && Object.values(value).every(isJsonValue);
}

function isIntentType(value: unknown): value is ParsedPolicyIntent["type"] {
  return (
    typeof value === "string" &&
    ["idle", "mark", "delegate", "integrate", "skip", "respond", "schedule", "cancel", "nudge"].includes(
      value,
    )
  );
}

function isJsonValue(value: unknown): value is JsonValue {
  if (value === null || typeof value === "string" || typeof value === "boolean") {
    return true;
  }
  if (typeof value === "number") {
    return Number.isFinite(value);
  }
  if (Array.isArray(value)) {
    return value.every(isJsonValue);
  }
  return isRecord(value) && Object.values(value).every(isJsonValue);
}

function isRecord(value: unknown): value is { [key: string]: unknown } {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
