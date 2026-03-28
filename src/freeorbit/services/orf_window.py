"""ORF：滑窗将字节流解释为标量，按范围/排除筛选并表格展示，附分布图。"""

from __future__ import annotations

import math
import re
import struct
from decimal import Decimal
from typing import Optional

try:
    from PySide6.QtCharts import (
        QChart,
        QChartView,
        QLineSeries,
        QValueAxis,
    )

    _HAS_QTCHARTS = True
except ImportError:  # pragma: no cover
    _HAS_QTCHARTS = False

from PySide6.QtCore import QObject, QPointF, QRectF, QSize, Qt, QMargins, QThread, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPalette, QPen
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QToolTip,
    QSplitter,
    QStackedWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from freeorbit.i18n import tr
from freeorbit.viewmodel.document_editor import DocumentEditor

# 名称 -> (宽度, struct fmt, 是否浮点)
_ORF_TYPES: dict[str, tuple[int, str, bool]] = {
    "i8": (1, "<b", False),
    "u8": (1, "<B", False),
    "i16le": (2, "<h", False),
    "u16le": (2, "<H", False),
    "i32le": (4, "<i", False),
    "u32le": (4, "<I", False),
    "i64le": (8, "<q", False),
    "u64le": (8, "<Q", False),
    "f32le": (4, "<f", True),
    "f64le": (8, "<d", True),
}

_MAX_SCAN = 64 * 1024 * 1024
_MAX_TABLE_ROWS = 50_000


def _float_decimal_places(val: float) -> int:
    """浮点解析值的有效小数位数（Decimal 规范化，与界面 repr 一致思路）。"""
    if not math.isfinite(val):
        return 0
    try:
        d = Decimal(repr(val)).normalize()
        exp = d.as_tuple().exponent
        if exp >= 0:
            return 0
        return int(-exp)
    except Exception:
        return 0


def _value_search_matches(srep: str, expr: str, whole_word: bool) -> bool:
    """解析值搜索：`|` 分支为或；分支内空格分隔为与（AND）。全词匹配用单词边界。"""
    expr = expr.strip()
    if not expr:
        return True
    srep_l = srep.lower()
    or_parts = [p.strip() for p in re.split(r"\s*\|\s*", expr) if p.strip()]
    if not or_parts:
        return True
    for or_part in or_parts:
        and_terms = [t for t in or_part.split() if t]
        if not and_terms:
            continue
        ok_and = True
        for t in and_terms:
            tl = t.lower()
            if whole_word:
                try:
                    pat = r"(?<!\w)" + re.escape(tl) + r"(?!\w)"
                except re.error:
                    ok_and = False
                    break
                if not re.search(pat, srep_l, re.IGNORECASE):
                    ok_and = False
                    break
            else:
                if tl not in srep_l:
                    ok_and = False
                    break
        if ok_and:
            return True
    return False


def _build_offset_bins(offsets: list[int]) -> list[tuple[int, int, int]]:
    """将匹配绝对偏移分箱，返回 (区间左闭, 区间右开, 频数)。"""
    if not offsets:
        return []
    lo, hi = min(offsets), max(offsets)
    n = len(offsets)
    span = hi - lo + 1
    if span <= 0:
        return [(lo, lo + 1, n)]
    nbin = min(32, max(1, int(math.sqrt(max(1, n)))))
    nbin = min(nbin, max(1, span))
    counts = [0] * nbin
    for o in offsets:
        bi = min(nbin - 1, max(0, (o - lo) * nbin // span))
        counts[bi] += 1
    out: list[tuple[int, int, int]] = []
    for i in range(nbin):
        left = lo + (i * span) // nbin
        right = lo + ((i + 1) * span) // nbin
        if i == nbin - 1:
            right = hi + 1
        out.append((left, right, counts[i]))
    return out


def _trim_bins_for_display(bins: list[tuple[int, int, int]]) -> list[tuple[int, int, int]]:
    """去掉首尾频数为 0 的分箱，使横轴紧贴有数据的区间，避免两侧空白过大。"""
    if len(bins) <= 1:
        return list(bins)
    first: Optional[int] = None
    last: Optional[int] = None
    for i, (_, _, c) in enumerate(bins):
        if c > 0:
            if first is None:
                first = i
            last = i
    if first is None or last is None:
        return list(bins)
    return bins[first : last + 1]


class _OrfScanThread(QThread):
    """后台扫描，分批发射行。"""

    batch_ready = Signal(list)  # list[tuple[int, int, str, str]] 相位, 偏移, hex, 值
    scan_done = Signal(int, object)  # total_matches, list[tuple[int,int,int]] 偏移分箱频数
    failed = Signal(str)

    def __init__(
        self,
        data: bytes,
        start: int,
        width: int,
        fmt: str,
        is_float: bool,
        vmin: Optional[float],
        vmax: Optional[float],
        exclude_ranges: list[tuple[float, float]],
        dp_filter_enabled: bool,
        dp_min: int,
        dp_max: int,
        value_search: str,
        whole_word: bool,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._data = data
        self._start = start
        self._width = width
        self._fmt = fmt
        self._is_float = is_float
        self._vmin = vmin
        self._vmax = vmax
        self._exclude_ranges = exclude_ranges
        self._dp_filter_enabled = dp_filter_enabled
        self._dp_min = dp_min
        self._dp_max = dp_max
        self._value_search = value_search
        self._whole_word = whole_word

    def run(self) -> None:  # noqa: PLR0915
        try:
            d = self._data
            w = self._width
            n = len(d)
            rel_end = n - w + 1
            if rel_end <= 0:
                self.scan_done.emit(0, [])
                return

            batch: list[tuple[int, int, str, str]] = []
            total = 0
            match_offsets: list[int] = []
            emit_every = 2000

            def in_excluded_range(v: float) -> bool:
                for lo, hi in self._exclude_ranges:
                    if self._is_float:
                        if lo <= v <= hi:
                            return True
                    else:
                        iv = int(v)
                        if int(lo) <= iv <= int(hi):
                            return True
                return False

            def in_range(v: float) -> bool:
                if self._vmin is not None and v < self._vmin:
                    return False
                if self._vmax is not None and v > self._vmax:
                    return False
                if in_excluded_range(v):
                    return False
                return True

            for i in range(0, rel_end):
                chunk = d[i : i + w]
                try:
                    val = struct.unpack(self._fmt, chunk)[0]
                except struct.error:
                    continue
                fv = float(val) if not isinstance(val, float) else val
                # 浮点非有限值无分析意义，不参与筛选与结果
                if self._is_float and not math.isfinite(fv):
                    continue
                if not in_range(fv):
                    continue
                if self._is_float:
                    srep = repr(val)
                elif isinstance(val, int):
                    srep = str(val)
                else:
                    srep = str(int(val))
                if self._dp_filter_enabled and self._is_float:
                    dp = _float_decimal_places(fv)
                    if dp < self._dp_min or dp > self._dp_max:
                        continue
                if self._value_search:
                    if not _value_search_matches(
                        srep, self._value_search, self._whole_word
                    ):
                        continue
                off = self._start + i
                # 阅读框相位：文件绝对偏移 mod 类型宽度（类比密码子阅读框）
                phase = off % w
                hx = chunk.hex().upper()
                batch.append((phase, off, hx, srep))
                total += 1
                match_offsets.append(off)

                if len(batch) >= emit_every:
                    self.batch_ready.emit(batch)
                    batch = []
                if total >= _MAX_TABLE_ROWS:
                    break

            if batch:
                self.batch_ready.emit(batch)
            self.scan_done.emit(total, _build_offset_bins(match_offsets))
        except Exception as e:  # noqa: BLE001
            self.failed.emit(str(e))


class _OffsetBinHistogram(QWidget):
    """频数折线：不按直方图柱显示，无 X 轴刻度；水平方向每段宽度按该箱频数占总量比例分配。"""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._bins: list[tuple[int, int, int]] = []
        self.setMinimumSize(220, 200)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

    def sizeHint(self) -> QSize:
        return QSize(320, 260)

    def set_bins(self, bins: list[tuple[int, int, int]]) -> None:
        self._bins = _trim_bins_for_display(bins)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: ANN001
        del event
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        p.fillRect(rect, self.palette().color(QPalette.ColorRole.Base))
        text_col = self.palette().color(QPalette.ColorRole.Text)
        axis_col = self.palette().color(QPalette.ColorRole.Mid)

        if not self._bins:
            p.setPen(text_col)
            p.drawText(rect, Qt.AlignmentFlag.AlignCenter, tr("orf.hist_need_data"))
            return

        counts = [c for _, _, c in self._bins]
        mx = max(counts) if counts else 1
        n = len(self._bins)
        total_c = float(sum(counts))
        fm = p.fontMetrics()
        y_lab_w = max(fm.horizontalAdvance(str(mx)), fm.horizontalAdvance("0")) + 8
        margin_l = max(40, y_lab_w)
        margin_r, margin_t = 12, 20
        margin_b = 16
        plot = rect.adjusted(margin_l, margin_t, -margin_r, -margin_b)
        if plot.width() < 8 or plot.height() < 8:
            return

        inner_w = float(plot.width())
        # 各段水平宽度 ∝ 该箱频数（与表格中各箱命中数一致）；全为 0 时均分
        if total_c <= 0:
            seg_w = [inner_w / n] * n
        else:
            seg_w = [inner_w * (c / total_c) for c in counts]

        p.setPen(axis_col)
        p.setFont(QFont())
        y_title = tr("orf.chart_y_freq")
        p.save()
        p.translate(
            10,
            margin_t + plot.height() // 2 + fm.horizontalAdvance(y_title) // 2,
        )
        p.rotate(-90)
        p.drawText(0, 0, y_title)
        p.restore()

        plot_left = plot.left()
        plot_right = plot.right()
        for t in (0, mx):
            ty = plot.bottom() - int((t / mx) * plot.height()) if mx else plot.bottom()
            p.drawLine(plot_left, ty, plot_left - 4, ty)
            lab = str(t)
            p.drawText(
                plot_left - fm.horizontalAdvance(lab) - 6,
                ty + fm.ascent() // 2 - fm.height() // 2,
                lab,
            )

        p.drawLine(plot_left, plot.bottom(), plot_right, plot.bottom())

        # 折线顶点：每段水平中心、高度 ∝ 频数
        pts: list[QPointF] = []
        x = float(plot_left)
        for i, c in enumerate(counts):
            w = seg_w[i]
            cx = x + w * 0.5
            yv = plot.bottom() - (plot.height() * (c / mx) if mx else 0.0)
            pts.append(QPointF(cx, yv))
            x += w

        line_col = QColor(80, 140, 220)
        fill_col = QColor(80, 140, 220, 55)
        if len(pts) == 1:
            p.setPen(QPen(line_col, 2))
            p.drawEllipse(pts[0], 3, 3)
        elif len(pts) >= 2:
            path = QPainterPath()
            path.moveTo(pts[0])
            for q in pts[1:]:
                path.lineTo(q)
            p.setPen(QPen(line_col, 2))
            p.drawPath(path)
            fill = QPainterPath(path)
            fill.lineTo(QPointF(pts[-1].x(), float(plot.bottom())))
            fill.lineTo(QPointF(pts[0].x(), float(plot.bottom())))
            fill.closeSubpath()
            p.fillPath(fill, fill_col)


if _HAS_QTCHARTS:

    class _OrfOffsetChartView(QChartView):
        """QtCharts：横轴 QValueAxis（分箱序号 0..n-1）+ 折线；柱形在视口中自绘，避免 QBarCategoryAxis 字符串序问题。"""

        _BAR_HW = 0.34  # 柱半宽，总宽约 0.68

        def __init__(self, parent: Optional[QWidget] = None) -> None:
            super().__init__(parent)
            self._chart = QChart()
            self._chart.legend().setVisible(False)
            self._chart.setBackgroundRoundness(0)
            self._chart.setMargins(QMargins(10, 8, 10, 6))
            self.setChart(self._chart)
            self.setRenderHint(QPainter.RenderHint.Antialiasing)

            self._axis_x = QValueAxis()
            self._axis_x.setTitleText(tr("orf.chart_axis_offset_interval"))
            self._axis_x.setLabelsVisible(False)
            self._axis_y = QValueAxis()
            self._axis_y.setTitleText(tr("orf.chart_y_freq"))
            self._axis_y.setLabelFormat("%.0f")
            self._axis_y.setMin(0)

            self._line_series = QLineSeries()
            self._line_series.setPointsVisible(True)

            line_col = QColor(45, 95, 185)
            self._line_series.setPen(QPen(line_col, 2))
            self._line_series.setColor(line_col)

            self._chart.addSeries(self._line_series)
            self._chart.addAxis(self._axis_x, Qt.AlignmentFlag.AlignBottom)
            self._chart.addAxis(self._axis_y, Qt.AlignmentFlag.AlignLeft)
            self._line_series.attachAxis(self._axis_x)
            self._line_series.attachAxis(self._axis_y)

            self._bins_data: list[tuple[int, int, int]] = []

            self.setMouseTracking(True)

        def _bar_rect_for_index(self, i: int, cnt: float) -> QRectF:
            """数据坐标：柱中心 i，纵轴 0..cnt。"""
            hw = self._BAR_HW
            x0 = float(i) - hw
            x1 = float(i) + hw
            c = self.chart()
            tl = c.mapToPosition(QPointF(x0, cnt), self._line_series)
            br = c.mapToPosition(QPointF(x1, 0.0), self._line_series)
            return QRectF(tl, br).normalized()

        def paintEvent(self, event) -> None:  # noqa: ANN001
            super().paintEvent(event)
            if not self._bins_data:
                return
            p = QPainter(self.viewport())
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            clip = self.chart().plotArea()
            p.setClipRect(clip.toRect())
            bar_fill = QColor(90, 145, 220, 140)
            border = QColor(55, 105, 175)
            pen = QPen(border, 1)
            for i, (_, _, cnt) in enumerate(self._bins_data):
                fc = float(cnt)
                if fc <= 0:
                    continue
                r = self._bar_rect_for_index(i, fc)
                if r.isNull() or r.width() <= 0 or r.height() <= 0:
                    continue
                p.setBrush(bar_fill)
                p.setPen(pen)
                p.drawRect(r)

        def set_bins(self, bins: list[tuple[int, int, int]]) -> None:
            bins = _trim_bins_for_display(bins)
            self._line_series.clear()
            self._bins_data = list(bins)
            if not bins:
                self._chart.setTitle("")
                return
            mx_c = 0
            for i, (_, _, cnt) in enumerate(bins):
                mx_c = max(mx_c, cnt)
                self._line_series.append(float(i), float(cnt))
            self._axis_y.setRange(0.0, max(1.0, float(mx_c) * 1.08))
            n = len(bins)
            self._axis_x.setRange(-0.5, float(n) - 0.5)
            self._axis_x.setLabelsVisible(False)
            self._chart.setTitle("")
            self.viewport().update()

        def _show_tip_at_index(self, idx: int) -> None:
            if idx < 0 or idx >= len(self._bins_data):
                return
            lo, hi, cnt = self._bins_data[idx]
            tip = tr("orf.chart_tip_bin").format(lo=lo, hi=hi, cnt=cnt)
            QToolTip.showText(self.cursor().pos(), tip, self)

        def mouseMoveEvent(self, event) -> None:
            super().mouseMoveEvent(event)
            if not self._bins_data:
                return
            vp = event.position()
            if not self.chart().plotArea().contains(vp):
                QToolTip.hideText()
                return
            val = self.chart().mapToValue(vp, self._line_series)
            x = float(val.x())
            n = len(self._bins_data)
            hw = self._BAR_HW
            for i in range(n):
                if float(i) - hw <= x <= float(i) + hw:
                    self._show_tip_at_index(i)
                    return
            idx = int(round(max(0, min(n - 1, x))))
            self._show_tip_at_index(idx)

        def leaveEvent(self, event) -> None:  # noqa: ANN001
            super().leaveEvent(event)
            QToolTip.hideText()


def _parse_float(s: str) -> Optional[float]:
    t = s.strip()
    if not t:
        return None
    try:
        return float(t)
    except ValueError:
        return None


def _parse_num_token(s: str, is_float: bool) -> Optional[float]:
    t = s.strip()
    if not t:
        return None
    try:
        if is_float:
            return float(t)
        if "." in t or "e" in t.lower():
            return float(t)
        return float(int(t, 0))
    except ValueError:
        return None


def _parse_exclude_ranges(text: str, is_float: bool) -> list[tuple[float, float]]:
    """解析排除区间（闭区间）：..、~、两数空格、或最后一个 '-' 作为分界（支持 -5-10）。"""
    ranges: list[tuple[float, float]] = []
    raw = text.replace(",", "\n").replace(";", "\n")
    for line in raw.split("\n"):
        line = line.strip()
        if not line:
            continue
        a_s: Optional[str] = None
        b_s: Optional[str] = None
        if ".." in line:
            a_s, b_s = line.split("..", 1)
        elif "~" in line:
            a_s, b_s = line.split("~", 1)
        elif "—" in line:
            a_s, b_s = line.split("—", 1)
        elif "–" in line:
            a_s, b_s = line.split("–", 1)
        else:
            parts = line.split()
            if len(parts) == 2:
                a_s, b_s = parts[0], parts[1]
            elif "-" in line:
                ax = line.rfind("-")
                if ax > 0:
                    a_s, b_s = line[:ax], line[ax + 1 :]
        if a_s is None or b_s is None:
            continue
        lo = _parse_num_token(a_s.strip(), is_float)
        hi = _parse_num_token(b_s.strip(), is_float)
        if lo is None or hi is None:
            continue
        if lo > hi:
            lo, hi = hi, lo
        ranges.append((lo, hi))
    return ranges


class OrfWindow(QWidget):
    """非模态分析窗口，绑定单个 DocumentEditor。"""

    def __init__(self, doc: DocumentEditor, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._doc = doc
        self._thread: Optional[_OrfScanThread] = None
        self._phase_parents: dict[int, QTreeWidgetItem] = {}
        # 必须带 Window 标志，否则作为 MainWindow 子控件会被裁剪在父窗口客户区内，看起来像「窗口坏了」
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.WindowCloseButtonHint
            | Qt.WindowType.WindowMinMaxButtonsHint
        )
        self.setWindowTitle(tr("orf.title"))
        self.setMinimumSize(720, 480)
        # 绑定文档生命周期：关闭标签后避免仍持有已销毁的 DocumentEditor
        doc.destroyed.connect(self.close)
        root = QVBoxLayout(self)

        g = QGroupBox(tr("orf.params"))
        fl = QFormLayout(g)
        self._combo = QComboBox()
        for k in _ORF_TYPES:
            self._combo.addItem(k, k)
        self._min_e = QLineEdit()
        self._max_e = QLineEdit()
        self._min_e.setPlaceholderText(tr("orf.min_ph"))
        self._max_e.setPlaceholderText(tr("orf.max_ph"))
        self._exclude_e = QLineEdit()
        self._exclude_e.setPlaceholderText(tr("orf.exclude_range_ph"))
        self._sel_only = QCheckBox(tr("orf.selection_only"))
        self._chk_dp = QCheckBox(tr("orf.dp_filter_enable"))
        self._chk_dp.setChecked(False)
        self._spin_dp_min = QSpinBox()
        self._spin_dp_min.setRange(0, 20)
        self._spin_dp_min.setValue(0)
        self._spin_dp_max = QSpinBox()
        self._spin_dp_max.setRange(0, 20)
        self._spin_dp_max.setValue(12)
        dp_row = QHBoxLayout()
        dp_row.addWidget(self._chk_dp)
        dp_row.addWidget(QLabel(tr("orf.dp_min")))
        dp_row.addWidget(self._spin_dp_min)
        dp_row.addWidget(QLabel(tr("orf.dp_max")))
        dp_row.addWidget(self._spin_dp_max)
        dp_row.addStretch()
        dp_w = QWidget()
        dp_w.setLayout(dp_row)
        self._value_search_e = QLineEdit()
        self._value_search_e.setPlaceholderText(tr("orf.value_search_ph"))
        self._chk_whole_word = QCheckBox(tr("orf.search_whole_word"))
        vs_row = QHBoxLayout()
        vs_row.addWidget(self._value_search_e, 1)
        vs_row.addWidget(self._chk_whole_word)
        vs_w = QWidget()
        vs_w.setLayout(vs_row)
        fl.addRow(tr("orf.dtype"), self._combo)
        fl.addRow(tr("orf.range_min"), self._min_e)
        fl.addRow(tr("orf.range_max"), self._max_e)
        fl.addRow(tr("orf.exclude_ranges"), self._exclude_e)
        fl.addRow(tr("orf.dp_filter"), dp_w)
        fl.addRow(tr("orf.value_search"), vs_w)
        fl.addRow(self._sel_only)
        self._combo.currentIndexChanged.connect(self._sync_orf_float_controls)
        self._chk_dp.toggled.connect(self._sync_orf_float_controls)
        self._sync_orf_float_controls()
        root.addWidget(g)

        btn_row = QHBoxLayout()
        self._btn = QPushButton(tr("orf.scan"))
        self._btn.clicked.connect(self._start_scan)
        btn_row.addWidget(self._btn)
        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.hide()
        btn_row.addWidget(self._progress, 1)
        root.addLayout(btn_row)

        # 左：结果树；右：频数–偏移分布直方图（可拖动分割条调宽度）
        split = QSplitter(Qt.Orientation.Horizontal)
        self._tree = QTreeWidget()
        self._tree.setColumnCount(4)
        self._tree.setHeaderLabels(
            [
                tr("orf.col_phase_group"),
                tr("orf.col_offset"),
                tr("orf.col_hex"),
                tr("orf.col_value"),
            ]
        )
        self._tree.setAlternatingRowColors(True)
        self._tree.setUniformRowHeights(True)
        self._tree.itemClicked.connect(self._on_tree_item_clicked)
        split.addWidget(self._tree)

        self._hist_label = QLabel(
            tr("orf.chart_line_caption_qt")
            if _HAS_QTCHARTS
            else tr("orf.chart_line_caption")
        )
        if _HAS_QTCHARTS:
            self._hist = _OrfOffsetChartView()
        else:
            self._hist = _OffsetBinHistogram()
        self._chart_placeholder = QWidget()
        self._chart_placeholder.setAutoFillBackground(True)
        self._chart_placeholder.setMinimumHeight(200)
        self._chart_placeholder.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self._chart_stack = QStackedWidget()
        self._chart_stack.addWidget(self._chart_placeholder)
        self._chart_stack.addWidget(self._hist)
        self._chart_stack.setCurrentIndex(0)
        self._chart_stack.setMinimumHeight(200)
        # 分箱多时横向加宽内容区，由滚动条左右浏览（避免柱体被压扁）
        self._chart_scroll = QScrollArea()
        self._chart_scroll.setWidget(self._chart_stack)
        self._chart_scroll.setWidgetResizable(True)
        self._chart_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._chart_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self._chart_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        w_chart = QWidget()
        chart_lay = QVBoxLayout(w_chart)
        chart_lay.setContentsMargins(8, 0, 0, 0)
        chart_lay.setSpacing(6)
        chart_lay.addWidget(self._hist_label)
        chart_lay.addWidget(self._chart_scroll, 1)
        split.addWidget(w_chart)
        split.setStretchFactor(0, 5)
        split.setStretchFactor(1, 3)
        split.setSizes([540, 360])
        self._orf_split = split
        self._orf_split.splitterMoved.connect(self._sync_orf_tree_quarter_columns)
        root.addWidget(split, 1)

        self._apply_orf_tree_columns()
        QTimer.singleShot(0, self._sync_orf_tree_quarter_columns)

        self._status = QLabel("")
        root.addWidget(self._status)

    def _sync_orf_float_controls(self) -> None:
        """小数位筛选仅对浮点类型有效。"""
        key = self._combo.currentData()
        is_f = isinstance(key, str) and _ORF_TYPES.get(key, (0, "", False))[2]
        self._chk_dp.setEnabled(is_f)
        on = is_f and self._chk_dp.isChecked()
        self._spin_dp_min.setEnabled(on)
        self._spin_dp_max.setEnabled(on)

    def _on_tree_item_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        del column
        if item.childCount() > 0:
            return
        off_s = item.text(1).strip()
        if not off_s.startswith("0x"):
            return
        try:
            off = int(off_s, 16)
        except ValueError:
            return
        m = self._doc.model()
        if off < 0 or off >= len(m):
            QMessageBox.information(self, tr("orf.title"), tr("orf.jump_out_of_range"))
            return
        self._doc.hex_view().select_single_byte(off)
        mw = self._doc.window()
        if mw is not None:
            mw.raise_()
            mw.activateWindow()

    def _adjust_orf_splitter_for_chart(self, n_bins: int) -> None:
        """按分箱数微调左右分割，使右侧图区宽度与数据量匹配。"""
        w = max(0, self.width())
        if w < 320 or not hasattr(self, "_orf_split"):
            return
        # 分箱越多，右侧略增宽，避免每段过窄；有上限以免挤压表格
        extra = min(0.12, max(0.0, (n_bins - 6) * 0.008))
        ratio_right = min(0.48, 0.30 + extra)
        rw = int(w * ratio_right)
        lw = max(280, w - rw - 6)
        rw = max(240, min(rw, w - lw))
        self._orf_split.setSizes([lw, rw])

    def _update_orf_chart_min_width(self, n_bins: int) -> None:
        """按分箱数设定图表最小宽度；组数多时图区下方出现横向滚动条。"""
        if n_bins <= 0:
            self._chart_stack.setMinimumWidth(0)
            return
        min_per_bin = 48
        self._chart_stack.setMinimumWidth(max(280, n_bins * min_per_bin))

    def _apply_orf_tree_columns(self) -> None:
        """四列固定宽度，按视口宽度均分为四等份。"""
        h = self._tree.header()
        h.setStretchLastSection(False)
        for col in range(4):
            h.setSectionResizeMode(col, QHeaderView.ResizeMode.Fixed)
        self._sync_orf_tree_quarter_columns()

    def _sync_orf_tree_quarter_columns(self) -> None:
        """每列宽度 = 树视图视口宽度 / 4（余数像素分给前几列）。"""
        if not hasattr(self, "_tree"):
            return
        w = max(4, self._tree.viewport().width())
        each = w // 4
        rem = w - each * 4
        for i in range(4):
            self._tree.setColumnWidth(i, each + (1 if i < rem else 0))

    def _start_scan(self) -> None:
        if self._thread is not None and self._thread.isRunning():
            return

        m = self._doc.model()
        n = len(m)
        if n < 1:
            QMessageBox.information(self, tr("orf.title"), tr("orf.empty_doc"))
            return

        key = self._combo.currentData()
        assert isinstance(key, str)
        w, fmt, is_float = _ORF_TYPES[key]

        a, b = self._doc.hex_view().selection_range()
        if self._sel_only.isChecked():
            if a == b:
                QMessageBox.information(self, tr("orf.title"), tr("orf.need_selection"))
                return
            start = min(a, b)
            end = max(a, b)
        else:
            start, end = 0, n

        span = end - start
        if span < w:
            QMessageBox.information(self, tr("orf.title"), tr("orf.span_too_small"))
            return
        if span > _MAX_SCAN:
            QMessageBox.warning(
                self,
                tr("orf.title"),
                tr("orf.scan_too_large").format(_MAX_SCAN),
            )
            return

        vmin = _parse_float(self._min_e.text())
        vmax = _parse_float(self._max_e.text())
        excl_ranges = _parse_exclude_ranges(self._exclude_e.text(), is_float)

        dp_on = self._chk_dp.isChecked() and is_float
        if dp_on and self._spin_dp_min.value() > self._spin_dp_max.value():
            QMessageBox.warning(self, tr("orf.title"), tr("orf.dp_range_invalid"))
            return

        try:
            raw = m.read(start, span)
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, tr("orf.title"), str(e))
            return

        self._tree.clear()
        self._phase_parents.clear()
        self._chart_stack.setMinimumWidth(0)
        self._chart_stack.setCurrentIndex(0)
        self._btn.setEnabled(False)
        self._progress.setRange(0, 0)
        self._progress.show()
        self._status.setText(tr("orf.scanning"))

        th = _OrfScanThread(
            raw,
            start,
            w,
            fmt,
            is_float,
            vmin,
            vmax,
            excl_ranges,
            dp_on,
            self._spin_dp_min.value(),
            self._spin_dp_max.value(),
            self._value_search_e.text().strip(),
            self._chk_whole_word.isChecked(),
            self,
        )
        self._thread = th
        th.batch_ready.connect(self._on_orf_batch)
        th.scan_done.connect(self._on_done)
        th.failed.connect(self._on_fail)
        th.finished.connect(self._on_thread_finished)
        th.start()

    def _on_orf_batch(self, batch: list[tuple[int, int, str, str]]) -> None:
        for phase, off, hx, val in batch:
            if phase not in self._phase_parents:
                par = QTreeWidgetItem(
                    [tr("orf.phase_parent_pending").format(r=phase), "", "", ""]
                )
                par.setData(0, Qt.ItemDataRole.UserRole, phase)
                self._tree.addTopLevelItem(par)
                self._phase_parents[phase] = par
            par = self._phase_parents[phase]
            QTreeWidgetItem(par, ["", f"0x{off:X}", hx, val])

    def _sort_phase_tree(self) -> None:
        items: list[QTreeWidgetItem] = []
        while self._tree.topLevelItemCount():
            items.append(self._tree.takeTopLevelItem(0))

        def _key(it: QTreeWidgetItem) -> int:
            d = it.data(0, Qt.ItemDataRole.UserRole)
            return int(d) if d is not None else 0

        items.sort(key=_key)
        for it in items:
            self._tree.addTopLevelItem(it)

    def _on_done(self, total: int, offset_bins: object) -> None:
        bins_list: list = offset_bins if isinstance(offset_bins, list) else []
        self._update_orf_chart_min_width(len(bins_list))
        self._chart_stack.setCurrentIndex(1)
        self._hist.set_bins(bins_list)
        for phase, par in self._phase_parents.items():
            par.setText(0, tr("orf.phase_parent").format(r=phase, n=par.childCount()))
        self._sort_phase_tree()
        self._status.setText(tr("orf.done_count").format(total))
        self._apply_orf_tree_columns()
        self._tree.expandAll()
        nb = len(bins_list)
        QTimer.singleShot(0, lambda n=nb: self._adjust_orf_splitter_for_chart(n))
        QTimer.singleShot(
            0, lambda: self._chart_scroll.horizontalScrollBar().setValue(0)
        )

    def _on_fail(self, msg: str) -> None:
        QMessageBox.warning(self, tr("orf.title"), msg)
        self._status.setText("")

    def _on_thread_finished(self) -> None:
        self._progress.hide()
        self._btn.setEnabled(True)
        self._thread = None

    def resizeEvent(self, event) -> None:  # noqa: ANN001
        super().resizeEvent(event)
        self._sync_orf_tree_quarter_columns()

    def closeEvent(self, event) -> None:  # noqa: ANN001
        # 先断开线程信号，避免 wait 返回后主线程才处理队列中的 scan_done，对已销毁窗口调槽崩溃
        if self._thread is not None:
            th = self._thread
            try:
                th.batch_ready.disconnect()
                th.scan_done.disconnect()
                th.failed.disconnect()
                th.finished.disconnect()
            except (TypeError, RuntimeError):
                pass
            if th.isRunning():
                th.wait(8000)
            self._thread = None
        super().closeEvent(event)
