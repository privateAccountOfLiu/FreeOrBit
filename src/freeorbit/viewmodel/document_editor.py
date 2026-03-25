"""单文档：模型 + 十六进制视图 + 撤销栈 + 键盘编辑。"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QByteArray, QEvent, QMimeData, QPoint, Qt
from PySide6.QtGui import QClipboard, QGuiApplication, QKeyEvent, QUndoStack
from PySide6.QtWidgets import (
    QFileDialog,
    QMenu,
    QMessageBox,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from freeorbit.commands.edit_commands import (
    DeleteBytesCommand,
    InsertBytesCommand,
    ModifyBytesCommand,
)
from freeorbit.model.binary_data_model import BinaryDataModel
from freeorbit.view.hex_editor_view import HexEditorView


_HEX_RE = re.compile(r"^[0-9A-Fa-f]$")


class DocumentEditor(QWidget):
    """一个标签页对应一个文档。"""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.bookmarks: list[tuple[int, str]] = []
        self._model = BinaryDataModel(self)
        self._hex = HexEditorView(self)
        self._hex.set_model(self._model)
        self._undo = QUndoStack(self)

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self._hex, 1)  # 占满标签页，随主窗口与停靠区变化伸展

        self._hex.installEventFilter(self)
        self._hex.cursor_moved.connect(self._on_cursor_moved)
        self._hex.selection_changed.connect(self._on_selection_changed)
        self._hex.context_menu_requested.connect(self._on_hex_context_menu)

    def model(self) -> BinaryDataModel:
        return self._model

    def hex_view(self) -> HexEditorView:
        return self._hex

    def undo_stack(self) -> QUndoStack:
        return self._undo

    def insert_bytes_at_cursor(self, data: bytes) -> None:
        """在光标处插入并记入撤销栈。"""
        self._model.ensure_mutable_copy()
        pos = self._hex.cursor_position()
        self._undo.push(InsertBytesCommand(self._model, pos, data))
        nl = len(self._model)
        hi = max(0, nl - 1)
        self._hex.set_cursor_position(min(pos + len(data) - 1, hi) if data else pos, nibble=0)
        self._hex.update_view()

    def _on_cursor_moved(self, _pos: int) -> None:
        pass

    def _on_selection_changed(self, _a: int, _b: int) -> None:
        pass

    def _on_hex_context_menu(self, global_pos: QPoint) -> None:
        menu = QMenu(self)
        menu.addAction("导出选区…", self.export_selection_to_file)
        menu.addAction("转换选区为…", self.open_convert_selection_dialog)
        menu.exec(global_pos)

    def export_selection_to_file(self) -> None:
        """将当前选区（无选区时为光标处 1 字节）导出为十六进制文本文件。"""
        parent = self.window()
        try:
            a, b = self._hex.selection_range()
            if a == b:
                a = self._hex.cursor_position()
                b = a + 1
            if b <= a:
                return
            raw = self._model.read(a, b - a)
            path, _ = QFileDialog.getSaveFileName(
                parent, "导出选区", "", "文本 (*.txt);;所有文件 (*.*)"
            )
            if not path:
                return
            Path(path).write_text(raw.hex().upper(), encoding="utf-8")
        except OSError as e:
            QMessageBox.warning(parent, "导出失败", str(e))

    def open_convert_selection_dialog(self) -> None:
        from freeorbit.dialogs.convert_selection_dialog import ConvertSelectionDialog

        parent = self.window()
        try:
            dlg = ConvertSelectionDialog(self._model, self._hex, parent)
            dlg.exec()
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(parent, "转换选区", str(e))

    def open_goto_offset_dialog(self) -> None:
        from freeorbit.dialogs.goto_offset_dialog import GotoOffsetDialog

        parent = self.window()
        try:
            GotoOffsetDialog(self._hex, parent).exec()
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(parent, "转到偏移", str(e))

    def eventFilter(self, obj: object, event: QEvent) -> bool:
        if obj is self._hex and event.type() == QEvent.Type.KeyPress:
            ev = event
            assert isinstance(ev, QKeyEvent)
            if self._handle_key(ev):
                return True
        return super().eventFilter(obj, event)

    def _handle_key(self, ev: QKeyEvent) -> bool:
        key = ev.key()
        mods = ev.modifiers()
        text = ev.text()

        # 撤销 / 重做
        if mods & Qt.ControlModifier and key == Qt.Key_Z:
            self._undo.undo()
            return True
        if (mods & Qt.ControlModifier and key == Qt.Key_Y) or (
            mods & (Qt.ControlModifier | Qt.ShiftModifier) and key == Qt.Key_Z
        ):
            self._undo.redo()
            return True

        # 复制 / 剪切 / 粘贴
        if mods & Qt.ControlModifier and key == Qt.Key_C:
            self._copy()
            return True
        if mods & Qt.ControlModifier and key == Qt.Key_X:
            self._cut()
            return True
        if mods & Qt.ControlModifier and key == Qt.Key_V:
            self._paste()
            return True

        # Insert 键切换覆盖/插入
        if key == Qt.Key_Insert:
            self._hex.set_overwrite_mode(not self._hex.overwrite_mode())
            return True

        # Tab 切换模式（与 Insert 二选一）
        if key == Qt.Key_Tab:
            self._hex.set_overwrite_mode(not self._hex.overwrite_mode())
            return True

        # 删除
        if key == Qt.Key_Delete:
            self._delete_forward()
            return True
        if key == Qt.Key_Backspace:
            self._delete_backward()
            return True

        # G：转到偏移（仅十六进制视图焦点，无修饰键）
        if key == Qt.Key_G and mods == Qt.KeyboardModifier.NoModifier:
            self.open_goto_offset_dialog()
            return True

        # 十六进制输入
        if text and _HEX_RE.match(text):
            d = int(text, 16)
            self._type_hex_nibble(d)
            return True

        return False

    def _type_hex_nibble(self, d: int) -> None:
        """覆盖写入半字节；空文件首键插入一字节。Insert 键仅影响粘贴等行为，不改变半字节逻辑。"""
        model = self._model
        model.ensure_mutable_copy()
        size = len(model)
        pos = self._hex.cursor_position()
        nib = self._hex.nibble_index()
        pos = min(pos, max(0, size - 1)) if size else 0

        if size == 0:
            self._undo.push(InsertBytesCommand(model, 0, bytes([d << 4])))
            self._hex.set_nibble_index(1)
            self._hex.update_view()
            return

        old = model.read_byte(pos)
        if nib == 0:
            new_b = (old & 0x0F) | (d << 4)
        else:
            new_b = (old & 0xF0) | d
        self._undo.push(ModifyBytesCommand(model, pos, bytes([old]), bytes([new_b])))
        self._advance_after_nibble(pos, nib, size)

    def _advance_after_nibble(self, pos: int, nib: int, size: int) -> None:
        model = self._model
        if nib == 0:
            self._hex.set_nibble_index(1)
        else:
            next_pos = pos + 1
            if next_pos < size:
                self._hex.set_cursor_position(next_pos, nibble=0)
            elif pos == size - 1:
                # 在文件末尾追加空字节，继续输入
                self._undo.push(InsertBytesCommand(model, size, bytes([0])))
                self._hex.set_cursor_position(size, nibble=0)
            else:
                self._hex.set_cursor_position(pos, nibble=0)
        self._hex.update_view()

    def _selected_range(self) -> tuple[int, int]:
        a, b = self._hex.selection_range()
        if a == b:
            return (self._hex.cursor_position(), self._hex.cursor_position() + 1)
        return (a, b)

    def _copy(self) -> None:
        a, b = self._hex.selection_range()
        if a == b:
            a = self._hex.cursor_position()
            b = a + 1
        if b <= a or a >= len(self._model):
            return
        b = min(b, len(self._model))
        data = self._model.read(a, b - a)
        md = QMimeData()
        md.setText(data.hex().upper())
        md.setData("application/octet-stream", QByteArray(data))
        QGuiApplication.clipboard().setMimeData(md)

    def _cut(self) -> None:
        self._copy()
        self._delete_selection()

    def _paste(self) -> None:
        clip = QGuiApplication.clipboard()
        text = clip.text().strip()
        raw = clip.mimeData().data("application/octet-stream")
        data: bytes
        if raw:
            data = bytes(raw)
        elif text:
            hex_clean = re.sub(r"\s+", "", text)
            if re.fullmatch(r"[0-9A-Fa-f]*", hex_clean) and len(hex_clean) % 2 == 0:
                data = bytes.fromhex(hex_clean)
            else:
                data = text.encode("utf-8", errors="replace")
        else:
            return
        self._model.ensure_mutable_copy()
        a, b = self._hex.selection_range()
        pos = a if a != b else self._hex.cursor_position()
        self._undo.beginMacro("粘贴")
        if a != b:
            self._undo.push(DeleteBytesCommand(self._model, a, self._model.read(a, b - a)))
            pos = a
        self._undo.push(InsertBytesCommand(self._model, pos, data))
        self._undo.endMacro()
        hi = max(0, len(self._model) - 1)
        self._hex.set_cursor_position(min(pos + len(data) - 1, hi), nibble=1)

    def _delete_forward(self) -> None:
        a, b = self._hex.selection_range()
        self._model.ensure_mutable_copy()
        if a != b:
            self._undo.push(DeleteBytesCommand(self._model, a, self._model.read(a, b - a)))
            self._hex.set_cursor_position(a, nibble=0)
            return
        pos = self._hex.cursor_position()
        if pos >= len(self._model):
            return
        self._undo.push(
            DeleteBytesCommand(self._model, pos, self._model.read(pos, 1))
        )

    def _delete_backward(self) -> None:
        a, b = self._hex.selection_range()
        self._model.ensure_mutable_copy()
        if a != b:
            self._undo.push(DeleteBytesCommand(self._model, a, self._model.read(a, b - a)))
            self._hex.set_cursor_position(a, nibble=0)
            return
        pos = self._hex.cursor_position()
        if pos == 0 and self._hex.nibble_index() == 0:
            return
        if self._hex.nibble_index() == 1:
            self._hex.set_nibble_index(0)
            return
        if pos > 0:
            self._undo.push(
                DeleteBytesCommand(self._model, pos - 1, self._model.read(pos - 1, 1))
            )
            self._hex.set_cursor_position(pos - 1, nibble=1)

    def _delete_selection(self) -> None:
        a, b = self._hex.selection_range()
        if a == b:
            return
        self._model.ensure_mutable_copy()
        self._undo.push(DeleteBytesCommand(self._model, a, self._model.read(a, b - a)))
        self._hex.set_cursor_position(a, nibble=0)
