"""为 Android 安装 frida-server 前的风险告知：需等待若干秒后方可确认。"""

from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QTextEdit,
    QVBoxLayout,
)

from freeorbit.i18n import tr


class FridaAndroidInstallRiskDialog(QDialog):
    """用户须知 + 倒计时后允许点击确定。"""

    def __init__(
        self,
        parent=None,
        *,
        wait_seconds: int = 10,
    ) -> None:
        super().__init__(parent)
        self._wait = max(1, int(wait_seconds))
        self._remain = self._wait
        self.setWindowTitle(tr("android.frida_risk_title"))
        self.setModal(True)
        self.resize(520, 380)

        root = QVBoxLayout(self)
        hint = QLabel(tr("android.frida_risk_intro"))
        hint.setWordWrap(True)
        hint.setStyleSheet("color: palette(mid);")
        root.addWidget(hint)

        body = QTextEdit()
        body.setReadOnly(True)
        body.setPlainText(tr("android.frida_risk_body"))
        root.addWidget(body, 1)

        self._btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self._btn_ok = self._btn_box.button(QDialogButtonBox.StandardButton.Ok)
        self._btn_cancel = self._btn_box.button(QDialogButtonBox.StandardButton.Cancel)
        if self._btn_ok is not None:
            self._btn_ok.setEnabled(False)
            self._btn_ok.setText(tr("android.frida_risk_ok_wait").format(n=self._remain))
        if self._btn_cancel is not None:
            self._btn_cancel.setText(tr("btn.cancel"))
        self._btn_box.accepted.connect(self.accept)
        self._btn_box.rejected.connect(self.reject)
        root.addWidget(self._btn_box)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_tick)
        self._timer.start(1000)

    def _on_tick(self) -> None:
        self._remain -= 1
        if self._btn_ok is None:
            return
        if self._remain > 0:
            self._btn_ok.setText(tr("android.frida_risk_ok_wait").format(n=self._remain))
        else:
            self._timer.stop()
            self._btn_ok.setEnabled(True)
            self._btn_ok.setText(tr("btn.ok"))
