"""后台翻译任务。"""

from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from translator import translate_text


class TranslateTask(QThread):
    finished_ok = Signal(str)
    failed = Signal(str)

    def __init__(
        self,
        text: str,
        source_code: str,
        target_code: str,
        engine_code: str,
        parent=None,
    ):
        super().__init__(parent)
        self._text = text
        self._source_code = source_code
        self._target_code = target_code
        self._engine_code = engine_code

    def run(self):
        try:
            result, _detected, _used = translate_text(
                self._text,
                target=self._target_code,
                source=self._source_code,
                engine=self._engine_code,
                rich=True,
            )
        except Exception as exc:
            if not self.isInterruptionRequested():
                self.failed.emit(str(exc))
            return
        if self.isInterruptionRequested():
            return
        if not result:
            self.failed.emit("翻译结果为空，请稍后重试。")
            return
        self.finished_ok.emit(result)
