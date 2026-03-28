"""
PNG：文件头签名 + IHDR 块（宽/高/位深/颜色类型等）。

魔数：89 50 4E 47 0D 0A 1A 0A；IHDR 为大端（网络字节序）。
"""

from __future__ import annotations

from freeorbit.model.binary_data_model import BinaryDataModel
from freeorbit.template.builders import bytes_hex, u32_be
from freeorbit.template.fields import FieldNode


def _fourcc(model: BinaryDataModel, offset: int, name: str) -> FieldNode:
    n = len(model)
    if offset < 0 or offset + 4 > n:
        return FieldNode(name, offset, 0, "", dtype=None)
    raw = model.read(offset, 4)
    try:
        s = raw.decode("ascii")
    except UnicodeDecodeError:
        s = raw.hex().upper()
    return FieldNode(name, offset, 4, s, dtype=None)


def build_field_tree(model: BinaryDataModel) -> list[FieldNode]:
    n = len(model)
    if n < 24:
        return []

    sig = model.read(0, min(8, n))
    if sig[:8] != bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A]):
        return [
            FieldNode(
                "提示",
                0,
                0,
                "非标准 PNG 签名（前 8 字节应为 89 50 4E 47…）",
                dtype=None,
            )
        ]

    out: list[FieldNode] = []
    out.append(bytes_hex("PNG_signature", 0, 8, model))
    out.append(u32_be("IHDR_chunk_length", 8, model))
    out.append(_fourcc(model, 12, "IHDR_chunk_type"))
    # IHDR 数据：宽、高、位深、颜色类型、压缩、滤波、交错
    out.append(u32_be("width_px", 16, model))
    out.append(u32_be("height_px", 20, model))
    out.append(FieldNode("bit_depth", 24, 1, f"{model.read_byte(24)}", dtype="u8"))
    out.append(FieldNode("color_type", 25, 1, f"{model.read_byte(25)}", dtype="u8"))
    out.append(FieldNode("compression", 26, 1, f"{model.read_byte(26)}", dtype="u8"))
    out.append(FieldNode("filter_method", 27, 1, f"{model.read_byte(27)}", dtype="u8"))
    out.append(FieldNode("interlace", 28, 1, f"{model.read_byte(28)}", dtype="u8"))
    if n >= 33:
        out.append(u32_be("IHDR_CRC32_BE", 29, model))
    return out
