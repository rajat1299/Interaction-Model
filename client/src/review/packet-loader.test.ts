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
});
