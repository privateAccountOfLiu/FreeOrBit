"""跳转到指定偏移（支持十六进制/十进制）；进程视图支持 VA 与分页切换。"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Optional

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

from freeorbit.i18n import tr

if TYPE_CHECKING:
    from freeorbit.view.hex_editor_view import HexEditorView
    from freeorbit.viewmodel.document_editor import DocumentEditor

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

    def __init__(
        self,
        hex_view: HexEditorView,
        parent: QWidget | None = None,
        *,
        document: Optional[DocumentEditor] = None,
    ) -> None:
        super().__init__(parent)
        self._hex = hex_view
        self._doc = document
        self._settings = QSettings()

        self._combo = QComboBox(self)
        self._combo.setEditable(True)
        self._combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        for t in _load_history(self._settings):
            self._combo.addItem(t)
        self._combo.setCurrentText("")
        le = self._combo.lineEdit()
        if le is not None:
            le.selectAll()

        self._tip = QLabel(self)
        self._tip.setStyleSheet("color: palette(mid);")

        self._form = QFormLayout()
        self._lbl_off = QLabel()
        self._form.addRow(self._lbl_off, self._combo)

        btn = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btn.accepted.connect(self._on_accept)
        btn.rejected.connect(self.reject)

        lay = QVBoxLayout(self)
        lay.addLayout(self._form)
        lay.addWidget(self._tip)
        lay.addWidget(btn)

        le = self._combo.lineEdit()
        if le is not None:
            le.returnPressed.connect(self._on_accept)

        self._apply_retranslate()

    def _apply_retranslate(self) -> None:
        self.setWindowTitle(tr("goto.title"))
        self._lbl_off.setText(tr("goto.label"))
        le = self._combo.lineEdit()
        if le is not None:
            if (
                self._doc is not None
                and self._doc.model().external_kind == "process"
            ):
                le.setPlaceholderText(tr("goto.hint_process_va"))
            else:
                le.setPlaceholderText(tr("goto.placeholder_simple"))
        self._tip.setText(tr("goto.hint_history"))

    def _current_text(self) -> str:
        le = self._combo.lineEdit()
        if le is not None:
            return le.text()
        return self._combo.currentText()

    def _on_accept(self) -> None:
        raw = self._current_text()
        off = _parse_offset(raw)
        if off is None:
            QMessageBox.warning(self, tr("goto.title"), tr("goto.parse_fail"))
            return
        model = self._hex.model()
        if model is None:
            return
        n = len(model)
        if n == 0:
            QMessageBox.information(self, tr("goto.title"), tr("goto.empty"))
            return
        if off < 0:
            QMessageBox.warning(self, tr("goto.title"), tr("goto.invalid_offset"))
            return

        doc = self._doc
        if (
            doc is not None
            and model.external_kind == "process"
            and doc.process_refresh_base() is not None
        ):
            rb = doc.process_refresh_base()
            assert rb is not None
            # 1) 当前缓冲内的虚拟地址
            if rb <= off < rb + n:
                idx = off - rb
                _push_history(self._settings, raw.strip())
                self._hex.select_single_byte(idx)
                self.accept()
                return
            # 2) 缓冲区内偏移
            if 0 <= off < n:
                _push_history(self._settings, raw.strip())
                self._hex.select_single_byte(off)
                self.accept()
                return
            # 3) 切换分页
            r = QMessageBox.question(
                self,
                tr("goto.page_switch_title"),
                tr("goto.page_switch_body").format(va=off),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if r != QMessageBox.StandardButton.Yes:
                return
            if doc.switch_process_memory_page(off, self, skip_discard_confirm=True):
                _push_history(self._settings, raw.strip())
                self.accept()
            return

        if off < 0 or off >= n:
            QMessageBox.warning(
                self,
                tr("goto.title"),
                tr("goto.out_of_range").format(hi=n - 1),
            )
            return
        _push_history(self._settings, raw.strip())
        self._hex.select_single_byte(off)
        self.accept()
