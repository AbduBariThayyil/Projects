#!/usr/bin/env python3
"""
gba_start_menu_widget.py - Authentic GBA Start Menu Overlay
=============================================================
Replicates the in-game GBA Start Menu overlay triggered by pressing Space
or clicking [START] in the companion header:
- Modal overlay with semi-transparent backdrop showing the companion underneath.
- Top-Left Player Info Card (Flower-Bordered):
  * NAME: <player_name> (e.g. NIG)
  * TIME: <play_time> (e.g. 56:05)
  * MONEY: ₽<money> (e.g. ₽1114118)
- Right-Hand Menu Card (Flower-Bordered):
  * ▶ POKÉDEX
  *   DEXNAV
  *   POKÉMON
  *   OPTION
  *   MPLAYER
  *   MISC
- Full keyboard (Up, Down, Enter, Space, Escape) and mouse interaction.
- Authentic sound effects (menu_move.wav, menu_select.wav, menu_cancel.wav).
"""

import os
import subprocess
from typing import Dict, List, Optional, Any

from PySide6.QtWidgets import (
    QWidget, QFrame, QSizePolicy
)
from PySide6.QtGui import (
    QPainter, QPixmap, QColor, QFont, QPen, QBrush, QImage,
    QCursor, QKeyEvent, QMouseEvent
)
from PySide6.QtCore import (
    Qt, QRectF, QPointF, QSize, Signal
)

import quetzal_save_reader

PROJECT_DIR = "/home/vibecoder/Projects"
DEFAULT_SAV_PATH = "/home/vibecoder/Games/Console Games/GBA/Moemon Quetzal.sav"
SFX_DIR = os.path.join(PROJECT_DIR, "assets", "sfx")
FLOWER_FRAME_PATH = os.path.join(PROJECT_DIR, "assets", "flower_frame_9slice.png")


def play_sfx(name: str):
    """Play sound effect non-blockingly."""
    wav = os.path.join(SFX_DIR, name)
    if os.path.exists(wav):
        cmd = ["paplay", wav] if subprocess.run(["which", "paplay"], capture_output=True).returncode == 0 else ["aplay", "-q", wav]
        try:
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass


class GbaStartMenuOverlay(QWidget):
    """
    Authentic GBA Start Menu overlay with flower borders and player info.
    """
    # Emits selected menu action: "POKÉDEX", "DEXNAV", "POKÉMON", "OPTION", "MPLAYER", "MISC"
    action_triggered = Signal(str)
    closed = Signal()

    def __init__(self, save_path: str = DEFAULT_SAV_PATH, parent=None):
        super().__init__(parent)
        self.save_path = save_path
        self.setFocusPolicy(Qt.StrongFocus)

        # Flower border 9-slice pixmap
        self.flower_pm: Optional[QPixmap] = None
        if os.path.exists(FLOWER_FRAME_PATH):
            self.flower_pm = QPixmap(FLOWER_FRAME_PATH)

        # Player Info (read from .sav)
        self.player_name = "NIG"
        self.play_time = "56:05"
        self.money = 1114118

        # Menu Items matching reference ground truth (uploaded_media_0)
        self.menu_items = [
            {"id": "POKÉDEX", "label": "POKÉDEX", "hint": "View Regional & National Pokédex"},
            {"id": "DEXNAV", "label": "DEXNAV", "hint": "Wild Route Encounters & Habitat"},
            {"id": "POKÉMON", "label": "POKÉMON", "hint": "Trainer Card & Team Preview"},
            {"id": "OPTION", "label": "OPTION", "hint": "Toggle Retro GBA / Cyber Theme"},
            {"id": "MPLAYER", "label": "MPLAYER", "hint": "Retro 8-Bit Audio Fanfare"},
            {"id": "MISC", "label": "MISC", "hint": "Town Map & Catch Calculator"}
        ]
        self.selected_index = 0

        self.update_player_info()
        self.hide()  # Starts hidden until triggered

    def update_player_info(self):
        """Read latest player statistics from the GBA save file."""
        if os.path.exists(self.save_path):
            try:
                parser = quetzal_save_reader.QuetzalSaveParser(self.save_path)
                pinfo = parser.get_player_info()
                self.player_name = pinfo.get("name", "NIG")
                self.play_time = pinfo.get("short_time_str", "56:05")
                self.money = pinfo.get("money", 1114118)
            except Exception as e:
                print(f"[GbaStartMenuOverlay] Save reader error: {e}")

    def show_menu(self):
        """Display the Start Menu overlay with audio and keyboard grab."""
        self.update_player_info()
        self.show()
        self.raise_()
        self.setFocus()
        play_sfx("menu_select.wav")
        self.update()

    def hide_menu(self):
        """Close the Start Menu overlay."""
        play_sfx("menu_cancel.wav")
        self.hide()
        self.closed.emit()

    def toggle_menu(self):
        """Toggle open/closed state."""
        if self.isVisible():
            self.hide_menu()
        else:
            self.show_menu()

    # -------------------------------------------------------------
    # DRAWING & AUTHENTIC FLOWER FRAME RENDERING
    # -------------------------------------------------------------
    def draw_flower_card(self, painter: QPainter, rect: QRectF, tile_size: float = 24.0):
        """Draw an authentic GBA flower frame 9-slice card."""
        x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()

        if self.flower_pm and not self.flower_pm.isNull():
            s = self.flower_pm.width() / 3.0

            # 1. White interior
            painter.setBrush(QColor("#ffffff"))
            painter.setPen(Qt.NoPen)
            painter.drawRect(QRectF(x + tile_size - 2, y + tile_size - 2, w - 2*tile_size + 4, h - 2*tile_size + 4))

            # 2. Four Corner Flower Blossoms
            painter.drawPixmap(QRectF(x, y, tile_size, tile_size), self.flower_pm, QRectF(0, 0, s, s))
            painter.drawPixmap(QRectF(x + w - tile_size, y, tile_size, tile_size), self.flower_pm, QRectF(s*2, 0, s, s))
            painter.drawPixmap(QRectF(x, y + h - tile_size, tile_size, tile_size), self.flower_pm, QRectF(0, s*2, s, s))
            painter.drawPixmap(QRectF(x + w - tile_size, y + h - tile_size, tile_size, tile_size), self.flower_pm, QRectF(s*2, s*2, s, s))

            # 3. Top & Bottom Edges
            painter.drawPixmap(QRectF(x + tile_size, y, w - 2*tile_size, tile_size), self.flower_pm, QRectF(s, 0, s, s))
            painter.drawPixmap(QRectF(x + tile_size, y + h - tile_size, w - 2*tile_size, tile_size), self.flower_pm, QRectF(s, s*2, s, s))

            # 4. Left & Right Edges
            painter.drawPixmap(QRectF(x, y + tile_size, tile_size, h - 2*tile_size), self.flower_pm, QRectF(0, s, s, s))
            painter.drawPixmap(QRectF(x + w - tile_size, y + tile_size, tile_size, h - 2*tile_size), self.flower_pm, QRectF(s*2, s, s, s))

        else:
            # Fallback classic rounded frame
            painter.setBrush(QColor("#ffffff"))
            painter.setPen(QPen(QColor("#293131"), 3.0))
            painter.drawRoundedRect(rect, 6.0, 6.0)

    def paintEvent(self, event):
        """Paint the authentic GBA Start Menu cards and overworld overlay."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        # Semi-transparent dark emerald backdrop (lets companion UI shine through)
        painter.fillRect(self.rect(), QColor(10, 25, 30, 185))

        # Card Coordinates (Responsive to window dimensions)
        w = self.width()
        h = self.height()

        # 1. Top-Left Player Info Card
        card_w = min(340.0, w * 0.35)
        card_h = 210.0
        card_x = 32.0
        card_y = 28.0
        self.player_card_rect = QRectF(card_x, card_y, card_w, card_h)
        self.draw_flower_card(painter, self.player_card_rect, tile_size=24.0)

        # Draw Player Info Text
        font_pixel = QFont("JetBrainsMono Nerd Font", 14, QFont.Bold)
        painter.setFont(font_pixel)
        painter.setPen(QColor("#293131"))

        inner_x = card_x + 36.0
        inner_y = card_y + 36.0
        line_h = 46.0

        # NAME: NIG
        painter.drawText(QRectF(inner_x, inner_y, card_w - 50, line_h), Qt.AlignLeft | Qt.AlignVCenter, f"NAME: {self.player_name}")
        # TIME: 56:05
        painter.drawText(QRectF(inner_x, inner_y + line_h, card_w - 50, line_h), Qt.AlignLeft | Qt.AlignVCenter, f"TIME: {self.play_time}")
        # MONEY: ₽1114118
        painter.drawText(QRectF(inner_x, inner_y + line_h * 2, card_w - 50, line_h), Qt.AlignLeft | Qt.AlignVCenter, f"MONEY: ₽{self.money}")

        # 2. Right-Hand Menu Card
        menu_w = min(280.0, w * 0.30)
        menu_h = 440.0
        menu_x = w - menu_w - 32.0
        menu_y = 28.0
        self.menu_card_rect = QRectF(menu_x, menu_y, menu_w, menu_h)
        self.draw_flower_card(painter, self.menu_card_rect, tile_size=24.0)

        # Draw Menu Items & Cursor
        item_y_start = menu_y + 32.0
        item_h = 58.0

        font_menu = QFont("JetBrainsMono Nerd Font", 15, QFont.Bold)
        painter.setFont(font_menu)

        for i, item in enumerate(self.menu_items):
            cur_y = item_y_start + i * item_h
            is_sel = (i == self.selected_index)

            if is_sel:
                # Authentic red or dark selection arrow
                painter.setPen(QColor("#ef3131"))
                painter.drawText(QRectF(menu_x + 24.0, cur_y, 30.0, item_h), Qt.AlignLeft | Qt.AlignVCenter, "▶")
                painter.setPen(QColor("#0f172a"))
            else:
                painter.setPen(QColor("#475569"))

            painter.drawText(QRectF(menu_x + 58.0, cur_y, menu_w - 70.0, item_h), Qt.AlignLeft | Qt.AlignVCenter, item["label"])

        # 3. Bottom Controls Hint Pill
        hint_text = "⌨ [↑/↓] Navigate  •  [ENTER/SPACE] Select  •  [ESC] Close Menu"
        font_hint = QFont("JetBrainsMono Nerd Font", 10, QFont.Bold)
        painter.setFont(font_hint)
        painter.setPen(QColor("#e2e8f0"))
        painter.drawText(QRectF(0, h - 36, w, 24), Qt.AlignCenter, hint_text)

    # -------------------------------------------------------------
    # KEYBOARD & MOUSE CONTROLS
    # -------------------------------------------------------------
    def keyPressEvent(self, event: QKeyEvent):
        """Authentic GBA keypad navigation."""
        key = event.key()

        if key in (Qt.Key_Up, Qt.Key_K):
            play_sfx("menu_move.wav")
            self.selected_index = (self.selected_index - 1) % len(self.menu_items)
            self.update()
            event.accept()

        elif key in (Qt.Key_Down, Qt.Key_J):
            play_sfx("menu_move.wav")
            self.selected_index = (self.selected_index + 1) % len(self.menu_items)
            self.update()
            event.accept()

        elif key in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            self.activate_selected()
            event.accept()

        elif key in (Qt.Key_Escape, Qt.Key_Backspace):
            self.hide_menu()
            event.accept()

        else:
            super().keyPressEvent(event)

    def mousePressEvent(self, event: QMouseEvent):
        """Click handling: select item or close when clicking outside."""
        pos = event.position()

        if hasattr(self, "menu_card_rect") and self.menu_card_rect.contains(pos):
            # Check which menu item was clicked
            item_y_start = self.menu_card_rect.y() + 32.0
            item_h = 58.0
            clicked_idx = int((pos.y() - item_y_start) // item_h)
            if 0 <= clicked_idx < len(self.menu_items):
                self.selected_index = clicked_idx
                self.activate_selected()
                return

        # Clicked outside both cards: close menu
        if hasattr(self, "player_card_rect") and not self.player_card_rect.contains(pos):
            self.hide_menu()

    def activate_selected(self):
        """Execute selected menu option."""
        selected_item = self.menu_items[self.selected_index]
        action_id = selected_item["id"]
        play_sfx("menu_select.wav")
        self.hide()
        self.action_triggered.emit(action_id)


# ---------------------------------------------------------------------
# STANDALONE VERIFICATION LAUNCHER
# ---------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication, QMainWindow

    app = QApplication.instance() or QApplication(sys.argv)
    parent_win = QMainWindow()
    parent_win.setWindowTitle("GBA Start Menu Test")
    parent_win.resize(1024, 680)

    menu = GbaStartMenuOverlay(parent=parent_win)
    menu.resize(1024, 680)
    menu.show_menu()

    parent_win.show()
    sys.exit(app.exec())
