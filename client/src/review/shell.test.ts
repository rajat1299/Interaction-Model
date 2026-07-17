import { afterEach, describe, expect, it } from "vitest";
import {
  adoptLoadedPacket,
  loadPacketEntries,
  loadTeacherLabelsText,
  mountReviewShell,
} from "./shell";
import { loadPacketFromEntries } from "./packet-loader";
import { loadCanaryEntries } from "./test-fixtures";

describe("review shell", () => {
  let cleanup: (() => void) | null = null;

  afterEach(() => {
    cleanup?.();
    cleanup = null;
    window.localStorage.clear();
    document.body.innerHTML = "";
  });

  it("supports essential keyboard navigation after load", async () => {
    const root = document.createElement("div");
    document.body.appendChild(root);
    cleanup = mountReviewShell(root);

    const err = await loadPacketEntries(loadCanaryEntries());
    expect(err).toBeNull();

    const meta = () => document.getElementById("nav-meta")!.textContent ?? "";
    expect(meta()).toMatch(/decision \d+\//);
    const initialEvent = Number(meta().match(/event (\d+)\//)?.[1]);
    const event = JSON.parse(document.getElementById("inspect-event")!.textContent!);
    const oracle = JSON.parse(document.getElementById("inspect-oracle")!.textContent!);
    expect(event.seq).toBe(oracle.observed_policy_seq);

    window.dispatchEvent(new KeyboardEvent("keydown", { key: "j" }));
    expect(Number(meta().match(/event (\d+)\//)?.[1])).toBe(initialEvent + 1);

    window.dispatchEvent(new KeyboardEvent("keydown", { key: "k" }));
    expect(Number(meta().match(/event (\d+)\//)?.[1])).toBe(initialEvent);

    const initialDecision = Number(meta().match(/decision (\d+)\//)?.[1]);
    window.dispatchEvent(new KeyboardEvent("keydown", { key: "n" }));
    expect(Number(meta().match(/decision (\d+)\//)?.[1])).toBe(initialDecision + 1);

    window.dispatchEvent(new KeyboardEvent("keydown", { key: "p" }));
    expect(Number(meta().match(/decision (\d+)\//)?.[1])).toBe(initialDecision);

    window.dispatchEvent(new KeyboardEvent("keydown", { key: "]" }));
    expect(document.getElementById("load-status")!.textContent).toContain("family=");
  });

  it("queues and opens a different-type teacher disagreement by decision identity", async () => {
    const result = await loadPacketFromEntries(loadCanaryEntries());
    expect(result.ok).toBe(true);
    if (!result.ok) return;
    const target = result.packet.streams[0];
    const targetDecision = target.sidecar.decisions[0];
    const teacherAction =
      targetDecision.action.type === "idle"
        ? { type: "nudge" as const, fire_event_id: "e_missing" }
        : { type: "idle" as const, reason: "no_trigger" as const, related_event_id: null };

    const root = document.createElement("div");
    document.body.appendChild(root);
    cleanup = mountReviewShell(root);
    adoptLoadedPacket(result.packet);
    const preexistingReview = document.getElementById("stream-decision") as HTMLSelectElement;
    preexistingReview.value = "accept";
    document.getElementById("btn-save-stream")!.click();
    expect(
      await loadTeacherLabelsText(
        JSON.stringify({
          stream_sha256: `sha256:${target.sha256}`,
          decision_policy_seq: targetDecision.observed_policy_seq,
          action: teacherAction,
          label: "completed",
        }),
      ),
    ).toBeNull();
    expect((document.getElementById("stream-decision") as HTMLSelectElement).value).toBe("");

    const button = [...document.querySelectorAll<HTMLButtonElement>(".stream-item")].find(
      (item) => item.textContent?.includes(target.sha256.slice(0, 10)),
    );
    expect(button).toBeTruthy();
    button!.click();
    const event = JSON.parse(document.getElementById("inspect-event")!.textContent!);
    const oracle = JSON.parse(document.getElementById("inspect-oracle")!.textContent!);
    expect(event.seq).toBe(targetDecision.observed_policy_seq);
    expect(oracle.observed_policy_seq).toBe(targetDecision.observed_policy_seq);
    expect(document.getElementById("teacher-panel")!.textContent).toContain(
      "CAUSAL DISAGREEMENT",
    );
  });

  it("persists a packet-keyed draft and guards unexported work", async () => {
    const root = document.createElement("div");
    document.body.appendChild(root);
    cleanup = mountReviewShell(root);
    expect(await loadPacketEntries(loadCanaryEntries())).toBeNull();

    const select = document.getElementById("stream-decision") as HTMLSelectElement;
    select.value = "accept";
    document.getElementById("btn-save-stream")!.click();
    const unload = new Event("beforeunload", { cancelable: true });
    window.dispatchEvent(unload);
    expect(unload.defaultPrevented).toBe(true);

    cleanup();
    cleanup = null;
    document.body.innerHTML = "";
    const remount = document.createElement("div");
    document.body.appendChild(remount);
    cleanup = mountReviewShell(remount);
    expect(await loadPacketEntries(loadCanaryEntries())).toBeNull();
    expect((document.getElementById("stream-decision") as HTMLSelectElement).value).toBe(
      "accept",
    );
  });

  it("shows persistent divergence warning when reducer state mismatches oracle", async () => {
    const result = await loadPacketFromEntries(loadCanaryEntries());
    expect(result.ok).toBe(true);
    if (!result.ok) return;

    // Corrupt every stream so rare-action-first queue still surfaces a mismatch.
    const packet = {
      ...result.packet,
      streams: result.packet.streams.map((s) => ({
        ...s,
        sidecar: {
          ...s.sidecar,
          decisions: s.sidecar.decisions.map((d, di) =>
            di === 0 ? { ...d, active_timer_ids: ["t_999"] } : d,
          ),
        },
      })),
    };

    const root = document.createElement("div");
    document.body.appendChild(root);
    cleanup = mountReviewShell(root);
    adoptLoadedPacket(packet);

    const box = document.getElementById("divergence")!;
    expect(box.hidden).toBe(false);
    expect(box.getAttribute("role")).toBe("alert");
    expect(box.textContent).toContain("DIVERGENCE");
    expect(box.textContent).toContain("active_timer_ids");
  });
});
