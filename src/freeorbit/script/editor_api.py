"""脚本 API：受限全局命名空间与 editor 对象。"""

from __future__ import annotations

import builtins
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from freeorbit.viewmodel.document_editor import DocumentEditor


_ALLOWED_BUILTINS = frozenset(
    {
        "abs",
        "all",
        "any",
        "bin",
        "bool",
        "bytes",
        "chr",
        "dict",
        "enumerate",
        "filter",
        "float",
        "format",
        "frozenset",
        "hash",
        "hex",
        "int",
        "isinstance",
        "issubclass",
        "iter",
        "len",
        "list",
        "map",
        "max",
        "min",
        "next",
        "oct",
        "ord",
        "pow",
        "range",
        "repr",
        "reversed",
        "round",
        "set",
        "slice",
        "sorted",
        "str",
        "sum",
        "tuple",
        "zip",
    }
)


def _safe_builtins_dict() -> dict[str, Any]:
    return {n: getattr(builtins, n) for n in _ALLOWED_BUILTINS if hasattr(builtins, n)}


class EditorAPI:
    """暴露给用户脚本的安全接口。"""

    def __init__(self, doc: DocumentEditor) -> None:
        self._doc = doc
        self._lines: list[str] = []

    def read(self, offset: int, size: int) -> bytes:
        return self._doc.model().read(offset, size)

    def write(self, offset: int, data: bytes) -> None:
        self._doc.model().ensure_mutable_copy()
        self._doc.model().replace_range(offset, data)

    def cursor(self) -> int:
        return self._doc.hex_view().cursor_position()

    def set_cursor(self, offset: int) -> None:
        self._doc.hex_view().set_cursor_position(offset, nibble=0)

    def message(self, text: str) -> None:
        self._lines.append(str(text))

    def log_text(self) -> str:
        return "\n".join(self._lines)


def make_script_globals(api: EditorAPI) -> dict[str, Any]:
    g: dict[str, Any] = {"__builtins__": _safe_builtins_dict(), "editor": api}

    def print_fn(*args: Any, **kwargs: Any) -> None:  # noqa: A001
        if kwargs:
            api._lines.append(" ".join(str(a) for a in args) + f" {kwargs!r}")
        else:
            api._lines.append(" ".join(str(a) for a in args))

    g["print"] = print_fn
    return g
