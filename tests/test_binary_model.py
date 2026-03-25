"""BinaryDataModel 单元测试。"""

from __future__ import annotations

import tempfile
from pathlib import Path

from freeorbit.model.binary_data_model import BinaryDataModel


def test_memory_read_write() -> None:
    m = BinaryDataModel()
    m.load_bytes(b"\x00\x01\x02")
    assert m.read(0, 3) == b"\x00\x01\x02"
    m.replace_range(1, b"\xff")
    assert m.read_byte(1) == 0xFF


def test_insert_delete() -> None:
    m = BinaryDataModel()
    m.load_bytes(b"\xaa\xbb")
    m.insert_at(1, b"\x00\x00")
    assert bytes(m.read(0, len(m))) == b"\xaa\x00\x00\xbb"
    m.delete_range(1, 2)
    assert bytes(m.read(0, len(m))) == b"\xaa\xbb"


def test_mmap_roundtrip() -> None:
    with tempfile.NamedTemporaryFile(delete=False) as f:
        f.write(b"hello mmap test data")
        p = f.name
    try:
        m = BinaryDataModel()
        m.load_file(p, prefer_mmap=True)
        assert len(m) > 0
        assert m.read(0, 5) == b"hello"
        m.ensure_mutable_copy()
        m.replace_range(0, b"H")
        m.save_as(p)
        assert Path(p).read_bytes().startswith(b"H")
    finally:
        Path(p).unlink(missing_ok=True)


def test_undo_commands_merge() -> None:
    from freeorbit.commands.edit_commands import ModifyBytesCommand

    m = BinaryDataModel()
    m.load_bytes(b"\x00\x00")
    c1 = ModifyBytesCommand(m, 0, b"\x00", b"\x10")
    c2 = ModifyBytesCommand(m, 1, b"\x00", b"\x20")
    assert c1.mergeWith(c2) is True
    assert c1._new == b"\x10\x20"
