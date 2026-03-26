"""按扩展名与文件头 Magic 自动选择结构模板。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Union


@dataclass(frozen=True)
class ExtRule:
    """扩展名匹配（小写，含点，如 .exe）。"""

    ext: str
    template_path: str


@dataclass(frozen=True)
class MagicRule:
    """从 offset 起与 pattern 完全相等则匹配。"""

    offset: int
    pattern: bytes
    template_path: str


AutoRule = Union[ExtRule, MagicRule]


def parse_rules_text(text: str) -> tuple[list[AutoRule], list[str]]:
    """
    解析多行规则。每行一条，# 开头为注释；空行忽略。
    格式：
      ext:.exe=C:\\path\\to\\template.py
      magic:0:4D5A=C:\\path\\to\\template.py
    magic 段为 偏移:十六进制字节（无空格，偶数长度）。
    返回 (规则列表, 错误信息列表)。
    """
    rules: list[AutoRule] = []
    errors: list[str] = []
    for line_no, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            errors.append(f"行 {line_no}: 缺少 '='")
            continue
        key, path = line.split("=", 1)
        key = key.strip()
        path = path.strip()
        if not path:
            errors.append(f"行 {line_no}: 模板路径为空")
            continue
        low = key.lower()
        try:
            if low.startswith("ext:"):
                ext = key[4:].strip().lower()
                if not ext.startswith("."):
                    ext = "." + ext
                rules.append(ExtRule(ext, path))
            elif low.startswith("magic:"):
                rest = key[6:].strip()
                if ":" not in rest:
                    errors.append(f"行 {line_no}: magic 需为 magic:偏移:十六进制")
                    continue
                off_s, hex_s = rest.split(":", 1)
                offset = int(off_s.strip(), 0)
                hex_clean = re.sub(r"\s+", "", hex_s.strip())
                if len(hex_clean) % 2:
                    errors.append(f"行 {line_no}: magic 十六进制长度须为偶数")
                    continue
                rules.append(MagicRule(offset, bytes.fromhex(hex_clean), path))
            else:
                errors.append(f"行 {line_no}: 仅支持 ext: 或 magic: 前缀")
        except ValueError as e:
            errors.append(f"行 {line_no}: {e}")
    return rules, errors


def match_auto_template(
    file_path: Path | None,
    head: bytes,
    rules: list[AutoRule],
) -> str | None:
    """
    按规则顺序首个命中即返回模板路径；无命中返回 None。
    head 建议为文件开头若干字节（如 512），用于 magic 匹配。
    """
    for r in rules:
        if isinstance(r, ExtRule):
            if file_path is None:
                continue
            suf = file_path.suffix.lower()
            if suf == r.ext:
                return r.template_path
        elif isinstance(r, MagicRule):
            o = r.offset
            pat = r.pattern
            if o < 0 or o + len(pat) > len(head):
                continue
            if head[o : o + len(pat)] == pat:
                return r.template_path
    return None
