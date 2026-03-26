"""供 build_nuitka.ps1 解析 capstone.dll 绝对路径（避免 PowerShell 对 -c 引号与编码差异导致无输出）。"""

from __future__ import annotations

import pathlib
import sys


def main() -> None:
    import capstone  # noqa: PLC0415

    p = pathlib.Path(capstone.__file__).resolve().parent / "lib" / "capstone.dll"
    if not p.is_file():
        sys.exit(1)
    sys.stdout.write(p.as_posix())


if __name__ == "__main__":
    main()
