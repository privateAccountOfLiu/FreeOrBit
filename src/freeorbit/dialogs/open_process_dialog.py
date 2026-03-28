"""进程列表（CE 风格）与起始地址；仅 Windows。"""

from __future__ import annotations

from PySide6.QtCore import Qt, QSettings, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QStyle,
    QTabBar,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from freeorbit.i18n import tr
from freeorbit.platform import win_memory
from freeorbit.platform import win_process_list


class ProcessListDialog(QDialog):
    """三标签进程/窗口列表 + 起始虚拟地址；返回 (pid, base_va)。"""

    _ROLE_PID = Qt.ItemDataRole.UserRole
    _ROLE_HWND = Qt.ItemDataRole.UserRole + 1
    _ROLE_IMAGE_BASE = Qt.ItemDataRole.UserRole + 2
    _ROLE_EXE_PATH = Qt.ItemDataRole.UserRole + 3

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(720, 480)
        self._prev_proc_times: dict[int, int] | None = None
        self._prev_sys_snap: tuple[int, int, int] | None = None
        self._icon_cache: dict[str, QIcon] = {}
        self._icon_chunk_start: int = 0
        self._default_file_icon: QIcon | None = None
        self._settings = QSettings()

        root = QVBoxLayout(self)

        self._warn = QLabel("")
        self._warn.setWordWrap(True)
        root.addWidget(self._warn)

        self._tab_bar = QTabBar(self)
        self._tab_bar.addTab("")
        self._tab_bar.addTab("")
        self._tab_bar.addTab("")
        self._tab_bar.currentChanged.connect(self._refresh_list)
        root.addWidget(self._tab_bar)

        self._table = QTableWidget(self)
        self._table.setColumnCount(5)
        self._table.setMinimumHeight(260)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setSortingEnabled(False)
        self._table.setShowGrid(True)
        self._table.verticalHeader().setVisible(False)
        self._table.itemDoubleClicked.connect(lambda _it: self._on_accept())
        root.addWidget(self._table, 1)

        row_rf = QHBoxLayout()
        self._btn_refresh = QToolButton(self)
        self._btn_refresh.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        ic = self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload)
        if not ic.isNull():
            self._btn_refresh.setIcon(ic)
        self._btn_refresh.clicked.connect(self._refresh_list)
        row_rf.addWidget(self._btn_refresh)
        row_rf.addStretch()
        root.addLayout(row_rf)

        form = QFormLayout()
        self._edit_base = QLineEdit()
        self._edit_base.setPlaceholderText("0x400000")
        self._lbl_base = QLabel("")
        form.addRow(self._lbl_base, self._edit_base)
        self._chk_rel_image = QCheckBox()
        self._chk_rel_image.setChecked(
            self._settings.value("open_process/start_relative_image", False, type=bool)
        )
        form.addRow(self._chk_rel_image)
        root.addLayout(form)

        self._btn_attach = QPushButton("")
        self._btn_attach.setEnabled(False)
        self._btn_network = QPushButton("")
        self._btn_network.setEnabled(False)
        root.addWidget(self._btn_attach)
        root.addWidget(self._btn_network)

        bb = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        bb.accepted.connect(self._on_accept)
        bb.rejected.connect(self.reject)
        root.addWidget(bb)

        self._auto_timer = QTimer(self)
        self._auto_timer.setInterval(10_000)
        self._auto_timer.timeout.connect(self._refresh_list)

        if not win_memory.is_windows():
            self._btn_refresh.setEnabled(False)
        self._apply_retranslate()

    def showEvent(self, event) -> None:  # noqa: ANN001
        super().showEvent(event)
        if win_memory.is_windows():
            self._auto_timer.start()
            # 先显示窗口再填充表格，避免打开对话框时主线程长时间阻塞
            QTimer.singleShot(0, self._refresh_list)

    def hideEvent(self, event) -> None:  # noqa: ANN001
        self._auto_timer.stop()
        super().hideEvent(event)

    def _default_icon(self) -> QIcon:
        if self._default_file_icon is None:
            self._default_file_icon = self.style().standardIcon(
                QStyle.StandardPixmap.SP_FileIcon
            )
        return self._default_file_icon

    def _load_icons_chunk(self) -> None:
        """分批设置 exe 图标，避免单次 SHGetFileInfo 过多导致卡顿。"""
        chunk = 48
        end = min(self._icon_chunk_start + chunk, self._table.rowCount())
        for r in range(self._icon_chunk_start, end):
            it = self._table.item(r, 2)
            if not it:
                continue
            path = it.data(self._ROLE_EXE_PATH)
            if path:
                it.setIcon(self._icon_for_path(str(path)))
        self._icon_chunk_start = end
        if self._icon_chunk_start < self._table.rowCount():
            QTimer.singleShot(12, self._load_icons_chunk)

    def _icon_for_path(self, path: str) -> QIcon:
        if not path:
            ic = self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon)
            return ic
        if path in self._icon_cache:
            return self._icon_cache[path]
        h = win_process_list.get_exe_small_icon_handle(path)
        if h:
            try:
                from PySide6.QtGui import QImage, QPixmap

                qimg = QImage.fromHICON(h)
                pm = QPixmap.fromImage(qimg)
                if not pm.isNull():
                    ic = QIcon(pm)
                    self._icon_cache[path] = ic
                    win_process_list.destroy_icon_handle(h)
                    return ic
            except (AttributeError, TypeError, RuntimeError):
                win_process_list.destroy_icon_handle(h)
        ic = self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon)
        self._icon_cache[path] = ic
        return ic

    def _set_row_item(
        self,
        row: int,
        col: int,
        text: str,
        *,
        icon: QIcon | None = None,
        user_data: tuple | None = None,
    ) -> None:
        it = QTableWidgetItem(text)
        it.setFlags(
            Qt.ItemFlag.ItemIsSelectable
            | Qt.ItemFlag.ItemIsEnabled
        )
        if icon is not None and not icon.isNull():
            it.setIcon(icon)
        if user_data:
            pid, hwnd = user_data
            it.setData(self._ROLE_PID, pid)
            it.setData(self._ROLE_HWND, hwnd)
        self._table.setItem(row, col, it)

    def _refresh_list(self) -> None:
        self._table.setRowCount(0)
        if not win_memory.is_windows():
            return
        prev_cpu = self._prev_proc_times
        prev_sys = self._prev_sys_snap
        idx = self._tab_bar.currentIndex()
        try:
            self._table.setUpdatesEnabled(False)
            cur_sys = win_process_list.get_system_times_100ns()
            if cur_sys is None:
                cur_sys = (0, 0, 0)
            total_phys = win_process_list.get_physical_total_bytes()

            if idx == 0:
                rows_spec: list = list(win_process_list.list_application_processes())
            elif idx == 1:
                rows_spec = list(win_process_list.list_processes())
            else:
                rows_spec = list(win_process_list.list_windows())

            snap_cache: dict[int, tuple[int | None, str | None, int | None, int | None]] = {}

            def _snap(pid: int) -> tuple[int | None, str | None, int | None, int | None]:
                if pid not in snap_cache:
                    snap_cache[pid] = win_process_list.get_process_row_snapshot(pid)
                return snap_cache[pid]

            new_proc_times: dict[int, int] = {}

            r = 0
            dfi = self._default_icon()
            if idx == 2:
                for pid, hwnd, title in rows_spec:
                    base, path, ws, pt = _snap(pid)
                    if pid not in new_proc_times and pt is not None:
                        new_proc_times[pid] = pt
                    mem_pct = (
                        (100.0 * ws / total_phys)
                        if (total_phys and ws)
                        else 0.0
                    )
                    cpu_str = tr("process_list.cpu_na")
                    if (
                        prev_cpu is not None
                        and prev_sys is not None
                        and pid in prev_cpu
                        and pid in new_proc_times
                    ):
                        pc = win_process_list.cpu_percent_between_samples(
                            prev_cpu[pid],
                            new_proc_times[pid],
                            prev_sys,
                            cur_sys,
                        )
                        cpu_str = f"{pc:.1f}%"

                    self._table.insertRow(r)
                    ud = (pid, hwnd)
                    self._set_row_item(r, 0, str(pid), user_data=ud)
                    it0 = self._table.item(r, 0)
                    if it0 is not None and base is not None:
                        it0.setData(self._ROLE_IMAGE_BASE, base)
                    self._set_row_item(r, 1, f"{hwnd:08X}")
                    self._set_row_item(r, 2, title, icon=dfi, user_data=ud)
                    it2 = self._table.item(r, 2)
                    if it2 is not None:
                        it2.setData(self._ROLE_EXE_PATH, path or "")
                        if base is not None:
                            it2.setData(self._ROLE_IMAGE_BASE, base)
                    self._set_row_item(r, 3, cpu_str)
                    self._set_row_item(r, 4, f"{mem_pct:.1f}%")
                    for c in range(5):
                        item = self._table.item(r, c)
                        if item and c != 2:
                            item.setData(self._ROLE_PID, pid)
                            item.setData(self._ROLE_HWND, hwnd)
                    r += 1
            else:
                for pid, name in rows_spec:
                    base, path, ws, pt = _snap(pid)
                    if pid not in new_proc_times and pt is not None:
                        new_proc_times[pid] = pt
                    mem_pct = (
                        (100.0 * ws / total_phys)
                        if (total_phys and ws)
                        else 0.0
                    )
                    cpu_str = tr("process_list.cpu_na")
                    if (
                        prev_cpu is not None
                        and prev_sys is not None
                        and pid in prev_cpu
                        and pid in new_proc_times
                    ):
                        pc = win_process_list.cpu_percent_between_samples(
                            prev_cpu[pid],
                            new_proc_times[pid],
                            prev_sys,
                            cur_sys,
                        )
                        cpu_str = f"{pc:.1f}%"

                    self._table.insertRow(r)
                    addr_s = f"{base:#x}" if base is not None else "—"
                    ud = (pid, None)
                    self._set_row_item(r, 0, str(pid), user_data=ud)
                    it0 = self._table.item(r, 0)
                    if it0 is not None and base is not None:
                        it0.setData(self._ROLE_IMAGE_BASE, base)
                    self._set_row_item(r, 1, addr_s)
                    self._set_row_item(r, 2, name, icon=dfi, user_data=ud)
                    it2 = self._table.item(r, 2)
                    if it2 is not None:
                        it2.setData(self._ROLE_EXE_PATH, path or "")
                        if base is not None:
                            it2.setData(self._ROLE_IMAGE_BASE, base)
                    self._set_row_item(r, 3, cpu_str)
                    self._set_row_item(r, 4, f"{mem_pct:.1f}%")
                    for c in range(5):
                        item = self._table.item(r, c)
                        if item and c != 2:
                            item.setData(self._ROLE_PID, pid)
                            item.setData(self._ROLE_HWND, None)
                    r += 1

            self._prev_proc_times = new_proc_times
            self._prev_sys_snap = cur_sys
        except OSError as e:
            QMessageBox.warning(self, tr("open_process.title"), str(e))
        finally:
            self._table.setUpdatesEnabled(True)
        self._icon_chunk_start = 0
        if self._table.rowCount() > 0:
            QTimer.singleShot(0, self._load_icons_chunk)

    def _on_accept(self) -> None:
        row = self._table.currentRow()
        if row < 0:
            QMessageBox.information(
                self, tr("open_process.title"), tr("process_list.pick_process")
            )
            return
        it = self._table.item(row, 0)
        if it is None:
            QMessageBox.information(
                self, tr("open_process.title"), tr("process_list.pick_process")
            )
            return
        pid = it.data(self._ROLE_PID)
        if pid is None:
            QMessageBox.information(
                self, tr("open_process.title"), tr("process_list.pick_process")
            )
            return
        base_s = self._edit_base.text().strip()
        if base_s:
            try:
                int(base_s, 0)
            except ValueError:
                QMessageBox.warning(
                    self, tr("open_process.title"), tr("open_process.bad_base")
                )
                return
        if base_s and self._chk_rel_image.isChecked():
            img = self._image_base_for_row(row, int(pid))
            if img is None:
                QMessageBox.warning(
                    self, tr("open_process.title"), tr("open_process.need_image_base")
                )
                return
        self._settings.setValue(
            "open_process/start_relative_image", self._chk_rel_image.isChecked()
        )
        self.accept()

    def _apply_retranslate(self) -> None:
        self.setWindowTitle(tr("open_process.title"))
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint
        )
        self._warn.setText(tr("open_process.warning"))
        self._tab_bar.setTabText(0, tr("process_list.tab_apps"))
        self._tab_bar.setTabText(1, tr("process_list.tab_processes"))
        self._tab_bar.setTabText(2, tr("process_list.tab_windows"))
        self._btn_refresh.setText(tr("process_list.refresh"))
        self._lbl_base.setText(tr("open_process.base"))
        self._chk_rel_image.setText(tr("open_process.start_relative_image"))
        self._btn_attach.setText(tr("process_list.attach_debugger"))
        self._btn_network.setText(tr("process_list.network"))
        self._btn_attach.setToolTip(tr("process_list.not_implemented"))
        self._btn_network.setToolTip(tr("process_list.not_implemented"))
        self._table.setHorizontalHeaderLabels(
            [
                tr("process_list.col_pid"),
                tr("process_list.col_addr"),
                tr("process_list.col_name"),
                tr("process_list.col_cpu"),
                tr("process_list.col_mem"),
            ]
        )
        hh = self._table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)

    def retranslate_ui(self) -> None:
        self._apply_retranslate()

    def _image_base_for_row(self, row: int, pid: int) -> int | None:
        for col in (0, 2):
            it = self._table.item(row, col)
            if it is None:
                continue
            v = it.data(self._ROLE_IMAGE_BASE)
            if isinstance(v, int):
                return v
        b, _p, _ws, _pt = win_process_list.get_process_row_snapshot(pid)
        return b

    def values(self) -> tuple[int, int]:
        """pid, 起始虚拟地址 VA。勾选「相对映像基址」时 VA = 映像基址 + 输入值；否则输入值为完整 VA。"""
        row = self._table.currentRow()
        if row < 0:
            raise ValueError("no selection")
        it = self._table.item(row, 0)
        if it is None:
            raise ValueError("no selection")
        pid = int(it.data(self._ROLE_PID))
        img = self._image_base_for_row(row, pid)
        base_s = self._edit_base.text().strip()
        if base_s:
            parsed = int(base_s, 0)
            if self._chk_rel_image.isChecked():
                if img is None:
                    raise ValueError("no image base")
                user_va = img + parsed
            else:
                user_va = parsed
        else:
            user_va = img if img is not None else 0
        return pid, user_va


OpenProcessDialog = ProcessListDialog
