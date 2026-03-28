"""
GIF：签名 GIF87a / GIF89a + 逻辑屏幕描述符（宽、高、标志、背景色、像素宽高比）。
"""

from __future__ import annotations

from freeorbit.model.binary_data_model import BinaryDataModel
from freeorbit.template.builders import bytes_hex, u16_le
from freeorbit.template.fields import FieldNode


def build_field_tree(model: BinaryDataModel) -> list[FieldNode]:
    n = len(model)
    if n < 13:
        return []

    sig = model.read(0, 6)
    out: list[FieldNode] = []
    out.append(bytes_hex("GIF_signature", 0, 6, model))
    if sig not in (b"GIF87a", b"GIF89a"):
        out.append(
            FieldNode(
                "提示",
                0,
                0,
                "非 GIF 签名（应为 GIF87a 或 GIF89a）",
                dtype=None,
            )
        )
        return out

    out.append(u16_le("logical_screen_width", 6, model))
    out.append(u16_le("logical_screen_height", 8, model))
    out.append(FieldNode("packed_fields", 10, 1, f"0x{model.read_byte(10):02X}", dtype="u8"))
    out.append(FieldNode("background_color_index", 11, 1, f"{model.read_byte(11)}", dtype="u8"))
    out.append(FieldNode("pixel_aspect_ratio", 12, 1, f"{model.read_byte(12)}", dtype="u8"))
    return out
