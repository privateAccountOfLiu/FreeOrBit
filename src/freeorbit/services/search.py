"""异步二进制搜索与结果停靠窗口。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
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

if TYPE_CHECKING:
    from freeorbit.viewmodel.document_editor import DocumentEditor


class SearchWorkerSignals(QObject):
    finished = Signal(list)  # list[int] 偏移
    error = Signal(str)


class _SearchTask(QRunnable):
    def __init__(self, data: bytes, pattern: bytes, start: int) -> None:
        super().__init__()
        self._data = data
        self._pattern = pattern
        self._start = start
        self.signals = SearchWorkerSignals()

    def run(self) -> None:
        try:
            hits: list[int] = []
            i = self._start
            d = self._data
            pat = self._pattern
            if not pat:
                self.signals.finished.emit([])
                return
            while True:
                j = d.find(pat, i)
                if j < 0:
                    break
                hits.append(j)
                i = j + 1
            self.signals.finished.emit(hits)
        except Exception as e:  # noqa: BLE001
            self.signals.error.emit(str(e))


class SearchDock(QDockWidget):
    """搜索停靠窗口：字节串（十六进制）。"""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__("搜索", parent)
        self._doc: Optional[DocumentEditor] = None
        self._pool = QThreadPool.globalInstance()

        w = QWidget()
        self.setWidget(w)
        lay = QVBoxLayout(w)
        row = QHBoxLayout()
        row.addWidget(QLabel("十六进制:"))
        self._pat = QLineEdit()
        self._pat.setPlaceholderText("例如 48 65 6C 6C 6F 或 48656C6C6F")
        row.addWidget(self._pat)
        self._btn = QPushButton("搜索")
        self._btn.clicked.connect(self._run_search)
        row.addWidget(self._btn)
        lay.addLayout(row)

        self._list = QListWidget()
        self._list.itemDoubleClicked.connect(self._on_jump)
        lay.addWidget(self._list)

    def bind_document(self, doc: DocumentEditor) -> None:
        self._doc = doc

    def show_and_focus(self) -> None:
        self.show()
        self.raise_()
        self._pat.setFocus()

    def _parse_pattern(self) -> bytes:
        s = self._pat.text().strip().replace(" ", "").replace("\n", "")
        if not s:
            return b""
        if len(s) % 2:
            raise ValueError("十六进制长度须为偶数")
        return bytes.fromhex(s)

    def _run_search(self) -> None:
        if self._doc is None:
            return
        try:
            pat = self._parse_pattern()
        except ValueError as e:
            QMessageBox.warning(self, "搜索", str(e))
            return
        model = self._doc.model()
        data = model.read(0, len(model))
        task = _SearchTask(data, pat, 0)
        task.signals.finished.connect(self._on_results)
        task.signals.error.connect(lambda m: QMessageBox.warning(self, "搜索", m))
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
            mw.statusBar().showMessage(f"找到 {n} 处匹配")

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
