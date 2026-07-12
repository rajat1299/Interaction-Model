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
});
