"""填充与字节运算停靠面板。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDockWidget,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from freeorbit.commands.edit_commands import ModifyBytesCommand
from freeorbit.i18n import tr

if TYPE_CHECKING:
    from freeorbit.viewmodel.document_editor import DocumentEditor


def _parse_int(s: str) -> int:
    t = s.strip()
    if not t:
        raise ValueError("empty")
    return int(t, 0)


def _effective_byte_range(
    doc: DocumentEditor,
    *,
    use_selection: bool,
    start_text: str,
    end_text: str,
) -> tuple[int, int] | None:
    """返回 [lo, hi) 半开区间；无效时 None。"""
    m = doc.model()
    n = len(m)
    if n == 0:
        return None
    hv = doc.hex_view()
    if use_selection:
        lo, hi = hv.selection_range()
        if lo == hi:
            p = hv.cursor_position()
            lo, hi = p, p + 1
        if lo >= hi:
            return None
    else:
        try:
            lo = _parse_int(start_text)
            hi = _parse_int(end_text)
        except ValueError:
            return None
        if lo < 0 or hi > n or lo >= hi:
            return None
    if lo < 0 or hi > n or lo >= hi:
        return None
    return (lo, hi)


class ByteToolsDock(QDockWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(tr("dock.byte_tools"), parent)
        self._doc: Optional[DocumentEditor] = None

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setWidget(scroll)

        inner = QWidget()
        scroll.setWidget(inner)
        inner.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.MinimumExpanding
        )
        root = QVBoxLayout(inner)
        root.setContentsMargins(6, 8, 6, 8)
        root.setSpacing(10)

        # —— 范围 ——
        self._grp_range = QGroupBox()
        lay_r = QVBoxLayout(self._grp_range)
        lay_r.setSpacing(8)
        self._radio_sel = QRadioButton()
        self._radio_manual = QRadioButton()
        self._radio_sel.setChecked(True)
        lay_r.addWidget(self._radio_sel)
        lay_r.addWidget(self._radio_manual)

        grid_off = QGridLayout()
        grid_off.setHorizontalSpacing(8)
        grid_off.setVerticalSpacing(6)
        self._lbl_start = QLabel()
        self._edit_start = QLineEdit()
        self._edit_start.setPlaceholderText("0x0")
        self._edit_start.setMinimumWidth(100)
        self._lbl_end = QLabel()
        self._edit_end = QLineEdit()
        self._edit_end.setPlaceholderText("0x100")
        self._edit_end.setMinimumWidth(100)
        grid_off.addWidget(self._lbl_start, 0, 0, Qt.AlignmentFlag.AlignRight)
        grid_off.addWidget(self._edit_start, 0, 1)
        grid_off.addWidget(self._lbl_end, 1, 0, Qt.AlignmentFlag.AlignRight)
        grid_off.addWidget(self._edit_end, 1, 1)
        grid_off.setColumnStretch(1, 1)
        lay_r.addLayout(grid_off)

        self._radio_sel.toggled.connect(self._toggle_manual)
        self._radio_manual.toggled.connect(self._toggle_manual)
        root.addWidget(self._grp_range)

        # —— 填充 ——
        self._grp_fill = QGroupBox()
        lay_f = QVBoxLayout(self._grp_fill)
        lay_f.setSpacing(8)
        self._lb_fill_mode = QLabel()
        self._combo_fill = QComboBox()
        self._combo_fill.setMinimumHeight(26)
        self._combo_fill.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        row_mode = QHBoxLayout()
        row_mode.addWidget(self._lb_fill_mode)
        row_mode.addWidget(self._combo_fill, 1)
        lay_f.addLayout(row_mode)

        self._lb_fill_val = QLabel()
        self._spin_fill = QSpinBox()
        self._spin_fill.setRange(0, 255)
        self._spin_fill.setMinimumHeight(26)
        self._spin_fill.setMinimumWidth(80)
        row_val = QHBoxLayout()
        row_val.addWidget(self._lb_fill_val)
        row_val.addWidget(self._spin_fill)
        row_val.addStretch(1)
        lay_f.addLayout(row_val)

        self._btn_fill = QPushButton()
        self._btn_fill.setMinimumHeight(28)
        self._btn_fill.clicked.connect(self._do_fill)
        lay_f.addWidget(self._btn_fill)
        root.addWidget(self._grp_fill)

        # —— 字节运算 ——
        self._grp_op = QGroupBox()
        lay_o = QVBoxLayout(self._grp_op)
        lay_o.setSpacing(8)

        self._lb_xor = QLabel()
        self._edit_xor = QLineEdit()
        self._edit_xor.setPlaceholderText("FF")
        self._edit_xor.setMinimumHeight(26)
        self._btn_xor = QPushButton()
        self._btn_xor.setMinimumWidth(88)
        self._btn_xor.clicked.connect(lambda: self._do_binop("xor"))
        lay_o.addLayout(self._make_op_row(self._lb_xor, self._edit_xor, self._btn_xor))

        self._lb_and = QLabel()
        self._edit_and = QLineEdit()
        self._edit_and.setPlaceholderText("FF")
        self._edit_and.setMinimumHeight(26)
        self._btn_and = QPushButton()
        self._btn_and.setMinimumWidth(88)
        self._btn_and.clicked.connect(lambda: self._do_binop("and"))
        lay_o.addLayout(self._make_op_row(self._lb_and, self._edit_and, self._btn_and))

        self._lb_or = QLabel()
        self._edit_or = QLineEdit()
        self._edit_or.setPlaceholderText("FF")
        self._edit_or.setMinimumHeight(26)
        self._btn_or = QPushButton()
        self._btn_or.setMinimumWidth(88)
        self._btn_or.clicked.connect(lambda: self._do_binop("or"))
        lay_o.addLayout(self._make_op_row(self._lb_or, self._edit_or, self._btn_or))

        self._btn_not = QPushButton()
        self._btn_not.setMinimumHeight(28)
        self._btn_not.clicked.connect(self._do_not)
        lay_o.addWidget(self._btn_not)

        self._btn_rol = QPushButton()
        self._btn_rol.setMinimumHeight(28)
        self._btn_rol.clicked.connect(self._do_rol)
        lay_o.addWidget(self._btn_rol)

        self._btn_swap16 = QPushButton()
        self._btn_swap16.setMinimumHeight(28)
        self._btn_swap16.clicked.connect(lambda: self._do_swap(2))
        lay_o.addWidget(self._btn_swap16)

        self._btn_swap32 = QPushButton()
        self._btn_swap32.setMinimumHeight(28)
        self._btn_swap32.clicked.connect(lambda: self._do_swap(4))
        lay_o.addWidget(self._btn_swap32)

        root.addWidget(self._grp_op)

        self._toggle_manual()
        self.retranslate_ui()

    @staticmethod
    def _make_op_row(lbl: QLabel, edit: QLineEdit, btn: QPushButton) -> QHBoxLayout:
        h = QHBoxLayout()
        h.setSpacing(6)
        lbl.setMinimumWidth(52)
        lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        h.addWidget(lbl, 0)
        h.addWidget(edit, 1)
        h.addWidget(btn, 0)
        return h

    def _toggle_manual(self) -> None:
        manual = self._radio_manual.isChecked()
        self._edit_start.setEnabled(manual)
        self._edit_end.setEnabled(manual)

    def bind_document(self, doc: DocumentEditor) -> None:
        self._doc = doc

    def retranslate_ui(self) -> None:
        self.setWindowTitle(tr("dock.byte_tools"))
        self._grp_range.setTitle(tr("byte_tools.grp_range"))
        self._grp_fill.setTitle(tr("byte_tools.grp_fill"))
        self._grp_op.setTitle(tr("byte_tools.grp_ops"))
        self._radio_sel.setText(tr("byte_tools.use_selection"))
        self._radio_manual.setText(tr("byte_tools.manual_range"))
        self._lbl_start.setText(tr("byte_tools.start"))
        self._lbl_end.setText(tr("byte_tools.end"))
        self._lb_fill_mode.setText(tr("byte_tools.fill_mode"))
        self._lb_fill_val.setText(tr("byte_tools.fill_value"))
        self._btn_fill.setText(tr("byte_tools.apply_fill"))
        self._lb_xor.setText(tr("byte_tools.op_xor"))
        self._btn_xor.setText(tr("byte_tools.apply_xor"))
        self._lb_and.setText(tr("byte_tools.op_and"))
        self._btn_and.setText(tr("byte_tools.apply_and"))
        self._lb_or.setText(tr("byte_tools.op_or"))
        self._btn_or.setText(tr("byte_tools.apply_or"))
        self._btn_not.setText(tr("byte_tools.apply_not"))
        self._btn_rol.setText(tr("byte_tools.apply_rol"))
        self._btn_swap16.setText(tr("byte_tools.swap16"))
        self._btn_swap32.setText(tr("byte_tools.swap32"))
        cur = self._combo_fill.currentData()
        self._combo_fill.clear()
        self._combo_fill.addItem(tr("byte_tools.fill_const"), "const")
        self._combo_fill.addItem(tr("byte_tools.fill_inc"), "inc")
        self._combo_fill.addItem(tr("byte_tools.fill_dec"), "dec")
        ix = self._combo_fill.findData(cur if cur else "const")
        self._combo_fill.setCurrentIndex(max(0, ix))

    def _range(self) -> tuple[int, int] | None:
        if self._doc is None:
            return None
        return _effective_byte_range(
            self._doc,
            use_selection=self._radio_sel.isChecked(),
            start_text=self._edit_start.text(),
            end_text=self._edit_end.text(),
        )

    def _warn_range(self) -> tuple[int, int] | None:
        r = self._range()
        if r is None:
            QMessageBox.warning(self, tr("byte_tools.warn_title"), tr("byte_tools.bad_range"))
        return r

    def _do_fill(self) -> None:
        r = self._warn_range()
        if r is None or self._doc is None:
            return
        lo, hi = r
        mode = self._combo_fill.currentData()
        v0 = self._spin_fill.value()
        length = hi - lo
        if mode == "const":
            new = bytes([v0 & 0xFF]) * length
        elif mode == "inc":
            new = bytes((v0 + i) & 0xFF for i in range(length))
        else:
            new = bytes((v0 - i) & 0xFF for i in range(length))
        self._apply_replace(lo, new)

    def _parse_byte_hex(self, text: str) -> int:
        t = text.strip().replace("0x", "").replace(" ", "")
        if not t:
            raise ValueError("empty")
        return int(t, 16) & 0xFF

    def _do_binop(self, kind: str) -> None:
        r = self._warn_range()
        if r is None or self._doc is None:
            return
        lo, hi = r
        edits = {"xor": self._edit_xor, "and": self._edit_and, "or": self._edit_or}
        try:
            k = self._parse_byte_hex(edits[kind].text())
        except ValueError:
            QMessageBox.warning(self, tr("byte_tools.warn_title"), tr("byte_tools.bad_byte"))
            return
        m = self._doc.model()
        old = m.read(lo, hi - lo)
        if kind == "xor":
            new = bytes(b ^ k for b in old)
        elif kind == "and":
            new = bytes(b & k for b in old)
        else:
            new = bytes(b | k for b in old)
        self._apply_replace(lo, new)

    def _do_not(self) -> None:
        r = self._warn_range()
        if r is None or self._doc is None:
            return
        lo, hi = r
        m = self._doc.model()
        old = m.read(lo, hi - lo)
        new = bytes((~b) & 0xFF for b in old)
        self._apply_replace(lo, new)

    def _do_rol(self) -> None:
        r = self._warn_range()
        if r is None or self._doc is None:
            return
        lo, hi = r
        m = self._doc.model()
        old = m.read(lo, hi - lo)
        new = bytes((((b << 1) | (b >> 7)) & 0xFF) for b in old)
        self._apply_replace(lo, new)

    def _do_swap(self, width: int) -> None:
        r = self._warn_range()
        if r is None or self._doc is None:
            return
        lo, hi = r
        m = self._doc.model()
        buf = bytearray(m.read(lo, hi - lo))
        n = len(buf)
        i = 0
        while i + width <= n:
            sl = slice(i, i + width)
            buf[sl] = buf[sl][::-1]
            i += width
        self._apply_replace(lo, bytes(buf))

    def _apply_replace(self, offset: int, new: bytes) -> None:
        if self._doc is None:
            return
        m = self._doc.model()
        try:
            m.ensure_mutable_copy()
        except OSError as e:
            QMessageBox.warning(self, tr("byte_tools.warn_title"), str(e))
            return
        old = m.read(offset, len(new))
        if len(old) != len(new):
            return
        cmd = ModifyBytesCommand(m, offset, old, new)
        self._doc.undo_stack().push(cmd)
        self._doc.hex_view().update_view()
