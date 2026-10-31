"""
Interactive Double-Click Speed Test Widget.
Allows users to verify their mouse double-click interval and feel.
"""

import time
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPainter, QColor, QFont, QPen, QBrush


class DoubleClickTestWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(90)
        self.setCursor(Qt.PointingHandCursor)

        self._last_click_time = 0.0
        self._measured_ms = None
        self._flash_active = False

        self._flash_timer = QTimer(self)
        self._flash_timer.setSingleShot(True)
        self._flash_timer.timeout.connect(self._reset_flash)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            now = time.perf_counter()
            delta_ms = int((now - self._last_click_time) * 1000)
            self._last_click_time = now

            if 20 <= delta_ms <= 600:
                self._measured_ms = delta_ms
                self._flash_active = True
                self._flash_timer.start(800)
            else:
                self._measured_ms = None
            self.update()

    def _reset_flash(self):
        self._flash_active = False
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()

        if self._flash_active:
            bg_color = QColor(0, 245, 155, 30)
            border_color = QColor("#00f59b")
            title_text = f"Double Click Detected! ({self._measured_ms} ms)"
            subtitle_text = "Speed Rating: EXCELLENT" if self._measured_ms < 180 else "Speed Rating: NORMAL"
            sub_color = QColor("#00f59b")
        else:
            bg_color = QColor("#12161f")
            border_color = QColor("#273142")
            title_text = "Double Click Test Area"
            subtitle_text = "Click twice here to test your click interval"
            sub_color = QColor("#8b949e")

        painter.setPen(QPen(border_color, 1.5))
        painter.setBrush(QBrush(bg_color))
        painter.drawRoundedRect(2, 2, w - 4, h - 4, 8, 8)

        # Title
        font_title = QFont()
        font_title.setPointSize(11)
        font_title.setBold(True)
        painter.setFont(font_title)
        painter.setPen(QColor("#00e5ff" if not self._flash_active else "#00f59b"))
        painter.drawText(0, 18, w, 24, Qt.AlignCenter, title_text)

        # Subtitle
        font_sub = QFont()
        font_sub.setPointSize(9)
        painter.setFont(font_sub)
        painter.setPen(sub_color)
        painter.drawText(0, 46, w, 20, Qt.AlignCenter, subtitle_text)
