"""十六进制文本行格式，与 HexEditorView 绘制布局一致（地址 + hex 对 + ASCII）。"""

from __future__ import annotations


def _byte_to_ascii(b: int) -> str:
    return chr(b) if 32 <= b <= 126 else "."


def address_digit_count(total_file_bytes: int) -> int:
    """与 HexEditorView._addr_digits 一致：由文件总长度决定地址列宽。"""
    if total_file_bytes <= 0:
        return 8
    n = max(0, total_file_bytes - 1)
    return max(8, (n.bit_length() + 3) // 4)


def format_hex_dump_lines(
    data: bytes,
    bytes_per_line: int,
    *,
    start_offset: int = 0,
    total_file_bytes: int | None = None,
) -> list[str]:
    """
    生成若干行文本，每行：大写十六进制地址、两空格、空格分隔的十六进制字节对、两空格、ASCII。

    total_file_bytes 用于地址列宽；默认取 start_offset + len(data)。
    """
    if bytes_per_line < 1:
        bytes_per_line = 1
    if total_file_bytes is None:
        total_file_bytes = start_offset + len(data)
    digits = address_digit_count(total_file_bytes)
    lines: list[str] = []
    for row in range(0, len(data), bytes_per_line):
        chunk = data[row : row + bytes_per_line]
        base = start_offset + row
        addr = f"{base:0{digits}X}"
        hex_part = " ".join(f"{b:02X}" for b in chunk)
        ascii_part = "".join(_byte_to_ascii(b) for b in chunk)
        lines.append(f"{addr}  {hex_part}  {ascii_part}")
    return lines
