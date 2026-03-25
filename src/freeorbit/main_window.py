"""主窗口：多标签、菜单、状态栏与停靠面板。"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QCloseEvent, QKeySequence, QPalette
from PySide6.QtWidgets import (
    QFileDialog,
    QMainWindow,
    QMessageBox,
    QSizePolicy,
    QStatusBar,
    QTabWidget,
    QWidget,
)

from freeorbit.services.bookmarks import BookmarkPanel
from freeorbit.services.checksum_dialog import ChecksumDialog
from freeorbit.services.compare_view import CompareWindow
from freeorbit.services.search import SearchDock
from freeorbit.services.script_runner import ScriptDock
from freeorbit.template.structure_dock import StructureDock
from freeorbit.viewmodel.document_editor import DocumentEditor


class MainWindow(QMainWindow):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("FreeOrBit")
        self.resize(1100, 700)

        self._tabs = QTabWidget(self)
        # qt-material 等主题可能把标签设为全大写，覆盖为保持文件名原样
        self._tabs.setStyleSheet("QTabBar::tab { text-transform: none; }")
        self._tabs.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._tabs.setTabsClosable(True)
        self._tabs.tabCloseRequested.connect(self._close_tab)
        self._tabs.currentChanged.connect(self._bind_docks)
        self.setCentralWidget(self._tabs)

        self._status = QStatusBar(self)
        self.setStatusBar(self._status)

        self._search_dock = SearchDock(self)
        self.addDockWidget(Qt.RightDockWidgetArea, self._search_dock)

        self._struct_dock = StructureDock(self)
        self.addDockWidget(Qt.RightDockWidgetArea, self._struct_dock)

        self._bookmark_dock = BookmarkPanel(self)
        self.addDockWidget(Qt.LeftDockWidgetArea, self._bookmark_dock)

        self._script_dock = ScriptDock(self)
        self.addDockWidget(Qt.BottomDockWidgetArea, self._script_dock)

        # 四周工具区默认偏窄，中央编辑区占更多空间（用户仍可拖曳调整）
        self._bookmark_dock.setMaximumWidth(260)
        self._search_dock.setMaximumWidth(300)
        self._struct_dock.setMaximumWidth(300)
        self._script_dock.setMaximumHeight(480)

        self._compare_window: Optional[CompareWindow] = None

        self._create_menus()
        self._new_tab()

    def _create_menus(self) -> None:
        file_menu = self.menuBar().addMenu("文件(&F)")
        act_new = QAction("新建(&N)", self)
        act_new.setShortcut(QKeySequence.New)
        act_new.triggered.connect(self._new_tab)
        file_menu.addAction(act_new)

        act_open = QAction("打开(&O)...", self)
        act_open.setShortcut(QKeySequence.Open)
        act_open.triggered.connect(self._open_file)
        file_menu.addAction(act_open)

        act_save = QAction("保存(&S)", self)
        act_save.setShortcut(QKeySequence.Save)
        act_save.triggered.connect(self._save_file)
        file_menu.addAction(act_save)

        act_save_as = QAction("另存为(&A)...", self)
        act_save_as.setShortcut(QKeySequence.SaveAs)
        act_save_as.triggered.connect(self._save_file_as)
        file_menu.addAction(act_save_as)

        file_menu.addSeparator()
        act_exit = QAction("退出(&X)", self)
        act_exit.triggered.connect(self.close)
        file_menu.addAction(act_exit)

        edit_menu = self.menuBar().addMenu("编辑(&E)")
        act_undo = QAction("撤销(&U)", self)
        act_undo.setShortcut(QKeySequence.Undo)
        act_undo.triggered.connect(self._undo)
        edit_menu.addAction(act_undo)

        act_redo = QAction("重做(&R)", self)
        act_redo.setShortcut(QKeySequence.Redo)
        act_redo.triggered.connect(self._redo)
        edit_menu.addAction(act_redo)

        tools_menu = self.menuBar().addMenu("工具(&T)")
        act_search = QAction("搜索(&S)...", self)
        act_search.setShortcut(QKeySequence.Find)
        act_search.triggered.connect(self._search_dock.show_and_focus)
        tools_menu.addAction(act_search)

        act_checksum = QAction("校验和/哈希(&C)...", self)
        act_checksum.triggered.connect(self._open_checksum)
        tools_menu.addAction(act_checksum)

        act_compare = QAction("比较文件(&M)...", self)
        act_compare.triggered.connect(self._open_compare)
        tools_menu.addAction(act_compare)

        act_import = QAction("导入十六进制文本(&I)...", self)
        act_import.triggered.connect(self._import_hex)
        tools_menu.addAction(act_import)

        act_export = QAction("导出选区(&E)...", self)
        act_export.triggered.connect(self._export_selection)
        tools_menu.addAction(act_export)

        act_convert = QAction("转换选区为…(&V)", self)
        act_convert.triggered.connect(self._convert_selection)
        tools_menu.addAction(act_convert)

        act_goto = QAction("转到偏移…", self)
        act_goto.triggered.connect(self._goto_offset)
        tools_menu.addAction(act_goto)

        win_menu = self.menuBar().addMenu("窗口(&W)")
        act_show_search = QAction("显示搜索面板", self)
        act_show_search.triggered.connect(lambda: self._show_dock(self._search_dock))
        win_menu.addAction(act_show_search)
        act_show_struct = QAction("显示结构模板面板", self)
        act_show_struct.triggered.connect(lambda: self._show_dock(self._struct_dock))
        win_menu.addAction(act_show_struct)
        act_show_bm = QAction("显示书签面板", self)
        act_show_bm.triggered.connect(lambda: self._show_dock(self._bookmark_dock))
        win_menu.addAction(act_show_bm)
        act_show_script = QAction("显示脚本面板", self)
        act_show_script.triggered.connect(lambda: self._show_dock(self._script_dock))
        win_menu.addAction(act_show_script)
        win_menu.addSeparator()
        act_show_all = QAction("显示全部工具面板", self)
        act_show_all.triggered.connect(self._show_all_docks)
        win_menu.addAction(act_show_all)

        help_menu = self.menuBar().addMenu("帮助(&H)")
        act_about = QAction("关于(&A)", self)
        act_about.triggered.connect(self._about)
        help_menu.addAction(act_about)

        self._apply_qtawesome_icons(
            [
                (act_new, "fa5s.file"),
                (act_open, "fa5s.folder-open"),
                (act_save, "fa5s.save"),
                (act_save_as, "fa5s.save"),
                (act_exit, "fa5s.door-open"),
                (act_undo, "fa5s.undo"),
                (act_redo, "fa5s.redo"),
                (act_search, "fa5s.search"),
                (act_checksum, "fa5s.file-signature"),
                (act_compare, "fa5s.columns"),
                (act_import, "fa5s.file-import"),
                (act_export, "fa5s.file-export"),
                (act_convert, "fa5s.exchange-alt"),
                (act_goto, "fa5s.location-arrow"),
                (act_show_search, "fa5s.search"),
                (act_show_struct, "fa5s.sitemap"),
                (act_show_bm, "fa5s.bookmark"),
                (act_show_script, "fa5s.code"),
                (act_show_all, "fa5s.window-maximize"),
                (act_about, "fa5s.info-circle"),
            ]
        )

    def _apply_qtawesome_icons(self, actions: list[tuple[QAction, str]]) -> None:
        """菜单图标：Font Awesome Free，经 QtAwesome 渲染（未安装则跳过）。"""
        try:
            import qtawesome as qta
        except ImportError:
            qta = None
        color = self.palette().color(QPalette.ColorRole.WindowText).name()
        if qta is not None:
            for act, name in actions:
                act.setIcon(qta.icon(name, color=color))
        # 窗口图标优先包内 ICO，否则回退 QtAwesome
        from freeorbit.icon_assets import app_icon

        ico = app_icon()
        if ico is not None:
            self.setWindowIcon(ico)
        elif qta is not None:
            self.setWindowIcon(qta.icon("fa5s.file-code", color=color))

    def current_editor(self) -> Optional[DocumentEditor]:
        w = self._tabs.currentWidget()
        return w if isinstance(w, DocumentEditor) else None

    def _new_tab(self) -> None:
        doc = DocumentEditor(self._tabs)
        self._tabs.addTab(doc, "未命名")
        self._tabs.setCurrentWidget(doc)
        self._wire_document(doc)
        self._update_title(doc)

    def _wire_document(self, doc: DocumentEditor) -> None:
        doc.model().data_changed.connect(
            lambda *a, d=doc: self._on_doc_data_changed(d)
        )
        doc.model().modified_changed.connect(
            lambda *a, d=doc: self._on_doc_modified(d)
        )
        doc.model().file_path_changed.connect(lambda d=doc: self._update_title(d))
        doc.hex_view().cursor_moved.connect(
            lambda *a, d=doc: self._on_doc_cursor(d)
        )
        doc.hex_view().selection_changed.connect(
            lambda *a, d=doc: self._on_doc_cursor(d)
        )
        self._bind_docks()

    def _on_doc_data_changed(self, doc: DocumentEditor) -> None:
        if self.current_editor() is doc:
            self._refresh_status(doc)

    def _on_doc_modified(self, doc: DocumentEditor) -> None:
        if self.current_editor() is doc:
            self._update_title(doc)

    def _on_doc_cursor(self, doc: DocumentEditor) -> None:
        if self.current_editor() is doc:
            self._refresh_status(doc)

    def _bind_docks(self, _index: int = -1) -> None:
        doc = self.current_editor()
        if doc is None:
            return
        self._search_dock.bind_document(doc)
        self._struct_dock.bind_document(doc)
        self._bookmark_dock.bind_document(doc)
        self._script_dock.bind_document(doc)
        self._refresh_status(doc)

    def _close_tab(self, index: int, *, repopulate_if_empty: bool = True) -> None:
        """关闭标签。退出程序时 repopulate_if_empty=False，避免删完又自动新建导致无法退出。"""
        w = self._tabs.widget(index)
        if isinstance(w, DocumentEditor) and w.model().modified:
            r = QMessageBox.question(
                self,
                "未保存",
                "是否保存当前修改？",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
            )
            if r == QMessageBox.Cancel:
                return
            if r == QMessageBox.Save:
                self._tabs.setCurrentIndex(index)
                if not self._save_file():
                    return
        self._tabs.removeTab(index)
        if self._tabs.count() == 0 and repopulate_if_empty:
            self._new_tab()

    def closeEvent(self, event: QCloseEvent) -> None:
        while self._tabs.count():
            self._close_tab(0, repopulate_if_empty=False)
            if self._tabs.count():
                # 用户取消关闭
                event.ignore()
                return
        event.accept()

    def _open_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "打开文件", "", "所有文件 (*.*)")
        if not path:
            return
        doc = DocumentEditor(self._tabs)
        try:
            doc.model().load_file(path)
        except OSError as e:
            QMessageBox.warning(self, "打开失败", str(e))
            return
        self._tabs.addTab(doc, Path(path).name)
        self._tabs.setCurrentWidget(doc)
        self._wire_document(doc)
        doc.hex_view().refresh_display()

    def _save_file(self) -> bool:
        doc = self.current_editor()
        if doc is None:
            return False
        p = doc.model().file_path
        if p is None:
            return self._save_file_as()
        try:
            doc.model().save_as(p)
            doc.undo_stack().setClean()
            return True
        except OSError as e:
            QMessageBox.warning(self, "保存失败", str(e))
            return False

    def _save_file_as(self) -> bool:
        doc = self.current_editor()
        if doc is None:
            return False
        path, _ = QFileDialog.getSaveFileName(self, "另存为", "", "所有文件 (*.*)")
        if not path:
            return False
        try:
            doc.model().save_as(path)
            doc.undo_stack().setClean()
            self._update_title(doc)
            idx = self._tabs.indexOf(doc)
            if idx >= 0:
                self._tabs.setTabText(idx, Path(path).name)
            return True
        except OSError as e:
            QMessageBox.warning(self, "保存失败", str(e))
            return False

    def _undo(self) -> None:
        doc = self.current_editor()
        if doc:
            doc.undo_stack().undo()

    def _redo(self) -> None:
        doc = self.current_editor()
        if doc:
            doc.undo_stack().redo()

    def _refresh_status(self, doc: DocumentEditor) -> None:
        if self.current_editor() is not doc:
            return
        m = doc.model()
        pos = doc.hex_view().cursor_position()
        a, b = doc.hex_view().selection_range()
        sel = (b - a) if a != b else 0
        self._status.showMessage(
            f"地址: 0x{pos:X} ({pos})  |  选区: {sel} 字节  |  长度: {len(m)}  |  "
            f"模式: {'覆盖' if doc.hex_view().overwrite_mode() else '插入'}"
        )

    def _update_title(self, doc: DocumentEditor) -> None:
        idx = self._tabs.indexOf(doc)
        if idx < 0:
            return
        name = "未命名"
        if doc.model().file_path:
            name = doc.model().file_path.name
        star = "*" if doc.model().modified else ""
        self._tabs.setTabText(idx, f"{star}{name}")

    def _open_checksum(self) -> None:
        doc = self.current_editor()
        if doc is None:
            return
        dlg = ChecksumDialog(doc.model(), self)
        dlg.exec()

    def _open_compare(self) -> None:
        a, _ = QFileDialog.getOpenFileName(self, "文件 A", "", "所有文件 (*.*)")
        if not a:
            return
        b, _ = QFileDialog.getOpenFileName(self, "文件 B", "", "所有文件 (*.*)")
        if not b:
            return
        if self._compare_window is None:
            self._compare_window = CompareWindow(self)
        self._compare_window.load_paths(a, b)
        self._compare_window.show()
        self._compare_window.raise_()
        self._compare_window.activateWindow()

    def _import_hex(self) -> None:
        doc = self.current_editor()
        if doc is None:
            return
        path, _ = QFileDialog.getOpenFileName(self, "导入十六进制文本", "", "文本 (*.txt);;所有 (*.*)")
        if not path:
            return
        try:
            text = Path(path).read_text(encoding="utf-8", errors="ignore")
        except OSError as e:
            QMessageBox.warning(self, "导入", str(e))
            return
        import re

        hx = re.sub(r"\s+|0x", "", text)
        if not re.fullmatch(r"[0-9A-Fa-f]*", hx) or len(hx) % 2:
            QMessageBox.warning(self, "导入", "无效的十六进制文本")
            return
        try:
            data = bytes.fromhex(hx)
            doc.insert_bytes_at_cursor(data)
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, "导入", str(e))

    def _export_selection(self) -> None:
        doc = self.current_editor()
        if doc is None:
            return
        try:
            doc.export_selection_to_file()
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, "导出选区", str(e))

    def _convert_selection(self) -> None:
        doc = self.current_editor()
        if doc is None:
            return
        try:
            doc.open_convert_selection_dialog()
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, "转换选区", str(e))

    def _goto_offset(self) -> None:
        doc = self.current_editor()
        if doc is None:
            return
        try:
            doc.open_goto_offset_dialog()
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, "转到偏移", str(e))

    def _show_dock(self, dock: QWidget) -> None:
        dock.show()
        dock.raise_()
        dock.activateWindow()

    def _show_all_docks(self) -> None:
        for d in (
            self._search_dock,
            self._struct_dock,
            self._bookmark_dock,
            self._script_dock,
        ):
            d.show()
            d.raise_()

    def _about(self) -> None:
        QMessageBox.about(
            self,
            "关于 FreeOrBit",
            "FreeOrBit — 免费开源十六进制编辑器\nPython / PySide6\n\n"
            "界面图标使用 Font Awesome Free（https://fontawesome.com/license/free），"
            "通过 QtAwesome 在 Qt 中渲染。",
        )
