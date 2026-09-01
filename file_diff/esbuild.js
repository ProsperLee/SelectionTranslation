/**
 * file_diff 前端打包：只产出浏览器可用的 webview + Monaco worker。
 * 不打包 VS Code extension host。
 *
 * 产出：
 *   dist/webview/main.js / main.css
 *   dist/webview/editor.worker.js
 *   dist/webview/ts.worker.js
 */
const esbuild = require("esbuild");
const path = require("path");

const production = process.argv.includes("--production");
const watch = process.argv.includes("--watch");

/** Monaco 内置的 DOMPurify 过旧，重定向到已打补丁的独立包。 */
const dompurifyRedirectPlugin = {
  name: "dompurify-redirect",
  setup(build) {
    const patched = path.resolve(
      __dirname,
      "node_modules/dompurify/dist/purify.es.mjs",
    );
    build.onResolve({ filter: /dompurify[\\/]dompurify\.js$/ }, () => ({
      path: patched,
    }));
  },
};

const loggerPlugin = {
  name: "build-logger",
  setup(build) {
    build.onStart(() => console.log("[file_diff] build started"));
    build.onEnd((result) => {
      for (const { text, location } of result.errors) {
        console.error(`✘ ${text}`);
        if (location) {
          console.error(`    ${location.file}:${location.line}:${location.column}`);
        }
      }
      console.log("[file_diff] build finished");
    });
  },
};

const base = {
  bundle: true,
  minify: production,
  sourcemap: !production,
  logLevel: "silent",
  plugins: [loggerPlugin, dompurifyRedirectPlugin],
};

async function main() {
  const webviewCtx = await esbuild.context({
    ...base,
    entryPoints: ["webview/main.ts"],
    outfile: "dist/webview/main.js",
    platform: "browser",
    format: "iife",
    loader: { ".ttf": "dataurl" },
  });

  const workerCtx = await esbuild.context({
    ...base,
    entryPoints: [
      "node_modules/monaco-editor/esm/vs/editor/editor.worker.js",
    ],
    outfile: "dist/webview/editor.worker.js",
    platform: "browser",
    format: "iife",
  });

  const tsWorkerCtx = await esbuild.context({
    ...base,
    entryPoints: [
      "node_modules/monaco-editor/esm/vs/language/typescript/ts.worker.js",
    ],
    outfile: "dist/webview/ts.worker.js",
    platform: "browser",
    format: "iife",
  });

  const contexts = [webviewCtx, workerCtx, tsWorkerCtx];
  if (watch) {
    await Promise.all(contexts.map((c) => c.watch()));
  } else {
    await Promise.all(contexts.map((c) => c.rebuild()));
    await Promise.all(contexts.map((c) => c.dispose()));
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
