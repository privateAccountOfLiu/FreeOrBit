"""包内内置 .py 模板路径枚举（随 setuptools package-data 分发）。"""

from __future__ import annotations

from pathlib import Path

import freeorbit


def builtin_templates_dir() -> Path:
    return Path(freeorbit.__file__).resolve().parent / "resources" / "templates"


def list_builtin_templates() -> list[tuple[str, Path]]:
    """返回 (显示名, 文件路径) 列表，按文件名排序。"""
    d = builtin_templates_dir()
    if not d.is_dir():
        return []
    out: list[tuple[str, Path]] = []
    for p in sorted(d.glob("*.py")):
        out.append((p.stem, p))
    return out
