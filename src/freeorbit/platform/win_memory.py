"""
Windows 进程虚拟内存读写（ReadProcessMemory / WriteProcessMemory）。
需目标进程与权限允许；失败时抛出 OSError。
"""

from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes

if sys.platform != "win32":  # pragma: no cover - 非 Windows CI

    def is_windows() -> bool:
        return False

    def open_process(_pid: int) -> int:
        raise OSError("仅 Windows 支持进程内存")

    def close_handle(_h: int) -> None:
        pass

    def read_process_memory(_h: int, _base: int, _size: int) -> bytes:
        raise OSError("仅 Windows 支持进程内存")

    def write_process_memory(_h: int, _base: int, _data: bytes) -> None:
        raise OSError("仅 Windows 支持进程内存")

else:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    PROCESS_VM_READ = 0x0010
    PROCESS_VM_WRITE = 0x0020
    PROCESS_VM_OPERATION = 0x0008
    PROCESS_QUERY_INFORMATION = 0x0400

    _OpenProcess = kernel32.OpenProcess
    _OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    _OpenProcess.restype = wintypes.HANDLE

    _ReadProcessMemory = kernel32.ReadProcessMemory
    _ReadProcessMemory.argtypes = [
        wintypes.HANDLE,
        wintypes.LPCVOID,
        wintypes.LPVOID,
        ctypes.c_size_t,
        ctypes.POINTER(ctypes.c_size_t),
    ]
    _ReadProcessMemory.restype = wintypes.BOOL

    _WriteProcessMemory = kernel32.WriteProcessMemory
    _WriteProcessMemory.argtypes = [
        wintypes.HANDLE,
        wintypes.LPVOID,
        wintypes.LPCVOID,
        ctypes.c_size_t,
        ctypes.POINTER(ctypes.c_size_t),
    ]
    _WriteProcessMemory.restype = wintypes.BOOL

    _CloseHandle = kernel32.CloseHandle
    _CloseHandle.argtypes = [wintypes.HANDLE]
    _CloseHandle.restype = wintypes.BOOL

    def is_windows() -> bool:
        return True

    def open_process(pid: int) -> int:
        access = (
            PROCESS_VM_READ
            | PROCESS_VM_WRITE
            | PROCESS_VM_OPERATION
            | PROCESS_QUERY_INFORMATION
        )
        h = _OpenProcess(access, False, pid)
        if not h:
            err = ctypes.get_last_error()
            raise OSError(err, f"OpenProcess 失败 (pid={pid})，可能需要管理员或以管理员运行目标)")
        return int(h)

    def close_handle(h: int) -> None:
        if h:
            _CloseHandle(wintypes.HANDLE(h))

    def read_process_memory(h_process: int, base: int, size: int) -> bytes:
        if size <= 0 or size > 64 * 1024 * 1024:
            raise ValueError("读取长度无效或过大（最大 64MB）")
        buf = ctypes.create_string_buffer(size)
        nread = ctypes.c_size_t(0)
        ok = _ReadProcessMemory(
            wintypes.HANDLE(h_process),
            ctypes.c_void_p(base),
            buf,
            ctypes.c_size_t(size),
            ctypes.byref(nread),
        )
        if not ok:
            raise OSError(ctypes.get_last_error(), "ReadProcessMemory 失败（地址可能不可读）")
        return buf.raw[: nread.value]

    def write_process_memory(h_process: int, base: int, data: bytes) -> None:
        if not data:
            return
        buf = ctypes.create_string_buffer(data)
        nwritten = ctypes.c_size_t(0)
        ok = _WriteProcessMemory(
            wintypes.HANDLE(h_process),
            ctypes.c_void_p(base),
            buf,
            ctypes.c_size_t(len(data)),
            ctypes.byref(nwritten),
        )
        if not ok:
            raise OSError(ctypes.get_last_error(), "WriteProcessMemory 失败（页可能不可写）")
        if nwritten.value != len(data):
            raise OSError("WriteProcessMemory 未写完")
