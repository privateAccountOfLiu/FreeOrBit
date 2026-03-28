"""
MP4 / ISO BMFF：首个顶层盒（通常为 ftyp）。

盒头：4 字节大端长度 + 4 字节类型（如 ftyp、moov）；长度含自身 8 字节。
若长度==1 表示扩展 64 位长度（本模板不展开）。
"""

from __future__ import annotations

from freeorbit.model.binary_data_model import BinaryDataModel
from freeorbit.template.builders import bytes_hex, u32_be, u64_be
from freeorbit.template.fields import FieldNode, read_u32_be


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
    if n < 8:
        return []

    out: list[FieldNode] = []
    sz = read_u32_be(model, 0)
    out.append(u32_be("first_box_size", 0, model))
    out.append(_fourcc(model, 4, "box_type"))

    if sz == 1 and n >= 16:
        out.append(u64_be("extended_size_64be", 8, model))
        return out

    typ = model.read(4, 4)
    if typ == b"ftyp" and n >= 16:
        out.append(_fourcc(model, 8, "major_brand"))
        out.append(u32_be("minor_version", 12, model))
        if n > 16 and sz >= 16:
            rest = max(0, min(sz - 16, n - 16))
            if rest > 0:
                out.append(
                    bytes_hex(
                        "compatible_brands_preview",
                        16,
                        min(rest, 64),
                        model,
                    )
                )
    elif n > 8:
        take = min(64, n - 8)
        if take > 0:
            out.append(bytes_hex("box_payload_preview", 8, take, model))
    return out
