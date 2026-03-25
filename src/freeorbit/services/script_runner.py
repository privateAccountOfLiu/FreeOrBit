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
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from freeorbit.i18n import tr
from freeorbit.script.editor_api import EditorAPI, make_script_globals

if TYPE_CHECKING:
    from freeorbit.viewmodel.document_editor import DocumentEditor


class _WheelPlainTextEdit(QPlainTextEdit):
    """滚轮灵敏度提高，高度由父分割器分配，不随行数变化。"""

    def wheelEvent(self, event: QWheelEvent) -> None:
        if event.modifiers() == Qt.KeyboardModifier.NoModifier:
            dy = event.angleDelta().y()
            sb = self.verticalScrollBar()
            line = max(12, QFontMetrics(self.font()).height())
            sb.setValue(sb.value() - int(dy * line * 2.5 / 120))
            event.accept()
            return
        super().wheelEvent(event)


class ScriptDock(QDockWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(tr("dock.script"), parent)
        self._doc: Optional[DocumentEditor] = None

        w = QWidget()
        self.setWidget(w)
        lay = QVBoxLayout(w)
        lay.setContentsMargins(4, 4, 4, 4)

        self._lbl_code = QLabel()
        self._code = _WheelPlainTextEdit()
        self._code.setPlaceholderText(tr("script.placeholder"))
        self._code.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self._code.setMinimumHeight(48)
        self._code.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

        self._lbl_out = QLabel()
        self._out = _WheelPlainTextEdit()
        self._out.setReadOnly(True)
        self._out.setMinimumHeight(40)
        self._out.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        fm = QFontMetrics(self._out.font())
        self._out.verticalScrollBar().setSingleStep(max(12, fm.height()))

        splitter = QSplitter(Qt.Orientation.Vertical)
        box_code = QWidget()
        lc = QVBoxLayout(box_code)
        lc.setContentsMargins(0, 0, 0, 0)
        lc.addWidget(self._lbl_code)
        lc.addWidget(self._code, 1)
        box_out = QWidget()
        lo = QVBoxLayout(box_out)
        lo.setContentsMargins(0, 0, 0, 0)
        lo.addWidget(self._lbl_out)
        lo.addWidget(self._out, 1)
        splitter.addWidget(box_code)
        splitter.addWidget(box_out)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        lay.addWidget(splitter, 1)

        row = QHBoxLayout()
        self._btn_run = QPushButton()
        self._btn_run.clicked.connect(self._run)
        row.addWidget(self._btn_run)
        lay.addLayout(row)

        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        self.setWindowTitle(tr("dock.script"))
        self._lbl_code.setText(tr("script.label_code"))
        self._lbl_out.setText(tr("script.label_out"))
        self._code.setPlaceholderText(tr("script.placeholder"))
        self._btn_run.setText(tr("script.run"))

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
            QMessageBox.warning(self, tr("script.err_title"), str(e))
