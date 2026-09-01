/**
 * 浏览器壳启动脚本：在加载 Monaco 打包产物之前注入。
 * - 伪造 VS Code webview API（本项目不跑扩展宿主）
 * - 告知 Monaco worker 脚本地址（相对当前页面，兼容 file:// 与 http://）
 * - 可选转发到 Qt：window.__fileDiffPost（由宿主注入）
 */
(function () {
  globalThis.acquireVsCodeApi = function () {
    return {
      postMessage: function (message) {
        try {
          if (typeof window.__fileDiffPost === "function") {
            window.__fileDiffPost(
              typeof message === "string" ? message : JSON.stringify(message),
            );
          }
        } catch (e) {
          /* ignore */
        }
      },
      getState: function () {
        return undefined;
      },
      setState: function () {},
    };
  };
  var base = window.location.href;
  window.__JBMERGE__ = {
    workerUri: new URL("dist/webview/editor.worker.js", base).href,
    tsWorkerUri: new URL("dist/webview/ts.worker.js", base).href,
  };
})();
