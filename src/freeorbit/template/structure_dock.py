"""结构树停靠：内置 DWORD 预览或用户 .py 模板 build_field_tree(model)；支持标量写回。"""

from __future__ import annotations

import struct
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from PySide6.QtCore import QSettings, Qt, Signal
from PySide6.QtGui import QAction, QFontMetrics, QResizeEvent, QShowEvent
from PySide6.QtWidgets import (
    QDockWidget,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from freeorbit.i18n import tr
from freeorbit.template.builtin_templates import list_builtin_templates
from freeorbit.template.fields import (
    FieldNode,
    encode_field_value,
    load_template_from_path,
    run_template_field_tree,
)

if TYPE_CHECKING:
    from freeorbit.viewmodel.document_editor import DocumentEditor

_SETTINGS_KEY_TEMPLATE = "structure/last_template_path"

# 元数据挂在列 0，避免与「值」列编辑冲突
_ROLE_OFF = Qt.ItemDataRole.UserRole
_ROLE_SIZE = Qt.ItemDataRole.UserRole + 1
_ROLE_DTYPE = Qt.ItemDataRole.UserRole + 2


class StructureDock(QDockWidget):
    """结构树停靠：模板与字段树。"""

    struct_tree_changed = Signal()  # 结构树刷新后发射，供主窗口同步十六进制区字段高亮

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(tr("dock.struct"), parent)
        self._doc: Optional[DocumentEditor] = None
        self._template_module: Any | None = None
        self._template_path: Optional[str] = None
        self._last_template_error: str | None = None
        self._populating = False
        self._filename_raw: str = ""

        w = QWidget()
        self.setWidget(w)
        w.setStyleSheet(
            """
            QPushButton#StructToolbarButton {
                min-height: 26px;
                min-width: 52px;
                max-width: 72px;
                padding: 4px 8px;
                font-size: 12px;
            }
            QLabel#StructFilenameLabel {
                font-size: 12px;
                padding: 2px 0 4px 2px;
            }
            """
        )
        lay = QVBoxLayout(w)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(4)

        self._toolbar_area = QWidget()
        grp = QVBoxLayout(self._toolbar_area)
        grp.setSpacing(4)
        row = QHBoxLayout()
        row.setSpacing(12)

        row.addStretch(1)
        self._btn_load = QPushButton()
        self._btn_load.setObjectName("StructToolbarButton")
        self._btn_load.clicked.connect(self._load_template)
        row.addWidget(self._btn_load)

        self._btn_clear = QPushButton()
        self._btn_clear.setObjectName("StructToolbarButton")
        self._btn_clear.clicked.connect(self._clear_template)
        row.addWidget(self._btn_clear)

        self._btn_builtin = QPushButton()
        self._btn_builtin.setObjectName("StructToolbarButton")
        self._menu_builtin = QMenu(self._btn_builtin)
        self._btn_builtin.setMenu(self._menu_builtin)
        row.addWidget(self._btn_builtin)
        row.addStretch(1)
        grp.addLayout(row)

        self._lbl_status = QLabel()
        self._lbl_status.setObjectName("StructFilenameLabel")
        self._lbl_status.setWordWrap(False)
        self._lbl_status.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed
        )
        grp.addWidget(self._lbl_status)

        lay.addWidget(self._toolbar_area)

        self._tree = QTreeWidget()
        self._tree.setAlternatingRowColors(True)
        self._tree.setUniformRowHeights(True)
        self._tree.setIndentation(14)
        self._tree.setAnimated(True)
        self._tree.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        self._tree.itemChanged.connect(self._on_item_changed)
        lay.addWidget(self._tree, 1)
        self.retranslate_ui()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._apply_filename_elide()

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        self._apply_filename_elide()

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
        self._btn_load.setText(tr("struct.btn_load"))
        self._btn_load.setToolTip(tr("struct.tooltip_load"))
        self._btn_clear.setText(tr("struct.btn_clear"))
        self._btn_clear.setToolTip(tr("struct.tooltip_clear"))
        self._btn_builtin.setText(tr("struct.btn_builtin"))
        self._btn_builtin.setToolTip(tr("struct.tooltip_builtin"))
        self._tree.setHeaderLabels(
            [tr("struct.col_field"), tr("struct.col_value"), tr("struct.col_offset")]
        )
        self._update_status_label()
        self._populate_builtin_menu()

    def _populate_builtin_menu(self) -> None:
        self._menu_builtin.clear()
        entries = list_builtin_templates()
        if not entries:
            act = QAction(tr("struct.builtin_empty"), self)
            act.setEnabled(False)
            self._menu_builtin.addAction(act)
            return
        for stem, path in entries:
            label = tr("struct.builtin_item").format(name=stem.replace("_", " "))
            act = QAction(label, self)
            p = str(path)
            act.triggered.connect(
                lambda checked=False, path_str=p: self.try_load_template_path(
                    path_str, silent=False
                )
            )
            self._menu_builtin.addAction(act)

    def restore_saved_template(self) -> None:
        """启动时恢复上次成功加载的模板路径（静默失败）。"""
        s = QSettings()
        raw = s.value(_SETTINGS_KEY_TEMPLATE, "")
        path = raw if isinstance(raw, str) else ""
        if path and Path(path).is_file():
            self.try_load_template_path(path, silent=True)

    def try_load_template_path(self, path: str, *, silent: bool = False) -> bool:
        mod = load_template_from_path(path)
        if mod is None:
            if not silent:
                QMessageBox.warning(self, tr("struct.warn_title"), tr("struct.load_fail"))
            return False
        self._template_module = mod
        self._template_path = path
        self._last_template_error = None
        QSettings().setValue(_SETTINGS_KEY_TEMPLATE, path)
        self._refresh()
        if not silent:
            if self._last_template_error:
                QMessageBox.warning(
                    self,
                    tr("struct.warn_title"),
                    tr("struct.template_error").format(err=self._last_template_error),
                )
            else:
                QMessageBox.information(
                    self,
                    tr("struct.warn_title"),
                    tr("struct.load_ok").format(path=path),
                )
        return True

    def _clear_template(self) -> None:
        self._template_module = None
        self._template_path = None
        self._last_template_error = None
        QSettings().remove(_SETTINGS_KEY_TEMPLATE)
        self._refresh()
        self._update_status_label()

    def _load_template(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, tr("struct.dlg_template"), "", tr("struct.filter_py")
        )
        if not path:
            return
        self.try_load_template_path(path, silent=False)

    def _update_status_label(self) -> None:
        """仅显示当前模板文件名（或占位符）；错误时标红，详情在 ToolTip。"""
        err = self._last_template_error
        if self._template_path:
            self._filename_raw = Path(self._template_path).name
            self._lbl_status.setToolTip(str(Path(self._template_path).resolve()))
        else:
            self._filename_raw = tr("struct.filename_none")
            self._lbl_status.setToolTip("")

        if err and self._template_module is not None and self._template_path:
            self._lbl_status.setStyleSheet(
                "color: #e57373; font-size: 12px; padding: 2px 0 4px 2px;"
            )
            self._lbl_status.setToolTip(
                f"{Path(self._template_path).resolve()}\n\n{err}"
            )
        else:
            self._lbl_status.setStyleSheet(
                "color: palette(mid); font-size: 12px; padding: 2px 0 4px 2px;"
            )

        self._apply_filename_elide()

    def _apply_filename_elide(self) -> None:
        raw = self._filename_raw
        if not raw:
            self._lbl_status.setText(tr("struct.filename_none"))
            return
        w = self._lbl_status.width()
        if w <= 40:
            w = max(120, self.width() - 40)
        fm = QFontMetrics(self._lbl_status.font())
        self._lbl_status.setText(
            fm.elidedText(raw, Qt.TextElideMode.ElideMiddle, max(60, w))
        )

    def locate_field_at_offset(self, offset: int) -> bool:
        """选中包含字节偏移 offset 的最内层字段节点（对齐 010「Jump to Template Variable」思路）。"""
        target = self.deepest_item_for_offset(offset)
        if target is None:
            return False
        self._expand_parents(target)
        self._tree.setCurrentItem(target, 0)
        self._tree.scrollToItem(target)
        self._tree.setFocus(Qt.FocusReason.OtherFocusReason)
        return True

    def deepest_item_for_offset(self, offset: int) -> QTreeWidgetItem | None:
        """返回包含 offset 的最内层字段节点（无匹配则 None）。"""
        if self._tree.topLevelItemCount() == 0 or self._doc is None:
            return None
        n = len(self._doc.model())
        if n <= 0 or offset < 0 or offset >= n:
            return None
        for i in range(self._tree.topLevelItemCount()):
            it = self._tree.topLevelItem(i)
            found = self._find_deepest_item_for_offset(it, offset)
            if found is not None:
                return found
        return None

    def field_range_at_offset(self, offset: int) -> tuple[int, int] | None:
        """当前结构树中覆盖 offset 的字段 (起始偏移, 长度)；无则 None。"""
        item = self.deepest_item_for_offset(offset)
        if item is None:
            return None
        off = item.data(0, _ROLE_OFF)
        size = item.data(0, _ROLE_SIZE)
        if isinstance(off, int) and isinstance(size, int) and size > 0:
            return (off, size)
        return None

    def field_path_at_offset(self, offset: int) -> str | None:
        """从根到叶子的字段名路径，用于悬停提示。"""
        item = self.deepest_item_for_offset(offset)
        if item is None:
            return None
        parts: list[str] = []
        p: QTreeWidgetItem | None = item
        while p is not None:
            parts.append(p.text(0))
            p = p.parent()
        return " > ".join(reversed(parts))

    @staticmethod
    def _expand_parents(item: QTreeWidgetItem) -> None:
        p = item.parent()
        while p is not None:
            p.setExpanded(True)
            p = p.parent()

    def _find_deepest_item_for_offset(
        self, item: QTreeWidgetItem, offset: int
    ) -> QTreeWidgetItem | None:
        off = item.data(0, _ROLE_OFF)
        size = item.data(0, _ROLE_SIZE)
        if not isinstance(off, int) or not isinstance(size, int):
            return None
        if size < 0 or not (off <= offset < off + size):
            return None
        for i in range(item.childCount()):
            ch = item.child(i)
            inner = self._find_deepest_item_for_offset(ch, offset)
            if inner is not None:
                return inner
        return item

    def _refresh(self) -> None:
        self._tree.blockSignals(True)
        self._populating = True
        try:
            self._tree.clear()
            if self._doc is None:
                return
            m = self._doc.model()
            nodes, err = run_template_field_tree(self._template_module, m)
            self._last_template_error = err
            self._populate_nodes(self._tree, nodes)
            self._tree.expandToDepth(3)
            self._tree.header().setStretchLastSection(True)
            self._tree.setColumnWidth(0, 140)
            self._tree.setColumnWidth(1, 168)
            self._update_status_label()
        finally:
            self._populating = False
            self._tree.blockSignals(False)
        self.struct_tree_changed.emit()

    def _populate_nodes(self, tree: QTreeWidget, nodes: list[FieldNode]) -> None:
        for node in nodes:
            self._add_node_item(tree, None, node)

    def _add_node_item(
        self,
        tree: QTreeWidget,
        parent_item: QTreeWidgetItem | None,
        node: FieldNode,
    ) -> None:
        cols = [node.name, node.value_repr, f"0x{node.offset:X}"]
        if parent_item is None:
            it = QTreeWidgetItem(cols)
            tree.addTopLevelItem(it)
        else:
            it = QTreeWidgetItem(parent_item, cols)
        it.setData(0, _ROLE_OFF, node.offset)
        it.setData(0, _ROLE_SIZE, node.size)
        dtype = (node.dtype or "").strip()
        it.setData(0, _ROLE_DTYPE, dtype)
        if dtype:
            it.setFlags(
                it.flags()
                | Qt.ItemFlag.ItemIsEditable
                | Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsSelectable
            )
        if node.children:
            for ch in node.children:
                self._add_node_item(tree, it, ch)

    def _on_item_double_clicked(self, item: QTreeWidgetItem, col: int) -> None:
        if self._doc is None:
            return
        dtype = item.data(0, _ROLE_DTYPE)
        if col == 1 and isinstance(dtype, str) and dtype:
            self._tree.editItem(item, 1)
            return
        off = item.data(0, _ROLE_OFF)
        if isinstance(off, int) and off >= 0:
            self._doc.hex_view().set_cursor_position(off, nibble=0)
            self._doc.hex_view().setFocus(Qt.FocusReason.OtherFocusReason)

    def _on_item_changed(self, item: QTreeWidgetItem, col: int) -> None:
        if self._populating or col != 1 or self._doc is None:
            return
        dtype = item.data(0, _ROLE_DTYPE)
        if not isinstance(dtype, str) or not dtype:
            return
        offset = item.data(0, _ROLE_OFF)
        size = item.data(0, _ROLE_SIZE)
        if not isinstance(offset, int) or not isinstance(size, int):
            return
        text = item.text(1)
        try:
            data = encode_field_value(dtype, text)
        except (ValueError, struct.error, OverflowError) as e:
            QMessageBox.warning(
                self,
                tr("struct.warn_title"),
                tr("struct.field_edit_error").format(err=str(e)),
            )
            self._refresh()
            return
        if len(data) != size:
            QMessageBox.warning(
                self,
                tr("struct.warn_title"),
                tr("struct.field_size_mismatch").format(
                    expect=size, got=len(data)
                ),
            )
            self._refresh()
            return
        try:
            self._doc.model().ensure_mutable_copy()
            self._doc.model().replace_range(offset, data)
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(
                self,
                tr("struct.warn_title"),
                tr("struct.field_edit_error").format(err=str(e)),
            )
            self._refresh()
            return
        self._refresh()
