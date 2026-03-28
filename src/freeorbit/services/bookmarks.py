"""书签面板：数据保存在 DocumentEditor.bookmarks；支持增删改查与 JSON 导入导出。"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDockWidget,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
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


class BookmarkEditDialog(QDialog):
    """编辑书签：偏移（十六进制）与名称。"""

    def __init__(
        self,
        parent: Optional[QWidget],
        offset: int,
        name: str,
        max_offset_exclusive: int,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("bookmark.edit_title"))
        self._max_ex = max(0, max_offset_exclusive)
        form = QFormLayout(self)
        self._off_e = QLineEdit(f"0x{offset:X}")
        self._name_e = QLineEdit(name)
        form.addRow(tr("bookmark.edit_offset"), self._off_e)
        form.addRow(tr("bookmark.edit_name"), self._name_e)
        bb = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        form.addRow(bb)

    def values(self) -> tuple[int, str]:
        raw = self._off_e.text().strip()
        try:
            off = int(raw, 0)
        except ValueError as e:
            raise ValueError(str(e)) from e
        if off < 0 or (self._max_ex > 0 and off >= self._max_ex):
            raise ValueError("range")
        name = self._name_e.text().strip() or f"0x{off:X}"
        return off, name


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

        self._filter = QLineEdit()
        self._filter.setClearButtonEnabled(True)
        self._filter.textChanged.connect(self._reload_list)
        lay.addWidget(self._filter)

        self._list = QListWidget()
        self._list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self._list.itemDoubleClicked.connect(self._jump)
        lay.addWidget(self._list, 1)

        self._shortcut_del = QShortcut(QKeySequence.StandardKey.Delete, self._list)
        self._shortcut_del.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self._shortcut_del.activated.connect(self._delete_selected)

        row2 = QHBoxLayout()
        self._btn_edit = QPushButton()
        self._btn_edit.clicked.connect(self._edit_selected)
        row2.addWidget(self._btn_edit)
        self._btn_del = QPushButton()
        self._btn_del.clicked.connect(self._delete_selected)
        row2.addWidget(self._btn_del)
        lay.addLayout(row2)

        row3 = QHBoxLayout()
        self._btn_export = QPushButton()
        self._btn_export.clicked.connect(self._export)
        row3.addWidget(self._btn_export)
        self._btn_import = QPushButton()
        self._btn_import.clicked.connect(self._import)
        row3.addWidget(self._btn_import)
        lay.addLayout(row3)

        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        self.setWindowTitle(tr("dock.bookmark"))
        self._name.setPlaceholderText(tr("bookmark.name_ph"))
        self._btn_add.setText(tr("bookmark.add"))
        self._filter.setPlaceholderText(tr("bookmark.filter_ph"))
        self._btn_edit.setText(tr("bookmark.edit"))
        self._btn_del.setText(tr("bookmark.delete"))
        self._btn_export.setText(tr("bookmark.export"))
        self._btn_import.setText(tr("bookmark.import"))

    def bind_document(self, doc: DocumentEditor) -> None:
        self._doc = doc
        self._reload_list()

    def _model_size(self) -> int:
        if self._doc is None:
            return 0
        return len(self._doc.model())

    def _reload_list(self) -> None:
        self._list.clear()
        if self._doc is None:
            return
        q = self._filter.text().strip().lower()
        hex_pos = q[2:] if q.startswith("0x") else q
        for i, (pos, name) in enumerate(self._doc.bookmarks):
            line = f"{name}  @  0x{pos:X}"
            if q:
                ok = q in line.lower()
                if not ok:
                    try:
                        if int(q, 0) == pos:
                            ok = True
                    except ValueError:
                        pass
                    if not ok and hex_pos:
                        try:
                            if int(hex_pos, 16) == pos:
                                ok = True
                        except ValueError:
                            pass
                if not ok:
                    continue
            it = QListWidgetItem(line)
            it.setData(Qt.ItemDataRole.UserRole, i)
            self._list.addItem(it)

    def _add(self) -> None:
        if self._doc is None:
            return
        pos = self._doc.hex_view().cursor_position()
        name = self._name.text().strip() or f"0x{pos:X}"
        self._doc.bookmarks.append((pos, name))
        self._reload_list()

    def _selected_source_indices(self) -> list[int]:
        out: list[int] = []
        for it in self._list.selectedItems():
            v = it.data(Qt.ItemDataRole.UserRole)
            if v is not None:
                out.append(int(v))
        return out

    def _delete_selected(self) -> None:
        if self._doc is None:
            return
        indices = sorted(set(self._selected_source_indices()), reverse=True)
        if not indices:
            return
        for i in indices:
            if 0 <= i < len(self._doc.bookmarks):
                del self._doc.bookmarks[i]
        self._reload_list()

    def _edit_selected(self) -> None:
        if self._doc is None:
            return
        items = self._list.selectedItems()
        if len(items) != 1:
            QMessageBox.information(
                self, tr("dock.bookmark"), tr("bookmark.edit_one_only")
            )
            return
        src = items[0].data(Qt.ItemDataRole.UserRole)
        if src is None:
            return
        i = int(src)
        if i < 0 or i >= len(self._doc.bookmarks):
            return
        pos, name = self._doc.bookmarks[i]
        n = self._model_size()
        dlg = BookmarkEditDialog(self, pos, name, n)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            np, nn = dlg.values()
        except ValueError as e:
            msg = (
                tr("bookmark.invalid_offset_range")
                if str(e) == "range"
                else tr("bookmark.invalid_offset")
            )
            QMessageBox.warning(self, tr("bookmark.edit_title"), msg)
            return
        self._doc.bookmarks[i] = (np, nn)
        self._reload_list()

    def _jump(self, item: QListWidgetItem) -> None:
        if self._doc is None:
            return
        src = item.data(Qt.ItemDataRole.UserRole)
        if src is None:
            return
        i = int(src)
        if i < 0 or i >= len(self._doc.bookmarks):
            return
        pos, _ = self._doc.bookmarks[i]
        self._doc.hex_view().set_cursor_position(pos, nibble=0)

    def _export(self) -> None:
        if self._doc is None or not self._doc.bookmarks:
            QMessageBox.information(
                self, tr("bookmark.export_title"), tr("bookmark.export_empty")
            )
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            tr("bookmark.export_title"),
            "",
            tr("bookmark.json_filter"),
        )
        if not path:
            return
        data = {
            "version": 1,
            "bookmarks": [
                {"offset": int(p), "name": str(n)} for p, n in self._doc.bookmarks
            ],
        }
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except OSError as e:
            QMessageBox.warning(
                self, tr("bookmark.export_title"), tr("bookmark.io_fail").format(err=e)
            )

    def _import(self) -> None:
        if self._doc is None:
            return
        path, _ = QFileDialog.getOpenFileName(
            self,
            tr("bookmark.import_title"),
            "",
            tr("bookmark.json_filter"),
        )
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as f:
                raw = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            QMessageBox.warning(
                self, tr("bookmark.import_title"), tr("bookmark.io_fail").format(err=e)
            )
            return
        if isinstance(raw, list):
            entries = raw
        else:
            entries = raw.get("bookmarks")
        if not isinstance(entries, list):
            QMessageBox.warning(
                self, tr("bookmark.import_title"), tr("bookmark.import_bad_format")
            )
            return
        n = self._model_size()
        parsed: list[tuple[int, str]] = []
        for item in entries:
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                off, nm = item[0], item[1]
            elif isinstance(item, dict):
                off = item.get("offset", item.get("off"))
                nm = item.get("name", item.get("label", ""))
            else:
                continue
            try:
                o = int(off)
            except (TypeError, ValueError):
                continue
            if n == 0 or o < 0 or o >= n:
                continue
            parsed.append((o, str(nm) if nm is not None else f"0x{o:X}"))
        if not parsed:
            QMessageBox.information(
                self, tr("bookmark.import_title"), tr("bookmark.import_nothing")
            )
            return
        r = QMessageBox.question(
            self,
            tr("bookmark.import_title"),
            tr("bookmark.import_merge_hint"),
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Yes,
        )
        if r == QMessageBox.StandardButton.Cancel:
            return
        if r == QMessageBox.StandardButton.Yes:
            seen = {p for p, _ in self._doc.bookmarks}
            for p, nm in parsed:
                if p not in seen:
                    self._doc.bookmarks.append((p, nm))
                    seen.add(p)
        else:
            self._doc.bookmarks.clear()
            self._doc.bookmarks.extend(parsed)
        self._reload_list()
