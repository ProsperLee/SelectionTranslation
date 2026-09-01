/**
 * 前端入口（浏览器 / webview）。
 *
 * 首条宿主消息分流：
 *   init     → 三栏 MergeView
 *   diffInit → 双栏 DiffView
 *
 * 本地上传逻辑见 localFiles.ts；UI 文案为中文。
 */

import "./styles/diff.css";
import {
  configureMonacoLanguageDefaults,
  configureMonacoWorkers,
} from "./monacoEnv";
import * as monaco from "monaco-editor";
import { vscodeApi } from "./vscodeApi";
import { MergeView, type MergeCountsView } from "./mergeView";
import { DiffView } from "./diffView";
import type {
  DiffInitPayload,
  HostMessage,
  MergeInitPayload,
} from "../src/shared/protocol";
import type { WhitespaceMode } from "../src/engine/lineDiff";
import {
  diffPayloadAfterUpload,
  mergePayloadAfterUpload,
  pickTextFile,
} from "./localFiles";
import {
  arrowDown,
  arrowUp,
  chevronDoubleLeft,
  chevronDoubleRight,
  chevronsInward,
  historyIcon,
  iconElement,
  magicWand,
  openExternal,
  redoIcon,
  resetIcon,
  syncScroll,
  undoIcon,
} from "./icons";

configureMonacoWorkers();
configureMonacoLanguageDefaults(monaco);

const root = document.getElementById("root");
if (root) {
  start(root);
}

function start(root: HTMLElement): void {
  let started = false;

  const onFirst = (event: MessageEvent) => {
    const message = event.data as HostMessage;
    if (started) {
      return;
    }
    if (message?.type === "init") {
      started = true;
      window.removeEventListener("message", onFirst);
      startMerge(root, message);
    } else if (message?.type === "diffInit") {
      started = true;
      window.removeEventListener("message", onFirst);
      startDiff(root, message);
    }
  };
  window.addEventListener("message", onFirst);

  // 通知宿主（或空 shim）webview 已就绪
  vscodeApi.postMessage({ type: "ready" });
}

// --- shared toolbar helpers ---

function button(label: string, variant: "" | "primary" | "bordered" = ""): HTMLButtonElement {
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "jb-toolbar-btn";
  if (variant === "primary") {
    btn.classList.add("jb-primary");
  } else if (variant === "bordered") {
    btn.classList.add("jb-bordered");
  }
  btn.textContent = label;
  return btn;
}

function iconButton(svg: string, title: string): HTMLButtonElement {
  const btn = button("");
  btn.classList.add("jb-icon");
  btn.title = title;
  btn.appendChild(iconElement(svg));
  return btn;
}

/** A compact icon+text action, like IntelliJ's "≫ Left / ≪≫ All / ≪ Right". */
function iconTextButton(svg: string, label: string, title: string): HTMLButtonElement {
  const btn = button("");
  btn.title = title;
  btn.appendChild(iconElement(svg));
  btn.appendChild(document.createTextNode(label));
  return btn;
}

function toolbarLabel(text: string): HTMLElement {
  const span = document.createElement("span");
  span.className = "jb-toolbar-label";
  span.textContent = text;
  return span;
}

function separator(): HTMLElement {
  const sep = document.createElement("span");
  sep.className = "jb-sep";
  return sep;
}

function whitespaceSelect(onChange: (mode: WhitespaceMode) => void): HTMLSelectElement {
  const select = document.createElement("select");
  select.className = "jb-toolbar-select";
  select.title = "空白处理";
  const options: Array<[WhitespaceMode, string]> = [
    ["none", "不忽略空白"],
    ["trailing", "忽略行尾空白"],
    ["all", "忽略所有空白"],
  ];
  for (const [value, text] of options) {
    const opt = document.createElement("option");
    opt.value = value;
    opt.textContent = text;
    select.appendChild(opt);
  }
  select.addEventListener("change", () =>
    onChange(select.value as WhitespaceMode),
  );
  return select;
}

function granularityToggle(onChange: (showWords: boolean) => void): HTMLSelectElement {
  const select = document.createElement("select");
  select.className = "jb-toolbar-select";
  select.title = "高亮粒度";
  for (const [value, text] of [
    ["words", "按词高亮"],
    ["lines", "按行高亮"],
  ]) {
    const opt = document.createElement("option");
    opt.value = value;
    opt.textContent = text;
    select.appendChild(opt);
  }
  select.addEventListener("change", () => onChange(select.value === "words"));
  return select;
}

function note(): HTMLElement {
  const span = document.createElement("span");
  span.className = "jb-note";
  span.hidden = true;
  return span;
}

// --- 3-way merge mode ---

function startMerge(root: HTMLElement, first: MergeInitPayload & { type: "init" }): void {
  const app = document.createElement("div");
  app.className = "jb-app";

  // Top toolbar, laid out like the IntelliJ merge window header.
  const toolbar = document.createElement("div");
  toolbar.className = "jb-toolbar";

  const isMac = navigator.platform.toUpperCase().includes("MAC");
  const undoBtn = iconButton(undoIcon, `撤销 (${isMac ? "⌘Z" : "Ctrl+Z"})`);
  const redoBtn = iconButton(
    redoIcon,
    `重做 (${isMac ? "⇧⌘Z" : "Ctrl+Shift+Z"})`,
  );
  undoBtn.disabled = true;
  redoBtn.disabled = true;

  // History dropdown: every merge action this session, newest first.
  const historyWrap = document.createElement("span");
  historyWrap.className = "jb-history-wrap";
  const historyBtn = iconButton(historyIcon, "操作历史");
  historyBtn.disabled = true;
  const historyPop = document.createElement("div");
  historyPop.className = "jb-history-pop";
  historyPop.hidden = true;
  historyWrap.append(historyBtn, historyPop);

  const prevBtn = iconButton(arrowUp, "上一处变更 (Shift+F7)");
  const nextBtn = iconButton(arrowDown, "下一处变更 (F7)");

  const applyLeftBtn = iconTextButton(
    chevronDoubleRight,
    "左侧",
    "应用左侧非冲突变更",
  );
  const applyAllBtn = iconTextButton(
    chevronsInward,
    "全部",
    "应用全部非冲突变更",
  );
  const applyRightBtn = iconTextButton(
    chevronDoubleLeft,
    "右侧",
    "应用右侧非冲突变更",
  );
  const magicBtn = iconButton(
    magicWand,
    "解决简单冲突（两侧改动相同）",
  );
  magicBtn.disabled = true;

  const wsSelect = whitespaceSelect((mode) =>
    view.setRenderOptions({ whitespace: mode }),
  );
  const granSelect = granularityToggle((showWords) =>
    view.setRenderOptions({ showInner: showWords }),
  );

  const syncBtn = iconButton(syncScroll, "同步滚动");
  syncBtn.classList.add("jb-toggled");
  const resetBtn = iconButton(resetIcon, "重置为初始合并状态");

  const largeNote = note();

  const spacer = document.createElement("span");
  spacer.className = "jb-spacer";

  const counter = document.createElement("span");
  counter.className = "jb-counter";
  counter.textContent = "加载中…";

  toolbar.append(
    undoBtn,
    redoBtn,
    historyWrap,
    separator(),
    prevBtn,
    nextBtn,
    separator(),
    toolbarLabel("应用非冲突变更："),
    applyLeftBtn,
    applyAllBtn,
    applyRightBtn,
    magicBtn,
    separator(),
    wsSelect,
    granSelect,
    separator(),
    syncBtn,
    resetBtn,
    largeNote,
    spacer,
    counter,
  );

  const content = document.createElement("div");
  content.className = "jb-merge-content";

  // Bottom bar, like the IntelliJ dialog footer.
  const bottomBar = document.createElement("div");
  bottomBar.className = "jb-bottom-bar";

  const acceptLeftBtn = button("采用左侧", "bordered");
  acceptLeftBtn.title = "用左侧版本解决全部冲突";
  const acceptRightBtn = button("采用右侧", "bordered");
  acceptRightBtn.title = "用右侧版本解决全部冲突";

  const bottomSpacer = document.createElement("span");
  bottomSpacer.className = "jb-spacer";

  const cancelBtn = button("取消", "bordered");
  cancelBtn.title = "关闭";
  const applyBtn = button("应用", "primary");
  applyBtn.title = "保存中间结果到本地";

  bottomBar.append(acceptLeftBtn, acceptRightBtn, bottomSpacer);

  // Escape hatch to the real IDE merge window; only offered when one exists.
  // Tucked away right of the spacer, with a gap before Cancel/Apply so it
  // can't be hit when aiming at the resolution buttons.
  if (first.jetbrainsName) {
    const jetbrainsBtn = button(`在 ${first.jetbrainsName} 中打开`);
    jetbrainsBtn.classList.add("jb-external");
    jetbrainsBtn.prepend(iconElement(openExternal));
    jetbrainsBtn.title =
      `关闭此编辑器，改用 ${first.jetbrainsName} 合并窗口解决冲突`;
    jetbrainsBtn.addEventListener("click", () => {
      vscodeApi.postMessage({ type: "openInJetBrains" });
    });
    bottomBar.append(jetbrainsBtn);
  }

  bottomBar.append(cancelBtn, applyBtn);

  app.append(toolbar, content, bottomBar);
  root.replaceChildren(app);

  const view = new MergeView(content);
  let currentPayload: MergeInitPayload = { ...first };
  delete (currentPayload as { type?: string }).type;

  view.onSideUpload = async (side) => {
    const picked = await pickTextFile();
    if (!picked) {
      return;
    }
    currentPayload = mergePayloadAfterUpload(currentPayload, side, picked);
    view.render(currentPayload);
  };

  let counts: MergeCountsView = { total: 0, pending: 0, conflictsPending: 0 };
  view.onCountsChanged = (next) => {
    counts = next;
    updateMergeToolbar(counter, counts);
    magicBtn.disabled = !view.hasSimpleConflicts();
    // Resolution buttons deactivate once they have nothing left to do (and
    // re-activate on undo/reset, since this fires on every state change).
    const nothingPending = counts.pending === 0;
    acceptLeftBtn.disabled = nothingPending;
    acceptRightBtn.disabled = nothingPending;
    // Pending work again (undo, reset, re-diff) revokes the green
    // confirmation; it is granted in the Accept click handlers, which run
    // after the (synchronous) bulk accept settles the counts.
    if (!nothingPending) {
      acceptLeftBtn.classList.remove("jb-confirmed");
      acceptRightBtn.classList.remove("jb-confirmed");
    }
    const nonConflictingPending = counts.pending - counts.conflictsPending;
    applyLeftBtn.disabled = nonConflictingPending === 0;
    applyAllBtn.disabled = nonConflictingPending === 0;
    applyRightBtn.disabled = nonConflictingPending === 0;
    // Any new resolution activity (including Reset) re-arms Apply after a
    // completed merge and clears a pending two-step confirmation.
    applyBtn.disabled = false;
    disarmApply();
  };

  view.onLargeFile = (large) => {
    largeNote.hidden = !large;
    largeNote.textContent = large
      ? "大文件：已关闭词级高亮"
      : "";
  };

  let syncTimer = 0;
  view.onResultChanged = () => {
    if (syncTimer) {
      window.clearTimeout(syncTimer);
    }
    syncTimer = window.setTimeout(() => {
      syncTimer = 0;
      vscodeApi.postMessage({ type: "resultChanged", text: view.getResultText() });
    }, 250);
  };

  undoBtn.addEventListener("click", () => view.undo());
  redoBtn.addEventListener("click", () => view.redo());

  const refreshHistoryUi = () => {
    undoBtn.disabled = !view.canUndo();
    redoBtn.disabled = !view.canRedo();
    const history = view.getHistory();
    historyBtn.disabled =
      history.undo.length === 0 && history.redo.length === 0;
    if (!historyPop.hidden) {
      renderHistoryPop();
    }
  };
  view.onHistoryChanged = refreshHistoryUi;

  function renderHistoryPop(): void {
    const history = view.getHistory();
    historyPop.replaceChildren();
    if (history.undo.length === 0 && history.redo.length === 0) {
      const empty = document.createElement("div");
      empty.className = "jb-history-empty";
      empty.textContent = "暂无操作记录";
      historyPop.appendChild(empty);
      return;
    }
    // Undone actions on top (dim, clickable to re-apply), next redo first.
    for (let i = history.redo.length - 1; i >= 0; i--) {
      const steps = history.redo.length - i;
      const item = document.createElement("div");
      item.className = "jb-history-item jb-history-redo";
      item.textContent = history.redo[i];
      item.title = "已撤销 — 点击重做到此处";
      item.addEventListener("click", () => {
        for (let n = 0; n < steps; n++) {
          view.redo();
        }
        historyPop.hidden = true;
      });
      historyPop.appendChild(item);
    }
    // Applied actions, newest first; clicking one undoes it and what followed.
    for (let i = history.undo.length - 1; i >= 0; i--) {
      const index = i;
      const item = document.createElement("div");
      item.className = "jb-history-item";
      item.textContent = history.undo[i];
      item.title = "点击撤销到此操作之前";
      item.addEventListener("click", () => {
        view.undoTo(index);
        historyPop.hidden = true;
      });
      historyPop.appendChild(item);
    }
  }

  historyBtn.addEventListener("click", (event) => {
    event.stopPropagation();
    historyPop.hidden = !historyPop.hidden;
    if (!historyPop.hidden) {
      const rect = historyBtn.getBoundingClientRect();
      historyPop.style.top = `${rect.bottom + 4}px`;
      historyPop.style.left = `${rect.left}px`;
      renderHistoryPop();
    }
  });
  document.addEventListener("click", (event) => {
    if (!historyPop.hidden && !historyWrap.contains(event.target as Node)) {
      historyPop.hidden = true;
    }
  });

  // Cmd+Z (mac) / Ctrl+Z (win/linux) outside the editors (toolbar focus
  // etc.). Inside Monaco the editor-level commands in MergeView handle the
  // same keys — KeyMod.CtrlCmd resolves to ⌘ on mac automatically.
  window.addEventListener("keydown", (event) => {
    const mod = isMac ? event.metaKey : event.ctrlKey;
    if (!mod || event.altKey) {
      return;
    }
    const target = event.target as HTMLElement | null;
    if (target?.closest?.(".monaco-editor")) {
      return;
    }
    const key = event.key.toLowerCase();
    if (key === "z") {
      event.preventDefault();
      if (event.shiftKey) {
        view.redo();
      } else {
        view.undo();
      }
    } else if (key === "y") {
      event.preventDefault();
      view.redo();
    }
  });

  prevBtn.addEventListener("click", () => view.goToPrevChange());
  nextBtn.addEventListener("click", () => view.goToNextChange());
  applyLeftBtn.addEventListener("click", () => view.applyNonConflictingSide("left"));
  applyAllBtn.addEventListener("click", () => view.applyAllNonConflicting());
  applyRightBtn.addEventListener("click", () => view.applyNonConflictingSide("right"));
  magicBtn.addEventListener("click", () => view.resolveSimpleConflicts());
  acceptLeftBtn.addEventListener("click", () => {
    view.acceptAllLeft();
    acceptLeftBtn.classList.toggle("jb-confirmed", counts.pending === 0);
  });
  acceptRightBtn.addEventListener("click", () => {
    view.acceptAllRight();
    acceptRightBtn.classList.toggle("jb-confirmed", counts.pending === 0);
  });

  syncBtn.addEventListener("click", () => {
    const enabled = !view.getSyncScroll();
    view.setSyncScroll(enabled);
    syncBtn.classList.toggle("jb-toggled", enabled);
  });
  resetBtn.addEventListener("click", () => view.reset());

  cancelBtn.addEventListener("click", () => {
    vscodeApi.postMessage({ type: "cancel" });
  });

  // 直接保存中间「结果」栏内容到本地（与并排 Diff 保存右侧一致）
  applyBtn.addEventListener("click", () => {
    if (applyBtn.disabled) {
      return;
    }
    const text = view.getResultText();
    const fileName =
      (currentPayload.fileName || "").split(/[\\/]/).pop() || "result.txt";
    vscodeApi.postMessage({ type: "apply", text, fileName });
    if (typeof (window as unknown as { __fileDiffPost?: unknown }).__fileDiffPost !== "function") {
      const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = fileName;
      a.click();
      URL.revokeObjectURL(a.href);
      counter.textContent = "已应用 ✓";
      counter.classList.add("jb-done");
      applyBtn.disabled = true;
    }
  });

  window.addEventListener("message", (event: MessageEvent) => {
    const message = event.data as HostMessage;
    if (message?.type === "init") {
      currentPayload = message;
      applyBtn.disabled = false;
      view.render(message);
    } else if (message?.type === "applied") {
      counter.textContent = message.staged
        ? "已应用并暂存 ✓"
        : "已应用 ✓";
      counter.classList.add("jb-done");
      applyBtn.disabled = true;
    }
  });

  view.render(first);
}

function updateMergeToolbar(counter: HTMLElement, counts: MergeCountsView): void {
  if (counts.total === 0) {
    counter.classList.remove("jb-done");
    counter.textContent = "无变更";
  } else if (counts.pending === 0) {
    counter.textContent = "全部变更已处理";
    counter.classList.add("jb-done");
  } else {
    counter.classList.remove("jb-done");
    const changes = `${counts.pending} 处变更`;
    const conflicts = counts.conflictsPending
      ? `，其中 ${counts.conflictsPending} 处冲突`
      : "";
    counter.textContent = `${changes}${conflicts}`;
  }
}

// --- 2-way diff mode ---

function startDiff(root: HTMLElement, first: DiffInitPayload & { type: "diffInit" }): void {
  const app = document.createElement("div");
  app.className = "jb-app";

  const toolbar = document.createElement("div");
  toolbar.className = "jb-toolbar";

  const prevBtn = iconButton(arrowUp, "上一处变更 (Shift+F7)");
  const nextBtn = iconButton(arrowDown, "下一处变更 (F7)");

  const wsSelect = whitespaceSelect((mode) =>
    view.setRenderOptions({ whitespace: mode }),
  );
  const granSelect = granularityToggle((showWords) =>
    view.setRenderOptions({ showInner: showWords }),
  );

  const largeNote = note();
  const spacer = document.createElement("span");
  spacer.className = "jb-spacer";

  const status = document.createElement("span");
  status.className = "jb-counter";
  status.textContent = "加载中…";

  const label = document.createElement("span");
  label.className = "jb-toolbar-label";
  label.textContent = "对比";

  const refreshDiffTitle = () => {
    const strip = (s: string) => s.replace(/^本地\s*[—–-]\s*/, "").trim();
    const left = strip(currentPayload.leftLabel || "");
    const right = strip(currentPayload.rightLabel || "");
    const leftNamed = left && left !== "文件1";
    const rightNamed = right && right !== "文件2";
    if (leftNamed || rightNamed) {
      label.textContent = `${leftNamed ? left : "文件1"} · ${rightNamed ? right : "文件2"}`;
      return;
    }
    const name = (currentPayload.fileName || "").trim();
    label.textContent = name ? name.split(/[\\/]/).pop()! : "对比";
  };

  toolbar.append(
    prevBtn,
    nextBtn,
    separator(),
    wsSelect,
    granSelect,
    largeNote,
    spacer,
    status,
    separator(),
    label,
  );

  const content = document.createElement("div");
  content.className = "jb-merge-content";

  const bottomBar = document.createElement("div");
  bottomBar.className = "jb-bottom-bar";
  const bottomSpacer = document.createElement("span");
  bottomSpacer.className = "jb-spacer";
  const cancelBtn = button("取消", "bordered");
  cancelBtn.title = "关闭";
  const applyBtn = button("应用", "primary");
  applyBtn.title = "保存右侧结果到本地";
  bottomBar.append(bottomSpacer, cancelBtn, applyBtn);

  app.append(toolbar, content, bottomBar);
  root.replaceChildren(app);

  const view = new DiffView(content);
  let currentPayload: DiffInitPayload = { ...first };
  delete (currentPayload as { type?: string }).type;

  view.onSideUpload = async (side) => {
    const picked = await pickTextFile();
    if (!picked) {
      return;
    }
    currentPayload = diffPayloadAfterUpload(currentPayload, side, picked);
    refreshDiffTitle();
    view.render(currentPayload);
  };

  view.onLargeFile = (large) => {
    largeNote.hidden = !large;
    largeNote.textContent = large
      ? "大文件：已关闭词级高亮"
      : "";
  };

  view.onCountsChanged = (changes) => {
    if (changes === 0) {
      status.textContent = "内容完全相同";
      status.classList.add("jb-done");
    } else {
      status.textContent = `${changes} 处差异`;
      status.classList.remove("jb-done");
    }
    prevBtn.disabled = changes === 0;
    nextBtn.disabled = changes === 0;
  };

  let syncTimer = 0;
  view.onRightChanged = () => {
    if (syncTimer) {
      window.clearTimeout(syncTimer);
    }
    syncTimer = window.setTimeout(() => {
      syncTimer = 0;
      vscodeApi.postMessage({ type: "diffChanged", text: view.getRightText() });
    }, 250);
  };

  prevBtn.addEventListener("click", () => view.goToPrevChange());
  nextBtn.addEventListener("click", () => view.goToNextChange());

  cancelBtn.addEventListener("click", () => {
    vscodeApi.postMessage({ type: "cancel" });
  });

  applyBtn.addEventListener("click", () => {
    if (applyBtn.disabled) {
      return;
    }
    const text = view.getRightText();
    const fileName =
      (currentPayload.fileName || "").split(/[\\/]/).pop() || "result.txt";
    vscodeApi.postMessage({ type: "apply", text, fileName });
    // 浏览器预览：无 Qt 宿主时直接下载
    if (typeof (window as unknown as { __fileDiffPost?: unknown }).__fileDiffPost !== "function") {
      const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = fileName;
      a.click();
      URL.revokeObjectURL(a.href);
      status.textContent = "已应用 ✓";
      status.classList.add("jb-done");
      applyBtn.disabled = true;
    }
  });

  const handle = (message: HostMessage) => {
    if (message?.type === "diffInit") {
      currentPayload = message;
      refreshDiffTitle();
      applyBtn.disabled = false;
      view.render(message);
    } else if (message?.type === "applied") {
      status.textContent = message.staged ? "已应用并暂存 ✓" : "已应用 ✓";
      status.classList.add("jb-done");
      applyBtn.disabled = true;
    } else if (message?.type === "persistState") {
      // Persist so the panel can be reconstructed after a window reload.
      vscodeApi.setState(message.state);
    }
  };

  window.addEventListener("message", (event: MessageEvent) =>
    handle(event.data as HostMessage),
  );

  handle(first);
}
