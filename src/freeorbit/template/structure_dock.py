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

from freeorbit.template.fields import field_tree, load_template_from_path

if TYPE_CHECKING:
    from freeorbit.viewmodel.document_editor import DocumentEditor


class StructureDock(QDockWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__("结构", parent)
        self._doc: Optional[DocumentEditor] = None
        self._template_path: Optional[str] = None

        w = QWidget()
        self.setWidget(w)
        lay = QVBoxLayout(w)
        row = QHBoxLayout()
        btn = QPushButton("加载模板…")
        btn.clicked.connect(self._load_template)
        row.addWidget(btn)
        row.addWidget(QLabel("（可选）用户 .py 模板"))
        lay.addLayout(row)

        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["字段", "值", "偏移"])
        lay.addWidget(self._tree)

    def bind_document(self, doc: DocumentEditor) -> None:
        if self._doc is not None:
            try:
                self._doc.model().data_changed.disconnect(self._refresh)
            except TypeError:
                pass
        self._doc = doc
        doc.model().data_changed.connect(self._refresh)
        self._refresh()

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
            self, "模板文件", "", "Python (*.py);;所有 (*.*)"
        )
        if not path:
            return
        mod = load_template_from_path(path)
        if mod is None:
            QMessageBox.warning(self, "模板", "无法加载")
            return
        self._template_path = path
        QMessageBox.information(
            self,
            "模板",
            f"已加载: {path}\n可在脚本中 importlib 使用；结构树仍为 DWORD 预览。",
        )
