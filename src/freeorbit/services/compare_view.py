"""双文件二进制比较：独立子窗口，绿/红逐字节标示相同与差异。"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QDialog,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from freeorbit.model.binary_data_model import BinaryDataModel
from freeorbit.view.hex_format import format_hex_dump_lines
from freeorbit.view.hex_editor_view import HexEditorView


def _build_compare_highlights(
    left: BinaryDataModel, right: BinaryDataModel
) -> tuple[list[int], list[int]]:
    """每个字节：1=两侧相同 2=不同或一侧缺字节。"""
    la, lb = len(left), len(right)
    hl_left: list[int] = []
    for i in range(la):
        if i < lb:
            same = left.read_byte(i) == right.read_byte(i)
        else:
            same = False
        hl_left.append(1 if same else 2)
    hl_right: list[int] = []
    for i in range(lb):
        if i < la:
            same = left.read_byte(i) == right.read_byte(i)
        else:
            same = False
        hl_right.append(1 if same else 2)
    return hl_left, hl_right


class CompareWindow(QDialog):
    """独立窗口，左右分栏同步滚动，十六进制区显示比较底色。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("二进制比较")
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowMinMaxButtonsHint
            | Qt.WindowType.WindowCloseButtonHint
        )
        self.resize(1100, 720)

        self._path_a = ""
        self._path_b = ""

        self._left_model = BinaryDataModel(self)
        self._right_model = BinaryDataModel(self)
        self._left = HexEditorView(self)
        self._right = HexEditorView(self)
        self._left.set_model(self._left_model)
        self._right.set_model(self._right_model)

        left_wrap = QWidget()
        ll = QVBoxLayout(left_wrap)
        ll.setContentsMargins(4, 4, 4, 4)
        ll.addWidget(QLabel("文件 A"))
        ll.addWidget(self._left, 1)

        right_wrap = QWidget()
        rl = QVBoxLayout(right_wrap)
        rl.setContentsMargins(4, 4, 4, 4)
        rl.addWidget(QLabel("文件 B"))
        rl.addWidget(self._right, 1)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left_wrap)
        splitter.addWidget(right_wrap)
        splitter.setSizes([540, 540])

        top_bar = QHBoxLayout()
        btn_export = QPushButton("导出相同部分…")
        btn_export.setToolTip("导出两文件在相同偏移处相等的字节：偏移表 + 连续十六进制串")
        btn_export.clicked.connect(self._export_matching)
        top_bar.addWidget(btn_export)
        top_bar.addStretch()

        lay = QVBoxLayout(self)
        lay.addLayout(top_bar)
        lay.addWidget(splitter, 1)

        self._left.verticalScrollBar().valueChanged.connect(self._sync_from_left)
        self._right.verticalScrollBar().valueChanged.connect(self._sync_from_right)

    def _sync_from_left(self, v: int) -> None:
        self._right.verticalScrollBar().blockSignals(True)
        self._right.verticalScrollBar().setValue(v)
        self._right.verticalScrollBar().blockSignals(False)

    def _sync_from_right(self, v: int) -> None:
        self._left.verticalScrollBar().blockSignals(True)
        self._left.verticalScrollBar().setValue(v)
        self._left.verticalScrollBar().blockSignals(False)

    def load_paths(self, path_a: str, path_b: str) -> None:
        self._path_a = str(Path(path_a))
        self._path_b = str(Path(path_b))
        self._left_model.load_file(path_a)
        self._right_model.load_file(path_b)
        hl_l, hl_r = _build_compare_highlights(self._left_model, self._right_model)
        self._left.set_compare_highlights(hl_l)
        self._right.set_compare_highlights(hl_r)
        self._left.refresh_display()
        self._right.refresh_display()
        self.setWindowTitle(f"二进制比较 — {Path(path_a).name} / {Path(path_b).name}")

    def _export_matching(self) -> None:
        """导出相同偏移处相等的字节：与主编辑器一致的地址 + Hex + ASCII 行格式。"""
        la, lb = len(self._left_model), len(self._right_model)
        if la == 0 and lb == 0:
            QMessageBox.information(self, "导出", "没有已加载的数据。")
            return
        n = min(la, lb)
        self._left.refresh_display()
        bpl = self._left.bytes_per_line()
        total_for_digits = max(la, lb)

        match_count = 0
        body_lines: list[str] = []
        run_start: int | None = None
        for i in range(n):
            same = self._left_model.read_byte(i) == self._right_model.read_byte(i)
            if same:
                match_count += 1
                if run_start is None:
                    run_start = i
            else:
                if run_start is not None:
                    chunk = self._left_model.read(run_start, i - run_start)
                    body_lines.extend(
                        format_hex_dump_lines(
                            chunk,
                            bpl,
                            start_offset=run_start,
                            total_file_bytes=total_for_digits,
                        )
                    )
                    body_lines.append("")
                    run_start = None
        if run_start is not None:
            chunk = self._left_model.read(run_start, n - run_start)
            body_lines.extend(
                format_hex_dump_lines(
                    chunk,
                    bpl,
                    start_offset=run_start,
                    total_file_bytes=total_for_digits,
                )
            )

        path, _ = QFileDialog.getSaveFileName(
            self,
            "导出相同部分",
            "compare_match_export.txt",
            "文本 (*.txt);;所有 (*.*)",
        )
        if not path:
            return
        lines = [
            "# FreeOrBit 文件比较 — 相同字节导出（格式与主编辑器十六进制视图一致：地址 / Hex / ASCII）",
            f"# 文件A: {self._path_a}",
            f"# 文件B: {self._path_b}",
            f"# 相同字节数: {match_count}  每行字节数: {bpl}",
            "",
            *body_lines,
        ]
        try:
            Path(path).write_text("\n".join(lines), encoding="utf-8")
        except OSError as e:
            QMessageBox.warning(self, "导出失败", str(e))
            return
        QMessageBox.information(self, "导出", f"已保存到:\n{path}")


CompareWidget = CompareWindow  # 兼容旧名称
