# SelectionTranslation

Windows 桌面划词 / OCR 翻译工具，附带屏幕吸色与便签。托盘常驻，国内免密钥翻译引擎。

## 功能

| 功能 | 划词翻译 | OCR | 吸色 | 便签 | 文件对比 |
| --- | :---: | :---: | :---: | :---: | :---: |
| 全局热键 | ✅ | ✅ | ✅ | ✅ | — |
| 划词浮动按钮 | ✅ | — | — | — | — |
| 多引擎翻译 / 语言切换 | ✅ | ✅ | — | — | — |
| 词典释义 | ✅ | ✅ | — | — | — |
| 复制 / 朗读 | ✅ | ✅ | — | — | — |
| 窗口置顶与布局记忆 | ✅ | ✅ | — | — | — |
| 框选截图预览 / 保存 | — | ✅ | — | — | — |
| 跨屏取色 / HEX·RGBA | — | — | ✅ | — | — |
| 多窗便签 / 换色 / 缩放 / 本地记忆 | — | — | — | ✅ | — |
| 三栏合并 / 并排 Diff / 上传保存 | — | — | — | — | ✅ |
| 开机自启 | ✅ | ✅ | ✅ | ✅ | ✅ |

## 安装

### 方式一：安装包（推荐）

运行 `release\SelectionTranslation-Setup-1.2.0.exe`（需先执行 [`packaging\build.ps1`](#打包成安装包windows) 生成）。默认安装到 `%LOCALAPPDATA%\SelectionTranslation`，无需管理员权限；升级安装会保留已有 `settings_config.json`。

### 方式二：源码运行

环境要求：**Windows 10+**、**Python 3.10+**

```bash
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

## 启动

```bash
# 推荐：无控制台窗口
.venv\Scripts\pythonw.exe main.py

# 或调试（可见控制台输出）
python main.py
```

- 托盘常驻，**双击**托盘图标打开设置
- 仅打开设置：`python main.py --settings`
- 同时只能运行一个主程序实例

### 托盘菜单

| 菜单项 | 说明 |
| --- | --- |
| 打开设置 | 快捷键、划词按钮、开机自启等 |
| 查看日志 | 本次启动以来的运行日志（彩色） |
| 重新注册快捷键 | 休眠 / 锁屏后热键失效时可手动恢复 |
| 显示全部便签 | 显示当前已隐藏的全部便签 |
| 文件对比 | 打开本地双文件三栏合并 / 并排 Diff |
| 退出 | 关闭应用 |

## 默认快捷键

可在设置页修改；三项快捷键不可重复。

| 操作 | 默认热键 |
| --- | --- |
| 划词翻译 | `Ctrl+Alt+T` |
| OCR 翻译 | `Ctrl+Alt+O` |
| 屏幕吸色 | `Ctrl+Alt+I` |
| 新建便签 | `Ctrl+Alt+N` |

全局热键基于 Win32 `RegisterHotKey`，并在解锁会话、系统唤醒后自动重新注册；另设有定时 watchdog 兜底。

## 使用说明

### 划词翻译

1. 在任意应用中选中文字
2. 按划词快捷键，或（若已开启）点击选中文字旁的浮动翻译按钮
3. 在翻译窗口中切换引擎 / 语言、复制或朗读结果

### OCR 翻译

1. 按 OCR 快捷键进入框选模式
2. 拖动框选屏幕区域，确认后自动 OCR 并翻译
3. 可预览、保存截图，翻译区操作与划词窗口一致

### 屏幕吸色

1. 按吸色快捷键进入全屏取色模式（跨屏十字线 + 跟随鼠标的放大镜 HUD）
2. **左键**或 **C**：复制当前色值并退出（默认 `#RRGGBB`）
3. **Shift**：在 HEX 与 `rgba(r, g, b, a)` 之间切换
4. **Esc** 或 **右键抬起**：取消，不复制

### 便签

1. 按便签快捷键（默认 `Ctrl+Alt+N`）新建便签
2. 标题栏可拖动；右下角可缩放
3. **置顶** / **新增** / **换色** / **隐藏（−）** / **关闭（删除）** 仅作用于当前便签
4. 有内容时防抖保存到本地（含位置、颜色、尺寸）；无内容不保存
5. 关闭需二次确认并删除本地记录；隐藏后可在托盘菜单「显示全部便签」找回
6. 重启应用时自动恢复已保存的便签

### 朗读

翻译面板原文 / 译文旁有音量图标：优先使用有道 dictvoice 在线读音，网络不可用时回退到 Windows 系统语音（SAPI）。

## 配置

运行时配置：`settings_config.json`（由设置页写入；安装版优先与 exe 同目录，不可写时落到 `%LOCALAPPDATA%\SelectionTranslation`）  
便签数据：同目录下的 `sticky_notes.json`  
示例：`settings_config.example.json`

| 字段 | 说明 |
| --- | --- |
| `hotkey` / `ocr_hotkey` / `color_picker_hotkey` / `sticky_note_hotkey` | 划词 / OCR / 吸色 / 便签全局热键 |
| `selection_bubble` | 选中文字后显示翻译浮动按钮 |
| `start_on_boot` | 开机自启（当前用户注册表 Run 键） |
| `engine` / `source_lang` / `target_lang` | 默认翻译选项（翻译窗口内修改会自动保存） |
| `window_pinned` | 结果窗口是否置顶 |
| `translation_*` / `ocr_*` / `split_ratio` | 窗口尺寸与分栏比例 |

## 目录结构

```
SelectionTranslation/
├── main.py                       # 入口（DPI / 单实例 / 隐藏子进程控制台）
├── app.py                        # 托盘、热键、流程调度
├── boot.py                       # 开机自启
├── config.py                     # 配置读写
├── single_instance.py            # 防重复启动
├── hotkeys.py                    # Win32 全局热键
├── win_subprocess.py             # 抑制 translators/node 子进程黑框
├── app_log.py                    # 内存日志缓冲
├── selection.py                  # 选区捕获（UIA + WM_COPY）
├── selection_bubble_watcher.py   # 划词浮动按钮
├── selection_task.py             # 异步抓取选区
├── translator.py                 # 翻译引擎 + 词典
├── translate_task.py             # 异步翻译
├── tts.py                        # 原文 / 译文朗读
├── ocr.py / ocr_task.py          # OCR 识别
├── screenshot_selector.py        # 框选截图
├── color_picker.py               # 屏幕吸色
├── sticky_notes_store.py         # 便签本地持久化
├── packaging/                    # 打包脚本（PyInstaller + Inno Setup）
├── icons/                        # SVG 图标
├── web/
│   └── merge-studio/             # 文件对比前端（三栏合并 / 并排 Diff）
└── ui/                           # 界面
    ├── file_diff_window.py       # 文件对比窗口（嵌入 merge-studio）
    ├── sticky_note_window.py     # 桌面便签
    ├── note_confirm_dialog.py    # 便签删除确认框
    ├── window_pin.py             # 窗口置顶公共逻辑
    ├── note_colors.py            # 便签配色
    ├── translation_workspace.py  # 划词 / OCR 共用窗口
    ├── translation_panel.py      # 翻译面板（复制、朗读）
    ├── screenshot_panel.py       # OCR 截图区
    ├── selection_bubble.py       # 浮动按钮控件
    ├── log_window.py             # 运行日志查看
    ├── screen_coords.py          # 多屏 DPI 坐标
    ├── constants.py              # 尺寸、吸色 HUD 等常量
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
| `release\SelectionTranslation-Setup-1.2.0.exe` | 安装包（需 Inno Setup；版本见 `packaging/version.txt`） |

安装包特性：

- 安装向导按钮为英文，任务选项为中文
- 可自选安装目录（默认 `%LOCALAPPDATA%\SelectionTranslation`，显示名仍为「划词翻译」，无需管理员）
- 可选「开机自启」（写入与应用内一致的 `HKCU\...\Run\SelectionTranslation`，并同步 `settings_config.json`）
- 可选桌面快捷方式；卸载时清理自启项
- **首次安装**才写入默认配置（含吸色快捷键）；覆盖/升级安装**不会**覆盖已有用户配置

## 说明

- **划词**优先 UIA，其次经典编辑框 API，最后 `WM_COPY`（**不注入 Ctrl+C**，避免打断终端）
- **划词按钮**同样走上述路径；部分 Electron 应用依赖其是否响应 `WM_COPY`
- **翻译引擎**「自动选择」会按可用性依次尝试必应、有道、搜狗等；短词/短语附加有道词典公开释义
- **托盘「查看日志」**可查看本次启动以来的彩色运行日志（含划词/OCR 原文）；超过 6 小时或 3000 条会自动清理
- **OCR** 依赖 `rapidocr-onnxruntime`（打包时会一并打入）
- **多显示器**已适配混合 DPI；吸色与 OCR 框选均支持跨屏坐标
