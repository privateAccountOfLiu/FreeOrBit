"""兼容入口：python main.py（将 src 加入路径以便未 pip 安装时运行）。"""

from __future__ import annotations

import sys
from pathlib import Path

_root = Path(__file__).resolve().parent
_src = _root / "src"
if _src.is_dir():
    sys.path.insert(0, str(_src))

from freeorbit.app import main

if __name__ == "__main__":
    raise SystemExit(main())
