"""
JPEG：SOI (FF D8) + 紧跟的标记段（FF xx）及段长度（大端 u16）。

常见：FFE0 APP0(JFIF)、FFE1 APP1(EXIF) 等。
"""

from __future__ import annotations

from freeorbit.model.binary_data_model import BinaryDataModel
from freeorbit.template.builders import bytes_hex, u16_be
from freeorbit.template.fields import FieldNode


def build_field_tree(model: BinaryDataModel) -> list[FieldNode]:
    n = len(model)
    if n < 2:
        return []

    out: list[FieldNode] = []
    out.append(bytes_hex("SOI", 0, 2, model))
    if model.read(0, 2) != b"\xff\xd8":
        out.append(
            FieldNode(
                "提示",
                0,
                0,
                "非 JPEG SOI（应以 FF D8 开头）",
                dtype=None,
            )
        )
        return out

    if n < 4:
        return out

    out.append(bytes_hex("marker_FF_xx", 2, 2, model))
    if model.read_byte(2) != 0xFF:
        out.append(
            FieldNode(
                "提示",
                2,
                0,
                "SOI 后应为 FF 起始的段标记",
                dtype=None,
            )
        )
        return out

    if n >= 6:
        out.append(u16_be("segment_length_be", 4, model))
    # 段数据从偏移 6 起（长度字段之后）
    if n > 6:
        take = min(32, n - 6)
        out.append(bytes_hex("segment_data_preview", 6, take, model))
    return out
