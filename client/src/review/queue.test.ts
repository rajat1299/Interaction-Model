import { describe, expect, it } from "vitest";
import { buildStreamQueue } from "./queue";
import { loadPacketFromEntries } from "./packet-loader";
import { loadCanaryEntries } from "./test-fixtures";
import type { LoadedStream } from "./types";

describe("filters and rare-action-first queue", () => {
  async function streams(): Promise<LoadedStream[]> {
    const result = await loadPacketFromEntries(loadCanaryEntries());
    if (!result.ok) throw new Error(result.errors.join("\n"));
    return result.packet.streams;
  }

  it("orders streams by max rarity (non-idle first)", async () => {
    const all = await streams();
    const queue = buildStreamQueue(all, { families: null, actionTypes: null });
    expect(queue.length).toBe(all.length);
    for (let i = 1; i < queue.length; i++) {
      expect(queue[i - 1].maxRarity).toBeGreaterThanOrEqual(queue[i].maxRarity);
    }
    // A stream with only idle should not outrank one with skips/cancels.
    const cancelFamily = queue.find((q) => q.family.includes("timer_cancel"));
    const neutral = queue.find((q) => q.family.includes("neutral_typing"));
    expect(cancelFamily).toBeTruthy();
    expect(neutral).toBeTruthy();
    expect(cancelFamily!.maxRarity).toBeGreaterThan(neutral!.maxRarity);
  });

  it("filters by family and action type without shuffling primary stream unit", async () => {
    const all = await streams();
    const family = all[0].family;
    const filtered = buildStreamQueue(all, {
      families: new Set([family]),
      actionTypes: null,
    });
    expect(filtered.every((q) => q.family === family)).toBe(true);
    // Decisions stay attached to their stream.
    for (const item of filtered) {
      expect(item.decisions.every((d) => d.streamSha256 === item.streamSha256)).toBe(
        true,
      );
    }

    const nudgeOnly = buildStreamQueue(all, {
      families: null,
      actionTypes: new Set(["nudge"]),
    });
    expect(nudgeOnly.length).toBeGreaterThan(0);
    for (const item of nudgeOnly) {
      expect(item.decisions.every((d) => d.actionType === "nudge")).toBe(true);
    }
  });

  it("boosts disagreements above ordinary idle", async () => {
    const all = await streams();
    const idleStream = all.find((s) =>
      s.sidecar.decisions.every((d) => d.action.type === "idle"),
    );
    const target = all.find((s) =>
      s.sidecar.decisions.some((d) => d.action.type === "idle"),
    )!;
    const idleDec = target.sidecar.decisions.find((d) => d.action.type === "idle")!;
    const key = `${target.sha256}\x00${idleDec.observed_policy_seq}`;
    const queue = buildStreamQueue(
      idleStream ? [idleStream, target] : [target],
      { families: null, actionTypes: null },
      new Set([key]),
    );
    expect(queue[0].streamSha256).toBe(target.sha256);
    expect(queue[0].maxRarity).toBeGreaterThanOrEqual(10);
  });
});
