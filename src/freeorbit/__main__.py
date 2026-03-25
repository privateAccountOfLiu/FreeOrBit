"""命令行入口：python -m freeorbit"""

from __future__ import annotations

import sys

from freeorbit.app import main


if __name__ == "__main__":
    sys.exit(main())
