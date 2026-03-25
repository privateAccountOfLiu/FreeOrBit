"""应用程序入口与高 DPI 设置。"""

from __future__ import annotations

import sys
import traceback

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMessageBox

from freeorbit.icon_assets import app_icon
from freeorbit.main_window import MainWindow


def _install_excepthook() -> None:
    """未捕获异常时弹出提示，避免静默失败。"""

    def _hook(exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
        err = "".join(traceback.format_exception(exc_type, exc, tb))
        try:
            QMessageBox.critical(None, "未处理的错误", err[:4000])
        except Exception:
            pass
        sys.__excepthook__(exc_type, exc, tb)

    sys.excepthook = _hook


def main() -> int:
    # 高 DPI 缩放（Qt6 默认行为较合理，此处显式启用像素比）
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName("FreeOrBit")
    app.setOrganizationName("FreeOrBit")

    _ico = app_icon()
    if _ico is not None:
        app.setWindowIcon(_ico)

    try:
        from qt_material import apply_stylesheet

        apply_stylesheet(app, theme="dark_blue.xml")
    except Exception:
        # 未安装或主题加载失败时使用系统原生样式
        pass

    _install_excepthook()

    win = MainWindow()
    # 最大化以占满工作区，保留标题栏关闭/最小化/还原按钮（非真正全屏）
    win.showMaximized()
    return app.exec()
