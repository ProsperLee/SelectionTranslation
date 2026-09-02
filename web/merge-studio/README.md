# merge-studio

浏览器里跑的本地文件对比工具：三栏合并 + 并排 Diff。  
源自 [Merge Studio](https://github.com/GitStudioHQ/merge-studio) 的 webview / engine，已中文化并支持左右上传。

主应用托盘右键「文件对比」也会打开同一套界面（Qt WebEngine 嵌入）。

## 启动（浏览器预览）

```powershell
cd web/merge-studio
npm install
npm start
```

| 页面 | 地址 |
| --- | --- |
| 三栏合并 | http://localhost:5173/ |
| 并排 Diff | http://localhost:5173/diff.html |

开发时另开终端：`npm run watch`，再 `npx serve -l 5173 .`。

打包主程序前请先执行 `npm run build`，确保 `dist/` 存在。

## 用法

1. 左右栏标题右侧上传图标，分别选择本地文件  
2. 中间「结果」初始为两侧**公共行**（按行 LCS）  
3. 用 ≫ / ≪ / ✕ 或底栏按钮处理差异后「应用」

## 目录

```
web/merge-studio/
├── index.html / diff.html   # 页面入口（空状态，无默认示例）
├── public/                  # harness 共用 CSS / 启动 shim
├── webview/                 # Monaco UI：工具栏、色带、上传
├── src/engine/              # 纯逻辑：行 diff、三方合并模型
├── src/shared/              # 宿主 ↔ 前端消息协议
└── esbuild.js               # 仅打包 webview + Monaco worker
```
