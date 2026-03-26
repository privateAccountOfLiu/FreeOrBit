"""
内置：PE IMAGE_DOS_HEADER 关键字段（MZ、e_lfanew），对齐常见逆向场景。

文件不足 0x40 字节时仅展示已有部分。
"""

from __future__ import annotations

from freeorbit.model.binary_data_model import BinaryDataModel
from freeorbit.template.builders import bytes_hex, u16_le, u32_le
from freeorbit.template.fields import FieldNode


def build_field_tree(model: BinaryDataModel) -> list[FieldNode]:
    n = len(model)
    if n < 2:
        return []
    out: list[FieldNode] = []
    out.append(u16_le("e_magic (MZ)", 0, model))
    if n >= 0x40:
        out.append(bytes_hex("dos_stub", 2, 0x3A, model))
        out.append(u32_le("e_lfanew", 0x3C, model))
    elif n > 2:
        out.append(bytes_hex("dos_remainder", 2, n - 2, model))
    return out
