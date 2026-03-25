"""校验和与哈希对话框。"""

from __future__ import annotations

import hashlib
import zlib
from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
)

if TYPE_CHECKING:
    from freeorbit.model.binary_data_model import BinaryDataModel


def _crc32(data: bytes) -> str:
    return f"{zlib.crc32(data) & 0xFFFFFFFF:08X}"


def _adler32(data: bytes) -> str:
    return f"{zlib.adler32(data) & 0xFFFFFFFF:08X}"


_ALGORITHMS = {
    "MD5": lambda d: hashlib.md5(d).hexdigest().upper(),
    "SHA-1": lambda d: hashlib.sha1(d).hexdigest().upper(),
    "SHA-256": lambda d: hashlib.sha256(d).hexdigest().upper(),
    "SHA-512": lambda d: hashlib.sha512(d).hexdigest().upper(),
    "CRC32": _crc32,
    "Adler-32": _adler32,
}


class ChecksumDialog(QDialog):
    def __init__(self, model: BinaryDataModel, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("校验和 / 哈希")
        self._model = model
        data = model.read(0, len(model))

        self._combo = QComboBox()
        self._combo.addItems(list(_ALGORITHMS.keys()))
        self._combo.currentTextChanged.connect(lambda _: self._update(data))
        self._out = QLineEdit()
        self._out.setReadOnly(True)

        form = QFormLayout()
        form.addRow("算法:", self._combo)
        form.addRow("结果:", self._out)

        box = QDialogButtonBox(QDialogButtonBox.Close)
        box.rejected.connect(self.reject)

        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(QLabel(f"数据长度: {len(data)} 字节"))
        lay.addWidget(box)

        self._update(data)

    def _update(self, data: bytes) -> None:
        name = self._combo.currentText()
        fn = _ALGORITHMS.get(name)
        if fn:
            self._out.setText(fn(data))
