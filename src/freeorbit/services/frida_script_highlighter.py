"""Frida 脚本编辑器的轻量 JS/TS 语法高亮器。"""

from __future__ import annotations

from PySide6.QtCore import QRegularExpression
from PySide6.QtGui import (
    QColor,
    QFont,
    QSyntaxHighlighter,
    QTextCharFormat,
    QTextDocument,
)

from freeorbit.theme import theme_color


class FridaScriptHighlighter(QSyntaxHighlighter):
    """基于正则的 JS/TS 语法高亮（关键字、字符串、注释、数字）。"""

    def __init__(self, parent: QTextDocument | None = None) -> None:
        super().__init__(parent)
        self._formats: dict[str, QTextCharFormat] = {}
        self._setup_formats()
        self._rules: list[tuple[QRegularExpression, QTextCharFormat]] = []
        self._setup_rules()
        self._comment_start = QRegularExpression(r"/\*")
        self._comment_end = QRegularExpression(r"\*/")

    def _setup_formats(self) -> None:
        keyword = QTextCharFormat()
        keyword.setForeground(theme_color("syntax_keyword"))
        keyword.setFontWeight(QFont.Weight.Bold)
        self._formats["keyword"] = keyword

        string = QTextCharFormat()
        string.setForeground(theme_color("syntax_string"))
        self._formats["string"] = string

        comment = QTextCharFormat()
        comment.setForeground(theme_color("syntax_comment"))
        comment.setFontItalic(True)
        self._formats["comment"] = comment

        number = QTextCharFormat()
        number.setForeground(theme_color("syntax_number"))
        self._formats["number"] = number

    def _setup_rules(self) -> None:
        keywords = [
            "break", "case", "catch", "class", "const", "continue", "debugger",
            "default", "delete", "do", "else", "export", "extends", "finally",
            "for", "function", "if", "import", "in", "instanceof", "let", "new",
            "return", "super", "switch", "this", "throw", "try", "typeof",
            "var", "void", "while", "with", "yield",
            "async", "await", "static", "get", "set", "of", "from", "as",
            "type", "interface", "implements", "declare", "namespace", "module",
            "enum", "abstract", "readonly", "public", "private", "protected",
            "true", "false", "null", "undefined",
        ]
        keyword_pat = r"\b(" + "|".join(keywords) + r")\b"
        self._rules.append(
            (QRegularExpression(keyword_pat), self._formats["keyword"])
        )

        # 字符串：双引号、单引号、反引号
        self._rules.append(
            (QRegularExpression(r'"([^"\\]|\\.)*"'), self._formats["string"])
        )
        self._rules.append(
            (QRegularExpression(r"'([^'\\]|\\.)*'"), self._formats["string"])
        )
        self._rules.append(
            (QRegularExpression(r"`([^`\\]|\\.)*`"), self._formats["string"])
        )

        # 数字（含十六进制、二进制、八进制）
        self._rules.append(
            (
                QRegularExpression(
                    r"\b((0[xX][0-9a-fA-F_]*)|(0[oO]?[0-7_]*)|(0[bB][01_]*)|(\d[\d_]*))\b"
                ),
                self._formats["number"],
            )
        )

        # 行注释
        self._rules.append(
            (QRegularExpression(r"//[^\n]*"), self._formats["comment"])
        )

    def highlightBlock(self, text: str) -> None:
        for expr, fmt in self._rules:
            it = expr.globalMatch(text)
            while it.hasNext():
                match = it.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), fmt)

        self.setCurrentBlockState(0)
        start_index = 0
        if self.previousBlockState() != 1:
            match = self._comment_start.match(text)
            start_index = match.capturedStart() if match.hasMatch() else -1

        while start_index >= 0:
            end_match = self._comment_end.match(text, start_index)
            if not end_match.hasMatch():
                self.setCurrentBlockState(1)
                comment_len = len(text) - start_index
                self.setFormat(start_index, comment_len, self._formats["comment"])
                break
            end_index = end_match.capturedStart() + end_match.capturedLength()
            comment_len = end_index - start_index
            self.setFormat(start_index, comment_len, self._formats["comment"])
            next_match = self._comment_start.match(text, end_index)
            start_index = next_match.capturedStart() if next_match.hasMatch() else -1
