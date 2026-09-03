# SelectionTranslation

Windows 桌面效率工具：**划词翻译**、**OCR 翻译**、**屏幕吸色**、**桌面便签**、**文件对比**、**思维导图**。托盘常驻，翻译引擎免密钥，支持混合 DPI 多显示器。

当前版本：**1.3.1**（见 `packaging/version.txt`）

---

## 快速开始

### 安装包（推荐）

运行 `release\SelectionTranslation-Setup-1.3.1.exe`（需自行 [`打包`](#打包) 生成）。

- 默认安装到 `%LOCALAPPDATA%\SelectionTranslation`，无需管理员
- 升级安装保留已有 `settings_config.json`

### 源码运行

环境：**Windows 10+**、**Python 3.10+**

```powershell
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt

# 思维导图前端（首次，需可访问 GitHub）
.\web\drawnix\setup.ps1

# 启动（无控制台）
.venv\Scripts\pythonw.exe main.py

# 调试
python main.py
```

- **双击**托盘图标 → 打开设置
- `python main.py --settings` → 仅打开设置页
- 同时只能运行一个实例

---

## 功能概览

- 💯 免费 + 开源
- ⌨️ 全局热键
- 📝 划词翻译
- 💬 划词浮动按钮
- 📷 OCR 翻译
- 🎨 屏幕吸色
- 📌 桌面便签
- 📂 文件对比
- ⚒️ 思维导图 / 白板
- 🔔 托盘常驻
- 🖥️ 多显示器适配

### 默认快捷键

可在设置页修改；各热键不可重复。

| 操作 | 默认热键 |
| --- | --- |
| 划词翻译 | `Ctrl+Alt+T` |
| OCR 翻译 | `Ctrl+Alt+O` |
| 屏幕吸色 | `Ctrl+Alt+I` |
| 新建便签 | `Ctrl+Alt+N` |

### 托盘菜单

| 菜单项 | 说明 |
| --- | --- |
| 打开设置 | 快捷键、划词按钮、开机自启等 |
| 文件对比 | 本地双文件三栏合并 / 并排 Diff |
| 思维导图 | Drawnix 白板 / 思维导图 |
| 显示全部便签 | 显示已隐藏的便签 |
| 查看日志 | 本次启动以来的彩色运行日志 |
| 重新注册快捷键 | 休眠 / 锁屏后热键失效时手动恢复 |
| 关于 | 版本与作者信息 |
| 退出 | 关闭应用 |

---

## 使用说明

- **划词翻译** — 选中文字后翻译，支持多引擎与词典释义
- **OCR 翻译** — 框选屏幕区域，识别文字并翻译
- **屏幕吸色** — 全屏取色，复制 HEX / RGBA 色值
- **桌面便签** — 多窗口便签，内容本地保存
- **文件对比** — 本地双文件三栏合并或并排 Diff
- **思维导图** — Drawnix 白板，思维导图 / 流程图 / 自由画
- **朗读** — 翻译结果在线或系统语音朗读

---

## 配置与数据

| 文件 | 说明 |
| --- | --- |
| `settings_config.json` | 运行时配置（设置页写入；与 exe 同目录，不可写时落到 `%LOCALAPPDATA%\SelectionTranslation`） |
| `sticky_notes.json` | 便签数据 |
| `settings_config.example.json` | 配置示例 |

| 字段 | 说明 |
| --- | --- |
| `hotkey` / `ocr_hotkey` / `color_picker_hotkey` / `sticky_note_hotkey` | 四项全局热键 |
| `selection_bubble` | 选中文字后显示浮动翻译按钮 |
| `start_on_boot` | 开机自启 |
| `engine` / `source_lang` / `target_lang` | 默认翻译选项 |
| `window_pinned` | 结果窗口置顶 |
| `translation_*` / `ocr_*` / `split_ratio` | 窗口尺寸与分栏比例 |

---

## 项目结构

```
SelectionTranslation/
├── main.py                       # 入口（DPI / 单实例 / 隐藏子进程控制台）
├── app.py                        # 托盘、热键、功能调度
├── boot.py                       # 开机自启
├── config.py                     # 配置读写
├── hotkeys.py                    # Win32 全局热键
├── selection.py                  # 选区捕获
├── selection_bubble_watcher.py   # 划词浮动按钮
├── translator.py / translate_task.py   # 翻译引擎
├── ocr.py / ocr_task.py          # OCR 识别
├── screenshot_selector.py        # 框选截图
├── color_picker.py               # 屏幕吸色
├── sticky_notes_store.py         # 便签持久化
├── tts.py                        # 朗读
├── app_log.py                    # 内存日志
├── win_subprocess.py             # 抑制子进程黑框
├── single_instance.py            # 防重复启动
│
├── ui/                           # Qt 界面
│   ├── settings_window.py        # 设置页
│   ├── translation_workspace.py  # 划词 / OCR 翻译窗口
│   ├── translation_panel.py      # 翻译面板
│   ├── ocr_window.py             # OCR 窗口
│   ├── sticky_note_window.py     # 桌面便签
│   ├── file_diff_window.py       # 文件对比（WebEngine）
│   ├── drawnix_window.py         # 思维导图（WebEngine）
│   ├── log_window.py             # 运行日志
│   └── …
│
├── web/
│   ├── merge-studio/             # 文件对比前端（Monaco）
│   └── drawnix/                  # 思维导图前端（Drawnix）
│
├── icons/                        # SVG 图标
├── packaging/                    # PyInstaller + Inno Setup 打包
│   ├── build.ps1
│   ├── SelectionTranslation.spec
│   ├── installer.iss
│   └── version.txt
│
└── release/                      # 打包产出（git 忽略）
    ├── app/SelectionTranslation/
    └── SelectionTranslation-Setup-1.3.1.exe
```

---

## 打包

终端会持续输出进度。版本号来自 `packaging/version.txt`。

```cmd
powershell -NoProfile -ExecutionPolicy Bypass -File ".\packaging\build.ps1"
```

```powershell
# 一次性：Inno Setup 6（生成 Setup.exe，可选）
winget install --id JRSoftware.InnoSetup -e

# 完整打包（含 merge-studio / drawnix 前端构建 + 安装包）
.\packaging\build.ps1

# 指定版本
.\packaging\build.ps1 -Version 1.3.1

# 仅生成可运行目录，不编译安装包
.\packaging\build.ps1 -SkipInstaller

# 清理后全量重打
.\packaging\build.ps1 -Clean
```

| 产出 | 说明 |
| --- | --- |
| `release\app\SelectionTranslation\SelectionTranslation.exe` | 免安装目录 |
| `release\SelectionTranslation-Setup-1.3.1.exe` | 安装包 |

安装包特性：默认 `%LOCALAPPDATA%\SelectionTranslation`、可选桌面快捷方式与开机自启；**首次安装**写入默认配置，升级不覆盖用户配置。

更多细节见 [`packaging/README.md`](packaging/README.md)。

---

## 其他说明

- **翻译引擎**：「自动选择」依次尝试必应、有道、搜狗等；短词附加有道词典释义
- **热键**：基于 Win32 `RegisterHotKey`，解锁 / 唤醒后自动重注册，并有 watchdog 兜底
- **日志**：托盘「查看日志」；超过 6 小时或 3000 条自动清理
- **OCR**：依赖 `rapidocr-onnxruntime`，打包时一并打入
- **多显示器**：混合 DPI；吸色与 OCR 框选支持跨屏坐标
