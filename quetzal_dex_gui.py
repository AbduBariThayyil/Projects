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
from typing import Dict, List, Optional, Tuple

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QLineEdit, QListWidget, QListWidgetItem,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QScrollArea, QFrame, QSplitter, QTabWidget, QProgressBar, QGridLayout,
    QSizePolicy, QSpinBox, QCheckBox
)
from PySide6.QtGui import (
    QFont, QColor, QPixmap, QIcon, QPainter, QBrush, QPen, QCursor
)
from PySide6.QtCore import Qt, QTimer, Signal

import quetzal_save_reader
from regional_map_widget import RegionalMapWidget, normalize_loc

# ==========================================
# CONSTANTS & ASSET PATHS
# ==========================================
PROJECT_DIR = "/home/vibecoder/Projects"
DB_PATH = os.path.join(PROJECT_DIR, "quetzal_database.db")
DEFAULT_SAV_PATH = "/home/vibecoder/Games/Console Games/GBA/Moemon Quetzal.sav"
ASSETS_SPRITES_DIR = os.path.join(PROJECT_DIR, "assets", "sprites")
ASSETS_SILHOUETTES_DIR = os.path.join(PROJECT_DIR, "assets", "silhouettes")

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

def get_species_pixmap(species_id: int, is_silhouette: bool = False) -> Optional[QPixmap]:
    """Load cached 2D sprite or silhouette pixmap."""
    target_dir = ASSETS_SILHOUETTES_DIR if is_silhouette else ASSETS_SPRITES_DIR
    path = os.path.join(target_dir, f"{species_id}.png")
    if os.path.exists(path):
        pm = QPixmap(path)
        if not pm.isNull():
            return pm
    return None


class TypeBadge(QLabel):
    """Clean rounded dual-type pill badge."""
    def __init__(self, type_name: str, parent=None):
        super().__init__(parent)
        self.type_name = type_name
        self.setText(type_name.upper())
        self.setAlignment(Qt.AlignCenter)
        self.setFixedHeight(20)
        self.setContentsMargins(8, 2, 8, 2)
        font = QFont("Arial", 9, QFont.Bold)
        self.setFont(font)

        bg, border = TYPE_COLORS.get(type_name, ("#475569", "#334155"))
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


class ModernEncounterCard(QFrame):
    """
    Modern responsive encounter card.
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

        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.init_ui()

    def init_ui(self):
        self.setMinimumWidth(220)
        self.setFixedHeight(120)

        self.update_card_style(is_selected=False)

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(10, 8, 10, 8)
        main_layout.setSpacing(10)

        # Left Column: Large Pokémon Sprite in soft rounded container
        sprite_box = QFrame()
        sprite_box.setFixedSize(68, 68)
        sprite_box.setStyleSheet("""
            background-color: #0b111a;
            border: 1px solid #1e2b3e;
            border-radius: 8px;
        """)
        sb_layout = QVBoxLayout(sprite_box)
        sb_layout.setContentsMargins(0, 0, 0, 0)
        self.sprite_lbl = QLabel()
        self.sprite_lbl.setAlignment(Qt.AlignCenter)
        pm = get_species_pixmap(self.species_id, is_silhouette=False)
        if pm:
            self.sprite_lbl.setPixmap(pm.scaled(60, 60, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            self.sprite_lbl.setText("🐾")
        sb_layout.addWidget(self.sprite_lbl)
        main_layout.addWidget(sprite_box, alignment=Qt.AlignVCenter)

        # Center Column: Info & Details
        info_col = QVBoxLayout()
        info_col.setContentsMargins(0, 0, 0, 0)
        info_col.setSpacing(3)

        # Row 1: Dex # + Name
        title_box = QHBoxLayout()
        title_box.setSpacing(6)
        dex_num = QLabel(f"#{self.species_id:04d}")
        dex_num.setStyleSheet("color: #64748b; font-size: 11px; font-weight: bold;")
        title_box.addWidget(dex_num)

        name_lbl = QLabel(self.species_name)
        name_lbl.setStyleSheet("color: #f8fafc; font-size: 14px; font-weight: bold;")
        title_box.addWidget(name_lbl)
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

        rate_lbl = QLabel(f"{meth_icon} {meth} ({chance}%) • Lv.{min_l}–{max_l}")
        rate_lbl.setStyleSheet("color: #94a3b8; font-size: 11px;")
        meta_box.addWidget(rate_lbl)
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

    def update_card_style(self, is_selected: bool = False):
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

    def update_caught_button_state(self):
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
            self.clicked.emit(self.mon_data)
        super().mousePressEvent(event)


class SpeciesInspectorDrawer(QFrame):
    """
    Sleek right-side species telemetry panel.
    Displays base stats bars, catch probabilities, abilities, held items,
    evolution chain, and jump-to-pokedex button.
    """
    open_in_pokedex = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_species_id = None
        self.init_ui()

    def init_ui(self):
        self.setFixedWidth(340)
        self.setStyleSheet("""
            SpeciesInspectorDrawer {
                background-color: #101726;
                border: 1px solid #1e293b;
                border-radius: 8px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        # Header Title
        title_box = QHBoxLayout()
        header_title = QLabel("🔍 SPECIES TELEMETRY")
        header_title.setFont(QFont("Arial", 11, QFont.Bold))
        header_title.setStyleSheet("color: #38bdf8; letter-spacing: 1px;")
        title_box.addWidget(header_title)
        layout.addLayout(title_box)

        # Sprite + Name banner
        banner = QFrame()
        banner.setObjectName("banner_frame")
        banner.setStyleSheet("""
            QFrame#banner_frame {
                background-color: #0c121d;
                border: 1px solid #1e293b;
                border-radius: 6px;
            }
            QLabel {
                border: none;
                background: transparent;
                padding: 0px;
            }
        """)
        b_layout = QHBoxLayout(banner)
        b_layout.setContentsMargins(8, 8, 8, 8)
        b_layout.setSpacing(10)

        self.sprite_lbl = QLabel()
        self.sprite_lbl.setFixedSize(68, 68)
        self.sprite_lbl.setAlignment(Qt.AlignCenter)
        b_layout.addWidget(self.sprite_lbl)

        info_box = QVBoxLayout()
        info_box.setSpacing(4)
        self.name_lbl = QLabel("Select a Pokémon")
        self.name_lbl.setStyleSheet("color: #f8fafc; font-size: 15px; font-weight: bold;")
        info_box.addWidget(self.name_lbl)

        self.type_row = QHBoxLayout()
        self.type_row.setSpacing(4)
        info_box.addLayout(self.type_row)

        self.bst_lbl = QLabel("BST: ---")
        self.bst_lbl.setStyleSheet("color: #94a3b8; font-size: 11px;")
        info_box.addWidget(self.bst_lbl)

        b_layout.addLayout(info_box, 1)
        layout.addWidget(banner)

        # Catch Probability Box
        prob_frame = QFrame()
        prob_frame.setObjectName("prob_frame")
        prob_frame.setStyleSheet("""
            QFrame#prob_frame {
                background-color: #0c121d;
                border: 1px solid #1e293b;
                border-radius: 6px;
            }
            QLabel {
                border: none;
                background: transparent;
                padding: 0px;
            }
        """)
        pf_layout = QVBoxLayout(prob_frame)
        pf_layout.setContentsMargins(10, 8, 10, 8)
        pf_layout.setSpacing(4)

        pf_title = QLabel("🎯 CATCH PROBABILITY")
        pf_title.setStyleSheet("color: #f59e0b; font-size: 10px; font-weight: bold; letter-spacing: 1px;")
        pf_layout.addWidget(pf_title)

        self.quick_ball_lbl = QLabel("⚡ Quick Ball (Turn 1): ---")
        self.quick_ball_lbl.setStyleSheet("color: #e2e8f0; font-size: 11px;")
        pf_layout.addWidget(self.quick_ball_lbl)

        self.false_swipe_lbl = QLabel("⚔️ False Swipe + Ultra: ---")
        self.false_swipe_lbl.setStyleSheet("color: #e2e8f0; font-size: 11px;")
        pf_layout.addWidget(self.false_swipe_lbl)

        self.timer_ball_lbl = QLabel("⏱️ Timer Ball (Turn 5+): ---")
        self.timer_ball_lbl.setStyleSheet("color: #e2e8f0; font-size: 11px;")
        pf_layout.addWidget(self.timer_ball_lbl)
        layout.addWidget(prob_frame)

        # Base Stats Bars Container
        stats_frame = QFrame()
        stats_frame.setObjectName("stats_frame")
        stats_frame.setStyleSheet("""
            QFrame#stats_frame {
                background-color: #0c121d;
                border: 1px solid #1e293b;
                border-radius: 6px;
            }
            QLabel {
                border: none;
                background: transparent;
                padding: 0px;
            }
        """)
        sf_layout = QVBoxLayout(stats_frame)
        sf_layout.setContentsMargins(10, 8, 10, 8)
        sf_layout.setSpacing(4)

        sf_title = QLabel("📊 BASE STATS")
        sf_title.setStyleSheet("color: #38bdf8; font-size: 10px; font-weight: bold; letter-spacing: 1px;")
        sf_layout.addWidget(sf_title)

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
            row.addWidget(bar, 1)

            val_lbl = QLabel("---")
            val_lbl.setFixedWidth(26)
            val_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            val_lbl.setStyleSheet("color: #f1f5f9; font-size: 10px; font-weight: bold;")
            row.addWidget(val_lbl)

            self.stat_bars[stat] = (bar, val_lbl)
            sf_layout.addLayout(row)

        layout.addWidget(stats_frame)

        # Abilities & Held Items
        extra_frame = QFrame()
        extra_frame.setObjectName("extra_frame")
        extra_frame.setStyleSheet("""
            QFrame#extra_frame {
                background-color: #0c121d;
                border: 1px solid #1e293b;
                border-radius: 6px;
            }
            QLabel {
                border: none;
                background: transparent;
                padding: 0px;
            }
        """)
        ef_layout = QVBoxLayout(extra_frame)
        ef_layout.setContentsMargins(10, 8, 10, 8)
        ef_layout.setSpacing(4)

        self.ability_lbl = QLabel("Abilities: ---")
        self.ability_lbl.setWordWrap(True)
        self.ability_lbl.setStyleSheet("color: #cbd5e1; font-size: 11px;")
        ef_layout.addWidget(self.ability_lbl)

        self.hidden_ability_lbl = QLabel("Hidden Ability: ---")
        self.hidden_ability_lbl.setStyleSheet("color: #38bdf8; font-size: 11px; font-weight: bold;")
        ef_layout.addWidget(self.hidden_ability_lbl)

        self.items_lbl = QLabel("Wild Held Items: None")
        self.items_lbl.setWordWrap(True)
        self.items_lbl.setStyleSheet("color: #facc15; font-size: 11px;")
        ef_layout.addWidget(self.items_lbl)

        layout.addWidget(extra_frame)
        layout.addStretch()

        # Jump to Pokédex Full View Button
        self.open_pokedex_btn = QPushButton("📖 View Learnset & Evolution in Pokédex")
        self.open_pokedex_btn.setFixedHeight(34)
        self.open_pokedex_btn.setCursor(QCursor(Qt.PointingHandCursor))
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
        self.open_pokedex_btn.clicked.connect(self.on_open_pokedex_clicked)
        layout.addWidget(self.open_pokedex_btn)

    def populate(self, data: dict):
        self.current_species_id = data["species_id"]
        pid = data["species_id"]
        name = data["species_name"]

        self.name_lbl.setText(f"#{pid:04d} {name}")
        pm = get_species_pixmap(pid, is_silhouette=False)
        if pm:
            self.sprite_lbl.setPixmap(pm.scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            self.sprite_lbl.setText("🐾")

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

        bst = data.get("bst", 0)
        self.bst_lbl.setText(f"Total BST: {bst}")

        # Catch probabilities
        cr = data.get("catch_rate", 45)
        # Gen 3 catch rate math approximation
        # Quick ball on turn 1 = 5x ball modifier
        qb_chance = min(100, int(cr * 5 / 3))
        fs_chance = min(100, int(cr * 2 * 3.5 / 2.5))  # 1 HP + Sleep + Ultra
        tb_chance = min(100, int(cr * 4 / 2.5))

        self.quick_ball_lbl.setText(f"⚡ Quick Ball (Turn 1): {qb_chance}% capture chance")
        self.false_swipe_lbl.setText(f"⚔️ False Swipe + Ultra: {fs_chance}% capture chance")
        self.timer_ball_lbl.setText(f"⏱️ Timer Ball (Turn 5+): {tb_chance}% capture chance")

        # Stats
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

        ab = data.get("abilities", "None")
        ha = data.get("hidden_ability", "None")
        self.ability_lbl.setText(f"Abilities: {ab}")
        self.hidden_ability_lbl.setText(f"Hidden Ability: {ha}")

        held = data.get("held_items")
        if held and held != "None":
            self.items_lbl.setText(f"🎁 Held Items: {held}")
        else:
            self.items_lbl.setText("Wild Held Items: None")

    def on_open_pokedex_clicked(self):
        if self.current_species_id:
            self.open_in_pokedex.emit(self.current_species_id)


class ModernLegendaryCard(QFrame):
    """
    Polished graphical card for Legendary & Mythical Pokémon.
    Features 68x68 sprite, glowing gold/purple border, type pills, location,
    generation badge, unlock preview, and 1-click caught toggle button.
    """
    clicked = Signal(dict)
    catch_toggled = Signal(int, str, bool)

    def __init__(self, leg_data: dict, parent=None):
        super().__init__(parent)
        self.leg_data = leg_data
        self.species_id = leg_data.get("species_id", 0)
        self.name = leg_data.get("name", "Unknown")
        self.is_caught = leg_data.get("is_caught", False)
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.init_ui()

    def init_ui(self):
        self.setMinimumWidth(240)
        self.setFixedHeight(125)
        self.update_card_style(is_selected=False)

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(10, 8, 10, 8)
        main_layout.setSpacing(10)

        # Left Column: Large Sprite Box with Gold/Purple Legendary styling
        sprite_box = QFrame()
        sprite_box.setFixedSize(68, 68)
        border_col = "#eab308" if self.is_caught else "#6366f1"
        bg_col = "#1c1917" if self.is_caught else "#1e1b4b"
        sprite_box.setStyleSheet(f"""
            background-color: {bg_col};
            border: 1.5px solid {border_col};
            border-radius: 8px;
        """)
        sb_layout = QVBoxLayout(sprite_box)
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
        main_layout.addWidget(sprite_box, alignment=Qt.AlignVCenter)

        # Center Column: Info & Unlock Details
        info_col = QVBoxLayout()
        info_col.setContentsMargins(0, 0, 0, 0)
        info_col.setSpacing(3)

        # Row 1: Dex # + Name + Gen Tag
        title_box = QHBoxLayout()
        title_box.setSpacing(6)
        if self.species_id > 0:
            dex_num = QLabel(f"#{self.species_id:04d}")
            dex_num.setStyleSheet("color: #facc15; font-size: 11px; font-weight: bold;")
            title_box.addWidget(dex_num)

        name_lbl = QLabel(f"⭐ {self.name}")
        name_lbl.setStyleSheet("color: #f8fafc; font-size: 14px; font-weight: bold;")
        title_box.addWidget(name_lbl)

        gen = self.leg_data.get("generation", "")
        if gen:
            gen_clean = gen.replace("Generation ", "Gen ").replace("Native", "").strip()
            gen_lbl = QLabel(gen_clean)
            gen_lbl.setStyleSheet("""
                background-color: #312e81;
                color: #c7d2fe;
                border: 1px solid #4338ca;
                border-radius: 3px;
                padding: 1px 5px;
                font-size: 9px;
                font-weight: bold;
            """)
            title_box.addWidget(gen_lbl)

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
        loc_tag = QLabel(f"📍 {loc}")
        loc_tag.setStyleSheet("color: #38bdf8; font-size: 11px; font-weight: 500;")
        loc_box.addWidget(loc_tag)
        loc_box.addStretch()
        info_col.addLayout(loc_box)

        # Row 4: Unlock Requirements Preview
        req = self.leg_data.get("requirements", "")
        req_lbl = QLabel(f"🔓 {req[:46]}..." if len(req) > 46 else f"🔓 {req}")
        req_lbl.setStyleSheet("color: #94a3b8; font-size: 10px;")
        info_col.addWidget(req_lbl)

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

    def update_card_style(self, is_selected=False):
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

    def update_caught_button_state(self):
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
        self.setStyleSheet("""
            LegendaryInspectorDrawer {
                background-color: #0a0f1d;
                border: 1px solid #1e293b;
                border-radius: 8px;
            }
        """)

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
        profile_frame = QFrame()
        profile_frame.setStyleSheet("""
            background-color: #0f172a;
            border: 1px solid #312e81;
            border-radius: 8px;
            padding: 8px;
        """)
        pf_layout = QHBoxLayout(profile_frame)
        pf_layout.setSpacing(12)

        self.sprite_lbl = QLabel()
        self.sprite_lbl.setFixedSize(88, 88)
        self.sprite_lbl.setAlignment(Qt.AlignCenter)
        self.sprite_lbl.setStyleSheet("background-color: #0b111a; border: 1px solid #4338ca; border-radius: 8px;")
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
        layout.addWidget(profile_frame)

        # Scrollable Content Area for Requirements & Lore
        content_scroll = QScrollArea()
        content_scroll.setWidgetResizable(True)
        content_scroll.setStyleSheet("background: transparent; border: none;")
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(10)

        # Unlock Requirements Box
        req_frame = QFrame()
        req_frame.setStyleSheet("""
            background-color: #0c121d;
            border: 1px solid #e11d48;
            border-radius: 6px;
            padding: 8px 10px;
        """)
        rf_layout = QVBoxLayout(req_frame)
        rf_layout.setContentsMargins(4, 4, 4, 4)
        rf_layout.setSpacing(4)
        rf_title = QLabel("🔓 UNLOCK REQUIREMENTS & ACCESS")
        rf_title.setStyleSheet("color: #fb7185; font-size: 10px; font-weight: bold; letter-spacing: 1px;")
        rf_layout.addWidget(rf_title)
        self.req_lbl = QLabel("---")
        self.req_lbl.setWordWrap(True)
        self.req_lbl.setStyleSheet("color: #f1f5f9; font-size: 11px; line-height: 1.4;")
        rf_layout.addWidget(self.req_lbl)
        scroll_layout.addWidget(req_frame)

        # Party Synergy / Multi-Use Squad Box
        syn_frame = QFrame()
        syn_frame.setStyleSheet("""
            background-color: #0c121d;
            border: 1px solid #0284c7;
            border-radius: 6px;
            padding: 8px 10px;
        """)
        sf_layout = QVBoxLayout(syn_frame)
        sf_layout.setContentsMargins(4, 4, 4, 4)
        sf_layout.setSpacing(4)
        sf_title = QLabel("🧭 RECOMMENDED PARTY SYNERGY")
        sf_title.setStyleSheet("color: #38bdf8; font-size: 10px; font-weight: bold; letter-spacing: 1px;")
        sf_layout.addWidget(sf_title)
        self.syn_lbl = QLabel("---")
        self.syn_lbl.setWordWrap(True)
        self.syn_lbl.setStyleSheet("color: #e2e8f0; font-size: 11px;")
        sf_layout.addWidget(self.syn_lbl)
        scroll_layout.addWidget(syn_frame)

        # Base Stats Bars Container
        stats_frame = QFrame()
        stats_frame.setStyleSheet("""
            background-color: #0c121d;
            border: 1px solid #1e293b;
            border-radius: 6px;
            padding: 8px 10px;
        """)
        st_layout = QVBoxLayout(stats_frame)
        st_layout.setContentsMargins(4, 4, 4, 4)
        st_layout.setSpacing(4)
        st_title = QLabel("📊 BASE STATS")
        st_title.setStyleSheet("color: #facc15; font-size: 10px; font-weight: bold; letter-spacing: 1px;")
        st_layout.addWidget(st_title)

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
            bar.setStyleSheet("""
                QProgressBar {
                    background-color: #1e293b;
                    border-radius: 4px;
                }
                QProgressBar::chunk {
                    background-color: #eab308;
                    border-radius: 4px;
                }
            """)
            row.addWidget(bar, 1)

            val_lbl = QLabel("0")
            val_lbl.setFixedWidth(28)
            val_lbl.setAlignment(Qt.AlignRight)
            val_lbl.setStyleSheet("color: #f8fafc; font-size: 10px;")
            row.addWidget(val_lbl)

            st_layout.addLayout(row)
            self.stat_bars[stat] = (bar, val_lbl)

        scroll_layout.addWidget(stats_frame)

        # Catch Probability Box
        prob_frame = QFrame()
        prob_frame.setStyleSheet("""
            background-color: #0c121d;
            border: 1px solid #1e293b;
            border-radius: 6px;
            padding: 8px 10px;
        """)
        pf2_layout = QVBoxLayout(prob_frame)
        pf2_layout.setContentsMargins(4, 4, 4, 4)
        pf2_layout.setSpacing(4)
        pf2_title = QLabel("🎯 CATCH PROBABILITY")
        pf2_title.setStyleSheet("color: #f59e0b; font-size: 10px; font-weight: bold; letter-spacing: 1px;")
        pf2_layout.addWidget(pf2_title)

        self.quick_ball_lbl = QLabel("⚡ Quick Ball (Turn 1): ---")
        self.quick_ball_lbl.setStyleSheet("color: #e2e8f0; font-size: 11px;")
        pf2_layout.addWidget(self.quick_ball_lbl)

        self.false_swipe_lbl = QLabel("⚔️ False Swipe + Ultra: ---")
        self.false_swipe_lbl.setStyleSheet("color: #e2e8f0; font-size: 11px;")
        pf2_layout.addWidget(self.false_swipe_lbl)

        self.timer_ball_lbl = QLabel("⏱️ Timer Ball (Turn 5+): ---")
        self.timer_ball_lbl.setStyleSheet("color: #e2e8f0; font-size: 11px;")
        pf2_layout.addWidget(self.timer_ball_lbl)
        scroll_layout.addWidget(prob_frame)

        content_scroll.setWidget(scroll_widget)
        layout.addWidget(content_scroll, 1)

        # View in Pokedex Button
        self.btn_open_pokedex = QPushButton("📖 View Learnset & Stats in Pokédex")
        self.btn_open_pokedex.setFixedHeight(34)
        self.btn_open_pokedex.setCursor(QCursor(Qt.PointingHandCursor))
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
        self.btn_open_pokedex.clicked.connect(self.on_open_pokedex_clicked)
        layout.addWidget(self.btn_open_pokedex)

    def populate(self, leg_data: dict):
        self.current_species_id = leg_data.get("species_id", 0)
        self.dex_lbl.setText(f"#{self.current_species_id:04d}" if self.current_species_id > 0 else "")
        self.name_lbl.setText(leg_data.get("name", "Unknown"))
        self.bst_lbl.setText(f"Total BST: {leg_data.get('bst', '---')}")

        # Update sprite
        pm = get_species_pixmap(self.current_species_id, is_silhouette=False)
        if pm:
            self.sprite_lbl.setPixmap(pm.scaled(80, 80, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            self.sprite_lbl.setText("👑")

        # Types
        while self.types_layout.count():
            item = self.types_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        t1 = leg_data.get("type1")
        t2 = leg_data.get("type2")
        if t1 and t1 != "None":
            self.types_layout.addWidget(TypeBadge(t1))
        if t2 and t2 != "None" and t2 != t1:
            self.types_layout.addWidget(TypeBadge(t2))
        self.types_layout.addStretch()

        # Requirements and Synergy
        self.req_lbl.setText(leg_data.get("requirements", "No special unlock requirements reported."))
        syn = leg_data.get("synergy", "")
        if not syn or syn == "None":
            syn = "Standard High-Level Battle (False Swipe + Spore/Sleep recommended)."
        self.syn_lbl.setText(syn)

        # Base stats
        for stat, (bar, lbl) in self.stat_bars.items():
            val = leg_data.get(stat.lower(), 0)
            bar.setValue(val)
            lbl.setText(str(val))

        # Catch calculations
        cr = leg_data.get("catch_rate", 3)
        if cr <= 0:
            cr = 3
        qb_pct = min(99.0, max(1.0, (cr * 5.0 / 3.0 / 255.0) * 100))
        fs_pct = min(99.0, max(1.0, (cr * 2.0 * 2.5 / 255.0) * 100))
        tb_pct = min(99.0, max(1.0, (cr * 4.0 * 2.5 / 255.0) * 100))

        self.quick_ball_lbl.setText(f"⚡ Quick Ball (Turn 1): ~{qb_pct:.1f}%")
        self.false_swipe_lbl.setText(f"⚔️ False Swipe + Ultra (1 HP + Sleep): ~{fs_pct:.1f}%")
        self.timer_ball_lbl.setText(f"⏱️ Timer Ball (Turn 5+ & 1 HP): ~{tb_pct:.1f}%")

    def on_open_pokedex_clicked(self):
        if self.current_species_id > 0:
            self.open_in_pokedex.emit(self.current_species_id)


class QuetzalMasterApp(QMainWindow):
    """Lead Orchestrator Window for Pokémon Quetzal Companion."""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("⚡ Pokémon Quetzal Master Companion & Strategy Hub")
        self.resize(1380, 890)
        self.setMinimumSize(1220, 780)
        self.setStyleSheet(MODERN_STYLESHEET)

        self.conn = sqlite3.connect(DB_PATH, timeout=15.0)
        self.cur = self.conn.cursor()
        self.cur.execute("PRAGMA journal_mode=WAL;")
        self.cur.execute("PRAGMA busy_timeout=10000;")

        # Load caught species
        self.cur.execute("SELECT species_id FROM caught_pokemon")
        self.caught_species = set(row[0] for row in self.cur.fetchall())

        self.current_region = "Hoenn"
        self.current_route_name = "ROUTE 101"
        self.filter_mode = "Show All"
        self.habitat_filter = "All"

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
        main_layout.setContentsMargins(12, 10, 12, 12)
        main_layout.setSpacing(8)

        # ==========================================
        # TOP HEADER & REAL-TIME SAVE STATUS
        # ==========================================
        header = QFrame()
        header.setStyleSheet("""
            QFrame {
                background-color: #0f172a;
                border: 1px solid #1e293b;
                border-radius: 8px;
                padding: 6px 14px;
            }
        """)
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(8, 4, 8, 4)
        h_layout.setSpacing(12)

        # Title
        title_col = QVBoxLayout()
        title_col.setSpacing(1)
        app_title = QLabel("⚡ QUETZAL MASTER COMPANION")
        app_title.setFont(QFont("Arial", 15, QFont.Bold))
        app_title.setStyleSheet("color: #38bdf8; letter-spacing: 0.5px;")
        title_col.addWidget(app_title)

        subtitle = QLabel("Gen 1–9 Multi-Region DexNav & Strategic Guide")
        subtitle.setStyleSheet("color: #64748b; font-size: 11px;")
        title_col.addWidget(subtitle)
        h_layout.addLayout(title_col)

        h_layout.addStretch()

        # Save Info & Caught Progress
        save_col = QVBoxLayout()
        save_col.setSpacing(2)
        save_col.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.save_status_lbl = QLabel(f"💾 Player: NIG • Caught: {len(self.caught_species)} / 1,499 ({len(self.caught_species)/1499*100:.1f}%)")
        self.save_status_lbl.setStyleSheet("color: #f1f5f9; font-size: 12px; font-weight: bold;")
        save_col.addWidget(self.save_status_lbl, alignment=Qt.AlignRight)

        self.live_watcher_badge = QLabel("🟢 Live Save Sync Active (Auto-Refreshes On In-Game Save)")
        self.live_watcher_badge.setStyleSheet("color: #10b981; font-size: 10px; font-weight: bold;")
        save_col.addWidget(self.live_watcher_badge, alignment=Qt.AlignRight)

        h_layout.addLayout(save_col)

        # Manual Sync Button
        self.sync_btn = QPushButton("↻ Resync .SAV")
        self.sync_btn.setFixedHeight(30)
        self.sync_btn.setCursor(QCursor(Qt.PointingHandCursor))
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
        self.sync_btn.clicked.connect(self.sync_save_file)
        h_layout.addWidget(self.sync_btn)

        main_layout.addWidget(header)

        # ==========================================
        # TABS CONTAINER
        # ==========================================
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs, 1)

        self.create_encounter_tab()
        self.create_map_tab()
        self.create_pokedex_tab()
        self.create_trainers_tab()
        self.create_legendaries_tab()
        self.create_legendary_roadmap_tab()
        self.create_calculator_tab()

    # ==========================================
    # TAB 0: ROUTE ENCOUNTER EXPLORER
    # ==========================================
    def create_encounter_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Top Controls Bar
        controls = QFrame()
        controls.setObjectName("top_controls")
        controls.setStyleSheet("""
            QFrame#top_controls {
                background-color: #0f172a;
                border: 1px solid #1e293b;
                border-radius: 6px;
            }
        """)
        c_layout = QHBoxLayout(controls)
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

        layout.addWidget(controls)

        # Habitat Filter Pills
        habitat_bar = QHBoxLayout()
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

        layout.addLayout(habitat_bar)

        # Splitter: Encounter Card Grid (Left) | Inspector Drawer (Right)
        splitter = QSplitter(Qt.Horizontal)

        self.cards_scroll = QScrollArea()
        self.cards_scroll.setWidgetResizable(True)
        self.cards_container = QWidget()
        self.cards_grid = QGridLayout(self.cards_container)
        self.cards_grid.setContentsMargins(4, 4, 4, 4)
        self.cards_grid.setSpacing(10)
        self.cards_scroll.setWidget(self.cards_container)
        splitter.addWidget(self.cards_scroll)

        # Right Inspector Drawer
        self.inspector_drawer = SpeciesInspectorDrawer()
        self.inspector_drawer.open_in_pokedex.connect(self.jump_to_pokedex_mon)
        splitter.addWidget(self.inspector_drawer)

        splitter.setStretchFactor(0, 7)
        splitter.setStretchFactor(1, 3)
        layout.addWidget(splitter, 1)

        self.tabs.addTab(tab, "🗺️ Route Encounters")

        self.populate_route_list()

    def set_caught_filter(self, mode: str):
        self.filter_mode = mode
        self.update_filter_button_styles()
        self.filter_route_cards()

    def update_filter_button_styles(self):
        for btn, mode in zip(self.filter_buttons, ["Show All", "Missing Only", "Caught Only"]):
            active = (mode == self.filter_mode)
            btn.setChecked(active)
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
        self.habitat_filter = hab
        self.update_habitat_button_styles()
        self.filter_route_cards()

    def update_habitat_button_styles(self):
        for hab, btn in self.hab_buttons.items():
            active = (hab == self.habitat_filter)
            btn.setChecked(active)
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
        self.populate_route_list()

    def on_prev_route(self):
        idx = self.route_combo.currentIndex()
        if idx > 0:
            self.route_combo.setCurrentIndex(idx - 1)

    def on_next_route(self):
        idx = self.route_combo.currentIndex()
        if idx < self.route_combo.count() - 1:
            self.route_combo.setCurrentIndex(idx + 1)

    def on_route_changed(self):
        self.load_current_route_encounters()

    def load_current_route_encounters(self):
        route = self.route_combo.currentText()
        if not route:
            return
        self.current_route_name = route
        reg = self.region_combo.currentText()

        sql = """
            SELECT e.method, e.slot, e.chance, e.min_level, e.max_level, e.species_id, e.species_name,
                   p.type1, p.type2, p.abilities, p.hidden_ability, p.held_items,
                   p.hp, p.atk, p.def, p.spa, p.spd, p.spe, p.bst, p.catch_rate
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
            key = (r[0], r[1], r[5])
            if key in seen_keys:
                continue
            seen_keys.add(key)

            d = {
                "method": r[0], "slot": r[1], "chance": r[2], "min_level": r[3], "max_level": r[4],
                "species_id": r[5], "species_name": r[6], "type1": r[7], "type2": r[8],
                "abilities": r[9], "hidden_ability": r[10], "held_items": r[11],
                "hp": r[12], "atk": r[13], "def": r[14], "spa": r[15], "spd": r[16], "spe": r[17],
                "bst": r[18], "catch_rate": r[19],
                "is_caught": r[5] in self.caught_species
            }
            self.current_route_data.append(d)

        # Update Route Completion Badge
        total_unique = len(set(d["species_id"] for d in self.current_route_data))
        caught_unique = len(set(d["species_id"] for d in self.current_route_data if d["is_caught"]))
        pct = (caught_unique / total_unique * 100) if total_unique > 0 else 0

        self.route_progress_badge.setText(f"{route}: {caught_unique} / {total_unique} Caught ({pct:.1f}%)")
        if total_unique > 0 and caught_unique >= total_unique:
            self.route_progress_badge.setStyleSheet("background-color: #064e3b; color: #34d399; border: 1px solid #10b981; border-radius: 4px; padding: 4px 10px; font-weight: bold;")
        else:
            self.route_progress_badge.setStyleSheet("background-color: #1e293b; color: #facc15; border: 1px solid #eab308; border-radius: 4px; padding: 4px 10px; font-weight: bold;")

        self.filter_route_cards()

        # Populate inspector drawer with first mon if available
        if self.current_route_data:
            self.inspector_drawer.populate(self.current_route_data[0])

    def filter_route_cards(self):
        # Clear existing cards in grid
        while self.cards_grid.count():
            item = self.cards_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        search_query = self.route_mon_search.text().strip().lower()

        filtered = []
        for d in self.current_route_data:
            # Search query
            if search_query:
                if search_query not in d["species_name"].lower() and search_query not in str(d["species_id"]):
                    continue

            # Caught status filter
            if self.filter_mode == "Missing Only" and d["is_caught"]:
                continue
            if self.filter_mode == "Caught Only" and not d["is_caught"]:
                continue

            # Habitat filter
            meth = d.get("method", "")
            if self.habitat_filter == "Land" and "Grass" not in meth:
                continue
            if self.habitat_filter == "Water" and "Surfing" not in meth:
                continue
            if self.habitat_filter == "Beach" and "Beach" not in meth:
                continue
            if self.habitat_filter == "Rock" and "Rock" not in meth:
                continue
            if self.habitat_filter == "Fishing" and "Fishing" not in meth:
                continue
            if self.habitat_filter == "Hidden" and "Hidden" not in meth:
                continue

            filtered.append(d)

        # Populate Grid (2 columns for clean spaciousness)
        self.all_rendered_cards = []
        for idx, mon_data in enumerate(filtered):
            card = ModernEncounterCard(mon_data)
            card.clicked.connect(self.on_encounter_card_clicked)
            card.catch_toggled.connect(self.on_encounter_catch_toggled)
            r = idx // 2
            c = idx % 2
            self.cards_grid.addWidget(card, r, c)
            self.all_rendered_cards.append(card)

        # If empty
        if not filtered:
            empty_lbl = QLabel(f"No encounters match your current filters on {self.current_route_name}.")
            empty_lbl.setAlignment(Qt.AlignCenter)
            empty_lbl.setStyleSheet("color: #64748b; font-size: 14px; padding: 40px;")
            self.cards_grid.addWidget(empty_lbl, 0, 0, 1, 2)

    def on_encounter_card_clicked(self, mon_data: dict):
        self.inspector_drawer.populate(mon_data)
        for card in self.all_rendered_cards:
            is_sel = (card.species_id == mon_data["species_id"])
            card.update_card_style(is_selected=is_sel)

    def on_encounter_catch_toggled(self, species_id: int, species_name: str, is_caught: bool):
        if is_caught:
            self.caught_species.add(species_id)
            self.cur.execute("INSERT OR REPLACE INTO caught_pokemon (species_id, species_name) VALUES (?, ?)", (species_id, species_name))
        else:
            self.caught_species.discard(species_id)
            self.cur.execute("DELETE FROM caught_pokemon WHERE species_id = ?", (species_id,))
        self.conn.commit()

        # Update summary badge
        self.save_status_lbl.setText(f"💾 Player: NIG • Caught: {len(self.caught_species)} / 1,499 ({len(self.caught_species)/1499*100:.1f}%)")

        # Update route stats
        total_unique = len(set(d["species_id"] for d in self.current_route_data))
        caught_unique = len(set(d["species_id"] for d in self.current_route_data if d["is_caught"]))
        pct = (caught_unique / total_unique * 100) if total_unique > 0 else 0
        self.route_progress_badge.setText(f"{self.current_route_name}: {caught_unique} / {total_unique} Caught ({pct:.1f}%)")

        # Update map widget stats if instantiated
        if hasattr(self, 'map_widget'):
            self.map_widget.load_data_from_db(DB_PATH)

    # ==========================================
    # TAB 1: REGIONAL TOWN MAP
    # ==========================================
    def create_map_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        self.map_widget = RegionalMapWidget(db_path=DB_PATH)
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
            for i in range(self.route_combo.count()):
                if route_clean in self.route_combo.itemText(i) or self.route_combo.itemText(i) in route_clean:
                    self.route_combo.setCurrentIndex(i)
                    break

        # Jump to Tab 0
        self.tabs.setCurrentIndex(0)

    # ==========================================
    # TAB 2: POKÉDEX & AREA HABITAT LOCATOR
    # ==========================================
    def create_pokedex_tab(self):
        tab = QWidget()
        layout = QHBoxLayout(tab)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(12)

        # Left Column: Species List & Instant Filter
        left_box = QVBoxLayout()
        left_box.setSpacing(6)

        left_box.addWidget(QLabel("National Pokédex (#1 – #1,499):"))
        self.pokedex_search = QLineEdit()
        self.pokedex_search.setPlaceholderText("Search species (e.g. Breloom, Ralts, #285)...")
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
        p_header = QFrame()
        p_header.setStyleSheet("""
            background-color: #0f172a;
            border: 1px solid #1e293b;
            border-radius: 8px;
            padding: 8px 14px;
        """)
        ph_layout = QHBoxLayout(p_header)
        ph_layout.setContentsMargins(8, 4, 8, 4)
        ph_layout.setSpacing(12)

        self.pokedex_sprite = QLabel()
        self.pokedex_sprite.setFixedSize(64, 64)
        self.pokedex_sprite.setAlignment(Qt.AlignCenter)
        ph_layout.addWidget(self.pokedex_sprite)

        title_col = QVBoxLayout()
        title_col.setSpacing(3)
        self.pokedex_name_lbl = QLabel("#0001 Bulbasaur")
        self.pokedex_name_lbl.setStyleSheet("color: #f8fafc; font-size: 16px; font-weight: bold;")
        title_col.addWidget(self.pokedex_name_lbl)

        self.pokedex_types_row = QHBoxLayout()
        self.pokedex_types_row.setSpacing(4)
        title_col.addLayout(self.pokedex_types_row)
        ph_layout.addLayout(title_col, 1)

        self.pokedex_caught_btn = QPushButton("○ MISSING")
        self.pokedex_caught_btn.setFixedSize(90, 32)
        self.pokedex_caught_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.pokedex_caught_btn.clicked.connect(self.on_pokedex_caught_clicked)
        ph_layout.addWidget(self.pokedex_caught_btn)

        right_box.addWidget(p_header)

        # Pokédex Sub-Tabs: Area Locator, Base Stats, Learnsets, Evolution
        self.pokedex_subtabs = QTabWidget()
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
        self.tabs.addTab(tab, "📖 Pokédex & Area Finder")

        self.populate_pokedex_list()

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
        self.cur.execute("SELECT id, name FROM pokemon ORDER BY id ASC")
        rows = self.cur.fetchall()

        self.pokedex_list.blockSignals(True)
        self.pokedex_list.clear()
        for pid, name in rows:
            tag = "✓" if pid in self.caught_species else "○"
            item = QListWidgetItem(f"#{pid:04d} {name}  {tag}")
            if pid in self.caught_species:
                item.setForeground(QColor("#34d399"))
            else:
                item.setForeground(QColor("#94a3b8"))
            self.pokedex_list.addItem(item)
        self.pokedex_list.blockSignals(False)

        if self.pokedex_list.count() > 0:
            self.pokedex_list.setCurrentRow(0)

    def filter_pokedex_list(self, query: str):
        q = query.strip().lower()
        for i in range(self.pokedex_list.count()):
            item = self.pokedex_list.item(i)
            match = (q in item.text().lower())
            item.setHidden(not match)

    def on_pokedex_mon_selected(self, row: int):
        if row < 0:
            return
        item = self.pokedex_list.item(row)
        if not item:
            return
        pid = int(item.text().split()[0].replace("#", ""))
        self.current_pokedex_mon_id = pid

        self.cur.execute("""
            SELECT name, hp, atk, def, spa, spd, spe, bst, type1, type2, catch_rate, abilities, hidden_ability
            FROM pokemon WHERE id = ?
        """, (pid,))
        r = self.cur.fetchone()
        if not r:
            return

        name, hp, atk, df, spa, spd, spe, bst, t1, t2, cr, ab, ha = r
        self.current_pokedex_mon_name = name

        self.pokedex_name_lbl.setText(f"#{pid:04d} {name} (Catch Rate: {cr})")

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
        reg_idx = self.region_combo.findText(region)
        if reg_idx >= 0:
            self.region_combo.setCurrentIndex(reg_idx)
        r_idx = self.route_combo.findText(route_name)
        if r_idx >= 0:
            self.route_combo.setCurrentIndex(r_idx)
        self.tabs.setCurrentIndex(0)

    def show_location_on_map(self, route_name: str, region: str):
        """Switches to Regional Town Map tab and highlights this route."""
        if hasattr(self, 'map_widget'):
            self.map_widget.set_region(region)
            self.map_widget.highlight_locations([route_name])
        self.tabs.setCurrentIndex(1)

    def jump_to_pokedex_mon(self, species_id: int):
        """Jumps directly to this Pokémon inside the Pokédex tab."""
        self.tabs.setCurrentIndex(2)
        # Find in list
        for i in range(self.pokedex_list.count()):
            item = self.pokedex_list.item(i)
            if f"#{species_id:04d}" in item.text():
                self.pokedex_list.setCurrentRow(i)
                break

    def on_pokedex_caught_clicked(self):
        if not hasattr(self, 'current_pokedex_mon_id'):
            return
        pid = self.current_pokedex_mon_id
        name = self.current_pokedex_mon_name
        is_c = pid in self.caught_species

        if is_c:
            self.caught_species.discard(pid)
            self.cur.execute("DELETE FROM caught_pokemon WHERE species_id = ?", (pid,))
        else:
            self.caught_species.add(pid)
            self.cur.execute("INSERT OR REPLACE INTO caught_pokemon (species_id, species_name) VALUES (?, ?)", (pid, name))
        self.conn.commit()

        self.update_pokedex_caught_btn(not is_c)
        self.populate_pokedex_list()
        self.save_status_lbl.setText(f"💾 Player: NIG • Caught: {len(self.caught_species)} / 1,499 ({len(self.caught_species)/1499*100:.1f}%)")

    def update_pokedex_caught_btn(self, is_caught: bool):
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

        self.trainer_cat_buttons[0].setChecked(True)
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
        layout.addWidget(self.trainers_table, 1)

        self.tabs.addTab(tab, "⚔️ Trainers & Frontier")

        self.populate_trainers_table()

    def populate_trainers_table(self):
        self.cur.execute("SELECT category, name, title, region, location, unlock_condition, team_preview, reward FROM trainers ORDER BY id ASC")
        self.all_trainers_data = self.cur.fetchall()
        self.filter_trainers()

    def filter_trainers(self, category: str = None):
        if category:
            self.selected_trainer_cat = category
            for btn in self.trainer_cat_buttons:
                btn.setChecked(btn.text() == category)

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
        self.leg_filter_mode = mode
        self.update_leg_filter_button_styles()
        self.filter_legendaries()

    def update_leg_filter_button_styles(self):
        for btn in self.leg_status_btns:
            is_active = (btn.text().endswith(self.leg_filter_mode) or btn.text() == self.leg_filter_mode)
            btn.setChecked(is_active)
            if is_active:
                btn.setStyleSheet("background-color: #0284c7; color: #FFFFFF; font-weight: bold; border-radius: 4px; padding: 2px 10px;")
            else:
                btn.setStyleSheet("background-color: #1e293b; color: #94a3b8; border: 1px solid #334155; border-radius: 4px; padding: 2px 10px;")

    def populate_legendaries_cards(self):
        self.cur.execute("""
            SELECT l.name, l.generation, l.level, l.location, l.requirements, l.synergy, l.notes,
                   MIN(p.id), p.type1, p.type2, p.hp, p.atk, p.def, p.spa, p.spd, p.spe, p.bst, p.catch_rate,
                   p.abilities, p.hidden_ability
            FROM legendaries l
            LEFT JOIN pokemon p ON LOWER(l.name) = LOWER(p.name)
            GROUP BY l.name
            ORDER BY l.name ASC
        """)
        rows = self.cur.fetchall()
        self.all_legendary_data = []
        for r in rows:
            name, gen, lvl, loc, req, syn, notes = r[:7]
            sp_id, t1, t2, hp, atk, df, spa, spd, spe, bst, cr, ab, ha = r[7:]
            sp_id = sp_id if sp_id else 0
            is_caught = sp_id in self.caught_species if sp_id else False
            d = {
                "name": name, "generation": gen, "level": lvl, "location": loc,
                "requirements": req, "synergy": syn, "notes": notes,
                "species_id": sp_id, "type1": t1, "type2": t2,
                "hp": hp or 0, "atk": atk or 0, "def": df or 0, "spa": spa or 0,
                "spd": spd or 0, "spe": spe or 0, "bst": bst or 0, "catch_rate": cr or 3,
                "abilities": ab, "hidden_ability": ha, "is_caught": is_caught
            }
            self.all_legendary_data.append(d)

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
        if is_caught:
            self.caught_species.add(species_id)
            self.cur.execute("INSERT OR IGNORE INTO caught_pokemon (species_id, species_name) VALUES (?, ?)", (species_id, species_name))
        else:
            self.caught_species.discard(species_id)
            self.cur.execute("DELETE FROM caught_pokemon WHERE species_id = ?", (species_id,))
        self.conn.commit()

        for d in self.all_legendary_data:
            if d["name"] == species_name:
                d["is_caught"] = is_caught

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
        hero_card = QFrame()
        hero_card.setStyleSheet("""
            background-color: #0f172a;
            border: 1px solid #1e293b;
            border-radius: 8px;
            padding: 10px 14px;
        """)
        h_layout = QVBoxLayout(hero_card)
        h_layout.setContentsMargins(6, 4, 6, 4)
        h_layout.setSpacing(4)

        title = QLabel("🧭 OPTIMAL DUAL-TYPE SQUAD & REGIONAL LEGENDARY ROADMAP")
        title.setFont(QFont("Arial", 13, QFont.Bold))
        title.setStyleSheet("color: #38bdf8;")
        h_layout.addWidget(title)

        subtitle = QLabel(
            "Solve all ancient statues, puzzle seals, and door requirements across Hoenn, Kanto, Johto, and Portals "
            "with zero repetitive PC backtracking by utilizing dual-type squad coverage."
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color: #94a3b8; font-size: 11px;")
        h_layout.addWidget(subtitle)
        layout.addWidget(hero_card)

        # Main Scroll Area for Roadmap
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background: transparent; border: none;")

        s_widget = QWidget()
        s_layout = QVBoxLayout(s_widget)
        s_layout.setContentsMargins(0, 0, 0, 0)
        s_layout.setSpacing(14)

        # Blueprint Frame: Hall of Fame Coverage Analysis
        bp_frame = QFrame()
        bp_frame.setStyleSheet("""
            background-color: #0c121d;
            border: 1.5px solid #0284c7;
            border-radius: 8px;
            padding: 12px;
        """)
        bp_layout = QVBoxLayout(bp_frame)
        bp_layout.setContentsMargins(8, 6, 8, 6)
        bp_layout.setSpacing(8)

        bp_title = QLabel("⭐ UNIVERSAL MULTI-USE SQUAD BLUEPRINT")
        bp_title.setFont(QFont("Arial", 11, QFont.Bold))
        bp_title.setStyleSheet("color: #38bdf8; letter-spacing: 0.5px;")
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
        bp_desc.setStyleSheet("color: #e2e8f0; font-size: 11px; line-height: 1.5;")
        bp_layout.addWidget(bp_desc)
        s_layout.addWidget(bp_frame)

        # Roadmap Sequence Cards
        phases = [
            ("PHASE 1: HOENN ANCIENT RUINS & WEATHER SUMMITS", "#059669", [
                ("Rayquaza", "Sky Pillar (Route 131 Rooftop)", "Defeat HoF. Bring Mach Bike or Flying Avatar (Aerodactyl).", "Flying / Dragon"),
                ("Kyogre", "Marine Cave (Routes 105, 125, 127, 129)", "Speak to Weather Institute scientist on Route 119. Bring Dive user (Swampert).", "Water"),
                ("Groudon", "Terra Cave (Routes 114, 115, 116, 118)", "Speak to Weather Institute scientist. Bring Ground / Water counter.", "Ground"),
                ("Regirock", "Desert Ruins (Route 111 Desert)", "Sealed Chamber unlock (Wailord #1, Relicanth #6, Dig). Walk 2 left, 2 down, Rock Smash.", "Rock"),
                ("Regice", "Island Cave (Route 105)", "Clockwise perimeter walk flush along room walls, inspect wall.", "Ice"),
                ("Registeel", "Ancient Tomb (Route 120)", "Stand at center and use Flash.", "Steel"),
                ("Latios / Latias", "Southern Island / Roaming Hoenn", "Obtain Eon Ticket, speak to Norman in Petalburg.", "Dragon / Psychic"),
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
                ("Raikou, Entei, Suicune", "Burned Tower & Roaming Johto", "Awaken beasts in Burned Tower basement in Ecruteak City.", "Electric / Fire / Water"),
                ("Lugia", "Whirl Islands Deep Chamber", "Bring Tidal Bell + Silver Wing from Goldenrod Radio Director + Whirlpool user.", "Psychic / Flying"),
                ("Ho-Oh", "Tin Tower Roof (Ecruteak City)", "Clear Bell + Rainbow Wing, defeat Ecruteak Wise Trio.", "Fire / Flying"),
                ("Celebi", "Ilex Forest Shrine", "Bring GS Ball to forest shrine.", "Grass / Psychic")
            ]),
            ("PHASE 4: DIMENSIONAL PORTALS & ULTRA EXPEDITIONS", "#7c3aed", [
                ("Dialga, Palkia, Giratina", "Spear Pillar Dimensional Rift", "Adamant, Lustrous, and Griseous Orbs required at dimensional anomaly.", "Dragon / Steel / Water / Ghost"),
                ("Reshiram, Zekrom, Kyurem", "Giant Chasm / Dragonspiral Tower", "Light Stone & Dark Stone triggers.", "Dragon / Fire / Electric / Ice"),
                ("Xerneas & Yveltal", "Geosenge Deep Ruins", "Power Plant Pass & Fairy/Dark dual keys.", "Fairy / Dark"),
                ("Necrozma & Ultra Beasts", "Ultra Megalopolis Portal", "Post-game Wormhole portal exploration.", "Psychic / Ultra"),
                ("Treasures of Ruin (Wo-Chien, Chien-Pao, Ting-Lu, Chi-Yu)", "Paldea Ruin Shrines", "Pull all 8 Ominous Stakes per elemental shrine.", "Dark + Grass / Ice / Ground / Fire")
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

        card = QFrame()
        card.setObjectName("calc_card")
        card.setStyleSheet("""
            QFrame#calc_card {
                background-color: #0f172a;
                border: 1px solid #1e293b;
                border-radius: 8px;
            }
            QPushButton {
                background-color: #2563eb;
                color: #FFFFFF;
                font-size: 13px;
                font-weight: bold;
                border-radius: 6px;
                padding: 6px 14px;
            }
            QPushButton:hover {
                background-color: #3b82f6;
            }
        """)
        c_layout = QVBoxLayout(card)
        c_layout.setContentsMargins(16, 16, 16, 16)
        c_layout.setSpacing(12)

        title = QLabel("🎯 Quick Ball vs False Swipe Capture Calculator")
        title.setFont(QFont("Arial", 14, QFont.Bold))
        title.setStyleSheet("color: #38bdf8;")
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
        self.calc_result_lbl.setStyleSheet("color: #34d399; font-size: 16px; font-weight: bold; padding: 10px 0;")
        c_layout.addWidget(self.calc_result_lbl)

        calc_btn = QPushButton("Calculate Capture Rate")
        calc_btn.setFixedHeight(34)
        calc_btn.setCursor(QCursor(Qt.PointingHandCursor))
        calc_btn.setStyleSheet("background-color: #2563eb; color: #FFFFFF; font-weight: bold; border-radius: 6px;")
        calc_btn.clicked.connect(self.calculate_catch_rate)
        c_layout.addWidget(calc_btn)

        layout.addWidget(card)
        layout.addStretch()

        self.tabs.addTab(tab, "🎯 Catch Calculator")
        self.calculate_catch_rate()

    def calculate_catch_rate(self):
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

            self.save_status_lbl.setText(f"💾 Player: NIG • Caught: {len(self.caught_species)} / 1,499 ({len(self.caught_species)/1499*100:.1f}%)")
            self.live_watcher_badge.setText(f"🟢 Live Save Synced ({time.strftime('%H:%M:%S')})")

            # Reload active route
            self.load_current_route_encounters()
            self.populate_pokedex_list()
            self.populate_legendaries_table()

            if hasattr(self, 'map_widget'):
                self.map_widget.load_data_from_db(DB_PATH)
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
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
