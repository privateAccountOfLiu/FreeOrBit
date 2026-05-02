"""启动画面：暗色主题样式 + 0～100% 线性进度条。"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from freeorbit.i18n import tr
from freeorbit.theme import (
    ACCENT_PRIMARY,
    SURFACE_DARK,
    SURFACE_DARKEST,
    SURFACE_LIGHT,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


def _splash_stylesheet() -> str:
    return f"""
            SplashScreen {{
                background-color: {SURFACE_DARKEST};
                border: 1px solid {SURFACE_LIGHT};
            }}
            QLabel#splashTitle {{
                color: {TEXT_PRIMARY};
                font-size: 22pt;
                font-weight: 600;
            }}
            QLabel#splashSub {{
                color: {TEXT_SECONDARY};
                font-size: 10pt;
            }}
            QLabel#splashStatus {{
                color: {TEXT_SECONDARY};
                font-size: 9pt;
            }}
            QProgressBar {{
                border: 1px solid {SURFACE_LIGHT};
                border-radius: 3px;
                background-color: {SURFACE_DARK};
                min-height: 22px;
                max-height: 22px;
                text-align: center;
                color: {TEXT_PRIMARY};
            }}
            QProgressBar::chunk {{
                background-color: {ACCENT_PRIMARY};
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
