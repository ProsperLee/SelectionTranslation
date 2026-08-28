"""划词翻译结果窗口。"""

from ui.constants import DEFAULT_TRANSLATION_WIDTH, MIN_TRANSLATION_WIDTH
from ui.translation_workspace import TranslationWorkspace


class TranslationWindow(TranslationWorkspace):
    def __init__(
        self,
        *,
        pending_selection: bool = False,
        placement_physical: tuple[int, int] | None = None,
        placement_mode: str = "cursor",
    ):
        super().__init__(
            title="划词翻译",
            with_screenshot=False,
            default_width=DEFAULT_TRANSLATION_WIDTH,
            min_width=MIN_TRANSLATION_WIDTH,
            pending_selection=pending_selection,
            config_profile="translation",
            placement_physical=placement_physical,
            placement_mode=placement_mode,
        )
