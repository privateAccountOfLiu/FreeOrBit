"""将选区按多种二进制类型解析（struct）。"""

from __future__ import annotations

import struct
from typing import TYPE_CHECKING, Callable

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from freeorbit.model.binary_data_model import BinaryDataModel
    from freeorbit.view.hex_editor_view import HexEditorView


def _has_float16() -> bool:
    try:
        struct.pack("<e", 1.0)
        return True
    except struct.error:
        return False


def _decode_utf8(data: bytes) -> str:
    return data.decode("utf-8", errors="replace")


def _decode_ascii(data: bytes) -> str:
    return data.decode("ascii", errors="replace")


def _decode_utf16le(data: bytes) -> str:
    return data.decode("utf-16-le", errors="replace")


def _decode_utf16be(data: bytes) -> str:
    return data.decode("utf-16-be", errors="replace")


def _unpack_repeat(fmt: str, data: bytes) -> str:
    size = struct.calcsize(fmt)
    if size == 0:
        return "无效格式"
    if len(data) == 0:
        return "（空选区）"
    if len(data) % size != 0:
        return (
            f"选区长度 {len(data)} 字节，不是该类型单元素大小 {size} 的整数倍，"
            f"末尾 {len(data) % size} 字节将被忽略。\n\n"
        ) + _unpack_repeat_truncate(fmt, data[: len(data) - (len(data) % size)])

    lines: list[str] = []
    for i in range(0, len(data), size):
        chunk = data[i : i + size]
        try:
            val = struct.unpack(fmt, chunk)[0]
            off = i
            lines.append(f"偏移 +0x{off:X} ({off}): {val!r}")
        except struct.error as e:
            lines.append(f"偏移 +0x{i:X}: 解析失败 {e}")
    return "\n".join(lines)


def _unpack_repeat_truncate(fmt: str, data: bytes) -> str:
    size = struct.calcsize(fmt)
    lines: list[str] = []
    for i in range(0, len(data), size):
        chunk = data[i : i + size]
        if len(chunk) < size:
            break
        val = struct.unpack(fmt, chunk)[0]
        lines.append(f"偏移 +0x{i:X} ({i}): {val!r}")
    return "\n".join(lines)


def _entries_ordered() -> list[tuple[str, Callable[[bytes], str]]]:
    out: list[tuple[str, Callable[[bytes], str]]] = [
        ("UTF-8 文本", _decode_utf8),
        ("ASCII 文本", _decode_ascii),
        ("UTF-16 LE 文本", _decode_utf16le),
        ("UTF-16 BE 文本", _decode_utf16be),
        ("int8 (signed)", lambda d: _unpack_repeat("<b", d)),
        ("uint8", lambda d: _unpack_repeat("<B", d)),
        ("int16 小端", lambda d: _unpack_repeat("<h", d)),
        ("int16 大端", lambda d: _unpack_repeat(">h", d)),
        ("uint16 小端", lambda d: _unpack_repeat("<H", d)),
        ("uint16 大端", lambda d: _unpack_repeat(">H", d)),
        ("int32 小端", lambda d: _unpack_repeat("<i", d)),
        ("int32 大端", lambda d: _unpack_repeat(">i", d)),
        ("uint32 小端", lambda d: _unpack_repeat("<I", d)),
        ("uint32 大端", lambda d: _unpack_repeat(">I", d)),
        ("int64 小端", lambda d: _unpack_repeat("<q", d)),
        ("int64 大端", lambda d: _unpack_repeat(">q", d)),
        ("uint64 小端", lambda d: _unpack_repeat("<Q", d)),
        ("uint64 大端", lambda d: _unpack_repeat(">Q", d)),
    ]
    if _has_float16():
        out.append(("float16 半精度 (IEEE754 binary16) 小端", lambda d: _unpack_repeat("<e", d)))
        out.append(("float16 半精度 大端", lambda d: _unpack_repeat(">e", d)))
    out.extend(
        [
            ("float32 小端 (binary32)", lambda d: _unpack_repeat("<f", d)),
            ("float32 大端", lambda d: _unpack_repeat(">f", d)),
            ("float64 小端 (binary64)", lambda d: _unpack_repeat("<d", d)),
            ("float64 大端", lambda d: _unpack_repeat(">d", d)),
        ]
    )
    return out


class ConvertSelectionDialog(QDialog):
    """将当前选区按选定类型解释为多元素或文本。"""

    def __init__(
        self,
        model: BinaryDataModel,
        hex_view: HexEditorView,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("转换选区为…")
        self.resize(560, 420)
        self._model = model
        self._hex_view = hex_view

        self._combo = QComboBox()
        self._entries = _entries_ordered()
        for name, _ in self._entries:
            self._combo.addItem(name)

        self._out = QPlainTextEdit()
        self._out.setReadOnly(True)
        self._out.setPlaceholderText("选择类型后将在此显示解析结果。")

        form = QFormLayout()
        form.addRow("数据类型:", self._combo)

        btn = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Close
        )
        btn.rejected.connect(self.reject)
        apply_btn = btn.addButton("解析", QDialogButtonBox.ButtonRole.ActionRole)
        apply_btn.clicked.connect(self._apply)

        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(QLabel("结果:"))
        lay.addWidget(self._out)
        lay.addWidget(btn)

        self._combo.currentIndexChanged.connect(lambda _: self._apply())

    def _selection_bytes(self) -> bytes:
        """无选区时退化为光标处 1 字节；与导出选区逻辑一致。"""
        a, b = self._hex_view.selection_range()
        if a == b:
            a = self._hex_view.cursor_position()
            b = a + 1
        if b <= a:
            b = a + 1
        n = len(self._model)
        b = min(b, n)
        a = min(max(0, a), n)
        if a >= b:
            return b""
        return self._model.read(a, b - a)

    def _apply(self) -> None:
        try:
            data = self._selection_bytes()
            idx = self._combo.currentIndex()
            if idx < 0 or idx >= len(self._entries):
                return
            fn = self._entries[idx][1]
            text = fn(data)
            self._out.setPlainText(text)
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, "解析失败", str(e))
            self._out.setPlainText("")
