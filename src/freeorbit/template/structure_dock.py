"""结构树停靠：展示简单 DWORD 解析或用户模板。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from PySide6.QtWidgets import (
    QDockWidget,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from freeorbit.i18n import tr
from freeorbit.template.fields import field_tree, load_template_from_path

if TYPE_CHECKING:
    from freeorbit.viewmodel.document_editor import DocumentEditor


class StructureDock(QDockWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(tr("dock.struct"), parent)
        self._doc: Optional[DocumentEditor] = None
        self._template_path: Optional[str] = None

        w = QWidget()
        self.setWidget(w)
        lay = QVBoxLayout(w)
        row = QHBoxLayout()
        self._btn_load = QPushButton()
        self._btn_load.clicked.connect(self._load_template)
        row.addWidget(self._btn_load)
        self._lbl_hint = QLabel()
        row.addWidget(self._lbl_hint)
        lay.addLayout(row)

        self._tree = QTreeWidget()
        lay.addWidget(self._tree)
        self.retranslate_ui()

    def bind_document(self, doc: DocumentEditor) -> None:
        if self._doc is not None:
            try:
                self._doc.model().data_changed.disconnect(self._refresh)
            except TypeError:
                pass
        self._doc = doc
        doc.model().data_changed.connect(self._refresh)
        self._refresh()

    def retranslate_ui(self) -> None:
        self.setWindowTitle(tr("dock.struct"))
        self._btn_load.setText(tr("struct.load"))
        self._lbl_hint.setText(tr("struct.optional"))
        self._tree.setHeaderLabels(
            [tr("struct.col_field"), tr("struct.col_value"), tr("struct.col_offset")]
        )

    def _refresh(self) -> None:
        self._tree.clear()
        if self._doc is None:
            return
        m = self._doc.model()
        for node in field_tree(m):
            QTreeWidgetItem(
                self._tree, [node.name, node.value_repr, f"0x{node.offset:X}"]
            )

    def _load_template(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, tr("struct.dlg_template"), "", tr("struct.filter_py")
        )
        if not path:
            return
        mod = load_template_from_path(path)
        if mod is None:
            QMessageBox.warning(self, tr("struct.warn_title"), tr("struct.load_fail"))
            return
        self._template_path = path
        QMessageBox.information(
            self,
            tr("struct.warn_title"),
            tr("struct.load_ok").format(path=path),
        )
