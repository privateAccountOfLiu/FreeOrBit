"""
ZIP：本地文件头（PK\\x03\\x04）— 常用于 .zip、.docx、.apk 等。

偏移：版本、标志、压缩方法、时间、CRC、压缩/未压缩大小、文件名长、扩展区长等。
"""

from __future__ import annotations

from freeorbit.model.binary_data_model import BinaryDataModel
from freeorbit.template.builders import bytes_hex, u16_le, u32_le
from freeorbit.template.fields import FieldNode


def build_field_tree(model: BinaryDataModel) -> list[FieldNode]:
    n = len(model)
    if n < 30:
        return []

    sig = model.read(0, 4)
    out: list[FieldNode] = []
    out.append(bytes_hex("local_file_header_sig", 0, 4, model))
    if sig != b"PK\x03\x04":
        return [
            FieldNode(
                "提示",
                0,
                0,
                "非 ZIP 本地文件头（应以 50 4B 03 04 开头）",
                dtype=None,
            )
        ]

    out.append(u16_le("version_needed", 4, model))
    out.append(u16_le("general_purpose_bit_flag", 6, model))
    out.append(u16_le("compression_method", 8, model))
    out.append(u16_le("last_mod_file_time", 10, model))
    out.append(u16_le("last_mod_file_date", 12, model))
    out.append(u32_le("crc32", 14, model))
    out.append(u32_le("compressed_size", 18, model))
    out.append(u32_le("uncompressed_size", 22, model))
    out.append(u16_le("file_name_length", 26, model))
    out.append(u16_le("extra_field_length", 28, model))

    fn_len = model.read_byte(26) | (model.read_byte(27) << 8)
    x_len = model.read_byte(28) | (model.read_byte(29) << 8)
    start = 30
    if start + fn_len <= n:
        raw = model.read(start, fn_len)
        try:
            name = raw.decode("utf-8", errors="replace")
        except Exception:
            name = raw.hex().upper()
        out.append(
            FieldNode(
                "file_name",
                start,
                fn_len,
                name,
                dtype=None,
            )
        )
    return out
