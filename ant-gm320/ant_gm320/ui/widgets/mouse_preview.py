"""
Interactive Mouse Diagram widget for Ant Esports GM320.
Renders the high-res mouse illustration with interactive glowing numbered callouts (1-8).
Badges are mathematically aligned with the mouse hardware button positions.
"""

import os
from typing import Dict, Tuple, Optional
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, Signal, QRectF, QPointF
from PySide6.QtGui import QPainter, QColor, QPixmap, QPen, QBrush, QFont, QRadialGradient

ASSET_MOUSE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "assets", "mouse_clean.png")

# Calibrated coordinates on centered mouse_clean.png (260 x 420)
# Mouse centerline (wheel, DPI, LED loop) is exactly at x = 0.500
BUTTON_ANCHORS = {
    1: (0.327, 0.250, "Left Click"),
    2: (0.673, 0.250, "Right Click"),
    3: (0.500, 0.262, "Middle Click"),
    4: (0.500, 0.381, "DPI Switch"),
    5: (0.500, 0.464, "LED Loop"),
    6: (0.173, 0.369, "Rapid Fire"),
    7: (0.212, 0.476, "Forward"),
    8: (0.212, 0.571, "Backward"),
}


class MousePreviewWidget(QWidget):
    button_clicked = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(260, 390)
        self.setMouseTracking(True)

        self._pixmap = QPixmap(ASSET_MOUSE_PATH) if os.path.exists(ASSET_MOUSE_PATH) else None
        self._selected_button = 1
        self._hovered_button = None
        self._glow_color = QColor("#00e5ff")
        self._show_badges = True

    def set_show_badges(self, show: bool):
        """Toggles between interactive button badges and clean RGB lighting visualizer."""
        self._show_badges = show
        self.update()

    def set_selected_button(self, btn_num: int):
        self._selected_button = btn_num
        self.update()

    def set_glow_color(self, r: int, g: int, b: int):
        self._glow_color = QColor(r, g, b)
        self.update()

    def _get_badge_center(self, btn_num: int, img_rect: QRectF) -> QPointF:
        rx, ry, _ = BUTTON_ANCHORS[btn_num]
        return QPointF(img_rect.left() + rx * img_rect.width(),
                       img_rect.top() + ry * img_rect.height())

    def mouseMoveEvent(self, event):
        if not self._show_badges:
            self.setCursor(Qt.ArrowCursor)
            return

        pos = event.position()
        img_rect = self._compute_image_rect()

        found = None
        for num in BUTTON_ANCHORS:
            c = self._get_badge_center(num, img_rect)
            dist = (pos.x() - c.x()) ** 2 + (pos.y() - c.y()) ** 2
            if dist <= 18 * 18:
                found = num
                break

        if found != self._hovered_button:
            self._hovered_button = found
            self.setCursor(Qt.PointingHandCursor if found else Qt.ArrowCursor)
            self.update()

    def mousePressEvent(self, event):
        if not self._show_badges:
            return

        if event.button() == Qt.LeftButton and self._hovered_button:
            self._selected_button = self._hovered_button
            self.button_clicked.emit(self._selected_button)
            self.update()

    def _compute_image_rect(self) -> QRectF:
        w = self.width()
        h = self.height()
        target_w = min(w * 0.90, 260)
        target_h = target_w * (420.0 / 260.0)
        if target_h > h * 0.92:
            target_h = h * 0.92
            target_w = target_h * (260.0 / 420.0)
        return QRectF((w - target_w) / 2, (h - target_h) / 2, target_w, target_h)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        w = self.width()
        h = self.height()
        img_rect = self._compute_image_rect()

        # Ambient glow behind mouse
        radial = QRadialGradient(w / 2, h / 2, img_rect.width() * 0.85)
        c_glow = QColor(self._glow_color)
        c_glow.setAlpha(45 if not self._show_badges else 35)
        radial.setColorAt(0.0, c_glow)
        radial.setColorAt(0.7, QColor(c_glow.red(), c_glow.green(), c_glow.blue(), 15))
        radial.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.fillRect(0, 0, w, h, QBrush(radial))

        # Draw Mouse Diagram
        if self._pixmap and not self._pixmap.isNull():
            painter.drawPixmap(img_rect.toRect(), self._pixmap)
        else:
            painter.setPen(QPen(QColor("#273142"), 2))
            painter.setBrush(QColor("#161b24"))
            painter.drawRoundedRect(img_rect, 20, 20)

        # In Backlight / lighting mode, skip numbered badges and show clean visualizer
        if not self._show_badges:
            return

        # Draw Numbered Glowing Badges 1 to 8 (Key config mode)
        badge_radius = 13.5
        for num in BUTTON_ANCHORS:
            c = self._get_badge_center(num, img_rect)
            is_sel = (num == self._selected_button)
            is_hov = (num == self._hovered_button)

            # Outer ring pulse if selected
            if is_sel:
                halo_pen = QPen(QColor(0, 229, 255, 120), 5)
                painter.setPen(halo_pen)
                painter.setBrush(Qt.NoBrush)
                painter.drawEllipse(c, badge_radius + 4, badge_radius + 4)

            # Badge Circle
            if is_sel:
                bg_color = QColor("#00e5ff")
                border_color = QColor("#ffffff")
                text_color = QColor("#050a12")
            elif is_hov:
                bg_color = QColor("#1c2738")
                border_color = QColor("#00e5ff")
                text_color = QColor("#00e5ff")
            else:
                bg_color = QColor("#0f1520")
                border_color = QColor("#00b4d8")
                text_color = QColor("#e0f4ff")

            painter.setPen(QPen(border_color, 1.8))
            painter.setBrush(QBrush(bg_color))
            painter.drawEllipse(c, badge_radius, badge_radius)

            # Number text
            font = QFont()
            font.setPointSize(9)
            font.setBold(True)
            painter.setFont(font)
            painter.setPen(text_color)
            painter.drawText(QRectF(c.x() - badge_radius, c.y() - badge_radius,
                                    badge_radius * 2, badge_radius * 2),
                             Qt.AlignCenter, str(num))
