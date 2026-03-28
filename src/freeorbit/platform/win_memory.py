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

    def list_readable_regions(_pid: int, _max_regions: int = 500) -> list[tuple[int, int, str]]:
        raise OSError("仅 Windows 支持进程内存")

    def get_system_page_size() -> int:
        return 4096

    def align_address_to_page(addr: int, page_size: int) -> int:
        if page_size <= 0:
            return addr
        return addr & ~(page_size - 1)

    def clamp_read_in_region(_pid: int, _page_base: int, max_bytes: int) -> int:
        return max_bytes

    def first_readable_page_base(_pid: int) -> int | None:
        return None

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

    MEM_COMMIT = 0x1000
    PAGE_NOACCESS = 0x01
    PAGE_GUARD = 0x100

    class MEMORY_BASIC_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("BaseAddress", ctypes.c_void_p),
            ("AllocationBase", ctypes.c_void_p),
            ("AllocationProtect", wintypes.DWORD),
            ("RegionSize", ctypes.c_size_t),
            ("State", wintypes.DWORD),
            ("Protect", wintypes.DWORD),
            ("Type", wintypes.DWORD),
        ]

    _VirtualQueryEx = kernel32.VirtualQueryEx
    _VirtualQueryEx.argtypes = [
        wintypes.HANDLE,
        ctypes.c_void_p,
        ctypes.POINTER(MEMORY_BASIC_INFORMATION),
        ctypes.c_size_t,
    ]
    _VirtualQueryEx.restype = ctypes.c_size_t

    def _protect_str(fl: int) -> str:
        # 低字节为页类型；PAGE_GUARD 等为高位标志
        if fl & 0xFF == PAGE_NOACCESS:
            return "NOACCESS"
        parts: list[str] = []
        if fl & PAGE_GUARD:
            parts.append("GUARD")
        p = fl & 0xFF
        m = {
            0x02: "R",
            0x04: "RW",
            0x08: "WCOPY",
            0x10: "X",
            0x20: "RX",
            0x40: "RWX",
            0x80: "WXCOPY",
        }
        parts.append(m.get(p, f"0x{p:02X}"))
        return "|".join(parts)

    def _region_readable(protect: int) -> bool:
        if protect == 0 or (protect & PAGE_GUARD):
            return False
        p = protect & 0xFF
        return p not in (0, PAGE_NOACCESS)

    def list_readable_regions(pid: int, max_regions: int = 500) -> list[tuple[int, int, str]]:
        """枚举目标进程可读已提交区域，返回 (基址, 长度, 保护说明)。"""
        h = open_process(pid)
        try:
            out: list[tuple[int, int, str]] = []
            addr = 0
            mbi = MEMORY_BASIC_INFORMATION()
            while len(out) < max_regions:
                r = _VirtualQueryEx(
                    wintypes.HANDLE(h),
                    ctypes.c_void_p(addr),
                    ctypes.byref(mbi),
                    ctypes.sizeof(mbi),
                )
                if r == 0:
                    break
                base = ctypes.cast(mbi.BaseAddress, ctypes.c_void_p).value or 0
                rsize = int(mbi.RegionSize)
                if (
                    mbi.State == MEM_COMMIT
                    and _region_readable(int(mbi.Protect))
                    and rsize > 0
                ):
                    out.append((base, rsize, _protect_str(int(mbi.Protect))))
                if rsize <= 0:
                    break
                addr = base + rsize
                if addr <= base:
                    break
            return out
        finally:
            close_handle(h)

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

    class _SYSTEM_INFO(ctypes.Structure):
        _fields_ = [
            ("wProcessorArchitecture", wintypes.WORD),
            ("wReserved", wintypes.WORD),
            ("dwPageSize", wintypes.DWORD),
            ("lpMinimumApplicationAddress", ctypes.c_void_p),
            ("lpMaximumApplicationAddress", ctypes.c_void_p),
            ("dwActiveProcessorMask", ctypes.c_size_t),
            ("dwNumberOfProcessors", wintypes.DWORD),
            ("dwProcessorType", wintypes.DWORD),
            ("dwAllocationGranularity", wintypes.DWORD),
            ("wProcessorLevel", wintypes.WORD),
            ("wProcessorRevision", wintypes.WORD),
        ]

    _GetSystemInfo = kernel32.GetSystemInfo
    _GetSystemInfo.argtypes = [ctypes.POINTER(_SYSTEM_INFO)]
    _GetSystemInfo.restype = None

    def get_system_page_size() -> int:
        si = _SYSTEM_INFO()
        _GetSystemInfo(ctypes.byref(si))
        ps = int(si.dwPageSize)
        return ps if ps > 0 else 4096

    def align_address_to_page(addr: int, page_size: int) -> int:
        if page_size <= 0:
            return addr
        return addr & ~(page_size - 1)

    def clamp_read_in_region(pid: int, page_base: int, max_bytes: int) -> int:
        """在可读已提交区内，从 page_base 起最多可读的字节数（不超过 max_bytes）。

        对 page_base 直接 VirtualQueryEx，不依赖 list_readable_regions 的前 N 条枚举，
        否则高地址（如映像基址）常落在「500 个可读区」之外导致误判为不可读。
        """
        h = open_process(pid)
        try:
            mbi = MEMORY_BASIC_INFORMATION()
            r = _VirtualQueryEx(
                wintypes.HANDLE(h),
                ctypes.c_void_p(page_base),
                ctypes.byref(mbi),
                ctypes.sizeof(mbi),
            )
            if r == 0:
                return 0
            base = ctypes.cast(mbi.BaseAddress, ctypes.c_void_p).value or 0
            rsize = int(mbi.RegionSize)
            if rsize <= 0:
                return 0
            if mbi.State != MEM_COMMIT or not _region_readable(int(mbi.Protect)):
                return 0
            end = base + rsize
            if not (base <= page_base < end):
                return 0
            return min(max_bytes, end - page_base)
        finally:
            close_handle(h)

    def first_readable_page_base(pid: int) -> int | None:
        """枚举虚拟地址空间，返回首段可读已提交区所在页的页对齐基址（用于默认打开）。"""
        ps = get_system_page_size()
        h = open_process(pid)
        try:
            addr = 0
            mbi = MEMORY_BASIC_INFORMATION()
            while True:
                r = _VirtualQueryEx(
                    wintypes.HANDLE(h),
                    ctypes.c_void_p(addr),
                    ctypes.byref(mbi),
                    ctypes.sizeof(mbi),
                )
                if r == 0:
                    return None
                base = ctypes.cast(mbi.BaseAddress, ctypes.c_void_p).value or 0
                rsize = int(mbi.RegionSize)
                if rsize <= 0:
                    return None
                if (
                    mbi.State == MEM_COMMIT
                    and _region_readable(int(mbi.Protect))
                    and rsize > 0
                ):
                    return align_address_to_page(base, ps)
                addr = base + rsize
                if addr <= base:
                    return None
        finally:
            close_handle(h)
