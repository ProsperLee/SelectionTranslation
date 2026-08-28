# SelectionTranslation

Windows 桌面划词 / OCR 翻译工具：全局热键捕获选中文本翻译，或框选屏幕区域 OCR 后翻译。国内免密钥引擎（必应 / 有道 / 搜狗 / 阿里 / 金山词霸），托盘常驻，支持划词浮动按钮。

## 功能

| 功能 | 划词翻译 | OCR |
| --- | :---: | :---: |
| 全局热键 | ✅ | ✅ |
| 划词浮动按钮（可开关） | ✅ | — |
| 源 / 目标语言、交换、引擎切换 | ✅ | ✅ |
| 词典增强（短词有道释义） | ✅ | ✅ |
| 复制原文 / 复制核心译文 | ✅ | ✅ |
| 窗口置顶、拖动、缩放、布局记忆 | ✅ | ✅ |
| 框选截图、预览、保存 | — | ✅ |
| 开机自启 / 单实例 | ✅ | ✅ |

## 安装

```bash
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

## 启动

```bash
# 推荐：无控制台窗口
.venv\Scripts\pythonw.exe main.py

# 或调试
python main.py
```

- 托盘常驻，双击托盘图标打开设置
- 仅打开设置：`python main.py --settings`
- 同时只能运行一个主程序实例

## 配置

运行时配置：`settings_config.json`（由设置页写入）  
示例：`settings_config.example.json`

| 字段 | 说明 |
| --- | --- |
| `hotkey` / `ocr_hotkey` | 全局热键 |
| `selection_bubble` | 选中文字后显示翻译浮动按钮 |
| `start_on_boot` | 开机自启（当前用户注册表 Run 键） |
| `engine` / `source_lang` / `target_lang` | 默认翻译选项（翻译窗口内修改会自动保存） |
| `window_pinned` | 结果窗口是否置顶 |
| `translation_*` / `ocr_*` / `split_ratio` | 窗口尺寸与分栏比例 |

## 目录结构

```
SelectionTranslation/
├── main.py                       # 入口（DPI / 单实例）
├── app.py                        # 托盘、热键、流程调度
├── boot.py                       # 开机自启
├── config.py                     # 配置读写
├── single_instance.py            # 防重复启动
├── hotkeys.py                    # 全局热键
├── app_log.py                    # 内存日志缓冲
├── selection.py                  # 选区捕获（UIA + WM_COPY）
├── selection_bubble_watcher.py   # 划词浮动按钮
├── selection_task.py             # 异步抓取选区
├── translator.py                 # 翻译引擎 + 词典
├── translate_task.py             # 异步翻译
├── ocr.py / ocr_task.py          # OCR 识别
├── screenshot_selector.py        # 框选截图
├── packaging/                    # 打包脚本（PyInstaller + Inno Setup）
├── icons/                        # SVG 图标
└── ui/                           # 界面
    ├── translation_workspace.py  # 划词 / OCR 共用窗口
    ├── translation_panel.py      # 翻译面板
    ├── screenshot_panel.py       # OCR 截图区
    ├── selection_bubble.py       # 浮动按钮控件
    ├── log_window.py             # 运行日志查看
    ├── screen_coords.py          # 多屏 DPI 坐标
    └── settings_window.py        # 设置页
```

## 打包成安装包（Windows）

终端会持续输出进度日志。

```powershell
# 一次性：安装 Inno Setup 6（用于生成 Setup.exe，可选）
winget install --id JRSoftware.InnoSetup -e

# 打包（生成 exe 目录；若已装 Inno 则继续生成安装包）
.\packaging\build.ps1

# 仅生成可运行目录，不编译安装包
.\packaging\build.ps1 -SkipInstaller

# 清理后全量重打
.\packaging\build.ps1 -Clean
```

产出：

| 路径 | 说明 |
| --- | --- |
| `release\app\SelectionTranslation\SelectionTranslation.exe` | 免安装可运行目录 |
| `release\SelectionTranslation-Setup-1.0.0.exe` | 安装包（需 Inno Setup） |

安装包特性：

- 可自选安装目录（默认 `%LOCALAPPDATA%\SelectionTranslation`，显示名仍为「划词翻译」，无需管理员）
- 可选「开机自启」（写入与应用内一致的 `HKCU\...\Run\SelectionTranslation`，并同步 `settings_config.json`）
- 可选桌面快捷方式；卸载时清理自启项

## 说明

- **划词**优先 UIA，其次经典编辑框 API，最后 `WM_COPY`（**不注入 Ctrl+C**，避免打断终端）
- **划词按钮**同样走上述路径；部分 Electron 应用依赖其是否响应 `WM_COPY`
- **托盘右键「查看日志」**可查看本次启动以来的彩色运行日志（含划词/OCR 原文）；超过 6 小时或 3000 条会自动清理
- **OCR** 需 `rapidocr-onnxruntime`（打包时会一并打入）
- **多显示器**已适配混合 DPI
