"""
Windows 管理员权限检测与自提权重启（UAC）。

用于进程内存、原始磁盘等需提升权限的能力。
"""

from __future__ import annotations

import ctypes
import os
import subprocess
import sys


def is_windows() -> bool:
    return sys.platform == "win32"


def is_admin() -> bool:
    """当前进程是否已以管理员身份运行。"""
    if not is_windows():
        return False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _build_relaunch_parameters() -> str:
    """构造传给 ShellExecute 的 lpParameters（不含可执行文件路径）。"""
    argv = list(sys.argv)
    if argv:
        argv[0] = os.path.abspath(argv[0])
    if getattr(sys, "frozen", False):
        # PyInstaller / Nuitka onefile：argv[0] 为 exe，参数为 argv[1:]
        return subprocess.list2cmdline(argv[1:])
    # python.exe script.py ...
    return subprocess.list2cmdline(argv)


def restart_as_admin() -> bool:
    """
    通过 ShellExecute runas 以管理员身份重启当前入口。

    返回 True 表示已发起新进程（当前进程应退出）；False 表示失败或用户取消 UAC。
    """
    if not is_windows() or is_admin():
        return False
    try:
        params = _build_relaunch_parameters()
        # SW_SHOWNORMAL = 1
        ret = ctypes.windll.shell32.ShellExecuteW(
            None,
            "runas",
            sys.executable,
            params,
            None,
            1,
        )
        return int(ret) > 32
    except Exception:
        return False


def maybe_relaunch_if_requested() -> bool:
    """
    在 QApplication 已创建且已设置 organization/application 名后调用。

    若用户启用了「默认以管理员启动」且当前非管理员，则发起 UAC 提权重启并返回 True
    （调用方应立即退出当前进程）；否则返回 False。
    """
    if not is_windows() or is_admin():
        return False
    from PySide6.QtCore import QSettings

    if not QSettings().value("elevation/request_admin_on_launch", False, type=bool):
        return False
    return restart_as_admin()
