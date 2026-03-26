"""parse_hex_search_pattern 单元测试（无 Qt）。"""

from __future__ import annotations

import pytest

from freeorbit.services.search import parse_hex_search_pattern, parse_search_pattern


def test_exact_no_mask() -> None:
    p, m = parse_hex_search_pattern("48656C6C6F")
    assert p == b"Hello"
    assert m is None


def test_exact_with_spaces() -> None:
    p, m = parse_hex_search_pattern("48 65 6C")
    assert p == b"\x48\x65\x6c"
    assert m is None


def test_mask_wildcard_bytes() -> None:
    p, m = parse_hex_search_pattern("48??6C")
    assert p == b"\x48\x00\x6c"
    assert m == b"\xff\x00\xff"


def test_mask_multiple_wildcards() -> None:
    p, m = parse_hex_search_pattern("????")
    assert len(p) == 2
    assert m == b"\x00\x00"


def test_empty() -> None:
    p, m = parse_hex_search_pattern("   ")
    assert p == b""
    assert m is None


def test_hex_even_raises() -> None:
    with pytest.raises(ValueError) as e:
        parse_hex_search_pattern("481")
    assert str(e.value) == "hex_even"


def test_single_question_raises() -> None:
    with pytest.raises(ValueError) as e:
        parse_hex_search_pattern("48?6C")
    assert str(e.value) == "mask_bad_single"


def test_ascii_mode() -> None:
    p, m = parse_search_pattern("hello", "ascii")
    assert p == b"hello"
    assert m is None


def test_ascii_empty_raises() -> None:
    with pytest.raises(ValueError) as e:
        parse_search_pattern("   ", "ascii")
    assert str(e.value) == "empty_pattern"


def test_ascii_non_ascii_raises() -> None:
    with pytest.raises(ValueError) as e:
        parse_search_pattern("\u4e00", "ascii")
    assert str(e.value) == "ascii_only"


def test_hex_mode_delegates() -> None:
    p, m = parse_search_pattern("48656C6C6F", "hex")
    assert p == b"Hello"
    assert m is None
