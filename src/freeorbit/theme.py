"""Centralized theme: dark/light palettes, color constants, fonts, and global QSS."""

from __future__ import annotations

from PySide6.QtCore import Qt, QSettings
from PySide6.QtGui import QPalette, QColor, QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

# ── Theme persistence key ────────────────────────────────────────────
_THEME_KEY = "ui/theme"
_THEME_DARK = "dark"
_THEME_LIGHT = "light"

# ── Surface colors ──────────────────────────────────────────────────
SURFACE_DARKEST = "#1e1e1e"  # Main background, matrix bg
SURFACE_DARK = "#252526"     # Panel backgrounds, group boxes
SURFACE_MID = "#2d2d30"      # Alternate rows
SURFACE_LIGHT = "#3e3e42"    # Borders, separators, input bg
SURFACE_HOVER = "#454545"    # Hover states

# ── Accent colors ───────────────────────────────────────────────────
ACCENT_PRIMARY = "#0078d4"      # Blue — selections, highlights
ACCENT_SECONDARY = "#4ec9b0"    # Teal — structure highlighting
ACCENT_WARNING = "#cca700"      # Amber — search hits, matrix matches
ACCENT_SUCCESS = "#6a9955"      # Green — compare match
ACCENT_DANGER = "#f44747"       # Red — compare diff, cursor, errors

# ── Text colors ─────────────────────────────────────────────────────
TEXT_PRIMARY = "#cccccc"
TEXT_SECONDARY = "#999999"
TEXT_DISABLED = "#5a5a5a"

# ── Syntax highlighting ─────────────────────────────────────────────
SYNTAX_KEYWORD = "#569cd6"
SYNTAX_STRING = "#ce9178"
SYNTAX_COMMENT = "#6a9955"
SYNTAX_NUMBER = "#b5cea8"

# ── Semantic color lookup ───────────────────────────────────────────
_SEMANTIC: dict[str, str] = {
    "search_hit": ACCENT_WARNING,
    "compare_match": ACCENT_SUCCESS,
    "compare_diff": ACCENT_DANGER,
    "structure": ACCENT_SECONDARY,
    "cursor": ACCENT_DANGER,
    "matrix_match": ACCENT_WARNING,
    "matrix_bg": SURFACE_DARKEST,
    "matrix_border": SURFACE_LIGHT,
    "chart_line": "#5096dc",
    "chart_fill": "#5096dc",
    "chart_bar": "#5096dc",
    "chart_border": "#3a7abf",
    "syntax_keyword": SYNTAX_KEYWORD,
    "syntax_string": SYNTAX_STRING,
    "syntax_comment": SYNTAX_COMMENT,
    "syntax_number": SYNTAX_NUMBER,
    "error": ACCENT_DANGER,
}


def theme_color(name: str) -> QColor:
    """Look up a semantic color by name. Returns QColor."""
    return QColor(_SEMANTIC.get(name, TEXT_PRIMARY))


# ── Dark palette builder ────────────────────────────────────────────


def build_dark_palette() -> QPalette:
    p = QPalette()

    p.setColor(QPalette.ColorRole.Window, QColor(SURFACE_DARKEST))
    p.setColor(QPalette.ColorRole.WindowText, QColor(TEXT_PRIMARY))
    p.setColor(QPalette.ColorRole.Base, QColor(SURFACE_DARK))
    p.setColor(QPalette.ColorRole.AlternateBase, QColor(SURFACE_MID))
    p.setColor(QPalette.ColorRole.Text, QColor(TEXT_PRIMARY))
    p.setColor(QPalette.ColorRole.Button, QColor(SURFACE_MID))
    p.setColor(QPalette.ColorRole.ButtonText, QColor(TEXT_PRIMARY))
    p.setColor(QPalette.ColorRole.Highlight, QColor(ACCENT_PRIMARY))
    p.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    p.setColor(QPalette.ColorRole.ToolTipBase, QColor(SURFACE_DARK))
    p.setColor(QPalette.ColorRole.ToolTipText, QColor(TEXT_PRIMARY))
    p.setColor(QPalette.ColorRole.BrightText, QColor(ACCENT_DANGER))
    p.setColor(QPalette.ColorRole.Link, QColor(ACCENT_PRIMARY))
    p.setColor(QPalette.ColorRole.LinkVisited, QColor("#9775d6"))
    p.setColor(QPalette.ColorRole.Mid, QColor(SURFACE_LIGHT))
    p.setColor(QPalette.ColorRole.Dark, QColor(TEXT_SECONDARY))
    p.setColor(QPalette.ColorRole.Light, QColor(SURFACE_MID))
    p.setColor(QPalette.ColorRole.Midlight, QColor(SURFACE_HOVER))
    p.setColor(QPalette.ColorRole.Shadow, QColor("#000000"))

    # Disabled
    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, QColor(TEXT_DISABLED))
    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor(TEXT_DISABLED))
    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor(TEXT_DISABLED))

    return p


# ── Global stylesheet (palette-uncoverable widgets only) ────────────


def theme_stylesheet() -> str:
    return f"""
    QToolTip {{
        border: 1px solid {SURFACE_LIGHT};
        padding: 4px 6px;
        background: {SURFACE_DARK};
        color: {TEXT_PRIMARY};
    }}
    QDockWidget::title {{
        padding: 4px 8px;
        background: {SURFACE_DARK};
    }}
    QTabBar::tab {{
        text-transform: none;
    }}
    QTabWidget::pane {{
        border: 1px solid {SURFACE_LIGHT};
    }}
    QStatusBar {{
        border-top: 1px solid {SURFACE_LIGHT};
        color: {TEXT_SECONDARY};
    }}
    QScrollBar:vertical {{
        background: {SURFACE_DARKEST};
        width: 12px;
    }}
    QScrollBar::handle:vertical {{
        background: {SURFACE_LIGHT};
        min-height: 30px;
        border-radius: 3px;
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}
    QScrollBar:horizontal {{
        background: {SURFACE_DARKEST};
        height: 12px;
    }}
    QScrollBar::handle:horizontal {{
        background: {SURFACE_LIGHT};
        min-width: 30px;
        border-radius: 3px;
    }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        width: 0px;
    }}
    QToolBar {{
        border-bottom: 1px solid {SURFACE_LIGHT};
        spacing: 4px;
    }}
    QMenuBar {{
        background: {SURFACE_DARKEST};
        border-bottom: 1px solid {SURFACE_LIGHT};
    }}
    QMenuBar::item:selected {{
        background: {SURFACE_MID};
    }}
    QMenu {{
        background: {SURFACE_DARK};
        border: 1px solid {SURFACE_LIGHT};
    }}
    QMenu::item:selected {{
        background: {ACCENT_PRIMARY};
    }}
    QListWidget::item, QTreeWidget::item {{
        padding: 2px 4px;
    }}
    QTableWidget {{
        gridline-color: {SURFACE_LIGHT};
    }}
    QSplitter::handle {{
        background: {SURFACE_LIGHT};
    }}
    QSplitter::handle:horizontal {{
        width: 1px;
    }}
    QSplitter::handle:vertical {{
        height: 1px;
    }}
    QProgressBar {{
        border: 1px solid {SURFACE_LIGHT};
        border-radius: 3px;
        text-align: center;
        color: {TEXT_PRIMARY};
    }}
    QProgressBar::chunk {{
        background: {ACCENT_PRIMARY};
        border-radius: 2px;
    }}
    QGroupBox {{
        font-weight: bold;
        border: 1px solid {SURFACE_LIGHT};
        border-radius: 4px;
        margin-top: 12px;
        padding-top: 12px;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 10px;
        padding: 0 4px;
    }}
    """


# ── Standard metrics ────────────────────────────────────────────────

STANDARD_MARGINS = 6
STANDARD_SPACING = 8

# ── Font utilities ──────────────────────────────────────────────────


def font_mono(size: int = 11) -> QFont:
    """Monospace font: Consolas → Courier New → system monospace."""
    for family in ("Consolas", "Courier New", "monospace"):
        f = QFont(family, size)
        if QFontDatabase.hasFamily(family):
            return f
    f = QFont("monospace", size)
    f.setStyleHint(QFont.StyleHint.Monospace)
    return f


def font_default(size: int = 9) -> QFont:
    """Default UI font with CJK fallback."""
    for family in ("Microsoft YaHei", "Segoe UI", "system-ui"):
        if QFontDatabase.hasFamily(family):
            return QFont(family, size)
    return QFont("sans-serif", size)


# ═══════════════════════════════════════════════════════════════════════
#  Light theme
# ═══════════════════════════════════════════════════════════════════════

LIGHT_SURFACE = "#f5f5f5"
LIGHT_SURFACE_ALT = "#ffffff"
LIGHT_SURFACE_MID = "#e0e0e0"
LIGHT_BORDER = "#c8c8c8"
LIGHT_TEXT_PRIMARY = "#1e1e1e"
LIGHT_TEXT_SECONDARY = "#666666"
LIGHT_TEXT_DISABLED = "#aaaaaa"
LIGHT_ACCENT_PRIMARY = "#0078d4"
LIGHT_ACCENT_HOVER = "#e5f0fb"


def build_light_palette() -> QPalette:
    p = QPalette()
    p.setColor(QPalette.ColorRole.Window, QColor(LIGHT_SURFACE))
    p.setColor(QPalette.ColorRole.WindowText, QColor(LIGHT_TEXT_PRIMARY))
    p.setColor(QPalette.ColorRole.Base, QColor(LIGHT_SURFACE_ALT))
    p.setColor(QPalette.ColorRole.AlternateBase, QColor(LIGHT_SURFACE))
    p.setColor(QPalette.ColorRole.Text, QColor(LIGHT_TEXT_PRIMARY))
    p.setColor(QPalette.ColorRole.Button, QColor(LIGHT_SURFACE))
    p.setColor(QPalette.ColorRole.ButtonText, QColor(LIGHT_TEXT_PRIMARY))
    p.setColor(QPalette.ColorRole.Highlight, QColor(LIGHT_ACCENT_PRIMARY))
    p.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    p.setColor(QPalette.ColorRole.ToolTipBase, QColor(LIGHT_SURFACE_ALT))
    p.setColor(QPalette.ColorRole.ToolTipText, QColor(LIGHT_TEXT_PRIMARY))
    p.setColor(QPalette.ColorRole.BrightText, QColor("#cc0000"))
    p.setColor(QPalette.ColorRole.Link, QColor(LIGHT_ACCENT_PRIMARY))
    p.setColor(QPalette.ColorRole.LinkVisited, QColor("#6b4e9f"))
    p.setColor(QPalette.ColorRole.Mid, QColor(LIGHT_BORDER))
    p.setColor(QPalette.ColorRole.Dark, QColor(LIGHT_TEXT_SECONDARY))
    p.setColor(QPalette.ColorRole.Light, QColor(LIGHT_SURFACE_ALT))
    p.setColor(QPalette.ColorRole.Midlight, QColor(LIGHT_ACCENT_HOVER))
    p.setColor(QPalette.ColorRole.Shadow, QColor("#666666"))
    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, QColor(LIGHT_TEXT_DISABLED))
    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor(LIGHT_TEXT_DISABLED))
    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor(LIGHT_TEXT_DISABLED))
    return p


def _light_stylesheet() -> str:
    return f"""
    QToolTip {{
        border: 1px solid {LIGHT_BORDER};
        padding: 4px 6px;
        background: {LIGHT_SURFACE_ALT};
        color: {LIGHT_TEXT_PRIMARY};
    }}
    QDockWidget::title {{
        padding: 4px 8px;
        background: {LIGHT_SURFACE};
    }}
    QTabBar::tab {{
        text-transform: none;
    }}
    QTabWidget::pane {{
        border: 1px solid {LIGHT_BORDER};
    }}
    QStatusBar {{
        border-top: 1px solid {LIGHT_BORDER};
        color: {LIGHT_TEXT_SECONDARY};
    }}
    QScrollBar:vertical {{
        background: {LIGHT_SURFACE};
        width: 12px;
    }}
    QScrollBar::handle:vertical {{
        background: {LIGHT_BORDER};
        min-height: 30px;
        border-radius: 3px;
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}
    QScrollBar:horizontal {{
        background: {LIGHT_SURFACE};
        height: 12px;
    }}
    QScrollBar::handle:horizontal {{
        background: {LIGHT_BORDER};
        min-width: 30px;
        border-radius: 3px;
    }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        width: 0px;
    }}
    QToolBar {{
        border-bottom: 1px solid {LIGHT_BORDER};
        spacing: 4px;
    }}
    QMenuBar {{
        background: {LIGHT_SURFACE};
        border-bottom: 1px solid {LIGHT_BORDER};
    }}
    QMenuBar::item:selected {{
        background: {LIGHT_ACCENT_HOVER};
    }}
    QMenu {{
        background: {LIGHT_SURFACE_ALT};
        border: 1px solid {LIGHT_BORDER};
    }}
    QMenu::item:selected {{
        background: {LIGHT_ACCENT_PRIMARY};
        color: #ffffff;
    }}
    QListWidget::item, QTreeWidget::item {{
        padding: 2px 4px;
    }}
    QTableWidget {{
        gridline-color: {LIGHT_BORDER};
    }}
    QSplitter::handle {{
        background: {LIGHT_BORDER};
    }}
    QSplitter::handle:horizontal {{
        width: 1px;
    }}
    QSplitter::handle:vertical {{
        height: 1px;
    }}
    QProgressBar {{
        border: 1px solid {LIGHT_BORDER};
        border-radius: 3px;
        text-align: center;
        color: {LIGHT_TEXT_PRIMARY};
    }}
    QProgressBar::chunk {{
        background: {LIGHT_ACCENT_PRIMARY};
        border-radius: 2px;
    }}
    QGroupBox {{
        font-weight: bold;
        border: 1px solid {LIGHT_BORDER};
        border-radius: 4px;
        margin-top: 12px;
        padding-top: 12px;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 10px;
        padding: 0 4px;
    }}
    """


# ═══════════════════════════════════════════════════════════════════════
#  Theme management
# ═══════════════════════════════════════════════════════════════════════


def current_theme() -> str:
    """Return the persisted theme name ('dark' or 'light'). Defaults to 'dark'."""
    return QSettings().value(_THEME_KEY, _THEME_DARK)


def set_theme(name: str) -> None:
    """Persist the theme preference."""
    QSettings().setValue(_THEME_KEY, name)


def apply_theme(app: QApplication) -> None:
    """Apply the current theme's palette and stylesheet to the QApplication."""
    theme = current_theme()
    if theme == _THEME_LIGHT:
        app.setPalette(build_light_palette())
        app.setStyleSheet(_light_stylesheet())
    else:
        app.setPalette(build_dark_palette())
        app.setStyleSheet(theme_stylesheet())
