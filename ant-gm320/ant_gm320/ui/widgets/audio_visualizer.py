"""
High-performance dynamic audio visualizer widget for PySide6.
Renders real-time frequency spectrum bars and rhythmic beat ripples.
"""

import math
import random
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QTimer, QRectF
from PySide6.QtGui import QPainter, QColor, QLinearGradient, QBrush, QPen


class AudioVisualizerWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(140)
        self.setMinimumWidth(300)

        self._num_bars = 24
        self._bars = [0.0] * self._num_bars
        self._peak_caps = [0.0] * self._num_bars

        self._bass = 0.0
        self._mids = 0.0
        self._highs = 0.0
        self._overall_peak = 0.0

        self._ripple_radius = 0.0
        self._ripple_alpha = 0.0

        # Animation timer (40 FPS for super smooth rendering)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._animate_step)
        self._timer.start(25)

    def update_metrics(self, bass: float, mids: float, highs: float, peak: float):
        self._bass = bass
        self._mids = mids
        self._highs = highs
        self._overall_peak = peak

    def trigger_beat(self):
        self._ripple_radius = 10.0
        self._ripple_alpha = 0.8

    def _animate_step(self):
        # Calculate target heights for each frequency band
        for i in range(self._num_bars):
            ratio = i / float(self._num_bars - 1)
            if ratio < 0.33:
                # Bass range
                w = 1.0 - (ratio / 0.33)
                target = self._bass * w + self._mids * (1.0 - w) * 0.4
            elif ratio < 0.66:
                # Mids range
                w = (ratio - 0.33) / 0.33
                target = self._mids * (1.0 - w) + self._highs * w * 0.5
            else:
                # Highs range
                target = self._highs

            # Add subtle natural micro-jitter
            target = max(0.02, min(1.0, target * (0.85 + 0.3 * random.random())))

            # Smooth decay / rise
            if target > self._bars[i]:
                self._bars[i] = 0.5 * self._bars[i] + 0.5 * target
            else:
                self._bars[i] = 0.85 * self._bars[i] + 0.15 * target

            # Peak caps with gravity drop
            if self._bars[i] > self._peak_caps[i]:
                self._peak_caps[i] = self._bars[i]
            else:
                self._peak_caps[i] = max(0.0, self._peak_caps[i] - 0.02)

        # Expand ripple
        if self._ripple_alpha > 0.02:
            self._ripple_radius += 4.0
            self._ripple_alpha *= 0.90
        else:
            self._ripple_alpha = 0.0

        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()

        # Background
        painter.fillRect(0, 0, w, h, QColor("#12161f"))

        # Center ripple if active
        if self._ripple_alpha > 0.01:
            pen = QPen(QColor(0, 229, 255, int(self._ripple_alpha * 200)))
            pen.setWidth(2)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(QRectF(w / 2 - self._ripple_radius, h / 2 - self._ripple_radius,
                                       self._ripple_radius * 2, self._ripple_radius * 2))

        # Draw spectrum bars
        bar_gap = 4.0
        total_gaps = (self._num_bars - 1) * bar_gap
        bar_width = max(3.0, (w - 32 - total_gaps) / self._num_bars)
        x_start = (w - (self._num_bars * bar_width + total_gaps)) / 2

        for i in range(self._num_bars):
            bx = x_start + i * (bar_width + bar_gap)
            bh = max(4.0, self._bars[i] * (h - 28))
            by = h - 14 - bh

            # Bar Gradient: Cyan -> Electric Blue -> Magenta
            ratio = i / float(self._num_bars)
            grad = QLinearGradient(bx, h - 14, bx, by)
            if ratio < 0.4:
                grad.setColorAt(0.0, QColor("#00b4d8"))
                grad.setColorAt(1.0, QColor("#00e5ff"))
            elif ratio < 0.7:
                grad.setColorAt(0.0, QColor("#3a86ff"))
                grad.setColorAt(1.0, QColor("#7928ca"))
            else:
                grad.setColorAt(0.0, QColor("#7928ca"))
                grad.setColorAt(1.0, QColor("#ff007f"))

            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(grad))
            painter.drawRoundedRect(QRectF(bx, by, bar_width, bh), 2.5, 2.5)

            # Peak Cap line
            cap_y = h - 14 - (self._peak_caps[i] * (h - 28))
            painter.setPen(QPen(QColor("#ffffff"), 1.5))
            painter.drawLine(bx, cap_y, bx + bar_width, cap_y)
