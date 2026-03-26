"""字段编码写回单元测试。"""

from freeorbit.template.fields import encode_field_value


def test_encode_u32_hex() -> None:
    assert encode_field_value("u32le", "0x11223344") == bytes([0x44, 0x33, 0x22, 0x11])


def test_encode_i32_negative() -> None:
    assert encode_field_value("i32le", "-1") == b"\xff\xff\xff\xff"


def test_encode_u8() -> None:
    assert encode_field_value("u8", "255") == b"\xff"


def test_encode_f32() -> None:
    import struct

    assert encode_field_value("f32le", "1.5") == struct.pack("<f", 1.5)


def test_encode_u32_be() -> None:
    assert encode_field_value("u32be", "0x11223344") == bytes([0x11, 0x22, 0x33, 0x44])
