"""打开原始磁盘 / 卷设备的一段字节（需管理员权限）。"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from freeorbit.i18n import tr


class OpenDiskDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumWidth(460)
        root = QVBoxLayout(self)
        self._lbl_warn = QLabel(tr("open_disk.warning"))
        self._lbl_warn.setWordWrap(True)
        root.addWidget(self._lbl_warn)
        form = QFormLayout()
        self._edit_path = QLineEdit()
        self._edit_path.setText(r"\\.\PhysicalDrive0")
        # QSpinBox 最大约 2^31，大磁盘偏移改用文本输入（十进制或 0x 十六进制）
        self._edit_offset = QLineEdit()
        self._edit_offset.setText("0")
        self._spin_size = QSpinBox()
        self._spin_size.setRange(1, 64 * 1024 * 1024)
        self._spin_size.setValue(8192)
        form.addRow(tr("open_disk.path"), self._edit_path)
        form.addRow(tr("open_disk.offset"), self._edit_offset)
        form.addRow(tr("open_disk.size"), self._spin_size)
        root.addLayout(form)
        bb = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        bb.accepted.connect(self._on_accept)
        bb.rejected.connect(self.reject)
        root.addWidget(bb)
        self._apply_retranslate()

    def _apply_retranslate(self) -> None:
        self.setWindowTitle(tr("open_disk.title"))
        self._edit_offset.setPlaceholderText(tr("open_disk.offset_placeholder"))
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint
        )

    def _on_accept(self) -> None:
        r = QMessageBox.question(
            self,
            tr("open_disk.confirm_title"),
            tr("open_disk.confirm_body"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if r == QMessageBox.StandardButton.Yes:
            self.accept()

    def values(self) -> tuple[str, int, int]:
        path = self._edit_path.text().strip()
        off_s = self._edit_offset.text().strip() or "0"
        try:
            offset = int(off_s, 0)
        except ValueError as e:
            raise ValueError("bad_offset") from e
        if offset < 0:
            raise ValueError("bad_offset")
        return path, offset, self._spin_size.value()
