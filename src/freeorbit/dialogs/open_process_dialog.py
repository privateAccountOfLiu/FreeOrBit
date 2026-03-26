"""打开进程内存片段（仅 Windows）。"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from freeorbit.i18n import tr


class OpenProcessDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumWidth(420)
        root = QVBoxLayout(self)
        w0 = QLabel(tr("open_process.warning"))
        w0.setWordWrap(True)
        root.addWidget(w0)
        form = QFormLayout()
        self._spin_pid = QSpinBox()
        self._spin_pid.setRange(1, 2**31 - 1)
        self._edit_base = QLineEdit()
        self._edit_base.setPlaceholderText("0x400000")
        self._spin_size = QSpinBox()
        self._spin_size.setRange(1, 64 * 1024 * 1024)
        self._spin_size.setValue(4096)
        form.addRow(tr("open_process.pid"), self._spin_pid)
        form.addRow(tr("open_process.base"), self._edit_base)
        form.addRow(tr("open_process.size"), self._spin_size)
        root.addLayout(form)
        bb = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        root.addWidget(bb)
        self._apply_retranslate()

    def _apply_retranslate(self) -> None:
        self.setWindowTitle(tr("open_process.title"))
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint
        )

    def retranslate_ui(self) -> None:
        self._apply_retranslate()

    def values(self) -> tuple[int, int, int]:
        pid = self._spin_pid.value()
        base_s = self._edit_base.text().strip() or "0"
        base = int(base_s, 0)
        size = self._spin_size.value()
        return pid, base, size
