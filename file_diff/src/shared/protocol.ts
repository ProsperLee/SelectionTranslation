/**
 * 宿主（扩展或浏览器壳）与前端之间的消息协议。
 * 禁止 import vscode，以便打进浏览器 bundle。
 *
 * 浏览器壳通过 window.postMessage 发送：
 *   - { type: "init", ...MergeInitPayload }      → 三栏合并
 *   - { type: "diffInit", ...DiffInitPayload }   → 并排 Diff
 */

export type ConflictType =
  | "content" // 双方都改了，有公共祖先
  | "add-add" // 双方都新增，无公共祖先
  | "deleted-by-us"
  | "deleted-by-them"
  | "unknown";

export type VersionsSource =
  | "git-stages" // git index :1: / :2: / :3:
  | "markers" // 从冲突标记还原
  | "none"; // 本地上传等，无 git 上下文

/** 三栏合并初始化数据 */
export interface MergeInitPayload {
  fileName: string;
  conflictType: ConflictType;
  source: VersionsSource;
  /** 是否具备可用的公共祖先（base） */
  hasBase: boolean;
  oursLabel: string;
  theirsLabel: string;
  /** 公共祖先文本；本地双文件对比时为两侧公共行 */
  base: string;
  ours: string;
  theirs: string;
  /** 结果栏初始文本（通常与 base 相同，随后由用户接受左右变更） */
  result: string;
  jetbrainsName?: string;
}

/** 并排 Diff 初始化数据 */
export interface DiffInitPayload {
  leftLabel: string;
  rightLabel: string;
  leftText: string;
  rightText: string;
  /** 用于语言检测 / 标题 */
  fileName: string;
  /** 右侧是否可编辑，并将编辑同步回宿主 */
  rightEditable: boolean;
}

/** 宿主 → 前端 */
export type HostMessage =
  | ({ type: "init" } & MergeInitPayload)
  | { type: "applied"; staged: boolean }
  | ({ type: "diffInit" } & DiffInitPayload)
  | { type: "persistState"; state: unknown };

/** 前端 → 宿主 */
export type WebviewMessage =
  | { type: "ready" }
  | { type: "resultChanged"; text: string }
  | { type: "apply"; text: string; fileName?: string }
  | { type: "cancel" }
  | { type: "openInJetBrains" }
  | { type: "diffChanged"; text: string };
