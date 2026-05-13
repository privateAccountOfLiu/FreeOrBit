"""十六进制主视图：QScrollArea + 内部画布，在内容坐标系绘制（避免 QAbstractScrollArea 视口白屏）。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import QEvent, QPoint, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPalette,
    QPaintEvent,
    QResizeEvent,
    QShowEvent,
    QWheelEvent,
)
from PySide6.QtWidgets import QFrame, QScrollArea, QSizePolicy, QWidget

from freeorbit.theme import theme_color, TEXT_PRIMARY, TEXT_SECONDARY, SURFACE_LIGHT

if TYPE_CHECKING:
    from freeorbit.model.binary_data_model import BinaryDataModel

# 每行最大字节数（视口足够宽时可为 16，否则为 8 或 4）
MAX_BYTES_PER_LINE = 16
# 默认每行字节数（启动与窄视口）
DEFAULT_BYTES_PER_LINE = 8
# 列标题行高度（字节偏移标尺）
_HEADER_HEIGHT = 18
# 4 字节分组额外间距（像素）
_GROUP_GAP = 3
# Qt 单维控件像素上限；超过时 setFixedSize 会告警且布局异常
_QT_WIDGET_MAX_PX = 16777215


def _byte_to_ascii(b: int) -> str:
    return chr(b) if 32 <= b <= 126 else "."


class _HexCanvas(QWidget):
    """可滚动内容区：坐标即文件布局坐标，无滚动偏移。"""

    def __init__(self, editor: "HexEditorView") -> None:
        super().__init__(editor)
        self._editor = editor
        self.setMouseTracking(True)
        self.setBackgroundRole(QPalette.Base)
        self.setAutoFillBackground(True)
        # 键盘焦点交给 QScrollArea，避免按键进不了 DocumentEditor 的过滤器
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def paintEvent(self, event: QPaintEvent) -> None:
        self._editor._paint_canvas(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self._editor._mouse_press(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        self._editor._mouse_move(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._editor._mouse_release(event)

    def leaveEvent(self, event: QEvent) -> None:
        super().leaveEvent(event)
        self._editor._canvas_leave()


class _HeaderWidget(QWidget):
    """浮动于视口顶部的固定列标题行（字节偏移标尺 00-0F）。"""

    def __init__(self, editor: "HexEditorView", parent: QWidget) -> None:
        super().__init__(parent)
        self._editor = editor
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

    def paintEvent(self, event: QPaintEvent) -> None:
        editor = self._editor
        p = QPainter(self)
        p.setFont(editor._font)
        palette = editor.palette()
        header_bg = QColor(palette.color(QPalette.ColorRole.AlternateBase))
        p.fillRect(self.rect(), header_bg)

        header_font = QFont(editor._font)
        header_font.setPointSize(max(7, editor._font.pointSize() - 2))
        p.setFont(header_font)
        p.setPen(QColor(TEXT_SECONDARY))
        fm = QFontMetrics(header_font)
        cw = editor._fm.horizontalAdvance("0")
        h_scroll = editor.horizontalScrollBar().value()
        for col in range(editor._bytes_per_line):
            xh = editor._x_hex_for_col(col) - h_scroll
            lbl = f"{col:02X}"
            tw = fm.horizontalAdvance(lbl)
            # 两个 hex 字符的视觉中心在 xh + cw（两 nibble 中间）
            cx = xh + cw - tw / 2.0
            p.drawText(int(cx), _HEADER_HEIGHT - 3, lbl)
        p.setFont(editor._font)
        # 底部分隔线
        p.setPen(QColor(SURFACE_LIGHT))
        p.drawLine(0, self.height() - 1, self.width(), self.height() - 1)


class HexEditorView(QScrollArea):
    """显示十六进制 + ASCII。"""

    cursor_moved = Signal(int)
    selection_changed = Signal(int, int)
    # 鼠标悬停的字节偏移；-1 表示离开画布
    hover_byte_changed = Signal(int)
    # 画布上请求上下文菜单时的全局坐标（用于 QMenu.exec）
    context_menu_requested = Signal(QPoint)
    # 进程视图：竖直滚动条已在最底端时用户仍向下滚动（加载下一页）
    scroll_past_bottom_requested = Signal()
    # 进程视图：已在最顶端仍向上滚动（加载上一页）
    scroll_past_top_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._model: Optional[BinaryDataModel] = None
        self._bytes_per_line = DEFAULT_BYTES_PER_LINE
        self._font = QFont("Consolas", 11)
        if not self._font.exactMatch():
            self._font = QFont("Courier New", 11)
        self._fm = QFontMetrics(self._font)
        self._row_height = self._fm.height() + 4
        self._margin_x = 8
        self._cursor_pos = 0
        self._nibble = 0
        self._anchor: Optional[int] = None
        self._overwrite = True
        self._mouse_drag = False
        self._hex_area_left = 0
        self._hex_draw_left = 0  # 地址列之后、Hex 块实际绘制左缘（中间区居中）
        self._ascii_area_left = 0
        self._min_content_width = 400
        self._paint_width = 400
        self._search_hits: set[int] = set()
        # 逐字节比较着色：None 关闭；1=相同(绿) 2=不同(红)
        self._compare_highlights: Optional[list[int]] = None
        # 结构模板字段范围 [start, start+length) 高亮（对齐 010 struct outlining 的轻量版）
        self._struct_range: tuple[int, int] | None = None
        self._hover_idx: int = -1
        # 左侧列仅为相对当前缓冲起始的偏移；进程 VA/模块信息见状态栏。
        self._address_origin: int = 0
        self._address_relative_base: int | None = None
        self._process_image_size: int | None = None
        # 进程内存：底端/顶端边缘各触发一次翻页询问，离开边缘后重新允许
        self._scroll_next_process_page_armed = True
        self._scroll_prev_process_page_armed = True

        self.setFont(self._font)
        self._canvas = _HexCanvas(self)
        self._canvas.setFont(self._font)
        self.setWidget(self._canvas)
        self.setWidgetResizable(False)
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self._canvas.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._canvas.customContextMenuRequested.connect(self._on_canvas_context_menu)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.verticalScrollBar().valueChanged.connect(self._on_vertical_scroll_changed)
        self.horizontalScrollBar().valueChanged.connect(self._on_h_scroll_changed)

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(320, 200)

        # 固定列标题行（浮动于视口顶部，不随滚动消失）
        self._header_widget: Optional[_HeaderWidget] = None

    def _ensure_header_widget(self) -> None:
        """创建或更新列标题浮层控件。"""
        vp = self.viewport()
        if vp is None:
            return
        if self._header_widget is None:
            self._header_widget = _HeaderWidget(self, vp)
            self._header_widget.setGeometry(0, 0, vp.width(), _HEADER_HEIGHT)
            self._header_widget.show()
        else:
            self._header_widget.setGeometry(0, 0, vp.width(), _HEADER_HEIGHT)
        self._header_widget.raise_()
        self._header_widget.update()

    def _on_canvas_context_menu(self, pos: QPoint) -> None:
        self.context_menu_requested.emit(self._canvas.mapToGlobal(pos))

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        self.refresh_display()
        self._ensure_header_widget()

    def update_view(self) -> None:
        """仅重绘画布（不重新计算尺寸）。"""
        self._canvas.update()

    def refresh_display(self) -> None:
        self._fit_bytes_per_line_to_viewport()
        self._recalc_geometry()
        self._resize_canvas()
        self._canvas.update()
        self._ensure_header_widget()

    def set_model(self, model: Optional[BinaryDataModel]) -> None:
        if self._model is not None:
            try:
                self._model.data_changed.disconnect(self._on_data_changed)
            except TypeError:
                pass
        self._model = model
        if model is not None:
            model.data_changed.connect(self._on_data_changed)
        self._cursor_pos = 0
        self._anchor = None
        self._struct_range = None
        self._address_origin = 0
        self._address_relative_base = None
        self._process_image_size = None
        self._scroll_next_process_page_armed = True
        self._scroll_prev_process_page_armed = True
        self.refresh_display()

    def set_address_origin(self, origin: int) -> None:
        """缓冲首字节对应的 VA（进程当前页基址）；普通文件为 0。"""
        self._address_origin = max(0, int(origin))
        self.refresh_display()

    def set_process_image_range(
        self, image_base: int | None, image_size: int | None
    ) -> None:
        """主模块基址与 SizeOfImage（供状态栏等）；Hex 左侧仅显示缓冲内偏移。"""
        self._address_relative_base = None if image_base is None else int(image_base)
        self._process_image_size = (
            None if image_size is None or image_size <= 0 else int(image_size)
        )
        self.refresh_display()

    def set_address_relative_base(self, image_base: int | None) -> None:
        """兼容旧调用：仅设基址、不启用模块范围判断时等价于始终用页内偏移。"""
        self.set_process_image_range(image_base, None)

    def rearm_scroll_next_page_prompt(self) -> None:
        """取消「下一页」对话框后允许再次在底端触发询问。"""
        self._scroll_next_process_page_armed = True

    def rearm_scroll_prev_page_prompt(self) -> None:
        """取消「上一页」对话框后允许再次在顶端触发询问。"""
        self._scroll_prev_process_page_armed = True

    def rearm_scroll_edge_prompts(self) -> None:
        """成功切换内存页后允许再次在顶/底边缘触发翻页（尤其内容不足一屏时）。"""
        self._scroll_next_process_page_armed = True
        self._scroll_prev_process_page_armed = True

    def model(self) -> Optional[BinaryDataModel]:
        return self._model

    def set_search_hits(self, hits: set[int]) -> None:
        self._search_hits = hits
        self._canvas.update()

    def clear_search_hits(self) -> None:
        self._search_hits.clear()
        self._canvas.update()

    def set_structure_range(self, start: int, length: int) -> None:
        """高亮结构字段覆盖的字节范围（半透明显示）。"""
        if length <= 0:
            self._struct_range = None
        else:
            self._struct_range = (start, length)
        self._canvas.update()

    def clear_structure_range(self) -> None:
        self._struct_range = None
        self._canvas.update()

    def set_compare_highlights(self, highlights: Optional[list[int]]) -> None:
        """设置逐字节比较底色，None 表示关闭。"""
        self._compare_highlights = highlights
        self._canvas.update()

    def set_bytes_per_line(self, n: int) -> None:
        n = max(1, min(MAX_BYTES_PER_LINE, n))
        self._bytes_per_line = n
        self._recalc_geometry()
        self._resize_canvas()
        self._canvas.update()

    def bytes_per_line(self) -> int:
        return self._bytes_per_line

    def cursor_position(self) -> int:
        return self._cursor_pos

    def set_cursor_position(self, pos: int, *, nibble: Optional[int] = None) -> None:
        if self._model is None:
            return
        size = len(self._model)
        max_pos = max(0, size - 1) if size > 0 else 0
        pos = max(0, min(pos, max_pos))
        self._cursor_pos = pos
        if nibble is not None:
            self._nibble = 0 if nibble == 0 else 1
        self._ensure_cursor_visible()
        self._canvas.update()
        self.cursor_moved.emit(self._cursor_pos)
        self._emit_selection()

    def select_single_byte(self, offset: int) -> None:
        """将选区设为仅包含 offset 处一字节（anchor 与 cursor 同址）。"""
        if self._model is None:
            return
        size = len(self._model)
        if size == 0:
            return
        hi = max(0, size - 1)
        offset = max(0, min(offset, hi))
        self._anchor = offset
        self._cursor_pos = offset
        self._nibble = 0
        self._ensure_cursor_visible()
        self._canvas.update()
        self.cursor_moved.emit(self._cursor_pos)
        self._emit_selection()

    def selection_range(self) -> tuple[int, int]:
        if self._anchor is None:
            return (self._cursor_pos, self._cursor_pos)
        a, b = self._anchor, self._cursor_pos
        lo, hi = min(a, b), max(a, b)
        return (lo, hi + 1)

    def set_overwrite_mode(self, on: bool) -> None:
        self._overwrite = on

    def overwrite_mode(self) -> bool:
        return self._overwrite

    def nibble_index(self) -> int:
        return self._nibble

    def set_nibble_index(self, n: int) -> None:
        self._nibble = 0 if (n & 1) == 0 else 1
        self._canvas.update()

    def _emit_selection(self) -> None:
        s, e = self.selection_range()
        self.selection_changed.emit(s, e)

    def _on_data_changed(self, _start: int, _length: int) -> None:
        self._resize_canvas()
        self._canvas.update()

    def _digits_for_page_offset(self) -> int:
        if self._model is None or len(self._model) == 0:
            return 8
        hi = len(self._model) - 1
        return max(8, (hi.bit_length() + 3) // 4)

    def _addr_line_text(self, buf_idx: int) -> str:
        """左侧列：相对当前缓冲起始的纯偏移（十六进制）。模块信息见状态栏。"""
        off = buf_idx
        d = self._digits_for_page_offset()
        return f"{off:0{d}X}"

    def _addr_column_width_for_bpl(self, bpl: int) -> int:
        """地址列宽度（与纯十六进制偏移位数一致）。"""
        del bpl  # 偏移列与 bpl 无关
        digits = self._digits_for_page_offset()
        return self._fm.horizontalAdvance("0" * digits) + 2

    def _hex_cell_pitch(self, col: int) -> int:
        """单字节 Hex 区宽度（含两字符与字间略增间距，4 字节组间留空）。"""
        cw = self._fm.horizontalAdvance("0")
        sp = self._fm.horizontalAdvance(" ")
        extra = max(2, sp // 2)
        pitch = 2 * cw + sp + extra
        if col > 0 and col % 4 == 0:
            pitch += _GROUP_GAP
        return pitch

    def _hex_total_width(self, bpl: int) -> int:
        """计算给定每行字节数下 Hex 区的总像素宽度（含分组间距）。"""
        cw = self._fm.horizontalAdvance("0")
        sp = self._fm.horizontalAdvance(" ")
        extra = max(2, sp // 2)
        cell = 2 * cw + sp + extra
        groups = max(0, (bpl - 1) // 4)
        return bpl * cell + groups * _GROUP_GAP

    def _x_hex_for_col(self, col: int) -> int:
        """计算第 col 列字节的 Hex 绘制 x 坐标（逐列累加以处理分组间距）。"""
        x = self._hex_draw_left
        for c in range(col):
            x += self._hex_cell_pitch(c)
        return x

    def _content_width_for_bpl(self, bpl: int) -> int:
        """给定每行字节数，计算整行最小宽度（ASCII 右对齐时的紧凑布局，用于自适应视口）。"""
        bpl = max(1, min(MAX_BYTES_PER_LINE, bpl))
        if self._model is None:
            addr_w = self._fm.horizontalAdvance("0" * 8)
        else:
            addr_w = self._addr_column_width_for_bpl(bpl)
        cw = self._fm.horizontalAdvance("0")
        hex_w = self._hex_total_width(bpl)
        gap_after_addr = self._fm.horizontalAdvance("  ")
        ascii_w = bpl * cw
        x0 = self._margin_x
        hex_area_left = x0 + addr_w + gap_after_addr
        min_gap_hex_ascii = self._fm.horizontalAdvance(" ")
        return hex_area_left + hex_w + min_gap_hex_ascii + ascii_w + self._margin_x

    def _fit_bytes_per_line_to_viewport(self) -> None:
        """视口宽度自适应：16 > 8 > 4 字节/行。"""
        vw = max(1, self.viewport().width() - 4)
        if self._content_width_for_bpl(16) <= vw:
            best = 16
        elif self._content_width_for_bpl(8) <= vw:
            best = 8
        else:
            best = 4
        if self._bytes_per_line != best:
            self._bytes_per_line = best

    def _recalc_geometry(self) -> None:
        if self._model is None:
            self._min_content_width = 400
            self._paint_width = max(400, max(1, self.viewport().width()))
            return
        addr_w = self._addr_column_width_for_bpl(self._bytes_per_line)
        cw = self._fm.horizontalAdvance("0")
        hex_w = self._hex_total_width(self._bytes_per_line)
        ascii_w = self._bytes_per_line * cw
        x0 = self._margin_x
        gap_after_addr = self._fm.horizontalAdvance("  ")
        self._hex_area_left = x0 + addr_w + gap_after_addr
        min_gap_hex_ascii = self._fm.horizontalAdvance(" ")
        # 紧凑行宽：地址 + Hex + 最小间隙 + ASCII + 右边距
        self._min_content_width = (
            self._hex_area_left + hex_w + min_gap_hex_ascii + ascii_w + self._margin_x
        )

    def _resize_canvas(self) -> None:
        self._recalc_geometry()
        vpw = max(1, self.viewport().width())
        cw = self._fm.horizontalAdvance("0")
        ascii_w = self._bytes_per_line * cw
        if self._model is None:
            self._paint_width = max(self._min_content_width, vpw)
            self._hex_draw_left = 0
            h = self._row_height + _HEADER_HEIGHT
        else:
            self._paint_width = max(self._min_content_width, vpw)
            # ASCII 区紧贴画布右缘，中间 Hex 与 ASCII 之间留白随窗口变宽
            self._ascii_area_left = self._paint_width - self._margin_x - ascii_w
            hex_w = self._hex_total_width(self._bytes_per_line)
            mid = self._ascii_area_left - self._hex_area_left
            self._hex_draw_left = self._hex_area_left + max(0, (mid - hex_w) // 2)
            n = len(self._model)
            total_rows = max(1, (n + self._bytes_per_line - 1) // self._bytes_per_line)
            h = total_rows * self._row_height + _HEADER_HEIGHT
        h = max(self._row_height + _HEADER_HEIGHT, h)
        h = min(h, _QT_WIDGET_MAX_PX)
        w = min(max(self._paint_width, 1), _QT_WIDGET_MAX_PX)
        self._canvas.setFixedSize(w, h)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._fit_bytes_per_line_to_viewport()
        self._recalc_geometry()
        self._resize_canvas()
        self._canvas.update()
        self._ensure_header_widget()

    def _on_h_scroll_changed(self, value: int) -> None:
        self._canvas.update()
        if self._header_widget is not None:
            self._header_widget.update()

    def _ensure_cursor_visible(self) -> None:
        if self._model is None:
            return
        row = self._cursor_pos // self._bytes_per_line
        y = _HEADER_HEIGHT + row * self._row_height
        self.ensureVisible(0, y, 1, self._row_height)

    def _row_text_color(self, palette: QPalette, row: int) -> QColor:
        """Ensure text contrasts with row background on both light and dark themes."""
        if row % 2 == 0:
            return palette.color(QPalette.ColorRole.WindowText)
        fg = palette.color(QPalette.ColorRole.Text)
        alt = palette.color(QPalette.ColorRole.AlternateBase)
        if alt.lightness() < 50 and fg.lightness() < 50:
            return QColor(TEXT_PRIMARY)
        if alt.lightness() > 160 and fg.lightness() > 170:
            return QColor(28, 28, 32)
        return fg

    def _paint_canvas(self, event: QPaintEvent) -> None:
        if self._model is None:
            return
        p = QPainter(self._canvas)
        p.setFont(self._font)
        palette = self.palette()
        bg = palette.color(QPalette.ColorRole.Base)
        alt = QColor(palette.color(QPalette.ColorRole.AlternateBase))
        sel = QColor(palette.color(QPalette.ColorRole.Highlight))
        sel.setAlpha(120)
        hit_c = QColor(theme_color("search_hit"))
        hit_c.setAlpha(80)
        cmp_same = QColor(theme_color("compare_match"))
        cmp_same.setAlpha(85)
        cmp_diff = QColor(theme_color("compare_diff"))
        cmp_diff.setAlpha(100)
        struct_bg = QColor(theme_color("structure"))
        struct_bg.setAlpha(58)

        total = len(self._model)
        clip = event.rect()
        first_row = max(0, (clip.top() - _HEADER_HEIGHT) // self._row_height)
        last_row = (clip.bottom() - _HEADER_HEIGHT) // self._row_height + 1
        sel_lo, sel_hi = self.selection_range()

        cw = self._fm.horizontalAdvance("0")
        sep_color = QColor(SURFACE_LIGHT)
        cursor_row = self._cursor_pos // self._bytes_per_line if total > 0 else -1
        cursor_row_alpha = QColor(theme_color("cursor"))
        cursor_row_alpha.setAlpha(15)

        # ── Vertical separators ────────────────────────────────────────
        addr_w = self._addr_column_width_for_bpl(self._bytes_per_line)
        sep1_x = self._margin_x + addr_w + self._fm.horizontalAdvance(" ")
        sep2_x = self._ascii_area_left - self._fm.horizontalAdvance(" ")
        p.drawLine(int(sep1_x), 0, int(sep1_x), self._canvas.height())
        p.drawLine(int(sep2_x), 0, int(sep2_x), self._canvas.height())

        for row in range(max(0, first_row), last_row + 1):
            y_base = _HEADER_HEIGHT + row * self._row_height
            base = row * self._bytes_per_line
            if base >= total and total > 0:
                break

            if row % 2 == 1:
                p.fillRect(0, y_base, self._paint_width, self._row_height, alt)
            else:
                p.fillRect(0, y_base, self._paint_width, self._row_height, bg)

            # Cursor row subtle highlight
            if row == cursor_row:
                p.fillRect(0, y_base, self._paint_width, self._row_height, cursor_row_alpha)

            addr = self._addr_line_text(base)
            row_fg = self._row_text_color(palette, row)
            p.setPen(row_fg)
            p.drawText(self._margin_x, y_base + self._fm.ascent() + 2, addr)

            for col in range(self._bytes_per_line):
                idx = base + col
                if idx >= total:
                    break
                b = self._model.read_byte(idx)
                x_hex = self._x_hex_for_col(col)
                ax = self._ascii_area_left + col * cw
                cell_w = self._hex_cell_pitch(col) + 4

                in_struct = False
                if self._struct_range is not None:
                    s0, slen = self._struct_range
                    in_struct = s0 <= idx < s0 + slen
                if in_struct:
                    p.fillRect(
                        x_hex - 2,
                        y_base,
                        cell_w,
                        self._row_height,
                        struct_bg,
                    )
                    p.fillRect(ax - 1, y_base, cw + 2, self._row_height, struct_bg)

                if self._compare_highlights is not None and idx < len(self._compare_highlights):
                    ch = self._compare_highlights[idx]
                    if ch == 1:
                        p.fillRect(
                            x_hex - 2,
                            y_base,
                            cell_w,
                            self._row_height,
                            cmp_same,
                        )
                        p.fillRect(ax - 1, y_base, cw + 2, self._row_height, cmp_same)
                    elif ch == 2:
                        p.fillRect(
                            x_hex - 2,
                            y_base,
                            cell_w,
                            self._row_height,
                            cmp_diff,
                        )
                        p.fillRect(ax - 1, y_base, cw + 2, self._row_height, cmp_diff)

                in_sel = sel_lo <= idx < sel_hi
                if in_sel:
                    p.fillRect(
                        x_hex - 2,
                        y_base,
                        cell_w,
                        self._row_height,
                        sel,
                    )
                if idx in self._search_hits:
                    p.fillRect(
                        x_hex - 2,
                        y_base,
                        cell_w,
                        self._row_height,
                        hit_c,
                    )

                hx = f"{b:02X}"
                p.setPen(row_fg)
                p.drawText(x_hex, y_base + self._fm.ascent() + 2, hx[0])
                p.drawText(x_hex + cw, y_base + self._fm.ascent() + 2, hx[1])

                ch = _byte_to_ascii(b)
                if in_sel:
                    p.fillRect(ax - 1, y_base, cw + 2, self._row_height, sel)
                if idx in self._search_hits:
                    p.fillRect(ax - 1, y_base, cw + 2, self._row_height, hit_c)
                p.setPen(row_fg)
                p.drawText(ax, y_base + self._fm.ascent() + 2, ch)

        if total == 0:
            x_hex = self._x_hex_for_col(0)
            vx = x_hex + (self._nibble * cw)
            p.setPen(theme_color("cursor"))
            p.drawLine(int(vx), _HEADER_HEIGHT + 2, int(vx), _HEADER_HEIGHT + self._row_height - 2)
        elif self._cursor_pos < total:
            cr = self._cursor_pos // self._bytes_per_line
            cc = self._cursor_pos % self._bytes_per_line
            cy = _HEADER_HEIGHT + cr * self._row_height
            x_hex = self._x_hex_for_col(cc)
            vx = x_hex + (self._nibble * cw)
            p.setPen(theme_color("cursor"))
            p.drawLine(int(vx), int(cy) + 2, int(vx), int(cy + self._row_height - 2))

    def _byte_at_point(self, pos: QPoint) -> tuple[str, int]:
        if self._model is None:
            return ("", -1)
        x, y = pos.x(), pos.y()
        if y < _HEADER_HEIGHT:
            return ("", -1)
        row = (y - _HEADER_HEIGHT) // self._row_height
        total = len(self._model)
        base = row * self._bytes_per_line
        if base >= total:
            return ("", -1)

        cw = self._fm.horizontalAdvance("0")

        # Use cumulative x positions to find the column
        col = -1
        for c in range(self._bytes_per_line):
            xl = self._x_hex_for_col(c)
            xr = xl + self._hex_cell_pitch(c)
            if xl <= x < xr:
                col = c
                break
        if col < 0:
            # Check ASCII area
            ax_start = self._ascii_area_left
            ax_end = ax_start + self._bytes_per_line * cw
            if ax_start <= x < ax_end:
                col = (x - ax_start) // cw
                col = max(0, min(self._bytes_per_line - 1, col))
                idx = base + col
                if idx >= total:
                    idx = total - 1
                return ("ascii", idx)
            return ("", -1)
        idx = base + col
        if idx >= total:
            idx = total - 1
        x_hex = self._x_hex_for_col(col)
        frac = x - x_hex
        nibble = 0 if frac < cw else 1
        return ("hex", idx)

        if x >= self._ascii_area_left and x < self._ascii_area_left + self._bytes_per_line * cw:
            col = int((x - self._ascii_area_left) / cw)
            col = max(0, min(self._bytes_per_line - 1, col))
            idx = base + col
            if idx >= total:
                idx = total - 1
            return ("ascii", idx)

        return ("", -1)

    def _mouse_press(self, event: QMouseEvent) -> None:
        if self._model is None:
            return
        total = len(self._model)
        area, idx = self._byte_at_point(event.position().toPoint())
        if idx < 0 or (total > 0 and idx >= total):
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self.setFocus(Qt.FocusReason.MouseFocusReason)
            self._mouse_drag = True
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                if self._anchor is None:
                    self._anchor = self._cursor_pos
                self._cursor_pos = idx
            else:
                self._cursor_pos = idx
                self._anchor = None
            if area == "hex":
                cw = self._fm.horizontalAdvance("0")
                col = idx % self._bytes_per_line
                x_hex = self._x_hex_for_col(col)
                rel = event.position().x() - x_hex
                self._nibble = 0 if rel < cw else 1
            else:
                self._nibble = 0
            self._ensure_cursor_visible()
            self._canvas.update()
            self.cursor_moved.emit(self._cursor_pos)
            self._emit_selection()
        elif event.button() == Qt.MouseButton.RightButton:
            # 保留当前选区；上下文菜单仍作用于已有光标/选区
            self.setFocus(Qt.FocusReason.MouseFocusReason)
            return

    def _mouse_move(self, event: QMouseEvent) -> None:
        if self._model is None:
            return
        if self._mouse_drag and (event.buttons() & Qt.MouseButton.LeftButton):
            area, idx = self._byte_at_point(event.position().toPoint())
            if idx >= 0 and self._model is not None and idx < len(self._model):
                if self._anchor is None:
                    self._anchor = self._cursor_pos
                self._cursor_pos = idx
                self._ensure_cursor_visible()
                self._canvas.update()
                self.cursor_moved.emit(self._cursor_pos)
                self._emit_selection()
            return
        self._update_hover_from_point(event.position().toPoint())

    def _canvas_leave(self) -> None:
        if self._hover_idx != -1:
            self._hover_idx = -1
            self.hover_byte_changed.emit(-1)

    def _update_hover_from_point(self, pt: QPoint) -> None:
        if self._model is None:
            return
        area, idx = self._byte_at_point(pt)
        if idx >= 0 and idx < len(self._model):
            if idx != self._hover_idx:
                self._hover_idx = idx
                self.hover_byte_changed.emit(idx)
        else:
            if self._hover_idx != -1:
                self._hover_idx = -1
                self.hover_byte_changed.emit(-1)

    def _mouse_release(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._mouse_drag = False
            if self._anchor is not None and self._anchor == self._cursor_pos:
                self._anchor = None
                self._emit_selection()

    def _on_vertical_scroll_changed(self, value: int) -> None:
        self._canvas.update()
        sb = self.verticalScrollBar()
        mx = sb.maximum()
        if mx > 0:
            if value < mx:
                self._scroll_next_process_page_armed = True
            if value > 0:
                self._scroll_prev_process_page_armed = True

    def wheelEvent(self, event: QWheelEvent) -> None:
        m = self._model
        if (
            m is not None
            and len(m) > 0
            and getattr(m, "external_kind", None) == "process"
        ):
            sb = self.verticalScrollBar()
            dy = event.angleDelta().y()
            if dy == 0:
                dy = event.pixelDelta().y()
            mx = sb.maximum()
            v = sb.value()
            want_down = dy < 0
            want_up = dy > 0
            # 内容不足一屏：无法滚动，用滚轮方向区分上一页 / 下一页
            if mx <= 0:
                if want_up and self._scroll_prev_process_page_armed:
                    self._scroll_prev_process_page_armed = False
                    self.scroll_past_top_requested.emit()
                    event.accept()
                    return
                if want_down and self._scroll_next_process_page_armed:
                    self._scroll_next_process_page_armed = False
                    self.scroll_past_bottom_requested.emit()
                    event.accept()
                    return
            else:
                at_top = v <= 0
                at_bottom = v >= mx
                if (
                    at_top
                    and want_up
                    and self._scroll_prev_process_page_armed
                ):
                    self._scroll_prev_process_page_armed = False
                    self.scroll_past_top_requested.emit()
                    event.accept()
                    return
                if (
                    at_bottom
                    and want_down
                    and self._scroll_next_process_page_armed
                ):
                    self._scroll_next_process_page_armed = False
                    self.scroll_past_bottom_requested.emit()
                    event.accept()
                    return
        super().wheelEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if self._model is None:
            super().keyPressEvent(event)
            return
        key = event.key()
        size = len(self._model)

        if key == Qt.Key.Key_Left:
            self._move_nibble(-1, size)
            event.accept()
            return
        if key == Qt.Key.Key_Right:
            self._move_nibble(1, size)
            event.accept()
            return
        if key == Qt.Key.Key_Up:
            self._move_byte(-self._bytes_per_line, size)
            event.accept()
            return
        if key == Qt.Key.Key_Down:
            self._move_byte(self._bytes_per_line, size)
            event.accept()
            return
        if key == Qt.Key.Key_Home:
            self._cursor_pos = (self._cursor_pos // self._bytes_per_line) * self._bytes_per_line
            self._nibble = 0
            self._ensure_cursor_visible()
            self._canvas.update()
            self.cursor_moved.emit(self._cursor_pos)
            event.accept()
            return
        if key == Qt.Key.Key_End:
            line_start = (self._cursor_pos // self._bytes_per_line) * self._bytes_per_line
            self._cursor_pos = min(size - 1, line_start + self._bytes_per_line - 1) if size else 0
            self._nibble = 1
            self._ensure_cursor_visible()
            self._canvas.update()
            self.cursor_moved.emit(self._cursor_pos)
            event.accept()
            return
        if key == Qt.Key.Key_PageUp:
            vp = self.viewport()
            rows = max(1, vp.height() // self._row_height)
            self._move_byte(-rows * self._bytes_per_line, size)
            event.accept()
            return
        if key == Qt.Key.Key_PageDown:
            vp = self.viewport()
            rows = max(1, vp.height() // self._row_height)
            self._move_byte(rows * self._bytes_per_line, size)
            event.accept()
            return

        super().keyPressEvent(event)

    def _move_nibble(self, delta: int, size: int) -> None:
        nib = self._cursor_pos * 2 + self._nibble + delta
        if nib < 0:
            nib = 0
        max_nib = 2 * size - 1 if size > 0 else 0
        if nib > max_nib:
            nib = max_nib
        self._cursor_pos = nib // 2
        self._nibble = nib % 2
        self._ensure_cursor_visible()
        self._canvas.update()
        self.cursor_moved.emit(self._cursor_pos)

    def _move_byte(self, delta: int, size: int) -> None:
        hi = max(0, size - 1) if size else 0
        self._cursor_pos = max(0, min(hi, self._cursor_pos + delta))
        self._nibble = 0
        self._ensure_cursor_visible()
        self._canvas.update()
        self.cursor_moved.emit(self._cursor_pos)
