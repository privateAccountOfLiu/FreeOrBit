"""示例：结构面板「加载模板」用 .py 文件。

在模板中实现 build_field_tree(model)，返回 list[FieldNode]。
运行 FreeOrBit 时需能 import freeorbit（开发时 PYTHONPATH=src 或 pip install -e .）。

用法：结构面板 → 加载模板… → 选本文件。
"""

from __future__ import annotations

from freeorbit.model.binary_data_model import BinaryDataModel
from freeorbit.template.fields import FieldNode, read_u32_le


def build_field_tree(model: BinaryDataModel) -> list[FieldNode]:
    """解析文件头 16 字节为 4 个小端 DWORD（示例）。"""
    out: list[FieldNode] = []
    n = len(model)
    for i in range(4):
        off = i * 4
        if off + 4 > n:
            break
        v = read_u32_le(model, off)
        out.append(
            FieldNode(f"dword_{i}", off, 4, f"0x{v:08X} ({v})"),
        )
    if not out:
        out.append(FieldNode("(empty)", 0, 0, "—"))
    return out