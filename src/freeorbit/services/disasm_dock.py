"""基于 Capstone 的反汇编停靠面板（可选依赖）。

Capstone 解码在后台线程执行，主线程只做调度与表格填充，避免 Hex 编辑时界面卡死。
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, QTimer, Signal
from PySide6.QtGui import QFont, QFontMetrics
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDockWidget,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from freeorbit.i18n import tr

try:
    from capstone import (  # type: ignore[import-untyped]
        CS_ARCH_ARM,
        CS_ARCH_ARM64,
        CS_ARCH_MIPS,
        CS_ARCH_RISCV,
        CS_ARCH_X86,
        CS_MODE_32,
        CS_MODE_64,
        CS_MODE_ARM,
        CS_MODE_LITTLE_ENDIAN,
        CS_MODE_MIPS32,
        CS_MODE_RISCV64,
        CS_MODE_THUMB,
        Cs,
    )

    _CAPSTONE_OK = True
except ImportError:  # pragma: no cover - 可选依赖
    _CAPSTONE_OK = False
    Cs = None  # type: ignore[misc, assignment]

if TYPE_CHECKING:
    from freeorbit.viewmodel.document_editor import DocumentEditor


def _arch_choices() -> list[tuple[str, int, int]]:
    """(标签, capstone arch, capstone mode)。"""
    if not _CAPSTONE_OK:
        return []
    return [
        ("x86-64", CS_ARCH_X86, CS_MODE_64),
        ("x86-32", CS_ARCH_X86, CS_MODE_32),
        ("ARM64", CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN),
        ("ARM-32", CS_ARCH_ARM, CS_MODE_ARM),
        ("Thumb", CS_ARCH_ARM, CS_MODE_THUMB),
        ("MIPS32 (LE)", CS_ARCH_MIPS, CS_MODE_MIPS32 | CS_MODE_LITTLE_ENDIAN),
        ("RISC-V 64", CS_ARCH_RISCV, CS_MODE_RISCV64),
    ]


# 主线程表格行数上限：数千行 QTableWidgetItem 会显著阻塞事件循环
_MAX_DISPLAY_ROWS = 1200


class DisasmWorkerSignals(QObject):
    """后台任务与主线程通信（单例连接，避免重复 connect）。"""

    finished = Signal(int, list)  # seq, list[tuple[str,str,str,str]]
    error = Signal(int, str)  # seq, message


class _DisasmTask(QRunnable):
    """在工作线程中运行 Capstone，不向主线程传递 CsInsn 对象。"""

    def __init__(
        self,
        seq: int,
        data: bytes,
        arch: int,
        mode: int,
        start_addr: int,
        signals: DisasmWorkerSignals,
    ) -> None:
        super().__init__()
        self._seq = seq
        self._data = data
        self._arch = arch
        self._mode = mode
        self._start = start_addr
        self._signals = signals

    def run(self) -> None:
        if not _CAPSTONE_OK:
            return
        try:
            md = Cs(self._arch, self._mode)
            md.detail = False
            rows: list[tuple[str, str, str, str]] = []
            for insn in md.disasm(self._data, self._start):
                raw = bytes(insn.bytes)
                hex_spaced = " ".join(f"{b:02X}" for b in raw)
                rows.append(
                    (
                        f"{insn.address:08X}",
                        hex_spaced,
                        insn.mnemonic or "",
                        insn.op_str or "",
                    )
                )
                if len(rows) >= _MAX_DISPLAY_ROWS:
                    break
            self._signals.finished.emit(self._seq, rows)
        except Exception as e:  # noqa: BLE001
            self._signals.error.emit(self._seq, str(e))


class DisasmDock(QDockWidget):
    """从光标或选区取字节并反汇编（长度上限约 4KB）。"""

    _MAX_BYTES = 4096
    _REFRESH_DEBOUNCE_MS = 56
    _REFRESH_DEBOUNCE_DATA_MS = 180

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(tr("dock.disasm"), parent)
        self._doc: Optional[DocumentEditor] = None
        self._last_disasm_cache_key: object | None = None
        self._last_row_count_for_resize = -1
        self._disasm_seq = 0
        self._pool = QThreadPool.globalInstance()
        self._worker_signals = DisasmWorkerSignals(self)
        self._worker_signals.finished.connect(self._on_worker_finished)
        self._worker_signals.error.connect(self._on_worker_error)

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(self._REFRESH_DEBOUNCE_MS)
        self._debounce.timeout.connect(lambda: self._refresh_impl(force=False))
        self._debounce_data = QTimer(self)
        self._debounce_data.setSingleShot(True)
        self._debounce_data.setInterval(self._REFRESH_DEBOUNCE_DATA_MS)
        self._debounce_data.timeout.connect(lambda: self._refresh_impl(force=False))

        w = QWidget()
        self.setWidget(w)
        lay = QVBoxLayout(w)
        lay.setContentsMargins(4, 4, 4, 4)

        top = QHBoxLayout()
        self._lbl_arch = QLabel()
        self._combo = QComboBox()
        self._combo.blockSignals(True)
        for label, arch, mode in _arch_choices():
            self._combo.addItem(label, (arch, mode))
        self._combo.blockSignals(False)
        self._combo.currentIndexChanged.connect(self._schedule_refresh)
        self._btn = QPushButton()
        self._btn.clicked.connect(lambda: self._refresh_impl(force=True))
        self._btn_export = QPushButton()
        self._btn_export.clicked.connect(self._export_asm_file)
        top.addWidget(self._lbl_arch)
        top.addWidget(self._combo, 1)
        top.addWidget(self._btn)
        top.addWidget(self._btn_export)
        lay.addLayout(top)

        self._stack = QStackedWidget()
        self._table = QTableWidget()
        self._table.setColumnCount(4)
        self._table.setAlternatingRowColors(True)
        self._table.setShowGrid(False)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.horizontalHeader().setDefaultAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        mono = QFont("Consolas", 10)
        if not mono.exactMatch():
            mono = QFont("Courier New", 10)
        self._table.setFont(mono)
        self._table.horizontalHeader().setFont(mono)
        self._apply_table_headers()

        self._lbl_no_capstone = QLabel()
        self._lbl_no_capstone.setWordWrap(True)
        self._lbl_no_capstone.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        )

        self._stack.addWidget(self._table)
        self._stack.addWidget(self._lbl_no_capstone)
        self._stack.setCurrentIndex(0 if _CAPSTONE_OK else 1)
        if not _CAPSTONE_OK:
            self._lbl_no_capstone.setText(tr("disasm.no_capstone"))

        self._table.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        lay.addWidget(self._stack, 1)

        self._hint = QLabel()
        self._hint.setWordWrap(True)
        lay.addWidget(self._hint)

        self._apply_retranslate()
        self.visibilityChanged.connect(self._on_dock_visibility_changed)

    def _apply_default_column_widths(self) -> None:
        """避免依赖 resizeColumnToContents 全表测量（主线程昂贵）。"""
        fm = QFontMetrics(self._table.font())
        self._table.setColumnWidth(0, max(88, fm.horizontalAdvance("00000000") + 16))
        self._table.setColumnWidth(1, max(200, fm.horizontalAdvance("00 " * 24)))
        self._table.setColumnWidth(2, max(100, fm.horizontalAdvance("xmm0") + 16))

    def _on_dock_visibility_changed(self, visible: bool) -> None:
        if visible and _CAPSTONE_OK and self._doc is not None:
            self._last_disasm_cache_key = None
            self._schedule_refresh()

    def _apply_table_headers(self) -> None:
        self._table.setHorizontalHeaderLabels(
            [
                tr("disasm.col_addr"),
                tr("disasm.col_bytes"),
                tr("disasm.col_mnemonic"),
                tr("disasm.col_ops"),
            ]
        )
        hdr = self._table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)

    def _apply_retranslate(self) -> None:
        self.setWindowTitle(tr("dock.disasm"))
        self._lbl_arch.setText(tr("disasm.arch"))
        self._btn.setText(tr("disasm.refresh"))
        self._btn_export.setText(tr("disasm.export"))
        self._hint.setText(tr("disasm.hint"))
        self._apply_table_headers()
        self._apply_default_column_widths()
        if not _CAPSTONE_OK:
            self._lbl_no_capstone.setText(tr("disasm.no_capstone"))

    def retranslate_ui(self) -> None:
        self._last_disasm_cache_key = None
        self._apply_retranslate()
        if _CAPSTONE_OK and self._doc is not None:
            self._refresh_impl(force=True)

    def bind_document(self, doc: Optional[DocumentEditor]) -> None:
        self._debounce.stop()
        self._debounce_data.stop()
        self._disasm_seq += 1
        self._last_disasm_cache_key = None
        self._last_row_count_for_resize = -1
        if self._doc is not None:
            hv = self._doc.hex_view()
            try:
                hv.cursor_moved.disconnect(self._schedule_refresh)
            except TypeError:
                pass
            try:
                hv.selection_changed.disconnect(self._schedule_refresh)
            except TypeError:
                pass
            try:
                self._doc.model().data_changed.disconnect(self._on_model_data_changed)
            except TypeError:
                pass
        self._doc = doc
        if doc is not None:
            hv = doc.hex_view()
            hv.cursor_moved.connect(self._schedule_refresh)
            hv.selection_changed.connect(self._schedule_refresh)
            doc.model().data_changed.connect(self._on_model_data_changed)
        self._schedule_refresh()

    def _schedule_refresh(self, *_args: object) -> None:
        self._debounce.start()

    def _on_model_data_changed(self, *_args: object) -> None:
        if not self.isVisible():
            self._last_disasm_cache_key = None
            return
        self._debounce_data.start()

    def _is_message_only_table(self) -> bool:
        if self._table.rowCount() != 1:
            return False
        return self._table.columnSpan(0, 0) >= 4

    def _export_asm_file(self) -> None:
        if not _CAPSTONE_OK:
            QMessageBox.information(
                self, tr("dock.disasm"), tr("disasm.no_capstone")
            )
            return
        if self._stack.currentIndex() != 0:
            QMessageBox.information(
                self, tr("disasm.export_title"), tr("disasm.export_nothing")
            )
            return
        if self._table.rowCount() == 0 or self._is_message_only_table():
            QMessageBox.information(
                self, tr("disasm.export_title"), tr("disasm.export_nothing")
            )
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            tr("disasm.export_dlg"),
            "",
            tr("disasm.export_filter"),
        )
        if not path:
            return
        arch_label = self._combo.currentText()
        lines: list[str] = [
            "# FreeOrBit disassembly",
            f"# {tr('disasm.arch')}: {arch_label}",
            "",
            "\t".join(
                [
                    tr("disasm.col_addr"),
                    tr("disasm.col_bytes"),
                    tr("disasm.col_mnemonic"),
                    tr("disasm.col_ops"),
                ]
            ),
        ]
        for r in range(self._table.rowCount()):
            row_cells: list[str] = []
            for c in range(4):
                it = self._table.item(r, c)
                row_cells.append(it.text() if it is not None else "")
            lines.append("\t".join(row_cells))
        body = "\n".join(lines) + "\n"
        try:
            Path(path).write_text(body, encoding="utf-8", newline="\n")
        except OSError as e:
            QMessageBox.warning(self, tr("disasm.export_fail"), str(e))
            return
        QMessageBox.information(self, tr("disasm.export_title"), tr("disasm.export_ok"))

    def _set_message_row(self, text: str) -> None:
        self._last_disasm_cache_key = None
        self._last_row_count_for_resize = -1
        self._table.setRowCount(0)
        self._table.setRowCount(1)
        it = QTableWidgetItem(text)
        it.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        self._table.setItem(0, 0, it)
        self._table.setSpan(0, 0, 1, 4)

    def _on_worker_finished(self, seq: int, rows: list[Any]) -> None:
        if seq != self._disasm_seq or self._doc is None:
            return
        if not rows:
            self._set_message_row(tr("disasm.no_insn"))
            return
        self._fill_table_rows(rows)
        nrows = len(rows)
        if nrows != self._last_row_count_for_resize:
            self._last_row_count_for_resize = nrows
            self._apply_default_column_widths()

    def _on_worker_error(self, seq: int, message: str) -> None:
        if seq != self._disasm_seq or self._doc is None:
            return
        self._set_message_row(f"{tr('disasm.err_title')}: {message}")

    def _fill_table_rows(self, rows: list[tuple[str, str, str, str]]) -> None:
        addr_align = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        left_align = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        self._table.setUpdatesEnabled(False)
        try:
            self._table.clearSpans()
            self._table.setRowCount(len(rows))
            for row, (a_s, b_s, m_s, o_s) in enumerate(rows):
                a_it = QTableWidgetItem(a_s)
                a_it.setTextAlignment(addr_align)
                a_it.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                b_it = QTableWidgetItem(b_s)
                b_it.setTextAlignment(left_align)
                b_it.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                m_it = QTableWidgetItem(m_s)
                m_it.setTextAlignment(left_align)
                m_it.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                o_it = QTableWidgetItem(o_s)
                o_it.setTextAlignment(left_align)
                o_it.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                self._table.setItem(row, 0, a_it)
                self._table.setItem(row, 1, b_it)
                self._table.setItem(row, 2, m_it)
                self._table.setItem(row, 3, o_it)
        finally:
            self._table.setUpdatesEnabled(True)
        hdr = self._table.horizontalHeader()
        hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)

    def _refresh_impl(self, *, force: bool = False) -> None:
        if not _CAPSTONE_OK:
            self._stack.setCurrentIndex(1)
            return
        if not force and not self.isVisible():
            return
        self._stack.setCurrentIndex(0)

        doc = self._doc
        if doc is None:
            self._table.setRowCount(0)
            return
        m = doc.model()
        n = len(m)
        if n == 0:
            self._set_message_row(tr("disasm.empty"))
            return
        hv = doc.hex_view()
        a, b = hv.selection_range()
        if a != b:
            start = max(0, min(a, b))
            end = max(a, b)
        else:
            start = hv.cursor_position()
            end = min(n, start + self._MAX_BYTES)
        if start >= n:
            start = max(0, n - 1)
            end = n
        length = min(end - start, self._MAX_BYTES)
        if length <= 0:
            length = min(self._MAX_BYTES, n - start)
        data = m.read(start, length)
        if not data:
            self._set_message_row(tr("disasm.empty"))
            return
        arch_mode = self._combo.currentData()
        if arch_mode is None:
            return
        arch, mode = arch_mode
        arch_ix = self._combo.currentIndex()
        cache_key = (start, len(data), arch_ix, data)
        if cache_key == self._last_disasm_cache_key:
            return
        self._last_disasm_cache_key = cache_key

        self._disasm_seq += 1
        seq = self._disasm_seq
        task = _DisasmTask(
            seq,
            bytes(data),
            arch,
            mode,
            start,
            self._worker_signals,
        )
        self._pool.start(task)
