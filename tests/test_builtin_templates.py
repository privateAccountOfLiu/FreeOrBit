"""内置模板路径与包内文件。"""

from pathlib import Path

import freeorbit

from freeorbit.template.builtin_templates import builtin_templates_dir, list_builtin_templates


def test_builtin_dir_under_package() -> None:
    d = builtin_templates_dir()
    assert d.name == "templates"
    assert "freeorbit" in str(d).lower() or d.is_dir()


def test_pe_template_shipped() -> None:
    root = Path(freeorbit.__file__).resolve().parent
    pe = root / "resources" / "templates" / "pe_dos_header.py"
    assert pe.is_file(), f"missing {pe}"


def test_list_builtin_non_empty_when_packaged() -> None:
    lst = list_builtin_templates()
    names = [x[0] for x in lst]
    assert "pe_dos_header" in names
