#!/usr/bin/env python3
"""
⚡ Pokémon Quetzal Master Companion & Strategy Hub
=================================================
A modern, uncluttered desktop companion for Pokémon Quetzal:
- Uncluttered Route Encounter Explorer across Hoenn, Johto, Kanto, and Sevii Islands
- Interactive Vector Town Map with route completion rings and 1-click navigation
- Pokédex with in-game style Area / Habitat Locator (find all routes where a mon spawns)
- Battle Frontier Brains (Silver & Gold), Gym Leader Rematches, and Champions Database
- Master Non-Editable Legendary Guide & Dual-Type Strategic Squad Builder
- Real-Time Live Save File Auto-Watcher (synchronizes automatically when saving in mGBA)
- Quick Ball & False Swipe Capture Probability Calculator
"""

import os
import sys
import math
import sqlite3
import time
import subprocess
from typing import Dict, List, Optional, Tuple

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QLineEdit, QListWidget, QListWidgetItem,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QScrollArea, QFrame, QSplitter, QTabWidget, QProgressBar, QGridLayout,
    QSizePolicy, QSpinBox, QCheckBox, QTextEdit, QPlainTextEdit
)
from PySide6.QtGui import (
    QFont, QColor, QPixmap, QIcon, QPainter, QBrush, QPen, QCursor
)
from PySide6.QtCore import Qt, QTimer, Signal, QEvent, QObject

import quetzal_save_reader
from regional_map_widget import RegionalMapWidget, normalize_loc, REGIONAL_MAP_DATA
from pokedex_retro_view import PokedexRetroView
from gba_start_menu_widget import GbaStartMenuOverlay

# ==========================================
# GBA CONSOLE ARCHITECTURE & FILTER
# ==========================================
class GbaApplicationEventFilter(QObject):
    """
    Application-level event filter ensuring GBA controls take precedence:
    - Space always toggles Start Menu (unless typing in text input).
    - Esc / X always closes Start Menu if open.
    - F11 toggles Fullscreen.
    - Prevents QPushButton focus stealing from triggering buttons on Space.
    """
    def __init__(self, main_win):
        super().__init__(main_win)
        self.main_win = main_win

    def eventFilter(self, watched, event):
        if event.type() == QEvent.KeyPress:
            focus_w = QApplication.focusWidget()
            in_text = isinstance(focus_w, (QLineEdit, QTextEdit, QPlainTextEdit))

            if event.key() == Qt.Key_F11:
                if self.main_win.isFullScreen():
                    self.main_win.showNormal()
                else:
                    self.main_win.showFullScreen()
                return True

            if event.key() == Qt.Key_Space:
                if not in_text:
                    self.main_win.toggle_start_menu()
                    return True  # Consume completely so NO QPushButton ever handles Space!

            if event.key() in (Qt.Key_Escape, Qt.Key_X):
                if hasattr(self.main_win, 'start_menu') and self.main_win.start_menu.isVisible():
                    self.main_win.start_menu.hide_menu()
                    return True
                elif in_text and event.key() == Qt.Key_Escape:
                    focus_w.clearFocus()
                    return True

        return super().eventFilter(watched, event)


class DexNavRetroBackgroundWidget(QWidget):
    """Authentic GBA DexNav background: sky blue #72b8df with cyan pinstripes #92cce8."""
    def paintEvent(self, event):
        painter = QPainter(self)
        w, h = self.width(), self.height()
        painter.fillRect(0, 0, w, h, QColor("#72b8df"))
        painter.setPen(QColor("#92cce8"))
        for y in range(0, h, 4):
            painter.drawLine(0, y, w, y)

# ==========================================
# CONSTANTS & ASSET PATHS
# ==========================================
PROJECT_DIR = "/home/vibecoder/Projects"
DB_PATH = os.path.join(PROJECT_DIR, "quetzal_database.db")
DEFAULT_SAV_PATH = "/home/vibecoder/Games/Console Games/GBA/Moemon Quetzal.sav"
ASSETS_SPRITES_DIR = os.path.join(PROJECT_DIR, "assets", "sprites")
ASSETS_SILHOUETTES_DIR = os.path.join(PROJECT_DIR, "assets", "silhouettes")
SFX_DIR = os.path.join(PROJECT_DIR, "assets", "sfx")

# Current Active Theme: "retro" (PokéNav GBA) or "modern" (Cyber Modern)
CURRENT_THEME = "retro"

def is_retro() -> bool:
    """Return True if active theme is authentic Emerald PokéNav GBA."""
    return CURRENT_THEME == "retro"

def play_sfx(sfx_name: str):
    """Play a retro chiptune sound effect asynchronously without blocking."""
    fname = sfx_name if sfx_name.endswith(".wav") else f"{sfx_name}.wav"
    path = os.path.join(SFX_DIR, fname)
    if os.path.exists(path):
        try:
            # paplay is native pulse/pipewire client with zero latency and no stderr clutter
            subprocess.Popen(["paplay", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            try:
                subprocess.Popen(["pw-play", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass

TYPE_COLORS = {
    "Normal":   ("#A8A878", "#6D6D4E"),
    "Fire":     ("#F08030", "#9C531F"),
    "Water":    ("#6890F0", "#445E9C"),
    "Grass":    ("#78C850", "#4E8234"),
    "Electric": ("#F8D030", "#A1871F"),
    "Ice":      ("#98D8D8", "#638D8D"),
    "Fighting": ("#C03028", "#7D1F1A"),
    "Poison":   ("#A040A0", "#682A68"),
    "Ground":   ("#E0C068", "#927D44"),
    "Flying":   ("#A890F0", "#6D5E9C"),
    "Psychic":  ("#F85888", "#A13959"),
    "Bug":      ("#A8B820", "#6D7915"),
    "Rock":     ("#B8A038", "#786824"),
    "Ghost":    ("#705898", "#493963"),
    "Dragon":   ("#7038F8", "#4924A1"),
    "Dark":     ("#705848", "#49392F"),
    "Steel":    ("#B8B8D0", "#787887"),
    "Fairy":    ("#EE99AC", "#9B6470"),
    "Stellar":  ("#42C8D4", "#2B828A"),
    "Mystery":  ("#68A090", "#44685E"),
}

# ==========================================
# RETRO POKéNAV GBA THEME (AUTHENTIC EMERALD)
# ==========================================
RETRO_POKENAV_STYLESHEET = """
QMainWindow {
    background-color: #0a1820;
}
QWidget {
    background-color: #0a1820;
    color: #e2f4ea;
    font-family: "JetBrainsMono Nerd Font", "UbuntuMono Nerd Font", "Courier New", monospace;
    font-size: 12px;
}
QTabWidget::pane {
    border-top: 3px solid #58b8a8;
    border-left: 3px solid #58b8a8;
    border-bottom: 3px solid #081820;
    border-right: 3px solid #081820;
    background-color: #10262e;
    border-radius: 4px;
    top: -2px;
}
QTabBar::tab {
    background: #0d1e24;
    color: #6a9c90;
    border-top: 2px solid #3d7870;
    border-left: 2px solid #3d7870;
    border-right: 2px solid #081820;
    border-bottom: none;
    padding: 8px 14px;
    font-family: "JetBrainsMono Nerd Font", "UbuntuMono Nerd Font", "Courier New", monospace;
    font-weight: bold;
    font-size: 11px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    margin-right: 3px;
}
QTabBar::tab:selected {
    background: #10262e;
    color: #00ff66;
    border-top: 3px solid #00ff66;
    border-left: 3px solid #58b8a8;
    border-right: 3px solid #081820;
    border-bottom: 3px solid #10262e;
}
QTabBar::tab:hover:!selected {
    background: #143038;
    color: #a8d8c8;
    border-top: 2px solid #58b8a8;
}
QLineEdit, QComboBox, QSpinBox {
    background-color: #08151c;
    border-top: 2px solid #050e12;
    border-left: 2px solid #050e12;
    border-bottom: 2px solid #58b8a8;
    border-right: 2px solid #58b8a8;
    border-radius: 2px;
    padding: 5px 10px;
    color: #00ff88;
    font-family: "JetBrainsMono Nerd Font", "UbuntuMono Nerd Font", "Courier New", monospace;
    font-size: 12px;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {
    border-top: 2px solid #050e12;
    border-left: 2px solid #050e12;
    border-bottom: 2px solid #00ff66;
    border-right: 2px solid #00ff66;
    background-color: #0c202a;
    color: #ffffff;
}
QComboBox QAbstractItemView {
    background-color: #08151c;
    border: 2px solid #58b8a8;
    selection-background-color: #184452;
    selection-color: #00ff88;
    color: #f8f8f8;
    font-family: "JetBrainsMono Nerd Font", "UbuntuMono Nerd Font", monospace;
}
QPushButton {
    background-color: #183844;
    border-top: 2px solid #58b8a8;
    border-left: 2px solid #58b8a8;
    border-bottom: 2px solid #081820;
    border-right: 2px solid #081820;
    border-radius: 2px;
    color: #f8f8f8;
    font-family: "JetBrainsMono Nerd Font", "UbuntuMono Nerd Font", "Courier New", monospace;
    font-weight: bold;
    font-size: 11px;
    padding: 6px 14px;
}
QPushButton:hover {
    background-color: #245060;
    border-top: 2px solid #78d8c0;
    border-left: 2px solid #78d8c0;
    border-bottom: 2px solid #051015;
    border-right: 2px solid #051015;
    color: #00ff88;
}
QPushButton:pressed {
    background-color: #0d2027;
    border-top: 2px solid #081820;
    border-left: 2px solid #081820;
    border-bottom: 2px solid #58b8a8;
    border-right: 2px solid #58b8a8;
    color: #00e858;
    padding-top: 8px;
    padding-left: 16px;
    padding-bottom: 4px;
    padding-right: 12px;
}
QScrollArea {
    border: none;
    background: transparent;
}
QScrollBar:vertical {
    border: none;
    background: #081418;
    width: 10px;
    border-radius: 2px;
}
QScrollBar::handle:vertical {
    background: #204654;
    border: 1px solid #58b8a8;
    min-height: 20px;
    border-radius: 2px;
}
QScrollBar::handle:vertical:hover {
    background: #2d6275;
}
QTableWidget {
    background-color: #08151c;
    border-top: 2px solid #081820;
    border-left: 2px solid #081820;
    border-bottom: 2px solid #58b8a8;
    border-right: 2px solid #58b8a8;
    gridline-color: #14303c;
    border-radius: 4px;
    color: #f8f8f8;
    font-family: "JetBrainsMono Nerd Font", "UbuntuMono Nerd Font", monospace;
}
QHeaderView::section {
    background-color: #122c36;
    color: #a8d8c8;
    padding: 7px;
    border-top: 1px solid #58b8a8;
    border-left: 1px solid #58b8a8;
    border-bottom: 2px solid #081820;
    border-right: 2px solid #081820;
    font-weight: bold;
    font-family: "JetBrainsMono Nerd Font", "UbuntuMono Nerd Font", monospace;
}
QTableWidget::item:selected {
    background-color: #1a4e5e;
    color: #00ff88;
}
QListWidget {
    background-color: #08151c;
    border-top: 2px solid #081820;
    border-left: 2px solid #081820;
    border-bottom: 2px solid #58b8a8;
    border-right: 2px solid #58b8a8;
    border-radius: 4px;
    font-family: "JetBrainsMono Nerd Font", "UbuntuMono Nerd Font", monospace;
}
QListWidget::item {
    padding: 6px 8px;
    border-bottom: 1px solid #132c36;
    color: #f8f8f8;
}
QListWidget::item:selected {
    background-color: #1a4e5e;
    color: #00ff88;
    border-left: 3px solid #00e858;
}
QListWidget::item:hover:!selected {
    background-color: #102630;
    color: #78d8c0;
}
QProgressBar {
    background-color: #081418;
    border-top: 2px solid #040a0c;
    border-left: 2px solid #040a0c;
    border-bottom: 2px solid #204854;
    border-right: 2px solid #204854;
    border-radius: 2px;
    text-align: center;
    color: #f8f8f8;
    font-family: "JetBrainsMono Nerd Font", "UbuntuMono Nerd Font", monospace;
    font-size: 9px;
    font-weight: bold;
}
QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #00ff68, stop:0.5 #00e858, stop:1 #009838);
    border-radius: 1px;
}
"""

MODERN_STYLESHEET = """
QMainWindow {
    background-color: #0b0f17;
}
QWidget {
    background-color: #0b0f17;
    color: #f1f5f9;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
}
QTabWidget::pane {
    border: 1px solid #1e293b;
    background-color: #0d131f;
    border-radius: 8px;
    top: -1px;
}
QTabBar::tab {
    background: #111827;
    color: #94a3b8;
    border: 1px solid #1e293b;
    border-bottom: none;
    padding: 10px 18px;
    font-weight: bold;
    font-size: 13px;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    margin-right: 4px;
}
QTabBar::tab:selected {
    background: #1e293b;
    color: #38bdf8;
    border-color: #38bdf8 #1e293b #1e293b #1e293b;
}
QTabBar::tab:hover:!selected {
    background: #162032;
    color: #cbd5e1;
}
QLineEdit, QComboBox, QSpinBox {
    background-color: #141c2b;
    border: 1px solid #27354a;
    border-radius: 6px;
    padding: 6px 12px;
    color: #f8fafc;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {
    border: 1px solid #38bdf8;
    background-color: #172235;
}
QComboBox QAbstractItemView {
    background-color: #141c2b;
    border: 1px solid #27354a;
    selection-background-color: #2563eb;
    color: #f8fafc;
}
QPushButton {
    background-color: #1a2436;
    border: 1px solid #2a3b57;
    border-radius: 6px;
    color: #f1f5f9;
    padding: 6px 14px;
    font-weight: 600;
}
QPushButton:hover {
    background-color: #253550;
    border-color: #38bdf8;
}
QPushButton:pressed {
    background-color: #1e293b;
}
QScrollArea {
    border: none;
    background: transparent;
}
QScrollBar:vertical {
    border: none;
    background: #0f172a;
    width: 8px;
    border-radius: 4px;
}
QScrollBar::handle:vertical {
    background: #334155;
    min-height: 20px;
    border-radius: 4px;
}
QScrollBar::handle:vertical:hover {
    background: #475569;
}
QTableWidget {
    background-color: #0f172a;
    border: 1px solid #1e293b;
    border-radius: 6px;
    gridline-color: #1e293b;
}
QHeaderView::section {
    background-color: #1e293b;
    color: #94a3b8;
    padding: 8px;
    border: 1px solid #0f172a;
    font-weight: bold;
}
QTableWidget::item:selected {
    background-color: #1e3a8a;
    color: #FFFFFF;
}
QListWidget {
    background-color: #0f172a;
    border: 1px solid #1e293b;
    border-radius: 6px;
}
QListWidget::item {
    padding: 6px 10px;
    border-radius: 4px;
    margin: 2px 4px;
}
QListWidget::item:selected {
    background-color: #2563eb;
    color: #FFFFFF;
}
QListWidget::item:hover:!selected {
    background-color: #1e293b;
}
"""

SILHOUETTE_CACHE: Dict[int, QPixmap] = {}

def get_species_pixmap(species_id: int, is_silhouette: bool = False) -> Optional[QPixmap]:
    """Load cached 2D sprite or silhouette pixmap with auto-generation fallback."""
    if is_silhouette and species_id in SILHOUETTE_CACHE:
        return SILHOUETTE_CACHE[species_id]

    target_dir = ASSETS_SILHOUETTES_DIR if is_silhouette else ASSETS_SPRITES_DIR
    path = os.path.join(target_dir, f"{species_id}.png")
    if os.path.exists(path):
        pm = QPixmap(path)
        if not pm.isNull():
            if is_silhouette:
                SILHOUETTE_CACHE[species_id] = pm
            return pm

    # Fallback: dynamically generate silhouette from normal sprite if missing
    if is_silhouette:
        sprite_path = os.path.join(ASSETS_SPRITES_DIR, f"{species_id}.png")
        if os.path.exists(sprite_path):
            base_pm = QPixmap(sprite_path)
            if not base_pm.isNull():
                img = base_pm.toImage()
                for y in range(img.height()):
                    for x in range(img.width()):
                        c = img.pixelColor(x, y)
                        if c.alpha() > 20:
                            img.setPixelColor(x, y, QColor(10, 20, 26, c.alpha()))
                sil_pm = QPixmap.fromImage(img)
                SILHOUETTE_CACHE[species_id] = sil_pm
                return sil_pm

    return None


class TypeBadge(QLabel):
    """Clean dual-type pill badge with retro GBA styling support."""
    def __init__(self, type_name: str, parent=None):
        super().__init__(parent)
        self.type_name = type_name
        self.setText(type_name.upper())
        self.setAlignment(Qt.AlignCenter)
        self.setFixedHeight(20)
        self.setContentsMargins(6, 2, 6, 2)
        font = QFont("JetBrainsMono Nerd Font" if is_retro() else "Arial", 9, QFont.Bold)
        self.setFont(font)

        bg, border = TYPE_COLORS.get(type_name, ("#475569", "#334155"))
        if is_retro():
            self.setStyleSheet(f"""
                QLabel {{
                    background-color: {bg};
                    border-top: 1.5px solid #ffffff;
                    border-left: 1.5px solid #ffffff;
                    border-bottom: 1.5px solid #000000;
                    border-right: 1.5px solid #000000;
                    border-radius: 2px;
                    color: #FFFFFF;
                    padding: 1px 5px;
                    font-size: 9px;
                    font-weight: bold;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                QLabel {{
                    background-color: {bg};
                    border: 1px solid {border};
                    border-radius: 4px;
                    color: #FFFFFF;
                    padding: 1px 6px;
                    font-size: 10px;
                    font-weight: bold;
                }}
            """)


def get_form_badge(species_id: int, national_dex_num: int, base_species_id: int, type1: str = "", type2: str = "") -> str:
    """
    Returns a clean, authentic Pokémon form badge name.
    If it is the base species (or sole form), returns 'Standard'.
    """
    if species_id == base_species_id:
        return "Standard"

    # Megas and Primals
    if 899 <= species_id <= 948:
        if species_id in (900, 912):
            return "Mega X"
        if species_id in (901, 913):
            return "Mega Y"
        if species_id == 939:
            return "Primal"
        if species_id == 940:
            return "Primal"
        return "Mega"

    # Alolan Forms (Gen 7)
    if 949 <= species_id <= 966:
        return "Alolan"

    # Galarian Forms (Gen 8)
    if 967 <= species_id <= 985:
        return "Galarian"

    # Cap / Cosplay Pikachu & Special
    if 986 <= species_id <= 999:
        return f"Cap {species_id - 985}"

    # Weather forms (Castform)
    if 1028 <= species_id <= 1030:
        return {1028: "Sunny", 1029: "Rainy", 1030: "Snowy"}.get(species_id, "Castform")

    # Deoxys forms
    if 1031 <= species_id <= 1033:
        return {1031: "Attack", 1032: "Defense", 1033: "Speed"}.get(species_id, "Form")

    # Rotom forms
    if 1041 <= species_id <= 1045:
        return {1041: "Heat", 1042: "Wash", 1043: "Frost", 1044: "Fan", 1045: "Mow"}.get(species_id, "Rotom")

    # Origin / Sky forms
    if species_id == 1046:
        return "Origin"
    if species_id == 1047:
        return "Sky"

    # Therian Formes
    if 1065 <= species_id <= 1067:
        return "Therian"

    # Kyurem Black / White
    if species_id == 1077:
        return "Black"
    if species_id == 1078:
        return "White"

    # Hisuian Forms (Gen 8 Legends: Arceus)
    if 1223 <= species_id <= 1239:
        return "Hisuian"

    # Paldean Forms (Gen 9)
    if 1363 <= species_id <= 1369:
        return "Paldean"

    # Gigantamax Forms
    if 1435 <= species_id <= 1468:
        return "G-Max"

    # Generic fallback based on typing
    t_clean = type1 if (type1 == type2 or not type2 or type2 == "None") else f"{type1}/{type2}"
    return f"[{t_clean}]"


class DexNavSlotWidget(QFrame):
    """
    Tactile 1:1 in-game DexNav slot widget.
    Represents an authentic habitat slot:
    - If mon_data is None: renders an authentic '✕' (empty slot mark).
    - If mon_data is present: renders Pokémon mini-sprite (or silhouette if uncaught),
      Dex #, mini Pokéball icon if caught, species name, and rate %.
    - Clicking selects the Pokémon and populates the right Telemetry Inspector.
    """
    slot_selected = Signal(dict)
    catch_toggled = Signal(int, str, bool)

    def __init__(self, habitat: str, slot_num: int, mon_data: Optional[dict] = None, parent=None):
        super().__init__(parent)
        self.habitat = habitat.upper()
        self.slot_num = slot_num
        self.mon_data = mon_data
        self.is_selected = False
        self.is_dimmed = False
        self.is_caught = bool(mon_data and mon_data.get("is_caught", False))
        self.species_id = mon_data["species_id"] if mon_data else 0
        self.dex_num = None
        self.form_badge = mon_data.get("form_badge") if mon_data else None
        self.form_badge_lbl = QLabel()

        self.init_ui()

    def init_ui(self):
        if is_retro():
            if self.habitat == "LAND":
                self.setFixedSize(58, 58)
            else:
                self.setFixedSize(64, 64)
        else:
            if self.habitat == "LAND":
                self.setFixedSize(88, 92)
            else:
                self.setFixedSize(94, 94)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(1)

        # Top Bar: Dex # / Slot # and mini Pokéball
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(0, 0, 0, 0)
        top_bar.setSpacing(2)

        self.id_lbl = QLabel()
        self.id_lbl.setFont(QFont("Monospace", 8, QFont.Bold))
        self.dex_num = self.id_lbl
        top_bar.addWidget(self.id_lbl)

        top_bar.addStretch()

        self.ball_lbl = QLabel()
        self.ball_lbl.setFont(QFont("SansSerif", 8))
        top_bar.addWidget(self.ball_lbl)

        layout.addLayout(top_bar)

        # Center: Sprite / Silhouette or X Mark
        self.center_box = QLabel()
        self.center_box.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.center_box, 1)

        # Bottom Bar: Name and Rate %
        self.name_lbl = QLabel()
        self.name_lbl.setAlignment(Qt.AlignCenter)
        self.name_lbl.setFont(QFont("SansSerif", 8, QFont.Bold))
        layout.addWidget(self.name_lbl)

        self.rate_lbl = QLabel()
        self.rate_lbl.setAlignment(Qt.AlignCenter)
        self.rate_lbl.setFont(QFont("Monospace", 7))
        layout.addWidget(self.rate_lbl)

        self.update_content()
        self.update_style()

    def set_mon_data(self, mon_data: Optional[dict]):
        self.mon_data = mon_data
        self.is_caught = bool(mon_data and mon_data.get("is_caught", False))
        self.update_content()
        self.update_style()

    def set_selected(self, selected: bool):
        self.is_selected = selected
        self.update_style()

    def set_dimmed(self, dimmed: bool):
        self.is_dimmed = dimmed
        self.update_style()

    def update_content(self):
        if not self.mon_data:
            # Empty slot -> authentic X mark
            self.species_id = 0
            self.form_badge = None
            self.form_badge_lbl.setText("")
            self.setCursor(QCursor(Qt.ArrowCursor))
            self.id_lbl.setText("")
            if hasattr(self, "dex_num") and self.dex_num:
                self.dex_num.setText("")
            self.ball_lbl.setText("")
            self.center_box.clear()
            self.center_box.setText("✕")
            self.center_box.setFont(QFont("Monospace", 20, QFont.Bold))
            self.center_box.setStyleSheet("color: #ff3858;" if is_retro() else "color: #ef4444;")
            self.name_lbl.setText("—")
            self.rate_lbl.setText("")
            self.setToolTip(f"{self.habitat} Slot {self.slot_num}: No Pokémon")
            return

        self.setCursor(QCursor(Qt.PointingHandCursor))
        pid = self.mon_data["species_id"]
        nat_dex = self.mon_data.get("national_dex_num", pid)
        name = self.mon_data["species_name"]
        chance = self.mon_data.get("chance", 0)
        min_l = self.mon_data.get("min_level", 0)
        max_l = self.mon_data.get("max_level", 0)

        self.species_id = pid
        self.id_lbl.setText(f"#{nat_dex:04d}")
        self.dex_num = self.id_lbl
        self.form_badge = self.mon_data.get("form_badge")
        if self.form_badge and self.form_badge != "Standard":
            disp_b = f"{self.form_badge} Form" if self.form_badge in ("Alolan", "Galarian", "Hisuian", "Paldean") else self.form_badge
            self.form_badge_lbl.setText(disp_b)
        else:
            self.form_badge_lbl.setText("")

        self.ball_lbl.setText("🔴" if self.is_caught else "")

        # Sprite / Silhouette: show silhouette if uncaught (authentic DexNav behavior)
        pm = get_species_pixmap(pid, is_silhouette=(not self.is_caught))
        if pm:
            scale_sz = 48 if is_retro() else (42 if self.habitat == "LAND" else 46)
            self.center_box.setPixmap(pm.scaled(scale_sz, scale_sz, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            self.center_box.setText("🐾")

        # Name label
        disp_name = name
        if len(disp_name) > 8:
            disp_name = disp_name[:7] + "…"
        self.name_lbl.setText(disp_name)

        # Rate / Level label
        lvl_str = f"Lv.{min_l}" if min_l == max_l else f"Lv.{min_l}-{max_l}"
        if chance > 0:
            self.rate_lbl.setText(f"{chance}% • {lvl_str}")
        else:
            self.rate_lbl.setText(lvl_str)

        status_str = "Caught ✓" if self.is_caught else "Missing ○"
        self.setToolTip(f"#{nat_dex:04d} {name}\nHabitat: {self.habitat} (Slot {self.slot_num})\nLevel: {lvl_str}\nEncounter Rate: {chance}%\nStatus: {status_str}")

    def update_style(self):
        retro = is_retro()
        if retro:
            self.id_lbl.hide()
            self.ball_lbl.hide()
            self.name_lbl.hide()
            self.rate_lbl.hide()
            self.form_badge_lbl.hide()
            if self.habitat == "LAND":
                self.setFixedSize(58, 58)
            else:
                self.setFixedSize(64, 64)
        else:
            self.id_lbl.show()
            self.ball_lbl.show()
            self.name_lbl.show()
            self.rate_lbl.show()
            if self.habitat == "LAND":
                self.setFixedSize(88, 92)
            else:
                self.setFixedSize(94, 94)

        if not self.mon_data:
            # Empty X slot styling
            if retro:
                self.setStyleSheet("""
                    QFrame {
                        background-color: #f8fafc;
                        border: 1px dashed #cbd5e1;
                        border-radius: 4px;
                    }
                """)
                self.center_box.setStyleSheet("color: #cbd5e1; font-weight: bold; font-size: 16px;")
            else:
                self.setStyleSheet("""
                    QFrame {
                        background-color: #0b111e;
                        border: 1px dashed #1e293b;
                        border-radius: 6px;
                    }
                """)
                self.center_box.setStyleSheet("color: #ef4444; font-weight: bold; font-size: 16px;")
            self.name_lbl.setStyleSheet("color: #475569; font-size: 8px;")
            return

        opacity_css = "opacity: 0.25;" if self.is_dimmed else ""

        if retro:
            if self.is_selected:
                self.setStyleSheet(f"""
                    QFrame {{
                        background-color: #e0f2fe;
                        border: 3px solid #0284c7;
                        border-radius: 4px;
                        {opacity_css}
                    }}
                """)
            else:
                self.setStyleSheet(f"""
                    QFrame {{
                        background-color: #ffffff;
                        border: 1px solid #f1f5f9;
                        border-radius: 4px;
                        {opacity_css}
                    }}
                """)
        else:
            if self.is_selected:
                border_style = "border: 2px solid #38bdf8; background-color: #1e293b;"
            elif self.is_caught:
                border_style = "border: 1px solid #059669; background-color: #064e3b;"
            else:
                border_style = "border: 1px solid #334155; background-color: #0f172a;"
            self.setStyleSheet(f"""
                QFrame {{
                    {border_style}
                    border-radius: 6px;
                    {opacity_css}
                }}
            """)
            self.id_lbl.setStyleSheet("color: #94a3b8; font-size: 8px; font-weight: bold;")
            self.name_lbl.setStyleSheet("color: #f8fafc; font-size: 8px; font-weight: bold;")
            self.rate_lbl.setStyleSheet("color: #cbd5e1; font-size: 7px;")

    def update_card_style(self, is_selected=None):
        if is_selected is not None:
            self.is_selected = is_selected
        self.update_content()
        self.update_style()

    def update_caught_button_state(self):
        pass

    def mousePressEvent(self, event):
        btn = None
        try:
            btn = event.button()
        except TypeError:
            try:
                btn = event.button
            except Exception:
                pass
        except Exception:
            pass
        if btn == Qt.LeftButton and self.mon_data:
            play_sfx("menu_move.wav")
            self.slot_selected.emit(self.mon_data)
        try:
            super().mousePressEvent(event)
        except Exception:
            pass


class DexNavHabitatBoxWidget(QFrame):
    """
    Habitat Box widget matching the authentic ORAS / Quetzal DexNav screen layout.
    - Title banner with Habitat Name (WATER, LAND, BEACH, HIDDEN), icon, and completion Pokéball.
    - Grid of exact fixed slots (WATER: 5, LAND: 12, BEACH: 3, HIDDEN: 1).
    - If a habitat has 0 Pokémon on that route, all slots render authentic '✕' marks.
    - When all available Pokémon in the habitat are caught, the header Pokéball turns GOLD!
    """
    slot_clicked = Signal(dict)
    catch_toggled = Signal(int, str, bool)

    def __init__(self, habitat: str, icon: str, header_color: str, total_slots: int, columns: int, parent=None):
        super().__init__(parent)
        self.habitat = habitat.upper()
        self.icon = icon
        self.header_color = header_color
        self.total_slots = total_slots
        self.columns = columns
        self.slots: List[DexNavSlotWidget] = []

        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(6, 6, 6, 8)
        main_layout.setSpacing(6)

        # Header Banner
        self.header_frame = QFrame()
        self.header_frame.setFixedHeight(30)
        h_layout = QHBoxLayout(self.header_frame)
        h_layout.setContentsMargins(10, 2, 10, 2)
        h_layout.setSpacing(6)

        # Left: Habitat Icon & Title
        self.title_lbl = QLabel(f"{self.icon} {self.habitat}")
        self.title_lbl.setFont(QFont("SansSerif", 10, QFont.Bold))
        h_layout.addWidget(self.title_lbl)

        # Counter / badge: e.g. "5 / 5 CAUGHT"
        self.count_lbl = QLabel("")
        self.count_lbl.setFont(QFont("Monospace", 8, QFont.Bold))
        h_layout.addWidget(self.count_lbl)

        h_layout.addStretch()

        # Right: Authentic Pokéball Completion Badge
        self.ball_icon = QLabel("⚪")
        self.ball_icon.setFont(QFont("SansSerif", 11))
        h_layout.addWidget(self.ball_icon)

        main_layout.addWidget(self.header_frame)

        # Slots Grid
        self.grid_frame = QFrame()
        self.grid_layout = QGridLayout(self.grid_frame)
        self.grid_layout.setContentsMargins(4, 4, 4, 4)
        self.grid_layout.setSpacing(6)

        # Pre-instantiate the fixed slots
        for idx in range(1, self.total_slots + 1):
            slot_w = DexNavSlotWidget(self.habitat, idx)
            slot_w.slot_selected.connect(self.on_slot_selected)
            slot_w.catch_toggled.connect(self.catch_toggled.emit)
            r = (idx - 1) // self.columns
            c = (idx - 1) % self.columns
            self.grid_layout.addWidget(slot_w, r, c)
            self.slots.append(slot_w)

        main_layout.addWidget(self.grid_frame)
        self.apply_theme(CURRENT_THEME)

    def on_slot_selected(self, mon_data: dict):
        self.slot_clicked.emit(mon_data)

    def populate(self, mons: List[dict]):
        """
        Populate the slots with encounter records.
        If mons has fewer items than total_slots, remaining slots render as '✕' (None).
        """
        total_avail = len(mons)
        caught_count = sum(1 for m in mons if m.get("is_caught", False))

        for idx, slot_w in enumerate(self.slots):
            if idx < total_avail:
                slot_w.set_mon_data(mons[idx])
            else:
                slot_w.set_mon_data(None)

        # Update Header Counter and Pokéball Badge
        if total_avail == 0:
            self.count_lbl.setText("— EMPTY")
            self.ball_icon.setText("—")
            self.ball_icon.setToolTip(f"No {self.habitat} encounters on this route")
        elif caught_count >= total_avail:
            self.count_lbl.setText(f"✓ {caught_count}/{total_avail} CAUGHT (100%)")
            self.ball_icon.setText("🟡")  # Gold Pokéball / crown!
            self.ball_icon.setToolTip(f"100% Complete! All {self.habitat} Pokémon caught!")
        else:
            self.count_lbl.setText(f"○ {caught_count}/{total_avail} CAUGHT")
            self.ball_icon.setText("⚪")  # Unfinished Pokéball
            self.ball_icon.setToolTip(f"{caught_count} of {total_avail} caught")

    def deselect_all(self):
        for s in self.slots:
            s.set_selected(False)

    def select_species(self, species_id: int):
        found = False
        for s in self.slots:
            if s.mon_data and s.mon_data["species_id"] == species_id:
                s.set_selected(True)
                found = True
            else:
                s.set_selected(False)
        return found

    def apply_filters(self, filter_mode: str, query: str):
        q = query.strip().lower()
        clean_q = q.lstrip("#").strip()
        for s in self.slots:
            if not s.mon_data:
                s.set_dimmed(False)
                continue
            d = s.mon_data
            # Caught filter
            dim = False
            if filter_mode == "Missing Only" and d.get("is_caught", False):
                dim = True
            elif filter_mode == "Caught Only" and not d.get("is_caught", False):
                dim = True

            # Query filter
            if q and not dim:
                matches_name = q in d["species_name"].lower()
                matches_id = q in str(d["species_id"])
                nat_dex = d.get("national_dex_num", d["species_id"])
                matches_nat = (clean_q.isdigit() and int(clean_q) == nat_dex) or (f"#{nat_dex:04d}" in q)
                matches_form = bool(d.get("form_badge") and q in d["form_badge"].lower())
                if not (matches_name or matches_id or matches_nat or matches_form):
                    dim = True

            s.set_dimmed(dim)

    def apply_theme(self, theme_mode: str):
        retro = (theme_mode == "retro")
        # Color palettes per habitat matching authentic DexNav
        colors = {
            "WATER": {"header_retro": "#0284c7", "border_retro": "#e0f2fe", "header_mod": "#1e3a8a", "border_mod": "#3b82f6"},
            "LAND": {"header_retro": "#22c55e", "border_retro": "#dcfce7", "header_mod": "#14532d", "border_mod": "#22c55e"},
            "BEACH": {"header_retro": "#d97706", "border_retro": "#fef3c7", "header_mod": "#78350f", "border_mod": "#f59e0b"},
            "HIDDEN": {"header_retro": "#ef4444", "border_retro": "#fee2e2", "header_mod": "#7f1d1d", "border_mod": "#ef4444"},
        }.get(self.habitat, {"header_retro": "#0f766e", "border_retro": "#ccfbf1", "header_mod": "#1e293b", "border_mod": "#64748b"})

        if retro:
            self.setStyleSheet("""
                DexNavHabitatBoxWidget {
                    background-color: transparent;
                    border: none;
                }
            """)
            self.header_frame.setStyleSheet(f"""
                background-color: {colors["header_retro"]};
                border-top: 2px solid rgba(255, 255, 255, 0.4);
                border-left: 2px solid rgba(255, 255, 255, 0.4);
                border-bottom: 2px solid rgba(0, 0, 0, 0.2);
                border-right: 2px solid rgba(0, 0, 0, 0.2);
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            """)
            self.grid_frame.setStyleSheet("""
                background-color: #ffffff;
                border-bottom-left-radius: 4px;
                border-bottom-right-radius: 4px;
                border: 2px solid #ffffff;
            """)
            self.title_lbl.setStyleSheet(f"color: #ffffff; font-weight: bold; font-family: monospace; font-size: 11px;")
            self.count_lbl.setStyleSheet(f"color: {colors['border_retro']}; font-weight: bold; font-family: monospace; font-size: 9px;")
        else:
            self.setStyleSheet("""
                DexNavHabitatBoxWidget {
                    background-color: #0f172a;
                    border: 1px solid #1e293b;
                    border-radius: 8px;
                }
            """)
            self.header_frame.setStyleSheet(f"""
                background-color: {colors["header_mod"]};
                border: 1px solid {colors["border_mod"]};
                border-radius: 6px;
            """)
            self.grid_frame.setStyleSheet("""
                background-color: transparent;
                border: none;
            """)
            self.title_lbl.setStyleSheet("color: #f8fafc; font-weight: bold; font-size: 11px;")
            self.count_lbl.setStyleSheet(f"color: {colors['border_mod']}; font-weight: bold; font-size: 9px;")

        for s in self.slots:
            s.update_style()


class ModernEncounterCard(QFrame):
    """
    Modern responsive encounter card with authentic Emerald GBA retro styling.
    Generous whitespace, large crisp sprite, dual types, level range, rate %,
    held item highlight (gold), and 1-click caught toggle.
    """
    clicked = Signal(dict)
    catch_toggled = Signal(int, str, bool)

    def __init__(self, mon_data: dict, parent=None):
        super().__init__(parent)
        self.mon_data = mon_data
        self.is_caught = mon_data.get("is_caught", False)
        self.species_id = mon_data["species_id"]
        self.species_name = mon_data["species_name"]
        self.national_dex_num = mon_data.get("national_dex_num", self.species_id)
        self.form_badge = mon_data.get("form_badge")
        if not self.form_badge:
            self.form_badge = get_form_badge(self.species_id, self.national_dex_num, self.national_dex_num, mon_data.get("type1", ""), mon_data.get("type2", ""))

        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.init_ui()

    def init_ui(self):
        self.setMinimumWidth(220)
        self.setFixedHeight(120)

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(10, 8, 10, 8)
        main_layout.setSpacing(10)

        # Left Column: Large Pokémon Sprite in beveled/rounded container
        self.sprite_box = QFrame()
        self.sprite_box.setFixedSize(68, 68)
        sb_layout = QVBoxLayout(self.sprite_box)
        sb_layout.setContentsMargins(0, 0, 0, 0)
        self.sprite_lbl = QLabel()
        self.sprite_lbl.setAlignment(Qt.AlignCenter)
        pm = get_species_pixmap(self.species_id, is_silhouette=False)
        if pm:
            self.sprite_lbl.setPixmap(pm.scaled(60, 60, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            self.sprite_lbl.setText("🐾")
        sb_layout.addWidget(self.sprite_lbl)
        main_layout.addWidget(self.sprite_box, alignment=Qt.AlignVCenter)

        # Center Column: Info & Details
        info_col = QVBoxLayout()
        info_col.setContentsMargins(0, 0, 0, 0)
        info_col.setSpacing(3)

        # Row 1: Dex # + Name + Form Badge
        title_box = QHBoxLayout()
        title_box.setSpacing(6)
        self.dex_num = QLabel(f"#{self.national_dex_num:04d}")
        title_box.addWidget(self.dex_num)

        self.name_lbl = QLabel(self.species_name)
        title_box.addWidget(self.name_lbl)

        if self.form_badge and self.form_badge != "Standard":
            display_badge = f"{self.form_badge} Form" if self.form_badge in ("Alolan", "Galarian", "Hisuian", "Paldean") else self.form_badge
            self.form_badge_lbl = QLabel(display_badge)
            if is_retro():
                self.form_badge_lbl.setStyleSheet("""
                    background-color: #10262e;
                    color: #58f8e8;
                    border: 1px solid #58b8a8;
                    border-radius: 2px;
                    padding: 0px 4px;
                    font-family: monospace;
                    font-size: 9px;
                    font-weight: bold;
                """)
            else:
                if "Alolan" in self.form_badge:
                    bg, fg, border = "#0c4a6e", "#bae6fd", "#0284c7"
                elif "Galarian" in self.form_badge:
                    bg, fg, border = "#4c1d95", "#ddd6fe", "#7c3aed"
                elif "Hisuian" in self.form_badge:
                    bg, fg, border = "#134e4a", "#99f6e4", "#0d9488"
                elif "Paldean" in self.form_badge:
                    bg, fg, border = "#7c2d12", "#ffedd5", "#ea580c"
                elif "Mega" in self.form_badge or "Primal" in self.form_badge:
                    bg, fg, border = "#78350f", "#fef3c7", "#d97706"
                elif "G-Max" in self.form_badge:
                    bg, fg, border = "#7f1d1d", "#fee2e2", "#dc2626"
                else:
                    bg, fg, border = "#1e293b", "#e2e8f0", "#475569"

                self.form_badge_lbl.setStyleSheet(f"""
                    background-color: {bg};
                    color: {fg};
                    border: 1px solid {border};
                    border-radius: 3px;
                    padding: 0px 4px;
                    font-size: 9px;
                    font-weight: bold;
                """)
            title_box.addWidget(self.form_badge_lbl)

        title_box.addStretch()
        info_col.addLayout(title_box)

        # Row 2: Dual Type Badges
        type_box = QHBoxLayout()
        type_box.setSpacing(4)
        t1 = self.mon_data.get("type1")
        t2 = self.mon_data.get("type2")
        if t1 and t1 != "None":
            type_box.addWidget(TypeBadge(t1))
        if t2 and t2 != "None" and t2 != t1:
            type_box.addWidget(TypeBadge(t2))
        type_box.addStretch()
        info_col.addLayout(type_box)

        # Row 3: Method & Encounter Rate
        meta_box = QHBoxLayout()
        meta_box.setSpacing(6)
        meth = self.mon_data.get("method", "Grass")
        chance = self.mon_data.get("chance", 0)
        min_l = self.mon_data.get("min_level", 1)
        max_l = self.mon_data.get("max_level", 1)

        # Method icons
        if "Grass" in meth:
            meth_icon = "🌿"
        elif "Surfing" in meth:
            meth_icon = "🌊"
        elif "Fishing" in meth:
            meth_icon = "🎣"
        elif "Rock" in meth:
            meth_icon = "🪨"
        elif "Hidden" in meth:
            meth_icon = "🔍"
        else:
            meth_icon = "📍"

        self.rate_lbl = QLabel(f"{meth_icon} {meth} ({chance}%) • Lv.{min_l}–{max_l}")
        meta_box.addWidget(self.rate_lbl)
        meta_box.addStretch()
        info_col.addLayout(meta_box)

        # Row 4: Held Item / Special Badges (Gold highlight for Nugget/Leftovers/etc.)
        held = self.mon_data.get("held_items")
        if held and held != "None":
            item_box = QHBoxLayout()
            item_box.setSpacing(4)
            valuable = any(x in held for x in ["Nugget", "Leftovers", "Pearl", "Star", "Master Ball"])
            bg_col = "#3b2a05" if valuable else "#1e293b"
            fg_col = "#facc15" if valuable else "#cbd5e1"
            border_col = "#eab308" if valuable else "#334155"
            item_tag = QLabel(f"🎁 {held}")
            item_tag.setStyleSheet(f"""
                background-color: {bg_col};
                color: {fg_col};
                border: 1px solid {border_col};
                border-radius: 3px;
                padding: 1px 5px;
                font-size: 10px;
                font-weight: bold;
            """)
            item_box.addWidget(item_tag)
            item_box.addStretch()
            info_col.addLayout(item_box)

        main_layout.addLayout(info_col, 1)

        # Right Column: 1-Click Caught Toggle Button
        btn_col = QVBoxLayout()
        btn_col.setContentsMargins(0, 0, 0, 0)
        self.caught_btn = QPushButton()
        self.caught_btn.setFixedSize(92, 28)
        self.caught_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.update_caught_button_state()
        self.caught_btn.clicked.connect(self.on_caught_button_clicked)
        btn_col.addWidget(self.caught_btn, alignment=Qt.AlignVCenter)
        main_layout.addLayout(btn_col)

        self.update_card_style(is_selected=False)

    def update_card_style(self, is_selected: bool = False):
        if is_retro():
            if is_selected:
                self.setStyleSheet("""
                    ModernEncounterCard {
                        background-color: #173b44;
                        border-top: 2px solid #00ff88;
                        border-left: 2px solid #00ff88;
                        border-bottom: 2px solid #081820;
                        border-right: 2px solid #081820;
                        border-radius: 4px;
                    }
                """)
            elif self.is_caught:
                self.setStyleSheet("""
                    ModernEncounterCard {
                        background-color: #0d2820;
                        border-top: 2px solid #00e858;
                        border-left: 2px solid #00e858;
                        border-bottom: 2px solid #081820;
                        border-right: 2px solid #081820;
                        border-radius: 4px;
                    }
                    ModernEncounterCard:hover {
                        background-color: #14382e;
                        border-top: 2px solid #34d399;
                        border-left: 2px solid #34d399;
                    }
                """)
            else:
                self.setStyleSheet("""
                    ModernEncounterCard {
                        background-color: #10262e;
                        border-top: 2px solid #58b8a8;
                        border-left: 2px solid #58b8a8;
                        border-bottom: 2px solid #081820;
                        border-right: 2px solid #081820;
                        border-radius: 4px;
                    }
                    ModernEncounterCard:hover {
                        background-color: #15323c;
                        border-top: 2px solid #78d8c0;
                        border-left: 2px solid #78d8c0;
                    }
                """)
            if hasattr(self, 'sprite_box'):
                self.sprite_box.setStyleSheet("""
                    background-color: #081418;
                    border-top: 2px solid #040a0c;
                    border-left: 2px solid #040a0c;
                    border-bottom: 2px solid #285462;
                    border-right: 2px solid #285462;
                    border-radius: 3px;
                """)
            if hasattr(self, 'dex_num'):
                self.dex_num.setStyleSheet("color: #58b8a8; font-family: monospace; font-size: 11px; font-weight: bold;")
            if hasattr(self, 'name_lbl'):
                self.name_lbl.setStyleSheet("color: #f8f8f8; font-family: monospace; font-size: 13px; font-weight: bold;")
            if hasattr(self, 'rate_lbl'):
                self.rate_lbl.setStyleSheet("color: #a8d8c8; font-family: monospace; font-size: 10px;")
        else:
            if is_selected:
                border = "2px solid #38bdf8"
                bg = "#192538"
            elif self.is_caught:
                border = "1px solid #166534"
                bg = "#121d28"
            else:
                border = "1px solid #27354a"
                bg = "#141c2b"

            self.setStyleSheet(f"""
                ModernEncounterCard {{
                    background-color: {bg};
                    border: {border};
                    border-radius: 8px;
                }}
                ModernEncounterCard:hover {{
                    border: 1px solid #38bdf8;
                    background-color: #172437;
                }}
            """)
            if hasattr(self, 'sprite_box'):
                self.sprite_box.setStyleSheet("""
                    background-color: #0b111a;
                    border: 1px solid #1e2b3e;
                    border-radius: 8px;
                """)
            if hasattr(self, 'dex_num'):
                self.dex_num.setStyleSheet("color: #64748b; font-size: 11px; font-weight: bold;")
            if hasattr(self, 'name_lbl'):
                self.name_lbl.setStyleSheet("color: #f8fafc; font-size: 14px; font-weight: bold;")
            if hasattr(self, 'rate_lbl'):
                self.rate_lbl.setStyleSheet("color: #94a3b8; font-size: 11px;")

    def update_caught_button_state(self):
        if is_retro():
            if self.is_caught:
                self.caught_btn.setText("✓ CAUGHT")
                self.caught_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #0a301c;
                        border-top: 2px solid #00e858;
                        border-left: 2px solid #00e858;
                        border-bottom: 2px solid #04140c;
                        border-right: 2px solid #04140c;
                        color: #00ff88;
                        font-family: 'JetBrainsMono Nerd Font', 'UbuntuMono Nerd Font', monospace;
                        font-size: 10px;
                        font-weight: bold;
                        border-radius: 2px;
                        padding: 2px 4px;
                    }
                    QPushButton:hover {
                        background-color: #104228;
                        color: #ffffff;
                    }
                    QPushButton:pressed {
                        border-top: 2px solid #04140c;
                        border-left: 2px solid #04140c;
                        border-bottom: 2px solid #00e858;
                        border-right: 2px solid #00e858;
                        padding-top: 4px; padding-left: 6px;
                    }
                """)
            else:
                self.caught_btn.setText("○ MISSING")
                self.caught_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #321c04;
                        border-top: 2px solid #f8b800;
                        border-left: 2px solid #f8b800;
                        border-bottom: 2px solid #140c02;
                        border-right: 2px solid #140c02;
                        color: #f8b800;
                        font-family: 'JetBrainsMono Nerd Font', 'UbuntuMono Nerd Font', monospace;
                        font-size: 10px;
                        font-weight: bold;
                        border-radius: 2px;
                        padding: 2px 4px;
                    }
                    QPushButton:hover {
                        background-color: #482a08;
                        color: #ffffff;
                    }
                    QPushButton:pressed {
                        border-top: 2px solid #140c02;
                        border-left: 2px solid #140c02;
                        border-bottom: 2px solid #f8b800;
                        border-right: 2px solid #f8b800;
                        padding-top: 4px; padding-left: 6px;
                    }
                """)
        else:
            if self.is_caught:
                self.caught_btn.setText("✓ CAUGHT")
                self.caught_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #065f46;
                        border: 1px solid #10b981;
                        color: #FFFFFF;
                        font-size: 11px;
                        font-weight: bold;
                        border-radius: 4px;
                        padding: 2px 4px;
                    }
                    QPushButton:hover {
                        background-color: #047857;
                    }
                """)
            else:
                self.caught_btn.setText("○ MISSING")
                self.caught_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #451a03;
                        border: 1px solid #d97706;
                        color: #fbbf24;
                        font-size: 11px;
                        font-weight: bold;
                        border-radius: 4px;
                        padding: 2px 4px;
                    }
                    QPushButton:hover {
                        background-color: #78350f;
                        color: #FFFFFF;
                    }
                """)

    def on_caught_button_clicked(self):
        self.is_caught = not self.is_caught
        self.mon_data["is_caught"] = self.is_caught
        self.update_caught_button_state()
        self.update_card_style()
        self.catch_toggled.emit(self.species_id, self.species_name, self.is_caught)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            play_sfx("menu_move.wav")
            self.clicked.emit(self.mon_data)
        super().mousePressEvent(event)


class SpeciesInspectorDrawer(QFrame):
    """
    DexNav Route Inspector & Telemetry Panel matching authentic ORAS / Quetzal in-game DexNav.
    Features:
    - Big clean tactile SEARCH button at top (no [A] button graphic).
    - Pokémon Preview Banner: Species Name, NatDex #, Form Badge, Caught status toggle button.
    - Type badge row ([BUG], [NORMAL], [ICE], etc.).
    - Authentic DexNav Telemetry Card:
        * SEARCH LEVEL (e.g. 10 if caught, 0 if uncaught)
        * HIDDEN ABILITY (e.g. Snow Warning, Friend Guard)
        * HELD ITEMS (e.g. Big Malasada, None)
        * FIRST MOVE / ABILITIES
        * ENCOUNTER RATE & LEVEL RANGE
    - Catch Probability telemetry (Quick Ball, False Swipe + Ultra, Timer Ball)
    - Base Stats Bars Container (HP, Atk, Def, SpA, SpD, Spe, BST)
    - Jump to Pokédex Full View Button
    """
    open_in_pokedex = Signal(int)
    catch_toggled = Signal(int, str, bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_species_id = None
        self.current_species_name = ""
        self.current_national_dex_num = None
        self.current_mon_data = None
        self.is_caught = False
        self.init_ui()

    def init_ui(self):
        self.setFixedWidth(300)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # 1. Big Clean Tactile SEARCH Button at Top (NO [A] button graphic)
        self.search_btn = QPushButton("SEARCH")
        self.search_btn.setFixedHeight(36)
        self.search_btn.setFont(QFont("Arial", 11, QFont.Bold))
        self.search_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.search_btn.clicked.connect(self.on_search_clicked)
        layout.addWidget(self.search_btn)

        # DexNav Title
        self.header_title = QLabel("📡 DEXNAV // SPECIES TELEMETRY")
        self.header_title.setFont(QFont("Arial", 10, QFont.Bold))
        self.header_title.setStyleSheet("color: #38bdf8; letter-spacing: 1px;")
        layout.addWidget(self.header_title)

        # 2. Sprite + Name + Caught Toggle Banner
        self.banner = QFrame()
        self.banner.setObjectName("banner_frame")
        b_layout = QHBoxLayout(self.banner)
        b_layout.setContentsMargins(8, 8, 8, 8)
        b_layout.setSpacing(10)

        self.sprite_lbl = QLabel()
        self.sprite_lbl.setFixedSize(68, 68)
        self.sprite_lbl.setAlignment(Qt.AlignCenter)
        b_layout.addWidget(self.sprite_lbl)

        info_box = QVBoxLayout()
        info_box.setSpacing(3)
        self.name_lbl = QLabel("Select a Pokémon")
        self.name_lbl.setStyleSheet("color: #f8fafc; font-size: 14px; font-weight: bold;")
        self.name_lbl.setWordWrap(True)
        info_box.addWidget(self.name_lbl)

        self.type_row = QHBoxLayout()
        self.type_row.setSpacing(4)
        info_box.addLayout(self.type_row)

        self.caught_btn = QPushButton("○ MISSING")
        self.caught_btn.setFixedHeight(24)
        self.caught_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.caught_btn.clicked.connect(self.on_caught_clicked)
        info_box.addWidget(self.caught_btn)

        b_layout.addLayout(info_box, 1)
        layout.addWidget(self.banner)

        # 3. Authentic DexNav Telemetry Card
        self.dexnav_frame = QFrame()
        self.dexnav_frame.setObjectName("dexnav_frame")
        dn_layout = QVBoxLayout(self.dexnav_frame)
        dn_layout.setContentsMargins(10, 8, 10, 8)
        dn_layout.setSpacing(4)

        self.dn_title = QLabel("🎯 DEXNAV SENSOR DATA")
        self.dn_title.setStyleSheet("color: #38bdf8; font-size: 10px; font-weight: bold; letter-spacing: 1px;")
        dn_layout.addWidget(self.dn_title)

        self.search_lvl_lbl = QLabel("SEARCH LEVEL:  —")
        self.search_lvl_lbl.setStyleSheet("color: #facc15; font-size: 11px; font-weight: bold;")
        dn_layout.addWidget(self.search_lvl_lbl)

        self.hidden_ability_lbl = QLabel("HIDDEN ABILITY:  —")
        self.hidden_ability_lbl.setStyleSheet("color: #38bdf8; font-size: 11px; font-weight: bold;")
        self.hidden_ability_lbl.setWordWrap(True)
        dn_layout.addWidget(self.hidden_ability_lbl)

        self.items_hdr = QLabel("ITEMS")
        self.items_hdr.setAlignment(Qt.AlignCenter)
        dn_layout.addWidget(self.items_hdr)

        self.items_lbl = QLabel("None")
        self.items_lbl.setStyleSheet("color: #e2e8f0; font-size: 11px;")
        self.items_lbl.setWordWrap(True)
        dn_layout.addWidget(self.items_lbl)

        self.rate_info_lbl = QLabel("ENCOUNTER:  —")
        self.rate_info_lbl.setStyleSheet("color: #94a3b8; font-size: 10px;")
        dn_layout.addWidget(self.rate_info_lbl)

        layout.addWidget(self.dexnav_frame)

        # 4. Catch Probability Box
        self.prob_frame = QFrame()
        self.prob_frame.setObjectName("prob_frame")
        pf_layout = QVBoxLayout(self.prob_frame)
        pf_layout.setContentsMargins(10, 8, 10, 8)
        pf_layout.setSpacing(4)

        self.pf_title = QLabel("🎯 CATCH PROBABILITY")
        self.pf_title.setStyleSheet("color: #f59e0b; font-size: 10px; font-weight: bold; letter-spacing: 1px;")
        pf_layout.addWidget(self.pf_title)

        self.quick_ball_lbl = QLabel("⚡ Quick Ball (Turn 1): ---")
        self.quick_ball_lbl.setStyleSheet("color: #e2e8f0; font-size: 11px;")
        pf_layout.addWidget(self.quick_ball_lbl)

        self.false_swipe_lbl = QLabel("⚔️ False Swipe + Ultra: ---")
        self.false_swipe_lbl.setStyleSheet("color: #e2e8f0; font-size: 11px;")
        pf_layout.addWidget(self.false_swipe_lbl)

        self.timer_ball_lbl = QLabel("⏱️ Timer Ball (Turn 5+): ---")
        self.timer_ball_lbl.setStyleSheet("color: #e2e8f0; font-size: 11px;")
        pf_layout.addWidget(self.timer_ball_lbl)
        layout.addWidget(self.prob_frame)

        # 5. Base Stats Bars Container
        self.stats_frame = QFrame()
        self.stats_frame.setObjectName("stats_frame")
        sf_layout = QVBoxLayout(self.stats_frame)
        sf_layout.setContentsMargins(10, 8, 10, 8)
        sf_layout.setSpacing(3)

        sf_head = QHBoxLayout()
        self.sf_title = QLabel("📊 BASE STATS")
        self.sf_title.setStyleSheet("color: #38bdf8; font-size: 10px; font-weight: bold; letter-spacing: 1px;")
        sf_head.addWidget(self.sf_title)
        sf_head.addStretch()
        self.bst_lbl = QLabel("BST: ---")
        self.bst_lbl.setStyleSheet("color: #f8fafc; font-size: 10px; font-weight: bold;")
        sf_head.addWidget(self.bst_lbl)
        sf_layout.addLayout(sf_head)

        self.stat_bars = {}
        for stat in ["HP", "Atk", "Def", "SpA", "SpD", "Spe"]:
            row = QHBoxLayout()
            row.setSpacing(6)
            s_lbl = QLabel(f"{stat:3}")
            s_lbl.setFixedWidth(28)
            s_lbl.setStyleSheet("color: #94a3b8; font-size: 10px; font-weight: bold;")
            row.addWidget(s_lbl)

            bar = QProgressBar()
            bar.setFixedHeight(8)
            bar.setMaximum(255)
            bar.setTextVisible(False)
            row.addWidget(bar, 1)

            val_lbl = QLabel("---")
            val_lbl.setFixedWidth(26)
            val_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            val_lbl.setStyleSheet("color: #f1f5f9; font-size: 10px; font-weight: bold;")
            row.addWidget(val_lbl)

            self.stat_bars[stat] = (bar, val_lbl)
            sf_layout.addLayout(row)

        layout.addWidget(self.stats_frame)
        layout.addStretch()

        # 6. Jump to Pokédex Full View Button
        self.open_pokedex_btn = QPushButton("📖 View Learnset & Evolution in Pokédex")
        self.open_pokedex_btn.setFixedHeight(34)
        self.open_pokedex_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.open_pokedex_btn.clicked.connect(self.on_open_pokedex_clicked)
        layout.addWidget(self.open_pokedex_btn)

        self.apply_theme(CURRENT_THEME)

    def on_search_clicked(self):
        play_sfx("menu_select.wav")
        if not self.current_species_id:
            self.search_btn.setText("⚠️ NO TARGET")
            QTimer.singleShot(1200, lambda: self.search_btn.setText("SEARCH"))
            return
        name = self.current_mon_data.get("species_name", "Pokémon") if self.current_mon_data else "Pokémon"
        self.search_btn.setText(f"🔍 SCANNING {name.upper()}...")
        QTimer.singleShot(600, lambda: self.search_btn.setText(f"✓ {name.upper()} LOCATED NEARBY!"))
        QTimer.singleShot(2200, lambda: self.search_btn.setText("SEARCH"))

    def on_caught_clicked(self):
        if not self.current_species_id:
            return
        self.is_caught = not self.is_caught
        if self.current_mon_data:
            self.current_mon_data["is_caught"] = self.is_caught
        self.update_caught_button_state()
        pm = get_species_pixmap(self.current_species_id, is_silhouette=(not self.is_caught))
        if pm:
            self.sprite_lbl.setPixmap(pm.scaled(68, 68, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        search_lvl = 10 if self.is_caught else 0
        self.search_lvl_lbl.setText(f"SEARCH LEVEL:  {search_lvl}")
        self.catch_toggled.emit(self.current_species_id, self.current_species_name, self.is_caught)

    def set_caught_state(self, is_caught: bool):
        self.is_caught = is_caught
        if self.current_mon_data:
            self.current_mon_data["is_caught"] = is_caught
        self.update_caught_button_state()
        if self.current_species_id:
            pm = get_species_pixmap(self.current_species_id, is_silhouette=(not self.is_caught))
            if pm:
                self.sprite_lbl.setPixmap(pm.scaled(68, 68, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            search_lvl = 10 if self.is_caught else 0
            self.search_lvl_lbl.setText(f"SEARCH LEVEL:  {search_lvl}")

    def update_caught_button_state(self):
        retro = is_retro()
        if retro:
            if self.is_caught:
                self.caught_btn.setText("✓ CAUGHT")
                self.caught_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #0a301c;
                        border-top: 2px solid #00e858;
                        border-left: 2px solid #00e858;
                        border-bottom: 2px solid #04140c;
                        border-right: 2px solid #04140c;
                        color: #00ff88;
                        font-family: 'JetBrainsMono Nerd Font', 'UbuntuMono Nerd Font', monospace;
                        font-size: 10px;
                        font-weight: bold;
                        border-radius: 2px;
                        padding: 3px 8px;
                    }
                    QPushButton:hover { background-color: #104228; color: #ffffff; }
                """)
            else:
                self.caught_btn.setText("○ MISSING")
                self.caught_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #321c04;
                        border-top: 2px solid #f8b800;
                        border-left: 2px solid #f8b800;
                        border-bottom: 2px solid #140c02;
                        border-right: 2px solid #140c02;
                        color: #f8b800;
                        font-family: 'JetBrainsMono Nerd Font', 'UbuntuMono Nerd Font', monospace;
                        font-size: 10px;
                        font-weight: bold;
                        border-radius: 2px;
                        padding: 3px 8px;
                    }
                    QPushButton:hover { background-color: #482a08; color: #ffffff; }
                """)
        else:
            if self.is_caught:
                self.caught_btn.setText("✓ CAUGHT")
                self.caught_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #065f46;
                        border: 1px solid #10b981;
                        color: #FFFFFF;
                        font-size: 11px;
                        font-weight: bold;
                        border-radius: 4px;
                        padding: 3px 8px;
                    }
                    QPushButton:hover { background-color: #047857; }
                """)
            else:
                self.caught_btn.setText("○ MISSING")
                self.caught_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #451a03;
                        border: 1px solid #d97706;
                        color: #fbbf24;
                        font-size: 11px;
                        font-weight: bold;
                        border-radius: 4px;
                        padding: 3px 8px;
                    }
                    QPushButton:hover { background-color: #78350f; color: #FFFFFF; }
                """)

    def apply_theme(self, theme_mode: str):
        if theme_mode == "retro":
            self.setStyleSheet("""
                SpeciesInspectorDrawer {
                    background-color: #ffffff;
                    border-top: 5px solid #ef4444;
                    border-left: 2px solid #cbd5e1;
                    border-right: 2px solid #cbd5e1;
                    border-bottom: 2px solid #cbd5e1;
                    border-radius: 8px;
                }
            """)
            self.search_btn.setStyleSheet("""
                QPushButton {
                    background-color: #22c55e;
                    border: 2px solid #16a34a;
                    color: #ffffff;
                    font-family: 'JetBrainsMono Nerd Font', 'UbuntuMono Nerd Font', monospace;
                    font-size: 13px;
                    font-weight: bold;
                    letter-spacing: 2px;
                    border-radius: 17px;
                    padding: 6px 20px;
                }
                QPushButton:hover {
                    background-color: #16a34a;
                }
                QPushButton:pressed {
                    background-color: #15803d;
                }
            """)
            self.banner.setStyleSheet("background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px;")
            self.name_lbl.setStyleSheet("color: #0f172a; font-family: 'JetBrainsMono Nerd Font', monospace; font-size: 15px; font-weight: bold;")
            self.dexnav_frame.setStyleSheet("background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px;")
            self.search_lvl_lbl.setStyleSheet("color: #d97706; font-family: monospace; font-size: 11px; font-weight: bold;")
            self.hidden_ability_lbl.setStyleSheet("color: #0f172a; font-family: monospace; font-size: 11px; font-weight: bold;")
            self.items_hdr.show()
            self.items_hdr.setStyleSheet("background-color: #dc2626; color: #ffffff; font-family: 'JetBrainsMono Nerd Font', monospace; font-size: 11px; font-weight: bold; padding: 2px 6px; border-radius: 3px;")
            self.items_lbl.setStyleSheet("color: #0f172a; font-family: monospace; font-size: 12px; font-weight: bold; padding: 2px 4px;")

            self.header_title.hide()
            self.rate_info_lbl.hide()
            self.dn_title.hide()
            self.prob_frame.hide()
            self.stats_frame.hide()
            self.open_pokedex_btn.hide()
        else:
            self.setStyleSheet("""
                SpeciesInspectorDrawer {
                    background-color: #101726;
                    border: 1px solid #1e293b;
                    border-radius: 8px;
                }
            """)
            self.header_title.setText("📡 DEXNAV // SPECIES TELEMETRY")
            self.header_title.setStyleSheet("color: #38bdf8; letter-spacing: 1px;")
            self.search_btn.setStyleSheet("""
                QPushButton {
                    background-color: #0284c7;
                    border: 1px solid #38bdf8;
                    color: #ffffff;
                    font-size: 13px;
                    font-weight: bold;
                    letter-spacing: 1px;
                    border-radius: 6px;
                    padding: 6px;
                }
                QPushButton:hover {
                    background-color: #0369a1;
                }
                QPushButton:pressed {
                    background-color: #075985;
                }
            """)
            box_style = """
                background-color: #0c121d;
                border: 1px solid #1e293b;
                border-radius: 6px;
            """
            self.banner.setStyleSheet(box_style)
            self.name_lbl.setStyleSheet("color: #f8fafc; font-size: 14px; font-weight: bold;")
            self.dexnav_frame.setStyleSheet(box_style)
            self.prob_frame.setStyleSheet(box_style)
            self.stats_frame.setStyleSheet(box_style)
            self.header_title.show()
            self.rate_info_lbl.show()
            self.dn_title.show()
            self.prob_frame.show()
            self.stats_frame.show()
            self.open_pokedex_btn.show()
            self.items_hdr.hide()
            for stat, (bar, val_lbl) in self.stat_bars.items():
                bar.setStyleSheet("""
                    QProgressBar {
                        background-color: #1e293b;
                        border-radius: 4px;
                    }
                    QProgressBar::chunk {
                        background-color: #3b82f6;
                        border-radius: 4px;
                    }
                """)
                val_lbl.setStyleSheet("color: #f1f5f9; font-size: 10px; font-weight: bold;")
            self.open_pokedex_btn.setStyleSheet("""
                QPushButton {
                    background-color: #1e3a8a;
                    border: 1px solid #3b82f6;
                    color: #FFFFFF;
                    font-weight: bold;
                    border-radius: 6px;
                }
                QPushButton:hover {
                    background-color: #2563eb;
                }
            """)
        self.update_caught_button_state()

    def on_open_pokedex_clicked(self):
        play_sfx("menu_select.wav")
        if self.current_species_id:
            self.open_in_pokedex.emit(self.current_species_id)

    def populate(self, data: dict):
        self.current_mon_data = data
        self.current_species_id = data["species_id"]
        pid = data["species_id"]
        nat_dex = data.get("national_dex_num", pid)
        self.current_national_dex_num = nat_dex
        name = data["species_name"]
        self.current_species_name = name
        self.is_caught = bool(data.get("is_caught", False))

        form_badge = data.get("form_badge") or get_form_badge(pid, nat_dex, nat_dex, data.get("type1", ""), data.get("type2", ""))
        if is_retro():
            self.name_lbl.setText(name)
        else:
            if form_badge and form_badge != "Standard":
                display_badge = f"{form_badge} Form" if form_badge in ("Alolan", "Galarian", "Hisuian", "Paldean") else form_badge
                self.name_lbl.setText(f"#{nat_dex:04d} {name} • {display_badge}")
            else:
                self.name_lbl.setText(f"#{nat_dex:04d} {name}")
        pm = get_species_pixmap(pid, is_silhouette=(not self.is_caught))
        if pm:
            self.sprite_lbl.setPixmap(pm.scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            self.sprite_lbl.setText("🐾")

        self.update_caught_button_state()

        # Clear type row
        while self.type_row.count():
            item = self.type_row.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        t1 = data.get("type1")
        t2 = data.get("type2")
        if t1 and t1 != "None":
            self.type_row.addWidget(TypeBadge(t1))
        if t2 and t2 != "None" and t2 != t1:
            self.type_row.addWidget(TypeBadge(t2))
        self.type_row.addStretch()

        # DexNav Sensor Data
        search_lvl = 10 if self.is_caught else 0
        self.search_lvl_lbl.setText(f"SEARCH LEVEL:  {search_lvl}")

        ha = data.get("hidden_ability") or data.get("abilities")
        if ha and ha != "None":
            self.hidden_ability_lbl.setText(f"HIDDEN ABILITY:  {ha}")
        else:
            self.hidden_ability_lbl.setText("HIDDEN ABILITY:  None")

        held = data.get("held_items")
        if held and held != "None":
            self.items_lbl.setText(held if is_retro() else f"ITEMS:  {held}")
        else:
            self.items_lbl.setText("NONE" if is_retro() else "ITEMS:  None")

        chance = data.get("chance", 0)
        min_l = data.get("min_level", 0)
        max_l = data.get("max_level", 0)
        lvl_str = f"Lv.{min_l}" if min_l == max_l else (f"Lv.{min_l}–{max_l}" if min_l > 0 else "—")
        self.rate_info_lbl.setText(f"RATE: {chance}%  |  LEVEL: {lvl_str}")

        # Catch probabilities
        cr = data.get("catch_rate", 45)
        qb_chance = min(100, int(cr * 5 / 3))
        fs_chance = min(100, int(cr * 2 * 3.5 / 2.5))
        tb_chance = min(100, int(cr * 4 / 2.5))

        self.quick_ball_lbl.setText(f"⚡ Quick Ball (Turn 1): {qb_chance}% capture chance")
        self.false_swipe_lbl.setText(f"⚔️ False Swipe + Ultra: {fs_chance}% capture chance")
        self.timer_ball_lbl.setText(f"⏱️ Timer Ball (Turn 5+): {tb_chance}% capture chance")

        # Stats
        bst = data.get("bst", 0)
        self.bst_lbl.setText(f"BST: {bst}")
        stats_map = {
            "HP": data.get("hp", 0),
            "Atk": data.get("atk", 0),
            "Def": data.get("def", 0),
            "SpA": data.get("spa", 0),
            "SpD": data.get("spd", 0),
            "Spe": data.get("spe", 0)
        }
        for stat, val in stats_map.items():
            if stat in self.stat_bars:
                bar, lbl = self.stat_bars[stat]
                bar.setValue(val)
                lbl.setText(str(val))

    def clear(self):
        self.current_species_id = None
        self.current_species_name = ""
        self.current_mon_data = None
        self.is_caught = False
        self.name_lbl.setText("No Pokémon Selected")
        self.sprite_lbl.clear()
        self.sprite_lbl.setText("—")
        while self.type_row.count():
            item = self.type_row.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.search_lvl_lbl.setText("SEARCH LEVEL:  —")
        self.hidden_ability_lbl.setText("HIDDEN ABILITY:  —")
        self.items_lbl.setText("ITEMS:  —")
        self.rate_info_lbl.setText("ENCOUNTER:  —")
        self.bst_lbl.setText("BST: —")
        self.quick_ball_lbl.setText("⚡ Quick Ball (Turn 1): —")
        self.false_swipe_lbl.setText("⚔️ False Swipe + Ultra: —")
        self.timer_ball_lbl.setText("⏱️ Timer Ball (Turn 5+): —")
        for stat in ["HP", "Atk", "Def", "SpA", "SpD", "Spe"]:
            if stat in self.stat_bars:
                bar, lbl = self.stat_bars[stat]
                bar.setValue(0)
                lbl.setText("0")
        self.update_caught_button_state()


class ModernLegendaryCard(QFrame):
    """
    Polished graphical card for Legendary & Mythical Pokémon with authentic Emerald GBA styling.
    Features 68x68 sprite, beveled frame, type pills, location,
    generation badge, unlock preview, and 1-click caught toggle button.
    """
    clicked = Signal(dict)
    catch_toggled = Signal(int, str, bool)

    def __init__(self, leg_data: dict, parent=None):
        super().__init__(parent)
        self.leg_data = leg_data
        self.species_id = leg_data.get("species_id", 0)
        self.national_dex_num = leg_data.get("national_dex_num", self.species_id)
        self.name = leg_data.get("name", "Unknown")
        self.is_caught = leg_data.get("is_caught", False)
        self.form_badge = leg_data.get("form_badge") or get_form_badge(self.species_id, self.national_dex_num, self.national_dex_num, leg_data.get("type1", ""), leg_data.get("type2", ""))
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.init_ui()

    def init_ui(self):
        self.setMinimumWidth(240)
        self.setFixedHeight(125)

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(10, 8, 10, 8)
        main_layout.setSpacing(10)

        # Left Column: Large Sprite Box with Gold/Purple Legendary styling
        self.sprite_box = QFrame()
        self.sprite_box.setFixedSize(68, 68)
        sb_layout = QVBoxLayout(self.sprite_box)
        sb_layout.setContentsMargins(0, 0, 0, 0)
        self.sprite_lbl = QLabel()
        self.sprite_lbl.setAlignment(Qt.AlignCenter)

        # Show sprite or silhouette if uncaught
        pm = get_species_pixmap(self.species_id, is_silhouette=(not self.is_caught))
        if pm:
            self.sprite_lbl.setPixmap(pm.scaled(60, 60, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            self.sprite_lbl.setText("👑")
        sb_layout.addWidget(self.sprite_lbl)
        main_layout.addWidget(self.sprite_box, alignment=Qt.AlignVCenter)

        # Center Column: Info & Unlock Details
        info_col = QVBoxLayout()
        info_col.setContentsMargins(0, 0, 0, 0)
        info_col.setSpacing(3)

        # Row 1: Dex # + Name + Form Badge + Gen Tag
        title_box = QHBoxLayout()
        title_box.setSpacing(6)
        if self.national_dex_num > 0:
            self.dex_num = QLabel(f"#{self.national_dex_num:04d}")
            self.dex_num.setStyleSheet("color: #facc15; font-size: 11px; font-weight: bold;")
            title_box.addWidget(self.dex_num)

        self.name_lbl = QLabel(f"⭐ {self.name}")
        self.name_lbl.setStyleSheet("color: #f8fafc; font-size: 14px; font-weight: bold;")
        title_box.addWidget(self.name_lbl)

        if self.form_badge and self.form_badge != "Standard":
            display_badge = f"{self.form_badge} Form" if self.form_badge in ("Alolan", "Galarian", "Hisuian", "Paldean") else self.form_badge
            self.form_badge_lbl = QLabel(display_badge)
            self.form_badge_lbl.setStyleSheet("""
                background-color: #3b2a05;
                color: #fef08a;
                border: 1px solid #ca8a04;
                border-radius: 3px;
                padding: 1px 5px;
                font-size: 9px;
                font-weight: bold;
            """)
            title_box.addWidget(self.form_badge_lbl)

        gen = self.leg_data.get("generation", "")
        if gen:
            gen_clean = gen.replace("Generation ", "Gen ").replace("Native", "").strip()
            self.gen_lbl = QLabel(gen_clean)
            self.gen_lbl.setStyleSheet("""
                background-color: #312e81;
                color: #c7d2fe;
                border: 1px solid #4338ca;
                border-radius: 3px;
                padding: 1px 5px;
                font-size: 9px;
                font-weight: bold;
            """)
            title_box.addWidget(self.gen_lbl)

        title_box.addStretch()
        info_col.addLayout(title_box)

        # Row 2: Dual Type Badges
        type_box = QHBoxLayout()
        type_box.setSpacing(4)
        t1 = self.leg_data.get("type1")
        t2 = self.leg_data.get("type2")
        if t1 and t1 != "None":
            type_box.addWidget(TypeBadge(t1))
        if t2 and t2 != "None" and t2 != t1:
            type_box.addWidget(TypeBadge(t2))
        type_box.addStretch()
        info_col.addLayout(type_box)

        # Row 3: Location Badge
        loc = self.leg_data.get("location", "Unknown Location")
        loc_box = QHBoxLayout()
        loc_box.setSpacing(4)
        self.loc_tag = QLabel(f"📍 {loc}")
        self.loc_tag.setStyleSheet("color: #38bdf8; font-size: 11px; font-weight: 500;")
        loc_box.addWidget(self.loc_tag)
        loc_box.addStretch()
        info_col.addLayout(loc_box)

        # Row 4: Unlock Requirements Preview
        req = self.leg_data.get("requirements", "")
        self.req_lbl = QLabel(f"🔓 {req[:46]}..." if len(req) > 46 else f"🔓 {req}")
        self.req_lbl.setStyleSheet("color: #94a3b8; font-size: 10px;")
        info_col.addWidget(self.req_lbl)

        main_layout.addLayout(info_col, 1)

        # Right Column: 1-Click Caught Toggle Button
        btn_col = QVBoxLayout()
        btn_col.setContentsMargins(0, 0, 0, 0)
        self.caught_btn = QPushButton()
        self.caught_btn.setFixedSize(92, 28)
        self.caught_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.update_caught_button_state()
        self.caught_btn.clicked.connect(self.on_caught_button_clicked)
        btn_col.addWidget(self.caught_btn, alignment=Qt.AlignVCenter)
        main_layout.addLayout(btn_col)

        self.update_card_style(is_selected=False)

    def update_card_style(self, is_selected=False):
        if is_retro():
            if is_selected:
                self.setStyleSheet("""
                    ModernLegendaryCard {
                        background-color: #173b44;
                        border-top: 2px solid #00ff88;
                        border-left: 2px solid #00ff88;
                        border-bottom: 2px solid #081820;
                        border-right: 2px solid #081820;
                        border-radius: 4px;
                    }
                """)
            elif self.is_caught:
                self.setStyleSheet("""
                    ModernLegendaryCard {
                        background-color: #0d2820;
                        border-top: 2px solid #00e858;
                        border-left: 2px solid #00e858;
                        border-bottom: 2px solid #081820;
                        border-right: 2px solid #081820;
                        border-radius: 4px;
                    }
                    ModernLegendaryCard:hover {
                        background-color: #14382e;
                        border-top: 2px solid #34d399;
                        border-left: 2px solid #34d399;
                    }
                """)
            else:
                self.setStyleSheet("""
                    ModernLegendaryCard {
                        background-color: #12242a;
                        border-top: 2px solid #f8b800;
                        border-left: 2px solid #f8b800;
                        border-bottom: 2px solid #081820;
                        border-right: 2px solid #081820;
                        border-radius: 4px;
                    }
                    ModernLegendaryCard:hover {
                        background-color: #182e36;
                        border-top: 2px solid #ffd700;
                        border-left: 2px solid #ffd700;
                    }
                """)
            if hasattr(self, 'sprite_box'):
                border_c = "#00e858" if self.is_caught else "#f8b800"
                self.sprite_box.setStyleSheet(f"""
                    background-color: #081418;
                    border-top: 2px solid #040a0c;
                    border-left: 2px solid #040a0c;
                    border-bottom: 2px solid {border_c};
                    border-right: 2px solid {border_c};
                    border-radius: 3px;
                """)
            if hasattr(self, 'name_lbl'):
                self.name_lbl.setStyleSheet("color: #f8f8f8; font-family: monospace; font-size: 13px; font-weight: bold;")
        else:
            if is_selected:
                self.setStyleSheet("""
                    ModernLegendaryCard {
                        background-color: #1e1b4b;
                        border: 2px solid #818cf8;
                        border-radius: 8px;
                    }
                """)
            elif self.is_caught:
                self.setStyleSheet("""
                    ModernLegendaryCard {
                        background-color: #062b1f;
                        border: 1px solid #059669;
                        border-radius: 8px;
                    }
                    ModernLegendaryCard:hover {
                        background-color: #0c3e2e;
                        border: 1px solid #10b981;
                    }
                """)
            else:
                self.setStyleSheet("""
                    ModernLegendaryCard {
                        background-color: #0f172a;
                        border: 1px solid #1e293b;
                        border-radius: 8px;
                    }
                    ModernLegendaryCard:hover {
                        background-color: #1e293b;
                        border: 1px solid #6366f1;
                    }
                """)
            if hasattr(self, 'sprite_box'):
                border_col = "#eab308" if self.is_caught else "#6366f1"
                bg_col = "#1c1917" if self.is_caught else "#1e1b4b"
                self.sprite_box.setStyleSheet(f"""
                    background-color: {bg_col};
                    border: 1.5px solid {border_col};
                    border-radius: 8px;
                """)
            if hasattr(self, 'name_lbl'):
                self.name_lbl.setStyleSheet("color: #f8fafc; font-size: 14px; font-weight: bold;")

    def update_caught_button_state(self):
        if is_retro():
            if self.is_caught:
                self.caught_btn.setText("✓ CAUGHT")
                self.caught_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #0a301c;
                        border-top: 2px solid #00e858;
                        border-left: 2px solid #00e858;
                        border-bottom: 2px solid #04140c;
                        border-right: 2px solid #04140c;
                        color: #00ff88;
                        font-family: 'JetBrainsMono Nerd Font', 'UbuntuMono Nerd Font', monospace;
                        font-size: 10px;
                        font-weight: bold;
                        border-radius: 2px;
                        padding: 2px 4px;
                    }
                    QPushButton:hover {
                        background-color: #104228;
                        color: #ffffff;
                    }
                    QPushButton:pressed {
                        border-top: 2px solid #04140c;
                        border-left: 2px solid #04140c;
                        border-bottom: 2px solid #00e858;
                        border-right: 2px solid #00e858;
                        padding-top: 4px; padding-left: 6px;
                    }
                """)
            else:
                self.caught_btn.setText("○ MISSING")
                self.caught_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #321c04;
                        border-top: 2px solid #f8b800;
                        border-left: 2px solid #f8b800;
                        border-bottom: 2px solid #140c02;
                        border-right: 2px solid #140c02;
                        color: #f8b800;
                        font-family: 'JetBrainsMono Nerd Font', 'UbuntuMono Nerd Font', monospace;
                        font-size: 10px;
                        font-weight: bold;
                        border-radius: 2px;
                        padding: 2px 4px;
                    }
                    QPushButton:hover {
                        background-color: #482a08;
                        color: #ffffff;
                    }
                    QPushButton:pressed {
                        border-top: 2px solid #140c02;
                        border-left: 2px solid #140c02;
                        border-bottom: 2px solid #f8b800;
                        border-right: 2px solid #f8b800;
                        padding-top: 4px; padding-left: 6px;
                    }
                """)
        else:
            if self.is_caught:
                self.caught_btn.setText("✓ CAUGHT")
                self.caught_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #059669;
                        color: #FFFFFF;
                        font-size: 11px;
                        font-weight: bold;
                        border-radius: 4px;
                        border: 1px solid #10b981;
                    }
                    QPushButton:hover {
                        background-color: #047857;
                    }
                """)
            else:
                self.caught_btn.setText("○ MISSING")
                self.caught_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #1e293b;
                        color: #facc15;
                        font-size: 11px;
                        font-weight: bold;
                        border-radius: 4px;
                        border: 1px solid #eab308;
                    }
                    QPushButton:hover {
                        background-color: #334155;
                        color: #fef08a;
                    }
                """)

    def on_caught_button_clicked(self):
        self.is_caught = not self.is_caught
        self.update_caught_button_state()
        self.update_card_style(is_selected=False)
        pm = get_species_pixmap(self.species_id, is_silhouette=(not self.is_caught))
        if pm:
            self.sprite_lbl.setPixmap(pm.scaled(60, 60, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.catch_toggled.emit(self.species_id, self.name, self.is_caught)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            play_sfx("menu_move.wav")
            self.clicked.emit(self.leg_data)
        super().mousePressEvent(event)


class LegendaryInspectorDrawer(QFrame):
    """
    Sleek right-side inspector drawer for the selected Legendary Pokémon.
    Displays big sprite, stats, unlock requirements, party synergy, and catch rates.
    """
    open_in_pokedex = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_species_id = 0
        self.init_ui()

    def init_ui(self):
        self.setMinimumWidth(320)
        self.setMaximumWidth(420)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        # Header Title
        title_box = QHBoxLayout()
        h_icon = QLabel("👑")
        h_icon.setStyleSheet("font-size: 16px;")
        title_box.addWidget(h_icon)
        self.title_lbl = QLabel("LEGENDARY SANCTUM")
        self.title_lbl.setFont(QFont("Arial", 11, QFont.Bold))
        self.title_lbl.setStyleSheet("color: #facc15; letter-spacing: 1px;")
        title_box.addWidget(self.title_lbl)
        title_box.addStretch()
        layout.addLayout(title_box)

        # Hero Profile Frame
        self.profile_frame = QFrame()
        pf_layout = QHBoxLayout(self.profile_frame)
        pf_layout.setSpacing(12)

        self.sprite_lbl = QLabel()
        self.sprite_lbl.setFixedSize(88, 88)
        self.sprite_lbl.setAlignment(Qt.AlignCenter)
        pf_layout.addWidget(self.sprite_lbl)

        info_col = QVBoxLayout()
        info_col.setSpacing(3)
        self.dex_lbl = QLabel("#0000")
        self.dex_lbl.setStyleSheet("color: #facc15; font-size: 12px; font-weight: bold;")
        info_col.addWidget(self.dex_lbl)

        self.name_lbl = QLabel("Select a Legendary")
        self.name_lbl.setFont(QFont("Arial", 15, QFont.Bold))
        self.name_lbl.setStyleSheet("color: #f8fafc;")
        info_col.addWidget(self.name_lbl)

        self.types_layout = QHBoxLayout()
        self.types_layout.setSpacing(4)
        info_col.addLayout(self.types_layout)

        self.bst_lbl = QLabel("Total BST: ---")
        self.bst_lbl.setStyleSheet("color: #94a3b8; font-size: 11px;")
        info_col.addWidget(self.bst_lbl)
        pf_layout.addLayout(info_col, 1)
        layout.addWidget(self.profile_frame)

        # Scrollable Content Area for Requirements & Lore
        content_scroll = QScrollArea()
        content_scroll.setWidgetResizable(True)
        content_scroll.setStyleSheet("background: transparent; border: none;")
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(10)

        # Unlock Requirements Box
        self.req_frame = QFrame()
        rf_layout = QVBoxLayout(self.req_frame)
        rf_layout.setContentsMargins(8, 8, 8, 8)
        rf_layout.setSpacing(4)
        self.rf_title = QLabel("🔓 UNLOCK REQUIREMENTS & ACCESS")
        self.rf_title.setStyleSheet("color: #fb7185; font-size: 10px; font-weight: bold; letter-spacing: 1px;")
        rf_layout.addWidget(self.rf_title)
        self.req_lbl = QLabel("---")
        self.req_lbl.setWordWrap(True)
        self.req_lbl.setStyleSheet("color: #f1f5f9; font-size: 11px; line-height: 1.4;")
        rf_layout.addWidget(self.req_lbl)
        scroll_layout.addWidget(self.req_frame)

        # Party Synergy / Multi-Use Squad Box
        self.syn_frame = QFrame()
        sf_layout = QVBoxLayout(self.syn_frame)
        sf_layout.setContentsMargins(8, 8, 8, 8)
        sf_layout.setSpacing(4)
        self.sf_title = QLabel("🧭 RECOMMENDED PARTY SYNERGY")
        self.sf_title.setStyleSheet("color: #38bdf8; font-size: 10px; font-weight: bold; letter-spacing: 1px;")
        sf_layout.addWidget(self.sf_title)
        self.syn_lbl = QLabel("---")
        self.syn_lbl.setWordWrap(True)
        self.syn_lbl.setStyleSheet("color: #e2e8f0; font-size: 11px;")
        sf_layout.addWidget(self.syn_lbl)
        scroll_layout.addWidget(self.syn_frame)

        # Base Stats Bars Container
        self.stats_frame = QFrame()
        st_layout = QVBoxLayout(self.stats_frame)
        st_layout.setContentsMargins(8, 8, 8, 8)
        st_layout.setSpacing(4)
        self.st_title = QLabel("📊 BASE STATS")
        self.st_title.setStyleSheet("color: #facc15; font-size: 10px; font-weight: bold; letter-spacing: 1px;")
        st_layout.addWidget(self.st_title)

        self.stat_bars = {}
        for stat in ["HP", "Atk", "Def", "SpA", "SpD", "Spe"]:
            row = QHBoxLayout()
            row.setSpacing(6)
            s_lbl = QLabel(f"{stat:3}")
            s_lbl.setFixedWidth(28)
            s_lbl.setStyleSheet("color: #94a3b8; font-size: 10px; font-weight: bold;")
            row.addWidget(s_lbl)

            bar = QProgressBar()
            bar.setFixedHeight(8)
            bar.setMaximum(255)
            bar.setTextVisible(False)
            row.addWidget(bar, 1)

            val_lbl = QLabel("0")
            val_lbl.setFixedWidth(28)
            val_lbl.setAlignment(Qt.AlignRight)
            val_lbl.setStyleSheet("color: #f8fafc; font-size: 10px;")
            row.addWidget(val_lbl)

            st_layout.addLayout(row)
            self.stat_bars[stat] = (bar, val_lbl)

        scroll_layout.addWidget(self.stats_frame)

        # Catch Probability Box
        self.prob_frame = QFrame()
        pf2_layout = QVBoxLayout(self.prob_frame)
        pf2_layout.setContentsMargins(8, 8, 8, 8)
        pf2_layout.setSpacing(4)
        self.pf2_title = QLabel("🎯 CATCH PROBABILITY")
        self.pf2_title.setStyleSheet("color: #f59e0b; font-size: 10px; font-weight: bold; letter-spacing: 1px;")
        pf2_layout.addWidget(self.pf2_title)

        self.quick_ball_lbl = QLabel("⚡ Quick Ball (Turn 1): ---")
        self.quick_ball_lbl.setStyleSheet("color: #e2e8f0; font-size: 11px;")
        pf2_layout.addWidget(self.quick_ball_lbl)

        self.false_swipe_lbl = QLabel("⚔️ False Swipe + Ultra: ---")
        self.false_swipe_lbl.setStyleSheet("color: #e2e8f0; font-size: 11px;")
        pf2_layout.addWidget(self.false_swipe_lbl)

        self.timer_ball_lbl = QLabel("⏱️ Timer Ball (Turn 5+): ---")
        self.timer_ball_lbl.setStyleSheet("color: #e2e8f0; font-size: 11px;")
        pf2_layout.addWidget(self.timer_ball_lbl)
        scroll_layout.addWidget(self.prob_frame)

        content_scroll.setWidget(scroll_widget)
        layout.addWidget(content_scroll, 1)

        # View in Pokedex Button
        self.btn_open_pokedex = QPushButton("📖 View Learnset & Stats in Pokédex")
        self.btn_open_pokedex.setFixedHeight(34)
        self.btn_open_pokedex.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_open_pokedex.clicked.connect(self.on_open_pokedex_clicked)
        layout.addWidget(self.btn_open_pokedex)

        self.apply_theme(CURRENT_THEME)

    def apply_theme(self, theme_mode: str):
        if theme_mode == "retro":
            self.setStyleSheet("""
                LegendaryInspectorDrawer {
                    background-color: #10262e;
                    border-top: 3px solid #58b8a8;
                    border-left: 3px solid #58b8a8;
                    border-bottom: 3px solid #081820;
                    border-right: 3px solid #081820;
                    border-radius: 4px;
                }
            """)
            self.title_lbl.setText("LEGENDARY SANCTUM // POKéNAV")
            self.title_lbl.setStyleSheet("color: #f8b800; font-family: 'JetBrainsMono Nerd Font', 'UbuntuMono Nerd Font', monospace; font-size: 11px; font-weight: bold; letter-spacing: 1px;")
            box_style = """
                background-color: #09171e;
                border-top: 2px solid #040a0c;
                border-left: 2px solid #040a0c;
                border-bottom: 2px solid #387068;
                border-right: 2px solid #387068;
                border-radius: 3px;
                padding: 6px;
            """
            self.profile_frame.setStyleSheet(box_style)
            self.req_frame.setStyleSheet(box_style)
            self.syn_frame.setStyleSheet(box_style)
            self.stats_frame.setStyleSheet(box_style)
            self.prob_frame.setStyleSheet(box_style)
            for stat, (bar, val_lbl) in self.stat_bars.items():
                bar.setStyleSheet("""
                    QProgressBar {
                        background-color: #081418;
                        border-top: 1px solid #040a0c;
                        border-left: 1px solid #040a0c;
                        border-bottom: 1px solid #285462;
                        border-right: 1px solid #285462;
                        border-radius: 2px;
                    }
                    QProgressBar::chunk {
                        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #f8b800, stop:1 #c08000);
                        border-radius: 1px;
                    }
                """)
                val_lbl.setStyleSheet("color: #f8b800; font-family: monospace; font-size: 10px; font-weight: bold;")
            self.btn_open_pokedex.setStyleSheet("""
                QPushButton {
                    background-color: #183844;
                    border-top: 2px solid #58b8a8;
                    border-left: 2px solid #58b8a8;
                    border-bottom: 2px solid #081820;
                    border-right: 2px solid #081820;
                    color: #00ff88;
                    font-family: 'JetBrainsMono Nerd Font', 'UbuntuMono Nerd Font', monospace;
                    font-size: 11px;
                    font-weight: bold;
                    border-radius: 2px;
                    padding: 5px 8px;
                }
                QPushButton:hover {
                    background-color: #245060;
                    border-top: 2px solid #78d8c0;
                    border-left: 2px solid #78d8c0;
                    color: #ffffff;
                }
                QPushButton:pressed {
                    border-top: 2px solid #081820;
                    border-left: 2px solid #081820;
                    border-bottom: 2px solid #58b8a8;
                    border-right: 2px solid #58b8a8;
                    padding-top: 7px; padding-left: 10px;
                }
            """)
        else:
            self.setStyleSheet("""
                LegendaryInspectorDrawer {
                    background-color: #0a0f1d;
                    border: 1px solid #1e293b;
                    border-radius: 8px;
                }
            """)
            self.title_lbl.setText("LEGENDARY SANCTUM")
            self.title_lbl.setStyleSheet("color: #facc15; letter-spacing: 1px;")
            box_style = """
                background-color: #0f172a;
                border: 1px solid #312e81;
                border-radius: 8px;
                padding: 8px;
            """
            self.profile_frame.setStyleSheet(box_style)
            self.req_frame.setStyleSheet("""
                background-color: #0f172a;
                border: 1px solid #1e293b;
                border-radius: 8px;
                padding: 10px;
            """)
            self.syn_frame.setStyleSheet("""
                background-color: #0f172a;
                border: 1px solid #1e293b;
                border-radius: 8px;
                padding: 10px;
            """)
            self.stats_frame.setStyleSheet("""
                background-color: #0f172a;
                border: 1px solid #1e293b;
                border-radius: 8px;
                padding: 10px;
            """)
            self.prob_frame.setStyleSheet("""
                background-color: #0f172a;
                border: 1px solid #1e293b;
                border-radius: 8px;
                padding: 10px;
            """)
            for stat, (bar, val_lbl) in self.stat_bars.items():
                bar.setStyleSheet("""
                    QProgressBar {
                        background-color: #1e293b;
                        border-radius: 4px;
                    }
                    QProgressBar::chunk {
                        background-color: #3b82f6;
                        border-radius: 4px;
                    }
                """)
                val_lbl.setStyleSheet("color: #f8fafc; font-size: 10px;")
            self.btn_open_pokedex.setStyleSheet("""
                QPushButton {
                    background-color: #2563eb;
                    color: #FFFFFF;
                    font-size: 12px;
                    font-weight: bold;
                    border-radius: 6px;
                }
                QPushButton:hover {
                    background-color: #3b82f6;
                }
            """)

    def on_open_pokedex_clicked(self):
        play_sfx("menu_select.wav")
        if self.current_species_id > 0:
            self.open_in_pokedex.emit(self.current_species_id)

    def populate(self, data: dict):
        self.current_species_id = data.get("species_id", 0)
        pid = self.current_species_id
        nat_dex = data.get("national_dex_num", pid)
        self.current_national_dex_num = nat_dex
        name = data.get("name", "Unknown")
        is_caught = data.get("is_caught", False)

        form_badge = data.get("form_badge") or get_form_badge(pid, nat_dex, nat_dex, data.get("type1", ""), data.get("type2", ""))
        form_suffix = f" • {form_badge} Form" if (form_badge and form_badge != "Standard") else ""

        if nat_dex > 0:
            self.dex_lbl.setText(f"#{nat_dex:04d}")
        else:
            self.dex_lbl.setText("SPECIAL")
        self.name_lbl.setText(f"⭐ {name}{form_suffix}")

        pm = get_species_pixmap(pid, is_silhouette=(not is_caught))
        if pm:
            self.sprite_lbl.setPixmap(pm.scaled(80, 80, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            self.sprite_lbl.setText("👑")

        while self.types_layout.count():
            item = self.types_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        t1 = data.get("type1")
        t2 = data.get("type2")
        if t1 and t1 != "None":
            self.types_layout.addWidget(TypeBadge(t1))
        if t2 and t2 != "None" and t2 != t1:
            self.types_layout.addWidget(TypeBadge(t2))
        self.types_layout.addStretch()

        bst = data.get("bst", 0)
        self.bst_lbl.setText(f"Total BST: {bst}" if bst else "Total BST: ---")

        self.req_lbl.setText(data.get("requirements", "No special unlock requirements."))
        self.syn_lbl.setText(data.get("synergy", "Standard high-level party setup recommended."))

        # Stats
        stat_keys = [("HP", "hp"), ("Atk", "atk"), ("Def", "def"), ("SpA", "spa"), ("SpD", "spd"), ("Spe", "spe")]
        for stat_name, k in stat_keys:
            if stat_name in self.stat_bars:
                val = data.get(k, 0) or 0
                bar, val_lbl = self.stat_bars[stat_name]
                bar.setValue(val)
                val_lbl.setText(str(val))

        # Catch Probabilities
        cr = data.get("catch_rate", 3) or 3
        qb_pct = min(100.0, (cr * 5.0 / (3 * 255)) * 100.0)
        fs_pct = min(100.0, (cr * 2.0 / 255) * 100.0)
        tb_pct = min(100.0, (cr * 4.0 / (3 * 255)) * 100.0)

        self.quick_ball_lbl.setText(f"⚡ Quick Ball (Turn 1): ~{qb_pct:.1f}%")
        self.false_swipe_lbl.setText(f"⚔️ False Swipe (1 HP) + Ultra: ~{fs_pct:.1f}%")
        self.timer_ball_lbl.setText(f"⏱️ Timer Ball (Turn 5+): ~{tb_pct:.1f}%")

    def clear(self):
        self.current_species_id = 0
        self.dex_lbl.setText("#0000")
        self.name_lbl.setText("Select a Legendary")
        self.sprite_lbl.clear()
        self.sprite_lbl.setText("👑")
        while self.types_layout.count():
            item = self.types_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.bst_lbl.setText("Total BST: ---")
        self.req_lbl.setText("---")
        self.syn_lbl.setText("---")
        for stat, (bar, val_lbl) in self.stat_bars.items():
            bar.setValue(0)
            val_lbl.setText("0")
        self.quick_ball_lbl.setText("⚡ Quick Ball (Turn 1): ---")
        self.false_swipe_lbl.setText("⚔️ False Swipe + Ultra: ---")
        self.timer_ball_lbl.setText("⏱️ Timer Ball (Turn 5+): ---")


class QuetzalMasterApp(QMainWindow):
    """Lead Orchestrator Window for Pokémon Quetzal Companion."""
    def __init__(self):
        super().__init__()
        self.current_theme = "retro"
        global CURRENT_THEME
        CURRENT_THEME = "retro"

        self.setWindowTitle("🎮 Pokémon Quetzal // PokéNav Advance Companion")
        self.resize(1380, 890)
        self.setMinimumSize(1220, 780)
        self.setStyleSheet(RETRO_POKENAV_STYLESHEET)

        self.db_path = DB_PATH
        self.conn = sqlite3.connect(DB_PATH, timeout=15.0)
        self.cur = self.conn.cursor()
        self.cur.execute("PRAGMA journal_mode=WAL;")
        self.cur.execute("PRAGMA busy_timeout=10000;")

        # Load caught species
        self.cur.execute("SELECT species_id FROM caught_pokemon")
        self.caught_species = set(row[0] for row in self.cur.fetchall())

        # Load national dex maps and form groupings
        self.cur.execute("SELECT id, national_dex_num, name, type1, type2 FROM pokemon ORDER BY national_dex_num ASC, id ASC")
        rows = self.cur.fetchall()
        self.sp_to_nat = {}
        self.sp_to_name = {}
        self.nat_to_sps = {}
        self.nat_base_species = {}
        self.nat_dex_to_forms = {}

        for pid, nat, name, t1, t2 in rows:
            nat = nat if nat is not None else pid
            self.sp_to_nat[pid] = nat
            self.sp_to_name[pid] = name
            self.nat_to_sps.setdefault(nat, []).append(pid)
            if nat not in self.nat_base_species:
                self.nat_base_species[nat] = pid

        for pid, nat, name, t1, t2 in rows:
            nat = nat if nat is not None else pid
            base_id = self.nat_base_species[nat]
            badge = get_form_badge(pid, nat, base_id, t1, t2)
            self.nat_dex_to_forms.setdefault(nat, []).append({
                "id": pid,
                "name": name,
                "national_dex_num": nat,
                "type1": t1,
                "type2": t2,
                "badge": badge
            })

        self.current_region = "Hoenn"
        self.current_route_name = "ROUTE 101"
        self.filter_mode = "Show All"
        self.habitat_filter = "All"
        self.all_rendered_cards = []
        self.rendered_leg_cards = []

        # Save file monitoring
        self.save_path = DEFAULT_SAV_PATH
        self.last_save_mtime = 0
        if os.path.exists(self.save_path):
            self.last_save_mtime = os.path.getmtime(self.save_path)

        self.init_ui()
        self.init_save_watcher()

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        self.main_layout = main_layout
        main_layout.setContentsMargins(12, 10, 12, 12)
        main_layout.setSpacing(8)

        # ==========================================
        # TOP HEADER & REAL-TIME SAVE STATUS
        # ==========================================
        self.header_frame = QFrame()
        self.header_frame.setObjectName("top_header_bar")
        h_layout = QHBoxLayout(self.header_frame)
        h_layout.setContentsMargins(10, 6, 10, 6)
        h_layout.setSpacing(12)

        # Title & Subtitle Column
        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        self.app_title = QLabel("🎮 POKéNAV ADVANCE // QUETZAL COMPANION")
        title_col.addWidget(self.app_title)

        self.subtitle = QLabel("DEVON CORP. POKéNAV EMERALD OS // HOENN DUAL-DEX SYSTEM")
        title_col.addWidget(self.subtitle)
        h_layout.addLayout(title_col)

        # Retro GBA Hardware Telemetry: Glowing Green Power LED & Retro Battery Badge
        self.telemetry_col = QHBoxLayout()
        self.telemetry_col.setSpacing(8)

        self.power_led = QLabel("● POWER")
        self.power_led.setAlignment(Qt.AlignCenter)
        self.telemetry_col.addWidget(self.power_led)

        self.battery_badge = QLabel("🔋 BATTERY: FULL [■■■]")
        self.battery_badge.setAlignment(Qt.AlignCenter)
        self.telemetry_col.addWidget(self.battery_badge)

        h_layout.addLayout(self.telemetry_col)

        h_layout.addStretch()

        # Save Info & Caught Progress
        save_col = QVBoxLayout()
        save_col.setSpacing(2)
        save_col.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.save_status_lbl = QLabel(f"💾 Player: NIG • Caught: {len(self.caught_species)} / 1,499 ({len(self.caught_species)/1499*100:.1f}%)")
        save_col.addWidget(self.save_status_lbl, alignment=Qt.AlignRight)

        self.live_watcher_badge = QLabel("🟢 Live Save Sync Active (Auto-Refreshes On In-Game Save)")
        save_col.addWidget(self.live_watcher_badge, alignment=Qt.AlignRight)

        h_layout.addLayout(save_col)

        # Theme Toggle Button: [🎮 PokéNav GBA] ↔ [⚡ Cyber Modern]
        self.theme_btn = QPushButton("🎮 PokéNav GBA")
        self.theme_btn.setFixedHeight(32)
        self.theme_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.theme_btn.clicked.connect(self.toggle_theme)
        h_layout.addWidget(self.theme_btn)

        # Manual Sync Button
        self.sync_btn = QPushButton("↻ Resync .SAV")
        self.sync_btn.setFixedHeight(32)
        self.sync_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.sync_btn.clicked.connect(self.sync_save_file)
        h_layout.addWidget(self.sync_btn)

        # Authentic GBA [START] Menu Button
        self.start_btn = QPushButton("▶ [START] (Space)")
        self.start_btn.setFixedHeight(32)
        self.start_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.start_btn.clicked.connect(self.toggle_start_menu)
        h_layout.addWidget(self.start_btn)

        main_layout.addWidget(self.header_frame)

        # ==========================================
        # TABS CONTAINER
        # ==========================================
        self.tabs = QTabWidget()
        self.tabs.currentChanged.connect(self.on_tab_changed)
        main_layout.addWidget(self.tabs, 1)

        self.create_encounter_tab()
        self.create_map_tab()
        self.create_pokedex_tab()
        self.create_trainers_tab()
        self.create_legendaries_tab()
        self.create_legendary_roadmap_tab()
        self.create_calculator_tab()

        # GBA Controller Guide Bar
        self.controller_guide_bar = QFrame()
        self.controller_guide_bar.setFixedHeight(28)
        self.controller_guide_bar.setStyleSheet("""
            QFrame {
                background-color: #08161e;
                border-top: 1px solid #1a3d38;
            }
        """)
        cgb_layout = QHBoxLayout(self.controller_guide_bar)
        cgb_layout.setContentsMargins(12, 2, 12, 2)
        self.controller_guide_lbl = QLabel("🎮 [D-PAD / ↑↓←→] Move  •  [A / Z / Enter] Select/Search  •  [B / X / Esc] Back  •  [START / Space] Menu  •  [L / R / Q/W] Route  •  [F11] Fullscreen")
        self.controller_guide_lbl.setAlignment(Qt.AlignCenter)
        self.controller_guide_lbl.setStyleSheet("color: #00ff88; font-family: 'JetBrainsMono Nerd Font', 'UbuntuMono Nerd Font', monospace; font-size: 11px; font-weight: bold;")
        cgb_layout.addWidget(self.controller_guide_lbl)
        main_layout.addWidget(self.controller_guide_bar)

        self.apply_theme()

        # GBA Start Menu Overlay
        self.start_menu = GbaStartMenuOverlay(save_path=self.save_path, parent=self)
        self.start_menu.action_triggered.connect(self.on_start_menu_action)

        for btn in self.findChildren(QPushButton):
            btn.setFocusPolicy(Qt.NoFocus)

        self.gba_event_filter = GbaApplicationEventFilter(self)
        qapp = QApplication.instance()
        if qapp:
            qapp.installEventFilter(self.gba_event_filter)

        self.dexnav_sel_row = 1
        self.dexnav_sel_col = 0

    def toggle_start_menu(self):
        """Toggle authentic in-game GBA Start Menu overlay."""
        if hasattr(self, 'start_menu'):
            self.start_menu.resize(self.size())
            self.start_menu.toggle_menu()

    def on_start_menu_action(self, action: str):
        """Handle option selected in the GBA Start Menu overlay."""
        if action == "POKÉDEX":
            self.tabs.setCurrentIndex(2)
            if hasattr(self, 'pokedex_main_tabs'):
                self.pokedex_main_tabs.setCurrentIndex(0)
        elif action == "DEXNAV":
            self.tabs.setCurrentIndex(0)
        elif action == "TOWN MAP":
            self.tabs.setCurrentIndex(1)
        elif action == "POKÉMON":
            self.tabs.setCurrentIndex(3)
        elif action == "LEGENDARY":
            self.tabs.setCurrentIndex(5)
        elif action == "OPTION":
            self.toggle_theme()
        elif action == "MPLAYER":
            play_sfx("caught_fanfare.wav")
        elif action == "MISC":
            self.tabs.setCurrentIndex(6)

    def _get_dexnav_slots_grid(self):
        """Returns 2D grid of DexNavSlotWidget:
        row 0: water_box.slots (5)
        row 1: land_box.slots[0:6] (6)
        row 2: land_box.slots[6:12] (6)
        row 3: beach_box.slots (3) + hidden_box.slots (1) (4)
        """
        r0 = list(getattr(self.water_box, 'slots', []))
        land_slots = getattr(self.land_box, 'slots', [])
        r1 = list(land_slots[:6])
        r2 = list(land_slots[6:12])
        r3 = list(getattr(self.beach_box, 'slots', [])) + list(getattr(self.hidden_box, 'slots', []))
        return [r0, r1, r2, r3]

    def _select_dexnav_slot(self, row: int, col: int, play_sound: bool = True):
        grid = self._get_dexnav_slots_grid()
        if not grid or not (0 <= row < len(grid)):
            return
        r_slots = grid[row]
        if not r_slots:
            return
        col = max(0, min(col, len(r_slots) - 1))
        self.dexnav_sel_row = row
        self.dexnav_sel_col = col
        target_slot = r_slots[col]

        for box in [self.water_box, self.land_box, self.beach_box, self.hidden_box]:
            for s in box.slots:
                s.is_selected = (s is target_slot)
                s.update_style()

        if target_slot.mon_data:
            self.inspector_drawer.populate(target_slot.mon_data)
            if hasattr(self, 'dexnav_search_lbl'):
                self.dexnav_search_lbl.setText(f"SEARCH  {target_slot.mon_data['species_name'].upper()}")
        else:
            if hasattr(self, 'dexnav_search_lbl'):
                self.dexnav_search_lbl.setText("SEARCH  POKéMON")

        if hasattr(self, 'cards_scroll'):
            self.cards_scroll.ensureWidgetVisible(target_slot)

        if play_sound:
            play_sfx("menu_move.wav")

    def _nav_dexnav_dpad(self, dx: int, dy: int):
        grid = self._get_dexnav_slots_grid()
        if not grid:
            return
        curr_r = getattr(self, 'dexnav_sel_row', 1)
        curr_c = getattr(self, 'dexnav_sel_col', 0)

        if dy != 0:
            new_r = max(0, min(len(grid) - 1, curr_r + dy))
            new_c = min(curr_c, len(grid[new_r]) - 1)
            self._select_dexnav_slot(new_r, new_c, play_sound=True)
        elif dx != 0:
            new_c = max(0, min(len(grid[curr_r]) - 1, curr_c + dx))
            self._select_dexnav_slot(curr_r, new_c, play_sound=True)

    def keyPressEvent(self, event):
        """Global key handling for authentic GBA controls."""
        focus_w = QApplication.focusWidget()
        in_text = isinstance(focus_w, (QLineEdit, QTextEdit, QPlainTextEdit))

        if event.key() == Qt.Key_F11:
            if self.isFullScreen():
                self.showNormal()
            else:
                self.showFullScreen()
            event.accept()
            return

        if event.key() == Qt.Key_Space:
            if not in_text:
                self.toggle_start_menu()
                event.accept()
                return

        if hasattr(self, 'start_menu') and self.start_menu.isVisible():
            if event.key() in (Qt.Key_Escape, Qt.Key_X):
                self.start_menu.hide_menu()
                event.accept()
                return
            self.start_menu.keyPressEvent(event)
            if event.isAccepted():
                return

        if not in_text:
            cur_tab = self.tabs.currentIndex()
            # DexNav Route encounters tab
            if cur_tab == 0:
                key = event.key()
                if key in (Qt.Key_Up, Qt.Key_K):
                    self._nav_dexnav_dpad(0, -1)
                    event.accept()
                    return
                elif key in (Qt.Key_Down, Qt.Key_J):
                    self._nav_dexnav_dpad(0, 1)
                    event.accept()
                    return
                elif key in (Qt.Key_Left, Qt.Key_H):
                    self._nav_dexnav_dpad(-1, 0)
                    event.accept()
                    return
                elif key in (Qt.Key_Right, Qt.Key_L):
                    self._nav_dexnav_dpad(1, 0)
                    event.accept()
                    return
                elif key in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Z):
                    grid = self._get_dexnav_slots_grid()
                    r = getattr(self, 'dexnav_sel_row', 1)
                    c = getattr(self, 'dexnav_sel_col', 0)
                    if 0 <= r < len(grid) and 0 <= c < len(grid[r]):
                        slot = grid[r][c]
                        if slot.mon_data:
                            play_sfx("menu_select.wav")
                            if hasattr(self.inspector_drawer, 'search_btn'):
                                self.inspector_drawer.search_btn.click()
                    event.accept()
                    return
                elif key in (Qt.Key_Escape, Qt.Key_X):
                    play_sfx("menu_cancel.wav")
                    event.accept()
                    return
                elif key in (Qt.Key_Q, Qt.Key_PageUp, Qt.Key_BracketLeft):
                    self.on_prev_route()
                    event.accept()
                    return
                elif key in (Qt.Key_W, Qt.Key_PageDown, Qt.Key_BracketRight):
                    self.on_next_route()
                    event.accept()
                    return

            # Town Map tab
            elif cur_tab == 1 and hasattr(self, 'map_widget'):
                self.map_widget.keyPressEvent(event)
                if event.isAccepted():
                    return

            # Pokédex tab
            elif cur_tab == 2 and hasattr(self, 'retro_pokedex_view'):
                self.retro_pokedex_view.keyPressEvent(event)
                if event.isAccepted():
                    return

        super().keyPressEvent(event)

    def resizeEvent(self, event):
        """Keep overlay sized to main companion window."""
        super().resizeEvent(event)
        if hasattr(self, 'start_menu'):
            self.start_menu.resize(self.size())

    def on_tab_changed(self, index: int):
        play_sfx("menu_select.wav")

    def toggle_theme(self):
        play_sfx("menu_select.wav")
        if self.current_theme == "retro":
            self.current_theme = "modern"
        else:
            self.current_theme = "retro"
        global CURRENT_THEME
        CURRENT_THEME = self.current_theme
        self.apply_theme()

    def apply_theme(self):
        global CURRENT_THEME
        CURRENT_THEME = self.current_theme

        if self.current_theme == "retro":
            self.setStyleSheet(RETRO_POKENAV_STYLESHEET)
            self.setWindowTitle("🎮 Pokémon Quetzal // PokéNav Advance Companion")

            if hasattr(self, 'tabs') and self.tabs.tabBar():
                self.tabs.tabBar().hide()
            if hasattr(self, 'header_frame'):
                self.header_frame.hide()
            if hasattr(self, 'controls'):
                self.controls.hide()
            if hasattr(self, 'habitat_bar_frame'):
                self.habitat_bar_frame.hide()
            if hasattr(self, 'controller_guide_bar'):
                self.controller_guide_bar.show()
            if hasattr(self, 'main_layout'):
                self.main_layout.setContentsMargins(0, 0, 0, 0)
                self.main_layout.setSpacing(0)
            if hasattr(self, 'cards_scroll'):
                self.cards_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
            if hasattr(self, 'dexnav_l_hint'):
                self.dexnav_l_hint.show()
            if hasattr(self, 'dexnav_r_hint'):
                self.dexnav_r_hint.show()
            if hasattr(self, 'map_widget'):
                self.map_widget.set_retro_mode(True)

            if hasattr(self, 'header_frame'):
                self.header_frame.setStyleSheet("""
                    QFrame#top_header_bar {
                        background-color: #10262e;
                        border-top: 3px solid #58b8a8;
                        border-left: 3px solid #58b8a8;
                        border-bottom: 3px solid #081820;
                        border-right: 3px solid #081820;
                        border-radius: 4px;
                        padding: 6px 14px;
                    }
                """)
                self.app_title.setText("🎮 POKéNAV ADVANCE // QUETZAL COMPANION")
                self.app_title.setStyleSheet("color: #00ff88; font-family: 'JetBrainsMono Nerd Font', 'UbuntuMono Nerd Font', monospace; font-size: 14px; font-weight: bold; letter-spacing: 1px;")
                self.subtitle.setText("DEVON CORP. POKéNAV EMERALD OS // HOENN DUAL-DEX SYSTEM")
                self.subtitle.setStyleSheet("color: #58b8a8; font-family: 'JetBrainsMono Nerd Font', 'UbuntuMono Nerd Font', monospace; font-size: 10px; font-weight: bold;")

                self.power_led.setVisible(True)
                self.power_led.setStyleSheet("color: #00ff66; font-family: 'JetBrainsMono Nerd Font', 'UbuntuMono Nerd Font', monospace; font-size: 11px; font-weight: bold; background: #062214; border: 1.5px solid #00e858; border-radius: 3px; padding: 2px 7px;")

                self.battery_badge.setVisible(True)
                self.battery_badge.setText("🔋 BATTERY: FULL [■■■]")
                self.battery_badge.setStyleSheet("color: #f8b800; font-family: 'JetBrainsMono Nerd Font', 'UbuntuMono Nerd Font', monospace; font-size: 11px; font-weight: bold; background: #261c06; border: 1.5px solid #f8b800; border-radius: 3px; padding: 2px 7px;")

                self.save_status_lbl.setStyleSheet("color: #f8f8f8; font-family: 'JetBrainsMono Nerd Font', 'UbuntuMono Nerd Font', monospace; font-size: 11px; font-weight: bold;")
                self.live_watcher_badge.setStyleSheet("color: #00ff88; font-family: 'JetBrainsMono Nerd Font', 'UbuntuMono Nerd Font', monospace; font-size: 10px; font-weight: bold;")

                self.theme_btn.setText("🎮 PokéNav GBA")
                self.theme_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #0d3824;
                        border-top: 2px solid #00ff88;
                        border-left: 2px solid #00ff88;
                        border-bottom: 2px solid #081820;
                        border-right: 2px solid #081820;
                        color: #00ff88;
                        font-family: 'JetBrainsMono Nerd Font', 'UbuntuMono Nerd Font', monospace;
                        font-weight: bold;
                        font-size: 11px;
                        padding: 4px 12px;
                        border-radius: 3px;
                    }
                    QPushButton:hover {
                        background-color: #124d32;
                        color: #ffffff;
                    }
                    QPushButton:pressed {
                        border-top: 2px solid #081820;
                        border-left: 2px solid #081820;
                        border-bottom: 2px solid #00ff88;
                        border-right: 2px solid #00ff88;
                        padding-top: 6px; padding-left: 14px;
                    }
                """)
                self.sync_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #183844;
                        border-top: 2px solid #58b8a8;
                        border-left: 2px solid #58b8a8;
                        border-bottom: 2px solid #081820;
                        border-right: 2px solid #081820;
                        color: #f8f8f8;
                        font-family: monospace;
                        font-weight: bold;
                        font-size: 11px;
                        padding: 4px 12px;
                        border-radius: 3px;
                    }
                    QPushButton:hover {
                        background-color: #245060;
                        color: #00ff88;
                    }
                    QPushButton:pressed {
                        border-top: 2px solid #081820;
                        border-left: 2px solid #081820;
                        border-bottom: 2px solid #58b8a8;
                        border-right: 2px solid #58b8a8;
                        padding-top: 6px; padding-left: 14px;
                    }
                """)
                self.start_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #3b1414;
                        border-top: 2px solid #ef4444;
                        border-left: 2px solid #ef4444;
                        border-bottom: 2px solid #081820;
                        border-right: 2px solid #081820;
                        color: #ff9ca5;
                        font-family: 'JetBrainsMono Nerd Font', 'UbuntuMono Nerd Font', monospace;
                        font-weight: bold;
                        font-size: 11px;
                        padding: 4px 12px;
                        border-radius: 3px;
                    }
                    QPushButton:hover {
                        background-color: #5c1e1e;
                        color: #ffffff;
                    }
                    QPushButton:pressed {
                        border-top: 2px solid #081820;
                        border-left: 2px solid #081820;
                        border-bottom: 2px solid #ef4444;
                        border-right: 2px solid #ef4444;
                        padding-top: 6px; padding-left: 14px;
                    }
                """)

            if hasattr(self, 'controls'):
                self.controls.setStyleSheet("""
                    QFrame#top_controls {
                        background-color: #10262e;
                        border-top: 2px solid #58b8a8;
                        border-left: 2px solid #58b8a8;
                        border-bottom: 2px solid #081820;
                        border-right: 2px solid #081820;
                        border-radius: 4px;
                    }
                """)
            if hasattr(self, 'prev_route_btn'):
                arrow_style = """
                    QPushButton {
                        background-color: #183844;
                        border-top: 2px solid #58b8a8;
                        border-left: 2px solid #58b8a8;
                        border-bottom: 2px solid #081820;
                        border-right: 2px solid #081820;
                        color: #00ff88;
                        font-size: 12px;
                        font-weight: bold;
                        border-radius: 2px;
                    }
                    QPushButton:hover {
                        background-color: #245060;
                        color: #ffffff;
                    }
                """
                self.prev_route_btn.setStyleSheet(arrow_style)
                self.next_route_btn.setStyleSheet(arrow_style)

            if hasattr(self, 'p_header'):
                self.p_header.setStyleSheet("""
                    background-color: #10262e;
                    border-top: 2px solid #58b8a8;
                    border-left: 2px solid #58b8a8;
                    border-bottom: 2px solid #081820;
                    border-right: 2px solid #081820;
                    border-radius: 4px;
                    padding: 8px 14px;
                """)

            if hasattr(self, 'leg_cards_scroll'):
                self.leg_cards_scroll.setStyleSheet("""
                    background-color: #08151c;
                    border-top: 2px solid #58b8a8;
                    border-left: 2px solid #58b8a8;
                    border-bottom: 2px solid #081820;
                    border-right: 2px solid #081820;
                    border-radius: 4px;
                """)

            if hasattr(self, 'hero_card'):
                self.hero_card.setStyleSheet("""
                    background-color: #10262e;
                    border-top: 2px solid #58b8a8;
                    border-left: 2px solid #58b8a8;
                    border-bottom: 2px solid #081820;
                    border-right: 2px solid #081820;
                    border-radius: 4px;
                    padding: 10px 14px;
                """)
            if hasattr(self, 'bp_frame'):
                self.bp_frame.setStyleSheet("""
                    background-color: #09171e;
                    border-top: 2px solid #040a0c;
                    border-left: 2px solid #040a0c;
                    border-bottom: 2px solid #387068;
                    border-right: 2px solid #387068;
                    border-radius: 3px;
                    padding: 12px;
                """)
            if hasattr(self, 'calc_card'):
                self.calc_card.setStyleSheet("""
                    QFrame#calc_card {
                        background-color: #10262e;
                        border-top: 2px solid #58b8a8;
                        border-left: 2px solid #58b8a8;
                        border-bottom: 2px solid #081820;
                        border-right: 2px solid #081820;
                        border-radius: 4px;
                    }
                """)
            if hasattr(self, 'calc_btn'):
                self.calc_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #183844;
                        border-top: 2px solid #58b8a8;
                        border-left: 2px solid #58b8a8;
                        border-bottom: 2px solid #081820;
                        border-right: 2px solid #081820;
                        color: #00ff88;
                        font-family: monospace;
                        font-weight: bold;
                        font-size: 12px;
                        border-radius: 2px;
                        padding: 6px 14px;
                    }
                    QPushButton:hover {
                        background-color: #245060;
                        color: #ffffff;
                    }
                    QPushButton:pressed {
                        border-top: 2px solid #081820;
                        border-left: 2px solid #081820;
                        border-bottom: 2px solid #58b8a8;
                        border-right: 2px solid #58b8a8;
                        padding-top: 8px; padding-left: 16px;
                    }
                """)
        else:
            self.setStyleSheet(MODERN_STYLESHEET)
            self.setWindowTitle("⚡ Pokémon Quetzal Master Companion & Strategy Hub")

            if hasattr(self, 'tabs') and self.tabs.tabBar():
                self.tabs.tabBar().show()
            if hasattr(self, 'header_frame'):
                self.header_frame.show()
            if hasattr(self, 'controls'):
                self.controls.show()
            if hasattr(self, 'habitat_bar_frame'):
                self.habitat_bar_frame.show()
            if hasattr(self, 'controller_guide_bar'):
                self.controller_guide_bar.hide()
            if hasattr(self, 'main_layout'):
                self.main_layout.setContentsMargins(12, 10, 12, 12)
                self.main_layout.setSpacing(8)
            if hasattr(self, 'cards_scroll'):
                self.cards_scroll.setStyleSheet("")
            if hasattr(self, 'dexnav_l_hint'):
                self.dexnav_l_hint.hide()
            if hasattr(self, 'dexnav_r_hint'):
                self.dexnav_r_hint.hide()
            if hasattr(self, 'map_widget'):
                self.map_widget.set_retro_mode(False)

            if hasattr(self, 'header_frame'):
                self.header_frame.setStyleSheet("""
                    QFrame#top_header_bar {
                        background-color: #0f172a;
                        border: 1px solid #1e293b;
                        border-radius: 8px;
                        padding: 6px 14px;
                    }
                """)
                self.app_title.setText("⚡ QUETZAL MASTER COMPANION")
                self.app_title.setStyleSheet("color: #38bdf8; font-family: sans-serif; font-size: 15px; font-weight: bold; letter-spacing: 0.5px;")
                self.subtitle.setText("Gen 1–9 Multi-Region DexNav & Strategic Guide")
                self.subtitle.setStyleSheet("color: #64748b; font-size: 11px; font-family: sans-serif;")

                self.power_led.setVisible(False)
                self.battery_badge.setVisible(False)

                self.save_status_lbl.setStyleSheet("color: #f1f5f9; font-family: sans-serif; font-size: 12px; font-weight: bold;")
                self.live_watcher_badge.setStyleSheet("color: #10b981; font-family: sans-serif; font-size: 10px; font-weight: bold;")

                self.theme_btn.setText("⚡ Cyber Modern")
                self.theme_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #1e293b;
                        border: 1px solid #38bdf8;
                        color: #38bdf8;
                        font-family: sans-serif;
                        font-weight: bold;
                        font-size: 11px;
                        border-radius: 4px;
                        padding: 4px 12px;
                    }
                    QPushButton:hover {
                        background-color: #253550;
                    }
                """)
                self.sync_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #1e3a8a;
                        border: 1px solid #3b82f6;
                        color: #FFFFFF;
                        font-weight: bold;
                        border-radius: 4px;
                        padding: 4px 12px;
                    }
                    QPushButton:hover { background-color: #2563eb; }
                """)
                self.start_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #991b1b;
                        border: 1px solid #ef4444;
                        color: #FFFFFF;
                        font-family: sans-serif;
                        font-weight: bold;
                        border-radius: 4px;
                        padding: 4px 12px;
                    }
                    QPushButton:hover { background-color: #b91c1c; }
                """)

            if hasattr(self, 'controls'):
                self.controls.setStyleSheet("""
                    QFrame#top_controls {
                        background-color: #0f172a;
                        border: 1px solid #1e293b;
                        border-radius: 6px;
                    }
                """)
            if hasattr(self, 'prev_route_btn'):
                arrow_style = """
                    QPushButton {
                        background-color: #1e293b;
                        color: #f1f5f9;
                        font-size: 13px;
                        font-weight: bold;
                        border: 1px solid #334155;
                        border-radius: 4px;
                        padding: 0px;
                    }
                    QPushButton:hover {
                        background-color: #334155;
                        color: #38bdf8;
                    }
                """
                self.prev_route_btn.setStyleSheet(arrow_style)
                self.next_route_btn.setStyleSheet(arrow_style)

            if hasattr(self, 'p_header'):
                self.p_header.setStyleSheet("""
                    background-color: #0f172a;
                    border: 1px solid #1e293b;
                    border-radius: 8px;
                    padding: 8px 14px;
                """)

            if hasattr(self, 'leg_cards_scroll'):
                self.leg_cards_scroll.setStyleSheet("""
                    background-color: #0b0f17;
                    border: 1px solid #1e293b;
                    border-radius: 8px;
                """)

            if hasattr(self, 'hero_card'):
                self.hero_card.setStyleSheet("""
                    background-color: #0f172a;
                    border: 1px solid #1e293b;
                    border-radius: 8px;
                    padding: 10px 14px;
                """)
            if hasattr(self, 'bp_frame'):
                self.bp_frame.setStyleSheet("""
                    background-color: #0c121d;
                    border: 1.5px solid #0284c7;
                    border-radius: 8px;
                    padding: 12px;
                """)
            if hasattr(self, 'calc_card'):
                self.calc_card.setStyleSheet("""
                    QFrame#calc_card {
                        background-color: #0f172a;
                        border: 1px solid #1e293b;
                        border-radius: 8px;
                    }
                """)
            if hasattr(self, 'calc_btn'):
                self.calc_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #2563eb;
                        color: #FFFFFF;
                        font-weight: bold;
                        border-radius: 6px;
                    }
                    QPushButton:hover {
                        background-color: #3b82f6;
                    }
                """)

        self.update_filter_button_styles()
        self.update_habitat_button_styles()
        self.update_route_completion_badge()
        if hasattr(self, 'update_trainer_cat_button_styles'):
            self.update_trainer_cat_button_styles()
        if hasattr(self, 'update_leg_filter_button_styles'):
            self.update_leg_filter_button_styles()
        if hasattr(self, 'pokedex_caught_btn'):
            pid = getattr(self, 'current_pokedex_mon_id', 1)
            self.update_pokedex_caught_btn(pid in self.caught_species)
        if hasattr(self, 'pk_stat_bars'):
            for stat, (bar, val) in self.pk_stat_bars.items():
                if self.current_theme == "retro":
                    bar.setStyleSheet("""
                        QProgressBar {
                            background-color: #081418;
                            border-top: 1px solid #040a0c;
                            border-left: 1px solid #040a0c;
                            border-bottom: 1px solid #285462;
                            border-right: 1px solid #285462;
                            border-radius: 2px;
                        }
                        QProgressBar::chunk {
                            background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #00ff68, stop:0.5 #00e858, stop:1 #009838);
                            border-radius: 1px;
                        }
                    """)
                    val.setStyleSheet("color: #00ff88; font-family: monospace; font-size: 11px; font-weight: bold;")
                else:
                    bar.setStyleSheet("""
                        QProgressBar { background-color: #1e293b; border-radius: 6px; }
                        QProgressBar::chunk { background-color: #3b82f6; border-radius: 6px; }
                    """)
                    val.setStyleSheet("color: #f8fafc; font-weight: bold;")

        if hasattr(self, 'water_box'):
            for b in [self.water_box, self.land_box, self.beach_box, self.hidden_box]:
                b.apply_theme(self.current_theme)
        if hasattr(self, 'dexnav_route_header'):
            self.update_dexnav_header_theme()
        if hasattr(self, 'inspector_drawer'):
            self.inspector_drawer.apply_theme(self.current_theme)
        if hasattr(self, 'leg_inspector_drawer'):
            self.leg_inspector_drawer.apply_theme(self.current_theme)
        for c in getattr(self, 'all_rendered_cards', []):
            c.update_card_style()
            c.update_caught_button_state()
        for c in getattr(self, 'rendered_leg_cards', []):
            c.update_card_style()
            c.update_caught_button_state()

    def update_route_completion_badge(self):
        if not hasattr(self, 'route_progress_badge'):
            return
        total_unique = len(set(d["species_id"] for d in getattr(self, 'current_route_data', [])))
        caught_unique = len(set(d["species_id"] for d in getattr(self, 'current_route_data', []) if d.get("is_caught", False)))
        pct = (caught_unique / total_unique * 100) if total_unique > 0 else 0
        route = getattr(self, 'current_route_name', 'Current Route')

        if total_unique == 0:
            self.route_progress_badge.setText(f"{route}: Safe Town (No Wild Encounters)")
            if is_retro():
                self.route_progress_badge.setStyleSheet("background-color: #0d1e24; color: #6a9c90; border-top: 2px solid #3d7870; border-left: 2px solid #3d7870; border-bottom: 2px solid #081820; border-right: 2px solid #081820; border-radius: 2px; padding: 4px 10px; font-weight: bold; font-family: monospace;")
            else:
                self.route_progress_badge.setStyleSheet("background-color: #0f172a; color: #94a3b8; border: 1px solid #334155; border-radius: 4px; padding: 4px 10px; font-weight: bold;")
        else:
            self.route_progress_badge.setText(f"{route}: {caught_unique} / {total_unique} Caught ({pct:.1f}%)")
            if is_retro():
                if total_unique > 0 and caught_unique >= total_unique:
                    self.route_progress_badge.setStyleSheet("background-color: #0d3824; color: #00ff88; border-top: 2px solid #00ff88; border-left: 2px solid #00ff88; border-bottom: 2px solid #081820; border-right: 2px solid #081820; border-radius: 2px; padding: 4px 10px; font-weight: bold; font-family: monospace;")
                else:
                    self.route_progress_badge.setStyleSheet("background-color: #261c06; color: #f8b800; border-top: 2px solid #f8b800; border-left: 2px solid #f8b800; border-bottom: 2px solid #081820; border-right: 2px solid #081820; border-radius: 2px; padding: 4px 10px; font-weight: bold; font-family: monospace;")
            else:
                if total_unique > 0 and caught_unique >= total_unique:
                    self.route_progress_badge.setStyleSheet("background-color: #064e3b; color: #34d399; border: 1px solid #10b981; border-radius: 4px; padding: 4px 10px; font-weight: bold;")
                else:
                    self.route_progress_badge.setStyleSheet("background-color: #1e293b; color: #facc15; border: 1px solid #eab308; border-radius: 4px; padding: 4px 10px; font-weight: bold;")

    # ==========================================
    # TAB 0: ROUTE ENCOUNTER EXPLORER
    # ==========================================
    def create_encounter_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Top Controls Bar
        self.controls = QFrame()
        self.controls.setObjectName("top_controls")
        c_layout = QHBoxLayout(self.controls)
        c_layout.setContentsMargins(10, 6, 10, 6)
        c_layout.setSpacing(10)

        # Region Selector
        c_layout.addWidget(QLabel("Region:"))
        self.region_combo = QComboBox()
        self.region_combo.addItems(["Hoenn", "Johto", "Kanto", "Sevii Islands", "All Regions"])
        self.region_combo.currentIndexChanged.connect(self.on_region_changed)
        c_layout.addWidget(self.region_combo)

        # Route Selector
        c_layout.addWidget(QLabel("Location:"))
        arrow_btn_style = """
            QPushButton {
                background-color: #1e293b;
                color: #f1f5f9;
                font-size: 13px;
                font-weight: bold;
                border: 1px solid #334155;
                border-radius: 4px;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: #334155;
                color: #38bdf8;
            }
        """
        self.prev_route_btn = QPushButton("<")
        self.prev_route_btn.setFixedSize(28, 28)
        self.prev_route_btn.setStyleSheet(arrow_btn_style)
        self.prev_route_btn.setToolTip("Previous Location")
        self.prev_route_btn.clicked.connect(self.on_prev_route)
        c_layout.addWidget(self.prev_route_btn)

        self.route_combo = QComboBox()
        self.route_combo.setMinimumWidth(200)
        self.route_combo.currentIndexChanged.connect(self.on_route_changed)
        c_layout.addWidget(self.route_combo)

        self.next_route_btn = QPushButton(">")
        self.next_route_btn.setFixedSize(28, 28)
        self.next_route_btn.setStyleSheet(arrow_btn_style)
        self.next_route_btn.setToolTip("Next Location")
        self.next_route_btn.clicked.connect(self.on_next_route)
        c_layout.addWidget(self.next_route_btn)

        # Route Completion Progress Badge
        self.route_progress_badge = QLabel("Route Completion: 0 / 0 (0%)")
        self.route_progress_badge.setStyleSheet("""
            background-color: #064e3b;
            color: #34d399;
            border: 1px solid #059669;
            border-radius: 4px;
            padding: 4px 10px;
            font-size: 11px;
            font-weight: bold;
        """)
        c_layout.addWidget(self.route_progress_badge)

        c_layout.addStretch()

        # Filter Pills: All / Missing / Caught
        c_layout.addWidget(QLabel("Filter:"))
        self.btn_filter_all = QPushButton("Show All")
        self.btn_filter_uncaught = QPushButton("○ Missing Only")
        self.btn_filter_caught = QPushButton("✓ Caught Only")

        self.filter_buttons = [self.btn_filter_all, self.btn_filter_uncaught, self.btn_filter_caught]
        for btn, mode in zip(self.filter_buttons, ["Show All", "Missing Only", "Caught Only"]):
            btn.setCheckable(True)
            btn.setFixedHeight(26)
            btn.setCursor(QCursor(Qt.PointingHandCursor))
            btn.clicked.connect(lambda checked, m=mode: self.set_caught_filter(m))
            c_layout.addWidget(btn)

        self.update_filter_button_styles()

        layout.addWidget(self.controls)

        # Habitat Filter Pills
        self.habitat_bar_frame = QFrame()
        habitat_bar = QHBoxLayout(self.habitat_bar_frame)
        habitat_bar.setContentsMargins(0, 0, 0, 0)
        habitat_bar.setSpacing(6)
        habitat_bar.addWidget(QLabel("Habitat:"))

        self.hab_buttons = {}
        for hab, icon in [("All", "🌐"), ("Land", "🌿"), ("Water", "🌊"), ("Beach", "🏖️"), ("Rock", "🪨"), ("Fishing", "🎣"), ("Hidden", "🔍")]:
            btn = QPushButton(f"{icon} {hab}")
            btn.setFixedHeight(24)
            btn.setCheckable(True)
            btn.setCursor(QCursor(Qt.PointingHandCursor))
            btn.clicked.connect(lambda checked, h=hab: self.set_habitat_filter(h))
            habitat_bar.addWidget(btn)
            self.hab_buttons[hab] = btn

        self.hab_buttons["All"].setChecked(True)
        self.update_habitat_button_styles()
        habitat_bar.addStretch()

        # Species Search Filter
        self.route_mon_search = QLineEdit()
        self.route_mon_search.setPlaceholderText("Filter Pokémon on this route...")
        self.route_mon_search.setFixedWidth(220)
        self.route_mon_search.textChanged.connect(self.filter_route_cards)
        habitat_bar.addWidget(self.route_mon_search)

        layout.addWidget(self.habitat_bar_frame)

        # Splitter: DexNav Route Screen (Left) | DexNav Telemetry Inspector (Right)
        splitter = QSplitter(Qt.Horizontal)

        self.cards_scroll = QScrollArea()
        self.cards_scroll.setWidgetResizable(True)
        self.cards_container = DexNavRetroBackgroundWidget()
        self.cards_grid = QGridLayout(self.cards_container)
        self.cards_grid.setContentsMargins(12, 8, 12, 10)
        self.cards_grid.setSpacing(10)
        self.cards_scroll.setWidget(self.cards_container)
        splitter.addWidget(self.cards_scroll)

        # DexNav Route Header & Search Top Bar
        self.dexnav_top_bar = QWidget()
        self.dexnav_top_bar.setFixedHeight(36)
        top_bar_layout = QHBoxLayout(self.dexnav_top_bar)
        top_bar_layout.setContentsMargins(8, 2, 8, 2)

        self.dexnav_search_lbl = QLabel("SEARCH  POKéMON")
        self.dexnav_search_lbl.setStyleSheet("""
            color: #ffffff;
            font-family: 'JetBrainsMono Nerd Font', 'UbuntuMono Nerd Font', monospace;
            font-size: 15px;
            font-weight: 900;
            letter-spacing: 1.5px;
        """)
        top_bar_layout.addWidget(self.dexnav_search_lbl)

        top_bar_layout.addStretch()

        self.dexnav_l_hint = QLabel("◀ [L]")
        self.dexnav_l_hint.setStyleSheet("color: rgba(255, 255, 255, 0.75); font-family: monospace; font-size: 12px; font-weight: bold;")
        top_bar_layout.addWidget(self.dexnav_l_hint)

        self.dexnav_route_header = QLabel("ROUTE 101")
        self.dexnav_route_header.setAlignment(Qt.AlignCenter)
        self.dexnav_route_header.setStyleSheet("""
            color: #ffffff;
            font-family: 'JetBrainsMono Nerd Font', 'UbuntuMono Nerd Font', monospace;
            font-size: 15px;
            font-weight: 900;
            letter-spacing: 2px;
            padding: 0 8px;
        """)
        top_bar_layout.addWidget(self.dexnav_route_header)

        self.dexnav_r_hint = QLabel("[R] ▶")
        self.dexnav_r_hint.setStyleSheet("color: rgba(255, 255, 255, 0.75); font-family: monospace; font-size: 12px; font-weight: bold;")
        top_bar_layout.addWidget(self.dexnav_r_hint)

        self.cards_grid.addWidget(self.dexnav_top_bar, 0, 0, 1, 2)

        # Habitat Box 1: WATER (5 slots)
        self.water_box = DexNavHabitatBoxWidget("WATER", "🌊", "#3b82f6", total_slots=5, columns=5)
        self.water_box.slot_clicked.connect(self.on_encounter_card_clicked)
        self.water_box.catch_toggled.connect(self.on_encounter_catch_toggled)
        self.cards_grid.addWidget(self.water_box, 1, 0, 1, 2)

        # Habitat Box 2: LAND (12 slots: 6 columns x 2 rows)
        self.land_box = DexNavHabitatBoxWidget("LAND", "🌿", "#22c55e", total_slots=12, columns=6)
        self.land_box.slot_clicked.connect(self.on_encounter_card_clicked)
        self.land_box.catch_toggled.connect(self.on_encounter_catch_toggled)
        self.cards_grid.addWidget(self.land_box, 2, 0, 1, 2)

        # Habitat Boxes 3 & 4: BEACH (3 slots) and HIDDEN (1 slot) side by side
        self.bottom_habitats_container = QWidget()
        b_layout = QHBoxLayout(self.bottom_habitats_container)
        b_layout.setContentsMargins(0, 0, 0, 0)
        b_layout.setSpacing(8)

        self.beach_box = DexNavHabitatBoxWidget("BEACH", "🏖️", "#f59e0b", total_slots=3, columns=3)
        self.beach_box.slot_clicked.connect(self.on_encounter_card_clicked)
        self.beach_box.catch_toggled.connect(self.on_encounter_catch_toggled)
        b_layout.addWidget(self.beach_box, 3)

        self.hidden_box = DexNavHabitatBoxWidget("HIDDEN", "🔍", "#ef4444", total_slots=1, columns=1)
        self.hidden_box.slot_clicked.connect(self.on_encounter_card_clicked)
        self.hidden_box.catch_toggled.connect(self.on_encounter_catch_toggled)
        b_layout.addWidget(self.hidden_box, 1)

        self.cards_grid.addWidget(self.bottom_habitats_container, 3, 0, 1, 2)

        # Empty Peaceful Town Label
        self.empty_peaceful_lbl = QLabel("No wild Pokémon encounters in this peaceful town.")
        self.empty_peaceful_lbl.setAlignment(Qt.AlignCenter)
        self.empty_peaceful_lbl.setStyleSheet("color: #94a3b8; font-size: 14px; font-weight: bold; padding: 40px;")
        self.empty_peaceful_lbl.hide()
        self.cards_grid.addWidget(self.empty_peaceful_lbl, 4, 0, 1, 2)

        # Right Inspector Drawer
        self.inspector_drawer = SpeciesInspectorDrawer()
        self.inspector_drawer.open_in_pokedex.connect(self.jump_to_pokedex_mon)
        self.inspector_drawer.catch_toggled.connect(self.on_encounter_catch_toggled)
        splitter.addWidget(self.inspector_drawer)

        splitter.setStretchFactor(0, 7)
        splitter.setStretchFactor(1, 3)
        layout.addWidget(splitter, 1)

        self.update_dexnav_header_theme()
        self.tabs.addTab(tab, "🗺️ Route Encounters")

        self.populate_route_list()

    def set_caught_filter(self, mode: str):
        play_sfx("menu_select.wav")
        self.filter_mode = mode
        self.update_filter_button_styles()
        self.filter_route_cards()

    def update_filter_button_styles(self):
        for btn, mode in zip(self.filter_buttons, ["Show All", "Missing Only", "Caught Only"]):
            active = (mode == self.filter_mode)
            btn.setChecked(active)
            if is_retro():
                if active:
                    btn.setStyleSheet("""
                        QPushButton {
                            background-color: #008850;
                            border-top: 2px solid #00ff88;
                            border-left: 2px solid #00ff88;
                            border-bottom: 2px solid #042010;
                            border-right: 2px solid #042010;
                            color: #ffffff;
                            font-weight: bold;
                            font-family: monospace;
                            border-radius: 2px;
                            padding: 3px 10px;
                        }
                    """)
                else:
                    btn.setStyleSheet("""
                        QPushButton {
                            background-color: #0c1c22;
                            border-top: 2px solid #306056;
                            border-left: 2px solid #306056;
                            border-bottom: 2px solid #050e12;
                            border-right: 2px solid #050e12;
                            color: #6a9c90;
                            font-family: monospace;
                            border-radius: 2px;
                            padding: 3px 10px;
                        }
                        QPushButton:hover { background-color: #143038; color: #a8d8c8; }
                        QPushButton:pressed {
                            border-top: 2px solid #050e12;
                            border-left: 2px solid #050e12;
                            border-bottom: 2px solid #306056;
                            border-right: 2px solid #306056;
                        }
                    """)
            else:
                if active:
                    btn.setStyleSheet("""
                        QPushButton {
                            background-color: #2563eb;
                            border: 1px solid #60a5fa;
                            color: #FFFFFF;
                            font-weight: bold;
                            border-radius: 4px;
                            padding: 3px 10px;
                        }
                    """)
                else:
                    btn.setStyleSheet("""
                        QPushButton {
                            background-color: #1e293b;
                            border: 1px solid #334155;
                            color: #94a3b8;
                            border-radius: 4px;
                            padding: 3px 10px;
                        }
                        QPushButton:hover { background-color: #334155; color: #FFFFFF; }
                    """)

    def set_habitat_filter(self, hab: str):
        play_sfx("menu_select.wav")
        self.habitat_filter = hab
        self.update_habitat_button_styles()
        self.filter_route_cards()

    def update_habitat_button_styles(self):
        for hab, btn in self.hab_buttons.items():
            active = (hab == self.habitat_filter)
            btn.setChecked(active)
            if is_retro():
                if active:
                    btn.setStyleSheet("""
                        QPushButton {
                            background-color: #185468;
                            border-top: 2px solid #58f8e8;
                            border-left: 2px solid #58f8e8;
                            border-bottom: 2px solid #081820;
                            border-right: 2px solid #081820;
                            color: #ffffff;
                            font-weight: bold;
                            font-family: monospace;
                            border-radius: 2px;
                            padding: 2px 8px;
                            font-size: 11px;
                        }
                    """)
                else:
                    btn.setStyleSheet("""
                        QPushButton {
                            background-color: #0c1c22;
                            border-top: 2px solid #306056;
                            border-left: 2px solid #306056;
                            border-bottom: 2px solid #050e12;
                            border-right: 2px solid #050e12;
                            color: #6a9c90;
                            font-family: monospace;
                            border-radius: 2px;
                            padding: 2px 8px;
                            font-size: 11px;
                        }
                        QPushButton:hover { background-color: #143038; color: #a8d8c8; }
                        QPushButton:pressed {
                            border-top: 2px solid #050e12;
                            border-left: 2px solid #050e12;
                            border-bottom: 2px solid #306056;
                            border-right: 2px solid #306056;
                        }
                    """)
            else:
                if active:
                    btn.setStyleSheet("""
                        QPushButton {
                            background-color: #0284c7;
                            border: 1px solid #38bdf8;
                            color: #FFFFFF;
                            font-weight: bold;
                            border-radius: 4px;
                            padding: 2px 8px;
                            font-size: 11px;
                        }
                    """)
                else:
                    btn.setStyleSheet("""
                        QPushButton {
                            background-color: #1e293b;
                            border: 1px solid #334155;
                            color: #94a3b8;
                            border-radius: 4px;
                            padding: 2px 8px;
                            font-size: 11px;
                        }
                        QPushButton:hover { background-color: #334155; color: #FFFFFF; }
                    """)

    def populate_route_list(self):
        reg = self.region_combo.currentText()
        sql = "SELECT DISTINCT location_name FROM encounters"
        params = []
        if reg != "All Regions":
            sql += " WHERE region = ?"
            params.append(reg)
        sql += " ORDER BY location_name ASC"

        self.cur.execute(sql, params)
        routes = [r[0] for r in self.cur.fetchall()]

        # Also include regional map nodes (e.g. peaceful towns with 0 wild encounters)
        if reg in REGIONAL_MAP_DATA:
            map_nodes = [normalize_loc(n) for n in REGIONAL_MAP_DATA[reg].get("nodes", {}).keys()]
            for mn in map_nodes:
                if mn not in routes:
                    routes.append(mn)
            routes.sort()
        elif reg == "All Regions":
            for r_key in REGIONAL_MAP_DATA:
                for n in REGIONAL_MAP_DATA[r_key].get("nodes", {}).keys():
                    mn = normalize_loc(n)
                    if mn not in routes:
                        routes.append(mn)
            routes.sort()

        self.route_combo.blockSignals(True)
        self.route_combo.clear()
        for r in routes:
            self.route_combo.addItem(r)

        # Default select
        if reg == "Johto" and "ROUTE 29" in routes:
            self.route_combo.setCurrentText("ROUTE 29")
        elif "ROUTE 101" in routes:
            self.route_combo.setCurrentText("ROUTE 101")
        elif routes:
            self.route_combo.setCurrentIndex(0)

        self.route_combo.blockSignals(False)
        self.load_current_route_encounters()

    def on_region_changed(self):
        play_sfx("menu_select.wav")
        self.populate_route_list()

    def on_prev_route(self):
        play_sfx("menu_select.wav")
        idx = self.route_combo.currentIndex()
        if idx > 0:
            self.route_combo.setCurrentIndex(idx - 1)

    def on_next_route(self):
        play_sfx("menu_select.wav")
        idx = self.route_combo.currentIndex()
        if idx < self.route_combo.count() - 1:
            self.route_combo.setCurrentIndex(idx + 1)

    def on_route_changed(self):
        play_sfx("menu_select.wav")
        self.load_current_route_encounters()

    def update_dexnav_header_theme(self):
        if not hasattr(self, "dexnav_route_header"):
            return
        route = getattr(self, "current_route_name", "ROUTE 101")
        self.dexnav_route_header.setText(f"{route.upper()}")
        if is_retro():
            self.dexnav_route_header.setStyleSheet("""
                background-color: #10262e;
                border-top: 2px solid #58b8a8;
                border-left: 2px solid #58b8a8;
                border-bottom: 2px solid #081820;
                border-right: 2px solid #081820;
                color: #00ff88;
                font-family: 'JetBrainsMono Nerd Font', 'UbuntuMono Nerd Font', monospace;
                font-size: 13px;
                font-weight: bold;
                letter-spacing: 2px;
                border-radius: 4px;
                padding: 4px;
            """)
        else:
            self.dexnav_route_header.setStyleSheet("""
                background-color: #0f172a;
                border: 1px solid #1e293b;
                color: #38bdf8;
                font-size: 13px;
                font-weight: bold;
                letter-spacing: 1px;
                border-radius: 6px;
                padding: 4px;
            """)

    def select_species_in_habitat_boxes(self, species_id: int):
        for box in [self.water_box, self.land_box, self.beach_box, self.hidden_box]:
            box.select_species(species_id)

    def load_current_route_encounters(self):
        route = self.route_combo.currentText()
        if not route:
            return
        self.current_route_name = route
        reg = self.region_combo.currentText()

        sql = """
            SELECT e.method, e.slot, e.chance, e.min_level, e.max_level, e.species_id, e.species_name,
                   p.type1, p.type2, p.abilities, p.hidden_ability, p.held_items,
                   p.hp, p.atk, p.def, p.spa, p.spd, p.spe, p.bst, p.catch_rate,
                   p.national_dex_num
            FROM encounters e
            LEFT JOIN pokemon p ON e.species_id = p.id
            WHERE e.location_name = ?
        """
        params = [route]
        if reg != "All Regions":
            sql += " AND e.region = ?"
            params.append(reg)
        sql += " ORDER BY e.method, e.slot ASC"

        self.cur.execute(sql, params)
        rows = self.cur.fetchall()

        self.current_route_data = []
        seen_keys = set()
        for r in rows:
            key = (r[0], r[1])
            if key in seen_keys:
                continue
            seen_keys.add(key)

            nat_dex = r[20] if len(r) > 20 and r[20] is not None else self.sp_to_nat.get(r[5], r[5])
            base_id = self.nat_base_species.get(nat_dex, r[5])
            form_badge = get_form_badge(r[5], nat_dex, base_id, r[7], r[8])

            d = {
                "method": r[0], "slot": r[1], "chance": r[2], "min_level": r[3], "max_level": r[4],
                "species_id": r[5], "species_name": r[6], "type1": r[7], "type2": r[8],
                "abilities": r[9], "hidden_ability": r[10], "held_items": r[11],
                "hp": r[12], "atk": r[13], "def": r[14], "spa": r[15], "spd": r[16], "spe": r[17],
                "bst": r[18], "catch_rate": r[19],
                "national_dex_num": nat_dex,
                "form_badge": form_badge,
                "is_caught": r[5] in self.caught_species
            }
            self.current_route_data.append(d)

        self.update_dexnav_header_theme()
        self.update_route_completion_badge()

        # Split by habitat
        water_mons = [d for d in self.current_route_data if "Surfing" in d.get("method", "")]
        land_mons = [d for d in self.current_route_data if "Grass" in d.get("method", "")]
        beach_mons = [d for d in self.current_route_data if "Beach" in d.get("method", "")]
        hidden_mons = [d for d in self.current_route_data if "Hidden" in d.get("method", "")]

        self.water_box.populate(water_mons)
        self.land_box.populate(land_mons)
        self.beach_box.populate(beach_mons)
        self.hidden_box.populate(hidden_mons)

        self.all_rendered_cards = [
            s for box in [self.water_box, self.land_box, self.beach_box, self.hidden_box]
            for s in box.slots if s.mon_data
        ]

        if not self.current_route_data:
            self.empty_peaceful_lbl.show()
            self.water_box.hide()
            self.land_box.hide()
            self.bottom_habitats_container.hide()
            self.inspector_drawer.clear()
        else:
            self.empty_peaceful_lbl.hide()
            self.water_box.show()
            self.land_box.show()
            self.bottom_habitats_container.show()
            self.filter_route_cards()
            self.inspector_drawer.populate(self.current_route_data[0])
            self.select_species_in_habitat_boxes(self.current_route_data[0]["species_id"])

    def filter_route_cards(self):
        search_query = self.route_mon_search.text().strip().lower()

        # Apply filter dimming to each habitat box
        for box in [self.water_box, self.land_box, self.beach_box, self.hidden_box]:
            box.apply_filters(self.filter_mode, search_query)

        # Handle habitat visibility pill filters
        if self.habitat_filter == "All":
            self.water_box.show()
            self.land_box.show()
            self.bottom_habitats_container.show()
            self.beach_box.show()
            self.hidden_box.show()
        elif self.habitat_filter == "Water":
            self.water_box.show()
            self.land_box.hide()
            self.bottom_habitats_container.hide()
        elif self.habitat_filter == "Land":
            self.water_box.hide()
            self.land_box.show()
            self.bottom_habitats_container.hide()
        elif self.habitat_filter == "Beach":
            self.water_box.hide()
            self.land_box.hide()
            self.bottom_habitats_container.show()
            self.beach_box.show()
            self.hidden_box.hide()
        elif self.habitat_filter == "Hidden":
            self.water_box.hide()
            self.land_box.hide()
            self.bottom_habitats_container.show()
            self.beach_box.hide()
            self.hidden_box.show()
        else:
            self.water_box.show()
            self.land_box.show()
            self.bottom_habitats_container.show()

    def on_encounter_card_clicked(self, mon_data: dict):
        self.inspector_drawer.populate(mon_data)
        self.select_species_in_habitat_boxes(mon_data["species_id"])

    def on_encounter_catch_toggled(self, species_id: int, species_name: str, is_caught: bool):
        nat_num = self.sp_to_nat.get(species_id, species_id)
        related_ids = self.nat_to_sps.get(nat_num, [species_id])

        if is_caught:
            play_sfx("caught_fanfare.wav")
            for rid in related_ids:
                self.caught_species.add(rid)
                rname = self.sp_to_name.get(rid, species_name)
                self.cur.execute("INSERT OR REPLACE INTO caught_pokemon (species_id, species_name) VALUES (?, ?)", (rid, rname))
                self.cur.execute("INSERT OR REPLACE INTO user_pokedex (species_id, caught, seen) VALUES (?, 1, 1)", (rid,))
        else:
            play_sfx("menu_cancel.wav")
            for rid in related_ids:
                self.caught_species.discard(rid)
                self.cur.execute("DELETE FROM caught_pokemon WHERE species_id = ?", (rid,))
                self.cur.execute("UPDATE user_pokedex SET caught = 0 WHERE species_id = ?", (rid,))
        self.conn.commit()

        # Update in-memory data
        for d in self.current_route_data:
            if d.get("species_id") in related_ids or d.get("national_dex_num") == nat_num:
                d["is_caught"] = is_caught

        for card in self.all_rendered_cards:
            if card.species_id in related_ids or getattr(card, "national_dex_num", None) == nat_num:
                card.is_caught = is_caught
                card.update_card_style(is_selected=card.is_selected)

        # Re-evaluate completion of each habitat box
        for box in [self.water_box, self.land_box, self.beach_box, self.hidden_box]:
            caught_count = sum(1 for s in box.slots if s.mon_data and s.mon_data.get("is_caught"))
            total_avail = sum(1 for s in box.slots if s.mon_data)
            if total_avail == 0:
                box.count_lbl.setText("— EMPTY")
                box.ball_icon.setText("—")
            elif caught_count >= total_avail:
                box.count_lbl.setText(f"✓ {caught_count}/{total_avail} CAUGHT (100%)")
                box.ball_icon.setText("🟡")
            else:
                box.count_lbl.setText(f"○ {caught_count}/{total_avail} CAUGHT")
                box.ball_icon.setText("⚪")

        # Update inspector if currently viewing this mon
        if self.inspector_drawer.current_species_id in related_ids or getattr(self.inspector_drawer, "current_national_dex_num", None) == nat_num:
            self.inspector_drawer.set_caught_state(is_caught)

        # Update summary badge
        pct = (len(self.caught_species) / 1499 * 100) if 1499 > 0 else 0
        if is_retro():
            self.save_status_lbl.setText(f"💾 SAVE: NIG | POKéDEX: {len(self.caught_species)}/1,499 ({pct:.1f}%)")
        else:
            self.save_status_lbl.setText(f"💾 Player: NIG • Caught: {len(self.caught_species)} / 1,499 ({pct:.1f}%)")

        # Update route stats
        self.update_route_completion_badge()

        # Update map widget stats if instantiated
        if hasattr(self, 'map_widget'):
            self.map_widget.load_data_from_db(DB_PATH)

    # ==========================================
    # TAB 1: REGIONAL TOWN MAP
    # ==========================================
    def create_map_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.map_widget = RegionalMapWidget(db_path=DB_PATH)
        self.map_widget.set_retro_mode(self.current_theme == "retro")
        self.map_widget.route_selected.connect(self.on_map_route_selected)
        layout.addWidget(self.map_widget, 1)

        self.tabs.addTab(tab, "📍 Regional Town Map")

    def on_map_route_selected(self, route_name: str, region: str):
        """When user clicks any route on the Town Map, jump straight to Route Encounters tab!"""
        # Switch region if necessary
        r_idx = self.region_combo.findText(region)
        if r_idx >= 0 and self.region_combo.currentIndex() != r_idx:
            self.region_combo.setCurrentIndex(r_idx)

        # Select route
        route_clean = normalize_loc(route_name)
        rt_idx = self.route_combo.findText(route_clean)
        if rt_idx >= 0:
            self.route_combo.setCurrentIndex(rt_idx)
        else:
            # Try partial
            found = False
            for i in range(self.route_combo.count()):
                if route_clean in self.route_combo.itemText(i) or self.route_combo.itemText(i) in route_clean:
                    self.route_combo.setCurrentIndex(i)
                    found = True
                    break
            if not found:
                self.route_combo.addItem(route_clean)
                self.route_combo.setCurrentText(route_clean)

        # Jump to Tab 0
        self.tabs.setCurrentIndex(0)

    # ==========================================
    # TAB 2: POKÉDEX & AREA HABITAT LOCATOR
    # ==========================================
    def create_pokedex_tab(self):
        container = QWidget()
        c_layout = QVBoxLayout(container)
        c_layout.setContentsMargins(0, 0, 0, 0)
        c_layout.setSpacing(0)

        self.pokedex_main_tabs = QTabWidget()
        self.pokedex_main_tabs.currentChanged.connect(lambda: play_sfx("menu_select.wav"))

        # 1. Authentic In-Game GBA Pokédex View (Matching Reference Ground Truth)
        self.retro_pokedex_view = PokedexRetroView(db_path=self.db_path, save_path=self.save_path)
        self.retro_pokedex_view.pokemon_selected.connect(self.on_retro_pokemon_selected)
        self.pokedex_main_tabs.addTab(self.retro_pokedex_view, "🎮 In-Game GBA Pokédex")

        # 2. Existing Detailed Area & Habitat Locator View
        tab = QWidget()
        layout = QHBoxLayout(tab)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(12)

        # Left Column: Species List & Instant Filter
        left_box = QVBoxLayout()
        left_box.setSpacing(6)

        left_box.addWidget(QLabel("National Pokédex (#1 – #1,025):"))
        self.pokedex_search = QLineEdit()
        self.pokedex_search.setPlaceholderText("Search species (e.g. Vulpix, Breloom, #0037, Alolan)...")
        self.pokedex_search.textChanged.connect(self.filter_pokedex_list)
        left_box.addWidget(self.pokedex_search)

        self.pokedex_list = QListWidget()
        self.pokedex_list.currentRowChanged.connect(self.on_pokedex_mon_selected)
        left_box.addWidget(self.pokedex_list, 1)

        left_widget = QWidget()
        left_widget.setLayout(left_box)
        left_widget.setFixedWidth(260)
        layout.addWidget(left_widget)

        # Right Column: Details, Habitat Locator, Stats & Learnset
        right_box = QVBoxLayout()
        right_box.setSpacing(10)

        # Header Frame: Sprite + Name + Types + Catch Status
        self.p_header = QFrame()
        self.p_header.setStyleSheet("""
            background-color: #10262e;
            border-top: 2px solid #58b8a8;
            border-left: 2px solid #58b8a8;
            border-bottom: 2px solid #081820;
            border-right: 2px solid #081820;
            border-radius: 4px;
            padding: 8px 14px;
        """ if is_retro() else """
            background-color: #0f172a;
            border: 1px solid #1e293b;
            border-radius: 8px;
            padding: 8px 14px;
        """)
        ph_layout = QHBoxLayout(self.p_header)
        ph_layout.setContentsMargins(8, 4, 8, 4)
        ph_layout.setSpacing(12)

        self.pokedex_sprite = QLabel()
        self.pokedex_sprite.setFixedSize(64, 64)
        self.pokedex_sprite.setAlignment(Qt.AlignCenter)
        ph_layout.addWidget(self.pokedex_sprite)

        title_col = QVBoxLayout()
        title_col.setSpacing(3)
        self.pokedex_name_lbl = QLabel("#0001 Bulbasaur")
        self.pokedex_name_lbl.setStyleSheet("color: #00ff88; font-family: monospace; font-size: 16px; font-weight: bold;" if is_retro() else "color: #f8fafc; font-size: 16px; font-weight: bold;")
        title_col.addWidget(self.pokedex_name_lbl)

        # Form toggles / chips container
        self.pokedex_forms_container = QWidget()
        self.pokedex_forms_layout = QHBoxLayout(self.pokedex_forms_container)
        self.pokedex_forms_layout.setContentsMargins(0, 0, 0, 0)
        self.pokedex_forms_layout.setSpacing(6)
        title_col.addWidget(self.pokedex_forms_container)

        self.pokedex_types_row = QHBoxLayout()
        self.pokedex_types_row.setSpacing(4)
        title_col.addLayout(self.pokedex_types_row)
        ph_layout.addLayout(title_col, 1)

        self.pokedex_caught_btn = QPushButton("○ MISSING")
        self.pokedex_caught_btn.setFixedSize(90, 32)
        self.pokedex_caught_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.pokedex_caught_btn.clicked.connect(self.on_pokedex_caught_clicked)
        ph_layout.addWidget(self.pokedex_caught_btn)

        right_box.addWidget(self.p_header)

        # Pokédex Sub-Tabs: Area Locator, Base Stats, Learnsets, Evolution
        self.pokedex_subtabs = QTabWidget()
        self.pokedex_subtabs.currentChanged.connect(lambda: play_sfx("menu_select.wav"))
        right_box.addWidget(self.pokedex_subtabs, 1)

        # Sub-tab 1: Area / Habitat Locator ("locating pokemon and shi")
        self.create_pokedex_locator_tab()

        # Sub-tab 2: Base Stats & Abilities
        self.create_pokedex_stats_tab()

        # Sub-tab 3: Learnsets & Moves
        self.create_pokedex_learnsets_tab()

        # Sub-tab 4: Evolutions
        self.create_pokedex_evolutions_tab()

        layout.addLayout(right_box, 1)
        self.pokedex_main_tabs.addTab(tab, "📍 Area & Habitat Locator")

        c_layout.addWidget(self.pokedex_main_tabs)
        self.tabs.addTab(container, "📖 Pokédex & Area Finder")

        self.populate_pokedex_list()

    def on_retro_pokemon_selected(self, nat: int):
        """Synchronize selection from Retro Pokédex to Area Finder."""
        base_id = self.nat_base_species.get(nat, nat)
        for row in range(self.pokedex_list.count()):
            item = self.pokedex_list.item(row)
            if item and item.data(Qt.UserRole) == base_id:
                self.pokedex_list.blockSignals(True)
                self.pokedex_list.setCurrentRow(row)
                self.pokedex_list.blockSignals(False)
                self.load_pokedex_mon_details(base_id)
                break

    def create_pokedex_locator_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        loc_header = QHBoxLayout()
        lbl = QLabel("📍 WILD HABITAT & ROUTE LOCATIONS (Hoenn, Johto, Kanto, Sevii)")
        lbl.setStyleSheet("color: #38bdf8; font-weight: bold; font-size: 12px;")
        loc_header.addWidget(lbl)
        loc_header.addStretch()
        layout.addLayout(loc_header)

        self.locator_scroll = QScrollArea()
        self.locator_scroll.setWidgetResizable(True)
        self.locator_container = QWidget()
        self.locator_layout = QVBoxLayout(self.locator_container)
        self.locator_layout.setContentsMargins(4, 4, 4, 4)
        self.locator_layout.setSpacing(6)
        self.locator_scroll.setWidget(self.locator_container)
        layout.addWidget(self.locator_scroll, 1)

        self.pokedex_subtabs.addTab(tab, "📍 Area & Habitat Locator")

    def create_pokedex_stats_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        self.pk_stat_bars = {}
        for stat in ["HP", "Attack", "Defense", "Sp. Atk", "Sp. Def", "Speed"]:
            row = QHBoxLayout()
            row.setSpacing(8)
            lbl = QLabel(f"{stat:10}")
            lbl.setFixedWidth(70)
            lbl.setStyleSheet("color: #94a3b8; font-weight: bold;")
            row.addWidget(lbl)

            bar = QProgressBar()
            bar.setFixedHeight(12)
            bar.setMaximum(255)
            bar.setTextVisible(False)
            bar.setStyleSheet("""
                QProgressBar { background-color: #1e293b; border-radius: 6px; }
                QProgressBar::chunk { background-color: #3b82f6; border-radius: 6px; }
            """)
            row.addWidget(bar, 1)

            val = QLabel("---")
            val.setFixedWidth(40)
            val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            val.setStyleSheet("color: #f8fafc; font-weight: bold;")
            row.addWidget(val)

            self.pk_stat_bars[stat] = (bar, val)
            layout.addLayout(row)

        layout.addSpacing(10)
        self.pk_bst_lbl = QLabel("Base Stat Total (BST): ---")
        self.pk_bst_lbl.setStyleSheet("color: #38bdf8; font-size: 14px; font-weight: bold;")
        layout.addWidget(self.pk_bst_lbl)

        layout.addStretch()
        self.pokedex_subtabs.addTab(tab, "📊 Base Stats")

    def create_pokedex_learnsets_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)

        self.learnset_table = QTableWidget()
        self.learnset_table.setColumnCount(6)
        self.learnset_table.setHorizontalHeaderLabels(["Level", "Move Name", "Type", "Power", "Acc", "PP"])
        self.learnset_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.learnset_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.learnset_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        layout.addWidget(self.learnset_table)

        self.pokedex_subtabs.addTab(tab, "⚔️ Level-Up Learnset")

    def create_pokedex_evolutions_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        self.evo_info_lbl = QLabel("Evolution Chain Details:")
        self.evo_info_lbl.setStyleSheet("color: #38bdf8; font-weight: bold; font-size: 13px;")
        layout.addWidget(self.evo_info_lbl)

        self.evo_list = QListWidget()
        layout.addWidget(self.evo_list, 1)

        self.pokedex_subtabs.addTab(tab, "🧬 Evolution Line")

    def populate_pokedex_list(self):
        self.pokedex_list.blockSignals(True)
        self.pokedex_list.clear()

        # Group pokemon by national_dex_num
        for nat_dex in sorted(self.nat_dex_to_forms.keys()):
            forms = self.nat_dex_to_forms[nat_dex]
            base_form = forms[0]
            base_id = base_form["id"]
            base_name = base_form["name"]
            base_t1 = base_form["type1"]
            base_t2 = base_form["type2"]
            base_tag = "✓" if base_id in self.caught_species else "○"

            if len(forms) == 1:
                item = QListWidgetItem(f"#{nat_dex:04d} {base_name}  {base_tag}")
                item.setData(Qt.UserRole, base_id)
                item.setData(Qt.UserRole + 1, nat_dex)
                item.setData(Qt.UserRole + 2, False)
                if base_id in self.caught_species:
                    item.setForeground(QColor("#34d399"))
                else:
                    item.setForeground(QColor("#94a3b8"))
                self.pokedex_list.addItem(item)
            else:
                t_str = f"[{base_t1}]" if (base_t1 == base_t2 or not base_t2 or base_t2 == "None") else f"[{base_t1}/{base_t2}]"
                item = QListWidgetItem(f"#{nat_dex:04d} {base_name} {t_str}  {base_tag}")
                item.setData(Qt.UserRole, base_id)
                item.setData(Qt.UserRole + 1, nat_dex)
                item.setData(Qt.UserRole + 2, False)
                if base_id in self.caught_species:
                    item.setForeground(QColor("#34d399"))
                else:
                    item.setForeground(QColor("#94a3b8"))
                self.pokedex_list.addItem(item)

                # Indented variants under primary National Dex entry
                for var in forms[1:]:
                    v_id = var["id"]
                    v_badge = var["badge"]
                    v_t1 = var["type1"]
                    v_t2 = var["type2"]
                    v_t_str = f"[{v_t1}]" if (v_t1 == v_t2 or not v_t2 or v_t2 == "None") else f"[{v_t1}/{v_t2}]"
                    v_tag = "✓" if v_id in self.caught_species else "○"
                    var_item = QListWidgetItem(f"   ↳ #{nat_dex:04d} {v_badge} {base_name} {v_t_str}  {v_tag}")
                    var_item.setData(Qt.UserRole, v_id)
                    var_item.setData(Qt.UserRole + 1, nat_dex)
                    var_item.setData(Qt.UserRole + 2, True)
                    if v_id in self.caught_species:
                        var_item.setForeground(QColor("#38bdf8"))
                    else:
                        var_item.setForeground(QColor("#64748b"))
                    self.pokedex_list.addItem(var_item)

        self.pokedex_list.blockSignals(False)
        if self.pokedex_list.count() > 0:
            self.pokedex_list.setCurrentRow(0)

    def filter_pokedex_list(self, query: str):
        q = query.strip().lower()
        cleaned = q.lstrip("#").strip()
        num_query = int(cleaned) if cleaned.isdigit() else None

        for i in range(self.pokedex_list.count()):
            item = self.pokedex_list.item(i)
            text = item.text().lower()
            nat_dex = item.data(Qt.UserRole + 1)

            match = False
            if not q:
                match = True
            elif num_query is not None:
                if nat_dex == num_query:
                    match = True
                else:
                    hash_idx = text.find("#")
                    name_part = text[hash_idx + 5:].strip() if hash_idx != -1 else text
                    match = (q in name_part)
            else:
                match = (q in text)
            item.setHidden(not match)

    def on_pokedex_mon_selected(self, row: int):
        if row < 0:
            return
        play_sfx("menu_move.wav")
        item = self.pokedex_list.item(row)
        if not item:
            return
        pid = item.data(Qt.UserRole)
        if pid is None:
            pid = int(item.text().split()[0].replace("#", ""))
        self.load_pokedex_mon_details(pid)

    def select_pokedex_form(self, target_id: int):
        play_sfx("menu_select.wav")
        for i in range(self.pokedex_list.count()):
            item = self.pokedex_list.item(i)
            if item.data(Qt.UserRole) == target_id:
                self.pokedex_list.blockSignals(True)
                self.pokedex_list.setCurrentRow(i)
                self.pokedex_list.blockSignals(False)
                break
        self.load_pokedex_mon_details(target_id)

    def load_pokedex_mon_details(self, pid: int):
        self.current_pokedex_mon_id = pid

        self.cur.execute("""
            SELECT name, hp, atk, def, spa, spd, spe, bst, type1, type2, catch_rate, abilities, hidden_ability, national_dex_num
            FROM pokemon WHERE id = ?
        """, (pid,))
        r = self.cur.fetchone()
        if not r:
            return

        name, hp, atk, df, spa, spd, spe, bst, t1, t2, cr, ab, ha = r[:13]
        nat_dex = r[13] if len(r) > 13 and r[13] is not None else self.sp_to_nat.get(pid, pid)
        self.current_pokedex_mon_name = name
        self.current_national_dex_num = nat_dex

        base_id = self.nat_base_species.get(nat_dex, pid)
        form_badge = get_form_badge(pid, nat_dex, base_id, t1, t2)

        # Update title with form badge
        if form_badge and form_badge != "Standard":
            display_badge = f"{form_badge} Form" if form_badge in ("Alolan", "Galarian", "Hisuian", "Paldean") else form_badge
            self.pokedex_name_lbl.setText(f"#{nat_dex:04d} {name} • {display_badge} (Catch Rate: {cr})")
        else:
            self.pokedex_name_lbl.setText(f"#{nat_dex:04d} {name} (Catch Rate: {cr})")

        # Update Form Toggles / Chips
        while self.pokedex_forms_layout.count():
            it = self.pokedex_forms_layout.takeAt(0)
            if it.widget():
                it.widget().deleteLater()

        forms = self.nat_dex_to_forms.get(nat_dex, [])
        if len(forms) > 1:
            self.pokedex_forms_container.show()
            for f_info in forms:
                f_id = f_info["id"]
                f_badge = f_info["badge"]
                f_t1 = f_info["type1"]
                f_t2 = f_info["type2"]
                f_t_str = f"[{f_t1}]" if (f_t1 == f_t2 or not f_t2 or f_t2 == "None") else f"[{f_t1}/{f_t2}]"
                chip = QPushButton(f"{f_badge} {f_t_str}")
                chip.setCursor(QCursor(Qt.PointingHandCursor))
                chip.setCheckable(True)
                is_active = (f_id == pid)
                chip.setChecked(is_active)
                if is_retro():
                    if is_active:
                        chip.setStyleSheet("""
                            QPushButton {
                                background-color: #185468;
                                border-top: 2px solid #58f8e8;
                                border-left: 2px solid #58f8e8;
                                border-bottom: 2px solid #081820;
                                border-right: 2px solid #081820;
                                color: #ffffff;
                                font-family: monospace;
                                font-weight: bold;
                                font-size: 10px;
                                border-radius: 2px;
                                padding: 2px 7px;
                            }
                        """)
                    else:
                        chip.setStyleSheet("""
                            QPushButton {
                                background-color: #0c1c22;
                                border-top: 2px solid #306056;
                                border-left: 2px solid #306056;
                                border-bottom: 2px solid #050e12;
                                border-right: 2px solid #050e12;
                                color: #6a9c90;
                                font-family: monospace;
                                font-size: 10px;
                                border-radius: 2px;
                                padding: 2px 7px;
                            }
                            QPushButton:hover { background-color: #143038; color: #a8d8c8; }
                        """)
                else:
                    if is_active:
                        chip.setStyleSheet("""
                            QPushButton {
                                background-color: #2563eb;
                                border: 1px solid #60a5fa;
                                color: #FFFFFF;
                                font-weight: bold;
                                font-size: 10px;
                                border-radius: 4px;
                                padding: 2px 7px;
                            }
                        """)
                    else:
                        chip.setStyleSheet("""
                            QPushButton {
                                background-color: #1e293b;
                                border: 1px solid #334155;
                                color: #94a3b8;
                                font-size: 10px;
                                border-radius: 4px;
                                padding: 2px 7px;
                            }
                            QPushButton:hover { background-color: #334155; color: #FFFFFF; }
                        """)
                chip.clicked.connect(lambda checked=False, target_id=f_id: self.select_pokedex_form(target_id))
                self.pokedex_forms_layout.addWidget(chip)
            self.pokedex_forms_layout.addStretch()
        else:
            self.pokedex_forms_container.hide()

        # Sprite
        pm = get_species_pixmap(pid, is_silhouette=False)
        if pm:
            self.pokedex_sprite.setPixmap(pm.scaled(60, 60, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            self.pokedex_sprite.setText("🐾")

        # Dual types
        while self.pokedex_types_row.count():
            it = self.pokedex_types_row.takeAt(0)
            if it.widget(): it.widget().deleteLater()
        if t1 and t1 != "None":
            self.pokedex_types_row.addWidget(TypeBadge(t1))
        if t2 and t2 != "None" and t2 != t1:
            self.pokedex_types_row.addWidget(TypeBadge(t2))
        self.pokedex_types_row.addStretch()

        # Caught button
        is_c = pid in self.caught_species
        self.update_pokedex_caught_btn(is_c)

        # Base stats
        stats_map = {
            "HP": hp, "Attack": atk, "Defense": df,
            "Sp. Atk": spa, "Sp. Def": spd, "Speed": spe
        }
        for stat, val in stats_map.items():
            if stat in self.pk_stat_bars:
                bar, lbl = self.pk_stat_bars[stat]
                bar.setValue(val)
                lbl.setText(str(val))
        self.pk_bst_lbl.setText(f"Base Stat Total (BST): {bst}")

        # Area / Habitat Locator populate
        self.populate_pokedex_habitat_locator(pid, name)

        # Learnsets
        self.cur.execute("""
            SELECT l.level, l.move_name, m.type, m.power, m.accuracy, m.pp
            FROM learnsets l
            LEFT JOIN moves m ON l.move_id = m.id
            WHERE l.pokemon_id = ?
            ORDER BY l.level ASC
        """, (pid,))
        learn_rows = self.cur.fetchall()
        self.learnset_table.setRowCount(len(learn_rows))
        for i, lr in enumerate(learn_rows):
            lv, m_name, m_type, pwr, acc, pp = lr
            self.learnset_table.setItem(i, 0, QTableWidgetItem(f"Lv. {lv}"))
            self.learnset_table.setItem(i, 1, QTableWidgetItem(m_name))
            self.learnset_table.setItem(i, 2, QTableWidgetItem(m_type or "---"))
            self.learnset_table.setItem(i, 3, QTableWidgetItem(str(pwr) if pwr and pwr > 0 else "---"))
            self.learnset_table.setItem(i, 4, QTableWidgetItem(f"{acc}%" if acc and acc > 0 else "---"))
            self.learnset_table.setItem(i, 5, QTableWidgetItem(str(pp) if pp else "---"))

        # Evolution Line
        self.evo_list.clear()
        self.cur.execute("SELECT target_name, method_desc FROM evolutions WHERE pokemon_id = ?", (pid,))
        evos = self.cur.fetchall()
        if evos:
            for tgt, meth in evos:
                self.evo_list.addItem(f"➔ Evolves into {tgt}: {meth}")
        else:
            self.evo_list.addItem("This Pokémon does not evolve further.")

    def populate_pokedex_habitat_locator(self, pid: int, name: str):
        """Populate in-game Area Habitat Locator cards."""
        while self.locator_layout.count():
            item = self.locator_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self.cur.execute("""
            SELECT region, location_name, method, chance, min_level, max_level
            FROM encounters
            WHERE species_id = ? OR species_name = ?
            ORDER BY region, location_name, method
        """, (pid, name))
        rows = self.cur.fetchall()

        if not rows:
            # Check legendaries
            self.cur.execute("SELECT location, requirements FROM legendaries WHERE name = ?", (name,))
            leg = self.cur.fetchone()
            if leg:
                card = QFrame()
                card.setStyleSheet("background-color: #1e1b4b; border: 1px solid #6366f1; border-radius: 6px; padding: 10px;")
                c_lay = QVBoxLayout(card)
                c_lay.addWidget(QLabel(f"⭐ LEGENDARY SPAWN: {leg[0]}"))
                c_lay.addWidget(QLabel(f"Requirements: {leg[1]}"))
                self.locator_layout.addWidget(card)
            else:
                card = QFrame()
                card.setStyleSheet("background-color: #0f172a; border: 1px solid #1e293b; border-radius: 6px; padding: 12px;")
                c_lay = QVBoxLayout(card)
                msg = QLabel("Area Unknown: Not found in the wild.\nObtained via Evolution, Breeding, Fossil Revival, or Special NPC Gift.")
                msg.setStyleSheet("color: #94a3b8; font-size: 12px;")
                c_lay.addWidget(msg)
                self.locator_layout.addWidget(card)
            return

        for r in rows:
            reg, loc, meth, ch, min_l, max_l = r
            card = QFrame()
            card.setStyleSheet("""
                QFrame {
                    background-color: #0f172a;
                    border: 1px solid #1e293b;
                    border-radius: 6px;
                    padding: 6px 10px;
                }
                QFrame:hover {
                    border-color: #38bdf8;
                    background-color: #131d30;
                }
            """)
            c_lay = QHBoxLayout(card)
            c_lay.setContentsMargins(6, 4, 6, 4)
            c_lay.setSpacing(10)

            # Region tag
            reg_badge = QLabel(f"{reg.upper()}")
            reg_badge.setStyleSheet("""
                background-color: #1e293b;
                color: #38bdf8;
                font-weight: bold;
                font-size: 10px;
                padding: 2px 6px;
                border-radius: 4px;
            """)
            c_lay.addWidget(reg_badge)

            # Location & Details
            loc_lbl = QLabel(f"<b>{loc}</b>  •  {meth} ({ch}%)  •  Lv.{min_l}–{max_l}")
            loc_lbl.setStyleSheet("color: #f1f5f9; font-size: 12px;")
            c_lay.addWidget(loc_lbl, 1)

            # Action button: Jump to Route
            jump_btn = QPushButton("🎯 Jump to Route")
            jump_btn.setFixedSize(110, 24)
            jump_btn.setCursor(QCursor(Qt.PointingHandCursor))
            jump_btn.setStyleSheet("""
                QPushButton {
                    background-color: #0284c7;
                    border: 1px solid #38bdf8;
                    color: #FFFFFF;
                    font-size: 10px;
                    font-weight: bold;
                    border-radius: 4px;
                }
                QPushButton:hover { background-color: #0369a1; }
            """)
            jump_btn.clicked.connect(lambda ch=False, l=loc, rg=reg: self.jump_to_route(l, rg))
            c_lay.addWidget(jump_btn)

            # Action button: Locate on Map
            map_btn = QPushButton("📍 Show on Map")
            map_btn.setFixedSize(100, 24)
            map_btn.setCursor(QCursor(Qt.PointingHandCursor))
            map_btn.setStyleSheet("""
                QPushButton {
                    background-color: #1e293b;
                    border: 1px solid #475569;
                    color: #cbd5e1;
                    font-size: 10px;
                    font-weight: bold;
                    border-radius: 4px;
                }
                QPushButton:hover { background-color: #334155; color: #FFFFFF; }
            """)
            map_btn.clicked.connect(lambda ch=False, l=loc, rg=reg: self.show_location_on_map(l, rg))
            c_lay.addWidget(map_btn)

            self.locator_layout.addWidget(card)

        self.locator_layout.addStretch()

    def jump_to_route(self, route_name: str, region: str):
        """Switches to Route Encounters tab and selects this route."""
        play_sfx("menu_select.wav")
        reg_idx = self.region_combo.findText(region)
        if reg_idx >= 0:
            self.region_combo.setCurrentIndex(reg_idx)
        r_idx = self.route_combo.findText(route_name)
        if r_idx >= 0:
            self.route_combo.setCurrentIndex(r_idx)
        self.tabs.setCurrentIndex(0)

    def show_location_on_map(self, route_name: str, region: str):
        """Switches to Regional Town Map tab and highlights this route."""
        play_sfx("menu_select.wav")
        if hasattr(self, 'map_widget'):
            self.map_widget.set_region(region)
            self.map_widget.highlight_locations([route_name])
        self.tabs.setCurrentIndex(1)

    def jump_to_pokedex_mon(self, species_id: int, activate_tab: str = "EVOS"):
        """Jumps directly to this Pokémon inside the Pokédex tab and activates EVOS & PATHS view."""
        play_sfx("menu_select.wav")
        self.tabs.setCurrentIndex(2)

        # 1. Switch to In-Game GBA Pokédex View & activate EVOS & PATHS tab
        if hasattr(self, "pokedex_main_tabs"):
            self.pokedex_main_tabs.setCurrentIndex(0)

        nat = self.sp_to_nat.get(species_id, species_id)
        if hasattr(self, "retro_pokedex_view") and self.retro_pokedex_view is not None:
            self.retro_pokedex_view.select_pokemon(nat)
            if activate_tab == "EVOS":
                self.retro_pokedex_view.show_evos_tab()
            elif activate_tab == "HOW_TO_GET":
                self.retro_pokedex_view.show_how_to_get_tab()
            elif activate_tab == "STATS":
                self.retro_pokedex_view.show_stats_tab()

        # 2. Match exact species_id first in Area Finder legacy list
        for i in range(self.pokedex_list.count()):
            item = self.pokedex_list.item(i)
            if item.data(Qt.UserRole) == species_id:
                self.pokedex_list.blockSignals(True)
                self.pokedex_list.setCurrentRow(i)
                self.pokedex_list.blockSignals(False)
                return

        # 3. Match by national_dex_num
        for i in range(self.pokedex_list.count()):
            item = self.pokedex_list.item(i)
            if item.data(Qt.UserRole + 1) == nat:
                self.pokedex_list.blockSignals(True)
                self.pokedex_list.setCurrentRow(i)
                self.pokedex_list.blockSignals(False)
                if species_id in self.nat_to_sps.get(nat, []):
                    self.load_pokedex_mon_details(species_id)
                return

    def refresh_pokedex_list_tags(self):
        """Silky-smooth tag and color update for pokedex items without rebuilding or jumping."""
        for i in range(self.pokedex_list.count()):
            item = self.pokedex_list.item(i)
            pid = item.data(Qt.UserRole)
            is_sub = item.data(Qt.UserRole + 2)
            is_c = pid in self.caught_species
            old_text = item.text()
            if old_text.endswith("✓") or old_text.endswith("○"):
                new_text = old_text[:-1] + ("✓" if is_c else "○")
                item.setText(new_text)
            if is_c:
                item.setForeground(QColor("#38bdf8" if is_sub else "#34d399"))
            else:
                item.setForeground(QColor("#64748b" if is_sub else "#94a3b8"))

    def on_pokedex_caught_clicked(self):
        if not hasattr(self, 'current_pokedex_mon_id'):
            return
        pid = self.current_pokedex_mon_id
        name = self.current_pokedex_mon_name
        is_c = pid in self.caught_species

        # Synchronize all forms sharing national_dex_num
        nat = self.sp_to_nat.get(pid, pid)
        related_ids = self.nat_to_sps.get(nat, [pid])

        if is_c:
            play_sfx("menu_cancel.wav")
            for rid in related_ids:
                self.caught_species.discard(rid)
                self.cur.execute("DELETE FROM caught_pokemon WHERE species_id = ?", (rid,))
                self.cur.execute("UPDATE user_pokedex SET caught = 0 WHERE species_id = ?", (rid,))
        else:
            play_sfx("caught_fanfare.wav")
            for rid in related_ids:
                self.caught_species.add(rid)
                rname = self.sp_to_name.get(rid, name)
                self.cur.execute("INSERT OR REPLACE INTO caught_pokemon (species_id, species_name) VALUES (?, ?)", (rid, rname))
                self.cur.execute("INSERT OR REPLACE INTO user_pokedex (species_id, caught, seen) VALUES (?, 1, 1)", (rid,))
        self.conn.commit()

        self.update_pokedex_caught_btn(not is_c)
        self.refresh_pokedex_list_tags()
        pct = (len(self.caught_species) / 1499 * 100) if 1499 > 0 else 0
        if is_retro():
            self.save_status_lbl.setText(f"💾 SAVE: NIG | POKéDEX: {len(self.caught_species)}/1,499 ({pct:.1f}%)")
        else:
            self.save_status_lbl.setText(f"💾 Player: NIG • Caught: {len(self.caught_species)} / 1,499 ({pct:.1f}%)")

    def update_pokedex_caught_btn(self, is_caught: bool):
        if is_retro():
            if is_caught:
                self.pokedex_caught_btn.setText("✓ CAUGHT")
                self.pokedex_caught_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #008850;
                        color: #00ff88;
                        border-top: 2px solid #00ff88;
                        border-left: 2px solid #00ff88;
                        border-bottom: 2px solid #042010;
                        border-right: 2px solid #042010;
                        border-radius: 2px;
                        font-weight: bold;
                        font-family: monospace;
                        font-size: 11px;
                    }
                    QPushButton:pressed {
                        border-top: 2px solid #042010;
                        border-left: 2px solid #042010;
                        border-bottom: 2px solid #00ff88;
                        border-right: 2px solid #00ff88;
                    }
                """)
            else:
                self.pokedex_caught_btn.setText("○ MISSING")
                self.pokedex_caught_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #5c1810;
                        color: #ff8878;
                        border-top: 2px solid #ff8878;
                        border-left: 2px solid #ff8878;
                        border-bottom: 2px solid #200806;
                        border-right: 2px solid #200806;
                        border-radius: 2px;
                        font-weight: bold;
                        font-family: monospace;
                        font-size: 11px;
                    }
                    QPushButton:pressed {
                        border-top: 2px solid #200806;
                        border-left: 2px solid #200806;
                        border-bottom: 2px solid #ff8878;
                        border-right: 2px solid #ff8878;
                    }
                """)
        else:
            if is_caught:
                self.pokedex_caught_btn.setText("✓ CAUGHT")
                self.pokedex_caught_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #065f46;
                        border: 1px solid #10b981;
                        color: #FFFFFF;
                        font-weight: bold;
                        border-radius: 4px;
                    }
                """)
            else:
                self.pokedex_caught_btn.setText("○ MISSING")
                self.pokedex_caught_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #451a03;
                        border: 1px solid #d97706;
                        color: #fbbf24;
                        font-weight: bold;
                        border-radius: 4px;
                    }
                """)

    # ==========================================
    # TAB 3: TRAINERS & BATTLE FRONTIER
    # ==========================================
    def create_trainers_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Controls: Category Pills & Search
        top_row = QHBoxLayout()
        top_row.setSpacing(8)

        top_row.addWidget(QLabel("Category:"))
        self.trainer_cat_buttons = []
        categories = ["All (35)", "Battle Frontier Brains", "Hoenn Gym Rematches", "Johto Gym Rematches", "Champions & Bosses"]
        for cat in categories:
            btn = QPushButton(cat)
            btn.setCheckable(True)
            btn.setFixedHeight(28)
            btn.setCursor(QCursor(Qt.PointingHandCursor))
            btn.clicked.connect(lambda ch=False, c=cat: self.filter_trainers(category=c))
            top_row.addWidget(btn)
            self.trainer_cat_buttons.append(btn)

        self.selected_trainer_cat = "All (35)"
        self.update_trainer_cat_button_styles()
        top_row.addStretch()

        self.trainer_search = QLineEdit()
        self.trainer_search.setPlaceholderText("Search trainer name, title, location, Pokémon...")
        self.trainer_search.setFixedWidth(280)
        self.trainer_search.textChanged.connect(lambda: self.filter_trainers())
        top_row.addWidget(self.trainer_search)

        layout.addLayout(top_row)

        # Trainers Table
        self.trainers_table = QTableWidget()
        self.trainers_table.setColumnCount(7)
        self.trainers_table.setHorizontalHeaderLabels([
            "Category", "Trainer Name", "Title", "Region", "Location", "Unlock Condition", "Team Preview"
        ])
        self.trainers_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.trainers_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.trainers_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.trainers_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.trainers_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.trainers_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)
        self.trainers_table.horizontalHeader().setSectionResizeMode(6, QHeaderView.Stretch)
        self.trainers_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.trainers_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.trainers_table.verticalHeader().setVisible(False)
        self.trainers_table.itemSelectionChanged.connect(lambda: play_sfx("menu_move.wav"))
        layout.addWidget(self.trainers_table, 1)

        self.tabs.addTab(tab, "⚔️ Trainers & Frontier")

        self.populate_trainers_table()

    def update_trainer_cat_button_styles(self):
        cat_filter = getattr(self, "selected_trainer_cat", "All (35)")
        for btn in getattr(self, "trainer_cat_buttons", []):
            is_active = (btn.text() == cat_filter)
            btn.setChecked(is_active)
            if is_retro():
                if is_active:
                    btn.setStyleSheet("""
                        QPushButton {
                            background-color: #008850;
                            border-top: 2px solid #00ff88;
                            border-left: 2px solid #00ff88;
                            border-bottom: 2px solid #042010;
                            border-right: 2px solid #042010;
                            color: #ffffff;
                            font-weight: bold;
                            font-family: monospace;
                            border-radius: 2px;
                            padding: 2px 8px;
                            font-size: 11px;
                        }
                    """)
                else:
                    btn.setStyleSheet("""
                        QPushButton {
                            background-color: #0c1c22;
                            border-top: 2px solid #306056;
                            border-left: 2px solid #306056;
                            border-bottom: 2px solid #050e12;
                            border-right: 2px solid #050e12;
                            color: #6a9c90;
                            font-family: monospace;
                            border-radius: 2px;
                            padding: 2px 8px;
                            font-size: 11px;
                        }
                        QPushButton:hover { background-color: #143038; color: #a8d8c8; }
                        QPushButton:pressed {
                            border-top: 2px solid #050e12;
                            border-left: 2px solid #050e12;
                            border-bottom: 2px solid #306056;
                            border-right: 2px solid #306056;
                        }
                    """)
            else:
                if is_active:
                    btn.setStyleSheet("background-color: #2563eb; color: #FFFFFF; font-weight: bold; border-radius: 4px; padding: 2px 8px;")
                else:
                    btn.setStyleSheet("background-color: #1e293b; color: #94a3b8; border: 1px solid #334155; border-radius: 4px; padding: 2px 8px;")

    def populate_trainers_table(self):
        self.cur.execute("SELECT category, name, title, region, location, unlock_condition, team_preview, reward FROM trainers ORDER BY id ASC")
        self.all_trainers_data = self.cur.fetchall()
        self.filter_trainers()

    def filter_trainers(self, category: str = None):
        if category:
            play_sfx("menu_select.wav")
            self.selected_trainer_cat = category
            self.update_trainer_cat_button_styles()

        cat_filter = getattr(self, "selected_trainer_cat", "All (35)")
        query = self.trainer_search.text().strip().lower()

        filtered = []
        for t in self.all_trainers_data:
            cat, name, title, reg, loc, unlock, team, reward = t

            # Category filter
            if "Frontier" in cat_filter and "Frontier" not in cat:
                continue
            if "Hoenn Gym" in cat_filter and ("Gym" not in cat or reg != "Hoenn"):
                continue
            if "Johto Gym" in cat_filter and ("Gym" not in cat or reg != "Johto"):
                continue
            if "Champions" in cat_filter and "Champion" not in cat and "Boss" not in cat:
                continue

            # Query filter
            if query:
                combined = f"{cat} {name} {title} {reg} {loc} {unlock} {team} {reward}".lower()
                if query not in combined:
                    continue

            filtered.append(t)

        self.trainers_table.setRowCount(len(filtered))
        for i, t in enumerate(filtered):
            cat, name, title, reg, loc, unlock, team, reward = t
            self.trainers_table.setItem(i, 0, QTableWidgetItem(cat))
            self.trainers_table.setItem(i, 1, QTableWidgetItem(f"⭐ {name}"))
            self.trainers_table.setItem(i, 2, QTableWidgetItem(title))
            self.trainers_table.setItem(i, 3, QTableWidgetItem(reg))
            self.trainers_table.setItem(i, 4, QTableWidgetItem(loc))
            self.trainers_table.setItem(i, 5, QTableWidgetItem(unlock))
            self.trainers_table.setItem(i, 6, QTableWidgetItem(team.replace("\n", " | ")))

    # ==========================================
    # TAB 4: MASTER LEGENDARY GRAPHICAL GUIDE
    # ==========================================
    def create_legendaries_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Top Bar
        top_row = QHBoxLayout()
        top_row.setSpacing(10)

        top_row.addWidget(QLabel("Status:"))
        self.leg_status_all = QPushButton("Show All")
        self.leg_status_missing = QPushButton("○ Missing Only")
        self.leg_status_caught = QPushButton("✓ Caught Only")

        self.leg_status_btns = [self.leg_status_all, self.leg_status_missing, self.leg_status_caught]
        self.leg_filter_mode = "Show All"

        for btn, mode in zip(self.leg_status_btns, ["Show All", "Missing Only", "Caught Only"]):
            btn.setCheckable(True)
            btn.setFixedHeight(26)
            btn.setCursor(QCursor(Qt.PointingHandCursor))
            btn.clicked.connect(lambda checked, m=mode: self.set_leg_status_filter(m))
            top_row.addWidget(btn)

        self.update_leg_filter_button_styles()

        top_row.addSpacing(14)
        top_row.addWidget(QLabel("Gen / Region:"))
        self.leg_gen_combo = QComboBox()
        self.leg_gen_combo.addItems([
            "All Generations",
            "Hoenn Native",
            "Generation 1 (Kanto)",
            "Generation 2 (Johto)",
            "Generation 4 (Sinnoh)",
            "Generation 5 (Unova)",
            "Generation 6 (Kalos)",
            "Generation 7 (Alola & Ultra Beasts)",
            "Generation 8 (Galar)",
            "Generation 9 (Paldea & Paradox Encounters)"
        ])
        self.leg_gen_combo.currentIndexChanged.connect(self.filter_legendaries)
        top_row.addWidget(self.leg_gen_combo)

        top_row.addStretch()

        self.leg_search = QLineEdit()
        self.leg_search.setPlaceholderText("🔍 Search Legendary (e.g. Rayquaza, Sky Pillar, Mach Bike)...")
        self.leg_search.setFixedWidth(280)
        self.leg_search.textChanged.connect(self.filter_legendaries)
        top_row.addWidget(self.leg_search)

        layout.addLayout(top_row)

        # Splitter: Card Grid (Left) | Legendary Inspector Drawer (Right)
        splitter = QSplitter(Qt.Horizontal)

        self.leg_cards_scroll = QScrollArea()
        self.leg_cards_scroll.setWidgetResizable(True)
        self.leg_cards_scroll.setStyleSheet("background-color: #0b0f17; border: 1px solid #1e293b; border-radius: 8px;")

        self.leg_cards_container = QWidget()
        self.leg_cards_grid = QGridLayout(self.leg_cards_container)
        self.leg_cards_grid.setContentsMargins(10, 10, 10, 10)
        self.leg_cards_grid.setSpacing(10)
        self.leg_cards_scroll.setWidget(self.leg_cards_container)
        splitter.addWidget(self.leg_cards_scroll)

        # Right Legendary Inspector Drawer
        self.leg_inspector_drawer = LegendaryInspectorDrawer()
        self.leg_inspector_drawer.open_in_pokedex.connect(self.jump_to_pokedex_mon)
        splitter.addWidget(self.leg_inspector_drawer)

        splitter.setStretchFactor(0, 7)
        splitter.setStretchFactor(1, 3)
        layout.addWidget(splitter, 1)

        self.tabs.addTab(tab, "👑 Legendary Master Guide")

        self.populate_legendaries_cards()

    def set_leg_status_filter(self, mode: str):
        play_sfx("menu_select.wav")
        self.leg_filter_mode = mode
        self.update_leg_filter_button_styles()
        self.filter_legendaries()

    def update_leg_filter_button_styles(self):
        for btn in self.leg_status_btns:
            is_active = (btn.text().endswith(self.leg_filter_mode) or btn.text() == self.leg_filter_mode)
            btn.setChecked(is_active)
            if is_retro():
                if is_active:
                    btn.setStyleSheet("""
                        QPushButton {
                            background-color: #008850;
                            border-top: 2px solid #00ff88;
                            border-left: 2px solid #00ff88;
                            border-bottom: 2px solid #042010;
                            border-right: 2px solid #042010;
                            color: #ffffff;
                            font-weight: bold;
                            font-family: monospace;
                            border-radius: 2px;
                            padding: 2px 10px;
                        }
                    """)
                else:
                    btn.setStyleSheet("""
                        QPushButton {
                            background-color: #0c1c22;
                            border-top: 2px solid #306056;
                            border-left: 2px solid #306056;
                            border-bottom: 2px solid #050e12;
                            border-right: 2px solid #050e12;
                            color: #6a9c90;
                            font-family: monospace;
                            border-radius: 2px;
                            padding: 2px 10px;
                        }
                        QPushButton:hover { background-color: #143038; color: #a8d8c8; }
                        QPushButton:pressed {
                            border-top: 2px solid #050e12;
                            border-left: 2px solid #050e12;
                            border-bottom: 2px solid #306056;
                            border-right: 2px solid #306056;
                        }
                    """)
            else:
                if is_active:
                    btn.setStyleSheet("background-color: #0284c7; color: #FFFFFF; font-weight: bold; border-radius: 4px; padding: 2px 10px;")
                else:
                    btn.setStyleSheet("background-color: #1e293b; color: #94a3b8; border: 1px solid #334155; border-radius: 4px; padding: 2px 10px;")

    def update_stats_header(self):
        if not hasattr(self, 'save_status_lbl'):
            return
        pct = (len(self.caught_species) / 1499 * 100) if 1499 > 0 else 0
        if is_retro():
            self.save_status_lbl.setText(f"💾 SAVE: NIG | POKéDEX: {len(self.caught_species)}/1,499 ({pct:.1f}%)")
        else:
            self.save_status_lbl.setText(f"💾 Player: NIG • Caught: {len(self.caught_species)} / 1,499 ({pct:.1f}%)")

    def populate_legendaries_cards(self):
        self.cur.execute("""
            SELECT l.name, l.generation, l.level, l.location, l.requirements, l.synergy, l.notes,
                    MIN(p.id), p.type1, p.type2, p.hp, p.atk, p.def, p.spa, p.spd, p.spe, p.bst, p.catch_rate,
                    p.abilities, p.hidden_ability, p.national_dex_num
            FROM legendaries l
            LEFT JOIN pokemon p ON LOWER(l.name) = LOWER(p.name)
            GROUP BY l.name
            ORDER BY l.name ASC
        """)
        rows = self.cur.fetchall()
        self.all_legendary_data = []
        for r in rows:
            name, gen, lvl, loc, req, syn, notes = r[:7]
            sp_id, t1, t2, hp, atk, df, spa, spd, spe, bst, cr, ab, ha = r[7:20]
            sp_id = sp_id if sp_id else 0
            is_caught = sp_id in self.caught_species if sp_id else False

            nat_dex = r[20] if len(r) > 20 and r[20] is not None else self.sp_to_nat.get(sp_id, sp_id)
            base_id = self.nat_base_species.get(nat_dex, sp_id)
            form_badge = get_form_badge(sp_id, nat_dex, base_id, t1, t2)

            d = {
                "name": name, "generation": gen, "level": lvl, "location": loc,
                "requirements": req, "synergy": syn, "notes": notes,
                "species_id": sp_id, "type1": t1, "type2": t2,
                "hp": hp or 0, "atk": atk or 0, "def": df or 0, "spa": spa or 0,
                "spd": spd or 0, "spe": spe or 0, "bst": bst or 0, "catch_rate": cr or 3,
                "abilities": ab, "hidden_ability": ha, "is_caught": is_caught,
                "national_dex_num": nat_dex,
                "form_badge": form_badge
            }
            self.all_legendary_data.append(d)

        # Defer creating 80+ card widgets until the tab is displayed
        if hasattr(self, 'tabs') and self.tabs.currentIndex() != 4 and not getattr(self, '_force_populate_cards', False):
            if self.all_legendary_data:
                self.leg_inspector_drawer.populate(self.all_legendary_data[0])
            return

        self.filter_legendaries()
        if self.all_legendary_data:
            self.leg_inspector_drawer.populate(self.all_legendary_data[0])

    def filter_legendaries(self):
        while self.leg_cards_grid.count():
            item = self.leg_cards_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        status_filter = self.leg_filter_mode
        gen_filter = self.leg_gen_combo.currentText()
        query = self.leg_search.text().strip().lower()

        filtered = []
        for d in self.all_legendary_data:
            if status_filter == "Missing Only" and d["is_caught"]:
                continue
            if status_filter == "Caught Only" and not d["is_caught"]:
                continue

            if gen_filter != "All Generations":
                if gen_filter.lower() not in d["generation"].lower():
                    continue

            if query:
                haystack = f"{d['name']} {d['generation']} {d['location']} {d['requirements']} {d['synergy']}".lower()
                if query not in haystack:
                    continue

            filtered.append(d)

        self.rendered_leg_cards = []
        for idx, leg_data in enumerate(filtered):
            card = ModernLegendaryCard(leg_data)
            card.clicked.connect(self.on_legendary_card_clicked)
            card.catch_toggled.connect(self.on_legendary_catch_toggled)
            r = idx // 2
            c = idx % 2
            self.leg_cards_grid.addWidget(card, r, c)
            self.rendered_leg_cards.append(card)

        if not filtered:
            empty_lbl = QLabel("No Legendary Pokémon match your filter criteria.")
            empty_lbl.setAlignment(Qt.AlignCenter)
            empty_lbl.setStyleSheet("color: #64748b; font-size: 14px; padding: 40px;")
            self.leg_cards_grid.addWidget(empty_lbl, 0, 0, 1, 2)

    def on_legendary_card_clicked(self, leg_data: dict):
        self.leg_inspector_drawer.populate(leg_data)
        for card in self.rendered_leg_cards:
            is_sel = (card.name == leg_data["name"])
            card.update_card_style(is_selected=is_sel)

    def on_legendary_catch_toggled(self, species_id: int, species_name: str, is_caught: bool):
        nat_num = self.sp_to_nat.get(species_id, species_id)
        related_ids = self.nat_to_sps.get(nat_num, [species_id])

        if is_caught:
            play_sfx("caught_fanfare.wav")
            for rid in related_ids:
                self.caught_species.add(rid)
                rname = self.sp_to_name.get(rid, species_name)
                self.cur.execute("INSERT OR REPLACE INTO caught_pokemon (species_id, species_name) VALUES (?, ?)", (rid, rname))
                self.cur.execute("INSERT OR REPLACE INTO user_pokedex (species_id, caught, seen) VALUES (?, 1, 1)", (rid,))
        else:
            play_sfx("menu_cancel.wav")
            for rid in related_ids:
                self.caught_species.discard(rid)
                self.cur.execute("DELETE FROM caught_pokemon WHERE species_id = ?", (rid,))
                self.cur.execute("UPDATE user_pokedex SET caught = 0 WHERE species_id = ?", (rid,))
        self.conn.commit()

        for d in self.all_legendary_data:
            if d.get("species_id") in related_ids or d.get("national_dex_num") == nat_num or d["name"] == species_name:
                d["is_caught"] = is_caught

        for card in self.rendered_leg_cards:
            if card.species_id in related_ids or getattr(card, "national_dex_num", None) == nat_num or card.name == species_name:
                card.is_caught = is_caught
                card.update_card_style(is_selected=False)

        self.update_stats_header()
        if hasattr(self, 'map_widget'):
            self.map_widget.load_data_from_db(DB_PATH)

    # ==========================================
    # TAB 5: DEDICATED LEGENDARY ROADMAP & SYNERGIES
    # ==========================================
    def create_legendary_roadmap_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        # Header Hero Card
        self.hero_card = QFrame()
        self.hero_card.setStyleSheet("""
            background-color: #10262e;
            border-top: 2px solid #58b8a8;
            border-left: 2px solid #58b8a8;
            border-bottom: 2px solid #081820;
            border-right: 2px solid #081820;
            border-radius: 4px;
            padding: 10px 14px;
        """ if is_retro() else """
            background-color: #0f172a;
            border: 1px solid #1e293b;
            border-radius: 8px;
            padding: 10px 14px;
        """)
        h_layout = QVBoxLayout(self.hero_card)
        h_layout.setContentsMargins(6, 4, 6, 4)
        h_layout.setSpacing(4)

        title = QLabel("🧭 OPTIMAL DUAL-TYPE SQUAD & REGIONAL LEGENDARY ROADMAP")
        title.setFont(QFont("Arial", 13, QFont.Bold))
        title.setStyleSheet("color: #00ff88; font-family: monospace;" if is_retro() else "color: #38bdf8;")
        h_layout.addWidget(title)

        subtitle = QLabel(
            "Solve all ancient statues, puzzle seals, and door requirements across Hoenn, Kanto, Johto, and Portals "
            "with zero repetitive PC backtracking by utilizing dual-type squad coverage."
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color: #6a9c90; font-size: 11px; font-family: monospace;" if is_retro() else "color: #94a3b8; font-size: 11px;")
        h_layout.addWidget(subtitle)
        layout.addWidget(self.hero_card)

        # Main Scroll Area for Roadmap
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background: transparent; border: none;")

        s_widget = QWidget()
        s_layout = QVBoxLayout(s_widget)
        s_layout.setContentsMargins(0, 0, 0, 0)
        s_layout.setSpacing(14)

        # Blueprint Frame: Hall of Fame Coverage Analysis
        self.bp_frame = QFrame()
        self.bp_frame.setStyleSheet("""
            background-color: #09171e;
            border-top: 2px solid #040a0c;
            border-left: 2px solid #040a0c;
            border-bottom: 2px solid #387068;
            border-right: 2px solid #387068;
            border-radius: 3px;
            padding: 12px;
        """ if is_retro() else """
            background-color: #0c121d;
            border: 1.5px solid #0284c7;
            border-radius: 8px;
            padding: 12px;
        """)
        bp_layout = QVBoxLayout(self.bp_frame)
        bp_layout.setContentsMargins(8, 6, 8, 6)
        bp_layout.setSpacing(8)

        bp_title = QLabel("⭐ UNIVERSAL MULTI-USE SQUAD BLUEPRINT")
        bp_title.setFont(QFont("Arial", 11, QFont.Bold))
        bp_title.setStyleSheet("color: #00ff88; letter-spacing: 0.5px; font-family: monospace;" if is_retro() else "color: #38bdf8; letter-spacing: 0.5px;")
        bp_layout.addWidget(bp_title)

        bp_desc = QLabel(
            "<b>Your Active Hall of Fame Squad:</b><br>"
            "• <b>Breloom</b> (Grass/Fighting) • <b>Togekiss</b> (Fairy/Flying) • <b>Gardevoir</b> (Psychic/Fairy)<br>"
            "• <b>Blaziken</b> (Fire/Fighting) • <b>Hydrapple</b> (Grass/Dragon) • <b>Goodra</b> (Dragon)<br>"
            "<span style='color:#34d399;'>Current Coverage:</span> Grass, Fighting, Fairy, Flying, Psychic, Fire, Dragon (7 Types).<br><br>"
            "<b>The 2 Golden Squad Expansions (To achieve 100% door unlock coverage for all 84+ Legendaries):</b><br>"
            "1. <span style='color:#38bdf8; font-weight:bold;'>Swampert</span> (Water / Ground) — Unlocks Marine Cave, Terra Cave, Diving Trenches, Desert Underpass, and Regi puzzles.<br>"
            "2. <span style='color:#f59e0b; font-weight:bold;'>Tyranitar</span> (Rock / Dark) — Unlocks Ancient Tomb, Desert Ruins, Distortion Nether Rifts, and Ruin Shrines.<br>"
            "<i>With these 8 Pokémon, you never need to visit the PC again for type-gated legendary access!</i>"
        )
        bp_desc.setWordWrap(True)
        bp_desc.setStyleSheet("color: #e2f4ea; font-size: 11px; line-height: 1.5; font-family: monospace;" if is_retro() else "color: #e2e8f0; font-size: 11px; line-height: 1.5;")
        bp_layout.addWidget(bp_desc)
        s_layout.addWidget(self.bp_frame)

        # Roadmap Sequence Cards
        phases = [
            ("PHASE 1: HOENN ANCIENT RUINS & WEATHER SUMMITS", "#059669", [
                ("Rayquaza", "Sky Pillar (Route 131 Rooftop)", "Defeat HoF. Bring Mach Bike or Flying Avatar (Aerodactyl).", "Flying / Dragon"),
                ("Kyogre", "Marine Cave (Routes 105, 125, 127, 129)", "Speak to Weather Institute scientist on Route 119. Bring Dive user (Swampert).", "Water"),
                ("Groudon", "Terra Cave (Routes 114, 115, 116, 118)", "Speak to Weather Institute scientist. Bring Ground / Water counter.", "Ground"),
                ("Regirock", "Desert Ruins (Route 111 Desert)", "Sealed Chamber unlock (Wailord #1, Relicanth #6, Dig). Walk 2 left, 2 down, Rock Smash.", "Rock"),
                ("Regice", "Island Cave (Route 105)", "Clockwise perimeter walk flush along room walls, inspect wall.", "Ice"),
                ("Registeel", "Ancient Tomb (Route 120)", "Stand at center and use Flash.", "Steel"),
                ("Latios", "Southern Island", "Post-League. Buy Eon Ticket at Battle Frontier Mart (100k). Male avatar + 6 Male Pokémon in party. Ferry from Slateport Harbor.", "Male protagonist + 6 Male Pokémon"),
                ("Latias", "Southern Island", "Post-League. Buy Eon Ticket at Battle Frontier Mart (100k). Female avatar + At least 5 Female Pokémon in party. Ferry from Lilycove Harbor.", "Female protagonist + 5 Female Pokémon"),
                ("Jirachi", "Mossdeep White Rock Space Center", "Interact with white rock with Wishing Stone or Space Center trigger.", "Steel / Psychic"),
                ("Deoxys", "Birth Island (Triangle Puzzle)", "Walk straight shortest path to hot triangle without running until it turns red.", "Psychic")
            ]),
            ("PHASE 2: KANTO EXPEDITIONS & SEAFOAM ISLES", "#0284c7", [
                ("Articuno", "Seafoam Islands B4F", "Bring Surf + Strength to redirect boulder rapids.", "Ice / Flying"),
                ("Zapdos", "Kanto Power Plant Inner Sanctum", "Surf from Route 10, navigate generator maze.", "Electric / Flying"),
                ("Moltres", "Mt. Ember Summit (One Island)", "Post-game Sevii Island access, navigate magma stairs.", "Fire / Flying"),
                ("Mewtwo", "Cerulean Cave Deep Basin", "Defeat Champion, complete Sevii Ruby/Sapphire quest.", "Psychic"),
                ("Mew", "Faraway Island Deep Foliage", "Old Sea Map ferry, play hide-and-seek in grass maze.", "Psychic")
            ]),
            ("PHASE 3: JOHTO SACRED SHRINES & BELL TOWERS", "#d97706", [
                ("Raikou", "Route 119 upper cliff behind Weather Institute", "Requires Acro Bike + Waterfall. Put Zapdos in Slot 1 + 5 Electric-types in party.", "Zapdos + 5 Electric-types"),
                ("Entei", "Jagged Pass / Magma Hideout", "Machinery chamber. Put Moltres in Slot 1 + 5 Fire-types in party. Pre-League accessible.", "Moltres + 5 Fire-types"),
                ("Suicune", "Route 130 island", "Put Entei in Slot 1, Raikou in Slot 2 + 4 Water-types in party.", "Entei + Raikou + 4 Water-types"),
                ("Lugia", "Whirl Islands Deep Chamber", "Bring Tidal Bell + Silver Wing from Goldenrod Radio Director + Whirlpool user.", "Psychic / Flying"),
                ("Ho-Oh", "Tin Tower Roof (Ecruteak City)", "Clear Bell + Rainbow Wing, defeat Ecruteak Wise Trio.", "Fire / Flying"),
                ("Celebi", "Ilex Forest Shrine", "Bring GS Ball to forest shrine.", "Grass / Psychic")
            ]),
            ("PHASE 4: DIMENSIONAL PORTALS & ULTRA EXPEDITIONS", "#7c3aed", [
                ("Dialga", "Mt. Pyre summit", "Post-League. Defeat Lucas; catch Uxie, Mesprit, Azelf. Avatar: Lucas, Dawn, or Cynthia. Party: At least 5 Gen 4 Pokémon (Dex 387–493).", "At least 5 Gen 4 Pokémon"),
                ("Palkia", "Mt. Pyre summit", "Post-League. Defeat Lucas; catch Uxie, Mesprit, Azelf. Avatar: Lucas, Dawn, or Cynthia. Party: At least 5 Gen 4 Pokémon (Dex 387–493).", "At least 5 Gen 4 Pokémon"),
                ("Giratina", "Mt. Pyre top floor", "Defeat/catch Dialga & Palkia. Same Gen 4 party + Sinnoh avatar.", "Dialga + Palkia + Sinnoh Avatar"),
                ("Reshiram", "Sky Pillar summit", "Defeat Rayquaza, unlock Battle Frontier. Avatar: N. Party: 5 Gen 5 Pokémon.", "5 Gen 5 Pokémon"),
                ("Zekrom", "Sky Pillar summit", "Defeat Rayquaza, unlock Battle Frontier. Avatar: N. Party: 5 Gen 5 Pokémon.", "5 Gen 5 Pokémon"),
                ("Kyurem", "Shoal Cave", "Defeat/catch Reshiram & Zekrom. Party: 5 Gen 5 Pokémon.", "Shoal Cave (Reshiram + Zekrom)"),
                ("Xerneas", "Safari Zone", "Avatar: Calem or Serena. Party: 5 Gen 6 Pokémon (Dex 650–721).", "5 Gen 6 Pokémon"),
                ("Yveltal", "Mt. Pyre summit", "Avatar: Calem or Serena. Party: 5 Gen 6 Pokémon.", "Mt. Pyre (Dark/Flying-types)"),
                ("Necrozma & Ultra Beasts", "Ultra Megalopolis Portal", "Post-game Wormhole portal exploration.", "Psychic / Ultra"),
                ("Wo-Chien", "Petalburg Woods", "Party: 5 Paldean Grass-types.", "Route 119 (Ominous Purple Stakes)"),
                ("Chien-Pao", "Shoal Cave bridge", "Party: 5 Paldean Ice-types.", "Shoal Cave (Ominous Yellow Stakes)"),
                ("Ting-Lu", "Route 111 Desert", "North of Regi cave. Party: 5 Paldean Ground-types.", "Route 111 Desert (Ominous Green Stakes)"),
                ("Chi-Yu", "Magma Hideout", "Groudon chamber. Party: 5 Paldean Fire-types.", "Magma Hideout (Ominous Blue Stakes)")
            ])
        ]

        for phase_title, phase_color, leg_list in phases:
            p_card = QFrame()
            p_card.setStyleSheet(f"""
                background-color: #0c121d;
                border: 1px solid {phase_color};
                border-radius: 8px;
                padding: 10px;
            """)
            pc_layout = QVBoxLayout(p_card)
            pc_layout.setContentsMargins(6, 4, 6, 4)
            pc_layout.setSpacing(6)

            pt_lbl = QLabel(phase_title)
            pt_lbl.setFont(QFont("Arial", 11, QFont.Bold))
            pt_lbl.setStyleSheet(f"color: {phase_color};")
            pc_layout.addWidget(pt_lbl)

            for mon_name, loc, req, synergy in leg_list:
                row_frame = QFrame()
                row_frame.setStyleSheet("""
                    background-color: #0f172a;
                    border: 1px solid #1e293b;
                    border-radius: 6px;
                    padding: 6px 8px;
                """)
                rf_layout = QHBoxLayout(row_frame)
                rf_layout.setContentsMargins(6, 4, 6, 4)
                rf_layout.setSpacing(10)

                self.cur.execute("SELECT id FROM pokemon WHERE name = ?", (mon_name,))
                sp_row = self.cur.fetchone()
                sp_id = sp_row[0] if sp_row else 0
                is_caught = sp_id in self.caught_species if sp_id else False

                sprite_box = QLabel()
                sprite_box.setFixedSize(40, 40)
                sprite_box.setAlignment(Qt.AlignCenter)
                pm = get_species_pixmap(sp_id, is_silhouette=(not is_caught))
                if pm:
                    sprite_box.setPixmap(pm.scaled(36, 36, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                else:
                    sprite_box.setText("👑")
                rf_layout.addWidget(sprite_box)

                info_col = QVBoxLayout()
                info_col.setSpacing(2)
                name_row = QHBoxLayout()
                name_row.setSpacing(6)

                m_name = QLabel(f"⭐ {mon_name}")
                m_name.setFont(QFont("Arial", 11, QFont.Bold))
                m_name.setStyleSheet("color: #f8fafc;")
                name_row.addWidget(m_name)

                m_loc = QLabel(f"📍 {loc}")
                m_loc.setStyleSheet("color: #38bdf8; font-size: 10px;")
                name_row.addWidget(m_loc)
                name_row.addStretch()
                info_col.addLayout(name_row)

                m_req = QLabel(f"🔓 {req}  •  <span style='color:#facc15;'>Synergy: {synergy}</span>")
                m_req.setWordWrap(True)
                m_req.setStyleSheet("color: #cbd5e1; font-size: 10px;")
                info_col.addWidget(m_req)
                rf_layout.addLayout(info_col, 1)

                s_lbl = QLabel("✓ CAUGHT" if is_caught else "○ MISSING")
                s_col = "#34d399" if is_caught else "#f59e0b"
                s_lbl.setStyleSheet(f"color: {s_col}; font-size: 10px; font-weight: bold; padding: 2px 8px; border: 1px solid {s_col}; border-radius: 4px;")
                rf_layout.addWidget(s_lbl)

                pc_layout.addWidget(row_frame)

            s_layout.addWidget(p_card)

        scroll.setWidget(s_widget)
        layout.addWidget(scroll, 1)
        self.tabs.addTab(tab, "🧭 Legendary Roadmap & Synergies")

    # ==========================================
    # TAB 5: CATCH CALCULATOR
    # ==========================================
    def create_calculator_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        self.calc_card = QFrame()
        self.calc_card.setObjectName("calc_card")
        self.calc_card.setStyleSheet("""
            QFrame#calc_card {
                background-color: #10262e;
                border-top: 2px solid #58b8a8;
                border-left: 2px solid #58b8a8;
                border-bottom: 2px solid #081820;
                border-right: 2px solid #081820;
                border-radius: 4px;
            }
        """ if is_retro() else """
            QFrame#calc_card {
                background-color: #0f172a;
                border: 1px solid #1e293b;
                border-radius: 8px;
            }
        """)
        c_layout = QVBoxLayout(self.calc_card)
        c_layout.setContentsMargins(16, 16, 16, 16)
        c_layout.setSpacing(12)

        title = QLabel("🎯 Quick Ball vs False Swipe Capture Calculator")
        title.setFont(QFont("Arial", 14, QFont.Bold))
        title.setStyleSheet("color: #00ff88; font-family: monospace;" if is_retro() else "color: #38bdf8;")
        c_layout.addWidget(title)

        grid = QGridLayout()
        grid.setSpacing(10)

        grid.addWidget(QLabel("Target Pokémon:"), 0, 0)
        self.calc_mon_combo = QComboBox()
        self.cur.execute("SELECT id, name, catch_rate FROM pokemon ORDER BY name ASC")
        for pid, name, cr in self.cur.fetchall():
            self.calc_mon_combo.addItem(f"{name} (CR: {cr})", pid)
        grid.addWidget(self.calc_mon_combo, 0, 1)

        grid.addWidget(QLabel("Remaining HP (%):"), 1, 0)
        self.calc_hp_spin = QSpinBox()
        self.calc_hp_spin.setRange(1, 100)
        self.calc_hp_spin.setValue(1)  # 1 HP (False Swipe)
        grid.addWidget(self.calc_hp_spin, 1, 1)

        grid.addWidget(QLabel("Status Condition:"), 2, 0)
        self.calc_status_combo = QComboBox()
        self.calc_status_combo.addItems(["Sleep / Freeze (2.5x)", "Paralyze / Poison / Burn (1.5x)", "None (1.0x)"])
        grid.addWidget(self.calc_status_combo, 2, 1)

        grid.addWidget(QLabel("Ball Type:"), 3, 0)
        self.calc_ball_combo = QComboBox()
        self.calc_ball_combo.addItems([
            "Quick Ball (Turn 1 - 5.0x)", "Ultra Ball (2.0x)", "Timer Ball (Turn 5+ - 4.0x)",
            "Dusk Ball (Cave/Night - 3.0x)", "Repeat Ball (Caught before - 3.5x)", "Net Ball (Water/Bug - 3.5x)"
        ])
        grid.addWidget(self.calc_ball_combo, 3, 1)

        c_layout.addLayout(grid)

        self.calc_result_lbl = QLabel("Capture Chance per Ball: --- %")
        self.calc_result_lbl.setStyleSheet("color: #00ff88; font-family: monospace; font-size: 16px; font-weight: bold; padding: 10px 0;" if is_retro() else "color: #34d399; font-size: 16px; font-weight: bold; padding: 10px 0;")
        c_layout.addWidget(self.calc_result_lbl)

        self.calc_btn = QPushButton("Calculate Capture Rate")
        self.calc_btn.setFixedHeight(34)
        self.calc_btn.setCursor(QCursor(Qt.PointingHandCursor))
        if is_retro():
            self.calc_btn.setStyleSheet("""
                QPushButton {
                    background-color: #183844;
                    border-top: 2px solid #58b8a8;
                    border-left: 2px solid #58b8a8;
                    border-bottom: 2px solid #081820;
                    border-right: 2px solid #081820;
                    color: #00ff88;
                    font-family: monospace;
                    font-weight: bold;
                    font-size: 12px;
                    border-radius: 2px;
                    padding: 6px 14px;
                }
                QPushButton:hover {
                    background-color: #245060;
                    color: #ffffff;
                }
                QPushButton:pressed {
                    border-top: 2px solid #081820;
                    border-left: 2px solid #081820;
                    border-bottom: 2px solid #58b8a8;
                    border-right: 2px solid #58b8a8;
                    padding-top: 8px; padding-left: 16px;
                }
            """)
        else:
            self.calc_btn.setStyleSheet("background-color: #2563eb; color: #FFFFFF; font-weight: bold; border-radius: 6px;")
        self.calc_btn.clicked.connect(self.calculate_catch_rate)
        c_layout.addWidget(self.calc_btn)

        layout.addWidget(self.calc_card)
        layout.addStretch()

        self.tabs.addTab(tab, "🎯 Catch Calculator")
        self.calculate_catch_rate()

    def calculate_catch_rate(self):
        play_sfx("menu_select.wav")
        pid = self.calc_mon_combo.currentData()
        self.cur.execute("SELECT hp, catch_rate FROM pokemon WHERE id = ?", (pid,))
        r = self.cur.fetchone()
        if not r: return
        base_hp, cr = r

        hp_pct = self.calc_hp_spin.value() / 100.0
        status_text = self.calc_status_combo.currentText()
        if "2.5x" in status_text:
            status_mod = 2.5
        elif "1.5x" in status_text:
            status_mod = 1.5
        else:
            status_mod = 1.0

        ball_text = self.calc_ball_combo.currentText()
        if "5.0x" in ball_text:
            ball_mod = 5.0
        elif "4.0x" in ball_text:
            ball_mod = 4.0
        elif "3.5x" in ball_text:
            ball_mod = 3.5
        elif "3.0x" in ball_text:
            ball_mod = 3.0
        elif "2.0x" in ball_text:
            ball_mod = 2.0
        else:
            ball_mod = 1.0

        # Gen 3 catch probability formula
        max_hp = base_hp * 2 + 110
        cur_hp = max(1, int(max_hp * hp_pct))
        a = (((3 * max_hp - 2 * cur_hp) * cr * ball_mod) / (3 * max_hp)) * status_mod
        if a >= 255:
            pct = 100.0
        else:
            b = 65536 / ((255 / a) ** 0.1875)
            pct = ((b / 65536) ** 4) * 100.0

        self.calc_result_lbl.setText(f"Capture Probability per Throw: {pct:.1f}%")

    # ==========================================
    # SAVE FILE WATCHER & SYNCHRONIZATION
    # ==========================================
    def init_save_watcher(self):
        """Lightweight non-polling background watcher for save file modifications."""
        self.save_timer = QTimer(self)
        self.save_timer.timeout.connect(self.check_save_file_update)
        self.save_timer.start(2500)  # Check every 2.5 seconds without burning CPU

    def check_save_file_update(self):
        if not os.path.exists(self.save_path):
            return
        mtime = os.path.getmtime(self.save_path)
        if mtime > self.last_save_mtime:
            self.last_save_mtime = mtime
            self.sync_save_file(is_auto=True)

    def sync_save_file(self, is_auto: bool = False):
        if not os.path.exists(self.save_path):
            return
        try:
            c_cnt, s_cnt = quetzal_save_reader.update_database_user_pokedex(self.save_path, DB_PATH, existing_conn=self.conn)
            self.cur.execute("SELECT species_id FROM caught_pokemon")
            self.caught_species = set(r[0] for r in self.cur.fetchall())

            self.update_stats_header()
            if is_retro():
                self.live_watcher_badge.setText(f"● LIVE SYNC ({time.strftime('%H:%M:%S')})")
            else:
                self.live_watcher_badge.setText(f"🟢 Live Save Synced ({time.strftime('%H:%M:%S')})")

            # Reload active route
            self.load_current_route_encounters()
            self.populate_pokedex_list()
            self.populate_legendaries_cards()

            if hasattr(self, 'map_widget'):
                self.map_widget.load_data_from_db(DB_PATH)

            if hasattr(self, 'retro_pokedex_view'):
                self.retro_pokedex_view.load_data()

            if hasattr(self, 'start_menu'):
                self.start_menu.update_player_info()
        except Exception as e:
            print("Auto-save sync error:", e)

    def closeEvent(self, event):
        self.save_timer.stop()
        self.conn.close()
        super().closeEvent(event)


def main():
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)
    window = QuetzalMasterApp()
    if "--fullscreen" in sys.argv:
        window.showFullScreen()
    else:
        window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
