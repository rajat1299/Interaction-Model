import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

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

  close(): void {
    this.readyState = FakeWebSocket.CLOSED;
    this.dispatchEvent(new Event("close"));
  }
}

async function settle(): Promise<void> {
  await Promise.resolve();
  await Promise.resolve();
}

describe("browser harness", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-07-12T00:00:00.000Z"));
    vi.resetModules();
    FakeWebSocket.instances = [];
    window.history.replaceState({}, "", "/");
    document.body.innerHTML = '<div id="app"></div>';
    vi.stubGlobal("WebSocket", FakeWebSocket);
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({ session_id: "s_persistent" }),
      }),
    );
  });

  afterEach(() => {
    window.dispatchEvent(new Event("beforeunload"));
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    vi.useRealTimers();
    document.body.replaceChildren();
  });

  it("reuses its session and flushes the latest sampler frame after reconnecting", async () => {
    await import("./main");
    await settle();
    const firstSocket = FakeWebSocket.instances[0]!;
    firstSocket.open();

    expect(firstSocket.url).toContain("/session/s_persistent");
    expect(firstSocket.send).toHaveBeenCalledTimes(1);

    firstSocket.close();
    const textarea = document.querySelector<HTMLTextAreaElement>("#interaction-text")!;
    textarea.value = "latest disconnected edit";
    textarea.setSelectionRange(textarea.value.length, textarea.value.length);
    textarea.dispatchEvent(new InputEvent("input", { inputType: "insertText" }));
    vi.advanceTimersByTime(100);
    document.querySelector<HTMLButtonElement>("#reconnect")!.click();
    await settle();
    const secondSocket = FakeWebSocket.instances[1]!;
    secondSocket.open();

    expect(fetch).toHaveBeenCalledTimes(1);
    expect(secondSocket.url).toContain("/session/s_persistent");
    expect(secondSocket.send).toHaveBeenCalledTimes(1);
    expect(JSON.parse(secondSocket.send.mock.calls[0]![0])).toEqual(
      expect.objectContaining({
        text: "latest disconnected edit",
        input_type: "insertText",
        activity: "active",
      }),
    );
  });

  it("flushes calibration before acknowledging completion and downloading the sidecar", async () => {
    window.history.replaceState({}, "", "/?calibration=natural-drafting");
    const createObjectURL = vi.fn((_blob: Blob) => "blob:calibration-recording");
    const revokeObjectURL = vi.fn();
    class CalibrationUrl extends URL {
      static createObjectURL = createObjectURL;
      static revokeObjectURL = revokeObjectURL;
    }
    vi.stubGlobal("URL", CalibrationUrl);
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    let resolveCompletion!: (response: { ok: boolean; status: number }) => void;
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce({
          ok: true,
          status: 200,
          json: async () => ({ session_id: "s_persistent" }),
        })
        .mockReturnValueOnce(
          new Promise((resolve) => {
            resolveCompletion = resolve;
          }),
        ),
    );

    await import("./main");
    await settle();
    expect(fetch).toHaveBeenCalledWith("/session?calibration=true", { method: "POST" });
    const socket = FakeWebSocket.instances[0]!;
    socket.open();
    const textarea = document.querySelector<HTMLTextAreaElement>("#interaction-text")!;
    textarea.value = "captured draft";
    textarea.setSelectionRange(textarea.value.length, textarea.value.length);
    textarea.dispatchEvent(new InputEvent("input", { inputType: "insertText", data: "t" }));

    expect(document.querySelector("#calibration-status")?.textContent).toBe("Recording calibration: natural-drafting");
    expect(socket.send).toHaveBeenCalledTimes(1);
    document.querySelector<HTMLButtonElement>("#calibration-download")!.click();

    expect(socket.send).toHaveBeenCalledTimes(2);
    expect(fetch).toHaveBeenNthCalledWith(2, "/session/s_persistent/calibration-complete", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ last_client_ts: Date.now(), sampler_frame_count: 2 }),
    });
    expect(textarea.disabled).toBe(true);
    expect(createObjectURL).not.toHaveBeenCalled();
    resolveCompletion({ ok: true, status: 204 });
    await settle();

    expect(createObjectURL).toHaveBeenCalledOnce();
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:calibration-recording");
    expect(click).toHaveBeenCalledOnce();
    const bundle = JSON.parse(await (createObjectURL.mock.calls[0]![0] as Blob).text());
    expect(bundle).toEqual(
      expect.objectContaining({
        runtime_session_id: "s_persistent",
        regime: "natural-drafting",
        recording_duration_ms: expect.any(Number),
        raw_events: [expect.objectContaining({ text: "captured draft", input_type: "insertText" })],
        sampler_frames: [
          expect.objectContaining({ frame: expect.objectContaining({ text: "" }) }),
          expect.objectContaining({ frame: expect.objectContaining({ text: "captured draft" }) }),
        ],
      }),
    );
    expect(document.querySelector("#calibration-status")?.textContent).toBe("Calibration stopped; JSON downloaded");
  });

  it("preserves a stopped calibration bundle for completion retry", async () => {
    window.history.replaceState({}, "", "/?calibration=natural-drafting");
    const createObjectURL = vi.fn((_blob: Blob) => "blob:calibration-recording");
    const revokeObjectURL = vi.fn();
    class CalibrationUrl extends URL {
      static createObjectURL = createObjectURL;
      static revokeObjectURL = revokeObjectURL;
    }
    vi.stubGlobal("URL", CalibrationUrl);
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce({
          ok: true,
          status: 200,
          json: async () => ({ session_id: "s_persistent" }),
        })
        .mockResolvedValueOnce({ ok: false, status: 503 })
        .mockResolvedValueOnce({ ok: true, status: 204 }),
    );

    await import("./main");
    await settle();
    FakeWebSocket.instances[0]!.open();
    const textarea = document.querySelector<HTMLTextAreaElement>("#interaction-text")!;
    textarea.value = "captured draft";
    textarea.setSelectionRange(textarea.value.length, textarea.value.length);
    textarea.dispatchEvent(new InputEvent("input", { inputType: "insertText", data: "t" }));
    const stop = document.querySelector<HTMLButtonElement>("#calibration-download")!;
    stop.click();
    await settle();

    expect(createObjectURL).toHaveBeenCalledOnce();
    expect(stop.disabled).toBe(false);
    expect(document.querySelector("#calibration-status")?.textContent).toBe(
      "Calibration completion failed; incomplete JSON downloaded; retry completion",
    );
    textarea.value = "not recorded after stop";
    textarea.dispatchEvent(new InputEvent("input", { inputType: "insertText", data: "x" }));

    stop.click();
    await settle();

    expect(fetch).toHaveBeenNthCalledWith(2, "/session/s_persistent/calibration-complete", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ last_client_ts: Date.now(), sampler_frame_count: 2 }),
    });
    expect(fetch).toHaveBeenNthCalledWith(3, "/session/s_persistent/calibration-complete", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ last_client_ts: Date.now(), sampler_frame_count: 2 }),
    });
    expect(createObjectURL).toHaveBeenCalledTimes(2);
    const bundle = JSON.parse(await (createObjectURL.mock.calls[1]![0] as Blob).text());
    expect(bundle.raw_events).toEqual([expect.objectContaining({ text: "captured draft" })]);
  });

  it("downloads the frozen recovery bundle if transport dies after Stop", async () => {
    window.history.replaceState({}, "", "/?calibration=natural-drafting");
    const createObjectURL = vi.fn((_blob: Blob) => "blob:stopped-recovery");
    class CalibrationUrl extends URL {
      static createObjectURL = createObjectURL;
      static revokeObjectURL = vi.fn();
    }
    vi.stubGlobal("URL", CalibrationUrl);
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce({
          ok: true,
          status: 200,
          json: async () => ({ session_id: "s_persistent" }),
        })
        .mockReturnValueOnce(new Promise(() => {})),
    );

    await import("./main");
    await settle();
    const socket = FakeWebSocket.instances[0]!;
    socket.open();
    document.querySelector<HTMLButtonElement>("#calibration-download")!.click();
    socket.close();

    expect(createObjectURL).toHaveBeenCalledOnce();
    const recovery = JSON.parse(await (createObjectURL.mock.calls[0]![0] as Blob).text());
    expect(recovery).toEqual(
      expect.objectContaining({ runtime_session_id: "s_persistent", sampler_frames: [expect.any(Object)] }),
    );
    expect(document.querySelector("#calibration-status")?.textContent).toBe(
      "Calibration connection lost; incomplete JSON downloaded",
    );
  });

  it("keeps calibration input disabled until recorder and sampler start together", async () => {
    window.history.replaceState({}, "", "/?calibration=natural-drafting");
    let resolveSession!: (value: object) => void;
    vi.stubGlobal(
      "fetch",
      vi.fn().mockReturnValue(
        new Promise((resolve) => {
          resolveSession = resolve;
        }),
      ),
    );

    await import("./main");
    const textarea = document.querySelector<HTMLTextAreaElement>("#interaction-text")!;
    expect(textarea.disabled).toBe(true);

    resolveSession({
      ok: true,
      status: 200,
      json: async () => ({ session_id: "s_delayed" }),
    });
    await settle();

    expect(textarea.disabled).toBe(true);
    expect(document.querySelector("#calibration-status")?.textContent).toBe(
      "Waiting for runtime session",
    );

    FakeWebSocket.instances[0]!.open();

    expect(textarea.disabled).toBe(false);
    expect(document.querySelector("#calibration-status")?.textContent).toBe(
      "Recording calibration: natural-drafting",
    );
  });

  it("invalidates a calibration disconnect and downloads a local recovery bundle", async () => {
    window.history.replaceState({}, "", "/?calibration=natural-drafting");
    const createObjectURL = vi.fn((_blob: Blob) => "blob:incomplete-calibration");
    class CalibrationUrl extends URL {
      static createObjectURL = createObjectURL;
      static revokeObjectURL = vi.fn();
    }
    vi.stubGlobal("URL", CalibrationUrl);
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});

    await import("./main");
    await settle();
    const socket = FakeWebSocket.instances[0]!;
    socket.open();
    const textarea = document.querySelector<HTMLTextAreaElement>("#interaction-text")!;
    textarea.value = "recover this";
    textarea.setSelectionRange(textarea.value.length, textarea.value.length);
    textarea.dispatchEvent(new InputEvent("input", { inputType: "insertText", data: "s" }));

    socket.close();

    expect(textarea.disabled).toBe(true);
    expect(createObjectURL).toHaveBeenCalledOnce();
    expect(click).toHaveBeenCalledOnce();
    expect((click.mock.instances[0] as HTMLAnchorElement).download).toBe(
      "incomplete-calibration-natural-drafting.json",
    );
    expect(document.querySelector("#calibration-status")?.textContent).toBe(
      "Calibration connection lost; incomplete JSON downloaded",
    );
    expect(document.querySelector<HTMLButtonElement>("#reconnect")!.disabled).toBe(true);
  });

  it("does not expose or attach calibration recording for an invalid regime", async () => {
    window.history.replaceState({}, "", "/?calibration=freeform");

    await import("./main");
    await settle();
    const socket = FakeWebSocket.instances[0]!;
    socket.open();
    const textarea = document.querySelector<HTMLTextAreaElement>("#interaction-text")!;
    textarea.value = "ordinary frame";
    textarea.dispatchEvent(new InputEvent("input", { inputType: "insertText" }));
    vi.advanceTimersByTime(100);

    expect(document.querySelector("#calibration-status")).toBeNull();
    expect(document.querySelector("#calibration-download")).toBeNull();
    expect(socket.send).toHaveBeenCalledTimes(2);
  });
});
