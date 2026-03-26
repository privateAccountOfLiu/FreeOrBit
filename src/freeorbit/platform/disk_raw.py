"""
原始磁盘 / 卷设备按字节偏移读写（需管理员权限，误操作可破坏数据）。
"""

from __future__ import annotations

import os
from pathlib import Path


def normalize_device_path(user: str) -> str:
    r"""接受 \\.\PhysicalDrive0、PhysicalDrive0、\\.\C: 等形式。"""
    s = user.strip()
    if s.startswith("\\\\.\\") or s.startswith("\\\\?\\"):
        return s
    if s[:1].isalpha() and len(s) == 2 and s[1] == ":":
        return f"\\\\.\\{s}"
    if s.lower().startswith("physicaldrive"):
        return "\\\\.\\" + s
    return s


def read_device_range(path: str, offset: int, size: int) -> bytes:
    if offset < 0 or size < 0:
        raise ValueError("offset/size 无效")
    if size > 64 * 1024 * 1024:
        raise ValueError("单次读取最大 64MB")
    p = normalize_device_path(path)
    # os.open 二进制无缓冲，便于定位大偏移
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
    fd = os.open(p, flags)
    try:
        os.lseek(fd, offset, os.SEEK_SET)
        return os.read(fd, size)
    finally:
        os.close(fd)


def write_device_range(path: str, offset: int, data: bytes) -> None:
    if offset < 0:
        raise ValueError("offset 无效")
    p = normalize_device_path(path)
    flags = os.O_RDWR | getattr(os, "O_BINARY", 0)
    fd = os.open(p, flags)
    try:
        os.lseek(fd, offset, os.SEEK_SET)
        written = 0
        while written < len(data):
            n = os.write(fd, data[written:])
            if n <= 0:
                raise OSError("写入中断")
            written += n
    finally:
        os.close(fd)


def display_path_for_tab(device_path: str, offset: int) -> Path:
    """用于标签页展示的稳定伪路径。"""
    safe = device_path.replace("\\", "_").replace(":", "")[:48]
    return Path(f"disk_{safe}@{offset:#x}")
