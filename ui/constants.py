from pathlib import Path
import sys


def _resource_root() -> Path:
    """开发态为项目根；打包后为 PyInstaller 解包/_internal 目录。"""
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass)
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


# ── 路径 ──────────────────────────────────────────────
ROOT_DIR = _resource_root()
ICONS_DIR = ROOT_DIR / "icons"

# ── 窗口尺寸（最小 / 默认） ────────────────────────────
MIN_TEXTAREA_HEIGHT = 80          # 输入区最小高度
MIN_CONTENT_HEIGHT = 100          # 结果区最小高度
MIN_TRANSLATION_WIDTH = 280       # 翻译面板最小宽度（划词窗口 / OCR 右侧一致）
MIN_TRANSLATION_HEIGHT = 320      # 翻译窗口最小高度

DEFAULT_TRANSLATION_WIDTH = 320
DEFAULT_TRANSLATION_HEIGHT = 320
DEFAULT_SETTINGS_WIDTH = 320
DEFAULT_TEXTAREA_HEIGHT = 80
DEFAULT_CONTENT_HEIGHT = 100

SNAPSHOT_WIDTH = 320              # OCR 截图区固定宽度

# ── 布局与间距 ─────────────────────────────────────────
BORDER_RADIUS = 6                 # 统一圆角
FONT_SIZE = 14                    # 统一字号（面板正文 / 下拉框闭合态）
COMBO_POPUP_FONT_SIZE = 12        # 下拉列表字号（比闭合态略小）
COMBO_POPUP_ROW_HEIGHT = 28       # 下拉列表行高
COMBO_POPUP_H_PADDING = 40        # 下拉宽度：文字宽度之外的左右留白（含内边距）
COMBO_POPUP_MAX_VISIBLE = 8       # 下拉最多同时可见行数
WIDGET_MARGIN_V = 10              # 上下边距（区块间距、面板上下内边距）
WIDGET_MARGIN_H = 8               # 左右边距（面板左右内边距、水平间距）

# OCR 最小宽 = 截图区 + 翻译面板 + 左边距 + 栏间距 + 右边距
MIN_OCR_WIDTH = SNAPSHOT_WIDTH + MIN_TRANSLATION_WIDTH + WIDGET_MARGIN_H * 3
DEFAULT_OCR_WIDTH = max(640, MIN_OCR_WIDTH)
DEFAULT_OCR_HEIGHT = 320

# ── 标题栏 ─────────────────────────────────────────────
HEADER_BTN_SIZE = 18              # 标题栏图标按钮尺寸（pin / close）
HEADER_BAR_HEIGHT = 30            # 翻译面板标题栏区域高度
HEADER_HEIGHT = 36                # 设置页等 FramelessWindow 标题栏高度
HEADER_DRAG_HEIGHT = HEADER_BAR_HEIGHT  # 翻译窗口可拖拽区域高度

# ── 便签 ───────────────────────────────────────────────
DEFAULT_NOTE_WIDTH = 200
DEFAULT_NOTE_HEIGHT = 300
MIN_NOTE_WIDTH = 160
MIN_NOTE_HEIGHT = 120
NOTE_HEADER_HEIGHT = 32
NOTE_WINDOW_ALPHA = 200           # 便签底色透明度（0–255，约 78%）

# ── 翻译面板内部 ───────────────────────────────────────
RESULT_HEADER_HEIGHT = 30         # 结果区顶栏高度
SPLIT_LINE_BLOCK_HEIGHT = WIDGET_MARGIN_V * 2 + 2  # 分割线：上下各 WIDGET_MARGIN_V + 线宽 2

# ── 语言检测标签 ───────────────────────────────────────
TAG_MARGIN_V = 6                  # 检测标签上下内边距
TAG_MARGIN_H = 10                 # 检测标签左右内边距
TAG_DOT_SIZE = 6                  # 语言标签圆点直径

# ── 图标 ───────────────────────────────────────────────
ICON_SIZE = 12                    # 界面内 SVG 图标尺寸
TRAY_ICON_SIZE = 64               # 系统托盘图标（需大于界面图标）
TRAY_FONT_SIZE = 10               # 系统托盘右键菜单字号
SELECTION_BUBBLE_SIZE = 28        # 划词浮动按钮尺寸
SELECTION_BUBBLE_ICON = 16        # 划词浮动按钮图标尺寸

# ── 吸色 Popover ─────────────────────────────────────
COLOR_PICKER_POPOVER_FONT_SIZE = 8
COLOR_PICKER_MAG_COLS = 15       # 放大镜列数（宽）
COLOR_PICKER_MAG_ROWS = 15       # 放大镜行数（高）
COLOR_PICKER_MAG_CELL = 10         # 单格边长（像素）
