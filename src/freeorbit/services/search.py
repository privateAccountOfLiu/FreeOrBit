"""异步二进制搜索与结果停靠窗口。"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QComboBox,
    QDockWidget,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from freeorbit.i18n import tr

if TYPE_CHECKING:
    from freeorbit.viewmodel.document_editor import DocumentEditor


def parse_hex_search_pattern(text: str) -> tuple[bytes, Optional[bytes]]:
    """
    解析搜索框内容。
    返回 (pattern, mask)；mask 为 None 表示全字节精确匹配；
    若含 ?? 则进入掩码模式，mask 中 0 表示该字节通配。
    """
    raw = re.sub(r"\s+", "", (text or "").strip())
    if not raw:
        return b"", None
    if "??" in raw:
        if re.search(r"(?<!\?)\?(?!\?)", raw):
            raise ValueError("mask_bad_single")
        tokens = re.findall(r"[0-9A-Fa-f]{2}|\?\?", raw, re.I)
        if not tokens:
            raise ValueError("mask_empty")
        pat = bytearray()
        mask = bytearray()
        for t in tokens:
            if t == "??":
                pat.append(0)
                mask.append(0)
            else:
                pat.append(int(t, 16))
                mask.append(0xFF)
        return bytes(pat), bytes(mask)
    if "?" in raw:
        raise ValueError("mask_bad_single")
    if len(raw) % 2:
        raise ValueError("hex_even")
    return bytes.fromhex(raw), None


def parse_search_pattern(text: str, mode: str) -> tuple[bytes, Optional[bytes]]:
    """mode 为 \"hex\" 或 \"ascii\"（ASCII 字面量逐字节匹配）。"""
    if mode == "ascii":
        raw = (text or "").strip()
        if not raw:
            raise ValueError("empty_pattern")
        try:
            return raw.encode("ascii"), None
        except UnicodeEncodeError as e:
            raise ValueError("ascii_only") from e
    return parse_hex_search_pattern(text)


class SearchWorkerSignals(QObject):
    finished = Signal(list)  # list[int] 偏移
    error = Signal(str)


class _SearchTask(QRunnable):
    def __init__(
        self,
        data: bytes,
        pattern: bytes,
        mask: Optional[bytes],
        start: int,
    ) -> None:
        super().__init__()
        self._data = data
        self._pattern = pattern
        self._mask = mask
        self._start = start
        self.signals = SearchWorkerSignals()

    def run(self) -> None:
        try:
            hits: list[int] = []
            d = self._data
            pat = self._pattern
            if not pat:
                self.signals.finished.emit([])
                return
            mask = self._mask
            if mask is None:
                i = self._start
                while True:
                    j = d.find(pat, i)
                    if j < 0:
                        break
                    hits.append(j)
                    i = j + 1
                self.signals.finished.emit(hits)
                return
            mlen = len(pat)
            n = len(d)
            for i in range(self._start, n - mlen + 1):
                ok = True
                for j in range(mlen):
                    if mask[j] != 0 and d[i + j] != pat[j]:
                        ok = False
                        break
                if ok:
                    hits.append(i)
            self.signals.finished.emit(hits)
        except Exception as e:  # noqa: BLE001
            self.signals.error.emit(str(e))


class SearchDock(QDockWidget):
    """搜索停靠窗口：十六进制字节串（支持 ?? 通配）或 ASCII 字面量。"""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(tr("dock.search"), parent)
        self._doc: Optional[DocumentEditor] = None
        self._pool = QThreadPool.globalInstance()

        w = QWidget()
        self.setWidget(w)
        lay = QVBoxLayout(w)
        row_mode = QHBoxLayout()
        self._lbl_mode = QLabel()
        row_mode.addWidget(self._lbl_mode)
        self._mode = QComboBox()
        self._mode.addItem(tr("search.mode_hex"), "hex")
        self._mode.addItem(tr("search.mode_ascii"), "ascii")
        self._mode.currentIndexChanged.connect(self._update_placeholder)
        row_mode.addWidget(self._mode, 1)
        lay.addLayout(row_mode)

        row_pat = QHBoxLayout()
        self._lbl_pat = QLabel()
        row_pat.addWidget(self._lbl_pat)
        self._pat = QLineEdit()
        row_pat.addWidget(self._pat, 1)
        self._btn = QPushButton()
        self._btn.clicked.connect(self._run_search)
        row_pat.addWidget(self._btn)
        lay.addLayout(row_pat)

        self._list = QListWidget()
        self._list.itemDoubleClicked.connect(self._on_jump)
        lay.addWidget(self._list)
        self.retranslate_ui()

    def bind_document(self, doc: DocumentEditor) -> None:
        self._doc = doc

    def show_and_focus(self) -> None:
        self.show()
        self.raise_()
        self._pat.setFocus()

    def retranslate_ui(self) -> None:
        self.setWindowTitle(tr("dock.search"))
        self._lbl_mode.setText(tr("search.mode_label"))
        self._lbl_pat.setText(tr("search.pattern_label"))
        self._mode.setItemText(0, tr("search.mode_hex"))
        self._mode.setItemText(1, tr("search.mode_ascii"))
        self._btn.setText(tr("search.button"))
        self._update_placeholder()

    def _update_placeholder(self, *_args: object) -> None:
        if self._mode.currentData() == "ascii":
            self._pat.setPlaceholderText(tr("search.placeholder_ascii"))
        else:
            self._pat.setPlaceholderText(tr("search.placeholder"))

    @staticmethod
    def _format_parse_error(code: str) -> str:
        if code == "hex_even":
            return tr("search.hex_even")
        if code == "mask_bad_single":
            return tr("search.mask_bad_single")
        if code == "mask_empty":
            return tr("search.mask_empty")
        if code == "empty_pattern":
            return tr("search.empty_pattern")
        if code == "ascii_only":
            return tr("search.ascii_only")
        return code

    def _parse_pattern(self) -> tuple[bytes, Optional[bytes]]:
        mode = self._mode.currentData()
        if not isinstance(mode, str):
            mode = "hex"
        return parse_search_pattern(self._pat.text(), mode)

    def _run_search(self) -> None:
        if self._doc is None:
            return
        try:
            pat, mask = self._parse_pattern()
        except ValueError as e:
            code = str(e)
            QMessageBox.warning(
                self,
                tr("search.warn_title"),
                self._format_parse_error(code),
            )
            return
        model = self._doc.model()
        data = model.read(0, len(model))
        task = _SearchTask(data, pat, mask, 0)
        task.signals.finished.connect(self._on_results)
        task.signals.error.connect(
            lambda m: QMessageBox.warning(self, tr("search.warn_title"), m)
        )
        self._pool.start(task)

    def _on_results(self, hits: list[int]) -> None:
        self._list.clear()
        for off in hits:
            self._list.addItem(QListWidgetItem(f"0x{off:X}  ({off})"))
        if self._doc is not None:
            self._doc.hex_view().set_search_hits(set(hits))
        self._status_msg(len(hits))

    def _status_msg(self, n: int) -> None:
        mw = self.parent()
        if mw is not None and hasattr(mw, "statusBar"):
            mw.statusBar().showMessage(tr("search.found").format(n=n))

    def _on_jump(self, item: QListWidgetItem) -> None:
        if self._doc is None:
            return
        text = item.text().split()[0]
        off = int(text, 16)
        self._doc.hex_view().set_cursor_position(off, nibble=0)

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._doc is not None:
            self._doc.hex_view().clear_search_hits()
        super().closeEvent(event)
