"""单文档：模型 + 十六进制视图 + 撤销栈 + 键盘编辑。"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Callable, Optional

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

from freeorbit.i18n import tr
from freeorbit.commands.edit_commands import (
    DeleteBytesCommand,
    InsertBytesCommand,
    ModifyBytesCommand,
)
from freeorbit.model.binary_data_model import BinaryDataModel
from freeorbit.platform.win_process_list import ModuleInfo
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
        self._external_flush: Optional[Callable[[], None]] = None
        self._external_close: Optional[Callable[[], None]] = None
        # 刷新快照用（进程 / 磁盘切片）；普通文件用 model.file_path
        self._refresh_pid: Optional[int] = None
        self._refresh_base: Optional[int] = None
        self._refresh_size: Optional[int] = None
        self._refresh_disk_norm: Optional[str] = None
        self._refresh_disk_offset: Optional[int] = None
        self._refresh_disk_size: Optional[int] = None
        # 主模块映像基址与 SizeOfImage（PSAPI），仅进程缓冲；用于 CE 式「仅在模块内显示 RVA」
        self._process_image_base: Optional[int] = None
        self._process_image_size: Optional[int] = None
        self._process_modules: list[ModuleInfo] = []

    def set_external_hooks(
        self,
        *,
        flush: Optional[Callable[[], None]] = None,
        close: Optional[Callable[[], None]] = None,
    ) -> None:
        """进程内存 / 磁盘切片等：保存时写回、关闭句柄。"""
        self._external_flush = flush
        self._external_close = close

    def external_flush(self) -> None:
        if self._external_flush is not None:
            self._external_flush()

    def external_close(self) -> None:
        if self._external_close is not None:
            self._external_close()
        self._external_close = None
        self._external_flush = None
        self._clear_refresh_sources()

    def set_process_refresh_meta(self, pid: int, base: int, size: int) -> None:
        """打开进程内存后调用，供「刷新」重新 ReadProcessMemory。"""
        self._refresh_pid = pid
        self._refresh_base = base
        self._refresh_size = size
        self._refresh_disk_norm = None
        self._refresh_disk_offset = None
        self._refresh_disk_size = None
        self._hex.set_address_origin(base)

    def set_process_image_base(
        self,
        image_base: Optional[int],
        image_size: Optional[int] = None,
    ) -> None:
        """主模块 PE 映像基址与大小；大小用于判断 VA 是否在模块内（与 CE 一致，区外显示页内偏移）。"""
        self._process_image_base = image_base
        self._process_image_size = image_size
        self._hex.set_process_image_range(image_base, image_size)

    def process_image_base(self) -> Optional[int]:
        return self._process_image_base

    def process_image_size(self) -> Optional[int]:
        return self._process_image_size

    def process_refresh_base(self) -> Optional[int]:
        return self._refresh_base

    def process_refresh_size(self) -> Optional[int]:
        return self._refresh_size

    def process_pid(self) -> Optional[int]:
        return self._refresh_pid

    def set_process_modules(self, modules: list[ModuleInfo]) -> None:
        """已加载模块列表（CE 式命中，供状态栏）；打开/刷新/切页时更新。"""
        self._process_modules = list(modules)

    def process_modules(self) -> list[ModuleInfo]:
        return list(self._process_modules)

    def set_disk_refresh_meta(self, norm_path: str, offset: int, size: int) -> None:
        """打开磁盘切片后调用。"""
        self._refresh_disk_norm = norm_path
        self._refresh_disk_offset = offset
        self._refresh_disk_size = size
        self._refresh_pid = None
        self._refresh_base = None
        self._refresh_size = None
        self._process_image_base = None
        self._process_image_size = None
        self._process_modules = []
        self._hex.set_address_origin(0)
        self._hex.set_process_image_range(None, None)

    def _clear_refresh_sources(self) -> None:
        self._refresh_pid = None
        self._refresh_base = None
        self._refresh_size = None
        self._refresh_disk_norm = None
        self._refresh_disk_offset = None
        self._refresh_disk_size = None
        self._process_image_base = None
        self._process_image_size = None
        self._process_modules = []
        self._hex.set_address_origin(0)
        self._hex.set_process_image_range(None, None)

    def can_refresh(self) -> bool:
        """是否可从外部源重新载入缓冲（进程 / 磁盘 / 已保存路径的文件）。"""
        m = self._model
        if m.external_kind == "process":
            return (
                self._refresh_pid is not None
                and self._refresh_base is not None
                and self._refresh_size is not None
            )
        if m.external_kind == "disk_slice":
            return (
                self._refresh_disk_norm is not None
                and self._refresh_disk_offset is not None
                and self._refresh_disk_size is not None
            )
        return m.file_path is not None and m.file_path.exists()

    def switch_process_memory_page(
        self,
        target_va: int,
        parent: QWidget,
        *,
        skip_discard_confirm: bool = False,
    ) -> bool:
        """切换到包含 target_va 的内存页并重新读取；成功返回 True。"""
        from freeorbit.platform import win_memory

        m = self._model
        if m.external_kind != "process" or self._refresh_pid is None:
            return False
        if m.modified and not skip_discard_confirm:
            r = QMessageBox.question(
                parent,
                tr("goto.page_switch_title"),
                tr("goto.switch_discard"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if r != QMessageBox.StandardButton.Yes:
                return False
        pid = self._refresh_pid
        img = self._process_image_base
        ps = win_memory.get_system_page_size()
        page_base = win_memory.align_address_to_page(target_va, ps)
        sz = win_memory.clamp_read_in_region(pid, page_base, ps)
        if sz <= 0:
            QMessageBox.warning(parent, tr("open_process.title"), tr("open_process.bad_region"))
            return False
        self.external_close()
        try:
            h = win_memory.open_process(pid)
            data = win_memory.read_process_memory(h, page_base, sz)
        except (OSError, ValueError) as e:
            QMessageBox.warning(parent, tr("open_process.title"), str(e))
            return False
        tab_path = m.file_path or Path(f"proc_{pid}_{page_base:#x}")
        m.load_bytes(data, tab_path, external_kind="process")

        def flush() -> None:
            win_memory.write_process_memory(
                h, page_base, bytes(m.read(0, len(m)))
            )

        def close_h() -> None:
            win_memory.close_handle(h)

        self.set_external_hooks(flush=flush, close=close_h)
        self.set_process_refresh_meta(pid, page_base, sz)
        self.set_process_image_base(img, self._process_image_size)
        from freeorbit.platform import win_process_list

        self.set_process_modules(win_process_list.list_loaded_modules(pid))
        self._undo.clear()
        self._hex.refresh_display()
        rel = target_va - page_base
        if 0 <= rel < len(m):
            self._hex.select_single_byte(rel)
        return True

    def refresh_content(self, parent: QWidget) -> tuple[bool, str]:
        """从外部源重新读取并替换当前缓冲；成功返回 (True, "")。"""
        from freeorbit.platform import disk_raw
        from freeorbit.platform import win_memory

        m = self._model
        if m.external_kind == "process":
            if not win_memory.is_windows():
                return False, tr("open_process.win_only")
            if (
                self._refresh_pid is None
                or self._refresh_base is None
                or self._refresh_size is None
            ):
                return False, tr("refresh.no_source")
            if self._external_close is not None:
                self._external_close()
            self._external_close = None
            self._external_flush = None
            try:
                h = win_memory.open_process(self._refresh_pid)
                data = win_memory.read_process_memory(
                    h, self._refresh_base, self._refresh_size
                )
            except (OSError, ValueError) as e:
                return False, str(e)

            tab_path = m.file_path or Path(
                f"proc_{self._refresh_pid}_{self._refresh_base:#x}"
            )
            m.load_bytes(data, tab_path, external_kind="process")

            def flush() -> None:
                win_memory.write_process_memory(
                    h,
                    self._refresh_base,
                    bytes(m.read(0, len(m))),
                )

            def close_h() -> None:
                win_memory.close_handle(h)

            self.set_external_hooks(flush=flush, close=close_h)
            self.set_process_refresh_meta(
                self._refresh_pid, self._refresh_base, self._refresh_size
            )
            from freeorbit.platform import win_process_list

            self.set_process_modules(
                win_process_list.list_loaded_modules(self._refresh_pid)
            )
            self._undo.clear()
            self._hex.refresh_display()
            return True, ""

        if m.external_kind == "disk_slice":
            if (
                self._refresh_disk_norm is None
                or self._refresh_disk_offset is None
                or self._refresh_disk_size is None
            ):
                return False, tr("refresh.no_source")
            try:
                data = disk_raw.read_device_range(
                    self._refresh_disk_norm,
                    self._refresh_disk_offset,
                    self._refresh_disk_size,
                )
            except (OSError, ValueError) as e:
                return False, str(e)
            tab_path = m.file_path or disk_raw.display_path_for_tab(
                self._refresh_disk_norm, self._refresh_disk_offset
            )
            m.load_bytes(data, tab_path, external_kind="disk_slice")

            def flush() -> None:
                disk_raw.write_device_range(
                    self._refresh_disk_norm,
                    self._refresh_disk_offset,
                    bytes(m.read(0, len(m))),
                )

            self.set_external_hooks(flush=flush, close=lambda: None)
            self.set_disk_refresh_meta(
                self._refresh_disk_norm,
                self._refresh_disk_offset,
                self._refresh_disk_size,
            )
            self._undo.clear()
            self._hex.refresh_display()
            return True, ""

        fp = m.file_path
        if fp is None or not fp.exists():
            return False, tr("refresh.no_source")
        if m.modified:
            r = QMessageBox.question(
                parent,
                tr("refresh.title"),
                tr("refresh.discard_changes"),
                QMessageBox.Yes | QMessageBox.No,
            )
            if r != QMessageBox.Yes:
                return False, ""
        try:
            m.load_file(fp)
        except OSError as e:
            return False, str(e)
        self._undo.clear()
        self._hex.refresh_display()
        return True, ""

    def uses_external_save(self) -> bool:
        """是否为进程内存 / 磁盘切片等外部缓冲（保存时写回而非另存为）。"""
        return self._external_flush is not None

    def _fixed_external(self) -> bool:
        return not self._model.allows_resize

    def _warn_fixed_external(self) -> bool:
        if not self._fixed_external():
            return False
        QMessageBox.information(
            self.window(),
            tr("doc.external_title"),
            tr("doc.external_no_resize"),
        )
        return True

    def model(self) -> BinaryDataModel:
        return self._model

    def hex_view(self) -> HexEditorView:
        return self._hex

    def undo_stack(self) -> QUndoStack:
        return self._undo

    def insert_bytes_at_cursor(self, data: bytes) -> None:
        """在光标处插入并记入撤销栈。"""
        if self._warn_fixed_external():
            return
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
        menu.addAction(tr("ctx.export"), self.export_selection_to_file)
        menu.addAction(tr("ctx.convert"), self.open_convert_selection_dialog)
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
                parent, tr("dlg.export_save"), "", tr("dlg.text_files")
            )
            if not path:
                return
            Path(path).write_text(raw.hex().upper(), encoding="utf-8")
        except OSError as e:
            QMessageBox.warning(parent, tr("dlg.export_fail"), str(e))

    def open_convert_selection_dialog(self) -> None:
        from freeorbit.dialogs.convert_selection_dialog import ConvertSelectionDialog

        parent = self.window()
        try:
            dlg = ConvertSelectionDialog(self._model, self._hex, parent)
            dlg.exec()
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(parent, tr("dlg.convert_sel"), str(e))

    def open_goto_offset_dialog(self) -> None:
        from freeorbit.dialogs.goto_offset_dialog import GotoOffsetDialog

        parent = self.window()
        try:
            GotoOffsetDialog(self._hex, parent, document=self).exec()
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(parent, tr("dlg.goto"), str(e))

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
            if self._fixed_external():
                return
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
                if self._fixed_external():
                    self._hex.set_cursor_position(pos, nibble=0)
                    self._hex.update_view()
                    return
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
        if self._fixed_external():
            QMessageBox.information(
                self.window(),
                tr("doc.external_title"),
                tr("doc.external_no_paste"),
            )
            return
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
        if self._warn_fixed_external():
            return
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
        if self._warn_fixed_external():
            return
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
        if self._warn_fixed_external():
            return
        a, b = self._hex.selection_range()
        if a == b:
            return
        self._model.ensure_mutable_copy()
        self._undo.push(DeleteBytesCommand(self._model, a, self._model.read(a, b - a)))
        self._hex.set_cursor_position(a, nibble=0)
