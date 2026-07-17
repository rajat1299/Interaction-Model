import { describe, expect, it } from "vitest";
import { projectAppliedMark } from "./mark-projection";
import type { AppliedMark } from "./reducer";

function mark(text: string, start: number, end: number): AppliedMark {
  return {
    markEventId: "e_mark",
    instructionEventId: "e_instruction",
    instructionStart: 0,
    instructionEnd: 4,
    instructionText: "mark",
    targetEventId: "e_source",
    targetStart: start,
    targetEnd: end,
    targetText: text.slice(start, end),
  };
}

describe("mark occurrence projection", () => {
  it("follows an untouched target through UTF-16 prefix insertion", () => {
    expect(projectAppliedMark(mark("cat", 0, 3), "cat", "e_next", "😀 cat")).toEqual({
      applied: expect.objectContaining({ targetEventId: "e_next", targetStart: 3, targetEnd: 6 }),
      ambiguous: [],
    });
  });

  it("uses unique unchanged context to disambiguate repeated target text", () => {
    expect(projectAppliedMark(mark("ab", 0, 1), "ab", "e_next", "aab")).toEqual({
      applied: expect.objectContaining({ targetStart: 1, targetEnd: 2 }),
      ambiguous: [],
    });
  });

  it("represents an inserted indistinguishable occurrence as explicit ambiguity", () => {
    expect(projectAppliedMark(mark("cat", 0, 3), "cat", "e_next", "cat cat")).toEqual({
      applied: null,
      ambiguous: [
        expect.objectContaining({ targetStart: 0, targetEnd: 3 }),
        expect.objectContaining({ targetStart: 4, targetEnd: 7 }),
      ],
    });
  });

  it("drops a touched or absent target and never revives it", () => {
    expect(projectAppliedMark(mark("cat", 0, 3), "cat", "e_next", "dog")).toEqual({
      applied: null,
      ambiguous: [],
    });
  });

  it("keeps the original occurrence through disjoint edits", () => {
    const before = "A cat B dog C cat D";
    const after = "X cat B dog C cat Y";
    expect(projectAppliedMark(mark(before, 2, 5), before, "e_next", after)).toEqual({
      applied: expect.objectContaining({ targetStart: 2, targetEnd: 5 }),
      ambiguous: [],
    });
  });

  it("matches the canonical Python projection digest over 7,488 Unicode transitions", async () => {
    const alphabet = ["a", "b", "😀"];
    const strings: string[] = [];
    const expand = (prefix: string[], remaining: number): void => {
      if (remaining === 0) {
        strings.push(prefix.join(""));
        return;
      }
      for (const symbol of alphabet) expand([...prefix, symbol], remaining - 1);
    };
    for (let length = 1; length <= 3; length++) expand([], length);

    const rows: unknown[] = [];
    for (const before of strings) {
      const chars = Array.from(before);
      for (const after of strings) {
        for (let start = 0; start < chars.length; start++) {
          for (let end = start + 1; end <= chars.length; end++) {
            const startUtf16 = chars.slice(0, start).join("").length;
            const endUtf16 = chars.slice(0, end).join("").length;
            const target = chars.slice(start, end).join("");
            const projection = projectAppliedMark(
              mark(before, startUtf16, endUtf16),
              before,
              "e_000002",
              after,
            );
            const kind = projection.applied ? "applied" : "ambiguous";
            const targets = projection.applied
              ? [[projection.applied.targetStart, projection.applied.targetEnd]]
              : projection.ambiguous.map((item) => [item.targetStart, item.targetEnd]);
            rows.push([before, after, startUtf16, endUtf16, target, kind, targets]);
          }
        }
      }
    }
    expect(rows).toHaveLength(7_488);
    const digest = await crypto.subtle.digest(
      "SHA-256",
      new TextEncoder().encode(JSON.stringify(rows)),
    );
    const hex = Array.from(new Uint8Array(digest))
      .map((byte) => byte.toString(16).padStart(2, "0"))
      .join("");
    // Generated from src/im/mark_projection.py with autojunk=False on 2026-07-17.
    expect(hex).toBe("b736d0b244741b40c70540f080afc37327561875c0a7357259e7a1c1d0c65301");
  });
});
