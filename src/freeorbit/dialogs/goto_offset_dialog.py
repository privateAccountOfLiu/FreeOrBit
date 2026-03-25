"""跳转到指定偏移（支持十六进制/十进制）。"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from freeorbit.view.hex_editor_view import HexEditorView

_HISTORY_KEY = "goto/history"
_MAX_HISTORY = 10


def _parse_offset(text: str) -> int | None:
    t = text.strip()
    if not t:
        return None
    if re.match(r"^0[xX]", t):
        try:
            return int(t, 16)
        except ValueError:
            return None
    if re.match(r"^[0-9A-Fa-f]+$", t) and not re.match(r"^\d+$", t):
        try:
            return int(t, 16)
        except ValueError:
            return None
    try:
        return int(t, 0)
    except ValueError:
        return None


def _load_history(settings: QSettings) -> list[str]:
    raw = settings.value(_HISTORY_KEY, "")
    if not raw or not isinstance(raw, str):
        return []
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return [str(x) for x in data if str(x).strip()][: _MAX_HISTORY]
    except (json.JSONDecodeError, TypeError):
        pass
    return []


def _save_history(settings: QSettings, items: list[str]) -> None:
    settings.setValue(_HISTORY_KEY, json.dumps(items[:_MAX_HISTORY], ensure_ascii=False))


def _push_history(settings: QSettings, entry: str) -> None:
    e = entry.strip()
    if not e:
        return
    cur = _load_history(settings)
    if e in cur:
        cur.remove(e)
    cur.insert(0, e)
    _save_history(settings, cur)


class GotoOffsetDialog(QDialog):
    """快捷键 G：输入偏移并跳转，选中该字节。"""

    def __init__(self, hex_view: HexEditorView, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("转到偏移")
        self._hex = hex_view
        self._settings = QSettings()

        self._combo = QComboBox(self)
        self._combo.setEditable(True)
        self._combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        for t in _load_history(self._settings):
            self._combo.addItem(t)
        self._combo.setCurrentText("")
        le = self._combo.lineEdit()
        if le is not None:
            le.setPlaceholderText("十进制 或 0x 前缀十六进制")
            le.selectAll()

        tip = QLabel("提示：Enter 确认；保留最近 10 次成功跳转。")
        tip.setStyleSheet("color: palette(mid);")

        form = QFormLayout()
        form.addRow("偏移:", self._combo)

        btn = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btn.accepted.connect(self._on_accept)
        btn.rejected.connect(self.reject)

        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(tip)
        lay.addWidget(btn)

        le = self._combo.lineEdit()
        if le is not None:
            le.returnPressed.connect(self._on_accept)

    def _current_text(self) -> str:
        le = self._combo.lineEdit()
        if le is not None:
            return le.text()
        return self._combo.currentText()

    def _on_accept(self) -> None:
        raw = self._current_text()
        off = _parse_offset(raw)
        if off is None:
            QMessageBox.warning(self, "转到偏移", "无法解析偏移，请输入十进制或 0x 开头的十六进制。")
            return
        model = self._hex.model()
        if model is None:
            return
        n = len(model)
        if n == 0:
            QMessageBox.information(self, "转到偏移", "文件为空。")
            return
        if off < 0 or off >= n:
            QMessageBox.warning(
                self,
                "转到偏移",
                f"偏移超出范围：有效 0～{n - 1}（0x0～0x{n - 1:X}）。",
            )
            return
        _push_history(self._settings, raw.strip())
        self._hex.select_single_byte(off)
        self.accept()
