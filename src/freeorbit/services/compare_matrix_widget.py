"""Byte-level comparison matrix (Dot Plot): direct byte comparison with downsampling + QImage rendering."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import Qt, Signal, QThread, QRect, QSize
from PySide6.QtGui import QImage, QPainter, QColor, QFont
from PySide6.QtWidgets import QSizePolicy, QWidget

from freeorbit.theme import (
    theme_color,
    font_default,
    SURFACE_DARKEST,
    SURFACE_LIGHT,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)

if TYPE_CHECKING:
    from freeorbit.model.binary_data_model import BinaryDataModel

MATCH_COLOR = theme_color("matrix_match")
BG_COLOR = QColor(SURFACE_DARKEST)
BORDER_COLOR = QColor(SURFACE_LIGHT)


class _CompareMatrixThread(QThread):
    """Background thread: byte-level comparison matrix as QImage."""

    image_ready = Signal(QImage)

    def __init__(
        self,
        left: "BinaryDataModel",
        right: "BinaryDataModel",
        sample_step: int = 1,
        max_dim: int = 4096,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._left = left
        self._right = right
        self._sample_step = max(sample_step, 1)
        self._max_dim = max_dim

    def run(self) -> None:
        left_len = len(self._left)
        right_len = len(self._right)
        if left_len == 0 or right_len == 0:
            self.image_ready.emit(QImage(1, 1, QImage.Format.Format_RGB888))
            return

        ss = self._sample_step
        bx = math.ceil(left_len / ss)
        by = math.ceil(right_len / ss)

        step_x = max(1, math.ceil(bx / self._max_dim))
        step_y = max(1, math.ceil(by / self._max_dim))
        img_w = math.ceil(bx / step_x)
        img_h = math.ceil(by / step_y)

        image = QImage(img_w, img_h, QImage.Format.Format_RGB888)
        image.fill(BG_COLOR)

        match_rgb = MATCH_COLOR.rgb()
        no_match = BG_COLOR.rgb()

        for py in range(img_h):
            if self.isInterruptionRequested():
                return
            right_idx = py * step_y
            right_off = right_idx * ss
            right_byte = self._right.read_byte(right_off)
            for px in range(img_w):
                left_idx = px * step_x
                left_off = left_idx * ss
                left_byte = self._left.read_byte(left_off)
                if left_byte == right_byte:
                    image.setPixelColor(px, py, QColor(match_rgb))
                # else: already filled with BG_COLOR

        self.image_ready.emit(image)


class CompareMatrixWidget(QWidget):
    """Widget displaying a byte-level comparison matrix with 1:1 aspect ratio."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._image: Optional[QImage] = None
        self._label_y: str = ""
        self._label_x: str = ""
        self.setMinimumSize(200, 200)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.setStyleSheet(
            f"CompareMatrixWidget {{ border: 1px solid {SURFACE_LIGHT}; background: {SURFACE_DARKEST}; }}"
        )

    def set_labels(self, y_label: str, x_label: str) -> None:
        """Set axis labels: y_label = left/vertical axis (File B), x_label = bottom/horizontal axis (File A)."""
        self._label_y = y_label
        self._label_x = x_label
        self.update()

    def set_image(self, image: QImage) -> None:
        self._image = image
        self.update()

    def sizeHint(self) -> QSize:
        return QSize(400, 400)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect()

        # Fill background
        painter.fillRect(rect, BG_COLOR)

        if self._image is None or self._image.isNull():
            painter.setPen(QColor(TEXT_PRIMARY))
            painter.setFont(font_default(10))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "No data")
            return

        # Reserve space for labels
        label_margin_y = 28 if self._label_y else 4
        label_margin_x = 22 if self._label_x else 4
        top = rect.top() + label_margin_y
        left = rect.left() + 4
        inner_w = rect.width() - 8 - label_margin_x
        inner_h = rect.height() - 4 - label_margin_y

        # Scale preserving image aspect ratio (len(A):len(B)), centered
        img_w = max(self._image.width(), 1)
        img_h = max(self._image.height(), 1)
        scale_w = inner_w
        scale_h = int(inner_w * (img_h / img_w))
        if scale_h > inner_h:
            scale_h = inner_h
            scale_w = int(inner_h * (img_w / img_h))
        matrix_rect = QRect(
            left + (inner_w - scale_w) // 2,
            top + (inner_h - scale_h) // 2,
            scale_w,
            scale_h,
        )

        # Draw border around matrix
        painter.setPen(BORDER_COLOR)
        painter.drawRect(matrix_rect.adjusted(-1, -1, 1, 1))

        scaled = self._image.scaled(
            matrix_rect.size(),
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        painter.drawImage(matrix_rect, scaled)

        # Draw axis labels
        painter.setFont(font_default(8))
        painter.setPen(QColor(TEXT_SECONDARY))

        if self._label_y:
            painter.save()
            painter.translate(rect.left() + 2, matrix_rect.center().y())
            painter.rotate(-90)
            painter.drawText(QRect(-60, -10, 120, 20), Qt.AlignmentFlag.AlignCenter, self._label_y)
            painter.restore()

        if self._label_x:
            painter.drawText(
                QRect(matrix_rect.left(), matrix_rect.bottom() + 4, matrix_rect.width(), 20),
                Qt.AlignmentFlag.AlignCenter,
                self._label_x,
            )

        # Low-resolution hint
        if self._image.width() <= 2 and self._image.height() <= 2:
            painter.setPen(QColor(TEXT_PRIMARY))
            painter.setFont(font_default(9))
            txt = (
                "Matrix too small ({w}x{h} pixels).\n"
                "Try a smaller sample step or larger files."
            ).format(w=self._image.width(), h=self._image.height())
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, txt)
