from freeorbit.view.hex_format import address_digit_count, format_hex_dump_lines


def test_address_digit_count() -> None:
    assert address_digit_count(0) == 8
    assert address_digit_count(1) == 8
    assert address_digit_count(0x10000) >= 8


def test_format_hex_dump_lines_matches_editor_shape() -> None:
    data = bytes([0x48, 0x65, 0x6C, 0x6C, 0x6F])
    lines = format_hex_dump_lines(data, 4, start_offset=0x10, total_file_bytes=0x100)
    assert len(lines) == 2
    assert lines[0].startswith("00000010  ")
    assert "48 65 6C 6C" in lines[0]
    assert "He" in lines[0] or "." in lines[0]
