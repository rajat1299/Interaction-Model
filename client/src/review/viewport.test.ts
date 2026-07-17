import { describe, expect, it } from "vitest";
import { buildHighlightedNodes } from "./viewport";

describe("UTF-16 highlighting", () => {
  it("indexes by UTF-16 code units, including astral surrogate pairs", () => {
    // "A" + musical G-clef (U+1D11E, surrogate pair) + "B"
    const text = "A\uD834\uDD1EB";
    expect(text.length).toBe(4); // UTF-16 code units

    // Highlight only the astral character (units 1..3)
    const frag = buildHighlightedNodes(text, [
      { start: 1, end: 3, className: "vp-mark" },
    ]);
    const parts: { type: string; text: string; cls?: string }[] = [];
    frag.childNodes.forEach((n) => {
      if (n.nodeType === Node.TEXT_NODE) {
        parts.push({ type: "text", text: n.textContent ?? "" });
      } else if (n instanceof HTMLElement) {
        parts.push({ type: "span", text: n.textContent ?? "", cls: n.className });
      }
    });
    expect(parts).toEqual([
      { type: "text", text: "A" },
      { type: "span", text: "\uD834\uDD1E", cls: "vp-mark" },
      { type: "text", text: "B" },
    ]);
  });

  it("highlights selection ranges by code unit offsets", () => {
    const text = "hello";
    const frag = buildHighlightedNodes(text, [
      { start: 1, end: 4, className: "vp-selection" },
    ]);
    const html = Array.from(frag.childNodes)
      .map((n) =>
        n instanceof HTMLElement
          ? `<${n.className}>${n.textContent}</>`
          : n.textContent,
      )
      .join("");
    expect(html).toBe("h<vp-selection>ell</>o");
  });
});
