import { describe, expect, it } from "vitest";
import {
  loadPacketFromEntries,
  sha256Hex,
  type PacketEntry,
} from "./packet-loader";
import { loadCanaryEntries } from "./test-fixtures";

function cloneEntries(): PacketEntry[] {
  return loadCanaryEntries().map((entry) => ({ ...entry }));
}

async function replaceHashed(entries: PacketEntry[], path: string, text: string): Promise<void> {
  const entry = entries.find((item) => item.path === path);
  const sums = entries.find((item) => item.path === "SHA256SUMS");
  if (!entry || !sums) throw new Error(`missing test fixture entry: ${path}`);
  entry.text = text;
  const suffix = `  ${path}`;
  let found = false;
  const hash = await sha256Hex(text);
  sums.text = sums.text
    .split("\n")
    .map((line) => {
      if (!line.endsWith(suffix)) return line;
      found = true;
      return `${hash}${suffix}`;
    })
    .join("\n");
  if (!found) throw new Error(`missing SHA256SUMS entry: ${path}`);
}

async function addHashed(entries: PacketEntry[], path: string, text: string): Promise<void> {
  const sums = entries.find((item) => item.path === "SHA256SUMS");
  if (!sums) throw new Error("missing SHA256SUMS");
  entries.push({ path, text });
  sums.text = `${sums.text.trimEnd()}\n${await sha256Hex(text)}  ${path}\n`;
}

async function addPhase2Evidence(entries: PacketEntry[]): Promise<void> {
  const chosen = entries
    .filter((entry) => entry.path.endsWith("/sidecar.json"))
    .slice(0, 3)
    .map((entry, index) => {
      const sidecar = JSON.parse(entry.text) as { stream_sha256: string; decisions: unknown[] };
      return { sidecar, decision: sidecar.decisions[0], source: `source-${index}` };
    });
  let rank = 0;
  const decisions = entries
    .filter((entry) => entry.path.endsWith("/sidecar.json"))
    .flatMap((entry) => {
      const sidecar = JSON.parse(entry.text) as {
        stream_sha256: string;
        decisions: Array<{ action: unknown; observed_policy_seq: number }>;
      };
      return sidecar.decisions.map((decision) => {
        const selected = chosen.find(
          (item) => item.sidecar.stream_sha256 === sidecar.stream_sha256 &&
            (item.decision as { observed_policy_seq: number }).observed_policy_seq === decision.observed_policy_seq,
        );
        const alternate = (decision.action as { type: string }).type === "nudge"
          ? { type: "idle", reason: "no_trigger", related_event_id: null }
          : { type: "nudge", fire_event_id: "e_000001" };
        return {
          candidates: selected
            ? [
                {
                  candidate_id: "A",
                  action: decision.action,
                  license: { result: "licensed", codes: [] },
                  reveal: { origin: "oracle", provenance: { request_sha256: "sha256:" + "1".repeat(64) } },
                },
                {
                  candidate_id: "B",
                  action: alternate,
                  license: { result: "blocked", codes: ["reason_mismatch"] },
                  reveal: { origin: "teacher", provenance: { request_sha256: "sha256:" + "2".repeat(64) } },
                },
              ]
            : [],
          cluster_signature: selected ? `sha256:${"c".repeat(64)}` : null,
          comparison: selected ? "causal_disagreement" : "equivalent",
          decision_policy_seq: decision.observed_policy_seq,
          oracle_action: decision.action,
          priority_rank: rank++,
          review_evidence: {
            wave_id: "sentinel-0",
            template_id: "packet-template",
            causal_state_class: "packet-state",
            boundary_class: "ordinary",
            risk_flags: selected ? ["oracle_teacher_non_equivalence"] : [],
            idle_boundary: null,
            rollover: false,
            trust_cell: { protocol: "generation", family: "neutral_typing", floor: "closed" },
            review_route: {
              review_required: Boolean(selected),
              mandatory: Boolean(selected),
              sample_rate: selected ? 1 : 0,
              reasons: selected ? ["teacher_oracle_disagreement"] : [],
              provisional_label_origin: null,
            },
          },
          source_unit_id: selected?.source ?? "ordinary-source",
          stream_sha256: sidecar.stream_sha256,
        };
      });
    });
  const member_identities = chosen.map((item) => ({
    stream_sha256: item.sidecar.stream_sha256,
    decision_policy_seq: (item.decision as { observed_policy_seq: number }).observed_policy_seq,
  }));
  const evidence = {
    format_version: 1,
    teacher_evidence_identity: `sha256:${"d".repeat(64)}`,
    blind_seed_sha256: `sha256:${"b".repeat(64)}`,
    decisions,
    clusters: [{
      signature: `sha256:${"c".repeat(64)}`,
      priority_rank: 0,
      representative: member_identities[0],
      confirmations: member_identities.slice(1),
      member_identities,
      mechanical_invariants: {
        all_members_non_equivalent: true,
        distinct_source_unit_count: 3,
        member_count: 3,
        priority_order_sha256: `sha256:${"e".repeat(64)}`,
        three_distinct_source_units: true,
      },
    }],
    mechanical_invariants: {
      all_packet_decisions_included: true,
      decision_identity_count: decisions.length,
      non_equivalent_decision_count: 3,
    },
  };
  await addHashed(entries, "phase2-review-evidence.json", JSON.stringify(evidence));
}

describe("packet loader", () => {
  it("loads teacher-canary with verified SHA256SUMS", async () => {
    const result = await loadPacketFromEntries(loadCanaryEntries());
    if (!result.ok) throw new Error(result.errors.join("\n"));
    expect(result.packet.streams.length).toBe(38);
    const totalDecisions = result.packet.streams.reduce(
      (n, s) => n + s.sidecar.decisions.length,
      0,
    );
    expect(totalDecisions).toBeGreaterThan(200);
  });

  it("rejects hash mismatch", async () => {
    const entries = loadCanaryEntries();
    const mani = entries.find((e) => e.path === "manifest.json")!;
    mani.text = mani.text.replace("{", "{ ");
    const result = await loadPacketFromEntries(entries);
    expect(result.ok).toBe(false);
    if (result.ok) return;
    expect(result.errors.some((e) => e.includes("hash mismatch"))).toBe(true);
  });

  it("rejects missing required file", async () => {
    const entries = loadCanaryEntries().filter((e) => e.path !== "manifest.json");
    const result = await loadPacketFromEntries(entries);
    expect(result.ok).toBe(false);
    if (result.ok) return;
    expect(result.errors.some((e) => e.includes("missing manifest.json"))).toBe(true);
  });

  it("rejects duplicate path entries", async () => {
    const entries = loadCanaryEntries();
    const dup: PacketEntry = { ...entries[0] };
    const result = await loadPacketFromEntries([...entries, dup]);
    expect(result.ok).toBe(false);
    if (result.ok) return;
    expect(result.errors.some((e) => e.includes("duplicate path"))).toBe(true);
  });

  it("rejects path-mismatched segment content hash", async () => {
    const entries = loadCanaryEntries();
    const seg = entries.find((e) => e.path.startsWith("teacher/") && e.path.endsWith(".jsonl"))!;
    seg.text = seg.text + "\n";
    const result = await loadPacketFromEntries(entries);
    expect(result.ok).toBe(false);
    if (result.ok) return;
    expect(
      result.errors.some(
        (e) => e.includes("hash mismatch") || e.includes("content hash"),
      ),
    ).toBe(true);
  });

  it("requires both packet metadata files in SHA256SUMS", async () => {
    const entries = cloneEntries();
    const sums = entries.find((entry) => entry.path === "SHA256SUMS")!;
    sums.text = sums.text
      .split("\n")
      .filter((line) => !line.endsWith("  manifest.json") && !line.endsWith("  source-index.json"))
      .join("\n");
    const result = await loadPacketFromEntries(entries);
    expect(result.ok).toBe(false);
    if (result.ok) return;
    expect(result.errors).toEqual(expect.arrayContaining([
      "SHA256SUMS missing required entry: manifest.json",
      "SHA256SUMS missing required entry: source-index.json",
    ]));
  });

  it("rejects structurally empty manifest streams without throwing", async () => {
    const entries = cloneEntries();
    await replaceHashed(entries, "manifest.json", JSON.stringify({ format_version: 1, streams: [{}] }));
    const result = await loadPacketFromEntries(entries);
    expect(result.ok).toBe(false);
    if (result.ok) return;
    expect(result.errors.some((error) => error.includes("streams[0].stream_sha256"))).toBe(true);
  });

  it("rejects unsupported versions, batch numbers, and empty inventories", async () => {
    const entries = cloneEntries();
    await replaceHashed(
      entries,
      "manifest.json",
      JSON.stringify({ format_version: 2, streams: [] }),
    );
    await replaceHashed(
      entries,
      "source-index.json",
      JSON.stringify({
        batch: 2,
        format_version: 2,
        source_identity_rule: "unsupported",
        sources: [],
      }),
    );
    const result = await loadPacketFromEntries(entries);
    expect(result.ok).toBe(false);
    if (result.ok) return;
    expect(result.errors).toContain("manifest.json: manifest.json.format_version must be 1");
  });

  it.each([
    ["sidecar", (entries: PacketEntry[]) => entries.find((entry) => entry.path.endsWith("/sidecar.json"))!],
    ["runtime ledger", (entries: PacketEntry[]) => entries.find((entry) => entry.path.endsWith("/runtime-ledger.json"))!],
    ["source index", (entries: PacketEntry[]) => entries.find((entry) => entry.path === "source-index.json")!],
  ])("rejects malformed %s", async (_name, findEntry) => {
    const entries = cloneEntries();
    const entry = findEntry(entries);
    await replaceHashed(entries, entry.path, "[]");
    const result = await loadPacketFromEntries(entries);
    expect(result.ok).toBe(false);
    if (result.ok) return;
    expect(result.errors.some((error) => error.includes(entry.path))).toBe(true);
  });

  it("reconciles manifest decision counts with sidecars", async () => {
    const entries = cloneEntries();
    const manifest = JSON.parse(entries.find((entry) => entry.path === "manifest.json")!.text);
    const checkpointPath = entries.find((entry) =>
      entry.path.endsWith("/checkpoint-selection.json"),
    )!.path;
    const streamHash = checkpointPath.split("/")[1];
    const stream = manifest.streams.find(
      (item: { stream_sha256: string }) => item.stream_sha256.endsWith(streamHash),
    );
    stream.decision_count++;
    await replaceHashed(entries, "manifest.json", JSON.stringify(manifest));
    const result = await loadPacketFromEntries(entries);
    expect(result.ok).toBe(false);
    if (result.ok) return;
    expect(result.errors.some((error) => error.includes("decisions") && error.includes("manifest decision_count"))).toBe(true);
  });

  it("rejects a source unit whose sidecar multiset no longer closes over its parents", async () => {
    const entries = cloneEntries();
    const sourceIndex = JSON.parse(
      entries.find((entry) => entry.path === "source-index.json")!.text,
    );
    const source = sourceIndex.sources.find(
      (item: { sidecar_sha256s: string[] }) => item.sidecar_sha256s.length > 1,
    );
    source.sidecar_sha256s[1] = source.sidecar_sha256s[0];
    await replaceHashed(entries, "source-index.json", JSON.stringify(sourceIndex));
    const result = await loadPacketFromEntries(entries);
    expect(result.ok).toBe(false);
    if (result.ok) return;
    expect(result.errors).toContain(
      "source-index.json: sidecar identities do not close over source unit",
    );
  });

  it("rejects checkpoint candidates that no longer close over raw segment identities", async () => {
    const entries = cloneEntries();
    const sourceIndex = JSON.parse(
      entries.find((entry) => entry.path === "source-index.json")!.text,
    );
    const source = sourceIndex.sources.find(
      (item: { checkpoint: unknown }) => item.checkpoint !== null,
    );
    source.raw_source_sha256s[0] = `sha256:${"0".repeat(64)}`;
    await replaceHashed(entries, "source-index.json", JSON.stringify(sourceIndex));
    const result = await loadPacketFromEntries(entries);
    expect(result.ok).toBe(false);
    if (result.ok) return;
    expect(result.errors).toContain(
      "source-index.json: checkpoint segments do not close over raw sources",
    );
  });

  it("returns an error instead of throwing for malformed entry objects", async () => {
    await expect(
      loadPacketFromEntries([null] as unknown as PacketEntry[]),
    ).resolves.toMatchObject({ ok: false });
  });

  it("sha256Hex is stable", async () => {
    expect(await sha256Hex("abc")).toBe(
      "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
    );
  });

  it("loads checksum-bound Phase 2 evidence only when it closes over sidecar actions", async () => {
    const entries = cloneEntries();
    await addPhase2Evidence(entries);
    const result = await loadPacketFromEntries(entries);
    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.packet.phase2ReviewEvidence?.clusters[0].confirmations).toHaveLength(2);
    expect(result.packet.phase2ReviewEvidence?.decisions).toHaveLength(
      result.packet.streams.reduce((total, stream) => total + stream.sidecar.decisions.length, 0),
    );
  });

  it("rejects Phase 2 evidence not listed in the checksum inventory", async () => {
    const entries = cloneEntries();
    await addPhase2Evidence(entries);
    const sums = entries.find((entry) => entry.path === "SHA256SUMS")!;
    sums.text = sums.text
      .split("\n")
      .filter((line) => !line.endsWith("  phase2-review-evidence.json"))
      .join("\n");
    const result = await loadPacketFromEntries(entries);
    expect(result.ok).toBe(false);
    if (result.ok) return;
    expect(result.errors).toContain("undeclared file not in SHA256SUMS: phase2-review-evidence.json");
  });

  it("rejects Phase 2 action or three-source cluster mismatches", async () => {
    const entries = cloneEntries();
    await addPhase2Evidence(entries);
    const path = "phase2-review-evidence.json";
    const evidence = JSON.parse(entries.find((entry) => entry.path === path)!.text);
    evidence.decisions[0].oracle_action = { type: "nudge", fire_event_id: "e_bad" };
    await replaceHashed(entries, path, JSON.stringify(evidence));
    const actionResult = await loadPacketFromEntries(entries);
    expect(actionResult.ok).toBe(false);
    if (!actionResult.ok) expect(actionResult.errors.join("\n")).toContain("candidates do not close over actions");

    const sourceEntries = cloneEntries();
    await addPhase2Evidence(sourceEntries);
    const sourceEvidence = JSON.parse(sourceEntries.find((entry) => entry.path === path)!.text);
    const member = sourceEvidence.clusters[0].member_identities[1];
    const record = sourceEvidence.decisions.find(
      (item: { stream_sha256: string; decision_policy_seq: number }) =>
        item.stream_sha256 === member.stream_sha256 && item.decision_policy_seq === member.decision_policy_seq,
    );
    record.source_unit_id = sourceEvidence.decisions.find(
      (item: { stream_sha256: string; decision_policy_seq: number }) =>
        item.stream_sha256 === sourceEvidence.clusters[0].representative.stream_sha256 &&
        item.decision_policy_seq === sourceEvidence.clusters[0].representative.decision_policy_seq,
    ).source_unit_id;
    await replaceHashed(sourceEntries, path, JSON.stringify(sourceEvidence));
    const sourceResult = await loadPacketFromEntries(sourceEntries);
    expect(sourceResult.ok).toBe(false);
    if (!sourceResult.ok) expect(sourceResult.errors.join("\n")).toContain("three distinct source units");
  });
});
