"""auto_template 规则解析与匹配。"""

from __future__ import annotations

from pathlib import Path

from freeorbit.template.auto_template import (
    ExtRule,
    MagicRule,
    match_auto_template,
    parse_rules_text,
)


def test_parse_ext() -> None:
    rules, errs = parse_rules_text("ext:.exe=C:/t.py\n")
    assert not errs
    assert len(rules) == 1
    assert isinstance(rules[0], ExtRule)
    assert rules[0].ext == ".exe"
    assert rules[0].template_path == "C:/t.py"


def test_parse_magic() -> None:
    rules, errs = parse_rules_text("magic:0:4D5A=C:/pe.py")
    assert not errs
    assert isinstance(rules[0], MagicRule)
    assert rules[0].offset == 0
    assert rules[0].pattern == b"MZ"
    assert rules[0].template_path == "C:/pe.py"


def test_parse_comment_and_empty() -> None:
    rules, errs = parse_rules_text("# c\n\next:.bin=X\n")
    assert not errs
    assert len(rules) == 1


def test_match_magic_first() -> None:
    rules = [
        MagicRule(0, b"MZ", "a.py"),
        ExtRule(".exe", "b.py"),
    ]
    head = b"MZ\x90\x00" + b"\x00" * 500
    assert match_auto_template(Path("x.exe"), head, rules) == "a.py"


def test_match_ext_when_magic_miss() -> None:
    rules = [
        MagicRule(0, b"ZZ", "a.py"),
        ExtRule(".exe", "b.py"),
    ]
    head = b"MZ\x90\x00"
    assert match_auto_template(Path(r"C:\f.exe"), head, rules) == "b.py"


def test_match_none() -> None:
    assert match_auto_template(Path("a.txt"), b"hello", [ExtRule(".exe", "x.py")]) is None
