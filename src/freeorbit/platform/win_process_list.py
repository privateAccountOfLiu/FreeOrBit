"""
Windows 进程/窗口枚举与主模块映像基址（PSAPI）。
非 Windows 下全部返回空或 None。
"""

from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes
from dataclasses import dataclass

# 与 Windows 分支共用；非 Windows 下列表为空，仅类型保留
@dataclass(frozen=True)
class ModuleInfo:
    """已加载 PE 模块：基址、SizeOfImage、短文件名（CE 式 模块+偏移）。"""

    base: int
    size: int
    name: str


if sys.platform != "win32":  # pragma: no cover

    def list_processes() -> list[tuple[int, str]]:
        return []

    def list_windows() -> list[tuple[int, int, str]]:
        return []

    def visible_window_pids() -> set[int]:
        return set()

    def list_application_processes() -> list[tuple[int, str]]:
        return []

    def get_main_module_base(_pid: int) -> int | None:
        return None

    def get_main_module_base_and_size(_pid: int) -> tuple[int | None, int | None]:
        return None, None

    def list_loaded_modules(_pid: int) -> list[ModuleInfo]:
        return []

    def get_process_image_base_and_path(_pid: int) -> tuple[int | None, str | None]:
        return None, None

    def get_process_row_snapshot(
        _pid: int,
    ) -> tuple[int | None, str | None, int | None, int | None]:
        return None, None, None, None

    def get_process_working_set_bytes(_pid: int) -> int | None:
        return None

    def get_physical_total_bytes() -> int:
        return 0

    def get_process_proc_time_100ns(_pid: int) -> int | None:
        return None

    def get_system_times_100ns() -> tuple[int, int, int] | None:
        return None

    def get_exe_small_icon_handle(_path: str) -> int | None:
        return None

    def destroy_icon_handle(_hicon: int) -> None:
        pass

    def get_processor_count() -> int:
        return 1

    def cpu_percent_between_samples(
        _prev_proc: int,
        _cur_proc: int,
        _prev_sys: tuple[int, int, int],
        _cur_sys: tuple[int, int, int],
    ) -> float:
        return 0.0

else:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)

    TH32CS_SNAPPROCESS = 0x00000002
    MAX_PATH = 260
    MAX_TITLE = 512

    _CreateToolhelp32Snapshot = kernel32.CreateToolhelp32Snapshot
    _CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    _CreateToolhelp32Snapshot.restype = wintypes.HANDLE

    _Process32FirstW = kernel32.Process32FirstW
    _Process32NextW = kernel32.Process32NextW

    _CloseHandle = kernel32.CloseHandle
    _CloseHandle.argtypes = [wintypes.HANDLE]
    _CloseHandle.restype = wintypes.BOOL

    _OpenProcess = kernel32.OpenProcess
    _OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    _OpenProcess.restype = wintypes.HANDLE

    PROCESS_QUERY_INFORMATION = 0x0400
    PROCESS_VM_READ = 0x0010

    class PROCESSENTRY32W(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.c_size_t),
            ("th32ModuleID", wintypes.DWORD),
            ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD),
            ("pcPriClassBase", ctypes.c_long),
            ("dwFlags", wintypes.DWORD),
            ("szExeFile", wintypes.WCHAR * MAX_PATH),
        ]

    _Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
    _Process32FirstW.restype = wintypes.BOOL
    _Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
    _Process32NextW.restype = wintypes.BOOL

    _EnumWindows = user32.EnumWindows
    _IsWindowVisible = user32.IsWindowVisible
    _GetWindowTextW = user32.GetWindowTextW
    _GetWindowThreadProcessId = user32.GetWindowThreadProcessId

    WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    class MODULEINFO(ctypes.Structure):
        _fields_ = [
            ("lpBaseOfDll", ctypes.c_void_p),
            ("SizeOfImage", wintypes.DWORD),
            ("EntryPoint", ctypes.c_void_p),
        ]

    _EnumProcessModules = psapi.EnumProcessModules
    _EnumProcessModules.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(wintypes.HMODULE),
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    ]
    _EnumProcessModules.restype = wintypes.BOOL

    _GetModuleInformation = psapi.GetModuleInformation
    _GetModuleInformation.argtypes = [
        wintypes.HANDLE,
        wintypes.HMODULE,
        ctypes.POINTER(MODULEINFO),
        wintypes.DWORD,
    ]
    _GetModuleInformation.restype = wintypes.BOOL

    _GetModuleBaseNameW = psapi.GetModuleBaseNameW
    _GetModuleBaseNameW.argtypes = [
        wintypes.HANDLE,
        wintypes.HMODULE,
        wintypes.LPWSTR,
        wintypes.DWORD,
    ]
    _GetModuleBaseNameW.restype = wintypes.DWORD

    class FILETIME(ctypes.Structure):
        _fields_ = [
            ("dwLowDateTime", wintypes.DWORD),
            ("dwHighDateTime", wintypes.DWORD),
        ]

    def _ft64(ft: FILETIME) -> int:
        return int((ft.dwHighDateTime << 32) | ft.dwLowDateTime)

    _QueryFullProcessImageNameW = kernel32.QueryFullProcessImageNameW
    _QueryFullProcessImageNameW.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.LPWSTR,
        ctypes.POINTER(wintypes.DWORD),
    ]
    _QueryFullProcessImageNameW.restype = wintypes.BOOL

    _GetProcessTimes = kernel32.GetProcessTimes
    _GetProcessTimes.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(FILETIME),
        ctypes.POINTER(FILETIME),
        ctypes.POINTER(FILETIME),
        ctypes.POINTER(FILETIME),
    ]
    _GetProcessTimes.restype = wintypes.BOOL

    _GetSystemTimes = kernel32.GetSystemTimes
    _GetSystemTimes.argtypes = [
        ctypes.POINTER(FILETIME),
        ctypes.POINTER(FILETIME),
        ctypes.POINTER(FILETIME),
    ]
    _GetSystemTimes.restype = wintypes.BOOL

    class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD),
            ("PageFaultCount", wintypes.DWORD),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
        ]

    _GetProcessMemoryInfo = psapi.GetProcessMemoryInfo
    _GetProcessMemoryInfo.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(PROCESS_MEMORY_COUNTERS),
        wintypes.DWORD,
    ]
    _GetProcessMemoryInfo.restype = wintypes.BOOL

    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [
            ("dwLength", wintypes.DWORD),
            ("dwMemoryLoad", wintypes.DWORD),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    _GlobalMemoryStatusEx = kernel32.GlobalMemoryStatusEx
    _GlobalMemoryStatusEx.argtypes = [ctypes.POINTER(MEMORYSTATUSEX)]
    _GlobalMemoryStatusEx.restype = wintypes.BOOL

    shell32 = ctypes.WinDLL("shell32", use_last_error=True)

    class SHFILEINFO(ctypes.Structure):
        _fields_ = [
            ("hIcon", wintypes.HANDLE),
            ("iIcon", ctypes.c_int),
            ("dwAttributes", wintypes.DWORD),
            ("szDisplayName", wintypes.WCHAR * 260),
            ("szTypeName", wintypes.WCHAR * 80),
        ]

    SHGFI_ICON = 0x000000100
    SHGFI_SMALLICON = 0x000000001

    _SHGetFileInfoW = shell32.SHGetFileInfoW
    _SHGetFileInfoW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        ctypes.POINTER(SHFILEINFO),
        wintypes.UINT,
        wintypes.UINT,
    ]
    _SHGetFileInfoW.restype = ctypes.c_size_t

    _DestroyIcon = user32.DestroyIcon
    _DestroyIcon.argtypes = [wintypes.HANDLE]
    _DestroyIcon.restype = wintypes.BOOL

    class _SYSINFO_PROC(ctypes.Structure):
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

    _GetSystemInfoProc = kernel32.GetSystemInfo
    _GetSystemInfoProc.argtypes = [ctypes.POINTER(_SYSINFO_PROC)]
    _GetSystemInfoProc.restype = None

    def list_processes() -> list[tuple[int, str]]:
        """枚举进程：(pid, exe 文件名)。"""
        out: list[tuple[int, str]] = []
        snap = _CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
        if snap == wintypes.HANDLE(-1).value or int(snap) == -1:
            return out
        try:
            pe = PROCESSENTRY32W()
            pe.dwSize = ctypes.sizeof(PROCESSENTRY32W)
            if not _Process32FirstW(snap, ctypes.byref(pe)):
                return out
            while True:
                pid = int(pe.th32ProcessID)
                name = pe.szExeFile.strip() or f"pid{pid}"
                out.append((pid, name))
                if not _Process32NextW(snap, ctypes.byref(pe)):
                    break
        finally:
            _CloseHandle(snap)
        out.sort(key=lambda x: x[1].lower())
        return out

    def visible_window_pids() -> set[int]:
        """至少有一个可见顶层窗口的 PID 集合。"""
        pids: set[int] = set()

        def _cb(hwnd: int, _lp: int) -> bool:
            if not _IsWindowVisible(wintypes.HWND(hwnd)):
                return True
            pid = wintypes.DWORD()
            _GetWindowThreadProcessId(wintypes.HWND(hwnd), ctypes.byref(pid))
            if pid.value:
                pids.add(int(pid.value))
            return True

        cb = WNDENUMPROC(_cb)
        _EnumWindows(cb, 0)
        return pids

    def list_application_processes() -> list[tuple[int, str]]:
        """有可见窗口的进程（Applications 页近似 CE）。"""
        vis = visible_window_pids()
        return [(p, n) for p, n in list_processes() if p in vis]

    def list_windows() -> list[tuple[int, int, str]]:
        """(pid, hwnd, 窗口标题)，仅可见且标题非空。"""
        rows: list[tuple[int, int, str]] = []

        def _cb(hwnd: int, _lp: int) -> bool:
            if not _IsWindowVisible(wintypes.HWND(hwnd)):
                return True
            buf = ctypes.create_unicode_buffer(MAX_TITLE)
            n = _GetWindowTextW(wintypes.HWND(hwnd), buf, MAX_TITLE)
            if n <= 0 or not buf.value.strip():
                return True
            pid = wintypes.DWORD()
            _GetWindowThreadProcessId(wintypes.HWND(hwnd), ctypes.byref(pid))
            if pid.value:
                rows.append((int(pid.value), int(hwnd), buf.value.strip()))
            return True

        cb = WNDENUMPROC(_cb)
        _EnumWindows(cb, 0)
        rows.sort(key=lambda x: (x[2].lower(), x[0]))
        return rows

    def get_process_row_snapshot(
        pid: int,
    ) -> tuple[int | None, str | None, int | None, int | None]:
        """一次 OpenProcess：映像基址、主模块路径、工作集字节、进程 CPU 时间(100ns 内核+用户)。"""
        access = PROCESS_QUERY_INFORMATION | PROCESS_VM_READ
        h = _OpenProcess(access, False, wintypes.DWORD(pid))
        if not h:
            return None, None, None, None
        try:
            path: str | None = None
            buf = ctypes.create_unicode_buffer(65536)
            sz = wintypes.DWORD(len(buf))
            if _QueryFullProcessImageNameW(wintypes.HANDLE(h), 0, buf, ctypes.byref(sz)):
                path = buf.value
            base: int | None = None
            mods = (wintypes.HMODULE * 1)()
            needed = wintypes.DWORD()
            if _EnumProcessModules(
                h,
                ctypes.cast(mods, ctypes.POINTER(wintypes.HMODULE)),
                ctypes.sizeof(mods),
                ctypes.byref(needed),
            ):
                mi = MODULEINFO()
                if _GetModuleInformation(
                    h, mods[0], ctypes.byref(mi), ctypes.sizeof(MODULEINFO)
                ):
                    b = ctypes.cast(mi.lpBaseOfDll, ctypes.c_void_p).value
                    base = int(b) if b is not None else None
            pmc = PROCESS_MEMORY_COUNTERS()
            pmc.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
            ws: int | None = None
            if _GetProcessMemoryInfo(
                wintypes.HANDLE(h), ctypes.byref(pmc), ctypes.sizeof(pmc)
            ):
                ws = int(pmc.WorkingSetSize)
            c = FILETIME()
            e = FILETIME()
            k = FILETIME()
            u = FILETIME()
            pt: int | None = None
            if _GetProcessTimes(
                wintypes.HANDLE(h),
                ctypes.byref(c),
                ctypes.byref(e),
                ctypes.byref(k),
                ctypes.byref(u),
            ):
                pt = _ft64(k) + _ft64(u)
            return base, path, ws, pt
        finally:
            _CloseHandle(h)

    def get_process_image_base_and_path(pid: int) -> tuple[int | None, str | None]:
        b, p, _ws, _pt = get_process_row_snapshot(pid)
        return b, p

    def get_main_module_base(pid: int) -> int | None:
        """主模块映像基址（首个模块的 lpBaseOfDll）；失败返回 None。"""
        b, _ = get_process_image_base_and_path(pid)
        return b

    def get_main_module_base_and_size(pid: int) -> tuple[int | None, int | None]:
        """主模块 lpBaseOfDll 与 SizeOfImage（PE 映像大小）；用于判断 VA 是否落在主模块内（对齐 CE 模块+偏移）。"""
        access = PROCESS_QUERY_INFORMATION | PROCESS_VM_READ
        h = _OpenProcess(access, False, wintypes.DWORD(pid))
        if not h:
            return None, None
        try:
            mods = (wintypes.HMODULE * 1)()
            needed = wintypes.DWORD()
            if not _EnumProcessModules(
                h,
                ctypes.cast(mods, ctypes.POINTER(wintypes.HMODULE)),
                ctypes.sizeof(mods),
                ctypes.byref(needed),
            ):
                return None, None
            mi = MODULEINFO()
            if not _GetModuleInformation(
                h, mods[0], ctypes.byref(mi), ctypes.sizeof(MODULEINFO)
            ):
                return None, None
            b = ctypes.cast(mi.lpBaseOfDll, ctypes.c_void_p).value
            base = int(b) if b is not None else None
            sz = int(mi.SizeOfImage)
            if base is None or sz <= 0:
                return None, None
            return base, sz
        finally:
            _CloseHandle(h)

    def list_loaded_modules(pid: int) -> list[ModuleInfo]:
        """枚举进程已加载模块（EnumProcessModules + GetModuleInformation + GetModuleBaseNameW）。"""
        access = PROCESS_QUERY_INFORMATION | PROCESS_VM_READ
        h = _OpenProcess(access, False, wintypes.DWORD(pid))
        if not h:
            return []
        try:
            # 首次 cb=0：常返回 FALSE，但 cbNeeded 仍为所需字节数
            cb_needed = wintypes.DWORD()
            _EnumProcessModules(h, None, 0, ctypes.byref(cb_needed))
            if cb_needed.value == 0:
                return []
            n_bytes = int(cb_needed.value)
            n_mods = n_bytes // ctypes.sizeof(wintypes.HMODULE)
            if n_mods <= 0:
                return []
            h_mods = (wintypes.HMODULE * n_mods)()
            cb2 = wintypes.DWORD(ctypes.sizeof(h_mods))
            if not _EnumProcessModules(
                h,
                ctypes.cast(h_mods, ctypes.POINTER(wintypes.HMODULE)),
                cb2,
                ctypes.byref(cb2),
            ):
                return []
            count = cb2.value // ctypes.sizeof(wintypes.HMODULE)
            out: list[ModuleInfo] = []
            name_buf = ctypes.create_unicode_buffer(MAX_PATH)
            for i in range(count):
                mod = h_mods[i]
                mi = MODULEINFO()
                if not _GetModuleInformation(
                    h, mod, ctypes.byref(mi), ctypes.sizeof(MODULEINFO)
                ):
                    continue
                b = ctypes.cast(mi.lpBaseOfDll, ctypes.c_void_p).value
                base = int(b) if b is not None else None
                sz = int(mi.SizeOfImage)
                if base is None or sz <= 0:
                    continue
                if _GetModuleBaseNameW(h, mod, name_buf, MAX_PATH) == 0:
                    name = "?"
                else:
                    name = name_buf.value or "?"
                out.append(ModuleInfo(base=base, size=sz, name=name))
            return out
        finally:
            _CloseHandle(h)

    def get_process_working_set_bytes(pid: int) -> int | None:
        _b, _p, ws, _pt = get_process_row_snapshot(pid)
        return ws

    def get_physical_total_bytes() -> int:
        ms = MEMORYSTATUSEX()
        ms.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        if not _GlobalMemoryStatusEx(ctypes.byref(ms)):
            return 0
        return int(ms.ullTotalPhys)

    def get_process_proc_time_100ns(pid: int) -> int | None:
        _b, _p, _ws, pt = get_process_row_snapshot(pid)
        return pt

    def get_system_times_100ns() -> tuple[int, int, int] | None:
        idle = FILETIME()
        k = FILETIME()
        u = FILETIME()
        if not _GetSystemTimes(ctypes.byref(idle), ctypes.byref(k), ctypes.byref(u)):
            return None
        return _ft64(idle), _ft64(k), _ft64(u)

    def get_exe_small_icon_handle(path: str) -> int | None:
        if not path:
            return None
        fi = SHFILEINFO()
        r = _SHGetFileInfoW(
            path, 0, ctypes.byref(fi), ctypes.sizeof(fi), SHGFI_ICON | SHGFI_SMALLICON
        )
        if r == 0:
            return None
        ih = int(fi.hIcon)
        return ih if ih else None

    def destroy_icon_handle(hicon: int) -> None:
        if hicon:
            _DestroyIcon(wintypes.HANDLE(hicon))

    def get_processor_count() -> int:
        si = _SYSINFO_PROC()
        _GetSystemInfoProc(ctypes.byref(si))
        return max(1, int(si.dwNumberOfProcessors))

    def cpu_percent_between_samples(
        prev_proc: int,
        cur_proc: int,
        prev_sys: tuple[int, int, int],
        cur_sys: tuple[int, int, int],
    ) -> float:
        dp = cur_proc - prev_proc
        if dp < 0:
            dp = 0
        idle_d = cur_sys[0] - prev_sys[0]
        k_d = cur_sys[1] - prev_sys[1]
        u_d = cur_sys[2] - prev_sys[2]
        sys_busy = k_d + u_d - idle_d
        if sys_busy <= 0:
            return 0.0
        return min(100.0, 100.0 * dp / sys_busy)


def resolve_va_to_module(va: int, modules: list[ModuleInfo]) -> ModuleInfo | None:
    """若 va 落在某一模块 [base, base+size) 内则返回该模块；多区间重叠时取 base 最大者（最后装入）。"""
    if not modules:
        return None
    candidates = [m for m in modules if m.base <= va < m.base + m.size]
    if not candidates:
        return None
    return max(candidates, key=lambda m: m.base)
