"""在首次 import capstone 之前运行。

capstone 用 ctypes 加载 lib/capstone.dll。Nuitka 将包编译进二进制后，
pkg_resources / __file__ 往往无法定位到随包展开的 lib，导致 DLL 加载失败。

打包时通过 Nuitka 将 capstone.dll 安装到 **freeorbit/resources/capstone/**（与 ico 同层），
此处用 freeorbit.__file__ 解析出绝对路径并设置 LIBCAPSTONE_PATH。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def ensure_capstone_dll_path() -> None:
    """设置 LIBCAPSTONE_PATH，使 capstone 能加载 capstone.dll（幂等）。"""
    if os.environ.get("LIBCAPSTONE_PATH"):
        return

    # 1) Nuitka onefile：DLL 与包内资源一并展开到 freeorbit/resources/capstone/
    try:
        import freeorbit

        base = Path(freeorbit.__file__).resolve().parent
        bundled = base / "resources" / "capstone" / "capstone.dll"
        if bundled.is_file():
            lib_dir = str(bundled.parent)
            os.environ["LIBCAPSTONE_PATH"] = lib_dir
            if sys.platform == "win32" and hasattr(os, "add_dll_directory"):
                os.add_dll_directory(lib_dir)
            return
    except Exception:
        pass

    # 2) 源码 / 普通 pip：site-packages/capstone/lib/
    try:
        import importlib.util

        spec = importlib.util.find_spec("capstone")
        if spec is None or not spec.submodule_search_locations:
            return
        root = Path(spec.submodule_search_locations[0])
        lib_dir = root / "lib"
        if sys.platform == "win32":
            dll = lib_dir / "capstone.dll"
        elif sys.platform == "darwin":
            dll = lib_dir / "libcapstone.dylib"
        else:
            dll = lib_dir / "libcapstone.so"
        if dll.is_file():
            d = str(lib_dir)
            os.environ["LIBCAPSTONE_PATH"] = d
            if sys.platform == "win32" and hasattr(os, "add_dll_directory"):
                os.add_dll_directory(d)
    except Exception:
        pass
