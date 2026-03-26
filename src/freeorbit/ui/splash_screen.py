"""启动画面：与系统主题协调的样式 + 0～100% 线性进度条。"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QPalette
from PySide6.QtWidgets import (
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from freeorbit.i18n import tr


def _splash_stylesheet() -> str:
    """使用当前应用调色板，与 WindowsVista 等原生样式一致。"""
    pal = QGuiApplication.palette()
    bg = pal.color(QPalette.ColorRole.Window).name()
    border = pal.color(QPalette.ColorRole.Mid).name()
    fg = pal.color(QPalette.ColorRole.WindowText).name()
    muted = pal.color(QPalette.ColorRole.Mid).name()
    status = pal.color(QPalette.ColorRole.Dark).name()
    hl = pal.color(QPalette.ColorRole.Highlight).name()
    base = pal.color(QPalette.ColorRole.Base).name()
    return f"""
            SplashScreen {{
                background-color: {bg};
                border: 1px solid {border};
            }}
            QLabel#splashTitle {{
                color: {fg};
                font-size: 22pt;
                font-weight: 600;
            }}
            QLabel#splashSub {{
                color: {muted};
                font-size: 10pt;
            }}
            QLabel#splashStatus {{
                color: {status};
                font-size: 9pt;
            }}
            QProgressBar {{
                border: 1px solid {border};
                border-radius: 3px;
                background-color: {base};
                min-height: 22px;
                max-height: 22px;
                text-align: center;
                color: {fg};
            }}
            QProgressBar::chunk {{
                background-color: {hl};
            }}
            """


class SplashScreen(QWidget):
    """无边框启动页：标题、副标题、百分比进度条、状态行。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            parent,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.SplashScreen,
        )
        self.setFixedSize(460, 300)
        self.setWindowTitle(tr("app.title"))
        self.setStyleSheet(_splash_stylesheet())

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 28, 28, 24)
        root.setSpacing(14)

        self._title = QLabel("FreeOrBit")
        self._title.setObjectName("splashTitle")
        self._title.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self._sub = QLabel()
        self._sub.setObjectName("splashSub")
        self._sub.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._sub.setWordWrap(True)

        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setValue(0)
        self._bar.setTextVisible(True)
        self._bar.setFormat("%p%")

        self._status = QLabel()
        self._status.setObjectName("splashStatus")
        self._status.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._status.setWordWrap(True)

        root.addWidget(self._title)
        root.addWidget(self._sub)
        root.addWidget(self._bar)
        root.addStretch(1)
        root.addWidget(self._status)

        self._apply_texts()

    def _apply_texts(self) -> None:
        self._sub.setText(tr("splash.subtitle"))
        self._status.setText(tr("splash.loading"))

    def set_progress(self, value: int) -> None:
        """设置进度 0～100。"""
        self._bar.setValue(max(0, min(100, int(value))))

    def set_status(self, text: str) -> None:
        self._status.setText(text)

    def showEvent(self, event: object) -> None:
        super().showEvent(event)
        screen = QGuiApplication.primaryScreen()
        if screen is not None:
            ag = screen.availableGeometry()
            self.move(
                ag.center().x() - self.width() // 2,
                ag.center().y() - self.height() // 2,
            )

    def finish(self, main_window: QWidget) -> None:
        """关闭启动页并显示主窗口。"""
        self.close()
        main_window.showMaximized()
        main_window.raise_()
        main_window.activateWindow()
