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

from freeorbit.dialogs.settings_dialog import SettingsDialog
from freeorbit.i18n import tr
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
        self.retranslate_ui()
        self._new_tab()

    def _create_menus(self) -> None:
        mb = self.menuBar()
        self._menu_file = mb.addMenu("")
        self._act_new = QAction(self)
        self._act_new.setShortcut(QKeySequence.New)
        self._act_new.triggered.connect(self._new_tab)
        self._menu_file.addAction(self._act_new)

        self._act_open = QAction(self)
        self._act_open.setShortcut(QKeySequence.Open)
        self._act_open.triggered.connect(self._open_file)
        self._menu_file.addAction(self._act_open)

        self._act_save = QAction(self)
        self._act_save.setShortcut(QKeySequence.Save)
        self._act_save.triggered.connect(self._save_file)
        self._menu_file.addAction(self._act_save)

        self._act_save_as = QAction(self)
        self._act_save_as.setShortcut(QKeySequence.SaveAs)
        self._act_save_as.triggered.connect(self._save_file_as)
        self._menu_file.addAction(self._act_save_as)

        self._menu_file.addSeparator()
        self._act_exit = QAction(self)
        self._act_exit.triggered.connect(self.close)
        self._menu_file.addAction(self._act_exit)

        self._menu_edit = mb.addMenu("")
        self._act_undo = QAction(self)
        self._act_undo.setShortcut(QKeySequence.Undo)
        self._act_undo.triggered.connect(self._undo)
        self._menu_edit.addAction(self._act_undo)

        self._act_redo = QAction(self)
        self._act_redo.setShortcut(QKeySequence.Redo)
        self._act_redo.triggered.connect(self._redo)
        self._menu_edit.addAction(self._act_redo)

        self._menu_tools = mb.addMenu("")
        self._act_search = QAction(self)
        self._act_search.setShortcut(QKeySequence.Find)
        self._act_search.triggered.connect(self._search_dock.show_and_focus)
        self._menu_tools.addAction(self._act_search)

        self._act_checksum = QAction(self)
        self._act_checksum.triggered.connect(self._open_checksum)
        self._menu_tools.addAction(self._act_checksum)

        self._act_compare = QAction(self)
        self._act_compare.triggered.connect(self._open_compare)
        self._menu_tools.addAction(self._act_compare)

        self._act_import = QAction(self)
        self._act_import.triggered.connect(self._import_hex)
        self._menu_tools.addAction(self._act_import)

        self._act_export = QAction(self)
        self._act_export.triggered.connect(self._export_selection)
        self._menu_tools.addAction(self._act_export)

        self._act_convert = QAction(self)
        self._act_convert.triggered.connect(self._convert_selection)
        self._menu_tools.addAction(self._act_convert)

        self._act_goto = QAction(self)
        self._act_goto.triggered.connect(self._goto_offset)
        self._menu_tools.addAction(self._act_goto)

        self._menu_win = mb.addMenu("")
        self._act_show_search = QAction(self)
        self._act_show_search.triggered.connect(
            lambda: self._show_dock(self._search_dock)
        )
        self._menu_win.addAction(self._act_show_search)
        self._act_show_struct = QAction(self)
        self._act_show_struct.triggered.connect(
            lambda: self._show_dock(self._struct_dock)
        )
        self._menu_win.addAction(self._act_show_struct)
        self._act_show_bm = QAction(self)
        self._act_show_bm.triggered.connect(
            lambda: self._show_dock(self._bookmark_dock)
        )
        self._menu_win.addAction(self._act_show_bm)
        self._act_show_script = QAction(self)
        self._act_show_script.triggered.connect(
            lambda: self._show_dock(self._script_dock)
        )
        self._menu_win.addAction(self._act_show_script)
        self._menu_win.addSeparator()
        self._act_show_all = QAction(self)
        self._act_show_all.triggered.connect(self._show_all_docks)
        self._menu_win.addAction(self._act_show_all)

        self._menu_settings = mb.addMenu("")
        self._act_open_settings = QAction(self)
        self._act_open_settings.setShortcut(QKeySequence("Ctrl+,"))
        self._act_open_settings.triggered.connect(self._open_settings)
        self._menu_settings.addAction(self._act_open_settings)

        self._menu_help = mb.addMenu("")
        self._act_about = QAction(self)
        self._act_about.triggered.connect(self._about)
        self._menu_help.addAction(self._act_about)

        self._apply_qtawesome_icons(
            [
                (self._act_new, "fa5s.file"),
                (self._act_open, "fa5s.folder-open"),
                (self._act_save, "fa5s.save"),
                (self._act_save_as, "fa5s.save"),
                (self._act_exit, "fa5s.door-open"),
                (self._act_undo, "fa5s.undo"),
                (self._act_redo, "fa5s.redo"),
                (self._act_search, "fa5s.search"),
                (self._act_checksum, "fa5s.file-signature"),
                (self._act_compare, "fa5s.columns"),
                (self._act_import, "fa5s.file-import"),
                (self._act_export, "fa5s.file-export"),
                (self._act_convert, "fa5s.exchange-alt"),
                (self._act_goto, "fa5s.location-arrow"),
                (self._act_show_search, "fa5s.search"),
                (self._act_show_struct, "fa5s.sitemap"),
                (self._act_show_bm, "fa5s.bookmark"),
                (self._act_show_script, "fa5s.code"),
                (self._act_show_all, "fa5s.window-maximize"),
                (self._act_open_settings, "fa5s.cog"),
                (self._act_about, "fa5s.info-circle"),
            ]
        )

    def retranslate_ui(self) -> None:
        self.setWindowTitle(tr("app.title"))
        self._menu_file.setTitle(tr("menu.file"))
        self._act_new.setText(tr("action.new"))
        self._act_open.setText(tr("action.open"))
        self._act_save.setText(tr("action.save"))
        self._act_save_as.setText(tr("action.save_as"))
        self._act_exit.setText(tr("action.exit"))
        self._menu_edit.setTitle(tr("menu.edit"))
        self._act_undo.setText(tr("action.undo"))
        self._act_redo.setText(tr("action.redo"))
        self._menu_tools.setTitle(tr("menu.tools"))
        self._act_search.setText(tr("action.search"))
        self._act_checksum.setText(tr("action.checksum"))
        self._act_compare.setText(tr("action.compare"))
        self._act_import.setText(tr("action.import_hex"))
        self._act_export.setText(tr("action.export_sel"))
        self._act_convert.setText(tr("action.convert"))
        self._act_goto.setText(tr("action.goto"))
        self._menu_win.setTitle(tr("menu.window"))
        self._act_show_search.setText(tr("action.show_search"))
        self._act_show_struct.setText(tr("action.show_struct"))
        self._act_show_bm.setText(tr("action.show_bookmark"))
        self._act_show_script.setText(tr("action.show_script"))
        self._act_show_all.setText(tr("action.show_all_docks"))
        self._menu_settings.setTitle(tr("menu.settings"))
        self._act_open_settings.setText(tr("action.open_settings"))
        self._menu_help.setTitle(tr("menu.help"))
        self._act_about.setText(tr("action.about"))

        self._search_dock.retranslate_ui()
        self._struct_dock.retranslate_ui()
        self._bookmark_dock.retranslate_ui()
        self._script_dock.retranslate_ui()

        for i in range(self._tabs.count()):
            w = self._tabs.widget(i)
            if isinstance(w, DocumentEditor):
                self._update_title(w)

        doc = self.current_editor()
        if doc is not None:
            self._refresh_status(doc)

    def _open_settings(self) -> None:
        dlg = SettingsDialog(self, on_apply_lang=self.retranslate_ui)
        dlg.exec()

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
        self._tabs.addTab(doc, tr("tab.untitled"))
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
                tr("dlg.unsaved"),
                tr("dlg.unsaved_msg"),
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
        path, _ = QFileDialog.getOpenFileName(
            self, tr("dlg.open_file"), "", tr("dlg.all_files")
        )
        if not path:
            return
        doc = DocumentEditor(self._tabs)
        try:
            doc.model().load_file(path)
        except OSError as e:
            QMessageBox.warning(self, tr("dlg.open_fail"), str(e))
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
            QMessageBox.warning(self, tr("dlg.save_fail"), str(e))
            return False

    def _save_file_as(self) -> bool:
        doc = self.current_editor()
        if doc is None:
            return False
        path, _ = QFileDialog.getSaveFileName(
            self, tr("dlg.save_as"), "", tr("dlg.all_files")
        )
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
            QMessageBox.warning(self, tr("dlg.save_fail"), str(e))
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
        mode = (
            tr("status.overwrite")
            if doc.hex_view().overwrite_mode()
            else tr("status.insert")
        )
        self._status.showMessage(
            f"{tr('status.addr')}: 0x{pos:X} ({pos})  |  "
            f"{tr('status.sel')}: {sel} {tr('status.bytes')}  |  "
            f"{tr('status.len')}: {len(m)}  |  "
            f"{tr('status.mode')}: {mode}"
        )

    def _update_title(self, doc: DocumentEditor) -> None:
        idx = self._tabs.indexOf(doc)
        if idx < 0:
            return
        name = tr("tab.untitled")
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
        a, _ = QFileDialog.getOpenFileName(
            self, tr("dlg.compare_a"), "", tr("dlg.all_files")
        )
        if not a:
            return
        b, _ = QFileDialog.getOpenFileName(
            self, tr("dlg.compare_b"), "", tr("dlg.all_files")
        )
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
        path, _ = QFileDialog.getOpenFileName(
            self, tr("dlg.import_hex"), "", tr("dlg.text_files")
        )
        if not path:
            return
        try:
            text = Path(path).read_text(encoding="utf-8", errors="ignore")
        except OSError as e:
            QMessageBox.warning(self, tr("dlg.import"), str(e))
            return
        import re

        hx = re.sub(r"\s+|0x", "", text)
        if not re.fullmatch(r"[0-9A-Fa-f]*", hx) or len(hx) % 2:
            QMessageBox.warning(self, tr("dlg.import"), tr("dlg.import_invalid"))
            return
        try:
            data = bytes.fromhex(hx)
            doc.insert_bytes_at_cursor(data)
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, tr("dlg.import"), str(e))

    def _export_selection(self) -> None:
        doc = self.current_editor()
        if doc is None:
            return
        try:
            doc.export_selection_to_file()
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, tr("dlg.export_sel"), str(e))

    def _convert_selection(self) -> None:
        doc = self.current_editor()
        if doc is None:
            return
        try:
            doc.open_convert_selection_dialog()
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, tr("dlg.convert_sel"), str(e))

    def _goto_offset(self) -> None:
        doc = self.current_editor()
        if doc is None:
            return
        try:
            doc.open_goto_offset_dialog()
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, tr("dlg.goto"), str(e))

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
        QMessageBox.about(self, tr("about.title"), tr("about.body"))
