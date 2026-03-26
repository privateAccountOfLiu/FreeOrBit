"""
示例：自定义结构模板（对齐 010「变量映射到字节」）。

加载后：带标量 dtype 的节点可在「值」列编辑，写回文件（小端）；
双击「名称/偏移」列跳转到十六进制光标；双击「值」进入编辑。
"""

from __future__ import annotations

from freeorbit.model.binary_data_model import BinaryDataModel
from freeorbit.template.builders import u16_le, u32_le
from freeorbit.template.fields import FieldNode


def build_field_tree(model: BinaryDataModel) -> list[FieldNode]:
    n = len(model)
    if n == 0:
        return []
    root: list[FieldNode] = []
    if n >= 4:
        root.append(u32_le("header0", 0, model))
    if n >= 8:
        root.append(u32_le("header1", 4, model))
    if n >= 12:
        children = [
            u16_le("word_a", 8, model),
            u16_le("word_b", 10, model),
        ]
        root.append(
            FieldNode(
                "pair_u16",
                8,
                4,
                "2 x u16 LE",
                children=children,
                dtype=None,
            )
        )
    return root
