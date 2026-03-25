"""编辑命令：与 QUndoStack 配合。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtGui import QUndoCommand

if TYPE_CHECKING:
    from freeorbit.model.binary_data_model import BinaryDataModel


class ModifyBytesCommand(QUndoCommand):
    """覆盖一段字节。"""

    def __init__(
        self,
        model: BinaryDataModel,
        offset: int,
        old_data: bytes,
        new_data: bytes,
    ) -> None:
        super().__init__("修改字节")
        self._model = model
        self._offset = offset
        self._old = old_data
        self._new = new_data

    def undo(self) -> None:
        self._model.replace_range(self._offset, self._old, mark_modified=True)

    def redo(self) -> None:
        self._model.replace_range(self._offset, self._new, mark_modified=True)

    def id(self) -> int:
        return 1001

    def mergeWith(self, other: QUndoCommand) -> bool:
        if other.id() != self.id():
            return False
        o = other
        if not isinstance(o, ModifyBytesCommand):
            return False
        # 同一字节连续半字节输入：保留最初旧值，仅更新最终新值
        if self._offset == o._offset and len(self._new) == 1 and len(o._new) == 1:
            self._new = o._new
            self.setText("修改字节")
            return True
        if self._offset + len(self._new) == o._offset:
            self._new += o._new
            self._old += o._old
            self.setText("修改字节")
            return True
        return False


class InsertBytesCommand(QUndoCommand):
    def __init__(self, model: BinaryDataModel, offset: int, data: bytes) -> None:
        super().__init__("插入字节")
        self._model = model
        self._offset = offset
        self._data = data

    def undo(self) -> None:
        self._model.delete_range(self._offset, len(self._data), mark_modified=True)

    def redo(self) -> None:
        self._model.insert_at(self._offset, self._data, mark_modified=True)


class DeleteBytesCommand(QUndoCommand):
    def __init__(self, model: BinaryDataModel, offset: int, data: bytes) -> None:
        super().__init__("删除字节")
        self._model = model
        self._offset = offset
        self._data = data

    def undo(self) -> None:
        self._model.insert_at(self._offset, self._data, mark_modified=True)

    def redo(self) -> None:
        self._model.delete_range(self._offset, len(self._data), mark_modified=True)
