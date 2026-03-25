"""受限 Python 脚本执行与输出。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QFontMetrics, QWheelEvent
from PySide6.QtWidgets import (
    QDockWidget,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from freeorbit.script.editor_api import EditorAPI, make_script_globals

if TYPE_CHECKING:
    from freeorbit.viewmodel.document_editor import DocumentEditor


class ScriptCodeEdit(QPlainTextEdit):
    """多行脚本编辑：滚轮更灵敏，高度随行数在合理范围内变化。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._line_h = QFontMetrics(self.font()).height()
        self._min_h = 72
        self._max_h = 360
        self.textChanged.connect(self._adjust_height)
        self._adjust_height()

    def _adjust_height(self) -> None:
        doc = self.document()
        n = max(1, doc.blockCount())
        pad = 16
        h = min(self._max_h, max(self._min_h, n * self._line_h + pad))
        self.setMinimumHeight(int(h))
        self.setMaximumHeight(int(h))

    def wheelEvent(self, event: QWheelEvent) -> None:
        # 提高滚轮灵敏度（约为默认行滚动的 2.5 倍）
        if event.modifiers() == Qt.KeyboardModifier.NoModifier:
            dy = event.angleDelta().y()
            sb = self.verticalScrollBar()
            line = max(12, self._line_h)
            sb.setValue(sb.value() - int(dy * line * 2.5 / 120))
            event.accept()
            return
        super().wheelEvent(event)


class ScriptDock(QDockWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__("脚本", parent)
        self._doc: Optional[DocumentEditor] = None

        w = QWidget()
        self.setWidget(w)
        lay = QVBoxLayout(w)
        self._code = ScriptCodeEdit()
        self._code.setPlaceholderText(
            "# 示例: data = editor.read(0, 16); editor.message(hex(data))\\n"
        )
        self._code.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self._code.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        lay.addWidget(QLabel("Python（受限 API）:"))
        lay.addWidget(self._code, 1)

        row = QHBoxLayout()
        run = QPushButton("运行")
        run.clicked.connect(self._run)
        row.addWidget(run)
        lay.addLayout(row)

        self._out = QPlainTextEdit()
        self._out.setReadOnly(True)
        self._out.setMinimumHeight(48)
        self._out.setMaximumHeight(160)
        self._out.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        fm = QFontMetrics(self._out.font())
        self._out.verticalScrollBar().setSingleStep(max(12, fm.height()))
        lay.addWidget(QLabel("输出:"))
        lay.addWidget(self._out)

    def bind_document(self, doc: DocumentEditor) -> None:
        self._doc = doc

    def _run(self) -> None:
        if self._doc is None:
            return
        api = EditorAPI(self._doc)
        g = make_script_globals(api)
        try:
            exec(self._code.toPlainText(), g, g)  # noqa: S102
            self._out.setPlainText(api.log_text())
        except Exception as e:  # noqa: BLE001
            self._out.setPlainText(api.log_text() + f"\n错误: {e!r}")
            QMessageBox.warning(self, "脚本", str(e))
