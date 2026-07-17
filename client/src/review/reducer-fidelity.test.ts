import { describe, expect, it } from "vitest";
import { loadPacketFromEntries, concatStreamEvents } from "./packet-loader";
import { checkStreamFidelity } from "./reducer-fidelity";
import { reduceStream } from "./reducer";
import { loadCanaryEntries } from "./test-fixtures";
import type { LoadedStream } from "./types";

async function loadCanary() {
  const result = await loadPacketFromEntries(loadCanaryEntries());
  if (!result.ok) throw new Error(result.errors.join("\n"));
  return result.packet;
}

function byFamily(streams: LoadedStream[], family: string): LoadedStream {
  const s = streams.find((x) => x.family === family);
  if (!s) throw new Error(`missing family ${family}`);
  return s;
}

describe("reducer canary stream-derivable subset coverage", () => {
  it("is deterministic for the same stream bytes", async () => {
    const packet = await loadCanary();
    const stream = byFamily(packet.streams, "mark_activation_positive");
    const events = concatStreamEvents(stream);
    const a = reduceStream(events);
    const b = reduceStream(events);
    expect(JSON.stringify(a.states)).toBe(JSON.stringify(b.states));
  });

  it("matches oracle + checkpoints + ledger on ordinary mark stream", async () => {
    const packet = await loadCanary();
    const stream = byFamily(packet.streams, "mark_activation_positive");
    const fid = checkStreamFidelity(stream);
    expect(fid.decisionComparisons).toBe(stream.sidecar.decisions.length);
    expect(fid.divergences).toEqual([]);
  });

  it("matches tool lifecycle stream", async () => {
    const packet = await loadCanary();
    const stream = byFamily(packet.streams, "live_lookup_lifecycle");
    const fid = checkStreamFidelity(stream);
    expect(fid.decisionComparisons).toBeGreaterThan(0);
    expect(fid.divergences).toEqual([]);
  });

  it("matches timer lifecycle stream", async () => {
    const packet = await loadCanary();
    const stream = byFamily(packet.streams, "timer_creation_normal_fire");
    const fid = checkStreamFidelity(stream);
    expect(fid.decisionComparisons).toBe(stream.sidecar.decisions.length);
    expect(fid.divergences).toEqual([]);
  });

  it("matches timer cancel / disposition stream", async () => {
    const packet = await loadCanary();
    const stream = byFamily(packet.streams, "timer_cancel_quoting_stale_fire");
    const fid = checkStreamFidelity(stream);
    expect(fid.checkpointComparisons).toBeGreaterThan(0);
    expect(fid.ledgerCompared).toBe(true);
    expect(fid.divergences).toEqual([]);
  });

  it("matches checkpoint rollover stream", async () => {
    const packet = await loadCanary();
    const stream = byFamily(packet.streams, "rollover_continuity");
    expect(stream.segments.length).toBe(2);
    const fid = checkStreamFidelity(stream);
    expect(fid.checkpointComparisons).toBeGreaterThan(0);
    expect(fid.divergences).toEqual([]);
  });

  it("matches stream-derivable fields on stale-tool skip stream", async () => {
    const packet = await loadCanary();
    const stream = byFamily(packet.streams, "lookup_latency_duplicate_pressure");
    const fid = checkStreamFidelity(stream);
    const hasStaleOracle = stream.sidecar.decisions.some(
      (d) => d.stale_tool_result_event_ids.length > 0,
    );
    expect(hasStaleOracle).toBe(true);
    expect(fid.unavailableFields).toContain("stale_tool_result_event_ids");
    expect(fid.divergences).toEqual([]);
  });

  it("matches floor_owned from activity/composing; floor_open unavailable", async () => {
    const packet = await loadCanary();
    const owned = packet.streams.find((s) =>
      s.sidecar.decisions.some((d) => d.floor_owned),
    );
    expect(owned).toBeTruthy();
    const fid = checkStreamFidelity(owned!);
    expect(fid.unavailableFields).toContain("floor_open");
    expect(fid.divergences).toEqual([]);
  });

  it("detects an action_executed inside an oracle-idle decision interval", async () => {
    const packet = await loadCanary();
    const original = packet.streams.find((stream) =>
      stream.sidecar.decisions.some((decision) => decision.action.type !== "idle"),
    )!;
    const decisionIndex = original.sidecar.decisions.findIndex(
      (decision) => decision.action.type !== "idle",
    );
    const stream = {
      ...original,
      sidecar: {
        ...original.sidecar,
        decisions: original.sidecar.decisions.map((decision, index) =>
          index === decisionIndex
            ? {
                ...decision,
                action: {
                  type: "idle" as const,
                  reason: "no_trigger" as const,
                  related_event_id: null,
                },
              }
            : decision,
        ),
      },
    };
    const fidelity = checkStreamFidelity(stream);
    expect(fidelity.divergences).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          field: "oracle_action",
          expected: "no action_executed for idle",
        }),
      ]),
    );
  });

  it("reports zero stream-derivable divergences across the full canary packet", async () => {
    const packet = await loadCanary();
    const all: string[] = [];
    for (const stream of packet.streams) {
      const fid = checkStreamFidelity(stream);
      expect(fid.unavailableFields).toEqual(
        expect.arrayContaining([
          "floor_open",
          "stale_tool_result_event_ids",
          "raw_attempted_action",
          "license_block_code",
        ]),
      );
      for (const d of fid.divergences) {
        all.push(`${d.streamSha256.slice(0, 12)} ${d.location} ${d.field}`);
      }
    }
    expect(all).toEqual([]);
  });
});
