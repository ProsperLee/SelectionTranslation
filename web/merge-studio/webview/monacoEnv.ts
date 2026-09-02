/**
 * Monaco web worker 配置。
 *
 * - editorWorkerService → editor.worker.js（diff / 基础编辑）
 * - javascript / typescript → ts.worker.js（避免 provideInlayHints 等落到 editor worker）
 * - 其余语言暂用 editor worker，并关掉会打到专用 worker 的校验
 */
import type * as monaco from "monaco-editor";

declare global {
  interface Window {
    __JBMERGE__?: {
      workerUri: string;
      tsWorkerUri?: string;
    };
    MonacoEnvironment?: monaco.Environment;
  }
}

function spawnWorker(workerUri: string): Worker {
  // file:// / 自定义 CSP 下不能直接跨源 new Worker(url)，用 blob + importScripts。
  const shim = `importScripts(${JSON.stringify(workerUri)});`;
  const blob = new Blob([shim], { type: "application/javascript" });
  return new Worker(URL.createObjectURL(blob));
}

export function configureMonacoWorkers(): void {
  const workerUri = window.__JBMERGE__?.workerUri;
  const tsWorkerUri = window.__JBMERGE__?.tsWorkerUri || workerUri;

  self.MonacoEnvironment = {
    getWorker(_workerId: string, label: string): Worker {
      if (!workerUri) {
        throw new Error("Monaco worker URI was not provided by the host.");
      }
      if (label === "typescript" || label === "javascript") {
        return spawnWorker(tsWorkerUri!);
      }
      return spawnWorker(workerUri);
    },
  };
}

/** 关掉不需要的语言服务，减少对专用 worker 的依赖与控制台噪音。 */
export function configureMonacoLanguageDefaults(
  monacoApi: typeof monaco,
): void {
  const tsOff = {
    noSemanticValidation: true,
    noSyntaxValidation: true,
    noSuggestionDiagnostics: true,
  };
  monacoApi.languages.typescript.javascriptDefaults.setDiagnosticsOptions(tsOff);
  monacoApi.languages.typescript.typescriptDefaults.setDiagnosticsOptions(tsOff);
  monacoApi.languages.typescript.javascriptDefaults.setInlayHintsOptions({
    includeInlayParameterNameHints: "none",
    includeInlayParameterNameHintsWhenArgumentMatchesName: false,
    includeInlayFunctionParameterTypeHints: false,
    includeInlayVariableTypeHints: false,
    includeInlayVariableTypeHintsWhenTypeMatchesName: false,
    includeInlayPropertyDeclarationTypeHints: false,
    includeInlayFunctionLikeReturnTypeHints: false,
    includeInlayEnumMemberValueHints: false,
  });
  monacoApi.languages.typescript.typescriptDefaults.setInlayHintsOptions({
    includeInlayParameterNameHints: "none",
    includeInlayParameterNameHintsWhenArgumentMatchesName: false,
    includeInlayFunctionParameterTypeHints: false,
    includeInlayVariableTypeHints: false,
    includeInlayVariableTypeHintsWhenTypeMatchesName: false,
    includeInlayPropertyDeclarationTypeHints: false,
    includeInlayFunctionLikeReturnTypeHints: false,
    includeInlayEnumMemberValueHints: false,
  });
  monacoApi.languages.json.jsonDefaults.setDiagnosticsOptions({
    validate: false,
    allowComments: true,
    schemaValidation: "ignore",
    comments: "ignore",
    trailingCommas: "ignore",
  });
}
