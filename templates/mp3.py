"""
MP3：ID3v2 标签头（若以「ID3」开头）或首个 MPEG 音频帧同步字（0xFF Ex）。

ID3v2：版本、标志、Synchsafe 标签大小（不含 10 字节头）。
"""

from __future__ import annotations

from freeorbit.model.binary_data_model import BinaryDataModel
from freeorbit.template.builders import bytes_hex
from freeorbit.template.fields import FieldNode


def _id3_syncsafe_size(model: BinaryDataModel, o: int) -> int:
    """4 字节 synchsafe 整数（每字节仅低 7 位有效）。"""
    b = model.read(o, 4)
    if len(b) < 4:
        return 0
    return (b[0] << 21) | (b[1] << 14) | (b[2] << 7) | b[3]


def build_field_tree(model: BinaryDataModel) -> list[FieldNode]:
    n = len(model)
    if n < 4:
        return []

    out: list[FieldNode] = []

    if model.read(0, 3) == b"ID3" and n >= 10:
        out.append(bytes_hex("ID3_magic", 0, 3, model))
        out.append(FieldNode("id3_major", 3, 1, f"{model.read_byte(3)}", dtype="u8"))
        out.append(FieldNode("id3_revision", 4, 1, f"{model.read_byte(4)}", dtype="u8"))
        out.append(FieldNode("id3_flags", 5, 1, f"0x{model.read_byte(5):02X}", dtype="u8"))
        tag_body = _id3_syncsafe_size(model, 6)
        out.append(
            FieldNode(
                "id3_tag_size_synchsafe",
                6,
                4,
                f"{tag_body} 字节（不含 10 字节头）",
                dtype=None,
            )
        )
        if n > 10:
            out.append(bytes_hex("id3_body_preview", 10, min(32, n - 10), model))
        return out

    # MPEG-1/2 Layer 帧头：12 位同步 1 + 其余
    b0, b1 = model.read_byte(0), model.read_byte(1)
    if b0 == 0xFF and (b1 & 0xE0) == 0xE0:
        out.append(bytes_hex("mpeg_frame_header", 0, min(4, n), model))
        return out

    out.append(
        FieldNode(
            "提示",
            0,
            0,
            "未识别为 ID3v2 头或 MPEG 同步帧（FF Ex，x∈E0–FF）",
            dtype=None,
        )
    )
    out.append(bytes_hex("file_start_preview", 0, min(16, n), model))
    return out
