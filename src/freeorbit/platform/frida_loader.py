"""按设置选择程序内置 Frida 与用户 pip 环境中的 Frida（Nuitka 单文件与开发环境）。"""

from __future__ import annotations

import os
import sys

_CONFIGURED = False


def reset_frida_import_config() -> None:
    """设置中切换 Frida 来源后调用，使下次 import 重新解析路径。"""
    global _CONFIGURED
    _CONFIGURED = False
    for k in list(sys.modules.keys()):
        if k == "frida" or k.startswith("frida."):
            del sys.modules[k]


def ensure_frida_import_preference() -> None:
    """在首次 import frida 之前调用：若勾选使用 pip 环境，将 site-packages 前置到 sys.path。"""
    global _CONFIGURED
    if _CONFIGURED:
        return
    _CONFIGURED = True

    from PySide6.QtCore import QSettings

    use_pip = QSettings().value("android/frida_use_pip_env", False, type=bool)
    if not use_pip:
        return

    extra = QSettings().value("android/frida_pip_site_packages", "")
    path = extra.strip() if isinstance(extra, str) else ""
    if not path:
        return

    path = os.path.normpath(path)
    if os.path.isdir(path) and path not in sys.path:
        sys.path.insert(0, path)
