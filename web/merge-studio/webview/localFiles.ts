/**
 * 本地文件选择，以及上传后组装合并 / Diff 的 payload。
 * 浏览器壳专用（不依赖 VS Code 扩展宿主）。
 */
import { commonLinesText } from "../src/engine/lineDiff";
import type { DiffInitPayload, MergeInitPayload } from "../src/shared/protocol";

const TEXT_ACCEPT =
  ".txt,.md,.json,.js,.jsx,.ts,.tsx,.css,.html,.htm,.xml,.yml,.yaml,.py,.java,.go,.rs,.c,.cpp,.h,.cs,.php,.rb,.sh,.sql,.toml,.ini,text/*";

type PickedTextFile = { name: string; text: string };

declare global {
  interface Window {
    /** Qt 宿主：默认从桌面打开，避免落到安装目录 */
    __fileDiffPickTextFile?: () => Promise<PickedTextFile | null>;
  }
}

/** 弹出系统文件选择框，读取为 UTF-8 文本。 */
export function pickTextFile(): Promise<PickedTextFile | null> {
  if (typeof window.__fileDiffPickTextFile === "function") {
    return window.__fileDiffPickTextFile();
  }
  return new Promise((resolve) => {
    const input = document.createElement("input");
    input.type = "file";
    input.accept = TEXT_ACCEPT;
    input.addEventListener("change", async () => {
      const file = input.files?.[0];
      if (!file) {
        resolve(null);
        return;
      }
      try {
        resolve({ name: file.name, text: await file.text() });
      } catch {
        resolve(null);
      }
    });
    input.click();
  });
}

/**
 * 一侧上传后：更新该侧文本，并以两侧「公共行」作为 base / 结果初始内容。
 * 这样中间栏只显示共有部分，左右独有行成为相对公共祖先的变更。
 */
export function mergePayloadAfterUpload(
  current: MergeInitPayload,
  side: "ours" | "theirs",
  file: { name: string; text: string },
): MergeInitPayload {
  const next: MergeInitPayload = {
    ...current,
    source: "none",
    fileName: file.name,
  };
  if (side === "ours") {
    next.ours = file.text;
    next.oursLabel = `本地 — ${file.name}`;
  } else {
    next.theirs = file.text;
    next.theirsLabel = `本地 — ${file.name}`;
  }
  const common = commonLinesText(next.ours, next.theirs);
  next.base = common;
  next.result = common;
  next.hasBase = true;
  next.conflictType = "content";
  return next;
}

/** Diff 页：更新左或右文本与栏目标题。 */
export function diffPayloadAfterUpload(
  current: DiffInitPayload,
  side: "left" | "right",
  file: { name: string; text: string },
): DiffInitPayload {
  const next: DiffInitPayload = { ...current, fileName: file.name };
  if (side === "left") {
    next.leftText = file.text;
    next.leftLabel = `本地 — ${file.name}`;
  } else {
    next.rightText = file.text;
    next.rightLabel = `本地 — ${file.name}`;
  }
  return next;
}

/** 从路径或「本地 — name.ext」标签取出扩展名（含点），无则返回空串。 */
export function fileExtension(nameOrLabel: string): string {
  const base =
    (nameOrLabel || "")
      .replace(/^本地\s*[—–-]\s*/, "")
      .split(/[\\/]/)
      .pop()
      ?.trim() || "";
  if (!base || base === "文件1" || base === "文件2") {
    return "";
  }
  const dot = base.lastIndexOf(".");
  if (dot <= 0 || dot === base.length - 1) {
    return "";
  }
  return base.slice(dot).toLowerCase();
}

/**
 * 保存默认名：未命名 + 两侧相同扩展名；两侧不同或都没有则 .txt。
 */
export function suggestedSaveFileName(
  leftNameOrLabel: string,
  rightNameOrLabel: string,
): string {
  const leftExt = fileExtension(leftNameOrLabel);
  const rightExt = fileExtension(rightNameOrLabel);
  if (leftExt && rightExt) {
    return leftExt === rightExt ? `未命名${leftExt}` : "未命名.txt";
  }
  if (leftExt) {
    return `未命名${leftExt}`;
  }
  if (rightExt) {
    return `未命名${rightExt}`;
  }
  return "未命名.txt";
}
