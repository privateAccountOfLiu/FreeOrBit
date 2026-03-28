"""Android / Frida 相关 QSettings 读写（与设置对话框、Android 停靠面板共用）。"""

from __future__ import annotations

from PySide6.QtCore import QSettings


def adb_path() -> str:
    v = QSettings().value("android/adb_path", "adb")
    if isinstance(v, str) and v.strip():
        return v.strip()
    return "adb"


def frida_remote_host() -> str:
    """非空时优先通过该地址连接 Frida（如 192.168.0.1:27042）；空则走 USB / 序列号。"""
    v = QSettings().value("android/frida_remote_host", "")
    return v.strip() if isinstance(v, str) else ""


def frida_server_device_path() -> str:
    """设备上 frida-server 参考路径（仅文案/提示，应用不自动推送）。"""
    v = QSettings().value("android/frida_server_device_path", "/data/local/tmp/frida-server")
    if isinstance(v, str) and v.strip():
        return v.strip()
    return "/data/local/tmp/frida-server"


def frida_expected_major() -> str:
    """期望与 frida-server 一致的主版本号片段（如 16），仅用于提示。"""
    v = QSettings().value("android/frida_expected_major", "")
    return v.strip() if isinstance(v, str) else ""


def frida_warn_version_mismatch() -> bool:
    return QSettings().value("android/frida_warn_version_mismatch", True, type=bool)


def frida_use_pip_env() -> bool:
    """True：从用户填写的路径（通常为 site-packages）加载 frida；False：使用程序内置（打包 exe）或当前解释器环境。"""
    return QSettings().value("android/frida_use_pip_env", False, type=bool)


def frida_pip_site_packages() -> str:
    """勾选「使用 pip Frida」时，前置到 sys.path 的目录（一般为 Python 的 site-packages）。"""
    v = QSettings().value("android/frida_pip_site_packages", "")
    return v.strip() if isinstance(v, str) else ""


def python_frida_version() -> str | None:
    """当前生效的 frida Python 包版本；未安装返回 None。"""
    from freeorbit.platform import frida_loader

    frida_loader.ensure_frida_import_preference()
    try:
        import frida

        return str(getattr(frida, "__version__", "?"))
    except ImportError:
        return None
