/**
 * 行级 diff 工具（基于 vscode-diff）。
 *
 * 核心能力：
 * - diffSide：base ↔ 某一侧，产出带坐标的变更块（含字符级 inner）
 * - commonLinesText：两侧保序公共行，用作本地上传对比的「公共祖先」
 */
import { linesDiffComputers } from "vscode-diff";
import type {
  InnerRange,
  LineSpan,
  Side,
  SideChange,
} from "./types";

/** How whitespace differences are treated when diffing. */
export type WhitespaceMode = "none" | "trailing" | "all";

export interface DiffOptions {
  whitespace?: WhitespaceMode;
  /**
   * When set, skip inner (character-level) diffs above this combined line
   * count to stay responsive on very large inputs.
   */
  innerLineBudget?: number;
}

const BASE_DIFF_OPTIONS = {
  ignoreTrimWhitespace: false,
  maxComputationTimeMs: 5000,
  computeMoves: false,
};

export function splitLines(text: string): string[] {
  return text.split("\n");
}

/**
 * 两侧按行的最长公共子序列（保序、完全相同的行），拼成文本。
 * 用于本地双文件对比时作为公共祖先 / 结果栏初始内容。
 */
export function commonLinesText(left: string, right: string): string {
  const leftLines = splitLines(left);
  const rightLines = splitLines(right);
  if (leftLines.length === 0 || rightLines.length === 0) {
    return "";
  }

  const { changes } = linesDiffComputers.getDefault().computeDiff(
    leftLines,
    rightLines,
    { ...BASE_DIFF_OPTIONS, ignoreTrimWhitespace: false },
  );

  // 左侧未进入任何 diff 原区间的行 = 与右侧相同且保序的公共行
  const removed = new Uint8Array(leftLines.length);
  for (const change of changes) {
    const from = change.original.startLineNumber - 1;
    const to = change.original.endLineNumberExclusive - 1;
    for (let i = from; i < to && i < removed.length; i++) {
      if (i >= 0) {
        removed[i] = 1;
      }
    }
  }

  const common: string[] = [];
  for (let i = 0; i < leftLines.length; i++) {
    if (!removed[i]) {
      common.push(leftLines[i]);
    }
  }
  return common.join("\n");
}

/** Collapses runs of whitespace to a single space and trims, for "ignore all". */
function normalizeAllWhitespace(line: string): string {
  return line.replace(/\s+/g, " ").trim();
}

/**
 * Diffs `base` against one side and returns the side's changes anchored in both
 * base and side coordinates, with character-level inner ranges.
 */
export function diffSide(
  baseLines: string[],
  sideLines: string[],
  side: Side,
  options: DiffOptions = {},
): SideChange[] {
  const whitespace = options.whitespace ?? "none";
  // "all" whitespace is handled by normalizing the compared lines; the diff
  // computer's own ignoreTrimWhitespace covers the "trailing" case.
  const compareBase =
    whitespace === "all" ? baseLines.map(normalizeAllWhitespace) : baseLines;
  const compareSide =
    whitespace === "all" ? sideLines.map(normalizeAllWhitespace) : sideLines;

  const diffOptions = {
    ...BASE_DIFF_OPTIONS,
    ignoreTrimWhitespace: whitespace !== "none",
  };

  const { changes } = linesDiffComputers
    .getDefault()
    .computeDiff(compareBase, compareSide, diffOptions);

  return changes.map((change) => {
    const baseSpan: LineSpan = {
      start: change.original.startLineNumber,
      endExclusive: change.original.endLineNumberExclusive,
    };
    const sideSpan: LineSpan = {
      start: change.modified.startLineNumber,
      endExclusive: change.modified.endLineNumberExclusive,
    };
    const innerBase: InnerRange[] = [];
    const innerSide: InnerRange[] = [];
    for (const inner of change.innerChanges ?? []) {
      innerBase.push(toInnerRange(inner.originalRange));
      innerSide.push(toInnerRange(inner.modifiedRange));
    }
    return {
      side,
      role: roleFor(baseSpan, sideSpan),
      baseSpan,
      sideSpan,
      innerBase,
      innerSide,
    };
  });
}

function roleFor(
  baseSpan: LineSpan,
  sideSpan: LineSpan,
): SideChange["role"] {
  const baseEmpty = baseSpan.start === baseSpan.endExclusive;
  const sideEmpty = sideSpan.start === sideSpan.endExclusive;
  if (baseEmpty && !sideEmpty) {
    return "inserted";
  }
  if (!baseEmpty && sideEmpty) {
    return "deleted";
  }
  return "modified";
}

interface RangeLike {
  startLineNumber: number;
  startColumn: number;
  endLineNumber: number;
  endColumn: number;
}

function toInnerRange(range: RangeLike): InnerRange {
  return {
    startLine: range.startLineNumber,
    startColumn: range.startColumn,
    endLine: range.endLineNumber,
    endColumn: range.endColumn,
  };
}
