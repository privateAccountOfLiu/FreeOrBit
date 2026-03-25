"""二进制模板基元：小端整数与简单结构树（供结构视图使用）。"""

from __future__ import annotations

import importlib.util
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from freeorbit.model.binary_data_model import BinaryDataModel


@dataclass
class FieldNode:
    name: str
    offset: int
    size: int
    value_repr: str


def read_u8(model: BinaryDataModel, o: int) -> int:
    return model.read_byte(o)


def read_u32_le(model: BinaryDataModel, o: int) -> int:
    return struct.unpack_from("<I", model.read(o, 4))[0]


def read_u16_le(model: BinaryDataModel, o: int) -> int:
    return struct.unpack_from("<H", model.read(o, 2))[0]


def field_tree(model: BinaryDataModel) -> list[FieldNode]:
    """默认解析：将前 256 字节按 4 字节一组显示为 DWORD（小端）。"""
    out: list[FieldNode] = []
    n = min(len(model), 256)
    i = 0
    idx = 0
    while i + 4 <= n:
        v = read_u32_le(model, i)
        out.append(FieldNode(f"DWORD[{idx}]", i, 4, f"0x{v:08X} ({v})"))
        i += 4
        idx += 1
    while i < n:
        b = read_u8(model, i)
        out.append(FieldNode(f"BYTE[{i}]", i, 1, f"0x{b:02X}"))
        i += 1
    return out


class StructBase:
    """用户模板可继承的占位基类；高级解析可扩展 load_template_from_path。"""

    @staticmethod
    def describe() -> str:
        return "StructBase"


def load_template_from_path(path: str | Path) -> Optional[Any]:
    """动态加载用户 Python 模板文件，返回模块对象。"""
    p = Path(path)
    if not p.is_file():
        return None
    spec = importlib.util.spec_from_file_location("user_template", p)
    if spec is None or spec.loader is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # noqa: S301
    return mod
