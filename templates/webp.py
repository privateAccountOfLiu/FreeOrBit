"""
WebP：RIFF 容器 + WEBP + 首个子块（VP8 / VP8L / VP8X）。

RIFF 头：0-3「RIFF」，4-7 小端文件长（减 8），8-11「WEBP」。
"""

from __future__ import annotations

from freeorbit.model.binary_data_model import BinaryDataModel
from freeorbit.template.builders import bytes_hex, u32_le
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
    if n < 12:
        return []

    out: list[FieldNode] = []
    out.append(bytes_hex("RIFF_tag", 0, 4, model))
    if model.read(0, 4) != b"RIFF":
        return [
            FieldNode(
                "提示",
                0,
                0,
                "非 RIFF/WebP（应以 RIFF 开头）",
                dtype=None,
            )
        ]

    out.append(u32_le("file_size_minus_8", 4, model))
    out.append(_fourcc(model, 8, "WEBP_tag"))
    if model.read(8, 4) != b"WEBP":
        out.append(
            FieldNode(
                "提示",
                8,
                0,
                "WEBP 标识缺失",
                dtype=None,
            )
        )
        return out

    if n >= 16:
        out.append(_fourcc(model, 12, "first_chunk_fourcc"))
        out.append(u32_le("first_chunk_size", 16, model))
    if n > 20:
        out.append(bytes_hex("chunk_payload_preview", 20, min(32, n - 20), model))
    return out
