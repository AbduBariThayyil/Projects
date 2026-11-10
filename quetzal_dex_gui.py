#!/usr/bin/env python3
"""
Pokémon Quetzal Master Pokédex & DexNav Route Explorer (PySide6)
Comprehensive retro gaming HUD for Pokémon Quetzal:
- 1,499 Pokémon (All 9 Gens + Megas + Forms) with Base Stats, Types, Learnsets, Evolution Conditions
- Interactive In-Game DexNav Route HUD matching the GBA / ORAS aesthetic:
  * Habitat Boxes: WATER (5 slots), LAND (12 slots), BEACH (3 slots), HIDDEN DETECTOR
  * Right-Hand Information Card with tactile green SEARCH [A] button, Search Level, Hidden Ability, Held Items
  * Caught / Uncaught Filter Toggles ("Show All", "Uncaught Only", "Caught Only")
- 103 Clean Legendary & Mythical Encounters with Location, Level, Prerequisites, and Party Synergies
- Interactive Catch Probability Calculator
- Persistent SQLite Caught Pokémon Tracker
"""

import sys
import os
import sqlite3
import re
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QListWidget, QTableWidget, QTableWidgetItem, QTabWidget,
    QLabel, QHeaderView, QSplitter, QProgressBar, QComboBox, QGroupBox,
    QFormLayout, QSpinBox, QPushButton, QFrame, QTextEdit, QScrollArea,
    QGridLayout, QButtonGroup, QRadioButton, QSizePolicy
)
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont, QColor, QPalette, QCursor

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "quetzal_database.db")

# Authentic Pokémon Type Colors (Gen 3 / ORAS Palette)
AUTHENTIC_TYPE_COLORS = {
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
    "Bug":      ("#A8B820", "#6D7815"),
    "Rock":     ("#B8A038", "#786824"),
    "Ghost":    ("#705898", "#493963"),
    "Dragon":   ("#7038F8", "#4924A1"),
    "Dark":     ("#705848", "#49392F"),
    "Steel":    ("#B8B8D0", "#787887"),
    "Fairy":    ("#EE99AC", "#9B6470"),
    "Stellar":  ("#4682B4", "#2B506E"),
    "Mystery":  ("#68A090", "#44685E"),
}

RETRO_GAMING_STYLESHEET = """
QMainWindow {
    background-color: #0b0f17;
}
QWidget {
    color: #e2e8f0;
    font-family: 'Segoe UI', 'Ubuntu', 'DejaVu Sans', sans-serif;
    font-size: 13px;
}
QTabWidget::pane {
    border: 2px solid #1c2638;
    background-color: #101624;
    border-radius: 8px;
    margin-top: -1px;
}
QTabBar::tab {
    background-color: #151d2c;
    color: #8fa0b5;
    padding: 10px 22px;
    margin-right: 4px;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    border: 1px solid #1c2638;
    border-bottom: none;
    font-weight: bold;
    font-size: 13px;
}
QTabBar::tab:selected {
    background-color: #101624;
    color: #38ef7d;
    border: 2px solid #1c2638;
    border-bottom: 2px solid #101624;
    border-top: 3px solid #38ef7d;
}
QTabBar::tab:hover:!selected {
    background-color: #1d273a;
    color: #ffffff;
}
QLineEdit, QComboBox, QSpinBox {
    background-color: #141b29;
    border: 1px solid #28374f;
    border-radius: 6px;
    padding: 7px 12px;
    color: #ffffff;
    selection-background-color: #10b981;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {
    border: 1px solid #38ef7d;
    background-color: #192335;
}
QGroupBox {
    border: 1px solid #25334a;
    border-radius: 8px;
    margin-top: 14px;
    padding-top: 16px;
    font-weight: bold;
    color: #38ef7d;
    background-color: #121927;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 2px 10px;
    background-color: #1a2538;
    border: 1px solid #25334a;
    border-radius: 4px;
    color: #38ef7d;
}
QListWidget {
    background-color: #131a27;
    border: 1px solid #25334a;
    border-radius: 6px;
    padding: 4px;
}
QListWidget::item {
    padding: 7px 10px;
    border-radius: 4px;
    margin-bottom: 2px;
}
QListWidget::item:selected {
    background-color: #059669;
    color: #ffffff;
    font-weight: bold;
}
QListWidget::item:hover:!selected {
    background-color: #1d273a;
}
QTableWidget {
    background-color: #121927;
    border: 1px solid #25334a;
    gridline-color: #1d273a;
    border-radius: 6px;
    selection-background-color: #1e3a5f;
    selection-color: #ffffff;
}
QTableWidget::item {
    padding: 8px;
    border-bottom: 1px solid #1a2334;
}
QHeaderView::section {
    background-color: #0b111a;
    color: #38ef7d;
    font-weight: bold;
    padding: 8px;
    border: none;
    border-bottom: 2px solid #25334a;
}
QProgressBar {
    background-color: #172131;
    border: 1px solid #25334a;
    border-radius: 4px;
    text-align: center;
    color: #ffffff;
    font-size: 11px;
    font-weight: bold;
}
QProgressBar::chunk {
    border-radius: 3px;
    background-color: #10b981;
}
QScrollBar:vertical {
    border: none;
    background: #0b0f17;
    width: 10px;
    margin: 0px;
    border-radius: 5px;
}
QScrollBar::handle:vertical {
    background: #25334a;
    min-height: 25px;
    border-radius: 5px;
}
QScrollBar::handle:vertical:hover {
    background: #38ef7d;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
"""

def clean_wiki_text(s):
    """Strip raw markdown, HTML artifacts, and line breaks into clean text."""
    if not s:
        return ""
    # Convert <br> or <br/> into clean bullet points
    s = re.sub(r'<br\s*/?>', '\n • ', s)
    s = re.sub(r'<[^>]+>', '', s)
    # Remove markdown bold/italics and code fences
    s = re.sub(r'\*\*(.*?)\*\*', r'\1', s)
    s = re.sub(r'\*(.*?)\*', r'\1', s)
    s = re.sub(r'`(.*?)`', r'\1', s)
    # Clean multiple spaces while preserving intentional newlines
    lines = [re.sub(r'[ \t]+', ' ', line).strip() for line in s.split('\n')]
    return '\n'.join([line for line in lines if line]).strip()


class TypeBadge(QLabel):
    """Retro pixel-style type pill badge."""
    def __init__(self, type_name):
        super().__init__()
        bg, border = AUTHENTIC_TYPE_COLORS.get(type_name, ("#68A090", "#44685E"))
        self.setText(f" {type_name.upper()} ")
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet(f"""
            QLabel {{
                background-color: {bg};
                border: 1px solid {border};
                border-radius: 4px;
                color: #FFFFFF;
                font-size: 11px;
                font-weight: bold;
                padding: 3px 8px;
            }}
        """)


class DexNavSlotCard(QFrame):
    """
    Individual Encounter Slot Card inside Habitat Boxes.
    Clickable to select and update the right-hand information card.
    Double-click or click Pokéball to toggle caught status.
    """
    clicked = Signal(dict)
    caught_toggled = Signal(int, str, bool)

    def __init__(self, slot_data, is_selected=False, filter_mode="Show All"):
        super().__init__()
        self.slot_data = slot_data
        self.is_selected = is_selected
        self.filter_mode = filter_mode
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setFixedHeight(82)

        self.init_ui()
        self.update_style()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(2)

        # Header Row: Slot # & Chance %
        top_row = QHBoxLayout()
        top_row.setSpacing(4)
        slot_num = self.slot_data.get("slot", 1)
        chance = self.slot_data.get("chance", 0)

        self.slot_lbl = QLabel(f"SLOT {slot_num}")
        self.slot_lbl.setStyleSheet("color: #94a3b8; font-size: 10px; font-weight: bold;")
        top_row.addWidget(self.slot_lbl)

        top_row.addStretch()

        self.chance_badge = QLabel(f"{chance}%")
        self.chance_badge.setStyleSheet("""
            background-color: #1e293b;
            color: #38ef7d;
            border-radius: 3px;
            font-size: 10px;
            font-weight: bold;
            padding: 1px 4px;
        """)
        top_row.addWidget(self.chance_badge)
        layout.addLayout(top_row)

        # Main Row: Pokéball caught badge + Pokémon Name
        mid_row = QHBoxLayout()
        mid_row.setSpacing(6)

        is_caught = self.slot_data.get("is_caught", False)
        self.ball_btn = QPushButton("🔴" if is_caught else "⚪")
        self.ball_btn.setFixedSize(22, 22)
        self.ball_btn.setToolTip("Click to toggle Caught status")
        self.ball_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                font-size: 13px;
                padding: 0px;
            }
            QPushButton:hover {
                background: #334155;
                border-radius: 11px;
            }
        """)
        self.ball_btn.clicked.connect(self.on_ball_clicked)
        mid_row.addWidget(self.ball_btn)

        mon_name = self.slot_data.get("species_name", "Unknown")
        self.name_lbl = QLabel(mon_name)
        self.name_lbl.setStyleSheet("color: #FFFFFF; font-size: 12px; font-weight: bold;")
        mid_row.addWidget(self.name_lbl)
        mid_row.addStretch()

        layout.addLayout(mid_row)

        # Bottom Row: Dex # & Level Range
        bot_row = QHBoxLayout()
        bot_row.setSpacing(4)
        dex_num = self.slot_data.get("species_id", 0)
        min_lv = self.slot_data.get("min_level", 1)
        max_lv = self.slot_data.get("max_level", 1)
        lv_txt = f"Lv.{min_lv}" if min_lv == max_lv else f"Lv.{min_lv}–{max_lv}"

        self.dex_lbl = QLabel(f"#{dex_num:03d}")
        self.dex_lbl.setStyleSheet("color: #64748b; font-size: 10px;")
        bot_row.addWidget(self.dex_lbl)

        bot_row.addStretch()

        self.lv_lbl = QLabel(lv_txt)
        self.lv_lbl.setStyleSheet("color: #cbd5e1; font-size: 10px; font-weight: bold;")
        bot_row.addWidget(self.lv_lbl)

        layout.addLayout(bot_row)

    def on_ball_clicked(self):
        new_state = not self.slot_data.get("is_caught", False)
        self.slot_data["is_caught"] = new_state
        self.ball_btn.setText("🔴" if new_state else "⚪")
        self.caught_toggled.emit(self.slot_data.get("species_id", 0), self.slot_data.get("species_name", ""), new_state)
        self.update_style()

    def set_selected(self, selected):
        self.is_selected = selected
        self.update_style()

    def set_filter_mode(self, mode):
        self.filter_mode = mode
        self.update_style()

    def update_style(self):
        is_caught = self.slot_data.get("is_caught", False)
        bg = "#162032"
        border = "#25334a"
        opacity = "1.0"

        if self.is_selected:
            border = "#00d2ff"
            bg = "#1e2f4a"
        elif self.filter_mode == "Uncaught Only":
            if not is_caught:
                border = "#f59e0b"
                bg = "#292416"
            else:
                bg = "#101622"
                border = "#1c2434"
                opacity = "0.35"
        elif self.filter_mode == "Caught Only":
            if is_caught:
                border = "#10b981"
                bg = "#132b22"
            else:
                bg = "#101622"
                border = "#1c2434"
                opacity = "0.35"

        self.setStyleSheet(f"""
            DexNavSlotCard {{
                background-color: {bg};
                border: 2px solid {border};
                border-radius: 8px;
            }}
            DexNavSlotCard:hover {{
                border-color: #38ef7d;
                background-color: #1c2a42;
            }}
        """)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.slot_data)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.on_ball_clicked()
        super().mouseDoubleClickEvent(event)


class HabitatBox(QFrame):
    """
    Curved habitat container matching DexNav boxes:
    - Box 1: WATER (Blue header with Pokéball completion badge)
    - Box 2: LAND (Green header with grass texture & badge)
    - Box 3: BEACH (Orange header with sand texture & badge)
    - Box 4: HIDDEN (Red header with detector slot)
    """
    def __init__(self, title, color_theme, max_slots=12, is_grid=False):
        super().__init__()
        self.title_text = title
        self.color_theme = color_theme  # (header_bg, accent_color, border_color)
        self.max_slots = max_slots
        self.is_grid = is_grid

        self.init_ui()

    def init_ui(self):
        header_bg, accent, border_col = self.color_theme
        self.setStyleSheet(f"""
            HabitatBox {{
                background-color: #101726;
                border: 2px solid {border_col};
                border-radius: 10px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header Bar
        self.header_frame = QFrame()
        self.header_frame.setFixedHeight(34)
        self.header_frame.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {header_bg}, stop:1 #111827);
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                border-bottom: 2px solid {accent};
                padding: 0 10px;
            }}
        """)
        h_layout = QHBoxLayout(self.header_frame)
        h_layout.setContentsMargins(10, 0, 10, 0)

        self.title_lbl = QLabel(self.title_text)
        self.title_lbl.setStyleSheet(f"color: #FFFFFF; font-weight: bold; font-size: 13px; letter-spacing: 1px;")
        h_layout.addWidget(self.title_lbl)

        h_layout.addStretch()

        self.badge_lbl = QLabel("⚪ 0/0")
        self.badge_lbl.setStyleSheet(f"""
            background-color: rgba(0, 0, 0, 0.4);
            color: {accent};
            border-radius: 4px;
            padding: 2px 8px;
            font-size: 11px;
            font-weight: bold;
        """)
        h_layout.addWidget(self.badge_lbl)

        layout.addWidget(self.header_frame)

        # Content Container
        self.content_widget = QWidget()
        self.content_layout = QGridLayout(self.content_widget) if self.is_grid else QHBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(8, 8, 8, 8)
        self.content_layout.setSpacing(6)
        layout.addWidget(self.content_widget)

    def set_completion(self, caught_count, total_count):
        if total_count == 0:
            self.badge_lbl.setText("✕ NONE")
            self.badge_lbl.setStyleSheet("background-color: rgba(0,0,0,0.4); color: #64748b; font-size: 11px; font-weight: bold; padding: 2px 8px; border-radius: 4px;")
        elif caught_count >= total_count:
            self.badge_lbl.setText(f"⭐ {caught_count}/{total_count} COMPLETE")
            self.badge_lbl.setStyleSheet("background-color: #065f46; color: #34d399; font-size: 11px; font-weight: bold; padding: 2px 8px; border-radius: 4px;")
        else:
            self.badge_lbl.setText(f"⚪ {caught_count}/{total_count}")
            accent = self.color_theme[1]
            self.badge_lbl.setStyleSheet(f"background-color: rgba(0,0,0,0.4); color: {accent}; font-size: 11px; font-weight: bold; padding: 2px 8px; border-radius: 4px;")

    def show_empty(self, message="NO ENCOUNTERS ON THIS ROUTE"):
        # Clear content
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        empty_frame = QFrame()
        empty_frame.setFixedHeight(64)
        empty_frame.setStyleSheet("""
            background-color: #0d131f;
            border: 1px dashed #243048;
            border-radius: 6px;
        """)
        e_layout = QHBoxLayout(empty_frame)
        msg_lbl = QLabel(f"✕  {message}")
        msg_lbl.setStyleSheet("color: #475569; font-weight: bold; font-size: 12px;")
        msg_lbl.setAlignment(Qt.AlignCenter)
        e_layout.addWidget(msg_lbl)

        if self.is_grid:
            self.content_layout.addWidget(empty_frame, 0, 0, 1, 6)
        else:
            self.content_layout.addWidget(empty_frame)


class DexNavInfoCard(QFrame):
    """
    Right-Hand Telemetry Information Card:
    - Big green tactile SEARCH [A] button
    - Selected Pokémon Name & Dex #
    - Authentic type badges
    - Interactive Catch Status Toggle Button
    - SEARCH LEVEL progress gauge
    - HIDDEN ABILITY & HELD ITEMS display
    - Quick shortcut to open Mon in Pokédex tab
    """
    search_requested = Signal(dict)
    catch_toggled = Signal(int, str, bool)
    open_in_pokedex = Signal(int)

    def __init__(self):
        super().__init__()
        self.current_data = None
        self.search_level = 10
        self.init_ui()

    def init_ui(self):
        self.setStyleSheet("""
            DexNavInfoCard {
                background-color: #121927;
                border: 2px solid #25334a;
                border-radius: 10px;
            }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        # Big Green SEARCH [A] Button
        self.search_btn = QPushButton("SEARCH  [A]")
        self.search_btn.setFixedHeight(44)
        self.search_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.search_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #22c55e, stop:1 #15803d);
                border: 2px solid #4ade80;
                border-radius: 8px;
                color: #FFFFFF;
                font-family: 'Segoe UI', 'Ubuntu', sans-serif;
                font-size: 15px;
                font-weight: 900;
                letter-spacing: 2px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #4ade80, stop:1 #16a34a);
                border-color: #86efac;
            }
            QPushButton:pressed {
                background: #15803d;
                border-color: #166534;
            }
        """)
        self.search_btn.clicked.connect(self.on_search_clicked)
        layout.addWidget(self.search_btn)

        # Mon Header: Name & Dex #
        header_box = QVBoxLayout()
        header_box.setSpacing(2)

        self.dex_lbl = QLabel("#---")
        self.dex_lbl.setStyleSheet("color: #38ef7d; font-size: 12px; font-weight: bold;")
        header_box.addWidget(self.dex_lbl)

        self.name_lbl = QLabel("Select a Pokémon")
        self.name_lbl.setStyleSheet("color: #FFFFFF; font-size: 20px; font-weight: 900;")
        header_box.addWidget(self.name_lbl)

        layout.addLayout(header_box)

        # Type Badges
        self.types_box = QHBoxLayout()
        self.types_box.setSpacing(6)
        layout.addLayout(self.types_box)

        # Catch Status Toggle Button
        self.catch_toggle_btn = QPushButton("⚪  UNCAUGHT  (Click to Catch)")
        self.catch_toggle_btn.setFixedHeight(32)
        self.catch_toggle_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.catch_toggle_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                border: 1px solid #475569;
                border-radius: 6px;
                color: #cbd5e1;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #334155;
            }
        """)
        self.catch_toggle_btn.clicked.connect(self.on_toggle_caught_clicked)
        layout.addWidget(self.catch_toggle_btn)

        # Search Level Gauge
        sl_box = QVBoxLayout()
        sl_box.setSpacing(4)
        sl_top = QHBoxLayout()
        self.sl_title = QLabel("SEARCH LEVEL:")
        self.sl_title.setStyleSheet("color: #ef4444; font-size: 11px; font-weight: 900; letter-spacing: 1px;")
        sl_top.addWidget(self.sl_title)
        self.sl_val = QLabel("Lv. 10")
        self.sl_val.setStyleSheet("color: #FFFFFF; font-size: 12px; font-weight: bold;")
        sl_top.addWidget(self.sl_val, alignment=Qt.AlignRight)
        sl_box.addLayout(sl_top)

        self.sl_bar = QProgressBar()
        self.sl_bar.setRange(0, 100)
        self.sl_bar.setValue(10)
        self.sl_bar.setFixedHeight(12)
        self.sl_bar.setStyleSheet("""
            QProgressBar {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 4px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #ef4444, stop:1 #f87171);
                border-radius: 3px;
            }
        """)
        sl_box.addWidget(self.sl_bar)
        layout.addLayout(sl_box)

        # Telemetry Card (Hidden Ability, Items, Rates)
        telemetry_frame = QFrame()
        telemetry_frame.setStyleSheet("""
            background-color: #0c121d;
            border: 1px solid #1e293b;
            border-radius: 8px;
            padding: 8px;
        """)
        t_layout = QVBoxLayout(telemetry_frame)
        t_layout.setSpacing(6)

        # Hidden Ability
        t_layout.addWidget(QLabel("HIDDEN ABILITY:"))
        self.ha_lbl = QLabel("Frisk")
        self.ha_lbl.setStyleSheet("""
            background-color: #2e1065;
            color: #d8b4fe;
            border: 1px solid #7c3aed;
            border-radius: 4px;
            padding: 4px 8px;
            font-weight: bold;
            font-size: 12px;
        """)
        t_layout.addWidget(self.ha_lbl)

        # Abilities
        t_layout.addWidget(QLabel("STANDARD ABILITIES:"))
        self.std_ab_lbl = QLabel("Run Away / Keen Eye")
        self.std_ab_lbl.setStyleSheet("color: #cbd5e1; font-size: 12px; padding-left: 2px;")
        t_layout.addWidget(self.std_ab_lbl)

        # Held Items
        t_layout.addWidget(QLabel("HELD ITEMS:"))
        self.items_lbl = QLabel("NONE")
        self.items_lbl.setStyleSheet("""
            background-color: #1e293b;
            color: #fcd34d;
            border: 1px solid #475569;
            border-radius: 4px;
            padding: 4px 8px;
            font-weight: bold;
            font-size: 12px;
        """)
        t_layout.addWidget(self.items_lbl)

        # Method & Chance
        self.encounter_info_lbl = QLabel("Habitat: Tall Grass • Rate: 20%")
        self.encounter_info_lbl.setStyleSheet("color: #94a3b8; font-size: 11px;")
        t_layout.addWidget(self.encounter_info_lbl)

        layout.addWidget(telemetry_frame)

        # Status text feedback label
        self.status_feedback = QLabel("")
        self.status_feedback.setStyleSheet("color: #38ef7d; font-size: 11px; font-weight: bold;")
        self.status_feedback.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_feedback)

        layout.addStretch()

        # View in Pokédex Shortcut Button
        self.dex_shortcut_btn = QPushButton("📖 View Learnset & Stats in Pokédex")
        self.dex_shortcut_btn.setFixedHeight(34)
        self.dex_shortcut_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.dex_shortcut_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                border: 1px solid #38ef7d;
                border-radius: 6px;
                color: #38ef7d;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #065f46;
                color: #FFFFFF;
            }
        """)
        self.dex_shortcut_btn.clicked.connect(self.on_open_pokedex_clicked)
        layout.addWidget(self.dex_shortcut_btn)

    def set_data(self, data):
        self.current_data = data
        dex_id = data.get("species_id", 0)
        name = data.get("species_name", "Unknown")
        t1 = data.get("type1", "Normal")
        t2 = data.get("type2", None)
        ha = data.get("hidden_ability", "None")
        abilities = data.get("abilities", "None")
        items = data.get("held_items", "NONE")
        method = data.get("method", "Wild")
        chance = data.get("chance", 0)
        min_l = data.get("min_level", 1)
        max_l = data.get("max_level", 1)
        is_caught = data.get("is_caught", False)

        self.dex_lbl.setText(f"#{dex_id:04d}")
        self.name_lbl.setText(name.upper())

        # Update type badges
        while self.types_box.count():
            item = self.types_box.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for t in [t1, t2]:
            if t and t != "Type_0" and (t != t1 or self.types_box.count() == 0):
                self.types_box.addWidget(TypeBadge(t))
        self.types_box.addStretch()

        # Catch state
        if is_caught:
            self.catch_toggle_btn.setText("🔴  CAUGHT  (Click to Release)")
            self.catch_toggle_btn.setStyleSheet("""
                QPushButton {
                    background-color: #065f46;
                    border: 1px solid #34d399;
                    border-radius: 6px;
                    color: #FFFFFF;
                    font-weight: bold;
                    font-size: 12px;
                }
                QPushButton:hover { background-color: #047857; }
            """)
        else:
            self.catch_toggle_btn.setText("⚪  UNCAUGHT  (Click to Catch)")
            self.catch_toggle_btn.setStyleSheet("""
                QPushButton {
                    background-color: #1e293b;
                    border: 1px solid #475569;
                    border-radius: 6px;
                    color: #cbd5e1;
                    font-weight: bold;
                    font-size: 12px;
                }
                QPushButton:hover { background-color: #334155; }
            """)

        # Search level
        self.search_level = 15 if is_caught else 5
        self.sl_val.setText(f"Lv. {self.search_level}")
        self.sl_bar.setValue(self.search_level)

        # Telemetry
        self.ha_lbl.setText(ha if ha and ha != "None" else "None")
        self.std_ab_lbl.setText(abilities if abilities else "None")
        self.items_lbl.setText(items if items and items != "None" else "NONE")

        lv_str = f"Lv. {min_l}" if min_l == max_l else f"Lv. {min_l}–{max_l}"
        self.encounter_info_lbl.setText(f"Habitat: {method} • Rate: {chance}% • {lv_str}")
        self.status_feedback.setText("")

    def on_search_clicked(self):
        if not self.current_data:
            return
        name = self.current_data.get("species_name", "")
        self.search_level = min(100, self.search_level + 1)
        self.sl_val.setText(f"Lv. {self.search_level}")
        self.sl_bar.setValue(self.search_level)

        self.status_feedback.setText(f"🔍 Rustling detected! {name} found! (Search Lv. {self.search_level})")
        QTimer.singleShot(3500, lambda: self.status_feedback.setText(""))
        self.search_requested.emit(self.current_data)

    def on_toggle_caught_clicked(self):
        if not self.current_data:
            return
        new_state = not self.current_data.get("is_caught", False)
        self.current_data["is_caught"] = new_state
        pid = self.current_data.get("species_id", 0)
        pname = self.current_data.get("species_name", "")

        self.set_data(self.current_data)
        self.catch_toggled.emit(pid, pname, new_state)

    def on_open_pokedex_clicked(self):
        if self.current_data:
            self.open_in_pokedex.emit(self.current_data.get("species_id", 1))


class QuetzalDexApp(QMainWindow):
    """Lead Orchestrator Window for Pokémon Quetzal DexNav & Database."""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("⚡ Pokémon Quetzal DexNav Route Explorer & Compendium")
        self.resize(1340, 880)
        self.setStyleSheet(RETRO_GAMING_STYLESHEET)

        self.conn = sqlite3.connect(DB_PATH)
        self.cur = self.conn.cursor()

        # Ensure caught_pokemon table exists
        self.cur.execute("""
            CREATE TABLE IF NOT EXISTS caught_pokemon (
                species_id INTEGER PRIMARY KEY,
                species_name TEXT,
                caught_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.conn.commit()

        # Load caught species into set for fast O(1) checks
        self.cur.execute("SELECT species_id FROM caught_pokemon")
        self.caught_species = set(row[0] for row in self.cur.fetchall())

        self.filter_mode = "Show All"  # "Show All", "Uncaught Only", "Caught Only"
        self.current_route_name = "ROUTE 101"
        self.current_region = "Hoenn"

        self.init_ui()

    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(14, 14, 14, 14)
        main_layout.setSpacing(10)

        # Top App Title Bar
        title_box = QHBoxLayout()
        title_label = QLabel("⚡ Pokémon Quetzal DexNav & Master Explorer")
        title_label.setFont(QFont("Arial", 16, QFont.Bold))
        title_label.setStyleSheet("color: #38ef7d; letter-spacing: 1px;")
        title_box.addWidget(title_label)

        self.caught_status_lbl = QLabel(f"Pokédex Completion: {len(self.caught_species)} / 1,499 Caught ({len(self.caught_species)/1499*100:.1f}%)")
        self.caught_status_lbl.setStyleSheet("color: #94a3b8; font-size: 12px; font-weight: bold;")
        title_box.addWidget(self.caught_status_lbl, alignment=Qt.AlignRight | Qt.AlignVCenter)
        main_layout.addLayout(title_box)

        # Tabs
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        self.create_dexnav_tab()
        self.create_pokedex_tab()
        self.create_legendaries_tab()
        self.create_calculator_tab()

    # ==========================================
    # TAB 1: DEXNAV ROUTE EXPLORER (Centerpiece)
    # ==========================================
    def create_dexnav_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Top Control Bar (Search, Region, Route Selector, Filters)
        top_bar = QFrame()
        top_bar.setStyleSheet("""
            QFrame {
                background-color: #121927;
                border: 1px solid #25334a;
                border-radius: 8px;
                padding: 4px 8px;
            }
        """)
        tb_layout = QHBoxLayout(top_bar)
        tb_layout.setSpacing(8)

        # [R] Search Mon
        tb_layout.addWidget(QLabel("[R] Search Mon:"))
        self.mon_quick_search = QLineEdit()
        self.mon_quick_search.setPlaceholderText("Find route with species (e.g. Sentret, Ralts, #161)...")
        self.mon_quick_search.setFixedWidth(220)
        self.mon_quick_search.textChanged.connect(self.on_quick_search_mon)
        tb_layout.addWidget(self.mon_quick_search)

        tb_layout.addSpacing(10)

        # Region Selector
        tb_layout.addWidget(QLabel("Region:"))
        self.route_region_combo = QComboBox()
        self.route_region_combo.addItems(["Hoenn", "Kanto", "Sevii Islands", "All Regions"])
        self.route_region_combo.currentIndexChanged.connect(self.on_region_changed)
        tb_layout.addWidget(self.route_region_combo)

        # Route Selector & Arrows
        tb_layout.addWidget(QLabel("Location:"))
        self.prev_route_btn = QPushButton("◀")
        self.prev_route_btn.setFixedWidth(28)
        self.prev_route_btn.clicked.connect(self.on_prev_route)
        tb_layout.addWidget(self.prev_route_btn)

        self.route_combo = QComboBox()
        self.route_combo.setMinimumWidth(180)
        self.route_combo.currentIndexChanged.connect(self.on_route_changed)
        tb_layout.addWidget(self.route_combo)

        self.next_route_btn = QPushButton("▶")
        self.next_route_btn.setFixedWidth(28)
        self.next_route_btn.clicked.connect(self.on_next_route)
        tb_layout.addWidget(self.next_route_btn)

        tb_layout.addSpacing(12)

        # Filter Toggles: Show All, Uncaught Only, Caught Only
        tb_layout.addWidget(QLabel("Filter:"))
        self.filter_btn_all = QPushButton("Show All")
        self.filter_btn_uncaught = QPushButton("Uncaught Only")
        self.filter_btn_caught = QPushButton("Caught Only")

        self.filter_buttons = [self.filter_btn_all, self.filter_btn_uncaught, self.filter_btn_caught]
        for btn in self.filter_buttons:
            btn.setCheckable(True)
            btn.setFixedHeight(28)
            btn.setCursor(QCursor(Qt.PointingHandCursor))
            tb_layout.addWidget(btn)

        self.filter_btn_all.setChecked(True)
        self.filter_btn_all.clicked.connect(lambda: self.set_caught_filter("Show All"))
        self.filter_btn_uncaught.clicked.connect(lambda: self.set_caught_filter("Uncaught Only"))
        self.filter_btn_caught.clicked.connect(lambda: self.set_caught_filter("Caught Only"))
        self.update_filter_button_styles()

        tb_layout.addStretch()

        # Sync with Save File Button
        self.sync_sav_btn = QPushButton("🔄 Sync .SAV")
        self.sync_sav_btn.setFixedHeight(28)
        self.sync_sav_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.sync_sav_btn.setToolTip("Sync caught Pokémon directly from Moemon Quetzal.sav")
        self.sync_sav_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                border: 1px solid #3b82f6;
                border-radius: 4px;
                color: #60a5fa;
                font-weight: bold;
                padding: 4px 10px;
            }
            QPushButton:hover { background-color: #1d4ed8; color: #FFFFFF; }
        """)
        self.sync_sav_btn.clicked.connect(self.sync_save_file)
        tb_layout.addWidget(self.sync_sav_btn)

        # Route Completion Badge
        self.route_progress_badge = QLabel("Route Completion: 0/0")
        self.route_progress_badge.setStyleSheet("""
            background-color: #065f46;
            color: #34d399;
            border-radius: 4px;
            font-weight: bold;
            padding: 4px 10px;
            font-size: 11px;
        """)
        tb_layout.addWidget(self.route_progress_badge)

        layout.addWidget(top_bar)

        # Main Splitter: Habitat Boxes (Left 70%) | Info Card (Right 30%)
        splitter = QSplitter(Qt.Horizontal)

        # Left Container with ScrollArea for Habitat Boxes
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        left_content = QWidget()
        left_layout = QVBoxLayout(left_content)
        left_layout.setContentsMargins(0, 0, 8, 0)
        left_layout.setSpacing(10)

        # Habitat Box 1: WATER (Blue header, 5 slots)
        self.box_water = HabitatBox("WATER", ("#1e3a8a", "#60a5fa", "#2563eb"), max_slots=5, is_grid=False)
        left_layout.addWidget(self.box_water)

        # Habitat Box 2: LAND (Green header, 12 slots, 2x6 grid)
        self.box_land = HabitatBox("LAND", ("#14532d", "#4ade80", "#16a34a"), max_slots=12, is_grid=True)
        left_layout.addWidget(self.box_land)

        # Bottom Row: Box 3 (BEACH) & Box 4 (HIDDEN DETECTOR)
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(10)

        self.box_beach = HabitatBox("BEACH / FISHING / ROCKS", ("#7c2d12", "#fb923c", "#ea580c"), max_slots=3, is_grid=False)
        bottom_row.addWidget(self.box_beach, 1)

        self.box_hidden = HabitatBox("HIDDEN DETECTOR", ("#7f1d1d", "#f87171", "#dc2626"), max_slots=1, is_grid=False)
        bottom_row.addWidget(self.box_hidden, 1)

        left_layout.addLayout(bottom_row)
        left_scroll.setWidget(left_content)
        splitter.addWidget(left_scroll)

        # Right Container: Telemetry Info Card
        self.info_card = DexNavInfoCard()
        self.info_card.search_requested.connect(self.on_dexnav_search_pulse)
        self.info_card.catch_toggled.connect(self.on_catch_status_toggled)
        self.info_card.open_in_pokedex.connect(self.jump_to_pokedex_mon)
        splitter.addWidget(self.info_card)

        splitter.setStretchFactor(0, 7)
        splitter.setStretchFactor(1, 3)
        layout.addWidget(splitter)

        self.tabs.addTab(tab, "📟 DexNav Route HUD")

        # Populate route list
        self.populate_routes()

    def populate_routes(self):
        region = self.route_region_combo.currentText()
        sql = "SELECT DISTINCT location_name FROM encounters"
        params = []
        if region != "All Regions":
            sql += " WHERE region = ?"
            params.append(region)
        sql += " ORDER BY location_name ASC"

        self.cur.execute(sql, params)
        routes = [row[0] for row in self.cur.fetchall()]

        self.route_combo.blockSignals(True)
        self.route_combo.clear()
        for r in routes:
            self.route_combo.addItem(r)

        # Default to ROUTE 101 if present
        idx = self.route_combo.findText("ROUTE 101")
        if idx >= 0:
            self.route_combo.setCurrentIndex(idx)
        elif self.route_combo.count() > 0:
            self.route_combo.setCurrentIndex(0)
        self.route_combo.blockSignals(False)

        self.load_current_route_dexnav()

    def on_region_changed(self):
        self.populate_routes()

    def on_route_changed(self):
        self.load_current_route_dexnav()

    def on_prev_route(self):
        idx = self.route_combo.currentIndex()
        if idx > 0:
            self.route_combo.setCurrentIndex(idx - 1)

    def on_next_route(self):
        idx = self.route_combo.currentIndex()
        if idx < self.route_combo.count() - 1:
            self.route_combo.setCurrentIndex(idx + 1)

    def set_caught_filter(self, mode):
        self.filter_mode = mode
        self.update_filter_button_styles()
        self.load_current_route_dexnav()

    def update_filter_button_styles(self):
        for btn, name in zip(self.filter_buttons, ["Show All", "Uncaught Only", "Caught Only"]):
            active = (name == self.filter_mode)
            btn.setChecked(active)
            if active:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #059669;
                        border: 1px solid #34d399;
                        border-radius: 4px;
                        color: #FFFFFF;
                        font-weight: bold;
                        padding: 4px 10px;
                    }
                """)
            else:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #1e293b;
                        border: 1px solid #334155;
                        border-radius: 4px;
                        color: #94a3b8;
                        padding: 4px 10px;
                    }
                    QPushButton:hover { background-color: #24344d; color: #FFFFFF; }
                """)

    def load_current_route_dexnav(self):
        route_name = self.route_combo.currentText()
        if not route_name:
            return
        self.current_route_name = route_name

        region = self.route_region_combo.currentText()
        sql = """
            SELECT e.method, e.slot, e.chance, e.min_level, e.max_level, e.species_id, e.species_name,
                   p.type1, p.type2, p.abilities, p.hidden_ability, p.held_items,
                   p.hp, p.atk, p.def, p.spa, p.spd, p.spe, p.bst
            FROM encounters e
            LEFT JOIN pokemon p ON e.species_id = p.id
            WHERE e.location_name = ?
        """
        params = [route_name]
        if region != "All Regions":
            sql += " AND e.region = ?"
            params.append(region)
        sql += " ORDER BY e.method, e.slot ASC"

        self.cur.execute(sql, params)
        rows = self.cur.fetchall()

        # Categorize slots
        land_encs = []
        water_encs = []
        beach_encs = []

        seen_slots = set()
        for r in rows:
            meth = r[0]
            slot_id = r[1]
            sp_id = r[5]
            key = (meth, slot_id, sp_id)
            if key in seen_slots:
                continue
            seen_slots.add(key)

            data = {
                "method": r[0], "slot": r[1], "chance": r[2], "min_level": r[3], "max_level": r[4],
                "species_id": r[5], "species_name": r[6], "type1": r[7], "type2": r[8],
                "abilities": r[9], "hidden_ability": r[10], "held_items": r[11],
                "hp": r[12], "atk": r[13], "def": r[14], "spa": r[15], "spd": r[16], "spe": r[17], "bst": r[18],
                "is_caught": r[5] in self.caught_species
            }

            if meth == "Tall Grass":
                land_encs.append(data)
            elif meth == "Surfing":
                water_encs.append(data)
            elif "Fishing" in meth or "Rock Smash" in meth:
                beach_encs.append(data)

        # Clear and populate boxes
        self.populate_habitat_box(self.box_water, water_encs, is_grid=False, max_cols=5)
        self.populate_habitat_box(self.box_land, land_encs, is_grid=True, max_cols=6)
        self.populate_habitat_box(self.box_beach, beach_encs, is_grid=False, max_cols=3)

        # Hidden slot: pick the rarest or first mon with hidden ability from land
        hidden_candidate = None
        for enc in land_encs:
            if enc.get("hidden_ability") and enc.get("hidden_ability") != "None":
                hidden_candidate = dict(enc)
                hidden_candidate["slot"] = "HA"
                hidden_candidate["chance"] = 5
                break
        if not hidden_candidate and land_encs:
            hidden_candidate = dict(land_encs[0])
            hidden_candidate["slot"] = "DETECTOR"

        if hidden_candidate:
            self.populate_habitat_box(self.box_hidden, [hidden_candidate], is_grid=False, max_cols=1)
        else:
            self.box_hidden.show_empty("NO DETECTOR SIGNAL")

        # Total completion stats
        all_species_on_route = set([e["species_id"] for e in (land_encs + water_encs + beach_encs)])
        caught_on_route = sum(1 for sid in all_species_on_route if sid in self.caught_species)
        total_unique = len(all_species_on_route)

        pct = (caught_on_route / total_unique * 100) if total_unique > 0 else 0
        self.route_progress_badge.setText(f"{route_name}: {caught_on_route} / {total_unique} Caught ({pct:.0f}%)")

        # Select first mon into Right Card
        initial_mon = None
        if land_encs: initial_mon = land_encs[0]
        elif water_encs: initial_mon = water_encs[0]
        elif beach_encs: initial_mon = beach_encs[0]

        if initial_mon:
            self.select_slot_in_card(initial_mon)

    def populate_habitat_box(self, habitat_box, encounters, is_grid=False, max_cols=6):
        # Clear layout
        while habitat_box.content_layout.count():
            item = habitat_box.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not encounters:
            habitat_box.show_empty()
            habitat_box.set_completion(0, 0)
            return

        caught_count = sum(1 for e in encounters if e["is_caught"])
        habitat_box.set_completion(caught_count, len(encounters))

        for idx, enc in enumerate(encounters):
            card = DexNavSlotCard(enc, is_selected=False, filter_mode=self.filter_mode)
            card.clicked.connect(self.select_slot_in_card)
            card.caught_toggled.connect(self.on_catch_status_toggled)

            if is_grid:
                row = idx // max_cols
                col = idx % max_cols
                habitat_box.content_layout.addWidget(card, row, col)
            else:
                habitat_box.content_layout.addWidget(card)

    def select_slot_in_card(self, mon_data):
        self.info_card.set_data(mon_data)

    def on_catch_status_toggled(self, species_id, species_name, is_caught):
        if is_caught:
            self.caught_species.add(species_id)
            self.cur.execute("INSERT OR REPLACE INTO caught_pokemon (species_id, species_name) VALUES (?, ?)", (species_id, species_name))
        else:
            self.caught_species.discard(species_id)
            self.cur.execute("DELETE FROM caught_pokemon WHERE species_id = ?", (species_id,))
        self.conn.commit()

        # Update global counter
        self.caught_status_lbl.setText(f"Pokédex Completion: {len(self.caught_species)} / 1,499 Caught ({len(self.caught_species)/1499*100:.1f}%)")

        # Refresh current route display to update badges and dimmed/highlighted cards
        self.load_current_route_dexnav()

    def on_dexnav_search_pulse(self, mon_data):
        # Simulated scan feedback
        pass

    def on_quick_search_mon(self, query):
        q = query.strip().lower()
        if not q or len(q) < 2:
            return
        # Find first location that has this pokemon
        self.cur.execute("""
            SELECT location_name FROM encounters
            WHERE LOWER(species_name) LIKE ? OR CAST(species_id AS TEXT) = ?
            LIMIT 1
        """, (f"%{q}%", q))
        row = self.cur.fetchone()
        if row:
            loc = row[0]
            idx = self.route_combo.findText(loc)
            if idx >= 0 and idx != self.route_combo.currentIndex():
                self.route_combo.setCurrentIndex(idx)

    def jump_to_pokedex_mon(self, species_id):
        self.tabs.setCurrentIndex(1)
        # Find row in mon_list
        for i in range(self.mon_list.count()):
            item = self.mon_list.item(i)
            if item.text().startswith(f"#{species_id:04d}"):
                self.mon_list.setCurrentRow(i)
                break

    # ==========================================
    # TAB 2: POKÉDEX & LEARNSET EXPLORER
    # ==========================================
    def create_pokedex_tab(self):
        tab = QWidget()
        layout = QHBoxLayout(tab)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(14)

        # Left Column: Search & Pokémon List
        left_box = QVBoxLayout()
        left_box.setSpacing(8)

        search_label = QLabel("Search Pokémon (Name, #ID):")
        self.mon_search = QLineEdit()
        self.mon_search.setPlaceholderText("e.g. Breloom, Rayquaza, 285...")
        self.mon_search.textChanged.connect(self.filter_pokemon_list)

        self.mon_list = QListWidget()
        self.mon_list.currentRowChanged.connect(self.on_pokemon_selected)

        left_box.addWidget(search_label)
        left_box.addWidget(self.mon_search)
        left_box.addWidget(self.mon_list)

        left_container = QWidget()
        left_container.setLayout(left_box)
        left_container.setFixedWidth(280)

        # Right Column: Details & Tabs (Stats, Learnset, Evolutions)
        right_box = QVBoxLayout()
        right_box.setSpacing(12)

        # Mon Header Card
        self.header_card = QFrame()
        self.header_card.setStyleSheet("background-color: #121927; border: 1px solid #25334a; border-radius: 8px; padding: 14px;")
        card_layout = QHBoxLayout(self.header_card)

        self.mon_name_lbl = QLabel("Select a Pokémon")
        self.mon_name_lbl.setFont(QFont("Arial", 18, QFont.Bold))
        self.mon_name_lbl.setStyleSheet("color: #FFFFFF;")
        card_layout.addWidget(self.mon_name_lbl)

        self.type_badges_box = QHBoxLayout()
        card_layout.addLayout(self.type_badges_box)
        card_layout.addStretch()

        self.mon_caught_btn = QPushButton("⚪ Mark Caught")
        self.mon_caught_btn.setCheckable(True)
        self.mon_caught_btn.setFixedHeight(30)
        self.mon_caught_btn.clicked.connect(self.on_pokedex_caught_clicked)
        card_layout.addWidget(self.mon_caught_btn)

        self.catch_rate_lbl = QLabel("")
        self.catch_rate_lbl.setStyleSheet("color: #94a3b8; font-size: 12px; font-weight: bold;")
        card_layout.addWidget(self.catch_rate_lbl)

        right_box.addWidget(self.header_card)

        # Base Stats Panel
        stats_group = QGroupBox("Base Stats")
        stats_layout = QVBoxLayout(stats_group)
        self.stat_bars = {}
        for stat in ["HP", "Attack", "Defense", "Sp. Atk", "Sp. Def", "Speed"]:
            row = QHBoxLayout()
            lbl = QLabel(f"{stat:8}")
            lbl.setFixedWidth(70)
            lbl.setStyleSheet("color: #E1E1E6; font-weight: bold;")
            bar = QProgressBar()
            bar.setRange(0, 255)
            bar.setValue(0)
            bar.setFixedHeight(18)
            row.addWidget(lbl)
            row.addWidget(bar)
            stats_layout.addLayout(row)
            self.stat_bars[stat] = bar

        self.bst_lbl = QLabel("Base Stat Total (BST): 0")
        self.bst_lbl.setStyleSheet("color: #38ef7d; font-weight: bold; margin-top: 4px;")
        stats_layout.addWidget(self.bst_lbl, alignment=Qt.AlignRight)
        right_box.addWidget(stats_group)

        # Evolutions Card
        self.evo_group = QGroupBox("Evolution Tree & Requirements")
        evo_layout = QVBoxLayout(self.evo_group)
        self.evo_text = QLabel("No evolution data.")
        self.evo_text.setStyleSheet("color: #E1E1E6; font-size: 13px;")
        evo_layout.addWidget(self.evo_text)
        right_box.addWidget(self.evo_group)

        # Learnset Table
        learn_group = QGroupBox("Level-Up Moves")
        learn_layout = QVBoxLayout(learn_group)
        self.learn_table = QTableWidget()
        self.learn_table.setColumnCount(7)
        self.learn_table.setHorizontalHeaderLabels(["Level", "Move", "Type", "Power", "Acc", "PP", "Priority"])
        self.learn_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        learn_layout.addWidget(self.learn_table)
        right_box.addWidget(learn_group)

        right_container = QWidget()
        right_container.setLayout(right_box)

        # Splitter
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left_container)
        splitter.addWidget(right_container)
        splitter.setStretchFactor(1, 3)
        layout.addWidget(splitter)

        self.tabs.addTab(tab, "📖 Pokédex & Moves")

        # Load all pokemon into list
        self.cur.execute("SELECT id, name FROM pokemon ORDER BY id ASC")
        self.all_pokemon = self.cur.fetchall()
        for pid, name in self.all_pokemon:
            is_c = pid in self.caught_species
            ball = "🔴" if is_c else "⚪"
            self.mon_list.addItem(f"#{pid:04d}  {ball} {name}")

        if self.mon_list.count() > 0:
            self.mon_list.setCurrentRow(284)

    def filter_pokemon_list(self, text):
        query = text.strip().lower()
        self.mon_list.clear()
        for pid, name in self.all_pokemon:
            if query in name.lower() or query in str(pid):
                is_c = pid in self.caught_species
                ball = "🔴" if is_c else "⚪"
                self.mon_list.addItem(f"#{pid:04d}  {ball} {name}")
        if self.mon_list.count() > 0:
            self.mon_list.setCurrentRow(0)

    def on_pokemon_selected(self, row):
        if row < 0:
            return
        item = self.mon_list.item(row)
        if not item:
            return
        pid = int(item.text().split()[0].replace("#", ""))

        self.cur.execute("SELECT name, hp, atk, def, spa, spd, spe, bst, type1, type2, catch_rate FROM pokemon WHERE id=?", (pid,))
        row_data = self.cur.fetchone()
        if not row_data:
            return

        name, hp, atk, df, spa, spd, spe, bst, t1, t2, cr = row_data

        self.mon_name_lbl.setText(f"#{pid:04d} {name}")
        self.catch_rate_lbl.setText(f"Catch Rate: {cr} / 255")

        # Catch button state
        is_c = pid in self.caught_species
        self.mon_caught_btn.setChecked(is_c)
        if is_c:
            self.mon_caught_btn.setText("🔴 Caught")
            self.mon_caught_btn.setStyleSheet("background-color: #065f46; color: #FFFFFF; font-weight: bold; border-radius: 4px; padding: 4px 10px;")
        else:
            self.mon_caught_btn.setText("⚪ Uncaught")
            self.mon_caught_btn.setStyleSheet("background-color: #1e293b; color: #94a3b8; font-weight: bold; border-radius: 4px; padding: 4px 10px;")

        # Clear type badges
        while self.type_badges_box.count():
            item = self.type_badges_box.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for t in [t1, t2]:
            if t and t != "Type_0" and (t != t1 or self.type_badges_box.count() == 0):
                self.type_badges_box.addWidget(TypeBadge(t))

        # Update stats
        stats_map = {"HP": hp, "Attack": atk, "Defense": df, "Sp. Atk": spa, "Sp. Def": spd, "Speed": spe}
        for s_name, val in stats_map.items():
            bar = self.stat_bars[s_name]
            bar.setValue(val)
            bar.setFormat(f"{val}")
            col = "#38ef7d" if val >= 90 else ("#fcd34d" if val >= 60 else "#f87171")
            bar.setStyleSheet(f"QProgressBar::chunk {{ background-color: {col}; border-radius: 3px; }}")

        self.bst_lbl.setText(f"Base Stat Total (BST): {bst}")

        # Update Evolutions
        self.cur.execute("SELECT target_name, method_desc FROM evolutions WHERE pokemon_id=?", (pid,))
        evos = self.cur.fetchall()
        if evos:
            evo_str = "  ➔  " + " | ".join([f"<b>{t_name}</b> ({desc})" for t_name, desc in evos])
            self.evo_text.setText(evo_str)
        else:
            self.evo_text.setText("Does not evolve (Final Stage or Standalone).")

        # Update Learnset
        self.cur.execute("""
            SELECT l.level, l.move_name, m.type, m.power, m.accuracy, m.pp, m.priority
            FROM learnsets l
            LEFT JOIN moves m ON l.move_id = m.id
            WHERE l.pokemon_id = ?
            ORDER BY l.level ASC
        """, (pid,))
        learn_rows = self.cur.fetchall()

        self.learn_table.setRowCount(len(learn_rows))
        for r_idx, (lv, m_name, m_type, pwr, acc, pp, pri) in enumerate(learn_rows):
            pwr_txt = str(pwr) if pwr > 0 else "—"
            acc_txt = f"{acc}%" if acc > 0 else "—"
            pri_txt = f"+{pri}" if pri > 0 else (str(pri) if pri < 0 else "0")

            self.learn_table.setItem(r_idx, 0, QTableWidgetItem(f"Lv. {lv}"))
            self.learn_table.setItem(r_idx, 1, QTableWidgetItem(m_name))
            self.learn_table.setItem(r_idx, 2, QTableWidgetItem(m_type or "Normal"))
            self.learn_table.setItem(r_idx, 3, QTableWidgetItem(pwr_txt))
            self.learn_table.setItem(r_idx, 4, QTableWidgetItem(acc_txt))
            self.learn_table.setItem(r_idx, 5, QTableWidgetItem(str(pp)))
            self.learn_table.setItem(r_idx, 6, QTableWidgetItem(pri_txt))

    def on_pokedex_caught_clicked(self):
        row = self.mon_list.currentRow()
        if row < 0:
            return
        item = self.mon_list.item(row)
        pid = int(item.text().split()[0].replace("#", ""))
        pname = item.text().split()[-1]

        is_c = pid in self.caught_species
        new_state = not is_c
        self.on_catch_status_toggled(pid, pname, new_state)

        # Update row label in list
        ball = "🔴" if new_state else "⚪"
        item.setText(f"#{pid:04d}  {ball} {pname}")
        self.on_pokemon_selected(row)

    # ==========================================
    # TAB 3: LEGENDARY & MYTHICAL GUIDE
    # ==========================================
    def create_legendaries_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Filters Box
        top_box = QHBoxLayout()
        top_box.setSpacing(10)

        top_box.addWidget(QLabel("Generation:"))
        self.leg_gen_combo = QComboBox()
        self.leg_gen_combo.addItems([
            "All Generations", "Hoenn Native", "Generation 1 (Kanto)", "Generation 2 (Johto)",
            "Generation 4 (Sinnoh)", "Generation 5 (Unova)", "Generation 6 (Kalos)",
            "Generation 7 (Alola & Ultra Beasts)", "Generation 8 (Galar & Hisui)",
            "Generation 9 (Paldea & Paradox Encounters)", "Multi-Region Special"
        ])
        self.leg_gen_combo.currentIndexChanged.connect(self.filter_legendaries)
        top_box.addWidget(self.leg_gen_combo)

        top_box.addWidget(QLabel("Search Legendary:"))
        self.leg_search = QLineEdit()
        self.leg_search.setPlaceholderText("Filter by Name, Location, Item, or Synergy Setup...")
        self.leg_search.textChanged.connect(self.filter_legendaries)
        top_box.addWidget(self.leg_search)

        layout.addLayout(top_box)

        # Main Table: Clean, well-spaced retro table with dedicated columns
        self.leg_table = QTableWidget()
        self.leg_table.setColumnCount(6)
        self.leg_table.setHorizontalHeaderLabels([
            "Status", "Legendary", "Generation", "Level", "Location", "Prerequisites & Party Synergies"
        ])
        self.leg_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.leg_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.leg_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.leg_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.leg_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.leg_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)
        self.leg_table.setWordWrap(True)
        self.leg_table.verticalHeader().setDefaultSectionSize(48)
        self.leg_table.currentCellChanged.connect(lambda r, c, pr, pc: self.on_legendary_selected(r))
        layout.addWidget(self.leg_table)

        # Bottom Details Card
        self.leg_detail_card = QFrame()
        self.leg_detail_card.setStyleSheet("""
            background-color: #121927;
            border: 1px solid #25334a;
            border-radius: 8px;
            padding: 12px;
        """)
        d_layout = QVBoxLayout(self.leg_detail_card)
        d_layout.setSpacing(6)

        d_top = QHBoxLayout()
        self.leg_detail_name = QLabel("Select a Legendary to view complete walkthrough")
        self.leg_detail_name.setFont(QFont("Arial", 14, QFont.Bold))
        self.leg_detail_name.setStyleSheet("color: #38ef7d;")
        d_top.addWidget(self.leg_detail_name)

        self.leg_detail_loc = QLabel("")
        self.leg_detail_loc.setStyleSheet("color: #fcd34d; font-weight: bold;")
        d_top.addWidget(self.leg_detail_loc, alignment=Qt.AlignRight)
        d_layout.addLayout(d_top)

        self.leg_detail_req = QTextEdit()
        self.leg_detail_req.setReadOnly(True)
        self.leg_detail_req.setFixedHeight(75)
        self.leg_detail_req.setStyleSheet("""
            QTextEdit {
                background-color: #0c121d;
                border: 1px solid #1e293b;
                border-radius: 6px;
                color: #e2e8f0;
                font-size: 13px;
                padding: 6px;
            }
        """)
        d_layout.addWidget(self.leg_detail_req)

        self.leg_detail_synergy = QLabel("")
        self.leg_detail_synergy.setStyleSheet("color: #93c5fd; font-weight: bold; font-size: 12px;")
        d_layout.addWidget(self.leg_detail_synergy)

        layout.addWidget(self.leg_detail_card)

        self.tabs.addTab(tab, "⚔️ Legendary & Mythical Guide")
        self.filter_legendaries()

    def filter_legendaries(self):
        gen = self.leg_gen_combo.currentText()
        query = self.leg_search.text().strip().lower()

        sql = "SELECT name, generation, level, location, requirements, synergy FROM legendaries WHERE 1=1"
        params = []

        if gen != "All Generations":
            sql += " AND generation LIKE ?"
            params.append(f"%{gen.split('(')[0].strip()}%")
        if query:
            sql += " AND (LOWER(name) LIKE ? OR LOWER(location) LIKE ? OR LOWER(requirements) LIKE ? OR LOWER(synergy) LIKE ?)"
            params.extend([f"%{query}%", f"%{query}%", f"%{query}%", f"%{query}%"])

        sql += " ORDER BY generation, name"
        self.cur.execute(sql, params)
        rows = self.cur.fetchall()

        self.leg_table.setRowCount(len(rows))
        for r_idx, (name, g, lv, loc, req, syn) in enumerate(rows):
            # Clean text
            clean_req = clean_wiki_text(req)
            clean_loc = clean_wiki_text(loc)
            clean_syn = clean_wiki_text(syn)

            # Check if species is in caught list
            self.cur.execute("SELECT id FROM pokemon WHERE LOWER(name) = LOWER(?) LIMIT 1", (name,))
            p_row = self.cur.fetchone()
            is_c = (p_row[0] in self.caught_species) if p_row else False
            status_txt = "🔴" if is_c else "⚪"

            req_syn_combined = f"{clean_req}"
            if clean_syn:
                req_syn_combined += f"\n[Synergy Setup: {clean_syn}]"

            self.leg_table.setItem(r_idx, 0, QTableWidgetItem(status_txt))
            self.leg_table.setItem(r_idx, 1, QTableWidgetItem(name))
            self.leg_table.setItem(r_idx, 2, QTableWidgetItem(g))
            self.leg_table.setItem(r_idx, 3, QTableWidgetItem(lv or "Lv 70"))
            self.leg_table.setItem(r_idx, 4, QTableWidgetItem(clean_loc))
            self.leg_table.setItem(r_idx, 5, QTableWidgetItem(req_syn_combined))

        if len(rows) > 0:
            self.leg_table.setCurrentCell(0, 1)

    def on_legendary_selected(self, row):
        if row < 0 or row >= self.leg_table.rowCount():
            return
        name_item = self.leg_table.item(row, 1)
        gen_item = self.leg_table.item(row, 2)
        lv_item = self.leg_table.item(row, 3)
        loc_item = self.leg_table.item(row, 4)
        req_item = self.leg_table.item(row, 5)

        if not name_item:
            return

        name = name_item.text()
        gen = gen_item.text() if gen_item else ""
        lv = lv_item.text() if lv_item else ""
        loc = loc_item.text() if loc_item else ""
        req = req_item.text() if req_item else ""

        self.leg_detail_name.setText(f"{name}  •  {lv}  ({gen})")
        self.leg_detail_loc.setText(f"📍 {loc}")
        self.leg_detail_req.setText(req)

    # ==========================================
    # TAB 4: CATCH RATE CALCULATOR
    # ==========================================
    def create_calculator_tab(self):
        tab = QWidget()
        layout = QHBoxLayout(tab)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(20)

        # Calculator Form
        form_group = QGroupBox("Catch Parameters")
        form = QFormLayout(form_group)
        form.setSpacing(12)

        self.calc_mon_combo = QComboBox()
        for pid, name in self.all_pokemon:
            self.calc_mon_combo.addItem(f"#{pid:04d} {name}", pid)
        self.calc_mon_combo.currentIndexChanged.connect(self.calculate_catch_rate)
        form.addRow("Target Pokémon:", self.calc_mon_combo)

        self.calc_hp_spin = QSpinBox()
        self.calc_hp_spin.setRange(1, 100)
        self.calc_hp_spin.setValue(1)
        self.calc_hp_spin.setSuffix("% HP Remaining")
        self.calc_hp_spin.valueChanged.connect(self.calculate_catch_rate)
        form.addRow("HP Status (False Swipe):", self.calc_hp_spin)

        self.calc_status_combo = QComboBox()
        self.calc_status_combo.addItems([
            "Asleep / Frozen (2.5x - Spore!)",
            "Paralyzed / Burned / Poisoned (1.5x)",
            "None (1.0x)"
        ])
        self.calc_status_combo.currentIndexChanged.connect(self.calculate_catch_rate)
        form.addRow("Status Condition:", self.calc_status_combo)

        layout.addWidget(form_group, 1)

        # Results Panel
        results_group = QGroupBox("Poké Ball Catch Probabilities")
        res_layout = QVBoxLayout(results_group)
        res_layout.setSpacing(10)

        self.ball_bars = {}
        balls = [
            ("Quick Ball (Turn 1 - 5.0x)", "Quick"),
            ("Timer Ball (Turn 11+ - 4.0x)", "Timer"),
            ("Repeat Ball (Caught before - 3.5x)", "Repeat"),
            ("Dusk Ball (Cave / Night - 3.0x)", "Dusk"),
            ("Ultra Ball (Standard - 2.0x)", "Ultra"),
            ("Great Ball (1.5x)", "Great"),
            ("Poké Ball (1.0x)", "Poke")
        ]

        for label, key in balls:
            row = QHBoxLayout()
            lbl = QLabel(f"{label:32}")
            lbl.setStyleSheet("font-weight: bold;")
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setFixedHeight(22)
            row.addWidget(lbl)
            row.addWidget(bar)
            res_layout.addLayout(row)
            self.ball_bars[key] = bar

        layout.addWidget(results_group, 2)
        self.tabs.addTab(tab, "🎯 Catch Probability Calculator")
        self.calculate_catch_rate()

    def calculate_catch_rate(self):
        idx = self.calc_mon_combo.currentIndex()
        if idx < 0:
            return
        pid = self.calc_mon_combo.currentData()

        self.cur.execute("SELECT hp, catch_rate FROM pokemon WHERE id=?", (pid,))
        row = self.cur.fetchone()
        if not row:
            return
        base_hp, cr = row

        hp_pct = self.calc_hp_spin.value() / 100.0
        st_idx = self.calc_status_combo.currentIndex()
        st_mult = 2.5 if st_idx == 0 else (1.5 if st_idx == 1 else 1.0)

        multipliers = {
            "Quick": 5.0, "Timer": 4.0, "Repeat": 3.5, "Dusk": 3.0,
            "Ultra": 2.0, "Great": 1.5, "Poke": 1.0
        }

        for key, mult in multipliers.items():
            a = ((3.0 - 2.0 * hp_pct) * cr * mult * st_mult) / 3.0
            if a >= 255:
                prob = 100.0
            else:
                p_shake = (a / 255.0) ** 0.75
                prob = (p_shake ** 4) * 100.0

            prob = min(100.0, max(0.0, prob))
            bar = self.ball_bars[key]
            bar.setValue(int(prob))
            bar.setFormat(f"{prob:.1f}%")
            col = "#38ef7d" if prob >= 70 else ("#fcd34d" if prob >= 35 else "#f87171")
            bar.setStyleSheet(f"QProgressBar::chunk {{ background-color: {col}; border-radius: 4px; }}")

    def closeEvent(self, event):
        self.conn.close()
        event.accept()


def main():
    app = QApplication(sys.argv)
    window = QuetzalDexApp()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
