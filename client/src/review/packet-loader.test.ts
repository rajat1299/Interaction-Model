import { describe, expect, it } from "vitest";
import {
  loadPacketFromEntries,
  sha256Hex,
  type PacketEntry,
} from "./packet-loader";
import { loadCanaryEntries } from "./test-fixtures";
import {
  phase2CandidateOriginOrder,
  phase2ClusterSignature,
} from "./phase2-review-evidence";

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
  const commitment = `sha256:${"b".repeat(64)}`;
  const sidecars = entries
    .filter((entry) => entry.path.endsWith("/sidecar.json"))
    .map((entry) => JSON.parse(entry.text) as {
      stream_sha256: string;
      decisions: Array<{ action: unknown; observed_policy_seq: number }>;
    });
  const actionGroups = new Map<string, Array<{
    sidecar: (typeof sidecars)[number];
    decision: (typeof sidecars)[number]["decisions"][number];
  }>>();
  sidecars.forEach((sidecar) => sidecar.decisions.forEach((decision) => {
    const group = actionGroups.get(JSON.stringify(decision.action)) ?? [];
    group.push({ sidecar, decision });
    actionGroups.set(JSON.stringify(decision.action), group);
  }));
  const repeated = [...actionGroups.values()].find(
    (group) => new Set(group.map((item) => item.sidecar.stream_sha256)).size >= 3,
  );
  if (!repeated) throw new Error("fixture has no repeated action across three streams");
  const chosen: Array<(typeof repeated)[number] & { source: string }> = [];
  for (const item of repeated) {
    if (chosen.some((existing) => existing.sidecar.stream_sha256 === item.sidecar.stream_sha256)) continue;
    chosen.push({ ...item, source: `source-${chosen.length}` });
    if (chosen.length === 3) break;
  }
  let rank = 0;
  const decisions = [];
  for (const sidecar of sidecars) {
    for (const decision of sidecar.decisions) {
        const selected = chosen.find(
          (item) => item.sidecar.stream_sha256 === sidecar.stream_sha256 &&
            item.decision.observed_policy_seq === decision.observed_policy_seq,
        );
        const alternate = (decision.action as { type: string }).type === "nudge"
          ? { type: "idle", reason: "no_trigger", related_event_id: null }
          : { type: "nudge", fire_event_id: "e_000001" };
        const identity = {
          stream_sha256: sidecar.stream_sha256,
          decision_policy_seq: decision.observed_policy_seq,
        };
        const origins = selected
          ? await phase2CandidateOriginOrder(commitment, identity)
          : [];
        const candidate = (candidate_id: "A" | "B", origin: "oracle" | "teacher") => ({
          candidate_id,
          action: origin === "oracle" ? decision.action : alternate,
          license: origin === "oracle"
            ? { result: "licensed" as const, codes: [] }
            : { result: "blocked" as const, codes: ["reason_mismatch"] },
          reveal: {
            origin,
            provenance: { request_sha256: `sha256:${(origin === "oracle" ? "1" : "2").repeat(64)}` },
          },
        });
        const action = decision.action as { type: string; reason?: string };
        const routeReasons = [
          ...(["schedule", "cancel", "skip", "nudge"].includes(action.type) ? ["mandatory_action"] : []),
          ...(selected ? ["teacher_oracle_disagreement", "risk_flag"] : []),
          ...(action.type === "idle" && ["awaiting_opening", "already_handled"].includes(action.reason ?? "")
            ? ["idle_reason_100_percent"] : []),
        ];
        const mandatory = routeReasons.length > 0;
        decisions.push({
          candidates: selected ? [candidate("A", origins[0]!), candidate("B", origins[1]!)] : [],
          cluster_signature: null as string | null,
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
            trust_cell: { protocol: "generation", family: "neutral_typing_revision_pause", floor: "closed" },
            review_route: {
              review_required: mandatory,
              mandatory,
              sample_rate: mandatory ? 1 : 0,
              reasons: routeReasons,
              provisional_label_origin: mandatory ? null : "oracle_teacher_agreement",
            },
          },
          source_unit_id: selected?.source ?? "ordinary-source",
          stream_sha256: sidecar.stream_sha256,
        });
    }
  }
  const selectedDecisions = decisions
    .filter((item) => item.comparison === "causal_disagreement")
    .sort((left, right) => left.priority_rank - right.priority_rank);
  const signature = await phase2ClusterSignature(selectedDecisions[0] as never);
  selectedDecisions.forEach((decision) => { decision.cluster_signature = signature; });
  const member_identities = selectedDecisions.map((item) => ({
    stream_sha256: item.stream_sha256,
    decision_policy_seq: item.decision_policy_seq,
  }));
  const confirmationRanks = await Promise.all(selectedDecisions.slice(1).map(async (item) => ({
    item,
    rank: await sha256Hex(`${commitment}|${signature}|${item.stream_sha256}\x00${item.decision_policy_seq}`),
  })));
  confirmationRanks.sort((left, right) => left.rank.localeCompare(right.rank));
  const confirmations = confirmationRanks.map(({ item }) => ({
    stream_sha256: item.stream_sha256,
    decision_policy_seq: item.decision_policy_seq,
  }));
  const priorityJson = `[${member_identities.map((item) => `{"decision_policy_seq":${item.decision_policy_seq},"stream_sha256":${JSON.stringify(item.stream_sha256)}}`).join(",")}]`;
  const evidence = {
    format_version: 1,
    teacher_evidence_identity: `sha256:${"d".repeat(64)}`,
    blind_seed_sha256: commitment,
    decisions,
    clusters: [{
      signature,
      priority_rank: selectedDecisions[0].priority_rank,
      representative: member_identities[0],
      confirmations,
      member_identities,
      mechanical_invariants: {
        all_members_non_equivalent: true,
        distinct_source_unit_count: 3,
        member_count: 3,
        priority_order_sha256: `sha256:${await sha256Hex(priorityJson)}`,
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
    if (!actionResult.ok) expect(actionResult.errors.join("\n")).toContain("candidate origin does not close");

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
    if (!sourceResult.ok) expect(sourceResult.errors.join("\n")).toContain("confirmations do not match");
  });

  it("rejects reversed A/B origins and confirmation commitment order", async () => {
    const candidateEntries = cloneEntries();
    await addPhase2Evidence(candidateEntries);
    const path = "phase2-review-evidence.json";
    const candidateEvidence = JSON.parse(candidateEntries.find((entry) => entry.path === path)!.text);
    const target = candidateEvidence.decisions.find((item: { candidates: unknown[] }) => item.candidates.length === 2);
    target.candidates.reverse();
    await replaceHashed(candidateEntries, path, JSON.stringify(candidateEvidence));
    const candidateResult = await loadPacketFromEntries(candidateEntries);
    expect(candidateResult.ok).toBe(false);
    if (!candidateResult.ok) expect(candidateResult.errors.join("\n")).toContain("canonical A then B");

    const revealEntries = cloneEntries();
    await addPhase2Evidence(revealEntries);
    const revealEvidence = JSON.parse(revealEntries.find((entry) => entry.path === path)!.text);
    const revealTarget = revealEvidence.decisions.find((item: { candidates: unknown[] }) => item.candidates.length === 2);
    [revealTarget.candidates[0].reveal, revealTarget.candidates[1].reveal] = [
      revealTarget.candidates[1].reveal,
      revealTarget.candidates[0].reveal,
    ];
    await replaceHashed(revealEntries, path, JSON.stringify(revealEvidence));
    const revealResult = await loadPacketFromEntries(revealEntries);
    expect(revealResult.ok).toBe(false);
    if (!revealResult.ok) expect(revealResult.errors.join("\n")).toContain("blind seed commitment");

    const confirmationEntries = cloneEntries();
    await addPhase2Evidence(confirmationEntries);
    const confirmationEvidence = JSON.parse(confirmationEntries.find((entry) => entry.path === path)!.text);
    confirmationEvidence.clusters[0].confirmations.reverse();
    await replaceHashed(confirmationEntries, path, JSON.stringify(confirmationEvidence));
    const confirmationResult = await loadPacketFromEntries(confirmationEntries);
    expect(confirmationResult.ok).toBe(false);
    if (!confirmationResult.ok) expect(confirmationResult.errors.join("\n")).toContain("confirmations do not match");
  });

  it("rejects out-of-range and inconsistent Phase 2 review routes", async () => {
    const rateEntries = cloneEntries();
    await addPhase2Evidence(rateEntries);
    const path = "phase2-review-evidence.json";
    const rateEvidence = JSON.parse(rateEntries.find((entry) => entry.path === path)!.text);
    rateEvidence.decisions[0].review_evidence.review_route.sample_rate = 2.5;
    await replaceHashed(rateEntries, path, JSON.stringify(rateEvidence));
    const rateResult = await loadPacketFromEntries(rateEntries);
    expect(rateResult.ok).toBe(false);
    if (!rateResult.ok) expect(rateResult.errors.join("\n")).toContain("within [0, 1]");

    const mandatoryEntries = cloneEntries();
    await addPhase2Evidence(mandatoryEntries);
    const mandatoryEvidence = JSON.parse(mandatoryEntries.find((entry) => entry.path === path)!.text);
    const mandatory = mandatoryEvidence.decisions.find(
      (item: { review_evidence: { review_route: { mandatory: boolean } } }) => item.review_evidence.review_route.mandatory,
    );
    mandatory.review_evidence.review_route.review_required = false;
    await replaceHashed(mandatoryEntries, path, JSON.stringify(mandatoryEvidence));
    const mandatoryResult = await loadPacketFromEntries(mandatoryEntries);
    expect(mandatoryResult.ok).toBe(false);
    if (!mandatoryResult.ok) expect(mandatoryResult.errors.join("\n")).toContain("canonical mandatory router");

    const inventedEntries = cloneEntries();
    await addPhase2Evidence(inventedEntries);
    const inventedEvidence = JSON.parse(inventedEntries.find((entry) => entry.path === path)!.text);
    inventedEvidence.decisions[0].review_evidence.review_route = {
      review_required: true,
      mandatory: false,
      sample_rate: 0,
      reasons: ["invented_reason"],
      provisional_label_origin: null,
    };
    await replaceHashed(inventedEntries, path, JSON.stringify(inventedEvidence));
    const inventedResult = await loadPacketFromEntries(inventedEntries);
    expect(inventedResult.ok).toBe(false);
    if (!inventedResult.ok) expect(inventedResult.errors.join("\n")).toContain("closed router vocabulary");
  });
});
