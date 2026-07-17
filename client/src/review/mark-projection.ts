/** Exact TypeScript port of src/im/mark_projection.py (autojunk=False, no junk). */

import type { AppliedMark } from "./reducer";

type Range = [number, number];
type Match = [number, number, number];
type Opcode = ["equal" | "replace" | "delete" | "insert", number, number, number, number];

export type MarkProjection = {
  applied: AppliedMark | null;
  ambiguous: AppliedMark[];
};

function codepoints(text: string): string[] {
  return Array.from(text);
}

function utf16ToCodepoint(chars: string[], offset: number): number | null {
  if (!Number.isInteger(offset) || offset < 0) return null;
  let utf16 = 0;
  for (let i = 0; i <= chars.length; i++) {
    if (utf16 === offset) return i;
    if (i === chars.length) break;
    utf16 += chars[i].length;
    if (utf16 > offset) return null;
  }
  return null;
}

function codepointToUtf16(chars: string[], offset: number): number {
  let utf16 = 0;
  for (let i = 0; i < offset; i++) utf16 += chars[i].length;
  return utf16;
}

function sliceEquals(a: string[], start: number, end: number, b: string[]): boolean {
  if (end - start !== b.length) return false;
  for (let i = 0; i < b.length; i++) if (a[start + i] !== b[i]) return false;
  return true;
}

function occurrences(haystack: string[], needle: string[]): number[] {
  if (needle.length === 0) return [];
  const found: number[] = [];
  for (let start = 0; start <= haystack.length - needle.length; start++) {
    if (sliceEquals(haystack, start, start + needle.length, needle)) found.push(start);
  }
  return found;
}

/** Python difflib.SequenceMatcher matching blocks for autojunk=False and no junk predicate. */
function matchingBlocks(a: string[], b: string[]): Match[] {
  const b2j = new Map<string, number[]>();
  for (let j = 0; j < b.length; j++) {
    const positions = b2j.get(b[j]);
    if (positions) positions.push(j);
    else b2j.set(b[j], [j]);
  }

  const longest = (alo: number, ahi: number, blo: number, bhi: number): Match => {
    let besti = alo;
    let bestj = blo;
    let bestsize = 0;
    let j2len = new Map<number, number>();
    for (let i = alo; i < ahi; i++) {
      const next = new Map<number, number>();
      for (const j of b2j.get(a[i]) ?? []) {
        if (j < blo) continue;
        if (j >= bhi) break;
        const size = (j2len.get(j - 1) ?? 0) + 1;
        next.set(j, size);
        if (size > bestsize) {
          besti = i - size + 1;
          bestj = j - size + 1;
          bestsize = size;
        }
      }
      j2len = next;
    }
    while (besti > alo && bestj > blo && a[besti - 1] === b[bestj - 1]) {
      besti--;
      bestj--;
      bestsize++;
    }
    while (
      besti + bestsize < ahi &&
      bestj + bestsize < bhi &&
      a[besti + bestsize] === b[bestj + bestsize]
    ) {
      bestsize++;
    }
    return [besti, bestj, bestsize];
  };

  const queue: [number, number, number, number][] = [[0, a.length, 0, b.length]];
  const matches: Match[] = [];
  while (queue.length > 0) {
    const [alo, ahi, blo, bhi] = queue.pop()!;
    const [i, j, size] = longest(alo, ahi, blo, bhi);
    if (size === 0) continue;
    matches.push([i, j, size]);
    if (alo < i && blo < j) queue.push([alo, i, blo, j]);
    if (i + size < ahi && j + size < bhi) {
      queue.push([i + size, ahi, j + size, bhi]);
    }
  }
  matches.sort((x, y) => x[0] - y[0] || x[1] - y[1]);
  const collapsed: Match[] = [];
  for (const match of matches) {
    const prior = collapsed.at(-1);
    if (prior && prior[0] + prior[2] === match[0] && prior[1] + prior[2] === match[1]) {
      prior[2] += match[2];
    } else {
      collapsed.push([...match]);
    }
  }
  collapsed.push([a.length, b.length, 0]);
  return collapsed;
}

function opcodes(a: string[], b: string[]): Opcode[] {
  const out: Opcode[] = [];
  let i = 0;
  let j = 0;
  for (const [ai, bj, size] of matchingBlocks(a, b)) {
    if (i < ai || j < bj) {
      const tag = i < ai && j < bj ? "replace" : i < ai ? "delete" : "insert";
      out.push([tag, i, ai, j, bj]);
    }
    if (size > 0) out.push(["equal", ai, ai + size, bj, bj + size]);
    i = ai + size;
    j = bj + size;
  }
  return out;
}

function equalBlockForRange(
  previous: string[],
  current: string[],
  start: number,
  end: number,
): [number, number, number, number] | null {
  for (const [tag, previousStart, previousEnd, currentStart, currentEnd] of opcodes(
    previous,
    current,
  )) {
    if (tag === "equal" && start >= previousStart && end <= previousEnd) {
      return [previousStart, previousEnd, currentStart, currentEnd];
    }
  }
  return null;
}

function uniqueProjection(
  previous: string[],
  current: string[],
  start: number,
  end: number,
): Range | null {
  const block = equalBlockForRange(previous, current, start, end);
  if (!block) return null;
  const [previousStart, previousEnd, currentStart] = block;
  const context = previous.slice(previousStart, previousEnd);
  if (occurrences(previous, context).length !== 1 || occurrences(current, context).length !== 1) {
    return null;
  }
  return [currentStart + start - previousStart, currentStart + end - previousStart];
}

function matchingOccurrences(
  text: string[],
  needle: string[],
  candidateStart: number,
  candidateEnd: number,
): Range[] {
  return occurrences(text, needle)
    .map((start): Range => [start, start + needle.length])
    .filter(([start, end]) =>
      candidateStart < candidateEnd
        ? start < candidateEnd && end > candidateStart
        : start < candidateStart && candidateStart < end,
    );
}

function ambiguousProjection(
  previous: string[],
  current: string[],
  start: number,
  end: number,
  target: string[],
): Range[] {
  const exact = uniqueProjection(previous, current, start, end);
  if (exact) return [];

  const repeatedBlock = equalBlockForRange(previous, current, start, end);
  if (repeatedBlock) {
    const [previousStart, previousEnd] = repeatedBlock;
    const context = previous.slice(previousStart, previousEnd);
    const relativeStart = start - previousStart;
    const relativeEnd = end - previousStart;
    return occurrences(current, context)
      .map((contextStart): Range => [
        contextStart + relativeStart,
        contextStart + relativeEnd,
      ])
      .filter(([candidateStart, candidateEnd]) =>
        sliceEquals(current, candidateStart, candidateEnd, target),
      );
  }

  const affected = opcodes(previous, current)
    .filter(
      ([, previousStart, previousEnd]) =>
        Math.max(start, previousStart) < Math.min(end, previousEnd) ||
        (previousStart === previousEnd && start < previousStart && previousStart < end),
    )
    .map(([, , , currentStart, currentEnd]): Range => [currentStart, currentEnd]);
  if (affected.length === 0) return [];
  const candidateStart = Math.min(...affected.map((item) => item[0]));
  const candidateEnd = Math.max(...affected.map((item) => item[1]));
  const replacements = matchingOccurrences(current, target, candidateStart, candidateEnd);
  return replacements.length === 1 ? replacements : [];
}

/** Project one current mark through one subsequent snapshot using canonical occurrence identity. */
export function projectAppliedMark(
  mark: AppliedMark,
  previousText: string,
  snapshotEventId: string,
  currentText: string,
): MarkProjection {
  const previous = codepoints(previousText);
  const current = codepoints(currentText);
  const target = codepoints(mark.targetText);
  const start = utf16ToCodepoint(previous, mark.targetStart);
  const end = utf16ToCodepoint(previous, mark.targetEnd);
  if (start === null || end === null || !sliceEquals(previous, start, end, target)) {
    return { applied: null, ambiguous: [] };
  }

  const make = ([candidateStart, candidateEnd]: Range): AppliedMark => ({
    ...mark,
    targetEventId: snapshotEventId,
    targetStart: codepointToUtf16(current, candidateStart),
    targetEnd: codepointToUtf16(current, candidateEnd),
  });
  const exact = uniqueProjection(previous, current, start, end);
  if (exact) return { applied: make(exact), ambiguous: [] };
  return {
    applied: null,
    ambiguous: ambiguousProjection(previous, current, start, end, target).map(make),
  };
}
