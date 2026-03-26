"""应用程序入口与高 DPI 设置。"""

from __future__ import annotations

import sys
import traceback

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMessageBox

from freeorbit.icon_assets import app_icon
from freeorbit.i18n import tr
from freeorbit.main_window import MainWindow
from freeorbit.ui.splash_screen import SplashScreen


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

    # Windows：若用户选择默认以管理员启动，则尽早提权重启（在闪屏与主窗口之前）
    if sys.platform == "win32":
        from freeorbit.platform.win_elevation import maybe_relaunch_if_requested

        if maybe_relaunch_if_requested():
            sys.exit(0)

    splash = SplashScreen()
    splash.set_progress(0)
    splash.show()
    app.processEvents()

    _ico = app_icon()
    if _ico is not None:
        app.setWindowIcon(_ico)
        splash.setWindowIcon(_ico)

    splash.set_progress(8)
    splash.set_status(tr("splash.theme"))
    app.processEvents()
    try:
        from qt_material import apply_stylesheet

        apply_stylesheet(app, theme="dark_blue.xml")
    except Exception:
        # 未安装或主题加载失败时使用系统原生样式
        pass

    splash.set_progress(42)
    splash.set_status(tr("splash.ui"))
    app.processEvents()

    _install_excepthook()

    splash.set_progress(72)
    win = MainWindow()
    splash.set_progress(100)
    app.processEvents()
    splash.finish(win)
    return app.exec()
