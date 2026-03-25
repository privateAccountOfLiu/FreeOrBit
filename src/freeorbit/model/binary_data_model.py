"""二进制数据模型：内存缓冲区与可选 mmap 大文件访问。"""

from __future__ import annotations

import mmap
from pathlib import Path
from typing import BinaryIO, Optional

from PySide6.QtCore import QObject, Signal


class BinaryDataModel(QObject):
    """底层字节存储，发出 data_changed(start, length) 供视图刷新。"""

    data_changed = Signal(int, int)  # 起始偏移、连续长度
    file_path_changed = Signal()
    modified_changed = Signal(bool)

    # 超过此字节数打开文件时优先使用 mmap（只读或读写依实现）
    MMAP_THRESHOLD = 8 * 1024 * 1024

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._path: Optional[Path] = None
        self._buffer = bytearray()
        self._mmap: Optional[mmap.mmap] = None
        self._mmap_file: Optional[BinaryIO] = None
        self._use_mmap = False
        self._modified = False

    @property
    def file_path(self) -> Optional[Path]:
        return self._path

    @property
    def modified(self) -> bool:
        return self._modified

    def _set_modified(self, value: bool) -> None:
        if self._modified != value:
            self._modified = value
            self.modified_changed.emit(value)

    def __len__(self) -> int:
        if self._use_mmap and self._mmap is not None:
            return len(self._mmap)
        return len(self._buffer)

    def read(self, offset: int, length: int) -> bytes:
        if length <= 0:
            return b""
        n = len(self)
        if offset >= n:
            return b""
        end = min(offset + length, n)
        if self._use_mmap and self._mmap is not None:
            return bytes(self._mmap[offset:end])
        return bytes(self._buffer[offset:end])

    def read_byte(self, offset: int) -> int:
        if offset < 0 or offset >= len(self):
            return 0
        if self._use_mmap and self._mmap is not None:
            return self._mmap[offset]
        return self._buffer[offset]

    def clear(self) -> None:
        self._close_mmap()
        self._buffer = bytearray()
        self._path = None
        self._set_modified(False)
        self.file_path_changed.emit()
        self.data_changed.emit(0, 0)

    def _close_mmap(self) -> None:
        if self._mmap is not None:
            self._mmap.close()
            self._mmap = None
        if self._mmap_file is not None:
            self._mmap_file.close()
            self._mmap_file = None
        self._use_mmap = False

    def load_file(
        self,
        path: str | Path,
        *,
        prefer_mmap: bool | None = None,
    ) -> None:
        """从路径加载文件。大文件默认 mmap；否则读入内存。"""
        self._close_mmap()
        p = Path(path).resolve()
        size = p.stat().st_size
        use_mmap = prefer_mmap if prefer_mmap is not None else size >= self.MMAP_THRESHOLD

        if use_mmap and size > 0:
            # 读写映射以便覆盖写入；插入/删除需复制到内存（见 ensure_mutable_copy）
            f = open(p, "r+b")
            self._mmap_file = f
            self._mmap = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_WRITE)
            self._use_mmap = True
            self._buffer = bytearray()
        else:
            self._buffer = bytearray(p.read_bytes()) if size > 0 else bytearray()
            self._use_mmap = False

        self._path = p
        self._set_modified(False)
        self.file_path_changed.emit()
        self.data_changed.emit(0, len(self))

    def load_bytes(self, data: bytes, path: Optional[Path] = None) -> None:
        self._close_mmap()
        self._buffer = bytearray(data)
        self._path = path
        self._set_modified(False)
        self.file_path_changed.emit()
        self.data_changed.emit(0, len(self))

    def ensure_mutable_copy(self) -> None:
        """从 mmap 转为内存缓冲区，以支持插入/删除等修改。"""
        if not self._use_mmap:
            return
        if self._mmap is None:
            return
        self._buffer = bytearray(self._mmap[:])
        self._close_mmap()
        self._set_modified(True)
        self.data_changed.emit(0, len(self))

    def save_as(self, path: str | Path) -> None:
        """将当前数据写入路径。"""
        p = Path(path)
        data = self.read(0, len(self))
        p.write_bytes(data)
        self._path = p.resolve()
        self._set_modified(False)
        self.file_path_changed.emit()

    def replace_range(self, offset: int, data: bytes, *, mark_modified: bool = True) -> None:
        """覆盖 [offset, offset+len(data))，长度必须等于现有区间长度（不扩展文件）。"""
        if self._use_mmap:
            self.ensure_mutable_copy()
        n = len(data)
        if offset < 0 or offset + n > len(self._buffer):
            raise IndexError("replace_range 越界")
        self._buffer[offset : offset + n] = data
        if mark_modified:
            self._set_modified(True)
        self.data_changed.emit(offset, n)

    def insert_at(self, offset: int, data: bytes, *, mark_modified: bool = True) -> None:
        if self._use_mmap:
            self.ensure_mutable_copy()
        if offset < 0 or offset > len(self._buffer):
            raise IndexError("insert_at 越界")
        self._buffer[offset:offset] = data
        if mark_modified:
            self._set_modified(True)
        self.data_changed.emit(offset, len(self._buffer) - offset)

    def delete_range(self, offset: int, count: int, *, mark_modified: bool = True) -> None:
        if self._use_mmap:
            self.ensure_mutable_copy()
        if count <= 0:
            return
        if offset < 0 or offset + count > len(self._buffer):
            raise IndexError("delete_range 越界")
        del self._buffer[offset : offset + count]
        if mark_modified:
            self._set_modified(True)
        self.data_changed.emit(offset, len(self._buffer) - offset + count)
