"""Windows 文件关联注册：右键菜单 "Open with FreeOrBit" 和默认程序关联。"""

from __future__ import annotations

import os
import sys
import winreg


def _app_path() -> str:
    """当前可执行文件或 Python 入口的绝对路径。"""
    if getattr(sys, "frozen", False):
        return os.path.abspath(sys.executable)
    return os.path.abspath(sys.argv[0])


def _python_open_command() -> str:
    """python.exe 打开 FreeOrBit 的命令行。"""
    exe = _app_path()
    if exe.lower().endswith(".exe"):
        return f'"{exe}" "%1"'
    py = sys.executable
    script = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "main.py")
    )
    return f'"{py}" "{script}" "%1"'


def register() -> str | None:
    """注册 FreeOrBit 到 Windows 右键菜单 "Open with FreeOrBit" (HKCU)。"""
    if sys.platform != "win32":
        return "仅支持 Windows"

    cmd = _python_open_command()
    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER,
                              r"Software\Classes\*\shell\FreeOrBit") as k:
            winreg.SetValueEx(k, "", 0, winreg.REG_SZ, "Open with FreeOrBit")
            winreg.SetValueEx(k, "Icon", 0, winreg.REG_SZ, _app_path())
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER,
                              r"Software\Classes\*\shell\FreeOrBit\command") as k:
            winreg.SetValueEx(k, "", 0, winreg.REG_SZ, cmd)
        return None
    except OSError as e:
        return str(e)


def unregister() -> str | None:
    """移除 FreeOrBit 的 Windows 右键菜单条目。"""
    if sys.platform != "win32":
        return "仅支持 Windows"
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                             r"Software\Classes\*\shell", 0, winreg.KEY_WRITE | winreg.KEY_READ)
        try:
            winreg.DeleteKey(key, r"FreeOrBit\command")
        except FileNotFoundError:
            pass
        try:
            winreg.DeleteKey(key, "FreeOrBit")
        except FileNotFoundError:
            pass
        winreg.CloseKey(key)
        return None
    except OSError as e:
        return str(e)


def is_registered() -> bool:
    """检查 FreeOrBit 是否已注册右键菜单。"""
    if sys.platform != "win32":
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Classes\*\shell\FreeOrBit"):
            return True
    except FileNotFoundError:
        return False
