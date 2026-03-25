"""书签面板：数据保存在 DocumentEditor.bookmarks。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from PySide6.QtWidgets import (
    QDockWidget,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from freeorbit.i18n import tr

if TYPE_CHECKING:
    from freeorbit.viewmodel.document_editor import DocumentEditor


class BookmarkPanel(QDockWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(tr("dock.bookmark"), parent)
        self._doc: Optional[DocumentEditor] = None

        w = QWidget()
        self.setWidget(w)
        lay = QVBoxLayout(w)
        row = QHBoxLayout()
        self._name = QLineEdit()
        row.addWidget(self._name)
        self._btn_add = QPushButton()
        self._btn_add.clicked.connect(self._add)
        row.addWidget(self._btn_add)
        lay.addLayout(row)

        self._list = QListWidget()
        self._list.itemDoubleClicked.connect(self._jump)
        lay.addWidget(self._list)
        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        self.setWindowTitle(tr("dock.bookmark"))
        self._name.setPlaceholderText(tr("bookmark.name_ph"))
        self._btn_add.setText(tr("bookmark.add"))

    def bind_document(self, doc: DocumentEditor) -> None:
        self._doc = doc
        self._reload_list()

    def _reload_list(self) -> None:
        self._list.clear()
        if self._doc is None:
            return
        for pos, name in self._doc.bookmarks:
            self._list.addItem(QListWidgetItem(f"{name}  @ 0x{pos:X}"))

    def _add(self) -> None:
        if self._doc is None:
            return
        pos = self._doc.hex_view().cursor_position()
        name = self._name.text().strip() or f"0x{pos:X}"
        self._doc.bookmarks.append((pos, name))
        self._reload_list()

    def _jump(self, item: QListWidgetItem) -> None:
        row = self._list.row(item)
        if row < 0 or self._doc is None or row >= len(self._doc.bookmarks):
            return
        pos, _ = self._doc.bookmarks[row]
        self._doc.hex_view().set_cursor_position(pos, nibble=0)
