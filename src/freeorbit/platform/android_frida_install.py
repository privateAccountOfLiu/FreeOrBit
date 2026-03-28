"""通过 ADB 检测 Android 上 root / frida-server，并下载与 Windows 端 pip frida 同版本的 frida-server。"""

from __future__ import annotations

import lzma
import os
import shutil
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable, Optional

from freeorbit.platform.android_adb import run_adb, shell

LogFn = Callable[[str], None]


def get_windows_frida_version() -> Optional[str]:
    """当前生效的 frida 版本号；未安装返回 None。"""
    from freeorbit.platform import frida_loader

    frida_loader.ensure_frida_import_preference()
    try:
        import frida

        v = getattr(frida, "__version__", None)
        return str(v).strip() if v else None
    except ImportError:
        return None


def _run_shell(
    serial: Optional[str],
    shell_cmd: str,
    adb_exe: str,
    *,
    timeout: float = 60.0,
) -> tuple[int, str, str]:
    args: list[str] = []
    if serial:
        args.extend(["-s", serial])
    args.extend(["shell", shell_cmd])
    return run_adb(args, adb_exe=adb_exe, timeout=timeout)


def probe_android_root(serial: Optional[str], adb_exe: str) -> tuple[str, str]:
    """检测 root：返回 (状态码, 说明)。

    状态码: 'yes' | 'no' | 'unknown'
    """
    for cmd in ('su -c id', 'su 0 id'):
        code, out, err = _run_shell(serial, cmd, adb_exe, timeout=15.0)
        text = (out + err).lower()
        if code == 0 and "uid=0" in out:
            return ("yes", out.strip()[:200])
        if "not found" in text or "no su" in text:
            continue
    code2, out2, err2 = _run_shell(serial, "id", adb_exe, timeout=10.0)
    if code2 == 0 and "uid=0" in out2:
        return ("yes", out2.strip()[:200])
    return ("no", (err2 or out2 or "su 不可用").strip()[:200])


def probe_frida_server_on_device(serial: Optional[str], adb_exe: str) -> tuple[str, str]:
    """设备上 frida-server：返回 (状态码, 说明)。

    状态码: 'running' | 'file_only' | 'none' | 'unknown'
    """
    code, out, err = _run_shell(serial, "ps -A", adb_exe, timeout=35.0)
    if code != 0:
        code, out, err = _run_shell(serial, "ps", adb_exe, timeout=35.0)
    combined = out + "\n" + err
    running = "frida-server" in combined
    code2, out2, err2 = _run_shell(
        serial,
        "ls -l /data/local/tmp/frida-server 2>&1",
        adb_exe,
        timeout=15.0,
    )
    has_file = code2 == 0 and "No such file" not in out2 and "cannot access" not in out2.lower()
    if running:
        return ("running", "ps 中发现 frida-server 进程")
    if has_file:
        return ("file_only", out2.strip()[:200])
    return ("none", "未发现运行中的 frida-server，且未找到 /data/local/tmp/frida-server")


def get_device_cpu_abi(serial: Optional[str], adb_exe: str) -> str:
    try:
        return shell(serial, "getprop ro.product.cpu.abi", adb_exe=adb_exe, timeout=15.0).strip()
    except Exception as e:  # noqa: BLE001
        return str(e)


def cpu_abi_to_frida_arch(abi: str) -> str:
    """映射 ro.product.cpu.abi 到 frida 发布包中的 android-* 后缀。"""
    a = abi.strip().lower()
    if a in ("arm64-v8a", "arm64"):
        return "arm64"
    if a in ("armeabi-v7a", "armeabi"):
        return "arm"
    if a == "x86":
        return "x86"
    if a == "x86_64":
        return "x86_64"
    return "arm64"


def frida_server_asset_name(version: str, arch: str) -> str:
    return f"frida-server-{version}-android-{arch}.xz"


def frida_server_download_url(version: str, arch: str) -> str:
    name = frida_server_asset_name(version, arch)
    return f"https://github.com/frida/frida/releases/download/{version}/{name}"


def _download_file(url: str, dest: Path, log: LogFn) -> None:
    log(f"GET {url}\n")
    req = urllib.request.Request(url, headers={"User-Agent": "FreeOrBit/1.0"})
    with urllib.request.urlopen(req, timeout=120) as resp:  # noqa: S310  # 可信固定 URL
        data = resp.read()
    dest.write_bytes(data)
    log(f"已下载 {len(data)} 字节 -> {dest}\n")


def _decompress_xz(xz_path: Path, log: LogFn) -> Path:
    out_path = xz_path.with_suffix("")  # 去掉 .xz
    log(f"解压 {xz_path.name} -> {out_path.name}\n")
    with lzma.open(xz_path, "rb") as f:
        data = f.read()
    out_path.write_bytes(data)
    xz_path.unlink(missing_ok=True)
    return out_path


def install_frida_server_to_device(
    serial: Optional[str],
    adb_exe: str,
    *,
    device_path: str = "/data/local/tmp/frida-server",
    log: LogFn,
) -> None:
    """下载与 pip frida 同版本的 frida-server，push 到设备并 chmod；不自动长期驻留启动。"""
    ver = get_windows_frida_version()
    if not ver:
        raise RuntimeError("NO_FRIDA_PIP")

    abi_raw = get_device_cpu_abi(serial, adb_exe)
    abi_clean = abi_raw.strip()
    if not abi_clean or len(abi_clean) > 48:
        raise RuntimeError(f"ABI_INVALID:{abi_raw}")

    arch = cpu_abi_to_frida_arch(abi_clean)
    log(f"[1/6] Windows pip frida 版本: {ver}\n")
    log(f"[2/6] 设备 CPU ABI: {abi_clean} -> frida android-{arch}\n")

    url = frida_server_download_url(ver, arch)
    tmp_dir = Path(tempfile.mkdtemp(prefix="frida_srv_"))
    try:
        xz_path = tmp_dir / frida_server_asset_name(ver, arch)
        try:
            _download_file(url, xz_path, log)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise RuntimeError(f"HTTP_404:{url}") from e
            raise
        except OSError as e:
            raise RuntimeError(f"DOWNLOAD_FAIL:{e}") from e

        binary = _decompress_xz(xz_path, log)
        if os.name != "nt":
            os.chmod(binary, 0o755)

        log(f"[3/6] adb push -> {device_path}\n")
        args: list[str] = []
        if serial:
            args.extend(["-s", serial])
        args.extend(["push", str(binary), device_path])
        code, out, err = run_adb(args, adb_exe=adb_exe, timeout=180.0)
        log(out + err + "\n")
        if code != 0:
            raise RuntimeError(f"adb push 退出码 {code}")

        log(f"[4/6] chmod 755\n")
        for chmod_cmd in (
            f"chmod 755 {device_path}",
            f"su -c chmod 755 {device_path}",
            f"su 0 chmod 755 {device_path}",
        ):
            c2, o2, e2 = _run_shell(serial, chmod_cmd, adb_exe, timeout=20.0)
            log(f"  $ {chmod_cmd}\n{o2}{e2}\n")
            if c2 == 0:
                break
        else:
            log("  （chmod 未全部成功，若设备已 root 可手动：su -c chmod 755 ...）\n")

        log(f"[5/6] 检测进程（可选结束旧进程）\n")
        _run_shell(serial, "su -c killall frida-server", adb_exe, timeout=10.0)
        _run_shell(serial, "killall frida-server", adb_exe, timeout=10.0)

        log(
            f"[6/6] 安装文件已就绪。手动启动示例（需 root）：\n"
            f"  adb shell su -c \"{device_path} &\"\n"
            f"或在本机使用 Frida 连接 USB 设备。\n"
        )
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
