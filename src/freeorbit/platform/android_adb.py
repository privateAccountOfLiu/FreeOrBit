"""主机侧 ADB 封装（子进程调用 `adb`），不依赖第三方 Python 包。

需本机已安装 Android SDK platform-tools 并将 `adb` 加入 PATH，或填写可执行文件绝对路径。
"""

from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class AdbDevice:
    """`adb devices` 中的一行。"""

    serial: str
    state: str


def run_adb(
    args: list[str],
    *,
    adb_exe: str = "adb",
    timeout: float = 60.0,
) -> tuple[int, str, str]:
    """执行 `adb` + 参数，返回 (退出码, stdout, stderr)。"""
    cmd = [adb_exe, *args]
    kw: dict = {}
    if sys.platform == "win32":
        kw["creationflags"] = subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]
    try:
        p = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            **kw,
        )
        return p.returncode, p.stdout or "", p.stderr or ""
    except FileNotFoundError as e:
        raise OSError(f"找不到 adb 可执行文件: {adb_exe}") from e
    except subprocess.TimeoutExpired as e:
        raise TimeoutError(f"adb 超时 ({timeout}s): {' '.join(cmd)}") from e


def list_devices(adb_exe: str = "adb") -> list[AdbDevice]:
    """解析 `adb devices -l` 输出。"""
    code, out, err = run_adb(["devices", "-l"], adb_exe=adb_exe, timeout=15.0)
    if code != 0:
        raise RuntimeError(err.strip() or out.strip() or f"adb devices 退出码 {code}")
    rows: list[AdbDevice] = []
    for line in out.splitlines():
        line = line.strip()
        if not line or line.startswith("List of devices"):
            continue
        # serial \t state [ ... ]
        parts = re.split(r"\s+", line, maxsplit=1)
        if len(parts) >= 2:
            serial, rest = parts[0], parts[1]
            state = rest.split()[0] if rest.split() else "unknown"
            rows.append(AdbDevice(serial=serial, state=state))
    return rows


def shell(
    serial: Optional[str],
    shell_cmd: str,
    *,
    adb_exe: str = "adb",
    timeout: float = 60.0,
) -> str:
    """在设备上执行 `adb shell` 单行命令，返回标准输出文本。"""
    args = []
    if serial:
        args.extend(["-s", serial])
    args.extend(["shell", shell_cmd])
    code, out, err = run_adb(args, adb_exe=adb_exe, timeout=timeout)
    if code != 0:
        msg = (err or out).strip() or f"退出码 {code}"
        raise RuntimeError(msg)
    return out


def list_packages(
    serial: Optional[str],
    *,
    adb_exe: str = "adb",
    third_party_only: bool = False,
) -> list[str]:
    """已安装包名列表（`pm list packages`）。"""
    flag = "-3" if third_party_only else ""
    cmd = f"pm list packages {flag}".strip()
    text = shell(serial, cmd, adb_exe=adb_exe, timeout=120.0)
    names: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("package:"):
            names.append(line.split("package:", 1)[1].strip())
    return sorted(names)


def list_processes_ps(
    serial: Optional[str],
    *,
    adb_exe: str = "adb",
) -> list[tuple[int, str]]:
    """尝试 `ps -A` 解析 PID 与进程名（不同 ROM 格式略有差异）。"""
    try:
        text = shell(serial, "ps -A", adb_exe=adb_exe, timeout=30.0)
    except RuntimeError:
        text = shell(serial, "ps", adb_exe=adb_exe, timeout=30.0)
    out: list[tuple[int, str]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.upper().startswith("USER "):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        # 常见：`USER PID ... NAME`，PID 多为第二列
        pid: Optional[int] = None
        try:
            pid = int(parts[1])
        except (ValueError, IndexError):
            for t in parts:
                if t.isdigit():
                    try:
                        pid = int(t)
                        break
                    except ValueError:
                        pass
        if pid is None:
            continue
        name = parts[-1]
        out.append((pid, name))
    out.sort(key=lambda x: x[0])
    return out


def list_app_processes_ps(
    serial: Optional[str],
    *,
    adb_exe: str = "adb",
) -> list[tuple[int, str]]:
    """列出与已安装应用包相关的进程（与 `pm list packages` 一致，含系统应用与第三方）。

    进程名通常为包名或 `包名:子进程` 形式；与全量 `ps` 相比可排除内核等无包名项。
    """
    pkgs = set(
        list_packages(serial, adb_exe=adb_exe, third_party_only=False)
    )
    if not pkgs:
        return []
    all_rows = list_processes_ps(serial, adb_exe=adb_exe)
    out: list[tuple[int, str]] = []
    for pid, name in all_rows:
        base = name.split(":", 1)[0]
        if base in pkgs or name in pkgs:
            out.append((pid, name))
    out.sort(key=lambda x: x[0])
    return out
