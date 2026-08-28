"""OCR 结果窗口（左侧截图 + 右侧翻译面板）。"""

from ui.constants import DEFAULT_OCR_WIDTH, MIN_OCR_WIDTH
from ui.translation_workspace import TranslationWorkspace


class OCRWindow(TranslationWorkspace):
    def __init__(
        self,
        screenshot=None,
        *,
        pending_ocr: bool = False,
        placement_physical: tuple[int, int] | None = None,
    ):
        super().__init__(
            title="OCR 翻译",
            with_screenshot=True,
            default_width=DEFAULT_OCR_WIDTH,
            min_width=MIN_OCR_WIDTH,
            screenshot=screenshot,
            pending_ocr=pending_ocr,
            config_profile="ocr",
            placement_physical=placement_physical,
            placement_mode="cursor",
        )
