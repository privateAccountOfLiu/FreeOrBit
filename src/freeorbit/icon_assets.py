"""应用图标路径解析（开发与 Nuitka 单文件均可用）。"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import freeorbit
from PySide6.QtGui import QIcon


def app_icon() -> Optional[QIcon]:
    """加载包内 resources/FreeOrBit.ico；不存在则返回 None。"""
    p = Path(freeorbit.__file__).resolve().parent / "resources" / "FreeOrBit.ico"
    if p.is_file():
        return QIcon(str(p))
    return None
