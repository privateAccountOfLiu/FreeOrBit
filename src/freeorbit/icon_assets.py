"""应用图标路径解析（开发与 Nuitka 单文件均可用）。

包内资源需与 setuptools package-data 及 Nuitka --include-data-files 目标路径一致
（freeorbit/resources/FreeOrBit.ico）；__file__ 在 frozen 下指向展开后的包目录。
"""

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
