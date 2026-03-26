"""010 风格便捷构造器：从模型读标量并生成带 dtype 的 FieldNode（支持结构树写回）。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from freeorbit.template.fields import (
    FieldNode,
    format_u16,
    format_u32,
    format_u64,
    read_f32_be,
    read_f32_le,
    read_f64_be,
    read_f64_le,
    read_i32_be,
    read_i32_le,
    read_i64_be,
    read_i64_le,
    read_u16_be,
    read_u16_le,
    read_u32_be,
    read_u32_le,
    read_u64_be,
    read_u64_le,
    read_u8,
)

if TYPE_CHECKING:
    from freeorbit.model.binary_data_model import BinaryDataModel


def u8(name: str, offset: int, model: BinaryDataModel) -> FieldNode:
    v = read_u8(model, offset)
    return FieldNode(name, offset, 1, f"0x{v:02X}", dtype="u8")


def u16_le(name: str, offset: int, model: BinaryDataModel) -> FieldNode:
    v = read_u16_le(model, offset)
    return FieldNode(name, offset, 2, format_u16(v), dtype="u16le")


def u16_be(name: str, offset: int, model: BinaryDataModel) -> FieldNode:
    v = read_u16_be(model, offset)
    return FieldNode(name, offset, 2, format_u16(v) + " BE", dtype="u16be")


def u32_le(name: str, offset: int, model: BinaryDataModel) -> FieldNode:
    v = read_u32_le(model, offset)
    return FieldNode(name, offset, 4, format_u32(v), dtype="u32le")


def u32_be(name: str, offset: int, model: BinaryDataModel) -> FieldNode:
    v = read_u32_be(model, offset)
    return FieldNode(name, offset, 4, format_u32(v) + " BE", dtype="u32be")


def u64_le(name: str, offset: int, model: BinaryDataModel) -> FieldNode:
    v = read_u64_le(model, offset)
    return FieldNode(name, offset, 8, format_u64(v), dtype="u64le")


def u64_be(name: str, offset: int, model: BinaryDataModel) -> FieldNode:
    v = read_u64_be(model, offset)
    return FieldNode(name, offset, 8, format_u64(v) + " BE", dtype="u64be")


def i32_le(name: str, offset: int, model: BinaryDataModel) -> FieldNode:
    v = read_i32_le(model, offset)
    return FieldNode(name, offset, 4, f"{v} (0x{v & 0xFFFFFFFF:08X})", dtype="i32le")


def i32_be(name: str, offset: int, model: BinaryDataModel) -> FieldNode:
    v = read_i32_be(model, offset)
    return FieldNode(name, offset, 4, f"{v} BE (0x{v & 0xFFFFFFFF:08X})", dtype="i32be")


def i64_le(name: str, offset: int, model: BinaryDataModel) -> FieldNode:
    v = read_i64_le(model, offset)
    return FieldNode(name, offset, 8, f"{v}", dtype="i64le")


def i64_be(name: str, offset: int, model: BinaryDataModel) -> FieldNode:
    v = read_i64_be(model, offset)
    return FieldNode(name, offset, 8, f"{v} BE", dtype="i64be")


def f32_le(name: str, offset: int, model: BinaryDataModel) -> FieldNode:
    v = read_f32_le(model, offset)
    return FieldNode(name, offset, 4, repr(v), dtype="f32le")


def f64_le(name: str, offset: int, model: BinaryDataModel) -> FieldNode:
    v = read_f64_le(model, offset)
    return FieldNode(name, offset, 8, repr(v), dtype="f64le")


def f32_be(name: str, offset: int, model: BinaryDataModel) -> FieldNode:
    v = read_f32_be(model, offset)
    return FieldNode(name, offset, 4, repr(v) + " BE", dtype="f32be")


def f64_be(name: str, offset: int, model: BinaryDataModel) -> FieldNode:
    v = read_f64_be(model, offset)
    return FieldNode(name, offset, 8, repr(v) + " BE", dtype="f64be")


def bytes_hex(name: str, offset: int, length: int, model: BinaryDataModel) -> FieldNode:
    """原始字节块：只读展示，不可通过 dtype 写回（保持与 010 中 char[] 只读展示类似）。"""
    n = len(model)
    if offset < 0 or offset >= n:
        return FieldNode(name, offset, 0, "")
    take = min(length, n - offset)
    raw = model.read(offset, take)
    return FieldNode(name, offset, take, raw.hex().upper(), dtype=None)
