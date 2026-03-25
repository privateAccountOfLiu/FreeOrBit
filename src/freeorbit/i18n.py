"""界面中英文字符串（运行时切换）。

文案均内嵌于本模块，无外部语言文件；Nuitka 打包后仍从字节码加载。
语言偏好通过 QSettings 持久化，与可执行文件路径、onefile 解压目录无关
（由 QApplication 的 organizationName / applicationName 决定存储位置）。
"""

from __future__ import annotations

from PySide6.QtCore import QSettings

_SETTINGS_KEY = "ui/language"
_LANG_ZH = "zh"
_LANG_EN = "en"

_STRINGS: dict[str, dict[str, str]] = {
    _LANG_ZH: {
        "app.title": "FreeOrBit",
        "menu.file": "文件(&F)",
        "menu.edit": "编辑(&E)",
        "menu.tools": "工具(&T)",
        "menu.window": "窗口(&W)",
        "menu.settings": "设置(&S)",
        "menu.help": "帮助(&H)",
        "action.new": "新建(&N)",
        "action.open": "打开(&O)...",
        "action.save": "保存(&S)",
        "action.save_as": "另存为(&A)...",
        "action.exit": "退出(&X)",
        "action.undo": "撤销(&U)",
        "action.redo": "重做(&R)",
        "action.search": "搜索(&S)...",
        "action.checksum": "校验和/哈希(&C)...",
        "action.compare": "比较文件(&M)...",
        "action.import_hex": "导入十六进制文本(&I)...",
        "action.export_sel": "导出选区(&E)...",
        "action.convert": "转换选区为…(&V)",
        "action.goto": "转到偏移…",
        "action.show_search": "显示搜索面板",
        "action.show_struct": "显示结构模板面板",
        "action.show_bookmark": "显示书签面板",
        "action.show_script": "显示脚本面板",
        "action.show_all_docks": "显示全部工具面板",
        "action.open_settings": "设置…",
        "action.about": "关于(&A)",
        "tab.untitled": "未命名",
        "status.addr": "地址",
        "status.sel": "选区",
        "status.bytes": "字节",
        "status.len": "长度",
        "status.mode": "模式",
        "status.overwrite": "覆盖",
        "status.insert": "插入",
        "dlg.unsaved": "未保存",
        "dlg.unsaved_msg": "是否保存当前修改？",
        "dlg.open_file": "打开文件",
        "dlg.compare_a": "文件 A",
        "dlg.compare_b": "文件 B",
        "dlg.all_files": "所有文件 (*.*)",
        "dlg.open_fail": "打开失败",
        "dlg.save_fail": "保存失败",
        "dlg.save_as": "另存为",
        "dlg.import_hex": "导入十六进制文本",
        "dlg.text_files": "文本 (*.txt);;所有 (*.*)",
        "dlg.import": "导入",
        "dlg.import_invalid": "无效的十六进制文本",
        "dlg.export_sel": "导出选区",
        "dlg.convert_sel": "转换选区",
        "dlg.goto": "转到偏移",
        "ctx.export": "导出选区…",
        "ctx.convert": "转换选区为…",
        "dock.search": "搜索",
        "dock.struct": "结构",
        "dock.bookmark": "书签",
        "dock.script": "脚本",
        "search.hex_label": "十六进制:",
        "search.placeholder": "例如 48 65 6C 6C 6F 或 48656C6C6F",
        "search.button": "搜索",
        "search.warn_title": "搜索",
        "search.hex_even": "十六进制长度须为偶数",
        "search.found": "找到 {n} 处匹配",
        "struct.load": "加载模板…",
        "struct.optional": "（可选）用户 .py 模板",
        "struct.col_field": "字段",
        "struct.col_value": "值",
        "struct.col_offset": "偏移",
        "struct.dlg_template": "模板文件",
        "struct.filter_py": "Python (*.py);;所有 (*.*)",
        "struct.warn_title": "模板",
        "struct.load_fail": "无法加载",
        "struct.load_ok": "已加载: {path}\n可在脚本中 importlib 使用；结构树仍为 DWORD 预览。",
        "bookmark.name_ph": "名称",
        "bookmark.add": "添加当前位置",
        "dlg.export_save": "导出选区",
        "dlg.export_fail": "导出失败",
        "script.label_code": "Python（受限 API）:",
        "script.run": "运行",
        "script.label_out": "输出:",
        "script.placeholder": "# 示例: data = editor.read(0, 16); editor.message(hex(data))\\n",
        "script.err_title": "脚本",
        "about.title": "关于 FreeOrBit",
        "about.body": (
            "FreeOrBit — 免费开源十六进制编辑器\nPython / PySide6\n\n"
            "作者：Privateliu\n"
            "最终解释权归作者所有\n\n"
            "界面图标使用 Font Awesome Free（https://fontawesome.com/license/free），"
            "通过 QtAwesome 在 Qt 中渲染。"
        ),
        "settings.title": "设置",
        "settings.tree.appearance": "外观与行为",
        "settings.tree.system": "系统设置",
        "settings.tree.language": "语言功能",
        "settings.lang.label": "界面语言",
        "settings.lang.zh": "简体中文",
        "settings.lang.en": "English",
        "settings.breadcrumb": "外观与行为 > 系统设置 > 语言功能",
        "btn.ok": "确定",
        "btn.cancel": "取消",
        "btn.apply": "应用",
    },
    _LANG_EN: {
        "app.title": "FreeOrBit",
        "menu.file": "&File",
        "menu.edit": "&Edit",
        "menu.tools": "&Tools",
        "menu.window": "&Window",
        "menu.settings": "&Settings",
        "menu.help": "&Help",
        "action.new": "&New",
        "action.open": "&Open...",
        "action.save": "&Save",
        "action.save_as": "Save &As...",
        "action.exit": "E&xit",
        "action.undo": "&Undo",
        "action.redo": "&Redo",
        "action.search": "&Search...",
        "action.checksum": "&Checksum/Hash...",
        "action.compare": "Compare &Files...",
        "action.import_hex": "Import &Hex Text...",
        "action.export_sel": "&Export Selection...",
        "action.convert": "Convert Selection...",
        "action.goto": "Go to Offset…",
        "action.show_search": "Show Search Panel",
        "action.show_struct": "Show Structure Panel",
        "action.show_bookmark": "Show Bookmarks Panel",
        "action.show_script": "Show Script Panel",
        "action.show_all_docks": "Show All Tool Panels",
        "action.open_settings": "Settings…",
        "action.about": "&About",
        "tab.untitled": "Untitled",
        "status.addr": "Addr",
        "status.sel": "Sel",
        "status.bytes": "bytes",
        "status.len": "Len",
        "status.mode": "Mode",
        "status.overwrite": "Overwrite",
        "status.insert": "Insert",
        "dlg.unsaved": "Unsaved",
        "dlg.unsaved_msg": "Save changes to the current document?",
        "dlg.open_file": "Open File",
        "dlg.compare_a": "File A",
        "dlg.compare_b": "File B",
        "dlg.all_files": "All Files (*.*)",
        "dlg.open_fail": "Open failed",
        "dlg.save_fail": "Save failed",
        "dlg.save_as": "Save As",
        "dlg.import_hex": "Import Hex Text",
        "dlg.text_files": "Text (*.txt);;All (*.*)",
        "dlg.import": "Import",
        "dlg.import_invalid": "Invalid hex text",
        "dlg.export_sel": "Export Selection",
        "dlg.convert_sel": "Convert Selection",
        "dlg.goto": "Go to Offset",
        "ctx.export": "Export Selection…",
        "ctx.convert": "Convert Selection…",
        "dock.search": "Search",
        "dock.struct": "Structure",
        "dock.bookmark": "Bookmarks",
        "dock.script": "Script",
        "search.hex_label": "Hex:",
        "search.placeholder": "e.g. 48 65 6C 6C 6F or 48656C6C6F",
        "search.button": "Search",
        "search.warn_title": "Search",
        "search.hex_even": "Hex string length must be even",
        "search.found": "Found {n} match(es)",
        "struct.load": "Load template…",
        "struct.optional": "(optional) user .py template",
        "struct.col_field": "Field",
        "struct.col_value": "Value",
        "struct.col_offset": "Offset",
        "struct.dlg_template": "Template file",
        "struct.filter_py": "Python (*.py);;All (*.*)",
        "struct.warn_title": "Template",
        "struct.load_fail": "Failed to load",
        "struct.load_ok": "Loaded: {path}\nYou may use importlib in scripts; the tree still shows DWORD preview.",
        "bookmark.name_ph": "Name",
        "bookmark.add": "Add current position",
        "dlg.export_save": "Export selection",
        "dlg.export_fail": "Export failed",
        "script.label_code": "Python (restricted API):",
        "script.run": "Run",
        "script.label_out": "Output:",
        "script.placeholder": "# e.g. data = editor.read(0, 16); editor.message(hex(data))\\n",
        "script.err_title": "Script",
        "about.title": "About FreeOrBit",
        "about.body": (
            "FreeOrBit — open-source hex editor\nPython / PySide6\n\n"
            "Author: Privateliu\n"
            "All rights reserved by the author.\n\n"
            "Icons: Font Awesome Free (https://fontawesome.com/license/free), "
            "via QtAwesome in Qt."
        ),
        "settings.title": "Settings",
        "settings.tree.appearance": "Appearance & Behavior",
        "settings.tree.system": "System Settings",
        "settings.tree.language": "Language",
        "settings.lang.label": "UI language",
        "settings.lang.zh": "简体中文",
        "settings.lang.en": "English",
        "settings.breadcrumb": "Appearance & Behavior > System Settings > Language",
        "btn.ok": "OK",
        "btn.cancel": "Cancel",
        "btn.apply": "Apply",
    },
}


def current_language() -> str:
    s = QSettings()
    v = s.value(_SETTINGS_KEY, _LANG_EN)
    if v in (_LANG_ZH, _LANG_EN):
        return str(v)
    return _LANG_EN


def set_language(lang: str) -> None:
    if lang not in (_LANG_ZH, _LANG_EN):
        lang = _LANG_EN
    QSettings().setValue(_SETTINGS_KEY, lang)


def tr(key: str) -> str:
    lang = current_language()
    base = _STRINGS.get(lang, _STRINGS[_LANG_EN])
    return base.get(key, _STRINGS[_LANG_EN].get(key, key))
