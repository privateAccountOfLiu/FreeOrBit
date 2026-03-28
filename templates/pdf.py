"""
PDF：文件头 %PDF-x.y 及首行预览。

规范要求以 ASCII 百分号文本 %PDF-1.x 开头（后可有换行）。
"""

from __future__ import annotations

from freeorbit.model.binary_data_model import BinaryDataModel
from freeorbit.template.builders import bytes_hex
from freeorbit.template.fields import FieldNode


def build_field_tree(model: BinaryDataModel) -> list[FieldNode]:
    n = len(model)
    if n < 5:
        return []

    head = model.read(0, min(32, n))
    if not head.startswith(b"%PDF"):
        return [
            FieldNode(
                "提示",
                0,
                0,
                "非 PDF 头（应以 %PDF- 开头）",
                dtype=None,
            )
        ]

    out: list[FieldNode] = []
    # 首行：到 \r 或 \n
    line_end = len(head)
    for i, c in enumerate(head):
        if c in (0x0D, 0x0A):
            line_end = i
            break
    first_line = head[:line_end].decode("latin-1", errors="replace")
    out.append(
        FieldNode(
            "header_line",
            0,
            line_end,
            first_line,
            dtype=None,
        )
    )
    if n > line_end:
        out.append(bytes_hex("after_header_preview", line_end, min(32, n - line_end), model))
    return out
