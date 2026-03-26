"""二进制模板基元：小端整数、FieldNode 树、标量写回编码与用户 .py 模板入口。"""

from __future__ import annotations

import importlib.util
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from freeorbit.model.binary_data_model import BinaryDataModel

# 与 010「变量映射到固定宽度」对齐：标量类型名用于结构树原地编辑写回
VALID_DTYPES = frozenset(
    {
        "u8",
        "u16le",
        "u16be",
        "u32le",
        "u32be",
        "u64le",
        "u64be",
        "i32le",
        "i32be",
        "i64le",
        "i64be",
        "f32le",
        "f32be",
        "f64le",
        "f64be",
    }
)


@dataclass
class FieldNode:
    """结构树节点；children 嵌套层次；dtype 非空时可于结构树中编辑值并写回文件。"""

    name: str
    offset: int
    size: int
    value_repr: str
    children: list[FieldNode] | None = None
    # 可选：标量类型，用于与文件中字节一一映射并支持写回（对齐 010 变量可编辑性）
    dtype: Optional[str] = None


def read_u8(model: BinaryDataModel, o: int) -> int:
    return model.read_byte(o)


def read_u16_le(model: BinaryDataModel, o: int) -> int:
    return struct.unpack_from("<H", model.read(o, 2))[0]


def read_u32_le(model: BinaryDataModel, o: int) -> int:
    return struct.unpack_from("<I", model.read(o, 4))[0]


def read_u64_le(model: BinaryDataModel, o: int) -> int:
    return struct.unpack_from("<Q", model.read(o, 8))[0]


def read_i32_le(model: BinaryDataModel, o: int) -> int:
    return struct.unpack_from("<i", model.read(o, 4))[0]


def read_i64_le(model: BinaryDataModel, o: int) -> int:
    return struct.unpack_from("<q", model.read(o, 8))[0]


def read_f32_le(model: BinaryDataModel, o: int) -> float:
    return struct.unpack_from("<f", model.read(o, 4))[0]


def read_f64_le(model: BinaryDataModel, o: int) -> float:
    return struct.unpack_from("<d", model.read(o, 8))[0]


def read_u16_be(model: BinaryDataModel, o: int) -> int:
    return struct.unpack_from(">H", model.read(o, 2))[0]


def read_u32_be(model: BinaryDataModel, o: int) -> int:
    return struct.unpack_from(">I", model.read(o, 4))[0]


def read_u64_be(model: BinaryDataModel, o: int) -> int:
    return struct.unpack_from(">Q", model.read(o, 8))[0]


def read_i32_be(model: BinaryDataModel, o: int) -> int:
    return struct.unpack_from(">i", model.read(o, 4))[0]


def read_i64_be(model: BinaryDataModel, o: int) -> int:
    return struct.unpack_from(">q", model.read(o, 8))[0]


def read_f32_be(model: BinaryDataModel, o: int) -> float:
    return struct.unpack_from(">f", model.read(o, 4))[0]


def read_f64_be(model: BinaryDataModel, o: int) -> float:
    return struct.unpack_from(">d", model.read(o, 8))[0]


def format_u32(v: int) -> str:
    return f"0x{v:08X} ({v})"


def format_u16(v: int) -> str:
    return f"0x{v:04X} ({v})"


def format_u64(v: int) -> str:
    return f"0x{v:016X} ({v})"


def encode_field_value(dtype: str, text: str) -> bytes:
    """将用户在「值」列输入的文本编码为字节（小端/大端由 dtype 后缀 le/be 决定）。"""
    d = dtype.lower().strip()
    s = text.strip()
    if d in ("f32le", "f64le", "f32be", "f64be"):
        val = float(s)
        if d == "f32le":
            out = struct.pack("<f", val)
        elif d == "f64le":
            out = struct.pack("<d", val)
        elif d == "f32be":
            out = struct.pack(">f", val)
        else:
            out = struct.pack(">d", val)
    else:
        if s.lower().startswith("0x"):
            val = int(s, 16)
        else:
            val = int(s, 10)
        if d == "u8":
            out = struct.pack("<B", val & 0xFF)
        elif d == "u16le":
            out = struct.pack("<H", val & 0xFFFF)
        elif d == "u16be":
            out = struct.pack(">H", val & 0xFFFF)
        elif d == "u32le":
            out = struct.pack("<I", val & 0xFFFFFFFF)
        elif d == "u32be":
            out = struct.pack(">I", val & 0xFFFFFFFF)
        elif d == "u64le":
            out = struct.pack("<Q", val & ((1 << 64) - 1))
        elif d == "u64be":
            out = struct.pack(">Q", val & ((1 << 64) - 1))
        elif d == "i32le":
            out = struct.pack("<i", val)
        elif d == "i32be":
            out = struct.pack(">i", val)
        elif d == "i64le":
            out = struct.pack("<q", val)
        elif d == "i64be":
            out = struct.pack(">q", val)
        else:
            raise ValueError(f"未知 dtype: {dtype}")
    return out


def field_tree(model: BinaryDataModel) -> list[FieldNode]:
    """内置默认解析：将前 256 字节按 4 字节一组显示为 DWORD（小端），可编辑写回。"""
    out: list[FieldNode] = []
    n = min(len(model), 256)
    i = 0
    idx = 0
    while i + 4 <= n:
        v = read_u32_le(model, i)
        out.append(
            FieldNode(
                f"DWORD[{idx}]",
                i,
                4,
                format_u32(v),
                dtype="u32le",
            )
        )
        i += 4
        idx += 1
    while i < n:
        b = read_u8(model, i)
        out.append(
            FieldNode(f"BYTE[{i}]", i, 1, f"0x{b:02X}", dtype="u8")
        )
        i += 1
    return out


def _validate_field_nodes(nodes: list[FieldNode]) -> str | None:
    for node in nodes:
        if node.dtype and node.dtype.lower() not in VALID_DTYPES:
            return f"非法 dtype「{node.dtype}」，允许: {', '.join(sorted(VALID_DTYPES))}"
        if node.children:
            err = _validate_field_nodes(node.children)
            if err:
                return err
    return None


# 用户模板必须实现的入口函数名（与 Scheme.md 一致）
TEMPLATE_ENTRY_FN = "build_field_tree"


def run_template_field_tree(
    mod: Any | None, model: BinaryDataModel
) -> tuple[list[FieldNode], str | None]:
    """
    若 mod 提供 build_field_tree(model)，则调用之；否则使用内置 field_tree。
    返回 (节点列表, 错误信息)；错误时仍回退为内置树，便于继续编辑。
    """
    if mod is None:
        return field_tree(model), None
    fn = getattr(mod, TEMPLATE_ENTRY_FN, None)
    if not callable(fn):
        return field_tree(model), None
    try:
        raw = fn(model)
    except Exception as e:  # noqa: BLE001 — 用户模板异常需捕获并展示
        return field_tree(model), str(e)
    if raw is None:
        return field_tree(model), None
    if not isinstance(raw, list):
        return field_tree(model), "build_field_tree 必须返回 list[FieldNode] 或 None"
    for i, node in enumerate(raw):
        if not isinstance(node, FieldNode):
            return field_tree(model), f"第 {i} 项不是 FieldNode 实例"
    verr = _validate_field_nodes(raw)
    if verr:
        return field_tree(model), verr
    return raw, None


class StructBase:
    """用户模板可继承的占位基类（预留与 Scheme 中 DSL 演进对接）。"""

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
