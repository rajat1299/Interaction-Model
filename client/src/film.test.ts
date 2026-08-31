import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { DecisionTraceV1, FilmReplay } from "./protocol";

class FakeWebSocket extends EventTarget {
  static readonly CONNECTING = 0;
  static readonly OPEN = 1;
  static readonly CLOSED = 3;
  static instances: FakeWebSocket[] = [];

  readonly send = vi.fn();
  readyState = FakeWebSocket.CONNECTING;

  constructor(readonly url: string) {
    super();
    FakeWebSocket.instances.push(this);
  }

  open(): void {
    this.readyState = FakeWebSocket.OPEN;
    this.dispatchEvent(new Event("open"));
  }

  receive(value: object): void {
    this.dispatchEvent(new MessageEvent("message", { data: JSON.stringify(value) }));
  }

  close(): void {
    this.readyState = FakeWebSocket.CLOSED;
    this.dispatchEvent(new Event("close"));
  }
}

const trace = (
  decisionId: string,
  intent: DecisionTraceV1["parsed_raw_intent"],
  overrides: Partial<DecisionTraceV1> = {},
): DecisionTraceV1 => ({
  version: "decision_trace_v1",
  decision_id: decisionId,
  observed_through_policy_seq: null,
  final_policy_seq: null,
  audit_sha256: `sha256:${decisionId.padEnd(64, "0")}`,
  operator_mode: "fixed_sandbox",
  raw_provider_output: { encoding: "utf8", data: JSON.stringify(intent) },
  raw_provider_output_sha256: `sha256:${"1".repeat(64)}`,
  parser_input: { encoding: "utf8", data: JSON.stringify(intent) },
  parser_input_sha256: `sha256:${"5".repeat(64)}`,
  parser_input_binding: "authenticated_terminal_framing",
  parsed_raw_intent: intent,
  frozen_policy_sha256: `sha256:${"2".repeat(64)}`,
  frozen_license_view_sha256: `sha256:${"3".repeat(64)}`,
  frozen_registry_sha256: `sha256:${"4".repeat(64)}`,
  resolution: null,
  initial_license: null,
  pending_license: null,
  fresh_license: null,
  executed_event: null,
  effect: null,
  latency_ms: 12,
  ...overrides,
});

async function settle(): Promise<void> {
  await Promise.resolve();
  await Promise.resolve();
  await Promise.resolve();
}

describe("film UI", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.resetModules();
    FakeWebSocket.instances = [];
    document.body.innerHTML = '<div id="app"></div>';
    vi.stubGlobal("WebSocket", FakeWebSocket);
  });

  afterEach(() => {
    window.dispatchEvent(new Event("beforeunload"));
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    vi.useRealTimers();
    document.body.replaceChildren();
  });

  it("opens one clean session and lists completed non-idle intents newest first", async () => {
    window.history.replaceState({}, "", "/film.html");
    const fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ session_id: "s_film" }),
    });
    vi.stubGlobal("fetch", fetch);

    await import("./film");
    await settle();

    expect(fetch).toHaveBeenCalledOnce();
    expect(fetch).toHaveBeenCalledWith("/session", { method: "POST" });
    const socket = FakeWebSocket.instances[0]!;
    socket.open();
    expect(socket.send).toHaveBeenCalledOnce();
    expect(JSON.parse(socket.send.mock.calls[0]![0])).toMatchObject({
      activity: "active",
      text: "",
    });
    const textarea = document.querySelector<HTMLTextAreaElement>("#film-input")!;
    expect(textarea.disabled).toBe(true);
    socket.receive({
      type: "decision_trace",
      trace: trace("mark", { type: "mark", text: "quokka" }, {
        executed_event: { kind: "action_executed" },
      }),
    });
    expect(textarea.disabled).toBe(false);
    expect(document.activeElement).toBe(textarea);
    socket.receive({
      type: "decision_trace",
      trace: trace("idle", { type: "idle", reason: "no_trigger", related: null }),
    });
    socket.receive({
      type: "decision_trace",
      trace: trace("blocked", { type: "delegate", source: "u0", query: "score", occurrence: 0 }),
    });

    const actions = [...document.querySelectorAll("#action-list li")].map((item) => item.textContent);
    expect(actions).toEqual(["called out quokka"]);
    expect(document.querySelector("#technical-list")).toBeNull();
    expect(document.querySelector(".trace")).toBeNull();
  });

  it("keeps an idle-only clean take visually empty", async () => {
    window.history.replaceState({}, "", "/film.html");
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({ session_id: "s_film" }),
      }),
    );
    await import("./film");
    await settle();
    const socket = FakeWebSocket.instances[0]!;
    socket.open();
    socket.receive({
      type: "decision_trace",
      trace: trace("idle", { type: "idle", reason: "no_trigger", related: null }),
    });

    expect(document.querySelector("#action-list")?.childElementCount).toBe(0);
    expect(document.querySelector("#document-responses")?.childElementCount).toBe(0);
    expect(document.querySelector("#context-list")?.childElementCount).toBe(0);
    expect(document.querySelector("#technical-list")).toBeNull();
  });

  it("fails closed when the warm-up trace has no parsed intent", async () => {
    window.history.replaceState({}, "", "/film.html");
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({ session_id: "s_film" }),
      }),
    );
    await import("./film");
    await settle();
    const socket = FakeWebSocket.instances[0]!;
    socket.open();
    const textarea = document.querySelector<HTMLTextAreaElement>("#film-input")!;
    socket.receive({
      type: "decision_trace",
      trace: trace("warmup-failed", null),
    });

    expect(document.querySelector("#film-clock")?.textContent).toBe("unavailable");
    expect(document.querySelector(".film__error")?.textContent).toContain("warm-up");
    expect(textarea.disabled).toBe(true);
    textarea.value = "ignored";
    textarea.dispatchEvent(new InputEvent("input", { inputType: "insertText" }));
    vi.advanceTimersByTime(2_000);
    expect(socket.send).toHaveBeenCalledOnce();
  });

  it("sends only the active baseline while warm-up remains pending", async () => {
    window.history.replaceState({}, "", "/film.html");
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({ session_id: "s_film" }),
      }),
    );
    await import("./film");
    await settle();
    const socket = FakeWebSocket.instances[0]!;
    socket.open();
    expect(socket.send).toHaveBeenCalledOnce();
    expect(JSON.parse(socket.send.mock.calls[0]![0])).toMatchObject({
      activity: "active",
      text: "",
    });

    vi.advanceTimersByTime(1_501);
    expect(socket.send).toHaveBeenCalledOnce();
    expect(document.querySelector<HTMLTextAreaElement>("#film-input")?.disabled).toBe(true);
  });

  it("renders first-segment active frames but sends only its complete pause", async () => {
    window.history.replaceState({}, "", "/film.html");
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({ session_id: "s_film" }),
      }),
    );
    await import("./film");
    await settle();
    const socket = FakeWebSocket.instances[0]!;
    socket.open();
    const textarea = document.querySelector<HTMLTextAreaElement>("#film-input")!;
    expect(socket.send).toHaveBeenCalledOnce();
    expect(textarea.disabled).toBe(true);
    socket.receive({
      type: "decision_trace",
      trace: trace("warmup", { type: "idle", reason: "no_trigger", related: null }),
    });
    expect(textarea.disabled).toBe(false);
    expect(document.activeElement).toBe(textarea);

    document.dispatchEvent(new Event("selectionchange"));
    vi.advanceTimersByTime(100);
    vi.advanceTimersByTime(1_400);
    expect(socket.send).toHaveBeenCalledOnce();

    textarea.value = "partial";
    textarea.dispatchEvent(new InputEvent("input", { inputType: "insertText" }));
    vi.advanceTimersByTime(100);
    expect(document.querySelector("#document-text")?.textContent).toBe("partial");
    expect(socket.send).toHaveBeenCalledOnce();

    textarea.value = "complete instruction";
    textarea.dispatchEvent(new InputEvent("input", { inputType: "insertText" }));
    vi.advanceTimersByTime(100);
    expect(document.querySelector("#document-text")?.textContent).toBe("complete instruction");
    expect(socket.send).toHaveBeenCalledOnce();

    vi.advanceTimersByTime(1_400);
    expect(socket.send).toHaveBeenCalledTimes(2);
    expect(JSON.parse(socket.send.mock.calls[1]![0])).toMatchObject({
      activity: "paused",
      text: "complete instruction",
    });
  });

  it("coalesces subsequent active frames and lets pause supersede the newest active", async () => {
    window.history.replaceState({}, "", "/film.html");
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({ session_id: "s_film" }),
      }),
    );
    await import("./film");
    await settle();
    const socket = FakeWebSocket.instances[0]!;
    socket.open();
    const textarea = document.querySelector<HTMLTextAreaElement>("#film-input")!;
    socket.receive({
      type: "decision_trace",
      trace: trace("warmup", { type: "idle", reason: "no_trigger", related: null }),
    });

    textarea.value = "first";
    textarea.dispatchEvent(new InputEvent("input", { inputType: "insertText" }));
    vi.advanceTimersByTime(100);
    vi.advanceTimersByTime(1_400);
    expect(socket.send).toHaveBeenCalledTimes(2);
    expect(JSON.parse(socket.send.mock.calls[1]![0])).toMatchObject({
      activity: "paused",
      text: "first",
    });

    textarea.value = "second";
    textarea.dispatchEvent(new InputEvent("input", { inputType: "insertText" }));
    vi.advanceTimersByTime(100);
    textarea.value = "latest";
    textarea.dispatchEvent(new InputEvent("input", { inputType: "insertText" }));
    vi.advanceTimersByTime(100);
    expect(socket.send).toHaveBeenCalledTimes(2);

    vi.advanceTimersByTime(1_400);
    expect(socket.send).toHaveBeenCalledTimes(2);

    socket.receive({
      type: "decision_trace",
      trace: trace("first-pause-ack", { type: "idle", reason: "no_trigger", related: null }),
    });
    expect(socket.send).toHaveBeenCalledTimes(3);
    expect(JSON.parse(socket.send.mock.calls[2]![0])).toMatchObject({
      activity: "paused",
      text: "latest",
    });

    socket.receive({
      type: "checkpoint_notice",
      checkpoint_event_id: "checkpoint-1",
      segment_index: 1,
      covers_through_policy_seq: 1,
    });
    expect(socket.send).toHaveBeenCalledTimes(3);
  });

  it("summarizes every non-idle intent without exposing registry aliases", async () => {
    window.history.replaceState({}, "", "/film.html");
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({ session_id: "s_film" }),
      }),
    );
    await import("./film");
    await settle();
    const socket = FakeWebSocket.instances[0]!;
    socket.open();
    const intents: DecisionTraceV1["parsed_raw_intent"][] = [
      { type: "idle", reason: "no_trigger", related: null },
      { type: "mark", text: "quokka" },
      { type: "delegate", source: "u0", query: "score", occurrence: 0 },
      { type: "integrate", result: "r0" },
      { type: "skip", target: "r1", reason: "stale_tool_result" },
      { type: "respond", warrant: "u0", response_kind: "clarification" },
      {
        type: "schedule",
        instruction: {
          kind: "visible",
          source: "u0",
          text: "Check the draft every ten minutes",
          occurrence: 0,
        },
      },
      { type: "nudge", fire: "f0" },
      {
        type: "cancel",
        instruction: { kind: "committed", instruction: "i0" },
        target: { kind: "timer", timer: "t0" },
      },
    ];
    intents.forEach((intent, index) => {
      const overrides: Partial<DecisionTraceV1> = {
        executed_event: { kind: "action_executed" },
      };
      if (intent?.type === "integrate") {
        overrides.resolution = {
          status: "canonical_result_fallback",
          value: { type: "integrate", result_event_id: "e_result", text: "Velin Quay 41" },
        };
      } else if (intent?.type === "schedule") {
        overrides.resolution = {
          status: "resolved_action",
          action: {
            type: "schedule",
            instruction: { event_id: "e0", start_utf16: 0, end_utf16: 5, text: "Check" },
            interval_ms: 600_000,
            message: "Check the draft",
          },
        };
      } else if (intent?.type === "nudge" || intent?.type === "cancel") {
        overrides.effect = {
          render_frames: intent.type === "nudge" ? [{ message: "Check the draft" }] : [],
          timers: [{ message: "Check the draft" }],
        };
      }
      socket.receive({
        type: "decision_trace",
        trace: trace(`intent-${index}`, intent, overrides),
      });
    });

    expect([...document.querySelectorAll("#action-list li")].map((item) => item.textContent)).toEqual([
      "canceled Check the draft",
      "nudged Check the draft",
      "scheduled Check the draft · every 10m",
      "responded",
      "skipped stale tool result",
      "integrated Velin Quay 41",
      "delegate lookup",
      "called out quokka",
    ]);
    expect(document.querySelector("#action-list")?.textContent).not.toMatch(/\b[urtf]\d+\b/);
    expect(document.querySelector("#technical-list")).toBeNull();
  });

  it("renders exact UTF-16 marks and held context without injecting markup", async () => {
    window.history.replaceState({}, "", "/film.html");
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({ session_id: "s_film" }),
      }),
    );
    await import("./film");
    await settle();
    const socket = FakeWebSocket.instances[0]!;
    socket.open();
    socket.receive({
      type: "decision_trace",
      trace: trace("warmup", { type: "idle", reason: "no_trigger", related: null }),
    });
    const textarea = document.querySelector<HTMLTextAreaElement>("#film-input")!;
    textarea.value = "🙂 A quokka sat nearby.";
    textarea.setSelectionRange(textarea.value.length, textarea.value.length);
    textarea.dispatchEvent(new InputEvent("input", { inputType: "insertText" }));
    vi.advanceTimersByTime(100);
    socket.receive({
      type: "mark_render",
      action_event_id: "e_mark",
      instruction: { event_id: "e_snapshot", start_utf16: 3, end_utf16: 4, text: "A" },
      target: { event_id: "e_snapshot", start_utf16: 5, end_utf16: 11, text: "quokka" },
    });
    socket.receive({
      type: "held_context",
      result_event_id: "e_result",
      text: "Velin Quay 41 <script>",
      query: "Velin Quay score",
      source: "tool",
    });

    expect(document.querySelector("#document-text mark")?.textContent).toBe("quokka");
    expect(document.querySelector("#context-list")?.textContent).toContain(
      "Velin Quay 41 <script>",
    );
    expect(document.querySelector("#context-list script")).toBeNull();
    socket.receive({
      type: "decision_trace",
      trace: trace(
        "integrate",
        { type: "integrate", result: "r0" },
        {
          resolution: {
            status: "canonical_result_fallback",
            value: { type: "integrate", result_event_id: "e_result", text: "Velin Quay 41" },
            reason: null,
          },
          executed_event: { kind: "action_executed" },
        },
      ),
    });

    expect(document.querySelector("#context-list")?.textContent).not.toContain("Velin Quay 41");
    expect(document.querySelector("#document-responses")?.textContent).toBe("Velin Quay 41");
  });

  it("disposes held context only after an executed skip", async () => {
    window.history.replaceState({}, "", "/film.html");
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({ session_id: "s_film" }),
      }),
    );
    await import("./film");
    await settle();
    const socket = FakeWebSocket.instances[0]!;
    socket.open();
    socket.receive({
      type: "decision_trace",
      trace: trace("warmup", { type: "idle", reason: "no_trigger", related: null }),
    });
    socket.receive({
      type: "held_context",
      result_event_id: "e_result",
      text: "Velin Quay 41",
      query: "Velin Quay score",
      source: "tool",
    });
    socket.receive({
      type: "decision_trace",
      trace: trace(
        "blocked-skip",
        { type: "skip", target: "r0", reason: "stale_result" },
        {
          resolution: {
            status: "resolved_action",
            action: { type: "skip", target_event_id: "e_result", reason: "stale_result" },
          },
          executed_event: null,
        },
      ),
    });
    expect(document.querySelector("#context-list")?.textContent).toContain("Velin Quay 41");

    socket.receive({
      type: "decision_trace",
      trace: trace(
        "executed-skip",
        { type: "skip", target: "r0", reason: "stale_result" },
        {
          resolution: {
            status: "resolved_action",
            action: { type: "skip", target_event_id: "e_result", reason: "stale_result" },
          },
          executed_event: { kind: "action_executed" },
        },
      ),
    });
    expect(document.querySelector("#context-section")?.hasAttribute("hidden")).toBe(true);
  });

  it("replays an existing durable stream with one GET and no sampling transport", async () => {
    window.history.replaceState({}, "", "/film.html?mode=technical&session=s_recorded");
    const replay: FilmReplay = {
      session_id: "s_recorded",
      events: [
        {
          type: "snapshot_projection",
          event_id: "e_snapshot",
          text: "Notes about a wombat.",
          client_ts: 10,
        },
        {
          type: "decision_trace",
          trace: trace("recorded", { type: "mark", text: "wombat" }),
        },
        {
          type: "mark_render",
          action_event_id: "e_mark",
          instruction: { event_id: "e_snapshot", start_utf16: 0, end_utf16: 5, text: "Notes" },
          target: { event_id: "e_snapshot", start_utf16: 14, end_utf16: 20, text: "wombat" },
        },
      ],
    };
    const fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => replay,
    });
    vi.stubGlobal("fetch", fetch);

    await import("./film");
    await settle();

    expect(fetch).toHaveBeenCalledOnce();
    expect(fetch).toHaveBeenCalledWith("/session/s_recorded/decision-traces", { method: "GET" });
    expect(FakeWebSocket.instances).toHaveLength(0);
    expect(document.querySelector<HTMLTextAreaElement>("#film-input")?.readOnly).toBe(true);
    expect(document.querySelector("#document-text")?.textContent).toBe("Notes about a wombat.");
    expect(document.querySelector("#technical-list summary")?.textContent).toBe("recorded · mark");
    expect(document.querySelector("#action-list")?.hasAttribute("hidden")).toBe(true);
    expect(document.querySelector("#new-take")).toBeNull();
  });

  it("resets only by stopping the completed sandbox and opening a new take", async () => {
    window.history.replaceState({}, "", "/film.html");
    const fetch = vi.fn(async (input: string | URL | Request, _init?: RequestInit) => {
      const url = String(input);
      if (url === "/session") {
        const ordinal = fetch.mock.calls.filter(([value]) => String(value) === "/session").length;
        return {
          ok: true,
          status: 200,
          json: async () => ({ session_id: `s_take_${ordinal}` }),
        };
      }
      return { ok: true, status: 200, json: async () => ({ stopped: true }) };
    });
    vi.stubGlobal("fetch", fetch);

    await import("./film");
    await settle();
    const firstSocket = FakeWebSocket.instances[0]!;
    firstSocket.open();
    firstSocket.receive({
      type: "decision_trace",
      trace: trace("mark", { type: "mark", text: "quokka" }, {
        executed_event: { kind: "action_executed" },
      }),
    });
    expect(document.querySelectorAll("#action-list li")).toHaveLength(1);

    const firstTextarea = document.querySelector<HTMLTextAreaElement>("#film-input")!;
    firstTextarea.value = "first take";
    firstTextarea.dispatchEvent(new InputEvent("input", { inputType: "insertText" }));
    vi.advanceTimersByTime(100);
    vi.advanceTimersByTime(1_400);
    expect(firstSocket.send).toHaveBeenCalledTimes(2);

    document.querySelector<HTMLButtonElement>("#new-take")!.click();
    await settle();
    await settle();

    expect(fetch.mock.calls.map(([input, init]) => [String(input), init])).toEqual([
      ["/session", { method: "POST" }],
      ["/session/s_take_1/stop", { method: "POST", keepalive: false }],
      ["/session", { method: "POST" }],
    ]);
    expect(FakeWebSocket.instances).toHaveLength(2);
    expect(firstSocket.readyState).toBe(FakeWebSocket.CLOSED);
    expect(document.querySelectorAll("#action-list li")).toHaveLength(0);
    const textarea = document.querySelector<HTMLTextAreaElement>("#film-input")!;
    expect(textarea.value).toBe("");
    expect(textarea.disabled).toBe(true);
    expect(document.querySelector<HTMLButtonElement>("#new-take")?.textContent).toBe("Reset");

    const secondSocket = FakeWebSocket.instances[1]!;
    secondSocket.open();
    expect(secondSocket.send).toHaveBeenCalledOnce();
    secondSocket.receive({
      type: "decision_trace",
      trace: trace("warmup-2", { type: "idle", reason: "no_trigger", related: null }),
    });
    expect(textarea.disabled).toBe(false);
    textarea.focus();
    document.dispatchEvent(new Event("selectionchange"));
    vi.advanceTimersByTime(1_500);
    expect(secondSocket.send).toHaveBeenCalledOnce();
    textarea.value = "reset first segment";
    textarea.dispatchEvent(new InputEvent("input", { inputType: "insertText" }));
    vi.advanceTimersByTime(100);
    expect(secondSocket.send).toHaveBeenCalledOnce();
    expect(document.querySelector("#document-text")?.textContent).toBe("reset first segment");
    vi.advanceTimersByTime(1_400);
    expect(secondSocket.send).toHaveBeenCalledTimes(2);
    expect(JSON.parse(secondSocket.send.mock.calls[1]![0])).toMatchObject({
      activity: "paused",
      text: "reset first segment",
    });

    const clock = document.querySelector("#film-clock")?.textContent;
    firstSocket.dispatchEvent(new Event("close"));
    firstSocket.dispatchEvent(new Event("error"));
    expect(document.querySelector("#film-clock")?.textContent).toBe(clock);
  });

  it("does not open a second sandbox when reset cannot stop the first", async () => {
    window.history.replaceState({}, "", "/film.html");
    const fetch = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ session_id: "s_take_1" }),
      })
      .mockResolvedValueOnce({ ok: false, status: 500 });
    vi.stubGlobal("fetch", fetch);

    await import("./film");
    await settle();
    document.querySelector<HTMLButtonElement>("#new-take")!.click();
    await settle();

    expect(fetch).toHaveBeenCalledTimes(2);
    expect(FakeWebSocket.instances).toHaveLength(1);
    expect(document.querySelector("#film-clock")?.textContent).toBe("unavailable");
    expect(document.querySelector<HTMLButtonElement>("#new-take")?.disabled).toBe(false);
  });
});
